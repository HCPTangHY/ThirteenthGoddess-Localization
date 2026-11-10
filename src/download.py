# 从 itch.io 下载 Thirteenth Goddess Windows 包（免费游戏，走网页下载流程，不需要 API key）
# 用法: python -m src.download [--check-only] [--out DIR]
# 输出: game/<version>/<exe>，并打印 version=...（GITHUB_OUTPUT 存在时写入）
import argparse, os, re, sys, zipfile, shutil, json
import requests

GAME_URL = "https://00kereru.itch.io/thirteenth-goddess"
PLATFORM_HINT = "forWindows"

def list_uploads(s: requests.Session):
    html = s.get(GAME_URL, timeout=30).text
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    # itch 每次渲染的属性顺序是随机的（data-upload_id/href、title/class 会互换），只按 upload 块切分再分别取
    ups = []
    for blk in html.split('<div class="upload">')[1:]:
        i = re.search(r'data-upload_id="(\d+)"', blk); n = re.search(r'<strong[^>]*\btitle="([^"]+)"', blk)
        if i and n: ups.append((i.group(1), n.group(1)))
    return csrf, [(int(i), n) for i, n in ups]

def pick(uploads):
    for uid, name in uploads:
        if PLATFORM_HINT.lower() in name.lower():
            m = re.search(r'_(\d+(?:\.\d+)+[a-z]?)_', name)
            return uid, name, (m.group(1) if m else str(uid))
    raise SystemExit(f"未找到 Windows 包: {uploads}")

def direct_url(s, csrf, uid):
    r = s.post(f"{GAME_URL}/file/{uid}", params={"source": "view_game", "as_props": 1, "after_download_lightbox": "true"},
               data={"csrf_token": csrf}, timeout=30)
    r.raise_for_status()
    return r.json()["url"]

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="game")
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args(argv)
    s = requests.Session()  # 别伪装 UA：itch 对裸 "Mozilla/5.0" 返回的页面不带下载列表
    csrf, uploads = list_uploads(s)
    uid, name, version = pick(uploads)
    print(f"upload_id={uid} file={name} version={version}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f: f.write(f"version={version}\nupload_id={uid}\n")
    if a.check_only: return 0
    dest = os.path.join(a.out, version); os.makedirs(dest, exist_ok=True)
    zpath = os.path.join(dest, name)
    with s.get(direct_url(s, csrf, uid), stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f: shutil.copyfileobj(r.raw, f, 1 << 20)
    with zipfile.ZipFile(zpath) as z: z.extractall(dest)
    os.remove(zpath)
    exe = next(p for p in os.listdir(dest) if p.endswith(".exe"))
    print(f"exe={os.path.join(dest, exe)}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f: f.write(f"exe={os.path.join(dest, exe)}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
