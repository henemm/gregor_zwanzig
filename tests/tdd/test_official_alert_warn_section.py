"""Amtliche-Warnung-Sektion: Titel, Gueltigkeit, Quelle-Box, Chips, Buendelung.

SPEC: docs/specs/modules/fix_1237_1238_1239_mail_darstellung.md
      (AC-4 bis AC-14, AC-18)
KONTEXT: docs/context/fix-1237-1238-mail-darstellung.md (#1238/#1239)

RED-Phase (Verhaltens-ACs):
- AC-4/AC-6: `_standalone_warn_type_html` KONKATENIERT Typ-Wort + vollen
  Quell-Label ("Zugang gesperrt — Zugang eingeschraenkt — Maures") und laesst
  die numerische Quell-Stufe im Titel stehen ("Waldbrand-Gefahr — Stufe 3"
  neben dem Meter "ORANGE · 2/3").
- AC-7: `_format_validity` liefert "unbekannt" statt die "Gueltig:"-Zeile
  wegzulassen.
- AC-9: `_standalone_src_sentence` verallgemeinert den Scope der FUEHRENDEN
  Warnung ueber alle Warnungen.
- AC-12: `build_compare_official_alert_notices` fuellt `free_chips` mit allen
  nicht betroffenen Orten (durchgestrichene Chips + "uebrige Strecke frei"-Satz)
  und der Renderer beschriftet das Feld mit "Route:".
- AC-13: `dedupe_official_alerts` trennt gleichartige Warnungen (gleicher Typ,
  gleiche Stufe) nach Zone/Region.
- AC-18: Stufenwort ("ORANGE") kann in der schmalen Titel-Spalte umbrechen.

Non-Regression (JETZT SCHON GRUEN, muss gruen bleiben): AC-5, AC-8, AC-10,
AC-11, AC-14.

Mock-frei: echte `OfficialAlert`/`OfficialAlertNotice`-DTOs, echte Renderer
(`render_warn_block`) und echte Aufbau-Helfer (`build_official_alert_notices`,
`build_compare_official_alert_notices`, `dedupe_official_alerts`). Auswertung am
gerenderten HTML per BeautifulSoup, kein Dateiinhalt-Check am Quellcode.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_FROM = datetime(2026, 7, 10, 6, 0, tzinfo=UTC)
FR_TO = datetime(2026, 7, 10, 20, 0, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)


def _alert(level, hazard, label, vf=FR_FROM, vt=FR_TO, *, region="Var", source="geosphere_warn",
           dedup_id=None) -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, dedup_id=dedup_id,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


def _render_standalone(notices, **overrides) -> str:
    from output.renderers.alert.official_alerts import render_warn_block
    kwargs = dict(
        variant="standalone", source_label="Präfektur (Zugangssperre)",
        stand_at="09:30", tz=UTC,
    )
    kwargs.update(overrides)
    return render_warn_block(notices, **kwargs)


def _render_embedded(notices, **overrides) -> str:
    from output.renderers.alert.official_alerts import render_warn_block
    kwargs = dict(
        variant="embedded", source_label="Präfektur (Zugangssperre)", tz=UTC,
    )
    kwargs.update(overrides)
    return render_warn_block(notices, **kwargs)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _warn_rows(html: str) -> list:
    """Alle Warn-Zeilen (`.warn` bzw. `.warn.stacked`) des Standalone-Blocks."""
    return _soup(html).select("div.warn")


def _type_texts(html: str) -> list[str]:
    return [el.get_text(" ", strip=True) for el in _soup(html).select("div.warn .type")]


def _src_text(html: str) -> str:
    box = _soup(html).select_one("div.src")
    assert box is not None, "Quelle-Box (.src) fehlt im Standalone-Alert"
    return box.get_text(" ", strip=True)


def _text(html: str) -> str:
    return _soup(html).get_text(" ", strip=True)


def _massif_notice(label="Zugang eingeschränkt — Maures", level=3, **kw):
    return _notice(
        _alert(level, "access_ban", label, source="massif_closure", region="Maures", **kw),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )


# ---------------------------------------------------------------------------
# AC-4 — reicherer Quell-Label ERSETZT das Typ-Wort (statt Konkatenation)
# ---------------------------------------------------------------------------

def test_ac4_richer_label_replaces_generic_hazard_word():
    """AC-4: Given eine amtliche Warnung mit einem reicheren Quell-Label (z. B.
    eine Zugangssperre mit Massiv-Namen) / When der Warn-Titel im Standalone-
    Alarm gerendert wird / Then erscheint der Gefahren-Typ genau einmal — der
    reichere Label ersetzt das allgemeine Typ-Wort, statt es zu wiederholen."""
    html = _render_standalone([_massif_notice()])
    titles = _type_texts(html)
    assert titles, "Keine Warn-Titel (.type) gerendert"
    title = titles[0]
    assert title == "Zugang eingeschränkt — Maures", (
        f"Titel wiederholt das generische Typ-Wort: {title!r} "
        "(erwartet: nur der reichere Quell-Label)"
    )
    assert "Zugang gesperrt" not in title, f"Doppeltes Typ-/Stufenwort im Titel: {title!r}"


# ---------------------------------------------------------------------------
# AC-5 — Non-Regression: Standard-Warnung ohne Zusatz-Label
# ---------------------------------------------------------------------------

def test_ac5_plain_hazard_title_unchanged():
    """AC-5 (Non-Regression, JETZT SCHON GRUEN): Given eine Standard-Warnung ohne
    zusaetzlichen Quell-Label (Hitze/Gewitter direkt aus der Wettervorhersage) /
    When der Warn-Titel gerendert wird / Then bleibt der Titeltext bit-identisch
    zum Stand vor diesem Fix."""
    hitze = _notice(
        _alert(3, "extreme_heat", "Hitze"),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    gewitter = _notice(
        _alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    titles = _type_texts(_render_standalone([hitze, gewitter]))
    assert titles == ["Hitze", "Gewitter"], f"Standard-Titel veraendert: {titles!r}"


# ---------------------------------------------------------------------------
# AC-6 — keine numerische Quell-Stufe mehr im Titel, wenn das Meter sie zeigt
# ---------------------------------------------------------------------------

def test_ac6_title_drops_numeric_source_level_next_to_meter():
    """AC-6: Given eine Warnung, deren Eskalationsstufe bereits als Eskalations-
    Meter/Stufenwort in derselben Zeile angezeigt wird / When der Warn-Titel
    gerendert wird / Then nennt der Titel den Gefahren-Typ, aber keine
    zusaetzliche numerische Quell-Stufe mehr ('Waldbrand-Gefahr — Stufe 3'
    neben 'ORANGE · 2/3')."""
    brand = _notice(
        _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3", source="meteo_forets",
               region="Zone Ouest"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    hitze = _notice(  # zweite Stufe -> gemischt -> stacked-Pfad mit Meter
        _alert(4, "extreme_heat", "Hitze"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    html = _render_standalone([brand, hitze])
    brand_titles = [t for t in _type_texts(html) if "Waldbrand" in t]
    assert brand_titles, f"Waldbrand-Titel nicht gefunden: {_type_texts(html)!r}"
    title = brand_titles[0]
    assert not re.search(r"Stufe\s*\d", title), (
        f"Titel nennt die numerische Quell-Stufe zusaetzlich zum Meter: {title!r}"
    )
    assert "ORANGE · 2/3" in _text(html), "Eskalations-Meter fehlt (Stufe muss dort stehen)"


# ---------------------------------------------------------------------------
# AC-7 — keine "Gültig:"-Zeile ohne bekannten Gueltigkeitszeitraum
# ---------------------------------------------------------------------------

def test_ac7_no_validity_line_when_times_missing_standalone():
    """AC-7 (Standalone): Given eine amtliche Warnung ohne bekannten
    Gueltigkeitszeitraum (tagesbezogene Zugangssperre) / When die Warn-Sektion
    gerendert wird / Then erscheint fuer diese Warnung keine 'Gueltig:'-Zeile
    mehr."""
    html = _render_standalone([_massif_notice(vf=None, vt=None)])
    text = _text(html)
    assert "Gültig:" not in text, f"'Gültig:'-Zeile trotz fehlender Zeiten: {text!r}"
    assert "unbekannt" not in text, f"Platzhalter 'unbekannt' im Output: {text!r}"


def test_ac7_no_validity_line_when_times_missing_embedded():
    """AC-7 (embedded): Given dieselbe Warnung ohne Zeiten / When der embedded
    WarnBlock (Trip-Briefing / Ortsvergleich-Banner) gerendert wird / Then
    erscheint fuer diese Warnung kein Gueltigkeits-Platzhalter."""
    text = _text(_render_embedded([_massif_notice(vf=None, vt=None)]))
    assert "unbekannt" not in text, f"Platzhalter 'unbekannt' im embedded WarnBlock: {text!r}"


def test_ac7_no_validity_line_when_times_missing_plain():
    """AC-7 (Nachzug, Klartext-Pfad): Given dieselbe Warnung ohne Zeiten / When
    `render_official_alert_notice_plain` (der Klartext-Teil der multipart-Mail)
    rendert / Then erscheint keine 'Gültig:'-Zeile und kein Platzhalter
    'unbekannt' -- AC-7 gilt fuer die ganze Mail, nicht nur den HTML-Teil
    (manche Clients zeigen den Klartext-Teil an, und er speist die eigenen
    Pruef-Werkzeuge)."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    sperre = _alert(4, "access_ban", "Zugang gesperrt — Maures", vf=None, vt=None,
                     source="massif_closure", region="Maures", dedup_id="maures")
    lines = render_official_alert_notice_plain([(sperre, [])], tz=UTC)
    text = "\n".join(lines)
    assert "Gültig:" not in text, f"'Gültig:'-Zeile trotz fehlender Zeiten (Klartext): {text!r}"
    assert "unbekannt" not in text, f"Platzhalter 'unbekannt' im Klartext-Output: {text!r}"


def test_ac8_validity_line_kept_when_times_known_plain():
    """AC-8 (Nachzug, Klartext-Pfad, Non-Regression): Given dieselbe Warnung MIT
    bekanntem Zeitraum / When der Klartext-Renderer laeuft / Then bleibt die
    'Gültig:'-Zeile mit dem formatierten Zeitraum unveraendert."""
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    sperre = _alert(4, "access_ban", "Zugang gesperrt — Maures",
                     source="massif_closure", region="Maures", dedup_id="maures")
    lines = render_official_alert_notice_plain([(sperre, [])], tz=UTC)
    text = "\n".join(lines)
    # Bestands-Format nutzt strftime("%a") -- locale-abhaengiges Wochentags-
    # Kuerzel (nicht Teil dieses Fixes); geprueft wird Datum/Uhrzeit-Kern.
    assert re.search(r"Gültig: \w+ 10\.07\. 06:00 – \w+ 10\.07\. 20:00", text), (
        f"Gueltigkeits-Zeile mit bekannten Zeiten fehlt oder Format veraendert: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Non-Regression: bekannte Zeiten -> "Gültig:"-Zeile bleibt
# ---------------------------------------------------------------------------

def test_ac8_validity_line_kept_when_times_known():
    """AC-8 (Non-Regression, JETZT SCHON GRUEN): Given eine amtliche Warnung mit
    bekanntem Gueltigkeitszeitraum / When die Warn-Sektion gerendert wird / Then
    erscheint die 'Gueltig:'-Zeile weiterhin mit dem formatierten Zeitraum."""
    text = _text(_render_standalone([_massif_notice()]))
    assert "Gültig:" in text, "Gueltigkeits-Zeile fehlt trotz bekannter Zeiten"
    assert "Fr 10.07. · 06:00–20:00" in text, f"Gueltigkeits-Format veraendert: {text!r}"


# ---------------------------------------------------------------------------
# AC-9 — Quelle-Box verallgemeinert nicht mehr den Scope der ersten Warnung
# ---------------------------------------------------------------------------

def test_ac9_source_box_does_not_generalize_leading_scope():
    """AC-9: Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem
    Umfang / When die Quelle-Box gerendert wird / Then verallgemeinert ihr Satz
    nicht mehr den Umfang der ersten Warnung, sondern verweist neutral auf die
    Einzelangaben der Warnungen oben."""
    a = _notice(
        _alert(3, "extreme_heat", "Hitze"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    b = _notice(
        _alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="nur Hyères", sms_scope="nurHyeres",
        affected_chips=["Hyères"], free_chips=[],
    )
    src = _src_text(_render_standalone([a, b]))
    assert "Betrifft nur" not in src, (
        f"Quelle-Box verallgemeinert weiter den Scope der ersten Warnung: {src!r}"
    )
    assert "Toulon" not in src and "Hyères" not in src, (
        f"Quelle-Box gibt den Umfang einer einzelnen Warnung als Gesamtaussage aus: {src!r}"
    )
    assert "Quelle:" in src, "Quelle-Box hat ihre Quellen-Angabe verloren"


# ---------------------------------------------------------------------------
# AC-10 — Non-Regression: uniformer Scope -> Satz bleibt
# ---------------------------------------------------------------------------

def test_ac10_source_box_sentence_unchanged_for_uniform_scope():
    """AC-10 (Non-Regression, JETZT SCHON GRUEN): Given mehrere amtliche Warnungen,
    die alle denselben betroffenen Umfang haben / When die Quelle-Box gerendert
    wird / Then bleibt ihr zusammenfassender Satz wie vor diesem Fix."""
    a = _notice(
        _alert(3, "extreme_heat", "Hitze"),
        scope_label="alle Orte", sms_scope="alleOrte",
        affected_chips=["alle Orte"], free_chips=[],
    )
    b = _notice(
        _alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="alle Orte", sms_scope="alleOrte",
        affected_chips=["alle Orte"], free_chips=[],
    )
    src = _src_text(_render_standalone([a, b]))
    assert "Alle Warnungen decken die alle Orte ab." in src, (
        f"Scope-Satz bei uniformem Umfang veraendert: {src!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — Non-Regression: Trip-Pfad behaelt Segment-Chips + Hinweistext
# ---------------------------------------------------------------------------

def _trip_notices():
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import build_official_alert_notices

    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[
            Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0),
            Waypoint(id="w2", name="Huette", lat=47.1, lon=11.1, elevation_m=1400.0),
            Waypoint(id="w3", name="Pass", lat=47.2, lon=11.2, elevation_m=1800.0),
            Waypoint(id="w4", name="Ziel", lat=47.3, lon=11.3, elevation_m=1200.0),
        ],
    )
    trip = Trip(id="tdd-1238-trip", name="KHW 403", stages=[stage])
    tagged = [(_alert(3, "extreme_heat", "Hitze"), ["2"])]
    return build_official_alert_notices(trip, tagged)


def test_ac11_trip_path_keeps_segment_chips_and_route_note():
    """AC-11 (Non-Regression, JETZT SCHON GRUEN): Given eine Trip-Standalone-
    Alarmmail mit Warnungen, die nur einen Teil der Route betreffen / When die
    Warn-Sektion gerendert wird / Then zeigt sie weiterhin Segment-Chips inkl.
    durchgestrichener freier Segmente und den erklaerenden Hinweistext,
    unveraendert."""
    notices = _trip_notices()
    assert notices[0].affected_chips == ["Segment 2"], (
        f"Trip-Segment-Chips veraendert: {notices[0].affected_chips!r}"
    )
    assert notices[0].free_chips == ["Segment 1", "Segment 3", "🏁 Ziel"], (
        f"Freie Trip-Segment-Chips veraendert: {notices[0].free_chips!r}"
    )
    html = _render_standalone(notices)
    soup = _soup(html)
    struck = [c for c in soup.select("span.seg") if "line-through" in (c.get("style") or "")]
    assert struck, "Durchgestrichene freie Segment-Chips fehlen im Trip-Pfad"
    assert soup.select_one("div.route-note") is not None, "route-note fehlt im Trip-Pfad"
    assert "übrige Strecke frei" in _text(html), "Hinweistext im Trip-Pfad veraendert"
    assert "Route:" in _text(html), "Trip-Feldlabel 'Route:' veraendert"


# ---------------------------------------------------------------------------
# AC-12 — Compare-Pfad: nur betroffene Orts-Chips, Label "Orte:"
# ---------------------------------------------------------------------------

def _compare_notices(tagged):
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices

    all_ids = ["toulon", "hyeres", "frejus", "marseille"]
    id_to_name = {
        "toulon": "Toulon", "hyeres": "Hyères",
        "frejus": "Fréjus", "marseille": "Marseille",
    }
    return build_compare_official_alert_notices(all_ids, id_to_name, tagged)


def test_ac12_compare_path_shows_only_affected_location_chips():
    """AC-12: Given eine Ortsvergleich-Standalone-Alarmmail mit Warnungen, die
    nur einen Teil der verglichenen Orte betreffen / When die Warn-Sektion
    gerendert wird / Then zeigt sie ausschliesslich die betroffenen Orte als
    Chips ohne durchgestrichene freie Orte und ohne den 'uebrige Strecke frei'-
    Hinweistext, und das Feld heisst 'Orte:' statt 'Route:'."""
    notices = _compare_notices([(_alert(3, "extreme_heat", "Hitze"), ["toulon", "hyeres"])])
    assert len(notices) == 1
    assert notices[0].affected_chips == ["Toulon", "Hyères"]
    assert notices[0].free_chips == [], (
        f"Compare-Notice fuehrt weiter freie Orts-Chips: {notices[0].free_chips!r}"
    )

    html = _render_standalone(notices)
    soup = _soup(html)
    chips = soup.select("div.warn span.seg")
    assert [c.get_text(strip=True) for c in chips] == ["Toulon", "Hyères"], (
        f"Compare-Chips zeigen nicht nur die betroffenen Orte: "
        f"{[c.get_text(strip=True) for c in chips]!r}"
    )
    struck = [c for c in chips if "line-through" in (c.get("style") or "")]
    assert not struck, "Durchgestrichene freie Orts-Chips im Compare-Pfad"
    assert soup.select_one("div.route-note") is None, "route-note im Compare-Pfad"
    text = _text(html)
    assert "übrige Strecke frei" not in text, "Hinweistext 'übrige Strecke frei' im Compare-Pfad"
    assert "Orte:" in text, f"Compare-Feldlabel 'Orte:' fehlt: {text!r}"
    assert "Route:" not in text, f"Compare-Feldlabel heisst weiter 'Route:': {text!r}"


# ---------------------------------------------------------------------------
# AC-13 — Buendelung gleichartiger Warnungen (gleicher Typ, gleiche Stufe)
# ---------------------------------------------------------------------------

def test_ac13_same_hazard_same_level_bundled_into_one_warning():
    """AC-13: Given zwei amtliche Warnungen mit demselben Gefahren-Typ und
    derselben Stufe, aber unterschiedlichen betroffenen Zonen oder Orten / When
    die Warn-Sektion gerendert wird / Then erscheinen sie als eine einzige
    Warnung mit einer vereinigten Orts-/Segmentliste statt als zwei getrennte
    Warnungen."""
    west = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                  source="meteo_forets", region="Zone Ouest")
    est = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                 source="meteo_forets", region="Zone Est")
    notices = _compare_notices([(west, ["toulon"]), (est, ["frejus"])])
    assert len(notices) == 1, (
        f"Gleichartige Warnungen (Typ + Stufe) nicht gebuendelt: {len(notices)} Eintraege"
    )
    assert notices[0].affected_chips == ["Toulon", "Fréjus"], (
        f"Orts-Liste nicht vereinigt: {notices[0].affected_chips!r}"
    )
    html = _render_standalone(notices)
    assert len(_warn_rows(html)) == 1, "Zwei Warn-Zeilen statt einer gebuendelten"


def test_ac13_different_validity_periods_not_bundled():
    """AC-13 (Adversary F003, HIGH, Datenverlust): Given zwei amtliche Warnungen
    mit demselben Gefahren-Typ, derselben Stufe, aber VERSCHIEDENEN
    Gueltigkeitszeitraeumen / When die Warn-Sektion gerendert wird / Then
    buendeln sie NICHT zu einer Warnung -- fachlich sind es zwei verschiedene
    Warnungen, und beide Zeitraeume muessen sichtbar bleiben. Vorher warf die
    Buendelung stillschweigend den Zeitraum der nicht-repraesentativen Warnung
    weg (falsche Aussage in einer Sicherheitswarnung)."""
    west = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                  vf=FR_FROM, vt=FR_TO, source="meteo_forets", region="Zone Ouest")
    est = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                 vf=SA_FROM, vt=SA_TO, source="meteo_forets", region="Zone Est")
    notices = _compare_notices([(west, ["toulon"]), (est, ["frejus"])])
    assert len(notices) == 2, (
        f"Warnungen mit unterschiedlichen Zeitraeumen faelschlich gebuendelt: "
        f"{len(notices)} Eintraege"
    )
    html = _render_standalone(notices)
    assert len(_warn_rows(html)) == 2, "Zwei Warn-Zeilen erwartet (Zeitraeume unterschiedlich)"
    text = _text(html)
    assert "Fr 10.07. · 06:00–20:00" in text, "Zeitraum der ersten Warnung (Toulon) fehlt"
    assert "Sa 11.07. · 15:00–21:00" in text, "Zeitraum der zweiten Warnung (Fréjus) fehlt"


def test_ac13_different_massif_labels_not_bundled():
    """AC-13 (Adversary F012, HIGH, Staging-Regression): Given drei amtliche
    Zugangssperren-Warnungen mit demselben Gefahren-Typ, derselben Stufe und
    OHNE Gueltigkeitszeitraum (wie die F003-Buendelungsbedingung es erlaubt),
    aber DREI VERSCHIEDENEN Massiv-Bezeichnungen ("Monts Toulonnais",
    "Corniche Des Maures", "Centre Var") / When die Warn-Sektion gerendert
    wird / Then buendeln sie NICHT zu einer Warnung -- jede behaelt ihren
    eigenen Massiv-Namen und ihre eigenen Orte.

    Reproduziert die echte Staging-Regression: vorher zeigte die gebuendelte
    Karte nur "Zugang eingeschränkt — Monts Toulonnais" (das Label des ERSTEN
    Massivs) fuer alle drei Orte -- wer in Hyères stand, laes eine Sperre fuer
    ein falsches Massiv und erfuhr nichts von der ihn tatsaechlich
    betreffenden Corniche-des-Maures-Sperre."""
    toulonnais = _alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                        vf=None, vt=None, source="massif_closure",
                        region="Monts Toulonnais", dedup_id="monts-toulonnais")
    maures = _alert(3, "access_ban", "Zugang eingeschränkt — Corniche Des Maures",
                     vf=None, vt=None, source="massif_closure",
                     region="Corniche Des Maures", dedup_id="corniche-maures")
    centre_var = _alert(3, "access_ban", "Zugang eingeschränkt — Centre Var",
                         vf=None, vt=None, source="massif_closure",
                         region="Centre Var", dedup_id="centre-var")
    notices = _compare_notices([
        (toulonnais, ["toulon"]), (maures, ["hyeres"]), (centre_var, ["frejus"]),
    ])
    assert len(notices) == 3, (
        f"Verschiedene Massiv-Sperren faelschlich gebuendelt: {len(notices)} Eintraege "
        f"(Labels: {[n.alert.label for n in notices]!r})"
    )
    html = _render_standalone(notices)
    assert len(_warn_rows(html)) == 3, "Drei Warn-Zeilen erwartet (drei verschiedene Massive)"
    titles = _type_texts(html)
    assert titles == [
        "Zugang eingeschränkt — Monts Toulonnais",
        "Zugang eingeschränkt — Corniche Des Maures",
        "Zugang eingeschränkt — Centre Var",
    ], f"Massiv-Titel vermischt/verloren: {titles!r}"
    text = _text(html)
    assert "Hyères" in text and "Fréjus" in text and "Toulon" in text, (
        f"Nicht alle drei Orte erscheinen als eigene Chips: {text!r}"
    )


def test_ac13_same_label_wildfire_still_bundled_across_zones():
    """AC-13 (Non-Regression fuer den urspruenglichen #1239-Fall, nach dem
    F012-Fix): Given zwei Waldbrand-Warnungen mit IDENTISCHEM Label
    ("Waldbrand-Gefahr — Stufe 3") aus zwei verschiedenen Zonen / When die
    Warn-Sektion gerendert wird / Then buendeln sie WEITERHIN zu einer
    Warnung -- das Label-Kriterium aus F012 verhindert nur die Buendelung
    fachlich VERSCHIEDENER Warnungen (F012), nicht den urspruenglichen
    AC-13-Bündelungsfall (identisches Label, unterschiedliche Zonen)."""
    west = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                  vf=None, vt=None, source="meteo_forets", region="Zone Ouest")
    est = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                 vf=None, vt=None, source="meteo_forets", region="Zone Est")
    notices = _compare_notices([(west, ["toulon"]), (est, ["frejus"])])
    assert len(notices) == 1, (
        f"Identisches Label aus zwei Zonen nicht mehr gebuendelt: {len(notices)} Eintraege"
    )
    assert notices[0].affected_chips == ["Toulon", "Fréjus"], (
        f"Orts-Liste nicht vereinigt: {notices[0].affected_chips!r}"
    )
    html = _render_standalone(notices)
    assert len(_warn_rows(html)) == 1, "Eine Warn-Zeile erwartet (identisches Label)"


def test_ac13_bundled_warning_names_all_member_regions_in_source_box():
    """AC-13 (Adversary F013, HIGH, Staging-Regression Runde 7): Given zwei
    Waldbrand-Warnungen mit identischem Label und identischer Stufe, aber
    VERSCHIEDENEN Départements ("Var"/"Bouches-du-Rhône"), ohne dedup_id / When
    die Warn-Sektion gerendert wird / Then buendeln sie korrekt zu EINER
    Warnung mit Chips fuer BEIDE Orte -- aber die Quelle-Box nennt NICHT nur
    die Region des Buendel-Repraesentanten, sondern ALLE Regionen des Buendels.

    Vorher: 'Quelle: Météo-France — Var.' fuer eine Warnung, die tatsaechlich
    Var UND Bouches-du-Rhône abdeckt -- eine falsche Zustaendigkeits-Zuordnung
    fuer Marseille (Bouches-du-Rhône), keine blosse Auslassung."""
    var = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                 vf=None, vt=None, source="meteo_forets", region="Var")
    bdr = _alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                  vf=None, vt=None, source="meteo_forets", region="Bouches-du-Rhône")
    notices = _compare_notices([(var, ["toulon"]), (bdr, ["marseille"])])
    assert len(notices) == 1, f"Faelschlich nicht gebuendelt: {len(notices)} Eintraege"
    assert notices[0].affected_chips == ["Toulon", "Marseille"], (
        f"Orts-Liste nicht vereinigt: {notices[0].affected_chips!r}"
    )
    html = _render_standalone(notices)
    assert len(_warn_rows(html)) == 1, "Eine Warn-Zeile erwartet (gebuendelt)"
    src = _src_text(html)
    assert "Var" in src and "Bouches-du-Rhône" in src, (
        f"Quelle-Box nennt nicht beide Regionen des Buendels: {src!r}"
    )


def test_ac13_single_region_source_box_unchanged():
    """AC-13 (Non-Regression, F013-Gegenstueck): Given eine einzelne
    ungebuendelte Warnung mit genau EINER Region / When die Warn-Sektion
    gerendert wird / Then bleibt die Quelle-Box-Regionsangabe wortgleich zum
    Stand vor dem F013-Fix (keine Aenderung fuer den unproblematischen Fall)."""
    notice = _notice(
        _alert(3, "extreme_heat", "Hitze", region="Var"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    src = _src_text(_render_standalone([notice]))
    assert "Var" in src, f"Region fehlt in der Quelle-Box: {src!r}"
    assert src.count("Var") == 1, f"Region wird unerwartet vervielfacht: {src!r}"


# ---------------------------------------------------------------------------
# AC-14 — Non-Regression: Massiv-Eskalation kollabiert auf hoechste Stufe
# ---------------------------------------------------------------------------

def test_ac14_massif_escalation_still_collapses_to_highest_level():
    """AC-14 (Non-Regression, JETZT SCHON GRUEN): Given eine Massiv-Zugangssperre,
    die von Stufe 3 auf Stufe 4 eskaliert (stabile Massiv-Kennung) / When die
    Warn-Sektion gerendert wird / Then bleibt sie eine Warnung mit der hoechsten
    Stufe."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    lvl3 = _alert(3, "access_ban", "Zugang eingeschränkt — Maures",
                  source="massif_closure", region="Maures", dedup_id="maures")
    lvl4 = _alert(4, "access_ban", "Zugang gesperrt — Maures",
                  source="massif_closure", region="Maures", dedup_id="maures")
    deduped = dedupe_official_alerts([(lvl3, ["toulon"]), (lvl4, ["toulon"])])
    assert len(deduped) == 1, f"Massiv-Eskalation nicht kollabiert: {len(deduped)} Warnungen"
    assert deduped[0][0].level == 4, f"Nicht die hoechste Stufe behalten: {deduped[0][0].level}"

    notices = _compare_notices([(lvl3, ["toulon"]), (lvl4, ["toulon"])])
    assert len(notices) == 1
    assert len(_warn_rows(_render_standalone(notices))) == 1


# ---------------------------------------------------------------------------
# AC-18 — Stufenwort bricht nicht mitten im Wort um
# ---------------------------------------------------------------------------

def _first_track_px(style: str) -> int | None:
    m = re.search(r"grid-template-columns:\s*(\d+)px", style or "")
    return int(m.group(1)) if m else None


def test_ac18_level_word_does_not_break_mid_word():
    """AC-18: Given eine Warnstufe mit einem langen Stufenwort ('ORANGE') / When
    der Warn-Titel-Bereich gerendert wird / Then bricht das Stufenwort nicht
    mitten im Wort um.

    Strukturelle Pruefung ohne Pixel-Fixierung: entweder traegt das Element mit
    dem Stufenwort einen Umbruch-Schutz (`white-space:nowrap`/`nobr`), oder die
    Titel-Spalte ist nicht mehr auf die zu schmale Bestands-Breite (130px)
    festgenagelt."""
    brand = _notice(
        _alert(3, "wildfire_risk", "Waldbrand-Gefahr", source="meteo_forets", region="Zone Ouest"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    hitze = _notice(
        _alert(4, "extreme_heat", "Hitze"),
        scope_label="nur Toulon", sms_scope="nurToulon",
        affected_chips=["Toulon"], free_chips=[],
    )
    for notices in ([brand, hitze], [brand]):  # stacked (Meter) UND Grid-Zeile
        html = _render_standalone(notices)
        soup = _soup(html)
        carriers = [
            el for el in soup.find_all(True)
            if "ORANGE" in el.get_text() and len(el.get_text(strip=True)) <= 30
        ]
        nowrap = any(
            "nowrap" in (el.get("style") or "") or "nowrap" in (el.parent.get("style") or "")
            for el in carriers if el.parent is not None
        )
        tracks = [_first_track_px(row.get("style") or "") for row in soup.select("div.warn")]
        widened = all(t is None or t >= 150 for t in tracks)
        assert nowrap or widened, (
            "Stufenwort 'ORANGE' ohne Umbruch-Schutz in einer 130px-Spalte "
            f"(nowrap={nowrap}, Spalten-Tracks={tracks!r})"
        )


# ---------------------------------------------------------------------------
# F004 (Adversary, HIGH, #1239 Nachzug Runde 2) — Compare-Aggregat-Banner
# zeigt die numerische Quell-Stufe nicht mehr doppelt neben dem Stufenwort.
# Reproduktion aus Nutzersicht am echten Ortsvergleich-Mail-Output (nicht am
# privaten Helfer): `render_compare_html()` mit einer Waldbrand-Warnung.
# ---------------------------------------------------------------------------

def test_f004_compare_aggregate_banner_no_duplicate_level_in_type():
    """AC-6 (vierter Anzeige-Ort, Adversary F004): Given eine Ortsvergleich-Mail
    mit genau einer Waldbrand-Gefahrenstufe-Warnung (Quelle meteo_forets,
    Label "Waldbrand-Gefahr — Stufe N") / When der Compare-Aggregat-Banner
    (`_render_warn_banner`, embedded WarnBlock mit `count_line`) gerendert
    wird / Then zeigt der Typ-Text (`.wb-type`) nur "Waldbrand-Gefahr", nicht
    zusaetzlich die numerische Quell-Stufe -- die Stufe steht bereits im
    Banner-Kopf ("höchste Stufe {WORT}").

    Root Cause (Adversary-Befund): "wildfire_risk" fehlte in `_HAZARD_DISPLAY`,
    wodurch `_hazard_display` auf den rohen Quell-Label inkl. "— Stufe N"
    zurueckfiel -- unabhaengig davon, ob die Anzeige-Stelle `_display_label`
    oder das kurze Typ-Wort nutzte. Der Fix sitzt daher im Hazard-Mapping,
    nicht an dieser (oder einer vierten) Anzeige-Stelle."""
    from datetime import date, datetime as _dt

    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.email.compare_html import render_compare_html

    brand = OfficialAlert(
        source="meteo_forets", hazard="wildfire_risk", level=3,
        label="Waldbrand-Gefahr — Stufe 3", region_label="Zone Est",
        dedup_id="zoneE",
    )
    toulon = LocationResult(
        location=SavedLocation(id="toulon", name="Toulon", lat=43.1, lon=5.9, elevation_m=20),
        score=70, temp_max=31.0, wind_max=18.0, sunny_hours=7.0, cloud_avg=30,
        official_alerts=[brand], hourly_data=[],
    )
    marseille = LocationResult(
        location=SavedLocation(id="marseille", name="Marseille", lat=43.3, lon=5.4, elevation_m=5),
        score=65, temp_max=29.0, wind_max=22.0, sunny_hours=6.0, cloud_avg=40,
        official_alerts=[], hourly_data=[],
    )
    result = ComparisonResult(
        locations=[toulon, marseille], time_window=(7, 16),
        target_date=date(2026, 7, 14), created_at=_dt(2026, 7, 13, 4, 1),
    )
    html = render_compare_html(result)
    soup = BeautifulSoup(html, "html.parser")

    type_texts = [el.get_text(strip=True) for el in soup.select(".wb-type")]
    assert type_texts, ".wb-type fehlt im Aggregat-Banner"
    assert type_texts[0] == "Waldbrand-Gefahr", (
        f"Aggregat-Banner zeigt die Stufe doppelt im Typ-Text: {type_texts[0]!r}"
    )
    assert not any("Stufe" in t for t in type_texts), (
        f"Numerische Quell-Stufe im Typ-Text: {type_texts!r}"
    )
