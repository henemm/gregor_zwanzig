# Context: Telegram vs Vorlage (#994)

## Request Summary
Der Nutzer meldet per Screenshot, dass die Telegram-Briefing-Nachricht nicht der
erwarteten Vorlage entspricht: doppelte eckige Klammern im Titel, doppelter
Trip-Name (einmal im Titel, einmal als erste Zeile des Bodys) und kaputte
Detail-Zeile pro Stunden-Segment (`Cloud ☀%`, `Sun 1.0 h h`).

## Related Files

| File | Relevance |
|------|-----------|
| `src/outputs/telegram.py` | `send()` (Zeile 51-74) — wrapt `subject` immer in `[{subject}]`, außer `suppress_subject_line=True`. Bereits vorhandener Escape-Hatch. |
| `src/services/trip_report_scheduler.py` | Zeile 634-638 — ruft `TelegramOutput.send(subject=report.email_subject, body=report.telegram_text or report.email_plain)` **ohne** `suppress_subject_line=True`. Root Cause #1. |
| `src/services/trip_alert.py` | Zeile 847-849, 999-1003 — nutzt bereits `suppress_subject_line=True` für self-contained Bodies. Referenz-Pattern für den Fix. |
| `src/output/subject.py` | `build_email_subject()` (Zeile 148ff) — baut `[{trip}] {stage_name} — {report} — ...`. Liefert bereits geklammerten String, der als `report.email_subject` überall (E-Mail, SMS, Telegram) wiederverwendet wird. |
| `src/output/renderers/narrow.py` | `render_narrow()` (Zeile 402-544) — Telegram-Body beginnt selbst mit eigener Kopfzeile (`trip_name` + `report_type` + Datum, Zeile 430-441). Macht den `[subject]`-Header von `telegram.py` redundant für den Briefing-Pfad. |
| `src/output/renderers/narrow.py` | `_tg_extra_detail_line()` (Zeile 279-304) — Root Cause #2: hängt Katalog-`unit` blind an den bereits formatierten Zellwert an (`f"{label} {val}{sep}{unit}"`), ohne zu prüfen ob `val` (aus `fmt_val`) die Einheit/ein Symbol schon enthält. |
| `src/output/renderers/email/helpers.py` | `fmt_val()` (Zeile 447-592) — Quelle der Werte für `_cell()`. Für `cloud*` liefert im Friendly-Modus ein reines Emoji (Zeile 530-543, kein `%`-Anhängen vorgesehen). Für `sunshine` liefert im Nicht-Friendly-Modus bereits `f"{hours:.1f} h"` inkl. Einheit (Zeile 544-551). |
| `src/app/metric_catalog.py` | `MetricDefinition` (Zeile ~78ff) — `col_label`/`unit` je Metrik, u.a. `cape`: `col_label="Thndr%"`, `unit="J/kg"` (Zeile 248-251) — Label/Einheit-Mismatch, evtl. eigenständiger Folgefund, kein Teil des Kern-Fixes.

## Existing Patterns

- **`suppress_subject_line`-Flag existiert bereits** in `TelegramOutput.send()` genau für den Fall "Body ist selbst-enthaltend, kein zusätzlicher `[subject]`-Header nötig". `trip_alert.py` nutzt es an zwei Stellen. Der Briefing-Versand in `trip_report_scheduler.py` ist der einzige Telegram-Call-Site, der es **nicht** setzt, obwohl `report.telegram_text` (aus `render_narrow()`) exakt dasselbe Muster (eigener Header) erfüllt.
- **`fmt_val()` kennt zwei Modi** pro Metrik (`raw` vs. `friendly`/`use_friendly`) — für `cloud*` wechselt der Rückgabetyp zwischen Zahl (roh) und Emoji (friendly), für `sunshine` zwischen `"X h"` (roh, inkl. Einheit) und Wetter-Emoji (friendly). `_tg_extra_detail_line()` behandelt beide Fälle identisch wie einen reinen Zahlenwert und hängt immer die Katalog-Einheit an.

## Dependencies

- **Upstream:** `report.email_subject` (aus `output/subject.py::build_email_subject`), `report.telegram_text` (aus `formatters/trip_report.py` → `output/renderers/narrow.py::render_narrow`).
- **Downstream:** Nur `src/services/trip_report_scheduler.py:634-638` (Telegram-Briefing-Versand) ist vom Header-Duplikat betroffen. Andere `TelegramOutput.send()`-Aufrufer (`trip_alert.py`, `inbound_telegram_reader.py` für Bot-Antworten) sind unabhängig und bereits korrekt bzw. nutzen andere Bodies.
- `_tg_extra_detail_line()` wird nur aus `render_narrow()` für `channel == "telegram"` aufgerufen (Zeile 458-460) — Fix ist auf den Telegram-Kanal beschränkt, Signal-Pfad (falls noch code vorhanden) nutzt `_detail_lines()` (andere Funktion, nicht betroffen).

## Existing Specs

- `docs/specs/modules/issue_360_signal_channel_renderer.md` — Ursprungs-Spec für `render_narrow()`/`_tg_extra_detail_line()` (kanal-bewusster Renderer, Epic #331). Definiert Grundformat, aber keine explizite Regel zur Einheiten-Behandlung bei Emoji-/bereits-formatierten Werten — das ist die Lücke, die #994 aufdeckt.

## Analysis

### Type
Bug (zwei unabhängige, gegengeprüfte Root Causes — Verdict: CONFIRMED durch `analysis-challenger`).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/trip_report_scheduler.py` | MODIFY | `TelegramOutput.send(...)`-Aufruf (Zeile ~635-638) um `suppress_subject_line=True` ergänzen — verhindert doppelte Klammern + doppelten Trip-Namen, da `report.telegram_text` bereits einen eigenen Header trägt. |
| `src/output/renderers/narrow.py` | MODIFY | `_tg_extra_detail_line()` (Zeile 279-304): Einheiten-Anhängung generisch/wertbasiert machen statt blind. |
| Test-Datei (neu/erweitert) | CREATE/MODIFY | Echter Test gegen `render_narrow()` + `TelegramOutput.send()`-Payload mit realen Trip-Daten (kein Mock, Projektregel). Idealerweise zusätzlich Live-Verifikation über Staging-Telegram-Bot. |

### Scope Assessment
- Files: 2 Source-Dateien + 1 Test-Datei
- Estimated LoC: ~15-20 (Kern-Fix), gut unter dem 250-LoC-Workflow-Limit
- Risk Level: LOW (reine String-Formatierung, pure Functions, deterministisch reproduzierbar, kein Race/Platform-Bezug)

### Technical Approach

**Fix #1 — Header-Duplikat:** In `trip_report_scheduler.py` beim Telegram-Send-Call `suppress_subject_line=True` setzen (Pattern bereits etabliert in `trip_alert.py:847-850`/`:999-1003`). Bewusst dokumentierter Rand-Fall: `body=report.telegram_text or report.email_plain` — der `email_plain`-Fallback ist im Briefing-Pfad praktisch unerreichbar, da `render_narrow()` immer mindestens eine Header-Zeile emittiert (`narrow.py:434-441`); wird als Code-Kommentar/AC-Hinweis festgehalten, nicht separat abgesichert.

**Fix #2 — Detail-Zeilen-Einheiten:** In `_tg_extra_detail_line()` (`narrow.py`) generische, wertbasierte Erkennung statt Metrik-ID-Sonderfälle (deckt automatisch `cloud_total`, `cloud_low`, `cloud_mid`, `cloud_high` sowie sowohl den Sunshine-Raw-Fall (`"1.0 h"`) als auch den Sunshine-Friendly-Emoji-Fall (`☀️` + `h`) ab, ohne bei rein numerischen Metriken etwas zu ändern):

```python
has_digit = any(ch.isdigit() for ch in val)
already_has_unit = bool(unit) and val.rstrip().endswith(unit)
if unit and has_digit and not already_has_unit:
    parts.append(f"{label} {val}{sep}{unit}")
else:
    parts.append(f"{label} {val}")
```

Fix muss im Call-Site (`narrow.py`) bleiben, NICHT in `fmt_val()` selbst — sonst bricht der bestehende Vertrag für E-Mail-Tabellen-Zellen (separate Einheiten-Legende, siehe `tests/unit/test_issue_347_sunshine_hours.py:266-314`).

**Bewusst außerhalb des Scope:** `cape`-Label/Einheit-Mismatch (`col_label="Thndr%"` vs. `unit="J/kg"`, `metric_catalog.py:248-251`) — vorbestehendes, unabhängiges Problem. Wird als Folge-Issue angelegt (Memory-Regel: „IMMER Folge-Issue für Nebenbefunde").

### Dependencies
Siehe Context-Sektion oben — keine neuen Erkenntnisse durch die Analyse-Phase.

### Open Questions
- [x] Keine offenen Fragen — Adversary-Gegenprüfung durch `analysis-challenger` bestätigt beide Root Causes und liefert einen konkreten, generischen Fix-Vorschlag für #2.

## Risks & Considerations

- **Scope-Grenze:** Das `col_label`/`unit`-Mismatch bei `cape` (`Thndr%` + `J/kg`) ist ein separates, älteres Problem im Metrik-Katalog (nicht durch #994 verursacht) — sollte als Folge-Issue dokumentiert werden, nicht im selben Fix mitgezogen werden (Scope-Explosion vermeiden).
- **Nicht alle Metriken sind betroffen:** Nur Metriken, deren `fmt_val()`-Rückgabe im aktuellen Format-Modus bereits eine Einheit/ein Symbol enthält (`cloud*` im Friendly-Modus, `sunshine` im Roh-Modus), produzieren die doppelte/falsche Einheit. Der Fix in `_tg_extra_detail_line()` muss generisch genug sein, um für beide Fälle zu greifen, ohne andere Metriken (z. B. `dewpoint`/`Cond°`, die eine reine Zahl liefern und korrekt `°C` brauchen) zu brechen.
- **Kein Mock-Test möglich** (Projekt-Regel): Der TDD-Test muss die tatsächliche Telegram-Nachricht über die Staging-Bot-Instanz verifizieren (`reference_staging_telegram_bot.md` aus Memory) oder zumindest `render_narrow()`/`TelegramOutput.send()`-Payload-Aufbau end-to-end mit echten Trip-Daten prüfen — keine gemockten HTTP-Calls für den Beweis des Bugs.
- **Zwei unabhängige Root Causes** in unterschiedlichen Dateien — beide sollten in derselben Spec mit je eigenem AC abgedeckt werden, da sie unabhängig voneinander testbar/verifizierbar sind.
