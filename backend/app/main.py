from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.routes.upload import router as upload_router
from app.api.routes.packets import router as packets_router
from app.api.routes.flags import router as flags_router
from app.api.routes.stores import router as stores_router
from app.api.routes.meetings import router as meetings_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(upload_router, prefix="/api/v1", tags=["upload"])
app.include_router(packets_router, prefix="/api/v1", tags=["packets"])
app.include_router(flags_router, prefix="/api/v1", tags=["flags"])
app.include_router(stores_router, prefix="/api/v1", tags=["stores"])
app.include_router(meetings_router, prefix="/api/v1", tags=["meetings"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/")
async def serve_ui():
    return FileResponse("app/static/index.html")


# Static file serving (must be after route definitions)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
