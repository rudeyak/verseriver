<template>
  <main>
    <!-- Search / filter bar -->
    <div class="filter-bar">
      <div class="container--wide">
        <div class="filter-bar__inner">
          <input
            v-model="search"
            class="input filter-bar__search"
            placeholder="Search poems, authors…"
            @input="debouncedFetch"
          />
          <select v-model="statusFilter" class="input filter-bar__select" @change="fetchPoems">
            <option value="">All poems</option>
            <option value="done">With text</option>
            <option value="pending">Pending</option>
            <option value="error">Errors</option>
          </select>
          <input
            v-model="authorFilter"
            class="input filter-bar__author"
            placeholder="Author…"
            @input="debouncedFetch"
          />
          <div class="filter-bar__spacer" />
          <button class="btn btn--ghost btn--sm" title="Import URLs" @click="showImport = true">
            + Import
          </button>
          <button class="btn btn--ghost btn--sm" title="Trigger full refresh" @click="triggerRefresh">
            ↺ Refresh
          </button>
        </div>
      </div>
    </div>

    <!-- Stats strip -->
    <div class="stats-strip" v-if="stats">
      <div class="container--wide">
        <span class="font-ui text-sm text-muted">
          {{ stats.total_poems }} poems &middot;
          {{ stats.scraped }} with text &middot;
          {{ stats.pending }} pending &middot;
          {{ stats.distinct_authors }} authors &middot;
          {{ stats.active_sources }} sources
        </span>
        <button
          v-if="stats.pending > 0"
          class="btn btn--sm btn--ghost"
          style="margin-left: 1rem"
          @click="scrapePending"
        >Scrape {{ stats.pending }} pending</button>
      </div>
    </div>

    <!-- Poem grid -->
    <div class="container--wide page-content">
      <div v-if="loading" class="state-box">Loading…</div>

      <div v-else-if="data && data.poems.length === 0" class="state-box">
        No poems found.
        <br />
        <a href="/sources" class="mt-2" style="display:inline-block">Add sources</a>
        or
        <button class="btn btn--sm mt-2" @click="showImport = true">import URLs</button>
      </div>

      <template v-else-if="data">
        <div class="poem-grid">
          <PoemCard
            v-for="poem in data.poems"
            :key="poem.id"
            :poem="poem"
          />
        </div>

        <!-- Pagination -->
        <div class="pagination" v-if="data.total > limit">
          <button
            class="btn btn--sm"
            :disabled="page <= 1"
            @click="page--; fetchPoems()"
          >← Prev</button>
          <span class="font-ui text-sm text-muted">
            Page {{ page }} of {{ Math.ceil(data.total / limit) }}
          </span>
          <button
            class="btn btn--sm"
            :disabled="page * limit >= data.total"
            @click="page++; fetchPoems()"
          >Next →</button>
        </div>
      </template>
    </div>

    <!-- Import modal -->
    <div class="overlay" v-if="showImport" @click.self="showImport = false">
      <div class="overlay__box">
        <h2 class="poem-title" style="font-size:1.2rem; margin-bottom:1rem">Import URLs</h2>
        <p class="font-ui text-sm text-muted" style="margin-bottom:0.75rem">
          Paste poem URLs, one per line. The app will scrape text automatically.
        </p>
        <textarea
          v-model="importText"
          class="input"
          rows="10"
          placeholder="https://www.poetryfoundation.org/poems/…&#10;https://poets.org/poem/…"
          style="resize: vertical; font-family: monospace; font-size: 0.8125rem;"
        />
        <div style="display:flex; gap:0.5rem; margin-top:1rem; justify-content:flex-end">
          <button class="btn btn--ghost" @click="showImport = false">Cancel</button>
          <button class="btn btn--primary" :disabled="importing" @click="doImport">
            {{ importing ? 'Importing…' : 'Import' }}
          </button>
        </div>
        <p v-if="importResult" class="font-ui text-sm mt-3" style="color: var(--accent)">
          {{ importResult }}
        </p>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'
import PoemCard from '../components/PoemCard.vue'

const data = ref(null)
const stats = ref(null)
const loading = ref(false)
const page = ref(1)
const limit = 30
const search = ref('')
const statusFilter = ref('')
const authorFilter = ref('')
const showImport = ref(false)
const importText = ref('')
const importing = ref(false)
const importResult = ref('')

let debounceTimer = null

async function fetchPoems() {
  loading.value = true
  try {
    data.value = await api.poems.list({
      page: page.value,
      limit,
      search: search.value || undefined,
      status: statusFilter.value || undefined,
      author: authorFilter.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

function debouncedFetch() {
  clearTimeout(debounceTimer)
  page.value = 1
  debounceTimer = setTimeout(fetchPoems, 350)
}

async function fetchStats() {
  stats.value = await api.stats()
}

async function triggerRefresh() {
  await api.refresh()
  setTimeout(fetchStats, 3000)
}

async function scrapePending() {
  await api.scrapePending()
  setTimeout(() => { fetchPoems(); fetchStats() }, 2000)
}

async function doImport() {
  importing.value = true
  importResult.value = ''
  try {
    const urls = importText.value.split('\n').filter(l => l.trim())
    const result = await api.import(urls)
    importResult.value = `Added ${result.added_poems} poems, ${result.added_sources} sources.`
    importText.value = ''
    await fetchPoems()
    await fetchStats()
  } catch (e) {
    importResult.value = `Error: ${e.message}`
  } finally {
    importing.value = false
  }
}

onMounted(() => {
  fetchPoems()
  fetchStats()
})
</script>

<style scoped>
.filter-bar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0.75rem 0;
  position: sticky;
  top: var(--nav-height);
  z-index: 90;
}

.filter-bar__inner {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.filter-bar__search {
  flex: 1;
  min-width: 180px;
  max-width: 320px;
}

.filter-bar__select {
  width: 140px;
  flex-shrink: 0;
}

.filter-bar__author {
  width: 160px;
  flex-shrink: 0;
}

.filter-bar__spacer { flex: 1; }

.stats-strip {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}

.page-content {
  padding-top: 1.5rem;
  padding-bottom: 3rem;
}

/* ── Poem grid — responsive columns ── */
.poem-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

:root[data-theme="broadsheet"] .poem-grid {
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.25rem;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 2rem;
}
</style>
