import { useEffect, useState } from 'react'
import { useStore } from '../stores/useStore'
import NewNoteModal from './NewNoteModal'

const LABELS: { key: 'Note' | 'Resource'; text: string }[] = [
  { key: 'Note', text: '笔记' },
  { key: 'Resource', text: '论文' },
]

export default function TopBar() {
  const { stats, syncing, syncResources, doSearch, init } = useStore()
  const [q, setQ] = useState('')
  const [label, setLabel] = useState<'Note' | 'Resource'>('Note')
  const [showNew, setShowNew] = useState(false)
  const [dark, setDark] = useState(
    () => (localStorage.getItem('kb.theme') ?? 'light') === 'dark',
  )

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('kb.theme', dark ? 'dark' : 'light')
  }, [dark])

  const onSearch = () => {
    if (!q.trim()) return
    void doSearch(q.trim(), label)
  }

  return (
    <header className="topbar">
      <div className="brand">个人知识库</div>
      <div className="search-box">
        {LABELS.map((l) => (
          <button
            key={l.key}
            className={label === l.key ? 'primary' : ''}
            style={{ flex: 'none', padding: '5px 10px', fontSize: 12 }}
            onClick={() => setLabel(l.key)}
          >
            {l.text}
          </button>
        ))}
        <input
          value={q}
          placeholder={label === 'Note' ? '搜索笔记…（回车）' : '搜索论文…（回车）'}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
        />
        <button onClick={onSearch}>搜索</button>
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
