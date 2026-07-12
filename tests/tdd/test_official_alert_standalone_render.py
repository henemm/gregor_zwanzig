"""Geteilter Standalone-Renderer — Redesign auf SOLL-Vorlage (#1233 Slice B).

SPEC: docs/specs/modules/issue_1233_alert_amtliche_warnung.md (AC-6..AC-13)
DESIGN: docs/design-requests/issue_1233_alert_amtliche_warnung/
        Gregor 20 - Alert Amtliche Warnung.html

RED-Phase: `render_warn_block(variant="standalone")` → `render_official_alert_html`
erzeugt heute noch die ALTE Struktur (kein `.verdict`, keine `.stufe`/`.warns`/
`.facts`/`.mono`/`.seg`/`.route-note`-Klassen). Alle Tests unten, die auf diese
Klassen selektieren, sind daher RED, bis der Renderer auf die SOLL-Vorlage
gehoben wird.

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`/`OfficialAlertNotice`-DTOs,
reine Renderer-Funktionen bzw. echte `NotificationService`-Aufrufe mit
`mail_sink`-Aufzeichnungssenke (kein Netzwerk). HTML wird strukturell mit
BeautifulSoup geparst (Klassen/Reihenfolge/Text), nicht per Substring-Suche im
rohen HTML — Ausnahme AC-12 (Wochentags-Konsistenz, Text-Extraktion aus
gerendertem Betreff/Body-Text) und AC-13 (Farbwert-Nachweis am gerenderten
Ergebnis, Spec verlangt explizit "nicht Quelltext-grep", ein Wert-Nachweis am
Output ist hier die vorgesehene Pruefform).

AC-14 (Pixel-/Struktur-Fidelity gegen die Design-Vorlage) läuft separat über den
Fidelity-Harness im Validierungsschritt (`/60-validate`) und ist hier bewusst
NICHT als Unittest abgebildet (nur ein `skip`-Platzhalter unten).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_ALLDAY_FROM = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
FR_ALLDAY_TO = datetime(2026, 7, 10, 23, 59, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)
SA_ORANGE_FROM = datetime(2026, 7, 11, 16, 0, tzinfo=UTC)
SA_ORANGE_TO = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)

# Bestands-Code-Tokens (design_tokens.py G_ALERT_L2/L3/L4) — DIESE müssen im
# Output stehen (AC-13).
TOKEN_L2, TOKEN_L3, TOKEN_L4 = "#9a6f00", "#c8482a", "#6d28d9"
# Design-Vorlage-Hex (`.stufe`/`.meter`/`.dot`-Klassen) — DIESE dürfen NICHT im
# Output erscheinen (AC-13).
DESIGN_HEX_GELB, DESIGN_HEX_ORANGE, DESIGN_HEX_ROT = "#e8b81f", "#e07a1e", "#c43030"


def _alert(level, hazard, label, vf, vt, region="Hermagor-Pressegger See") -> OfficialAlert:
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


def _render(notices, **overrides) -> str:
    from output.renderers.alert.official_alerts import render_warn_block
    kwargs = dict(
        variant="standalone", source_label="GeoSphere Austria",
        stand_at="09:30", tz=UTC,
    )
    kwargs.update(overrides)
    return render_warn_block(notices, **kwargs)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def soup_has_class(html: str, css_class: str) -> bool:
    return _soup(html).select_one(f".{css_class}") is not None


def _class_fingerprint(html: str) -> list[tuple[str, tuple[str, ...]]]:
    """Klassen-Reihenfolge-Fingerabdruck: (Tag, sortierte Klassen) je Element
    mit `class`-Attribut, in DOM-Reihenfolge. Ignoriert Text -> Chip-
    Beschriftungen (Segmente vs. Orte) fallen bewusst nicht ins Gewicht (AC-11)."""
    soup = _soup(html)
    return [
        (tag.name, tuple(sorted(tag.get("class", []))))
        for tag in soup.find_all(True)
        if tag.get("class")
    ]


def _two_gelb_full_route():
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    gewitter = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    return [hitze, gewitter]


def _mixed_orange_gelb():
    gewitter = _notice(
        _alert(3, "thunderstorm", "Gewitter", SA_ORANGE_FROM, SA_ORANGE_TO),
        scope_label="Segment 3", sms_scope="S3",
        affected_chips=["Segment 3"], free_chips=["Segment 1", "Ziel"],
    )
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="Segment 1", sms_scope="S1",
        affected_chips=["Segment 1"], free_chips=["Segment 3", "Ziel"],
    )
    # Absichtlich unsortiert übergeben (GELB zuerst) — der Renderer MUSS nach
    # Stufe absteigend ordnen (ORANGE zuerst).
    return [hitze, gewitter]


# ---------------------------------------------------------------------------
# AC-6 — Verdict-Pill mit .dot, Text + optionalem Höchststufen-Zusatz
# ---------------------------------------------------------------------------
def test_ac6_verdict_pill_uniform_count_and_dot():
    soup = _soup(_render(_two_gelb_full_route()))
    verdicts = soup.select(".verdict")
    assert len(verdicts) == 1, f"Erwartet genau 1 .verdict-Pill, gefunden: {len(verdicts)}"
    verdict = verdicts[0]
    assert len(verdict.select(".dot")) == 1, f".verdict muss genau einen .dot enthalten: {verdict}"
    text = verdict.get_text(" ", strip=True)
    assert "2 amtliche Warnungen" in text, f"Verdict-Text falsch: {text!r}"
    assert "höchste Stufe" not in text, f"Uniforme Stufe darf keinen Zusatz zeigen: {text!r}"


def test_ac6_verdict_pill_mixed_shows_highest_level_suffix():
    soup = _soup(_render(_mixed_orange_gelb()))
    verdicts = soup.select(".verdict")
    assert len(verdicts) == 1
    text = verdicts[0].get_text(" ", strip=True)
    assert "2 amtliche Warnungen" in text, f"Verdict-Text falsch: {text!r}"
    assert "höchste Stufe ORANGE" in text, f"Gemischte Stufen -> Zusatz erwartet: {text!r}"


# ---------------------------------------------------------------------------
# AC-7 — deterministische .body-h1 Headline nach fester Template-Regel
# ---------------------------------------------------------------------------
def test_ac7_headline_deterministic_two_runs_byte_identical():
    notices = _two_gelb_full_route()
    h1_a = _soup(_render(notices)).select_one(".body-h1")
    h1_b = _soup(_render(notices)).select_one(".body-h1")
    assert h1_a is not None, "kein .body-h1 im Standalone-Body gefunden"
    assert h1_b is not None
    assert h1_a.get_text() == h1_b.get_text(), (
        "Headline muss bei identischer Eingabe byte-identisch sein (kein LLM, "
        "reine Template-Logik)"
    )


def test_ac7_headline_follows_template_rule_for_known_scope():
    """Bekannte Eingabe (Spec-Beispiel, wörtlich aus der Bug-Beschreibung #1233:
    scope_label 'nur Geisbergalm (Zillertal Arena)') -> erwarteter Satz
    '{Typ} für {scope} gemeldet.'"""
    warn = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="nur Geisbergalm (Zillertal Arena)", sms_scope="nurGeisbergalm",
        affected_chips=["Geisbergalm"], free_chips=[],
    )
    soup = _soup(_render([warn]))
    h1 = soup.select_one(".body-h1")
    assert h1 is not None
    assert h1.get_text() == "Hitze für nur Geisbergalm (Zillertal Arena) gemeldet.", (
        f"Headline weicht von der Template-Regel ab: {h1.get_text()!r}"
    )


def test_ac7_headline_lists_multiple_types_joined_with_und():
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="alle Orte", sms_scope="alleOrte",
        affected_chips=["Ort A", "Ort B"], free_chips=[],
    )
    gewitter = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="alle Orte", sms_scope="alleOrte",
        affected_chips=["Ort A", "Ort B"], free_chips=[],
    )
    soup = _soup(_render([hitze, gewitter]))
    h1 = soup.select_one(".body-h1")
    assert h1 is not None
    assert h1.get_text() == "Hitze und Gewitter für alle Orte gemeldet.", h1.get_text()


# ---------------------------------------------------------------------------
# AC-8 — uniforme Stufe: .stufe-Leiter mit .on, kein .meter
# ---------------------------------------------------------------------------
def test_ac8_uniform_level_shows_stufe_ladder_with_on_and_no_meter():
    soup = _soup(_render(_two_gelb_full_route()))
    ladder = soup.select_one(".stufe")
    assert ladder is not None, "Uniforme Stufe erwartet eine .stufe-Leiter"
    on_spans = ladder.select(".on")
    assert len(on_spans) == 1, f"Genau eine aktive Stufe erwartet: {on_spans}"
    assert on_spans[0].get_text(strip=True) == "GELB", (
        f"Aktive Stufe muss GELB heissen (Stufe 2): {on_spans[0].get_text()!r}"
    )
    hint = soup.select_one(".stufe-hint")
    assert hint is not None, ".stufe-hint fehlt"
    assert "niedrigste" in hint.get_text(), (
        f".stufe-hint muss die Position benennen: {hint.get_text()!r}"
    )
    assert soup.select(".meter") == [], "Bei uniformer Stufe darf KEIN .meter erscheinen"


# ---------------------------------------------------------------------------
# AC-9 — gemischte Stufen: je Warnung ein .meter, keine .stufe-Leiter, Reihenfolge
# ---------------------------------------------------------------------------
def test_ac9_mixed_levels_each_warning_has_meter_no_ladder_highest_first():
    soup = _soup(_render(_mixed_orange_gelb()))
    meters = soup.select(".meter")
    assert len(meters) == 2, f"Erwartet je Warnung ein .meter: {len(meters)}"
    assert soup.select(".stufe") == [], (
        "Bei gemischten Stufen darf KEINE gemeinsame .stufe-Leiter erscheinen"
    )
    # Design-Vorlage: gemischte Stufen -> `.warn.stacked` je Warnung mit `.whead`
    # (Meter + Typ), statt des einheitlichen `.warn`-Grids (AC-9/Body-Reihenfolge
    # Punkt 5 der Spec).
    stacked = soup.select(".warn.stacked")
    assert len(stacked) == 2, f"Erwartet je Warnung ein .warn.stacked: {len(stacked)}"
    assert len(soup.select(".warn.stacked .whead")) == 2, (
        "Jedes .warn.stacked braucht einen .whead (Meter + Typ)"
    )
    types = [t.get_text(strip=True) for t in soup.select(".type")]
    assert types, "Keine .type-Elemente gefunden"
    assert types[0] == "Gewitter", (
        f"Höchste Stufe (ORANGE/Gewitter) muss zuerst stehen: {types!r}"
    )
    assert "Hitze" in types[1:], f"Hitze (GELB) muss nach Gewitter stehen: {types!r}"


# ---------------------------------------------------------------------------
# AC-10 — Teilstrecke: betroffene Chips normal, freie durchgestrichen + Hinweis
# ---------------------------------------------------------------------------
def test_ac10_partial_route_affected_active_free_struck_through_with_note():
    warn = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="St. Stefan im Gailtal"),
        scope_label="Segment 2–4", sms_scope="nur S2-4",
        affected_chips=["Segment 2–4"], free_chips=["Segment 1", "Ziel"],
    )
    soup = _soup(_render([warn]))
    off_chips = soup.select(".seg.off")
    off_labels = {c.get_text(strip=True) for c in off_chips}
    assert off_labels == {"Segment 1", "Ziel"}, f"Freie Chips falsch/fehlend: {off_labels!r}"

    active_chips = [c for c in soup.select(".seg") if "off" not in (c.get("class") or [])]
    active_labels = {c.get_text(strip=True) for c in active_chips}
    assert active_labels == {"Segment 2–4"}, f"Betroffener Chip falsch/fehlend: {active_labels!r}"

    note = soup.select_one(".route-note")
    assert note is not None, "Bei Teilstrecke erwartet .route-note"
    assert "frei" in note.get_text(), (
        f".route-note muss die freie Reststrecke erwähnen: {note.get_text()!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — geteilter Renderer: Trip- und Compare-Pfad strukturgleich
# ---------------------------------------------------------------------------
def test_ac11_trip_and_compare_paths_share_identical_body_structure():
    """Trip-Pfad (`send_official_alert`) und Compare-Pfad
    (`send_multi_location_official_alert`) rufen denselben Renderer auf ->
    identische Klassen-/Reihenfolge-Struktur bei äquivalentem Szenario (1
    Warnung Stufe 2, volle Abdeckung, 1 aktiver Chip). Einziger legitimer
    Unterschied sind die Chip-Beschriftungen (Segment- vs. Ortsname), die der
    Fingerabdruck bewusst ausblendet."""
    from app.config import Settings
    from app.trip import Stage, Trip, Waypoint
    from app.user import SavedLocation
    from services.notification_service import NotificationService

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
    )

    # Trip-Pfad: 1 Wegpunkt -> 1 Segment, volle Route betroffen.
    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(id="tdd-1233-ac11-trip", name="AC11 Trip", stages=[stage])
    trip_notices_raw = [(_alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO), ["1"])]
    trip_mail: list = []
    NotificationService(settings, "tdd-1233-ac11-trip").send_official_alert(
        trip=trip, notices=trip_notices_raw, effective_channels={"email"},
        mail_sink=lambda subject, body: trip_mail.append(body),
        sms_sink=lambda text: None,
    )
    assert len(trip_mail) == 1, "Trip-Pfad hat keine Mail erzeugt"

    # Compare-Pfad: 1 Ort, volle Abdeckung.
    loc = SavedLocation(id="loc-a", name="Ort A", lat=47.0, lon=11.0, elevation_m=1000)
    compare_tagged = [
        (_alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO), ["loc-a"])
    ]
    compare_mail: list = []
    NotificationService(settings, "tdd-1233-ac11-compare").send_multi_location_official_alert(
        "AC11 Compare", [loc], compare_tagged, {"email"},
        mail_sink=lambda subject, body: compare_mail.append(body),
    )
    assert len(compare_mail) == 1, "Compare-Pfad hat keine Mail erzeugt"

    fp_trip = _class_fingerprint(trip_mail[0])
    fp_compare = _class_fingerprint(compare_mail[0])
    assert fp_trip == fp_compare, (
        "Trip- und Compare-Pfad müssen strukturgleiches HTML liefern (ein und "
        f"derselbe geteilte Renderer):\nTrip:    {fp_trip!r}\nCompare: {fp_compare!r}"
    )
    # Anker gegen einen falsch-grünen Vergleich zweier ALTER (identisch
    # gebliebener) Strukturen: beide Pfade müssen tatsächlich die NEUE
    # SOLL-Struktur tragen (sonst würde dieser Test schon mit dem
    # unveränderten #1216-Renderer grün sein, ohne das Redesign zu belegen).
    assert soup_has_class(trip_mail[0], "verdict"), "Trip-Body hat keine .verdict-Pill"
    assert soup_has_class(trip_mail[0], "warns"), "Trip-Body hat keinen .warns-Container"
    assert soup_has_class(compare_mail[0], "verdict"), "Compare-Body hat keine .verdict-Pill"
    assert soup_has_class(compare_mail[0], "warns"), "Compare-Body hat keinen .warns-Container"


# ---------------------------------------------------------------------------
# AC-12 — Betreff-Wochentag == Body-Wochentag (Nebenbefund)
# ---------------------------------------------------------------------------
def test_ac12_subject_and_body_weekday_are_consistent():
    """AC-12 (#1233 Nebenbefund-Repro): Betreff-Wochentagskürzel muss zum
    Body-Wochentag passen. Bug: `_typ_tag` (Betreff) nutzt `alert.valid_from`
    roh (i.d.R. UTC), `_format_validity` (Body) lokalisiert — bei einem
    Gültigkeitsbeginn kurz vor Mitternacht (lokaler Tageswechsel) zeigen beide
    unterschiedliche Wochentage (Symptom: '(Sa)' im Betreff vs. 'So' im Body)."""
    from output.renderers.alert.official_alerts import render_official_alert_subject

    vienna = ZoneInfo("Europe/Vienna")
    # UTC-Datum X, 23:00 -> Europe/Vienna (Sommer, +2h) rollt auf Datum X+1 über.
    vf = datetime(2026, 7, 11, 23, 0, tzinfo=UTC)
    vt = datetime(2026, 7, 12, 2, 0, tzinfo=UTC)
    warn = _notice(
        _alert(2, "extreme_heat", "Hitze", vf, vt),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )

    subject = render_official_alert_subject([warn], prefix="KHW 403")
    html = _render([warn], tz=vienna)

    m_subj = re.search(r"\(([A-Za-zÄÖÜäöü]{2})\)", subject)
    assert m_subj is not None, f"kein Wochentagskürzel im Betreff gefunden: {subject!r}"
    subj_weekday = m_subj.group(1)

    body_text = _soup(html).get_text(" ", strip=True)
    m_body = re.search(r"Gültig:\s*([A-Za-zÄÖÜäöü]{2})\s\d{2}\.\d{2}\.", body_text)
    assert m_body is not None, f"kein lokalisierter Wochentag im Body gefunden: {body_text!r}"
    body_weekday = m_body.group(1)

    assert subj_weekday == body_weekday, (
        f"Betreff zeigt '{subj_weekday}', Body zeigt '{body_weekday}' für dieselbe "
        f"Warnung — Wochentag muss konsistent sein (#1233 Nebenbefund)"
    )


# ---------------------------------------------------------------------------
# AC-13 — Farbgebung über Bestands-Tokens, keine Design-Vorlage-Hex
# ---------------------------------------------------------------------------
def test_ac13_uniform_level2_dot_uses_code_token_not_design_hex():
    """Die `.verdict .dot` (Leitstufen-Farbe, Design-Vorlage Zeile 174) muss die
    Bestands-Token-Farbe tragen -- Wert-Nachweis AM konkreten neuen Element,
    nicht per Blanket-Substring auf dem gesamten Dokument (das wäre schon mit
    dem alten #1216-Badge zufällig grün, weil der ebenfalls G_ALERT_L2 nutzt,
    ohne die neue `.dot`-Struktur zu haben)."""
    html = _render(_two_gelb_full_route())
    dot = _soup(html).select_one(".verdict .dot")
    assert dot is not None, ".verdict .dot fehlt im Output"
    style = dot.get("style", "")
    assert TOKEN_L2 in style, f"Bestands-Token {TOKEN_L2} (Stufe 2) fehlt am .dot: {style!r}"
    for hexv in (DESIGN_HEX_GELB, DESIGN_HEX_ORANGE, DESIGN_HEX_ROT):
        assert hexv not in style, f"Design-Vorlage-Hex {hexv} darf NICHT am .dot stehen: {style!r}"


def test_ac13_mixed_levels_meter_bars_use_l3_token_not_design_hex():
    """Das fuehrende `.meter .bars i` (gefuellter Balken, Design-Vorlage Zeile
    350) der hoechsten Warnung (ORANGE, Stufe 3) muss die Bestands-Token-Farbe
    tragen, nicht das Design-Hex."""
    html = _render(_mixed_orange_gelb())
    meters = _soup(html).select(".meter")
    assert meters, "kein .meter gefunden (gemischte Stufen erwarten je Warnung eins)"
    bars = meters[0].select(".bars i")
    assert bars, ".meter .bars i (gefuellte Eskalations-Punkte) fehlt am fuehrenden Meter"
    bar_styles = " ".join(b.get("style", "") for b in bars)
    assert TOKEN_L3 in bar_styles, (
        f"Bestands-Token {TOKEN_L3} (Stufe 3, führend) fehlt an den Meter-Balken: {bar_styles!r}"
    )
    for hexv in (DESIGN_HEX_GELB, DESIGN_HEX_ORANGE, DESIGN_HEX_ROT):
        assert hexv not in bar_styles, (
            f"Design-Vorlage-Hex {hexv} darf NICHT an den Meter-Balken stehen: {bar_styles!r}"
        )


# ---------------------------------------------------------------------------
# Fix-Loop Adversary F001 — freier `.seg.off`-Chip nutzt das Bestands-Token
# G_INK_FAINT statt der roh uebernommenen Design-Vorlage-Hex `#9a958a`.
# ---------------------------------------------------------------------------
def test_f001_free_chip_uses_code_token_not_design_hex():
    from output.renderers.email.design_tokens import G_INK_FAINT

    warn = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="St. Stefan im Gailtal"),
        scope_label="Segment 2–4", sms_scope="nur S2-4",
        affected_chips=["Segment 2–4"], free_chips=["Segment 1", "Ziel"],
    )
    soup = _soup(_render([warn]))
    off_chips = soup.select(".seg.off")
    assert off_chips, "kein freier .seg.off-Chip gefunden"
    for chip in off_chips:
        style = chip.get("style", "")
        assert G_INK_FAINT in style, (
            f"Bestands-Token {G_INK_FAINT} fehlt am freien Chip: {style!r}"
        )
        assert "#9a958a" not in style, (
            f"Design-Vorlage-Hex #9a958a darf NICHT am freien Chip stehen: {style!r}"
        )


# ---------------------------------------------------------------------------
# Fix-Loop Adversary F002 — zentrale Struktur-Elemente MUESSEN Inline-CSS
# tragen, weil der Renderer keinen <style>-Block emittiert (E-Mail-Clients
# ignorieren externes/<style>-CSS). Sichert die "Verbindliche Arbeitsweise
# (PO)"-Vorgabe der Spec dauerhaft ab.
# ---------------------------------------------------------------------------
def test_f002_central_structure_elements_carry_non_empty_inline_style():
    # `.stufe` erscheint nur bei uniformer Stufe, `.meter` nur bei gemischten
    # Stufen (AC-8/AC-9) — zwei Szenarien noetig, um beide DOM-Zweige
    # gleichzeitig abzudecken.
    warn_partial = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="St. Stefan im Gailtal"),
        scope_label="Segment 2–4", sms_scope="nur S2-4",
        affected_chips=["Segment 2–4"], free_chips=["Segment 1", "Ziel"],
    )
    uniform_selectors = [
        ".verdict", ".body-h1", ".stufe", ".warn", ".facts", ".seg",
        ".route-note", ".src", ".body-foot",
    ]
    mixed_selectors = [".verdict", ".body-h1", ".warn", ".facts", ".seg", ".meter"]
    for html, selectors in (
        (_render([warn_partial]), uniform_selectors),
        (_render(_mixed_orange_gelb()), mixed_selectors),
    ):
        soup = _soup(html)
        for selector in selectors:
            elements = soup.select(selector)
            assert elements, f"Selector {selector!r} liefert kein Element im gerenderten HTML"
            for el in elements:
                style = el.get("style", "")
                assert style.strip(), (
                    f"Element {selector!r} ({el.name} class={el.get('class')!r}) hat "
                    f"kein/leeres Inline-style-Attribut — E-Mail-Clients ignorieren "
                    f"externes/<style>-CSS, ohne Inline-Style rendert es unformatiert (F002)"
                )


# ---------------------------------------------------------------------------
# Fix-Loop Nachzug — `.warn + .warn`-Trennlinie der Vorlage hat in
# Inline-CSS-Mails keinen Geschwister-Selektor: jede Zeile ausser der ersten
# traegt ihr `border-top` selbst inline.
# ---------------------------------------------------------------------------
def test_f002_followup_only_non_first_warn_row_carries_border_top():
    soup_uniform = _soup(_render(_two_gelb_full_route()))
    rows_uniform = soup_uniform.select(".warn")
    assert len(rows_uniform) == 2, f"Erwartet 2 .warn-Zeilen (uniform): {len(rows_uniform)}"
    assert "border-top" not in rows_uniform[0].get("style", ""), (
        f"Erste .warn-Zeile darf KEIN border-top tragen: {rows_uniform[0].get('style')!r}"
    )
    assert "border-top:1px solid #e7e2d3" in rows_uniform[1].get("style", ""), (
        f"Zweite .warn-Zeile muss die Trennlinie inline tragen: "
        f"{rows_uniform[1].get('style')!r}"
    )

    soup_mixed = _soup(_render(_mixed_orange_gelb()))
    rows_mixed = soup_mixed.select(".warn.stacked")
    assert len(rows_mixed) == 2, f"Erwartet 2 .warn.stacked-Zeilen (gemischt): {len(rows_mixed)}"
    assert "border-top" not in rows_mixed[0].get("style", ""), (
        f"Erste .warn.stacked-Zeile darf KEIN border-top tragen: {rows_mixed[0].get('style')!r}"
    )
    assert "border-top:1px solid #e7e2d3" in rows_mixed[1].get("style", ""), (
        f"Zweite .warn.stacked-Zeile muss die Trennlinie inline tragen: "
        f"{rows_mixed[1].get('style')!r}"
    )


def test_f002_standalone_body_never_leaks_design_template_hex():
    """Ergaenzender Substring-Nachweis (Optional-Punkt des Fix-Auftrags):
    keine der vier Design-Vorlage-Warnstufen-/Ink4-Hex duerfen im gerenderten
    Standalone-Body auftauchen (AC-13-Absicherung ueber alle betroffenen
    Elemente hinweg, nicht nur `.dot`/`.meter .bars i`)."""
    html_uniform = _render(_two_gelb_full_route())
    html_mixed = _render(_mixed_orange_gelb())
    for hexv in (DESIGN_HEX_GELB, DESIGN_HEX_ORANGE, DESIGN_HEX_ROT, "#9a958a"):
        assert hexv not in html_uniform, (
            f"Design-Vorlage-Hex {hexv} darf NICHT im Standalone-Body (uniform) stehen"
        )
        assert hexv not in html_mixed, (
            f"Design-Vorlage-Hex {hexv} darf NICHT im Standalone-Body (gemischt) stehen"
        )


# ---------------------------------------------------------------------------
# Fix-Loop Nebenbefund F003 — aktive `.stufe span.on` darf jede CSS-
# Eigenschaft nur EINMAL im style-Attribut tragen (keine Basis+Override-
# Duplikate wie `background:...;background:...;`).
# ---------------------------------------------------------------------------
def test_f003_active_stufe_span_style_has_no_duplicate_properties():
    soup = _soup(_render(_two_gelb_full_route()))
    on_span = soup.select_one(".stufe span.on")
    assert on_span is not None, "kein aktiver .stufe span.on gefunden"
    style = on_span.get("style", "")
    assert style.strip(), "aktiver .stufe span.on hat kein Inline-style"
    props = [decl.split(":", 1)[0].strip() for decl in style.split(";") if decl.strip()]
    for prop in ("background", "color"):
        count = props.count(prop)
        assert count == 1, (
            f"CSS-Eigenschaft {prop!r} darf nur EINMAL im style stehen, "
            f"gefunden {count}x: {style!r}"
        )


# ---------------------------------------------------------------------------
# AC-14 — Pixel-/Struktur-Fidelity: läuft separat im Fidelity-Harness
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Fidelity via Harness in /60-validate")
def test_ac14_pixel_fidelity_placeholder():
    """AC-14: Pixel-/Struktur-Fidelity der Standalone-Mail gegen
    'Gregor 20 - Alert Amtliche Warnung.html' (Sektionen 'Nachher · Email',
    Teilstrecke, gemischte Stufen) wird über den Fidelity-Harness im
    Validierungsschritt geprüft, nicht als isolierter Unittest hier."""
