from fastapi import APIRouter

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.patients import router as patients_router
from app.api.v1.system import router as system_router
from app.api.v1.visits import router as visits_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(patients_router)
api_v1_router.include_router(visits_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(system_router)
