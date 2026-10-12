"""Gemini는 답변 생성, HuggingFace는 정책 검색용 로컬 임베딩에 사용."""
import os
from functools import lru_cache
from ai_inquiry.config import settings

@lru_cache
def get_chat():
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is required for Gemini LLM answers')
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=settings()['model'], temperature=0)

@lru_cache
def get_embeddings():
    # 정책 문서 저장과 질문 검색에서 반드시 같은 모델을 사용해야 합니다.
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=settings()['embedding_model'],
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )
