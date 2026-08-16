"""TDD RED — Issue #1680 Scheibe 1: Herkunft der Gewitterstufe im Ortsvergleich.

SPEC: docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md
(AC-1 bis AC-7, AC-10 bis AC-12; AC-8/AC-9 in
``test_thunder_origin_snapshot_roundtrip.py``).

RED-Ursache (heute): ``metric_format.thunder_signal_carriers()``,
``ForecastDataPoint.thunder_level_signals`` und
``compare_html.loc_thunder_signals()`` existieren nicht, ``_fmt_thunder()``
kennt keinen dritten Parameter -> jede Gewitterzelle zeigt nur die Stufe.

Kein Mock-Theater: echte ``ForecastDataPoint``-Rohwerte, echte Fusion
(``thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``), echte Renderer bis zum zurueckgegebenen Body.
"""
from __future__ import annotations

import html as _html
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.model_registry import cape_ladder_thresholds_jkg, lpi_thresholds_jkg  # noqa: E402
from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.comparison import (  # noqa: E402
    render_compare_email, render_compare_sms, render_compare_telegram,
)
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402

# Die vier Zutaten der Fusion (metric_format.thunder_level_from_signals) in
# ihrer deutschen Beschriftung -- KEINE davon darf im SMS-Kanal auftauchen
# (AC-5). Die frueher hier ebenfalls genannte Compare-Stundentabelle (AC-11)
# zeigt die Herkunft seit Issue #1680 Scheibe 3 sehr wohl -- s. den Docstring
# von ``test_ac11_trip_stundenzelle_bleibt_ohne_herkunft``.
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def _dp(h: int, *, cape=None, cin=None, lpi=None, dichte=None, hail=None, code=None):
    """Ein Stunden-Datenpunkt mit ROHWERTEN -- die Stufe rechnet die Fusion.

    ``code`` ist die Wettercode-Stufe dieser Stunde (``dp.thunder_level``, das
    Signal "wettercode" der Fusion) -- die EINZIGE Zutat, die schon als Stufe
    hereinkommt statt als Rohwert.
    """
    return ForecastDataPoint(
        ts=datetime(2026, 8, 6, h, 0, tzinfo=timezone.utc), t2m_c=20.0,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
        hail_flag=hail, thunder_level=code,
    )


def _ort(name: str, lat: float, lon: float, punkte: list, *,
         modell: str = "icon_d2", **felder) -> LocationResult:
    """Ort, dessen Stunden durch die ECHTE Fusion gelaufen sind: Gebiet aus
    ``thunder_routing``, Schwellenleitern aus ``model_registry`` -- keine im
    Test getippte Schwelle (sonst prueft er eine Welt, die es nicht gibt)."""
    region = thunder_region_for(lat, lon)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(modell, region), lpi_thresholds_jkg(region),
    )
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=lat, lon=lon,
                               elevation_m=1000),
        score=50, hourly_data=punkte, **felder,
    )


def _vergleich(*orte: LocationResult) -> ComparisonResult:
    return ComparisonResult(
        locations=list(orte), time_window=(12, 20),
        target_date=date(2026, 8, 6), created_at=datetime(2026, 8, 5, 18, 0),
    )


def _mail(*orte: LocationResult, stunden=False) -> tuple[str, str]:
    """(html_body, text_body) des Ortsvergleichs mit NUR der Gewitter-Zeile."""
    return render_compare_email(
        _vergleich(*orte), enabled_metrics=["thunder_max"],
        hourly_metrics=["thunder_level"] if stunden else None,
        hourly_enabled=stunden,
    )


def _html_zellen(html: str) -> list[str]:
    """Zellentexte der Gewitter-Zeile der HTML-Uebersicht, in Ortsreihenfolge
    (alphabetisch, ``location_render_order``)."""
    rest = html.split(">Gewitter</td>", 1)[1]
    return [_html.unescape(c) for c in _TD.findall(rest.split("</tr>", 1)[0])]


def _text_zellen(text: str, trenner: str = "Gewitter: ") -> list[str]:
    """Gewitter-Zellen der Klartext-/Telegram-Uebersicht, in Ortsreihenfolge."""
    return [ln.split(trenner, 1)[1].strip() for ln in text.splitlines() if trenner in ln]


def _teile(zelle: str) -> tuple[str, set[str]]:
    """"hoch · CAPE, Blitzpotenzial" -> ("hoch", {"CAPE", "Blitzpotenzial"})."""
    stufe, _, rest = zelle.partition(" · ")
    return stufe, {t.strip() for t in rest.split(",") if t.strip()}


def _alpen_und_korsika() -> tuple[LocationResult, LocationResult]:
    """Zwei Orte auf "hoch" ueber VERSCHIEDENE Zutaten (Spec AC-1).

    Alpenort: CAPE 1500 J/kg bei schwacher Hemmung (CIN 5) -- ueber der
    obersten Sprosse der icon_d2/DE_ALPEN-Leiter. Korsikaort: Blitzdichte
    0,5/km2 ueber der obersten Sprosse ihrer Leiter; FR hat keine
    LPI-Kalibrierung und kein CAPE, dort traegt also nur die Dichte.
    """
    return (
        _ort("Alpenort", 47.0, 12.0, [_dp(14, cape=1500.0, cin=5.0)]),
        _ort("Korsikaort", 42.0, 9.0, [_dp(14, dichte=0.5)], modell="meteofrance_arome"),
    )


def test_ac1_html_uebersicht_nennt_je_ort_die_eigene_tragende_zutat():
    """AC-1: Given zwei Orte erreichen "hoch" ueber verschiedene Zutaten,
    When die Vergleichsmail gerendert wird, Then nennt jede Ortszelle die
    JEWEILS eigene Zutat -- nicht dieselbe Angabe fuer beide."""
    html, text = _mail(*_alpen_und_korsika())
    erwartet = ["hoch · CAPE", "hoch · Blitzdichte"]
    assert _html_zellen(html) == erwartet, (
        f"HTML-Uebersicht muss je Ort die tragende Zutat nennen: {_html_zellen(html)!r}")
    assert _text_zellen(text) == erwartet, (
        f"Klartext-Teil DERSELBEN Mail muss dieselbe Herkunft zeigen: "
        f"{_text_zellen(text)!r}")


def test_ac4_telegram_zeigt_dieselbe_herkunft_wie_die_mail():
    """AC-4: Given derselbe Ortsvergleich geht als Telegram-Nachricht raus,
    When der Nutzer sie liest, Then steht dort dieselbe Herkunfts-Angabe wie
    in der E-Mail (Fliesstext statt Farbzelle, inhaltsgleich)."""
    telegram = render_compare_telegram(
        _vergleich(*_alpen_und_korsika()), enabled_metrics=["thunder_max"])
    assert _text_zellen(telegram, "Gewitter ") == ["hoch · CAPE", "hoch · Blitzdichte"], (
        f"Telegram muss dieselbe Herkunft zeigen wie die Mail: {telegram!r}")


def test_ac5_sms_zeigt_die_stufe_aber_keine_herkunft():
    """AC-5: Given derselbe Ortsvergleich geht als SMS raus, When der Nutzer
    sie liest, Then steht dort die Stufe, aber KEINE der vier Zutaten.

    Gegenprobe im selben Lauf (Spec-Pflicht): Telegram zeigt die Herkunft
    gegen DIESELBE Fixture sehr wohl -- sonst waere dieses AC auch dann
    gruen, wenn die Herkunft nirgends erschiene.
    """
    result = _vergleich(*_alpen_und_korsika())
    sms = render_compare_sms(result, enabled_metrics=["thunder_max"])
    telegram = render_compare_telegram(result, enabled_metrics=["thunder_max"])

    assert "hoch" in sms, f"Die Stufe selbst muss in der SMS stehen: {sms!r}"
    for zutat in ALLE_ZUTATEN:
        assert zutat not in sms, (
            f"SMS ist bewusst OHNE Herkunft (PO-Entscheidung) -- '{zutat}' "
            f"darf nicht vorkommen: {sms!r}")
    assert "CAPE" in telegram and "Blitzdichte" in telegram, (
        f"Gegenprobe gescheitert: Telegram MUSS die Herkunft gegen dieselbe "
        f"Fixture zeigen, sonst beweist die SMS-Abwesenheit nichts: {telegram!r}")


def test_ac2_beide_tragenden_zutaten_werden_genannt():
    """AC-2: Given CAPE UND Blitzpotenzial erreichen an einem Ort dieselbe
    Hoechststufe, When die Gewitter-Zeile gerendert wird, Then werden BEIDE
    kommagetrennt genannt -- es wird kein Gewinner gekuert."""
    html, _ = _mail(_ort("Beideort", 47.0, 12.0,
                         [_dp(14, cape=1500.0, cin=5.0, lpi=60.0)]))
    assert _teile(_html_zellen(html)[0]) == ("hoch", {"CAPE", "Blitzpotenzial"}), (
        f"Beide Traeger der Hoechststufe muessen erscheinen: {_html_zellen(html)[0]!r}")


def test_ac2_eine_schwaechere_zutat_derselben_stunde_wird_nicht_mitgenannt():
    """AC-2/AC-10 (Gegenrichtung): Given DIESELBE Stunde traegt zwei Zutaten
    auf UNTERSCHIEDLICHEN Stufen -- Wettercode nur "leicht", CAPE dagegen
    "hoch" --, When die Gewitter-Zeile gerendert wird, Then wird NUR die
    tragende Zutat genannt.

    "Genannt wird JEDE Zutat, die die HOECHSTSTUFE erreicht" ist die
    Zusicherung; ohne diese Fixture belegt keine Fixture den zweiten Teil des
    Satzes: alle uebrigen tragen entweder genau ein Signal oder zwei Signale
    auf DERSELBEN Hoechststufe. Faellt der Filter in
    ``thunder_signal_carriers()`` weg, wuerde hier zusaetzlich "Wettercode"
    erscheinen und dem Leser eine Zutat als tragend ausweisen, die die Stufe
    gar nicht hergibt.
    """
    html, _ = _mail(_ort("Mischort", 47.0, 12.0,
                         [_dp(14, code=ThunderLevel.LOW, cape=1500.0, cin=5.0)]))
    assert _html_zellen(html)[0] == "hoch · CAPE", (
        f"Nur die Zutat AUF der Hoechststufe darf erscheinen -- der "
        f"Wettercode traegt hier nur 'leicht': {_html_zellen(html)[0]!r}")


def test_ac3_stufe_kein_bekommt_keinen_herkunfts_zusatz():
    """AC-3: Given eine Zutat ist vorhanden, erreicht aber keine Stufe ueber
    NONE, When die Gewitter-Zeile gerendert wird, Then bleibt die Zelle ohne
    Herkunfts-Zusatz -- waehrend der zweite Ort im selben Vergleich (Zutat
    ueber der Leiter) seine Herkunft sehr wohl zeigt."""
    html, _ = _mail(
        _ort("Ruhigort", 47.0, 12.0, [_dp(14, cape=100.0, cin=5.0)]),
        _ort("Sturmort", 47.0, 12.0, [_dp(14, cape=1500.0, cin=5.0)]),
    )
    ruhig_zelle, sturm_zelle = _html_zellen(html)
    assert "·" not in ruhig_zelle, (
        f"Ohne erreichte Stufe darf KEIN Herkunfts-Zusatz erscheinen: {ruhig_zelle!r}")
    assert sturm_zelle == "hoch · CAPE", (
        f"Gegenprobe gescheitert: der Ort MIT erreichter Stufe muss die "
        f"Herkunft zeigen: {sturm_zelle!r}")


def test_ac6_hagel_hinweis_und_herkunft_stehen_nebeneinander():
    """AC-6: Given ein Ort hat bestaetigten Hagel UND eine Gewitter-Herkunft,
    When die E-Mail gerendert wird, Then stehen beide Zusaetze nebeneinander,
    ohne dass einer den anderen verdraengt."""
    html, _ = _mail(_ort("Hagelort", 47.0, 12.0,
                         [_dp(14, cape=1500.0, cin=5.0, hail=True)]))
    assert _html_zellen(html)[0] == "hoch · CAPE · Hagel: ja", (
        f"Herkunft UND Hagel-Hinweis muessen erscheinen (Herkunft vor Hagel, "
        f"Spec D8): {_html_zellen(html)[0]!r}")


def test_ac7_eu_rest_nennt_nur_blitzpotenzial_ohne_eichungshinweis():
    """AC-7: Given ein Ort im Gebiet EU_REST erreicht seine Stufe nur ueber
    das Blitzpotenzial (unbelegte Interim-Schwelle), When die Herkunft
    erscheint, Then steht dort ausschliesslich "Blitzpotenzial" -- kein
    Eichungs-Hinweis, keine Bewertung (ADR-0007/ADR-0048)."""
    # Issue #1678: EU_REST-Hoch-Sprosse jetzt 86,16 J/kg (zuvor 50) -- 90.0
    # statt der frueheren 60.0, damit der Ort weiterhin "hoch" erreicht
    # (dieser Test prueft die Herkunfts-Anzeige, nicht die Leiter selbst).
    html, _ = _mail(_ort("Nordort", 60.0, 25.0, [_dp(14, lpi=90.0)], modell="icon_eu"))
    assert _html_zellen(html)[0] == "hoch · Blitzpotenzial", (
        f"EU_REST-LPI wird genannt wie jede andere Zutat -- ohne Zusatz zur "
        f"Guete der Eichung: {_html_zellen(html)[0]!r}")


def test_ac10_tagesmaximum_vereinigt_die_zutaten_mehrerer_stunden():
    """AC-10: Given zwei Stunden desselben Tages erreichen dieselbe
    Hoechststufe ueber unterschiedliche Zutaten (14 Uhr CAPE, 18 Uhr
    Blitzpotenzial), When die Vergleichsmatrix gerendert wird, Then nennt sie
    BEIDE -- nicht nur die der ersten passenden Stunde."""
    # Issue #1678 geprueft und AUSGESCHLOSSEN: Zweiort (47.0, 12.0) loest zu
    # DE_ALPEN auf (thunder_region_for), dessen Leiter unveraendert 1/30/50
    # ist -- 60.0 J/kg bleibt dort unabhaengig von #1678 HIGH.
    html, _ = _mail(_ort("Zweiort", 47.0, 12.0,
                         [_dp(14, cape=1500.0, cin=5.0), _dp(18, lpi=60.0)]))
    assert _teile(_html_zellen(html)[0]) == ("hoch", {"CAPE", "Blitzpotenzial"}), (
        f"Das Tagesaggregat muss die Traeger ALLER Stunden mit der "
        f"Hoechststufe vereinigen: {_html_zellen(html)[0]!r}")


def test_ac11_trip_stundenzelle_bleibt_ohne_herkunft():
    """AC-11 (Trip-Haelfte, weiterhin gueltig): Given diese Scheibe aendert
    nur die Ortsvergleich-Tagesuebersicht, When die Gewitterzelle der
    TRIP-Stundentabelle gerendert wird, Then bleibt sie zeichengleich -- kein
    Herkunfts-Zusatz auf der Trip-Seite.

    Gegenprobe im selben Lauf: die Ortsvergleich-Uebersicht derselben Fixture
    zeigt die Herkunft sehr wohl -- ohne sie waere die zugesicherte
    ABWESENHEIT auch dann gruen, wenn die Herkunft nirgends erschiene.

    🔴 Die ZWEITE Haelfte dieses AC ist abgeloest (PO-Entscheid 2026-08-13,
    Issue #1680 Scheibe 3). Hier stand bis dahin die Zusicherung, dass keine
    der vier Zutaten im Stundenabschnitt der Vergleichsmail (HTML UND
    Klartext) auftaucht. Die Compare-Stundentabelle zeigt die Herkunft ab
    Scheibe 3 SEHR WOHL; die Zusicherung ist damit veraltetes Verhalten und
    ersatzlos entfallen -- nicht bloss umgedreht, sonst stuende dieselbe
    Aussage doppelt in zwei Dateien. Den neuen Sollzustand bewacht
    ``test_thunder_origin_four_places.py``, dort
    ``test_ac4_stundentabelle_nennt_die_zutat_in_html_und_klartext`` und
    ``test_ac9_jede_stundenzeile_zeigt_nur_die_zutat_ihres_datenpunkts``.
    Die TRIP-Stundentabelle bleibt auch in Scheibe 3 ausdruecklich aussen vor
    (dortige Spec, Abschnitt "Nicht in dieser Scheibe") -- deshalb bleibt
    diese Haelfte stehen.
    """
    from output.renderers.email.helpers import fmt_val

    html, _ = _mail(*_alpen_und_korsika())
    assert _html_zellen(html)[0] == "hoch · CAPE", (
        f"Gegenprobe gescheitert: die Tagesuebersicht MUSS die Herkunft "
        f"zeigen: {_html_zellen(html)[0]!r}")
    assert fmt_val("thunder", ThunderLevel.HIGH, row={"_hail_flag": None}) == "hoch", (
        "Die Gewitterzelle der TRIP-Stundentabelle (email/helpers.fmt_val) "
        "bleibt zeichengleich -- kein Herkunfts-Zusatz auf der Trip-Seite.")


def test_ac12_bei_abweichung_von_engine_wert_und_stunden_keine_herkunft():
    """AC-12: Given die angezeigte Stufe stammt aus dem Engine-Lauf und weicht
    von der aus den Stundenwerten abgeleiteten ab, When die Gewitter-Zeile
    gerendert wird, Then erscheint die Stufe ohne Herkunft -- nie eine
    Herkunft, die zu einer anderen als der gezeigten Stufe gehoert.

    Gegenprobe im selben Test (Spec-Pflicht): stimmen Engine-Wert und
    Stundenwert ueberein, erscheint die Herkunft sehr wohl.
    """
    # CAPE 800 J/kg bei schwacher Hemmung -> MED ueber die icon_d2-Leiter.
    html, _ = _mail(
        _ort("Driftort", 47.0, 12.0, [_dp(14, cape=800.0, cin=5.0)],
             thunder_level_max=ThunderLevel.HIGH),
        _ort("Einigort", 47.0, 12.0, [_dp(14, cape=800.0, cin=5.0)],
             thunder_level_max=ThunderLevel.MED),
    )
    drift_zelle, einig_zelle = _html_zellen(html)
    assert drift_zelle == "hoch", (
        f"Bei Drift zwischen Engine-Stufe und Stundenwerten darf KEINE "
        f"Herkunft erscheinen: {drift_zelle!r}")
    assert einig_zelle == "mittel · CAPE", (
        f"Gegenprobe gescheitert: bei uebereinstimmender Stufe MUSS die "
        f"Herkunft erscheinen: {einig_zelle!r}")
