"""Time-weighted power uptime from recorder history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from homeassistant.components.recorder import history
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

POWER_ON_STATE = "on"
UPTIME_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class PowerUptimeStats:
    """Seconds spent powered on within the measurement window."""

    seconds_on: float
    period_seconds: float


def _floored_timestamp(incoming_dt: datetime) -> float:
    return math.floor(dt_util.as_timestamp(incoming_dt))


def _compute_seconds_on(
    states: list[State],
    *,
    on_states: set[str],
    start_timestamp: float,
    end_timestamp: float,
    now_timestamp: float,
) -> float:
    """Return seconds spent in on_states between start and end."""
    previous_state_matches = False
    last_state_change_timestamp = 0.0
    elapsed = 0.0

    for state in states:
        current_state_matches = state.state in on_states
        state_change_timestamp = state.last_changed_timestamp

        if math.floor(state_change_timestamp) > end_timestamp:
            break
        if math.floor(state_change_timestamp) > now_timestamp:
            break

        if not previous_state_matches and current_state_matches:
            last_state_change_timestamp = max(start_timestamp, state_change_timestamp)
        elif previous_state_matches and not current_state_matches:
            elapsed += state_change_timestamp - last_state_change_timestamp

        previous_state_matches = current_state_matches

    if previous_state_matches:
        measure_end = min(end_timestamp, now_timestamp)
        elapsed += max(0.0, measure_end - last_state_change_timestamp)

    return elapsed


def compute_power_uptime(
    hass: HomeAssistant,
    entity_id: str,
    *,
    duration: timedelta = UPTIME_WINDOW,
    on_states: set[str] | None = None,
) -> PowerUptimeStats | None:
    """Compute time-weighted powered-on seconds over the given window."""
    if on_states is None:
        on_states = {POWER_ON_STATE}

    utc_now = dt_util.utcnow()
    period_start = utc_now - duration
    period_end = utc_now

    start_timestamp = _floored_timestamp(period_start)
    end_timestamp = _floored_timestamp(period_end)
    now_timestamp = _floored_timestamp(utc_now)

    states = history.state_changes_during_period(
        hass,
        period_start,
        period_end,
        entity_id,
        include_start_time_state=True,
        no_attributes=True,
    ).get(entity_id, [])

    seconds_on = _compute_seconds_on(
        states,
        on_states=on_states,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        now_timestamp=now_timestamp,
    )
    period_seconds = (period_end - period_start).total_seconds()
    if period_seconds <= 0:
        return None
    return PowerUptimeStats(seconds_on=seconds_on, period_seconds=period_seconds)


def uptime_ratio_percent(stats: PowerUptimeStats) -> float:
    """Convert matched seconds into a 0-100 percentage."""
    return round(100 * stats.seconds_on / stats.period_seconds, 1)
