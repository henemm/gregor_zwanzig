---
entity_id: oeffentliche_doku_3319
type: feature
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.2"
workflow: feat-3319-oeffentliche-doku
tags: [startseite, funktionen, level, i18n, bilder, epic-3318]
---

# Öffentliche Doku: Startseite aktuell, Level Free/Standard/Premium, Funktionsübersicht /funktionen (DE/EN)

## Approval

- [ ] Approved

## Purpose

Die öffentliche Startseite nennt heute SMS als „in Arbeit/auf Anfrage“ und Telegram nur „auf Wunsch“, obwohl alle vier Kanäle gleichrangig verfügbar sind (ADR-0095, ADR-0049); außerdem erklärt sie nicht, was kostenlos und was Premium ist. Diese Spec bringt die Startseite auf den Ist-Stand, erklärt die Level Free/Standard/Premium aus einer einzigen Zahlenquelle und ergänzt eine öffentliche, zweisprachige Funktionsübersicht nach gängiger Praxis für Produkt-Dokumentation: eine Übersichtsseite `/funktionen` mit Themenkacheln und je Thema eine eigene Unterseite `/funktionen/<thema>` mit Bildern der echten Oberfläche, Brotkrumen, Themen-Navigation und Weiter/Zurück (gebündelt #3319 + #3320, Epic #3318; Unterseiten-Struktur auf PO-Vorgabe vom 24.11.2026).

## Source

- **File:** `frontend/src/routes/_start/Startseite.svelte`, `frontend/src/routes/funktionen/+page.svelte`, `frontend/src/routes/funktionen/[thema]/+page.svelte`, `frontend/src/lib/funktionen_seiten.ts`, `frontend/src/lib/level_grenzen.json`
- **Identifier:** Startseite (Level-Kurzform), Übersicht `/funktionen`, Unterseiten `/funktionen/<thema>`, `LevelTabelle.svelte`

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
| `frontend/src/hooks.server.ts` | Auth-Hook | öffentliche exakte Pfade (`/`, neu `/funktionen` und die neun Unterseiten aus `funktionen_seiten.ts`) |
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
| `frontend/src/lib/funktionen_seiten.ts` | CREATE | einzige Liste der Unterseiten (Slug, Reihenfolge, Katalog-Schlüssel, Inventarpunkte); Quelle für Hook, Übersicht, Navigation |
| `frontend/src/hooks.server.ts` | MODIFY | exakte Pfade `/funktionen` und `/funktionen/<slug>` aus der Liste öffentlich (Set, kein `startsWith`) |
| `frontend/src/routes/+layout.svelte` | MODIFY | `publicPages` um dieselben exakten Pfade |
| `frontend/src/routes/funktionen/+page.svelte`, `+page.server.ts` | CREATE | Übersichtsseite mit Themenkacheln, kein API-Aufruf |
| `frontend/src/routes/funktionen/[thema]/+page.svelte`, `+page.server.ts` | CREATE | Unterseite je Thema; unbekannter Slug ⇒ 404; kein API-Aufruf |
| `frontend/src/routes/_funktionen/*.svelte` | CREATE | Seitenrahmen (Brotkrumen, Themen-Navigation, Weiter/Zurück, Aufruf zur Registrierung), Bild-Block, Befehlsliste |
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
- **Seitenstruktur (Praxis für Produkt-Dokumentation, PO 24.11.2026):** Übersicht `/funktionen` mit kurzer Einleitung, „In drei Schritten“ (Trip anlegen → Kanäle wählen → Briefings und Alarme unterwegs) und je Thema einer Kachel (Bild, Titel, ein Satz, Link). Neun Unterseiten, Reihenfolge fest in `funktionen_seiten.ts`:
  1. `trips` Trips planen (Inventar: Cockpit, Trip anlegen, Trip-Hub, Archiv)
  2. `briefings` Wetter-Briefings (Briefings morgens/abends, Reiter Wetter)
  3. `alarme` Alarme und Warnungen (Wetteränderung, Vorboten, amtliche Warnungen, Radar)
  4. `ortsvergleich` Ortsvergleich
  5. `kanaele` Kanäle und Zustellung (Kanäle, Reiter Zustellung)
  6. `befehle` Antwort-Befehle
  7. `wetterdaten` Wetterdaten und Modelle
  8. `konto` Konto und App (Konto, App/Offline)
  9. `level` Free, Standard, Premium (volle Level-Tabelle, Wechselweg)
  Jeder der 14 Inventarpunkte steht auf genau einer Unterseite. Jede Unterseite hat: Brotkrumen („Funktionen › Thema“), Titel mit Einleitungssatz, Abschnitte mit Zwischenüberschriften und Bildern, Hinweis „Verfügbar in: Free/Standard/Premium“ wo das Level eine Rolle spielt, Themen-Navigation zu allen Unterseiten (Desktop seitlich, Handy als Liste über oder unter dem Inhalt), Weiter/Zurück zur Nachbarseite, Aufruf zur Registrierung, eigenen Seitentitel und eigene Meta-Beschreibung.
- **Routen:** ein Pfad je Seite für DE/EN, Sprache wie Startseite (Cookie `gz_lang` > Accept-Language > de) mit Umschalter; kein `/en/…`-Präfix, Slugs bleiben sprachunabhängig. Im Hook nur exakte Pfade aus der Seitenliste (Set, kein `startsWith`); `+page.server.ts` liefert nur `oeffentlich: true`, die aufgelöste Sprache und ggf. den Slug, keinen userId- oder API-Zugriff. Unbekannter Slug für Angemeldete ⇒ 404; für Abgemeldete bleibt er wie jeder nicht freigegebene Pfad hinter dem Login.
- **Inhalt:** Inventar 1–14 (Cockpit, Trip anlegen, Trip-Hub, Briefings, Reiter Wetter, Zustellung, Alarme inkl. amtlicher Warnungen und Radar, Ortsvergleich, Kanäle, Antwort-Befehle, Archiv, Konto, App/Offline, Wetterdaten), verteilt auf die Unterseiten oben; Startseite verlinkt die Übersicht und die Level-Seite. Nicht aufnehmen: Claude-Konnektor, Admin, Design-Seiten. Nur Funktionsbeschreibung, keine Wetter-Handlungsempfehlungen (ADR-0007).
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

- **AC-4:** Given ein nicht angemeldeter Besucher / When er `/funktionen` oder eine der neun Unterseiten `/funktionen/<thema>` aufruft / Then wird die Seite ohne Weiterleitung zum Login ausgeliefert, ohne Nutzerdaten und ohne Aufruf der Go-API; ein Angemeldeter erreicht sie ebenfalls.
  - Test: Hook-Test für die Übersicht und jeden Slug der Seitenliste; Aufruf auf Staging ohne Cookie liefert 200 für alle zehn Pfade; mit Sitzung ebenfalls 200; kein Netzwerkaufruf an `/api`.

- **AC-5:** Given ein nicht angemeldeter Besucher / When er `/funktionen/unbekannt`, `/funktionen/trips/x`, `/funktionenx`, `/hilfe` oder `/account` aufruft / Then wird er wie bisher zum Login geleitet; öffentlich sind nur `/`, exakt `/funktionen` und exakt die Pfade der Seitenliste.
  - Test: Hook-Test prüft die Nachbarpfade als geschützt und die öffentlichen Pfade als offen; die öffentliche Pfadmenge wird aus derselben Seitenliste gebildet wie Navigation und Übersicht.

- **AC-6:** Given ein Besucher mit deutscher oder englischer Spracheinstellung / When er `/funktionen` öffnet, eine Kachel anklickt und den Sprachumschalter benutzt / Then erscheint jede Seite vollständig in der gewählten Sprache (Cookie `gz_lang` vor Accept-Language vor Deutsch); die Übersicht zeigt je Unterseite eine Kachel mit Link, und jeder der 14 Inventarpunkte steht auf genau einer der neun Unterseiten.
  - Test: Seitentest je Sprache findet neun Kacheln mit Ziel aus der Seitenliste, alle 14 Inventarpunkte genau einmal zugeordnet, und für jeden Katalogschlüssel DE und EN; Umschalter wechselt die Sprache ohne Login.
  - Nachtrag #3337: Der Sprachumschalter erscheint nur für Besucher ohne Anmeldung; Angemeldete sehen im Seitenkopf stattdessen einen Hinweis mit Link zur Sprachwahl im Konto (`/account#sprache`). Siehe `sprachumschalter_angemeldet_3337.md`.

- **AC-7:** Given die Funktionsübersicht ist öffentlich / When ein Besucher alle Seiten liest / Then kommen der Claude-Konnektor, der Admin-Bereich und Design-Seiten nicht vor, und es steht dort nur Funktionsbeschreibung ohne Wetter-Handlungsempfehlungen.
  - Test: Katalogtest findet keine Begriffe Konnektor/MCP/Admin/Design und keine Empfehlungsformulierungen in `funktionen.*`.

- **AC-8:** Given die Funktionsseiten enthalten Bilder / When ein Besucher sie in Deutsch und Englisch ansieht / Then zeigt jedes Bild die echte Oberfläche oder einen echten Renderer-Ausgang in der jeweiligen Sprache (eigene Datei je Sprache), jede Unterseite außer `level` hat mindestens ein Bild, jedes Bild ist kleiner als 200 KB und hat Alt-Text, feste Breite und Höhe sowie lazy Loading.
  - Test: Bildtest prüft Existenz, Größe unter 200 KB, Alt-Text, width/height, `loading="lazy"`, das DE/EN-Paar je Bild und mindestens ein Bild je Unterseite außer `level`.

- **AC-9:** Given Bilder entstehen aus dem Staging-Prüfkonto und aus Renderern / When sie veröffentlicht werden / Then enthalten sie nur Prüfkonto-Fiktivwerte (GR221-Mockup, Münsterland-Vergleich), Mail-Adressen und Telefonnummern sind maskiert, und die Sichtprüfung ist im Runbook dokumentiert.
  - Test: Das Bild-Skript bricht vor jeder Aufnahme ab, wenn der sichtbare Seitentext eine Mail-Adresse oder Telefonnummer außerhalb der Fiktiv-Liste des Seeds enthält (automatischer Wächter, mit Gegenprobe); zusätzlich Sichtprüfung jedes Bildes, Ergebnis im Issue.

- **AC-10:** Given die Unterseite `befehle` listet die Antwort-Befehle (HEUTE, MORGEN, JETZT, GEWITTER, STRECKE, RUHETAG, STATUS, PAUSE, SKIP, STOP, WEITER, HILFE, KUERZEL, STARTDATUM, REPORT) / When die Befehle der Hilfe geändert werden / Then schlägt der Drift-Test fehl, bis die Liste wieder derselben Quelle entspricht; die Seite nennt zudem, dass Befehle per E-Mail, Telegram und Premium-SMS ankommen und normale SMS nur empfangen wird.
  - Test: Drift-Test vergleicht die Befehle der Unterseite `befehle` mit der Hilfe-Quelle; verfälschter Befehl macht ihn rot.

- **AC-11:** Given ein Besucher liest die Startseite, `/funktionen` und jede Unterseite auf einem Handy mit 375 px Breite / When er durch die Seite scrollt / Then gibt es keine horizontale Scrollleiste, Text und Tabellen sind lesbar mit hohem Kontrast (WCAG-AA), und die Themen-Navigation ist erreichbar.
  - Test: Playwright-Prüfung bei 375 px Breite auf allen elf Seiten: `scrollWidth` gleich Viewportbreite; Kontrastprüfung der Textfarben auf AA.
  - Nachtrag #3337: Im Seitenkopf steht der Sprachumschalter nur für Besucher ohne Anmeldung; Angemeldete sehen einen Hinweis aufs Konto in Primärtextfarbe mit unterstrichenem Link (Kontrast AA). Siehe `sprachumschalter_angemeldet_3337.md`.

- **AC-12:** Given ein Besucher ist auf einer Unterseite / When er sich orientieren will / Then sieht er Brotkrumen „Funktionen › <Thema>“ mit Link zur Übersicht, eine Themen-Navigation mit allen neun Unterseiten (aktuelle markiert), Links „Zurück“/„Weiter“ zur Nachbarseite in der Reihenfolge der Seitenliste (erste Seite ohne Zurück, letzte ohne Weiter), einen Aufruf zur Registrierung, und der Browser-Tab trägt einen eigenen Seitentitel mit eigener Meta-Beschreibung je Unterseite und Sprache.
- **AC-13:** Given ein Besucher sieht auf einer Unterseite `/funktionen/<thema>` ein Bild / When er es anklickt oder per Tastatur (Enter/Leertaste) auswählt / Then öffnet sich eine Bildergalerie über der Seite mit dem Bild in voller Größe (höchstens Fenstergröße, ohne horizontale Scrollleiste bei 375 px), Beschriftung und Zähler „n / m“, „Vor“/„Zurück“ (Pfeiltasten, Wischen auf dem Handy) blättern nur durch die Bilder derselben Seite, Schließen geht per Schaltfläche, Esc und Klick neben das Bild, danach liegt der Tastaturfokus wieder auf dem angeklickten Bild; alle Bedienelemente haben Beschriftungen in DE/EN, und ohne Klick lädt kein zusätzliches Bild. Auf der Übersicht `/funktionen` bleiben die Kacheln samt Vorschaubild vollständig Links zur Unterseite (keine Galerie dort).
  - Test: Seitentest prüft für jeden Slug Brotkrumen-Link, neun Navigationslinks mit markierter aktueller Seite, Nachbarlinks gemäß Reihenfolge und eindeutige Titel/Beschreibungen je Sprache; Staging-Prüfung klickt Weiter von der ersten bis zur letzten Seite.

## Definition of Done

- Startseite DE/EN nennt alle vier Kanäle als verfügbar und zeigt die Level-Kurzübersicht mit Link zu `/funktionen` (AC-1, AC-2).
- `/funktionen` und neun Unterseiten sind ohne Anmeldung in DE/EN erreichbar, vollständig (14 Inventarpunkte, volle Level-Tabelle, Befehlsliste, Bilder), mit Brotkrumen, Themen-Navigation und Weiter/Zurück, und die Auth-Grenze bleibt sonst unverändert (AC-4 bis AC-8, AC-10, AC-12).
- Level-Zahlen und Befehlsliste sind per Drift-Test an den Code gebunden, Gegenproben rot (AC-3, AC-10).
- Alle Bilder ohne Personendaten (Wächter + Sichtprüfung) und mobil lesbar (AC-9, AC-11).
- Alle genannten Tests grün, Staging-Prüfung bestanden, Produktion ausgeliefert, Inhalt im Issue dokumentiert.

## Test Plan

- `internal/model/tier_katalog_drift_test.go`: Level-Datei gegen `quotaTable`, `SmsAllowed`, `PremiumSmsAllowed`, mit Gegenprobe (AC-3).
- `tests/test_level_grenzen_drift.py`: Level-Datei gegen `user_tier.py`, mit Gegenprobe (AC-3).
- `frontend/src/hooks.server*.test.ts`: `/`, `/funktionen` und alle Slugs der Seitenliste öffentlich, `/funktionen/unbekannt`, `/funktionen/trips/x`, `/funktionenx`, `/hilfe`, `/account` geschützt (AC-4, AC-5).
- `frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts`: keine „in Arbeit/auf Anfrage“-Formulierung zu SMS/Satellit in `start.*`/`funktionen.*`; keine Konnektor/Admin/Empfehlungstexte (AC-1, AC-7).
- `frontend/src/lib/i18n/__tests__/funktionen_seite.test.ts`: neun Unterseiten und Kacheln je Sprache, 14 Inventarpunkte genau einmal zugeordnet, Level-Tabelle auf `level`, Befehlsliste gegen Hilfe-Quelle, Kanalhinweis, Brotkrumen/Navigation/Weiter-Zurück, eindeutige Titel und Beschreibungen (AC-6, AC-10, AC-12).
- Galerie (AC-13): Logik-Test (Reihenfolge je Seite, Vor/Zurück an den Rändern, Beschriftungen DE/EN aus dem Katalog) und Playwright-Prüfung ohne Anmeldung: Klick öffnet, Pfeiltaste blättert, Esc schließt, Fokus zurück, 375 px ohne horizontale Scrollleiste.
- `frontend/src/lib/i18n/__tests__/textkatalog.test.ts`: Bilder existieren je Sprache, < 200 KB, Alt-Text, Maße, lazy (AC-8).
- Personendaten-Wächter im Bild-Skript mit Gegenprobe plus Sichtprüfung (AC-9).
- Staging-Prüfung mit Playwright ohne Anmeldung: Startseite, `/funktionen` und alle Unterseiten DE/EN, Weiter-Kette von der ersten bis zur letzten Seite, 375 px ohne horizontale Scrollleiste, Kontrast AA (AC-2, AC-4, AC-6, AC-11, AC-12).

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
- 2026-11-24: PO-Vorgabe „an Best Practice orientieren, mit Unterseiten“: Einzelseite mit Sprungankern ersetzt durch Übersicht + neun Unterseiten mit Brotkrumen, Themen-Navigation, Weiter/Zurück, eigenen Titeln (AC-4 bis AC-6, AC-8, AC-10 bis AC-12).
- 2026-11-24: PO-Entscheidung (Rückfrage „öffnen alle Bilder in einer Galerie?“, Antwort „Ja, Galerie gleich mitbauen“): Klick auf ein Bild öffnet eine Galerie mit Blättern innerhalb der Seite (AC-13, Spec 1.2).
- 2026-11-24: AC-13 präzisiert (Tech-Lead-Entscheidung, gängiges Kachel-Muster): Galerie nur auf Unterseiten; auf der Übersicht führt die ganze Kachel inkl. Vorschaubild zur Unterseite, wo dieselben Bilder in der Galerie vergrößert werden können.
- 2026-11-24: Nachtrag #3337 (PO-Entscheidung Option c): Sprachumschalter im Seitenkopf nur ohne Anmeldung, Angemeldete sehen einen Hinweis aufs Konto (AC-6, AC-11); Spec `sprachumschalter_angemeldet_3337.md`.
