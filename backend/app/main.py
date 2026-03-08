from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes.upload import router as upload_router
from app.api.routes.packets import router as packets_router
from app.api.routes.flags import router as flags_router
from app.api.routes.stores import router as stores_router
from app.api.routes.meetings import router as meetings_router

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api/v1", tags=["upload"])
app.include_router(packets_router, prefix="/api/v1", tags=["packets"])
app.include_router(flags_router, prefix="/api/v1", tags=["flags"])
app.include_router(stores_router, prefix="/api/v1", tags=["stores"])
app.include_router(meetings_router, prefix="/api/v1", tags=["meetings"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}
