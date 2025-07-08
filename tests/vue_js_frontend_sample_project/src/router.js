import { createRouter, createWebHistory } from 'vue-router';
import HomeView from './views/HomeView.vue';
import CoinDetailView from './views/CoinDetailView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/coin/:id',
    name: 'coin-detail',
    component: CoinDetailView,
    props: true,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;