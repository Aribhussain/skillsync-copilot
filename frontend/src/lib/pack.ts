/**
 * QP pack management for offline use.
 * Priority: latest pack synced from the server (IndexedDB) -> seed pack bundled with the
 * PWA (/packs/seed-pack.json, precached by the service worker).
 */
import { api } from './api'
import { db } from './db'
import { MapperLite } from './mapper/mapperLite'
import type { QP, QPPack } from './mapper/types'

const KEY = 'qp_pack'
let cached: { pack: QPPack; mapper: MapperLite } | null = null

function use(pack: QPPack) {
  cached = { pack, mapper: new MapperLite(pack) }
  return cached
}

export async function loadPack(): Promise<{ pack: QPPack; mapper: MapperLite }> {
  if (cached) return cached
  const stored = (await db.kv.get(KEY))?.value as QPPack | undefined
  if (stored) return use(stored)
  const res = await fetch('/packs/seed-pack.json')
  if (!res.ok) throw new Error('No QP pack available offline')
  return use((await res.json()) as QPPack)
}

/** Sync-down: fetch a newer pack if the server has one. Returns true if updated. */
export async function refreshPack(): Promise<boolean> {
  const current = cached?.pack.pack_version ?? ((await db.kv.get(KEY))?.value as QPPack | undefined)?.pack_version
  const { pack_version } = await api<{ pack_version: string }>('/packs/version')
  if (pack_version === current) return false
  const pack = await api<QPPack>('/packs/latest')
  await db.kv.put({ key: KEY, value: pack })
  use(pack)
  return true
}

export async function qpFromPack(id: string): Promise<QP | undefined> {
  const { pack } = await loadPack()
  return pack.qps.find((q) => q.id === id)
}

export function resetPackCache(): void {
  cached = null
}
