<script setup lang="ts">
import { ref } from 'vue'
import type { StartPayload } from '../types'

const props = defineProps<{ loading: boolean }>()
const emit = defineEmits<{ (e: 'start', payload: StartPayload): void }>()

const symptom = ref('')
const age = ref<number | null>(null)
const gender = ref('')

const quickSymptoms = ['咳嗽发烧', '腹痛腹泻', '头晕头痛', '胸闷心慌', '皮肤瘙痒', '腰痛腿麻']

function useQuick(s: string) {
  symptom.value = s
}

function submit() {
  if (!symptom.value.trim() || props.loading) return
  const ageNum = age.value === null || (age.value as unknown) === '' ? undefined : Number(age.value)
  emit('start', {
    symptom: symptom.value.trim(),
    age: Number.isFinite(ageNum as number) ? (ageNum as number) : undefined,
    gender: gender.value || undefined,
  })
}
</script>

<template>
  <section class="intake card">
    <div class="page-head">
      <h1>新建预问诊</h1>
      <p>AI 助手将通过 3–5 轮追问补全问诊信息，为您推荐就诊科室并评估急诊风险</p>
    </div>

    <div class="form-row">
      <label class="label" for="symptom">主要症状 <span class="req">*</span></label>
      <textarea
        id="symptom"
        v-model="symptom"
        class="control"
        placeholder="例如：咳嗽发烧三天了，还有点胸闷、乏力…"
        :disabled="loading"
        @keydown.ctrl.enter="submit"
      ></textarea>
      <div class="quick-chips">
        <button
          v-for="q in quickSymptoms"
          :key="q"
          type="button"
          class="chip-btn"
          :disabled="loading"
          @click="useQuick(q)"
        >{{ q }}</button>
      </div>
      <div class="hint">快捷键：Ctrl + Enter 开始问诊</div>
    </div>

    <div class="form-grid">
      <div class="form-row">
        <label class="label" for="age">年龄（选填）</label>
        <input
          id="age"
          v-model.number="age"
          type="number"
          min="0"
          max="120"
          class="control"
          placeholder="如：32"
          :disabled="loading"
        />
      </div>
      <div class="form-row">
        <label class="label" for="gender">性别（选填）</label>
        <select id="gender" v-model="gender" class="control" :disabled="loading">
          <option value="">不透露</option>
          <option value="男">男</option>
          <option value="女">女</option>
        </select>
      </div>
    </div>

    <div class="notice">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" /><path d="M12 8v5M12 16h.01" />
      </svg>
      <span>本系统输出仅为分诊建议，不构成医疗诊断依据。如有胸痛、呼吸困难、意识障碍、大出血等急症，请立即拨打 120。</span>
    </div>

    <button class="btn btn-primary btn-block" :disabled="!symptom.trim() || loading" @click="submit">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
      {{ loading ? '正在连接…' : '开始预问诊' }}
    </button>
  </section>
</template>
