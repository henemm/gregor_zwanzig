---
entity_id: fix_1592_c3_cape_delta_alarme
type: module
created: 2026-08-08
updated: 2026-08-08
status: draft
version: "1.0"
tags: [cape, alarme, delta, modellschwelle, issue-1592]
---

# #1592 Scheibe C3 — CAPE-Änderungsalarme in die jeweilige Modellwelt umrechnen

## Approval

- [x] Approved — PO-„Go" 2026-08-08, neun ACs auf Deutsch vorgelegt und freigegeben

## Purpose

Die letzte modellblinde CAPE-Schwellenfamilie sind die **Änderungsalarme**. Ein Sprung von
600 J/kg (Empfindlichkeitsstufe „standard") löst heute unabhängig davon aus, aus welchem
Wettermodell der Wert stammt — bei AROME praktisch nie, bei ECMWF beiläufig. Diese Scheibe
rechnet die bestehende Empfindlichkeitsleiter mit der bereits geeichten Schwelle aus B0 in
die jeweilige Modellwelt um, sodass dieselbe Stufe überall dasselbe bedeutet.

## Source

- **File:** `src/services/weather_change_detection.py` — `WeatherChangeDetectionService.detect_changes()`
- **File:** `src/app/model_registry.py` — Umrechnung + Referenzniveau
- **File:** `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` — `levelToThreshold()`

Schicht: **Python-Core** (`src/services/`, `src/app/`) + **Frontend** (SvelteKit). Keine
Go-Seite berührt.

## Estimated Scope

- **LoC:** ~55 Produktiv / ~90 Test
- **Files:** 3 Produktiv (2 Python, 1 TypeScript), 2 Test
- **Effort:** medium
- **Scope-Art:** full-stack (Frontend berührt ⇒ Browser-Gate beim Ausliefern greift)

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.model_registry.CAPE_THRESHOLDS_JKG` | vorhanden (B0) | Geeichte Niveau-Schwelle je Modell × Gebiet |
| `app.model_registry.cape_threshold_jkg()` | vorhanden (B0) | Nachschlag mit „nicht belegt" = `None` |
| `providers.thunder_routing.thunder_region_for()` | vorhanden | Koordinaten → `FR`/`DE_ALPEN`/`EU_REST` |
| `app.models.SegmentWeatherSummary.cape_model_id` | vorhanden (C0) | Herkunft am Vergleichspunkt |
| `services.alert_preset._PRESET_TABLE` | unverändert | Nominale Empfindlichkeitsleiter |

## Die Regel

```
wirksame Δ-Schwelle = nominale Preset-Zahl × cape_threshold_jkg(modell, gebiet) / 1000
```

Die **1000** ist kein neu gesetzter Wert, sondern die bis Scheibe C1 überall gültige
CAPE-Schwelle — genau die Welt, für die die Leiter 1200/600/200 geschrieben wurde. Sie wird
als benannte Konstante mit dieser Begründung abgelegt, nicht als nackte Zahl im Code.

**Keine neue Eichung, kein neuer Messlauf, keine erfundene Zahl** — die vorhandene Eichung
wird nur weitergetragen. Damit bleibt auch ADR-0043 gewahrt: die Empfindlichkeitsstufe ist
weiterhin der **einzige** Regler; Modell und Gebiet ändern nicht die Einstellung, sondern nur
ihre Übersetzung in die Skala des liefernden Modells.

### Gemessene Wirkung (alle 11 geeichten Kombinationen, Stufe „standard")

| Modell × Gebiet | geeicht | heute | neu | Faktor |
|---|---|---|---|---|
| meteofrance_arome × FR (GR20) | 300 | 600 | **180** | 0,30 |
| icon_d2 × FR | 300 | 600 | 180 | 0,30 |
| icon_d2 × DE_ALPEN | 300 | 600 | 180 | 0,30 |
| icon_eu × EU_REST | 300 | 600 | 180 | 0,30 |
| meteofrance_arome × EU_REST | 310 | 600 | 186 | 0,31 |
| icon_eu × DE_ALPEN | 360 | 600 | 216 | 0,36 |
| meteofrance_arome × DE_ALPEN | 380 | 600 | 228 | 0,38 |
| ecmwf_ifs04 × EU_REST | 420 | 600 | 252 | 0,42 |
| ecmwf_ifs04 × DE_ALPEN | 650 | 600 | 390 | 0,65 |
| ecmwf_ifs04 × FR | 710 | 600 | 426 | 0,71 |
| icon_eu × FR | 850 | 600 | 510 | 0,85 |

🔴 **Alle Faktoren liegen unter 1 — die Schwellen sinken überall, nicht nur in Frankreich.**
An keinem Referenzpunkt erreicht das 95. Perzentil der Modellklimatologie 1000 J/kg. Folge:
**mehr CAPE-Änderungsalarme als heute**, am stärksten unter AROME und ICON-D2. Das ist die
beabsichtigte Korrektur — die alte 600 war an nichts geeicht —, aber es ist eine spürbare
Produktänderung und gehört ausdrücklich in diese Freigabe.

Eine untere Grenze ist bereits eingebaut und wird **nicht** zusätzlich erfunden: die
Eichtabelle hat den Boden 300 J/kg (`scripts/eichung_cape_schwelle.py:70`), der
Umrechnungsfaktor kann deshalb nicht unter 0,30 fallen.

## Implementation Details

```
In detect_changes(), am bestehenden Sonderpfad je Metrik (weather_change_detection.py:628-630,
Vorbild _ordinal_levels aus #1460):

  wenn Feld == "cape_max_jkg":
      geeicht = cape_threshold_jkg(
          new_summary.cape_model_id,
          thunder_region_for(new_data.segment.start_point.lat,
                             new_data.segment.start_point.lon),
      )
      wenn geeicht is None:
          weiter                       # Abstain: keine Aussage, kein Alarm
      schwelle = nominale_schwelle * geeicht / CAPE_REFERENZ_NIVEAU_JKG

Die so bestimmte `schwelle` ist ab hier die EINE Wahrheit — sie entscheidet über
`triggered`, über `_classify_severity(...)` UND wird als `WeatherChange.threshold`
mitgegeben.
```

**Warum die wirksame Schwelle ins Ereignis muss:** `WeatherChange.threshold` wird nicht nur
im Alarmtext genannt (`src/output/renderers/alert/render.py:494`), sondern dort **nachgeprüft**
(`src/output/renderers/alert/model.py:97-104`, `over_thr()` → „über"/„unter") und zur
Sortierung der Alarmzeilen benutzt (`render.py:725`). Trüge das Ereignis die nominale 600,
während mit 180 ausgelöst wurde, stünde im Alarm „unter Schwelle" und die Reihenfolge wäre
falsch.

**Warum in `detect_changes()` und nicht bei der Konstruktion:** `_thresholds` ist ein Dict pro
Service-Instanz (ein Trip), Modell und Gebiet variieren aber je Segment.

**Der Ortsvergleich erbt die Wirkung**, ohne eigenen Code: `CompareAlertService` läuft über
denselben `DeviationAlertEngine` → dieselbe `detect_changes()`. Gemessen: der
Ortsvergleichs-**Alarm**pfad trägt eine echte Herkunft (`compare_location_weather_source.py:103-119`
→ `segment_weather.py:280-281` → `weather_metrics.py:802`); nur der *Anzeige*-Pfad
(`summarize_points`, `model="aggregate"`) hat keine — der löst aber keine Alarme aus.

## Expected Behavior

- **Input:** Zwei `SegmentWeatherData` (Δ-Anker und frischer Stand) mit `cape_max_jkg` und
  `cape_model_id`, plus Segment-Koordinaten.
- **Output:** `WeatherChange` für `cape_max_jkg` genau dann, wenn der Sprung die **umgerechnete**
  Schwelle überschreitet — mit dieser Schwelle im Ereignis; sonst kein Ereignis.
- **Side effects:** Keine Persistenz-Änderung, kein neues Feld, keine Abrufe zur Laufzeit.

## Acceptance Criteria

- **AC-1 (Der Kernfall: CAPE-Alarme erreichen Frankreich):** Given eine Etappe auf Korsika
  (42.22/9.05, Gebiet FR) mit Herkunft `meteofrance_arome` und Empfindlichkeitsstufe
  „standard" / When das CAPE-Tagesmaximum gegenüber dem Δ-Anker um 250 J/kg steigt / Then
  entsteht eine CAPE-Alarmzeile (umgerechnete Schwelle 180), während heute keine entsteht
  (nominale Schwelle 600).
  - Test: Aufruf über `detect_changes()` mit echten `SegmentWeatherData`; geprüft wird die
    Existenz des `WeatherChange` für `cape_max_jkg`, nicht ein Zwischenwert.

- **AC-2 (Gegenprobe — die Schwelle verschwindet nicht):** Given dieselbe Etappe und Stufe /
  When das CAPE-Maximum um nur 150 J/kg steigt / Then entsteht **keine** CAPE-Alarmzeile
  (150 < 180).
  - Test: derselbe Aufruf, leere Ergebnisliste für `cape_max_jkg`. Ohne diesen Fall wäre
    AC-1 auch von einer Implementierung erfüllt, die immer auslöst.

- **AC-3 (Unbekannte Herkunft schweigt, statt zu behaupten):** Given eine Etappe, deren
  `cape_model_id` `None` ist (unbekanntes Modell oder Herkunft über Segmentgrenzen uneinig) /
  When das CAPE-Maximum um 5000 J/kg springt / Then entsteht **keine** CAPE-Alarmzeile —
  „keine Aussage", nicht „unauffällig".
  - Test: `detect_changes()` liefert kein `cape_max_jkg`-Ereignis; Gegenprobe mit gesetzter
    Herkunft liefert eines.

- **AC-4 (Kein Gebiet, keine Aussage):** Given eine Etappe mit bekannter Herkunft, aber
  Koordinaten außerhalb jedes geeichten Gebiets bzw. einer Kombination ohne Eichwert / When
  ein beliebig großer CAPE-Sprung auftritt / Then entsteht **keine** CAPE-Alarmzeile.
  - Test: über `detect_changes()` mit einer nachweislich nicht in `CAPE_THRESHOLDS_JKG`
    enthaltenen Kombination.

- **AC-5 (Der Alarmtext nennt die Schwelle, die wirklich galt):** Given der Alarm aus AC-1 /
  When die Alarmzeile gerendert wird / Then nennt sie 180 J/kg als Schwelle und stuft das
  Ereignis als „über Schwelle" ein — nicht 600 und nicht „unter Schwelle".
  - Test: `WeatherChange.threshold == 180.0` **und** `over_thr()` des Renderer-Modells
    liefert `True` für das daraus gebaute Ereignis. Prüfort ist der Renderer, nicht nur das
    Ereignis.

- **AC-6 (Die Dringlichkeit folgt der umgerechneten Schwelle):** Given die Etappe aus AC-1 /
  When das CAPE-Maximum um 400 J/kg steigt / Then ist die Alarmstufe MAJOR (400/180 = 2,2 ≥ 2,0),
  während heute überhaupt kein Alarm entstünde (400 < 600).
  - Test: `WeatherChange.severity is ChangeSeverity.MAJOR`.

- **AC-7 (Der Ortsvergleich erbt die Wirkung, ohne eigenen Code):** Given ein Ortsvergleich
  mit einem Ort in Frankreich, Herkunft `meteofrance_arome`, Stufe „standard" / When das
  CAPE-Maximum dieses Ortes um 250 J/kg steigt / Then entsteht eine Abweichungsmeldung für
  diesen Ort.
  - Test: über den Compare-Auswertungspfad (`DeviationAlertEngine`), nicht über eine
    Trip-Attrappe — beweist die geteilte Wirkung.

- **AC-8 (Keine andere Metrik ändert ihr Verhalten):** Given identische Eingaben für
  Windböen, Niederschlag, Frischschnee und Nullgradgrenze / When `detect_changes()` vor und
  nach der Änderung läuft / Then sind Auslösung, Schwelle und Alarmstufe dieser Metriken
  byte-identisch.
  - Test: A/B-Vergleich gegen den Basis-Commit für die nicht betroffenen Metriken.

- **AC-9 (Die Anzeige behauptet keine Zahl, die nirgends wirkt):** Given der Alarme-Reiter im
  Trip-Editor mit CAPE auf „standard" / When der Nutzer die Schwellenspalte liest / Then ist
  erkennbar, dass 600 J/kg ein Richtwert ist, der je Wettermodell und Gebiet umgerechnet wird
  — bei allen anderen Metriken bleibt die Anzeige unverändert.
  - Test: `levelToThreshold('cape', 'standard')` trägt die Kennzeichnung; `levelToThreshold`
    für Windböen/Sicht/Nullgradgrenze liefert unveränderte Zeichenketten. `thresholdTitle('cape')`
    liefert die Umrechnungs-Erklärung, für alle anderen Metriken `undefined`; ein SSR-Render-Test
    (`AlertMetricLevelRow.svelte` via `svelte/server`) prüft das `title`-Attribut UND den
    Zellentext am tatsächlich erzeugten HTML. Zusätzlich im echten Browser gegen Staging
    geprüft (Frontend-Browser-Gate).

## Nicht in dieser Scheibe

- **#1601** (Modellwechsel zwischen Δ-Anker und frischem Wert löst allein einen Alarm aus).
  Gemessen bestätigt: der Anker trägt eine eingefrorene `cape_model_id`, der frische Wert
  eine aktuelle; abweichen können sie. Eigenes Ticket, direkt im Anschluss.
- **Die nominale Leiter 1200/600/200 selbst.** Sie bleibt unverändert die
  Empfindlichkeitseinstellung (ADR-0043). Dass für sie keine Quelle existiert, ist notiert
  (`docs/context/fix-1592-c3-cape-delta-alarme.md`), aber kein Gegenstand dieser Scheibe.
- **Feinere Gebiete als `FR`/`DE_ALPEN`/`EU_REST`.** Ein Perzentil je Ort wäre genauer, kostet
  aber Abrufe je Ort — in B0 bereits als spätere Verfeinerung zurückgestellt.
- **Der Katalog-Default `default_change_threshold=500`** (`metric_catalog.py:337`) bleibt
  stehen; er ist der nominale Ausgangswert für Trips ohne Empfindlichkeitsstufen und läuft
  durch dieselbe Umrechnung.

## ADR

**Kein neues ADR.** ADR-0048 („Modellabhängige Schwellen statt einer Zahl") gilt unverändert
und benennt die Δ-Alarme ausdrücklich als noch nicht umgestellt — diese Scheibe schließt
genau diese Lücke. ADR-0048 bekommt dazu einen Vollzugsvermerk.

## Changelog

- 2026-08-08: Erstfassung. Zuschnitt gegenüber dem Vorgänger-Kontextdokument erweitert
  (Umrechnung statt reinem Beleg-Gate), nachdem die Annahme „Ortsvergleich und Schnappschuss
  haben keine Modell-Herkunft" offline widerlegt wurde. Δ-Eichung per eigenem Messlauf nach
  PO-Einwand verworfen zugunsten der Umrechnung der vorhandenen Eichung.

## Korrektur am Vorgänger-Kontextdokument

`docs/context/fix-1592-cape-modellschwelle.md:258,276-279` schnitt C3 auf „nur Beleg-Gate" zu
und nahm an, Ortsvergleich und Schnappschuss-Reload hätten nie eine Modell-Herkunft. Beides
wurde am 2026-08-08 offline nachgemessen und trifft für den Alarmpfad **nicht** zu (Herkunft
`icon_d2` vorhanden, überlebt den Schnappschuss-Roundtrip). Ein reines Beleg-Gate hätte fast
nichts bewacht und den im Issue benannten Fehler unangetastet gelassen.
