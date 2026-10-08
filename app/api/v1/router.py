from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.customers.router import router as customers_router
from app.modules.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(customers_router)
