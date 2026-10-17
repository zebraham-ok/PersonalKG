import { useStore } from '../stores/useStore'
import type { Resource } from '../types'

/**
 * 论文预览区（PDF iframe / 元数据 / 空提示）。
 * 左栏下部与中间区域共用：点「中心显示」后由中间渲染、左栏下部改放笔记。
 */

function MetaLink({ label, href }: { label: string; href?: string }) {
  if (!href || href === 'null' || href === 'undefined') return null
  return (
    <a
      className="meta-link"
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  )
}

function ResourceMeta({ res }: { res: Resource }) {
  const doiUrl = res.doi
    ? res.doi.startsWith('http')
      ? res.doi
      : `https://doi.org/${res.doi}`
    : undefined
  return (
    <div className="resource-meta">
      <div className="rm-title">{res.title}</div>
      <div className="rm-line">
        {res.authors?.length ? res.authors.join(', ') : '佚名'}
        {res.date && ` · ${res.date}`}
        {res.itype && ` · ${res.itype}`}
      </div>
      {res.ptitle && <div className="rm-line">{res.ptitle}</div>}
      <div className="rm-links">
        <MetaLink label="DOI" href={doiUrl} />
        <MetaLink label="网页" href={res.url} />
      </div>
      {res.abstract && <div className="rm-abstract">{res.abstract}</div>}
    </div>
  )
}

export default function ResourcePreview() {
  const { pdfUrl, currentResource } = useStore()
  if (pdfUrl) return <iframe title="pdf" src={pdfUrl} />
  if (currentResource) return <ResourceMeta res={currentResource} />
  return <div className="no-pdf">← 选择一篇论文查看 PDF 或访问 DOI/网页</div>
}
