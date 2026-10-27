"""
FastAPI 入口 —— 预问诊 Agent HTTP API

端点：
  POST /api/v1/triage/start    启动一次新的预问诊
  POST /api/v1/triage/chat     用户继续输入，返回 Agent 追问或最终分诊结果
  GET  /api/v1/triage/{tid}    查看当前会话状态
  DELETE /api/v1/triage/{tid}  结束会话

启动：
  uvicorn app:app --host 0.0.0.0 --port 8001 --reload
"""
from __future__ import annotations
import os, sys, uuid, threading, webbrowser
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from langchain_core.messages import HumanMessage

from agents.triage.graph import get_graph
from config import settings


app = FastAPI(title="MedAgent 预问诊系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schema ──
class StartRequest(BaseModel):
    first_message: str
    age: Optional[int] = None
    gender: Optional[str] = None

    @field_validator("age", mode="before")
    @classmethod
    def _coerce_age(cls, v):
        """容错：空字符串 / 非数字一律视为未提供"""
        if v in ("", None):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("gender", mode="before")
    @classmethod
    def _coerce_gender(cls, v):
        return None if v in ("", None) else str(v)

class ChatRequest(BaseModel):
    thread_id: str
    message: str

class TriageResponse(BaseModel):
    thread_id: str
    department_recommendation: Optional[str]
    urgency_level: Optional[str]
    triage_reason: Optional[str]
    final_response: Optional[str]
    next_question: Optional[str]
    turn_count: int
    is_final: bool
    slots: dict


# ── 辅助：从 LangGraph state 构造返回 ──
def _state_to_response(state: dict, thread_id: str) -> TriageResponse:
    msgs = state.get("messages", [])
    last_ai = None
    for m in reversed(msgs):
        if getattr(m, "type", "") == "ai":
            last_ai = m.content
            break

    is_final = state.get("final_response") is not None

    return TriageResponse(
        thread_id=thread_id,
        department_recommendation=state.get("department_recommendation"),
        urgency_level=state.get("urgency_level"),
        triage_reason=state.get("triage_reason"),
        final_response=state.get("final_response"),
        next_question=None if is_final else last_ai,
        turn_count=state.get("turn_count", 0),
        is_final=is_final,
        slots={
            "chief_complaint": state.get("chief_complaint"),
            "present_illness": state.get("present_illness"),
            "past_history": state.get("past_history"),
            "drug_allergy": state.get("drug_allergy"),
        },
    )


# ── 端点 ──
@app.post("/api/v1/triage/start", response_model=TriageResponse)
async def start_triage(req: StartRequest):
    graph = get_graph()
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    state = graph.invoke(
        {
            "messages": [HumanMessage(content=req.first_message)],
            "age": req.age,
            "gender": req.gender,
        },
        config,
    )
    return _state_to_response(state, thread_id)


@app.post("/api/v1/triage/chat", response_model=TriageResponse)
async def chat_triage(req: ChatRequest):
    graph = get_graph()
    config = {"configurable": {"thread_id": req.thread_id}}

    # MemorySaver 为进程内存储：服务重启后旧 thread 不存在，避免静默重置槽位
    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=409,
            detail="该会话已在服务重启后失效，请点击「新建预问诊」重新开始。",
        )

    # 先查现有 state（LangGraph MemorySaver 会自动恢复）
    state = graph.invoke(
        {"messages": [HumanMessage(content=req.message)]},
        config,
    )
    return _state_to_response(state, req.thread_id)


@app.get("/health")
async def health():
    return {"status": "ok", "milvus": "connectable", "model": settings.openai_model}


# ── 托管前端构建产物：直接运行 app.py 即可打开完整页面 ──
DIST_DIR = os.path.join(PROJECT_ROOT, "frontend", "dist")
UI_READY = os.path.isdir(DIST_DIR)
if UI_READY:
    # 挂载在 "/" 上，API 路由已先注册，不会被覆盖
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="ui")


# ── 命令行快速测试 ──
if __name__ == "__main__":
    import uvicorn

    if UI_READY:
        threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:8001/")).start()

    uvicorn.run(app, host="0.0.0.0", port=8001)
