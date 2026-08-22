---
entity_id: fix_2073_track_ergebnisgleichheit
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [gpx, track-resolution, alarm]
workflow: fix-2073-ergebnisgleichheit
---

# Track-Auflösung: Ergebnisgleichheit statt Dateianzahl als Eindeutigkeitsregel

## Approval

- [ ] Approved

## Purpose

`resolve_stage_track_km()` gibt heute auf, sobald **mehr als eine** GPX-Datei innerhalb der
Zuordnungstoleranz auf die Wegpunkte einer Etappe passt (Früh-Abbruch bei zweitem Treffer). Geprüft
wird damit die **Anzahl der Kandidaten**, nicht ob sie zu **verschiedenen** Kilometerwerten führen.
Eine byte-identische Dublette derselben GPX-Datei unter zwei Namen liefert dieselben Werte wie ein
einziger Kandidat, wird aber wie ein echter Widerspruch behandelt und die Etappe fällt unnötig auf
`Segment N` zurück (real gemessen: „GR221 Mallorca" Tag 1, Original + `test.gpx`). Diese Spec stellt
die Regel auf **Ergebnisgleichheit** um: liefern alle Kandidaten praktisch dieselbe Wegstrecke, darf
die Auflösung sich entscheiden; nur bei wirklich abweichenden Ergebnissen bleibt `None`.

## Source

- **File:** `src/services/track_resolution.py`
- **Identifier:** `resolve_stage_track_km()` (:59-98)

> **Schicht-Hinweis:** Python-Core / Domain-Backend (`src/services/`). Kein Go- und kein
> Frontend-Anteil — reine Auflösungslogik innerhalb einer bestehenden Funktion, kein neues
> Datenfeld, keine Schema-Änderung.

## Estimated Scope

- **LoC:** ~50–70 Produktivcode
- **Files:** 2 (`src/services/track_resolution.py`, `tests/tdd/test_track_resolution_legacy_trip.py`)
- **Effort:** medium — kleiner Funktionsumfang, aber die Umstellung von „ein Treffer" auf
  „mehrere Treffer paarweise vergleichen" verändert die Kernlogik einer bewachten Funktion, deren
  Bestandstests (AC-11 aus #2036) mit umgeschrieben werden müssen, ohne ihren Wächter-Zweck zu
  verlieren.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/track_resolution.py` (`_match_track`) | module | Vollständigkeitsregel je Kandidat (AC-12 aus #2036) — bleibt unverändert, liefert weiterhin `Dict[waypoint_id, km]` oder `None` je Track |
| `src/services/track_resolution.py` (`DEFAULT_TOLERANCE_M`) | module | Bereits festgelegte 10-m-Zuordnungstoleranz — die neue Ergebnisgleichheits-Schwelle wird von dieser Konstante abgeleitet, keine zweite freie Zahl |
| `src/services/track_resolution.py` (`backfill_stage_distances`) | module | Aufrufer von `resolve_stage_track_km`; Read-Modify-Write-Rückschreibweg bleibt unangetastet |
| `src/services/trip_segments.py` (`stage_measured_distances`, :150-151) | module | Wendet dieselbe Etappenstart-Normierung bereits auf dem Weg zum Nutzer an — Vorbild für die Normierung im Vergleich |
| `src/core/gpx_parser.py` (`GPXPoint.distance_from_start_km`, :155) | module | Liefert die rohe, ab Track-Anfang kumulierte Distanz je Trackpunkt — Grundlage der Normierung |
| `docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md` | spec | Vorgänger-Spec, Quelle von AC-11 (Eindeutigkeit), AC-12 (Vollständigkeit) und der 10-m-Toleranz |

## Implementation Details

**Auflösungsreihenfolge in `resolve_stage_track_km()` (ersetzt :82-98):**

1. **Kein Früh-Abbruch mehr.** Die Schleife über `sorted(directory.glob("*.gpx"))` läuft
   vollständig durch; jeder Kandidat, der `_match_track()` besteht, wird in `matches` gesammelt
   (statt bei `len(matches) > 1` sofort `None` zurückzugeben).
2. **Normierung vor dem Vergleich.** Für jeden Kandidaten wird die Ergebnis-Liste
   `[km_wp1, km_wp2, ...]` in Etappen-Reihenfolge auf den ersten Wegpunkt normiert:
   `norm[i] = roh[i] - roh[0]`. Dieselbe Normierung wendet `stage_measured_distances`
   (`trip_segments.py:150-151`) ohnehin auf dem Weg zum Nutzer an.
3. **Ergebnisgleichheit paarweise, nicht gegen einen Referenzkandidaten.** Zwei Kandidaten gelten
   als ergebnisgleich, wenn für JEDEN Wegpunkt `|norm_A[i] - norm_B[i]| <= 10 m` (0,01 km) gilt.
   Die Prüfung läuft über **alle** Kandidatenpaare (bei `n` Kandidaten: alle `n·(n-1)/2` Paare).
   Referenzvergleich gegen einen einzelnen Kandidaten würde die effektive Toleranz bei einer
   Kette knapp-innerhalb-Kandidaten stillschweigend verdoppeln (A~B, B~C, aber A und C 18 m
   auseinander) — deshalb paarweise.
4. **Sind alle Kandidaten paarweise ergebnisgleich**, wird das Ergebnis des **ersten** Kandidaten
   in `sorted(...)`-Reihenfolge zurückgegeben — mit seinen **rohen**, unnormierten Werten (wie
   bisher; die Normierung ist ausschließlich ein Vergleichs-Hilfsmittel, kein Rückgabeformat).
5. **Sonst** (mindestens ein Paar überschreitet die Schwelle, oder `len(matches) == 0`) liefert
   die Funktion weiterhin `None`.
6. `_match_track()` (die Vollständigkeitsregel, AC-12 aus #2036) wird **nicht** angefasst — sie
   entscheidet weiterhin unverändert, ob ein einzelner Kandidat überhaupt in `matches` landet.
7. Die Ergebnisgleichheits-Schwelle wird als benannte Konstante geführt, die aus
   `DEFAULT_TOLERANCE_M` abgeleitet ist (z. B. `RESULT_EQUALITY_TOLERANCE_M = DEFAULT_TOLERANCE_M`)
   — es gibt bewusst nur EINE 10-m-Zahl im Modul, keine zweite, frei geratene Größe.

**Warum normierte statt roher Werte verglichen werden:** `distance_from_start_km` kumuliert ab dem
Anfang des jeweiligen GPX-**Tracks** (`gpx_parser.py:155`), nicht ab dem Etappenstart. Eine
Einzeletappen-GPX beginnt bei 0 km, eine durchlaufende Gesamt-Tour-GPX kann für dieselbe physische
Etappe bei z. B. 50 km beginnen. Roh verglichen wären beide „verschieden", obwohl sie dem Nutzer
identische Kilometerwerte zeigen würden: `trip_segments.py:150-151` normiert ohnehin auf den
Etappenstart, und die ausgelieferten Segmente tragen ausschließlich diese normierten Werte
(`trip_segments.py:299-305`, `km_start = measured[i]`). Der rohe Absolutwert ist nirgends
nutzersichtbar — Go transportiert ihn nur (`internal/model/trip.go:99`), kein Frontend zeigt ihn.
Genau der Fall „Einzeletappe UND Gesamt-GPX" ist das Leitbeispiel aus AC-11 der Vorgänger-Spec, das
diese Scheibe löst.

**Warum 10 m und nicht relativ:** Am Produktivbestand gemessen (`docs/context/fix-2073-ergebnisgleichheit.md`,
Befund 3): der einzige real auftretende Gleichheitsfall liegt bei **0,0 m** Abweichung, der nächste
denkbare Abweichungsfall (dieselbe Strecke, andere Aufzeichnung) bei **144 m**, fremde Etappen liegen
im Kilometerbereich auseinander. 10 m ist bereits als „derselbe Punkt" festgelegt
(`DEFAULT_TOLERANCE_M`, Vorgänger-Spec „Festgelegte Schwellenwerte") — es kommt keine zweite, frei
geratene Zahl ins Modul. Eine relative Schwelle wäre schlechter: 1 % einer 9,6-km-Etappe sind 96 m
und würden echte Wegunterschiede durchwinken, bei einer 1-km-Etappe wären es nur 10 m. Die
verglichene Größe ist ein Ortsabstand, keine Proportion.

**Warum paarweise statt gegen einen Referenzkandidaten:** Bei einer harten Schwelle ist Gleichheit
nicht transitiv. Liegt B 9 m über A und C 9 m unter A, bestehen beide den Referenzvergleich gegen A,
liegen aber 18 m auseinander — ein Referenzvergleich würde die effektive Toleranz stillschweigend
verdoppeln. Bei A~B, B~C, A≁C ist `None` die ehrliche Antwort, weil kein einziges gemeinsames
Ergebnis alle drei Kandidaten gleichzeitig beschreibt.

## Expected Behavior

- **Input:** Eine Etappe mit Wegpunkten und ein GPX-Bestandsverzeichnis, in dem zwei oder mehr
  Dateien die Vollständigkeitsregel (`_match_track`, AC-12) für diese Etappe erfüllen.
- **Output:** Sind alle diese Kandidaten paarweise ergebnisgleich (je Wegpunkt ≤ 10 m normierte
  Abweichung), liefert `resolve_stage_track_km()` ein Ergebnis (die rohen Werte des ersten
  Kandidaten in `sorted(...)`-Reihenfolge) statt `None`. Weicht mindestens ein Kandidatenpaar
  wirklich ab, bleibt `None` — unverändert zum heutigen Verhalten.
- **Side effects:** Keine neuen. `backfill_stage_distances()` schreibt wie bisher additiv über
  `save_trip` zurück, sobald ein Ergebnis vorliegt.

## Festgelegte Schwellenwerte

| Größe | Wert | Begründung |
|---|---|---|
| Ergebnisgleichheits-Toleranz je Wegpunkt | **10 m** (abgeleitet von `DEFAULT_TOLERANCE_M`) | Real gemessener Gleichheitsfall liegt bei 0,0 m, der nächste denkbare Abweichungsfall bei 144 m — mehr als eine Größenordnung Luft; keine zweite freie Zahl im Modul (Kontext-Dokument, Befund 3). |
| Vergleichsbasis | **normierte** Wegpunkt-Kilometer (`norm[i] = roh[i] - roh[0]`) | Angleicht Track-Ursprünge; identisch zur Etappen-Normierung in `trip_segments.py:150-151`, die dem Nutzer ohnehin angezeigt wird. |
| Rückgabewert bei Ergebnisgleichheit | **rohe** Werte des ersten Kandidaten in `sorted(...)`-Reihenfolge | Deterministisch, reproduzierbar; die Normierung dient ausschließlich dem Vergleich, nicht der Rückgabe. |

## Acceptance Criteria

- **AC-1:** Given zwei byte-identische GPX-Dateien mit demselben Inhalt liegen unter
  verschiedenen Namen im GPX-Bestand des Nutzers und beide bestehen die Vollständigkeitsregel für
  eine Etappe (der real gemessene Fall: „GR221 Mallorca" Tag 1 mit einer zusätzlichen Kopie
  `test.gpx`) / When die Track-Auflösung für diese Etappe läuft / Then liefert sie ein Ergebnis
  mit den gemessenen Distanzen — nicht mehr `None`.
  - Test: Dieselbe GPX-Fixture wird zweimal unter unterschiedlichen Dateinamen in ein
    `tmp_path`-Verzeichnis kopiert; `resolve_stage_track_km()` liefert für die zugehörige Etappe
    ein Dict mit den erwarteten Kilometerwerten je Wegpunkt.

- **AC-2:** Given zwei GPX-Kandidaten bestehen beide die Vollständigkeitsregel, sind aber NICHT
  byte-identisch, und ihre normierten Wegpunkt-Kilometer weichen je Wegpunkt um weniger als 10 m
  voneinander ab / When die Track-Auflösung läuft / Then liefert sie ein Ergebnis, nicht `None`.
  - Test: Zwei Kandidaten, bei denen die zweite Datei zwischen zwei Wegpunkten einen minimalen
    zusätzlichen Trackpunkt trägt (Umweg von wenigen Metern), so dass die normierten
    Kilometerwerte messbar, aber um weniger als 10 m abweichen — die Dateien sind damit
    nachweislich **nicht** byte-identisch;
    `resolve_stage_track_km()` liefert ein Ergebnis. Dieser Test ist der Wirksamkeitsnachweis —
    ohne ihn wäre „Ergebnisgleichheitsprüfung ersatzlos entfernt" ununterscheidbar vom alten
    Verhalten, da AC-1 mit byte-identischen Dateien auch bei einer entfernten Prüfung bestünde.

- **AC-3:** Given eine Einzeletappen-GPX und eine durchlaufende Gesamt-Tour-GPX decken dieselbe
  Etappe ab, ihre rohen Distanzwerte unterscheiden sich aber um einen großen Offset (z. B. +50 km,
  weil die Gesamt-GPX nicht bei dieser Etappe beginnt) / When die Track-Auflösung läuft / Then
  liefert sie ein Ergebnis, weil die auf den Etappenstart normierten Werte je Wegpunkt innerhalb
  von 10 m übereinstimmen.
  - Test: Neben der Einzeletappen-Fixture wird eine zweite GPX gebaut, die **eine
    vorangestellte Fremdetappe und danach dieselben Trackpunkte** enthält (die Trackpunkte einer
    anderen Fixture-Etappe, gefolgt von denen der Zieletappe). `distance_from_start_km` wird von
    `parse_gpx` beim Parsen kumuliert berechnet (`gpx_parser.py:137-159`) und steht **nicht** in
    der Datei — der Offset entsteht deshalb ausschließlich durch die vorangestellten Trackpunkte,
    nicht durch manipulierte Werte. `resolve_stage_track_km()` liefert ein Ergebnis. Das ist das
    AC-11-Leitbeispiel der Vorgänger-Spec.

- **AC-4:** Given zwei GPX-Kandidaten bestehen beide die Vollständigkeitsregel, aber ihre
  normierten Wegpunkt-Kilometer weichen an mindestens einem Wegpunkt um deutlich mehr als 10 m
  voneinander ab (wirklich abweichende Strecken) / When die Track-Auflösung läuft / Then liefert
  sie `None`, und die nachgelagerte Ortsangabe bleibt `Segment N`.
  - Test: Zwei Kandidaten, die **beide** die Vollständigkeitsregel bestehen (alle Wegpunkte
    liegen bei beiden innerhalb von 10 m), deren kumulierte Wegstrecke **zwischen** den
    Wegpunkten aber auseinanderläuft: die zweite Datei bekommt zwischen zwei Wegpunkten einen
    eingefügten Umweg von einigen hundert Metern. Das ist der fachlich echte Fall „zwei
    Wegvarianten zwischen denselben Punkten" und die einzige Konstruktion, die den
    Ergebnisvergleich überhaupt erreicht — Kandidaten, deren **Wegpunkte** abweichen, werden
    schon von `_match_track` verworfen (deshalb taugt die zweite Mallorca-Tag-2-Aufzeichnung mit
    ihren 111 m Wegpunkt-Abstand hier **nicht** als Vorlage, siehe Kontext-Dokument Befund 1).
    `resolve_stage_track_km()` liefert `None`, und
    `format_alert_location(None, ..., km_measured=False)` liefert weiterhin `Segment N`. AC-11 der
    Vorgänger-Spec behält damit seinen Wächter — nur sein Auslöser ändert sich von „Anzahl" auf
    „Ergebnisunterschied".

- **AC-5:** Given drei GPX-Kandidaten bestehen die Vollständigkeitsregel, wobei Kandidat A und B
  paarweise ergebnisgleich sind, B und C paarweise ergebnisgleich sind, A und C aber NICHT
  ergebnisgleich sind (Kette ohne gemeinsames Ergebnis) / When die Track-Auflösung läuft / Then
  liefert sie `None`.
  - Test: Drei Kandidaten mit dieser Dreiecks-Konstellation, gebaut nach derselben Technik wie
    AC-4 (eingefügte Umwege verschiedener Länge zwischen denselben Wegpunkten, so dass A→B und
    B→C je knapp unter 10 m, A→C aber knapp über 10 m liegen);
    `resolve_stage_track_km()` liefert `None`. Unterscheidet „paarweise alle" von „nur gegen den
    ersten Kandidaten verglichen".

- **AC-6:** Given genau ein GPX-Kandidat besteht die Vollständigkeitsregel für eine Etappe / When
  die Track-Auflösung läuft / Then liefert sie unverändert das Ergebnis dieses einen Kandidaten
  (Regressionsschutz gegenüber #2036 AC-7).
  - Test: Der bestehende Test für den Einzeltreffer-Fall (eine GPX-Datei im Bestand) läuft
    unverändert grün und liefert dieselben Kilometerwerte wie vor dieser Änderung.

- **AC-7:** Given kein GPX-Kandidat im Bestand besteht die Vollständigkeitsregel für eine Etappe /
  When die Track-Auflösung läuft / Then liefert sie `None`, und die Ortsangabe bleibt byte-identisch
  `Segment N` (Regressionsschutz #2036 AC-10).
  - Test: Der bestehende Test für den Kein-Treffer-Fall (unpassende GPX-Datei) läuft unverändert
    grün; `format_alert_location(None, ..., km_measured=False)` liefert weiterhin exakt
    `Segment N`.

- **AC-8:** Given eine Etappe enthält einen Wegpunkt, der mehr als 10 m vom nächstgelegenen Punkt
  eines sonst passenden Tracks abweicht, während andere Kandidaten für dieselbe Etappe die
  Vollständigkeitsregel erfüllen / When die Track-Zuordnung läuft / Then bleibt die Etappe
  insgesamt unvermessen — die Vollständigkeitsregel (`_match_track`) verwirft den abweichenden
  Kandidaten vollständig, bevor er überhaupt in den Ergebnisgleichheits-Vergleich eingeht
  (Regressionsschutz #2036 AC-12, `_match_track` unangetastet).
  - Test: Der bestehende AC-12-Test (ein zusätzlicher, 15 m abseits liegender Wegpunkt neben einem
    sonst exakt passenden Track) läuft unverändert grün und liefert weiterhin `None`.

- **AC-9:** Given zwei oder mehr GPX-Kandidaten sind paarweise ergebnisgleich / When die
  Track-Auflösung für denselben Bestand mehrfach ausgeführt wird / Then liefert jeder Lauf
  denselben Rückgabewert (dieselben Kilometerwerte, aus demselben Kandidaten in
  `sorted(...)`-Reihenfolge).
  - Test: Dieselbe Kandidatenmenge wird zweimal hintereinander gegen `resolve_stage_track_km()`
    ausgeführt; beide Rückgaben sind identisch (Dict-Vergleich auf Gleichheit, nicht nur
    „ist nicht None").

- **AC-10:** Given eine Etappe wird über den bestehenden Rückschreibweg
  (`backfill_stage_distances`) nachgetragen, nachdem die Track-Auflösung durch Ergebnisgleichheit
  ein Ergebnis liefert, das vorher `None` gewesen wäre / When die Distanz additiv an den Trip
  zurückgeschrieben wird / Then landet nur die betroffene Etappe verändert, alle anderen Etappen
  und vom Python-Loader nicht modellierte (Go-only-)Felder bleiben unverändert erhalten
  (Regressionsschutz #2036 AC-7).
  - Test: Ein Trip mit zwei GPX-Dublett-Kandidaten im Bestand (analog AC-1) wird durch
    `backfill_stage_distances()` geschickt; nach dem Speichern trägt nur die betroffene Etappe die
    nachgetragene Distanz, alle übrigen Etappen sowie ein zuvor manuell in die JSON-Datei
    eingefügtes, dem Python-Modell unbekanntes Feld bleiben unverändert.

## Nicht Teil dieser Spec

- **Scheibe 2 (Sichtbarkeit des stillen Fehlschlags)** ist per PO-Entscheid 2026-08-22 auf nach der
  KHW-Tour verschoben. Der Fehlschlag der Track-Auflösung bleibt in dieser Scheibe weiterhin still
  (`logger.warning` bei nicht lesbaren Dateien, sonst kein Signal nach außen).
- **`_match_track()` / die Vollständigkeitsregel** wird nicht verändert — sie bleibt „alles oder
  nichts je Kandidat" (AC-12 aus #2036).
- **`test.gpx`** (der im Ticket genannte Aufräum-Rest im Produktivbestand) wird durch diese Spec
  gegenstandslos, aber nicht gelöscht — Produktivdaten des PO werden nicht angefasst.

## Bestandstests, die grün bleiben müssen

`tests/tdd/test_track_resolution_legacy_trip.py` — insbesondere
`test_ac7_eindeutiger_track_liefert_die_gemessenen_distanzen`,
`test_ac10_kein_passender_track_liefert_kein_ergebnis`,
`test_ac12_wegpunkt_mehr_als_10m_abseits_verhindert_die_zuordnung`,
`test_ac12_default_toleranz_nimmt_den_exakt_passenden_track_an`,
`test_ac12_default_toleranz_weist_einen_15m_abseits_liegenden_wegpunkt_ab`,
`test_ac7_rueckschreiben_erhaelt_go_only_felder`,
`test_ac7_alarm_pfad_loest_die_nachruestung_aus`,
`test_ac7_briefing_pfad_loest_die_nachruestung_weiterhin_aus`,
`test_ac7_zweite_aufloesung_schreibt_nicht_erneut`.

**`test_ac11_zwei_gleichwertige_treffer_liefern_kein_ergebnis` muss umgeschrieben werden** — er
kopiert heute dieselbe Fixture-Datei zweimal und erwartet `None`. Genau dieses Verhalten wird durch
AC-1 dieser Spec abgeschafft. Der Test wird auf zwei Kandidaten mit **wirklich abweichenden**
Ergebnissen umgestellt (Vorbild: AC-4/AC-5 dieser Spec), damit die Eindeutigkeitsregel ihren
Wächter behält — sie darf nicht ersatzlos entfallen, nur ihr Auslöser ändert sich von „Anzahl" auf
„Ergebnisunterschied".

## Risiken

1. **Der bewachende Test kippt, wenn er nicht mit umgeschrieben wird.** Ohne Anpassung von
   `test_ac11_...` verliert die Eindeutigkeitsregel ihren einzigen Nachweis — siehe Abschnitt
   „Bestandstests, die grün bleiben müssen".
2. **Vollständige Schleife statt Früh-Abbruch.** Der Alarmlauf hat eine Zeitobergrenze (ADR-0038,
   120 s), der gemessene GPX-Bestand umfasst 20 Dateien; im real gemessenen Fall parst die
   Schleife auch heute schon fast alle Dateien, der Mehraufwand ist begrenzt. Entschärft zusätzlich
   durch die bestehende `_failed_lookups`-Prozess-Sperre (`track_resolution.py:106-107`).
3. **Referenzvergleich statt paarweise wäre eine stille Verdoppelung der Toleranz.** Muss im
   Adversary-Dialog aktiv gegengeprüft werden (AC-5).
4. **Ohne echten Ergebnisunterschied bleibt alles wie heute.** Das ist die Fallback-Garantie
   (AC-4, AC-7), kein Bug — muss aber als Positivfall geprüft werden, nicht nur impliziter
   Nebeneffekt.

## Known Limitations

- **Rundungsgrenzfall:** Die Anzeige rundet auf ganze Kilometer. Liegen zwei ergebnisgleiche
  Kandidaten nahe einer .5-km-Grenze (z. B. 12,497 vs. 12,503 km), kann die Auswahl des ersten
  Kandidaten in `sorted(...)`-Reihenfolge den angezeigten gerundeten Wert um 1 km verschieben.
  Bewusst akzeptiert: die Alternative wäre, den bereits eindeutigen Fall wieder zu verwerfen.
- **Wegpunkt-Stichprobe statt Pfadvergleich:** Ergebnisgleichheit wird an den Wegpunkten geprüft,
  nicht über den gesamten Trassenverlauf zwischen ihnen. Zwei Aufzeichnungen könnten an den
  Wegpunkten zusammenfallen und dazwischen abweichen. Kein neues Risiko — AC-12 der Vorgänger-Spec
  akzeptiert dieselbe Stichprobenlogik bereits für den Einzelkandidaten.
- **Laufzeit:** Ohne Früh-Abbruch wird bei mehreren Vollständigkeits-Treffern der gesamte
  GPX-Bestand geparst, statt bei zwei Treffern abzubrechen. Entschärft durch die
  `_failed_lookups`-Sperre (einmal je `(user_id, trip_id, stage_id)` pro Prozess) und die
  bestehende Zeitobergrenze je Nutzerlauf (ADR-0038, 120 s, bewacht von
  `tests/tdd/test_alert_run_deadline.py`). Gemessener Bestand: 20 Dateien.
- **Scheibe 2 ist NICHT Teil dieser Spec:** Der Fehlschlag der Track-Auflösung bleibt still.
  Sichtbarmachung am Trip (zweiter Teil von #2073) ist per PO-Entscheid 2026-08-22 auf nach der
  KHW-Tour verschoben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine reine Verhaltensänderung innerhalb einer bestehenden
  Funktion (`resolve_stage_track_km`) — kein neues Datenfeld, keine Schema-Änderung, kein neuer
  Kanal, keine neue Persistenzentscheidung. Die Eindeutigkeitsregel aus #2036 (AC-11) bleibt
  inhaltlich bestehen, nur ihr Auslöser wechselt von „Anzahl der Kandidaten" auf „Ergebnisdifferenz
  zwischen den Kandidaten".

## Nachweisführung

- **AC-1 allein beweist die Wirksamkeit nicht.** Byte-identische Dateien würden auch bei einer
  fehlerhaft entfernten (statt korrekt umgestellten) Ergebnisgleichheitsprüfung ein Ergebnis
  liefern. **AC-2 ist der eigentliche Wirksamkeitsnachweis** — echt unterschiedliche, aber
  innerhalb der Toleranz liegende Kandidaten.
- **AC-4 ist der Gegenfall zu AC-1/AC-2/AC-3** und existiert, um eine versehentliche
  „immer-ja"-Logik fangbar zu machen (jede Kombination gilt als ergebnisgleich, wenn die
  Differenzprüfung fehlt oder invertiert ist). Ohne AC-4 bliebe diese Mutation unsichtbar.
- **AC-5 ist der Gegenfall zu „Referenzvergleich statt paarweise"** — ein Implementierung, die nur
  gegen den ersten Kandidaten vergleicht statt alle Paare, besteht AC-1 bis AC-4, aber nicht AC-5.
- **AC-8 ist der Regressionsnachweis, dass `_match_track` unangetastet bleibt** — eine
  Implementierung, die versehentlich die Vollständigkeitsregel mit der Ergebnisgleichheitsregel
  vermischt (z. B. einen 15 m abseits liegenden Wegpunkt über die neue Toleranz durchwinkt),
  fällt hier auf.
- Tests lösen ihren Prüfling **relativ zur eigenen Testdatei** auf, nie über den festen
  Hauptrepo-Pfad, damit sie im Worktree korrekt gegen den lokalen Stand laufen (Muster:
  `tests/tdd/test_track_resolution_legacy_trip.py`).

## Changelog

- 2026-08-22: Initial spec created
