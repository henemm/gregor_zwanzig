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
