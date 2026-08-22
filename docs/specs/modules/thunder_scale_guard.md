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

Geduldet wird **dreistufig**. Die Stufen sagen bewusst Verschiedenes aus — wer alles über einen
Marker regelt, behauptet an neun Stellen „diese Kopie ist gerechtfertigt", obwohl mehrere davon
nutzersichtbare Defekte sind (#2010, #2011).

1. **Whitelist kanonischer Quellen** (`ScaleSpec.canonical_symbols` bzw. `CANONICAL_SYMBOLS` im
   Frontend) — **symbolscharf**, als `(Datei, Symbol)`-Paare, nie dateiweit. Eine dateiweite
   Whitelist ließe die kanonischen Dateien vollständig unbewacht; die nächste Kopie entsteht
   erfahrungsgemäß **neben** der Quelle (die neunte #1474-Stelle entstand beim Reparieren der
   vierten), und `metric_format.py` führt außerdem Wolken-, Wind- und weitere Metriken. Die
   Kontextanalyse spricht ebenfalls symbolweise („`_THUNDER_AMPEL_BAND` fehlte auf der
   Whitelist"). Eine kanonische Quelle ist kein geduldeter Verstoß, sondern die Wahrheit; ein
   Wächter ohne sie meldet seine eigene Bezugsquelle (Kontextanalyse Z. 56/57). Parametrisiert,
   damit AC-24 trägt — **kein** Marker im Produktivcode.
   Inhalt (gemessen, nur Einträge die ohne Whitelist wirklich anschlagen):
   `thunder_scale.py::_THUNDER_ORDER`, `thunder_scale.py::_THUNDER_LABEL_VALUE`,
   `metric_format.py::THUNDER_LABEL_DE`, `metric_format.py::_THUNDER_AMPEL_BAND`,
   `corridorEditorState.ts::ORDINAL_ENUM`. **Nicht** aufgenommen sind
   `models.py::ThunderLevel` (Enum-Klassenrumpf), `compare_metric_catalog.py::_THUNDER_ORDINAL_LABELS`
   sowie `types.ts::ThunderLevel` und die Ableitungen in `compareMetricCatalogLoader.ts` — sie
   erzeugen heute keinen Fund; ein Eintrag dafür wäre Leerlauf, und schlüge einer künftig doch an,
   wäre das ein echtes Signal (Rückfall hinter #1911). Für beide Whitelists gilt derselbe
   **Nicht-Leerlauf-Test** wie für die Basislinie, dazu ein **Granularitäts-Nachweis**: eine
   konstruierte Kopie in einer kanonischen Datei unter anderem Symbolnamen **muss** gemeldet
   werden.
2. **Benannte Altlasten-Basislinie** (`ALTLASTEN` im Backend-Wächter, ursprünglich 9 Einträge,
   seit #2010/#2011 noch 3): die bekannten Kopien aus #1474. **Symbolgeschlüsselt** über
   `(Datei, Symbol-/Funktionsname, Regel)` —
   **niemals** über Zeilennummern (#1466); jeder Eintrag trägt Grund und Tracking-Issue. Die Liste
   darf nur schrumpfen. Gegen Verrotten schützt ein **Nicht-Leerlauf-Test**: erzeugt ein Eintrag
   heute keinen echten Fund mehr (Symbol saniert, umbenannt, verschoben), wird der Wächter **rot**
   statt still. Die Gegenrichtung ist ebenso geprüft — die Basislinie darf keine Stelle
   stillstellen, die nicht namentlich in ihr steht. Das Frontend braucht **keine** Basislinie: sein
   Bestand ist seit #1488/#1911 frei von aktiven Kopien.
3. **Marker-Kommentar an der Fundstelle**: `# gz-thunder-scale: <Begründung>` (Backend) bzw.
   `// gz-thunder-scale: <Begründung>` (Frontend), mindestens 15 sinnvolle Zeichen Begründung.
   Das ist die echte, begründete Duldung — der heutige Bestand hat **genau eine**:
   `src/output/renderers/narrow.py::_SEV_TO_THUNDER_LEVEL` (Kategorie B: liest die Quelle, führt
   bewusst eine positionale Teilmenge). Sie ist zugleich der einzige Nachweis, dass der
   Marker-Pfad am **echten** Baum wirkt und nicht nur an In-Memory-Fixtures.

Bei jedem neuen, ungedeckten Fund schlägt der jeweilige Wächter fehl und meldet
`Code reference: <Datei>:<Zeile>`.

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
  - Test (Umkehrprobe): eine verschachtelte `def`, die den Namensteil **selbst** trägt, wird
    gemeldet. Ohne diesen Fall wäre der AC auch von einer Implementierung erfüllt, die
    verschachtelte Funktionen pauschal übergeht — geprüft werden soll aber die fehlende
    *Vererbung*, nicht eine generelle Blindheit für innere Funktionen.
  - Die Nicht-Vererbung wird in **beiden** Wächtern geprüft, mit Positivfall und Umkehrprobe je
    Sprachraum: der Frontend-Wächter trägt dieselbe Schutzmaßnahme im Regel-C-Pfad (kein Abstieg
    in verschachtelte `function`/Arrow-Bodies) und braucht dafür einen eigenen Nachweis — ohne ihn
    ließe sich sie dort entfernen, ohne dass ein Test rot wird (Adversary-Mutation F7). Im Frontend
    wird die Nicht-Vererbung für **alle drei** Funktionsformen geprüft, die der Kern kennt
    (Function-Deklaration, Arrow-Function, Function-Expression), je mit Positivfall und
    Umkehrprobe — sonst bliebe eine Verengung der Sperre auf `ts.isFunctionDeclaration`
    unbemerkt (Adversary-Mutation F-FRONTEND-2).

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
  - Test: Acht Fixtures (Quelltext-Vorlagen, keine lauffähigen Module) aus `faelle.py.txt` werden
    **einzeln** geprüft — jede erzeugt **genau einen** Fund an **der erwarteten Fundstelle**.
    Ausdrücklich **nicht** genügt die Summe „acht Funde insgesamt": eine Implementierung, die bei
    manchen Fixtures mehrere Fehlfunde und bei anderen keinen liefert, könnte zufällig auf acht
    summieren und bestünde einen reinen Summentest.

- **AC-12:** Given der unveränderte Bestand von `src/**/*.py` + `api/**/*.py` / When der
  Backend-Wächter über den echten Repo-Baum läuft / Then ist der Lauf grün, weil jeder Fund
  entweder auf der Whitelist kanonischer Quellen steht, in der benannten Altlasten-Basislinie
  geführt wird oder einen Marker-Kommentar trägt — und **jede** dieser Duldungen ist nachweislich
  wirksam: entfernt man einen einzelnen Basislinien-Eintrag bzw. den `narrow.py`-Marker (in einer
  Kopie, nicht im Repo), wird genau diese eine Stelle rot, keine andere
  - Test: Wächterlauf gegen den echten Baum ist grün. Ein Lauf **ohne** die Basislinie liefert
    exakt die neun namentlich geführten Stellen — daraus folgt beides: kein Eintrag läuft leer
    (Nicht-Leerlauf, **Pflicht**), und keine Stelle wird stillgestellt, die nicht in der Liste
    steht. Ein Lauf ohne Whitelist meldet die kanonischen Quellen selbst; ein temporär entfernter
    Marker (in einer Kopie, nicht im Repo) macht `narrow.py::_SEV_TO_THUNDER_LEVEL` rot.

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
  unter 15 sinnvollen Zeichen bleibt rot
  - **„Sinnvolle Zeichen" sind Buchstaben und Ziffern.** Leerraum, Interpunktion und Unterstriche
    zählen nicht mit — identische Regel wie beim Vorbild-Ratchet
    `tests/tdd/test_repo_path_hardcoding_ratchet.py` (`_UNWORT = re.compile(r"[\W_]+")`, dort vor
    demselben `>= 15`-Vergleich angewendet). Im Frontend das Unicode-Pendant
    `/[^\p{L}\p{N}]+/gu`: **deutsche Umlaute zählen als sinnvolle Zeichen**, unsere Begründungen
    sind auf Deutsch.
  - **Zusätzlich zum Vorbild:** die Begründung muss mindestens **5 verschiedene** sinnvolle Zeichen
    tragen. Ohne diese Bedingung überlebt eine reine Zeichen-Wiederholung (`aaaaaaaaaaaaaaa`) die
    Filterung mit voller Länge 15. Schwelle 5 mit großem Abstand nach beiden Seiten (gemessen
    2026-08-20: echte Begründungen 11–20 verschiedene Zeichen, entartete Wiederholungen 1–2).
  - Begründung: Der Marker ist der **Notausgang der Ratsche**. Ließe er sich mit fünfzehn Punkten
    öffnen, könnte jeder unter Zeitdruck den Wächter stillstellen, ohne eine Begründung zu
    formulieren — genau davor schützt die Regel.
  - Test: Pro Wächter je eine Fixture mit (a) 15 Punkten, (b) 15 Bindestrichen, (c) 15 gleichen
    Buchstaben und (d) einer deutschen Begründung mit Umlauten knapp über der Grenze; (a)–(c)
    bleiben rot, (d) wird durchgelassen. Dazu die Grenzprobe von beiden Seiten (14 sinnvolle
    Zeichen → rot, 15 → grün) sowie die bestehenden Fixtures mit ausreichender/unzureichender
    Begründung.

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
  Scan-Funktion laufen lassen; **je Vorlage genau ein Fund an der erwarteten Fundstelle** — nicht
  bloß eine Gesamtsumme von acht, die auch bei ungleich verteilten Fehlfunden zustande käme.
- **AC-12 (Fehlalarm-Obergrenze):** vollen Backend-Scan gegen den echten Repo-Baum ausführen;
  erwarteter Output: Exit 0, keine Erwähnung einer unbegründeten Stelle außer
  `narrow.py::_SEV_TO_THUNDER_LEVEL` (die durch den Marker bereits grün ist). Gegenprobe mit
  temporär entferntem Marker **nur an einer Kopie im Scratchpad**, nie am Repo-Stand.
  Die Positivkontrolle zum Nullbefund prüft die **besuchte Dateimenge**, nicht „mindestens ein
  Fund": die von `scan_tree` gescannten Dateien müssen exakt der zur Laufzeit aus `rglob("*.py")`
  abgeleiteten Soll-Menge entsprechen (Mengen-, kein Zählvergleich — die Fehlermeldung nennt so
  die fehlende Datei; eine feste Zahl wäre bei jeder neuen `.py`-Datei ein Fehlalarm). „Mindestens
  ein Fund" allein bliebe auch dann wahr, wenn der Wächter nur die halbe Baumfläche liefe.
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
- **AC-21 (Marker-Duldung):** acht Fixtures je Wächter durch die Scan-Funktion laufen lassen —
  ausreichende Begründung, Alibi-Begründung (`x`), 15 Punkte, 15 Bindestriche, 15 gleiche
  Buchstaben, deutsche Begründung mit Umlauten sowie die Grenzproben mit 14 und 15 sinnvollen
  Zeichen. Erwarteter Output: Füllzeichen und 14 Zeichen liefern je einen Fund, die übrigen `[]`.
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
  meldet. Das Paar wird **zweimal** gefahren, für zwei verschiedene Regeln: über eine Regel-A-
  Fixture (Stufen-Token aus `member_names`) **und** über eine Regel-C-Fixture (Namens-Scope aus
  `name_scope_tokens`). Nur Regel A zu prüfen genügt nicht — die Scope-Kette bliebe dann
  unberührt und dürfte hartkodiert sein, ohne dass ein Test rot wird (Adversary-Mutation B11).

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
2. **Die Duldung verifiziert die geduldeten Kopien nicht auf Korrektheit.** Driftet
   `narrow.py::_SEV_TO_THUNDER_LEVEL` erneut (z. B. bei einer fünften Stufe), bleibt der Wächter
   still, solange der Symbolname überlebt. Der Nicht-Leerlauf-Test der Basislinie weist nach, dass
   ein Eintrag **noch existiert** — nicht, dass die Kopie richtig ist.
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
   nicht Teil dieses Workflows. Der Wächter startet als Ratsche mit benannter, nur schrumpfender
   Duldungsliste — bei Einführung **neun** Basislinien-Einträge (davon 7 in `src/services/`,
   2 in `email/html.py`) plus der eine Marker-Fall in `narrow.py`. **#2010/#2011 (2026-08-22)**
   haben sechs davon saniert (4× `src/services/trip_command_processor.py`: `_THUNDER_LABEL`,
   `_MAP_EMOJI`, `_MAP_PLAIN`, `_handle_hours_drilldown`; 2× `src/output/renderers/email/html.py`:
   `_thunder_risk_level` Regel B und C) — verbleibend **drei** Einträge (`day_window.py` und
   zwei `trip_report_scheduler.py`-Symbole). Die beiden Go-Kopien liegen außerhalb der
   Python-Scanfläche.
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
- 2026-08-20: AC-12 nach der GREEN-Messung korrigiert — der echte Baum liefert 14 Funde
  (4 kanonisch, 9 Altlasten, 1 Marker-Fall), nicht 1; die ursprüngliche Fassung verwechselte die
  gemessene Fehlalarmzahl (1) mit der Zahl der zu duldenden Stellen. Duldung dreistufig:
  Whitelist / benannte Basislinie / Marker. Abschnitt „Duldung und Verstoßmeldung" entsprechend
  neu gefasst (symbolgeschlüsselte Basislinie mit Nicht-Leerlauf-Test).
- 2026-08-20: Whitelist kanonischer Quellen von datei- auf **symbolscharf** umgestellt
  (`canonical_files` → `canonical_symbols` bzw. `CANONICAL_FILES` → `CANONICAL_SYMBOLS`,
  Team-Lead-Befund): dateiweit waren `thunder_scale.py`, `metric_format.py` & Co. vollständig
  unbewacht, obwohl die nächste Kopie erfahrungsgemäß genau dort entsteht. Dazu je ein
  Nicht-Leerlauf-Test und ein Granularitäts-Nachweis (Kopie in kanonischer Datei unter anderem
  Symbolnamen wird gemeldet) pro Wächter; beide Nachweise sind mit einer Gegenmutation auf
  dateiweites Verhalten geprüft (dort melden beide Wächter `[]` und die Tests werden rot).
- 2026-08-20: Nachbesserung nach Review (Team-Lead) — AC-16 von einem Dateiinhalt-Check auf einen
  echten Verhaltensnachweis per Injektion einer abweichenden Stufenordnung umgestellt; AC-24
  (parametrisierter Kern gegen `RiskLevel`-Parameter nachgewiesen) ergänzt; Gegenproben für
  AC-10/AC-14/AC-17 sowie eine begründete `# doc-compliance-test`-Ausnahme für den
  Prüfdatum-Nachweis (AC-22) ergänzt. 23 → 24 ACs.
- 2026-08-20: Nach der Adversary-Runde (Verdict BROKEN, 21 Mutationen) drei **Nachweise**
  geschärft — die ACs selbst bleiben inhaltlich gleich, sie waren nur unzureichend belegt:
  1. **AC-24** wird jetzt für **zwei** Regeln geführt statt nur für Regel A. Neu ist ein
     Regel-C-Paar über die Fixture `f24-risklevel-zahlen-schwelle`: mit
     `name_scope_tokens=("risk","risiko")` Fund, mit Gewitter-Parametern gegen denselben Quelltext
     still. Vorher blieb eine in `_im_namens_scope` hartkodierte Annahme unentdeckt (Mutation B11
     ließ alle 49 Tests grün), obwohl der AC-Wortlaut das Gegenteil behauptet.
  2. **AC-9** gilt ausdrücklich für **beide** Wächter. Der Frontend-Wächter bekommt Positivfall
     und Umkehrprobe für die Nicht-Vererbung des Namens-Scope an verschachtelte Funktionen;
     vorher war diese Schutzmaßnahme dort ohne jeden Test (Mutation F7 ließ alle 24 Tests grün).
  3. **AC-12** prüft in der Positivkontrolle die **besuchte Dateimenge** statt „mindestens ein
     Fund". Vorher wurde ein auf die halbe Baumfläche verkürzter Lauf (Mutation B9) nur zufällig
     rot, weil ein Altlasten-Eintrag in der weggeschnittenen Hälfte lag. `scan_tree` bekommt dafür
     einen optionalen Sammel-Parameter `besucht`; die Soll-Menge wird zur Laufzeit aus `rglob`
     abgeleitet, nie als Zahl festgeschrieben.
  Alle drei Mutationen wurden nach der Nachbesserung erneut gefahren und werden jetzt jeweils von
  genau dem dafür vorgesehenen Test gefangen.
- 2026-08-20: Nach Adversary-Runde 2 (Finding F-FRONTEND-2, MEDIUM) der **AC-9-Nachweis im
  Frontend** auf alle drei Funktionsformen ausgeweitet. Vorher deckten beide Fixtures nur
  `function`-Deklarationen ab; eine Verengung der Vererbungssperre auf `ts.isFunctionDeclaration`
  ließ alle 26 Frontend-Tests grün. Das AC-9-Pendant ist jetzt über Arrow-Function,
  Function-Expression und Function-Deklaration parametrisiert (je Positivfall + Umkehrprobe,
  26 → 30 Frontend-Tests); dieselbe Verengung macht seither zwei Tests rot.
- 2026-08-20: Nach Adversary-Runde 3 (Findings F-BACKEND-1-R3 / F-FRONTEND-4, MEDIUM) **AC-21
  präzisiert und in beiden Wächtern gehärtet**. Beide Längenprüfungen entfernten vor dem
  `>= 15`-Vergleich nur Leerraum, keine Interpunktion — `# gz-thunder-scale: ...............`
  (15 Punkte), 15 Bindestriche und 15 gleiche Buchstaben öffneten den Notausgang der Ratsche.
  Übernommen ist jetzt die Filterung des Vorbild-Ratchets
  `tests/tdd/test_repo_path_hardcoding_ratchet.py` (`_UNWORT = re.compile(r"[\W_]+")`, im Frontend
  `/[^\p{L}\p{N}]+/gu` — Umlaute zählen), ergänzt um eine Mindestzahl **verschiedener** Zeichen,
  weil eine Zeichen-Wiederholung die Unwort-Filterung mit voller Länge überlebt. Der bestehende
  Marker in `src/output/renderers/narrow.py` besteht die verschärfte Prüfung unverändert
  (47 sinnvolle Zeichen, 16 verschiedene). Neue Fixtures und Grenzproben von beiden Seiten
  (14 → rot, 15 → grün): 50 → 56 Backend-, 30 → 36 Frontend-Tests.
- 2026-08-22: `ALTLASTEN` um sechs sanierte Einträge geschrumpft (#2010, #2011) — 9 → 3.
  `trip_command_processor.py::_THUNDER_LABEL`/`_MAP_EMOJI`/`_MAP_PLAIN`/`_handle_hours_drilldown`
  leiten ihre Wörter jetzt aus `THUNDER_LABEL_DE` ab statt sie lokal zu kopieren;
  `email/html.py::_thunder_risk_level` ruft für den String-/Enum-Pfad tatsächlich
  `thunder_ampel_band()` auf (Regel B und C). Verbleibende drei Einträge (`day_window.py`,
  zwei `trip_report_scheduler.py`-Symbole) unverändert. Details:
  `docs/specs/modules/fix_2010_2011_gewitter_stufenwoerter.md`.
