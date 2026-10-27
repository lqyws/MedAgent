<script setup lang="ts">
import type { UrgencyLevel } from '../types'

defineProps<{
  department: string
  urgency: UrgencyLevel | null
  reason: string
  text: string
}>()

const emit = defineEmits<{ (e: 'restart'): void }>()

const URGENCY_MAP: Record<UrgencyLevel, { label: string; cls: string }> = {
  red: { label: '急症风险 · 立即就医', cls: 'badge-red' },
  yellow: { label: '建议尽快就医', cls: 'badge-yellow' },
  green: { label: '常规门诊', cls: 'badge-green' },
}

const URGENCY_TIP: Record<UrgencyLevel, string> = {
  red: '请立即拨打 120 或前往最近医院急诊科，不要自行前往。',
  yellow: '建议尽快就医，不要拖延；如症状加重请立即前往急诊。',
  green: '请按推荐科室前往门诊挂号就诊。',
}
</script>

<template>
  <section class="report card">
    <div class="report-head">
      <div class="report-head-left">
        <span class="report-head-ico">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9" />
          </svg>
        </span>
        <div>
          <h2>预问诊分诊报告</h2>
          <p>信息采集完成 · AI 已生成分诊建议</p>
        </div>
      </div>
      <span v-if="urgency" class="badge" :class="URGENCY_MAP[urgency].cls">
        <span class="bdot"></span>
        {{ URGENCY_MAP[urgency].label }}
      </span>
    </div>

    <div class="report-body">
      <div class="dept-block">
        <span class="dept-ico">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 21h18" /><path d="M5 21V7l7-4 7 4v14" /><path d="M9 21v-5h6v5" />
          </svg>
        </span>
        <div>
          <div class="dept-label">推荐就诊科室</div>
          <div class="dept-name">{{ department }}</div>
        </div>
      </div>

      <div v-if="urgency === 'red' || urgency === 'yellow'" class="notice">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" /><path d="M12 8v5M12 16h.01" />
        </svg>
        <span>{{ URGENCY_TIP[urgency] }}</span>
      </div>

      <div v-if="reason" class="section">
        <h4 class="section-title">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
          </svg>
          分诊依据
        </h4>
        <div class="reason-box">{{ reason }}</div>
      </div>

      <div v-if="text" class="section">
        <h4 class="section-title">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          问诊小结与指南参考
        </h4>
        <div class="summary">{{ text }}</div>
      </div>

      <div class="notice">
        <span>以上内容由 AI 生成，仅供参考，请以执业医师诊断为准。</span>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" type="button" @click="emit('restart')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        新建预问诊
      </button>
    </div>
  </section>
</template>
