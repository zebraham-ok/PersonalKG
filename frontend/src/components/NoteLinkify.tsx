import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStore } from '../stores/useStore'
import type { NoteSummary } from '../types'

const KB_PREFIX = 'kb-note:'

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
 * 将 AI 回复渲染为 Markdown，并把其中《标题》渲染为可点击链接：
 * 渲染前先把能匹配到知识库笔记的《标题》改写为内部协议链接 kb-note:xxx，
 * 由 react-markdown 统一渲染（##、*、列表、表格等语法随之生效），
 * 该内部链接在 a 组件中被还原为可点击打开笔记的链接。
 */
export default function NoteLinkify({ text }: { text: string }) {
  const loadNote = useStore((s) => s.loadNote)

  const md = text.replace(/(《[^》\n]+》)/g, (p) => {
    const title = p.slice(1, -1).trim()
    return findNote(title)
      ? `[${p}](kb-note:${encodeURIComponent(title)})`
      : p
  })

  const components: Components = {
    a({ href, children }) {
      const h = href ?? ''
      if (h.startsWith(KB_PREFIX)) {
        const hit = findNote(decodeURIComponent(h.slice(KB_PREFIX.length)))
        if (hit) {
          return (
            <a
              className="note-title-link"
              title={`打开笔记：${hit.title}`}
              href="#"
              onClick={(e) => {
                e.preventDefault()
                void loadNote(hit.md_path)
              }}
            >
              {children}
            </a>
          )
        }
        // 匹配不到了（笔记已删除等）就退化为纯文本
        return <>{children}</>
      }
      // 普通外链：新窗口打开
      return (
        <a href={h} target="_blank" rel="noreferrer">
          {children}
        </a>
      )
    },
  }

  return (
    <div className="markdown-body chat-md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(u) => u}
        components={components}
      >
        {md}
      </ReactMarkdown>
    </div>
  )
}
