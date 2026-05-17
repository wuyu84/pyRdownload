import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/search',
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('@/views/SearchView.vue'),
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
