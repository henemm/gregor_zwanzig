"""Issue #2050 Scheibe S6 — Unterdrueckungs-Eintraege (`not_delivered`) und
die E-1-Groessen: AC-9 (frueh, VOR dem Nowcast-Abruf -- strukturell nichts
bekannt) und AC-10 (spaet, NACH dem Abruf -- die Vergleichsbasis ist die
Begruendung der Unterdrueckung selbst).

SPEC: docs/specs/modules/alarm_protokoll_vorwarnzeit.md (AC-9, AC-10)

Beide Laeufe ueber `AlarmPruefstrecke` (S1, `zweig="radar"`) gegen die echte
Auslöseentscheidung. Kein Mock()/patch()/MagicMock.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from app.loader import get_data_dir
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary,
)
from services.radar_service import NowcastResult, RadarNowcastService
from services.throttle_store import ThrottleStore
from services.weather_snapshot import WeatherSnapshotService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels,
)
from tests.tdd.test_issue_1070_daily_alert_limit import _segment

_ANGELEGT: list[str] = []
_SECHS_SCHLUESSEL = (
    "lead_time_minutes", "event_at", "event_end_at",
    "measurement_point", "reference_at", "source",
)


def _uid(tag: str) -> str:
    uid = f"tdd-2050-s6-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _aufraeumen() -> None:
    for uid in _ANGELEGT:
        _clean_user(uid)
    _ANGELEGT.clear()


class _FixedRadar(RadarNowcastService):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        kwargs.setdefault("intensity_label", "leichter Regen")
        kwargs.setdefault("source", "radar")
        self._fixed = NowcastResult(**kwargs)

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        return self._fixed


def _not_delivered_entry_for(uid: str, entity_id: str) -> dict:
    path = get_data_dir(uid) / "alert_log.json"
    data = json.loads(path.read_text())
    treffer = [e for e in data.get("not_delivered", []) if e.get("entity_id") == entity_id]
    assert treffer, f"kein not_delivered-Eintrag fuer {entity_id!r} in {path}: {data!r}"
    return treffer[-1]


def test_ac9_fruehe_sperrzeit_unterdrueckt_nowcast_ohne_jede_der_sechs_groessen():
    """AC-9: Cooldown/Ruhezeit-Gate VOR dem Nowcast-Abruf -- an dieser
    Stelle existiert noch kein `result`, strukturell nichts bekannt.

    BEWUSST von Anfang an GRUEN (Vorbild: `test_alarm_szenario_
    laufendes_ereignis.py::test_ac2_...`, dort ausdruecklich als
    Regressions-Invariante markiert): die sechs neuen Schluessel fehlen
    HEUTE (vor GREEN) UND NACH GREEN an dieser Aufrufstelle gleichermassen,
    weil trip_alert.py:1299 laut Spec-Tabelle keinen der sechs kwargs je
    uebergibt. Die Positivkontrolle, dass die Pruefung ueberhaupt etwas
    MISST (und nicht bloss einen durchgehend leeren Pfad bestaetigt), liefert
    der direkte Nachbar-Test `test_ac10_...` in dieser Datei: SELBE
    Codefamilie (`append_suppressed_entry`, Radar-Nowcast-Zweig), aber am
    SPAETEREN Gate traegt der Eintrag dieselben Schluessel sehr wohl.
    """
    uid = _uid("ac9")
    try:
        trip = _radar_trip(uid, "trip-2050-s6-ac9", send_email=True)
        # Cooldown-Fenster (Default 120 Min, `AlarmPruefstrecke(throttle_hours=2)`)
        # aus einem vorherigen Lauf VOR dem eigentlichen Prueflauf gebucht.
        ThrottleStore(uid).record("radar", trip.id, _AT - timedelta(minutes=10))

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip, radar_service=_FixedRadar(onset_minutes=12),
        )
        assert lauf.triggered_count == 0, (
            f"AC-9 Vorbedingung: der gebuchte Cooldown muss den Alarm unterdruecken "
            f"(war triggered_count={lauf.triggered_count})."
        )
        entry = _not_delivered_entry_for(uid, trip.id)
        gruende = {c.get("reason") for c in entry.get("channels_not_sent") or []}
        assert gruende, (
            f"AC-9 Vorbedingung: kein Unterdrueckungs-Grund im Eintrag: {entry!r}"
        )
        for schluessel in _SECHS_SCHLUESSEL:
            assert schluessel not in entry, (
                f"AC-9: {schluessel!r} darf am fruehen Gate NICHT im Eintrag "
                f"stehen -- an dieser Stelle ist strukturell nichts bekannt: {entry!r}"
            )
    finally:
        _aufraeumen()


def test_ac10_briefing_ankuendigung_unterdrueckt_nowcast_aber_traegt_die_vergleichsbasis():
    """AC-10: das Gate NACH dem Abruf (Briefing hatte die Menge bereits
    angekuendigt) -- hier ist der Briefing-Schnappschuss die Begruendung der
    Unterdrueckung und muss als `reference_at` im Eintrag stehen, zusammen mit
    den vier weiteren an dieser Stelle bereits bekannten Groessen."""
    uid = _uid("ac10")
    try:
        trip = _radar_trip(uid, "trip-2050-s6-ac10", send_email=True)
        trip.alert_cooldown_minutes = 0  # nur das Briefing-Gate soll greifen

        onset_minutes = 12
        onset_hour_utc = (_AT + timedelta(minutes=onset_minutes)).replace(
            minute=0, second=0, microsecond=0,
        )
        schnappschuss_zeit = _AT - timedelta(hours=3)
        snapshot_segment = SegmentWeatherData(
            segment=_segment(1),
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
                data=[ForecastDataPoint(ts=onset_hour_utc, precip_1h_mm=2.0)],
            ),
            aggregated=SegmentWeatherSummary(),
            fetched_at=schnappschuss_zeit,
            provider="openmeteo",
        )
        WeatherSnapshotService(uid).save_dated(trip.id, _AT.date(), [snapshot_segment])

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_FixedRadar(onset_minutes=onset_minutes),
        )
        assert lauf.triggered_count == 0, (
            f"AC-10 Vorbedingung: die Briefing-Ankuendigung (2.0mm >= 0.5mm) "
            f"muss den Alarm unterdruecken (war triggered_count={lauf.triggered_count})."
        )
        entry = _not_delivered_entry_for(uid, trip.id)
        gruende = {c.get("reason") for c in entry.get("channels_not_sent") or []}
        assert any((g or "").startswith("briefing_announced:") for g in gruende), (
            f"AC-10 Vorbedingung: falscher Unterdrueckungs-Grund: {entry!r}"
        )

        assert entry.get("lead_time_minutes") == onset_minutes, (
            f"AC-10: lead_time_minutes fehlt/falsch: {entry!r}"
        )
        assert "event_at" in entry, f"AC-10: event_at fehlt: {entry!r}"
        mp = entry.get("measurement_point")
        assert mp is not None and {"segment_id", "km_from", "km_to"} <= set(mp), (
            f"AC-10: measurement_point fehlt/unvollstaendig: {entry!r}"
        )
        assert entry.get("source") == "radar", (
            f"AC-10: source muss der ROHE Quellen-Schluessel sein, nicht die "
            f"Beschriftung aus `source_label()` (Spec-Abschnitt \"Korrektur: "
            f"`source` ist immer der rohe Schluessel\"): {entry!r}"
        )
        assert "reference_at" in entry, (
            f"AC-10: reference_at (der Briefing-Schnappschusszeitpunkt, der die "
            f"Unterdrueckung begruendet) fehlt: {entry!r}"
        )
        assert datetime.fromisoformat(entry["reference_at"]) == schnappschuss_zeit, (
            f"AC-10: reference_at muss GENAU der Schnappschuss-Zeitpunkt sein, "
            f"der die Unterdrueckung begruendet: {entry.get('reference_at')!r}"
        )
    finally:
        _aufraeumen()


def test_vergleichsbasis_ist_opt_in_und_verschiebt_den_alarm_footer_nicht():
    """F003 (Adversary 2026-08-22): der segment-eigene Erhebungszeitpunkt ist
    NUR ueber `load_dated(segment_fetched_at=True)` zu haben.

    Ohne den Schalter liefert `load_dated()` weiter den Schreibzeitpunkt der
    Datei -- und nur dieser Weg speist ueber `_get_cached_weather()` den
    nutzersichtbaren Referenz-Zeitpunkt im Alarm-Footer (#1916), dessen
    Formatierung am KALENDERTAG verzweigt ("gestern HH:MM Uhr"). Eine rein
    additive Protokoll-Scheibe darf diese Anzeige nicht verschieben; kippte
    der Vorgabewert, faende es sonst niemand.

    Beide Richtungen in EINEM Test: der Kontrast IST die Positivkontrolle."""
    uid = _uid("f003")
    try:
        schnappschuss_zeit = _AT - timedelta(hours=3)
        segment = SegmentWeatherData(
            segment=_segment(1),
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
                data=[ForecastDataPoint(ts=_AT, precip_1h_mm=2.0)],
            ),
            aggregated=SegmentWeatherSummary(),
            fetched_at=schnappschuss_zeit,
            provider="openmeteo",
        )
        svc = WeatherSnapshotService(uid)
        vorher = datetime.now(timezone.utc)
        svc.save_dated("trip-2050-s6-f003", _AT.date(), [segment])
        nachher = datetime.now(timezone.utc)

        ohne_schalter = svc.load_dated("trip-2050-s6-f003", _AT.date())
        assert vorher <= ohne_schalter[0].fetched_at <= nachher, (
            f"F003: ohne `segment_fetched_at=True` MUSS der Schreibzeitpunkt der "
            f"Datei gelten (Bestandsverhalten, Alarm-Footer #1916) -- war "
            f"{ohne_schalter[0].fetched_at}"
        )

        mit_schalter = svc.load_dated(
            "trip-2050-s6-f003", _AT.date(), segment_fetched_at=True,
        )
        assert mit_schalter[0].fetched_at == schnappschuss_zeit, (
            f"F003: MIT dem Schalter muss der segment-eigene Erhebungszeitpunkt "
            f"herauskommen -- sonst haette die Protokoll-Vergleichsbasis (AC-10) "
            f"keine Quelle: {mit_schalter[0].fetched_at}"
        )
    finally:
        _aufraeumen()
