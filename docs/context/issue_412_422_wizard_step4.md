# Context: issue_412_422_wizard_step4

## Request Summary
Trip-Wizard Step 4 ("Reports") gegen das SOLL aus dem #404-Phase-3-Audit angleichen:
**#412** (BLOCKER) — dedizierte Kanal-Konfiguration mit On/Off-Toggle pro Kanal + maskierten
Kontaktdaten; angeblich falscher Abend-Briefing-Default 06:00. **#422** (MEDIUM) — Uhrzeiten
sollen 24h (18:00) statt 12h (06:00 PM) anzeigen. Beide Findings betreffen
`frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte`.

## ⚠️ Verifikation gegen echten Code (Lehre aus #419)
Das #404-Audit verglich teils gegen Katalog/Screenshots statt gegen den Code. Daher IST-Stand
gegen den aktuellen Code geprüft — **zwei der vier Audit-Behauptungen sind Fehl-Befunde**:

1. **#412 Problem 2 ("Abend-Default 06:00 statt 18:00") ist FALSCH.**
   `wizardState.svelte.ts:37-38` setzt bereits korrekt:
   ```
   morning: { enabled: true, time: '06:00' },
   evening: { enabled: true, time: '18:00' }
   ```
   Der IST-Screenshot zeigt für **beide** Karten "06:00", weil das native `<input type="time">`
   unter en-US-Browser-Locale (Playwright-Default) den Wert `18:00` als **"06:00 PM"** rendert —
   und das schmale Feld (`class="… w-28 …"`, Step4Reports.svelte:84) das "AM/PM"-Suffix abschneidet.
   Der Auditor las "06:00 PM" als falschen Default "06:00". → **Kein Code-Fix für P2 nötig; nur verifizieren.**

2. **#422 ("12h statt 24h") ist ein Browser-Locale-Artefakt, kein Code-Bug für reale Nutzer.**
   `type="time"` folgt dem Browser-/OS-Locale. Auf deutschen/europäischen Browsern zeigt es bereits
   24h. Das 12h-Format trat nur im Playwright-Screenshot (en-US) auf. → Tech-Lead-Entscheidung Phase 2:
   *nichts tun* (für EU-Nutzer korrekt) **oder** 24h erzwingen (z.B. via `lang`/`step`-Attribut bzw.
   eigenem Widget — native `type="time"` lässt sich nicht direkt auf 24h zwingen).

**Echter Kern der Arbeit = #412 Problem 1:** dedizierte Kanal-Karte mit Toggle + Kontaktdaten.

## SOLL vs. IST (Step 4)
**SOLL** (`claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/mobile-m-wiz-4.png`):
- Karte A "DEINE KANÄLE — Wohin sollen Briefings?": pro Kanal eine Zeile mit Label, **maskierter
  Kontaktangabe** (z.B. `+49 151 ••• 8847`, `gregor_zwanzig@henemm.com`, `@gregor_henemm`) und
  ON/OFF-Switch. SMS-Zeile mit "Fallback"-Hinweis. Subtext "Pro Kanal aktivierbar. Mehr in Einstellungen."
- Karte B "BRIEFINGS · WANN & WAS": Morgen-/Abend-Briefing als Zeilen (Titel + Subtitel + Uhrzeit + Toggle).
- Karte C "ALERT-SCHWELLEN": Vorschau konkreter Schwellen (z.B. Windböen ≥ 50 km/h).

**IST** (Code + `ist-screenshots/mobile-m-wiz-4.png`): 2×2-Grid aus 4 GCards
(Abend / Morgen / Warnungen / Trend). Kanäle erscheinen als kleine, anklickbare `ChannelChip`-Pills
(toggle-bar, aber ohne Kontaktdaten) — in jeder Karte wiederholt.

**Scope-Hinweis:** #412 fordert konkret nur die Kanal-Karte (P1) + Default (P2, hinfällig). Die
weitergehende Restrukturierung (Briefings-Zeilen-Karte, Alert-Schwellen-Karte; Audit-Findings Z. 205–208,
MEDIUM) ist **nicht** Teil von #412/#422. Phase 2 muss den Umfang sauber abgrenzen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-wizard/steps/Step4Reports.svelte` | **Zentrale Datei** beider Issues. Aktive Step-4-Komponente (von TripWizardShell importiert). Aktuell 2×2-Grid mit ChannelChip-Pills. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | Default-Zeiten (Z.37-38, evening bereits 18:00) + `channels`-Booleans (Z.25/35). Beweist Fehl-Befund #412-P2. |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | **Referenz-Implementierung** für Kanal-Toggle-mit-Kontaktdaten: `profile.{mail_to,signal_phone,telegram_chat_id}` → Checkbox-Label `E-Mail (…)` etc. (Z.47-57, 281-313). Pattern für #412-P1. |
| `frontend/src/routes/trips/new/+page.server.ts` | Wizard-Loader. Lädt aktuell **nichts** (`return {}`). Muss `/api/auth/profile` holen, um Kontaktdaten in den Wizard zu reichen. |
| `frontend/src/routes/account/+page.server.ts` | Vorbild: lädt `profile` via `GET /api/auth/profile` mit `gz_session`-Cookie. |
| `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte` | Importiert/rendert Step4Reports; Durchreichpunkt für `profile`-Prop. |
| `frontend/src/lib/components/molecules/ChannelChip.svelte` | Aktuelles Kanal-Indikator-Molecule (Glyph + Label, active-Opacity). |
| `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte` | Bestehendes Toggle-Atom (Checkbox + Label + Hint) aus Epic #136 — evtl. wiederverwendbar für die Kanal-Zeilen. |
| `internal/model/user.go` | Kontaktdaten-Quelle: `Email`, `MailTo`, `SignalPhone`, `TelegramChatID`. |
| `internal/handler/auth.go` | `GET /api/auth/profile` liefert `mail_to/signal_phone/telegram_chat_id` (Z.352-363). |

## Existing Patterns
- **Kanal-Toggle mit Kontaktdaten:** `EditReportConfigSection.svelte` zeigt exakt das gewünschte
  Muster (Checkbox pro Kanal, Kontakt in Klammern). Wiederverwenden statt neu erfinden.
- **Profil-Laden im SvelteKit-Loader:** `account/+page.server.ts` (`fetch(/api/auth/profile, {Cookie})`).
- **Atomic-Migration (Epic #368/#404 Phase 2):** Step 4 wurde bereits auf Eyebrow/GCard/Pill/ChannelChip
  migriert (#391). Neue UI muss Brand-Tokens + Atomic-Komponenten nutzen, hoher Kontrast (WCAG-AA),
  Karten weiß (`--g-card`).
- **Factory-Handler:** Step4Reports nutzt benannte Factory-Handler (Safari-Kompatibilität) — beibehalten.

## Dependencies
- **Upstream:** `wizardState.svelte.ts` (Kanal-/Report-State), `/api/auth/profile` (Kontaktdaten),
  Atomic-Komponenten (`ui/eyebrow`, `ui/g-card`, `ui/pill`, `molecules/ChannelChip`).
- **Downstream:** `wizardState.toReportConfig()` (Z.359-365) mappt `channels.*` → `send_email/…` beim
  Speichern. Trip-Anlage (`POST /api/trips`). Keine Schema-Änderung an Trip/ReportConfig nötig, solange
  nur UI/Anzeige geändert wird.

## Existing Specs
- `docs/specs/modules/issue_300_wizard_redesign.md` — Quelle der aktuellen Step-4-Struktur (im Datei-Header zitiert).
- `docs/specs/modules/epic_136_step4_briefings.md` — ursprüngliche Step-4/Kanal-Spec (ChannelToggle-Herkunft).
- `docs/specs/modules/issue_391_trip_wizard_atomic.md` — Atomic-Migration des Wizards.
- Neue Spec für diese Arbeit: `docs/specs/modules/issue_412_422_wizard_step4.md` (AC-N-Format Pflicht, created ≥ 2026-05-11).

## Risks & Considerations
- **Fehl-Befund-Falle:** #412-P2 ist bereits korrekt (18:00). Nicht „fixen", sondern als
  Verifikations-AC dokumentieren — sonst Regression durch unnötige Änderung.
- **#422 Tech-Lead-Frage:** native `type="time"` kann nicht hart auf 24h gezwungen werden ohne
  Locale-/Widget-Tricks. Für die deutsche Zielgruppe ist 24h bereits der Normalfall. Trade-off in Phase 2 klären.
- **Maskierung:** SOLL zeigt maskierte Telefonnummern (`••• 8847`). `EditReportConfigSection` zeigt
  volle Werte. Maskierungs-Helper neu nötig (Phase 2 — prüfen ob schon einer existiert).
- **Datenschema (CLAUDE.md-Pflicht):** Falls Kanal-Speicherung berührt wird → Read-Modify-Write-Merge,
  kein Überschreiben von `report_config`. Hook `data_schema_backup.py` greift bei Schema-Dateien.
- **Keine Mocks:** Kontaktdaten-Anzeige über echten `/api/auth/profile` testen, nicht mocken.
- **Mobile-Fokus:** Beide Issues haben `mobile`-Label; SOLL ist der Mobile-Screen. Frontend bleibt aber
  Desktop-Planungstool — Responsive prüfen, aber nicht Mobile-first argumentieren.
- **Parallel-Sessions:** Vor Commit `git fetch` + Konflikt-Check; isoliert in diesem Worktree arbeiten.

---

## Analyse & Strategie (Phase 2)

### Typ
Hybrid: **UI-Lücke/Bug**. #412-P1 = fehlende Funktionalität (Kanal-Karte), #412-P2 + #422 = Fehl-Befunde
(verifizieren statt fixen, plus optionale Robustheits-Maßnahme).

### Empfohlener Umfang: issue-genau (NICHT volles SOLL-Redesign)
Die Issues fordern konkret nur die **Kanal-Karte** (#412-P1) und das **Zeitformat** (#422). Die im Audit
ebenfalls gelisteten Punkte (Briefings-Zeilen-Karte „WANN & WAS", Alert-Schwellen-Vorschau-Karte;
Z. 205–208, MEDIUM) sind **nicht** Teil von #412/#422 → außerhalb des Umfangs, bei Bedarf eigenes Issue.
Begründung: Scope-Disziplin + LoC-Limit; das 2×2-Grid bleibt funktional erhalten.

### Architektur-Ansatz
1. **Profil-Daten via zweitem Context-Key** (`setContext('trip-wizard-profile', data.profile)`) statt
   Prop-Drilling oder `WizardState`-Erweiterung. Spiegelt das bestehende `getContext('trip-wizard-state')`-
   Muster, vermeidet Schema-Berührung des WizardState (CLAUDE.md-sensible Datei). Step4Reports liest beides.
2. **Kanal-Karte „DEINE KANÄLE"** an den Kopf von Step 4: pro Kanal (Email/Signal/Telegram/SMS) eine Zeile
   mit Label + maskierter Kontaktangabe + `Switch`-Atom (`size="lg"`, an `wizard.briefings.channels[key]`
   gebunden). SMS-Zeile mit „Fallback"-Hinweis. Quelle der Kontakte: `profile.{mail_to,signal_phone,
   telegram_chat_id}`. Kein Kontakt vorhanden → Zeile zeigt Hinweis „in Einstellungen hinterlegen" und
   Switch deaktiviert (kann nicht senden ohne Adresse).
3. **Wiederholte `channelRow()`-Chips entfernen** aus Abend/Morgen/Warnungen-Karten — Kanäle sind global
   (ein gemeinsames `channels`-Objekt), zentrale Steuerung in der neuen Karte. Entspricht SOLL + Datenmodell.
4. **Maskierungs-Helfer** `maskPhone()` (z.B. in `wizardHelpers`/lokal): `+49 151 ••• 8847`.
5. **#422:** `lang="de"` auf den Zeit-Inputs → erzwingt 24h in Chromium (inkl. Audit-Playwright) unabhängig
   vom OS-Locale; Zeit-Feld minimal verbreitern, damit nie etwas abschneidet. **Kein** eigenes Time-Widget
   (Over-Engineering, schadet Barrierefreiheit). Best-Effort, da Firefox/Safari OS-Locale folgen — für die
   deutsche Zielgruppe ohnehin 24h.
6. **#412-P2:** Default ist bereits `18:00` → **kein Code-Fix**, stattdessen Regressions-Test als Absicherung.

### Implementierungs-Reihenfolge
Tests RED → Profil-Loader (`+page.server.ts`) → Context (`+page.svelte`) → Kanal-Karte + Chip-Entfernung
(`Step4Reports.svelte`) → Mask-Helfer → `lang="de"` → GREEN → Staging-Verifikation (Login, Step 4 sichtbar).

### Scope-Schätzung
| Datei | Art | ~LoC |
|-------|-----|------|
| `routes/trips/new/+page.server.ts` | Profil laden (Cookie) | +10 |
| `routes/trips/new/+page.svelte` | `setContext('trip-wizard-profile', …)` | +3 |
| `steps/Step4Reports.svelte` | Kanal-Karte + Switches + Mask-Aufruf − Chip-Rows | +70 / −12 |
| `trip-wizard/wizardHelpers*` (o. lokal) | `maskPhone()` | +8 |
| Tests (Komponente + Default-Regression) | vitest, ohne Netzwerk-Mocks | +60 |
**Gesamt: 4 Quell-Dateien, ~100–130 LoC** — innerhalb LoC-Limit (250) und Datei-Flag (4–5).

### Risiken
- **Fehl-Befund-Regression:** #412-P2 nicht „korrigieren" — Default bleibt 18:00.
- **Fehlende Kontakte:** Neuer Nutzer ohne hinterlegtes Signal/Telegram → Switch deaktiviert + Hinweis,
  nicht still aktivierbar (sonst Versand ins Leere).
- **#422 nur Best-Effort** cross-browser; ehrlich kommunizieren statt „behoben".
- **Keine Schema-Änderung** an Trip/ReportConfig; `channels`-Mapping (`toReportConfig`) unverändert.
