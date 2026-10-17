import { useEffect, useRef, useState } from 'react'
import { useStore } from '../stores/useStore'
import NewNoteModal from './NewNoteModal'

// 搜索范围：默认搜笔记，搜论文为下拉里的备选项
const LABELS: { key: 'Note' | 'Resource'; text: string }[] = [
  { key: 'Note', text: '搜索笔记' },
  { key: 'Resource', text: '搜索论文' },
]

export default function TopBar() {
  const { stats, syncing, syncResources, doSearch, init } = useStore()
  const [q, setQ] = useState('')
  const [label, setLabel] = useState<'Note' | 'Resource'>('Note')
  const [scopeOpen, setScopeOpen] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const scopeWrapRef = useRef<HTMLDivElement>(null)
  const [dark, setDark] = useState(
    () => (localStorage.getItem('kb.theme') ?? 'light') === 'dark',
  )

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('kb.theme', dark ? 'dark' : 'light')
  }, [dark])

  // 点击下拉外部时收起
  useEffect(() => {
    if (!scopeOpen) return
    const onDocClick = (e: MouseEvent) => {
      if (!scopeWrapRef.current?.contains(e.target as Node)) setScopeOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [scopeOpen])

  const onSearch = () => {
    if (!q.trim()) return
    void doSearch(q.trim(), label)
  }

  return (
    <header className="topbar">
      <div className="brand">个人知识库</div>
      <div className="search-box">
        <input
          value={q}
          placeholder={label === 'Note' ? '搜索笔记…（回车）' : '搜索论文…（回车）'}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
        />
        <div className="scope-menu-wrap" ref={scopeWrapRef}>
          <button
            className={`scope-caret ${scopeOpen ? 'active' : ''}`}
            title="切换搜索范围"
            onClick={() => setScopeOpen((v) => !v)}
          >
            ▾
          </button>
          {scopeOpen && (
            <div className="scope-menu">
              {LABELS.map((l) => (
                <button
                  key={l.key}
                  className={label === l.key ? 'active' : undefined}
                  onClick={() => {
                    setLabel(l.key)
                    setScopeOpen(false)
                  }}
                >
                  {label === l.key ? '✓ ' : ''}
                  {l.text}
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="primary" onClick={onSearch}>
          {label === 'Note' ? '搜索笔记' : '搜索论文'}
        </button>
      </div>
      <button className="primary" onClick={() => setShowNew(true)}>
        ＋ 新建笔记
      </button>
      <button disabled={syncing} onClick={() => void syncResources()}>
        {syncing ? '同步中…' : '同步 Zotero'}
      </button>
      <button title="重新加载数据" onClick={() => void init()}>
        刷新
      </button>
      <div className="stats">
        {stats && (
          <>
            {stats.notes ?? '-'} 笔记 · {stats.resources ?? '-'} 论文 ·{' '}
            {stats.subjects ?? '-'} 主题
          </>
        )}
      </div>
      <button title="切换明暗主题" onClick={() => setDark((d) => !d)}>
        {dark ? '浅色模式' : '深色模式'}
      </button>
      {showNew && <NewNoteModal onClose={() => setShowNew(false)} />}
    </header>
  )
}
