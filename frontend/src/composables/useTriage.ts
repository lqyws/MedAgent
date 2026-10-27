import { computed, ref } from 'vue'
import { startTriage, chatTriage } from '../api/client'
import { useConversations } from './useConversations'
import type { ChatMsg, Session, StartPayload, TriageResponse, TriageSlots, UrgencyLevel } from '../types'

/** 消息自增 id，起始值取当前时间戳避免与历史消息冲突 */
let uid = Date.now()

export function useTriage() {
  const { active, setActive, upsert, remove, startNew } = useConversations()

  const loading = ref(false)
  const error = ref('')

  const phase = computed(() => active.value?.phase ?? 'idle')
  const messages = computed<ChatMsg[]>(() => active.value?.messages ?? [])
  const slots = computed<TriageSlots>(() => active.value?.slots ?? {})
  const turnCount = computed(() => active.value?.turnCount ?? 0)
  const department = computed(() => active.value?.department ?? '')
  const urgency = computed<UrgencyLevel | null>(() => active.value?.urgency ?? null)
  const reason = computed(() => active.value?.reason ?? '')
  const finalText = computed(() => active.value?.finalText ?? '')
  const activeTitle = computed(() => active.value?.title ?? '新建预问诊')

  function apply(s: Session, r: TriageResponse) {
    s.threadId = r.thread_id
    s.slots = r.slots || {}
    s.turnCount = r.turn_count
    s.updatedAt = Date.now()
    if (r.is_final) {
      s.phase = 'report'
      s.department = r.department_recommendation || '全科医学科'
      s.urgency = r.urgency_level ?? 'green'
      s.reason = r.triage_reason || ''
      s.finalText = r.final_response || ''
    } else if (r.next_question) {
      s.phase = 'chat'
      s.messages.push({ id: ++uid, role: 'agent', text: r.next_question })
    }
  }

  async function start(p: StartPayload) {
    if (loading.value) return
    loading.value = true
    error.value = ''

    const now = Date.now()
    const s: Session = {
      id: `c_${now.toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
      threadId: '',
      title: p.symptom.length > 26 ? `${p.symptom.slice(0, 26)}…` : p.symptom,
      createdAt: now,
      updatedAt: now,
      phase: 'chat',
      messages: [{ id: ++uid, role: 'user', text: p.symptom }],
      slots: {},
      turnCount: 0,
      department: '',
      urgency: null,
      reason: '',
      finalText: '',
    }
    upsert(s)
    setActive(s.id)

    try {
      apply(s, await startTriage(p))
    } catch (e) {
      error.value = e instanceof Error ? e.message : '网络异常，请重试'
      remove(s.id)
    } finally {
      loading.value = false
    }
  }

  async function send(text: string) {
    const s = active.value
    const t = text.trim()
    if (!s || !t || loading.value || s.phase !== 'chat' || !s.threadId) return

    s.messages.push({ id: ++uid, role: 'user', text: t })
    s.updatedAt = Date.now()
    loading.value = true
    error.value = ''

    try {
      apply(s, await chatTriage(s.threadId, t))
    } catch (e) {
      error.value = e instanceof Error ? e.message : '网络异常，请重试'
    } finally {
      loading.value = false
    }
  }

  /** 开启一个新对话（回到采集表单） */
  function newConversation() {
    error.value = ''
    startNew()
  }

  return {
    phase, messages, slots, turnCount, loading, error,
    department, urgency, reason, finalText, activeTitle,
    start, send, newConversation,
  }
}
