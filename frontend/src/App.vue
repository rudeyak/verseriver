<template>
  <div>
    <nav class="nav">
      <div class="nav__inner">
        <RouterLink to="/" class="nav__logo">Verse<span>River</span></RouterLink>
        <div class="nav__links">
          <RouterLink to="/" class="nav__link">Feed</RouterLink>
          <RouterLink to="/sources" class="nav__link">Sources</RouterLink>
        </div>
        <div class="nav__spacer" />
        <div class="nav__actions">
          <button
            class="btn btn--ghost btn--sm"
            :title="`Switch to ${otherTheme.label} theme`"
            @click="toggleTheme"
          >
            {{ currentTheme.label }}
          </button>
        </div>
      </div>
    </nav>
    <RouterView />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { theme, toggleTheme, initTheme, THEMES } from './theme.js'

onMounted(initTheme)

const currentTheme = computed(() => THEMES.find(t => t.id === theme.value))
const otherTheme   = computed(() => THEMES.find(t => t.id !== theme.value))
</script>
