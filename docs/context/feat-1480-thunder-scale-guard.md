# Context: feat-1480-thunder-scale-guard

Issue: [#1480](https://github.com/henemm/gregor_zwanzig/issues/1480) — Wächter gegen lokale
Kopien der Gewitter-Stufenskala (Folge aus #1474: neun Fundstellen, drei Abstürze).
Track: **Full Process** (Intake-Score 5: Scope High · Blast Radius Medium · Unsicherheit High).

## Request Summary

Ein Wächter-Test soll rot werden, sobald irgendwo im Repo eine **zehnte** lokale Kopie der
Gewitter-Stufenskala (`ThunderLevel`: NONE/LOW/MED/HIGH) entsteht — in Produktivcode **und** in
Test-Doubles, Backend **und** Frontend. Nicht „findet weitere Stellen", sondern „verhindert die
nächste".

## Die eine Einsicht, die die Bauform bestimmt

Die naheliegende Regel — „kommen alle vier Stufen vor?" — hätte den **neunten** Fund verfehlt:
dort fehlte die vierte Stufe ja gerade, das *war* der Fehler. Der Wächter muss deshalb **gegen
die kanonische Quelle zählen** (Längen-/Vollständigkeitsvergleich), nicht auf Anwesenheit prüfen.

## Kanonische Quellen (Whitelist-Kandidaten)

| Datei | Was sie führt | Anmerkung |
|---|---|---|
| `src/app/models.py:35-45` | `ThunderLevel(str, Enum)` — NONE/LOW/MED/HIGH | Die Wahrheit über die Stufenmenge |
| `src/app/thunder_scale.py` | `_THUNDER_ORDER`, `_THUNDER_LABEL_VALUE` (je Enum→Zahl) | **Bereits zentralisiert** (#1196-Nacharbeit); Domänenschicht, keine Render-Abhängigkeit |
| `src/output/metric_format.py:236` | `THUNDER_LABEL_DE` (Enum→deutsches Wort) | Re-exportiert die beiden Skalen aus `thunder_scale.py` |
| `src/output/renderers/compare_metric_catalog.py:111` | `ordinalLabels: ["kein","leicht","mittel","hoch"]` | Einzige Quelle der Frontend-Beschriftung; Schieberegler-Bereich wird aus `len()` abgeleitet |
| `frontend/src/lib/types.ts:363` | `export type ThunderLevel = 'NONE'\|'LOW'\|'MED'\|'HIGH'` | Frontend-Spiegel |

## Existing Patterns

**Vorbild 1 — Python-AST-Ratsche:** `tests/tdd/test_repo_path_hardcoding_ratchet.py` (691 Zeilen).
Liefert das komplette Muster: `REPO_ROOT = Path(__file__).resolve().parents[2]` (Worktree, nicht
Hauptrepo — Pfadregel #1409), maschinell auffindbares `EXPIRY`-Prüfdatum, Ausnahme-Marker mit
Mindestbegründung (15 Zeichen), Fixture-Quelltexte als `.py.txt` **außerhalb der eigenen
Scanfläche** (sonst meldet der Wächter sich selbst), und ACs, die den Wächter an konstruierten
Verstößen rot zeigen statt nur „läuft durch".

**Vorbild 2 — Frontend-Parität gegen die echte Quelle:**
`frontend/.../corridor-editor/__tests__/compareMetricCatalogParity.test.ts` liest den Katalog
**live** per `execFileSync('uv', ['run','python3', …])` aus dem Backend statt aus einer
abgeschriebenen Erwartungsliste — ausdrücklich, weil eine hartkodierte Liste (#1424 F001, #1351
F003) kein echter Drift-Wächter ist. Genau dieses Muster braucht der neue Wächter für die
Test-Double-Parität.

**Vorbild 3 — Namens-Gate:** `.claude/hooks/test_naming_gate.py` (Bauform der Prüfdatum-Konstante).

## Dependencies

- **Upstream:** `ThunderLevel` (models.py) → `thunder_scale.py` → `metric_format.py` →
  Renderer/Scheduler/Command-Processor; `compare_metric_catalog.py` → `/api/compare/metrics` →
  `compareMetricCatalogLoader.ts` → Editoren.
- **Downstream des Wächters:** CI-Job `test` (alle nicht in `.github/ci_tdd_excludes.txt`
  gelisteten `tests/tdd/`-Dateien laufen automatisch mit) und, falls ein Frontend-Teil entsteht,
  Job `frontend-test` (`node --test`). Ein falsch schlagender Wächter blockiert damit **jeden**
  PR — Merge-Regel CLAUDE.md.

## Gemessene Befunde (nicht aus dem Issue übernommen)

1. **Die im Issue genannte Fehlalarm-Quelle stimmt so nicht.** `ChangeSeverity`
   (`models.py:469`) heißt `MINOR/MODERATE/MAJOR` — nutzt die Wörter LOW/HIGH gar nicht. Was in
   `deviation_alert_engine.py:~40` steht, ist ein Feld-Default `severity: str = "LOW"` (ein
   einzelner String, kein Literal mit ≥2 Stufen). Die Fehlalarm-Analyse muss neu gemessen werden.
   Echter Nachbar-Kandidat ist `RiskLevel` (`models.py:266`: `low/moderate/high`, kleingeschrieben).
2. **Mindestens ein weiterer Kandidat im Bestand:**
   `src/output/renderers/email/helpers.py:736-759` führt ein lokales `_THUNDER_MAP` mit allen vier
   Stufen als Dict-Literal. Ob kanonisch geduldet oder zehnte Kopie — muss die Analyse klären.
   `outlook.py:171-178` zeigt den Grenzfall: Zeilen 171-173 **lesen** aus `_THUNDER_LABEL_DE`
   (kein Duplikat der Information), die **Schlüsselmenge** ist trotzdem lokal gepflegt und bliebe
   bei einer fünften Stufe unvollständig. Genau hier greift die Längenprüfung — die Anwesenheits-
   prüfung nicht.
3. **Scanfläche grob:** 15 Python-Dateien in `src/` mit `ThunderLevel.X`-Referenzen; 17
   Frontend-Dateien mit den vier deutschen Wörtern, davon 11 Testdateien.

## Existing Specs

- `docs/specs/modules/fix_1409b_repo_path_ratchet.md` — Bauform-Spec des Vorbild-Ratchets inkl.
  „Known Limitations"; Vorlage für Struktur und Abgrenzung.
- Gewitter-Skala #1474: Commits `860a3baf` (vierte Stufe), `a75a5ae5` (#1474b), `a7704eb2`
  (#1491 Ampel-Spalte) — Korpus-Quelle für „VORHER".

## Risks & Considerations

1. 🔴 **Wächter trifft nichts und ist für immer grün.** Der dokumentierte Hausfehler
   (`reference_regex_guard_matches_nothing_always_green`): leere Trefferliste ⇒ jede „keiner ist
   schlecht"-Aussage ist wahr. Gegenmittel: Trefferzahl selbst behaupten (`> 0`) **und**
   Syntaxbaum statt Textmuster. Für `.ts`/`.svelte` heißt das: TypeScript-AST bzw.
   Svelte-Compiler — Regex über Frontend-Quelltext ist die bekannte Falle.
2. 🔴 **Gegen drei Korpora messen, bevor die Spec steht** (`feedback_guard_signatures_derive_from_code_first`,
   verschärft in #1409 B): **IST** (HEAD, misst Fehlalarme) · **VORHER**
   (`git show 860a3baf^:<datei>` in ein tmp-Verzeichnis, misst Treffsicherheit an echten,
   von Menschen geschriebenen Verstößen) · **SYNTH** (konstruierte Umgehungsformen). Der Bestand
   ist bereits repariert — gegen IST allein misst **jede** Regel null, auch eine wertlose.
3. **Selbstbezug:** Der Wächter darf seine eigenen Testfälle nicht als Verstoß melden →
   Fixture-Vorlagen außerhalb der Scanfläche ablegen, nicht die Regel schwächen.
4. **Ein falsch schlagender Wächter blockiert alle Sitzungen** — Fehlalarmzahl über die volle
   Scanfläche muss **gezählt** vorliegen, nicht geschätzt.
5. **Frontend-Ausführungsweg offen:** Python-Test, der `.ts` mitscannt, oder eigener
   `node:test`-Wächter? Der `qa_gate` ist blind für `node:test`-TAP-Ausgabe
   (`reference_qa_gate_blind_to_node_test_tap`) — beeinflusst die Abnahme, nicht die Bauform.
6. **Generisch oder gewitter-spezifisch?** Issue verlangt ausdrücklich die Prüfung, ob dieselbe
   Bauform für `RiskLevel`/`PrecipType`/`AvalancheProblem` taugt. `RiskLevel` ist der einzige
   echte Nachbar mit Stufencharakter; `PrecipType`/`AvalancheProblem` sind Typ-Mengen ohne
   Ordnung — die Längenprüfung passt dort, die Ordnungsprüfung nicht.
7. **Regel-Budget:** Neues Gate ⇒ Prüfdatum **2026-11-01**, maschinell auffindbar (CLAUDE.md).
   Belegte Fänge bei Einführung: neun, davon drei Abstürze.

---

# Analysis

**Type:** Feature (neuer Wächter). Enthält zwei abgeleitete Bug-Befunde (s. u.).

## Korrektur der Annahme aus dem Kontext-Teil

Oben stand „Der Bestand ist bereits repariert". **Das ist widerlegt.** Die IST-Messung fand
**18 lokale Kopien im Produktivcode** und **13 in Test-Doubles**, davon 7 veraltet und
**eine heute tatsächlich rot**. Der Wächter kann also nicht einfach eingeschaltet werden.

## Messung 1 — Korpus VORHER (die 9 echten Verstöße aus #1474)

Basisregel aus dem Issue („Dict-/Listen-Literal mit ≥2 der vier Werte") trifft **6 von 9**.

| Verfehlt | Grund | Konsequenz |
|---|---|---|
| `trip_command_processor.py:~682` (VORHER) | if/elif mit Tupel-Membership `str(v) in ("MED","ThunderLevel.MED")` — kein Dict/Listen-Literal | braucht **Regel B** (Ketten) |
| `corridorEditorState.ts:416` | TypeScript-Array; VORHER-Fassung **nicht git-rekonstruierbar** (Fehler entstand und verschwand in derselben Sitzung). Plausibelste Form: `['NONE','MED','HIGH','LOW']` — LOW ans Ende gehängt. **Alle vier Werte anwesend** | Anwesenheits- *und* Längenprüfung wären grün geblieben; nötig ist **Positions**-Bezug |

**Zusatz:** Die if/elif-**Textzweige** in `trip_report_scheduler.py` (~1548, ~1705) erzeugten das
eigentliche Nutzersymptom („leicht" → „Starkes Gewitter erwartet"). Die Dict-Regel trifft dort nur
den Nachbar-Bug (KeyError/Ranking), nicht den Textzweig.

**Wichtige Widerlegung einer naheliegenden Abgrenzung:** „String-Literal = verdächtig,
Enum-Attribut = sicher" ist **falsch** — `trip_report_scheduler.py:1536` (VORHER) war
`_NUM = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}`, also reine
Enum-Attribute und trotzdem eine Kopie.

## Messung 2 — Korpus IST (heutiger Bestand)

| Kategorie | Anzahl |
|---|---|
| A — kanonische Quelle | 6 Definitionsstellen; **eine fehlt auf der Issue-Whitelist**: `metric_format.py:247-252` `_THUNDER_AMPEL_BAND` (#1491/ADR-0025) — ein Wächter ohne sie meldet sie fälschlich |
| B — liest Quelle, führt eigene Schlüsselmenge | 3 (`email/outlook.py:169-174`, `email/compare_html.py:168-173`, `renderers/narrow.py:178-179`) |
| C — echte lokale Kopie | **15** (14 gezählt + `WeatherMetricsTab.svelte:1287-1290` nachgetragen) |
| D — Fehlalarm | Kern: generische Severity-Skala LOW/MODERATE/HIGH; **die Issue-Angabe zu `deviation_alert_engine.py:37,212,214` ist veraltet** (`ChangeSeverity` = MINOR/MODERATE/MAJOR). Echte Stellen: `deviation_alert_engine.py:40,249-256`, `frontend/types.ts:567`, `internal/store/archive_stats_test.go:61-62` |
| E — Test-Double | **13** in 10 Dateien, davon **7 veraltet**, **1 heute rot** |

**Kein einziger Wächter existiert heute.** Kein Test importiert `THUNDER_LABEL_DE`/`ORDINAL_ENUM`
zum Abgleich; kein Test iteriert `ThunderLevel` auf Vollständigkeit.

### Die Fehlalarm-Falle, die die Regel bestimmt
`risk_engine.py:127-135` ist eine if/elif-Kette direkt auf `ThunderLevel.HIGH/MED/LOW` —
**legitim**, weil die Zweigkörper nur fremde Enum-Konstruktoren enthalten
(`Risk(type=RiskType.THUNDERSTORM, level=RiskLevel.HIGH)`), kein eigenes Label/Zahl-Literal.
Das ist das Trennmerkmal für Regel B: **rohes Literal im Zweigkörper = Kopie**.

## Messung 3 — Werkzeuge (Unsicherheit aufgelöst)

- `typescript` 6.0.2 und `svelte` 5.56.3 sind vorhanden und werden im Repo **bereits produktiv
  für AST-Tests genutzt** (`deadTripOverviewComponentsRemoved.test.ts:21,60-77` nutzt
  `ts.createSourceFile`; ≥13 Dateien nutzen `svelte/compiler`).
- CI-Job `frontend-test` installiert bereits **uv + uv sync**, weil bestehende Tests die
  kanonische Python-Quelle live lesen (`compareMetricCatalogParity.test.ts:44-53`). Der Weg
  „Node-Wächter liest `_THUNDER_ORDER` aus dem Backend" ist erprobt und CI-seitig fertig.
- ⚠️ **Umgekehrte Richtung ist verbrannt:** TS-Parsing *aus Python heraus* hat einmal die gesamte
  pytest-Collection zerstört (`tests/unit/test_compare_metric_catalog_consistency.py:19-23`,
  Vorfall 2026-07-24). ⇒ **Zwei Wächter, nicht einer.**

## Technical Approach (Empfehlung)

**Zwei Wächter, Ratsche statt Vorsanierung, parametrisierter Kern.**

| Regel | Fasst | Fängt von den 9 |
|---|---|---|
| **A — Literal-Katalog** | Dict/Listen/Tupel/Set-Literal mit ≥2 der vier Werte (String **oder** `ThunderLevel.X`) als Key/Element, außerhalb der Whitelist | ~6 |
| **B — Ketten-Aggregation** | if/elif (≥2 Zweige) auf dieselbe Variable gegen ≥2 der vier Werte **und** mindestens ein Zweigkörper enthält ein eigenes String-/Zahl-Literal | +2–3 |
| **Positions-Bezug (Frontend)** | geordnete Arrays gegen `_THUNDER_ORDER` live abgleichen — Index von MED muss 2 sein, nicht 1 | die neunte |

Die neunte Stelle ist mit einer Anwesenheits-/Längenregel **strukturell nicht** fangbar. Sie
verschwindet nicht durch bessere Prüfung, sondern dadurch, dass ein lokales geordnetes Array
gegen die Quelle abgeglichen wird.

**Bestand: Ratsche mit nur-schrumpfender Ausnahmeliste.** Vorsanierung aller 15 C-Stellen berührt
alle drei Versandkanäle gleichzeitig (Mail/Telegram/SMS) plus Ortsvergleich-Scoring, Go und
Frontend — 150–300 LoC über 9 Dateien, jede Mail-Datei zieht den Pflicht-Validator (#811) nach
sich. Das reißt das 250-LoC-Limit und lässt den Schutzzweck tagelang unerfüllt. Die
Erkennungslogik bleibt dabei **ungeschwächt** — geduldet wird nur ein sichtbarer, benannter
Bestand (Präzedenz: `.github/ci_tdd_excludes.txt`).
⚠️ **Ausnahmen nie per Zeilennummer schlüsseln** (bricht bei jeder Verschiebung, #1466), sondern
per qualifiziertem Symbolnamen.

## Scheiben

| # | Inhalt | Umfang |
|---|---|---|
| **S1** | Backend-Wächter (Python-AST, Regel A+B, Ratsche, Prüfdatum 2026-11-01) | ~150–200 LoC |
| **S2** | Frontend-Wächter (TS-AST + Positions-Abgleich gegen `_THUNDER_ORDER` live) | ~80–120 LoC |
| **S3+** | Sanierung kanalweise, außerhalb dieses Workflows — je Kanal 1–4 Ratschen-Zeilen raus | je eigener PR |

## Abgeleitete Bug-Befunde (nicht Teil des Wächters)

1. **Mail mischt Deutsch und Englisch.** `email/helpers.py:735-765` `_THUNDER_MAP` liefert
   `"plain": "⚡MED"` / `"⚡HIGH"`, während NONE/LOW `"⚡–"` / `"⚡leicht"` liefern. Gerendert in
   `outlook.py:303` und `compact.py:224`. Die kanonische Quelle sagt „mittel"/„hoch"
   (`metric_format.py:238-239`). Nutzersichtbar ⇒ eigenes Issue (Triage-Kriterium a).
2. **Go-Endpoint kennt nur zwei Stufen.** `internal/provider/openmeteo/models.go:51-58`
   `parseThunderLevel()` liefert **nur** HIGH oder NONE (WMO 95/96/99), fließt über
   `provider.go:204-211` in `GET /api/forecast` (`router.go:126`). **Kein #1474-Regress**, sondern
   seit jeher binär. **Kein Aufrufer in `frontend/src` gefunden**, aber im `api_contract.md:1066`
   dokumentiert ⇒ kein bestätigtes Nutzerleid ⇒ Sammel-Eintrag #1199, kein eigenes Issue.
3. **Ein Test ist heute rot.** `tests/tdd/test_compare_metric_catalog_endpoint.py:220-228` erwartet
   `["kein","mittel","hoch"]`, der Endpoint liefert vier Labels. Steht auf
   `.github/ci_tdd_excludes.txt:24` ⇒ **CI-Ampel nicht betroffen** (letzter main-Lauf grün).
   Prüft veraltetes Verhalten ⇒ Erwartung nachziehen (Test-Politik: fixen oder löschen).

## Open Questions

- [ ] PO: Sanierung der 15 Altlasten als Folgearbeit (empfohlen) oder in diesem Zug?
- [ ] PO: Wächter nur für Gewitter (empfohlen) oder gleich `RiskLevel` mit (2 Duplikate:
      `risk_engine.py:28`, `stage_weather.py:31`)? Kern wird so oder so parametrisiert gebaut.
