# Context: feat-3440-test-schicken-menue

Workflow `feat-3440-test-schicken-menue` · Issue #3440 (S5a) · Scheibe S5 #2797 · Epic #2791 · gemessen gegen Worktree-HEAD `16df7864b` (27.11.2026)

## Request Summary

Der Kopf-Knopf „Test schicken ▾“ (`HubKopf.svelte`, testid `subscription-hub-send`) öffnet heute den Dialog „Briefing senden?“ (`SendConfirmDialog`). Soll (Mockup Fassung 4, ADR-0109 Punkt 6, PO-Entscheidungen K9–K12 in #2797): ein **Menü am Knopf**. Beim Trip oben das Segment „Morgen-Briefing · Abend-Briefing“, darunter je Kanal eine Zeile mit Ziel; gesperrte Kanäle ausgegraut mit „gesperrt: {Grund}“ und „Im Konto {verbinden|bestätigen|prüfen} →“; dann „Alle eingerichteten Kanäle“. Ein Klick öffnet, der zweite schickt. Rückmeldung „{Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“ in Trip und Orte gleich, auch mobil. Der Senden-Dialog entfällt im Hub. Abschnitt-Haken `data-abschnitt="test-menue"`. **Nicht im Umfang:** Eintrag „Test-Alarm“ (#3441, S5b), Kebab (K14/K15), Aktivieren-Pill (V16).

## Related Files

| Datei:Zeile | Rolle |
|---|---|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte:31-36,71,103-109` | Props `sendLabel`, `onSend`, `sendDisabled`, `sendMode`; Knopf `Btn variant="accent"` testid `subscription-hub-send` ruft nur `onSend()` (kein API-Aufruf im Baustein, #2278) |
| `HubKopf.svelte:110` | Snippet `meldungen` (Rückmeldung liegt heute in der Seite, nicht im Baustein) |
| `HubKopf.svelte:191-202,242-255` | `.hub-actions` flex-wrap; mobil ≤899 px 44-px-Tippflächen; Meldungen in jeder Breite |
| `frontend/src/lib/components/molecules/SendConfirmDialog.svelte:1-62` | Heutiger Dialog (ConfirmDialog + Segmented Morgen/Abend), testids `send-confirm-dialog/-yes/-cancel/-berichtsart-{morning,evening}` |
| `frontend/src/lib/components/molecules/sendConfirmModel.ts:10-39` | `Berichtsart = 'morning'|'evening'`, Morgen/Abend nur bei `kind==='trip'`, Sperre aus `sendTargetLabel` |
| `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts:61-97` | Heutige Ziel-/Sperrlogik „Geht an E-Mail (x) · Telegram …“; ohne Profil / ohne `mail_to` / E-Mail unbestätigt ⇒ gesperrt |
| `frontend/src/routes/trips/[id]/+page.svelte:12,142-146` | Import + State `sendDialogOpen/sendLoading/sendStatus/sendMessage` |
| `trips/[id]/+page.svelte:274-293` | `handleSendConfirm(berichtsart)` → `sendSubscription('trip', id, {reportType})`, Meldung 4 s |
| `trips/[id]/+page.svelte:317-331` | `sendLabel` (Wird gesendet…/Test schicken ▾), `onSend` öffnet Dialog, `sendDisabled` bei archived/draft; Meldungen testid `test-briefing-success` („Briefing gesendet!“) / `test-briefing-error` |
| `trips/[id]/+page.svelte:380-388` | `<SendConfirmDialog kind="trip" profile={data.profile} subscription={trip}>` |
| `frontend/src/routes/compare/[id]/+page.svelte:12,234,247-265` | State + `handleTestSend()` → `sendSubscription('vergleich', id)`; Meldung `vergleich.hub.test_gesendet` (ohne testid, bleibt stehen, kein Timer) |
| `compare/[id]/+page.svelte:385-412` | HubKopf: `sendMode='setup'` im Entwurf, `onSend` öffnet Dialog, `sendDisabled` bei archived; Meldung `<span>` ohne testid |
| `compare/[id]/+page.svelte:446-454` | `<SendConfirmDialog kind="vergleich" …>` |
| `routes/trips/+page.svelte:11,301` · `routes/compare/+page.svelte:14,339` | **Listen** nutzen SendConfirmDialog ebenfalls (nicht Teil des Hub-Umbaus) |
| `routes/trips/[id]/+page.server.ts:27,48` · `routes/compare/[id]/+page.server.ts:21,38` | `profile` (GET /api/auth/profile über `loadProfile`) liegt in `data.profile` |
| `frontend/src/lib/components/shared/subscriptionExec.ts:93-104` | `sendSubscription(kind,id,{reportType})` → `sendBriefing('route'|'vergleich')`; **kein Kanal-Parameter** |
| `frontend/src/lib/utils/sendOutcome.ts:19-33,94-154` | Klassifikation ok/already_running/unclear/rejected/failed + Texte `fehler.versand.*`; `briefingSendUrl` baut nur `kind` + `report_type`; In-Flight-Schlüssel `trip:<id>`/`compare:<id>` |
| `internal/router/router.go:397` | `POST /api/briefings/{id}/send` (Mengenbremse `bremsen.Versand`) |
| `internal/handler/briefing_send.go:36-54` | Go reicht **nur** `kind` und (bei route) `report_type` weiter, alle anderen Query-Parameter fallen weg |
| `internal/handler/send_proxy.go:25-54` | `forwardSend`: `user_id` aus Auth-Kontext injiziert, Client-`user_id` verworfen |
| `api/routers/briefings_send.py:56-87,90-118,140-151` | Python-Endpunkt; Trip → `send_test_report_outcome(trip, report_type)`; Vergleich → `send_compare_preset(user_id, id)`; Antwort `{status, kind, id, sent, report_type?, fehlende_orte?}` – **keine Kanal-Liste** |
| `src/services/trip_report_scheduler.py:1445-1476` | `send_test_report_outcome` (Test-Fallback, [TEST]-Präfix, Lock) – **ohne** `restrict_to_channel` |
| `trip_report_scheduler.py:1478-1532,1594,1643-1650,1923` | `send_on_demand_report(..., restrict_to_channel=)` + internes Durchreichen bis `_resolve_channel_flags` (#2126) |
| `src/services/scheduler_dispatch_service.py:1102-1170` | `send_compare_preset(..., restrict_to_channel=)` existiert (#2282), Web-Handversand ruft es ohne |
| `scheduler_dispatch_service.py:854-866` | restrict ⇒ `resolve_restricted_channel_flags`; gesperrt ⇒ `channels_unreachable` |
| `src/services/user_tier.py:112-125` | `resolve_restricted_channel_flags`: Kanal aktiv **auch wenn im Abo aus**, Tarif-Gate bleibt (SMS/Premium) |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts:30-41,111-139,177-227` | `KanalStatus {verbunden, ziel, grund, kontoLink{verb,text}}`, `adresseGekuerzt`, `nummerGekuerzt` („+49 171 …“), `kanalStatus(profil)` = Sperrlogik je Kanal (#3202) |
| `zustellungModell.ts:255-300` | `standAusTrip/standAusPreset` → `briefing: Record<KanalId,bool>` (im Abo eingeschaltete Kanäle) |
| `frontend/src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte:92-93` | Konto-Link `Btn href="/account" variant="link"` (Muster für „Im Konto … →“) |
| `frontend/src/lib/components/molecules/SubscriptionKebab.svelte:6,23-74` | bits-ui `DropdownMenu` (Desktop) / 44-px-Knopf → Sheet (mobil) |
| `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte:5,30` | Mobil-Muster `Sheet snap="half"` |
| `frontend/src/lib/components/atoms/Segmented.svelte` | Segment-Baustein (heute im Dialog `rolle="radio"`) |
| `frontend/src/lib/components/organisms/ListActionsMenu.svelte` | zweites Menü-Muster (Portal, role=menu) für Listen |

## Existing Patterns

- **Baustein ruft keine API** (HubKopf, SendConfirmDialog, Kebab): Seite hält Laufzustand und ruft `sendSubscription`; neues Menü sollte gleich gebaut sein (emittiert `{kanal, berichtsart}`).
- **Sperrlogik nie neu ableiten:** `sendTargetLabel` delegiert an `channelConnectionStatus`/`premiumSmsChannelState`; `zustellungModell.kanalStatus` ist die neuere Fassung mit Grund + Konto-Verb + gekürztem Ziel (#3202). Kandidat für das Menü: `kanalStatus(data.profile)` + `standAus*().briefing`.
- **In-Flight-Schutz** je Abo (`trip:<id>`/`compare:<id>`), 409 `already_running`; Python-Lock je (Nutzer, Trip, report_type) bzw. (compare, Nutzer, Preset).
- **Desktop Dropdown / mobil Sheet** (Kebab) mit `mobil`-Flag aus `matchMedia('(max-width: 899px)')` in beiden Seiten.
- **Texte über Katalog** (`$t`/`tr`), Kanalnamen sind Eigennamen, aber als Schlüssel `zustellung.kanal.*` vorhanden.

## Dependencies (Upstream)

- Profil: `GET /api/auth/profile` (Go `profileResponse`, `internal/handler/auth.go:~1080`) – Felder `mail_to, email_verified, telegram_chat_id, sms_to, sms_verified, pending_sms_to, sms_allowed, premium_sms_*`. **Kein Telegram-Name**, keine Empfängerzahl.
- Versand: Go `BriefingSendHandler` → Python `send_briefing` → `TripReportSchedulerService.send_test_report_outcome` bzw. `send_compare_preset` (on_demand=True) → Notification/Transporte.
- Fehlervokabular `src/services/send_outcomes.py` (`no_channels`, `channels_unreachable`, `no_weather`, `no_stage`, `kontingent_erschoepft`, …), Kontingent `manueller_abruf` (ADR-0117).

## Dependents (Downstream)

- Trip-Hub, Orte-Hub (beide Seiten oben), `TripHeader` reicht HubKopf-Props durch.
- Listen (`routes/trips/+page.svelte:301`, `routes/compare/+page.svelte:339`) nutzen SendConfirmDialog/sendConfirmModel/sendTargetLabel weiter ⇒ Dialog darf nicht gelöscht werden, solange die Listen ihn brauchen (Entscheidung nötig, siehe Open questions).
- Elementlisten-Abgleich: `frontend/e2e/elementliste_abgleich_logik.ts:391,420ff` – `test-menue` steht in `SCRIPT_ABSCHNITT`, hat aber keinen Bedienplan (heute `nicht_herstellbar`, Test `frontend/src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts:124-148,250-257`). Muss einen Plan bekommen (Klick `subscription-hub-send`, lesen, schließen).
- #3441 (Test-Alarm) hängt sich als Eintrag unterhalb von „Alle eingerichteten Kanäle“ (nach `<hr>`) in dasselbe Menü; Menü-Struktur so anlegen, dass ein weiterer Eintrag ohne Umbau dazukommt.

## Existing Specs/ADRs

- **ADR-0109** Punkt 6 (`docs/adr/0109-reiterstruktur-wetter-zustellung.md:25`): Menü mit Kanälen (Ziel, Sperre mit Grund), Trip Morgen/Abend, „Alle eingerichteten Kanäle“, „Test-Alarm“.
- **ADR-0110** HubKopf ein Baustein; **ADR-0118** „Test schicken ▾“ = `Btn variant="accent"` Fläche `--g-accent-deep` (bleibt).
- **ADR-0092** Testmail nur an bestätigte Profiladresse dieses Nutzers; Staging/Testnutzer über `force_test` auf Stalwart.
- **ADR-0095** Kanal-Parität; **ADR-0097** Trip/Orte ein Code (`context="route"|"vergleich"`, Pendant-Sperre); **ADR-0104** DE/EN; **ADR-0112** nur Bausteine/Tokens, Wächter `frontend/src/lib/__tests__/bausteine_waechter.test.ts` (HubKopf steht in `BESTAND`, `bausteine_waechter_regeln.ts:582`; neue `.svelte` außerhalb atoms/molecules/organisms muss in `SEITEN_SCOPE`).
- Specs: `docs/specs/modules/feat_2278_aktionsmodell.md` (Dialog, AC-3/4/10/12), `fix_1471_sende_dialog_ziel.md`, `feat_2280_handversand_endpoint.md`, `feat_2913_c2_seitenkopf.md`, `feat_2795_s3b_teil1_zustellung.md` (+ #3202 Kürzung).
- Glossar `docs/reference/i18n_glossar.md:13,28,224`: „Orts-Briefing“ nicht mehr für neue Texte; `:29` Briefing, `:51` Empfänger/recipient, `:138` Testmail.

## Mockup-Soll

Quelle `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`:
- Markup Z. 268-276: `<span class="toast" aria-live="polite">` · Kebab `⋮` · `<button class="btn sm accent" aria-haspopup="menu" aria-expanded>Test schicken ▾</button><div class="menu" role="menu" hidden>`. Reihenfolge Toast, Kebab, Knopf.
- Aufbau `renderMenu()` Z. 414-422: Trip ⇒ `.mhead` mit `seg('slot',['Morgen-Briefing','Abend-Briefing'])` + `<hr>`; Orte ⇒ kein Kopf. Je Kanal: frei = `<button role="menuitem" data-send>{Kanal}<small>{Ziel}</small></button>`; gesperrt = `<div class="dis" role="menuitem" aria-disabled="true">{Kanal}<small>gesperrt: {Grund} <button class="linkish">Im Konto {verb} →</button></small></div>`. Dann `<hr>` „**Alle eingerichteten Kanäle**“, `<hr>` Test-Alarm (#3441).
- Ziele Z. 373-377 (`konto()`): E-Mail „an 2 Empfänger“ · Telegram „@henning“ · SMS „+49 171 …“ · Premium-SMS „inReach · über Satellit“. Lücken: Telegram „Telegram-Chat fehlt.“/verbinden · SMS „Nummer noch nicht bestätigt.“/bestätigen · Premium „Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.“/prüfen. E-Mail bleibt in „luecken“ frei.
- Klickverhalten Z. 808-814: Knopf toggelt Menü (`aria-expanded`), Segment wechselt ohne Schließen, Kanal-Klick schließt und meldet: Einzel „{Morgen-Briefing|Abend-Briefing|Briefing} an {Kanal} geschickt · {Ziel} · 20:41“; Alle „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen (nicht verbunden) · …“ (Grund = letzter Teil des Statustexts). Außenklick schließt (Z. 802). Toast 5 s (Z. 879), Fehler rot `.toast.bad`.
- CSS Z. 54-61,194-198: `.menu` absolut rechts, min-width 250 px, `small` Mono 10.5 px `--g-ink-3`, `.dis small` `--g-bad`.

Elementliste `docs/context/einstellungen_neu/elementliste.json` Abschnitt `test-menue` (nur Reiter `wetter`, Zustände normal/laedt/fehler identisch):

| ctx/zustand | Reihenfolge (DE → EN, Schlüssel) |
|---|---|
| trip normal (13) | Morgen-Briefing→Morning briefing `trip.briefing.morgen` · Abend-Briefing→Evening briefing `trip.briefing.abend` · E-Mail→Email `auth.feld.email` · „an 2 Empfänger“ Muster `an {zahl} Empfänger` **Lücke (kein Key/EN)** · Telegram `level.zeile.telegram` · „@henning“ (EN gleich, kein Key) · SMS `wetter.wsw.spalte.sms` · „+49 171 …“ Muster `+{zahl} {zahl} …` · Premium-SMS→Premium SMS `wetter.wsw.kanal.premium` · „inReach · über Satellit“ **Lücke** · „Alle eingerichteten Kanäle“ **Lücke** · „Test-Alarm“ **Lücke** · „Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“ **Lücke** |
| trip luecken (16) | Segment, E-Mail + „an 2 Empfänger“, dann Telegram + „gesperrt: Telegram-Chat fehlt.“ (`zustellung.gesperrt` „locked: {grund}“) + Knopf „Im Konto verbinden →“/„Connect in your account →“ (`zustellung.konto.verbinden`), SMS + „gesperrt: Nummer noch nicht bestätigt.“ + „Im Konto bestätigen →“/„Confirm in your account →“, Premium-SMS + „gesperrt: Schick eine Nachricht vom Gerät, …“ + „Im Konto prüfen →“/„Check in your account →“, Alle, Test-Alarm (2) |
| orte normal (11) / luecken (14) | wie Trip ohne die beiden Segment-Optionen |

Rollen: Segment = `option`, Zeilen = `menuepunkt`, Konto-Links = `knopf`. Elementliste prüft die Kanalnamen gegen Schlüssel aus anderen Bereichen (`auth.feld.email`, `level.zeile.telegram`, `wetter.wsw.*`) – inhaltlich gleich zu `zustellung.kanal.*`.

## i18n-Bestand

Vorhanden: `aktionen.kopf.test_schicken` („Test schicken ▾“/„Send test ▾“, `messages/de/aktionen.json:34`), `aktionen.wird_gesendet`, `trip.briefing.morgen/abend` (`de/trip.json:52`, en:52-53), `zustellung.kanal.*` (`de/zustellung.json:36-39`), `zustellung.gesperrt` (:52), `zustellung.grund.*` (:47-51), `zustellung.konto.*` (:53-55), `zustellung.premium.verfallen_hinweis`, `trip.hub.briefing_gesendet` („Briefing gesendet!“), `vergleich.hub.test_gesendet` („Test-Briefing gesendet“), `fehler.versand.*`, `bausteine.senden_dialog.*` (Dialog, wird im Hub frei).
Fehlt (neu, DE+EN, ggf. Glossar): „an {n} Empfänger“, „inReach · über Satellit“, „Alle eingerichteten Kanäle“, Rückmeldungen „{Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“, „{Briefing} geschickt: {Liste}“, „übersprungen ({Grund})“, ggf. neutrales „Briefing“ für Orte. Kein Key `test_schicken.*`/`alle_kanaele` außer `bausteine.versand.alle_kanaele_ok` (anderer Sinn).

## Backend: Einzelkanal-Test heute?

**Nein, nicht über den Web-Endpunkt.** `briefingSendUrl` (`sendOutcome.ts:117-120`) kennt nur `kind`+`report_type`; Go `briefing_send.go:48-52` verwirft alles andere; Python `send_briefing_endpoint` (`briefings_send.py:140-151`) hat keinen Kanal-Parameter, Trip-Testpfad `send_test_report_outcome` (`trip_report_scheduler.py:1445`) nimmt keinen. **Interne Naht existiert:** `restrict_to_channel` in `_send_trip_report_outcome` (Trip, #2126) und `send_compare_preset`/`send_one_compare_preset` (Orte, #2282), Flags über `resolve_restricted_channel_flags` (`user_tier.py:112`). Achtung Semantik: restrict schaltet den Kanal **auch dann ein, wenn er im Abo aus ist** (gedacht für Inbound-Antworten), und meldet gesperrt als `channels_unreachable`. Ebenso fehlt in der Antwort eine Kanal-Liste (`sent_channels` existiert intern, `trip_report_scheduler.py:2043-2062`), die „Alle“-Rückmeldung „E-Mail ✓ · Telegram übersprungen (…)“ braucht sie oder muss sie aus dem Frontend-Kanalstatus ableiten.

## Risks

1. **Backend-Erweiterung nötig** (Go-Whitelist + Python-Parameter + Trip-Testpfad) ⇒ Full-Stack-Scope; neuer Query-Parameter muss gegen die vier Namen geprüft werden (`_BEKANNTE_KANAELE`, `trip_report_scheduler.py:255-258`), sonst 400.
2. **Echter Versand auf Staging:** jeder Klick versendet real (Mail Stalwart via `force_test`, Telegram/SMS/Premium-SMS echt, Kontingent `user_manual`, Mengenbremse `bremsen.Versand`). E2E nur mit Prüfkonto; SMS/Premium kosten Geld (seven.io).
3. **Mandantentrennung:** Kanal-Parameter darf nie Ziel überschreiben – nur Kanal wählen, Empfänger immer aus Profil des Auth-Nutzers; Zwei-Nutzer-Test für den erweiterten Endpunkt Pflicht (bestehend `tests/tdd/test_briefings_send_endpoint.py`, `internal/handler/briefing_send_test.go`).
4. **Kanal-Parität:** alle vier Kanäle im Menü, Sperrgründe identisch zur Zustellung (`kanalStatus`) – Abweichung heute: E-Mail unbestätigt ist im Dialog gesperrt (`sendTargetLabel.ts:83-85`), in der Zustellung bedienbar mit Warnpunkt (`zustellungModell.ts:187-189`).
5. **Mockup vs. PO-Entscheidungen #3202:** Telegram „@henning“ – kein Name im Profil, PO 20.11.: „nur verbunden, nie Chat-ID, kein Telegram-Name“ (`zustellungModell.ts:194-196`); E-Mail „an 2 Empfänger“ – PO 21.11.: keine Empfängerzahl, nur Konto-Adresse (`zustellungModell.ts:174-176`, `preset.empfaenger` inert seit #1452).
6. **Mobil:** bits-ui Dropdown am Handy vs. Sheet-Muster des Kebab; Menü (≥250 px) in schmaler Leiste mit Brotkrumen; Rückmeldung muss am Handy sichtbar sein (heute rendert `meldungen` in jeder Breite – K12-„fehlt mobil“ ggf. veraltet, auf Staging prüfen).
7. **Viele Bestandstests** binden Dialog/testids (Liste unten) – Ratsche nicht durch Löschen umgehen, sondern auf neues Verhalten umstellen.
8. Wächter ADR-0112: neuer Menü-Baustein in `molecules`/`organisms` nur mit Tokens; Mockup-Styles nicht kopieren.

## Betroffene Tests

- Unit (node --test): `molecules/__tests__/send_confirm_dialog.test.ts`, `send_confirm_dialog_sperre.test.ts`; `shared/__tests__/aktionsmodell_seiten_bindung.test.ts` (Z. 43, 123, 291, 306, 358), `aktionsmodell_bausteine_ausloeser.test.ts:51`; `hub-kopf/__tests__/hub_kopf_{baustein,c2_mockup,c2_bildabgleich,seiten_bindung,seiten_paritaet}.test.ts`; `trip-detail/__tests__/trip_hub_aktionen_verhalten.test.ts`; `routes/compare/__tests__/compare_hub_{aktionen_verhalten,test_send_meldung,versand_neuer_endpunkt,loeschen_bestaetigung}.test.ts`, `compare_send_dialog_target.test.ts`; `routes/trips/[id]/__tests__/trip_hub_loeschen.test.ts`; `compare/__tests__/vergleich_hub_sprache.test.ts`; `versand-tab/__tests__/sendTargetLabel*.test.ts`; i18n-Wächter `keine_hartkodierten_nutzertexte.test.ts`, `reaktivitaet_waechter.test.ts`; `elementliste_abgleich_bedienplan.test.ts`.
- E2E: `hub-send-dialog-target.staging.spec.ts`, `send-in-flight-guard.spec.ts`, `issue-767-768-test-briefing.spec.ts`, `aktionsmodell-durchklick.spec.ts`, `hub-kopf-c2-{mockup,bildabgleich}.staging.spec.ts`, `hub-kopf-aufbau.spec.ts`, `mobile-ux-audit.spec.ts`, `fix-2271-email-verify-gate.spec.ts`, `pwa-offline-sperre-und-mandant.spec.ts`, `e2e/helpers.ts`, `elementliste-abgleich.staging.spec.ts`.
- Backend: `tests/tdd/test_briefings_send_endpoint.py`, `tests/tdd/_handversand_fixtures.py`, `tests/tdd/test_api_fehlertexte_forecast_handversand.py`, `internal/handler/briefing_send_test.go`, `internal/router/mengenbremsen_*_test.go`.

## Open questions

1. Welche Kanalzeilen zeigt das Menü: alle vier (Mockup/Elementliste) oder nur die im Abo eingeschalteten (`standAus*().briefing`)? Darf ein Test an einen im Abo ausgeschalteten, aber verbundenen Kanal gehen (restrict-Semantik erlaubt es)?
2. Ziel-Texte E-Mail/Telegram: Mockup („an 2 Empfänger“, „@henning“) widerspricht PO-Entscheidungen 20./21.11. (#3202). Vermutlich gekürzte Adresse „henning@…“ bzw. „verbunden“ – braucht PO-Klärung oder ist über #3202 bereits entschieden (dann Elementlisten-Ausnahme dokumentieren).
3. „Alle eingerichteten Kanäle“ = heutiger Versand ohne Kanal-Parameter? Rückmeldung je Kanal: Backend liefert `sent_channels` mit, oder Frontend leitet „übersprungen ({Grund})“ aus `kanalStatus` ab?
4. Orte: Label „Briefing“ (Mockup `slotLabel`) vs. „Orts-Briefing“ (#2797 Umfang 2) vs. Glossar (Orts-Briefing abgelöst). Orte haben auch Morgen/Abend-Slots (`standAusPreset` morgen/abend) – kein Segment laut Mockup.
5. Listen (`/trips`, `/compare`) behalten den Dialog „Briefing senden?“? (#3440 sagt nur „Senden-Dialog entfällt“ für den Kopf.)
6. Uhrzeit „{hh:mm}“: Client-Uhr beim Erfolg (kein Zeitstempel in der Antwort).
7. Mobil: Dropdown oder Sheet? Kebab nutzt Sheet; Mockup zeigt nur Dropdown.
8. Zustand „luecken“ auf Staging herstellbar (Prüfkonto mit fehlendem Telegram, unbestätigter SMS, verfallener Premium-Rückadresse)?

## Analysis

Stand 27.11.2026 · Grundlage: Kontext oben (Datei:Zeile gemessen), strategische Bewertung Plan/Sonnet (Varianten A–D), Gegenprüfung durch Orchestrator.

### Type
Feature (Full-Stack): Frontend-Menü + Erweiterung des Handversand-Endpunkts um Kanalwahl.

### Tech-Lead-Entscheidungen (offene Fragen 1–8 aufgelöst, keine PO-Frage nötig)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Welche Kanalzeilen? | Immer alle vier (Mockup, Elementliste). Bedienbar/gesperrt/Grund/Konto-Verb nur aus `kanalStatus(profil)`. Einzelkanal-Test geht auch an einen verbundenen Kanal, der im Abo aus ist (`restrict_to_channel` schaltet ihn ein). | Test prüft den Kanal; Sperrlogik nie neu ableiten (#3202). |
| 1b | E-Mail unbestätigt | Im Menü **gesperrt** („gesperrt: Adresse noch nicht bestätigt.“ + „Im Konto bestätigen →“), Backend lehnt `channel=email` bei unbestätigter Adresse ab. | ADR-0092 (Testmail nur an bestätigte Profiladresse); heutiger Dialog sperrt ebenso (`sendTargetLabel.ts:83-85`) — keine Verhaltensänderung. Abweichung zu `kanalStatus` (Warnpunkt) über ein Test-Flag im Modell, nicht über Kopie der Logik. |
| 2 | Ziel-Texte | E-Mail = gekürzte Konto-Adresse (`adresseGekuerzt`), Telegram = „verbunden“ ohne Namen, SMS = `nummerGekuerzt`, Premium-SMS = neuer Schlüssel „inReach · über Satellit“. Abweichungen vom Mockup („an 2 Empfänger“, „@henning“) als Einträge in `elementliste_freigaben.json` mit Spec-Verweis. | PO-Entscheidungen 20./21.11. (#3202): kein Telegram-Name, keine Empfängerzahl (`preset.empfaenger` inert seit #1452). Bereits entschieden, nicht erneut vorlegen. |
| 3 | „Alle eingerichteten Kanäle“ | = heutiger Versand ohne `channel`. Antwort bekommt `sent_channels` (Backend-Wahrheit, was rausging); „übersprungen ({Grund})“ je nicht gesendetem Kanal aus `kanalStatus`, „fehlgeschlagen“ wenn eingerichtet+bedienbar aber nicht in `sent_channels`. | Ohne Backend-Liste würden Teilausfälle verschwiegen. |
| 4 | Orte-Label | Kein Segment; Label „Briefing“ (Glossar: „Orts-Briefing“ abgelöst). | Mockup `slotLabel`, Glossar `i18n_glossar.md`. |
| 5 | Listen /trips, /compare | Behalten `SendConfirmDialog` (nicht im Umfang). Dialog wird nur aus beiden Hubs entfernt. | Issue nennt nur den Kopf; Listen sind andere Fläche. |
| 6 | Uhrzeit | Client-Uhr beim Erfolg, `hh:mm` lokal. | Antwort hat keinen Zeitstempel; Rückmeldung ist sofort. |
| 7 | Mobil | Kebab-Muster: Desktop bits-ui `DropdownMenu`, ≤899 px `Sheet` (44-px-Zeilen). Rückmeldung über `meldungen` in jeder Breite, 5 s, Fehler rot, testids einheitlich. | Konsistenz mit `SubscriptionKebab`, ADR-0112; 250-px-Dropdown in schmaler Leiste riskant. |
| 8 | Zustand „lücken“ auf Staging | Prüfkonto per Seed mit fehlendem Telegram/unbestätigter SMS/verfallener Premium-Rückadresse; E2E-Versand nur E-Mail (Stalwart) + Telegram, SMS/Premium nicht real auslösen (Kosten) — dort nur Sperr-Darstellung und Unit/Endpunkt-Test mit Transport-Fake an der Grenze. | Kosten seven.io; echte Wirkung wo bezahlbar. |

### Affected Files (Change Type)

**Backend**
- `api/routers/briefings_send.py` MODIFY — Query `channel` (nur `email|telegram|sms|premium_sms`, sonst 400 `invalid_channel`); E-Mail-Gate `can_send_email()` nur bei `channel` None oder `email`; `channel=email` + unbestätigt ⇒ Fehler; `sent_channels` in Antwort (Trip + Vergleich).
- `src/services/trip_report_scheduler.py` MODIFY — `send_test_report_outcome(..., restrict_to_channel=None, sent_channels_sink=None)` reicht an `_send_trip_report_outcome` durch; Sink füllt `result.sent_channels` (~Z. 2043).
- `src/services/scheduler_dispatch_service.py` MODIFY — `send_compare_preset` Sink für gesendete Kanäle (Muster `orte_ohne_wetter`).
- `src/services/send_outcomes.py` MODIFY (ggf.) — Outcome `invalid_channel`/`email_unverified` + Texte.
- `internal/handler/briefing_send.go` MODIFY — Whitelist um `channel` (Go prüft die vier Namen ebenfalls, 400 sonst).
- Tests: `tests/tdd/test_briefings_send_endpoint.py` (Kanal, 400, Zwei-Nutzer, unbestätigt, sent_channels), `internal/handler/briefing_send_test.go`.

**Frontend**
- `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` CREATE — ein Baustein für Trip+Orte (`context="route"|"vergleich"`), Desktop-Dropdown/mobil Sheet, emittiert `{kanal: KanalId|'alle', berichtsart}`, Abschnitt `data-abschnitt="test-menue"`, erweiterbar um Eintrag „Test-Alarm“ (#3441).
- `frontend/src/lib/components/molecules/testSchickenModell.ts` CREATE — Zeilenmodell aus `kanalStatus` (+ E-Mail-unbestätigt-Sperre), Rückmeldungstexte Einzel/Alle.
- `shared/hub-kopf/HubKopf.svelte` MODIFY — Knopf öffnet Menü (`aria-haspopup="menu"`, `aria-expanded`) statt `onSend()`; Callback `onTest({kanal, berichtsart})`.
- `routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte` MODIFY — Dialog raus, `handleTest` mit Kanal, einheitliche Rückmeldung (testids `test-schicken-ok`/`-fehler`, 5 s).
- `shared/subscriptionExec.ts`, `utils/sendOutcome.ts` MODIFY — `channel` in `briefingSendUrl`, `sent_channels` auswerten.
- `messages/{de,en}/*.json` MODIFY — neue Schlüssel (Ziel Premium, „Alle eingerichteten Kanäle“, Rückmeldungen, übersprungen, E-Mail-Sperre); Glossar ergänzen.
- `docs/context/einstellungen_neu/elementliste_freigaben.json` MODIFY — Freigaben Ziel E-Mail/Telegram.
- `frontend/e2e/elementliste_abgleich_logik.ts` MODIFY — Bedienplan `test-menue` (Klick `subscription-hub-send`, lesen, schließen).
- Bestandstests umstellen (Liste „Betroffene Tests“ oben), nicht löschen; `bausteine_waechter_regeln.ts` falls nötig.

### Scope / Risk
- Geschätzt: Produktivcode ~105 Backend + ~330 Frontend ≈ 435 LoC (ohne i18n/Doku), Tests ~450. Projektlimit `scope_guard.max_loc_delta: 250` ⇒ **Override nötig (~550)**. Entscheidung: **ein Workflow** statt Backend/Frontend-Schnitt — der Backend-Teil hat ohne Menü keinen Nutzerwert und wäre allein nicht E2E-abnehmbar; PO-Regel „kleine verwandte Teile in einem Durchlauf“. Override wird in Phase 3 mit dieser Begründung gesetzt.
- Risiko **mittel**: echter Versand auf Staging (Kosten SMS/Premium), Mandantentrennung (Kanal wählt nie Empfänger; Zwei-Nutzer-Test), viele Bestandstests am Dialog.
- In-Flight/Lock bleiben je Abo (nicht je Kanal): zweiter Klick während laufendem Versand ⇒ 409 `already_running` mit bestehendem Text. Kontingent `manueller_abruf` bucht je Klick (auch Einzelkanal) — in der Spec benennen.

### Technical Approach
1. Backend-Vertrag: `POST /api/briefings/{id}/send?kind=…&report_type=…&channel=…` → Antwort `{…, sent_channels: [..]}`. Go reicht `channel` nur nach Whitelist weiter; Python validiert erneut gegen `_BEKANNTE_KANAELE`; `user_id` weiter aus Auth-Kontext.
2. Trip: `send_test_report_outcome` → `_send_trip_report_outcome(restrict_to_channel=…)` (Naht #2126); Vergleich: `send_compare_preset(restrict_to_channel=…)` (Naht #2282). Gesperrter Kanal ⇒ `channels_unreachable` (bestehender Text).
3. Frontend: Modell aus `kanalStatus(data.profile)`; Baustein ruft keine API; Seite hält Laufzustand und Rückmeldung; Texte nur über Katalog DE/EN.
4. Elementlisten-Bedienplan + Freigaben, damit Abnahme #3009 `test-menue` messen kann.

### Dependencies
Profil `GET /api/auth/profile` (unverändert), Versandkette Go → Python → Scheduler → Transporte, `zustellungModell.kanalStatus`, bits-ui DropdownMenu, `Sheet`, `Segmented`. Nachfolger: #3441 (Test-Alarm im selben Menü).

### Open Questions
Keine Produktfragen offen: Ziel-Texte durch #3202 entschieden, Umfang K9–K12 durch #2797 freigegeben. Freigabepflichtig bleibt die Spec.
