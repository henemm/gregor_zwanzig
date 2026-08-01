---
entity_id: fix_1397_s4_it_grenze
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, italien, oesterreich, grenze, covers, false-positive]
workflow: fix-1397-it-grenze
---

<!-- Issue #1397, Scheibe S4 -->

# Italienischer Warnweg hält sich für Orte jenseits der Landesgrenze für zuständig

## Approval

- [x] Approved

## Purpose

`MeteoAlarmFeedSource("IT").covers()` entscheidet die Zuständigkeit über die grobe
DPC-Radar-Bbox (lat 36,0–47,5 / lon 6,5–19,0) und schließt darüber bisher **nur Frankreich**
per Sonderregel aus. Österreich, die Schweiz, Slowenien und Kroatien liegen ebenfalls weit in
dieser Bbox, ohne Ausnahme zu haben. Für einen Ort in einem dieser Länder behauptet die
italienische Quelle fälschlich Zuständigkeit, findet dann keine passende italienische Zone und
meldet „nicht abrufbar" — obwohl die tatsächlich zuständige Quelle (z. B. die österreichische)
ihre Warnungen ganz normal liefert. Diese Spec macht die Zuständigkeitsprüfung geometrie- statt
bbox-basiert, damit der Hinweis nur noch dort erscheint, wo er einen echten Ausfall bedeutet.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py`
- **Identifier:** `MeteoAlarmFeedSource.covers()` (Zeile 292-316), Instanz `country="IT"`

> **Schicht:** reiner Python-Core (`src/services/official_alerts/`), kein Go-/Frontend-Anteil.
> Die betroffene Betriebs-Aggregation (`warn_service_health` / CORE-Heartbeat, #1434) liegt in
> `internal/scheduler/`, wird hier aber **nicht verändert** — sie liest weiterhin dasselbe
> Diagnose-Journal, das mit diesem Fix einfach aufhört, für diesen Fall neue Zeilen zu bekommen.

## Der Befund

| # | Was | Ort im Code | Wirkung |
|---|---|---|---|
| A | `covers()` prüft nur die DPC-Bbox + eine Frankreich-Ausnahme | `meteoalarm_feed.py:311-316` | Punkte in AT/CH/SI/HR innerhalb der Bbox gelten fälschlich als „italienisch zuständig" |
| B | `fetch()` findet für so einen Punkt keine der 187 italienischen Zonen | `meteoalarm_feed.py:332-339` | `log_zone_drift(..., "point_unmapped")` + `mark_fetch_incomplete()` → `unavailable=True` |
| C | `base.py` sammelt dennoch alle Quellen | `base.py:118-146` | Es geht **keine Warnung verloren** (die AT-Quelle liefert korrekt) — der Schaden ist ausschließlich der grundlose „nicht abrufbar"-Hinweis |

**Messung (Prod, 2026-08-01, alle Nutzer-Koordinaten gegen die eingecheckte Geometrie):** 55
Punkte liegen in der DPC-Bbox, davon 39 in keiner der 187 Zonen — alle aus einer Tour (Karnischer
Höhenweg), die auf der Staatsgrenze IT/AT verläuft. Abstand dieser 39 Punkte zur nächsten
italienischen Zonengrenze: min 0,05 / median 1,14 / max 5,37 km, 17 davon unter 1 km. Journal:
durchgehend `{service: meteoalarm_feed, zone_code: null, has_warning: true, drift:
"point_unmapped"}`. Betrieblich zieht das den CORE-Heartbeat (#1434) mit irreführendem Text
(„Gebietskarte veraltet") dauerhaft rot — Prod 8 Vorkommen, 4 je 15-Minuten-Lauf, fortlaufend,
das 24h-Frischefenster läuft nie leer.

**Zwei bereits ausgeschlossene Ursachen (Abgrenzung):**

- **Die Gebietskarte ist intakt.** `_REGION_PREFIX_TO_EMMA` deckt alle 20 Regionspräfixe der
  187 Zonen vollständig ab. Ein Neuerzeugen von `dpc_zones.json` ändert am Befund nichts.
- **Kein Rückfall auf den 2026-07-27 behobenen Fehler** (Commit `5a4745b2`, damals
  `geosphere_warn`/`MeteoAlarmSource`). Der neue Feed-Weg aus #1445 (2026-07-31 live) hat die
  Fehlerklasse für die Nachbarländer außer Frankreich **wieder eingeführt** — Rückfall, kein
  Altbestand.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/dpc.py` (`_zone_at()`, Zeile 77-83) | module | Rein lokale Punkt-in-Fläche-Prüfung gegen die eingecheckte Geometrie (`data/dpc_zones.json`) — bereits importiert in `meteoalarm_feed.py` als `_zone_at`, Basis von `_zone_for_point()` |
| `src/services/official_alerts/meteoalarm_feed.py` (`_zone_for_point()`, Zeile 77-86) | module | Bündelt `_zone_at()` + Regions-Präfix-Tabelle zu einer EMMA-Zonen-ID; wird jetzt zusätzlich als Zuständigkeitsprüfung in `covers()` genutzt, nicht nur in `fetch()` |
| `src/services/official_alerts/department_mapper.py` (`lookup_department()`, Zeile 376) | module | Bestehende, rein lokale Frankreich-Ausnahme (#1397 S2b) — bleibt als expliziter Schutz erhalten, nicht durch die Geometrie-Prüfung ersetzt |
| `src/services/official_alerts/base.py` (`get_official_alerts_with_status()`, Zeile 90-176) | module | Wertet `covers()`/`fetch()` aus und leitet `unavailable` ab — unverändert, wirkt hier nur als Konsument |
| `src/services/massif_closure.py` (`covers()`, Zeile 119-120) | reference | Vorbild: `massif_at(lat, lon) is not None` — echte Fläche statt Rechteck, rein lokal, kein Netzabruf |
| `tests/tdd/test_meteoalarm_feed_italien.py` | test | Enthält den bestehenden Frankreich-Regressionswächter (`FREJUS`, Zeile 221-266) UND den Test `test_ac5_punkt_ohne_zone_meldet_nicht_abrufbar_und_zaehlbaren_drift` (Zeile 920-960), dessen Erwartung sich mit diesem Fix ändert (s. Implementation Details) |
| `docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md`, AC-5 | spec | Wird für den Spezialfall „Punkt ohne auflösbare Zone, aber auch nicht in Italien" durch diese Spec sachlich abgelöst — der dortige Test (offenes Meer) fällt unter denselben Mechanismus wie die Grenzfälle hier |
| `docs/specs/modules/fix_1434_dpc_zonen_drift.md` | spec | Nachbar-Betriebsauswertung (CORE-Heartbeat) — wird durch diesen Fix indirekt entlastet, ohne selbst verändert zu werden |

## Estimated Scope

- **LoC:** ~150–200 (Quelle ~15–25, Tests ~120–160) — deutlich unter dem 250er-Limit
- **Files:** 2 (1× Python-Quelle, 1× Test)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `covers()` für `country="IT"` von DPC-Bbox auf Zonen-Geometrie umstellen, Frankreich-Ausnahme als zusätzlichen Schutz beibehalten, Docstring aktualisieren |
| `tests/tdd/test_meteoalarm_feed_italien.py` | MODIFY | Bestehenden AC-5-Test (offenes Meer) auf die neue, korrekte Erwartung drehen; neue Tests für AT-Grenznähe (Regression) und grenznahe echte IT-Zone (Gegenprobe) ergänzen; Frankreich-Regressionswächter bleibt unverändert grün |

## Implementation Details

1. **`covers()` für `country="IT"`:** die grobe DPC-Bbox-Prüfung entfällt. Zuständig ist ein
   Punkt nur noch, wenn er (a) **nicht** in einem französischen Département liegt (bestehende,
   unveränderte `lookup_department()`-Prüfung, #1397 S2b) **und** (b) tatsächlich einer der 187
   italienischen Warnzonen zugeordnet werden kann (dieselbe Geometrie-Funktion, die `fetch()`
   ohnehin schon für die Zonenauflösung nutzt). Beide Prüfungen sind rein lokal, kein
   Netzabruf — Fail-soft/`base.py` bleiben unberührt (Invariante 5).
2. **Die Frankreich-Ausnahme bleibt als eigener, expliziter Schritt erhalten** (Invariante 1),
   statt sich implizit auf die italienische Geometrie zu verlassen: die vereinfachten
   Zonen-Polygone könnten an der Grenze selbst leicht ungenau sein, und die Frankreich-Prüfung
   ist bereits getestet und produktiv bewährt. Beide Prüfungen zusammen sind strenger als jede
   einzelne.
3. **`country="AT"` bleibt unangetastet** (Invariante 2) — andere Codezeilen, anderer
   Zuständigkeits-Mechanismus (INCA-Bbox + ZAMG-404 als Fall 1 in `fetch()`).
4. **Der `point_unmapped`-Zweig in `fetch()` (Zeile 332-339) bleibt im Code erhalten**, wird
   aber über den normalen Registry-Pfad (`base.py` ruft immer erst `covers()`, dann `fetch()`
   auf) nach diesem Fix praktisch nicht mehr erreicht — `covers()` filtert genau die Punkte
   vorher aus, die dort auf `None` treffen würden. Der Zweig bleibt bewusst als Sicherheitsnetz
   für direkte `fetch()`-Aufrufe (z. B. Tests, künftige andere Aufrufer) stehen und wird im Code
   als solches kommentiert — kein blinder Wächter, weil sein Zweck (Absicherung außerhalb des
   Registry-Pfads) unabhängig von seiner Trefferhäufigkeit im Normalbetrieb gilt.
5. **Bestehender Test muss sachlich mitgezogen werden:**
   `test_ac5_punkt_ohne_zone_meldet_nicht_abrufbar_und_zaehlbaren_drift`
   (`tests/tdd/test_meteoalarm_feed_italien.py:920-960`) prüft heute für `MEER_UNMAPPED`
   (offenes Meer zwischen Sizilien und dem Festland, in der DPC-Bbox, in keiner Zone) explizit
   `unavailable is True` plus eine Drift-Journalzeile — exakt das Verhalten, das dieser Fix
   beseitigt, nur an einem anderen Ort als Österreich (auch das Meer ist „innerhalb der Bbox,
   aber nicht Italien"). Der Test wird auf die neue, korrekte Erwartung gedreht
   (`unavailable is False`, keine neue Drift-Zeile) und entsprechend umbenannt/dokumentiert.
   Das ist keine stille Abschwächung, sondern derselbe Fehler an einem zweiten Symptom.
6. **Neue Tests** ergänzen echte, aus der eingecheckten Geometrie abgeleitete Koordinaten (Muster
   wie bestehend: `ROM = (41.9028, 12.4964)  # Lazi-D -> IT012`):
   - ein Punkt eindeutig in Österreich nahe der Kärnten/Friaul-Grenze (Region Karnischer
     Höhenweg/Plöckenpass) → `covers()` liefert `False`, kein `unavailable` über die
     italienische Quelle.
   - derselbe Ort, jetzt zusammen mit der (unverändert funktionierenden) österreichischen
     Quelle registriert → die österreichischen Warnungen kommen normal an, kein
     Ausfallhinweis von keiner der beiden Quellen.
   - ein Punkt in einer echten, grenznahen italienischen Zone (z. B. `Friu-B`/`Tren-A`/`Vene-A1`,
     dieselbe Tour) → `covers()` bleibt `True`, Warnungen kommen weiterhin an (Gegenprobe zu
     Invariante 4).
   - Fréjus (`FREJUS`, bestehende Konstante) bleibt unverändert ausgeschlossen — reiner
     Regressionslauf, kein neuer Test nötig.

## Abwägung: Grenznahe Punkte ohne trennscharfe Antwort

Für Punkte **real jenseits der Grenze** ist Schweigen richtig, der bisherige Hinweis falsch —
das ist der behobene Fall. Für Punkte, die **real in Italien liegen**, aber durch die
Vereinfachung der eingecheckten Zonen-Polygone knapp außerhalb fallen, wäre der Hinweis
„nicht abrufbar" ehrlicher als Schweigen. Mit der Geometrie allein sind beide Fälle nicht
unterscheidbar. Diese Spec entscheidet sich bewusst für **Schweigen als Standard**, aus zwei
Gründen: (1) schon heute liefert `fetch()` für alle 39 gemessenen betroffenen Punkte `[]` — der
einzige Unterschied ist der wegfallende, in praktisch allen 39 Fällen falsche Hinweis; (2) die
Zahl der Punkte, die tatsächlich fälschlich schweigen würden (real italienisch, aber von der
Geometrie knapp verfehlt), ist in der Messung nicht belegt und wäre strukturell selten, während
die Zahl der grundlos alarmierten Punkte (AT/CH/SI/HR) belegt hoch ist. Diese Abwägung ist eine
bewusste PO-taugliche Entscheidung, kein technisches Detail — sie steht auch unten als Known
Limitation.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts nahe der italienischen Staatsgrenze.
- **Output:** Für Orte außerhalb Italiens (AT/CH/SI/HR/FR) liefert die italienische Quelle
  keine Warnungen und **keinen** Ausfallhinweis mehr. Für Orte innerhalb einer echten
  italienischen Zone bleibt das Verhalten unverändert. Für Orte ohne jede auflösbare
  Zonen-Zugehörigkeit (auch außerhalb Italiens, z. B. offenes Meer) entfällt ebenfalls der
  bisher fälschlich ausgelöste Hinweis.
- **Side effects:** Für die betroffenen Grenzpunkte entstehen keine neuen Diagnose-Journal-Zeilen
  mehr (`drift: "point_unmapped"` für diese Fälle). Der CORE-Heartbeat (#1434) wird nach Ablauf
  des 24h-Frischefensters von selbst wieder grün, ohne dass an der Betriebsauswertung etwas
  geändert werden muss.

## Acceptance Criteria

- **AC-1:** Given ein beobachteter Ort liegt eindeutig in Österreich nahe der italienischen
  Grenze (z. B. entlang des Karnischen Höhenwegs) / When die amtlichen Warnungen für diesen Ort
  ermittelt werden / Then erscheint dafür kein „amtliche Warnungen nicht abrufbar"-Hinweis der
  italienischen Warnquelle mehr, solange die tatsächlich zuständige österreichische Quelle ihre
  Warnungen normal liefert.
  - Test: `tests/tdd/test_meteoalarm_feed_italien.py` — realer AT-Grenzpunkt, geprüft wird der
    `unavailable`-Status des echten Ermittlungswegs, nicht ein Log-Text.

- **AC-2 (Regressionsschutz Frankreich):** Given ein beobachteter Ort liegt in Frankreich nahe
  der italienischen Grenze (wie bisher bereits korrekt behandelt) / When die amtlichen Warnungen
  ermittelt werden / Then bleibt dieser Ort weiterhin von der italienischen Quelle
  ausgeschlossen — keine Rückkehr des bereits einmal behobenen Fehlers.
  - Test: `tests/tdd/test_meteoalarm_feed_italien.py` — bestehender Fréjus-Regressionswächter
    bleibt unverändert grün.

- **AC-3 (wichtigste Gegenprobe):** Given ein beobachteter Ort liegt tatsächlich in einer echten
  italienischen Warnzone, auch grenznah zu Österreich / When die amtlichen Warnungen ermittelt
  werden / Then bekommt dieser Ort weiterhin zuverlässig seine italienischen Warnungen — die
  Korrektur darf keinen bislang funktionierenden Ort verlieren.
  - Test: `tests/tdd/test_meteoalarm_feed_italien.py` — realer, grenznaher IT-Zonen-Punkt aus
    derselben Tour, geprüft wird, dass Warnungen weiterhin ankommen.

- **AC-4:** Given ein beobachteter Ort liegt an einer Stelle, die weder einem Land noch einer
  bekannten italienischen Warnzone eindeutig zuordenbar ist (z. B. offenes Meer weit von jeder
  Landzone) / When die amtlichen Warnungen ermittelt werden / Then löst auch dieser Ort keinen
  „nicht abrufbar"-Hinweis der italienischen Quelle mehr aus, weil erkennbar keine Zuständigkeit
  besteht.
  - Test: `tests/tdd/test_meteoalarm_feed_italien.py` — bestehender Meer-Testfall, Erwartung
    gedreht auf `unavailable is False`.

- **AC-5:** Given die italienische Quelle ist für einen tatsächlich in Italien liegenden Ort
  weiterhin real nicht erreichbar (z. B. der Datenabruf selbst schlägt fehl) / When die
  amtlichen Warnungen für diesen Ort ermittelt werden / Then bleibt der „nicht abrufbar"-Hinweis
  für diesen echten Fehlerfall unverändert bestehen — die Korrektur betrifft ausschließlich die
  fälschliche Zuständigkeit, nicht echte Ausfälle.
  - Test: bestehender Malformations-/Fehlschlag-Test in `tests/tdd/test_meteoalarm_feed_italien.py`
    (Zeile ~900-913) bleibt unverändert grün.

- **AC-6 (betrieblicher Nachweis):** Given der Stand ist ausgerollt und ein Beobachtungszyklus
  ist abgeschlossen / When der bestehende Betriebszustand zur italienischen Warnquelle betrachtet
  wird / Then hören die bisher fortlaufenden „Gebiet nicht zuordenbar"-Meldungen für Orte
  außerhalb Italiens auf, neu aufzutreten — der zugehörige Alarm wird nach Ablauf des
  24-Stunden-Frischefensters von selbst wieder ruhig, ohne dass die Betriebsauswertung selbst
  angefasst wird.
  - Test: Staging-/Prod-Beobachtung nach Deploy (kein pytest) — Diagnose-Journal zeigt für
    bekannte Grenzpunkte keine neuen `point_unmapped`-Zeilen mehr.

## Known Limitations

- **Grenznahe, aber real italienische Punkte können knapp verfehlt werden.** Die eingecheckte
  Zonen-Geometrie ist eine Vereinfachung; ein Punkt, der real in Italien liegt, aber außerhalb
  des vereinfachten Polygons, schweigt künftig statt zu warnen. Bewusste Abwägung, s. Abschnitt
  „Abwägung: Grenznahe Punkte ohne trennscharfe Antwort" oben — nicht Gegenstand einer
  automatischen Korrektur in dieser Scheibe.
- **Kein Selbstheilen bei Grenzverlauf-Änderungen.** Analog zur DPC-Zonen-Drift (#1434) wird die
  Geometrie nicht zur Laufzeit nachgezogen.
- **Der `point_unmapped`-Zweig in `fetch()` wird im normalen Registry-Pfad faktisch
  unerreichbar**, bleibt aber als dokumentiertes Sicherheitsnetz für direkte `fetch()`-Aufrufe
  außerhalb des Registry-Pfads bestehen (Implementation Details Punkt 4).
- **Weitere Nachbarländer/Enklaven** (San Marino, Vatikanstadt) sind nicht separat geprüft,
  fallen aber strukturell unter denselben Mechanismus wie AT/CH/SI/HR — keine Sonderbehandlung
  nötig, aber auch kein expliziter Testfall in dieser Scheibe.
- **`docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md` AC-5 wird durch diese Spec für den
  Meer-Spezialfall sachlich abgelöst**, ohne dass die Nachbar-Spec selbst in diesem Workflow
  aktualisiert wird — die Änderung ist im hier geänderten Testfall dokumentiert.

## Abgrenzung — nicht Teil dieser Scheibe

- **`MeteoAlarmFeedSource("AT")`** bleibt vollständig unverändert (Invariante 2).
- **`DpcSource`** (`dpc.py`) ist eine andere Quelle mit eigenem Bugfix-Kontext (#1434, Zonen-
  Drift zwischen Geometrie und Bulletin) — nicht Gegenstand dieser Spec.
- **Der Äquivalenznachweis EDR-Index vs. Feed** (die zwei `xfail(strict=True)`-Tests in
  `tests/tdd/test_meteoalarm_feed_italien.py:555` und
  `tests/tdd/test_meteoalarm_feed_oesterreich.py:949`, wartend auf `edr_snapshot_it.json`) ist
  ausdrücklich ausgeklammert (PO-Entscheid 2026-08-01, eigene Arbeit).
- **Kein Auftrag an `infra`.** Die Betriebsauswertung (#1434, `check-gregor20.sh`) bleibt
  unverändert richtig — sie hört einfach auf, für diesen Fall Signale zu bekommen.
- **Kein neues ADR, keine Architekturänderung.**

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Die Spec bewegt sich vollständig innerhalb bestehender Entscheidungen —
  ADR-0018 (Fail-soft in Warnquellen bleibt unverändert: kein Raise, `fetch()` liefert weiter
  fail-soft `[]`) und der bereits produktiven #1397-S2b-Entscheidung, geografische Zuständigkeit
  an der Staatsgrenze statt am Radar-/Bbox-Gitter zu bestimmen. Diese Spec wendet dasselbe
  Prinzip konsequent auf alle Nachbarländer an, statt eine neue Entscheidungsfläche zu öffnen.

## Changelog

- 2026-08-01: Initial spec created (Issue #1397, Scheibe S4).
