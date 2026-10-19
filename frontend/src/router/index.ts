import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { homeFor, type Role, useAuthStore } from '../stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    roles?: Role[]
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/about', component: () => import('../views/AboutView.vue'), meta: { public: true } },
  { path: '/worker', component: () => import('../views/WorkerHome.vue'), meta: { roles: ['worker'] } },
  {
    path: '/worker/consent',
    component: () => import('../views/worker/ConsentView.vue'),
    meta: { roles: ['worker'] },
  },
  {
    path: '/worker/declare',
    component: () => import('../views/worker/DeclareView.vue'),
    meta: { roles: ['worker'] },
  },
  {
    path: '/worker/results/:clientId',
    component: () => import('../views/worker/ResultsView.vue'),
    meta: { roles: ['worker'] },
  },
  {
    path: '/assessor',
    component: () => import('../views/AssessorHome.vue'),
    meta: { roles: ['assessor'] },
  },
  {
    path: '/assessor/assessment/:id',
    component: () => import('../views/assessor/AssessmentView.vue'),
    meta: { roles: ['assessor'] },
  },
  { path: '/qa', component: () => import('../views/QaHome.vue'), meta: { roles: ['qa_lead', 'admin'] } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

export const router = createRouter({ history: createWebHistory(), routes })

// Load the screens a role needs offline as soon as we know the role, so they are in
// memory (and in the SW cache) before the network drops.
const ROLE_VIEWS: Partial<Record<Role, (() => Promise<unknown>)[]>> = {
  worker: [
    () => import('../views/worker/ConsentView.vue'),
    () => import('../views/worker/DeclareView.vue'),
    () => import('../views/worker/ResultsView.vue'),
  ],
  assessor: [() => import('../views/AssessorHome.vue'), () => import('../views/assessor/AssessmentView.vue')],
}
const prefetched = new Set<Role>()
function prefetchRoleViews(role: Role) {
  if (prefetched.has(role)) return
  prefetched.add(role)
  for (const load of ROLE_VIEWS[role] ?? []) load().catch(() => prefetched.delete(role))
}

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (auth.user) prefetchRoleViews(auth.user.role)
  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated && auth.user) return homeFor[auth.user.role]
    return true
  }
  if (!auth.isAuthenticated || !auth.user) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.roles && !to.meta.roles.includes(auth.user.role)) return homeFor[auth.user.role]
  return true
})
