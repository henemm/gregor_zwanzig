"""TDD RED — Issue #1488 Scheibe B.

SPEC: docs/specs/modules/fix_1488_sb_gewitter_mailwort.md AC-1..AC-3, AC-5

Der `"plain"`-Zweig von `resolve_thunder_day_branch()` (Etappe OHNE stuendliche
Gewitterreihe) liest `tok["thunder_plain"]` aus `_THUNDER_MAP`
(`output.renderers.email.helpers`), das fuer die Stufen MED/HIGH noch die
englischen Woerter `'⚡MED'`/`'⚡HIGH'` traegt statt der kanonischen deutschen
Woerter aus `THUNDER_LABEL_DE` (`'⚡mittel'`/`'⚡hoch'`). Alle drei produktiven
Renderer (Klartext-Ausblick, Kompaktformat, Telegram-Trendblock) rufen
denselben `tok["thunder_plain"]`-Wert ab -- kein Test-Zwischenlayer, jede
Assertion prueft eine tatsaechlich gerenderte Ausgabe (ADR-0025 Entscheidung 5).

RED-Ursache (heute, vor der Implementierung):
- `_THUNDER_MAP["MED"]["plain"]` == "⚡MED" (nicht "⚡mittel")
- `_THUNDER_MAP["HIGH"]["plain"]` == "⚡HIGH" (nicht "⚡hoch")
- `format_trend_tokens()` liefert noch die toten Felder `thunder_sms`,
  `thunder_sq_color`, `thunder_word_color`

Keine Mocks, kein Dateiinhalt-Check.
"""
from __future__ import annotations


def _stage_ohne_stundenreihe(thunder: str) -> dict:
    return dict(
        weekday="Mo", name="Etappe Gewitter", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder=thunder, note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
    )


# ────────── AC-1 + AC-3: "plain"-Zweig zeigt deutsches Wort, ist erreichbar ──

def test_ac1_ac3_plain_zweig_zeigt_deutsche_gewitterworte():
    from output.renderers.email.compact import _compact_thunder_field
    from output.renderers.email.helpers import format_trend_tokens
    from output.renderers.email.outlook import render_outlook_plain
    from output.renderers.email.thunder_branch import resolve_thunder_day_branch
    from output.renderers.narrow import _outlook_lines

    for level, deutsches_wort in (("MED", "mittel"), ("HIGH", "hoch")):
        stage = _stage_ohne_stundenreihe(level)
        tok = format_trend_tokens(stage)

        # AC-3: der Zweig ist erreichbar -- kein toter Code
        branch = resolve_thunder_day_branch(tok, stage)
        assert branch == "plain", (
            f"resolve_thunder_day_branch() liefert {branch!r} statt 'plain' "
            f"fuer eine Etappe ohne hourly_thunder -- AC-3 unbelegt."
        )

        # AC-1: Klartext-Ausblick (outlook.py)
        plain_text = render_outlook_plain([stage])
        assert f"⚡{deutsches_wort}" in plain_text, (
            f"Klartext-Ausblick zeigt bei thunder={level!r} nicht "
            f"'⚡{deutsches_wort}'. Ausgabe: {plain_text!r}"
        )
        assert level not in plain_text, (
            f"Klartext-Ausblick zeigt bei thunder={level!r} noch das "
            f"englische Wort {level!r}. Ausgabe: {plain_text!r}"
        )

        # AC-1: Kompaktformat (compact.py)
        compact_field = _compact_thunder_field(tok, stage)
        assert compact_field == f"⚡{deutsches_wort}", (
            f"Kompaktformat zeigt bei thunder={level!r} nicht "
            f"'⚡{deutsches_wort}', erhalten {compact_field!r}"
        )

        # AC-1: Telegram/SMS-Trendblock (narrow.py)
        telegram_text = "\n".join(_outlook_lines([stage]))
        assert f"⚡{deutsches_wort}" in telegram_text, (
            f"Telegram-Trendblock zeigt bei thunder={level!r} nicht "
            f"'⚡{deutsches_wort}'. Ausgabe: {telegram_text!r}"
        )
        assert level not in telegram_text, (
            f"Telegram-Trendblock zeigt bei thunder={level!r} noch das "
            f"englische Wort {level!r}. Ausgabe: {telegram_text!r}"
        )


# ────────── AC-2 (Positivkontrolle): "day"-Zweig bleibt unveraendert ────────

def test_ac2_positivkontrolle_day_zweig_unveraendert():
    """Bewusst KEIN RED-Test -- Gegenprobe, dass der tokenbasierte 'day'-Zweig
    von dieser Scheibe nicht angefasst wird. Muss vor UND nach der
    Implementierung gruen bleiben.
    """
    from output.renderers.email.helpers import format_trend_tokens
    from output.renderers.email.outlook import render_outlook_plain
    from output.renderers.email.thunder_branch import resolve_thunder_day_branch
    from output.tokens.dto import HourlyValue

    stage = dict(
        weekday="Di", name="Etappe Tagesgewitter", temp_lo=10, temp_hi=18,
        precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="HIGH", note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        # 12 Uhr liegt im Tagesfenster (4-19, day_window.py); Stufe 2 = "mittel"
        # in _TREND_THUNDER_LABELS.
        hourly_thunder=(HourlyValue(hour=12, value=2.0),),
    )
    tok = format_trend_tokens(stage)
    branch = resolve_thunder_day_branch(tok, stage)
    assert branch == "day", (
        f"Testaufbau fehlerhaft -- Positivkontrolle braucht den 'day'-Zweig, "
        f"erhalten {branch!r}."
    )
    assert tok["thunder_day_token"] != "-"

    plain_text = render_outlook_plain([stage])
    assert "mittel" in plain_text, (
        f"Der 'day'-Zweig muss unveraendert das Tageswort aus dem Token "
        f"zeigen (nicht aus _THUNDER_MAP). Ausgabe: {plain_text!r}"
    )


# ────────── AC-5: tote Felder restlos entfernt ──────────────────────────────

def test_ac5_tote_felder_entfernt():
    from output.renderers.email.helpers import format_trend_tokens

    tokens = format_trend_tokens(_stage_ohne_stundenreihe("HIGH"))
    tote_felder = {"thunder_sms", "thunder_sq_color", "thunder_word_color"}
    vorhanden = tote_felder & tokens.keys()
    assert not vorhanden, (
        f"format_trend_tokens() liefert noch tote Felder: {vorhanden}. "
        f"AC-5 verlangt, dass sie entfernt sind."
    )
