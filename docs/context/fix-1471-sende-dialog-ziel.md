# Context: fix-1471-sende-dialog-ziel

Issue: [#1471](https://github.com/henemm/gregor_zwanzig/issues/1471) — Sende-Dialog im
Ortsvergleich sagt „An 0 Empfänger senden?", obwohl die Mail zugestellt wird.
Labels: `bug`, `area:compare`, `session:unity`. Track: **Standard** (Intake-Score 2).

## Request Summary

Der Bestätigungsdialog vor dem Sofort-Versand eines Ortsvergleichs-Briefings nennt eine
Empfängerzahl, die dauerhaft 0 ist. Er soll stattdessen das **tatsächliche Ziel** nennen — die
im Konto hinterlegte Adresse — und den Versand nicht anbieten, wenn keine hinterlegt ist.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/routes/compare/+page.svelte:337-344` | Der Dialog. Zeile 339: `description={'An ' + (sendTarget?.empfaenger?.length ?? 0) + ' Empfänger senden?'}` |
| `frontend/src/routes/compare/+page.server.ts` | Lädt heute **nur** `presets` — das Konto-Profil müsste hier dazukommen |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts:29-50` | **Vorhandener geteilter Baustein**: `channelConnectionStatus(profile)` beantwortet „ist der Kanal verbunden?" für E-Mail/Telegram/SMS, inkl. `email_verified` |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte:109` | Zeigt bereits `E-Mail{profile?.mail_to ? ` (${profile.mail_to})` : ''}` — die Formulierung, die der Dialog übernehmen soll |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:151` | `channelCountLabel()` liest dieselbe inerte Länge, ist **nirgends mehr eingebunden** (toter Code, laut Issue mitnehmen oder löschen) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte:296` | Zweite Stelle mit derselben Formulierung — Hinweis auf einen möglichen geteilten Baustein |

## Ursache (aus dem Issue, verifiziert)

`preset.empfaenger` ist seit **#1452** (`28cefe7f`) strukturell **inert** — der Versand geht
ausschließlich an die Konto-Settings (`Settings().with_user_profile(user_id)`), analog zum
Trip-Muster. Das Feld bleibt leer, der Zähler dauerhaft 0. Die Cockpit-Kanal-Anzeige las dasselbe
inerte Feld und wurde mit #1452 mitbehoben; **diese Stelle wurde übersehen**.

## Existing Patterns

- **Kanal-Status kommt aus einem Baustein, nicht aus einer Zählung.**
  `channelConnectionStatus()` liefert je Kanal `{tone, label}` und unterscheidet für E-Mail
  **drei** Zustände: keine Adresse (`nicht verbunden`), Adresse ohne Bestätigung
  (`nicht bestätigt`), bestätigt (`bestätigt`).
- **Adress-Anzeige** ist an zwei Stellen wortgleich formuliert (`VTBriefingChannels.svelte:109`,
  `EditReportConfigSection.svelte:296`).

## Dependencies

- **Upstream:** Konto-Profil (`profile.mail_to`, `email_verified`) — heute in der Vergleichs-Liste
  nicht geladen (`+page.svelte:31` nutzt nur `data.presets`).
- **Downstream:** nur der Dialog; der Versand-Pfad selbst (`confirmSend`, ab `+page.svelte:151`)
  bleibt unberührt.

## Trip/Compare-Teilung (Pflichtprüfung, CLAUDE.md-Invariante)

**Gemessen: Es gibt heute kein Trip-Pendant.** „Briefing jetzt senden" aus der Liste heraus
existiert **nur** im Ortsvergleich (`grep` über `frontend/src/routes` → einziger Treffer
`compare/+page.svelte`). Der Fix erzeugt damit keine Doppelung. **Aber:** Entsteht der
Sofort-Versand später auch beim Trip, muss die Ziel-Formulierung ein geteilter Baustein sein —
deshalb sollte die Lösung schon jetzt als wiederverwendbare Funktion entstehen, nicht als
Inline-Ausdruck im Dialog.

## Risks & Considerations

1. **Offene Produktfrage für die Spec:** Was zeigt der Dialog bei hinterlegter, aber **nicht
   bestätigter** Adresse? Das Issue beschreibt nur „gar keine Adresse". `channelConnectionStatus`
   kennt den Zwischenzustand bereits — die Antwort muss der PO geben.
2. **„Versand wird nicht angeboten" ist eine Verhaltensänderung**, nicht nur ein Text: Der
   Menüeintrag bzw. der Bestätigen-Knopf muss dann inaktiv sein. Betrifft `+page.svelte:112,124`.
3. **Nur E-Mail betrachten wäre zu kurz:** Ein Ortsvergleich kann auch Telegram/SMS senden
   (`VersandTab`). Der Dialog sollte das tatsächliche Ziel über **alle aktiven Kanäle** nennen,
   sonst entsteht dieselbe Halbwahrheit in neuer Form.
4. **Toter Code:** `channelCountLabel()` mitnehmen — sonst bleibt eine zweite Stelle stehen, die
   dieselbe falsche Zählung wiederbeleben könnte.
5. **Mandantentrennung:** Das Profil muss aus dem Auth-Kontext des angemeldeten Nutzers kommen
   (`+page.server.ts`), niemals aus einem Default.

---

# Analysis

**Type:** Bug (nutzersichtbare Falschaussage an einer Entscheidungsstelle).

## Der Versandweg — gemessen

`confirmSend()` (`compare/+page.svelte:157`) → `POST /api/compare/presets/{id}/send` → Go-Proxy
(`internal/handler/compare_preset.go:629-666`, User-ID aus `middleware.UserIDFromContext`) →
`api/routers/scheduler.py:210-221` → `send_one_compare_preset()`
(`src/services/scheduler_dispatch_service.py:292ff`).

**Empfänger:** `default_to = settings.mail_to` (Konto-Settings), `empfaenger = [default_to]`
(`scheduler_dispatch_service.py:335-341`). `preset.empfaenger` wird **nicht** gelesen.

**Der Versand ist mehrkanalig** (`compare_alert_channels.py:26-33`,
`_effective_compare_channels()` in `scheduler_dispatch_service.py:277-289`):

| Kanal | aktiv wenn |
|---|---|
| E-Mail | **immer** |
| Telegram | `preset.send_telegram` **und** `settings.can_send_telegram()` |
| SMS | `preset.send_sms` **und** `settings.can_send_sms()` **und** `sms_allowed(user_id)` (Tier-Gate) |

Die **Auswahl** kommt aus dem Vergleich, die **Zieladressen** durchweg aus den Konto-Settings
(`notification_service.py:752-838`: `TelegramOutput(self._settings)` / `SMSOutput(...)`).
⇒ Ein Dialog, der nur die Mailadresse nennt, wäre wieder nur die halbe Wahrheit.

## Drei Zustände, nicht zwei

Das Issue kennt „Adresse da" und „keine Adresse". Gemessen gibt es einen **dritten**:

| Zustand | Was tatsächlich passiert | Beleg |
|---|---|---|
| Adresse hinterlegt **und** bestätigt | Versand läuft | — |
| **Keine** Adresse | Server wirft `ValueError` („kein Empfaenger — mail_to fehlt") | `scheduler_dispatch_service.py:336-340` |
| Adresse hinterlegt, **nicht bestätigt** | **Empfängerschutz blockt die Zustellung** — die Adresse steht nicht in der Allowlist (`_load_resend_allowlist` sammelt nur Profile mit gesetztem `email_verified_at`), der Guard verweigert den Versand | `email.py:239-285`, Guard `:440-447` (`return True` = blockieren) |

Der dritte Zustand ist der heimtückische: Alles sieht eingerichtet aus, es wird aber nichts
zugestellt. Ein Dialog, der hier „Geht an a@b.de" sagt, wiederholt den Fehler von #1471 mit
umgekehrtem Vorzeichen.

## Wiederverwendung (DRY-Pflichtprüfung)

- **Profil laden:** etabliertes Muster, **3×** vorhanden, eines davon direkter Nachbar im selben
  Routenbaum: `compare/new/+page.server.ts:9-26`, `trips/new/+page.server.ts:11-20`,
  `account/+page.server.ts:16,20`. Cookie `gz_session` durchreichen → `GET /api/auth/profile`;
  User-ID leitet der Go-Handler aus der Session ab (`internal/handler/auth.go:512-526`), das
  Frontend baut **keinen** `user_id`-Parameter. Fail-soft: `profile = null` bei Fehler.
- **Ziel-Text („geht an X"): existiert NICHT.** Die Formulierung `E-Mail (adresse)` ist an
  **zwei** Stellen für je **drei** Kanäle dupliziert (`VTBriefingChannels.svelte:109,126,158` und
  `EditReportConfigSection.svelte:296,311,332`) — sechs Kopien derselben Aussage.
- **`channelConnectionStatus()`** (`shared/versand-tab/channelConnectionStatus.ts:29-50`) liefert
  nur Ton + Kurzlabel (`bestätigt`/`nicht bestätigt`/`nicht verbunden`), **nicht** die Adresse.
  Benutzt an **einer** Stelle (`VTBriefingChannels.svelte:17`); `EditReportConfigSection` baut
  dieselbe Information nochmals inline (`:93`).

⇒ Der Fix soll den Ziel-Text als **geteilte Funktion** anlegen (nicht als Inline-Ausdruck im
Dialog) — sie ist der fehlende Baustein, den heute sechs Kopien ersetzen. Trip-Pendant existiert
nicht (gemessen), die Funktion ist aber der Ort, an dem ein künftiger Trip-Sofortversand andockt.

## Testlage

- **Kein Test prüft den Dialogtext.** `issue_627_send_action.test.ts` testet nur das Menü-Label;
  `frontend/e2e/bug-626-compare-menu-actions.spec.ts:320-355` prüft nur die Sichtbarkeit des
  Menüpunkts, klickt ihn nicht.
- Kein Frontend-Test deckt den Versandaufruf aus der Liste ab.
- `channelCountLabel()` ist **bestätigt tot** (nachgemessen): kein `.svelte` importiert sie;
  Treffer nur im eigenen Test `channelCountLabel.test.ts`, in einem Negativtest
  (`compare_mobile_shared_hub.test.ts:90-94`, prüft ihre Abwesenheit) und in einem Kommentar.
  Nachfolgerin ist `channelNamesLabel()`. ⇒ Funktion **und** ihr Test entfallen.

## Scope Assessment

| | |
|---|---|
| Dateien | `compare/+page.server.ts` (Profil laden) · `compare/+page.svelte` (Dialog + Sperre) · neue geteilte Funktion + Test · `compare/subscriptionHelpers.ts` (tote Funktion raus) · `channelCountLabel.test.ts` (löschen) |
| Geschätzt | ~80–120 LoC |
| Risiko | MEDIUM — Anzeige vor dem Versand; die Sperre bei fehlender/unbestätigter Adresse ist eine Verhaltensänderung |

## Offene Frage für die AC-Freigabe

Bei **unbestätigter** Adresse: Versand sperren (Empfehlung — es wird nachweislich nichts
zugestellt) oder anbieten und scheitern lassen? Wird mit den ACs vorgelegt.
