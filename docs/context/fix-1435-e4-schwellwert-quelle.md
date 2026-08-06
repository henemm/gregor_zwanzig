# Context: fix-1435-e4-schwellwert-quelle

## Request Summary

Etappe E4 aus #1435: Die Schwellwert-Tabelle („ab welchem Wert löst eine Wettergröße
Alarm aus", je Empfindlichkeitsstufe entspannt/standard/sensibel) existiert zweimal
handgepflegt — einmal im Python-Backend, einmal im Frontend. Die *Deklaration* soll auf
eine Quelle zusammengeführt werden; über die *Zahlen* entscheidet der PO.

## Messung: die beiden Tabellen weichen ab

Zahl-für-Zahl-Vergleich `_PRESET_TABLE` (Backend) gegen `METRIC_PRESETS` (Frontend),
Reihenfolge entspannt/standard/sensibel:

| Metrik | Backend | Frontend | Urteil |
|---|---|---|---|
| `freezing_level` (Nullgradgrenze) | 600/400/200 | **400/200/100** | **weicht ab** |
| `snow_line` | — | 600/400/200 | nur Frontend |
| `humidity` | — | 25/15/10 | nur Frontend |
| 11 weitere (`wind_gust`, `cape`, `visibility`, …) | | | deckungsgleich |

### Der heute sichtbare Fehler: Nullgradgrenze

`freezing_level` steht in `ALERTABLE_METRICS` (`alertMetricTable.ts:215`) und wird
gerendert, sobald der Nutzer die Nullgradgrenze auswählt — die Zeile existiert seit
E1a-2. Der angezeigte Schwellwerttext kommt aus `levelToThreshold()`, das
`METRIC_PRESETS` liest. **Der Nutzer sieht also „Δ ≥ 200 m" bei Standard, während das
Backend erst bei 400 m alarmiert.** Anzeige und Wirkung widersprechen sich.

Ursache vermutlich #959: Dort wurde `snow_line` backendseitig auf `freezing_level`
konsolidiert und die snow_line-Schwellen 600/400/200 übernommen. Das Frontend behielt
beide Zeilen — `snow_line` mit den richtigen Zahlen, `freezing_level` mit den alten
eigenen. Zu verifizieren in der Analyse-Phase.

### Zwei tote Zeilen

- `snow_line` steht **nicht** in `ALERTABLE_METRICS` → wird nie gerendert.
- `humidity` steht zwar drin, ist aber seit #889/ADR-0010 im Register bewusst nicht als
  alarmfähig deklariert → kommt nie über den Katalog herein.

Beide sind Kandidaten für ersatzloses Löschen — das war schon in E3a der größere Gewinn.
**Vor dem Löschen die Einbindung erneut messen**, nicht den Quelltext lesen (in #1435
dreimal die Ursache falscher Prämissen).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_preset.py:39-53` | `_PRESET_TABLE` — 13 Metriken × 3 Stufen, die wirksame Quelle |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts:42-95` | `METRIC_PRESETS` — die abgetippte Kopie |
| `frontend/.../alertMetricTable.ts:20-36` | `METRIC_DEFAULTS` — drittes Zahlen-Set (Fallback ohne Preset) |
| `frontend/.../alertMetricTable.ts:246` | `levelToThreshold()` — einziger Leser von `METRIC_PRESETS` |
| `frontend/.../AlertMetricLevelRow.svelte:5` | ruft `levelToThreshold()`, rendert den Text |
| `frontend/.../shared/AlarmeTab.svelte:282` | bindet `AlertMetricLevelTable` ein — **lebendiger** Pfad, Trip **und** Vergleich |
| `scripts/generate_alert_metric_mapping.py` | Erzeuger-Muster aus E5, direkt übertragbar |
| `src/services/compare_alert.py:25`, `weather_change_detection.py:712`, `deviation_alert_engine.py:183` | Konsumenten der Backend-Tabelle |

**Tot:** `AlertMetricTable.svelte` (nur ein Kommentar-Verweis in `ListTable.svelte:10`),
`AlertsTab.svelte` (durch CorridorEditor ersetzt) — nicht mit `AlertMetricLevelTable`
verwechseln, das ist der lebendige Pfad.

## Existing Patterns

- **ADR-0045 (aus E5):** generiertes, eingechecktes Artefakt statt Laufzeit-Kopplung oder
  Handkopie. Python bleibt Quelle, ein Erzeuger-Skript schreibt JSON, das Frontend
  importiert es direkt. Für E4 unmittelbar übertragbar — und hier **einfacher als bei
  E5**, weil keine Go-Seite betroffen ist.
- **Frische-Ratsche** (`test_alert_metric_mapping_parity.py`): fängt Drift zwischen
  Quelle und generiertem Artefakt.
- **Ratsche in der Testschicht** (aus E3b), falls eine Schichtgrenze eine direkte
  Kopplung verbietet.

## Dependencies

- **Upstream:** `AlertMetric`/`AlertRuleKind` aus `src/app/models.py`; Empfindlichkeits-
  stufen aus #1460 (`ORDINAL_LEVEL_BOUNDS` für `thunder_level` — Niveau statt Delta,
  liegt neben der Zahlentabelle und ist **nicht** Teil davon).
- **Downstream:** Alarmregel-Erzeugung beim Speichern eines Trips/Vergleichs; die
  Schwellwert-Anzeige im Alarme-Reiter beider Editoren.

## Existing Specs

- `docs/specs/modules/fix_1435_e5_alert_mapping_unify.md` — direktes Vorbild
- `docs/specs/modules/feat_864_859_alert_presets.md` — Herkunft der Zahlen
- `docs/adr/0045-generiertes-eingebettetes-artefakt-fuer-cross-stack-abbildung.md`
- `docs/adr/0043-empfindlichkeitsstufe-als-niveau-statt-zweiter-alarm-typ.md`

## Risks & Considerations

1. **Die Nullgradgrenzen-Zahlen sind eine PO-Entscheidung, keine Bugfix-Automatik.**
   E4 wurde ausdrücklich als einzige Etappe mit erneutem PO-Entscheid geführt: Zahlen
   könnten absichtlich unterschiedlich eingestellt sein. Hier gilt Backend = wirksam,
   also ist Frontend-anpassen die naheliegende Richtung — vorlegen, nicht annehmen.
2. **`METRIC_DEFAULTS` ist ein drittes Zahlen-Set** mit anderem Zweck (Fallback ohne
   Preset). Nicht ungeprüft mit einziehen — sonst wird aus der Zusammenführung ein
   verstecktes Verhaltensänderung.
3. **`thunder_level` hat zwei Steuerungen**: Delta-Zahl (1/1/1) und Niveau-Grenzen aus
   #1460. Eine Zusammenführung, die nur die Zahl zieht, lässt die halbe Wahrheit im
   Backend — in der Spec als Grenze benennen.
4. **Tote Zeilen erst nach Messung löschen** (Lehre aus E3a/E3b).
5. **Neue Ratsche muss beim Einführen gebrochen werden** — ein Wächter zählt erst, wenn
   jemand die geschützte Sache kaputtgemacht und gesehen hat, dass er anschlägt.

---

# Analysis

## Type

**Bug im Gewand einer Aufräum-Etappe.** E4 war als reine Zusammenführung geplant; die
Messung fand **zwei nutzersichtbare Fehler**, die genau aus der doppelten Pflege folgen.

## Fund 1 — Nullgradgrenze: Anzeige widerspricht Wirkung

Hergang belegt (`git show e6eac45d`, `git show b65f22a0`):

- **#946** führte `freezing_level` ein, damals **neben** `snow_line` als getrennte Größe.
  Backend und Frontend waren identisch: `freezing_level` 400/200/100, `snow_line` 600/400/200.
- **#959** legte beide backendseitig zu einer Größe zusammen und übernahm die
  `snow_line`-Zahlen 600/400/200. Derselbe Commit fasste im Frontend `ALERTABLE_METRICS`
  und die Katalog-Zuordnung an — **`METRIC_PRESETS` aber nicht.** Die Zahlen wurden vergessen.

**Es braucht dafür keine neue PO-Entscheidung.** `docs/adr/0019-nullgradgrenze-eine-alert-metrik.md`
Punkt 4 legt die Preset-Schwellen der konsolidierten Metrik ausdrücklich auf
**600/400/200 m** fest. E4 setzt eine bestehende Entscheidung durch; das Alarmverhalten
ändert sich nicht, nur die Anzeige wird ehrlich.

## Fund 2 — Luftfeuchtigkeit ist ein Geister-Bedienelement (nur Trip-Pfad)

Gemessen über `expand_per_metric_levels()`:

```
Eingabe: {'humidity':'standard', 'snow_line':'sensibel', 'wind_gust':'standard'}
Erzeugte Regeln: [('freezing_level', 200.0), ('wind_gust', 20.0)]
humidity erzeugt Regel? False
```

Ursache ist ein **Absicherungs-Unterschied zwischen den beiden Editoren** (`AlarmeTab.svelte:121`):

| Pfad | Woher die Zeilenliste kommt | Folge |
|---|---|---|
| **Vergleich** | Katalog **und** `ALERTABLE_METRICS` gefiltert | Luftfeuchtigkeit erscheint nicht |
| **Trip** | `Object.keys(metricLevels)` — die **persistierten** Schlüssel, roh (`AlarmeScheduleTab.svelte:39`) | Luftfeuchtigkeit erscheint, wenn gespeichert |

Solche Werte sind real entstanden: Luftfeuchtigkeit war seit #864/#859 (`8682a645`)
wählbar; das Backend entfernte das Preset erst mit #889 (`f9275fd3`). Wer damals gespeichert
hat, sieht heute im Trip-Editor eine Zeile „Δ ≥ 15 %", die **nie** einen Alarm auslöst.

`AlertMetricLevelTable.svelte:79` rendert jede übergebene Zeile ungefiltert — die Filterung
ist allein Sache des Aufrufers, und einer der beiden filtert nicht.

**Offen:** Wie viele Trips tragen tatsächlich einen `humidity`-Schlüssel? Im Worktree
liegen keine Nutzerdaten; auf Staging/Prod zu messen.

## Fund 3 — `snow_line` ist wirklich tot, `METRIC_DEFAULTS` ebenfalls

- `snow_line`: doppelt abgesichert (`loader.py:711` Migration, `alert_preset.py:170`
  Normalisierung). Die Frontend-Zeile ist folgenlos — **aber** die Absicherung liegt
  allein im Backend.
- `METRIC_DEFAULTS` (14 Einträge): einziger Leser `alertRulesToRowState()`, einziger
  Aufrufer `AlertMetricTable.svelte` — **nirgends importiert** (nur Kommentar-Verweis in
  `ListTable.svelte:10`). Kein Backend-Gegenstück. **Kein Zusammenführungsziel**, sondern
  allenfalls Löschkandidat: sonst führt man Zahlen zusammen, die niemand liest.

## Technischer Ansatz — generiertes Artefakt (ADR-0045), nicht Laufzeit-API

Die Laufzeit-Variante (Werte über die bestehende Katalog-API ausliefern) scheitert an
`levelToThreshold()`: eine **reine Funktion** `(metric, level)`, aufgerufen tief in
`AlertMetricLevelRow.svelte:30`. Laufzeitwerte bräuchten Prop-Drilling durch drei
Einbettungen in beiden Editoren, eine Signaturänderung mit ~15 Test-Aufrufstellen, ein
Ladefenster in einem heute synchron rendernden Reiter **und** eine Fallback-Tabelle für
„Core nicht erreichbar" — womit die Dublette durch die Hintertür zurückkäme.

**Empfehlung:** `scripts/generate_alert_preset_table.py` erzeugt
`frontend/src/lib/generated/alertPresetThresholds.generated.json` in der Form
`{metric: {kind, entspannt, standard, sensibel}}`. Das `kind` mitzunehmen kostet ~5 Zeilen
und löst `THRESHOLD_CROSSING_METRICS` — heute eine **zweite** Handkopie in derselben
Datei — gleich mit ab. Eine Frische-Ratsche fängt jede Drift. Einfacher als E5: keine
Go-Seite, also nur **eine** generierte Datei.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `scripts/generate_alert_preset_table.py` | CREATE | Erzeuger, ~85 LoC |
| `frontend/src/lib/generated/alertPresetThresholds.generated.json` | CREATE (generiert) | zählt nicht aufs LoC-Limit |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | −58/+22: `METRIC_PRESETS` + `THRESHOLD_CROSSING_METRICS` abgeleitet |
| `src/services/alert_preset.py` | MODIFY | ~5, Docstring „Quelle für das Frontend" |
| `tests/tdd/test_alert_preset_table_parity.py` | CREATE | +90, Frische-Ratsche |
| `frontend/.../alertMetricTable.test.ts` | MODIFY | +25, Wirkungstest der angezeigten Zeile |

**Typbruch beachten:** `Record<AlertMetric, number>` verlangt alle 14 Schlüssel, Python
liefert 12 → `Partial<Record<…>>`. `levelToThreshold` behandelt `undefined` bereits
korrekt (`alertMetricTable.ts:249`).

## Scope Assessment

- Dateien: 6
- Geschätzte LoC: ~170 berührt (Limit 250 — passt, aber nicht großzügig)
- Risiko: **MEDIUM** — Anzeigepfad in beiden Editoren, Alarmverhalten unberührt
- Kein neues ADR nötig: ADR-0045 deckt das Muster, ADR-0019 die Zahlen

## Known Limitations (bewusst nicht in dieser Scheibe)

- **`thunder_level` zeigt bei allen drei Stufen „Δ ≥ 1"**, obwohl seit #1460 die
  Niveau-Grenzen (`ORDINAL_LEVEL_BOUNDS`) entscheiden. Zweiter Anzeigefehler derselben
  Art, aber andere Fragestellung — braucht eine Wortlaut-Entscheidung, eigene Scheibe.
- **`METRIC_DEFAULTS` + `AlertMetricTable.svelte`/`AlertMetricRow.svelte`** (toter
  Alt-Editor) — Löschung wäre Aufräumen, nicht Zusammenführung.
- **Go-seitiges `AlertableMetrics`** — offene Restlücke aus E5, unverändert.

## Nachweis der Wirksamkeit

Vier Mutationen für den Adversary:

1. `_PRESET_TABLE`: `FREEZING_LEVEL` entspannt 600→999, **nicht** regenerieren → Ratsche
   rot, nennt Größe und Stufe mit Soll und Ist.
2. Generierte JSON von Hand verfälschen (`wind_gust` standard 20→21) → Ratsche rot.
3. Ganze Zeile (`VISIBILITY`) aus `_PRESET_TABLE` löschen → Ratsche rot mit „fehlt",
   nicht still grün (fängt die Falle, nur über die Schlüssel **einer** Seite zu iterieren).
4. **Die entscheidende:** in `alertMetricTable.ts` die Ableitung durch ein Literal
   ersetzen → wird irgendetwas rot? Wenn nein, bewacht die Ratsche nur Python↔JSON,
   **nicht die angezeigte Zeile**. Deshalb Pflicht: ein `node:test`, der
   `levelToThreshold('freezing_level','standard') === 'Δ ≥ 400 m'` prüft.

**Staging-Nachweis:** Trip-Editor → Reiter Alarme, Zeile „Nullgradgrenze" auf Stufe
Standard muss „Δ ≥ 400 m" zeigen (vorher „Δ ≥ 200 m"), Screenshot. Danach dieselbe
Prüfung im Vergleichs-Editor — `AlarmeTab` ist geteilt.

## Open Questions

Keine offenen. **PO-Entscheid 2026-08-06:** Die Geisterzeile Luftfeuchtigkeit (Fund 2)
wird **nicht** in dieser Scheibe behoben, sondern bekommt ein eigenes Ticket — anderer
Fehlertyp (fehlende Filterung im Trip-Pfad, nicht die Zahlentabelle), und es fehlt noch
die Messung, wie viele Trips überhaupt einen `humidity`-Schlüssel tragen.
Zahlen der Nullgradgrenze: keine neue Entscheidung nötig, ADR-0019 Punkt 4 gilt (600/400/200).
