"""Geteilter WarnBlock-Renderer — Struktur-Fidelity (#1216, embedded).

SPEC: docs/specs/modules/issue_1216_embedded_warnblock.md (AC-1/AC-3/AC-8)
DESIGN: docs/design-requests/issue_1216_warn_im_briefing/Gregor 20 - Warnung im Briefing.html

RED-Phase: der geteilte Renderer `render_warn_block(notices, *, variant, ...)`
existiert noch nicht in `output.renderers.alert.official_alerts` -> ImportError
bzw. AttributeError bei jedem Test.

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`/`OfficialAlertNotice`-
Instanzen, reine Renderer-Funktion; kein Netzwerk. Struktur-Treue zur
Design-Vorlage (`.wb`), aber FARB-Treue bewusst NICHT (PO 2026-07-11): der
Block nutzt die Bestands-Code-Tokens G_ALERT_L2/L3/L4, nicht die Design-Hex.
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_ALLDAY_FROM = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
FR_ALLDAY_TO = datetime(2026, 7, 10, 23, 59, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)
SA_ORANGE_FROM = datetime(2026, 7, 11, 16, 0, tzinfo=UTC)
SA_ORANGE_TO = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)

# Design-Vorlage-Hex (`.wb`-Klassen) — DIESE dürfen NICHT im Output erscheinen.
DESIGN_HEX = ("#e8b81f", "#e07a1e", "#c43030")
# Bestands-Code-Tokens (design_tokens.py) — DIESE tragen die Severity-Farbe.
TOKEN_L2, TOKEN_L3, TOKEN_L4 = "#9a6f00", "#c8482a", "#6d28d9"


def _alert(level: int, hazard: str, label: str, vf, vt, region="Hermagor", url=None):
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, url=url,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


def _two_gelb_uniform():
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
    # Absichtlich unsortiert (GELB zuerst) — der Renderer MUSS nach Stufe
    # absteigend ordnen (ORANGE zuerst).
    return [hitze, gewitter]


# ---------------------------------------------------------------------------
# AC-1 — embedded WarnBlock-Struktur: Dot/Eyebrow/Count/Quelle + pro Warnung
# ---------------------------------------------------------------------------
def test_ac1_embedded_structure_eyebrow_count_source_and_items():
    from output.renderers.alert.official_alerts import render_warn_block
    html = render_warn_block(
        _mixed_orange_gelb(), variant="embedded",
        source_label="GeoSphere Austria",
        source_url="https://warnungen.geosphere.at",
        stand_at="09:30", tz=UTC,
    )
    # `.wb`-Struktur der Design-Vorlage.
    assert 'class="wb' in html, f"kein .wb-Block-Markup: {html!r}"
    # Eyebrow (Singular „Amtliche Warnung", wie die Vorlage im Head).
    assert "Amtliche Warnung" in html
    # Count-Zeile nennt die Anzahl aktiver Warnungen.
    assert "2 aktiv" in html, f"Count-Zeile fehlt/abweichend: {html!r}"
    # Quelle als Link auf source_url.
    assert 'href="https://warnungen.geosphere.at"' in html
    assert "GeoSphere Austria" in html
    # Pro Warnung: Typ, Zeitraum, Route-Chip.
    assert "Gewitter" in html and "Hitze" in html
    # Gewitter-Zeitfenster (SA_ORANGE_FROM/TO = 16:00–20:00, wie das
    # Misch-Beispiel der Design-Vorlage „16–20 Uhr").
    assert "16:00" in html and "20:00" in html
    assert "ganztägig" in html                        # Hitze ganztägig
    assert "Segment 3" in html and "Segment 1" in html


# ---------------------------------------------------------------------------
# AC-3 — gemischte Stufen (embedded): Meter je Warnung + „höchste Stufe ORANGE"
# ---------------------------------------------------------------------------
def test_ac3_embedded_mixed_levels_meter_and_highest():
    from output.renderers.alert.official_alerts import render_warn_block
    html = render_warn_block(
        _mixed_orange_gelb(), variant="embedded",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Gemischt -> Meter je Warnung.
    assert 'class="meter"' in html, f"Meter fehlt bei gemischten Stufen: {html!r}"
    # Count-Zeile: höchste Stufe ORANGE.
    assert "höchste Stufe ORANGE" in html, f"Count-Zeile ohne 'höchste Stufe ORANGE': {html!r}"
    # Pro-Warnung Stufen-Wort + Position N/3.
    assert "ORANGE 2/3" in html and "GELB 1/3" in html
    # Reihenfolge: ORANGE (Gewitter) VOR GELB (Hitze).
    assert html.index("Gewitter") < html.index("Hitze")


# ---------------------------------------------------------------------------
# AC-3 — einheitliche Stufe (embedded): KEIN Meter, „Stufe GELB (1/3)"
# ---------------------------------------------------------------------------
def test_ac3_embedded_uniform_level_stufe_word_no_meter():
    from output.renderers.alert.official_alerts import render_warn_block
    html = render_warn_block(
        _two_gelb_uniform(), variant="embedded",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Einheitlich -> KEIN Meter, stattdessen „Stufe {WORT} ({pos}/3)".
    assert 'class="meter"' not in html, f"Meter darf bei einheitl. Stufe fehlen: {html!r}"
    assert "Stufe GELB" in html and "(1/3)" in html
    assert "2 aktiv" in html
    # Keine höhere Stufe genannt (keine ORANGE/ROT-Eskalationssprache).
    assert "höchste Stufe" not in html


# ---------------------------------------------------------------------------
# AC-3 — standalone-Variante: einheitlich -> Leiter, gemischt -> Meter
# ---------------------------------------------------------------------------
def test_ac3_standalone_uniform_ladder_mixed_meter():
    from output.renderers.alert.official_alerts import render_warn_block
    uniform = render_warn_block(
        _two_gelb_uniform(), variant="standalone",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Standalone einheitlich -> Warnstufen-Leiter (alle drei Stufen-Wörter).
    assert "GELB" in uniform and "ORANGE" in uniform and "ROT" in uniform
    assert 'class="meter"' not in uniform

    mixed = render_warn_block(
        _mixed_orange_gelb(), variant="standalone",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Standalone gemischt -> Meter je Warnung (Positions 2/3 und 1/3). #1233
    # Slice B haengt eine Stufen-Modifier-Klasse an (`.meter.orange`/`.gelb`,
    # SOLL-Design-Vorlage) -- daher Praefix-Check statt exaktem Attributwert.
    assert 'class="meter ' in mixed
    assert "2/3" in mixed and "1/3" in mixed


# ---------------------------------------------------------------------------
# AC-8 — Farb-Token-Grenze: Bestands-Tokens JA, Design-Hex NEIN
# ---------------------------------------------------------------------------
def test_ac8_uses_code_tokens_not_design_hex():
    from output.renderers.alert.official_alerts import render_warn_block
    html = render_warn_block(
        _mixed_orange_gelb(), variant="embedded",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Führende Stufe ORANGE == Level 3 -> Bestands-Token #c8482a.
    assert TOKEN_L3 in html, f"Bestands-Token {TOKEN_L3} fehlt: {html!r}"
    # Keiner der Design-Vorlage-Hex-Werte darf im Output auftauchen.
    for hexv in DESIGN_HEX:
        assert hexv not in html, f"Design-Hex {hexv} darf NICHT im Output stehen (AC-8): {html!r}"


def test_ac8_level4_uses_violet_token_not_design_red():
    from output.renderers.alert.official_alerts import render_warn_block
    notice = _notice(
        _alert(4, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["gesamte Route"], free_chips=[],
    )
    html = render_warn_block(
        [notice], variant="embedded",
        source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert TOKEN_L4 in html, f"Level-4-Token {TOKEN_L4} (violett) fehlt: {html!r}"
    assert "#c43030" not in html, "Design-Rot #c43030 darf NICHT erscheinen (AC-8)"
