"""EIN Versand-Orchestrator fuer Trip + Compare (Issue #1207).

SPEC: docs/specs/modules/dispatch_orchestrator.md

Duenner geteilter Seam: `run_briefing_dispatch(kind, user_id, now_utc)` kapselt
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
from app.loader import get_data_root

if TYPE_CHECKING:
    from datetime import datetime

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

    def collect_due(self, now_utc: "datetime") -> list:
        return self._service._collect_due_trips(now_utc)

    def pre_pass(self, now_utc: "datetime", due: list) -> None:
        # Issue #1012 (b2): Catch-up ZUERST, offene Nachliefer-Marker vor den
        # regulaeren faelligen Slots abarbeiten (AC-6/AC-7).
        # Issue #1725: `collect_due` liefert (trip, report_type, ortstag).
        due_trip_ids_now = {trip.id for trip, _, _ in due}
        self._sent += self._service._process_pending_markers(now_utc, due_trip_ids_now)

    def dispatch_one(self, item, now_utc: "datetime") -> None:
        trip, report_type, local_day = item
        try:
            # Issue #1725: NICHT direkt `_send_trip_report_outcome` -- der
            # Wrapper reserviert zuerst den Vermerk (trip_id, ortstag, slot)
            # und gibt ihn je nach Ausgang frei. Er ist bewusst die EINZIGE
            # Stelle, die den Vermerk anfasst: die On-Demand-Pfade rufen
            # weiterhin `_send_trip_report_outcome` und bleiben unberuehrt.
            # Issue #1897: `now_utc` ist DER Zeitpunkt dieses Laufs, nicht eine
            # frische Uhrabfrage -- er entscheidet in `reserve`, ob ein Vermerk
            # ohne Ausgang zu einem laufenden Versand gehoert oder verwaist ist.
            outcome = self._service._dispatch_due_item(
                trip, report_type, local_day, now_utc=now_utc,
            )
            if outcome is None:
                # Kein Versandversuch (Slot bereits vermerkt oder Sperre nicht
                # zu bekommen). Weder gesendet noch technisch fehlgeschlagen --
                # der Wrapper hat den Grund bereits protokolliert.
                return
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

    2s-Delay zwischen Presets (PO-Entscheidung 2026-07-16, #1207): seit #1270
    versendet Compare drei Kanaele (E-Mail+Telegram+SMS) pro Preset -- ohne
    Pause besteht Rate-Limit-Risiko bei Resend/Telegram. Trip hat den gleichen
    Schutz seit #766. Kein SMTP-Vorab-Guard (per-Preset statt global) --
    `collect_due`/`pre_pass`/`dispatch_one` rufen ausschliesslich bestehende
    Funktionen aus `scheduler_dispatch_service.py` auf.
    """

    inter_mail_delay: float = 2.0
    smtp_guard: bool = False

    def __init__(self, settings: Settings, user_id: str, data_root: str | None = None) -> None:
        self._settings = settings
        self._user_id = user_id
        self._data_root = data_root or str(get_data_root())
        self._presets: list = []
        self._all_locations = None
        self._success = 0
        self._failed = 0  # Issue #1290 (E1): Fehlschlaege zaehlen, nicht nur Erfolge

    def empty_result(self) -> tuple[int, int]:
        return (0, 0)

    #: Referenz-Zone des manuellen `?hour=`-Testausloesers
    #: (`scheduler_dispatch_service.run_compare_presets_daily`) -- reines
    #: Ops-/Debug-Werkzeug ohne Preset-Bezug. Die FAELLIGKEIT selbst haengt
    #: seit #1726 an der Ortszone des jeweiligen Presets, nicht mehr hier.
    MANUAL_TRIGGER_REFERENCE_ZONE = "Europe/Vienna"

    def collect_due(self, now_utc: "datetime") -> list:
        from app.loader import load_all_locations
        from services.compare_slot_scheduler import presets_due_for_hour
        from services.scheduler_dispatch_service import _load_presets_for_dispatch

        presets = _load_presets_for_dispatch(self._user_id, self._data_root)
        if presets is None:
            return []
        self._presets = presets
        # Issue #1726: jedes Preset wird gegen die Ortszone SEINES ersten
        # aufloesbaren Orts geprueft -- ein globaler `vor_ort` kann das nicht
        # abbilden. Ortsliste deshalb vorab laden (bisher lazy) und mitgeben.
        if self._all_locations is None:
            self._all_locations = load_all_locations(user_id=self._user_id)
        by_id = {loc.id: loc for loc in self._all_locations}
        return presets_due_for_hour(presets, by_id, now_utc)

    def pre_pass(self, now_utc: "datetime", due: list) -> None:
        # Issue #1250 Scheibe 3 (AC-10/AC-11/AC-12): Auto-Pause fuer Presets
        # mit ueberschrittenem end_date -- unabhaengig vom Faelligkeits-Slot.
        from services.scheduler_dispatch_service import _auto_pause_expired_presets

        # Issue #1727 S5b: `now_utc` liegt hier bereits als Parameter vor und
        # die Ortsliste hat `collect_due` schon geladen -- beides wird
        # durchgereicht, damit der Ablauf gegen den ORTSTAG des Presets
        # geprueft wird (ADR-0044) statt gegen den Servertag. Keine zweite
        # Zeitabfrage, kein zweiter Ladevorgang.
        _auto_pause_expired_presets(
            self._presets, self._user_id, self._data_root,
            now_utc, self._all_locations or [],
        )

    def dispatch_one(self, item, now_utc: "datetime | None" = None) -> None:
        # `now_utc` gehoert zur geteilten Strategie-Schnittstelle (Issue #1897,
        # Trip-Seite). Der Compare-Pfad traegt seinen Tagesbezug bereits im
        # `item` (`target_date`, `tage_ab_ortstag`) und braucht ihn nicht.
        from app.loader import load_all_locations
        from services.scheduler_dispatch_service import _dispatch_due_preset

        # Issue #1661 (Adversary-Finding F003): `collect_due` liefert den
        # Tagesbezug in BEIDEN Formen — absoluter Zieltag UND Versatz gegen den
        # Ortstag, beide aus derselben Zeitabfrage. Der Versatz wird hier
        # durchgereicht statt spaeter aus einer zweiten `date.today()`-
        # Auswertung rekonstruiert; zwischen `collect_due` und diesem Aufruf
        # liegen Wetterabruf, Rendering und die 2s-Warteschlange je
        # vorangehendem Preset, und damit moeglicherweise eine Mitternacht.
        preset, target_date, tage_ab_ortstag = item
        # Lazy: erst laden, wenn ein faelliges Preset zu verarbeiten ist (#649).
        if self._all_locations is None:
            self._all_locations = load_all_locations(user_id=self._user_id)
        if _dispatch_due_preset(
            preset, target_date, self._settings, self._user_id, self._data_root,
            self._all_locations, tage_ab_ortstag=tage_ab_ortstag,
        ):
            self._success += 1
        else:
            # Issue #1290 (E1): _dispatch_due_preset faengt bereits jede
            # Exception (ValueError/Exception) und liefert False; Fehler-
            # Isolation bleibt UNVERAENDERT (kein Abbruch der Schleife).
            self._failed += 1

    def result(self) -> tuple[int, int]:
        return (self._success, self._failed)


_STRATEGY = {
    "route": TripDispatchStrategy,
    "vergleich": CompareDispatchStrategy,
}


def run_briefing_dispatch(
    kind: str, user_id: str, now_utc: "datetime", data_root: str | None = None,
    settings: Settings | None = None,
):
    """Gemeinsamer Versand-Einstieg fuer Trip (`route`) und Vergleich (`vergleich`).

    Kapselt das geteilte Skelett: Settings-Laden, Strategie-Aufloesung,
    kind-Hook `pre_pass`, Faelligkeitssammlung `collect_due`, Schleife mit
    Fehler-Isolation + `inter_mail_delay` zwischen Sends, Rueckgabe im
    kind-eigenen Format -- Trip `(sent, failed)` seit #766/#1012, Compare
    ebenfalls `(sent, failed)` seit Issue #1290 (E1, Epic #1301 Scheibe E):
    die vormalige Aussage "KEINE Vereinheitlichung" (#1207) galt nur bis zum
    Prod-Journal-Befund 2026-07-16 (133/133 stille Fehlschlaege) -- beide
    Strategien liefern jetzt dasselbe Tupel-Format, ohne dass ein Kind vom
    anderen abhaengt.

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

    due = strategy.collect_due(now_utc)
    strategy.pre_pass(now_utc, due)

    for i, item in enumerate(due):
        strategy.dispatch_one(item, now_utc)
        # 2s Pause zwischen aufeinanderfolgenden Mails (nicht nach der
        # letzten) -- Rate-Limit-Schutz: Trip seit #766, Compare seit
        # 2026-07-16 (#1207, drei Kanaele pro Preset seit #1270). Beide 2.0s.
        if i < len(due) - 1:
            time_module.sleep(strategy.inter_mail_delay)

    return strategy.result()
