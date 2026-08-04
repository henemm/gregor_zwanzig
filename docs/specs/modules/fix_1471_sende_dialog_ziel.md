---
entity_id: fix_1471_sende_dialog_ziel
type: bugfix
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [compare, versand, frontend]
---

# Sende-Dialog nennt das tatsächliche Versandziel (#1471)

## Approval

- [ ] Approved

## Purpose

Der Bestätigungsdialog vor dem Sofort-Versand eines Ortsvergleichs-Briefings
(`frontend/src/routes/compare/+page.svelte:337-344`) sagt heute „An 0 Empfänger senden?", weil er
`preset.empfaenger` zählt — ein seit #1452 strukturell inertes, dauerhaft leeres Feld. Diese Spec
ersetzt die Falschaussage durch eine Anzeige des **tatsächlichen** Ziels (Konto-Adresse(n) über
alle aktiven Kanäle) und sperrt den Versand, wenn nachweislich nichts zugestellt würde.

## Source

- **File:** `frontend/src/routes/compare/+page.svelte`
- **Identifier:** `ConfirmDialog` (Send-Variante, `sendTarget`-State, `confirmSend()`)

## Estimated Scope

- **LoC:** ~80–120
- **Files:** 6 (siehe unten)
- **Effort:** medium

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/routes/compare/+page.server.ts` | MODIFY | Lädt zusätzlich `GET /api/auth/profile` (Cookie-Weiterreichung, Muster aus `compare/new/+page.server.ts:9-26`), fail-soft `profile = null` |
| `frontend/src/routes/compare/+page.svelte` | MODIFY | Dialog-`description` nutzt neue Ziel-Funktion statt `sendTarget?.empfaenger?.length`; Versand-Auslöser (Menüpunkt `send`, Kachel-Primäraktion `compareRowPrimary`, Dialog-Bestätigen-Button) werden deaktiviert, wenn kein Ziel zustellbar ist |
| `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts` | CREATE | Neue geteilte Funktion: aus `ConnectionProfile` + aktivierten Kanälen (`send_telegram`, `send_sms`) einen Ziel-Text plus Zustellbarkeits-Flag ableiten |
| `frontend/src/lib/components/shared/versand-tab/__tests__/sendTargetLabel.test.ts` | CREATE | node:test, reine Verhaltenstests (kein Mock, kein DOM) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | MODIFY | Tote Funktion `channelCountLabel()` entfernen (Zeile 151, nachgemessen ungenutzt) |
| `frontend/src/lib/components/compare/channelCountLabel.test.ts` | DELETE | Test der entfernten Funktion |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `channelConnectionStatus()` (`shared/versand-tab/channelConnectionStatus.ts:29-50`) | function | Liefert bereits die Drei-Zustands-Logik für E-Mail (keine Adresse / nicht bestätigt / bestätigt) und den Verbunden-Status für Telegram/SMS — Basis für die neue Funktion, nicht neu erfinden |
| `GET /api/auth/profile` | endpoint | Liefert `mail_to`, `email_verified`, `telegram_chat_id`, `sms_to`, `sms_allowed` des angemeldeten Nutzers (User-ID aus Session, kein Client-Parameter) |
| `ComparePreset.send_telegram` / `ComparePreset.send_sms` (`frontend/src/lib/types.ts:610-611`) | field | Bestimmen, ob der jeweilige Zusatzkanal für **diesen** Vergleich aktiviert ist |

## Implementation Details

**Neue Funktion `sendTargetLabel(profile, preset)`** (Ort: `shared/versand-tab/`, da bereits Heimat
von `channelConnectionStatus`, die dieselbe Datenbasis konsumiert):

```
Eingabe: ConnectionProfile (mail_to, email_verified, telegram_chat_id, sms_to, sms_allowed),
         { send_telegram?: boolean, send_sms?: boolean }
Ausgabe: { text: string, deliverable: boolean }
```

Ableitungslogik (rein, keine Netz-/DOM-Zugriffe, analog `channelConnectionStatus`):

1. E-Mail ist immer Teil des Versands (siehe Analyse: „E-Mail immer aktiv").
   - Keine Adresse hinterlegt → `deliverable = false`, Text erklärt das Fehlen.
   - Adresse hinterlegt, aber `email_verified` falsy → `deliverable = false`, Text erklärt, dass
     nichts zugestellt wird (Empfängerschutz).
   - Adresse hinterlegt und bestätigt → E-Mail-Adresse erscheint im Ziel-Text.
2. Telegram erscheint im Ziel-Text nur, wenn **beides** zutrifft: `preset.send_telegram === true`
   **und** `profile.telegram_chat_id` gesetzt. Ist der Kanal im Vergleich aktiviert, aber im Konto
   nicht hinterlegt, erscheint er **nicht** — sonst entsteht dieselbe Falschaussage in neuer Form
   (Analyse, Risk 3).
3. SMS analog: nur wenn `preset.send_sms === true` **und** `profile.sms_to` gesetzt **und**
   `profile.sms_allowed !== false`.
4. Mehrere Ziele werden mit " · " verbunden (Konvention aus `channelNamesLabel()`,
   `subscriptionHelpers.ts`).

**Dialog** (`compare/+page.svelte`): `description` ruft `sendTargetLabel(profile, sendTarget)`
auf; `profile` kommt aus `data.profile` (Server-Load). Ist `deliverable === false`, wird zusätzlich
der Bestätigen-Button deaktiviert — **`ConfirmDialog` hat dafür bereits eine `disabled`-Prop**
(`molecules/ConfirmDialog.svelte:20,36,60`, nachgemessen), es ist **keine** API-Erweiterung nötig —
und der Text erklärt den Grund.

**Auslöser sperren:** `compareRowPrimary()` (Zeile 109-114) und der Menüpunkt `send`
(`onCompareAction`, Zeile 116-125) öffnen den Dialog weiterhin — die Sperre sitzt **im Dialog**
(Button deaktiviert), nicht am Auslöser, weil der Nutzer sonst gar nicht erfährt, *warum* nichts
passiert. Diese Entscheidung ist Teil der Spec-Freigabe (siehe AC-3/AC-4).

## Expected Behavior

- **Input:** Nutzer klickt „Briefing senden" (Menü oder Kachel-Primäraktion) auf einen aktiven
  Ortsvergleich.
- **Output:** Bestätigungsdialog zeigt das tatsächliche Versandziel (E-Mail-Adresse plus ggf.
  Telegram/SMS, wenn im Vergleich aktiviert und im Konto hinterlegt) oder — wenn nichts zustellbar
  wäre — eine verständliche Erklärung, und der Bestätigen-Button ist dann deaktiviert.
- **Side effects:** keine neuen; der eigentliche Versandpfad (`confirmSend`, Endpoint, Serverlogik)
  ist unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat eine bestätigte E-Mail-Adresse im Konto hinterlegt / When er auf
  einen aktiven Ortsvergleich „Briefing senden" klickt / Then zeigt der Bestätigungsdialog diese
  E-Mail-Adresse im Text, und die Zeichenfolge „0 Empfänger" kommt im gerenderten Dialog nicht mehr
  vor.
  - Test: `sendTargetLabel()`-Verhaltenstest mit Profil `{ mail_to: 'a@b.de', email_verified: true }`
    und Preset ohne Zusatzkanäle → `text` enthält `a@b.de`, `deliverable === true`.

- **AC-2:** Given der Vergleich hat Telegram und/oder SMS aktiviert (`send_telegram`/`send_sms`)
  / When das Konto den jeweiligen Kanal **hinterlegt** hat / Then nennt der Dialog auch diesen
  Kanal; ist der Kanal im Vergleich aktiviert, aber im Konto **nicht** hinterlegt, nennt der Dialog
  ihn **nicht**.
  - Test: zwei Fälle in `sendTargetLabel.test.ts` — (a) `send_telegram: true` +
    `telegram_chat_id` gesetzt → Telegram im Text; (b) `send_telegram: true` ohne
    `telegram_chat_id` → Telegram fehlt im Text, nur E-Mail erscheint.

- **AC-3:** Given im Konto ist keine E-Mail-Adresse hinterlegt / When der Nutzer den Dialog öffnet
  / Then erklärt der Dialogtext das verständlich (kein Zahlenwert), und der
  Bestätigen-Button ist deaktiviert, sodass der Versand nicht auslösbar ist.
  - Test: `sendTargetLabel()` mit `mail_to` fehlend → `deliverable === false`, `text` erklärt das
    Fehlen; zusätzlich ein struktureller Test auf `+page.svelte`, dass der Dialog-Bestätigen-Button
    im nicht-zustellbaren Fall `disabled` ist (Svelte-Compiler-AST oder DOM-Prop-Check, kein
    reines String-Grep).

- **AC-4:** Given im Konto ist eine E-Mail-Adresse hinterlegt, aber **nicht bestätigt**
  (`email_verified` falsy) / When der Nutzer den Dialog öffnet / Then sagt der Dialog, dass nichts
  zugestellt wird (Empfängerschutz greift nachweislich, `email.py:239-285`), und der Versand ist
  nicht auslösbar. Begründung: Ein Knopf, der nichts bewirkt, wäre der Fehler aus #1471 mit
  umgekehrtem Vorzeichen.
  - Test: `sendTargetLabel()` mit `mail_to` gesetzt, `email_verified: false` →
    `deliverable === false`, Text unterscheidet sich sichtbar von AC-3 (nennt „nicht bestätigt",
    nicht „fehlt").

- **AC-5:** Given zwei verschiedene Nutzer A und B mit unterschiedlichen Konto-Adressen / When
  jeder für sich den Sende-Dialog eines eigenen Ortsvergleichs öffnet / Then zeigt der Dialog
  jeweils **nur** die eigene Konto-Adresse — nie die des anderen Nutzers, unabhängig von der
  Aufrufreihenfolge.
  - Test: Die exportierte `load()`-Funktion aus `compare/+page.server.ts` wird **direkt aufgerufen**
    — zweimal, mit je einem eigenen `cookies`-Objekt (verschiedene `gz_session`-Werte) und einem
    `fetch`-Double, das je nach durchgereichtem Cookie ein anderes Profil liefert. Behauptung:
    jeder Aufruf liefert genau das Profil seiner Session, und ein zweiter Aufruf verändert das
    Ergebnis des ersten nicht (kein geteilter Modul-Zustand).
  - ⚠️ **Kein Quelltext-Scan.** Das vorhandene `routes/page-server.bug395.test.ts` liest die Datei
    per `readFileSync` und prüft sie mit einer Regex — genau die von der Test-Politik verbotene
    Bauform (Dateiinhalt als Verhaltensnachweis) und zugleich die bekannte Falle „Muster trifft
    nichts ⇒ immer grün". Es ist **kein** Vorbild für diesen Test.

- **AC-6:** Given eine Konto-/Vergleichs-Konstellation, in der ein Kanal im Vergleich aktiviert,
  im Konto aber nicht hinterlegt ist / When der Ziel-Text des Dialogs und der Verbindungsstatus des
  Versand-Reiters für **dieselbe** Konstellation ermittelt werden / Then nennt der Dialog keinen
  Kanal, den der Versand-Reiter als „nicht verbunden" führt — die beiden Ansichten widersprechen
  sich in keiner Konstellation.
  - Test: Verhaltenstest über eine Tabelle von Profil-/Preset-Kombinationen (mindestens: alle
    Kanäle hinterlegt · Telegram aktiviert ohne `telegram_chat_id` · SMS aktiviert mit
    `sms_allowed: false` · nur E-Mail). Für jede Zeile werden `sendTargetLabel()` **und**
    `channelConnectionStatus()` mit demselben Profil aufgerufen; die Behauptung lautet: kein Kanal,
    dessen Status `nicht verbunden` ist, kommt im Ziel-Text vor.
  - ⚠️ Explizit **nicht** so prüfen: „beide enthalten dieselbe Adresse" — `channelConnectionStatus()`
    liefert nur Ton und Kurzlabel (`bestätigt`/`nicht verbunden`), **keine** Adresse
    (`channelConnectionStatus.ts:29-50`). Ein Adress-Vergleich wäre nicht durchführbar.

- **AC-7:** Given `channelCountLabel()` ist nachgemessen ungenutzt / When sie samt ihrem Test
  entfernt wird / Then bleibt die restliche Testsuite (insbesondere
  `compare_mobile_shared_hub.test.ts`, das ihre **Abwesenheit** prüft) grün.
  - Test: `node --test` auf `frontend/src/lib/components/compare/` nach der Entfernung — kein
    Import-Fehler, `compare_mobile_shared_hub.test.ts` bleibt grün.

## Was sich NICHT ändert

- Der Versandweg selbst bleibt unberührt: `confirmSend()` (`+page.svelte:150-163`), der Endpoint
  `POST /api/compare/presets/{id}/send`, der Go-Proxy sowie
  `scheduler_dispatch_service.py`/`compare_alert_channels.py` auf Serverseite.
- `preset.empfaenger` wird **nicht** wiederbelebt oder wieder befüllt — es bleibt das seit #1452
  inerte Legacy-Feld.
- Die Kanal-Auswahl-Logik im Versand-Reiter (`VTBriefingChannels`, `EditReportConfigSection`)
  ändert sich inhaltlich nicht; sie bekommt lediglich dieselbe Datenquelle wie der Dialog zur
  Verfügung (AC-6), ihre bestehenden sechs Formulierungen werden nicht umgeschrieben.

## Offene Grenzen

- Die sechs bestehenden Duplikate der Ziel-Formulierung in `VTBriefingChannels.svelte:109,126,158`
  und `EditReportConfigSection.svelte:296,311,332` werden in diesem Zug **nicht** saniert (Umfang
  bewusst auf den Dialog begrenzt). `sendTargetLabel()` ist aber der Ort, an dem sie bei
  künftiger Aufräumarbeit zusammenlaufen können.
- Ein Sofort-Versand aus der Trip-Liste existiert heute nicht (gemessen, einziger Treffer ist
  `compare/+page.svelte`) — die neue Funktion liegt deshalb bewusst im geteilten
  `shared/versand-tab/`-Ordner, damit ein künftiger Trip-Sofortversand dieselbe Quelle nutzen kann,
  ohne dass diese Spec das für den Trip-Fall bereits behauptet.

## Known Limitations

- Der Zwischenzustand „SMS-Tier-Gate" (`sms_allowed(user_id)` serverseitig,
  `settings.can_send_sms()`) wird im Dialog nur über `profile.sms_allowed` abgebildet, wie es
  `channelConnectionStatus()` bereits tut — ein serverseitiges Tier-Downgrade zwischen Laden des
  Dialogs und dem tatsächlichen Versand wird nicht neu geprüft (bestehendes Verhalten, nicht Teil
  dieses Fixes).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Korrektur einer Anzeige plus Ableitungsfunktion nach etabliertem
  Muster (`channelConnectionStatus`); keine neue Entscheidungsfläche (Kanal, Provider, Datenmodell,
  Auth) betroffen.

## Changelog

- 2026-08-04: Initial spec created
