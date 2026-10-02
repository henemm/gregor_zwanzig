---
entity_id: fix_2229_premium_sms_kanallisten
type: bugfix
created: 2026-10-01
updated: 2026-10-01
status: draft
workflow: fix-2229-premium-sms-kanallisten
tags: [premium-sms, kanaele, vierkanal-paritaet, adr-0049, ratsche, issue-2229, epic-1676]
---

# Fix #2229: Vier-Kanal-Parität — Dreier-Kanallisten ohne `premium_sms`

## Approval

- [ ] Approved

## Purpose

Premium-SMS (Garmin inReach) ist laut ADR-0049 ein vierter, gleichrangiger Kanal. Im Ortsvergleich
fehlt er aber in drei Anzeigen: Die Kanal-Anzeige (Kachel, Hub-Stat „Kanäle") nennt ihn nicht, der
„Jetzt senden"-Dialog sagt „Geht an E-Mail · Telegram · SMS", obwohl der Sofort-Versand auch
Premium-SMS verschickt, und die Vorschau lässt offen, was Premium-SMS sendet. Gleichzeitig sind
acht Metrik-/Layout-Literale **zu Recht** dreistellig, tragen aber keine Begründung — so sieht jede
künftige Dreierliste wie ein Versehen aus oder wird „aus Versehen" auf vier erweitert. Diese Spec
repariert die drei Anzeigen, markiert die bewussten Dreierlisten mit `ADR-0049` und verankert die
Unterscheidung durch eine Ratsche.

**Grundsatz (am Code belegt):** Premium-SMS hat keine eigene Metrik- oder Layout-Auswahl, sie
verschickt den fertig gerenderten SMS-Text (Trip: `src/services/notification_service.py:651-659`;
Vergleich: `src/services/scheduler_dispatch_service.py:637` rendert mit
`enabled_metrics_by_channel["sms"]`, danach `notification_service.py:1339-1366`). Daraus folgt:
Listen für **Metriken/Layout** bleiben dreistellig, Listen der **Versand-Kanäle** müssen vierstellig
sein.

## Source

- **Schicht:** Frontend (SvelteKit) + Python-Kommentar + Repo-Test
- **File:** `frontend/src/lib/components/compare/subscriptionHelpers.ts`
- **Identifier:** `function presetChannels` (Hauptfehler); weitere Stellen siehe Scope

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0049-premium-sms-vierter-kanal.md` | ADR | Folgepflicht: neue Kanal-Mengen führen `premium_sms` mit oder begründen, warum nicht |
| `frontend/src/lib/components/shared/versand-tab/premiumSmsChannelState.ts` | Modul | Zustellbarkeit (`disabled`) der Premium-SMS aus dem Konto-Profil; bleibt unverändert |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` | Modul | Zustände E-Mail/Telegram/SMS; bleibt unverändert |
| `frontend/src/routes/_home/cockpitHelpers.ts` (:142-144) | Modul | Trip-Pendant, das „Premium-SMS" bereits anzeigt — Vorbild |
| `src/services/compare_alert_channels.py` (:57-61) | Modul | Versand-Gate (Opt-in + `premium_sms_allowed`), wird nicht geändert, ist Wahrheitsquelle für AC-2 |
| `frontend/src/lib/types.ts` (:678), `internal/model/compare_preset.go` (:99) | Typ/Modell | Feld `send_premium_sms` existiert bereits, keine Schema-Änderung |
| `tests/test_adr_index_drift.py`, `tests/test_mail_recipient_parity.py` | Test | Stilvorbild für die Ratsche |
| `docs/reference/gates_und_ratschen.md` | Doku | Ratschen-Eintrag mit Prüfdatum (Regel-Budget) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/compare/subscriptionHelpers.ts | MODIFY | `presetChannels` ergänzt „Premium-SMS"; Docstring; neuer reiner Helfer für den Vorschau-Hinweis |
| frontend/src/lib/components/shared/versand-tab/sendTargetLabel.ts | MODIFY | `SendTargetChannels` + `send_premium_sms`; Ziel „Premium-SMS" bei an + zustellbar |
| frontend/src/lib/components/compare/CompareTabs.svelte | MODIFY | Reicht `premiumSmsPreviewNote(preset, channel)` als Prop `note` an den Umschalter durch |
| frontend/src/lib/components/molecules/CompareChannelSwitch.svelte | MODIFY | Neue optionale Prop `note`, rendert den Hinweis neben den Reitern; Marke `ADR-0049` (kein vierter Reiter, Begründung) |
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | MODIFY | Nur Kommentar: Marke `ADR-0049` an Zeile 500 |
| frontend/src/lib/components/shared/layout-tab/channelLayoutsDirty.ts | MODIFY | Nur Kommentar: Marke `ADR-0049` an Zeile 35 |
| frontend/src/lib/components/shared/layout-tab/ltChannels.ts | MODIFY | Nur Kommentar: Marke `ADR-0049` an Zeile 71 und 118 |
| frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts | MODIFY | Nur Kommentar: Marke `ADR-0049` an Zeile 113 und 166 |
| frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts | MODIFY | Nur Kommentar: bestehende Begründung um Marke `ADR-0049` ergänzen (Zeile 29) |
| src/services/report_config_resolver.py | MODIFY | Marke `ADR-0049` an Zeile 338; veralteten Kommentar Zeile 205-206 korrigieren |
| frontend/src/lib/components/compare/__tests__/compare_preset_channels_premium_sms.test.ts | CREATE | Verhaltenstest `presetChannels`/`channelNamesLabel` mit Premium-SMS |
| frontend/src/lib/components/compare/__tests__/compare_preview_premium_sms_hinweis.test.ts | CREATE | Verhaltenstest des Vorschau-Hinweis-Helfers + serverseitiges Rendern (SSR) des echten `CompareChannelSwitch` |
| frontend/src/lib/components/shared/versand-tab/__tests__/sendTargetLabel_premium_sms.test.ts | CREATE | Verhaltenstest „Geht an …" mit Premium-SMS (an+zustellbar / an+gesperrt / aus), zwei Profile |
| tests/test_adr0049_kanalliste_ratsche.py | CREATE | Grep-Ratsche (`# doc-compliance-test`) mit Selbsttest |
| docs/reference/gates_und_ratschen.md | MODIFY | Ratschen-Eintrag, Prüfdatum 2026-12-30 |

Bewusst **nicht** im Scope: `briefingChannelGating.ts` (siehe Entscheidung unten), alle Alarm-Kanal-
Listen (bereits vierstellig, #1701), Go-Modell, Persistenz.

### Estimated Changes

- Files: 16 (davon 8 reine Kommentar-Änderungen, 5 Tests/Doku)
- LoC: +190/-6 gesamt; produktiv (ohne Kommentare, Tests, Doku) ca. +35, deutlich unter dem Limit von 250

## Implementation Details

**1. `presetChannels()`.** Nach `send_sms` kommt `if (preset.send_premium_sms === true) result.push('Premium-SMS')`
(Muster `cockpitHelpers.ts:142-144`). Wirkt automatisch auf `CompareTile.svelte:65`, die Hub-Stat „Kanäle"
(`channelNamesLabel`), die Listenspalte in `routes/compare/+page.svelte:92` und `CompareStatusRow.svelte`.
Anzeige folgt dem **Opt-in** (wie bei Telegram/SMS), nicht der Zustellbarkeit: Kachel und Hub zeigen, was
der Nutzer eingeschaltet hat — genau wie das Trip-Pendant (`cockpitHelpers.ts:142-144`, `heroKanaele`), das
Premium-SMS ebenfalls allein am Opt-in anzeigt. Der Unterschied zu „Jetzt senden" (2.) ist **gewollt**:
Kachel/Hub zeigen die **Einstellung**, „Jetzt senden" nennt die **tatsächlichen Empfänger dieses Versands**.
Eine gesperrte Premium-SMS ist an der Kachel weiterhin als eingestellt sichtbar; dass sie gerade nicht
zustellbar ist, meldet der Versand-Tab über `premiumSmsChannelState` (`contactLabel`). `previewConfiguredChannels` (`CompareTabs.svelte:555`) projiziert die
Anzeige-Namen auf Kleinschreibung; der Eintrag `premium-sms` kommt im Umschalter nicht vor und ist dort
wirkungslos (kein vierter Reiter, siehe 3.).

**2. `sendTargetLabel()`.** Im Zusatzkanal-Block kommt hinzu:
`send_premium_sms === true && !premiumSmsChannelState(p).disabled` ⇒ Ziel „Premium-SMS" (nach „SMS").
Damit gilt: an + zustellbar ⇒ genannt; an + gesperrt (Tarif/Rückadresse fehlt oder verfallen) ⇒ **nicht**
genannt, weil der Versand-Gate (`compare_alert_channels.py:57-61`) sie ohnehin sperrt und eine Falschaussage
wie in #1471 entstünde; aus ⇒ nicht genannt. Die Zustandslogik wird **nicht** neu abgeleitet, sondern
vom vorhandenen `premiumSmsChannelState` übernommen (Default-Fehler wäre eine dritte Kopie).
`channelConnectionStatus()` bleibt unverändert.

**3. Vorschau.** Kein vierter Reiter in `CompareChannelSwitch`: Premium-SMS hat keinen eigenen Inhalt, ein
Reiter würde Typ, Preview-Endpoint und Labels ohne Informationsgewinn erweitern. Stattdessen liefert ein
reiner Helfer in `subscriptionHelpers.ts` (z. B. `premiumSmsPreviewNote(preset, channel)`) den Text
„Premium-SMS versendet denselben Text", genau dann wenn der gewählte Reiter `sms` ist und
`preset.send_premium_sms === true`; sonst leer. `CompareTabs.svelte` reicht ihn als Prop `note` an
`CompareChannelSwitch` durch; der Umschalter rendert ihn bei nicht-leerem `note` neben den Reitern
(`data-testid="compare-preview-premium-sms-note"`). So ist das sichtbare Element per SSR-Render der echten
Komponente prüfbar; die Verdrahtung in `CompareTabs` prüft der Staging-Schritt (siehe Testplan). Die Trip-Vorschau (`PreviewCard.svelte`) hat keinen
Kanal-Umschalter; die Trip/Vergleich-Code-Teilung bleibt unberührt, kein Trip-Pendant nötig.

**4. Marken.** Jedes der bewusst dreistelligen Literale erhält einen Kommentar der Form
`// ADR-0049: nur Metrik-/Layout-Kanäle — Premium-SMS hat keine eigene Auswahl, sie sendet den SMS-Text`
(bei `compareChannelMetricLayouts.ts` ergänzt die Marke die vorhandene Begründung). Auch
`CompareChannelSwitch.svelte:19` (Vorschau-Reiter) trägt die Marke mit der Begründung aus 3.
Im Resolver wird der veraltete Kommentar korrigiert: Premium-SMS ist seit #2275 im Vergleich
**Briefing-Kanal**, hat aber keine eigene Metrik-Auswahl (sendet den SMS-Text); deshalb kennt dieses
Objekt strukturell nur drei Keys. Kein Verhalten ändert sich.

**5. Ratsche `tests/test_adr0049_kanalliste_ratsche.py`** (`# doc-compliance-test`). Scannt Dateien unter
`frontend/src`, `src`, `api` (ohne `node_modules`, ohne Test-Dateien/-Ordner `__tests__`, `*.test.ts`,
`test_*.py`) nach Literal-Listen mit den drei Kanälen in dieser Reihenfolge
(`['email', 'telegram', 'sms']`, `("email", "telegram", "sms")`, beliebige Anführungszeichen/Leerzeichen)
**ohne** `premium_sms` in derselben Liste. Ein Fund ist erlaubt, wenn die Fundzeile oder die Zeile davor
`ADR-0049` enthält. Die Fundmenge wird gegen leer geprüft; Ausnahmen werden nicht in einer Liste
geführt, sondern an der Stelle markiert. Selbsttest: ein synthetischer Text mit unmarkierter Dreierliste
ergibt einen Fund, derselbe Text mit `ADR-0049`-Marke ergibt keinen. **Bekannte Grenze (im Docstring):**
Listen in Objekt-Form, mit anderer Reihenfolge, über mehrere Zeilen verteilt oder aus Variablen
zusammengesetzt erkennt die Ratsche nicht. Kein Eintrag in `ci_tdd_excludes`. Eintrag in
`docs/reference/gates_und_ratschen.md` mit Prüfdatum **2026-12-30** (Regel-Budget: kein nachweisbarer
Fang bis dahin ⇒ Rückbau).

### Entscheidung zu `briefingChannelGating.syncSendFlags` (:46-58): keine Änderung

`send_premium_sms` fällt **nicht** mit, wenn der SMS-Metrik-Kanal aus ist. Begründung:

1. **Toter Pfad:** `syncSendFlags` wirkt nur, wenn `EditReportConfigSection` die Prop `weatherChannels`
   bekommt. Kein Aufrufer im Frontend übergibt sie (Grep über `frontend/src` ohne Treffer). Eine Änderung
   wäre ohne Wirkung und nicht beweisbar. Dasselbe hat `fix_2422_s3_kanal_an_aus_kette.md` (Zeile 630)
   festgestellt und als Nebenbefund geführt.
2. **Produktvorgabe:** `fix_1738_trips_new_versand_tab.md` (PO-Entscheid E1) entkoppelt die Versand-Kanäle
   von den Wetter-Metrik-Kanälen ausdrücklich: das `weatherChannels`-Gating entfällt auf `/trips/new`
   ersatzlos; der Test `trip_new_versandkanaele_unabhaengig_von_metriken.test.ts` bewacht das. Ein Mitfallen
   von `send_premium_sms` wäre die Wiedereinführung genau dieser Kopplung für einen Kanal.
3. **ADR-0049:** Die Folgepflicht betrifft Stellen, die ein **Kanal-Set auflösen**. `syncSendFlags` löst
   keines auf, sondern spiegelt Metrik-Sichtbarkeit in Versandflags; sein Verhalten für `send_x` bleibt
   hier unberührt. Die Lücke ist latent und bleibt als Sammel-Eintrag in #1199 (bereits dort geführt).

## Test Plan

Alle Tests sind Verhaltenstests ohne Mocks, im Kern deterministisch. Frontend: `node --test` (kein Vitest);
Python: pytest. Testdateien heißen nach Verhalten.

### Automated Tests (TDD RED)

- [ ] Test 1 (`compare_preset_channels_premium_sms.test.ts`): GIVEN ein Preset mit `send_premium_sms: true`
  WHEN `presetChannels` und `channelNamesLabel` aufgerufen werden THEN enthält die Liste „Premium-SMS" nach
  „SMS" und das Label endet auf „· Premium-SMS". Gegenprobe: ohne Flag bzw. mit `false` kein Eintrag.
- [ ] Test 2 (`sendTargetLabel_premium_sms.test.ts`): GIVEN ein Profil mit bestätigter E-Mail,
  `premium_sms_allowed: true`, `premium_sms_reply_state: 'fresh'` und ein Preset mit `send_premium_sms: true`
  WHEN `sendTargetLabel` aufgerufen wird THEN nennt der Text „Premium-SMS"; GIVEN dasselbe Preset aber
  `premium_sms_reply_state: 'stale'` bzw. `premium_sms_allowed: false` THEN nennt er sie nicht; GIVEN
  `send_premium_sms: false` THEN nennt er sie nicht.
- [ ] Test 3 (`sendTargetLabel_premium_sms.test.ts`): GIVEN zwei verschiedene Nutzerprofile (A zustellbar,
  B gesperrt) und dasselbe Preset WHEN `sendTargetLabel` je Profil aufgerufen wird THEN unterscheiden sich
  die Texte genau um „Premium-SMS" (kein Durchschlagen des einen Profils auf das andere).
- [ ] Test 4 (`compare_preview_premium_sms_hinweis.test.ts`): GIVEN ein Preset mit `send_premium_sms: true`
  WHEN der Hinweis für den Reiter `sms` abgefragt wird THEN lautet er „Premium-SMS versendet denselben Text";
  für `email`/`telegram` und bei `send_premium_sms` aus ist er leer.
- [ ] Test 4b (`compare_preview_premium_sms_hinweis.test.ts`, SSR): GIVEN der echte `CompareChannelSwitch`
  serverseitig gerendert (`svelte/server` `render`, Hooks `frontend/test-svelte-ssr-hooks.mjs`, Muster
  `compare_channel_display_from_flags.test.ts`) mit `active='sms'` und `note="Premium-SMS versendet denselben Text"`
  WHEN das HTML ausgewertet wird THEN enthält es genau ein Element `compare-preview-premium-sms-note` mit diesem
  Text und genau drei Reiter; GIVEN `note` leer THEN fehlt das Element.
- [ ] Test 5 (`tests/test_adr0049_kanalliste_ratsche.py`, Haupttest): GIVEN der aktuelle Stand von
  `frontend/src`, `src`, `api` WHEN nach unmarkierten Dreier-Kanallisten gesucht wird THEN ist die Fundmenge
  leer; vor der Markierung (RED) enthält sie die acht bekannten Metrik-/Layout-Literale plus `CompareChannelSwitch.svelte`.
- [ ] Test 6 (`tests/test_adr0049_kanalliste_ratsche.py`, Selbsttest): GIVEN ein synthetischer Text mit
  `['email', 'telegram', 'sms']` WHEN er ohne Marke geprüft wird THEN gibt es einen Fund; GIVEN derselbe Text
  mit `ADR-0049` in der Zeile davor bzw. derselben Zeile THEN keinen; GIVEN eine Vierer-Liste mit
  `premium_sms` THEN keinen.

**Bestehende Tests (geprüft):**

- AC-8 wird von einem **bestehenden** Test bewacht, keine neue Datei nötig:
  `trip_new_versandkanaele_unabhaengig_von_metriken.test.ts` (`premium_sms_zeile_ueberlebt_abgewaehlten_wetterkanal_sms`,
  `premium_sms_schaltbarkeit_haengt_nicht_an_der_metrik_auswahl`). Er muss in `/40` unverändert grün bleiben und
  wird im RED-Bericht als AC-8-Nachweis aufgeführt.

- `ltChannels.test.ts:58` und `issue_578_molecules_organisms.test.ts:266` schreiben die Dreierliste für
  Metrik/Layout fest — bleiben **unverändert gültig**, weil Metrik/Layout dreistellig bleibt.
- `compare_preset_channels.test.ts`, `compare_channel_display_from_flags.test.ts`, `issue_582_list_helpers.test.ts`,
  `channel_names_label.test.ts`, `issue_647_home_fidelity.test.ts` bauen ihre Presets ohne
  `send_premium_sms`; die Erwartungen bleiben gültig. Beim Lauf gegenlesen: keiner darf `send_premium_sms`
  im Fixture führen oder die Liste mit `deepEqual` auf eine feste Länge prüfen.
- `sendTargetLabel.test.ts` (inkl. AC-6-Schleife über `['email','telegram','sms']`) und
  `compare_send_dialog_target.test.ts` erwarten „Geht an …" für Presets ohne Premium-SMS; bleiben gültig.
  Die AC-6-Schleife prüft nur die drei Verbindungs-Kanäle und braucht keine Anpassung.
- `frontend/e2e/kanal-grenzen-ortsvergleich.staging.spec.ts:81` nennt `presetChannels` nur im Kommentar;
  keine Anpassung. Keine e2e-Spec erwartet den Text „Geht an" wörtlich.

### Staging-Verifikation (`/e2e-verify`)

- Auf Staging einen Vergleich mit eingeschalteter Premium-SMS öffnen: Kachel und Hub-Stat „Kanäle" nennen
  „Premium-SMS" (AC-1); in der Vorschau den SMS-Reiter wählen ⇒ Element `compare-preview-premium-sms-note`
  sichtbar, beim E-Mail-Reiter nicht (AC-3, Verdrahtung in `CompareTabs`); „Jetzt senden"-Dialog öffnen und
  den Text „Geht an …" gegen den Premium-SMS-Zustand des Kontos ablesen (AC-2).

## Acceptance Criteria

- [ ] **AC-1:** Given ein Ortsvergleich, bei dem der Nutzer Premium-SMS als Versandkanal eingeschaltet hat / When die Vergleichs-Kachel oder die Hub-Übersicht „Kanäle" angezeigt wird / Then steht dort „Premium-SMS" neben den übrigen eingeschalteten Kanälen, und bei ausgeschaltetem Premium-SMS steht es nicht dort.
- [ ] **AC-2:** Given ein Nutzer mit zustellbarer Premium-SMS (Tarif Premium, Rückadresse frisch) und einem Vergleich mit eingeschaltetem Premium-SMS / When er „Jetzt senden" öffnet / Then nennt der Bestätigungstext „Premium-SMS" als Ziel; ist die Premium-SMS eingeschaltet, aber nicht zustellbar (Tarif, nie gemeldet oder verfallen), oder ausgeschaltet, wird sie nicht genannt.
- [ ] **AC-3:** Given ein Ortsvergleich mit eingeschalteter Premium-SMS / When der Nutzer in der Vergleichs-Vorschau den SMS-Reiter wählt / Then erscheint daneben der Hinweis „Premium-SMS versendet denselben Text", und es gibt keinen vierten Reiter; bei E-Mail, Telegram oder ausgeschalteter Premium-SMS erscheint der Hinweis nicht.
- [ ] **AC-4:** Given die bewusst dreistelligen Metrik-/Layout-Listen im Frontend und im Resolver / When ein Entwickler eine davon liest / Then trägt sie die Marke `ADR-0049` mit Begründung (Premium-SMS hat keine eigene Metrik-Auswahl), und der Kommentar im Resolver nennt Premium-SMS nicht mehr fälschlich als reinen Alarm-Kanal.
- [ ] **AC-5:** Given der Quelltext unter `frontend/src`, `src` und `api` / When `uv run pytest tests/test_adr0049_kanalliste_ratsche.py` läuft / Then ist die Fundmenge unmarkierter Dreier-Kanallisten leer, und der Selbsttest beweist, dass eine unmarkierte Liste einen Fund erzeugt und eine markierte keinen.
- [ ] **AC-6:** Given ein Preset ohne Premium-SMS oder ein Konto ohne Premium-Tarif / When Kanal-Anzeige und „Geht an …"-Text erzeugt werden / Then bleiben sie byte-gleich zum bisherigen Stand (keine Regression für drei Kanäle, bestehende Tests grün).
- [ ] **AC-7:** Given zwei verschiedene Nutzer mit unterschiedlichem Premium-SMS-Zustand / When der Bestätigungstext je Nutzer erzeugt wird / Then richtet sich jeder Text nur nach dem Profil des jeweiligen Nutzers.
- [ ] **AC-8:** Given der Trip-Editor mit abgeschaltetem SMS-Metrik-Kanal / When die Versandkanäle gespeichert werden / Then bleibt `send_premium_sms` unverändert (keine Kopplung, `syncSendFlags` unberührt).

## Changelog

- 2026-10-01: Initial spec created (Issue #2229, Epic #1676)
- 2026-10-01: Briefing-Befunde eingearbeitet — Hinweis wird im `CompareChannelSwitch` gerendert und per SSR geprüft, Staging-Schritt für die Verdrahtung, AC-8-Nachweis über bestehenden Test, Opt-in-Anzeige vs. „Jetzt senden" als gewollter Unterschied begründet.
