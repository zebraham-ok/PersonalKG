# docx2md —— Word 转 Markdown 批量转换工具

将 Word（`.docx` / `.doc`）高效批量转换为 Markdown，**尽量保留原有文件格式**。

## 安装

```bash
pip install -r requirements.txt
```

- 核心依赖仅 `python-docx`。
- 如需转换旧版 `.doc`（需 Windows + 已安装 Microsoft Word）：`pip install pywin32`。

## 快速开始

```bash
# 单个文件（默认输出到当前目录下的 Files/）
python docx2md.py 我的笔记.docx

# 转换整个目录（默认递归所有子目录，批量多线程）
python docx2md.py "e:\思考\社会思考\政治\"

# 多个文件，指定输出目录并覆盖旧结果
python docx2md.py a.docx b.docx --out md/ --overwrite

# 输出 YAML front matter（标题/作者/日期），便于笔记软件导入
python docx2md.py 论文目录/ --recursive --meta
```

## 常用选项

| 参数 | 说明 |
| --- | --- |
| `paths...` | 一个或多个 `.docx`/`.doc` 文件或目录 |
| `--out DIR` | 输出目录（默认当前目录下的 `Files/`，可用它指定任意目录；均保持源文件相对结构） |
| `--assets 子目录名` | 图片存放目录名，默认 `assets`，图片位于 `assets/<文档名>/` |
| `--jobs N` | 并发转换数，默认按 CPU 自动（4） |
| `--no-recursive` | 目录只扫描顶层，不递归子目录 |
| `--overwrite` | 覆盖已存在的 `.md`（默认跳过，避免误覆盖） |
| `--no-images` | 不提取图片 |
| `--meta` | 输出 YAML front matter（标题/作者/创建日期） |
| `--code-lang LANG` | 指定代码块语言标记（默认按内容自动识别 python/js/c/sql） |
| `--doc2docx` | 用 Word COM 把 `.doc` 先转为 `.docx` 再转换（Windows） |
| `--verbose` | 打印额外信息 |

## 格式保留对照

| Word 格式 | Markdown 输出 |
| --- | --- |
| 标题 1–6 / Title / Subtitle / outline 级别 | `#` ~ `######` |
| 加粗 / 斜体 / 加粗斜体 | `**text**` / `*text*` / `***text***` |
| 下划线 | `<u>text</u>` |
| 删除线 | `~~text~~` |
| 上标 / 下标 | `<sup>text</sup>` / `<sub>text</sub>` |
| 高亮 | `<mark>text</mark>` |
| 等宽字体（Consolas/Courier 等） | `` `code` `` |
| 有序 / 无序 / 多级列表 | `1. ` / `- ` + 4 空格缩进，按 Word 编号自动计数 |
| 表格 | GFM 表格，保留单元格内加粗等格式，简单合并单元格 |
| 图片 | 提取到 `assets/<文档名>/`，md 中 `![](相对路径)` 引用 |
| 超链接 | `[文本](url)`（书签为 `#anchor`） |
| 连续代码段落 / 代码样式 | 围栏代码块 ` ```lang ` |
| 引用样式段落 | `> 文本` |

## 已知限制

- 页眉页脚、批注、修订记录、文本框、SmartArt、脚注/尾注不提取（正文为主）。
- 复杂合并单元格、嵌套表格（表格中的表格）无法用 GFM 表示，尽量保留文本。
- `.doc` 旧格式需要 Word 环境（`--doc2docx`），建议先用 Word「另存为 .docx」。
- 公式（OMML 数学公式）当前按普通文本导出。
- 图片顺序与文字流保持一致，但尺寸信息（宽高）默认不保留。

## 输出示例

```
原文件:  政治/某讲座.docx            （当前目录为 e:\思考\社会思考）
输出:    Files/政治/某讲座.md          （默认输出目录，保持相对结构）
图片:    Files/政治/assets/某讲座/某讲座_img0001.png
```

## 二次开发

核心类 `Docx2Md` 在 `docx2md.py` 中，按「段落 → 块类型判定 → 行内渲染」流水线工作，
可通过继承或修改 `render_paragraph` / `render_inline` 定制输出风格。
