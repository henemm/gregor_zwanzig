# Context: fix-1146-badge-window-mismatch

## Request Summary
Das Metriken-Überblick-Badge in Briefing-Mails deckt ein engeres Stunden-Fenster ab als die gerenderte Stundentabelle — dadurch kann das Badge "kein Regen" zeigen, obwohl die Tabelle direkt darunter reale Regenwerte ausweist (Nebenbefund aus E2E #1003, vom `briefing_mail_validator.py` als FULL-Plausibilitätsfehler gemeldet).

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:1298-1311` (`build_metrics_summary_pills`) | Aggregiert `all_dps` über alle Segmente mit **exklusivem** Ende: `s_h <= h < e_h`. Bewusst so seit #806/#807, um bei aufeinanderfolgenden ~2h-Segmenten die gemeinsame Grenzstunde nicht doppelt zu zählen. |
| `src/output/renderers/trip_report.py:257-274` (`_extract_hourly_rows`) | Baut die Stundentabelle pro Segment mit **inklusivem** Ende: `start_h <= h <= end_h`. Zeigt bewusst die Ankunftsstunde des Segments (nützliche Information für Wanderer). |
| `.claude/hooks/briefing_mail_validator.py:267-291` (`_check_metric_plausibility`) | AC-4-Validator: vergleicht "kein Regen"-Pill-Text gegen Tabellen-Regensumme. Meldet FULL-Fehler bei genau dieser Diskrepanz. |
| `src/output/renderers/email/{html,plain,compact}.py` | Rufen `build_metrics_summary_pills(segments, ...)` mit denselben `segments` wie die Tabelle auf — kein struktureller Unterschied in den übergebenen Daten, nur im Filter selbst. |

## Existing Patterns
- **#806/#807-Konvention:** "inclusive start, exclusive end" für die Badge-Aggregation — verhindert, dass die gemeinsame Grenzstunde zweier aufeinanderfolgender Segmente (Segment A endet 12:00 = Segment B beginnt 12:00) doppelt in `all_dps` landet.
- **TripSegment-Doku (`models.py:323`):** "Single segment of a trip (typically ~2 hours hiking)" — ein Tag/eine Etappe besteht typischerweise aus **mehreren** Segmenten hintereinander. Das exklusive Ende partitioniert die Stunden sauber — **außer** für das letzte Segment eines Reports: dessen Ende (Ankunftsstunde) wird von keinem nachfolgenden Segment mehr "aufgefangen" und fällt daher komplett aus `all_dps` heraus.
- Die Tabelle (`_extract_hourly_rows`) wird **pro Segment separat** aufgerufen (kein aggregiertes Cross-Segment-Array) — Doppel-Anzeige der Grenzstunde in zwei aufeinanderfolgenden Segment-Tabellen ist dort unproblematisch/sogar gewünscht (Kontext-Anzeige laut Issue-Text).

## Root Cause (verifiziert, nicht nur Hypothese)
Bei einem Segment mit `end_time.hour=12` enthält die Tabelle die 12:00-Zeile (inklusiv), das Badge nicht (exklusiv) — UND kein nachfolgendes Segment deckt Stunde 12 ab, wenn dies das letzte Segment des Tages ist. Genau das erklärt den gemeldeten 0.2mm-Fall (Regen exakt in der Ankunftsstunde). Bei mehreren Segmenten pro Tag kann sich der Effekt summieren, wenn mehrere Etappen-Enden betroffen sind (37mm-Fall).

## Dependencies
- Upstream: `SegmentWeatherData.timeseries` (Rohdaten), `TripSegment.start_time/end_time`
- Downstream: `render_html`, `render_plain`, `compact.py` — alle nutzen dieselbe `build_metrics_summary_pills`

## Existing Specs
- Keine dedizierte Spec für Segment-Fenster-Filterung gefunden; Verhalten ist über Bug-Fix-Kommentare (#806/#807) dokumentiert, nicht als formale Spec.

## Risks & Considerations
- **Naive Lösung vermeiden:** Einfach `<` zu `<=` in `helpers.py` ändern würde die #806/#807-Anti-Doppelzählung für alle NICHT-letzten Segmente eines Tages wieder brechen (jede Grenzstunde zwischen zwei Folge-Segmenten würde doppelt in `all_dps` landen → verfälschte Summen/Extremwerte).
- **Empfohlener Fix (Option 1, chirurgisch):** Nur für das **letzte** Segment in der übergebenen `segments`-Liste das Ende inklusiv behandeln (Ankunftsstunde einschließen), alle vorherigen Segmente bleiben exklusiv. Das schließt exakt die Lücke, ohne die bestehende Garantie zu verletzen.
- Betrifft `src/output/renderers/email/*.py` → löst den Renderer-Mail-Gate (#811) aus: `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf nötig vor Commit.
- Bestehender Test `test_issue_807_reproduction.py::test_pills_respect_segment_window` bleibt unberührt (Peak liegt weit außerhalb des Fensters, nicht an der Grenzstunde) — sollte grün bleiben.
