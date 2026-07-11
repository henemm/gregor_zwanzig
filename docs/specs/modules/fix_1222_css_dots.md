---
entity_id: fix_1222_css_dots
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [email, renderer, ampel, design]
---

# Fix #1222 — Gestylte CSS-Dots statt Kreis-Emojis in E-Mails

## Approval

- [ ] Approved

## Purpose

In allen E-Mails (Trip-Briefings UND Alert-Mails) dürfen die Kreis-Emojis
🟢🟡🟠🔴 nicht mehr erscheinen. Im HTML werden sie durch gestylte CSS-Dots
(farbiger Kreis mit hellem Ring, Claude-Design-Vorlage/RICHTIG) ersetzt; im
reinen Text werden sie ersatzlos entfernt. Wetter-Symbole (☀️⛅⚡) sind NICHT
betroffen.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `ampel_dot`, `ampel_stage_index`, `tone_symbol`, `AMPEL_LEGEND`
- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `_LEVEL_WORDS`, `render_official_alert_notice_plain`
- **File:** `src/output/renderers/email/plain.py` (Plain-Pills)
- Referenz-Vorbild (RICHTIG): `src/output/renderers/email/html.py::_risk_dot`

## Estimated Scope

- **LoC:** ~+55 / −30
- **Files:** 3 Kern (`helpers.py`, `official_alerts.py`, `plain.py`) + Tests; optional Cleanup `trip_report.py`
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_level_from_thresholds()` (helpers.py) | intern | Entkoppelt `ampel_stage_index` vom Emoji-Lookup |
| `_risk_dot()` (html.py) | Design-Referenz | Vorbild für Ring-Optik (box-shadow) |
| Renderer-Gate #811 | Gate | `test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` müssen grün sein |

## Implementation Details

```
1. Neuer Helper _ampel_dot_css(level) in helpers.py:
   - liefert <span style="display:inline-block;width:10px;height:10px;
     border-radius:50%;background:{fill};box-shadow:0 0 0 3px {ring};"></span>
   - 4 Stufen green|yellow|orange|red, Palette an _risk_dot angelehnt,
     um Gelb/Amber erweitert (Fill saturiert, Ring helle rgba-Variante).

2. ampel_dot(value, thresholds):
   - nutzt _level_from_thresholds(); None -> "–"
   - gibt _ampel_dot_css(level) zurück (statt Emoji).

3. ampel_stage_index(value, thresholds):
   - Umstellung auf ("green","yellow","orange","red").index(_level_from_thresholds(...))
     ODER direkte Level->Index-Map. KEIN Emoji-.index() mehr.
   - ampel_stage_tone / Pill-Farben bleiben unverändert.

4. tone_symbol(tone): liefert "" (kein Emoji-Marker mehr) — Plain-Pills tragen
   nur noch das Label.

5. official_alerts.py render_official_alert_notice_plain: Emoji-Präfix entfernen,
   Zeile beginnt mit dem Schwere-Wort (GRÜN/GELB/ORANGE/ROT). _LEVEL_WORDS auf
   reine Wörter reduzieren.

6. Tote Emoji-Reste entfernen: AMPEL_LEGEND (helpers.py, im Live-HTML ungenutzt),
   Emoji-Zweig in trip_report.py::_fmt_val (toter _render_html_table-Pfad).
```

## Expected Behavior

- **Input:** Trip-Briefing- oder Alert-Mail-Rendering mit Ampel-Metriken.
- **Output:** HTML-Zellen enthalten CSS-Dot-`<span>` (border-radius:50% + box-shadow-Ring);
  Plain-Text ohne Kreis-Emoji.
- **Side effects:** Keine — Schwellenlogik, Pill-Farben und Zell-Tönung unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Briefing mit Ampel-Metrik (z.B. CAPE über Gelb-Schwelle)
  / When die HTML-Mail gerendert wird / Then enthält die betreffende Tabellenzelle
  einen CSS-Dot (`border-radius:50%` mit `box-shadow`-Ring) und **kein** Emoji-Zeichen
  aus 🟢🟡🟠🔴.
  - Test: HTML-Renderer für eine Stundenzeile mit Ampel-Wert aufrufen, prüfen dass
    Ausgabe `border-radius:50%` enthält und keines der vier Kreis-Emojis.

- **AC-2:** Given verschiedene Metrikwerte über allen vier Schwellenbändern
  / When die HTML-Mail gerendert wird / Then zeigt der Dot je Band die korrekte
  Farbe (green/yellow/orange/red), passend zur bestehenden Zell-Tönung und
  Pill-Farbe (kein Widerspruch zwischen Dot-Farbe und Hintergrund).
  - Test: `ampel_dot` + `ampel_stage_tone` für Werte je Band aufrufen, Farb-Konsistenz
    (Dot-Level == Tönungs-Level) beweisen.

- **AC-3:** Given eine amtliche Warnung / When die **Plain-Text**-Alert-Notice
  gerendert wird / Then beginnt die Zeile mit dem Schwere-Wort (z.B. „ROT — …")
  und enthält **kein** Kreis-Emoji.
  - Test: `render_official_alert_notice_plain` mit Level-4-Alert aufrufen, prüfen
    dass Ausgabe „ROT" enthält und keines der vier Kreis-Emojis.

- **AC-4:** Given der Metriken-Überblick im **Plain-Text**-Briefing / When gerendert
  / Then enthält keine Pill-Zeile ein Kreis-Emoji.
  - Test: Plain-Renderer für ein Briefing mit Ampel-Pills aufrufen, prüfen dass
    Ausgabe keines der vier Kreis-Emojis enthält.

- **AC-5:** Given der gesamte gerenderte E-Mail-Korpus (HTML + Plain, Trip + Alert)
  / When gerendert / Then taucht **keines** der Zeichen 🟢🟡🟠🔴 mehr in der Ausgabe
  auf, während Wetter-Symbole (☀️⛅⚡) unverändert erhalten bleiben.
  - Test: Repräsentative HTML- und Plain-Mail rendern, Assertion auf Abwesenheit der
    vier Kreis-Emojis; separat prüfen dass ein Wetter-Symbol (⚡) noch vorhanden sein
    kann.

- **AC-6:** Given ein Nutzer antwortet **per E-Mail** mit einem Gewitter-/Stunden-
  Drilldown-Kommando (`dd_thunder_*`, `dd_hours_*`) / When die Bestätigungsmail
  gerendert wird / Then enthält der Text kein Kreis-Emoji (🟡🔴⚪), sondern das Wort
  (keins/mäßig/hoch). Für **Telegram** bleibt die Emoji-Darstellung unverändert
  (kanal-abhängiges Rendern; #654 unberührt).
  - Test: `process()` mit `channel="email"` für einen `dd_hours_*`/`dd_thunder_*`-
    Befehl → Body ohne Kreis-Emoji, mit Wort; `channel="telegram"` → Body mit Emoji.

## Was darf sich NICHT ändern (Invarianten)

- Schwellenwert-Logik (`_level_from_thresholds`, display_thresholds) unverändert.
- Pill-Farben (`ampel_stage_tone`/`_AMPEL_STAGE_COLORS`) und Zell-Tönung unverändert.
- HTML-Alert-Badge (Farb-Border) unverändert — nutzt bereits keine Emojis.
- Wetter-Symbole (Wolken/Blitz) unverändert.
- Renderer-Gate #811 muss grün bleiben.

## Nebenbefunde
- Toter Emoji-Code in `trip_report.py` (`_fmt_val`/`_render_html_table` ohne Aufrufer)
  wird im Zuge dieses Fixes mit-bereinigt (kein separates Issue nötig).
