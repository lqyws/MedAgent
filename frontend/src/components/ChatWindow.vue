<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { ChatMsg } from '../types'

const props = defineProps<{ messages: ChatMsg[]; loading: boolean }>()
const emit = defineEmits<{ (e: 'send', text: string): void }>()

const draft = ref('')
const scroller = ref<HTMLElement | null>(null)

function render(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

function submit() {
  const t = draft.value.trim()
  if (!t || props.loading) return
  emit('send', t)
  draft.value = ''
}

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="chat-panel card">
    <div class="chat-head">
      <span class="chat-head-title">问诊对话</span>
      <span class="page-sub">{{ messages.length }} 条消息</span>
    </div>

    <div ref="scroller" class="chat-scroll">
      <div
        v-for="m in messages"
        :key="m.id"
        class="msg"
        :class="m.role === 'agent' ? 'msg-agent' : 'msg-user'"
      >
        <span class="avatar" :class="m.role === 'agent' ? 'avatar-agent' : 'avatar-user'">
          <svg v-if="m.role === 'agent'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
            <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" />
            <circle cx="20" cy="10" r="2" />
          </svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
          </svg>
        </span>
        <div class="bubble" v-html="render(m.text)"></div>
      </div>

      <div v-if="loading" class="msg msg-agent">
        <span class="avatar avatar-agent">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" />
            <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" /><circle cx="20" cy="10" r="2" />
          </svg>
        </span>
        <div class="bubble">
          <span class="typing"><span></span><span></span><span></span></span>
        </div>
      </div>
    </div>

    <div class="composer">
      <textarea
        v-model="draft"
        class="control"
        placeholder="输入您的回答…（Enter 发送，Shift + Enter 换行）"
        :disabled="loading"
        @keydown.enter.exact.prevent="submit"
      ></textarea>
      <button class="btn btn-primary sender" :disabled="!draft.trim() || loading" @click="submit">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4z" />
        </svg>
        发送
      </button>
    </div>
  </div>
</template>
