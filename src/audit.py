import json, glob, re, collections, sys
SRC, PZ = (sys.argv[1:3] + ['recovered', 'pz_origin/0.18'])[:2] if len(sys.argv) > 1 else ('recovered', 'pz_origin/0.18')
src = '\n'.join(open(p, encoding='utf-8').read() for p in glob.glob(SRC + '/**/*.gd', recursive=True))
S = r'"((?:[^"\\\n]|\\.)*)"'
ctx = collections.defaultdict(set)
for name, pat in [
    ('compare', r'(?:==|!=)\s*' + S), ('compare', S + r'\s*(?:==|!=)'),
    ('lookup', r'\b(?:get|has|erase|get_flag|has_flag|set_flag|has_tag)\(\s*' + S),
    ('match', r'^\s*' + S + r'(?:\s*,\s*"[^"\n]*")*\s*:\s*$'),
    ('in_list', r'\bin\s*\[([^\]]*)\]'),
    ('dictkey', S + r'\s*:(?!=)'),
]:
    for m in re.finditer(pat, src, re.M):
        if name == 'in_list':
            for x in re.findall(S, m.group(1)): ctx[x].add(name)
        else: ctx[m.group(1)].add(name)
entries = [(f[len(PZ)+1:], e) for f in glob.glob(PZ + '/**/*.json', recursive=True) for e in json.load(open(f))]
risk = collections.defaultdict(list)
for f, e in entries:
    h = ctx.get(e['original'])
    if h: risk[tuple(sorted(h))].append((f, e['key'], e['original']))
print('total', len(entries), 'risky', sum(map(len, risk.values())))
for k, v in sorted(risk.items(), key=lambda x: -len(x[1])):
    print(k, len(v))
    for x in v[:8]: print('   ', x[0][:42], '|', x[1][:48], '|', x[2][:40])
