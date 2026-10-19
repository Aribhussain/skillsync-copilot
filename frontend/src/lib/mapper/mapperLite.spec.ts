import { describe, expect, it } from 'vitest'

import pack from '../../../public/packs/seed-pack.json'
import parity from './__fixtures__/parity.json'
import { MapperLite } from './mapperLite'
import { phraseTokens, tokenize } from './tokenize'
import type { QPPack } from './types'

const mapper = new MapperLite(pack as unknown as QPPack)
const stop = new Set((pack as unknown as QPPack).tokenizer.stopwords)

describe('tokenizer (mirror of text_norm.py)', () => {
  it('keeps Devanagari words with matras intact and drops stopwords', () => {
    expect(tokenize('वेल्डिंग के बाद ग्राइंडर से घिसाई करता हूँ।', stop)).toEqual(['वेल्डिंग', 'ग्राइंडर', 'घिसाई'])
  })
  it('stems plurals but not "ss" endings', () => {
    expect(tokenize('joints pipes glass', stop)).toEqual(['joint', 'pipe', 'glass'])
  })
  it('keeps stopwords in phrase tokens', () => {
    expect(phraseTokens('argon ka kaam')).toEqual(['argon', 'ka', 'kaam'])
  })
})

describe('mapper-lite parity with the server mapper', () => {
  it('uses the same pack version as the fixture', () => {
    expect(mapper.version).toBe(parity.pack_version)
  })

  for (const c of parity.cases) {
    it(`matches python for: ${c.text.slice(0, 50) || '(empty)'}`, () => {
      const r = mapper.map(c.text, 3)
      expect(r.no_match).toBe(c.no_match)
      expect(r.top.map((t) => t.qp_id)).toEqual(c.top.map((t) => t.qp_id))
      r.top.forEach((t, i) => {
        expect(t.bm25).toBeCloseTo(c.top[i].bm25, 3)
        expect(t.confidence).toBeCloseTo(c.top[i].confidence, 3)
      })
      expect(r.lexicon_matches.map((m) => m.term)).toEqual(c.lexicon_terms)
      const claimed = r.claims[r.top[0].qp_id].filter((x) => x.claimed).map((x) => x.pc_id).sort()
      expect(claimed).toEqual(c.claimed_pc_ids)
    })
  }
})

describe('golden-path narrative offline', () => {
  it('ranks Welding first with GTAW claimed and FCAW not', () => {
    const r = mapper.map(
      'Main 6 saal se fabrication shop mein kaam karta hoon, CO2 aur argon dono welding karta hoon, plate aur pipe joint banata hoon, grinding karke finishing deta hoon',
    )
    expect(r.top[0].qp_id).toBe('QG-4.5-AU-01811-2024-V1-ASDC')
    expect(r.engine).toBe('mapper-lite')
    const claims = r.claims['QG-4.5-AU-01811-2024-V1-ASDC']
    expect(claims.some((c) => c.nos_id === 'ASC/N3124' && c.claimed)).toBe(true)
    expect(claims.some((c) => c.nos_id === 'ASC/N3123' && c.claimed)).toBe(false)
  })
})
