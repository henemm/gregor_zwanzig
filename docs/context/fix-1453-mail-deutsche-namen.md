# Kontext: #1453 — Namensformen ordnen (Kurzform englisch, ausgeschriebener Name deutsch)

Stand 2026-08-02, HEAD `eedeeed9`. **Achtung: Der Ticket-Titel und die ursprüngliche
Forderung („Mail wieder deutsch beschriften") sind durch PO-Entscheidung vom 2026-08-02
überholt.** Maßgeblich sind die Issue-Kommentare vom selben Tag.

## Die geltende Regel (PO 2026-08-02)

> **Wo wenig Platz ist, steht die englische Fachkurzform. Wo Platz ist, steht der
> ausgeschriebene deutsche Name.**

Begründung des PO: Das Produkt richtet sich an Profis, die internationale Sprache ist
Englisch — deshalb sind auch die SMS-Kürzel bereits englisch. Einfache englische Sprache,
Fachbegriffe dort, wo sie der Klarheit dienen.

| Ort | Form | Sprache |
|---|---|---|
| Stundentabelle (bis 22 Spalten) | Kurzform | **englisch** |
| Übersichtstabelle (Zeilenbeschriftung) | voller Name | **deutsch** |
| 3-Tages-Ausblick (Zeilenbeschriftung) | voller Name | **deutsch** (heute schon) |
| Bedienoberfläche, Editor | voller Name | **deutsch** |
| Alarm-Mail, Telegram, Betreff | Alarm-Kurzform | deutsch |
| SMS-Token | Protokoll | neutral/englisch |

Damit ist die frühere PO-Entscheidung #862/#849 („Spaltenköpfe bleiben bewusst englisch",
`docs/specs/_archive/modules/fix_862_849_col_labels.md:58`) **bestätigt**, nicht aufgehoben.

## Umfang

1. `Cond°` → `Dew`, `hPa` → `Press` (fachlich schlecht gewählt; `CAPE` bleibt)
2. Übersichtstabelle: ausgeschriebene deutsche Namen statt Kurzformen
3. Pflicht-Prüfer auf genau eine Form zurückbauen
4. Konfiguration zeigt je Größe alle drei Formen (Deutsch lang · Englisch kurz · SMS)

## Befund 1 — der Vergleichs-Pfad hat genau EINE Lesestelle

`src/output/renderers/email/compare_html.py:440` — `derive_row_labels()` liest
`get_metric(row["metric_id"]).col_label`. **Die einzige `col_label`-Lesestelle des
gesamten Compare-Pfads.** Von dort verzweigt es in sechs sichtbare Ausgaben:

| Ziel | Datei:Zeile |
|---|---|
| Übersichtstabelle HTML (Zeilenkopf) | `:638`/`:641` (`_visible_metrics`) → `:589` |
| Stundentabelle HTML (`<th>`) | `:779`/`:783` (`_visible_hour_metrics`) → `:852` |
| Einheiten-Legende | `:1164` (`_units_legend_text`) |
| Klartext-Übersicht | `comparison.py:218` → `:221` |
| Klartext-Stundenzeile | `comparison.py:240` → `:289` |

⇒ Der Umbau ist an **einer** Funktion möglich, plus einer Unterscheidung
„Übersicht vs. Stunde". Der Klartext liest dieselbe Quelle (Import `comparison.py:33`),
festgenagelt durch `tests/unit/test_compare_mail_plaintext_html_label_parity.py`.

## Befund 2 — der Tour-Pfad ist vollständig getrennt

| | Vergleich | Tour |
|---|---|---|
| Beschriftungs-Funktion | `compare_html.derive_row_labels` (`:425-452`) | `helpers.visible_cols` (`:231-275`) |
| Register-Zugriff | `get_metric(mid).col_label` | `get_col_defs()` (`metric_catalog.py:910-917`) |
| HTML-Kopf | `compare_html.py:852` | `html.py:660` |
| Klartext-Kopf | `comparison.py:289` | `plain.py:50` |
| Zeitspalte | `"Zeit"` | `"Time"` |
| Pflicht-Prüfer | `email_spec_validator.py` | `briefing_mail_validator.py` |
| Golden-Dateien | `tests/fixtures/compare_mail_structure_golden.json` | `tests/golden/email/*` |

**Keine gemeinsame Codezeile erzeugt beide Köpfe.** Die Tour bleibt unberührt, solange
`MetricDefinition.col_label` selbst nicht umgeschrieben wird — die beiden Kürzel aus
Punkt 1 ändern es aber sehr wohl, also **ziehen dort die Tour-Golden-Dateien mit**
(`Cond°`/`hPa` erscheinen dort, sofern die Größen in den Fixtures aktiv sind — prüfen).

## Befund 3 — Platzgrenzen, am Code gemessen

**Stundentabelle HTML** (`compare_html.py:852-869`): keine festen Spaltenbreiten, kein
`min-width`, **kein `white-space:nowrap`** ⇒ Köpfe brechen an Leerzeichen und nach
Bindestrichen um. Schrift `FONT_DATA` = JetBrains Mono 11px ⇒ **6,6 px/Zeichen**.
Container `max-width:680px`.

Bei 23 Spalten: 207 px Chrome + 700 px Text = **907 px** — die Tabelle sprengt den
Container heute schon um ein Drittel und überlebt nur über `overflow-x:auto`.
Längste heutige Kürzel: **6 Zeichen** (`CldLow`, `CldMid`, `0°Line`).
⇒ **Belastbare Grenze: ≤ 6 Zeichen je unbrechbarem Token.** `Dew` (3) und `Press` (5)
verbessern das sogar.

**Übersichtstabelle** (`:586-589`, `:676-679`): Zeilenkopfzelle, proportionale Schrift,
kein nowrap, `min-width:760px` + `overflow-x:auto` ⇒ **praktisch unbegrenzt**. Vor
`386bbdba` standen dort die vollen deutschen Namen.

**Klartext**: `CHANNEL_LIMITS["email"]["max_chars"] = None`, kein Tabellenraster; die
Stundenzeile wiederholt jedes Label je Zelle (**22× pro Zeile**, heute schon 248 Zeichen).
⇒ Spricht für kurze Formen in der Stundenzeile, nicht dagegen.

## Befund 4 — die vollen deutschen Namen stehen noch im Repo

`git show 386bbdba` löschte die getippten `"label"`-Felder. Ein **zweiter Satz derselben
Namen lebt weiter**: `comparison.py:65-79` (`_DAILY_PLAIN_ROWS`) und `:95-110`
(`_PLAIN_ROWS`) — heute das Telegram/SMS-Vokabular, wörtlich die alten Mail-Labels.
**Das ist die Vorlage für Punkt 2** — aber Vorsicht: es darf keine dritte Kopie entstehen,
die Namen müssen aus `label_de` kommen.

Der 3-Tages-Ausblick derselben Mail ist **bereits deutsch**
(`compare_outlook_metric_ids.py:78-113`), mit ausdrücklicher Begründung im Docstring
(`:82-88`): `col_label` sei englisch und für temperature min/max/avg **identisch**
(`Temp`). ⇒ Der Ausblick ist bereits das Vorbild für Punkt 2.

## Befund 5 — die Kollisionsregel

`compare_html.py:444-452` in `derive_row_labels`: Kommt dieselbe Kurzform innerhalb der
sichtbaren Zeilenmenge mehrfach vor, hängt jede betroffene Zeile ihren **rohen**
`aggregation`-Wert an (`Temp max`/`Temp min`). Greift nur in der Übersicht — in
`HOUR_METRICS` ist jede `metric_id` genau einmal vertreten.

**Vorbild für die deutsche Fassung:** `compare_outlook_metric_ids.py:110-115` benutzt
dieselbe Mechanik mit `aggregation_label_de()` (`metric_catalog.py:608-610`:
min→Minimum, max→Maximum, avg→Mittel, sum→Summe) ⇒ `Temperatur Maximum`.

## Befund 6 — es sind ZWEI rote Tests, nicht fünf

Das Ticket nennt fünf; die Zahl stammt aus einem veralteten Stand
(`.pytest_cache/lastfailed`). Real ausgeführt über alle `tests/unit/test_compare_mail_*`
plus `tests/tdd/test_mail_alert_dedup.py`:

| Test | Ursache | Ticket |
|---|---|---|
| `test_compare_mail_overview_plausibility_coverage.py::test_ac4_exemption_set_is_declared_and_complete` | Prüfer trägt noch die 22 alten deutschen Übersichts-Schlüssel, Renderer liefert seit A2b englische | **#1420-Rückbau — fällt mit Punkt 2/3 weg** |
| `tests/tdd/test_mail_alert_dedup.py::test_ac5_same_hazard_different_region_not_collapsed` | `compare_html.py:504` `visual_key = (short, bg, fg)`, Gebiet geht nicht ein | **#1451, kein Bezug** |

Die vier Tests aus `test_compare_mail_labels_unchanged.py` existieren nicht mehr — die
Datei wurde am 2026-08-01 zu `test_compare_mail_labels_from_register.py` saniert.

**~~Glücksfall:~~ WIDERLEGT in der RED-Phase (2026-08-02).** Ich hatte hier notiert, die
alten deutschen Prüfer-Schlüssel griffen nach der Rückkehr zu `label_de` sofort. **Das ist
falsch** — sie sind nur *ähnlich*, nicht gleich. Gemessen weichen **9 von 24** ab:

| Prüfer führt | `label_de` liefert |
|---|---|
| `Sonne` | `Sonnenstunden` |
| `Wolken` | `Bewölkung` |
| `Sicht min` | `Sichtweite` |
| `Taupunkt Ø` | `Taupunkt` |
| `Luftdruck Ø` | `Luftdruck` |
| `UV max` | `UV-Index` |
| `Regen` | `Niederschlag` |
| `CAPE` | `Gewitterenergie (CAPE)` |
| `Temp max` | `Temperatur Maximum` |

Der Prüfer muss also an neun Stellen umgeschrieben werden, nicht nur bei den
Kollisionsformen. **Merke: „die alten Werte stehen ja noch da" ist keine Deckungsgleichheit
— vergleichen, nicht annehmen.** Die Ähnlichkeit hat mich die Prüfung sparen lassen.

## Befund 7 — der Pflicht-Prüfer

`.claude/hooks/email_spec_validator.py`:

| Stelle | Inhalt | nach dieser Lieferung |
|---|---|---|
| `:571-575` | `_HOUR_VALUE_COLUMN_LABELS` — aus `col_label` **abgeleitet** (seit #1406 B) | bleibt; zieht `Dew`/`Press` automatisch nach |
| `:590` | 6 Alt-Literale `Gef./Böen/Regen/Gew./Regen-W./Sicht` | **streichen** (Übergangs-Union) |
| `:657-731` | `_OVERVIEW_METRIC_CHECKS`, 46 Einträge: 24 alt-deutsch + 20 A2b-englisch + 2 Kollisionsformen | englische streichen, deutsche bleiben (= Zielform), Kollisionsformen deutsch neu |
| `:759-765` | `_OVERVIEW_NO_CHECK_LABELS`, 5 Einträge | `Thdr`/`PType` streichen |
| `:605`, `:734` | zwei `_REVIEW_DATE`-Merker | auflösen |

Ohne Auffangzweig bei Importfehlern (`:541-544`) — bewusst, damit ein stiller Rückfall
nicht alles durchwinkt.

Mitziehende Tests: `test_compare_mail_overview_plausibility_coverage.py:301-306`
(`ZIEL_LABELS_A2B`), `:57-58` (`_NEW_EXEMPT_LABELS_A2B`),
`test_compare_validator_hour_columns_from_catalog.py:101-107`,
`test_compare_mail_validator_column_order.py`.

## Befund 8 — Punkt 4 braucht keine neue Datenquelle

Alle drei Formen liegen im Register und werden bereits ausgeliefert:
`/api/metrics` führt `col_label` **und** `sms_code` (`api/routers/config.py:79`),
`/api/compare/metrics` den Namen.

Heute im Frontend, unsystematisch:

| Was | Wo | Lücke |
|---|---|---|
| englische Kurzform als Marke | `WeatherV2Reihenfolge.svelte:80-81` | **nur Touren-Editor** — die drei Compare-Editoren bauen ihre Einträge ohne `col_label` (`WeatherMetricsTab.svelte:822-831`, `CompareHourlyLayoutControls.svelte:116-124`, `CompareOutlookLayoutControls.svelte:65-73`) |
| SMS-Kürzel | `WeatherMetricsTab.svelte:1288,1302` | nur bei Größen mit Schwellwert |
| ausgeschriebener Name | überall | — |

⇒ Punkt 4 ist eine **Darstellungs**-Aufgabe, keine Datenaufgabe.

## Risiken

1. **Renderer-Commit-Gate #811** greift, sobald `compare_html.py` gestaged wird —
   Compare-Test-Mail + `email_spec_validator.py` vor dem Commit
   (`scripts/send_gate_test_mails.py --only compare`).
2. **`col_label` zu ändern trifft auch die Tour** (`Cond°`/`hPa` in `helpers.visible_cols`)
   — Tour-Golden-Dateien prüfen und ggf. mitziehen. Das ist bei Punkt 1 **gewollt**:
   ein schlechtes Kürzel ist in beiden Mails schlecht.
3. **Keine dritte Namenskopie erzeugen** — die deutschen Namen für Punkt 2 kommen aus
   `label_de`, nicht aus `_PLAIN_ROWS`.
4. **Neue Kollisionen** bei vollen deutschen Namen in der Übersicht sind unwahrscheinlich
   (`label_de` ist eindeutig), aber die Kollisionsregel muss auf `aggregation_label_de`
   umgestellt werden, sonst steht dort `Temperatur max` statt `Temperatur Maximum`.
