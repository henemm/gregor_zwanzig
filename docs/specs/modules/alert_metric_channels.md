---
entity_id: alert_metric_channels
type: module
created: 2026-09-22
updated: 2026-11-04
status: draft
version: "1.4"
tags: [alerts, channels, datamodel]
---

# Alert Metric Channels

## Approval

- [ ] Approved

## Purpose

Diese Spec legt die Zielform eines neuen, additiven Feldes `alert_metric_channels` auf
`Trip` und `ComparePreset` fest — Ablageort, Go-Typ und Merge-Verhalten — damit spätere
Scheiben (Metrik-genaue Kanal-Auflösung, Editor-Spalte) darauf aufbauen können, ohne beim
Speichern Kanäle einer anderen Metrik zu verlieren. Diese Scheibe (S1) ist reine
Verrohrung: Das Feld wird persistiert und übersteht Speichern/Laden, wirkt aber auf
nichts — es gibt in S1 noch keine Stelle, die es liest.

**Scheibe S3a (Issue #1895, Backend und Vertrag, für Nutzer noch nicht sichtbar):** S3a macht die
Schicht tragfähig, bevor eine Oberfläche sie anbietet. Vier Teile: (1) der Leser fällt auf den
Satz ohne Metrik-Arm zurück, wenn der Metrik-Arm **nach** den Tarif-Sperren leer ist (ein
gewählter Kanal kann den Alarm dann nicht mehr ins Leere schicken); (2) ein Nachtrag zu
ADR-0077 hält Schlüsselmenge, Rückfall und „null = erbt" fest; (3) ein neuer Lese-Endpunkt
`GET /alert-metric-channel-keys` (Go-Proxy `GET /api/alert-metric-channel-keys`) ist die
**einzige** Quelle dafür, welche Alarm-Zeile auf welchen Speicherschlüssel abbildet; (4) ein
Top-Level-`null` auf `alert_metric_channels` löscht beim Ortsvergleich nicht mehr die ganze
Map (Angleichung an den Trip). Es gibt dafür **keine Oberfläche** (Prod-Bestand: 0 Briefings
mit `alert_metric_channels`); das Verhalten ist für Nutzer erst mit S3b sichtbar. Die Oberfläche
(Block „Kanäle je Wettergröße", Hinweise) ist ausdrücklich **nicht** Teil von S3a.

**Scheibe S3b1 (Issue #1895, Oberfläche, für Nutzer erstmals sichtbar):** S3b1 liefert den Block
„Kanäle je Wettergröße" im geteilten Alarme-Reiter auf **allen vier Flächen** (Trip-Hub,
Trip-Anlegen, Ortsvergleich, Ortsvergleich-Anlegen) samt Speicherweg, Snapshot/Rollback,
DE/EN-Texten und drei Hinweisen („Kanal nicht im Abo-Satz aktiv", „Radar und amtliche Warnungen
gehen immer über die Abo-Kanäle", Wind-Hinweis). Die Zuordnung Zeile → Speicherschlüssel kommt
ausschließlich aus `GET /api/alert-metric-channel-keys` (S3a). Die Hinweise „Kanal ohne
Empfänger" und „Kanal-Schwelle über Metrik-Stufe" sind **nicht** Teil von S3b1, sondern S3b2
(geliefert mit S3b2, siehe Abschnitte S3b2).

**Scheibe S3b2 (Issue #1895, Hinweise im Block, reine Frontend-Scheibe):** S3b2 ergänzt im Block
„Kanäle je Wettergröße" genau zwei Hinweise für Zeilen mit **eigener Wahl**: (1) „Kanal ohne
Empfänger" — ein gewählter Kanal hat keinen Empfänger, an den der Alarm zugestellt werden könnte
(Telegram ohne Chat, SMS ohne bestätigte Nummer, Premium-SMS ohne frische Rückadresse); (2)
„Kanal-Schwelle über Metrik-Stufe" — der gewählte Kanal hat eine Schwelle über „niedrig", schwächere
Warnungen kommen darüber nicht an (ADR-0046). Die Hinweise **informieren nur**: sie sperren weder
Auswahl noch Speichern, und der Speicherweg, Snapshot und Rollback bleiben unberührt. Es gibt keinen
neuen Backend-Code.

## Source

- **File (Go-Modell):** `internal/model/trip.go`, `internal/model/compare_preset.go`
- **File (Go-Handler):** `internal/handler/trip.go`
- **File (Python-Domäne):** `src/app/trip.py`, `src/app/loader.py`
- **File (Doku):** `docs/reference/api_contract.md`, `docs/adr/0077-*.md`
- **Identifier:** `Trip.AlertMetricChannels`, `ComparePreset.AlertMetricChannels`,
  `tripUpdateRequest.AlertMetricChannels`, `Trip.alert_metric_channels` (Python-Dataclass)

### Affected Files (S1)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `internal/model/trip.go` | MODIFY | Feld `AlertMetricChannels map[string]interface{}` mit `json:"alert_metric_channels,omitempty"` + Docstring (Muster `AlertChannels`, `:151-163`) |
| `internal/model/compare_preset.go` | MODIFY | dito (Muster `AlertChannelThresholds`, `:91-98`) |
| `internal/handler/trip.go` | MODIFY | DTO-Feld in `tripUpdateRequest` + `mergeConfigMap`-Zeile im RMW-Block, analog `:334-336` |
| `internal/handler/compare_preset.go` | — | **unberührt**, läuft generisch über `mergeBriefingPatch` — aber das Struct-Feld ist trotzdem Pflicht (typisierter Unmarshal verwirft sonst den Key, s. Implementation Details) |
| `internal/store/trip.go` | — | **unberührt, nachgemessen 2026-09-22:** `SaveTrip` marshalt das Struct transparent (`:272`), `LoadTrip`/`LoadTrips` unmarshalen transparent (`:197`/`:141`). Ein neues Struct-Feld fließt ohne Registrierung mit; die `snow_line`→`freezing_level`-Legacy-Migration (`:314-330`) ist feldspezifisch und berührt es nicht. |
| `src/app/trip.py` | MODIFY | Dataclass-Feld `alert_metric_channels: Optional[dict] = None` (Muster `alert_channels`, `:221`) |
| `src/app/loader.py` | MODIFY | `KNOWN_TOP_LEVEL`-Eintrag + Konstruktor-`data.get(...)` + bedingtes Schreiben in `_trip_to_dict` (Muster `:652,695,1625-1626`) |
| `src/app/models.py` | MODIFY | optionales typisiertes `ComparePreset`-Feld (Parität). **Für die Persistenz nicht nötig, nachgemessen:** `compare_preset_to_dict` liefert `preset.raw` unverändert zurück (`src/app/loader.py:345-352`) — jeder Key übersteht den Python-Roundtrip ohne Codeänderung. Das Feld dient S2 als benannter Leser. |
| `docs/reference/api_contract.md` | MODIFY | **Pflicht, sonst CI rot** — siehe AC-8 |
| `docs/adr/0077-*.md` + `docs/adr/README.md` | CREATE/MODIFY | ADR-0077 (Fortschreibung ADR-0046), Index-Eintrag (`tests/test_adr_index_drift.py`) |
| `tests/…` Roundtrip + `internal/store/…_test.go` | CREATE/MODIFY | Roundtrip-Nachweis beide `kind`-Werte, zwei Nutzer |

### Affected Files (S2)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | Rückwärts-Lookup `summary_field → Kandidaten` als **eine** Primitive (Katalog besitzt `summary_fields` bereits); Wählbarkeits-Tie-Break (bei mehreren Kandidaten gewinnt `selectable=True`, bei genau einem Kandidaten gewinnt dieser) |
| `src/services/alert_channels.py` | MODIFY | Fünfte Eingabe `metric_channel_sets` im reinen Kern (Schleifen-Form aus `:56-60`, umgeschlüsselt auf Metrik statt Regel); Adapter lesen `alert_metric_channels`; Leer-Rückfall-Guard vor den Tier-Gates (seit S3a/AC-25: nach den Tier-Gates); `metrics=None`-Default im Dispatcher, damit die acht metrikfreien Aufrufstellen unverändert bleiben |
| `src/services/trip_alert.py` | MODIFY | Nur `:2509` (`_send_alert`) reicht die Metriken der `changes` durch; `:552` bleibt unberührt (reine Protokoll-Zierde, kein Versand) |
| `src/services/compare_alert.py` | MODIFY | **Nicht** `:601` — dort sind die auslösenden Metriken noch unbekannt. Der metrik-bewusste Aufruf gehört in die bestehende Ortsschleife `:286-293`, inklusive Fix der `ids_by_channel`-Vorbelegung (AC-17) |
| `src/app/loader.py` | MODIFY | Migration `alert_rules[].channels` → `alert_metric_channels`, Read-Modify-Write nach Muster `:741-753` (`snow_line`→`freezing_level`) |
| `src/output/renderers/alert/project.py` | MODIFY | `_resolve_metric_id` + `_resolve_corridor_metric_id` delegieren auf die Katalog-Primitive aus `metric_catalog.py` statt eine zweite Kopie zu halten (#1481, ADR-0021). Diese Änderung fällt unter das Renderer-Mail-Gate (`renderer_mail_gate.py:45/56`) und verlangt vor „E2E bestanden" einen frischen Nachweis mit **`radar_alert_mail_validator.py`** gegen eine **echt zugestellte Staging-Mail** aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`) — entschieden: Weg (i), kein zweiter Rückwärts-Lookup |
| `docs/reference/api_contract.md` | MODIFY | Semantik-Nachtrag am schon dokumentierten Feld (`:925-940`) — `tests/test_api_contract_drift.py` bleibt grün |
| `docs/adr/0077-*.md` | MODIFY | Ergänzung an Punkt 3: „Das Lese-Vokabular legt S2 fest (Katalog-`metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt); die verbindliche, validierte Menge samt Editor-Anzeige bleibt S3." Keine Statusänderung, kein neues ADR — `tests/test_adr_index_drift.py` bleibt unberührt |
| `tests/tdd/test_alert_metric_channel_reader.py` | CREATE | Leser, Tie-Break, Leer-Rückfall, metrikfreie Immunität, Trip/Vergleich-Parität |
| `tests/tdd/test_alert_metric_channel_migration.py` | CREATE | Migrations-Fallen (eins-zu-viele, Kollisionen, leere Liste, deaktivierte Regeln) + Roundtrip über Go-Handler und Python-Lader |

**Nicht angefasst (S2):** alles unter `frontend/`, `internal/`, `cmd/`; `has_active_rules`;
`alert_rules` als Entität (Rückbau folgt S4); `split_by_threshold` (die Union braucht keine
Partitionsstelle).

### Affected Files (S3a)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/services/alert_channels.py` | MODIFY | `resolve_alert_channels`: Rückfall auf den Satz ohne Metrik-Arm, wenn der Metrik-Arm **nach** den Tier-Gates leer ist (AC-25); Docstring Schritt 4/5 anpassen (Satz „kein Fall für den Rückfall" entfällt) |
| `src/services/weather_change_detection.py` | MODIFY | Neben den Summary-Feld-Tabellen die **eine** Funktion `alert_metric_channel_keys()` (Zeile → sortierte Liste der Speicherschlüssel aus Lesersicht, akzeptierte Menge); keine zweite Zeile-zu-Schlüssel-Liste |
| `api/routers/config.py` | MODIFY | Neuer Endpunkt `GET /alert-metric-channel-keys`; `get_metrics` bleibt **unverändert** |
| `internal/router/router.go` | MODIFY | Proxy `GET /api/alert-metric-channel-keys` → `/alert-metric-channel-keys`, gleiche Auth-Gruppe und Zeilenmuster wie `/api/metrics` (`:235`) |
| `internal/handler/briefing_subscription.go` | MODIFY | `mergeBriefingPatch`: Top-Level-`null` für **genau** `alert_metric_channels` überspringen (No-Op); alle anderen Felder behalten ihre Semantik (AC-36/AC-37) |
| `docs/reference/api_contract.md` | MODIFY | SSOT: neuer Endpunkt samt Antwortform und Hinweis „null = erbt" am Feld (`tests/test_api_contract_drift.py` bleibt grün) |
| `docs/adr/0077-metrik-genaue-kanal-schicht-als-top-level-map.md` | MODIFY | Nachtrag „S3a" (kein neues ADR, kein Status-Wechsel; `docs/adr/README.md` bleibt unverändert, `tests/test_adr_index_drift.py` prüft nur Datei↔Index-Konsistenz und Status) |
| `tests/tdd/test_alert_metric_channel_reader.py` | MODIFY | `test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren` (`:511`) wird **umgekehrt**: nach Tier-Gate-Kürzung greift der Rückfall (AC-25) |
| `tests/tdd/test_alert_metric_channel_keys.py` | CREATE | Endpunkt-Abbildung, zeilenweiser Wirk-Test, Migrations-Schlüsselmenge (AC-30 bis AC-34) |
| `internal/handler/compare_preset_alert_metric_channels_test.go` | MODIFY | Null-Angleichung, Gegenprobe, je-Metrik-`null`, zwei Nutzer (AC-36 bis AC-39) |
| `internal/handler/trip_alert_metric_channels_test.go` | MODIFY | Trip-Regressionsfall: Top-Level-`null` bleibt No-Op (AC-36) |
| `internal/router/alert_metric_channel_keys_route_test.go` | CREATE | Proxy-Route und Auth (AC-35) |

**Nicht angefasst (S3a):** alles unter `frontend/` (keine UI), `src/app/loader.py` (Migration
und ihr Tie-Break bleiben unverändert, AC-33 prüft nur die Verträglichkeit), `split_by_threshold`
(`trip_alert.py`, `compare_alert.py`), `internal/handler/trip.go` (Trip-Verhalten schon korrekt,
nur Regressions-Test), `/api/metrics`-Antwort, `has_active_rules`, `alert_rules` als Entität.

### Affected Files (S3b1)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/alerts-tab/AlertMetricChannelsBlock.svelte` | CREATE | Block je Speicherschlüssel, Umschalter „wie Abo-Kanäle" / „eigene Wahl", vier `ChannelToggle`, Hinweise (~130 LoC) |
| `frontend/src/lib/components/shared/alarme-tab/alertMetricChannels.ts` | CREATE | Endpunkt-Modul-Promise-Cache, Zeilen-Vereinigung, Normalisierung (alle aus ⇒ `null`, immer vier Flags), Diff-Payload, Hinweislogik (~70 LoC) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Props/State, Mount des Blocks nach dem Abschnitt `metric-levels`, route: Aufnahme in den bestehenden Dirty-JSON-`$effect` und `buildAlarmeSaveFn`, vergleich: `alarmZustandsBruecke` (~28 LoC); Ratsche neu messen |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | MODIFY | Section-ID an der bestehenden Liste anhängen (zeilenneutral) |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | MODIFY | Trip-PUT: Top-Level-Feld `alert_metric_channels` (nicht in `display_config`), nur wenn der Diff nicht leer ist |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | MODIFY | Bestandsmap des Trips durchreichen |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts`, `trip-new/TripNewEditor.svelte` | MODIFY | Anlege-Payload, Desktop- und Mobil-Mount |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | MODIFY | `AlarmSnapshot`, `AlarmHydrationTarget`, `ALARM_TOP`, `baueAlarmNutzlast`, Rollback (seit dem Snapshot neu entstandene Einträge ⇒ `null`) |
| `frontend/src/lib/components/compare/alarmePropsAus.ts`, `compare/compareHubHydration.ts`, `compare/compareEditorSave.ts` | MODIFY | Props, Hydration, Edit- und Create-Payload (`buildComparePresetSavePayload`) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Create-Payload (Mounts per Spread unverändert) |
| `frontend/src/lib/types.ts` | MODIFY | `alert_metric_channels?: Record<string, Record<string, boolean> \| null>` an `Trip` und `ComparePreset` |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | MODIFY | neue Texte, Präfix `alarme.kanaele…` |
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`, `corridor-editor/wertebereicheVergleichSpeicherung.ts`, `compare/CompareTabs.svelte` | unverändert | Feld darf dort nicht verloren gehen ⇒ Test, keine Änderung |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte`, `…Row.svelte` | unverändert | Nachbar der Stufen-Tabelle (E1) |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Pins der AlarmeTab-Zeilen nach der Änderung neu messen (fester Schritt, keine neue `context===`-Weiche) |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | diese Spec |

**Nicht angefasst (S3b1):** alles unter `internal/`, `cmd/`, `src/`, `api/` (Backend und Endpunkt
sind mit S3a fertig); `/api/metrics`; `hardcode_allowlist.json` (bleibt `[]`).

### Affected Files (S3b2)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/alarme-tab/alertMetricChannels.ts` | MODIFY | reine Funktionen `kanaeleOhneEmpfaenger(eintrag, profil)` und `kanaeleMitSchwelle(eintrag, schwellen)` neben `hinweise()`; Empfänger-Bedingung für Telegram/SMS deckungsgleich mit `channelConnectionStatus` |
| `frontend/src/lib/components/alerts-tab/AlertMetricChannelsBlock.svelte` | MODIFY | neue Props `profil`, `schwellen`; je Zeile mit eigener Wahl zwei Hinweiszeilen (Testids `kanal-hinweis-kein-empfaenger-<k>`, `kanal-hinweis-schwelle-<k>`) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Typ von `alarmProfile` auf `ConnectionProfile` erweitern, `alarmProfile` und `displayChannelThresholds` an den Block reichen; keine zweite Profil-Abfrage, keine neue `context===`-Weiche; Ratsche neu messen |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts` | MODIFY (nur Kommentar) | überholte Aussage (Zeilen 7-14), der Alarmpfad frage die Empfängerprüfung nicht, berichtigen; Logik unverändert |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | MODIFY | je 2 neue Schlüssel `alarme.kanaele.kein_empfaenger`, `alarme.kanaele.schwelle_hinweis` |
| `frontend/src/lib/components/alerts-tab/__tests__/kanal_block_zeilen_und_hinweise_render.test.ts`, `shared/alarme-tab/__tests__/kanal_wahl_je_wettergroesse_regeln.test.ts`, `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Regeltests (zwei Nutzer, Profil null, je Kanal), Render-Test, Katalog DE/EN, Ratsche neu messen |
| `frontend/e2e/kanal-je-wettergroesse-block.staging.spec.ts` | MODIFY | Hinweise sichtbar auf `.tn-mobile` und `.tn-desktop` |
| `frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts` | unverändert | Quelle der Empfänger-Definition (Telegram/SMS); wird gelesen, nicht verändert |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | diese Spec |

**Nicht angefasst (S3b2):** alles unter `internal/`, `cmd/`, `src/`, `api/` (nur gelesen als Quelle
der Bedingungen: `src/output/channels/recipient.py`, `premium_sms.py`,
`src/services/alert_channel_threshold.py`); Speicherweg, Payload, Snapshot, Rollback;
`hardcode_allowlist.json` (bleibt `[]`).

## Estimated Scope

- **LoC:** +40 bis +90 produktiv (Doku/`*.md`/Tests zählen nicht)
- **Files:** 7 produktiv + 2 Doku + Tests
- **Effort:** medium

### Estimated Scope (S2)

- **LoC:** ca. **+180 / −15** produktiv — eng am 250er-Limit. Vor `/40-tdd-red` erst
  `workflow.py status` lesen; wird es knapp, `workflow.py set-field loc_limit_override 500`
  setzen, statt die RED-Abdeckung eigenmächtig auf eine Teilmenge der ACs zu verengen.
  `docs/`, `*.md` und ADR-Änderungen zählen nicht mit.
- **Files:** 6 produktiv + 2 Test + 3 Doku
- **Effort:** high (Risiko MITTEL-HOCH: Verhaltensänderung an Bestandsdaten, Persistenz-
  Migration mit Pre-Snapshot-Hook, Fläche ist der Alarm-Versand, Asymmetrie der zwei
  Aufrufstellen)

### Estimated Scope (S3a)

- **LoC:** ca. **+75 / −10** produktiv (Rückfall ~10, Schlüssel-Funktion ~20, Endpunkt ~15,
  Go-Proxy 1, Go-Null-Skip ~8, Rest Docstring). Limit 250 je Workflow; `docs/`, `*.md`, ADR und
  Tests zählen nicht.
- **Files:** 5 produktiv + 4 Test + 2 Doku (Spec/ADR-Nachtrag zählen nicht mit)
- **Effort:** medium (Risiko MITTEL: ändert die Versand-Auflösung, aber nur auf einem Zweig, den
  heute kein Bestand erreicht — 0 Briefings mit Feld)

### Estimated Scope (S3b1)

- **LoC:** ca. **+240 / −5** produktiv (Spanne 170–310; Block ~130, Helper ~70, AlarmeTab ~28,
  Rest verteilt auf Payload, Hydration, Snapshot, Typen). Das liegt am oder über dem Limit von
  250 je Workflow: ein `loc_limit_override` ist **voraussichtlich nötig** (Vorbild #1461,
  dieselbe Doppelverdrahtung Trip + Vergleich). Vor `/40-tdd-red` erst `workflow.py status`
  lesen und den Override setzen, statt die RED-Abdeckung auf eine Teilmenge der ACs zu verengen.
  `docs/`, `*.md`, ADR und Tests zählen nicht mit.
- **Files:** ca. 16 produktiv (2 neu) + Tests + Spec
- **Effort:** high (Risiko MITTEL: geteilter Organismus auf vier Flächen, Speicherweg mit
  Read-Modify-Write, Ratsche)
- **S3b2 (separat, unter #1895):** ca. +90/−5 LoC (siehe Estimated Scope S3b2).

### Estimated Scope (S3b2)

- **LoC:** ca. **+90 / −5** produktiv (zwei reine Funktionen ~25, Block ~30, AlarmeTab ~5,
  Kataloge ~4, Kommentar-Berichtigung). Unter dem Limit von 250 je Workflow; `docs/`, `*.md` und
  Tests zählen nicht.
- **Files:** ca. 6 produktiv + Tests + Spec; Frontend-only-Deploy.
- **Effort:** low bis medium (Risiko NIEDRIG: reine Anzeige, Speicherweg unberührt, kein Backend).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #1230 | Epic | Rahmen-Issue, dessen letzte offene Substanz diese Scheibe liefert |
| #2293 | Folge-Abstimmung | definiert dieselbe Fläche (`ComparePreset.AlertChannels`, Schicht 2 je Abo); wird nach dieser Spec gegen die hier festgelegte Zielform neu geschnitten. Beide Felder existieren nebeneinander: #2293 bleibt Schicht "je Abo", dieses Feld ist die neue Schicht "je Metrik". |
| ADR-0043 | Architekturentscheidung | verbietet eine Konfigurationsfläche ohne sichtbare Wirkung — begründet den Scheibenschnitt (S2 vor S3) |
| ADR-0046 | Architekturentscheidung | Kanal-Schwelle regelt AUF WELCHEM WEG eine Meldung ankommt, nicht OB — diese Spec schreibt ADR-0046 fort |
| S3a (`GET /api/alert-metric-channel-keys`, AC-25 bis AC-40) | Vorgänger-Scheibe (live) | S3b1 setzt voraus: einzige Quelle Alarm-Zeile → Speicherschlüssel, Leser-Rückfall nach Tier-Gates, je-Metrik-`null` = erbt, Top-Level-`null` = No-Op |

### Grün bleiben müssen (S2)

Diese sechs Wächter dürfen durch S2 an keiner Stelle rot werden:

- `tests/test_adr_index_drift.py`
- `tests/test_api_contract_drift.py`
- `tests/test_user_id_default_guard.py`
- `tests/test_router_user_id_required.py`
- `tests/tdd/test_alert_channel_resolution_parity.py`
- `tests/tdd/test_compare_alert_channels.py` — am kritischsten, weil er die
  Delegations-Nachweise für alle vier Vergleichs-Konsumenten führt und S2 genau die
  Datei ändert, die diese Delegation trägt (`compare_alert.py`).

## Implementation Details

1. **Go-Struct-Feld auf beiden Entitäten**, Typ `map[string]interface{}`, JSON-Tag
   `alert_metric_channels,omitempty`:
   - `internal/model/trip.go`: Feld `AlertMetricChannels map[string]interface{}` mit
     `json:"alert_metric_channels,omitempty"` + Docstring, analog zum Muster
     `AlertChannels` (`internal/model/trip.go:151-163`).
   - `internal/model/compare_preset.go`: dasselbe Feld, analog zum Muster
     `AlertChannelThresholds` (`internal/model/compare_preset.go:91-98`).
2. **Trip-PUT-DTO ergänzen UND die `mergeConfigMap`-Zeile setzen — beide zusammen**,
   sonst fällt das Feld beim Trip-PUT still raus (Feld fehlt im DTO) oder ersetzt beim
   Speichern blind alle Metriken (Feld im DTO, aber ohne Merge-Zeile):
   - `internal/handler/trip.go`: DTO-Feld in `tripUpdateRequest` + eine Zeile
     `existing.AlertMetricChannels = mergeConfigMap(existing.AlertMetricChannels, *req.AlertMetricChannels)`
     im Read-Modify-Write-Block, analog zum bestehenden Muster für `DisplayConfig`
     (`internal/handler/trip.go:334-336`).
   - `internal/handler/compare_preset.go` bleibt **unberührt** — der Vergleich-PUT läuft
     bereits generisch über `mergeBriefingPatch` (`internal/handler/briefing_subscription.go:188-196`)
     und mergt jeden Top-Level-Key mit Objekt-Wert automatisch eine Ebene tief. Das
     Go-Struct-Feld aus Schritt 1 ist trotzdem Pflicht: Ohne modelliertes Feld verwirft
     der anschließende typisierte `json.Unmarshal(merged, &p)`
     (`internal/handler/compare_preset.go:292-300`) den Key wieder.
3. **Python: alle drei Stellen zusammen**, nie nur eine oder zwei davon:
   - `src/app/trip.py`: Dataclass-Feld `alert_metric_channels: Optional[dict] = None`,
     analog zum Muster `alert_channels` (`src/app/trip.py:221`).
   - `src/app/loader.py`: Eintrag in `KNOWN_TOP_LEVEL` + `data.get(...)` im Konstruktor +
     bedingtes Zurückschreiben in `_trip_to_dict`, analog zum bestehenden Muster
     (`src/app/loader.py:652,695,1625-1626`). Wird nur der `KNOWN_TOP_LEVEL`-Eintrag
     gesetzt, ohne Dataclass-Feld und Rückschreiben, geht ein zuvor persistierter
     Bestandswert beim nächsten Speichern verloren (Falle `loader.py:657-658`) — daher
     müssen alle drei Stellen in einem Zug entstehen.
   - `src/app/models.py`: optionales typisiertes Feld am `ComparePreset` für Parität.
     Für die Persistenz selbst nicht erforderlich (`compare_preset_to_dict` liefert
     `preset.raw` unverändert zurück, `src/app/loader.py:345-352`), dient aber S2 als
     benannter Leser.
4. **`docs/reference/api_contract.md`** um das neue JSON-Tag `alert_metric_channels`
   ergänzen (beide Entitäten) — Pflicht, sonst wird `tests/test_api_contract_drift.py`
   rot.
5. **ADR-0077** als Fortschreibung von ADR-0046 anlegen: Ablageort (Top-Level auf Trip
   UND ComparePreset), Go-Typ (`map[string]interface{}`), Schlüsselmenge (Analyse-Notiz,
   keine Validierung in S1), Regel „kein Eintrag = erbt den Abo-weiten Kanal-Satz",
   Reihenfolge-Zwang „S2 muss vor S3 kommen" — plus Eintrag in `docs/adr/README.md`.
6. **Tests:** Roundtrip auf beiden `kind`-Werten (Trip, ComparePreset) mit zwei
   verschiedenen Nutzern; Teil-PUT ohne das Feld löscht es nicht; Teil-PUT mit einer
   Metrik löscht die anderen Metriken nicht. Die Trip-Teil-PUT-Tests laufen zwingend auf
   der HTTP-Schicht (`UpdateTripHandler`), nicht gegen `store.SaveTrip` — Begründung
   siehe AC 3/4.

### Mutations-Gegenprobe (Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot
färben:

- `omitempty` am Feld entfernen
- `mergeConfigMap` im Trip-PUT-Handler durch einen Blind-Replace ersetzen (muss AC-4 rot
  färben, sonst ist der Teil-PUT-Test wertlos)
- `KNOWN_TOP_LEVEL`-Eintrag in `src/app/loader.py` entfernen
- `_trip_to_dict`-Rückschreibe-Zeile in `src/app/loader.py` entfernen
- Feld aus dem Trip-DTO (`tripUpdateRequest`) entfernen

### Implementation Details (S2)

1. **Reiner Kern bleibt primitiv** (`src/services/alert_channels.py`): fünfte Eingabe
   `metric_channel_sets: dict[str, set[str]] | None`, umgeschlüsselte Fassung derselben
   Schleife wie `:56-60` (Union je Metrik statt je Regel), Leer-Rückfall-Guard **vor** den
   Tier-Gates (durch S3a/AC-25 abgelöst: Rückfall jetzt nach den Tier-Gates). `effective_alert_channels(subscription, settings, user_id, metrics=None)` —
   der neue Parameter existiert nur am Dispatcher; die acht metrikfreien Aufrufstellen
   ändern sich nicht und können den neuen Arm bauartbedingt nicht auslösen (AC-13).
2. **Katalog-Primitive** (`src/app/metric_catalog.py`): Rückwärts-Lookup
   `summary_field → Kandidaten` plus Wählbarkeits-Tie-Break (bei mehreren Kandidaten
   gewinnt `selectable=True`, bei genau einem Kandidaten gewinnt dieser — deckt `cape` ab).
   Fail-soft-Hülle um `_resolve_metric_id`/`_resolve_corridor_metric_id`: unbekannt oder
   mehrdeutig ohne eindeutigen Tie-Break ⇒ kein Eintrag ⇒ erbt (AC-15), niemals `KeyError`
   oder `ValueError` in den Alarm-Pfad durchlassen.
3. **Trip-Seite:** nur `trip_alert.py:2509` (`_send_alert`) reicht `changes`-Metriken
   durch. `:552` bleibt unberührt — dort wird `eval_result.channels` nirgends
   weiterverwendet und erscheint nur im Protokoll (`trip_alert.py:730`); ein Test, der
   bei `:552` grün wird, beweist folglich nichts über den tatsächlichen Versand.
4. **Vergleichs-Seite — Asymmetrie:** `compare_alert.py:601` (`_build_eval_config`) bleibt
   unverändert und liefert weiter den preset-weiten Startwert; die auslösenden Metriken
   sind dort noch nicht bekannt. Der metrik-bewusste Aufruf gehört in die bestehende
   Ortsschleife `:286-293`, wo `t["changes"]` je Ort vorliegt (AC-16). Dabei muss die
   Vorbelegung von `ids_by_channel` (heute nur aus `config.channels`) auch Kanäle
   abdecken, die erst durch einen Metrik-Eintrag hinzukommen — sonst wirft `:293` einen
   `KeyError` und der ganze Vergleichs-Alarm für den Ort fällt aus (AC-17).
5. **Migration** (`src/app/loader.py`, Muster `:741-753`): je aktiver, **aktivierter**
   Regel die Metrik(en) über `_ALERT_METRIC_TO_CATALOG_ID` auflösen (eins-zu-viele bei
   `TEMPERATURE_MIN`/`SNOW_LINE`, Wählbarkeits-Tie-Break bei `TEMPERATURE_MIN` ⇒ nur
   `temperature`), Kollisionen auf derselben `metric_id` unionieren, leere Regel-
   Kanallisten erzeugen **keinen** Schlüssel (kein `{}`), deaktivierte Regeln liefern
   keinen Beitrag, ein Trip ohne migrationsfähige Regel-Kanäle bekommt kein Feld
   (`omitempty` bleibt wirksam). Read-Modify-Write mit Merge — bestehende
   `alert_metric_channels`-Einträge und alle anderen Felder bleiben unangetastet
   (BUG-DATALOSS-GR221, #102).
6. **Renderer-Gate-Weg (i), entschieden:** `src/output/renderers/alert/project.py` wird
   angefasst und auf die Katalog-Primitive aus Schritt 2 umgestellt (keine zweite Kopie,
   #1481/ADR-0021). Das löst das Renderer-Mail-Gate aus; der Nachweis läuft über
   **`radar_alert_mail_validator.py`** gegen eine echt zugestellte Staging-Mail aus dem
   Stalwart-Test-Postfach — nicht `briefing_mail_validator.py` und nicht
   `email_spec_validator.py`.
7. **ADR-0077 Punkt 3 wird ergänzt, nicht abgelöst:** Zusatz „Das Lese-Vokabular legt S2
   fest (Katalog-`metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt); die
   verbindliche, validierte Menge samt Editor-Anzeige und Bestandsdaten-Prüfung bleibt
   S3." Kein neues ADR, kein Status-Wechsel — `tests/test_adr_index_drift.py` bleibt
   unberührt.

#### Mutations-Gegenprobe (S2, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot
färben:

- Ein Metrik-Argument an einer der acht metrikfreien Aufrufstellen (z. B. Radar oder
  amtliche Warnung) ergänzen → muss AC-13 rot färben. **Vorbedingung an der Fixture:**
  `alert_metric_channels` muss einen Eintrag für eine Metrik tragen, die im
  Radar-/amtlichen Alarm nicht vorkommt, und dieser Eintrag muss von der abo-weiten
  Kanalmenge abweichen — sonst ist die Mutation bei leerem oder deckungsgleichem
  `alert_metric_channels` strukturell unbeobachtbar und bleibt grün.
- Den Leer-Rückfall-Guard entfernen → muss AC-12 rot färben. (Die S2-Mutation „Guard hinter
  die Tier-Gates verschieben" ist seit S3a überholt: S3a schreibt genau diese Lage vor; die
  Gegen-Mutation „Rückfall wieder vor die Gates" steht in der Mutations-Gegenprobe (S3a).)
- Den Migrations-/Lese-Arm auf die heutige preset-weite Regel-Union (ohne Metrik-Filter)
  umstellen → muss AC-10/AC-11/AC-23 rot färben (S2 hätte sonst keine Wirkung, ADR-0043).
- Die `ids_by_channel`-Vorbelegung in der Ortsschleife auf reines `config.channels`
  zurücksetzen → muss AC-17 rot färben (`KeyError`).
- Den Wählbarkeits-Tie-Break entfernen, sodass `temp_min_c` auf `temperature_cold` statt
  `temperature` mappt → muss AC-14 rot färben.
- Eine deaktivierte Regel in die Migration einschließen → muss AC-20 rot färben.
- Eine leere Regel-Kanalliste als `{}` statt als weggelassenen Schlüssel migrieren → muss
  AC-19 rot färben.
- An der neuen Lesestelle `user_id` durch `"default"` ersetzen → muss AC-24 und
  `tests/test_user_id_default_guard.py` rot färben.

### Implementation Details (S3a)

1. **Rückfall nach den Tier-Gates (E7).** In `resolve_alert_channels` wird der bisherige
   Leer-Rückfall-Guard (Schritt 4, vor den Gates) durch eine Auswertung **nach** den Gates
   ersetzt: Zuerst die Tier-Gates auf den Metrik-Arm-Satz anwenden. Ist das Ergebnis leer,
   gilt der Satz ohne Metrik-Arm (Ergebnis aus override/Regel-Union/geerbt), ebenfalls nach
   denselben Tier-Gates. Die Gates selbst (`sms_allowed`, `premium_sms_allowed`) bleiben
   unverändert und werden weiterhin genau einmal je Satz angewandt (SMS/Premium-SMS ohne
   Tarif bleiben gestrichen — vereinbar mit #2279 S1 AC-4). Ist auch der Satz ohne Metrik-Arm
   nach den Gates leer, bleibt das Ergebnis leer (heutiges Verhalten des Abo-Satzes).
   Docstring Schritt 4/5 entsprechend umschreiben.
2. **Kanal-Schwelle bleibt dahinter (Entscheidung).** `split_by_threshold` (ADR-0046) läuft bei
   den Aufrufern (`trip_alert.py`, `compare_alert.py`) **nach** der Auflösung und bleibt
   unverändert; der Rückfall wird **nicht** dahinter gezogen. Die Schwelle je Kanal ist eine
   bewusste Nutzerwahl, und dasselbe Verhalten gilt heute schon für den Abo-Satz. Das ist ein
   benanntes Restrisiko (Known Limitations S3a), kein Fehler dieser Scheibe.
3. **Eine Funktion für die Schlüssel-Zuordnung (E2/E3).** `alert_metric_channel_keys()` in
   `weather_change_detection.py` leitet je `AlertMetric` die Speicherschlüssel **aus der Sicht
   des Lesers** ab: die Summary-Felder, die der Detektor für diese Zeile scharf stellt
   (`_ALERT_METRIC_TO_SUMMARY_FIELD` bzw. `_ALERT_DELTA_METRIC_TO_FIELDS`), werden über die
   Leser-Primitive `alert_channels._metric_id_for_summary_key` aufgelöst; der Wert je Zeile ist
   die **sortierte Liste** dieser Schlüssel. Damit gibt es keine zweite Zeile-zu-Schlüssel-Liste
   (Wächter #1480) und keine handgepflegte Ausnahme: Was der Leser liest, bietet der Endpunkt
   an. Gemessen 2026-11-03 (Detektor real, Regeln aus `expand_per_metric_levels`): 14 Zeilen
   tragen genau einen Schlüssel, **`wind_change` trägt zwei** (`["gust", "wind"]`), weil die
   Windänderung `wind_max_kmh` **und** `gust_max_kmh` beobachtet und der Leser das Böen-Feld als
   `gust` liest. `snowfall_limit` ist Legacy-Schlüssel und kommt in `keys` **nie** vor (der
   Detektor meldet `snow_line` über `freezing_level_m`); eine einzige benannte Konstante
   `_LEGACY_ONLY_CHANNEL_KEYS = {"snowfall_limit"}` nimmt ihn in `accepted` auf, weil die
   Legacy-Migration ihn schreibt. Rückgabe: `keys` (AlertMetric-Wert → sortierte Liste der
   Schlüssel) und `accepted` (sortierte Liste = Vereinigung aller Listen in `keys` ∪
   `_LEGACY_ONLY_CHANNEL_KEYS`). Beispiele: `wind_gust→[gust]`, `wind_change→[gust, wind]`,
   `temperature_min`/`temperature_max`/`temperature_change→[temperature]`,
   `thunder_level`/`thunder_onset→[thunder]`, `precipitation_sum`/`precipitation_change`/
   `precipitation_heavy_onset→[precipitation]`, `snow_line`/`freezing_level→[freezing_level]`,
   `cape→[cape]`, `fresh_snow→[fresh_snow]`, `visibility→[visibility]`. `humidity` hat kein Summary-Feld (ADR-0010) und fehlt. Der Wählbarkeits-
   Tie-Break der Migration (`loader.py::_katalog_ids_fuer_alarm_metrik`) bleibt, wo er ist —
   die Schlüssel-Funktion braucht ihn nicht mehr, AC-33 prüft die Verträglichkeit beider.
4. **Endpunkt statt `aggregations[]`.** `aggregations[]` in `/api/metrics` wird vom Wertebereiche-
   Editor als wählbare Auswertung gelesen, und `cape` (`selectable=False`) fehlt dort ganz;
   die Antwort bleibt daher unverändert. Neu: `GET /alert-metric-channel-keys` →
   `{"keys": {…}, "accepted": […]}`, Go-Proxy `GET /api/alert-metric-channel-keys` in
   derselben Auth-Gruppe wie `/api/metrics`. Die Antwort hängt von keinem Nutzer ab.
5. **Keine Go-Schreibvalidierung (E3).** Go besitzt keinen Katalog (eine Kopie wäre Drift),
   ADR-0077 Punkt 3 warnt vor Bestandsbruch, der Leser ist fail-soft (unbekannter Schlüssel ⇒
   erbt). Die Prüfung der Schlüsselmenge geschieht ausschließlich durch den zeilenweisen
   Wirk-Test (AC-32), nicht durch eine Laufzeit-Validierung.
6. **`null` (E4/E8).** Je Metrik bedeutet `{"gust": null}` „erbt" (persistiert als `null`,
   `config_merge.go:18-20`; Leser behandelt ihn als kein Eintrag). Top-Level
   `"alert_metric_channels": null` ist beim Trip No-Op (`handler/trip.go:375`, Pointer-DTO) und
   wird beim Ortsvergleich in `mergeBriefingPatch` (`briefing_subscription.go:200`, von
   `applyComparePresetPatch` für beide Ortsvergleichs-PUT-Wege genutzt) für **genau dieses
   Feld** übersprungen. Keine allgemeine „null = No-Op"-Regel: für andere Top-Level-Felder (z. B.
   `activity_profile: null`) überschreibt `null` den Bestandswert wie bisher (`base[k] = v`, AC-37).
7. **ADR-0077-Nachtrag „S3a"** (kein neues ADR): (a) gültige Schlüsselmenge und ihre einzige
   Definition (`alert_metric_channel_keys()`), (b) Rückfall nach Tier-Gates (ersetzt die
   S2-Aussage „kein Fall für den Rückfall", die nur in S2-Spec und Docstring stand; ADR-0077
   selbst enthielt keine Aussage zum Tier-Gate-Verhalten), (c) `null`-Eintrag je Metrik =
   „erbt", (d) keine Go-Schreibvalidierung samt Begründung. Statuszeile und Index-Eintrag
   bleiben unverändert.

#### Mutations-Gegenprobe (S3a, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen müssen jeweils mindestens einen Test rot färben:

- Den Rückfall wieder **vor** die Tier-Gates verschieben (alter Guard) → muss AC-25 rot färben.
- Den Rückfall auch das Tier-Gate des Rückfall-Satzes überspringen lassen (SMS ohne Tarif
  rutscht über den Rückfall wieder hinein) → muss AC-26 rot färben.
- Den Rückfall entfernen (leer bleibt leer) → muss AC-25 und AC-28 rot färben.
- Die Endpunkt-Abbildung `snow_line→[snowfall_limit]` statt `→[freezing_level]` → muss AC-30
  und AC-32 rot färben.
- `humidity` oder `snowfall_limit` als Ziel in `keys` aufnehmen → muss AC-31 rot färben.
- Die Schlüssel-Funktion durch eine handgeschriebene zweite Liste ersetzen, in der eine Zeile
  abweicht → muss AC-32 rot färben (zeilenweise Mengengleichheit, keine ⊆-Kette).
- `wind_change` auf nur einen Schlüssel kürzen (`[wind]`, das Böen-Feld fällt weg) → muss
  AC-30 und AC-32 rot färben.
- Die Migration einen Schlüssel schreiben lassen, der nicht in `accepted` liegt → muss AC-33
  rot färben.
- Go: das `null`-Überspringen auf **alle** Top-Level-Felder ausdehnen → muss AC-37 rot färben
  (ein anderes Feld mit `null`, z. B. `activity_profile`, bliebe dann unverändert).
- Go: das `null`-Überspringen entfernen → muss AC-36 rot färben.
- Go: den Proxy aus der Auth-Gruppe nehmen → muss AC-35 rot färben.
- `/api/metrics` um die Schlüssel-Zuordnung erweitern (`aggregations[]` verändern) → muss
  AC-34 rot färben.

### Implementation Details (S3b1)

Grundlage: `docs/context/feat-1895-s3b-kanal-spalte.md` Sektion `## Analysis` (F1–F9) und
`docs/context/feat-1895-s3-kanal-spalte.md` (E1–E10). Reines TS-Helper-Modul (jede Regel per
`node --test` prüfbar) plus schlanker Block; kein neuer Backend-Code.

1. **Helper `shared/alarme-tab/alertMetricChannels.ts`.**
   - `ladeKanalSchluessel()`: lädt `GET /api/alert-metric-channel-keys` über einen
     **Modul-Promise-Cache** nach dem Vorbild `compareMetricCatalogLoader.ts:257-273`. Die Antwort
     ist nutzerunabhängig (AC-39 S3a), der Cache daher mandantensicher. **Schlägt der Abruf fehl,
     wird der Promise verworfen** (nicht gecacht), der nächste Aufruf versucht es neu.
   - `kanalZeilen(aktiveMetriken, keys, accepted)`: Vereinigung von `keys[m]` über die aktiven
     Alarm-Zeilen (`effectiveActiveMetrics`), gefiltert auf `accepted`, sortiert und ohne
     Dubletten (F4). Keine zweite Zeile-zu-Schlüssel-Liste im Frontend (Wächter #1480).
   - `normalisiereEintrag(flags)`: liefert immer **alle vier** Flags (`email`, `telegram`, `sms`,
     `premium_sms`) als Boolean oder `null`, wenn kein Kanal gewählt ist (E5).
   - `baueDiff(hydriert, aktuell)`: nur geänderte Einträge, nie eine neu aufgebaute Vollmap;
     Bestandsschlüssel außerhalb der sichtbaren Zeilen kommen nie vor (F5).
   - `hinweise(eintrag, aboSatz)`: Hinweis „Kanal nicht im Abo-Satz aktiv" (E6).
2. **Block `alerts-tab/AlertMetricChannelsBlock.svelte`.** Liegt neben `AlertMetricLevelTable`,
   wird in `AlarmeTab.svelte` nach dem Abschnitt `metric-levels` gemountet (E1). Eine Zeile je
   Speicherschlüssel; Standard „wie Abo-Kanäle" (`null`); Umschalter „eigene Wahl" zeigt vier
   `ChannelToggle` (wiederverwendet), vorbelegt mit dem Abo-Satz (`displayChannelState`); Rückweg
   = Umschalter aus ⇒ `{key: null}` (F7). `premium_sms` nutzt das vorhandene
   `premiumSmsAlarmGate` (F8); für SMS gibt es keinen Tarif-Hinweis (Rückfall AC-25/26 S3a).
   Der Block lädt den Endpunkt selbst (F2), die Mounts bleiben unverändert. Ohne Antwort zeigt er
   „nicht verfügbar" und schreibt nichts (F3). Texte nur über den Katalog
   `messages/{de,en}/alarme.json`.
3. **Wind-Kopplung (F6).** `gust` und `wind` sind zwei eigene Zeilen. Kein Doppelschreiben, kein
   Zustand „gemischt". Beide tragen einen Hinweis: Die Windänderung folgt je nach Auslöser der
   Kanalwahl der Böen- oder der Wind-Zeile.
4. **Hinweis metrikfreie Alarme (E9).** Ein fester Satz im Block: Radar-/Regen-Alarme und amtliche
   Warnungen gehen immer über die Abo-Kanäle.
5. **Speicherweg Trip.** `routeAlertMetricChannels = $state(...)` aus dem Trip; das Feld geht in
   den **bestehenden** `_prevAlarmeJson`-/Dirty-`$effect` und in `buildAlarmeSaveFn` ein, **kein
   zweiter `schedule()`** (F001). `alarmeDeliveryPayload.ts` ergänzt `alert_metric_channels` als
   Top-Level-Feld, nur wenn der Diff nicht leer ist. Anlegen: `tripNewLogic.ts`/`TripNewEditor.svelte`
   (Desktop- und Mobil-Mount) tragen das Feld im Anlege-Payload (E10).
6. **Speicherweg Ortsvergleich.** Wertprop + `onAlarmFeldSetzen` über `alarmZustandsBruecke`;
   `alarmePropsAus.ts`, `compareHubHydration.ts` (Hydration aus dem Preset), `AlarmSnapshot`,
   `ALARM_TOP`, `baueAlarmNutzlast`, Rollback-Feldliste in `alarmeVergleichSpeicherung.ts`;
   `compareEditorSave.ts` (`buildComparePresetSavePayload`, Edit und Create), `CompareNewEditor.svelte`.
   **Rollback:** Einträge, die seit dem Snapshot neu entstanden sind, werden explizit mit `null`
   gesendet, weil der Server je Metrik-Schlüssel ersetzt (`config_merge.go:11-22`,
   `briefing_subscription.go:197-205`) und Weglassen nichts zurücksetzt.
7. **Server-Merge als Randbedingung (gemessen).** Eintrag wird als Ganzes ersetzt ⇒ jeder
   gesendete Eintrag trägt alle vier Flags oder ist `null`; Top-Level-`null` auf
   `alert_metric_channels` ist seit S3a in Trip und Ortsvergleich ein No-Op, daher nie als
   „löschen" einsetzen.
8. **Ratsche.** Keine neue `context===`-Weiche; `context_herkunft_zweige_eingefroren.test.ts`
   wird nach der Änderung neu gemessen (die vier AlarmeTab-Pins), Section-ID zeilenneutral.
   `hardcode_allowlist.json` bleibt `[]`.

#### Mutations-Gegenprobe (S3b1, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen (String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`) müssen jeweils mindestens einen Test rot färben:

- `baueDiff` sendet die komplette Map statt nur der geänderten Einträge → AC-47 und AC-42 rot
  (`snowfall_limit` würde mitgesendet oder überschrieben).
- `normalisiereEintrag` lässt ein Kanal-Flag weg (z. B. `premium_sms`) → AC-44 rot.
- Rollback sendet für seit dem Snapshot neue Einträge kein `null` → AC-56 rot.
- Alle Kanäle abgewählt wird als `{}` bzw. alle-`false` statt `null` gesendet → AC-45 rot.
- Der Endpunkt-Fehler wird gecacht (Promise nicht verworfen) → AC-50 rot.
- Die Trip-Verdrahtung ruft einen zweiten `schedule()` auf statt den bestehenden Dirty-`$effect`
  zu nutzen → AC-54 rot.
- `ALARM_TOP`/Nachbar-Schreiber lassen das Feld fallen → AC-57 rot.
- Der Block schreibt `wind_change` doppelt in `gust` und `wind` → AC-48 rot.

### Implementation Details (S3b2)

Grundlage: `docs/context/feat-1895-s3b2-kanal-hinweise.md` Sektion `## Analysis` (Messergebnisse
1–6). Zwei reine Funktionen im Helper, Anzeige im Block; kein neuer Backend-Code.

1. **Geltungsbereich.** Beide Hinweise erscheinen nur in Zeilen mit **eigener Wahl** (`eintrag`
   nicht `null`) und nur für **gewählte** Kanäle. Zeilen „wie Abo-Kanäle" und der Abo-Satz selbst
   bekommen keinen Hinweis (Scope-Grenze; derselbe Mangel im Abo-Satz ist eine bekannte Lücke,
   siehe Known Limitations S3b2).
2. **`kanaeleOhneEmpfaenger(eintrag, profil)`** liefert die gewählten Kanäle ohne Empfänger.
   `profil` ist `ConnectionProfile | null | undefined`; ist es `null`/unbekannt (nicht geladen),
   ist das Ergebnis leer (nie „kein Empfänger" raten). Bedingungen je Kanal, belegt am
   Python-Transport (`src/output/channels/recipient.py`, `premium_sms.py`):
   - `email`: nie (Konto hat Pflicht-E-Mail).
   - `telegram`: `!telegram_chat_id` (Transport: `telegram_no_chat_id`).
   - `sms`: `!sms_to || sms_allowed === false || !sms_verified` (Transport: `sms_no_recipient`).
     Das ist **dieselbe Definition** wie in `channelConnectionStatus` (Zweig „nicht verbunden" bzw.
     „eingetragen, unbestätigt"); keine zweite Ableitung mit abweichender Bedingung.
   - `premium_sms`: `premium_sms_reply_state` ∈ {`none`, `stale`}. Gemessen: der **Alarmpfad blockt
     tatsächlich** bei fehlender oder veralteter Rückadresse (jede Alarm-Sendestelle ruft
     `notification_service._premium_sms_output()` → `PremiumSmsRecipient.for_user` →
     `check_reply_address`; „bewusst ohne Bereitschaftsfrage" betrifft nur `can_send_*()`, nicht die
     Empfängerprüfung). Die Frische-Schwelle gehört dem Server; das Frontend rechnet keine Zeit.
3. **`kanaeleMitSchwelle(eintrag, schwellen)`** liefert die gewählten Kanäle, deren Schwelle in
   `schwellen` (`AlertChannelThresholdState`, aus `displayChannelThresholds`) `MODERATE` oder
   `HIGH` ist, samt Schwelle. **Stufenunabhängig:** das Frontend hat keine einzige Quelle für die
   Dringlichkeit der Metrik-Stufe (Mapping Stufe → LOW/MODERATE/HIGH liegt in
   `services.alert_urgency`); eine zweite Rangtabelle entstünde gegen Wächter #1480/#1481. Der
   Hinweis nennt daher nur die Schwelle des Kanals (Name über `CHANNEL_THRESHOLD_KEYS`) und sagt
   ehrlich, dass schwächere Warnungen über diesen Kanal nicht ankommen. Alle vier Kanäle (auch
   `premium_sms`, #1701 S2b). Schwelle `LOW` ⇒ kein Hinweis.
4. **Block** (`AlertMetricChannelsBlock.svelte`): neue Props `profil` und `schwellen`; je Zeile
   `{#if}` mit `data-testid="kanal-hinweis-kein-empfaenger-<k>"` bzw.
   `data-testid="kanal-hinweis-schwelle-<k>"` (`<k>` = Kanal). Reiner Text, **kein Link**; der Text
   nennt, wo der Empfänger einzutragen ist (Reiter Versand bzw. Profil). Farbe `--g-ink-muted`
   (WCAG-AA). In Ausdrücken kein `(x) as T` (Prüfstand `ohneTypen()`, Nebenbefund #1199).
5. **AlarmeTab**: `alarmProfile` wird im Typ auf `ConnectionProfile` erweitert (gleiche, bereits
   vorhandene Abfrage von `/api/auth/profile`, **keine zweite**), `profileOverride`-Testhaken bleibt;
   `alarmProfile` und `displayChannelThresholds` werden als Props an den Block gegeben. Keine neue
   `context===`-Weiche; `context_herkunft_zweige_eingefroren.test.ts` neu messen.
6. **Texte** nur über den Katalog: `alarme.kanaele.kein_empfaenger` (mit Platzhalter für Kanalnamen
   und Ort) und `alarme.kanaele.schwelle_hinweis` (mit Platzhaltern für Kanalname und Schwellenname)
   in `messages/{de,en}/alarme.json`; Kanalnamen (Protokoll-Token) nicht übersetzen.
7. **Kommentar** in `premiumSmsAlarmGate.ts` (Zeilen 7-14) berichtigen: Das Gate bleibt auf
   `premium_sms_allowed` beschränkt (Sperre der Auswahl), aber die Aussage, der Alarmpfad frage die
   Empfängerprüfung nicht, ist überholt; die Frische wird als Hinweis (S3b2), nicht als Sperre
   gezeigt. Keine Logikänderung.
8. **Nur Anzeige.** Hinweise ändern weder `eintraege`, `onChange`, Payload, Snapshot noch Rollback
   und sperren keinen Schalter und kein Speichern.

#### Mutations-Gegenprobe (S3b2, Pflicht in `/50-implement`)

Mindestens folgende gezielte Verfälschungen (String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`) müssen jeweils mindestens einen Test rot färben; die Hinweise müssen an
der **Bedingung** (Profilfeld bzw. Schwelle) hängen, nicht nur am Text:

- Telegram-Bedingung `!telegram_chat_id` entfernt bzw. invertiert → AC-63 rot.
- SMS-Bedingung ohne `!sms_verified` → AC-64 rot.
- Premium-SMS-Bedingung ohne `stale` (oder ohne `none`) → AC-65 rot.
- E-Mail erhält eine Empfänger-Bedingung → AC-66 rot.
- Profil `null` wird als „kein Empfänger" behandelt → AC-67 rot.
- Hinweise auch für „wie Abo-Kanäle"-Zeilen → AC-68 rot.
- Schwellen-Vergleich `> LOW` wird `>= LOW` bzw. `=== HIGH` → AC-69 bzw. AC-70 rot.
- Der Block sperrt bei Hinweis den Schalter oder das Speichern → AC-72 rot.
- Das Profil kommt aus einem festen Nutzer statt aus dem Auth-Kontext → AC-73 rot.
- Ein Katalogschlüssel fehlt in EN → AC-75 rot.

## Expected Behavior

- **Input:** Trip-PUT bzw. Vergleich-PUT mit optionalem Feld `alert_metric_channels`
  (Objekt, Schlüssel = Metrikname, Wert = beliebige Kanal-Repräsentation, in S1
  unvalidiert).
- **Output:** Persistierter Trip bzw. ComparePreset trägt das Feld unverändert weiter;
  ein Teil-PUT ohne das Feld oder mit nur einer Metrik lässt die übrigen bereits
  gespeicherten Metriken unangetastet.
- **Side effects:** Keine — S1 hat keinen Leser im Alarm-Pfad. Bestandstrips ohne das
  Feld serialisieren dank `omitempty` weiterhin keinen entsprechenden JSON-Schlüssel.

## Acceptance Criteria

- **AC-1:** Given ein Trip eines Nutzers A wird mit dem neuen Feld
  `alert_metric_channels` gespeichert, When der Trip anschließend neu geladen wird,
  Then enthält der geladene Trip exakt dieselben Metrik-Kanal-Zuordnungen wie beim
  Speichern — geprüft für zwei verschiedene Nutzer A und B, damit ausgeschlossen ist,
  dass Daten zwischen Mandanten vermischt werden.
  - Test: HTTP-Roundtrip (Trip anlegen/PUT mit Feld → GET) für Nutzer A und getrennt für
    Nutzer B; beide Antworten enthalten unabhängig voneinander genau ihre eigenen
    gespeicherten Werte, keine Vermischung zwischen den beiden Nutzern.

- **AC-2:** Given ein Ortsvergleich (`ComparePreset`) eines Nutzers wird mit dem neuen
  Feld `alert_metric_channels` gespeichert, When der Vergleich anschließend neu geladen
  wird, Then enthält er dieselben Metrik-Kanal-Zuordnungen wie beim Speichern — geprüft
  für zwei verschiedene Nutzer, als Parität zum Trip-Verhalten aus AC-1.
  - Test: HTTP-Roundtrip (ComparePreset anlegen/PUT mit Feld → GET) für zwei
    unterschiedliche Nutzer; beide erhalten unabhängig genau ihre eigenen Werte zurück.

- **AC-3:** Given ein Trip hat bereits gespeicherte Metrik-Kanal-Zuordnungen, When ein
  weiterer Trip-PUT geschickt wird, der das Feld `alert_metric_channels` gar nicht
  enthält, Then bleiben die zuvor gespeicherten Zuordnungen nach diesem PUT unverändert
  erhalten — ein Teil-Update löscht das Feld nicht.
  - Test: Auf HTTP-Ebene über `UpdateTripHandler` (nicht gegen `store.SaveTrip`, da der
    Merge in `internal/handler` sitzt und der Store das Struct nur transparent
    durchreicht): Trip mit Feld anlegen, dann PUT ohne dieses Feld im Body senden,
    anschließend per GET prüfen, dass die ursprünglichen Metrik-Kanal-Zuordnungen noch
    vollständig vorhanden sind.

- **AC-4:** Given ein Trip hat gespeicherte Kanal-Zuordnungen für mehrere Metriken
  (z. B. Regen und Wind), When ein Trip-PUT nur die Zuordnung einer einzelnen Metrik
  (z. B. Regen) ändert, Then bleiben die Zuordnungen der übrigen, im PUT nicht genannten
  Metriken (z. B. Wind) unverändert erhalten.
  - Test: Auf HTTP-Ebene über `UpdateTripHandler` (aus demselben Grund wie AC-3): Trip
    mit Zuordnungen für mindestens zwei Metriken anlegen, PUT senden, das nur eine der
    beiden Metriken im Feld `alert_metric_channels` enthält, anschließend per GET
    prüfen, dass die nicht genannte Metrik weiterhin ihren ursprünglichen Wert trägt.

- **AC-5:** Given ein Ortsvergleich hat gespeicherte Kanal-Zuordnungen für mehrere
  Metriken, When ein Vergleich-PUT nur die Zuordnung einer einzelnen Metrik ändert,
  Then bleiben die Zuordnungen der übrigen Metriken unverändert erhalten. **Hinweis:**
  Diese AC charakterisiert vorbestehendes, generisches Verhalten des
  Vergleich-PUT-Pfads (`mergeBriefingPatch` mergt jeden Top-Level-Key mit Objekt-Wert
  bereits automatisch) — sie bewacht keinen für diese Spec neu geschriebenen Merge,
  sondern das in Schritt 1 hinzugefügte Go-Struct-Feld selbst: Ohne dieses Feld würde
  der anschließende typisierte Unmarshal den Schlüssel `alert_metric_channels` beim
  Laden wieder verwerfen.
  - Test: Auf HTTP-Ebene über den Vergleich-PUT-Handler (nicht gegen den Store):
    ComparePreset mit Zuordnungen für mindestens zwei Metriken anlegen, PUT senden, das
    nur eine der beiden Metriken enthält, anschließend per GET prüfen, dass die nicht
    genannte Metrik weiterhin ihren ursprünglichen Wert trägt.

- **AC-6:** Given ein Trip wurde vor dieser Änderung bereits mit einem Wert im Feld
  `alert_metric_channels` in der Python-Datenhaltung gespeichert (vorbefüllter
  Bestandswert), When dieser Trip von der Python-Schicht geladen und anschließend wieder
  zurückgeschrieben wird, Then bleibt der Wert erhalten — das bewacht, dass alle drei
  Python-Stellen (`KNOWN_TOP_LEVEL`-Eintrag, Dataclass-Feld, Rückschreiben in
  `_trip_to_dict`) gemeinsam gesetzt sind und keine davon fehlt.
  - Test: Eine Trip-Datei mit vorbefülltem `alert_metric_channels`-Wert direkt in der
    Python-Datenhaltung ablegen, den Trip über den Python-Lade-/Speicherpfad laden und
    zurückschreiben, danach die Datei erneut lesen und prüfen, dass der Wert
    unverändert vorhanden ist.

- **AC-7:** Given ein Trip wurde ohne das Feld `alert_metric_channels` angelegt (Feld
  nicht gesetzt), When der Trip als JSON serialisiert wird, Then enthält die Ausgabe
  keinen Schlüssel `alert_metric_channels` — Bestandstrips bleiben dadurch byte-gleich
  zum Zustand vor dieser Änderung, das neue Feld ist verhaltensneutral.
  - Test: Einen Trip ohne das Feld über die HTTP-Schicht anlegen/laden und die
    JSON-Antwort auf Abwesenheit des Schlüssels `alert_metric_channels` prüfen (dies ist
    kein Dateiinhalt-Check auf Quellcode, sondern eine Prüfung des tatsächlich
    ausgelieferten API-Antwortkörpers).

- **AC-8:** Given das neue JSON-Tag `alert_metric_channels` existiert an `Trip` und
  `ComparePreset`, When `tests/test_api_contract_drift.py` läuft, Then findet der Test
  eine passende Erwähnung des Tags in `docs/reference/api_contract.md` und bleibt grün.
  - Test: `tests/test_api_contract_drift.py::test_every_model_json_tag_is_documented`
    ausführen und auf Exit-Code 0 prüfen.

- **AC-9:** Given ADR-0077 wurde als Fortschreibung von ADR-0046 angelegt und in
  `docs/adr/README.md` verlinkt, When `tests/test_adr_index_drift.py` läuft, Then bleibt
  der Test grün, weil Datei und Index-Eintrag übereinstimmen.
  - Test: `tests/test_adr_index_drift.py` ausführen und auf Exit-Code 0 prüfen.

### Acceptance Criteria (S2 — Leser + Migration)

- **AC-10:** Given ein Abweichungsalarm für einen Trip trägt mehrere ausgelöste Metriken
  (`changes`) und für mindestens eine dieser Metriken existiert ein Eintrag in
  `alert_metric_channels`, When der Alarm bei `trip_alert.py:2509` (`_send_alert`)
  tatsächlich versendet wird, Then enthält die dort verwendete Kanalmenge für jede
  ausgelöste Metrik `m` genau `Eintrag(m)` falls vorhanden, sonst die Kanäle der aktiven
  Regel(n) dieser Metrik, sonst den geerbten Satz — als Vereinigung über alle ausgelösten
  Metriken, nicht als das bisherige preset-weite Ergebnis.
  - Test: Trip mit Eintrag `{telegram}` für Metrik X, keinem Eintrag für Metrik Y,
    geerbtem Satz `{email, telegram}` — ein Alarm über X **und** Y liefert bei
    `trip_alert.py:2509` den versandten Satz `{email, telegram}` (Y's Anteil zieht ihn
    nach oben); derselbe Alarm ausschließlich über X liefert dort `{telegram}`. Gemessen
    an `trip_alert.py:2509`, ausdrücklich **nicht** an `:552` — ein Test, der dort grün
    wird, beweist über den tatsächlichen Versand nichts, weil `:552` nur protokolliert
    und der Versand bei `:2509` unabhängig neu auflöst.

- **AC-11:** Given ein Vergleichs-Abweichungsalarm löst für einen Ort mehrere Metriken
  aus und für mindestens eine dieser Metriken existiert ein Eintrag in
  `alert_metric_channels`, When der Alarm bei `compare_alert.py:335`
  (`send_multi_location_deviation_alert`) tatsächlich versendet wird, Then trägt die für
  diesen Ort verwendete Kanalmenge dieselbe dreiarmige Union je Metrik wie beim Trip
  (AC-10) — als Parität zur Trip-Seite, nicht das unveränderte preset-weite
  `config.channels`, das `compare_alert.py:601` weiterhin nur als Startwert liefert.
  - Test: Preset mit `config.channels={email}` und Metrik-Eintrag `{telegram}` für Metrik
    X, kein Eintrag für Metrik Y — ein Ort löst über X **und** Y aus: der versandte Satz
    für diesen Ort ist `{email, telegram}` (Y erbt `config.channels`, die Union hebt X's
    Verengung wieder an). Gemessen an `compare_alert.py:335`, nicht an `:601` allein.

- **AC-12:** Given die dreiarmige Union je Metrik ergibt für einen Alarm eine leere
  Kanalmenge, während dieselbe Kanalmenge ohne den Metrik-Arm (Ergebnis der bisherigen
  drei Schritte override/Regel-Union/geerbt) nicht leer wäre, When die Kanalmenge
  gebildet wird, Then gilt der Satz ohne Metrik-Arm — ein explizit leeres `override`
  ersetzt dabei weiterhin vollständig auch ins Leere (`alert_channels.py:49-50`).
  **Seit S3a gilt der Zeitpunkt des Rückfalls nach AC-25 (nach den Tier-Gates);** die
  frühere S2-Fassung „vor den Tier-Gates, ein nachgelagertes Tier-Gate darf die Menge danach
  auf leer führen" ist durch AC-25 abgelöst.
  - Test: Fall mit nicht-leerem Ergebnis ohne Metrik-Arm und leerendem Metrik-Arm prüft
    Rückfall; Fall mit explizit leerem `override` bleibt unverändert leer. Der frühere
    S2-Fall „Tier-Gate-Kürzung nach nicht-leerem Metrik-Arm bleibt leer" wird in S3a
    umgekehrt (siehe AC-25).

- **AC-13:** Given `alert_metric_channels` trägt einen Eintrag für eine Metrik, die in
  einem Radar-/Nowcast-Alarm oder einer amtlichen Warnung strukturell nicht vorkommt, und
  dieser Eintrag weicht von der abo-weiten Kanalmenge ab, When ein Radar-Alarm
  (`trip_alert.py:1671`, `compare_radar_alert.py:168`) oder eine amtliche Warnung
  (`trip_alert.py:2726`, `compare_official_alert.py:472`) versendet wird, Then bleibt die
  dabei verwendete Kanalmenge exakt die abo-weite Menge von vor dieser Scheibe, weil
  diese acht Aufrufstellen den Metrik-Parameter der Auflösung nicht übergeben.
  - Test: Mutations-Gegenprobe mit der in „Implementation Details (S2)" benannten
    Fixture-Vorbedingung (abweichender, nicht im Radar-/amtlichen Pfad vorkommender
    Metrik-Eintrag) — sonst ist die Mutation strukturell unbeobachtbar.

- **AC-14:** Given ein Alarm meldet eine Änderung mit dem rohen Summary-Key
  `temp_min_c`, When der Kanal-Schlüssel für diese Metrik aufgelöst wird, Then lautet der
  Schlüssel `temperature` — der wählbare Katalog-Eintrag — und niemals
  `temperature_cold`; derselbe Summary-Key liefert auf der Trip-Seite und auf der
  Vergleichs-Seite denselben Kanal-Schlüssel.
  - Test: Erweiterung der bestehenden 16er-Paritätsmatrix
    (`test_alert_channel_resolution_parity.py:225`) um den `temp_min_c`-Fall, geprüft in
    beiden Flächen.

- **AC-15:** Given ein Summary-Key lässt sich keiner Katalog-`metric_id` eindeutig
  zuordnen (unbekannt, oder mehrdeutig ohne eindeutigen Wählbarkeits-Tie-Break), When die
  Kanal-Auflösung für diese Metrik versucht wird, Then wirft sie weder `KeyError` noch
  `ValueError`, sondern behandelt die Metrik wie eine ohne Eintrag — sie erbt den
  abo-weiten Satz.
  - Test: unbekannten und mehrdeutigen Summary-Key gegen die Auflösung fahren, Ergebnis
    ist der geerbte Satz, kein geworfener Fehler.

- **AC-16:** Given zwei Orte desselben Vergleichs-Alarms lösen unterschiedliche Metriken
  mit unterschiedlichen Einträgen in `alert_metric_channels` aus (Ort 1 nur Metrik X mit
  Eintrag `{telegram}`, Ort 2 nur Metrik Z mit Eintrag `{sms}`, beide ohne Tier-Sperre),
  When der Vergleichs-Alarm versendet wird, Then erhält Ort 1 den Kanalsatz `{telegram}`
  und Ort 2 unabhängig davon `{sms}` — zwei verschiedene Kanalsätze im selben Alarmlauf.
  Das ist nur möglich, wenn die metrik-bewusste Auflösung **je Ort** in der Ortsschleife
  (`compare_alert.py:286-293`, wo `t["changes"]` je Ort vorliegt) geschieht, nicht einmal
  preset-weit bei `compare_alert.py:601` (`_build_eval_config`), wo die ausgelösten
  Metriken noch unbekannt sind und `:601` weiterhin nur den unveränderten Startwert
  liefert.
  - Test: Vergleichs-Alarm mit den zwei oben beschriebenen Orten versenden und prüfen,
    dass Ort 1 ausschließlich über `telegram` und Ort 2 ausschließlich über `sms`
    erreicht wird — nicht beide über die Vereinigung `{telegram, sms}`.

- **AC-17:** Given ein Metrik-Eintrag in `alert_metric_channels` fügt für einen Ort einen
  Kanal hinzu, der nicht in `config.channels` enthalten ist, When `ids_by_channel` in der
  Ortsschleife (`compare_alert.py:286-293`) für diesen Kanal beschrieben wird, Then löst
  das keinen `KeyError` aus, und der Vergleichs-Alarm für diesen Ort fällt dadurch nicht
  komplett aus.
  - Test: Preset mit `config.channels={email}` und Metrik-Eintrag `{telegram}` für die
    auslösende Metrik eines Orts — Alarm für diesen Ort wird versendet, kein
    unbehandelter `KeyError`.

- **AC-18:** Given eine aktive, aktivierte Regel mit `AlertMetric`-Wert
  `TEMPERATURE_MIN` oder `SNOW_LINE` bildet laut `_ALERT_METRIC_TO_CATALOG_ID` auf
  mehrere Katalog-`metric_id`s ab, und mehrere aktivierte Regeln bilden auf dieselbe
  `metric_id` ab, When die Migration `alert_rules[].channels` → `alert_metric_channels`
  läuft, Then entsteht für `TEMPERATURE_MIN` nur der wählbare Eintrag `temperature`
  (Tie-Break aus AC-14), für `SNOW_LINE` entstehen beide Einträge `snowfall_limit` und
  `freezing_level`, und bei mehreren Regeln auf derselben `metric_id` enthält der
  migrierte Eintrag die Vereinigung aller ihrer Kanäle.
  - Test: Migrations-Lauf mit je einer `TEMPERATURE_MIN`- und einer `SNOW_LINE`-Regel
    sowie zwei Regeln auf derselben `metric_id` mit unterschiedlichen Kanälen.

- **AC-19:** Given eine aktive, aktivierte Regel hat eine leere Kanalliste (bedeutet
  „erbt"), When die Migration für die Metrik(en) dieser Regel läuft, Then erzeugt die
  Migration dafür **keinen** Schlüssel in `alert_metric_channels` — insbesondere schreibt
  sie kein `{}` —, weil ein leeres Dict laut `alert_channels.py:49-50` als vollständiges
  Override ins Leere gelesen würde.
  - Test: Regel mit leerer Kanalliste migrieren, anschließend prüfen, dass die
    zugehörige Metrik in `alert_metric_channels` keinen Schlüssel trägt.

- **AC-20:** Given eine Regel mit gesetzten Kanälen ist deaktiviert (`enabled=False`),
  When die Migration läuft, Then wandern die Kanäle dieser Regel nicht in
  `alert_metric_channels` — eine heute wirkungslose Regel darf durch die Migration nicht
  aktiv werden.
  - Test: deaktivierte Regel mit Kanälen migrieren, anschließend prüfen, dass die
    zugehörige Metrik in `alert_metric_channels` keinen Eintrag aus dieser Regel trägt.

- **AC-21:** Given ein Trip hat keine aktive, aktivierte Regel mit gesetzten Kanälen,
  When die Migration läuft, Then bleibt `alert_metric_channels` für diesen Trip
  ungesetzt — kein leeres Objekt, `omitempty` bleibt wirksam.
  - Test: Trip ohne migrationsfähige Regel-Kanäle migrieren, JSON-Antwort auf Abwesenheit
    des Schlüssels prüfen.

- **AC-22:** Given ein Trip trägt bereits andere gespeicherte Felder (u. a. einen
  bestehenden `alert_metric_channels`-Eintrag einer anderen Metrik), When die Migration
  für diesen Trip läuft, Then bleiben alle anderen Felder und bereits vorhandenen
  Einträge per Read-Modify-Write mit Merge vollständig erhalten (BUG-DATALOSS-GR221,
  #102) — nachgewiesen per Roundtrip sowohl über den Go-Handler als auch über den
  Python-Lader.
  - Test: Trip mit Bestandsfeldern und vorhandenem `alert_metric_channels`-Eintrag durch
    Go-Handler-Roundtrip UND separat durch Python-Lader-Roundtrip schicken, danach beide
    Ergebnisse auf Vollständigkeit prüfen.

- **AC-23:** **🔴 Bestandsdaten-Verengung, PO-freigabepflichtig.** Given ein Bestands-Trip
  hat heute eine aktive Regel A mit Kanal `telegram` auf Metrik X und eine aktive Regel B
  mit Kanal `email` auf Metrik Y, sodass ein Alarm, der ausschließlich Metrik X auslöst,
  vor der Migration `telegram ∪ email` erreicht (heutige regelübergreifende Union,
  unabhängig von der auslösenden Metrik, `_trip_channel_inputs:92`), When die Migration
  läuft und anschließend ein Alarm ausschließlich über Metrik X ausgelöst wird, Then
  erreicht dieser Alarm nur noch `telegram` — die Kanalmenge verengt sich für
  Bestandsnutzer dadurch bewusst und ohne jede Nutzerhandlung auf die tatsächlich zur
  auslösenden Metrik gehörenden Kanäle. Das ist die Reparatur des in #1895 gemeldeten
  Fehlers (die Kanalzuordnung hing an der falschen Entität), keine Regression.
  - Test: Bestandsdaten mit den beiden beschriebenen Regeln anlegen, Migration
    ausführen, danach einen Alarm ausschließlich über Metrik X simulieren und prüfen,
    dass die versandte Kanalmenge exakt `{telegram}` ist, nicht `{telegram, email}`.

- **AC-24:** Given zwei verschiedene Nutzer A und B haben je eigene Trips mit
  unterschiedlichen `alert_metric_channels`-Einträgen und unterschiedlichen aktiven
  Regeln, When die neue Kanal-Auflösung bzw. die Migration für Nutzer A ausgeführt wird,
  Then verwendet sie ausschließlich die echte `user_id` von Nutzer A und liest oder
  schreibt an keiner Stelle Daten von Nutzer B oder unter dem Platzhalter `"default"`.
  - Test: Auflösung und Migration unabhängig für Nutzer A und für Nutzer B ausführen,
    beide Ergebnisse tragen ausschließlich die eigenen Daten; zusätzlich bewacht durch
    `tests/test_user_id_default_guard.py` (ADR-0003).

### Acceptance Criteria (S3a — Rückfall, Schlüssel-Quelle, Go-Angleichung)

Nummerierung setzt AC-24 (S2) fort. Alle ACs dieser Scheibe sind Backend-/Vertrags-ACs;
nutzerseitig sichtbar wird nichts (kein Frontend in S3a).

- **AC-25:** Given der Metrik-Arm einer Auflösung ist nicht leer, wird aber durch die
  Tier-Gates vollständig gestrichen (z. B. Eintrag `{sms}` bei Nutzer ohne SMS-Tarif, oder
  `{premium_sms}` ohne Premium-SMS-Tarif), und der Satz ohne Metrik-Arm (override/Regel-Union/
  geerbt) ist nach den Gates nicht leer, When die Kanalmenge gebildet wird, Then gilt der Satz
  ohne Metrik-Arm nach den Tier-Gates — der Alarm bleibt zustellbar, statt leer zu werden.
  - Testart: Kern (reiner Python-Test, kein Netz). Prüfling: `resolve_alert_channels` in
    `src/services/alert_channels.py`; der bisherige S2-Test
    `test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren` wird umgekehrt
    und prüft genau diesen Rückfall (Metrik-Arm `{sms}`, kein Tarif, geerbt `{email}` ⇒
    `{email}`).

- **AC-26:** Given der Rückfall nach AC-25 greift und der Satz ohne Metrik-Arm enthält selbst
  einen tarifgesperrten Kanal (`sms` oder `premium_sms` ohne Tarif), When die Kanalmenge
  gebildet wird, Then bleibt dieser Kanal gestrichen; ist der Satz ohne Metrik-Arm nach den
  Gates ebenfalls leer, bleibt das Ergebnis leer (heutiges Abo-Satz-Verhalten, unverändert),
  und ein explizit leeres `override` ersetzt weiterhin vollständig ins Leere.
  - Testart: Kern. Prüfling: `resolve_alert_channels`; Fälle: geerbt `{sms}` ohne Tarif ⇒
    leer; Metrik-Arm `{sms}` + geerbt `{sms}` ohne Tarif ⇒ leer; leeres `override` ⇒ leer;
    mit Tarif bleibt `sms` erhalten (Regression zu #2279 S1 AC-4).

- **AC-27:** Given der Metrik-Arm ist nach den Tier-Gates nicht leer (z. B. `{telegram}`),
  When die Kanalmenge gebildet wird, Then ersetzt er den Satz ohne Metrik-Arm weiterhin
  vollständig (S2 AC-10/AC-11) — der Rückfall greift nur bei leerem Metrik-Arm nach den Gates,
  und der Fall ohne Metrik-Arm-Eingabe (die acht metrikfreien Aufrufstellen, AC-13) bleibt
  byte-gleich zu vorher.
  - Testart: Kern. Prüfling: `resolve_alert_channels`, bestehende S2-Tests
    (`tests/tdd/test_alert_metric_channel_reader.py`, `test_alert_channel_resolution_parity.py`)
    bleiben grün.

- **AC-28:** Given ein Trip bzw. Ortsvergleich trägt für die auslösende Metrik einen Eintrag
  `{sms}`, der Nutzer hat keinen SMS-Tarif und der geerbte Satz ist `{email}`, When der
  Abweichungsalarm tatsächlich versendet wird (`trip_alert.py:2509` bzw. die Ortsschleife
  `compare_alert.py:286-293`), Then geht er über `email` und nicht an niemanden.
  - Testart: Kern. Prüfling: Trip-Versandpfad und Vergleichs-Ortsschleife (am Versand
    gemessen, nicht nur an `resolve_alert_channels`); Parität beider Flächen.

- **AC-29:** Given der Rückfall nach AC-25 liefert einen Kanalsatz und ein Kanal darin hat eine
  Kanal-Schwelle (ADR-0046), die über der Dringlichkeit des Alarms liegt, When der Alarm
  verteilt wird, Then wirkt `split_by_threshold` unverändert **nach** der Auflösung — der
  Rückfall wird nicht dahinter gezogen (bewusste Nutzerwahl der Schwelle; benanntes
  Restrisiko, Known Limitations S3a).
  - Testart: Kern. Prüfling: bestehende Schwellen-Tests (`trip_alert.py`, `compare_alert.py`)
    bleiben unverändert grün; ein Test hält fest, dass die Auflösung ihre Kanalmenge
    **ohne** Kenntnis der Schwelle liefert.

- **AC-30:** Given der Python-Core läuft, When `GET /alert-metric-channel-keys` aufgerufen
  wird, Then enthält `keys` je Alarm-Zeile die sortierte Liste ihrer Speicherschlüssel —
  mindestens `wind_gust→[gust]`, `wind_change→[gust, wind]` (die Windänderung beobachtet auch
  die Böen, und der Leser ordnet das Böen-Feld `gust` zu),
  `temperature_min`/`temperature_max`/`temperature_change→[temperature]`,
  `thunder_onset→[thunder]`, `precipitation_heavy_onset→[precipitation]`,
  `snow_line→[freezing_level]`, `cape→[cape]`, `fresh_snow→[fresh_snow]`,
  `visibility→[visibility]` — und `accepted` ist die sortierte Liste aller
  Schlüssel aus `keys` zuzüglich `snowfall_limit`.
  - Testart: Kern (FastAPI-`TestClient`, kein Mock). Prüfling: `api/routers/config.py`
    (`/alert-metric-channel-keys`) gegen `alert_metric_channel_keys()`; zusätzlich Staging-API
    (`/api/alert-metric-channel-keys` mit Login) nach Deploy.

- **AC-31:** Given die Antwort aus AC-30, When ihre Ziele geprüft werden, Then fehlt
  `humidity` (keine Alarm-Identität) in `keys`, und `snowfall_limit` ist **nie** Wert in `keys`
  (nur Element von `accepted`, weil die Legacy-Migration es schreibt).
  - Testart: Kern (`TestClient`). Prüfling: Antwort von `/alert-metric-channel-keys`.

- **AC-32:** Given eine beliebige Alarm-Zeile (jeder `AlertMetric`-Wert in `keys`), When der
  Detektor für diese Zeile bei Bewegung **aller** von ihr beobachteten Werte seine
  `WeatherChange`s emittiert und `_metric_id_for_summary_key` jeden Summary-Key auflöst, Then
  ist die Schlüsselliste aus dem Endpunkt **gleich** der Menge der aufgelösten Schlüssel —
  geprüft **zeilenweise auf Mengengleichheit** (keine ⊆-Kette, die z. B. einen im Trip-Pfad nie
  ausgelösten `snowfall_limit` grün durchließe oder bei `wind_change` den Böen-Schlüssel
  verschwiege).
  - Testart: Kern (reines Python, Endpunkt über `TestClient`, Detektor real, kein Mock).
    Prüfling: `alert_metric_channel_keys()`/Endpunkt gegen `weather_change_detection.py` und
    `alert_channels._metric_id_for_summary_key`. Der Test liest **keine** `.ts`-Datei ein
    (kein Dateiinhalt-Check).

- **AC-33:** Given die Legacy-Migration (S2 AC-18) läuft für Regeln aller `AlertMetric`-Werte
  mit gesetzten Kanälen, When `alert_metric_channels` entsteht, Then liegt jeder geschriebene
  Schlüssel in `accepted` aus dem Endpunkt (`snow_line`-Regeln schreiben `snowfall_limit` und
  `freezing_level`, beide akzeptiert).
  - Testart: Kern. Prüfling: `_migrate_rule_channels_to_metric_channels` in
    `src/app/loader.py` gegen die Antwort des Endpunkts.

- **AC-34:** Given der Endpunkt aus AC-30 existiert, When `GET /metrics` aufgerufen wird, Then
  ist die Antwort unverändert: `aggregations[]` enthält keine neuen Einträge (kein Onset,
  keine Alarm-Zeile), und `cape` fehlt weiterhin, weil `selectable=False`.
  - Testart: Kern (`TestClient`). Prüfling: `get_metrics` in `api/routers/config.py`; Vergleich
    gegen die Auswahl-Semantik des Wertebereiche-Editors (nur Verhalten der API, kein
    Frontend-Dateiinhalt).

- **AC-35:** Given ein angemeldeter bzw. ein nicht angemeldeter Aufruf, When
  `GET /api/alert-metric-channel-keys` gegen die Go-API gerichtet wird, Then wird der Aufruf
  nur mit gültiger Anmeldung an den Python-Core weitergereicht (gleiche Auth-Gruppe wie
  `/api/metrics`) und ohne Anmeldung mit 401 abgelehnt.
  - Testart: Go-Test (Router-Test). Prüfling: `internal/router/router.go`; nach Deploy
    zusätzlich Staging-API.

- **AC-36:** Given ein gespeicherter Ortsvergleich trägt `alert_metric_channels`
  (`{"gust": {"email": true}}`), When ein Teil-PUT (`PUT /api/briefings/{id}?kind=vergleich`
  und `PUT /api/compare/presets/{id}`) `"alert_metric_channels": null` sendet, Then bleibt die
  gespeicherte Map unverändert — wie beim Trip (`handler/trip.go:375`).
  - Testart: Go-Test. Prüfling: `mergeBriefingPatch` (`briefing_subscription.go`) /
    `applyComparePresetPatch` (`compare_preset.go`), über die HTTP-Schicht beider PUT-Wege;
    Trip-Pendant als Regressions-Fall.

- **AC-37:** Given derselbe Teil-PUT sendet für ein **anderes** Top-Level-Feld `null` (z. B.
  `activity_profile: null`), When er verarbeitet wird, Then ist das gespeicherte Ergebnis für
  dieses Feld exakt dasselbe wie vor S3a (`null` überschreibt den Bestandswert, `base[k] = v`) —
  die Angleichung gilt nur für `alert_metric_channels`. Der Test hält zuerst fest, dass das
  gewählte Feld vor der Änderung tatsächlich durch `null` verändert wird (sonst ist die
  Gegenprobe wertlos), und wählt notfalls ein anderes Feld, für das das gilt.
  - Testart: Go-Test gegen dieselben PUT-Wege. Prüfling: `mergeBriefingPatch`.

- **AC-38:** Given ein Teil-PUT sendet `{"alert_metric_channels": {"gust": null}}`, When er
  gespeichert und wieder geladen wird, Then ist `gust` als `null` persistiert (andere Metriken
  unverändert, `mergeConfigMap`), und der Leser behandelt `null` wie „kein Eintrag" — die
  Metrik erbt (Trip und Ortsvergleich).
  - Testart: Go-Test (Persistenz) plus Kern (Leser: `null`-Eintrag ⇒ geerbter Satz).
    Prüfling: `mergeConfigMap`, `alert_channels._metric_channel_sets`.

- **AC-39:** Given zwei verschiedene Nutzer A und B haben je einen Ortsvergleich mit eigenem
  `alert_metric_channels`, When Nutzer B Teil-PUTs mit `null` bzw. mit einer Metrik sendet
  (AC-36/AC-38) und Nutzer A liest, Then bleiben die Daten von A vollständig unverändert und B
  sieht und ändert nichts von A; `user_id` kommt aus dem Auth-Kontext, nie `"default"`. Der
  Endpunkt aus AC-30 liefert beiden Nutzern dieselbe, nutzerunabhängige Antwort.
  - Testart: Go-Test mit zwei Nutzern (ADR-0003). Prüfling: `UpdateBriefingHandler`/
    `UpdateComparePresetHandler`; `tests/test_user_id_default_guard.py` bleibt grün.

- **AC-40:** Given S3a ist umgesetzt, When die Dokumentation geprüft wird, Then beschreibt
  `docs/reference/api_contract.md` den Endpunkt samt Antwortform und die Semantik „null =
  erbt", und ADR-0077 trägt den Nachtrag „S3a" (Schlüsselmenge, Rückfall nach Tier-Gates,
  `null` = erbt, keine Go-Schreibvalidierung) bei unverändertem Status.
  - Testart: Kern, `# doc-compliance-test`: ein eigener Test prüft, dass ADR-0077 einen
    Abschnitt „S3a" mit den vier Punkten enthält und `api_contract.md` den Pfad
    `/api/alert-metric-channel-keys` samt `keys`/`accepted` nennt; zusätzlich bleiben
    `tests/test_api_contract_drift.py` und `tests/test_adr_index_drift.py` grün.

### Acceptance Criteria (S3b1 — Oberfläche)

Nummerierung setzt AC-40 (S3a) fort. Diese ACs betreffen die Oberfläche auf allen vier Flächen
(Trip-Hub, Trip-Anlegen, Ortsvergleich, Ortsvergleich-Anlegen). Ein Eintrag im Sinne dieser ACs
ist ein Wert unter `alert_metric_channels[<Speicherschlüssel>]`.

- **AC-41:** Given ein Alarme-Reiter mit aktiven Alarm-Zeilen und eine Antwort des Endpunkts
  `/api/alert-metric-channel-keys`, When der Block „Kanäle je Wettergröße" angezeigt wird, Then
  zeigt er genau eine Zeile je Speicherschlüssel, nämlich die Vereinigung von `keys[m]` über die
  aktiven Alarm-Zeilen, beschränkt auf Schlüssel aus `accepted` (z. B. `gust` und `wind` für eine
  aktive `wind_change`-Zeile; kein `humidity`, kein `snowfall_limit`).
  - Testart: Kern (`node --test`). Prüfling: `kanalZeilen` in `alertMetricChannels.ts` sowie
    Rendering des Blocks.

- **AC-42:** Given ein Bestandseintrag für einen Schlüssel, den keine aktive Alarm-Zeile mehr
  trägt (z. B. `snowfall_limit` oder die Größe einer deaktivierten Zeile), When der Nutzer im Block
  eine andere Größe ändert und speichert, Then wird der Bestandseintrag weder angezeigt noch
  gesendet und bleibt serverseitig unverändert erhalten.
  - Testart: Kern. Prüfling: `baueDiff` und der Payload beider Speicherwege; Gegenprobe am
    gespeicherten Stand (Eintrag danach noch vorhanden).

- **AC-43:** Given eine Zeile ohne Eintrag oder mit `null`, When der Block sie anzeigt, Then steht
  sie auf „wie Abo-Kanäle"; schaltet der Nutzer auf „eigene Wahl", Then zeigt die Zeile vier
  Kanal-Schalter, vorbelegt mit dem aktuellen Abo-Kanalsatz des Trips bzw. Ortsvergleichs.
  - Testart: Kern und Komponententest. Prüfling: `AlertMetricChannelsBlock.svelte`,
    Vorbelegung aus `displayChannelState`.

- **AC-44:** Given der Nutzer ändert die Kanalwahl einer Zeile (z. B. nur Telegram an), When
  gespeichert wird, Then trägt der gesendete Eintrag alle vier Flags (`email`, `telegram`, `sms`,
  `premium_sms`) als Boolean oder ist `null`, nie ein Teil davon.
  - Testart: Kern. Prüfling: `normalisiereEintrag` und der Payload; Mutations-Gegenprobe
    „Flag weglassen".

- **AC-45:** Given der Nutzer wählt in einer Zeile mit „eigene Wahl" alle vier Kanäle ab, When
  gespeichert wird, Then wird `null` (erbt) gesendet, die Zeile zeigt danach wieder „wie
  Abo-Kanäle", und weder `{}` noch ein Eintrag mit vier `false` wird je gesendet.
  - Testart: Kern. Prüfling: `normalisiereEintrag`, Block.

- **AC-46:** Given eine Zeile mit eigener Wahl, When der Nutzer den Umschalter zurück auf „wie
  Abo-Kanäle" stellt und speichert, Then sendet der Speicherweg `{<Schlüssel>: null}` und der
  Leser behandelt den Schlüssel danach wieder als „erbt" (AC-38).
  - Testart: Kern. Prüfling: Payload-Aufbau; Persistenz-Roundtrip auf Staging.

- **AC-47:** Given ein hydrierter Stand mit mehreren Einträgen und eine Änderung an genau einem,
  When gespeichert wird, Then enthält die Nutzlast nur diesen geänderten Eintrag (Diff gegen den
  hydrierten Stand); eine neu aufgebaute Vollmap wird nie gesendet, und ohne Änderung enthält die
  Nutzlast das Feld gar nicht.
  - Testart: Kern. Prüfling: `baueDiff`, `buildAlarmeDeliveryPayload`,
    `baueAlarmNutzlast`.

- **AC-48:** Given aktive Zeilen `wind_gust` und `wind_change`, When der Block angezeigt wird,
  Then sind `gust` und `wind` zwei eigene Zeilen mit je einem Hinweis, dass die Windänderung je
  nach Auslöser der Böen- oder der Wind-Zeile folgt; eine Änderung an einer Zeile schreibt nur
  ihren eigenen Schlüssel (kein Doppelschreiben) und es gibt keinen Zustand „gemischt".
  - Testart: Kern und Komponententest. Prüfling: Block, `baueDiff`.

- **AC-49:** Given der Endpunkt `/api/alert-metric-channel-keys` ist nicht ladbar (Netzwerk-
  oder Serverfehler), When der Block angezeigt wird, Then zeigt er „nicht verfügbar", rät keine
  Schlüssel, und ein Speichern des Alarme-Reiters sendet kein `alert_metric_channels`.
  - Testart: Kern. Prüfling: Helper und Block mit fehlschlagendem Abruf; Payload ohne das Feld.

- **AC-50:** Given mehrere Blöcke bzw. wiederholte Aufrufe in einer Sitzung, When der Endpunkt
  erfolgreich geladen wurde, Then erfolgt genau ein Abruf (Modul-Promise-Cache); schlug der Abruf
  fehl, wird das Ergebnis nicht gecacht und der nächste Aufruf versucht es erneut.
  - Testart: Kern. Prüfling: `ladeKanalSchluessel`; Mutations-Gegenprobe „Fehler wird
    gecacht".

- **AC-51:** Given eine eigene Wahl enthält einen Kanal, der im Abo-Satz nicht aktiv ist (z. B.
  Telegram gewählt, im Abo aber nur E-Mail), When die Zeile angezeigt wird, Then erscheint ein
  sichtbarer Hinweis, dass dieser Kanal im Abo nicht aktiv ist; die Wahl wird trotzdem gespeichert
  und nicht blockiert.
  - Testart: Kern. Prüfling: `hinweise` und Block.

- **AC-52:** Given der Block ist sichtbar, When der Nutzer ihn betrachtet, Then steht darin der
  Hinweis, dass Radar-/Regen-Alarme und amtliche Warnungen immer über die Abo-Kanäle gehen (nicht
  über die Wahl je Wettergröße).
  - Testart: Komponententest und E2E. Prüfling: Block, Katalogtext in DE und EN.

- **AC-53:** Given ein Nutzer ohne Premium-SMS-Freigabe (`premium_sms_allowed` aus dem Profil),
  When er in einer Zeile „eigene Wahl" öffnet, Then ist der Premium-SMS-Schalter nach demselben
  Gate gesperrt wie im Abo-Kanalwähler (`premiumSmsAlarmGate`); mit Freigabe ist er schaltbar.
  Für SMS gibt es keinen Tarif-Hinweis.
  - Testart: Kern. Prüfling: Block mit `premiumSmsAlarmGate`; zwei Profile.

- **AC-54:** Given ein bestehender Trip im Trip-Hub, When der Nutzer eine Kanalwahl ändert, Then
  geht die Änderung als Top-Level-Feld `alert_metric_channels` (nicht in `display_config`) mit dem
  **bestehenden** Dirty-`$effect` und ohne zweiten `schedule()`-Aufruf an das Speichern; beim
  Anlegen eines Trips (`/trips/new`, Desktop und Mobil) steht das Feld im Anlege-Payload.
  - Testart: Kern. Prüfling: `AlarmeTab.svelte` (route-Zweig), `alarmeDeliveryPayload.ts`,
    `tripNewLogic.ts`; Zählung der `schedule()`-Aufrufe im Test.

- **AC-55:** Given ein Ortsvergleich im Editor bzw. in der Anlegemaske (`/compare/new`), When der
  Nutzer eine Kanalwahl ändert, Then wird der Eintrag aus dem Preset hydriert, über Wertprop und
  `onAlarmFeldSetzen` geändert und in `buildComparePresetSavePayload` (Edit und Create) als
  `alert_metric_channels` gesendet; nach dem Neuladen zeigt der Block den gespeicherten Stand.
  - Testart: Kern. Prüfling: `alarmePropsAus.ts`, `compareHubHydration.ts`,
    `compareEditorSave.ts`; Roundtrip auf Staging.

- **AC-56:** Given ein Ortsvergleich mit Snapshot, in dem der Eintrag `gust` fehlte, und der Nutzer
  hat seither `gust` gesetzt, When der Snapshot per Rollback zurückgespielt wird, Then sendet der
  Rollback für `gust` explizit `null` und stellt Einträge, die im Snapshot standen, mit ihrem
  alten vollständigen Wert wieder her; Weglassen von `gust` wäre kein Zurücksetzen.
  - Testart: Kern. Prüfling: `rollbackAlarmSnapshot`/`alarmeVergleichSpeicherung.ts`;
    Mutations-Gegenprobe „Rollback ohne null".

- **AC-57:** Given ein Ortsvergleich mit gespeichertem `alert_metric_channels`, When ein Nachbar-
  Schreiber (`versandVergleichSpeicherung.ts`, `wertebereicheVergleichSpeicherung.ts`) einen
  Teil-PUT absetzt, Then enthält dessen Nutzlast das Feld nicht in verändernder Form und der
  gespeicherte Stand bleibt danach vollständig erhalten.
  - Testart: Kern. Prüfling: beide Schreiber (unverändert), Test mit Bestandsmap.

- **AC-58:** Given die vier Flächen Trip-Hub, Trip-Anlegen, Ortsvergleich-Editor und
  Ortsvergleich-Anlegen, When der Alarme-Reiter geöffnet wird, Then erscheint auf allen vier
  derselbe Block aus **einem** Baustein (`AlertMetricChannelsBlock.svelte`) ohne neue
  `context===`-Weiche, und `context_herkunft_zweige_eingefroren.test.ts` ist nach neuer Messung
  der AlarmeTab-Pins grün.
  - Testart: Kern (Ratsche) und E2E. Prüfling: `AlarmeTab.svelte`, Ratsche.

- **AC-59:** Given zwei verschiedene Nutzer A und B mit je eigenem Trip und Ortsvergleich und
  unterschiedlichem `alert_metric_channels`, When Nutzer B im Block ändert, speichert und
  zurückrollt, Then bleiben die Einträge von A unverändert, `user_id` kommt aus dem Auth-Kontext
  und nie `"default"`, und der Block von A zeigt weiter A's Stand.
  - Testart: Kern mit zwei Nutzern (ADR-0003; `fakeTripServer.ts` kennt das Feld bereits) und
    Persistenz-Roundtrip; Staging-Login nur mit `default`, daher Kern als Hauptnachweis.

- **AC-60:** (Wirkung am Leser) Given ein im Editor gesetzter Eintrag (z. B. `thunder` nur
  Telegram) wurde über den echten Speicherweg persistiert, When der Python-Leser den
  Abweichungsalarm für diese Größe versendet (`trip_alert.py` bzw. `compare_alert.py`), Then
  geht der Alarm über den gewählten Kanal und nicht über den Abo-Satz; der Nachweis wird am
  Leser geführt, nicht nur am Payload.
  - Testart: Kern. Brücke über eine gemeinsame JSON-Testdatei (Nutzlast-Beispiel): der
    Frontend-Test (`node --test`) weist nach, dass `alertMetricChannels.ts` für die
    Beispiel-Bedienung genau diese Nutzlast erzeugt; der Python-Test lädt dieselbe Datei
    über den echten Loader (`src/app/loader.py`) und schickt sie durch
    `resolve_alert_channels` (`src/services/alert_channels.py`) bzw. den Versandpfad.
    Zusätzlich Staging-E2E mit Zustellung im Test-Postfach. Parität Trip und Ortsvergleich
    (ADR-0043).

- **AC-61:** Given die Sprache des Nutzers ist DE bzw. EN, When der Block angezeigt wird, Then
  stammen alle Texte (Überschrift, Umschalter, Hinweise, „nicht verfügbar") aus
  `messages/{de,en}/alarme.json`, es gibt keinen hartkodierten Nutzertext, und
  `hardcode_allowlist.json` bleibt `[]`; Protokoll-Token (Kanalnamen im Sinne von `sms_code`)
  werden nicht übersetzt.
  - Testart: Kern (Hardcode-Ratsche, Katalog-Parität DE/EN). Prüfling: `alarme.json`, Block.

- **AC-62:** Given der Block auf Staging, When ein Nutzer eine Wahl setzt und speichert, Then
  ist der Ablauf (Umschalten, Kanal wählen, Speichern, Neuladen, Zurück auf „wie Abo-Kanäle")
  sowohl im Layout `.tn-mobile` als auch im Layout `.tn-desktop` bedienbar, ohne verdeckte oder
  abgeschnittene Schalter, bei WCAG-AA-Kontrast.
  - Testart: Playwright-E2E, beide Layouts, auf Staging.

### Acceptance Criteria (S3b2 — Hinweise)

Nummerierung setzt AC-62 (S3b1) fort. Die Hinweise erscheinen nur in Zeilen mit **eigener Wahl**,
nur für gewählte Kanäle, und sie informieren nur: Auswahl und Speichern bleiben immer möglich.

- **AC-63:** Given eine Zeile mit eigener Wahl, in der Telegram gewählt ist, und ein Nutzerprofil
  ohne verknüpften Telegram-Chat, When die Zeile angezeigt wird, Then erscheint der Hinweis
  `kanal-hinweis-kein-empfaenger-telegram`, dass dieser Kanal keinen Empfänger hat und wo er
  einzutragen ist (Reiter Versand bzw. Profil); mit verknüpftem Chat erscheint er nicht.
  - Testart: Kern (`node --test`). Prüfling: `kanaeleOhneEmpfaenger` und Block; Mutations-Gegenprobe
    „Bedingung am Profilfeld entfernt".

- **AC-64:** Given eine Zeile mit eigener Wahl, in der SMS gewählt ist, und ein Profil, bei dem die
  Nummer fehlt, die SMS-Freigabe aus ist oder die Nummer nicht bestätigt ist, When die Zeile
  angezeigt wird, Then erscheint der Hinweis `kanal-hinweis-kein-empfaenger-sms`; mit bestätigter
  Nummer und Freigabe erscheint er nicht, und die Bedingung stimmt mit der Anzeige „nicht verbunden"
  bzw. „eingetragen, unbestätigt" von `channelConnectionStatus` überein.
  - Testart: Kern. Prüfling: `kanaeleOhneEmpfaenger`; Gleichlauf-Test gegen
    `channelConnectionStatus` (eine Definition, keine zweite Ableitung); Mutations-Gegenprobe
    „`!sms_verified` entfernt".

- **AC-65:** Given eine Zeile mit eigener Wahl, in der Premium-SMS gewählt ist, When der
  Rückadress-Stand des Profils `none` oder `stale` ist, Then erscheint der Hinweis
  `kanal-hinweis-kein-empfaenger-premium_sms`; bei `fresh` erscheint er nicht. Das Frontend rechnet
  keine Zeit, es liest nur `premium_sms_reply_state`.
  - Testart: Kern. Prüfling: `kanaeleOhneEmpfaenger`, Block mit drei Profilen (`none`, `stale`,
    `fresh`); Mutations-Gegenprobe „`stale` fehlt".

- **AC-66:** Given eine Zeile mit eigener Wahl, in der E-Mail gewählt ist, When das Profil keine
  weiteren Kanaldaten enthält, Then erscheint nie ein Hinweis „Kanal ohne Empfänger" für E-Mail,
  weil das Konto immer eine E-Mail-Adresse hat.
  - Testart: Kern. Prüfling: `kanaeleOhneEmpfaenger` (leeres und volles Profil).

- **AC-67:** Given das Profil ist noch nicht geladen, nicht ladbar oder `null`, When eine Zeile mit
  eigener Wahl (z. B. Telegram) angezeigt wird, Then erscheint **kein** Hinweis „Kanal ohne
  Empfänger"; der Block behauptet nie „kein Empfänger", solange der Stand unbekannt ist. Der
  Schwellen-Hinweis hängt nicht am Profil und bleibt davon unberührt.
  - Testart: Kern. Prüfling: `kanaeleOhneEmpfaenger(…, null)` und Block ohne Profil.

- **AC-68:** Given eine Zeile steht auf „wie Abo-Kanäle" (kein eigener Eintrag), When der Block sie
  anzeigt, Then erscheint weder ein Hinweis „Kanal ohne Empfänger" noch ein Schwellen-Hinweis,
  auch wenn das Profil Lücken hat oder Kanal-Schwellen über „niedrig" stehen; die Hinweise gelten
  nur für die eigene Wahl.
  - Testart: Kern und Komponententest. Prüfling: Block; Mutations-Gegenprobe „Hinweis auch bei
    erbender Zeile".

- **AC-69:** Given eine Zeile mit eigener Wahl und gewähltem Kanal, dessen Kanal-Schwelle `LOW`
  (niedrig) ist, When die Zeile angezeigt wird, Then erscheint **kein** Schwellen-Hinweis; dies gilt
  für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS).
  - Testart: Kern. Prüfling: `kanaeleMitSchwelle`; Mutations-Gegenprobe „`>= LOW` statt `> LOW`".

- **AC-70:** Given eine Zeile mit eigener Wahl und ein gewählter Kanal (je einer der vier: E-Mail,
  Telegram, SMS, Premium-SMS) mit Schwelle `MODERATE` oder `HIGH`, When die Zeile angezeigt wird,
  Then erscheint `kanal-hinweis-schwelle-<k>` mit dem Kanalnamen und dem Schwellennamen und der
  Aussage, dass schwächere Warnungen über diesen Kanal nicht ankommen; der Hinweis ist
  stufenunabhängig (es gibt im Frontend keine zweite Rangtabelle der Metrik-Stufen).
  - Testart: Kern. Prüfling: `kanaeleMitSchwelle`, Block; je Kanal ein Fall für `MODERATE` und
    `HIGH`; Mutations-Gegenprobe „nur `HIGH`".

- **AC-71:** Given eine Zeile mit eigener Wahl, in der ein Kanal sowohl ohne Empfänger ist als auch
  eine Schwelle über „niedrig" hat (z. B. Telegram ohne Chat, Schwelle `HIGH`), When die Zeile
  angezeigt wird, Then erscheinen beide Hinweise gleichzeitig, jeder mit eigener Testid, und
  keiner verdeckt den anderen.
  - Testart: Kern und Komponententest. Prüfling: Block.

- **AC-72:** Given eine Zeile mit eigener Wahl und mindestens einem Hinweis, When der Nutzer den
  Kanal trotzdem gewählt lässt und speichert, Then bleiben alle Schalter bedienbar, das Speichern
  wird nicht blockiert, und der gesendete Eintrag bzw. Payload, Snapshot und Rollback sind
  identisch zu einer Zeile ohne Hinweis (die Hinweise ändern nichts am Speicherweg).
  - Testart: Kern. Prüfling: Block (`disabled` unverändert, `onChange`-Aufrufe), Payload-Vergleich
    mit und ohne Hinweis; Mutations-Gegenprobe „Hinweis sperrt Schalter".

- **AC-73:** Given zwei verschiedene Nutzer A (Telegram-Chat verknüpft) und B (kein Chat), je mit
  eigener Wahl „Telegram", When der Block für A bzw. B angezeigt wird, Then zeigt A keinen und B
  den Hinweis „Kanal ohne Empfänger"; das Profil stammt aus dem Auth-Kontext des jeweiligen Nutzers
  (nie `"default"`), und der Stand von A beeinflusst B nicht.
  - Testart: Kern mit zwei Nutzern (ADR-0003); Staging kennt nur den Login `default`, daher ist
    der Kern der Hauptnachweis.

- **AC-74:** Given die vier Flächen Trip-Hub, Trip-Anlegen (`/trips/new`), Ortsvergleich-Editor
  und Ortsvergleich-Anlegen (`/compare/new`), When der Alarme-Reiter mit eigener Wahl geöffnet
  wird, Then erscheinen die Hinweise auf allen vier gleich aus **einem** Baustein
  (`AlertMetricChannelsBlock.svelte`) über `AlarmeTab`, ohne neue `context===`-Weiche und ohne
  zweite Profil-Abfrage; `context_herkunft_zweige_eingefroren.test.ts` ist nach neuer Messung grün.
  - Testart: Kern (Ratsche) und Komponententest je Fläche; Staging-E2E für die erreichbaren
    Flächen.

- **AC-75:** Given die Sprache des Nutzers ist DE bzw. EN, When ein Hinweis angezeigt wird, Then
  stammen die Texte aus den Schlüsseln `alarme.kanaele.kein_empfaenger` und
  `alarme.kanaele.schwelle_hinweis` in `messages/{de,en}/alarme.json`, es gibt keinen
  hartkodierten Nutzertext, `hardcode_allowlist.json` bleibt `[]`, und Kanalnamen (Protokoll-Token)
  werden nicht übersetzt.
  - Testart: Kern (Katalog-Parität DE/EN, Hardcode-Ratsche). Prüfling: `alarme.json`, Block.

- **AC-76:** Given der Block auf Staging mit einer Zeile mit eigener Wahl, die einen Hinweis
  auslöst, When ein Nutzer die Zeile betrachtet, Then ist der Hinweis sowohl im Layout `.tn-mobile`
  als auch im Layout `.tn-desktop` sichtbar, nicht abgeschnitten oder verdeckt, bei
  WCAG-AA-Kontrast.
  - Testart: Playwright-E2E, beide Layouts, auf Staging (`kanal-je-wettergroesse-block.staging.spec.ts`).

- **AC-77:** Given die Hinweislogik, When die Bedingung (Profilfeld bzw. Schwelle) verfälscht wird
  (z. B. Telegram-Prüfung entfernt, Premium-SMS-Stand ignoriert, Schwelle ignoriert), Then färbt
  mindestens ein Test jeweils rot; die Zusicherung ist dort geprüft, wo sie wirkt (an der
  Bedingung der reinen Funktion und am Rendering des Blocks), nicht nur am Vorhandensein des Texts.
  - Testart: Mutations-Gegenprobe im `implementation-validator` (Liste siehe Implementation Details
    S3b2).

## Known Limitations / Nicht-Ziele

Diese Scheibe (S1) liefert ausschließlich Feld, Persistenz, Roundtrip, Doku und ADR.
Ausdrücklich **nicht** Teil von S1:

- **Kein Leser im Alarm-Pfad.** Das Feld wirkt in S1 auf nichts — das ist Absicht
  (Risiko R2 „stille Kanal-Abschaltung" kann ohne Leser strukturell nicht feuern). Ein
  Leser folgt erst in S2.
- **Keine Migration** von `alert_rules[].channels` in das neue Feld — folgt in S2,
  direkt neben dem Code, der das Feld erst maßgeblich macht.
- **Keine Frontend-/`.svelte`-Änderung, keine Editor-Spalte.** Folgt in S3b (Oberfläche;
  S3 ist in S3a/S3b geteilt, siehe Scheibenschnitt unten), und S3 darf laut ADR-0043 erst
  nach S2 kommen (eine Bedienfläche ohne wirkende Aufrufstelle wäre eine
  Konfigurationsfläche ohne sichtbare Wirkung).
- **Kein Rückbau** von `alert_rules` — folgt in S4.
- **Keine Validierung** der Metrik-Schlüssel oder Kanalwerte. Go validiert heute weder
  Metrik-Keys noch Stufenwerte; eine neue Validierung wäre Scope-Creep und würde
  Bestandsdaten mit dem abgelösten Schlüssel `snow_line` brechen.
- **`has_active_rules` bleibt unangetastet.** Weder S1 noch S2–S4 fassen es an — ein
  Wegfall würde Trip-Verhalten ändern (überstimmt `alert_on_changes=False`) und wäre
  nicht verhaltensneutral. Das gilt ausdrücklich auch für S4 (Schnitt C, siehe Known
  Limitations S4): das Gate geht unverändert an #2793 über.

### Known Limitations / Nicht-Ziele (S2)

Diese Scheibe (S2) liefert Leser + Migration. Ausdrücklich **nicht** Teil von S2:

- **Kein Frontend/`.svelte`.** Alles unter `frontend/`, `internal/`, `cmd/` ist
  unangetastet — die Editor-Spalte folgt in S3b (ADR-0043: erst nach S2).
- **Kein Rückbau von `alert_rules`.** Die Entität bleibt bestehen; `alert_rules[].channels`
  wird kopiert, nicht verschoben oder geleert — folgt in S4, erst wenn der Eintrags-Arm
  trägt.
- **Keine Validierung der Metrik-Schlüssel.** S2 legt das Lese-Vokabular fest (Katalog-
  `metric_id`, wählbarkeitsdisambiguiert, unbekannt ⇒ erbt), aber prüft nicht, ob
  Bestandsdaten „falsche" Schlüssel tragen — die verbindliche Schlüsselmenge (eine
  Definition, zeilenweiser Wirk-Test, ADR-0077-Nachtrag) liefert S3a; eine
  Go-Schreibvalidierung gibt es bewusst nicht (E3). Bestandsprüfung erledigt: 0 Briefings
  mit `alert_metric_channels`, 0 Regeln mit `channels` in Prod.
- **`has_active_rules` bleibt unangetastet** — wie in S1, unverändert gültig für S2–S4.
- **`split_by_threshold` wird nicht gebraucht.** Die Union je Metrik braucht keine
  Partitionsstelle; Drosselung, Tages-Obergrenze und der Doppel-Alarm-Guard bleiben
  dadurch unberührt.

### Known Limitations / Nicht-Ziele (S3a)

**Scheibenschnitt (löst die frühere Einteilung „S3 = Editor-Spalte" ab):**

| Scheibe | Inhalt | Workflow |
|---|---|---|
| S3a | Backend und Vertrag: Leser-Rückfall nach Tier-Gates, ADR-0077-Nachtrag, Schlüssel-Endpunkt, Go-Angleichung Top-Level-`null` | dieser Workflow |
| S3b1 | Oberfläche: Block „Kanäle je Wettergröße" auf allen vier Flächen (Trip-Hub, Trip-Anlegen, Ortsvergleich, Ortsvergleich-Anlegen) samt Payload, Snapshot/Rollback, DE/EN-Texte, Hinweise „nicht im Abo-Satz", „metrikfreie Alarme" und Wind-Hinweis | Workflow `feat-1895-s3b-kanal-spalte` (Beschluss F1) |
| S3b2 | Hinweis „Kanal ohne Empfänger" und Hinweis „Kanal-Schwelle über Metrik-Stufe" | dieser Workflow `feat-1895-s3b2-kanal-hinweise` (unter #1895, kein neues Issue) |
| S4 | Rückbau des toten Codes rund um `alert_rules` (Schnitt C): nicht eingebundene Regel-Editor-Komponenten, tote Exporte in `alertMetricTable.ts`, `expand_preset`. Leser, Gate, Kanal-Union und Persistenz gehen an #2793 | Workflow `feat-1895-s4-alert-rules-rueckbau`, Spec `docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md` |

Ausdrücklich **nicht** Teil von S3a:

- **Keine Oberfläche, für Nutzer unsichtbar.** Block „Kanäle je Wettergröße" (E1), „erbt"-Zustand
  und Abwahl aller Kanäle (E4/E5), freie Kanalwahl mit Tarif-Sperre (E6), Hinweistext für
  metrikfreie Alarme (E9) und Anlegemasken (E10) sind S3b1. Bis dahin schreibt kein Nutzer das
  Feld (Prod-Bestand: 0 Briefings), die Rückfall-Änderung wirkt auf keinen Bestand.
- **Kanal-Schwelle (benanntes Restrisiko).** `split_by_threshold` (ADR-0046) läuft nach der
  Auflösung und bleibt unverändert. Ein Metrik-Arm `{sms}` mit SMS-Schwelle „hoch" unterdrückt
  eine niedrigere Warnung, auch wenn der Abo-Satz sie zugestellt hätte. Das gilt heute schon
  gleich für den Abo-Satz; S3a macht es nicht schlechter. Der sichtbare Hinweis dafür ist
  **S3b2** (geliefert mit S3b2).
- **Fehlender Empfänger (benanntes Restrisiko).** `resolve_alert_channels` kennt keine
  Empfänger; ein gewählter Kanal ohne Empfänger (z. B. Telegram ohne verknüpften Chat) wird vom
  Rückfall nicht erfasst. Der sichtbare Hinweis dafür ist **S3b2** (geliefert mit S3b2).
- **Windänderung hängt an zwei Schlüsseln.** Ein Windänderungs-Alarm, der über die Böen
  ausgelöst wird, folgt der Kanalwahl unter `gust`, einer über den Mittelwind der unter `wind`
  (so liest der S2-Leser heute, gemessen 2026-11-03). Der Endpunkt sagt das ehrlich
  (`wind_change→[gust, wind]`); wie die Oberfläche diese Kopplung zeigt, ist mit S3b1 entschieden (F6, AC-48).
- **Metrikfreie Alarme unberührt.** Radar-/Regen-Alarme und amtliche Warnungen übergeben keinen
  Metrik-Parameter und gehen unverändert über den Abo-Satz (AC-13).
- **Nebenbefund außerhalb des Umfangs.** `compare_alert.py:70-80` bildet `temp_min_c` auf
  `temperature_cold` ab, `alert_channels.py` auf `temperature`; betroffen ist nur der
  Deaktivieren-Filter, nicht die Kanal-Map. Wird als Nebenbefund (#1199) geführt, nicht hier
  geändert.
- **Keine Go-Schreibvalidierung** der Metrik-Schlüssel (E3) und **keine allgemeine
  „null = No-Op"-Regel** im Go-Merge (E8): nur `alert_metric_channels`.
- **`/api/metrics` unverändert**; kein Rückbau von `alert_rules`; `has_active_rules` unangetastet.

### Known Limitations / Nicht-Ziele (S3b1)

- **S3b2 war offen (Stand S3b1; geliefert mit S3b2, siehe unten).** Zwei Hinweise fehlten in S3b1 ausdrücklich und
  bleiben bis S3b2 (weiter unter #1895) eine bekannte Lücke: (1) „Kanal ohne Empfänger" — das
  Frontend kennt `mail_to`, `sms_to`, `telegram_chat_id`, `sms_verified` und `tier` im
  Alarme-Reiter nicht, obwohl das Profil sie liefert, und es braucht erst einen Abgleich mit dem
  Python-Transport (wann ein Kanal dort als „ohne Empfänger" gilt), sonst entstünde ein neues
  Falschversprechen; (2) „Kanal-Schwelle über Metrik-Stufe" (ADR-0046: `split_by_threshold` läuft
  nach der Auflösung). Bis dahin kann eine Kanalwahl ohne Empfänger oder unter einer hohen
  Kanal-Schwelle einen Alarm nicht zustellen; der Nutzer sieht in S3b1 dazu keinen Hinweis.
- **Kein neuer Backend-Code.** Kein Endpunkt, keine Leser-Änderung, keine Go-Schreibvalidierung;
  die UI schreibt nur Schlüssel aus `accepted`.
- **Keine Kanalwahl für metrikfreie Alarme.** Radar-/Regen-Alarme und amtliche Warnungen gehen
  immer über die Abo-Kanäle (E9, AC-52).
- **Kein Zustand „gemischt" für die Wind-Kopplung.** `gust` und `wind` bleiben zwei Zeilen (F6).
- **Inaktive Bestandseinträge** werden nicht angezeigt, aber auch nicht gelöscht (F5, AC-42).
- **Kein Rückbau von `alert_rules`** (S4), `has_active_rules` unangetastet, `/api/metrics`
  unverändert.
- **Staging kennt nur den Login `default`.** Die Mandantentrennung (AC-59) wird im Kern mit zwei
  Nutzern bewiesen, nicht über zwei Staging-Konten.

### Known Limitations / Nicht-Ziele (S3b2)

- **Hinweise informieren nur.** Kein Gate, keine Sperre von Auswahl oder Speichern; ein Kanal ohne
  Empfänger oder über der Schwelle bleibt wählbar und wird gespeichert.
- **Schwellen-Hinweis ist stufenunabhängig.** Es gibt im Frontend keine einzige Quelle für die
  Dringlichkeit einer Metrik-Stufe (Mapping liegt in `services.alert_urgency`); eine zweite
  Rangtabelle wäre ein Verstoß gegen #1480/#1481. Der Hinweis erscheint daher bei jeder Schwelle
  über „niedrig", auch wenn die gerade gewählte Stufe die Schwelle erreichen würde. Eine
  stufengenaue Aussage bräuchte eine geteilte Quelle und wäre eine eigene Scheibe.
- **Abo-Satz-Zeilen ohne Hinweis.** Zeilen „wie Abo-Kanäle" und der Abo-Kanalsatz selbst
  bekommen keinen Hinweis, obwohl derselbe Mangel dort auftreten kann; die Scheibe bleibt auf die
  eigene Wahl im Block begrenzt (Scope-Creep vermieden).
- **Premium-SMS-Frische gehört dem Server.** Das Frontend liest nur `premium_sms_reply_state`; die
  Schwelle für „veraltet" wird nicht dupliziert. Zwischen Laden des Profils und Versand kann sich
  der Stand ändern.
- **Kein Link.** Die Hinweise nennen den Ort (Reiter Versand bzw. Profil) als Text; es gibt
  keinen Sprung dorthin und damit keinen toten Link.
- **Kein neuer Backend-Code, Speicherweg unberührt.** Payload, Snapshot und Rollback bleiben wie in
  S3b1; kein Rückbau von `alert_rules` (S4), `has_active_rules` unangetastet.
- **Staging kennt nur den Login `default`.** Die Mandantentrennung (AC-73) wird im Kern mit zwei
  Nutzern bewiesen; das Staging-E2E zeigt die Hinweise mit dem Zustand dieses einen Kontos.
- **EN-Anlegen-Abläufe im E2E nicht messbar (#2810).** Der Testhelfer `anlegenPflicht` kennt nur
  deutsche Labels; die englischen Texte deckt der Katalog-Test (AC-75) ab, nicht das E2E.
- **Profil nicht ladbar ⇒ kein Empfänger-Hinweis.** Die Lücke bleibt dann unsichtbar (bewusst:
  lieber kein Hinweis als ein Falschversprechen).

### Known Limitations / Nicht-Ziele (S4)

S4 (Spec `docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md`) löscht nur toten Code:
die nicht eingebundenen Komponenten `AlertsTab`, `AlertCard`, `AlertMetricTable`,
`AlertMetricRow`, `AlertPresetSelector` und `trip-detail/AlertsPreviewCard`, die toten Exporte
in `alerts-tab/alertMetricTable.ts` und die Python-Hilfe `expand_preset` ohne Aufrufer
(ADR-0043). Nutzerverhalten, Kanalwahl und Persistenz ändern sich nicht.

- **Schnitt C, Übergabe an #2793.** Unverändert bleiben und gehen an #2793 (Epic #2791 S2,
  ADR-0106): das Prüf-Gate `has_active_rules`, die Kanal-Union der Regel-Kanäle in
  `alert_channels.py`, die Vorschau `AlertPreviewCard` (liest `trip.alert_rules`), der Badge in
  `TripTabs.svelte` und `hubUebersichtModell.ts`, die Diagnose in `api/routers/validator.py`,
  das Go-Modell samt `SyncAlertRules` sowie Loader und Persistenz des Feldes.
- **Kein stilles Zurückdrehen.** Der Rückbau der Leser ist aufgeschoben, nicht aufgegeben; die
  Entscheidung aus ADR-0077 (Rückbau von `alert_rules` als S4) gilt weiter und wird mit #2793
  abgeschlossen (Nachtrag S4 in ADR-0077).
- **Gate nicht verhaltensneutral umstellbar.** Die Gate-Fälle 1 bis 4 stehen in
  `docs/context/feat-1895-s4-alert-rules-rueckbau.md`; `_has_active_alert_metric` ist kein
  äquivalenter Ersatz.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0077, Fortschreibung von ADR-0046 (`0046-alarm-kanal-schwelle.md`)
- **Rationale:** ADR-0046 legt fest, dass die Kanal-Schwelle regelt, AUF WELCHEM WEG
  eine Meldung ankommt, nicht OB. ADR-0077 schreibt das fort, indem es die Zielform der
  neuen, metrik-genauen Kanal-Schicht festlegt: Ablageort (Top-Level auf `Trip` UND
  `ComparePreset`, Parität ab S1), Go-Typ (`map[string]interface{}`, damit der
  bestehende `mergeConfigMap`-Mechanismus greift und kein atomarer Ersatz der ganzen Map
  entsteht — Muster `DisplayConfig`), Schlüsselmenge (Analyse-Entscheidung für S3, in S1
  nicht validiert), die Regel „kein Eintrag = erbt den Abo-weiten Kanal-Satz" (Feld ist
  in S1 dadurch verhaltensneutral) sowie den Reihenfolge-Zwang „S2 muss vor S3 kommen"
  (ADR-0043-Konsequenz: keine Bedienfläche ohne wirkende Aufrufstelle).

## Changelog

- 2026-09-22: Initial spec created (Scheibe S1 von #1895-F2, Analyse-Grundlage
  `docs/context/feat-1895-kanalzuordnung-je-metrik.md` Sektion `# Analysis`).
- 2026-09-22: Scheibe S2 ergänzt (Leser im Alarm-Pfad + Migration
  `alert_rules[].channels` → `alert_metric_channels`, AC-10 bis AC-24), Analyse-Grundlage
  `docs/context/feat-1895-s2-kanal-leser.md` Sektion `# Analysis`. S1-Inhalte (AC-1 bis
  AC-9, Approval-Block) unverändert.
- 2026-11-03: Scheibe S3a ergänzt (Backend und Vertrag: Leser-Rückfall nach Tier-Gates,
  Schlüssel-Endpunkt `GET /alert-metric-channel-keys`, Go-Angleichung Top-Level-`null`,
  ADR-0077-Nachtrag, AC-25 bis AC-40), Analyse-Grundlage
  `docs/context/feat-1895-s3-kanal-spalte.md` Sektion `## Analysis` (E1–E10). S2 AC-12 als
  „teilweise abgelöst durch AC-25" vermerkt; Scheibenschnitt auf S3a/S3b/S4 umgeschrieben.
  Oberfläche (S3b) ausdrücklich nicht enthalten.
- 2026-11-03 (Nachfreigabe aus `/40-tdd-red`): Detektor-Probe zeigte, dass `wind_change` auch
  `gust_max_kmh` meldet und der Leser es als `gust` liest — AC-30/AC-32 in der alten Form
  (ein Schlüssel je Zeile, Gleichheit je Zeile) waren zusammen mit AC-33 nicht erfüllbar.
  Korrektur: `keys` liefert je Zeile die sortierte Schlüsselliste aus Lesersicht, AC-32 prüft
  Mengengleichheit; Implementation Details §3, Affected Files (Tie-Break bleibt in `loader.py`),
  Mutations-Gegenprobe und Known Limitations entsprechend angepasst.
- 2026-11-03: Scheibe S3b1 ergänzt (Oberfläche „Kanäle je Wettergröße" auf allen vier Flächen,
  AC-41 bis AC-62), Analyse-Grundlage `docs/context/feat-1895-s3b-kanal-spalte.md` Sektion
  `## Analysis` (F1–F9). Scheibenschnitt auf S3a/S3b1/S3b2/S4 umgeschrieben; S3b2 (Hinweise
  „Kanal ohne Empfänger" und „Kanal-Schwelle über Metrik-Stufe") ausdrücklich als offen
  benannt. S1–S3a-Inhalte unverändert; die Zusagen „S3b zeigt Hinweis" (Kanal-Schwelle, fehlender
  Empfänger) und „Wind-Kopplung entscheidet S3b" wurden auf S3b2 bzw. S3b1 präzisiert.
- 2026-11-04: Scheibe S3b2 ergänzt (Hinweise „Kanal ohne Empfänger" und „Kanal-Schwelle über
  Metrik-Stufe" im Block „Kanäle je Wettergröße", reine Frontend-Scheibe, AC-63 bis AC-77),
  Analyse-Grundlage `docs/context/feat-1895-s3b2-kanal-hinweise.md` Sektion `## Analysis`.
  Scheibenschnitt-Zeile S3b2 von „offen" auf „dieser Workflow" gesetzt; Kommentar in
  `premiumSmsAlarmGate.ts` zur Berichtigung vorgemerkt. S1–S3b1-Inhalte unverändert (nur der
  Stand-Vermerk in den Known Limitations S3b1).
- 2026-11-05: Scheibe S4 ergänzt (Schnitt C: nur toter Code rund um `alert_rules` entfernt,
  Leser/Gate/Kanal-Union/Persistenz an #2793), eigene Spec
  `docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md`. Scheibenschnitt-Zeile S4 auf den
  tatsächlichen Schnitt gesetzt, `has_active_rules`-Aussage (Known Limitations S1) präzisiert,
  Abschnitt „Known Limitations / Nicht-Ziele (S4)" ergänzt.
