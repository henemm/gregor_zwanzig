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
# F008 (Adversary Runde 5, PO-go 2026-07-13) — AC-16 gilt nur bei
# EINHEITLICHEM Umfang; bei uneinheitlichem Umfang gewinnt die korrekte
# Aussage ("mehrere Orte") auch bei <=2 Orten/Warnungen. Siehe Spec-Changelog
# `docs/specs/modules/fix_1237_1238_1239_mail_darstellung.md`.
# ---------------------------------------------------------------------------

def test_f008_ac16_does_not_apply_when_scope_differs_even_with_two_locations():
    """F008: Given eine Ortsvergleich-Alarmmail mit genau ZWEI betroffenen
    Orten und ZWEI Warnungen, die aber UNTERSCHIEDLICHE Orte betreffen (Hitze
    nur Alpha, Gewitter nur Beta) / When der Betreff gerendert wird / Then
    nennt er NICHT den Umfang der fuehrenden Warnung (das waere die falsche
    Aussage "nur Toulon", obwohl das Gewitter nur Hyères betrifft), sondern den
    neutralen, korrekten Platzhalter 'mehrere Orte'. AC-16s Bit-Identitaet gilt
    hier bewusst NICHT (PO-Entscheidung F008) -- sie war nie fuer diesen
    (vorher ungetesteten) uneinheitlichen Fall gedacht."""
    all_ids = ["toulon", "hyeres"]
    id_to_name = {"toulon": "Toulon", "hyeres": "Hyères"}
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices

    notices = build_compare_official_alert_notices(all_ids, id_to_name, [
        (_alert(3, "extreme_heat", "Hitze"), ["toulon"]),
        (_alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO), ["hyeres"]),
    ])
    subject = _subject(notices)
    assert "mehrere Orte" in subject, (
        f"Betreff nennt bei uneinheitlichem Umfang keinen neutralen Platzhalter: {subject!r}"
    )
    assert "nur Toulon" not in subject, (
        f"Betreff verallgemeinert weiterhin faelschlich auf den Umfang der "
        f"fuehrenden Warnung: {subject!r}"
    )


def test_f008_ac16_bit_identical_when_scope_uniform_with_two_warnings():
    """F008 (Non-Regression, Gegenstueck): Given zwei Warnungen, die BEIDE
    denselben Umfang haben (Toulon+Hyères) / When der Betreff gerendert wird /
    Then bleibt AC-16s Bit-Identitaet gewahrt -- der Umfang der fuehrenden
    Warnung ist hier korrekt, weil ALLE Warnungen ihn teilen."""
    notices = _compare_notices([
        (_alert(3, "extreme_heat", "Hitze"), ["toulon", "hyeres"]),
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO), ["toulon", "hyeres"]),
    ])
    subject = _subject(notices)
    assert subject == "[Le Var] Toulon, Hyères · ORANGE Hitze (Fr) + Gewitter (Sa)", (
        f"Betreff bei einheitlichem Umfang veraendert: {subject!r}"
    )


# ---------------------------------------------------------------------------
# F009 (Adversary Runde 5, HIGH) — `_uniform_scope` vergleicht Identitaeten
# (Orts-IDs), NICHT Anzeige-Namen. Zwei VERSCHIEDENE Orte mit GLEICHEM Namen
# duerfen nicht faelschlich als "einheitlicher Umfang" durchgehen.
# ---------------------------------------------------------------------------

def test_f009_same_name_different_location_ids_not_treated_as_uniform_scope():
    """F009 (HIGH): Given zwei VERSCHIEDENE Orte mit demselben Anzeigenamen
    ("Hütte"), die von je einer eigenen Warnung betroffen sind / When der
    Betreff gerendert wird / Then gilt der Umfang NICHT als einheitlich (beide
    Orte heissen zwar gleich, sind aber unterschiedliche IDs) -- der Betreff
    darf nicht faelschlich 'nur Hütte' zeigen, als waere nur EIN Ort betroffen.

    Root Cause: `scope_label` waere fuer beide Warnungen identisch ('nur
    Hütte'), weil `id_to_name` keine Eindeutigkeit der Namen erzwingt. Die
    Compare-Notices rechnen deshalb durchgaengig ueber Orts-**IDs** (#1216
    Slice 2a F006) -- `_uniform_scope` muss dieselbe Regel befolgen."""
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices

    all_ids = ["hutte-a", "hutte-b"]
    id_to_name = {"hutte-a": "Hütte", "hutte-b": "Hütte"}
    notices = build_compare_official_alert_notices(all_ids, id_to_name, [
        (_alert(3, "extreme_heat", "Hitze"), ["hutte-a"]),
        (_alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO), ["hutte-b"]),
    ])
    # Testaufbau-Nachweis: der Anzeige-Name-Vergleich WAERE hier "einheitlich"
    # gewesen (beide "nur Hütte") -- genau die Faessung, die F009 verhindert.
    assert {n.scope_label for n in notices} == {"nur Hütte"}, (
        "Testaufbau greift nicht: scope_label muesste fuer beide Orte "
        f"identisch sein: {[n.scope_label for n in notices]!r}"
    )
    subject = _subject(notices)
    assert "mehrere Orte" in subject, (
        f"Betreff behandelt zwei verschiedene gleichnamige Orte faelschlich "
        f"als einheitlichen Umfang: {subject!r}"
    )
    assert subject.count("nur Hütte") == 0, (
        f"Betreff zeigt 'nur Hütte', als waere nur EIN Ort betroffen: {subject!r}"
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


# ---------------------------------------------------------------------------
# F006/F007 (Adversary, Staging-Fund) — Headline verallgemeinert den Umfang
# der fuehrenden Warnung auf alle UND nutzt das generische Typ-Wort statt des
# reicheren Quell-Labels. Reproduktion der echten Staging-Mail (#1238/#1239):
# eine GELBE Waldbrand-Warnung betraf ausschliesslich Draguignan, waehrend die
# Headline nur Toulon/Hyeres nannte; die Zugangssperre hiess in der Headline
# "Zugang gesperrt", im Warn-Titel/Betreff aber "Zugang eingeschraenkt —
# Monts Toulonnais".
# ---------------------------------------------------------------------------

def _mixed_scope_locations():
    """Vier Warnungen (Staging-Nachbau): zwei ORANGE ueber Toulon+Hyères
    (Waldbrand + Zugangssperre), eine GELBE Waldbrand-Warnung NUR ueber
    Draguignan, eine GELBE Hitze-Warnung ueber Toulon+Hyères -- also
    UNTERSCHIEDLICHER Umfang je Warnung (kein einheitlicher Scope)."""
    all_ids = ["toulon", "hyeres", "draguignan"]
    id_to_name = {"toulon": "Toulon", "hyeres": "Hyères", "draguignan": "Draguignan"}
    tagged = [
        (_alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                source="meteo_forets", region="Zone Ouest"), ["toulon", "hyeres"]),
        (_alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                source="massif_closure", region="Monts Toulonnais",
                dedup_id="monts-toulonnais"), ["toulon", "hyeres"]),
        (_alert(2, "wildfire_risk", "Waldbrand-Gefahr — Stufe 2", SA_FROM, SA_TO,
                source="meteo_forets", region="Zone Draguignan"), ["draguignan"]),
        (_alert(2, "extreme_heat", "Hitze", SA_FROM, SA_TO), ["toulon", "hyeres"]),
    ]
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    return build_compare_official_alert_notices(all_ids, id_to_name, tagged)


def test_f006_headline_drops_scope_when_warnings_have_different_scope():
    """F006 (HIGH, Staging-Fund): Given Warnungen mit UNTERSCHIEDLICHEM Umfang
    (eine betrifft nur Draguignan, drei betreffen Toulon+Hyères) / When die
    Ueberschrift gerendert wird / Then nennt sie KEINEN gemeinsamen Umfang mehr
    (kein "für ... gemeldet") -- vorher verallgemeinerte sie faelschlich den
    Umfang der fuehrenden Warnung ("für Toulon, Hyères gemeldet", obwohl eine
    Warnung ausschliesslich Draguignan betraf)."""
    headline = _headline_text(_mixed_scope_locations())

    assert "für" not in headline, (
        f"Ueberschrift nennt trotz unterschiedlichem Umfang einen gemeinsamen "
        f"Ort/Scope: {headline!r}"
    )
    # Wortgrenzen-Regex statt Substring: "Toulon" ist Teil von "Monts
    # Toulonnais" (Zugangssperre-Label), das als reicherer Warn-Titel bewusst
    # weiter im Text steht (F007) -- nur der ORTSNAME "Toulon" (Scope-Angabe)
    # darf verschwunden sein, nicht die Massiv-Bezeichnung.
    assert not re.search(r"\bToulon\b", headline) and "Draguignan" not in headline, (
        f"Ueberschrift nennt weiterhin Ortsnamen trotz unterschiedlichem Umfang: {headline!r}"
    )
    assert "Waldbrand-Gefahr" in headline and "Hitze" in headline, (
        f"Ueberschrift nennt nicht mehr alle Gefahren-Typen: {headline!r}"
    )


def test_f007_headline_uses_richer_label_not_generic_hazard_word():
    """F007 (MEDIUM, Staging-Fund): Given eine Zugangssperre mit reicherem
    Quell-Label ("Zugang eingeschränkt — Monts Toulonnais") / When die
    Ueberschrift gerendert wird / Then nennt sie denselben reicheren Label wie
    Warn-Titel/Betreff, NICHT das generische Typ-Wort "Zugang gesperrt" --
    sonst widerspricht sich die Mail an zwei Stellen ueber dieselbe Warnung."""
    headline = _headline_text(_mixed_scope_locations())

    assert "Zugang eingeschränkt — Monts Toulonnais" in headline, (
        f"Ueberschrift nutzt nicht den reicheren Quell-Label: {headline!r}"
    )
    assert "Zugang gesperrt" not in headline, (
        f"Ueberschrift nennt weiterhin das generische, widerspruechliche "
        f"Typ-Wort 'Zugang gesperrt': {headline!r}"
    )


def test_f006_subject_drops_leading_scope_when_warnings_have_different_scope():
    """F006 (HIGH, Staging-Fund, proaktiv auch im Betreff behoben): derselbe
    Umfang-Verallgemeinerungsfehler im Betreff (`render_official_alert_subject`
    nutzt ebenfalls `_scope_display(ordered[0])`) -- bei unterschiedlichem
    Umfang der Warnungen nennt der Betreff einen neutralen Platzhalter statt
    des Umfangs der fuehrenden Warnung."""
    subject = _subject(_mixed_scope_locations(), prefix="E2E1238")

    # Wortgrenzen-Regex (wie bei der Headline): "Toulon" als Teil von "Monts
    # Toulonnais" (Warn-Titel der Zugangssperre) bleibt zulaessig, nur die
    # SCOPE-Angabe (Ortsname als Reichweite) darf nicht mehr die Warnung eines
    # einzelnen Hazards als Gesamtaussage zeigen.
    assert not re.search(r"\bToulon\b", subject) and "Draguignan" not in subject, (
        f"Betreff nennt weiterhin den Umfang einer einzelnen Warnung als "
        f"Gesamtaussage: {subject!r}"
    )
    assert "mehrere Orte" in subject, (
        f"Betreff nennt keinen neutralen Platzhalter bei unterschiedlichem Umfang: {subject!r}"
    )
