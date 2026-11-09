# Adversary-Dialog #2878 (Etappenliste + Hub-Titel)

Runde 1: Tests. trip-hub-etappenliste-titel.spec.ts 6/6 gruen, hub_kopf_baustein.test.ts 29/29, trip-hub-kopf-region-aktivitaet.spec.ts 31/31.

Runde 2: Mutationen (String-Ersetzung, Sicherung in Scratchpad, danach diff identisch, git status sauber).
| Mutation | Ergebnis |
|---|---|
| M1 truncate zurueck an h1 | gefangen: EL-3, EL-4, EL-5 |
| M2 Container-Query entfernt (max-width 1px) | gefangen: EL-1 (Name 0 px), EL-2 |
| M3 white-space:nowrap der Meta-Teile entfernt | gefangen: EL-1 (Stresstest) |
| M4 Stift aus Titelgruppe geloest (display:contents) | NICHT GEFANGEN |
| M5 Schwelle 639 -> 400 px | gefangen: EL-1, EL-2 |
| M6 container-type in HubOverview entfernt | gefangen: EL-1, EL-2 |
| M7 overflow-wrap:anywhere entfernt | NICHT GEFANGEN |
| M8 flex-wrap an Titelzeile entfernt | NICHT GEFANGEN |
| M9 flex-wrap an Meta-Zeile entfernt | NICHT GEFANGEN |

Runde 3: Randfaelle (Probe-Spec im Scratchpad): 60 Zeichen ohne Leerzeichen 390 px (kein Seiten-Scroll, h1 274 px, Stift 44x44), 1 Zeichen, 30 Etappen EN, 768/960/1280/1440 px: keine Zeilen-Ueberbreite, Titel nie abgeschnitten.
Beobachtung: bei 960 px ist der Behaelter nur 200 px, Name 84 px breit (Ellipsis); bei 1440 px 153 px (Zusammenfassung sichtbar, lange Namen mit Ellipsis). Spec fordert nur 1280 -> kein Bruch, LOW.

## Fix-Loop (F001/F002, Testluecken; Verhalten unveraendert)

Neue Abdeckung in `frontend/e2e/trip-hub-etappenliste-titel.spec.ts` (Mutationen per String-Ersetzung, Sicherung in Scratchpad `bak2/`, danach `git diff` der Komponente leer):

| Mutation | neue Abdeckung | Ergebnis |
|---|---|---|
| M4 Titelgruppe `display: contents` (Stift aus der Gruppe geloest) | EL-4b (neu, 390 px, 60 Zeichen ohne Leerzeichen): Stift und h1 haben dasselbe Elternelement, Gruppe mit eigener Box (nicht `contents`), h1 und Stift liegen in der Gruppenbox, Stift rechts neben dem Titel und nicht allein in einer neuen Zeile | gefangen: EL-4b („Titelgruppe ohne eigene Box") |
| M7 `overflow-wrap:anywhere` am h1 entfernt | EL-4b: Titel ohne Ueberbreite (scrollWidth <= clientWidth), h1 nie breiter als die Titelzeile, kein Seiten-Scroll | gefangen: EL-4b („Titel laeuft ueber, scrollWidth 634 > clientWidth 274") |
| M8 `flex-wrap` der Titelzeile entfernt | EL-4b: Status-Schild steht unter dem Titel (Oberkante >= Titel-Unterkante - 1) | gefangen: EL-4b („Status-Schild steht neben statt unter dem Titel") |
| M9 `flex-wrap` der Meta-Zeile entfernt | EL-1 Stresstest: bei 1 px Behaelter steht jedes Meta-Teil in einer eigenen Reihe (Zahl verschiedener Oberkanten = Zahl der Teile) | gefangen: EL-1 („1 Reihe(n) fuer 2 Teile") |

Ohne Mutation: `trip-hub-etappenliste-titel.spec.ts` 7/7 (inkl. setup), zusammen mit `trip-hub-kopf-region-aktivitaet.spec.ts` 37/37. CI-Ratsche `E2E_MIN_EXECUTED_HAUPT` 625 -> 626 (+1 Fall EL-4b; `--list` ueber die Positivliste ohne bug-703: 671).
