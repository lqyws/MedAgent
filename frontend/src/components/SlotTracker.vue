<script setup lang="ts">
import { computed } from 'vue'
import type { TriageSlots } from '../types'

const props = defineProps<{ slots: TriageSlots; turn: number }>()

const slotDefs = [
  { key: 'chief_complaint', label: '主诉' },
  { key: 'present_illness', label: '现病史' },
  { key: 'past_history', label: '既往史' },
  { key: 'drug_allergy', label: '用药禁忌' },
] as const

const filled = computed(() => slotDefs.filter((d) => !!props.slots[d.key]).length)
const percent = computed(() => Math.round((filled.value / 4) * 100))
</script>

<template>
  <aside class="panel card">
    <div class="panel-head">
      <span class="panel-title">信息采集</span>
      <span class="panel-count">{{ filled }}/4</span>
    </div>
    <div class="panel-sub">第 {{ turn }} 轮追问 · 已完成 {{ percent }}%</div>

    <div class="progress">
      <div class="progress-bar" :style="{ width: `${percent}%` }"></div>
    </div>

    <div class="slot-list">
      <div v-for="d in slotDefs" :key="d.key" class="slot" :class="{ ok: !!slots[d.key] }">
        <span class="slot-ico">
          <svg v-if="slots[d.key]" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
          <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
            <circle cx="12" cy="12" r="3" />
          </svg>
        </span>
        <span class="slot-name">{{ d.label }}</span>
        <span class="slot-state">{{ slots[d.key] ? '已采集' : '待采集' }}</span>
      </div>
    </div>
  </aside>
</template>
