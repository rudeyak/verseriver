import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './pages/Home.vue'
import PoemView from './pages/PoemView.vue'
import Sources from './pages/Sources.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/poem/:id', component: PoemView },
    { path: '/sources', component: Sources },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

const app = createApp(App)
app.use(router)
app.mount('#app')
