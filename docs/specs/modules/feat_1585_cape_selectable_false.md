---
entity_id: feat_1585_cape_selectable_false
type: feature
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [metric-catalog, sms, compare, trip-compare-sharing, thunder, adr-0005]
workflow: 1585-cape-selectable-false
---

# Feature #1585 — CAPE wird unsichtbar (`selectable=False`), überall

## Approval

- [x] Approved

## Purpose

CAPE (Gewitterenergie, `cape_jkg`) ist heute eine ganz normal wählbare
Wetter-Metrik im Trip-Editor und im Ortsvergleich — fachlich ist sie aber nur
eine interne **Zutat** der Gewitterstufen-Fusion (`thunder_level`), keine
eigenständige, für sich genommen entscheidungsrelevante Größe. Das ist exakt
die Situation, die ADR-0005/#710 für `confidence` bereits gelöst hat:
`MetricDefinition.selectable=False` schließt eine Größe aus der
Nutzerauswahl UND aus dem gerenderten Output aus, ohne sie intern zu
entfernen.

Anders als beim `confidence`-Präzedenzfall respektieren zwei Renderer-Pfade
das zentrale `selectable`-Flag heute **nicht**: die SMS-Kanal-Kaskade
(`CP:`-Kürzel hängt am `enabled`-Flag des Trips, nicht am Katalog) und der
Ortsvergleich (eigener kuratierter 26er-Katalog + Frontend-Hardcoding, beide
lösen `cape`/`cape_max_jkg` unabhängig vom zentralen Register auf). PO-
Entscheidung 2026-08-10: **volle Parität** — CAPE wird nicht nur im
zentralen Katalog-Pfad, sondern überall unsichtbar, wo es heute als wählbare
Metrik erscheint.

## Source

> **Schicht-Hinweis:** Python-Core (`src/app/`, `src/output/`, `api/`) +
> Frontend (`frontend/src/lib/components/shared/corridor-editor/`). Keine
> Go-Beteiligung.

- **File:** `src/app/metric_catalog.py`
- **Identifier:** `MetricDefinition(id="cape", ...)` (Zeile 351-377) —
  bekommt `selectable=False`; `get_all_templates()` (Zeile 794-804) — Filter
  gegen die selectable-IDs
- **File:** `src/app/models.py`
- **Identifier:** `_filter_metrics_by_report_type()` (Zeile 613-645) —
  zusätzlicher `selectable`-Filter; wird von `get_metrics_for_channel()`
  (Zeile 735, alle drei Kaskaden-Ebenen) UND `get_metrics_for_report_type()`
  aufgerufen
- **File:** `src/output/renderers/compare_metric_catalog.py`
- **Identifier:** `get_compare_metric_catalog()` (Zeile 251-283) —
  Editor-Katalog filtert `cape_max_jkg` aus
- **File:** `src/output/renderers/compare_metric_ids.py`
- **Identifier:** `resolve_enabled_metrics()` (Zeile 125-172) — behandelt
  `cape_max_jkg` wie einen nicht auflösbaren Key (dropped + geloggt)
- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **Identifier:** `COMPARE_METRIC_KEYS` (Zeile 475-482), `_COMPARE_DEFAULTS`
  (Zeile 425-459) — `cape_max_jkg`-Einträge entfernt
- **File:** `src/output/renderers/email/compare_html.py` (Nachtrag, im
  ursprünglichen Scope übersehen — echte Lücke, am Renderer gemessen)
- **Identifier:** `CV2_METRICS` — `cape_max`-Renderzeile entfernen; ohne
  diesen Fix zeigt der Alt-Vergleich (`active_metrics=None`, kein Filter)
  weiterhin eine CAPE-Zeile, AC-5 wäre nur für Preset-Fälle erfüllt
- **File:** `src/services/weather_change_detection.py` (Nachtrag,
  PO-Entscheidung 2026-08-10 — CAPE bekommt auch keine Alarmwirkung mehr)
- **Identifier:** `is_alert_metric_active()` (Zeile 181-221) — zusätzliche
  Bedingung: die Katalog-Größe(n) hinter der `AlertMetric` müssen
  `selectable` sein, sonst gilt sie nie als aktiv. Einziger Fix-Punkt für
  AC-9 (Delta-Alarm #1592 UND Wertebereichs-Korridor, beide Trip- und
  Compare-Pfad, s. AC-9-Begründung)

**Ausdrücklich UNVERÄNDERT (Regressionsschutz, s. AC-8):**
`src/output/metric_format.py::thunder_level_from_signals()` (Zeile 315-361),
`src/providers/thunder_enrichment.py::_fuse_thunder_levels()` (Zeile
84-185) — beide lesen `cape_jkg` direkt aus den Rohdaten, nicht über den
Katalog, und bleiben vom `selectable`-Flag strukturell unabhängig (das gilt
NICHT mehr für den Alarm-Pfad, s. AC-9 oben — dort war die ursprüngliche
Einschätzung falsch und wurde per PO-Nachtrag korrigiert).

**Mitzuführende Testdateien (Bestand, ehrliche Nachführung statt Umgehung —
PO-Vorgabe „Frag nicht, ob es Umgehung ist, mach die Wahrheit sichtbar"):**
`tests/tdd/test_compare_metric_catalog_endpoint.py` (26→25, 7 Stellen),
`frontend/.../corridor-editor/__tests__/compareMetricCatalogParity.test.ts`
(24→23/25→24), `.../routeCorridorPoolCatalogExpansion.test.ts` (Trägermetrik
tauschen), `test_weather_templates.py` (AC-6-Umkehr + `test_all_metric_ids_valid`
— Rohlisten zusätzlich bereinigen), `test_alert_metric_identity_delivery.py`
(zehn→neun Alarm-Keys), `test_mail_metric_name_forms.py`,
`test_compare_mail_labels_from_register.py`, `test_compare_extra_daily_metrics.py`,
`test_compare_cape_severity_ampel.py`, `test_issue_811_mode_matrix.py`
(CAPE-Sichtbarkeit umkehren/Trägermetrik tauschen — `renderer_mail_gate`-Pflicht
beachten), `test_config_persistence.py::test_location_roundtrip_alert_enabled`
(Trägermetrik tauschen), `tests/tdd/test_trip_mail_corridor_mark.py` (3 Tests,
Korridor-Markierung entfällt, s. AC-10).

## Estimated Scope

- **LoC (Schätzung):** deutlich über der ursprünglichen Schätzung — 7
  Produktivdateien statt 5 (siehe Source) + Nachführung von ca. 12
  Bestandstestdateien (mehrheitlich mechanisch: Zahlen/Fixtures anpassen,
  vgl. `test_issue_715_confidence_not_selectable.py`-Präzedenz). Reale
  Zwischenmessung beim Developer-Agent nach den ersten 5 Dateien:
  +110/−28 Zeilen — die Testnachführung kommt noch obendrauf. **Deutlich
  über dem 250-Zeilen-Deckel**, `loc_limit_override` wird nach
  Fertigstellung mit realer Zahl beim PO eingeholt (nicht eigenmächtig).
- **Files:** 7 Produktivdateien (`metric_catalog.py`, `models.py`,
  `compare_metric_catalog.py`, `compare_metric_ids.py`,
  `corridorEditorState.ts`, `compare_html.py`,
  `weather_change_detection.py`), ~13 Bestandstestdateien nachgeführt, 2
  neue Testdateien (`test_cape_not_selectable.py`,
  `corridorEditorCapeExclusion.test.ts`).
- **Effort:** medium-high (gewachsen gegenüber Erstschätzung — Ursache:
  CAPE war jahrelang eine vollwertige, wählbare Metrik mit entsprechend
  vielen Integrationsstellen; PO-Entscheidung 2026-08-10 erweiterte den
  Scope zusätzlich um die Alarm-Wirkung).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0005-confidence-not-selectable-metric.md` | REFERENZ | Präzedenz-ADR — Mechanik `selectable=False`, Backward-Compat-Regel für Bestandsdaten |
| `tests/tdd/test_issue_715_confidence_not_selectable.py` | REFERENZ (Teststil) | Vorbild für AC-1/AC-2/AC-3/AC-7 (API-Exclusion, Renderer-Exclusion, Config-Roundtrip) |
| `src/app/metric_catalog.py::get_all_metrics()` (Zeile 687-695) | UNVERÄNDERT | Filtert bereits auf `selectable` — `/api/metrics` und E-Mail-Renderer (`helpers.py::dp_to_row`, Zeile 103-124) brauchen dadurch **keinen** Code-Edit, nur die Flag-Änderung an `cape` |
| `src/output/renderers/compare_hourly_metric_ids.py::hourly_selectable_metric_ids()` (Zeile 97-102) | UNVERÄNDERT | Leitet sich bereits aus `get_all_metrics()` ab — Compare-Stundenverlauf respektiert `selectable` automatisch, kein Edit nötig |
| `src/output/renderers/compare_metric_catalog.py::COMPARE_METRIC_CATALOG` (Zeile 76-162, roher dict-Katalog) | **NICHT LÖSCHEN** | Der Modul-Import-Assert `_catalog_keys == _resolver_keys` (Zeile 168-175) prüft gegen `FRONTEND_TO_RENDERER_METRIC_ID` (`compare_metric_ids.py`), das `cape_max_jkg` weiterhin führt — ein gelöschter Katalog-Eintrag lässt den Modul-Import mit `AssertionError` scheitern und reißt den gesamten Ortsvergleich mit. Nur die AUSLIEFERUNG (`get_compare_metric_catalog()`) filtert, der Roheintrag bleibt |
| `src/services/corridor_threshold.py::_CATALOG_BY_KEY` | UNVERÄNDERT | Liest `COMPARE_METRIC_CATALOG` direkt — bleibt funktionsfähig, weil der Roheintrag erhalten bleibt |
| `alert_preset.py` / `AlertPresetSelector.svelte` (CAPE-Delta-Alarm-Auswahl, #1592) | UNVERÄNDERT | Bewusst außerhalb des Scopes — s. Known Limitations |

## Implementation Details

### 1. Zentrales Register: `cape` bekommt `selectable=False`

```python
# src/app/metric_catalog.py, MetricDefinition(id="cape", ...)
selectable=False,
```

Zieht automatisch: `get_all_metrics()` (→ `GET /api/metrics`, Trip-Editor)
UND `helpers.py::dp_to_row()`/`visible_cols()` (E-Mail-Tabelle) — beide
filtern bereits generisch auf `metric_def.selectable`, exakt wie beim
`confidence`-Präzedenzfall. **Kein Code-Edit an `helpers.py` nötig.**

### 2. `GET /api/templates`: zentraler Filter statt drei manueller Listen-Edits

```python
# src/app/metric_catalog.py::get_all_templates()
def get_all_templates() -> list[dict]:
    selectable_ids = {m.id for m in get_all_metrics()}
    return [
        {
            "id": tid,
            "label": tdata["label"],
            "metrics": [m for m in tdata["metrics"] if m in selectable_ids],
        }
        for tid, tdata in WEATHER_TEMPLATES.items()
    ]
```

Statt `"cape"` einzeln aus den drei Listen (`alpen-trekking`, `radtour`,
`wassersport` — gegen den Code verifiziert, nicht `wandern`/`allgemein`) zu
streichen: ein Filter gegen `get_all_metrics()`, analog zu
`compare_hourly_metric_ids.py::hourly_selectable_metric_ids()`. Schützt
strukturell auch vor der nächsten `selectable=False`-Metrik, deren
Template-Referenz sonst erneut vergessen würde. `api/routers/config.py`
braucht **keinen** Edit — `get_templates()` ruft bereits `get_all_templates()`
unverändert auf.

### 3. SMS + Trip-Telegram: EIN gemeinsamer Choke-Point

`_filter_metrics_by_report_type()` (`models.py:613-645`) ist die Funktion,
durch die **alle drei Kaskaden-Ebenen** von `get_metrics_for_channel()`
laufen (Zeile 759, 771 direkt; Zeile 775 über `get_metrics_for_report_type()`)
— und `get_metrics_for_channel()` speist sowohl `trip_report.py:292`
(`sms_metric_ids`, `CP:`-Kürzel via `build_extended_metric_specs`) als auch
`channel_layout.render_for_channel()` (`narrow.py:661`, Trip-Telegram).
Verifiziert: `_visible(spec, rt)` in `output/tokens/builder.py:109-115`
liefert bei `spec.enabled=False` `None` statt eines Null-Form-Tokens — das
`CP:`-Kürzel verschwindet also vollständig, nicht nur als „CP-".

```python
# src/app/models.py::_filter_metrics_by_report_type()
from app.metric_catalog import get_metric  # lokaler Import (Zyklus-Vermeidung wie in compare_hourly_metric_ids.py)

def _is_selectable(metric_id: str) -> bool:
    definition = get_metric(metric_id) if metric_id in _METRICS_BY_ID else None
    return definition is None or definition.selectable
```

...und jeden der bestehenden `result.append(mc)`-Zweige zusätzlich gegen
`_is_selectable(mc.metric_id)` gaten. Unbekannte `metric_id`s bleiben
unverändert durch (kein neues Fehlverhalten für Alt-Daten mit inzwischen
entfernten IDs) — nur eine **bekannte, aber nicht-selektierbare** ID wird
neu ausgeschlossen.

**Nebeneffekt, im Sinne der PO-Vorgabe „überall":** derselbe Fix schließt
strukturell auch die Lücke bei Trip-Telegram (`render_for_channel` →
`narrow.py`), die im Kontext-Dokument als „keine `selectable`-Prüfung
gefunden" vermerkt war, aber nicht explizit im Auftrag stand. Da der Fix am
gemeinsamen Choke-Point sitzt, kostet das keinen Zusatzaufwand — s. AC-3
(SMS) für den geforderten Nachweis; ein Telegram-Regressionsnachweis ist in
Known Limitations als optionale Ergänzung vermerkt, nicht als eigene AC
(Auftrag nannte Telegram nicht explizit).

### 4. Ortsvergleich-Editor: `get_compare_metric_catalog()` filtert, der Rohkatalog bleibt

```python
# src/output/renderers/compare_metric_catalog.py::get_compare_metric_catalog()
for entry in source:
    metric_id = entry["metric_id"]
    definition = get_metric(metric_id)  # wirft KeyError bei unbekannter ID (unverändert, AC #1401)
    if not definition.selectable:
        continue
    ...
```

**Bewusst NICHT im rohen `COMPARE_METRIC_CATALOG` (Zeile 76-162) gelöscht**
— der Modul-Import-Assert `_catalog_keys == _resolver_keys` (Zeile 168-175)
würde sonst beim Import scheitern, weil `FRONTEND_TO_RENDERER_METRIC_ID`
(`compare_metric_ids.py:39`) `cape_max_jkg` weiterhin führt. Nur die
**Auslieferungsfunktion** filtert — dieselbe Trennung „Register bleibt
vollständig, nur die Sichtbarkeits-Ableitung filtert" wie beim
`confidence`-Präzedenzfall.

### 5. Ortsvergleich-Ausgabe (E-Mail/SMS/Telegram, deckt Preset 4 ab): `resolve_enabled_metrics()`

```python
# src/output/renderers/compare_metric_ids.py::resolve_enabled_metrics()
_NON_SELECTABLE_KEYS = {
    entry["key"] for entry in COMPARE_METRIC_CATALOG
    if not get_metric(entry["metric_id"]).selectable
}
# ... innerhalb der Normalisierungsschleife: Keys aus _NON_SELECTABLE_KEYS
# werden wie "unmapped" behandelt (gedroppt + geloggt), NICHT als KeyError.
```

`resolve_enabled_metrics()` ist der Punkt, an dem eine gespeicherte
`active_metrics`-Auswahl (z.B. Preset 4s persistiertes `"cape_max_jkg"`) in
die tatsächlich gerenderte Spalten-/Token-Liste übersetzt wird — für alle
Compare-Kanäle gemeinsam (E-Mail via `report_config_resolver.py:277`,
Telegram via `render_compare_telegram`/`_channel_layout_for_metrics`, SMS
analog). Die Funktion kennt bereits das Muster „nicht auflösbarer Key wird
gedroppt und geloggt, nicht geworfen" (Zeile 154-166) — die
`selectable`-Prüfung wird als zusätzlicher Ausschlussgrund in genau dieses
bestehende Muster eingehängt, kein zweiter Code-Pfad.

### 6. Frontend Corridor-Editor: zwei hartkodierte Fundstellen

`corridorEditorState.ts`: `cape_max_jkg` raus aus `COMPARE_METRIC_KEYS`
(Zeile 478 — die synchrone „active_metrics=null → alle Metriken aktiv"-
Fallback-Liste) und aus `_COMPARE_DEFAULTS` (Zeile 434 — Werte-Default für
„+ Metrik hinzufügen", wird ohne Backend-Katalog-Eintrag ohnehin nie mehr
erreicht, Entfernen ist Hygiene statt funktionale Notwendigkeit).

## Expected Behavior

- **Input:** Ein Nutzer öffnet den Trip-Editor eines Bestandstrips
  (`display_config.metrics` enthält `{"metric_id": "cape", "enabled": true}`)
  oder den Ortsvergleichs-Editor eines Presets mit `cape_max_jkg` in
  `active_metrics`.
- **Output:** CAPE erscheint in keiner Metrik-Auswahl mehr (`/api/metrics`,
  `/api/compare/metrics`-Auslieferung, `/api/templates`). Bereits
  gerenderte Ausgaben desselben Trips/Presets (E-Mail-Tabelle, SMS `CP:`,
  Ortsvergleichs-Tabelle) zeigen CAPE nicht mehr — ohne dass der Nutzer
  etwas ändern muss. `thunder_level` (⚡-Symbol/-Spalte) und der
  CAPE-Delta-Alarm bleiben unverändert funktional.
- **Side effects:** Keine Datenmigration, kein Datenverlust. Gespeicherte
  `display_config`/`active_metrics`-Einträge mit `cape`/`cape_max_jkg`
  bleiben in der Persistenz unverändert erhalten (Read-Modify-Write-Prinzip,
  CLAUDE.md „Daten-Schema-Reworks") — nur die Konsum-/Render-Seite ignoriert
  sie ab jetzt.

## Acceptance Criteria

- **AC-1:** Given der zentrale Metrik-Katalog / When `GET /api/metrics`
  aufgerufen wird oder der Trip-Editor die Metrik-Auswahl lädt / Then
  erscheint in keiner Kategorie ein Eintrag mit `id=="cape"`.
  - Test: Echter FastAPI-`TestClient`-Aufruf gegen `GET /api/metrics`
    (Vorbild `test_api_metrics_endpoint_excludes_confidence`), zusätzlich
    `get_all_metrics()` direkt geprüft (Vorbild
    `test_catalog_helper_excludes_confidence_from_selection`).

- **AC-2:** Given ein Bestandstrip mit `display_config.metrics` = `cape`
  `enabled=True` (synthetische Fixture, kein Zugriff auf echte PO-Daten) /
  When die E-Mail-Stundentabelle gerendert wird (`dp_to_row`/`visible_cols`)
  / Then erscheint keine CAPE-Spalte (`col_key="cape"`) — übrige aktivierte
  Metriken (z.B. Temperatur, Wind) bleiben unverändert sichtbar.
  - Test: Vorbild `test_dp_to_row_excludes_confidence_col_key` /
    `test_visible_cols_excludes_sicherheit`, 1:1 auf `cape` übertragen.

- **AC-3:** Given derselbe Bestandstrip (`cape` `enabled=True`) / When die
  SMS-Kurzform gerendert wird / Then enthält der Text kein `CP:`-Kürzel —
  weder als Wert noch als Null-Form (`CP-`).
  - Test: `SMSTripFormatter.format_sms(...)` bzw. der Aufbau von
    `sms_metric_ids`/`active_metric_ids` in `trip_report.py` mit einer
    Fixture, deren `display_config` `cape` aktiviert enthält; Assert `"CP"`
    kommt im gerenderten SMS-Text nicht vor. Ergänzend ein Unit-Test auf
    `_filter_metrics_by_report_type()`: eine `MetricConfig(metric_id="cape",
    enabled=True)` erscheint nicht im Rückgabewert für `report_type in
    {"morning", "evening"}`.

- **AC-4:** Given ein Nutzer öffnet den Ortsvergleichs-Editor (Reiter
  Wetter-Metriken/Wertebereiche) / When die verfügbaren Metriken geladen
  werden (`GET /api/compare/metrics` bzw. `get_compare_metric_catalog()`) /
  Then ist `cape_max_jkg` nicht in der angebotenen Liste — weder als
  wählbare Zeile noch als Corridor-Pool-Default (`COMPARE_METRIC_KEYS`,
  `_COMPARE_DEFAULTS` in `corridorEditorState.ts`).
  - Test: `get_compare_metric_catalog()` direkt geprüft (kein Eintrag mit
    `key=="cape_max_jkg"`); Frontend-Test (`node:test` oder Vitest) prüft
    `COMPARE_METRIC_KEYS` und `Object.keys(_COMPARE_DEFAULTS)` enthalten
    `'cape_max_jkg'` nicht mehr.

- **AC-5:** Given Vergleichs-Preset 4 (persistiert mit `cape_max_jkg` in
  `active_metrics`, synthetische Fixture nach demselben Muster wie AC-2) /
  When die Preset-Ausgabe für E-Mail, SMS oder Telegram gerendert wird /
  Then zeigt keiner der drei Kanäle CAPE — andere aktivierte Metriken des
  Presets bleiben unverändert sichtbar.
  - Test: `resolve_enabled_metrics(["cape_max_jkg", "temp_max_c", ...])`
    liefert `cape_max_jkg` nicht im Ergebnis, `temp_max_c` unverändert;
    ergänzend ein Rendering-Smoke-Test (`render_compare_telegram` oder
    `_render_html_table`-Pfad) mit derselben Fixture, der die Abwesenheit
    der CAPE-Spalte/des CAPE-Tokens im Ausgabetext bestätigt.

- **AC-6:** Given die drei Aktivitätsprofile `alpen-trekking`, `radtour`,
  `wassersport` referenzieren heute `"cape"` in `WEATHER_TEMPLATES` / When
  `GET /api/templates` aufgerufen wird / Then enthält keines der drei
  Profile `"cape"` in seiner `metrics`-Liste.
  - Test: FastAPI-`TestClient`-Aufruf gegen `GET /api/templates`, Assert
    `"cape" not in template["metrics"]` für alle Profile, die es heute
    führen; zusätzlich Assert, dass die übrigen Metriken jedes Profils
    (Anzahl/Reihenfolge minus `cape`) unverändert erhalten bleiben.

- **AC-7:** Given ein Bestandstrip mit aktiviertem `cape` UND Vergleichs-
  Preset 4 mit `cape_max_jkg` in `active_metrics` (synthetische Fixtures,
  kein Zugriff auf echte PO-Daten) / When die jeweilige Konfiguration
  geladen/deserialisiert wird / Then läuft das ohne Exception, und alle
  übrigen konfigurierten Metriken bleiben in der geladenen Konfiguration
  erhalten (kein Datenverlust, Read-Modify-Write-Prinzip).
  - Test: Vorbild `test_display_config_with_confidence_preserves_other_metrics`
    (Serialisierungs-Roundtrip über `UnifiedWeatherDisplayConfig`), analog
    ein Roundtrip-Test für ein Compare-Preset-Objekt mit `active_metrics`.

- **AC-8:** Given ein Datenpunkt mit gesetztem `cape_jkg` / When
  `thunder_level_from_signals()` bzw. `_fuse_thunder_levels()` die
  Gewitterstufe berechnen / Then ist das Ergebnis identisch zum Verhalten
  vor dieser Änderung — CAPE bleibt intern volle Zutat der Fusion.
  - Test: Bestehende Tests für `thunder_level_from_signals()`/
    `_fuse_thunder_levels()` bleiben unverändert grün (kein Edit an diesen
    Funktionen); ergänzend ein expliziter Vorher/Nachher-Vergleich mit
    einer CAPE-Grenzwert-Fixture (z.B. `cape_jkg=1200`), der dieselbe
    `ThunderLevel` vor und nach der `selectable`-Änderung liefert.

- **AC-9 (ersetzt, PO-Nachtrag 2026-08-10):** Given ein Bestandstrip/-Preset
  mit bereits konfiguriertem CAPE-Alarm (`enabled=True` in der
  `display_config`, unabhängig ob Delta-Alarm #1592 oder Wertebereichs-
  Korridor) / When die Alarm-Engine die Aktivität der Größe prüft
  (`is_alert_metric_active()`, gemeinsamer Choke-Point für Trip- UND
  Compare-Pfad über `deviation_alert_engine.py::_select_detector` →
  `expand_per_metric_levels`) / Then gilt CAPE NIE mehr als aktiv — der
  Alarm feuert nicht mehr, weder für Bestandsdaten noch neu eingerichtet.
  PO wörtlich: „CAPE soll nur noch so wie Superzellen und die anderen Werte
  dazu dienen, Gewitter genauer zu machen" — vollständig kein Nutzerkontakt
  mehr, auch nicht für Alarme. Ersetzt die ursprüngliche AC-9, die den
  Delta-Alarm fälschlich als bewusst unberührt einstufte.
  - Test: `tests/tdd/test_cape_not_selectable.py::TestAlertEngineExcludesCape`
    — `is_alert_metric_active(AlertMetric.CAPE, dc_mit_cape_enabled)` liefert
    `False`; Kollateralschaden-Wächter zeigt andere Alarmgrößen
    (`TEMPERATURE_MAX`, `WIND_GUST`) unverändert `True`.

- **AC-10 (automatische Konsequenz von AC-1, gemessen):** Given ein CAPE-
  Wertebereichs-Korridor (`Corridor(metric="cape_max_jkg", ...)`) / When
  `resolve_corridor_summary_field()` das Feld auflöst / Then liefert sie
  `None` — der Korridor markiert nichts mehr. Kein eigener Code-Fix nötig
  (die Funktion respektierte `selectable` bereits vor diesem Issue über
  `summary_field_for()`), aber 3 bestehende Tests in
  `tests/tdd/test_trip_mail_corridor_mark.py` behaupten das Gegenteil und
  brauchen eine ehrliche Nachführung (Markierung entfällt).
  - Test: `tests/tdd/test_cape_not_selectable.py::TestCorridorGoesInertForCape`
    — `resolve_corridor_summary_field("cape_max_jkg")` liefert `None`.

## Known Limitations

- **Kosmetischer Rest in der Alarm-Voreinstellungs-Liste (PO-akzeptiert
  2026-08-10):** `alert_preset.py::_PRESET_TABLE` (Zeile 62) und die
  generierte Frontend-Anzeige (`AlertPresetSelector.svelte`,
  `alertPresetThresholds.generated.json`) listen „CAPE-Anstieg" weiterhin
  als Voreinstellungs-Zeile auf. Das ist wirkungslos (AC-9 verhindert jede
  tatsächliche Alarmwirkung), aber optisch nicht bereinigt — PO hat das
  als kleine, separate Aufräumarbeit akzeptiert, kein Blocker für dieses
  Issue.
- **Trip-Telegram-Nachweis ist kein eigenes AC.** Der gewählte Fix
  (`_filter_metrics_by_report_type()`) schließt strukturell auch die im
  Kontext-Dokument vermerkte Telegram-Lücke (`render_for_channel` →
  `narrow.py`), die im PO-Auftrag nicht explizit benannt war. Ein
  expliziter Telegram-Regressionstest ist optional (Empfehlung: bei der
  Implementierung mitziehen, da er ohne Zusatzaufwand aus AC-3s
  Testinfrastruktur ableitbar ist), aber keine Bedingung für „Issue
  erfüllt".
- **`COMPARE_METRIC_CATALOG` (roher Katalog) bleibt mit `cape_max_jkg`
  bestehen** — s. Implementation Details Punkt 4. Ein künftiger, isolierter
  Blick auf diese Datei ohne diese Spec könnte fälschlich annehmen, CAPE
  sei dort „vergessen" worden; der Grund (Modul-Import-Assert) steht als
  Code-Kommentar an der Stelle, nicht nur hier.
- **Mutations-Gegenprobe, primärer Zielpunkt:** `_filter_metrics_by_report_type()`
  ist eine geteilte Funktion (E-Mail + SMS + Telegram + `get_metrics_for_report_type()`).
  Der Adversary MUSS gezielt prüfen, dass der neue Filter ausschließlich
  gegen `MetricDefinition.selectable` arbeitet (nicht gegen eine
  hartkodierte `"cape"`-Zeichenkette) — sonst bricht ein künftiger zweiter
  `selectable=False`-Fall lautlos nicht, oder eine noch-selektierbare
  Metrik verschwindet fälschlich.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue Nummer.
- **Rationale:** ADR-0005 dokumentiert bereits das Grundsatzmuster
  „`selectable=False` schließt eine Größe aus Auswahl UND gerenderter
  Ausgabe aus, Bestandsdaten laden weiterhin still" — diese Spec wendet das
  identische Muster auf eine zweite Metrik an, ohne die Entscheidung selbst
  zu ändern. Empfehlung statt neuer ADR: **ADR-0005 um einen kurzen
  Konsequenzen-Absatz ergänzen**, der festhält, dass der `selectable`-
  Vertrag inzwischen (Stand #1585) auch die SMS-Kanal-Kaskade
  (`_filter_metrics_by_report_type()`) und den Ortsvergleich
  (`get_compare_metric_catalog()`/`resolve_enabled_metrics()`) einschließt
  — beim `confidence`-Erstimplementierung (#710/#715) war das noch nicht
  der Fall, ein künftiger dritter `selectable=False`-Fall soll diese beiden
  Stellen nicht erneut selbst entdecken müssen. Diese Ergänzung ist ein
  Doku-Nachtrag (`docs/`), kein Code, und blockt Implementierung/Deploy
  nicht — PO entscheidet bei Spec-Freigabe, ob sie mit ausgeliefert wird.

## Changelog

- 2026-08-10: Initial spec created. Implementation-Details-Ansatz an fünf
  konkreten Fundstellen gegen den aktuellen Code verifiziert (nicht aus dem
  Kontext-Dokument übernommen): `_filter_metrics_by_report_type()` als
  gemeinsamer Choke-Point für SMS+Telegram (inkl. Verifikation über
  `output/tokens/builder.py::_visible()`, dass `enabled=False` den Token
  vollständig entfernt statt Null-Form zu zeigen), `get_compare_metric_catalog()`
  vs. rohes `COMPARE_METRIC_CATALOG` (Modul-Import-Assert als harter Grund
  gegen Löschen des Dict-Eintrags), `resolve_enabled_metrics()` als
  gemeinsamer Choke-Point für alle Compare-Kanäle inkl. Preset 4.
