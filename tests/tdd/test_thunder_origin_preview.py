"""TDD RED — Issue #1680 Scheibe 5b: Herkunft der Gewitterstufe in der
Gewitter-Vorschau (``+1``/``+2``-Block der Trip-Vollmail, Klartext + HTML).

SPEC: docs/specs/modules/feat_1680_s5b_gewitter_herkunft_vorschau.md v1.1
      (AC-1..AC-11; AC-12/AC-13 sind Browser-Nachweise, AC-14 ist der
      IMAP-Nachweis an der zugestellten Staging-Mail — alle drei sind
      bewusst NICHT Teil dieser Datei)
KONTEXT: docs/context/feat-1680-s5b-vorschau-herkunft.md

RED-Ursache (heute gemessen, Stand 5b2cecd3): beide Bauwege des
Vorschau-Eintrags bauen ``text`` ohne die tragende Zutat.
``_thunder_entry_from_trend_row()``
(``src/services/trip_report_scheduler.py:2251``) hat die Traegerquelle
``row["hourly_thunder_signals"]`` (aus S5a, ``email/outlook.py:545-547``)
bereits vorliegen und liest sie nicht; ``_build_thunder_forecast()``
(``:2442``) ruft ``summarize_points(thunder_dps)`` (``:2587``) und liest
davon nur ``.hail_flag``, nicht ``.thunder_level_max_signals``. In der Mail
steht deshalb heute ``21.08.2026: ⚡ Gewitter möglich ab 14:00`` statt
``... ab 14:00 · CAPE``.

PRUEFORT = WIRKORT. Kein Test bleibt am Eintrags-Dict stehen. Jeder
Wortlaut-AC misst die Zeile der Gewitter-Vorschau in der FERTIGEN Mail,
und zwar in BEIDEN Fassungen: der Klartext-Block „━━ Gewitter-Vorschau ━━"
(``email/plain.py:311-332``) und der HTML-Block „⚡ Gewitter-Vorschau"
(``email/html.py:1311-1329``). Genau an dieser Stelle ist dieser Strang
dreimal auf ein gruen getestetes, wirkungsloses Kriterium hereingefallen
(S2 falscher Textzweig, S5a falscher Compare-Zweig, S5a Punkt A).

DIE BEIDEN BAUWEGE SIND NICHT AUSTAUSCHBAR (Spec „Am Code gemessen" 1).
Die Vorschau erscheint nur bei ``not outlook_active`` mit
``outlook_active = show_outlook and bool(multi_day_trend)``:

  * Morgen-Standard: kein Trend  ⇒ Vorschau sichtbar ⇒ RUECKFALLPFAD
    (``_build_thunder_forecast``) — der Regelfall, AC-1.
  * Abend-Standard: Trend + ``show_outlook=True`` ⇒ Vorschau unsichtbar.
  * Abend mit ``show_outlook=False`` ⇒ Vorschau sichtbar ⇒ PRIMAERPFAD
    (``_thunder_entry_from_trend_row``) — AC-2, AC-7, AC-8.

Woran der jeweils gemeinte Bauweg festgemacht ist — strukturell, nicht per
Zusicherung im Kommentar:

  * RUECKFALL: ``multi_day_trend=None`` ⇒ ``trend_by_date`` ist leer ⇒
    ``_thunder_entry_from_trend_row()`` kann gar nicht aufgerufen werden
    (``trip_report_scheduler.py:2199-2211``). Ein vorhandener „+1"-Eintrag
    KANN nur aus ``_build_thunder_forecast()`` stammen.
  * PRIMAER: der Netzabruf liefert eine LEERE Segmentliste ⇒ der Rueckfall
    liefert strukturell ``{}`` (``:2217-2224``). Ein vorhandener
    „+1"-Eintrag KANN nur aus der Trend-Zeile stammen.

Beide Bedingungen werden in ``_rueckfall()``/``_primaer()`` mitgeprueft,
damit ein spaeterer Umbau der Weiche nicht still den falschen Pfad misst.

KEIN MOCK-THEATER. Stufen und Traegerlisten entstehen ausschliesslich ueber
die ECHTE Fusion (``providers.thunder_enrichment._fuse_thunder_levels`` mit
den geeichten Leitern aus ``app.model_registry``) — keine im Test getippte
Stufe, keine getippte Schwelle. Der Vorschau-Eintrag entsteht ueber die
ECHTE Weiche ``_build_thunder_forecast_from_trend_or_fetch()`` des
produktiven Zeitplaners, die Mail ueber den produktiven
``TripReportFormatter.format_email()``. Kein ``Mock``/``patch``/
``MagicMock``. Ersetzt ist genau EIN Baustein: der Netzabruf
``_collect_future_stage_weather()`` (Unterklasse ``_ZeitplanerOhneNetz``) —
er liefert im Produktivbetrieb nichts anderes als die hier gebauten
``SegmentWeatherData``, und die Kern-Testschicht darf kein Netz benutzen.
Einzige Laufzeit-Instrumentierung ist die SONDE in AC-9 (Spec verlangt
dort ausdruecklich eine Sonde statt einer Wortsuche).

GEGENPROBEN. Jeder Abwesenheits-AC (AC-6, AC-8, AC-9, AC-10, AC-11) belegt
an DERSELBEN Fixture zuerst, dass die Herkunft dort ueberhaupt entstuende —
ohne diese Gegenprobe waere ein Abwesenheits-Test auch dann gruen, wenn die
ganze Kette nichts produziert (vakuum-gruen).
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
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_report_scheduler import (  # noqa: E402
    TripReportSchedulerService,
)
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService, summarize_points,
)

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung
# (``metric_format.THUNDER_SIGNAL_LABEL_DE``). Keine davon darf in SMS/
# Premium-SMS (AC-9) oder in Telegram/Kompakt-Mail (AC-10) auftauchen.
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_HEUTE = date(2026, 8, 20)     # Etappe des Briefings (Bezugstag)
# Der EINE Zeitpunkt des Briefing-Aufbaus (#1727 S5b, ADR-0051 Regel 3): der
# Produktivpfad bindet ihn oben einmal (`trip_report_scheduler.py:1136`,
# `preview_service.py:223`) und reicht ihn durch. Hier fest auf den Morgen des
# Bezugstags gesetzt, in DERSELBEN Zone, in der die ganze Fixture rechnet —
# ein `datetime.now()` machte den Test von der Systemuhr abhaengig.
_JETZT = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)
_MORGEN = date(2026, 8, 21)    # die "+1"-Vorschau-Etappe
_DATUM = "21.08.2026"          # so schreibt der Eintrag sein Datum
_KLARTEXT_UEBERSCHRIFT = "━━ Gewitter-Vorschau ━━"
_HTML_UEBERSCHRIFT = "Gewitter-Vorschau"


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, ECHTE Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _MORGEN, cape=None, cin=None, lpi=None,
        dichte=None, hail=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN — Stufe und Traeger rechnet die Fusion.

    Geeichte Leitern der Testregion DE_ALPEN/icon_d2 (gemessen ueber
    ``model_registry``, nicht geraten): CAPE 300/750/1200 J/kg, LPI
    1/30/50 J/kg, Blitzdichte 0.003/0.015/0.075 je km2. ``cin=5.0`` liegt im
    Band „schwacher Deckel" (Betrag < 25) und laesst die CAPE-Leiter voll
    zaehlen.
    """
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
        hail_flag=hail,
    )


def _eine_zutat_14uhr() -> list[ForecastDataPoint]:
    """Die Standard-Fixture „genau EINE tragende Zutat im Tagesfenster":
    14 Uhr, CAPE 800 J/kg bei schwachem Deckel → ueber die echte Fusion
    ``MED`` mit der Traegerliste ``['cape']``, im Text „· CAPE".

    ALS FUNKTION statt als Konstante, damit jede Verwendung zwangslaeufig ein
    FRISCHES Objekt bekommt: die Fusion mutiert die Punkte in-place (s.
    ``_fusioniere``), eine geteilte Liste laege beim zweiten Durchgang anders
    vor. Ein Aufrufausdruck kann — anders als eine Variable — nicht versehentlich
    ein zweites Mal durch die Fusion gereicht werden.
    """
    return [_dp(14, cape=800.0, cin=5.0)]


def _kein_gewitter_am_tag() -> list[ForecastDataPoint]:
    """Die ENTSCHEIDBARE „Kein Gewitter"-Fixture (AC-6): 14 Uhr CAPE 200 J/kg
    → ueber die echte Fusion ``NONE`` mit LEERER Traegerliste, dazu 21 Uhr
    CAPE 800 → ``MED`` mit ``['cape']``, also AUSSERHALB des Standardfensters
    4-19.

    Warum nicht der ruhige Tag allein: fuehrt KEINE Stunde der Etappe eine
    nichtleere Traegerliste, kann die Zeile schon deshalb keine Herkunft
    zeigen, weil es nirgends eine gibt — der Test waere dann gruen, ganz
    gleich ob der NONE-Guard am Wirkort steht oder nicht (gemessen: die
    Verfaelschung, die bei ``NONE`` eine Herkunft anhaengt, laesst eine
    reine 200er-Fixture unveraendert). Erst die Nachtstunde legt eine
    Traegerliste in die Zeile, die ein Fehler ANHAENGEN koennte — damit wird
    „ohne Gewitter keine Herkunft" ueberhaupt falsifizierbar.

    Als FUNKTION aus demselben Grund wie ``_eine_zutat_14uhr()``: jeder
    Fusionsdurchgang braucht ein frisches Objekt (s. ``_fusioniere``).
    """
    return [_dp(14, cape=200.0), _dp(21, cape=800.0, cin=5.0)]


def _fusioniere(punkte: list[ForecastDataPoint], *,
                traeger_verwerfen: bool = False) -> list[ForecastDataPoint]:
    """Wendet die ECHTE Fusion in-place an (setzt ``dp.thunder_level`` UND
    ``dp.thunder_level_signals``) — keine im Test getippte Schwelle.

    ``traeger_verwerfen=True`` bildet einen aufgezeichneten Schnappschuss VOR
    Scheibe 1 nach: die Stufe steht am Datenpunkt, die Traegerliste fehlt
    (AC-11).

    DER WAECHTER UNTEN schliesst eine ganze Fehlerklasse aus, die diese Datei
    schon einmal falsch messen liess: die Fusion arbeitet IN-PLACE und reicht
    ``dp.thunder_level`` als Wettercode-Eingang wieder in sich selbst hinein
    (``thunder_enrichment.py:140-151``). Geht DIESELBE Punktliste ein zweites
    Mal durch, traegt die Stufe ploetzlich zusaetzlich „Wettercode" — gemessen:
    1x auf frischer Liste ``MED ['cape']``, 2x auf derselben Liste
    ``MED ['wettercode', 'cape']``. Im Produktivpfad kann das nicht passieren,
    weil der einzige echte Einstieg ``enrich_thunder()`` bei einer bereits
    angereicherten Reihe sofort zurueckkehrt (``:228-231``) — es ist also ein
    Fixture-Fehler, kein Codefehler, und genau deshalb gehoert der Waechter
    hierher und nicht in den Prueflings-Code. Ohne ihn faellt jeder kuenftige
    Test derselben Datei still darauf herein, sobald er eine Punktliste in
    einer Variablen bindet und zweimal verwendet.
    """
    bereits = [p for p in punkte
               if p.thunder_level is not None or p.thunder_level_signals is not None]
    assert not bereits, (
        "Fixture-Aliasing: diese Punktliste wurde bereits fusioniert. Die "
        "Fusion arbeitet in-place und speist ihr eigenes Ergebnis als "
        "Wettercode-Eingang wieder ein — ein zweiter Durchgang erfindet einen "
        "zusaetzlichen Traeger 'Wettercode' und der Test misst dann etwas "
        "anderes, als er behauptet. Fuer jeden Durchgang eine FRISCHE Liste "
        "bauen (z.B. ueber ``_eine_zutat_14uhr()``), nie eine Variable "
        f"mehrfach durchreichen. Betroffene Punkte: "
        f"{[(p.ts.hour, p.thunder_level, p.thunder_level_signals) for p in bereits]!r}")
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    if traeger_verwerfen:
        for p in punkte:
            p.thunder_level_signals = None
    return punkte


def _etappe(punkte: list[ForecastDataPoint], tag: date,
            segment_id: int) -> SegmentWeatherData:
    """Ein Etappen-Wetterdatensatz aus fertig fusionierten Punkten."""
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(tag.year, tag.month, tag.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(tag.year, tag.month, tag.day, 17, 0, tzinfo=timezone.utc),
        duration_hours=11.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _ruhige_etappe() -> SegmentWeatherData:
    """Die HEUTIGE Etappe des Briefings — bewusst GEWITTERFREI.

    ``cape=200`` liegt unter der niedrigsten Sprosse (300 J/kg) und ergibt
    ueber die echte Fusion ``ThunderLevel.NONE`` mit LEERER Traegerliste.
    Damit ist die Gewitter-Vorschau der EINZIGE Ort dieser Mail, an dem eine
    Zutat-Bezeichnung entstehen kann — sonst faerbten die Herkuenfte aus
    Scheibe 2 (Kurzzusammenfassung) und Scheibe 4 (Stundentabelle) die
    Gegenproben von AC-9/AC-10 gruen, ohne dass diese Scheibe irgendetwas
    bewirkt haette. Heute gemessen: weder ``email_plain`` noch ``email_html``
    dieser Mail enthalten eine der vier Bezeichnungen.
    """
    return _etappe(
        _fusioniere([_dp(h, tag=_HEUTE, cape=200.0) for h in range(6, 18)]),
        _HEUTE, 1,
    )


class _TripAttrappe:
    """Echtes Datenobjekt (kein Mock): genau die zwei Zugriffe, die
    ``_build_thunder_forecast_from_trend_or_fetch()`` auf dem Trip macht —
    ``report_config`` (fuer die Fensterauflösung, ``:2185-2189``) und
    ``get_future_stages()`` (fuer die Luecken-Markierung, ``:2237-2245``).
    Muster: ``tests/unit/test_thunder_forecast_day_window.py::_StubTrip``.
    """

    def __init__(self, report_config: TripReportConfig | None = None) -> None:
        self.report_config = report_config

    def get_future_stages(self, target_date):
        return []


class _ZeitplanerOhneNetz(TripReportSchedulerService):
    """Der PRODUKTIVE Zeitplaner mit genau EINEM ersetzten Baustein: dem
    Netzabruf ``_collect_future_stage_weather()``.

    Kein Mock: die Unterklasse ersetzt keine Rueckgabewerte des Prueflings,
    sondern liefert an der Naht, an der im Betrieb Open-Meteo-Daten
    hereinkommen, dieselben ``SegmentWeatherData``, die der Produktivpfad
    dort gebaut haette. Alles danach — Weiche, Fensterauflösung,
    Datumsabgleich, Eintragsbau in BEIDEN Pfaden — ist unveraenderter
    Produktivcode. Die Kern-Testschicht darf kein Netz benutzen; der
    Vorgaenger-Bestandstest ``test_thunder_night_addendum_parity.py`` loest
    dasselbe ueber ``GZ_TEST_FIXTURE_DIR``, was hier den vollen Trip-/
    Waypoint-Aufbau erzwingen wuerde, ohne mehr zu beweisen.

    ``segmente=[]`` heisst „der Rueckfall kann strukturell nichts liefern" —
    genau das macht den Primaerpfad-Nachweis in ``_primaer()`` entscheidbar.

    ``now_utc`` steht in der Signatur, weil der Produktivaufrufer ihn seit
    #1727 S5b als Schluesselwort uebergibt (``trip_report_scheduler.py:2316``).
    Ersetzt ist genau der Netzabruf: im Original waehlt ``now_utc`` ueber
    ``trip_local_today()`` -> ``is_within_forecast_horizon()``, WELCHE ETAPPEN
    ueberhaupt abgerufen werden; die hier gelieferten Segmente sind das
    Ergebnis genau dieser Wahl. Auf die Fensterfrage (welche STUNDEN zaehlen)
    wirkt er an keiner Stelle.
    """

    def __init__(self, segmente: list[SegmentWeatherData]) -> None:
        super().__init__()
        self._segmente = list(segmente)

    def _collect_future_stage_weather(self, trip, target_date, now_utc,
                                      wanted_dates=None):
        return list(self._segmente)


def _trend_zeile(punkte: list[ForecastDataPoint], *,
                 report_config: TripReportConfig | None = None,
                 traeger_verwerfen: bool = False) -> dict:
    """Eine ``multi_day_trend``-Zeile GENAU so, wie der Zeitplaner sie baut.

    Wortgleich zu ``trip_report_scheduler._build_stage_trend()``
    (``:2100-2116``): Tagesfenster EINMAL ueber ``resolve_configured_window()``
    aus ``trip.report_config`` aufloesen, an ``build_outlook_row()``
    durchreichen, danach ``date``/``name`` ergaenzen. ``date`` ist der
    Schluessel, ueber den die Weiche die Zeile dem Vorschau-Offset zuordnet
    (``:2191-2199``).
    """
    punkte = _fusioniere(punkte, traeger_verwerfen=traeger_verwerfen)
    win_start, win_end = resolve_configured_window(
        getattr(report_config, "day_window_start_hour", None),
        getattr(report_config, "day_window_end_hour", None),
    )
    zeile = build_outlook_row(
        summarize_points(punkte), punkte, "Fr", _TZ,
        day_window_start_hour=win_start, day_window_end_hour=win_end,
    )
    zeile["date"] = _MORGEN
    zeile["name"] = "Etappe B"
    return zeile


# ---------------------------------------------------------------------------
# Die beiden Bauwege — je mit strukturellem Nachweis, WELCHER gelaufen ist
# ---------------------------------------------------------------------------

def _rueckfall(punkte: list[ForecastDataPoint], *,
               report_config: TripReportConfig | None = None,
               traeger_verwerfen: bool = False) -> dict:
    """RUECKFALLPFAD (Morgen-Regelfall): kein Mehrtages-Trend vorhanden.

    Nachweis, dass wirklich ``_build_thunder_forecast()`` gelaufen ist:
    ``multi_day_trend=None`` laesst ``trend_by_date`` leer, damit ist der
    ``row is not None``-Zweig der Weiche (``:2200``) unerreichbar und
    ``_thunder_entry_from_trend_row()`` wird nie aufgerufen. Ein „+1"-Eintrag
    kann folglich NUR aus dem Rueckfall stammen.
    """
    zeitplaner = _ZeitplanerOhneNetz(
        [_etappe(_fusioniere(punkte, traeger_verwerfen=traeger_verwerfen),
                 _MORGEN, 2)]
    )
    forecast = zeitplaner._build_thunder_forecast_from_trend_or_fetch(
        _TripAttrappe(report_config), _HEUTE, now_utc=_JETZT, tz=_TZ,
        multi_day_trend=None,
    )
    assert forecast and "+1" in forecast, (
        "Fixture-/Wegefehler: ohne Trend MUSS der Rueckfallpfad einen "
        f"'+1'-Eintrag bauen, erhalten: {forecast!r}")
    return forecast


def _primaer(punkte: list[ForecastDataPoint], *,
             report_config: TripReportConfig | None = None,
             traeger_verwerfen: bool = False) -> tuple[dict, list[dict]]:
    """PRIMAERPFAD (Abend mit abgeschaltetem Ausblick): Trend liegt vor.

    Nachweis, dass wirklich ``_thunder_entry_from_trend_row()`` gelaufen ist:
    der Netzabruf liefert eine LEERE Segmentliste, damit ergibt der Rueckfall
    strukturell ``{}`` (``:2217-2224``: ``fetched`` ist falsy →
    ``fetched_fc = {}``). Ein „+1"-Eintrag kann folglich NUR aus der
    Trend-Zeile stammen.

    Gibt Eintrag UND Trend-Zeilen zurueck, weil die Mail beides braucht: die
    Vorschau erscheint nur bei ``show_outlook=False`` TROTZ vorhandenem Trend.
    """
    zeilen = [_trend_zeile(punkte, report_config=report_config,
                           traeger_verwerfen=traeger_verwerfen)]
    zeitplaner = _ZeitplanerOhneNetz([])
    forecast = zeitplaner._build_thunder_forecast_from_trend_or_fetch(
        _TripAttrappe(report_config), _HEUTE, now_utc=_JETZT, tz=_TZ,
        multi_day_trend=zeilen,
    )
    assert forecast and "+1" in forecast, (
        "Fixture-/Wegefehler: die Trend-Zeile MUSS ueber den Primaerpfad "
        f"einen '+1'-Eintrag bauen, erhalten: {forecast!r}")
    return forecast, zeilen


def _mail(forecast: dict | None, *, trend: list[dict] | None = None,
          report_config: TripReportConfig | None = None,
          report_type: str = "morning"):
    """Das ECHTE Trip-Briefing (HTML + Klartext + SMS + Telegram-Bubbles)
    ueber den produktiven Formatierer — Pruefort = Wirkort."""
    return TripReportFormatter().format_email(
        [_ruhige_etappe()], "Test-Trip", report_type,
        display_config=build_default_display_config(), tz=_TZ,
        stage_name="Etappe A", thunder_forecast=forecast,
        multi_day_trend=trend, report_config=report_config,
    )


# ---------------------------------------------------------------------------
# Messsonden auf der ZUGESTELLTEN Ausgabe
# ---------------------------------------------------------------------------

def _vorschau_klartext(bericht) -> str:
    """Die EINE Vorschau-Zeile aus dem Klartext-Block der fertigen Mail.

    Der Block wird ueber seine Ueberschrift gefunden, nicht ueber einen
    Inhalt, der sich mit dieser Scheibe aendert. Fuehrende Einrueckung wird
    entfernt, damit die Zeile mit der HTML-Fassung zeichengleich vergleichbar
    ist (``plain.py`` setzt zwei Leerzeichen davor, ``html.py`` nicht).
    """
    text = bericht.email_plain
    assert _KLARTEXT_UEBERSCHRIFT in text, (
        f"Der Klartext-Block '{_KLARTEXT_UEBERSCHRIFT}' fehlt in der Mail:\n{text}")
    rest = text.split(_KLARTEXT_UEBERSCHRIFT, 1)[1].splitlines()
    zeilen = []
    for ln in rest:
        if not ln.strip():
            if zeilen:
                break
            continue
        zeilen.append(ln.strip())
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Vorschau-Zeile, gefunden: {zeilen!r}")
    return zeilen[0]


def _vorschau_html(bericht) -> str:
    """Die EINE Vorschau-Zeile aus dem HTML-Block der fertigen Mail."""
    suppe = BeautifulSoup(bericht.email_html, "html.parser")
    ueberschriften = [
        h for h in suppe.find_all("h3")
        if _HTML_UEBERSCHRIFT in h.get_text()
    ]
    assert len(ueberschriften) == 1, (
        f"Erwartet genau EINEN HTML-Block '{_HTML_UEBERSCHRIFT}', gefunden: "
        f"{len(ueberschriften)}")
    eintraege = [li.get_text() for li in ueberschriften[0].parent.find_all("li")]
    assert len(eintraege) == 1, (
        f"Erwartet genau EINEN Vorschau-Eintrag, gefunden: {eintraege!r}")
    return eintraege[0]


def _beide_fassungen(bericht) -> str:
    """Die Vorschau-Zeile, nachdem belegt ist, dass Klartext und HTML
    zeichengleich sind — die Spec verlangt „wortgleich in beiden Formaten"
    (AC-1). Ein Test, der nur eine Fassung liest, uebersieht, wenn nur ein
    Renderer die Herkunft zeigt."""
    klartext = _vorschau_klartext(bericht)
    html = _vorschau_html(bericht)
    assert klartext == html, (
        "Klartext- und HTML-Fassung der Gewitter-Vorschau muessen wortgleich "
        f"sein.\n  Klartext: {klartext!r}\n  HTML:     {html!r}")
    return klartext


def _ohne_zeitstempel(text: str) -> str:
    """Blendet die einzige laufzeitabhaengige Zeile der Kompakt-Mail aus."""
    return "\n".join(
        ln for ln in text.splitlines() if not ln.startswith("Generated:")
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2: derselbe Wortlaut ueber BEIDE Bauwege
# ---------------------------------------------------------------------------

def test_ac1_rueckfallpfad_eine_zutat_klartext_und_html():
    """AC-1: Given einen Morgen-Bericht in Standard-Konfiguration (kein
    Mehrtages-Trend) mit einer Folge-Etappe, deren Gewitterstufe im
    Tagesfenster von genau EINER Zutat getragen wird / When die Trip-Vollmail
    (Klartext UND HTML) erzeugt wird / Then steht hinter der Tagesaussage
    " · " und die deutsche Bezeichnung der Zutat, wortgleich in beiden
    Formaten.

    Bauweg: RUECKFALL (``_build_thunder_forecast``), strukturell erzwungen
    durch ``multi_day_trend=None`` — s. ``_rueckfall()``.

    Fixture-Auflage der Spec (Testplan, „Fixture-Hinweis"): zusaetzlich zu
    dem Punkt IM Tagesfenster (14 Uhr, CAPE 800 → MED) traegt die Fixture
    einen Punkt AUSSERHALB des Fensters mit einer ANDEREN Zutat auf
    DERSELBEN Stufe (21 Uhr, LPI 35 → MED ueber Blitzpotenzial). Laese die
    Implementierung die Traeger aus der ungefensterten Punktliste ``day_dps``
    statt aus ``thunder_dps``, stuende hier „CAPE, Blitzpotenzial" — ohne
    diese gemischte Fixture bliebe der Fehler unentdeckt (Spec Punkt 2 legt
    die Fenster-Kohaerenz strukturell nahe, beweist sie aber nicht).

    Der Nacht-Halbsatz ist Folge derselben Auflage (ein Gewitter ausserhalb
    des Fensters WIRD seit #1651 genannt) und deshalb Teil der Erwartung.
    """
    zeile = _beide_fassungen(_mail(
        _rueckfall([_dp(14, cape=800.0, cin=5.0), _dp(21, lpi=35.0)])
    ))
    assert zeile == (
        f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE, "
        "nachts mittleres Gewitter ab 21:00"
    ), (
        "Die Gewitter-Vorschau des Morgen-Berichts muss die tragende Zutat "
        f"hinter der Tagesaussage nennen: {zeile!r}")
    assert "Blitzpotenzial" not in zeile, (
        "Die Zutat der Stunde AUSSERHALB des Tagesfensters gehoert nicht zur "
        f"gezeigten Tagesstufe und darf nicht erscheinen: {zeile!r}")


def test_ac2_primaerpfad_eine_zutat_klartext_und_html():
    """AC-2: Given einen Abend-Bericht mit ausdruecklich ausgeschaltetem
    Mehrtages-Ausblick (``show_outlook=False``), obwohl ein Mehrtages-Trend
    vorliegt, mit DERSELBEN tragenden Zutat wie in AC-1 / When die
    Trip-Vollmail erzeugt wird / Then zeigt die Gewitter-Vorschau denselben
    Herkunfts-Zusatz — obwohl hier der ANDERE interne Bauweg laeuft.

    Bauweg: PRIMAER (``_thunder_entry_from_trend_row``), strukturell
    erzwungen durch einen Netzabruf, der nichts liefert — s. ``_primaer()``.
    Traegerquelle ist hier ``row["hourly_thunder_signals"]`` (S5a-Feld), nicht
    ``summarize_points()``: zwei unabhaengige Codestellen, die derselbe
    Wortlaut verbindet. Ein Test, der nur AC-1 hat, deckt diesen Weg NICHT
    ab (Spec „Am Code gemessen" Punkt 1).

    Erwartung ist bewusst zeichengleich zu AC-1 — dieselbe Fixture, derselbe
    Satz. Weicht sie ab, driften die beiden Bauwege auseinander.
    """
    forecast, zeilen = _primaer([_dp(14, cape=800.0, cin=5.0), _dp(21, lpi=35.0)])
    bericht = _mail(forecast, trend=zeilen, report_type="evening",
                    report_config=TripReportConfig(show_outlook=False))
    zeile = _beide_fassungen(bericht)
    assert zeile == (
        f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE, "
        "nachts mittleres Gewitter ab 21:00"
    ), (
        "Der Primaerpfad (Trend-Zeile) muss denselben Herkunfts-Zusatz zeigen "
        f"wie der Rueckfallpfad: {zeile!r}")
    assert "Blitzpotenzial" not in zeile, (
        "Auch im Primaerpfad gehoert die Zutat der Stunde AUSSERHALB des "
        f"Tagesfensters nicht in die Tagesaussage: {zeile!r}")


# ---------------------------------------------------------------------------
# AC-3 bis AC-5: Wortlaut-Details
# ---------------------------------------------------------------------------

def test_ac3_zwei_zutaten_werden_beide_genannt():
    """AC-3: Given eine Folge-Etappe, deren Hoechststufe im Tagesfenster von
    ZWEI Zutaten gleichzeitig getragen wird / When die Gewitter-Vorschau
    gerendert wird / Then werden BEIDE genannt, mit ", " verbunden — kein
    Gewinner gekuert (Auslegung (ii), unveraendert seit S1).

    Zwei Fixturen, weil sie verschiedene Fehler fangen:
    (a) EIN Punkt mit zwei Zutaten (16 Uhr, CAPE 1500 + LPI 60 → beide HIGH)
        — Erstauftritt ist die Katalogreihenfolge: "CAPE, Blitzpotenzial".
        Prueft Verbinder und Reihenfolge innerhalb einer Stunde.
    (b) ZWEI Punkte mit je EINER Zutat (15 Uhr LPI 60, 16 Uhr CAPE 1500) —
        Erstauftritt ist die ZEITLICHE Reihenfolge: "Blitzpotenzial, CAPE".
        Nur (b) faellt, wenn statt der Vereinigung die erste Traegerliste
        genommen wird; bei (a) waere die erste Liste zufaellig schon die
        Vereinigung.
    Bauweg: RUECKFALL (Spec-Testplan: „wahlweise Pfad").
    """
    zeile_a = _beide_fassungen(_mail(
        _rueckfall([_dp(16, cape=1500.0, cin=5.0, lpi=60.0)])
    ))
    assert zeile_a == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet ab 16:00 · CAPE, Blitzpotenzial"
    ), (
        "Beide Traeger der Hoechststufe muessen mit ', ' verbunden erscheinen "
        f"— innerhalb EINER Stunde in Katalogreihenfolge: {zeile_a!r}")

    zeile_b = _beide_fassungen(_mail(
        _rueckfall([_dp(15, lpi=60.0), _dp(16, cape=1500.0, cin=5.0)])
    ))
    assert zeile_b == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet ab 15:00 · Blitzpotenzial, CAPE"
    ), (
        "Tragen ZWEI Stunden des Tagesfensters die Hoechststufe ueber "
        "verschiedene Zutaten, muessen BEIDE erscheinen (Vereinigung, nicht "
        f"die erste Liste), in zeitlicher Erstauftritts-Reihenfolge: {zeile_b!r}")


def test_ac4_herkunft_steht_vor_dem_nacht_halbsatz():
    """AC-4: Given eine Etappe mit Gewitter im Tagesfenster UND zusaetzlichem
    Gewitter im Nachtfenster / When die Gewitter-Vorschau gerendert wird /
    Then steht die Herkunft unmittelbar hinter der Tagesaussage und VOR dem
    Nacht-Halbsatz; der Nacht-Halbsatz selbst bleibt wortgleich zu heute.

    Die Positions-Zusicherung wird ZUSAETZLICH zur Zeichengleichheit ueber
    die Fundstellen geprueft: Pflicht-Mutation (e) der Spec vertauscht genau
    diese Reihenfolge, und eine reine Gleichheitspruefung sagt dann zwar
    „falsch", aber nicht „an der falschen Stelle".

    „Wortgleich zu heute" ist am gemessenen Ist-Stand festgemacht: heute
    liefert dieselbe Fixture ``…ab 14:00, nachts leichtes Gewitter ab 02:00``
    (``format_night_addendum``, EINE Wortlaut-Quelle fuer beide Bauwege).
    """
    zeile = _beide_fassungen(_mail(
        _rueckfall([_dp(2, cape=400.0, cin=5.0), _dp(14, cape=800.0, cin=5.0)])
    ))
    nacht = ", nachts leichtes Gewitter ab 02:00"
    assert zeile == (
        f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE{nacht}"
    ), (
        "Die Herkunft gehoert zwischen Tagesaussage und Nacht-Halbsatz, der "
        f"Nacht-Halbsatz bleibt wortgleich: {zeile!r}")
    assert zeile.index(" · CAPE") < zeile.index(nacht), (
        f"Die Herkunft steht hinter dem Nacht-Halbsatz statt davor: {zeile!r}")


def test_ac5_herkunft_steht_vor_dem_hagel_zusatz():
    """AC-5: Given eine Etappe mit Gewitter UND gesetztem Hagel-Kennzeichen /
    When die Gewitter-Vorschau gerendert wird / Then steht die Herkunft VOR
    dem Hagel-Zusatz, und der Hagel-Zusatz bleibt wortgleich erhalten.

    Der Hagel-Zusatz entsteht erst im Renderer (``plain.py:326-328`` /
    ``html.py:1319-1322``, ``format_hail_note``) und wird an ``fc['text']``
    angehaengt — die Reihenfolge ergibt sich also nur dann richtig, wenn die
    Herkunft TEIL von ``text`` ist. Genau das ist Entscheidung E1, und genau
    deshalb ist dieser Test der Waechter dafuer, dass die Herkunft nicht als
    zweiter Dict-Schluessel hinter dem Hagel landet.
    """
    zeile = _beide_fassungen(_mail(
        _rueckfall([_dp(14, cape=800.0, cin=5.0, hail=True)])
    ))
    assert zeile == (
        f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE · Hagel: ja"
    ), (
        "Die Herkunft gehoert zwischen Tagesaussage und Hagel-Zusatz, der "
        f"Hagel-Zusatz bleibt wortgleich: {zeile!r}")


# ---------------------------------------------------------------------------
# AC-6 bis AC-8: die Abwesenheits-Zusicherungen (je mit Gegenprobe)
# ---------------------------------------------------------------------------

def test_ac6_kein_gewitter_zeigt_nie_herkunft():
    """AC-6: Given eine Etappe OHNE Gewitter im Tagesfenster (Stufe „Kein
    Gewitter erwartet") / When die Gewitter-Vorschau gerendert wird / Then
    enthaelt die Zeile WEDER eine Zutat-Bezeichnung NOCH einen zusaetzlichen
    ·-Trenner — sie bleibt zeichengleich zu heute.

    ``cape=200`` erzeugt ueber die echte Fusion ein ECHTES
    ``ThunderLevel.NONE`` mit LEERER Traegerliste — kein Python-``None``, das
    schon ein frueher Guard abfinge.

    BEIDE Pfade, weil die Zusicherung ZWEIMAL im Produktivcode steht, in
    baulich getrennten Zweigen mit je EIGENER Traegerquelle:
    ``_thunder_entry_from_trend_row()`` (``trip_report_scheduler.py:2376``,
    Quelle ``row["hourly_thunder_signals"]``) und ``_build_thunder_forecast()``
    (``:2605``, Quelle ``summarize_points(thunder_dps)``). Gemessen (Adversary
    F001): eine Verfaelschung, die im PRIMAERpfad bei ``NONE`` doch eine
    Herkunft anhaengt, liess die Fassung dieses Tests, die nur ueber
    ``_rueckfall()`` lief, vollstaendig gruen — die Haelfte der Zusicherung war
    unbewacht. Muster fuer die Zwei-Pfad-Messung:
    ``test_ac11_ohne_traegerinfo_bleibt_byte_identisch``.

    Fixture: ``_kein_gewitter_am_tag()`` — ruhiger Tag, Gewitter erst um
    21 Uhr, also AUSSERHALB des Fensters. Das ist die einzige Gestalt, in der
    die Zeile ueberhaupt eine Traegerliste MIT SICH FUEHRT, die ein Fehler
    anhaengen koennte; ohne sie ist der Test unfalsifizierbar (Begruendung
    dort). Der Nacht-Halbsatz ist Folge derselben Auflage und Teil der
    Erwartung — er ist wortgleich zu heute und traegt selbst keine Herkunft.

    Gegenprobe JE PFAD (Spec-Auflage): dieselbe 14-Uhr-Stunde mit ``cape=800``
    liegt oberhalb NONE und MUSS ueber DENSELBEN Pfad die Herkunft zeigen.
    Ohne sie waere der jeweilige Abwesenheits-Nachweis auch dann gruen, wenn
    die Herkunft auf diesem Pfad ueberhaupt nicht entstuende.
    Die Pflicht-Mutation (c) der Spec setzt an genau den Einfuegestellen an,
    die dieser Test bewacht.
    """
    ohne = f"{_DATUM}: Kein Gewitter erwartet, nachts mittleres Gewitter ab 21:00"
    mit = f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE"

    def _ohne_herkunft(zeile: str, pfad: str, ohne: str = ohne) -> None:
        assert zeile == ohne, (
            f"{pfad}: ohne Gewitter im Tagesfenster bleibt die Zeile "
            f"zeichengleich zu heute: {zeile!r}")
        assert "·" not in zeile, (
            f"{pfad}: kein zusaetzlicher ·-Trenner ohne Gewitter: {zeile!r}")
        for zutat in ALLE_ZUTATEN:
            assert zutat not in zeile, (
                f"{pfad}: '{zutat}' darf ohne Gewitter nicht erscheinen — auch "
                f"nicht die Zutat der Nachtstunde: {zeile!r}")

    # --- RUECKFALLPFAD (_build_thunder_forecast, :2605) --------------------
    _ohne_herkunft(
        _beide_fassungen(_mail(_rueckfall(_kein_gewitter_am_tag()))),
        "Rueckfallpfad",
    )
    # Der durchweg ruhige Tag zusaetzlich, damit auch die Fassung OHNE jeden
    # Nachtteil zeichengleich bleibt (Bestandszusicherung, unveraendert).
    _ohne_herkunft(
        _beide_fassungen(_mail(_rueckfall([_dp(14, cape=200.0)]))),
        "Rueckfallpfad (ruhiger Tag ohne Nachtgewitter)",
        f"{_DATUM}: Kein Gewitter erwartet",
    )
    laut_r = _beide_fassungen(_mail(_rueckfall(_eine_zutat_14uhr())))
    assert laut_r == mit, (
        "Gegenprobe Rueckfallpfad gescheitert: oberhalb NONE MUSS die Herkunft "
        f"erscheinen, sonst beweist die ruhige Zeile nichts: {laut_r!r}")

    # --- PRIMAERPFAD (_thunder_entry_from_trend_row, :2376) ----------------
    aus = TripReportConfig(show_outlook=False)
    forecast, zeilen = _primaer(_kein_gewitter_am_tag(), report_config=aus)
    assert zeilen[0].get("hourly_thunder_signals"), (
        "Fixture-Fehler: die Trend-Zeile MUSS eine Traegerliste fuehren, sonst "
        "kann der Primaerpfad selbst bei entferntem NONE-Guard nichts "
        f"anhaengen und der Test bewacht nichts: {sorted(zeilen[0])!r}")
    _ohne_herkunft(
        _beide_fassungen(_mail(forecast, trend=zeilen, report_type="evening",
                               report_config=aus)),
        "Primaerpfad",
    )
    forecast_g, zeilen_g = _primaer(_eine_zutat_14uhr(), report_config=aus)
    laut_p = _beide_fassungen(_mail(forecast_g, trend=zeilen_g,
                                    report_type="evening", report_config=aus))
    assert laut_p == mit, (
        "Gegenprobe Primaerpfad gescheitert: oberhalb NONE MUSS die Herkunft "
        f"auch ueber die Trend-Zeile erscheinen: {laut_p!r}")


def test_ac7_primaerpfad_abweichendes_fenster():
    """AC-7: Given einen Trip mit einem vom Standard (4-19) ABWEICHENDEN
    Tagesfenster und einem Gewitter, das nur innerhalb dieses Fensters liegt
    (Primaerpfad: Abend-Bericht mit ausgeschaltetem Ausblick) / When die
    Gewitter-Vorschau gerendert wird / Then stammen angezeigte Stufe UND
    angezeigte Herkunft aus DEMSELBEN Fenster.

    Fenster 6-14. Die Fixture traegt ZWEI Stunden mit derselben Hoechststufe
    (hoch), aber VERSCHIEDENEN Zutaten: 10 Uhr ueber die Blitzdichte (0.1 je
    km2), 18 Uhr ueber CAPE (1500 J/kg). Damit ist die Fensterfrage
    entscheidbar statt zufaellig richtig — bei entfernter Fensterfilterung
    (Pflicht-Mutation (b)) stuende dort „Blitzdichte, CAPE".

    Zweiter Durchgang mit DEN GLEICHEN Punkten im STANDARDfenster: dort
    liegen beide Stunden drin, beide Zutaten erscheinen und der
    Nacht-Halbsatz entfaellt. Beide Faelle zusammen belegen, dass Stufe,
    Herkunft und Nachtteil MITEINANDER umschalten — ein Test mit
    Standardfenster allein bewiese hier nichts.
    """
    eng = TripReportConfig(show_outlook=False, day_window_start_hour=6,
                           day_window_end_hour=14)
    forecast, zeilen = _primaer(
        [_dp(10, dichte=0.1), _dp(18, cape=1500.0, cin=5.0)],
        report_config=eng,
    )
    zeile = _beide_fassungen(_mail(forecast, trend=zeilen, report_type="evening",
                                   report_config=eng))
    assert zeile == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet ab 10:00 · Blitzdichte, "
        "nachts starkes Gewitter ab 18:00"
    ), (
        "Im abweichenden Fenster 6-14 muessen Stufe UND Herkunft aus der "
        f"10-Uhr-Stunde stammen (Blitzdichte): {zeile!r}")
    assert "CAPE" not in zeile, (
        "Die Zutat der 18-Uhr-Stunde liegt ausserhalb des konfigurierten "
        f"Fensters und gehoert nicht zur gezeigten Stufe: {zeile!r}")

    weit = TripReportConfig(show_outlook=False)
    forecast_w, zeilen_w = _primaer(
        [_dp(10, dichte=0.1), _dp(18, cape=1500.0, cin=5.0)],
        report_config=weit,
    )
    zeile_w = _beide_fassungen(_mail(forecast_w, trend=zeilen_w,
                                     report_type="evening", report_config=weit))
    assert zeile_w == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet ab 10:00 · Blitzdichte, CAPE"
    ), (
        "Im Standardfenster 4-19 liegen BEIDE Stunden drin — dann muessen "
        f"auch beide Zutaten erscheinen: {zeile_w!r}")


def test_ac8_primaerpfad_failsoft_ohne_traegerquelle():
    """AC-8: Given eine Etappe, fuer die im Tagesfenster KEINE Stundenprobe
    liegt und die Stufe deshalb ueber das Kalendertags-Maximum bestimmt wird
    (Fail-soft-Zweig, ``:2319-2326`` — ausschliesslich im Primaerpfad
    erreichbar, weil der Rueckfallpfad bei leerem ``thunder_dps`` gar keinen
    Eintrag baut, ``:2540-2541``) / When die Gewitter-Vorschau gerendert wird
    / Then erscheint die Stufe OHNE Herkunft — es gibt fuer diesen Zweig
    keine zum Fenster passende Traegerquelle.

    Fixture: Fenster 6-14, einziges Gewitter um 21 Uhr (CAPE 1500 → hoch).
    ``windowed`` ist leer, die Stufe kommt aus ``row["thunder"]``; die
    fehlende Stunde zeigt sich am Wortlaut „Starkes Gewitter erwartet" OHNE
    „ab HH:MM" — daran ist im zugestellten Text ablesbar, dass wirklich der
    Fail-soft-Zweig lief und nicht der Regelzweig.

    Gegenprobe an derselben Fixture (Spec-Auflage): dieselben Punkte PLUS
    eine Stunde IM Fenster (10 Uhr, CAPE 1500) — dann erscheint die Herkunft
    sehr wohl. Pflicht-Mutation (d) der Spec haengt dem Fail-soft-Zweig eine
    Herkunft aus dem Kalendertags-Maximum an; daran faellt der erste Teil.
    """
    eng = TripReportConfig(show_outlook=False, day_window_start_hour=6,
                           day_window_end_hour=14)
    forecast, zeilen = _primaer([_dp(21, cape=1500.0, cin=5.0)], report_config=eng)
    zeile = _beide_fassungen(_mail(forecast, trend=zeilen, report_type="evening",
                                   report_config=eng))
    assert zeile == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet, "
        "nachts starkes Gewitter ab 21:00"
    ), (
        "Ohne Stundenprobe im Fenster bleibt der Fail-soft-Satz zeichengleich "
        f"zu heute und traegt KEINE Herkunft: {zeile!r}")
    for zutat in ALLE_ZUTATEN:
        assert zutat not in zeile, (
            f"'{zutat}' gehoert nicht zu einer Stufe aus dem Kalendertags-"
            f"Maximum: {zeile!r}")

    forecast_g, zeilen_g = _primaer(
        [_dp(10, cape=1500.0, cin=5.0), _dp(21, cape=1500.0, cin=5.0)],
        report_config=eng,
    )
    zeile_g = _beide_fassungen(_mail(forecast_g, trend=zeilen_g,
                                     report_type="evening", report_config=eng))
    assert zeile_g == (
        f"{_DATUM}: ⚡ Starkes Gewitter erwartet ab 10:00 · CAPE, "
        "nachts starkes Gewitter ab 21:00"
    ), (
        "Gegenprobe gescheitert: mit einer Stundenprobe IM Fenster MUSS die "
        f"Herkunft erscheinen, sonst beweist der Fail-soft-Fall nichts: "
        f"{zeile_g!r}")


# ---------------------------------------------------------------------------
# AC-9 / AC-10: die bewusst ausgenommenen Ausgabewege
# ---------------------------------------------------------------------------

def test_ac9_sms_und_premium_sms_ohne_herkunft_sonde():
    """AC-9: Given einen Trip-Briefing-Versand ueber SMS bzw. Premium-SMS mit
    einer Etappe, deren Gewitter-Vorschau in der zeitgleich erzeugten Mail
    eine Zutat traegt / When der SMS-Text erzeugt wird / Then enthaelt er
    KEINE der vier Zutat-Bezeichnungen.

    Nachweis per SONDE, nicht per Wortsuche (Spec-Auflage): die WERTE der
    Beschriftungstabelle ``THUNDER_SIGNAL_LABEL_DE`` werden zur Laufzeit
    in-place durch eindeutige Marker ersetzt (Wiederherstellung in
    ``finally``). In-place, weil ``thunder_signal_label()`` die Tabelle zur
    AUFRUFZEIT liest — die Sonde wirkt damit unabhaengig davon, wie die
    Implementierung die Funktion importiert. Verfahren uebernommen aus
    ``tests/tdd/test_thunder_origin_outlook.py:680-710``.

    Zugriff bewusst ueber ``output.metric_format``: die Spec verschiebt die
    Tabelle nach ``app.thunder_scale``, behaelt dort aber einen Re-Export,
    der DIESELBE Dict-Instanz bindet (Muster #1196). Bindet die Umsetzung
    stattdessen eine Kopie, faellt die Gegenprobe unten — und das ist dann
    ein echter Befund, kein Testartefakt.

    Gegenprobe an DERSELBEN Mail: die Sonde MUSS in der Vorschau-Zeile
    anschlagen. Ohne sie bewiese ihre Abwesenheit in der SMS nichts. SMS und
    Premium-SMS teilen sich ``report.sms_text`` (ein Text, zwei Transporte);
    geprueft wird zusaetzlich der dokumentierte Rueckfall
    ``sms_text or email_plain`` (``notification_service.py:411-483``).
    """
    from output import metric_format

    sonde = "ZUTATSONDE"
    original = dict(metric_format.THUNDER_SIGNAL_LABEL_DE)
    try:
        for schluessel in list(metric_format.THUNDER_SIGNAL_LABEL_DE):
            metric_format.THUNDER_SIGNAL_LABEL_DE[schluessel] = f"{sonde}-{schluessel}"
        bericht = _mail(_rueckfall(_eine_zutat_14uhr()))

        zeile = _beide_fassungen(bericht)
        assert sonde in zeile, (
            "Gegenprobe gescheitert: die Sonde muss in der Vorschau-Zeile der "
            "Mail anschlagen, sonst beweist ihre Abwesenheit in der SMS "
            f"nichts: {zeile!r}")

        assert bericht.sms_text, (
            "sms_text muss immer erzeugt werden — sonst greift der Rueckfall "
            "`sms_text or email_plain` und die Herkunft koennte in die SMS "
            "durchsickern")
        zugestellt = bericht.sms_text or bericht.email_plain
        assert sonde not in zugestellt, (
            "SMS/Premium-SMS sind bewusst OHNE Herkunft — die Sonde darf dort "
            f"NICHT anschlagen: {zugestellt!r}")
        for zutat in ALLE_ZUTATEN:
            assert zutat not in zugestellt, (
                f"'{zutat}' darf im SMS-Text nicht vorkommen: {zugestellt!r}")
    finally:
        metric_format.THUNDER_SIGNAL_LABEL_DE.clear()
        metric_format.THUNDER_SIGNAL_LABEL_DE.update(original)


def test_ac10_telegram_und_kompaktmail_unveraendert():
    """AC-10: Given einen Trip-Briefing-Versand ueber Telegram bzw. im
    E-Mail-Kompaktformat mit derselben Etappe / When Telegram-Bubbles bzw.
    Kompakt-Mail erzeugt werden / Then bleibt ihre Ausgabe zeichengleich zu
    heute — kein „Gewitter-Vorschau"-Block, keine Herkunft.

    „Zeichengleich zu heute" wird als Unempfindlichkeit gegen die
    Traegerinformation gemessen: dieselbe Etappe einmal MIT und einmal OHNE
    Traegerliste muss dieselben Bubbles und denselben Kompakttext ergeben
    (bis auf die laufzeitabhaengige „Generated:"-Zeile). Das ist staerker als
    eine reine Wortsuche, weil es auch eine Herkunft faenge, die unter einer
    anderen Beschriftung durchsickerte.

    Gegenprobe an derselben Fixture-DEFINITION (``_eine_zutat_14uhr()``, jeder
    Durchgang auf einem frischen Objekt — s. dort und ``_fusioniere``): die
    VOLLMAIL zeigt die Herkunft sehr wohl — ohne sie waere der Test auch dann
    gruen, wenn die Scheibe gar nichts bewirkte.
    """
    mit = _mail(_rueckfall(_eine_zutat_14uhr()))
    ohne = _mail(_rueckfall(_eine_zutat_14uhr(), traeger_verwerfen=True))

    assert mit.telegram_bubbles == ohne.telegram_bubbles, (
        "Die Telegram-Bubbles duerfen sich durch die Traegerinformation NICHT "
        f"aendern.\nMIT:\n{mit.telegram_bubbles!r}\nOHNE:\n{ohne.telegram_bubbles!r}")
    for bubble in mit.telegram_bubbles:
        assert _HTML_UEBERSCHRIFT not in bubble, (
            f"Telegram kennt keinen Vorschau-Block: {bubble!r}")
        for zutat in ALLE_ZUTATEN:
            assert zutat not in bubble, (
                f"'{zutat}' darf nicht in einer Telegram-Bubble stehen: {bubble!r}")

    kompakt = TripReportConfig(email_format="compact")
    k_mit = _mail(_rueckfall(_eine_zutat_14uhr()),
                  report_config=kompakt).email_plain
    k_ohne = _mail(_rueckfall(_eine_zutat_14uhr(), traeger_verwerfen=True),
                   report_config=kompakt).email_plain
    assert _ohne_zeitstempel(k_mit) == _ohne_zeitstempel(k_ohne), (
        "Die Kompakt-Mail darf sich durch die Traegerinformation NICHT "
        f"aendern.\nMIT:\n{k_mit}\nOHNE:\n{k_ohne}")
    assert _HTML_UEBERSCHRIFT not in k_mit, (
        f"Die Kompakt-Mail kennt keinen Vorschau-Block:\n{k_mit}")
    for zutat in ALLE_ZUTATEN:
        assert zutat not in k_mit, (
            f"Die Kompakt-Mail darf keine Zutat '{zutat}' zeigen:\n{k_mit}")

    voll = _beide_fassungen(mit)
    assert voll == f"{_DATUM}: ⚡ Gewitter möglich ab 14:00 · CAPE", (
        "Gegenprobe gescheitert: die Vollmail DERSELBEN Etappe MUSS die "
        f"Herkunft zeigen, sonst beweisen Telegram/Kompakt nichts: {voll!r}")


# ---------------------------------------------------------------------------
# AC-11: Alt-Aufrufer ohne Traegerinformation
# ---------------------------------------------------------------------------

def test_ac11_ohne_traegerinfo_bleibt_byte_identisch():
    """AC-11: Given eine Vorschau-Etappe OHNE Traegerinformation (weder
    ``hourly_thunder_signals`` im Primaerpfad noch eine Traegerliste im
    Rueckfallpfad — Alt-Aufrufer bzw. aufgezeichnete Fixturen vor Scheibe 1)
    / When die Gewitter-Vorschau gerendert wird / Then bleibt ihre Ausgabe
    byte-identisch zu heute: kein leerer ·-Trenner, keine leere Herkunft.

    BEIDE Pfade, weil beide eine eigene Traegerquelle haben:
    * Rueckfall — die Datenpunkte fuehren ``thunder_level_signals=None``,
      also liefert ``summarize_points(...).thunder_level_max_signals``
      ``None``.
    * Primaer — die Trend-Zeile fuehrt den Schluessel
      ``hourly_thunder_signals`` gar nicht erst (gemessen: ``build_outlook_row``
      filtert ihn im ``optional``-Block heraus, wenn KEIN Punkt eine
      Traegerliste hat, ``outlook.py:545-549``). Das ist exakt die Gestalt
      der aufgezeichneten Golden-Fixturen unter
      ``tests/fixtures/outlook_trip_parity/``.

    Gegenprobe an derselben Fixture-DEFINITION (``_eine_zutat_14uhr()``, jedes
    Mal ein frisches Objekt — s. dort und ``_fusioniere``): dieselben Rohwerte
    MIT Traegerliste zeigen die Herkunft sehr wohl. Pflicht-Mutation (f) der
    Spec entfernt den Guard, der die Herkunft nur bei vorhandener Traegerliste
    anhaengt.
    """
    heute = f"{_DATUM}: ⚡ Gewitter möglich ab 14:00"

    ohne_r = _beide_fassungen(_mail(
        _rueckfall(_eine_zutat_14uhr(), traeger_verwerfen=True)))
    assert ohne_r == heute, (
        "Rueckfallpfad ohne Traegerliste: die Zeile bleibt byte-identisch zu "
        f"heute: {ohne_r!r}")

    aus = TripReportConfig(show_outlook=False)
    forecast_p, zeilen_p = _primaer(_eine_zutat_14uhr(), report_config=aus,
                                    traeger_verwerfen=True)
    assert "hourly_thunder_signals" not in zeilen_p[0], (
        "Fixture-Fehler: eine Alt-Zeile darf das S5a-Traegerfeld gar nicht "
        f"fuehren: {sorted(zeilen_p[0])!r}")
    ohne_p = _beide_fassungen(_mail(forecast_p, trend=zeilen_p,
                                    report_type="evening", report_config=aus))
    assert ohne_p == heute, (
        "Primaerpfad ohne Traegerfeld: die Zeile bleibt byte-identisch zu "
        f"heute: {ohne_p!r}")

    mit = _beide_fassungen(_mail(_rueckfall(_eine_zutat_14uhr())))
    assert mit == f"{heute} · CAPE", (
        "Gegenprobe gescheitert: MIT Traegerliste MUSS die Herkunft "
        f"erscheinen, sonst beweisen die Alt-Faelle nichts: {mit!r}")
