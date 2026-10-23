from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import env
from ..db import get_session
from ..models import Rule, Settings
from ..schemas import AuthStatus, RuleIn, RuleOut, SettingsData
from ..spotify import SpotifyError, spotify

router = APIRouter(prefix="/api")


@router.get("/settings", response_model=SettingsData)
def get_settings(session: Session = Depends(get_session)):
    return session.get(Settings, 1)


@router.put("/settings", response_model=SettingsData)
def update_settings(data: SettingsData, session: Session = Depends(get_session)):
    settings = session.get(Settings, 1)
    for field, value in data.model_dump().items():
        setattr(settings, field, value)
    session.commit()
    return settings


@router.get("/rules", response_model=list[RuleOut])
def list_rules(session: Session = Depends(get_session)):
    return session.scalars(select(Rule).where(Rule.playlist_id.is_(None)).order_by(Rule.kind, Rule.pattern)).all()


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(data: RuleIn, session: Session = Depends(get_session)):
    rule = Rule(**data.model_dump())
    session.add(rule)
    session.commit()
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    session.delete(rule)
    session.commit()


@router.get("/auth", response_model=AuthStatus)
def auth_status():
    has_app = bool(env.client_id and env.client_secret)
    return AuthStatus(
        configured=has_app and bool(env.refresh_token),
        authorize_url=spotify.authorize_url() if has_app else None,
    )


@router.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(code: str | None = None, error: str | None = None):
    if error or not code:
        return f"<p>Authorization failed: {escape(error or 'no code')}</p>"
    try:
        refresh_token = await spotify.exchange_code(code)
    except SpotifyError as failure:
        return f"<p>{escape(str(failure))}</p>"
    return (
        "<p>Add this line to your <code>.env</code> file, then restart the container:</p>"
        f"<pre>SPOTIFY_REFRESH_TOKEN={refresh_token}</pre>"
    )
