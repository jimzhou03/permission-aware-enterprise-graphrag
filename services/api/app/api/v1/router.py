from fastapi import APIRouter

from app.api.v1 import auth, knowledge_bases, qa


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(qa.router)
