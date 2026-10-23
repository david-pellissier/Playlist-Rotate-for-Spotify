from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from .config import env
from .db import Base, engine

DEFAULT_KEYWORDS = (
    "live", "remix", "remixed", "mix", "instrumental", "acoustic",
    "remaster", "remastered", "demo", "piano", "intro", "outro",
)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str]
    synced_at: Mapped[datetime | None]

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
    refresh_lookback_days: Mapped[int] = mapped_column(default=30)


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    spotify_target: Mapped[str]
    spotify_playlist_id: Mapped[str | None]
    artists: Mapped[str] = mapped_column(Text, default="")
    songs_per_artist: Mapped[int] = mapped_column(default=3)
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
    disabled_rule_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    last_rotated_at: Mapped[datetime | None]
    last_error: Mapped[str | None]

    rules: Mapped[list["Rule"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)

    @property
    def artist_names(self) -> list[str]:
        lines = (line.strip() for line in self.artists.splitlines())
        return list(dict.fromkeys(line for line in lines if line and not line.startswith("#")))

    @property
    def next_rotation_at(self) -> datetime:
        day = self.first_rotation_date
        if self.last_rotated_at:
            last_day = self.last_rotated_at.replace(tzinfo=UTC).astimezone(env.timezone).date()
            if last_day >= day:
                periods = (last_day - day).days // self.update_interval_days + 1
                day += timedelta(days=periods * self.update_interval_days)
        scheduled = datetime.combine(day, self.rotation_time, env.timezone)
        return scheduled.astimezone(UTC).replace(tzinfo=None)


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


def init_db() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(Settings, 1) is None:
            session.add(Settings(id=1))
            session.add_all(Rule(kind="keyword", pattern=keyword) for keyword in DEFAULT_KEYWORDS)
            session.commit()
