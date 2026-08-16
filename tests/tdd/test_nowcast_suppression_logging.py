"""TDD RED + Invarianten-Waechter — Unterdrueckte Nowcast-Alarme werden
protokolliert (Issue #1467 S3, AC-6 bis AC-10).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md — Aenderung (d)

Die drei Konstanten ``REASON_QUIET_HOURS``/``REASON_COOLDOWN``/
``REASON_DAILY_LIMIT`` (``alert_log.py:47-49``) sind seit #1459 dokumentiert,
aber repo-weit von KEINEM Aufrufer gesetzt (gemessen 2026-08-08). Diese
Scheibe schaltet sie fuer die beiden Nowcast-Pfade scharf: wird ein
Nowcast-Lauf vom Freigabe-Baustein abgewiesen, entsteht dafuer GENAU EIN
Protokoll-Eintrag mit dem Grund der sperrenden Stufe — in der Liste
``not_delivered``, die Go nie liest (D4: Cockpit-Kachel und Archiv-Statistik
bleiben zahlgleich).

Zwei Sorten Test:

* AC-6/AC-7/AC-8 (Ortsvergleich) und AC-10 (Trip) sind ROT — heute wird gar
  nichts protokolliert.
* AC-9 ist ein Invarianten-Waechter und HEUTE GRUEN: der Geltungsbereich
  bleibt strikt auf die beiden Nowcast-Pfade begrenzt. Aenderungsalarm und
  amtliche Warnung bekommen KEINEN der drei Gruende — auch nicht als
  Nebenwirkung einer Protokollierung, die im geteilten Ruhezeit-/Tageslimit-
  Baustein statt im Nowcast-Pfad sitzt.

Mock-frei: echte Presets/Trips/Orte auf Platte, echte Services, echtes
``alert_log.json``; DI-Naehte fuer Radar/Wetter/amtliche Quelle/Versand.
Kein Netz.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import save_location

from tests.helpers.alert_log_fixtures import gust_alert_trip, weather
from tests.helpers.nowcast_gate_fixtures import (
    LAT, LON, SCOPE_COMPARE_RADAR, SCOPE_TRIP_RADAR, CountingFrameSource,
    clean_uid, compare_radar_service, entries_for, fresh_uid, location,
    TRIP_ZONE, make_trip, quiet_window_elsewhere, quiet_window_now, radar_preset,
    read_log, record_throttle, save_trip, seed_daily_counter,
    settings_email_only, suppression_reasons, trip_alert_service,
    write_presets, write_user_tier,
)


class _FakeOfficialSource:
    """Echte Quelle im Sinne des Quell-Protokolls (strukturelles Subtyping) —
    Vorbild ``tests/tdd/test_alert_log_compare_and_tenancy.py``."""

    def __init__(self, alerts) -> None:
        self._alerts = alerts

    @property
    def name(self) -> str:
        return "tdd-1467s3-source"

    def covers(self, lat, lon) -> bool:
        return True

    def fetch(self, lat, lon):
        return list(self._alerts)


def _gate_reasons_in_log(uid: str) -> set[str]:
    log = read_log(uid)
    gefunden: set[str] = set()
    for eintrag in log["entries"] + log["not_delivered"]:
        gefunden |= suppression_reasons(eintrag)
    return gefunden


def _assert_zustellung_ohne_unterdrueckungs_eintrag(uid: str, entity_id: str) -> None:
    """Ein ZUGESTELLTER Nowcast-Alarm darf keinen Unterdrueckungs-Eintrag
    hinterlassen — weder mit einem der drei Gate-Gruende noch ueberhaupt.

    Die zweite Haelfte ist die entscheidende: wird
    ``append_suppressed_entry()`` bedingungslos statt nur bei
    ``GateResult.allowed is False`` gerufen, traegt der Zusatz-Eintrag
    ``gate_reason=None`` (bei einer Freigabe ist ``GateResult.reason`` leer).
    Eine Pruefung, die nur nach den drei Gruenden sucht, laeuft an genau
    dieser Verfaelschung vorbei — gemessen am 2026-08-08, sie liess beide
    Pfade durch. Geprueft wird deshalb die Liste selbst: nach einer
    erfolgreichen Zustellung steht fuer diese Kennung GENAU EIN Eintrag in
    ``entries`` und KEINER in ``not_delivered``.

    Fachlicher Grund: das Protokoll beantwortet die Frage „warum kam kein
    Alarm?". Ein Eintrag, der auch dann erscheint, wenn der Alarm ankam,
    macht diese Antwort unbrauchbar.
    """
    log = read_log(uid)
    unterdrueckt = [
        e for e in log["not_delivered"]
        if isinstance(e, dict) and e.get("entity_id") == entity_id
    ]
    assert unterdrueckt == [], (
        f"Ein ZUGESTELLTER Nowcast hat einen Unterdrueckungs-Eintrag fuer "
        f"{entity_id!r} hinterlassen: {unterdrueckt!r}"
    )
    zugestellt = [
        e for e in log["entries"]
        if isinstance(e, dict) and e.get("entity_id") == entity_id
    ]
    assert len(zugestellt) == 1, (
        f"Erwartet GENAU EINEN Zustellungs-Eintrag fuer {entity_id!r}, "
        f"gefunden {len(zugestellt)}: {zugestellt!r}"
    )
    assert _gate_reasons_in_log(uid) == set(), (
        f"Ein ZUGESTELLTER Nowcast darf keinen Unterdrueckungs-Grund "
        f"protokollieren: {log!r}"
    )


# ═══════════════════ Ortsvergleich-Nowcast (AC-6/AC-7/AC-8) ═════════════════


def _setup_compare(uid: str, preset_id: str, *, quiet: bool = False) -> None:
    save_location(location("loc-log", "Protokolldorf"), user_id=uid)
    quiet_from, quiet_to = quiet_window_now() if quiet else quiet_window_elsewhere()
    write_presets(uid, [radar_preset(
        preset_id, ["loc-log"], user_id=uid, cooldown_minutes=120,
        quiet_from=quiet_from, quiet_to=quiet_to,
    )])


def _run_compare(uid: str) -> int:
    return compare_radar_service(
        uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: None,
    ).check_all_compare_presets()


def _assert_genau_ein_unterdrueckungs_eintrag(
    uid: str, entity_id: str, entity_type: str, grund: str,
) -> None:
    unterdrueckt = entries_for(uid, entity_id, bucket="not_delivered")
    passend = [e for e in unterdrueckt if grund in suppression_reasons(e)]
    assert len(passend) == 1, (
        f"Erwartet GENAU EINEN Protokoll-Eintrag mit dem Unterdrueckungs-Grund "
        f"{grund!r} fuer {entity_id!r} in 'not_delivered', gefunden "
        f"{len(passend)}. Protokoll: {read_log(uid)!r}"
    )
    assert passend[0].get("entity_type") == entity_type, (
        f"Der Eintrag muss den Typ {entity_type!r} tragen: {passend[0]!r}"
    )
    zugestellt = entries_for(uid, entity_id, bucket="entries")
    assert zugestellt == [], (
        f"Ein unterdrueckter Alarm darf NICHT in 'entries' landen — sonst "
        f"zaehlen Cockpit-Kachel und Archiv-Statistik ihn als Meldung: "
        f"{zugestellt!r}"
    )


def test_ac6_ruhezeit_erzeugt_protokoll_eintrag_im_ortsvergleich():
    """AC-6: Scheitert der Vergleichs-Nowcast an der Ruhezeit, steht im
    Alarm-Protokoll ein Eintrag mit dem Grund ``quiet_hours``.

    RED heute: der Vergleichs-Nowcast protokolliert Unterdrueckungen
    ueberhaupt nicht — das Protokoll bleibt leer."""
    uid, preset_id = fresh_uid("ac6"), "cp-1467s3-ac6"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_QUIET_HOURS

        write_user_tier(uid, "premium")  # Tageslimit aus dem Weg
        _setup_compare(uid, preset_id, quiet=True)

        assert _run_compare(uid) == 0, "Voraussetzung: die Ruhezeit muss sperren"
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, preset_id, "compare", REASON_QUIET_HOURS,
        )
    finally:
        clean_uid(uid)


def test_ac7_sperrzeit_erzeugt_protokoll_eintrag_im_ortsvergleich():
    """AC-7: Scheitert der Vergleichs-Nowcast an der Sperrzeit, steht im
    Alarm-Protokoll ein Eintrag mit dem Grund ``cooldown``.

    RED heute: keine Protokollierung (und die Sperrzeit wirkt noch aus der
    presetseigenen Altdatei, s. ``test_compare_radar_alert_shared_throttle``)."""
    uid, preset_id = fresh_uid("ac7"), "cp-1467s3-ac7"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_COOLDOWN

        write_user_tier(uid, "premium")
        _setup_compare(uid, preset_id)
        record_throttle(uid, SCOPE_COMPARE_RADAR, preset_id,
                        datetime.now(timezone.utc) - timedelta(minutes=5))

        assert _run_compare(uid) == 0, "Voraussetzung: die Sperrzeit muss sperren"
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, preset_id, "compare", REASON_COOLDOWN,
        )
    finally:
        clean_uid(uid)


def test_ac8_tageslimit_erzeugt_protokoll_eintrag_im_ortsvergleich():
    """AC-8: Scheitert der Vergleichs-Nowcast an der Tages-Obergrenze, steht
    im Alarm-Protokoll ein Eintrag mit dem Grund ``daily_limit``.

    RED heute: der Vergleichs-Nowcast kennt weder die Tages-Obergrenze noch
    die Protokollierung."""
    uid, preset_id = fresh_uid("ac8"), "cp-1467s3-ac8"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_DAILY_LIMIT

        write_user_tier(uid, "free")
        seed_daily_counter(uid, 2)
        _setup_compare(uid, preset_id)

        assert _run_compare(uid) == 0, "Voraussetzung: das Tageslimit muss sperren"
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, preset_id, "compare", REASON_DAILY_LIMIT,
        )
    finally:
        clean_uid(uid)


# ═══════════════════════════ Trip-Nowcast (AC-10) ═══════════════════════════


def _run_trip(
    uid: str, trip_id: str, *, quiet: bool = False, throttled: bool = False,
    daily_limit_reached: bool = False,
) -> int:
    # Issue #1726: Ruhezeit und Zaehler laufen in der Ortszone der TOUR —
    # `make_trip()` legt ihre Wegpunkte nach Island (TRIP_ZONE), nicht nach Wien.
    quiet_from, quiet_to = (
        quiet_window_now(zone=TRIP_ZONE) if quiet
        else quiet_window_elsewhere(zone=TRIP_ZONE)
    )
    save_trip(make_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to), uid)
    if throttled:
        record_throttle(uid, SCOPE_TRIP_RADAR, trip_id,
                        datetime.now(timezone.utc) - timedelta(minutes=5))
    seed_daily_counter(uid, 2 if daily_limit_reached else 0, zone=TRIP_ZONE)
    return trip_alert_service(
        uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
        lambda subject, body: None,
    ).check_radar_alerts()


def test_ac10_trip_nowcast_protokolliert_ruhezeit():
    """AC-10: Auch der Trip-Nowcast protokolliert seine Unterdrueckung —
    Ruhezeit.

    RED heute: der Trip-Pfad bricht bei Ruhezeit mit einem Debug-Log ab und
    schreibt nichts ins Alarm-Protokoll."""
    uid, trip_id = fresh_uid("ac10-qh"), "trip-1467s3-ac10-qh"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_QUIET_HOURS

        write_user_tier(uid, "premium")
        assert _run_trip(uid, trip_id, quiet=True) == 0, (
            "Voraussetzung: die Ruhezeit muss sperren"
        )
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, trip_id, "trip", REASON_QUIET_HOURS,
        )
    finally:
        clean_uid(uid)


def test_ac10_trip_nowcast_protokolliert_sperrzeit():
    """AC-10: Trip-Nowcast, Unterdrueckung durch die Sperrzeit.

    RED heute: keine Protokollierung."""
    uid, trip_id = fresh_uid("ac10-cd"), "trip-1467s3-ac10-cd"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_COOLDOWN

        write_user_tier(uid, "premium")
        assert _run_trip(uid, trip_id, throttled=True) == 0, (
            "Voraussetzung: die Sperrzeit muss sperren"
        )
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, trip_id, "trip", REASON_COOLDOWN,
        )
    finally:
        clean_uid(uid)


def test_ac10_trip_nowcast_protokolliert_tageslimit():
    """AC-10: Trip-Nowcast, Unterdrueckung durch die Tages-Obergrenze.

    RED heute: keine Protokollierung."""
    uid, trip_id = fresh_uid("ac10-dl"), "trip-1467s3-ac10-dl"
    clean_uid(uid)
    try:
        from services.alert_log import REASON_DAILY_LIMIT

        write_user_tier(uid, "free")
        assert _run_trip(uid, trip_id, daily_limit_reached=True) == 0, (
            "Voraussetzung: das Tageslimit muss sperren"
        )
        _assert_genau_ein_unterdrueckungs_eintrag(
            uid, trip_id, "trip", REASON_DAILY_LIMIT,
        )
    finally:
        clean_uid(uid)


def test_ac10_zugestellter_trip_nowcast_erzeugt_keinen_unterdrueckungs_grund():
    """AC-10 (Gegenprobe, Trip): Geht der Trip-Nowcast raus, entsteht KEIN
    Unterdrueckungs-Eintrag — die neue Protokollierung darf nicht bei jedem
    Lauf mitschreiben.

    Schuetzt die Implementierung davor, ``append_suppressed_entry()``
    bedingungslos statt nur bei ``allowed == False`` zu rufen."""
    uid, trip_id = fresh_uid("ac10-ok"), "trip-1467s3-ac10-ok"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        assert _run_trip(uid, trip_id) == 1, (
            "Voraussetzung: ohne Sperre muss der Trip-Nowcast zustellen"
        )
        _assert_zustellung_ohne_unterdrueckungs_eintrag(uid, trip_id)
    finally:
        clean_uid(uid)


def test_zugestellter_ortsvergleich_nowcast_erzeugt_keinen_unterdrueckungs_grund():
    """AC-6/7/8 (Gegenprobe, Ortsvergleich): das Gegenstueck zum Trip-Waechter
    darueber — geht der Vergleichs-Nowcast raus, entsteht KEIN
    Unterdrueckungs-Eintrag fuer dieses Preset.

    Ohne diesen Waechter waere die Protokollierung auf der Vergleichs-Seite
    unbewacht: AC-6/7/8 zeigen nur, dass bei einer SPERRE ein Eintrag
    entsteht, nicht dass er bei einer ZUSTELLUNG ausbleibt. Beide Nowcast-
    Pfade brauchen dieselbe Zusicherung — ein Waechter, den nur eine der
    beiden Seiten hat, ist genau die Trip/Vergleich-Asymmetrie, die diese
    Scheibe beseitigt."""
    uid, preset_id = fresh_uid("ov-ok"), "cp-1467s3-zustellung"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")  # Tageslimit aus dem Weg
        _setup_compare(uid, preset_id)

        assert _run_compare(uid) == 1, (
            "Voraussetzung: ohne Sperre muss der Vergleichs-Nowcast zustellen"
        )
        _assert_zustellung_ohne_unterdrueckungs_eintrag(uid, preset_id)
    finally:
        clean_uid(uid)


# ═══════════ Der Protokoll-Eintrag darf nicht luegen (F003) ═════════════════


@pytest.mark.parametrize("leerer_grund", [None, "", "   "])
def test_unterdrueckungs_eintrag_ohne_grund_scheitert_laut(leerer_grund):
    """Ein Unterdrueckungs-Eintrag OHNE Grund wird gar nicht erst geschrieben —
    die Schreibfunktion scheitert laut.

    Warum das inhaltlich zaehlt und nicht kosmetisch ist: beim LESEN deutet
    ``alert_log._missed_channels()`` einen leeren Grund still zu
    ``REASON_DELIVERY_FAILED`` um. Das Protokoll behauptete dann „Zustellung
    fehlgeschlagen", wo in Wahrheit gar keine Sperre vorlag — und damit das
    Gegenteil dessen, wofuer die Unterdrueckungs-Protokollierung ueberhaupt
    eingefuehrt wurde: wahrheitsgemaess zu beantworten, WARUM kein Alarm kam.

    Geprueft wird zusaetzlich, dass NICHTS auf Platte landet: ein Eintrag, der
    halb geschrieben und dann verworfen wird, waere dieselbe Luege mit
    Zwischenschritt.
    """
    from services import alert_log

    uid = fresh_uid("f003")
    clean_uid(uid)
    try:
        with pytest.raises(ValueError):
            alert_log.append_suppressed_entry(
                uid, entity_id="cp-1467s3-f003", entity_type="compare",
                reason=alert_log.REASON_NOWCAST, gate_reason=leerer_grund,
                effective_channels={"email"},
            )

        log = read_log(uid)
        assert log["entries"] == [] and log["not_delivered"] == [], (
            f"Trotz fehlendem Grund wurde ins Protokoll geschrieben: {log!r}"
        )
    finally:
        clean_uid(uid)


def test_unterdrueckungs_eintrag_mit_grund_wird_weiterhin_geschrieben():
    """Gegenprobe zum Waechter darueber: mit gueltigem Grund schreibt dieselbe
    Funktion unveraendert — der Schutz darf den Normalfall nicht mitnehmen.

    Ohne diese Haelfte waere auch eine Fassung „konform", die grundsaetzlich
    nichts mehr schreibt.
    """
    from services import alert_log

    uid = fresh_uid("f003-ok")
    clean_uid(uid)
    try:
        alert_log.append_suppressed_entry(
            uid, entity_id="cp-1467s3-f003-ok", entity_type="compare",
            reason=alert_log.REASON_NOWCAST,
            gate_reason=alert_log.REASON_COOLDOWN,
            effective_channels={"email"},
        )

        eintraege = entries_for(uid, "cp-1467s3-f003-ok", bucket="not_delivered")
        assert len(eintraege) == 1, f"Erwartet EINEN Eintrag: {read_log(uid)!r}"
        assert suppression_reasons(eintraege[0]) == {alert_log.REASON_COOLDOWN}
    finally:
        clean_uid(uid)


# ═════ Ein gescheiterter Eintrag reisst den Stapellauf nicht mit (F004) ═════


def _fehler_einspeisen(monkeypatch, kaputte_kennung: str) -> None:
    """Laesst den Protokoll-Eintrag fuer GENAU EINE Kennung scheitern.

    Kein Mock-Theater: die Ausnahme wird nicht erfunden, sondern von der
    ECHTEN Schreibfunktion unter ihrem echten Vertrag ausgeloest — der Aufruf
    wird mit leerem ``gate_reason`` durchgereicht, was die F003-Pruefung
    zurecht mit ``ValueError`` quittiert. Jede andere Kennung laeuft
    unveraendert in die Originalfunktion. Damit haengt dieser Test an genau der
    Zusicherung, die er absichern soll, statt an einer Attrappe.
    """
    from services import alert_log

    original = alert_log.append_suppressed_entry

    def _injektor(user_id, *, entity_id, **kwargs):
        if entity_id == kaputte_kennung:
            kwargs["gate_reason"] = None  # loest den echten Vertragsbruch aus
        return original(user_id, entity_id=entity_id, **kwargs)

    monkeypatch.setattr(alert_log, "append_suppressed_entry", _injektor)


def test_f004_gescheitertes_protokoll_stoppt_den_ortsvergleich_lauf_nicht(monkeypatch):
    """F004: Scheitert der Unterdrueckungs-Eintrag EINES Ortsvergleichs, laeuft
    der Stapellauf weiter — ein gesunder Ortsvergleich im selben Lauf bekommt
    seinen Alarm.

    Der kaputte Ortsvergleich steht ABSICHTLICH vorn in der Ladereihenfolge
    (`load_compare_presets` sortiert nach Dateiname, `...-a-` vor `...-b-`);
    stuende er hinten, bewiese der Test nichts.

    Ohne die Absicherung im Schleifenkoerper verlaesst die Ausnahme
    `check_all_compare_presets()` und der zweite Ortsvergleich wird nie
    erreicht — der gefaehrlichste Fehler dieser Scheibe (ausbleibender Alarm),
    ausgeloest ausgerechnet durch eine Haertung.
    """
    uid = fresh_uid("f004-ov")
    kaputt, gesund = "cp-1467s3-a-kaputt", "cp-1467s3-b-gesund"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")  # Tageslimit aus dem Weg
        save_location(location("loc-f004", "Nachbardorf"), user_id=uid)
        quiet_from, quiet_to = quiet_window_elsewhere()
        write_presets(uid, [
            radar_preset(kaputt, ["loc-f004"], user_id=uid,
                         quiet_from=quiet_from, quiet_to=quiet_to),
            radar_preset(gesund, ["loc-f004"], user_id=uid,
                         quiet_from=quiet_from, quiet_to=quiet_to),
        ])
        # Nur der erste Ortsvergleich ist gesperrt -> nur fuer ihn wird
        # ueberhaupt ein Unterdrueckungs-Eintrag versucht.
        record_throttle(uid, SCOPE_COMPARE_RADAR, kaputt,
                        datetime.now(timezone.utc) - timedelta(minutes=5))
        _fehler_einspeisen(monkeypatch, kaputt)

        mails: list = []
        sent = compare_radar_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
            lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert sent == 1, (
            f"Der gesunde Ortsvergleich {gesund!r} muss seinen Alarm bekommen, "
            f"obwohl das Protokoll von {kaputt!r} im selben Lauf scheiterte — "
            f"erhalten sent={sent}"
        )
        assert len(mails) == 1, (
            f"Genau EINE Mail erwartet (die des gesunden Ortsvergleichs), "
            f"erhalten {len(mails)}"
        )
        # Der kaputte bleibt unterdrueckt und ohne Protokoll-Eintrag — sein
        # Alarm geht NICHT etwa ersatzweise raus.
        assert entries_for(uid, kaputt, bucket="entries") == []
        assert entries_for(uid, kaputt, bucket="not_delivered") == []
        assert len(entries_for(uid, gesund, bucket="entries")) == 1
    finally:
        clean_uid(uid)


def test_f004_gescheitertes_protokoll_stoppt_den_trip_lauf_nicht(monkeypatch):
    """F004, Trip-Pendant: derselbe Nachweis fuer `check_radar_alerts()` — ein
    Trip, dessen Unterdrueckungs-Eintrag scheitert, kostet die uebrigen Trips
    des Nutzers nicht ihren Alarm."""
    uid = fresh_uid("f004-trip")
    kaputt, gesund = "trip-1467s3-a-kaputt", "trip-1467s3-b-gesund"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        quiet_from, quiet_to = quiet_window_elsewhere()
        for trip_id in (kaputt, gesund):
            save_trip(make_trip(trip_id, quiet_from=quiet_from, quiet_to=quiet_to), uid)
        record_throttle(uid, SCOPE_TRIP_RADAR, kaputt,
                        datetime.now(timezone.utc) - timedelta(minutes=5))
        _fehler_einspeisen(monkeypatch, kaputt)

        mails: list = []
        sent = trip_alert_service(
            uid, settings_email_only(), CountingFrameSource(onset_minutes=8),
            lambda subject, body: mails.append((subject, body)),
        ).check_radar_alerts()

        assert sent == 1, (
            f"Der gesunde Trip {gesund!r} muss seinen Alarm bekommen, obwohl "
            f"das Protokoll von {kaputt!r} im selben Lauf scheiterte — "
            f"erhalten sent={sent}"
        )
        assert len(mails) == 1, f"Genau EINE Mail erwartet, erhalten {len(mails)}"
        assert entries_for(uid, kaputt, bucket="not_delivered") == []
        assert len(entries_for(uid, gesund, bucket="entries")) == 1
    finally:
        clean_uid(uid)


# ══════════════ Geltungsbereich: NUR die Nowcast-Pfade (AC-9) ═══════════════


def test_ac9_aenderungsalarm_bekommt_keinen_unterdrueckungs_grund():
    """AC-9 (Invariante, heute GRUEN): Ein durch die Ruhezeit unterdrueckter
    Vorhersage-Aenderungsalarm erzeugt KEINEN Protokoll-Eintrag mit einem der
    drei neuen Gruende — der Geltungsbereich von (d) bleibt strikt auf die
    beiden Nowcast-Pfade begrenzt (offene Luecke O3 in
    ``feat_1459_alert_protokoll.md``, hier ausdruecklich NICHT geschlossen).

    Der Kontroll-Lauf (ohne Ruhezeit) beweist, dass derselbe Aufbau real
    alarmiert — sonst waere die Zusicherung leer."""
    kontrolle, gesperrt = fresh_uid("ac9d-ok"), fresh_uid("ac9d-quiet")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    try:
        write_user_tier(kontrolle, "premium")
        write_user_tier(gesperrt, "premium")

        offen = gust_alert_trip("trip-1467s3-ac9-ok")
        offen.alert_quiet_from, offen.alert_quiet_to = quiet_window_elsewhere()
        raus = trip_alert_service(
            kontrolle, settings_email_only(), CountingFrameSource(), lambda s, b: None,
        ).check_and_send_alerts(
            offen, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )
        assert raus is True, (
            "Voraussetzung: der Aenderungsalarm muss ohne Ruhezeit rausgehen"
        )

        still = gust_alert_trip("trip-1467s3-ac9-quiet")
        still.alert_quiet_from, still.alert_quiet_to = quiet_window_now()
        unterdrueckt = trip_alert_service(
            gesperrt, settings_email_only(), CountingFrameSource(), lambda s, b: None,
        ).check_and_send_alerts(
            still, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )
        assert unterdrueckt is False, (
            "Voraussetzung: die Ruhezeit muss den Aenderungsalarm unterdruecken"
        )
        assert _gate_reasons_in_log(gesperrt) == set(), (
            f"Der Aenderungsalarm-Pfad darf keinen der drei Nowcast-"
            f"Unterdrueckungsgruende protokollieren: {read_log(gesperrt)!r}"
        )
    finally:
        clean_uid(kontrolle)
        clean_uid(gesperrt)


def test_ac9_amtlicher_alarm_bekommt_keinen_unterdrueckungs_grund():
    """AC-9 (Invariante, heute GRUEN): Eine durch die Tages-Obergrenze
    unterdrueckte amtliche Warnung erzeugt KEINEN Protokoll-Eintrag mit einem
    der drei neuen Gruende.

    Der Kontroll-Lauf (freies Tagesbudget) beweist, dass der Aufbau real
    alarmiert — und dass der zweite Lauf tatsaechlich an der Tages-Obergrenze
    scheitert und nicht schon vorher."""
    import services.official_alerts.base as base
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from services.official_alerts.models import OfficialAlert

    kontrolle, gesperrt = fresh_uid("ac9a-ok"), fresh_uid("ac9a-limit")
    clean_uid(kontrolle)
    clean_uid(gesperrt)
    quellen = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        jetzt = datetime.now(timezone.utc)
        register_official_alert_source(_FakeOfficialSource([OfficialAlert(
            source="tdd-1467s3", hazard="thunderstorm", level=2, label="Gewitter",
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=6),
            region_label="Testregion",
        )]))

        for uid, verbraucht in ((kontrolle, 0), (gesperrt, 2)):
            write_user_tier(uid, "free")
            seed_daily_counter(uid, verbraucht)
            save_location(location("loc-amt", "Amtsdorf", LAT, LON), user_id=uid)
            write_presets(uid, [radar_preset(
                f"cp-1467s3-ac9-{uid[-6:]}", ["loc-amt"], user_id=uid,
            )])

        raus = CompareOfficialAlertService(
            settings=settings_email_only(), user_id=kontrolle,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert raus == 1, (
            f"Voraussetzung: die amtliche Warnung muss bei freiem Tagesbudget "
            f"rausgehen, erhalten {raus}"
        )

        unterdrueckt = CompareOfficialAlertService(
            settings=settings_email_only(), user_id=gesperrt,
            mail_sink=lambda subject, body: None,
        ).check_all_compare_presets()
        assert unterdrueckt == 0, (
            "Voraussetzung: das erreichte Tageslimit muss die amtliche Warnung "
            "unterdruecken"
        )
        assert _gate_reasons_in_log(gesperrt) == set(), (
            f"Der amtliche Pfad darf keinen der drei Nowcast-"
            f"Unterdrueckungsgruende protokollieren: {read_log(gesperrt)!r}"
        )
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(quellen)
        clean_uid(kontrolle)
        clean_uid(gesperrt)


# ═══ Issue #1467 Scheibe S4b-1 — Ereignis-Identitaet-Unterdrueckung (T6) ═════
# SPEC: docs/specs/modules/rework_1467_s4b_entdopplung.md, AC-15/AC-16
#
# `record_event_identity`/`check_event_identity_gate` existieren heute
# nicht -> ImportError. Diese Erweiterung von append_suppressed_entry() auf
# den amtlichen Pfad ist bewusst NUR fuer REASON_EVENT_DUPLICATE gedacht --
# der bestehende Waechter oben (test_ac9_amtlicher_alarm_bekommt_keinen_
# unterdrueckungs_grund) bleibt fuer Ruhezeit/Tageslimit unveraendert gruen,
# weil `suppression_reasons()`/`_gate_reasons_in_log()` NUR die drei
# S3/S4a-Gate-Gruende zaehlen (REASON_EVENT_DUPLICATE ist bewusst NICHT in
# dieser Menge, s. Helper oben) — AC-16 grenzt das explizit ab.


def test_ac15_trip_nowcast_protokolliert_ereignis_identitaet_unterdrueckung():
    """AC-15 (Beobachtbarkeit Nowcast, Erweiterung ggu. S3): ein durch
    ``check_event_identity_gate`` unterdrueckter Trip-Nowcast erzeugt GENAU
    EINEN Protokoll-Eintrag mit ``reason=REASON_NOWCAST`` und
    ``gate_reason=REASON_EVENT_DUPLICATE``.

    RED heute: ImportError (``services.alert_gate.record_event_identity``
    fehlt)."""
    from services.alert_gate import record_event_identity
    from services.alert_log import REASON_EVENT_DUPLICATE

    uid, trip_id = fresh_uid("s4b-ac15"), "trip-1467s4b-ac15"
    clean_uid(uid)
    try:
        write_user_tier(uid, "premium")
        now = datetime.now(timezone.utc)
        # Bereits registrierte amtliche Warnung derselben Klasse/desselben
        # Segments ("1", s. trip_segments.py::segment_id=i+1 fuer die
        # Einzeletappe von make_trip()) -- der nachfolgende Nowcast gilt als
        # Duplikat.
        record_event_identity(
            user_id=uid, entity_id=trip_id, hazard_class="wet",
            segment_ids=["1"], severity="HIGH",
            window_start=now - timedelta(minutes=10),
            window_end=now + timedelta(hours=4), now=now,
        )
        assert _run_trip(uid, trip_id) == 0, (
            "Voraussetzung: die Ereignis-Identitaet muss den Nowcast unterdruecken"
        )
        unterdrueckt = entries_for(uid, trip_id, bucket="not_delivered")
        passend = [
            e for e in unterdrueckt
            if any(
                item.get("reason") == REASON_EVENT_DUPLICATE
                for item in e.get("channels_not_sent", [])
                if isinstance(item, dict)
            )
        ]
        assert len(passend) == 1, (
            f"Erwartet GENAU EINEN Protokoll-Eintrag mit gate_reason="
            f"{REASON_EVENT_DUPLICATE!r}, gefunden {len(passend)}: {read_log(uid)!r}"
        )
    finally:
        clean_uid(uid)


def test_ac16_amtliche_ereignis_identitaet_unterdrueckung_erzeugt_protokoll_eintrag():
    """AC-16 (a): eine durch ``check_event_identity_gate`` unterdrueckte
    amtliche Warnung erzeugt GENAU EINEN Protokoll-Eintrag mit
    ``reason=REASON_OFFICIAL_ALERT`` und ``gate_reason=REASON_EVENT_DUPLICATE``
    -- bewusste Erweiterung ggu. S4a E3, wo der amtliche Pfad NIE
    protokollierte.

    RED heute: ImportError (``record_event_identity``)."""
    from services.alert_gate import record_event_identity
    from services.alert_log import REASON_EVENT_DUPLICATE, REASON_OFFICIAL_ALERT
    from services.official_alerts import OfficialAlert, register_official_alert_source
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    uid = fresh_uid("s4b-ac16")
    clean_uid(uid)
    quellen = list(base_mod()._REGISTERED_SOURCES)
    base_mod()._REGISTERED_SOURCES.clear()
    try:
        now = datetime.now(timezone.utc)
        record_event_identity(
            user_id=uid, entity_id="trip-s4b-ac16", hazard_class="wet",
            segment_ids=["1"], severity="HIGH", point_at=now, now=now,
        )
        trip = gust_alert_trip("trip-s4b-ac16")
        # Issue #1467 S4b-1 Test-Fix: `gust_alert_trip()` ist fuer die
        # Aenderungsalarm-Tests gebaut und setzt bewusst
        # `official_alert_triggers_enabled = False` (Zeile 162 der
        # gemeinsamen Helferfunktion, tests/helpers/alert_log_fixtures.py) --
        # das wuerde `check_official_alert_triggers()` fuer JEDEN Trip
        # blockieren, unabhaengig vom Ereignis-Identitaets-Gate, das dieser
        # Test eigentlich prueft. Nur auf DIESER Instanz zurueckgesetzt, die
        # geteilte Helferfunktion bleibt unveraendert (andere Tests haengen
        # an ihrem Bestandsverhalten).
        trip.official_alert_triggers_enabled = None
        WeatherSnapshotService(user_id=uid).save_dated(
            trip.id, date.today(), [weather(1, precip_sum_mm=2.0)],
        )
        alert = OfficialAlert(
            source="tdd-s4b-ac16", hazard="thunderstorm", level=3,
            label="AC-16-Warnung", valid_from=now - timedelta(minutes=5),
            valid_to=now + timedelta(minutes=30), region_label="AC16-Region",
        )
        register_official_alert_source(_FakeOfficialSource([alert]))

        svc = TripAlertService(user_id=uid, mail_sink=lambda s, b: None)
        notices = svc.check_official_alert_triggers(trip)
        assert len(notices) == 1, "Voraussetzung: die Warnung muss als neu erkannt werden"

        sent = svc._send_official_alert_only(trip, notices)
        assert sent is False, f"Voraussetzung: die Warnung muss unterdrueckt werden ({sent!r})"

        unterdrueckt = entries_for(uid, trip.id, bucket="not_delivered")
        passend = [
            e for e in unterdrueckt
            if e.get("reason") == REASON_OFFICIAL_ALERT
            and any(
                item.get("reason") == REASON_EVENT_DUPLICATE
                for item in e.get("channels_not_sent", [])
                if isinstance(item, dict)
            )
        ]
        assert len(passend) == 1, (
            f"Erwartet GENAU EINEN Protokoll-Eintrag mit reason="
            f"{REASON_OFFICIAL_ALERT!r} und gate_reason={REASON_EVENT_DUPLICATE!r}: "
            f"{read_log(uid)!r}"
        )
    finally:
        base_mod()._REGISTERED_SOURCES.clear()
        base_mod()._REGISTERED_SOURCES.extend(quellen)
        clean_uid(uid)


def base_mod():
    import services.official_alerts.base as base

    return base
