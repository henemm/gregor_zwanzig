"""EIN Versand-Orchestrator fuer Trip + Compare (Issue #1207).

SPEC: docs/specs/modules/dispatch_orchestrator.md

Duenner geteilter Seam: `run_briefing_dispatch(kind, user_id, hour)` kapselt
das gemeinsame Skelett (Settings-Laden, Faelligkeits-/Delay-/Tally-Schleife)
und delegiert alles Kind-spezifische an eine Strategie (`TripDispatchStrategy`
fuer `kind="route"`, `CompareDispatchStrategy` fuer `kind="vergleich"`). Die
Strategien DELEGIEREN an bestehenden Code (`TripReportSchedulerService` bzw.
`scheduler_dispatch_service`-Funktionen) -- sie kopieren dessen Logik nicht.

Config-Routing (AC-2): kind="route" nutzt intern
`report_config_resolver.resolve_report_render_options` (via die delegierte
`TripReportSchedulerService._send_trip_report_outcome`), kind="vergleich"
nutzt intern `report_config_resolver.resolve_compare_render_options` (via die
delegierte `scheduler_dispatch_service.send_one_compare_preset`) -- dieses
Modul liest `.report_config`/`.display_config` an keiner Stelle direkt.
"""
from __future__ import annotations

import logging
import time as time_module
from typing import TYPE_CHECKING

from app.config import Settings

if TYPE_CHECKING:
    from services.trip_report_scheduler import TripReportSchedulerService

logger = logging.getLogger("dispatch_orchestrator")


class TripDispatchStrategy:
    """Trip-Adapter (`kind="route"`) -- delegiert an `TripReportSchedulerService`.

    Kein 2s-Delay-Verzicht, keine Relocation der Versandlogik: `collect_due`,
    `pre_pass` und `dispatch_one` rufen ausschliesslich bestehende (private)
    Methoden von `TripReportSchedulerService` auf.
    """

    inter_mail_delay: float = 2.0
    smtp_guard: bool = True

    def __init__(self, settings: Settings, user_id: str, data_root: str | None = None) -> None:
        from services.trip_report_scheduler import TripReportSchedulerService

        self._service: "TripReportSchedulerService" = TripReportSchedulerService(
            settings=settings, user_id=user_id,
        )
        self._sent = 0
        self._failed = 0

    def empty_result(self) -> tuple[int, int]:
        return (0, 0)

    def collect_due(self, hour: int) -> list:
        return self._service._collect_due_trips(hour)

    def pre_pass(self, hour: int, due: list) -> None:
        # Issue #1012 (b2): Catch-up ZUERST, offene Nachliefer-Marker vor den
        # regulaeren faelligen Slots abarbeiten (AC-6/AC-7).
        due_trip_ids_now = {trip.id for trip, _ in due}
        self._sent += self._service._process_pending_markers(hour, due_trip_ids_now)

    def dispatch_one(self, item) -> None:
        trip, report_type = item
        try:
            outcome = self._service._send_trip_report_outcome(trip, report_type)
            # Issue #1012 (c): "no_weather" (kompletter Ausfall) zaehlt als
            # failed statt sent -- alle anderen Outcomes bleiben sent.
            if outcome == "no_weather":
                self._failed += 1
            else:
                self._sent += 1
        except Exception as e:
            self._failed += 1
            logger.error("Failed %s report for %s: %s", report_type, trip.id, e)

    def result(self) -> tuple[int, int]:
        return (self._sent, self._failed)


class CompareDispatchStrategy:
    """Compare-Adapter (`kind="vergleich"`) -- delegiert an `scheduler_dispatch_service`.

    Kein 2s-Delay (Non-Goal, Tech-Lead-Entscheidung), kein SMTP-Vorab-Guard
    (per-Preset statt global) -- `collect_due`/`pre_pass`/`dispatch_one` rufen
    ausschliesslich bestehende Funktionen aus `scheduler_dispatch_service.py`
    auf.
    """

    inter_mail_delay: float = 0
    smtp_guard: bool = False

    def __init__(self, settings: Settings, user_id: str, data_root: str | None = None) -> None:
        self._settings = settings
        self._user_id = user_id
        self._data_root = data_root or "data"
        self._presets: list = []
        self._all_locations = None
        self._success = 0

    def empty_result(self) -> int:
        return 0

    def collect_due(self, hour: int) -> list:
        from datetime import date

        from services.compare_slot_scheduler import presets_due_for_hour
        from services.scheduler_dispatch_service import _load_presets_for_dispatch

        presets = _load_presets_for_dispatch(self._user_id, self._data_root)
        if presets is None:
            return []
        self._presets = presets
        return presets_due_for_hour(presets, hour, date.today())

    def pre_pass(self, hour: int, due: list) -> None:
        # Issue #1250 Scheibe 3 (AC-10/AC-11/AC-12): Auto-Pause fuer Presets
        # mit ueberschrittenem end_date -- unabhaengig vom Faelligkeits-Slot.
        from services.scheduler_dispatch_service import _auto_pause_expired_presets

        _auto_pause_expired_presets(self._presets, self._user_id, self._data_root)

    def dispatch_one(self, item) -> None:
        from app.loader import load_all_locations
        from services.scheduler_dispatch_service import _dispatch_due_preset

        preset, target_date = item
        # Lazy: erst laden, wenn ein faelliges Preset zu verarbeiten ist (#649).
        if self._all_locations is None:
            self._all_locations = load_all_locations(user_id=self._user_id)
        if _dispatch_due_preset(
            preset, target_date, self._settings, self._user_id, self._data_root,
            self._all_locations,
        ):
            self._success += 1

    def result(self) -> int:
        return self._success


_STRATEGY = {
    "route": TripDispatchStrategy,
    "vergleich": CompareDispatchStrategy,
}


def run_briefing_dispatch(
    kind: str, user_id: str, hour: int, data_root: str | None = None,
    settings: Settings | None = None,
):
    """Gemeinsamer Versand-Einstieg fuer Trip (`route`) und Vergleich (`vergleich`).

    Kapselt das geteilte Skelett: Settings-Laden, Strategie-Aufloesung,
    kind-Hook `pre_pass`, Faelligkeitssammlung `collect_due`, Schleife mit
    Fehler-Isolation + `inter_mail_delay` zwischen Sends, Rueckgabe im
    kind-eigenen Format (Trip `(sent, failed)`, Compare `count` -- KEINE
    Vereinheitlichung, s. Spec Known Limitations).

    Issue #1207 Fix-Loop F002: optionales `settings` erlaubt der aufrufenden
    Instanz (z.B. `TripReportSchedulerService` mit injiziertem Settings-Objekt
    im Konstruktor), ihr bereits geladenes Settings weiterzureichen statt es
    hier stillschweigend neu zu laden. Default (kein Override) bleibt
    unveraendert: frisches Laden ueber `Settings().with_user_profile`.
    """
    if settings is None:
        settings = Settings().with_user_profile(user_id)
    strategy = _STRATEGY[kind](settings, user_id, data_root)

    if strategy.smtp_guard and not settings.can_send_email():
        return strategy.empty_result()

    due = strategy.collect_due(hour)
    strategy.pre_pass(hour, due)

    for i, item in enumerate(due):
        strategy.dispatch_one(item)
        # 2s Pause zwischen aufeinanderfolgenden Mails (nicht nach der
        # letzten) -- Trip 2.0s Rate-Limit-Schutz (#766), Compare 0.
        if i < len(due) - 1:
            time_module.sleep(strategy.inter_mail_delay)

    return strategy.result()
