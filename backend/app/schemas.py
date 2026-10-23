import re
from datetime import UTC, date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, ValidationInfo, field_validator

UtcDatetime = Annotated[datetime, PlainSerializer(lambda value: value.replace(tzinfo=UTC).isoformat(), when_used="json")]
ClockTime = Annotated[time, PlainSerializer(lambda value: value.strftime("%H:%M"), when_used="json")]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class SettingsData(Schema):
    min_cooldown: int = Field(ge=0)
    min_duration: int = Field(ge=0)
    max_duration: int | None = Field(default=None, ge=1)
    solo_only: bool
    exclude_duplicates: bool
    refresh_lookback_days: int = Field(ge=0)


class RuleIn(Schema):
    kind: Literal["keyword", "regex"]
    pattern: str = Field(min_length=1)

    @field_validator("pattern")
    @classmethod
    def valid_regex(cls, pattern: str, info: ValidationInfo) -> str:
        if info.data.get("kind") == "regex":
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(f"Invalid regex: {error}") from error
        return pattern


class RuleOut(RuleIn):
    id: int


class PlaylistSettings(Schema):
    name: str = Field(min_length=1)
    spotify_target: str = Field(min_length=1)
    artists: str
    songs_per_artist: int = Field(ge=1)
    max_new_releases: int = Field(ge=0)
    update_interval_days: int = Field(ge=1)
    first_rotation_date: date
    rotation_time: ClockTime
    shuffle: bool
    enabled: bool
    min_duration: int = Field(ge=0)
    max_duration: int | None = Field(default=None, ge=1)
    solo_only: bool
    exclude_duplicates: bool


class PlaylistIn(PlaylistSettings):
    disabled_rule_ids: list[int]


class PlaylistOut(PlaylistIn):
    id: int
    artist_names: list[str]
    spotify_playlist_id: str | None
    last_rotated_at: UtcDatetime | None
    next_rotation_at: UtcDatetime
    last_error: str | None
    rules: list[RuleOut]


class PlaylistExport(Schema):
    format: Literal["spotify-playlist-rotate"] = "spotify-playlist-rotate"
    version: Literal[1] = 1
    playlist: PlaylistSettings
    rules: list[RuleIn]
    disabled_global_rules: list[RuleIn]


class PlaylistSummary(Schema):
    id: int
    name: str
    spotify_target: str
    artist_count: int
    enabled: bool
    update_interval_days: int
    rotation_time: ClockTime
    last_rotated_at: UtcDatetime | None
    next_rotation_at: UtcDatetime
    last_error: str | None


class TrackOut(BaseModel):
    id: str
    name: str
    duration: int
    released: date
    exclusion: str | None
    disabled: bool
    cooldown: int
    current: bool
    play_count: int


class AlbumOut(BaseModel):
    id: str
    artist_name: str
    name: str
    album_type: str
    release_date: date
    image_url: str | None
    disabled: bool
    tracks: list[TrackOut]


class ArtistOut(BaseModel):
    id: str
    name: str
    total: int
    eligible: int
    on_cooldown: int


class CatalogOut(BaseModel):
    artists: list[ArtistOut]
    missing_artists: list[str]
    albums: list[AlbumOut]
    total_tracks: int
    page: int
    page_size: int


class ToggleIn(BaseModel):
    disabled: bool


class PickOut(BaseModel):
    track_id: str
    name: str
    album_name: str
    artist_name: str
    duration: int
    source: str


class SelectionOut(BaseModel):
    artist_name: str
    eligible: int
    cooldown: int
    picks: list[PickOut]


class RotationOut(BaseModel):
    dry_run: bool
    selections: list[SelectionOut]
    missing_artists: list[str]
    order: list[PickOut]


class ProgressOut(Schema):
    step: str
    done: int
    total: int


class AuthStatus(BaseModel):
    configured: bool
    authorize_url: str | None
