"""
LangGraph State Schema —— 预问诊 Agent 的状态机载体

四个核心槽位：
  chief_complaint   主诉
  present_illness   现病史
  past_history      既往史
  drug_allergy      用药禁忌（过敏史）

流转：entry → ask_slot → check_slots ─(未满)→ ask_slot
                                  └(已满/超限)→ triage → rag → output
"""
from __future__ import annotations
from typing import TypedDict, Optional, Literal, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TriageState(TypedDict, total=False):
    # ── 会话标记 ──
    initialized: Optional[bool]                  # entry 仅首次初始化，避免多轮时重置槽位

    # ── 用户基础信息 ──
    age: Optional[int]                           # 年龄（可选，评测时会传入）
    gender: Optional[str]                        # 性别（可选）

    # ── 对话层 ──
    messages: Annotated[List[BaseMessage], add_messages]  # 完整对话历史（多轮累加）
    turn_count: int                             # 当前追问轮次
    max_turns_exceeded: bool                    # 是否超过追问上限

    # ── 槽位层（四个预问诊核心槽位）──
    chief_complaint: Optional[str]              # 主诉
    present_illness: Optional[str]              # 现病史
    past_history: Optional[str]                 # 既往史
    drug_allergy: Optional[str]                 # 用药禁忌

    # ── 缺失槽位队列（由 LLM 判断还需要补什么）──
    pending_slots: List[Literal[
        "chief_complaint", "present_illness", "past_history", "drug_allergy"
    ]]
    # ── 已追问过的槽位（避免同一问题无限重复）──
    asked_slots: List[str]

    # ── 分诊输出 ──
    department_recommendation: Optional[str]    # 推荐科室
    urgency_level: Optional[Literal["green", "yellow", "red"]]  # 急诊风险
    triage_reason: Optional[str]                # 分诊依据（规则/LLM 推理）

    # ── RAG 层 ──
    rag_evidence: List[dict]                    # 检索到的指南片段 [{source, content}]

    # ── 最终响应 ──
    final_response: Optional[str]


SLOT_NAME_ZH = {
    "chief_complaint": "主诉",
    "present_illness": "现病史",
    "past_history": "既往史",
    "drug_allergy": "用药禁忌/过敏史",
}
