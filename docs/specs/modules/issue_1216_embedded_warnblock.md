---
entity_id: issue_1216_embedded_warnblock
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [official-alerts, email, compare, trip-briefing, alert-trigger, convergence]
---

# Geteilter WarnBlock — amtliche Warnung eingebettet im Briefing (#1216, embedded)

## Approval

- [x] Approved (PO 'go', 2026-07-11)

## Purpose

Ein **geteilter WarnBlock-Renderer** (`variant="standalone"|"embedded"`) ersetzt die drei divergenten Ist-Darstellungen amtlicher Warnungen in Trip-Briefing, Ortsvergleich und Standalone-Alarm durch EINEN Baustein nach der Design-Vorlage `docs/design-requests/issue_1216_warn_im_briefing/Gregor 20 - Warnung im Briefing.html`: Severity-Dot, Eyebrow „Amtliche Warnung", Count-Zeile, Quelle-Link, pro Warnung Meter/Stufen-Wort+Position/Typ/Zeitraum/Route-Chips. Struktur-Treue zur Vorlage ist Ziel, **nicht** Farb-Treue — Farben bleiben die bestehenden Code-Tokens.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` (MODIFY) — neuer `render_warn_block(notices, *, variant, source_label, source_url, stand_at, tz)`; `render_official_alert_html` und `render_official_alerts_html` werden Thin-Wrapper darauf
- **File:** `src/output/renderers/email/html.py` (MODIFY) — Trip: Notices bauen, WarnBlock(embedded) nach Header, vor Tageslage
- **File:** `src/output/renderers/email/compare_html.py` (MODIFY) — `_render_warn_lead` durch WarnBlock(embedded, Orts-Scope) ersetzt/erweitert; Matrix-Zeile + Pro-Ort-Streifen unverändert
- **File:** `src/services/notification_service.py` (MODIFY) — `source_label`/`source_url` per Mapping statt hartkodiert „GeoSphere Austria" (Zeilen 481, 574)
- **Identifier:** `render_warn_block`, `_render_location_section`, `_render_warn_lead`, `send_official_alert`, `send_multi_location_official_alert`

Schicht: **Python-Core / Domain-Backend** (`src/output/renderers/`, `src/services/`).

## Estimated Scope

- **LoC:** ~250–300 (Renderer-Umbau + drei Flächen + Mapping + Golden-Regen) → **LoC-Override nötig** (PO-Freigabe im GREEN-Schritt einholen, siehe Known Limitations)
- **Files:** 4 MODIFY (Kern-Renderer, Trip-HTML, Compare-HTML, Notification-Service) + Golden-Fixtures + Tests
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlertNotice` DTO (`official_alerts.py:56-65`) | reuse | Kontext-agnostisches Praesentations-DTO, bereits gemeinsam fuer Trip/Compare |
| `build_official_alert_notices` / `build_compare_official_alert_notices` | reuse | Bauen Notices mit Segment- bzw. Orts-Scope; liefern die Eingabe fuer `render_warn_block` |
| `_LEVEL_WORDS`, `_LEVEL_POSITION`, `_ladder_html`, `_meter_html`, `_chip_html`, `_hazard_display`, `_format_validity`, `format_segment_reference` | reuse | Bestehende Basis-Helfer, bleiben unveraendert als Bausteine von `render_warn_block` |
| `dedupe_official_alerts`, `collect_trip_alert_entries` | reuse | Dedup-Pfad fuer Trip-Notices vor dem Rendern |
| `design_tokens.G_ALERT_L2/L3/L4`, `G_SUCCESS` | reuse | Bestehende Farb-Tokens — PO-Entscheidung: **nicht** durch Design-Hex ersetzt |
| `CV2_METRICS`, `_render_location_section`, `_render_overview_table` (`compare_html.py`) | reuse | Bestehende Matrix-Warn-Zeile + Pro-Ort-Streifen, bleiben unveraendert erhalten |
| `EmailOutput.send(mail_type=...)`, `renderer_mail_gate` (#811) | gate | Jede geaenderte Datei ist Mail-Inhalt — Commit-Gate erzwingt Matrix-Test + `briefing_mail_validator.py` vor Commit |

## Implementation Details

### Kern: `render_warn_block(notices, *, variant, source_label, source_url, stand_at, tz)`
Neue Funktion in `official_alerts.py`, emittiert die `.wb`-Struktur der Design-Vorlage: Dot (Farbe nach `_LEVEL_WORDS`/Farb-Tokens), Eyebrow „Amtliche Warnung", Count-Zeile (`"{n} aktiv · höchste Stufe {WORT}"` bei gemischten Stufen, `"{n} aktiv · Stufe {WORT} ({pos}/3)"` bei einheitlicher Stufe), Quelle-Link (`source_label` verlinkt auf `source_url`, falls vorhanden), pro Warnung eine `wb-item`-Zeile mit Meter (nur bei gemischten Stufen, via `_meter_html`), Stufen-Wort+Position, Typ (`_hazard_display`), Zeitraum (`_format_validity`), Route/Umfang-Chips (`_chip_html` über `affected_chips`/`free_chips`).

`variant="standalone"` ergänzt zusätzlich die H1-Headline (`render_official_alert_subject`-Text als Überschrift) und den Verdict-Chip + die uniforme Leiter (`_ladder_html`) — bestehendes Verhalten von `render_official_alert_html`, jetzt als Aufruf von `render_warn_block(variant="standalone")` realisiert (Thin-Wrapper, Rückwärtskompatibilität der öffentlichen Signatur bleibt erhalten).

`variant="embedded"` liefert die kompakte Bannerform ohne H1/Verdict/Leiter — bei gemischten Stufen Meter je Warnung, bei einheitlicher Stufe das Format `"Stufe {WORT} ({pos}/3)"` statt der Leiter.

### Trip-Briefing (`email/html.py`)
Notices werden aus `segments` via `dedupe_official_alerts` + Segment-Chips (`format_segment_reference`) gebaut (Bestandslogik aus Zeilen 1416-1423 bleibt, liefert jetzt `OfficialAlertNotice`s statt `(label, [alert])`-Tupel). `render_warn_block(notices, variant="embedded", ...)` ersetzt `official_alerts_html` und wird **nach `{header_html}` (Zeile 1525), vor `{stability_html}`/`{tageslage_html}`** eingefügt (heute liegt der Block bei `{changes_html}{official_alerts_html}` nach Tageslage, Zeile 1531 — Umstellung der Reihenfolge). Keine Warnung → leerer String, kein Platzhalter.

### Ortsvergleich (`email/compare_html.py`)
Neuer Aggregat-Banner = `render_warn_block(notices, variant="embedded", ...)` mit Orts-Scope (Count-Zeile „höchste Stufe {WORT} · {Ort}" bzw. „{n} von {total} Orten"), ersetzt/erweitert `_render_warn_lead` (Zeilen 313-354). Notices werden über `build_compare_official_alert_notices` aus den Ort-Alerts gebaut. **Unverändert bleiben:** die Matrix-Warn-Zeile (`CV2_METRICS`-Eintrag `"warn"`, Zeile 90, Zellen-Rendering Zeilen 238-244) und der Pro-Ort-Streifen (`_render_location_section`, Aufruf `render_official_alerts_html` Zeilen 443-445) — additiver Umbau, kein Entfernen (PO-Entscheidung Frage D).

### Standalone-Alarm (`notification_service.py`)
`send_official_alert` (Trip, Zeile ~481) und `send_multi_location_official_alert` (Compare, Zeile ~574) rufen `render_warn_block(dto_notices, variant="standalone", source_label=..., source_url=..., ...)` statt der bisherigen `render_official_alert_html`. Betreff (`render_official_alert_subject`), Telegram (`render_official_alert_telegram`), SMS (`render_official_alert_sms`) und der Plain-Notice-Pfad (`render_official_alert_notice_plain`) bleiben **unverändert** — nur der HTML-Body wird auf den geteilten Baustein umgestellt.

### source→Name/URL-Mapping
Neue Mapping-Funktion (analog dem Provider-Namens-Pattern in `providers/geosphere.py`/`services/official_alerts/vigilance.py`): `alert.source` → Anzeigename (`geosphere_warn`→„GeoSphere Austria", `meteofrance_vigilance`→„Météo-France", DWD-Quelle→„DWD"), Link aus `alert.url` (Feld existiert bereits im `OfficialAlert`-Modell). Ersetzt die hartkodierten `source_label = "GeoSphere Austria"`-Zeilen in `notification_service.py:481` und `:574`. Bei mehreren Quellen unter denselben Notices (Mischfall) wird die Quelle der führenden (höchststufigen) Warnung angezeigt.

### Golden-Emails
`tests/golden/email/*` (u.a. `corsica-vigilance`) werden nach dem Umbau via `regenerate.py` neu erzeugt und manuell auf Struktur-Konsistenz geprüft (Diff-Review, kein automatisches Overwrite ohne Sichtprüfung).

## Expected Behavior

- **Input:** `list[OfficialAlertNotice]` (bereits dedupliziert, Segment- oder Orts-Scope) + `variant`/`source_label`/`source_url`/`stand_at`/`tz`.
- **Output:** HTML-Fragment (`embedded`) bzw. vollständiges HTML-Dokument (`standalone`) mit identischer Severity-Grammatik über alle drei Flächen; leere Notice-Liste → embedded liefert `""`, standalone wird nicht aufgerufen (kein Alarm ohne Warnung).
- **Side effects:** keine (reine Renderer-Funktion); Aufrufer (`html.py`, `compare_html.py`, `notification_service.py`) reichen Notices/Metadaten durch.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Briefing mit mindestens einer aktiven amtlichen Warnung im Segment / When das HTML gerendert wird / Then erscheint der WarnBlock als erstes inhaltliche Element direkt nach dem Header und vor der Tageslage, mit Dot, Eyebrow „Amtliche Warnung", Count-Zeile, Quelle-Link und je Warnung Typ/Zeitraum/Route-Chip.
  - Test: `render_trip_report_html` mit präparierten Segmenten inkl. Alert; Assert Reihenfolge (Header-Marker vor Tageslage-Marker vor Warn-Block-Marker in der HTML-Ausgabe) + Vorhandensein aller Struktur-Elemente.

- **AC-2:** Given ein Trip-Briefing ohne amtliche Warnung / When das HTML gerendert wird / Then entfällt der WarnBlock ersatzlos — kein „alles ruhig"-Platzhalter, kein leeres `.wb`-Div im Markup.
  - Test: `render_trip_report_html` ohne Alerts; Assert keine `wb-`-Klassen/kein WarnBlock-Marker im Output.

- **AC-3:** Given zwei Warnungen unterschiedlicher Stufe (GELB + ORANGE) / When der WarnBlock gerendert wird / Then zeigt jede Warnzeile ihr eigenes Meter + „höchste Stufe ORANGE" in der Count-Zeile; sind alle Warnungen derselben Stufe, erscheint stattdessen die Leiter (standalone) bzw. „Stufe {WORT} ({n}/3)" (embedded) ohne Meter.
  - Test: `render_warn_block` mit gemischten vs. einheitlichen Notice-Listen, je `variant="embedded"` und `variant="standalone"`; Assert Meter-Präsenz/-Absenz und Count-Text exakt.

- **AC-4:** Given ein Ortsvergleich mit amtlichen Warnungen an 6 von 7 Orten, höchste Stufe ROT an Marseille / When das Compare-HTML gerendert wird / Then zeigt der Aggregat-Banner „höchste Stufe ROT · Marseille" bzw. „6 von 7 Orten"; die bestehende Matrix-Warn-Zeile und der Pro-Ort-Warn-Streifen bleiben zusätzlich und unverändert im Output vorhanden.
  - Test: `render_compare_html` mit 7 Test-Orten, 6 mit Alert; Assert Banner-Count-Text + Matrix-`warnrow`-Zelle + Pro-Ort-`_render_location_section`-Streifen alle drei gleichzeitig im HTML.

- **AC-5:** Given eine Standalone-Alarm-Mail (Trip oder Compare) mit amtlichen Warnungen / When `render_warn_block(..., variant="standalone")` läuft / Then ist das HTML strukturell äquivalent zur bisherigen `render_official_alert_html`-Ausgabe (H1-Headline, Verdict, Leiter bei einheitlicher Stufe) und die bestehenden Fidelity-Tests bleiben grün.
  - Test: `tests/tdd/test_952_alert_mail_*fidelity.py`, `tests/tdd/test_957_alert_mail_*fidelity.py`, `test_official_alert_template_render` — Regressionslauf nach Umbau, alle grün ohne Anpassung der Assertions (Farben unverändert).

- **AC-6:** Given eine Standalone-Alarm-Mail vor und nach dem Umbau auf `render_warn_block` / When Betreff, SMS-Text, Telegram-Text und Plain-Notice-Text verglichen werden / Then sind sie textuell identisch — nur der HTML-Body ändert sich strukturell.
  - Test: Snapshot-Vergleich `render_official_alert_subject`/`render_official_alert_sms`/`render_official_alert_telegram`/`render_official_alert_notice_plain` vor/nach Umbau mit identischen Notice-Fixtures; Assert Byte-Gleichheit.

- **AC-7:** Given amtliche Warnungen aus GeoSphere, Météo-France und einer dritten Quelle (DWD-Fixture) / When der WarnBlock die Quelle-Zeile rendert / Then zeigt sie den korrekten Anzeigenamen („GeoSphere Austria", „Météo-France", „DWD") mit Link auf `alert.url`, statt des bisher hartkodierten „GeoSphere Austria" für alle Quellen.
  - Test: Notice-Fixtures mit `alert.source` je Quelle + `alert.url` gesetzt; Assert Anzeigename + `href` je Quelle in allen drei Flächen (Trip, Compare, Standalone).

- **AC-8:** Given die Design-Vorlage nutzt andere Hex-Werte als der Bestandscode / When der WarnBlock gerendert wird / Then verwendet er ausschließlich die bestehenden Code-Farb-Tokens (`G_ALERT_L2 #9a6f00`, `G_ALERT_L3 #c8482a`, `G_ALERT_L4 #6d28d9`) — kein Design-Hex-Wert taucht im generierten HTML auf.
  - Test: HTML-Output nach Farb-Substrings aus der Design-Vorlage (`#e8b81f`, `#e07a1e`, `#c43030`) durchsuchen; Assert Abwesenheit, stattdessen Assert Präsenz der Bestands-Tokens.

- **AC-9:** Given der Renderer-Umbau ist abgeschlossen / When `tests/golden/email/regenerate.py` läuft / Then sind alle betroffenen Golden-Fixtures (u.a. `corsica-vigilance`) neu erzeugt, manuell auf Struktur-Konsistenz geprüft und die zugehörigen Golden-Tests grün.
  - Test: `pytest tests/golden/email/` nach Regenerierung; Assert alle Golden-Vergleiche grün, Diff-Review-Notiz im PR/Commit.

## Test Plan

Konsolidierte Test-Checkliste (Kern-Schicht, deterministisch, kein Netz — siehe Test-Politik Zwei-Schichten):

- [ ] `tests/tdd/test_issue_1216_warn_block_render.py` (NEU): Struktur-Tests für `render_warn_block` — Platzierung (AC-1), Leer-Fall (AC-2), Meter-vs-Leiter-Logik (AC-3), Farb-Token-Grenze (AC-8)
- [ ] `tests/tdd/test_issue_1216_compare_warnblock.py` (NEU oder Erweiterung bestehender Compare-Alert-Tests): Aggregat-Banner + Matrix-Zeile + Pro-Ort-Streifen gleichzeitig (AC-4)
- [ ] `tests/tdd/test_952_alert_mail_*fidelity.py`, `tests/tdd/test_957_alert_mail_*fidelity.py`, `test_official_alert_template_render` (BESTAND, Regressionslauf): müssen ohne Assertion-Änderung grün bleiben (AC-5)
- [ ] Snapshot-Vergleich Betreff/SMS/Telegram/Plain vor/nach Umbau (AC-6)
- [ ] Quelle-Mapping-Test mit GeoSphere-/Météo-France-/DWD-Fixtures über alle drei Flächen (AC-7)
- [ ] `tests/tdd/test_issue_811_mode_matrix.py` grün (Renderer-Mailgate #811 Pflicht vor Commit, da `email/html.py`/`compare_html.py` Briefing-Dateien sind)
- [ ] `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen echte Staging-Mail (Trip + Compare) grün — Pflicht vor „E2E bestanden"
- [ ] `pytest tests/golden/email/` nach `regenerate.py`-Lauf grün (AC-9)

Live-E2E (nur `/e2e-verify`, nicht Commit-Gate): echte Trip-Briefing- und Compare-Mail auf Staging mit aktiver amtlicher Warnung bzw. Fixture-Fake-Alert-Seam, IMAP-Verifikation + Struktur-Fidelity gegen die Design-Vorlage.

## Known Limitations

- **Farb-Treue zur Design-Vorlage bewusst NICHT gegeben** (PO-Entscheidung 2026-07-11): der WarnBlock nutzt die bestehenden Code-Farb-Tokens (`G_ALERT_L2/L3/L4`), nicht die `.wb`-Hex-Werte der Vorlage. Struktur-Treue (Layout, Grammatik, Platzierung) ist der Maßstab, Pixel-Diff-Gates laufen entsprechend gegen eine an die Bestandsfarben angepasste Referenz, nicht gegen die rohe Design-HTML.
- **LoC-Override > 250 nötig** — PO-Freigabe im GREEN-Schritt einholen (`workflow.py set-field loc_limit_override 500`), nicht eigenmächtig setzen.
- Compare-Pro-Ort-Streifen bleibt bewusst dreifach redundant zum neuen Banner (additiv, PO-Entscheidung Frage D) — kein Aufräumen in dieser Slice.
- Renderer-Mailgate (#811) betrifft alle drei geänderten Dateien; `official_alerts.py` zusätzlich als Radar-Datei (No-Op-Pfad), `email/html.py`/`compare_html.py` als Briefing-Dateien (Matrix-Test + Live-Validator Pflicht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (gemeinsamer Official-Alert-Renderer) — bestehend, additiv erweitert um den `variant`-Parameter. Keine neue ADR nötig: die Konsolidierung folgt der bereits etablierten Architektur-Leitplanke „ein gemeinsamer Renderer statt Kopie" (Epic #1073 Punkt 6).
- **Rationale:** Der geteilte Baustein ist die konsequente Fortsetzung des bestehenden `OfficialAlertNotice`-DTO-Ansatzes (bereits kontext-agnostisch für Trip/Compare) auf die visuelle Ebene — kein neues Architekturmuster, sondern Anwendung des bestehenden.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1216, embedded WarnBlock (Full-Process-Workflow)
