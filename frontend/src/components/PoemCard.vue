<template>
  <RouterLink :to="`/poem/${poem.id}`" class="poem-card" :class="`status-${poem.scrape_status}`">
    <!-- Status pip -->
    <span class="poem-card__pip" :title="statusLabel" />

    <div class="poem-card__body">
      <p class="poem-card__source font-ui">{{ poem.source_name || domain }}</p>

      <h2 class="poem-card__title">
        {{ poem.title || '(untitled)' }}
      </h2>

      <p class="poem-card__author font-ui" v-if="poem.author">
        {{ poem.author }}
      </p>

      <p class="poem-card__preview" v-if="poem.preview && poem.scrape_status === 'done'">
        {{ firstLines }}
      </p>
      <p class="poem-card__pending font-ui" v-else-if="poem.scrape_status === 'pending'">
        Awaiting scrape…
      </p>
      <p class="poem-card__error font-ui" v-else-if="poem.scrape_status === 'error'">
        Could not extract text
      </p>
    </div>

    <div class="poem-card__footer font-ui">
      <span v-if="poem.published_date">{{ poem.published_date.slice(0, 10) }}</span>
      <span v-else>{{ poem.date_added?.slice(0, 10) }}</span>
    </div>
  </RouterLink>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ poem: Object })

const domain = computed(() => {
  try { return new URL(props.poem.source_url || props.poem.url).hostname.replace('www.', '') }
  catch { return '' }
})

const firstLines = computed(() => {
  if (!props.poem.preview) return ''
  const lines = props.poem.preview.split('\n').filter(l => l.trim()).slice(0, 3)
  return lines.join(' / ')
})

const statusLabel = computed(() => ({
  done: 'Text available',
  pending: 'Pending scrape',
  error: 'Scrape failed',
}[props.poem.scrape_status] || ''))
</script>

<style scoped>
.poem-card {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: 1.125rem 1.25rem 0.875rem;
  text-decoration: none;
  color: inherit;
  position: relative;
  transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s;
  overflow: hidden;
  min-height: 140px;
}

.poem-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
  border-color: var(--accent);
  text-decoration: none;
}

/* Coloured left border by status */
.poem-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
}
.poem-card.status-done::before   { background: #10B981; }
.poem-card.status-pending::before { background: #F59E0B; }
.poem-card.status-error::before  { background: #EF4444; }

.poem-card__pip {
  display: none; /* pip is communicated by left border */
}

.poem-card__body { flex: 1; }

.poem-card__source {
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin-bottom: 0.35rem;
}

.poem-card__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text);
  margin-bottom: 0.25rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.poem-card__author {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-bottom: 0.6rem;
}

.poem-card__preview {
  font-family: var(--font-poem);
  font-size: 0.875rem;
  color: var(--text-muted);
  font-style: italic;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.poem-card__pending,
.poem-card__error {
  font-size: 0.8rem;
  color: var(--text-faint);
}

.poem-card__footer {
  font-size: 0.75rem;
  color: var(--text-faint);
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
}

/* Broadsheet-specific card style */
:root[data-theme="broadsheet"] .poem-card {
  border-radius: 2px;
}

:root[data-theme="broadsheet"] .poem-card:hover {
  transform: none;
  box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
</style>
