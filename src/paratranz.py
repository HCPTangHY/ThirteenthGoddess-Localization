# ParaTranz 导出下载（同 CoTLocalization/build.py 的流程）：触发导出 → 下载 artifacts → 解压 utf8/<version> 到 trans_origin/<version>
# 用法: PARATRANZ_TOKEN=... python -m src.paratranz [-p PROJECT_ID] [-v VERSION]
import argparse, io, os, shutil, sys, time, zipfile
import requests

API = 'https://paratranz.cn/api'

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--project', default=os.environ.get('PARATRANZ_PROJECT', ''))
    ap.add_argument('-v', '--version', help='默认取导出包里唯一的版本目录')
    ap.add_argument('--out', default='trans_origin')
    ap.add_argument('--no-trigger', action='store_true')
    a = ap.parse_args(argv)
    h = {'Authorization': os.environ['PARATRANZ_TOKEN']}
    if not a.no_trigger:
        requests.post(f'{API}/projects/{a.project}/artifacts', headers=h, timeout=60)
        time.sleep(60)  # PZ 导出需要一点时间
    r = requests.get(f'{API}/projects/{a.project}/artifacts/download', headers=h, timeout=300)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = [n for n in z.namelist() if n.startswith('utf8/') and n.endswith('.json')]
    vers = sorted({n.split('/')[1] for n in names})
    ver = a.version or (vers[0] if len(vers) == 1 else None)
    if not ver: raise SystemExit(f'导出包里有多个版本目录 {vers}，请用 -v 指定')
    dest = os.path.join(a.out, ver); shutil.rmtree(dest, ignore_errors=True)
    for n in names:
        if n.split('/')[1] != ver: continue
        p = os.path.join(a.out, *n.split('/')[1:]); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(z.read(n))
    print(f'version={ver} files={sum(1 for n in names if n.split("/")[1] == ver)}')
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write(f'i18n_version={ver}\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
