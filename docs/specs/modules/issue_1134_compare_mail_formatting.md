---
entity_id: issue_1134_compare_mail_formatting
type: module
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
issue: 1134
tags: [compare, email, renderer, official-alerts, frontend, bugfix]
---

# Issue #1134 — Compare-Mail Formatierungs-Fixes (Warnfarben, Dedup, Zeitfenster-Speicherung)

## Approval

- [ ] Approved

## Purpose

Behebt drei unabhängige Bugs in der Ortsvergleich-E-Mail: (1) die Warnfarbe für
Waldbrand-Stufen ist zwischen Übersichtstabelle und Pro-Ort-Stundenverlauf
inkonsistent, weil zwei unterschiedliche Farblogiken für denselben Alert
existieren; (2) „Extreme Hitze" erscheint im Pro-Ort-Stundenverlauf doppelt,
weil der Compare-Pfad keinen Dedup anwendet; (3) das im Wizard gewählte
Zeitfenster wird beim Bearbeiten eines bestehenden Orts-Vergleichs nicht
gespeichert, weil `CompareEditorEdits` kein `hourFrom`/`hourTo`-Feld trägt.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `render_official_alerts_html()` (Zeile 24-65)
- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `_warn_short()` (Zeile 160-169), `_render_location_section()` (Zeile 403-427)
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts`
- **Identifier:** `CompareEditorEdits` (Zeile 13-32), `buildComparePresetSavePayload()` (Zeile 40-99)
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
- **Identifier:** `saveComparePreset()` (Zeile 200-227)

> **Schicht-Hinweis:** Punkt 1+2 sind reines **Python-Core-Backend**
> (`src/output/renderers/`, `src/services/official_alerts/`). Punkt 3 ist
> reines **Frontend / User-UI** (`frontend/src/lib/components/compare/`,
> SvelteKit, gregor20.henemm.com). Kein Go-API-Code betroffen — die
> Edit-Route läuft ausschließlich über `PUT /api/compare/presets/{id}`
> (ComparePreset, kein `internal/model/subscription.go`, das ist seit #582
> Legacy für diese Route).

## Estimated Scope

- **LoC:** ~75 (Farb-Vereinheitlichung ~25, Dedup ~15, Frontend-Zeitfenster-Fix
  ~15, Tests ~20-30)
- **Files:** 5 (`official_alerts.py`, `compare_html.py`, `compareEditorSave.ts`,
  `compareWizardState.svelte.ts`, + Testdatei(en))
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlert` (`src/services/official_alerts/models.py:15`) | intern | `hazard`, `level` (1-4), `label`, `region_label` — Datenquelle für beide Farblogiken |
| `wildfire_risk.level` (`meteo_forets.py:109/117`, Skala `niveau_j1`) | intern | Waldbrand-Gefahrenstufe 1-4, KEIN Mindest-Schwellwert (auch Stufe 1 wird geliefert) |
| `extreme_heat.level` (`vigilance.py:130`, Skala `phenomenon_max_color_id`) | intern | Vigilance-Farbstufe, Quelle filtert bereits auf `level >= 2` (`vigilance.py:135-136`) |
| `_RISK_CELL` / `_warn_short()` (`compare_html.py:42-46, 160-169`) | Single Source | bestehende hazard-aware Stufen-Farb-Zuordnung der Übersichtstabelle — wird für Punkt 1 als kanonische Quelle wiederverwendet, kein Duplikat |
| `render_official_alerts_html()` (`official_alerts.py:24-65`) | geteilter Renderer | wird zusätzlich vom Trip-Briefing-Pfad (`html.py`, `plain.py`, `compact.py`) genutzt — Änderung MUSS für beide Pfade korrekt bleiben (ADR-0011/#1087) |
| `collect_trip_alert_entries()` (`official_alerts.py:79-96`) | Referenz-Pattern | Dedup-Prinzip für den Trip-Pfad (Gruppierung nach `region_label`) — Vorbild, nicht direkt wiederverwendbar (dort werden Segmente über mehrere Etappen dedupliziert, hier reicht Dedup innerhalb einer einzelnen `loc.official_alerts`-Liste) |
| `buildComparePresetSavePayload()` (`compareEditorSave.ts:40-99`) | Round-Trip-Spread | etabliertes Muster für editierbare Preset-Felder (`forecastHours` #764, `officialAlertsEnabled` #1040, `hourlyEnabled` #1107) — Fix für Punkt 3 folgt demselben Muster |
| `PUT /api/compare/presets/{id}` (Go-Handler, RMW-Merge) | reuse | unverändert — Fix ändert nur den Request-Body, nicht den Endpunkt |

## Implementation Details

### 1. Farbkonsistenz Waldbrand-/Hitze-Warnstufen

`render_official_alerts_html()` (`official_alerts.py:44-52`) berechnet die
Badge-Farbe heute ausschließlich aus `alert.level` (hazard-unabhängige
Schwelle: `<=2` grün, `==3` orange, `>=4` rot). Das kollidiert mit der
hazard-aware Zuordnung der Übersichtstabelle (`_warn_short()`,
`compare_html.py:160-169`, nutzt `_RISK_CELL`-Keys `caution`/`warn`/`danger`
statt Rohfarben).

Fix: `render_official_alerts_html()` erhält einen optionalen
Severity-Resolver-Parameter (Default: bestehendes Verhalten, damit der
Trip-Pfad ohne Codeänderung byte-gleich bleibt), den der Compare-Aufruf mit
einer hazard-aware Funktion befüllt, die dieselbe Stufenlogik wie
`_warn_short()` nutzt:

```
def render_official_alerts_html(
    entries: list[tuple[str, list["OfficialAlert"]]],
    severity_fn: Callable[["OfficialAlert"], str] | None = None,
) -> str:
    ...
    color = _color_for_level(alert.level) if severity_fn is None else _color_for_sev(severity_fn(alert))
```

`compare_html.py::_render_location_section` (Zeile 403-427) übergibt eine
kleine Adapter-Funktion, die `_warn_short(alert)[1]` (die bestehende
Severity-Kategorie `caution`/`warn`/`danger`/`info`) auf die drei
`official_alerts.py`-Rohfarben (`G_SUCCESS`/`G_WARNING`/`G_DANGER`) mappt —
keine zweite Farbtabelle, `_warn_short()` bleibt die alleinige Quelle für
"welche Stufe bedeutet welche Warnstufe je hazard".

Der Trip-Briefing-Pfad (`html.py`, `plain.py`, `compact.py`) ruft
`render_official_alerts_html()` weiterhin ohne `severity_fn` auf → unverändertes
Verhalten, kein Bruch von #1087/ADR-0011.

### 2. Dedup "Extreme Hitze" im Pro-Ort-Stundenverlauf

`_render_location_section()` (`compare_html.py:416-422`) ruft
`render_official_alerts_html([("", loc.official_alerts)])` ohne Dedup auf.
Fix: vor dem Aufruf wird `loc.official_alerts` auf eindeutige
`(hazard, level, label)`-Tupel reduziert (Reihenfolge erhalten, erstes
Vorkommen gewinnt) — bewusst **kein** Einsatz von `collect_trip_alert_entries()`
(das ist laut eigenem Docstring, `official_alerts.py:82-85`, explizit nur für
den Trip-Pfad gebaut, da es über mehrere Segmente hinweg nach `region_label`
gruppiert; hier reicht ein einfacher Dedup innerhalb der bereits pro-Ort
vorliegenden Liste). Neue kleine Hilfsfunktion (lokal in `compare_html.py`,
kein neuer Shared-Helper nötig — Umfang bewusst klein gehalten):

```
def _dedup_alerts(alerts: list) -> list:
    seen = set()
    out = []
    for a in alerts:
        key = (a.hazard, a.level, a.label)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out
```

**Wichtig:** zwei `OfficialAlert`-Objekte mit gleichem `hazard`, aber
unterschiedlichem `region_label` (z.B. zwei verschiedene Massive mit
`access_ban`) sind **kein** Duplikat — der Dedup-Key enthält `label` (das bei
unterschiedlichem `region_label` unterschiedlich ist), nicht nur `hazard`.

### 3. Zeitfenster im Edit-Pfad speichern

`CompareEditorEdits` (`compareEditorSave.ts:13-32`) bekommt zwei neue
optionale Felder, exakt nach dem etablierten Muster von `forecastHours`
(#764)/`officialAlertsEnabled` (#1040)/`hourlyEnabled` (#1107):

```
hourFrom?: number;
hourTo?: number;
```

`buildComparePresetSavePayload()` (Zeile 81-96) ergänzt den Body-Spread:

```
...(edits.hourFrom !== undefined ? { hour_from: edits.hourFrom } : {}),
...(edits.hourTo !== undefined ? { hour_to: edits.hourTo } : {})
```

`saveComparePreset()` (`compareWizardState.svelte.ts:200-216`) reicht
`this.timeWindowStart`/`this.timeWindowEnd` als `hourFrom`/`hourTo` durch —
analog zu den bereits durchgereichten `forecastHours`/`officialAlertsEnabled`/
`hourlyEnabled` in derselben Aufrufstelle (Zeile 212-214). Der Create-Pfad
(`saveNewPreset`, Zeile 167-168) ist bereits korrekt und bleibt unverändert.

## Expected Behavior

- **Input (1+2):** `LocationResult.official_alerts` mit einer oder mehreren
  `OfficialAlert`-Instanzen, teils mit identischem `(hazard, level, label)`.
- **Output (1):** Badge-Farbe im Pro-Ort-Stundenverlauf entspricht für
  denselben Alert exakt der Zellfarbe des zugehörigen Kürzel-Chips in der
  Übersichtstabelle (gleiche `caution`/`warn`/`danger`-Klassifikation).
- **Output (2):** Jede eindeutige Warnung erscheint höchstens einmal im
  Pro-Ort-Stundenverlauf-Streifen, unabhängig von Duplikaten in der
  Eingabeliste.
- **Input (3):** Nutzer öffnet `/compare/[id]/edit`, ändert das Zeitfenster
  (Step 5) und klickt „Speichern".
- **Output (3):** `PUT /api/compare/presets/{id}` trägt die geänderten
  `hour_from`/`hour_to`-Werte; nach Reload der Edit-Seite sind die neuen
  Werte vorausgewählt.
- **Side effects:** keine neuen Persistenz-Formate; Trip-Briefing-Pfad
  (`html.py`/`plain.py`/`compact.py`) bleibt byte-gleich, da
  `render_official_alerts_html()` ohne `severity_fn` weiterhin exakt das
  bisherige Verhalten zeigt.

## Acceptance Criteria

- **AC-1:** Given ein Ort mit einer `wildfire_risk`-Warnung Stufe 3 in der
  zugestellten Ortsvergleich-Mail / When ich die Zellfarbe des Kürzel-Chips
  in der Übersichtstabelle mit der Badge-Farbe desselben Alerts im
  Pro-Ort-Stundenverlauf vergleiche / Then sind beide Farben identisch
  (gleicher `warn`-Hex-Wert), nicht die generische Level-3-Farbe aus der
  alten hazard-unabhängigen Logik.
  - Test: Echte Staging-Mail (Stalwart, `gregor-test@henemm.com`) mit einer
    Testlocation, die eine `wildfire_risk`-Warnung Stufe 3 liefert, rendern
    lassen; Hex-Farbwert der Übersichtstabellen-Zelle und des
    Pro-Ort-Badges aus dem zugestellten HTML extrahieren und auf exakte
    Übereinstimmung prüfen (kein Dateiinhalt-Check am Quellcode).

  - **AC-1a (Edge Case — Trip-Pfad unverändert):** Given eine Trip-Briefing-Mail
    mit derselben `extreme_heat`-Warnung Stufe 3 / When ich sie mit dem Stand
    vor diesem Fix vergleiche / Then ist die Badge-Farbe im Trip-Briefing
    identisch zum Vorher-Zustand (keine Regression durch den neuen
    `severity_fn`-Parameter, da der Trip-Pfad ihn nicht übergibt).
    - Test: Echte Staging-Trip-Mail rendern lassen, Badge-Hexfarbe gegen den
      bekannten Vorher-Wert (`G_WARNING` für Level 3) aus `html.py`/`plain.py`
      prüfen.

- **AC-2:** Given ein Ort mit zwei identischen `extreme_heat`-Warnungen
  (gleicher `hazard`, `level`, `label` — z.B. durch doppelte Quellmeldung) in
  `loc.official_alerts` / When ich den Pro-Ort-Stundenverlauf-Streifen dieses
  Ortes in der zugestellten Mail betrachte / Then erscheint „Extreme Hitze"
  dort genau einmal, nicht zweimal.
  - Test: Testfall mit einer Location, deren `official_alerts` zwei
    `OfficialAlert(hazard="extreme_heat", level=3, label="...")`-Instanzen mit
    identischen Werten enthält, gegen die zugestellte Mail — Anzahl der
    Badge-Divs mit diesem Label-Text im Pro-Ort-Abschnitt dieses Ortes == 1.

  - **AC-2a (Edge Case — kein Falsch-Positiv-Dedup):** Given zwei
    verschiedene Orte mit je einer `access_ban`-Warnung für unterschiedliche
    Massive (unterschiedlicher `region_label`/`label`, gleicher `hazard`) /
    When ich beide Pro-Ort-Streifen in derselben Mail ansehe / Then zeigt
    JEDER Ort seine eigene Warnung vollständig — keine der beiden wird als
    Duplikat der anderen unterdrückt.
    - Test: Testfall mit zwei Locations, deren `official_alerts` je eine
      `access_ban`-Warnung mit unterschiedlichem `label` tragen, gegen die
      zugestellte Mail — beide Label-Texte erscheinen je einmal in ihrem
      jeweiligen Ort-Abschnitt.

- **AC-3:** Given ein bestehender Orts-Vergleich mit Zeitfenster 09:00–16:00 /
  When ich ihn unter `/compare/[id]/edit` öffne, das Zeitfenster auf
  07:00–14:00 ändere und „Speichern" klicke / Then zeigt ein erneutes Öffnen
  der Edit-Seite das neue Zeitfenster 07:00–14:00, nicht mehr das alte.
  - Test: Playwright-E2E gegen Staging als eingeloggter Nutzer — Edit-Seite
    öffnen, Zeitfenster-Felder in Step 5 auf 07:00/14:00 ändern, „Speichern"
    klicken, Redirect zur Detail-Seite abwarten, Edit-Seite erneut öffnen,
    Zeitfenster-Feldwerte auf 07/14 prüfen.

  - **AC-3a (Edge Case — Round-Trip ohne Zeitfenster-Änderung):** Given
    dasselbe Preset mit Zeitfenster 07:00–14:00 (nach AC-3) / When ich die
    Edit-Seite öffne, ein anderes Feld ändere (z.B. den Namen) und
    speichere, ohne das Zeitfenster anzufassen / Then bleibt das Zeitfenster
    07:00–14:00 erhalten (kein Reset auf einen Default-Wert).
    - Test: Playwright-E2E — Name ändern, Speichern, Reload Edit-Seite,
      Zeitfenster-Felder weiterhin 07/14, Empfänger-Liste unverändert
      (Round-Trip-Spread-Beweis analog #679 AC-3).

## Known Limitations

- Der Severity-Resolver-Parameter (`severity_fn`) wird ausschließlich vom
  Compare-Pfad genutzt. Sollte ein zukünftiger dritter Aufrufer eine dritte
  Farblogik brauchen, ist `render_official_alerts_html()` bereits darauf
  vorbereitet — kein neuer Vertrag nötig.
- Level-1-Waldbrandwarnungen (`wildfire_risk`, `niveau_j1=1`) fallen bei
  `_warn_short()` mangels explizitem Mapping-Eintrag auf die `"warn"`-Kategorie
  zurück (Bestandsverhalten, nicht Teil dieses Fixes) — dieser Fix stellt nur
  sicher, dass beide Renderpfade *dieselbe* (ggf. weiterhin ungenaue) Stufe
  zeigen, korrigiert aber nicht die Stufen-Zuordnung selbst. Kandidat für ein
  separates Folge-Issue, falls Level-1-Warnungen in der Praxis auftreten.
- Der Go-`Subscription`-Pfad (`internal/model/subscription.go`,
  `/api/subscriptions/{id}`) ist für die Compare-Edit-Route seit #582 Legacy
  und bleibt unangetastet.
- Dieser Fix ändert nicht die Farblogik der Übersichtstabelle
  (`_RISK_CELL`/`_warn_short`) selbst — sie bleibt die kanonische Quelle, auf
  die der Pro-Ort-Streifen angeglichen wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix ohne neue Architekturentscheidung. Punkt 1
  nutzt die bestehende ADR-0011-Leitplanke (ein geteilter Alert-Renderer)
  weiter — der neue `severity_fn`-Parameter ist eine additive, abwärts­
  kompatible Erweiterung derselben Funktion, kein zweiter Renderer. Punkt 3
  folgt dem bereits etablierten Round-Trip-Spread-Muster (#679/#764/#1040/#1107)
  ohne neue Abstraktion.

## Changelog

- 2026-07-09: Initial spec created (Issue #1134).
