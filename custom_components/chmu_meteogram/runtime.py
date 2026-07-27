"""Sdílený stav integrace uložený v hass.data."""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import ChmuCoordinator
from .radar_coordinator import ChmuRadarCoordinator


@dataclass
class ChmuRuntime:
    """Koordinátory jedné instance — meteogram a (volitelně) radar."""

    coordinator: ChmuCoordinator
    radar: ChmuRadarCoordinator | None = None
