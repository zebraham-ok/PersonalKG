import { useStore } from '../stores/useStore'
import { api } from '../services/api'
import type { RelatedResource, Resource } from '../types'

function ResourceItem({
  title,
  meta,
  active,
  hasPdf,
  onClick,
  onOpenDir,
}: {
  title: string
  meta: string
  active: boolean
  hasPdf: boolean
  onClick: () => void
  onOpenDir?: () => void
}) {
  return (
    <div className={`resource-item ${active ? 'active' : ''}`} onClick={onClick}>
      <div className="rt">
        <span className="rt-title">{title}</span>
        {hasPdf && onOpenDir && (
          <button
            className="open-dir-btn"
            title="在文件管理器中打开该文件所在路径"
            onClick={(e) => {
              e.stopPropagation()
              onOpenDir()
            }}
          >
            打开路径
          </button>
        )}
      </div>
      <div className="rm">
        {meta}
        {!hasPdf && <span className="no-pdf-tag">无 PDF</span>}
      </div>
    </div>
  )
}

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

function isResource(r: Resource | RelatedResource | null): r is Resource {
  return r != null && 'zid' in r
}

export default function ResourcePanel() {
  const { relatedResources, resources, currentResource, pdfUrl, openResourcePdf } = useStore()
  const activeZid = currentResource?.zid ?? null

  const openDir = async (zid: string | null | undefined) => {
    if (!zid) return
    try {
      const r = await api.openResourceDir(zid)
      window.alert(`已在文件管理器中打开：\n${r.dir}`)
    } catch (e) {
      window.alert(`打开文件所在路径失败：${(e as Error).message}`)
    }
  }

  return (
    <div className="resource-panel">
      <div className="resource-list">
        {relatedResources.length > 0 && (
          <>
            <div className="section-title">与当前笔记相关</div>
            {relatedResources.map((r) => (
              <ResourceItem
                key={`rel-${r.zotero_id ?? r.title}`}
                title={r.title}
                meta={`相关度 ${r.score.toFixed(3)}${r.date ? ` · ${r.date}` : ''}`}
                active={activeZid === r.zotero_id}
                hasPdf={Boolean(r.dir)}
                onClick={() => r.zotero_id && openResourcePdf(r.zotero_id)}
                onOpenDir={() => void openDir(r.zotero_id)}
              />
            ))}
          </>
        )}
        <div className="section-title">Zotero 论文库（{resources.length}）</div>
        {resources.map((r) => (
          <ResourceItem
            key={`lib-${r.zid ?? r.title}`}
            title={r.title}
            meta={`${r.itype ?? ''}${r.ptitle ? ' · ' + r.ptitle : ''}${
              r.date ? ' · ' + r.date : ''
            }`}
            active={activeZid === r.zid}
            hasPdf={Boolean(r.dir)}
            onClick={() => r.zid && openResourcePdf(r.zid)}
            onOpenDir={() => void openDir(r.zid)}
          />
        ))}
      </div>
      <div className="resource-pdf">
        {pdfUrl ? (
          <iframe title="pdf" src={pdfUrl} />
        ) : currentResource && isResource(currentResource) ? (
          <ResourceMeta res={currentResource} />
        ) : (
          <div className="no-pdf">← 选择一篇论文查看 PDF 或访问 DOI/网页</div>
        )}
      </div>
    </div>
  )
}
