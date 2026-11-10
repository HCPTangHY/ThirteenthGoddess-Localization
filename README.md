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

## 提取规则（extract.py）

扫描 `.gd` 全部字符串字面量，排除：
- 字典键、`&"..."` / `^"..."`（StringName/NodePath）、`res://` 路径、文档字符串
- 调用参数：`print*`/`push_*`/`BugLogger.log`/`get_node`/`get`/`has`/`add_theme_*`/`set_meta` 等（见 `SKIP_CALL`）
- 标识符形态：无空格且是 snake_case / CamelCase / 含 `@` 数字 等；演出指令 `LEFT@pasha,RIGHT@iris`
- 字典字段黑名单：`anchor` `sprite` `bus` `anim`
- 目录：`scenes/debug`、`scenes/combat/sandbox`

`.tscn` 只锚定 `text / tooltip_text / placeholder_text / title / dialog_text = "..."`。

key 规则：`顶层const/var/func名|字典键或数组下标路径`，例如
- `CARDS|shy_tease_hands|card_name`
- `HELLO_LINES|BRATTY|1|0`（性格 → 好感档位 → 第 0 句）
- 非字典/数组位置的散串：`函数名|赋值目标|文本摘要`
- tscn：`父节点/节点名|属性`

重复 key 追加 `#n`。

## 已知限制 / 注意

- **不能翻**（逻辑比较用到）：`Web` `Home` `Default` `Music`（音频总线名）等，用 `audit.py` 查，PZ 上标注保留原文
- NameGenerator 名字池可翻：名字只在生成角色时写入存档，判断走 `c.id`；旧存档已生成的角色仍为英文名
- `[color=` 拼接类文本会被拆成多条，需结合上下文翻译
- GDRE 需要 glibc ≥ 2.34（Ubuntu 22.04+ / Debian 12+）；老系统用 docker 跑
- 外置同名 `.pck` 不会覆盖内嵌 pck，所以 patch.py 直接 `--embed` 回 exe
