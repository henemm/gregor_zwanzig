---
entity_id: fix_1667_s2_naismith_wrap
type: bugfix
created: 2026-08-10
updated: 2026-08-11
status: draft
workflow: fix-1667-s2-naismith-wrap
version: "1.2"
tags: [issue-1667, naismith, midnight-wrap, cross-language-parity, arrival-time]
---

# S2 — Naismith-Ankunftszeit: Klemme → Modulo (Python/Go/TS)

## Approval

- [x] Approved — PO-„go" 2026-08-10

## 🔴 Diese Scheibe schließt Issue #1667 NICHT

**Update 2026-08-11: mittlerweile durch S3 geschlossen** — s. „Known
Limitations" unten. Der Rest dieses Abschnitts beschreibt den Scope von S2
selbst und bleibt als solcher richtig: S2 allein schloss #1667 nicht.

**S2 macht Nacht-Ankünfte *darstellbar*, nicht *erreichbar*.** Sie behebt die
23:59-Klemme in den drei `formatHHMM`-Kopien und damit den Datenkollaps im
Segmentbau (`wp_days`-Rollover erkennt den Tageswechsel wieder, weil die
Ankunftszeiten nicht mehr künstlich auf denselben Wert zusammenfallen). Die
eigentliche Sicherheitslücke — dass `trip_alert.py:745`
(`convert_trip_to_segments(trip, today)`) nach Mitternacht für einen
Ein-Etappen-Trip `[]` liefert und damit **null Alarme** erzeugt, obwohl
korrekt gebaute Segmente existierten — bleibt nach S2 **unverändert offen**.
Sie ist Gegenstand von S3 (tagesübergreifende Segment-Auswahl als additiver
Fallback). **Issue #1667 bleibt bis S3 offen** (PO-Entscheidung 2026-08-10,
`docs/context/fix-1667-arrival-midnight-wrap.md`, Abschnitt „PO-Entscheidungen").

Zusätzlich **keine** Editor-Kennzeichnung „(+1)" für Folgetags-Ankünfte —
eigene, kleine Arbeit danach (PO-Entscheidung 2026-08-10). S2 zeigt im Editor
nur die korrekte Uhrzeit (z. B. „02:23"), ohne Datumshinweis.

## Purpose

Drei bit-identische Kopien einer Formatierfunktion — `_format_hhmm()`
(`src/core/naismith.py:54-60`), `formatHHMM()`
(`internal/model/naismith.go:84-97`) und `formatHHMM()`
(`frontend/src/lib/utils/naismith.ts:62-68`) — klemmen Naismith-Ankunftszeiten
auf `23:59` (`min(total_min, 24*60-1)` bzw. Go-Äquivalent). Bei einer Etappe,
deren kumulierte Gehzeit über Mitternacht reicht (erreichbar ohne Trick — ein
Abendstart 18:00 mit 10 h Gehzeit genügt; `StageTimeField.svelte:34` hat kein
`min`/`max`), fallen mehrere Wegpunkte auf denselben Wert `"23:59"`.

Das zerstört das Signal, an dem `src/services/trip_segments.py:151-159` den
Tageswechsel erkennt: der Rollover wird **nur bei strikt fallender** Uhrzeit
zwischen zwei Wegpunkten ausgelöst (`t < prev`); `"23:59" == "23:59"` ist
weder fallend noch informativ. Gemessen an `start_time=22:00`, 4 Wegpunkten,
Korsika (`docs/context/fix-1667-arrival-midnight-wrap.md`, Abschnitt „Die
Sicherheitslücke — gemessen, nicht hergeleitet"):

| Messpunkt | Ergebnis |
|---|---|
| `arrival_calculated` | `['22:00','23:59','23:59','23:59']` — 3 von 4 auf der Klemme |
| Segmente (`convert_trip_to_segments`) | **2 statt 4** — Kollaps-Guard (`trip_segments.py:194-205`) verwirft 15,6 km / 1800 Hm samt Wetterüberwachung |
| Ziel-Segment | 1h-Mindestfenster statt Tagesfenster |

Der Fix: `min(total_min, 24*60-1)` → `total_min % (24*60)` in allen drei
Sprachen. Damit liefert eine über Mitternacht reichende Etappe monoton
fortlaufende (aus Tagessicht: umlaufende) Uhrzeiten statt eines dreifachen
Plateaus, der `wp_days`-Rollover erkennt den Tageswechsel wieder korrekt, und
alle vier Segmente entstehen.

**Gemessene Wirkung (M1, Kontext-Dokument, Abschnitt „Zwei Messungen, die den
Zuschnitt bestimmen"):**

| Start | Klemme (heute) | `total_min % (24*60)` |
|---|---|---|
| 08:00 | `['08:00','12:23','14:58','19:21']` → 4 Segmente | **bit-identisch** |
| 18:00 | `['18:00','22:23','23:59','23:59']` → **3** Segmente | `['18:00','22:23','00:58','05:21']` → **4** Segmente |
| 22:00 | `['22:00','23:59','23:59','23:59']` → **2** Segmente | `['22:00','02:23','04:58','09:21']` → **4** Segmente |

🔴 **Diese Tabelle ist ein Herkunftsbeleg, kein Testfixture.** Die
zugrundeliegenden Wegpunkt-Koordinaten der Korsika-Beispieletappe stammen aus
einem einmaligen Handlauf beim Schreiben des Kontext-Dokuments und sind
**nirgends im Repo eingecheckt**. Die Uhrzeiten oben belegen die
Größenordnung der Wirkung (2 statt 4 Segmente), dürfen aber **nicht** als
Erwartungswerte in einem Test verwendet werden — ein Entwickler müsste dafür
Koordinaten raten, die zufällig auf exakt diese Minutenwerte führen. Genau
die „geratene Zahl", die diese Spec an anderer Stelle vermeiden will (s.
Spec-Prüfung, Befund 1). Die Acceptance Criteria unten (AC-1/AC-2) prüfen
dieselbe Eigenschaft strukturell, ohne diese Zahlen vorauszusetzen.

### 🔴 Verworfene Alternative: Klemme anheben statt Modulo

Naheliegend wäre, die Klemme einfach zu lockern (z. B. auf `"25:30"`
formatieren) statt zu wickeln. **Das würde den Datenkontrakt brechen und
wurde deshalb verworfen.** Die Go-Begründung der bestehenden Klemme
(`naismith.go:86-90`) lautet wörtlich: die Python-Gegenseite `_parse_hhmm`
kann einen Stunden-Teil `>23` nicht konsumieren und fällt sonst still auf die
divergente Interpolation zurück — das untergräbt das Ziel „Editor-Zeit ==
Wetterabruf-Zeit". Diese Bedingung gilt unverändert; der Modulo **erfüllt**
sie, statt sie zu umgehen: er liefert weiterhin ausschließlich Werte im
Bereich `00:00`–`23:59`.

`docs/reference/api_contract.md:917` (`ArrivalCalculated ... "HH:MM"`) bleibt
dadurch **wortgleich gültig** — kein Feld, kein Format, kein Kommentar dort
ändert sich. Ein echtes Anheben der Klemme hätte drei stille, voneinander
abweichende Rückfälle erzeugt: Python `time.fromisoformat("25:30")` wirft
eine Exception, Go `fmt.Sscanf` mit `%d:%d` würde bei `h>23` laut
`parseStartMinutes` ohnehin auf `08:00` zurückfallen, und die TS-Regex
`/^(\d{1,2}):(\d{1,2})$/` mit der Bereichsprüfung `h<=23` würde ebenfalls auf
den Default zurückfallen — drei unterschiedliche, ungeprüfte Rückfälle ohne
Paritätstest dazwischen. Dieser Absatz steht hier, damit die Alternative
nicht erneut erwogen wird.

## Source

- **Files:** `src/core/naismith.py`, `internal/model/naismith.go`,
  `frontend/src/lib/utils/naismith.ts` (Produktivcode); je ein
  Test-Update in fünf bestehenden Dateien + drei neue Paritäts-/
  Wirkungs-Testdateien + eine gemeinsame Fixture
- **Identifier:** `_format_hhmm()` (Python), `formatHHMM()` (Go, Zeile
  84-97), `formatHHMM()` (TS, Zeile 62-68, bislang nicht exportiert)

> **Schicht-Hinweis:** Betrifft **alle drei** Schichten gleichzeitig —
> Python-Core (`src/core/naismith.py`), Go-API
> (`internal/model/naismith.go`) und Frontend
> (`frontend/src/lib/utils/naismith.ts`). Das ist die Fehlerklasse selbst:
> drei parallele Implementierungen ohne gemeinsamen Test. Die Spec verlangt
> deshalb einen echten Cross-Language-Paritätstest, keine drei separaten
> Einzeiler.

## Affected Files

| Datei:Zeile | Änderung |
|---|---|
| `src/core/naismith.py:59` | `_format_hhmm`: `total_min = min(total_min, 24*60-1)` → `total_min = total_min % (24*60)` |
| `internal/model/naismith.go:91-96` | `formatHHMM`: Klemm-`if` → `totalMin %= 24 * 60`; Kommentar Zeile 84-90 aktualisiert — Begründung („Python kann >23h nicht konsumieren") bleibt stehen, „Clamp" wird zu „Wrap" |
| `frontend/src/lib/utils/naismith.ts:62-68` | `formatHHMM`: Klemme → `totalMin % (24*60)`; Funktion bekommt **`export`** für Direkttest aus der Parity-Suite (bislang nur intern genutzt) |
| `tests/tdd/test_issue_802_fahrrad_segment_zeit.py:28` | Contract `"C"`: Erwartung `["08:00","23:59"]` → Modulo-Wert für dieselbe Höhendifferenz (neu berechnet, keine geratene Zahl) |
| `internal/model/naismith_802_test.go:77-86` | `TestNaismith802_C`: gleiche Anpassung, bit-identisch zu Python-Fixture C |
| `internal/model/naismith_test.go:160-189` | `TestFormatHHMM_ClampsOverflow` → umbenannt `TestFormatHHMM_WrapsPastMidnight`; Assertion auf Modulo-Wert; Begründungskommentar (Zeile 160-164, 184) bleibt inhaltlich erhalten, nur „Clamp"/„geclampt" → „Wrap"/„gewickelt" korrigiert — **umgeschrieben, nicht gelöscht**, sonst geht die einzige Dokumentation der `_parse_hhmm`-Kontrakt-Überlegung verloren |
| `tests/tdd/test_issue_1004_startzeit_ssot.py:207-248` | `test_ac5_spaete_startzeit_kein_totalausfall` → umbenannt `test_ac5_spaete_startzeit_alle_segmente_erhalten`; Erwartung ändert sich fundamental: statt „Kollaps + Warnung" jetzt „alle 4 Segmente vorhanden, keine Kollaps-Warnung" |
| `src/services/trip_segments.py:194-205` | **Nur Kommentar** korrigiert — „vermutlich Mitternachts-Klemme (23:59)" wird nach S2 falsch, weil die Klemme nicht mehr existiert; der Guard selbst (fängt weiter `==`-Zeiten aus der Interpolation, #1091) bleibt unverändert bestehen |
| `tests/fixtures/naismith_hhmm_wrap.json` (neu) | Gemeinsame Paritäts-Fixture: Minuten-Werte `1439/1440/1441/2879` mit je erwartetem `"HH:MM"`-String (Randfälle für AC-3) — **eine** Quelle für alle drei Sprachtests |
| `tests/tdd/test_naismith_hhmm_wrap_parity.py` (neu) | Python-Seite: Eigenschaftsnachweis über `range(1440)` gegen die alte Klemmformel als Referenz (AC-1) + Randfall-Test gegen die JSON-Fixture (AC-3) |
| `internal/model/naismith_wrap_parity_test.go` (neu) | Go-Seite derselben zwei Tests (AC-1, AC-3), liest dieselbe JSON-Fixture für AC-3 |
| `frontend/src/lib/utils/naismith_wrap_parity.test.ts` (neu) | TS-Seite derselben zwei Tests (AC-1, AC-3); Wurzel-Erkennung für den Fixture-Zugriff ist ein eigenes Umsetzungsrisiko (s. Implementation Details) |
| `tests/tdd/test_naismith_midnight_wrap_segments.py` (neu) | Wirkungsbeleg am Segmentbau mit eingecheckter, koordinatenfreier Fixture (AC-2) + Mutations-Gegenprobe (AC-4) |

**Nicht angefasst (bewusst):** `docs/reference/api_contract.md` — bleibt
wortgleich gültig (s. o.). `src/app/loader.py:1684-1688` und
`internal/store/trip.go:228-241` (Compute-on-Save-Aufrufer) rufen
`compute_stage_arrivals`/`ComputeStageArrivals` unverändert auf; sie
verhalten sich automatisch korrekt, weil sich nur die interne Formatierung
ändert, nicht die Aufruf-Signatur.

## Estimated Scope

- **LoC:** ~95–115 (3× Produktivcode-Einzeiler + Go/TS-Kommentarpflege
  ~15 LoC; 3 bestehende Testdateien umgeschrieben ~25-35 LoC Delta; 1
  Kommentarkorrektur `trip_segments.py` ~4 Zeilen; neue Randfall-Fixture
  ~15-20 LoC; drei Paritäts-Testdateien (Eigenschaftsnachweis + Randfälle)
  ~20-25 LoC je Sprache; ein Wirkungs-/Mutationstest mit eingecheckter
  Wegpunkt-Fixture ~30-35 LoC)
- **Files:** 8 geänderte + 5 neue = 13
- **Effort:** medium — die Änderung selbst ist trivial (drei Einzeiler),
  der Aufwand liegt im Paritätstest über drei Sprachen (inkl. eines neu zu
  bauenden Wurzel-Erkennungs-Mechanismus auf der TS-Seite) und im sauberen
  Umschreiben (nicht Löschen) der vorbestehenden Klemm-Tests

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_segments.py::convert_trip_to_segments` (Zeile 151-159, `wp_days`) | module | Wirkort der Änderung — hier zeigt sich, ob der Modulo den Rollover wieder erkennbar macht; AC-2/AC-4 prüfen hier, nicht nur an `_format_hhmm` |
| `tests/tdd/test_issue_802_fahrrad_segment_zeit.py::_CONTRACT` | fixture | Bestehender fixer Wertekontrakt Python↔Go; Contract C trägt heute die Klemme und muss auf den Modulo-Wert umgestellt werden |
| `internal/model/naismith_802_test.go` | test | Go-Spiegel desselben Kontrakts — Contract C dort synchron anpassen |
| `internal/mail/recipient_parity_test.go::findRepoRoot` (Zeile 41-63) | pattern | Vorbild für Wurzel-Erkennung: Aufwärtssuche im Dateisystem bis `go.mod` gefunden ist (max. 6 Ebenen), statt fester `../../..`-Kette. Go **hat** damit bereits ein Vorbild für den Fixture-Zugriff dieser Scheibe, Python ebenfalls (`Path(__file__).resolve().parents[2]`) — **die TS-Seite hat keins** (s. Implementation Details, Umsetzungsrisiko) |
| `tests/unit/test_alarm_zeitfenster_ziel.py::test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster` (Zeile 605) | guard | Fremde Zusicherung aus #1584 (PO-Entscheidung 2026-08-08), sitzt im `window_end <= arrival_time`-Guard — von S2 nicht berührt, muss als Regressionsbeleg grün bleiben |
| `src/services/segment_weather.py:453-457` | risk | Nachtfenster (arrival → 06:00 Folgetag) springt bei UTC-Mitternachts-Ankunft von ~6h auf ~30h Providerabruf; nach S2 werden Nacht-Ankünfte erstmals real gebaut — Pflicht-Nachmessung in der Adversary-Runde (s. Risiko) |

## Implementation Details

Kern der Änderung, alle drei Sprachen bit-identisch im Verhalten:

```
# Python (naismith.py:59)
total_min = total_min % (24 * 60)   # statt: min(total_min, 24*60-1)

// Go (naismith.go:91-96)
func formatHHMM(totalMin int) string {
    totalMin %= 24 * 60             // statt: Klemm-if auf maxMin
    return fmt.Sprintf("%02d:%02d", totalMin/60, totalMin%60)
}

// TS (naismith.ts:63-68) — export ergänzt für Paritätstest
export function formatHHMM(totalMin: number): string {
    const wrapped = totalMin % (24 * 60);   // statt: Klemme auf MAX_MINUTES
    ...
}
```

`totalMin`/`total_min` ist an allen drei Aufrufstellen bereits `>= 0`
(Startzeit `>= 0`, kumulierte Naismith-Minuten `>= 0` addiert) — ein
negativsicherer Modulo (`((x % m) + m) % m`) ist **nicht nötig**, liefert
für nicht-negative Eingaben aber denselben Wert wie der einfache Modulo.
Die Implementierung verwendet den einfachen Modulo; ein Kommentar an der
Stelle hält fest, warum Negativsicherheit hier nicht gebraucht wird (das
verhindert eine spätere, unnötige „Sicherheits"-Änderung durch jemanden,
der die Invariante nicht kennt).

**Paritäts-Fixture** (`tests/fixtures/naismith_hhmm_wrap.json`): Liste von
`{"total_min": N, "expected_hhmm": "HH:MM"}`-Objekten für die vier Kanten
`1439` (23:59, letzte Minute vor der Klemme/vor dem Wrap — muss
unverändert `23:59` bleiben), `1440` (24:00 — erste gewickelte Minute,
muss `00:00` sein, war bisher fälschlich `23:59`), `1441` (24:01 → `00:01`)
und `2879` (47:59, zwei volle Tage minus eine Minute → wieder `23:59` —
prüft, dass der Modulo auch über mehrere Tageslängen hinweg korrekt
umläuft, nicht nur einmal). Alle drei Sprachtests laden **dieselbe** Datei
und iterieren dieselben Fälle — keine drei gespiegelten Listen. Diese
Fixture deckt ausschließlich die Randfälle für AC-3 ab; der vollständige
Eigenschaftsnachweis für AC-1 (Bereich `0..1439`) braucht **keine**
Fixture-Datei, weil die Referenzformel (`min(m, 1439)`) direkt im Testcode
jeder Sprache steht.

### 🔴 Umsetzungsrisiko: TS-Seite der Paritäts-Fixture hat kein Vorbild

Go hat mit `internal/mail/recipient_parity_test.go::findRepoRoot` (Zeile
41-63) bereits ein erprobtes Muster: Aufwärtssuche im Dateisystem ab
`os.Getwd()` bis ein Verzeichnis mit `go.mod` gefunden ist (begrenzt auf 6
Ebenen, mit klarer Fehlermeldung statt stillem Leerlauf). Python hat
reichlich Vorbilder mit `Path(__file__).resolve().parents[2]`.

**Die TS-Seite hat kein Vorbild.** Kein einziger Test unter
`frontend/src/**/*.test.ts` liest heute eine Datei außerhalb von
`frontend/` — die Naismith-TS-Tests laufen über
`node --experimental-strip-types --test` mit `cd frontend` als Arbeits-
verzeichnis. `naismith_wrap_parity.test.ts` muss deshalb als **erster**
TS-Test im Repo einen Wurzel-Erkennungsmechanismus neu bauen.

**Richtung, nicht Rezept:** Aufwärtssuche analog zu Go-`findRepoRoot` — z. B.
ab `import.meta.url`/`process.cwd()` aufwärts, bis ein Verzeichnis mit `.git`
oder der Wurzel-`package.json` gefunden ist. **Verboten** ist eine feste
`../../../../`-Kette: die bricht lautlos, sobald die Testdatei verschoben
wird, und verstößt gegen Pfadregel #1409 (s. `CLAUDE.md` — ein Test löst
seinen Prüfling relativ zur eigenen Testdatei per Aufwärtssuche auf, nie
über eine fest verdrahtete Ebenenzahl). Diese Spec legt die Richtung fest;
die konkrete Umsetzung (genaues Suchkriterium, Fehlerverhalten bei nicht
gefundener Wurzel) fällt in der Implementierung.

## Expected Behavior

- **Input:** Eine Etappe mit `start_time` und Wegpunkten, deren kumulierte
  Naismith-Gehzeit die 24h-Grenze über- oder mehrfach überschreitet.
- **Output:** `arrival_calculated` je Wegpunkt ist weiterhin ein reiner
  `HH:MM`-String im Bereich `00:00`–`23:59` (Datenkontrakt unverändert),
  aber Wegpunkte nach Mitternacht tragen jetzt die tatsächliche
  Uhrzeit statt eines dreifachen `23:59`-Plateaus. Der Segmentbau
  (`convert_trip_to_segments`) erkennt den Tageswechsel über den
  bestehenden `wp_days`-Rollover und baut alle Segmente statt sie am
  Kollaps-Guard zu verwerfen.
- **Side effects:** Trips mit `start_time <= ~14:00` (Normalfall,
  kein Bestands-Trip hat je `start_time` gesetzt, s. Kontext-Dokument
  „Datenmodell — Ist-Stand nachgemessen") sind **bit-identisch** — die
  Änderung ist im Alltag inert. Erst Etappen, die real über Mitternacht
  laufen, ändern sich sichtbar.

## Acceptance Criteria

- **AC-1 (Eigenschaftsnachweis der Inertheit, ohne Wegpunkt-Fixture):**
  Given der volle Minutenbereich `0..1439` (jede Ankunft, die unter der
  alten 23:59-Klemme lag) / When für jeden Wert `m` in diesem Bereich sowohl
  die alte Klemmformel (`min(m, 1439)`, als Referenzimplementierung direkt
  im Test hinterlegt) als auch die neue Modulo-Implementierung
  (`_format_hhmm`/`formatHHMM`/`formatHHMM`, alle drei Sprachen) ausgewertet
  werden / Then liefern beide für **jeden** Wert in diesem Bereich denselben
  `HH:MM`-String — ein vollständiger Eigenschaftsnachweis der Inertheit
  statt eines Belegs an vier Beispielpunkten, und ohne dass dafür
  Wegpunktdaten existieren müssten.
  - Test: `tests/tdd/test_naismith_hhmm_wrap_parity.py` (Python),
    `internal/model/naismith_wrap_parity_test.go` (Go),
    `frontend/src/lib/utils/naismith_wrap_parity.test.ts` (TS) — je eine
    Schleife über `range(1440)` bzw. `0..1439`; Assert Gleichheit zur lokal
    hinterlegten Referenzformel `min(m, 1439)` in jedem Iterationsschritt.

- **AC-2 (Wirkungsbeleg am Segmentbau, strukturell statt zahlenwörtlich):**
  Given eine im Testfile eingecheckte Wegpunkt-Fixture (Koordinaten frei
  wählbar, einzige Bedingung: die kumulierte Naismith-Gehzeit überschreitet
  ab `start_time=22:00` die Mitternachtsgrenze) / When
  `convert_trip_to_segments(trip, target_date)` einmal mit
  `start_time=22:00` und einmal mit `start_time=08:00` auf derselben
  Fixture aufgerufen wird / Then gilt für den 22:00-Lauf: (a) es entstehen
  so viele Segmente wie Wegpunkt-Paare — keins wird am Kollaps-Guard
  verworfen; (b) keine zwei aufeinanderfolgenden `arrival_calculated`-Werte
  sind gleich (das Plateau ist genau der ursprüngliche Defekt); UND im
  Vergleich beider Läufe: (c) die Zeitdifferenzen zwischen aufeinander-
  folgenden Wegpunkten sind in beiden Läufen identisch (modulo
  Tageswechsel) — die Naismith-Berechnung selbst ist unverändert, nur die
  Formatierung wickelt statt zu klemmen.
  - Test: `tests/tdd/test_naismith_midnight_wrap_segments.py`,
    `test_start_22_uhr_liefert_alle_segmente_ohne_plateau`; Assert
    Anzahl der Wegpunkt-Paar-Segmente `== len(waypoints) - 1` (a) —
    **korrigiert 2026-08-10 in der RED-Phase:** `convert_trip_to_segments`
    hängt zusätzlich ein `Ziel`-Segment an (`trip_segments.py:313`), ein
    nacktes `len(segments) == len(waypoints) - 1` wäre also um eins falsch;
    gezählt werden die Paar-Segmente (`segment_id != "Ziel"`). Assert paarweise
    Ungleichheit aufeinanderfolgender `arrival_calculated`-Strings (b),
    Assert Delta-Gleichheit gegen den `start_time=08:00`-Lauf derselben
    Fixture (c).

- **AC-3 (Cross-Language-Paritätstest an den vier Randfällen):** Given die
  gemeinsame Fixture `tests/fixtures/naismith_hhmm_wrap.json` mit den
  Minutenwerten `1439/1440/1441/2879` / When `_format_hhmm` (Python),
  `formatHHMM` (Go) und `formatHHMM` (TS, neu exportiert) je mit denselben
  Werten aus derselben Fixture aufgerufen werden / Then liefern alle drei
  Implementierungen für jeden Wert exakt denselben `HH:MM`-String
  (`23:59`, `00:00`, `00:01`, `23:59`) — bislang existierte an keinem der
  drei Orte ein Test, der die Kopien gegeneinander prüft.
  - Test: `tests/tdd/test_naismith_hhmm_wrap_parity.py`,
    `internal/model/naismith_wrap_parity_test.go`,
    `frontend/src/lib/utils/naismith_wrap_parity.test.ts` — alle drei
    laden dieselbe JSON-Fixture und parametrisieren über deren Einträge;
    Assert Gleichheit je Eintrag in jeder der drei Suiten.

- **AC-4 (Mutations-Gegenprobe, Pflicht):** Given der Modulo in
  `_format_hhmm` (Python) wird per Textersetzung (externe Sicherungskopie,
  keine `git checkout/stash/reset`) auf die alte Klemme
  `min(total_min, 24*60-1)` zurückgedreht / When der Segmentzahl-Test aus
  AC-2 (Zusicherung a,
  `test_start_22_uhr_liefert_alle_segmente_ohne_plateau`) danach läuft /
  Then wird er rot — weniger Segmente als Wegpunkt-Paare, weil der
  Kollaps-Guard wieder greift. Das belegt, dass Zusicherung (a) tatsächlich
  die Modulo-Eigenschaft bewacht und nicht zufällig grün durchläuft.
  Mutation wird danach zurückgespielt.
  - Test: manuelle Textersetzung an `src/core/naismith.py:59`,
    `pytest tests/tdd/test_naismith_midnight_wrap_segments.py::test_start_22_uhr_liefert_alle_segmente_ohne_plateau`
    ausführen; Assert `AssertionError`. Danach Originaltext wiederherstellen.

- **AC-5 (Fremdzusicherung bleibt grün):** Given
  `tests/unit/test_alarm_zeitfenster_ziel.py::test_mitternachtsfenster_22_2_klemmt_auf_mindestfenster`
  (PO-Entscheidung 2026-08-08, sitzt im `window_end <= arrival_time`-Guard
  aus #1584) / When dieser Test nach der S2-Änderung an `_format_hhmm`
  erneut läuft / Then bleibt er unverändert grün — S2 fasst nur die
  Ankunfts*berechnung* an, nicht die Fenster*auswahl* aus #1584; beide
  laufen zufällig über denselben Guard, sind aber verschiedene Fälle
  (konfiguriertes Mitternachtsfenster vs. Etappe mit Ankunft nach
  Mitternacht).
  - Test: bestehenden Test unverändert im Kernlauf mitführen; Assert Exit
    0 ohne Anpassung an dieser Datei.

- **AC-6 (bestehende Klemm-Tests umgeschrieben, nicht gelöscht):** Given
  die drei Tests, die heute explizit die 23:59-Klemme als Sollverhalten
  festschreiben
  (`test_issue_802_fahrrad_segment_zeit.py::test_ac3_python_naismith_matches_fixed_contract[C]`,
  `naismith_802_test.go::TestNaismith802_C`,
  `naismith_test.go::TestFormatHHMM_ClampsOverflow`) / When sie nach S2
  laufen / Then erwarten sie den neu berechneten Modulo-Wert statt
  `"23:59"`, UND der Begründungskommentar in
  `naismith_test.go` (Python-Kontrakt `_parse_hhmm` kann Stunden `>23`
  nicht lesen) bleibt inhaltlich erhalten — nur als Beleg für den
  weiterhin gültigen `HH:MM`-Datenkontrakt umformuliert (`Clamp` → `Wrap`),
  nicht gelöscht.
  - Test: die drei genannten Testfunktionen laufen grün mit den neuen
    Erwartungswerten; manuelle Diff-Prüfung, dass der Kommentarblock in
    `naismith_test.go:160-164,184` weiterhin die `_parse_hhmm`-
    Begründung enthält (keine Kommentarzeile ersatzlos entfernt).

## Known Limitations

- **Die Alarm-Sicherheitslücke ist behoben — durch S3.** S2 machte
  Nacht-Ankünfte nur darstellbar, nicht erreichbar für die Alarm-Pipeline:
  `check_radar_alerts()` fragte weiterhin ausschließlich den heutigen
  Kalendertag ab. Seit Issue #1667 S3
  (`docs/specs/modules/fix_1667_s3_tagesuebergreifende_segmente.md`) löst
  `src/services/trip_segments.py::resolve_current_segment` das Ziel-Segment
  additiv tagesübergreifend auf (aktiv heute → aktiv gestern → Vorschau
  heute[0] → nichts, `trip_alert.py:911-928`) und liest den
  Briefing-Schnappschuss unter dem Datum des gewählten Segments (`:1022`)
  statt starr unter `today`. Issue #1667 ist damit vollständig geschlossen.
- **`wp_days[0]` bei manuellem `arrival_override` nach Mitternacht** ist
  weiterhin nicht darstellbar — nach S2 kommt `wp[0]` bei Naismith-
  berechneten Etappen garantiert aus `start_time` (0-23h), aber ein
  manueller Override wie `"02:00"` für den *ersten* Wegpunkt einer Etappe
  bliebe wp_days[0]==0 zugeordnet. Konstruiert, nicht in Bestandsdaten
  beobachtet (Kontext-Dokument, Abschnitt „Datenmodell — Ist-Stand
  nachgemessen": keine Etappe hat je eine Ankunft nach Mitternacht).
- **Kollaps-Guard bleibt bestehen.** `trip_segments.py:194-205` fängt
  weiterhin `end_dt <= start_dt`-Fälle aus der Interpolation (#1091) ab —
  dieser Fall ist von S2 unberührt, nur der erklärende Kommentar wird
  präzisiert.
- **Editor-Kennzeichnung „(+1)"** für Folgetags-Ankünfte ist bewusst nicht
  Teil dieser Scheibe (PO-Entscheidung 2026-08-10, s. o.).
- **`frontend/src/routes/_home/cockpitHelpers.ts:42-48` (`stageWindow`)**
  baut `"${first} – ${last}"` aus erstem und letztem Wegpunkt-
  `arrival_calculated`. Nach S2 kann dort z. B. `"22:00 – 02:23"`
  erscheinen — kein Absturz, keine Monotonie-Annahme im Code, aber es
  liest sich wie ein negatives Zeitfenster. Durch die PO-Entscheidung
  „keine (+1)-Kennzeichnung in S2" bereits fachlich abgedeckt; hier nur
  namentlich benannt, damit die Stelle nicht als neuer Bug gemeldet wird.
- **Geprüft, nichts weiter gefunden:** Die unabhängige Spec-Prüfung hat
  gezielt nach weiteren Anzeige-Konsumenten mit Monotonie-Annahme sowie
  weiteren Testdateien gesucht, die die 23:59-Klemme als Sollverhalten
  festschreiben. Außer den drei in „Affected Files" genannten Tests und der
  `stageWindow`-Stelle oben wurde **nichts** gefunden — das ist eine
  geprüfte Negativ-Aussage, kein Füllsatz.

## Risiko

**`src/services/segment_weather.py:453-457` — Pflicht-Nachmessung in der
Adversary-Runde.** Das Nachtfenster (letztes Segmentende → 06:00 Ortszeit
Folgetag) wird über `arrival.date() + timedelta(days=1)` in **UTC**
gebildet. Bei einer Ankunft kurz vor UTC-Mitternacht springt dieses Fenster
von ~6h auf ~30h Providerabruf (~2,5× erwarteter Umfang). Heute selten
erreichbar, weil Nacht-Ankünfte durch die 23:59-Klemme praktisch nie real
gebaut wurden. **Nach S2 ändert sich das** — Nacht-Ankünfte werden erstmals
real gebaut, also wird dieser Pfad erstmals real durchlaufen. Kein
Blocker für S2 selbst (kein belegter Fehlfall in zugestellter Mail), aber
ausdrücklicher Prüfpunkt für den `implementation-validator`: prüfen, ob ein
30h-Nachtfenster eine falsche Zahl in einer zugestellten Ausgabe erzeugt.
Falls ja: eigenes Issue (a: nutzersichtbares Fehlverhalten), sonst
#1199-Sammeleintrag.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Modulo ersetzt eine Klemme innerhalb derselben,
  bereits etablierten Formatierfunktion — kein neuer Auflöser, keine neue
  Zeitquelle, kein geänderter Datenkontrakt (`api_contract.md:917` bleibt
  wortgleich gültig). ADR-0044 (Kalendertage folgen der Ortszeit) ist
  bereits akzeptiert und wird durch S2 nicht berührt: S2 ändert nur, wie
  Minuten-ab-Mitternacht in einen `HH:MM`-String umgerechnet werden, nicht
  wie Kalendertage/Zeitzonen aufgelöst werden.

## Changelog

- 2026-08-10: Initial spec created
- 2026-08-10: Spec-Prüfung eingearbeitet (VERDICT: VALID, 4 Befunde) — AC-1
  und AC-2 von Magic Numbers gelöst (strukturelle statt zahlenwörtliche
  Zusicherungen), TS-Wurzel-Erkennung als Umsetzungsrisiko benannt
  (Vorbild `internal/mail/recipient_parity_test.go::findRepoRoot`),
  zwei Zitate in AC-6 korrigiert, `cockpitHelpers.ts::stageWindow` in
  Known Limitations ergänzt
- 2026-08-11: Docs-Update nach #1667 S3 (LIVE) — „Alarm-Sicherheitslücke
  bleibt offen" in Known Limitations als behoben markiert, mit Verweis auf
  `fix_1667_s3_tagesuebergreifende_segmente.md`
