# MedAgent · 多轮预问诊分诊 Agent

基于 **LangGraph** 的多轮追问式 AI 预问诊系统：通过槽位填充采集主诉、现病史、既往史与用药禁忌，结合科室分诊规则与急诊红线识别给出就诊建议，并使用 **Milvus + 诊疗指南 RAG** 让回答附带证据来源。

配套 Vue 3 企业级 B 端工作台，支持新建对话、历史会话持久化与移动端适配；`python app.py` 单命令启动 API + 页面并自动打开浏览器。

> 输出仅为分诊建议，不构成医疗诊断；急重症请立即拨打 120。

---

## 核心能力

- **真实多轮追问**：LangGraph 条件边路由，每轮只追问一个缺失槽位；追问由大模型结合上下文生成（先承接上一句再提问），不会机械重复同一句。
- **槽位结构化采集**：主诉 / 现病史 / 既往史 / 用药禁忌四个槽位，LLM JSON 抽取 + 结果去重合并 + 已问槽位记录，避免无效追问。
- **规则 + LLM 双路分诊**：关键词→科室映射、年龄/性别推断（儿科 / 妇产科分流）、红/黄/绿三级急诊判定；规则未命中时由 LLM 兜底并归一到标准科室。
- **RAG 证据溯源**：bge-m3 向量化诊疗指南写入 Milvus，检索结果随报告展示来源文件。
- **可复现评测**：自建 300 条标注样本（10 个科室），提供 zero-shot 基线与完整 Agent 的对照评测脚本。
- **企业级前端**：深色会话侧栏、新建对话、历史记录 localStorage 持久化、搜索、删除、响应式抽屉。

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 编排 | LangGraph（StateGraph / 条件边 / MemorySaver 多轮记忆） |
| LLM | 阿里百炼 qwen-plus（OpenAI 兼容协议，`langchain-openai`） |
| RAG | Milvus + bge-m3（sentence-transformers，1024 维，COSINE） |
| 后端 | Python · FastAPI · Uvicorn · Pydantic |
| 前端 | Vue 3 · TypeScript · Vite |
| 评测 | 自建 300 条标注集，baseline vs Agent 对照脚本 |

## 架构

```
用户输入
   │
   ▼
FastAPI  POST /api/v1/triage/start | /chat
   │
   ▼
LangGraph StateGraph（thread_id 会话隔离）
   entry ──► llm_extract ──┬─(槽位未满)─► ask_slot ──► END（返回本轮追问）
                           │
                           └─(槽位已满/超轮次)─► triage ──► rag_search ──► finalize ──► END
                                                     │            │
                                            规则引擎 + LLM 兜底   Milvus 指南检索
```

- `agents/triage/state.py`：State Schema（槽位、轮次、已问槽位、分诊输出）
- `agents/triage/nodes.py`：入口 / 抽取 / 追问 / 分诊 / 收尾节点
- `agents/triage/graph.py`：状态图装配与条件路由
- `tools/triage_rules.py`：科室映射与急诊红线规则
- `tools/guideline_rag.py`：Milvus 建库、检索与 RAG 节点

## 评测结果

评测集：**300 条标注样本 / 10 个科室**；对照组为零样本提示（zero-shot）的基线模型。

| 指标 | Baseline | MedAgent | 提升 |
|---|---|---|---|
| 科室推荐 Top-1 准确率 | 70.0% | **80.7%** | +10.7 pp |
| 急诊风险识别准确率 | 35.0% | **85.3%** | +50.3 pp |
| 平均追问轮次 | — | **2.3 轮** | — |

评测脚本：

```bash
python eval/generate_eval_set.py   # 生成 300 条评测集（data/eval/triage_eval_300.jsonl）
python eval/baseline_eval.py       # zero-shot 基线
python eval/agent_eval.py          # 完整 Agent 流程
python eval/agent_eval.py --compare  # 输出对比结果
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# Windows PowerShell（当前会话）
$env:OPENAI_API_KEY = "sk-xxxx"

# 或复制 .env.example 为 .env.local 并填写
```

| 变量 | 说明 | 默认 |
|---|---|---|
| `OPENAI_API_KEY` | 阿里百炼 API Key（必填） | — |
| `OPENAI_BASE_URL` | OpenAI 兼容地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `OPENAI_MODEL` | 模型名 | `qwen-plus` |
| `MILVUS_URI` | Milvus 地址 | `http://localhost:19531` |
| `EMBEDDING_MODEL_PATH` | 本地 bge-m3 路径（留空自动从 HF 下载） | `""` |

### 3.（可选）构建指南向量库

Milvus 可用时，首次运行需把 `data/guidelines/*.md` 灌入向量库：

```bash
python tools/guideline_rag.py
```

Milvus 不可用时仍可完成问诊与分诊，只是报告不带指南引用。

### 4. 启动

```bash
python app.py
```

启动后会**自动打开浏览器**访问 `http://127.0.0.1:8001/`，API 与前端同端口。

前端已附带构建产物 `frontend/dist`，克隆后无需 Node 即可运行；修改前端源码后重新构建：

```bash
cd frontend
npm install
npm run build        # 输出到 frontend/dist
# 开发调试：npm run dev（http://localhost:3001，接口代理到 8001）
```

## 目录结构

```
MedAgent/
├── app.py                  # FastAPI 入口（API + 前端托管 + 自动打开浏览器）
├── config.py               # 配置中心（模型 / Milvus / 路径）
├── requirements.txt
├── .env.example
├── agents/triage/          # LangGraph 状态机（state / nodes / graph）
├── tools/                  # 分诊规则、Milvus RAG
├── eval/                   # 评测：生成数据集 / 基线 / Agent
├── data/
│   ├── guidelines/         # 诊疗指南文档（RAG 语料）
│   └── eval/               # 300 条评测集与评测结果
└── frontend/               # Vue 3 + TS + Vite 企业级工作台
```

## 设计要点

- **为什么规则优先**：急诊红线（胸痛、呼吸困难、意识丧失、大出血等）必须可解释、可复核，规则先行、模型兜底，避免纯 LLM 误判延误。
- **为什么记录已问槽位**：用户回答可能答非所问；记录已问过的槽位后，下一轮推进到新槽位，全部问过仍缺才回问，避免“同一句话循环”。
- **为什么用 MemorySaver**：以 `thread_id` 隔离会话、`add_messages` 累加历史；服务重启后内存会话失效，接口返回 409 提示新建，避免静默重置槽位。
- **评测可复现**：基线、Agent 使用同一批样本与同一套科室标准，结果落盘 `data/eval/`，可逐条复核。

## 免责声明

本项目仅用于技术学习与演示，不构成医疗器械或临床诊断系统。任何分诊建议均需由执业医师判断，急重症请立即拨打 120。
