---
entity_id: fix_1926_metrik_kuerzel_englisch
type: module
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
tags: [bug, metric-catalog, adr-0042, sms, telegram, i18n]
---

# fix_1926_metrik_kuerzel_englisch

## Approval

- [x] Approved (2026-08-17, PO im Chat freigegeben — finale Werte-Tabelle siehe Purpose/Implementation Details)

## Purpose

Issue #1926: Elf Register-Werte im Wetter-Metrik-Katalog (`src/app/metric_catalog.py`) werden
korrigiert — sechs `col_label`-Werte sind deutsch und verletzen ADR-0042 (Klasse 2: Kurzform
≤6 Zeichen MUSS englisch sein), fünf `compact_label`/`sms_code`-Werte sind laut PO-Konsistenzentscheid
fehlerhaft (zwei echte SMS-Wire-Format-Token-Wechsel, drei Bereinigungen toter Literale). Betroffen
sind Nutzer, die Stundentabellen-Spaltenköpfe (Trip-/Vergleichs-Mail) oder SMS/Telegram-Kürzel lesen.

## Source

- **File:** `src/app/metric_catalog.py`
- **Identifier:** `_METRICS` (Liste von `MetricDefinition`), Modul-Konstanten `COMPACT_LABEL_EXCEPTIONS`, `_kurzform_kuerzel()`, `SMS_MULTI_SYMBOLS_BY_METRIC`

> **PFLICHT — Schicht-Hinweis:** Diese Änderung liegt vollständig in der **Python-Core / Domain-Backend**-Schicht
> (`src/app/metric_catalog.py`, `src/output/`, `src/app/` — FastAPI-Core, kein Go-API-Code in `internal/`/`cmd/`,
> keine SvelteKit-Komponenten). Downstream-Konsumenten (`src/output/metric_format.py`,
> `src/output/renderers/trip_report.py`, `src/output/renderers/email/helpers.py`,
> `src/output/renderers/email/compare_html.py`, `src/output/renderers/narrow.py`, `src/output/sms_trip.py`)
> lesen die Register-Werte nur, sie definieren sie nicht — kein Edit-Bedarf dort. Das Frontend
> (`frontend/src/`) referenziert Metriken ausschließlich über die stabile Metrik-UID (`id`) via
> `GET /api/metrics`, nie über `col_label`/`compact_label`/`sms_code` als Literal — verifiziert per
> `grep -rE "col_label|compact_label|sms_code"` gegen `frontend/src/`, kein Treffer der betroffenen
> alten oder neuen Werte (siehe AC-6).

## Estimated Scope

- **LoC:** ~60-100 (Register ~15-20 Zeilen direkte Änderung + Wächter-Erweiterung ~10-20 Zeilen +
  ~10+ Testdatei-Anpassungen, überwiegend 1-Zeilen-Ersetzungen)
- **Files:** 5-8 im Kern (`metric_catalog.py` + `col_label`-Konsumtest + Wächter), 15+ inklusive
  aller Testdateien, die `K`/`FK` als reales SMS-Symbol referenzieren
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/metric_format.py:204-212` | Consumer | `style="col_label"` löst gegen `metric.col_label` auf — Stundentabellen-Spaltenkopf |
| `src/output/renderers/trip_report.py:708,716` | Consumer | nutzt `col_label` für Spaltenkopf + Einheiten-Gruppierung |
| `src/output/renderers/email/helpers.py:548-577` | Consumer | Trip-Mail-Spaltenköpfe + Legenden-Zeile (löst `col_label` gegen `label_de` auf, ADR-0042-Nachtrag #1472) |
| `src/output/renderers/email/compare_html.py:479-521` | Consumer | Ortsvergleich-Tabelle, `form="short"` |
| `src/output/renderers/narrow.py` | Consumer | Telegram-Kompaktform liest `compact_label` |
| `src/output/sms_trip.py` | Consumer | SMS/Premium-SMS liest `sms_code`/`sms_multi_symbols` (Wire-Format, geht an echte Endgeräte) |
| `tests/unit/test_telegram_kuerzel_folgt_register.py` (#1719 S4) | Wächter | rechnet `compact_label` gegen `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` — muss nach `sms_code`-Änderung grün bleiben, da beide Seiten gemeinsam wandern |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` (#1856 E7) | Wächter | rein strukturell (Kollisionsfreiheit) — `_AC9_ERWARTUNG`-Tabelle pinnt `temperature_day_low: "K"` explizit, muss auf `"L"` umgestellt werden; wird um `col_label`-Sprachprüfung erweitert |
| ADR-0042 (`docs/adr/0042-namensform-folgt-der-platzgrenze.md`) | Regel | Klasse 2 (`col_label` MUSS englisch, ≤6 Zeichen) — diese Spec setzt sie durch; Klasse 1 (`sms_code`/`compact_label`) bleibt von Sprachfragen ausgenommen, die K/FK-Änderung ist ein Konsistenz-, kein Sprach-Fix |

## Implementation Details

**A) `col_label` — 6 Werte, reine Text-Ersetzung, ADR-0042-konform (≤6 Zeichen, englisch):**

| Zeile | `id` | Alt | Neu |
|---|---|---|---|
| 150 | `temperature_night` | `"Nacht"` | `"Night"` |
| 176 | `temperature_day_low` | `"TagMin"` | `"DayMin"` |
| 193 | `temperature_day_high` | `"TagMax"` | `"DayMax"` |
| 239 | `wind_chill_night` | `"NachtF"` | `"NightF"` |
| 263 | `wind_chill_day_low` | `"TagMinF"` | `"DayMinF"` |
| 274 | `wind_chill_day_high` | `"TagMaxF"` | `"DayMaxF"` |

**B) `sms_code`/`sms_multi_symbols` — 2 echte Wire-Format-Token-Wechsel (PO-Entscheid 2026-08-17):**

`compact_label` wird beim Laden des Registers automatisch aus `sms_code`/`sms_multi_symbols`
abgeleitet (`_kurzform_kuerzel()` + List-Comprehension über `_METRICS`, Zeilen ~813-855), außer die
`id` steht in `COMPACT_LABEL_EXCEPTIONS` (aktuell nur `"temperature"`/`"wind_chill"` als Basis-IDs —
`temperature_day_low`/`wind_chill_day_low` sind davon NICHT erfasst). Ein reiner Edit der
`compact_label`-Literalzeile bei diesen beiden IDs würde beim nächsten Laden also automatisch wieder
überschrieben (stiller No-Op). Deshalb wird die Ableitungsquelle selbst geändert:

| Zeile | `id` | Feld | Alt | Neu |
|---|---|---|---|---|
| 176 | `temperature_day_low` | `sms_code` | `"K"` | `"L"` |
| 176 | `temperature_day_low` | `sms_multi_symbols` | `("K",)` | `("L",)` |
| 263 | `wind_chill_day_low` | `sms_code` | `"FK"` | `"FL"` |
| 263 | `wind_chill_day_low` | `sms_multi_symbols` | `("FK",)` | `("FL",)` |

`compact_label` an diesen beiden Zeilen bleibt im Quelltext auf dem alten Literal (`"K"`/`"FK"`)
stehen — es ist ohnehin tot (wird durch die Ableitung überschrieben) und wird zur Lesbarkeit optional
auf `"L"`/`"FL"` nachgezogen, ohne funktionale Wirkung.

**C) `freezing_level.sms_code` — echter Fix (bisherige Kollision mit `snowfall_limit`/`snow`-Bereich vermeiden):**

| Zeile | Feld | Alt | Neu |
|---|---|---|---|
| 639 | `sms_code` | `"NL"` | `"FZ"` |

**D) Tote `compact_label`-Literale bereinigen (kein funktionaler Effekt, nur Lesbarkeit — die
Ableitung liefert zur Laufzeit bereits den neuen Wert):**

| Zeile | `id` | Feld | Alt (totes Literal) | Neu |
|---|---|---|---|---|
| 436 | `cape` | `compact_label` | `"CE"` | `"CP"` (= bereits abgeleiteter Laufzeitwert, `sms_code` bleibt `"CP"`) |
| 469 | `snowfall_limit` | `compact_label` | `"SG"` | `"SL"` (= bereits abgeleiteter Laufzeitwert, `sms_code` bleibt `"SL"`) |
| 632 | `freezing_level` | `compact_label` | `"0G"` | `"FZ"` (folgt dem neuen `sms_code`, s.o.) |

**Kollisionsfreiheit:** Alle neuen Werte (`L`, `FL`, `FZ`) wurden gegen alle 32 Katalog-Einträge
geprüft — kollisionsfrei. (Hinweis aus der Analyse: ein ursprünglich erwogenes `"C"` kollidierte mit
`cloud_total="C"` und wurde vor PO-Freigabe verworfen.)

**E) Wächter-Update (`tests/unit/test_sms_token_symbol_register_ratchet.py`):** Zeile 555,
`_AC9_ERWARTUNG`-Tabelle — Eintrag `"temperature_day_low": "K"` wird auf `"temperature_day_low": "L"`
umgestellt (Mutations-Gegenprobe für die Ableitung).

## Expected Behavior

- **Input:** Kein neuer Nutzer-Input — reine Registeränderung, wirkt bei jedem Rendern eines Trip-
  Briefings, Ortsvergleichs, Telegram-Kompaktreports oder einer SMS/Premium-SMS, die eine der elf
  betroffenen Metriken enthält.
- **Output:**
  - Stundentabellen-Spaltenköpfe (Trip- und Vergleichs-Mail) zeigen `Night`/`DayMin`/`DayMax`/
    `NightF`/`DayMinF`/`DayMaxF` statt der bisherigen deutschen Kürzel.
  - Die Legenden-Zeile unter der Stundentabelle (löst `col_label` gegen `label_de` auf, ADR-0042-
    Nachtrag #1472) bleibt unverändert korrekt, da sie den `label_de`-Volltext zeigt — nur der
    Spaltenkopf selbst ändert sich.
  - Telegram-Kompaktform und SMS/Premium-SMS senden `L` statt `K` (Tages-Tiefsttemperatur) und `FL`
    statt `FK` (gefühlte Tages-Tiefsttemperatur); `FZ` statt `NL` für Nullgradgrenze.
  - `cape`/`snowfall_limit`/`freezing_level` `compact_label` unverändert im Laufzeitverhalten (waren
    bereits `CP`/`SL`/via-Ableitung — nur der Quelltext-Literal-Wert wird lesbar korrekt).
- **Side effects:** Bestehende, bereits ausgehende Testmails/SMS mit den alten Kürzeln werden nicht
  rückwirkend geändert (keine Datenmigration nötig — Register-Werte werden nicht persistiert, nur zur
  Laufzeit gerendert).

## Test Plan

1. **Kern-Register-Test (neu/erweitert):** `tests/unit/test_sms_token_symbol_register_ratchet.py` —
   `_AC9_ERWARTUNG["temperature_day_low"]` auf `"L"` umgestellt; neue Prüfung, dass `col_label` für
   alle 32 Katalog-Einträge keine deutschen Wortbestandteile enthält (Negativliste, um Fachbegriffe
   wie `CAPE`/`UV` nicht fälschlich zu treffen).
2. **Konsumtest:** `tests/unit/test_trip_report_formatter_v2.py` Zeile 238-239 — Assertion
   `"Nacht" in evening/morning.email_html` auf den neuen `col_label`-Wert (`"Night"`) umgestellt;
   beweist, dass der Spaltenkopf tatsächlich im gerenderten Mail-HTML ankommt, nicht nur im Register.
3. **Wächter-Regressionslauf:** `tests/unit/test_telegram_kuerzel_folgt_register.py` läuft unverändert
   grün — beweist, dass Telegram-Kürzel (`compact_label`) und SMS-Kürzel (`sms_code`/
   `sms_multi_symbols`) nach der `K`→`L`/`FK`→`FL`-Änderung weiterhin synchron sind (beide Seiten
   wandern gemeinsam über dieselbe Ableitung).
4. **SMS-Wire-Format-Tests:** ~10+ Testdateien, die `K`/`FK` als reales gesendetes Symbol referenzieren
   (`test_sms_temperature_follows_metric_selection.py`, `test_night_temp_own_metric_selection.py`,
   `test_channel_metric_matrix.py`, `test_sms_snow_symbols.py`, `_hiking_window_fixtures.py`, u. a.) —
   Assertions auf `L`/`FL` umgestellt; beweisen, dass das tatsächlich an den Endnutzer gesendete
   SMS-Symbol (nicht nur der Katalog-Wert) sich ändert.
5. **Negativkontrolle (KEIN Change erwartet, gegengeprüft):** `tests/tdd/test_trip_outlook_metric_selection.py`,
   `tests/tdd/test_night_temp_own_metric_selection.py` (label-Assertion), `tests/tdd/test_felt_night_catalog_exclusions.py`,
   `tests/unit/test_renderers_email.py` — prüfen `label_de` oder einen anderen "Nacht"-Textblock
   außerhalb des Registers, bleiben unverändert grün.
6. **Frontend-Erhaltungsnachweis (AC-6):** `grep -rE '"(Nacht|TagMin|TagMax|NachtF|TagMinF|TagMaxF|K|FK|NL|CE|SG|0G)"'` gegen
   `frontend/src/` — kein Treffer, der die alten oder neuen Katalog-Literale referenziert (Frontend
   liest Metriken nur über die `id`/`GET /api/metrics`).
7. **Mutations-Gegenprobe (Adversary-Pflicht):** `sms_code`/`sms_multi_symbols` bei `temperature_day_low`
   zurück auf `"K"` verfälschen bei gleichzeitig belassenem `_AC9_ERWARTUNG`-Eintrag `"L"` — muss den
   Wächtertest rot werfen (beweist, dass die Ableitung tatsächlich geprüft wird, nicht nur der
   Quelltext-Wert).

## Acceptance Criteria

- **AC-1:** Given der Metrik-Katalog vor dem Fix / When ein Trip-Briefing mit `temperature_night`,
  `temperature_day_low`, `temperature_day_high`, `wind_chill_night`, `wind_chill_day_low` oder
  `wind_chill_day_high` gerendert wird / Then zeigt der Stundentabellen-Spaltenkopf den englischen
  Wert (`Night`/`DayMin`/`DayMax`/`NightF`/`DayMinF`/`DayMaxF`) statt des bisherigen deutschen Werts.
  - Test: `tests/unit/test_trip_report_formatter_v2.py` prüft `col_label`-String im gerenderten
    `email_html`, nicht nur im Register.

- **AC-2:** Given `temperature_day_low` ist als SMS-Metrik ausgewählt / When eine Trip-SMS oder
  Premium-SMS gesendet wird / Then trägt sie das Symbol `L` (nicht mehr `K`), und die zugehörige
  Telegram-Kompaktform zeigt ebenfalls `L` (nicht `K`).
  - Test: SMS-Wire-Format-Tests (`test_sms_temperature_follows_metric_selection.py` u. a.) prüfen
    den gesendeten Text; `test_telegram_kuerzel_folgt_register.py` prüft Telegram-Konsistenz.

- **AC-3:** Given `wind_chill_day_low` ist als SMS-Metrik ausgewählt / When eine Trip-SMS gesendet
  wird / Then trägt sie das Symbol `FL` (nicht mehr `FK`), kollisionsfrei gegen alle übrigen
  Register-Symbole.
  - Test: `test_sms_snow_symbols.py`/`_hiking_window_fixtures.py`-Familie plus
    `test_sms_token_symbol_register_ratchet.py`-Kollisionsprüfung.

- **AC-4:** Given `freezing_level` ist als Metrik ausgewählt / When ein SMS- oder Telegram-Kürzel
  für die Nullgradgrenze gerendert wird / Then lautet es `FZ` (nicht mehr `NL`), sowohl bei
  `sms_code` als auch beim daraus abgeleiteten `compact_label`.
  - Test: `test_telegram_kuerzel_folgt_register.py` plus Register-Wächter.

- **AC-5:** Given der Metrik-Katalog nach dem Fix / When `cape` oder `snowfall_limit` im Register
  inspiziert werden / Then stimmt das `compact_label`-Quelltext-Literal mit dem zur Laufzeit
  tatsächlich abgeleiteten Wert überein (`CP` bzw. `SL`), es gibt kein totes, abweichendes Literal
  mehr im Quelltext.
  - Test: statischer Registerwert-Vergleich in `test_sms_token_symbol_register_ratchet.py`
    (Quelltext-Literal == Ableitungsergebnis von `_kurzform_kuerzel()`).

- **AC-6:** Given die elf geänderten bzw. fünf ersetzten alten Kürzel-Werte / When `frontend/src/`
  nach diesen Literalen durchsucht wird / Then findet sich kein Treffer — das Frontend referenziert
  Metriken ausschließlich über die stabile `id` via `GET /api/metrics`, nicht über Kürzel-Literale.
  - Test: `grep -rE` gegen `frontend/src/` als Erhaltungs-Nachweis (kein neuer Testcode nötig, da
    bereits strukturell erfüllt — Nachmessung dokumentiert im Kontext-Dokument).

- **AC-7:** Given die Mutations-Gegenprobe verfälscht `sms_code`/`sms_multi_symbols` von
  `temperature_day_low` zurück auf `"K"` bei unverändertem Ratschen-Erwartungswert `"L"` / When der
  Wächtertest `test_sms_token_symbol_register_ratchet.py` läuft / Then schlägt er rot fehl — die
  Zusicherung wird an der Ableitungsstelle geprüft, nicht nur am unveränderten Quelltext-Literal.
  - Test: manuelle String-Ersetzung mit externer Sicherungskopie (kein `git checkout`), Testlauf vor
    und nach der Rücknahme dokumentiert.

- **AC-8 (RED-Phase-Korrektur, 2026-08-17, benannte Ausnahme statt erneuter spec-writer-Lauf —
  Kosten-/Kontext-Abwägung, PO informiert):** Given `src/output/tokens/builder.py` (`PRIORITY`,
  `POSITIONAL`, `build_token_line()`, Zeilen ~60/96/325-330/378/426) führt bewusst eigene,
  vom Register unabhängige Literale (#1435 E3b, Schichtgrenze `output/tokens/` importiert
  nicht aus `app/`) / When die fünf geänderten Kürzel (`L`, `FL`, `FZ`) betroffen sind / Then
  werden auch diese Literale von Hand nachgezogen (bestehendes, bewachtes Muster — **keine**
  Entkopplung der Schichtgrenze, das ist ausgegliedert nach #1934) und die Ratschen-Ausnahmeliste
  in `test_sms_token_symbol_register_ratchet.py` entsprechend aktualisiert.
  - Test: neuer RED-Test, der `builder.py`s tatsächlich erzeugten Token-Text gegen die alten
    Werte (`K`/`FK`/`NL`) prüft und rot ausschlägt, bis `builder.py` mitgezogen ist.
  - **Korrektur der Dependencies-Section:** `src/output/tokens/builder.py` ist entgegen der
    ursprünglichen Spec-Aussage („Downstream-Konsumenten lesen nur, kein Edit-Bedarf dort")
    doch eine Produktivdatei mit Edit-Bedarf — Fund aus der RED-Phase (Developer-Agent), siehe
    #1934 für die ausgegliederte Architekturfrage.

## Known Limitations

- Bereits ausgehende, historische Mails/SMS mit den alten Kürzeln (`K`, `FK`, `NL`, `Nacht`,
  `TagMin`, …) werden nicht rückwirkend korrigiert — reine Laufzeit-Registeränderung, keine
  Datenmigration.
- Die im Kontext-Dokument als offen markierte generelle Wächter-Erweiterung ("Negativliste
  deutscher Wortbestandteile für `col_label`", damit künftige Register-Einträge nicht erneut
  deutsche `col_label`-Werte einführen) ist Teil dieser Spec (siehe Implementation Details E,
  Test Plan Punkt 1) — eine pauschale `compact_label==sms_code`-Regel wird bewusst NICHT eingeführt,
  da sie bestehende, begründete Divergenzen brechen würde (`CT`≠`C`, `VS`≠`V`, `HP`≠`P`, `SU`≠`☀`).
- `sms_code`/`compact_label` (ADR-0042 Klasse 1, "Protokoll-Token") bleiben grundsätzlich von
  Sprachfragen ausgenommen — die K/FK/NL-Änderungen in dieser Spec sind Konsistenz-Fixes
  (Kollisionsvermeidung, Ableitungslogik), keine Sprachregel-Durchsetzung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0042 (bestehend, wird durch diesen Fix durchgesetzt, nicht geändert)
- **Rationale:** ADR-0042 Klasse 2 schreibt für `col_label` englische Kurzformen ≤6 Zeichen vor
  (bestätigt #862/#849: „Spaltenköpfe bleiben bewusst englisch"). Die sechs betroffenen Werte wurden
  alle **nach** dem ADR-Beschluss (2026-08-02) eingeführt und verletzen die Regel — dieser Fix stellt
  Konformität her, ohne die Regel selbst zu ändern. Die `sms_code`/`compact_label`-Änderungen
  (Klasse 1, von Sprachfragen ausgenommen) sind kein ADR-0042-Thema, sondern ein separater
  PO-Konsistenzentscheid (Kollisionsvermeidung, tote Literale bereinigen) — kein neues ADR nötig.

## Changelog

- 2026-08-17: Initial spec created (Issue #1926, PO-Freigabe im Chat, finale Werte-Tabelle inkl.
  Korrektur der ursprünglich erwogenen Kollisionswerte auf `L`/`FL`/`FZ`)
