---
entity_id: fix_1510_versand_ziel_dedupe
type: bugfix
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.0"
tags: [versand, trip-editor, compare, frontend]
---

# Kontakt-Beschriftung + Verbindungsstatus der Kanal-Checkboxen bündeln (#1510)

## Approval

- [ ] Approved

## Purpose

Die Kontakt-Beschriftung der drei Kanal-Checkboxen (E-Mail/Telegram/SMS) ist heute sechsfach als
wortgleicher Ternary-Ausdruck dupliziert — dreimal in `VTBriefingChannels.svelte`, dreimal in
`EditReportConfigSection.svelte`. Diese Spec bündelt sie in einer geteilten Funktion
`channelContactLabel()`, gibt dem Trip-Editor (`EditReportConfigSection`) denselben
Dot+Label-Verbindungsstatus wie dem Versand-Reiter (`VTBriefingChannels`), und verschärft dabei
bewusst die E-Mail-Checkbox-Sperre: eine hinterlegte, aber unbestätigte Adresse macht den Kanal
künftig in beiden Komponenten nicht mehr ankreuzbar — sie scheitert heute still am serverseitigen
Empfängerschutz. `sendTargetLabel()` (#1471, Bestätigungsdialog-Satz) ist keine Überschneidung und
bleibt unverändert.

## Source

- **File:** `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte`
- **Identifier:** Checkbox-Label-Ternaries (Zeilen 108,130,158) und `availableChannels`-Block
  (Zeilen 67–71); Gegenstück `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
  (Zeilen 90–94, 296,314,332)

## Estimated Scope

- **LoC:** ~+90/-40
- **Files:** 6 (2 neu, 4 geändert — siehe context-Dokument, hier 5 in der Tabelle plus Testdatei)
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/versand-tab/channelContactLabel.ts` | CREATE | Neue pure Funktion: liefert die Kontakt-Beschriftungs-Suffixe je Kanal aus `ConnectionProfile` (z.B. `" (a@b.de)"` oder `""`). Ersetzt die sechs Ternary-Duplikate in beiden Komponenten. |
| `frontend/src/lib/components/shared/versand-tab/__tests__/channelContactLabel.test.ts` | CREATE | node:test, reine Verhaltenstests: alle drei Kanäle × Kontakt vorhanden/fehlend. |
| `frontend/src/lib/components/shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` | CREATE | node:test, SSR-Render-Tests (svelte/server) für AC-2 bis AC-6 — ursprünglich in dieser Tabelle fehlend, aber von AC-2/AC-3/AC-4/AC-5/AC-6 bereits verlangt; in der RED-Phase nachgetragen (Zeile korrigiert 2026-08-05). |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | MODIFY | Checkbox-Labels nutzen `channelContactLabel()` statt eigener Ternaries (Zeilen 108,130,158). E-Mail-`disabled` wechselt von `availableChannels.email` auf `connectionStatus.email.tone === 'good'` (Zeile 108); der `availableChannels`-Eintrag für `email` entfällt, Telegram/SMS bleiben unverändert (Zeilen 69–70 bestehen fort). |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | MODIFY | Analog: `channelContactLabel()` für die drei Labels (Zeilen 296,314,332); neuer Import + Aufruf von `channelConnectionStatus()` (analog `VTBriefingChannels.svelte:17,75`) plus Dot/Label-Markup je Kanal (analog `VTBriefingChannels.svelte:112–115,133–136,161–164`); E-Mail-`disabled` verschärft wie oben; `Profile`-Interface (Zeilen 82–87) bekommt `email_verified?: boolean`. |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | MODIFY | AC-7-Test (Zeile ~155): `email.uncheck()` → `email.uncheck({ force: true })`, da die zuvor gesetzte, unbestätigte Testadresse die Checkbox jetzt sperrt; der Test prüft weiterhin die Leerzustand-Anzeige, nicht die neue Sperre. |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `channelConnectionStatus()` (`shared/versand-tab/channelConnectionStatus.ts:29-51`) | function | Liefert bereits die Drei-Zustands-Logik für E-Mail (fehlt/unbestätigt/bestätigt) und den Verbunden-Status für Telegram/SMS — wird in `EditReportConfigSection` neu aufgerufen (bisher nur in `VTBriefingChannels`) und ist Basis der verschärften E-Mail-`disabled`-Bedingung in beiden Komponenten. |
| `GET /api/auth/profile` | endpoint | Liefert `mail_to`, `email_verified`, `telegram_chat_id`, `sms_to`, `sms_allowed` des angemeldeten Nutzers (`internal/handler/auth.go:453,503`); beide Komponenten laden ihn bereits identisch per `onMount`/`fetch`, unverändert durch diese Spec. |
| `ConnectionProfile`-Typ (`shared/versand-tab/channelConnectionStatus.ts:19-25`) | type | Wiederverwendete Eingabe-Form für `channelContactLabel()` — keine neue Profil-Form nötig. |

## Implementation Details

**Neue Funktion `channelContactLabel(profile)`** (Ort: `shared/versand-tab/`, gleicher Ordner wie
`channelConnectionStatus.ts`/`sendTargetLabel.ts`, gleiches Muster: pure Funktion, ein Aufruf pro
Komponente, `node:test`-testbar):

```
Eingabe:  ConnectionProfile | null | undefined  (mail_to, telegram_chat_id, sms_to, ...)
Ausgabe:  { email: string; telegram: string; sms: string }
          — je Kanal der Suffix " (<Kontakt>)", oder "" wenn kein Kontakt hinterlegt.
```

**Design-Entscheidung — EIN Aufruf, drei Felder (kein Kanal-Diskriminator, keine drei
Einzelfunktionen):** Die Funktion spiegelt bewusst die Objektform von
`channelConnectionStatus()` (ein Aufruf liefert alle drei Kanäle als Objekt-Felder). Das hält den
Aufrufaufwand in beiden Komponenten bei je einem `$derived`-Aufruf (analog
`connectionStatus = $derived(channelConnectionStatus(profile))`), statt drei separaten Aufrufen pro
Komponente (sechs insgesamt). Die Funktion liefert bewusst nur den **Suffix**, nicht das ganze
Label inklusive Kanalnamen (`"E-Mail (a@b.de)"`) — das lässt den Kanalnamen als literalen Text im
Template stehen (`E-Mail{contactLabel.email}`) und minimiert den Diff gegenüber dem bisherigen
`E-Mail{profile?.mail_to ? ` (${profile.mail_to})` : ''}` auf einen reinen Feldzugriff, ohne die
Template-Struktur umzubauen.

```ts
export interface ChannelContactLabels {
  email: string;
  telegram: string;
  sms: string;
}

export function channelContactLabel(
  profile: ConnectionProfile | null | undefined
): ChannelContactLabels {
  const p = profile ?? {};
  return {
    email: p.mail_to ? ` (${p.mail_to})` : '',
    telegram: p.telegram_chat_id ? ` (${p.telegram_chat_id})` : '',
    sms: p.sms_to ? ` (${p.sms_to})` : ''
  };
}
```

**Einbindung `VTBriefingChannels.svelte`:**
- Neu: `let contactLabel = $derived(channelContactLabel(profile));` (neben der bestehenden
  `connectionStatus`-Zeile 75).
- Zeile 108: `E-Mail{profile?.mail_to ? ... : ''}` → `E-Mail{contactLabel.email}`; analog Zeile 130
  (Telegram) und 158 (SMS).
- Zeile 108: `disabled={!availableChannels.email}` → `disabled={connectionStatus.email.tone !== 'good'}`.
- `availableChannels`-Objekt (Zeilen 67–71) verliert den `email`-Eintrag; `telegram`/`sms` bleiben
  unverändert, ebenso deren `disabled`-Bindungen (Zeilen 128,157) und die Hinweis-Blöcke
  (`!availableChannels.email` an Zeile 117 wird durch die neue Bedingung ersetzt, damit der
  „E-Mail-Adresse fehlt"-Hinweis weiterhin nur bei fehlender Adresse erscheint, nicht bei jeder
  unbestätigten — siehe AC-4).

**Einbindung `EditReportConfigSection.svelte`:**
- Neuer Import: `import { channelConnectionStatus, type ConnectionProfile } from
  '../shared/versand-tab/channelConnectionStatus';` und `import { channelContactLabel } from
  '../shared/versand-tab/channelContactLabel';`.
- `Profile`-Interface (Zeilen 82–87) bekommt `email_verified?: boolean;` (Backend liefert es
  bereits mit, siehe Dependencies).
- Neu: `let connectionStatus = $derived(channelConnectionStatus(profile));` und
  `let contactLabel = $derived(channelContactLabel(profile));` (analog `VTBriefingChannels.svelte:75`
  und der neuen Zeile oben).
- Zeilen 296,314,332: Label-Ternaries → `contactLabel.email`/`.telegram`/`.sms`.
- Zeile 294: `disabled={!availableChannels.email}` → `disabled={connectionStatus.email.tone !== 'good'}`.
- Neues Dot/Label-Markup je Kanal-Block (E-Mail, Telegram, SMS), 1:1 nach dem Muster
  `VTBriefingChannels.svelte:112–115,133–136,161–164` (`Dot`-Atom + Mono-Label-Span, Testids
  `channel-status-email`/`channel-status-telegram`/`channel-status-sms`); dazu der Import von `Dot`
  aus `$lib/components/atoms` (`VTBriefingChannels.svelte:14`).
- `availableChannels`-Block (Zeilen 90–94) verliert den `email`-Eintrag, analog oben.

## Expected Behavior

- **Input:** Nutzer öffnet den Kanäle-Bereich im Versand-Reiter (`VTBriefingChannels`) oder im
  Trip-Editor (`EditReportConfigSection`).
- **Output:** Beide zeigen dieselbe Kontakt-Beschriftung aus derselben Quelle; der Trip-Editor
  zeigt zusätzlich Dot+Label-Verbindungsstatus wie der Versand-Reiter. Die E-Mail-Checkbox ist in
  beiden nur ankreuzbar, wenn die Adresse hinterlegt **und** bestätigt ist; Telegram/SMS bleiben bei
  „hinterlegt" wie bisher.
- **Side effects:** keine neuen Netzwerk-Aufrufe (beide Komponenten laden `/api/auth/profile`
  bereits); kein Server-/Persistenz-Verhalten geändert — reine Anzeige- und Sperr-Logik.

## Acceptance Criteria

- **AC-1:** Given ein `ConnectionProfile` mit beliebiger Kombination aus vorhandenem/fehlendem
  `mail_to`, `telegram_chat_id`, `sms_to` / When `channelContactLabel(profile)` aufgerufen wird /
  Then liefert es je Kanal exakt den Suffix `" (<Kontakt>)"` bei vorhandenem Kontakt und `""` bei
  fehlendem — für alle drei Kanäle unabhängig voneinander.
  - Test: `channelContactLabel.test.ts`, mindestens 6 Fälle (jeder der drei Kanäle je einmal
    vorhanden, einmal fehlend), plus ein Fall mit `profile = null`/`undefined` → alle drei Felder
    `""`.

- **AC-2:** Given `VTBriefingChannels` wird mit einem Profil gerendert, dessen `mail_to` auf eine
  bestimmte Adresse gesetzt ist / When die Komponente rendert / Then enthält der sichtbare
  Checkbox-Beschriftungstext genau diese Adresse im Format `channelContactLabel()` — nicht nur der
  Quellcode enthält den Aufruf.
  - Test: Component-/DOM-Render-Test (Svelte-Testing-Library oder Playwright gegen Staging), der den
    tatsächlich gerenderten Text der `channel-email`-Checkbox liest und mit dem Wert vergleicht, den
    `channelContactLabel()` für dasselbe Profil zurückgibt. Kein Quelltext-Scan auf den
    Import-/Aufruf-Namen.

- **AC-3:** Given `EditReportConfigSection` wird mit demselben Profil wie in AC-2 gerendert / When
  die Komponente rendert / Then zeigt sie exakt dieselbe Kontakt-Beschriftung wie
  `VTBriefingChannels` für dasselbe Profil — beide Komponenten weichen für dieselbe Eingabe nie
  voneinander ab.
  - Test: Component-Render-Test analog AC-2, zusätzlich ein direkter Vergleich der beiden
    gerenderten Texte (bzw. der beiden `channelContactLabel()`-Rückgabewerte) für identische
    Profil-Fixtures.

- **AC-4:** Given ein Profil ohne `mail_to`, ein Profil mit `mail_to` aber `email_verified: false`
  und ein Profil mit `mail_to` und `email_verified: true` / When die E-Mail-Checkbox in
  `VTBriefingChannels` **und** in `EditReportConfigSection` jeweils für alle drei Profile gerendert
  wird / Then ist die Checkbox nur im dritten Fall (`tone === 'good'`) anklickbar (`disabled=false`);
  in den ersten beiden Fällen ist sie `disabled=true` — in beiden Komponenten symmetrisch, nicht nur
  in einer.
  - Test: Component-Render-Test, der das `disabled`-Attribut der jeweiligen Checkbox-DOM-Node für
    alle drei Profil-Fixtures × beide Komponenten prüft (6 Kombinationen).

- **AC-5:** Given ein Profil ohne `telegram_chat_id`/`sms_to` bzw. mit gesetztem
  `telegram_chat_id`/`sms_to` (inkl. `sms_allowed: false`) / When die Telegram- bzw. SMS-Checkbox in
  beiden Komponenten gerendert wird / Then ist ihr `disabled`-Zustand exakt derselbe wie vor dieser
  Änderung (`!!profile?.telegram_chat_id` bzw. `!!profile?.sms_to && sms_allowed !== false`) — keine
  Verschärfung, keine Lockerung.
  - Test: Component-Render-Test mit denselben Profil-Fixtures wie vor der Änderung (Regressionstest);
    Behauptung ist Gleichheit zum dokumentierten Vorverhalten, nicht nur „funktioniert irgendwie".

- **AC-6:** Given ein Profil mit gesetztem `mail_to`, `telegram_chat_id` und `sms_to` / When
  `EditReportConfigSection` rendert / Then erscheinen für alle drei Kanäle Dot+Label-Elemente mit
  den Testids `channel-status-email`, `channel-status-telegram`, `channel-status-sms` — analog zu
  `VTBriefingChannels` — wo vor dieser Änderung keines dieser Elemente existierte.
  - Test: Component-Render-Test, der Existenz und Text der drei neuen Testid-Elemente in
    `EditReportConfigSection` prüft (heute: Element nicht vorhanden → Test muss vor der
    Implementierung rot sein).

- **AC-7:** Given `sendTargetLabel.ts` und ihre bestehende Testsuite / When diese Spec umgesetzt
  ist / Then ist die Datei `sendTargetLabel.ts` byteidentisch zum Stand vor dieser Spec, und
  `sendTargetLabel.test.ts` läuft unverändert grün — die Kontakt-Beschriftung der Checkboxen und der
  Ziel-Satz im Bestätigungsdialog bleiben getrennte, unabhängige Bausteine.
  - Test: `git diff` auf `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts` ist
    leer nach Abschluss der Implementierung; `node --test` auf `sendTargetLabel.test.ts` bleibt
    grün ohne Anpassung.

- **AC-8:** Given `frontend/e2e/versand-tab-vergleich.spec.ts` AC-7 setzt eine unbestätigte
  Test-E-Mail-Adresse / When die verschärfte E-Mail-Sperre aktiv ist / Then kann der Test die
  Checkbox weiterhin gezielt abwählen (`{ force: true }`) und die Leerzustand-Anzeige
  (`briefings-channel-empty`) bleibt wie zuvor erreichbar und sichtbar.
  - Test: Der bestehende Playwright-Test `AC-7: alle Kanäle aus zeigt "Kein Kanal aktiv" statt
    Zeitplan-Karten` läuft nach der Anpassung grün, ohne die geprüfte Aussage (Leerzustand
    erscheint) zu verändern.

## Was sich NICHT ändert

- `sendTargetLabel()` (#1471) bleibt unverändert — sie liefert einen ganzen Satz für den
  Bestätigungsdialog des Ortsvergleichs, keine Checkbox-Beschriftung, und ruft bereits intern
  `channelConnectionStatus()` auf; es gibt keine Überschneidung mit dieser Spec.
- Der `availableChannels`-Eintrag für Telegram und SMS bleibt in beiden Komponenten unverändert
  (`!!profile?.telegram_chat_id` bzw. `!!profile?.sms_to && sms_allowed !== false`) — nur der
  E-Mail-Eintrag entfällt zugunsten von `channelConnectionStatus().email.tone`.
- Der Ladepfad `GET /api/auth/profile` (identischer `onMount`/`fetch`-Code in beiden Komponenten)
  wird nicht konsolidiert — im Kontext-Dokument als mögliche vierte Duplikat-Klasse benannt, aber
  nicht im Issue verlangt und daher nicht Teil dieses Scopes.

## Known Limitations

- Die Erweiterung des Pendant-Gates (#1481 B) um „geteilter Ordner, aber nur ein Aufrufer" (Punkt 3
  des ursprünglichen Issue-Vorschlags) ist **nicht** Teil dieser Spec — das ist eine
  Wächter-Änderung, kein Produktfehler, und geht als Sammel-Eintrag an #1199 (PO-Entscheidung im
  Intake-Dialog vom 2026-08-05).
- Ein serverseitiges Tier-Downgrade (`sms_allowed`) zwischen dem Laden des Profils und einer
  tatsächlichen Interaktion wird wie bisher nicht neu geprüft (bestehendes Verhalten,
  `channelConnectionStatus()` unverändert für SMS).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Konsolidierung einer Anzeige-Ableitung nach etabliertem Muster
  (`channelConnectionStatus`, `sendTargetLabel`) plus eine einzelne, klar begründete
  Verhaltensänderung (E-Mail-Checkbox-Sperre bei unbestätigter Adresse) — keine neue
  Entscheidungsfläche (Kanal, Provider, Datenmodell, Auth) betroffen. Analog zur Einschätzung in
  `docs/specs/modules/fix_1471_sende_dialog_ziel.md`.

## Changelog

- 2026-08-05: Initial spec created
- 2026-08-05: Affected-Files-Tabelle um `channel_checkbox_dedupe_render.test.ts` ergänzt (war bereits durch AC-2/3/4/5/6 verlangt, fehlte aber in der Tabelle — Scope-Check bei `/60-validate` aufgedeckt)
