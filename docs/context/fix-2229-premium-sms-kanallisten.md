# Kontext: fix-2229-premium-sms-kanallisten

Issue #2229 — Vier-Kanal-Parität: Dreier-Kanallisten ohne `premium_sms` (Epic #1676).
Basis: `origin/main` `5ec28b86`. Befund auch im Ticket: https://github.com/henemm/gregor_zwanzig/issues/2229#issuecomment-5934882033

## Analysis

### Type
Bug

### Grundsatz (belegt)
Premium-SMS hat **keine eigene Metrik- oder Layout-Auswahl**, sie verschickt den fertig gerenderten SMS-Text:
- Trip: `src/services/notification_service.py:651-659` (`PremiumSmsOutput.send(body=report.sms_text …)`)
- Vergleich: `src/services/scheduler_dispatch_service.py:637` rendert mit `enabled_metrics_by_channel["sms"]`, danach `notification_service.py:1339-1366` an die Premium-SMS-Senke

Folge: Listen für **Metriken/Layout** sind zu Recht dreistellig (ADR-0049), Listen der **Versand-Kanäle** müssen vierstellig sein.

### Echte Lücken (für den Nutzer sichtbar)
1. **Kanalanzeige im Vergleich:** `frontend/src/lib/components/compare/subscriptionHelpers.ts:245-250` `presetChannels()` liest `send_premium_sms` nicht. Betroffen sind die Kachel (`CompareTile.svelte:65`), die Hub-Stat „Kanäle“ (`channelNamesLabel`) und `previewConfiguredChannels` (`CompareTabs.svelte:555`). Das Trip-Pendant `frontend/src/routes/_home/cockpitHelpers.ts:142-144` zeigt „Premium-SMS“ an. Das Feld ist da: `types.ts:678`, Go `internal/model/compare_preset.go:99` (omitempty).
2. **„Jetzt senden“-Meldung:** `frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts:82-83` schreibt „Geht an E-Mail · Telegram · SMS“ ohne Premium-SMS. Der Sofort-Versand verschickt aber tatsächlich Premium-SMS: `routes/compare/+page.svelte:162` → `POST /api/compare/presets/{id}/send` → `api/routers/scheduler.py:298` → `scheduler_dispatch_service.py:659` → `notification_service.py:1339-1366`, Gate `src/services/compare_alert_channels.py:57-61` (Opt-in + `premium_sms_allowed`). Die Zustellbarkeit prüft der vorhandene Helfer `versand-tab/premiumSmsChannelState.ts` (`disabled`, `contactLabel`). `channelConnectionStatus()` bleibt unverändert.
3. **Vorschau-Umschalter im Vergleich:** `frontend/src/lib/components/molecules/CompareChannelSwitch.svelte:19` hat keinen Premium-SMS-Reiter. Ihr Inhalt wäre identisch mit SMS.

### Bewusst dreistellig (Metrik/Layout, korrekt, Begründung fehlt)
- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:500`
- `frontend/src/lib/components/shared/layout-tab/channelLayoutsDirty.ts:35`
- `frontend/src/lib/components/shared/layout-tab/ltChannels.ts:71`, `:118`
- `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts:113`, `:166`
- `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:29` (Begründung vorhanden, ADR-0049-Marke ergänzen)
- `src/services/report_config_resolver.py:338` (Code korrekt; der Kommentar bei :205-206 ist veraltet, weil Premium-SMS seit #2275 auch im Vergleich Briefing-Kanal ist)
- `frontend/src/lib/components/trip-detail/briefingChannelGating.ts`: Metrik-Sichtbarkeit (`display_config.channels`), keine Versandliste. Prüfpunkt: `syncSendFlags` (:46-58) setzt `send_x` aus, wenn der Metrik-Kanal aus ist. Premium-SMS hängt am SMS-Inhalt. In der Spec mit ADR-0049 und der Spec feat_2277 klären, ob `send_premium_sms` mitfallen muss, wenn der SMS-Metrik-Kanal aus ist.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/compare/subscriptionHelpers.ts | MODIFY | `presetChannels` + „Premium-SMS“, Docstring |
| frontend/src/lib/components/compare/__tests__/… | MODIFY/CREATE | Verhaltenstest presetChannels/channelNamesLabel |
| frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts | MODIFY | Premium-SMS-Ziel über `premiumSmsChannelState(p).disabled` |
| frontend/src/lib/components/shared/versand-tab/__tests__/sendTargetLabel.test.ts | MODIFY | Fälle: Opt-in an+zustellbar / an+gesperrt / aus |
| frontend/src/lib/components/molecules/CompareChannelSwitch.svelte bzw. compare/CompareTabs.svelte | MODIFY | Hinweis am SMS-Reiter, wenn Premium-SMS aktiv ist („gleicher Text“) + Marke |
| 7 Metrik-/Layout-Dateien (oben) | MODIFY | Nur Kommentar `ADR-0049` mit Begründung |
| src/services/report_config_resolver.py | MODIFY | Marke + veralteten Kommentar :205-206 korrigieren |
| tests/test_adr0049_kanalliste_ratsche.py | CREATE | Grep-Ratsche (`# doc-compliance-test`) |
| docs/reference/gates_und_ratschen.md | MODIFY | Ratschen-Eintrag + Prüfdatum (Regel-Budget) |

### Scope Assessment
- Files: ~12–14 (davon 8 nur Kommentare)
- Estimated LoC: ca. +120/−5 inkl. Tests (produktiv deutlich unter 250)
- Risk Level: LOW. Nur Anzeige- und Kommentar-Änderungen, kein Eingriff in Versand oder Persistenz.

### Technical Approach
1. Ratsche zuerst (RED): pytest scannt `frontend/src`, `src`, `api` (ohne Tests und `node_modules`) nach Literal-Listen `['email','telegram','sms']` bzw. `("email","telegram","sms")` ohne `premium_sms`. Ein Treffer ist erlaubt, wenn die Zeile oder die Zeile davor `ADR-0049` enthält. Dazu ein Selbsttest (unmarkiert ⇒ Fund, markiert ⇒ kein Fund). Stilvorbild `tests/test_adr_index_drift.py`, `tests/test_mail_recipient_parity.py`. Kein Eintrag in `ci_tdd_excludes`.
2. Marken und Begründungen an die 9 bewusst dreistelligen Literale. Den veralteten Kommentar im Resolver korrigieren.
3. `presetChannels` um Premium-SMS erweitern (Muster `cockpitHelpers.ts:144`).
4. `sendTargetLabel` um Premium-SMS erweitern (`SendTargetChannels` + `send_premium_sms`; Bedingung `!premiumSmsChannelState(p).disabled`).
5. Vorschau: kein vierter Reiter (würde Typ, Preview-Endpoint und Labels ohne Informationsgewinn erweitern). Stattdessen ein Hinweis am SMS-Reiter, wenn Premium-SMS aktiv ist: „Premium-SMS versendet denselben Text“. Die Trip-Vorschau (`PreviewCard.svelte`) hat keinen Kanal-Umschalter, die Code-Teilung bleibt also unberührt.

### Dependencies
- `premiumSmsChannelState.ts` (vorhanden, unverändert)
- Bekannte Grenze der Ratsche: Listen in Objekt-Form oder mit anderer Reihenfolge erkennt sie nicht (im Docstring nennen)

### Open Questions
- [ ] `briefingChannelGating.syncSendFlags`: Soll `send_premium_sms` mitfallen, wenn der SMS-Metrik-Kanal aus ist? Technisch klären (ADR-0049, Spec feat_2277), keine PO-Frage.
- [ ] Prüfen, ob Tests oder e2e-Specs den Text „Geht an …“ oder die Kanal-Label wörtlich erwarten (`grep -rn "Geht an\|channelNamesLabel" frontend`).
- [ ] Tests, die die Dreierliste festschreiben (`ltChannels.test.ts:58`, `issue_578_molecules_organisms.test.ts:266`): bleiben gültig, weil Metrik/Layout dreistellig bleibt.
