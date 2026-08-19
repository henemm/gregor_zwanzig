"""TDD RED — Issue #1680 Scheibe 4: Herkunft der Gewitterstufe in der
Trip-Stundentabelle (E-Mail-Klartext + Telegram-rich-Bubbles).

SPEC: docs/specs/modules/feat_1680_s4_gewitter_herkunft_trip_stundentabelle.md
(AC-1 bis AC-13)

RED-Ursache (heute): ``TripReportFormatter._dp_to_row()`` setzt keinen
Seitenkanal ``row["_thunder_signals"]`` (D1), ``_aggregate_night_block()``
ebenso wenig (D2), und ``email.helpers.fmt_val()``s Roh-/Klartext-Zweig
haengt keine Herkunft an (D3) -- daher zeigt weder die E-Mail-Stundentabelle
noch die davon strukturell erbende Telegram-rich-Stundentabelle (Bubbles)
neben der Gewitterstufe die tragende(n) Zutat(en).

Pruefort=Wirkort: JEDER Test laeuft ueber die echte Renderkette bis zum
zurueckgegebenen ``email_plain``/Telegram-Bubble-Text -- Ausnahme AC-10, das
bewusst ``fmt_val()`` direkt prueft (das ist dort der Untersuchungsgegenstand
selbst, s. Spec Testplan). AC-6/AC-7/AC-8 rufen ``_aggregate_night_block()``
(echte Konstruktion) gefolgt von ``fmt_val()`` (echtes Rendern der Zelle),
wie in den jeweiligen AC-Testhinweisen der Spec vorgegeben.

Kein Mock-Theater: Stufen und Traegerlisten entstehen ueber die ECHTE Fusion
(``providers.thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``) -- kein im Test getippter Wert, keine getippte
Schwelle.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.loader import get_snapshots_dir  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, ThunderLevel, TripSegment,
)
from output.metric_format import thunder_ampel_band  # noqa: E402
from output.renderers.email.helpers import _ampel_dot_css, fmt_val  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung
# (``metric_format.THUNDER_SIGNAL_LABEL_DE``). Keine davon darf in SMS/
# Premium-SMS auftauchen (AC-11).
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_ETAPPE = "Test-Etappe"
_TAG = date(2026, 8, 20)
_USER = "default"
_TRIP_ID_SNAPSHOT = "herkunft-trip-stundentabelle"


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, echte Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _TAG, cape=None, cin=None, lpi=None,
        dichte=None, precip=0.0, gust=12.0) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN -- Stufe und Traeger rechnet die Fusion."""
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=gust, precip_1h_mm=precip,
        cloud_total_pct=40, humidity_pct=50,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
    )


def _reihe(punkte: list[ForecastDataPoint]) -> NormalizedTimeseries:
    """Wendet die ECHTE Fusion in-place auf ``punkte`` an (setzt
    ``dp.thunder_level``/``dp.thunder_level_signals``) und liefert eine
    Zeitreihe daraus -- keine im Test getippte Schwelle."""
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=punkte,
    )


def _segment(punkte: list[ForecastDataPoint], *, tag: date = _TAG,
             start_h: int = 6, end_h: int = 17, seg_id: int = 1) -> SegmentWeatherData:
    """Segment, dessen Aggregat die ECHTE Engine rechnet."""
    reihe = _reihe(punkte)
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(tag.year, tag.month, tag.day, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(tag.year, tag.month, tag.day, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h), distance_km=10.0,
        ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _dc():
    return build_default_display_config()


def _mail(segmente):
    """Der ECHTE Trip-Bericht (HTML + Klartext + SMS + Telegram-Bubbles)
    ueber den produktiven Formatierer -- Pruefort = Wirkort."""
    return TripReportFormatter().format_email(
        segmente, "Test-Trip", "evening", display_config=_dc(),
        tz=_TZ, stage_name=_ETAPPE,
    )


def _zeile(text: str, stunde: str) -> str:
    """Die EINE Stundentabellen-Zeile fuer ``stunde`` (z.B. "14") im
    Klartext-Tabellenblock -- Zeilen beginnen dort mit dem gepolsterten
    Stundenwert am Zeilenanfang."""
    treffer = [ln for ln in text.splitlines() if re.match(rf"^\s*{stunde}\s", ln)]
    assert len(treffer) == 1, (
        f"Erwartet genau EINE Zeile fuer Stunde {stunde} im Tabellentext, "
        f"gefunden: {treffer!r}\n--- Volltext ---\n{text}")
    return treffer[0]


def _neue_nacht_zelle(formatter: TripReportFormatter, dps: list[ForecastDataPoint]) -> str:
    """Baut EINEN Nacht-Block ueber die echte Konstruktionsstelle
    (``_aggregate_night_block()``, D2) und rendert seine Gewitter-Zelle ueber
    die echte Formatierfunktion (``fmt_val()``, D3) -- exakt der von der Spec
    fuer AC-6/AC-7/AC-8 vorgegebene zweistufige Pruefweg."""
    _reihe(dps)
    row = formatter._aggregate_night_block(dps, _dc())
    return fmt_val("thunder", row.get("thunder"), row=row)


# ---------------------------------------------------------------------------
# Pro-Stunde (D1): _dp_to_row() ueber die volle E-Mail-/Telegram-Kette
# ---------------------------------------------------------------------------

def test_ac1_pro_stunde_nennt_die_tragende_zutat():
    """AC-1: Given eine Stunde erreicht ihre Gewitterstufe ausschliesslich
    ueber CAPE, When die Vollmail gerendert wird, Then zeigt die
    Stundentabellen-Zeile im Klartextteil "· CAPE" neben der Stufe."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
                   start_h=6, end_h=16)
    bericht = _mail([seg])
    zeile = _zeile(bericht.email_plain, "14")
    assert "· CAPE" in zeile, (
        f"Die Stundentabellen-Zeile muss die tragende Zutat neben der "
        f"Stufe nennen: {zeile!r}")


def test_ac2_telegram_rich_erbt_dieselbe_herkunft():
    """AC-2 (berichtigt waehrend GREEN, s. Spec "Berichtigung waehrend
    GREEN"): Given dieselbe Stunde wird als Telegram-Bubble gerendert, Then
    enthaelt der Segment-Block-Text sowohl die Stufe ("hoch") als auch die
    Zutat ("CAPE") -- strukturell geerbt ueber dieselbe
    fmt_val()/_dp_to_row()-Kette (D4), ohne eigenen Code-Pfad. Kein
    zusammenhaengender Teilstring "· CAPE" gefordert, da der bestehende
    32-Zeichen-Hartumbruch (`narrow._wrap`) den Zusatz mitten im Wort trennen
    kann -- unveraendertes, nicht zu dieser Scheibe gehoerendes Verhalten."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
                   start_h=6, end_h=16)
    bericht = _mail([seg])
    segment_block = next(
        b for b in bericht.telegram_bubbles if "<pre>" in b)
    assert "hoch" in segment_block, (
        f"Der Segment-Block muss die Gewitterstufe zeigen: {segment_block!r}")
    assert "CAPE" in segment_block, (
        f"Der Segment-Block muss die tragende Zutat zeigen (ggf. auf "
        f"Folgezeile durch den Hartumbruch): {segment_block!r}")


def test_ac3_beide_zutaten_derselben_stunde_katalogreihenfolge():
    """AC-3: Given CAPE UND Blitzpotenzial erreichen in derselben Stunde
    gemeinsam die Hoechststufe, Then werden BEIDE in Katalogreihenfolge
    genannt -- kein Gewinner wird gekuert (PO-Auslegung (ii))."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0, lpi=60.0) for h in (14, 15)],
                   start_h=6, end_h=16)
    bericht = _mail([seg])
    zeile = _zeile(bericht.email_plain, "14")
    assert "· CAPE, Blitzpotenzial" in zeile, (
        f"Beide Traeger der Hoechststufe muessen in Katalogreihenfolge "
        f"erscheinen: {zeile!r}")


def test_ac4_ohne_gewitter_bleibt_pro_stunde_zeichengleich():
    """AC-4 (NONE-Gegenprobe): Given eine Stunde zeigt "kein" Gewitter, Then
    bleibt die Zeile ohne ·-Zusatz -- obwohl der Pro-Stunde-Durchgriff (D1)
    roh und ohne eigenen Guard erfolgt.

    Gegenprobe im selben Test: dieselbe Stunde mit CAPE ueber der Leiter
    zeigt die Herkunft sehr wohl -- sonst waere dieses AC auch dann gruen,
    wenn die Herkunft nirgends erschiene.

    Berichtigung waehrend GREEN (Adversary-Fund F001): die "ruhige" Fixture
    muss ein ECHTES ``ThunderLevel.NONE`` aus der Fusion erzeugen, nicht
    Python-``None`` (alle vier Signale fehlen). Ein Python-``None`` wird von
    ``fmt_val()``s allgemeinem Guard ``if val is None: return "-"`` VOR dem
    thunder-Zweig abgefangen -- der neue D1-Code wird dann nie erreicht,
    das AC bliebe auch bei einem kaputten Seitenkanal gruen. ``cape=50.0``
    liegt sicher unter der niedrigsten Sprosse der Testregion DE_ALPEN/
    icon_d2 (300.0 J/kg, ``cape_ladder_thresholds_jkg()``) und fuehrt ueber
    die echte Fusion zu ``ThunderLevel.NONE`` mit leerer Traegerliste.
    """
    ruhig = _segment([_dp(h, cape=50.0) for h in (14, 15)], start_h=6, end_h=16)
    zeile_ruhig = _zeile(_mail([ruhig]).email_plain, "14")
    assert "·" not in zeile_ruhig, (
        f"Eine Stunde ohne jedes Gewittersignal darf keinen ·-Zusatz "
        f"tragen: {zeile_ruhig!r}")

    laut = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
                    start_h=6, end_h=16)
    zeile_laut = _zeile(_mail([laut]).email_plain, "14")
    assert "· CAPE" in zeile_laut, (
        f"Gegenprobe gescheitert: mit erreichter Stufe MUSS die Herkunft "
        f"erscheinen, sonst beweist die 'ruhige' Zeile nichts: {zeile_laut!r}")


def test_ac5_kohaerenz_pro_stunde_keine_vermischung_benachbarter_zeilen():
    """AC-5: Given zwei benachbarte Stunden tragen ihre Stufe ueber
    verschiedene Zutaten, Then zeigt JEDE Zeile ausschliesslich die
    Zutat(en) IHRES EIGENEN Datenpunkts -- keine Vermischung."""
    seg = _segment(
        [_dp(14, cape=1500.0, cin=5.0), _dp(15, dichte=0.005)],
        start_h=6, end_h=16,
    )
    bericht = _mail([seg])
    zeile_a = _zeile(bericht.email_plain, "14")
    zeile_b = _zeile(bericht.email_plain, "15")
    assert "CAPE" in zeile_a and "Blitzdichte" not in zeile_a, (
        f"Zeile A (Stunde 14) darf nur ihre EIGENE Zutat zeigen: {zeile_a!r}")
    assert "Blitzdichte" in zeile_b and "CAPE" not in zeile_b, (
        f"Zeile B (Stunde 15) darf nur ihre EIGENE Zutat zeigen: {zeile_b!r}")


# ---------------------------------------------------------------------------
# Nacht-Block (D2): _aggregate_night_block() + fmt_val() (Spec-Testhinweise)
# ---------------------------------------------------------------------------

def test_ac6_nacht_block_vereinigt_zutaten_zweier_datenpunkte():
    """AC-6: Given zwei Datenpunkte desselben Nachtblocks erreichen die
    Blockhoechststufe ueber unterschiedliche Zutaten, Then nennt die Zeile
    BEIDE -- nicht nur die eines einzelnen dp des Blocks."""
    formatter = TripReportFormatter()
    formatter._tz = _TZ
    dpA = _dp(0, cape=1500.0, cin=5.0)
    dpB = _dp(1, lpi=60.0)
    text = _neue_nacht_zelle(formatter, [dpA, dpB])
    assert "CAPE" in text and "Blitzpotenzial" in text, (
        f"Der Nacht-Block muss BEIDE Traeger der Hoechststufe nennen: {text!r}")


def test_ac7_nacht_block_kein_leck_unterhalb_maximums():
    """AC-7: Given im selben Nachtblock traegt ein dritter Datenpunkt eine
    Zutat, die NUR eine niedrigere Stufe erreicht, Then erscheint diese
    dritte Zutat NICHT in der Zeile."""
    formatter = TripReportFormatter()
    formatter._tz = _TZ
    dpA = _dp(0, cape=1500.0, cin=5.0)
    dpB = _dp(1, lpi=60.0)
    dpC = _dp(1, dichte=0.005)
    text = _neue_nacht_zelle(formatter, [dpA, dpB, dpC])
    assert "CAPE" in text and "Blitzpotenzial" in text, (
        f"Beide Traeger der Hoechststufe muessen erscheinen: {text!r}")
    assert "Blitzdichte" not in text, (
        f"Die dritte Zutat traegt nur eine NIEDRIGERE Stufe als das "
        f"Blockmaximum und darf NICHT erscheinen: {text!r}")


def test_ac8_nacht_block_none_bleibt_zeichengleich():
    """AC-8 (Nacht-Block NONE ⇒ kein Zusatz): Given alle Datenpunkte eines
    Nachtblocks zeigen "kein" Gewitter, Then bleibt die Zeile ohne
    ·-Zusatz -- garantiert durch union_of_max_carriers() selbst.

    Gegenprobe im selben Test: ein Block MIT erreichter Stufe zeigt die
    Herkunft sehr wohl.

    Berichtigung waehrend GREEN (Adversary-Fund F001, analog AC-4): die
    "ruhige" Fixture braucht ein ECHTES ``ThunderLevel.NONE`` je Datenpunkt,
    sonst maskiert ``fmt_val()``s allgemeiner ``val is None``-Guard jeden
    Fehler im neuen D2-Code. ``cape=50.0`` liegt sicher unter der
    niedrigsten Sprosse der Testregion (300.0 J/kg, s. AC-4-Begruendung).
    """
    formatter = TripReportFormatter()
    formatter._tz = _TZ
    ruhig_text = _neue_nacht_zelle(
        formatter, [_dp(0, cape=50.0), _dp(1, cape=50.0)])
    assert "·" not in ruhig_text, (
        f"Ein Nachtblock ohne jedes Gewittersignal darf keinen ·-Zusatz "
        f"tragen: {ruhig_text!r}")

    laut_text = _neue_nacht_zelle(
        formatter, [_dp(0, cape=1500.0, cin=5.0), _dp(1, lpi=60.0)])
    assert "CAPE" in laut_text and "Blitzpotenzial" in laut_text, (
        f"Gegenprobe gescheitert: ein Nachtblock MIT erreichter Stufe MUSS "
        f"die Herkunft zeigen, sonst beweist der 'ruhige' Block nichts: "
        f"{laut_text!r}")


# ---------------------------------------------------------------------------
# Scope-Grenzen (D3-Nebenwirkungen bewusst AUSGENOMMEN)
# ---------------------------------------------------------------------------

def test_ac9_ampel_kreis_modus_bleibt_unveraendert():
    """AC-9 (bewusste Scope-Grenze): Given die Gewitter-Spalte wird im
    HTML-Ampel-Kreis-Modus gerendert, When eine Stunde eine Herkunft haette,
    Then bleibt der gerenderte Kreis byteidentisch zum unveraenderten
    Ampel-Zweig (``_ampel_dot_css``) -- kein Text, kein visueller
    Herkunfts-Indikator."""
    formatter = TripReportFormatter()
    formatter._tz = _TZ
    dp = _dp(14, cape=1500.0, cin=5.0)
    _reihe([dp])
    row = formatter._dp_to_row(dp, _dc())
    band = thunder_ampel_band(row["thunder"])
    hail = row.get("_hail_flag") is True
    erwartet = _ampel_dot_css(band, hail=hail)
    ergebnis = fmt_val(
        "thunder", row["thunder"], html=True,
        indicator_keys={"thunder"}, row=row,
    )
    assert ergebnis == erwartet, (
        f"Der Ampel-Kreis-Modus darf durch den neuen Seitenkanal NICHT "
        f"veraendert werden: erwartet {erwartet!r}, erhalten {ergebnis!r}")


def test_ac10_fmt_val_ohne_seitenkanal_bleibt_zeichengleich():
    """AC-10 (Rueckwaertskompatibilitaet): Given ein Aufrufer ruft
    fmt_val(key="thunder", ...) OHNE row oder mit row ohne
    "_thunder_signals", Then bleibt die Ausgabe zeichengleich zum Verhalten
    vor dieser Scheibe -- kein Fehler, kein leerer ·-Zusatz."""
    ohne_row = fmt_val("thunder", ThunderLevel.LOW, row=None)
    leeres_row = fmt_val("thunder", ThunderLevel.LOW, row={})
    assert ohne_row == "leicht", f"row=None muss unveraendert bleiben: {ohne_row!r}"
    assert leeres_row == "leicht", (
        f"row={{}} ohne '_thunder_signals' muss unveraendert bleiben: {leeres_row!r}")


def test_ac11_sms_bleibt_ohne_herkunft():
    """AC-11: Given dieselbe Fixture wuerde in der Stundentabelle eine
    Herkunft zeigen, Then enthaelt weder report.sms_text noch der
    tatsaechliche Rueckfall (sms_text or email_plain) eine der vier
    Zutat-Bezeichnungen; report.sms_text ist nicht-leer.

    Gegenprobe im selben Test: die Mail DERSELBEN Fixture zeigt die
    Herkunft sehr wohl.
    """
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
                   start_h=6, end_h=16)
    bericht = _mail([seg])

    assert bericht.sms_text, (
        "sms_text muss immer erzeugt werden -- sonst greift der Rueckfall "
        "`sms_text or email_plain` und die Herkunft koennte in die SMS "
        "durchsickern")
    zugestellt = bericht.sms_text or bericht.email_plain
    for zutat in ALLE_ZUTATEN:
        assert zutat not in zugestellt, (
            f"SMS/Premium-SMS sind bewusst OHNE Herkunft -- '{zutat}' darf "
            f"nicht vorkommen: {zugestellt!r}")

    zeile = _zeile(bericht.email_plain, "14")
    assert "· CAPE" in zeile, (
        f"Gegenprobe gescheitert: die Mail DERSELBEN Fixture MUSS die "
        f"Herkunft zeigen, sonst beweist die SMS-Abwesenheit nichts: {zeile!r}")


def test_ac12_compare_importiert_fmt_val_nicht():
    """AC-12 (Compare strukturell unberuehrt): Given fmt_val() wird um den
    Seitenkanal '_thunder_signals' erweitert, Then bleibt der gesamte
    Compare-Pfad unberuehrt, weil er fmt_val() gar nicht aufruft
    (Grep-basierte Struktur-Assertion, kein Verhaltens-Mock)."""
    import output.renderers.comparison as comparison_mod
    import output.renderers.email.compare_html as compare_html_mod

    quelle_comparison = inspect.getsource(comparison_mod)
    quelle_compare_html = inspect.getsource(compare_html_mod)
    assert "fmt_val" not in quelle_comparison, (
        "comparison.py darf fmt_val() NICHT importieren -- sonst waere die "
        "Compare-Stundentabelle vom neuen Seitenkanal betroffen")
    assert "fmt_val" not in quelle_compare_html, (
        "compare_html.py darf fmt_val() NICHT importieren -- sonst waere die "
        "Compare-HTML-Stundentabelle vom neuen Seitenkanal betroffen")


def test_ac13_alt_schnappschuss_zeigt_stufe_ohne_herkunft():
    """AC-13: Given ein gespeicherter Schnappschuss OHNE das Feld
    thunder_level_signals (Alt-Snapshot vor Scheibe 1) wird geladen, Then
    zeigt die Stundenzeile die Gewitterstufe unveraendert, aber OHNE
    Herkunfts-Zusatz -- kein Fehler.

    Gegenprobe im selben Test: derselbe Trip mit VOLLSTAENDIGEM Schnappschuss
    nennt die Zutat sehr wohl.
    """
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
                   start_h=6, end_h=16)
    WeatherSnapshotService(_USER).save(_TRIP_ID_SNAPSHOT, [seg], _TAG)

    vollstaendig = WeatherSnapshotService(_USER).load(_TRIP_ID_SNAPSHOT)
    zeile_voll = _zeile(_mail(vollstaendig).email_plain, "14")
    assert "· CAPE" in zeile_voll, (
        f"Gegenprobe gescheitert: der vollstaendige Schnappschuss MUSS die "
        f"Herkunft zeigen: {zeile_voll!r}")

    pfad = get_snapshots_dir(_USER) / f"{_TRIP_ID_SNAPSHOT}.json"
    roh = json.loads(pfad.read_text())
    for seg_roh in roh["segments"]:
        for stunde in seg_roh.get("hourly", []):
            stunde.pop("thunder_level_signals", None)
    pfad.write_text(json.dumps(roh, indent=2))

    alt = WeatherSnapshotService(_USER).load(_TRIP_ID_SNAPSHOT)
    zeile_alt = _zeile(_mail(alt).email_plain, "14")
    assert "hoch" in zeile_alt, (
        f"Die Gewitterstufe selbst muss trotz Alt-Schnappschuss erscheinen: "
        f"{zeile_alt!r}")
    assert "CAPE" not in zeile_alt and "·" not in zeile_alt, (
        f"Ein Alt-Schnappschuss ohne Traegerfeld zeigt KEINEN Herkunfts-"
        f"Zusatz: {zeile_alt!r}")
