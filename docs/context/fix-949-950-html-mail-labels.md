# Context: #949 + #950 — HTML-Mail-Renderer Test-Staleness

## Request Summary

Zwei fehlschlagende Unit-Tests wurden als Nebenbefund bei #944 entdeckt:
- `test_html_contains_ziel_label` (#949): erwartet `"Ziel"` (mixed case) in `email_html`
- `test_structural_columns_always_visible` (#950): erwartet exakt `"<th>Time</th>"` in `email_html`

## Root-Cause-Befund (verifiziert per echtem Renderer-Aufruf, kein Mock)

Beide sind **keine Renderer-Defekte**, sondern **veraltete Testerwartungen** — dasselbe
Muster wie die bereits geschlossenen Stale-Test-Issues #926/#867/#820/#797/#815/#625:

### #949 — "Ziel"-Label
`src/output/renderers/email/html.py:875-892` rendert die Ziel-Sektion seit Commit
`38f8f935` (#884, "Mail-Fidelity 1:1 — neues HTML-Briefing-Layout") mit **Großbuchstaben**:
`"ANKUNFT · WETTER AM ZIEL"` / `"WETTER AM ZIEL"`. Der Test (`assert "Ziel" in html`,
Python case-sensitive) prüft die **mixed-case** Schreibweise, die seit der #884-Umstellung
auf Uppercase-Eyebrow/-Headline nirgends mehr vorkommt. Live-Verifikation:
`"Ziel" in html` → `False`, `"ZIEL" in html` → `True`.

Der Test stammt aus der ursprünglichen BUG-01-Implementierung (Commit `889b53d2`, lange vor
#884) und wurde bei der #884-Redesign nicht auf die neue Schreibweise angepasst.

### #950 — `<th>Time</th>`
`src/output/renderers/email/html.py:483` rendert seit Commit `d11b25b7`
(#911, "Briefing-Mail Detail-Korrekturen — 13 ACs") den Time-Header mit **Inline-Style**
(Outlook-Kompatibilität, AC-1/AC-4 aus #911): `<th style="...">Time</th>` statt
`<th>Time</th>`. Die Spalte ist strukturell **immer vorhanden** (bare `<th>Time</th>`
existiert nur noch im Leer-Zeilen-Fallback derselben Funktion, Zeile 460 — nicht im
Hauptpfad). Live-Verifikation: `"<th>Time</th>" in html` → `False`,
`">Time<" in html` → `True`.

## Design-Autorität

Beide Änderungen (#884 Uppercase-Redesign, #911 Inline-Style für Outlook) sind
JSX-validierte, PO-freigegebene Design-Fidelity-Arbeit (siehe CLAUDE.md
"JSX ist IMMER die Wahrheit" / "Design-Fidelity 1:1"). Der Renderer-Code ist korrekt —
**die Tests müssen an die aktuelle, freigegebene Darstellung angepasst werden**, nicht
umgekehrt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py` | Enthält beide betroffenen Render-Pfade (Ziel-Sektion Z.875ff, Tabellen-Header Z.448-486) — WIRD NICHT GEÄNDERT |
| `tests/unit/test_destination_segment.py` | `test_html_contains_ziel_label` (Z.128) — wird angepasst |
| `tests/unit/test_trip_report_formatter.py` | `test_structural_columns_always_visible` (Z.190ff) — wird angepasst |

## Konsequenz für Scope

Da NUR Testdateien geändert werden (kein `src/output/renderers/email/*.py`), greift das
Renderer-Commit-Gate (`renderer_mail_gate.py`) **nicht** — es reagiert ausschließlich auf
gestagte Mail-Inhalts-Dateien. Kein Mode-Matrix-Test, kein `briefing_mail_validator.py`-Lauf
nötig, da keine Mail-Ausgabe sich ändert.

## Risks & Considerations

- Sicherstellen, dass die neuen Assertions weiterhin echtes Verhalten prüfen (nicht
  vacuous) — z.B. `"ZIEL" in html.upper()` bzw. `"WETTER AM ZIEL" in html` für #949,
  `">Time<" in html` oder Regex auf `<th[^>]*>Time</th>` für #950.
- Kontrollprobe: Assertion muss bei einem hypothetisch fehlenden Ziel-Label/Time-Header
  tatsächlich rot werden (keine Tautologie).
