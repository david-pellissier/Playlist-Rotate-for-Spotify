from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Playlist, Rule
from ..schemas import PlaylistExport, PlaylistOut, PlaylistSettings, RuleIn
from .playlists import get_playlist

router = APIRouter(prefix="/api/playlists")


@router.get("/{playlist_id}/export")
def export_playlist(playlist: Playlist = Depends(get_playlist), session: Session = Depends(get_session)):
    disabled_rules = session.scalars(select(Rule).where(Rule.id.in_(playlist.disabled_rule_ids)))
    export = PlaylistExport(
        playlist=PlaylistSettings.model_validate(playlist),
        rules=[RuleIn.model_validate(rule) for rule in playlist.rules],
        disabled_global_rules=[RuleIn.model_validate(rule) for rule in disabled_rules],
    )
    filename = quote(f"{playlist.name}.json")
    return Response(
        export.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/import", response_model=PlaylistOut, status_code=201)
def import_playlist(
    data: PlaylistExport,
    on_conflict: Literal["fail", "replace", "copy"] = "fail",
    session: Session = Depends(get_session),
):
    settings = data.playlist.model_dump()
    existing = session.scalar(select(Playlist).where(Playlist.name == settings["name"]))

    if existing and on_conflict == "fail":
        raise HTTPException(409, f'A playlist named "{settings["name"]}" already exists')
    if existing and on_conflict == "replace":
        playlist = existing
        playlist.set_spotify_target(settings["spotify_target"])
        playlist.rules.clear()
    else:
        if existing:
            settings["name"] = copy_name(session, settings["name"])
            settings["enabled"] = False
        playlist = Playlist()
        session.add(playlist)

    for field, value in settings.items():
        setattr(playlist, field, value)
    playlist.disabled_rule_ids = matching_global_rules(session, data.disabled_global_rules)
    playlist.rules.extend(Rule(**rule.model_dump()) for rule in data.rules)
    session.commit()
    return playlist


def copy_name(session: Session, name: str) -> str:
    taken = set(session.scalars(select(Playlist.name)))
    candidate, number = f"{name} (copy)", 2
    while candidate in taken:
        candidate, number = f"{name} (copy {number})", number + 1
    return candidate


def matching_global_rules(session: Session, rules: list[RuleIn]) -> list[int]:
    wanted = {(rule.kind, rule.pattern) for rule in rules}
    global_rules = session.scalars(select(Rule).where(Rule.playlist_id.is_(None)))
    return [rule.id for rule in global_rules if (rule.kind, rule.pattern) in wanted]
