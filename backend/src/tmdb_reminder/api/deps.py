"""FastAPI dependencies.

Shared resources live on `app.state` (set during lifespan). These providers hand
them to route handlers and yield a per-request database session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..notifications.gotify import GotifyClient
from ..tmdb.adapter import TmdbAdapter
from ..tracking.service import TrackingService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.session_factory() as session:
        yield session


def get_tracking(request: Request) -> TrackingService:
    return request.app.state.tracking


def get_adapter(request: Request) -> TmdbAdapter:
    return request.app.state.adapter


def get_gotify(request: Request) -> GotifyClient:
    return request.app.state.gotify


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TrackingDep = Annotated[TrackingService, Depends(get_tracking)]
AdapterDep = Annotated[TmdbAdapter, Depends(get_adapter)]
GotifyDep = Annotated[GotifyClient, Depends(get_gotify)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
