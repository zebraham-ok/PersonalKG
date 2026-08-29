import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { useStore } from '../stores/useStore'

const COLOR: Record<string, string> = {
  Note: '#3b82f6',
  Subject: '#8b5cf6',
  Resource: '#10b981',
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

export default function KnowledgeGraph() {
  const { graph, loadNote, openResourcePdf, setSubjectFilter } = useStore()
  const wrapRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)
  const [dark, setDark] = useState(
    () => document.documentElement.dataset.theme === 'dark',
  )

  useEffect(() => {
    const apply = () => setDark(document.documentElement.dataset.theme === 'dark')
    apply()
    const obs = new MutationObserver(apply)
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ch = echarts.init(el)
    chartRef.current = ch
    const ro = new ResizeObserver(() => ch.resize())
    ro.observe(el)
    return () => {
      ro.disconnect()
      ch.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const ch = chartRef.current
    if (!ch) return
    if (!graph || graph.nodes.length === 0) {
      ch.clear()
      return
    }
    ch.setOption(
      {
        backgroundColor: 'transparent',
        tooltip: {
          formatter: (p: unknown) => {
            const it = p as { dataType?: string; data?: { label?: string; relation?: string } }
            if (it.dataType === 'edge') return `关系：${it.data?.relation ?? ''}`
            return `节点：${it.data?.label ?? ''}`
          },
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            force: { repulsion: 240, edgeLength: [60, 150] },
            label: {
              show: true,
              position: 'right',
              fontSize: 11,
              color: dark ? '#cbd5e1' : '#4b5563',
              formatter: (p: unknown) => {
                const it = p as { data?: { label?: string } }
                return truncate(it.data?.label ?? '', 12)
              },
            },
            lineStyle: { color: dark ? '#4b5563' : '#b9c0cc', width: 1.2, curveness: 0.08 },
            emphasis: { focus: 'adjacency' },
            data: graph.nodes.map((n) => ({
              id: n.id,
              name: n.label,
              group: n.group,
              zid: n.zid ?? null,
              label: n.label,
              symbolSize: n.group === 'Note' ? 22 : n.group === 'Subject' ? 18 : 14,
              itemStyle: { color: COLOR[n.group] ?? '#999' },
            })),
            links: graph.links.map((l) => ({
              source: l.source,
              target: l.target,
              relation: l.relation,
            })),
          },
        ],
      },
      true,
    )
    ch.off('click')
    ch.on('click', (params: unknown) => {
      const p = params as {
        dataType?: string
        data?: { group?: string; id?: string; zid?: string | null }
      }
      if (p.dataType !== 'node' || !p.data) return
      const d = p.data
      if (d.group === 'Note' && d.id) void loadNote(d.id)
      else if (d.group === 'Resource' && d.zid) openResourcePdf(d.zid)
      else if (d.group === 'Subject' && d.id) setSubjectFilter(d.id)
    })

    // 力导向布局动画最多持续 4 秒后自动停止（force 仿真常不触发 finished，
    // 节点会一直运动、CPU 持续占用，页面看起来像"没加载完"）
    let timer = 0
    const stopAnimation = () => {
      window.clearTimeout(timer)
      ch.off('finished', stopAnimation)
      ch.setOption({ series: [{ force: { layoutAnimation: false } }] })
    }
    timer = window.setTimeout(stopAnimation, 4000)
    ch.on('finished', stopAnimation)
    return () => {
      window.clearTimeout(timer)
      ch.off('finished', stopAnimation)
    }
  }, [graph, dark, loadNote, openResourcePdf, setSubjectFilter])

  return (
    <div className="graph-wrap" ref={wrapRef}>
      <div className="graph-note">
        知识图谱：中心笔记 → 主题(ON) · 语义相近笔记/论文(VEC)
      </div>
    </div>
  )
}
