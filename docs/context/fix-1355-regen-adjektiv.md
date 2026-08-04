# Context: fix-1355-regen-adjektiv

## Request Summary
Issue #1355: Die Kurz-Zusammenfassungszeile im Briefing beginnt bei spät einsetzendem Regen unbedingt mit „trocken" (`„trocken, Regen ab {HH}:00"`), auch wenn die Tagessumme erheblich ist (Beleg: 15,4 mm). Das Adjektiv aus `_precip_adjective` (z.B. „starker Regen") wird in diesem Zweig verworfen. Fix: das Adjektiv muss in den `starts_later`-Zweig einfließen statt wegfallen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/compact_summary.py:360-395` | `_format_precipitation` — Ort des Bugs. `kind == "starts_later"` (Zeile 388-389) gibt unbedingt `f"trocken, Regen ab {pattern['start_hour']}:00"` zurück, ohne `adj` (Zeile 377) zu nutzen. Die anderen Zweige (`peak`, `ends_early`, `window`) nutzen `adj` bereits korrekt. |
| `src/output/renderers/compact_summary.py:400-405` | `_precip_adjective(mm)` — liefert „starker Regen" (>10mm), „mäßiger Regen" (>2mm), „leichter Regen" (sonst), berechnet aus der **Tagesfenster-Summe**, nicht dem Segment-Aggregat. |
| `src/output/renderers/compact_summary.py:407-465` | `_find_rain_pattern` — Musteranalyse (`throughout`/`peak`/`window`/`starts_later`/`ends_early`). Ändert sich in diesem Fix NICHT — nur die Textbildung im Aufrufer. |
| `src/output/renderers/trip_report.py:800-810` | Einziger Aufrufer von `format_stage_summary` → der Bug wirkt in **allen drei** Kanälen, die `trip_report.py` speist (HTML-Mail, Plain-Mail, SMS/Telegram-Kurzform teilen denselben Renderer-Kern laut Projektkonvention „ein Code für alle Kanäle"). |
| `docs/specs/modules/compact_summary.md:94` | Spec-Tabelle dokumentiert aktuell **die fehlerhafte** Ausgabe: `"Regen beginnt spaeter" → "trocken, Regen ab {HH}:00"` (Zeile 94) sowie Beispielsatz Zeile 72/79. Muss beim Fix mit-aktualisiert werden — sonst driftet Spec vs. Code wieder auseinander. |
| `docs/specs/modules/compact_summary.md:383-393` | AC-Abschnitt für `test_rain_starts_later` — beschreibt nur „Enthaelt 'Regen ab 13:00'", macht KEINE Aussage über das Adjektiv. Muss um die Adjektiv-Erwartung ergänzt werden. |

## Existing Patterns
- **`ends_early`-Zweig als Vorbild** (Zeile 391-393): `f"{adj} bis {end_h}:00, trocken ab {dry_h}:00"` — nennt das Adjektiv VOR dem Zeitfenster, „trocken" erscheint dort korrekt nur für die Phase, die tatsächlich trocken ist (danach). Der `starts_later`-Zweig sollte analog gebaut werden: „trocken" nur für die tatsächlich trockene Phase (vor Regenbeginn), das Adjektiv für die Regenphase danach.
- **Adjektiv-Schwellen bereits vorhanden** (`_precip_adjective`): leicht/mäßig/stark — keine neue Logik nötig, nur Verwendung im Zweig.
- Bestehender Test `test_rain_starts_later` (`tests/integration/test_compact_summary.py:187`) prüft nur `"13:00" in result or "13" in result` — **keine** Bindung an den exakten Wortlaut „trocken, Regen ab". Ein Fix, der das Wort „trocken" aus diesem Zweig entfernt/umstellt, bricht diesen Test NICHT.
- Adversary-Test `tests/tdd/test_sms_daywindow_aggregation.py:700` prüft NUR die Negativ-Aussage `"trocken, Regen ab 04:00" not in compact` (Fensterrand-Fall) — ebenfalls nicht am exakten Wortlaut des Normalfalls gebunden.

## Dependencies
- **Upstream:** `_precip_adjective(precip: float) -> str`, `_find_rain_pattern(hourly) -> Optional[dict]` — beide unverändert nutzbar.
- **Downstream:** `trip_report.py` → `email/html.py`, `email/plain.py` (laut geteiltem Renderer-Kern-Prinzip). Änderung an `compact_summary.py` löst das **Renderer-Commit-Gate #811** aus (`renderer_mail_gate.py`) — vor Commit: `tests/tdd/test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Erfolgslog gegen eine echte Staging-Testmail (`gregor-test@henemm.com`).

## Existing Specs
- `docs/specs/modules/compact_summary.md` — SSOT für dieses Format, v1.1. Muss im Rahmen dieses Fixes aktualisiert werden (Zeile 72/79/94 zeigen den heutigen, fehlerhaften Wortlaut als Soll-Zustand).

## Risks & Considerations
- **Wortlaut-Entscheidung nötig:** Der neue Satz muss für alle `start_hour`-Werte plausibel bleiben (früh am Morgen, spätabends) — „vormittags trocken" passt nicht immer. Sinnvoller Kandidat, der sich am `ends_early`-Muster orientiert: `f"trocken, ab {start_hour}:00 {adj}"` (mirrort `ends_early`s `f"{adj} bis {end_h}:00, trocken ab {dry_h}:00"` seitenverkehrt).
- **Geteilter Baustein:** `compact_summary.py` wird von HTML- und Plain-Mail-Renderer sowie Trip-Report gemeinsam genutzt — Fix wirkt automatisch in allen Kanälen (kein Extra-Aufwand, aber Mail-Gate-Pflicht für beide Formate).
- **Spec-Drift:** Ohne Spec-Update dokumentiert `compact_summary.md` weiterhin den Bug als Soll-Verhalten — muss im selben Workflow mit-gepflegt werden (Zeile 72, 79, 94, ggf. 383-393 AC-Text).
- Keine Migration auf `metric_format.format_value` (siehe Kommentar am Klassenkopf, Zeile 32-37) — dieser Fix bleibt im narrativen Satzbau, keine Katalog-Anbindung.

## Nächster Schritt
Kontext gesammelt. 6 relevante Dateien identifiziert (Code, Spec, Tests). Weiter mit `/30-write-spec` — der Bug-Fast-Track überspringt die separate Analyse-Phase.
