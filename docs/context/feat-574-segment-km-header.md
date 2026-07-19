# Context: feat-574-segment-km-header

## Request Summary
Feature #574 (PO-bestätigt via #1310): Kumulativer km-Bereich („km 0.0–4.2") in den Segment-Überschriften der HTML-Briefing-Mail. Plain-Text rendert das seit `320e9fac` korrekt — es fehlen Desktop- und Mobile-HTML-Header. 3 xfail-Tests definieren das Soll exakt.

## Soll (tests/tdd/test_feature_574_segment_km_header.py — 3 passed, 3 xfail, verifiziert)
| Test | Pfad | Assertion |
|---|---|---|
| AC-2a html_normal_segment (xfail) | render_html Desktop-Header | `"km 0.0–4.2" in result` (En-Dash, eine Nachkommastelle inkl. .0) |
| AC-2b html_destination_no_km (xfail) | render_html Ziel-Block | Ziel-Block ohne `km \d.\d`; Test-Anker `"Wetter am Ziel"` matcht seit #956 nicht mehr (Renderer: „WETTER AM ZIEL", Uppercase) → 1-Zeilen-Testanpassung nötig, unabhängig vom Feature |
| AC-3 mobile_compact_header (xfail) | render_html `class="mobile-compact"` | `"km 0.0–4.2"` in den ersten 500 Zeichen des Blocks |
| AC-1 plain ×2 + AC-4 (passed) | render_plain | bereits live seit 320e9fac |

## Ist (file:line)
- **html.py:1034** Desktop: `{seg_time} · {_from_km:.1f} km - {_to_km:.1f} km · …` — Daten (kumulierte Laufsumme `_from_km`/`_to_km`, html.py:948-956) sind DA, nur das Format weicht ab.
- **html.py:1054** Mobile: `SEG {seg_id} · {seg_time}` — gar kein km.
- **html.py:970-1015** Ziel-Block: strukturell korrekt ohne km.
- **plain.py:222** Vorbild-Format (Inline-f-String).
- helpers.py:901-935 `build_segment_label` ist ANDERER Baustein (Alert-/Change-Zeilen, strippt `.0`) — nicht wiederverwendbar; Konsolidierung stattdessen über NEUE kleine Hilfsfunktion.

## Design (minimal + Konsolidierungs-Gebot)
Neue geteilte Hilfsfunktion `_km_range(from_km, to_km) -> "km {:.1f}–{:.1f}"` in helpers.py (~3 LoC); drei Call-Sites: html.py:1034 (Format-Tausch), html.py:1054 (km ergänzen), plain.py:222 (Inline-String ersetzen — Verhalten identisch). Plus 1-Zeilen-Test-Anker-Fix (case: „WETTER AM ZIEL" bzw. case-insensitiv). Gesamt ~10-14 LoC.

## Existing Patterns
- Datenquelle bleibt die #956-kumulierte `distance_km`-Laufsumme (kein Modellwechsel).
- Golden-Refreeze-Prozess aus #1306 frisch erprobt (`tests/golden/email/regenerate.py`).

## Dependencies
- Downstream: 5 Golden-HTML-Fixtures brechen erwartbar (enthalten altes `X.X km - Y.Y km`; Mobile-Block ohne km) → einmalig regenerieren, Diff darf NUR km-Zeilen zeigen (keine #1306-Regression). Plain-Goldens unberührt.
- briefing_mail_validator: keine Kollision (Heuristiken matchen `km 0.0–4.2` nicht als Stunde/Temperatur — geprüft).
- #1306-Eyebrow/h1 (html.py:879-935): strukturell getrennt, keine Code-Kollision.
- Renderer-Mail-Gate #811 greift (html.py = Mail-Inhalts-Datei): mode_matrix + frischer Validator-Lauf mit echter Mail vor Commit.

## Existing Specs
- `docs/specs/modules/feature_574_segment_km_header.md` existiert NICHT (toter Docstring-Link; nie angelegt).
- `docs/specs/modules/issue_956_email_format.md` (draft) schrieb das heutige `X.X km - Y.Y km` fest → **ADR nötig:** #574-Format ersetzt das #956-Segment-Header-Format bewusst (PO-Entscheid #1310); Datenmodell unverändert.

## Risks & Considerations
- Zweites Golden-Refreeze kurz nach #1306 — Diff-Review strikt auf km-Zeilen begrenzen.
- Parallel-Sessions pushen laufend (3 Commits hinter origin/main bei Workflow-Start) — vor Commit fetch+ff.
- Kein Anfassen von helpers.py:build_segment_label (Alert-Pfad #397/#816/#832).
