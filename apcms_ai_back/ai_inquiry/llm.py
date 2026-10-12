import os
from functools import lru_cache
from ai_inquiry.config import settings

@lru_cache
def get_chat():
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is required for LLM answers')
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=settings()['model'], temperature=0)

@lru_cache
def get_embeddings():
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY is required for embedding')
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=settings()['embedding_model'], output_dimensionality=768)
