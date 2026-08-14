"""Pure TMDB payload -> value object mapping and release-selection logic.

No I/O here. Every function is deterministic given its inputs so the release
rules (digital date selection, next-episode identity, unknown dates) are unit
testable without network or database.
"""

from __future__ import annotations

from datetime import date

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


def select_movie_release(release_dates_payload: dict, region: str, today: date) -> MovieRelease:
    """Region-scoped availability and next-digital date for a movie.

    `release_dates_payload` is the body of TMDB `movie/{id}/release_dates`.

    - `available_since`: earliest type 4/5/6 (digital/physical/TV) date in
      `region` at or before `today`.
    - `next_digital_date`: earliest type-4 date strictly after `today`, only when
      the movie is not already available (availability outranks a later digital
      release).

    Other regions, theatrical types 1-3, and missing/malformed dates are ignored.
    """
    available: list[date] = []
    future_digital: list[date] = []
    for entry in release_dates_payload.get("results", []):
        if entry.get("iso_3166_1") != region:
            continue
        for rel in entry.get("release_dates", []):
            rel_type = rel.get("type")
            parsed = _parse_iso_date(rel.get("release_date"))
            if parsed is None:
                continue
            if rel_type in AVAILABILITY_RELEASE_TYPES and parsed <= today:
                available.append(parsed)
            if rel_type == DIGITAL_RELEASE_TYPE and parsed > today:
                future_digital.append(parsed)
    available_since = min(available) if available else None
    next_digital_date = min(future_digital) if future_digital and available_since is None else None
    return MovieRelease(available_since=available_since, next_digital_date=next_digital_date)


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
    tmdb_id: int, digital_date: date | None, region: str
) -> ReleaseCandidate | None:
    if digital_date is None:
        return None
    return ReleaseCandidate(
        kind=EventKind.MOVIE_DIGITAL,
        source_event_key=f"movie:{tmdb_id}:digital:{region}",
        scheduled_date=digital_date,
    )


def tv_release_candidate(tmdb_id: int, details: dict, today: date) -> ReleaseCandidate | None:
    """Derive the current TV episode event from `next_episode_to_air`.

    Identity is the series id plus season and episode numbers. An unknown air
    date yields no candidate; the title stays active for daily polling. A past
    air date is ignored (the episode already aired).
    """
    nxt = details.get("next_episode_to_air")
    if not nxt:
        return None
    season = nxt.get("season_number")
    episode = nxt.get("episode_number")
    air = _parse_iso_date(nxt.get("air_date"))
    if season is None or episode is None or air is None or air < today:
        return None
    return ReleaseCandidate(
        kind=EventKind.TV_EPISODE,
        source_event_key=f"tv:{tmdb_id}:s{int(season)}e{int(episode)}",
        scheduled_date=air,
        season_number=int(season),
        episode_number=int(episode),
    )
