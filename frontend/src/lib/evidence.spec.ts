import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { db } from './db'
import { fromBase64, getDeviceIdentity } from './deviceKey'
import { canonicalPacket, sealCapture } from './evidence'
import { flush } from './sync'
import { vaultGet } from './vault'

beforeEach(async () => {
  await db.outbox.clear()
  await db.vault.clear()
  await db.kv.clear()
})
afterEach(() => vi.restoreAllMocks())

describe('evidence packets', () => {
  it('canonical string matches the server (same literal as backend test_canonical_packet_is_stable)', () => {
    const p = {
      assessment_id: 7,
      shot: 'product' as const,
      sha256: 'AB'.repeat(32),
      captured_at: '2026-10-19T10:00:00.000Z',
      device_id: 'dev-1',
      challenge_code: 'QXW3AE',
      gps: { lat: 28.4, lon: 77.31 },
    }
    expect(canonicalPacket(p)).toBe(`v1|7|product|${'ab'.repeat(32)}|2026-10-19T10:00:00.000Z|dev-1|QXW3AE|28.400000|77.310000`)
    expect(canonicalPacket({ ...p, gps: null })).toMatch(/\|QXW3AE\|\|$/)
  })

  it('device private key is non-extractable and signatures verify (raw r||s, 64 bytes)', async () => {
    const id = await getDeviceIdentity()
    expect(id.keyPair.privateKey.extractable).toBe(false)
    await expect(crypto.subtle.exportKey('pkcs8', id.keyPair.privateKey)).rejects.toBeTruthy()
    const again = await getDeviceIdentity()
    expect(again.deviceId).toBe(id.deviceId) // persisted, not regenerated
  })

  it('seals: hash + signature + encrypted vault + outbox; ciphertext wiped after sync', async () => {
    const image = new Blob([new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8])], { type: 'image/jpeg' })
    const sealed = await sealCapture({
      username: 'assessor1',
      assessmentId: 12,
      shot: 'person',
      blob: image,
      challengeCode: 'QXW3AE',
      qc: null,
      source: 'simulated',
      gps: null,
    })
    expect(sealed.packet.sha256).toBe('66840dda154e8a113c31dd0ad32f7f3a366a80e8136979d8f5a101d3d29d6f72')
    expect(fromBase64(sealed.signature).length).toBe(64)

    // the signature verifies with the device's public key over the canonical string
    const id = await getDeviceIdentity()
    const ok = await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' },
      id.keyPair.publicKey,
      fromBase64(sealed.signature) as Uint8Array<ArrayBuffer>,
      new TextEncoder().encode(canonicalPacket(sealed.packet)),
    )
    expect(ok).toBe(true)

    // stored encrypted, not in plain text
    const entry = await db.vault.get(sealed.vaultId)
    expect(new Uint8Array(entry!.ciphertext!)).not.toEqual(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]))
    expect(new Uint8Array((await vaultGet(sealed.vaultId))!.data)).toEqual(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]))

    // queued: device registration first, then the evidence packet
    const kinds = (await db.outbox.orderBy('id').toArray()).map((i) => i.kind)
    expect(kinds).toEqual(['device', 'evidence'])

    // sealCapture already kicked off a flush with no network: let it finish first
    await flush()
    // sync: both requests succeed, ciphertext is wiped
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(String(url).replace(/^https?:\/\/[^/]+/, ''))
        return new Response(JSON.stringify({ ok: true }), { status: 201 })
      }),
    )
    await flush()
    expect(calls).toEqual(['/devices', '/assessments/12/evidence'])
    expect((await db.vault.get(sealed.vaultId))!.ciphertext).toBeNull()
  })
})
