"""
Milvus RAG —— 诊疗指南向量检索

设计：
  - Collection: medical_guidelines
  - Embedding: bge-m3（复用 EduAgent 已下载权重）
  - 构建脚本: build_guidelines.py（加载 data/guidelines/*.md → chunk → upsert）
  - 检索函数: rag_search_node（LangGraph 节点形式）
"""
from __future__ import annotations
import os, sys, json
from typing import List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from pymilvus import MilvusClient
from config import settings


def _get_client() -> MilvusClient:
    return MilvusClient(uri=settings.milvus_uri)


def _embed(texts: List[str]) -> List[List[float]]:
    """用 bge-m3 批量生成 embedding，返回向量列表。
    优先加载本地路径，不存在则从 HuggingFace 自动下载。"""
    from sentence_transformers import SentenceTransformer
    local_path = settings.embedding_model_path
    if os.path.isdir(local_path):
        model = SentenceTransformer(local_path, device="cpu")
    else:
        print(f"[guideline_rag] 本地模型不存在 {local_path}，从 HF 下载 {settings.embedding_model_hf}")
        model = SentenceTransformer(settings.embedding_model_hf, device="cpu")

    # bge-m3 新版本支持 instruction 参数，旧版本不支持 → try/except 兜底
    try:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            instruction="Represent this sentence for searching relevant passages.",
            batch_size=8,
        )
    except Exception:
        vectors = model.encode(texts, normalize_embeddings=True, batch_size=8)
    return vectors.tolist()


def ensure_collection():
    """如果 medical_guidelines 不存在则创建。"""
    client = _get_client()
    coll = settings.milvus_collection
    if client.has_collection(coll):
        # 旧 collection schema 可能不兼容（id 是 int64），直接 drop 重建
        client.drop_collection(coll)
        print(f"[guideline_rag] dropped old collection {coll}")

    client.create_collection(
        collection_name=coll,
        dimension=settings.embedding_dim,
        metric_type="COSINE",
        auto_id=True,   # 让 Milvus 自动分配 int64 主键，避免手动指定字符串 id
    )


def upsert_chunks(chunks: List[dict]):
    """
    批量写入 Milvus（auto_id=True，直接 insert）。
    chunks: [{"source": str, "content": str}, ...]
    """
    if not chunks:
        return
    ensure_collection()
    client = _get_client()
    vectors = _embed([c["content"] for c in chunks])
    data = []
    for c, v in zip(chunks, vectors):
        data.append({
            "vector": v,
            "source": c["source"],
            "content": c["content"],
        })
    # auto_id=True 时用 insert，Milvus 自动生成 int64 主键
    client.insert(collection_name=settings.milvus_collection, data=data)
    print(f"[guideline_rag] inserted {len(data)} chunks → {settings.milvus_collection}")


def search(query_text: str, top_k: int = 3) -> List[dict]:
    """
    检索指南片段。返回 top_k 条 [{source, content, score}]
    """
    client = _get_client()
    if not client.has_collection(settings.milvus_collection):
        print("[guideline_rag] collection 不存在，返回空结果")
        return []

    q_vec = _embed([query_text])[0]
    results = client.search(
        collection_name=settings.milvus_collection,
        data=[q_vec],
        limit=top_k,
        output_fields=["source", "content"],
    )
    # 展平 + 取 score
    out = []
    for hits in results:
        for h in hits:
            out.append({
                "source": h["entity"].get("source", "unknown"),
                "content": h["entity"].get("content", ""),
                "score": h["distance"],   # COSINE 距离，越小越相关
            })
    # 过滤过低相关（cosine distance > 0.7 基本无关）
    return [o for o in out if o["score"] < 0.7]


# ── LangGraph 节点版本 ──
def rag_search_node(state: dict) -> dict:
    """从已填槽位拼 query → 检索 Milvus → 把结果写入 state"""
    dept = state.get("department_recommendation", "")
    cc = state.get("chief_complaint", "")
    pi = state.get("present_illness", "")
    query = f"{dept} {cc} {pi}".strip()

    if not query:
        return {"rag_evidence": []}

    evences = search(query, top_k=3)
    # 只保留 source + content
    clean = [{"source": e["source"], "content": e["content"]} for e in evences]
    return {"rag_evidence": clean}


# ── 构建入口 ──
def build_collection(guideline_dir: str = None):
    """扫描 guideline_dir 下的所有 .md 文件，chunk 后 upsert 到 Milvus"""
    guideline_dir = guideline_dir or settings.guideline_dir
    if not os.path.isdir(guideline_dir):
        print(f"[build_collection] 目录不存在: {guideline_dir}")
        return

    chunks = []
    for fname in sorted(os.listdir(guideline_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(guideline_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()

        # 简单 chunk：按段切 + 限制上限 250 字
        import re
        paras = re.split(r"\n\s*\n", text)
        for i, p in enumerate(paras):
            p = p.strip()
            if len(p) < 10:
                continue
            # 超过 250 字再切一刀
            if len(p) > 250:
                for j in range(0, len(p), 250):
                    sub = p[j:j+250]
                    chunks.append({
                        "source": fname,
                        "content": sub,
                    })
            else:
                chunks.append({
                    "source": fname,
                    "content": p,
                })

    upsert_chunks(chunks)
    print(f"[build_collection] done, total chunks: {len(chunks)}")


if __name__ == "__main__":
    # 直接运行：把 data/guidelines 里的所有 md 灌入 Milvus
    build_collection()
