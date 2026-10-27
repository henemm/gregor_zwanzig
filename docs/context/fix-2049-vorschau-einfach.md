# Context: fix-2049-vorschau-einfach

Issue: [#2049](https://github.com/henemm/gregor_zwanzig/issues/2049) — „E-Mail Trip 3-Tages-Vorschau: 'Einfach' nicht waehlbar"
Milestone: Tour KHW 2026-08 · priority:high · type:bug · session:metrikauswahl

## Request Summary

Im Trip-Editor zeigt der Block **3-Tages-Vorschau** je Metrik einen Roh/Einfach-Umschalter.
Ein Klick auf „Einfach" bewirkt nichts. Gefordert ist, dass die Umschaltung dort **genauso
bedienbar** ist wie in den Kanal-Tabs (E-Mail/Telegram/SMS) — mit **eigener** Einstellung
fuer die Vorschau, **nicht** als geerbter Wert aus dem E-Mail-Kanal (PO-Klarstellung
2026-08-22: „In meiner Formulierung ging es um das Frontend im Backend. Nicht um die E-Mail.").

Abgrenzung: #2029 betrifft die Metrik-**Auswahl** (welche Groessen erscheinen) und ist mit
#1848 A3 bereits erledigt. #2049 betrifft die Darstellungs-**Umschaltung** (Roh oder Einfach
je Groesse). Zwei verschiedene Flaechen — Aussagen zur einen gelten nicht fuer die andere.

## Der Defekt (verifiziert)

`frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte`

```ts
// Z. 180-183
// Roh/Einfach-Umschalter gibt es im Vergleich nicht (indicatorCapable() ist
// fuer die Compare-Metrik-IDs durchgaengig false). Named function statt
// Inline-Closure im Markup (Safari-Factory-Muster).
function noopOutlookMode(): void {}
```
```svelte
<!-- Z. 217-229 -->
<WeatherV2Reihenfolge
	friendlyMap={{}}            <!-- immer leer  -> Anzeige immer 'Roh' -->
	onMode={noopOutlookMode}    <!-- Klick faellt ins Leere -->
	activeChannel="email"       <!-- daher meldet der PO „E-Mail" -->
	... />
```

**Warum der Umschalter ueberhaupt erscheint:** Die Annahme im Kommentar war bis Commit
`de7a3d11` (#1848 A2, 2026-08-20) richtig — der Ausblick speicherte Katalog-*Keys*
(`wind_max_kmh`), fuer die `indicatorCapable()` immer `false` liefert, das `Segmented`
wurde nie gerendert und der No-Op war folgenlos. A2 stellte auf **Kennungen** (`metric_id`)
um; 12 davon stehen in `INDICATOR_MAP` (`frontend/src/lib/components/trip-detail/metricsEditor.ts:25-39`).
Seitdem rendert der Umschalter und tut nichts — eine **Attrappe**, entstanden als
Seiteneffekt einer Vokabular-Umstellung.

Kein `disabled`, keine Validierung, keine Whitelist verwirft „Einfach" — die Kette existiert
schlicht nicht.

## Related Files

### Frontend
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte:180-183, 217-229` | **Die Fehlerstelle.** No-Op-Handler + leere `friendlyMap` |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:101-102, 148-155` | Der geteilte Baustein — traegt den `Segmented`-Umschalter bereits vollstaendig |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:724-731` | **Vorlage:** funktionierender `onMode` des Kanal-Pfads |
| `…/WeatherMetricsTab.svelte:268, 459-461, 891-893` | Ausblick-State `outlookMetricKeys` -> `display_config.outlook_metrics` |
| `…/WeatherMetricsTab.svelte:1406-1412, 1793-1794` | Einbettungen (Wizard + Trip) |
| `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts:44-77, 110ff` | Kanal-Override-Struktur, Serialisierung |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:25-39, 62-64, 336-369` | `INDICATOR_MAP`, `indicatorCapable`, `use_friendly_format`-Serialisierung |
| `frontend/src/lib/types.ts:297-302` | `outlook_metrics?: string[]` — **reines String-Array, kein Platz fuer ein Flag** |

### Go-API
| Datei | Relevanz |
|---|---|
| `internal/model/trip.go:117` | `DisplayConfig map[string]interface{}` — schemalos |
| `internal/handler/config_merge.go:12-21` | flacher Read-Modify-Write, nur oberste Schluesselebene |
| `internal/handler/weather_config.go:86-99, 179` | PUT-Handler, keine Validierung |

**Befund: Go ist null Arbeit.** Kein Struct-Feld, keine Whitelist, keine Validierung —
jedes neue Unterfeld reist automatisch mit.

### Python — Vorlage (Kanal-Pfad, funktioniert)
| Datei | Relevanz |
|---|---|
| `src/app/loader.py:56-88` (`_resolve_format_mode`) | Vorrangregel: explizites `format_mode` > `use_friendly_format=False` -> `raw` > Katalog-Default |
| `src/app/loader.py:868-899` | Parser der `channel_layouts` |
| `src/app/models.py:928-1008` (`get_metrics_for_channel`) | Kanal-Kaskade nach ADR-0050 |
| `src/output/renderers/email/helpers.py:1162-1180` (`build_friendly_keys`) | uebersetzt `MetricConfig` -> Menge `col_key` |
| `src/output/renderers/email/helpers.py:702-860` (`fmt_val`) | **der Einfach-Formatierer der Stundentabelle** |
| `src/output/renderers/email/helpers.py:1204-1220` | `build_html_indicator_keys` — der separate #814-Ampel-Pfad |
| `src/app/metric_catalog.py:98-100` | `has_friendly_format` = abgeleitet aus `friendly_label` |

### Python — Ausblick (Ist-Zustand, Flag fehlt komplett)
| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py:957-984` (`normalize_outlook_metric_ids`) | reduziert **jede** Form auf `list[str]` — Engstelle der Kette |
| `src/output/renderers/compare_outlook_metric_ids.py:194-222` | `resolve_trip_outlook_metrics` -> `list[str] \| None` |
| `…/compare_outlook_metric_ids.py:265-341` (`outlook_columns`) | Spalten-Dict — **einziger Transportweg** zu allen vier Ausgaben |
| `…/compare_outlook_metric_ids.py:374-406` (`format_outlook_value`) | **die eigentliche Luecke:** kein Einfach-Zweig, immer Rohzahl + Einheit |
| `…/compare_outlook_metric_ids.py:409-443` (`format_outlook_range_cell`) | Spannenzelle `9/27`, bewusst ohne Einheit (#1848 A1 AC-9) |
| `src/output/renderers/email/outlook.py:602-674` (`build_outlook_row`) | **der eine Zellenbau**, speist alle vier Ausgaben |
| `src/output/renderers/email/outlook.py:345-368` (`_metric_column_bg`) | Ampel-Toenung — heute **unbedingt** aktiv |
| `src/output/renderers/email/thunder_branch.py` | Gewitterspalte wird **nachtraeglich ueberschrieben**, viermal getrennt |
| `src/output/renderers/trip_report.py:142, 209, 224, 301, 308` | Einstiegspunkte: `build_friendly_keys` bzw. `resolve_trip_outlook_metrics` |

### Die vier Ausblick-Ausgabeorte (konsumieren alle nur `stage["cells"]`)
| Ausgabeort | Datei:Zeile |
|---|---|
| E-Mail HTML | `src/output/renderers/email/outlook.py:130-146` |
| E-Mail Klartext | `src/output/renderers/email/outlook.py:290-315` |
| E-Mail kompakt | `src/output/renderers/email/compact.py:265-282` |
| Telegram | `src/output/renderers/narrow.py:549-580` |
| SMS | **hat gar keinen Ausblick** |

## Existing Patterns

- **Der geteilte Baustein ist bereits da.** `WeatherV2Reihenfolge` traegt den Umschalter
  vollstaendig; der Ausblick fuettert ihn nur mit `{}` und einem No-Op. Die schmalste
  Einstiegsstelle ueberhaupt — kein neues Bedienelement noetig.
- **EIN Zellenbau statt vier.** Anders als die Stundentabelle (vier getrennte
  `fmt_val`-Aufrufe plus ein dritter Pfad in `compact_summary.py`) hat der Ausblick
  **genau eine** Zellenfabrik. Ein Flag, das dort ankommt, wirkt in allen vier Ausgaben.
- **Vorrangregel wiederverwendbar.** `_resolve_format_mode(mc_data, metric_id)` nimmt ein
  Dict + Kennung — direkt nutzbar, ohne `MetricConfig`.
- **Katalog ist SSoT** fuer „hat diese Metrik eine Einfach-Form": `friendly_label`.

## Dependencies

- **Upstream:** `display_config` (Trip-Persistenz), Metrik-Katalog (`friendly_label`,
  `format_modes`, `default_format_mode`), `derived_aggregations()`
- **Downstream:** vier Ausblick-Renderer, Paritaets-Waechter
  `tests/tdd/test_shared_outlook_renderer.py`, `tests/tdd/test_trip_outlook_parity.py`
  (ADR-0037-Folgepflicht: muessen bei jeder `outlook.py`-Aenderung gruen bleiben)

## Existing Specs

| Spec | Was sie festlegt |
|---|---|
| `docs/specs/modules/feat_1848_a2_ausblick_kennungen.md` | Ausblick speichert **nur noch die reine Kennung**; Paar-Altform dauerhaft lesbar, nie mehr geschrieben. Zweck: das „vierte Vokabular" abschaffen. Drei-Werte-Semantik (`None` vs. `[]`) |
| `docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md` | Ausblick verhaelt sich **exakt wie ein Kanal**: keine eigene Auswahl, Grundauswahl ist Ausgangsmenge, „Aus"/„Ein" statt Kaestchen. Erledigt #2029. AST-Waechter auf `splitChannelMetricsForDisplay()` |
| `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` | Ausblick-Auswahl ist **global, ohne Kanal-Ebene** (ADR-0055 Punkt 2). Known Limitation: „keine neue Formatierungsarbeit in dieser Scheibe" |
| `docs/specs/modules/feat_1720_s2_ausblick_kompakt_telegram.md` | Dieselbe Auswahl wirkt in allen vier Ausgabeorten. „Kein neues Persistenzfeld" |
| `docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md` | (ueberholt) Praezedenz: Ausblick-Umbauten wurden bisher als Frontend **oder** Renderer geschnitten, nie als beides |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md:73-77` | **Regel 5:** die Entscheidung betrifft nur die AUSWAHL — „Reihenfolge und Rohwert-/Einfach-Format bleiben kanal-eigen" |
| ADR-0037 / ADR-0055 / ADR-0059 | Ausblick-Datenmodell, keine Kanal-Ebene, Erbe der Grundauswahl |

**Es gibt kein ADR, das Roh/Einfach als eigene Entscheidung fuehrt.**

## Risks & Considerations

1. 🔴 **Nur 8 Metriken haben ueberhaupt eine Einfach-Form.** `friendly_label` ist gesetzt fuer
   `wind_direction, thunder, cape, cloud_total, cloud_low, cloud_mid, cloud_high, sunshine`.
   Das Frontend-`INDICATOR_MAP` fuehrt **12** — die vier zusaetzlichen (`wind`, `gust`,
   `rain_probability`, `precipitation`) haben backendseitig **kein** `friendly_label` und
   laufen nur ueber den HTML-Ampelpunkt (`_AMPEL_CAPABLE_METRIC_IDS`).
   **Konsequenz fuer den Screenshot des PO:** von den sechs sichtbaren Umschaltern haetten
   nur **Gewitter** und **Sonnenstunden** eine echte Einfach-Form; Wind, Boeen, Niederschlag
   und Regenwahrscheinlichkeit brauchen eine eigene Festlegung, sonst bleibt die Attrappe
   fuer vier von sechs Groessen bestehen — nur leiser.
2. 🔴 **Speicherform.** `outlook_metrics` ist bewusst `list[str]` (#1848 A2, ADR-0055-Nachtrag).
   Eine Rueckkehr zur Objektform wuerde genau das Sondervokabular wiedereinfuehren, dessen
   Abschaffung A2s Zweck war. Ein **paralleles** Feld (`outlook_metric_formats`) umgeht das,
   schafft aber einen zweiten Speicherweg neben `use_friendly_format`.
3. 🟠 **Ampel-Kollision.** Der Ausblick toent seine HTML-Zellen heute **immer** ampelartig
   (`_metric_column_bg`, #1849) — unabhaengig von jeder Nutzerwahl. Damit ist ein Teil der
   „Darstellung" bereits festgelegt. Zu entscheiden: ersetzt „Einfach" die Zahl durch ein
   Wort/Symbol, oder ergaenzt es einen Ampelpunkt?
4. 🟠 **Gewitterspalte umgeht den Zellenbau.** Seit #1848 A3 kommt ihr Text aus vier
   getrennten Bauern in `thunder_branch.py`, nicht aus `cells`. Ein Flag muesste dort
   **viermal** ankommen — genau die Doppelpflege, die A3 beseitigt hat.
5. 🟠 **Spannenzellen.** `_merge_min_max_pairs` baut ein **neues** Dict und kopiert nur
   explizit gelistete Schluessel (`aggregation` faellt dabei weg). Ein neues Feld muss an
   **beiden** Stellen durchgereicht werden, sonst wirkt es fuer Temperatur-Spannen nicht.
6. 🟡 **Renderer-Commit-Gate.** Aenderungen an `outlook.py` loesen das Gate aus
   (Modus-Matrix-Test + Mail-Validator frisch gruen). Die Paritaets-Waechter
   `test_shared_outlook_renderer.py` / `test_trip_outlook_parity.py` sind ADR-0037-Folgepflicht.
7. 🟡 **Der Umschalter ist auch im Ortsvergleich-Uebersichtsblock ein No-Op**
   (`WeatherMetricsTab.svelte:1168-1172`) — dort noch folgenlos, weil die Uebersicht
   weiterhin Katalog-Keys nutzt. Eine tickende Attrappe derselben Bauart.
8. 🟡 **Testabdeckung ist blind.** `frontend/e2e/epic-138-metriken-editor.spec.ts:159` heisst
   „Roh/Einfach umschaltbar", klickt aber ausschliesslich **Roh** und haette den Bug nie
   gefangen. `frontend/e2e/trip-outlook-metric-selection.staging.spec.ts` prueft die
   Umschaltung gar nicht.

## Offene Designfrage fuer /20-analyse

**Was bedeutet „Einfach" im Ausblick konkret?** Die Stundentabelle kennt die Antwort je
Metrik (`fmt_val`: `72` -> `☁️`, `225°` -> `SW`, `28` -> `stark`). Der Ausblick zeigt aber
**Tages-Aggregate und Spannen**, nicht Stundenwerte — `fmt_val` ist auf `col_key` +
Stunden-`row` gebaut und nicht direkt wiederverwendbar. Die untergeordneten Helfer
(`output/metric_format.py`, `services/weather_metrics`) sind teilbar.
Zu klaeren: Verhalten fuer die vier Ampel-Metriken ohne `friendly_label` und fuer Spannenzellen.

---

# Analysis (Phase 2)

## Type

**Bug** — ein sichtbares Bedienelement ohne Wirkung (Attrappe), entstanden als Seiteneffekt
von #1848 A2. Der Fix erfordert allerdings Feature-Arbeit: die Wirkungskette dahinter
existiert nirgends.

## Die zentrale technische Erkenntnis

🔴 **`stage["cells"]` ist EIN geteilter Kanal fuer HTML **und** Text.** `build_outlook_row`
(`email/outlook.py:602-674`) schreibt die Zellenliste einmal; vier Renderer lesen sie
(HTML `outlook.py:130-146`, Klartext `:290-315`, Kompakt `compact.py:265-282`,
Telegram `narrow.py:549-580`). `format_outlook_value` hat — anders als `fmt_val` — **keinen
`html`-Parameter**, und die HTML-Zelle wird escaped (`_otd(_html.escape(text), …)`,
`outlook.py:151`).

**Konsequenz:** Ein HTML-Ampelpunkt (`_ampel_dot_severity`) kommt im Ausblick nicht in
Frage — er erschiene als Quelltext bzw. auch in Telegram. **„Einfach" heisst im Ausblick
daher: Wort/Symbol statt Zahl, in allen vier Ausgaben gleich.** Das ist kein Verlust: die
HTML-Zelle traegt ihre Ampel bereits als Hintergrundtoenung (`_metric_column_bg`,
`outlook.py:345-368`, unbedingt aktiv seit #1849).

## Aggregat-Tauglichkeit der vorhandenen Formatierer

Alle Einfach-Formatierer ausser einem sind **reine Zahl→Text-Funktionen ohne Stundenkontext**
und damit direkt auf Tages-Aggregate anwendbar. Staerkster Beleg: `severity_for()` wird im
Ausblick **bereits heute** auf Aggregatwerte angewandt (`_metric_column_bg`).

| Metrik (Ausblick-Spalte) | Roh heute | Einfach moeglich? | Helfer |
|---|---|---|---|
| `wind_direction` (Mittel) | `225 °` | **ja** `SW` | `degrees_to_compass` (`src/utils/geo.py:32`) |
| `cloud_total/_low/_mid/_high` (Mittel) | `62 %` | **ja** `⛅` | `cloud_emoji` (`src/output/metric_format.py:253`) |
| `wind` (Maximum) | `45 km/h` | **ja** `sehr stark` | `format_wind_strength` (`src/services/weather_metrics.py:122`) |
| `gust` (Maximum) | `62 km/h` | **ja** `sehr stark` | dito |
| `precipitation` (Summe) | `7.4 mm` | **ja, aber neu eichen** `maessig` | `format_precip_intensity` (`:143`) — Schwellen 2/10 mm meinen **Stunden**-mm, hier steht die **Tagessumme** |
| `rain_probability` (Maximum) | `75 %` | **existiert nicht** | — Wortskala muss festgelegt werden |
| `sunshine` (Summe) | `6.4 h` | **existiert nicht** | — `get_weather_emoji` braucht `is_day`/`wmo_code`/`dni_wm2` je Stunde; fuer ein Tages-Aggregat sinnlos |
| `thunder` (Maximum) | `mittel` | **Roh IST bereits das Wort** | `_fmt_thunder` (`email/compare_html.py:204`) liefert nur die Stufe — ein Umschalter haette nichts zu tun |
| `temperature` / `wind_chill` (Spanne) | `9/27` | **existiert nirgends im Produkt** | kein `friendly_label`, kein `simplified` — zeigen daher korrekt **keinen** Umschalter |
| `cape` | — | **kommt im Ausblick nicht vor** | `selectable=False` ⇒ `available_aggregations('cape') == []` |
| `visibility` | `3000 m` | bewusst keine (#814 AC-5) | — |

**Ergebnis fuer den Screenshot des PO:** von den sechs sichtbaren Umschaltern wuerden mit den
vorhandenen Helfern **drei** wirken (Wind, Boeen, Niederschlag), **drei nicht**
(Regenwahrscheinlichkeit, Sonnenstunden, Gewitter).

## Technical Approach

**Speicherform: paralleles Feld `display_config.outlook_metric_formats: {metric_id: bool}`.**

Begruendung: `normalize_outlook_metric_ids()` reduziert **aktiv** jede Eingabe auf `list[str]`
(#1848 A2, ADR-0055-Nachtrag: das „vierte Vokabular" abschaffen). Eine Rueckkehr zur
Objektform in `outlook_metrics` wuerde genau das zurueckdrehen. Ein Sibling-Key ist
strukturell dasselbe Muster wie `channel_layouts` neben `metrics` — kein neues Konzept.
Go braucht dafuer nichts (`mergeConfigMap` merged top-level, `map[string]interface{}`).

🔴 **Der Ausblick-Default muss explizit `False` („Roh") sein — NICHT die Katalog-Vorrangregel
`_resolve_format_mode`.** Deren Rueckfall ist `metric_def.default_format_mode`, und der ist
fuer `cloud_total`/`sunshine`/`wind_direction` **`symbol`/`scale`**, nicht `raw`. Wuerde der
Ausblick sie uebernehmen, aenderte sich das Aussehen **bestehender** Trips ohne jede
Nutzeraktion — und die bytegenauen Paritaets-Fixtures brechen zu Recht.

**Kette:** `WeatherV2Reihenfolge` (traegt den Umschalter bereits) → `CompareOutlookLayoutControls`
(echter `onMode` statt No-Op) → `WeatherMetricsTab` (State + Payload) → neues Feld → Go
(unveraendert) → Normalisierer in `metric_catalog.py` → `resolve_trip_outlook_metrics` →
`outlook_columns` traegt das Flag je Spalte → `format_outlook_value` verzweigt →
`build_outlook_row` speist alle vier Ausgaben.

**Der Umschalter erscheint nur, wo er wirkt.** `indicatorCapable()` (Frontend-`INDICATOR_MAP`,
12 Eintraege) ist der falsche Waechter fuer den Ausblick — er kennt die Ausblick-Semantik
nicht. Es braucht eine **ausblick-eigene Faehigkeitsliste**, abgeleitet aus derselben
Quelle wie der Backend-Zweig, damit Bedienflaeche und Wirkung nicht auseinanderlaufen
koennen. Das ist der eigentliche Waechter gegen eine Wiederkehr des Bugs.

## Affected Files

| Datei | Aenderung | Beschreibung |
|---|---|---|
| `frontend/src/lib/types.ts` | MODIFY | `outlook_metric_formats?: Record<string, boolean>` |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | MODIFY | `noopOutlookMode` entfaellt, echter Handler + echte `friendlyMap`, ausblick-eigene Faehigkeitsliste |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | State, Lade- und Speicherpfad, Durchreichung an beide Einbettungen |
| `src/app/metric_catalog.py` | MODIFY | Normalisierer fuer das neue Feld; Wortskalen-Faehigkeit je Metrik |
| `src/services/weather_metrics.py` | MODIFY | Wortskalen fuer Regenwahrscheinlichkeit und Sonnenstunden; Niederschlag auf Tagessumme geeicht |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | Flag durch `outlook_columns` **und** `_merge_min_max_pairs`; Einfach-Zweig in `format_outlook_value` |
| `src/output/renderers/email/outlook.py` | MODIFY | `build_outlook_row` reicht das Flag durch |
| `src/output/renderers/trip_report.py` | MODIFY | Aufloesung des neuen Feldes, Durchreichung |
| `tests/tdd/test_outlook_darstellungsform.py` | CREATE | Kern-Tests: Umschaltung wirkt in allen vier Ausgaben |
| `frontend/e2e/epic-138-metriken-editor.spec.ts` | MODIFY | der blinde Test klickt nur „Roh" — muss „Einfach" klicken |

## Scope Assessment

- Dateien: 10 (8 MODIFY, 1 CREATE, 1 Test-MODIFY)
- Geschaetztes LoC-Delta: **+280 bis +320** ⇒ **Override auf 500 noetig** (`loc_limit_override`)
- Risk Level: **MEDIUM-HIGH**

## Risks

1. 🔴 **Bytegenaue Paritaets-Waechter.** `tests/tdd/test_trip_outlook_parity.py` vergleicht
   HTML und Klartext **byte-identisch** gegen Fixtures; `test_shared_outlook_renderer.py`
   prueft `build_outlook_row` gegen ein woertlich getipptes Dict. Jede Erweiterung muss
   **additiv und per Default abgeschirmt** sein (Default „Roh"), sonst brechen sie zu Recht.
2. 🔴 **`_merge_min_max_pairs` baut ein NEUES Dict** und kopiert nur explizit gelistete
   Schluessel — ein neues Feld muss dort **zusaetzlich** ergaenzt werden, sonst wirkt es fuer
   Spannenzellen nicht. (Trifft hier nur Temperatur/gefuehlte Temperatur, die ohnehin keine
   Einfach-Form haben — aber der Waechter muss das festhalten, sonst faellt es beim naechsten
   Ausbau durch.)
3. 🟠 **Gewitterspalte umgeht den Zellenbau** (vier Bauer in `thunder_branch.py`). Deshalb
   bleibt Gewitter bewusst draussen — die Roh-Darstellung ist dort bereits das Wort.
4. 🟠 **Renderer-Commit-Gate** greift bei `outlook.py` (Modus-Matrix + Mail-Validator frisch gruen).
5. 🟠 **Geteilter Baustein trifft beide Flaechen.** `CompareOutlookLayoutControls` bedient Trip
   **und** Ortsvergleich — der Fix wirkt gewollt in beiden. Im PR explizit benennen.
6. 🟡 **Blinder Bestandstest.** `epic-138-metriken-editor.spec.ts:159` heisst „Roh/Einfach
   umschaltbar", klickt aber nur „Roh". Der neue Test muss auf „Einfach" klicken **und** eine
   Inhaltsaenderung pruefen, nicht nur den Schalterzustand — sonst ist er selbst Theater.

## Vorschlag: Wortskalen fuer die drei Luecken (PO-Freigabe in Phase 3)

| Groesse | Vorschlag Einfach-Form | Schwellen |
|---|---|---|
| Regenwahrscheinlichkeit (Maximum) | `unwahrscheinlich / moeglich / wahrscheinlich / sehr wahrscheinlich` | `<25 / <50 / <75 / >=75 %` |
| Sonnenstunden (Tagessumme) | `truebe / wechselhaft / freundlich / sonnig` | `<2 / <5 / <8 / >=8 h` |
| Niederschlag (Tagessumme, neu geeicht) | `trocken / leicht / maessig / stark` | `<=0 / <=5 / <=20 / >20 mm` (statt Stunden-Schwellen 2/10) |

Alle drei sind reine Zustandsbeschreibungen ohne Handlungsempfehlung (ADR-0007).

## Bewusst NICHT im Zuschnitt

- **Gewitter und CAPE** — Gewitter zeigt bereits die einfache Form, CAPE kann im Ausblick
  nicht vorkommen (`selectable=False`). Der Umschalter wird dort **ausgeblendet**, nicht
  spaeter nachgezogen.
- **Temperatur / gefuehlte Temperatur** — haben produktweit keine Einfach-Form; zeigen
  korrekt keinen Umschalter.
- **Der No-Op im Ortsvergleichs-Uebersichtsblock** (`WeatherMetricsTab.svelte:1168-1172`) —
  strukturell verwandt, aber anderer Bug (Katalog-Keys). Sammel-Eintrag #1199.
- **Keine neue Kanal-Ebene fuer den Ausblick** — ADR-0055 Punkt 2 bleibt unangetastet.
- **Kein Go-Eingriff, keine SMS-Aenderung** (SMS hat keinen Ausblick).

## Open Questions

- [ ] Wortskalen (Tabelle oben) — Freigabe mit der Spec in Phase 3.
