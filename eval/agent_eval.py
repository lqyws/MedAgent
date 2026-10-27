"""
Agent 评测 —— 跑完整 LangGraph 预问诊流程（槽位填充 → 分诊 → RAG）

作用：验证多轮追问 + 规则分诊 + RAG 综合推理的效果，与 baseline 对照计算提升幅度
输出：data/eval/agent_result.json（含逐条预测 + 总体 Top-1 准确率 + 平均追问轮次）
"""
from __future__ import annotations
import os, sys, json, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import HumanMessage
from config import settings


def run_one(graph, symptom: str, thread_id: str, age=None, gender=None):
    """
    模拟真实多轮对话：Agent 追问 → 用规则模拟用户回答 → 循环直到 final_response。
    返回 (预测科室, 预测风险, 实际追问轮次, state)
    """
    config = {"configurable": {"thread_id": thread_id}}

    # 简单的用户模拟回答（针对不同槽位）
    def _simulate_answer(question: str) -> str:
        """根据 Agent 追问内容返回一个简单回答。"""
        if "哪里" in question or "不舒服" in question:
            return symptom  # 第一次追问可能是主诉
        if "持续" in question or "多久" in question or "伴随" in question or "其他" in question:
            return "大概两三天了，还有点不舒服"
        if "病史" in question or "手术" in question or "遗传" in question:
            return "没有慢性病史，家里也没有遗传病"
        if "过敏" in question or "药物" in question or "特殊" in question:
            return "没有药物过敏史"
        return "暂时没有其他不适"

    # 第 1 轮：用户给初始症状（把 age/gender 也注入 state 供 triage_node 使用）
    init_input = {
        "messages": [HumanMessage(content=symptom)],
        "age": age,
        "gender": gender,
    }
    state = graph.invoke(init_input, config)

    # 后续轮次：Agent 还没给最终分诊结果 → 模拟用户继续回答
    max_user_turns = 5
    for _ in range(max_user_turns):
        if state.get("final_response"):
            break

        # 从 Agent 的最新 AIMessage 里取追问内容
        msgs = state.get("messages", [])
        last_ai_msg = ""
        for m in reversed(msgs):
            if getattr(m, "type", "") == "ai":
                last_ai_msg = m.content
                break

        if not last_ai_msg:
            break

        user_reply = _simulate_answer(last_ai_msg)
        state = graph.invoke(
            {"messages": [HumanMessage(content=user_reply)]},
            config,
        )

    dept = state.get("department_recommendation", "unknown")
    urg = state.get("urgency_level", "unknown")
    turns = state.get("turn_count", 0)

    # 归一化
    dept_norm = dept or "unknown"
    if "急诊科" in dept_norm:
        dept_norm = "急诊科"

    return dept_norm, urg, turns, state


def run(limit: int = None, resume: bool = True):
    """评测集上跑 Agent"""
    # 延迟 import（避免 Milvus 未启动时卡死）
    from agents.triage.graph import get_graph

    eval_path = os.path.join(settings.eval_dir, "triage_eval_300.jsonl")
    if not os.path.exists(eval_path):
        print(f"[agent_eval] 评测集不存在，请先运行 generate_eval_set.py")
        sys.exit(1)

    graph = get_graph()
    samples = [json.loads(l) for l in open(eval_path, encoding="utf-8")]
    if limit:
        samples = samples[:limit]

    # 断点续跑
    out_path = os.path.join(settings.eval_dir, "agent_result.json")
    already_done_ids = set()
    existing_results = []
    if resume and os.path.exists(out_path):
        prev = json.load(open(out_path, encoding="utf-8"))
        for r in prev.get("results", []):
            already_done_ids.add(r["id"])
        existing_results = prev.get("results", [])
        print(f"[agent_eval] 断点续跑：已完成 {len(already_done_ids)} 条")

    correct_dept = 0
    correct_urg = 0
    turn_sum = 0
    total = 0
    results = list(existing_results)

    for i, s in enumerate(samples):
        if s["id"] in already_done_ids:
            total += 1
            if any(r["id"] == s["id"] for r in existing_results):
                r = [x for x in existing_results if x["id"] == s["id"]][0]
                if r["dept_correct"]:
                    correct_dept += 1
                if r["urg_correct"]:
                    correct_urg += 1
                turn_sum += r["turns_used"]
            continue

        thread_id = f"eval-{s['id']}"
        try:
            dept, urg, turns, state = run_one(
                graph, s["symptom_description"], thread_id,
                age=s.get("age"), gender=s.get("gender"),
            )
        except Exception as e:
            print(f"  [WARN] {s['id']} failed: {e}")
            dept, urg, turns = "ERROR", "ERROR", 0

        # 宽松匹配：急诊科/儿科方向匹配放宽
        dept_hit = (dept == s["expected_department"]) or \
                   ("急诊科" in dept and "急诊科" in s["expected_department"]) or \
                   ("儿科" in dept and "儿科" in s["expected_department"]) or \
                   (dept.startswith("儿科（") and "儿科" in s["expected_department"])
        urg_hit = (urg == s["expected_urgency"])

        if dept_hit:
            correct_dept += 1
        if urg_hit:
            correct_urg += 1
        turn_sum += turns
        total += 1

        results.append({
            "id": s["id"],
            "symptom": s["symptom_description"],
            "age": s.get("age"),
            "gender": s.get("gender"),
            "expected_dept": s["expected_department"],
            "predicted_dept": dept,
            "dept_correct": dept_hit,
            "expected_urg": s["expected_urgency"],
            "predicted_urg": urg,
            "urg_correct": urg_hit,
            "turns_used": turns,
        })

        if (i + 1) % 5 == 0:
            avg_turn = turn_sum / max(total, 1)
            print(f"  progress {i+1}/{len(samples)}  dept_acc={correct_dept/total:.3f}  urg_acc={correct_urg/total:.3f}  avg_turns={avg_turn:.2f}")

        # 中途保存
        if (i + 1) % 10 == 0:
            _save(results, total, correct_dept, correct_urg, turn_sum, out_path)

    _save(results, total, correct_dept, correct_urg, turn_sum, out_path, final=True)


def _save(results, total, cd, cu, ts, path, final=False):
    summary = {
        "total": total,
        "dept_top1_acc": cd / max(total, 1),
        "urgency_acc": cu / max(total, 1),
        "avg_turns": ts / max(total, 1),
        "results": results,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if final:
        print(f"\n✅ Agent 评测完成")
        print(f"   样本数: {total}")
        print(f"   科室 Top-1 准确率: {summary['dept_top1_acc']:.4f}")
        print(f"   急诊风险准确率: {summary['urgency_acc']:.4f}")
        print(f"   平均追问轮次: {summary['avg_turns']:.2f}")
        print(f"   结果 → {path}")


def compare(baseline_path=None, agent_path=None):
    """对比 baseline vs agent，打印提升幅度"""
    baseline_path = baseline_path or os.path.join(settings.eval_dir, "baseline_result.json")
    agent_path = agent_path or os.path.join(settings.eval_dir, "agent_result.json")
    if not os.path.exists(baseline_path) or not os.path.exists(agent_path):
        print("[compare] 请先运行 baseline_eval.py 和 agent_eval.py")
        return
    b = json.load(open(baseline_path, encoding="utf-8"))
    a = json.load(open(agent_path, encoding="utf-8"))
    delta_dept = a["dept_top1_acc"] - b["dept_top1_acc"]
    delta_urg = a["urgency_acc"] - b["urgency_acc"]
    print("=" * 60)
    print("Baseline vs Agent 对比")
    print("=" * 60)
    print(f"{'指标':<20}{'Baseline':>12}{'Agent':>12}{'提升':>12}")
    print("-" * 60)
    print(f"{'科室 Top-1 准确率':<18}{b['dept_top1_acc']:>12.4f}{a['dept_top1_acc']:>12.4f}{delta_dept:>+12.4f}")
    print(f"{'急诊风险准确率':<18}{b['urgency_acc']:>12.4f}{a['urgency_acc']:>12.4f}{delta_urg:>+12.4f}")
    print(f"{'平均追问轮次':<20}{'-':>12}{a['avg_turns']:>12.2f}{'-':>12}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条")
    parser.add_argument("--compare", action="store_true", help="对比 baseline vs agent")
    args = parser.parse_args()
    if args.compare:
        compare()
    else:
        run(limit=args.limit)
