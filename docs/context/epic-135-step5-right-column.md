---
entity_id: epic_135_step5_right_column
type: context
created: 2026-05-13
issues: [158, 159]
related: [epic_135_step4_left_column, epic_135_step3_trip_hero]
---

# Context: Epic #135 Step 5 — Rechte Spalte (Briefings + Wetter-Metriken + Alerts + Vorschau)

## Request Summary

Füllt den bisher leeren `<aside data-testid="trip-overview-right-column">` aus Step 4 mit vier read-only Karten:
- **Briefing-Card** (aus #159): Morning-/Evening-Briefing-Zeit + Alert-Toggle, „Bearbeiten →" zum #briefings-Tab
- **Wetter-Metriken-Card** (#158): aktive Metriken als Tag-Chips + Preset-Name, „Bearbeiten →" zum #weather-Tab
- **Alert-Card** (aus #159): Liste konfigurierter Alerts, „Bearbeiten →" zum #alerts-Tab
- **Vorschau-Card** (aus #159): CTAs „Email-Vorschau" / „SMS-Vorschau", öffnen #preview-Tab

Alle Karten sind **lesend** und verlinken zum jeweiligen Tab. Tab-Inhalte selbst sind out of scope (Placeholders aus TripTabs).

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` Z. 48–50 | Hier hängt die rechte Spalte als `<aside>` — Einbettungspunkt für 4 neue Cards |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | 6 Tabs mit Hash-Navigation (`overview`, `stages`, `weather`, `briefings`, `alerts`, `preview`); Tabs außer Overview sind aktuell Placeholders |
| `frontend/src/lib/types.ts` | `Trip.report_config: Record<string, unknown>` (generisch), `weather_config`, `aggregation` — **fehlt:** strukturiertes Typing |
| `internal/model/trip.go` | Go `Trip.ReportConfig`, `WeatherConfig` als `map[string]interface{}` — **fehlt:** `AlertRules`-Feld |
| `frontend/src/lib/utils/tripHero.ts::getNextBriefing` | bereits genutzt in Step 3 — wir können das Briefing-Format und die Eyebrow-Pattern wiederverwenden |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` (`BriefingConfig`, `defaultBriefingConfig`) | Strukturiertes Briefing-Interface — gute Vorlage für strukturiertes `report_config`-Typing (D5) |
| `frontend/src/routes/_cockpit/BriefingsTimeline.svelte` | Vorbild für Briefing-Card-Layout: GCard + Eyebrow + Zeit-Liste mit Dot-Status |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | Vorbild für Card-Komposition: GCard + Eyebrow + H2 + Stat-Strips + Link unten |
| `frontend/src/routes/_cockpit/AlertFeed.svelte` | Cockpit-Alert-Card (Placeholder) — visuelles Vorbild |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | Card-Container; akzeptiert `class`-Prop |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Eyebrow-Label-Komponente |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill mit `tone='accent'|'default'|...` — passt für Tag-Chips der Wetter-Metriken-Card |
| `frontend/src/app.css` | Tokens `--g-accent`, semantische Farben (success/warning/danger), Surface-Stufen |
| `frontend/e2e/global.setup.ts` Z. 14–52 | `e2e-cockpit-test` hat **kein** `report_config` und keine Alert-Konfiguration — Test-Trip muss erweitert werden |
| `internal/model/segment.go` Z. 4–28 | 18 mögliche Wetter-Metriken (TempMin/Max, WindMax, GustMax, Cloud, Humidity, Thunder, ... — das sind die Tag-Chip-Kandidaten) |

## Existing Patterns

- **Card-Standardlayout:** `<GCard class="...">` mit `<Eyebrow>Label</Eyebrow>`, `<h3>Titel</h3>`, Inhalt, optional unten ein Link `Bearbeiten →` (Anker zu `#tab-name` im selben Route).
- **Hash-basierte Tab-Navigation:** Klick auf `<a href="#briefings">` setzt den Tab-State in `TripTabs` (existierende Logik). Kein Routing-Refactor nötig.
- **Briefing-Zeit-Anzeige:** Format aus `tripHero.ts::getNextBriefing` (`heute, HH:MM` / `morgen, HH:MM`). Für die Briefing-Card reichen die Raw-Zeiten aus `report_config.morning_time` / `evening_time`.
- **Wizard-BriefingConfig** als Vorbild für strukturiertes Typing — aber wir bleiben für Step 5 beim generischen Lesen aus `report_config`.

## Dependencies

**Upstream (was wir nutzen):**
- `Trip.report_config` (lesend), `Trip.weather_config` (lesend), `Trip.aggregation` (lesend)
- `GCard`, `Eyebrow`, `Pill` aus `lib/components/ui/`
- Tab-Hash-Navigation aus `TripTabs.svelte`

**Downstream (was uns nutzt):**
- Nichts — wir sind Endpunkte im Overview-Panel.

## Existing Specs

- `docs/specs/modules/epic_135_step4_left_column.md` — Step 4 (linke Spalte), bleibt unverändert
- `docs/specs/modules/epic_135_step3_trip_hero.md` — Step 3 (Hero), unverändert
- `docs/specs/modules/trip_alert.md` — Backend-Alert-Service (Trip-Alert v1.0)
- `docs/specs/bugfix/alert_config_gaps.md` — Alert-Subject + `alert_on_changes`-Flag im `report_config`

## Lücken im Datenmodell (Folge-Issues anlegen)

| Lücke | Konsequenz für Step 5 | Folge-Issue |
|---|---|---|
| `Trip.alert_rules` fehlt komplett (Frontend + Backend) | Alert-Card kann konkrete Alerts nicht listen — zeigt nur Skeleton + Anker | [#205](https://github.com/henemm/gregor_zwanzig/issues/205) |
| `weather_config.preset_name` fehlt | Wetter-Metriken-Card zeigt aktive Metriken-Chips, aber kein Preset-Label | [#206](https://github.com/henemm/gregor_zwanzig/issues/206) |
| `report_config` ist `Record<string, unknown>` (Frontend) | Card greift dynamisch zu (`config.morning_time as string`); strukturiertes Typing wäre sauberer | [#207](https://github.com/henemm/gregor_zwanzig/issues/207) |
| Briefings-Tab-Inhalt fehlt (Placeholder) | „Bearbeiten →"-Link führt zu Placeholder — funktional sichtbar, aber editierbar erst nach diesem Tab | siehe Folge-Issue |
| Wetter-Metriken-Tab-Inhalt fehlt | wie oben | siehe Folge-Issue |
| Alerts-Tab-Inhalt fehlt | wie oben | siehe Folge-Issue |
| Vorschau-Tab-Inhalt (Issue #189 offen) | „Email-Vorschau" / „SMS-Vorschau" CTAs öffnen Tab mit Placeholder | #189 |
| `e2e-cockpit-test` ohne `report_config` | Test-Trip muss um `report_config` und ggf. `alert_rules`-Mock erweitert werden | im Scope |

## Risks & Considerations

1. **„Bearbeiten →"-Links führen zu Placeholders** — funktional korrekt (Tab wechselt, Hash setzt), aber der User landet auf einer leeren Seite. Das ist transparente Folge-Arbeit, kein Bug. Wir dokumentieren es in Known Limitations.

2. **Test-Trip-Erweiterung** — `e2e-cockpit-test` braucht `report_config = { enabled: true, morning_time: '06:00', evening_time: '18:00', alert_on_changes: true }` für aussagekräftige Card-Assertions. Wir editieren `global.setup.ts` minimal.

3. **Alert-Card ohne Datenfelder** — Wir können entweder einen Skeleton („Keine Alerts konfiguriert") rendern oder die Card weglassen. **Empfehlung: Skeleton anzeigen**, sonst klafft visuell eine Lücke und die spätere Aktivierung wäre ein UI-Sprung.

4. **Preset-Name-Heuristik** — Solange `weather_config.preset_name` fehlt, leiten wir das Label aus `trip.aggregation.activity_profile` ab (`wintersport` → „Wintersport-Standard", `wandern` → „Wandern-Standard", `allgemein` → „Standard-Metriken"). Provisional, in Known Limitations vermerkt.

5. **LoC-Schätzung:** 4 neue Card-Komponenten (~80 LoC je) + Wrapper-Edit in `TripOverview.svelte` + ggf. Utility (`reportConfigView.ts`) für die Briefing-Card-Anzeige. Unit-Tests (~80 LoC) + E2E (~100 LoC). Plus minimaler `global.setup.ts`-Edit. → **~600 LoC**, Override 650.

## PO-Entscheidungen (2026-05-13)

| # | Frage | Entscheidung |
|---|---|---|
| D1 | Alert-Card trotz fehlendem Datenmodell? | **(a) Skeleton + „Bearbeiten →".** Folge-Issue #205 trackt das Datenmodell. |
| D2 | Wetter-Metriken-Preset-Name? | **(a) Aus `activity_profile` ableiten** (Wintersport/Wandern/Allgemein → Standard-Label). Folge-Issue #206 für echtes Preset-Feld. |
| D3 | „Bearbeiten →"-Links | **(a) Tab-Wechsel** (`href="#briefings"` etc.), konsistent mit TripTabs. |
| D4 | Briefing-Card lesend oder editierbar? | **(a) Lesend.** Editieren ist Tab-Inhalt. |
| D5 | `report_config` strukturiert typen? | **(a) Generisch lassen.** Folge-Issue #207. |
| D6 | Vorschau-CTAs | **(a) Tab-Wechsel zu `#preview`** — Tab-Inhalt ist Issue #189. |

## Phase 2 — Analyse

### Komponenten-Layout

`TripOverview.svelte` rendert in der rechten Spalte ein neues `RightColumn`-Wrapper-Komponentchen oder direkt 4 Card-Komponenten. Empfehlung: **direkt 4 Cards** in `TripOverview` einhängen — kein zusätzlicher Wrapper-Layer (analog zur linken Spalte, wo `FullProfile` + `StageList` direkt liegen). Optionale Stack-Klasse mit `space-y-4`.

### Card 1: BriefingPreviewCard

**Props:** `trip: Trip`
**Inhalt:**
- `<Eyebrow>Briefings</Eyebrow>`
- `<h3>Tägliche Reports</h3>`
- Zwei Zeilen mit Dot (`tone='success'` wenn aktiviert, sonst grau):
  - `Morgens · {morning_time ?? '—'}`
  - `Abends · {evening_time ?? '—'}`
- Eine Zeile: `Alerts bei Änderungen · {alert_on_changes ? 'an' : 'aus'}`
- Link: `<a href="#briefings">Bearbeiten →</a>`
- Empty-State: kein `report_config` → „Briefings deaktiviert" Hinweis + Bearbeiten-Link

**TestIDs:** `right-card-briefings`, `right-card-briefings-morning`, `right-card-briefings-evening`, `right-card-briefings-alerts`, `right-card-briefings-edit-link`

### Card 2: WeatherMetricsPreviewCard

**Props:** `trip: Trip`
**Inhalt:**
- `<Eyebrow>Wetter-Metriken</Eyebrow>`
- `<h3>{presetName}</h3>` (abgeleitet aus `aggregation.activity_profile`)
- Tag-Chip-Liste: aktive Metriken aus `weather_config.metrics` (falls vorhanden) oder Default-Set basierend auf Aktivitätsprofil
- Falls keine Metriken: „Standard-Set" Pill als Fallback
- Link: `<a href="#weather">Bearbeiten →</a>`

**TestIDs:** `right-card-weather`, `right-card-weather-preset`, `right-card-weather-chip-{metricKey}`, `right-card-weather-edit-link`

### Card 3: AlertsPreviewCard (Skeleton bis #205)

**Props:** `trip: Trip`
**Inhalt:**
- `<Eyebrow>Alerts</Eyebrow>`
- `<h3>Wetter-Warnungen</h3>`
- Skeleton: „Noch keine Alerts konfiguriert" (Empty-State-Pattern)
- Link: `<a href="#alerts">Konfigurieren →</a>` (Wording weicht ab — „Konfigurieren" statt „Bearbeiten", weil nichts da)

**TestIDs:** `right-card-alerts`, `right-card-alerts-empty`, `right-card-alerts-edit-link`

### Card 4: PreviewCard

**Props:** `trip: Trip`
**Inhalt:**
- `<Eyebrow>Vorschau</Eyebrow>`
- `<h3>Wie sehen Reports aus?</h3>`
- Zwei CTAs untereinander oder nebeneinander:
  - `<a href="#preview?channel=email">📧 E-Mail-Vorschau →</a>`
  - `<a href="#preview?channel=sms">💬 SMS-Vorschau →</a>`
- Alternativ: zwei `<button>` mit `onclick={openPreview('email')}` — aber konsistent mit Tab-Wechsel-Pattern → Anker bevorzugt

**TestIDs:** `right-card-preview`, `right-card-preview-email`, `right-card-preview-sms`

### Helper-Modul `frontend/src/lib/utils/rightColumn.ts`

Pure Functions für die Kartenanzeige:
- `getPresetLabel(trip): string` — leitet aus `aggregation.activity_profile` ab (Wintersport-Standard / Wandern-Standard / Standard-Metriken)
- `getDefaultMetricsForProfile(profile): string[]` — Default-Metrik-Set falls `weather_config.metrics` fehlt
- `getReportSchedule(trip): { morning?: string; evening?: string; alertOnChanges: boolean; enabled: boolean }` — strukturierter Lese-Adapter über `report_config`

Die Helper isolieren die unsauberen `Record<string, unknown>`-Zugriffe an einer Stelle, bis #207 strukturiertes Typing einführt.

### Datei-Plan

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | Briefing-Karte | ~90 |
| NEU | `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | Wetter-Metriken-Karte | ~80 |
| NEU | `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Alert-Karte (Skeleton) | ~50 |
| NEU | `frontend/src/lib/components/trip-detail/PreviewCard.svelte` | Vorschau-Karte | ~60 |
| NEU | `frontend/src/lib/utils/rightColumn.ts` | Pure-Functions (Preset-Label, Default-Metriken, Briefing-Adapter) | ~80 |
| NEU | `frontend/src/lib/utils/rightColumn.test.ts` | Unit-Tests, mind. 12 | ~120 |
| NEU | `frontend/e2e/trip-detail-overview-right.spec.ts` | Playwright E2E, mind. 12 | ~140 |
| EDIT | `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Rechte Spalte einhängen | +12 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export 4 neuer Cards | +4 |
| EDIT | `frontend/e2e/global.setup.ts` | Test-Trip um `report_config` und `weather_config.metrics` erweitern | +12 |
| **Summe** | | | **~648 LoC** |

LoC-Override 700 vor Phase 6 setzen.

### Test-Strategie

**Unit (`rightColumn.test.ts`):**
- `getPresetLabel(trip)` mit allen 3 Aktivitätsprofilen + unbekannt + null
- `getDefaultMetricsForProfile('wintersport')` → enthält `snow_depth`, `snow_new`
- `getDefaultMetricsForProfile('wandern')` → enthält `temp_min`, `temp_max`, `precip_sum`
- `getReportSchedule(trip)` mit voll konfiguriertem report_config + leerem + null
- Edge: `report_config.enabled === false` → Schedule liefert `enabled: false`

**E2E (`trip-detail-overview-right.spec.ts`):**
- AC: rechte Spalte hat 4 Cards in fester Reihenfolge (Briefings, Wetter-Metriken, Alerts, Vorschau)
- AC: Briefing-Card zeigt Morning + Evening + Alert-Status aus Test-Trip
- AC: Klick auf „Bearbeiten →" in Briefing-Card → URL-Hash wird `#briefings`, Briefings-Tab ist aktiv
- AC: Wetter-Metriken-Card zeigt Preset-Label + mind. 1 Tag-Chip
- AC: Klick auf „Bearbeiten →" in Wetter-Card → URL-Hash `#weather`
- AC: Alert-Card zeigt Empty-State + „Konfigurieren →"-Link
- AC: Klick auf „Konfigurieren →" → URL-Hash `#alerts`
- AC: Vorschau-Card hat 2 CTAs (Email + SMS)
- AC: Klick auf E-Mail-CTA → URL-Hash `#preview`
- AC: Trip ohne `report_config` → Briefing-Card zeigt „Briefings deaktiviert", Link bleibt
- Regressions-Guard: Hero (Step 3), linke Spalte (Step 4), Header (Step 2), Tabs (Step 1) bleiben intakt

### Risiken

| # | Risiko | Mitigation |
|---|---|---|
| R1 | Generische `report_config`-Felder können fehlen oder anders heißen | Helper `getReportSchedule(trip)` validiert defensiv und liefert Defaults |
| R2 | Default-Metrik-Set für Aktivitätsprofile ist subjektiv | Default-Set in Helper hartkodieren mit Doc-Kommentar; bei echtem Preset-Feld (#206) ersetzbar |
| R3 | Tab-Wechsel-Links funktionieren nur, wenn Hash-Navigation aus TripTabs einen entsprechenden Listener hat | TripTabs liest URL-Hash bei mount + bei `hashchange` — bereits implementiert seit Step 1 |
| R4 | LoC ~648, knapp am Default-Limit 250 vorbei | Override 700 explizit setzen vor Phase 6 |
| R5 | Test-Trip in `global.setup.ts` ohne `report_config` würde Briefing-Card auf „deaktiviert" zeigen | Test-Trip um `report_config` erweitern (minimaler Edit, in Datei-Liste enthalten) |
| R6 | Card-Reihenfolge subjektiv | Spec legt feste Reihenfolge fest: Briefings → Wetter-Metriken → Alerts → Vorschau (von oben nach unten) |

### Bekannte Limitierungen (für Spec)

- Alert-Card zeigt Skeleton bis #205 die Datenmodell-Erweiterung liefert
- Wetter-Metriken-Preset-Name aus `activity_profile` abgeleitet, bis #206 echtes Feld einführt
- Generisches Typing für `report_config` (Helper kapselt unsauberen Zugriff), bis #207 strukturiertes Typing liefert
- „Bearbeiten →"-Links führen zu Tab-Placeholders, bis die jeweiligen Tabs implementiert sind
- Frontend = Desktop-Planungstool; Mobile-Stack ist Tailwind-Default (`grid-cols-1`), nicht primärer Designfall
