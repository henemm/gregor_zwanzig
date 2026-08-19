"""TDD RED — Issue #1680 Scheibe 5a: Herkunft der Gewitterstufe im
Mehrtages-Ausblick (Trip-Mail HTML + Klartext, Telegram-Trendblock,
Compare-Ausblick).

SPEC: docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md v1.1
      (AC-1..AC-10, AC-11a, AC-11b, AC-12, AC-13 — 14 Tests)
KONTEXT: docs/context/feat-1680-s5-ausblick-vorschau-herkunft.md

RED-Ursache (heute gemessen): ``build_outlook_row()``
(``src/output/renderers/email/outlook.py:463-477``) verengt die rohen
``ForecastDataPoint``s selbst zu ``HourlyValue``-Tupeln und wirft dabei
``dp.thunder_level_signals`` weg. ``format_trend_tokens()``
(``email/helpers.py:1005-1020``) kann darum keinen Herkunfts-Token neben
``thunder_day_token`` bilden, und die drei Ausblick-Renderer
(``render_outlook_table``/``render_outlook_plain``/``narrow._outlook_lines``)
zeigen die Stufe ohne die tragende Zutat: heute steht dort ``leicht @16``
statt ``leicht @16 · CAPE``.

PRUEFORT = WIRKORT. Alle Trip-ACs laufen ueber die ECHTE Renderkette bis zum
zugestellten Text: ``TripReportFormatter.format_email()`` liefert
``email_html``/``email_plain``/``telegram_bubbles``/``sms_text`` in EINEM
Lauf; gemessen wird die Gewitter-ZELLE der Ausblick-Tabelle aus dem
fertigen Mail-HTML (nicht der Rueckgabewert eines Bausteins). AC-11a und
AC-11b laufen ueber die echte Vergleichsmail (``render_compare_html`` /
``render_comparison_text``) — AC-11a ohne, AC-11b MIT gesetzter
Metrik-Auswahl, weil der Ortsvergleich zwei voellig getrennte
Ausblick-Renderpfade hat (Spec v1.1, "Am Code gemessen" Punkt 9).

KEIN MOCK-THEATER. Stufen und Traegerlisten entstehen ausschliesslich ueber
die ECHTE Fusion (``providers.thunder_enrichment._fuse_thunder_levels`` mit
den geeichten Leitern aus ``app.model_registry``) — kein im Test getippter
Stufenwert, keine getippte Schwelle. Einzige Laufzeit-Instrumentierung ist
die SONDE in AC-12: dort werden die WERTE der Beschriftungstabelle
``metric_format.THUNDER_SIGNAL_LABEL_DE`` voruebergehend durch eindeutige
Marker ersetzt (in-place, mit Wiederherstellung in ``finally``) — die Spec
verlangt fuer AC-12 ausdruecklich einen Sonden-Nachweis statt einer
Wortsuche. Kein ``Mock``/``patch``/``MagicMock``.

GEGENPROBEN. Jeder Abwesenheits-AC (AC-6, AC-7, AC-10, AC-12, AC-13) belegt
an DERSELBEN Fixture zuerst, dass die Herkunft dort ueberhaupt entstuende —
ohne diese Gegenprobe bewacht ein Abwesenheits-Test nichts (Muster S1-S4).
Genau diese Gegenproben machen die Abwesenheits-Tests heute rot.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur EIGENEN Testdatei aufloesen, nie ueber
# den festen Hauptrepo-Pfad — sonst pruefte dieser Test aus dem Worktree die
# unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from app.day_window import resolve_configured_window  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, TripReportConfig, TripSegment,
)
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.compare_outlook_metric_ids import (  # noqa: E402
    resolve_outlook_metrics,
)
from output.renderers.email.compare_html import render_compare_html  # noqa: E402
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.renderers.comparison import render_comparison_text  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from output.tokens.dto import HourlyValue  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService, summarize_points,
)

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung
# (``metric_format.THUNDER_SIGNAL_LABEL_DE``). Keine davon darf in SMS/
# Premium-SMS auftauchen (AC-12).
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_HEUTE = date(2026, 8, 20)     # Etappe des Briefings
_MORGEN = date(2026, 8, 21)    # kuenftige Etappe = Ausblick-Zeile
_WOCHENTAG = "Di"
_AUSBLICK_UEBERSCHRIFT = "Nächste Etappen"
_COMPARE_UEBERSCHRIFT = "3-Tages-Ausblick"


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, ECHTE Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _MORGEN, cape=None, cin=None, lpi=None,
        dichte=None, hail=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN — Stufe und Traeger rechnet die Fusion.

    Geeichte Leitern der Testregion DE_ALPEN/icon_d2 (gemessen, nicht
    geraten): CAPE 300/750/1200 J/kg, LPI 1/30/50 J/kg, Blitzdichte
    0.003/0.015/0.075 je km2. ``cin=5.0`` liegt im Band "schwacher Deckel"
    (Betrag < 25) und laesst die CAPE-Leiter voll zaehlen.
    """
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
        hail_flag=hail,
    )


def _fusioniere(punkte: list[ForecastDataPoint]) -> list[ForecastDataPoint]:
    """Wendet die ECHTE Fusion in-place an (setzt ``dp.thunder_level`` UND
    ``dp.thunder_level_signals``) — keine im Test getippte Schwelle."""
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    return punkte


def _ruhige_etappe() -> SegmentWeatherData:
    """Die HEUTIGE Etappe des Briefings — bewusst GEWITTERFREI.

    ``cape=200`` liegt unter der niedrigsten Sprosse (300 J/kg) und ergibt
    ueber die echte Fusion ``ThunderLevel.NONE`` mit LEERER Traegerliste.
    Damit ist der Ausblick der EINZIGE Ort der Mail, an dem eine
    Zutat-Bezeichnung entstehen kann — sonst faerbte die Herkunft der
    Stundentabelle aus Scheibe 4 die Gegenproben von AC-12/AC-13 gruen,
    ohne dass diese Scheibe irgendetwas bewirkt haette.
    """
    punkte = _fusioniere([_dp(h, tag=_HEUTE, cape=200.0) for h in range(6, 18)])
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=punkte,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 17, 0, tzinfo=timezone.utc),
        duration_hours=11.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _ausblick_zeile(punkte: list[ForecastDataPoint], *,
                    report_config: TripReportConfig | None = None,
                    traeger_verwerfen: bool = False) -> dict:
    """Eine Ausblick-Zeile GENAU so, wie der Zeitplaner sie baut.

    Wortgleich zu ``trip_report_scheduler._build_multi_day_trend()``
    (``:2064-2081``): Tagesfenster EINMAL ueber ``resolve_configured_window()``
    aus ``trip.report_config`` aufloesen und an ``build_outlook_row()``
    durchreichen, danach ``name`` ergaenzen.

    ``traeger_verwerfen=True`` bildet einen aufgezeichneten Schnappschuss VOR
    Scheibe 1 nach: die Stufe steht am Datenpunkt, die Traegerliste fehlt
    (AC-10).
    """
    punkte = _fusioniere(punkte)
    if traeger_verwerfen:
        for p in punkte:
            p.thunder_level_signals = None
    win_start, win_end = resolve_configured_window(
        getattr(report_config, "day_window_start_hour", None),
        getattr(report_config, "day_window_end_hour", None),
    )
    zeile = build_outlook_row(
        summarize_points(punkte), punkte, _WOCHENTAG, _TZ,
        day_window_start_hour=win_start, day_window_end_hour=win_end,
    )
    zeile["name"] = "Etappe B"
    return zeile


def _mail(zeilen: list[dict], *, report_config: TripReportConfig | None = None):
    """Das ECHTE Trip-Briefing (HTML + Klartext + SMS + Telegram-Bubbles)
    ueber den produktiven Formatierer — Pruefort = Wirkort."""
    return TripReportFormatter().format_email(
        [_ruhige_etappe()], "Test-Trip", "evening",
        display_config=build_default_display_config(), tz=_TZ,
        stage_name="Etappe A", multi_day_trend=zeilen,
        report_config=report_config,
    )


# ---------------------------------------------------------------------------
# Messsonden auf der ZUGESTELLTEN Ausgabe
# ---------------------------------------------------------------------------

def _gew_zelle(html: str, kopf: str = "Gew") -> str:
    """Der Text der Gewitter-Zelle der Ausblick-Tabelle aus fertigem Mail-HTML.

    Die Ausblick-Tabelle ist die EINZIGE Tabelle der Mail mit der Kopfzelle
    "Tag" — daran wird die Flaeche erkannt, nicht an einer Faehigkeit oder
    einem Inhalt, der sich mit dieser Scheibe aendert. Die Spalte wird
    anschliessend ueber ihren Kopf gefunden, nicht ueber einen festen Index —
    eine spaeter eingeschobene Spalte darf diesen Test nicht still
    verschieben.

    ``kopf`` ist die Beschriftung der Gewitter-Spalte: im festen
    Sieben-Spalten-Ausblick "Gew" (Trip und Compare-Altbestand), bei gesetzter
    Metrik-Auswahl der Katalogname "Gewitter" (``outlook_columns()``, AC-11b).
    """
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


def _klartext_ausblick_zeile(text: str, ueberschrift: str = _AUSBLICK_UEBERSCHRIFT) -> str:
    """Die Ausblick-Zeile aus dem Klartext-Block der zugestellten Mail."""
    assert ueberschrift in text, (
        f"Klartext-Ausblick '{ueberschrift}' fehlt in der Mail:\n{text}")
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


def _telegram_ausblick(bericht) -> str:
    """Der Telegram-Ausblick-Block als EINE Zeile.

    ``_outlook_lines()`` bricht an Wortgrenzen auf ``_TG_PROSE_WIDTH = 56``
    um (``narrow._wrap``). Das Wieder-Zusammenfuegen mit einem Leerzeichen
    stellt den Originaltext exakt her, solange kein einzelnes Wort laenger
    als 56 Zeichen ist — deshalb darf hier auf zusammenhaengende Teilstrings
    geprueft werden, ohne AC-3 ("nicht zwingend zusammenhaengend") zu
    verschaerfen.
    """
    bubbles = [b for b in bericht.telegram_bubbles if b.startswith("Ausblick")]
    assert len(bubbles) == 1, (
        f"Erwartet genau EINE Ausblick-Bubble, gefunden: {bubbles!r}")
    return " ".join(bubbles[0].splitlines()[1:])


def _compare_mail(punkte: list[ForecastDataPoint], *,
                  outlook_metrics: list[dict] | None = None) -> tuple[str, str]:
    """Die ECHTE Vergleichsmail (HTML + Klartext) fuer EINEN Ort mit Ausblick.

    ``outlook_metrics=None`` = Altbestand ohne gespeicherte Spaltenauswahl
    (Token-Pfad, AC-11a); eine gesetzte Auswahl geht in den Metrik-Zweig
    (AC-11b). Die Auswahl laeuft durch den produktiven Aufloeser
    ``resolve_outlook_metrics()``, nicht als handgetipptes Dict.
    """
    punkte = _fusioniere(punkte)
    ort = LocationResult(
        location=SavedLocation(id="ort-a", name="Ort A", lat=_LAT, lon=_LON,
                               elevation_m=1000, timezone="UTC"),
        score=50, hourly_data=punkte, outlook_hourly_data=punkte,
    )
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(0, 23), target_date=_MORGEN,
        created_at=datetime(2026, 8, 20, 4, 1),
    )
    return (
        render_compare_html(ergebnis, outlook_enabled=True,
                            outlook_metrics=outlook_metrics),
        render_comparison_text(ergebnis, outlook_enabled=True,
                               outlook_metrics=outlook_metrics),
    )


def _ohne_zeitstempel(text: str) -> str:
    """Blendet die einzige laufzeitabhaengige Zeile der Kompakt-Mail aus."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.startswith("Generated:")
    )


# ---------------------------------------------------------------------------
# AC-1 bis AC-5: der Wortlaut in den drei Kanaelen
# ---------------------------------------------------------------------------

def test_ac1_html_ausblickzelle_nennt_die_tragende_zutat():
    """AC-1: Given eine kuenftige Etappe, deren Tages-Gewitterstufe im
    Tagesfenster von genau einer Zutat getragen wird / When die
    HTML-Ausblick-Tabelle der Trip-Vollmail gerendert wird / Then steht in
    der Gewitter-Spalte dieser Zeile die Stufe mit Uhrzeit, gefolgt von
    " · " und der deutschen Bezeichnung der Zutat (z. B. "leicht @16 · CAPE").

    Exakte Gleichheit statt ``in``: die Herkunft muss HINTER der Uhrzeit
    stehen (Pflicht-Mutation (f) der Spec haengt sie davor).
    """
    bericht = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])])
    zelle = _gew_zelle(bericht.email_html)
    assert zelle == "leicht @16 · CAPE", (
        f"Die Gewitter-Zelle des HTML-Ausblicks muss die tragende Zutat "
        f"hinter der Uhrzeit nennen. Erwartet 'leicht @16 · CAPE', "
        f"erhalten: {zelle!r}")


def test_ac2_klartext_ausblick_traegt_denselben_zusatz():
    """AC-2: Given dieselbe Etappe / When der Klartext-Ausblick derselben Mail
    gerendert wird / Then traegt das Gewitterfeld denselben Zusatz im selben
    Wortlaut, hinter der Onset-Stunde ("⚡leicht@16 · CAPE").

    ⚠️ Abgeloest durch #1493 (2026-08-18): der urspruengliche Wortlaut dieses
    AC lautete "… — der Klartext fuehrt wie bisher keine Tagesuhrzeit", und
    die Zusicherung war "⚡leicht · CAPE" OHNE Stunde. #1493 fuehrt die
    Onset-Stunde im Klartext- und Kompakt-Ausblick ein (Spec
    ``feat_1493_gewitter_onset_sichtbar.md``, AC-3/AC-4; Ablose-Vermerk in
    ``feat_1680_s5a_gewitter_herkunft_ausblick.md`` AC-2/AC-13). Unveraendert
    bleibt die eigentliche Aussage dieses Tests: der Herkunfts-Zusatz "· CAPE"
    steht HINTER dem Gewitterfeld und ist im Klartext derselbe wie im HTML.
    """
    bericht = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])])
    zeile = _klartext_ausblick_zeile(bericht.email_plain)
    assert "⚡leicht@16 · CAPE" in zeile, (
        f"Der Klartext-Ausblick muss '⚡leicht@16 · CAPE' zeigen (Onset-Stunde "
        f"am Gewitterfeld seit #1493): {zeile!r}")


def test_ac3_telegram_trendblock_nennt_die_zutat():
    """AC-3: Given dieselbe Etappe / When der Telegram-Trendblock gerendert
    wird / Then nennt auch er die Zutat hinter der Tagesstufe. Der Inhalt muss
    im selben Ausblick-Block stehen, nicht zwingend als zusammenhaengender
    Teilstring — die Breite von 56 Zeichen darf umbrechen (deshalb wird der
    Block vor der Pruefung wieder zusammengefuegt, s. ``_telegram_ausblick``)."""
    bericht = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])])
    block = _telegram_ausblick(bericht)
    assert "⚡leicht@16 · CAPE" in block, (
        f"Der Telegram-Ausblick muss '⚡leicht@16 · CAPE' zeigen: {block!r}")


def test_ac4_zwei_tragende_zutaten_werden_beide_genannt():
    """AC-4: Given eine Etappe, deren Hoechststufe im Tagesfenster von ZWEI
    Zutaten gleichzeitig getragen wird / When der Ausblick gerendert wird /
    Then werden BEIDE Zutaten genannt, mit ", " verbunden (Auslegung (ii):
    alle tragenden Signale, kein Gewinner gekuert). Reihenfolge = die von
    ``union_of_max_carriers()`` gelieferte: dedupliziert, in Erstauftritts-
    Reihenfolge ueber die betrachteten Stunden (Spec v1.1).

    Zwei Fixturen, weil sie verschiedene Fehler fangen:
    (a) EIN Punkt mit zwei Zutaten — Erstauftritt ist hier die Reihenfolge in
        ``_signal_levels()``, also die Katalogreihenfolge: "CAPE,
        Blitzpotenzial". Prueft Verbinder und Reihenfolge innerhalb einer
        Stunde.
    (b) ZWEI Punkte mit je EINER Zutat — Erstauftritt ist hier die ZEITLICHE
        Reihenfolge: 15 Uhr (Blitzpotenzial) vor 16 Uhr (CAPE), also
        "Blitzpotenzial, CAPE". Nur (b) faellt bei der Pflicht-Mutation (c)
        der Spec ("union_of_max_carriers durch 'erste Traegerliste'
        ersetzen"); bei (a) waere die erste Liste zufaellig schon die
        Vereinigung.

    Beide Erwartungen sind exakt statt reihenfolge-unempfindlich formuliert:
    seit v1.1 legt die Spec die Reihenfolge fest, und eine festgelegte Regel
    ohne Test ist keine Regel. Dass DIESELBEN zwei Zutaten je nach Verteilung
    auf eine oder zwei Stunden in umgekehrter Reihenfolge erscheinen, ist die
    ausdrueckliche Spec-Aussage ("bei einem einzelnen Punkt die
    Katalogreihenfolge, ueber mehrere Stunden hinweg die zeitliche") — kein
    Testartefakt.
    """
    zelle_a = _gew_zelle(_mail([
        _ausblick_zeile([_dp(16, cape=1500.0, cin=5.0, lpi=60.0)])
    ]).email_html)
    assert zelle_a == "hoch @16 · CAPE, Blitzpotenzial", (
        f"Beide Traeger der Hoechststufe muessen mit ', ' verbunden in "
        f"Erstauftritts-Reihenfolge erscheinen — innerhalb EINER Stunde ist "
        f"das die Katalogreihenfolge: {zelle_a!r}")

    zelle_b = _gew_zelle(_mail([_ausblick_zeile(
        [_dp(15, lpi=60.0), _dp(16, cape=1500.0, cin=5.0)]
    )]).email_html)
    assert zelle_b == "hoch @15 · Blitzpotenzial, CAPE", (
        f"Tragen ZWEI Stunden des Tagesfensters die Hoechststufe ueber "
        f"verschiedene Zutaten, muessen BEIDE erscheinen (Vereinigung, nicht "
        f"die erste Liste) — in zeitlicher Erstauftritts-Reihenfolge: "
        f"{zelle_b!r}")


def test_ac5_herkunft_steht_vor_dem_hagel_zusatz():
    """AC-5: Given eine Etappe mit Gewitter UND Hagel-Kennzeichen / When der
    Ausblick gerendert wird / Then steht die Herkunft VOR dem Hagel-Zusatz,
    und der Hagel-Zusatz bleibt wortgleich erhalten
    ("leicht @16 · CAPE · Hagel: ja")."""
    bericht = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0, hail=True)])])
    zelle = _gew_zelle(bericht.email_html)
    assert zelle == "leicht @16 · CAPE · Hagel: ja", (
        f"Die Herkunft gehoert zwischen Uhrzeit und Hagel-Zusatz, der Hagel-"
        f"Zusatz bleibt wortgleich: {zelle!r}")
    zeile = _klartext_ausblick_zeile(bericht.email_plain)
    # #1493: Onset-Stunde im Klartext-Ausblick; Reihenfolge Herkunft vor
    # Hagel -- der Gegenstand dieses Tests -- unveraendert.
    assert "⚡leicht@16 · CAPE · Hagel: ja" in zeile, (
        f"Dieselbe Reihenfolge im Klartext-Ausblick: {zeile!r}")


# ---------------------------------------------------------------------------
# AC-6 bis AC-8, AC-10: die Abwesenheits-Zusicherungen (je mit Gegenprobe)
# ---------------------------------------------------------------------------

def test_ac6_nachtteil_bleibt_ohne_herkunft():
    """AC-6: Given eine Etappe mit Gewitter IM NACHTFENSTER / When der Ausblick
    gerendert wird / Then traegt der Nachtteil KEINE Herkunft, und der
    Nachtteil bleibt gegenueber heute zeichengleich.

    Gegenprobe an DERSELBEN Fixture: dieselben Stundenpunkte, nur mit einem
    Tagesfenster 0-3 statt 4-19 — dasselbe Gewitter liegt dann im Tagesteil
    und die Herkunft erscheint sehr wohl. Ohne diese Gegenprobe waere der
    Test auch dann gruen, wenn die Herkunft nirgends erschiene.
    """
    nacht = _gew_zelle(_mail([_ausblick_zeile([_dp(2, cape=400.0, cin=5.0)])]).email_html)
    assert nacht == "nachts leicht @2", (
        f"Der Nachtteil bleibt zeichengleich zu heute und traegt KEINE "
        f"Herkunft: {nacht!r}")

    tag = _gew_zelle(_mail([_ausblick_zeile(
        [_dp(2, cape=400.0, cin=5.0)],
        report_config=TripReportConfig(day_window_start_hour=0, day_window_end_hour=3),
    )]).email_html)
    assert tag == "leicht @2 · CAPE", (
        f"Gegenprobe gescheitert: laege dasselbe Gewitter im Tagesfenster, "
        f"MUESSTE die Herkunft erscheinen — sonst beweist der Nacht-Fall "
        f"nichts: {tag!r}")


def test_ac7_ohne_gewitter_bleibt_die_zelle_zeichengleich():
    """AC-7: Given eine Etappe OHNE Gewitter im Tagesfenster / When der Ausblick
    gerendert wird / Then enthaelt die Gewitterzelle WEDER eine
    Zutat-Bezeichnung NOCH einen zusaetzlichen ·-Trenner — sie bleibt
    zeichengleich zu heute ("–" bzw. "⚡–").

    Gegenprobe an DERSELBEN Fixture: dieselbe Stunde, nur mit einem CAPE-Wert
    ueber der niedrigsten Sprosse (400 statt 50 J/kg). ``cape=50`` erzeugt
    ueber die echte Fusion ein ECHTES ``ThunderLevel.NONE`` mit leerer
    Traegerliste — kein Python-``None``, das schon ein frueher Guard
    abfinge.
    """
    ruhig = _mail([_ausblick_zeile([_dp(16, cape=50.0)])])
    zelle_ruhig = _gew_zelle(ruhig.email_html)
    assert zelle_ruhig == "–", (
        f"Ohne Gewitter im Tagesfenster bleibt die Zelle zeichengleich '–' "
        f"— kein Zutat-Name, kein zusaetzliches '·': {zelle_ruhig!r}")
    zeile_ruhig = _klartext_ausblick_zeile(ruhig.email_plain)
    assert zeile_ruhig.rstrip().endswith("⚡–"), (
        f"Der Klartext-Ausblick bleibt zeichengleich '⚡–': {zeile_ruhig!r}")

    laut = _gew_zelle(_mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])]).email_html)
    assert laut == "leicht @16 · CAPE", (
        f"Gegenprobe gescheitert: mit erreichter Stufe MUSS die Herkunft "
        f"erscheinen, sonst beweist die ruhige Zelle nichts: {laut!r}")


def test_ac8_alt_aufrufer_zeilen_bleiben_byte_identisch():
    """AC-8: Given Ausblick-Zeilen, die KEINE Traegerinformation fuehren
    (Alt-Aufrufer, aufgezeichnete Fixtures) / When HTML- und Klartext-Ausblick
    gerendert werden / Then ist die Ausgabe byte-identisch zu heute.

    Die hier gebaute Zeile ist ein Alt-Aufrufer-Dict in genau der Gestalt der
    aufgezeichneten Golden-Fixturen unter
    ``tests/fixtures/outlook_trip_parity/`` (Zeilenbau ``parity_rows()``):
    feste Schluessel, ``hourly_thunder`` als reine ``HourlyValue``-Tupel,
    KEINE Traegerdaten. Weil diese Fixturen keine Traeger fuehren, MUSS die
    Ausgabe zeichengleich bleiben — der unveraenderte Bestandswaechter
    ``tests/tdd/test_trip_outlook_parity.py`` (heute gruen, gemessen) ist der
    formale Nachweis und darf weder angefasst noch neu erzeugt werden. Hier
    wird nur die Verhaltensseite geprueft: keine Zutat, kein zusaetzliches
    ``·``.

    Wirksamkeits-Gegenprobe: dieselbe Stunde ueber die echte Kette (MIT
    Traegern) zeigt die Herkunft sehr wohl.
    """
    alt_zeile = dict(
        weekday=_WOCHENTAG, name="Etappe B", note=None,
        temp_lo=9, temp_hi=21, precip_mm=2.5, wind_dir="W", wind_kmh=18,
        thunder="MED", rain_probability_pct=55, confidence_pct=82,
        hourly_precip=(HourlyValue(hour=14, value=2.1),),
        hourly_wind=(HourlyValue(hour=15, value=18.0),),
        hourly_gust=(HourlyValue(hour=15, value=44.0),),
        hourly_thunder=(HourlyValue(hour=16, value=2.0),),
    )
    alt = _mail([alt_zeile])
    zelle_alt = _gew_zelle(alt.email_html)
    assert zelle_alt == "mittel @16", (
        f"Eine Zeile ohne Traegerinformation bleibt zeichengleich zu heute: "
        f"{zelle_alt!r}")
    zeile_alt = _klartext_ausblick_zeile(alt.email_plain)
    for zutat in ALLE_ZUTATEN:
        assert zutat not in zeile_alt, (
            f"Alt-Aufrufer-Zeile darf keine Zutat '{zutat}' zeigen: {zeile_alt!r}")

    neu = _gew_zelle(_mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])]).email_html)
    assert neu == "leicht @16 · CAPE", (
        f"Gegenprobe gescheitert: eine Zeile MIT Traegern MUSS die Herkunft "
        f"zeigen, sonst beweist die Alt-Zeile nichts: {neu!r}")


def test_ac10_stufe_ohne_traegerliste_bleibt_ohne_herkunft():
    """AC-10: Given eine Etappe, deren Wetterpunkte eine Gewitterstufe tragen,
    fuer die KEINE Traegerliste vorliegt (aufgezeichneter Schnappschuss vor
    Scheibe 1) / When der Ausblick gerendert wird / Then erscheint die Stufe
    OHNE Herkunft — nie eine Herkunft, die nicht zur gezeigten Stufe gehoert
    (AC-12-Regel aus Scheibe 1).

    Gegenprobe an DERSELBEN Fixture: dieselben Stundenpunkte MIT ihrer
    Traegerliste zeigen die Herkunft sehr wohl.
    """
    ohne = _gew_zelle(_mail([_ausblick_zeile(
        [_dp(16, cape=400.0, cin=5.0)], traeger_verwerfen=True,
    )]).email_html)
    assert ohne == "leicht @16", (
        f"Ohne Traegerliste erscheint die Stufe unveraendert und OHNE "
        f"Herkunfts-Zusatz: {ohne!r}")

    mit = _gew_zelle(_mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])]).email_html)
    assert mit == "leicht @16 · CAPE", (
        f"Gegenprobe gescheitert: mit Traegerliste MUSS die Herkunft "
        f"erscheinen, sonst beweist der Alt-Schnappschuss nichts: {mit!r}")


# ---------------------------------------------------------------------------
# AC-9: EINE Fensterauflösung fuer Stufe UND Herkunft
# ---------------------------------------------------------------------------

def test_ac9_stufe_und_herkunft_stammen_aus_demselben_tagesfenster():
    """AC-9: Given ein Trip mit einem vom Standard ABWEICHENDEN Tagesfenster
    (nicht 4-19 Uhr) und einem Gewitter, das nur in diesem abweichenden
    Fenster liegt / When der Ausblick gerendert wird / Then stammen angezeigte
    Stufe UND angezeigte Herkunft aus demselben Fenster — die Herkunft wird an
    derselben Stelle und mit demselben Fensterwert ermittelt wie
    ``thunder_day_token``.

    Die Fixture traegt ZWEI Stunden mit derselben Hoechststufe (hoch), aber
    verschiedenen Zutaten: 10 Uhr ueber die Blitzdichte, 21 Uhr ueber CAPE.
    Damit ist die Fensterfrage entscheidbar statt zufaellig richtig:
    - Fenster 20-23 → Tagesteil 21 Uhr, Herkunft CAPE, "Blitzdichte" darf
      NICHT erscheinen (faellt bei Pflicht-Mutation (b), Fensterfilterung
      entfernt: dann stuende dort "CAPE, Blitzdichte").
    - Standardfenster 4-19 an DENSELBEN Punkten → Tagesteil 10 Uhr, Herkunft
      Blitzdichte. Beide Faelle zusammen belegen, dass Stufe und Herkunft
      MITEINANDER umschalten.
    Der Nachtteil traegt in beiden Faellen keine Herkunft (AC-6).
    """
    abweichend = _gew_zelle(_mail([_ausblick_zeile(
        [_dp(10, dichte=0.1), _dp(21, cape=1500.0, cin=5.0)],
        report_config=TripReportConfig(day_window_start_hour=20, day_window_end_hour=23),
    )]).email_html)
    assert abweichend == "hoch @21 · CAPE · nachts hoch @10", (
        f"Im abweichenden Fenster 20-23 muessen Stufe UND Herkunft aus der "
        f"21-Uhr-Stunde stammen (CAPE), nicht aus der 10-Uhr-Stunde "
        f"(Blitzdichte): {abweichend!r}")

    standard = _gew_zelle(_mail([_ausblick_zeile(
        [_dp(10, dichte=0.1), _dp(21, cape=1500.0, cin=5.0)],
    )]).email_html)
    assert standard == "hoch @10 · Blitzdichte · nachts hoch @21", (
        f"Im Standardfenster 4-19 muessen Stufe UND Herkunft aus der "
        f"10-Uhr-Stunde stammen: {standard!r}")


# ---------------------------------------------------------------------------
# AC-11a/AC-11b: der Ortsvergleich hat ZWEI Ausblick-Renderpfade
# ---------------------------------------------------------------------------

def test_ac11a_compare_ausblick_ohne_metrikauswahl_erbt_die_herkunft():
    """AC-11a: Given einen Ortsvergleich OHNE Metrik-Auswahl fuer den Ausblick
    (Altbestand, ``outlook_metrics`` fehlt) / When dessen Ausblick-Tabelle
    gerendert wird / Then nennt auch sie die Herkunft ueber denselben
    Token-Pfad wie der Trip — der geteilte Zeilenbau wird NICHT trip-seitig
    abgeschaltet (Trip/Compare-Teilungs-Invariante).

    Geprueft wird die ECHTE Vergleichsmail (``render_compare_html`` /
    ``render_comparison_text``), nicht der Baustein: "CAPE" steht in dieser
    Mail seit S1/S3 auch in der Uebersicht und in der Stundentabelle, deshalb
    wird gezielt die Gewitter-ZELLE des Ausblick-Blocks bzw. die Zeile unter
    "3-Tages-Ausblick" gemessen.

    ⚠️ Abgeloest durch #1493 (PO-Entscheid 2026-08-18): die Klartext-Erwartung
    lautete urspruenglich "⚡leicht · CAPE" — OHNE Tagesuhrzeit, in
    Uebereinstimmung mit dem damals gueltigen #1680 S5a AC-2. Mit #1493 fuehrt
    der geteilte Zeilenbau (``render_outlook_plain()``, aufgerufen aus
    ``comparison.py:360``) die Onset-Stunde, und der Ortsvergleich erbt sie —
    genau so, wie dieser Test es fuer die Herkunft schon festhaelt: der
    geteilte Zeilenbau wird nicht trip-seitig abgeschaltet. Die
    HTML-Zusicherung bleibt unveraendert, die Ausblickzelle fuehrte die Stunde
    schon immer. Eigenstaendiger Waechter dieser Invariante:
    ``test_thunder_level_word_and_onset_hour.py::test_ac9_…``.
    """
    html, text = _compare_mail([_dp(16, cape=400.0, cin=5.0)])
    zelle = _gew_zelle(html)
    assert zelle == "leicht @16 · CAPE", (
        f"Der Compare-Ausblick erbt den geteilten Zeilenbau und muss die "
        f"Herkunft ebenso nennen: {zelle!r}")
    zeile = _klartext_ausblick_zeile(text, _COMPARE_UEBERSCHRIFT)
    assert "⚡leicht@16 · CAPE" in zeile, (
        f"Auch der Klartext-Ausblick der Vergleichsmail muss Herkunft UND "
        f"Onset-Stunde nennen (seit #1493): {zeile!r}")


def test_ac11b_compare_ausblick_mit_metrikauswahl_nennt_die_herkunft():
    """AC-11b: Given einen Ortsvergleich MIT gesetzter Metrik-Auswahl (der
    Regelfall jedes ueber die Oberflaeche gepflegten Vergleichs) und einer
    gewaehlten Gewitter-Spalte / When dessen Ausblick-Tabelle gerendert wird /
    Then nennt die Gewitter-Zelle ebenfalls die tragende Zutat. Die Herkunft
    stammt dort aus DERSELBEN Rechnung wie die dort gezeigte Stufe (dem
    Tages-Aggregat ``summarize_points()``), nicht aus dem Tagesfenster — beide
    gehoeren zusammen (AC-10-Regel). Nachweis in HTML UND Klartext.

    Dieser Zweig umgeht den Token-Pfad vollstaendig: frueher Return
    ``outlook.py:148``, ``continue`` ``outlook.py:342``; die Zelle entsteht in
    ``format_outlook_value()`` → ``_fmt_thunder()``. Deshalb steht dort auch
    KEINE ``@``-Uhrzeit — erwartet wird ``leicht · CAPE``, nicht
    ``leicht @16 · CAPE``.

    Zwei Fixturen, weil sie verschiedene Fehler fangen:
    (a) EINE Stunde mit CAPE — Tages-Aggregat und Tagesfenster sind sich einig;
        prueft Wortlaut und Klartext-Pfad.
    (b) NACHT-Stunde ``hoch`` ueber CAPE + TAG-Stunde ``leicht`` ueber
        Blitzdichte — Tages-Aggregat (``hoch``/CAPE) und Tagesfenster-Token
        (``leicht``/Blitzdichte) sagen VERSCHIEDENES. Nur damit ist
        entscheidbar, ob Stufe und Herkunft aus derselben Rechnung stammen:
        wer hier den Token-Pfad-Traeger anhaengt, schreibt "hoch · Blitzdichte"
        — eine Herkunft, die nicht zur gezeigten Stufe gehoert (genau der
        AC-12-Fehler aus Scheibe 1).
    """
    auswahl = resolve_outlook_metrics([
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "thunder", "aggregation": "max"},
    ])
    assert auswahl and len(auswahl) == 2, (
        f"Die Auswahl muss durch den produktiven Aufloeser kommen und die "
        f"Gewitter-Spalte enthalten: {auswahl!r}")

    html_a, text_a = _compare_mail([_dp(16, cape=400.0, cin=5.0)],
                                   outlook_metrics=auswahl)
    zelle_a = _gew_zelle(html_a, kopf="Gewitter")
    assert zelle_a == "leicht · CAPE", (
        f"Auch der Metrik-Zweig des Compare-Ausblicks muss die tragende Zutat "
        f"nennen (ohne Uhrzeit, wie dort ueblich): {zelle_a!r}")
    zeile_a = _klartext_ausblick_zeile(text_a, _COMPARE_UEBERSCHRIFT)
    assert "Gewitter leicht · CAPE" in zeile_a, (
        f"Der Klartext-Ausblick des Metrik-Zweigs muss dieselbe Herkunft "
        f"zeigen: {zeile_a!r}")

    html_b, _ = _compare_mail(
        [_dp(2, cape=1500.0, cin=5.0), _dp(16, dichte=0.005)],
        outlook_metrics=auswahl,
    )
    zelle_b = _gew_zelle(html_b, kopf="Gewitter")
    assert zelle_b == "hoch · CAPE", (
        f"Stufe UND Herkunft muessen im Metrik-Zweig aus dem Tages-Aggregat "
        f"stammen (hoch ueber CAPE aus der Nachtstunde), nicht aus dem "
        f"Tagesfenster: {zelle_b!r}")
    assert "Blitzdichte" not in zelle_b, (
        f"Die Zutat der Tagesfenster-Stunde gehoert NICHT zur gezeigten "
        f"Aggregat-Stufe und darf dort nicht erscheinen: {zelle_b!r}")


# ---------------------------------------------------------------------------
# AC-12/AC-13: die beiden bewusst ausgenommenen Ausgabewege
# ---------------------------------------------------------------------------

def test_ac12_sms_und_premium_sms_bleiben_ohne_herkunft():
    """AC-12: Given einen Trip-Briefing-Versand ueber SMS bzw. Premium-SMS /
    When der Text erzeugt wird / Then enthaelt er KEINE der vier
    Zutat-Bezeichnungen. Nachweis per Sonde (Beschriftungsfunktion zur
    Laufzeit markieren), nicht per Wortsuche — mit Gegenprobe, dass die Sonde
    in E-Mail und Telegram anschlaegt.

    Die Sonde ersetzt die WERTE von ``THUNDER_SIGNAL_LABEL_DE`` in-place durch
    eindeutige Marker. In-place, weil ``thunder_signal_label()`` die Tabelle
    zur AUFRUFZEIT liest — die Sonde wirkt damit unabhaengig davon, wie die
    Implementierung die Funktion importiert. Wiederherstellung in ``finally``.

    SMS und Premium-SMS teilen sich ``report.sms_text`` (ein Text, zwei
    Transporte); geprueft wird zusaetzlich der tatsaechliche Rueckfall
    ``sms_text or email_plain``.
    """
    from output import metric_format

    sonde = "ZUTATSONDE"
    original = dict(metric_format.THUNDER_SIGNAL_LABEL_DE)
    try:
        for schluessel in list(metric_format.THUNDER_SIGNAL_LABEL_DE):
            metric_format.THUNDER_SIGNAL_LABEL_DE[schluessel] = f"{sonde}-{schluessel}"
        bericht = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])])

        assert sonde in _gew_zelle(bericht.email_html), (
            "Gegenprobe gescheitert: die Sonde muss in der HTML-Ausblick-"
            "Zelle anschlagen, sonst beweist ihre Abwesenheit in der SMS "
            f"nichts. Zelle: {_gew_zelle(bericht.email_html)!r}")
        assert sonde in _telegram_ausblick(bericht), (
            "Gegenprobe gescheitert: die Sonde muss im Telegram-Ausblick "
            f"anschlagen: {_telegram_ausblick(bericht)!r}")

        assert bericht.sms_text, (
            "sms_text muss immer erzeugt werden — sonst greift der Rueckfall "
            "`sms_text or email_plain` und die Herkunft koennte in die SMS "
            "durchsickern")
        zugestellt = bericht.sms_text or bericht.email_plain
        assert sonde not in zugestellt, (
            f"SMS/Premium-SMS sind bewusst OHNE Herkunft — die Sonde darf "
            f"dort NICHT anschlagen: {zugestellt!r}")
        for zutat in ALLE_ZUTATEN:
            assert zutat not in zugestellt, (
                f"'{zutat}' darf im SMS-Text nicht vorkommen: {zugestellt!r}")
    finally:
        metric_format.THUNDER_SIGNAL_LABEL_DE.clear()
        metric_format.THUNDER_SIGNAL_LABEL_DE.update(original)


def test_ac13_kompaktmail_bleibt_zeichengleich():
    """AC-13: Given ein Trip-Briefing im KOMPAKTFORMAT / When die Mail
    gerendert wird / Then bleibt deren Ausblick-Block ("Naechste Etappen")
    zeichengleich zu heute — er liest ``thunder_plain`` und wird von dieser
    Scheibe nicht beruehrt.

    "Zeichengleich zu heute" wird als Unempfindlichkeit gegen die
    Traegerinformation gemessen: dieselbe Etappe einmal MIT und einmal OHNE
    Traegerliste muss denselben Kompakttext ergeben (bis auf die
    laufzeitabhaengige "Generated:"-Zeile).

    Gegenprobe an DERSELBEN Fixture: die VOLLMAIL derselben Zeile zeigt die
    Herkunft sehr wohl — ohne diese Gegenprobe waere der Test auch dann
    gruen, wenn die Scheibe gar nichts bewirkte.
    """
    kompakt = TripReportConfig(email_format="compact")
    mit = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])],
                report_config=kompakt).email_plain
    ohne = _mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)],
                                  traeger_verwerfen=True)],
                 report_config=kompakt).email_plain
    assert _ohne_zeitstempel(mit) == _ohne_zeitstempel(ohne), (
        "Die Kompakt-Mail darf sich durch die Traegerinformation NICHT "
        f"aendern.\nMIT Traegern:\n{mit}\nOHNE Traeger:\n{ohne}")
    for zutat in ALLE_ZUTATEN:
        assert zutat not in mit, (
            f"Die Kompakt-Mail darf keine Zutat '{zutat}' zeigen:\n{mit}")

    voll = _gew_zelle(_mail([_ausblick_zeile([_dp(16, cape=400.0, cin=5.0)])]).email_html)
    assert voll == "leicht @16 · CAPE", (
        f"Gegenprobe gescheitert: die Vollmail DERSELBEN Etappe MUSS die "
        f"Herkunft zeigen, sonst beweist die Kompakt-Mail nichts: {voll!r}")
