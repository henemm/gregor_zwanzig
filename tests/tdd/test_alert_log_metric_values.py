"""TDD RED — Issue #1954: Das Alarm-Protokoll haelt auch den WERT fest.

SPEC: docs/specs/modules/feat_1459_alert_protokoll.md (AC-17..AC-24, v1.6)

Bisher steht im Protokoll nur, WORUM es ging (Register-Paar ``metric_id`` +
``aggregation``, #1459). Ab #1954 traegt jeder Register-Eintrag zusaetzlich die
beiden OPTIONALEN Felder ``value`` (neuer Wert) und ``previous_value`` (alter
Wert) — PO-Entscheide E1-E4.

RED-Grund heute: ``alert_log.append_entry()`` serialisiert die ``metrics``-Liste
als ``{"metric_id": ..., "aggregation": ...}`` (``src/services/alert_log.py:227``)
— die beiden neuen Schluessel existieren nirgends.

Prueforte (bindend): geprueft wird das aus ``alert_log.json`` GELESENE
``metrics``-Dict, nicht die interne Rueckgabeform von ``register_pairs_*``. Die
Zusicherung wirkt im geschriebenen Eintrag; ob die Implementierung intern
Tupel oder Dicts durchreicht, ist ihre Sache.

Positivkontrollen: AC-20/21/22/23 sichern eine ABWESENHEIT bzw. eine
Unveraendertheit zu — die ist heute trivial wahr, weil es die Wert-Felder
ueberhaupt nicht gibt. Jeder dieser Tests fuehrt deshalb eine Positivkontrolle
mit, die belegt, dass der Pruefling Werte ueberhaupt schreibt. Ohne sie waere
der Test gruen, ohne irgendetwas zu bewachen.

Mock-frei: echte ``TripAlertService``-Laeufe, echte Modelle, echte Persistenz
ueber die pytest-isolierte ``get_data_dir()``-Basis, Transport ausschliesslich
ueber die vorhandenen ``mail_sink``/``radar_service``-DI-Naehte (kein Netz).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.loader import get_briefings_dir, get_data_dir
from app.models import ChangeSeverity, WeatherChange

from services.alert_log import (
    REASON_FORECAST_CHANGE,
    REASON_NOWCAST,
    REASON_QUIET_HOURS,
    append_entry,
    append_suppressed_entry,
    read_undelivered,
    register_pairs_from_changes,
    register_pairs_from_corridor_hits,
)

from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

from tests.helpers.alert_log_fixtures import (
    LAT, LON, fresh_user, gust_alert_trip, read_log, settings_email_only, weather,
)


# ───────────────────────────── Bausteine ───────────────────────────────────

def _service(user_id: str, sink: list, **kwargs):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: sink.append((subject, body)), **kwargs,
    )


def _latest_entry(user_id: str) -> dict:
    entries = read_log(user_id)["entries"]
    assert entries, "Es wurde ueberhaupt kein Protokoll-Eintrag geschrieben."
    return entries[-1]


def _change(metric: str, old: float, new: float, segment_id: str = "1") -> WeatherChange:
    return WeatherChange(
        metric=metric, old_value=old, new_value=new, delta=new - old, threshold=20.0,
        severity=ChangeSeverity.MAJOR,
        direction="increase" if new >= old else "decrease",
        segment_id=segment_id,
    )


def _protokolliere(user_id: str, metrics, *, entity_id: str = "trip-x",
                   sent_channels=("email",)) -> None:
    """Register-Paare durch die ECHTE Schreibfunktion in die Datei geben."""
    append_entry(
        user_id=user_id, entity_id=entity_id, entity_type="trip", changes_count=1,
        severity="major", metrics=metrics, reason=REASON_FORECAST_CHANGE,
        effective_channels=["email", "telegram"], sent_channels=list(sent_channels),
    )


def _dicts_fuer(entry: dict, metric_id: str, aggregation: str) -> list[dict]:
    assert "metrics" in entry, (
        f"Der Eintrag haelt die Wettergroesse nicht fest: {sorted(entry)!r}"
    )
    return [
        m for m in entry["metrics"]
        if (m.get("metric_id"), m.get("aggregation")) == (metric_id, aggregation)
    ]


def _dict_fuer(entry: dict, metric_id: str, aggregation: str) -> dict:
    treffer = _dicts_fuer(entry, metric_id, aggregation)
    assert len(treffer) == 1, (
        f"Erwartet GENAU EIN Register-Dict fuer ({metric_id!r},{aggregation!r}), "
        f"erhalten {len(treffer)}: {entry.get('metrics')!r}"
    )
    return treffer[0]


def _positivkontrolle_wert_wird_geschrieben(prefix: str) -> None:
    """Belegt, dass der Pruefling Wert-Felder UEBERHAUPT schreibt.

    Ohne diesen Nachweis waere jede Abwesenheits- bzw. Unveraendertheits-
    Zusicherung trivial wahr — heute fehlen die Felder ja ueberall.
    """
    uid = fresh_user(prefix)
    _protokolliere(uid, register_pairs_from_changes([_change("gust_max_kmh", 20.0, 60.0)]))
    m = _dict_fuer(_latest_entry(uid), "gust", "max")
    assert m.get("value") == 60.0 and m.get("previous_value") == 20.0, (
        "Positivkontrolle gescheitert: der Pruefling schreibt gar keine "
        f"Wert-Felder, die gepruefte Abwesenheit waere damit bedeutungslos: {m!r}"
    )


# ───────────────────────────────── AC-17 ───────────────────────────────────

def test_ac17_boeen_aenderung_protokolliert_neuen_und_alten_wert():
    """AC-17 GIVEN eine Tour-Vorhersage-Aenderung am Boeen-Feld
    (``old_value=20.0`` -> ``new_value=60.0``)
    WHEN der Protokoll-Eintrag geschrieben wird
    THEN traegt das Register-Dict fuer ``("gust","max")`` zusaetzlich
    ``value: 60.0`` und ``previous_value: 20.0``."""
    uid = fresh_user("ac17")
    trip = gust_alert_trip("trip-ac17")
    mails: list = []

    sent = _service(uid, mails).check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )

    assert sent is True and mails, "Voraussetzung: der Boeen-Alarm muss versendet werden."
    m = _dict_fuer(_latest_entry(uid), "gust", "max")
    assert m.get("value") == 60.0, (
        f"Der neue Wert fehlt oder ist falsch: {m!r}"
    )
    assert m.get("previous_value") == 20.0, (
        f"Der alte Wert fehlt oder ist falsch: {m!r}"
    )


# ───────────────────────────────── AC-18 ───────────────────────────────────

def test_ac18_bei_mehrfachtreffer_gewinnt_der_groesste_betrag_der_aenderung():
    """AC-18 GIVEN DREI Aenderungen derselben Groesse in EINEM Lauf
    WHEN protokolliert wird
    THEN entsteht GENAU EIN Register-Dict fuer diese Groesse, dessen
    ``value``/``previous_value`` von der Aenderung mit dem groessten
    ``abs(delta)`` stammen.

    Drei statt der in der Spec genannten zwei Aenderungen, und die grosse
    steht in der MITTE: bei nur zweien waere der Extremwert zwangslaeufig
    entweder der erste oder der letzte — eine naive "nimm den ersten"- bzw.
    "nimm den letzten"-Implementierung bliebe unentdeckt. Zusaetzlich traegt
    die Gewinner-Aenderung NICHT den groessten ``new_value`` (90.0 gehoert der
    ersten), damit "groesstes abs(delta)" nicht mit "groesster Absolutwert"
    verwechselbar ist.
    """
    uid = fresh_user("ac18")
    changes = [
        _change("gust_max_kmh", 70.0, 90.0, segment_id="1"),   # |delta| 20, new 90
        _change("gust_max_kmh", 10.0, 55.0, segment_id="2"),   # |delta| 45  <- Gewinner
        _change("gust_max_kmh", 40.0, 65.0, segment_id="3"),   # |delta| 25
    ]

    _protokolliere(uid, register_pairs_from_changes(changes), entity_id="trip-ac18")

    entry = _latest_entry(uid)
    assert len(_dicts_fuer(entry, "gust", "max")) == 1, (
        "Mehrere Aenderungen derselben Groesse duerfen NUR EINEN Register-Eintrag "
        f"ergeben: {entry.get('metrics')!r}"
    )
    m = _dict_fuer(entry, "gust", "max")
    assert m.get("value") == 55.0, (
        "Es muss der Wert der Aenderung mit dem groessten abs(delta) (45) stehen — "
        f"weder der erste (90.0) noch der letzte (65.0): {m!r}"
    )
    assert m.get("previous_value") == 10.0, (
        f"Der alte Wert muss zur selben Aenderung gehoeren (10.0): {m!r}"
    )


# ───────────────────────────────── AC-19 ───────────────────────────────────

def test_ac19a_fast_gleiche_werte_derselben_groesse_bleiben_ein_eintrag():
    """AC-19 (a) GIVEN zwei Aenderungen DERSELBEN Groesse mit fast gleichem,
    aber nicht identischem Wert (``59.9`` und ``60.1``)
    WHEN protokolliert wird
    THEN bleibt es bei EINEM Register-Dict — der Wert gehoert NICHT in den
    Dedupe-Schluessel (E3), sonst zerfaellt jede Groesse an
    Fliesskomma-Rauschen in mehrere Eintraege.

    Die zweite Zusicherung (das ueberlebende Dict TRAEGT einen Wert) ist
    Pflichtbestandteil: ohne sie waere "genau eins" heute trivial wahr, weil
    der Wert gar nicht erst geschrieben wird.
    """
    uid = fresh_user("ac19a")
    changes = [
        _change("gust_max_kmh", 20.0, 59.9, segment_id="1"),
        _change("gust_max_kmh", 20.0, 60.1, segment_id="2"),
    ]

    _protokolliere(uid, register_pairs_from_changes(changes), entity_id="trip-ac19a")

    entry = _latest_entry(uid)
    assert len(_dicts_fuer(entry, "gust", "max")) == 1, (
        "59.9 und 60.1 derselben Groesse duerfen NICHT in zwei Eintraege zerfallen: "
        f"{entry.get('metrics')!r}"
    )
    m = _dict_fuer(entry, "gust", "max")
    assert "value" in m and "previous_value" in m, (
        "Der ueberlebende Eintrag muss die Wert-Felder tragen — sonst ist die "
        f"Eins-Zusicherung nur deshalb wahr, weil es keine Werte gibt: {m!r}"
    )


def test_ac19b_verschiedene_groessen_kollabieren_nicht_zu_einem_eintrag():
    """AC-19 (b) GIVEN zwei VERSCHIEDENE Groessen mit verschiedenen Werten
    WHEN protokolliert wird
    THEN bleiben es ZWEI Register-Dicts, jedes mit seinem eigenen Wert."""
    uid = fresh_user("ac19b")
    changes = [
        _change("gust_max_kmh", 20.0, 60.0, segment_id="1"),
        _change("temp_max_c", 12.0, 31.0, segment_id="1"),
    ]

    _protokolliere(uid, register_pairs_from_changes(changes), entity_id="trip-ac19b")

    entry = _latest_entry(uid)
    assert len(entry.get("metrics") or []) == 2, (
        "Zwei verschiedene Groessen duerfen NICHT zu einem Eintrag kollabieren: "
        f"{entry.get('metrics')!r}"
    )
    boe = _dict_fuer(entry, "gust", "max")
    temp = _dict_fuer(entry, "temperature", "max")
    assert (boe.get("value"), boe.get("previous_value")) == (60.0, 20.0), (
        f"Boeen-Werte falsch zugeordnet: {boe!r}"
    )
    assert (temp.get("value"), temp.get("previous_value")) == (31.0, 12.0), (
        f"Temperatur-Werte falsch zugeordnet: {temp!r}"
    )


# ───────────────────────────────── AC-20 ───────────────────────────────────

def _save_radar_trip(user_id: str, trip_id: str) -> None:
    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    # #1667 S1: Ankunftszeiten aus dem wanduhr-robusten Helfer statt aus roher
    # now+Nh-Arithmetik — sonst laeuft die Folge ab 23:00 UTC ueber Mitternacht
    # und das Segment landet in der Vergangenheit ("alle Segmente vorbei").
    arr0, arr1 = active_window_offsets(LAT, LON, 60, 240)
    (briefings / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Radar-Trip",
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": stage_date(LAT, LON).isoformat(),
            "waypoints": [
                {"id": "W0", "name": "Start", "lat": LAT, "lon": LON,
                 "elevation_m": 1000.0, "arrival_calculated": arr0},
                {"id": "W1", "name": "Ziel", "lat": LAT + 0.1, "lon": LON + 0.1,
                 "elevation_m": 1500.0, "arrival_calculated": arr1},
            ],
        }],
        "report_config": {"trip_id": trip_id, "send_email": True, "send_telegram": False},
    }))


def _frames(is_convective: bool):
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return lambda lat, lon: [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0,
                   is_convective=is_convective),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0,
                   is_convective=is_convective),
    ]


def test_ac20_konvektiver_nowcast_traegt_ueberhaupt_kein_wert_feld():
    """AC-20 GIVEN ein Radar-Alarm mit ``is_convective=True``
    WHEN protokolliert wird
    THEN fehlen im Register-Dict BEIDE Schluessel ``value`` und
    ``previous_value`` vollstaendig — Absenz heisst "nicht erhebbar" (E2),
    ein Nowcast hat keinen Messwert. ``0``/``None`` waere eine erfundene Zahl
    und damit eine Falschaussage.

    Die Positivkontrolle laeuft zuerst: sie belegt, dass der Pruefling Werte
    ueberhaupt schreibt — sonst waere die Abwesenheit hier bedeutungslos.
    """
    from services.radar_service import RadarNowcastService

    _positivkontrolle_wert_wird_geschrieben("ac20-kontrolle")

    uid = fresh_user("ac20")
    _save_radar_trip(uid, "trip-radar")
    mails: list = []
    svc = _service(uid, mails,
                   radar_service=RadarNowcastService(frame_source=_frames(True)))
    assert svc.check_radar_alerts() == 1, "Voraussetzung: der Radar-Alarm muss feuern."

    m = _dict_fuer(_latest_entry(uid), "thunder", "max")
    assert "value" not in m, (
        f"Ein Radar-Nowcast darf keinen Wert erfinden: {m!r}"
    )
    assert "previous_value" not in m, (
        f"Ein Radar-Nowcast hat auch keinen Vorwert: {m!r}"
    )


# ───────────────────────────────── AC-21 ───────────────────────────────────

_ALT_EINTRAG_V15 = {
    "entity_id": "trip-alt", "entity_type": "trip",
    "sent_at": "2026-08-01T06:00:00+00:00",
    "changes_count": 2, "severity": "major",
    "metrics": [
        {"metric_id": "gust", "aggregation": "max"},
        {"metric_id": "temperature", "aggregation": "max"},
    ],
    "hazards": [], "reason": "forecast_change",
    "channels_sent": ["email"],
    "channels_not_sent": [{"channel": "telegram", "reason": "channel_disabled"}],
}


def test_ac21_alt_eintrag_ohne_wert_bleibt_beim_anhaengen_unveraendert():
    """AC-21 GIVEN eine bestehende ``alert_log.json`` mit einem Alt-Eintrag im
    v1.5-Schema (``metrics``-Dicts nur mit ``metric_id``/``aggregation``)
    WHEN ein neuer Eintrag angehaengt wird
    THEN bleibt der Alt-Eintrag feldgleich unveraendert — Read-Modify-Write,
    keine Migration, kein Nachtragen von ``value: null``.

    Der neue Eintrag traegt im selben Test die Wert-Felder: erst dadurch ist
    die Unveraendertheit des Alten eine Aussage und nicht bloss die Folge
    davon, dass es die Felder nirgends gibt.
    """
    uid = fresh_user("ac21")
    pfad = get_data_dir(uid) / "alert_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [_ALT_EINTRAG_V15], "not_delivered": []}))

    _protokolliere(uid, register_pairs_from_changes([_change("gust_max_kmh", 20.0, 60.0)]),
                   entity_id="trip-ac21")

    entries = read_log(uid)["entries"]
    assert len(entries) == 2, f"Erwartet Alt- plus Neu-Eintrag, erhalten {len(entries)}."
    neu = _dict_fuer(entries[-1], "gust", "max")
    assert neu.get("value") == 60.0 and neu.get("previous_value") == 20.0, (
        "Positivkontrolle: der NEUE Eintrag muss die Wert-Felder tragen, sonst "
        f"bewacht die Unveraendertheits-Pruefung nichts: {neu!r}"
    )
    assert entries[0] == _ALT_EINTRAG_V15, (
        "Der Alt-Eintrag wurde beim Anhaengen veraendert (Migration statt "
        f"Read-Modify-Write): {entries[0]!r}"
    )


# ───────────────────────────────── AC-22 ───────────────────────────────────

def test_ac22_leseseite_liefert_weiterhin_zweigliedrige_register_paare():
    """AC-22 GIVEN ein Eintrag, dessen ``metrics``-Dicts ``value``/
    ``previous_value`` tragen und der einen Kanal nicht erreicht hat
    WHEN ``read_undelivered()`` ihn liest
    THEN bleibt ``UndeliveredIncident.metrics`` ein reines
    ``tuple[tuple[str, str], ...]`` — die Wert-Felder werden NICHT extrahiert
    und erreichen den Mail-Renderer nicht (Zusicherung #1503/#1474).

    Der Eintrag entsteht ueber den ECHTEN Schreibpfad, nicht von Hand: nur so
    prueft der Test das Format, das die Implementierung tatsaechlich ablegt.
    """
    uid = fresh_user("ac22")
    _protokolliere(uid, register_pairs_from_changes([_change("gust_max_kmh", 20.0, 60.0)]),
                   entity_id="trip-ac22", sent_channels=["email"])

    geschrieben = _dict_fuer(_latest_entry(uid), "gust", "max")
    assert "value" in geschrieben, (
        "Voraussetzung: der gelesene Eintrag muss ueberhaupt ein Wert-Feld tragen, "
        f"sonst prueft der Test die Leseseite gegen v1.5-Daten: {geschrieben!r}"
    )

    vorfaelle = read_undelivered(uid, entity_id="trip-ac22", entity_type="trip")
    assert len(vorfaelle) == 1, (
        "Voraussetzung: genau ein Vorfall (Telegram nicht zugestellt), erhalten "
        f"{len(vorfaelle)}."
    )
    assert vorfaelle[0].metrics == (("gust", "max"),), (
        "Die Leseseite muss zweigliedrig bleiben — kein Wert-Anteil im Tupel: "
        f"{vorfaelle[0].metrics!r}"
    )


# ───────────────────────────────── AC-23 ───────────────────────────────────

def test_ac23_unterdrueckte_meldung_bleibt_ohne_register_eintrag():
    """AC-23 GIVEN ``append_suppressed_entry()`` wird fuer eine unterdrueckte
    Nowcast-Meldung aufgerufen
    WHEN der Eintrag geschrieben wird
    THEN bleibt ``metrics`` die leere Liste — unveraendert gegenueber dem
    Bestand vor #1954 (zum Gate-Zeitpunkt ist die Groesse strukturell noch
    nicht erkannt, ein Wert waere erfunden).

    Positivkontrolle voran, sonst waere "leer" heute trivial wahr.
    """
    _positivkontrolle_wert_wird_geschrieben("ac23-kontrolle")

    uid = fresh_user("ac23")
    append_suppressed_entry(
        user_id=uid, entity_id="trip-ac23", entity_type="trip",
        reason=REASON_NOWCAST, gate_reason=REASON_QUIET_HOURS,
        effective_channels=["email"],
    )

    unzustellbar = read_log(uid)["not_delivered"]
    assert len(unzustellbar) == 1, (
        f"Voraussetzung: genau ein Unterdrueckungs-Eintrag, erhalten {len(unzustellbar)}."
    )
    assert unzustellbar[-1].get("metrics") == [], (
        "Eine unterdrueckte Meldung darf weder Groesse noch Wert tragen: "
        f"{unzustellbar[-1].get('metrics')!r}"
    )


# ───────────────────────────────── AC-24 ───────────────────────────────────

def test_ac24_korridor_treffer_traegt_wert_ohne_vorwert_und_ohne_schwelle():
    """AC-24 GIVEN ein ``CorridorHit`` mit ``value=45.0`` und ``bound=40.0``
    WHEN er ueber ``register_pairs_from_corridor_hits()`` protokolliert wird
    THEN traegt das Register-Dict ``value: 45.0``, aber KEINEN
    ``previous_value`` (ein Grenzwert-Treffer hat keinen Vorwert) und KEINEN
    ``bound`` (die Schwelle ist Konfiguration, kein Messwert — E1/E4)."""
    from services.corridor_threshold import CorridorHit

    uid = fresh_user("ac24")
    hit = CorridorHit(metric="wind_gust", value=45.0, bound=40.0, direction="above",
                      segment_id="1", occurred_at=None)

    _protokolliere(uid, register_pairs_from_corridor_hits([hit]), entity_id="trip-ac24")

    m = _dict_fuer(_latest_entry(uid), "gust", "max")
    assert m.get("value") == 45.0, (
        f"Der gerissene Wert fehlt oder ist falsch: {m!r}"
    )
    assert "previous_value" not in m, (
        f"Ein Grenzwert-Treffer hat keinen Vorwert — der Schluessel darf fehlen: {m!r}"
    )
    assert "bound" not in m, (
        f"Die Schwelle gehoert NICHT ins Protokoll (E1): {m!r}"
    )
