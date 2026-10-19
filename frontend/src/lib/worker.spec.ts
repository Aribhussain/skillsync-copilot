import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

import { db } from './db'
import { submitDeclaration } from './worker'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

beforeEach(async () => {
  await db.declarations.clear()
  await db.outbox.clear()
})
afterEach(() => vi.restoreAllMocks())

describe('submitDeclaration', () => {
  it('stores plain data even when given Vue reactive arrays (regression: DataCloneError)', async () => {
    const mapping = { engine: 'bm25+lexicon', no_match: false, top: [], claims: {}, lexicon_matches: [], query_terms: [], lexicon_version: 'x' }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => (String(url).endsWith('/map') ? jsonResponse(mapping) : jsonResponse({ id: 7 }, 201))),
    )
    const state = reactive({ cards: ['co2', 'argon'] })
    const d = await submitDeclaration({
      username: 'worker1',
      narrative: 'argon ka kaam',
      language: 'hi',
      inputMode: 'typed',
      cards: state.cards,
    })
    const stored = await db.declarations.get(d.clientId)
    expect(stored?.status).toBe('mapped')
    expect(stored?.serverId).toBe(7)
    expect(stored?.cards).toEqual(['co2', 'argon'])
  })
})
