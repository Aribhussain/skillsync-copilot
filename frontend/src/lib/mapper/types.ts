/** Shape of GET /packs/latest (see backend/app/api/packs.py). */

export interface PCMarks {
  theory: number
  practical: number
  viva: number
}

export interface PC {
  id: string
  code: string
  text: string
  marks: PCMarks
  weight: number
  critical: boolean
  safety: boolean
  evidence_hint: 'observe' | 'photo' | 'viva' | 'declaration'
  ai_signal: string | null
  nos_id: string
  nos_title: string
  qp_id: string
}

export interface NOS {
  id: string
  title: string
  marks: PCMarks
  keywords: string[]
  bridge_module: { title: string; hours: number }
  pcs: PC[]
}

export interface QP {
  id: string
  title: string
  title_hi?: string
  sector: string
  awarding_body: string
  nsqf_level: number
  source_kind: string
  description: string
  keywords: string[]
  pass_percentage: number
  nos: NOS[]
}

export interface PackLexiconEntry {
  term: string
  tokens: string[]
  canonical: string
  category: string
  expand_tokens: string[]
  source: string
}

export interface ConsentNotice {
  version: string
  language: string
  title: string
  items: { purpose: string; text: string }[]
  rights: string
  sha256: string
}

export interface QPPack {
  pack_version: string
  generated_at?: string
  tokenizer: { stopwords: string[]; devanagari_range: [number, number]; hinglish_markers: string[] }
  bm25: {
    k1: number
    b: number
    avgdl: number
    idf: Record<string, number>
    docs: { qp_id: string; len: number; tf: Record<string, number> }[]
    softmax_temperature: number
    top_k_softmax: number
    generic_tokens: Record<string, string[]>
  }
  claims: {
    nos_terms: Record<string, Record<string, string[]>>
    pc_tokens: Record<string, string[]>
  }
  lexicon_version: string
  lexicon: PackLexiconEntry[]
  qps: QP[]
  consent_notices: Record<'en' | 'hi', ConsentNotice>
}

export interface MappedQP {
  rank: number
  qp_id: string
  title: string
  title_hi?: string
  sector: string
  nsqf_level: number
  source_kind: string
  score: number
  bm25: number
  cosine: number | null
  confidence: number
  matched_terms: string[]
}

export interface PCClaim {
  pc_id: string
  nos_id: string
  code: string
  claimed: boolean
  strength: 'strong' | 'weak' | 'none'
  matched_terms: string[]
}

export interface LexiconMatch {
  term: string
  canonical: string
  category: string
  source?: string
}

export interface MappingResult {
  engine: 'hybrid' | 'bm25+lexicon' | 'mapper-lite'
  no_match: boolean
  language_detected?: string
  query_terms: string[]
  lexicon_matches: LexiconMatch[]
  top: MappedQP[]
  claims: Record<string, PCClaim[]>
  lexicon_version: string
  embedding_note?: string
}
