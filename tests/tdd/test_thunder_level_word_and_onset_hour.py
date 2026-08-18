"""TDD RED — Issue #1493: Gewitterstufe als Wort in der Pille + Onset-Stunde
im Klartext- und Kompakt-Ausblick.

SPEC: docs/specs/modules/feat_1493_gewitter_onset_sichtbar.md (AC-1..AC-8)
KONTEXT: docs/context/feat-1493-gewitter-onset.md

RED-Ursache (heute gemessen, 2026-08-18):

1. ``_pill_for_metric()`` (``email/helpers.py:1774``) rendert
   ``"Gewitter ab 14:00 · stärkste 18:00 · CAPE"`` — die STUFE steckt
   ausschliesslich im Ampelton (``_tone``). Im Klartext, wo Farbe nicht
   ankommt, ist sie damit gar nicht vorhanden.
2. ``render_outlook_plain()`` (``email/outlook.py:372``) baut
   ``f"⚡{_dm[0]}{_dm[2]}"`` und verwirft ``_dm[1]`` — die von
   ``_thunder_token_parts()`` laengst gelieferte Onset-Stunde. Gemessen steht
   dort ``⚡mittel (hoch @18) · CAPE``.
3. ``_compact_thunder_field()`` (``email/compact.py:103``) verwirft dieselbe
   Stunde im Tagesteil. Gemessen: ``Tmittel (hoch @18)``.

Die HTML-Ausblickzelle (``mittel @14``), der Telegram-Trendblock
(``⚡mittel@14(hoch@18)``) und die SMS (``TH:M@14(H@18)``) fuehren die Stunde
bereits — genau diese drei bleiben unveraendert (AC-5).

PRUEFORT = WIRKORT. Jeder Test rendert ueber die ECHTE Renderkette bis zum
zugestellten Text: ``TripReportFormatter.format_email()`` liefert
``email_html``/``email_plain``/``sms_text``/``telegram_bubbles`` in EINEM
Lauf; die Kompakt-Mail entsteht ueber ``TripReportConfig(email_format=
"compact")`` aus derselben Kette. Kein Test endet an ``_pill_for_metric()``,
``_thunder_token_parts()`` oder ``_compact_thunder_field()`` isoliert, und
kein Test liest Dateiinhalte.

KEIN MOCK-THEATER. Stufen und Traegerlisten entstehen ausschliesslich ueber
die ECHTE Fusion (``providers.thunder_enrichment._fuse_thunder_levels`` mit
den geeichten Leitern aus ``app.model_registry``) — kein im Test getippter
Stufenwert, keine getippte Schwelle. Jede Fixture belegt ihre Vorbedingung
(welche Stufe in welcher Stunde) an den fusionierten Punkten selbst, bevor
sie den gerenderten Text prueft.

WORTQUELLE. Die Erwartung "mittel" steht als LITERAL im Test, NICHT als
``THUNDER_LABEL_DE[ThunderLevel.MED]``. Zoege der Test sein Sollwort aus
derselben Tabelle wie der Prueling, bliebe er auch dann gruen, wenn diese
Tabelle verfaelscht wuerde — Test und Prueling teilten die Quelle. Dass die
Pille ihr Wort aus der geteilten SSoT holt (#1480), ist eine
Implementierungs-Zusicherung der Spec und bleibt Sache des Adversary.

INVARIANZ-WAECHTER. ``test_ac5_...``, ``test_ac6_...`` und ``test_ac7_...``
sind heute GRUEN und muessen es bleiben — sie bewachen die
Nicht-Aenderung (Telegram/SMS zeichengleich, "kein Gewitter" ohne erfundene
Stufe/Stunde, Ziel-Datenluecke bleibt "Gewitter ?"). Das ist kein
vergessener RED-Test: eine Aenderung, die AC-1..AC-4 gruen macht und dabei
einen dieser drei kippt, ist falsch implementiert.
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
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripReportConfig,
    TripSegment,
)
from app.user import (  # noqa: E402
    ComparisonResult, LocationResult, SavedLocation,
)
from output.renderers.comparison import render_comparison_text  # noqa: E402
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.notification_service import compute_has_gap  # noqa: E402
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService, summarize_points,
)

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_HEUTE = date(2026, 8, 20)     # Etappe des Briefings -> Pille
_MORGEN = date(2026, 8, 21)    # kuenftige Etappe    -> Ausblick-Zeile
_WOCHENTAG = "Di"
_AUSBLICK_PLAIN = "Nächste Etappen"      # Klartext-Vollmail
_AUSBLICK_KOMPAKT = "Naechste Etappen"   # Kompakt-Mail ist ASCII-gefaltet
_AUSBLICK_COMPARE = "3-Tages-Ausblick"   # im Ortsvergleich gibt es keine Etappen
_KOMPAKT = TripReportConfig(email_format="compact")


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, ECHTE Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date, cape=None, cin=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN — Stufe und Traeger rechnet die Fusion.

    Geeichte CAPE-Leiter der Testregion DE_ALPEN/icon_d2: 300/750/1200 J/kg
    (leicht/mittel/hoch). ``cin=5.0`` liegt im Band "schwacher Deckel"
    (Betrag < 25) und laesst die Leiter voll zaehlen. Damit ergibt sich ueber
    die echte Fusion: 200 -> kein, 400 -> leicht, 800 -> mittel, 1500 -> hoch.
    """
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.2,
        cloud_total_pct=40, humidity_pct=50, pop_pct=30,
        cape_jkg=cape, convective_inhibition_jkg=cin,
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


def _stufen(punkte: list[ForecastDataPoint]) -> dict[int, ThunderLevel]:
    """Die gerechneten Stufen je Stunde — Vorbedingungs-Nachweis der Fixture."""
    return {p.ts.hour: p.thunder_level for p in punkte}


def _tagespunkte(cape_je_stunde: dict[int, float]) -> list[ForecastDataPoint]:
    """Stundenreihe 6-18 Uhr der HEUTIGEN Etappe; genannte Stunden bekommen
    den angegebenen CAPE-Wert, alle uebrigen 200 J/kg (= kein Gewitter)."""
    return _fusioniere([
        _dp(h, tag=_HEUTE, cape=cape_je_stunde.get(h, 200.0), cin=5.0)
        for h in range(6, 19)
    ])


def _etappe(punkte: list[ForecastDataPoint]) -> SegmentWeatherData:
    """Die HEUTIGE Etappe des Briefings — Quelle der Metrik-Pillen."""
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=punkte,
    )
    return SegmentWeatherData(
        segment=_segment(), timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _segment() -> TripSegment:
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 6, 0,
                            tzinfo=timezone.utc),
        end_time=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, 18, 0,
                          tzinfo=timezone.utc),
        duration_hours=12.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )


def _etappe_ohne_daten() -> SegmentWeatherData:
    """Zieletappe mit echtem Fensterausfall (#1331): keine Stundenreihe, das
    gerenderte Tagesfenster bleibt leer. ``compute_has_gap()`` — der EINZIGE
    produktive Berechnungspunkt — leitet daraus die Ziel-Datenluecke ab."""
    return SegmentWeatherData(
        segment=_segment(), timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        has_error=True, error_message="provider timeout",
    )


def _ausblick_zeile(punkte: list[ForecastDataPoint]) -> dict:
    """Eine Ausblick-Zeile GENAU so, wie der Zeitplaner sie baut.

    Wortgleich zu ``trip_report_scheduler._build_multi_day_trend()``:
    Tagesfenster EINMAL ueber ``resolve_configured_window()`` aufloesen und an
    ``build_outlook_row()`` durchreichen, danach ``name`` ergaenzen.
    """
    win_start, win_end = resolve_configured_window(None, None)
    zeile = build_outlook_row(
        summarize_points(punkte), punkte, _WOCHENTAG, _TZ,
        day_window_start_hour=win_start, day_window_end_hour=win_end,
    )
    zeile["name"] = "Etappe B"
    return zeile


def _mail(segmente: list[SegmentWeatherData], zeilen: list[dict], *,
          report_config: TripReportConfig | None = None, has_gap: bool = False):
    """Das ECHTE Trip-Briefing (HTML + Klartext + SMS + Telegram-Bubbles)
    ueber den produktiven Formatierer — Pruefort = Wirkort."""
    return TripReportFormatter().format_email(
        segmente, "Test-Trip", "evening",
        display_config=build_default_display_config(), tz=_TZ,
        stage_name="Etappe A", multi_day_trend=zeilen,
        report_config=report_config, has_gap=has_gap,
    )


# ---------------------------------------------------------------------------
# Messsonden auf der ZUGESTELLTEN Ausgabe
# ---------------------------------------------------------------------------

def _pille_html(html: str) -> str:
    """Der Text der Gewitter-Kachel aus dem Metriken-Ueberblick des fertigen
    Mail-HTML.

    Der Block wird ueber seine Ueberschrift "Metriken-Überblick" gefunden
    (nicht ueber eine Klasse oder einen Inhalt, der sich mit dieser Aenderung
    verschiebt); die Kachel ist das INNERSTE Element darin, das "Gewitter"
    traegt — so faellt der umschliessende Container mit allen anderen Kacheln
    nicht faelschlich als Treffer an.
    """
    suppe = BeautifulSoup(html, "html.parser")
    kopf = [p for p in suppe.find_all("p")
            if p.get_text(strip=True) == "Metriken-Überblick"]
    assert len(kopf) == 1, (
        f"Erwartet genau EINEN Metriken-Ueberblick im Mail-HTML, "
        f"gefunden: {len(kopf)}")
    treffer = [
        el for el in kopf[0].parent.find_all(True)
        if "Gewitter" in el.get_text(strip=True)
        and not any("Gewitter" in kind.get_text(strip=True)
                    for kind in el.find_all(True))
    ]
    assert len(treffer) == 1, (
        f"Erwartet genau EINE Gewitter-Kachel im Metriken-Ueberblick, "
        f"gefunden: {[t.get_text(strip=True) for t in treffer]!r}")
    return treffer[0].get_text(strip=True)


def _pille_klartext(text: str, ueberschrift: str = "Metriken-Überblick") -> str:
    """Die Gewitter-Pille aus dem Metriken-Ueberblick der Klartext-Mail.

    ``ueberschrift`` unterscheidet Vollmail ("Metriken-Überblick") von der
    ASCII-gefalteten Kompakt-Mail ("Metriken-Ueberblick").
    """
    assert ueberschrift in text, (
        f"Metriken-Ueberblick fehlt in der Mail:\n{text}")
    block = text.split(ueberschrift, 1)[1]
    zeilen = [ln.strip() for ln in block.split("\n\n", 1)[0].splitlines()
              if "Gewitter" in ln]
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Gewitter-Pille im Metriken-Ueberblick, "
        f"gefunden: {zeilen!r}")
    return zeilen[0]


def _ausblick_zeile_text(text: str, ueberschrift: str) -> str:
    """Die EINE Ausblick-Zeile aus dem zugestellten Mailkoerper.

    Format-blind: die Zeile wird ueber ihre Position unter der Ueberschrift
    gefunden, nicht ueber ein Muster im Gewitterfeld. Ein Parser, der auf dem
    ALTEN Feldformat aufsetzte, wuerde nach dieser Aenderung nichts mehr
    finden und den Test faelschlich gruen melden (Muster #1929).
    """
    assert ueberschrift in text, (
        f"Ausblick '{ueberschrift}' fehlt in der Mail:\n{text}")
    rest = text.split(ueberschrift, 1)[1].splitlines()
    zeilen: list[str] = []
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


def _compare_klartext(punkte: list[ForecastDataPoint]) -> str:
    """Die ECHTE Vergleichsmail (Klartext) fuer EINEN Ort mit Ausblick.

    ``outlook_metrics=None`` = Altbestand ohne gespeicherte Spaltenauswahl;
    das ist der Token-Pfad, der sich den Zeilenbau (``render_outlook_plain()``,
    ``comparison.py:360``) mit dem Trip TEILT — genau die Flaeche, um die es
    in AC-9 geht.
    """
    ort = LocationResult(
        location=SavedLocation(id="ort-a", name="Ort A", lat=_LAT, lon=_LON,
                               elevation_m=1000, timezone="UTC"),
        score=50, hourly_data=punkte, outlook_hourly_data=punkte,
    )
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(0, 23), target_date=_MORGEN,
        created_at=datetime(2026, 8, 20, 4, 1),
    )
    return render_comparison_text(ergebnis, outlook_enabled=True,
                                  outlook_metrics=None)


def _gewitterfeld(zeile: str) -> str:
    """Das Gewitterfeld einer Klartext-Ausblickzeile — ab dem ``⚡`` bis zum
    Zeilenende (inklusive Peak-, Herkunfts- und Nachtzusatz).

    Ueber das Feld-EINLEITENDE Zeichen abgegrenzt, nicht ueber dessen Inhalt:
    so bleibt die Sonde auch dann sehend, wenn sich der Feldinhalt aendert —
    genau das ist hier der Fall. Trip- und Compare-Zeile unterscheiden sich
    im Vorspann (Etappenname fuehrt nur der Trip, ``show_name=False`` im
    Compare), das Gewitterfeld selbst muss identisch sein.
    """
    assert "⚡" in zeile, f"Kein Gewitterfeld in der Ausblickzeile: {zeile!r}"
    return "⚡" + zeile.split("⚡", 1)[1].rstrip()


def _telegram_ausblick(bericht) -> str:
    """Der Telegram-Ausblick-Block als EINE Zeile (``narrow._wrap`` bricht auf
    56 Zeichen an Wortgrenzen um; das Zusammenfuegen stellt den Originaltext
    her, solange kein Wort laenger als 56 Zeichen ist)."""
    bubbles = [b for b in bericht.telegram_bubbles if b.startswith("Ausblick")]
    assert len(bubbles) == 1, (
        f"Erwartet genau EINE Ausblick-Bubble, gefunden: {bubbles!r}")
    return " ".join(bubbles[0].splitlines()[1:])


# ---------------------------------------------------------------------------
# AC-1 / AC-2: die Stufe steht als WORT in der Pille — HTML und Klartext
# ---------------------------------------------------------------------------

def test_ac1_html_pille_nennt_die_gewitterstufe_als_wort():
    """AC-1: Given ein Trip-Briefing im Format "full" mit ausgewaehlter Metrik
    "Gewitter" und einer Etappe, deren hoechste Gewitterstufe im Tagesfenster
    "mittel" mit Beginn 14:00 Uhr und Spitze 18:00 Uhr ist / When der
    Empfaenger die HTML-E-Mail oeffnet / Then liest er in der Gewitter-Kachel
    das Wort "mittel" ausgeschrieben, nicht nur eine farbige Kachel ohne
    Stufenwort.

    RED heute: die Kachel zeigt "Gewitter ab 14:00 · stärkste 18:00 · CAPE" —
    die Stufe steckt allein im Ampelton.

    Exakte Gleichheit statt ``in``: das Stufenwort muss VOR "ab 14:00" stehen
    (die Spec legt "Gewitter mittel ab 14:00" fest); ein blosses ``in`` liesse
    "Gewitter ab 14:00 · stärkste 18:00 · mittel" durchgehen.
    """
    punkte = _tagespunkte({14: 400.0, 18: 800.0})
    stufen = _stufen(punkte)
    assert stufen[14] is ThunderLevel.LOW and stufen[18] is ThunderLevel.MED, (
        f"Vorbedingung: die ECHTE Fusion muss ab 14 Uhr ein Gewitter und als "
        f"Hoechststufe 'mittel' (18 Uhr) ergeben: {stufen!r}")

    kachel = _pille_html(_mail([_etappe(punkte)], []).email_html)
    assert kachel == "Gewitter mittel ab 14:00 · stärkste 18:00 · CAPE", (
        f"Die Gewitter-Kachel muss die Stufe als WORT vor der Beginnstunde "
        f"nennen. Erwartet 'Gewitter mittel ab 14:00 · stärkste 18:00 · CAPE', "
        f"erhalten: {kachel!r}")


def test_ac2_klartext_pille_nennt_dieselbe_gewitterstufe():
    """AC-2: Given dasselbe Briefing wie AC-1 / When der Empfaenger stattdessen
    die Klartext-Ansicht der Mail liest (Screenreader, Plaintext-Client) /
    Then liest er dieselbe Stufenaussage "mittel" in der Gewitter-Zeile — die
    Information ist dort nicht mehr ausschliesslich ueber Farbe codiert, die
    im Klartext gar nicht ankommt.

    Regressionsschutz gegen "nur HTML gefixt": geprueft wird der Klartext-Teil
    DERSELBEN Mail, und zusaetzlich, dass beide Teile denselben Wortlaut
    tragen.
    """
    punkte = _tagespunkte({14: 400.0, 18: 800.0})
    bericht = _mail([_etappe(punkte)], [])

    pille = _pille_klartext(bericht.email_plain)
    assert "mittel" in pille, (
        f"Im Klartext traegt keine Farbe — die Stufe muss dort als Wort "
        f"stehen: {pille!r}")
    assert pille == "Gewitter mittel ab 14:00 · stärkste 18:00 · CAPE", (
        f"Die Klartext-Pille muss denselben Wortlaut tragen wie die "
        f"HTML-Kachel: {pille!r}")
    assert pille == _pille_html(bericht.email_html), (
        f"HTML- und Klartext-Teil DERSELBEN Mail muessen dieselbe Pille "
        f"zeigen — sonst ist nur einer der beiden Renderpfade gefixt: "
        f"{pille!r} vs. {_pille_html(bericht.email_html)!r}")


# ---------------------------------------------------------------------------
# AC-3 / AC-4: die Onset-Stunde im Ausblick — Klartext und Kompakt
# ---------------------------------------------------------------------------

def test_ac3_klartext_ausblick_zeigt_die_onset_stunde():
    """AC-3: Given eine kuenftige Etappe im mehrtaegigen Ausblick mit
    Tagesgewitter ab Stunde 14 Uhr / When der Empfaenger den Klartext-Ausblick
    "Nächste Etappen" liest / Then sieht er in der Gewitterspalte dieser Zeile
    die Uhrzeit direkt neben dem Stufenwort (``⚡mittel@14``), nicht nur das
    Wort ohne jede Zeitangabe.

    RED heute: die Zeile zeigt "⚡mittel (hoch @18) · CAPE" — ``_dm[1]``
    (die Onset-Stunde) wird in ``render_outlook_plain()`` verworfen.

    Der Peak-Zusatz " (hoch @18)" und der Herkunfts-Zusatz " · CAPE" gehoeren
    zum Bestand (#1653/#1680 S5a) und werden hier mitgeprueft: die Aenderung
    darf ausschliesslich die Onset-Stunde HINZUFUEGEN, nichts umstellen.
    """
    punkte = _fusioniere([_dp(14, tag=_MORGEN, cape=800.0, cin=5.0),
                          _dp(18, tag=_MORGEN, cape=1500.0, cin=5.0)])
    stufen = _stufen(punkte)
    assert stufen[14] is ThunderLevel.MED and stufen[18] is ThunderLevel.HIGH, (
        f"Vorbedingung: Onset-Stunde 14 Uhr 'mittel', Spitze 18 Uhr 'hoch': "
        f"{stufen!r}")

    bericht = _mail([_etappe(_tagespunkte({}))], [_ausblick_zeile(punkte)])
    zeile = _ausblick_zeile_text(bericht.email_plain, _AUSBLICK_PLAIN)
    assert "⚡mittel@14" in zeile, (
        f"Der Klartext-Ausblick muss die Onset-Stunde am Gewitterfeld fuehren "
        f"('⚡mittel@14'), wie es die HTML-Ausblickzelle laengst tut: "
        f"{zeile!r}")
    assert zeile.rstrip().endswith("⚡mittel@14 (hoch @18) · CAPE"), (
        f"Nur die Onset-Stunde kommt hinzu — Peak-Zusatz und Herkunft bleiben "
        f"in Wortlaut und Reihenfolge unveraendert: {zeile!r}")


def test_ac4_kompakt_ausblick_zeigt_dieselbe_onset_stunde():
    """AC-4: Given dieselbe Etappe wie AC-3 / When der Empfaenger die
    Kompakt-Mail liest (``X-GZ-Format: compact``) / Then sieht er dieselbe
    Onset-Stunde in der Gewitterspalte der Ausblickzeile, im selben Format wie
    im Klartext-Ausblick.

    RED heute: die Zeile zeigt "Tmittel (hoch @18)".

    Die Kompakt-Mail ist ASCII-gefaltet — "⚡" wird zu "T", "·" zu "-". Das
    "@" der Onset-Stunde ueberlebt die Faltung (der Nachtteil fuehrt es seit
    #1671 bereits: "- nachts hoch @2"). Der Kompakt-Ausblick traegt
    bestandsgemaess KEINE Herkunft (#1680 S5a AC-13, von #1493 unberuehrt).
    """
    punkte = _fusioniere([_dp(14, tag=_MORGEN, cape=800.0, cin=5.0),
                          _dp(18, tag=_MORGEN, cape=1500.0, cin=5.0)])
    bericht = _mail([_etappe(_tagespunkte({}))], [_ausblick_zeile(punkte)],
                    report_config=_KOMPAKT)
    zeile = _ausblick_zeile_text(bericht.email_plain, _AUSBLICK_KOMPAKT)
    assert "Tmittel@14" in zeile, (
        f"Die Kompakt-Ausblickzeile muss dieselbe Onset-Stunde fuehren wie "
        f"der Klartext-Ausblick (ASCII-gefaltet 'Tmittel@14'): {zeile!r}")
    assert zeile.rstrip().endswith("Tmittel@14 (hoch @18)"), (
        f"Nur die Onset-Stunde kommt hinzu — der Peak-Zusatz bleibt "
        f"unveraendert, eine Herkunft entsteht hier weiterhin nicht: "
        f"{zeile!r}")


# ---------------------------------------------------------------------------
# AC-5: INVARIANZ-WAECHTER — Telegram und SMS bleiben zeichengleich
# ---------------------------------------------------------------------------

def test_ac5_telegram_und_sms_bleiben_zeichengleich():
    """AC-5: Given ein Trip mit derselben Etappenfolge wie AC-1/AC-3 / When
    Telegram-Trendblock und SMS-Trip-Briefing fuer dieselbe Etappe erzeugt
    werden / Then bleibt deren Text zeichengleich zum Stand vor #1493
    (``⚡mittel@14(hoch@18)`` bzw. ``TH:M@14(H@18)``) — kein Kanal, der die
    Onset-Stunde bereits fuehrte, aendert sich sichtbar.

    ⚠️ INVARIANZ-WAECHTER: dieser Test ist HEUTE SCHON GRUEN und muss es
    bleiben. Er ist kein vergessener RED-Test, sondern die Gegenrichtung: er
    faellt, sobald jemand die Onset-Stunde in ``format_trend_tokens()``
    (``helpers.py:994-1015``) oder im SMS-Tokenbau statt in den beiden
    E-Mail-Verbrauchern nachruestet — genau der Fehler, den die Spec
    ausschliesst, weil ``format_trend_tokens()`` mit Ortsvergleich, SMS und
    Telegram geteilt ist.

    Die Fixture ist bewusst eine ANDERE als in AC-1: die SMS-Erwartung
    ``TH:M@14(H@18)`` verlangt eine heutige Etappe mit "mittel" um 14 und
    "hoch" um 18 Uhr, waehrend AC-1 als Hoechststufe "mittel" braucht. Beide
    Zusicherungen an derselben Etappe sind rechnerisch unvereinbar.
    """
    heute = _tagespunkte({14: 800.0, 18: 1500.0})
    stufen = _stufen(heute)
    assert stufen[14] is ThunderLevel.MED and stufen[18] is ThunderLevel.HIGH, (
        f"Vorbedingung der SMS-Erwartung: 14 Uhr 'mittel', 18 Uhr 'hoch': "
        f"{stufen!r}")
    morgen = _fusioniere([_dp(14, tag=_MORGEN, cape=800.0, cin=5.0),
                          _dp(18, tag=_MORGEN, cape=1500.0, cin=5.0)])

    bericht = _mail([_etappe(heute)], [_ausblick_zeile(morgen)])

    assert "TH:M@14(H@18)" in bericht.sms_text, (
        f"Das SMS-Gewitter-Token muss zeichengleich zum Stand vor #1493 "
        f"bleiben: {bericht.sms_text!r}")
    block = _telegram_ausblick(bericht)
    assert "⚡mittel@14(hoch@18) · CAPE" in block, (
        f"Der Telegram-Trendblock muss zeichengleich zum Stand vor #1493 "
        f"bleiben — er fuehrte die Onset-Stunde bereits: {block!r}")


# ---------------------------------------------------------------------------
# AC-6 / AC-7: die Raender — kein Ereignis, keine Daten
# ---------------------------------------------------------------------------

def test_ac6_ohne_gewitter_bleiben_pille_und_ausblick_ohne_stufe_und_stunde():
    """AC-6: Given eine Etappe ohne jedes Gewitter im Tagesfenster / When der
    Empfaenger Pille und Ausblick derselben Mail liest / Then zeigen beide
    weiterhin "kein Gewitter" — ohne erfundenes Stufenwort und ohne eine
    Uhrzeit, die es mangels Ereignis nicht geben kann.

    ⚠️ ZWEITEILIG: die Abwesenheits-Zusicherung selbst ist heute schon
    erfuellt (Invarianz-Waechter — sie faellt, sobald das neue Stufenwort
    bedingungslos eingesetzt wird, "Gewitter kein ab …", oder die
    Onset-Stunde ohne Ereignis erscheint). ROT ist heute allein die
    Gegenprobe am Ende, die neues Verhalten verlangt. Genau diese Paarung
    macht den Test zum Nachweis: ohne Gegenprobe waere er auch dann gruen,
    wenn Stufenwort und Onset-Stunde NIRGENDS erschienen.

    Wortlaut-Praezisierung gegenueber der Spec (gemessen 2026-08-18): die
    Ausblickzeile zeigt in diesem Fall nicht die Prosa "kein Gewitter",
    sondern das Bestandszeichen ``⚡–`` (``_THUNDER_MAP["NONE"]["plain"]``,
    ASCII-gefaltet ``T-``). Gemeint und geprueft ist die Sachaussage der
    Spec: kein Stufenwort ausser "kein", kein ``@``, keine Uhrzeit.

    Gegenprobe an DERSELBEN Fixture-Bauart: dieselbe Etappe mit einem
    CAPE-Wert ueber der niedrigsten Sprosse zeigt Stufe UND Stunde sehr wohl
    — ohne sie bewiese der Abwesenheits-Test nichts.
    """
    ruhig_heute = _tagespunkte({})
    assert set(_stufen(ruhig_heute).values()) == {ThunderLevel.NONE}, (
        f"Vorbedingung: die ECHTE Fusion muss ueberall 'kein Gewitter' "
        f"ergeben: {_stufen(ruhig_heute)!r}")
    ruhig_morgen = _fusioniere(
        [_dp(h, tag=_MORGEN, cape=200.0, cin=5.0) for h in range(6, 19)])

    bericht = _mail([_etappe(ruhig_heute)], [_ausblick_zeile(ruhig_morgen)])

    pille = _pille_klartext(bericht.email_plain)
    assert pille == "kein Gewitter", (
        f"Ohne Ereignis bleibt die Pille zeichengleich 'kein Gewitter' — kein "
        f"Stufenwort, kein 'ab HH:00': {pille!r}")
    assert pille == _pille_html(bericht.email_html), (
        f"HTML- und Klartext-Pille muessen auch im Leerfall uebereinstimmen: "
        f"{pille!r}")

    zeile = _ausblick_zeile_text(bericht.email_plain, _AUSBLICK_PLAIN)
    assert zeile.rstrip().endswith("⚡–"), (
        f"Ohne Ereignis bleibt das Gewitterfeld des Ausblicks zeichengleich "
        f"'⚡–': {zeile!r}")
    assert "@" not in zeile.split("⚡")[-1], (
        f"Ohne Ereignis darf im Gewitterfeld keine Uhrzeit stehen: {zeile!r}")
    for wort in ("leicht", "mittel", "hoch"):
        assert wort not in zeile, (
            f"Ohne Ereignis darf kein Stufenwort '{wort}' erscheinen: "
            f"{zeile!r}")

    laut = _mail([_etappe(_tagespunkte({14: 800.0}))],
                 [_ausblick_zeile(_fusioniere(
                     [_dp(14, tag=_MORGEN, cape=800.0, cin=5.0)]))])
    assert "mittel" in _pille_klartext(laut.email_plain), (
        f"Gegenprobe gescheitert: mit erreichter Stufe MUSS das Stufenwort in "
        f"der Pille erscheinen, sonst beweist der Leerfall nichts: "
        f"{_pille_klartext(laut.email_plain)!r}")
    laut_zeile = _ausblick_zeile_text(laut.email_plain, _AUSBLICK_PLAIN)
    assert "@14" in laut_zeile, (
        f"Gegenprobe gescheitert: mit Ereignis MUSS die Onset-Stunde in der "
        f"Ausblickzeile erscheinen, sonst beweist der Leerfall nichts: "
        f"{laut_zeile!r}")


def test_ac7_zieldatenluecke_zeigt_weiterhin_gewitter_fragezeichen():
    """AC-7: Given eine Zieletappe mit Datenluecke zwischen Ankunft und 19 Uhr
    (``has_gap=True``, Ziel-Beobachtungsluecke #1331) / When der Empfaenger die
    Pille liest / Then zeigt sie weiterhin "Gewitter ?" — die Datenluecke wird
    nicht durch das neue Stufenwort in eine positive Entwarnung verwandelt.

    ⚠️ INVARIANZ-WAECHTER: heute gruen, muss gruen bleiben. Er faellt, sobald
    das Stufenwort VOR dem ``has_gap``-Zweig eingesetzt wird und aus der
    Luecke ein "Gewitter kein" oder "Gewitter kein ab …" macht.

    Die Luecke wird nicht behauptet, sondern ueber den produktiven
    ``compute_has_gap()`` aus der echten (leeren) Fensterreihe abgeleitet —
    derselbe Weg, den ``notification_service.send_trip_report()`` geht.
    """
    segmente = [_etappe_ohne_daten()]
    has_gap = compute_has_gap(segmente, None, _TZ)
    assert has_gap is True, (
        "Vorbedingung: ein echter Fensterausfall MUSS als Ziel-Datenluecke "
        "erkannt werden — sonst prueft dieser Test den falschen Zweig")

    bericht = _mail(segmente, [], has_gap=has_gap)
    pille = _pille_klartext(bericht.email_plain)
    assert pille == "Gewitter ?", (
        f"Bei Ziel-Datenluecke bleibt die Pille zeichengleich 'Gewitter ?' — "
        f"keine Stufe, kein 'ab HH:00': {pille!r}")
    for wort in ("leicht", "mittel", "hoch", "kein"):
        assert wort not in pille, (
            f"Eine Datenluecke darf nicht in eine Stufenaussage '{wort}' "
            f"verwandelt werden: {pille!r}")


# ---------------------------------------------------------------------------
# AC-9: der Ortsvergleich erbt die Onset-Stunde aus dem geteilten Zeilenbau
# ---------------------------------------------------------------------------

def test_ac9_ortsvergleich_zeigt_dieselbe_onset_stunde_wie_der_trip():
    """AC-9 (PO-Entscheid 2026-08-18): Given ein Ortsvergleich mit einem Ort,
    dessen Tagesgewitter um 14 Uhr beginnt / When die Vergleichsmail gerendert
    wird / Then traegt die Gewitterspalte ihres Klartext-Ausblicks dieselbe
    Onset-Stunde wie die Trip-Mail derselben Stundenreihe.

    Warum das kein Nebeneffekt, sondern eine Zusicherung ist: Trip-Ausblick
    und Compare-Ausblick teilen sich EINEN Zeilenbau — ``comparison.py:360``
    ruft dasselbe ``render_outlook_plain()`` auf wie ``plain.py``. Die
    Alternative waere ein Unterdrueckungs-Schalter im geteilten Baustein,
    also genau das Anti-Pattern, das die Trip/Compare-Teilungs-Invariante
    ausschliesst (CLAUDE.md; #1170).

    Gemessen wird deshalb die GLEICHHEIT des Gewitterfelds beider Flaechen an
    DERSELBEN Fixture, nicht zweimal derselbe Text. Zwei getrennte
    Textpruefungen wuerden gruen bleiben, wenn beide Seiten gemeinsam auf ein
    drittes, falsches Format abrutschten; die Gleichheits-Assertion faellt
    dagegen, sobald eine Seite ohne die andere geaendert wird. Die zweite
    Assertion pinnt zusaetzlich das SOLL-Format — sonst waere der Test heute
    schon gruen (beide Seiten zeigen heute uebereinstimmend ``⚡mittel (hoch
    @18) · CAPE``, also uebereinstimmend OHNE Onset-Stunde).
    """
    punkte = _fusioniere([_dp(14, tag=_MORGEN, cape=800.0, cin=5.0),
                          _dp(18, tag=_MORGEN, cape=1500.0, cin=5.0)])
    stufen = _stufen(punkte)
    assert stufen[14] is ThunderLevel.MED and stufen[18] is ThunderLevel.HIGH, (
        f"Vorbedingung: Onset-Stunde 14 Uhr 'mittel', Spitze 18 Uhr 'hoch': "
        f"{stufen!r}")

    trip = _mail([_etappe(_tagespunkte({}))], [_ausblick_zeile(punkte)])
    trip_feld = _gewitterfeld(
        _ausblick_zeile_text(trip.email_plain, _AUSBLICK_PLAIN))
    compare_feld = _gewitterfeld(
        _ausblick_zeile_text(_compare_klartext(punkte), _AUSBLICK_COMPARE))

    assert compare_feld == trip_feld, (
        f"Trip- und Compare-Ausblick teilen EINEN Zeilenbau — ihr "
        f"Gewitterfeld muss zeichengleich sein. Trip: {trip_feld!r}, "
        f"Compare: {compare_feld!r}")
    assert compare_feld == "⚡mittel@14 (hoch @18) · CAPE", (
        f"Beide Flaechen muessen die Onset-Stunde fuehren — Gleichheit allein "
        f"genuegt nicht, weil sie auch bei gemeinsam falschem Format bestuende: "
        f"{compare_feld!r}")
