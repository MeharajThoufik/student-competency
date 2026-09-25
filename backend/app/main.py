from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import activities, health, me, profile
from app.core.config import get_settings

settings = get_settings()

# All routes live under /api so Firebase Hosting can rewrite /api/** to Cloud Run unchanged.
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, me.router, profile.router, activities.router):
    app.include_router(router, prefix="/api")
