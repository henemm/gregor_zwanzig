---
entity_id: fix_2049_ausblick_darstellungsform
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [ausblick, darstellungsform, roh-einfach, issue-2049]
workflow: fix-2049-vorschau-einfach
---

# #2049 — Roh/Einfach-Umschalter im 3-Tages-Ausblick wird wirksam

## Approval

- [x] Approved — PO-Freigabe 2026-08-22 ('approved'), inklusive der drei Wortskalen
      (Regenwahrscheinlichkeit, Sonnenstunden, Niederschlag-Tagessumme)

## Purpose

Der Roh/Einfach-Umschalter im Block „3-Tages-Vorschau" ist heute eine Attrappe: der
Handler ist ein No-Op und die Übersetzungstabelle immer leer, ein Klick verändert nichts.
Diese Spec legt fest, wie die Umschaltung **wirksam** wird — mit einer eigenen Einstellung
je Trip/Ortsvergleich für den Ausblick (nicht geerbt vom E-Mail-Kanal), einer Fähigkeitsliste,
die Bedienfläche und Wirkung an derselben Quelle festmacht, und drei neu festgelegten
Wortskalen für Größen, die bisher keine Einfach-Form hatten.

## Source

- **File:** `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`
- **Identifier:** `function noopOutlookMode(): void {}` (`:180-183`), `friendlyMap={{}}` /
  `onMode={noopOutlookMode}` im `WeatherV2Reihenfolge`-Aufruf (`:217-229`)
- **File:** `src/output/renderers/compare_outlook_metric_ids.py`
- **Identifier:** `format_outlook_value` (`:374-406`) — der Zellenbau ohne Einfach-Zweig

## Estimated Scope

- **LoC:** ~280–320 (Frontend ~60, Backend ~150, Tests ~90)
- **Files:** 10 (8 MODIFY, 1 CREATE, 1 Test-MODIFY) — LoC-Limit-Override auf 500 nötig
- **Effort:** medium-high

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `WeatherV2Reihenfolge.svelte` (`:101-102, 148-155`) | Komponente | trägt den `Segmented`-Umschalter bereits vollständig — schmalste Einstiegsstelle |
| `WeatherMetricsTab.svelte` (`:724-731`) | Vorlage | funktionierender `onMode` des Kanal-Pfads, 1:1 als Vorbild für den Ausblick-Pfad |
| `_resolve_format_mode` (`src/app/loader.py:56-88`) | Funktion | Vorrangregel `format_mode` > `use_friendly_format=False` → `raw` > Katalog-Default — Muster, **nicht** direkt verwendbar für den Ausblick-Default (s. Risiko/AC-2) |
| `degrees_to_compass` (`src/utils/geo.py:32`) | Funktion | Windrichtung → Himmelsrichtung, wiederverwendet |
| `cloud_emoji` (`src/output/metric_format.py:253`) | Funktion | Bewölkung → Symbol, wiederverwendet |
| `format_wind_strength` (`src/services/weather_metrics.py:122`) | Funktion | Wind/Böen-km/h → Wortstufe, wiederverwendet |
| `format_precip_intensity` (`src/services/weather_metrics.py:143`) | Funktion | Vorlage für Niederschlag-Wortstufe, Schwellen müssen für Tagessumme neu geeicht werden |
| `normalize_outlook_metric_ids` (`src/app/metric_catalog.py:957-984`) | Funktion | Engstelle der Kette, muss um das neue Feld ergänzt werden |
| `resolve_trip_outlook_metrics` (`compare_outlook_metric_ids.py:194-222`) | Funktion | löst Ausblick-Konfiguration auf, muss das Flag durchreichen |
| `outlook_columns` (`compare_outlook_metric_ids.py:265-341`) | Funktion | einziger Transportweg zu allen vier Ausgaben — Flag muss hier je Spalte ankommen |
| `_merge_min_max_pairs` (`compare_outlook_metric_ids.py:325-371`) | Funktion | baut ein NEUES Dict, kopiert nur gelistete Schlüssel — neues Feld muss hier zusätzlich ergänzt werden |
| `build_outlook_row` (`src/output/renderers/email/outlook.py:602-674`) | Funktion | der eine Zellenbau, speist alle vier Ausgaben |
| `_metric_column_bg` (`src/output/renderers/email/outlook.py:345-368`) | Funktion | HTML-Ampeltönung, bleibt unbedingt aktiv, unabhängig vom neuen Flag |
| `tests/tdd/test_shared_outlook_renderer.py` | Test | Paritäts-Wächter, muss grün bleiben (ADR-0037-Folgepflicht) |
| `tests/tdd/test_trip_outlook_parity.py` | Test | bytegenauer HTML/Klartext-Vergleich gegen Fixtures, muss grün bleiben |
| `internal/handler/config_merge.go:12-21` (`mergeConfigMap`) | Go-Funktion | flacher Read-Modify-Write auf `display_config` — reicht das neue Sibling-Feld automatisch durch, keine Änderung nötig |
| ADR-0050 Regel 5 | Entscheidung | „Reihenfolge und Rohwert-/Einfach-Format bleiben kanal-eigen" — wird hier auf die Fläche „Ausblick" angewandt |
| ADR-0055 Punkt 2 | Entscheidung | keine Kanal-Ebene für den Ausblick — bleibt unangetastet, das neue Feld ist global je Fläche |

## Implementation Details

### Speicherform

Neues paralleles Feld `display_config.outlook_metric_formats: {metric_id: bool}` als
Sibling von `outlook_metrics` (`true` = Einfach, `false`/fehlend = Roh). **Keine** Rückkehr
zur Objektform in `outlook_metrics` — #1848 A2 hat dieses Feld bewusst auf reine
Kennungen (`list[str]`) verengt, um ein „viertes Vokabular" abzuschaffen. Ein Sibling-Key
ist strukturell dasselbe Muster wie `channel_layouts` neben `metrics`.

Go braucht keine Änderung: `internal/model/trip.go:117` (`DisplayConfig
map[string]interface{}`) ist schemalos, `mergeConfigMap` merged nur die oberste
Schlüsselebene und reicht das neue Unterfeld automatisch durch.

### Default ist explizit „Roh"

Der Ausblick-Default für ein Flag, das noch nie gesetzt wurde, ist **hart `False`**
(„Roh") — unabhängig vom Katalog-Feld `default_format_mode`. Der `_resolve_format_mode`-
Rückfall wäre für `cloud_total`/`sunshine`/`wind_direction` `symbol`/`scale`, nicht `raw`.
Würde der Ausblick diesen Rückfall übernehmen, änderte sich das Aussehen bestehender
Trips ohne jede Nutzeraktion, und die bytegenauen Paritäts-Fixtures in
`test_trip_outlook_parity.py` brächen — zu Recht, weil unangekündigt.

### Fähigkeitsliste statt `indicatorCapable()`

Der Umschalter erscheint nur für Metriken, die im Ausblick tatsächlich eine Einfach-Form
haben. `indicatorCapable()` (Frontend, `metricsEditor.ts:25-39`, 12 Einträge) kennt die
Ausblick-Semantik nicht und ist der falsche Wächter. Stattdessen liefert eine
ausblick-eigene Fähigkeitsliste — abgeleitet aus derselben Quelle wie der
Backend-Formatierer (`friendly_label`-Träger + die drei neuen Wortskalen) — sowohl die
Sichtbarkeit des Bedienelements als auch die Formatierungsentscheidung. Damit können
Bedienfläche und Wirkung nicht mehr auseinanderlaufen (das war exakt der Auslöser des
Bugs: A2 änderte die Sichtbarkeitsbedingung, ohne die Wirkungskette mitzuziehen).

**Metrik-Matrix (Ausblick):**

| Metrik | Umschalter | Einfach-Form | Helfer |
|---|---|---|---|
| `wind_direction` | JA | Himmelsrichtung (`SW`) | `degrees_to_compass` |
| `cloud_total`/`_low`/`_mid`/`_high` | JA | Symbol (`⛅`) | `cloud_emoji` |
| `wind` | JA | Wortstufe (`sehr stark`) | `format_wind_strength` |
| `gust` | JA | Wortstufe | `format_wind_strength` |
| `precipitation` | JA | Wortstufe, neu geeicht auf Tagessumme | neue Skala, s. u. |
| `rain_probability` | JA | Wortskala, neu | neue Skala, s. u. |
| `sunshine` | JA | Wortskala, neu | neue Skala, s. u. |
| `thunder` | NEIN | — Roh ist bereits das Wort | `_fmt_thunder` |
| `temperature` / `wind_chill` | NEIN | keine Einfach-Form im Produkt | — |
| `cape` | NEIN | kommt im Ausblick nicht vor (`selectable=False`) | — |
| `visibility` | NEIN | bewusst keine (#814 AC-5) | — |

### Kein Ampelpunkt in HTML — Wort/Symbol in allen vier Ausgaben

`stage["cells"]` ist ein geteilter Kanal für HTML **und** Text (`build_outlook_row`
schreibt die Zellenliste einmal, vier Renderer lesen sie). `format_outlook_value` hat
anders als `fmt_val` keinen `html`-Parameter, und die HTML-Zelle wird escaped
(`_html.escape(text)`, `outlook.py:151`). Ein HTML-Ampelpunkt (`_ampel_dot_severity`)
scheidet daher aus — er erschiene als Quelltext bzw. auch in Telegram. „Einfach" heißt
im Ausblick deshalb: **dieselbe Wort-/Symbol-Zeichenkette in allen vier Ausgabeorten**
(E-Mail HTML `outlook.py:130-146`, E-Mail Klartext `:290-315`, E-Mail kompakt
`compact.py:265-282`, Telegram `narrow.py:549-580`). Die HTML-Zelle trägt ihre Ampel
bereits als Hintergrundtönung (`_metric_column_bg`, unbedingt aktiv seit #1849) — das
bleibt unverändert und unabhängig vom neuen Flag bestehen.

### Drei neue Wortskalen

Reine Zustandsbeschreibungen ohne Handlungsempfehlung (ADR-0007):

| Größe (Aggregat im Ausblick) | Wortskala | Schwellen |
|---|---|---|
| Regenwahrscheinlichkeit (Maximum) | `unwahrscheinlich / möglich / wahrscheinlich / sehr wahrscheinlich` | `<25 / <50 / <75 / >=75 %` |
| Sonnenstunden (Tagessumme) | `trübe / wechselhaft / freundlich / sonnig` | `<2 / <5 / <8 / >=8 h` |
| Niederschlag (Tagessumme, neu geeicht) | `trocken / leicht / mäßig / stark` | `<=0 / <=5 / <=20 / >20 mm` |

Die Niederschlags-Schwellen sind **nicht** identisch mit `format_precip_intensity`
(2/10 mm) — jene meint Stundenwerte, der Ausblick zeigt eine Tagessumme.

### Kette (Frontend → Go → Python)

```
WeatherV2Reihenfolge (trägt Umschalter bereits)
  → CompareOutlookLayoutControls (echter onMode statt noopOutlookMode,
                                    echte friendlyMap statt {})
  → WeatherMetricsTab (State, Lade-/Speicherpfad, beide Einbettungen: Wizard + Trip)
  → display_config.outlook_metric_formats (neues Sibling-Feld)
  → Go: unverändert (schemalos, mergeConfigMap reicht durch)
  → normalize_outlook_metric_ids() um das Feld ergänzt
  → resolve_trip_outlook_metrics() reicht Flag je metric_id durch
  → outlook_columns() trägt das Flag je Spalte
  → _merge_min_max_pairs() reicht das Feld zusätzlich für Spannenzellen durch
  → format_outlook_value() verzweigt: Flag gesetzt UND Metrik fähig → Wortskala/Symbol,
                                        sonst wie bisher (Rohzahl + Einheit)
  → build_outlook_row() speist alle vier Ausgaben unverändert strukturell
```

Gewitter bleibt **außerhalb** dieser Kette: `thunder_branch.py` baut die Gewitterspalte
seit #1848 A3 über vier separate Bauer, nicht über `cells`. Da Roh dort bereits das
Wort ist, gibt es dort nichts zu verzweigen — der Umschalter wird für `thunder` nicht
angeboten (s. Metrik-Matrix).

## Expected Behavior

- **Input:** Klick auf den Roh/Einfach-Umschalter je Metrik im Block „3-Tages-Vorschau"
  (Trip-Editor und Ortsvergleich-Editor); gespeichert in
  `display_config.outlook_metric_formats`
- **Output:** Die betroffene Spalte zeigt in allen vier Ausgabeorten (E-Mail HTML,
  E-Mail Klartext, E-Mail kompakt, Telegram) Wort/Symbol statt Zahl; für Metriken ohne
  Einfach-Form erscheint kein Umschalter
- **Side effects:** `outlook_metric_formats` wird beim Umschalten geschrieben
  (Read-Modify-Write, bestehende Felder in `display_config` bleiben erhalten); keine
  Wirkung auf E-Mail-/Telegram-/SMS-Kanal-Reiter (eigene, nicht geerbte Einstellung)

## Scope

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/types.ts` | MODIFY | `outlook_metric_formats?: Record<string, boolean>` |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | MODIFY | `noopOutlookMode` entfällt, echter Handler + echte `friendlyMap`, ausblick-eigene Fähigkeitsliste |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | State, Lade-/Speicherpfad, Durchreichung an beide Einbettungen (Wizard `:1406-1412`, Trip `:1793-1794`) |
| `src/app/metric_catalog.py` | MODIFY | Normalisierer für das neue Feld; Wortskalen-Fähigkeit je Metrik |
| `src/services/weather_metrics.py` | MODIFY | Wortskalen für Regenwahrscheinlichkeit und Sonnenstunden; Niederschlag auf Tagessumme neu geeicht |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | Flag durch `outlook_columns` **und** `_merge_min_max_pairs`; Einfach-Zweig in `format_outlook_value` |
| `src/output/renderers/email/outlook.py` | MODIFY | `build_outlook_row` reicht das Flag durch |
| `src/output/renderers/trip_report.py` | MODIFY | Auflösung des neuen Feldes, Durchreichung an die Renderer |
| `tests/tdd/test_outlook_darstellungsform.py` | CREATE | Kern-Tests: Umschaltung wirkt identisch in allen vier Ausgaben, Default „Roh", Fähigkeitsliste, Spannenzellen-Durchreichung |
| `frontend/e2e/epic-138-metriken-editor.spec.ts` | MODIFY | bestehender Test klickt nur „Roh" (blind für den Bug) — muss „Einfach" klicken und eine Inhaltsänderung prüfen |

### Estimated Changes

- Files: 10
- LoC: +280/-20 (grob, s. Estimated Scope)

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Trip ohne `outlook_metric_formats` WHEN der Ausblick gerendert
      wird THEN zeigt die Windrichtungs-Spalte weiterhin die Gradzahl (Default „Roh",
      kein stiller Rückfall auf `default_format_mode`)
- [ ] Test 2: GIVEN `outlook_metric_formats={"wind_direction": true}` WHEN alle vier
      Ausgabeorte gerendert werden THEN zeigen alle vier dieselbe Himmelsrichtung statt
      der Gradzahl
- [ ] Test 3: GIVEN eine Metrik ohne Einfach-Form (`temperature`) WHEN die
      Fähigkeitsliste für den Ausblick abgefragt wird THEN ist sie nicht enthalten,
      unabhängig vom Wert in `outlook_metric_formats`
- [ ] Test 4: GIVEN eine Spannenzelle (z. B. Temperatur-Spanne) mit gesetztem Flag für
      eine andere Metrik WHEN `_merge_min_max_pairs` läuft THEN bleibt das neue Feld im
      zusammengeführten Dict erhalten (Regressionsschutz gegen das explizit gelistete
      Schlüssel-Kopieren)
- [ ] Test 5: GIVEN Niederschlag-Tagessumme von 12 mm WHEN Einfach aktiv ist THEN lautet
      der Text „mäßig" (nicht die Stunden-Schwelle aus `format_precip_intensity`)

## Acceptance Criteria

### Block A — Speicherform und Default

- **AC-1:** Given ein Trip mit gesetztem `display_config.outlook_metrics` / When der
  Nutzer im Ausblick eine Metrik auf „Einfach" umschaltet / Then wird der Wert in einem
  neuen, parallelen Feld `display_config.outlook_metric_formats` gespeichert und
  `outlook_metrics` bleibt eine reine `list[str]` ohne Objektform.
  - Test: Unit gegen den Speicherpfad — nach dem Umschalten enthält `outlook_metrics`
    ausschließlich Strings, `outlook_metric_formats` ist ein separates `{id: bool}`.

- **AC-2:** Given ein Trip, bei dem `outlook_metric_formats` noch nie gesetzt wurde /
  When der Ausblick für `wind_direction`, `cloud_total` oder `sunshine` gerendert wird /
  Then erscheint die Rohzahl (Grad/Prozent/Stunden), **nicht** die Katalog-Default-Form
  (`symbol`/`scale`) — der Ausblick-Default ist unabhängig von `default_format_mode`
  hart „Roh".
  - Test: Unit am gerenderten Ergebnis für alle drei Metriken, gegen die bestehenden
    Paritäts-Fixtures aus `test_trip_outlook_parity.py` verglichen.

### Block B — Sichtbarkeit und Fähigkeitsliste

- **AC-3:** Given der Trip-Editor mit geöffnetem Abschnitt „3-Tages-Vorschau" / When die
  Reihenfolge-Liste angezeigt wird / Then erscheint der Roh/Einfach-Umschalter für
  `wind_direction`, `cloud_total/_low/_mid/_high`, `wind`, `gust`, `precipitation`,
  `rain_probability` und `sunshine`, aber **nicht** für `thunder`, `temperature`,
  `wind_chill`, `cape` oder `visibility`.
  - Test: Staging-E2E, Umschalter je Metrik-Zeile auszählen und gegen die Metrik-Matrix
    abgleichen.

- **AC-4:** Given die Fähigkeitsliste des Ausblicks / When sie im Frontend (Sichtbarkeit
  des Umschalters) und im Backend (Formatierungsverzweigung) ausgewertet wird / Then
  stammen beide aus derselben Quelle, sodass eine Metrik nie einen sichtbaren, aber
  wirkungslosen Umschalter zeigen kann.
  - Test: Mutations-Gegenprobe — eine Metrik künstlich nur auf einer Seite (Frontend
    oder Backend) als „fähig" markieren muss einen Test rot werden lassen.

### Block C — Wirkung in allen vier Ausgabeorten

- **AC-5:** Given `outlook_metric_formats` markiert `wind` als „Einfach" / When das
  Briefing für E-Mail (HTML), E-Mail (Klartext), E-Mail (kompakt) und Telegram gerendert
  wird / Then zeigen alle vier Ausgabeorte dieselbe Wortstufe (z. B. „sehr stark") statt
  der km/h-Zahl.
  - Test: Unit, ein gemeinsamer `stage["cells"]`-Wert wird an alle vier
    Renderfunktionen übergeben und deren Ausgabe verglichen.

- **AC-6:** Given eine Metrik ist auf „Einfach" umgeschaltet / When die E-Mail-HTML-Zelle
  gerendert wird / Then enthält sie ausschließlich den Wort-/Symboltext (kein
  zusätzlicher Ampelpunkt-Marker im escaped Text) — die Ampel-Information bleibt allein
  über die Hintergrundtönung der Zelle sichtbar.
  - Test: Unit, HTML-Ausgabe auf Abwesenheit eines Ampel-Icons/-Markers geprüft, während
    `_metric_column_bg` weiterhin ein Tönungs-Attribut liefert.

### Block D — Drei neue Wortskalen

- **AC-7:** Given eine Regenwahrscheinlichkeit von 80 % (Tages-Maximum) / When Einfach
  aktiv ist / Then lautet der Ausblick-Text „sehr wahrscheinlich"; bei 40 % lautet er
  „möglich".
  - Test: Unit, Grenzwerte 24/25, 49/50, 74/75 Prozent parametrisiert geprüft.

- **AC-8:** Given eine Sonnenstunden-Tagessumme von 1,5 Stunden / When Einfach aktiv ist
  / Then lautet der Ausblick-Text „trübe"; bei 9 Stunden lautet er „sonnig".
  - Test: Unit, Grenzwerte 1,9/2, 4,9/5, 7,9/8 Stunden parametrisiert geprüft.

- **AC-9:** Given eine Niederschlag-Tagessumme von 12 mm / When Einfach aktiv ist / Then
  lautet der Ausblick-Text „mäßig" — die Schwelle stammt aus der neuen Tagessummen-Skala
  (`<=0/<=5/<=20/>20 mm`), nicht aus den Stunden-Schwellen von
  `format_precip_intensity` (2/10 mm).
  - Test: Unit, ein Wert von 4 mm ergibt mit der alten Stunden-Skala „mäßig" (>2 mm),
    mit der neuen Tagesskala „leicht" (<=5 mm) — an diesem Wert scheitert der Test,
    falls die Stunden-Schwellen weiterverwendet werden. Zusätzlich 12 mm: alte Skala
    „stark" (>10 mm), neue Skala „mäßig" (<=20 mm).

### Block E — Wiederverwendung bestehender Helfer

- **AC-10:** Given Windrichtung, Bewölkung, Wind und Böen auf „Einfach" / When der
  Ausblick gerendert wird / Then stammt der Text aus `degrees_to_compass`,
  `cloud_emoji` bzw. `format_wind_strength` — keine neu geschriebene Parallel-Logik für
  diese vier Größen.
  - Test: AST-Wächter oder Aufruf-Nachweis, dass diese vier bestehenden Funktionen aus
    dem neuen Verzweigungscode heraus aufgerufen werden.

### Block F — Spannenzellen-Durchreichung

- **AC-11:** Given `_merge_min_max_pairs` führt Min/Max-Paare zu einer Spanne zusammen /
  When ein Eintrag ein gesetztes `outlook_metric_formats`-Flag trägt / Then bleibt dieses
  Flag im zusammengeführten Ergebnis-Dict erhalten, obwohl die Funktion nur explizit
  gelistete Schlüssel kopiert.
  - Test: Unit direkt gegen `_merge_min_max_pairs` mit einem synthetischen Flag-Feld,
    unabhängig davon, dass heute keine Spannenmetrik eine Einfach-Form hat.

### Block G — Rückwärtskompatibilität

- **AC-12:** Given ein bestehender Trip ohne `outlook_metric_formats` / When sein
  Briefing vor und nach dieser Änderung gerendert wird / Then ist die HTML- und
  Klartext-Ausgabe bytegenau identisch (`test_trip_outlook_parity.py`,
  `test_shared_outlook_renderer.py` bleiben grün).
  - Test: bestehende Paritäts-Suite unverändert ausgeführt, keine neue Fixture-Anpassung
    nötig.

- **AC-13:** Given der Go-API-Layer / When `outlook_metric_formats` erstmals von
  Frontend nach Backend übertragen wird / Then reist das Feld ohne Code-Änderung in
  `internal/model/trip.go` oder `internal/handler/config_merge.go` durch, weil
  `DisplayConfig` schemalos ist und `mergeConfigMap` nur die oberste Ebene mergt.
  - Test: Go-Test (Read-Modify-Write-Roundtrip) mit dem neuen Unterfeld, ohne
    Struct-Erweiterung.

### Block H — Blinder Bestandstest wird scharf

- **AC-14:** Given `frontend/e2e/epic-138-metriken-editor.spec.ts:159`
  („Roh/Einfach umschaltbar") / When der Test nach dieser Änderung läuft / Then klickt
  er tatsächlich „Einfach" und prüft eine sichtbare Textänderung in der Ausblick-Zelle
  — nicht nur den Zustand des Schalters.
  - Test: der modifizierte E2E-Test selbst; er muss vor dem Fix rot gewesen wäre
    (Nachweis über eine kurzzeitig zurückgenommene Implementierung im Review).

## Known Limitations

- **Gewitter bekommt keinen Umschalter.** Die Roh-Darstellung ist im Ausblick bereits
  das Stufenwort (`_fmt_thunder`); ein Einfach-Zweig hätte nichts zu tun. Zusätzlich
  umgeht die Gewitterspalte seit #1848 A3 den geteilten Zellenbau (`thunder_branch.py`,
  vier separate Bauer) — ein Flag müsste dort viermal ankommen, was genau die
  Doppelpflege wäre, die A3 beseitigt hat.
- **Temperatur und gefühlte Temperatur bekommen keinen Umschalter.** Es existiert
  produktweit keine Einfach-Form für diese Größen (kein `friendly_label`, kein
  `simplified`); der Ausblick zeigt sie korrekt unverändert als Spanne.
- **CAPE bekommt keinen Umschalter**, weil die Metrik im Ausblick strukturell nicht
  vorkommen kann (`selectable=False` ⇒ `available_aggregations('cape') == []`).
- **Visibility bekommt bewusst keine Einfach-Form** (Entscheidung aus #814 AC-5), das
  gilt unverändert auch im Ausblick.
- **Der No-Op im Ortsvergleichs-Übersichtsblock** (`WeatherMetricsTab.svelte:1168-1172`)
  ist strukturell verwandt, aber ein anderer Bug (dort werden weiterhin Katalog-Keys
  statt Kennungen verwendet) — nicht Teil dieser Spec, Sammel-Eintrag #1199.
- **Keine neue Kanal-Ebene für den Ausblick.** Die Einstellung ist global je Fläche
  (Trip bzw. Ortsvergleich), nicht je Kanal — ADR-0055 Punkt 2 bleibt in Kraft.
- **Keine SMS-Änderung**, da SMS keinen 3-Tages-Ausblick hat.
- **Kein Go-Eingriff** über die reine Durchreichung hinaus — kein neues Struct-Feld,
  keine neue Validierung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — wendet ADR-0050 Regel 5 an
- **Rationale:** ADR-0050 Regel 5 legt fest, dass „Reihenfolge und Rohwert-/
  Einfach-Format kanal-eigen bleiben"; diese Spec überträgt dieselbe Logik auf die
  Fläche „Ausblick" (eigenes Format, unabhängig vom E-Mail-Kanal), ohne die
  Metrik-Auswahl-Kaskade (ADR-0050 Regeln 1–4, #1848 A3) oder die Kanal-losigkeit des
  Ausblicks (ADR-0055 Punkt 2) zu berühren. Es gibt kein bestehendes ADR, das
  Roh/Einfach als eigene Entscheidung führt — diese Spec füllt eine Lücke in der
  bestehenden Linie, sie weicht von keiner dokumentierten Entscheidung ab.

## Changelog

- 2026-08-22: Initial spec created
