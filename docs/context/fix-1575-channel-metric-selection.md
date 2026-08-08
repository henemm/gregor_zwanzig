# Context: fix-1575-channel-metric-selection

## Request Summary

#1575 Scheibe 3 (Symptom B): Die Kanal-Reiter Email/Telegram/SMS im
Wetter-Metriken-Tab des **Trip**-Editors (`shared/WeatherMetricsTab.svelte`,
`context="route"`) sollen eine echte Wirkung bekommen — Metrik-Auswahl,
Reihenfolge und Roh/Einfach-Modus werden PRO Kanal gespeichert, statt (wie
heute) eine einzige globale Liste zu mutieren, während der Reiter nur die
Vorschau umschaltet. PO-Entscheidung: "Eigene Metrik-Auswahl je Kanal" (nicht
die Alternative "Reiter nur ehrlich als Vorschau beschriften").

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (1723 Z.) | Haupt-Organism, GETEILT zwischen Trip (`context="route"`) und Compare (`context="vergleich"`) — enthält `activeChannel`-State, mountet `LayoutTab` |
| `frontend/src/lib/components/shared/layout-tab/{LayoutTab,LTChannelPicker,LTCapNote,LTCutLine}.svelte`, `ltChannels.ts` | Geteilte Kanal-Picker-Hülle aus #1232 Scheibe 3a — `ChannelId = 'email'\|'telegram'\|'sms'`, `channel` ist bisher explizit reiner View-State (`$bindable`, KEINE Persistenz) |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` (514 Z.) | Trip-Kern-Editor-Logik: `CHANNEL_COL_BUDGET`, `buildWeatherConfigMetrics`, `move`, `diffHighlight` — arbeitet auf EINER globalen `buckets`-Struktur |
| `frontend/src/lib/components/trip-detail/WeatherV2Reihenfolge.svelte` | Reihenfolge-Editor (DnD), aktuell `activeChannel` nur für Cut-Line-Anzeige, nicht für Dateninhalt |
| `frontend/src/lib/components/shared/OutputLayoutEditor.svelte` | **TOTER CODE** (0 Instanziierungen, per Kommentar in `WeatherMetricsTab.svelte` explizit "abgelöst: OutputLayoutEditor-basiertes Layout, Issue #364/#431") — KEIN Wiederverwendungs-Vorbild, siehe Analysis unten |
| `src/app/models.py:682-758` | `UnifiedWeatherDisplayConfig.per_channel_layouts`/`per_report_layouts` + `get_metrics_for_channel()` — Kaskade (#429/#434), **liest bereits korrekt**, Scheibe 1 (#1575) hat `_sorted_by_layout()` ergänzt |
| `src/output/renderers/trip_report.py:128-134` | `format_email` kollabiert `dc.metrics` bereits VOR dem Rendern via `dc.get_metrics_for_channel("email", report_type)` — Email-Selektion ist backend-seitig fertig verdrahtet |
| `src/output/renderers/narrow.py:644` | Trip-Telegram ruft `render_for_channel("telegram", dc, report_type)` — ebenfalls fertig verdrahtet |
| `src/output/renderers/channel_layout.py` | `render_for_channel()`, `CHANNEL_LIMITS` (inkl. `"sms"`) — pure functions, kanal-bewusst |
| `src/output/renderers/sms_trip.py::format_sms` | **Trip-SMS nutzt `dc.metrics`/die Kaskade NICHT** — fixes, nicht metrik-konfigurierbares Format. Einziger Aufrufer von `render_for_channel("sms", …)` im ganzen Baum ist `comparison.py` (Compare), nicht Trip |
| `internal/handler/weather_config.go`, `internal/handler/config_merge.go` | Go-API: `mergeConfigMap` ist generisches `map[string]interface{}`-Merge (Read-Modify-Write) — **kein Go-Struct-Feld nötig**, neue Keys wie `per_channel_layouts` würden schon heute schemafrei durchgereicht |

## Existing Patterns

- **Kaskade-Pattern (#429/#434):** `per_report_layouts[report_type][channel]` > `per_channel_layouts[channel]` > global. Bereits für Email und Telegram (Trip) sowie Email/Telegram/SMS (Compare) verdrahtet.
- **Geteilter Organism mit `context`-Prop** (#1232): `WeatherMetricsTab`/`LayoutTab` nehmen `context="route"|"vergleich"` und reichen `editor`/`preview`-Snippets durch — etabliertes Muster für die Teilungs-Invariante, hier fortzusetzen statt Trip-Sonderbau.
- **Kein bestehendes Vorbild für persistierte Pro-Kanal-Daten:** Weder Trip (`buckets.primary` → `display_config.metrics[].bucket/order`) noch Compare (`wiz.activeMetricKeys` → `display_config.active_metrics`, seit #1351 ebenfalls auf EINE globale Liste zurückgebaut) halten heute editierbare Kanal-Buckets. `LayoutTab.svelte` bleibt als zustandsarme UI-Hülle (Kanal-Umschalter + Grid, `editor`/`preview`-Snippets) brauchbar — die neue Datenstruktur darunter muss neu gebaut werden.

## Dependencies

- **Upstream (Backend-Kaskade):** existiert bereits vollständig für `email`/`telegram` im Trip-Kontext (siehe oben) — kein Neubau, nur ein Schreibweg fehlt.
- **Downstream (Regressionsgates):** `frontend/e2e/layout-tab-route.spec.ts` **AC-6** prüft explizit "Kanalwechsel allein löst KEINEN Auto-Save aus und bleibt nicht-dirty" — dieses Verhalten wird durch die neue Anforderung bewusst umgekehrt, der Test muss überarbeitet, nicht zufällig gebrochen werden. Ebenso `epic-138-metriken-editor.spec.ts`, `epic-138-block-b.spec.ts`, `issue-736/723/619/343/690/1117/932`-Specs als Regressionsgates.
- **Renderer-Mail-Gate (#811):** greift nur, falls `src/output/renderers/email/*.py` oder `trip_report.py` verändert werden. Falls sich der Email-Pfad wie vermutet unverändert lässt (Kaskade liest bereits), greift das Gate nicht — muss aber in `/20-analyse` bestätigt werden, sobald der SMS-Fund (s.u.) geklärt ist.
- **Pendant-Gate (#1481 B):** greift bei NEU angelegten Dateien in `trip-detail/**`/`compare/**` einseitig — Ziel ist, Kanal-Logik in `shared/**` zu bauen, dann irrelevant.

## Existing Specs

- `docs/specs/modules/layout_tab_route.md` (#1232 Scheibe 3b, status `draft`, aber implementiert & live) — **etabliert exakt das Gegenteil** der jetzigen Anforderung: "Der Kanal (`channel`) ist reiner UI-View-State ohne Persistenz — er geht NIE in `snapshot()`/`isDirty` ein", testgesichert über AC-6. Diese Spec/dieser Test müssen bewusst abgelöst werden, nicht umgangen.
- `docs/specs/modules/layout_tab_vergleich.md` (#1232 Scheibe 3a) — Compare-Seite des geteilten Organism, liefert `OutputLayoutEditor`/Bucket-Modell als Vorbild.
- `docs/specs/modules/rework_1351_compare_catalog.md` (#1351, PO-Entscheidung 2026-07-24) — **harte Leitplanke**: `channel_layouts` "bleibt Trip-only"; Compare hat `channel_layouts` bewusst als Ballast entfernt (widerspricht #1287/#1291 + Konvergenz-Richtung Epic #1230). Eine künftige Kanal-Auswahl für Compare wäre "eine neue Spec" — **diese Scheibe darf `context="vergleich"` NICHT berühren.**
- `docs/specs/modules/compare_layout_tab_dissolution.md` (#1360) — anderer, älterer, bereits entfernter Compare-Layout-Tab (Pillen-UI); nicht direkt betroffen, aber Referenzpunkt für "Attrappen-Verbot".

## Risks & Considerations

1. **🔴 Bewusste Abweichung von einer dokumentierten, testgesicherten Entscheidung (#1232 Scheibe 3b):** Die aktuelle "Kanalwechsel ist reiner Ansichtswechsel"-Regel war kein Versehen, sondern explizit spezifiziert und per Playwright-AC-6 erzwungen. Diese Scheibe hebt sie für `context="route"` bewusst auf — das muss in der neuen Spec als **Ablösung**, nicht als Nebenwirkung, benannt werden (analog ADR-Status "Abgelöst durch", auch ohne formale `docs/adr/`-Nummer).
2. **🔴 SMS-Pfad ist im Trip NICHT kaskaden-fähig:** `sms_trip.py::format_sms` liest `dc.metrics`/die Kaskade gar nicht — anders als Email/Telegram. Der KHW-Anwendungsfall ("SMS an Garmin inReach soll andere/weniger Größen zeigen") ist die zentrale Motivation des Issues, trifft aber auf eine Lücke, die über einen reinen Frontend-Schreibweg NICHT lösbar ist. Muss in `/20-analyse` geklärt werden: (a) `sms_trip.py` auf die Kaskade umstellen (zusätzlicher Backend-Scope), oder (b) der SMS-Reiter im Editor wirkt zunächst nur auf den bereits kaskaden-fähigen Telegram-Kurzform-Ersatzpfad, oder (c) Scope-Reduktion auf Email+Telegram, SMS bleibt Folge-Scheibe — PO-Entscheidung nötig.
3. **Compare darf nicht berührt werden:** geteilte Komponente + PO-Entscheidung #1351 verbieten eine Kanal-Auswahl für `context="vergleich"`. Die Implementierung muss das strukturell sicherstellen (z.B. neue Schreiblogik nur unter `context==="route"` aktiv), nicht nur durch Disziplin.
4. **Datenschema-Regel:** `per_channel_layouts`/`per_report_layouts` in `models.py` sind schema-relevant (Read-Modify-Write-Pflicht, löst `data_schema_backup`-Hook aus) — bereits als optionale Felder vorhanden, Migration vermutlich nicht nötig (Ebene ist additiv), aber in Analyse zu bestätigen.
5. **LoC-Risiko:** Das Vorbild `layout_tab_route.md` (kleinerer Scope, nur Restrukturierung) lag schon bei ~150-220 LoC Produktivcode + ~150-200 Tests. Diese Scheibe fügt zusätzlich eine neue Datenstruktur + Persistenz-Pfad hinzu — Überschreitung des 250-LoC-Limits ist wahrscheinlich, PO-Freigabe für `loc_limit_override` ist vorzubereiten, nicht eigenmächtig zu setzen.

## Analysis

### Type

Feature (Full Process) — Frontend-Editor-Persistenzpfad + ein kleiner, notwendiger Backend-Fix.

### SMS-Backend-Fund aufgelöst (war Risk 2)

`sms_trip.py::format_sms` selbst muss **nicht** umgebaut werden. Der eigentliche Bug sitzt in
`trip_report.py` (Methode, die auch `format_email` speist): Zeile ~128-134 kollabiert `dc.metrics`
via `dc.get_metrics_for_channel("email", report_type)` — und Zeile ~296
(`active_metric_ids = {m.metric_id for m in dc.metrics}`), die die SMS-Specs/-Schwellwerte baut,
liest genau diese bereits **email-kollabierte** `dc`. SMS erbt dadurch strukturell die
Email-Metrikauswahl, nie eine eigene. Fix: `sms_metrics = dc.get_metrics_for_channel("sms",
report_type)` separat ziehen, `active_metric_ids` daraus bilden statt aus dem kollabierten `dc`.
Klein (~15-25 LoC + Test). Realer SMS-Versand bestätigt über `src/output/channels/sms.py`
(seven.io) — `format_sms`-Text ist tatsächlich das Zugestellte. Einschränkung (kein Blocker): nur
~12 Metriken sind über `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` überhaupt SMS-fähig.

### Kein Wiederverwendungs-Vorbild für Pro-Kanal-Persistenz

`OutputLayoutEditor.svelte` ist toter Code (0 Instanziierungen). Sowohl Trip als auch Compare
(seit #1351, "channel_layouts-Ballast" bewusst entfernt) sind heute auf eine globale, geordnete
Liste zurückgebaut. `LayoutTab.svelte` (Kanal-Umschalter-Hülle) bleibt brauchbar, die Datenstruktur
darunter (`channelBuckets: Record<ChannelId, Buckets>` + `channelFriendlyMap`) ist Neubau. Isolation
Trip/Compare ist strukturell bereits sauber (hartes `{#if context==='vergleich'}`-Branching,
komplett getrennte Save-Pfade `metricsEditor.ts` vs. `compareEditorSave.ts`/`weatherMetricsCompareSave.ts`).

### 🔴 Neuer Fund: Shallow-Merge-Datenverlust-Risiko

Der rohe JSON-Key ist `channel_layouts` (nicht `per_channel_layouts` — das ist nur der
Python-Feldname) unter `display_config` (nicht `weather_config` — Issue-Text ist hier ungenau).
Go mergt `DisplayConfig` nur **shallow auf oberster Schlüsselebene**
(`internal/handler/config_merge.go:11-22`, aufgerufen `trip.go:304`). Sendet das Frontend beim
Speichern unter Reiter "SMS" nur `channel_layouts: {sms: [...]}`, **ersetzt das den kompletten
`channel_layouts`-Wert** — bereits gespeicherte `email`/`telegram`-Einträge werden lautlos
gelöscht. Ein neuer BUG-DATALOSS-GR221-Fall, den diese Scheibe selbst einführen würde, wenn das
Frontend nicht bei jedem Save den vollständigen `channel_layouts`-Stand alle bereits berührten
Kanäle mitsendet. **Pflicht-AC:** "Speichern in Kanal X lässt Kanal Y unverändert" — eigener Test.

### Copy-on-write statt Eager-Init

Ein Kanal bekommt erst beim ersten tatsächlichen Edit unter diesem Reiter einen eigenen Eintrag;
bis dahin liest der Reiter die globale Liste (spiegelt die Backend-Kaskade: `None` = Fallback auf
global). Verhindert, dass ein nie berührter Kanal fälschlich als "eigene leere Auswahl" gespeichert
wird.

### AC-6 (`layout_tab_route.md`): aufspalten, nicht ersetzen

Die alte Garantie "reiner Kanal**wechsel** (ohne Edit) bleibt clean/nicht-dirty" bleibt ein
sinnvolles eigenständiges Invariant. Neu daneben: "Kanal-**Edit** macht dirty UND das Speichern
schreibt nur den aktiven Kanal in `channel_layouts[kanal]`, andere Kanäle bleiben unverändert"
(deckt auch den Shallow-Merge-Test ab).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | SMS-Fix: `active_metric_ids` aus `get_metrics_for_channel("sms", …)` statt kollabiertem `dc` |
| `tests/tdd/` oder passende Modul-Suite | CREATE | RED/GREEN-Nachweis SMS-Fix |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | neue Kanal-State-Vars, `snapshot()`/`isDirty`-Erweiterung, Save-Payload |
| `frontend/src/lib/components/shared/` neue Datei (z.B. `channelLayouts.ts`) oder Erweiterung `metricsEditor.ts` | CREATE/MODIFY | `channelBuckets`/`channelFriendlyMap`-Struktur, Serialisierung zu `channel_layouts` (voller Stand, alle berührten Kanäle) |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | MODIFY | liest/schreibt kanalspezifische Buckets statt nur `activeChannel` für Cut-Line |
| `frontend/e2e/layout-tab-route.spec.ts` | MODIFY | AC-6 aufspalten (s.o.) + neuer Datenverlust-Test |
| `frontend/src/lib/components/shared/weatherMetricsTabSharing.test.ts` (bestehend) | MODIFY | Fall ergänzen: neue Kanal-State-Vars werden im `vergleich`-Zweig nie gelesen |

### Scope Assessment

- Files: ~7-9 (2 Backend, 5-7 Frontend inkl. Tests)
- Estimated LoC: Produktivcode ~200-350, Tests ~200-300 — **Überschreitung des 250-LoC-Limits
  wahrscheinlich**, `loc_limit_override` (Richtwert ~500, analog `layout_tab_route.md`-Vorgänger)
  vor Phase 6 explizit beim PO einholen, nicht eigenmächtig setzen.
- Risk Level: MEDIUM — Backend-Kaskade fertig, Isolation Trip/Compare strukturell sauber; Hauptrisiko
  ist der neue Shallow-Merge-Fund (gut testbar) und das Aufspalten von AC-6 sauber umzusetzen.

### Technical Approach

Ein Workflow (nicht mehrere Scheiben) — UI ohne den SMS-Backend-Fix wäre für SMS wirkungslos
(Attrappen-Verbot). Reihenfolge innerhalb des Workflows: TDD-RED zuerst isoliert für den kleinen,
unabhängig prüfbaren SMS-Backend-Fix, danach der größere Frontend-Persistenzpfad. Telegram-Backend
ist bereits fertig verdrahtet (`narrow.py:644`) — bei LoC-Druck wäre eine Zurückstellung der
Telegram-Editor-UI ein möglicher Trade-off, aber PO-Entscheidung, keine Vorentscheidung dieser Analyse.

### Dependencies

Wie in Related Files/Existing Specs oben — zusätzlich bestätigt: Renderer-Mail-Gate (#811) greift
sicher, da `trip_report.py` verändert wird → `briefing_mail_validator.py` gegen echte Staging-Mail
ist Pflicht vor "E2E bestanden".

### Open Questions

- [ ] Scope-Bestätigung: nur Metrik-Auswahl/Reihenfolge/Roh-Einfach pro Kanal — Horizonte,
      SMS-Schwellwerte, Auswertungswahl bleiben global?
- [x] Alt-`channel_layouts`-Datenfalle: **PO-go 2026-08-08, per Prod-Check verifiziert.**
      `sudo -u claude-gregor grep -rl "channel_layouts\|per_channel_layouts\|per_report_layouts"
      /home/hem/gregor_zwanzig/data/users/` (137 Briefing-Dateien durchsucht) findet **keine**
      Treffer in `briefings/` (Trip-Daten). Die einzigen zwei Treffer liegen in
      `henning/compare_presets.json` und `compare_subscriptions.json.bak` — Compare-Altlast,
      bereits durch #1351 als zu bereinigender Ballast bekannt, außerhalb dieser (Trip-)Scheibe.
      **Migration/Bereinigung ist NICHT Teil dieser Scheibe** — kein Bestands-Trip betroffen.
- [x] Telegram: **PO-go 2026-08-08** — vollwertig, alle drei Kanäle in dieser Scheibe.
- [x] Vererbung beim ersten Kanal-Edit: **PO-go 2026-08-08** — Kopie der aktuellen globalen
      Auswahl als Startpunkt.
- [x] Scope je Kanal: **PO-go 2026-08-08** — nur Auswahl/Reihenfolge/Roh-Einfach; Horizonte,
      SMS-Schwellwerte, Auswertungswahl bleiben global.
- Shallow-Merge-Schutz bleibt Pflicht-AC (kein PO-Ermessen — Datenverlust-Vermeidung ist Standard-
  Regel, nicht optional).

## Next Step

Kontext und Analyse vollständig. Weiter mit `/30-write-spec` — die fünf offenen Fragen oben werden
in die Spec aufgenommen und dem PO zur Freigabe vorgelegt (nicht separat vorab entschieden).
