---
entity_id: fix_994_telegram_vorlage
type: bugfix
created: 2026-07-03
updated: 2026-07-03
status: draft
workflow: fix-994-telegram-vorlage
---

# Telegram-Briefing: doppelter Header + kaputte Detail-Zeilen-Einheiten (Bug #994)

## Approval

- [ ] Approved

## Purpose

Behebt zwei unabhängige Formatierungsfehler in der Telegram-Briefing-Nachricht:
(1) ein doppelter Titel-Header mit doppelten eckigen Klammern und doppeltem
Trip-Namen, und (2) fehlerhaft angehängte Einheiten/Symbole in der
Detail-Zeile pro Stunden-Segment (z.B. `Cloud ☀%`, `Sun 1.0 h h`). Ziel ist
eine saubere, einmalige Kopfzeile und Detail-Werte, die ihre Einheit genau
einmal und nur dann zeigen, wenn sie nicht bereits im formatierten Wert
enthalten ist.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** Telegram-Send-Call innerhalb der Briefing-Versandmethode (Zeile ~634-638), `TelegramOutput(...).send(...)`

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `def _tg_extra_detail_line(layout, rows, fkeys) -> Optional[str]` (Zeile 279-304)

## Estimated Scope

- **LoC:** ~15-20 (Kern-Fix), plus Testdatei
- **Files:** 2 Source-Dateien (`src/services/trip_report_scheduler.py`, `src/output/renderers/narrow.py`) + 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/outputs/telegram.py::TelegramOutput.send()` | function | Bereits vorhandener `suppress_subject_line`-Parameter (Zeile 50-74) — wird für Fix #1 an der Call-Site in `trip_report_scheduler.py` aktiviert. |
| `src/output/subject.py::build_email_subject()` | function | Liefert `report.email_subject`, bereits geklammert (`[trip] stage — ...`) — Quelle des Header-Duplikats, wenn `telegram.py::send()` erneut klammert. |
| `src/output/renderers/narrow.py::render_narrow()` | function | Erzeugt `report.telegram_text` mit eigenem Header (trip_name + report_type + Datum, Zeile 434-441) — macht den zusätzlichen `[subject]`-Header überflüssig. |
| `src/output/renderers/email/helpers.py::fmt_val()` | function | Formatiert Zellwerte je Metrik/Modus (Zeile 447ff) — liefert für `cloud*` im Friendly-Modus reines Emoji, für `sunshine` im Roh-Modus bereits `"X h"` inkl. Einheit. Quelle des `val` in `_tg_extra_detail_line()`. |
| `src/app/metric_catalog.py::get_metric()` / `MetricDefinition.unit` | function/attribute | Liefert die Katalog-Einheit je Metrik, die `_tg_extra_detail_line()` aktuell blind anhängt. |
| `src/services/trip_alert.py` (Zeile 847-849, 999-1003) | reference pattern | Bereits etabliertes Vorbild für `suppress_subject_line=True` bei self-contained Telegram-Bodies. |

## Implementation Details

**Fix #1 — Header-Duplikat (`trip_report_scheduler.py`):**
Am Telegram-Send-Call (Zeile ~634-638) den Parameter `suppress_subject_line=True`
ergänzen, analog zum bereits etablierten Muster in `trip_alert.py`. Damit entfällt
das zusätzliche `[{subject}]\n\n`-Wrapping in `telegram.py::send()` (Zeile 74),
da `report.telegram_text` (aus `render_narrow()`) bereits eine eigene Kopfzeile
mit Trip-Name, Report-Typ und Datum enthält. Der Fallback
`body=report.telegram_text or report.email_plain` bleibt unverändert bestehen;
er ist im Briefing-Pfad praktisch unerreichbar, da `render_narrow()` immer
mindestens eine Header-Zeile emittiert (Zeile 434-441) — dies wird als
Code-Kommentar an der Call-Site festgehalten, nicht separat getestet.

**Fix #2 — Detail-Zeilen-Einheiten (`narrow.py::_tg_extra_detail_line()`):**
Die blinde Anhängung `f"{label} {val}{sep}{unit}"` wird durch eine generische,
wertbasierte Prüfung ersetzt: Die Einheit wird nur angehängt, wenn der Wert
eine Ziffer enthält UND nicht bereits mit der Einheit endet. Emoji-Werte
(reine Symbole, keine Ziffer) und bereits-formatierte Werte mit Einheit
(z.B. `"1.0 h"`) bleiben unverändert:

```python
has_digit = any(ch.isdigit() for ch in val)
already_has_unit = bool(unit) and val.rstrip().endswith(unit)
if unit and has_digit and not already_has_unit:
    parts.append(f"{_col_label_str(mid)} {val}{sep}{unit}")
else:
    parts.append(f"{_col_label_str(mid)} {val}")
```

Der Fix bleibt bewusst in `narrow.py` (Call-Site), nicht in `fmt_val()` selbst,
da `fmt_val()` auch für E-Mail-Tabellenzellen mit separater Einheiten-Legende
verwendet wird (Vertrag siehe `tests/unit/test_issue_347_sunshine_hours.py:266-314`)
— eine Änderung dort würde diesen Vertrag brechen.

**Bewusst außerhalb des Scope:** Das `cape`-Label/Einheit-Mismatch
(`col_label="Thndr%"` vs. `unit="J/kg"`, `metric_catalog.py:248-251`) ist ein
vorbestehendes, unabhängiges Problem und wird als eigenständiges Folge-Issue
(#996) behandelt.

## Expected Behavior

- **Input:** Ein Trip-Briefing (morning/evening) mit konfiguriertem Telegram-Versand,
  reale Segment-Wetterdaten inkl. Cloud- und Sunshine-Metriken in beiden
  Formatierungsmodi (raw/friendly).
- **Output:** Genau eine Kopfzeile (Trip-Name, Report-Typ, Datum) ohne doppelte
  eckige Klammern und ohne doppelten Trip-Namen. Detail-Zeilen pro Segment
  zeigen jede Einheit/jedes Symbol genau einmal, korrekt zugeordnet zum
  jeweiligen Formatierungsmodus.
- **Side effects:** Keine — reine String-Formatierung, keine Datenpersistenz,
  kein Cross-User-Effekt betroffen.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN ein Report mit `email_subject` und `telegram_text` (aus echten Trip-/Segment-Daten via `render_narrow()`) WHEN die Telegram-Send-Payload gemäß dem Fix-Aufruf (`suppress_subject_line=True`) konstruiert wird THEN enthält der resultierende Nachrichtentext (`telegram.py::send()`-Payload-Logik, Zeile 74) den Trip-Namen genau einmal und keine doppelten eckigen Klammern (`[[`/`]]`).
- [ ] Test 2: GIVEN Segment-Rows mit Cloud-Metriken im Friendly-Modus (Emoji-Werte aus echtem `fmt_val()`) WHEN `_tg_extra_detail_line()` mit diesen Rows aufgerufen wird THEN enthält die resultierende Detail-Zeile kein angehängtes `%` hinter dem Emoji.
- [ ] Test 3: GIVEN Segment-Rows mit Sunshine-Metrik im Roh-Modus (`fmt_val()` liefert `"X.X h"`) WHEN `_tg_extra_detail_line()` aufgerufen wird THEN erscheint `h` in der Detail-Zeile genau einmal.
- [ ] Test 4 (Regression): GIVEN Segment-Rows mit rein numerischen Metriken (z.B. `dewpoint`/`gust`) WHEN `_tg_extra_detail_line()` aufgerufen wird THEN bleibt die korrekte Einheit unverändert angehängt (kein Bruch durch den generischen Fix).

## Acceptance Criteria

- **AC-1:** Given ein Telegram-Briefing-Versand mit `report.email_subject` (bereits geklammert aus `build_email_subject()`) und `report.telegram_text` (mit eigenem Header aus `render_narrow()`) / When der Send-Call in `trip_report_scheduler.py` mit `suppress_subject_line=True` erfolgt / Then enthält der tatsächlich an die Telegram-API übergebene Nachrichtentext keine doppelten eckigen Klammern (`[[...]]`) mehr.
  - Test: Echter Aufruf der Payload-Konstruktion (`telegram.py::send()`-Nachrichtenlogik) mit realen `report.email_subject`/`report.telegram_text`-Werten aus einem echten Trip; geprüft wird der resultierende String, nicht eine gemockte HTTP-Response.

- **AC-2:** Given dieselbe Konfiguration wie AC-1 / When die Nachricht zusammengesetzt wird / Then erscheint der Trip-Name genau einmal im Gesamttext (nicht einmal im `[subject]`-Header und nochmal als erste Body-Zeile).
  - Test: String-Vorkommen-Zählung des Trip-Namens im realen zusammengesetzten Nachrichtentext (aus echten Report-Daten, kein Mock).

- **AC-3:** Given Segment-Daten mit Cloud-Metriken (`cloud_total`/`cloud_low`/`cloud_mid`/`cloud_high`) im Friendly-Modus, deren `fmt_val()`-Ergebnis ein reines Emoji ohne Ziffer ist / When `_tg_extra_detail_line()` die Detail-Zeile baut / Then wird kein `%`-Zeichen hinter dem Emoji angehängt.
  - Test: `_tg_extra_detail_line()` mit echten, aus dem Formatter erzeugten Segment-Rows aufrufen und den zurückgegebenen String auf Abwesenheit von `%` direkt nach einem Emoji prüfen.

- **AC-4:** Given Segment-Daten mit `sunshine`-Metrik sowohl im Roh-Modus (`fmt_val()` liefert `"X.X h"`) als auch im Friendly-Modus (reines Wetter-Emoji) / When `_tg_extra_detail_line()` die Detail-Zeile baut / Then erscheint die Einheit `h` im Roh-Modus genau einmal und im Friendly-Modus gar nicht (kein Anhängen an ein Emoji).
  - Test: `_tg_extra_detail_line()` für beide Modi mit echten Segment-Rows aufrufen und die Anzahl der Vorkommen von `h` als eigenständiges Einheiten-Token im Ergebnis-String zählen.

- **AC-5 (Regression):** Given Segment-Daten mit rein numerischen Detail-Metriken (z.B. `dewpoint`/`gust`/`cape`), deren `fmt_val()`-Ergebnis eine Ziffer ohne bereits enthaltene Einheit ist / When `_tg_extra_detail_line()` die Detail-Zeile baut / Then bleibt die Katalog-Einheit weiterhin korrekt angehängt wie vor dem Fix.
  - Test: `_tg_extra_detail_line()` mit echten numerischen Segment-Rows aufrufen und die korrekte Einheiten-Anhängung im Ergebnis-String verifizieren (Vergleich mit dem Vor-Fix-Verhalten für diese Metriken).

## Known Limitations

- Der Fallback `body=report.telegram_text or report.email_plain` in
  `trip_report_scheduler.py` bleibt unverändert und ungetestet, da er im
  Briefing-Pfad praktisch unerreichbar ist (`render_narrow()` liefert immer
  mindestens eine Header-Zeile).
- Das `cape`-Label/Einheit-Mismatch (`Thndr%` vs. `J/kg`) wird bewusst nicht
  mit adressiert — separates Folge-Issue #996.
- Der generische Fix in `_tg_extra_detail_line()` erkennt "Einheit bereits
  enthalten" über einen einfachen `endswith()`-Check auf den formatierten
  Wert; sollte eine zukünftige Metrik eine Einheit in der Mitte des Strings
  platzieren (aktuell nicht der Fall), müsste die Heuristik erweitert werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix an bestehender String-Formatierungslogik unter
  Wiederverwendung eines bereits etablierten Parameters (`suppress_subject_line`)
  und ohne neue Abstraktionsebene oder strukturelle Entscheidung. Der Fix bleibt
  bewusst in der bestehenden Funktion/Datei, um den etablierten Vertrag zwischen
  `fmt_val()` (E-Mail-Tabellen) und `_tg_extra_detail_line()` (Telegram-Detail-Zeile)
  nicht zu vermischen — keine ADR-würdige Weichenstellung.

## Changelog

- 2026-07-03: Initial spec created
