import { computed, ref, watch } from 'vue'
import type { Session } from '../types'

const STORAGE_KEY = 'medagent.conversations.v1'
const ACTIVE_KEY = 'medagent.active.v1'

function safeParse(raw: string | null): Session[] {
  if (!raw) return []
  try {
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.filter((s) => s && typeof s.id === 'string') : []
  } catch {
    return []
  }
}

/** 模块级单例：全应用共享同一份会话列表 */
const conversations = ref<Session[]>(safeParse(localStorage.getItem(STORAGE_KEY)))
const activeId = ref<string | null>(localStorage.getItem(ACTIVE_KEY))

watch(
  conversations,
  (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(v))
    } catch {
      /* 存储已满时静默降级 */
    }
  },
  { deep: true },
)

watch(activeId, (v) => {
  try {
    if (v) localStorage.setItem(ACTIVE_KEY, v)
    else localStorage.removeItem(ACTIVE_KEY)
  } catch {
    /* ignore */
  }
})

const active = computed<Session | null>(
  () => conversations.value.find((c) => c.id === activeId.value) ?? null,
)

export function useConversations() {
  /** 时间倒序列表 */
  const sorted = computed(() => [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt))

  function startNew() {
    activeId.value = null
  }

  function openConversation(id: string) {
    if (conversations.value.some((c) => c.id === id)) activeId.value = id
  }

  /** 新建或整条替换 */
  function upsert(session: Session) {
    const i = conversations.value.findIndex((c) => c.id === session.id)
    if (i >= 0) conversations.value[i] = session
    else conversations.value.unshift(session)
  }

  function setActive(id: string) {
    activeId.value = id
  }

  function remove(id: string) {
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (activeId.value === id) activeId.value = null
  }

  function rename(id: string, title: string) {
    const s = conversations.value.find((c) => c.id === id)
    if (s) s.title = title
  }

  return { conversations, sorted, active, activeId, startNew, openConversation, upsert, setActive, remove, rename }
}
