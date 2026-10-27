"""
LangGraph 节点函数 —— 预问诊 Agent 的状态迁移单元

节点：
  entry       收到用户第一句话，启动槽位填充
  ask_slot    针对缺失槽位向用户追问（当前节点会返回等待用户输入）
  check_slots 检查四个槽位是否都已填满，或是否超限
  llm_extract 用户回复后，用 LLM 抽取 / 更新槽位
  triage      调用科室分诊规则 + LLM 辅助，输出推荐科室
  rag_search  用 Milvus 检索对应的诊疗指南证据
  finalize    组装最终响应（科室 + 急诊提示 + 指南摘录）
"""
from __future__ import annotations
import os, sys, json
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 项目根目录引导（脚本直接运行时能正确导入）
# agents/triage/nodes.py → 需向上 3 层到项目根
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 支持脚本直接运行和包导入两种方式
if __package__ is None or __package__ == "":
    from state import TriageState, SLOT_NAME_ZH
else:
    from .state import TriageState, SLOT_NAME_ZH
from tools.triage_rules import check_urgency, match_department, build_triage_reason


# ── LLM 客户端（复用 EduAgent 的 qwen-plus）──
def _get_llm():
    from langchain_openai import ChatOpenAI
    from config import settings
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=0.3,
    )


_LLM_EXTRACT_PROMPT = """你是一位资深全科医生助理，正在为患者做预问诊。
根据对话历史，更新四个槽位的信息。已有信息不要丢失，补充新信息。
槽位：
  chief_complaint: 患者最主要的不适症状
  present_illness: 症状的时长、程度、诱因、伴随症状
  past_history:    既往病史、手术史、家族史
  drug_allergy:    药物过敏史、用药禁忌

- 用户没有提及的槽位必须保留为空字符串 ""，禁止猜测或编造
- 只有当用户明确否认时（如"没有高血压""无过敏"），才把对应槽位填 "无"
- 已有内容不要重复堆砌，只需补充新信息
严格输出 JSON，不要其他内容，格式：
{{"chief_complaint":"...","present_illness":"...","past_history":"...","drug_allergy":"..."}}"""


def entry_node(state: TriageState) -> dict:
    """入口：仅首轮初始化槽位，多轮调用时保留已采集数据"""
    if state.get("initialized"):
        return {}
    return {
        "initialized": True,
        "turn_count": 0,
        "max_turns_exceeded": False,
        "pending_slots": ["chief_complaint", "present_illness", "past_history", "drug_allergy"],
        "asked_slots": [],
        "chief_complaint": None,
        "present_illness": None,
        "past_history": None,
        "drug_allergy": None,
    }


def _extract_slot_from_first_message(text: str) -> Optional[str]:
    """启发式：用户第一句话里如果已经包含主诉，提前填好 chief_complaint"""
    # 简单规则：有明显症状词就认为提供了主诉
    symptom_keywords = [
        "痛", "疼", "发烧", "咳嗽", "呕吐", "腹泻", "头痛", "头晕",
        "胸闷", "心慌", "出血", "皮疹", "肿胀", "失眠", "乏力",
    ]
    for kw in symptom_keywords:
        if kw in text:
            return text.strip()[:200]
    return None


def llm_extract_node(state: TriageState) -> dict:
    """用 LLM 从最新用户回复里抽取/更新槽位"""
    messages = state.get("messages", [])
    if not messages:
        return {}

    # 只取最后一条用户消息的增量内容
    last_human = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_human = m.content
            break

    if not last_human:
        return {}

    # 槽位全拼好直接跳过
    filled = sum(1 for s in ["chief_complaint","present_illness","past_history","drug_allergy"] if state.get(s))
    if filled >= 4:
        return {}

    # 构造上下文：已有槽位 + 最近对话
    existing = {k: state.get(k) or "" for k in ["chief_complaint","present_illness","past_history","drug_allergy"]}
    context_lines = ["### 当前已采集信息："]
    for k, v in existing.items():
        context_lines.append(f"- {SLOT_NAME_ZH[k]}: {v or '（未提供）'}")
    context_lines.append("\n### 最近对话：")
    for m in messages[-6:]:
        role = "患者" if isinstance(m, HumanMessage) else "医生"
        context_lines.append(f"- {role}：{m.content}")
    context_lines.append("\n请输出更新后的 JSON。")

    llm = _get_llm()
    try:
        resp = llm.invoke([SystemMessage(content=_LLM_EXTRACT_PROMPT), HumanMessage(content="\n".join(context_lines))])
        content = resp.content.strip()
        # 提取 JSON（LLM 偶尔会包 ```）
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        extracted = json.loads(content)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[llm_extract] parse failed: {e}, raw={content if 'content' in locals() else 'N/A'}")
        extracted = {}

    updates = {}
    for slot in ["chief_complaint","present_illness","past_history","drug_allergy"]:
        val = (extracted.get(slot) or "").strip()
        if not val or val in ("（未提供）", "未提供"):
            continue
        old = state.get(slot)
        if not old:
            updates[slot] = val
            continue
        if val == old or val in old:
            continue                      # 没有新信息，避免重复堆砌
        if old in val:
            updates[slot] = val           # 新值更完整，直接覆盖
            continue
        if str(old).strip() in ("无", "否认"):
            updates[slot] = val           # 之前记为"无"，现在补充了具体病史
            continue
        if val in ("无", "否认") and slot in ("past_history", "drug_allergy"):
            continue                      # 已有病史时不追加"无"
        updates[slot] = f"{old}；{val}"

    return updates


_SLOT_PRIORITY = ["chief_complaint", "present_illness", "past_history", "drug_allergy"]

# LLM 不可用时的兜底模板
_ASK_TEMPLATES = {
    "chief_complaint": "您好，请问您今天主要是哪里不舒服？",
    "present_illness": "这种情况持续多久了？还有没有其他伴随症状？",
    "past_history": "您以前有没有慢性病史（比如高血压、糖尿病）、手术史或者家族遗传病史？",
    "drug_allergy": "您有没有药物过敏史，或者正在服用什么特殊药物？",
}

_ASK_PROMPT = """你是三甲医院预问诊助手，正在通过多轮对话采集患者信息。
本轮必须追问【{slot_zh}】。要求：
1. 先用一句话自然承接患者上一句回答，不要评价、不要下诊断
2. 再提出一个简短口语化的问题，引导患者回答【{slot_zh}】
3. 不要重复之前已经问过的问题原句
4. 总字数不超过 50 字
5. 只输出这句话本身，不要加引号、编号或解释"""


def _pick_slot(state: TriageState) -> Optional[str]:
    """优先追问从未问过的缺失槽位；若都问过仍未采到，再确认优先级最高的那个"""
    missing = [s for s in _SLOT_PRIORITY if not state.get(s)]
    if not missing:
        return None
    asked = state.get("asked_slots") or []
    for s in missing:
        if s not in asked:
            return s
    return missing[0]


def _generate_question(state: TriageState, slot: str) -> str:
    """用 LLM 结合上下文生成追问；失败时回退到固定模板"""
    recent_lines = []
    for m in state.get("messages", [])[-6:]:
        role = "患者" if isinstance(m, HumanMessage) else "医生"
        recent_lines.append(f"{role}：{m.content}")
    filled = {SLOT_NAME_ZH[k]: state.get(k) for k in _SLOT_PRIORITY if state.get(k)}
    context = "已采集信息：" + ("；".join(f"{k}={v}" for k, v in filled.items()) or "无")

    try:
        llm = _get_llm()
        resp = llm.invoke([
            SystemMessage(content=_ASK_PROMPT.format(slot_zh=SLOT_NAME_ZH[slot])),
            HumanMessage(content=f"{context}\n\n最近对话：\n" + "\n".join(recent_lines)),
        ])
        q = (resp.content or "").strip().strip('"“”').strip()
        return q or _ASK_TEMPLATES[slot]
    except Exception as e:
        print(f"[ask_slot] question generation failed: {e}")
        return _ASK_TEMPLATES[slot]


def ask_slot_node(state: TriageState) -> dict:
    """
    针对缺失槽位构造追问问题。
    问题由 LLM 结合上下文生成（不会多轮重复同一句），并记录已问槽位。
    """
    filled_count = sum(1 for s in _SLOT_PRIORITY if state.get(s))
    if filled_count >= 4:
        return {}

    next_slot = _pick_slot(state)
    if not next_slot:
        return {}

    question = _generate_question(state, next_slot)

    asked = list(state.get("asked_slots") or [])
    if next_slot not in asked:
        asked.append(next_slot)

    return {
        "messages": [AIMessage(content=question)],
        "turn_count": state.get("turn_count", 0) + 1,
        "pending_slots": [p for p in state.get("pending_slots", []) if p != next_slot],
        "asked_slots": asked,
    }


def check_slots_node(state: TriageState) -> str:
    """
    判断槽位是否已满、轮次是否超限。
    返回路由结果：'continue' 继续追问 / 'done' 进入分诊
    """
    turns = state.get("turn_count", 0)
    max_turns = 5  # 与 config 保持一致
    filled = sum(1 for s in ["chief_complaint","present_illness","past_history","drug_allergy"] if state.get(s))

    if turns >= max_turns:
        return "done"
    if filled >= 4:
        return "done"

    # 还有槽位没填
    return "continue"


def triage_node(state: TriageState) -> dict:
    """
    科室分诊：规则优先（带年龄/性别推断）+ LLM 兜底。
    """
    from tools.triage_rules import normalize_dept_name, STANDARD_DEPTS

    # 拼合所有文本供规则与 LLM 使用
    all_text_parts = [
        state.get("chief_complaint") or "",
        state.get("present_illness") or "",
        state.get("past_history") or "",
        state.get("drug_allergy") or "",
    ]
    all_text = " ".join(t for t in all_text_parts if t).strip()

    # 结合 age/gender 参数 + 文本推断
    age = state.get("age")
    gender = state.get("gender")
    urgency, hits = check_urgency(all_text)
    dept, dept_hits = match_department(all_text, age=age, gender=gender)

    # 规则没命中 → LLM 兜底
    if not dept:
        llm = _get_llm()
        dept_guess = llm.invoke([
            SystemMessage(content=f"你是三甲医院分诊台医生，只能从以下标准科室中选一个：{'、'.join(sorted(STANDARD_DEPTS))}。只输出科室名，不要其他内容。"),
            HumanMessage(content=f"症状：{all_text}"),
        ]).content.strip()
        import re
        # 正则匹配标准科室集合
        m = re.search(r"(急诊科|呼吸内科|消化内科|心血管内科|神经内科|肾内科|内分泌科|儿科|妇产科|骨科|皮肤科|眼科|耳鼻喉科|口腔科|普外科|全科医学科)", dept_guess)
        dept = m.group(1) if m else dept_guess[:30]

    # 规范化科室名称
    dept = normalize_dept_name(dept)

    reason = build_triage_reason(dept, urgency, list(set(hits + dept_hits)))

    return {
        "department_recommendation": dept,
        "urgency_level": urgency,
        "triage_reason": reason,
        "max_turns_exceeded": state.get("turn_count", 0) >= 5,
    }


def finalize_node(state: TriageState) -> dict:
    """组装最终响应：问候 + 分诊 + 指南引用 + 紧急提示"""
    dept = state.get("department_recommendation", "全科医学科")
    urgency = state.get("urgency_level", "green")
    reason = state.get("triage_reason", "")
    evences = state.get("rag_evidence", [])

    urgency_tips = {
        "red": "⚠️ 您的症状提示可能存在急症风险，请立即拨打 120 或前往最近医院急诊室，不要自行前往！",
        "yellow": "⚠️ 建议尽快就医，不要拖延。",
        "green": "请根据推荐科室前往门诊挂号就诊。",
    }

    lines = [
        "🏥 预问诊完成",
        f"📌 推荐科室：**{dept}**",
        f"🚨 风险等级：{urgency_tips[urgency]}",
        "",
        "**分诊依据：**",
        reason,
    ]

    if evences:
        lines.append("")
        lines.append("**参考诊疗指南：**")
        for i, ev in enumerate(evences[:3], 1):
            src = ev.get("source", "指南")
            content = ev.get("content", "")[:120]
            lines.append(f"{i}. [{src}] {content}{'…' if len(content)>=120 else ''}")

    if state.get("max_turns_exceeded"):
        lines.append("")
        lines.append("_（提示：追问已达上限，部分信息未采集完整，分诊结果仅供参考）_")

    return {"final_response": "\n".join(lines)}
