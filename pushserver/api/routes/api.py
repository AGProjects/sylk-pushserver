from fastapi import APIRouter

from pushserver.api.routes import home, push

router = APIRouter()
router.include_router(home.router, tags=["welcome", "home"])
router.include_router(push.router, tags=["push"], prefix="/push")
