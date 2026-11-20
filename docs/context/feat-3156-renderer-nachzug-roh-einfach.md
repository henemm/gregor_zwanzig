# Context: feat-3156-renderer-nachzug-roh-einfach

Issue #3156 · Teil von Epic #3122 · Spec `docs/specs/modules/feat_3122_was_steht_wo.md` Teil A Nr. 4 (AC-5, AC-6) · ADR-0124 Nr. 5.
Intake-Summe 3 (Scope/Blast/Unsicherheit je Medium) ⇒ Kontext und Analyse in einem Durchgang.

## Request Summary
Die Katalog-Quelle `zwei_formen_stellen` (welche Metrik an welcher Stelle Roh/Einfach hat) existiert seit B1a, der Renderpfad entscheidet aber noch über eigene, nicht deckungsgleiche Listen. Ziel: (1) zwei offene Fälle bauen — Wortstufe der Regenwahrscheinlichkeit in der Trip-Nur-Text-Mail, Ampelpunkt der Regenwahrscheinlichkeit in der Orte-HTML-Übersicht; (2) die alten Fähigkeitslisten im Renderpfad (Ausblick, Orte-Stundenverlauf, Orte-Telegram/Klartext) durch die eine Quelle ersetzen. „Fertig“: jede Stelle mit Umschalter liefert in echter Ausgabe beide Formen (Validator mit `--konfig`, HTML und Nur-Text), live.

## Soll (Spec-Tabelle Teil A Nr. 4, im Katalog `STELLEN_ZWEI_FORMEN`)
- wind, gust, precipitation, rain_probability, cloud_* : email, telegram, hourly, outlook
- sunshine, wind_direction : email, telegram, outlook (Stundenverlauf: Sonne gesperrt, Windrichtung immer Kompass)
- thunder : nur email (Ampelpunkt nur HTML; Texte immer Stufenwort)
- alle übrigen: keine, SMS nie

## Related Files (Ist, mit Abweichung zur Quelle)
| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py:1145-1221` | `OUTLOOK_FRIENDLY_CAPABLE`, `outlook_friendly_capable`, `normalize_outlook_metric_formats` (alte Ausblick-Liste) neben `STELLEN_ZWEI_FORMEN`/`zwei_formen_stellen` (neue Quelle). rain_probability `format_modes=("raw",)` (:456-473), col_key `pop`, Schwellen 30/60/80 (:470) |
| `src/output/renderers/compare_outlook_metric_ids.py` | `normalize_outlook_metric_formats` gerufen :294, :311, :353; `_friendly_outlook_text` :455-493 (eigene if-Kette, Wortstufe Regenwahrsch. via `format_rain_probability_scale` :487); `resolve_hourly_metric_formats` :496-505 filtert gar nicht; `_friendly_hour_text` :508-521; Warnung bei Drift :564-573 |
| `src/output/renderers/compare_metric_ids.py:364-376,424` | `_friendly_effective` nutzt `len(format_modes)>1` ⇒ Orte-Telegram/Klartext verwirft Einfach für rain_probability still; thunder bekommt dort Einfach, obwohl Quelle nur email nennt |
| `src/output/renderers/comparison.py:440,664-688,693-714` | Orte-Telegram/Klartext Einfach-Text über `_friendly_outlook_text` |
| `src/output/renderers/email/compare_html.py:761,777` | `_FRIENDLY_AMPEL_METRIC_IDS={wind,gust,precipitation}` — rain_probability fehlt ⇒ Wortstufe statt Ampelpunkt (Fall 2) |
| `src/output/renderers/email/compare_html.py:1125-1150` | `_hour_einfach_text` mit fest eingebauter Ampel-Liste `("wind","gust")` (Stundenverlauf) |
| `src/output/renderers/email/helpers.py:1262` `build_friendly_keys` | nimmt nur Metriken mit Modus≠raw und `friendly_label`; rain_probability fällt raus |
| `src/output/renderers/email/helpers.py:1378,1396-1416` | `build_format_modes` (pop immer raw), `_AMPEL_CAPABLE_METRIC_IDS`, `build_html_indicator_keys` (HTML-Ampel Trip, deshalb HTML grün) |
| `src/output/renderers/email/helpers.py:910-914` `fmt_val` pop-Zweig | nur HTML-Ampel oder Zahl; kein Text-Zweig „simplified ⇒ Wortstufe“ (Fall 1). Vorbild: wind/gust :851, precip :870 |
| `src/output/renderers/email/plain.py:96-139` | `_render_text_table` → `fmt_val(friendly_keys=…)` |
| `src/output/renderers/trip_report.py:184,361` | ruft `build_friendly_keys` |
| `src/services/placements.py` | nutzt Quelle schon (:175, :383, :482); `_AMPEL_CAPABLE_METRIC_IDS` noch in `heutige_form` :312/:320 und `_regel_changes` :493/:498 |
| `src/services/weather_metrics.py:184` | `format_rain_probability_scale` (Wortstufe existiert) |
| `src/app/loader.py:24,1197,1973` | `normalize_outlook_metric_formats` beim Laden |
| `.claude/hooks/_soll_aus_konfiguration.py:69,78,307-309,327,671` | Validator-Soll: importiert `OUTLOOK_FRIENDLY_CAPABLE` und `_AMPEL_CAPABLE_METRIC_IDS`; Trip-Klartext erwartet für Ampel-Metriken Zahl ⇒ muss für rain_probability Wortstufe erwarten |
| weitere Ampel-Konsumenten | `alert/hours.py:14,23`, `notification_service.py:699,706` (Alarm-Pfad, ADR-0124 Nr. 11 — nicht Scope) |

## Tests / Wächter
- `tests/tdd/test_katalog_stellen_formen.py:60-88` — Deckungstests alte Listen ↔ Quelle mit benannter Differenz; müssen nach dem Nachzug zu „Renderer folgt der Quelle“ umgeschrieben werden (:74 Differenz `{rain_probability}` bricht).
- xfail(strict): `test_einstellung_gleich_mail_trip_tabelle.py:409-414` (Nur-Text Wortstufe), `test_einstellung_gleich_mail_orte_tabelle.py:365-374` (HTML-Ampel). Nach Bau xfail entfernen.
- Fallliste: `fallliste_trip.json:4157-4169` `T-3122-B1B-AC5-REGENWAHRSCHEINLICHKEIT-NUR-TEXT`, `fallliste_orte.json:3198-3208` `O-3122-AC5-REGENWAHRSCHEINLICHKEIT-HTML-AMPEL` → `gruen`. Kein fester Zähler an den echten Listen.
- `tests/tdd/test_outlook_darstellungsform.py:190-201`, `tests/helpers/metrik_listen_scan.py:325,364,369` + Ratsche `tests/unit/test_metrik_listen_register_ratchet.py` (bricht/zählt beim Entfernen einer Liste — Registereintrag mitpflegen).
- Frontend-Drift: `frontend/.../outlookFriendlyCapability.ts:16` mit `__tests__/outlookFriendlyCapabilityDrift.test.ts:41-61` ruft Python live auf.

## Existing Patterns
- Einfach-Text über `_friendly_outlook_text` (eine Wortkette für Ausblick, Orte-Übersicht-Text, Stundenverlauf-Fallback).
- HTML-Ampel über `fmt_val(..., indicator_keys={col_key}, ampel=...)`.
- placements.py zeigt das Zielmuster: `if stelle in zwei_formen_stellen(metric_id)`.

## Analyse (kurz, Summe 1–3)
- **Fall 2 (Orte-HTML):** `rain_probability` in die Ampel-Menge — besser: Ampel-Entscheid aus Quelle + Kategorie „Ampel-fähig“ (wind/gust/precipitation/rain_probability, = Spec-Spalte „Ampelpunkt in der HTML-Mail“). Schwellen und col_key-Abbildung existieren.
- **Fall 1 (Trip-Nur-Text):** im pop-Zweig von `fmt_val` Text-Zweig „Einfach ⇒ `format_rain_probability_scale`“; dafür muss `friendly_keys` (bzw. ein Placements-gestützter Ersatz) `pop` enthalten, wenn email=simplified. Validator-Soll (`_soll_aus_konfiguration.py:307`) gleichziehen.
- **Ablösen der Listen:** `normalize_outlook_metric_formats`/`outlook_friendly_capable` auf `"outlook" in zwei_formen_stellen(m)` umstellen (deckungsgleich, keine Verhaltensänderung); `resolve_hourly_metric_formats` auf `"hourly" in …` filtern (Verhaltensänderung: sunshine/wind_direction im Stundenverlauf ohne Einfach — so von Spec gewollt); `_friendly_effective` auf `"telegram"`/`"email"` je Stelle (rain_probability bekommt Telegram-Einfach, thunder verliert Telegram-Einfach = Stufenwort bleibt ohnehin). `_FRIENDLY_AMPEL_METRIC_IDS`, `_hour_einfach_text`-Liste, `_AMPEL_CAPABLE_METRIC_IDS` auf eine gemeinsame Ampel-Menge im Katalog.
- **Nicht im Scope:** Frontend-Listen (`INDICATOR_MAP`, `outlookFriendlyCapability.ts`, `hourlyFriendlyMap.ts`) → B3b #3154; `SMS_FORMAT_MODE_METRIC_IDS` (SMS hat keine Wahl, Liste steuert Kürzelform, nicht Umschalter) — prüfen, ob als Fähigkeits-Abfrage genutzt; Alarm-Pfad.

## Risks & Considerations
- Bestandsabos: Altbestand ohne neues Feld muss dieselbe Ausgabe ergeben (AC-11). Verhaltensänderungen (Stundenverlauf sunshine/wind_direction, Telegram thunder/rain_probability) nur, wo ein Einfach-Format gespeichert ist — gegen Prod-Daten abschätzen.
- Mail-Inhalt ⇒ Renderer-Commit-Gate (Modus-Matrix-Test + Validator frisch grün) und Staging-Mail-Validator mit `--konfig`.
- Frontend-Drift-Test hängt an `OUTLOOK_FRIENDLY_CAPABLE`: Liste als abgeleiteter Alias aus der Quelle behalten, bis #3154 das Frontend umstellt.
- Ratsche Metrik-Listen-Register: entfernte Listen dort austragen.

## Analysis

### Type
Feature (Renderer-Nachzug, Teil von Epic #3122, Spec Teil A Nr. 4 · AC-5/AC-6)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | `rain_probability.format_modes=("raw","simplified")` (default bleibt raw); neue abgeleitete Menge `AMPEL_METRIC_IDS`/`ampel_faehig()` = `"email" in zwei_formen_stellen(m)` UND `display_thresholds` ⇒ {wind,gust,precipitation,rain_probability} (thunder ohne Schwellen, eigener Zweig); `outlook_friendly_capable`/`normalize_outlook_metric_formats` auf `"outlook" in zwei_formen_stellen`; `OUTLOOK_FRIENDLY_CAPABLE` bleibt abgeleiteter Alias (Frontend-Drift-Test, bis #3154) |
| `src/output/renderers/email/helpers.py` | MODIFY | `fmt_val` pop-Zweig :910: `mode=="simplified" and not html` ⇒ `format_rain_probability_scale` (Vorbild wind :851); `_AMPEL_CAPABLE_METRIC_IDS` = Alias auf Katalog-Menge (Alarm-Pfad + Validator importieren es) |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_FRIENDLY_AMPEL_METRIC_IDS` :761 und `_hour_einfach_text`-Liste :1139 aus Katalog (Ampel + `"hourly"`) ⇒ Fall 2 |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `_friendly_effective(kennung, entry, channel)`: `channel in zwei_formen_stellen(kennung)` statt `len(format_modes)>1` |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `resolve_hourly_metric_formats` filtert `"hourly" in zwei_formen_stellen` |
| `src/services/placements.py` | MODIFY | `heutige_form`/`_regel_changes` über Katalog-Ampelmenge |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | Trip-Klartext :307: rain_probability bei Einfach ⇒ Wortstufe; Imports :69/78/327 auf Quelle |
| `tests/tdd/test_katalog_stellen_formen.py` | MODIFY | Deckungstests ⇒ „Renderer folgt der Quelle“ (Differenz `{rain_probability}` :74/:80 entfällt) |
| `tests/.../test_einstellung_gleich_mail_trip_tabelle.py`, `..._orte_tabelle.py` | MODIFY | xfail(strict) entfernen |
| `fallliste_trip.json`, `fallliste_orte.json` | MODIFY | zwei Fälle → `gruen` |
| `tests/helpers/metrik_listen_scan.py`, `tests/unit/test_metrik_listen_register_ratchet.py` | MODIFY | Register: `_FRIENDLY_AMPEL_METRIC_IDS` aus, neue Ableitung ein |

### Scope Assessment
- Files: ~12 (6 Produktion, 1 Validator, ~5 Tests/Daten)
- Estimated LoC: Produktion +70/-40, Tests/Wächter +80/-60
- Risk Level: MEDIUM (Mail-Inhalt, Renderer-Gate; Bestandsdaten kaum betroffen)

### Technical Approach
Plan-Bewertung (Sonnet) bestätigt die Ist-Analyse am Code. Korrektur gegenüber der Kurzanalyse oben: Fall 1 NICHT über `build_friendly_keys`/`friendly_keys`, sondern wie wind/gust: Katalog-Modus `simplified` für rain_probability + Text-Zweig im `fmt_val`-pop-Zweig. HTML-Trip-Mail bleibt unverändert (Ampel über `indicator_keys`). Damit greift auch `_friendly_effective` (Orte-Telegram/Klartext) und Trip-Telegram (narrow.py nutzt denselben `fmt_val`) — spec-gedeckt (Spec :121).

Reihenfolge: (1) Katalog + Deckungstest, (2) Fall 1 + Validator-Soll + xfail, (3) Fall 2 + xfail, (4) Listenablösung `_friendly_effective`/`resolve_hourly`/`_hour_einfach_text`/placements, (5) Ratsche/Register, Modus-Matrix, Validator `--konfig`, Staging-Mail-Validator.

Scheiben-Entscheid (Tech Lead): ein Workflow, Commit-Reihenfolge wie oben; nur falls das LoC-Gate blockt, Schritte 4–5 als eigenes Kind-Issue unter #3122 abspalten.

Beim Bau prüfen: über welchen Pfad die Einfach-Zelle in der Orte-HTML-Übersicht ankommt (Zeilen-Format aus placements vs. `channel_layouts`), damit der Ampel-Zweig wirklich greift.

### Bestandsdaten (Prod, gemessen 2026-11-20)
- `hourly_metric_formats=true`: nur 1 Abo, Metriken wind/gust/precipitation/rain_probability/cloud_* — kein sunshine/wind_direction ⇒ Stundenverlauf-Filter ohne Ausgabeänderung.
- Orte-`channel_layouts` mit `use_friendly_format:true`: je 1 Abo für rain_probability (email/telegram) ⇒ wechselt bewusst von Zahl auf Wortstufe/Ampel (Spec :121); thunder telegram (1 Abo) verliert Einfach — Text zeigt ohnehin Stufenwort, keine sichtbare Änderung. Trip: kein rain_probability-Eintrag mit true.
- Trip-Nur-Text: Bestand mit HTML-Ampel bekommt Wortstufe erst bei wirksamem `format_mode="simplified"`; „Nur-Text folgt der HTML-Mail“ ist in Spec Nr. 8 als bewusste Änderung der Migration (B6) geführt, nicht dieser Scheibe.

### Dependencies
- `_AMPEL_CAPABLE_METRIC_IDS` wird von `alert/hours.py`, `notification_service.py` (Alarm, nicht Scope) und dem Validator importiert ⇒ Alias behalten.
- `OUTLOOK_FRIENDLY_CAPABLE` wird vom Frontend-Drift-Test live aufgerufen ⇒ Alias bis #3154.
- `/api/metrics` (`api/routers/config.py:150`) liefert `format_modes` aus; Frontend nutzt es nur als optionalen Typ (`types.ts:222`) ⇒ Erweiterung ohne UI-Wirkung (in Phase 3 am Editor gegenprüfen).
- `SMS_FORMAT_MODE_METRIC_IDS` steuert die Kürzelform (Wolken), keine Fähigkeitsabfrage ⇒ nicht anfassen.

### Open Questions
- [x] Keine Produktfrage offen — Verhalten ist durch Spec #3122 Teil A Nr. 4/8 freigegeben.

## Hinweis für Phase 4 (TDD RED)
- PO-Briefing-Anmerkung: Trip-Telegram ändert sich bei rain_probability mit Einfach ebenfalls (narrow.py über fmt_val), hat aber keinen eigenen Test in der Spec. In /40-tdd-red einen zusätzlichen Test für die Trip-Telegram-Ausgabe (Einfach ⇒ Wortstufe, Roh ⇒ Zahl) anlegen.
