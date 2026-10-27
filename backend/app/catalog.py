import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

from .models import Album, DisabledAlbum, EnabledAlbum, EnabledTrack, Playlist, PlaylistTrack, Rule, Track

ALBUM_TYPE_RANK = {"album": 0, "single": 1, "compilation": 2}
FEATURING = re.compile(r"\s*[(\[](?:feat|ft|with)\b.*?[)\]]", re.IGNORECASE)
VERSION_SUFFIX = re.compile(r"\s+-\s+.*$")
NON_WORD = re.compile(r"[\W_]+")


USER = "user"
AUTO = "auto"
ALBUM = "album"


@dataclass(slots=True)
class Status:
    automatic: str | None = None
    exclusion: str | None = None
    excluded_by: str | None = None
    forced: bool = False

    def exclude(self, reason: str, by: str) -> None:
        self.exclusion = reason
        self.excluded_by = by

    def apply_automatic(self, forced: bool) -> None:
        if not self.automatic or self.exclusion:
            return
        if forced:
            self.forced = True
        else:
            self.exclude(self.automatic, AUTO)


@dataclass(slots=True)
class Entry:
    track: Track
    album: Album
    album_status: Status
    status: Status
    state: PlaylistTrack | None
    released: date

    @property
    def exclusion(self) -> str | None:
        return self.status.exclusion

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

    def is_new_release(self, cutoff: date) -> bool:
        return self.eligible and self.play_count == 0 and self.released >= cutoff


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


def album_automatic_exclusion(session: Session, playlist: Playlist, album: Album) -> str | None:
    return _album_exclusion(playlist, RuleMatcher(active_rules(session, playlist)), album)


def _album_exclusion(playlist: Playlist, matcher: RuleMatcher, album: Album) -> str | None:
    if playlist.albums_only and album.album_type != "album":
        return "single/EP"
    return matcher.match(album.name)


def load_catalog(session: Session, playlist: Playlist, artist_ids: list[str]) -> dict[str, list[Entry]]:
    matcher = RuleMatcher(active_rules(session, playlist))
    states = {
        state.track_id: state
        for state in session.scalars(select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id))
    }
    disabled_albums = _playlist_ids(session, DisabledAlbum.album_id, playlist.id)
    enabled_albums = _playlist_ids(session, EnabledAlbum.album_id, playlist.id)
    enabled_tracks = _playlist_ids(session, EnabledTrack.track_id, playlist.id)
    rows = session.execute(
        select(Track, Album)
        .join(Track.album)
        .where(Album.artist_id.in_(artist_ids))
        .order_by(Album.release_date.desc(), Album.id, Track.disc_number, Track.track_number)
    )

    catalog: dict[str, list[Entry]] = {artist_id: [] for artist_id in artist_ids}
    album_statuses: dict[str, Status] = {}
    for track, album in rows:
        if album.id not in album_statuses:
            album_statuses[album.id] = _album_status(playlist, matcher, album, disabled_albums, enabled_albums)
        album_status = album_statuses[album.id]
        state = states.get(track.id)
        status = _track_status(playlist, matcher, track, album, state, album_status, track.id in enabled_tracks)
        catalog[album.artist_id].append(Entry(track, album, album_status, status, state, album.release_date))

    if playlist.exclude_duplicates:
        for entries in catalog.values():
            _mark_duplicates(entries, enabled_tracks)
    return catalog


def _playlist_ids(session: Session, column: InstrumentedAttribute[str], playlist_id: int) -> set[str]:
    return set(session.scalars(select(column).where(column.class_.playlist_id == playlist_id)))


def _album_status(
    playlist: Playlist, matcher: RuleMatcher, album: Album, disabled: set[str], enabled: set[str]
) -> Status:
    status = Status(automatic=_album_exclusion(playlist, matcher, album))
    if album.id in disabled:
        status.exclude("album disabled", USER)
    status.apply_automatic(forced=album.id in enabled)
    return status


def _track_status(
    playlist: Playlist,
    matcher: RuleMatcher,
    track: Track,
    album: Album,
    state: PlaylistTrack | None,
    album_status: Status,
    forced: bool,
) -> Status:
    status = Status(automatic=_automatic_exclusion(playlist, matcher, track, album))
    if album_status.exclusion:
        status.exclude("album disabled" if album_status.excluded_by == USER else "album excluded", ALBUM)
    elif state and state.disabled:
        status.exclude("disabled", USER)
    status.apply_automatic(forced)
    return status


def _automatic_exclusion(playlist: Playlist, matcher: RuleMatcher, track: Track, album: Album) -> str | None:
    seconds = track.duration_ms // 1000
    if not track.artist_ids or track.artist_ids[0] != album.artist_id:
        return "guest appearance"
    if playlist.solo_only and len(track.artist_ids) > 1:
        return "featuring"
    if seconds < playlist.min_duration:
        return "too short"
    if playlist.max_duration and seconds > playlist.max_duration:
        return "too long"
    return matcher.match(track.name)


def _title_key(track: Track) -> str:
    title = VERSION_SUFFIX.sub("", FEATURING.sub("", track.name))
    return NON_WORD.sub("", title.casefold()) or track.id


def _mark_duplicates(entries: list[Entry], enabled_tracks: set[str]) -> None:
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
        reason = f'duplicate of "{keeper.track.name}" ({keeper.album.name})'
        for entry in duplicates:
            entry.status.automatic = entry.status.automatic or reason
            entry.status.apply_automatic(forced=entry.track.id in enabled_tracks)
