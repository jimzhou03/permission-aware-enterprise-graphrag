from fastapi import APIRouter

from app.api.v1 import admin, auth, demo, knowledge_bases, qa


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(qa.router)
api_router.include_router(admin.router)
api_router.include_router(demo.router)
