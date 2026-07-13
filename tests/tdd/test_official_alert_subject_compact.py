"""Amtliche-Warnung-Mail: kompakter Betreff + kompakte Ueberschrift (Ortsvergleich).

SPEC: docs/specs/modules/fix_1237_1238_1239_mail_darstellung.md (AC-15, AC-16, AC-17)
KONTEXT: docs/context/fix-1237-1238-mail-darstellung.md (#1239 M6/M7)

RED-Phase:
- AC-15: `render_official_alert_subject` setzt `leading.scope_label` unveraendert
  ein — bei vielen betroffenen Orten ist das die komplette Kommaliste — und
  zaehlt ALLE Warnungen ungedeckelt mit " + " auf.
- AC-17: `_standalone_headline_html` wiederholt dieselbe vollstaendige Ortsliste
  im H1-Satz.

Non-Regression (JETZT SCHON GRUEN): AC-16 (<=2 Orte / <=2 Warnungen,
Sonderfaelle "alle Orte"/"gesamte Route").

Mock-frei: echte `OfficialAlert`-DTOs durch die echten Aufbau-Helfer
(`build_official_alert_notices`, `build_compare_official_alert_notices`) und die
echten Renderer (`render_official_alert_subject`, `render_warn_block`).
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

# Preset "Le Var": acht verglichene Orte.
LOC_IDS = ["toulon", "hyeres", "frejus", "marseille", "draguignan",
           "brignoles", "cassis", "bandol"]
LOC_NAMES = {
    "toulon": "Toulon", "hyeres": "Hyères", "frejus": "Fréjus",
    "marseille": "Marseille", "draguignan": "Draguignan",
    "brignoles": "Brignoles", "cassis": "Cassis", "bandol": "Bandol",
}
AFFECTED_7 = LOC_IDS[:7]  # sieben von acht -> KEIN "alle Orte"-Sonderfall


def _alert(level, hazard, label, vf=FR_FROM, vt=FR_TO, *, region="Var",
           source="geosphere_warn", dedup_id=None) -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, dedup_id=dedup_id,
    )


def _compare_notices(tagged, all_ids=None):
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    return build_compare_official_alert_notices(all_ids or LOC_IDS, LOC_NAMES, tagged)


def _subject(notices, prefix="Le Var") -> str:
    from output.renderers.alert.official_alerts import render_official_alert_subject
    return render_official_alert_subject(notices, prefix=prefix, tz=UTC)


def _headline_text(notices) -> str:
    from output.renderers.alert.official_alerts import render_warn_block
    html = render_warn_block(
        notices, variant="standalone", source_label="Météo-France",
        stand_at="09:30", tz=UTC,
    )
    h1 = BeautifulSoup(html, "html.parser").select_one("div.body-h1")
    assert h1 is not None, "Headline (.body-h1) fehlt im Standalone-Alert"
    return h1.get_text(" ", strip=True)


def _many_warnings_notices():
    """Vier gleichzeitige Warnungen ueber sieben von acht Orten."""
    tagged = [
        (_alert(4, "extreme_heat", "Hitze"), AFFECTED_7),
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO), AFFECTED_7),
        (_alert(3, "wind_gust", "Sturm", SA_FROM, SA_TO, region="Küste"), AFFECTED_7),
        (_alert(2, "rain", "Starkregen", SA_FROM, SA_TO, region="Hinterland"), AFFECTED_7),
    ]
    return _compare_notices(tagged)


# ---------------------------------------------------------------------------
# AC-15 — Betreff: Mengenangabe statt Namensliste, max. zwei Warnungen
# ---------------------------------------------------------------------------

def test_ac15_subject_uses_quantity_and_caps_warnings():
    """AC-15: Given eine Ortsvergleich-Alarmmail mit mehr als zwei betroffenen
    Orten und mehr als zwei gleichzeitigen Warnungen / When der Betreff
    gerendert wird / Then nennt er die Reichweite als Mengenangabe MIT
    Gesamtzahl ("7 von 8 Orten") statt aller Ortsnamen und fuehrt hoechstens
    zwei Warnungen aus, den Rest als '+N weitere'.

    Verschaerft (PO-Nachzug #1239): die Vorschau zeigte explizit die Form MIT
    Gesamtzahl ("[Le Var] 7 von 8 Orten · …") -- "7 von 8" traegt die
    Information "fast alle Orte betroffen", die eine reine Anzahl ("7 Orte")
    nicht hat. Die Erwartung verlangt daher zwingend die "N von M Orten"-Form,
    nicht mehr nur optional."""
    subject = _subject(_many_warnings_notices())

    named = [n for n in (LOC_NAMES[i] for i in AFFECTED_7) if n in subject]
    assert not named, f"Betreff zaehlt Ortsnamen auf ({named!r}): {subject!r}"
    assert re.search(rf"{len(AFFECTED_7)}\s*von\s*{len(LOC_IDS)}\s*Orten", subject), (
        f"Betreff nennt nicht die Mengenangabe 'N von M Orten': {subject!r}"
    )
    assert re.search(r"\+\d+\s*weitere", subject), (
        f"Betreff fasst die uebrigen Warnungen nicht als '+N weitere' zusammen: {subject!r}"
    )
    spelled_out = [t for t in ("Hitze", "Gewitter", "Sturm", "Starkregen") if t in subject]
    assert len(spelled_out) <= 2, (
        f"Mehr als zwei Warnungen ausgeschrieben ({spelled_out!r}): {subject!r}"
    )
    assert "Hitze" in spelled_out, f"Schwerste Warnung fehlt im Betreff: {subject!r}"
    # Vorlagen-Laenge (docs/design-requests/.../Alert Amtliche Warnung.html Z. 167:
    # "[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)" == 56 Zeichen).
    assert len(subject) <= 120, f"Betreff bleibt unlesbar lang ({len(subject)} Zeichen): {subject!r}"


# ---------------------------------------------------------------------------
# AC-16 — Non-Regression: <=2 Orte / <=2 Warnungen, Sonderfaelle unveraendert
# ---------------------------------------------------------------------------

def test_ac16_trip_subject_full_route_unchanged():
    """AC-16 (Non-Regression, JETZT SCHON GRUEN): Given eine Trip-Alarmmail mit
    'gesamte Route' und zwei Warnungen / When der Betreff gerendert wird / Then
    bleibt sein Text bit-identisch zum Stand vor diesem Fix."""
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import build_official_alert_notices

    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[
            Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0),
            Waypoint(id="w2", name="Ziel", lat=47.1, lon=11.1, elevation_m=1200.0),
        ],
    )
    trip = Trip(id="tdd-1239-trip", name="KHW 403", stages=[stage])
    notices = build_official_alert_notices(trip, [
        (_alert(2, "extreme_heat", "Hitze"), ["1", "Ziel"]),
        (_alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO), ["1", "Ziel"]),
    ])
    subject = _subject(notices, prefix="KHW 403")
    assert subject == "[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)", (
        f"Trip-Betreff veraendert: {subject!r}"
    )


def test_ac16_compare_subject_two_locations_unchanged():
    """AC-16 (Non-Regression, JETZT SCHON GRUEN): Given eine Ortsvergleich-
    Alarmmail mit zwei betroffenen Orten und einer Warnung / When der Betreff
    gerendert wird / Then bleiben die Ortsnamen im Betreff stehen."""
    notices = _compare_notices([(_alert(3, "extreme_heat", "Hitze"), ["toulon", "hyeres"])])
    subject = _subject(notices)
    assert subject == "[Le Var] Toulon, Hyères · ORANGE Hitze (Fr)", (
        f"Compare-Betreff mit <=2 Orten veraendert: {subject!r}"
    )


def test_ac16_compare_subject_all_locations_unchanged():
    """AC-16 (Non-Regression, JETZT SCHON GRUEN): Given alle Orte betroffen /
    When der Betreff gerendert wird / Then bleibt der Sonderfall 'alle Orte'
    unveraendert."""
    notices = _compare_notices([(_alert(3, "extreme_heat", "Hitze"), LOC_IDS)])
    subject = _subject(notices)
    assert subject == "[Le Var] alle Orte · ORANGE Hitze (Fr)", (
        f"Sonderfall 'alle Orte' veraendert: {subject!r}"
    )


# ---------------------------------------------------------------------------
# AC-17 — Ueberschrift wiederholt die Ortsliste nicht mehr
# ---------------------------------------------------------------------------

def test_ac17_headline_drops_full_location_list():
    """AC-17: Given eine Ortsvergleich-Alarmmail mit vielen betroffenen Orten /
    When die Ueberschrift im Mail-Text gerendert wird / Then nennt sie die
    betroffenen Gefahren-Typen, wiederholt aber nicht mehr die vollstaendige
    Liste der Ortsnamen aus dem Betreff."""
    headline = _headline_text(_many_warnings_notices())

    named = [n for n in (LOC_NAMES[i] for i in AFFECTED_7) if n in headline]
    assert not named, f"Ueberschrift wiederholt die Ortsnamen ({named!r}): {headline!r}"
    assert "Hitze" in headline, f"Ueberschrift nennt die Gefahren-Typen nicht: {headline!r}"
