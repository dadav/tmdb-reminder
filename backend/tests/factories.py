"""Test doubles and TMDB payload builders shared across integration tests."""

from __future__ import annotations

from datetime import date

from tmdb_reminder.errors import TmdbUnavailableError


def movie_details(
    tmdb_id: int,
    *,
    title: str = "The Matrix",
    digital: date | None = None,
    region: str = "DE",
    release_year: str = "1999-03-31",
) -> dict:
    release_dates: dict = {"results": []}
    if digital is not None:
        release_dates["results"].append(
            {
                "iso_3166_1": region,
                "release_dates": [
                    {"type": 4, "release_date": f"{digital.isoformat()}T00:00:00.000Z"}
                ],
            }
        )
    return {
        "id": tmdb_id,
        "title": title,
        "original_title": title,
        "overview": "overview",
        "poster_path": "/p.jpg",
        "release_date": release_year,
        "release_dates": release_dates,
    }


def tv_details(
    tmdb_id: int,
    *,
    name: str = "Game of Thrones",
    air_date: date | None = None,
    season: int = 1,
    episode: int = 1,
) -> dict:
    nxt = None
    if air_date is not None:
        nxt = {
            "air_date": air_date.isoformat(),
            "season_number": season,
            "episode_number": episode,
            "name": "Episode",
        }
    return {
        "id": tmdb_id,
        "name": name,
        "original_name": name,
        "overview": "overview",
        "poster_path": "/t.jpg",
        "first_air_date": "2011-04-17",
        "next_episode_to_air": nxt,
    }


class FakeAdapter:
    """In-memory stand-in for TmdbAdapter. Set payloads or an error per id."""

    def __init__(self) -> None:
        self.movies: dict[int, dict] = {}
        self.tvs: dict[int, dict] = {}
        self.search_payload: dict = {"page": 1, "results": [], "total_pages": 1, "total_results": 0}
        self.fail_ids: set[int] = set()

    async def movie_details(self, tmdb_id: int) -> dict:
        if tmdb_id in self.fail_ids:
            raise TmdbUnavailableError("boom")
        return self.movies[tmdb_id]

    async def tv_details(self, tmdb_id: int) -> dict:
        if tmdb_id in self.fail_ids:
            raise TmdbUnavailableError("boom")
        return self.tvs[tmdb_id]

    async def multi_search(self, query: str, page: int) -> dict:
        return self.search_payload

    async def check_connectivity(self) -> bool:
        return True


class FakeGotify:
    """In-memory Gotify client. Records sends; can be forced to fail."""

    def __init__(self) -> None:
        self.sent: list = []
        self.next_id = 100
        self.error: Exception | None = None

    async def send(self, message) -> int:
        if self.error is not None:
            raise self.error
        self.sent.append(message)
        mid = self.next_id
        self.next_id += 1
        return mid

    async def send_test(self) -> int:
        return await self.send(None)

    async def check_connectivity(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass
