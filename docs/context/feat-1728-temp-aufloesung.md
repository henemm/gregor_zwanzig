# Context: feat-1728-temp-aufloesung (Scheibe 1 — Backend)

> Erhoben 2026-08-14 im Worktree `intake-1728`, Basis `e50cd575`.
> Alle Datei:Zeile-Belege sind an diesem Stand gemessen, nicht aus dem Issue übernommen.

## Request Summary

Die Katalog-Größen `temperature` und `wind_chill` werden in je zwei eigene, einzeln
wählbare Größen aufgelöst (Tages-Tief / Tages-Hoch) — nach dem Muster, mit dem #1484
`temperature_night` und #1660 A `wind_chill_night` eingeführt haben. Damit entfällt der
Aggregations-Mechanismus (`MetricConfig.aggregations`) als Bedienkonzept; die Vollmail-
Überblick-Pillen zeigen künftig unbedingt die Spanne. Scheibe 1 ist der Backend-Anteil;
der Wegfall des Bedienabschnitts „05 — Auswertungen" ist Scheibe 2.

## Verbindliche Vorgaben (nicht verhandelbar, nicht neu zu erfinden)

| Quelle | Festlegung |
|---|---|
| PO-Kommentar zu #1728 (2026-08-11) | Trennlinie ist der **Ausgabeort**, nicht der Kanal. Orte mit Stundenauflösung bekommen keine Wahl; Orte mit genau einem Tageswert bekommen eigene Zeilen. **Vollmail-Pillen: immer Spanne, kein Bedienelement.** |
| PO-Kommentar zu #1728 (2026-08-11) | `avg` fällt **ersatzlos** — es hat nach dem Umbau keinen Ausgabeort mehr (SMS kennt es ohnehin nicht, DEC-1). Beim Durchzählen der Ausgabeorte zu bestätigen. |
| PO-Entscheid Metrik-Kaskade (2026-08-11, #1719) | Grundauswahl = Maximum, Kanal darf nur abwählen. Jede neue Zeile ist je Kanal an/aus mit eigener Position. |
| PO 2026-07-28 (`reference_trip_temperature_is_specially_computed`) | Gefühlte und gemessene Temperatur verhalten sich **exakt gleich** — derselbe Algorithmus auf `wind_chill_c` statt `t2m_c`. Kein Nachbau, keine Sonderbehandlung. |
| `sms_daywindow_aggregation.md:255-256` | `K`/`D` bleiben auf die **Gehzeit** gefenstert (`_collect_hiking_window_dps()`), **nicht** auf das Tagesfenster 04–19 wie Wind/Regen/Gewitter. |
| `night_temp_evening_only.md` (PO-go 2026-07-23) | `N` = echte Nacht-Tiefsttemperatur am Schlafplatz, nur im Abendbriefing. Von dieser Scheibe unberührt, aber die Abgrenzung muss stehen bleiben. |

**🔴 Begriffsfalle:** „Tages-Tief" bedeutet im Trip je nach Ausgabestelle drei verschiedene
Dinge — kälteste Gehstunde · Tagesfenster-Minimum · Nachttemperatur am Ziel. Die Spec MUSS
für jede neue Größe benennen, welchen dieser Werte sie meint. Für die hier aufzulösenden
`K`/`D`/`FK`/`FD` ist es die **Gehzeit-Spanne** (Beleg oben).

## Die gemessene Lage: wer liest die Wahl überhaupt?

19 Ausgabeorte im Trip-Pfad geprüft. **Genau vier** lesen `MetricConfig.aggregations`:

| Ausgabeort | Datei:Zeile | Bewacht am Wirkort? |
|---|---|---|
| E-Mail HTML Überblick-Pillen | `email/html.py:1446` | **nein** |
| E-Mail Klartext Überblick-Pillen | `email/plain.py:204` | **nein** |
| E-Mail Kompaktform Überblick-Pillen | `email/compact.py:174` | **nein** |
| SMS-/Premium-SMS-Token-Gate `K`/`D`/`FK`/`FD` | `trip_report.py:416-437` (`_AGG_GATE_SYMBOLS`) | **ja** — `tests/tdd/test_sms_temp_aggregation_gate.py` misst `format_email().sms_text` |

**Alle übrigen Orte zeigen bereits heute unbedingt die Spanne** und entsprechen damit dem
Zielbild schon: Kurzzusammenfassung F2 (`compact_summary.py:319-320,358-359`), Telegram-rich
und Telegram-Kurzform (`narrow.py:436-539`, `_overview_line` bedient beide), 3-Tages-Ausblick
(`outlook.py:218-219,277-278,482-483`, feste Doppelspalte N/D), GLANCE/Timeline-Bot
(`trip_command_processor.py:844-845,990-991`), Vortag-Vergleichszeile (`day_comparison.py:403-404`).
Stundentabelle (`email/helpers.py:103`, `dp_to_row`) und Nacht-Block
(`email/helpers.py:157-230`) lesen die Wahl gar nicht — der Nacht-Block kollabiert über den
**Katalog**-Fixwert `metric_def.default_aggregations`, nicht über die Trip-Wahl.

**🔴 Der wichtigste Befund für die RED-Phase:** Die drei Pillen-Wirkorte sind unbewacht. Alle
vorhandenen Pillen-Tests (`test_trip_aggregation_pill_selection.py`,
`test_trip_aggregation_single_choice.py`, `test_trip_aggregation_invalid_choice_guard.py`,
`test_issue_912_pill_textformat.py`) rufen `build_metrics_summary_pills()`
(`email/helpers.py:1890`) **direkt** auf und laufen nie durch `render_html`/`render_plain`/
`render_compact` bzw. `format_email()`. Es gibt kein Golden-Fixture, das `aggregations`
variiert. Das ist exakt das Muster aus `reference_pruefort_muss_dem_wirkort_entsprechen` —
eine Änderung an den Pillen kann hier grün durchlaufen und trotzdem wirkungslos oder falsch sein.

## Related Files

### Kern der Änderung

| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py` | SSoT. `MetricDefinition` ab `:27`, Registry ab `:92`, **28 Einträge**. `temperature` `:94-115` (`summary_fields` `:100`, `default_aggregations` `:97`, `trip_default_rank=1` `:114`), `wind_chill` `:151-173` (`summary_fields` `:157`, **kein** `trip_default_rank`). Kürzel-Tabellen `SMS_MULTI_SYMBOLS_BY_METRIC` `:710-716`, `COMPACT_LABEL_EXCEPTIONS` `:722-737`. Hilfsfunktionen `get_summary_field()` `:796`, `available_aggregations()` `:830`, `pill_default_aggregations()` `:843`, `aggregation_label_de()` `:855` |
| `src/app/loader.py` | Ableitungsblöcke `:803-819` (`temperature_night`) und `:821-834` (`wind_chill_night`) — **das zu kopierende Muster**. `aggregations` lesen `:790`, `:863`, `:896` (Default je `["min","max"]`), schreiben `:157-160`, Legacy-Migration `:970-981`, `derived`-Filter beim Speichern `:1324-1325` / `:1529-1530` |
| `src/app/models.py` | `MetricConfig.aggregations` `:609-613` (Default `["min","max"]`), `MetricConfig.derived` `:637-639`, Kaskaden-Docstring `:826-846` |
| `src/output/renderers/trip_report.py` | `_AGG_GATE_SYMBOLS` `:416-437` — das SMS-Gate, das nach dem Umbau ersatzlos entfällt. Kollabierung von `dc.metrics` `:113-119`, `_dc_uncollapsed` |
| `src/output/renderers/sms_trip.py` | Tagesaggregat für `K`/`D`/`FK`/`FD` `:254-271`, `:455-460`. Re-Export der Kürzel-Tabellen |
| `src/output/tokens/builder.py` | Token-Zuordnung `:320-325`, `_wintersport()` `:264-289` (**`WC`**, Wert `day.wind_chill_c`, `PRIORITY["WC"]=2` `:52`, Positions-Slot `:109`) |
| `src/output/renderers/email/helpers.py` | Pillen-Auflösung `_AGGREGATION_PILL_METRICS` / `_resolve_pill_aggregations` / `_pill_for_metric` `:1408-1601`, `build_metrics_summary_pills()` `:1890`. Getrennte Fensterlogik `:1475-1556` (Temperatur/Gefühlt auf `_collect_hiking_window_dps()`) |
| `src/output/renderers/email/{html,plain,compact}.py` | Die drei Pillen-Wirkorte (`:1429-1450` / `:180-204` / `:173-181`) |
| `api/routers/config.py` | `GET /api/metrics` liefert `"aggregations"` je Metrik `:112-119` aus `available_aggregations()` — Feld verschwindet in Scheibe 3, muss in S1 aber konsistent bleiben |
| `src/output/renderers/trip_metric_ids.py` | `DEFAULT_TRIP_METRIC_IDS` `:29-34` (nach `trip_default_rank`), `resolve_trip_active_metrics()` `:37-57` |

### Mitzuziehen (beide Vorgänger fassten sie an)

`src/output/renderers/channel_layout.py` · `src/output/renderers/compact_summary.py` ·
`src/output/renderers/compare_hourly_metric_ids.py` · `src/output/renderers/narrow.py` ·
`src/services/segment_weather.py` · `src/services/preview_service.py` ·
`docs/reference/sms_format.md` · `docs/reference/sms_briefing_overview.md`

## Existing Patterns

**Das Ableitungs-Muster (`loader.py:803-834`) — wörtlich zu übernehmen:**
Fehlt beim Laden ein Eintrag für die neue Größe, wird er in-memory angehängt: `enabled` =
ODER über die Enabled-Zustände der Eltern-Einträge, `aggregations=[]`, `bucket="secondary"`,
`derived=True`. **Nichts wird zurückgeschrieben** — `save_location`/`save_trip` filtern
`derived`-Einträge wieder heraus. Abgeleitet wird **nur, wenn ein Eltern-Eintrag existiert**;
eine ganz leere `metrics`-Liste ist Altbestand Fall A und bleibt leer, sonst „erfindet" das
Laden Einträge und bricht die Roundtrip-Invarianz.

**Umfang der Vorgänger als Maßstab:** #1484 (`b09e1ec9`) 28 Dateien, #1660 A (`94a38b18`)
24 Dateien — je **eine** neue Größe. Diese Scheibe führt **vier** ein.

## Dependencies

- **Upstream:** `metric_catalog.py` (SSoT) → `loader.py`/`models.py` (Persistenz) → Renderer.
  `GET /api/metrics` speist das Frontend.
- **Downstream:** alle vier Kanäle, Vorschau-Endpunkte, Kompaktform, 3-Tages-Ausblick.
- **Go: nicht betroffen.** Kein Pendant zu `MetricConfig.aggregations` in `internal/`. Das
  gleichnamige `Trip.Aggregation` (`internal/model/trip.go:109`) ist fachlich etwas anderes
  (Etappen-Strategie `strategy`/`window_days`) und bleibt unangetastet.
- **Ortsvergleich: liest die Wahl gar nicht.** Weder `comparison.py` noch
  `compare_metric_catalog.py` haben einen Treffer auf `aggregations`. Compare backt die
  Auswertung stattdessen in den Namen („Temperatur max"/„Temperatur min") — siehe Risiko 2.

## Existing Specs

| Spec | Rolle |
|---|---|
| `docs/specs/modules/feat_1484_night_temp_metric.md` (approved) | Das Muster. 9 ACs, u.a. Roundtrip mit Bestands-JSON (AC-6/7), Zwei-Nutzer-Isolation (AC-9). Abgrenzung 1 dort: „`FN` bleibt an `wind_chill` — symmetrische Trennung wäre ein Folgeschnitt" |
| `docs/specs/modules/fix_1660a_temp_trennung.md` | Hebt jene Abgrenzung auf, führt `wind_chill_night` ein **und** das `_AGG_GATE_SYMBOLS`-Gate. 14 ACs. **Abgrenzung 1: `WC` bleibt bei `wind_chill` — Umhängen wäre Regression #1450.** ⚠️ Datei trägt `status: draft` und `- [ ] Approved`, obwohl der Code live ist (Nebenbefund, s.u.) |
| `docs/specs/modules/night_temp_evening_only.md` (PO-go 2026-07-23) | Definiert `N`. Bindend für die Abgrenzung „Nacht ≠ Tages-Tief" |
| `docs/specs/modules/sms_daywindow_aggregation.md` | Definiert das Tagesfenster 04–19 **und** dass `K`/`D` bewusst davon ausgenommen sind |
| `docs/specs/modules/fix_1719_s2_kaskade_verfeinerung.md` | Kaskaden-Modell. **AC-12** behandelt genau den Fall „abgeleitete Größe im Kanal-Schnitt" — Vorlage für die neuen Größen. Known Limitation 2 (`dataclasses.replace(dc, metrics=…)`) ist eine offene Wurzel, die auch hier lauert |
| `docs/reference/metric_output_matrix.md` | 744 Zeilen, 33 Ausgabeorte. **Erwähnt `temperature_night`/`wind_chill_night` mit keinem Wort** — taugt hier nicht als Vollständigkeitsnachweis |
| ADR-0055, ADR-0050, ADR-0043 | Ausblick-Metriken · Kaskade · Alarm-Achse |

## Risks & Considerations

1. **🔴 `WC` verliert seinen Eigentümer.** `WC` (Wintersport-Tageskennzahl, `day.wind_chill_c`,
   `builder.py:264-289`) hängt ausschließlich deshalb an `wind_chill`, damit dessen Abwahl es
   mit unterdrückt (`metric_catalog.py:684-690`, Fix #1450/Adversary-F001). Löst man
   `wind_chill` auf, steht `WC` wieder bei abgewählter Größe in der Kurznachricht — genau die
   Regression, die #1450 behoben hat. **Muss in der Spec entschieden werden, nicht im Code.**

2. **🔴 Zwei Auflösungen derselben Frage drohen.** Der Ortsvergleich führt „Temperatur max"/
   „Temperatur min" seit jeher als zwei Katalogeinträge (`compare_metric_catalog.py`). Nach der
   Trip/Compare-Teilungs-Vorgabe (CLAUDE.md) ist ein zweiter, paralleler Mechanismus ein
   Verstoß. Die Spec muss sagen, ob S1 auf den Compare-Katalog zuläuft oder ihn ausdrücklich
   als Folgeschnitt abgrenzt. Vgl. `reference_trip_hourly_table_uses_central_catalog`.

3. **🔴 Die drei Pillen-Wirkorte sind unbewacht** (s.o.). Jeder Nachweis in der RED-Phase muss
   über `format_email()` laufen, nicht über `build_metrics_summary_pills()`.

4. **Kollisionsgefahr mit #1720 Scheibe 2.** Die ist offen und fasst `email/compact.py` und
   `narrow.py` an — dieselben Dateien. Zusätzlich hat #1720 S1 den 3-Tages-Ausblick gerade erst
   metrik-gesteuert gemacht (ADR-0055); löst man `temperature` auf, ändert sich dort die
   Spaltenmenge implizit mit. Reihenfolge klären, bevor S1 startet.

5. **`dc.metrics` ist nach der E-Mail-Kollabierung nicht mehr die Grundauswahl**
   (`trip_report.py:113-119`, `reference_trip_renderers_see_collapsed_metrics`). „Nie
   eingestellt" und „bewusst leer" fallen dort zusammen. Die neuen Größen müssen aus
   `_dc_uncollapsed` aufgelöst werden — sonst wiederholt sich F001 aus #1720 S1.

6. **Bestand ist klein, der Default ist der Regelfall.** Nur **1 von 17** Trips hat überhaupt
   ein `aggregations`-Feld (`data/users/default/trips/gr221-mallorca.json` — dort
   `temperature: ["min","max","avg"]`, `wind_chill: ["min"]`). Für alle anderen greift der
   Default `["min","max"]`. Die Ableitungsregel muss also beide neuen Zeilen anschalten, und
   der eine abweichende Trip darf sein `wind_chill: ["min"]` nicht verlieren.

7. **`trip_default_rank` fehlt bei `wind_chill`.** `temperature` hat Rang 1, `wind_chill`,
   `temperature_night`, `wind_chill_night` haben keinen — sie sind wählbar, aber bei neuen
   Trips nicht vorbelegt. Die Spec muss den Rang der vier neuen Größen festlegen, sonst
   entscheidet ein Zufall, was ein neuer Trip zeigt.

8. **`avg` betrifft real genau einen Trip.** Der Wegfall ist PO-entschieden, aber
   `gr221-mallorca.json` nutzt ihn — beim Ableiten darf daraus kein Datenverlust und keine
   stille Verhaltensänderung ohne Nennung entstehen.

---

# Analysis (Phase 2)

## Type

**Feature** — neue Wählbarkeit, kein Fehlverhalten. Der PO-Kommentar beschreibt ein Zielbild,
keinen Defekt.

## Die zentrale Weichenstellung: `temperature`/`wind_chill` bleiben bestehen

Gemessen: Die Stundentabelle löst ihre Spalten ausschließlich über `dc.metrics` →
`get_metric(mc.metric_id).dp_field/col_key` auf (`email/helpers.py:103-124`, `dp_to_row()`).
Einen zweiten Mechanismus für Stundenwerte gibt es nicht. `COMPACT_LABEL_EXCEPTIONS`
(`metric_catalog.py:722-737`) begründet die Telegram-Ausnahme wörtlich damit, dass die Zelle
einen **Stundenwert** zeigt.

⇒ Die Elterngrößen bleiben als Katalogeinträge (Stundenwert + `summary_fields` als einzige
Quelle eines Tageswerts). Die vier neuen Größen tragen **keine eigenen `summary_fields`**,
sondern sind reine Sichtbarkeits-Gates — genau wie `temperature_night`
(`metric_catalog.py:139-150`, ebenfalls ohne `summary_fields`).

**Das entschärft zwei Risiken auf einen Schlag:** `WC` bleibt korrekt an `wind_chill.enabled`
gebunden (Risiko 1), und der 3-Tages-Ausblick bleibt unberührt, weil er über
`{metric_id, aggregation}`-Paare gegen die weiterhin existierende Eltern-ID auflöst
(Risiko 4, zweite Hälfte).

## 🔴 Blocker vor jeder Zeile Code: die Namensfrage

`temperature_min` / `temperature_max` sind **vergeben** — als `AlertMetric`-Enum
(`models.py:1123-1124`), als Alarm-Vokabular (`weather_change_detection.py:114-115`,
`alert_preset.py:17-18`) und als Korridor-Schlüssel (`email/html.py:605-606`). Fachlich
bezeichnen sie dort das **Tagesfenster 04–19**, während `K`/`D` bewusst auf die **Gehzeit**
gefenstert bleiben. Dieselben Namen zu verwenden würde die Begriffsfalle real machen — und
zwar still: kein Python-Fehler, getrennte Namensräume, Auffallen erst in der Alarm-/Korridor-
Logik.

Geprüft kollisionsfrei über `src/`, `frontend/src/`, `internal/`:
`temperature_day_low` · `temperature_day_high` · `wind_chill_day_low` · `wind_chill_day_high`.

## 🔴 Das Repo drückt dieselbe Sache bereits auf zwei Arten aus

| Ort | Mechanismus | Beleg |
|---|---|---|
| Ortsvergleich-Katalog | eigener Eintrag je Auswertung, `{key, metric_id, aggregation}` | `compare_metric_catalog.py:101-136` (26 Einträge) |
| 3-Tages-Ausblick | `outlook_metrics` als Liste von `{metric_id, aggregation}`, eine Spalte je Paar; Label wird bei Kollision automatisch um „Minimum"/„Maximum" ergänzt | `compare_outlook_metric_ids.py:105-141` |
| **#1728 (geplant)** | **eigene Katalog-ID je Auswertung** | neu |

Das wäre ein **drittes** Ausdrucksmittel. Es gibt bereits eine Übersetzungstabelle zwischen
zwei der Welten (`compare_metric_ids.py:67-74`, `RENDERER_TO_TRIP_METRIC_ID`) und eine dritte
Richtung (`FRONTEND_TO_RENDERER_METRIC_ID`, `:15-57`). Das ist eine echte Architekturfrage,
keine Geschmacksfrage — siehe offene Frage 4.

## Affected Files (Scheibe 1, Produktivcode)

| File | Change | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | 4 neue `MetricDefinition` (ohne `summary_fields`), `SMS_MULTI_SYMBOLS_BY_METRIC` umhängen: `temperature` → `("K",)`/`("D",)` auf die neuen IDs, `wind_chill` behält `("WC",)`. `trip_default_rank` festlegen. `WEATHER_TEMPLATES` (7× `temperature`, 4× `wind_chill`, `:926-970`) prüfen |
| `src/app/loader.py` | MODIFY | 2 neue Ableitungsblöcke nach Vorbild `:803-834` |
| `src/output/renderers/trip_report.py` | MODIFY | `_AGG_GATE_SYMBOLS` (`:416-437`) **entfällt** — Gating läuft künftig über `enabled` der neuen IDs |
| `src/output/renderers/sms_trip.py` | MODIFY | Token-Bindung an die neuen IDs |
| `src/output/renderers/email/{html,plain,compact}.py` | MODIFY | die drei Pillen-Wirkorte fest auf Spanne |
| `src/output/renderers/email/helpers.py` | MODIFY | `_resolve_pill_aggregations` / `_AGGREGATION_PILL_METRICS` |
| `src/output/renderers/channel_layout.py` | MODIFY | `METRIC_PRIORITY` (`:61-62`) um die neuen IDs |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | Stundenverlauf-Ausschluss (Muster #1660 A) |
| `src/output/renderers/narrow.py` | PRÜFEN | `:499-522`, `:749-758` nennen `temperature`/`wind_chill` literal — zeigen aber schon heute die Spanne, vermutlich unverändert |

**Nicht angefasst:** Go (`internal/`) · Ortsvergleich-Renderer · Alarm-Pfad · Stundentabelle ·
Nacht-Block · 3-Tages-Ausblick.

## Scope Assessment

- Produktivdateien: **9**, davon 2 tragend (`metric_catalog.py`, `loader.py`)
- Produktiv-LoC: **~165–200** (Budget 250) — passt knapp
- Test-LoC: **realistisch > 500** (Budget 500) ⇒ `loc_limit_override` wird gebraucht
- Risiko: **HIGH** (SSoT, Persistenz, vier Kanäle)

**Alternativer Schnitt, falls es eng wird:** entlang „gemessen zuerst, gefühlt nachgezogen" —
exakt das bewährte Muster #1484 → #1660 A. S1a nur `temperature_day_low/high` inkl.
Gate-Umbau und Pillen-Fix; S1b dieselben zwei Mechanismen für `wind_chill`. Hält jede
Teilscheibe unter ~150 Produktiv-LoC.

## PO-Entscheide (2026-08-14, beantwortet — verbindlich für die Spec)

- [x] **E1 — Bestand:** Der eine Trip mit `temperature: ["min","max","avg"]`
  (`gr221-mallorca.json`) bekommt nach dem Umbau Tages-Tief **und** Tages-Hoch. **PO: „ja".**
  Der Mittelwert entfällt ersatzlos (bereits im Issue-Kommentar entschieden).
- [x] **E2 — Vorbelegung:** Bei einem neuen Trip sind beide neuen Zeilen **von Anfang an an**.
  **PO: „an".** ⇒ `trip_default_rank` muss für `temperature_day_low`/`temperature_day_high`
  gesetzt werden (heute trägt nur `temperature` Rang 1); für die gefühlte Seite analog zur
  heutigen Lage von `wind_chill` (kein Rang) zu behandeln — d.h. sie erscheinen wählbar, aber
  die Vorbelegung folgt der Elterngröße.
- [x] **E3 — `WC`:** bleibt an „Gefühlte Temperatur" (`wind_chill`) gebunden. **PO: „WC soll
  bleiben".** Kein Umhängen an `wind_chill_day_high`. Hält Regression #1450; durch die
  Entscheidung „Elterngröße bleibt bestehen" ohnehin baulich getragen.
- [x] **E4 — Gemeinsames Fundament:** **PO: „gemeinsames fundament"**, mit der Rückfrage nach
  einem guten Grund für die Doppel-Komplexität. Gemessene Antwort: **es gibt keinen.**
  `resolve_trip_outlook_metrics()` (`compare_outlook_metric_ids.py:78-102`) bezeichnet sich im
  eigenen Docstring als *„Nachbildung von `UnifiedWeatherDisplayConfig._clip_to_global_maximum()`
  für das `{metric_id, aggregation}`-Vokabular"* — dieselbe Kaskadenregel doppelt gepflegt,
  bereits einmal auffällig geworden (Adversary-F001 in #1720 S1).

  **Das Fundament sind die eigenen Katalog-Kennungen, nicht die Paare.** Begründung:
  1. Kanal-An/Aus, Reihenfolge, SMS-Kürzel und Schwellwerte sind sämtlich über `metric_id`
     verdrahtet.
  2. Das Paar-Vokabular passte dort nicht hinein und brauchte eine **eigene parallele Liste**
     (`outlook_metrics`, `models.py:812`).
  3. Selbst dort wird es zum Verschneiden mit der Hauptauswahl wieder auf reine Kennungen
     reduziert (`:101`) — „Temperatur Minimum" ist im Ausblick wählbar, in der Grundauswahl
     aber nur „Temperatur" als Ganzes. **Das ist derselbe Zwei-Ebenen-Widerspruch, den #1719
     abgeschafft hat, an einer anderen Fläche.**
  4. `temperature_night` lässt sich als Paar gar nicht ausdrücken (Wert kommt aus
     `day_window.night_temp_min_c`, nicht aus `summary_fields`).

  **Konsequenz für den Zuschnitt:** Scheibe 1 baut auf den eigenen Kennungen — Richtung
  unverändert. Die Umstellung von Ortsvergleich-Katalog und 3-Tages-Ausblick auf dieselben
  Kennungen ist Arbeit an fremden Flächen und wird als **eigenes Issue** mit konkretem
  Zuschnitt und Rückverweis auf #1728 angelegt, nicht als vage Notiz in der Spec vergraben.

## Nebenbefunde (nicht Teil dieser Scheibe)

- `fix_1660a_temp_trennung.md` trägt `status: draft` / `- [ ] Approved`, obwohl der Code seit
  2026-08-10 in Produktion ist. Kandidat für #1199.
- `MultiSymbolMetricRow.svelte:3` behauptet noch `wind_chill: FN/FK/FD/WC` — `FN` liegt seit
  #1660 A bei `wind_chill_night`. Ebenso fehlt `wind_chill_night` eine Kürzel-Zeile im Editor
  (`WeatherMetricsTab.svelte:1693-1712` führt nur `temperature`, `temperature_night`,
  `wind_chill`). Gehört fachlich in Scheibe 2.
- `metric_output_matrix.md` kennt die beiden Nacht-Größen nicht (s.o.).
