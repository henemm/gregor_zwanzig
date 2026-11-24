# Context: feat-3319-oeffentliche-doku

Gebündelt: #3319 (Startseite aktuell, Level erklärt) + #3320 (öffentliche Funktionsübersicht DE/EN mit Bildern), Epic #3318.

## Request Summary
PO 24.11.2026: „Aktualisiere die öffentliche Dokumentation von Gregor auf https://gregor20.henemm.com/ (SMS ist zum Beispiel verfügbar). Was ist kostenlos und was Premium? Erstelle darüber hinaus eine umfangreiche Dokumentation/Feature-Übersicht mit allen wesentlichen Features auf EN/DE mit Screenshots.“

## Ist-Stand
- Öffentlich ohne Login ist nur exakt `/` (Startseite, #2520) plus Auth-Seiten (`frontend/src/hooks.server.ts:38-67`, `publicPaths` + Sonderfall `/`).
- Startseite `frontend/src/routes/_start/Startseite.svelte`, Texte `frontend/src/lib/i18n/messages/{de,en}/start.json`.
  Veraltet: `start.ankommt.kanaele` („SMS oder Satelliten-Messenger … in Arbeit bzw. auf Anfrage“), `start.hero.lead`/`start.meta.description` („E-Mail als Hauptkanal, auf Wunsch zusätzlich Telegram“) — widerspricht ADR-0095 (vier gleichrangige Kanäle) und ADR-0049 (Premium-SMS).
- Hilfeseite `/hilfe` nur für Angemeldete (`hooks.server.hilfe_nur_eingeloggt.test.ts`), kurze Texte, Befehlsliste mit Drift-Wächter `tests/test_hilfe_befehle_drift.py`.
- Layout `frontend/src/routes/+layout.svelte:210-213`: `publicPages` + `/` ausgeloggt ⇒ Zweig ohne Sidebar, mit `AppFooter`.
- Beispielbilder Startseite: `frontend/static/landing/{,en/}*.png` (Renderer-Bilder, < 200 KB, Test `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` AC-7/#2777), Skript `scripts/landing_screenshots.py`.

## Level (Code ist Quelle der Wahrheit; Name in der UI: „Level“ Free / Standard / Premium)
| | Free | Standard | Premium |
|---|---|---|---|
| Aktive Trips | 3 | 15 | 50 |
| Aktive Ortsvergleiche | 2 | 10 | 30 |
| Orte gesamt | 10 | 50 | 200 |
| E-Mail, Telegram | ja | ja | ja |
| SMS / Tag (Alarm-Reserve 2) | – | 10 | 10 |
| Premium-SMS (Garmin inReach) / Tag (Reserve 3) + Antworten / Tag | – | – | 15 + 15 |
| Proaktive Alarme / Tag | 2 | 4 | unbegrenzt |
Quellen: `internal/model/tier.go` (Quoten, SmsAllowed, PremiumSmsAllowed), `src/services/user_tier.py` (SMS-/Premium-SMS-Tageslimits, `daily_alert_limit`).
- Offene Registrierung ⇒ Free (`EffectiveTier` fail-closed). Einladung des Betreibers kann Level setzen (#2519). Level-Wechsel: Antrag im Konto, Betreiber prüft (`konto.level.*`, RequestTierChangeHandler). **Keine Preise, kein Bezahlweg** im Code.

## Bilder der echten Oberfläche
- Staging-Prüfkonto mit Mockup-Daten (Premium, GR221 Mallorca 4 Etappen, Orts-Vergleich Münsterland, alle vier Kanäle mit fiktiven Werten): `scripts/staging_pruefkonto_mockupdaten.py`, Runbook `docs/runbooks/staging_pruefkonto_seed.md`. Läuft nur auf dem Host (Loopback 8091), Zugang `GZ_PRUEFKONTO_*` in Staging-`.env`.
- Mail/Telegram/Alarm-Bilder reproduzierbar aus Renderern (`scripts/landing_screenshots.py` als Muster).
- Playwright vorhanden (`frontend/e2e`, Python-Playwright im Landing-Skript).

## Existing Specs
- `docs/specs/modules/oeffentliche_startseite_2520.md`, `docs/specs/modules/startseite_en_bilder_2777.md`, `docs/specs/modules/onboarding_standardwerte_hilfe.md`, `docs/specs/modules/mengen_quoten_je_tier.md`, `docs/specs/modules/sms_daily_limit.md`.

## Risks & Considerations
- Öffentliche Route erweitert die Auth-Grenze: nur exakte Pfade, kein `startsWith`, keine Nutzerdaten, kein Go-API-Aufruf (Muster #2520/#2131).
- Bilder dürfen keine echten Personendaten zeigen (Prüfkonto-Mail, Telefonnummern): nur Seed-Fiktivwerte, Mail-Adresse maskieren.
- Level-Zahlen nicht doppelt pflegen: Texte gegen Code-Tabellen per Test absichern (Drift-Wächter wie bei der Hilfe-Befehlsliste).
- Zweisprachigkeit: alle Texte über Katalog, EN-Bilder aus EN-Oberfläche (ADR-0104, #2777-Lehre).
- Keine Handlungsempfehlungen in Produkttexten („nur Daten“-Vorgabe) — Funktionsbeschreibung, keine Wetter-Ratschläge.
- Bildgröße (Ladezeit unterwegs): je Bild < 200 KB wie Startseite.

## Funktionsinventar (Explore-Agent, 24.11.2026)
1. Cockpit `/` (angemeldet): Trips & Vergleiche, nächster Versand, Alarmstatus, Startklar-Checkliste.
2. Trip anlegen `/trips/new`: Route → Etappen & GPX (je Etappe eine GPX) → Wegpunkte prüfen; Tempo bestimmt Gehzeiten.
3. Trip-Hub `/trips/[id]?tab=uebersicht|etappen|wetter|zustellung`; Briefing sofort senden, archivieren.
4. Ortsvergleich `/compare`, `/compare/new`, `/compare/[id]`; Orte `/locations`; ab 2 Orten Vergleichstabelle ohne Rangfolge; „stehender Monitor“.
5. Briefings morgens (heute, Std. 07:00) / abends (morgen, 18:00), Stundentabelle + 3-Tages-Ausblick.
6. Reiter Wetter: Vorlagen/Profile, Metriken, Reihenfolge, Kurzformen, Schwellen „Alarm ab“ (Gelb/Orange/Rot), „Was steht wo“ je Kanal, Vorschau, eigene Vorlagen (Konto → Wetter-Profile). Layout-/Versand-Tab gibt es nicht mehr.
7. Reiter Zustellung: Zeiten, Laufzeit, Kanalmatrix Briefing/Alarm, Dringlichkeit je Kanal (SMS ab mittel, Premium-SMS nur hoch), stille Stunden, Cooldown, gesperrte Kanäle mit Grund.
8. Alarme: Wetteränderung + Entwarnung, Vorboten (Gewitter-/Starkregen-Beginn), amtliche Warnungen (Météo-France Vigilance, Meteoalarm, GeoSphere, DWD, DPC, SLF Lawinen, Massiv-Sperrungen, Waldbrand) mit Entwarnung, Radar-Regen-Nowcast; Tageslimit 2/4/unbegrenzt.
9. Kanäle (`/account`): E-Mail (alle), Telegram-Bot ausführlich/Kurzstil (alle), SMS mit Bestätigungscode (ab Standard), Premium-SMS Garmin inReach mit Verknüpfungscode (nur Premium); Testversand; Kontingentanzeige.
10. Antwort-Befehle über E-Mail, Telegram, Premium-SMS (normale SMS ohne Eingang): HEUTE, MORGEN, JETZT, GEWITTER, STRECKE, RUHETAG, STATUS, PAUSE, SKIP, STOP, WEITER, HILFE, KUERZEL, STARTDATUM, REPORT (+EN); Ortsvergleich nur PAUSE/WEITER/HILFE. Quelle `hilfe.json`, `docs/features/f6-trip-commands.md`.
11. Archiv `/archiv`: automatisch nach Trip-Ende, reaktivieren/löschen.
12. Konto: Sprache DE/EN, Level + Antrag, Mengenanzeige, Passkeys, Magic-Link, Google-Login, Datenexport, Konto löschen.
13. PWA installierbar, Offline-Übersicht mit letztem Stand (Speichern offline gesperrt).
14. Wetterdaten: Open-Meteo-Modellwahl nach Region (AROME 1,3 km FR/Balearen, ICON-D2 2 km Alpen/DE, MetNo Nordic 1 km, ICON-EU 7 km, ECMWF global), weitere Provider DWD/BrightSky/GeoSphere/Météo-France, Radar-Nowcast (RADOLAN, INCA, ICON-2I, AROME-HD).
15. MCP-Konnektor für die Claude-App: nur freigegebene Nutzer (ADR-0128) — öffentlich nicht bewerben.
16. Admin: nicht öffentlich dokumentieren; ebenso `/_design*`, `/email-preview-dev`.

## Analysis

### Type
Feature (gebündelt #3319 + #3320, Epic #3318)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/i18n/messages/{de,en}/start.json | MODIFY | `meta.description`, `hero.lead`, `ankommt.kanaele`: vier Kanäle verfügbar; neue Keys Level-Kurzübersicht + Link zur Funktionsseite |
| frontend/src/routes/_start/Startseite.svelte | MODIFY | Level-Block (Kurzform) + Link `/funktionen` |
| frontend/src/lib/level_grenzen.json | CREATE | einzige Text-Quelle der Level-Zahlen (Trips/Vergleiche/Orte, SMS/Tag, Premium-SMS/Tag + Antworten, Alarme/Tag; null = unbegrenzt) |
| frontend/src/lib/components/…/LevelTabelle.svelte | CREATE | gemeinsam für Startseite (kurz) und Funktionsseite (voll), Texte aus Katalog, Zahlen aus JSON |
| internal/model/tier_katalog_drift_test.go | CREATE | Go-Drift-Test: JSON gegen `quotaTable`, `SmsAllowed`, `PremiumSmsAllowed` (mit Gegenprobe) |
| tests/test_level_grenzen_drift.py | CREATE | Python-Drift-Test: JSON gegen `user_tier.py` (SMS 0/10/10, Premium-SMS 0/0/15, Antworten 0/0/15, Alarme 2/4/None), Muster `test_hilfe_befehle_drift.py` |
| frontend/src/hooks.server.ts | MODIFY | öffentlicher exakter Pfad `/funktionen` neben `/` (Set, kein startsWith), ohne userId/API |
| frontend/src/routes/+layout.svelte | MODIFY | `publicPages` um `/funktionen` (Zweig ohne Sidebar, mit AppFooter) |
| frontend/src/routes/funktionen/+page.svelte, +page.server.ts | CREATE | öffentliche Funktionsübersicht, `oeffentlich: true`, kein API-Aufruf |
| frontend/src/routes/_funktionen/*.svelte | CREATE | Abschnitte (Inventar Punkte 1–14), Inhaltsverzeichnis mit Sprungankern, Bild-Block (Bild, Alt, Unterschrift) |
| frontend/src/lib/i18n/messages/{de,en}/funktionen.json (+ Katalog-Registrierung in i18n/index.ts) | CREATE/MODIFY | alle Texte DE/EN |
| scripts/landing_screenshots.py | MODIFY | DE- und EN-Ausgabe; zusätzlich SMS- und Premium-SMS-Bild aus echten Renderern |
| scripts/funktionen_screenshots.py | CREATE | Playwright gegen Staging-Prüfkonto (Mockup-Seed), `gz_lang`-Cookie je Sprache; Cockpit, Trip-Hub (Wetter, Zustellung), Trip anlegen, Ortsvergleich, Konto/Kanäle, Archiv |
| frontend/static/funktionen/{,en/}*.webp | CREATE | Bilder < 200 KB, feste width/height, lazy |
| frontend/src/lib/i18n/__tests__/en_katalog_regeln.test.ts | MODIFY | alte Regel „SMS nur mit in progress/on request" umkehren: kein start.*/funktionen.*-Wert darf SMS/Satellit als „in Arbeit/auf Anfrage" bezeichnen |
| frontend/src/lib/i18n/__tests__/textkatalog.test.ts | MODIFY | Bild-Prüfung (Existenz, < 200 KB, Alt, DE/EN-Paar) auf funktionen.* erweitern |
| frontend/src/hooks.server*.test.ts | MODIFY/CREATE | `/funktionen` + `/` öffentlich; `/funktionen/x`, `/funktionenx`, `/hilfe`, `/account` nicht |
| docs/specs/modules/oeffentliche_startseite_2520.md | MODIFY | AC-6 „Abgelöst durch #3319" |
| docs/runbooks/funktionen_screenshots.md | CREATE | Bilder neu erzeugen (Host, Prüfkonto), Sichtprüfung Personendaten |

### Scope Assessment
- Files: ~25 (+ ca. 20–30 Bilddateien)
- Estimated LoC: +1200–1600 / -30
- Risk Level: MEDIUM (Auth-Grenze bekommt einen zweiten öffentlichen Pfad; viele Bilder; Texte müssen genau dem Code entsprechen)

### Technical Approach
- **Bündelung beibehalten** (Intake-Entscheidung, PO-Vorgabe „kleine verwandte Issues als Paket"): eine Spec, eine Freigabe; die Level-Tabelle wird von beiden Seiten genutzt. Umsetzung intern in Reihenfolge: (1) Startseite + Level-Daten + Drift-Tests, (2) Route `/funktionen` + Auth-Grenze, (3) Texte, (4) Renderer-Bilder, (5) UI-Bilder vom Staging-Prüfkonto, (6) Bild-Tests.
- **Route `/funktionen`**, ein Pfad für DE/EN, Sprache wie auf der Startseite (Cookie `gz_lang` > Accept-Language > de, Sprachumschalter auch dort). Kein `/en/…`-Präfix (neues Muster ohne Not).
- **Level-Zahlen** nur in `level_grenzen.json`; der Katalog enthält Texte mit Platzhaltern; Go- und Python-Drift-Tests halten die JSON-Datei an den Code gebunden. Keine Preise, kein Bezahlweg: Wechsel = „Antrag im Konto, der Betreiber prüft". Offene Registrierung = Free.
- **Bilder**: WebP (Qualität ~80) mit festen Maßen und `loading="lazy"`; Mail/Telegram/SMS/Premium-SMS/Alarm aus echten Renderern (deterministisch, ohne Netz), UI-Bilder aus der echten Staging-Oberfläche mit Prüfkonto-Seed (nur fiktive Daten, Mail-Adresse/Nummern maskiert). Jedes Bild per Auge auf Personendaten geprüft.
- **Inhalt**: Inventar Punkte 1–14 (Cockpit, Trip anlegen, Trip-Hub, Briefings, Reiter Wetter, Zustellung, Alarme inkl. amtliche Warnungen und Radar, Ortsvergleich, Kanäle, Antwort-Befehle, Archiv, Konto, App/Offline, Wetterdaten). Nicht aufnehmen: Claude-Konnektor (nur freigegebene Nutzer), Admin, Design-Seiten. Nur Funktionsbeschreibung, keine Wetter-Ratschläge (ADR-0007). Befehlsliste aus derselben Quelle wie die Hilfe bzw. per Drift-Test gebunden.
- `/hilfe` bleibt nur für Angemeldete.

### Dependencies
- Level-Quellen: `internal/model/tier.go:52-58` (quotaTable), `:3-25` (SmsAllowed, PremiumSmsAllowed); `src/services/user_tier.py:15-20, :87-109`.
- Sprache: `frontend/src/lib/i18n/resolveLang.ts`, `SprachUmschalter.svelte`, `routes/lang/+server.ts`.
- Bilder: `scripts/landing_screenshots.py` (Renderer), `scripts/staging_pruefkonto_mockupdaten.py` + Runbook `docs/runbooks/staging_pruefkonto_seed.md` (Host, Loopback 8091).
- Tests: `en_katalog_regeln.test.ts` (alte SMS-Regel kollidiert, wird bewusst umgekehrt), `textkatalog.test.ts`, `hardcode_scan.ts`, `hooks.server*.test.ts`, `tests/test_hilfe_befehle_drift.py`.
- Specs/ADRs: 2520 (AC-6 abgelöst), 2777 (Bildregeln), ADR-0095, ADR-0049, ADR-0104, ADR-0007; `epic_user_tiers_overview.md` nennt Premium-SMS noch „existiert nicht" — dort Hinweis nachziehen.

### Open Questions
- keine Produktfrage offen: Level-Namen, Grenzen und Wechselweg stehen im Code; Preise gibt es nicht und werden nicht genannt. Die Spec-Freigabe ist die PO-Entscheidung über den Inhalt.
