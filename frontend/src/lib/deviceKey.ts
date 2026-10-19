/**
 * Per-device ECDSA P-256 signing identity.
 * The private key is generated NON-EXTRACTABLE inside WebCrypto and stored as a CryptoKey
 * object in IndexedDB: it can sign, but its bytes can never be read or exported.
 * Only the public key (SPKI) is sent to the server.
 */
import { db, newClientId } from './db'

export interface DeviceIdentity {
  deviceId: string
  keyPair: CryptoKeyPair
}

const KEY = 'device.identity'

export async function getDeviceIdentity(): Promise<DeviceIdentity> {
  const stored = (await db.kv.get(KEY))?.value as DeviceIdentity | undefined
  if (stored?.keyPair?.privateKey) return stored
  const keyPair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify'])
  const identity = { deviceId: newClientId('dev').slice(0, 40), keyPair }
  await db.kv.put({ key: KEY, value: identity })
  return identity
}

export function toBase64(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(s)
}

export function fromBase64(b64: string): Uint8Array {
  const s = atob(b64)
  const out = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i)
  return out
}

export async function publicKeySpki(identity: DeviceIdentity): Promise<string> {
  return toBase64(await crypto.subtle.exportKey('spki', identity.keyPair.publicKey))
}

/** ECDSA(SHA-256) signature in WebCrypto's raw r||s form (64 bytes), base64. */
export async function signText(identity: DeviceIdentity, text: string): Promise<string> {
  const sig = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    identity.keyPair.privateKey,
    new TextEncoder().encode(text),
  )
  return toBase64(sig)
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', data))
  return [...digest].map((b) => b.toString(16).padStart(2, '0')).join('')
}
