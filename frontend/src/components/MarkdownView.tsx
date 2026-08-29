import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../services/api'

/** 外部/绝对地址：http(s)://、data:、blob:、/ 开头 */
function isExternal(src: string): boolean {
  return /^(https?:|data:|blob:|\/)/i.test(src)
}

export default function MarkdownView({
  content,
  mdPath,
}: {
  content: string
  mdPath?: string
}) {
  const components: Components = {
    img({ src, alt }) {
      if (!src) return null
      // 相对路径（如 assets/xxx/yyy.png）按笔记所在目录解析到后端图片接口
      const realSrc = src && !isExternal(src) && mdPath ? api.noteImageUrl(mdPath, src) : src
      return <img src={realSrc} alt={alt ?? ''} loading="lazy" />
    },
  }
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
