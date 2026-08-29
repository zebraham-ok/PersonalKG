import { useState } from 'react'
import { useStore } from '../stores/useStore'

export default function NewNoteModal({ onClose }: { onClose: () => void }) {
  const { subjects, createNote } = useStore()
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const onCreate = async () => {
    if (!title.trim()) {
      setErr('请输入标题')
      return
    }
    setBusy(true)
    setErr('')
    try {
      await createNote(title.trim(), subject || null)
      onClose()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>新建笔记</h3>
        <label htmlFor="nn-title">标题</label>
        <input
          id="nn-title"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void onCreate()}
          placeholder="笔记标题"
        />
        <label htmlFor="nn-subject">主题（可选）</label>
        <select
          id="nn-subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
        >
          <option value="">（未指定）</option>
          {subjects.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {err && <div className="form-err">{err}</div>}
        <div className="modal-actions">
          <button onClick={onClose}>取消</button>
          <button className="primary" disabled={busy} onClick={() => void onCreate()}>
            {busy ? '创建中…' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
