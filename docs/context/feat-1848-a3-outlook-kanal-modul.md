# Context: #1848 Scheibe A3 — Der Ausblick bekommt das Kanal-Modul

**Workflow:** `feat-1848-a3-outlook-kanal-modul` · Track Standard · Branch von `origin/main` @ `cba7ffa3`
**Erstellt:** 2026-08-21

## Request Summary

Der 3-Tages-Ausblick soll dieselbe Bedienlogik bekommen wie die Kanal-Reiter: die Grundauswahl
ist die Obergrenze (nur abwaehlen, nicht hinzufuegen), Abgewaehltes steht in einer sichtbaren
„Aus"-Gruppe und laesst sich zurueckholen — in **beiden** Flaechen (Trip-Editor und
Ortsvergleich-Editor, dieselbe geteilte Komponente an zwei Mountpunkten).

## 🟢 Zuschnitt-Korrektur: A2 hat einen Teil des geplanten A3 bereits geliefert

Das Vorbereitungsdokument (`docs/context/feat-1848-a1-tagesfenster-kennungen.md:167`) nannte fuer
A3 drei Punkte. Einer davon ist seit `cba7ffa3` erledigt:

| Geplant fuer A3 | Stand heute |
|---|---|
| ~~„eine Zeile je Groesse statt zweier Kaestchen fuer Minimum/Maximum"~~ | **erledigt in A2** — `CompareOutlookLayoutControls.svelte:159-182`, Kaestchen ueber `group.metric_id` |
| „nur abwaehlbar aus der Grundauswahl statt freier Katalog-Checkbox-Liste" | **offen** — Teil (a) |
| „sichtbare Aus-Gruppe mit Zurueckholen" | **offen** — Teil (b) |
| „gleiche Beschriftungsquelle wie die Kanaele" | **erledigt** — `outlook_columns()` zieht `label` aus dem Compare-Katalog (#1401 A1) |

**A3 ist damit zweiteilig**, nicht vierteilig.

## 🔴 Der Befund, der den Zuschnitt traegt: die Klemme wirkt im Trip schon — unsichtbar

Der Trip schneidet die Ausblick-Auswahl bereits gegen die Grundauswahl. Der Ortsvergleich nicht.
Das Frontend zeigt in **beiden** Faellen den vollen Katalog.

| Flaeche | Aufloesungsweg | schneidet gegen Grundauswahl? | Beleg |
|---|---|---|---|
| **Trip** | `resolve_trip_outlook_metrics()` | **JA** — `allowed_metric_ids_for_report_type()` | `compare_outlook_metric_ids.py:155-159`; Aufrufer `trip_report.py:209`, `email/outlook.py:580` |
| **Ortsvergleich** | `resolve_outlook_metrics()` direkt | **NEIN** — bewusst | `report_config_resolver.py:291`; Docstring `compare_outlook_metric_ids.py:130-132`: *„Der Ortsvergleich ruft weiterhin `resolve_outlook_metrics()` direkt — er kennt bewusst kein globales Maximum (ADR-0053)"* |

Daraus folgen **zwei verschiedene Aufgaben** unter einem Namen:

- **Trip, Teil (a):** kein neues Verhalten, sondern **Sichtbarmachen einer bereits wirkenden
  Regel**. Wer heute im Trip-Ausblick eine Groesse ankreuzt, die nicht in seiner Grundauswahl
  steht, bekommt ein angehaktes Kaestchen — und in der Mail keine Spalte. Die Oberflaeche
  verspricht etwas, das der Renderer stillschweigend verwirft.
  🔴 **Messpflicht Phase 2:** dieser Befund ist bislang aus dem Code gelesen, nicht gemessen.
  Vor der Spec ist er am echten Loader zu belegen (Trip mit Grundauswahl ohne `humidity`,
  `outlook_metrics=["humidity"]` ⇒ welche Spalten kommen heraus?). Gegenprobe noetig:
  `allowed_metric_ids_for_report_type()` liefert `None` („kein Maximum"), wenn keine Grundauswahl
  gespeichert ist (`models.py:967`, `if not self.metrics:`) — dann klemmt gar nichts und der
  Befund traegt nicht.
- **Ortsvergleich, Teil (a):** eine **echte Verhaltensaenderung**. Der Ausblick wuerde erstmals
  Teilmenge von `active_metrics`. ⇒ **PO-Entscheid noetig**, s. Open Questions.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte:167` | `groupCompareCatalog(catalog)` iteriert ueber den **vollen** Compare-Katalog (~24 Groessen) — hier entsteht Teil (a) |
| dito `:189-207` | `WeatherV2Reihenfolge` gemountet **ohne** `offColumns`/`onRestore` — hier entsteht Teil (b) |
| dito `:39, 44, 68-76` | Props `metricKeys: string[]`, `materializeOutlookMetricKeys()`, `toggleOutlookMetricKeyFromState()` |
| `.../shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:47-52, 168-213` | Der Baustein kann die „Aus"-Gruppe bereits (`offColumns`/`onRestore`, `data-testid="wm2-aus-gruppe"`); `undefined` ⇒ verhaelt sich exakt wie bisher |
| dito `:14-21` | Kommentar aus #1719 S3: Uebersicht/**Ausblick**/Stundenverlauf bekamen bewusst **kein** `offColumns` — die Entscheidung, die A3 fuer den Ausblick aufhebt |
| `.../shared/weather-metrics-tab/channelMetricLayouts.ts:92-101` | 🟢 **Die Formel existiert:** `splitChannelMetricsForDisplay(global, channel)` ⇒ `active = channel ∩ global`, `off = global \ active`. Kein Neubau noetig |
| `.../shared/WeatherMetricsTab.svelte:1398-1412` | Mountpunkt Ortsvergleich (`context="vergleich"`, mit Ein/Aus-Schalter) |
| dito `:1784-1794` | Mountpunkt Trip (`title="3-Tages-Vorschau"`, ohne Schalter — Ein/Aus liegt in `report_config.show_outlook`) |
| dito `:221, 390-440` | Trip-Grundauswahl `buckets.primary` aus `display_config.metrics` |
| dito `:1083` | Ortsvergleich-Grundauswahl `materializedActiveMetricKeys` aus `display_config.active_metrics` |
| dito `:285-286, 300, 790-798` | Trip-Vorbild: `activeChannelSections`, `onRestoreMetric` schreibt in den **Kanal-Override**, nie in die Grundauswahl |
| dito `:1133-1135, 1164-1166` | Ortsvergleich-Vorbild: `compareChannelSections`, `onCompareRestore` |
| `src/output/renderers/compare_outlook_metric_ids.py:129-160` | `resolve_trip_outlook_metrics()` — die Trip-Klemme |
| `src/services/report_config_resolver.py:291` | Ortsvergleich-Weg **ohne** Klemme; direkt darunter (`:299`) wird `active_metrics` sehr wohl als Maximum fuer die Uebersicht aufgeloest |
| `src/output/renderers/email/outlook.py:157-170` | Rueckfall-Kopfzeile bei `None`: `Tag, N, D, R, PR, Wind, Boeen, Gew` — fest verdrahtete Strings, **keine** Metric-ID-Liste |
| `.../weather-metrics-tab/compareMetricOrder.ts:37-44` | `DEFAULT_OUTLOOK_METRIC_KEYS` = `temperature, precipitation, rain_probability, wind, gust, thunder`; einziger Leser ist `materializeOutlookMetricKeys()` |

## Existing Patterns

- **Die „Aus"-Gruppe ist ein geloester Fall.** `WeatherV2Reihenfolge` traegt sie, `splitChannelMetricsForDisplay()`
  berechnet sie, zwei Aufrufstellen betreiben sie produktiv (Trip-Kanal-Reiter, Ortsvergleich-Uebersicht).
  A3 verdrahtet einen dritten und vierten Aufruf — **kein neuer Baustein, kein Compare-Eigenbau**
  (PO-Vorgabe Trip/Compare-Teilung, CLAUDE.md).
- **Beide Grundauswahlen sind am Mountpunkt bereits im Scope** (Top-Level-`$state`/`$derived`
  derselben Komponente) — nichts muss durchgereicht werden.
- **Zurueckholen schreibt nie in die Grundauswahl**, sondern in die flaechen-eigene Auswahl
  (`onRestoreMetric` ⇒ Kanal-Override; `onCompareRestore` ⇒ `channelActiveMetricKeys`). Fuer den
  Ausblick waere das analog `outlookMetricKeys`.

## Dependencies

- **Upstream:** `display_config.metrics` (Trip) bzw. `display_config.active_metrics` (Ortsvergleich)
  als Grundauswahl · `GET /api/compare/metrics` als Katalog · `display_config.outlook_metrics`
  als flaechen-eigene Auswahl (seit A2 reine Kennungen)
- **Downstream:** `resolve_trip_outlook_metrics()` / `resolve_outlook_metrics()` ⇒ `outlook_columns()`
  ⇒ HTML-, Klartext-, Kompakt- und Telegram-Renderer

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | **Die tragende Zusage.** Regel 1/2: Grundauswahl ist das Maximum, eine Ebene darf nur abwaehlen. Regel 4: „Aus" ist ein ZUSTAND, keine Loeschung — *„ein Bedienelement, das nur loeschen kann, verwischt den Unterschied zwischen ‚abgewaehlt' und ‚nie in dieser Auswahl gewesen'"* |
| `docs/adr/0053-compare-kanal-eigene-metrikauswahl-uebersicht.md` | Punkt 1: Ausblick und Stundenverlauf bleiben im Ortsvergleich **bewusst global**, ohne Kaskadenbindung — *„Scheiben-Schnitt, kein Widerspruch zu ADR-0050, weil diese sich auf Kanaele bezieht, nicht auf Ausgabeflaechen"*. **Teil (a) im Ortsvergleich schreibt genau das fort** |
| `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md:314-334` | **AC-13**, die Ausnahme, die A3 aufhebt (s.u.) |
| `docs/specs/modules/feat_1848_a2_ausblick_kennungen.md` | Vorscheibe — Kennungsformat, Drei-Werte-Semantik |
| `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` | Herkunft der Trip-Klemme |

## 🔴 Risks & Considerations

**R-A3-1 — A3 hebt AC-13 aus #1719 S3 auf; zwei Waechter erzwingen heute das Gegenteil.**
`compare_outlook_metric_selection_structure.test.ts:523-576` prueft per AST wortwoertlich
`assert.equal(findAttr(row, 'offColumns'), undefined)` und dasselbe fuer `onRestore`, mit dem
Fehlertext *„AC-13 FAIL: … das erzeugt eine Aus-Gruppe im Ortsvergleich, wo ADR-0050 Regel 4
nicht gilt"*. Die Begruendung dort (`:555-562`) lautet: der Ausblick habe *„bereits einen
funktionierenden Rueckweg (Checkbox darueber)"`. **Genau dieser Rueckweg entfaellt mit Teil (a)** —
ohne freie Katalogliste gibt es kein Kaestchen mehr, ueber das man etwas zurueckholen koennte.
Teil (a) und Teil (b) sind deshalb **nicht unabhaengig**: (a) ohne (b) nimmt den Rueckweg weg,
ohne Ersatz. Die Spec muss AC-13 ausdruecklich abloesen und begruenden.
Dasselbe gilt fuer `compare_hourly_layout_controls_structure.test.ts` — **nur** wenn der
Stundenverlauf mitgezogen wird; er ist **nicht** Teil von A3.

**R-A3-2 — Die Trip-Klemme ist gelesen, nicht gemessen.** S. Messpflicht oben. Faellt die
Positivkontrolle anders aus (z. B. weil `allowed_metric_ids_for_report_type()` in der Praxis
`None` liefert), verliert Teil (a) im Trip seine Begruendung als „Sichtbarmachen" und wird dort
ebenfalls zur Verhaltensaenderung.

**R-A3-3 — Grundauswahl kleiner als gespeicherte Ausblick-Auswahl.** Nach Teil (a) faellt aus der
aktiven Liste, was nicht mehr in der Grundauswahl steht. Es darf **nicht** in der „Aus"-Gruppe
landen (dort steht nur, was abwaehlbar *waere*) — Vorbild ist AC-9 des Trip-Kanal-Reiters:
global abgewaehlt heisst *weder aktiv noch in der Aus-Gruppe*
(`kanal-abwahl-bleibt-reversibel.staging.spec.ts:165-210`). Gespeichert bleibt der Eintrag
trotzdem (ADR-0050 Regel 3: Rueckkehr in die Grundauswahl holt ihn zurueck).

**R-A3-4 — Die sieben festen Rueckfall-Spalten sind keine Metric-IDs.** Liefert die Aufloesung
`None`, rendert `email/outlook.py:157-170` fest verdrahtete Kopfzeilen-Strings. Eine „Aus"-Gruppe
im Zustand `None` (= „nie eingestellt") hat also **keine** Backend-Entsprechung, gegen die sie
sich pruefen liesse; sie muesste aus `DEFAULT_OUTLOOK_METRIC_KEYS` gebildet werden. Die beiden
Listen decken sich heute inhaltlich — das ist aber **nirgends mechanisch erzwungen**. Driften sie,
zeigt die Bedienflaeche eine andere Vorgabe als die Mail. Kandidat fuer einen Waechter.

**R-A3-5 — `[]` heisst „Block aus".** Wer im Ausblick **alles** abwaehlt, erzeugt `[]` — und der
gesamte 3-Tages-Ausblick entfaellt (`report_config_resolver.py:291-294`). Mit einer „Aus"-Gruppe
wird dieser Zustand erstmals bequem erreichbar und ist zugleich **nicht** selbsterklaerend: die
Aus-Gruppe steht voll da, der Block ist weg. Braucht eine benannte Anzeige, sonst ist es die
stille Abwesenheit, die A2 gerade beseitigt hat.

**R-A3-6 — Drei Mountpunkte, nicht zwei.** `CompareOutlookLayoutControls` haengt an zwei Stellen;
der Ortsvergleich-Editor selbst hat laut Projektgedaechtnis **drei** Compare-Mounts. Vor der Spec
ist zu pruefen, ob eine dritte Einbettung existiert, die stillschweigend danebenlaeuft.

**R-A3-7 — E2E-Muster vorhanden, Uebertragung noetig.**
`kanal-abwahl-bleibt-reversibel.staging.spec.ts` prueft AC-7 (abwaehlen ⇒ Aus-Gruppe ⇒
Reload-fest ⇒ zurueckholbar), AC-9 (globale Abwahl schneidet sofort) und AC-11 (Kanal-Abwahl
ueberlebt globales Aus/Ein). Alle drei haben eine Ausblick-Entsprechung.
Bestehende Ausblick-E2E: `compare-outlook-metric-selection.staging.spec.ts`,
`trip-outlook-metric-selection.staging.spec.ts`.

## Open Questions (gehen mit der Spec an den PO)

- [ ] 🔴 **Soll der Ausblick des Ortsvergleichs an dessen Grundauswahl gekoppelt werden?**
      Heute nicht (ADR-0053 Punkt 1, ausdrueckliche Entscheidung). Mit A3 waere: eine im
      Ortsvergleich abgewaehlte Wettergroesse verschwindet auch aus seinem 3-Tages-Ausblick.
      Nein zu sagen ist konsistent moeglich — dann bekommt der Ortsvergleich nur Teil (b), und
      seine „Aus"-Gruppe bildet sich gegen den vollen Katalog (~18 Eintraege lang, unbrauchbar)
      oder gegen `DEFAULT_OUTLOOK_METRIC_KEYS`. **Empfehlung: koppeln** — sonst bleibt die
      Bedienflaeche in zwei Flaechen verschieden, und A3 verfehlt seinen Zweck.
      Entscheidungs-Umkehr zu ADR-0053 ⇒ **neues ADR** (CLAUDE.md).
- [ ] **Was ist die Obergrenze im Zustand „nie eingestellt" (`None`)?** Die Grundauswahl (dann
      ist die Vorgabe je Nutzer verschieden) oder die sechs `DEFAULT_OUTLOOK_METRIC_KEYS` (dann
      passt sie zur Mail, s. R-A3-4)?

## Nicht-Umfang

- Stundenverlauf (`hourly_metrics`) — eigene Flaeche, eigener Waechter, nicht Teil von A3.
- `temperature/avg` waehlbar machen — **PO-Entscheid 2026-08-21: faellt ersatzlos.** Damit
  entfaellt auch die A2-Vormerkung F-ADV1 in #1199.
- Ortsvergleich-Uebersicht und Kanal-Reiter — dort ist das Kanal-Modul bereits umgesetzt.

---

# Analysis (Phase 2, 2026-08-21)

## Type

Feature (Bedienflaechen-Angleichung) **mit einem mitgemessenen Fehlerpfad** — s. M3.

## Simulation VOR der Spec — gemessen, nicht behauptet

Inline gegen die echten Register und den echten Bestand ausgefuehrt (kein Mock).

### M1 — Die Trip-Klemme wirkt. Positiv- UND Negativkontrolle.

| Fall | Grundauswahl | `outlook_metrics` | ohne Klemme | mit Klemme | Klemme wirkt |
|---|---|---|---|---|---|
| **P1** | temp, precip, wind | temp, humidity, gust | Temperatur, Luftfeuchtigkeit, Boeen | **nur Temperatur** | **JA** |
| N1 | *keine* (`metrics=[]`) | temp, humidity, gust | 3 Spalten | 3 Spalten | nein (`allowed=None`) |
| N2 | temp, precip, wind, gust | temp, gust | 2 Spalten | 2 Spalten | nein (innerhalb) |
| **G1** | temp | humidity, gust | Luftfeuchtigkeit, Boeen | **`[]`** | **JA** |
| V1 | *Ortsvergleich* | humidity, gust | `['humidity','gust']` | — kein Schnitt — | n/a |

R-A3-2 ist damit **belegt**: die Klemme wirkt, und N1/N2 schliessen aus, dass sie trivial
immer/nie greift. Die Ausnahme `allowed is None` (N1) tritt nur ohne gespeicherte Grundauswahl auf.

### 🔴 M2 — 13 von 23 Kaestchen im Trip-Ausblick sind Attrappen

Gemessen am echten Bestand `data/users/default/briefings/gr221-mallorca.json`
(Grundauswahl: 11 von 25 Groessen aktiv):

| Menge | Anzahl | |
|---|---|---|
| Ausblick-Liste zeigt heute (Katalog) | **23** | `groupCompareCatalog(catalog)` |
| davon **wirksam** waehlbar | **10** | `cloud_total, fresh_snow, gust, precipitation, snow_depth, sunshine, temperature, visibility, wind, wind_chill` |
| 🔴 **Attrappen** — anhakbar, aber weggeschnitten | **13** | `cloud_high, cloud_low, cloud_mid, dewpoint, freezing_level, humidity, precip_type, pressure, rain_probability, snowfall_limit, thunder, uv_index, wind_direction` |
| in der Grundauswahl ohne Ausblick-Zeile | 1 | `confidence` (erwartet — nicht waehlbar, Issue #710) |

**Mehr als die Haelfte der angebotenen Kaestchen hat keine Wirkung.** Darunter `thunder` und
`rain_probability` — zwei der sieben Standardspalten. Das ist genau die Klasse Bedienelement, die
ADR-0053 im Kontext-Abschnitt woertlich **„Attrappe"** nennt und deren Entfernung dort als richtig
bewertet wird.

### 🔴 M3 — Neuer Befund: die Klemme kann den ganzen Ausblick loeschen (G1)

Liegt die **gesamte** gewaehlte Auswahl ausserhalb der Grundauswahl, liefert
`resolve_trip_outlook_metrics()` `[]`. Und `[]` heisst „bewusst geleert":
`html.py:1356` — `outlook_active = show_outlook and bool(multi_day_trend) and _outlook_metrics != []`.
**Der gesamte 3-Tages-Ausblick verschwindet kommentarlos.**

Das ist derselbe Fehlerpfad, den **A2 gerade an der Nachbarstelle beseitigt hat** (unaufloesbar ⇒
`None`, nicht `[]`, s. `compare_outlook_metric_ids.py:100-125`) — nur eine Stufe spaeter, in der
Klemme, wo ihn niemand gesucht hat. Die dort formulierte Regel gilt unveraendert:
*„Unaufloesbar" und „bewusst geleert" duerfen nie denselben Zustand erzeugen* — hier zusaetzlich:
**„vollstaendig weggeschnitten" auch nicht.**

**Erreichbarkeit** (vor Schwere geprueft): erreichbar auf zwei Wegen — (1) im Ausblick nur
Attrappen anhaken (13 der 23 Kaestchen fuehren dorthin), (2) nachtraeglich in der Grundauswahl
abwaehlen, was ADR-0050 Regel 3 ausdruecklich erlaubt. **Heute nicht eingetreten:** kein
Bestandstrip hat `outlook_metrics` gesetzt (`grep -rl outlook_metrics data/` ⇒ 0 Treffer,
deckt sich mit der A2-Messung vom 2026-08-18). Der Fehler ist also **latent**, nicht akut —
und wird durch A3 Teil (a) an der Wurzel unmoeglich, weil Attrappen verschwinden.

### M4 — Mountpunkte: genau ZWEI (R-A3-6 ausgeraeumt)

`grep` ueber `frontend/src/` liefert ausser Import und Kommentar genau
`WeatherMetricsTab.svelte:1403` (Ortsvergleich) und `:1786` (Trip). Kein drittes Mount.

### 🔴 M5 — Die Falle beim ersten Klick

Alle Trips laufen heute ueber `outlook_metrics = None` ⇒ Renderer zeigt die **festen sieben
Spalten** aus `email/outlook.py:157-170`, **ungeschnitten**. Die Bedienflaeche zeigt dazu passend
die sechs `DEFAULT_OUTLOOK_METRIC_KEYS` als angehakt. Beide stimmen ueberein — **solange niemand
etwas anfasst**.

Sobald der Nutzer im Ausblick **irgendetwas** klickt, wird eine Liste gespeichert, die Klemme
greift, und alles, was nicht in seiner Grundauswahl steht, faellt weg. Fuer `gr221-mallorca`
heisst das: **Gewitter und Regenwahrscheinlichkeit verschwinden beim ersten Klick** — zwei
Spalten, die der Nutzer nie angefasst hat, und die er im Ausblick nicht zurueckholen kann,
obwohl ihr Kaestchen dort steht.

## Affected Files (Scheibe A3)

| Datei | Change | Beschreibung |
|---|---|---|
| `frontend/.../shared/CompareOutlookLayoutControls.svelte` | MODIFY | Teil (a): Liste auf die Grundauswahl begrenzen (neue Prop) · Teil (b): `offColumns`/`onRestore` an `WeatherV2Reihenfolge` durchreichen |
| `frontend/.../shared/WeatherMetricsTab.svelte` | MODIFY | Grundauswahl an beide Mountpunkte (`:1403`, `:1786`) reichen; `onOutlookRestore` analog `onRestoreMetric`/`onCompareRestore` |
| `frontend/.../weather-metrics-tab/compareMetricOrder.ts` | MODIFY | „Aus"-Berechnung fuer den Ausblick (nutzt `splitChannelMetricsForDisplay`, **kein** zweiter Algorithmus) |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | M3-Fix: leer-geschnitten ⇒ `None` (Standardspalten + Warnung), **nicht** `[]` |
| `frontend/.../shared/__tests__/compare_outlook_metric_selection_structure.test.ts` | MODIFY | AC-13-Waechter loesen: prueft ab jetzt **Anwesenheit** statt Abwesenheit von `offColumns`/`onRestore` |
| Tests | CREATE/MODIFY | Unit (off-Berechnung, M3-Fix), AST-Waechter, 2 Staging-E2E nach dem Muster `kanal-abwahl-bleibt-reversibel` |
| `docs/adr/00XX-...` | CREATE | nur falls der PO den Ortsvergleich koppelt (Umkehr zu ADR-0053 Punkt 1) |
| `docs/reference/api_contract.md:2056` | MODIFY | Ausblick-Zeile: Kaskadenbindung + M3-Semantik |

## Scope Assessment

- Dateien: ~8 (3 Frontend-Quellen, 1 Backend, ~4 Test)
- Risk Level: **MEDIUM** — nutzersichtbare Bedienflaeche wird enger; Renderer-Ausgabe aendert sich
  nur im Fehlerfall (M3)
- Erleichterung: **keine Bestandsdaten** (0 gespeicherte `outlook_metrics`), also kein
  Migrationsdruck und keine stille Umdeutung gespeicherter Auswahlen

## Technical Approach

1. **Teil (a) — Liste begrenzen.** `CompareOutlookLayoutControls` bekommt eine Prop
   `grundauswahl: string[] | null`; die Zeilenliste ist `groupCompareCatalog(catalog)` **geschnitten
   gegen** die Grundauswahl. `null` = kein Maximum ⇒ voller Katalog (deckt N1 und, falls der PO so
   entscheidet, den Ortsvergleich ab). **Eine** Prop, **ein** Verhalten, zwei Mountpunkte — die
   Fallunterscheidung Trip/Ortsvergleich liegt allein im uebergebenen Wert, nicht im Bauteil
   (Trip/Compare-Teilung, CLAUDE.md).
2. **Teil (b) — „Aus"-Gruppe.** `splitChannelMetricsForDisplay(grundauswahl, outlookKeys)` liefert
   `{active, off}`; beides an `WeatherV2Reihenfolge` (`primaryColumns`, `offColumns`, `onRestore`).
   **Kein neuer Algorithmus, kein neuer Baustein.**
3. **M3-Fix im Backend.** `resolve_trip_outlook_metrics()`: schneidet die Klemme eine nicht-leere
   Auswahl auf `[]`, ist das Ergebnis `None` (Standardspalten + `logger.warning`), nicht `[]`.
   Die Drei-Werte-Semantik bleibt: `[]` **von der Auswahl selbst** heisst weiterhin „Block aus".
4. **Waechter.** Der AST-Test wird umgedreht (Anwesenheit statt Abwesenheit) und um die
   Grundauswahl-Prop erweitert; ein Wirkungs-Waechter prueft M3 am **gerenderten** Ergebnis
   (Pruefort == Wirkort), nicht am Rueckgabewert.

## Mutations-Gegenproben (Vormerkung fuer Phase 6)

| # | Verfaelschung | MUSS rot werden |
|---|---|---|
| M-1 | Schnitt gegen die Grundauswahl in der Zeilenliste entfernen | Teil-(a)-Test |
| M-2 | `offColumns` wieder weglassen | AST-Waechter **und** E2E |
| M-3 | `onRestore` schreibt in die Grundauswahl statt in `outlookMetricKeys` | E2E „Grundauswahl bleibt unberuehrt" |
| M-4 | M3-Fix zurueckdrehen (`[]` statt `None`) | Wirkungs-Waechter am gerenderten Block |
| M-5 | `off` = *Katalog* minus Auswahl statt *Grundauswahl* minus Auswahl | Test „Aus-Gruppe zeigt keine Attrappen" |
| M-6 | Grundauswahl-Prop nur am Trip-Mount, nicht am Ortsvergleich-Mount | je-Flaeche getrennter Test (nicht summarisch) |

## Open Questions (gehen an den PO)

- [ ] 🔴 **Ortsvergleich koppeln?** (s. oben)
- [ ] 🔴 **Was passiert beim ersten Klick (M5)?**
