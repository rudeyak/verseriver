import { ref, watch } from 'vue'

const STORAGE_KEY = 'verseriver-theme'
const DEFAULT = 'broadsheet'

export const theme = ref(localStorage.getItem(STORAGE_KEY) || DEFAULT)

watch(theme, (t) => {
  localStorage.setItem(STORAGE_KEY, t)
  document.documentElement.setAttribute('data-theme', t)
})

export function initTheme() {
  document.documentElement.setAttribute('data-theme', theme.value)
}

export function toggleTheme() {
  theme.value = theme.value === 'broadsheet' ? 'studio' : 'broadsheet'
}

export const THEMES = [
  { id: 'broadsheet', label: 'Broadsheet', description: 'Warm serif · literary journal' },
  { id: 'studio', label: 'Studio', description: 'Clean sans · modern minimal' },
]
