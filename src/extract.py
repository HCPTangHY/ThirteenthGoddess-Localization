# Thirteenth Goddess (Godot 4) 通用字符串提取：扫描所有字符串字面量 → 黑名单过滤 → 结构化 key
# 用法: python3 extract_tg.py <recovered_root> <out_root/version>
import os, re, sys, json, collections

SKIP_DIRS = ('scenes/debug', 'scenes/combat/sandbox')
SKIP_FILES = ('DebugBlockingNodes.gd',)
SKIP_CALL = re.compile(r'^(_make_player|_set_bus_volume|get_bus_index|log|print\w*|push_error|push_warning|assert|load|preload|get_node|get_node_or_null|has_node|find_child|find_children|emit_signal|connect|disconnect|has_method|has_signal|call|call_deferred|set_meta|get_meta|has_meta|remove_meta|is_in_group|add_to_group|get_nodes_in_group|play|travel|get_theme_\w+|add_theme_\w+|has_theme_\w+|set_shader_parameter|get_shader_parameter|tween_property|tween_method|has|erase|get|set|get_setting|set_setting|is_action\w*|has_animation|get_animation|begins_with|ends_with|split|replace|find|contains|matchn?|trim_\w+|load_threaded_\w+|ResourceLoader\.\w+|get_section_keys|get_value|set_value|has_section_key)$')
IDENT = re.compile(r'^[A-Za-z0-9_@./:%#\-\[\]]*$')
CAMEL = re.compile(r'^[A-Z][a-z0-9]+([A-Z][a-z0-9]*)+$')
STAGE = re.compile(r'^((LEFT|RIGHT|CENTER|MIDDLE)\w*@\w+,?)+$')
TSCN_PROPS = re.compile(r'^(text|tooltip_text|placeholder_text|title|dialog_text)\s*=\s*"')

def sem(s, n=40):
    return re.sub(r'[^A-Za-z0-9]+', '_', s[:n]).strip('_')

def is_text(s, ui=False):
    if 'res://' in s or 'user://' in s or STAGE.match(s): return False
    bare = re.sub(r'\[/?[^\]]*(\]|$)|^[^\[]*\]|\{[^}]*\}|%[-+0-9.]*[a-z%]', ' ', s)
    if not re.search(r'[A-Za-z]{2,}', bare): return False
    if ' ' not in s.strip() and IDENT.match(s) and (not s[0].isupper() or CAMEL.match(s) or re.search(r'[_@\d]|-[a-z]', s)): return False
    if not re.search(r'[a-z]', s):
        # 全大写：tscn 的 text 属性都算；gd 里要带空格或句末标点，避免吃掉 "SHY"/"BRATTY" 这类枚举值
        if ui: return bool(re.search(r'[A-Z]{2,}', bare))
        return bool(re.search(r'[A-Z]{2,}', bare) and re.search(r'[A-Z][ !?.:…]+\S|[A-Z][!?.…]$', s.strip()))
    return True

def scan_gd(src):
    out = []
    n = len(src); i = 0
    stack = []            # frames: [kind, label, idx, pending_key]
    top = '.'             # 当前顶层 const/var/func 名
    line_start = True
    while i < n:
        c = src[i]
        if line_start:
            m = re.match(r'(?:static\s+)?(func|const|var|class)\s+(\w+)', src[i:i+200])
            if m and not stack: top = m.group(2)
            line_start = False
        if c == '\n': line_start = True; i += 1; continue
        if c == '#': j = src.find('\n', i); i = n if j < 0 else j; continue
        if c in '{[(':
            f = stack[-1] if stack else None
            if f and f[0] == '{' and f[3]: label = f[3]
            elif f and f[0] == '[': label = str(f[2])
            else: label = ''
            stack.append([c, label, 0, None]); i += 1; continue
        if c in '}])':
            if stack: stack.pop()
            i += 1; continue
        if c == ',' and stack:
            stack[-1][2] += 1; stack[-1][3] = None; i += 1; continue
        if c.isalnum() or c == '_':
            m = re.match(r'\w+', src[i:]); w = m.group(0); j = i + len(w)
            if stack and stack[-1][0] == '{' and re.match(r'\s*[:=](?!=)', src[j:j+3]): stack[-1][3] = w
            i = j; continue
        if c in '"\'':
            prefix = src[i-1] if i else ''
            q = c * 3 if src.startswith(c * 3, i) else c
            j = i + len(q)
            while j < n and not src.startswith(q, j):
                j += 2 if src[j] == '\\' else 1
            s = src[i+len(q):j]; end = j + len(q); start = i + len(q)
            i = end
            f = stack[-1] if stack else None
            if f and f[0] == '{' and re.match(r'\s*:', src[end:end+3]):
                f[3] = s; continue                      # 字典键
            if prefix in '&^' or not is_text(s): continue
            ls = src.rfind('\n', 0, start) + 1
            before = src[ls:start-len(q)]
            if not stack and not before.strip() and not re.match(r'\s*[,)\]}+%]', src[end:end+2]): continue  # 文档字符串
            if f and f[0] == '(':
                m = re.search(r'([\w.]+)\s*\(\s*$', src[max(0, start-200):start-len(q)])
                if m and SKIP_CALL.match(m.group(1).split('.')[-1]): continue
            if re.search(r'\b(print\w*|push_error|push_warning|assert|\w*Logger\.log|_log)\s*\(', before): continue
            if f and f[0] == '{' and f[3] in ('anchor', 'sprite', 'bus', 'anim'): continue
            path = [top] + [fr[1] for fr in stack if fr[1]]
            if f and f[0] == '{' and f[3]: path.append(f[3])
            elif f and f[0] == '[': path.append(str(f[2]))
            else:
                m = re.match(r'\s*(?:var\s+)?([\w.]+)\s*[+]?=\s*$', before)
                path += ([m.group(1)] if m else []) + [sem(s)]
            out.append(('|'.join(path), s, start))
            continue
        i += 1
    return out

def scan_tscn(src):
    out = []; node = '.'; pos = 0
    for line in src.split('\n'):
        m = re.match(r'\[node name="([^"]+)"(?:.*?parent="([^"]*)")?', line)
        if m: node = f'{m.group(2) or ""}/{m.group(1)}'
        m = TSCN_PROPS.match(line)
        if m:
            start = pos + m.end(); j = start
            while j < len(src) and src[j] != '"': j += 2 if src[j] == '\\' else 1
            s = src[start:j]
            if is_text(s, ui=True): out.append((f'{node}|{m.group(1)}', s, start))
        pos += len(line) + 1
    return out

def main(root, out_root):
    total = 0; files = 0; stat = collections.Counter()
    for dp, ds, fs in os.walk(root):
        ds[:] = [d for d in ds if not d.startswith('.')]
        rel_dir = os.path.relpath(dp, root)
        if rel_dir.startswith(SKIP_DIRS): continue
        for fn in sorted(fs):
            if fn in SKIP_FILES or not fn.endswith(('.gd', '.tscn')): continue
            p = os.path.join(dp, fn); rel = os.path.relpath(p, root)
            src = open(p, encoding='utf-8', newline='').read()
            items = scan_gd(src) if fn.endswith('.gd') else scan_tscn(src)
            if not items: continue
            used = set(); entries = []
            for k, s, st in items:
                assert src[st:st+len(s)] == s
                key = k; i = 1
                while key in used: key = f'{k}#{i}'; i += 1
                used.add(key)
                entries.append({'key': key, 'original': s, 'translation': '', 'context': f'<<POS:{st+1:08d}>>'})
            op = os.path.join(out_root, rel + '.json')
            os.makedirs(os.path.dirname(op), exist_ok=True)
            json.dump(entries, open(op, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            total += len(entries); files += 1; stat[rel.split('/')[0] + ('/tscn' if fn.endswith('.tscn') else '')] += len(entries)
    print(f'files={files} entries={total}', dict(stat))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
