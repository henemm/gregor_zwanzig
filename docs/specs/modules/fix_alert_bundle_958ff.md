---
entity_id: fix_alert_bundle_958ff
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [alerts, bugfix, bundle, renderer, frontend]
---

<!-- Issues #958 #959 #933 #921 #980 #981 #982 #986 — Workflow fix-alert-bundle-958ff -->

# Fix Alert Bundle — #958/#959/#933/#921/#980/#981/#982/#986

## Approval

- [x] Approved (PO „go" 2026-07-02 — inkl. der 3 Empfehlungen aus „Offene PO-Fragen" und LoC-Override 350)

## Purpose

Acht zusammenhängende Alert-System-Bugs in einem Bündel beheben: ein semantisch
falscher Δ-vs-Absolutwert-Vergleich im Renderer-Fundament (#958), zwei
uneindeutige/teils tote Alert-Metriken für die Nullgradgrenze (#959), eine
ungefilterte Schwellwerte-Tabelle im Alerts-Tab (#933), zwei veraltete Tests an
einem toten Alt-Pfad (#921) sowie vier Abweichungen des Multi-Metrik-Renderers
von der Design-Vorlage bei gemischten über-/unter-Schwelle-Events
(#980, #981, #982, #986). #958 ist das Fundament — #980/#981/#982 sowie die
Verdict-Farbe bauen auf der `over_thr()`-Neudefinition auf und sind nur korrekt,
wenn #958 zuerst implementiert wird.

## Source

> **Schicht-Hinweis:** Dieses Bündel betrifft **Python-Backend**
> (`src/output/renderers/alert/`, `src/services/`, `src/app/`, `src/formatters/`)
> UND **Frontend** (`frontend/src/lib/components/alerts-tab/`,
> `frontend/src/lib/utils/`). Kein Go-API-Code betroffen.

| # | File | Identifier |
|---|------|------------|
| #958 | `src/output/renderers/alert/model.py:62-67` | `over_thr()`, `side_label()` |
| #958 | `src/output/renderers/alert/render.py:230-233,246-249,216-221` | `_verdict_single()`, `_datablock_single()`, `_email_line()` |
| #959 | `src/services/weather_change_detection.py:41-51,69-77` | `_ALERT_METRIC_TO_SUMMARY_FIELD`, `_ALERT_METRIC_TO_CATALOG_ID` |
| #959 | `src/services/alert_preset.py:39-45` | `_PRESET_TABLE` (SNOW_LINE/FREEZING_LEVEL-Zeilen) |
| #959 | `src/app/models.py:768-788` | `AlertMetric`-Enum (SNOW_LINE, FREEZING_LEVEL) |
| #959 | `frontend/src/lib/utils/alertMetricLabels.ts:19,31,58-63` | `ALERT_METRIC_LABELS`, `LEGACY_ALERT_METRIC_MAP` |
| #959 | `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:279-300` | `CATALOG_TO_ALERT_METRICS` |
| #933 | `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:308-323` | `activeAlertableMetrics()` |
| #921 | `tests/tdd/test_trip_alert_profile.py:122-166` | `test_ac2_trip_alert_render_with_wintersport_profile`, `test_ac2_trip_alert_render_with_wandern_profile` |
| #921 | `src/formatters/trip_report.py:619-620` | toter `report_type='alert'`-Zweig |
| #980/#986 | `src/output/renderers/alert/render.py:281-317` | Multi-Datenblock (`render_email`, else-Zweig) |
| #981 | `src/output/renderers/alert/render.py:195-203,277,342` | `render_subject()`, `render_email()`-Verdict, `render_telegram()`-Kopf |
| #982 | `src/output/renderers/alert/render.py:24-27` | `_sorted()` |
| #986 | `src/output/renderers/alert/render.py:236-254,299-317,137-144` | `_datablock_single()`, Multi-Rows, `_render_email_onset()` |

## Estimated Scope

- **LoC:** ~230-290 (Achtung: **überschreitet das Workflow-LoC-Limit von 250**.
  Grund: 8 Issues über Backend + Frontend + Bestandstest-Korrekturen. Bei
  Überschreitung explizit `workflow.py set-field loc_limit_override` mit
  **User-Permission** setzen — siehe Memory-Regel „Kein LoC-Override ohne
  User-Permission").
- **Files:** ~11 (5 Backend `src/`, 3 Frontend `frontend/src/lib/`, 1
  Formatter, 2 Bestandstest-Dateien zur Korrektur)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog.get_metric/get_decimals/get_alert_label` | intern | Single Source für Kürzel/Einheit/Dezimalstellen (#914/#917-Registry) — unverändert genutzt |
| `output.renderers.email.design_tokens` | intern | `G_INK_MUTED`, `G_DANGER`, `G_SUCCESS`, `FONT_DATA` — für #980/#986-Zeilenfarben/-Tabellen |
| `WeatherChangeDetectionService` (`src/services/weather_change_detection.py`) | intern | Δ-Erkennung seit letztem Briefing — Quelle von `AlertEvent.threshold`; Verhalten der Erkennung selbst bleibt unverändert, nur die FREEZING_LEVEL-Verdrahtung wird ergänzt |
| `expand_preset()` (`src/services/alert_preset.py`) | intern | Presets → `AlertRule`-Liste; Zeilen-Konsolidierung #959 |
| `trip_alert.py:548-550` | intern | Reicht seit #638 bewusst ALLE Changes durch (über- und unter-Schwelle) — Verhalten NICHT ändern |
| Design-Vorlage `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html` | Referenz | `.datarow`-Mechanik (Z.54-58), Multi-Metrik-Mockup (Z.200-247), Betreff-Top3-Beleg (Z.208 vs. Z.218-234) |

## Implementation Details

### #958 — `over_thr()` auf Δ-Semantik umstellen (Fundament)

`src/output/renderers/alert/model.py:62-67`:

```python
# VORHER (falsch — vergleicht Absolutwert value_to mit der Δ-Sensitivitätsschwelle):
def over_thr(e: AlertEvent) -> bool:
    return e.value_to > e.threshold if e.cmp == "über" else e.value_to < e.threshold

# NACHHER (Δ-Semantik — threshold ist IMMER die Δ-Auslöseschwelle, siehe
# WeatherChange.threshold-Docstring models.py:409-428 und Issue #958-Analyse):
def over_thr(e: AlertEvent) -> bool:
    return abs(e.value_to - e.value_from) >= e.threshold
```

`e.cmp` bleibt für die Pfeilrichtung/Katalog-Zuordnung erhalten, wird in
`over_thr()` aber nicht mehr als Vergleichsoperator gegen einen Absolutwert
verwendet. `side_label()` (Zeile 66-67) bleibt strukturell unverändert
(`"über" if over_thr(e) else "unter"`), liefert durch die neue `over_thr()`
jetzt aber korrekt „über/unter der Δ-Alarm-Schwelle" statt „über/unter dem
Absolutwert".

**Wording-Anpassung** (verhindert, dass „über/unter Schwelle X m" weiterhin
wie ein Absolutwert-Vergleich gelesen wird — 3 Stellen, alle nutzen aktuell
den nackten `side_label(e)`-Wert direkt neben dem Schwellenwert):

`render.py:230-233` (`_verdict_single`, E-Mail-Verdict-Pill):
```python
# VORHER: f"{arrow(e)} {tail}jetzt {side_label(e)} Schwelle {_val(e, e.threshold)}"
#   -> "↑ +15 % · jetzt über Schwelle 400 m"
# NACHHER:
f"{arrow(e)} {tail}Änderung {side_label(e)} deiner Alarm-Schwelle ({_val(e, e.threshold)})"
#   -> "↑ +15 % · Änderung über deiner Alarm-Schwelle (400 m)"
```

`render.py:246-249` (`_datablock_single`, Datenblock-Zeile 2 „Alarm-Schwelle"):
```python
# VORHER: row2 = (f"Alarm-Schwelle {_val(e, e.threshold)}", f"jetzt {side_label(e)} {mark}")
#   -> Label "Alarm-Schwelle 400 m", Value "jetzt über ✗"
# NACHHER: Label unveraendert, Value:
row2 = (f"Alarm-Schwelle {_val(e, e.threshold)}", f"Änderung {side_label(e)} {mark}")
#   -> Value "Änderung über ✗"
```

`render.py:216-221` (`_email_line`, Telegram-Zweitzeile bei Single-Event):
```python
# VORHER: f"{_label(e)} · Schwelle {_val(e, e.threshold)} · {_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)} · {side_label(e)}"
#   -> "Nullgradgrenze · Schwelle 400 m · 2.855 m ↑ 3.285 m · über"
# NACHHER: letzten Bestandteil auf "Änderung {side_label(e)}" umstellen:
f"{_label(e)} · Schwelle {_val(e, e.threshold)} · {_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)} · Änderung {side_label(e)}"
#   -> "Nullgradgrenze · Schwelle 400 m · 2.855 m ↑ 3.285 m · Änderung über"
```

Diese drei Strings sind der Tech-Lead-Vorschlag (Variante „Änderung {über/unter}
deiner Alarm-Schwelle") — siehe „Offene PO-Fragen" unten, PO kann bei der
Spec-Freigabe eine der beiden im Auftrag genannten Varianten (Richtungswort
„gestiegen/gefallen" vs. „Änderung über/unter") final festlegen.

### #959 — `snow_line`/`freezing_level` zu EINER Metrik konsolidieren (Option a)

1. `src/services/weather_change_detection.py`: `AlertMetric.FREEZING_LEVEL`
   in beide Dicts verdrahten:
   ```python
   # _ALERT_METRIC_TO_SUMMARY_FIELD (Z.41-51):
   AlertMetric.FREEZING_LEVEL: "freezing_level_m",  # ersetzt/ergänzt SNOW_LINE-Zeile
   # _ALERT_METRIC_TO_CATALOG_ID (Z.69-77):
   AlertMetric.FREEZING_LEVEL: ("freezing_level",),  # cmp="unter" aus Katalog
   ```
   `AlertMetric.SNOW_LINE`-Einträge in beiden Dicts werden entweder entfernt
   (nach Migration, siehe Punkt 3) oder — für den Übergang — auf denselben Wert
   wie `FREEZING_LEVEL` gemappt (Backward-Compat für ungewöhnliche Zwischen-
   zustände, z. B. laufende Requests während des Deploys).

2. `src/services/alert_preset.py::_PRESET_TABLE`: EINE Zeile für die
   Nullgradgrenze statt zwei (Z.39/44). Schwellen der bisherigen
   `SNOW_LINE`-Zeile (600/400/200) — **offene PO-Frage**, siehe unten.

3. **Migration (Read-Modify-Write, PFLICHT bei Persistenz-Reworks):**
   Bestandstrips mit `metric_alert_levels.snow_line = "<preset>"` werden beim
   Laden (Trip-Loader, `src/app/loader.py` bzw. `src/app/trip.py`) auf
   `metric_alert_levels.freezing_level` gemappt — bestehendes Objekt lesen,
   nur den `snow_line`-Key umbenennen/kopieren, alle anderen Felder erhalten
   (analog zu BUG-DATALOSS-GR221 / Issue #102-Lehre). `AlertMetric.SNOW_LINE`
   bleibt als toter Enum-Wert erhalten (Backward-Compat-Deserialisierung,
   analog `HUMIDITY`-Muster `models.py:785-788`), damit alt-persistierte
   `AlertRule`-Objekte mit `metric="snow_line"` nicht crashen.

4. **Frontend:** `frontend/src/lib/utils/alertMetricLabels.ts` —
   `ALERT_METRIC_LABELS['snow_line']`-Eintrag (Z.19) aus der für den Nutzer
   sichtbaren Auswahl entfernen (nur `freezing_level`, Z.31, bleibt wählbar);
   `LEGACY_ALERT_METRIC_MAP` (Z.58-63) um `snow_line: 'freezing_level'`
   ergänzen, damit `normalizeAlertMetric()` alt-persistierte `snow_line`-Werte
   weiterhin auflöst. `frontend/src/lib/components/alerts-tab/alertMetricTable.ts`:
   `CATALOG_TO_ALERT_METRICS['snow_line']` (Z.297) und `['snowfall_limit']`
   (Z.300) auf `['freezing_level']` ummappen. `AlertMetricLevelTable.svelte`
   und `types.ts` (falls dort `snow_line` separat gelistet ist) analog
   bereinigen.

### #933 — `activeAlertableMetrics()` ohne Alle-Metriken-Fallback

`frontend/src/lib/components/alerts-tab/alertMetricTable.ts:308-323`:

```ts
// VORHER — drei Fallback-Zweige auf ALLE Metriken:
export function activeAlertableMetrics(configMetrics) {
    if (!configMetrics || configMetrics.length === 0) return ALERTABLE_METRICS;   // Z.311
    const enabled = configMetrics.filter((m) => m.enabled);
    if (enabled.length === 0) return ALERTABLE_METRICS;                          // Z.313
    const seen = new Set<AlertMetric>();
    for (const m of enabled) { ... }
    if (seen.size === 0) return ALERTABLE_METRICS;                               // Z.320
    return ALERTABLE_METRICS.filter((a) => seen.has(a));
}

// NACHHER — leere Auswahl liefert leere Liste statt aller 14 Metriken:
export function activeAlertableMetrics(configMetrics) {
    if (!configMetrics || configMetrics.length === 0) return [];
    const enabled = configMetrics.filter((m) => m.enabled);
    if (enabled.length === 0) return [];
    const seen = new Set<AlertMetric>();
    for (const m of enabled) { ... }
    return ALERTABLE_METRICS.filter((a) => seen.has(a));
}
```

`AlertsTab.svelte:49,95-96`: Bei leerem Ergebnis von `activeAlertableMetrics()`
Hinweistext statt leerer Tabelle rendern: „Wähle oben Metriken aus, um
Alarm-Schwellen zu konfigurieren."

### #921 — Toten Profil-Farb-Pfad bereinigen

PO-Entscheidung (Issue-Kommentar 2026-06-30): Alarm-Mail bewusst OHNE
Profilfarbe. `tests/tdd/test_trip_alert_profile.py:122-166` — die beiden
AC-2-Tests (`test_ac2_trip_alert_render_with_wintersport_profile`,
`test_ac2_trip_alert_render_with_wandern_profile`) werden auf neutrales Soll
korrigiert (kein Assert auf `#4a7fb5`/`#3a7d44`/Eyebrow-Text) oder entfernt,
falls sie inhaltlich nichts mehr beweisen, das nicht schon `test_ac1_*`
(Zeile ~90-118, `render_deviation_alert`-Kompat-Pfad) abdeckt. Zusätzlich:
`src/formatters/trip_report.py:619-620` — der `report_type='alert'`-Zweig hat
seit #917 keinen produktiven Aufrufer mehr (Alert-Versand läuft über
`output/renderers/alert/render.py`); toten Zweig entfernen, `update`-Pfad
(Zeile 620, `rt = "update" if report_type == "alert" else report_type`)
bleibt für andere Aufrufer unangetastet, sofern noch reale Nutzung existiert
(Prüfung im Implementierungsschritt: `grep -rn "report_type=.alert" src/`).

### #980 — Unter-Schwelle-Zeile im Multi-Datenblock

Vorlage `.datarow`-Mechanik (`Gregor 20 - Alert Mail Vorschläge.html:54-58`):
`.datarow { display:flex; align-items:baseline; justify-content:space-between; ... }`,
`.datarow .k { color: var(--g-ink-2); }`, `.datarow .v { font-family: var(--g-font-mono); font-weight:600; color: var(--g-ink); }`.
Konkrete Zielzeile (Vorlage Z.231-234):
```html
<div class="datarow">
  <span class="k" style="color:var(--g-ink-3)">Regen% <span style="color:var(--g-ink-4);font-size:13px">· unter Schwelle</span></span>
  <span class="v" style="font-weight:500;color:var(--g-ink-3)">70 → 90 %</span>
</div>
```
`render.py:281-290` (`render_email`, else-Zweig, Multi-Loop) — für Events mit
`not over_thr(e)`: Label wird `f"{_label(e)} · unter Schwelle"` (OHNE
Schwellen-Zahl, ersetzt die aktuelle `f"{_label(e)} · Schwelle {_num(...)}{threshold_suffix}"`-Zeile
für diesen Fall), Value wird `f"{_num(e, e.value_from)} → {_num(e, e.value_to)}{unit_suffix}"`
(neutraler Pfeil `→` statt `arrow(e)`, KEIN `side_label(e)`-Suffix am Ende).
Für über-Schwelle-Events bleibt das bestehende Format (mit `arrow(e)` und
`side_label(e)`-Suffix `"über"`) unverändert.

### #981 — Betreff/Verdict/Telegram-Zähler auf über-Schwelle filtern

Beleg im Mockup: Betreff (Z.208) zeigt „3 über Schwelle: Böen 52, Gewitter
55%, Niedersch 14" (3 Werte), während der Datenblock (Z.218-234) 4 Zeilen
zeigt (die vierte, „Regen% · unter Schwelle", ist NICHT im Betreff-Zähler).

`render_subject()` (`render.py:195-203`): `evs = _sorted(msg)` liefert weiter
ALLE Events (Sortierreihenfolge bleibt, gedämpfte Gruppe am Ende), aber Zähler
`n` und `top3` werden aus `[e for e in evs if over_thr(e)]` gebildet statt aus
`evs` direkt.

`render_email()`-Verdict (`render.py:277`): `f"{arrow(evs[0])} {len(evs)} über Schwelle"`
→ `len([e for e in evs if over_thr(e)])`.

`render_telegram()`-Kopf (`render.py:342`): `f"{msg.trip_short} · {km} · {len(evs)} über Schwelle"`
→ analog gefiltert.

**Randfall (0 über-Schwelle-Events):** Formulierung wechselt auf
„N Änderungen seit dem Briefing" (N = Gesamtzahl `len(evs)`) statt „0 über
Schwelle" — in allen drei Stellen (Betreff, E-Mail-Verdict, Telegram-Kopf).
**Offene PO-Frage**, siehe unten.

### #982 — Intra-Gruppen-Sortierung nach `abs(severity)`

`render.py:24-27` (`_sorted`):
```python
# VORHER:
return sorted(msg.events, key=lambda e: (not over_thr(e), -severity(e)))
# NACHHER — innerhalb der unter-Schwelle-Gruppe nach Betrag statt Vorzeichen:
return sorted(
    msg.events,
    key=lambda e: (not over_thr(e), -severity(e) if over_thr(e) else -abs(severity(e))),
)
```
Über-Schwelle-Gruppe bleibt unverändert (severity dort ohnehin ≥0 durch
Definition). Unter-Schwelle-Gruppe sortiert nach `abs(severity)` absteigend
(am weitesten von der Schwelle entferntes Event zuerst innerhalb der
gedämpften Gruppe).

### #986 — Outlook-kompatible 2-Spalten-Tabellen-Rows

Vorlage-Referenz identisch zu #980 (`.datarow`-Flex-Mechanik, Z.54-58) —
Outlook ignoriert Flexbox, daher `<table>`-Row-Pattern analog bestehender
Briefing-Mail-Tabellen (`#902` Outlook-Inline-Borders):

```html
<!-- VORHER (zwei <span> im selben <div>, kein Spalten-Trenner): -->
<div style="border-top:...;padding:8px 0;font-family:...">
  <span style="color:...">{label}</span> <span style="color:...">{value}</span>
</div>

<!-- NACHHER (2-Spalten-Tabellen-Row, Label links, Wert rechtsbündig mono): -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:...;">
  <tr>
    <td align="left" style="padding:8px 0;font-family:{FONT_UI};color:{G_INK_MUTED};">{label}</td>
    <td align="right" style="padding:8px 0;font-family:{FONT_DATA};color:{value_color};">{value}</td>
  </tr>
</table>
```

Betrifft `_datablock_single()` (Z.236-254), den Multi-Loop in `render_email()`
(Z.299-317) UND den Onset-Datenblock `_render_email_onset()` (Z.137-144) —
alle drei bauen aktuell dieselbe zwei-`<span>`-Struktur.

## Expected Behavior

- **Input:** `AlertMessage` mit einem oder mehreren `AlertEvent`s (aus
  `WeatherChange` via `project.py`), `value_from`/`value_to`/`threshold`
  (Δ-Sensitivität) pro Event.
- **Output:** Betreff/E-Mail/Telegram/SMS zeigen Δ-korrekte über/unter-Labels,
  gemischte Events werden konsistent gefiltert (Zähler), gedämpft (Layout) und
  sortiert (Betrag statt Vorzeichen); Nullgradgrenze ist EINE eindeutige
  wählbare Metrik; Alerts-Tab zeigt nur Schwellwerte zu aktiv gewählten
  Wetter-Metriken.
- **Side effects:** Bestandstrips mit `metric_alert_levels.snow_line` werden
  beim nächsten Laden auf `freezing_level` gemappt (Persistenz-Schema-Änderung,
  löst `data_schema_backup.py`-Pre-Snapshot-Hook aus).

## Acceptance Criteria

- **AC-1 (#958):** Given ein `AlertEvent` mit `value_from=2855, value_to=3285,
  threshold=400, cmp="unter"` (Nullgradgrenze, realer Fall aus dem Bug-Report)
  / When `over_thr(e)` aufgerufen wird / Then liefert es `True`, weil
  `abs(3285-2855)=430 >= 400` — unabhängig von `cmp` und unabhängig davon, ob
  `value_to` größer oder kleiner als `threshold` ist.
  - Test: `over_thr()` direkt mit den Bug-Report-Werten aufrufen und `True`
    erwarten; zusätzlich Gegenprobe mit `value_to=2855, value_from=3285`
    (fallende Richtung, gleicher Betrag) — ebenfalls `True`.

- **AC-2 (#958):** Given dasselbe Event / When `render_email()` die
  Single-Metrik-Verdict-Pill und den Datenblock rendert / Then enthält der
  Verdict-Text „Änderung über deiner Alarm-Schwelle (400 m)" (nicht mehr
  „jetzt über Schwelle 400 m") und der Datenblock zeigt „Änderung über ✗" in
  der Alarm-Schwelle-Zeile.
  - Test: `render_email()` mit dem Bug-Report-Event aufrufen, exakten
    Teilstring in `html` und `plain` prüfen.

- **AC-3 (#959):** Given ein Bestandstrip mit
  `metric_alert_levels = {"snow_line": "standard"}` (kein `freezing_level`-Key)
  / When der Trip geladen wird / Then enthält `metric_alert_levels` nach dem
  Laden `freezing_level: "standard"` statt `snow_line`, alle anderen Felder
  des Trips sind unverändert (Read-Modify-Write, kein Datenverlust).
  - Test: Echten Trip-JSON mit `snow_line`-Key in `data/users/<test-user>/`
    anlegen, über den Loader laden, `metric_alert_levels`-Inhalt prüfen.

- **AC-4 (#959):** Given `weather_change_detection.py` nach der Änderung /
  When ein Nutzer im Alerts-Tab „Nullgradgrenze" (`freezing_level`) auswählt
  und ein Δ von 430 m auf einem Segment auftritt / Then erzeugt der
  Change-Detector einen `WeatherChange`-Eintrag für `freezing_level_m` (nicht
  mehr `logger.warning(...); continue` durch fehlende Dict-Einträge).
  - Test: `WeatherChangeDetectionService` mit einer `freezing_level`-Regel und
    einem echten Δ-Szenario aufrufen, Ergebnisliste auf den Change-Eintrag
    prüfen.

- **AC-5 (#959):** Given das Alerts-Tab-Frontend nach der Konsolidierung /
  When ein Nutzer die Metrik-Auswahl öffnet / Then erscheint nur noch
  „Nullgradgrenze" als wählbare Option für diese Wettergröße —
  „Schneefallgrenze" (`snow_line`) ist keine separat wählbare Alert-Metrik
  mehr.
  - Test: Playwright gegen Staging, Alerts-Tab öffnen, Metrik-Dropdown/-Liste
    auf Abwesenheit von „Schneefallgrenze" als Alert-Metrik prüfen (echter
    Klick-Pfad, kein DB-Read).

- **AC-6 (#933):** Given ein Trip mit einer Teilmenge aktiver Wetter-Metriken,
  die keiner der 14 `ALERTABLE_METRICS` zugeordnet ist (z. B. nur
  `visibility` deaktiviert alle anderen) / When der Alerts-Tab die
  Schwellwerte-Tabelle rendert / Then zeigt sie NUR die den aktiven
  Wetter-Metriken zugeordneten Alert-Metriken statt aller 14, und bei leerer
  Zuordnung erscheint der Hinweistext „Wähle oben Metriken aus, um
  Alarm-Schwellen zu konfigurieren" statt einer vollen/leeren Tabelle.
  - Test: Playwright gegen Staging als eingeloggter Nutzer — Wetter-Metriken
    im Wizard/Editor gezielt reduzieren, Alerts-Tab öffnen, sichtbare
    Tabellen-Zeilen zählen (echter Klick-Pfad + UI-Zustand, nicht DB-Read).

- **AC-7 (#933):** Given eine aktive, im Mapping vorhandene Wetter-Metrik
  (z. B. `wind_gust`) / When der Alerts-Tab rendert / Then zeigt die Tabelle
  weiterhin genau die dieser Metrik zugeordneten Alert-Metriken (bestehendes
  Verhalten bleibt für den nicht-leeren, gemappten Fall erhalten —
  Regressionsschutz gegen die Fallback-Entfernung).
  - Test: Playwright — eine einzelne Wetter-Metrik aktivieren, Alerts-Tab
    öffnen, exakt die erwartete(n) Zeile(n) prüfen.

- **AC-8 (#921):** Given die PO-Entscheidung „Alarm-Mail bewusst ohne
  Profilfarbe" (Issue-Kommentar 2026-06-30) / When
  `test_ac2_trip_alert_render_with_wintersport_profile` und
  `test_ac2_trip_alert_render_with_wandern_profile` ausgeführt werden / Then
  prüfen sie NICHT mehr auf `#4a7fb5`/`#3a7d44`/Profil-Eyebrow, sondern
  entweder auf neutrales, profil-unabhängiges Verhalten oder sind entfernt,
  falls sie keinen zusätzlichen Beweiswert mehr haben.
  - Test: `uv run pytest tests/tdd/test_trip_alert_profile.py` grün.

- **AC-9 (#921):** Given `src/formatters/trip_report.py` nach der Bereinigung
  / When nach `report_type='alert'`-Aufrufern im Produktivcode gesucht wird
  (`grep -rn "report_type=.alert" src/ api/ cmd/`) / Then existiert kein
  produktiver Aufrufer mehr, und `format_email(report_type='update', ...)`
  verhält sich exakt wie vor der Änderung (Regressionsschutz).
  - Test: Bestehende `update`-Pfad-Tests bleiben grün; neuer/angepasster Test
    belegt, dass der tote Zweig entfernt ist ohne den `update`-Pfad zu
    beeinflussen.

- **AC-10 (#980):** Given eine Multi-Metrik-Alert-Nachricht mit einem
  unter-Schwelle-Event (z. B. `metric_id="rain_probability", value_from=70,
  value_to=90, threshold=95`) / When der E-Mail-Datenblock gerendert wird /
  Then zeigt die Zeile links `{Kürzel} · unter Schwelle` (OHNE Schwellen-Zahl,
  gedämpfte Farbe) und rechts `70 → 90 %` (neutraler Pfeil `→`, KEIN
  `über`/`unter`-Wort am Ende) — exakt wie Design-Vorlage Zeile 231-234.
  - Test: `render_email()` mit dieser Fixture aufrufen, exakten Zeilen-Text
    in `html`/`plain` prüfen.

- **AC-11 (#981):** Given eine Multi-Metrik-Nachricht mit 2 über- und 1
  unter-Schwelle-Event / When Betreff, E-Mail-Verdict-Pill und
  Telegram-Kopfzeile gerendert werden / Then zeigen alle drei „2 über
  Schwelle" (nicht 3), und das Top-3 im Betreff enthält NUR die 2
  über-Schwelle-Events.
  - Test: `render_subject()`, `render_email()`, `render_telegram()` mit
    derselben Fixture aufrufen, Zähler und Top3-Inhalt in allen drei Outputs
    prüfen.

- **AC-12 (#981, Randfall):** Given eine Multi-Metrik-Nachricht, in der ALLE
  Events unter Schwelle liegen (0 über-Schwelle-Events) / When Betreff,
  E-Mail-Verdict und Telegram-Kopf gerendert werden / Then lautet die
  Formulierung „N Änderungen seit dem Briefing" (N = Gesamtzahl) statt „0 über
  Schwelle" in allen drei Kanälen.
  - Test: Fixture mit ausschließlich unter-Schwelle-Events konstruieren, alle
    drei Renderer aufrufen, exakten Text prüfen.

- **AC-13 (#982):** Given zwei unter-Schwelle-Events mit unterschiedlicher
  Distanz zur Schwelle (z. B. `severity=-0.3` und `severity=-0.8`) in
  derselben Nachricht / When `_sorted()` die gedämpfte Gruppe ordnet / Then
  erscheint das Event mit `severity=-0.8` VOR dem mit `severity=-0.3`
  (Betrag statt Vorzeichen bestimmt die Intra-Gruppen-Reihenfolge).
  - Test: Fixture mit beiden Events konstruieren, `_sorted()` bzw. den
    gerenderten Output auf die Reihenfolge prüfen.

- **AC-14 (#986):** Given ein Single- oder Multi-Metrik-Deviation-Datenblock
  / When das E-Mail-HTML gerendert wird / Then ist jede Datenblock-Zeile eine
  `<table>`-Row mit 2 `<td>`-Zellen (Label links, Wert rechtsbündig in
  `FONT_DATA`) statt zweier `<span>`s im selben `<div>`.
  - Test: `render_email()` aufrufen, HTML auf `<table` innerhalb der
    Datenblock-Sektion und auf `align="right"` in der Werte-Spalte prüfen;
    zusätzlich Live-Screenshot-Beleg (Outlook-Renderpfad, analog #902) im
    Adversary-Dialog.

- **AC-15 (#986):** Given den Onset-Datenblock (`_render_email_onset()`) /
  When das HTML gerendert wird / Then folgt er derselben 2-Spalten-
  Tabellen-Row-Struktur wie AC-14 (konsistente Outlook-Kompatibilität über
  Deviation- UND Onset-Alerts).
  - Test: `render_email()` mit `msg.source != None` (Onset-Zweig) aufrufen,
    identische Struktur-Assertion wie AC-14.

## Erwartete Test-Brüche in Bestandstests

**Systemischer Grund:** Alle bestehenden Renderer-Fixtures wurden mit
`threshold` als *Absolutwert-Referenz* konstruiert (deshalb bisher grün) —
nach der Δ-Neudefinition (AC-1) muss jede Fixture mit
`abs(value_to - value_from)` gegen `threshold` neu durchgerechnet werden. Die
folgenden sind konkret verifizierte Beispiele (Rechnung geprüft), keine
vollständige Liste — die TDD-RED-Phase muss weitere Fälle aufdecken:

- `tests/tdd/test_957_alert_mail_literal_structure.py:76-83`
  `test_threshold_row_has_check_or_cross_mark` — Fixture
  `value_from=200, value_to=900, threshold=800, cmp="über"` erwartet `✗`
  (über Schwelle). Neu: `abs(900-200)=700 < 800` → `over_thr()=False` → `✓`
  statt `✗`. Fixture-Werte müssen auf ein Δ ≥ 800 umgestellt werden.
- `tests/tdd/test_957_alert_mail_literal_structure.py:91-95`
  `test_verdict_says_n_ueber_schwelle` — `_multi_event_msg()`-Fixture (Δ 17,
  25 und ein `threshold=999`-Event) hat KEIN Event mit Δ ≥ threshold; nach
  dem Fix zeigt der Zähler „0 über Schwelle" (bzw. nach #981-Randfall „3
  Änderungen seit dem Briefing") statt „3 über Schwelle". Fixture muss auf
  Δ-realistische Thresholds umgestellt werden.
- `tests/tdd/test_957_alert_mail_literal_structure.py:101-107`
  `test_dampened_row_for_under_threshold_event` — hängt an derselben Fixture,
  vermutlich ebenfalls betroffen (Gruppierung ändert sich).
- `tests/tdd/test_issue_917_alert_renderer.py:273-283`
  `test_arrow_color_coupled_to_over_thr` — `_make_msg_3events()`-Fixture
  (`gust 50→80, threshold=60` → Δ=30 < 60) kippt `over_thr` von `True` auf
  `False`; die Farbkopplungs-Assertion muss ggf. auf Δ-realistische
  Threshold-Werte umgestellt werden.
- `tests/tdd/test_978_deviation_line_readability.py:286-370` (Klasse rund um
  Adversary-Finding F001, Dämpfung/Reihenfolge) — die Gruppierung
  über/unter hängt direkt an `over_thr()`; mehrere dort verwendete
  Threshold/Delta-Kombinationen sind mit der alten Absolutwert-Logik gebaut
  und müssen neu kalibriert werden.
- `tests/tdd/test_trip_alert_profile.py:122-166` — **bewusster** Soll-Bruch
  (siehe AC-8/AC-9), kein Kollateralschaden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** Vorschlag `ADR-0013` — „Alert-Renderer: `threshold` ist immer
  Δ-Sensitivitätsschwelle, nie Absolutwert-Referenz" (deckt #958). Und
  Vorschlag `ADR-0014` — „Nullgradgrenze: `snow_line` und `freezing_level`
  konsolidiert zu einer Alert-Metrik" (deckt #959). Beide sind
  Richtungsentscheidungen mit Tragweite über dieses Bündel hinaus (jede
  künftige Alert-Metrik/jeder künftige Renderer-Aufrufer muss sich an die
  Δ-Semantik halten bzw. darf keine zweite Nullgradgrenze-Metrik einführen).
  **Nur vorgeschlagen, nicht angelegt** — PO entscheidet bei Spec-Freigabe,
  ob als ein gemeinsamer oder zwei getrennte ADR-Einträge.
- **Rationale:** #958 legt eine bisher implizite, fehleranfällige Annahme
  (`threshold` = Absolutwert) explizit als falsch fest und ersetzt sie durch
  eine einzige konsistente Regel — das ist eine Architektur-Entscheidung
  über die künftige Bedeutung eines Kernfelds (`AlertEvent.threshold`), kein
  reiner Bugfix-Detail. #959 entscheidet zwischen zwei Produktoptionen (a)
  Konsolidierung vs. (b) Vollverdrahtung — die getroffene Wahl (a) hat
  Folgen für Presets, Frontend-Labels und künftige Winter-Metriken.

## Offene PO-Fragen

1. **Wording #958:** Tech-Lead-Vorschlag „Änderung {über/unter} deiner
   Alarm-Schwelle (400 m)" (siehe Implementation Details) vs. Alternative
   „Richtungswort aus `direction(e)`" (z. B. „gestiegen/gefallen seit dem
   Briefing" statt „über/unter Schwelle"). Spec verwendet aktuell die erste
   Variante als konkrete AC-2 — PO kann bei Freigabe die zweite Variante
   vorziehen.
2. **Randfall #981 (0 über-Schwelle-Events):** Formulierung „N Änderungen
   seit dem Briefing" ist Vorschlag (AC-12) — PO kann alternative Formulierung
   vorgeben.
3. **Preset-Schwellen #959:** Nach Konsolidierung zu EINER Nullgradgrenze-Zeile
   — welche der beiden bisherigen Schwellen-Zeilen gewinnt? Vorschlag:
   `snow_line`-Zeile (600/400/200), da dies die aktuell tatsächlich wirksame
   Konfiguration von Bestandstrips ist (`freezing_level`-Zeile 400/200/100 war
   bisher tot, siehe #959-Befund-1). PO kann stattdessen die
   `freezing_level`-Werte oder eine dritte Größenordnung vorgeben.

## Known Limitations

- Die Migration in AC-3 deckt nur `metric_alert_levels.snow_line` ab — falls
  weitere Persistenz-Orte (z. B. Alert-Preview-Cache) denselben Key nutzen,
  müssen sie im Implementierungsschritt zusätzlich gefunden werden
  (`grep -rn "snow_line" data/ src/`).
- Kein eigener Mail-Validator für Alert-Mails (siehe Risks in
  `docs/context/fix-alert-bundle-958ff.md`) — E2E-Nachweis für AC-2/AC-10/
  AC-11/AC-12/AC-14/AC-15 läuft über den Vorschau-Endpoint (#918) und einen
  echten Staging-Alert (Fake-Radar-Seam bzw. Preview-Payload).
- `renderer_mail_gate.py` feuert NICHT für `src/output/renderers/alert/*`
  (nur `renderers/email/*`, `formatters/*`, `outputs/email.py`) — aber #921
  fasst `src/formatters/trip_report.py` an, wodurch das Gate für DIESEN Teil
  des Bündels doch greift: Modus-Matrix-Vertragstest
  (`tests/tdd/test_issue_811_mode_matrix.py`) + `briefing_mail_validator.py`
  werden vor dem Commit Pflicht.

## Changelog

- 2026-07-02: Initial spec erstellt — Bündel #958/#959/#933/#921/#980/#981/#982/#986
