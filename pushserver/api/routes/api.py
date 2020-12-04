from fastapi import APIRouter

from pushserver.api.routes import home, push
from pushserver.api.routes.v2 import add, push as push_v2, remove


router = APIRouter()
router.include_router(home.router, tags=["welcome", "home"])
router.include_router(push.router, tags=["push"], prefix="/push")

router.include_router(add.router, tags=["v2"], prefix="/v2/tokens")
router.include_router(push_v2.router, tags=["v2"], prefix="/v2/tokens")
router.include_router(remove.router, tags=["v2"], prefix="/v2/tokens")

