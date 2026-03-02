<template>
  <div class="poem-page">
    <div class="container">
      <!-- Back nav -->
      <div class="poem-page__nav font-ui">
        <RouterLink to="/" class="btn btn--ghost btn--sm">← Back</RouterLink>
        <div class="poem-page__nav-actions" v-if="poem">
          <a :href="poem.url" target="_blank" rel="noopener" class="btn btn--ghost btn--sm">
            Source ↗
          </a>
          <button class="btn btn--ghost btn--sm" @click="showShare = true" v-if="poem.text">
            Share
          </button>
          <button class="btn btn--ghost btn--sm" @click="showEdit = true">
            Edit
          </button>
          <button
            class="btn btn--ghost btn--sm"
            :disabled="fetching"
            @click="reFetch"
            :title="poem.scrape_status === 'error' ? poem.error_msg : 'Re-scrape'"
          >
            ↺ {{ fetching ? 'Scraping…' : 'Re-scrape' }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="state-box">Loading…</div>

      <div v-else-if="error" class="state-box">{{ error }}</div>

      <article class="poem-article" v-else-if="poem">
        <!-- Header -->
        <header class="poem-header">
          <p class="poem-meta font-ui">
            <span class="poem-meta__source">{{ poem.source_name || sourceDomain }}</span>
            <span v-if="poem.published_date" class="poem-meta__date">
              &middot; {{ poem.published_date.slice(0, 10) }}
            </span>
          </p>
          <h1 class="poem-title mt-2">{{ poem.title || '(untitled)' }}</h1>
          <p class="poem-author mt-1" v-if="poem.author">{{ poem.author }}</p>
        </header>

        <hr class="divider" style="margin: 1.75rem 0" />

        <!-- Body -->
        <div v-if="poem.text" class="poem-body">
          <pre class="poem-text">{{ poem.text }}</pre>
        </div>

        <div v-else class="poem-no-text">
          <div class="state-box" style="text-align:left; padding: 2rem 0">
            <p class="font-ui text-muted">
              <span v-if="poem.scrape_status === 'pending'">This poem hasn't been scraped yet.</span>
              <span v-else-if="poem.scrape_status === 'error'">
                Couldn't extract text automatically.<br />
                <small>{{ poem.error_msg }}</small>
              </span>
              <span v-else>No poem text available.</span>
            </p>
            <div style="display:flex; gap:0.5rem; margin-top:1rem; flex-wrap:wrap">
              <button class="btn btn--primary btn--sm" :disabled="fetching" @click="reFetch">
                {{ fetching ? 'Scraping…' : 'Try scraping now' }}
              </button>
              <a :href="poem.url" target="_blank" class="btn btn--sm">Open source ↗</a>
              <button class="btn btn--sm" @click="showEdit = true">Enter text manually</button>
            </div>
          </div>
        </div>

        <!-- Notes -->
        <div v-if="poem.notes" class="poem-notes font-ui mt-6">
          <p class="text-muted text-sm" style="margin-bottom:0.35rem">Notes</p>
          <p style="font-size:0.9375rem">{{ poem.notes }}</p>
        </div>
      </article>
    </div>

    <!-- Share modal -->
    <div class="overlay" v-if="showShare && poem" @click.self="showShare = false">
      <div class="overlay__box">
        <h2 class="poem-title" style="font-size:1.1rem; margin-bottom:1rem">Share poem</h2>
        <div class="share-card" ref="shareCardEl">
          <p class="share-card__source font-ui">{{ poem.source_name }}</p>
          <h3 class="share-card__title">{{ poem.title }}</h3>
          <p class="share-card__author font-ui" v-if="poem.author">{{ poem.author }}</p>
          <pre class="share-card__text">{{ shareText }}</pre>
          <p class="share-card__brand font-ui">verseriver</p>
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:1rem; flex-wrap:wrap">
          <button class="btn btn--primary btn--sm" @click="copyLink">Copy link</button>
          <a :href="poem.url" target="_blank" class="btn btn--sm">Open original ↗</a>
          <button class="btn btn--ghost btn--sm" @click="showShare = false">Close</button>
        </div>
        <p class="font-ui text-sm mt-2 text-muted" v-if="copied">Link copied!</p>
      </div>
    </div>

    <!-- Edit modal -->
    <div class="overlay" v-if="showEdit && poem" @click.self="showEdit = false">
      <div class="overlay__box" style="max-width:640px">
        <h2 class="poem-title" style="font-size:1.1rem; margin-bottom:1rem">Edit poem</h2>
        <div class="edit-form">
          <label class="edit-label font-ui">Title</label>
          <input v-model="editData.title" class="input" />
          <label class="edit-label font-ui mt-3">Author</label>
          <input v-model="editData.author" class="input" />
          <label class="edit-label font-ui mt-3">Poem text</label>
          <textarea
            v-model="editData.text"
            class="input"
            rows="14"
            style="resize:vertical; font-family:var(--font-poem); white-space:pre-wrap"
          />
          <label class="edit-label font-ui mt-3">Notes</label>
          <input v-model="editData.notes" class="input" placeholder="Optional personal notes" />
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:1rem; justify-content:flex-end">
          <button class="btn btn--ghost" @click="showEdit = false">Cancel</button>
          <button class="btn btn--primary" :disabled="saving" @click="saveEdit">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const poem = ref(null)
const loading = ref(false)
const error = ref('')
const fetching = ref(false)
const showShare = ref(false)
const showEdit = ref(false)
const saving = ref(false)
const copied = ref(false)
const editData = ref({})

const sourceDomain = computed(() => {
  try { return new URL(poem.value?.url || '').hostname.replace('www.', '') }
  catch { return '' }
})

const shareText = computed(() => {
  if (!poem.value?.text) return ''
  const lines = poem.value.text.split('\n').slice(0, 8)
  return lines.join('\n') + (poem.value.text.split('\n').length > 8 ? '\n…' : '')
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    poem.value = await api.poems.get(Number(route.params.id))
    editData.value = {
      title: poem.value.title || '',
      author: poem.value.author || '',
      text: poem.value.text || '',
      notes: poem.value.notes || '',
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function reFetch() {
  fetching.value = true
  try {
    await api.poems.fetch(poem.value.id)
    // Poll for completion
    let tries = 0
    const poll = setInterval(async () => {
      tries++
      const updated = await api.poems.get(poem.value.id)
      if (updated.scrape_status !== 'pending' || tries > 15) {
        poem.value = updated
        clearInterval(poll)
        fetching.value = false
      }
    }, 1500)
  } catch (e) {
    fetching.value = false
  }
}

async function saveEdit() {
  saving.value = true
  try {
    poem.value = await api.poems.update(poem.value.id, {
      ...editData.value,
      scrape_status: editData.value.text ? 'done' : poem.value.scrape_status,
    })
    showEdit.value = false
  } finally {
    saving.value = false
  }
}

function copyLink() {
  navigator.clipboard.writeText(window.location.href)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

onMounted(load)
watch(() => route.params.id, load)
</script>

<style scoped>
.poem-page {
  padding-bottom: 4rem;
}

.poem-page__nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 0;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.poem-page__nav-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.poem-article {
  max-width: 680px;
}

.poem-meta {
  font-size: 0.8125rem;
  color: var(--text-faint);
  letter-spacing: 0.03em;
}

.poem-meta__source {
  text-transform: uppercase;
  font-size: 0.72rem;
  letter-spacing: 0.07em;
}

.poem-body {
  margin-top: 0.5rem;
}

.poem-no-text {
  max-width: 480px;
}

.poem-notes {
  border-top: 1px solid var(--border);
  padding-top: 1rem;
}

/* ── Share card ─────────────────────── */
.share-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5rem;
  position: relative;
}

.share-card__source {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  margin-bottom: 0.5rem;
}

.share-card__title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.2rem;
}

.share-card__author {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.share-card__text {
  font-family: var(--font-poem);
  font-size: 0.9375rem;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--text);
  border-left: 3px solid var(--accent);
  padding-left: 1rem;
  margin-bottom: 1rem;
}

.share-card__brand {
  font-size: 0.7rem;
  color: var(--text-faint);
  text-align: right;
  letter-spacing: 0.05em;
}

/* ── Edit form ─────────────────────── */
.edit-form {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.edit-label {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
  display: block;
}
</style>
