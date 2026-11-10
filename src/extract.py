# Thirteenth Goddess (Godot 4) 字符串提取
#  - .tscn: text / tooltip_text / placeholder_text / title / dialog_text 属性全部提取（非空即提，不做内容过滤）
#  - .gd:   按字符串的“所属属性”(owner，见 src/owner.py) 查 rules/owners.txt 决定是否提取
#           + 提取 / - 不提 / ? 归属混杂 → 按内容兜底；规则表里没有的新 owner 不提取，写入 unclassified 报告
# 用法: python -m src.extract <source_root/version> <out_root/version> [--rules rules/owners.txt] [--report unclassified.txt]
import argparse, collections, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from owner import scan

SKIP_DIRS = ('scenes/debug',)
SKIP_PARTS = ('sandbox',)
TSCN_PROPS = re.compile(r'^(text|tooltip_text|placeholder_text|title|dialog_text)\s*=\s*"')
STAGE = re.compile(r'^((LEFT|RIGHT|CENTER|MIDDLE)\w*@\w+,?)+$')

def load_rules(path):
    exact, regex = {}, []
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'): continue
        if line.startswith('~'): regex.append((line[1], re.compile(line[3:])))
        else: exact[line[2:]] = line[0]
    return exact, regex

def decide(owner, rules):
    exact, regex = rules
    for mark, rx in regex:
        if rx.search(owner): return mark
    return exact.get(owner)

def looks_like_text(s):
    """仅用于 ? 混杂归属的兜底：有两个以上字母，且像句子/短语而不是标识符"""
    if 'res://' in s or 'user://' in s or STAGE.match(s): return False
    bare = re.sub(r'\[/?[^\]]*(\]|$)|\{[^}]*\}|%[-+0-9.]*[a-z%]', ' ', s)
    if not re.search(r'[A-Za-z]{2,}', bare): return False
    if ' ' in s.strip(): return True
    if '_' in s or re.fullmatch(r'[a-z0-9]+|[A-Z0-9]+', s): return False   # snake_case / 纯小写 id / 全大写枚举
    if re.fullmatch(r'[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+', s): return False   # CamelCase 节点名/类名
    if re.fullmatch(r'#[0-9a-fA-F]{3,8}', s) or re.search(r'\.(png|jpe?g|webp|tscn|gd|tres|ogg|wav)$', s): return False
    return True

def sem(s, n=40):
    return re.sub(r'[^A-Za-z0-9]+', '_', s[:n]).strip('_')

def scan_tscn(src):
    out = []; node = '.'; pos = 0
    for line in src.split('\n'):
        m = re.match(r'\[node name="([^"]+)"(?:.*?parent="([^"]*)")?', line)
        if m: node = f'{m.group(2) or ""}/{m.group(1)}'
        m = TSCN_PROPS.match(line)
        if m:
            start = pos + m.end(); j = start
            while j < len(src) and src[j] != '"': j += 2 if src[j] == '\\' else 1
            if j > start: out.append((f'{node}|{m.group(1)}', src[start:j], start))
        pos += len(line) + 1
    return out

def scan_gd(src, rules, unclassified, rel):
    out = []
    for key, owner, s, start in scan(src):
        if not s.strip(): continue
        mark = decide(owner, rules)
        if mark is None:
            unclassified[owner].append((rel, s)); continue
        if mark == '-' or (mark == '?' and not looks_like_text(s)): continue
        if not re.search(r'[A-Za-z]', s): continue
        # 直接挂在代码上的串（赋值/参数/return，不在字典数组里）没有结构下标，用文本摘要做 key 尾巴
        if not re.search(r'[.\[]', owner) and not re.fullmatch(r'[A-Z_0-9]+', owner): key += '|' + sem(s)
        out.append((key, s, start))
    return out

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('source'); ap.add_argument('out')
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument('--rules', default=os.path.join(here, '..', 'rules', 'owners.txt'))
    ap.add_argument('--report', default='unclassified.txt')
    a = ap.parse_args(argv)
    rules = load_rules(a.rules)
    unclassified = collections.defaultdict(list)
    total = files = 0; stat = collections.Counter()
    for dp, ds, fs in os.walk(a.source):
        ds[:] = sorted(d for d in ds if not d.startswith('.'))
        rd = os.path.relpath(dp, a.source).replace(os.sep, '/')
        if rd.startswith(SKIP_DIRS) or any(x in rd.split('/') for x in SKIP_PARTS): continue
        for fn in sorted(fs):
            if not fn.endswith(('.gd', '.tscn')): continue
            p = os.path.join(dp, fn); rel = os.path.relpath(p, a.source).replace(os.sep, '/')
            src = open(p, encoding='utf-8', newline='').read()
            items = scan_gd(src, rules, unclassified, rel) if fn.endswith('.gd') else scan_tscn(src)
            if not items: continue
            used = set(); entries = []
            for k, s, st in items:
                assert src[st:st + len(s)] == s, (rel, k)
                key = k; i = 1
                while key in used: key = f'{k}#{i}'; i += 1
                used.add(key)
                entries.append({'key': key, 'original': s, 'translation': '', 'context': f'<<POS:{st + 1:08d}>>'})
            op = os.path.join(a.out, rel + '.json'); os.makedirs(os.path.dirname(op), exist_ok=True)
            json.dump(entries, open(op, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            total += len(entries); files += 1; stat['tscn' if fn.endswith('.tscn') else 'gd'] += len(entries)
    with open(a.report, 'w', encoding='utf-8') as f:
        for o, xs in sorted(unclassified.items(), key=lambda x: -len(x[1])):
            f.write(f'? {o}\t# {len(xs)}x  e.g. {xs[0][0]}: {xs[0][1][:60]!r}\n')
    print(f'files={files} entries={total} {dict(stat)} unclassified_owners={len(unclassified)} -> {a.report}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
