import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import seedPack from '../../public/packs/seed-pack.json'
import { ICON_CARDS } from './cards'
import { db } from './db'
import { loadPack, resetPackCache } from './pack'
import { flush } from './sync'
import { confirmQualification, submitDeclaration } from './worker'

const SERVER_MAPPING = {
  engine: 'bm25+lexicon',
  no_match: false,
  top: [{ rank: 1, qp_id: 'QG-4.5-AU-01811-2024-V1-ASDC', confidence: 0.9 }],
  claims: {},
  lexicon_matches: [],
  query_terms: [],
  lexicon_version: 'x',
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

function fakeServer(opts: { online: boolean }) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/packs/seed-pack.json')) return json(seedPack)
    if (!opts.online) throw new TypeError('Failed to fetch')
    calls.push(`${init?.method ?? 'GET'} ${url.replace(/^https?:\/\/[^/]+/, '')}`)
    if (url.endsWith('/map')) return json(SERVER_MAPPING)
    if (url.endsWith('/declarations')) return json({ id: 7 }, 201)
    if (url.endsWith('/assessments')) return json({ id: 42 }, 201)
    return json({}, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

beforeEach(async () => {
  await db.declarations.clear()
  await db.outbox.clear()
  await db.kv.clear()
  resetPackCache()
})
afterEach(() => vi.restoreAllMocks())

describe('local-first worker flow', () => {
  it('stores plain data even when given Vue reactive arrays (regression: DataCloneError)', async () => {
    fakeServer({ online: true })
    const state = reactive({ cards: ['co2', 'argon'] })
    const d = await submitDeclaration({ username: 'worker1', narrative: 'argon ka kaam', language: 'hi', inputMode: 'typed', cards: state.cards })
    await flush()
    const stored = await db.declarations.get(d.clientId)
    expect(stored?.cards).toEqual(['co2', 'argon'])
    expect(stored?.status).toBe('mapped')
  })

  it('offline: maps on-device instantly and queues; online: server result replaces it', async () => {
    const calls = fakeServer({ online: false })
    const d = await submitDeclaration({
      username: 'worker1',
      narrative: 'CO2 aur argon dono welding karta hoon, grinding karke finishing',
      language: 'hi',
      inputMode: 'typed',
      cards: [],
    })
    expect(d.provisional?.engine).toBe('mapper-lite')
    expect(d.provisional?.top[0].qp_id).toBe('QG-4.5-AU-01811-2024-V1-ASDC')
    await confirmQualification(d.clientId, 'QG-4.5-AU-01811-2024-V1-ASDC', ['ASC-N3124.PC1'])
    await flush()
    expect(await db.outbox.where('status').equals('pending').count()).toBe(2)
    expect(calls).toEqual([])

    // back online
    const online = fakeServer({ online: true })
    const r = await flush()
    expect(r.sent).toBe(2)
    expect(online).toEqual(['POST /declarations', 'POST /declarations/7/map', 'POST /assessments'])
    const stored = await db.declarations.get(d.clientId)
    expect(stored?.serverMapping?.engine).toBe('bm25+lexicon')
    expect(stored?.status).toBe('confirmed') // confirmation is not downgraded by the late mapping
    expect(stored?.assessmentId).toBe(42)
  })
})

describe('icon cards', () => {
  it('every card phrase is understood by the lexicon', async () => {
    fakeServer({ online: false })
    const { mapper } = await loadPack()
    for (const c of ICON_CARDS) {
      expect(mapper.matchLexicon(c.text).length, c.id).toBeGreaterThan(0)
      expect(mapper.map(c.text).no_match, c.id).toBe(false)
    }
  })
})
