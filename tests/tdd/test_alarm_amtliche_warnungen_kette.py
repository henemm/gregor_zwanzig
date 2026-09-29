"""TDD RED — Issue #2422 Scheibe S4, Bein amtliche Warnungen: Drei-Zustand-
Vorrangprüfung (AC-3/AC-4) und der Bug-Fall im Sammellauf-Vorabfilter (AC-5).

SPEC: docs/specs/modules/fix_2422_s4_alarm_familie_kette.md (AC-3, AC-4, AC-5).

Zwei verschiedene Einstiegspunkte, bewusst getrennt geprüft:

* AC-3/AC-4 rufen den ÖFFENTLICHEN Einstiegspunkt
  `TripAlertService.check_official_alert_triggers()` direkt (Drei-Zustand-
  Vorrangprüfung, trip_alert.py:2577-2587) — dort ist der Bug NICHT: die
  Prüfung selbst ist bereits korrekt.
* AC-5 ruft den REGULÄREN Sammellauf `check_all_trips()` — dort sitzt der
  Vorab-Filter (trip_alert.py:895-911), der `check_official_alert_triggers()`
  bei widersprüchlichem Legacy-Feld nie erreicht (Bug #2422). AC-5 ist die
  EINZIGE Bug-reproduzierende AC dieser Datei — rot vor dem Fix, grün danach.

Provider-Abruf und Wetter-Snapshot sind über `tests/tdd/_alarm_amtlich_fixtures.py`
durch deterministische Ersatzfunktionen ersetzt (kein Netz, kein `Mock()`).
Versand/Kanäle laufen ECHT über `TripAlertService`/`NotificationService` und
werden am Transport abgegriffen (`tests/helpers/transport_mitschrift.py`,
S1–S3-Muster).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from freezegun import freeze_time

from app.loader import save_trip
from services.trip_alert import TripAlertService

from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._alarm_amtlich_fixtures import (
    amtlich_trip, amtliche_warnung, segmentgeometrie, stelle_amtliche_quelle,
    stelle_cache_fuer_amtliche_kette,
)
from tests.tdd._einstellung_auslieferung_fixtures import TRANSPORT_ENV
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import _AT, _settings_all_channels, _write_tier


def _uid(tag: str) -> str:
    return f"tdd-2422s4-{tag}-{uuid.uuid4().hex[:6]}"


@dataclass
class _AmtlicherLauf:
    """Dieselbe Form wie `AlarmPruefstreckeLauf` (vier Kanal-Listen) — diese
    Datei nutzt `AlarmPruefstrecke` NICHT (sie ruft die amtlichen
    Einstiegspunkte direkt), hält die Auswertung aber vergleichbar."""
    mail: list = field(default_factory=list)
    telegram: list = field(default_factory=list)
    sms: list = field(default_factory=list)
    premium_sms: list = field(default_factory=list)


def _zu_lauf(mit: Kanalmitschrift) -> _AmtlicherLauf:
    return _AmtlicherLauf(
        mail=mit.sendungen("email"), telegram=mit.sendungen("telegram"),
        sms=mit.sendungen("sms"), premium_sms=mit.sendungen("premium_sms"),
    )


def _lauf_amtliche_kette(
    monkeypatch, uid: str, fixture_name: str, *, at, heute=None, tier: str = "premium",
    **trip_overrides,
) -> tuple[list, bool, _AmtlicherLauf]:
    """EIN amtlicher Kette-Lauf: Golden-Fixture über `app.loader` laden ->
    echte Kanal-/Transport-Umgebung -> `check_official_alert_triggers()`
    ECHT aufrufen -> bei Treffern `_send_official_alert_only()` ECHT
    ausliefern. Gibt (notices, geliefert, lauf) zurück.

    `settings=_settings_all_channels()` wird direkt an `TripAlertService`
    übergeben (kein `with_user_profile()`-Merge nötig, s. Moduldoku) —
    ausreichend für E-Mail/Telegram/SMS; Premium-SMS wird von dieser Kette
    nicht geprüft.
    """
    for k, v in TRANSPORT_ENV.items():
        monkeypatch.setenv(k, v)
    mit = aufzeichner_installieren(monkeypatch)
    _write_tier(uid, tier)
    trip = amtlich_trip(fixture_name, uid, heute=heute, **trip_overrides)
    svc = TripAlertService(settings=_settings_all_channels(), user_id=uid)
    with freeze_time(at):
        notices = svc.check_official_alert_triggers(trip)
        geliefert = svc._send_official_alert_only(trip, notices) if notices else False
    return notices, geliefert, _zu_lauf(mit)


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_official_warnings_enabled_hat_vorrang(monkeypatch):
    """AC-3 (Charakterisierung, heute GRÜN — der Bug sitzt NICHT hier).
    GIVEN ein geladener Trip mit `official_warnings.enabled=true` und einem
    widersprüchlichen Legacy-Feld `official_alert_triggers_enabled=false`,
    sowie KEINER aktiven Wetter-Delta-Regel (Golden-Fixture
    `golden_amtlich_fall1`) / WHEN `check_official_alert_triggers()` direkt
    für eine echte amtliche Warnmeldung ausgeführt wird / THEN wird die
    amtliche Alarm-Nachricht über die eingeschalteten Kanäle ausgeliefert —
    der aktuelle Schalter hat Vorrang vor dem veralteten Feld
    (trip_alert.py:2577-2580).
    """
    uid = _uid("ac3")
    try:
        alert = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        stelle_amtliche_quelle(monkeypatch, [alert])
        stelle_cache_fuer_amtliche_kette(monkeypatch, route_geometrie=segmentgeometrie(_AT))

        notices, geliefert, lauf = _lauf_amtliche_kette(
            monkeypatch, uid, "golden_amtlich_fall1", at=_AT,
            alert_channels={"email": True, "telegram": True},
        )

        assert notices, (
            "AC-3: check_official_alert_triggers() muss trotz "
            "widersprüchlichem Legacy-Feld eine Warnung finden (war leer)."
        )
        assert geliefert is True, (
            "AC-3: die amtliche Alarm-Nachricht muss ausgeliefert werden "
            "(der aktuelle Schalter hat Vorrang)."
        )
        assert lauf.mail and lauf.telegram, (
            f"AC-3: beide eingeschalteten Kanäle müssen bedient werden: "
            f"mail={lauf.mail!r} telegram={lauf.telegram!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_legacy_feld_traegt_bei_fehlendem_official_warnings_block(monkeypatch):
    """AC-4 (Charakterisierung, heute GRÜN). GIVEN ein geladener Trip OHNE
    `official_warnings`-Block (Alt-Daten-Fall, Golden-Fixture
    `golden_amtlich_fall2_altdaten`) und `official_alert_triggers_enabled=
    true` / WHEN derselbe Auslöser läuft / THEN wird die amtliche
    Alarm-Nachricht wie beim aktuellen Schalter ausgeliefert — Altbestand
    ohne den neuen Block funktioniert unverändert weiter
    (trip_alert.py:2581-2582).
    """
    uid = _uid("ac4")
    try:
        alert = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        stelle_amtliche_quelle(monkeypatch, [alert])
        stelle_cache_fuer_amtliche_kette(monkeypatch, route_geometrie=segmentgeometrie(_AT))

        notices, geliefert, lauf = _lauf_amtliche_kette(
            monkeypatch, uid, "golden_amtlich_fall2_altdaten", at=_AT,
            alert_channels={"email": True, "telegram": True},
        )

        assert notices, (
            "AC-4: check_official_alert_triggers() muss auch ohne "
            "official_warnings-Block über das Legacy-Feld auslösen (war leer)."
        )
        assert geliefert is True, (
            "AC-4: die amtliche Alarm-Nachricht muss wie beim aktuellen "
            "Schalter ausgeliefert werden."
        )
        assert lauf.mail and lauf.telegram, (
            f"AC-4: beide eingeschalteten Kanäle müssen bedient werden: "
            f"mail={lauf.mail!r} telegram={lauf.telegram!r}"
        )
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


def test_bugfall_vorab_filter_blockiert_nicht_mehr_trotz_veraltetem_legacy_feld(monkeypatch):
    """AC-5 (BUG-FALL — rot vor dem Fix, grün danach). GIVEN ein geladener
    Trip mit `official_warnings.enabled=true`,
    `official_alert_triggers_enabled=false` (historisch vor #1258
    ausgeschaltet) und KEINER aktiven Wetter-Delta-Regel (Golden-Fixture
    `golden_amtlich_fall3_bug`, identische Werte wie Fall 1 — der
    Unterschied ist NUR der Einstiegspunkt) / WHEN der REGULÄRE Sammellauf
    `check_all_trips()` (nicht `check_official_alert_triggers()` isoliert)
    für eine echte amtliche Warnmeldung läuft / THEN wird der Trip NICHT
    übersprungen und die amtliche Alarm-Nachricht wird ausgeliefert.

    RED heute: der Vorab-Filter (trip_alert.py:895-911) prüft nur das
    veraltete Feld (`official_alert_triggers_enabled is not False` == False)
    und überspringt den Trip in Zeile 906-911 komplett, BEVOR
    `check_official_alert_triggers()` (Zeile 930) überhaupt erreicht wird —
    Aufzeichner bleibt leer, `alerts_sent == 0`. Bug-Nachweis aus
    Nutzersicht: der Sammellauf-Einstieg wird verwendet, nicht der
    öffentliche Einstiegspunkt isoliert (sonst fängt der Test den Bug
    nicht — s. AC-3, das über denselben Datenstand GRÜN ist).
    """
    uid = _uid("ac5")
    try:
        alert = amtliche_warnung(4, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))
        stelle_amtliche_quelle(monkeypatch, [alert])
        stelle_cache_fuer_amtliche_kette(monkeypatch, route_geometrie=segmentgeometrie(_AT))

        for k, v in TRANSPORT_ENV.items():
            monkeypatch.setenv(k, v)
        mit = aufzeichner_installieren(monkeypatch)
        _write_tier(uid, "premium")
        trip = amtlich_trip(
            "golden_amtlich_fall3_bug", uid, heute=_AT,
            alert_channels={"email": True, "telegram": True},
        )
        with freeze_time(_AT):
            save_trip(trip, user_id=uid)

        svc = TripAlertService(settings=_settings_all_channels(), user_id=uid)
        with freeze_time(_AT):
            ergebnis = svc.check_all_trips()

        assert ergebnis.checked == 1, (
            f"AC-5 Vorbedingung: genau EIN Trip muss geprüft worden sein "
            f"(war checked={ergebnis.checked})."
        )
        assert ergebnis.alerts_sent == 1, (
            f"AC-5: der Sammellauf muss den Trip TROTZ des widersprüchlichen "
            f"Legacy-Felds bedienen — vor dem Fix wird er in "
            f"trip_alert.py:906-911 komplett übersprungen (war "
            f"alerts_sent={ergebnis.alerts_sent}, skipped={ergebnis.skipped})."
        )
        lauf = _zu_lauf(mit)
        assert lauf.mail and lauf.telegram, (
            f"AC-5: die amtliche Alarm-Nachricht muss tatsächlich auf "
            f"beiden eingeschalteten Kanälen ankommen: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r}"
        )
    finally:
        _clean_user(uid)
