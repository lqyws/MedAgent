<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  phase: 'idle' | 'chat' | 'report'
  turn: number
  loading: boolean
}>()

const emit = defineEmits<{ (e: 'toggle'): void }>()

const statusText = computed(() => {
  if (props.loading) return 'AI 正在回复…'
  if (props.phase === 'report') return '分诊已完成'
  if (props.phase === 'chat') return '问诊进行中'
  return '等待开始'
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <button class="icon-btn hamburger" type="button" aria-label="打开会话列表" @click="emit('toggle')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round">
          <path d="M3 6h18M3 12h18M3 18h18" />
        </svg>
      </button>
      <div>
        <div class="page-title">{{ title }}</div>
        <div class="page-sub">AI 智能预问诊 · 分诊辅助系统</div>
      </div>
    </div>

    <div class="topbar-right">
      <span v-if="turn > 0" class="chip">第 {{ turn }} 轮追问</span>
      <span class="chip"><span class="dot"></span>{{ statusText }}</span>
    </div>
  </header>
</template>
