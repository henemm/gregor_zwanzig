# Context: feat-2283-vorschau-baustein

Issue #2283 · Epic #2345 Etappe P3 (Rest nach #2278) · gemessen auf `origin/main` @ `500734951` (2026-10-19)

## Request Summary
Trip- und Ortsvergleich-Hub sollen **einen** geteilten Vorschau-Reiter (`shared/PreviewTab` mit `context`) bekommen, der E-Mail-iframe, SMS-Telefonrahmen und Telegram-Blase für beide rendert; dahinter eine kind-neutrale Preview-API (Alt-Routen als Delegates, toter `/signal`-Proxy weg) und eine kind-neutrale Alarm-Vorschau. Das Compare-Mail-Template selbst bleibt compare-eigen (E9, ADR-0023:32) — geteilt wird nur der Rahmen.

**Der Issue-Befund (2026-09-09) ist teilweise überholt** — die Zeilenangaben unten sind der Ist-Stand.

## Related Files

### Frontend
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | Reiter-Kennung beider Hubs ist bereits `vorschau` (#2287), Alt-Kennung `preview` → LEGACY-Map |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:212-240` (304 LoC) | Trip-Vorschau: Demo-Banner :214-226 (`demoMode` default true :114), Morgen/Abend-Radio :227-234, `<EmailIframe>` :236, `<SmsPhoneFrame>` :237. **Kein** Telegram, kein Kanalumschalter, kein Desktop/Mobil, kein Test-Senden. :93 toter PLACEHOLDER `vorschau` („#189") |
| `frontend/src/lib/components/compare/CompareTabs.svelte` (1479 LoC) | Compare-Vorschau: State/Effect :587-655 (`previewChannel`, `emailView`, ein Abruf `langlaeufer.compareVorschau`), Markup :1162-1255 (Leerfall, Test-Briefing-senden-Knopf :1174 `handleSend`, `CompareChannelSwitch` :1191 + `premiumSmsPreviewNote`, Desktop/iPhone :1199, „Kanal nicht konfiguriert" :1206, eigenes `iframe srcdoc` :1224-1232, `CompareChatBubble` :1238, `CompareSmsPreview` :1243). Zweiter Senden-Knopf :1152 (mobil, #2580) |
| `frontend/src/lib/components/preview/EmailIframe.svelte` (53), `SmsPhoneFrame.svelte` (109), `previewHelpers.ts` (57), `index.ts` | Trip-Bausteine, fetchen selbst per `buildPreviewUrl(channel)` → `GET /api/preview/{tripId}/{channel}?type&date&demo=1`. Einziger Importeur TripTabs:19 |
| `frontend/src/lib/components/molecules/CompareChannelSwitch` (75), `CompareChatBubble` (73), `CompareSmsPreview` (60) | Nur CompareTabs:15,20,21 + Barrel `molecules/index.ts:43-47` + Tests |
| `molecules/CompareBriefingPreview` (30), `ComparePreviewMissing` (23) | **Produktiv tot** seit #1270 — nur Barrel + `issue_578_molecules_organisms.test.ts` |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:286` | `premiumSmsPreviewNote` |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` (187) | Alarm-Vorschau, nur in `shared/AlarmeTab.svelte:35/567` Zweig `context !== 'vergleich'`; Vergleich zeigt statisches `<VTAlertSample context="vergleich">` (:564) |
| `frontend/src/lib/api.ts:280-285` | `langlaeufer.compareVorschau` → `POST /api/preview/compare/{id}` (70 s); `langlaeufer.alarmVorschau` → `POST /api/trips/{id}/alert-preview` (40 s) |
| `frontend/src/lib/components/shared/subscriptionActions.ts:35` | Aktionsmodell (#2278) — Trip-Senden läuft hier, nicht im Vorschau-Reiter |

### Go
| Datei | Relevanz |
|---|---|
| `internal/router/router.go:268` | `POST /api/trips/{id}/alert-preview` → `AlertPreviewProxyHandler` (`internal/handler/proxy.go:318`), 30 s |
| `internal/router/router.go:270-274` | `GET /api/preview/{trip_id}/{email,sms,signal,telegram}` → `PreviewProxyHandler` (`preview_proxy.go:72`), 30 s. **`/signal` :272-273 tot** (Python hat keinen Endpoint; `api_contract.md:246` markiert) |
| `internal/router/router.go:276` | `POST /api/preview/compare/{preset_id}` → `ComparePreviewProxyHandler` (`preview_proxy.go:34`), 60 s |
| `internal/router/router.go:292-296`, `internal/handler/briefing_subscription.go` (292) | `/api/briefings` Dispatcher (#1250 S6, ADR-0023): nur CRUD, `kind` per `?kind=route|vergleich` Pflicht (400 `kind_required`), `ValidEntityID`, `bailIf` — **Vorbild** |

### Python
| Datei | Relevanz |
|---|---|
| `api/routers/preview.py` (152) | Trip GET email :30 / sms :56 / telegram :129 (Param `user_id`, `type`, `date`, `demo`); Compare POST :86 (`user_id`, `date`; **kein** demo/type) → `{subject,email_html,telegram,sms,sms_char_count}` via `src/services/compare_preview_service.py` (284) |
| `src/services/preview_service.py` (427) | Trip-Vorschau-Rendering |
| `api/routers/validator.py:330-338` (548) | `alert_preview(trip_id, AlertPreviewBody, user_id)` — Body genau eines von `changes`(+`segment_times`)/`onset`/`official`/`nowcast_frames`; segmentbezogene Validierung |
| `src/services/validator_render_service.py:97` (568) | `render_alert_preview(trip_obj, body)` — komplett Trip-gebunden |
| `src/services/compare_alert.py:444`, `compare_alert_channels.py`, `compare_alert_guard.py`, `compare_official_alert.py`, `compare_radar_alert.py` | Vergleichs-Alarm-**Versand**pfad (keine Vorschau) |
| `output/renderers/alert/project.py:389/460/608` | `to_multi_point_alert_message`, `to_multi_location_onset_alert_message`, `to_point_alert_message` — von einer Compare-Alarm-Vorschau wiederzuverwenden (ADR-0011) |

## Existing Patterns
- **Kind-Dispatcher:** `/api/briefings` mit `?kind=` als Query (nie Store-Probing). Ein `{kind}` im **Pfad** (Issue-Zielbild `/api/preview/{kind}/{id}/{channel}`) wäre ein neues Muster → in Analyse entscheiden; konformer wäre `/api/briefings/{id}/preview/{channel}?kind=` bzw. `/api/briefings/{id}/alert-preview?kind=`.
- **User-Isolation Proxy:** `appendUserID(rawQuery, middleware.UserIDFromContext(...))`, Client-`user_id` verworfen (`preview_proxy.go:21-25`); Besitzprüfung erst in Python per user-scoped Loader. Go prüft bei Preview weder Besitz noch `ValidEntityID`.
- **Route-entfernt-Wächter:** `internal/router/legacy_subscription_routes_removed_test.go` — Muster für „`/signal` weg".
- **Geteilte Organismen:** `shared/` mit `context="route"|"vergleich"` (AlarmeTab, VersandTab, layout-tab, subscription-header).
- **Alarm-Render:** ein Backend-Renderer für Versand und Vorschau (ADR-0011).

## Dependencies
- Upstream: Python-Renderer (Trip-Briefing, Compare-Mail-Template E9, Alarm-Projektionen), Loader (user-scoped), Go-Middleware `UserIDFromContext`.
- Downstream: beide Hub-Reiter, `AlarmeTab`, Playwright-Specs (s. u.), `api_contract.md` (Drift-Test `tests/test_api_contract_drift.py`: jede `/api/`-Route in router.go muss in der Doku stehen; Prüfdatum 2026-10-20).

## Existing Specs
- `docs/specs/modules/preview_service.md`, `compare_channel_preview_dispatch.md` (#1270), `fix_1765_b1_compare_vorschau_parallel.md`, `fix_1765_1839_sa_vorschau_entblockung.md`, `fix_1651_vorschau_zeitfenster.md`, `fix_1727_s5c_vorschau_anzeige_ortstag.md`, `fix_1841_vorschau_metrik_tagesfenster.md`, `fix_923b_wire_live_sms_preview.md`, `alarm_pruefstrecke.md`, `issue_221_validator_observability_endpoints.md`, `fix_2140_entitaets_id_pfadsperre.md`
- `docs/reference/api_contract.md` :246 (signal tot), §20 Preview :4012ff, §22.5 Alert-Preview :4376/4389
- ADR-0023 (E9: Templates getrennt), ADR-0011 (ein Alarm-Renderer), ADR-0003 (anti-spoofing `user_id`)

## Bestehende Tests (Auswahl)
- pytest Trip: `test_epic_140_preview_endpoints`, `test_issue_363_signal_telegram_preview`, `test_preview_*` (fehlerformen, render_options_parity, parity_without_outlook, does_not_mutate_trip_data, night_block, thunder_matches_sent), `test_sms_preview_matches_sent`, `test_vorschau_*`
- pytest Compare: `test_compare_preview_service`, `test_compare_preview_user_isolation`, `test_compare_preview_hourly_parity`, `test_compare_vorschau_systemfehler`, `test_issue_464_compare_email_preview`
- pytest Alarm: `tests/integration/test_issue_918_alert_preview_4ch.py`, `test_preview_alert_preview_reject_foreign_trip_id.py`, `test_issue_221_validator_endpoints.py`, `tests/tdd/test_alert_preview_*` (7), `test_952_onset_alert_fidelity`, `test_regen_ausdehnung_vorschau`, `tests/unit/test_entity_id_path_guard.py`
- go: `internal/handler/preview_proxy_test.go` (inkl. signal :123-130), `compare_preview_proxy_test.go`
- node --test: `preview/__tests__/previewHelpers.test.ts`, `compare/__tests__/compare_preview_channel_switch.test.ts`, `compare_preview_premium_sms_hinweis.test.ts`, `alerts-tab/alertPreview*.test.ts`, `molecules/issue_578_molecules_organisms.test.ts`, `lib/__tests__/apiZeitlimit.test.ts`
- Playwright: `email-preview-header`, `compare-hub-versand-inline`, `compare-mobile-vervollstaendigung`, `compare-hub-briefing-times`, `hub-reiter-alt-kennungen-umleitung`, `langlaeufer-zeitbudget-wirkort`, `versand-tab`, `kanal-grenzen-ortsvergleich.staging`, `ausblick-einfach-wirkt.staging`, `trip-preview-thunder-origin.staging`
- **Kein** Wächter „jede Proxy-Route hat ein Python-Ziel" (AC-3 des Issues fordert ihn).

## Risks & Considerations
- **Pendant-Sperre** (`.claude/hooks/pendant_gate.py`): neues `shared/PreviewTab.svelte` freigestellt; neue Dateien unter `compare/`, `trip-detail/` würden geblockt. Löschungen und `molecules/`/`preview/` unüberwacht.
- **Datenform-Asymmetrie:** Trip = je Kanal ein GET (E-Mail HTML, SMS/Telegram JSON); Vergleich = ein POST mit allen Kanälen. Der geteilte Baustein braucht eine einheitliche Abruf-Abstraktion — entweder Server-seitig angleichen oder im Frontend adaptieren.
- **Optionen-Asymmetrie:** Trip hat `type` (Morgen/Abend) und `demo`; Vergleich hat beides nicht. Fachlich klären, was davon im Vergleich gilt.
- **Test-Senden-Knopf** im Compare-Vorschau-Reiter vs. Aktionsmodell (#2278) — Doppelung? Gehört zur Teilungsfrage.
- **Alarm-Vorschau Vergleich** ist echtes Neuland: Body-Schema ist segmentzentriert; Orts-Semantik fehlt. Riskanteste Scheibe; berührt #2261.
- **Laufzeit:** Compare-Vorschau dauert lang (Zeitlimits 60/70 s, #2234, #1839) — kein Ergebnis-Cache vorhanden; nicht verschlechtern.
- **Premium-SMS-Hinweis** (`premiumSmsPreviewNote`) darf nicht verloren gehen; laut CLAUDE.md sind alle vier Kanäle gleichrangig — Trip-Vorschau zeigt heute weder Telegram noch Premium-SMS.
- **Vergleichs-Mail:** nur Rahmen ändern, Template unverändert; trotzdem `email_spec_validator.py` im Blick (Arbeitsregel 3 Epic #2345).
- **Umfang** deutlich > 250 LoC → Scheiben. Vorschlag aus der Messung: S1 Backend-Dispatcher + `/signal` weg + Wächter · S2a `shared/PreviewTab` im Trip · S2b Compare-Hub umstellen + tote Molecules löschen · S3 Alarm-Vorschau kind-neutral (Backend) · S3b Frontend `AlertPreviewCard` statt `VTAlertSample`.
- **Multi-User:** jeder neue Endpoint mit zwei Nutzern testen; nie `"default"`.

## Analysis

### Type
Feature (Rework, Epic #2345 Etappe P3) — Teilung Trip↔Ortsvergleich, keine Fehlerbehebung.

### Zusatzmessungen (2026-10-19, `origin/main` @ `500734951`)
- **Antwortformen:** Trip-GET email → HTML; sms → `{subject, token_line, char_count}`; telegram → `{subject, body, char_count, max_line_width, bubbles?}` (`api/routers/preview.py:30/56/129`, `_narrow_payload` :114). Compare-POST → `{subject, email_html, telegram, sms, sms_char_count}` (:86).
- **Premium-SMS:** kein Vorschau-Backend kennt sie; Compare-Frontend zeigt nur `premiumSmsPreviewNote` (`compare/subscriptionHelpers.ts:286`). Trip zeigt weder Telegram noch Premium-SMS-Hinweis.
- **Bausteine:** `EmailIframe`/`SmsPhoneFrame` fetchen selbst (`buildPreviewUrl`), brauchen inhaltlich nur `html` bzw. `{token_line, char_count}` → auf Prop-Eingang umstellbar.
- **Test-Senden:** Compare-Reiter-Knöpfe (`CompareTabs.svelte:1149` testid `compare-hub-activation-testsend`, :1175) rufen `sendComparePreset` — derselbe Pfad wie der Hub-Kopf (`routes/compare/[id]/+page.svelte:228 handleTestSend`) und das Aktionsmodell (`subscriptionExec.ts:94-102`). Doppelung.
- **Morgen/Abend:** Compare-Abo hat genau einen `report_type` (`src/app/user.py:100`); `compare_preview_service.py` kennt keinen report_type → im Vergleich gibt es fachlich nichts umzuschalten. **Demo** (#483) = FixtureProvider statt Live-API, nur Trip (`preview_service.py:188`), Trip-Default `demoMode=true` (`TripTabs.svelte:114`).
- **Alarm-Versand Vergleich:** `NotificationService.send_multi_location_deviation_alert` (:1040 → `to_multi_point_alert_message` :1081), `send_multi_location_radar_alert` (:1104 → `to_multi_location_onset_alert_message` :1140), `send_multi_location_official_alert` (aus `compare_official_alert.py:340`). Aufrufer: `compare_alert.py:444`, `compare_radar_alert.py:423`, `compare_official_alert.py:340`.
- **Alarm-Vorschau Vergleich heute:** nur statische Fixtures `shared/versand-tab/VTAlertSample.svelte` (Kommentar „KL-4: kein Live-Preview-Datenmodell für Vergleiche"); Trip: `AlertPreviewCard` auf Klick → `POST /api/trips/{id}/alert-preview`.

### Entscheidungen (Tech Lead, begründet)
1. **Alarm-Vorschau Vergleich bleibt in #2283** (AC-2, PO-Regel „nie Reste abspalten"). Kopplung an #2261 Teil B wird technisch gelöst: Die Vorschau ruft **dieselben** Projektionen wie der Versand (`to_multi_point_alert_message` / `to_multi_location_onset_alert_message` / Official-Pfad, ADR-0011) — keine zweite Rendervariante; Paritätstest Vorschau↔Versandprojektion je Körperfall. #2261 als Querverweis, keine Abspaltung.
2. **API-Form = ein Aufruf, alle Kanäle, eine Antwortform, kind als Query** (ADR-0023-Muster `/api/briefings` mit `?kind=`; kein `{kind}` im Pfad — bewusste Abweichung vom Issue-Zielbild): `GET /api/briefings/{id}/preview?kind=route|vergleich[&type&date&demo]` → `{subject, email_html, sms:{text,char_count}, telegram:{body, bubbles?}}`. Begründung: Vergleich *kann* nur gebündelt (60–75 s, kein Cache — Einzelkanal-GETs würden die Laufzeit vervielfachen); Trip-Bündel ist billig (drei vorhandene Render-Funktionen in einem Python-Endpoint). So hat der geteilte Reiter genau **einen** Loader. `kind` fehlt/falsch → 400 `kind_required`; `ValidEntityID`; `appendUserID`, Client-`user_id` verworfen; Zeitlimit Go 30 s (route) / 60 s (vergleich). Alt-Routen `/api/preview/{trip_id}/{email,sms,telegram}` und `/api/preview/compare/{id}` bleiben als Delegates, `/signal` fällt (+ Wächter „jede Proxy-Route hat ein Python-Ziel", Muster `legacy_subscription_routes_removed_test.go`). Analog `POST /api/briefings/{id}/alert-preview?kind=`; `/api/trips/{id}/alert-preview` bleibt Delegate.
3. **Reiter-Anordnung (Richtung, in der Spec als AC zur Freigabe):** Kanalumschalter für **beide** (E-Mail · SMS · Telegram, Premium-SMS-Hinweis für beide), SMS **immer im Telefonrahmen** (`SmsPhoneFrame`), E-Mail mit Desktop/Mobil-Ansicht für beide, Telegram als Chat-Blase. Damit sind alle Kanäle in beiden Hubs sichtbar (vier gleichrangige Kanäle). AC-1 des Issue-Entwurfs („Anordnung wie im Trip") wird umformuliert zu „gleiche Anordnung in beiden Hubs". Kanalwechsel löst keinen neuen Abruf aus.
4. **Morgen/Abend + Demo nur bei `context="route"`** (Optionen-Prop). Gemessen: Vergleich hat einen festen `report_type`, Demo-Fixtures gibt es nur für Trips. Keine PO-Frage nötig.
5. **Test-Senden verlässt den Vorschau-Reiter** in beiden Hubs — der eine Sendeweg ist das Aktionsmodell (#2278) im Hub-Kopf (desktop `routes/compare/[id]/+page.svelte:228`, mobil #2580). Playwright `compare-hub-versand-inline` (testid `compare-hub-activation-testsend`) wird migriert, nicht still gelöscht.
6. **Alarm-Vorschau im Reiter Alarme:** `AlarmeTab` zeigt für `vergleich` die echte `AlertPreviewCard` (kind-neutral: Props `kind`, `id`, Regeln; Body-Bau für Orte statt Segmente) statt `VTAlertSample`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/router/router.go` | MODIFY | `/api/briefings/{id}/preview` + `/alert-preview` registrieren, `/signal` raus |
| `internal/handler/briefing_preview.go` | CREATE | kind-Dispatcher Preview + Alert-Preview (Muster `briefing_subscription.go`) |
| `internal/handler/preview_proxy.go`, `proxy.go` | MODIFY | gemeinsame Proxy-Logik, Alt-Routen als Delegates |
| `internal/handler/*_test.go`, `internal/router/*_test.go` | MODIFY/CREATE | Dispatcher-Tests (zwei Nutzer, kind fehlt/falsch, fremde ID), Wächter Proxy-Ziel |
| `api/routers/preview.py` | MODIFY | Trip-Bündel-Endpoint (alle Kanäle, gleiche Form wie Compare) |
| `api/routers/validator.py`, `src/services/compare_alert_preview_service.py` | MODIFY/CREATE | Compare-Alarm-Vorschau über Versand-Projektionen |
| `frontend/src/lib/components/shared/PreviewTab.svelte` | CREATE | geteilter Reiter (`context`) |
| `frontend/src/lib/components/shared/previewLoader.ts` | CREATE | ein Loader → `/api/briefings/{id}/preview?kind=` |
| `frontend/src/lib/components/preview/EmailIframe.svelte`, `SmsPhoneFrame.svelte`, `previewHelpers.ts` | MODIFY | Inhalt als Prop statt Selbst-Fetch |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Vorschau-Markup → `PreviewTab`; toter PLACEHOLDER :93 weg |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Vorschau-State :587-674 + Markup :1140-1255 → `PreviewTab` (netto Löschung) |
| `molecules/Compare{ChannelSwitch,ChatBubble,SmsPreview}` | MOVE/DELETE | Umschalter/Blase als kontext-neutrale Bausteine, SmsPreview durch `SmsPhoneFrame` ersetzt |
| `molecules/CompareBriefingPreview`, `ComparePreviewMissing` + Barrel + `issue_578_molecules_organisms.test.ts` | DELETE/MODIFY | produktiv tot |
| `alerts-tab/AlertPreviewCard.svelte`, `shared/AlarmeTab.svelte`, `shared/versand-tab/VTAlertSample.svelte` | MODIFY/DELETE | kind-neutrale Alarm-Vorschau im Vergleich |
| `frontend/src/lib/api.ts` | MODIFY | `briefingVorschau(kind,id)`, `alarmVorschau(kind,id)`; Zeitlimit 70 s (vergleich) bleibt |
| `docs/reference/api_contract.md` | MODIFY | neue Routen, `/signal` gestrichen (Drift-Test) |
| Playwright: `email-preview-header`, `compare-hub-versand-inline`, `compare-mobile-vervollstaendigung`, `compare-hub-briefing-times`, `langlaeufer-zeitbudget-wirkort`, Staging-Specs | MODIFY | Selektoren/testids migrieren |

### Scope Assessment
- Files: ~25 (ohne Tests ~15)
- Estimated LoC: produktiv ca. +700/-600 (Compare-Hub netto Löschung)
- Risk Level: **MEDIUM** — keine Mail-Templates werden angefasst, aber beide Hubs, ein neuer API-Weg und eine neue Alarm-Vorschau für den Vergleich.

### Technical Approach — Scheibenschnitt (je ≤250 LoC, ein Ticket, alle ACs in einer Spec)
| Scheibe | Inhalt | Abhängig von |
|---|---|---|
| **S1** Backend Preview | Trip-Bündel-Endpoint (Python), Go-Dispatcher `/api/briefings/{id}/preview?kind=`, `/signal` weg, Wächter, Contract | — |
| **S2** Trip-Reiter | `shared/PreviewTab` + Loader, Bausteine prop-getrieben, Telegram + Umschalter im Trip | S1 |
| **S3** Vergleichs-Reiter | `CompareTabs` → `PreviewTab`, Senden raus, tote Molecules weg (AC-4) | S2 |
| **S4** Alarm-Vorschau Backend | `POST /api/briefings/{id}/alert-preview?kind=`, Compare über Versand-Projektionen, Paritätstests | — (parallel zu S2/S3) |
| **S5** Alarm-Vorschau Frontend | `AlertPreviewCard` kind-neutral im `AlarmeTab`, `VTAlertSample` fällt | S4 |

Übersteigt eine Scheibe 250 LoC → `loc_limit_override`, nie AC streichen oder abspalten.

### Dependencies
- Upstream: Python-Renderer (unverändert), user-scoped Loader, `middleware.UserIDFromContext`, `ValidEntityID`, Versand-Projektionen `src/output/renderers/alert/project.py`.
- Downstream: beide Hub-Reiter, `AlarmeTab`, Playwright-Specs, `api_contract.md` + `tests/test_api_contract_drift.py`, `pendant_gate.py` (neue Dateien nur unter `shared/`, `preview/`, `molecules/`).
- Querverweis: #2261 Teil B (Vorschau = Versandpfad) — S4 liefert die Parität für den Vergleich von Anfang an.

### Risiken
- Pendant-Sperre: keine neuen Dateien unter `compare/` oder `trip-detail/`.
- Laufzeit Vergleich: genau ein Abruf beim Öffnen des Reiters, kein Eager-Load, Zeitlimit 70 s Frontend / 60 s Go unverändert.
- Multi-User: jeder neue Endpoint mit zwei Nutzern (fremde ID → 404, beide kinds).
- Vergleichs-Mail-Template unberührt; trotzdem `email_spec_validator.py` bei der Staging-Abnahme (Arbeitsregel 3 Epic #2345).
- Trip-Default `demoMode=true` bleibt unverändert (nicht Gegenstand dieses Tickets).

### Open Questions
- Keine offenen fachlichen Fragen. Reiter-Anordnung (Entscheidung 3) und Wegfall des Test-Senden-Knopfs im Reiter (Entscheidung 5) gehen als ACs in die Spec und damit in die PO-Freigabe.
