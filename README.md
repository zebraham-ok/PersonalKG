# 个人知识库系统（Personal Knowledge Base）

本地运行的个人知识库：以 **Neo4j 图数据库**为主存储，通过 FastAPI 薄网关 + 浏览器三栏界面，实现笔记浏览/编辑、语义搜索、AI 对话、文献（Zotero 论文）管理与 PDF 预览、知识图谱可视化。

## 目录结构

```
code/
├── backend/                  # FastAPI 后端网关
│   ├── main.py               # 全部 API 接口（约 15 个）
│   ├── data/subjects.json    # 主题分类树（AI 主题分配用）
│   └── requirements.txt      # 后端依赖
├── frontend/                 # 前端（Vite + React 18 + TS + Zustand + ECharts）
│   ├── src/                  # 组件 / store / 样式
│   └── package.json
├── docx2md/                  # Word → Markdown 批量转换工具
├── scripts/                  # 工具脚本（如 dedup_notes.py 去重）
├── API/                      # AI 调用封装（ai_ask 等，含 qwen/GPT 兜底）
├── kb_ctl.py                 # 服务管理脚本（核心逻辑）
├── kb.bat                    # 一键管理入口（推荐使用）
├── kb_launcher.cs            # 桌面启动器源码（C#，编译为单文件 exe）
├── dist/                     # C# 编译产物（知识库.exe，构建产物不入库）
├── .env                      # 本地配置（Neo4j 凭据 LOCAL_NEO4J_* 等，不入库）
├── .gitignore
└── personal-knowledge-base-frontend-plan.md   # 前端实现计划文档
```

数据存储位置：

- **Neo4j**：笔记（Note）、主题（Subject）、文献（Resource）节点及关系、语义向量，是唯一事实源
- **Zotero 附件**：文献 PDF 文件存放在 Zotero data 目录，后端按需读取
- **Files/**：Markdown 源文件（可选导出/人工阅读载体）

## 系统原理

```
docx 档案（按主题分目录）
    │  docx2md 转换 + AI 抽取（星级/关键词/类型/主题）+ 向量化
    ▼
Neo4j 图数据库（Note / Subject / Resource 节点，ON / ABOUT / VEC 关系）
    ▲                          │
    │  查询/写入（Bolt）       │  FastAPI 薄网关（backend/main.py）
    │                          ▼
code/.env ──凭据──►  前端浏览器界面（http://localhost:5173 或 :8000）
```

要点：

- **单一存储源**：Neo4j 保存笔记全文、属性与 512 维向量（qwen-embedding）；Files/*.md 仅为可选的导出载体
- **薄网关**：浏览器不能直连 Bolt 协议，所有读写经 FastAPI 一层包装；AI 对话复用 `API/ai_ask.py`（带 GPT 兜底）
- **语义检索**：笔记/文献的向量相似度检索（VEC 关系/余弦相似度），支撑搜索、相关推荐、图谱
- **文献同步**：`POST /api/resources/sync` 调用 zotero_bib skill 把 Zotero 条目（含 PDF 路径）同步进 Neo4j

## 启动 / 停止

> 前提：本机已安装 Python（含 fastapi/uvicorn/neo4j 依赖）、Node.js 20+、Neo4j（Community 版，凭据写在 `code/.env`）。

### 桌面一键启动（推荐）

双击桌面 `知识库.exe`（由 `kb_launcher.cs` 编译）：程序自动完成 Neo4j → 后端 → 浏览器的全流程启动，关闭窗口（或 Ctrl+C）即停止全部服务。

```
双击 知识库.exe
   │  1. 检查 Neo4j(7687)：未在线则自动启动（等待就绪，约 20s）
   │  2. 清理后端(8000)旧进程
   │  3. 启动后端（生产模式，托管 frontend/dist）
   ▼  4. 打开浏览器 http://localhost:8000
保持黑窗口运行；关窗 / Ctrl+C = 停止全部服务（含 Neo4j，Job Object 保证）
```

要点：

- 后端与 Neo4j 都纳入 **Job Object（KILL_ON_JOB_CLOSE）**，无论关窗、Ctrl+C 还是强杀，服务都自动停止，不留残留进程
- Neo4j 已在运行时自动复用，不会重复启动
- 若修改路径/端口：编辑 `kb_launcher.cs` 顶部常量后重新编译
  ```bat
  "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /codepage:65001 /target:exe /out:dist\知识库.exe kb_launcher.cs
  ```
- 后端日志 `code/_kb_launcher_backend.log`，Neo4j 日志 `code/_kb_launcher_neo4j.log`（均不入库）

### 命令行管理（开发模式）

在 `code/` 目录下使用 `kb.bat`（或 `python -X utf8 kb_ctl.py`）：

| 命令 | 作用 |
|------|------|
| `kb.bat start` | 检查 Neo4j → 启动后端(8000) + 前端(5173)，已运行的端口自动跳过 |
| `kb.bat stop` | 停止前后端进程 |
| `kb.bat restart` | 先停后启 |
| `kb.bat status` | 查看 Neo4j / 后端 / 前端在线状态与健康检查 |
| `kb.bat prod` | 生产模式：仅启动后端(8000)，托管前端构建产物（需先 `npm run build`） |
| `kb.bat open` | 用默认浏览器打开页面 |

启动成功后访问：

- **开发模式**：http://localhost:5173 （Vite 热更新，`/api` 自动代理到 8000）
- **生产模式**：http://localhost:8000 （单服务）

日志：后端 `code/_backend.log`，前端 `code/frontend/_frontend.log`。

### 手动启动

```bat
:: 1. 启动 Neo4j（Desktop 打开数据库，或命令行 neo4j console）

:: 2. 后端（端口 8000）
cd /d e:\思考\社会思考\code
python -m uvicorn backend.main:app --reload --port 8000

:: 3. 前端（开发模式，端口 5173）
cd /d e:\思考\社会思考\code\frontend
npm run dev
```

### 生产模式（可选）

```bat
cd /d e:\思考\社会思考\code\frontend
npm run build        :: 生成 dist/
:: 之后仅需启动后端，访问 http://localhost:8000 即为完整应用
```

## 基本功能

三栏布局 + 顶栏，宽度可拖拽调节（位置记忆在浏览器 localStorage）：

- **顶栏**：笔记/论文双模式语义搜索；同步 Zotero 文献；刷新；库统计
- **左栏（笔记）**：主题 chips 筛选；笔记列表（星级/类型）；搜索结果（笔记点击打开、文献点击预览 PDF）；支持"主题/相似度/近期编辑"三种视图切换
- **中栏上（笔记区）**：Markdown 渲染 / 编辑，`Ctrl+S` 保存（回写 Neo4j，若路径在 Files/ 内同步写回 md 文件）；双击标题可重命名
- **中栏下（Tab 区）**：
  - **AI 对话**：基于当前笔记上下文提问，支持快捷指令 `/总结` `/要点` `/联系` `/批判`
  - **文献**：相关论文推荐 + Zotero 论文库 + PDF 内嵌预览（iframe）
- **右栏上**：相关笔记推荐（点击切换笔记）
- **右栏下**：知识图谱（ECharts 力导向图，Note/Subject/Resource 三类节点）——点击笔记跳转、点击主题过滤、点击文献预览 PDF

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notes` | 笔记列表（可按 subject/limit 过滤） |
| GET / PUT | `/api/note?path=` | 获取 / 保存单篇笔记（md_path 走 query 参数） |
| GET | `/api/related?path=` | 语义相关笔记推荐 |
| GET | `/api/related-resources?path=` | 与当前笔记相关的文献 |
| POST | `/api/search` | 笔记 / 文献双模式语义搜索 |
| GET | `/api/subjects` | 主题列表 |
| GET | `/api/graph?path=` | 以笔记为中心的子图（图谱可视化） |
| GET | `/api/resources` | 论文库列表 |
| GET | `/api/resources/{zid}/pdf` | 文献 PDF（内嵌渲染） |
| POST | `/api/resources/sync` | 触发 Zotero → Neo4j 同步 |
| POST | `/api/chat` | AI 对话（带当前笔记上下文） |
| GET | `/api/stats` | 库统计 |
| GET | `/api/health` | 健康检查 |

## 常见问题

- **点文献触发下载而非预览**：后端已配置 `Content-Disposition: inline`，正常应在页面内渲染；若提示"无本地 PDF"，说明该条目的 PDF 文件路径在当前机器上不存在（Zotero 附件存储在其他位置），需同步 PDF 或重映射 `dir` 路径。
- **中文路径/参数**：md_path 一律走 query 参数传递，避免 URL path 中文与 `%2F` 解码歧义。
- **Neo4j 离线**：桌面 `知识库.exe` 会自动启动 Neo4j；`kb.bat start` 仅检查 Neo4j（7687），未在线会提示先启动数据库。
- **提交代码前**：`.env` 与 `API/secrets.csv`（含 API 密钥）已被 `.gitignore` 排除，切勿强制提交（`git add -f`）。
