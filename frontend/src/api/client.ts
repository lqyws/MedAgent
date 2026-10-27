import type { TriageResponse, StartPayload } from '../types'

const BASE: string = (import.meta.env.VITE_API_BASE as string) || ''

async function post<T>(path: string, body: unknown): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('无法连接服务器，请确认后端服务已启动（端口 8001）')
  }
  if (!resp.ok) {
    let msg = `请求失败（${resp.status}）`
    try {
      const data = await resp.json()
      if (typeof data?.detail === 'string') msg = data.detail
    } catch { /* ignore parse error */ }
    throw new Error(msg)
  }
  return resp.json() as Promise<T>
}

export function startTriage(p: StartPayload): Promise<TriageResponse> {
  return post('/api/v1/triage/start', {
    first_message: p.symptom,
    age: p.age ?? null,
    gender: p.gender ?? null,
  })
}

export function chatTriage(threadId: string, message: string): Promise<TriageResponse> {
  return post('/api/v1/triage/chat', { thread_id: threadId, message })
}
