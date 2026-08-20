---
entity_id: thunder_scale_guard
type: feature
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [tests, guard, ratchet, issue-1480, thunder-scale]
---

<!-- Issue #1480 — Wächter gegen lokale Kopien der Gewitter-Stufenskala -->

# Wächter gegen lokale Kopien der Gewitter-Stufenskala (#1480)

## Approval

- [ ] Approved

## Purpose

#1474 gab der Gewitterstärke eine vierte Stufe. Dabei kamen **neun** Stellen ans Licht, die
dieselbe Zuordnung lokal nachgebaut hatten — drei davon stürzten ab, drei sagten Falsches. Die
neunte entstand **beim Reparieren der vierten**: an einer korrekt umgestellten Stelle stand sogar
ein ausdrücklicher Warnkommentar vor genau dieser Falle, die Nachbarstelle, die dieselben Daten
liest, hat ihn nicht befolgt. Ein Kommentar schützt nicht, nur ein Test tut das.

Diese Lieferung baut zwei Wächter-Tests — einen Python-AST-Wächter fürs Backend, einen
Node-AST-Wächter fürs Frontend —, die rot werden, sobald irgendwo im Repo eine **neue** lokale
Kopie der Gewitter-Stufenskala (`ThunderLevel`: NONE/LOW/MED/HIGH) entsteht, egal ob in
Produktivcode oder in einem Test-Double. Sie verhindern die **nächste** Kopie, sie sanieren keine
bestehende. Kein Produktivcode wird verhaltensändernd angefasst.

## Source

- **File:** `tests/tdd/test_thunder_scale_local_copy_guard.py` (NEU) und
  `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts`
  (NEU)
- **Identifier:** Modul-Ebene in beiden Dateien — kein Produktivcode-Symbol, sondern je ein
  AST-Scan über eine feste Scanfläche (Backend: `src/**/*.py` + `api/**/*.py` für Regel A/B/C,
  zusätzlich `tests/**/*.py` für Regel D; Frontend: `frontend/src/**/*.{ts,svelte}` für Regel
  A/P/C, zusätzlich `frontend/**/*.test.ts` für Regel D) mit Auflösungslogik für
  Stufen-Literale/-Ketten sowie einer Ausnahmeprüfung über Marker-Kommentare an der Fundstelle.

> **Schicht-Hinweis:** Backend-Wächter ist reine Test-Infrastruktur (`tests/tdd/`), scannt aber
> Produktivcode in `src/`/`api/` **lesend** — er ändert dort nichts. Frontend-Wächter ist reine
> Test-Infrastruktur (`frontend/.../__tests__/`), scannt `frontend/src/**` lesend. Einzige
> tatsächliche Produktivcode-Berührung im gesamten Scope ist ein einzeiliger Marker-**Kommentar**
> in `src/output/renderers/narrow.py` (keine Verhaltensänderung, s. Scope).

## Estimated Scope

- **LoC:** ~400–500 (Backend-Prototyp allein bereits 423 Z. bei der Messung) — **LoC-Limit-
  Erhöhung auf 500 nötig** (`workflow.py set-field loc_limit_override 500`).
- **Files:** 6 (4 CREATE, 2 MODIFY) — siehe Affected Files unten.
- **Effort:** high — läuft in zwei CI-Jobs (`test`, `frontend-test`) und blockiert damit jeden PR
  jeder Session, wenn er falsch schlägt.

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | CREATE | Backend Python-AST-Wächter: Regel A/B/C/match-case, Treffsicherheits- und Fehlalarm-Selbsttests, Regel D auf `tests/`, Prüfdatum-Konstante |
| `tests/fixtures/thunder_scale_guard_cases/faelle.py.txt` | CREATE | Fixture-Quelltexte (Backend) außerhalb der Scanfläche — SYNTH-Fälle + die acht #1474-Verstöße als Vorlage |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts` | CREATE | Frontend Node-AST-Wächter: Regel A (Schwelle 3)/P/C, Regel D auf `*.test.ts`, Live-Read der kanonischen Ordnung |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/fixtures/thunder_scale_guard_cases.ts.txt` | CREATE | Fixture-Quelltexte (Frontend) außerhalb der Scanfläche — SYNTH-Fälle inkl. der neunten #1474-Stelle (Positionsfehler) |
| `src/output/renderers/narrow.py` | MODIFY | Ein Marker-Kommentar `# gz-thunder-scale: <Begründung>` an `_SEV_TO_THUNDER_LEVEL` — reine Duldung, keine Verhaltensänderung |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Neue Zeile in der Prüfdatum-Tabelle: Thunder-Scale-Wächter, Prüfdatum 2026-11-01 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1480-thunder-scale-guard.md` | Faktenbasis | Empirische Messung der Regeln A/B/C/P/D gegen drei Korpora (IST, VORHER = `860a3baf^`, SYNTH); Quelle aller Zahlen in dieser Spec |
| `src/app/models.py:35-43` | Kanonische Quelle | `ThunderLevel(str, Enum)` — die Wahrheit über die Stufenmenge NONE/LOW/MED/HIGH |
| `src/app/thunder_scale.py` | Kanonische Quelle | `_THUNDER_ORDER`, `thunder_ordinal()`, `thunder_label_value()`, `THUNDER_SIGNAL_LABEL_DE` — wird vom Frontend-Wächter live per `uv run python3 -c …` gelesen |
| `src/output/metric_format.py:283-312` | Kanonische Quelle | `THUNDER_LABEL_DE`, `_THUNDER_AMPEL_BAND`, `thunder_ampel_band()` — muss auf der Whitelist stehen, sonst meldet der Wächter die kanonische Quelle selbst |
| `frontend/src/lib/types.ts:401` | Kanonische Quelle | `export type ThunderLevel = 'NONE'\|'LOW'\|'MED'\|'HIGH'` |
| `frontend/.../corridor-editor/corridorEditorState.ts:407` | Kanonische Quelle | `ORDINAL_ENUM` — Index-Quelle des Frontends |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | Bauform-Vorbild | AST-Ratsche mit Marker-Kommentar (`# gz-main-path: <Begründung>`, Mindestlänge 15), `EXPIRY`-Konstante, Fixture-Auslagerung nach `.py.txt` außerhalb der Scanfläche mit eigenem Selbstbezug-Test |
| `frontend/.../weather-metrics-tab/__tests__/thunderThresholdCatalogGuard.test.ts` | Bauform-Vorbild + Vorgänger | AST-Struktur-Test via `svelte/compiler::parse(…, {modern:true})`; bewacht heute nur **eine** Datei (`WeatherMetricsTab.svelte`) — diese Lieferung erweitert den Schutz auf die volle Fläche |
| `tests/unit/test_compare_metric_catalog_consistency.py:19-21` | Warnender Präzedenzfall | Dokumentiert, dass TS-Parsing *aus Python heraus* am 2026-07-24 die gesamte pytest-Collection zerstört hat — Begründung für „zwei Wächter, nicht einer" |
| `tests/helpers/metrik_listen_scan.py` | Bewusst NICHT wiederverwendet | Soll-Menge ist modul-global auf `app.metric_catalog._METRICS` verdrahtet (keine Parametrisierung ohne Monkeypatch); erkennt nur `ast.Constant`-Strings, ist blind für `ast.Attribute` (`ThunderLevel.MED`) — genau die Form von #1474-Verstoß Nr. 1 |
| `docs/reference/gates_und_ratschen.md:179-196` | Ziel-Dokument | Regel-Budget-Tabelle „Prüfdaten im Überblick" (heute 11 Einträge) — bekommt eine zwölfte Zeile |
| Commit `860a3baf` (#1474) | VORHER-Korpus | `860a3baf^` liefert die acht Python- und die neun Gesamt-Verstöße, gegen die Regel A/B/C gemessen wurden |
| `docs/specs/modules/thunder_threshold_katalog.md` | Vorgänger-Spec | #1911 — definiert die Ableitung, die `compare_metric_catalog.py` seither keine Kopie mehr macht |

## Implementation Details

### Scanflächen (getrennt pro Wächter, getrennt pro Regel)

| Wächter | Regeln | Scanfläche |
|---|---|---|
| Backend (`tests/tdd/test_thunder_scale_local_copy_guard.py`) | A, B, C, `match/case` | `src/**/*.py` + `api/**/*.py` (204 Dateien) |
| Backend | D | `tests/**/*.py` |
| Frontend (`.../thunderScaleLocalCopyGuard.test.ts`) | A (Schwelle 3), P, C | `frontend/src/**/*.{ts,svelte}` |
| Frontend | D | `frontend/**/*.test.ts` |

Kein Wächter liest den jeweils anderen Sprachraum — der Backend-Wächter importiert und ruft
keinerlei TS-/Svelte-Parser auf, der Frontend-Wächter parst kein Python. Das ist keine
Nebensächlichkeit, sondern die Begründung für „zwei Wächter, nicht einer": TS-Parsing aus einem
Python-Testmodul heraus hat am 2026-07-24 die gesamte pytest-Collection zerstört
(`tests/unit/test_compare_metric_catalog_consistency.py:19-21`).

### Erkennungsregeln — Backend (Python-AST)

- **Regel A (Literal-Katalog):** Dict/Liste/Tupel/Set mit Stufen als Schlüssel oder Element,
  sowohl als String-Konstante (`ast.Constant`) als auch als Enum-Attributkette (`ast.Attribute`,
  z. B. `ThunderLevel.MED`). Vier Verfeinerungen sind Teil der Regel, nicht optional:
  1. Ein Dict gilt als „liest die Quelle" — kein Fund —, sobald **auch nur ein** Wert an eine
     externe Quelle delegiert (z. B. `THUNDER_LABEL_DE["LOW"]`).
  2. Dict-Schlüssel brauchen mindestens ein `MED`- oder `NONE`-Token; `LOW`/`HIGH` allein gehört
     auch zu `RiskLevel`/`alert_urgency` und darf keinen Fund auslösen.
  3. Liste/Tupel/Set brauchen ≥3 distinkte Stufen-Token (keine 2er-Ausnahme wie bei Dicts).
  4. Ein Tupel rechts von `x in (…)` zählt nicht für Regel A — das ist Regel Bs Aufgabe.
- **Regel B (Verzweigungsketten):** if/elif auf dieselbe Variable gegen ≥2 Stufen, wenn
  mindestens ein Zweigkörper ein **eigenes rohes** String-/Zahl-Literal erzeugt. Erfasst auch
  Ketten aus **separaten** `if`-Statements (nicht nur `elif`) und sucht **durch `and`/`or`-Ver­-
  knüpfungen (BoolOp) hindurch**. Enthält der Zweigkörper nur fremde Enum-Konstruktoren
  (`Risk(level=RiskLevel.HIGH)`), ist es keine Kopie.
- **Regel C (Zahlen-Schwellen):** if-Kette mit numerischen Vergleichen, deren Zweige Gewitter-
  Beschriftungen liefern. Nur im Namens-Scope (`thunder`/`gewitter` im Funktions-/Variablennamen);
  verschachtelte `def`s erben den Scope **nicht** vom umgebenden.
- **`match/case`:** wird strukturell wie Regel B behandelt (ein `ast.Match`-Handler).

### Erkennungsregeln — Frontend (TS-/Svelte-AST via `ts.createSourceFile` bzw. `svelte/compiler`)

- **Regel A, Schwelle 3** (nicht 2 wie im Backend) — Schwelle 2 erzeugt drei Fehlalarme auf
  `alertChannelState.ts` (`['LOW','MODERATE','HIGH']`, einer fremden Skala).
- **Regel P (Positions-Abgleich):** Ein geordnetes Array mit Stufennamen wird gegen die
  kanonische Ordnung verglichen; der Index von `MED` muss 2 sein, nicht 1. Greift **nur**, wenn
  die Folge beansprucht, bei `NONE`/„kein" zu beginnen — sonst meldet sie
  `thunderThresholdLevels.test.ts` fälschlich, das bewusst mit `slice(1)` bei „leicht" startet.
  Das ist die einzige Regel, die den neunten #1474-Fund gefangen hätte: alle vier Stufen waren
  anwesend, die Anzahl stimmte, nur die Reihenfolge war falsch.
- **Kanonische Ordnung wird live gelesen**, nie abgeschrieben: `execFileSync('uv', ['run',
  'python3', '-c', …])` gegen `src/app/thunder_scale.py`, Ergebnis `['NONE','LOW','MED','HIGH']`
  als JSON über stdout. Eine hartkodierte Erwartungsliste im Wächter selbst ist unzulässig
  (Präzedenz #1424 F001, #1351 F003). CI-seitig bereits abgesichert (`frontend-test`-Job
  installiert `uv` + `uv sync`, `ci.yml:94-102`).
- **Regel C** auch im Frontend, strukturell analog zum Backend (if/else-Ketten und `switch`).

### Regel D — Paritäts-Behauptung (beide Wächter, läuft auf Testdateien)

Läuft **zusätzlich und separat** auf Testdateien, im Gegensatz zu A/P/C, die auf Testdateien
16 Dauerfeuer-Treffer erzeugen würden (jede korrekte Fixture führt zwangsläufig alle vier Wörter).
Eine Fixture darf vereinfachen. Behauptet ihr Kommentar aber Übereinstimmung mit der echten
Quelle (Wortlaute wie „1:1 aus …", „wortwörtlicher Ausschnitt", „eingefroren aus dem heutigen
Stand", „identische Reihenfolge"), wird sie gegen die kanonische Ordnung geprüft; eine Fixture
ohne solche Behauptung wird ignoriert. Die Kommentar-Extraktion normalisiert Zeilenumbrüche und
Kommentarmarker, sonst zerreißt ein mehrzeiliger Wortlaut. Im Backend ist Regel D eine
**Fähigkeit des geteilten Kerns** (kein eigenes Regel-Budget) — Begründung: „fängt heute nichts"
ist bei einem präventiven Wächter der Normalzustand, kein Ausschlusskriterium; dasselbe Argument
würde sonst auch Regel A/P im Frontend erledigen, wo der Bestand ebenfalls sauber ist.

### Selbstbezug: Fixture-Quelltexte liegen außerhalb der Scanfläche

Beide Wächter laden ihre Verstoß-Vorlagen aus ausgelagerten Dateien mit **nicht**-scanbarer
Endung (`tests/fixtures/thunder_scale_guard_cases/faelle.py.txt` bzw.
`frontend/.../__tests__/fixtures/thunder_scale_guard_cases.ts.txt`), analog zum Vorbild-Ratchet.
Damit setzt kein Wächtermodul selbst ein Stufen-Literal zusammen und muss keine Rücksicht auf die
eigene Regel nehmen. Dass die Ablage wirklich außerhalb der Reichweite liegt, wird empirisch
geprüft (AC-19), nicht angenommen.

### Duldung und Verstoßmeldung

Ausnahmen werden **an der Fundstelle** per Marker-Kommentar `# gz-thunder-scale: <Begründung>`
(Backend) bzw. `// gz-thunder-scale: <Begründung>` (Frontend) eingetragen — nie über eine
zentrale Liste, nie über Zeilennummern (#1466). Ein Marker ohne Begründungstext oder mit einer
Alibi-Begründung unter 15 sinnvollen Zeichen zählt nicht. Der heutige Bestand braucht **genau
einen** Marker: `src/output/renderers/narrow.py::_SEV_TO_THUNDER_LEVEL` — ein Tupel aller vier
Stufen, das die Ordnung positional statt über `_THUNDER_ORDER` nachbaut und strukturell nicht von
einer echten Kopie unterscheidbar ist. Bei jedem neuen, unbegründeten Fund schlägt der jeweilige
Wächter fehl und meldet `Code reference: <Datei>:<Zeile>`.

### Prüfdatum

Beide Wächter tragen dieselbe Konstante `EXPIRY = "2026-11-01"` (Backend: Modul-Konstante;
Frontend: exportierte Konstante), maschinell auffindbar per `grep`. Zusätzlich eine neue Zeile in
der Tabelle „Regel-Budget: Prüfdaten im Überblick" (`docs/reference/gates_und_ratschen.md:179`).

## Expected Behavior

- **Input:** der aktuelle Stand von `src/`, `api/`, `frontend/src/` und `tests/`/`*.test.ts` beim
  Testlauf.
- **Output:** Beide Wächter grün, solange keine neue, unbegründete lokale Kopie der Gewitter-
  Stufenskala entsteht. Rot mit `Code reference: <Datei>:<Zeile>` bei jedem neuen Fund.
- **Side effects:** keine im Wächtercode selbst. Der Frontend-Wächter startet für die Live-
  Ordnungsprüfung einen `uv run python3 -c …`-Subprozess (reiner Lesezugriff).

## Acceptance Criteria

**Backend — Regel A**

- **AC-1:** Given ein neu angelegtes Dict/eine neue Liste/ein neues Tupel/Set in `src/` oder
  `api/`, dessen Schlüssel oder Elemente Gewitter-Stufen sowohl als String-Konstante als auch als
  Enum-Attributkette (`ThunderLevel.MED`) führen / When der Backend-Wächter läuft / Then meldet er
  diese Stelle als Fund mit Datei- und Zeilenangabe
  - Test: Je eine Fixture pro Literalform (String-Dict, Enum-Attribut-Dict, Liste, Tupel, Set)
    erzeugt genau einen Fund.

- **AC-2:** Given ein Dict, in dem mindestens ein Wert an eine externe Quelle delegiert
  (`THUNDER_LABEL_DE["LOW"]`) / When der Backend-Wächter läuft / Then wird das gesamte Dict als
  „liest die Quelle" gewertet und löst keinen Fund aus
  - Test: Fixture nach dem Muster von `email/helpers.py::_THUNDER_MAP` bleibt grün.

- **AC-3:** Given ein Dict, dessen Schlüssel nur `LOW`/`HIGH` führen, aber weder `MED` noch `NONE`
  / When der Backend-Wächter läuft / Then entsteht kein Fund, weil das auch zu `RiskLevel`/
  `alert_urgency` gehören kann
  - Test: Fixture nach dem Muster von `alert_urgency.py` (LOW/MODERATE/HIGH) bleibt grün.

- **AC-4:** Given eine Liste/ein Tupel mit nur zwei distinkten Gewitter-Stufen-Token / When der
  Backend-Wächter läuft / Then entsteht kein Fund, weil Liste/Tupel/Set erst ab drei distinkten
  Token als Kopie gilt
  - Test: Fixture nach dem Muster von `alert_preset.py` (2er-Tupel als Bereichsgrenze) bleibt
    grün.

- **AC-5:** Given ein Tupel, das ausschließlich als rechter Operand von `x in (…)` verwendet wird
  / When der Backend-Wächter läuft / Then löst dieses Tupel für sich genommen keinen Regel-A-Fund
  aus
  - Test: Fixture nach dem Muster von `outlook.py:229` (reine Nicht-NONE-Wächterbedingung) bleibt
    grün.

**Backend — Regel B, C, match/case**

- **AC-6:** Given eine if/elif-Kette auf dieselbe Variable gegen mindestens zwei Gewitter-Stufen,
  bei der mindestens ein Zweigkörper ein eigenes rohes String- oder Zahl-Literal erzeugt / When
  der Backend-Wächter läuft / Then meldet er diese Kette als Fund, auch wenn sie aus separaten
  `if`-Statements statt `elif` besteht oder die Bedingung über `and`/`or` verknüpft ist
  - Test: Je eine Fixture (elif-Kette, separate if-Statements, BoolOp-verknüpfte Bedingung) nach
    dem Muster von `email/html.py:187-196` erzeugt genau einen Fund.

- **AC-7:** Given eine if/elif-Kette, deren Zweigkörper ausschließlich fremde Enum-Konstruktoren
  erzeugen (`Risk(level=RiskLevel.HIGH)`) / When der Backend-Wächter läuft / Then entsteht kein
  Fund, weil hier keine rohe Beschriftung, sondern ein fremder Werttyp erzeugt wird
  - Test: Fixture nach dem Muster von `risk_engine.py:126-140` bleibt grün.

- **AC-8:** Given eine if-Kette mit numerischen Schwellenvergleichen, deren Zweige Gewitter-
  Beschriftungen liefern, innerhalb einer Funktion oder Variable mit `thunder`/`gewitter` im Namen
  / When der Backend-Wächter läuft / Then meldet er diese Kette als Fund; eine strukturell
  identische Kette außerhalb dieses Namens-Scope (z. B. Windstärke-Formatierung) bleibt unbemeldet
  - Test: Fixture nach dem Muster von `email/html.py:198-203` (`num > 20 → "risk"`) erzeugt einen
    Fund; eine Kontroll-Fixture nach dem Muster von `weather_metrics.format_wind_strength()`
    bleibt grün.

- **AC-9:** Given eine verschachtelte innere Funktion ohne `thunder`/`gewitter` im eigenen Namen,
  deren umgebende Funktion diesen Namensteil trägt / When der Backend-Wächter läuft / Then erbt
  die innere Funktion den Namens-Scope **nicht**, eine dortige unabhängige Zahlen-Schwellenkette
  bleibt unbemeldet
  - Test: Fixture mit verschachtelter `def` ohne eigenen Gewitter-Namensbezug bleibt grün.

- **AC-10:** Given ein `match/case`-Konstrukt, das strukturell einer Regel-B-Verzweigung
  entspricht (Match auf eine Stufen-Variable, mindestens ein `case`-Zweig mit eigenem rohen
  Literal) / When der Backend-Wächter läuft / Then wird es wie eine if/elif-Kette gemeldet
  - Test: Fixture mit `match/case` auf Gewitter-Stufen erzeugt genau einen Fund.
  - Test (Gegenprobe): ein `match/case`, dessen `case`-Zweige ausschließlich fremde
    Enum-Konstruktoren enthalten (kein eigenes rohes Literal), bleibt grün — dieselbe Abgrenzung,
    die AC-7 für if/elif verlangt. Sie wird hier eigens geprüft und nicht als „ergibt sich aus dem
    geteilten Prüfpfad" unterstellt: ob `match/case` tatsächlich denselben Pfad durchläuft, ist
    eine Implementierungsentscheidung, die genau dieser Test absichert.

**Backend — Treffsicherheit und Fehlalarm-Obergrenze**

- **AC-11:** Given die acht Python-Verstöße, die real in Commit `860a3baf^` vor der #1474-Reparatur
  standen (u. a. `_NUM={NONE:0,MED:1,HIGH:2}`, `_ORD`+if/elif, `[TL.NONE,TL.MED,TL.HIGH]`,
  `str(v) in ("MED","ThunderLevel.MED")`, `_THUNDER_LABEL`, `_MAP_EMOJI`/`_MAP_PLAIN`,
  `level_rank={...}`) als Fixture-Vorlagen / When der Backend-Wächter über diese Vorlagen läuft /
  Then meldet er alle acht als Fund
  - Test: Acht Fixtures (Quelltext-Vorlagen, keine lauffähigen Module) aus
    `faelle.py.txt` erzeugen zusammen acht Funde, einen je Verstoß.

- **AC-12:** Given der unveränderte Bestand von `src/**/*.py` + `api/**/*.py` (204 Dateien) / When
  der Backend-Wächter über den echten Repo-Baum läuft / Then entsteht genau **ein** unbegründeter
  Fund weniger als ohne den Marker an `narrow.py::_SEV_TO_THUNDER_LEVEL` — mit gesetztem Marker
  bleibt der Lauf grün, entfernt man den Marker probeweise, wird genau diese eine Stelle rot
  - Test: Wächterlauf gegen den echten Baum ist grün; ein temporär entfernter Marker (in einer
    Kopie, nicht im Repo) macht denselben Lauf an genau dieser Stelle rot.

**Frontend — Regel A, P, C**

- **AC-13:** Given ein neues TS-/Svelte-Array mit mindestens drei distinkten Gewitter-Stufen-
  Wörtern (NONE/LOW/MED/HIGH bzw. kein/leicht/mittel/hoch) / When der Frontend-Wächter läuft /
  Then meldet er diese Stelle als Fund; ein Array mit nur zwei der vier Wörter (Schwelle darunter)
  löst keinen Fund aus
  - Test: Fixture mit drei Stufen-Wörtern erzeugt einen Fund; eine Kontroll-Fixture nach dem
    Muster von `alertChannelState.ts` (`['LOW','MODERATE','HIGH']`) bleibt grün.

- **AC-14:** Given ein geordnetes Array, das beansprucht, bei `NONE`/„kein" zu beginnen, in dem
  aber der Index von `MED`/„mittel" nicht 2 ist / When der Frontend-Wächter läuft / Then meldet er
  diese Stelle als Fund — auch dann, wenn alle vier Stufen vorhanden sind und die Länge stimmt
  - Test: Fixture `['NONE','MED','HIGH','LOW']` (die reale neunte #1474-Stelle) erzeugt einen
    Fund.
  - Test (Gegenprobe): Fixture `['NONE','LOW','MED','HIGH']` — dieselbe Länge, dieselben vier
    Stufen, aber korrekte Reihenfolge — bleibt grün. Ohne diesen Fall wäre ein Wächter, der
    **jedes** bei `NONE` beginnende Array meldet, von einem korrekten nicht zu unterscheiden.

- **AC-15:** Given ein Array, das ausdrücklich nicht bei `NONE`/„kein" beginnt (z. B. per
  `slice(1)` bei „leicht" startend) / When der Frontend-Wächter läuft / Then löst diese Stelle
  keinen Regel-P-Fund aus
  - Test: Fixture nach dem Muster von `thunderThresholdLevels.test.ts` bleibt grün.

- **AC-16:** Given der Frontend-Wächter, dessen Bezugsquelle für die Stufenordnung im Test durch
  eine **abweichende** Ordnung ersetzt wird / When er mit dieser abweichenden Ordnung läuft / Then
  richtet er sein Urteil nach ihr — eine Folge, die der untergeschobenen Ordnung entspricht, bleibt
  grün, und eine, die der echten entspricht, wird rot
  - Test: Bezugsquelle liefert per Injektion `['NONE','MED','LOW','HIGH']` (MED und LOW vertauscht).
    Dann bleibt die Fixture `['NONE','MED','LOW','HIGH']` grün und `['NONE','LOW','MED','HIGH']`
    wird rot. Bei einer hartkodierten Liste im Wächter wäre das Ergebnis genau umgekehrt — der Test
    unterscheidet die beiden Bauweisen also zuverlässig, statt nur den Quelltext anzusehen.
  - Implementation Detail: Die Ordnung muss über einen Parameter mit Vorbelegung injizierbar sein,
    nicht als modul-globale Konstante feststehen. Im Normalbetrieb füllt
    `execFileSync('uv', ['run','python3','-c', …])` gegen `src/app/thunder_scale.py` diese
    Vorbelegung; eine hartkodierte Erwartungsliste der Stufenreihenfolge gibt es nicht
    (Präzedenz gegen abgeschriebene Listen: #1424 F001, #1351 F003).

- **AC-17:** Given eine if/else-Kette oder ein `switch` in TS/Svelte, deren Zweige Gewitter-
  Beschriftungen aus Zahlen-Schwellenvergleichen liefern / When der Frontend-Wächter läuft / Then
  meldet er diese Stelle als Fund
  - Test: Fixture nach dem rekonstruierten Muster von `alertMetricLabels.ts::thunderLevelLabel()`
    (aus `46ff82c2`) erzeugt einen Fund.
  - Test (Gegenprobe): eine strukturell identische Zahlen-Schwellenkette **außerhalb** des
    `thunder`/`gewitter`-Namensraums — etwa eine Windstärke-Formatierung, die ebenfalls „leicht"
    und „mittel" zurückgibt — bleibt grün. Ohne sie bliebe die Namens-Scope-Filterung des
    Frontend-Wächters ungeprüft, und eine Implementierung, die jede Zahlen-Schwellenkette meldet,
    bestünde AC-17 trivial. (Analog zur bereits verlangten Gegenprobe in AC-8 im Backend.)

**Beide — Regel D, Wirkungsnachweis, Duldung, Selbstbezug, Prüfdatum**

- **AC-18:** Given eine Test-Fixture, deren Kommentar Übereinstimmung mit der echten Quelle
  behauptet („1:1 aus …", „wortwörtlicher Ausschnitt", „eingefroren aus dem heutigen Stand",
  „identische Reihenfolge" — auch über mehrere Kommentarzeilen verteilt) und deren tatsächlicher
  Inhalt von der kanonischen Ordnung abweicht / When der jeweilige Wächter über Testdateien läuft
  / Then meldet er diese Fixture als Fund; eine strukturell identische, aber unbehauptete Fixture
  bleibt unbemeldet
  - Test: Je eine Fixture mit Paritätsbehauptung + Abweichung (Fund) und ohne Behauptung +
    gleicher Abweichung (kein Fund), inklusive einer Variante mit mehrzeiligem Kommentar.

- **AC-19:** Given die ausgelagerten Fixture-Quelltexte beider Wächter, die absichtlich echte
  Verstöße enthalten / When der jeweilige Wächter über die eigene Scanfläche läuft / Then
  erscheinen die Fixture-Dateien selbst nicht als Fund, weil ihre Ablage (`.py.txt` bzw. `.ts.txt`)
  nachweislich außerhalb der Scanfläche liegt
  - Test: Ein eigener Selbstbezug-Test scannt das Fixture-Verzeichnis mit derselben Scanlogik und
    erhält null Funde, obwohl die Datei den vollen Stufen-Wortschatz enthält.

- **AC-20:** Given beide Wächter, an konstruierten Verstößen ausgeführt / When man ihre eigene
  Trefferzahl abfragt / Then behaupten sie diese Zahl selbst als größer null — eine leere
  Trefferliste würde jede „keiner ist schlecht"-Aussage trivial wahr machen
  - Test: Je ein Selbsttest pro Wächter prüft `len(funde) > 0` gegen eine Fixture mit bekanntem
    Verstoß.

- **AC-21:** Given eine begründete Ausnahme in Form eines Marker-Kommentars
  (`# gz-thunder-scale: <Begründung>` bzw. `// gz-thunder-scale: <Begründung>`) mit mindestens
  15 sinnvollen Zeichen direkt an der Fundstelle / When der jeweilige Wächter läuft / Then wird
  dieser Fund durchgelassen; derselbe Marker ohne Begründungstext oder mit einer Alibi-Begründung
  unter 15 Zeichen bleibt rot
  - Test: Je zwei Fixtures (mit ausreichender, mit unzureichender Begründung) pro Wächter zeigen
    das jeweils erwartete Ergebnis.

- **AC-22:** Given die Prüfdatum-Konstante `EXPIRY = "2026-11-01"` in beiden Wächterdateien / When
  der Bestand durchsucht wird / Then lässt sich das Prüfdatum maschinell per `grep` in beiden
  Dateien auffinden, und die Tabelle „Regel-Budget: Prüfdaten im Überblick" in
  `docs/reference/gates_und_ratschen.md` enthält eine Zeile für diesen Wächter mit demselben Datum
  - Test: `grep -n "2026-11-01"` findet einen Treffer in jeder Wächterdatei sowie in
    `docs/reference/gates_und_ratschen.md`.

- **AC-23:** Given der Backend-Wächter als eigenständiges Python-Modul / When man seinen
  Quelltext auf Importe und Subprozess-Aufrufe prüft / Then enthält er keinerlei Aufruf eines
  TS-/Svelte-Parsers oder einer Node-Laufzeit — die Trennung der beiden Wächter ist strukturell
  erzwungen, nicht nur eine Absichtserklärung, und die volle pytest-Collection bleibt beim
  Hinzufügen des Backend-Wächters unversehrt
  - Test: `uv run pytest --collect-only` über den vollen `tests/`-Baum läuft ohne Collection-
    Fehler; ein Quelltext-Scan des Backend-Wächters findet keine `node`/`tsc`/`svelte`-Referenz.

**Wiederverwendbarkeit des Erkennungs-Kerns**

- **AC-24:** Given der Erkennungs-Kern des Backend-Wächters / When man ihn mit einer **anderen**
  Stufenmenge und anderen Scan-Wurzeln aufruft — etwa `RiskLevel` mit `low`/`moderate`/`high` —
  / Then meldet er die Fundstellen dieser anderen Skala, **ohne dass eine Zeile des Kerns geändert
  werden muss**
  - Test: Kern mit `RiskLevel`-Parametern (kanonisches Modul, Symbolname, Mitgliedsnamen,
    Scan-Wurzel) gegen eine konstruierte Fixture aufrufen; erwarteter Fund tritt ein. Ein Aufruf
    mit den Gewitter-Parametern gegen dieselbe Fixture bleibt still — der Kern richtet sich also
    nach den übergebenen Parametern, nicht nach einer eingebauten Annahme.
  - Abgrenzung: Es wird **kein** `RiskLevel`-Wächter angelegt und keiner in die CI aufgenommen —
    nachgewiesen wird ausschließlich die Aufrufbarkeit. Ein späterer `RiskLevel`-Wächter soll
    dadurch ~20–30 LoC kosten statt eines Neubaus.
  - Begründung: Genau diese Fähigkeit fehlt dem bestehenden `tests/helpers/metrik_listen_scan.py`,
    dessen Soll-Menge `KENNUNGEN` modul-global auf den Metrik-Katalog verdrahtet ist — der Grund,
    warum er hier nicht wiederverwendet wird (s. Abschnitt Nichtteilung). Ohne AC-24 wiederholte
    dieser Wächter denselben Fehler für den nächsten.

## Test Plan

Backend-Läufe erfolgen über
`uv run pytest tests/tdd/test_thunder_scale_local_copy_guard.py -v` im Sitzungs-Worktree.
Frontend-Läufe erfolgen über
`npm --prefix frontend test -- thunderScaleLocalCopyGuard` (bzw. das Äquivalent im
`frontend-test`-CI-Job).

- **AC-1 bis AC-5 (Regel A + Verfeinerungen):** Scan-Funktion des Backend-Wächters direkt auf
  In-Memory-AST-Fixtures anwenden (Unit-Test der Erkennungslogik, kein voller Repo-Scan nötig);
  je Fixture einen erwarteten Fund-/Kein-Fund-Status prüfen.
- **AC-6 bis AC-10 (Regel B/C/match-case):** dieselbe Vorgehensweise, Fixtures nach den in den
  ACs genannten realen Vorbildern.
- **AC-11 (Treffsicherheit):** die acht Fixture-Vorlagen aus `faelle.py.txt` einzeln durch die
  Scan-Funktion laufen lassen; Summe der Funde muss 8 sein.
- **AC-12 (Fehlalarm-Obergrenze):** vollen Backend-Scan gegen den echten Repo-Baum ausführen;
  erwarteter Output: Exit 0, keine Erwähnung einer unbegründeten Stelle außer
  `narrow.py::_SEV_TO_THUNDER_LEVEL` (die durch den Marker bereits grün ist). Gegenprobe mit
  temporär entferntem Marker **nur an einer Kopie im Scratchpad**, nie am Repo-Stand.
- **AC-13 bis AC-15, AC-17 (Frontend-Regeln):** Scan-Funktion des Frontend-Wächters auf
  In-Memory-AST-Fixtures anwenden; je Fixture erwarteten Fund-/Kein-Fund-Status prüfen.
- **AC-16 (Live-Bezug der Ordnung):** die Ordnungsquelle per Injektion durch
  `['NONE','MED','LOW','HIGH']` ersetzen und **zwei** Fixtures prüfen — die der untergeschobenen
  Ordnung folgende bleibt grün, die der echten folgende wird rot. Beide Erwartungen sind nötig:
  eine allein wäre auch bei hartkodierter Liste erfüllbar. **Kein** Quelltext-Grep als Nachweis
  (Dateiinhalt-Check ist als Verhaltensnachweis unzulässig).
- **AC-18 (Regel D):** Kommentar-Extraktion des jeweiligen Wächters auf Fixtures mit/ohne
  Paritätsbehauptung anwenden, inklusive einer mehrzeiligen Kommentarvariante.
- **AC-19 (Selbstbezug):** vollen Scan gegen `tests/fixtures/thunder_scale_guard_cases/` bzw.
  `frontend/.../__tests__/fixtures/` ausführen; erwarteter Output: 0 Funde trotz vollem
  Stufen-Wortschatz in den Dateien.
- **AC-20 (Wirkungsnachweis):** `len(funde) > 0` gegen eine Fixture mit bekanntem Verstoß prüfen.
- **AC-21 (Marker-Duldung):** zwei Fixtures (ausreichende/unzureichende Begründung) je Wächter
  durch die Scan-Funktion laufen lassen.
- **AC-22 (Prüfdatum):** `grep -n "2026-11-01" tests/tdd/test_thunder_scale_local_copy_guard.py
  frontend/src/lib/components/shared/weather-metrics-tab/__tests__/thunderScaleLocalCopyGuard.test.ts
  docs/reference/gates_und_ratschen.md` ausführen; erwarteter Output: mindestens ein Treffer je
  Datei. **Ausdrückliche Ausnahme von der Dateiinhalt-Check-Regel:** Geprüft wird hier reine
  Metadaten-Präsenz (Prüfdatum, Ratschen-Tabellenzeile), kein Laufzeitverhalten — ein
  Verhaltensnachweis ist dafür weder möglich noch sinnvoll. Die Testfunktion trägt deshalb den
  Marker `# doc-compliance-test`.
- **AC-23 (Wächtertrennung):** `uv run pytest --collect-only` über `tests/` ausführen (erwarteter
  Output: Exit 0, keine Collection-Fehler); ergänzend Quelltext-Grep des Backend-Wächters auf
  `node|tsc|svelte` (erwarteter Output: kein Treffer). Der Collection-Lauf ist der eigentliche
  Nachweis, der Grep nur eine Zusatzabsicherung.
- **AC-24 (parametrisierter Kern):** den Erkennungs-Kern zweimal gegen **dieselbe** konstruierte
  Fixture aufrufen — einmal mit `RiskLevel`-Parametern (Fund erwartet), einmal mit
  Gewitter-Parametern (kein Fund erwartet). Beide Erwartungen sind nötig: der Fund allein wiese
  nicht nach, dass der Kern sich wirklich nach den Parametern richtet und nicht ohnehin alles
  meldet.

## Known Limitations

Übernommen aus `docs/context/feat-1480-thunder-scale-guard.md`, Abschnitt „Was strukturell
unfangbar bleibt" — bewusst nicht Teil dieser Lieferung:

1. **Enum-Iteration / `dict(genexpr)`, `.append()`-Aufbau, `+`-Konkatenation,
   `getattr(ThunderLevel, "MED")`, Zahlen-Schlüssel ohne Wortbezug, Skala in JSON/YAML,
   vollständige String-Konkatenation** werden nicht erkannt. Alle bräuchten Datenflussanalyse
   oder liegen außerhalb jeder AST-Reichweite. Es sind absichtliche Umgehungen oder exotische
   Formen, für die es im Repo keinen Anhaltspunkt gibt — der reale #1474-Fehler war versehentlich
   und wird gefangen. `match/case` ist die einzige Ausnahme aus dieser Liste: es wird verfolgt,
   weil es strukturell nah an Regel B liegt.
2. **Die Duldungsliste (Marker-Kommentare) verifiziert die geduldeten Kopien nicht auf
   Korrektheit.** Driftet `narrow.py::_SEV_TO_THUNDER_LEVEL` erneut (z. B. bei einer fünften
   Stufe), bleibt der Wächter still, solange der Symbolname überlebt.
3. **Regel D hat im Python-Teil bei Einführung null Fänge** — 25 Stufen-Literale in `tests/`
   geprüft, keines trägt eine Paritäts-Behauptung; historisch (`860a3baf^`) ebenfalls null. Sie
   wird trotzdem gebaut, als Fähigkeit des geteilten Kerns ohne eigenes Regel-Budget: „fängt
   heute nichts" ist bei einem präventiven Wächter der Normalzustand, kein Ausschlusskriterium
   (dasselbe Argument würde sonst auch Regel A/P im sauberen Frontend-Bestand erledigen). Am
   Prüfdatum 2026-11-01 wird sie mitbewertet.
4. **Kein `RiskLevel`-Wächter.** Der Kern ist parametrisiert (kanonisches Modul/Symbol,
   Mitgliedsnamen, Scan-Wurzeln als Argumente), wird aber vorerst nur auf `ThunderLevel`
   angewandt — ein späterer `RiskLevel`-Wächter kostet dadurch ~20–30 LoC statt Neubau.
5. **Die 10 bestehenden Kopien im Produktivcode werden nicht saniert.** Das ist ausdrücklich
   nicht Teil dieses Workflows (#2010, #2011 decken zwei davon in eigenen PRs ab). Der Wächter
   startet als Ratsche mit benannter, nur schrumpfender Duldungsliste (heute: ein Eintrag).
6. **Regel A/P laufen nicht auf Testdateien** — eine korrekte Fixture führt zwangsläufig alle
   vier Stufen-Wörter und würde 16 Dauerfeuer-Treffer erzeugen. Nur Regel D läuft dort.
7. **Ein falsch schlagender Wächter blockiert jeden PR jeder Session** — beide CI-Jobs (`test`,
   `frontend-test`) hängen an dieser Regel. Die Fehlalarmzahl über die volle Scanfläche ist
   deshalb gezählt (nicht geschätzt) in AC-12/AC-13 verankert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Absicherung ohne Auswirkung auf Produktarchitektur,
  Datenmodell, Kanäle oder Provider — keine Entscheidungsfläche im Sinne der ADR-Kriterien. Die
  einzige Produktivcode-Berührung ist ein Marker-Kommentar ohne Verhaltensänderung.

## Changelog

- 2026-08-20: Initial spec erstellt — Issue #1480, auf Basis der am selben Tag neu vermessenen
  Kontextanalyse (`docs/context/feat-1480-thunder-scale-guard.md`, Stand `bc6897a7`).
- 2026-08-20: Nachbesserung nach Review (Team-Lead) — AC-16 von einem Dateiinhalt-Check auf einen
  echten Verhaltensnachweis per Injektion einer abweichenden Stufenordnung umgestellt; AC-24
  (parametrisierter Kern gegen `RiskLevel`-Parameter nachgewiesen) ergänzt; Gegenproben für
  AC-10/AC-14/AC-17 sowie eine begründete `# doc-compliance-test`-Ausnahme für den
  Prüfdatum-Nachweis (AC-22) ergänzt. 23 → 24 ACs.
