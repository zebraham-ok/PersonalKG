import type {
  GraphData,
  Note,
  NoteHit,
  NoteSummary,
  RelatedNote,
  RelatedResource,
  Resource,
  ResourceHit,
  Stats,
} from '../types'

const API = '/api'

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  return sp.toString()
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const d = await res.json()
      if (d?.detail) msg = String(d.detail)
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => fetch(`${API}/health`).then(j<{ ok: boolean; files_dir: string }>),

  notes: (subject?: string) =>
    fetch(`${API}/notes?${qs({ subject })}`).then(j<NoteSummary[]>),

  note: (path: string) =>
    fetch(`${API}/note?${qs({ path })}`).then(j<Note>),

  createNote: (title: string, subject?: string | null) =>
    fetch(`${API}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, subject }),
    }).then(j<Note>),

  deleteNote: (path: string) =>
    fetch(`${API}/note?${qs({ path })}`, { method: 'DELETE' }).then(j<{ ok: boolean }>),

  exportNote: (path: string) => fetch(`${API}/note/export?${qs({ path })}`).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.blob()
  }),

  reindexNote: (path: string) =>
    fetch(`${API}/note/index?${qs({ path })}`, { method: 'POST' }).then(
      j<{ ok: boolean; embedded: boolean; subjects: string[] }>,
    ),

  removeNoteSubject: (path: string, subject: string) =>
    fetch(`${API}/note/subject?${qs({ path, subject })}`, { method: 'DELETE' }).then(
      j<{ ok: boolean; removed: string; remaining: number; reindexed: string[] | null }>,
    ),

  addNoteSubject: (path: string, subject: string) =>
    fetch(`${API}/note/subject?${qs({ path, subject })}`, { method: 'POST' }).then(
      j<{ ok: boolean; added: string | null; remaining: number }>,
    ),

  subjectCatalog: () => fetch(`${API}/subject-catalog`).then(j<string[]>),

  saveNote: (path: string, content: string, title?: string) =>
    fetch(`${API}/note?${qs({ path })}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, title }),
    }).then(j<{ ok: boolean; word_count: number }>),

  related: (path: string, limit = 10) =>
    fetch(`${API}/related?${qs({ path, limit })}`).then(j<RelatedNote[]>),

  relatedResources: (path: string, limit = 6) =>
    fetch(`${API}/related-resources?${qs({ path, limit })}`).then(j<RelatedResource[]>),

  noteImageUrl: (path: string, rel: string) => {
    // react-markdown 默认 urlTransform 已对相对图片 URL 做过一次 encodeURI（中文→%xx），
    // 这里先还原，避免 URLSearchParams 二次编码成 %25xx 导致后端 404。
    let clean = rel
    try {
      if (/%[0-9a-fA-F]{2}/.test(clean)) clean = decodeURIComponent(clean)
    } catch {
      /* 含非法 % 序列时保留原样 */
    }
    return `${API}/note/image?${qs({ path, rel: clean })}`
  },

  uploadNoteImage: (path: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch(`${API}/note/image?${qs({ path })}`, {
      method: 'POST',
      body: fd,
    }).then(j<{ name: string; rel: string }>)
  },

  openResourceDir: (zoteroId: string) =>
    fetch(`${API}/resources/${encodeURIComponent(zoteroId)}/open-dir`, {
      method: 'POST',
    }).then(j<{ ok: boolean; dir: string }>),

  subjects: () => fetch(`${API}/subjects`).then(j<string[]>),

  subjectCounts: () => fetch(`${API}/subject-counts`).then(j<Record<string, number>>),

  /** 仅删除 Subject（保留笔记）；因此失去全部主题的笔记会自动 AI 重新分配 */
  deleteSubject: (name: string) =>
    fetch(`${API}/subject?${qs({ name })}`, { method: 'DELETE' }).then(
      j<{
        ok: boolean
        removed_notes: number
        reindexed: { md_path: string; subjects: string[] }[]
        failed: string[]
      }>,
    ),

  /** 删除 Subject 及其下所有内容（笔记 + 本地载体文件） */
  deleteSubjectWithContent: (name: string) =>
    fetch(`${API}/subject/content?${qs({ name })}`, { method: 'DELETE' }).then(
      j<{ ok: boolean; deleted_notes: string[] }>,
    ),

  search: (query: string, label = 'Note', limit = 20) =>
    fetch(`${API}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, label, limit }),
    }).then(j<(NoteHit | ResourceHit)[]>),

  graph: (path: string) =>
    fetch(`${API}/graph?${qs({ path })}`).then(j<GraphData>),

  resources: () => fetch(`${API}/resources`).then(j<Resource[]>),

  resource: (zid: string) => fetch(`${API}/resources/${encodeURIComponent(zid)}`).then(j<Resource>),

  /** 流式对话（SSE）：onDelta 每收到一段文本即回调（参数为累计全文） */
  chatStream: async (
    md_path: string,
    message: string,
    history: { role: string; content: string }[],
    model: string,
    opts: {
      useNote?: boolean
      usePdf?: boolean
      rag?: boolean
      resourceZid?: string | null
    } = {},
    onDelta?: (full: string) => void,
  ): Promise<string> => {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        md_path,
        message,
        history,
        model,
        use_note: opts.useNote ?? true,
        use_pdf: opts.usePdf ?? false,
        rag: opts.rag ?? false,
        resource_zid: opts.resourceZid ?? '',
      }),
    })
    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let full = ''
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) {
        const t = line.trim()
        if (!t.startsWith('data:')) continue
        const data = t.slice(5).trim()
        if (!data || data === '[DONE]') continue
        try {
          const obj = JSON.parse(data) as { delta?: string; error?: string }
          if (obj.error) throw new Error(obj.error)
          if (obj.delta) {
            full += obj.delta
            onDelta?.(full)
          }
        } catch {
          // 忽略无法解析的 SSE 行
        }
      }
    }
    return full
  },

  syncResources: () =>
    fetch(`${API}/resources/sync`, { method: 'POST' }).then(j<{ ok: boolean; output: string }>),

  stats: () => fetch(`${API}/stats`).then(j<Stats>),
}
