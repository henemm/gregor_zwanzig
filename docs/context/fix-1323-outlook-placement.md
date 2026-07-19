# Context: fix-1323-outlook-placement

## Request Summary
Der 3-Tage-Ausblick je Ort (Epic #1301 B4) erscheint in der Ortsvergleich-Mail als **gesammelter Block am Ende** (hinter allen Stundentabellen). Er soll stattdessen **je Ort direkt unter dessen Stundentabelle** stehen — Ort für Ort zusammenhängend lesbar. PO-Entscheidung 2026-07-19, Issue #1323.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py` | **HTML-Pfad.** `render_comparison_html` baut `hourly_sections_html` (Zeile ~1025, join `_render_location_section` je Ort) und `outlook_sections_html` (Zeile ~1036, join `_render_location_outlook` je Ort) **getrennt**; `body_html` (Zeile ~1047) reiht sie als zwei Blöcke: `hourly_head, hourly_sections, outlook_head, outlook_sections`. Hier liegt die Kernänderung. |
| `src/output/renderers/comparison.py` | **Klartext-Pfad.** Zeile 186–198: `if outlook_enabled:` sammelt alle Orts-Ausblicke **nach** den Stundentabellen (`render_outlook_plain` je Ort in einer eigenen Schleife). Muss analog je Ort verschachtelt werden — sonst driften HTML- und Text-Mail auseinander. |
| `src/output/renderers/email/outlook.py` | Geteilter Ausblick-Renderer (`render_outlook_table` / `render_outlook_plain` / `build_outlook_row`), Trip+Compare. **Bleibt unverändert** — nur die Platzierung im Compare-HTML/-Text ändert sich, nicht der Tabellen-Renderer selbst. |
| `tests/tdd/test_compare_outlook.py` | Prüft Compare-Ausblick (AC-5/AC-8/AC-9). Reihenfolge-/Platzierungs-Assertions hier anpassen bzw. neuen Platzierungs-Test ergänzen. |
| `tests/tdd/test_shared_outlook_renderer.py` | Prüft den geteilten Renderer — darf grün bleiben (Renderer unverändert). Regressionsschutz. |

## Existing Patterns
- **Per-Ort-Section (HTML):** `_render_location_section(loc, i, hourly_metrics, corridors)` (Zeile 613) rendert je Ort eine Stundentabelle; `_render_location_outlook(loc, index)` (Zeile 685) je Ort eine Ausblick-Tabelle. Beide sind bereits pro Ort aufrufbar — die Umstellung führt sie in **einer** Per-Ort-Schleife zusammen, statt zwei getrennte Joins.
- **Anti-Erosion beim Body-Zusammenbau:** `body_html = "\n".join(part for part in (...) if part)` — leere Blöcke werden herausgefiltert. Muss beim Verschachteln erhalten bleiben (kein leerer Ausblick, wenn `outlook_hourly_data` fehlt — `_render_location_outlook` liefert dann `""`).
- **Section-Heads:** Heute je ein Sammel-Head „STUNDEN · Stundenverlauf · alle Orte" und „AUSBLICK · 3-Tage-Ausblick · alle Orte". Bei Verschachtelung je Ort ist ein gesammelter „AUSBLICK"-Head nicht mehr passend — Platzierung/Beschriftung neu entscheiden (Design-Frage für die Spec).

## Dependencies
- **Upstream:** `outlook_enabled` (bool) fließt über `report_config_resolver.py` (Default True) → `scheduler_dispatch_service.py` / `compare_preview_service.py` → `render_comparison_html` / Klartext-Renderer. `outlook_hourly_data` je `LocationResult` wird in `comparison_engine.py` befüllt (bis 3 Kalendertage, 96h-Fetch).
- **Downstream:** Compare-Mail (HTML + Klartext), Vorschau (`compare_preview_service`). Renderer-Commit-Gate **#811** greift bei Edit an `compare_html.py`.

## Existing Specs
- `docs/specs/modules/epic_1301_b4_compare_outlook.md` — B4-Spec (Ausblick eingeführt). Die Platzierungs-Änderung ist die direkte Folgekorrektur.

## Risks & Considerations
- **Zwei Renderer synchron halten:** HTML **und** Klartext müssen dieselbe Verschachtelung bekommen, sonst weichen die Mail-Formate voneinander ab. Verifikation gegen echte Staging-Mail in **beiden** Formaten.
- **Edge-Case `hourly_enabled=False` + `outlook_enabled=True`:** Ohne Stundentabelle gibt es nichts, „worunter" der Ausblick steht — der Ausblick muss trotzdem je Ort gruppiert erscheinen. Die Per-Ort-Schleife muss beide Bausteine unabhängig behandeln.
- **Reihenfolge-Konsistenz:** Orte-Reihenfolge (= Spaltenreihenfolge der Übersicht) muss in der verschachtelten Ausgabe identisch bleiben.
- **Renderer-Gate #811:** Test-Mails + `briefing_mail_validator.py` (Exit 0) vor Commit Pflicht.
- **Geteilter Renderer nicht anfassen:** Die Änderung ist reine Platzierung/Orchestrierung im Compare-Pfad; `outlook.py` bleibt byte-stabil (Trip-Pfad darf sich nicht ändern).

## Analysis

### Type
Bug (nutzersichtbare Fehlplatzierung eines ausgelieferten Features).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | Stundentabelle + Ausblick je Ort in **einer** Per-Ort-Schleife zusammenführen statt zwei getrennter Joins; gesammelten „AUSBLICK"-Sammel-Head auflösen. |
| `src/output/renderers/comparison.py` | MODIFY | Klartext-Pfad analog: Ausblick je Ort direkt nach dessen Stundenblock statt gesammelt am Ende (Zeile 186–198). |
| `tests/tdd/test_compare_outlook.py` | MODIFY | Platzierungs-/Reihenfolge-Assertion: Ausblick jedes Orts steht **zwischen** dessen Stundentabelle und der nächsten Ort-Sektion (nicht am Mail-Ende). |

### Scope Assessment
- Files: 2 Quell- + 1 Testdatei
- Estimated LoC: +50 / −30
- Risk Level: MEDIUM (Compare-Mail-Ausgabe HTML+Text, Renderer-Gate #811)

### Technical Approach (Tech-Lead-Entscheid)
Eine gemeinsame Per-Ort-Schleife über `locations` (Reihenfolge = Übersichts-Spalten) baut je Ort: (1) Stundentabelle `_render_location_section` **falls** `hourly_enabled`, (2) direkt darunter `_render_location_outlook` **falls** `outlook_enabled`. Beide Bausteine sind bereits pro Ort aufrufbar — es entfällt der zweite Sammel-Join `outlook_sections_html`. Der Sammel-Head „AUSBLICK · alle Orte" wird aufgelöst; der Ausblick erhält je Ort seine bestehende Kopfzeile (`_render_location_outlook`-Header). Klartext-Pfad (`comparison.py`) identisch verschachteln. Anti-Erosion-Filter (`if part`) und fail-soft (leeres `outlook_hourly_data` → `""`) bleiben erhalten.

### Dependencies
`outlook.py` (geteilter Renderer) bleibt unverändert. `outlook_enabled`/`hourly_enabled` sind unabhängige Bools — die Schleife behandelt jeden Baustein einzeln, damit „Ausblick an, Stundenverlauf aus" je Ort korrekt greift.

### Open Questions
- [ ] Beschriftung der verschachtelten Ausblick-Tabelle je Ort — Tech-Lead-Vorschlag geht in die Spec-ACs zur PO-Freigabe (kleine „Ausblick nächste Tage"-Zeile je Ort statt Sammel-Head).
