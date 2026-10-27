"""
评测集生成器 —— 自动生成 300 条带标注的预问诊测试样本

覆盖 10 个科室 × 30 条 = 300 条：
  呼吸内科 / 消化内科 / 心血管内科 / 神经内科 / 肾内科 /
  内分泌科 / 儿科 / 妇产科 / 骨科 / 皮肤科 + 急诊科（红线 case）

输出：data/eval/triage_eval_300.jsonl
      每行 JSON: {id, age, gender, symptom_description, expected_department, expected_urgency, notes}
"""
from __future__ import annotations
import os, sys, json, random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import settings


# ── 模板：(症状模板列表, 正确科室, 正确风险, 可选 age/gender 约束) ──
DEPT_TEMPLATES = {
    "呼吸内科": [
        (["咳嗽 {d}，还有点发烧 {t}", "我咳嗽好几天了，还咳痰 {c}", "感冒发烧咳嗽，嗓子也痛"],
         "呼吸内科", "green", None),
        (["咳嗽发烧 {d} 天，胸闷气短", "发热 38.9℃ 伴咳嗽胸痛"],
         "呼吸内科", "yellow", None),
        (["咳嗽伴咯血 {d} 口", "咳痰带血"], "呼吸内科", "yellow", None),
    ],
    "消化内科": [
        (["肚子痛拉肚子 {d} 次", "胃痛反酸好几天了", "腹胀便秘，吃不下饭"], "消化内科", "green", None),
        (["剧烈腹痛伴呕吐 {d} 天", "呕血黑便"], "消化内科", "yellow", None),
        (["吃完饭就胃痛，空腹反而好点", "十二指肠溃疡那种痛"], "消化内科", "green", None),
    ],
    "心血管内科": [
        (["胸口闷痛 {d} 分钟，休息能缓解", "心慌心悸，心跳快", "高血压头有点晕"], "心血管内科", "green", None),
        (["胸痛伴大汗，持续 {d} 分钟不缓解", "胸口压榨感，要晕倒了"], "急诊科", "red", None),
        (["血压高到 180/110，头痛想吐", "高血压危象"], "急诊科", "red", None),
    ],
    "神经内科": [
        (["头痛头晕 {d} 天", "失眠多梦睡不好", "手脚有点发麻"], "神经内科", "green", None),
        (["突发半边身体不能动，说话不清楚", "中风了感觉"], "急诊科", "red", None),
        (["这辈子最剧烈的头痛，要炸了", "蛛网膜下腔出血那种痛"], "急诊科", "red", None),
    ],
    "肾内科": [
        (["腰痛腰酸 {d} 天", "小便有泡沫", "尿频尿急尿痛"], "肾内科", "green", None),
        (["小便带血，腰部绞痛", "肾绞痛那种痛"], "急诊科", "yellow", None),
    ],
    "内分泌科": [
        (["血糖有点高，多饮多尿", "最近瘦了 {w} 斤", "甲状腺肿大，手抖"], "内分泌科", "green", None),
        (["糖尿病昏迷，叫不醒", "低血糖/高渗昏迷"], "急诊科", "red", None),
    ],
    "儿科": [
        (["宝宝发烧 {d} 天，咳嗽", "小孩拉肚子 {d} 次，水样便", "婴儿湿疹很痒"], "儿科", "green", "ped"),
        (["{m} 个月宝宝发烧 39℃ 抽搐了", "婴儿高热惊厥"], "急诊科", "red", "ped"),
        (["{m} 个月宝宝吐了 {d} 次，没尿", "婴儿脱水"], "急诊科", "yellow", "ped"),
    ],
    "妇产科": [
        (["阴道出血，月经不调", "白带多有异味，外阴痒", "痛经痛得厉害"], "妇产科", "green", "female"),
        (["停经 {w} 周，突然下腹痛加出血", "宫外孕破裂？"], "急诊科", "red", "female"),
        (["怀孕 {m} 周，阴道大量出血", "胎盘早剥？"], "急诊科", "red", "female"),
    ],
    "骨科": [
        (["摔了一跤，膝盖痛 {d} 天", "腰痛腿麻，直不起来", "颈椎病，脖子痛手麻"], "骨科", "green", None),
        (["外伤后腿畸形，不能动", "开放性骨折，骨头露出来了"], "急诊科", "red", None),
        (["车祸后颈痛，手脚麻木", "脊髓损伤？"], "急诊科", "red", None),
    ],
    "皮肤科": [
        (["身上起皮疹很痒 {d} 天", "脸上长痘痘痤疮", "皮肤发红发烫"], "皮肤科", "green", None),
    ],
}

# 变量填充器
def _fill(template: str, seed: int = 0) -> str:
    r = random.Random(seed)
    replacements = {
        "{d}": lambda: str(r.randint(1, 7)),
        "{t}": lambda: str(r.randint(37, 40)) + "℃",
        "{c}": lambda: random.choice(["白色", "黄色", "绿色脓性"]),
        "{w}": lambda: str(r.randint(3, 15)),
        "{m}": lambda: str(r.randint(2, 12)),
    }
    out = template
    for key, fn in replacements.items():
        while key in out:
            out = out.replace(key, fn(), 1)
    return out


def generate(n_per_dept: int = 30) -> list:
    """为每个科室生成 n_per_dept 条样本，合计约 300 条"""
    random.seed(42)
    samples = []
    sid = 0

    # 科室优先级：呼吸/消化/心血管/神经/儿科/妇产/骨科/皮肤/肾内/内分泌 = 10 个
    depts = list(DEPT_TEMPLATES.keys())
    # 每科室 30 条 → 10 × 30 = 300
    for dept in depts:
        templates = DEPT_TEMPLATES[dept]
        # 给每类模板分配大致比例（急诊模板少一些）
        weighted = []
        for tpls, exp_dept, urg, age_fn in templates:
            weight = 3 if exp_dept == "急诊科" else 7
            weighted.extend([(tpls, exp_dept, urg, age_fn)] * weight)

        for i in range(n_per_dept):
            tpls, exp_dept, urg, age_fn = random.choice(weighted)
            tpl = random.choice(tpls)
            symptom = _fill(tpl, seed=sid)

            # 年龄/性别（age_fn 约定：None=通用; "ped"=儿科 age<14; "female"=女性）
            if age_fn == "ped":
                age = random.randint(0, 14)
                gender = random.choice(["M", "F"])
            elif age_fn == "female":
                age = random.randint(16, 55)
                gender = "F"
            elif age_fn == "male":
                age = random.randint(18, 70)
                gender = "M"
            else:
                age = random.randint(18, 75)
                gender = random.choice(["M", "F"])

            samples.append({
                "id": f"S{sid:04d}",
                "age": age,
                "gender": gender,
                "symptom_description": symptom,
                "expected_department": exp_dept,
                "expected_urgency": urg,
                "notes": f"模板={tpl[:30]}",
            })
            sid += 1

    # 打乱（保留标注不变）
    random.shuffle(samples)
    return samples


def main():
    out_dir = settings.eval_dir
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "triage_eval_300.jsonl")

    samples = generate(30)
    with open(out_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # 打印分布统计
    from collections import Counter
    dept_cnt = Counter(s["expected_department"] for s in samples)
    urg_cnt = Counter(s["expected_urgency"] for s in samples)
    print(f"✅ 生成 {len(samples)} 条样本 → {out_path}")
    print(f"   科室分布: {dict(dept_cnt)}")
    print(f"   风险分布: {dict(urg_cnt)}")


if __name__ == "__main__":
    main()
