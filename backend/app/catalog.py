import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Album, DisabledAlbum, Playlist, PlaylistTrack, Rule, Track

ALBUM_TYPE_RANK = {"album": 0, "single": 1, "compilation": 2}
FEATURING = re.compile(r"\s*[(\[](?:feat|ft|with)\b.*?[)\]]", re.IGNORECASE)
VERSION_SUFFIX = re.compile(r"\s+-\s+.*$")
NON_WORD = re.compile(r"[\W_]+")


@dataclass(slots=True)
class Entry:
    track: Track
    album: Album
    state: PlaylistTrack | None
    released: date
    exclusion: str | None = None

    @property
    def eligible(self) -> bool:
        return self.exclusion is None

    @property
    def cooldown(self) -> int:
        return self.state.cooldown if self.state else 0

    @property
    def current(self) -> bool:
        return bool(self.state and self.state.current)

    @property
    def play_count(self) -> int:
        return self.state.play_count if self.state else 0

    @property
    def available(self) -> bool:
        return self.eligible and self.cooldown == 0


class RuleMatcher:
    def __init__(self, rules: list[Rule]) -> None:
        keywords = sorted({re.escape(r.pattern) for r in rules if r.kind == "keyword"}, key=len, reverse=True)
        self._keywords = re.compile(rf"(?<!\w)(?:{'|'.join(keywords)})(?!\w)", re.IGNORECASE) if keywords else None
        self._regexes = [(r.pattern, re.compile(r.pattern, re.IGNORECASE)) for r in rules if r.kind == "regex"]

    def match(self, text: str) -> str | None:
        if self._keywords and (found := self._keywords.search(text)):
            return f'keyword "{found.group(0).lower()}"'
        return next((f'regex "{pattern}"' for pattern, regex in self._regexes if regex.search(text)), None)


def active_rules(session: Session, playlist: Playlist) -> list[Rule]:
    global_rules = session.scalars(
        select(Rule).where(Rule.playlist_id.is_(None), Rule.id.not_in(playlist.disabled_rule_ids))
    )
    return [*global_rules, *playlist.rules]


def load_catalog(session: Session, playlist: Playlist, artist_ids: list[str]) -> dict[str, list[Entry]]:
    matcher = RuleMatcher(active_rules(session, playlist))
    states = {
        state.track_id: state
        for state in session.scalars(select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id))
    }
    disabled_albums = set(session.scalars(
        select(DisabledAlbum.album_id).where(DisabledAlbum.playlist_id == playlist.id)
    ))
    rows = session.execute(
        select(Track, Album)
        .join(Track.album)
        .where(Album.artist_id.in_(artist_ids))
        .order_by(Album.release_date.desc(), Album.id, Track.disc_number, Track.track_number)
    )

    catalog: dict[str, list[Entry]] = {artist_id: [] for artist_id in artist_ids}
    for track, album in rows:
        entry = Entry(track, album, states.get(track.id), album.release_date)
        entry.exclusion = _exclusion(playlist, matcher, entry, album.id in disabled_albums)
        catalog[album.artist_id].append(entry)

    if playlist.exclude_duplicates:
        for entries in catalog.values():
            _mark_duplicates(entries)
    return catalog


def _exclusion(playlist: Playlist, matcher: RuleMatcher, entry: Entry, album_disabled: bool) -> str | None:
    track, album = entry.track, entry.album
    seconds = track.duration_ms // 1000
    if album_disabled:
        return "album disabled"
    if entry.state and entry.state.disabled:
        return "disabled"
    if not track.artist_ids or track.artist_ids[0] != album.artist_id:
        return "guest appearance"
    if playlist.solo_only and len(track.artist_ids) > 1:
        return "featuring"
    if seconds < playlist.min_duration:
        return "too short"
    if playlist.max_duration and seconds > playlist.max_duration:
        return "too long"
    return matcher.match(track.name) or matcher.match(album.name)


def _title_key(track: Track) -> str:
    title = VERSION_SUFFIX.sub("", FEATURING.sub("", track.name))
    return NON_WORD.sub("", title.casefold()) or track.id


def _mark_duplicates(entries: list[Entry]) -> None:
    groups: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        if entry.eligible:
            groups[_title_key(entry.track)].append(entry)

    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda e: (
            ALBUM_TYPE_RANK.get(e.album.album_type, len(ALBUM_TYPE_RANK)),
            e.album.release_date,
            e.track.disc_number,
            e.track.track_number,
        ))
        keeper, *duplicates = group
        keeper.released = min(e.album.release_date for e in group)
        for entry in duplicates:
            entry.exclusion = f'duplicate of "{keeper.track.name}" ({keeper.album.name})'
