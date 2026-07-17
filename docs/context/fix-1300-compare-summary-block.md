# Context: fix-1300-compare-summary-block

**Issue:** #1300 — Ortsvergleich-Mail: Ort-Zusammenfassungs-Sätze unter der Matrix ersatzlos entfernen (Rückbau #1278)
**Typ:** Rework / Rückbau nach PO-Entscheid
**Erstellt:** 2026-07-17
**Basis:** `origin/main` @ `080e96d8`

## Request Summary

Der PO hat am 2026-07-17 entschieden: Die mit #1278 (`cb9918b0`, jüngster Commit auf `main`) eingeführte Kurz-Zusammenfassung je Ort unter der Vergleichs-Matrix soll **ersatzlos** aus der Ortsvergleichs-E-Mail verschwinden — „kein Mehrwert". Sie wiederholt in Prosa, was die Matrix direkt darüber als Zahlen zeigt.

Wörtlich beanstandeter Output:
```
Bormes Les Mimosas: 22–31°C, trocken, mäßiger Wind 17 km/h, Böen bis 34 km/h ab 16:00
Camp du Domaine: 23–32°C, trocken, mäßiger Wind 22 km/h, Böen bis 41 km/h ab 17:00
…
```

## Scope: zwei Fundstellen, dieselbe Mail

Der Satz steht an **zwei** Stellen — beide sind „die Ortsvergleichs-E-Mail" (HTML- und Text-Teil derselben multipart-Nachricht), beide stammen aus #1278:

| # | Fundstelle | Rolle |
|---|---|---|
| 1 | `src/output/renderers/email/compare_html.py:483-501` (`_render_summary_block`), Aufruf `:966`, Einbau in Blockfolge `:990` | **HTML-Teil** der Mail |
| 2 | `src/output/renderers/comparison.py:165-172` (Block in `render_comparison_text`) | **Text-Teil** der Mail — `render_comparison_text` wird von `render_compare_email:244` als `text_body` genutzt |

Der Kommentar an Fundstelle 2 bestätigt die Absicht der Doppelung: „Issue #1278: Kurz-Zusammenfassung je Ort … an der zum HTML analogen Stelle, wortgleich, weil derselbe geteilte Trip-Baustein den Satz erzeugt."

**Nicht betroffen:** `render_compare_telegram` (`comparison.py:320`) und `render_compare_sms` (`:428`) bauen ihre Ausgabe eigenständig auf und rufen `render_comparison_text` **nicht** auf (verifiziert: einziger Aufrufer ist `:244`). Telegram und SMS zeigen den Satz nicht — kein Handlungsbedarf, kein Scope-Creep.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | Fundstelle 1. **Renderer-Commit-Gate #811 greift** (Datei ist gate-pflichtig) |
| `src/output/renderers/comparison.py` | Fundstelle 2 (Text-Teil) |
| `src/output/renderers/compact_summary.py:423` (`format_location_summary`) | **Nur Aufrufer entfernen, Datei NICHT anfassen** — geteilter Trip-Baustein |
| `src/services/report_config_resolver.py:166-231` | `resolve_compare_render_options` — unverändert, `enabled_metrics` wird weiter für die Matrix gebraucht |

## Risks & Considerations

### RISIKO 1 (hoch): `_daily_summary` / `summaries` NICHT mitreißen

Die naheliegende Annahme „die Summary-Vorberechnung fällt mit dem Summary-Block weg" ist **falsch** und würde eine #1285-Regression erzeugen.

`summaries` (`compare_html.py:464-469`) speist die **Matrix**, nicht den Summary-Block:
```python
# :407
value = None if loc.error is not None else _metric_value(loc, m["key"], summaries.get(id(loc)))
```
`_daily_summary` (`:349`) ist die Live-Ableitung, aus der laut `:343` fünf Matrix-Metriken „ausschliesslich" ihren Wert beziehen — genau die fünf, die #1285 repariert hat (`comparison.py:48` verweist auf dieselbe Kette).

→ **`_daily_summary`, die `summaries`-Vorberechnung und der `summaries`-Parameter von `_render_overview_table`/`_render_overview_row` bleiben unverändert.** Entfernt wird ausschließlich `_render_summary_block` und dessen Aufruf.

### RISIKO 2 (hoch): `format_location_summary` / `CompactSummaryFormatter` nicht löschen

Geteilter Trip-Baustein (`compact_summary.py:423`). Der Trip-Pfad braucht ihn weiter. Entfernt wird nur der **Import + Aufruf** in den beiden Compare-Fundstellen, nicht der Formulierer.

Berührt die Trip/Compare-Teilungs-Invariante (CLAUDE.md) **nicht**: Es wird kein geteilter Baustein dupliziert oder ersetzt, sondern eine Platzierung zurückgenommen.

### RISIKO 3: Renderer-Commit-Gate #811

`src/output/renderers/email/compare_html.py` ist gate-pflichtig. Vor dem Commit müssen im aktiven Workflow **frisch** vorliegen:
1. `tests/tdd/test_issue_811_mode_matrix.py` grün
2. erfolgreicher `briefing_mail_validator.py`-Lauf

Für die **Compare**-Mail ist der fachlich zuständige Validator dagegen `.claude/hooks/email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`) — der Briefing-Validator ist der Trip-Pfad. Beide Anforderungen sind zu bedienen: #811 als Commit-Gate, `email_spec_validator.py` als fachlicher Nachweis vor „E2E bestanden".

### RISIKO 4: Leerraum-Reste

Fundstelle 2 hängt an einem `lines.append("")`-Muster. Beim Entfernen darf keine doppelte Leerzeile zwischen Orts-Übersicht und „STUNDENVERLAUF" zurückbleiben. Fundstelle 1: `summary_html` muss aus der Block-Tuple `:990` entfernt werden, nicht nur auf `""` gesetzt.

### RISIKO 5: Bestehende #1278-Tests

Tests, die die Anwesenheit der Sätze prüfen (AC-9-Anti-Erosion aus #1278), werden durch den Rückbau rot. Sie prüfen dann überholtes Verhalten und sind zu **löschen**, nicht zu reparieren (Test-Politik: „sofort fixen ODER löschen, wenn er veraltetes Verhalten prüft"). Vor der RED-Phase zu identifizieren.

## Existing Patterns

- **Rückbau-Vorbild #1268/#1278:** Tote Anzeige ersatzlos entfernen, Persistenz-Felder aber erhalten (`compareEditorSave.ts:130-132`). Hier ist **kein** Persistenz-Feld betroffen — der Block war nie konfigurierbar, er hing an `active_metrics`. Nichts zu erhalten.
- **Blockfolge-Muster:** `compare_html.py:983-990` fügt die Blöcke als Tuple in fester Reihenfolge zusammen — sauberer Ausbau-Punkt.

## Dependencies

- **Upstream:** `format_location_summary` ← `CompactSummaryFormatter.format_weather_summary` (bleibt)
- **Downstream:** `render_compare_email` (`comparison.py:196`) und `render_compare_html` — beide von `scheduler_dispatch_service.py:317` (Versand) und `compare_preview_service.py:166` (Vorschau) genutzt. Der Rückbau wirkt auf **Versand und Vorschau gleichermaßen** — beide müssen den Block danach nicht mehr zeigen (kein Preview/Versand-Divergenz-Risiko wie #1297).

## Existing Specs

- `docs/specs/modules/issue_1110_compare_mail_v2.md` — v2-Vertrag der Compare-Mail (Neutralität, kein Score)
- #1278-Spec — der Vorgang, der hier zurückgebaut wird

## Nebenwirkung (kein eigener Scope)

Der Wegfall entzieht der Layout-Tab-Gruppe „Im Briefing als Detail" ihr letztes Ziel — sie hat ohnehin nie gewirkt (schreibt nach `display_config.channel_layouts`, was der Compare-Renderpfad nie liest). Das ist Gegenstand von **#1299**, nicht dieser Scheibe. Diese Scheibe fasst **kein Frontend** an.

## Nachweis-Anforderung

Test gegen die **echte Render-Ausgabe** (kein Dateiinhalt-Check): Vergleichs-Mail mit mehreren Orten rendern, rot solange die Zusammenfassungs-Sätze erscheinen — für **beide** Fundstellen (HTML und Text).
