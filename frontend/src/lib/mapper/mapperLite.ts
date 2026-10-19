/**
 * Mapper-lite: on-device, offline QP mapping (BM25 + trade-vernacular lexicon).
 * Same algorithm as the server's QPMapper without the embedding re-rank, driven by the
 * statistics shipped in the QP pack (GET /packs/latest).
 */
import { phraseTokens, rawTokens, tokenize } from './tokenize'
import type { LexiconMatch, MappingResult, PackLexiconEntry, PCClaim, QP, QPPack } from './types'

export class MapperLite {
  private readonly pack: QPPack
  private readonly stopwords: Set<string>
  private readonly byFirst = new Map<string, PackLexiconEntry[]>()
  private readonly maxPhrase: number
  private readonly docSets: Set<string>[]
  private readonly qpById = new Map<string, QP>()
  private readonly generic = new Map<string, Set<string>>()
  private readonly hinglish: Set<string>

  constructor(pack: QPPack) {
    this.pack = pack
    this.stopwords = new Set(pack.tokenizer.stopwords)
    this.hinglish = new Set(pack.tokenizer.hinglish_markers)
    let max = 1
    for (const e of pack.lexicon) {
      if (!e.tokens.length) continue
      const list = this.byFirst.get(e.tokens[0]) ?? []
      list.push(e)
      this.byFirst.set(e.tokens[0], list)
      max = Math.max(max, e.tokens.length)
    }
    for (const list of this.byFirst.values()) list.sort((a, b) => b.tokens.length - a.tokens.length)
    this.maxPhrase = max
    this.docSets = pack.bm25.docs.map((d) => new Set(Object.keys(d.tf)))
    for (const qp of pack.qps) this.qpById.set(qp.id, qp)
    for (const [qp, toks] of Object.entries(pack.bm25.generic_tokens)) this.generic.set(qp, new Set(toks))
  }

  get version(): string {
    return this.pack.pack_version
  }

  /** Longest-match-first phrase matching; each token is consumed at most once. */
  matchLexicon(text: string): PackLexiconEntry[] {
    const toks = phraseTokens(text)
    const used = new Array<boolean>(toks.length).fill(false)
    const found: { i: number; e: PackLexiconEntry }[] = []
    for (let len = this.maxPhrase; len >= 1; len--) {
      for (let i = 0; i + len <= toks.length; i++) {
        if (used.slice(i, i + len).some(Boolean)) continue
        for (const e of this.byFirst.get(toks[i]) ?? []) {
          if (e.tokens.length !== len) continue
          let same = true
          for (let j = 0; j < len; j++) {
            if (toks[i + j] !== e.tokens[j]) {
              same = false
              break
            }
          }
          if (same) {
            found.push({ i, e })
            for (let j = i; j < i + len; j++) used[j] = true
            break
          }
        }
      }
    }
    return found.sort((a, b) => a.i - b.i).map((f) => f.e)
  }

  expandQuery(text: string): { tokens: string[]; matches: PackLexiconEntry[] } {
    const matches = this.matchLexicon(text)
    const tokens = tokenize(text, this.stopwords)
    for (const m of matches) tokens.push(...m.expand_tokens)
    return { tokens, matches }
  }

  bm25Scores(query: string[]): number[] {
    const { k1, b, avgdl, idf, docs } = this.pack.bm25
    const scores = new Array<number>(docs.length).fill(0)
    for (const q of query) {
      const w = idf[q] ?? 0
      if (!w) continue
      docs.forEach((d, i) => {
        const f = d.tf[q] ?? 0
        // same association as rank_bm25: idf * (f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl)))
        if (f) scores[i] += w * ((f * (k1 + 1)) / (f + k1 * (1 - b + (b * d.len) / avgdl)))
      })
    }
    return scores
  }

  claimsFor(qpId: string, queryTokens: string[]): PCClaim[] {
    const qp = this.qpById.get(qpId)
    if (!qp) return []
    const generic = this.generic.get(qpId) ?? new Set<string>()
    const q = new Set(queryTokens.filter((t) => !generic.has(t)))
    const nosTerms = this.pack.claims.nos_terms[qpId] ?? {}
    const claims: PCClaim[] = []
    for (const nos of qp.nos) {
      const nosHits = (nosTerms[nos.id] ?? []).filter((t) => q.has(t)).sort()
      for (const pc of nos.pcs) {
        const pcHits = nosHits.length ? (this.pack.claims.pc_tokens[pc.id] ?? []).filter((t) => q.has(t)).sort() : []
        const strength = pcHits.length ? 'strong' : nosHits.length ? 'weak' : 'none'
        claims.push({
          pc_id: pc.id,
          nos_id: nos.id,
          code: pc.code,
          claimed: strength !== 'none',
          strength,
          matched_terms: [...new Set([...pcHits, ...nosHits])].sort(),
        })
      }
    }
    return claims
  }

  map(narrative: string, topN = 3): MappingResult {
    const { tokens, matches } = this.expandQuery(narrative)
    const bm25 = this.bm25Scores(tokens)
    const max = Math.max(0, ...bm25)
    const norm = bm25.map((s) => (max > 0 ? s / max : 0))
    const order = norm.map((_, i) => i).sort((a, b) => norm[b] - norm[a] || a - b)
    const noMatch = max <= 0
    const { top_k_softmax: k, softmax_temperature: T } = this.pack.bm25
    const window = order.slice(0, k).map((i) => norm[i])
    const conf = noMatch ? [] : softmax(window, T)
    const idf = this.pack.bm25.idf
    const top = order.slice(0, topN).map((i, rank) => {
      const qpId = this.pack.bm25.docs[i].qp_id
      const qp = this.qpById.get(qpId)!
      const matched = [...new Set(tokens.filter((t) => this.docSets[i].has(t)))]
        .sort((a, b) => (idf[b] ?? 0) - (idf[a] ?? 0) || (a < b ? -1 : a > b ? 1 : 0))
        .slice(0, 10)
      return {
        rank: rank + 1,
        qp_id: qpId,
        title: qp.title,
        title_hi: qp.title_hi,
        sector: qp.sector,
        nsqf_level: qp.nsqf_level,
        source_kind: qp.source_kind,
        score: round4(norm[i]),
        bm25: round4(bm25[i]),
        cosine: null,
        confidence: rank < conf.length ? round4(conf[rank]) : 0,
        matched_terms: matched,
      }
    })
    const lexicon_matches: LexiconMatch[] = matches.map((m) => ({
      term: m.term,
      canonical: m.canonical,
      category: m.category,
      source: m.source,
    }))
    const claims: Record<string, PCClaim[]> = {}
    for (const t of top) claims[t.qp_id] = this.claimsFor(t.qp_id, tokens)
    return {
      engine: 'mapper-lite',
      no_match: noMatch,
      language_detected: detectLanguage(narrative, this.pack.tokenizer.devanagari_range, this.hinglish),
      query_terms: [...new Set(tokens)].sort(),
      lexicon_matches,
      top,
      claims,
      lexicon_version: this.pack.lexicon_version,
    }
  }
}

export function softmax(xs: number[], temperature: number): number[] {
  if (!xs.length) return []
  const m = Math.max(...xs)
  const exps = xs.map((x) => Math.exp((x - m) / temperature))
  const s = exps.reduce((a, b) => a + b, 0)
  return exps.map((e) => e / s)
}

/** Mirror of backend detect_language: >30% Devanagari -> hi; >=2 Hinglish stopwords -> hinglish. */
export function detectLanguage(text: string, range: [number, number], hinglish: Set<string>): string {
  const chars = [...text].filter((c) => !/\s/.test(c))
  if (!chars.length) return 'en'
  const dev = chars.filter((c) => {
    const cp = c.codePointAt(0) ?? 0
    return cp >= range[0] && cp <= range[1]
  }).length
  if (dev / chars.length > 0.3) return 'hi'
  return rawTokens(text).filter((t) => hinglish.has(t)).length >= 2 ? 'hinglish' : 'en'
}

function round4(x: number): number {
  return Math.round(x * 10000) / 10000
}
