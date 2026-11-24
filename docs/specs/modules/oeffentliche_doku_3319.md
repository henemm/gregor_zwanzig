---
entity_id: oeffentliche_doku_3319
type: feature
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
workflow: feat-3319-oeffentliche-doku
tags: [startseite, funktionen, level, i18n, bilder, epic-3318]
---

# Öffentliche Doku: Startseite aktuell, Level Free/Standard/Premium, Funktionsübersicht /funktionen (DE/EN)

## Approval

- [ ] Approved

## Purpose

Die öffentliche Startseite nennt heute SMS als „in Arbeit/auf Anfrage“ und Telegram nur „auf Wunsch“, obwohl alle vier Kanäle gleichrangig verfügbar sind (ADR-0095, ADR-0049); außerdem erklärt sie nicht, was kostenlos und was Premium ist. Diese Spec bringt die Startseite auf den Ist-Stand, erklärt die Level Free/Standard/Premium aus einer einzigen Zahlenquelle und ergänzt eine öffentliche, zweisprachige Funktionsübersicht `/funktionen` mit Bildern der echten Oberfläche (gebündelt #3319 + #3320, Epic #3318).

## Source

- **File:** `frontend/src/routes/_start/Startseite.svelte`, `frontend/src/routes/funktionen/+page.svelte`, `frontend/src/lib/level_grenzen.json`
- **Identifier:** Startseite (Level-Kurzform), Route `/funktionen`, `LevelTabelle.svelte`

> **Schicht-Hinweis:** Frontend (SvelteKit) für Seiten, Texte, Auth-Grenze und Bilder. Go (`internal/model/`) und Python (`src/services/`) werden nur **gelesen** und durch Drift-Tests an die JSON-Datei gebunden; kein Produktivcode dort ändert sich.
> **Trip/Ortsvergleich-Teilung:** nicht betroffen (reine Doku-Seiten, keine Editor-Komponente).
> **Mandantentrennung:** nicht betroffen, die Seiten laden keine Nutzerdaten und rufen keine API auf.
> **Kanäle:** Alle vier Kanäle (E-Mail · Telegram · SMS · Premium-SMS) werden gleichrangig und mit gleichem Inhaltsanspruch beschrieben.

## Estimated Scope

- **LoC:** +1200 bis +1600 / -30
- **Files:** ca. 25 Dateien (+ 20 bis 30 Bilddateien)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/tier.go` (quotaTable, SmsAllowed, PremiumSmsAllowed) | Go-Modul | Quelle der Wahrheit der Quoten; Go-Drift-Test liest sie |
| `src/services/user_tier.py` | Python-Modul | SMS-/Premium-SMS-Tageslimits, `daily_alert_limit`; Python-Drift-Test |
| `frontend/src/hooks.server.ts` | Auth-Hook | öffentliche exakte Pfade (`/`, neu `/funktionen`) |
| `frontend/src/routes/+layout.svelte` | Layout | `publicPages`: Zweig ohne Sidebar, mit `AppFooter` |
| `frontend/src/lib/i18n/resolveLang.ts`, `SprachUmschalter.svelte` | i18n | Sprachwahl Cookie `gz_lang` > Accept-Language > de |
| `frontend/src/lib/i18n/messages/{de,en}/hilfe.json`, `tests/test_hilfe_befehle_drift.py` | Katalog/Test | Quelle und Wächter der Befehlsliste |
| `scripts/landing_screenshots.py` | Skript | Renderer-Bilder (Mail, Telegram, SMS, Premium-SMS, Alarm) |
| `scripts/staging_pruefkonto_mockupdaten.py`, `docs/runbooks/staging_pruefkonto_seed.md` | Skript/Runbook | Prüfkonto mit Fiktivdaten für UI-Bilder (Host, Loopback 8091) |
| ADR-0095, ADR-0049, ADR-0104, ADR-0007 | ADR | Kanalparität, Premium-SMS, Zweisprachigkeit, nur Daten |
| `oeffentliche_startseite_2520.md`, `startseite_en_bilder_2777.md` | Spec | AC-6 von 2520 wird abgelöst; Bildregeln aus 2777 |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/i18n/messages/{de,en}/start.json` | MODIFY | `meta.description`, `hero.lead`, `ankommt.kanaele`: vier Kanäle verfügbar; neue Keys Level-Kurzübersicht, Wechselweg, Link zu `/funktionen` |
| `frontend/src/routes/_start/Startseite.svelte` | MODIFY | Level-Block (Kurzform) + Link `/funktionen` |
| `frontend/src/lib/level_grenzen.json` | CREATE | einzige Quelle der Level-Zahlen (`null` = unbegrenzt) |
| `frontend/src/lib/components/shared/LevelTabelle.svelte` | CREATE | gemeinsam für Startseite (kurz) und Funktionsseite (voll) |
| `internal/model/tier_katalog_drift_test.go` | CREATE | Go-Drift-Test JSON gegen Code, mit Gegenprobe |
| `tests/test_level_grenzen_drift.py` | CREATE | Python-Drift-Test JSON gegen `user_tier.py`, mit Gegenprobe |
| `frontend/src/hooks.server.ts` | MODIFY | exakter Pfad `/funktionen` öffentlich (Set, kein `startsWith`) |
| `frontend/src/routes/+layout.svelte` | MODIFY | `publicPages` um `/funktionen` |
| `frontend/src/routes/funktionen/+page.svelte`, `+page.server.ts` | CREATE | öffentliche Funktionsübersicht, kein API-Aufruf |
| `frontend/src/routes/_funktionen/*.svelte` | CREATE | Abschnitte 1–14, Inhaltsverzeichnis mit Sprungankern, Bild-Block |
| `frontend/src/lib/i18n/messages/{de,en}/funktionen.json`, `i18n/index.ts` | CREATE/MODIFY | alle Texte DE/EN, Katalog-Registrierung |
| `scripts/landing_screenshots.py` | MODIFY | DE- und EN-Ausgabe; zusätzlich SMS- und Premium-SMS-Bild |
| `scripts/funktionen_screenshots.py` | CREATE | Playwright gegen Staging-Prüfkonto, `gz_lang` je Sprache |
| `frontend/static/funktionen/{,en/}*.webp` | CREATE | Bilder, je < 200 KB |
| `frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts` | MODIFY | alte Regel „SMS nur in progress/on request“ umkehren |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` | MODIFY | Bildprüfung auf `funktionen.*` erweitern |
| `frontend/src/hooks.server*.test.ts` | MODIFY/CREATE | `/` und `/funktionen` öffentlich; Nachbarpfade nicht |
| `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts` | CREATE | Inhalt, Sprachen, Verzeichnis, Befehlsliste, Level-Tabelle |
| `docs/specs/modules/oeffentliche_startseite_2520.md` | MODIFY | AC-6 „Abgelöst durch #3319“ |
| `docs/specs/modules/epic_user_tiers_overview.md` | MODIFY | Hinweis „Premium-SMS existiert nicht“ nachziehen |
| `docs/runbooks/funktionen_screenshots.md` | CREATE | Bilder neu erzeugen, Sichtprüfung auf Personendaten |

### Estimated Changes

- Files: ca. 25 (+ 20 bis 30 Bilder)
- LoC: +1200 bis +1600 / -30

## Implementation Details

Reihenfolge der Umsetzung: (1) Startseite + Level-Daten + Drift-Tests, (2) Route `/funktionen` + Auth-Grenze, (3) Texte DE/EN, (4) Renderer-Bilder, (5) UI-Bilder vom Staging-Prüfkonto, (6) Bild-Tests.

- **Level-Zahlen** stehen nur in `level_grenzen.json`; die Kataloge enthalten Texte mit Platzhaltern. Werte: Aktive Trips 3/15/50, aktive Ortsvergleiche 2/10/30, Orte gesamt 10/50/200, SMS pro Tag 0/10/10, Premium-SMS pro Tag 0/0/15 (+ Antworten 0/0/15), proaktive Alarme pro Tag 2/4/unbegrenzt; E-Mail und Telegram in allen Leveln. Go- und Python-Drift-Test vergleichen jeweils gegen den Code und haben eine Gegenprobe (verfälschter Wert muss rot werden).
- **Wechselweg:** offene Registrierung = Free; Level-Wechsel per Antrag im Konto, der Betreiber prüft. Keine Preise, kein Bezahlweg.
- **Route `/funktionen`:** ein Pfad für DE/EN, Sprache wie Startseite (Cookie `gz_lang` > Accept-Language > de) mit Umschalter; kein `/en/…`-Präfix. Im Hook nur exakter Pfad, `+page.server.ts` liefert nur `oeffentlich: true` und die aufgelöste Sprache, keinen userId- oder API-Zugriff.
- **Inhalt:** Inventar 1–14 (Cockpit, Trip anlegen, Trip-Hub, Briefings, Reiter Wetter, Zustellung, Alarme inkl. amtlicher Warnungen und Radar, Ortsvergleich, Kanäle, Antwort-Befehle, Archiv, Konto, App/Offline, Wetterdaten), Inhaltsverzeichnis mit Sprungankern, volle Level-Tabelle. Nicht aufnehmen: Claude-Konnektor, Admin, Design-Seiten. Nur Funktionsbeschreibung, keine Wetter-Handlungsempfehlungen (ADR-0007).
- **Befehlsliste** wird aus derselben Quelle wie die Hilfe gebildet bzw. per Drift-Test an `hilfe.json` gebunden (Muster `test_hilfe_befehle_drift.py`).
- **Bilder:** WebP (Qualität ca. 80), feste `width`/`height`, `loading="lazy"`, Alt-Text, je Sprache eigene Dateien unter `static/funktionen/` und `static/funktionen/en/`. Mail/Telegram/SMS/Premium-SMS/Alarm aus echten Renderern, UI-Bilder aus der echten Staging-Oberfläche mit Prüfkonto-Seed (nur Fiktivwerte, Mail-Adresse und Nummern maskiert). Jedes Bild wird vor Auslieferung per Auge auf Personendaten geprüft.
- **Auth-Grenze:** `/hilfe` bleibt nur für Angemeldete.

## Expected Behavior

- **Input:** Besuch von `/` oder `/funktionen` ohne Anmeldung, in Deutsch oder Englisch.
- **Output:** Aktuelle Startseite mit vier Kanälen und Level-Kurzübersicht; umfangreiche Funktionsübersicht mit Inhaltsverzeichnis, Bildern und voller Level-Tabelle.
- **Side effects:** Keine; keine Nutzerdaten, keine API-Aufrufe.

## Acceptance Criteria

- **AC-1:** Given ein nicht angemeldeter Besucher öffnet die Startseite auf Deutsch oder Englisch / When er Titelbeschreibung, Einleitung und den Abschnitt zur Zustellung liest / Then werden E-Mail, Telegram, SMS und Premium-SMS (Garmin inReach) als verfügbar genannt und keine Formulierung wie „in Arbeit“, „auf Anfrage“ oder „auf Wunsch“ steht mehr bei SMS oder Telegram (auch nicht in `meta.description` und `hero.lead`).
  - Test: Besucher sieht auf der Startseite in beiden Sprachen alle vier Kanäle gleichrangig als verfügbar; Katalog-Regeltest schlägt bei „in Arbeit/auf Anfrage“ zu SMS/Satellit fehl.

- **AC-2:** Given ein nicht angemeldeter Besucher auf der Startseite / When er zur Level-Übersicht scrollt / Then sieht er Free, Standard und Premium mit den echten Grenzen (Trips, Ortsvergleiche, Orte, SMS, Premium-SMS, Alarme pro Tag), den Hinweis „offene Registrierung = Free, Wechsel per Antrag im Konto, der Betreiber prüft“, keine Preise und einen Link zu `/funktionen`.
  - Test: Startseite DE/EN zeigt die Kurztabelle mit den Zahlen aus der Level-Datei; kein Preis- oder Bezahltext; Klick auf den Link führt zu `/funktionen`.

- **AC-3:** Given die Level-Zahlen stehen ausschließlich in `level_grenzen.json` / When ein Wert in Go (`quotaTable`, `SmsAllowed`, `PremiumSmsAllowed`) oder Python (`user_tier.py`) geändert wird, ohne die Datei anzupassen / Then schlägt der jeweilige Drift-Test in Go bzw. Python fehl, und die Gegenprobe mit verfälschtem Wert wird nachweislich rot.
  - Test: Go- und Python-Drift-Test grün im Ist-Zustand; Mutation eines Grenzwerts macht beide rot.

- **AC-4:** Given ein nicht angemeldeter Besucher / When er `/funktionen` aufruft / Then wird die Seite ohne Weiterleitung zum Login ausgeliefert, ohne Nutzerdaten und ohne Aufruf der Go-API; ein Angemeldeter erreicht sie ebenfalls.
  - Test: Hook-Test und Aufruf auf Staging ohne Cookie liefern 200 für `/funktionen`; mit Sitzung ebenfalls 200; kein Netzwerkaufruf an `/api`.

- **AC-5:** Given ein nicht angemeldeter Besucher / When er `/funktionen/x`, `/funktionenx`, `/hilfe` oder `/account` aufruft / Then wird er wie bisher zum Login geleitet, nur `/` und exakt `/funktionen` sind öffentlich.
  - Test: Hook-Test prüft alle vier Nachbarpfade als geschützt und `/` sowie `/funktionen` als öffentlich.

- **AC-6:** Given ein Besucher mit deutscher oder englischer Spracheinstellung / When er `/funktionen` öffnet und den Sprachumschalter benutzt / Then erscheint die Seite vollständig in der gewählten Sprache (Cookie `gz_lang` vor Accept-Language vor Deutsch), mit Inhaltsverzeichnis, dessen Sprungankern zu den Abschnitten 1 bis 14 des Funktionsinventars springen, und der vollen Level-Tabelle.
  - Test: Seitentest je Sprache findet alle 14 Abschnitte, funktionierende Ankerziele und die Level-Tabelle; Umschalter wechselt die Sprache ohne Login.

- **AC-7:** Given die Funktionsübersicht ist öffentlich / When ein Besucher alle Abschnitte liest / Then kommen der Claude-Konnektor, der Admin-Bereich und Design-Seiten nicht vor, und es steht dort nur Funktionsbeschreibung ohne Wetter-Handlungsempfehlungen.
  - Test: Katalogtest findet keine Begriffe Konnektor/MCP/Admin/Design und keine Empfehlungsformulierungen in `funktionen.*`.

- **AC-8:** Given die Funktionsübersicht enthält Bilder / When ein Besucher sie in Deutsch und Englisch ansieht / Then zeigt jedes Bild die echte Oberfläche oder einen echten Renderer-Ausgang in der jeweiligen Sprache (eigene Datei je Sprache), ist kleiner als 200 KB, hat Alt-Text, feste Breite und Höhe sowie lazy Loading.
  - Test: Bildtest prüft Existenz, Größe unter 200 KB, Alt-Text, width/height, `loading="lazy"` und das DE/EN-Paar je Bild.

- **AC-9:** Given Bilder entstehen aus dem Staging-Prüfkonto und aus Renderern / When sie veröffentlicht werden / Then enthalten sie nur Prüfkonto-Fiktivwerte (GR221-Mockup, Münsterland-Vergleich), Mail-Adressen und Telefonnummern sind maskiert, und die Sichtprüfung ist im Runbook dokumentiert.
  - Test: Das Bild-Skript bricht vor jeder Aufnahme ab, wenn der sichtbare Seitentext eine Mail-Adresse oder Telefonnummer außerhalb der Fiktiv-Liste des Seeds enthält (automatischer Wächter, mit Gegenprobe); zusätzlich Sichtprüfung jedes Bildes, Ergebnis im Issue.

- **AC-10:** Given die Funktionsübersicht listet die Antwort-Befehle (HEUTE, MORGEN, JETZT, GEWITTER, STRECKE, RUHETAG, STATUS, PAUSE, SKIP, STOP, WEITER, HILFE, KUERZEL, STARTDATUM, REPORT) / When die Befehle der Hilfe geändert werden / Then schlägt der Drift-Test fehl, bis die Liste auf `/funktionen` wieder derselben Quelle entspricht; die Seite nennt zudem, dass Befehle per E-Mail, Telegram und Premium-SMS ankommen und normale SMS nur empfangen wird.
  - Test: Drift-Test vergleicht die Befehle auf `/funktionen` mit der Hilfe-Quelle; verfälschter Befehl macht ihn rot.

- **AC-11:** Given ein Besucher liest `/funktionen` und die Startseite auf einem Handy mit 375 px Breite / When er durch die Seite scrollt / Then gibt es keine horizontale Scrollleiste, Text und Tabellen sind lesbar mit hohem Kontrast (WCAG-AA).
  - Test: Playwright-Prüfung bei 375 px Breite: `scrollWidth` gleich Viewportbreite; Kontrastprüfung der Textfarben auf AA.

## Definition of Done

- Startseite DE/EN nennt alle vier Kanäle als verfügbar und zeigt die Level-Kurzübersicht mit Link zu `/funktionen` (AC-1, AC-2).
- `/funktionen` ist ohne Anmeldung in DE/EN erreichbar, vollständig (14 Abschnitte, volle Level-Tabelle, Befehlsliste, Bilder) und die Auth-Grenze bleibt sonst unverändert (AC-4 bis AC-8, AC-10).
- Level-Zahlen und Befehlsliste sind per Drift-Test an den Code gebunden, Gegenproben rot (AC-3, AC-10).
- Alle Bilder ohne Personendaten (Wächter + Sichtprüfung) und mobil lesbar (AC-9, AC-11).
- Alle genannten Tests grün, Staging-Prüfung bestanden, Produktion ausgeliefert, Inhalt im Issue dokumentiert.

## Test Plan

- `internal/model/tier_katalog_drift_test.go`: Level-Datei gegen `quotaTable`, `SmsAllowed`, `PremiumSmsAllowed`, mit Gegenprobe (AC-3).
- `tests/test_level_grenzen_drift.py`: Level-Datei gegen `user_tier.py`, mit Gegenprobe (AC-3).
- `frontend/src/hooks.server*.test.ts`: `/` und `/funktionen` öffentlich, `/funktionen/x`, `/funktionenx`, `/hilfe`, `/account` geschützt (AC-4, AC-5).
- `frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts`: keine „in Arbeit/auf Anfrage“-Formulierung zu SMS/Satellit in `start.*`/`funktionen.*`; keine Konnektor/Admin/Empfehlungstexte (AC-1, AC-7).
- `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts`: 14 Abschnitte je Sprache, Anker, Level-Tabelle, Befehlsliste gegen Hilfe-Quelle, Kanalhinweis zu Befehlen (AC-6, AC-10).
- `frontend/src/lib/i18n/__tests__/textkatalog.test.ts`: Bilder existieren je Sprache, < 200 KB, Alt-Text, Maße, lazy (AC-8).
- Personendaten-Wächter im Bild-Skript mit Gegenprobe plus Sichtprüfung (AC-9).
- Staging-Prüfung mit Playwright ohne Anmeldung: Startseite und `/funktionen` DE/EN, 375 px ohne horizontale Scrollleiste, Kontrast AA (AC-2, AC-4, AC-6, AC-11).

## Known Limitations

- Bilder spiegeln den Stand der Oberfläche zum Aufnahmezeitpunkt; bei UI-Änderungen müssen sie über das Runbook neu erzeugt werden.
- Preise und Bezahlweg gibt es im Produkt nicht und werden nicht genannt.
- Der Claude-Konnektor wird bewusst nicht öffentlich beworben (ADR-0128).
- UI-Bilder lassen sich nur auf dem Host gegen das Staging-Prüfkonto erzeugen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0095, ADR-0049, ADR-0104 und ADR-0007 um und ändert keine Entscheidung; der zweite öffentliche Pfad folgt dem Muster aus #2520 (exakter Pfad, keine Nutzerdaten). Die Abwandlung von AC-6 in Spec 2520 ist dort vermerkt.

## Changelog

- 2026-11-24: Initial spec created (#3319 + #3320, Epic #3318)
