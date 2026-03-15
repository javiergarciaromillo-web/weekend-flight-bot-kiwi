from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class SearchConfig:
    weeks_ahead: int
    outbound_days: list[int]
    inbound_days: list[int]
    min_departure_time: time
    direct_only: bool
    allowed_airlines: list[str]


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str


@dataclass(frozen=True)
class DatePair:
    outbound_date: date
    inbound_date: date

    @property
    def pattern_label(self) -> str:
        out_name = self.outbound_date.strftime("%a")
        in_name = self.inbound_date.strftime("%a")
        return f"{out_name} -> {in_name}"

    @property
    def weekend_start(self) -> date:
        return self.outbound_date


@dataclass(frozen=True)
class FlightOption:
    origin: str
    destination: str
    outbound_date: date
    inbound_date: date
    airline: str
    outbound_flight_no: str
    inbound_flight_no: str
    outbound_departure: str
    outbound_arrival: str
    inbound_departure: str
    inbound_arrival: str
    total_price_eur: float
    currency: str = "EUR"

    @property
    def pattern_label(self) -> str:
        out_name = self.outbound_date.strftime("%a")
        in_name = self.inbound_date.strftime("%a")
        return f"{out_name} -> {in_name}"

    @property
    def route_label(self) -> str:
        return f"{self.origin} -> {self.destination}"

    @property
    def trip_label(self) -> str:
        return f"{self.outbound_date.isoformat()} -> {self.inbound_date.isoformat()}"


@dataclass(frozen=True)
class HistoricalRow:
    run_date: date
    weekend_start: date
    pattern_label: str
    best_price_eur: float
