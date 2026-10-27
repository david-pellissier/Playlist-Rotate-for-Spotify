import math
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import JSON, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .config import env
from .db import Base, engine

DEFAULT_KEYWORDS = (
    "live", "remix", "remixed", "mix", "instrumental", "acoustic",
    "remaster", "remastered", "demo", "piano", "intro", "outro",
)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def local_date(moment: datetime) -> date:
    return moment.replace(tzinfo=UTC).astimezone(env.timezone).date()


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str]
    synced_at: Mapped[datetime | None]
    singles_synced: Mapped[bool] = mapped_column(default=True)
    image_url: Mapped[str | None]

    albums: Mapped[list["Album"]] = relationship(back_populates="artist", cascade="all, delete-orphan")


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    album_type: Mapped[str]
    release_date: Mapped[date]
    image_url: Mapped[str | None]

    artist: Mapped[Artist] = relationship(back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship(back_populates="album", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    album_id: Mapped[str] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    duration_ms: Mapped[int]
    disc_number: Mapped[int]
    track_number: Mapped[int]
    artist_ids: Mapped[list[str]] = mapped_column(JSON)

    album: Mapped[Album] = relationship(back_populates="tracks")

    @property
    def uri(self) -> str:
        return f"spotify:track:{self.id}"


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    min_cooldown: Mapped[int] = mapped_column(default=2)
    min_duration: Mapped[int] = mapped_column(default=100)
    max_duration: Mapped[int | None]
    solo_only: Mapped[bool] = mapped_column(default=False)
    exclude_duplicates: Mapped[bool] = mapped_column(default=True)
    albums_only: Mapped[bool] = mapped_column(default=False)
    refresh_lookback_days: Mapped[int] = mapped_column(default=30)


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    spotify_target: Mapped[str]
    spotify_playlist_id: Mapped[str | None]
    artists: Mapped[str] = mapped_column(Text, default="")
    songs_per_artist: Mapped[int] = mapped_column(default=3)
    max_artists: Mapped[int | None]
    artist_selection: Mapped[str] = mapped_column(default="fair")
    max_new_releases: Mapped[int] = mapped_column(default=1)
    update_interval_days: Mapped[int] = mapped_column(default=7)
    first_rotation_date: Mapped[date]
    rotation_time: Mapped[time] = mapped_column(default=time(6))
    shuffle: Mapped[bool] = mapped_column(default=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    min_duration: Mapped[int] = mapped_column(default=100)
    max_duration: Mapped[int | None]
    solo_only: Mapped[bool] = mapped_column(default=False)
    exclude_duplicates: Mapped[bool] = mapped_column(default=True)
    albums_only: Mapped[bool] = mapped_column(default=False)
    disabled_rule_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    last_rotated_at: Mapped[datetime | None]
    last_error: Mapped[str | None]

    rules: Mapped[list["Rule"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    cover: Mapped["PlaylistCover | None"] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )

    def set_spotify_target(self, target: str) -> None:
        if target != self.spotify_target:
            self.spotify_playlist_id = None
            self.cover = None
        self.spotify_target = target

    @property
    def cover_url(self) -> str | None:
        if self.cover is None or not self.cover.content_type:
            return None
        return f"/api/playlists/{self.id}/cover?v={self.cover.updated_at:%Y%m%d%H%M%S%f}"

    @property
    def artist_names(self) -> list[str]:
        lines = (line.strip() for line in self.artists.splitlines())
        return list(dict.fromkeys(line for line in lines if line and not line.startswith("#")))

    @property
    def next_rotation_at(self) -> datetime:
        if not self.last_rotated_at:
            return self._rotation_on(self.first_rotation_date)
        return self._rotation_on(self._rotation_day_from(local_date(self.last_rotated_at) + timedelta(days=1)))

    def next_rotation_after(self, moment: datetime) -> datetime:
        day = self._rotation_day_from(local_date(moment))
        if self._rotation_on(day) <= moment:
            day = self._rotation_day_from(day + timedelta(days=1))
        return self._rotation_on(day)

    def _rotation_day_from(self, day: date) -> date:
        if day <= self.first_rotation_date:
            return self.first_rotation_date
        periods = math.ceil((day - self.first_rotation_date).days / self.update_interval_days)
        return self.first_rotation_date + timedelta(days=periods * self.update_interval_days)

    def _rotation_on(self, day: date) -> datetime:
        scheduled = datetime.combine(day, self.rotation_time, env.timezone)
        return scheduled.astimezone(UTC).replace(tzinfo=None)


class PlaylistCover(Base):
    __tablename__ = "playlist_covers"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    content_type: Mapped[str]
    updated_at: Mapped[datetime]
    checked_at: Mapped[datetime]


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int | None] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]
    pattern: Mapped[str]


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    disabled: Mapped[bool] = mapped_column(default=False)
    cooldown: Mapped[int] = mapped_column(default=0)
    current: Mapped[bool] = mapped_column(default=False)
    play_count: Mapped[int] = mapped_column(default=0)


class DisabledAlbum(Base):
    __tablename__ = "disabled_albums"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    album_id: Mapped[str] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True)


class Rotation(Base):
    __tablename__ = "rotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), index=True)
    rotated_at: Mapped[datetime]
    trigger: Mapped[str]
    error: Mapped[str | None]

    tracks: Mapped[list["RotationTrack"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="RotationTrack.position"
    )


class RotationTrack(Base):
    __tablename__ = "rotation_tracks"

    rotation_id: Mapped[int] = mapped_column(ForeignKey("rotations.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    source: Mapped[str]

    track: Mapped[Track] = relationship()


class PlaylistArtist(Base):
    __tablename__ = "playlist_artists"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True)
    last_picked_at: Mapped[datetime]


class EnabledAlbum(Base):
    __tablename__ = "enabled_albums"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    album_id: Mapped[str] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True)


class EnabledTrack(Base):
    __tablename__ = "enabled_tracks"

    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(Settings, 1) is None:
            session.add(Settings(id=1))
            session.add_all(Rule(kind="keyword", pattern=keyword) for keyword in DEFAULT_KEYWORDS)
            session.commit()
