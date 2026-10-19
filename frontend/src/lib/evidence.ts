/**
 * Seal a capture into a signed, encrypted evidence packet and queue it for sync.
 *   image bytes -> SHA-256 -> packet {assessment, shot, hash, time, GPS, device, challenge code}
 *   -> canonical string -> ECDSA P-256 signature (non-extractable device key)
 *   -> image AES-GCM encrypted into the vault -> outbox
 * `canonicalPacket` must stay byte-identical with backend/app/services/signing.py.
 */
import { api } from './api'
import { db, newClientId } from './db'
import { getDeviceIdentity, publicKeySpki, sha256Hex, signText } from './deviceKey'
import type { QcResult } from './imageQc'
import { enqueue, flush, registerHandler } from './sync'
import { vaultGet, vaultPut, vaultWipe } from './vault'

export type Shot = 'process' | 'product' | 'person'

export interface Packet {
  v: 'v1'
  assessment_id: number
  shot: Shot
  sha256: string
  captured_at: string
  device_id: string
  challenge_code: string
  gps: { lat: number; lon: number; accuracy?: number } | null
  qc: { ok: boolean; issues: string[] } | null
  source: 'camera' | 'upload' | 'simulated'
  client_id: string
}

const coord = (v: number | undefined) => (v === undefined || v === null ? '' : v.toFixed(6))

export function canonicalPacket(p: Pick<Packet, 'assessment_id' | 'shot' | 'sha256' | 'captured_at' | 'device_id' | 'challenge_code' | 'gps'>): string {
  return [
    'v1',
    String(Math.trunc(p.assessment_id)),
    p.shot,
    p.sha256.toLowerCase(),
    p.captured_at,
    p.device_id,
    p.challenge_code,
    coord(p.gps?.lat),
    coord(p.gps?.lon),
  ].join('|')
}

/** Best-effort GPS fix (permission may be denied, or there may be no fix indoors). */
export function currentPosition(timeoutMs = 5000): Promise<Packet['gps']> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) return Promise.resolve(null)
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      // Round to 6 decimals before signing so Python's '.6f' and JS toFixed(6) agree exactly.
      (pos) =>
        resolve({
          lat: Number(pos.coords.latitude.toFixed(6)),
          lon: Number(pos.coords.longitude.toFixed(6)),
          accuracy: Math.round(pos.coords.accuracy),
        }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    )
  })
}

/** Register this device's public key once per user (queued, so it works offline too). */
export async function ensureDeviceRegistered(username: string): Promise<void> {
  const flag = `device.registered.${username}`
  if ((await db.kv.get(flag))?.value) return
  const id = await getDeviceIdentity()
  await enqueue(
    'device',
    { device_id: id.deviceId, public_key_spki: await publicKeySpki(id), label: navigator.userAgent.slice(0, 120), username },
    `device-${id.deviceId}-${username}`,
  )
}

export interface SealedCapture {
  vaultId: number
  packet: Packet
  signature: string
}

export async function sealCapture(input: {
  username: string
  assessmentId: number
  shot: Shot
  blob: Blob
  challengeCode: string
  qc: QcResult | null
  source: Packet['source']
  gps?: Packet['gps']
}): Promise<SealedCapture> {
  await ensureDeviceRegistered(input.username)
  const identity = await getDeviceIdentity()
  const data = await input.blob.arrayBuffer()
  const packet: Packet = {
    v: 'v1',
    assessment_id: input.assessmentId,
    shot: input.shot,
    sha256: await sha256Hex(data),
    captured_at: new Date().toISOString(),
    device_id: identity.deviceId,
    challenge_code: input.challengeCode,
    gps: input.gps === undefined ? await currentPosition() : input.gps,
    qc: input.qc ? { ok: input.qc.ok, issues: [...input.qc.issues] } : null,
    source: input.source,
    client_id: newClientId('ev'),
  }
  const signature = await signText(identity, canonicalPacket(packet))
  const vaultId = await vaultPut(
    { assessmentId: input.assessmentId, shot: input.shot, sha256: packet.sha256, mime: input.blob.type || 'image/jpeg' },
    data,
  )
  await enqueue('evidence', { vaultId, packet: { ...packet }, signature }, packet.client_id)
  void flush()
  return { vaultId, packet, signature }
}

registerHandler('device', async (item) => {
  const p = item.payload as { device_id: string; public_key_spki: string; label: string; username: string }
  await api('/devices', { body: { device_id: p.device_id, public_key_spki: p.public_key_spki, label: p.label } })
  await db.kv.put({ key: `device.registered.${p.username}`, value: true })
})

registerHandler('evidence', async (item) => {
  const { vaultId, packet, signature } = item.payload as { vaultId: number; packet: Packet; signature: string }
  const stored = await vaultGet(vaultId)
  if (!stored) return // already synced and wiped
  const form = new FormData()
  form.append('packet', JSON.stringify(packet))
  form.append('signature', signature)
  form.append('file', new Blob([stored.data], { type: stored.entry.mime }), `${packet.shot}.jpg`)
  await api(`/assessments/${packet.assessment_id}/evidence`, { body: form })
  await vaultWipe(vaultId)
})
