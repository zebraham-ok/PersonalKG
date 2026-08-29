import { useStore } from '../stores/useStore'

/** 中间区域顶部的多标签栏（可左右滑动） */
export default function TabsBar() {
  const { tabs, currentPath, loadNote, closeTab } = useStore()
  if (!tabs.length) return null
  return (
    <div className="note-tabs">
      {tabs.map((t) => (
        <div
          key={t.md_path}
          className={`note-tab ${t.md_path === currentPath ? 'active' : ''}`}
          title={t.md_path}
          onClick={() => void loadNote(t.md_path)}
        >
          <span className="note-tab-title">{t.title}</span>
          <button
            className="note-tab-close"
            title="关闭标签"
            onClick={(e) => {
              e.stopPropagation()
              closeTab(t.md_path)
            }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
