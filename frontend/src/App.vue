<script setup lang="ts">
import { ref } from 'vue'
import { useTriage } from './composables/useTriage'
import { useConversations } from './composables/useConversations'
import Sidebar from './components/Sidebar.vue'
import AppHeader from './components/AppHeader.vue'
import EmergencyBanner from './components/EmergencyBanner.vue'
import IntakeForm from './components/IntakeForm.vue'
import ChatWindow from './components/ChatWindow.vue'
import SlotTracker from './components/SlotTracker.vue'
import TriageReport from './components/TriageReport.vue'

const { sorted, activeId, openConversation, remove } = useConversations()
const {
  phase, messages, slots, turnCount, loading, error,
  department, urgency, reason, finalText, activeTitle,
  start, send, newConversation,
} = useTriage()

const sidebarOpen = ref(false)

function handleNew() {
  newConversation()
  sidebarOpen.value = false
}

function handleOpen(id: string) {
  openConversation(id)
  sidebarOpen.value = false
}
</script>

<template>
  <div class="app">
    <Sidebar
      :sessions="sorted"
      :active-id="activeId"
      :class="{ open: sidebarOpen }"
      @new="handleNew"
      @open="handleOpen"
      @remove="remove"
    />

    <div v-if="sidebarOpen" class="overlay" @click="sidebarOpen = false"></div>

    <div class="main">
      <AppHeader
        :title="activeTitle"
        :phase="phase"
        :turn="turnCount"
        :loading="loading"
        @toggle="sidebarOpen = !sidebarOpen"
      />

      <EmergencyBanner v-if="phase === 'report' && urgency === 'red'" />

      <main class="workspace">
        <IntakeForm v-if="phase === 'idle'" :loading="loading" @start="start" />

        <div v-else-if="phase === 'chat'" class="chat-layout">
          <ChatWindow :messages="messages" :loading="loading" @send="send" />
          <SlotTracker :slots="slots" :turn="turnCount" />
        </div>

        <TriageReport
          v-else
          :department="department"
          :urgency="urgency"
          :reason="reason"
          :text="finalText"
          @restart="newConversation"
        />
      </main>
    </div>

    <div v-if="error" class="toast">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" /><path d="M12 8v5M12 16h.01" />
      </svg>
      {{ error }}
    </div>
  </div>
</template>
