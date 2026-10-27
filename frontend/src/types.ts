export type UrgencyLevel = 'red' | 'yellow' | 'green'

export interface TriageSlots {
  chief_complaint?: string | null
  present_illness?: string | null
  past_history?: string | null
  drug_allergy?: string | null
}

export interface TriageResponse {
  thread_id: string
  department_recommendation?: string | null
  urgency_level?: UrgencyLevel | null
  triage_reason?: string | null
  final_response?: string | null
  next_question?: string | null
  turn_count: number
  is_final: boolean
  slots: TriageSlots
}

export interface StartPayload {
  symptom: string
  age?: number
  gender?: string
}

export interface ChatMsg {
  id: number
  role: 'agent' | 'user'
  text: string
}

/** 一次完整的预问诊会话（本地持久化） */
export interface Session {
  id: string
  threadId: string
  title: string
  createdAt: number
  updatedAt: number
  phase: 'chat' | 'report'
  messages: ChatMsg[]
  slots: TriageSlots
  turnCount: number
  department: string
  urgency: UrgencyLevel | null
  reason: string
  finalText: string
}
