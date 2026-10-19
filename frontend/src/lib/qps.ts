import { api } from './api'
import { db } from './db'
import type { QP } from './mapper/types'

/** QP details from the server, cached locally for later offline use. */
export async function loadQp(id: string): Promise<QP | null> {
  try {
    const qp = await api<QP>(`/qps/${encodeURIComponent(id)}`)
    await db.kv.put({ key: `qp.${id}`, value: qp })
    return qp
  } catch {
    return ((await db.kv.get(`qp.${id}`))?.value as QP | undefined) ?? null
  }
}
