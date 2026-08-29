import { useStore } from '../stores/useStore'

function Stars({ n }: { n: number | null }) {
  if (!n) return null
  return <span className="stars">{'★'.repeat(n)}</span>
}

export default function Recommendations() {
  const { related, loadNote, currentPath } = useStore()

  return (
    <>
      <div className="section-title">相关笔记（语义相似）</div>
      <div className="recommend-list">
        {related.length === 0 && (
          <div style={{ color: 'var(--text-dim)', padding: 10, fontSize: 12 }}>
            选择一篇笔记后显示
          </div>
        )}
        {related.map((r) => (
          <div
            key={r.md_path}
            className={`rec-item ${r.md_path === currentPath ? 'active' : ''}`}
            onClick={() => void loadNote(r.md_path)}
          >
            <div className="rt">{r.title}</div>
            <div className="rm">
              <Stars n={r.stars} />
              <span> 相关度 {r.score.toFixed(3)}</span>
              {r.reason && <div style={{ marginTop: 2 }}>{r.reason}</div>}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
