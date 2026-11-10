# 把 translation/<v>/ 下改过的 .gd/.tscn 编译成 .gdc/.scn，并用 GDRE --pck-patch 打进原版 exe 的 PCK
# 用法: python -m src.patch -v 0.18 --exe game/0.18/xxx.exe --gdre tools/gdre/gdre_tools.x86_64 [--source source] --out dist/
# 产物: dist/<原 exe 名>（PCK 重新嵌入 exe；Godot 优先读内嵌 pck，外置同名 pck 不会覆盖它）
import argparse, os, re, subprocess, sys, shutil

def run(cmd):
    print('+', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    errs = [l for l in out.splitlines() if ('ERROR' in l or 'Parse Error' in l or 'Failed' in l) and 'fontconfig' not in l]
    return r.returncode, out, errs

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--version', required=True)
    ap.add_argument('--exe', required=True)
    ap.add_argument('--gdre', required=True)
    ap.add_argument('--source', default='source')
    ap.add_argument('--trans', default='translation')
    ap.add_argument('--bytecode', default='4.5.0')
    ap.add_argument('--out', default='dist')
    a = ap.parse_args(argv)
    troot = os.path.abspath(os.path.join(a.trans, a.version)); sroot = os.path.join(a.source, a.version)
    build = os.path.abspath('build_tmp'); shutil.rmtree(build, ignore_errors=True)
    gd, tscn = [], []
    for dp, _, fs in os.walk(troot):
        for fn in fs:
            p = os.path.join(dp, fn); rel = os.path.relpath(p, troot).replace(os.sep, '/')
            (gd if fn.endswith('.gd') else tscn if fn.endswith('.tscn') else []).append(rel)
    patches = []
    # .gd → .gdc（res://xxx.gdc，原版就是这个路径）
    # 按目录分批编译，避免不同目录同名文件在 --output 里互相覆盖
    by_dir = {}
    for r in gd: by_dir.setdefault(os.path.dirname(r), []).append(r)
    for d, rs in by_dir.items():
        od = os.path.join(build, 'gdc', d)
        code, out, errs = run([a.gdre, '--headless', f'--bytecode={a.bytecode}', f'--output={od}'] + [f'--compile={os.path.join(troot, r)}' for r in rs])
        if errs or code: print(out); raise SystemExit(f'GDScript 编译失败: {d}（多半是译文引号/转义问题）')
        for r in rs:
            gdc = os.path.join(od, os.path.basename(r)[:-3] + '.gdc')
            if not os.path.isfile(gdc): print(out); raise SystemExit(f'未生成 {gdc}')
            patches.append((gdc, f'res://{r[:-3]}.gdc'))
    # .tscn → .scn（目标路径取 source 里的 .tscn.remap 指向的 .godot/exported/...）
    remap_dir = os.path.join(build, 'remap')
    if tscn:  # recover 不保留 .tscn.remap，从原包里单独解出来
        run([a.gdre, '--headless', f'--extract={os.path.abspath(a.exe)}', f'--output={remap_dir}', '--include=res://**/*.tscn.remap'])
    for r in tscn:
        remap = open(os.path.join(remap_dir, r + '.remap'), encoding='utf-8').read()
        target = re.search(r'path="([^"]+)"', remap).group(1)
        od = os.path.join(build, 'scn', os.path.dirname(r))
        code, out, errs = run([a.gdre, '--headless', f'--txt-to-bin={os.path.join(troot, r)}', f'--output={od}'])
        scn = os.path.join(od, os.path.basename(r)[:-5] + '.scn')
        if errs or not os.path.isfile(scn): print(out); raise SystemExit(f'场景转换失败: {r}')
        patches.append((scn, target))
    os.makedirs(a.out, exist_ok=True)
    pck = os.path.abspath(os.path.join(a.out, os.path.basename(a.exe)))
    code, out, errs = run([a.gdre, '--headless', f'--pck-patch={os.path.abspath(a.exe)}', f'--embed={os.path.abspath(a.exe)}', f'--output={pck}'] + [f'--patch-file={s}={d}' for s, d in patches])
    if code or not os.path.isfile(pck): print(out); raise SystemExit('pck-patch 失败')
    print(f'patched {len(patches)} files ({len(gd)} gd, {len(tscn)} tscn) -> {pck}')
    if os.environ.get('GITHUB_OUTPUT'): open(os.environ['GITHUB_OUTPUT'], 'a').write(f'exe={pck}\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
