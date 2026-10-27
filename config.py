# config.py — 全局配置中心，复用 EduAgent 的 qwen-plus / Milvus 基础设施
import os
from pydantic_settings import BaseSettings

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    # ── 大模型（阿里百炼 qwen-plus）──
    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_model: str = "qwen-plus"

    # ── Milvus 向量库 ──
    milvus_uri: str = "http://localhost:19531"
    milvus_collection: str = "medical_guidelines"

    # ── 本地 Embedding 模型（可选；留空则自动从 HuggingFace 下载）──
    embedding_model_path: str = ""
    embedding_model_hf: str = "BAAI/bge-m3"   # fallback：HF 仓库名
    embedding_dim: int = 1024

    # ── 槽位填充上限 ──
    max_turns: int = 5              # 最多追问 5 轮，防止死循环

    # ── 路径 ──
    guideline_dir: str = os.path.join(PROJECT_ROOT, "data", "guidelines")
    eval_dir: str = os.path.join(PROJECT_ROOT, "data", "eval")

    class Config:
        env_file = os.path.join(PROJECT_ROOT, ".env.local")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()

if not settings.openai_api_key:
    print("[config] 警告：未读取到环境变量 OPENAI_API_KEY，槽位抽取与追问生成将不可用")
