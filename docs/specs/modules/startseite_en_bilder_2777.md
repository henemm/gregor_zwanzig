---
entity_id: startseite_en_bilder_2777
type: bugfix
created: 2026-11-14
updated: 2026-11-14
status: draft
version: "1.0"
workflow: fix-2777-startseite-en-bilder
tags: [i18n, startseite, landing, epic-2644]
---

# Englische Beispielbilder auf der öffentlichen Startseite (#2777)

## Approval

- [ ] Approved

## Purpose

Die ausgeloggte Startseite zeigt in Englisch bisher dieselben drei Beispielbilder (Briefing-Mail, Telegram, Alarm) wie in Deutsch, und diese enthalten deutschen Text. Diese Spec liefert eigene englische Bilder unter `/landing/en/` und lässt den englischen Textkatalog darauf zeigen (Nachtrag zu A2 #2681, Epic #2644).

## Source

- **File:** `frontend/src/lib/i18n/messages/en/start.json`
- **Identifier:** Schlüssel `start.mail.src`, `start.telegram.src`, `start.alarm.src`

> Schicht: Frontend (statische Assets in `frontend/static/landing/en/`, Textkatalog unter `frontend/src/lib/i18n/`) plus ein Hilfsskript in `scripts/`. Keine Änderung an Python-Core, Go-API oder `Startseite.svelte`.
>
> Querschnitts-Prüfpunkte: Trip/Ortsvergleich-Teilung nicht betroffen (Startseite hat kein Pendant). Mandantentrennung nicht betroffen (statische, öffentliche Bilder, keine Nutzerdaten). Kanäle: Die Bilder zeigen die Kanäle E-Mail, Telegram und Alarm; SMS und Premium-SMS bleiben wie in #2520 (Punkt 6) bewusst ohne Screenshot.

## Estimated Scope

- **LoC:** ca. +150 / -3
- **Files:** 7 (davon 3 Binärdateien)
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/static/landing/en/briefing-mail.png` | CREATE | englische Briefing-Mail |
| `frontend/static/landing/en/briefing-telegram.png` | CREATE | englische Telegram-Nachricht |
| `frontend/static/landing/en/alarm.png` | CREATE | englischer Alarm (Sturm orange, Hitze gelb) |
| `frontend/src/lib/i18n/messages/en/start.json` | MODIFY | drei `src`-Pfade auf `/landing/en/...` |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` | MODIFY | Bild-Prüfung (AC-7 aus #2520) für beide Kataloge; en-Pfad ungleich de-Pfad |
| `scripts/landing_screenshots.py` | CREATE | reproduzierbare Erzeugung der englischen Bilder |
| `docs/specs/modules/oeffentliche_startseite_2520.md` | MODIFY | Nachtrag: Bilder je Sprache |

Unverändert: `de/start.json` (Pfade `/landing/*.png`), `Startseite.svelte`, `hooks.server.ts` (`/landing/*` wird statisch ausgeliefert, Unterordner ändert daran nichts), Glossar-Ausnahme für `start.alarm.src`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2681 (A2, en-Staging-Nutzer) | issue, geschlossen | englischer Testnutzer `+en` für die zugestellte Briefing-Mail |
| #2774 (Staging-Mailweg) | issue, geschlossen | Voraussetzung für echte Staging-Mails |
| `render_official_alert_html(lang="en")` in `src/output/renderers/alert/official_alerts.py` | function | englisches Alarm-HTML |
| `render_telegram_bubbles(lang="en")` in `src/output/renderers/narrow.py` | function | englische Telegram-Blasen |
| Playwright / Chromium | tool | HTML nach PNG |
| `docs/specs/modules/oeffentliche_startseite_2520.md` | spec | AC-7, Asset-Regeln (statisch, keine Personendaten) |
| `frontend/src/lib/i18n/__tests__/glossar_konformitaet_de_en.test.ts` | test | Ausnahme `start.alarm.src` bleibt gültig |

## Implementation Details

1. **Briefing-Mail:** echt zugestellte englische Briefing-Mail des `en`-Testnutzers aus dem Stalwart-Testpostfach auf Staging; nur der Mail-Körper wird zugeschnitten (kein Kopf mit Empfängeradresse), per Chromium als PNG.
2. **Alarm:** `render_official_alert_html(lang="en")` mit denselben Warnungen wie das deutsche Bild (Sturm Stufe orange, Hitze Stufe gelb, Gültigkeit, betroffenes Segment).
3. **Telegram:** `render_telegram_bubbles(lang="en")` mit einem Testsegment analog zum deutschen Bild.
4. `scripts/landing_screenshots.py` erzeugt die englischen Bilder nach `frontend/static/landing/en/`; die deutschen Bilder werden nicht angefasst. Das Skript macht spätere Erneuerungen nach Renderer-Änderungen reproduzierbar.
5. `en/start.json`: `start.mail.src`, `start.telegram.src`, `start.alarm.src` zeigen auf `/landing/en/briefing-mail.png`, `/landing/en/briefing-telegram.png`, `/landing/en/alarm.png`.
6. Sichtprüfung jedes PNG vor Commit: keine Personendaten, kein deutscher Text, unter 200 KB.

**Begründete Abweichung vom Issue-Wortlaut (offen benannt):** Das Issue verlangt Bilder aus echt zugestellten englischen Mails. Das gilt hier nur für die Briefing-Mail. Alarm und Telegram stammen aus den sprachfähigen Renderern, weil (a) sich ein amtlicher Alarm auf Staging nicht auf Bestellung auslösen lässt und der Renderer genau der Code ist, der die zugestellte Mail baut, (b) Telegram nicht im Mail-Testpostfach landet, und (c) so der Alarm-Inhalt (Sturm orange, Hitze gelb) zum englischen Alt-Text passt. Die deutschen Bilder entstanden ebenfalls aus Renderern mit Testdaten (#2520), die Herkunft ist also gleichwertig. Die Abweichung wird im Issue dokumentiert.

**Restdeutsch:** Zeigt ein englischer Render noch deutsche Wörter, ist das ein Renderer-Befund und bekommt ein eigenes Issue; die Bilder werden nicht retuschiert.

## Expected Behavior

- **Input:** Besucher ohne Anmeldung öffnet die Startseite mit Sprache `en`.
- **Output:** Drei Beispielbilder aus `/landing/en/`, englischer Inhalt, englischer Alt-Text. Mit Sprache `de` unverändert die Bilder aus `/landing/`.
- **Side effects:** keine.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Katalog-Test (`node --test`): GIVEN en- und de-Katalog / WHEN je Bildschlüssel verglichen / THEN ist der en-Pfad ungleich dem de-Pfad. Vor der Umstellung rot.
- [ ] Katalog-Test: GIVEN en-Katalog / WHEN die drei `src`-Pfade gelesen werden / THEN liegen sie unter `/landing/en/` und die Dateien existieren.
- [ ] Katalog-Test: GIVEN beide Kataloge / WHEN die Bilddateien geprüft werden / THEN ist jede unter 200 KB und jeder Alt-Text nicht leer.
- [ ] Mutation: en-Pfad zurück auf de-Pfad, und en-Datei löschen; beide Mutationen müssen rot werden.
- [ ] E2E (Staging, `/e2e-verify`): ausgeloggt mit Sprache `en` die Startseite laden und die drei Bildanfragen prüfen.

## Acceptance Criteria

- **AC-1:** Given der englische Textkatalog / When die Bildpfade der Startseite gelesen werden / Then verweisen `start.mail.src`, `start.telegram.src` und `start.alarm.src` auf `/landing/en/briefing-mail.png`, `/landing/en/briefing-telegram.png` und `/landing/en/alarm.png`.
  - Test: Katalog-Test liest den en-Katalog wie die Seite und erwartet genau diese Pfade; Mutation (Pfad zurück auf `/landing/...`) macht ihn rot.

- **AC-2:** Given der deutsche Textkatalog / When die Bildpfade gelesen werden / Then verweisen sie unverändert auf `/landing/briefing-mail.png`, `/landing/briefing-telegram.png` und `/landing/alarm.png`, und die deutschen Bilddateien sind unverändert.
  - Test: Katalog-Test erwartet die bisherigen de-Pfade; deutsche Besucher sehen dieselben Bilder wie vor der Änderung.

- **AC-3:** Given je eines der drei Bilder / When en- und de-Katalog verglichen werden / Then ist der en-Pfad vom de-Pfad verschieden, beide Dateien existieren, sind kleiner als 200 KB und haben einen nicht leeren Alt-Text in der jeweiligen Sprache.
  - Test: Katalog-Test über beide Sprachen und alle drei Bilder; löschen der en-Datei oder gleiche Pfade machen ihn rot.

- **AC-4:** Given die drei englischen Bilder / When sie angesehen werden / Then zeigen sie keine Personendaten (keine echten Adressen, Namen, Empfänger, keinen Mail-Kopf mit Testnutzer-Adresse) und keinen deutschen Text.
  - Test: manuelle Sichtprüfung jedes PNG vor dem Commit, im Issue protokolliert; verbleibender deutscher Text wird als eigenes Renderer-Issue erfasst und nicht retuschiert.

- **AC-5:** Given das englische Alarm-Bild / When es angesehen wird / Then zeigt es eine Sturmwarnung der Stufe orange und eine Hitzewarnung der Stufe gelb, jeweils mit Gültigkeitszeitraum und betroffenem Segment, passend zum englischen Alt-Text.
  - Test: Sichtprüfung gegen den en-Alt-Text aus `en/start.json`; das Skript verwendet dieselben Warnungen wie das deutsche Bild.

- **AC-6:** Given das Repository / When `scripts/landing_screenshots.py` ausgeführt wird / Then erzeugt es die englischen Alarm- und Telegram-Bilder reproduzierbar unter `frontend/static/landing/en/`, ohne die deutschen Bilder zu verändern.
  - Test: Skript zweimal laufen lassen; beide Läufe liefern Dateien am selben Ort, `landing/*.png` (de) bleibt byte-gleich.

- **AC-7:** Given Staging und ein ausgeloggter Besucher mit Sprache `en` / When die Startseite geladen wird / Then lädt sie genau die drei Beispielbilder unter `/landing/en/` mit HTTP 200 und `naturalWidth > 0`.
  - Test: Playwright gegen Staging ohne Login mit Sprache `en`; Netzwerkantworten der drei Bildanfragen prüfen (Pfad `/landing/en/`, Status 200). Ein Besucher mit `de` bekommt weiterhin Bilder unter `/landing/`.

## Definition of Done

- AC-1 bis AC-3 durch den Katalog-Test (node --test) belegt, Kern-Schicht grün; Pflicht-Mutationen (en-Pfad zurück auf de, en-Datei gelöscht) werden gefangen
- AC-4 und AC-5 durch Sichtprüfung jedes englischen PNG belegt, Ergebnis im Issue #2777 protokolliert; Restdeutsch als eigenes Renderer-Issue erfasst
- AC-6 durch zweimaligen Skriptlauf belegt, deutsche Bilder byte-gleich
- AC-7 auf Staging belegt (ausgeloggt, Sprache en, drei Bilder unter `/landing/en/` mit HTTP 200)
- Abweichung vom Issue-Wortlaut (Herkunft Alarm/Telegram) im Issue #2777 dokumentiert, Nachtrag in `oeffentliche_startseite_2520.md`
- Adversary-Verdict VERIFIED, alle 6 CI-Checks grün, Produktion ausgeliefert, Selftest grün

## Known Limitations

- Alarm und Telegram stammen aus den Renderern mit Testdaten, nicht aus zugestellten Mails (siehe begründete Abweichung oben).
- Die Bilder sind statisch und werden bei Renderer-Änderungen nicht automatisch erneuert; das Skript erlaubt eine manuelle Erneuerung.
- Restdeutsch im englischen Render ist ein Renderer-Thema und nicht Teil dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt die bestehende Entscheidung ADR-0104 (zweisprachig, Sprache am Nutzer, Texte über den Katalog) für drei statische Assets um; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-14: Initial spec created (#2777)
