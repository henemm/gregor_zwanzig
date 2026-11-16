# Context: fix-3048-altbestand-telegram-kopf (#3048 + #3052, Epic #3047)

## Request Summary
PO 2026-11-16: #3048 und #3052 aus Epic #3047 in einem Durchlauf bis live.
- #3048: Trip mit `display_config` ohne `metrics` (Altbestand, Fall A) -> Etappen-/Nachttabelle der Mail ohne Wertspalten, Metriken-Überblick derselben Mail zeigt den Standardsatz.
- #3052: Telegram-Kopf eines Trip-Briefings zeigt `report_type.title()` („Evening 15.07.2026") auch bei `language=de`.
- F4 aus #3048 (Ausblick-Hydration im Orte-Editor) ist nach #3061 abgespalten (Frontend, anderer Datenpfad).

## Bestandszählung 2026-11-16
Prod (`/var/lib/gregor`) und Staging: kein Trip mit `display_config` ohne `metrics`. Echte Nutzer 24–27 Metriken. `validator-issue110`: 8 Archiv-Trips ganz ohne `display_config` -> Loader-Zweig Profil-Vorgabe (#111), nicht betroffen. Behebung trotzdem, weil der Eingang (API/Import ohne `metrics`) offen ist und der Prüfkatalog den Fall als `ausnahme` führt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/loader.py:579-594` | Zweige: `display_config` vorhanden -> `_parse_display_config`; fehlt -> Profil-Vorgabe |
| `src/app/loader.py:972ff` `_parse_display_config` | liest `metrics` (fehlend -> `[]`), `auto_distribute` für bucket/order, `_append_derived_metrics` |
| `src/output/renderers/trip_metric_ids.py` | `DEFAULT_TRIP_METRIC_IDS`, Doku Fall A (fehlt/leer -> Standard) vs. Fall B (alle `enabled=False` -> leer) |
| `src/app/models.py` `get_metrics_for_channel` | liefert bei `metrics=[]` leer; 34 Matrix-Tests (`test_channel_metric_matrix.py`) bauen darauf -> NICHT ändern |
| `src/output/renderers/narrow.py:779` | Telegram-Kopf `report_type.title()`; `render_telegram_bubbles` hat bereits `lang` |
| `src/output/renderers/email/html.py:322` `_briefing_typ` | Mail-Lösung #3047 über `mail.kopf.typ_*` |
| `src/i18n/messages/{de,en}/mail.json` / `telegram.json` | Katalog |
| `tests/tdd/test_einstellung_gleich_mail_trip.py::test_n1_altbestand_ohne_metrics` | hält Ist-Zustand fest, muss auf Soll umgestellt werden |
| `tests/tdd/test_einstellung_gleich_mail_editor_standard.py::test_python_seite_trip_tabellen_altbestand` | Editor-Seite N1 |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,editor}.json` | Fälle `ausnahme` mit Verweis #3048 -> `gruen` |
| `tests/tdd/test_issue_1001_telegram_bubbles.py`, `tests/golden/telegram_briefing/*` | Bestandstests/Golden für Telegram-Kopf |

## Analyse / Ansatz
1. **#3048:** Normalisierung beim Laden: In `_parse_display_config` gilt `metrics` fehlend oder leer (Fall A laut `trip_metric_ids.py`) als Altbestand -> Liste aus `DEFAULT_TRIP_METRIC_IDS` (enabled, bucket/order per `auto_distribute`, Standard-Formatmodus). Fall B (Einträge alle aus) bleibt unberührt, `get_metrics_for_channel` und die Matrix-Tests bleiben unberührt. Eine Quelle für den Standardsatz (`DEFAULT_TRIP_METRIC_IDS`), damit Überblick und Tabellen übereinstimmen. Zu prüfen: zweiter Aufrufer `loader.py:1592` (Orte, `display_config` optional) -- Normalisierung nur für Trips (Parameter), sonst ändern sich Orte-Ausgaben.
2. **#3052:** Briefing-Art im Telegram-Kopf über denselben Katalogschlüssel wie die Mail (`mail.kopf.typ_*` bzw. gemeinsamer Helfer), Datum bleibt. Kein neuer Text, nur Wiederverwendung; unbekannte `report_type` fallen wie in der Mail auf `.title()` zurück.

## Risiken
- Roundtrip: schreibt ein Python-Pfad den geladenen Trip zurück, wird der Standardsatz persistiert (= gewollte Migration, Read-Modify-Write). Roundtrip-Tests (Snow-AC-10) prüfen.
- Englische Golden-Dateien bleiben „Evening“; deutsche Telegram-Golden/Tests mit „Evening“ müssen auf „Abend“.

## Analysis

### Type
Bug (zwei Nebenbefunde aus Epic #3047, gebündelt)

### Verifizierte Befunde (Code-Stand origin/main 4b5e8749f)
- `loader.py:581-585`: Trip mit `display_config` -> `_parse_display_config(data["display_config"] or {}, id)`. `metrics` fehlend/leer ergibt `raw_metrics=[]` -> `dc.metrics` nur aus `_append_derived_metrics` bzw. leer.
- `trip_report.py:133`: `_trip_metrics_altbestand = len(dc.metrics) == 0` steuert nur den Überblick (`resolve_trip_active_metrics(..., altbestand=True)` -> `DEFAULT_TRIP_METRIC_IDS`); Stunden-/Nachttabelle folgen `get_metrics_for_channel` -> leer. Daher der Widerspruch in derselben Mail.
- `DEFAULT_TRIP_METRIC_IDS` = temperature, wind, gust, precipitation, thunder, freezing_level, visibility, temperature_day_low, temperature_day_high. Die ersten sieben = `_REGISTER_STANDARD_STUNDENSPALTEN` des Prüfkatalogs (Soll) -> eine Quelle reicht.
- `loader.py:1592` (Orte-Laden) ruft `_parse_display_config` ebenfalls -> Normalisierung nur für Trips (Schalter), Orte bleiben unverändert.
- `narrow.py:779`: `head2 = f"{report_type.title()} {report_date}"`; Funktion hat `lang` (Default "de"). Mail-Pendant `email/html.py:_briefing_typ` mit `mail.kopf.typ_{morning,evening,alert}`, Rückfall `.title()`.
- Weitere `.title()`-Stellen: `email/plain.py:69` (Betreff-Allgemeinfall, Rückfall), `text_report/__init__.py:59` (Debug-Text), `sms_trip.py:779`/`trip_report.py:843` (Gefahrentyp-Tokens = Protokoll, NICHT übersetzen). Nicht im Scope.
- Golden `tests/golden/telegram_briefing/briefing_normalstil.de.txt:2` enthält „Morning 29.10.2026“ -> wird „Morgen 29.10.2026“; `.en.txt` bleibt. `test_issue_1001_telegram_bubbles.py:260` prüft `"Morning" in kopf` -> Sprache des Testaufrufs prüfen (Default de -> anpassen oder lang="en").

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` | MODIFY | `_parse_display_config(..., trip_standard_bei_leer: bool=False)`; Trip-Zweig ruft mit True: `metrics` fehlt/leer -> Einträge aus `DEFAULT_TRIP_METRIC_IDS` (enabled, bucket/order per auto_distribute) |
| `src/output/renderers/email/html.py` | MODIFY | `_briefing_typ` in geteilten Helfer verschieben oder exportieren (eine Quelle für Mail + Telegram) |
| `src/output/renderers/narrow.py` | MODIFY | Kopf über `_briefing_typ(report_type, lang)` |
| `tests/tdd/test_einstellung_gleich_mail_trip.py` | MODIFY | N1 von Ist auf Soll (Spalten = `_REGISTER_STANDARD_STUNDENSPALTEN`) |
| `tests/tdd/test_einstellung_gleich_mail_editor_standard.py` | MODIFY | Editor-Seite N1 auf Soll |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,editor}.json` | MODIFY | 5 Fälle `ausnahme` -> `gruen` |
| `tests/golden/telegram_briefing/briefing_normalstil.de.txt` | MODIFY | „Morning“ -> „Morgen“ |
| neue TDD-Tests | CREATE | Loader-Normalisierung (Fall A fehlt/leer, Fall B alle aus bleibt leer, Orte unverändert), Telegram-Kopf de/en |

### Scope Assessment
- Files: ~8 (2-3 Quellcode, Rest Tests/Fixtures)
- Estimated LoC: Quellcode +30/-5, Tests +120/-30
- Risk Level: LOW–MEDIUM (Loader ist zentral, aber Eingriff nur im Fall „metrics fehlt/leer“, der auf Prod/Staging nicht vorkommt; Telegram-Kopf nur Text)

### Technical Approach
1. #3048: Normalisierung an der Eingangsgrenze (Loader), nicht in `get_metrics_for_channel` (34 Matrix-Tests und #1394 „bewusst leer“ = Fall B bleiben unberührt). Fall B (Einträge vorhanden, alle `enabled=False`) bleibt leer. Danach ist `_trip_metrics_altbestand` beim Laden aus Datei faktisch False; der Überblick zeigt weiter den Standardsatz, jetzt aus den Einträgen statt aus dem Rückfall -> Überblick und Tabellen aus derselben Liste. Kein Daten-Rückschreiben nötig (keine Bestandsfälle); schreibt ein Python-Pfad den Trip zurück, wird der Standard persistiert (gewollt, Merge).
2. #3052: `_briefing_typ` als einzige Quelle für Mail und Telegram (Katalog `mail.kopf.typ_*`), Datum unverändert, unbekannte Typen `.title()`.

### Dependencies
`app.loader` -> `output.renderers.trip_metric_ids` (Import innerhalb der Funktion, Zyklus vermeiden wie bei `auto_distribute`). `narrow.py` -> Helfer aus email-Paket oder neutraler Ort (z. B. `output/renderers/briefing_typ.py`), Importzyklus prüfen.

### Open Questions
- keine Produktfrage offen (Soll aus Issue/Prüfkatalog eindeutig).
