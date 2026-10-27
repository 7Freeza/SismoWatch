from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.nl_agent import ask
from app.schemas import AskRequest
from app.security import require_viewer

router = APIRouter(prefix="/api", tags=["agente"])


@router.post("/ask")
def ask_agent(
    payload: AskRequest, user=Depends(require_viewer), db: Session = Depends(get_db)
):
    return ask(payload.question, db, payload.history)
