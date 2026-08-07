# Context: fix-1544-1545-alarm-zeilen-ableitung

**Issues:** #1544 (Neuer Trip kann Alarme nicht erstmalig einrichten) + #1545 (wirkungslose Zeile Luftfeuchtigkeit)
**Track:** Full Process · **Erstellt:** 2026-08-07
**Vorgeschichte:** Beide ausgegliedert aus #1435 E4 (PO-Entscheid 2026-08-06). Die E4-Spec kündigt #1545 wörtlich als Folge-Ticket an.

## Request Summary

Der Trip-Editor leitet die Zeilen seiner Alarm-Tabelle aus den **persistierten Schlüsseln**
(`Object.keys(display_config.metric_alert_levels)`) ab, der Ortsvergleich dagegen aus
**Auswahl × Katalog**. Aus diesem einen Unterschied folgen drei nutzersichtbare Fehler.

## 🔴 Der Befund, der in keinem der beiden Tickets steht

Die Tickets beschreiben den Fehler als „Alarme lassen sich nicht einrichten". **Gemessen am echten
Datenbestand ist er das Gegenteil: die Alarme sind bereits scharf — nur unsichtbar und nicht
abschaltbar.**

Ursache ist ein Auffüll-Mechanismus im Backend (`src/services/alert_preset.py:309-348`): fehlt für
eine im Reiter *Wetter-Metriken* aktivierte, alarmfähige Größe ein Eintrag in
`metric_alert_levels`, wird stillschweigend `standard` angenommen — und daraus entsteht eine
**scharfe** Regel im Live-Detektor (`deviation_alert_engine.py:191-198`), keine bloße Anzeige.

### Messung an den 14 echten Trips

Gelesen aus `data/users/*/briefings/*.json` (der maßgebliche Pfad seit #1250 S7a; `trips/` wird
laut `internal/store/trip.go:215-216` nicht mehr geschrieben). Regeln nicht nachgerechnet, sondern
mit dem echten Produktivcode erzeugt: `load_trip_from_dict()` → Guard aus
`deviation_alert_engine.py:186-191` → `expand_per_metric_levels()`.

| Fehlerklasse | Betroffen | Wirkung |
|---|---|---|
| **1 — unsichtbare Scharfschaltung** | **12 von 14** | 6–9 scharfe Regeln je Trip, **null** Zeilen im Datensatz. Kein Bedienelement existiert, über das der Nutzer sie sehen oder abschalten könnte. Keine einzige Nutzerentscheidung dahinter. |
| **2 — Geisterzeile Luftfeuchtigkeit** | **2 von 14** | Zeile sichtbar, löst nie aus (seit #889/ADR-0010 backendseitig hart ausgeschlossen). Seit E4 zeigt sie „—" statt der irreführenden Zahl. |
| **3 — vorgetäuschte Kontrolle** | **2 von 14** | Der Nutzer hat 13 Zeilen auf echte Stufen gesetzt (**nicht** „aus"); real wirken nur 8 bzw. 6. Bei „Lottis Abschiedfahrradtour" sind **7 von 13** Zeilen auf `standard` und trotzdem stumm, weil die zugehörige Wetter-Metrik im anderen Reiter nicht aktiviert ist. |

**Kein einziger der 14 Trips zeigt korrekt an, was tatsächlich wirkt.**

Klasse 3 steht in **keinem** der beiden Tickets. Verwerfende Stelle: `alert_preset.py:278-283` via
`is_alert_metric_active()` (`weather_change_detection.py:181-221`) — dokumentiert als gewollte
„Deaktivieren-Lücke" (#961), aus Nutzersicht aber nicht von einem echten „aus" zu unterscheiden.

Der in #1544 vermutete Fall „ganz frischer Trip bekommt gar keinen Detektor" kommt im realen
Bestand **nicht** vor — jeder Trip hat mindestens eine Wetter-Metrik aktiviert.

## Der Lösungsweg löst alle drei Klassen mit einem Schnitt

Leitet der Trip-Reiter seine Zeilen aus **Auswahl × Katalog** ab (wie der Ortsvergleich seit
#1435 E1a-2, `53f88757`), fällt jede Klasse für sich weg:

| Klasse | Warum sie verschwindet |
|---|---|
| 1 | Für jede aktivierte alarmfähige Größe entsteht eine Zeile — genau die Menge, die der Backfill scharf schaltet. Sichtbar und änderbar. |
| 2 | Luftfeuchtigkeit ist im Register nicht alarmfähig → keine Zeile. |
| 3 | Nicht aktivierte Größen liefern keine Zeile mehr → keine Stufe ohne Wirkung. Der gespeicherte Wert bleibt liegen und wirkt wieder, sobald die Größe erneut aktiviert wird. |

Die Anzeige zeigt damit deckungsgleich, was das Backend auswertet — heute weichen beide voneinander ab.

## ⚠️ Zwei Fallen, die ohne Messung zugeschnappt wären

**Falle 1 — den toten Code wiederbeleben.** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`
(nachgemessen nirgends eingebunden; einziger Treffer ist eine negative Assertion in
`corridorEditorMobile.test.ts:193`) trägt mit `activeAlertableMetrics()` +
`CATALOG_TO_ALERT_METRICS` (`alertMetricTable.ts:266-311`) bereits eine fertige Übersetzung. Sie
führt aber weiterhin `humidity: ['humidity']` (`:277`) — ein naiver Fix würde **#1545
verschlimmern** und eine weitere handgepflegte Liste zementieren (gegen #1435).

**Falle 2 — den Vergleichs-Katalog recyceln.** `GET /api/compare/metrics` liefert die Alarm-Identität
fertig mit (`alertMetric`), `GET /api/metrics` nicht. Naheliegend wäre, ihn auch für Trips zu
nutzen. Das verschluckt zwei Alarmzeilen: **`temperature_change` und `precipitation_change` sind
über keinen Compare-Auswahlschlüssel erreichbar** — der Vergleichskatalog führt Temperatur nur als
`max`/`min`. Trips können beides. Belegt an allen 26 Compare-Einträgen.

→ Die Ableitung muss auf Ebene der **Metrik-Kennung** gegen das zentrale Register laufen.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte:36-42` | **Der Fehler.** `activeMetrics = Object.keys(metricLevels)` |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:135-147` | Geteilter Baustein, `context`-Weiche; Vergleichs-Zweig als Vorbild |
| `frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts:19-68` | `deriveActiveAlertMetricsFromCatalog` — das Vorbild, aber auf Compare-Keys |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:185-197, 266-311` | `ALERTABLE_METRICS` (13, enthält `humidity`) + tote Übersetzungstabelle |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte:70-79` | Rendert ungefiltert; Filterung ist Sache des Aufrufers |
| `api/routers/config.py:58-107` | `GET /api/metrics` — gibt Alarm-Identität **nicht** vollständig heraus |
| `src/app/metric_catalog.py:591-619` | `alert_metric_for(metric_id, aggregation)` — existiert, nicht exponiert |
| `src/services/alert_preset.py:143-350` | Backfill (`:309-348`), „off" (`:275-276`), Verwerfen (`:278-283`) |
| `src/services/weather_change_detection.py:181-221` | `is_alert_metric_active` — Kopplung an den Wetter-Reiter |
| `src/output/renderers/trip_metric_ids.py:29-57` | Drei Zustände + Vorgabesatz (7 Kennungen) |

## Zahlen aus dem Register (gelesen, nicht geschätzt)

- 27 Katalog-Einträge, davon 25 wählbar (`temperature_cold`, `confidence` haben `selectable=False`)
- **9** Größen sind alarmfähig, 16 nicht
- **12** Alarm-Identitäten insgesamt (9 aus `alert_metrics`, 3 aus `change_alert_metric`) — eine Größe
  kann mehrere tragen (`temperature` → `min`/`max`/`change`)
- Frontend führt **13**; die Differenz zur generierten Backend-Datei ist exakt `{humidity}` und in der
  Gegenrichtung leer. **Luftfeuchtigkeit ist die einzige Geisterzeile.**

## Bindende Entscheidungen

| Quelle | Bindender Inhalt |
|---|---|
| **ADR-0010** | Luftfeuchtigkeit ist Vorboten-Größe, kein Alarm-Auslöser. Enum bleibt für Altdaten. → Entfernen aus der Anzeige ist ADR-konform. |
| **ADR-0032** | Progressive Tab-Editoren, kein Wizard. → Lösung bleibt im Reiter, **kein** neuer Onboarding-Schritt. |
| **ADR-0043** | Empfindlichkeitsstufe ist der einzige Alarm-Regler. → keine zweite Steuergröße einführen. |
| **#946 AC-4** | „…einen Onboarding-Zustand … **und keinen stillen Standard-Preset**." Der Mechanismus wurde in `AlertsTab.svelte` gebaut und ist heute toter Code. **Der stille Standard existiert trotzdem — im Backend-Backfill.** Die Zeilen anzuzeigen macht sichtbar, was ohnehin gilt; es schafft ihn nicht. |
| **#1258 S3 D4** | Hat die Ableitung aus persistierten Schlüsseln für den Trip-Pfad festgeschrieben — die Stelle, die heute der Fehler ist. |
| **#1435 E1a-2** | Stellte **nur** den Vergleichs-Zweig um, AC-3 ausdrücklich: „Trip-Zweig bleibt unangetastet". Ab da liefen die Pfade auseinander. |
| **Teilungs-Invariante** | Ableitungslogik gehört nach `shared/alarme-tab/`. Eine **neue** Datei unter `trip-detail/**` löst die Pendant-Sperre aus; Änderungen an der bestehenden `AlarmeScheduleTab.svelte` sind frei. |

## ⚠️ Test, der dem Fix im Weg steht

`frontend/src/lib/components/shared/__tests__/alarme_tab_catalog_prop_structure.test.ts` prüft per
AST (AC-7 aus #1258):

- `:246-268` — der `context==='route'`-Zweig in `AlarmeTab.svelte` darf **ausschließlich**
  `activeMetrics` lesen, nie `catalog` / `deriveActiveAlertMetricsFromCatalog` / `wiz`
- `:270-284` — `AlarmeScheduleTab.svelte` darf **keinen** `catalog`-Prop an `<AlarmeTab>` übergeben

Der Test zementiert exakt die Trennung, die den Fehler verursacht. **Regelkonformer Ausweg:**
`activeMetrics` bereits fertig berechnet in `AlarmeScheduleTab.svelte` übergeben (dort ist die
Katalog-Nutzung nicht verboten) — dann bleibt `AlarmeTab.svelte` unberührt und der Test grün. Ob das
trägt oder der Test begründet zu ändern ist, entscheidet die Spec, nicht die Implementierung.

## Persistenz

- Python `src/app/models.py:667`: `metric_alert_levels: Optional[dict[str,str]]` — freies Dict
- Go `internal/model/trip.go:111`: `DisplayConfig map[string]interface{}` — untypisiertes JSON
- `internal/handler/config_merge.go:11-22`: **flacher** Top-Level-Merge. Nicht mitgesendete Keys
  bleiben; ein mitgesendetes `metric_alert_levels` **ersetzt** den ganzen bisherigen Wert.
- Migrationen existieren nur für `snow_line`→`freezing_level` (`loader.py:716-730`,
  `internal/store/trip.go:283-299`). Für `humidity` gibt es **keine** — #889 lieferte keine mit,
  deshalb überlebt der Schlüssel bis heute.

## Offene Frage für die Spec (PO-Entscheidung)

**Umfang.** Klasse 3 (vorgetäuschte Kontrolle) steht in keinem Ticket, verschwindet aber durch
denselben Fix. Zwei Wege:

- **A — mitnehmen** (Empfehlung): ein Schnitt, eine Ableitung, alle drei Klassen weg. Kein
  Mehraufwand in der Umsetzung, aber die ACs müssen es abdecken, sonst ist es ungeprüfte Wirkung.
- **B — Klasse 3 ausgliedern**: kleinerer Nachweis, aber der Fix ändert das Verhalten ohnehin — dann
  bliebe eine Wirkung ohne AC, genau das Muster, das #1435 dreimal Findings gekostet hat.

**Migration der `humidity`-Schlüssel:** nicht nötig. 2 Trips tragen den Schlüssel, er wirkt schon
heute nicht, und die neue Ableitung zeigt ihn nicht mehr an. Ein Aufräumen wäre kosmetisch und
brächte Datenrisiko ohne Nutzen.

## Risks

- **Verhaltensänderung ist Sichtbarmachung, keine Neuerung** — die 6–9 Regeln je Trip laufen bereits.
  Der Nutzer sieht künftig Zeilen, die er nie gesetzt hat. Das ist beabsichtigt und muss in der
  Oberfläche als „gilt derzeit" lesbar sein, nicht als „du hast das eingestellt".
- Nach dem Fix kann der Nutzer diese Regeln erstmals auf „aus" stellen — das **verringert** Alarme
  gegenüber heute. Erwünscht, aber eine echte Änderung am Versand.
- ~~Der Trip-Katalog kennt heute keine Alarm-Identität; `GET /api/metrics` muss sie liefern → Backend-Änderung.~~
  **Korrigiert 2026-08-07 nach Nachmessung an der Route:** `GET /api/metrics` liefert
  `aggregations[].alert_metric` (`api/routers/config.py:98-105`) und `change_alert_metric`
  (`:89`) **bereits**. Nur der Frontend-Typ `MetricEntry` (`frontend/src/lib/types.ts:159-194`)
  nimmt beide Felder nicht auf. Der Umfang ist damit **frontend-only** — eine additive
  Typ-Erweiterung, kein Backend-Change.
- Volle Staging-Verifikation trotzdem: es ändert sich sichtbares Verhalten an echten Trip-Daten
  (6–9 Regeln je Trip werden erstmals sichtbar und abschaltbar). Der Frontend/Backend-Schnitt ist
  dafür nicht das Kriterium.
- `frontend`-Änderung ⇒ Pflicht-Prüfung im echten Browser (PO-Vorgabe 2026-08-07, #1552).

## 🔴 Zwei Fallen aus der Strategie-Bewertung (beide heute ungetestet)

**Falle 3 — der Altbestands-Sonderfall.** `is_alert_metric_active()`
(`weather_change_detection.py:213-216`) behandelt einen Trip mit leerem/fehlendem
`display_config.metrics` als „**jede** alarmfähige Größe ist aktiv" — bewusst konservativ, damit
Alt-Trips keinen stillen Alarmverlust erleiden. Eine naive Frontend-Ableitung („keine `metrics[]`
→ keine aktiven Größen → keine Zeilen") zeigt für genau diese Trips **wieder null Zeilen**, während
das Backend alles scharf hat — ein Rückfall in Klasse 1, unbemerkt von jedem Test, der nur Trips
mit gesetztem `metrics[]` prüft. Braucht eigenen AC.

**Falle 4 — Datenverlust beim Speichern.** `buildAlarmeDeliveryPayload`
(`alarmeDeliveryPayload.ts:117-121`) sendet `metric_alert_levels` als **vollständigen Ersatz**; der
Go-Merge ist flach (`config_merge.go:11-22`), der Top-Level-Key wird komplett überschrieben. Heute
trägt die `metricLevels`-Prop den **ungefilterten** gespeicherten Dict
(`AlarmeScheduleTab.svelte:36-38`). Ein naiver Fix, der sie mitfiltert („was nicht angezeigt wird,
muss man auch nicht speichern"), löscht beim nächsten Speichern die Stufen aller deaktivierten
Größen. **Die beiden Props müssen aus getrennten Quellen kommen: `activeMetrics` gefiltert,
`metricLevels` ungefiltert.** Braucht eigenen AC.

## Geklärt: der AC-7-Test steht dem Fix nicht im Weg

`alarme_tab_catalog_prop_structure.test.ts` prüft (a) die Bezeichner im `route`-Zweig von
`AlarmeTab.svelte` und (b) die Attribut-Allowlist der `<AlarmeTab>`-Einbettung in
`AlarmeScheduleTab.svelte` (`:284-293`). Rechnet `AlarmeScheduleTab.svelte` die Ableitung **selbst**
und übergibt weiterhin nur `activeMetrics` unter demselben Namen, bleiben beide Prüfungen grün —
`AlarmeTab.svelte` wird nicht angefasst, die Attributliste ändert sich nicht. Der Test bewacht die
Grenze zwischen den Komponenten, nicht die Datenquelle innerhalb des Containers. **Kein Testumbau,
kein AC-7-Konflikt.** Im Adversary trotzdem mitlaufen lassen statt anzunehmen.

## Technischer Ansatz (entschieden)

1. `MetricEntry` in `frontend/src/lib/types.ts` additiv erweitern: `alert_metric` in
   `aggregations[]`, `change_alert_metric` am Interface (~6 Zeilen).
2. Geteilte Ableitung unter `frontend/src/lib/components/shared/alarme-tab/` — Kern
   `alertIdentitiesForMetricEntry(entry)`: liest `aggregations[].alert_metric` **und**
   `change_alert_metric`, dedupliziert. Belegt durch die Messung: ein Trip mit aktivierter
   Temperatur erzeugt real alle drei Identitäten (`temperature_min=5`, `temperature_max=6`,
   `temperature_change=10`) — beide Quellen zusammen, nicht die eine oder die andere.
   Reihenfolge stabil über `ALERTABLE_METRICS`, sonst springen Zeilen bei jedem Speichern.
3. `AlarmeScheduleTab.svelte` umverdrahten; `metricsCatalog` von `TripTabs.svelte:232`
   durchreichen — dort bereits geladen (`:199`), **kein neuer Abruf**.
4. **Keine** Vereinheitlichung mit `deriveActiveAlertMetricsFromCatalog`: das arbeitet auf
   Compare-Auswahlschlüsseln, Trip auf nackten Metrik-Kennungen. Gemeinsamer Kern, zwei Aufrufer —
   eine erzwungene gemeinsame Signatur liefe genau in Falle 2.

**Umfang:** ~60–90 LoC produktiv, **eine Scheibe** (Limit 250). Ein Schnitt schadete hier: alle drei
Fehlerklassen hängen an derselben Ableitung, ein Zwischenstand zeigt keine korrekte Zeilenliste.

## Nebenbefunde (nicht in diesem Workflow)

- **#1435 Ticket-Body führt E4 noch als offen**, obwohl am 6.8. live (`2a31fd60`). Genau dieses
  Muster hat dort schon einmal eine Falschbuchung über drei Stellen fortgeschrieben → Body nachziehen.
- `tripActiveMetricNames.ts:27` verweist auf `trip_report.py:119`, die Bedingung steht heute in
  `:127` — veralteter Kommentar, Logik identisch.
- Verwaister Workflow-State `fix-1544-1545-trip-alarm-onboarding` (behauptete Phase 6, Spec
  freigegeben, rote Tests — nichts davon existierte) → abgebrochen, gebucht in #1197.
