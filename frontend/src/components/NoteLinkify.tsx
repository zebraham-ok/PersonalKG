import { useStore } from '../stores/useStore'
import type { NoteSummary } from '../types'

/** 根据标题在笔记列表中查找匹配项（精确 → 标题包含名称 → 名称包含标题） */
function findNote(name: string): NoteSummary | undefined {
  const notes = useStore.getState().allNotes
  const n = name.trim()
  if (!n) return undefined
  let hit = notes.find((x) => x.title === n)
  if (hit) return hit
  const incl = notes
    .filter((x) => x.title.includes(n))
    .sort((a, b) => a.title.length - b.title.length)
  if (incl.length) return incl[0]
  if (n.length >= 4) {
    const cont = notes
      .filter((x) => n.includes(x.title) && x.title.length >= 2)
      .sort((a, b) => b.title.length - a.title.length)
    if (cont.length) return cont[0]
  }
  return undefined
}

/**
 * 将 AI 回复中的《标题》渲染为可点击链接：
 * 若能匹配到知识库中的某篇笔记，点击即在中间区域的新标签页打开该笔记。
 */
export default function NoteLinkify({ text }: { text: string }) {
  const loadNote = useStore((s) => s.loadNote)
  const parts = text.split(/(《[^》]+》)/g)
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^《(.+)》$/)
        if (!m) return <span key={i}>{p}</span>
        const hit = findNote(m[1])
        if (!hit) return <span key={i}>{p}</span>
        return (
          <a
            key={i}
            className="note-title-link"
            href="#"
            title={`打开笔记：${hit.title}`}
            onClick={(e) => {
              e.preventDefault()
              void loadNote(hit.md_path)
            }}
          >
            {p}
          </a>
        )
      })}
    </>
  )
}
