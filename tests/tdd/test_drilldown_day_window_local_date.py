"""TDD RED — "heute" und "morgen" im Drilldown folgen der ORTSzeit der Tour.

Issue #1470 (PO-Entscheidung 2026-08-03: "Ja, Ortszeit."). Nebenbefund aus
#1465: seit der Absturz weg ist, ist das Tagesfenster in sich stimmig — aber
um die Zeitzonendifferenz verschoben. Beide Zweige haengen an der Weltzeit:

* **"morgen"** beginnt an der Weltzeit-Mitternacht. Auf Korsika (UTC+2 im
  Sommer) zeigt die Liste das Fenster 02:00–02:00 ORTSzeit: die ersten zwei
  Stunden des Tages fehlen, dafuer sind zwei Stunden des Vortages dabei.
* **"heute"** traegt das UTC-DATUM (``received_at.date()``). Zwischen
  Ortsmitternacht und Weltzeit-Mitternacht — auf Korsika 00:00–02:00 Ortszeit
  — steht in der Stunden-Tabelle deshalb das Datum von GESTERN.

Die Erwartungen hier sind bewusst NICHT aus dem Prueflingsweg gebildet,
sondern aus der Ortszone der Tour (``Europe/Paris``) und einem festen
Zeitstempel. Drei Kalender sind unterscheidbar, und genau das ist der Sinn
des Aufbaus:

===========================  ==================  =====================
Kalender                     "morgen" beginnt    "heute" am 22:30 UTC
===========================  ==================  =====================
Weltzeit (Fehlerbild heute)  02:00 Ortszeit      20.08. (Vortag!)
Prozess-Zone (conftest.py,   04:30 Ortszeit      20.08. (Vortag!)
America/St_Johns, -2:30)     (Halbstunden-Rest)
Ortszeit der Tour (Soll)     00:00 Ortszeit      21.08.
===========================  ==================  =====================

Der Halbstunden-Versatz der Prozess-Zone stammt aus ``conftest.py`` und wird
hier AUSGENUTZT statt vorausgesetzt: eine Umstellung auf die Prozess-Zone
statt auf die Ortszone faellt an der Uhrzeit ``04:30`` sofort auf.

Kein Mock: echter Trip, echter Snapshot ueber ``WeatherSnapshotService``,
echte Callback-Aufloesung des Empfaengers, echter ``TripCommandProcessor``.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.inbound_telegram_reader import InboundTelegramReader
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_snapshot import WeatherSnapshotService

# Korsika -> Europe/Paris, im August CEST (UTC+2). Nur so unterscheiden sich
# Ortszeit, Weltzeit und Prozess-Zone voneinander.
_WP_LAT, _WP_LON = 42.1, 9.0
_TRIP_TZ = ZoneInfo("Europe/Paris")

_TRIP_ID = "drilldown-tagesfenster"
_TRIP_NAME = "Tagesfenster-Tour"
_USER_ID = "default"

# Fester Ausgangstag. Die Etappen decken drei Tage ab, damit `_display_tz`
# fuer JEDEN geprueften Tag eine echte Etappe findet (und nicht ueber den
# Rueckfall "erste Etappe mit Wegpunkt" laeuft).
_DAY0 = date(2026, 8, 20)

# Vormittag: Ortszeit-Datum == UTC-Datum. Damit haengt Test 1 allein an der
# FENSTERGRENZE, nicht zusaetzlich am Datumswechsel.
_MIDDAY_UTC = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)

# 22:30 UTC am 20.08. == 00:30 Ortszeit am 21.08.: nach der ORTSmitternacht,
# aber noch vor der Weltzeit-Mitternacht. Genau das Fenster, in dem "heute"
# heute den Vortag zeigt.
_AFTER_LOCAL_MIDNIGHT_UTC = datetime(2026, 8, 20, 22, 30, tzinfo=timezone.utc)


def _trip(day0: date = None) -> Trip:
    day0 = day0 or _DAY0
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id=f"S{i}",
                name=f"Etappe {i}",
                date=day0 + timedelta(days=i),
                waypoints=[
                    Waypoint(
                        id=f"W{i}", name=f"Vizzavona {i}",
                        lat=_WP_LAT, lon=_WP_LON, elevation_m=900,
                    ),
                ],
            )
            for i in range(3)
        ],
    )


def _rain_at(ts: datetime, start: datetime) -> float:
    """Regenwert des Stundenpunkts ``ts`` — Fingerabdruck, kein Zierwert.

    Adversary-Fund F001: Tests, die nur die BESCHRIFTUNG ``00..23`` pruefen,
    bleiben gruen, wenn Fenster UND Beschriftung gemeinsam um denselben
    Betrag verrutschen (z.B. beides in Weltzeit) — die Spalte liest sich dann
    unveraendert, zeigt aber die Daten einer anderen Stunde. Deshalb ist der
    Regenwert ueber die GESAMTE Reihe eindeutig (0.0, 0.1, ... 6.0): jede
    Zeile verraet, WELCHEN Zeitpunkt sie in Wahrheit zeigt.
    """
    return round(0.1 * ((ts - start).total_seconds() / 3600), 1)


def _segments(
    start: datetime = datetime(2026, 8, 20, 6, 0), span: int = 61,
) -> list[SegmentWeatherData]:
    """Luekenlose Stundenpunkte ab ``start`` (naive UTC), ``span`` Stueck.

    Naive UTC-Zeitstempel per Hausnorm (#1345) — ``ForecastDataPoint`` zieht
    sie ohnehin dorthin. Der Bereich ist absichtlich viel groesser als jedes
    geprueften Fenster: WELCHE Stunden in der Antwort landen, entscheidet
    dadurch allein die Fenstergrenze des Prueflings, nicht die Datenlage.
    """
    thunder_seq = [ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH]
    points = [
        ForecastDataPoint(
            ts=start + timedelta(hours=i),
            t2m_c=10.0 + (i % 12),
            wind10m_kmh=float(20 + (i % 7)),
            precip_1h_mm=_rain_at(start + timedelta(hours=i), start),
            thunder_level=thunder_seq[i % len(thunder_seq)],
        )
        for i in range(span)
    ]
    segment = TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=_WP_LAT, lon=_WP_LON, elevation_m=900),
        end_point=GPXPoint(lat=_WP_LAT + 0.1, lon=_WP_LON + 0.1, elevation_m=600),
        start_time=start,
        end_time=start + timedelta(hours=span - 1),
        duration_hours=float(span - 1),
        distance_km=15.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.OPENMETEO, model="test", grid_res_km=0.0,
                ),
                data=points,
            ),
            aggregated=SegmentWeatherSummary(
                thunder_level_max=ThunderLevel.HIGH,
                wind_max_kmh=31.0,
                precip_sum_mm=3.3,
            ),
            fetched_at=start,
            provider=Provider.OPENMETEO.value,
        )
    ]


@pytest.fixture
def make_env(tmp_path: Path, monkeypatch):
    """Baut Trip + Snapshot fuer einen frei waehlbaren Zeitraum."""
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    def _make(day0: date, start: datetime, span: int, trip: Trip = None) -> datetime:
        save_trip(trip or _trip(day0), _USER_ID)
        WeatherSnapshotService(_USER_ID).save(
            _TRIP_ID, _segments(start, span), day0
        )
        return start

    return _make


@pytest.fixture
def env(make_env) -> None:
    make_env(_DAY0, datetime(2026, 8, 20, 6, 0), 61)


def _press(callback_data: str, received_at: datetime) -> CommandResult:
    """Knopfdruck -> Antwort, ueber die ECHTE Callback-Aufloesung des Empfaengers."""
    body = InboundTelegramReader()._callback_to_body(callback_data)
    assert body is not None, f"Knopf {callback_data!r} ist beim Empfaenger unbekannt"
    msg = InboundMessage(
        channel="telegram",
        trip_name=_TRIP_NAME,
        body=body,
        sender="4711",
        received_at=received_at,
        user_id=_USER_ID,
    )
    result = TripCommandProcessor().process(msg)
    assert result.success is True, (
        f"{callback_data}: keine Antwort — {result.confirmation_body!r}"
    )
    return result


def _list_times(body: str) -> list[str]:
    """Uhrzeiten der Einzelmetrik-Liste (``HH:MM  Wert``)."""
    return re.findall(r"^(\d{2}:\d{2})\s", body, flags=re.MULTILINE)


def _table_hours(body: str) -> list[str]:
    """Stundenspalte der Kompakttabelle (``HH  18°C ...``)."""
    return re.findall(r"^(\d{2})\s\s", body, flags=re.MULTILINE)


def _list_rows(body: str) -> list[tuple[str, float]]:
    """Einzelmetrik-Liste als ``(Ortszeit, Regenwert)`` — Zeit UND Wert.

    Adversary-Fund F001: die Zeitspalte allein ist blind gegen eine
    Verschiebung, die Fenster und Beschriftung gemeinsam betrifft.
    """
    return [
        (t, float(v))
        for t, v in re.findall(
            r"^(\d{2}:\d{2})\s+([\d.]+) mm", body, flags=re.MULTILINE
        )
    ]


def _table_rows(body: str) -> list[tuple[str, float]]:
    """Kompakttabelle als ``(Ortsstunde, Regenwert)``."""
    return [
        (h, float(v))
        for h, v in re.findall(
            r"^(\d{2})\s\s.*?([\d.]+)mm", body, flags=re.MULTILINE
        )
    ]


def _expected_rows(
    start_utc: datetime, count: int, data_start: datetime, tz=_TRIP_TZ,
) -> list[tuple[str, float]]:
    """Sollzeilen ab dem UTC-Zeitpunkt ``start_utc`` — Zeit UND Wert.

    Beide unabhaengig vom Prueflingsweg gebildet: die Beschriftung aus der
    Zone, der Wert aus derselben Formel wie die Testdaten.
    """
    rows = []
    for i in range(count):
        ts = start_utc + timedelta(hours=i)
        rows.append((
            ts.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%H"),
            _rain_at(ts, data_start),
        ))
    return rows


# ---------------------------------------------------------------------------
# 1) "morgen" beginnt an der ORTSmitternacht
# ---------------------------------------------------------------------------

def test_tomorrow_window_starts_at_local_midnight(env):
    """
    GIVEN eine Tour auf Korsika (Europe/Paris, im August UTC+2) und einen
          luekenlosen Stundensatz ueber drei Tage,
    WHEN  der Nutzer vormittags den Regen-Drilldown fuer MORGEN oeffnet,
    THEN  zeigt die erste Zeile 00:00 Ortszeit UND den Messwert genau dieser
          Stunde (1.6 mm, der Punkt von 22:00 UTC) — nicht 02:00/1.8 mm
          (Weltzeit-Mitternacht) und nicht 04:30 (Prozess-Zone).

    Die Zeile haengt bewusst am WERT: eine Verschiebung, die Fenster und
    Beschriftung gemeinsam trifft, laesst die Zeitspalte unveraendert
    aussehen (Adversary-Fund F001).
    """
    data_start = datetime(2026, 8, 20, 6, 0)
    body = _press("dd_precip_tomorrow", _MIDDAY_UTC).confirmation_body
    rows = [(t, v) for t, v in re.findall(
        r"^(\d{2}:\d{2})\s+([\d.]+) mm", body, flags=re.MULTILINE)]
    rows = [(t, float(v)) for t, v in rows]
    assert rows, f"Keine Stundenzeilen in der Morgen-Liste:\n{body}"

    local_midnight_utc = datetime(2026, 8, 20, 22, 0)      # = 21.08. 00:00 CEST
    utc_midnight = datetime(2026, 8, 21, 0, 0)             # Fehlerbild vorher
    assert rows[0] == ("00:00", _rain_at(local_midnight_utc, data_start)), (
        "Die erste Zeile ist nicht die ORTSmitternacht.\n"
        f"  gesehen:   {rows[0][0]} / {rows[0][1]} mm\n"
        f"  erwartet:  00:00 / {_rain_at(local_midnight_utc, data_start)} mm "
        f"(Punkt {local_midnight_utc:%d.%m. %H:%M} UTC)\n"
        f"  Weltzeit-Mitternacht waere {utc_midnight:%d.%m. %H:%M} UTC = "
        f"{_rain_at(utc_midnight, data_start)} mm\n"
        f"  Liste: {rows[:4]}"
    )
    # Das Fenster endet an der NAECHSTEN Ortsmitternacht. Die Daten reichen
    # weit darueber hinaus (bis 22.08. 18:00 UTC), die Grenze kommt also vom
    # Pruefling und nicht von der Datenlage.
    last_utc = local_midnight_utc + timedelta(hours=23)
    assert rows[-1] == ("23:00", _rain_at(last_utc, data_start)), (
        "Die letzte Zeile ist nicht die Stunde vor der naechsten "
        f"ORTSmitternacht.\n  gesehen:  {rows[-1]}\n"
        f"  erwartet: ('23:00', {_rain_at(last_utc, data_start)})\n"
        f"  Liste: {rows}"
    )


def test_tomorrow_window_covers_the_full_local_day(env):
    """
    GIVEN dieselbe Tour,
    WHEN  der Nutzer die Stunden-Tabelle fuer MORGEN oeffnet,
    THEN  stehen dort die 24 ORTSstunden 00..23 des Folgetages — vollstaendig
          und in Ortszeit, kein abgeschnittener Tagesanfang.
    """
    data_start = datetime(2026, 8, 20, 6, 0)
    body = _press("dd_hours_tomorrow", _MIDDAY_UTC).confirmation_body
    rows = _table_rows(body)
    expected = _expected_rows(datetime(2026, 8, 20, 22, 0), 24, data_start)
    assert rows == expected, (
        "Die Morgen-Tabelle deckt nicht den ORTS-Tag 00..23 mit den Werten "
        "genau dieser Stunden ab.\n"
        f"  gesehen:   {rows}\n"
        f"  erwartet:  {expected}\n{body}"
    )


# ---------------------------------------------------------------------------
# 1b) Sommerzeit-Wechsel: der Ortstag hat 23 bzw. 25 Stunden
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "day0, press_utc, data_start, local_hours, missing, doubled",
    [
        # Rueckstellung: 25.10. hat 25 Ortsstunden, 02:00 kommt ZWEIMAL.
        # Ortsmitternacht 24.10. 22:00 UTC -> naechste 25.10. 23:00 UTC.
        pytest.param(
            date(2026, 10, 24), datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 24, 6, 0), 25, None, "02",
            id="rueckstellung-25-stunden",
        ),
        # Vorstellung: 29.03. hat 23 Ortsstunden, 02:00 existiert NICHT.
        # Ortsmitternacht 28.03. 23:00 UTC -> naechste 29.03. 22:00 UTC.
        pytest.param(
            date(2026, 3, 28), datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 28, 6, 0), 23, "02", None,
            id="vorstellung-23-stunden",
        ),
    ],
)
def test_tomorrow_window_matches_the_real_length_of_the_local_day(
    make_env, day0, press_utc, data_start, local_hours, missing, doubled,
):
    """
    GIVEN eine Tour auf Korsika am Vorabend einer Zeitumstellung,
    WHEN  der Nutzer die Stunden-Tabelle fuer MORGEN oeffnet,
    THEN  deckt sie GENAU den Ortstag ab — 25 Zeilen an der Rueckstellung
          (02:00 doppelt), 23 an der Vorstellung (02:00 existiert nicht).
          Keine fehlende, keine fremde Stunde.

    Adversary-Fund F002: ein festes ``hours=24`` liess an der Rueckstellung
    die Stunde 23 aus der Tabelle fallen und an der Vorstellung eine Zeile
    des Folgetages hereinbluten. Dieser Fehler entstand erst, als die
    Bezugsgroesse von Weltzeit auf Ortszeit wechselte — vorher war das
    Fenster sommerzeit-immun, weil es gar keinen Ortstag meinte.
    """
    make_env(day0, data_start, 80)
    body = _press("dd_hours_tomorrow", press_utc).confirmation_body
    hours = _table_hours(body)

    assert len(hours) == local_hours, (
        f"Der Ortstag {day0 + timedelta(days=1):%d.%m.%Y} hat {local_hours} "
        f"Stunden, die Tabelle zeigt {len(hours)} Zeilen.\n"
        f"  gesehen: {hours}\n{body}"
    )
    if doubled:
        assert hours.count(doubled) == 2, (
            f"An der Rueckstellung muss {doubled}:00 ZWEIMAL vorkommen "
            f"(gesehen {hours.count(doubled)}x).\n  {hours}"
        )
    if missing:
        assert missing not in hours, (
            f"An der Vorstellung gibt es keine {missing}:00 Ortszeit — die "
            f"Tabelle zeigt sie trotzdem.\n  {hours}"
        )
    # Vollstaendigkeit: jede uebrige Stunde des Ortstages genau einmal.
    for h in range(24):
        label = f"{h:02d}"
        if label == missing:
            continue
        expected_n = 2 if label == doubled else 1
        assert hours.count(label) == expected_n, (
            f"Stunde {label}:00 kommt {hours.count(label)}x vor, erwartet "
            f"{expected_n}x.\n  {hours}\n{body}"
        )


# ---------------------------------------------------------------------------
# 1c) Tour ueber mehrere Zonen: der Tageswechsel haengt an der HEUTIGEN
#     Etappe, nicht an der ersten der Tour
# ---------------------------------------------------------------------------

# Wellington und Vizzavona — zwoelf Stunden auseinander. Genau die Spanne,
# die den Anker sichtbar macht.
_WP_NZ = (-41.3, 174.8)


def _trip_two_zones(day0: date) -> Trip:
    """Etappe 0 in Neuseeland, ab Etappe 1 auf Korsika."""
    coords = [_WP_NZ, (_WP_LAT, _WP_LON), (_WP_LAT, _WP_LON)]
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id=f"S{i}", name=f"Etappe {i}", date=day0 + timedelta(days=i),
                waypoints=[
                    Waypoint(id=f"W{i}", name=f"WP{i}", lat=lat, lon=lon,
                             elevation_m=100),
                ],
            )
            for i, (lat, lon) in enumerate(coords)
        ],
    )


@pytest.mark.parametrize(
    "press_hour_utc, expected_local_day",
    [
        # Messprotokoll aus dem #1470-Bericht. Der Nutzer steht auf Korsika
        # (UTC+2); die Tour BEGANN in Neuseeland (UTC+12).
        pytest.param(9,  date(2026, 8, 21), id="11-uhr-ortszeit"),
        pytest.param(12, date(2026, 8, 21), id="14-uhr-ortszeit"),
        pytest.param(21, date(2026, 8, 21), id="23-uhr-ortszeit"),
        pytest.param(23, date(2026, 8, 22), id="01-uhr-ortszeit-folgetag"),
    ],
)
def test_day_boundary_follows_todays_stage_not_the_first_of_the_trip(
    make_env, press_hour_utc, expected_local_day,
):
    """
    GIVEN eine Tour, die in Neuseeland beginnt und deren heutige Etappe auf
          Korsika liegt,
    WHEN  der Nutzer die Stunden-Tabelle fuer HEUTE oeffnet,
    THEN  nennt die Kopfzeile den Tag, der AM ORT gilt — nicht den, der in
          der Startzone der Tour schon angebrochen ist.

    Adversary-Fund F003: mit dem Anker "erste Etappe der Tour" lag der
    Tageswechsel bei dieser Tour zehn Stunden falsch (12:00-22:00 UTC meldete
    bereits den Folgetag). Die vier Zeitpunkte stammen aus dem Messprotokoll;
    zwei davon (12:00 und 21:00) trennen alten und neuen Anker.
    """
    day0 = date(2026, 8, 20)
    make_env(day0, datetime(2026, 8, 21, 6, 0), 40, trip=_trip_two_zones(day0))
    press = datetime(2026, 8, 21, press_hour_utc, 0, tzinfo=timezone.utc)

    body = _press("dd_hours_today", press).confirmation_body
    local_now = press.astimezone(_TRIP_TZ)
    assert local_now.date() == expected_local_day, "Testaufbau kaputt"

    assert f"({expected_local_day:%d.%m})" in body, (
        "Die Kopfzeile nennt nicht den Tag, der am ORT gilt.\n"
        f"  Knopfdruck: {press:%d.%m. %H:%M} UTC = {local_now:%d.%m. %H:%M} "
        "Korsika\n"
        f"  erwartet:   ({expected_local_day:%d.%m})\n"
        f"  Kopfzeile:  {body.splitlines()[0]!r}\n"
        "  Hinweis: in der Startzone Neuseeland (UTC+12) waere es "
        f"{press.astimezone(ZoneInfo('Pacific/Auckland')):%d.%m. %H:%M}."
    )


# ---------------------------------------------------------------------------
# 2) "heute" traegt das ORTS-Datum
# ---------------------------------------------------------------------------

def test_today_after_local_midnight_shows_the_local_date(env):
    """
    GIVEN dieselbe Tour und einen Knopfdruck um 00:30 ORTSzeit (22:30 UTC am
          Vortag) — nach der Ortsmitternacht, vor der Weltzeit-Mitternacht,
    WHEN  der Nutzer die Stunden-Tabelle fuer HEUTE oeffnet,
    THEN  steht in der Ueberschrift der ORTS-Tag (21.08.) und nicht der
          Weltzeit-Tag (20.08.).
    """
    body = _press("dd_hours_today", _AFTER_LOCAL_MIDNIGHT_UTC).confirmation_body

    local_day = (_AFTER_LOCAL_MIDNIGHT_UTC.astimezone(_TRIP_TZ)).date()
    assert local_day == _DAY0 + timedelta(days=1), "Testaufbau kaputt"

    assert f"({local_day:%d.%m})" in body, (
        "Die Heute-Tabelle traegt nicht das ORTS-Datum.\n"
        f"  erwartet:  ({local_day:%d.%m}) — Ortszeit war "
        f"{_AFTER_LOCAL_MIDNIGHT_UTC.astimezone(_TRIP_TZ):%d.%m. %H:%M}\n"
        f"  Kopfzeile: {body.splitlines()[0]!r}"
    )
    assert f"({_AFTER_LOCAL_MIDNIGHT_UTC:%d.%m})" not in body, (
        "Die Heute-Tabelle zeigt das WELTZEIT-Datum "
        f"({_AFTER_LOCAL_MIDNIGHT_UTC:%d.%m}) statt des Orts-Datums "
        f"({local_day:%d.%m}).\n  Kopfzeile: {body.splitlines()[0]!r}"
    )


# ---------------------------------------------------------------------------
# 3) "heute" und "morgen" folgen DEMSELBEN Kalender
# ---------------------------------------------------------------------------

def test_today_and_tomorrow_follow_the_same_calendar(env):
    """
    GIVEN denselben Knopfdruck-Zeitpunkt um 00:30 Ortszeit,
    WHEN  der Nutzer nacheinander die Stunden-Tabelle fuer HEUTE und fuer
          MORGEN oeffnet,
    THEN  liegen die beiden Ueberschriften genau EINEN Tag auseinander, und
          das Morgen-Fenster beginnt an der Ortsmitternacht dieses Tages.

    Das ist die Auflage aus #1470: ein halber Umbau — nur "morgen" auf
    Ortszeit — waere schlimmer als der Ist-Zustand, weil "heute" und "morgen"
    dann verschiedenen Kalendern folgten.
    """
    today_body = _press(
        "dd_hours_today", _AFTER_LOCAL_MIDNIGHT_UTC
    ).confirmation_body
    tomorrow_body = _press(
        "dd_hours_tomorrow", _AFTER_LOCAL_MIDNIGHT_UTC
    ).confirmation_body

    local_today = (_AFTER_LOCAL_MIDNIGHT_UTC.astimezone(_TRIP_TZ)).date()
    local_tomorrow = local_today + timedelta(days=1)

    assert f"({local_today:%d.%m})" in today_body, (
        f"Heute-Tabelle: erwartet ({local_today:%d.%m}), Kopfzeile: "
        f"{today_body.splitlines()[0]!r}"
    )
    assert f"({local_tomorrow:%d.%m})" in tomorrow_body, (
        f"Morgen-Tabelle: erwartet ({local_tomorrow:%d.%m}), Kopfzeile: "
        f"{tomorrow_body.splitlines()[0]!r}"
    )

    hours = _table_hours(tomorrow_body)
    assert hours[:1] == ["00"], (
        "Morgen beginnt nicht an der Ortsmitternacht des Tages, den die "
        f"Kopfzeile nennt.\n  erste Stunde: {hours[:3]}\n"
        f"  Kopfzeile: {tomorrow_body.splitlines()[0]!r}"
    )
