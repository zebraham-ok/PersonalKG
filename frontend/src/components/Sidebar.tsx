import { useState } from 'react'
import { useStore } from '../stores/useStore'
import Recommendations from './Recommendations'
import SubjectSelectorModal from './SubjectSelectorModal'
import type { NoteHit, NoteSummary, ResourceHit } from '../types'

function Stars({ n }: { n: number | null }) {
  if (!n) return null
  return <span className="stars">{'★'.repeat(n)}</span>
}

interface CtxMenu {
  x: number
  y: number
  name: string
}

export default function Sidebar() {
  const [view, setView] = useState<'subjects' | 'similar' | 'recent'>('recent')
  const [showSelector, setShowSelector] = useState(false)
  const [ctx, setCtx] = useState<CtxMenu | null>(null)
  const {
    notes,
    allNotes,
    subjects,
    subjectCounts,
    subjectFilter,
    setSubjectFilter,
    loadNote,
    currentPath,
    searchMode,
    searchLabel,
    searchResults,
    clearSearch,
    openResourcePdf,
    deleteSubject,
  } = useStore()

  const selectSubject = (s: string | null) => {
    setSubjectFilter(s)
    setShowSelector(false)
  }

  const confirmAndDelete = (withContent: boolean) => {
    if (!ctx) return
    const { name } = ctx
    const cnt = subjectCounts[name] ?? 0
    const ok = withContent
      ? window.confirm(`删除主题「${name}」及其下全部内容？\n\n将删除 ${cnt} 篇笔记及其本地文件，此操作不可恢复！`)
      : window.confirm(`删除主题「${name}」？\n\n${cnt} 篇笔记将保留，但移除该主题；若笔记因此失去全部主题，将自动 AI 重新分配。`)
    setCtx(null)
    if (ok) void deleteSubject(name, withContent)
  }

  const totalCount = Object.values(subjectCounts).reduce((a, b) => a + b, 0)

  // 「近期编辑」视图：全库按最近编辑（indexed_at）倒序取 20 条，不受主题过滤影响
  const recentNotes = [...allNotes]
    .sort((a, b) => (b.indexed_at ?? '').localeCompare(a.indexed_at ?? ''))
    .slice(0, 20)

  const renderNote = (n: NoteSummary, showTime = false) => (
    <div
      key={n.md_path}
      className={`note-item ${n.md_path === currentPath ? 'active' : ''}`}
      onClick={() => void loadNote(n.md_path)}
    >
      <div className="t">{n.title || n.md_path}</div>
      <div className="m">
        <Stars n={n.stars} />
        {n.type && <span className="tag">{n.type}</span>}
        {(n.subjects || []).slice(0, 2).map((s) => (
          <span key={s} className="tag">
            {s}
          </span>
        ))}
        {showTime && n.indexed_at ? <span className="tag">{n.indexed_at}</span> : null}
        {n.word_count ? <span>{n.word_count} 字</span> : null}
      </div>
    </div>
  )

  return (
    <>
      <div className="panel-head">
        <span>{searchMode ? `搜索结果「${useStore.getState().searchQuery}」` : '笔记'}</span>
        {searchMode && (
          <button style={{ fontSize: 11, padding: '2px 8px' }} onClick={clearSearch}>
            清除
          </button>
        )}
      </div>

      {!searchMode && (
        <div className="left-tabs">
          <button
            className={`tab-btn ${view === 'subjects' ? 'active' : ''}`}
            onClick={() => setView('subjects')}
          >
            主题视图
          </button>
          <button
            className={`tab-btn ${view === 'similar' ? 'active' : ''}`}
            onClick={() => setView('similar')}
          >
            相似度视图
          </button>
          <button
            className={`tab-btn ${view === 'recent' ? 'active' : ''}`}
            onClick={() => setView('recent')}
          >
            近期编辑
          </button>
        </div>
      )}

      {view === 'similar' && !searchMode ? (
        <Recommendations />
      ) : view === 'recent' && !searchMode ? (
        <div className="note-list">
          {recentNotes.length === 0 ? (
            <div className="empty-hint" style={{ padding: 40 }}>
              无笔记（请先导入或刷新）
            </div>
          ) : (
            recentNotes.map((n) => renderNote(n, true))
          )}
        </div>
      ) : (
        <>
          {!searchMode && (
            <div className="subject-chips">
              <span
                className={`chip ${subjectFilter === null ? 'active' : ''}`}
                title={totalCount > 0 ? `全部笔记（${totalCount} 篇）` : undefined}
                onClick={() => setSubjectFilter(null)}
              >
                全部
              </span>
              {subjects.map((s) => {
                const cnt = subjectCounts[s]
                return (
                  <span
                    key={s}
                    className={`chip ${subjectFilter === s ? 'active' : ''}`}
                    title={cnt != null ? `${s}（${cnt} 篇）` : s}
                    onClick={() => setSubjectFilter(s)}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      setCtx({ x: e.clientX, y: e.clientY, name: s })
                    }}
                  >
                    {s}
                  </span>
                )
              })}
            </div>
          )}

          <div className="note-list">
            {searchMode ? (
              searchResults.length === 0 ? (
                <div className="empty-hint" style={{ flex: 1, padding: 40 }}>
                  无结果
                </div>
              ) : (
                searchResults.map((r) =>
                  searchLabel === 'Note' ? (
                    <div
                      key={(r as NoteHit).md_path}
                      className={`note-item ${
                        (r as NoteHit).md_path === currentPath ? 'active' : ''
                      }`}
                      onClick={() => void loadNote((r as NoteHit).md_path)}
                    >
                      <div className="t">{(r as NoteHit).title}</div>
                      <div className="m">
                        {(r as NoteHit).type && <span className="tag">{(r as NoteHit).type}</span>}
                        <Stars n={(r as NoteHit).stars} />
                        <span className="tag">相关度 {(r as NoteHit).score.toFixed(3)}</span>
                      </div>
                    </div>
                  ) : (
                    <div
                      key={(r as ResourceHit).zotero_id ?? (r as ResourceHit).title}
                      className="note-item"
                      onClick={() =>
                        (r as ResourceHit).zotero_id &&
                        openResourcePdf((r as ResourceHit).zotero_id!)
                      }
                    >
                      <div className="t">{(r as ResourceHit).title}</div>
                      <div className="m">
                        {(r as ResourceHit).date && (
                          <span className="tag">{(r as ResourceHit).date}</span>
                        )}
                        <span className="tag">
                          相关度 {(r as ResourceHit).score.toFixed(3)}
                        </span>
                      </div>
                    </div>
                  ),
                )
              )
            ) : notes.length === 0 ? (
              <div className="empty-hint" style={{ padding: 40 }}>
                无笔记（请先导入或刷新）
              </div>
            ) : (
              notes.map((n) => renderNote(n))
            )}
          </div>
        </>
      )}

      {showSelector && (
        <SubjectSelectorModal
          subjects={subjects}
          subjectCounts={subjectCounts}
          active={subjectFilter}
          totalCount={totalCount}
          onSelect={selectSubject}
          onClose={() => setShowSelector(false)}
        />
      )}

      {view === 'subjects' && !searchMode && (
        <button
          className="subject-fab"
          title="展开全部主题"
          onClick={() => setShowSelector(true)}
        >
          ＋
        </button>
      )}

      {ctx && (
        <div
          className="ctx-backdrop"
          onClick={() => setCtx(null)}
          onContextMenu={(e) => {
            e.preventDefault()
            setCtx(null)
          }}
        >
          <div
            className="ctx-menu"
            style={{
              left: Math.min(ctx.x, window.innerWidth - 240),
              top: Math.min(ctx.y, window.innerHeight - 110),
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ctx-title" title={ctx.name}>
              {ctx.name}
            </div>
            <button className="ctx-item" onClick={() => confirmAndDelete(false)}>
              删除主题（保留笔记）
            </button>
            <button className="ctx-item danger" onClick={() => confirmAndDelete(true)}>
              删除主题及其全部内容
            </button>
          </div>
        </div>
      )}
    </>
  )
}
