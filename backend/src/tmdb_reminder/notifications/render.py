"""Render a release event into a Markdown Gotify message.

Dates are always ISO `YYYY-MM-DD`. Labels ("Late", "Revised") are app-owned and
remain English regardless of TMDB language.
"""

from __future__ import annotations

from ..enums import EventKind, MediaType
from ..models import NotificationDelivery, ReleaseEvent, TrackedTitle
from ..tmdb.mapping import tmdb_url
from ..value_objects import GotifyMessage


def _identity_line(event: ReleaseEvent) -> str:
    if event.kind == EventKind.TV_EPISODE.value:
        s = event.season_number
        e = event.episode_number
        return f"New episode: Season {s}, Episode {e}"
    return "Digital release"


def render_message(
    title: TrackedTitle,
    event: ReleaseEvent,
    delivery: NotificationDelivery,
    *,
    is_late: bool,
    priority: int,
) -> GotifyMessage:
    labels: list[str] = []
    if delivery.is_revised:
        labels.append("Revised")
    if is_late:
        labels.append("Late")
    prefix = f"[{' / '.join(labels)}] " if labels else ""

    year = f" ({title.release_year})" if title.release_year else ""
    url = tmdb_url(MediaType(title.media_type), title.tmdb_id)
    iso_date = event.scheduled_date.isoformat()

    body_lines = [
        f"**{title.title}**{year}",
        "",
        _identity_line(event),
        f"Expected availability: {iso_date}",
        "",
        f"[View on TMDB]({url})",
    ]
    if labels:
        body_lines.insert(0, f"_{' / '.join(labels)} reminder_")
        body_lines.insert(1, "")

    return GotifyMessage(
        title=f"{prefix}{title.title}",
        markdown="\n".join(body_lines),
        priority=priority,
        click_url=url,
    )
