# -*- coding: utf-8 -*-
"""personal-knowledge-base 后端 —— FastAPI 薄网关。

复用 skills/md-index/scripts/neo4j_kg.py 的 PersonalKG（Neo4j 单一存储源）。

运行（在 code/ 目录下）：
    python -m uvicorn backend.main:app --reload --port 8000

前端开发用 Vite dev server（5173），vite.config.ts 已配置 /api 代理到本服务。
"""
import io
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

CODE_DIR = Path(__file__).resolve().parent.parent          # code/
FILES_DIR = CODE_DIR.parent / 'Files'                      # e:\思考\社会思考\Files
sys.path.insert(0, str(CODE_DIR))

# 定位 neo4j_kg.py（skill 脚本）；若 code/scripts 存在本地副本则优先
SCRIPTS_DIR = CODE_DIR / 'scripts'
if not (SCRIPTS_DIR / 'neo4j_kg.py').is_file():
    SCRIPTS_DIR = Path.home() / '.codebuddy' / 'skills' / 'md-index' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from neo4j_kg import PersonalKG, norm_path, resolve_md_arg  # noqa: E402
from API import secret_manager                              # noqa: E402

ZOTERO_SCRIPT = Path.home() / '.codebuddy' / 'skills' / 'zotero-bib' / 'scripts' / 'zotero_bib.py'
if not ZOTERO_SCRIPT.is_file():
    ZOTERO_SCRIPT = CODE_DIR / 'scripts' / 'zotero_bib.py'

app = FastAPI(title='Personal Knowledge Base API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['*'],
    allow_headers=['*'],
)


# ---------------------------------------------------------------- Neo4j 连接
def _connect():
    secrets = secret_manager.read_secrets_from_env()
    return PersonalKG(
        uri=secrets.get('local_neo4j_url', 'bolt://localhost:7687'),
        user=secrets.get('local_neo4j_username', 'neo4j'),
        password=secrets.get('local_neo4j_password', ''),
        files_dir=str(FILES_DIR),
    )


try:
    kg = _connect()
    print('[后端] Neo4j 已连接')
except SystemExit as e:
    print(f'[后端] Neo4j 连接失败: {e}')
    kg = None


def _kg():
    if kg is None:
        raise HTTPException(503, 'Neo4j 未连接，请先启动本地 Neo4j')
    return kg


def _norm_md(md_path: str) -> str:
    """归一化 md_path（兼容相对/绝对路径）。

    不做目录白名单校验：Neo4j 中笔记除 Files/ 外，还包含工作区各主题目录
    （如 政治/、组织/ 等 docx 转换而来）。笔记是否存在由各接口查询兜底（404）。
    """
    return resolve_md_arg(md_path, str(FILES_DIR))


def _note_checked(md_path: str):
    n = _kg().note(md_path)
    if n is None:
        raise HTTPException(404, f'未找到笔记: {md_path}')
    return n


# ------------------------------------------------------------------- 请求体
class SaveBody(BaseModel):
    content: str
    title: Optional[str] = None


class SearchBody(BaseModel):
    query: str
    label: str = 'Note'          # Note | Resource
    limit: int = 10


class ChatBody(BaseModel):
    md_path: str = ''    # 当前笔记路径；未打开笔记（如纯 RAG / 自由提问）时为空
    message: str
    model: str = 'qwen-turbo'
    history: list = []           # [{"role": "user"|"assistant", "content": "..."}]
    use_note: bool = True        # 是否引入当前笔记内容
    use_pdf: bool = False        # 是否引入当前打开的 PDF 内容
    rag: bool = False            # 是否全库 RAG 检索（相似度召回知识片段）
    resource_zid: str = ''       # 当前打开的 PDF 对应 Zotero 条目 zid


class SyncBody(BaseModel):
    limit: Optional[int] = None
    no_embed: bool = False


class CreateNoteBody(BaseModel):
    title: str
    subject: Optional[str] = None


# ------------------------------------------------------------------- 笔记
@app.get('/api/notes')
def list_notes(subject: Optional[str] = None, limit: Optional[int] = None):
    return _kg().list_notes(subject=subject, limit=limit)


@app.get('/api/note')
def get_note(path: str = Query(...)):
    md = _norm_md(path)
    return _note_checked(md)


@app.put('/api/note')
def save_note(path: str = Query(...), body: SaveBody = None):
    md = _norm_md(path)
    _note_checked(md)
    wc = len(body.content.replace('\n', '').replace('\r', ''))
    _kg().set_note_content(md, body.content, title=body.title, word_count=wc)
    # 2026-08-29 起：Neo4j 为唯一内容源，不再回写 Files/*.md（Files 仅保留 assets 图片）
    return {'ok': True, 'word_count': wc}


def _unique_md_path(title: str) -> str:
    """由标题生成 Files/新建笔记/ 下唯一 md_path（Neo4j 内不存在冲突）。

    返回绝对形式（_norm_md 归一化），与后端其余路径处理一致。
    """
    safe = re.sub(r'[\\/:*?"<>|\s]+', '_', title).strip('_') or '未命名'
    rel = f'新建笔记/{safe}'
    md_path = _norm_md(f'{rel}.md')
    if _kg().note(md_path) is None:
        return md_path
    return _norm_md(f'{rel}-{time.strftime("%Y%m%d%H%M%S")}.md')


@app.post('/api/notes')
def create_note(body: CreateNoteBody):
    title = (body.title or '').strip()
    if not title:
        raise HTTPException(400, '标题不能为空')
    md_path = _unique_md_path(title)
    subs = [body.subject] if body.subject and body.subject.strip() else None
    _kg().create_note(md_path, title, subjects=subs)
    return _note_checked(md_path)


def _delete_note_files(md: str):
    """删除 Files/ 内 md 载体 + 笔记同级 assets/<笔记名>/ 图片目录（尽力而为）。"""
    target = Path(md)
    fd = Path(FILES_DIR).resolve()
    if str(target.resolve()).startswith(str(fd)) and target.is_file():
        try:
            target.unlink()
        except OSError:
            pass
    img_dir = target.parent / 'assets' / target.stem
    if img_dir.is_dir():
        shutil.rmtree(img_dir, ignore_errors=True)


@app.delete('/api/note')
def delete_note(path: str = Query(...)):
    md = _norm_md(path)
    _note_checked(md)
    _kg().delete_note(md)
    _delete_note_files(md)
    return {'ok': True}


@app.get('/api/note/export')
def export_note(path: str = Query(...)):
    """导出单篇笔记为 Markdown 文件下载。"""
    md = _norm_md(path)
    note = _note_checked(md)
    # 构建 YAML frontmatter
    lines = ['---']
    for key in ['title', 'type', 'stars', 'created', 'source_docx', 'md_path', 'word_count', 'indexed_at']:
        val = note.get(key)
        if val is None:
            continue
        if key in ('keywords', 'subjects') and not val:
            continue
        if isinstance(val, str):
            # YAML 字符串安全转义
            if any(c in val for c in (':', '#', '\'', '"', '\n', '\r')):
                val = json.dumps(val, ensure_ascii=False)
            lines.append(f'{key}: {val}')
        else:
            lines.append(f'{key}: {val}')
    keywords = note.get('keywords') or []
    if keywords:
        lines.append('keywords:')
        for kw in keywords:
            lines.append(f'  - {kw}')
    subjects = note.get('subjects') or []
    if subjects:
        lines.append('subjects:')
        for sub in subjects:
            lines.append(f'  - {sub}')
    lines.append('---')
    lines.append('')
    content = note.get('content') or ''
    lines.append(content)
    if content and not content.endswith('\n'):
        lines.append('')
    body = '\n'.join(lines)

    safe_title = re.sub(r'[\\/:*?"<>|\s]+', '_', note.get('title') or Path(md).stem).strip('_') or '未命名'
    filename = f'{safe_title}.md'
    encoded = urllib.parse.quote(filename)
    return StreamingResponse(
        io.BytesIO(body.encode('utf-8')),
        media_type='text/markdown; charset=utf-8',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded}"
        }
    )


# ---------------------------------------------------------------- 笔记图片
def _note_asset_dir(md_path: str) -> Path:
    """笔记同级 assets/<笔记名>/ 目录（与 docx 转换产物的图片布局一致）。"""
    p = Path(_norm_md(md_path))
    return p.parent / 'assets' / p.stem


@app.get('/api/note/image')
def note_image(path: str = Query(...), rel: str = Query(...)):
    """按 md_path + 相对笔记所在目录的图片路径返回图片文件（防路径穿越）。"""
    md = _norm_md(path)
    _note_checked(md)
    base = Path(md).parent.resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(400, '非法图片路径')
    if not target.is_file():
        raise HTTPException(404, f'图片不存在: {rel}')
    media = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
    return FileResponse(target, media_type=media)


@app.post('/api/note/image')
async def upload_note_image(path: str = Query(...), file: UploadFile = File(...)):
    """上传图片到笔记同级 assets/<笔记名>/，返回相对笔记的 md 引用路径。

    命名沿用 docx 转换规则 <笔记名>_imgNNNN.<ext>，编号自动递增避免覆盖。
    """
    md = _norm_md(path)
    _note_checked(md)
    ext = Path(file.filename or '').suffix.lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}:
        raise HTTPException(400, f'不支持的图片格式: {ext or "未知"}')
    data = await file.read()
    if not data:
        raise HTTPException(400, '空文件')
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, '图片过大（>15MB）')
    base = Path(md).stem
    d = _note_asset_dir(md)
    d.mkdir(parents=True, exist_ok=True)
    nxt = 1
    for f in d.glob(f'{base}_img*'):
        m = re.match(rf'{re.escape(base)}_img(\d+)\.', f.name)
        if m:
            nxt = max(nxt, int(m.group(1)) + 1)
    name = f'{base}_img{nxt:04d}{ext}'
    (d / name).write_bytes(data)
    rel = f'assets/{base}/{name}'
    return {'name': name, 'rel': rel}


def _ai_assign_subjects(md_path: str, content: str, title: str = '') -> list:
    """用 AI 为主题分类：复用 assign_subjects 的 ask_one 逻辑（文本取自 content）。"""
    from assign_subjects import flatten_subjects, ask_one  # noqa: PLC0415
    subj_file = CODE_DIR / 'backend' / 'data' / 'subjects.json'
    if not subj_file.is_file():
        raise FileNotFoundError(f'未找到主题分类树: {subj_file}')
    subj_data = json.loads(subj_file.read_text(encoding='utf-8'))
    cats, tree_text = flatten_subjects(subj_data)
    import assign_subjects as _as  # noqa: PLC0415
    _as._TREE_CATS = cats
    from API import ai_ask  # noqa: PLC0415
    return ask_one(ai_ask, title or md_path, content,
                   _kg().list_subjects(), tree_text,
                   'qwen-plus', 'gpt-4o', 8000)


@app.post('/api/note/index')
def reindex_note(path: str = Query(...)):
    """重新索引一篇笔记：嵌入向量 + AI 主题分配 + 星级/类型/关键词评估。

    文本一律取自 Neo4j Note.content（唯一内容来源），不读 md 文件。
    """
    md = _norm_md(path)
    n = _note_checked(md)
    content = n.get('content') or ''
    if not content.strip():
        raise HTTPException(400, '笔记内容为空，请先写入内容再索引')
    out = {'ok': True, 'embedded': False, 'subjects': [], 'fields': {}}

    from API import ai_ask  # noqa: PLC0415
    # 1) 嵌入向量
    try:
        vec = ai_ask.get_qwen_embedding(
            content, model='text-embedding-v3', dimensions=512)
        if vec:
            _kg().set_note_embedding(md, vec)
            out['embedded'] = True
    except Exception as e:  # noqa: BLE001
        out['embed_error'] = str(e)

    # 2) 主题分配（复用 assign_subjects 的 AI 分类逻辑，文本取自 content）
    try:
        subs = _ai_assign_subjects(md, content, n.get('title') or '')
        if subs:
            _kg().set_note_subjects(md, subs)
            out['subjects'] = subs
    except Exception as e:  # noqa: BLE001
        out['subjects_error'] = str(e)

    # 3) 星级/类型/关键词评估（复用 ai_index_fields：qwen-plus 主 + gpt-4o 兜底）
    try:
        from ai_index_fields import ask_one as _fields_ask_one  # noqa: PLC0415
        fields = _fields_ask_one(
            ai_ask, n.get('title') or '', content, 'qwen-plus', 'gpt-4o', 8000)
        if fields:
            from ai_index_fields import apply_to_neo4j as _fields_apply  # noqa: PLC0415
            _fields_apply(_kg(), md, fields)
            out['fields'] = fields
    except Exception as e:  # noqa: BLE001
        out['fields_error'] = str(e)
    return out


@app.delete('/api/note/subject')
def remove_note_subject(path: str = Query(...), subject: str = Query(...)):
    """移除一篇笔记与某个 Subject 的 ON 关联。

    移除后若该笔记不再属于任何主题，则自动调用 AI 重新分配主题。
    """
    md = _norm_md(path)
    n = _note_checked(md)
    subj = subject.strip()
    if not subj:
        raise HTTPException(400, '主题名不能为空')
    if subj not in (n.get('subjects') or []):
        raise HTTPException(404, f'该笔记未关联主题: {subj}')

    # 1) 删除该主题关联
    _kg()._tx(
        "MATCH (n:Note {md_path: $md})-[r:ON]->(s:Subject {name: $subj}) DELETE r",
        md=md, subj=subj)

    # 2) 检查剩余主题数
    rows = _kg()._tx(
        "MATCH (n:Note {md_path: $md})-[:ON]->(:Subject) RETURN count(*) AS c",
        md=md)
    remaining = rows[0]['c'] if rows else 0

    # 3) 若失去全部主题则 AI 重分配
    reindexed = None
    if remaining == 0:
        content = (n.get('content') or '').strip()
        if content:
            try:
                subs = _ai_assign_subjects(md, content, n.get('title') or '')
                if subs:
                    _kg().set_note_subjects(md, subs)
                    reindexed = subs
            except Exception as e:  # noqa: BLE001
                print(f'[remove_note_subject] 重分配失败 {md}: {e}')

    return {'ok': True, 'removed': subj, 'remaining': remaining, 'reindexed': reindexed}


@app.post('/api/note/subject')
def add_note_subject(path: str = Query(...), subject: str = Query(...)):
    """给一篇笔记追加一个主题（不覆盖已有主题）。

    与 set_note_subjects（重建）不同：此处仅 upsert Subject 并 MERGE 一条 ON 关系，
    保留该笔记已有的其它主题；若主题已关联则幂等返回。
    """
    md = _norm_md(path)
    n = _note_checked(md)
    subj = subject.strip()
    if not subj:
        raise HTTPException(400, '主题名不能为空')
    existing = n.get('subjects') or []
    if subj in existing:
        return {'ok': True, 'added': None, 'remaining': len(existing)}
    _kg().upsert_subject(subj)
    _kg()._tx(
        "MATCH (n:Note {md_path: $md}), (s:Subject {name: $subj}) MERGE (n)-[:ON]->(s)",
        md=md, subj=subj)
    return {'ok': True, 'added': subj, 'remaining': len(existing) + 1}


@app.get('/api/related')
def related_notes(path: str = Query(...), limit: int = 10):
    md = _norm_md(path)
    _note_checked(md)
    res = _kg().related_notes(md, limit=limit) or []
    out = []
    for p, sc, reasons in res:
        n = _kg().note(p) or {}
        out.append({
            'md_path': p,
            'title': n.get('title') or p,
            'stars': n.get('stars'),
            'type': n.get('type'),
            'reason': '、'.join(reasons),
            'score': sc,
        })
    return out


@app.get('/api/related-resources')
def related_resources(path: str = Query(...), limit: int = 6):
    md = _norm_md(path)
    _note_checked(md)
    res = _kg().related_resources(md, limit=limit) or []
    return [{'title': t, 'score': s, 'zotero_id': z, 'dir': d, 'date': dt}
            for t, s, z, d, dt in res]


# ------------------------------------------------------------------- 主题/搜索/图谱
@app.get('/api/subjects')
def subjects():
    # 主题视图按总星级（该主题下所有 Note 的 stars 之和）从大到小排序
    return _kg().list_subjects_by_stars()


@app.get('/api/subject-catalog')
def subject_catalog():
    """返回学科分类树（backend/data/subjects.json）中的全部名称，扁平化、去重。

    供前端「添加主题」输入框做包含匹配；不含根节点「学科」。
    """
    subj_file = CODE_DIR / 'backend' / 'data' / 'subjects.json'
    if not subj_file.is_file():
        return []
    data = json.loads(subj_file.read_text(encoding='utf-8'))
    out: list = []

    def walk(node, is_root=False):
        name = (node or {}).get('name')
        if name and not is_root:
            out.append(name)
        for child in (node or {}).get('children', []) or []:
            walk(child, False)

    walk(data, True)
    return sorted(set(out))


@app.get('/api/subject-counts')
def subject_counts():
    return {c['name']: c['count'] for c in _kg().subject_counts()}


def _subject_notes(name: str) -> list:
    """返回挂在该主题下的全部 Note md_path（归一化）。"""
    rows = _kg()._tx(
        "MATCH (n:Note)-[:ON]->(:Subject {name: $name}) "
        "RETURN n.md_path AS md_path ORDER BY n.md_path", name=name)
    return [r['md_path'] for r in rows]


@app.delete('/api/subject')
def delete_subject(name: str = Query(...)):
    """仅删除 Subject（保留笔记）。

    1. 摘除该主题与所有 Note 的 ON 关系，再删除 Subject 节点；
    2. 对因此失去全部主题的 Note，自动 AI 重新分配主题。
    若其它节点（Project/Resource 等）仍引用该主题，DETACH DELETE 会一并移除相关关系。
    """
    name = name.strip()
    if not name:
        raise HTTPException(400, '主题名不能为空')
    if name not in _kg().list_subjects():
        raise HTTPException(404, f'未找到主题: {name}')

    paths = _subject_notes(name)
    # 1) 删除该主题的所有入边关系（含 Note-ON / Project-COVERS / Resource-ABOUT）
    _kg()._tx("MATCH (s:Subject {name: $name}) DETACH DELETE s", name=name)

    # 2) 删除后无任何主题的 Note 自动 AI 重分配
    reindexed, failed = [], []
    if paths:
        orphan = _kg()._tx(
            "MATCH (n:Note) WHERE NOT (n)-[:ON]->(:Subject) "
            "RETURN n.md_path AS md_path")
        orphan_paths = [r['md_path'] for r in orphan]
        for md in orphan_paths:
            n = _kg().note(md) or {}
            content = (n.get('content') or '').strip()
            if not content:
                continue
            try:
                subs = _ai_assign_subjects(md, content, n.get('title') or '')
                if subs:
                    _kg().set_note_subjects(md, subs)
                    reindexed.append({'md_path': md, 'subjects': subs})
                else:
                    failed.append(md)
            except Exception as e:  # noqa: BLE001
                print(f'[delete_subject] 重分配失败 {md}: {e}')
                failed.append(md)

    return {'ok': True, 'removed_notes': len(paths),
            'reindexed': reindexed, 'failed': failed}


@app.delete('/api/subject/content')
def delete_subject_content(name: str = Query(...)):
    """删除 Subject 及其下所有内容（笔记 + 本地载体文件）。

    删除该主题下全部 Note（Neo4j 节点 + Files/*.md 载体 + assets/<笔记名>/ 图片），
    最后删除 Subject 节点本身。
    """
    name = name.strip()
    if not name:
        raise HTTPException(400, '主题名不能为空')
    if name not in _kg().list_subjects():
        raise HTTPException(404, f'未找到主题: {name}')

    paths = _subject_notes(name)
    deleted = []
    for md in paths:
        _kg().delete_note(md)
        _delete_note_files(md)
        deleted.append(md)
    _kg()._tx("MATCH (s:Subject {name: $name}) DETACH DELETE s", name=name)
    return {'ok': True, 'deleted_notes': deleted}


@app.post('/api/search')
def search(body: SearchBody):
    res = _kg().vector_search(body.query, label=body.label, limit=body.limit)
    if res is None:
        raise HTTPException(503, '向量搜索不可用（请确认已 ensure-schema 且存在向量）')
    if body.label == 'Resource':
        return [{'title': t, 'zotero_id': z, 'dir': d, 'date': dt, 'score': s}
                for t, z, d, dt, s in res]
    return [{'md_path': p, 'title': t, 'type': tp, 'stars': st, 'score': s}
            for p, t, tp, st, s in res]


@app.get('/api/graph')
def graph(path: str = Query(...)):
    md = _norm_md(path)
    nodes, links = _kg().note_graph(md)
    if nodes is None:
        raise HTTPException(404, f'未找到笔记: {md}')
    return {'nodes': nodes, 'links': links}


@app.get('/api/stats')
def stats():
    return _kg().stats()


# ------------------------------------------------------------------- Resource / PDF
@app.get('/api/resources')
def resources():
    return _kg().list_resources()


@app.get('/api/resources/{zotero_id}')
def resource_detail(zotero_id: str):
    res = _kg().resource_by_zotero_id(zotero_id)
    if not res:
        raise HTTPException(404, '未找到该资源')
    # 统一字段名，与前端 Resource 类型保持一致
    return {
        'title': res.get('title'),
        'keywords': res.get('keywords'),
        'abstract': res.get('abstract') or '',
        'zid': res.get('zotero_id'),
        'dir': res.get('dir') or '',
        'doi': res.get('doi') or '',
        'date': res.get('date') or '',
        'authors': res.get('authors') or [],
        'itype': res.get('item_type') or '',
        'ckey': res.get('citation_key') or '',
        'url': res.get('url') or '',
        'ptitle': res.get('publication_title') or '',
        'coll': res.get('collection') or '',
        'subjects': res.get('subjects') or [],
    }


@app.get('/api/resources/{zotero_id}/pdf')
def resource_pdf(zotero_id: str):
    res = _kg().resource_by_zotero_id(zotero_id)
    if not res or not res.get('dir'):
        raise HTTPException(404, '该条目无本地 PDF')
    p = Path(res['dir'])
    if not p.is_file():
        raise HTTPException(404, f'PDF 不存在: {p}')
    return FileResponse(p, media_type='application/pdf', content_disposition_type='inline')


@app.post('/api/resources/{zotero_id}/open-dir')
def open_resource_dir(zotero_id: str):
    """在系统文件管理器中打开该条目本地文件的所在目录并选中文件。"""
    res = _kg().resource_by_zotero_id(zotero_id)
    if not res or not res.get('dir'):
        raise HTTPException(404, '该条目无本地文件')
    p = Path(res['dir'])
    if not p.is_file():
        raise HTTPException(404, f'文件不存在: {p}')
    try:
        if sys.platform.startswith('win'):
            subprocess.Popen(['explorer', '/select,', str(p)])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', str(p)])
        else:
            subprocess.Popen(['xdg-open', str(p.parent)])
    except OSError as e:
        raise HTTPException(500, f'无法打开文件所在路径: {e}')
    return {'ok': True, 'dir': str(p.parent)}


@app.post('/api/resources/sync')
def sync_resources(body: Optional[SyncBody] = None):
    """触发 Zotero -> Neo4j 同步（调 zotero_bib.py sync）。"""
    if not ZOTERO_SCRIPT.is_file():
        raise HTTPException(404, f'未找到 zotero_bib.py: {ZOTERO_SCRIPT}')
    secrets = secret_manager.read_secrets_from_env()
    cmd = [sys.executable, str(ZOTERO_SCRIPT), 'sync',
           '--api-dir', str(CODE_DIR),
           '--uri', secrets.get('local_neo4j_url', 'bolt://localhost:7687'),
           '--user', secrets.get('local_neo4j_username', 'neo4j'),
           '--password', secrets.get('local_neo4j_password', '')]
    if body and body.limit:
        cmd += ['--limit', str(body.limit)]
    if body and body.no_embed:
        cmd += ['--no-embed']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           timeout=3600, cwd=str(CODE_DIR))
    except subprocess.TimeoutExpired:
        raise HTTPException(504, '同步超时（>1h）')
    if r.returncode != 0:
        raise HTTPException(500, f'sync 失败: {(r.stderr or "")[-2000:]}')
    return {'ok': True, 'output': (r.stdout or '')[-2000:]}


# ------------------------------------------------------------------- AI 对话
def _to_ask_history(history):
    """[{role, content}] -> [{"user": .., "bot": ..}] 成对（ai_ask 格式）。"""
    out, i = [], 0
    while i < len(history):
        m = history[i]
        if m.get('role') == 'user':
            bot = ''
            if i + 1 < len(history) and history[i + 1].get('role') == 'assistant':
                bot = history[i + 1].get('content', '')
                i += 1
            out.append({'user': m.get('content', ''), 'bot': bot})
        i += 1
    return out[-6:]  # 只保留最近 3 轮，控制 token


def _extract_pdf_text(path: Path, limit: int = 8000) -> str:
    """用 pymupdf 提取 PDF 文本（失败回退 pdfplumber），截取前 limit 字符。"""
    try:
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf
        doc = pymupdf.open(str(path))
        try:
            text = ''
            for page in doc:
                text += str(page.get_text())
                if len(text) >= limit:
                    break
            return text[:limit]
        finally:
            doc.close()
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                text = ''.join((pg.extract_text() or '') for pg in pdf.pages)
            return text[:limit]
        except Exception:
            return ''


def _rag_context(message: str, topk: int = 5) -> str:
    """全库 RAG：对问题做向量检索，召回相似度最高的笔记片段。"""
    hits = _kg().vector_search(message, label='Note', limit=topk) or []
    blocks = []
    for h in hits:
        md_path, title, _type, _stars, score = h
        n = _kg().note(md_path)
        body = ((n or {}).get('content') or '').strip()[:2000]
        if not body:
            continue
        blocks.append(
            f'### 片段：{title}（相似度 {score:.3f}）\n'
            f'来源：{md_path}\n{body}'
        )
    return '\n\n'.join(blocks)


@app.post('/api/chat')
def chat(body: ChatBody):
    n = None
    if body.md_path:
        # 打开笔记时的上下文；若笔记不存在（已被删除等）则忽略，不影响 RAG / 普通问答
        try:
            n = _note_checked(_norm_md(body.md_path))
        except HTTPException:
            n = None
    sys.path.insert(0, str(CODE_DIR))
    from API import ai_ask

    # ---- 上下文组装：按开关选择性注入 ----
    ctx = []
    if body.use_note and n:
        head = (
            f"当前笔记：《{n.get('title') or ''}》\n"
            f"类型：{n.get('type') or '未知'} | 星级：{n.get('stars') or '-'} | "
            f"关键词：{'、'.join(n.get('keywords') or []) or '-'}\n"
        )
        text = (n.get('content') or '')[:3000]
        ctx.append(f'## 当前笔记\n{head}\n正文：\n{text}')

    if body.use_pdf and body.resource_zid:
        res = _kg().resource_by_zotero_id(body.resource_zid) or {}
        pdf_path = res.get('dir')
        if pdf_path and Path(pdf_path).is_file():
            pdf_text = _extract_pdf_text(Path(pdf_path))
            if pdf_text:
                ctx.append(
                    f'## 当前打开的 PDF 内容\n'
                    f'标题：{res.get("title") or "未知"}\n正文（节选）：\n{pdf_text}'
                )
        else:
            ctx.append('## 当前打开的 PDF 内容\n（未能读取该 PDF 文本）')

    if body.rag:
        rag_text = _rag_context(body.message)
        ctx.append(
            f'## 全库知识库检索（RAG）结果\n'
            f'{rag_text if rag_text else "（未检索到相关知识片段）"}'
        )

    if ctx:
        prompt = '\n\n'.join(ctx) + f'\n\n用户问题：{body.message}'
    else:
        prompt = f'用户问题：{body.message}'
    system = ('你是我的个人知识库助手。请优先依据上面提供的上下文内容回答；'
              '若上下文包含当前笔记/PDF/RAG 片段，请引用其内容展开分析；'
              '上下文中不包含的信息，请直接说明并给出一般性回答。'
              '当你在回答中提及知识库中的某篇笔记时，必须用书名号《》包裹该笔记的完整标题'
              '（例如《衡水与农村教育》），以便前端把该标题渲染成可点击跳转的笔记链接。')
    model = body.model or 'qwen-turbo'
    history = _to_ask_history(body.history)

    def gen():
        # SSE 流式：每个文本块一行 data: {"delta": "..."}，结束标记 data: [DONE]
        try:
            if model.startswith('gpt-'):
                # GPT 系列 → YunWu（OpenLux）流式（OpenAI 兼容 /v1/chat/completions）
                it = ai_ask.ask_yunwu_stream(
                    prompt_text=prompt,
                    history=history,
                    system_instruction=system,
                    model=model,
                    temperature=0.3,
                )
            else:
                # Qwen / DeepSeek（均由阿里云百炼托管）→ 百炼流式优先，
                # 首个块之前失败则回退 YunWu GPT-4o 流式
                it = ai_ask.ask_qwen_with_gpt_backup_stream(
                    prompt_text=prompt,
                    history=history,
                    system_instruction=system,
                    model=model,
                    temperature=0.3,
                    retry_model='gpt-4o',
                )
            for piece in it:
                yield f'data: {json.dumps({"delta": piece}, ensure_ascii=False)}\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            print(f'/api/chat stream error: {e}')
            yield f'data: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'

    return StreamingResponse(
        gen(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.get('/api/health')
def health():
    return {'ok': kg is not None, 'files_dir': str(FILES_DIR)}


# ---- 生产模式：托管前端构建产物（code/frontend/dist），单服务访问 ----
DIST_DIR = CODE_DIR / 'frontend' / 'dist'
if DIST_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount('/', StaticFiles(directory=str(DIST_DIR), html=True), name='spa')
    print(f'[后端] 已托管前端构建产物: {DIST_DIR}')
