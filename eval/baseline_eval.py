"""
Baseline 评测 —— 用 LLM zero-shot 直接从症状文本推荐科室

作用：作为"无 Agent 流程"的基线对照，用来衡量完整 LangGraph 预问诊流程的提升幅度
输出：data/eval/baseline_result.json（含逐条预测 + 总体 Top-1 准确率）
"""
from __future__ import annotations
import os, sys, json, time
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings


# 标准科室列表（约束 LLM 输出）
STANDARD_DEPTS = [
    "急诊科", "呼吸内科", "消化内科", "心血管内科", "神经内科",
    "肾内科", "内分泌科", "儿科", "妇产科", "骨科", "皮肤科",
    "眼科", "耳鼻喉科", "口腔科", "普外科", "全科医学科",
]

PROMPT = """你是三甲医院分诊台医生。根据患者症状，从下列标准科室中选择一个最合适的推荐科室。
标准科室：{depts}
只输出科室名称，不要其他内容。"""

URGENCY_PROMPT = """根据患者症状，判断急诊风险等级。
红色 red = 危及生命需立即 120；黄色 yellow = 建议尽快就医；绿色 green = 常规门诊。
只输出 red / yellow / green。"""


def predict_one(llm: ChatOpenAI, symptom: str):
    # 科室
    resp1 = llm.invoke([
        SystemMessage(content=PROMPT.format(depts="、".join(STANDARD_DEPTS))),
        HumanMessage(content=symptom),
    ])
    import re
    text = resp1.content.strip()
    m = re.search(r"(" + "|".join(STANDARD_DEPTS) + r")", text)
    dept = m.group(1) if m else text[:20]

    # 风险
    resp2 = llm.invoke([
        SystemMessage(content=URGENCY_PROMPT),
        HumanMessage(content=symptom),
    ])
    urg_text = resp2.content.strip().lower()
    if "red" in urg_text:
        urg = "red"
    elif "yellow" in urg_text:
        urg = "yellow"
    else:
        urg = "green"

    return dept, urg


def run(limit: int = None):
    eval_path = os.path.join(settings.eval_dir, "triage_eval_300.jsonl")
    if not os.path.exists(eval_path):
        print(f"[baseline] 评测集不存在，请先运行 generate_eval_set.py")
        sys.exit(1)

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=0,
    )

    samples = [json.loads(l) for l in open(eval_path, encoding="utf-8")]
    if limit:
        samples = samples[:limit]

    results = []
    correct_dept = 0
    correct_urg = 0
    total = len(samples)

    for i, s in enumerate(samples):
        dept, urg = predict_one(llm, s["symptom_description"])
        dept_hit = (dept == s["expected_department"]) or \
                   (s["expected_department"] == "急诊科" and dept == "急诊科") or \
                   ("急诊科" in dept and "急诊科" in s["expected_department"])
        urg_hit = (urg == s["expected_urgency"])
        if dept_hit:
            correct_dept += 1
        if urg_hit:
            correct_urg += 1

        results.append({
            "id": s["id"],
            "symptom": s["symptom_description"],
            "expected_dept": s["expected_department"],
            "predicted_dept": dept,
            "dept_correct": dept_hit,
            "expected_urg": s["expected_urgency"],
            "predicted_urg": urg,
            "urg_correct": urg_hit,
        })

        if (i + 1) % 10 == 0:
            print(f"  progress {i+1}/{total}  dept_acc={correct_dept/(i+1):.3f}  urg_acc={correct_urg/(i+1):.3f}")

        # 控制 API 频率
        time.sleep(0.3)

    summary = {
        "model": settings.openai_model,
        "total": total,
        "dept_top1_acc": correct_dept / total,
        "urgency_acc": correct_urg / total,
        "results": results,
    }

    out_path = os.path.join(settings.eval_dir, "baseline_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Baseline 评测完成")
    print(f"   样本数: {total}")
    print(f"   科室 Top-1 准确率: {summary['dept_top1_acc']:.4f}")
    print(f"   急诊风险准确率: {summary['urgency_acc']:.4f}")
    print(f"   结果 → {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条（调试用）")
    args = parser.parse_args()
    run(limit=args.limit)
