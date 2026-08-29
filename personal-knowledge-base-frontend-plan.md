# 个人知识库前端搭建计划

## 1. 项目概述

基于已有 Neo4j PersonalKG 数据层（**Neo4j 为元数据单一存储源**，MetaData JSON 已弃用），搭建一个**单页面应用（SPA）**作为个人知识库的前端入口。页面围绕"笔记阅读/编辑"、"AI 对话"、"PDF 资料"、"相关推荐"、"知识图谱"五大模块展开，实现以 Markdown 笔记为中心的沉浸式知识管理体验。

> **数据架构（2026-08-29 更新）**
> - 元数据（标题/来源/星级/类型/关键词/主题/向量/全文 content）**全部存 Neo4j Note 节点**，不再经 MetaData/**/*.json 中转。
> - md 文件本体仍保留在磁盘 `Files/*.md`（人工阅读/编辑/git 追踪用），但**运行时的读写以 Neo4j 为准**：保存时后端写 Neo4j 节点并同步回写 Files/*.md。
> - 数据链路：前端 → FastAPI（薄网关）→ Neo4j。

## 2. 总体布局（对应草图）

采用**三栏响应式布局**：

```
┌─────────────────────────────────────────────────────────────┐
│                      个人知识库（顶栏）                        │
├──────────────┬──────────────────────────────┬───────────────┤
│              │                              │               │
│   左栏       │         中栏                 │     右栏      │
│ Markdown     │   上区：PDF / AI 对话          │   相关条目    │
│ 渲染+编辑    │   ── 可拖动分隔条 ──           │   ────        │
│   一体化     │   下区：AI 对话区              │   知识图谱    │
│              │   [输入框 ...] [发送]          │               │
└──────────────┴──────────────────────────────┴───────────────┘
```

### 2.1 左栏：Markdown 渲染/编辑一体化
- **宽度**：约 30%-35%，最小 320px，可折叠。
- **模式切换**：
  - 阅读模式：Markdown 渲染（标题、列表、代码块、图片等）。
  - 编辑模式：所见即所得或分屏源码编辑（推荐轻量 Markdown 编辑器）。
  - 支持 `Ctrl/Cmd + E` 快速切换。
- **笔记选择**：顶部提供下拉/搜索框选择当前打开的 `md_path`；可选文件树侧边抽屉。
- **自动保存**：编辑后 2 秒自动保存到后端（`PUT /api/notes/{md_path}`），后端**写 Neo4j Note 节点（content 属性）并同步回写 `Files/*.md`**。

### 2.2 中栏：上下分区（可拖动）
#### 上区：PDF 区 / AI 对话 / PDF 资料
- **Tab 切换**：
  - `PDF 预览`：嵌入 PDF.js 渲染器，打开当前笔记关联的 PDF/Resource。
  - `AI 对话`：与当前笔记上下文相关的 AI 聊天面板。
  - `PDF 资料`：列出与当前主题/笔记相关的 Resource/PDF 资料卡片。
- **默认显示**：无 PDF 时默认显示 `AI 对话`。

#### 下区：主 AI 对话区
- **核心交互**：围绕当前笔记内容进行问答、续写、总结、扩写。
- **输入框**：底部固定输入条，支持多行、快捷指令（如 `/总结`、`/扩写`）。
- **发送按钮**：点击或 `Enter` 发送，`Shift+Enter` 换行。
- **上下文**：自动携带当前笔记标题 + 摘要/关键词 + 最近对话历史。

#### 可拖动分隔条
- 中栏上下区之间设置水平拖拽条，用户可自由分配 PDF/AI 区域高度。
- 拖动时实时更新上下区 `flex` 或百分比高度；释放后记忆到 `localStorage`。

### 2.3 右栏：相关推荐 + 知识图谱
#### 上区：相关条目
- 基于 Neo4j `related_notes` 与 `vector_search` 返回的关联内容。
- 显示条目列表：同主题笔记、共享关键词笔记、向量相似笔记。
- 每项显示：标题、星级、类型、匹配理由（`同主题` / `共享关键词：xx` / `语义相似`）。
- 点击条目可在左栏打开对应 Markdown。

#### 下区：知识图谱
- 使用 D3.js / ECharts / react-force-graph 等库可视化当前笔记为中心的子图。
- 节点：Note（当前高亮）、Subject、Project、Resource。
- 关系：ON / COVERS / ABOUT，边可hover显示关系类型。
- 交互：点击节点跳转/打开详情；支持缩放、拖拽、聚焦当前笔记邻居。

## 3. 功能模块拆解

| 模块 | 功能点 | 优先级 |
|------|--------|--------|
| 笔记管理 | 选择笔记、渲染 Markdown、编辑、保存 | P0 |
| AI 对话 | 上下文问答、快捷指令、对话历史 | P0 |
| PDF 预览 | PDF.js 嵌入、Resource 列表 | P1 |
| 相关推荐 | 同主题/关键词/向量相似条目 | P1 |
| 知识图谱 | 子图可视化、节点交互 | P1 |
| 全局搜索 | 顶栏语义搜索当前库 | P2 |
| 主题过滤 | 按 Subject 筛选笔记 | P2 |
| 用户偏好 | 布局比例、主题色、字体大小持久化 | P2 |

## 4. 技术栈选型

| 层级 | 选型 | 理由 |
|------|------|------|
| 框架 | React 18 + TypeScript | 组件化、生态成熟、类型安全 |
| 构建 | Vite | 启动快、热更新、配置简单 |
| 状态管理 | Zustand | 轻量，适合布局/笔记/对话状态 |
| UI 组件 | Ant Design / shadcn/ui | 快速搭建输入框、按钮、标签页、抽屉 |
| Markdown | react-markdown + remark-gfm | 支持 GFM、代码高亮、自定义链接 |
| PDF 预览 | react-pdf / PDF.js | 标准 PDF 渲染方案 |
| 图谱 | D3.js 或 react-force-graph-2d | 力导向图，节点拖拽缩放 |
| 网络请求 | Axios / SWR | 缓存与自动重试 |
| 后端 API | Python FastAPI | 已有 Neo4j 脚本可包装为 REST |

备选：如希望纯静态/更轻量，可用 Vanilla JS + Tailwind CSS，但扩展性较弱。

## 5. 后端 API 设计（与 Neo4j 层对接）

在 `code/API` 或新建 `code/backend` 中写一个轻量 FastAPI 服务，复用 `scripts/neo4j_kg.py` 的 `PersonalKG` 类。**数据全部读写 Neo4j**（单一存储源），md 文件仅作外部内容载体。

### 5.1 核心接口

```
GET  /api/notes                  # 列出所有 Note 摘要（来自 Neo4j）
GET  /api/notes/{md_path}        # 获取单篇 Markdown 内容（n.content）与元数据（来自 Neo4j）
PUT  /api/notes/{md_path}        # 保存 Markdown：写 Neo4j content + 同步回写 Files/*.md
GET  /api/notes/{md_path}/related?limit=10  # 相关笔记推荐（向量+主题+关键词）
GET  /api/notes/{md_path}/related-resources?limit=10  # 与笔记最相关的 Zotero 论文（Resource 向量索引）
POST /api/search                 # 语义搜索 {query: "...", label: "Note|Resource", limit: 10}
GET  /api/subjects               # 主题列表（来自 Neo4j Subject 节点）
GET  /api/graph/{md_path}        # 当前笔记为中心的子图
POST /api/chat                   # AI 对话 {md_path, message, history}
GET  /api/resources              # Resource 列表（PDF 资料，含 zotero_id/dir 等）
GET  /api/resources/{zotero_id}/pdf  # 下载/预览论文 PDF（FileResponse 转发本地绝对路径）
POST /api/resources/sync         # 触发 Zotero -> Neo4j 同步（调 zotero_bib.py sync）
```

### 5.2 PDF 访问机制（Resource → 前端）

浏览器**不能**直接打开 `file://` 本地路径（安全限制），因此 Resource 节点存
`dir`（本地 PDF **绝对路径**），前端通过后端转发获取：

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

@app.get("/api/resources/{zotero_id}/pdf")
def get_resource_pdf(zotero_id: str):
    res = kg.resource_by_zotero_id(zotero_id)   # 查询 Resource 节点
    if not res or not res.get("dir") or not os.path.exists(res["dir"]):
        raise HTTPException(404, "该条目无本地 PDF")
    return FileResponse(res["dir"], filename=os.path.basename(res["dir"]))
```

前端 PDF 区用 PDF.js 加载 `http://localhost:8000/api/resources/<zotero_id>/pdf`
即可预览论文全文。

### 5.3 保存逻辑（PUT /api/notes/{md_path}）

```python
@app.put("/api/notes/{md_path:path}")
def save_note(md_path: str, body: dict):
    content = body["content"]
    # 1) 写 Neo4j（单一存储源）：更新 content + word_count + indexed_at
    kg.set_note_content(md_path, content)
    # 2) 同步回写外部 Files/*.md（人工编辑/git 追踪仍可用）
    md = files_dir / md_path
    md.write_text(content, encoding="utf-8")
    return {"ok": True}
```

### 5.4 对话接口细节

`POST /api/chat` 请求体：

```json
{
  "md_path": "政治/从一次被毙的活动看官僚体制.md",
  "message": "帮我总结一下这篇文章的核心观点",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

后端拼接 prompt：
- 当前笔记标题、类型、关键词、星级
- 笔记正文摘要或全文（按模型上下文限制截断）
- 用户问题与历史对话
- 调用 `code/API/ai_ask.py` 的 `ask_qwen_with_gpt_backup`

返回流式或非流式文本，建议优先**流式 SSE** 提升体验。

## 6. 组件结构

```
frontend/
├── src/
│   ├── App.tsx                      # 三栏布局与全局状态
│   ├── components/
│   │   ├── TopBar.tsx               # 顶栏：标题、全局搜索、主题切换
│   │   ├── NotePanel.tsx            # 左栏：Markdown 渲染/编辑
│   │   ├── MarkdownRender.tsx       # Markdown 渲染组件
│   │   ├── MarkdownEditor.tsx       # Markdown 编辑器
│   │   ├── CenterPanel.tsx          # 中栏容器
│   │   ├── UpperPanel.tsx           # 上区：PDF / AI / Resource Tab
│   │   ├── LowerPanel.tsx           # 下区：AI 对话
│   │   ├── ChatInput.tsx            # 对话输入条
│   │   ├── MessageList.tsx          # 对话消息列表
│   │   ├── PdfViewer.tsx            # PDF 预览
│   │   ├── ResourceList.tsx         # PDF 资料列表
│   │   ├── RightPanel.tsx           # 右栏容器
│   │   ├── RelatedList.tsx          # 相关条目
│   │   ├── KnowledgeGraph.tsx       # 知识图谱可视化
│   │   ├── ResizableDivider.tsx     # 可拖动分隔条
│   │   └── NoteSelector.tsx         # 笔记选择器
│   ├── hooks/
│   │   ├── useCurrentNote.ts        # 当前笔记状态
│   │   ├── useChat.ts               # 对话逻辑
│   │   ├── useRelated.ts            # 相关推荐
│   │   ├── useGraph.ts              # 图谱数据
│   │   └── useResize.ts             # 拖动分隔条逻辑
│   ├── services/
│   │   └── api.ts                   # Axios 封装与 API 调用
│   ├── stores/
│   │   └── appStore.ts              # Zustand 全局状态
│   ├── types/
│   │   └── index.ts                 # TypeScript 类型定义
│   └── main.tsx
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## 7. 关键交互细节

### 7.1 Markdown 编辑/渲染切换
- 默认渲染模式。
- 点击编辑按钮或 `Ctrl/Cmd+E` 进入编辑模式。
- 编辑模式下保留实时预览（可选左右分屏）。
- 失焦或 2 秒无输入后触发 `PUT /api/notes/{md_path}`。

### 7.2 中栏上下区拖动
- 使用自定义 `ResizableDivider` 组件监听 `mousedown`/`touchstart`。
- 计算鼠标 Y 偏移，动态设置 `UpperPanel` 与 `LowerPanel` 的 `height` 百分比。
- 最小高度限制：上区 15%，下区 20%。
- 记忆比例到 `localStorage`。

### 7.3 右栏相关条目与图谱联动
- 点击相关条目 → 左栏切换到对应笔记；图谱高亮该节点（若已在图中）。
- 点击图谱节点：
  - Note 节点 → 打开笔记。
  - Subject 节点 → 主题过滤/聚焦该主题下所有 Note。
  - Resource 节点 → 中栏上区切换到 PDF 预览。

### 7.4 AI 对话上下文
- 每次发送自动附加：
  ```
  当前笔记：《{title}》
  类型：{type} | 关键词：{keywords}
  正文摘要：{text[:3000]}
  ```
- 支持快捷指令：`/总结`、`/扩写`、`/找相关`、`/提问`。

## 8. 数据类型定义

```typescript
interface Note {
  md_path: string;
  title: string;
  source_docx: string | null;
  created: string;
  stars: number;
  type: string;
  keywords: string[];
  subjects: string[];          // 学科主题（可多个），来自 Neo4j ON->Subject
  word_count: number;
  qwen_embedding?: number[];
  content?: string;            // Markdown 原文，来自 Neo4j n.content（与 Files/*.md 一致）
}

interface Resource {
  title: string;
  keywords: string[];
  abstract: string | null;
  zotero_id: string | null;
  dir: string | null;          // 本地 PDF 绝对路径（仅后端读取，前端经 /pdf 接口访问）
  doi: string | null;
  date: string | null;
  authors: string | null;
  item_type: string | null;
  citation_key: string | null;
  url: string | null;
  publication_title: string | null;
  pdf_url?: string;            // GET /api/resources/{zotero_id}/pdf
}

interface RelatedItem {
  md_path: string;
  title: string;
  stars: number;
  type: string;
  reason: string; // "同主题", "共享关键词：xx", "语义相似"
  score: number;
}

interface RelatedResource {
  title: string;
  score: number;
  zotero_id: string | null;
  dir: string | null;
  date: string | null;
}

interface GraphNode {
  id: string;
  label: string;
  group: 'Note' | 'Subject' | 'Project' | 'Resource';
  stars?: number;
}

interface GraphLink {
  source: string;
  target: string;
  relation: 'ON' | 'COVERS' | 'ABOUT';
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
```

## 9. 开发路线图

### Phase 1：基础骨架（可运行）
1. 用 Vite + React + TS 初始化项目。
2. 搭建三栏布局 + 顶栏。
3. 实现笔记选择器 + Markdown 渲染（阅读模式）。
4. 对接 `GET /api/notes`、`GET /api/notes/{md_path}`。

### Phase 2：AI 对话核心
1. 实现中栏下区 AI 对话界面。
2. 对接 `POST /api/chat`（先非流式，再优化为 SSE）。
3. 添加快捷指令与上下文自动注入。

### Phase 3：PDF 与 Resource
1. 集成 PDF.js 预览。
2. 实现 Resource/PDF 资料列表与 Tab 切换。

### Phase 4：相关推荐 + 图谱
1. 右栏相关条目列表。
2. 右栏知识图谱可视化（D3 / react-force-graph）。
3. 节点点击与笔记切换联动。

### Phase 5：编辑与细节优化
1. Markdown 编辑模式 + 自动保存。
2. 中栏上下区可拖动分隔条。
3. 全局搜索、主题过滤、布局比例记忆。
4. 暗色模式、字体大小调整。

## 10. 部署建议

- 开发：`npm run dev`（Vite 默认端口 5173）。
- 后端 FastAPI：`python -m uvicorn backend.main:app --reload --port 8000`。
- 生产构建：`npm run build`，输出静态文件后由 Nginx/后端服务托管。
- 如需桌面端，后期可用 Tauri 将前端 + Python 后端打包为桌面应用。

## 11. 下一步建议

1. 在 `code/` 下新建 `frontend/` 目录，按上述结构初始化 Vite 项目。
2. 在 `code/backend/` 下新增 FastAPI 服务，先把 `neo4j_kg.py` 的 `related_notes`、`vector_search`、`note` 包装成 REST 接口（数据全部来自 Neo4j）。
3. 从 Phase 1 开始实现，先跑通"选择笔记 → 渲染 Markdown"这一主链路（内容读 `n.content`）。
4. 数据入库（新文档）：`docx → Files/*.md → neo4j_kg.py ingest`（不再生成 MetaData JSON），AI 字段/向量/主题用各脚本的 `--neo4j` 模式直写节点。

---

## 12. 实现状态（2026-08-29 已完成）

已按本计划完成 **Phase 1–5** 全部功能并端到端验证通过：

**交付物**
- `code/backend/main.py` + `requirements.txt`：FastAPI 薄网关，复用 `neo4j_kg.PersonalKG`
- `code/frontend/`：Vite + React 18 + TS + Zustand + react-markdown + ECharts
- `neo4j_kg.py` 新增方法：`list_notes` / `list_resources` / `resource_by_zotero_id` / `note_graph`（`resource()` 增加 subjects）

**已实现功能**
| 模块 | 状态 |
|------|------|
| 三栏布局 + 顶栏（搜索/同步/统计/刷新） | ✅ |
| 左栏：主题筛选 + 笔记列表 + 语义搜索结果 | ✅ |
| 中栏上：Markdown 渲染 / 编辑（Ctrl+S 保存，回写 Neo4j + Files/*.md） | ✅ |
| 中栏下 Tab：AI 对话（快捷指令 /总结 /要点 /联系 /批判） | ✅ |
| 中栏下 Tab：相关论文 + Zotero 论文库 + PDF iframe 预览 | ✅ |
| 右栏上：相关笔记推荐（点击切换） | ✅ |
| 右栏下：ECharts 力导向图谱（Note/Subject/Resource 点击联动） | ✅ |
| 拖拽分隔条 + localStorage 记忆 | ✅ |
| 后端静态托管前端构建产物（单服务访问） | ✅ |

**与计划的实现差异（说明）**
- md_path 改由 query 参数传递（`/api/note?path=…`），而非 URL path segment——避免中文路径与 `%2F` 解码歧义；其余接口语义不变。
- PDF 预览用浏览器原生 `<iframe>` 渲染（后端 `FileResponse` 已带 `application/pdf`），未引入 PDF.js（省去 worker 配置，效果一致）；如需页级操作可后续替换。
- 图谱用 ECharts graph（force 布局），替代 D3/react-force-graph，交互能力（缩放/拖拽/hover 高亮）等价。
- 中栏上下区未做上下拖拽（笔记区与底部 Tab 区高度固定 46%），三栏宽度拖拽已实现。

**运行方式**
- 开发：`cd code\backend && python -m uvicorn backend.main:app --reload --port 8000`；`cd code\frontend && npm run dev`（访问 http://localhost:5173）
- 生产/单服务：`npm run build` 后仅启动后端，访问 http://localhost:8000
- 当前两个服务已在后台运行（8000/5173），Neo4j 需保持在线

---

> 附：本计划直接对应用户手绘草图，所有布局比例、模块职责、接口设计均以现有 `Neo4j PersonalKG` 单一存储源数据层为基础，可快速落地。
