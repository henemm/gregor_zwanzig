# Context: Scheibe S3b — Oberfläche „Kanäle je Wettergröße" (#1895)

> Workflow `feat-1895-s3b-kanal-spalte` · Issue #1895 · Epic #2345
> Erhoben 2026-11-03, Stand `origin/main` = `df87d9f82` (S3a live, PR #2785).
> **Grundlage, weiter gültig:** `docs/context/feat-1895-s3-kanal-spalte.md` (Kernbefunde 1–6,
> Sektion `# Analysis` mit Entscheidungen E1–E10, Prod-Bestandsmessung). Dieses Dokument hält nur
> fest, was sich durch S3a geändert hat und was S3b konkret berührt.
> Spec: `docs/specs/modules/alert_metric_channels.md` (S1, S2, S3a; Scheibenschnitt `:805-811`).

## Request Summary

Seit S2 wirkt `alert_metric_channels` im Alarm-Versand, seit S3a ist der Leser gegen „Alarm erreicht
niemanden" abgesichert und die Zuordnung Alarm-Zeile → Speicherschlüssel kommt aus genau einer Quelle
(`GET /api/alert-metric-channel-keys`). Der Nutzer sieht davon nichts. S3b baut die Oberfläche:
Block „Kanäle je Wettergröße" im geteilten Alarme-Reiter (Trip, Ortsvergleich, beide Anlegemasken),
samt Speicherweg, Snapshot/Rollback, DE/EN-Texten und den Hinweisen aus S3a Known Limitations.

## Was S3a geliefert hat und S3b nutzt (Ist-Stand, gemessen)

| Baustein | Stand | Für S3b |
|---|---|---|
| `GET /api/alert-metric-channel-keys` → `{keys: {AlertMetric: [metric_id…]}, accepted: […]}` | live, Auth-Gruppe wie `/api/metrics`, nutzerunabhängig | **einzige** Quelle für Zeile → Speicherschlüssel (statt Onset-Lücke in `/api/metrics`, die E2 ursprünglich vorsah — `/api/metrics` bleibt unverändert). Frontend lädt den Endpunkt; keine zweite Liste im Frontend (Wächter #1480) |
| Leser-Rückfall nach Tier-Gates (AC-25…29) | live | Ein Eintrag „nur SMS" ohne SMS-Tarif schickt den Alarm nicht mehr ins Leere ⇒ die UI muss tarifgesperrte Kanäle nicht hart verhindern, ein Hinweis genügt (R5b aus S3-Kontext ist backendseitig geschlossen) |
| Je-Metrik-`null` = „erbt", wird persistiert; Top-Level-`null` ist No-Op in Trip **und** Ortsvergleich (AC-36…38) | live | „Wieder erben" = Senden von `{metric_id: null}`. Kein Risiko mehr, dass ein Top-Level-`null` des Ortsvergleichs die Map löscht |
| Keine Go-Schreibvalidierung der Schlüssel | bewusst | UI darf nur Schlüssel aus `accepted` schreiben; Bestandsschlüssel außerhalb (z. B. `snowfall_limit`) beim Speichern unangetastet lassen |

Gemessene Zuordnung (S3a AC-30): 14 Zeilen tragen genau einen Schlüssel; **`wind_change → [gust, wind]`**;
`temperature_min/_max/_change → [temperature]`; `precipitation_sum/_change/_heavy_onset → [precipitation]`;
`thunder_level/_onset → [thunder]`; `snow_line/freezing_level → [freezing_level]`; `cape`, `fresh_snow`,
`visibility` je sich selbst; `humidity` fehlt.

## Entscheidungen aus der S3-Analyse, die für S3b weiter gelten

E1 (eigener Block je Katalog-Größe unter der Stufen-Tabelle, nicht Zelle je Zeile), E4 (`null` = erbt,
sichtbarer Zustand), E5 (alle Kanäle abgewählt ⇒ wird als „erbt" gespeichert, nie `{}`/alle-false),
E6 (freie Wahl aus allen vier Kanälen, Premium-SMS mit vorhandenem Gate, Hinweis wenn ein gewählter
Kanal nicht im Abo-Satz aktiv ist), E9 (Hinweis: Radar und amtliche Warnungen gehen immer über die
Abo-Kanäle), E10 (Block sofort auch in den Anlegemasken). Zusätzlich offen aus S3a Known Limitations:
Hinweis „Kanal ohne Empfänger", Hinweis „Kanal-Schwelle über Metrik-Stufe", Darstellung der
Wind-Kopplung (`wind_change` hängt an `gust` **und** `wind`).

## Related Files (S3b)

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` (635 Z.) | Abschnitt `metric-levels` (`:500-523`) — Block darunter mounten; route-Zweig: lokaler `$state` + EIN Dirty-JSON-`$effect` (`:403-428`) + `buildAlarmeSaveFn` (`:388-399`); vergleich-Zweig: Wertprop + `alarmZustandsBruecke` (`:439-462`) |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` / `…Row.svelte` | Nachbar, bleibt unverändert (E1) |
| `frontend/src/lib/components/alerts-tab/<neuer Block>.svelte` | CREATE — Name in Spec |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` (133 Z.) | Trip-PUT: Top-Level-Feld `alert_metric_channels` ergänzen (nicht in `display_config`) |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` (376 Z.) | `AlarmSnapshot` (+Feld), `ALARM_TOP` (Top-Level-Eigenfelder), `baueAlarmNutzlast`, `rollbackAlarmSnapshot`-Feldliste, Hydration |
| `frontend/src/lib/components/compare/alarmePropsAus.ts`, `compareHubHydration.ts`, `compareEditorSave.ts` | Vergleich: Props, Hydration, `buildComparePresetSavePayload` (auch Anlegen) |
| `frontend/src/lib/components/compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte` (Desktop + Mobile) | Vergleichs-Mounts |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte`, `trip-new/TripNewEditor.svelte`, `trip-new/tripNewLogic.ts` | Trip-Mounts + Anlege-Payload |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte`, `ChannelToggle.svelte`, `alarme-tab/premiumSmsAlarmGate.ts` | Kanal-Bausteine, Premium-SMS-Gate wiederverwenden |
| `frontend/src/lib/types.ts` | `alert_metric_channels?: Record<string, Record<string, boolean> \| null>` an `Trip` und `ComparePreset` |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | neue Texte (Präfix `alarme.kanaele…` existiert, ADR-0104) |
| `frontend/src/lib/__tests__/fakeTripServer.ts:119,127` | Test-Fake kennt das Feld bereits |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`, `corridor-editor/wertebereicheVergleichSpeicherung.ts` | Nachbar-Schreiber des Ortsvergleichs — dürfen das Feld nicht verlieren |

Vorbild für die Doppelverdrahtung ist die Kanal-Schwelle (#1461 S3b-2a/2b): dieselben 13 Dateien
tragen heute `channelThresholds`/`alert_channel_thresholds` (gemessen per `grep`).

## Existing Patterns

- route: `routeX = $state(...)` aus dem Trip, in `_prevAlarmeJson` + `$effect` aufnehmen,
  `buildAlarmeDeliveryPayload` erweitert — **kein** zweiter `schedule()` (F001).
- vergleich: Wertprop + `onXChange` → `onAlarmFeldSetzen`, Feld in `AlarmSnapshot`, Rollback-Liste,
  `ALARM_TOP`, Hydration aus dem Preset.
- Ratsche `context_herkunft_zweige_eingefroren.test.ts`: keine neuen `context===`-Zweige; Diskriminator `trip`.
- Frontend-Tests über `node --test`; E2E Playwright, Nachweis `.tn-mobile` UND `.tn-desktop`.
- Neue Nutzertexte nur über den Katalog DE/EN; Hardcode-Ratsche `i18n/hardcode_allowlist.json`.

## Dependencies

- Upstream: `/api/alert-metric-channel-keys` (S3a), aktive Alarm-Zeilen (`effectiveActiveMetrics`),
  Abo-Kanalstand (`displayChannelState`), Premium-SMS-Gate (`alarmProfile`), Kanal-Schwellen.
- Downstream: S2-Leser im Versand (`trip_alert.py:2509`, `compare_alert.py:601`); S4 (Rückbau
  `alert_rules`) setzt S3b voraus.

## Existing Specs

- `docs/specs/modules/alert_metric_channels.md` — S3b als weiterer Abschnitt, AC-Nummerierung ab AC-41.
- Spec #1461 (Kanal-Schwellen) — Vorbild Doppelverdrahtung.
- Nicht verwechseln: ADR-0050 / `fix_1575_channel_metric_selection.md` (Briefing-Metrik×Kanal-Matrix
  im Versand-Reiter) — Benennung trennscharf halten.

## Risks & Considerations

- **R1 Wirkungslose Fläche (ADR-0043):** Block darf nur Schlüssel aus dem Endpunkt schreiben; Gegenprobe
  am Leser (ein im Editor gesetzter Wert ändert den Versandkanal), nicht nur am Payload.
- **R2 Datenverlust (Read-Modify-Write):** je geänderter Größe vollständiger Eintrag bzw. `null`;
  nicht angefasste und unbekannte Bestandsschlüssel bleiben erhalten; Ortsvergleich-Nachbar-Schreiber
  und Snapshot/Rollback dürfen das Feld nicht verlieren.
- **R3 Wind-Kopplung:** `wind_change` wirkt über `gust` und `wind`; ohne sichtbaren Hinweis neues
  stilles Falschversprechen.
- **R4 Endpunkt nicht ladbar:** Block muss ohne Antwort sicher degradieren (nichts schreiben, nicht
  raten).
- **R5 LoC-Limit 250:** Schätzung UI ~220–250 Produktions-LoC (S3-Analyse). Zuschnitt S3b1
  (Komponente + Trip) / S3b2 (Vergleich + Anlegemasken) in `/30-write-spec` festlegen.
- **R6 Mobile/Kontrast:** vier Kanäle je Größe auf Mobile; WCAG-AA vor Optik.
- **R7 Mandantentrennung:** Speicherweg mit zwei Nutzern (Kern), Staging-Login nur `default`.
- **R8 Parität:** Trip + Vergleich + zwei Anlegemasken, EIN Baustein (Pendant-Sperre).

## Offene Punkte für /20-analyse

1. Zuschnitt (ein Workflow mit Override vs. S3b1/S3b2) anhand genauerer LoC-Schätzung.
2. Ladeort des Endpunkts (im AlarmeTab selbst vs. vom Mount als Prop) und Verhalten ohne Antwort.
3. Darstellung „erbt" vs. eigene Wahl und der Rückweg zu „erbt".
4. Wind-Kopplung und die drei Hinweise (metrikfreie Alarme, Kanal nicht im Abo-Satz, Kanal ohne
   Empfänger / Schwelle) — welche Daten kennt das Frontend dafür überhaupt (Empfänger, SMS-Tarif)?
5. Welche Größen zeigt der Block: Vereinigung der Schlüssel der **aktiven** Zeilen; was mit Bestandseinträgen
   für inaktive Größen (anzeigen oder still erhalten)?

## Analysis

> /20-analyse 2026-11-03 · 3× Explore + Plan-Bewertung + Advisor · Merge-Semantik selbst nachgelesen.

### Type
Feature (Frontend-Scheibe von Epic #2345 / Issue #1895)

### Gemessene Fakten (für /30-write-spec, nicht neu messen)

- **Server-Merge je Metrik-Schlüssel, Eintrag als Ganzes ersetzt.** `internal/handler/config_merge.go:11-22`
  (`dst[k]=v`), Trip-PUT `internal/handler/trip.go:375-378`, Ortsvergleich `internal/handler/briefing_subscription.go:197-205`
  (Top-Level-`null` auf `alert_metric_channels` = No-Op `:198`, nested eine Ebene `mergeConfigMap`).
  Folgen (je eigener AC):
  - (a) Jeder gesendete Eintrag trägt **alle vier** Kanal-Flags oder `null`, nie einen Teil (ein fehlendes Flag ginge verloren).
  - (b) Rollback Ortsvergleich: Einträge, die seit dem Snapshot neu entstanden sind, explizit mit `null` senden;
    Weglassen setzt nichts zurück.
  - (c) Unbekannte/inaktive Bestandsschlüssel (z. B. `snowfall_limit`) bleiben erhalten, solange sie nicht gesendet werden.
  - **Entscheidung Payload:** nur geänderte Einträge senden (Diff gegen den hydrierten Stand), nie eine neu aufgebaute Vollmap.
- **Endpunkt** `GET /api/alert-metric-channel-keys` → `{keys:{AlertMetric:[key…]}, accepted:[…]}`; im Frontend noch nirgends
  aufgerufen; nutzerunabhängig ⇒ Modul-Promise-Cache mandantensicher (Vorbild `compareMetricCatalogLoader.ts:257-273`,
  bei Fehler nicht cachen).
- **AlarmeTab kennt:** aktive Zeilen `effectiveActiveMetrics` (`AlarmeTab.svelte:245-254`), Abo-Kanalstand `displayChannelState`
  (`:306-308`), Kanal-Schwellen `displayChannelThresholds` (`:334-343`), Premium-SMS-Gate über `alarmProfile` aus
  `/api/auth/profile` (`:187-206`, liest nur `premium_sms_allowed`). **Kennt nicht:** Empfänger (`mail_to`, `sms_to`,
  `telegram_chat_id`, `sms_verified`) und `tier`, obwohl das Profil sie liefert (`auth.go:913-957`).
- **Ratsche** `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` pinnt `AlarmeTab.svelte:259,:519,:537,:570`,
  `alarmeTabSections.ts:27,:38`, `versandVergleichSpeicherung.ts:244`, `wertebereicheVergleichSpeicherung.ts:209`.
  Neuer Inhalt in neue Dateien; in AlarmeTab wenige Zeilen; die vier AlarmeTab-Pins danach neu messen (fester Schritt);
  Section-ID in `alarmeTabSections.ts:20` anhängen (zeilenneutral). Keine neue `context===`-Weiche (bei Variante C nicht nötig).
- **Pendant-Sperre** greift für `components/alerts-tab/` nicht automatisch; Block liegt in `alerts-tab/` neben
  `AlertMetricLevelTable` (E1), Helper in `shared/alarme-tab/`.
- **i18n:** `hardcode_allowlist.json` muss `[]` bleiben; alle Texte in `messages/{de,en}/alarme.json` (Präfix `alarme.kanaele…`).

### Entscheidungen S3b (zusätzlich zu E1–E10)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| F1 | Zuschnitt | **Variante C:** S3b1 (dieser Workflow) = Block + Helper + **alle vier Flächen** (Trip-Hub, Trip-Anlegen, Vergleich, Vergleich-Anlegen) samt Speicherweg, Snapshot/Rollback, Hinweis „nicht im Abo-Satz", Hinweis metrikfreie Alarme (E9), Wind-Hinweis. S3b2 (unter #1895, kein neues Issue) = Hinweis „Kanal ohne Empfänger" + Hinweis „Kanal-Schwelle über Metrik-Stufe" | Kein temporäres Flächen-Gate (Parität ADR-0095, keine wirkungslose Fläche ADR-0043); Variante B (Trip/Vergleich-Split) hätte ein Gate gebraucht und nur ~59 LoC gespart. Der Empfänger-Hinweis braucht einen Abgleich mit dem Python-Transport (wann gilt ein Kanal dort als „ohne Empfänger": `sms_verified`, leere `telegram_chat_id` …), sonst neues Falschversprechen. **Das** ist der Grund für den Schnitt, nicht die Zeilenzahl |
| F2 | Ladeort Endpunkt | Im Helper-Modul (Modul-Promise-Cache), vom Block selbst geladen; Mounts bleiben unverändert | Keine Prop-Durchreichung durch 6 Mount-Stellen |
| F3 | Endpunkt nicht ladbar | Block zeigt „nicht verfügbar", schreibt nichts, rät keine Schlüssel | R4 |
| F4 | Welche Zeilen | Eine Zeile je Speicherschlüssel = Vereinigung `keys[m]` über die aktiven Alarm-Zeilen, nur Schlüssel aus `accepted` | E1 (1:1, kein verstecktes Spiegeln) |
| F5 | Inaktive Bestandseinträge | nicht anzeigen, still erhalten (werden nie gesendet) | Merge (c) |
| F6 | Wind-Kopplung | **Kein** Doppelschreiben, **kein** Zustand „gemischt": `gust` und `wind` sind zwei eigene Zeilen; Hinweistext an beiden, dass die Windänderung je nach Auslöser der Böen- oder der Wind-Zeile folgt | E1; Known Limitation Spec `:827`. Plan-Vorschlag „beide schreiben + gemischt" verworfen |
| F7 | „erbt" vs. eigene Wahl | Je Zeile Standard „wie Abo-Kanäle" (`null`); Umschalter „eigene Wahl" zeigt vier Kanal-Schalter (`ChannelToggle` wiederverwenden), vorbelegt mit dem Abo-Satz; Rückweg = Umschalter aus ⇒ `{key:null}`; alle vier abgewählt ⇒ `null` (E5) | E4/E5 |
| F8 | Premium-SMS | vorhandenes Gate `premiumSmsAlarmGate` wiederverwenden; kein Tarif-Hinweis für SMS nötig (Rückfall AC-25/26) | E6, S3a |
| F9 | LoC | S3b1 ≈ 240 ±30 % ⇒ `loc_limit_override` **voraussichtlich nötig** (Vorbild #1461) | ehrlich angesetzt |

### Affected Files (S3b1)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alerts-tab/AlertMetricChannelsBlock.svelte` | CREATE | Block je Speicherschlüssel, Umschalter erbt/eigene Wahl, 4× ChannelToggle, Hinweise (~130) |
| `frontend/src/lib/components/shared/alarme-tab/alertMetricChannels.ts` | CREATE | Endpunkt-Cache, Zeilen-Vereinigung, Normalisierung (alle aus ⇒ null, immer 4 Flags), Diff-Payload, Hinweislogik (~70) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Props/State, Mount des Blocks nach `metric-levels`, route: Dirty-`$effect` + `buildAlarmeSaveFn`, vergleich: Brücke (~28); Ratsche neu messen |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY | Section-ID an `:20` anhängen |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | MODIFY | Top-Level `alert_metric_channels` (nur wenn Diff nicht leer) |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | MODIFY | Bestandsmap durchreichen |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts`, `TripNewEditor.svelte` | MODIFY | Anlege-Payload, Desktop- + Mobil-Mount |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | `AlarmSnapshot`, `AlarmHydrationTarget`, `ALARM_TOP`, `baueAlarmNutzlast`, Rollback (neue Einträge ⇒ null) |
| `frontend/src/lib/components/compare/alarmePropsAus.ts`, `compareHubHydration.ts`, `compareEditorSave.ts` | MODIFY | Props, Hydration, Edit- + Create-Payload |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Create-Payload (Mounts per Spread unverändert) |
| `frontend/src/lib/types.ts` | MODIFY | Feld an `Trip` und `ComparePreset` |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | MODIFY | neue Texte |
| `versandVergleichSpeicherung.ts`, `wertebereicheVergleichSpeicherung.ts`, `CompareTabs.svelte` | unverändert | Feld darf dort nicht verloren gehen ⇒ Test, keine Änderung |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | S3b1-ACs ab AC-41; Scheibenschnitt `:805-811` und Zusage `:824` auf S3b1/S3b2 umschreiben (kein stilles Versprechen) |

### Scope Assessment
- Files: ~16 (2 neu)
- Estimated LoC: S3b1 ≈ +240/−5 Produktion (Spanne 170–310), Tests zusätzlich; S3b2 ≈ +60–80
- Risk Level: MEDIUM (geteilter Organismus auf vier Flächen, Speicherweg mit Read-Modify-Write, Ratsche)

### Technical Approach
Reines TS-Helper-Modul (alle Regeln testbar per `node --test`) + schlanker Block; AlarmeTab bindet ihn ohne neue
Context-Weiche ein; route über lokalen `$state` im bestehenden Dirty-`$effect` (kein zweiter `schedule()`),
vergleich über Wertprop + `onAlarmFeldSetzen` + Snapshot/Rollback. Nachweis der Wirkung am Leser (ein im Editor
gesetzter Wert ändert den Versandkanal, R1), Speicherweg mit zwei Nutzern (R7), E2E `.tn-mobile` und `.tn-desktop`.

### AC-Pflichtpunkte für die Spec (ab AC-41)
Vollständiger Eintrag (4 Flags) oder `null`; Diff statt Vollmap; Bestandsschlüssel erhalten; Rollback sendet `null`
für neue Einträge; Nachbar-Schreiber verlieren das Feld nicht; Endpunkt-Ausfall ⇒ nichts geschrieben; alle aus ⇒ erbt;
Wind-Hinweis an `gust`/`wind`; Hinweis „nicht im Abo-Satz"; Hinweis metrikfreie Alarme; alle vier Flächen; zwei Nutzer;
Wirkung am Leser; DE/EN.

### Dependencies
Upstream S3a (Endpunkt, Rückfall, null-No-Op) live. Downstream: S3b2 (Hinweise Empfänger/Schwelle), S4 (Rückbau `alert_rules`).

### Open Questions
- keine PO-Fragen; alle Punkte technisch entschieden (F1–F9).

## Übergabe-Vertrag RED → /50-implement (2026-11-03)

RED-Tests (alle rot aus fachlichem Grund, außer bewusst grün markiert):
- `frontend/src/lib/components/shared/alarme-tab/__tests__/kanal_wahl_je_wettergroesse_regeln.test.ts` — Helper (AC-41/42/44–51, AC-60 Frontend-Hälfte); rot: Modul fehlt
- `frontend/src/lib/components/alerts-tab/__tests__/kanal_block_zeilen_und_hinweise_render.test.ts` — Block (AC-41/43/45/46/48/49/51/52/53); rot: Komponente fehlt
- `frontend/src/lib/components/shared/__tests__/alarme_trip_kanalwahl_ein_speichervorgang.test.ts` — Trip (AC-47/54/59/42); 4× Assertion-rot
- `frontend/src/lib/components/shared/__tests__/alarme_vergleich_kanalwahl_speicherweg.test.ts` — Vergleich (AC-55/47/42/56); 4× rot, AC-57 grün (Mutations-Fixture)
- `frontend/src/lib/i18n/__tests__/alarme_kanaele_texte_de_en.test.ts` — AC-61; rot: Schlüssel fehlen
- `tests/tdd/test_alert_metric_channels_nutzlast_bruecke.py` + `tests/fixtures/alert_metric_channels_nutzlast_beispiel.json` — AC-60 Leser-Hälfte, grün seit S3a (bewusst)

**Helper `shared/alarme-tab/alertMetricChannels.ts`:**
- `type KanalEintrag = {email, telegram, sms, premium_sms: boolean} | null`
- `ladeKanalSchluessel(fetchFn = fetch): Promise<{keys, accepted} | null>` — Modul-Promise-Cache, parallele Aufrufe teilen einen Abruf; HTTP-nicht-ok/Netzfehler ⇒ `null` (oder Reject), nie gecacht; URL enthält `/api/alert-metric-channel-keys`
- `_resetKanalSchluesselCache()`
- `kanalZeilen(aktiveMetriken, keys, accepted): string[]` sortiert, ohne Dubletten
- `normalisiereEintrag(flags): KanalEintrag` immer vier Flags, alle aus ⇒ `null`
- `baueDiff(hydriert, aktuell)`: verglichen werden nur Schlüssel aus `aktuell` (fehlend = unberührt); fehlend und `null` gelten beide als „erbt" ⇒ Rollback muss `null` explizit setzen
- `hinweise(eintrag, aboSatz): string[]` gewählte Kanäle, die im Abo aus sind; `null` ⇒ `[]`

**Block `alerts-tab/AlertMetricChannelsBlock.svelte`:** Props `aktiveMetriken`, `eintraege`, `aboKanaele`, `premiumSmsGate` (Ausgabe `derivePremiumSmsAlarmGate`), `schluesselOverride?` (Testhaken: Objekt = Antwort, `null` = Abruf gescheitert), `onChange(schluessel, eintrag)`. Instanzfunktionen `kanalSetzen(k, kanal, an)`, `eigeneWahl(k, an)` — Änderungen nur über `onChange`. Testids: `kanal-zeile-<k>`, `kanal-schalter-<k>-<kanal>` (ChannelToggle, gesperrt über `disabled`), `kanal-hinweis-wind-<k>`, `kanal-hinweis-nicht-im-abo-<k>`, `kanal-hinweis-metrikfrei`, `kanal-nicht-verfuegbar`.

**Trip:** `AlarmeDeliveryState.metricChannelsDiff` ⇒ Top-Level `alert_metric_channels` nur bei nicht-leerem Diff; `CreateTripAlarmState.metricChannels`; AlarmeTab route: `routeAlertMetricChannels` + Prop `existingAlertMetricChannels`; Einbettung genau einmal `<AlertMetricChannelsBlock onChange={…}>`, `onChange` als Funktionsname oder Ausdruck ohne TS-Typannotation (Prüfstand wertet ihn aus). Kein Resync-`$effect` auf `routeAlertMetricChannels` (der AC-54-Test führt alle Effekte aus, die ihn nennen, und zählt `schedule()`).

**Vergleich:** Feld `alertMetricChannels` in `AlarmSnapshot`, `AlarmHydrationTarget`, `alarmePropsAus`, `CompareEditorEdits`, `NewComparePresetFields`; Diff-Basis `preset.alert_metric_channels`.

**i18n** (`alarme.json` de+en, Ratsche `katalog_schluessel_haben_verwender` verlangt Nutzung im Block): `alarme.kanaele.ueberschrift`, `.wie_abo`, `.eigene_wahl`, `.nicht_im_abo`, `.metrikfrei_hinweis`, `.wind_hinweis`, `.nicht_verfuegbar`.

**Feste Schritte in /50-implement:**
- `compare_alarme_wertprops.test.ts:1020` `SNAPSHOT_FELDER_SOLL = 10` → 11 und Feldtabelle um `alertMetricChannels` ergänzen.
- Ratsche `context_herkunft_zweige_eingefroren.test.ts` (AlarmeTab-Pins) neu messen (AC-58).
- `loc_limit_override` (≈ 320) vor dem ersten Produktiv-Edit — muss der PO setzen (automatisch abgelehnt).

**Bekannte Lücken der RED-Abdeckung (in /60 bzw. /e2e-verify schließen):**
- AC-62 (Playwright, `.tn-mobile`/`.tn-desktop`) nicht als Kern-Test geschrieben → /e2e-verify; dort auch Klickwege AC-43/AC-48 echt im Browser.
- AC-59: `fakeTripServer` kennt keine Nutzer; Vergleichsseite fehlt; „Rollback" ist PUT mit `null`, nicht `rollbackAlarmSnapshot`.
- AC-54 Anlegen: nur Payload-Builder, Desktop-/Mobil-Mount von `TripNewEditor` ungetestet.
- AC-55: Verdrahtung AlarmeTab (vergleich) → Brücke → `onAlarmFeldSetzen` ohne eigenen Test (indirekt über die Snapshot-Frische-Schleife nach Anhebung auf 11).
