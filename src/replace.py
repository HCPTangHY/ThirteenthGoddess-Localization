# 基于 POS 的流式替换（移植自 FindingColor-Localization/src/replace.py，去掉了对齐猜测，改为严格校验原文）
# 用法: python -m src.replace -v 0.18 [--src-root source] [--pz-root pz_origin] [--trans-root trans_origin] [--out-root translation]
# 只输出有译文变动的文件，build 时只 patch 这些文件
import argparse, json, os, re, sys

POS_RE = re.compile(r'(?:<<|&lt;&lt;)POS:(\d+)(?:>>|&gt;&gt;)')

def pos_of(ctx):
    m = POS_RE.findall(ctx or '')
    return int(m[-1]) - 1 if m else None

def escape(t: str) -> str:
    # 译文写回 GDScript/tscn 的 "..." 字符串：裸换行转 \n，未转义的 " 转 \"
    t = t.replace('\r\n', '\n').replace('\n', '\\n')
    return re.sub(r'(?<!\\)((?:\\\\)*)"', r'\1\\"', t)

def replace_file(src: str, base: dict, trans: list, rel: str):
    items, warn = [], 0
    for d in trans:
        k = d.get('key'); t = d.get('translation') or ''
        if not k or not t or (d.get('stage') not in (None, 1, 3, 5) ): continue
        b = base.get(k)
        if not b: print(f'[WARN] {rel}: key 不存在 {k}'); warn += 1; continue
        p, o = b
        if src[p:p + len(o)] != o:
            print(f'[WARN] {rel}: 原文不匹配 {k}'); warn += 1; continue
        items.append((p, o, escape(t)))
    items.sort()
    out, last = [], 0
    for p, o, t in items:
        if p < last: print(f'[WARN] {rel}: 位置重叠 @{p}'); warn += 1; continue
        out += [src[last:p], t]; last = p + len(o)
    out.append(src[last:])
    return ''.join(out), len(items), warn

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--version', required=True)
    ap.add_argument('--src-root', default='source')
    ap.add_argument('--pz-root', default='pz_origin')
    ap.add_argument('--trans-root', default='trans_origin')
    ap.add_argument('--out-root', default='translation')
    a = ap.parse_args(argv)
    troot = os.path.join(a.trans_root, a.version)
    files = applied = warns = 0
    for dp, _, fs in os.walk(troot):
        for fn in fs:
            if not fn.endswith('.json'): continue
            tj = os.path.join(dp, fn); rel = os.path.relpath(tj, troot)[:-5]
            sp = os.path.join(a.src_root, a.version, rel); bp = os.path.join(a.pz_root, a.version, rel + '.json')
            if not (os.path.isfile(sp) and os.path.isfile(bp)):
                print(f'[WARN] 缺源文件或基线: {rel}'); warns += 1; continue
            base = {e['key']: (pos_of(e['context']), e['original']) for e in json.load(open(bp, encoding='utf-8'))}
            src = open(sp, encoding='utf-8', newline='').read()
            res, n, w = replace_file(src, base, json.load(open(tj, encoding='utf-8')), rel)
            warns += w
            if n == 0 or res == src: continue
            op = os.path.join(a.out_root, a.version, rel)
            os.makedirs(os.path.dirname(op), exist_ok=True)
            open(op, 'w', encoding='utf-8', newline='').write(res)
            files += 1; applied += n
    print(f'[SUMMARY] files={files} applied={applied} warnings={warns}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
