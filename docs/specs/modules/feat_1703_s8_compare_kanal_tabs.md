---
entity_id: feat_1703_s8_compare_kanal_tabs
type: feature
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [frontend, backend, compare, metrik-kaskade, adr-0050, adr-0053, issue-1703]
---

# #1703 Scheibe 8 — Compare-Kanal-Tabs für die Übersichtstabelle

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich bekommt für die **Übersichtstabelle** (`display_config.active_metrics`)
kanal-eigene Metrik-Auswahl, wie sie der Trip-Editor bereits für alle drei Kanäle führt. Löst
die Nutzer-Zusage ein: „Ich wähle im Ortsvergleich für die SMS andere Wettergrößen als für die
E-Mail — und es kommt auch so an." Das ist eine **Entscheidungs-Umkehr**: Compare hatte
kanalweise Auswahl bereits einmal (#442, 2026-05-29) und verlor sie 2026-07-18/24/29
(#1287/#1291/#1351) mit der Begründung „Attrappen" — die Oberfläche existierte, ohne dass die
Python-Seite je etwas anderes als eine flache Liste las. Diese Scheibe liefert deshalb die
**ganze Kette** (Oberfläche → Speicherweg → Resolver → Renderer), nicht nur die Oberfläche.

Stundenverlauf (`hourly_metrics`) und Ausblick (`outlook_metrics`) bleiben in dieser Scheibe
**bewusst global** — eigene, getrennt gespeicherte Auswahllisten, keine Kanal-Ebene. Das ist
eine Schnitt-Entscheidung (Analyse-Phase, PO-freigegeben 2026-08-13), keine Auslassung.

## Source

- **File:** `src/services/report_config_resolver.py`
- **Identifier:** `resolve_compare_render_options()` (Zeilen 212-286), `CompareRenderOptions`
  (Zeilen 160-193)
- **Zweite Kette:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, Zeilen
  1125-1286 (`{#if context === 'vergleich'}`-Zweig), speziell der `WeatherV2Reihenfolge`-Aufruf
  Zeilen 1218-1228 (die „Reihenfolge"-Card, Übersichtstabelle)
- **Schicht:** Python-Core (`src/services/`, `src/output/renderers/`) UND Frontend
  (`frontend/src/lib/components/shared/`, `frontend/src/lib/components/compare/`). Kein
  Go-Schema-Change (`internal/model/compare_preset.go:48`, `DisplayConfig map[string]interface{}`
  ist bereits ein untypisiertes Blob).

## Estimated Scope

- **LoC:** ~380–450 (PO-Freigabe auf 450 angehoben, Kontext-Dokument Punkt 8/Analyse F1)
- **Files:** ~16 (6 Backend/Frontend-Produktivdateien MODIFY, 1 Frontend-Datei CREATE, 1
  AST-Wächter MODIFY+RENAME, 4-5 Testdateien neu/erweitert, 1 ADR-Datei CREATE — Doku zählt
  laut LoC-Gate nicht mit)
- **Effort:** high (Datenmodell-Erweiterung + Persistenz-Kette + Editor-Umbau + ADR-Pflicht)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| ADR-0050 | Zusage | Regeln 1-4 (Maximum, nur Abwahl, sofortige Durchschreibung, „Aus ist ein Zustand") — Compare erbt sie unverändert |
| ADR-0049 | Zusage | Kanalliste; bestätigt hier: Compare-Briefing kennt nur E-Mail/Telegram/SMS, kein Premium-SMS (Kontext-Dokument Punkt 6) |
| `channelMetricLayouts.ts` (Trip) | Frontend | Vorbild; `splitChannelMetricsForDisplay()` wird direkt WIEDERVERWENDET (generisch über `string[]`, keine Buckets-Abhängigkeit) |
| `LayoutTab.svelte`/`LTChannelPicker.svelte`/`ltChannels.ts` | Frontend | geteilter Kanal-Tab-Organism, bekommt zwei Pflicht-Fixes (Abschnitt 7) |
| `compare_metric_ids.py::resolve_enabled_metrics()` | Backend | Übersetzung Alt-/Neuformat → Renderer-IDs, wird von der neuen kanalweisen Funktion wiederverwendet |
| `mergeConfigMap` (Go, `internal/handler/config_merge.go:11-22`) | Backend | löscht Keys nie, ersetzt `display_config`-Top-Level-Keys als GANZES — bestimmt die RMW-Pflicht beim Speichern |
| `docs/specs/modules/rework_1351_compare_catalog.md`, `compare_kanal_metriken.md` | Spec | die zwei abzulösenden Vorgänger-Entscheidungen |
| `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md` | Spec | Trip-Vorbild für Regel 4 (Editor-Umsetzung) |

## Scope

### Affected Files

| File | Change | Beschreibung |
|---|---|---|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | neue Funktion `resolve_channel_enabled_metrics()` neben `resolve_enabled_metrics()` |
| `src/services/report_config_resolver.py` | MODIFY | `CompareRenderOptions` bekommt additives Feld `enabled_metrics_by_channel`; `resolve_compare_render_options()` füllt es |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 3 Aufrufstellen (Z. 436, 497, 499) lesen kanalspezifisch statt `opts.enabled_metrics` |
| `src/services/compare_preview_service.py` | MODIFY | 4 Aufrufstellen (Z. 63, 66, 100, 115, 178) analog |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts` | CREATE | Compare-Pendant zu `channelMetricLayouts.ts` (Hydration + RMW-Merge fürs `{metric_id,aggregation}`-Format) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | neuer State `channelActiveMetricKeys` |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | `WeatherMetricsSnapshot` + Hydration + Diff-Guard erweitert |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY | `HubEdit` + `buildHubPutPayload` reichen das neue Feld durch |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits` + RMW-Bau von `display_config.channel_active_metrics` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Übersicht-Reihenfolge-Card bekommt `<LayoutTab context="vergleich">`-Wrapper mit Kanal-Handlern |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | MODIFY | `hasLabelColumn` Pflicht-Prop, `smsCharLimit` Prop, `channels`-Weiterreichung |
| `frontend/src/lib/components/shared/layout-tab/LTChannelPicker.svelte` | MODIFY | optionale `channels`-Prop statt fest verdrahteter `LT_CHANNELS`-Konstante |
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | MODIFY | neue Hilfsfunktion `ltChannelsFor(smsCharLimit)` |
| `frontend/src/lib/components/shared/__tests__/weather_metrics_tab_vergleich_reihenfolge_no_off_columns.test.ts` | RENAME+MODIFY | → `weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts`, Invariante gedreht (Abschnitt 7) |
| `docs/adr/0053-compare-kanal-eigene-metrikauswahl-uebersicht.md` | CREATE | löst #1287/#1291/#1351 ab (zählt nicht zum LoC-Limit) |
| `docs/adr/README.md` | MODIFY | Index-Eintrag ADR-0053 (Doku, zählt nicht) |

**Unverändert bleiben** (explizite Abgrenzung, Regressionsschutz): `CompareOutlookLayoutControls.svelte`,
`CompareHourlyLayoutControls.svelte`, deren AST-Wächter `compare_outlook_metric_selection_structure.test.ts`
und `compare_hourly_layout_controls_structure.test.ts`, sowie `LTComparePreview.svelte`/`LTCutLine.svelte`
(bleiben Totcode, kein Scheiben-Ziel).

## Implementation Details

### 1. Backend — kanalweise Auflösung (additiv, kein Feld-Umbau)

`resolve_enabled_metrics()` (`compare_metric_ids.py:144-197`) bleibt unverändert — sie löst EINE
gespeicherte Liste auf. Neu daneben: `resolve_channel_enabled_metrics()` wendet ADR-0050 Regel
1/2 als reine ID-Mengen-Operation auf zwei bereits aufgelöste Listen an:

```python
def resolve_channel_enabled_metrics(
    global_metrics: list[str] | None,
    channel_active_metrics: dict | None,
    channel: str,
) -> list[str] | None:
    if not channel_active_metrics or channel not in channel_active_metrics:
        return global_metrics  # kein Kanal-Eintrag -> folgt der Grundauswahl
    channel_resolved = resolve_enabled_metrics(channel_active_metrics.get(channel))
    if channel_resolved is None:
        return global_metrics  # defensiv: kein Fallback-Absturz bei Fremddaten
    if global_metrics is None:
        return channel_resolved  # kein Maximum definiert -> ADR-0050 D4-analog: nicht schneiden
    allowed = set(global_metrics)
    return [m for m in channel_resolved if m in allowed]  # Reihenfolge = Kanal-Liste
```

`global_metrics is None` bedeutet „Feld `active_metrics` fehlt komplett" (Altbestand/nie
konfiguriert, `resolve_enabled_metrics(None) == None`) — dieselbe Semantik wie Trips
`_clip_to_global_maximum()` bei leerem `self.metrics` (`models.py:913-914`, „kein Maximum
definiert → nicht schneiden"). `global_metrics == []` (bewusste Leerauswahl) IST ein Maximum
(die leere Menge) — jeder Kanal wird dann auf `[]` geschnitten, das ist ADR-0050 Regel 1
korrekt angewendet.

`resolve_compare_render_options()` (`report_config_resolver.py:212-286`) ruft die Funktion
dreimal auf und legt das Ergebnis **additiv** ab:

```python
active_metrics = display_config.get("active_metrics")
channel_raw = display_config.get("channel_active_metrics")
global_metrics = resolve_enabled_metrics(active_metrics)
enabled_metrics_by_channel = {
    ch: resolve_channel_enabled_metrics(global_metrics, channel_raw, ch)
    for ch in ("email", "telegram", "sms")
}
```

**Bewusst additiv, kein Feld-Umbau:** Das bestehende Feld `CompareRenderOptions.enabled_metrics`
bleibt unverändert (weiterhin die reine globale Auflösung) — nur `scheduler_dispatch_service.py`
und `compare_preview_service.py` (die einzigen zwei Leser, s. u.) wechseln auf das neue Feld
`enabled_metrics_by_channel: dict[str, list[str] | None]`. Grund: `enabled_metrics=` als
Keyword-Argument der Renderer-Funktionen (`render_compare_email/telegram/sms`) taucht in **33**
Testdateien auf — sie rufen die Renderer aber direkt mit einem eigenen Wert auf, nicht über den
Resolver, und sind damit unberührt. Nur `tests/tdd/test_compare_render_options_resolver.py`
prüft `CompareRenderOptions` selbst; dessen bestehende Assertions auf `.enabled_metrics` bleiben
gültig, weil sich dessen Bedeutung nicht ändert.

### 2. Aufrufstellen — pro Kanal statt einer gemeinsamen Liste

`scheduler_dispatch_service.py` (`send_one_compare_preset`, drei Aufrufe innerhalb von
`render_compare_email(...)`/`render_compare_telegram(...)`/`render_compare_sms(...)`,
Zeilen 432-499) und `compare_preview_service.py` (`_render_email`, `render_all_channels`,
`render_telegram_preview`, `render_sms_preview` — vier Stellen) ersetzen
`enabled_metrics=opts.enabled_metrics` durch
`enabled_metrics=opts.enabled_metrics_by_channel["email"|"telegram"|"sms"]` — je nachdem, welchen
Kanal der jeweilige Aufruf rendert. Die Renderer-Funktionssignaturen selbst
(`comparison.py:409/704/995`) ändern sich NICHT — sie erwarten weiterhin `list[str] | None`.

### 3. Persistenz-Format

Neues `display_config`-Feld `channel_active_metrics: {"email"?: [...], "telegram"?: [...],
"sms"?: [...]}` — jeder Wert im selben Format wie `active_metrics` (Alt-Zeichenkette ODER
`{metric_id, aggregation}`, gemischt erlaubt). **Bewusst keine `enabled`-Flags wie beim
Trip-`channel_layouts`** — anders als `WeatherConfigMetric` kennt Compares Format kein
`enabled`-Feld; ein Kanal-Eintrag listet nur die AKTIVEN Metriken dieses Kanals, exakt wie
`active_metrics` selbst. „Aus in diesem Kanal" ist damit reine Editor-Anzeige
(`splitChannelMetricsForDisplay`, Abschnitt 5), keine gespeicherte Flag-Information.

Persistenz-Semantik (deckungsgleich mit `active_metrics`, #1191/#1366):
- Kanal-Key fehlt im `channel_active_metrics`-Objekt → kein Override, Kanal folgt der
  Grundauswahl.
- Kanal-Key vorhanden, Liste leer (`[]`) → bewusste Leerauswahl für diesen Kanal.
- `channel_active_metrics` selbst fehlt komplett → Altbestand, alle drei Kanäle folgen der
  Grundauswahl (AC-S8-15).

Go-seitig kein Schema-Change: `mergeConfigMap` (`config_merge.go:11-22`) ersetzt jeden
Top-Level-Key von `display_config` — inklusive `channel_active_metrics` — als GANZES. Das
erzwingt dieselbe RMW-Pflicht wie beim Trip (`config_merge.go` löscht nie, ersetzt aber ganze
Werte): der Client MUSS beim Speichern alle bereits editierten Kanal-Einträge mitschicken, sonst
gehen nicht angefasste Kanäle verloren (Trip-Lehre #1575/#1719, hier neu zu vermeiden).

### 4. Neues Frontend-Modul `compareChannelMetricLayouts.ts`

`frontend/src/lib/components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts` (CREATE,
in `shared/**` — umgeht die Pendant-Sperre strukturell und ist der architektonisch richtige Ort).
State-Form: `Record<ChannelId, string[] | null>` — schlanker als Trips `ChannelOverride`
(`{buckets, friendlyMap}`), weil Compare pro Kanal nur EINE geordnete Auswahlliste braucht, keine
Buckets/Friendly-Map. `splitChannelMetricsForDisplay()` aus `channelMetricLayouts.ts` wird
**direkt importiert und wiederverwendet** (generisch über `string[]`, keine Änderung nötig).

Zwei neue Funktionen:

```ts
export function compareChannelActiveMetricsFromStored(
	stored: Record<string, StoredActiveMetric[]> | undefined,
	catalog: CompareSelectionEntry[]
): Record<ChannelId, string[] | null> {
	const result = { email: null, telegram: null, sms: null } as Record<ChannelId, string[] | null>;
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		if (stored?.[ch] !== undefined) result[ch] = normalizeStoredActiveMetrics(stored[ch], catalog) ?? [];
	}
	return result;
}
```

```ts
export function mergeAllCompareChannelActiveMetricsForSave(
	prevStored: Record<string, StoredActiveMetric[]> | undefined,
	channelOverrides: Record<ChannelId, string[] | null>,
	catalog: CompareSelectionEntry[]
): Record<ChannelId, StoredActiveMetric[]> {
	let next = { ...(prevStored ?? {}) } as Record<ChannelId, StoredActiveMetric[]>;
	for (const ch of ['email', 'telegram', 'sms'] as ChannelId[]) {
		const override = channelOverrides[ch];
		if (override === null) continue; // nie editiert -> Bestand aus prevStored erhalten
		next = { ...next, [ch]: toStoredActiveMetrics(override, catalog) };
	}
	return next;
}
```

`mergeAllCompareChannelActiveMetricsForSave` ist das Compare-Pendant zu
`mergeAllChannelLayoutsForSave` (`channelMetricLayouts.ts:117-129`) — serialisiert JEDEN
nicht-`null`-Eintrag, nicht nur den aktiven Kanal (Trip-Lehre #1719 S3, Abschnitt 3 dort).

### 5. State- und Save-Kette

- `CompareWizardState` (`compareWizardState.svelte.ts:31`, direkt neben `activeMetricKeys`):
  neuer State `channelActiveMetricKeys = $state<Record<ChannelId, string[] | null>>({email: null,
  telegram: null, sms: null})`.
- `WeatherMetricsSnapshot` (`weatherMetricsCompareSave.ts:71-79`) bekommt das Feld als
  **Erweiterung derselben Domäne** — kein dritter Commit-Wrapper (Kontext-Dokument F2). Der
  Diff-Guard `flushPendingWeatherMetricsSave` (Zeilen 88-115) nimmt es in `norm()` mit auf
  (JSON.stringify-Vergleich, analog `activeMetricKeys`) und reicht es an `buildHubPutPayload`
  weiter.
- `hydrateWeatherMetricsFromPreset` (`weatherMetricsCompareSave.ts:54-61`) bleibt für die
  Grundauswahl unverändert; eine neue Funktion `hydrateChannelActiveMetricsFromPreset(preset,
  catalog)` (selbe Datei) liest `preset.display_config.channel_active_metrics` über
  `compareChannelActiveMetricsFromStored()`. `CompareTabs.svelte::hydrateWetterMetrikenTab()`
  (Zeilen 721-742) ruft beide Funktionen auf und setzt `wizardState.channelActiveMetricKeys`
  zusätzlich zu `wizardState.activeMetricKeys`.
- `HubEdit` (`compareHubWizardBridge.ts:74-122`) und `CompareEditorEdits`
  (`compareEditorSave.ts:19-90`) bekommen je ein optionales Feld
  `channelActiveMetricKeys?: Record<ChannelId, string[] | null>` (`undefined` = nicht editiert,
  Round-Trip). `buildComparePresetSavePayload` (`compareEditorSave.ts:98-227`) baut daraus —
  analog zum bestehenden `active_metrics`-Block (Zeilen 120-130) — den Payload-Eintrag
  `displayConfig.channel_active_metrics = mergeAllCompareChannelActiveMetricsForSave(original
  .display_config?.channel_active_metrics, edits.channelActiveMetricKeys, catalog)`, nur wenn
  `edits.channelActiveMetricKeys !== undefined`.
- Rollback bei fehlgeschlagenem PUT (`CompareTabs.svelte::handleWetterMetrikenCommit`, Zeilen
  752-774): `wizardState.channelActiveMetricKeys = before.channelActiveMetricKeys` ergänzt die
  bestehenden drei Rollback-Zeilen.

### 6. Editor — Kanal-Tabs für die Übersicht

Die „Reihenfolge"-Card im vergleich-Zweig (`WeatherMetricsTab.svelte:1213-1229`) verliert ihren
bloßen `WeatherV2Reihenfolge`-Aufruf und bekommt denselben `<LayoutTab>`-Wrapper wie der
Trip-Kanal-Reiter (Vorbild Zeilen 1358-1381), mit vier Unterschieden zum Trip-Aufruf:
`context="vergleich"`, `hasLabelColumn={false}` (Metriken bleiben Zeilen, s. Abschnitt 7),
`smsCharLimit={SMS_COMPARE_CHAR_LIMIT}` (153, nicht 160), und `friendlyMap={{}}`/`onMode=
{noopMode}` (Compare kennt keine Roh-/Einfach-Umschaltung).

Neue Handler-Trias, analog `onCompareRemove`/`onCompareDndReorder` (Zeilen 1056-1067), aber
kanalbewusst und mit Copy-on-write (Vorbild `editActiveChannel`, Zeilen ~680-691):

- `onCompareChannelRemove(ch, id)` — abwählen im Kanal-Reiter. Ohne bestehenden Override:
  `startCompareChannelOverride(materializedActiveMetricKeys)` als Startpunkt (Klon der globalen
  Reihenfolge), danach die Metrik entfernen.
- `onCompareChannelDndReorder(ch, newOrder)` — Ziehen im Kanal-Reiter, analog.
- `onCompareChannelRestore(ch, id)` — Regel 4: fügt eine Metrik aus der „Aus"-Gruppe wieder in
  den aktiven Teil des Kanal-Overrides ein.

`toggleCompareMetric()` (Zeilen 1013-1016, die Grundauswahl-Checkbox) bekommt den ADR-0050-
Regel-3-Zusatz aus dem Trip-Vorbild (`onToggleMetric`, Zeilen 712-730): bei ABWAHL wird die
Metrik-ID aus jedem nicht-`null`-Eintrag von `wiz.channelActiveMetricKeys` entfernt (reiner
Array-Filter, kein `move()` nötig — Compare kennt keine Buckets). Bei EINWAHL bleiben
Kanal-Overrides unangetastet (Grundsatz „keine Bevormundung").

`colCount` des `LayoutTab`-Aufrufs = Länge der AKTIVEN Liste des gewählten Kanals
(`splitChannelMetricsForDisplay(materializedActiveMetricKeys, channelView).active.length`, exakt
wie Trips `activeChannelSections.active.length`, Zeile 1361).

### 7. Kappungs-Aussage-Fix (zwei Pflicht-Fixes am geteilten Organism)

**Fix A — `hasLabelColumn`:** `LayoutTab.svelte:59` setzt heute
`hasLabelColumn={context === 'vergleich'}`. Dieser Default war für den Hub-Reiter „Layout"
gebaut (Orte als Spalten) — der ist seit #1360 aufgelöst, `ltChannels.ts:64-68` bestätigt: es
gibt heute keinen lebenden `context="vergleich"`-Konsumenten. Für den einzig verbleibenden
Vergleichsfall — diese Scheibe, Metriken als Zeilen — ist der kontextabgeleitete Default
**falsch** und würde vom ersten Tag an eine falsche Kappungslinie zeigen (`ltCapNoteText()`,
`ltChannels.ts:138`: `hasLabelColumn ? "N Spalten (Label + Metriken)" : "N Metriken"`).
`hasLabelColumn` wird **Pflicht-Prop** ohne Default; der neue Compare-Aufruf übergibt `false`.

⚠️ **Folge, die nicht übersehen werden darf:** Wird die Prop zur Pflicht, muss auch die
**bestehende Trip-Aufrufstelle** (`WeatherMetricsTab.svelte:1358-1381`) sie explizit übergeben —
dort ebenfalls `hasLabelColumn={false}` (Trip zählt schon heute reine Metrik-Spalten, der
bisherige Default lieferte für `context="route"` genau `false`). Ohne diese Anpassung schlägt
`svelte-check` fehl; das Verhalten des Trips ändert sich dadurch **nicht** (gleicher Wert, nur
nicht mehr abgeleitet). Ein AC braucht es dafür nicht — `svelte-check` ist Teil der CI-Ampel und
fängt das Versäumnis sofort.

**Fix B — SMS-Zeichengrenze am Kanal-Tab-Badge:** `LayoutTab.svelte:49` reicht
`smsCharLimit` bereits an `ltOverflowAcrossChannels()` durch (→ `LTCapNote` zeigt korrekt 153).
**Der Kanal-Tab-Picker selbst tut das nicht:** `LTChannelPicker.svelte:29,39` iteriert die
Modul-Konstante `LT_CHANNELS` (`ltChannels.ts:71-75`), fest berechnet mit
`SMS_TRIP_CHAR_LIMIT` (160) — der SMS-Badge im Kanal-Tab zeigt für Compare also weiterhin „160",
während der Hinweistext darunter korrekt „153" sagt. Das ist ein über die explizite
Aufgabenstellung hinaus **beim Code-Lesen gefundener, notwendiger** Fix: ohne ihn widerspricht
sich die Kappungs-Aussage auf derselben Seite selbst.

Fix: neue Funktion `ltChannelsFor(smsCharLimit: number): LtChannel[]` in `ltChannels.ts`
(baut dieselbe Liste wie `LT_CHANNELS`, aber mit `ltLimitForChannel(id, smsCharLimit)` statt der
fest verdrahteten Konstante — `LT_CHANNELS` selbst bleibt als Default für Route bestehen).
`LTChannelPicker` bekommt eine optionale Prop `channels: LtChannel[] = LT_CHANNELS` und iteriert
diese statt der importierten Konstante direkt. `LayoutTab.svelte` reicht
`channels={ltChannelsFor(smsCharLimit)}` durch. Zusammen ≤15 Zeilen an drei Dateien.

## Expected Behavior

- **Input:** Nutzer bedient den Reiter „Wetter-Metriken" eines Ortsvergleichs — Grundauswahl
  (Checkbox-Liste, unverändert) und darunter neu: Kanal-Reiter E-Mail/Telegram/SMS mit je
  eigener Reihenfolge/Auswahl für die Übersichtstabelle.
- **Output:** Die zugestellte Compare-E-Mail, -Telegram-Nachricht und -SMS zeigen je Kanal die
  dort eingestellte Metrik-Auswahl in der Übersichtstabelle; Kappungs-Hinweise nennen die
  gemessenen Grenzen des Vergleichspfads (E-Mail unbegrenzt, Telegram 7, SMS 153 Zeichen).
  Ausblick und Stundenverlauf zeigen unverändert eine einzige globale Auswahl.
- **Side effects:** Ein Speichern schreibt ab jetzt alle im aktuellen Editier-Vorgang
  angefassten Kanal-Ebenen der Übersicht, nicht nur den zuletzt sichtbaren Reiter. Presets ohne
  `channel_active_metrics` verhalten sich unverändert (alle Kanäle folgen der Grundauswahl).

## Acceptance Criteria

### Block A — Die Kaskade gilt jetzt auch für Compare (ADR-0050 Regeln 1-4)

- **AC-S8-1:** Given eine Metrik Y ist in der Grundauswahl der Übersicht abgewählt / When der
  Nutzer einen beliebigen Kanal-Reiter (E-Mail/Telegram/SMS) öffnet / Then erscheint Y weder
  aktiv noch in der Aus-Gruppe — kein Kanal kann sie zurückholen.
  - Test: Unit-Test auf `resolve_channel_enabled_metrics()` (Y in `channel_active_metrics.sms`
    mit `enabled`-artigem Eintrag, aber Y fehlt in `active_metrics`) + Playwright-Klickpfad.

- **AC-S8-2:** Given der SMS-Reiter zeigt einen eigenen Override, der eine Metrik enthält, die
  NICHT in der Grundauswahl steht (z. B. Alt-Daten oder manipulierter Payload) / When die
  Übersicht gerendert wird / Then fehlt diese Metrik im gerenderten SMS-Text.
  - Test: Unit-Test auf `resolve_channel_enabled_metrics()` mit inkonsistenten Eingabedaten.

- **AC-S8-3:** Given der SMS-Reiter hat einen eigenen Override mit Metrik Z aktiv / When der
  Nutzer Z in der Grundauswahl abwählt, OHNE zu speichern / Then zeigt der SMS-Reiter Z sofort
  nicht mehr als aktiv (reine Anzeige-Zusicherung, kein PUT nötig).
  - Test: Playwright-Klickpfad ohne Reload.

- **AC-S8-4:** Given denselben Ablauf wie AC-S8-3, aber der Nutzer steht beim Abwählen im
  E-Mail-Reiter / When er speichert und die Seite neu lädt / Then ist Z auch im SMS-Reiter
  dauerhaft abgewählt, UND die als Nächstes zugestellte SMS enthält Z nicht.
  - Test: **Playwright-Klickpfad gegen Staging** + Abruf/Prüfung der tatsächlich zugestellten
    Compare-SMS (nicht nur des PUT-Bodys — Persistenz-Nachweis).

- **AC-S8-5:** Given Metrik W ist im SMS-Reiter der Übersicht bewusst abgewählt / When der
  Nutzer sie in der Gruppe „Aus in diesem Kanal" wieder einschaltet / Then erscheint W wieder
  in der aktiven, sortierbaren Liste des SMS-Reiters — sie war nie physisch entfernt.
  - Test: Playwright-Klickpfad.

- **AC-S8-6:** Given W wurde nach AC-S8-5 wieder eingeschaltet und gespeichert / When die Seite
  neu geladen wird / Then bleibt W im SMS-Reiter aktiv, UND die nächste zugestellte SMS zeigt W.
  - Test: Playwright-Klickpfad gegen Staging + zugestellte SMS.

### Block B — Die Nutzer-Zusage: unterschiedliche Metriken, wirklich zugestellt

- **AC-S8-7:** Given ein Ortsvergleich mit unterschiedlicher Metrik-Auswahl in E-Mail- und
  SMS-Reiter der Übersicht / When das Preset versendet wird / Then zeigt die zugestellte
  Compare-E-Mail (Übersichtstabelle) eine andere Metrik-Menge als die zugestellte SMS-Zeile
  derselben Sendung.
  - Test: Staging-Versand, `email_spec_validator.py` (Header `X-GZ-Mail-Type: compare`) für die
    E-Mail-Seite, Inhaltsvergleich mit der zugestellten SMS.

- **AC-S8-8:** Given denselben Ablauf wie AC-S8-7, aber verglichen werden Telegram und SMS /
  When versendet wird / Then unterscheiden sich die gezeigten Metriken entsprechend der
  Kanal-Auswahl.
  - Test: Staging-Versand, Inhaltsvergleich der zugestellten Telegram- und SMS-Nachricht.

### Block C — Persistenz ohne Datenverlust

- **AC-S8-9:** Given der Telegram-Reiter (A) ist sichtbar, der Nutzer ändert dort nichts,
  wechselt zum SMS-Reiter (B) und ändert dort die Auswahl / When die Änderung committet /
  Then löst das genau EINEN PUT aus, dessen Body Kanal Bs Änderung trägt.
  - Test: Playwright-Klickpfad mit Netzwerk-Request-Zählung (Vorbild F003-Fix,
    `CompareTabs.svelte:1342-1360`).

- **AC-S8-10:** Given der Nutzer editiert nacheinander E-Mail-, Telegram- und SMS-Reiter der
  Übersicht (drei unterschiedliche Auswahllisten), ohne zwischendurch zu speichern / When
  einmal gespeichert wird / Then trägt der PUT-Body alle drei Kanal-Listen, nicht nur die
  zuletzt aktive.
  - Test: TS-Unit-Test auf `mergeAllCompareChannelActiveMetricsForSave()` + Playwright-Klickpfad.

- **AC-S8-11:** Given der Nutzer wählt im SMS-Reiter alle Metriken ab (bewusste Leerauswahl) /
  When gespeichert und die Seite neu geladen wird / Then bleibt der SMS-Reiter leer — kein
  Rückfall auf die globale Liste.
  - Test: **Rundlauf-Test** (Playwright gegen Staging: speichern → neu laden → Renderer-Ausgabe
    prüfen) — ein reiner PUT-Body-Unit-Test beweist das Serververhalten NICHT
    (`config_merge.go` löscht Keys nie, aber ersetzt Werte; nur ein echter Go-Merge-Durchlauf
    zeigt, ob `[]` ankommt statt eines weggelassenen Keys).

### Block D — Die Kappungs-Aussage stimmt

- **AC-S8-12:** Given der SMS-Reiter der Übersicht im Ortsvergleich / When der Nutzer ihn
  öffnet / Then zeigen sowohl der Kanal-Tab-Badge (`LTChannelPicker`) als auch der
  Kappungs-Hinweis (`LTCapNote`) 153 Zeichen — nicht 160, keine Spaltengrenze.
  - Test: Playwright-Klickpfad (beide Textstellen ablesen) + TS-Unit-Test auf `ltChannelsFor()`.

- **AC-S8-13:** Given der Telegram-Reiter der Übersicht mit mehr als 7 aktiven Metriken / When
  der Nutzer ihn öffnet / Then sitzt die Kapplinie nach der siebten Zeile, und die
  Kappungs-Zählung zählt reine Metrik-Zeilen (keine Label-Spalte, `hasLabelColumn=false`).
  - Test: Playwright-Klickpfad (Position der Kapplinie ablesen) + Unit-Test auf `ltCapNoteText()`
    mit `hasLabelColumn: false`.

### Block E — Abgrenzung und Rückwärtskompatibilität

- **AC-S8-14:** Given die Ausblick- und Stundenverlauf-Auswahl desselben Ortsvergleichs / When
  der Nutzer sie öffnet / Then bleiben beide unverändert je eine einzige globale Liste ohne
  Kanal-Reiter — keine Aus-Gruppe, kein `offColumns`/`onRestore` an ihren
  `WeatherV2Reihenfolge`-Aufrufen.
  - Test: **AST-Wächter** `compare_outlook_metric_selection_structure.test.ts` und
    `compare_hourly_layout_controls_structure.test.ts` bleiben UNVERÄNDERT grün (Abschnitt
    „Mutations-Gegenproben" M9).

- **AC-S8-15:** Given ein Compare-Preset ohne `channel_active_metrics`-Feld (Altbestand, jedes
  heute gespeicherte Preset) / When irgendein Kanal gerendert wird / Then gilt für alle drei
  Kanäle unverändert die globale `active_metrics`-Liste — keine Migration nötig, kein Fehler,
  kein Verhaltensunterschied zu heute.
  - Test: Unit-Test auf `resolve_channel_enabled_metrics(global, None, "sms")` sowie
    `resolve_channel_enabled_metrics(global, {}, "sms")`.

## Mutations-Gegenproben (PFLICHT)

| # | Verfälschung | MUSS rot werden |
|---|---|---|
| M1 | `resolve_channel_enabled_metrics()`: den Schnitt gegen `global_metrics` (Zeile `allowed = set(...)`) entfernen, Kanal-Liste ungeschnitten zurückgeben | **AC-S8-1**, AC-S8-2 |
| M2 | `scheduler_dispatch_service.py`: alle drei `render_compare_*`-Aufrufe wieder mit derselben Liste (`opts.enabled_metrics` statt `opts.enabled_metrics_by_channel[...]`) füttern | **AC-S8-7**, AC-S8-8 |
| M3 | `toggleCompareMetric()`: die ADR-0050-Regel-3-Durchschreibung in `channelActiveMetricKeys` bei Abwahl entfernen | **AC-S8-4** — *nicht* AC-S8-3 (dieselbe Lehre wie #1719 S3 M2: die Anzeige bleibt korrekt, weil `splitChannelMetricsForDisplay` immer gegen die aktuelle Grundauswahl filtert; nur der GESPEICHERTE Stand verrät das Fehlen der Durchschreibung) |
| M4 | `mergeAllCompareChannelActiveMetricsForSave()`: nur den zuletzt aktiven Kanal statt aller `!== null`-Einträge serialisieren | **AC-S8-10** |
| M5 | `buildComparePresetSavePayload`: eine leere Kanal-Auswahl als weggelassenen Key statt `[]` senden | **AC-S8-11** |
| M6 | `LayoutTab.svelte`: `hasLabelColumn` für den neuen Compare-Aufruf bleibt bei `context === 'vergleich'`-Default (`true`) statt explizit `false` | **AC-S8-13** |
| M7 | `LTChannelPicker`: `channels`-Prop ignorieren, weiterhin `LT_CHANNELS` (160) direkt importieren | **AC-S8-12** |
| M8 | `resolve_channel_enabled_metrics()`: bei fehlendem `channel_active_metrics` `[]` statt `global_metrics` zurückgeben | **AC-S8-15** |
| M9 | Den AST-Wächter der Übersicht (Abschnitt 7) ersatzlos löschen statt umzuschreiben | ohne ihn bliebe eine versehentliche `offColumns`/`onRestore`-Durchreichung an Ausblick/Stundenverlauf (AC-S8-14) unentdeckt — kein AC wird direkt rot, aber die Schutzwirkung von AC-S8-14 entfällt; deshalb Pflicht-Nachweis über den Wächter selbst, nicht über einen weiteren AC |

Wird eine Verfälschung von KEINEM Test gefangen, ist das ein Befund — kein Grund, den Test
nachträglich passend zu machen.

## Known Limitations

- **Ausblick und Stundenverlauf bleiben global** — bewusster Scheiben-Schnitt (Analyse F1), keine
  Auslassung. Eine Folge-Scheibe müsste dieselbe Kette (Resolver, Persistenz, Editor) für
  `outlook_metrics`/`hourly_metrics` wiederholen; Scheibe 7 (Reihenfolge-Wächter Compare-Seite)
  bleibt bis dahin auf die Übersicht beschränkt.
- **Reversibilität hat keine Positions-Erinnerung** — wie beim Trip (#1719 S3) landet eine
  wieder eingeschaltete Kanal-Metrik am Ende der Liste, nicht an ihrer früheren Position. Das
  Compare-Format speichert nur die aktive Reihenfolge, keine Position für inaktive Einträge.
- **Kein SMS-Überlauf-Hinweis über die Zeichengrenze hinaus** — wie beim Trip zeigt der Editor
  nur die Zeichengrenze (153), keine geschätzte „passt/passt nicht"-Aussage; die Kürzung
  arbeitet zeichenweise auf der fertig gebauten SMS-Zeile, die der Editor nicht kennt.
- **`LTComparePreview.svelte`/`LTCutLine.svelte` bleiben Totcode** — nicht Teil dieser Scheibe,
  weiterhin ohne Importeur.
- **Premium-SMS bleibt außen vor** — Compare-Briefing kennt strukturell nur drei Kanäle
  (`send_compare_report`, `notification_service.py:997/1016/1034`); Premium-SMS ist im
  Ortsvergleich ausschließlich Alarm-Kanal (#1745), diese Scheibe ändert daran nichts.
- **Der Rundlauf-Nachweis für AC-S8-11 braucht eine echte Go-Instanz (Staging)** — ein reiner
  Frontend-Unit-Test auf den PUT-Body kann `config_merge.go`s Verhalten nicht beweisen.
- **Attrappen-Risiko bleibt ein Prozessrisiko, kein technisches Limit dieser Spec** — wird der
  Nachweis (Block B) nicht tatsächlich gegen die zugestellte Ausgabe geführt, sondern nur gegen
  den PUT-Body, entsteht exakt die Wirkungslosigkeit, die #1287/#1291 bereits einmal zum
  Rückbau geführt hat.
- **`LTChannelPicker`-Badge-Fix (Abschnitt 7, Fix B) ist ein beim Code-Lesen gefundener
  Zusatzfund**, nicht Teil der ursprünglichen Aufgabenstellung — ohne ihn wäre die
  Kappungs-Aussage auf derselben Seite widersprüchlich (Badge 160 vs. Hinweistext 153).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0053 (neu, nächste freie Nummer nach ADR-0052; löst ADR-Bezug in
  `docs/specs/modules/rework_1351_compare_catalog.md` sowie die Entscheidungen aus #1287/#1291
  ab — Status dort wird auf „Abgelöst durch ADR-0053" gesetzt, sofern diese Specs ein
  ADR-Feld führen; andernfalls referenziert ADR-0053 sie im Fließtext)
- **Rationale:** Diese Scheibe macht eine bereits einmal getroffene, dokumentierte Entscheidung
  („Compare bekommt KEINE kanalweise Metrikauswahl — Attrappen-Risiko", 2026-07-18/24/29) still
  rückgängig. CLAUDE.md verlangt dafür zwingend ein neues ADR mit Status „Abgelöst durch". Das
  ADR MUSS festhalten:
  1. Den PO-Entscheid vom 2026-08-10 (#1514) als Auslöser, mit Verweis auf die vorherige
     Abschaffung und deren Begründung (Attrappen — Oberfläche ohne Wirkung).
  2. Die entscheidende Bedingung, die den Rückbau diesmal verhindert: die **ganze Kette**
     (Oberfläche → Speicherweg → Resolver → Renderer) liefert diese Scheibe zusammen, nicht nur
     die Oberfläche — der Nachweis hängt an der zugestellten Ausgabe (Block B dieser Spec).
  3. Den bewussten Scope-Schnitt: NUR die Übersichtstabelle (`active_metrics`); Ausblick und
     Stundenverlauf bleiben ausdrücklich global (kein Widerspruch zur Kaskaden-Zusage aus
     ADR-0050, weil diese sich auf Kanäle bezieht, nicht auf Ausgabeflächen).
  4. Die Übernahme von ADR-0050 Regeln 1-4 unverändert für Compare (keine eigene Kaskaden-Regel
     nötig — ADR-0053 zitiert ADR-0050, statt sie zu duplizieren).
  5. Verworfene Alternative: „nur die Technik liefern, Oberfläche folgt später" (Analyse F1) —
     verworfen, weil sie keine Nutzer-Zusage einlöst und das mahnende Gegenbeispiel
     `LTComparePreview.svelte` (300 Zeilen ohne Importeur seit #1719 S3) im selben Verzeichnis
     liegt.

## Testauflage

**Kern (deterministisch, offline, Commit-Gate):**
- `resolve_channel_enabled_metrics()` — neue Datei `tests/unit/test_compare_channel_metric_cascade.py`
  (Regeln 1-4, Altbestand-Fallback, defensive Fälle).
- `CompareRenderOptions.enabled_metrics_by_channel` — Erweiterung von
  `tests/tdd/test_compare_render_options_resolver.py`.
- `compareChannelMetricLayouts.ts` (Hydration, RMW-Merge) — neue Datei
  `frontend/src/lib/components/shared/__tests__/compareChannelMetricLayouts.test.ts`, Vorbild
  `channelMetricLayouts.test.ts`/`channelPayloadAllChannels.test.ts`.
- `ltChannelsFor()`/`LTChannelPicker`-`channels`-Prop — Erweiterung von
  `frontend/src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts`.
- Der umgeschriebene AST-Wächter (Abschnitt 7) sowie die beiden unveränderten Geschwister-Wächter.

**Live/Staging (Pflicht vor „E2E bestanden"):**
- Mindestens EIN Test misst die tatsächlich **zugestellte** Compare-Mail über
  `.claude/hooks/email_spec_validator.py` (Header `X-GZ-Mail-Type: compare`) — AC-S8-7.
- Klickpfad-Bündel (Vorbild #1719 S3, je `*.staging.spec.ts` + `*.staging.setup.ts`):

  | Bündel | ACs |
  |---|---|
  | `compare-uebersicht-kanal-tabs-sichtbar` | AC-S8-1, AC-S8-3, AC-S8-5, AC-S8-9 |
  | `compare-uebersicht-persistiert-je-kanal` | AC-S8-4, AC-S8-6, AC-S8-10, AC-S8-11 |
  | `compare-uebersicht-kappungsaussage` | AC-S8-12, AC-S8-13 |
  | `compare-uebersicht-zugestellte-ausgabe` | AC-S8-7, AC-S8-8 (kombiniert mit
    `email_spec_validator.py`-Lauf + zugestellter SMS/Telegram-Prüfung) |

- **Playwright-Regel (verbindlich, #1423-Lehre):** jeder Klickpfad wartet das Laden ab und nutzt
  `waitFor({state: 'attached'})` statt `count() === 0 → weiter` — Letzteres hat in #1423 einen
  Testfehler wie einen Produktfehler aussehen lassen, weil der Ausblick-Block während des
  Katalog-Ladens bewusst aus dem DOM entfernt ist (`WeatherMetricsTab.svelte:1142-1145`).

## Changelog

- 2026-08-13: Initial spec created (Scheibe 8 von #1703)
