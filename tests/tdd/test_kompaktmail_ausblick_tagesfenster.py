"""TDD RED — Issue #1671: Kurzformat-Mail liest die Gewitterspalte des
Ausblicks aus dem Tagesfenster statt aus dem 24h-Aggregat.

SPEC: docs/specs/modules/fix_1671_kompaktmail_ausblick_tagesfenster.md
      (AC-1..AC-7)

RED-Ursache (heute gemessen, `src/output/renderers/email/compact.py:227-238`):
die Ausblick-Schleife der Kurzformat-Mail liest ausschliesslich
``tok['thunder_plain']`` -- das auf die Gehzeit geklemmte 24h-Aggregat
(``stage["thunder"]``, unabhaengig von der Stundenreihe berechnet). HTML-
Ausblick-Tabelle, Klartext-Mail-Ausblick und Telegram-Trendblock wurden
bereits mit #1653 auf ``thunder_day_token``/``thunder_night_token`` (die nach
Tagesfenster gefilterte Stundenreihe) umgestellt -- die Kurzformat-Mail ist
der vierte, damals vergessene Ausgabeort.

PRUEFORT = WIRKORT. Jeder Test rendert ueber die ECHTE Renderkette bis zur
zugestellten Zeile: ``TripReportFormatter.format_email()`` mit
``TripReportConfig(email_format="compact")`` liefert ``.email_plain`` -- den
ASCII-gefalteten Kompakt-Mailkoerper, wie er tatsaechlich verschickt wird.
Keine Pruefung endet an ``_compact_thunder_field()`` oder
``format_trend_tokens()`` isoliert.

KEIN MOCK-THEATER. ``Mock``/``patch``/``MagicMock`` nirgends. Fuer AC-1..AC-4
wird das Ausblick-Zeilen-Dict wie ``build_outlook_row()`` es in Produktion
liefert direkt gebaut (Muster ``tests/tdd/test_outlook_day_night_thunder_split.py::_stage``,
das #1653 -- den unmittelbaren Vorgaenger dieses Fixes -- bereits fuer exakt
dieselbe Fehlerklasse in den drei anderen Kanaelen bewacht): Aggregat
(``thunder``) und Stundenreihe (``hourly_thunder``) sind in der Produktion
ZWEI GETRENNTE Rechnungen (``build_outlook_row()``: ``thunder`` aus
``summary.thunder_level_max``, ``hourly_thunder`` aus der flachen
Punktliste) -- ein Stage-Dict mit unabhaengig gesetzten Werten deckt genau
diese reale Fehlerklasse ab, es ist keine gemockte Fusion, sondern das
dokumentierte Eingabeformat von ``format_trend_tokens()``. Fuer die
AC-6-Gegenprobe wird die ECHTE Traeger-Fusion verwendet (wie
``tests/tdd/test_thunder_origin_outlook.py``), weil dort eine Herkunft
NACHWEISLICH entstehen muss, nicht nur behauptet werden darf.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur EIGENEN Testdatei aufloesen, nie ueber
# den festen Hauptrepo-Pfad -- sonst pruefte dieser Test aus dem Worktree die
# unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, TripReportConfig, TripSegment,
)
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from output.tokens.dto import HourlyValue  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService, summarize_points,
)

_TZ = ZoneInfo("UTC")
_HEUTE = date(2026, 8, 20)      # Etappe des Briefings (heutiger Tag)
_MORGEN = date(2026, 8, 21)     # kuenftige Etappe = Ausblick-Zeile
_WOCHENTAG = "Di"
_AUSBLICK_UEBERSCHRIFT = "Naechste Etappen"
_KOMPAKT = TripReportConfig(email_format="compact")

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung (AC-6). Keine
# davon darf im Kompakt-Ausblick auftauchen -- PO-Entscheidung 1 der Spec.
_ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")


# ---------------------------------------------------------------------------
# Fixture-Bausteine
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float) -> HourlyValue:
    return HourlyValue(hour=hour, value=value)


def _stage(*, weekday: str = "Di", name: str = "Etappe B", temp_lo=9, temp_hi=21,
           precip_mm=2.5, wind_dir="W", wind_kmh=18, thunder="NONE",
           hourly_thunder=None, day_window_start_hour=None,
           day_window_end_hour=None) -> dict:
    """Ausblick-Zeile mit UNABHAENGIG gesetztem Aggregat (``thunder``) und
    Stundenreihe (``hourly_thunder``) -- exakt die Faelle, die #1653 fuer
    HTML/Klartext/Telegram bereits geprueft hat. Kein Python-``None`` als
    Traeger einer Stufe: die Werte sind das dokumentierte Eingabeformat von
    ``format_trend_tokens()``, keine gemockte Fusion.
    """
    row = dict(
        weekday=weekday, name=name, note=None,
        temp_lo=temp_lo, temp_hi=temp_hi, precip_mm=precip_mm,
        wind_dir=wind_dir, wind_kmh=wind_kmh, thunder=thunder,
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        hourly_thunder=hourly_thunder or (),
    )
    if day_window_start_hour is not None:
        row["day_window_start_hour"] = day_window_start_hour
    if day_window_end_hour is not None:
        row["day_window_end_hour"] = day_window_end_hour
    return row


def _heutige_etappe() -> SegmentWeatherData:
    """Die HEUTIGE Etappe des Briefings -- gewitterfrei, dient nur als
    Pflicht-Segment fuer ``TripReportFormatter.format_email()``. Ihr Inhalt
    ist fuer keinen AC dieser Datei von Belang, nur der Ausblick-Block ist
    der Pruefling."""
    punkte = [
        ForecastDataPoint(
            ts=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, h, 0, tzinfo=timezone.utc),
            t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
            cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        )
        for h in range(6, 18)
    ]
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=punkte,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=12.1, elevation_m=1200.0),
        start_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 17, 0, tzinfo=timezone.utc),
        duration_hours=11.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _mail(zeilen: list[dict], *, report_config: TripReportConfig | None = None):
    """Das ECHTE Trip-Briefing ueber den produktiven Formatierer -- Pruefort
    = Wirkort."""
    return TripReportFormatter().format_email(
        [_heutige_etappe()], "Test-Trip", "evening",
        display_config=build_default_display_config(), tz=_TZ,
        stage_name="Etappe A", multi_day_trend=zeilen,
        report_config=report_config,
    )


def _ohne_zeitstempel(text: str) -> str:
    """Blendet die einzige laufzeitabhaengige Zeile der Kompakt-Mail aus."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.startswith("Generated:")
    )


def _kompakt_ausblick_zeile(text: str, ueberschrift: str = _AUSBLICK_UEBERSCHRIFT) -> str:
    """Die EINE Ausblick-Zeile aus dem zugestellten Kompakt-Mailkoerper."""
    assert ueberschrift in text, (
        f"Kompakt-Ausblick '{ueberschrift}' fehlt in der Mail:\n{text}")
    rest = text.split(ueberschrift, 1)[1].splitlines()
    zeilen = []
    for ln in rest:
        if not ln.strip():
            if zeilen:
                break
            continue
        zeilen.append(ln)
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Ausblick-Zeile unter '{ueberschrift}', "
        f"gefunden: {zeilen!r}")
    return zeilen[0]


# ---------------------------------------------------------------------------
# AC-1 bis AC-4: die vier Verzweigungen von resolve_thunder_day_branch()
# ---------------------------------------------------------------------------

def test_tagesgewitter_erscheint_trotz_leerem_24h_aggregat():
    """AC-1: Given eine Etappe mit Tagesgewitter 'leicht' um 16 Uhr innerhalb
    des Tagesfensters, waehrend das 24h-Aggregat 'NONE' zeigt (Aggregat und
    Tagesfenster widersprechen sich) / When die Kurzformat-Mail gerendert
    wird / Then zeigt die Ausblick-Zeile das Tagesgewitter 'leicht' -- nicht
    das leere Aggregat.

    Heute (RED): die Zeile liest ``tok['thunder_plain']`` == ``_THUNDER_MAP
    ["NONE"]["plain"]`` == '⚡–' -> ASCII 'T-'. Das Tagesgewitter aus der
    Stundenreihe (hour=16, LOW) verschwindet vollstaendig.
    """
    zeile = _stage(hourly_thunder=(_hv(16, 1.0),), thunder="NONE")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    # #1493: der Tagesteil traegt jetzt die Onset-Stunde (`@16`).
    assert ausblick.endswith("Tleicht@16"), (
        f"Die Kompakt-Ausblick-Zeile muss auf das Tagesgewitter 'leicht' "
        f"(ASCII-gefaltet 'Tleicht@16') enden, nicht auf das leere 24h-Aggregat: "
        f"{ausblick!r}")


def test_kein_tagesgewitter_trotz_aggregat_high():
    """AC-2: Given dieselbe Konstellation umgekehrt -- 24h-Aggregat 'HIGH',
    Tagesfenster leer, das Gewitterereignis (hoch, 2 Uhr) liegt vollstaendig
    in der Nacht / When die Kurzformat-Mail gerendert wird / Then zeigt der
    Tagesteil explizit 'kein Gewitter' (ASCII-gefaltet 'T-'), nicht das
    faelschlich uebernommene Aggregat 'HIGH'; der Nachtteil zeigt das echte
    Nachtgewitter mit Uhrzeit.

    Heute (RED): die Zeile liest ``tok['thunder_plain']`` == ``_THUNDER_MAP
    ["HIGH"]["plain"]`` == '⚡HIGH' -> ASCII 'THIGH', ohne jeden Nachtzusatz
    (den es im Kompaktformat vor dieser Scheibe strukturell nie gab).
    """
    zeile = _stage(hourly_thunder=(_hv(2, 3.0),), thunder="HIGH")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    assert ausblick.endswith("T- - nachts hoch @2"), (
        f"Der Tagesteil muss explizit 'kein Gewitter' zeigen (nicht das "
        f"Aggregat 'HIGH'), gefolgt vom echten Nachtgewitter mit Uhrzeit: "
        f"{ausblick!r}")
    assert "HIGH" not in ausblick, (
        f"Das faelschlich uebernommene Aggregat 'HIGH' darf in der Zeile "
        f"nicht mehr auftauchen: {ausblick!r}")


def test_nachtgewitter_erscheint_mit_uhrzeit_im_kompaktformat():
    """AC-3: Given eine Etappe mit Tagesgewitter 'mittel' 14 Uhr UND
    Nachtgewitter 'hoch' 0 Uhr (Fall B aus #1653) / When die Kurzformat-Mail
    gerendert wird / Then enthaelt die zugestellte, ASCII-gefaltete Zeile
    sowohl den Tagesteil als auch einen Nachtzusatz der exakten Form
    '- nachts hoch @0' (Bindestrich statt '·' nach der Faltung) -- eine
    Nachtangabe, die im Kompaktformat vor dieser Scheibe strukturell nie
    erschien.

    Exakte Wortlaut-Pruefung (kein loses ``in``-'nachts'): faengt Mutation
    (e) der Spec (entferntes Leerzeichen vor '@').
    """
    zeile = _stage(hourly_thunder=(_hv(14, 2.0), _hv(0, 3.0)), thunder="MED")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    # #1493: Tagesteil mit Onset-Stunde, Nachtzusatz unveraendert.
    assert ausblick.endswith("Tmittel@14 - nachts hoch @0"), (
        f"Tagesteil 'Tmittel@14' und Nachtzusatz '- nachts hoch @0' (mit "
        f"Leerzeichen vor '@') muessen exakt so am Ende der Zeile stehen: "
        f"{ausblick!r}")


def test_kein_gewitter_tag_und_nacht_zeigt_explizites_none():
    """AC-4: Given eine Etappe ganz ohne Gewitter (Tag- und Nachtstunde mit
    Wert 0.0, Stundenreihe vorhanden, Aggregat behauptet dagegen 'HIGH') /
    When die Kurzformat-Mail gerendert wird / Then zeigt die Zeile das
    explizite 'kein Gewitter'-Zeichen ('T-') ohne Nachtzusatz -- kein leerer
    oder abweichender Ausdruck, und das falsche Aggregat 'HIGH' wird
    ignoriert.

    Bewusst mit Aggregat 'HIGH' (statt 'NONE'), damit der Test nicht
    zufaellig schon am unveraenderten ``tok['thunder_plain']`` gruen waere --
    nur wenn die Stundenreihe (nicht das Aggregat) den Ausschlag gibt, zeigt
    die Zeile 'T-' statt 'THIGH'.
    """
    zeile = _stage(hourly_thunder=(_hv(10, 0.0), _hv(22, 0.0)), thunder="HIGH")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    assert ausblick.endswith("T-"), (
        f"Ohne Gewitter in Tag- und Nachtfenster muss die Zeile explizit "
        f"'T-' zeigen (nicht das Aggregat 'HIGH'): {ausblick!r}")
    assert "nachts" not in ausblick, (
        f"Ohne Nachtgewitter darf kein Nachtzusatz erscheinen: {ausblick!r}")
    assert "HIGH" not in ausblick, (
        f"Das falsche Aggregat 'HIGH' darf nicht durchsickern: {ausblick!r}")


# ---------------------------------------------------------------------------
# Adversary-Nachbesserung F002 (Blocker): Peak-Zusatz einer Eskalation
# innerhalb des Tagesfensters ist unbewacht -- Mutation `_d[2]` entfernen
# blieb bei 582 Bestandstests gruen, weil keine Fixture eine Eskalation im
# Tagesfenster nutzte.
# ---------------------------------------------------------------------------

def test_tagesgewitter_eskalation_zeigt_spitzenstufe_im_kompaktformat():
    """F002: Given eine Etappe mit einer Gewitter-Eskalation INNERHALB des
    Tagesfensters (Erst-Ueberschreitung 'leicht' um 5 Uhr, Spitze 'hoch' um
    15 Uhr -- Vorbild ``test_outlook_day_night_thunder_split.py::
    TestEscalationWithinWindowShowsPeak``, derselbe meteorologische
    Normalfall wie #1653 F005) / When die Kurzformat-Mail gerendert wird /
    Then zeigt die zugestellte, ASCII-gefaltete Ausblick-Zeile sowohl die
    Erst-Stufe 'leicht' als auch den Peak-Zusatz '(hoch @15)' -- nicht nur
    die erste, schwaechere Stufe.

    Ohne diese Pruefung liest die Zeile zwar bereits ``thunder_day_token``
    (AC-1), unterschlaegt aber stillschweigend die staerkere Spitzenstufe,
    vor der gewarnt werden soll (Adversary-Finding F002).
    """
    zeile = _stage(hourly_thunder=(_hv(5, 1.0), _hv(15, 3.0)), thunder="NONE")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    # #1493: Erst-Stufe mit Onset-Stunde, Peak-Zusatz unveraendert.
    assert ausblick.endswith("Tleicht@5 (hoch @15)"), (
        f"Die Kompakt-Ausblick-Zeile muss die Erst-Stufe 'leicht' UND den "
        f"Peak-Zusatz '(hoch @15)' zeigen -- die Eskalation innerhalb des "
        f"Tagesfensters darf nicht auf die schwaechere Erst-Stufe "
        f"zusammenschrumpfen: {ausblick!r}")


# ---------------------------------------------------------------------------
# Adversary-Nachbesserung F001: ein gesetzter, aber unzerlegbarer
# Tages-Token darf nicht abstuerzen, sondern muss auf "kein Gewitter"
# zurueckfallen (Guard aus der Nachbesserung waehrend der Implementierung,
# bislang ohne injizierten Testfall).
# ---------------------------------------------------------------------------

def test_unzerlegbarer_tagestoken_faellt_auf_kein_gewitter_zurueck():
    """F001: Given eine Tagesstunde mit einem Gewitter-Rohwert (4.0), der in
    KEINEM Eintrag von ``_TREND_THUNDER_LABELS`` (nur 1/2/3) vorkommt / When
    die Kurzformat-Mail gerendert wird / Then wird ``thunder_day_token``
    zwar gesetzt (``"-@5"``, denn ``render_threshold_peak_value`` liefert
    fuer eine unbekannte Stufe das Label '-'), ist aber fuer
    ``_thunder_token_parts()`` NICHT zerlegbar (der Regex verlangt ein
    Buchstaben-Wort vor dem '@'). Die Zeile faellt auf das explizite
    'kein Gewitter'-Zeichen zurueck, statt mit ``TypeError:
    'NoneType' object is not subscriptable`` abzustuerzen.

    Belegt die Invariante, auf der der ``branch == "day"``-Guard aus
    ``_compact_thunder_field()`` beruht, mit einem echten injizierten Fall
    (Adversary-Finding F001) -- vorher war die Absicherung nur durch
    Codeanalyse, nicht durch einen Test verifiziert.

    Bewusst mit Aggregat 'HIGH' (statt 'NONE', analog AC-4): faellt der
    unzerlegbare Zweig faelschlich auf ``tok["thunder_plain"]`` zurueck
    (die Mutation, die dieser Test fangen muss), zeigt die Zeile 'THIGH'
    statt 'T-' -- mit Aggregat 'NONE' waeren beide Rueckfaelle zufaellig
    identisch und die Mutation bliebe ungefangen.
    """
    zeile = _stage(hourly_thunder=(_hv(5, 4.0),), thunder="HIGH")
    bericht = _mail([zeile], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    assert ausblick.endswith("T-"), (
        f"Ein gesetzter, aber unzerlegbarer Tages-Token muss auf das "
        f"explizite 'kein Gewitter'-Zeichen 'T-' zurueckfallen (nicht "
        f"abstuerzen und nicht das Aggregat 'HIGH' zeigen): {ausblick!r}")
    assert "HIGH" not in ausblick, (
        f"Das Aggregat 'HIGH' darf im Rueckfall nicht durchsickern: "
        f"{ausblick!r}")


# ---------------------------------------------------------------------------
# AC-5: Bestandsschutz -- Alt-Fixture ohne Stundenreihe bleibt unveraendert
# ---------------------------------------------------------------------------

# Aufgezeichnet VOR jeder Implementierung dieser Scheibe, am Stand
# `71dd8a2d45d9edd914c6b8209f85e9ebd050a668` (== HEAD dieses Branches beim
# Schreiben dieses Tests, 2026-08-14), durch einen echten Renderlauf von
# ``_mail([_AC5_ALT_ZEILE], report_config=_KOMPAKT).email_plain`` durch
# ``_kompakt_ausblick_zeile()`` -- KEIN zweiter Aufruf desselben Codes zur
# Testlaufzeit (Spec AC-5, Begruendung woertlich aus
# tests/tdd/test_trip_outlook_parity.py).
# Issue #1488 Scheibe B: Sollwert neu aufgezeichnet -- das Aggregatwort kommt
# jetzt aus THUNDER_LABEL_DE ("mittel" statt "MED"). Geprueft bleibt die
# Zweigwahl (Rueckfall auf `thunder_plain` ohne Stundenreihe), nicht das Vokabular.
# Issue #1848 Scheibe A1: Sollwert erneut aufgezeichnet -- der Temperatur-Spannen-
# Trenner ist vom Bindestrich auf den Schraegstrich gewechselt ("9-21C" -> "9/21C").
# Grund: PO-Entscheid 2026-08-20, EIN Trenner ueber alle Klartext-Flaechen; der
# Bindestrich ist bei Minusgraden zugleich Trenner und Vorzeichen und damit nicht
# eindeutig lesbar. Gleiche Lage wie bei #1488 oben (MED -> mittel): geaendert hat
# sich das VOKABULAR, nicht die hier bewachte Zweigwahl -- der Rueckfall auf
# `thunder_plain` ohne Stundenreihe bleibt am abschliessenden "Tmittel" ablesbar
# und unveraendert geprueft.
_AC5_ALT_ZEILE_SOLL = "Mi  Alte Etappe                9/21C   1.5mm NW22  Tmittel"

_AC5_ALT_ZEILE = dict(
    weekday="Mi", name="Alte Etappe", note=None,
    temp_lo=9, temp_hi=21, precip_mm=1.5,
    wind_dir="NW", wind_kmh=22, thunder="MED",
    # Bewusst OHNE "hourly_thunder"-Schluessel -- der echte Alt-Aufrufer-Fall
    # (Spec AC-5: "hourly_thunder fehlt"), nicht nur eine leere Stundenreihe.
)


def test_ohne_stundenreihe_bleibt_kurzformat_unveraendert():
    """AC-5: Given eine Ausblick-Zeile ganz OHNE Stundenreihe (Alt-Fixture,
    Schluessel 'hourly_thunder' fehlt) / When die Kurzformat-Mail gerendert
    wird / Then bleibt die Ausgabe zeichengleich zum Stand vor dieser
    Aenderung (Rueckfall auf ``thunder_plain``, Zweig 'plain').

    Bestandsschutz -- dieser Test ist bereits JETZT gruen, vor jeder
    Implementierung: ohne Stundenreihe greift ``resolve_thunder_day_branch()``
    laut Spec unveraendert auf ``tok['thunder_plain']`` zurueck, denselben
    Wert, den der heutige (ungeaenderte) Code bereits liefert. Er MUSS nach
    der Implementierung gruen BLEIBEN -- ein rot werdender Lauf hier heisst,
    dass sich das Alt-Verhalten veraendert hat.
    """
    bericht = _mail([_AC5_ALT_ZEILE], report_config=_KOMPAKT)
    ausblick = _kompakt_ausblick_zeile(bericht.email_plain)
    assert ausblick == _AC5_ALT_ZEILE_SOLL, (
        f"Ohne Stundenreihe darf sich die Kompakt-Ausblick-Zeile NICHT "
        f"aendern.\nSoll (aufgezeichnet vor der Implementierung):\n"
        f"{_AC5_ALT_ZEILE_SOLL!r}\nIst:\n{ausblick!r}")


# ---------------------------------------------------------------------------
# AC-6-Gegenprobe: Kurzformat-Mail bleibt ohne Herkunfts-Zusatz
# ---------------------------------------------------------------------------
# AC-6 selbst ist der bestehende Bestandswaechter
# tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich
# (wird hier NICHT neu geschrieben). Testplan-Zeile AC-6 verlangt zusaetzlich
# eine Gegenprobe mit einer Fixture, die im HTML-/Klartext-Pfad NACHWEISLICH
# eine Herkunft erzeugen WUERDE -- sonst waere eine reine Abwesenheitspruefung
# vakuum-gruen.

_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN


def _dp_mit_traeger(h: int, *, cape=None, cin=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN -- Stufe und Traeger rechnet die
    ECHTE Fusion (wie tests/tdd/test_thunder_origin_outlook.py::_dp)."""
    return ForecastDataPoint(
        ts=datetime(_MORGEN.year, _MORGEN.month, _MORGEN.day, h, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=cin,
    )


def _mit_herkunft_ausblick_zeile() -> dict:
    """Eine Ausblick-Zeile MIT echter Traeger-Berechnung (#1680 S5a): CAPE
    400 J/kg bei schwachem Deckel (cin=5) liegt ueber der niedrigsten Sprosse
    (300 J/kg) und ergibt ueber die echte Fusion 'leicht' mit der Zutat
    CAPE als einzigem Traeger -- dieselbe Fixture-Bauart wie
    tests/tdd/test_thunder_origin_outlook.py::test_ac1_..., kein getippter
    Stufenwert."""
    punkte = [_dp_mit_traeger(16, cape=400.0, cin=5.0)]
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    zeile = build_outlook_row(summarize_points(punkte), punkte, _WOCHENTAG, _TZ)
    zeile["name"] = "Etappe B"
    return zeile


def _gew_zelle(html: str, kopf: str = "Gew") -> str:
    """Der Text der Gewitter-Zelle der Ausblick-Tabelle aus fertigem
    Mail-HTML (Muster tests/tdd/test_thunder_origin_outlook.py::_gew_zelle)."""
    suppe = BeautifulSoup(html, "html.parser")
    tabellen = [
        t for t in suppe.find_all("table")
        if {"Tag", kopf} <= {th.get_text(strip=True) for th in t.find_all("th")}
    ]
    assert len(tabellen) == 1, (
        f"Erwartet genau EINE Ausblick-Tabelle mit den Kopfzellen 'Tag' und "
        f"{kopf!r}, gefunden: {len(tabellen)}")
    tabelle = tabellen[0]
    spalte = [th.get_text(strip=True) for th in tabelle.find_all("th")].index(kopf)
    zeilen = tabelle.find("tbody").find_all("tr")
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Ausblick-Datenzeile, gefunden: {len(zeilen)}")
    return [td.get_text(strip=True) for td in zeilen[0].find_all("td")][spalte]


def test_kompaktmail_ohne_herkunfts_zusatz():
    """AC-6-Gegenprobe (Testplan-Zeile AC-6): Given dieselbe Fixture, die im
    HTML-Ausblick der Vollmail NACHWEISLICH die Herkunft 'CAPE' zeigt
    (#1680 S5a) / When dieselbe Ausblick-Zeile in der Kurzformat-Mail
    gerendert wird / Then enthaelt die zugestellte Zeile KEINE der vier
    Zutat-Bezeichnungen -- ``resolve_thunder_day_branch()``/
    ``_compact_thunder_field()`` lesen ``thunder_day_origin`` laut Spec
    (PO-Entscheidung 1) nie.

    Gegenprobe zuerst: ohne den Beleg, dass dieselbe Fixture im HTML-Pfad
    eine Herkunft zeigt, waere die Abwesenheitspruefung im Kompaktformat
    vakuum-gruen (sie waere auch gruen, wenn CAPE nirgends berechnet
    wuerde).

    GEMESSEN: dieser Test ist bereits VOR jeder Implementierung gruen (am
    Stand `71dd8a2d`) -- strukturell erklaerbar, nicht vakuum-gruen: die
    heutige (ungeaenderte) Ausblick-Schleife in ``compact.py`` liest
    ausschliesslich ``tok['thunder_plain']`` und ruft nie einen Code-Pfad
    auf, der ``thunder_day_origin`` anhaengt -- weder vor noch nach dieser
    Scheibe. Die Gegenprobe selbst (HTML zeigt 'CAPE') beweist, dass an
    dieser Fixture ueberhaupt eine Herkunft entstuende, also ist die
    Abwesenheitspruefung nicht vakuum-gruen. Absichern gegen Mutation (c)
    der Spec (Herkunft an den 'day'-Zweig von ``_compact_thunder_field()``
    anhaengen) leistet dieser Test erst NACH der Implementierung -- vorher
    existiert der Zweig noch nicht, den die Mutation treffen wuerde.
    """
    zeile = _mit_herkunft_ausblick_zeile()

    voll = _gew_zelle(_mail([zeile]).email_html)
    assert voll == "leicht @16 · CAPE", (
        f"Gegenprobe gescheitert: die Vollmail-HTML MUSS die Herkunft 'CAPE' "
        f"zeigen, sonst beweist die Kompakt-Pruefung nichts: {voll!r}")

    kompakt_bericht = _mail([zeile], report_config=_KOMPAKT)
    kompakt_ausblick = _kompakt_ausblick_zeile(kompakt_bericht.email_plain)
    for zutat in _ALLE_ZUTATEN:
        assert zutat not in kompakt_ausblick, (
            f"Die Kurzformat-Mail darf keine Zutat {zutat!r} zeigen: "
            f"{kompakt_ausblick!r}")
