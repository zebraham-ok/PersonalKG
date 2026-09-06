import { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { useStore } from '../stores/useStore'
import { api } from '../services/api'
import MarkdownView from './MarkdownView'

function EditableTitle({ title }: { title: string }) {
  const { renameCurrent } = useStore()
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(title)
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setVal(title)
  }, [title])

  useEffect(() => {
    if (editing) {
      ref.current?.focus()
      ref.current?.select()
    }
  }, [editing])

  const save = async () => {
    const next = val.trim()
    if (next && next !== title) {
      await renameCurrent(next)
    }
    setEditing(false)
  }

  if (editing) {
    return (
      <input
        ref={ref}
        className="rename-input"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onBlur={() => void save()}
        onKeyDown={(e) => {
          if (e.key === 'Enter') void save()
          if (e.key === 'Escape') {
            setVal(title)
            setEditing(false)
          }
        }}
      />
    )
  }
  return (
    <h2 onDoubleClick={() => setEditing(true)} title="双击重命名">
      {title}
    </h2>
  )
}

function Stars({ n }: { n: number | null }) {
  if (!n) return null
  return <span className="stars">{'★'.repeat(n)}</span>
}

/** 添加主题：输入时从「已有主题 + 学科分类」做包含匹配给出候选，点击/回车添加 */
function SubjectAdder({
  existing,
  catalog,
  onAdd,
}: {
  existing: string[]
  catalog: string[]
  onAdd: (name: string) => void
}) {
  const [val, setVal] = useState('')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const query = val.trim()

  // 候选池：学科分类 + 已有主题，去重
  const pool = useMemo(() => {
    const seen = new Set<string>()
    const merged: string[] = []
    for (const s of [...catalog, ...existing]) {
      const t = s.trim()
      if (!t || seen.has(t)) continue
      seen.add(t)
      merged.push(t)
    }
    return merged
  }, [catalog, existing])

  // 包含匹配，过滤掉已关联的主题
  const matches = useMemo(() => {
    if (!query) return []
    const taken = new Set(existing)
    return pool.filter((s) => !taken.has(s) && s.includes(query)).slice(0, 30)
  }, [pool, query, existing])

  const canAddNew = query && !pool.includes(query) && !existing.includes(query)

  const commit = (name: string) => {
    onAdd(name)
    setVal('')
    setOpen(false)
  }

  const showDropdown = open && query && (matches.length > 0 || canAddNew)

  return (
    <div className="subject-adder" ref={wrapRef}>
      <input
        className="subject-input"
        value={val}
        placeholder="+ 主题"
        onChange={(e) => {
          setVal(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false)
            setVal('')
          } else if (e.key === 'Enter') {
            e.preventDefault()
            if (matches.length) commit(matches[0])
            else if (canAddNew) commit(query)
          }
        }}
      />
      {showDropdown && (
        <div className="subject-dropdown">
          {matches.map((s) => (
            <button key={s} className="subject-option" onClick={() => commit(s)}>
              {s}
            </button>
          ))}
          {canAddNew && (
            <button className="subject-option new" onClick={() => commit(query)}>
              + 添加「{query}」
            </button>
          )}
          {matches.length === 0 && !canAddNew && (
            <div className="subject-option empty">没有匹配项</div>
          )}
        </div>
      )}
    </div>
  )
}

export default function NoteView() {
  const {
    current,
    noteLoading,
    saveCurrent,
    setCurrentContent,
    indexing,
    deleteCurrent,
    reindexCurrent,
    removeCurrentSubject,
    addCurrentSubject,
    renameCurrent,
    subjectCatalog,
  } = useStore()
  const [editing, setEditing] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const previewRef = useRef<HTMLDivElement>(null)
  const exportWrapRef = useRef<HTMLDivElement>(null)
  const isSyncing = useRef(false)
  void renameCurrent

  // 点击菜单外部时关闭导出下拉
  useEffect(() => {
    if (!exportOpen) return
    const onDocClick = (e: MouseEvent) => {
      if (!exportWrapRef.current?.contains(e.target as Node)) setExportOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [exportOpen])

  // 切换笔记时退出编辑态
  useEffect(() => setEditing(false), [current?.md_path])

  // 编辑态下 textarea 与预览区滚动联动
  useEffect(() => {
    const ta = textareaRef.current
    // 真正可滚动的是 .note-preview 内部的 .markdown-body（外层 overflow:hidden）
    const pvBody = previewRef.current?.querySelector<HTMLElement>('.markdown-body')
    if (!ta || !pvBody || !editing) return

    const onTaScroll = () => {
      if (isSyncing.current) return
      isSyncing.current = true
      const ratio = ta.scrollTop / (ta.scrollHeight - ta.clientHeight || 1)
      pvBody.scrollTop = ratio * (pvBody.scrollHeight - pvBody.clientHeight || 1)
      requestAnimationFrame(() => (isSyncing.current = false))
    }
    const onPvScroll = () => {
      if (isSyncing.current) return
      isSyncing.current = true
      const ratio = pvBody.scrollTop / (pvBody.scrollHeight - pvBody.clientHeight || 1)
      ta.scrollTop = ratio * (ta.scrollHeight - ta.clientHeight || 1)
      requestAnimationFrame(() => (isSyncing.current = false))
    }

    ta.addEventListener('scroll', onTaScroll)
    pvBody.addEventListener('scroll', onPvScroll)
    return () => {
      ta.removeEventListener('scroll', onTaScroll)
      pvBody.removeEventListener('scroll', onPvScroll)
    }
  }, [editing, current?.md_path])

  // 仅保存到 Neo4j，不退出编辑态（Ctrl+S 快捷保存）
  const saveOnly = async () => {
    await saveCurrent()
  }

  // 保存并退出编辑态（「保存」按钮）
  const handleSave = async () => {
    await saveOnly()
    setEditing(false)
  }

  // 剪贴板粘贴图片：上传到笔记 assets 目录，并在光标处插入 md 引用
  const onPaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (!current) return
    const files = Array.from(e.clipboardData.items)
      .filter((it) => it.type.startsWith('image/'))
      .map((it) => it.getAsFile())
      .filter((f): f is File => Boolean(f))
    if (!files.length) return
    e.preventDefault()
    const ta = textareaRef.current
    let latest = current.content ?? ''
    let pos = ta ? ta.selectionStart : latest.length
    for (const f of files) {
      try {
        const res = await api.uploadNoteImage(current.md_path, f)
        const insert = `![${f.name ?? res.name}](${res.rel})`
        latest = latest.slice(0, pos) + insert + latest.slice(pos)
        pos += insert.length
      } catch (err) {
        window.alert(`图片上传失败：${(err as Error).message}`)
      }
    }
    if (latest !== (current.content ?? '')) setCurrentContent(latest)
  }

  if (noteLoading) return <div className="loading">加载中…</div>
  if (!current) return <div className="empty-hint">→ 从右侧选择一篇笔记</div>

  const onDelete = () => {
    if (window.confirm(`确定删除《${current.title}》？\n该笔记及其关联关系将不可恢复。`)) {
      void deleteCurrent()
    }
  }

  const safeTitle = () => (current.title || '未命名').replace(/[\\/:*?"<>|\s]+/g, '_')

  const onExportMd = async () => {
    try {
      const blob = await api.exportNote(current.md_path)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeTitle()}.md`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      window.alert(`导出失败：${(err as Error).message}`)
    }
  }

  const onExportPdf = async () => {
    if (!current) return
    if (!(current.content ?? '').trim()) {
      window.alert('笔记内容为空，无法导出 PDF')
      return
    }
    let root: Root | null = null
    let container: HTMLDivElement | null = null
    const prevTheme = document.documentElement.dataset.theme
    const nextFrame = () =>
      new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())))
    try {
      // html2canvas + jsPDF 直连（上一版已验证可正确输出白底黑字的完整文档）。
      // 分页改为：把 .markdown-body 的块级子元素按 A4 可用高度分组，
      // 每页只显示该组元素再截图，从根源避免图片/文字被页边截断。
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ])

      // 离屏渲染完整笔记：容器必须位于视口内（html2canvas 只捕捉视口元素），
      // 高 z-index 覆盖在应用之上，导出完成后立即移除
      container = document.createElement('div')
      container.className = 'pdf-export-root'
      container.style.position = 'fixed'
      container.style.top = '0'
      container.style.left = '0'
      container.style.width = '794px' // A4 宽度 @96dpi
      container.style.zIndex = '99999'
      container.style.backgroundColor = '#ffffff'
      container.style.boxSizing = 'border-box'
      container.style.padding = '45px 53px' // 约等于 jsPDF 上下 12mm、左右 14mm 页边距
      document.body.appendChild(container)
      root = createRoot(container)
      root.render(<MarkdownView mdPath={current.md_path} content={current.content ?? ''} />)

      // 等 React 渲染完成 + 图片加载完成（离屏 lazy 图片需强制 eager）
      await new Promise<void>((resolve, reject) => {
        let settled = false
        const done = (err?: unknown) => {
          if (!settled) {
            settled = true
            if (err) reject(err)
            else resolve()
          }
        }
        const check = () => {
          if (!container) return done(new Error('导出容器不存在'))
          const body = container.querySelector<HTMLElement>('.markdown-body')
          if (!body || body.children.length === 0 || container.offsetHeight < 10) {
            setTimeout(check, 100) // 渲染未完成，稍后重试
            return
          }
          const imgs = Array.from(body.querySelectorAll<HTMLImageElement>('img'))
          let pending = imgs.length
          if (pending === 0) return done()
          for (const img of imgs) {
            img.loading = 'eager'
            const onImg = () => {
              pending -= 1
              if (pending <= 0) done()
            }
            if (img.complete) onImg()
            else {
              img.onload = onImg
              img.onerror = onImg
            }
          }
        }
        setTimeout(check, 300)
        setTimeout(() => done(new Error('渲染超时（8s）')), 8000) // 兜底
      })

      // 强制亮色主题：暗色模式下 CSS 变量会解析成暗色值，
      // 导出期间临时把 data-theme 回落到 :root 默认亮色（结束后恢复）
      document.documentElement.dataset.theme = 'light'
      const body = container.querySelector<HTMLElement>('.markdown-body')
      if (!body) throw new Error('未找到笔记正文')
      body.style.overflow = 'visible'
      body.style.maxHeight = 'none'
      body.style.height = 'auto'
      body.style.padding = '0'
      body.style.backgroundColor = '#ffffff'
      body.style.color = '#1f2328'
      // 代码块固定深色底，统一改为浅色，保证白底黑字
      container.querySelectorAll<HTMLElement>('pre').forEach((pre) => {
        pre.style.backgroundColor = '#f6f8fa'
        pre.style.color = '#1f2328'
      })
      container.querySelectorAll<HTMLElement>('pre code').forEach((code) => {
        code.style.backgroundColor = 'transparent'
        code.style.color = '#1f2328'
      })
      // 超高图片限制最大高度，避免单独占一页仍被页底截断
      const usableH = 1123 - 90 // A4 高 1123px，扣除上下 45px 边距
      container.querySelectorAll<HTMLElement>('img').forEach((img) => {
        img.style.maxWidth = '100%'
        img.style.maxHeight = `${usableH - 24}px`
      })
      await document.fonts?.ready?.catch(() => undefined)
      await nextFrame() // 等待主题与样式重排生效

      // 把 .markdown-body 的直接块级子元素按累计高度分组
      const children = Array.from(body.children) as HTMLElement[]
      const outerH = (el: HTMLElement) => {
        const cs = window.getComputedStyle(el)
        const mt = parseFloat(cs.marginTop) || 0
        const mb = parseFloat(cs.marginBottom) || 0
        return el.getBoundingClientRect().height + mt + mb
      }
      const groups: HTMLElement[][] = []
      let cur: HTMLElement[] = []
      let curH = 0
      for (const el of children) {
        const h = outerH(el)
        if (h > usableH) {
          // 单个元素超高（如超长表格）：独立成页
          if (cur.length) {
            groups.push(cur)
            cur = []
            curH = 0
          }
          groups.push([el])
          continue
        }
        if (curH + h > usableH && cur.length) {
          groups.push(cur)
          cur = [el]
          curH = h
        } else {
          cur.push(el)
          curH += h
        }
      }
      if (cur.length) groups.push(cur)

      const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })
      for (let i = 0; i < groups.length; i++) {
        // 每页只显示本组元素，其余隐藏，容器高度恰好等于本页内容
        for (const el of children) {
          el.style.display = groups[i].includes(el) ? '' : 'none'
        }
        await nextFrame()
        const canvas = await html2canvas(container, {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          logging: false,
          scrollX: 0,
          scrollY: 0,
        })
        if (canvas.width < 100 || canvas.height < 100) {
          throw new Error(`第 ${i + 1} 页截图异常（${canvas.width}x${canvas.height}）`)
        }
        const imgData = canvas.toDataURL('image/jpeg', 0.95)
        if (i > 0) pdf.addPage()
        const mmPerPx = 210 / canvas.width // 页宽 210mm 对应整幅截图宽度
        let w = 210
        let h = canvas.height * mmPerPx
        if (h > 297) {
          // 兜底：万一某页内容超高，等比缩小避免溢出
          const k = 297 / h
          h = 297
          w = 210 * k
        }
        pdf.addImage(imgData, 'JPEG', (210 - w) / 2, 0, w, h)
      }
      pdf.save(`${safeTitle()}.pdf`)
    } catch (err) {
      window.alert(`PDF 导出失败：${(err as Error).message}`)
    } finally {
      root?.unmount()
      container?.remove()
      document.documentElement.dataset.theme = prevTheme
    }
  }

  return (
    <div className="note-view">
      <div className="note-toolbar">
        <div style={{ minWidth: 0 }}>
          <EditableTitle title={current.title} />
          <div className="meta">
            {current.type && <span className="tag">{current.type}</span>}
            <Stars n={current.stars} />
            {(current.subjects || []).map((s) => (
              <span key={s} className="tag subject-tag">
                {s}
                <button
                  className="chip-remove"
                  title="移除此主题"
                  onClick={() => {
                    if (window.confirm(`确定将《${current.title}》从「${s}」主题中移除？`)) {
                      void removeCurrentSubject(s)
                    }
                  }}
                >
                  ×
                </button>
              </span>
            ))}
            <SubjectAdder
              existing={current.subjects || []}
              catalog={subjectCatalog || []}
              onAdd={(n) => void addCurrentSubject(n)}
            />
            <span>{current.word_count ?? 0} 字</span>
            {current.source_docx && <span className="tag">源: {current.source_docx}</span>}
          </div>
        </div>
        <div className="toolbar-actions">
          {editing ? (
            <button
              className="primary"
              title="保存并退出编辑模式；Ctrl+S 可仅保存不退出"
              onClick={() => void handleSave()}
            >
              保存并退出
            </button>
          ) : (
            <>
              <button
                disabled={indexing}
                title="重新生成嵌入向量与主题关联"
                onClick={() => void reindexCurrent()}
              >
                {indexing ? '索引中…' : '索引'}
              </button>
              <div className="export-menu-wrap" ref={exportWrapRef}>
                <button
                  className={exportOpen ? 'active' : undefined}
                  title="导出"
                  onClick={() => setExportOpen((v) => !v)}
                >
                  导出
                </button>
                {exportOpen && (
                  <div className="export-menu">
                    <button
                      onClick={() => {
                        setExportOpen(false)
                        void onExportMd()
                      }}
                    >
                      导出 Markdown
                    </button>
                    <button
                      onClick={() => {
                        setExportOpen(false)
                        void onExportPdf()
                      }}
                    >
                      导出 PDF
                    </button>
                  </div>
                )}
              </div>
              <button onClick={() => setEditing(true)}>编辑</button>
              <button className="danger" onClick={onDelete}>
                删除
              </button>
            </>
          )}
        </div>
      </div>

      {editing ? (
        <div className="note-editor split">
          <textarea
            ref={textareaRef}
            value={current.content ?? ''}
            onChange={(e) => setCurrentContent(e.target.value)}
            onPaste={onPaste}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault()
                void saveOnly()
              }
            }}
            spellCheck={false}
            placeholder="支持直接粘贴图片（Ctrl+V），将自动上传并插入到光标处"
          />
          <div ref={previewRef} className="note-preview">
            <MarkdownView mdPath={current.md_path} content={current.content ?? ''} />
          </div>
        </div>
      ) : (
        <MarkdownView mdPath={current.md_path} content={current.content ?? ''} />
      )}
    </div>
  )
}
