"""Settings validation for public environment configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conftest import make_settings
from tmdb_reminder.config import Settings


def test_availability_delay_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("AVAILABILITY_DELAY_DAYS", raising=False)
    assert Settings(_env_file=None).availability_delay_days == 0


@pytest.mark.parametrize("value", [0, 1, 30])
def test_availability_delay_accepts_supported_range(value):
    assert Settings(_env_file=None, availability_delay_days=value).availability_delay_days == value


@pytest.mark.parametrize("value", [-1, 31])
def test_availability_delay_rejects_out_of_range_values(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, availability_delay_days=value)


def test_availability_delay_reads_environment(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_DELAY_DAYS", "3")
    assert Settings(_env_file=None).availability_delay_days == 3


def test_test_settings_do_not_inherit_environment_delay(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_DELAY_DAYS", "1")
    assert make_settings().availability_delay_days == 0
