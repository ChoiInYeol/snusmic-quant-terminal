"""Persona implementations.

Each module exposes a single ``simulate_<persona>(...) -> PersonaRunOutput``
entrypoint that takes the warehouse-derived inputs and returns the account's
trades + daily equity snapshots. The runner in :mod:`..runner` dispatches
based on the ``persona_name`` discriminator on the persona config.
"""

from .all_weather import simulate_all_weather
from .base import PersonaRunOutput, build_summary, record_equity_point
from .prophet import simulate_prophet
from .smic_follower import simulate_smic_follower
from .smic_follower_v2 import simulate_smic_follower_v2
from .weak_prophet import simulate_weak_prophet

__all__ = [
    "PersonaRunOutput",
    "build_summary",
    "record_equity_point",
    "simulate_all_weather",
    "simulate_prophet",
    "simulate_smic_follower",
    "simulate_smic_follower_v2",
    "simulate_weak_prophet",
]
