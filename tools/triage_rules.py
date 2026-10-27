"""
科室分诊规则工具 —— 结构化症状关键词 → 科室映射 + 急诊触发条件

设计原则：
  1. 急诊触发条件优先（胸痛/呼吸困难/意识丧失/大出血/高热惊厥 → 红色）
  2. 多系统主诉按急诊 > 专科 > 综合的优先级
  3. 关键词匹配而非纯 LLM 推理，可解释、可评测
"""
from __future__ import annotations
import re
from typing import List, Tuple, Literal, Optional


URGENCY_RED_KEYWORDS: List[str] = [
    "胸痛", "压榨", "濒死",
    "呼吸困难", "窒息", "不能呼吸",
    "意识丧失", "昏迷", "晕倒", "昏厥",
    "大出血", "大量出血", "失血",
    "高热惊厥", "抽搐", "癫痫持续",
    "剧烈头痛", "喷射性呕吐",
    "肢体瘫痪", "偏瘫", "不能动",
    "言语不清", "说话不清楚", "口歪",
    "突发偏瘫", "肢体无力", "肢体麻木",  # 脑卒中
    "剧烈腹痛伴休克",
    "妊娠出血", "胎盘早剥", "宫外孕破裂",
    "颈部外伤", "颈痛伴肢体",
    "严重外伤", "开放性骨折",
]

URGENCY_YELLOW_KEYWORDS: List[str] = [
    "持续呕吐", "脱水",
    "孕妇出血",
    "婴幼儿高热",
    "持续高热超过3天",
    "精神萎靡",
    "肾绞痛", "血尿", "小便带血",
    "持续胸痛超过15分钟",
    "剧烈腹痛", "急腹症",
    "意识模糊", "意识障碍",
    "高热抽搐", "惊厥",
]

# 年龄暗示词 → 儿科（没年龄参数时从症状文本推断）
PED_HINT_KEYWORDS = ["宝宝", "小孩", "婴儿", "孩子", "幼儿", "新生儿"]
# 性别暗示词 → 妇产科
FEMALE_HINT_KEYWORDS = ["怀孕", "停经", "月经", "阴道", "白带", "妇科", "痛经", "妊娠"]

# 科室 → 症状关键词列表（可扩展）
DEPARTMENT_RULES: dict = {
    "呼吸内科": [
        "咳嗽", "咳痰", "气喘", "气短", "胸闷", "咽痛", "扁桃体",
        "鼻塞", "流涕", "感冒", "发烧", "发热", "肺部", "支气管炎",
        "肺炎", "哮喘", "呼吸困难",
    ],
    "消化内科": [
        "胃痛", "腹痛", "腹胀", "腹泻", "拉肚子", "便秘", "便血",
        "呕血", "反酸", "烧心", "打嗝", "消化不良", "恶心", "呕吐",
        "胃炎", "胃溃疡", "十二指肠", "肠炎", "肝功能", "肝炎",
    ],
    "心血管内科": [
        "胸痛", "胸闷", "心慌", "心悸", "心律不齐", "早搏",
        "血压高", "高血压", "血压低", "低血压", "头晕", "心脏",
        "冠心病", "心绞痛", "心梗",
    ],
    "神经内科": [
        "头痛", "头晕", "眩晕", "失眠", "睡不着", "多梦",
        "肢体麻木", "手脚麻", "偏瘫", "言语不清",
        "中风", "脑梗", "脑出血", "癫痫", "抽搐",
    ],
    "肾内科": [
        "腰痛", "腰酸", "血尿", "蛋白尿", "尿频", "尿急", "尿痛",
        "小便", "排尿", "浮肿", "水肿", "肾功能", "肾炎",
    ],
    "内分泌科": [
        "血糖高", "糖尿病", "多饮", "多尿", "体重下降",
        "甲状腺", "甲亢", "甲减", "手抖", "出汗多",
    ],
    "儿科": [
        # 通过年龄判断，不单独列关键词
    ],
    "妇产科": [
        "下腹痛", "妇科", "阴道出血", "月经", "痛经", "白带",
        "子宫肌瘤", "卵巢", "怀孕", "妊娠",
    ],
    "骨科": [
        "骨折", "扭伤", "外伤", "疼痛", "关节痛", "腰痛",
        "颈椎病", "腰椎", "膝盖痛", "肩痛", "脱臼",
    ],
    "皮肤科": [
        "皮疹", "过敏", "湿疹", "荨麻疹", "痘痘", "痤疮",
        "皮肤瘙痒", "皮肤发红", "带状疱疹",
    ],
    "眼科": [
        "眼睛痛", "眼痛", "视力模糊", "视力下降", "红眼", "流泪",
        "近视", "白内障",
    ],
    "耳鼻喉科": [
        "耳朵痛", "耳鸣", "听力下降", "鼻塞", "鼻炎", "鼻窦炎",
        "喉咙痛", "咽炎", "扁桃体炎",
    ],
    "口腔科": [
        "牙痛", "牙龈", "口腔溃疡", "嘴唇", "口干",
    ],
    "普外科": [
        "阑尾炎", "胆囊炎", "胆结石", "疝气", "肛门", "痔疮",
        "急性腹痛",
    ],
}


# 急诊触发判断
def check_urgency(text: str) -> Tuple[Literal["red", "yellow", "green"], List[str]]:
    """返回 (风险等级, 命中的关键词列表)"""
    hits: List[str] = []
    for kw in URGENCY_RED_KEYWORDS:
        if kw in text:
            hits.append(kw)
    if hits:
        return "red", hits
    for kw in URGENCY_YELLOW_KEYWORDS:
        if kw in text:
            hits.append(kw)
    if hits:
        return "yellow", hits
    return "green", hits


# 科室名称规范化映射（LLM 兜底或边界匹配可能输出这些别名）
DEPT_NORMALIZE: dict = {
    "妇科": "妇产科",
    "心内科": "心血管内科",
    "心内科": "心血管内科",
    "神经外科": "神经内科",       # 简化处理，评测集中没有神经外科标注
    "泌尿外科": "肾内科",         # 简化处理
    "儿内科": "儿科",
    "产科": "妇产科",
}

# 科室名称必须从这个集合里选（评测集标准）
STANDARD_DEPTS = {
    "急诊科", "呼吸内科", "消化内科", "心血管内科", "神经内科",
    "肾内科", "内分泌科", "儿科", "妇产科", "骨科", "皮肤科",
    "眼科", "耳鼻喉科", "口腔科", "普外科", "全科医学科",
}


def match_department(symptoms_text: str, age: Optional[int] = None, gender: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
    """
    基于关键词 + 年龄/性别规则匹配科室。
    返回 (推荐科室, 命中的关键词列表)
    """
    # 1. 急诊优先（红色）
    urgency, _ = check_urgency(symptoms_text)
    if urgency == "red":
        return "急诊科", ["急诊触发"]

    # 2. 年龄推断：显式 age 或文本暗示（宝宝/小孩 → 儿科）
    is_ped = (age is not None and age <= 14)
    if age is None:
        for kw in PED_HINT_KEYWORDS:
            if kw in symptoms_text:
                is_ped = True
                break

    # 3. 性别推断
    is_female = (gender and ("女" in str(gender) or "female" in str(gender).lower()))
    if gender is None:
        for kw in FEMALE_HINT_KEYWORDS:
            if kw in symptoms_text:
                is_female = True
                break

    # 4. 儿科分流
    if is_ped:
        hits = {}
        for dept, kws in DEPARTMENT_RULES.items():
            if dept in ("儿科", "妇产科"):
                continue
            for kw in kws:
                if kw in symptoms_text:
                    hits.setdefault(dept, []).append(kw)
        if hits:
            best = max(hits.items(), key=lambda x: len(x[1]))
            return f"儿科（{best[0]}方向）", best[1]
        return "儿科", []

    # 5. 妇产科分流
    if is_female:
        gyno_hits = [kw for kw in DEPARTMENT_RULES["妇产科"] if kw in symptoms_text]
        if gyno_hits:
            return "妇产科", gyno_hits

    # 6. 黄色急诊条件 → 急诊科
    if urgency == "yellow":
        return "急诊科", ["黄色预警"]

    # 7. 正常匹配：按命中关键词数量决定
    hits: dict = {}
    for dept, kws in DEPARTMENT_RULES.items():
        if dept == "儿科":
            continue
        for kw in kws:
            if kw in symptoms_text:
                hits.setdefault(dept, []).append(kw)

    if not hits:
        return None, []

    best = max(hits.items(), key=lambda x: len(x[1]))
    return best[0], best[1]


def normalize_dept_name(name: str) -> str:
    """把 LLM 或规则输出的科室名规范化为标准名称"""
    if not name:
        return ""
    name = name.strip()
    # 去掉括号部分（如 "儿科（呼吸内科方向）" → 完整保留或取儿科）
    name = name.split("（")[0].split("(")[0].strip()
    # 别名映射
    name = DEPT_NORMALIZE.get(name, name)
    return name


def build_triage_reason(department: str, urgency: str, hits: List[str]) -> str:
    """把规则命中转成人类可读的分诊依据"""
    urgency_map = {"red": "红色急诊（请立即拨打 120）", "yellow": "黄色预警（建议尽快就医）", "green": "绿色常规"}
    if hits:
        return f"根据症状关键词 {hits} 匹配 → {department}；风险等级：{urgency_map[urgency]}"
    return f"LLM 推理 → {department}；风险等级：{urgency_map[urgency]}"


if __name__ == "__main__":
    # 快速自测
    cases = [
        ("胸痛伴大汗", None, None),
        ("咳嗽发烧 3 天", 30, None),
        ("肚子痛拉肚子", 5, None),
        ("眼睛痛视力模糊", 40, None),
        ("怀孕三个月阴道出血", 28, "女"),
    ]
    for text, age, g in cases:
        u, uh = check_urgency(text)
        d, dh = match_department(text, age, g)
        print(f"'{text}' → 风险={u}{uh} 科室={d}{dh}")
