# Context: fix-1861-1865-alarm-mail-klarheit

## Request Summary
Zwei PO-Bug-Reports (heute, 2026-08-15) zur Abweichungs-Alarm-Mail (`deviation-alert`): (#1861) bei mehreren Ereignissen derselben Metrik sind die Zeilen ununterscheidbar ("Gewitter · Schwelle 1" 3×); (#1865) die Datenblock-Zeile "Alarm-Schwelle 1 / Änderung über ✗" ist ein unverständliches Textfragment.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py` | Zentrale Renderer-Funktionen für beide Bugs: `_datablock_single` (Zeile 375-400, #1865-Fragment), Multi-Event-Zweig in `render_email` (Zeile 492-531, #1861-Ununterscheidbarkeit), `_h1`/`render_subject` (Betreff-Wortlaut) |
| `src/output/renderers/alert/model.py` | `AlertEvent` trägt bereits `occurred_at`, `km_from`/`km_to`, `segment_id` (Zeile 12-33) — Differenzierungs-Daten sind vorhanden, werden im Multi-Zweig nur nicht gerendert. `over_thr`/`side_label` (Zeile 110-119) — Kern der #958-Korrektur, NICHT anfassen |
| `src/output/renderers/alert/project.py` | `to_alert_message()` befüllt `segment_id`/`km_from`/`km_to` je Event aus dem passenden Segment (Zeile 66-99) — Quelle für den #1861-Differenzierer |
| `src/services/notification_service.py`, `radar_alert_service.py`, `validator_render_service.py` | Aufrufer von `render_email`/`render_subject`/`render_telegram` — reine Konsumenten, keine eigene Wortlaut-Logik |
| `tests/tdd/test_alert_bundle_958ff.py` (Zeile 123-150) | Fixiert AC-2 aus #958: exakt der jetzt bemängelte Text `"Änderung über ✗"` — **muss beim Fix mitgezogen werden**, nicht einfach gelöscht |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` (Zeile 750-765) | Weitere Fixierung derselben Wortlaute für den Compare-Alarm-Pfad (nutzt denselben Renderer) |
| `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html` | Original-Design-Vorlage (Claude Design). Zeigt Row2-Muster `"Alarm-Schwelle 800" / "jetzt darunter ✓"` als vollständigen Satz — Vorlage deckt den Multi-Event-Gleichname-Fall (#1861) NICHT ab |

## Existing Patterns
- **Single-Event-Datenblock** (`_datablock_single`) hat bereits eine 3. Zeile "Wo & wann" mit `_location_of((e,), location_label)` + `occurred_at` — genau dieses Muster fehlt im Multi-Event-Zweig.
- **Reihenfolge nach Schwere** (Issue #978): Multi-Event-Zeilen sind bereits nach `severity()` sortiert (`_sorted(msg)`) — reine Text-Ergänzung ändert die Sortierung nicht.
- Betreff-Kurzform (`_sms_subject`/render_telegram) hat dasselbe Ununterscheidbarkeits-Problem wie #1861 (KHW-SMS "TH1 TH0 TH0" aus dem Issue-Text) — Scope-Frage für Analyse: nur E-Mail oder auch SMS/Telegram?

## Dependencies
- Upstream: `AlertEvent`/`AlertMessage` (model.py), `get_metric()` (Katalog für Einheit), `segments.format_alert_location` (Ortssprache, s. #1744)
- Downstream: E-Mail (Trip + Compare via `to_multi_point_alert_message`), Telegram, SMS — alle vier Renderer-Funktionen (`render_subject/email/telegram/sms`) sind kanal-konsistent (Issue #978-Vorgabe); Wortlautänderung an einer Stelle zieht ggf. Konsistenz-Erwartung an den anderen Kanälen nach sich

## Existing Specs
- Kein dediziertes Entity-Spec für `alert/render.py` gefunden; Design-Referenz ist die o.g. Claude-Design-Vorlage + `docs/adr/` (ADR-0011 kanonisches AlertMessage-Modell, s. Docstring model.py)

## Risks & Considerations
- **#958-Regressionsgefahr:** Die aktuell bemängelte Zeile "Änderung über ✗" wurde in #958 GEZIELT eingeführt, um einen semantischen Bug zu fixen (`über`/`unter` verglich bei Δ-Metriken fälschlich Absolutwert mit Δ-Schwelle — bei steigender Nullgradgrenze stand dort "unter"). Der Fix darf NICHT zur alten Absolutwert-Semantik zurück, sondern muss nur den TEXT der bereits korrekten `side_label()`/`over_thr()`-Werte verständlicher fassen.
- **Gebundene Tests:** `test_alert_bundle_958ff.py` und `test_issue_1169_compare_alert_consumer.py` fixieren den exakten aktuellen Wortlaut — beide müssen im selben Workflow aktualisiert werden, sonst bricht `touched_tests_gate.py`.
- **Renderer-Commit-Gate (#811):** `alert/render.py` ist eine Mail-Inhalts-Datei → Commit erfordert grünen `test_issue_811_mode_matrix.py` + erfolgreichen `briefing_mail_validator.py`-Lauf (bzw. den für Alarm-Mails zuständigen Validator prüfen — laut Memory ist `radar_alert_mail_validator` für `mail_type="official-alert"` ein No-Op; für `"deviation-alert"` muss das in der Analyse-Phase verifiziert werden).
- **#1861-Differenzierer offen:** Model hat `occurred_at` (nur HH:MM, kein Datum) und `segment_id`/`km_from`/`km_to`. Bei mehrtägigen Alarmen kann `occurred_at` allein missverständlich sein (gleiche Uhrzeit an verschiedenen Tagen). Empfehlung für Analyse-Phase: Segment/km als primären Differenzierer nutzen (analog Single-Event-Zeile "Wo & wann"), `occurred_at` ergänzend.
- **Scope-Grenze:** SMS-Kurzform (`-TH1 -TH0 -TH0` aus #1861) hat dasselbe Ununterscheidbarkeits-Problem, aber SMS ist hart zeichenlimitiert (GSM-7, Token-Format). Muss in der Analyse explizit entschieden werden: Teil dieser Scheibe oder bewusst ausgeklammert (Token-Format-Erweiterung wäre größerer Eingriff).

## Analysis

### Type
Bug (2 zusammengehörige PO-Reports, ein Slice/Commit).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Neuer gemeinsamer Helper `_where_when(e, location_label=None)` (extrahiert aus `_datablock_single`-Zeile-3-Logik) für #1861-Differenzierer im Multi-Zweig von `render_email` (Zeile 504-519) **und** Telegram-Multi-Zweig (Zeile ~610-615, Konsistenz-Vorgabe #978); Wortlaut-Fix `_datablock_single` Zeile 388-391 für #1865 (vollständiger Satz statt Fragment, `over_thr()`/`side_label()`-Aufrufe unverändert) |
| `tests/tdd/test_alert_bundle_958ff.py` | MODIFY | Zeile 144/148 — neuer Wortlaut statt `"Änderung über ✗"`, AC-2-Beschreibung anpassen |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY | Zeile 750-765 — identischer String-Block für den Compare-Alarm-Pfad |
| ggf. weitere Testdateien mit `"Änderung über/unter"`/`"Alarm-Schwelle"`-Assertions | MODIFY | Vor Implementierung per `grep -rn "Änderung über\|Änderung unter" tests/` vollständig erfassen — nicht von den zwei oben genannten verallgemeinern |

### Scope Assessment
- Files: 1 Quelldatei + 2-4 Testdateien
- Estimated LoC: ~30-40 (Helper-Extraktion + zwei Wortlaut-Stellen + Test-Anpassungen)
- Risk Level: LOW (reines Text-Templating, `over_thr()`/`side_label()`-Semantik aus #958 bleibt unberührt)

### Technical Approach
- **#1861:** Multi-Event-Zeilen bekommen einen Orts-/Zeit-Zusatz aus bereits vorhandenen `AlertEvent`-Feldern (`segment_id`/`km_from`/`km_to`/`occurred_at`) — analog zur bestehenden "Wo & wann"-Zeile im Single-Event-Pfad, über gemeinsamen Helper statt Duplikat-Logik. Telegram-Multi-Zweig zieht aus Kanal-Konsistenz-Gründen (Präzedenz #978) mit; SMS bewusst **ausgeklammert** (strukturell anders: `_sms_token` hängt bereits `@HH` an, hartes GSM-7-Zeichenlimit — eigenes Ticket bei Bedarf).
- **#1865:** Nur der Text um die bereits korrekten `over_thr()`/`side_label()`-Werte wird zum vollständigen Satz (z. B. „jetzt darüber ✗"/„jetzt darunter ✓" analog Design-Vorlage, oder „Wert liegt über/unter ✗/✓"). Exakter deutscher Wortlaut wird in `/30-write-spec` als AC formuliert und dem PO zur Freigabe vorgelegt — keine Logikänderung an `over_thr()`/`side_label()` (#958-Invariante).

### Dependencies
- Ein Slice für beide Bugs (dieselbe Datei, dieselben zwei Pflicht-Test-Updates fallen so oder so an — zwei separate Renderer-Gate-Läufe wären Mehraufwand ohne Nutzen).
- Renderer-Commit-Gate #811 greift (`alert/render.py` matched das `radar_alert_files`-Pattern in `renderer_mail_gate.py:56`), verlangt `test_issue_811_mode_matrix.py` grün + einen `radar_alert_validation.yaml`-Nachweis.
- **Korrektur zur strategischen Bewertung des Plan-Agenten:** dessen Aussage „`briefing_mail_validator.py:574` behandelt `deviation-alert` aktiv" ist **falsch** — nachgemessen (`briefing_mail_validator.py:574-580`): `mail_type in ("compare", "deviation-alert")` liefert dort explizit `(False, ["... falscher Validator, uebersprungen"])`, ist also selbst ein No-Op-Fail, kein aktiver Check. Und `radar_alert_mail_validator.py:105-108` validiert nur `mail_type == "radar-alert"` (Nowcast/Onset), für `deviation-alert` ebenfalls No-Op (Exit 0 ohne Inhaltsprüfung, wie bereits für `official-alert` in `[[project_issue_1216_alert_mail_vorlage]]` dokumentiert). **Es gibt keinen aktiven Inhalts-Validator für `deviation-alert`-Mails** — der einzige echte Korrektheits-Nachweis für den neuen Wortlaut kommt aus den (angepassten) deterministischen Unit-/TDD-Tests, nicht aus einem Live-Mail-Validator-Lauf. Bekannte, bereits dokumentierte Gate-Lücke (kein neuer Handlungsbedarf in dieser Scheibe).

### Open Questions
- [x] Braucht #1861 einen Differenzierer? → Ja, Segment/km + Uhrzeit aus vorhandenen Feldern.
- [x] SMS mitziehen? → Nein, eigenes Ticket bei Bedarf.
- [x] Gefährdet der #1865-Fix die #958-Korrektheit? → Nein, wenn nur der Text um `over_thr()`/`side_label()` geändert wird.
- [ ] Exakter deutscher Wortlaut beider Zeilen — wird als AC in `/30-write-spec` formuliert und PO-freigegeben.
