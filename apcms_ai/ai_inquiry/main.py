"""React POST /api/inquiry/chat → 문의 서비스."""
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from typing import Optional
from uuid import UUID
from ai_inquiry.config import settings
from ai_inquiry.clients.backend_client import BackendError
from ai_inquiry.service import answer
router=APIRouter(prefix='/api/inquiry',tags=['1:1 문의'])
class ChatRequest(BaseModel):
 conversation_id: Optional[str]=Field(default=None,min_length=1,max_length=100)
 request_id: Optional[UUID]=None
 question: str=Field(min_length=1,max_length=2000)
 mock_user_id: Optional[str]=None
@router.post('/chat')
async def chat(req: ChatRequest,authorization: Optional[str]=Header(None)):
 token=(authorization[7:].strip() if authorization and authorization.lower().startswith('bearer ') else None)
 if settings()['mode']=='API' and not token: raise HTTPException(401,'Bearer 토큰이 필요합니다.')
 try:
  return await answer(req.question,req.conversation_id,token=token,mock_user_id=req.mock_user_id,
                      request_id=str(req.request_id) if req.request_id else None)
 except PermissionError as e: raise HTTPException(401,str(e)) from e
 except ValueError as e: raise HTTPException(400,str(e)) from e
 except BackendError as e: raise HTTPException(502,str(e)) from e
 except FileNotFoundError as e: raise HTTPException(503,str(e)) from e
 except RuntimeError as e: raise HTTPException(503,str(e)) from e
