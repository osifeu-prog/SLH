from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..config import settings

router = APIRouter(tags=["wallet"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "slh_token_address": settings.slh_token_address,
        },
    )


@router.get("/u/{telegram_id}", response_class=HTMLResponse)
async def user_card(
    telegram_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    wallet = db.get(models.Wallet, telegram_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="User not found")

    return templates.TemplateResponse(
        "user_card.html",
        {
            "request": request,
            "wallet": wallet,
            "slh_token_address": settings.slh_token_address,
            "base_url": settings.base_url,
        },
    )
