/**
 * Encrypted local evidence vault. Captured images are AES-GCM-256 encrypted with a
 * NON-EXTRACTABLE device key before they touch IndexedDB, and the ciphertext is wiped
 * once the packet has synced (only metadata stays on the device).
 */
import { db, type VaultEntry } from './db'

const KEY = 'vault.key'

async function vaultKey(): Promise<CryptoKey> {
  const stored = (await db.kv.get(KEY))?.value as CryptoKey | undefined
  if (stored) return stored
  const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
  await db.kv.put({ key: KEY, value: key })
  return key
}

export async function vaultPut(meta: Omit<VaultEntry, 'id' | 'iv' | 'ciphertext' | 'createdAt'>, data: ArrayBuffer): Promise<number> {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await vaultKey(), data)
  return db.vault.add({ ...meta, iv, ciphertext, createdAt: Date.now() })
}

export async function vaultGet(id: number): Promise<{ entry: VaultEntry; data: ArrayBuffer } | null> {
  const entry = await db.vault.get(id)
  if (!entry?.ciphertext) return null
  const data = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: entry.iv as Uint8Array<ArrayBuffer> }, await vaultKey(), entry.ciphertext)
  return { entry, data }
}

/** After a successful sync: drop the ciphertext, keep the metadata. */
export async function vaultWipe(id: number): Promise<void> {
  await db.vault.update(id, { ciphertext: null, syncedAt: Date.now() })
}
