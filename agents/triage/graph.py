"""
LangGraph 状态图定义 —— 预问诊 Agent 的完整流转

图结构：
  START → entry → llm_extract ──(条件)──► ask_slot → (条件) ask_slot / triage
                                     │
                                     └──► triage → rag_search → finalize → END

条件路由逻辑：check_slots_node(state) 返回 'continue' 继续追问 / 'done' 进入分诊
"""
from __future__ import annotations
import os, sys

# agents/triage/graph.py → 向上 3 层到项目根 MedAgent/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 支持脚本直接运行（python agents/triage/graph.py）和包导入两种方式
if __package__ is None or __package__ == "":
    from state import TriageState
    from nodes import (
        entry_node, llm_extract_node, ask_slot_node,
        check_slots_node, triage_node, finalize_node,
    )
else:
    from .state import TriageState
    from .nodes import (
        entry_node, llm_extract_node, ask_slot_node,
        check_slots_node, triage_node, finalize_node,
    )
from tools.guideline_rag import rag_search_node


def build_graph():
    """构建并编译 LangGraph 预问诊 Agent"""
    g = StateGraph(TriageState)

    # ── 节点注册 ──
    g.add_node("entry", entry_node)
    g.add_node("llm_extract", llm_extract_node)
    g.add_node("ask_slot", ask_slot_node)
    g.add_node("triage", triage_node)
    g.add_node("rag_search", rag_search_node)
    g.add_node("finalize", finalize_node)

    # ── 固定边 ──
    g.set_entry_point("entry")
    g.add_edge("entry", "llm_extract")
    g.add_edge("ask_slot", END)          # 每轮只问一个问题，结束本轮等待用户回复
    g.add_edge("triage", "rag_search")
    g.add_edge("rag_search", "finalize")
    g.add_edge("finalize", END)

    # ── 条件边：槽位是否填满 ──
    def _route(state: TriageState) -> str:
        return "ask_slot" if check_slots_node(state) == "continue" else "triage"

    g.add_conditional_edges(
        "llm_extract",
        _route,
        {"ask_slot": "ask_slot", "triage": "triage"},
    )

    # ── 编译（带 MemorySaver 支持多轮会话持久化）──
    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


# 模块级单例，避免重复编译
GRAPH = None
def get_graph():
    global GRAPH
    if GRAPH is None:
        GRAPH = build_graph()
    return GRAPH


if __name__ == "__main__":
    # 快速自测：从用户一句话开始跑完整图
    from langchain_core.messages import HumanMessage

    agent = get_graph()
    thread_id = "test-001"
    config = {"configurable": {"thread_id": thread_id}}

    state = {}
    # 第 1 轮：用户给初始症状
    state = agent.invoke({"messages": [HumanMessage(content="我咳嗽发烧三天了，还有点胸闷")]}, config)
    # 第 2 轮：模拟用户继续回复（messages 使用 add_messages 累加，无需重复传历史）
    state = agent.invoke({"messages": [HumanMessage(content="没有药物过敏史，以前有高血压")]}, config)

    print("=== FINAL STATE ===")
    for k, v in state.items():
        if k == "messages":
            continue
        print(f"  {k}: {v}")
