"""Pure TMDB payload -> value object mapping and release-selection logic.

No I/O here. Every function is deterministic given its inputs so the release
rules (digital date selection, next-episode identity, unknown dates) are unit
testable without network or database.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..enums import EventKind, MediaType
from ..value_objects import MovieRelease, ReleaseCandidate, TitleSnapshot

# TMDB movie release-date "type" codes; 4 == Digital, 5 == Physical, 6 == TV.
# Types 1-3 (premiere/theatrical) never establish availability.
DIGITAL_RELEASE_TYPE = 4
AVAILABILITY_RELEASE_TYPES = frozenset({4, 5, 6})

# TMDB watch-provider offering categories that count as "available now". A
# link-only region entry (only a `link`, no offering lists) does not qualify.
WATCH_PROVIDER_OFFERING_KEYS = ("flatrate", "free", "ads", "rent", "buy")


def tmdb_url(media_type: MediaType, tmdb_id: int) -> str:
    return f"https://www.themoviedb.org/{media_type.value}/{tmdb_id}"


def _year_from_iso(value: str | None) -> int | None:
    if not value or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _parse_iso_date(value: str | None) -> date | None:
    """Parse a TMDB date, tolerating both `YYYY-MM-DD` and full ISO timestamps."""
    if not value:
        return None
    head = value[:10]
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


def select_movie_release(
    release_dates_payload: dict,
    region: str,
    today: date,
    availability_delay_days: int = 0,
) -> MovieRelease:
    """Region-scoped availability and next-digital date for a movie.

    `release_dates_payload` is the body of TMDB `movie/{id}/release_dates`.

    The configured calendar-day delay is applied before comparison with `today`.
    `available_since` is the earliest effective type 4/5/6 date at or before
    today. `next_digital_date` is the earliest effective future type-4 date and
    is only set when the movie is not already available.

    Other regions, theatrical types 1-3, and missing/malformed dates are ignored.
    """
    available: list[date] = []
    future_digital: list[tuple[date, date]] = []
    for entry in release_dates_payload.get("results", []):
        if entry.get("iso_3166_1") != region:
            continue
        for rel in entry.get("release_dates", []):
            rel_type = rel.get("type")
            parsed = _parse_iso_date(rel.get("release_date"))
            if parsed is None:
                continue
            effective = parsed + timedelta(days=availability_delay_days)
            if rel_type in AVAILABILITY_RELEASE_TYPES and effective <= today:
                available.append(effective)
            if rel_type == DIGITAL_RELEASE_TYPE and effective > today:
                future_digital.append((effective, parsed))
    available_since = min(available) if available else None
    next_pair = min(future_digital) if future_digital and available_since is None else None
    return MovieRelease(
        available_since=available_since,
        next_digital_date=next_pair[0] if next_pair else None,
        next_digital_source_date=next_pair[1] if next_pair else None,
    )


def movie_available_from_providers(providers_payload: dict, region: str) -> bool:
    """Whether TMDB watch providers establish undated availability in `region`.

    `providers_payload` is the body of TMDB `movie/{id}/watch/providers`. A region
    is available when its entry has a non-empty `flatrate`, `free`, `ads`, `rent`,
    or `buy` list. Link-only entries, empty lists, malformed values, and other
    regions are ignored.
    """
    results = providers_payload.get("results")
    if not isinstance(results, dict):
        return False
    region_entry = results.get(region)
    if not isinstance(region_entry, dict):
        return False
    for key in WATCH_PROVIDER_OFFERING_KEYS:
        offering = region_entry.get(key)
        if isinstance(offering, list) and len(offering) > 0:
            return True
    return False


def snapshot_from_movie(details: dict) -> TitleSnapshot:
    return TitleSnapshot(
        media_type=MediaType.MOVIE,
        tmdb_id=int(details["id"]),
        title=details.get("title") or details.get("original_title") or "Untitled",
        original_title=details.get("original_title"),
        overview=details.get("overview") or None,
        poster_path=details.get("poster_path"),
        release_year=_year_from_iso(details.get("release_date")),
    )


def snapshot_from_tv(details: dict) -> TitleSnapshot:
    return TitleSnapshot(
        media_type=MediaType.TV,
        tmdb_id=int(details["id"]),
        title=details.get("name") or details.get("original_name") or "Untitled",
        original_title=details.get("original_name"),
        overview=details.get("overview") or None,
        poster_path=details.get("poster_path"),
        release_year=_year_from_iso(details.get("first_air_date")),
    )


def movie_release_candidate(
    tmdb_id: int,
    digital_source_date: date | None,
    digital_date: date | None,
    region: str,
) -> ReleaseCandidate | None:
    if digital_date is None:
        return None
    return ReleaseCandidate(
        kind=EventKind.MOVIE_DIGITAL,
        source_event_key=f"movie:{tmdb_id}:digital:{region}",
        source_date=digital_source_date or digital_date,
        scheduled_date=digital_date,
    )


def tv_release_candidate(
    tmdb_id: int, details: dict, today: date, availability_delay_days: int = 0
) -> ReleaseCandidate | None:
    """Derive the current TV episode event from `next_episode_to_air`.

    Identity is the series id plus season and episode numbers. An unknown air
    date yields no candidate. The source air date is ignored only when its
    delayed effective date is already in the past.
    """
    nxt = details.get("next_episode_to_air")
    if not nxt:
        return None
    season = nxt.get("season_number")
    episode = nxt.get("episode_number")
    air = _parse_iso_date(nxt.get("air_date"))
    if season is None or episode is None or air is None:
        return None
    effective = air + timedelta(days=availability_delay_days)
    if effective < today:
        return None
    return ReleaseCandidate(
        kind=EventKind.TV_EPISODE,
        source_event_key=f"tv:{tmdb_id}:s{int(season)}e{int(episode)}",
        source_date=air,
        scheduled_date=effective,
        season_number=int(season),
        episode_number=int(episode),
    )
