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
    path: '/assessor',
    component: () => import('../views/AssessorHome.vue'),
    meta: { roles: ['assessor'] },
  },
  { path: '/qa', component: () => import('../views/QaHome.vue'), meta: { roles: ['qa_lead', 'admin'] } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated && auth.user) return homeFor[auth.user.role]
    return true
  }
  if (!auth.isAuthenticated || !auth.user) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.roles && !to.meta.roles.includes(auth.user.role)) return homeFor[auth.user.role]
  return true
})
