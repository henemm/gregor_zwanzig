"""TDD RED — Der geteilte Nowcast-Freigabe-Baustein (Issue #1467 S3,
AC-11 + AC-12 + AC-13 + AC-15).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md

``src/services/alert_gate.py`` existiert heute nicht — die Reihenfolge
Ruhezeit → Sperrzeit → Tages-Obergrenze steht als Inline-Kette im Trip-Pfad
(``trip_alert.py:748-765``), waehrend der Vergleichs-Pfad eine andere,
unvollstaendige Reihenfolge fuehrt. RED-Grund fuer AC-11: ``ImportError`` —
das Modul fehlt.

Vier Zusicherungen:

* **AC-11 Reihenfolge** — der Ablauf haelt an der ERSTEN zutreffenden Stufe
  an. Nachgewiesen mit einem echten, zaehlenden ``ThrottleStore``
  (Unterklasse, die den echten Speicher weiterbenutzt) statt eines
  Aufruf-Spions auf einem gemockten Objekt.
* **AC-12 Vorrang-Schutz** — der Vergleichs-Nowcast prueft mit
  ``reason="nowcast"`` gegen das VOLLE Tagesbudget. Ein Compare-eigener Grund
  oder ``"forecast_change"`` wuerde die NowCast-Reserve aus #1555 still
  verlieren. Der Test belegt zuerst, dass der gewaehlte Zaehlerstand
  tatsaechlich in der Reserve-Zone liegt — sonst waere die Zusicherung leer.
* **AC-13 Zaehler-Invariante** — Sperrzeit und Tageszaehler werden NIEMALS vor
  der erfolgreichen Zustellung gebucht. Gemessen an den echten Zustandsdateien
  auf Platte, in beiden Richtungen (scheiternde und gelingende Zustellung).
* **AC-15 Mandantentrennung** — zwei Nutzer mit DERSELBEN Preset-Kennung.

Mock-frei, kein Netz: echte Zustandsdateien, echte Services, DI-Naehte fuer
Radar und Versand.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.loader import save_location

from tests.helpers.nowcast_gate_fixtures import (
    SCOPE_COMPARE_RADAR, CountingFrameSource, clean_uid, compare_radar_service,
    LOCATION_ZONE, fresh_uid, location, quiet_window_elsewhere, quiet_window_now,
    radar_preset, read_daily_counter, read_throttle_state, record_throttle,
    reset_radar_cache, seed_daily_counter, settings_email_only,
    settings_no_channel_reachable, write_presets, write_user_tier,
)


def _counting_store(user_id: str):
    """Echter ``ThrottleStore`` (echte Datei, echte Sperrzeit-Semantik), der
    seine Sperrzeit-Abfragen mitzaehlt. Kein Mock: die Unterklasse delegiert
    jeden Aufruf an die Originalimplementierung."""
    from services.throttle_store import ThrottleStore

    class _CountingThrottleStore(ThrottleStore):
        def __init__(self, uid: str) -> None:
            super().__init__(uid)
            self.is_throttled_calls = 0

        def is_throttled(self, scope, key, cooldown_minutes, now):  # type: ignore[override]
            self.is_throttled_calls += 1
            return super().is_throttled(scope, key, cooldown_minutes, now)

    return _CountingThrottleStore(user_id)


def _setup_compare(uid: str, preset_id: str, *, quiet: bool = False) -> None:
    save_location(location("loc-gate", "Gattersdorf"), user_id=uid)
    quiet_from, quiet_to = quiet_window_now() if quiet else quiet_window_elsewhere()
    write_presets(uid, [radar_preset(
        preset_id, ["loc-gate"], user_id=uid, cooldown_minutes=120,
        quiet_from=quiet_from, quiet_to=quiet_to,
    )])


def _run_compare(uid: str, settings=None) -> tuple[int, list]:
    reset_radar_cache()
    mails: list = []
    sent = compare_radar_service(
        uid, settings or settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: mails.append((subject, body)),
    ).check_all_compare_presets()
    return sent, mails


# ═════════════════════════ AC-11: feste Reihenfolge ═════════════════════════


def test_ac11_ruhezeit_stoppt_vor_der_sperrzeit_pruefung():
    """AC-11: Treffen Ruhezeit UND Sperrzeit gleichzeitig zu, haelt der Ablauf
    an der Ruhezeit an — die Sperrzeit-Pruefung wird fuer diesen Aufruf gar
    nicht mehr erreicht (Aufrufzaehler bleibt bei 0).

    RED heute: ``services.alert_gate`` existiert nicht (ImportError)."""
    from services.alert_gate import check_nowcast_gate
    from services.alert_log import REASON_QUIET_HOURS

    uid, preset_id = fresh_uid("ac11-qh"), "cp-1467s3-ac11"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        store = _counting_store(uid)
        store.record(SCOPE_COMPARE_RADAR, preset_id,
                     datetime.now(timezone.utc) - timedelta(minutes=5))
        store.is_throttled_calls = 0
        quiet_from, quiet_to = quiet_window_now()

        ergebnis = check_nowcast_gate(
            user_id=uid, throttle_scope=SCOPE_COMPARE_RADAR, throttle_key=preset_id,
            cooldown_minutes=120, quiet_from=quiet_from, quiet_to=quiet_to,
            context_label=preset_id, now=datetime.now(timezone.utc),
            zone=LOCATION_ZONE, throttle_store=store,
        )

        assert ergebnis.allowed is False, (
            f"Aktive Ruhezeit muss den Nowcast sperren: {ergebnis!r}"
        )
        assert ergebnis.reason == REASON_QUIET_HOURS, (
            f"Der gemeldete Grund muss die ERSTE zutreffende Stufe sein "
            f"({REASON_QUIET_HOURS!r}), gemeldet wurde {ergebnis.reason!r}"
        )
        assert store.is_throttled_calls == 0, (
            f"Die Sperrzeit-Pruefung darf bei aktiver Ruhezeit gar nicht erst "
            f"laufen, wurde aber {store.is_throttled_calls}x gerufen"
        )
    finally:
        clean_uid(uid)


def test_ac11_sperrzeit_stoppt_vor_der_tages_obergrenze():
    """AC-11 (zweite Stufengrenze): Treffen Sperrzeit UND Tages-Obergrenze
    gleichzeitig zu, meldet der Baustein die Sperrzeit — er haelt an der
    ersten zutreffenden Stufe an, nicht an der letzten.

    RED heute: ``services.alert_gate`` existiert nicht (ImportError)."""
    from services.alert_gate import check_nowcast_gate
    from services.alert_log import REASON_COOLDOWN

    uid, preset_id = fresh_uid("ac11-cd"), "cp-1467s3-ac11b"
    clean_uid(uid)
    try:
        write_user_tier(uid, "free")
        seed_daily_counter(uid, 2)  # Tages-Obergrenze ebenfalls erreicht
        record_throttle(uid, SCOPE_COMPARE_RADAR, preset_id,
                        datetime.now(timezone.utc) - timedelta(minutes=5))
        quiet_from, quiet_to = quiet_window_elsewhere()

        ergebnis = check_nowcast_gate(
            user_id=uid, throttle_scope=SCOPE_COMPARE_RADAR, throttle_key=preset_id,
            cooldown_minutes=120, quiet_from=quiet_from, quiet_to=quiet_to,
            context_label=preset_id, now=datetime.now(timezone.utc),
            zone=LOCATION_ZONE,
        )

        assert ergebnis.allowed is False, f"Die Sperrzeit muss sperren: {ergebnis!r}"
        assert ergebnis.reason == REASON_COOLDOWN, (
            f"Erwartet {REASON_COOLDOWN!r} (erste zutreffende Stufe), gemeldet "
            f"wurde {ergebnis.reason!r}"
        )
    finally:
        clean_uid(uid)


def test_ac11_freie_bahn_wird_durchgelassen():
    """AC-11 (Gegenprobe): Ohne Ruhezeit, ohne Sperrzeit, mit freiem
    Tagesbudget laesst der Baustein durch und nennt keinen Grund. Ohne diese
    Haelfte waere ein Baustein, der ALLES sperrt, formal AC-konform — der
    gefaehrlichste Fehler dieser Scheibe.

    RED heute: ``services.alert_gate`` existiert nicht (ImportError)."""
    from services.alert_gate import check_nowcast_gate

    uid, preset_id = fresh_uid("ac11-frei"), "cp-1467s3-ac11c"
    clean_uid(uid)
    try:
        write_user_tier(uid, "free")
        quiet_from, quiet_to = quiet_window_elsewhere()

        ergebnis = check_nowcast_gate(
            user_id=uid, throttle_scope=SCOPE_COMPARE_RADAR, throttle_key=preset_id,
            cooldown_minutes=120, quiet_from=quiet_from, quiet_to=quiet_to,
            context_label=preset_id, now=datetime.now(timezone.utc),
            zone=LOCATION_ZONE,
        )

        assert ergebnis.allowed is True, (
            f"Ohne jede Sperre muss der Nowcast durchgelassen werden: {ergebnis!r}"
        )
        assert ergebnis.reason is None, (
            f"Ein durchgelassener Lauf darf keinen Sperrgrund nennen: "
            f"{ergebnis.reason!r}"
        )
    finally:
        clean_uid(uid)


# ══════════════════ AC-12: Vorrang-Schutz aus #1555 bleibt ══════════════════


def test_ac12_vergleichs_nowcast_prueft_gegen_das_volle_tagesbudget():
    """AC-12: Bei Limit 2 und Reserve 1 (#1555) ist nach EINEM verbrauchten
    Platz nur noch der Reserve-Platz frei. Der Vergleichs-Nowcast wird
    trotzdem zugestellt — er prueft, wie der Trip-Nowcast, gegen das VOLLE
    Limit (``reason="nowcast"``). Erst das erschoepfte volle Limit sperrt ihn.

    Der erste Block belegt, dass der gewaehlte Zaehlerstand wirklich in der
    Reserve-Zone liegt: mit ``reason="forecast_change"`` waere derselbe Stand
    bereits gesperrt. Ohne diesen Nachweis koennte der Test auch dann gruen
    sein, wenn die Reserve gar nicht griffe.

    RED heute: der zweite Block stellt zu — der Vergleichs-Nowcast kennt gar
    keine Tages-Obergrenze."""
    from services import alert_daily_limit

    reserve, voll = fresh_uid("ac12-res"), fresh_uid("ac12-voll")
    clean_uid(reserve)
    clean_uid(voll)
    try:
        jetzt = datetime.now(timezone.utc)

        write_user_tier(reserve, "free")     # Limit 2, Reserve 1
        seed_daily_counter(reserve, 1)
        assert alert_daily_limit.is_allowed(
            reserve, jetzt, LOCATION_ZONE, reason="forecast_change",
        ) is False, (
            "Aufbau-Nachweis: bei count=1 und Limit 2 muss die #1555-Reserve den "
            "Aenderungsalarm bereits sperren — sonst prueft dieser Test nichts"
        )
        assert alert_daily_limit.is_allowed(
            reserve, jetzt, LOCATION_ZONE, reason="nowcast",
        ) is True, (
            "Aufbau-Nachweis: derselbe Stand muss fuer den Nowcast frei sein"
        )
        _setup_compare(reserve, "cp-1467s3-ac12")
        sent_reserve, mails_reserve = _run_compare(reserve)
        assert (sent_reserve, len(mails_reserve)) == (1, 1), (
            f"Der Vergleichs-Nowcast muss den Reserve-Platz nutzen duerfen "
            f"(reason='nowcast' gegen das VOLLE Limit) — erhalten "
            f"sent={sent_reserve}, Mails={len(mails_reserve)}"
        )

        write_user_tier(voll, "free")
        seed_daily_counter(voll, 2)
        _setup_compare(voll, "cp-1467s3-ac12")  # dieselbe Kennung, anderer Nutzer
        sent_voll, mails_voll = _run_compare(voll)
        assert (sent_voll, mails_voll) == (0, []), (
            f"Bei erschoepftem VOLLEN Tagesbudget muss auch der Nowcast sperren — "
            f"erhalten sent={sent_voll}, Mails={mails_voll!r}"
        )
    finally:
        clean_uid(reserve)
        clean_uid(voll)


# ═════════════════ AC-13: Buchung erst NACH der Zustellung ══════════════════


def test_ac13_gescheiterte_zustellung_bucht_weder_sperrzeit_noch_tageszaehler():
    """AC-13: Ist kein Kanal erreichbar, bleiben Sperrzeit und Tageszaehler
    exakt unveraendert — und wenn die Zustellung gelingt, wachsen beide um
    genau eine Buchung.

    Beide Haelften gehoeren zusammen: die erste allein waere auch von einer
    Implementierung erfuellt, die NIE bucht (dann wuerde die Sperrzeit nie
    wirken); die zweite allein waere auch von einer erfuellt, die IMMER bucht
    (dann zaehlen fehlgeschlagene Versuche als verbraucht).

    RED heute: in der zweiten Haelfte bleibt der Tageszaehler bei 0 und der
    Sperrzeit-Eintrag landet in der presetseigenen Altdatei."""
    gescheitert, gelungen = fresh_uid("ac13-fail"), fresh_uid("ac13-ok")
    clean_uid(gescheitert)
    clean_uid(gelungen)
    try:
        write_user_tier(gescheitert, "free")
        _setup_compare(gescheitert, "cp-1467s3-ac13")
        zaehler_vorher = read_daily_counter(gescheitert)
        speicher_vorher = read_throttle_state(gescheitert)

        sent, mails = _run_compare(gescheitert, settings_no_channel_reachable())

        assert (sent, mails) == (0, []), (
            f"Ohne erreichbaren Kanal darf nichts als versendet gelten — "
            f"erhalten sent={sent}, Mails={mails!r}"
        )
        assert read_daily_counter(gescheitert) == zaehler_vorher, (
            f"Der Tageszaehler wurde trotz gescheiterter Zustellung erhoeht: "
            f"{zaehler_vorher} -> {read_daily_counter(gescheitert)}"
        )
        assert read_throttle_state(gescheitert) == speicher_vorher, (
            f"Die Sperrzeit wurde trotz gescheiterter Zustellung gebucht: "
            f"{speicher_vorher!r} -> {read_throttle_state(gescheitert)!r}"
        )

        write_user_tier(gelungen, "free")
        _setup_compare(gelungen, "cp-1467s3-ac13")
        sent_ok, mails_ok = _run_compare(gelungen)

        assert (sent_ok, len(mails_ok)) == (1, 1), (
            f"Voraussetzung der zweiten Haelfte: die Zustellung muss gelingen — "
            f"erhalten sent={sent_ok}, Mails={len(mails_ok)}"
        )
        assert read_daily_counter(gelungen) == 1, (
            f"Nach erfolgreicher Zustellung muss der Tageszaehler auf 1 stehen, "
            f"steht auf {read_daily_counter(gelungen)}"
        )
        assert "cp-1467s3-ac13" in read_throttle_state(gelungen).get(SCOPE_COMPARE_RADAR, {}), (
            f"Nach erfolgreicher Zustellung muss die Sperrzeit im geteilten "
            f"Speicher stehen: {read_throttle_state(gelungen)!r}"
        )
    finally:
        clean_uid(gescheitert)
        clean_uid(gelungen)


# ══════════════════════ AC-15: Mandantentrennung ════════════════════════════


_GETEILTE_KENNUNG = "cp-1467s3-ac15"


def test_ac15_sperrzeit_wirkt_nicht_ueber_die_nutzergrenze():
    """AC-15: Zwei Nutzer mit DERSELBEN Preset-Kennung. Die laufende Sperrzeit
    des einen darf den anderen nicht sperren.

    RED heute: die Sperrzeit von A wirkt aus dessen eigener Datei, der
    geteilte Speicher-Eintrag von A bleibt wirkungslos — A stellt zu."""
    a, b = fresh_uid("ac15a-a"), fresh_uid("ac15a-b")
    clean_uid(a)
    clean_uid(b)
    try:
        for uid in (a, b):
            write_user_tier(uid, "premium")  # Tageslimit aus dem Weg
            _setup_compare(uid, _GETEILTE_KENNUNG)
        record_throttle(a, SCOPE_COMPARE_RADAR, _GETEILTE_KENNUNG,
                        datetime.now(timezone.utc) - timedelta(minutes=5))

        sent_a, mails_a = _run_compare(a)
        sent_b, mails_b = _run_compare(b)

        assert (sent_a, mails_a) == (0, []), (
            f"Die Sperrzeit von Nutzer A muss dessen eigenen Alarm sperren — "
            f"erhalten sent={sent_a}, Mails={mails_a!r}"
        )
        assert (sent_b, len(mails_b)) == (1, 1), (
            f"Die Sperrzeit von Nutzer A darf Nutzer B — gleiche Preset-Kennung, "
            f"anderes Konto — NICHT sperren: sent={sent_b}, Mails={len(mails_b)}"
        )
        assert _GETEILTE_KENNUNG not in read_throttle_state(a).get("radar", {}), (
            "Die Vergleichs-Sperrzeit darf nicht im Trip-Scope liegen"
        )
    finally:
        clean_uid(a)
        clean_uid(b)


def test_ac15_tageslimit_wirkt_nicht_ueber_die_nutzergrenze():
    """AC-15: Das erschoepfte Tagesbudget des einen Nutzers darf den anderen
    nicht sperren — beide fuehren ihren Zaehler unter ``data/users/<id>/``.

    RED heute: A stellt trotz erschoepftem Tagesbudget zu (keine Pruefung)."""
    a, b = fresh_uid("ac15b-a"), fresh_uid("ac15b-b")
    clean_uid(a)
    clean_uid(b)
    try:
        for uid in (a, b):
            write_user_tier(uid, "free")
            _setup_compare(uid, _GETEILTE_KENNUNG)
        seed_daily_counter(a, 2)
        seed_daily_counter(b, 0)

        sent_a, mails_a = _run_compare(a)
        sent_b, mails_b = _run_compare(b)

        assert (sent_a, mails_a) == (0, []), (
            f"Nutzer A hat sein Tagesbudget aufgebraucht — kein Alarm erwartet, "
            f"erhalten sent={sent_a}, Mails={mails_a!r}"
        )
        assert (sent_b, len(mails_b)) == (1, 1), (
            f"Das Tagesbudget von A darf B nicht sperren: sent={sent_b}, "
            f"Mails={len(mails_b)}"
        )
        assert read_daily_counter(a) == 2 and read_daily_counter(b) == 1, (
            f"Zaehlerstaende nach dem Lauf: A={read_daily_counter(a)} (erwartet 2, "
            f"unveraendert), B={read_daily_counter(b)} (erwartet 1)"
        )
    finally:
        clean_uid(a)
        clean_uid(b)


# ═══════════════════════════════════════════════════════════════════════════
# Issue #1467 Scheibe S4b-1 — quellenuebergreifende Ereignis-Identitaet
# SPEC: docs/specs/modules/rework_1467_s4b_entdopplung.md
#
# ``check_event_identity_gate``/``record_event_identity``/
# ``resolve_hazard_class`` existieren heute nicht -- RED-Grund fuer JEDEN
# Test unten ist ein ``ImportError``, solange die Bausteine fehlen. Sobald
# sie existieren, pruefen die Tests das tatsaechliche Verhalten (echte
# ``AlertStateService``-Dateien auf Platte, kein Mock).
#
# Angenommene Signaturen (von diesen Tests VORGEGEBEN, nicht im Quellcode
# gesehen -- die Implementierung muss sie erfuellen):
#
#     resolve_hazard_class(*, is_convective=None, hazard=None) -> str | None
#     check_event_identity_gate(
#         *, user_id, entity_id, hazard_class, segment_ids, severity, now,
#         point_at=None, window_start=None, window_end=None,
#         cooldown_minutes=None,
#     ) -> GateResult
#     record_event_identity(
#         *, user_id, entity_id, hazard_class, segment_ids, severity, now,
#         point_at=None, window_start=None, window_end=None,
#     ) -> None
# ═══════════════════════════════════════════════════════════════════════════


# ─────────────── Gefahrenart-Kanon (T2) — AC-4 + AC-4b ──────────────────────


def test_ac4_resolve_hazard_class_kennt_nowcast_immer_als_wet():
    """AC-4b (Baustein): ``resolve_hazard_class(is_convective=...)`` liefert
    in BEIDEN Faellen (True/False) dieselbe Klasse ``HAZARD_CLASS_WET`` — ein
    Nowcast ist immer Niederschlag, ``is_convective`` unterscheidet nur die
    Erscheinungsform derselben Zelle (PO-Entscheid 2026-08-16, s. Spec
    Implementation Details T2).

    RED heute: ImportError."""
    from services.alert_gate import HAZARD_CLASS_WET, resolve_hazard_class

    assert resolve_hazard_class(is_convective=True) == HAZARD_CLASS_WET
    assert resolve_hazard_class(is_convective=False) == HAZARD_CLASS_WET


@pytest.mark.parametrize("hazard", ["thunderstorm", "flood", "rain"])
def test_ac4b_amtliche_wet_hazards_erhalten_dieselbe_klasse(hazard):
    """AC-4b: alle drei amtlichen ``wet``-Hazards (``thunderstorm``, ``flood``,
    ``rain``) muessen auf dieselbe Klasse abbilden wie der Nowcast — sonst
    liefe die quellenuebergreifende Entdopplung fuer diese Paare ins Leere."""
    from services.alert_gate import HAZARD_CLASS_WET, resolve_hazard_class

    assert resolve_hazard_class(hazard=hazard) == HAZARD_CLASS_WET


@pytest.mark.parametrize("hazard", [
    "wind_gust", "snow", "black_ice", "extreme_heat",
    "extreme_cold", "wildfire_risk", "access_ban",
])
def test_ac4_nicht_wet_hazards_bekommen_keine_klasse(hazard):
    """AC-4: die sieben Hazards ausserhalb des ``wet``-Kanons liefern ``None``
    — ``resolve_hazard_class`` kennt keine andere Klasse, die Ereignis-
    Identitaet greift fuer diese Gefahrenarten grundsaetzlich nie."""
    from services.alert_gate import resolve_hazard_class

    assert resolve_hazard_class(hazard=hazard) is None


def test_ac4_check_event_identity_gate_laesst_hazard_class_none_immer_durch():
    """AC-4 (integriert): ``hazard_class=None`` lässt IMMER durch, egal was im
    Register steht — ``resolve_hazard_class`` hat vorher schon entschieden,
    dass es fuer diese Gefahrenart keinen Kandidaten geben kann."""
    from services.alert_gate import check_event_identity_gate

    uid = fresh_uid("s4b-ac4")
    clean_uid(uid)
    try:
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac4", hazard_class=None,
            segment_ids=["1"], severity="HIGH",
            now=datetime.now(timezone.utc),
        )
        assert ergebnis.allowed is True
        assert ergebnis.reason is None
    finally:
        clean_uid(uid)


@pytest.mark.parametrize("is_convective,hazard", [
    (True, "thunderstorm"), (True, "rain"),
    (False, "thunderstorm"), (False, "rain"),
])
def test_ac4b_kreuzprobe_konvektiv_und_niederschlag_entdoppeln_sich_gegenseitig(
    is_convective, hazard,
):
    """AC-4b (Kreuzprobe, Pflicht laut Spec) + Mutations-Gegenprobe.

    GIVEN einen registrierten Nowcast-Eintrag mit ``is_convective=<param>``
    WHEN  eine amtliche Warnung mit ``hazard=<param>`` desselben Orts und
          ueberlappenden Zeitfensters eintrifft
    THEN  wird sie unterdrueckt (``allowed=False``) — in ALLEN vier
          Kombinationen. Die Radar-Einstufung konvektiv/nicht-konvektiv
          trennt KEINE Ereignisse (PO-Entscheid 2026-08-16).

    Mutations-Gegenprobe (Pflicht laut AC-4b): wuerde ``resolve_hazard_class``
    wieder auf zwei Klassen (``"convective"``/``"precipitation"``﻿) aufgespalten,
    lieferten ``is_convective=False``+``hazard="thunderstorm"`` bzw.
    ``is_convective=True``+``hazard="rain"`` UNTERSCHIEDLICHE Klassen — kein
    Registereintrag matcht mehr, die amtliche Warnung ginge faelschlich durch
    (``allowed=True``), und genau diese zwei der vier Parametrisierungen
    werden dann rot.

    RED heute: ImportError."""
    from services.alert_gate import (
        check_event_identity_gate, record_event_identity, resolve_hazard_class,
    )

    uid = fresh_uid("s4b-ac4b")
    clean_uid(uid)
    try:
        onset = datetime.now(timezone.utc) - timedelta(minutes=8, seconds=12)
        record_event_identity(
            user_id=uid, entity_id="trip-ac4b",
            hazard_class=resolve_hazard_class(is_convective=is_convective),
            segment_ids=["7"], severity="HIGH", point_at=onset, now=onset,
        )

        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac4b",
            hazard_class=resolve_hazard_class(hazard=hazard),
            segment_ids=["7"], severity="HIGH",
            window_start=onset - timedelta(minutes=10),
            window_end=onset + timedelta(minutes=45),
            now=datetime.now(timezone.utc),
        )

        assert ergebnis.allowed is False, (
            f"is_convective={is_convective} gegen hazard={hazard!r} muss "
            f"entdoppeln: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ─────────────────── Baustein-Struktur — AC-1 (Teil) / AC-2 / AC-3 ──────────


def test_ac1_check_event_identity_gate_liefert_eine_echte_gateresult_instanz():
    """AC-1 (Typ-Nachweis): der Rueckgabewert ist eine echte ``GateResult``-
    Instanz, nicht nur ein Objekt mit gleichnamigen Attributen. Der zweite
    Teil von AC-1 (beide Trip-Pfade rufen DENSELBEN Baustein, per
    Aufrufzaehler) steht end-to-end in
    ``tests/tdd/test_issue_1088_official_alert_triggers.py`` — dort sind
    echte Trip-/Versand-Fixtures ohnehin vorhanden, ein zweiter Nachbau hier
    waere doppelte Testinfrastruktur ohne zusaetzliche Aussagekraft."""
    from services.alert_gate import GateResult, check_event_identity_gate

    uid = fresh_uid("s4b-ac1")
    clean_uid(uid)
    try:
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac1", hazard_class="wet",
            segment_ids=["1"], severity="HIGH",
            now=datetime.now(timezone.utc),
        )
        assert isinstance(ergebnis, GateResult), (
            f"Erwartet eine echte GateResult-Instanz, erhalten: {type(ergebnis)!r}"
        )
    finally:
        clean_uid(uid)


def test_ac2_record_event_identity_legt_genau_einen_registereintrag_an():
    """AC-2: eine erfolgreich zugestellte Meldung legt GENAU EINEN
    Registereintrag unter dem Praefix ``event_identity:<hazard_class>:`` an,
    mit Gefahrenklasse, Ortskennungen, Zeitbezug, Dringlichkeit und
    Zeitpunkt."""
    from services.alert_gate import record_event_identity
    from services.alert_state import EVENT_IDENTITY_KEY_PREFIX, AlertStateService

    uid = fresh_uid("s4b-ac2")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac2", hazard_class="wet",
            segment_ids=["3", "4"], severity="HIGH", point_at=now, now=now,
        )

        state = AlertStateService(user_id=uid).load("trip-ac2")
        neue = {k: v for k, v in state.items() if k.startswith(EVENT_IDENTITY_KEY_PREFIX)}
        assert len(neue) == 1, (
            f"Erwartet genau EINEN neuen event_identity:-Schluessel, "
            f"gefunden {len(neue)}: {sorted(state)!r}"
        )
        (eintrag,) = neue.values()
        assert eintrag["hazard_class"] == "wet"
        assert set(eintrag["segment_ids"]) == {"3", "4"}
        assert eintrag["severity"] == "HIGH"
        assert "reported_at" in eintrag
    finally:
        clean_uid(uid)


def test_ac3_check_event_identity_gate_ist_rein_lesend_kein_registereintrag():
    """AC-3 (Baustein-Ebene, F001-Symmetrie): ein reiner Freigabe-Check darf
    NIE selbst einen Registereintrag anlegen — Registrierung ist
    ausschliesslich Sache von ``record_event_identity()``, aufgerufen NACH
    erfolgreicher Zustellung (analog ``record_nowcast_sent``). Der
    End-to-End-Nachweis fuer eine technisch gescheiterte Zustellung liegt
    im AC-11/AC-17-Umfeld von ``test_issue_1088_official_alert_triggers.py``."""
    from services.alert_gate import check_event_identity_gate
    from services.alert_state import AlertStateService

    uid = fresh_uid("s4b-ac3")
    clean_uid(uid)
    try:
        vorher = AlertStateService(user_id=uid).load("trip-ac3")
        check_event_identity_gate(
            user_id=uid, entity_id="trip-ac3", hazard_class="wet",
            segment_ids=["1"], severity="HIGH",
            point_at=datetime.now(timezone.utc), now=datetime.now(timezone.utc),
        )
        nachher = AlertStateService(user_id=uid).load("trip-ac3")
        assert vorher == nachher == {}, (
            f"check_event_identity_gate() darf selbst NIE einen "
            f"Registereintrag anlegen: vorher={vorher!r} nachher={nachher!r}"
        )
    finally:
        clean_uid(uid)


def test_ac13_aenderungsalarm_guard_eintraege_erzeugen_keinen_event_identity_key():
    """AC-13 (T7-Ergaenzung): ein Aenderungsalarm-Guard-Eintrag
    (``precip:<segment>``/``thunder_level_max:<segment>``, geschrieben vom
    Δ-Pfad) erzeugt KEINEN ``event_identity:``-Registereintrag — der neue
    Baustein ist fuer diese Paarung strukturell nicht zustaendig (T7:
    Nowcast↔Δ bleibt allein Sache des bestehenden Doppel-Alert-Guards,
    ``trip_alert.py:1081-1099``). Der Bestandsschutz des Guards selbst bleibt
    unveraendert in
    ``tests/tdd/test_issue_818_radar_briefing_integration.py::
    test_ac4_double_alert_guard_suppresses_radar_when_forecast_recent``
    (hier NICHT erneut nachgebaut)."""
    from services.alert_state import EVENT_IDENTITY_KEY_PREFIX, AlertStateService

    uid = fresh_uid("s4b-ac13")
    clean_uid(uid)
    try:
        AlertStateService(user_id=uid).save("trip-ac13", {
            "precip:1": {
                "last_reported_value": 5.0,
                "reported_at": datetime.now(timezone.utc).isoformat(),
            },
        })
        state = AlertStateService(user_id=uid).load("trip-ac13")
        event_keys = [k for k in state if k.startswith(EVENT_IDENTITY_KEY_PREFIX)]
        assert event_keys == [], (
            f"Ein Aenderungsalarm-Guard-Eintrag darf keinen event_identity:-"
            f"Schluessel erzeugen (andere Paarung, T7): {event_keys!r}"
        )
    finally:
        clean_uid(uid)


# ───────────────────────── Ortsbezug (T3) — AC-5 ─────────────────────────────


def test_ac5_disjunkte_segment_mengen_erzeugen_kein_match():
    """AC-5: gleiche Gefahrenklasse, ueberlappendes Zeitfenster, aber
    DISJUNKTE Segment-Mengen -> kein Match, die neue Meldung wird
    zugestellt."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac5a")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac5a", hazard_class="wet",
            segment_ids=["1", "2"], severity="HIGH", point_at=now, now=now,
        )
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac5a", hazard_class="wet",
            segment_ids=["9"], severity="HIGH",
            window_start=now - timedelta(minutes=10),
            window_end=now + timedelta(minutes=30),
            now=now + timedelta(minutes=5),
        )
        assert ergebnis.allowed is True, (
            f"Disjunkte Segment-Mengen duerfen NICHT als Match zaehlen: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


def test_ac5_leere_segment_kennung_erzeugt_niemals_ein_match():
    """AC-5 (Bruchstelle): eine leere/fehlende Segment-Kennung auf EINER Seite
    darf niemals ein Match erzeugen — sonst passte "kein Ort bekannt" auf
    "jeden Ort"."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac5b")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac5b", hazard_class="wet",
            segment_ids=[], severity="HIGH", point_at=now, now=now,
        )
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac5b", hazard_class="wet",
            segment_ids=["3"], severity="HIGH",
            window_start=now - timedelta(minutes=10),
            window_end=now + timedelta(minutes=30),
            now=now + timedelta(minutes=5),
        )
        assert ergebnis.allowed is True, (
            f"Ein Registereintrag ohne Segment-Kennung darf kein Match "
            f"erzeugen: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ────────────────────── Zeitfenster (T4) — AC-6 / AC-7 ───────────────────────


def test_ac6_kernfall_nowcast_gefolgt_von_amtlicher_warnung_8_2_min_spaeter():
    """AC-6: Reproduktion des gemessenen Falls ``5f534011`` (2026-08-11,
    14:22 UTC Nowcast, +8,2 Min amtliche Warnung, s. Spec Purpose).

    GIVEN ein registrierter Nowcast-Eintrag (Klasse 'wet', Segment '3', Onset
          14:22 UTC)
    WHEN  8,2 Min spaeter eine amtliche Warnung derselben Klasse/desselben
          Segments eintrifft, deren Fenster den Onset-Punkt (mit 60-Min-
          Puffer) ueberlappt UND das abgedeckte Ende NICHT wesentlich
          ueberschreitet (keine V1-Ausnahme) UND keine hoehere Dringlichkeit
          traegt (keine V2-Eskalation)
    THEN  wird sie unterdrueckt."""
    from services.alert_gate import check_event_identity_gate, record_event_identity
    from services.alert_log import REASON_EVENT_DUPLICATE

    uid = fresh_uid("s4b-ac6")
    clean_uid(uid)
    try:
        onset = datetime(2026, 8, 11, 14, 22, 0, tzinfo=timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac6", hazard_class="wet",
            segment_ids=["3"], severity="HIGH", point_at=onset, now=onset,
        )
        amtlich_zeit = onset + timedelta(minutes=8, seconds=12)
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac6", hazard_class="wet",
            segment_ids=["3"], severity="HIGH",
            window_start=onset - timedelta(minutes=10),
            window_end=onset + timedelta(minutes=45),
            now=amtlich_zeit,
        )
        assert ergebnis.allowed is False
        assert ergebnis.reason == REASON_EVENT_DUPLICATE, (
            f"Erwartet {REASON_EVENT_DUPLICATE!r}, erhalten {ergebnis.reason!r}"
        )
    finally:
        clean_uid(uid)


def test_ac7_neue_meldung_ohne_zeitbezug_erzeugt_kein_match():
    """AC-7 (fail-soft, erste Seite): fehlt der neuen Meldung jeder
    vergleichbare Zeitbezug (weder ``point_at`` noch ``window_start``/
    ``window_end``), entsteht kein Match — die Meldung wird zugestellt."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac7a")
    clean_uid(uid)
    try:
        onset = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac7a", hazard_class="wet",
            segment_ids=["1"], severity="HIGH", point_at=onset, now=onset,
        )
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac7a", hazard_class="wet",
            segment_ids=["1"], severity="HIGH", now=onset + timedelta(minutes=5),
        )
        assert ergebnis.allowed is True, (
            f"Ohne vergleichbaren Zeitbezug darf keine Unterdrueckung "
            f"entstehen: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


def test_ac7_unparsbares_zeitfeld_im_registereintrag_erzeugt_kein_match():
    """AC-7 (fail-soft, zweite Seite): ein Registereintrag mit unparsbarem
    ``point_at`` darf nicht zum Absturz fuehren UND erzeugt fail-soft kein
    Match — die neue Meldung wird zugestellt."""
    from services.alert_gate import check_event_identity_gate
    from services.alert_state import AlertStateService

    uid = fresh_uid("s4b-ac7b")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        AlertStateService(user_id=uid).save("trip-ac7b", {
            "event_identity:wet:1:kaputt": {
                "hazard_class": "wet", "segment_ids": ["1"], "severity": "HIGH",
                "point_at": "nicht-geparst-2026-13-99", "window_start": None,
                "window_end": None, "reported_at": now.isoformat(),
            },
        })
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac7b", hazard_class="wet",
            segment_ids=["1"], severity="HIGH", point_at=now, now=now,
        )
        assert ergebnis.allowed is True, (
            f"Ein unparsbares Zeitfeld im Register darf kein Match erzeugen "
            f"(fail-soft): {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ──────────── V1 — zeitliche Prioritaet + Abdeckungs-Vorbehalt — AC-8/AC-9 ───


def test_ac8_zweite_meldung_vollstaendig_innerhalb_des_abgedeckten_fensters():
    """AC-8: keine Eskalation, keine wesentliche Erweiterung -> die zweite
    Meldung wird unterdrueckt (Intervall-gegen-Intervall-Fall, isoliert
    getestet, s. Spec T4)."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac8")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac8", hazard_class="wet",
            segment_ids=["2"], severity="MODERATE",
            window_start=now, window_end=now + timedelta(hours=2), now=now,
        )
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac8", hazard_class="wet",
            segment_ids=["2"], severity="MODERATE",
            window_start=now + timedelta(minutes=30),
            window_end=now + timedelta(hours=1),
            now=now + timedelta(minutes=10),
        )
        assert ergebnis.allowed is False, (
            f"Ein vollstaendig abgedecktes Fenster ohne Eskalation muss "
            f"unterdrueckt werden: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


def test_ac9_valid_to_reicht_wesentlich_ueber_das_abgedeckte_ende_hinaus():
    """AC-9 (V1-Ausnahme) + Mutations-Gegenprobe (PFLICHT laut Spec).

    GIVEN ein registrierter Nowcast-Eintrag (abgedeckt bis Onset+60 Min)
    WHEN  eine amtliche Warnung derselben Klasse/desselben Orts eintrifft,
          deren ``valid_to`` MEHR ALS 60 Min ueber das abgedeckte Ende
          hinausreicht — OHNE hoehere Dringlichkeit
    THEN  wird sie zugestellt (neue Information).

    Mutations-Gegenprobe: wird ``NOWCAST_HORIZON_MIN`` durch eine deutlich
    groessere Zahl (z. B. 600) ersetzt, deckt das verfaelschte Fenster
    ``covered_until + 600min`` das hier verwendete ``valid_to`` (nur +90 Min
    ueber ``covered_until``) weiterhin ab — die V1-Ausnahme greift dann
    NICHT mehr, ``allowed`` wird ``False`` statt ``True``, und dieser Test
    wird rot."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac9")
    clean_uid(uid)
    try:
        onset = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac9", hazard_class="wet",
            segment_ids=["4"], severity="MODERATE", point_at=onset, now=onset,
        )
        # covered_until = onset + NOWCAST_HORIZON_MIN (60 Min)
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac9", hazard_class="wet",
            segment_ids=["4"], severity="MODERATE",  # keine hoehere Dringlichkeit
            window_start=onset,
            window_end=onset + timedelta(minutes=150),  # 90 Min ueber covered_until
            now=onset + timedelta(minutes=5),
        )
        assert ergebnis.allowed is True, (
            f"Ein Fenster, das wesentlich ueber das abgedeckte Ende "
            f"hinausreicht, muss durchkommen (V1-Ausnahme): {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ─────────────── V2 — Verschaerfung durchbricht immer — AC-10 ───────────────


def test_ac10_hoehere_dringlichkeit_durchbricht_auch_ohne_zeitliche_erweiterung():
    """AC-10 (V2-Eskalation) + Mutations-Gegenprobe (PFLICHT laut Spec).

    GIVEN eine registrierte Meldung mit Dringlichkeit MODERATE
    WHEN  eine zweite Meldung derselben Klasse/desselben Orts mit HOEHERER
          Dringlichkeit (HIGH) eintrifft, deren Zeitfenster VOLLSTAENDIG
          innerhalb des abgedeckten Fensters liegt (die V1-Ausnahme greift
          hier ausdruecklich NICHT — nur die Eskalation)
    THEN  wird sie zugestellt.

    Mutations-Gegenprobe: wird der Eskalations-Zweig entfernt oder HINTER
    die V1-Ausnahme verschoben, prueft die Funktion zuerst "wesentlich mehr
    abgedeckt?" — das Zeitfenster liegt hier bewusst VOLLSTAENDIG innerhalb
    des abgedeckten Fensters, die V1-Ausnahme greift also nicht, und ohne den
    strukturell ERSTEN Eskalations-Zweig bliebe die Warnung faelschlich
    unterdrueckt (``allowed=False``). Dieser Test wird dann rot — das ist die
    Absicherung gegen die gefaehrlichste Fehlerrichtung "Alarm bleibt aus"
    bei einer echten Verschaerfung."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    uid = fresh_uid("s4b-ac10")
    clean_uid(uid)
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-ac10", hazard_class="wet",
            segment_ids=["5"], severity="MODERATE",
            window_start=now, window_end=now + timedelta(hours=3), now=now,
        )
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac10", hazard_class="wet",
            segment_ids=["5"], severity="HIGH",  # Eskalation
            window_start=now + timedelta(minutes=30),
            window_end=now + timedelta(hours=1),  # vollstaendig innerhalb
            now=now + timedelta(minutes=10),
        )
        assert ergebnis.allowed is True, (
            f"Eine echte Verschaerfung muss IMMER durchkommen, auch ohne "
            f"zeitliche Erweiterung: {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ───────────────────────── Mandantentrennung — AC-18 ────────────────────────


def test_ac18_registereintrag_von_nutzer_a_wirkt_nicht_auf_nutzer_b():
    """AC-18: zwei verschiedene Nutzer, gleiche Trip-Kennung, unabhaengig
    gefuehrte Register — Nutzer A registriert einen Nowcast, Nutzer B erhaelt
    seine amtliche Warnung trotzdem (kein Rueckfall auf ``"default"``)."""
    from services.alert_gate import check_event_identity_gate, record_event_identity

    a, b = fresh_uid("s4b-ac18-a"), fresh_uid("s4b-ac18-b")
    clean_uid(a)
    clean_uid(b)
    try:
        onset = datetime.now(timezone.utc)
        record_event_identity(
            user_id=a, entity_id="trip-geteilt", hazard_class="wet",
            segment_ids=["9"], severity="HIGH", point_at=onset, now=onset,
        )
        ergebnis_b = check_event_identity_gate(
            user_id=b, entity_id="trip-geteilt", hazard_class="wet",
            segment_ids=["9"], severity="HIGH",
            window_start=onset - timedelta(minutes=10),
            window_end=onset + timedelta(minutes=30),
            now=onset + timedelta(minutes=5),
        )
        assert ergebnis_b.allowed is True, (
            f"Nutzer B (user_id={b!r}) darf durch den Registereintrag von "
            f"Nutzer A (user_id={a!r}) nicht beeinflusst werden: {ergebnis_b!r}"
        )
    finally:
        clean_uid(a)
        clean_uid(b)


# ─────────────────── Bestandsdaten / fail-soft — AC-19 ──────────────────────


def test_ac19_registereintrag_mit_fehlendem_severity_feld_wird_wie_kein_match_behandelt():
    """AC-19: ein Registereintrag ohne ``severity`` (kaputtes/altes/kuenftiges
    Schema) darf nicht zum Absturz fuehren und zaehlt fail-soft NICHT als
    Match — die neue Meldung wird zugestellt."""
    from services.alert_gate import check_event_identity_gate
    from services.alert_state import AlertStateService

    uid = fresh_uid("s4b-ac19")
    clean_uid(uid)
    try:
        onset = datetime.now(timezone.utc)
        AlertStateService(user_id=uid).save("trip-ac19", {
            f"event_identity:wet:6:{onset.isoformat()}": {
                "hazard_class": "wet", "segment_ids": ["6"],
                # 'severity' fehlt bewusst — kaputtes/altes Format
                "point_at": onset.isoformat(), "window_start": None,
                "window_end": None, "reported_at": onset.isoformat(),
            },
        })
        ergebnis = check_event_identity_gate(
            user_id=uid, entity_id="trip-ac19", hazard_class="wet",
            segment_ids=["6"], severity="HIGH",
            point_at=onset + timedelta(minutes=5), now=onset + timedelta(minutes=5),
        )
        assert ergebnis.allowed is True, (
            f"Ein kaputter Registereintrag darf nicht als Match zaehlen "
            f"(fail-soft, kein Absturz): {ergebnis!r}"
        )
    finally:
        clean_uid(uid)


# ─────────────────────── Regression zu S4a — AC-20 ───────────────────────────


def test_ac20_check_official_alert_gate_signatur_bleibt_ohne_cooldown_parameter():
    """AC-20 (Regression zu S4a, HEUTE SCHON GRUEN — kein RED-Nachweis): die
    Funktionssignatur von ``check_official_alert_gate`` bleibt durch S4b-1
    UNVERAENDERT — kein Cooldown-/Sperrzeit-Parameter wandert nachtraeglich
    hinein. Die neue Ereignis-Identitaet-Pruefung ist ein EIGENER,
    nachgelagerter Aufruf, keine Erweiterung des Gates selbst."""
    import inspect

    from services.alert_gate import check_official_alert_gate

    params = set(inspect.signature(check_official_alert_gate).parameters)
    verbotene = {"cooldown_minutes", "cooldown", "throttle_scope", "throttle_key"}
    getroffen = params & verbotene
    assert not getroffen, (
        f"check_official_alert_gate hat einen Cooldown-aehnlichen Parameter "
        f"bekommen: {getroffen!r} (voller Parametersatz: {sorted(params)!r})"
    )


# ───────────────────────── Dokumentation — AC-21 ─────────────────────────────


def test_ac21_adr_0021_traegt_einen_datierten_s4b_nachtrag():
    """AC-21. ``# doc-compliance-test`` (Ausnahme von der
    Dateiinhalt-Regel, CLAUDE.md). GIVEN den bestehenden ADR-0021-Nachtrag
    aus S4a (#1467), WHEN diese Scheibe abgeschlossen ist, THEN traegt
    ADR-0021 einen weiteren, datierten Nachtrag mit Bezug auf '#1467' UND
    'S4b', der die neue quellenuebergreifende Ereignis-Identitaet-Pruefung
    festhaelt, ohne die S4a-Aussage zur Unterdrueckungs-Protokollierung zu
    widerrufen.

    RED heute: der Nachtrag fehlt noch."""
    from pathlib import Path

    adr_path = (
        Path(__file__).resolve().parents[2]
        / "docs" / "adr" / "0021-shared-deviation-alert-engine.md"
    )
    text = adr_path.read_text(encoding="utf-8")

    assert "S4b" in text, (
        f"ADR-0021 muss einen Nachtrag mit Bezug auf 'S4b' tragen: {adr_path}"
    )
    assert "#1467" in text, (
        f"ADR-0021 muss den Nachtrag auf '#1467' beziehen: {adr_path}"
    )
    # Der neue Nachtrag muss NACH dem S4a-Nachtrag stehen (Reihenfolge =
    # Chronologie der Nachtraege in diesem ADR).
    s4a_pos = text.find("Issue #1467 S4a")
    s4b_pos = text.find("Issue #1467 S4b")
    assert s4a_pos != -1, "Der bestehende S4a-Nachtrag darf nicht verschwinden"
    assert s4b_pos != -1 and s4b_pos > s4a_pos, (
        f"Der neue S4b-Nachtrag muss NACH dem S4a-Nachtrag stehen "
        f"(s4a_pos={s4a_pos}, s4b_pos={s4b_pos})"
    )
