# Context + Analyse: #1401 Scheibe C — Begründung statt Leerstelle

**Workflow:** `fix-1401c-begruendung-fehlende-groesse` · Standard Track · Issue #1401 (letzte offene Scheibe)
**Epic-Einordnung:** #1372 Etappe S2-Nachzügler, unter Dach-Epic #1374. Vor S4 (#1357).

> ## ⏸ STATUS 2026-07-31: ANGEHALTEN vor `/30-write-spec`
>
> **PO-Entscheidung: „erst nachdenken, dann bauen".** Beim Schreiben der Spec fiel auf, dass
> „kann diese Größe einen Alarm auslösen" an **drei** Stellen unterschiedlich beantwortet wird
> (Backend `compare_alert.py:46` = 10 · Frontend-Vergleich `compareMetricMapping.ts:10` = 6 ·
> Frontend-Trip `alertMetricTable.ts:202` = 13). Der unten dokumentierte Zuschnitt hätte die
> 6er-Liste repariert und die beiden anderen stehen gelassen — also eine **sechste** Quelle
> geschaffen statt einer zusammengeführt. Genau davor warnt der PO-Kommentar vom 27.07. in #1401.
>
> **Konzept und Bestandsaufnahme: #1435** (rund 60 handgepflegte Listen, 7 Vokabulare,
> 24 Übersetzungstabellen, drei nutzersichtbare Fehler). Scheibe C wird dort zu **Etappe E1**
> plus den beiden Punkten, die dort keinen Platz haben: dem Erklärsatz (Invariante 2, der
> eigentliche Ticket-Inhalt) und dem Leerzustand-Hinweis auf den falschen Reiter.
>
> Eine Spec-Datei wurde bewusst **nicht** hinterlassen — sie hätte die überholte Richtung
> festgeschrieben. Die PO-Entscheidungen E1–E4 unten bleiben gültig, ebenso alle Befunde.
> Nächster Schritt ist die PO-Entscheidung in #1435, nicht `/30-write-spec`.

## Request Summary

Aus dem Issue-Text, Erwartetes Verhalten Punkt 3:

> Bietet eine Fläche eine Größe **nicht** an, wird das sichtbar begründet (z.B. „liegt nur als Tageswert vor"), statt sie kommentarlos wegzulassen — Invariante 2 des Epics (kein stilles Verwerfen).

Ergänzt durch zwei spätere PO-Eingaben:
- **2026-07-28 (Kaskaden-Kommentar):** Die Schrumpfung ist keine Eigenschaft dreier getrennter Flächen, sondern eine **Verjüngung im selben Arbeitsgang** — anhaken, dann feststellen dass die Größe im Stundenverlauf fehlt, dann feststellen dass sie sich auch nicht sortieren lässt.
- **2026-07-31 (Staging-Audit):** Die Alarm-Fläche ist nicht nur lückenhaft, sondern **kreuzverdrahtet**. „Bitte in den Spec-Scope aufnehmen."

## Befund: Kaskade heute nachgemessen (nach Lieferung Scheibe B)

| Schritt | Größen | Quelle | Status |
|---|---|---|---|
| Grundauswahl | **26** | `compare_metric_catalog.py:64-145` | bestätigt |
| Stundenverlauf wählbar | **10** | `compareHourlyMetricDefs.ts:29-44` | bestätigt |
| davon sortierbar | **9** | `orderableHourlyMetricKeys():118-121` filtert `wind_dir_deg` (`defaultOff`) | bestätigt |
| Alarme | **6** | `compareMetricMapping.ts:10-17` | bestätigt |

Scheibe B hat nur **Beschriftungen** aus dem Register abgeleitet. Der Umfang (`COMPARE_TO_ALERT_METRIC`, 6 Einträge) blieb unberührt — die Spec von B klammert Scheibe C ausdrücklich aus (`fix_1401b_register_stundenverlauf_alarme.md:391-392`).

## Befund: die Alarm-Fläche ist falsch verdrahtet, nicht nur knapp

`compareMetricMapping.ts:10-17` (vollständig, 6 Einträge):

```ts
wind_max_kmh:      'wind_gust',       // ← Kreuz-Verdrahtung
precip_sum_mm:     'precipitation_sum',
temp_max_c:        'temperature_max',
thunder_level_max: 'thunder_level',
snow_new_sum_cm:   'fresh_snow',
visibility_min_m:  'visibility'
```

1. **Kreuz-Verdrahtung:** Der Grundauswahl-Key **Wind** (`wind_max_kmh`, Katalog-`id` `wind`) zeigt auf die Alarmgröße `wind_gust` — beschriftet **„Böen"** (`alertMetricLabels.ts:16`). Der Grundauswahl-Key **Böen** (`gust_max_kmh`) ist **gar nicht** gemappt. Folge, vom PO am echten Staging-UI belegt: Wer „Böen" wählt, bekommt keinen Alarm; wer „Wind" wählt, bekommt einen Alarm namens „Böen".
2. **Der Alarm-Vorrat ist 13, nicht 6.** `ALERTABLE_METRICS` (`alertMetricTable.ts:202-215`) führt 13 Größen. Aus dem Vergleich erreichbar sind 6. Unerreichbar, obwohl vorhanden: `temperature_min`, `cape`, `freezing_level`, `humidity` (die vier vom PO genannten) sowie die drei Delta-Größen `temperature_change`, `wind_change`, `precipitation_change`.
3. **Leerzustand schickt in den falschen Reiter.** `AlarmeTab.svelte:239-243`: „Wähle im Tab „Wertebereiche" Metriken aus…" — gewählt wird tatsächlich im Reiter **Wetter-Metriken** (`WeatherMetricsTab.svelte:808` setzt `wiz.activeMetricKeys`; `CorridorEditor.svelte` liest sie nur, Zeilen 62/189).

## Befund: es gibt keine hinterlegte Wahrheit, WARUM eine Größe fehlt

Das ist die zentrale Schwierigkeit dieser Scheibe.

- `MetricDefinition` (`metric_catalog.py:24-66`) kennt **nur** `selectable: bool` — ein globales Ein/Aus. **Kein** Feld wie `hourly_available`, `daily_only`, `alertable`, kein Kontext-Scope.
- Die Beschränkung des Stundenverlaufs auf 10 Größen lebt **ausschließlich** in der hartkodierten Frontend-Liste. Es gibt keine fachliche Quelle dafür.
- **Die naheliegende Begründung wäre teilweise unwahr:** `cloud_total_pct` ist stündlich vorhanden (`models.py:105`), Sonnenstunden sind pro Stunde ableitbar (`helpers.py:116-117` → `weather_metrics.py:285-310`). „Liegt nur als Tageswert vor" wäre für genau diese Größen **falsch**.

**Konsequenz für die Spec:** Ein Begründungstext darf nicht erfunden werden. Er muss aus einem **deklarierten** Feld stammen, das zusammen mit einem Vollständigkeits-Wächter gepflegt wird — Muster vorhanden aus A2b (`test_ac4_exemption_set_is_declared_and_complete`). Wo keine wahre Begründung existiert, ist die richtige Antwort **die Lücke schließen**, nicht sie beschriften.

## Existing Patterns (wiederverwenden, nicht neu bauen)

1. **`option-hint`-Absatz** — `WeatherMetricsTab.svelte:1537-1542` (CSS), eingesetzt u.a. `:927`. Der strukturell passendste Vorläufer ist `weather-metrics-vergleich-warn-hint` (`:992-995`): erklärt, warum „Amtliche Warnungen" **nicht** Teil der sortierbaren Liste ist. Exakt die gesuchte Gattung Hinweis.
2. **`.hourly-email-hint`** — `CompareHourlyLayoutControls.svelte:150-152,168-174`: „Erscheint nur in der E-Mail." Stilistisch identisch zu `option-hint`, aber als Duplikat geführt.
3. **`lockHint`** — `TripNewEditor.svelte:38-44`, `CompareNewEditor.svelte:65-71`: Grund-Text als **Datenfeld** neben dem Element, gerendert via `title=`. Vorbild für „Grund gehört ans Datum, nicht ins Markup".
4. **Empty-State:** uneinheitlich (inline `<p class="empty-state">` in ~7 Komponenten). `ui/empty-state/EmptyState.svelte` gilt für Editor-Kontexte als abgelöst (Regressionstest `routes/trips/issue_477_486.test.ts:73-77` verbietet den Import dort). → Inline-Muster verwenden.
5. **ID-Crosswalk:** `compareMetricMapping.ts` selbst ist das etablierte Muster; Scheibe B hat es zweimal nachgebaut (`compareHourlyCatalogIds.ts`, `alertMetricCatalogIds.ts`).

Keine Tooltip-Komponente im Repo — Hover-Erklärungen laufen über natives `title=`.

## Kollision mit #1406 Scheibe B — bestimmt den Zuschnitt

`docs/context/feat-1406b-stundenverlauf-katalog.md` (Analyse fertig, Workflow ruht seit 2026-07-30, Vorbedingung #1423 ✅ gefallen):

- #1406 B **schafft `compareHourlyMetricDefs.ts` ersatzlos ab** (Z.144) und hebt den Stundenverlauf auf den zentralen Katalog: **alle 24 Größen wählbar statt 10**.
- Damit **verschwindet die Stufe 26→10 der Kaskade** — sie wird geschlossen, nicht begründet.
- Dateiüberschneidung mit der Alarm-Fläche: **keine** (Z.197-207, das Dokument ordnet die Alarm-Liste ausdrücklich „#1406 Scheibe C" zu, also nicht seiner Scheibe B).

**Folge:** Würde #1401 C jetzt Begründungstexte für die 16 im Stundenverlauf fehlenden Größen bauen, wäre das Arbeit an einer Datei, die #1406 B abschafft — und teilweise mit unwahrem Text (s.o.).

## Dependencies

- **Upstream:** `src/app/metric_catalog.py` (Namensregister, seit A1 SSoT), `alertMetricTable.ts::ALERTABLE_METRICS` (Alarm-Vorrat, 13).
- **Downstream:** `AlarmeTab.svelte` ist geteilt (`context="route"|"vergleich"`) — jede Änderung wirkt auf **Trip und Vergleich**. Persistenz unberührt: `COMPARE_TO_ALERT_METRIC` wird nur lesend zur Ableitung sichtbarer Zeilen benutzt (`AlarmeTab.svelte:107-111`), Speicher-Keys ändern sich nicht.
- **Renderer-Mail-Gate (#811):** nicht betroffen, sofern der Umfang Frontend bleibt.

## Existing Specs

- `docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md` — Vorgänger-Scheibe, Beleg-/Teststil als Vorbild.
- `docs/specs/modules/fix_1401_a2_mailtabellen.md` — A2a/A2b, Muster „deklariertes Ausnahme-Set + Vollständigkeits-Wächter".
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — `AlarmeTab.svelte`.
- `docs/specs/modules/warn_unavailable_hint.md` (#1348, draft) — Prinzip „sichtbar statt kommentarlos weglassen", aber Backend/Mail, kein UI-Muster.
- `docs/context/fix-1366-leerauswahl-heisst-leer.md` — **andere** Regel: dort geht es um bewusst **leere** Auswahl (`[]` ≠ `None`), hier um **fehlende** Größen. Nicht verwechseln.

## Risiken

1. **Unwahre Begründung** — der größte Fallstrick, s.o. Gegenmittel: Grund muss deklariert + gewächtert sein; wo keiner existiert, Lücke schließen.
2. **Doppelarbeit / Wegwerf-Arbeit** an `compareHourlyMetricDefs.ts` wegen #1406 B.
3. **Teilungs-Invariante:** `AlarmeTab.svelte`/`AlertMetricLevelTable.svelte` sind geteilt — eine Compare-eigene Zweitkomponente wäre ein Verstoß (Anti-Pattern-Referenz #1170).
4. **Crosswalk-Erweiterung ist nutzersichtbar:** Wer heute „Wind" gewählt hat, sieht die Alarm-Zeile „Böen". Nach der Korrektur ist sie an „Böen" gebunden. Bestandsdaten (`metric_levels`) bleiben erhalten, aber die *Sichtbarkeit* einer Zeile ändert sich. Muss in den ACs stehen.

## Entscheidungen — PO-freigegeben 2026-07-31

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Umfasst C beide Flächen (Stundenverlauf + Alarme) oder nur die Alarme? | **Nur die Alarme.** Die Stufe 26→10 im Stundenverlauf wird von **#1406 B geschlossen** (Liste entfällt, alle Größen wählbar), nicht hier beschriftet. `compareHourlyMetricDefs.ts` wird in dieser Scheibe **nicht angefasst**. |
| E2 | Crosswalk nur entkreuzen oder auch die 4 unerreichbaren Größen anschließen? | **Beides.** „Böen" löst wieder den Böen-Alarm aus; `temperature_min`, `cape`, `freezing_level`, `humidity` werden erreichbar. **6 → 10 von 13.** |
| E3 | Wie erscheint der Grund für die dann noch fehlenden Größen? | **Ein Erklärsatz unter der Tabelle**, der die nicht alarmfähigen Größen namentlich nennt. Bestehendes Muster `weather-metrics-vergleich-warn-hint` (`WeatherMetricsTab.svelte:992-995`) wiederverwenden, keine neue Komponente, keine ausgegrauten Zeilen. |
| E4 | Was passiert mit den 3 Delta-Größen (`*_change`)? | Begründen, nicht anschließen — Änderungsraten, keine wählbaren Wettergrößen. Fallen unter den Satz aus E3. |

**Damit ist der Umfang von Scheibe C:**

1. Kreuz-Verdrahtung beheben (`gust_max_kmh` → `wind_gust`; `wind_max_kmh` verliert die falsche Zuordnung).
2. Vier unerreichbare Alarmgrößen anschließen.
3. Ein deklarierter, gewächteter Erklärsatz nennt die nicht alarmfähigen Größen samt Grund — kein erfundener Text, Vollständigkeits-Wächter nach A2b-Muster.
4. Leerzustand-Hinweis verweist auf den richtigen Reiter (**Wetter-Metriken** statt „Wertebereiche").

Alles in geteilten Bausteinen (`AlarmeTab.svelte`, `AlertMetricLevelTable.svelte`) — wirkt in Trip **und** Vergleich.
