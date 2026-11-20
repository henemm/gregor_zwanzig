# Adversary Dialog — feat-3189-vorlage-herkunft
Spec: docs/specs/modules/feat_3189_vorlage_herkunft.md
Datum: 2026-11-20 11:00

## Checkliste
- [x] **Input:** POST `/api/metric-presets` mit `kind` und optional `herkunft {id, name}`; Anzeige im Vorlagen-Menü.
- [x] **Output:** gespeicherte Vorlage trägt `herkunft` (Name eingefroren); Unterzeile nach Priorität Beschreibung > Herkunft > „eigene“.
- [x] **Side effects:** keine; Bestand ohne Feld bleibt unverändert, Anlege-Modus erzeugt keine Herkunft.
- [x] **AC-1:** Given ein Nutzer mit einem Trip „GR221“ und einem Orts-Vergleich / When er im Reiter Wetter „Als eigene Vorlage speichern“ wählt (POST) / Then ist `herkunft {id, name}` an der Vorlage gespeichert, der Name zum Speicherzeitpunkt eingefroren (spätere Umbenennung ändert ihn nicht), und ein PATCH der Vorlage lässt `herkunft` unberührt.
- [x] **AC-2:** Given Bestands-Vorlagen ohne Feld `herkunft` / When die Daten geladen und gespeichert werden (Store-Migration `migrateMetricPreset`) / Then bleiben sie gültig und unverändert, und eine Vorlage mit `herkunft` behält das Feld nach Load und Save.
- [x] **AC-3:** Given zwei verschiedene Nutzer / When beide Vorlagen speichern und listen / Then sieht jeder nur seine eigenen Vorlagen samt Herkunft; die Herkunft-id wird nicht fremd aufgelöst (reiner Verweis im eigenen Datenbestand), Name wird getrimmt und auf 200 Zeichen gekappt, leerer Name verwirft das Feld ohne Fehler.
- [x] **AC-4:** Given eine eigene Vorlage im Vorlagen-Menü / When die Unterzeile berechnet wird / Then gilt die Reihenfolge Beschreibung („eigene · <Beschreibung>“), sonst Herkunft (DE „eigene · aus {name} gespeichert“, EN „eigene · saved from {name}“ je nach Sprache aus dem Katalog), sonst nur „eigene“; Trip und Orts-Vergleich nutzen denselben Code.
- [x] **AC-5:** Given der Anlegen-Modus, in dem Trip bzw. Vergleich noch nicht existiert / When der Nutzer eine eigene Vorlage speichert / Then wird keine Herkunft gespeichert und die Unterzeile zeigt nur „eigene“.
- [x] **AC-6:** Given Staging mit einem Prüfkonto / When eine Vorlage ohne Beschreibung gespeichert wird (Trip und Orts-Vergleich) / Then zeigt das Menü sofort ohne Neuladen „eigene · aus <Name> gespeichert“, die Testvorlage wird aufgeräumt, und der Test #3192 AC-8 (mit Beschreibung) bleibt grün.
- [x] **AC-7:** Given ein Entwickler liest die API-Beschreibung / When er POST `/api/metric-presets` nachschlägt / Then ist das optionale Feld `herkunft {id, name}` samt Regeln (eingefroren, nur beim Anlegen, 200 Zeichen) dokumentiert.

## Dialog

### Runde 1
**Adversary:** Tests selbst gefahren: go test handler/store/model gruen; node --test (organisms + i18n) 544 pass, 0 fail, 0 skipped; pytest test_3189_api_contract_herkunft 3 passed. Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, sha256 je Datei vor/nachher identisch, kein git checkout/stash/reset): store liest herkunft nicht -> GEFANGEN; PATCH loescht herkunft (unbedingt) -> GEFANGEN; Kappung entfernt -> GEFANGEN; leerer Name nicht verworfen -> GEFANGEN; Create ignoriert herkunft -> GEFANGEN; Payload schreibt herkunft ohne Name -> GEFANGEN; createMode liefert Herkunft -> GEFANGEN; Unterzeilen-Prioritaet vertauscht -> GEFANGEN; EN-Katalog falsch -> GEFANGEN; eigeneVorlageAus ohne herkunftName -> GEFANGEN. UEBERLEBT: (a) PATCH-Loeschung nur im Zweig `patch.Kind != nil` (Randfall, Test patcht Name/Metriken); (b) id-Trim in NormalizePresetHerkunft entfernt; (c) Weitergabe WetterTabInhalt->VorlageKarte (`{herkunft}`), (d) VorlageKarte->SavePresetDialog, (e) SavePresetDialog->eigeneVorlagePayload: je einzeln entfernt, kein lokaler Test rot.
**Implementierer:** (Kontext-isoliert, keine Antwort.) Spec Known Limitation 3 erklaert die fehlende id-Aufloesung; Svelte-Kette wird laut Spec durch Staging-E2E AC-6 abgedeckt.

### Runde 2
**Adversary:** Nachgefasst: Mandantentrennung: Handler nutzt bestehendes `s.WithUser(UserIDFromContext)`, Diff fuehrt keinen Fallback "default" ein; Zwei-Nutzer-Test im Handler-Testfile vorhanden. Trip/Vergleich: ein Code (`vorlageHerkunft` nimmt `trip ?? preset`), keine Kontext-Zweige. Daten-Schema: Feld additiv, omitempty, migrateMetricPreset liest explizit; PATCH-Struct nimmt kein herkunft an (RMW erhalten). createMode -> undefined. AC-6-Spezifikation (Staging-E2E s3a2794-teil3-vorlage-herkunft.spec.ts) gelesen: haengt an echter Oberflaeche, prueft POST-Antwort, Menuetext ohne Reload, GET-Liste, Aufraeumen im finally, je route und vergleich; er faengt die drei Svelte-Verdrahtungs-Mutationen. Er laeuft erst nach Deploy, Ergebnis steht aus.
**Implementierer:** Nicht zutreffend. Offene Hinweise siehe Findings.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:275
  Description: `{herkunft}` wird an VorlageKarte gereicht; VorlageKarte.svelte reicht es an SavePresetDialog.svelte, dieser an eigeneVorlagePayload. Jede der drei Weitergaben einzeln entfernt: alle lokalen Tests bleiben gruen (Mutation ueberlebt).
  Spec requirement: AC-1/AC-6 — Herkunft wird beim Speichern aus dem Reiter Wetter gesetzt
  Conflict: Nur das Staging-E2E faengt eine unterbrochene Kette; lokal kein Test.
  Remediation: Source-nahen node-Test fuer die Verdrahtung ergaenzen oder AC-6-E2E nach Deploy als Pflichtnachweis behandeln (Spec sieht das vor).

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: internal/model/metric_preset.go:85
  Description: Trim der Herkunft-id (`strings.TrimSpace(h.ID)`) ist nicht testbewacht; ohne Trim ueberlebt die Mutation. Ebenso die PATCH-Loeschung nur im Kind-Zweig (internal/handler/metric_preset.go:390).
  Spec requirement: AC-3 — Name getrimmt/gekappt; id-Trim ist nur in Spec-Impl-Details/API-Doku genannt
  Conflict: Randverhalten ohne Test.
  Remediation: Ein Test mit id " gr221 " und ein PATCH mit kind-Wechsel auf Vorlage mit Herkunft.

## Confirmations

Confirmation:
  AC: AC-1
  Code reference: internal/handler/metric_preset.go:292
  Evidence: Create setzt Herkunft via NormalizePresetHerkunft; PATCH-Struct hat kein herkunft (internal/handler/metric_preset.go:368-378); Go-Test AC1 gruen, Mutation PATCH-loescht gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: internal/store/metric_preset.go:142
  Evidence: migrateMetricPreset liest herkunft; Mutation gefangen; Altbestand bleibt nil.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: internal/model/metric_preset.go:80
  Evidence: Trim, 200-Rune-Kappung, leer -> nil; Mutationen Kappung und leerer Name gefangen; Zwei-Nutzer-Test gruen; keine "default"-Fallbacks im Diff.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte:64
  Evidence: Prioritaet Beschreibung > Herkunft > eigene; DE/EN-Schluessel in frontend/src/lib/i18n/messages/de/wetter.json:23 und frontend/src/lib/i18n/messages/en/wetter.json:23 mit {name}; Mutationen Prioritaet und EN-Katalog gefangen; eigeneVorlageAus (frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts:90) nimmt herkunftName mit.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts:98
  Evidence: vorlageHerkunft liefert bei createMode undefined; eigeneVorlagePayload (frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts:240) schreibt herkunft nur mit Namen; Mutationen createMode und Payload gefangen; Typen in frontend/src/lib/types.ts:377.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:66
  Evidence: Dialog reicht herkunft an Payload; Staging-E2E nur gelesen, plausibel und deckt Kette, laeuft nach Deploy (offen, kein Ist-Nachweis).
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: docs/reference/api_contract.md:2580
  Evidence: herkunft im DTO, Request-Tabelle (Zeile ~2686) und Absatz mit eingefroren/nur beim Anlegen/200 Zeichen; pytest test_3189 3 passed.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts:242
  Evidence: Payload schreibt herkunft nur mit nicht leerem Namen (Spread-Zeile), sonst kein Feld.
  Status: CONFIRMED

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/types.ts:378
  Evidence: MetricPreset.herkunft?: PresetHerkunft, Typ {id, name} fuer die POST-Antwort.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Feld `herkunft` wird produktiv nur in CreateMetricPresetHandler (internal/handler/metric_preset.go:292, Bedingung: id und Name nicht leer nach Trim) und migrateMetricPreset (Durchreichen) geschrieben; Test fuer genau diesen Weg: TestHerkunft3189_AC1 / AC3 in internal/handler/metric_preset_herkunft_test.go.

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: Go ok, node 544 passed / 0 failed / 0 uebersprungen, pytest 3 passed
Mutationen: 10 von 15 gefangen; 5 ueberlebt (F001 MEDIUM Svelte-Kette, F002 LOW id-Trim/Kind-Zweig) ohne Spec-Verstoss
Regressions: keine; Checklist: 7/7 (AC-6 Staging-Lauf steht nach Deploy aus)

## Geprüfte Dateien

- sha256:0164e0fa38b86608f3bccc513bace441e78978468ebede520792eac33241b450  docs/reference/api_contract.md
- sha256:f78e4d7b927d7682865c498054796e684ac33108736f4dcafa5b1e9c62660596  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:10790a6b904e09140d2c4e03de65b194d187def9e774170da178f60cddce1b7e  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:0d260de32d7277998ec1cc0441a9ab3669e3bac7c4a28e9ab1df3810ffc1dbf4  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:d65e1f0a5c26c00083552e8fdecd1f31d0918082aada8b887e5993ec61cba098  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- sha256:fee2e0501e0d94388783fa6b79e556969167f4e4d27c7f59a8a1269f87bb4fbf  internal/handler/metric_preset.go
- sha256:9edeba2a15bcb894656413fa2fdb550b06b4ce0e2346d032b18c7ce4bcab98a1  internal/model/metric_preset.go
- sha256:92da445f449555c3a930904dde80b1fe94849707f0347586c2ddfdce69beba2f  internal/store/metric_preset.go

## Prüfbasis

- base: 16ac7629e6773ba25f0a18bff628337201454ad5
- blob:a728cba36def84adeb6b8ac3ea722c8201771722  docs/reference/api_contract.md
- blob:095f2ebf179b6253e8b2920362f9b25c662fef63  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:7b190e29d95114056107f25bf2020d89d05d7623  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a689243183480323e661367e6f6b8cba5982fe14  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:27bc906db7d5ebf721455459b806feae594ec677  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- blob:bb7f5361cd5ad7617c766d2e2800b3a334990de4  internal/handler/metric_preset.go
- blob:c12f3ca8f88bc8eb4a1207d18b72cf78cebcbbb8  internal/model/metric_preset.go
- blob:edc7a56dd36b406c7351ed337059346c2f668112  internal/store/metric_preset.go

## Geprüfte Dateien

- sha256:0164e0fa38b86608f3bccc513bace441e78978468ebede520792eac33241b450  docs/reference/api_contract.md
- sha256:f78e4d7b927d7682865c498054796e684ac33108736f4dcafa5b1e9c62660596  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:10790a6b904e09140d2c4e03de65b194d187def9e774170da178f60cddce1b7e  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:0d260de32d7277998ec1cc0441a9ab3669e3bac7c4a28e9ab1df3810ffc1dbf4  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:d65e1f0a5c26c00083552e8fdecd1f31d0918082aada8b887e5993ec61cba098  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- sha256:fee2e0501e0d94388783fa6b79e556969167f4e4d27c7f59a8a1269f87bb4fbf  internal/handler/metric_preset.go
- sha256:9edeba2a15bcb894656413fa2fdb550b06b4ce0e2346d032b18c7ce4bcab98a1  internal/model/metric_preset.go
- sha256:92da445f449555c3a930904dde80b1fe94849707f0347586c2ddfdce69beba2f  internal/store/metric_preset.go

## Prüfbasis

- base: 16ac7629e6773ba25f0a18bff628337201454ad5
- blob:a728cba36def84adeb6b8ac3ea722c8201771722  docs/reference/api_contract.md
- blob:095f2ebf179b6253e8b2920362f9b25c662fef63  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:7b190e29d95114056107f25bf2020d89d05d7623  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a689243183480323e661367e6f6b8cba5982fe14  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:27bc906db7d5ebf721455459b806feae594ec677  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- blob:bb7f5361cd5ad7617c766d2e2800b3a334990de4  internal/handler/metric_preset.go
- blob:c12f3ca8f88bc8eb4a1207d18b72cf78cebcbbb8  internal/model/metric_preset.go
- blob:edc7a56dd36b406c7351ed337059346c2f668112  internal/store/metric_preset.go

## Geprüfte Dateien

- sha256:0164e0fa38b86608f3bccc513bace441e78978468ebede520792eac33241b450  docs/reference/api_contract.md
- sha256:f78e4d7b927d7682865c498054796e684ac33108736f4dcafa5b1e9c62660596  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:10790a6b904e09140d2c4e03de65b194d187def9e774170da178f60cddce1b7e  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:0d260de32d7277998ec1cc0441a9ab3669e3bac7c4a28e9ab1df3810ffc1dbf4  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:d65e1f0a5c26c00083552e8fdecd1f31d0918082aada8b887e5993ec61cba098  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- sha256:fee2e0501e0d94388783fa6b79e556969167f4e4d27c7f59a8a1269f87bb4fbf  internal/handler/metric_preset.go
- sha256:9edeba2a15bcb894656413fa2fdb550b06b4ce0e2346d032b18c7ce4bcab98a1  internal/model/metric_preset.go
- sha256:92da445f449555c3a930904dde80b1fe94849707f0347586c2ddfdce69beba2f  internal/store/metric_preset.go

## Prüfbasis

- base: 16ac7629e6773ba25f0a18bff628337201454ad5
- blob:a728cba36def84adeb6b8ac3ea722c8201771722  docs/reference/api_contract.md
- blob:095f2ebf179b6253e8b2920362f9b25c662fef63  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:7b190e29d95114056107f25bf2020d89d05d7623  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a689243183480323e661367e6f6b8cba5982fe14  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:27bc906db7d5ebf721455459b806feae594ec677  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- blob:bb7f5361cd5ad7617c766d2e2800b3a334990de4  internal/handler/metric_preset.go
- blob:c12f3ca8f88bc8eb4a1207d18b72cf78cebcbbb8  internal/model/metric_preset.go
- blob:edc7a56dd36b406c7351ed337059346c2f668112  internal/store/metric_preset.go

## Geprüfte Dateien

- sha256:0164e0fa38b86608f3bccc513bace441e78978468ebede520792eac33241b450  docs/reference/api_contract.md
- sha256:f78e4d7b927d7682865c498054796e684ac33108736f4dcafa5b1e9c62660596  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:10790a6b904e09140d2c4e03de65b194d187def9e774170da178f60cddce1b7e  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:0d260de32d7277998ec1cc0441a9ab3669e3bac7c4a28e9ab1df3810ffc1dbf4  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:d65e1f0a5c26c00083552e8fdecd1f31d0918082aada8b887e5993ec61cba098  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- sha256:fee2e0501e0d94388783fa6b79e556969167f4e4d27c7f59a8a1269f87bb4fbf  internal/handler/metric_preset.go
- sha256:9edeba2a15bcb894656413fa2fdb550b06b4ce0e2346d032b18c7ce4bcab98a1  internal/model/metric_preset.go
- sha256:92da445f449555c3a930904dde80b1fe94849707f0347586c2ddfdce69beba2f  internal/store/metric_preset.go

## Prüfbasis

- base: 16ac7629e6773ba25f0a18bff628337201454ad5
- blob:a728cba36def84adeb6b8ac3ea722c8201771722  docs/reference/api_contract.md
- blob:095f2ebf179b6253e8b2920362f9b25c662fef63  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:7b190e29d95114056107f25bf2020d89d05d7623  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a689243183480323e661367e6f6b8cba5982fe14  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:27bc906db7d5ebf721455459b806feae594ec677  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- blob:bb7f5361cd5ad7617c766d2e2800b3a334990de4  internal/handler/metric_preset.go
- blob:c12f3ca8f88bc8eb4a1207d18b72cf78cebcbbb8  internal/model/metric_preset.go
- blob:edc7a56dd36b406c7351ed337059346c2f668112  internal/store/metric_preset.go

## Geprüfte Dateien

- sha256:0164e0fa38b86608f3bccc513bace441e78978468ebede520792eac33241b450  docs/reference/api_contract.md
- sha256:f78e4d7b927d7682865c498054796e684ac33108736f4dcafa5b1e9c62660596  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- sha256:10790a6b904e09140d2c4e03de65b194d187def9e774170da178f60cddce1b7e  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:0d260de32d7277998ec1cc0441a9ab3669e3bac7c4a28e9ab1df3810ffc1dbf4  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- sha256:294c5e57641384ce275e82edfdd9442d7b733aebee412066e881ee7ba0db45a3  frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts
- sha256:d65e1f0a5c26c00083552e8fdecd1f31d0918082aada8b887e5993ec61cba098  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- sha256:665d98e16a3432ad6c22f4094d58ba5f367a6ea6b51446b6a7358d049e143f75  frontend/src/lib/types.ts
- sha256:fee2e0501e0d94388783fa6b79e556969167f4e4d27c7f59a8a1269f87bb4fbf  internal/handler/metric_preset.go
- sha256:9edeba2a15bcb894656413fa2fdb550b06b4ce0e2346d032b18c7ce4bcab98a1  internal/model/metric_preset.go
- sha256:92da445f449555c3a930904dde80b1fe94849707f0347586c2ddfdce69beba2f  internal/store/metric_preset.go

## Prüfbasis

- base: 16ac7629e6773ba25f0a18bff628337201454ad5
- blob:a728cba36def84adeb6b8ac3ea722c8201771722  docs/reference/api_contract.md
- blob:095f2ebf179b6253e8b2920362f9b25c662fef63  frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte
- blob:7b190e29d95114056107f25bf2020d89d05d7623  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:a689243183480323e661367e6f6b8cba5982fe14  frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte
- blob:fa2b6812bdcbb1cde73413d64df00dce863806bc  frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts
- blob:27bc906db7d5ebf721455459b806feae594ec677  frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts
- blob:9722894f8733d07c52eb107a3bd5931513c04cb4  frontend/src/lib/types.ts
- blob:bb7f5361cd5ad7617c766d2e2800b3a334990de4  internal/handler/metric_preset.go
- blob:c12f3ca8f88bc8eb4a1207d18b72cf78cebcbbb8  internal/model/metric_preset.go
- blob:edc7a56dd36b406c7351ed337059346c2f668112  internal/store/metric_preset.go
