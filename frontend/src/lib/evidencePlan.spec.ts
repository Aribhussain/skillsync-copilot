import { describe, expect, it } from 'vitest'

import pack from '../../public/packs/seed-pack.json'
import { planFor } from './evidencePlan'
import parity from './mapper/__fixtures__/parity.json'
import type { QPPack } from './mapper/types'

const qps = new Map((pack as unknown as QPPack).qps.map((q) => [q.id, q]))

describe('evidence plan parity with the server rules engine', () => {
  for (const p of parity.plans) {
    it(`${p.qp_id} (${p.claimed.length ? 'all claimed' : 'nothing claimed'})`, () => {
      const plan = planFor(qps.get(p.qp_id)!, p.claimed)
      const got = Object.fromEntries(Object.entries(plan).map(([id, d]) => [id, [d.route, d.locked, d.rule]]))
      expect(got).toEqual(p.routes)
    })
  }

  it('locks every critical and safety PC to live observation', () => {
    for (const qp of qps.values()) {
      const plan = planFor(qp, [])
      for (const nos of qp.nos)
        for (const pc of nos.pcs)
          if (pc.critical || pc.safety) expect(plan[pc.id]).toMatchObject({ route: 'observe', locked: true })
    }
  })
})
