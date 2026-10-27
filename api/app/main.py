from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.routers import admin, assistant, auth, dashboard, events, pipeline, reports, stream

app = FastAPI(
    title="SismoWatch API",
    version="1.0.0",
    description="Plataforma de consumo de datos sismicos con arquitectura Medallion",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(events.router)
app.include_router(reports.router)
app.include_router(pipeline.router)
app.include_router(stream.router)
app.include_router(assistant.router)
app.include_router(admin.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible", "path": request.url.path},
    )


@app.get("/api/health", tags=["salud"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from exc
    return {"status": "ok", "service": "sismowatch-api"}


@app.get("/", include_in_schema=False)
def root():
    return {"service": "SismoWatch API", "docs": "/docs", "health": "/api/health"}
