import { create } from 'zustand'
import { api } from '../services/api'
import type {
  ChatMsg,
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

export interface KbTab {
  md_path: string
  title: string
}

export interface SendChatOpts {
  model: string
  useNote: boolean
  usePdf: boolean
  rag: boolean
}

/** 删除 Subject 的返回结果（仅删主题 / 删主题及内容 两种接口的并集） */
export interface DeleteSubjectResult {
  ok: boolean
  removed_notes?: number
  reindexed?: { md_path: string; subjects: string[] }[]
  failed?: string[]
  deleted_notes?: string[]
}

interface KbState {
  // 数据
  notes: NoteSummary[]
  /** 全量笔记（不受主题过滤影响，供 AI 回复《标题》链接匹配） */
  allNotes: NoteSummary[]
  subjects: string[]
  /** 学科分类树扁平化列表（供添加主题时包含匹配） */
  subjectCatalog: string[]
  subjectCounts: Record<string, number>
  subjectFilter: string | null
  tabs: KbTab[]
  currentPath: string | null
  current: Note | null
  related: RelatedNote[]
  relatedResources: RelatedResource[]
  graph: GraphData | null
  resources: Resource[]
  stats: Stats | null
  // UI
  noteLoading: boolean
  syncing: boolean
  toast: string | null
  searchMode: boolean
  searchQuery: string
  searchLabel: 'Note' | 'Resource'
  searchResults: (NoteHit | ResourceHit)[]
  /** 全局 AI 对话消息（切换笔记/面板不清空，除非用户点"清空对话"） */
  chatMsgs: ChatMsg[]
  chatBusy: boolean
  midTab: 'chat' | 'resource'
  pdfUrl: string | null
  currentResource: Resource | null
  indexing: boolean

  // 动作
  init: () => Promise<void>
  loadNotes: () => Promise<void>
  loadSubjects: () => Promise<void>
  loadSubjectCounts: () => Promise<void>
  loadNote: (path: string) => Promise<void>
  closeTab: (path: string) => void
  saveCurrent: () => Promise<void>
  createNote: (title: string, subject?: string | null) => Promise<void>
  deleteCurrent: () => Promise<void>
  deleteSubject: (name: string, withContent: boolean) => Promise<DeleteSubjectResult>
  removeCurrentSubject: (subject: string) => Promise<void>
  addCurrentSubject: (subject: string) => Promise<void>
  reindexCurrent: () => Promise<void>
  setCurrentContent: (content: string) => void
  renameCurrent: (title: string) => Promise<void>
  loadRelated: () => Promise<void>
  loadGraph: () => Promise<void>
  loadResources: () => Promise<void>
  doSearch: (q: string, label?: 'Note' | 'Resource') => Promise<void>
  clearSearch: () => void
  syncResources: () => Promise<void>
  setSubjectFilter: (s: string | null) => void
  showToast: (msg: string) => void
  clearToast: () => void
  setMidTab: (t: 'chat' | 'resource') => void
  openResourcePdf: (zid: string) => Promise<void>
  sendChat: (text: string, opts: SendChatOpts) => Promise<void>
  clearChat: () => void
}

let toastTimer: ReturnType<typeof setTimeout> | undefined
let notesReqId = 0

export const useStore = create<KbState>((set, get) => ({
  notes: [],
  allNotes: [],
  subjects: [],
  subjectCatalog: [],
  subjectCounts: {},
  subjectFilter: null,
  tabs: [],
  currentPath: null,
  current: null,
  related: [],
  relatedResources: [],
  graph: null,
  resources: [],
  stats: null,
  noteLoading: false,
  syncing: false,
  toast: null,
  searchMode: false,
  searchQuery: '',
  searchLabel: 'Note',
  searchResults: [],
  chatMsgs: [],
  chatBusy: false,
  midTab: 'chat',
  pdfUrl: null,
  currentResource: null,
  indexing: false,

  init: async () => {
    const [notes, subjects, subjectCatalog, subjectCounts, resources, stats] = await Promise.all([
      api.notes(),
      api.subjects(),
      api.subjectCatalog(),
      api.subjectCounts(),
      api.resources(),
      api.stats(),
    ])
    set({ notes, allNotes: notes, subjects, subjectCatalog, subjectCounts, resources, stats })
  },

  loadSubjectCounts: async () => {
    const subjectCounts = await api.subjectCounts().catch(() => ({} as Record<string, number>))
    set({ subjectCounts })
  },

  loadSubjects: async () => {
    const subjects = await api.subjects().catch(() => [] as string[])
    set({ subjects })
  },

  loadNotes: async () => {
    const id = ++notesReqId
    // 总是拉取全量，再本地按主题过滤，保证 allNotes 始终完整（供《标题》链接匹配）
    const all = await api.notes()
    if (id !== notesReqId) return
    const filter = get().subjectFilter
    set({
      allNotes: all,
      notes: filter ? all.filter((n) => n.subjects.includes(filter)) : all,
    })
  },

  loadNote: async (path) => {
    // 多标签：若该笔记尚未打开，则追加一个标签
    const { tabs } = get()
    if (!tabs.some((t) => t.md_path === path)) {
      const known = get().notes.find((n) => n.md_path === path)
      const title = known?.title ?? path.split(/[\\/]/).pop()?.replace(/\.md$/, '') ?? path
      set({ tabs: [...tabs, { md_path: path, title }] })
    }
    set({ noteLoading: true, currentPath: path })
    try {
      const note = await api.note(path)
      set({ current: note, searchMode: false })
      // 并行加载周边上下文
      const [related, graph] = await Promise.all([
        api.related(path).catch(() => [] as RelatedNote[]),
        api.graph(path).catch(() => null as GraphData | null),
      ])
      set({
        related,
        graph,
        relatedResources: await api
          .relatedResources(path)
          .catch(() => [] as RelatedResource[]),
      })
    } finally {
      set({ noteLoading: false })
    }
  },

  closeTab: (path) => {
    const { tabs, currentPath } = get()
    const idx = tabs.findIndex((t) => t.md_path === path)
    if (idx < 0) return
    const next = tabs.filter((t) => t.md_path !== path)
    set({ tabs: next })
    if (currentPath === path) {
      const nxt = next[Math.min(idx, next.length - 1)]
      if (nxt) {
        void get().loadNote(nxt.md_path)
      } else {
        set({ current: null, currentPath: null, related: [], relatedResources: [], graph: null })
      }
    }
  },

  saveCurrent: async () => {
    const { current } = get()
    if (!current) return
    await api.saveNote(current.md_path, current.content, current.title)
    get().showToast(`已保存（${current.md_path}）`)
    // 刷新全量笔记，使「近期编辑」视图按最新 indexed_at 重排
    await get().loadNotes()
  },

  setCurrentContent: (content) => {
    const cur = get().current
    if (cur) set({ current: { ...cur, content } })
  },

  renameCurrent: async (title) => {
    const { current } = get()
    if (!current) return
    const trimmed = title.trim()
    if (!trimmed || trimmed === current.title) return
    await api.saveNote(current.md_path, current.content, trimmed)
    set({ current: { ...current, title: trimmed } })
    set((s) => ({
      tabs: s.tabs.map((t) =>
        t.md_path === current.md_path ? { ...t, title: trimmed } : t
      ),
    }))
    await get().loadNotes()
    get().showToast(`已重命名为《${trimmed}》`)
  },

  createNote: async (title, subject) => {
    const note = await api.createNote(title, subject)
    get().showToast(`已创建：${note.title}`)
    await get().loadNotes()
    await get().loadSubjectCounts()
    await get().loadNote(note.md_path)
  },

  deleteCurrent: async () => {
    const { currentPath } = get()
    if (!currentPath) return
    await api.deleteNote(currentPath)
    get().showToast('笔记已删除')
    set({
      current: null,
      currentPath: null,
      related: [],
      relatedResources: [],
      graph: null,
      tabs: get().tabs.filter((t) => t.md_path !== currentPath),
    })
    await get().loadNotes()
    await get().loadSubjectCounts()
  },

  deleteSubject: async (name, withContent) => {
    const r: DeleteSubjectResult = withContent
      ? await api.deleteSubjectWithContent(name)
      : await api.deleteSubject(name)
    // 若当前正按该主题过滤，清除过滤
    if (get().subjectFilter === name) set({ subjectFilter: null })
    // withContent 模式下，若当前打开/标签中的笔记已被删除，关闭之
    if (withContent && r.deleted_notes) {
      const gone = new Set(r.deleted_notes)
      const curPath = get().currentPath
      if (curPath && gone.has(curPath)) {
        set({
          current: null,
          currentPath: null,
          related: [],
          relatedResources: [],
          graph: null,
          tabs: get().tabs.filter((t) => !gone.has(t.md_path)),
        })
      }
    }
    if (withContent && r.deleted_notes?.length) {
      get().showToast(`已删除主题「${name}」及其下 ${r.deleted_notes.length} 篇笔记`)
    } else if (r.removed_notes) {
      const re = r.reindexed?.length ?? 0
      const fail = r.failed?.length ?? 0
      get().showToast(
        `已删除主题「${name}」（${r.removed_notes} 篇笔记移除该主题）` +
          (re || fail ? `｜AI 重分配 ${re} 篇${fail ? `，${fail} 失败` : ''}` : ''),
      )
    }
    await get().loadNotes()
    await get().loadSubjectCounts()
    await get().loadSubjects()
    return r
  },

  reindexCurrent: async () => {
    const { currentPath } = get()
    if (!currentPath) return
    set({ indexing: true })
    try {
      const r = await api.reindexNote(currentPath)
      const parts = [
        r.embedded ? '向量已更新' : '向量失败',
        r.subjects?.length ? `主题：${r.subjects.join('、')}` : '主题未分配',
      ]
      get().showToast(`索引完成：${parts.join(' | ')}`)
      // 刷新笔记（主题变化）与图谱
      await get().loadNote(currentPath)
      await get().loadNotes()
      await get().loadSubjectCounts()
      await get().loadSubjects()
    } finally {
      set({ indexing: false })
    }
  },

  removeCurrentSubject: async (subject) => {
    const { current, currentPath } = get()
    if (!current || !currentPath) return
    const r = await api.removeNoteSubject(currentPath, subject)
    const nextSubjects =
      r.reindexed && r.reindexed.length
        ? r.reindexed
        : current.subjects?.filter((s) => s !== r.removed) || []
    set({ current: { ...current, subjects: nextSubjects } })
    get().showToast(
      r.reindexed?.length
        ? `已移除「${r.removed}」，并重新分配主题：${r.reindexed.join('、')}`
        : `已移除「${r.removed}」`,
    )
    await get().loadNotes()
    await get().loadSubjectCounts()
    await get().loadSubjects()
  },

  addCurrentSubject: async (subject) => {
    const { current, currentPath } = get()
    if (!current || !currentPath) return
    const name = subject.trim()
    if (!name) return
    // 已关联则直接返回，避免重复
    if ((current.subjects || []).includes(name)) return
    const r = await api.addNoteSubject(currentPath, name)
    const nextSubjects = [...(current.subjects || [])]
    if (r.added && !nextSubjects.includes(r.added)) nextSubjects.push(r.added)
    set({ current: { ...current, subjects: nextSubjects } })
    get().showToast(r.added ? `已添加主题「${r.added}」` : '主题已存在，未重复添加')
    await get().loadNotes()
    await get().loadSubjectCounts()
    await get().loadSubjects()
  },

  loadRelated: async () => {
    const { currentPath } = get()
    if (!currentPath) return
    const related = await api.related(currentPath).catch(() => [] as RelatedNote[])
    set({ related })
  },

  loadGraph: async () => {
    const { currentPath } = get()
    if (!currentPath) return
    const graph = await api.graph(currentPath).catch(() => null as GraphData | null)
    set({ graph })
  },

  loadResources: async () => {
    const resources = await api.resources().catch(() => [] as Resource[])
    set({ resources })
  },

  doSearch: async (q, label = 'Note') => {
    const results = await api.search(q, label)
    set({ searchMode: true, searchQuery: q, searchLabel: label, searchResults: results })
  },

  clearSearch: () => set({ searchMode: false, searchQuery: '', searchResults: [] }),

  syncResources: async () => {
    set({ syncing: true })
    try {
      const r = await api.syncResources()
      get().showToast(`同步完成：${r.output.slice(-120)}`)
      await get().loadResources()
    } finally {
      set({ syncing: false })
    }
  },

  setSubjectFilter: (s) => {
    set({ subjectFilter: s })
    void get().loadNotes()
  },

  showToast: (msg) => {
    set({ toast: msg })
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => set({ toast: null }), 4000)
  },

  clearToast: () => set({ toast: null }),

  setMidTab: (t) => set({ midTab: t }),

  openResourcePdf: async (zid) => {
    set({ midTab: 'resource', currentResource: null, pdfUrl: null })
    try {
      const res = await api.resource(zid)
      set({ currentResource: res, pdfUrl: res.dir ? `/api/resources/${encodeURIComponent(zid)}/pdf` : null })
    } catch (e) {
      get().showToast(`加载资源失败：${e instanceof Error ? e.message : String(e)}`)
    }
  },

  sendChat: async (text, opts) => {
    const msg = text.trim()
    const { currentPath, currentResource, chatMsgs } = get()
    if (!msg || !currentPath || get().chatBusy) return
    const next = [...chatMsgs, { role: 'user' as const, content: msg }]
    // 先插入占位空消息，随 SSE 流式逐步填充
    set({ chatMsgs: [...next, { role: 'assistant', content: '' }], chatBusy: true })
    const aIdx = next.length
    try {
      const full = await api.chatStream(
        currentPath,
        msg,
        next,
        opts.model,
        {
          useNote: opts.useNote,
          usePdf: opts.usePdf,
          rag: opts.rag,
          resourceZid: currentResource?.zid,
        },
        (delta) => {
          set({ chatMsgs: [...next, { role: 'assistant', content: delta }] })
        },
      )
      set({ chatMsgs: [...next, { role: 'assistant', content: full }] })
    } catch (e) {
      const partial = (get().chatMsgs[aIdx] as ChatMsg | undefined)?.content ?? ''
      const err = `⚠️ ${String(e)}`
      set({
        chatMsgs: [
          ...next,
          { role: 'assistant', content: partial ? `${partial}\n\n${err}` : err },
        ],
      })
    } finally {
      set({ chatBusy: false })
    }
  },

  clearChat: () => set({ chatMsgs: [] }),
}))
