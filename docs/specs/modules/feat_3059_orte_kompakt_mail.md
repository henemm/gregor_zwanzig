---
entity_id: feat_3059_orte_kompakt_mail
type: feature
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: feat-3059-orte-kompakt-zusatzbloecke
tags: [issue-3059, epic-3047, orte, email-format, kompakt, adr-0124]
---

# E-Mail-Format „Kompakt“ für Orte

## Approval

- [ ] Approved

## Purpose

Orte-Abos können wie Trips wahlweise als ausführliche oder als kompakte Text-Mail zugestellt werden. Die kompakte Mail zeigt je Ort eine Zeile mit den gewählten Werten und passt auf einen Blick, auch bei schlechtem Empfang. Bestehende Orte-Abos bleiben unverändert ausführlich.

## Source

- **File:** `src/services/compare_briefing_aufbau.py`
- **Identifier:** `compare_email_rendern` (Abzweig), neuer Renderer `render_compare_compact`

## Scope

### Nicht im Scope

- Zusatzblock „Vergleich mit gestern“ für Orte: ausgelagert nach #3342 (neuer Datenpfad mit datierten Snapshots).
- Etappen-Kennzahlen und Nacht-Stundentabelle für Orte: nicht vorgesehen (PO-Entscheidung 2026-11-24, Kommentar in #3059).
- Migration/Aufräumen aus Phase 3 (#3102) und Orte anlegen / Zustellung (#3333).
- Kein Go-Strukturwechsel: `display_config` ist dort eine Map.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/report_config_resolver.py` | MODIFY | `CompareRenderOptions.email_format` ("full" Vorgabe) aus `display_config.email_format` |
| `src/output/renderers/email/compact_compare.py` | CREATE | `render_compare_compact`: ASCII-Text, eine Zeile je Ort, Ausblick optional, 2-KB-Grenze, Kürzung |
| `src/services/compare_briefing_aufbau.py` | MODIFY | Abzweig vor dem HTML-Aufbau: Kompakt gibt `("", text)` zurück (Versand, Vorschau, Testversand gleich) |
| `src/services/notification_service.py` | MODIFY | `send_compare_report`: leeres HTML sendet `html=False, mail_format="compact"` (Header `X-GZ-Format: compact`), auch im mail_sink-Zweig |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Δ-Anker-Reset (#1629) auch im Kompaktpfad nur nach erfolgreichem Versand |
| `src/services/compare_preview_service.py`, `src/services/placements_view_service.py` | MODIFY | Vorschau zeigt Kompakttext; Block-Liste Orte kennt `email_format` |
| `src/i18n/` (Katalog, DE/EN) | MODIFY | Texte „+N Orte nicht gezeigt“ und Kopf-/Fußzeilen der Kompakt-Mail |
| `.claude/hooks/email_spec_validator.py` | MODIFY | Kompakt-Zweig (ein text/plain-Teil, ASCII, `X-GZ-Format`, < 2 KB) |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | `orte_soll` kennt `email_format` |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json`, `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | Format-Dimension `kompakt` für Orte |
| `tests/tdd/test_orte_kompakt_mail.py` | CREATE | Renderer, Versand-Header, Resolver, Zwei-Nutzer, Anker-Reset |
| `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` | MODIFY | Format-Schalter auch im Kontext „vergleich“ (neues Kontext-Flag statt `tripBloecke`); bei Kompakt Stundenverlauf gesperrt, Ausblick wirksam |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | MODIFY | Vergleich-Nutzlast schreibt `email_format` per Read-Modify-Write |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | MODIFY | Texte nicht mehr Trip-formuliert |
| `docs/adr/0124-was-steht-wo-eine-tabelle.md` | MODIFY | Nachtrag zu Nr. 6/7 (keine stille Umkehr) |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Verweise Nr. 6, :97, :329 nachziehen |
| `docs/reference/renderer_email_spec.md`, `docs/reference/api_contract.md` | MODIFY | Routing-Zeile `compare/compact`, Feld `display_config.email_format` |

### Estimated Changes

- Files: ~18
- LoC: +700/-30 inklusive Tests und Doku (Code ca. 450)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0121 / `report_config_resolver` | module | Auflösung der Einstellungen je Kanal |
| ADR-0124, feat_3122 Nr. 6 | spec | Ausblick steuert allein `outlook_reports`, übrige Block-Schalter ignoriert (#722, PO #3160) |
| `fold_ascii` (`src/output/renderers/email/compact.py`) | function | ASCII-Faltung, `_severity_prefix` für Warnmarker |
| `EmailOutput.send(mail_format=…)` | function | einzelner text/plain-Teil, `X-GZ-Format` |
| ADR-0104 / Katalog | module | DE/EN-Texte, Protokoll-Token nie übersetzt |
| `compare_weather_snapshot.py` | module | Δ-Anker-Reset nach Versand (#1629) |
| `briefing_mail_validator.py` | hook | Vorlage für den Kompakt-Zweig |

## Implementation Details

- **Feld:** `display_config.email_format` ("full" | "compact"); fehlend = "full". Wie `telegram_style` liegt es in `display_config` des Orte-Abos. Speichern per Read-Modify-Write: nur `email_format` wird überschrieben, `telegram_style` und alle anderen Felder bleiben erhalten.
- **Signal „Kompakt“:** wie beim Trip ein leeres HTML aus dem Aufbau; kein eigenes Flag im Versandpfad. `compare_email_rendern` ist der einzige gemeinsame Punkt für Versand, Vorschau und Testversand.
- **Inhalt der Kompakt-Mail:** Kopf mit Bereichsname „Orte“/„Locations“ und Datum; eine Zeile je Ort (Name plus die für die E-Mail gewählten Metriken, Warnmarker bei amtlicher Warnung); je Ort eine 3-Tages-Ausblick-Zeile nur wenn der Ausblick eingeschaltet ist; Fußzeile. Kein Stundenverlauf; Block-Schalter außer dem Ausblick werden ignoriert. Kein SMS-Text als Mail.
- **Format:** ein einzelner text/plain-Teil, 7bit, nur ASCII (`fold_ascii`), Header `X-GZ-Format: compact`, `X-GZ-Mail-Type: compare`, `X-GZ-Lang`.
- **Größe:** Obergrenze 2 KB. Wird sie überschritten, werden Orte vom Listenende gekürzt und die Zeile „+N Orte nicht gezeigt“ (EN „+N locations not shown“, Katalog) angehängt; die Grenze gilt inklusive dieser Zeile.
- **Sprache:** Texte aus dem Katalog nach `language` des Nutzers; Ortsnamen und Kürzel bleiben unübersetzt.
- **Δ-Anker (#1629):** der Anker wird nur nach erfolgreichem Versand zurückgesetzt, im Kompaktpfad genauso.
- **Mandantentrennung:** `user_id` aus dem Auth-Kontext, nie `"default"`; „Senden“ geht an die Empfänger dieses Nutzers.
- **Kanäle:** E-Mail ändert sich. Telegram, SMS und Premium-SMS behalten Inhalt und Form; `email_format` und `telegram_style` sind unabhängig.
- **Editor:** die geteilte Karte „Was steht wo“ zeigt den Format-Schalter auch im Kontext „vergleich“ (Teilungs-Gate #1170, kein eigener Orte-Baustein). Bei Kompakt ist der Stundenverlauf-Schalter gesperrt, der Ausblick-Schalter bleibt wirksam. Texte sind neutral für Trip und Orte, DE/EN.
- **Reihenfolge:** Resolver, dann Renderer, Versand, Validator und Soll-Hook in einem Zug, dann Prüfkatalog, zuletzt Editor (Editor nie vor dem Backend ausliefern). Kein Schritt braucht eine Gate-Sperre; die wirksame Gate-Konfiguration bleibt unverändert.

## Expected Behavior

- **Input:** Orte-Abo mit `display_config.email_format = "compact"` zur Versandzeit, in der Vorschau oder beim Testversand.
- **Output:** einzelner ASCII-Textteil unter 2 KB mit einer Zeile je Ort. Ohne Feld oder bei "full" ändert sich nichts.
- **Side effects:** Δ-Anker wird nur nach erfolgreichem Versand zurückgesetzt.

## Definition of Done

- AC-1 bis AC-15 durch benannte Tests grün; Adversary mit Mutations-Gegenprobe ohne offenen Befund; alle sechs CI-Checks grün.
- Orte-Validator (`email_spec_validator.py`, Kompakt-Zweig) gegen echt zugestellte Staging-Mail grün, je einmal Kompakt und Ausführlich, DE und EN.
- Bestand: Orte-Abos ohne `email_format` erhalten auf Staging unverändert die ausführliche Mail.
- Zwei-Nutzer-Test auf Staging bestanden; Prod-Deploy mit Selftest-Exit 0.
- Mit dem Bau nachgezogen: Nachtrag ADR-0124 Nr. 6/7, `feat_3122_was_steht_wo.md`, `renderer_email_spec.md`, `api_contract.md`, `mail_validators.md`.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN Orte-Abo mit `email_format: compact` WHEN die Mail zugestellt wird THEN genau ein text/plain-Teil, ASCII, Header `X-GZ-Format: compact`.
- [ ] GIVEN Abo ohne `email_format` WHEN zugestellt THEN multipart mit HTML und Text wie bisher.
- [ ] GIVEN 40 Orte WHEN Kompakt THEN unter 2 KB, letzte Zeile „+N Orte nicht gezeigt“.
- [ ] GIVEN zwei Nutzer mit verschiedenen Formaten WHEN beide versenden THEN jede Mail nur mit eigenen Orten und eigenem Format.
- [ ] GIVEN `display_config` mit `telegram_style` WHEN Format gespeichert THEN `telegram_style` bleibt.
- [ ] GIVEN Versand schlägt fehl WHEN Kompakt THEN Δ-Anker unverändert.
- [ ] Validator-Lauf gegen echt zugestellte Staging-Mail im Kompaktfall (`email_spec_validator.py`, Exit 0).

## Acceptance Criteria

- **AC-1:** Given ein Orte-Abo mit E-Mail-Format „Kompakt“ und drei Orten / When das Briefing zugestellt wird / Then besteht die Mail aus einem einzigen Text-Teil ohne HTML mit dem Kopf `X-GZ-Format: compact` und einer Zeile je Ort mit Ortsname und den für die E-Mail gewählten Werten.
  - Test: Zugestellte Staging-Mail im Test-Postfach abrufen, Teile, Header und Zeilen je Ort prüfen.

- **AC-2:** Given ein bestehendes Orte-Abo ohne Feld `email_format` / When das Briefing zugestellt wird / Then kommt unverändert die ausführliche Mail mit HTML-Vergleichstabelle und Text-Teil an.
  - Test: Bestandsabo ohne Feld versenden, Mail mit dem bisherigen Aufbau (multipart/alternative, Vergleichstabelle) vergleichen.

- **AC-3:** Given ein Nutzer speichert in der Karte „Was steht wo“ eines Orte-Abos „Kompakt“ / When die Einstellung gespeichert und das Abo neu geladen wird / Then steht „Kompakt“ dort wieder, und der Telegram-Kurzstil sowie alle übrigen Einstellungen des Abos sind unverändert.
  - Test: Abo mit gesetztem Telegram-Kurzstil laden, Format umstellen, speichern, erneut laden und beide Werte prüfen.

- **AC-4:** Given ein Orte-Abo mit Kompakt und eingeschaltetem 3-Tages-Ausblick / When die Mail zugestellt wird / Then steht unter jedem Ort eine Zeile „3-Tages-Ausblick“, und ohne eingeschalteten Ausblick steht sie nirgends.
  - Test: Zwei Zustellungen mit Ausblick an und aus, Mailtext auf die Ausblick-Zeilen prüfen.

- **AC-5:** Given ein Orte-Abo mit Kompakt und eingeschaltetem Stundenverlauf / When die Mail zugestellt wird / Then enthält sie keinen Stundenverlauf, und im Editor ist der Stundenverlauf-Schalter bei Kompakt gesperrt, der Ausblick-Schalter dagegen bedienbar.
  - Test: Editor im Kontext Orte mit Kompakt öffnen, Schalterzustände prüfen; zugestellte Mail auf Stundenwerte prüfen.

- **AC-6:** Given ein Orte-Abo mit Kompakt und so vielen Orten, dass der Text über 2 KB käme / When die Mail zugestellt wird / Then ist sie höchstens 2 KB groß, die ersten Orte stehen vollständig, und die letzte Zeile lautet „+N Orte nicht gezeigt“ mit der richtigen Zahl der weggelassenen Orte.
  - Test: Abo mit 40 Orten zustellen, Größe, Ortszeilen und Restzahl prüfen.

- **AC-7:** Given ein Nutzer mit Sprache Englisch und ein Orte-Abo mit Kompakt und vielen Orten / When die Mail zugestellt wird / Then sind alle Texte Englisch (Kopf, Hinweis „+N locations not shown“, Ausblick-Name „3-day outlook“), Ortsnamen und Kürzel bleiben unübersetzt, und der Text ist reines ASCII.
  - Test: EN-Nutzer anlegen, zustellen, Sprache über `X-GZ-Lang`, Texte und ASCII prüfen.

- **AC-8:** Given ein Orte-Name mit Umlauten und Sonderzeichen / When die Kompakt-Mail zugestellt wird / Then erscheint der Name ASCII-gefaltet (zum Beispiel „Muenster“) und die Mail trägt keine Zeichen außerhalb von ASCII.
  - Test: Ort „Münster“ im Kompakt-Abo zustellen, Rohtext der Mail prüfen.

- **AC-9:** Given zwei verschiedene Nutzer mit je eigenen Orte-Abos, der eine Kompakt, der andere Ausführlich / When beide Abos versendet werden / Then erhält jeder Nutzer nur Mails mit seinen eigenen Orten und in seinem eigenen Format, ohne Daten des anderen.
  - Test: Zwei Nutzer mit echter `user_id` anlegen, beide Zustellungen im jeweiligen Postfach prüfen, außerdem Speichern und Laden je Nutzer trennen.

- **AC-10:** Given ein Orte-Abo mit Kompakt / When der Nutzer im Editor die Vorschau öffnet oder den Testversand auslöst / Then zeigen Vorschau und Testmail denselben Kompakttext wie die planmäßige Zustellung.
  - Test: Vorschau-Antwort und zugestellte Testmail mit der planmäßigen Mail vergleichen.

- **AC-11:** Given ein Orte-Abo mit Kompakt und aktivem Δ-Anker / When die Zustellung erfolgreich war bzw. der Versand fehlschlägt / Then wird der Anker nur nach dem erfolgreichen Versand zurückgesetzt und bleibt bei einem Fehler unverändert.
  - Test: Versand mit gestelltem Fehler und mit Erfolg, Ankerzustand danach prüfen.

- **AC-12:** Given ein Orte-Abo mit Kompakt und Telegram-Kurzstil aus / When Briefing und Telegram-Nachricht erzeugt werden / Then folgt die Telegram-Nachricht weiter nur dem Telegram-Kurzstil und SMS und Premium-SMS bleiben unverändert; das Mail-Format wirkt allein auf die E-Mail.
  - Test: Alle Kanäle des Abos erzeugen und Telegram, SMS und Premium-SMS mit Ausführlich-Stand vergleichen.

- **AC-13:** Given im Editor der Orte und der Trips die Karte „Was steht wo“ / When sie geöffnet wird / Then erscheint der Format-Schalter „Ausführlich/Kompakt“ in beiden Kontexten aus demselben Baustein, mit Texten ohne Trip-spezifische Wörter, auf Deutsch und Englisch.
  - Test: Editor beider Kontexte in DE und EN öffnen, Schalter und Beschriftungen prüfen.

- **AC-14:** Given eine echt zugestellte Staging-Mail zu einem Orte-Abo / When `email_spec_validator.py` mit Kompakt als Soll läuft / Then endet er mit Exit 0 für eine korrekte Kompakt-Mail und schlägt bei einer ausführlichen Mail trotz Soll Kompakt (und umgekehrt) fehl.
  - Test: Validator gegen Staging-Mail beider Formate laufen lassen, Exit-Codes prüfen.

- **AC-15:** Given der Prüfkatalog „Einstellung gleich Mail“ für Orte / When die Fallliste und die Soll-Ermittlung ausgewertet werden / Then enthält sie Fälle mit Format „kompakt“ für Orte, und der Soll-Hook leitet das Format aus `email_format` des Abos ab.
  - Test: Fallliste laden, Format-Dimension und Soll je Konfiguration prüfen.

## Known Limitations

- Kein Vortag-Vergleich, keine Etappen-Kennzahlen, keine Nacht-Tabelle für Orte (siehe Nicht im Scope, #3342).
- Die 2-KB-Grenze kann bei vielen Orten Orte weglassen; das ist beabsichtigt und wird in der Mail genannt.
- Δ-Anker (AC-11): Der Kompaktpfad verhält sich exakt wie der Vollpfad. Seit #1629 wird der Vergleichs-Anker bewusst auch bei Versandfehler geschrieben, damit der nächste Vergleich eine Basis hat; #3059 ändert diese bestehende Entscheidung nicht. Abgesichert ist die Gleichheit Kompakt = Vollpfad, auch bei Fehlversand (Tech-Lead-Festlegung im Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; Nachtrag zu ADR-0124 Nr. 6/7
- **Rationale:** ADR-0124 verwies das Orte-Kompakt-Format ausdrücklich auf #3059. Die Aussage „Orte kennt keine Kompakt-Mail“ wird per Nachtrag überholt, nicht still rückgängig gemacht.

## Changelog

- 2026-11-24: Initial spec created
