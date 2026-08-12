---
entity_id: fix_923b_wire_live_sms_preview
type: bugfix
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.0"
tags: [sms, fidelity-preview, trip-editor, dead-code-cleanup]
---

# Fix #923b — SMS-Fidelity-Vorschau an die live gerenderte Komponente anschließen

> **Abgelöst durch #1719 S3 (2026-08-11):** Die hier verdrahtete Zielkomponente
> `WeatherV2MailPreview.svelte` und die Live-Vorschau „So kommt es an" sind auf
> PO-Entscheid ersatzlos entfernt (Komponente gelöscht, ebenso
> `trip-detail/smsFidelityPreview.ts`). Der in dieser Scheibe angeschlossene
> Endpoint `POST /api/_validator/sms-fidelity-preview` bleibt registriert, hat
> seither aber keinen Live-Konsumenten mehr. Details:
> `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md`.

## Approval

- [x] Approved

## Purpose

#923 verdrahtete den SMS-Fidelity-Server-Endpoint gegen tote Komponenten
(`ChannelFidelitySMS.svelte` u. a.) — die Trip-Editor-Route rendert tatsächlich
`WeatherV2MailPreview.svelte`, die weiterhin ihre eigene, veraltete SMS-Simulation
(hartcodiertes `SMS_TOK`-Dict, 140-Zeichen-Limit, `Z:WATCH`-Anhang) zeigt. Diese
Scheibe schließt den bereits funktionierenden Backend-Endpoint an die ECHTE
Komponente an, blendet die SMS-Kachel im Ortsvergleich-Editor kontrolliert aus
(statt sie falsch zu simulieren), räumt den entstandenen toten Code auf und behebt
eine unabhängig gefundene Katalog/Renderer-Inkonsistenz bei `temperature_night`.

## Source

- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2MailPreview.svelte`
- **Identifier:** `<script>`-Block, SMS-Zweig ab Zeile 260 (`{#if channel === 'email'} ... {:else}` SMS-Vorschau)

> **Schicht-Hinweis geprüft:** Frontend-Änderungen liegen ausschließlich unter
> `frontend/src/lib/components/...` (SvelteKit). Der Backend-Fix liegt in
> `src/app/metric_catalog.py` (Python-Core, Katalog-Modul). Es gibt keine
> Go-API-Berührung in dieser Scheibe.

## Estimated Scope

- **LoC:** ~150-200 (netto, geänderte/neue Dateien; Löschungen zählen laut
  Projektkonvention nicht als Zuwachs)
- **Files:** 5 geändert, 6 gelöscht, 1 neu (Test)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/_validator/sms-fidelity-preview` (`api/routers/validator.py`) | endpoint | Liefert `line`/`char_count`/`max_length`/`carried_ids` — unverändert aus #923 |
| `render_sms_fidelity_preview()` / `build_sms_fidelity_specs()` (`src/services/validator_render_service.py`) | function | Backend-Pipeline hinter dem Endpoint — unverändert |
| `loadSmsFidelityPreview()` (`frontend/src/lib/components/trip-detail/smsFidelityPreview.ts`) | utility | DOM-freie Fetch/Catch-Logik, wiederverwendet statt neu gebaut |
| `WeatherMetricsTab.svelte` (`frontend/src/lib/components/shared/`) | component | Einbindestelle, muss `context`-Prop an `WeatherV2MailPreview` durchreichen |
| `SMS_MULTI_SYMBOLS_BY_METRIC` (`src/output/renderers/sms_trip.py`) | mapping | Tatsächliche Symbol-Zuordnung, unabhängig vom Katalog — Root-Cause der AC-4-Inkonsistenz |

## Implementation Details

### 1. `WeatherV2MailPreview.svelte` — echte Server-Anbindung

- Neue Prop `context: 'route' | 'vergleich'` ergänzen (analog `LayoutTab`/`WeatherMetricsTab`-Konvention).
- Eigenes `SMS_TOK`-Dict (Zeile 131), `smsLine`-Derivation (Zeile 135-143) und die
  hartcodierte `140`-Anzeige (Zeile 265) vollständig entfernen.
- Bei `channel === 'sms' && context === 'route'`: Lade-/Fehler-Zustand nach dem
  Muster des gelöschten `ChannelFidelitySMS.svelte` (`$effect`, `loading`/`error`-
  State, `previewOverride`-Prop für SSR-Testbarkeit — `svelte/server`s `render()`
  führt kein `$effect`/`onMount` aus). Aufruf über `loadSmsFidelityPreview(
  primaryColumns, (path, body) => api.post(path, body))` aus `smsFidelityPreview.ts`.
  Anzeige: `preview.line` statt `smsLine`, `${preview.char_count}/${preview.max_length}
  Zeichen` statt `{smsLine.length}/140 Zeichen`.
- Bei `channel === 'sms' && context === 'vergleich'`: die gesamte SMS-Vorschau-Kachel
  (`data-testid="wm2-sms-line"`-Block) wird NICHT gerendert — kein Platzhaltertext,
  kein Fake-Rendering, kein `api.post`-Aufruf. PO-Entscheidung 2026-08-06: der
  Backend-Endpoint ist strukturell an die Trip-Etappen-Token-Line-Pipeline gebunden
  (Format "Etappe: ..."), eine Mehrort-Vergleichszeile ist ein eigenes, größeres
  Vorhaben und explizit out of scope für diese Scheibe.
- E-Mail- und Telegram-Zweig (Zeile 171-258) bleiben unverändert — nur der
  SMS-Zweig ist betroffen.

### 2. `WeatherMetricsTab.svelte` — Context durchreichen

Beide Einbindestellen von `<WeatherV2MailPreview>` (Desktop-Snippet ~Zeile 1160,
Mobile Bottom-Sheet ~Zeile 1418) bekommen zusätzlich `{context}` als Prop
(die Komponente selbst führt `context` bereits als lokale Variable, Default `'route'`,
s. Zeile 141).

### 3. Tote Dateien löschen

Vollständig entfernen (keine Referenzen außerhalb von `organisms/index.ts`):
- `frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte`
- `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte`
- `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte`
- `frontend/src/lib/components/trip-detail/ChannelFidelityEmail.svelte` (nur über
  das ebenfalls tote `ChannelPreviewBlock.svelte` erreichbar)
- `frontend/src/lib/components/trip-detail/ChannelFidelityBubble.svelte` (dito)
- `frontend/src/lib/components/trip-detail/__tests__/channel_sms_fidelity_backend_render.test.ts`
  (testet ausschließlich die gelöschten Komponenten; Kern-Assertionen wandern in
  den neuen Test, s. u.)

In `frontend/src/lib/components/organisms/index.ts` die beiden Re-Export-Zeilen
für `ChannelPreviewBlock`/`ChannelPreviewCard` entfernen (Zeile 21-22).

`frontend/src/lib/components/trip-detail/smsFidelityPreview.ts` bleibt als Datei
bestehen (die generische Utility-Funktion wird weiterverwendet) — nur der
Kopfkommentar wird korrigiert: nicht mehr "Compare out of scope" pauschal, sondern
"route-only Live-Anbindung ab #923b, `context==='vergleich'` blendet die Kachel
aus statt die Utility aufzurufen".

### 4. Backend-Fix: `temperature_night` bekommt einen `sms_code`

`src/app/metric_catalog.py`, `MetricDefinition(id="temperature_night", ...)`:
`sms_code="TN"` ergänzen. Root-Cause: `SMS_MULTI_SYMBOLS_BY_METRIC` in
`src/output/renderers/sms_trip.py:120` führt für `temperature_night` bereits das
Symbol `"N"` (unabhängig vom Katalog) — die Metrik erscheint deshalb schon heute
in `carried_ids`, obwohl der Katalog `sms_code=""` (leer) zeigt. Diese Diskrepanz
lässt die UI (`metricById[id]?.sms_code`) für eine tatsächlich getragene Metrik
einen leeren Token statt eines Kürzels anzeigen. `"TN"` ist geprüft kollisionsfrei
(deckt sich mit dem bereits vorhandenen `compact_label="TN"` derselben Metrik;
Kollisionsprüfung gegen alle bestehenden `sms_code`-Werte in `_METRICS` sowie den
bestehenden Wächter `tests/tdd/test_issue_917_alert_renderer.py::
test_all_sms_codes_globally_unique`). `temperature_cold` (interne Alarm-
Pseudogröße, `sms_code="N"`) bleibt unverändert — beide Katalogeinträge dürfen
unterschiedliche `sms_code` tragen, weil sie unterschiedliche Zwecke haben
(Katalog-Anzeige vs. tatsächliches Render-Symbol); der bestehende AC-4-Test
(`tests/unit/test_sms_fidelity_preview.py::TestAC4_MetricWithoutSmsCodeExcluded`)
bleibt unverändert grün, da er gegen `cloud_total` (kein Token-Symbol überhaupt)
prüft, nicht gegen `temperature_night`.

### 5. Neuer Test

`frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weather_v2_mail_preview_sms_fidelity.test.ts`

SSR-Render-Test nach dem Muster des gelöschten
`channel_sms_fidelity_backend_render.test.ts` (`svelte/server`, `previewOverride`-
Prop). Deckt ab:
- Server-`line`-Text erscheint exakt im DOM (kein `SMS_TOK`/`Z:WATCH`-Rest).
- Zeichenzähler zeigt Server-`char_count`/`max_length` (kein hartcodiertes `/140`).
- `context==='vergleich'`: SMS-Kachel (`data-testid="wm2-sms-line"`) fehlt komplett
  im DOM, unabhängig vom `channel`-Prop-Wert `'sms'`.
- Mutations-taugliche Gegenprobe: eine bewusst abweichende `previewOverride`-Zeile
  muss im DOM ankommen (beweist, dass die Komponente nicht lokal simuliert,
  sondern den übergebenen Serverwert 1:1 zeigt).

## Expected Behavior

- **Input:** Nutzer wählt im Trip-Editor (Wetter-Metriken-Tab) den Kanal "SMS" und
  hat mindestens eine Metrik aktiviert.
- **Output:** Die Vorschau-Kachel zeigt den echten, vom Server gerenderten
  Token-Text und die echte 160-Zeichen-Grenze — keine lokal simulierten Werte.
- **Side effects:** Bei `context==='route'` löst die Kanalwahl "SMS" einen
  `POST /api/_validator/sms-fidelity-preview`-Aufruf aus (wie bisher bei den toten
  Komponenten geplant, jetzt tatsächlich wirksam). Bei `context==='vergleich'`
  entfällt dieser Aufruf vollständig — kein Netzwerk-Request, keine Kachel.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Trip-Editor, wählt im Wetter-Metriken-Tab
  den Kanal "SMS" und aktiviert die Metrik "Temperatur" / When die Vorschau lädt /
  Then zeigt die Kachel den vom Server gelieferten Text (`POST
  /api/_validator/sms-fidelity-preview`-Antwort), NICHT mehr `Z:WATCH` oder ein
  `SMS_TOK`-Kürzel aus der alten Eigenberechnung.
  - Test: SSR-Render mit `previewOverride`-Fixture, deren `line` einen eindeutigen
    Marker-String trägt — Assertion, dass genau dieser Text im DOM steht und die
    alten Marker (`Z:WATCH`, `SMS_TOK`-Kürzelmuster) fehlen.

- **AC-2:** Given die SMS-Kachel ist sichtbar / When der Zeichenzähler gerendert
  wird / Then zeigt er die vom Server gelieferte Zeichengrenze (160), nicht mehr
  die hartcodierte alte Grenze (140).
  - Test: SSR-Render mit `previewOverride.max_length` ungleich 140 (z. B. 160) —
    Assertion, dass der angezeigte Zähler diesen Wert übernimmt und `/140` nirgends
    im DOM vorkommt.

- **AC-3:** Given ein Nutzer öffnet den Ortsvergleich-Editor im Wetter-Metriken-Tab
  und wählt den Kanal "SMS" / When die Vorschau-Kachel gerendert wird / Then
  erscheint keinerlei SMS-Vorschau (kein Platzhaltertext, kein Fake-Rendering,
  kein Server-Aufruf) — der Bereich bleibt leer.
  - Test: SSR-Render mit `context='vergleich'`, `channel='sms'` — Assertion, dass
    `data-testid="wm2-sms-line"` NICHT im DOM vorkommt.

- **AC-4:** Given der Katalog-Eintrag `temperature_night` in `metric_catalog.py` /
  When `/api/metrics` bzw. die interne Katalog-Auflösung aufgerufen wird / Then
  trägt die Metrik einen nicht-leeren, kollisionsfreien `sms_code` ("TN"), der mit
  ihrer tatsächlichen Trägerschaft im SMS-Renderer (`SMS_MULTI_SYMBOLS_BY_METRIC`)
  übereinstimmt.
  - Test: `tests/unit/test_metric_catalog.py` (neuer oder erweiterter Testfall) —
    `get_sms_code("temperature_night") == "TN"`; zusätzlich läuft der bestehende
    globale Eindeutigkeits-Wächter (`tests/tdd/test_issue_917_alert_renderer.py::
    test_all_sms_codes_globally_unique`) unverändert grün.

- **AC-5:** Given die fünf toten Altdateien (`ChannelFidelitySMS.svelte`,
  `ChannelPreviewCard.svelte`, `ChannelPreviewBlock.svelte`,
  `ChannelFidelityEmail.svelte`, `ChannelFidelityBubble.svelte`) / When das Delta
  committet wird / Then existieren diese Dateien nicht mehr im Repository und
  `organisms/index.ts` re-exportiert sie nicht mehr.
  - Test: `git ls-files` bzw. Dateisystem-Check in einem Gate-/CI-Kontext — die
    Pfade dürfen nicht auffindbar sein; Grep auf `ChannelPreviewBlock`/
    `ChannelPreviewCard` in `organisms/index.ts` liefert keinen Treffer.

- **AC-6:** Given die SMS-Vorschau-Kachel im Trip-Editor (`context='route'`) / When
  sie über die reale Nutzer-Route erreicht wird (nicht nur über einen isolierten
  Komponenten-Import) / Then ist die tatsächlich live gerenderte Komponente
  `WeatherV2MailPreview.svelte`, eingebunden über `WeatherMetricsTab.svelte` in
  `TripEditView.svelte`/`TripNewEditor.svelte` — das war der Root-Cause-Fehler von
  #923 (Verdrahtung gegen eine nur über den Barrel-Export erreichbare, tote
  Komponente).
  - Test: Playwright-E2E gegen Staging (echter Klickpfad: Trip öffnen → Wetter-
    Metriken-Tab → Kanal "SMS" wählen) — Assertion, dass der angezeigte Text dem
    Server-Endpoint entspricht, NICHT der alten `Z:WATCH`/`SMS_TOK`-Simulation.
    Ergänzend: Grep-Nachweis, dass `WeatherV2MailPreview.svelte` von
    `WeatherMetricsTab.svelte` importiert wird und diese wiederum von
    `TripEditView.svelte`/`TripNewEditor.svelte` — eine Importkette bis zur Route,
    nicht nur bis zu `organisms/index.ts`.

## Test Plan

### Automated Tests (Kern, deterministisch)

- **Neu:** `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weather_v2_mail_preview_sms_fidelity.test.ts`
  — SSR-Render (`svelte/server`) von `WeatherV2MailPreview.svelte` mit
  `previewOverride`-Fixtures. Deckt AC-1, AC-2, AC-3 ab. Migriert die
  Kernassertionen aus dem gelöschten `channel_sms_fidelity_backend_render.test.ts`
  (Server-Text exakt im DOM, kein alter Präfix/Anhang, Zeichenzähler-Werte) plus
  den neuen `context='vergleich'`-Fall.
- **Erweitert:** `tests/unit/test_metric_catalog.py` — `get_sms_code("temperature_night")`
  liefert `"TN"`. Deckt AC-4 ab (Python-Kernschicht, kein Netz).
- **Unverändert grün (Regressions-Nachweis):**
  - `tests/unit/test_sms_fidelity_preview.py` (AC-1 bis AC-5, AC-9 aus #923 —
    Backend-Endpoint bleibt unverändert)
  - `tests/tdd/test_issue_917_alert_renderer.py::test_all_sms_codes_globally_unique`
    (keine `sms_code`-Kollision nach dem `temperature_night`-Fix)
  - `frontend/src/lib/components/trip-detail/__tests__/sms_fidelity_preview_fetch.test.ts`
    (generische Utility-Funktion, komponentenunabhängig, nicht Teil des Deltas)

### Live-E2E (Staging, `/e2e-verify`)

- Playwright: Trip-Editor öffnen → Wetter-Metriken-Tab → Kanal "SMS" wählen →
  Assertion auf Server-gerenderten Text (deckt AC-6/Erreichbarkeit über die reale
  Route ab, plus visuelle Bestätigung von AC-1/AC-2 im echten Browser-Kontext).
- Playwright: Ortsvergleich-Editor öffnen → Wetter-Metriken-Tab → Kanal "SMS"
  wählen → Assertion, dass keine SMS-Kachel sichtbar ist (deckt AC-3 im echten
  Browser-Kontext ab).

## Known Limitations

- Der Ortsvergleich-Editor bekommt in dieser Scheibe explizit KEINE eigene
  Mehrort-SMS-Vorschau — das Ausblenden ist die bewusste, endgültige Lösung für
  diese Scheibe (PO-Entscheidung 2026-08-06), nicht ein Platzhalter für eine
  spätere Ergänzung innerhalb dieser Spec. Eine künftige Compare-SMS-Vorschau
  wäre ein eigenes, neu zu spezifizierendes Vorhaben.
- `temperature_cold` (interne Alarm-Pseudogröße) behält weiterhin `sms_code="N"`,
  unverändert durch diese Scheibe — beide Katalogeinträge dürfen dasselbe Kürzel-
  Präfix-Muster ("N"/"TN"), aber unterschiedliche Werte tragen, da sie
  unterschiedliche Domänen betreffen (Alarm-Schwelle vs. Trip-Anzeige).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bereits bestehend — "ein einziger Backend-Renderer, kein
  zweiter im Frontend")
- **Rationale:** Diese Scheibe setzt ADR-0011 erstmals tatsächlich in der live
  gerenderten Komponente um (bisher nur in der toten Komponente aus #923). Kein
  neues ADR nötig — die Entscheidung war bereits getroffen, #923b korrigiert
  lediglich die fehlerhafte Verdrahtung.

## Changelog

- 2026-08-06: Initial spec created (Korrektur-Scheibe zu #923, Root-Cause:
  Verdrahtung gegen toten Code)
