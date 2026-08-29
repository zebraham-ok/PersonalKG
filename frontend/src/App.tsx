import { useEffect, useRef, useState } from 'react'
import { useStore } from './stores/useStore'
import TopBar from './components/TopBar'
import Sidebar from './components/Sidebar'
import NoteView from './components/NoteView'
import TabsBar from './components/TabsBar'
import ChatPanel from './components/ChatPanel'
import ResourcePanel from './components/ResourcePanel'
import KnowledgeGraph from './components/KnowledgeGraph'

export default function App() {
  const { init, toast, midTab, setMidTab } = useStore()
  const [leftW, setLeftW] = useState(() =>
    Number(localStorage.getItem('kb.leftW') ?? 300),
  )
  const [rightW, setRightW] = useState(() =>
    Number(localStorage.getItem('kb.rightW') ?? 340),
  )
  const [leftCollapsed, setLeftCollapsed] = useState(
    () => localStorage.getItem('kb.leftCollapsed') === '1',
  )
  const [rightCollapsed, setRightCollapsed] = useState(
    () => localStorage.getItem('kb.rightCollapsed') === '1',
  )
  const dragRef = useRef<{ side: 'l' | 'r'; startX: number; startW: number } | null>(
    null,
  )

  const toggleLeft = () => {
    setLeftCollapsed((c) => {
      localStorage.setItem('kb.leftCollapsed', c ? '0' : '1')
      return !c
    })
  }
  const toggleRight = () => {
    setRightCollapsed((c) => {
      localStorage.setItem('kb.rightCollapsed', c ? '0' : '1')
      return !c
    })
  }

  useEffect(() => {
    void init()
  }, [init])

  const startDrag = (side: 'l' | 'r') => (e: React.MouseEvent) => {
    dragRef.current = {
      side,
      startX: e.clientX,
      startW: side === 'l' ? leftW : rightW,
    }
    document.body.style.userSelect = 'none'
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const d = ev.clientX - dragRef.current.startX
      const w =
        dragRef.current.side === 'l'
          ? dragRef.current.startW + d
          : dragRef.current.startW - d
      const clamped = Math.min(Math.max(w, 200), 560)
      if (dragRef.current.side === 'l') {
        setLeftW(clamped)
        localStorage.setItem('kb.leftW', String(clamped))
      } else {
        setRightW(clamped)
        localStorage.setItem('kb.rightW', String(clamped))
      }
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.userSelect = ''
      dragRef.current = null
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return (
    <div className="app">
      <TopBar />
      <div className="body">
        <aside
          className={`col col-left ${leftCollapsed ? 'collapsed' : ''}`}
          style={{ width: leftCollapsed ? 0 : leftW, flex: 'none' }}
        >
          <div className="left-panel">
            <div className="mid-tabs">
              <button
                className={`tab-btn ${midTab === 'chat' ? 'active' : ''}`}
                onClick={() => setMidTab('chat')}
              >
                AI 对话
              </button>
              <button
                className={`tab-btn ${midTab === 'resource' ? 'active' : ''}`}
                onClick={() => setMidTab('resource')}
              >
                相关论文 / PDF
              </button>
            </div>
            {midTab === 'chat' ? <ChatPanel /> : <ResourcePanel />}
          </div>
        </aside>
        {!leftCollapsed && <div className="resize-handle" onMouseDown={startDrag('l')} />}

        <main className="col-mid">
          <TabsBar />
          <NoteView />
        </main>

        {!rightCollapsed && <div className="resize-handle" onMouseDown={startDrag('r')} />}

        <aside
          className={`col col-right ${rightCollapsed ? 'collapsed' : ''}`}
          style={{ width: rightCollapsed ? 0 : rightW, flex: 'none' }}
        >
          <div className="right-sec right-top">
            <Sidebar />
          </div>
          <div className="right-sec" style={{ flex: 1, minHeight: 220 }}>
            <KnowledgeGraph />
          </div>
        </aside>

        <button
          className="panel-toggle"
          style={{
            left: leftCollapsed ? 0 : leftW - 8,
            zIndex: 20,
          }}
          title={leftCollapsed ? '展开左栏' : '收起左栏'}
          onClick={toggleLeft}
        >
          {leftCollapsed ? '>' : '<'}
        </button>
        <button
          className="panel-toggle"
          style={{
            right: rightCollapsed ? 0 : rightW - 8,
            zIndex: 20,
          }}
          title={rightCollapsed ? '展开右栏' : '收起右栏'}
          onClick={toggleRight}
        >
          {rightCollapsed ? '<' : '>'}
        </button>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
