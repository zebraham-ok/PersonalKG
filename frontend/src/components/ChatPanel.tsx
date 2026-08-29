import { useEffect, useRef, useState } from 'react'
import { useStore } from '../stores/useStore'
import NoteLinkify from './NoteLinkify'

const SHORTCUTS: Record<string, string> = {
  '/总结': '请用一段话总结这篇笔记的核心论点、结构与关键证据。',
  '/要点': '请列出这篇笔记的 3-5 个核心要点，逐条简要说明。',
  '/联系': '这篇笔记与哪些现实议题或理论概念有关？请给出你的分析。',
  '/批判': '请批判性审视这篇笔记的论证：有哪些弱点、遗漏或可反驳之处？',
}

const MODELS: { id: string; label: string }[] = [
  { id: 'deepseek-v4-pro-0813', label: 'DeepSeek V4 Pro（默认）' },
  { id: 'deepseek-v4-flash-0731', label: 'DeepSeek V4 Flash' },
  { id: 'qwen-plus', label: 'Qwen Plus' },
  { id: 'qwen3-max', label: 'Qwen3 Max' },
  { id: 'gpt-5.1', label: 'GPT-5.1' },
  { id: 'gpt-4o', label: 'GPT-4o' },
]

const DEFAULT_MODEL = 'deepseek-v4-pro-0813'

function loadOpt(key: string, def: boolean): boolean {
  const v = localStorage.getItem(key)
  return v === null ? def : v === '1'
}

export default function ChatPanel() {
  const { currentPath, chatMsgs, chatBusy, sendChat, clearChat } = useStore()
  const [input, setInput] = useState('')
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const [model, setModel] = useState(() => {
    const saved = localStorage.getItem('kb.chatModel')
    return saved && MODELS.some((m) => m.id === saved) ? saved : DEFAULT_MODEL
  })
  // 三个上下文开关（本地记忆）
  const [useNote, setUseNote] = useState(() => loadOpt('kb.chatUseNote', true))
  const [usePdf, setUsePdf] = useState(() => loadOpt('kb.chatUsePdf', false))
  const [rag, setRag] = useState(() => loadOpt('kb.chatRag', false))
  const bottomRef = useRef<HTMLDivElement>(null)

  const saveOpt = (key: string, v: boolean) => localStorage.setItem(key, v ? '1' : '0')

  const selectModel = (m: string) => {
    setModel(m)
    localStorage.setItem('kb.chatModel', m)
  }

  const lastMsg = chatMsgs[chatMsgs.length - 1]
  const waitingFirst = chatBusy && (!lastMsg || lastMsg.role !== 'assistant' || !lastMsg.content)

  useEffect(() => {
    // 仅在用户接近底部时自动跟随滚动，避免打断向上查看历史
    const el = bottomRef.current
    const parent = el?.parentElement
    if (!el || !parent) return
    const nearBottom = parent.scrollHeight - parent.scrollTop - parent.clientHeight < 40
    if (nearBottom) el.scrollIntoView({ behavior: 'smooth' })
  }, [chatMsgs, chatBusy])

  const send = async (raw?: string) => {
    const text = (raw ?? input).trim()
    if (!text || !currentPath || chatBusy) return
    const message = SHORTCUTS[text] ?? text
    setInput('')
    await sendChat(message, { model, useNote, usePdf, rag })
  }

  const copyMsg = async (content: string, i: number) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIdx(i)
      setTimeout(() => setCopiedIdx((c) => (c === i ? null : c)), 1500)
    } catch {
      window.alert('复制失败，请手动选择文本复制')
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-msgs">
        <div className="chat-head">
          <span className="chat-head-title">AI 对话</span>
          {chatMsgs.length > 0 && (
            <button
              className="clear-chat-btn"
              title="清空当前对话记录（不影响笔记与知识库）"
              onClick={() => {
                if (window.confirm('确定要清空当前对话吗？')) clearChat()
              }}
            >
              清空对话
            </button>
          )}
        </div>
        {chatMsgs.length === 0 && (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '4px 2px' }}>
            基于当前笔记提问。可勾选「引入 PDF」「全库 RAG」扩展上下文。试试快捷指令：
          </div>
        )}
        {chatMsgs.map((m, i) => (
          <div key={i} className={`msg-row ${m.role}`}>
            <div className={`msg ${m.role}`}>
              {m.role === 'assistant' ? <NoteLinkify text={m.content} /> : m.content}
            </div>
            {m.role === 'assistant' && (
              <button
                className="copy-btn"
                title="复制这段回复"
                onClick={() => void copyMsg(m.content, i)}
              >
                {copiedIdx === i ? '已复制 ✓' : '复制'}
              </button>
            )}
          </div>
        ))}
        {waitingFirst && (
          <div className="msg assistant">
            <span className="thinking-hint">思考中…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="chat-toolbar">
        <select
          className="model-select"
          value={model}
          title="选择 AI 模型"
          onChange={(e) => selectModel(e.target.value)}
        >
          {MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
        <div className="chat-opts">
          <label className="opt" title="将当前笔记的标题与正文发给 AI">
            <input
              type="checkbox"
              checked={useNote}
              onChange={(e) => {
                setUseNote(e.target.checked)
                saveOpt('kb.chatUseNote', e.target.checked)
              }}
            />
            笔记
          </label>
          <label
            className="opt"
            title="将当前打开的 PDF 文本发给 AI（需先在资源面板打开一篇论文）"
          >
            <input
              type="checkbox"
              checked={usePdf}
              onChange={(e) => {
                setUsePdf(e.target.checked)
                saveOpt('kb.chatUsePdf', e.target.checked)
              }}
            />
            PDF
          </label>
          <label className="opt" title="从全库按语义相似度召回相关知识片段，供 AI 系统性回答">
            <input
              type="checkbox"
              checked={rag}
              onChange={(e) => {
                setRag(e.target.checked)
                saveOpt('kb.chatRag', e.target.checked)
              }}
            />
            RAG
          </label>
        </div>
      </div>
      <div className="chat-input">
        <textarea
          value={input}
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
        />
        <button className="primary" disabled={chatBusy} onClick={() => void send()}>
          发送
        </button>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 6,
          padding: '0 12px 8px',
          flexWrap: 'wrap',
        }}
      >
        {Object.keys(SHORTCUTS).map((k) => (
          <span
            key={k}
            className="chip"
            style={{ fontSize: 11, padding: '2px 8px' }}
            onClick={() => void send(k)}
          >
            {k}
          </span>
        ))}
      </div>
    </div>
  )
}
