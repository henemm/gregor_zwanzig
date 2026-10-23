---
entity_id: shared_preview_tab
type: module
created: 2026-10-19
updated: 2026-10-19
status: implemented
version: "1.0"
tags: [epic-2345, preview, trip, ortsvergleich, shared, alert-preview]
issue: 2283
workflow: feat-2283-vorschau-baustein
---

# Geteilter Vorschau-Baustein Trip und Ortsvergleich

> **Abgelöst durch #1743 (2026-10-22, PO-Entscheid):** Der Reiter „Vorschau" ist ersatzlos entfallen. `shared/PreviewTab.svelte`
> und der Endpoint `GET /api/briefings/{id}/preview` (Go + Python) sind zurückgebaut. Nach PO-Entscheid 2026-10-22 (F003)
> entfallen auch die verwaisten Reste (`CompareChatBubble`, `CompareChannelSwitch`, `SmsPhoneFrame`, `EmailIframe`) und die
> Routen `POST /api/preview/compare/{id}`, `GET /api/preview/{trip}/email|telegram`. Es bleibt nur die Alarm-Vorschau im
> Reiter Alarme (`POST /api/briefings/{id}/alert-preview`); `GET /api/preview/{trip}/sms` bleibt allein als Messweg der
> Staging-Specs. Die ACs dieser Spec bleiben als Historie stehen.

## Approval

- [ ] Approved

## Purpose

Trip-Hub und Ortsvergleich-Hub bekommen **einen** gemeinsamen Vorschau-Reiter (`shared/PreviewTab.svelte`, Parameter `context="route"|"vergleich"`). Dahinter stehen eine kind-neutrale Vorschau-Schnittstelle und eine kind-neutrale Alarm-Vorschau. Das Mail-Template des Ortsvergleichs bleibt eigenständig (ADR-0023, E9) — geteilt wird nur der Rahmen. Ticket #2283, Epic #2345 Etappe P3 (Rest nach #2278). Alle Scheiben S1 bis S5 liegen in dieser einen Spec; nichts wird abgespalten.

### Abweichungen vom Issue-Zielbild (bewusst, begründet)

1. **`?kind=` als Query statt `{kind}` im Pfad.** Das Issue nennt `/api/preview/{kind}/{id}/{channel}`. Der bestehende Dispatcher `/api/briefings` (ADR-0023, #1250 S6) führt `kind` aber als Pflicht-Query (`?kind=route|vergleich`, sonst 400 `kind_required`). Ein `{kind}` im Pfad wäre ein zweites, neues Muster. Wir bleiben beim bestehenden Muster: `GET /api/briefings/{id}/preview?kind=…`.
2. **Ein Aufruf für alle Kanäle statt je Kanal ein Aufruf.** Der Ortsvergleich kann Vorschau nur gebündelt rendern (60 bis 75 Sekunden, kein Zwischenspeicher). Einzelaufrufe je Kanal würden die Wartezeit vervielfachen. Der Trip-Bündelaufruf ist billig (drei vorhandene Render-Funktionen). So braucht der geteilte Reiter genau **einen** Lader.
3. **Issue-AC-1 „Anordnung wie im Trip" wird zu „gleiche Anordnung in beiden Hubs".** Der Trip zeigt heute weder Telegram noch einen Kanalumschalter noch den Premium-SMS-Hinweis; der Ortsvergleich schon. Weil alle vier Kanäle gleichrangig sind, bekommen beide Hubs die vollständige Anordnung — nicht der Trip-Ist-Stand ist Maßstab.
4. **Test-Senden verlässt den Vorschau-Reiter.** Senden gibt es nur noch über das Aktionsmodell (#2278) im Hub-Kopf. Im Reiter wäre es eine Doppelung desselben Sendewegs.

## Source

- **Frontend:** `frontend/src/lib/components/shared/PreviewTab.svelte` (neu), `shared/previewLoader.ts` (neu), `preview/EmailIframe.svelte`, `preview/SmsPhoneFrame.svelte`, `preview/previewHelpers.ts`, `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `shared/AlarmeTab.svelte`, `alerts-tab/AlertPreviewCard.svelte`, `shared/versand-tab/VTAlertSample.svelte`, `frontend/src/lib/api.ts`
- **Go-API:** `internal/handler/briefing_preview.go` (neu), `internal/handler/preview_proxy.go`, `internal/handler/proxy.go`, `internal/router/router.go`
- **Python-Core:** `api/routers/preview.py`, `api/routers/validator.py`, `src/services/compare_alert_preview_service.py` (neu), `src/output/renderers/alert/project.py` (wiederverwendet, nicht geändert)
- **Doku:** `docs/reference/api_contract.md`
- **Identifier:** `PreviewTab`, `briefingVorschau(kind, id)`, `alarmVorschau(kind, id)`

## Estimated Scope

- **LoC:** produktiv ca. +700/−600 (Ortsvergleich-Hub netto Löschung), verteilt auf fünf Scheiben je ≤250 LoC; bei Überschreitung `loc_limit_override`, nie AC streichen
- **Files:** ca. 25 (ohne Tests ca. 15)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `/api/briefings` Dispatcher (`briefing_subscription.go`) | Go-Handler | Vorbild für `?kind=`, `ValidEntityID`, `bailIf` |
| `middleware.UserIDFromContext`, `appendUserID` | Go | `user_id` aus Auth, Client-Wert verwerfen (ADR-0003) |
| `compare_preview_service.py`, `preview_service.py` | Python | bestehende Render-Funktionen, unverändert |
| `output/renderers/alert/project.py` | Python | Versand-Projektionen, einziger Alarm-Renderer (ADR-0011) |
| `shared/subscriptionActions.ts` (Aktionsmodell #2278) | Frontend | einziger Sendeweg im Hub-Kopf |
| ADR-0023, ADR-0011, ADR-0003 | Entscheidungen | Template getrennt, ein Alarm-Renderer, Anti-Spoofing |

## Implementation Details

**Scheibenschnitt**

| Scheibe | Inhalt | Abhängig von |
|---|---|---|
| S1 | Backend Vorschau: Trip-Bündelaufruf (Python), Go-Dispatcher, Alt-Routen als Delegates, `/signal` weg, Wächter, `api_contract.md` | — |
| S2 | `shared/PreviewTab` + Lader, Bausteine inhaltsgetrieben, Trip-Reiter umgestellt | S1 |
| S3 | Ortsvergleich-Reiter auf `PreviewTab`, Senden raus, tote Bausteine weg | S2 |
| S4 | Alarm-Vorschau Backend kind-neutral, Vergleich über Versand-Projektionen | — |
| S5 | Alarm-Vorschau Frontend: `AlertPreviewCard` im Vergleich, `VTAlertSample` weg | S4 |

**Antwortform Bündelaufruf** (für beide kinds gleich): `{subject, email_html, sms: {text, char_count}, telegram: {body, bubbles?}}`. Optionen `type` (Morgen/Abend), `date`, `demo` gelten nur bei `kind=route`.

**Go-Zeitlimits:** 30 s (`route`), 60 s (`vergleich`) auf Go-Seite; Frontend-Zeitlimit Vergleich bleibt 70 s.

**Alarm-Vorschau Vergleich:** keine zweite Renderer-Variante; die Vorschau ruft dieselben Projektionen wie der Versand (`to_multi_point_alert_message`, `to_multi_location_onset_alert_message`, amtlicher Pfad aus `compare_official_alert`). Querverweis #2261 Teil B, keine Abspaltung.

**Pendant-Sperre:** neue Dateien nur unter `shared/`, `preview/`, `molecules/`; keine neuen Dateien unter `compare/` oder `trip-detail/`; keine neue Compare-only-Komponente.

**Zusätzlich geänderte Dateien (Umsetzung, 2026-10-19):** `src/services/preview_service.py` (Bündel-Render `render_all_channels` ergänzt), `frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts` (kind-neutraler Abruf), `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` (1 Zeile).

**Begründung Pendant-Sperre für `compare_alert_preview_service.py`:** Der Dienst ist compare-eigen, weil die Vergleichs-Alarm-Nachrichten andere Versand-Builder nutzen (`to_multi_point_alert_message`, `to_multi_location_onset_alert_message`, `build_compare_official_alert_notices`); der Trip-Pfad nutzt `render_alert_preview` in `validator_render_service.py`. Der Frontend-Baustein (`AlertPreviewCard`) ist geteilt.

**AC-6 Wächter:** Der Go-Wächter liest das versionierte Abbild `internal/router/testdata/python_preview_routes.json`; `tests/test_vorschau_proxy_ziel_snapshot.py` erzwingt, dass das Abbild exakt der echten FastAPI-Routentabelle entspricht.

## Expected Behavior

- **Input:** Nutzer öffnet im Trip-Hub oder Ortsvergleich-Hub den Reiter „Vorschau" bzw. klickt in „Alarme" auf eine Alarm-Vorschau.
- **Output:** In beiden Hubs dieselbe Anordnung: Kanalumschalter E-Mail · SMS · Telegram, Premium-SMS-Hinweis, SMS im Telefonrahmen, E-Mail mit Ansicht Desktop/Mobil, Telegram als Chat-Blase. Alarm-Vorschau mit echten Daten in beiden Hubs.
- **Side effects:** Keine. Vorschau sendet nichts und verändert keine Daten. `/api/preview/{id}/signal` entfällt (Signal ist seit #610 app-weit entfernt).

## Acceptance Criteria

### S1 — Backend Vorschau

- **AC-1:** Given ein angemeldeter Nutzer mit einem Trip / When er `GET /api/briefings/{id}/preview?kind=route` aufruft / Then erhält er in einer Antwort `subject`, `email_html`, `sms` (Text und Zeichenzahl) und `telegram` (Text, ggf. Blasen), und der Inhalt je Kanal ist identisch zu dem, was die bisherigen Einzelrouten für denselben Trip liefern.
  - Test (Kern, Python + Go): Bündelantwort gegen die Antworten der drei Einzelrouten desselben Trips vergleichen (Gleichheit je Kanal, ohne Mock der Render-Funktionen). Datei: `tests/integration/test_briefing_preview_bundle.py`, `internal/handler/briefing_preview_test.go`.
  - Scheibe: S1

- **AC-2:** Given ein angemeldeter Nutzer mit einem Ortsvergleich / When er `GET /api/briefings/{id}/preview?kind=vergleich` aufruft / Then erhält er dieselbe Antwortform wie bei `kind=route` (`subject`, `email_html`, `sms`, `telegram`), und das Ergebnis entspricht dem Inhalt der bisherigen Route `POST /api/preview/compare/{id}`.
  - Test (Kern): Bündelantwort Vergleich gegen `compare_preview_service` mit identischer Eingabe. Datei: `tests/integration/test_briefing_preview_bundle.py`.
  - Scheibe: S1

- **AC-3:** Given ein Aufruf von `/api/briefings/{id}/preview` / When der Parameter `kind` fehlt oder weder `route` noch `vergleich` ist / Then antwortet die API mit 400 und Fehlercode `kind_required`; Given eine ungültige Entitäts-ID (`ValidEntityID` verletzt, z. B. mit Pfadzeichen) / When aufgerufen / Then antwortet sie mit 400 und es wird nichts an Python weitergereicht.
  - Test (Kern, Go): Tabellentest mit fehlendem, falschem, leerem `kind` und ungültigen IDs; prüft Statuscode und dass der Python-Kern nicht erreicht wurde. Datei: `internal/handler/briefing_preview_test.go`.
  - Scheibe: S1

- **AC-4:** Given zwei verschiedene Nutzer A und B, jeder mit eigenem Trip und eigenem Ortsvergleich / When A die Vorschau mit der ID eines Eintrags von B abruft (beide kinds) / Then antwortet die API mit 404 und enthält keine Daten von B; Given A schickt zusätzlich einen eigenen `user_id`-Parameter mit fremdem Wert / When aufgerufen / Then wird dieser verworfen und stets die Nutzerkennung aus der Anmeldung verwendet — niemals `default`.
  - Test (Kern, Go + Python): Zwei-Nutzer-Test je kind, inklusive eingeschleustem `user_id` in der Query. Datei: `internal/handler/briefing_preview_test.go`, `tests/integration/test_briefing_preview_user_isolation.py`.
  - Scheibe: S1

- **AC-5:** Given die bisherigen Routen `GET /api/preview/{trip_id}/{email,sms,telegram}` und `POST /api/preview/compare/{id}` / When ein bestehender Aufrufer sie weiter nutzt / Then antworten sie unverändert in Form und Inhalt und laufen über dieselbe gemeinsame Proxy-Logik wie der neue Bündelaufruf (Delegates, keine zweite Implementierung).
  - Test (Kern, Go): bestehende `preview_proxy_test.go` und `compare_preview_proxy_test.go` bleiben grün und werden um einen Beleg ergänzt, dass beide Wege dieselbe Proxy-Funktion durchlaufen. Datei: `internal/handler/preview_proxy_test.go`.
  - Scheibe: S1

- **AC-6:** Given der Router / When `GET /api/preview/{trip_id}/signal` aufgerufen wird / Then ist die Route nicht mehr registriert (404), und ein Wächtertest schlägt Alarm, sobald irgendeine Preview-Proxy-Route in `router.go` kein Ziel im Python-Core hat.
  - Test (Kern, Go): Muster `legacy_subscription_routes_removed_test.go` — Route entfernt; zweiter Test vergleicht alle Preview-Proxy-Pfade gegen die Python-Routen (echte Routentabelle, kein Spiegeln). Datei: `internal/router/preview_proxy_targets_test.go`.
  - Scheibe: S1

- **AC-7:** Given `docs/reference/api_contract.md` / When der Drift-Test läuft / Then enthält die Doku die neuen Routen `GET /api/briefings/{id}/preview` und `POST /api/briefings/{id}/alert-preview`, die Alt-Routen als Delegates, und `/signal` ist gestrichen; der Drift-Test bleibt grün.
  - Test (Kern): `tests/test_api_contract_drift.py` (bestehend, doc-compliance-test).
  - Scheibe: S1

### S2 — Geteilter Reiter im Trip-Hub

- **AC-8:** *(abgelöst durch #1743: der Reiter „Vorschau" entfällt; Mini-Vorschauen bleiben im Reiter Wetter-Metriken)* Given der Trip-Hub, Reiter „Vorschau" / When der Nutzer ihn öffnet / Then sieht er einen Kanalumschalter E-Mail · SMS · Telegram; bei SMS den Text im Telefonrahmen; bei E-Mail eine Ansicht Desktop/Mobil; bei Telegram eine Chat-Blase; und den Premium-SMS-Hinweis (`premiumSmsPreviewNote`).
  - Test (Kern, node --test mit SSR-Harness für `PreviewTab context="route"`; Live: Playwright gegen Staging). Datei: `frontend/src/lib/components/shared/__tests__/previewTab.test.ts`, `frontend/e2e/preview-tab-gleiche-anordnung.spec.ts`.
  - Scheibe: S2

- **AC-9:** *(abgelöst durch #1743: der Reiter „Vorschau" entfällt, kein Briefing-Vorschau-Abruf mehr)* Given der geöffnete Vorschau-Reiter in einem der beiden Hubs / When er geöffnet wird / Then wird die Vorschau mit genau **einem** Abruf geladen (kein Laden vor dem Öffnen des Reiters), und When der Nutzer den Kanal wechselt oder zwischen Desktop und Mobil umschaltet / Then entsteht kein neuer Abruf.
  - Test (Kern, node --test: Zähler am Lader; Live: Playwright zählt Netzwerkaufrufe an `/api/briefings/*/preview`). Datei: `frontend/src/lib/components/shared/__tests__/previewLoader.test.ts`, `frontend/e2e/langlaeufer-zeitbudget-wirkort.spec.ts` (migriert).
  - Scheibe: S2

- **AC-10:** Given `PreviewTab` / When `context="route"` / Then sind Morgen/Abend-Umschaltung und Demo-Hinweis vorhanden und wirken wie bisher (Standard `demoMode=true` unverändert); When `context="vergleich"` / Then sind beide nicht vorhanden, weil der Ortsvergleich nur einen festen Berichtstyp und keine Demo-Daten kennt.
  - Test (Kern, node --test): beide Kontexte rendern, Elemente vorhanden bzw. abwesend. Datei: `frontend/src/lib/components/shared/__tests__/previewTab.test.ts`.
  - Scheibe: S2

- **AC-11:** Given ein bestehender Trip / When die Trip-Vorschau nach der Umstellung geöffnet wird / Then entspricht der Inhalt von E-Mail und SMS dem bisherigen (gleiche Betreffzeile, gleiches HTML, gleicher SMS-Text), und der tote Platzhalter-Reiter `vorschau` („#189") in `TripTabs.svelte` ist entfernt.
  - Test (Kern: Bündelantwort-Gleichheit aus AC-1; Live: Playwright `email-preview-header.spec.ts` migriert). Datei: `frontend/e2e/email-preview-header.spec.ts`.
  - Scheibe: S2

### S3 — Geteilter Reiter im Ortsvergleich-Hub

- **AC-12:** Given der Ortsvergleich-Hub, Reiter „Vorschau" / When der Nutzer ihn öffnet / Then rendert derselbe `PreviewTab` mit `context="vergleich"` dieselbe Anordnung wie im Trip (Kanalumschalter E-Mail · SMS · Telegram, Premium-SMS-Hinweis, SMS im Telefonrahmen, E-Mail Desktop/Mobil, Telegram-Blase), und CompareTabs enthält keinen eigenen Vorschau-Zustand und kein eigenes Vorschau-Markup mehr.
  - Test (Kern, node --test mit SSR-Harness über `CompareTabs`: Vorschau-Reiter enthält `PreviewTab`; Live: Playwright). Datei: `frontend/src/lib/components/shared/__tests__/previewTab.test.ts`, `frontend/e2e/compare-hub-briefing-times.spec.ts` (migriert).
  - Scheibe: S3

- **AC-13:** Given der Vorschau-Reiter in Trip-Hub und Ortsvergleich-Hub / When der Nutzer ihn betrachtet / Then enthält er keinen Test-Senden-Knopf; Senden ist nur über das Aktionsmodell (#2278) im Hub-Kopf erreichbar, am Desktop und mobil, und diese Wege senden weiterhin an die konfigurierten Empfänger des Nutzers.
  - Test (Kern: Reiter-Markup ohne Sende-Knopf; Live: Playwright `compare-hub-versand-inline.spec.ts` und `compare-mobile-vervollstaendigung.spec.ts` migriert — testid `compare-hub-activation-testsend` wird auf den Hub-Kopf umgestellt, nicht still gelöscht). Datei: `frontend/e2e/compare-hub-versand-inline.spec.ts`.
  - Scheibe: S3

- **AC-14:** Given das Frontend-Verzeichnis / When S3 abgeschlossen ist / Then sind `CompareBriefingPreview` und `ComparePreviewMissing` (produktiv tot seit #1270) samt Barrel-Einträgen entfernt, ebenso die durch `PreviewTab` ersetzten Vergleichs-Vorschau-Bausteine (`CompareSmsPreview`, eigenes `iframe srcdoc`), und es gibt keine neue Compare-only-Vorschau-Komponente; der Umschalter und die Chat-Blase leben als kontextneutrale Bausteine weiter.
  - Test (Kern, node --test): Barrel `molecules/index.ts` exportiert die Entfernten nicht mehr; `issue_578_molecules_organisms.test.ts` angepasst; Import-Test, dass `CompareTabs` keinen der entfernten Bausteine mehr lädt (Verhalten über Rendern, kein Dateitext-Check). Datei: `frontend/src/lib/components/molecules/__tests__/issue_578_molecules_organisms.test.ts`.
  - Scheibe: S3

- **AC-15:** Given ein Ortsvergleich mit mindestens drei Orten / When die Vorschau geöffnet wird / Then ist das Vergleichs-Mail-Template unverändert (Mail-Validator `email_spec_validator.py` bleibt grün) und die Wartezeit ist nicht schlechter als vorher: genau ein Abruf, Zeitlimits 60 s (Go) und 70 s (Frontend) unverändert, kein Laden beim bloßen Öffnen des Hubs.
  - Test (Kern: `apiZeitlimit.test.ts` und Go-Zeitlimit-Test unverändert grün; Live-Staging: `email_spec_validator.py` gegen zugestellte Vergleichs-Mail, Exit 0, plus Messung der Vorschau-Laufzeit). Datei: `frontend/src/lib/__tests__/apiZeitlimit.test.ts`.
  - Scheibe: S3

### S4 — Alarm-Vorschau Backend

- **AC-16:** Given ein angemeldeter Nutzer / When er `POST /api/briefings/{id}/alert-preview?kind=route|vergleich` aufruft / Then antwortet die API bei fehlendem oder falschem `kind` mit 400 `kind_required`, bei ungültiger ID mit 400, bei fremder ID (zwei Nutzer, beide kinds) mit 404, verwirft einen Client-`user_id` und liefert für eigene Einträge die Alarm-Vorschau; `POST /api/trips/{id}/alert-preview` bleibt als Delegate mit unverändertem Verhalten.
  - Test (Kern, Go + Python): Zwei-Nutzer-Test je kind; Delegate-Gleichheit. Datei: `internal/handler/briefing_alert_preview_test.go`, `tests/integration/test_alert_preview_kind_isolation.py`.
  - Scheibe: S4

- **AC-17:** Given ein Ortsvergleich mit Alarm-Regeln und einer Messwert-Abweichung an mehreren Orten / When die Alarm-Vorschau (Art Abweichung) abgerufen wird / Then ist ihr Text in allen Kanälen identisch zur Nachricht, die der Versand (`to_multi_point_alert_message`) für dieselbe Eingabe erzeugt.
  - Test (Kern, Python): Vorschau-Ergebnis gegen direkten Aufruf der Versand-Projektion, mehrere Körperfälle (ein Ort, mehrere Orte); kein Mock der Projektion. Datei: `tests/tdd/test_alert_preview_compare_paritaet.py`.
  - Scheibe: S4

- **AC-18:** Given ein Ortsvergleich und ein Regen-/Radar-Ereignis (Onset) / When die Alarm-Vorschau (Art Radar/Onset) abgerufen wird / Then ist ihr Text identisch zur Nachricht aus `to_multi_location_onset_alert_message` für dieselbe Eingabe.
  - Test (Kern, Python): Gleichheit je Kanal gegen die Versand-Projektion. Datei: `tests/tdd/test_alert_preview_compare_paritaet.py`.
  - Scheibe: S4

- **AC-19:** Given ein Ortsvergleich und eine amtliche Warnung / When die Alarm-Vorschau (Art amtlich) abgerufen wird / Then ist ihr Text identisch zur Nachricht, die der Versandpfad (`compare_official_alert` über `send_multi_location_official_alert`) für dieselbe Warnung erzeugt; die Vorschau enthält nur Daten, keine Handlungsempfehlung.
  - Test (Kern, Python): Gleichheit gegen die Versand-Projektion für den amtlichen Fall. Datei: `tests/tdd/test_alert_preview_compare_paritaet.py`.
  - Scheibe: S4

### S5 — Alarm-Vorschau Frontend

- **AC-20:** Given der Ortsvergleich-Hub, Reiter „Alarme" / When der Nutzer eine Alarm-Vorschau auslöst / Then zeigt `AlarmeTab` mit `context="vergleich"` die echte `AlertPreviewCard` mit Daten aus `POST /api/briefings/{id}/alert-preview?kind=vergleich` (gleicher Baustein wie im Trip), statt der statischen Beispielkarte `VTAlertSample`.
  - Test (Kern, node --test: `AlarmeTab` beide Kontexte rendern `AlertPreviewCard`, Body-Bau je kind; Live: Playwright Staging). Datei: `frontend/src/lib/components/alerts-tab/__tests__/alertPreviewKind.test.ts`.
  - Scheibe: S5

- **AC-21:** Given das Frontend / When S5 abgeschlossen ist / Then ist `VTAlertSample` (Kommentar „kein Live-Preview-Datenmodell für Vergleiche") entfernt oder ohne Verwendung gelöscht, und `AlertPreviewCard` ist im Vergleich für einen Nutzer mit zwei Orten und einer Regel mit echtem Ergebnis sichtbar (Zeitlimit 40 s unverändert).
  - Test (Kern: nirgends mehr importiert, `AlarmeTab`-Rendering ohne statische Karte; Live: Playwright). Datei: `frontend/src/lib/components/alerts-tab/__tests__/alertPreviewKind.test.ts`, `frontend/src/lib/__tests__/apiZeitlimit.test.ts`.
  - Scheibe: S5

### AC-Zuordnung

| Scheibe | ACs |
|---|---|
| S1 | AC-1 bis AC-7 |
| S2 | AC-8 bis AC-11 |
| S3 | AC-12 bis AC-15 |
| S4 | AC-16 bis AC-19 |
| S5 | AC-20, AC-21 |

## Test Plan

Die Testzuordnung je AC steht an der jeweiligen AC (Zeile „Test"). Übersicht der Dateien:

| Schicht | Dateien | ACs |
|---|---|---|
| Kern, Python | `tests/integration/test_briefing_preview_bundle.py`, `tests/integration/test_briefing_preview_user_isolation.py`, `tests/integration/test_alert_preview_kind_isolation.py`, `tests/tdd/test_alert_preview_compare_paritaet.py`, `tests/test_api_contract_drift.py` | AC-1, AC-2, AC-4, AC-7, AC-16 bis AC-19 |
| Kern, Go | `internal/handler/briefing_preview_test.go`, `internal/handler/briefing_alert_preview_test.go`, `internal/handler/preview_proxy_test.go`, `internal/router/preview_proxy_targets_test.go` | AC-1, AC-3 bis AC-6, AC-16 |
| Kern, Frontend (`node --test`) | `shared/__tests__/previewTab.test.ts`, `shared/__tests__/previewLoader.test.ts`, `molecules/__tests__/issue_578_molecules_organisms.test.ts`, `alerts-tab/__tests__/alertPreviewKind.test.ts`, `lib/__tests__/apiZeitlimit.test.ts` | AC-8 bis AC-15, AC-20, AC-21 |
| Live (Playwright gegen Staging, migriert bzw. neu) | `preview-tab-gleiche-anordnung.spec.ts`, `langlaeufer-zeitbudget-wirkort.spec.ts`, `email-preview-header.spec.ts`, `compare-hub-briefing-times.spec.ts`, `compare-hub-versand-inline.spec.ts`, `compare-mobile-vervollstaendigung.spec.ts` | AC-8, AC-9, AC-11 bis AC-13, AC-20 |
| Live, Mail | `email_spec_validator.py` gegen zugestellte Vergleichs-Mail (Exit 0) | AC-15 |

Mutations-Gegenprobe (Pflicht in `/50`): Vorschau-Weg vom Versand-Projektionsaufruf auf eine Kopie umbiegen (AC-17 bis AC-19 müssen rot werden), `kind`-Prüfung entfernen (AC-3), Client-`user_id` durchreichen (AC-4), zweiten Abruf beim Kanalwechsel einbauen (AC-9).

## Known Limitations

- Vergleichs-Vorschau bleibt langsam (60 bis 75 s, kein Zwischenspeicher); Verbesserung ist nicht Gegenstand (#2234, #1839).
- Premium-SMS wird in der Vorschau nur als Hinweis gezeigt; kein eigenes Vorschau-Backend (wie bisher im Ortsvergleich).
- Der Trip-Standard `demoMode=true` bleibt unverändert.
- Das Vergleichs-Mail-Template bleibt compare-eigen (ADR-0023, E9).
- Die amtliche Alarm-Vorschau zeigt keine Entwarnungen (für eine frische Warnung gibt es keine); Parität zum Versand ist für den Fall ohne Entwarnung belegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; folgt ADR-0023 (Dispatcher `?kind=`, Templates getrennt), ADR-0011 (ein Alarm-Renderer), ADR-0003 (Anti-Spoofing `user_id`).
- **Rationale:** Das Query-Muster `?kind=` ist bestehende Entscheidung; die Abweichung vom Issue-Zielbild (Pfad-`{kind}`) ist eine Angleichung an ADR-0023, keine Aufhebung.

## Changelog

- 2026-10-22: Spec durch #1743 abgelöst (Reiter Vorschau entfällt ersatzlos, Endpoint `GET /api/briefings/{id}/preview` zurückgebaut); AC-8 und AC-9 als abgelöst markiert, Kopf-Hinweis ergänzt.
- 2026-10-19: Initiale Spec (Issue #2283, Epic #2345 P3), 21 ACs in 5 Scheiben
- 2026-10-19: Umsetzung dokumentiert (zusätzliche Dateien, Begründung Pendant-Sperre, AC-6-Abbild, Known Limitation Entwarnung); ACs unverändert
