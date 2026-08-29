export interface NoteSummary {
  md_path: string
  title: string
  source_docx: string | null
  created: string | null
  stars: number | null
  type: string | null
  keywords: string[] | null
  word_count: number | null
  indexed_at: string | null
  subjects: string[]
}

export interface Note extends NoteSummary {
  content: string
}

export interface RelatedNote {
  md_path: string
  title: string
  stars: number | null
  type: string | null
  reason: string
  score: number
}

export interface RelatedResource {
  title: string
  score: number
  zotero_id: string | null
  dir: string | null
  date: string | null
}

export interface Resource {
  title: string
  keywords: string[] | null
  abstract: string
  zid: string | null
  dir: string
  doi: string
  date: string
  authors: string[] | null
  itype: string
  ckey: string
  url: string
  ptitle: string
  coll: string
  subjects: string[]
}

export interface NoteHit {
  md_path: string
  title: string
  type: string | null
  stars: number | null
  score: number
}

export interface ResourceHit {
  title: string
  zotero_id: string | null
  dir: string | null
  date: string | null
  score: number
}

export interface GraphNode {
  id: string
  label: string
  group: 'Note' | 'Subject' | 'Resource'
  stars?: number | null
  type?: string | null
  zid?: string | null
  score?: number
}

export interface GraphLink {
  source: string
  target: string
  relation: string
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

export interface Stats {
  notes?: number
  resources?: number
  subjects?: number
  [k: string]: unknown
}
