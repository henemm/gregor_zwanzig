# Context: fix-1488-gewitterstufen

Issue: [#1488](https://github.com/henemm/gregor_zwanzig/issues/1488) — Gewitterstufen im Frontend:
drei Wortkopien, Alarm-Editor um eine Stufe verschoben — EINE geteilte Quelle für Trip, Vergleich
und Alarme. Epic: [#1419](https://github.com/henemm/gregor_zwanzig/issues/1419).
Track: **Full Process** (Intake-Score 5: Scope High · Blast Radius High · Unsicherheit Medium).

## Request Summary

Die Gewitterstufen-Skala hat seit #1474 vier Stufen (kein/leicht/mittel/hoch). Das Frontend
führt an mehreren Stellen eigene Wortkopien, die diesen Umbau nicht mitgemacht haben. Die
schwerwiegendste beschriftet eine **Alarm**-Einstellung falsch. Ziel laut PO: eine geteilte
Wortquelle für Trip, Ortsvergleich und Alarme — plus (Umfangserweiterung 2026-08-04) die
englisch gebliebene Mail-Textfassung.

## 🔴🔴 Der gemessene Kern: die Fläche ist falsch beschriftet UND wirkungslos

Das Issue beschreibt „um eine Stufe verschoben". Gemessen ist es etwas anderes — und schlimmer.

### Befund 1: Die Gewitter-Alarmschwelle wird nie ausgewertet

Der einzige produktive Auslösepfad ist `TripAlertService.check_and_send_alerts()`
(`src/services/trip_alert.py:447`) → `_select_change_detector()` (`trip_alert.py:366-381`).
Diese Methode baut die `AlertEvaluationConfig` **ausschließlich** aus
`trip.display_config.metric_alert_levels` — `trip.alert_rules` wird dort **gar nicht gelesen**.
Für `AlertMetric.THUNDER_LEVEL` erzeugt `_PRESET_TABLE` (`src/services/alert_preset.py:50`)
dabei **immer** `kind=AlertRuleKind.DELTA`, nie `ABSOLUTE` — unabhängig von der
Empfindlichkeitsstufe.

`_detect_absolute_changes()` mit dem `>=`-Stufenvergleich
(`weather_change_detection.py:808-821`) läuft für andere Metriken (z. B. `WIND_GUST`)
produktiv durch, wird für **Gewitter aber nie mit einer Regel gefüttert**.

Wofür `trip.alert_rules` tatsächlich noch dient (alle 7 Fundstellen geprüft): Kanal-Routing
(`_effective_alert_channels`, `trip_alert.py:1547-1595`) und als Prüf-Gate
„wird der Trip überhaupt gecheckt" (`has_active_rules`, `trip_alert.py:444-447`).
Positivkontrolle für den lebenden Pfad: `tests/tdd/test_alert_channel_threshold.py:113`
nutzt `metric_alert_levels`, nicht `alert_rules`.

### Befund 2: Das Produkt hat die Entscheidung längst getroffen — die Sperre hat ein Loch

`frontend/src/lib/components/shared/alarme-tab/alertRuleDefaults.ts:45-50` führt
`DELTA_ONLY_METRICS` — und `'thunder_level'` **steht bereits darin**. Die Guard greift aber
nur im Zweig `mode === 'both'` (Z.75-80, Rückfall auf eine reine Delta-Regel), **nicht** im
Zweig `mode === 'absolute'` (Z.61-66). `ModeCard.svelte` zeigt zudem für jede Metrik alle drei
Modus-Karten ohne Sperre.

Ein Nutzer kann also „Absolut" + „MITTEL"/„HOCH" wählen; die Regel wird über Go
(`SyncAlertRules`) klaglos persistiert und beeinflusst Kanal-Routing und Prüf-Gate — aber
**nie** die Schwellenauswertung. Die falsche Beschriftung ist damit das sichtbare Symptom
eines Lecks in einer bereits bestehenden Absicht, nicht eine fehlende Beschriftung.

### Befund 3: Wäre sie wirksam, wäre sie zusätzlich falsch beschriftet

**Was das Backend tut** (`src/services/weather_change_detection.py:808-821`): Eine Alarm-Regel
für `thunder_level` mit `comparison="above"` löst aus, sobald
`thunder_ordinal(aktuelle_stufe) >= rule.threshold`. Die Ordinalskala ist seit #1474
`NONE=0 · LOW=1 · MED=2 · HIGH=3` (`src/app/thunder_scale.py:42-57`).

**Was die Oberfläche anbietet** (`frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte:178-179`):

```svelte
<option value={1.0}>MITTEL</option>
<option value={2.0}>HOCH</option>
```

| Nutzer wählt | gespeichert | löst tatsächlich aus ab | Oberfläche behauptet |
|---|---|---|---|
| „MITTEL" | 1.0 | **leicht** | mittel |
| „HOCH" | 2.0 | **mittel** | hoch |
| *(nicht wählbar)* | 3.0 | hoch | — |

Beide angebotenen Stufen alarmieren also **eine Stufe früher** als beschriftet, und die
tatsächlich höchste Gefahrenstufe lässt sich überhaupt nicht einstellen. Die
View-Mode-Beschriftung derselben Fläche (`alertMetricLabels.ts:58-62`,
`thunderLevelLabel()`) hat denselben Versatz und wirft zusätzlich 2.0 und 3.0 zusammen
(`>= 2.0 → 'HOCH'`).

**Ein Kommentar im Backend behauptet weiterhin die alte Welt:**
`weather_change_detection.py:814-816` („threshold=1.0 must match MED=1") und
`alert_preset.py:75-76` beschreiben die Drei-Stufen-Skala von vor #1474. Sie sind die
wahrscheinliche Ursache dafür, dass die Frontend-Beschriftung nie nachgezogen wurde.

## Related Files

### Frontend — die vier Wortquellen

| Datei:Zeile | Zustand | Erreichbar über |
|---|---|---|
| `lib/components/alert-rules-editor/AlertRuleRow.svelte:178-179` | 🔴 **falsch, 2 von 4 Stufen** (Edit-Mode-Auswahl) | `/trips/new` → Alarm-Regeln |
| `lib/utils/alertMetricLabels.ts:58-62` `thunderLevelLabel()` | 🔴 **falsch, 3 Stufen, Versatz** (View-Mode-Text) | dieselbe Fläche |
| `lib/components/shared/WeatherMetricsTab.svelte:1629-1634` | ✅ inhaltlich richtig (`leicht 1.0 / mittel 2.0 / hoch 3.0`), aber weiterhin **lokale** Liste | `/trips/{id}?tab=weather`, `/compare/{id}?tab=wetter-metriken` |
| `lib/components/shared/corridor-editor/CorridorEditor.svelte:374,386` (+ `CorridorEditorMobile.svelte:245,361`) | ✅ **Vorbild** — rendert `ordinalLabels` live aus dem Backend-Katalog | Wertebereiche-Tab, beide Kontexte |

Weitere Fundstellen ohne Nutzerschaden: `corridorEditorState.ts:407` `ORDINAL_ENUM`
(internes Enum, positionell benutzt — driftet still), `TablePreview.svelte:36-39`
(kosmetische Mockdaten), `alertChannelState.ts:97-100` (**nicht** thunder-spezifisch,
allgemeine Kanal-Dringlichkeit — kein Kandidat).

**Tot / nicht gemountet:** `trip-detail/AlertsPreviewCard.svelte:29` (kein Importer),
`edit/TripEditView.svelte` (kein Importer außer einem Test) — beide konsumieren
`thunderLevelLabel()`, sind aber im Browser nicht erreichbar.

### Backend — die kanonischen Quellen

| Datei:Zeile | Inhalt |
|---|---|
| `src/app/models.py:35-44` | `ThunderLevel` — NONE/LOW/MED/HIGH |
| `src/app/thunder_scale.py:42-57`, `:65-91` | `thunder_ordinal()` und `thunder_label_value()` — bewusst zwei Funktionen (ADR-0025 Entscheidung 3) |
| `src/output/metric_format.py:246-251` | `THUNDER_LABEL_DE` — kein/leicht/mittel/hoch |
| `src/output/metric_format.py:257-262` | `_THUNDER_AMPEL_BAND` — grün/gelb/orange/rot |
| `src/output/renderers/compare_metric_catalog.py:105-115` | `ordinalLabels: ["kein","leicht","mittel","hoch"]`, ausgeliefert über `GET /api/compare/metrics` (`api/routers/compare.py:11-22`, **kein** `context`-Parameter) |
| `src/services/alert_preset.py:102-106` | `ORDINAL_LEVEL_BOUNDS` — Empfindlichkeitsstufen (andere Achse, s. u.) |

### Backend — die englisch gebliebene Mail-Textfassung

`src/output/renderers/email/helpers.py:872-902` `_THUNDER_MAP` (Zeilen gegenüber dem
Issue-Text verschoben):

| Stufe | `plain` heute | kanonisch (`THUNDER_LABEL_DE`) |
|---|---|---|
| NONE | `⚡–` | kein |
| LOW | `⚡leicht` | ✅ |
| MED | **`⚡MED`** | mittel |
| HIGH | **`⚡HIGH`** | hoch |

Konsumenten von `thunder_plain`, alle **nutzersichtbar**: `email/outlook.py:386`
(Mailtext-Trendzeile), `email/compact.py:106` (Kompakt-Textfassung), `narrow.py:605`
(schmale Ausgabe / Telegram).
Die Schlüssel `word` und `sms` (`"MED"`/`"GEW-MED"`) haben **keinen** Produktivkonsumenten
(einziger Treffer: `tests/tdd/test_thunder_low_output_channels.py:82`);
`sq_color`/`word_color` sind tote Schlüssel.
Der bereits richtige HTML-Pfad zum Abgleich: `email/helpers.py:621-643` `ampel_dot()` über
`thunder_ampel_band()`.

## Existing Patterns

**Vorbild 1 — Katalog live gegenlesen:**
`frontend/src/lib/components/shared/corridor-editor/__tests__/compareMetricCatalogParity.test.ts:38-51`
ruft den Backend-Katalog per `execFileSync('uv', ['run','python3', …])` auf, statt eine
Erwartungsliste abzuschreiben. Der CI-Job `frontend-test` hat `uv` dafür bereits eingerichtet.

**Vorbild 2 — Produktivquelle statt Kopie prüfen:**
`frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts:49-70`
liest das `levels={[...]}`-Array real aus `WeatherMetricsTab.svelte`. Es entstand für **exakt
denselben Bugtyp** (Rest der alten Drei-Stufen-Skala) — in `AlertRuleRow.svelte` wurde er nie
nachgezogen.

**Vorbild 3 — Katalogdurchreichung in beide Kontexte:**
`compareMetricCatalogLoader.ts:47-74` (`buildCompareMetricDefs`) und `:131-166`
(`buildRouteMetricDefsFromCatalog`) liefern die vier `ordinalLabels` bereits **für beide**
Kontexte korrekt durch. Die im Issue vermutete „Weiche, die den Trip-Kontext ausschließt"
existiert dort **nicht** — sie betrifft den Wertebereiche-Tab, der ohnehin schon richtig ist.
Der Alarm-Editor zieht seine Wörter schlicht gar nicht aus diesem Loader.

## Dependencies

- **Upstream:** `ThunderLevel` → `thunder_scale.py` → `metric_format.py` /
  `compare_metric_catalog.py` → `GET /api/compare/metrics` → `compareMetricCatalogLoader.ts`
- **Downstream:** Alarm-Auswertung `_detect_absolute_changes`
  (`weather_change_detection.py:788-826`); Mail-/Telegram-Renderer (`outlook.py`,
  `compact.py`, `narrow.py`) — Änderungen dort ziehen das **Renderer-Commit-Gate** und die
  Pflicht-Mail-Validatoren nach sich.

## Zwei Achsen, die nicht verwechselt werden dürfen

| Achse | Wo eingestellt | Was sie tut | Quelle |
|---|---|---|---|
| **Alarm-Regel-Schwelle** (`AlertRule.threshold`, `comparison="above"`) | `/trips/new` → Alarm-Regeln (`AlertRuleRow`) | absoluter Vergleich `ordinal >= threshold` | `weather_change_detection.py:808-821` |
| **Empfindlichkeitsstufe** (entspannt/standard/sensibel) | `?tab=alarme` (`AlarmeTab` → `AlertMetricLevelRow`) | Sprung-Alarm gegen den letzten Briefing-Stand | `alert_preset.py:102-106`, ADR-0043 |
| **Erwähnungs-/SMS-Schwelle** | `?tab=weather` (`WeatherMetricsTab`) | ab wann erwähnen | `WeatherMetricsTab.svelte:1629` |
| **Wertebereich** (`corridors[].notify`) | Wertebereiche-Tab | **keine Alarmwirkung mehr** (ADR-0043) | Katalog `ordinalLabels` |

ADR-0043 hat dem Wertebereich die Alarmwirkung entzogen und die Empfindlichkeitsstufe zum
einzigen Alarm-Regler erklärt. **Die Messung zeigt: die Alarm-Regel-Schwelle für Gewitter ist
ebenfalls entwertet** (Befund 1) — nur hat niemand die Bedienfläche dazu entfernt.

### Zwei Alarm-Systeme nebeneinander

| System | Route | Komponente | Zeigt für Gewitter | Wirkt? |
|---|---|---|---|---|
| **Empfindlichkeitsstufe** | `/trips/{id}?tab=alarme`, `/compare/{id}?tab=alarme` | `AlarmeTab` → `AlertMetricLevelRow` | `off / entspannt / standard / sensibel` (generisch für alle Metriken), Schwelle als Zahl | ✅ **ja** — der einzige wirksame Regler |
| **Alarm-Regeln (Alt)** | nur `/trips/new` | `AlertRulesEditor` → `AlertRuleRow` | Auswahl `MITTEL` (1.0) / `HOCH` (2.0) | 🔴 **nein** (Befund 1) |

Ein Nutzer stellt bei der Trip-Anlage also etwas ein, das er später an derselben Stelle nie
wiederfindet **und** das nie etwas auslöst.

## Existing Specs & ADRs

- `docs/context/feat-1480-thunder-scale-guard.md` — Vollmessung des Bestands: **15 lokale
  Kopien im Produktivcode, 13 Test-Doubles (7 veraltet, 1 rot)**. Die dortige Empfehlung
  „Vorsanierung reißt das LoC-Limit" gilt für #1488 unverändert ⇒ Scheiben.
- ADR-0043 — Empfindlichkeitsstufe als einziger Alarm-Regler
- ADR-0025 — zwei getrennte Thunder-Skalen (Ordnung vs. Renderwert)
- ADR-0011 — ein Backend-Renderer für Alarme
- `docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md` — der Vorgänger, der den
  Trip-Teil gerichtet hat

## Test-Doubles, die beim Fix mitgezogen werden müssen

`ordinalLabels: ['kein','leicht','mittel','hoch']` hartkodiert in 5 Dateien / 6 Vorkommen:
`corridorEditorState.test.ts:52`, `compareMetricCatalogParity.test.ts:71` und `:126`,
`routeCorridorPoolCatalogExpansion.test.ts:78`,
`alarme_tab_alert_metrics_from_catalog.test.ts:42`, `compareMetricSelection.test.ts:45`.

Zusätzlich: `frontend/src/lib/utils/alertMetricLabels.test.ts:22-30` zementiert die falsche
Beschriftung (`thunderLevelLabel(2.0) === 'HOCH'`), und
`tests/tdd/test_compare_metric_catalog_endpoint.py:220-228` erwartet noch drei Labels — steht
auf `.github/ci_tdd_excludes.txt:24` und läuft deshalb nicht auf CI.

## Testwege für den geforderten Browser-Nachweis

- Playwright-Specs: `frontend/e2e/*.spec.ts`, Login über Setup-Projekt
  (`global.setup.ts:22-51`, `storageState` in `playwright/.auth/admin.json`)
- CI-Job `e2e` fährt gegen einen **lokal gebauten Stack** (`localhost:4173`), nicht gegen
  Staging; Staging-Specs tragen `.staging.spec.ts`
- **Positivliste `.github/ci_e2e_specs.txt`** (45 Zeilen): ein neuer Spec läuft nur auf CI,
  wenn er dort eingetragen ist; `E2E_MIN_SPECS: 45` prüft die Zeilenzahl **exakt**, geprüft
  von `tests/unit/test_e2e_positivliste_ratschen_bindung.py`
- ⚠️ `frontend/e2e/alert-rules-editor.spec.ts` navigiert nach `/trips/{id}/edit` — seit #616
  nur noch ein Redirect auf eine nicht mehr geroutete Komponente. **Nicht als Vorlage nehmen.**

## Risks & Considerations

1. 🔴 **Umdeutung bestehender Regeln.** Wird die Beschriftung richtiggestellt, ohne die
   gespeicherten Werte anzufassen, ändert sich für Bestandsnutzer nichts an der Wirkung —
   ihre Regel alarmiert weiter ab „leicht", heißt aber jetzt auch so. Wird stattdessen der
   Wert umgerechnet, ändert sich die Alarmhäufigkeit still. Beides ist vertretbar, aber es
   ist eine **PO-Entscheidung**, keine Implementierungsdetailfrage.
2. 🔴 **Mail-Renderer-Änderung zieht Pflicht-Validatoren.** `_THUNDER_MAP` liegt in
   `email/helpers.py` ⇒ Renderer-Commit-Gate, Modus-Matrix-Test und
   `briefing_mail_validator.py` gegen echt zugestellte Staging-Mail.
3. **LoC-Limit 250.** Frontend-Sanierung + Mail-Textfassung + Test-Nachzug + Browser-Spec
   überschreiten das Budget deutlich ⇒ Scheiben (Vorschlag in der Analyse).
4. **Der Nachweis kostet mehr als der Fix.** Die reine Korrektur ist zweistellig in Zeilen;
   Browser-Spec, Positivlisten-Ratsche und Test-Nachzug sind der Hauptteil.
5. **Nicht in diesen Zug gehört** der Wächter gegen neue Kopien — das ist #1480, das laut
   PO-Entscheidung **nach** #1488 kommt.

## Backend-Tests und stale Kommentare, die mitgezogen werden müssen

Alarm-Auslösung für `thunder_level` (`tests/unit/test_issue_222_alert_rules_detection.py`):

| Test:Zeile | threshold | Zustand |
|---|---|---|
| `test_ac9_thunder_level_med_at_threshold_fires:273-292` | 1.0 | 🔴 Docstring behauptet „MED (ordinal=1)"; die Zusicherung **unterscheidet nicht** zwischen „ab leicht" und „ab mittel" — bleibt bei jeder Lesart grün. Muss inhaltlich ergänzt werden (Fall `NONE→LOW` fehlt), nicht nur umbenannt |
| `test_ac9_thunder_level_high_with_threshold_2_fires:294-319` | 3.0 | ✅ für #1474 nachgezogen (Testname irreführend, Wert ist 3.0) |
| `test_ac1_absolute_thunder_high_fires_once:369-383` | 2.0 | ✅ konsistent, prüft die MED-Grenze aber nicht |
| `test_ac2_absolute_thunder_below_threshold_no_fire:385-399` | 3.0 | ✅ für #1474 nachgezogen |

Stale Kommentare mit der alten Drei-Stufen-Skala (vollständiger Lauf über `src/ api/ tests/`):
`weather_change_detection.py:814-816`, `alert_preset.py:75-77` (Produktivcode);
`tests/tdd/test_alert_sensitivity_levels.py:6`, `tests/tdd/test_day_comparison_service.py:8`
(widerspricht der korrigierten Stelle `:178-179` in derselben Datei),
`tests/integration/test_friendly_format_email_and_alerts.py:717`.

**Kein serverseitiger Wertebereich für `threshold`:** `src/app/models.py:1136-1152`
(reines Dataclass, keine Constraints) und `internal/model/trip.go:56-67` (kein Tag);
`validateTrip()` (`internal/handler/trip.go:89-107`) prüft Alarm-Regeln für **keine** Metrik.
`3.0` wäre über die API persistierbar — nur das Bedienelement bietet es nicht an.

## DOM-Testbarkeit (für die Browser-Nachweise)

| Fläche | Locator | Zustand |
|---|---|---|
| Empfindlichkeitsstufe | `alert-metric-row-{metric}`, `alert-level-{metric}-{stufe}`, `alert-threshold-{metric}` | ✅ vollständig |
| SMS-Schwelle Gewitter | `threshold-metric-row-thunder`, `threshold-level-thunder-{leicht\|mittel\|hoch}` | ✅ Stufenwort steht im Button-Text |
| Alarm-Regel-Auswahl (Alt) | `alert-rule-threshold` (Edit-Modus) | ✅ Auswahl adressierbar; View-Modus hat **kein** eigenes testid, nur `.threshold` innerhalb `alert-rule-row` |

Kein Spec auf der Positivliste `.github/ci_e2e_specs.txt` fasst heute die Gewitter-Stufennamen
an. `frontend/e2e/alert-rules-editor.spec.ts` (AC-10) prüft genau diese Auswahl — zielt aber auf
die seit #616 nicht mehr geroutete `/trips/[id]/edit` und steht folgerichtig nicht auf der Liste.
Staging-Specs (`.staging.spec.ts`) sind von der Positivliste ausgenommen; Basis-URL über
`GZ_SVELTE_BASE`, Zugänge über `GZ_VALIDATOR_*` (nginx) und `GZ_AUTH_*` (App).

## Open Questions

- [ ] **PO-Entscheid: beschriften oder entfernen?** Messung sagt: die Fläche wirkt nicht, und
      `DELTA_ONLY_METRICS` enthält `thunder_level` bereits. Empfehlung: Absolut-Modus für
      Gewitter konsequent sperren (Loch schließen) statt zwei falsche Wörter zu korrigieren.
- [ ] **PO: Was passiert mit bereits gespeicherten wirkungslosen Regeln?** Still liegenlassen
      (sie tun ohnehin nichts, beeinflussen aber Kanal-Routing und Prüf-Gate) oder beim Laden
      auf eine Delta-Regel normalisieren?
- [ ] **PO: Zuschnitt** — Frontend-Sanierung und Mail-Textfassung als zwei Scheiben?
## ✅ Erreichbarkeit — Laufzeit-Nachweis (Playwright/Chromium gegen Staging, 2026-08-16)

Kein Code-Scan, sondern real durchgeklickt auf `https://staging.gregor20.henemm.com`
(Basic-Auth `GZ_VALIDATOR_*` + App-Login; **nichts angelegt**, Trip-Zahl vor/nach unverändert 4,
einziger Netzaufruf mit Seiteneffekt war der zustandslose `POST /api/gpx/parse`).

| Geprüft | Ergebnis |
|---|---|
| **Positivkontrolle** — Namensfeld auf `/trips/new` (`trip-new-name-input-desktop`) | ✅ gefunden und befüllbar ⇒ Suchweg funktioniert |
| `/trips/new` → Alarm-Regeln → Metrik „Gewitter" → Schwellwert-Auswahl | 🔴 **bestätigt**: Optionstexte wörtlich `["MITTEL","HOCH"]`, Werte `["1","2"]` |
| Bestehender Trip `?tab=alarme`, Metrik Gewitter | Sensitivitäts-Buttons (Aus/Entspannt/Standard/Sensibel) + Schwellwert-Anzeige **`Δ ≥ 1`**; Volltextsuche nach „MITTEL"/„HOCH" auf der Seite: **kein Treffer** |
| `/trips/{id}/edit` | leitet real auf `/trips/{id}` um ⇒ Alt-Route bestätigt tot |

**Nicht geprüft (Lücken):** mobile Ansicht; Ortsvergleich `/compare/…?tab=alarme` — Code deutet
auf denselben geteilten `AlarmeTab`-Pfad wie bestehende Trips (also ebenfalls kein MITTEL/HOCH),
das ist aber Lektüre, kein Laufzeit-Nachweis.

**Nebenbefund** (nicht Teil dieses Tickets): Die Schwellwert-Anzeige zeigt für Gewitter `Δ ≥ 1`
— konsistent damit, dass `_PRESET_TABLE` für `THUNDER_LEVEL` eine Delta-Regel erzeugt, aber
erklärungsbedürftig für den Nutzer. Kandidat für den Sammel-Eintrag #1199.
