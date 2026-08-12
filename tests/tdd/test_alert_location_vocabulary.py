"""Eine Ortssprache fuer alle Trip-Alarme (#1744 Scheibe A1).

SPEC:    docs/specs/modules/fix_1744_alarm_format_angleichen.md (AC-1 bis AC-7)
KONTEXT: docs/context/fix-1744-a-alarm-format.md

Heute nennen zwei Alarm-Mails zum selben Ort zwei verschiedene Dinge:

    [KHW 403] km 8–8 · Gewitter in 8 Min        (Radar-Nowcast, render.py:110)
    [KHW 403] 🏁 Ziel · GELB Gewitter (Mi)      (amtliche Warnung, official_alerts.py:264)

Geprueft wird ausschliesslich die Ausgabe, die den Nutzer erreicht: der
gerenderte Betreff, der gerenderte Mailkoerper, die gerenderte Kurznachricht.
Keine Hilfsfunktion isoliert, keine Dateiinhalt-Checks, keine Mocks — echte
Domaenen-Objekte (`WeatherChange`, `TripSegment`, `OfficialAlert`,
`SavedLocation`) durch die echten Projektionen und Renderer.

RED-VERTRAG (was die GREEN-Phase anlegen muss, damit diese Datei OHNE Umbau
gruen wird):

1. `OnsetEvent` (src/output/renderers/alert/model.py:31) bekommt ein additives,
   optionales Feld ``segment_id: int | str | None = None`` — Namensmuster wie
   `WeatherChange.segment_id` (models.py:541), `TripSegment.segment_id`
   (models.py:389) und `CorridorHit.segment_id`. Nur die Nowcast-Tests
   konstruieren es direkt (`_onset_message`); ohne dieses Feld sind sie rot mit
   `TypeError: unexpected keyword argument 'segment_id'`.
2. `AlertEvent` braucht dieselbe Kennung, aber KEIN Test setzt sie hier direkt:
   der Abweichungspfad laeuft ueber `to_alert_message()` und die echten
   `TripSegment.segment_id` (project.py:84-94). Wie das Feld dort heisst, ist
   fuer diese Datei folgenlos.
3. Die Ortsangabe entsteht in GENAU EINER Funktion (Spec „Eine Formatierung,
   zwei Aufrufer"), Aufloesungsreihenfolge:
   `location_label` → Segment-Kennung (`format_segment_reference`) → `km a–b`.

NICHT Gegenstand dieser Datei: AC-8 bis AC-12 (Mail-Koerper, Scheibe A2).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

UTC = timezone.utc
TRIP_NAME = "KHW 403"
TRIP_TZ = ZoneInfo("Europe/Vienna")
# Warnzeitraum fest datiert -> Wochentag im Betreff ist deterministisch ("Mi").
WARN_FROM = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
WARN_TO = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)

# Betreff-Bauform beider Pfade: "[<Trip>] <Ortsangabe> · <Kernaussage>"
# (render.py:294-325 bzw. official_alerts.py:859-919).
_SUBJECT_RE = re.compile(r"^\[[^\]]*\]\s+(?P<where>.+?)\s+·\s+.+$")


# ---------------------------------------------------------------------------
# Fixtures — echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _gpx(distance_km: float):
    """GPX-Punkt in Kaernten (Trip-Zeitzone Europe/Vienna)."""
    from app.models import GPXPoint

    return GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                    distance_from_start_km=distance_km)


def _segment(segment_id, km_from: float, km_to: float):
    """Eine Etappe mit Wetterdaten (`SegmentWeatherData`), wie sie der
    Abweichungs-Detektor an `to_alert_message()` reicht."""
    from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment

    seg = TripSegment(
        segment_id=segment_id,
        start_point=_gpx(km_from), end_point=_gpx(km_to),
        start_time=datetime(2026, 7, 1, 6, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
        duration_hours=2.0, distance_km=km_to - km_from,
        ascent_m=200.0, descent_m=50.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _change(segment_id, *, old: float = 50.0, new: float = 80.0):
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric="gust_max_kmh", old_value=old, new_value=new, delta=new - old,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id=segment_id,
        occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )


def _delta_message(specs):
    """Abweichungsalarm ueber die echte Projektion (`to_alert_message`).

    `specs`: Liste `(segment_id, km_from, km_to)` — je Eintrag eine betroffene
    Etappe mit genau einer Aenderung. Die Segment-Kennung kommt damit dort her,
    wo sie im Produktivlauf herkommt: aus `TripSegment.segment_id`
    (project.py:84). Diese Datei setzt sie NIE direkt am Renderer-Modell.
    """
    from output.renderers.alert.project import to_alert_message

    segments = [_segment(sid, a, b) for sid, a, b in specs]
    changes = [_change(sid) for sid, _a, _b in specs]
    return to_alert_message(
        changes, segments, TRIP_NAME, tz=TRIP_TZ, stand_at="10:00",
    )


def _onset_message(*, segment_id="__omit__", km_from: float = 8.0,
                   km_to: float = 8.0, convective: bool = True):
    """Radar-Nowcast-Alarm, gebaut wie `NotificationService.send_radar_alert()`
    (notification_service.py:1234) — dort entsteht das `OnsetEvent` direkt aus
    dem `RadarAlertRequest`, es gibt keine Projektionsfunktion dazwischen.

    `segment_id="__omit__"` laesst die Kennung weg (Altdaten-/Bestandsaufrufer
    wie radar_alert_service.py:59 und validator_render_service.py:102).
    """
    from output.renderers.alert.model import AlertMessage, OnsetEvent

    kwargs = dict(
        onset_minutes=8, onset_time="14:08", km_from=km_from, km_to=km_to,
        is_convective=convective, intensity_label="kraeftiger Regen",
        source_label="Radar (GeoSphere INCA)",
        briefing_context="nicht angekuendigt",
    )
    if segment_id != "__omit__":
        kwargs["segment_id"] = segment_id
    try:
        event = OnsetEvent(**kwargs)
    except TypeError as exc:  # RED-Vertrag Punkt 1
        raise AssertionError(
            "OnsetEvent traegt keine Segment-Kennung — der Nowcast kann den Ort "
            "deshalb nur als km-Spanne nennen (model.py:31, Spec #1744 AC-1). "
            f"Urspruenglicher Fehler: {exc}"
        ) from exc
    return AlertMessage(
        trip_short=TRIP_NAME, stand_at="10:00", events=(event,),
        source="radar", cooldown_display="60 Min",
    )


def _trip(waypoint_count: int = 10):
    """Trip mit `waypoint_count` Wegpunkten -> Segmente '1'..'N-1' + 'Ziel'
    (`_trip_total_segment_ids`, official_alerts.py:1923). Zehn Wegpunkte sorgen
    dafuer, dass keine der geprueften Warnungen die GESAMTE Route abdeckt —
    sonst greift der Sonderfall 'gesamte Route' statt der Segment-Kennung."""
    from app.trip import Stage, Trip, Waypoint

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i / 100, lon=12.9 + i / 100,
                 elevation_m=1900.0 + i)
        for i in range(waypoint_count)
    ]
    stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 1), waypoints=waypoints)
    return Trip(id="tdd-1744-khw", name=TRIP_NAME, stages=[stage])


def _official_subject(segment_ids: list[str]) -> str:
    """Betreff der amtlichen Warnung ueber genau den Produktivweg:
    `build_official_alert_notices()` -> `render_official_alert_subject()`
    (notification_service.py:823/828)."""
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_subject,
    )
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Kaernten",
    )
    notices = build_official_alert_notices(_trip(), [(alert, segment_ids)])
    return render_official_alert_subject(notices, prefix=TRIP_NAME, tz=TRIP_TZ)


def _location_slot(subject: str) -> str:
    """Die Ortsangabe aus einem Alarm-Betreff."""
    match = _SUBJECT_RE.match(subject)
    assert match, f"Betreff hat nicht die Bauform '[Trip] <Ort> · <Kern>': {subject!r}"
    return match.group("where")


def _wo_und_wann(plain: str) -> str:
    """Wert der Datenzeile 'Wo & wann' aus dem Text-Teil einer Alarm-Mail."""
    hits = [ln for ln in plain.splitlines() if ln.startswith("Wo & wann: ")]
    assert len(hits) == 1, f"Genau eine 'Wo & wann'-Zeile erwartet, gefunden: {hits!r}"
    return hits[0][len("Wo & wann: "):]


def _wo_ort(plain: str) -> str:
    """Nur der ORT aus der 'Wo & wann'-Zeile (vor dem ersten ' · ' steht der
    Ort, dahinter die Zeit — render.py:379-382 bzw. :233)."""
    return _wo_und_wann(plain).split(" · ")[0]


# ---------------------------------------------------------------------------
# AC-1 — Nowcast und amtliche Warnung nennen dasselbe Ziel-Segment gleich
# ---------------------------------------------------------------------------

def test_nowcast_und_amtliche_warnung_nennen_das_ziel_segment_gleich():
    """AC-1: Given ein Trip-Nowcast-Alarm fuer das Ziel-Segment / When die
    Alarm-Mail versendet wird / Then nennt die Betreffzeile '🏁 Ziel' statt
    'km 8–8', und der Betreff einer amtlichen Warnung fuer DASSELBE Segment
    nennt denselben Text.

    Zwei Zusicherungen, absichtlich beide: die Gleichheit faengt „nur ein Pfad
    umgestellt"; der Literalwert legt die RICHTUNG fest — der Nowcast
    uebernimmt die Sprache der amtlichen Warnung, nicht umgekehrt. Ohne den
    Literal waere auch „beide auf km umgestellt" gruen.

    HEUTE ROT: Nowcast sagt 'km 8–8' (render.py:110), amtliche Warnung
    '🏁 Ziel' (official_alerts.py:290).
    """
    from output.renderers.alert.render import render_subject

    nowcast = _location_slot(render_subject(_onset_message(segment_id="Ziel")))
    official = _location_slot(_official_subject(["Ziel"]))

    assert nowcast == official, (
        "Nowcast und amtliche Warnung nennen denselben Ort verschieden: "
        f"{nowcast!r} vs. {official!r}"
    )
    assert nowcast == "🏁 Ziel", (
        f"Ortsangabe folgt nicht der Segment-Sprache: {nowcast!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Abweichungsalarm ueber drei Segmente
# ---------------------------------------------------------------------------

def test_abweichungsalarm_ueber_drei_segmente_nennt_sie_wie_die_amtliche_warnung():
    """AC-2: Given ein Trip-Abweichungsalarm, der die Segmente 3, 4 und 5
    betrifft / When der Betreff gerendert wird / Then steht dort 'Segment 3–5'
    — dieselbe Zusammenfassung, die eine amtliche Warnung ueber dieselben drei
    Segmente erzeugt.

    HEUTE ROT: der Abweichungsalarm sagt 'km 4–10' (render.py:100-107), die
    amtliche Warnung 'Segment 3–5'.
    """
    from output.renderers.alert.render import render_subject

    msg = _delta_message([("3", 4.0, 6.0), ("4", 6.0, 8.0), ("5", 8.0, 10.0)])
    delta = _location_slot(render_subject(msg))
    official = _location_slot(_official_subject(["3", "4", "5"]))

    assert delta == official, (
        "Abweichungsalarm und amtliche Warnung fassen dieselben Segmente "
        f"verschieden zusammen: {delta!r} vs. {official!r}"
    )
    assert delta == "Segment 3–5", (
        f"Ortsangabe folgt nicht der Segment-Sprache: {delta!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Teilungs-Nachweis: genau EINE Ortsformatierung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("segment_id,erwartet", [
    ("3", "Segment 3"),
    ("7", "Segment 7"),
    ("Ziel", "🏁 Ziel"),
])
def test_alle_drei_alarmarten_bilden_denselben_ortstext(segment_id, erwartet):
    """AC-3 (Teilungs-Nachweis): Given irgendein Trip-Alarm mit Ortsangabe /
    When die Ortsangabe gebildet wird / Then geschieht das ueber GENAU EINE
    Funktion.

    Dieser Test rendert alle drei Alarmarten fuer DIESELBE Segment-Kennung und
    prueft sie gegeneinander UND gegen den erwarteten Wortlaut.

    MUTATION, die diesen Test rot machen MUSS (Mutations-Gegenprobe):
    in der gemeinsamen Ortsformatierung 'Segment' -> 'Etappe' (heute
    `format_segment_reference`, official_alerts.py:283/285) — dann muessen
    Nowcast-, Abweichungs- UND Amtliche-Warnung-Zusicherung GLEICHZEITIG
    fallen. Bleibt eine gruen, existiert eine zweite Formatierung; das ist ein
    Verstoss gegen die Teilungsregel, kein Detail.

    HEUTE ROT: Nowcast und Abweichungsalarm sprechen km, die amtliche Warnung
    spricht Segmente.
    """
    from output.renderers.alert.render import render_subject

    nowcast = _location_slot(render_subject(_onset_message(segment_id=segment_id)))
    delta = _location_slot(render_subject(_delta_message([(segment_id, 4.0, 6.0)])))
    official = _location_slot(_official_subject([segment_id]))

    assert nowcast == erwartet, f"Nowcast-Ortsangabe: {nowcast!r}"
    assert delta == erwartet, f"Abweichungs-Ortsangabe: {delta!r}"
    assert official == erwartet, f"Amtliche-Warnung-Ortsangabe: {official!r}"


@pytest.mark.parametrize("segment_ids,erwartet", [
    (["3", "4", "5"], "Segment 3–5"),          # zusammenhaengend -> Range
    (["3", "5"], "Segment 3, 5"),              # Luecke -> Aufzaehlung
    (["2", "Ziel"], "Segment 2, 🏁 Ziel"),     # Ziel nie in die Range mischen
    (["1", "3", "5", "7", "9"], "5 Segmente"),  # >4 -> Verdichtung
])
def test_abweichungsalarm_folgt_denselben_verdichtungsregeln(segment_ids, erwartet):
    """AC-3 (Teilungs-Nachweis, Kanten): Range-Verdichtung, Aufzaehlung,
    Ziel-Sonderfall und die '>4 Segmente'-Verdichtung sind vier Regeln, die
    eine handgeschriebene Zweitfassung im Abweichungspfad mit hoher
    Wahrscheinlichkeit NICHT gleich reproduziert. Genau deshalb stehen sie
    hier: sie unterscheiden „geteilt" von „nachgebaut".

    HEUTE ROT: der Abweichungsalarm sagt in allen vier Faellen 'km a–b'.
    """
    from output.renderers.alert.render import render_subject

    specs = [(sid, 2.0 * n, 2.0 * n + 2.0) for n, sid in enumerate(segment_ids, 1)]
    delta = _location_slot(render_subject(_delta_message(specs)))
    official = _location_slot(_official_subject(segment_ids))

    assert delta == official, (
        f"Abweichungsalarm {delta!r} != amtliche Warnung {official!r} "
        f"fuer Segmente {segment_ids}"
    )
    assert delta == erwartet, f"Ortsangabe: {delta!r}"


# ---------------------------------------------------------------------------
# AC-4 — Ortsvergleich unveraendert (HEUTE GRUEN, Invariante)
# ---------------------------------------------------------------------------

def _saved_location(loc_id: str, name: str, lat: float, lon: float):
    from app.user import SavedLocation

    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=20)


def test_ortsvergleich_aenderungsalarm_nennt_weiterhin_den_ortsnamen():
    """AC-4 (HEUTE GRUEN, Invariante): Given ein Aenderungsalarm im
    Ortsvergleich mit einem Ort / When Betreff, Mail und Telegram gerendert
    werden / Then erscheint weiterhin der Ortsname — die Segment-Kennung greift
    dort nicht (ein Vergleichs-Ort hat keine Etappen).

    Die Erwartungen sind der HEUTIGE Wortlaut, byte-genau. Sie duerfen sich
    durch #1744 nicht bewegen; `location_label` bleibt die erste Stufe der
    Aufloesungsreihenfolge.
    """
    from output.renderers.alert.project import to_point_alert_message
    from output.renderers.alert.render import (
        render_email, render_subject, render_telegram,
    )

    msg = to_point_alert_message(
        [_change("1")], [_saved_location("toulon", "Toulon", 43.12, 5.93)],
        "Toulon", tz=ZoneInfo("Europe/Paris"), stand_at="10:00",
    )

    assert render_subject(msg) == "[Toulon] Toulon · ↑ Böen: 50 km/h→80 km/h"
    assert render_telegram(msg).splitlines()[0] == "<b>Toulon · Toulon · ↑ Böen</b>"
    assert _wo_und_wann(render_email(msg)[1]) == "Toulon · 16:00"


def test_ortsvergleich_mehrere_orte_nennen_weiterhin_ihre_namen():
    """AC-4 (HEUTE GRUEN, Invariante): derselbe Nachweis fuer den gebuendelten
    Mehr-Orte-Alarm (`to_multi_point_alert_message`, #1170)."""
    from output.renderers.alert.project import to_multi_point_alert_message
    from output.renderers.alert.render import render_subject, render_telegram

    msg = to_multi_point_alert_message(
        [
            ("Toulon", [_change("1")], _saved_location("toulon", "Toulon", 43.12, 5.93)),
            ("Hyères", [_change("1", old=40.0, new=70.0)],
             _saved_location("hyeres", "Hyères", 43.12, 6.13)),
        ],
        tz=ZoneInfo("Europe/Paris"), stand_at="10:00",
    )

    assert render_subject(msg) == (
        "[Toulon, Hyères] Toulon, Hyères · ↑ 2 über Schwelle: Böen 80, Böen 70"
    )
    assert render_telegram(msg).splitlines()[0] == (
        "<b>Toulon, Hyères · Toulon, Hyères · 2 über Schwelle</b>"
    )


def test_ortsvergleich_radaralarm_bleibt_unveraendert():
    """AC-4 (HEUTE GRUEN, Invariante): der Radar-Alarm des Ortsvergleichs hat
    keine Segmente (`km_from=km_to=0.0`, project.py:308) und traegt den
    Ortsnamen im Trip-Slot. Sein Betreff nennt heute 'km 0–0'; das ist
    Bestandsverhalten und NICHT Gegenstand von #1744 — der Test bewacht, dass
    die neue Segment-Sprache hier weder auftaucht noch etwas abstuerzen laesst.
    """
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from output.renderers.alert.render import render_subject
    from services.radar_service import NowcastResult

    def _nc():
        return NowcastResult(onset_minutes=30, intensity_label="leichter Regen",
                             source="Radar (AROME-FR)", is_convective=False)

    single = to_multi_location_onset_alert_message(
        [("Toulon", _saved_location("toulon", "Toulon", 43.12, 5.93), _nc())],
        tz=ZoneInfo("Europe/Paris"), stand_at="10:00",
    )
    multi = to_multi_location_onset_alert_message(
        [
            ("Toulon", _saved_location("toulon", "Toulon", 43.12, 5.93), _nc()),
            ("Hyères", _saved_location("hyeres", "Hyères", 43.12, 6.13), _nc()),
        ],
        tz=ZoneInfo("Europe/Paris"), stand_at="10:00",
    )

    assert render_subject(single) == "[Toulon] km 0–0 · Regen in 30 Min"
    assert render_subject(multi) == "[Toulon, Hyères] Regen-Alarm: 2 Orte"


# ---------------------------------------------------------------------------
# AC-3/AC-4 — die RANGFOLGE selbst, nicht nur ihre heutigen Auswirkungen
# ---------------------------------------------------------------------------

def test_ortsname_schlaegt_die_segment_kennung():
    """Die Aufloesungsreihenfolge lautet `location_label` -> Segment -> km.
    Dieser Test prueft die ERSTE Stufe an der Stelle, an der sie WIRKT.

    Warum er noetig ist (Adversary-Befund F002, 2026-08-12): vertauscht man in
    `segments.format_alert_location` die beiden ersten Stufen, wird KEIN
    anderer Test rot — weil heute kein einziger Aufrufer beide Felder
    gleichzeitig setzt (`to_alert_message` setzt nur die Segment-Kennung,
    `to_multi_point_alert_message` nur den Ortsnamen). Die Regel stand damit im
    Code und in der Spec, war aber unbewacht: eine Verfaelschung waere durch
    alle 24 Zusicherungen dieser Datei hindurchgelaufen.

    Die Kombination ist deshalb bewusst am Renderer-Modell gebaut und nicht
    ueber eine Projektion — es GIBT heute keine, die sie erzeugt. Genau das ist
    die Luecke: die Rangfolge entscheidet erst, wenn ein kuenftiger Aufrufer
    beides mitgibt (z.B. ein Vergleichs-Ort mit Etappenbezug). Bis dahin haelt
    dieser Test die Entscheidung fest, statt sie dem Zufall der naechsten
    Erweiterung zu ueberlassen.
    """
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_email, render_subject

    event = AlertEvent(
        metric_id="gust", value_from=50.0, value_to=80.0, threshold=20.0,
        cmp="über", occurred_at="16:00", km_from=4.0, km_to=6.0,
        location_label="Toulon", segment_id="3",
    )
    msg = AlertMessage(
        trip_short="Toulon", stand_at="10:00", events=(event,),
        location_label="Toulon",
    )

    assert _location_slot(render_subject(msg)) == "Toulon", (
        "Segment-Kennung verdraengt den Ortsnamen im Betreff — Stufe 1 der "
        "Aufloesungsreihenfolge greift nicht"
    )
    assert _wo_ort(render_email(msg)[1]) == "Toulon", (
        "Segment-Kennung verdraengt den Ortsnamen im Mailkoerper"
    )


# ---------------------------------------------------------------------------
# AC-5 — Kurznachricht nennt keinen Ort und bleibt <= 140 Zeichen
# ---------------------------------------------------------------------------

def _assert_kurznachricht_ohne_ort(sms: str) -> None:
    """PO-Entscheid 2026-08-04 (#1467 S2 AG3b): Alarm-Kurznachrichten nennen
    keinen Ort. SMS und Premium-SMS teilen denselben gerenderten Text
    (`render_alert_sms`, notification_service.py:1318 -> :1488 SMS / :1502
    Premium-SMS) — ein Nachweis deckt beide Kanaele.
    """
    assert "Segment" not in sms, f"Kurznachricht nennt ein Segment: {sms!r}"
    assert "Ziel" not in sms, f"Kurznachricht nennt das Ziel: {sms!r}"
    assert "🏁" not in sms, f"Kurznachricht traegt das Ziel-Symbol: {sms!r}"
    assert re.search(r"km\d", sms), (
        f"Kurznachricht hat ihren km-Kopf verloren: {sms!r}"
    )
    # Alarm-Grenze ist 140, NICHT 160 (render.py:285/621, official_alerts.py:1836).
    assert len(sms) <= 140, f"Kurznachricht ist {len(sms)} Zeichen lang: {sms!r}"


def test_kurznachricht_des_abweichungsalarms_nennt_keinen_ort():
    """AC-5 (HEUTE GRUEN, Invariante): Given ein Trip-Abweichungsalarm auf dem
    Ziel-Segment / When die Kurznachricht gerendert wird / Then nennt sie
    weiterhin keinen Ortsnamen und bleibt <= 140 Zeichen.

    Der Alarm laeuft ueber `to_alert_message()` mit einer echten Etappe
    `segment_id='Ziel'` — also genau der Eingabe, aus der der BETREFF nach
    AC-1 kuenftig '🏁 Ziel' bildet. Der Test bewacht, dass diese Umstellung
    NICHT in die Kurznachricht durchschlaegt.
    """
    from output.renderers.alert.render import render_sms

    _assert_kurznachricht_ohne_ort(render_sms(_delta_message([("Ziel", 8.0, 8.0)])))


def test_kurznachricht_des_abweichungsalarms_ueber_mehrere_segmente_nennt_keinen_ort():
    """AC-5 (HEUTE GRUEN, Invariante): dieselbe Zusicherung fuer den
    Mehr-Segment-Fall aus AC-2 ('Segment 3–5' im Betreff)."""
    from output.renderers.alert.render import render_sms

    msg = _delta_message([("3", 4.0, 6.0), ("4", 6.0, 8.0), ("5", 8.0, 10.0)])
    _assert_kurznachricht_ohne_ort(render_sms(msg))


def test_kurznachricht_des_nowcasts_nennt_keinen_ort():
    """AC-5: dieselbe Zusicherung fuer den Radar-Nowcast.

    ROT bis der RED-Vertrag Punkt 1 erfuellt ist (`OnsetEvent.segment_id`):
    ohne das Feld laesst sich der Fall „Nowcast KENNT das Ziel-Segment" gar
    nicht herstellen. Danach ist es eine reine Invariante — der Betreff wechselt
    auf '🏁 Ziel', die Kurznachricht bleibt bei 'km8-8'.
    """
    from output.renderers.alert.render import render_sms

    _assert_kurznachricht_ohne_ort(render_sms(_onset_message(segment_id="Ziel")))


# ---------------------------------------------------------------------------
# AC-6 — eine Mail, eine Ortssprache
# ---------------------------------------------------------------------------

def test_nowcast_mail_nennt_im_koerper_denselben_ort_wie_im_betreff():
    """AC-6: Given eine Alarm-Mail mit Ortsangabe im Betreff / When der
    Mail-Koerper gerendert wird / Then nennt die Zeile 'Wo & wann' DENSELBEN
    Ortstext wie der Betreff.

    Erst Gleichheit (faengt „Betreff umgestellt, Koerper vergessen"), dann der
    Wortlaut (faengt „beide noch auf km"). Zusaetzlich muss der Ort auch im
    HTML-Teil stehen — zugestellt wird beides.

    HEUTE ROT im zweiten Schritt: Betreff und Koerper sagen einvernehmlich
    'km 8–8'.
    """
    from output.renderers.alert.render import render_email, render_subject

    msg = _onset_message(segment_id="Ziel")
    html, plain = render_email(msg)
    im_betreff = _location_slot(render_subject(msg))
    im_koerper = _wo_ort(plain)

    assert im_koerper == im_betreff, (
        f"Betreff sagt {im_betreff!r}, Mailkoerper sagt {im_koerper!r}"
    )
    assert im_betreff == "🏁 Ziel", f"Ortsangabe: {im_betreff!r}"
    assert im_betreff in html, "Ortsangabe fehlt im HTML-Teil der Mail"


def test_abweichungsmail_nennt_im_koerper_denselben_ort_wie_im_betreff():
    """AC-6: derselbe Nachweis fuer die Abweichungsmail (Ein-Metrik-Fall — nur
    der traegt eine 'Wo & wann'-Zeile, render.py:361-383)."""
    from output.renderers.alert.render import render_email, render_subject

    msg = _delta_message([("3", 4.0, 6.0)])
    html, plain = render_email(msg)
    im_betreff = _location_slot(render_subject(msg))
    im_koerper = _wo_ort(plain)

    assert im_koerper == im_betreff, (
        f"Betreff sagt {im_betreff!r}, Mailkoerper sagt {im_koerper!r}"
    )
    assert im_betreff == "Segment 3", f"Ortsangabe: {im_betreff!r}"
    assert im_betreff in html, "Ortsangabe fehlt im HTML-Teil der Mail"


# ---------------------------------------------------------------------------
# AC-7 — Rueckfall auf km, wenn keine Segment-Kennung vorliegt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("segment_id", [None, ""])
def test_etappe_ohne_segment_kennung_faellt_auf_km_zurueck(segment_id):
    """AC-7 (HEUTE GRUEN, Invariante gegen den Fix): Given ein Trip-Alarm,
    dessen Etappe keine Segment-Kennung traegt (Altdaten) / When die Ortsangabe
    gebildet wird / Then faellt sie auf die km-Spanne zurueck, statt leer zu
    bleiben oder den Versand abzubrechen.

    `WeatherChange.segment_id` hat den Default '' (models.py:541), gespeicherte
    Altdaten koennen also ohne Kennung ankommen. Die dritte Stufe der
    Aufloesungsreihenfolge muss das auffangen: ein ungeprueftes
    `format_segment_reference([None])` wuerde werfen bzw. 'Segment None'
    liefern — beides faengt dieser Test.
    """
    from output.renderers.alert.render import render_email, render_subject

    msg = _delta_message([(segment_id, 12.0, 20.0)])
    ort = _location_slot(render_subject(msg))

    assert ort == "km 12–20", f"Kein km-Rueckfall ohne Segment-Kennung: {ort!r}"
    assert _wo_ort(render_email(msg)[1]) == "km 12–20"


def test_nowcast_ohne_segment_kennung_faellt_auf_km_zurueck():
    """AC-7 (HEUTE GRUEN, Invariante gegen den Fix): dasselbe fuer die
    Nowcast-Bestandsaufrufer, die kein `OnsetEvent.segment_id` setzen
    (radar_alert_service.py:59, validator_render_service.py:102). Sie duerfen
    durch den Fix weder leer laufen noch abstuerzen."""
    from output.renderers.alert.render import render_subject

    ort = _location_slot(render_subject(_onset_message(km_from=8.0, km_to=12.0)))

    assert ort == "km 8–12", f"Kein km-Rueckfall ohne Segment-Kennung: {ort!r}"
