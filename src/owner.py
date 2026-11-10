# GDScript 字符串扫描：给每个字符串字面量算出 key（结构路径）和 owner（所属属性签名）
# owner 是规则匹配的依据，例如:
#   CARDS.card_name            const CARDS 里任意层级的 card_name 字段
#   CARDS.scene_text[]         card 的 scene_text 数组元素
#   DIALOGUE_HOOK[][4]         二维数组（元组）第 4 位
#   HELLO_LINES.#[]            数字键下的数组元素
#   =text                      函数里 xxx.text = "..."
#   call:append#0              函数里 append("...") 的第 0 个参数
#   =dialogue[][4]             函数里赋给 dialogue 的元组数组第 4 位
#   return / compare / match / in / expr / doc
import re

def _norm(k: str) -> str:
    return '#' if re.fullmatch(r'-?\d+', k) else k

def _code_anchor(before: str, nxt: str, at_top: bool) -> str:
    m = re.search(r'(?:var\s+|const\s+)?([\w.\]\[]+)\s*(?::\s*[\w\[\], ]*)?\s*(?:\+=|:=|=)\s*$', before)
    if m and not re.search(r'(==|!=|<=|>=)\s*$', before):
        name = re.split(r'[.\[]', m.group(1).rstrip(']'))[-1]
        return ('const:' if at_top else '=') + name
    if re.search(r'(==|!=)\s*$', before) or re.match(r'\s*(==|!=)', nxt): return 'compare'
    if re.search(r'\breturn\s*$', before): return 'return'
    if re.search(r'\bin\s*$', before) or re.match(r'\s+(not\s+)?in\b', nxt): return 'in'
    return 'expr'

def scan(src: str):
    """yield (key, owner, text, start_pos) for every string literal (dict keys / StringName / NodePath excluded)."""
    out = []
    n = len(src); i = 0
    st = []            # frame: dict(kind, label, idx, key, anchor, fn)
    top = '.'; in_func = False; line_start = True
    while i < n:
        c = src[i]
        if line_start:
            m = re.match(r'(static\s+)?(func|const|var|class|signal|enum)\s+(\w+)', src[i:i+200])
            if m and not st:
                top = m.group(3); in_func = m.group(2) == 'func'
            elif not st and re.match(r'\S', src[i:i+1]) and not m:
                in_func = in_func  # 续行/装饰器，保持
            line_start = False
        if c == '\n': line_start = True; i += 1; continue
        if c == '#': j = src.find('\n', i); i = n if j < 0 else j; continue
        if c in '{[(':
            f = st[-1] if st else None
            label = (f['key'] if f and f['kind'] == '{' and f['key'] else str(f['idx']) if f and f['kind'] == '[' else '')
            fn = None; anchor = None
            if c == '(':
                m = re.search(r'([\w.]+)\s*$', src[max(0, i-80):i]); fn = m.group(1).split('.')[-1] if m else ''
            if not st:
                ls = src.rfind('\n', 0, i) + 1
                anchor = _code_anchor(src[ls:i], '', not in_func)
                if anchor.startswith('const:'): anchor = anchor[6:]
            elif f['kind'] == '(':
                anchor = f'call:{f["fn"]}#{f["idx"]}'
            st.append(dict(kind=c, label=label, idx=0, key=None, anchor=anchor, fn=fn)); i += 1; continue
        if c in '}])':
            if st: st.pop()
            i += 1; continue
        if c == ',' and st: st[-1]['idx'] += 1; st[-1]['key'] = None; i += 1; continue
        if c.isalnum() or c == '_':
            m = re.match(r'\w+', src[i:]); w = m.group(0); j = i + len(w)
            if st and st[-1]['kind'] == '{' and re.match(r'\s*[:=](?!=)', src[j:j+3]): st[-1]['key'] = w
            i = j; continue
        if c in '"\'':
            prefix = src[i-1] if i else ''
            q = c * 3 if src.startswith(c * 3, i) else c
            j = i + len(q)
            while j < n and not src.startswith(q, j): j += 2 if src[j] == '\\' else 1
            s = src[i+len(q):j]; start = i + len(q); end = j + len(q); i = end
            f = st[-1] if st else None
            if f and f['kind'] == '{' and re.match(r'\s*:', src[end:end+3]): f['key'] = s; continue
            if prefix in '&^': continue
            ls = src.rfind('\n', 0, start) + 1
            before = src[ls:start-len(q)]; nxt = src[end:end+6]
            # ---- owner ----
            if not st:
                if not before.strip() and in_func and not re.match(r'\s*[,)\]}+%.]', nxt): owner = 'doc'
                elif re.match(r'\s*:\s*(#.*)?$', src[end:src.find('\n', end) if src.find('\n', end) > 0 else n]) and not before.strip(): owner = 'match'
                else:
                    owner = _code_anchor(before, nxt, not in_func)
                    if owner.startswith('const:'): owner = owner[6:]
            else:
                # 找容器链的根：最内层 '(' 或最外层容器
                ri = 0
                for k in range(len(st) - 1, -1, -1):
                    if st[k]['kind'] == '(':
                        ri = k; break
                root = st[ri]
                if f['kind'] == '(' and re.match(r'\s*(?:var\s+)?[\w.]+\s*(?::\s*\w+\s*)?(?:\+=|:=|=)\s*$', before) and src.rfind('(', 0, start) < ls:
                    owner = _code_anchor(before, nxt, False)   # 多行 lambda 体里的赋值，例如 connect(func(): var desc = "...")
                elif f['kind'] == '(':
                    owner = f'call:{f["fn"]}#{f["idx"]}'
                    if f['fn'] == 'get' and f['idx'] == 1:
                        m = re.search(r'\bget\(\s*"([^"]+)"\s*,\s*$', src[max(0, start-120):start-len(q)])
                        if m: owner = f'call:get({m.group(1)})#1'
                else:
                    chain = st[ri+1:] if root['kind'] == '(' else st[ri:]
                    base = root['anchor'] if root['kind'] != '(' else f'call:{root["fn"]}#{root["idx"]}'
                    if root['kind'] != '(' and chain and chain[0] is root: base = root['anchor']
                    # 最后一个字典键 + 其后的数组标记
                    lastkey = None; suffix = ''
                    for k, fr in enumerate(chain):
                        if fr['kind'] == '{' and fr['key'] is not None and (k < len(chain) - 1 or True):
                            if fr is f or k < len(chain) - 1:
                                lastkey = _norm(fr['key']); suffix = ''
                                continue
                        if fr['kind'] == '[':
                            parent = chain[k-1] if k > 0 else None
                            suffix += f'[{fr["idx"]}]' if parent is not None and parent['kind'] == '[' else '[]'
                    if f['kind'] == '[':
                        pass
                    owner = (base or '?') + ('.' + lastkey if lastkey else '') + suffix
            # ---- key ----
            path = [top] + [fr['label'] for fr in st if fr['label']]
            if f and f['kind'] == '{' and f['key']: path.append(f['key'])
            elif f and f['kind'] == '[': path.append(str(f['idx']))
            elif f and f['kind'] == '(': path += [f'{f["fn"]}()', str(f['idx'])]
            else:
                m = re.match(r'\s*(?:var\s+)?([\w.]+)\s*[+]?=\s*$', before)
                if m: path.append(m.group(1))
            out.append(('|'.join(path), owner, s, start))
            continue
        i += 1
    return out

if __name__ == '__main__':
    demo = '''const CARDS: Dictionary = {
\t"shy_a": {"card_name": "Tease her", "scene_text": ["one", "two"], "tags": ["SHY"]},
}
const DIALOGUE_HOOK: Array = [
\t[1, "b1", "LEFT@pasha", "hiwa", "Hullo!"],
]
const HELLO: Dictionary = {"SHY": {0: ["hi"]}}
func f():
\tlabel.text = "NEW GAME"
\tlines.append("Obedience capped at %d" % x)
\tif mode == "Web":
\t\tpass
\tvar d = {"name": "Mud"}
\treturn "done"
'''
    got = {(o, s) for _, o, s, _ in scan(demo)}
    lam = 'func g():\n\tb.connect(func():\n\t\tvar desc = "Bring her"\n\t\tshow(desc))\n'
    assert any(o == '=desc' and t == 'Bring her' for _, o, t, _ in scan(lam)), scan(lam)
    assert any(o == 'call:get(name)#1' and t == 'She' for _, o, t, _ in scan('func h():\n\tvar n = c.get("name", "She")\n')), 'get default'
    for want in [('CARDS.card_name', 'Tease her'), ('CARDS.scene_text[]', 'one'), ('CARDS.tags[]', 'SHY'),
                 ('DIALOGUE_HOOK[][4]', 'Hullo!'), ('DIALOGUE_HOOK[][1]', 'b1'), ('HELLO.#[]', 'hi'),
                 ('=text', 'NEW GAME'), ('call:append#0', 'Obedience capped at %d'), ('compare', 'Web'),
                 ('=d.name', 'Mud'), ('return', 'done')]:
        assert want in got, (want, sorted(got))
    print('owner self-check ok')
