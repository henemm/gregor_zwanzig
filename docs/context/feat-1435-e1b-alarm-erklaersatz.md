# Context + Analyse: #1435 Etappe E1b — Erklärsatz statt Leerstelle, Hinweis auf den richtigen Reiter

**Workflow:** `feat-1435-e1b-alarm-erklaersatz` · Standard Track · Issue #1435 (Etappe E1b)
**Vorgänger:** E1a-1 (`98d1a1f6`) und E1a-2 (`53f88757`), beide live.
**Herkunft:** Der sichtbare Rest von #1401 Scheibe C. Vorarbeit: `docs/context/fix-1401c-begruendung-fehlende-groesse.md` (angehalten, Befunde gültig).

## Request Summary

Zwei nutzersichtbare Punkte aus #1401 Scheibe C, die in E1a keinen Platz hatten:

1. **Erklärsatz** unter der Alarm-Tabelle: Wettergrößen, die der Nutzer ausgewählt hat, die aber
   keinen Alarm auslösen können, verschwinden heute **kommentarlos**. Sie sollen namentlich
   genannt und begründet werden (Invariante 2 des Epics: kein stilles Verwerfen).
2. **Leerzustand-Hinweis** verweist auf den **falschen Reiter**.

Die dritte Baustelle von #1401 C (Kreuz-Verdrahtung Wind→Böen, vier unerreichbare Größen)
ist mit **E1a-2 bereits erledigt** und nicht mehr Teil dieser Etappe.

## Befund 1 — der Leerzustand-Hinweis nennt in BEIDEN Kontexten den falschen Reiter

`AlarmeTab.svelte:251-254`:

```svelte
{#if effectiveActiveMetrics.length === 0}
  <p class="alarme-no-metrics-hint" data-testid="alarme-no-metrics">
    Wähle im Tab „Wertebereiche" Metriken aus, um Alarm-Schwellen zu konfigurieren.
  </p>
```

Gewählt werden die Größen tatsächlich im Reiter **„Wetter-Metriken"** — und zwar in **beiden**
Kontexten. Nachgemessen an den Reiter-Registern:

| Kontext | Reiter-Register | „Wetter-Metriken" | „Wertebereiche" |
|---|---|---|---|
| Ortsvergleich | `compareTabsResolve.ts:13-14` | `wetter-metriken` | `idealwerte` |
| Tour | `TripTabs.svelte:80-81` | `weather` | `alerts` |

**Folge für den Zuschnitt:** Der Hinweis braucht **keine** Kontext-Weiche — die Beschriftung ist
in Tour und Vergleich identisch. Eine Textkorrektur an einer Stelle genügt.

## Befund 2 — der Erklärsatz kann heute NUR im Ortsvergleich wahr sein

Das ist der Knackpunkt dieser Etappe. Die beiden Kontexte speisen die Alarm-Tabelle aus
**verschiedenen Quellen** (`AlarmeTab.svelte:116-123`):

| Kontext | Quelle der sichtbaren Zeilen | Kennt die Metrik-Auswahl des Nutzers? |
|---|---|---|
| **vergleich** | `wiz.activeMetricKeys` × Register-Katalog (`activeAlertMetricsFromCatalog.ts:19-30`) | **ja** — Auswahl und Katalog liegen beide an |
| **route** | `Object.keys(trip.display_config.metric_alert_levels)` (`AlarmeScheduleTab.svelte:35-38`) | **nein** — das sind die bereits gesetzten Schwellen, nicht die Auswahl |

Im Tour-Kontext gibt es also gar keine Liste „vom Nutzer gewählt, aber nicht alarmfähig", aus
der ein wahrer Satz gebildet werden könnte. Der Container reicht weder die Metrik-Auswahl noch
den Katalog durch (`AlarmeScheduleTab.svelte:44-53` — kein `catalog`-Prop).

Der Vorgänger-Kontext hat diese Lücke bereits als eigene Aufgabe markiert
(`AlarmeTab.svelte:114-115`: „route: aus Props (Ermittlung aus trip ist S3-Aufgabe)").

**Das ist keine Verletzung der Teilungs-Invariante**, sondern ein Datenverfügbarkeits-Unterschied:
derselbe geteilte Baustein, dieselbe Ableitungsfunktion — im Tour-Kontext fehlt schlicht die
Eingabe. Eine Compare-eigene Zweitkomponente wäre ein Verstoß (Anti-Pattern #1170) und ist
ausdrücklich **nicht** vorgesehen.

## Befund 3 — welche Größen der Satz nennen würde

Am heutigen Register nachgemessen (`get_compare_metric_catalog()`, 26 Einträge):
**10 alarmfähig, 16 nicht.**

Nicht alarmfähig (Kandidaten für den Erklärsatz, sofern gewählt):
Schneehöhe · Sonnenstunden · Bewölkung · UV-Index · Regenwahrscheinlichkeit · Windrichtung ·
Gefühlte Temperatur (Minimum) · Gefühlte Temperatur (Maximum) · Luftfeuchtigkeit · Taupunkt ·
Schneefallgrenze · Niederschlagsart · Tiefe Wolken · Mittelhohe Wolken · Hohe Wolken · Luftdruck

Zwei Detailpunkte:

- **`label` allein ist mehrdeutig.** „Temperatur" und „Gefühlte Temperatur" kommen je zweimal vor
  (Minimum/Maximum). Der Satz muss `label` + `aggregation_label` verbinden — dasselbe Muster,
  das `CompareOutlookLayoutControls.svelte:121-122` und `WeatherMetricsTab.svelte:951` bereits
  verwenden. Namen kommen **aus dem Register**, nicht aus einer neuen Textliste (Kernregel #1435).
- **Luftfeuchtigkeit** ist der in E1a-1 dokumentierte Sonderfall: bewusst nicht deklariert, weil
  die Auswertungskette sie nicht erreicht. Sie fällt hier unter den Erklärsatz — genau so war es
  im E1a-1-Bericht angekündigt.
- Die drei **Änderungsraten** (`*_change`) sind seit E1a-2 über Wind/Temperatur/Niederschlag
  erreichbar. Die Festlegung E4 aus dem 1401-C-Kontext („Delta-Größen begründen, nicht
  anschließen") ist damit gegenstandslos.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | **Hauptort.** Leerzustand `:251-254`, Tabelle `:250-261`, Ableitung `:116-123` |
| `frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts` | Ableitungsfunktion aus E1a-2 — hier gehört das Gegenstück „nicht alarmfähig" hin |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | Tour-Container; liefert `activeMetrics` aus `metric_alert_levels`, **kein** Katalog |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1422` | Einbettung 1 (Vergleichs-Hub) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:412` | Einbettung 2 (`/compare/new`, Desktop) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:499` | Einbettung 3 (`/compare/new`, mobil) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:992-995` | **Vorbild-Muster** `option-hint` für erklärende Hinweise |
| `src/output/renderers/compare_metric_catalog.py:281-282` | Herkunft von `alertMetric`/`alarmCapable` |

**Vier** Einbettungen insgesamt — drei davon Vergleich. Genau hier lag der Adversary-Befund F001
aus E1a-2 (`/compare/new` wurde übersehen). Jede Einbettung muss einzeln geprüft werden.

## Existing Patterns

1. **`option-hint`-Absatz** (`WeatherMetricsTab.svelte:992-995`, Testid
   `weather-metrics-vergleich-warn-hint`) — erklärt, warum „Amtliche Warnungen" nicht Teil der
   sortierbaren Liste sind. Exakt dieselbe Gattung Hinweis. Wiederverwenden, keine neue Komponente.
2. **Anzeigename aus dem Register** — `label` + `aggregation_label`, s.
   `CompareOutlookLayoutControls.svelte:70,121-122`.
3. **Reine Ableitungsfunktion in eigener Datei** — `activeAlertMetricsFromCatalog.ts` (E1a-2),
   testbar ohne Komponenten-Rendering.
4. **Leerzustand inline** (`<p class="empty-state">`), nicht `ui/empty-state/EmptyState.svelte` —
   dessen Import ist in Editor-Kontexten per Regressionstest verboten
   (`routes/trips/issue_477_486.test.ts:73-77`).

## Dependencies

- **Upstream:** `alertMetric` aus dem Register (E1a-1), `wiz.activeMetricKeys`, Katalog-Prop
  (E1a-2 führte sie ein).
- **Downstream:** `AlarmeTab.svelte` ist geteilt (`context="route"|"vergleich"`) — jede Änderung
  wirkt auf Tour **und** Vergleich.
- **Nicht betroffen:** Persistenz (nur lesende Ableitung), Backend, Go-Schicht, Mail-Renderer,
  Renderer-Mail-Gate #811. Der Umfang bleibt Frontend.

## Existing Specs

- `docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md` — direkter Vorgänger, Beleg-/Teststil
- `docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md` — Registerfelder, Wirksamkeits-Wächter
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — `AlarmeTab.svelte` selbst
- `docs/specs/modules/warn_unavailable_hint.md` (#1348) — Prinzip „sichtbar statt kommentarlos weglassen"
- `docs/context/fix-1366-leerauswahl-heisst-leer.md` — **andere** Regel (bewusst leere Auswahl
  `[]` ≠ `None`), nicht verwechseln

## Risiken

1. **Unwahrer Text.** Der Satz darf nur behaupten, was das Register deklariert. Namen und
   Alarmfähigkeit kommen aus dem Katalog, nie aus einer neuen Textliste — sonst entstünde genau
   die Liste, gegen die #1435 gebaut wird.
2. **Tour-Kontext.** Ein Satz, der im Tour-Kontext aus `metric_alert_levels` gebildet würde, wäre
   sachlich falsch (das sind gesetzte Schwellen, keine Auswahl). Offene Entscheidung, s.u.
3. **Vier Einbettungen.** Nachweis muss jede einzeln treffen (Fehlerklasse E1a-2/F001, #1320).
4. **Länge des Satzes.** Bei „alle 26 Größen gewählt" nennt er 16 Namen. Darstellungsfrage,
   gehört in die Spec.
5. **Leerauswahl-Kante.** `activeMetricKeys = null` („nie geöffnet", Default = alle) verhält sich
   anders als `[]` („bewusst leer"). `materializeActiveMetricKeys` regelt das bereits — der neue
   Satz muss dieselbe Materialisierung benutzen, nicht eine zweite.

## Offene Entscheidung für die Spec (PO)

**Gilt der Erklärsatz auch bei Touren?**

- **Empfehlung (Tech Lead): nein, in dieser Etappe nicht.** Im Tour-Kontext fehlt die
  Eingabe (Befund 2). Sie nachzuliefern heißt: Metrik-Auswahl und Katalog durch den
  Tour-Container reichen — das ist ein eigener Eingriff mit eigenem Nachweis und würde diese
  kleine Etappe verdoppeln. Der **Reiter-Hinweis** wird in beiden Kontexten korrigiert, weil er
  dort ein reiner Textfehler ist.
- Alternative: beides in einem Zug, dafür deutlich größerer Umfang und ein zweiter
  Datenpfad, der mitgeprüft werden muss.

Zweiter Punkt für die Spec: **Wortlaut** des Erklärsatzes.
