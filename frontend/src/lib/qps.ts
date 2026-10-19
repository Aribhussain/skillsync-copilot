import { api } from './api'
import { db } from './db'
import type { QP } from './mapper/types'
import { qpFromPack } from './pack'

/** QP details: server first, then the local cache, then the offline QP pack. */
export async function loadQp(id: string): Promise<QP | null> {
  try {
    const qp = await api<QP>(`/qps/${encodeURIComponent(id)}`)
    await db.kv.put({ key: `qp.${id}`, value: qp })
    return qp
  } catch {
    const cachedQp = (await db.kv.get(`qp.${id}`))?.value as QP | undefined
    return cachedQp ?? (await qpFromPack(id)) ?? null
  }
}
