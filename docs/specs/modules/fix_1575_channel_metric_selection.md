---
entity_id: fix_1575_channel_metric_selection
type: feature
created: 2026-08-08
updated: 2026-08-08
status: draft
workflow: fix-1575-channel-metric-selection
---

# Kanal-eigene Metrik-Auswahl im Trip-Editor — #1575 Scheibe 3 (Symptom B)

- **Issue:** #1575 Scheibe 3 von 3, Symptom B
- **Vorgänger (geteilter Organism):** `docs/specs/modules/layout_tab_route.md` (#1232 Scheibe 3b, live) — diese Scheibe löst dessen AC-6 teilweise ab, siehe „Architektur-Entscheidung" unten
- **Typ:** Full-Stack-Fix — ein kleiner Backend-Bugfix (Python) + ein neuer Frontend-Persistenzpfad (Svelte/TS), kein neues Datenschema (additive, bereits vorhandene Backend-Felder)

## Approval

- [x] Approved (PO, 2026-08-08)

## Purpose

Die Kanal-Reiter Email/Telegram/SMS im Wetter-Metriken-Tab des **Trip**-Editors
(`WeatherMetricsTab.svelte`, `context="route"`) schalten heute nur die
Vorschau um, ohne eigene Daten zu tragen — ein Klick auf "SMS" zeigt ein
SMS-Template, aber mit exakt derselben (globalen) Metrik-Auswahl wie Email.
Diese Scheibe gibt den Reitern eine echte Wirkung: Metrik-Auswahl,
Reihenfolge und Roh/Einfach-Modus werden pro Kanal gespeichert. Motivation
ist der KHW-Anwendungsfall — SMS an ein Garmin inReach soll andere/weniger
Größen zeigen können als die Email. Die Backend-Kaskade dafür existiert seit
#429/#434 bereits für Email und Telegram; SMS hat zusätzlich einen isolierten
Bug, der die Kaskade für SMS strukturell wirkungslos macht (siehe Teil 1).

## Source

- **Files:**
  - `src/output/renderers/trip_report.py` — MODIFY (SMS-Backend-Fix)
  - `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (1723 Z.) — MODIFY (neue Kanal-State, Save-Payload)
  - `frontend/src/lib/components/trip-detail/metricsEditor.ts` (514 Z.) — MODIFY (per-Kanal-Bucket-Helfer)
  - `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` — MODIFY
  - `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2MailPreview.svelte` — MODIFY (Fund, s. u.)
  - `frontend/e2e/layout-tab-route.spec.ts` — MODIFY
  - `frontend/src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts` — MODIFY
- **Identifier:** `dc.get_metrics_for_channel()` (`src/app/models.py:726`, unverändert genutzt), `channel_layouts` (Wire-Key unter `display_config`), `ChannelId`/`ChannelLayouts`/`WeatherConfigMetric` (`frontend/src/lib/types.ts`)

> **Schicht-Hinweis bestätigt:** Backend-Teil liegt in Python-Core (`src/output/renderers/`), Frontend-Teil in `frontend/src/lib/components/shared/**` (geteilte Trip/Compare-Schicht, hier nur der `route`-Zweig betroffen). Kein Go-Struct-Feld nötig — `DisplayConfig` ist in `internal/model` bereits `map[string]interface{}` (schemafrei).

## Estimated Scope

- **LoC:** Produktivcode ~200–350, Tests ~200–300 — **Überschreitung des
  250-LoC-Standardlimits wahrscheinlich.** `loc_limit_override` (Richtwert
  ~500, analog `layout_tab_route.md`-Vorgänger) ist vor Phase 6 **explizit
  beim PO einzuholen**, nicht eigenmächtig zu setzen.
- **Files:** ~7–9 (2 Backend inkl. Test, 5–7 Frontend inkl. Tests)
- **Effort:** high — neue Datenstruktur + Persistenzpfad in der am dichtesten
  getesteten Editor-Komponente des Projekts, plus eine bewusste Ablösung
  einer testgesicherten Vorgänger-Garantie (AC-6, s. u.)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/models.py:682-766` (`UnifiedWeatherDisplayConfig.per_channel_layouts`, `get_metrics_for_channel()`) | module | Backend-Kaskade (#429/#434) — bereits vollständig vorhanden für Email/Telegram, wird für SMS erst durch Teil 1 dieser Scheibe erreichbar; kein Neubau |
| `src/output/renderers/narrow.py:644` (`render_for_channel("telegram", dc, report_type)`) | module | Telegram-Backend bereits fertig verdrahtet — reiner Regressionsbeweis in dieser Scheibe, keine Änderung |
| `frontend/src/lib/components/shared/layout-tab/{LayoutTab,LTChannelPicker,LTCapNote,LTCutLine}.svelte`, `ltChannels.ts` | module | Geteilte Kanal-Picker-Hülle (#1232 Scheibe 3a/3b) — `channel`/`ChannelId` bleibt unverändert die UI-Steuergröße, wird hier zusätzlich zur Dateninhalt-Auswahl |
| `frontend/src/lib/types.ts:272-291` (`ChannelLayouts`, `ChannelLayoutsPerReport`, `WeatherConfigMetric`) | module | Wire-Typen existieren bereits (Issue #429/#434) — kein neuer Typ nötig, nur ein neuer Schreibweg dorthin |
| `frontend/src/lib/components/shared/layout-tab/channelLayoutsDirty.ts` (`channelLayoutsChangedByUser`) | module | **Fund:** bereits vorhandene, wertbasierte Dirty-Erkennung für `ChannelLayouts` aus #1269 (ursprünglich für den Compare-Kanal-Picker gebaut) — seit #1351 (Compare verwirft `channel_layouts` beim Speichern) nur noch von der eigenen Testdatei referenziert, sonst ungenutzt. Wiederverwendbar für die neue Trip-`isDirty`-Erweiterung statt eines Neubaus; ggf. Anpassung, falls die Trip-Bucket-Form von der Compare-Rohform abweicht — in Phase 5 zu prüfen |
| `internal/handler/config_merge.go:11-22` (`mergeConfigMap`), `internal/handler/trip.go:303-304` | module | Go-Merge ist **shallow auf oberster Schlüsselebene** von `display_config` — der Grund für den Pflicht-Test AC-3 (s. u.); kein Go-Code-Change nötig, wenn das Frontend beim Speichern den vollen `channel_layouts`-Stand mitsendet |
| `docs/specs/modules/layout_tab_route.md` (#1232 Scheibe 3b, live) | module | **Wird teilweise abgelöst**, s. „Architektur-Entscheidung" |
| `docs/specs/modules/rework_1351_compare_catalog.md` (#1351) | module | Harte Leitplanke: `channel_layouts` bleibt Trip-only — Compare (`context="vergleich"`) darf strukturell nicht berührt werden |
| `frontend/e2e/layout-tab-route.spec.ts`, `epic-138-metriken-editor.spec.ts`, `epic-138-block-b.spec.ts`, `issue-736/723/619/343/690/1117/932`-Specs | tests | Regressionsgates — bestehende Selektoren (`wm2-*`, `weather-metrics-*`, `sms-thresholds`) müssen unverändert grün bleiben |

## Implementation Details

### Teil 1 — Backend-Fix: SMS erbt die Email-Auswahl statt einer eigenen (`trip_report.py`)

`format_email()` in `trip_report.py` kollabiert `dc` **vor** dem eigentlichen
Rendern für Email (Z. 129–134):

```python
if report_type in ("morning", "evening"):
    active_metrics = dc.get_metrics_for_channel("email", report_type)
    active_metrics = [dataclasses.replace(mc, enabled=True) for mc in active_metrics]
    dc = dataclasses.replace(dc, metrics=active_metrics)
```

Ab hier ist `dc.metrics` bereits die **Email**-Auswahl. Der SMS-Aufbau
weiter unten (Z. 281–314, insbesondere `_sms_thr` Z. 282–286 und
`active_metric_ids` Z. 296) liest **dieselbe**, bereits kollabierte `dc`:

```python
_sms_thr = {
    SMS_SYMBOL_BY_METRIC[m.metric_id]: m.sms_threshold
    for m in dc.metrics                       # ← Email-kollabiert
    if m.metric_id in SMS_SYMBOL_BY_METRIC and m.sms_threshold is not None
}
...
active_metric_ids = {m.metric_id for m in dc.metrics}   # ← Email-kollabiert
```

SMS erbt dadurch strukturell die Email-Metrikauswahl und kann nie eine
eigene haben — unabhängig davon, was im Frontend unter `channel_layouts.sms`
gespeichert wird. **Fix:** vor der SMS-Symbol-Konstruktion eine eigene,
SMS-spezifische Metrikliste aus dem noch **ungekollabierten** `display_config`
ziehen (nicht aus dem oben bereits mutierten `dc`), um die **Menge** der
SMS-relevanten Metriken zu bestimmen — der **Schwellwert-Wert** selbst muss
weiterhin aus der **globalen** Metrikliste kommen:

> **Korrektur (RED-Phase, 2026-08-08):** Die ursprüngliche Fassung dieses
> Code-Beispiels baute `_sms_thr` direkt aus `sms_metrics` (`m.sms_threshold`
> für `m in sms_metrics`). Das ist falsch und wurde durch
> `test_globaler_sms_schwellwert_wirkt_auch_bei_sms_eigener_auswahl`
> (`tests/unit/test_trip_sms_channel_metric_selection.py`) widerlegt: die vom
> Editor geschriebenen Kanal-Layouts (`buildWeatherConfigMetrics`,
> `metricsEditor.ts:332`) führen **kein** `sms_threshold`-Feld — dessen Wert
> lebt ausschließlich in der globalen Metrikliste (PO-Scope-Entscheidung 1,
> KL-4). Bei kanal-eigener Auswahl wäre `m.sms_threshold` für jede Metrik in
> `sms_metrics` `None`, die konfigurierten Schwellwerte gingen lautlos
> verloren. Korrigierter Fix — Menge aus `sms_metrics`, Schwellwert-Wert aus
> der ungekollabierten globalen Liste:

```python
sms_metrics = (display_config or dc).get_metrics_for_channel("sms", report_type)
sms_metric_ids = {m.metric_id for m in sms_metrics}
_global_metrics = {m.metric_id: m for m in (display_config or dc).metrics}
_sms_thr = {
    SMS_SYMBOL_BY_METRIC[mid]: _global_metrics[mid].sms_threshold
    for mid in sms_metric_ids
    if mid in SMS_SYMBOL_BY_METRIC
    and mid in _global_metrics
    and _global_metrics[mid].sms_threshold is not None
}
...
active_metric_ids = sms_metric_ids
```

`sms_trip.py::format_sms` selbst bleibt unverändert — es ist ein reiner
Symbol-Renderer, der die bereits fertig gefilterten `MetricSpec`-Objekte aus
`trip_report.py` konsumiert; der Fund sitzt ausschließlich im Aufrufer.
`sms_threshold` selbst bleibt eine globale (nicht kanal-eigene) Konfiguration
pro Metrik (PO-Scope-Entscheidung, s. u.) — nur die **Menge der SMS-relevanten
Metriken** wird kanalspezifisch, nicht der Schwellwert-Wert.

### Teil 2 — Frontend: `channel_layouts` als eigener Persistenzpfad

**Neue State-Struktur** in `WeatherMetricsTab.svelte` (nur unter
`context === 'route'` aktiv gepflegt):

```ts
type ChannelOverride = { buckets: Buckets; friendlyMap: Record<string, boolean> } | null;
let channelBuckets = $state<Record<ChannelId, ChannelOverride>>({
  email: null, telegram: null, sms: null,
});
```

`null` = **kein eigener Eintrag** (copy-on-write, PO-Entscheidung 4) — der
Reiter zeigt und editiert in diesem Zustand die globale `buckets`/`friendlyMap`
direkt (analog Kaskaden-Ebene 3 im Backend: „kein `per_channel_layouts[channel]`
→ Fallback auf global"). Erst der erste tatsächliche Edit unter einem Reiter
(Drag&Drop, Modus-Wechsel, Entfernen) legt `channelBuckets[channel]` an — als
**Kopie** der zu diesem Zeitpunkt aktuellen globalen `buckets`/`friendlyMap`
(PO-Entscheidung: Startpunkt ist die globale Auswahl, nicht leer).

`WeatherV2Reihenfolge.svelte` und `WeatherV2MailPreview.svelte` lesen/schreiben
ab dieser Scheibe die **effektiven** Buckets/den effektiven `friendlyMap` für
den aktiven Kanal:

```ts
const effectiveBuckets = $derived(channelBuckets[activeChannel] ?? { buckets, friendlyMap });
```

**Fund (über die vom Auftraggeber gelieferte Dateiliste hinaus):**
`WeatherV2MailPreview.svelte` erhält heute `primaryColumns`/`friendlyMap` als
rohe, globale Props — nur `channel` steuert, welches Template (Email/
Telegram/SMS) gerendert wird, nicht welcher INHALT. Ohne Anpassung würde die
Vorschau weiterhin die globale Auswahl zeigen, selbst wenn der aktive Kanal
einen eigenen Eintrag hat. `WeatherMetricsTab.svelte` muss beim Rendern des
`preview`-Snippets die für den jeweiligen Kanal **effektiven** `primaryColumns`/
`friendlyMap` übergeben (aus `effectiveBuckets`, s. o.) statt der globalen
Variablen unverändert durchzureichen.

**Horizonte bleiben explizit global** (`horizonsMap` wird NICHT Teil von
`channelBuckets` — PO-Scope-Entscheidung 1): Reihenfolge und Roh/Einfach-Modus
sind die einzigen Bucket-Eigenschaften, die pro Kanal divergieren dürfen.

**Save-Payload** (`buildWeatherPayload()`, Z. 690–697) erhält einen neuen
Zweig, der — analog zum bestehenden Muster `...(trip!.display_config ?? {})`
— den **vollständigen bisherigen** `channel_layouts`-Stand aus `trip!.display_config`
übernimmt und nur den gerade aktiven Kanal überschreibt:

```ts
function buildWeatherPayload() {
  const prevLayouts = trip!.display_config?.channel_layouts ?? {};
  const nextLayouts = channelBuckets[activeChannel]
    ? { ...prevLayouts, [activeChannel]: buildWeatherConfigMetrics(
        channelBuckets[activeChannel]!.buckets,
        channelBuckets[activeChannel]!.friendlyMap,
        horizonsMap, catalog, aggregationsMap) }
    : prevLayouts;               // Kanal nie editiert → nichts Eigenes zu senden
  return {
    ...(trip!.display_config ?? {}),
    metrics: buildWeatherMetricsList(),
    channel_layouts: nextLayouts,
    preset_name: selectedTemplate || undefined,
    telegram_kurzform: telegramKurzform,
  };
}
```

Das schützt gegen den **Shallow-Merge-Datenverlust** (`config_merge.go`
ersetzt `channel_layouts` komplett, nicht feldweise): Speichert der Nutzer
im SMS-Reiter, ohne den Stand von zuvor bereits editierten Email-/Telegram-
Einträgen mitzusenden, würden diese sonst beim nächsten `PUT` lautlos
gelöscht (neuer BUG-DATALOSS-GR221-Fall). Deshalb liest `buildWeatherPayload()`
den `prevLayouts`-Stand immer aus `trip!.display_config` (der aktuellsten
bekannten Serverantwort), nicht aus einem lokalen Zwischenspeicher, der
zwischen Reitern veralten könnte.

**`isDirty`/`snapshot()`** (Z. 288–298) werden um `channelBuckets` erweitert.
Der reine Kanalwechsel (kein Edit) darf **weiterhin nicht** dirty machen
— dafür wird `channelBuckets` selbst nicht bei jedem Reiter-Klick verändert
(bleibt `null` bzw. unverändert, solange nichts editiert wurde), sondern nur
bei einem tatsächlichen Edit-Callback. Für den Vergleich `savedSnapshot`
vs. aktuellem State wird — analog dem Fund unter Dependencies —
`channelLayoutsChangedByUser`-artige, wertbasierte Normalisierung genutzt
statt eines rohen `JSON.stringify`-Vergleichs auf `channelBuckets`, damit
Kanonisierungs-Rauschen (z. B. `off`-Metriken-Reihenfolge) keine
Fehlalarme erzeugt (gleiches Prinzip wie in `channelLayoutsDirty.ts`
dokumentiert).

### Isolation zu `context="vergleich"` (strukturell, nicht nur Disziplin)

`channelBuckets`, `effectiveBuckets` und der neue Save-Zweig werden
ausschließlich in Codepfaden gelesen/geschrieben, die bereits heute hinter
`context === 'route'`-Branches liegen (Save-Handler, `buildWeatherPayload`,
`WeatherV2Reihenfolge`/`WeatherV2MailPreview`-Aufrufe im `route`-Zweig der
Komponente). Keine der neuen Funktionen wird von einer Stelle aus
aufgerufen, die auch vom `vergleich`-Zweig durchlaufen wird — Diff-Review
(AC-8) prüft das explizit, nicht nur über eine Konvention.

## Expected Behavior

- **Input:** Der Nutzer öffnet den Wetter-Metriken-Tab eines Trips, wechselt
  über den `LTChannelPicker` zwischen Email/Telegram/SMS und editiert
  innerhalb eines Reiters die Reihenfolge (Drag&Drop), den Roh/Einfach-Modus
  oder entfernt eine Metrik.
- **Output:** Ein reiner Kanal**wechsel** ändert nur die angezeigten Daten
  (zeigt entweder den eigenen Kanal-Eintrag oder — falls noch nie editiert —
  die globale Auswahl), macht den Tab NICHT dirty, löst KEINEN Auto-Save aus.
  Ein Kanal-**Edit** legt (beim ersten Mal, als Kopie der globalen Auswahl)
  einen eigenen `channelBuckets[kanal]`-Eintrag an, macht den Tab dirty, und
  der Auto-Save schreibt den vollständigen `channel_layouts`-Stand (alle
  bereits berührten Kanäle) nach `PUT /api/trips/{id}/weather-config`. Nach
  einem Reload zeigt jeder editierte Reiter weiterhin seine eigene Auswahl,
  unedierte Reiter weiterhin die globale.
- **Side effects:** Email- und Telegram-Trip-Renderer lesen die neue
  Kanal-Auswahl bereits über die bestehende Kaskade (`get_metrics_for_channel`)
  — keine weitere Backend-Änderung nötig. SMS-Trip-Renderer liest sie erst
  nach dem Fix aus Teil 1 korrekt. `context="vergleich"` ist vollständig
  unberührt — Compare zeigt weiterhin eine einzige globale Auswahl ohne
  Kanal-Persistenz (#1351 bleibt in Kraft).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit globaler Metrik-Auswahl (z. B. A, B, C) und noch
  keinem eigenen Kanal-Eintrag / When der Nutzer zwischen Email, Telegram und
  SMS wechselt, ohne etwas zu editieren / Then zeigen alle drei Reiter
  dieselbe (globale) Auswahl A, B, C, und der Tab bleibt nicht-dirty
  (`weather-metrics-dirty-pill` unsichtbar, kein Auto-Save-Request).
  - Test: Playwright wechselt die drei Kanäle nacheinander, prüft Vorschau-
    Inhalt und Netzwerk-Requests. (Fortführung der alten AC-6-Hälfte
    „reiner Kanalwechsel bleibt clean" aus `layout_tab_route.md`.)

- **AC-2 (Copy-on-write):** Given der SMS-Reiter zeigt noch die globale Auswahl
  A, B, C / When der Nutzer im SMS-Reiter Metrik C entfernt / Then entsteht ein
  eigener `channelBuckets.sms`-Eintrag mit Startpunkt A, B, C (Kopie der
  globalen Auswahl zum Edit-Zeitpunkt), nicht leer beginnend, und zeigt nach
  dem Edit A, B. Email/Telegram zeigen weiterhin unverändert die globale
  Auswahl A, B, C.
  - Test: Playwright entfernt eine Metrik im SMS-Reiter, wechselt zu
    Email/Telegram und prüft, dass dort die volle globale Auswahl weiterhin
    sichtbar ist.

- **AC-3 (Pflicht — Shallow-Merge-Datenverlust-Schutz):** Given der Trip hat
  bereits gespeicherte, unterschiedliche Kanal-Layouts unter
  `display_config.channel_layouts.email` und `.telegram` / When der Nutzer
  ausschließlich im SMS-Reiter editiert und speichert / Then bleiben die
  gespeicherten `email`- und `telegram`-Einträge nach dem `PUT` unverändert
  (per Folge-`GET` desselben Trips verifiziert) — kein lautloser Verlust
  analog BUG-DATALOSS-GR221.
  - Test: End-to-End über die echte Save-API (kein Mock): PUT SMS-Edit →
    GET Trip → assert `channel_layouts.email`/`.telegram` unverändert,
    `channel_layouts.sms` neu/geändert. Muster analog
    `rework_1351_compare_catalog.md` AC-6/AC-7.

- **AC-4:** Given eine Metrik-Reihenfolge A, B, C im Email-Reiter (bereits
  eigener Eintrag) / When im Telegram-Reiter die Reihenfolge auf C, A, B
  geändert und gespeichert wird / Then bleibt Email nach einem Reload A, B, C,
  Telegram zeigt C, A, B.
  - Test: Playwright Drag&Drop in beiden Reitern nacheinander, Reload,
    Reihenfolge je Kanal geprüft.

- **AC-5 (Roh/Einfach pro Kanal):** Given Metrik X ist im Email-Reiter auf
  "Einfach" gesetzt (eigener Eintrag) / When im SMS-Reiter Metrik X auf "Roh"
  umgeschaltet und beides gespeichert wird / Then bleibt der Email-Modus für X
  nach einem Reload "Einfach", der SMS-Modus "Roh".
  - Test: Playwright Modus-Toggle in beiden Reitern, Reload, Modus je Kanal
    geprüft.

- **AC-6 (SMS-Backend-Fix, RED vor Fix):** Given ein Trip mit Email-Auswahl
  {A, B, C} und SMS-eigener Auswahl {A} (`channel_layouts.sms` gesetzt) / When
  das SMS-Briefing gerendert wird (`trip_report.py` → `format_sms`) / Then
  enthält der SMS-Text ausschließlich die für A definierten SMS-Symbole, NICHT
  die zusätzlichen Symbole von B/C — vor dem Fix (Teil 1) enthält er
  fälschlich auch B/C, weil `active_metric_ids`/`_sms_thr` aus dem bereits
  Email-kollabierten `dc` gebildet werden.
  - Test: Kern-Suite, Modul-Test (nach Verhalten benannt, nicht nach
    Issue-Nummer) reproduziert den Bug rot vor Fix, grün danach — direkter
    Aufruf von `trip_report.py`s Render-Pfad mit präparierter
    `display_config`, Assertion auf den zusammengesetzten SMS-Text.

- **AC-7 (Telegram bereits verdrahtet, Regressionsbeweis):** Given eine
  Telegram-eigene Metrik-Auswahl, die von der Email-Auswahl abweicht / When
  das Telegram-Briefing gerendert wird (`narrow.py` → `render_for_channel`)
  / Then zeigt die Telegram-Bubble die Telegram-eigene Auswahl — ohne
  Code-Änderung an `narrow.py`, ausschließlich über den neuen Frontend-
  Schreibweg nachgewiesen.
  - Test: E2E-Mail-/Telegram-Nachweis über eine echt zugestellte Staging-
    Mail bzw. Telegram-Testnachricht (Pflicht laut Test-Nachweis-Abschnitt).

- **AC-8 (Compare strukturell unberührt):** Given der Compare-Editor
  (`context="vergleich"`) / When diese Scheibe abgeschlossen ist / Then ist
  keine Compare-eigene Datei verändert, und `weatherMetricsTabSharing.test.ts`
  belegt zusätzlich, dass die neuen State-Variablen (`channelBuckets`,
  `effectiveBuckets`) in keiner Funktion gelesen werden, die der
  `vergleich`-Zweig durchläuft.
  - Test: Diff-Review (nur gelistete Affected Files verändert) + erweiterter
    `weatherMetricsTabSharing.test.ts`-Fall.

- **AC-9 (globale Größen bleiben global):** Given Horizonte, SMS-Schwellwerte
  und Auswertungswahl (min/max) sind Trip-weit konfiguriert / When ein Kanal
  editiert und gespeichert wird / Then ändern sich diese drei Werte NICHT pro
  Kanal — sie bleiben eine einzige globale Konfiguration, unabhängig vom
  aktiven Reiter.
  - Test: Playwright ändert einen Horizont-Chip/SMS-Schwellwert im Email-
    Reiter, wechselt zu SMS, prüft denselben (nicht kanal-eigenen) Wert.

- **AC-10:** Given die bestehenden Testids und Regressions-Specs (`wm2-*`,
  `weather-metrics-*`, `sms-thresholds`, `layout-tab-route.spec.ts` außer der
  bewusst abgelösten Teil-AC, `epic-138-metriken-editor.spec.ts`,
  `epic-138-block-b.spec.ts`, `issue-736/723/619/343/690/1117/932`-Specs) /
  When die Seite gerendert bzw. die Specs ausgeführt werden / Then existieren
  die Testids unverändert und alle genannten Bestands-Specs bleiben grün.
  - Test: Playwright-Regressionslauf der genannten Specs.

- **AC-11 (Renderer-Mail-Gate #811 erfüllt):** Given `trip_report.py` wurde
  verändert (Teil 1) / When ein Commit die Datei staged / Then blockiert
  `renderer_mail_gate.py` erst nach erfolgreichem `briefing_mail_validator.py`-
  Lauf gegen eine echt zugestellte Staging-Mail (`X-GZ-Mail-Type: trip-briefing`).
  - Test: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` +
    `uv run python3 .claude/hooks/briefing_mail_validator.py` grün vor
    Commit.

## Known Limitations

- **KL-1 · Nur ~12 SMS-fähige Metriken:** eine Kanal-eigene SMS-Auswahl kann
  nur Metriken enthalten, die über `SMS_SYMBOL_BY_METRIC`/
  `SMS_MULTI_SYMBOLS_BY_METRIC` (`sms_trip.py`) überhaupt ein SMS-Symbol
  haben — andere Metriken in der SMS-Auswahl bleiben wirkungslos (kein
  Blocker, bestehende Einschränkung des SMS-Formats).
- **KL-2 · `per_report_layouts` (Morgen ≠ Abend) bleibt außerhalb:** diese
  Scheibe schreibt ausschließlich `per_channel_layouts` (`channel_layouts`
  auf der Wire); eine zusätzliche Report-Type-Differenzierung
  (`channel_layouts_per_report`) ist nicht Teil dieser Scheibe.
- **KL-3 · Kein Re-Sync bei globaler Änderung nach Copy-on-write:** ändert
  der Nutzer die globale Auswahl, NACHDEM ein Kanal bereits einen eigenen
  Eintrag hat, bleibt der Kanal-Eintrag unverändert (Kaskaden-Ebene 2
  gewinnt immer über Ebene 3, sobald gesetzt) — entspricht der bestehenden
  Backend-Kaskaden-Semantik, kein neues Verhalten dieser Scheibe.
- **KL-4 · Horizonte/SMS-Schwellwerte/Auswertungswahl bleiben global:**
  PO-Scope-Entscheidung 1 — nur Auswahl, Reihenfolge, Roh/Einfach-Modus sind
  pro Kanal. Eine künftige Erweiterung dieser drei Größen auf Kanal-Ebene
  wäre eine neue Spec.
- **KL-5 · LoC-Schätzung ~400–650 (Produktivcode + Tests):** über dem
  250-LoC-Standardlimit. `loc_limit_override` wird vor Phase 6 explizit
  beim PO eingeholt (`workflow.py set-field loc_limit_override <N>`), nicht
  eigenmächtig gesetzt.
- **KL-6 · Compare-Altlast (`compare_presets.json`/`.bak`) bleibt
  unberührt:** die einzigen bestehenden `channel_layouts`-Treffer in
  Produktionsdaten liegen in Compare-Presets (#1351-Ballast) — Migration/
  Bereinigung ist ausdrücklich NICHT Teil dieser (Trip-)Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein formaler `docs/adr/`-Eintrag), aber ausdrückliche
  Ablösung einer dokumentierten, testgesicherten Entscheidung:

**Ablösung von AC-6 aus `docs/specs/modules/layout_tab_route.md` (#1232
Scheibe 3b):** Jene Spec etabliert explizit "Der Kanal (`channel`) ist
reiner UI-View-State ohne Persistenz — er geht NIE in `snapshot()`/`isDirty`
ein" und sichert das per Playwright-AC-6 ab. Diese Garantie wird durch
diese Scheibe **bewusst aufgespalten, nicht ersetzt**:

1. **Bleibt bestehen (AC-1 dieser Spec):** ein reiner Kanal**wechsel** (Klick
   auf den `LTChannelPicker`, ohne inhaltlichen Edit) bleibt weiterhin ein
   reiner Ansichtswechsel — macht den Tab nicht dirty, löst keinen Auto-Save
   aus. Das ursprüngliche Invariant war korrekt für "Wechsel", nicht für
   "Edit".
2. **Neu (AC-2/AC-3/AC-4/AC-5 dieser Spec):** ein Kanal-**Edit** (Reihenfolge,
   Roh/Einfach, Entfernen innerhalb eines Reiters) macht den Tab dirty und
   der Auto-Save schreibt ausschließlich den aktiven Kanal in
   `channel_layouts[kanal]`, während zuvor gespeicherte andere Kanäle
   unverändert bleiben (Shallow-Merge-Schutz).

Diese Aufspaltung ist keine stille Verhaltensänderung, sondern eine
explizite Produktentscheidung dieser Scheibe (PO-go 2026-08-08): der
Kanal-Reiter bekommt zusätzlich zur reinen Vorschau-Funktion eine
Dateninhalt-Funktion. `layout_tab_route.md` bleibt als historisches Dokument
bestehen; sein AC-6 gilt ab dieser Scheibe nur noch für den
Kanal-**Wechsel**-Fall, nicht mehr für den Kanal-Inhalt insgesamt.

## Test-Nachweis

- **Kern:** neuer Modul-Test für den SMS-Backend-Fix (Teil 1), benannt nach
  Verhalten (z. B. `tests/unit/output/test_sms_channel_metric_selection.py`
  oder passende bestehende Modul-Suite), RED vor Fix, GREEN danach. Kein
  bestehender Test darf durch die Änderung rot werden (`touched_tests_gate.py`).
- **Frontend (node:test):** `weatherMetricsTabSharing.test.ts` erweitert um
  den Isolationsfall aus AC-8; ggf. neuer Test für die
  `channelBuckets`-Dirty-Normalisierung (Wiederverwendung/Adaption von
  `channelLayoutsDirty.ts`).
- **Staging-E2E (`/60-validate`):** Playwright gegen einen echten Trip (kein
  Mock) für AC-1 bis AC-5, AC-9, AC-10.
- **Mail-Validator (Pflicht vor "E2E bestanden", da `trip_report.py`
  verändert wird — Renderer-Commit-Gate #811 greift):**
  `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen eine echt
  zugestellte Staging-Mail (`X-GZ-Mail-Type: trip-briefing`), zusätzlich
  `uv run pytest tests/tdd/test_issue_811_mode_matrix.py`.
- **Telegram/SMS-Zustellnachweis (AC-6/AC-7):** echte Staging-Zustellung
  über die konfigurierten Test-Postfächer/Test-Bot (kein Mock, kein
  PO-Privatpostfach) — analog `docs/reference/mail_validators.md`.

## Changelog

- 2026-08-08: Initial spec created
