# Thirteenth Goddess 汉化工具链

Godot 4.5（bytecode 4.5.0）游戏，itch.io: https://00kereru.itch.io/thirteenth-goddess

## 流程

```
itch.io (免费，网页下载流程) ──download.py──▶ game/<v>/*.exe
          GDRE --recover ──▶ source/<v>/ (*.gd 反编译 / *.tscn / *.remap)
          extract.py   ──▶ pz_origin/<v>/**.gd.json / **.tscn.json   → 上传 PZ
PZ 导出   paratranz.py ──▶ trans_origin/<v>/
          replace.py   ──▶ translation/<v>/ (仅含有译文的 .gd/.tscn)
          patch.py     ──▶ dist/<原 exe 名>（.gd→.gdc，.tscn→.scn，GDRE --pck-patch --embed 回 exe）
```

| 文件 | 作用 |
|---|---|
| `src/download.py` | 抓 itch 页面 csrf → `/file/{upload_id}` 拿签名直链下载 Windows 包 |
| `src/extract.py` | 通用扫描：所有字符串字面量 → 黑名单过滤 → 按字典/数组路径生成 key |
| `src/audit.py` | 风险审计：原文是否同时出现在 `==`/`match`/`in [...]`/`get()`/字典键里 |
| `src/paratranz.py` | 触发 PZ 导出并解压 `utf8/<v>` |
| `src/replace.py` | 按 `<<POS:N>>` 流式替换（来自 FindingColor），严格校验原文，自动转义 `"` 和换行 |
| `src/patch.py` | 编译并打回 pck |

## 提取规则

**.tscn**：`text / tooltip_text / placeholder_text / title / dialog_text` 全部提取，不做内容过滤。

**.gd**：不看字符串长什么样，看它的**所属属性（owner）**，查 `rules/owners.txt` 决定：

| owner 例子 | 含义 |
|---|---|
| `CARDS.card_name` | const CARDS 里（任意层级）的 card_name 字段 |
| `CARDS.scene_text[]` | card 的 scene_text 数组元素 |
| `HELLO_LINES.#[]` | 数字键下的数组元素 |
| `DIALOGUE_HOOK[][4]` | 元组数组第 4 位（台词；0-3 位是序号/背景/站位/说话人） |
| `=text` | 函数里 `xxx.text = "..."` |
| `call:_tbtn_show_3#2` | 调用 `_tbtn_show_3(...)` 的第 2 个参数 |
| `call:get(name)#1` | `xxx.get("name", "She")` 的默认值 |
| `compare` / `match` / `in` / `doc` / `return` / `expr` | 比较、match 分支、in 判断、文档字符串、return、其它表达式 |

`rules/owners.txt` 每行 `+ owner`（提）/ `- owner`（不提）/ `? owner`（归属混杂，按内容兜底判断）；`~` 开头是正则规则，优先于精确行。
**规则表里没有的新 owner 一律不提**，写进 `unclassified.txt`，游戏更新后看这个文件补规则即可。

key：`顶层const/var/func名|字典键或数组下标路径`，代码里散落的串（赋值/参数/return）再加文本摘要，例如
`CARDS|shy_tease_hands|card_name`、`HELLO_LINES|BRATTY|1|0`、`_show_main_buttons|_tbtn_show_3()|0|CHAT`。重复 key 追加 `#n`。

## 已知限制 / 注意

- **不能翻**（逻辑比较用到）：`Web` `Home` `Default` `Music`（音频总线名）等，用 `audit.py` 查，PZ 上标注保留原文
- NameGenerator 名字池可翻：名字只在生成角色时写入存档，判断走 `c.id`；旧存档已生成的角色仍为英文名
- `[color=` 拼接类文本会被拆成多条，需结合上下文翻译
- GDRE 需要 glibc ≥ 2.34（Ubuntu 22.04+ / Debian 12+）；老系统用 docker 跑
- 外置同名 `.pck` 不会覆盖内嵌 pck，所以 patch.py 直接 `--embed` 回 exe
