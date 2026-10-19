/**
 * M3 evidence-plan rules engine. Mirror of backend/app/services/evidence_plan.py;
 * the parity test (evidencePlan.spec.ts) compares every QP against the server's output.
 *  1. critical or safety PC        -> observe (LOCKED: cannot be downgraded)
 *  2. evidence_hint photo          -> photo
 *  3. evidence_hint viva           -> viva
 *  4. evidence_hint declaration    -> declaration+spot-check if claimed, else viva
 *  5. otherwise                    -> observe
 */
import type { PC, QP } from './mapper/types'

export type Route = 'observe' | 'photo' | 'viva' | 'declaration+spot-check'
export type Rule = 'critical' | 'safety' | 'photo' | 'viva' | 'declaration_claimed' | 'declaration_unclaimed' | 'observe' | 'override'

export interface RouteDecision {
  route: Route
  locked: boolean
  rule: Rule
}

export function routeFor(pc: Pick<PC, 'critical' | 'safety' | 'evidence_hint'>, claimed: boolean): RouteDecision {
  if (pc.critical || pc.safety) return { route: 'observe', locked: true, rule: pc.critical ? 'critical' : 'safety' }
  switch (pc.evidence_hint) {
    case 'photo':
      return { route: 'photo', locked: false, rule: 'photo' }
    case 'viva':
      return { route: 'viva', locked: false, rule: 'viva' }
    case 'declaration':
      return claimed
        ? { route: 'declaration+spot-check', locked: false, rule: 'declaration_claimed' }
        : { route: 'viva', locked: false, rule: 'declaration_unclaimed' }
    default:
      return { route: 'observe', locked: false, rule: 'observe' }
  }
}

export function planFor(qp: QP, claimedPcIds: string[]): Record<string, RouteDecision> {
  const claimed = new Set(claimedPcIds)
  const out: Record<string, RouteDecision> = {}
  for (const nos of qp.nos) for (const pc of nos.pcs) out[pc.id] = routeFor(pc, claimed.has(pc.id))
  return out
}

export const ROUTE_ICON: Record<Route, string> = {
  observe: '👁️',
  photo: '📷',
  viva: '💬',
  'declaration+spot-check': '📝',
}
