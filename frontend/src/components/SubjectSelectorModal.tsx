import { useMemo, useState } from 'react'

interface Props {
  subjects: string[]
  subjectCounts: Record<string, number>
  active: string | null
  totalCount: number
  onSelect: (name: string | null) => void
  onClose: () => void
}

export default function SubjectSelectorModal({
  subjects,
  subjectCounts,
  active,
  totalCount,
  onSelect,
  onClose,
}: Props) {
  const [q, setQ] = useState('')

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase()
    if (!t) return subjects
    return subjects.filter((s) => s.toLowerCase().includes(t))
  }, [subjects, q])

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal subject-modal" onClick={(e) => e.stopPropagation()}>
        <div className="subject-modal-head">
          <h3>选择主题</h3>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>

        <input
          type="text"
          className="subject-modal-search"
          placeholder="搜索主题…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />

        <div className="subject-modal-grid">
          <button
            className={`chip ${active === null ? 'active' : ''}`}
            onClick={() => onSelect(null)}
          >
            全部 <span className="count">{totalCount}</span>
          </button>
          {filtered.map((s) => (
            <button
              key={s}
              className={`chip ${active === s ? 'active' : ''}`}
              onClick={() => onSelect(s)}
            >
              {s} <span className="count">{subjectCounts[s] ?? 0}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
