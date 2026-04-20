from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.core import router as core_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.ml_routes import router as ml_router
from app.api.v1.surveys import router as surveys_router
from app.api.v1.viz import router as viz_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="PMBI API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(core_router)
app.include_router(surveys_router)
app.include_router(analytics_router)
app.include_router(viz_router)
app.include_router(dashboard_router)
app.include_router(ml_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
