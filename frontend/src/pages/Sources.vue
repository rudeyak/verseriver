<template>
  <div class="sources-page">
    <div class="container">
      <div class="sources-header">
        <div>
          <h1 class="poem-title" style="font-size:1.4rem">Sources</h1>
          <p class="font-ui text-sm text-muted mt-1">
            RSS feeds and sites to watch for new poems.
          </p>
        </div>
        <button class="btn btn--primary btn--sm" @click="showAdd = true">+ Add source</button>
      </div>

      <div v-if="loading" class="state-box">Loading sources…</div>

      <div v-else-if="sources.length === 0" class="state-box">
        No sources yet. Add an RSS feed or poetry site URL.
      </div>

      <div class="source-list" v-else>
        <div
          v-for="source in sources"
          :key="source.id"
          class="source-card card"
          :class="{ 'source-card--inactive': !source.is_active }"
        >
          <div class="source-card__info">
            <div class="source-card__name font-ui">
              {{ source.name || sourceDomain(source.url) }}
              <span class="badge" :class="typeBadgeClass(source.type)">{{ source.type }}</span>
              <span v-if="!source.is_active" class="badge" style="margin-left:0.25rem">paused</span>
            </div>
            <a :href="source.url" target="_blank" class="source-card__url font-ui text-sm text-muted">
              {{ source.url }}
            </a>
            <p class="source-card__meta font-ui text-sm text-muted" v-if="source.last_fetched">
              Last fetched: {{ source.last_fetched.slice(0, 16).replace('T', ' ') }}
            </p>
            <p class="source-card__meta font-ui text-sm text-muted" v-else>Never fetched</p>
          </div>
          <div class="source-card__stats font-ui">
            <span class="text-muted text-sm">{{ source.poem_count }} poems</span>
          </div>
          <div class="source-card__actions">
            <button class="btn btn--ghost btn--sm" @click="refresh(source)" :disabled="refreshing[source.id]">
              {{ refreshing[source.id] ? '…' : '↺' }}
            </button>
            <button
              class="btn btn--ghost btn--sm"
              @click="toggleActive(source)"
              :title="source.is_active ? 'Pause' : 'Resume'"
            >{{ source.is_active ? '⏸' : '▶' }}</button>
            <button class="btn btn--ghost btn--sm" @click="remove(source)" title="Delete">✕</button>
          </div>
        </div>
      </div>

      <!-- Refresh all -->
      <div v-if="sources.length > 0" style="margin-top:1.5rem; display:flex; gap:0.5rem">
        <button class="btn btn--sm" @click="refreshAll">↺ Refresh all sources</button>
        <button class="btn btn--sm btn--ghost" @click="exportData">Export JSON</button>
      </div>
    </div>

    <!-- Add source modal -->
    <div class="overlay" v-if="showAdd" @click.self="showAdd = false">
      <div class="overlay__box">
        <h2 class="poem-title" style="font-size:1.1rem; margin-bottom:1rem">Add source</h2>
        <p class="font-ui text-sm text-muted" style="margin-bottom:0.75rem">
          Enter a site URL or RSS feed. VerseRiver will try to discover the RSS feed automatically.
        </p>
        <label class="font-ui text-sm" style="display:block; margin-bottom:0.25rem">URL *</label>
        <input v-model="newSource.url" class="input" placeholder="https://…" />
        <label class="font-ui text-sm mt-3" style="display:block; margin-bottom:0.25rem">Name (optional)</label>
        <input v-model="newSource.name" class="input" placeholder="Poetry Foundation…" />
        <label class="font-ui text-sm mt-3" style="display:block; margin-bottom:0.25rem">RSS URL (optional — leave blank to auto-discover)</label>
        <input v-model="newSource.rss_url" class="input" placeholder="https://…/feed.xml" />
        <div style="display:flex; gap:0.5rem; margin-top:1rem; justify-content:flex-end">
          <button class="btn btn--ghost" @click="showAdd = false">Cancel</button>
          <button class="btn btn--primary" :disabled="adding" @click="addSource">
            {{ adding ? 'Adding…' : 'Add source' }}
          </button>
        </div>
        <p v-if="addError" class="font-ui text-sm mt-2" style="color:var(--accent)">{{ addError }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'

const sources = ref([])
const loading = ref(false)
const showAdd = ref(false)
const adding = ref(false)
const addError = ref('')
const refreshing = ref({})

const newSource = ref({ url: '', name: '', rss_url: '' })

function sourceDomain(url) {
  try { return new URL(url).hostname.replace('www.', '') }
  catch { return url }
}

function typeBadgeClass(type) {
  return type === 'rss' ? 'badge--green' : ''
}

async function load() {
  loading.value = true
  try { sources.value = await api.sources.list() }
  finally { loading.value = false }
}

async function addSource() {
  addError.value = ''
  if (!newSource.value.url) { addError.value = 'URL is required'; return }
  adding.value = true
  try {
    await api.sources.add(newSource.value)
    newSource.value = { url: '', name: '', rss_url: '' }
    showAdd.value = false
    await load()
  } catch (e) {
    addError.value = e.message
  } finally {
    adding.value = false
  }
}

async function refresh(source) {
  refreshing.value[source.id] = true
  try {
    await api.sources.refresh(source.id)
    await new Promise(r => setTimeout(r, 2000))
    await load()
  } finally {
    delete refreshing.value[source.id]
  }
}

async function refreshAll() {
  await api.refresh()
  setTimeout(load, 3000)
}

async function toggleActive(source) {
  await api.sources.update(source.id, { is_active: !source.is_active })
  await load()
}

async function remove(source) {
  if (!confirm(`Remove source "${source.name || sourceDomain(source.url)}"?`)) return
  await api.sources.delete(source.id)
  await load()
}

async function exportData() {
  const data = await api.export()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'verseriver-export.json'
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(load)
</script>

<style scoped>
.sources-page {
  padding-bottom: 4rem;
}

.sources-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.5rem 0 1rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.25rem;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.source-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.875rem 1rem;
  flex-wrap: wrap;
}

.source-card--inactive {
  opacity: 0.55;
}

.source-card__info {
  flex: 1;
  min-width: 200px;
}

.source-card__name {
  font-size: 0.9375rem;
  font-weight: 500;
  margin-bottom: 0.2rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.source-card__url {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 360px;
  color: var(--text-faint);
}

.source-card__meta {
  margin-top: 0.15rem;
}

.source-card__stats {
  text-align: right;
  white-space: nowrap;
}

.source-card__actions {
  display: flex;
  gap: 0.25rem;
}
</style>
