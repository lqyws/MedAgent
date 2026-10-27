<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Session } from '../types'

const props = defineProps<{ sessions: Session[]; activeId: string | null }>()
const emit = defineEmits<{
  (e: 'new'): void
  (e: 'open', id: string): void
  (e: 'remove', id: string): void
}>()

const keyword = ref('')

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return props.sessions
  return props.sessions.filter((s) => s.title.toLowerCase().includes(k))
})

const DAY = 86400000
function startOfDay(ts: number): number {
  const d = new Date(ts)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}
const todayStart = startOfDay(Date.now())

const groups = computed(() => {
  const buckets = [
    { label: '今天', items: [] as Session[] },
    { label: '昨天', items: [] as Session[] },
    { label: '更早', items: [] as Session[] },
  ]
  for (const s of filtered.value) {
    const t = startOfDay(s.updatedAt)
    if (t >= todayStart) buckets[0].items.push(s)
    else if (t >= todayStart - DAY) buckets[1].items.push(s)
    else buckets[2].items.push(s)
  }
  return buckets.filter((b) => b.items.length > 0)
})

function hhmm(ts: number): string {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function badge(s: Session): { text: string; cls: string } {
  if (s.phase === 'report') {
    return s.urgency === 'red'
      ? { text: '急诊', cls: 'nav-badge red' }
      : { text: '已完成', cls: 'nav-badge done' }
  }
  return { text: '问诊中', cls: 'nav-badge' }
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span class="brand-logo" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M11 3v6H5v6h6v6h6v-6h6V9h-6V3z" />
        </svg>
      </span>
      <span class="brand-meta">
        <span class="brand-name">MedAgent</span>
        <span class="brand-sub">智能预问诊工作台</span>
      </span>
    </div>

    <div class="sidebar-actions">
      <button class="btn-new" type="button" @click="emit('new')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        新建预问诊
      </button>
    </div>

    <div class="search-wrap">
      <div class="search">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round">
          <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
        </svg>
        <input v-model="keyword" type="search" placeholder="搜索历史对话" />
      </div>
    </div>

    <nav class="nav-scroll">
      <div v-for="g in groups" :key="g.label" class="nav-group">
        <div class="nav-group-label">
          <span>{{ g.label }}</span>
          <span>{{ g.items.length }}</span>
        </div>
        <div
          v-for="s in g.items"
          :key="s.id"
          class="nav-item"
          :class="{ active: s.id === activeId }"
          role="button"
          tabindex="0"
          @click="emit('open', s.id)"
          @keydown.enter="emit('open', s.id)"
        >
          <span class="nav-ico">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z" />
            </svg>
          </span>
          <span class="nav-body">
            <span class="nav-title" :title="s.title">{{ s.title }}</span>
            <span class="nav-meta">
              <span>{{ hhmm(s.updatedAt) }}</span>
              <span :class="badge(s).cls">{{ badge(s).text }}</span>
            </span>
          </span>
          <span class="nav-del" role="button" aria-label="删除对话" @click.stop="emit('remove', s.id)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </span>
        </div>
      </div>

      <div v-if="!filtered.length" class="nav-empty">
        {{ keyword.trim() ? '没有匹配的对话' : '暂无历史对话' }}<br />
        点击上方「新建预问诊」开始
      </div>
    </nav>

    <div class="sidebar-foot">
      <div class="foot-status">
        <span class="foot-dot"></span>
        服务运行中 · qwen-plus
      </div>
    </div>
  </aside>
</template>
