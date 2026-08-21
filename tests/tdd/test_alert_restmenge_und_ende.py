"""TDD RED — Issue #2020, Scheibe 2: der Abweichungsalarm schaut nach VORN.

SPEC: docs/specs/modules/fix_2020_alarm_blickrichtung.md (AC-1 .. AC-7)

GEMESSENER IST-STAND (2026-08-21, dieser Branch): der Alarm nennt fuer eine
Niederschlags-Summen-Aenderung ausschliesslich Vergangenheit — den Von-/
Bis-Wert und die staerkste Stunde (`_datablock_single`, render.py:692-723).
Es fehlen alle drei Bausteine:

1. `WeatherChange` fuehrt weder `remaining_mm` noch `precip_ends_at`
   (models.py:570 ff.), und `weather_change_detection.py` rechnet nichts
   dergleichen aus der Stundenreihe.
2. `to_alert_message()` (project.py:125) kennt keine Referenzzeit `now_utc` —
   ohne sie kann niemand entscheiden, welche Stunde noch bevorsteht.
3. `AlertEvent` traegt keine Restmengen-Felder, und kein Renderer setzt die
   Saetze "Bis jetzt: …"/"Ab jetzt: …" bzw. das Kurzform-Token `Rest{mm}@{HH}`.

PRUEFORT = WIRKORT. Restmenge und Ende entstehen laut Spec im ERKENNUNGSDIENST
aus der Stundenreihe INNERHALB DES SEGMENTFENSTERS (bindende Invariante,
Spec-Abschnitt "Implementation Details"). Deshalb faehrt jeder Test hier die
echte Produktivkette:

    resolve_configured_window()/window_end_utc_exclusive()  -> Fenstergrenzen
    WeatherChangeDetectionService().detect_changes(...)     -> WeatherChange
    to_alert_message(...)                                   -> AlertMessage
    render_email()/render_telegram()/render_sms()           -> die vier Kanaele

Kein Test baut sich eine `WeatherChange` von Hand mit fertigen Werten
zusammen — das pruefte die Fenster-Invariante (AC-5/AC-6) ueberhaupt nicht.

KEIN MOCK-THEATER (CLAUDE.md, Kern-Schicht): kein `Mock()`/`patch()`/
`MagicMock`, kein Dateiinhalt-Check als Verhaltensnachweis, kein Netz.

ZEITZONE. Die Etappe haengt bewusst auf Island (`Atlantic/Reykjavik`,
ganzjaehrig UTC+0, keine Sommerzeit): Ortszeit und Weltzeit sind dort
zeichengleich, die Uhrzeit-Erwartungen der Spec ("15:00", "17:00") stehen
damit als LITERAL im Test und werden nicht aus derselben Zeitzonen-Aufloesung
gezogen, die der Prueling benutzt. Kalendertag und Referenzzeiten sind fest —
nirgends entscheidet die Systemuhr mit (AC-13).

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest (ueber
`tests/conftest.py`, das `<repo>/src` an `sys.path` haengt), nie ueber den
festen Hauptrepo-Pfad — sonst pruefte dieser Test aus dem Worktree die
unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from app.day_window import resolve_configured_window, window_end_utc_exclusive
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    _render_sms_body, render_email, render_sms, render_telegram,
)
from services.weather_change_detection import WeatherChangeDetectionService
from utils.timezone import local_fmt

# Island: ganzjaehrig UTC+0 -> Ortszeit == Weltzeit (s. Modul-Docstring).
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
TZ = ZoneInfo("Atlantic/Reykjavik")
TAG = date(2026, 8, 20)

# Die Stundenreihe der Spec (AC-1): 13:00=8 · 15:00=10 · 16:00=3 · 17:00=1 mm.
# Summe im Tagesfenster 4-19 = 22 mm; angekuendigt (letzter Briefing-Stand)
# waren 5 mm.
REIHE_AC1 = {13: 8.0, 15: 10.0, 16: 3.0, 17: 1.0}
SUMME_AC1 = 22.0
ANGEKUENDIGT = 5.0

# Fenster 4-19 (Default, ADR-0035). `end_hour` zaehlt VOLL mit -> das Fenster
# endet effektiv um 20:00 Ortszeit (window_end_utc_exclusive, day_window.py:57).
FENSTER_TAG = (4, 19)
# Zweites, ausdruecklich genanntes Fenster fuer die Fenstergrenzen-Gegenprobe.
FENSTER_LANG = (4, 22)


# --------------------------------------------------------------------------
# Fixture-Bausteine — die Fenstergrenzen kommen aus den PRODUKTIVEN Funktionen
# (`resolve_configured_window`/`window_end_utc_exclusive`), nicht aus getippten
# Uhrzeiten. Sonst pruefte der Test seine eigene Annahme ueber das Fenster.
# --------------------------------------------------------------------------

def _fenstergrenzen(fenster: tuple[int, int], *, tag: date = TAG):
    """(Beginn, effektives Ende) des Tagesfensters als UTC-Zeitstempel."""
    start_h, end_h = resolve_configured_window(*fenster)
    beginn = (
        datetime.combine(tag, time(start_h))
        .replace(tzinfo=TZ)
        .astimezone(timezone.utc)
    )
    return beginn, window_end_utc_exclusive(tag, end_h, TZ)


def _fensterende_text(fenster: tuple[int, int] = FENSTER_TAG) -> str:
    """"20:00" fuer das Default-Fenster — abgeleitet, nicht getippt."""
    return local_fmt(_fenstergrenzen(fenster)[1], TZ)


def _segment(fenster: tuple[int, int]) -> TripSegment:
    """Ziel-Etappe, deren Fenster GENAU das Tagesfenster ist — so, wie
    `_aggregate_for_segment()` es fuer Alarm UND Briefing zuschneidet."""
    beginn, ende = _fenstergrenzen(fenster)
    return TripSegment(
        segment_id="Ziel",
        start_point=GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=800.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=ISLAND_LAT + 0.1, lon=ISLAND_LON + 0.1,
                           elevation_m=900.0, distance_from_start_km=9.0),
        start_time=beginn, end_time=ende,
        duration_hours=(ende - beginn).total_seconds() / 3600.0,
        distance_km=9.0, ascent_m=100.0, descent_m=100.0,
    )


def _punkte(stunden: dict[int, float], *, tag: date = TAG):
    """Volle 24-Stunden-Reihe des Tages; nur die genannten Stunden tragen Regen.

    Bewusst der GANZE Tag: eine Stunde ausserhalb des Fensters muss ueber ihren
    ZEITSTEMPEL herausfallen (AC-6), nicht dadurch, dass es sie gar nicht gibt.
    """
    return [
        ForecastDataPoint(
            ts=datetime(tag.year, tag.month, tag.day, h, 0),
            t2m_c=12.0, wind10m_kmh=15.0, gust_kmh=25.0,
            precip_1h_mm=stunden.get(h, 0.0),
        )
        for h in range(24)
    ]


def _data(stunden: dict[int, float], summe: float,
          fenster: tuple[int, int] = FENSTER_TAG) -> SegmentWeatherData:
    """Ein Etappen-Datenstand: Stundenreihe + Fenster-Aggregat.

    `precip_sum_mm` ist die FENSTER-Gesamtsumme (so entsteht sie produktiv in
    `_aggregate_for_segment()`); die Projektion leitet daraus das bereits
    Gefallene als `new_value - remaining_mm` ab.
    """
    return SegmentWeatherData(
        segment=_segment(fenster),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                              grid_res_km=1.0),
            data=_punkte(stunden),
        ),
        aggregated=SegmentWeatherSummary(temp_max_c=12.0, precip_sum_mm=summe),
        fetched_at=datetime(TAG.year, TAG.month, TAG.day, 6, 0,
                            tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _data_ohne_reihe(summe: float,
                     fenster: tuple[int, int] = FENSTER_TAG) -> SegmentWeatherData:
    """Ein Etappen-Datenstand OHNE Stundenreihe.

    `SegmentWeatherData.timeseries` ist im DTO ausdruecklich optional
    ("None bei Provider-Fehler", models.py:543) — das ist also kein
    konstruierter Sonderfall, sondern der dokumentierte Datenmangel-Zustand
    des Versandpfads. Dieselbe Lage entsteht beim Vorschau-Stub des
    Validators (`validator_render_service._stub_segment`, `data=[]`).
    """
    return SegmentWeatherData(
        segment=_segment(fenster),
        timeseries=None,
        aggregated=SegmentWeatherSummary(temp_max_c=12.0, precip_sum_mm=summe),
        fetched_at=datetime(TAG.year, TAG.month, TAG.day, 6, 0,
                            tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _aenderungen(stunden: dict[int, float], *, alt: float, neu: float,
                 fenster: tuple[int, int] = FENSTER_TAG,
                 schwelle: float | None = None):
    """Der PRODUKTIVE Vergleichslauf. `include_absolute=False` ist der
    Alarm-Pfad (Issue #816). `schwelle` bildet eine nutzerseitig gesetzte
    Empfindlichkeit ab (Katalog-Default fuer `precip_sum_mm` ist 10 mm)."""
    detektor = (
        WeatherChangeDetectionService(thresholds={"precip_sum_mm": schwelle})
        if schwelle is not None else WeatherChangeDetectionService()
    )
    alt_data = _data(stunden, alt, fenster)
    neu_data = _data(stunden, neu, fenster)
    changes = detektor.detect_changes(alt_data, neu_data, include_absolute=False)
    regen = [c for c in changes if c.metric == "precip_sum_mm"]
    assert regen, (
        "Der Detektor muss eine Niederschlags-Summen-Aenderung liefern; "
        f"bekam {[c.metric for c in changes]}"
    )
    return regen, [neu_data]


def _uhr(stunde: int, minute: int = 0, *, tag: date = TAG) -> datetime:
    """Referenzzeit (Ortszeit == UTC auf Island) als UTC-Zeitstempel."""
    return datetime(tag.year, tag.month, tag.day, stunde, minute,
                    tzinfo=timezone.utc)


def _nachricht(changes, segmente, *, now_utc: datetime,
               stand_at: str | None = None):
    """Projektion MIT Referenzzeit.

    `stand_at` ist normalerweise die Ortszeit der Referenzzeit (so entsteht sie
    produktiv). Wo ZWEI Referenzzeiten gegeneinander verglichen werden (AC-4),
    setzt der Test ihn fest — sonst unterschieden sich die Texte schon an der
    Stand-Zeile, und der Vergleich sagte nichts ueber die Restmenge aus.
    """
    kwargs = dict(tz=TZ, stand_at=stand_at or local_fmt(now_utc, TZ))
    return to_alert_message(changes, segmente, "Test-Trip",
                            now_utc=now_utc, **kwargs)


def _texte(stunden: dict[int, float], *, now_utc: datetime,
           alt: float = ANGEKUENDIGT, neu: float = SUMME_AC1,
           fenster: tuple[int, int] = FENSTER_TAG,
           schwelle: float | None = None,
           stand_at: str | None = None) -> dict[str, str]:
    """Die vier Kanaltexte aus EINEM Alarm-Lauf — genau die Renderer, die
    `notification_service._dispatch_alert_message()` aufruft. Premium-SMS
    bekommt dort denselben `sms_body` wie SMS (`_render_sms_body`)."""
    changes, segmente = _aenderungen(stunden, alt=alt, neu=neu,
                                     fenster=fenster, schwelle=schwelle)
    msg = _nachricht(changes, segmente, now_utc=now_utc, stand_at=stand_at)
    html, plain = render_email(msg)
    return {
        "email_html": html, "email_plain": plain,
        "telegram": render_telegram(msg),
        # 160 statt des Default-Limits 140: die Spec bemisst die Kurzform an
        # der 160-Zeichen-Grenze (AC-7), und ein zu enges Limit wuerde den
        # Restmengen-Token wegschneiden, bevor er geprueft werden kann.
        "sms": render_sms(msg, 160),
        "premium_sms": _render_sms_body(msg, 160),
    }


def _langform(texte: dict[str, str]) -> list[tuple[str, str]]:
    """(Kanalname, Text) der beiden Langform-Kanaele — E-Mail-Klartext und
    Telegram muessen dieselben Saetze tragen."""
    return [("email_plain", texte["email_plain"]), ("telegram", texte["telegram"])]


# --------------------------------------------------------------------------
# AC-1 .. AC-3: dieselbe Stundenreihe, drei Referenzzeiten
# --------------------------------------------------------------------------

def test_alarm_nennt_restmenge_und_letzten_regen_ab_versandzeit():
    """AC-1.

    GIVEN Tagesfenster 4-19 (effektives Ende 20:00 Ortszeit) und die
          Stundenreihe 13:00=8 · 15:00=10 · 16:00=3 · 17:00=1 mm
          (angekuendigt waren 5 mm)
    WHEN  die Nachricht bei Referenzzeit 14:30 Ortszeit gerendert wird —
          nach der 13:00-Stunde, vor der 15:00-Stunde
    THEN  ist die Hauptaussage vorwaertsgewandt: Kopf "mehr Regen als
          angekuendigt", "Bis jetzt: ~8 mm gefallen (angekuendigt waren 5)",
          "Ab jetzt: noch ~14 mm, letzter Regen gegen 17:00".
    """
    texte = _texte(REIHE_AC1, now_utc=_uhr(14, 30))

    for kanal, text in _langform(texte):
        assert "mehr Regen als angekündigt" in text, (
            f"{kanal}: Der Kopf muss die Blickrichtung nennen "
            f"('mehr Regen als angekündigt'); bekam:\n{text}"
        )
        assert "Bis jetzt: ~8 mm gefallen (angekündigt waren 5)" in text, (
            f"{kanal}: Einordnung des bereits Gefallenen fehlt; bekam:\n{text}"
        )
        assert "Ab jetzt: noch ~14 mm, letzter Regen gegen 17:00" in text, (
            f"{kanal}: Restmenge ab Versand und ihr Ende fehlen — genau das "
            f"ist die Hauptaussage dieser Scheibe; bekam:\n{text}"
        )

    kopfzeile = [z for z in texte["telegram"].splitlines()
                 if "mehr Regen als angekündigt" in z]
    assert kopfzeile and "Ziel" in kopfzeile[0], (
        f"Der Kopf muss weiterhin den Ort nennen ('🏁 Ziel'); bekam {kopfzeile!r}"
    )


def test_frueher_versand_meldet_fast_die_ganze_menge_als_rest():
    """AC-2.

    GIVEN dieselbe Stundenreihe und dasselbe Fenster wie AC-1
    WHEN  die Nachricht bei Referenzzeit 10:00 Ortszeit gerendert wird, bevor
          irgendeine Stunde der Reihe begonnen hat
    THEN  ist die Restmenge nahe der Fenster-Gesamtmenge (~22 mm), das bereits
          Gefallene nahe null (~0 mm), und die Endzeit bleibt 17:00 — sie ist
          eine Eigenschaft der Reihe, nicht der Referenzzeit.
    """
    texte = _texte(REIHE_AC1, now_utc=_uhr(10))

    for kanal, text in _langform(texte):
        assert "Ab jetzt: noch ~22 mm, letzter Regen gegen 17:00" in text, (
            f"{kanal}: Vor der ersten Regenstunde muss die volle Fenstermenge "
            f"als Rest stehen; bekam:\n{text}"
        )
        assert "Bis jetzt: ~0 mm gefallen (angekündigt waren 5)" in text, (
            f"{kanal}: Vor der ersten Regenstunde darf nichts gefallen sein; "
            f"bekam:\n{text}"
        )
        assert "~-" not in text, (
            f"{kanal}: Keine Teilmenge darf negativ werden; bekam:\n{text}"
        )
        assert "noch ~23 mm" not in text and "noch ~24 mm" not in text, (
            f"{kanal}: Die Restmenge darf die Fenster-Gesamtmenge (22 mm) nicht "
            f"ueberschreiten; bekam:\n{text}"
        )


def test_alarm_nach_dem_letzten_regen_meldet_ehrlich_nichts_mehr():
    """AC-3.

    GIVEN dieselbe Stundenreihe und dasselbe Fenster wie AC-1 (letzte
          Regenstunde 17:00)
    WHEN  die Nachricht bei Referenzzeit 18:15 Ortszeit gerendert wird — nach
          der letzten Regenstunde, aber vor dem effektiven Fensterende 20:00
          (der beanstandete Originalfall vom 2026-08-20)
    THEN  meldet sie "kein weiterer Regen bis Tagesende (Fensterende 20:00
          Ortszeit)" statt eine Restmenge zu erfinden — und wird trotzdem
          zugestellt, weil bereits mehr gefallen ist als angekuendigt.
    """
    texte = _texte(REIHE_AC1, now_utc=_uhr(18, 15))
    erwartet = (
        "Ab jetzt: kein weiterer Regen bis Tagesende "
        f"(Fensterende {_fensterende_text()} Ortszeit)"
    )

    for kanal, text in _langform(texte):
        assert text.strip(), f"{kanal}: Die Meldung darf nicht leer sein"
        assert erwartet in text, (
            f"{kanal}: Nach der letzten Regenstunde muss die Meldung ehrlich "
            f"sagen, dass nichts mehr kommt. Erwartet {erwartet!r}; bekam:\n{text}"
        )
        assert "Bis jetzt: ~22 mm gefallen (angekündigt waren 5)" in text, (
            f"{kanal}: Die Einordnung des bereits Gefallenen bleibt — sie ist "
            f"der Grund, warum die Meldung zugestellt wird; bekam:\n{text}"
        )
        assert "noch ~" not in text, (
            f"{kanal}: Es darf keine Restmenge erfunden werden; bekam:\n{text}"
        )


# --------------------------------------------------------------------------
# AC-4 .. AC-6: Rechenregeln der Restmenge
# --------------------------------------------------------------------------

def test_angebrochene_stunde_zaehlt_voll_und_nicht_anteilig():
    """AC-4.

    GIVEN eine Referenzzeit mitten in einer angebrochenen Regenstunde
          (14:20 Ortszeit bei 2,0 mm um 14:00, sonst die AC-1-Reihe)
    WHEN  die Restmenge berechnet wird
    THEN  zaehlt die angebrochene Stunde VOLL (2 + 10 + 3 + 1 = 16 mm) — die
          Reihe ergibt bei 14:00 exakt denselben Wert wie bei 14:20. Eine
          anteilige Implementierung muss daran brechen.
    """
    reihe = {**REIHE_AC1, 14: 2.0}
    summe = SUMME_AC1 + 2.0
    # `stand_at` fest auf BEIDEN Seiten: sonst unterschieden sich die Texte
    # bereits an der Stand-Zeile ("Stand: heute 14:00" gegen "… 14:20"), und
    # der Vergleich unten koennte selbst nach einer korrekten Implementierung
    # nie gruen werden. So bleibt der schaerfste Vergleich moeglich — der
    # GESAMTE Kanaltext —, und der einzige zulaessige Unterschied waere ein
    # anteilig gekuerzter Restmengenwert. Genau den soll AC-4 verbieten.
    voll = _texte(reihe, now_utc=_uhr(14, 0), neu=summe, stand_at="14:00")
    angebrochen = _texte(reihe, now_utc=_uhr(14, 20), neu=summe, stand_at="14:00")

    for kanal, text in _langform(angebrochen):
        assert "Ab jetzt: noch ~16 mm, letzter Regen gegen 17:00" in text, (
            f"{kanal}: Die um 14:00 beginnende Stunde (2,0 mm) zaehlt VOLL zur "
            f"Restmenge (2+10+3+1 = 16 mm); bekam:\n{text}"
        )
    for kanal in ("email_plain", "telegram", "sms"):
        assert voll[kanal] == angebrochen[kanal], (
            f"{kanal}: Grenzstabilitaet — 14:00 und 14:20 muessen denselben "
            f"Restmengen-Wert liefern.\n14:00: {voll[kanal]!r}\n"
            f"14:20: {angebrochen[kanal]!r}"
        )


def test_ende_ist_die_letzte_regenstunde_des_ganzen_fensters():
    """AC-5.

    GIVEN Tagesfenster 4-19 und zwei getrennte Regenphasen, die BEIDE im
          Fenster liegen (6:00=1 · 7:00=1 mm, Pause, 16:00=1 · 17:00=1 mm)
    WHEN  das Ende bei Referenzzeit 10:00 Ortszeit — zwischen den Phasen —
          berechnet wird
    THEN  ist das Ende die letzte Regenstunde des GESAMTEN Fensters (17:00),
          nicht das Ende der ersten Phase (07:00).
    """
    reihe = {6: 1.0, 7: 1.0, 16: 1.0, 17: 1.0}
    # Nutzerseitig empfindlichere Schwelle (1 mm statt Katalog-Default 10 mm) —
    # sonst loest diese kleine, aber fachlich reale Reihe gar keinen Alarm aus.
    texte = _texte(reihe, now_utc=_uhr(10), alt=1.0, neu=4.0, schwelle=1.0)

    for kanal, text in _langform(texte):
        assert "letzter Regen gegen 17:00" in text, (
            f"{kanal}: Das Ende muss die letzte Regenstunde des Fensters sein "
            f"(17:00), nicht das Ende der ersten Phase; bekam:\n{text}"
        )
        assert "gegen 07:00" not in text, (
            f"{kanal}: 07:00 ist nur das Ende der ERSTEN Phase — die zweite "
            f"Phase liegt im selben Fenster; bekam:\n{text}"
        )
        assert "Ab jetzt: noch ~2 mm" in text, (
            f"{kanal}: Beide Stunden der zweiten Phase stehen noch bevor; "
            f"bekam:\n{text}"
        )


@pytest.mark.parametrize(
    "fenster, erwartet_rest, erwartet_ende, summe",
    [
        (FENSTER_TAG, "noch ~22 mm", "gegen 17:00", SUMME_AC1),
        (FENSTER_LANG, "noch ~27 mm", "gegen 21:00", SUMME_AC1 + 5.0),
    ],
    ids=["fenster_4_19_schliesst_21_uhr_aus", "fenster_4_22_schliesst_21_uhr_ein"],
)
def test_restmenge_und_ende_bleiben_im_konfigurierten_tagesfenster(
    fenster, erwartet_rest, erwartet_ende, summe,
):
    """AC-6.

    GIVEN die AC-1-Reihe, ergaenzt um eine Regenstunde um 21:00 (5 mm)
    WHEN  Restmenge und Ende bei Referenzzeit 10:00 einmal mit Tagesfenster
          4-19 (effektives Ende 20:00) und einmal mit 4-22 (effektives Ende
          23:00) berechnet werden
    THEN  bleiben die Werte bei 4-19 GENAU wie in AC-2 (22 mm / 17:00 — die
          21:00-Stunde faellt heraus) und aendern sich bei 4-22 fenstertreu
          (27 mm / 21:00). Eine Implementierung, die global ueber die Reihe
          summiert, muss mindestens einen der beiden Faelle brechen.
    """
    reihe = {**REIHE_AC1, 21: 5.0}
    texte = _texte(reihe, now_utc=_uhr(10), neu=summe, fenster=fenster)

    for kanal, text in _langform(texte):
        assert f"Ab jetzt: {erwartet_rest}, letzter Regen {erwartet_ende}" in text, (
            f"{kanal}: Fenster {fenster} -> erwartet {erwartet_rest!r} / "
            f"{erwartet_ende!r}; bekam:\n{text}"
        )


def test_regen_nach_fensterende_erscheint_nicht_in_der_meldung():
    """AC-6 (Gegenprobe zur Fenster-Invariante).

    GIVEN dieselbe erweiterte Reihe (21:00 = 5 mm) und Tagesfenster 4-19
    WHEN  die Nachricht bei Referenzzeit 10:00 gerendert wird
    THEN  taucht die 21:00-Stunde nirgends auf — weder als Endzeit noch in der
          Restmenge. Genau das sieht auch das Briefing fuer diesen Zeitraum
          nicht (gemeinsames Fenster, Spec-Invariante).
    """
    reihe = {**REIHE_AC1, 21: 5.0}
    texte = _texte(reihe, now_utc=_uhr(10))

    for kanal, text in _langform(texte):
        # Positivseite ZUERST: ohne sie waere dieser Waechter allein dadurch
        # gruen, dass es noch gar keine Restmengen-Aussage gibt.
        assert "Ab jetzt: noch ~22 mm, letzter Regen gegen 17:00" in text, (
            f"{kanal}: Die Werte muessen mit AC-2 identisch bleiben, obwohl die "
            f"Reihe eine 21:00-Stunde traegt; bekam:\n{text}"
        )
        assert "21:00" not in text, (
            f"{kanal}: Regen nach dem effektiven Fensterende (20:00) darf die "
            f"Meldung nicht erreichen; bekam:\n{text}"
        )
        assert "noch ~27 mm" not in text, (
            f"{kanal}: Die 21:00-Stunde darf nicht in die Restmenge fliessen; "
            f"bekam:\n{text}"
        )


# --------------------------------------------------------------------------
# AC-7: alle vier Kanaele aus EINER Nachricht
# --------------------------------------------------------------------------

def test_alle_vier_kanaele_tragen_restmenge_und_ende():
    """AC-7.

    GIVEN denselben Abweichungsalarm wie AC-1 (Reihe/Fenster/Referenzzeit
          14:30)
    WHEN  er in alle vier Kanaele gerendert wird (E-Mail HTML, E-Mail
          Klartext, Telegram, SMS/Premium-SMS)
    THEN  tragen E-Mail und Telegram die vollstaendigen Saetze, SMS und
          Premium-SMS denselben Sachverhalt als Kompakt-Token
          ("Ziel: R5->22@15 Rest14@17"), und die Kurznachricht bleibt
          innerhalb der 160-Zeichen-Grenze.
    """
    texte = _texte(REIHE_AC1, now_utc=_uhr(14, 30))

    assert "Ab jetzt" in texte["email_html"], (
        "Die HTML-Fassung ist die Normalfassung und muss dieselbe Aussage "
        f"tragen; bekam:\n{texte['email_html']}"
    )
    for kanal, text in _langform(texte):
        assert "Ab jetzt: noch ~14 mm, letzter Regen gegen 17:00" in text, (
            f"{kanal}: vollstaendiger Satz erwartet; bekam:\n{text}"
        )

    for kanal in ("sms", "premium_sms"):
        kurz = texte[kanal]
        assert "Rest14@17" in kurz, (
            f"{kanal}: Kompakt-Token der Restmenge erwartet ('Rest14@17'); "
            f"bekam {kurz!r}"
        )
        assert "R5->22@15" in kurz, (
            f"{kanal}: Das bestehende Delta-Token bleibt unveraendert daneben "
            f"stehen; bekam {kurz!r}"
        )
        assert kurz.startswith("Ziel:"), (
            f"{kanal}: Der Kurzform-Kopf nennt weiterhin den Ort; bekam {kurz!r}"
        )
        assert len(kurz) <= 160, (
            f"{kanal}: 160-Zeichen-Grenze gerissen ({len(kurz)}): {kurz!r}"
        )

    # Premium-SMS laeuft ueber DENSELBEN `_render_sms_body`-Pfad wie SMS —
    # nachgewiesen, nicht angenommen: derselbe Text, nicht nur derselbe Inhalt.
    assert texte["sms"] == texte["premium_sms"], (
        "SMS und Premium-SMS muessen denselben Text bekommen.\n"
        f"sms:         {texte['sms']!r}\npremium_sms: {texte['premium_sms']!r}"
    )


def test_kein_weiterer_regen_wird_auch_in_der_kurzform_gesagt():
    """AC-7 (Kurzform des AC-3-Falls).

    GIVEN die AC-1-Reihe und Referenzzeit 18:15 (nichts kommt mehr)
    WHEN  die Kurznachricht gebaut wird
    THEN  steht dort "Rest0" ohne Zeit-Suffix — die Kurzform verschweigt den
          Sachverhalt nicht, sie kuerzt ihn nur.
    """
    kurz = _texte(REIHE_AC1, now_utc=_uhr(18, 15))["sms"]

    assert "Rest0" in kurz, (
        f"Kurzform muss 'Rest0' melden statt zu schweigen; bekam {kurz!r}"
    )
    assert "Rest0@" not in kurz, (
        f"'Rest0' traegt kein Zeit-Suffix (es gibt keine Endzeit); bekam {kurz!r}"
    )
    assert len(kurz) <= 160, f"160-Zeichen-Grenze gerissen: {kurz!r}"


# --------------------------------------------------------------------------
# Absicherung der Umsetzung (kein AC): "weiss ich nicht" ist NICHT "kommt
# nichts mehr". Ein Datenmangel darf keine Entwarnung erfinden.
# --------------------------------------------------------------------------

def test_unbestimmbare_restmenge_erfindet_keine_entwarnung():
    """Absicherung zur Datenmangel-Unterscheidung (gehoert zu keinem der 14
    ACs — sie schuetzt die Umsetzung von AC-3).

    GIVEN denselben Abweichungsalarm wie AC-3 (Referenzzeit 18:15, nach der
          letzten Regenstunde), einmal MIT vollstaendiger Stundenreihe und
          einmal mit einem Etappen-Datenstand OHNE Zeitreihe (Provider-Fehler,
          `SegmentWeatherData.timeseries is None`)
    WHEN  beide Faelle gerendert werden
    THEN  sagt NUR der bestimmbare Fall "kein weiterer Regen bis Tagesende"
          (und in der Kurzform "Rest0"). Der unbestimmbare sagt ueber die
          Restmenge GAR NICHTS und faellt auf den Bestands-Kopf zurueck —
          eine Entwarnung aus einem technischen Defekt waere die gefaehrlichste
          Falschaussage, die diese Nachricht ueberhaupt treffen kann.

    Die Gegenueberstellung ist der Kern: eine Implementierung, die den
    Fehlerfall auf `0.0` legt, macht beide Faelle textgleich und muss hier
    brechen.
    """
    changes, segmente = _aenderungen(REIHE_AC1, alt=ANGEKUENDIGT, neu=SUMME_AC1)
    now = _uhr(18, 15)

    def _kanaele(segs):
        msg = _nachricht(changes, segs, now_utc=now)
        _html, plain = render_email(msg)
        return {"email_plain": plain, "telegram": render_telegram(msg),
                "sms": render_sms(msg, 160)}

    bestimmbar = _kanaele(segmente)
    unbestimmbar = _kanaele([_data_ohne_reihe(SUMME_AC1)])

    # Gegenprobe zuerst: ohne sie waere der Waechter unten allein dadurch
    # gruen, dass es den Satz ueberhaupt nicht (mehr) gibt.
    for kanal, text in _langform(bestimmbar):
        assert "kein weiterer Regen bis Tagesende" in text, (
            f"{kanal}: Der BESTIMMBARE Fall muss die Entwarnung ausdruecklich "
            f"aussprechen (AC-3); bekam:\n{text}"
        )
    assert "Rest0" in bestimmbar["sms"], (
        f"Kurzform des bestimmbaren Falls: {bestimmbar['sms']!r}"
    )

    for kanal, text in _langform(unbestimmbar):
        assert text.strip(), f"{kanal}: Die Meldung muss trotzdem rausgehen"
        # Positiv-Anker: die Meldung ist vollstaendig, nur die Restmengen-
        # Aussage fehlt — sonst waere dieser Test schon durch eine leere
        # Nachricht zufrieden.
        assert "stärkste Stunde" in text, (
            f"{kanal}: Ohne Restmenge greift der Bestands-Kopf; bekam:\n{text}"
        )
        assert "kein weiterer Regen" not in text, (
            f"{kanal}: Eine unbestimmbare Restmenge darf NICHT als Entwarnung "
            f"erscheinen — das erfindet aus einem Datenfehler eine Aussage; "
            f"bekam:\n{text}"
        )
        assert "Ab jetzt" not in text and "Bis jetzt" not in text, (
            f"{kanal}: Ohne bestimmbare Restmenge gibt es keine der beiden "
            f"Blickrichtungs-Zeilen; bekam:\n{text}"
        )
    assert "Rest" not in unbestimmbar["sms"], (
        f"Kurzform darf kein Restmengen-Token erfinden; "
        f"bekam {unbestimmbar['sms']!r}"
    )
