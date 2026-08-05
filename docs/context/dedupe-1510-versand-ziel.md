# Context: dedupe-1510-versand-ziel (#1510)

## Request Summary

Sieben Stellen formulieren „an welches Ziel geht der Versand?" — nachgemessen sind es aber
**zwei unabhängige Duplikat-Paare**, nicht eine einzige Wiederholung. #1510 verlangt, die
Kontakt-Beschriftung der drei Kanal-Checkboxen (E-Mail/Telegram/SMS) an einer Stelle zu bündeln
und `EditReportConfigSection` denselben Verbindungsstatus wie `VTBriefingChannels` benutzen zu
lassen. `sendTargetLabel()` (aus #1471) bleibt eigenständig — sie liefert einen ganzen Satz
für den Bestätigungsdialog, keine Checkbox-Beschriftung.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | Geteilte Kanal-Card (Versand-Reiter, `context="route"\|"vergleich"`). Zeilen 67–71: `availableChannels`-Block. Zeilen 108,130,158: `E-Mail{profile?.mail_to ? \` (${profile.mail_to})\` : ''}` je Kanal. Zeile 75: nutzt bereits `channelConnectionStatus()` für Dot+Label. |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Trip-Editor-Kanal-Card. Zeilen 90–94: **wortgleicher** `availableChannels`-Block wie oben (dritte, bisher unbenannte Kopie). Zeilen 296,314,332: wortgleiche Kontakt-Beschriftung. Ruft `channelConnectionStatus()` **nicht** auf — hat keinen Dot/Label. |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` | Bestehende geteilte Funktion (Issue #1258 S6). Liefert je Kanal `{ tone, label }` — u.a. E-Mail dreistufig (fehlt/unbestätigt/bestätigt). Wird heute nur von `VTBriefingChannels` aufgerufen. |
| `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts` | #1471. Liefert `{ text, deliverable, gesperrt }` für den Bestätigungsdialog — ein ganzer Satz, keine Checkbox-Beschriftung. Ruft intern bereits `channelConnectionStatus()` auf. Nur von `routes/compare/+page.svelte` benutzt (das ist der Gate-Befund aus #1510, siehe unten). |
| `docs/specs/modules/fix_1471_sende_dialog_ziel.md` | Abschnitt „Offene Grenzen" benennt genau diese sechs Duplikate ausdrücklich als **bewusst nicht saniert** in #1471 — #1510 holt das nach. |

## Existing Patterns

- **Pure Ableitungsfunktion + `__tests__/`-node:test** ist das etablierte Muster im
  `shared/versand-tab/`-Ordner (`channelConnectionStatus.ts`, `sendTargetLabel.ts`,
  `dayWindowClamp.ts`) — kein DOM/Netz, direkt aus `profile`/`preset` abgeleitet.
- `context="route"|"vergleich"`-Parametrisierung für geteilte Organismen (bereits in
  `VTBriefingChannels` vorhanden).
- Read-Modify-Write-Merge in `EditReportConfigSection` (`$effect`-Block) — von der Änderung
  nicht betroffen, nur die Anzeige-Logik ändert sich.

## Der entscheidende Befund für die Analyse-Phase

**`availableChannels` (Checkbox-`disabled`) und `channelConnectionStatus()` (Dot+Label) sind
heute zwei unterschiedliche Härtegrade — kein reiner Textdopplung-Fall:**

| | `availableChannels.email` (beide Komponenten) | `channelConnectionStatus(profile).email.tone` |
|---|---|---|
| Bedingung | `!!profile?.mail_to` (Adresse vorhanden) | `mail_to` **und** `email_verified === true` |
| Wirkung heute | steuert `disabled` der Checkbox | steuert nur Dot-Farbe + Text-Label in `VTBriefingChannels` |

Würde `EditReportConfigSection` für `disabled` direkt auf `channelConnectionStatus().tone === 'good'`
umgestellt, wäre das **kein reines Refactoring**, sondern eine Verhaltensänderung: Nutzer mit
hinterlegter, aber unbestätigter E-Mail könnten den Kanal im Trip-Editor dann nicht mehr
ankreuzen (heute können sie — der Versand scheitert dann serverseitig am
Empfängerschutz, still). Das muss die Analyse-/Spec-Phase explizit entscheiden, nicht die
Implementierung nebenbei.

**PO-Entscheidung (2026-08-05, im Intake-Dialog):**
1. `EditReportConfigSection` bekommt **zusätzlich** Dot+Label wie `VTBriefingChannels`
   (`channelConnectionStatus()` wird dort neu aufgerufen und gerendert) — optische Parität zum
   Versand-Reiter, entspricht der Teilungs-Invariante.
2. Die `disabled`-Bedingung der E-Mail-Checkbox wechselt **in beiden Komponenten** von
   „Adresse vorhanden" auf „Adresse vorhanden **und** bestätigt" (`channelConnectionStatus().email.tone
   === 'good'`) — das ist eine bewusste Verhaltensänderung, kein reines Refactoring: sie verhindert
   das stille Scheitern am Empfängerschutz, das heute möglich ist (Checkbox ankreuzbar, Versand
   liefert serverseitig nichts aus).

**Daraus folgt für den Baustein-Zuschnitt:**
- `availableChannels.email` entfällt als eigener Existenz-Check; `disabled` leitet sich für
  E-Mail direkt aus `channelConnectionStatus().email.tone` ab. Telegram/SMS bleiben bei
  „hinterlegt" (kein Verifikations-Konzept für diese Kanäle vorhanden — `channelConnectionStatus()`
  hat für sie ohnehin nur zwei Zustände, `good`/`neutral`, ohne Zwischenstufe).
- Eine gemeinsame Funktion für die Kontakt-Beschriftung („E-Mail (a@b.de)" / „Telegram (12345)" /
  „SMS (+49…)") ersetzt die sechs Checkbox-Label-Duplikate.
- `VTBriefingChannels` ändert sich ebenfalls (E-Mail-`disabled` nutzt jetzt `channelConnectionStatus()`
  statt `availableChannels.email`) — bisher war das dort schon berechnet, aber ungenutzt für
  `disabled`; das ist die zweite Hälfte derselben Verhaltensänderung, nicht nur Trip-Editor-seitig.

## Dependencies

- **Upstream:** `GET /api/auth/profile` (beide Komponenten laden es per `onMount`/`fetch`,
  identischer Code — evtl. vierte Duplikat-Klasse, aber **nicht** im Issue benannt, daher nicht
  Teil dieses Scopes ohne PO-Bestätigung).
- **Downstream:** Keine Komponente ruft `VTBriefingChannels`/`EditReportConfigSection` intern auf
  Basis der Checkbox-Beschriftung ab — reine Anzeige, kein Datenfluss nach außen.

## Existing Specs

- `docs/specs/modules/fix_1471_sende_dialog_ziel.md` — Ursprung von `sendTargetLabel()` und
  `channelConnectionStatus()`-Nutzung, explizit vorausschauend auf diese Aufräumarbeit verweisend.
- `docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md` — Ursprung von
  `channelConnectionStatus()` (Abschnitt 12, AC-21).

## Analysis

### Type

Feature (Konsolidierung + eine bewusste Verhaltensänderung).

### PO-Entscheidungen (2026-08-05, Intake-Dialog)

1. **Dot+Label auch im Trip-Editor:** `EditReportConfigSection` ruft künftig `channelConnectionStatus()`
   auf und rendert Dot+Label wie `VTBriefingChannels` — optische Parität zum Versand-Reiter.
2. **E-Mail-Checkbox-Sperre verschärft:** `disabled` der E-Mail-Checkbox wechselt in **beiden**
   Komponenten von „Adresse vorhanden" auf „Adresse vorhanden **und** bestätigt"
   (`channelConnectionStatus(profile).email.tone === 'good'`). Telegram/SMS bleiben bei „hinterlegt"
   (kein Verifikations-Konzept für diese Kanäle).
3. **E2E-Testkonflikt (AC-7, `versand-tab-vergleich.spec.ts:139-164`):** Der Test setzt bewusst eine
   unbestätigte Adresse und erwartet eine anklickbare Checkbox — das bricht mit Entscheidung 2. Eine
   „ehrliche" Testkorrektur bräuchte IMAP-Tokenabruf (reale Verifikations-Mail) — unverhältnismäßig
   für dieses Ticket. **Entschieden:** `email.uncheck({ force: true })` — der Test prüft die
   Leerzustand-Anzeige („Kein Kanal aktiv"), nicht die neue Sperre selbst; `force: true` umgeht
   bewusst nur die Interaktions-Blockade, nicht die Testaussage.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/versand-tab/channelContactLabel.ts` | CREATE | Neue pure Funktion: liefert Kontakt-Beschriftung je Kanal (`"E-Mail (a@b.de)"` / `"Telegram (12345)"` / `"SMS (+49…)"`, leer wenn kein Kontakt hinterlegt) aus `profile`. Ersetzt die sechs Ternary-Duplikate. |
| `frontend/src/lib/components/shared/versand-tab/__tests__/channelContactLabel.test.ts` | CREATE | node:test, reine Verhaltenstests (alle drei Kanäle × vorhanden/fehlend). |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Checkbox-Labels nutzen `channelContactLabel()`; E-Mail-`disabled` wechselt von `availableChannels.email` auf `connectionStatus.email.tone === 'good'`; `availableChannels`-Block entfällt für E-Mail (Telegram/SMS bleiben wie bisher). |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | MODIFY | Analog: `channelContactLabel()` für Labels, `channelConnectionStatus()` neu importiert + Dot/Label-Markup ergänzt (analog `VTBriefingChannels.svelte:112-115` etc.), E-Mail-`disabled` verschärft, `Profile`-Interface bekommt `email_verified?: boolean`. |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | MODIFY | AC-7-Test: `email.uncheck({ force: true })` statt `uncheck()`. |

### Scope Assessment

- Files: 6 (2 neu, 4 geändert)
- Estimated LoC: ~+90/-40 (Netto unter dem 250-LoC-Workflow-Limit)
- Risk Level: MEDIUM — sichtbare UI-Änderung im Trip-Editor (neues Dot/Label) + eine echte
  Verhaltensänderung (Checkbox-Sperre), nicht nur internes Refactoring.

### Technical Approach

Ein neuer geteilter Baustein `channelContactLabel.ts` (analog `channelConnectionStatus.ts`,
gleicher Ordner, gleiches Muster: pure Funktion, `profile`-Eingabe, node:test) übernimmt die
Kontakt-Beschriftung. Beide Komponenten binden ihn identisch ein. `channelConnectionStatus()`
wird in beiden Komponenten zur **einzigen** Quelle für den E-Mail-`disabled`-Zustand — das macht
die Verhaltensänderung an beiden Stellen symmetrisch, keine Asymmetrie zwischen Versand-Reiter und
Trip-Editor. `sendTargetLabel()` bleibt unangetastet (nutzt `channelConnectionStatus()` bereits
intern, keine Überschneidung mit den beiden UI-Komponenten).

### Dependencies

- Kein neuer Backend-Endpoint nötig: `email_verified` liefert `/api/auth/profile` bereits
  (`internal/handler/auth.go:453,503`, abgesichert durch `profile_test.go:517-562`).
- `EditReportConfigSection`'s `Profile`-Interface muss um `email_verified?: boolean` erweitert
  werden (fehlt heute, Backend liefert es aber schon mit).

### Open Questions

Keine offenen — beide Design-Entscheidungen (Dot+Label, Checkbox-Sperre) und der Testkonflikt sind
vom PO entschieden.

## Risks & Considerations

- **Verhaltensänderung vs. reines Refactoring** (siehe oben) — größtes Risiko, muss in Phase 2/3
  geklärt werden, sonst schleicht sich eine Checkbox-Sperre ein, die niemand angefordert hat.
- **Pendant-Gate (#1481 B):** Eine neue Datei in `shared/versand-tab/**` ist unproblematisch
  (das ist der geteilte Ordner selbst); falls eine neue Datei stattdessen in `edit/**` oder
  `compare/**` läge, würde der Gate greifen.
- **Mutations-Gegenprobe:** Die Kontakt-Beschriftung hat einen ternären Ausdruck
  (`profile?.mail_to ? ... : ''`) — die Extraktion darf die drei bestehenden Fallgruben (fehlende
  Adresse, gesetzte Adresse, `sms_allowed === false`) nicht durch die Zusammenführung verlieren.
- **Punkt 3 des Issues** (Pendant-Gate um „geteilter Ordner, aber nur ein Aufrufer" erweitern)
  ist laut vorheriger Einschätzung ein separates Vorhaben (Wächter-Änderung statt Produktfehler)
  — hier **nicht** umgesetzt, geht als Sammel-Eintrag an #1199.
