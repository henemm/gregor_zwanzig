---
entity_id: issue_412_422_wizard_step4
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [frontend, trip-wizard, channels, svelte, issue-412, issue-422, epic-404, mobile]
---

<!-- Issue #412 (BLOCKER) + #422 (MEDIUM) — Trip-Wizard Step 4: Kanal-Karte mit Kontaktdaten + 24h-Uhrzeit -->

# Issue #412 + #422 — Trip-Wizard Step 4: Kanal-Karte mit Kontaktdaten + 24h-Uhrzeit

## Approval

- [x] Approved

## Zweck

Die letzte Seite des Tour-Assistenten (Schritt 4 „Reports/Briefings") bringt die Versandkanäle
auf das SOLL-Design des #404-Phase-3-Audits: Statt kleiner, in jeder Karte wiederholter Kanal-Tags
gibt es **eine dedizierte Karte „DEINE KANÄLE"** mit je einer Zeile pro Kanal
(E-Mail / Signal / Telegram / SMS), die die **hinterlegte Kontaktangabe** aus dem Nutzerprofil zeigt
und per Schalter (`Switch`) an-/abschaltbar ist. Zusätzlich wird die Uhrzeit-Anzeige (#422) gegen das
12-Stunden-Artefakt des Test-Browsers abgesichert.

**Wichtige Korrektur zweier Audit-Behauptungen (gegen den echten Code verifiziert):**
- #412-Problem-2 („Abend-Default 06:00 statt 18:00") ist ein **Fehl-Befund** — `wizardState.svelte.ts`
  setzt bereits korrekt `evening.time = '18:00'`. Der Screenshot zeigte „06:00 PM" (= 18:00) mit
  abgeschnittenem „PM" unter en-US-Locale. → Kein Fix, nur Regressions-Absicherung.
- #422 („12h statt 24h") ist ein **Browser-Locale-Artefakt** des nativen `<input type="time">`; auf
  deutschen Geräten bereits 24h. → Best-Effort-Härtung (`lang="de"` + breiteres Feld), kein eigenes Widget.

## Quelle / Source

**Geänderte Dateien (alle im Frontend-Layer, SvelteKit):**

| Datei | Art der Änderung |
|-------|-----------------|
| `frontend/src/routes/trips/new/+page.server.ts` | Profil via `GET /api/auth/profile` (Session-Cookie) laden, an Page reichen |
| `frontend/src/routes/trips/new/+page.svelte` | `data.profile` empfangen, via `setContext('trip-wizard-profile', …)` bereitstellen |
| `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` | Neue Karte „DEINE KANÄLE" (Switch + Kontakt je Kanal); wiederholte `channelRow()`-Chips aus Abend/Morgen/Warnungen-Karten entfernen; `lang="de"` + breiteres Zeit-Feld |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` *(oder lokal in Step4Reports)* | `maskPhone()`-Helfer für `+49 151 ••• 8847` |

**Nicht geänderte Dateien (bewusst):**
- `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` — Default `evening.time='18:00'` ist bereits
  korrekt; `channels`-Booleans + `toReportConfig()`-Mapping bleiben unverändert (keine Schema-Berührung).
- `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` — nicht gemountet, nicht anfassen.
- Trip-/ReportConfig-Persistenz (Go + Python) — keine Backend-Änderung.

> **Schicht-Hinweis:** Alle produktiven Änderungen liegen im SvelteKit-Frontend
> (`frontend/src/routes/trips/new/`, `frontend/src/lib/components/trip-wizard/`). Die Kontaktdaten-Quelle
> `GET /api/auth/profile` (Go, `internal/handler/auth.go`) wird nur **gelesen**, nicht verändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/auth/profile` | Go-API (read-only) | Liefert `mail_to`, `signal_phone`, `telegram_chat_id` des angemeldeten Nutzers |
| `$lib/components/atoms` → `Switch` | Atom | Soll-Schalter pro Kanal (`size="lg"`, `bind:checked`, `onchange`) |
| `$lib/components/ui/g-card` `GCard` | Komponente | Karten-Container „DEINE KANÄLE" |
| `$lib/components/ui/eyebrow` `Eyebrow` | Komponente | Karten-Überschrift („DEINE KANÄLE") |
| `wizard.briefings.channels.{email\|signal\|telegram\|sms}` | WizardState | An-/Aus-Zustand pro Kanal (gemeinsam für alle Briefings) |
| `frontend/src/routes/account/+page.server.ts` | Referenz | Vorbild für Profil-Load mit `gz_session`-Cookie |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Referenz | Vorbild für Kanal-Anzeige mit Kontaktdaten |
| `frontend/src/lib/contrast-audit.test.ts` | Test-Suite | WCAG-AA-Audit; keine neuen Verletzungen durch neue Karte |

## Implementation Details

```
1. trips/new/+page.server.ts:
   load({cookies}): session = cookies.get('gz_session')
   profile = fetch(`${API}/api/auth/profile`, {Cookie: gz_session}).ok ? json : null  (fail-soft)
   return { profile }

2. trips/new/+page.svelte:
   let { data } = $props()
   setContext('trip-wizard-profile', data.profile)   // null-tolerant

3. Step4Reports.svelte:
   const profile = getContext('trip-wizard-profile')  // {mail_to?, signal_phone?, telegram_chat_id?} | null
   maskPhone('+49 151 23 45 8847') -> '+49 151 ••• 8847'  (letzte 4 Ziffern sichtbar)

   CHANNEL_ROWS (in fester Reihenfolge):
     email    -> contact = profile?.mail_to    (unmaskiert),     hint = —
     signal   -> contact = maskPhone(profile?.signal_phone),     hint = —
     telegram -> contact = profile?.telegram_chat_id (unmaskiert),hint = —
     sms      -> contact = maskPhone(profile?.signal_phone),      hint = "Fallback"

   Karte „DEINE KANÄLE" (oben, volle Breite):
     je Zeile: Label (Mono-Eyebrow-Stil) · Kontakt/Hinweis · <Switch bind:checked={channels[key]} size="lg">
     Kein Kontakt vorhanden -> Switch disabled, Hinweistext "in Einstellungen hinterlegen",
       channels[key] wird NICHT automatisch auf true gesetzt.

   Abend-/Morgen-/Warnungen-Karten: {@render channelRow()} ENTFERNEN.

   Zeit-Inputs (evening-time, morning-time): lang="de" ergänzen, Feldbreite so, dass nichts abschneidet.
```

## Expected Behavior

- **Input:** Eingeloggte Session mit (teilweise) hinterlegten Kontaktdaten; frisch initialisierter WizardState.
- **Output:** Schritt 4 zeigt oben die Kanal-Karte mit Kontakten + Schaltern; darunter das bestehende
  Karten-Grid (Abend/Morgen/Warnungen/Trend) **ohne** wiederholte Kanal-Chips; Uhrzeiten im 24h-Format.
- **Side effects:** Keine. Schalter mutieren ausschließlich `wizard.briefings.channels.*`; Persistenz-Mapping
  (`toReportConfig` → `send_email/_signal/_telegram/_sms`) bleibt unverändert.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer mit hinterlegten Kontaktdaten / When er den Tour-Assistenten bis
  Schritt 4 öffnet / Then erscheint eine Karte „DEINE KANÄLE" mit genau vier Zeilen (E-Mail, Signal,
  Telegram, SMS), jede mit Kanal-Label, Kontaktangabe und einem `Switch`-Schalter.
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-2:** Given das Profil enthält eine Telefonnummer in `signal_phone` / When Schritt 4 gerendert wird /
  Then werden Signal- und SMS-Nummer maskiert dargestellt (nur die letzten vier Ziffern sichtbar, davor
  `•••`), während E-Mail (`mail_to`) und Telegram-Handle (`telegram_chat_id`) unmaskiert erscheinen.
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-3:** Given die Kanal-Karte ist sichtbar und ein Kanal hat eine Kontaktangabe / When der Nutzer den
  Schalter dieses Kanals umlegt / Then ändert sich `wizard.briefings.channels[key]` entsprechend auf
  true bzw. false (über `bind:checked`/`onchange`).
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-4:** Given ein Kanal hat im Profil keine Kontaktangabe (z.B. leeres `telegram_chat_id`) / When
  Schritt 4 gerendert wird / Then ist der Schalter dieses Kanals deaktiviert, ein Hinweis „in Einstellungen
  hinterlegen" erscheint, und `channels[key]` wird nicht automatisch aktiviert.
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-5:** Given Schritt 4 ist gerendert / When man die Karten Abend-Briefing, Morgen-Update und Warnungen
  betrachtet / Then enthalten diese keine wiederholten Kanal-Chips mehr — die Kanal-Steuerung erfolgt
  ausschließlich in der Karte „DEINE KANÄLE".
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-6:** Given ein frisch über `new WizardState()` initialisierter Zustand / When Schritt 4 geöffnet wird /
  Then zeigt das Abend-Briefing-Uhrzeitfeld den Wert `18:00` und das Morgen-Update `06:00` (Verifikation
  des bestehenden korrekten Defaults — bewusst keine Code-Änderung am Default).
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-7:** Given die Uhrzeit-Eingabefelder in Schritt 4 / When sie im DOM gerendert werden / Then tragen sie
  das Attribut `lang="de"` und sind breit genug, dass keine AM/PM-Kennung sichtbar abgeschnitten wird
  (24-Stunden-Anzeige in Chromium unabhängig vom Betriebssystem-Locale).
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-8:** Given der Aufruf von `/trips/new` mit gültiger Session / When die Seite serverseitig lädt / Then
  ruft der Loader `GET /api/auth/profile` mit dem `gz_session`-Cookie auf und stellt das Profil dem Wizard
  über den Context `trip-wizard-profile` bereit; bei fehlgeschlagenem Abruf bleibt `profile` null (fail-soft,
  Karte zeigt dann alle Kanäle als „in Einstellungen hinterlegen").
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

- **AC-9:** Given die neue Kanal-Karte wird gerendert / When das WCAG-Kontrast-Audit
  (`contrast-audit.test.ts`) läuft / Then meldet es keine neuen Verletzungen, und die Karte nutzt
  Atomic-Komponenten (`Switch`, `GCard`, `Eyebrow`) sowie Brand-Tokens statt Hex-Literalen.
  - Test: `frontend/src/lib/components/trip-wizard/__tests__/issue_412_422_step4.test.ts` (node:test, RED-Artefakt: `docs/artifacts/issue_412_422_wizard_step4/test-red-output.txt`)

## Known Limitations

- **#422 ist nur Best-Effort:** `lang="de"` erzwingt 24h zuverlässig in Chromium (inkl. Audit-Playwright);
  Firefox und Safari folgen dem OS-Locale und ignorieren das Attribut bei `type="time"`. Für die deutsche
  Zielgruppe ist das unkritisch (OS bereits 24h). Ein eigenes Time-Widget wird bewusst vermieden
  (Over-Engineering, Barrierefreiheits-Nachteil).
- **SMS-Versand:** Die SMS-Zeile zeigt die Telefonnummer (geteilt mit Signal) als „Fallback"-Kanal; der
  tatsächliche SMS-Versand-Status ist nicht Teil dieses Specs (nur die Schalter-UI im Wizard).
- **Weitergehendes SOLL-Redesign** (Briefings-Zeilen-Karte „WANN & WAS", Alert-Schwellen-Vorschau-Karte;
  Audit-Findings MEDIUM) ist **außerhalb des Umfangs** von #412/#422 → ggf. eigenes Issue.

## Changelog

- 2026-05-27: Initial spec created (Phase 3) — #412 Kanal-Karte + #422 24h-Härtung; #412-P2 als Fehl-Befund klassifiziert.
- 2026-05-27: Implementation GREEN + Adversary VERIFIED (F002/F003/F001 behandelt). Kanal-Karte mit maskierten Kontaktdaten, Switch-Atome, Profile-Context, Zeit-Inputs gehärtet, wiederholte Chips entfernt.
