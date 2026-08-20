# Context: feat-1480-thunder-scale-guard

Issue: [#1480](https://github.com/henemm/gregor_zwanzig/issues/1480) — Wächter gegen lokale
Kopien der Gewitter-Stufenskala (Folge aus #1474: neun Fundstellen, drei Abstürze).
Track: **Full Process** (Intake-Score 5: Scope High · Blast Radius High · Unsicherheit Medium).

> **Neu vermessen 2026-08-20.** Die vorherige Fassung dieses Dokuments stammte vom 2026-08-04.
> Seither sind **#1488** (2026-08-16) und **#1911** (2026-08-20) geliefert. Beide haben den
> Korpus verändert. Alle Zahlen unten sind frisch am Stand `bc6897a7` erhoben, nichts ist aus
> der alten Fassung übernommen.

## Request Summary

Ein Wächter-Test soll rot werden, sobald irgendwo im Repo eine **neue** lokale Kopie der
Gewitter-Stufenskala (`ThunderLevel`: NONE/LOW/MED/HIGH) entsteht — Produktivcode **und**
Test-Doubles, Backend **und** Frontend. Nicht „findet weitere Stellen", sondern „verhindert die
nächste".

## Was sich seit der Voranalyse geändert hat

| Annahme der Voranalyse (2026-08-04) | Stand 2026-08-20 |
|---|---|
| „Kein einziger Wächter existiert heute" | **Widerlegt.** Zwei existieren — aber beide bewachen **einen Punkt**, keine Fläche (s. u.) |
| 15 lokale Kopien im Produktivcode | **10** — Frontend ist sauber geworden, `compare_metric_catalog.py` leitet seit #1911 ab |
| 13 Test-Doubles, davon 7 veraltet | **12 Doubles, 0 veraltet.** Alle führen heute vier Stufen |
| `test_compare_metric_catalog_endpoint.py` ist rot, steht auf der Exclude-Liste | **Grün**, und nicht mehr auf der Liste (Batch 2, 2026-08-07) |
| `alertMetricLabels.ts::thunderLevelLabel()` ist die schädlichste Kopie | **Ersatzlos entfernt** in #1488 |
| Fehlalarm-Quelle sei `ChangeSeverity` | Bleibt falsch; echte Quellen s. Abschnitt Fehlalarm |

## Die Einsicht, die die Bauform bestimmt

Zwei Regeln, die beide **nicht** genügen:

1. **„Kommen alle vier Stufen vor?"** hätte den neunten #1474-Fund verfehlt — dort fehlte die
   vierte ja gerade, das *war* der Fehler.
2. **Eine Wortliste** hätte die damals schädlichste Kopie verfehlt: sie schrieb weder die Enum-
   noch die deutschen Namen, sondern rechnete Zahlen-Schwellen in Großbuchstaben-Deutsch um.

Die Frage muss deshalb umgedreht werden: nicht „erkenne ich alle Formen einer Kopie?" (jede neue
Schreibweise erzeugt eine neue blinde Stelle), sondern **„welche Stellen dürfen überhaupt eine
Gewitter-Beschriftung oder einen Stufen-Rang erzeugen?"** — alles außerhalb dieser Menge ist
verdächtig, auch in unbekannter Schreibweise.

## Kanonische Quellen (verifiziert 2026-08-20)

| Datei | Was sie führt |
|---|---|
| `src/app/models.py:35-43` | `ThunderLevel(str, Enum)` — NONE/LOW/MED/HIGH. Die Wahrheit über die Stufenmenge |
| `src/app/thunder_scale.py` | `_THUNDER_ORDER`, `thunder_ordinal()`, `thunder_label_value()`, `THUNDER_SIGNAL_LABEL_DE` |
| `src/output/metric_format.py:283-312` | `THUNDER_LABEL_DE`, `_THUNDER_AMPEL_BAND`, `thunder_ampel_band()`, `max_thunder()` |
| `src/output/renderers/compare_metric_catalog.py:66-67` | `_THUNDER_ORDINAL_LABELS` — **seit #1911 abgeleitet**, keine Kopie mehr |
| `frontend/src/lib/types.ts:401` | `export type ThunderLevel = 'NONE'\|'LOW'\|'MED'\|'HIGH'` |
| `frontend/.../corridor-editor/corridorEditorState.ts:407` | `ORDINAL_ENUM` — Index-Quelle des Frontends |
| `frontend/.../corridor-editor/compareMetricCatalogLoader.ts:212-236` | `deriveThunderThresholdLevels` / `thunderThresholdLevelsFromCatalog` |

⚠️ `_THUNDER_AMPEL_BAND` fehlte auf der Whitelist im Issue-Text. Ein Wächter ohne sie meldet die
kanonische Quelle selbst als Verstoß.

## Bestehende Wächter — sie bewachen einen Punkt, nicht die Fläche

| Wächter | Was er prüft | Fängt eine neue Kopie anderswo? |
|---|---|---|
| `tests/unit/test_compare_metric_catalog_consistency.py:151` | iteriert `list(ThunderLevel)`, prüft `len(ordinalLabels) == len(ThunderLevel)` + Ordinal-Lückenlosigkeit; **mit Wirkungsnachweis** | **Nein** — nur der Compare-Katalog-Eintrag |
| `tests/tdd/test_thunder_ordinal_labels_derivation.py` | Mutationstest: mutiert `THUNDER_LABEL_DE`, prüft dass `ordinalLabels` folgt | **Nein** — dieselbe eine Naht |
| `frontend/.../thunderThresholdCatalogGuard.test.ts` | AST-Strukturtest: `levels`-Attribut ist ein `CallExpression`, kein Array-Literal; Lade-/Fehler-Guard korrekt | **Nein** — genau **eine** hart verdrahtete Datei (`WeatherMetricsTab.svelte`) |

**Das ist die Lücke, die #1480 schließt.** Alle drei sichern die Naht ab, die #1911 gerade gebaut
hat. Legt jemand morgen in `trip_report_scheduler.py` ein neues `_NUM = {...}` an oder in einer
neuen Svelte-Komponente eine Stufenliste, bleibt jeder von ihnen still.

## Korpus IST — Backend (`src/`, `api/`, `internal/`, `cmd/`)

`api/` hat **keinen** Treffer. Zählung: **4× A · 4× B · 10× C.**

### Kategorie B — liest die Quelle, führt eigene Teilmenge (kein Duplikat der Information)

| Datei:Zeile | Was |
|---|---|
| `src/output/renderers/narrow.py:186-188` | `_SEV_TO_THUNDER_LEVEL` — Ordnung positional nachgebaut statt über `_THUNDER_ORDER` |
| `src/output/renderers/email/helpers.py:876-895` | `_THUNDER_MAP` — String-Keys, Werte aus `THUNDER_LABEL_DE` |
| `src/output/renderers/email/outlook.py:178-182` | nur LOW/MED/HIGH (NONE bewusst vorgelagert ausgeschlossen) |
| `src/output/renderers/email/compare_html.py:166-169` | LOW/MED/HIGH aus der Quelle, NONE lokal auf „—" — das dokumentierte erlaubte Muster |

Die **Schlüsselmenge** ist hier lokal gepflegt und bliebe bei einer fünften Stufe unvollständig.
Genau hier greift die Längenprüfung; die Anwesenheitsprüfung nicht.

### Kategorie C — echte lokale Kopien (10)

| Datei:Zeile | Was | Vollständig? |
|---|---|---|
| `src/services/trip_command_processor.py:135-142` | `_THUNDER_LABEL` Dict → kein/leicht/**mäßig**/hoch | 4/4, **Wortdrift** |
| `src/services/trip_command_processor.py:174-177` | `_MAP_EMOJI` + `_MAP_PLAIN`, „**keins**"/„**mäßig**" | 4/4, **Wortdrift** |
| `src/services/trip_command_processor.py:746-756` | if/elif, Tupel-Membership, rohe Wörter im Zweig | 4/4 |
| `src/app/day_window.py:178-182` | `_NIGHT_ADDENDUM_WORD` — leichtes/mittleres/starkes | NONE fehlt — **absichtlich**, Aufrufer filtert vor |
| `src/output/renderers/email/html.py:187-196` | if/elif auf rohe Strings → „risk"/„watch"/„yellow", **ohne** `thunder_ampel_band()` zu rufen, obwohl der Docstring das behauptet | 4/4 |
| `src/output/renderers/email/html.py:198-203` | **Zahlen-Schwelle→Wort:** `num > 20 → "risk"`, `num > 0 → "watch"` | **Nein — LOW/MED verschmelzen** |
| `src/services/trip_report_scheduler.py:2595-2605` | if/elif → rohe Satzvorlagen | 4/4 |
| `src/services/trip_report_scheduler.py:2831-2838` | **exaktes Duplikat** derselben vier Satzvorlagen, unabhängig gepflegt, selbe Datei | 4/4 |
| `internal/model/forecast.go:8-14` | Go-Typ: `ThunderNone/ThunderMed/ThunderHigh` — **`ThunderLow` existiert nicht** | **Nein — strukturell** |
| `internal/provider/openmeteo/models.go:50-57` | `parseThunderLevel()` — kann nur HIGH/NONE liefern | **Nein**, baut auf dem lückenhaften Go-Typ auf |

### Nicht als Kopie gewertet (delegieren an `thunder_ordinal()` / kanonische Konstruktoren)

`risk_engine.py:126-140` · `providers/openmeteo.py:664-686` · `weather_change_detection.py:866-870`
· `alert_preset.py:114-117` · `weather_metrics.py:1355-1358` · `day_comparison.py:343-356`
· `day_window.py:144-171` · `email/corridor_mark.py:51-56` · `narrow.py:177-180`
· `thunder_enrichment.py:262,271` · `providers/fixture.py:65-66` · `trip_report_scheduler.py:2539`

**Das Trennmerkmal für if/elif-Ketten:** `risk_engine.py:126-140` verzweigt legitim auf
`ThunderLevel.HIGH/MED/LOW`, weil die Zweigkörper nur **fremde Enum-Konstruktoren** enthalten
(`Risk(level=RiskLevel.HIGH)`). **Rohes Label-/Zahl-Literal im Zweigkörper = Kopie.**

## Korpus IST — Frontend (`frontend/src/`, ohne Tests)

**Keine aktive Kopie mehr.** Die letzte (`alertMetricLabels.ts::thunderLevelLabel()`) wurde in
#1488 ersatzlos entfernt. Verbleibender Drift:

| Datei:Zeile | Art |
|---|---|
| `corridorEditorState.ts:119-133` | `percentBoundToOrdinal` deckelt bei Index 2 — **Verhalten, nicht nur Kommentar** (s. Nebenbefunde) |
| `CorridorEditor.svelte:367` | stale Kommentar „3-Stufen-Band"; die Schleife rendert real vier |
| `CorridorEditorMobile.svelte:351-354` | stale Kommentar „3 Ordinal-Buttons" |
| `corridorEditorState.ts:113-130` | Doku-Kommentar beschreibt die alte 3-Stufen-Semantik |

## Korpus IST — Test-Doubles

**12 Vorkommen in 10 Dateien, davon 0 veraltet.** Die drei vom PO genannten 3-Stufen-Fixtures sind
durch #1911 (Commit `5c6abc8a`) saniert. Zwei Tests lesen die kanonische Quelle **live** per
`execFileSync('uv', ['run','python3','-c', …])`: `compareMetricCatalogParity.test.ts` (prüft
allerdings nur `defaultMin/Max` live, nicht `ordinalLabels` selbst) und
`thunderThresholdLevels.test.ts` (prüft `ordinalLabels` tatsächlich live gegen die Quelle).

## Werkzeuge & Bauform-Vorbilder (verifiziert)

- **Python-AST-Ratsche:** `tests/tdd/test_repo_path_hardcoding_ratchet.py` (692 Z.) — `ast.walk`,
  Marker-Kommentar `# gz-main-path: <Begründung>` mit Mindestlänge 15, `EXPIRY: date`-Konstante,
  Fixtures als `.py.txt` **außerhalb** der Scanfläche (mit eigenem Test, der das prüft).
  Schmalere Zweitfassung: `tests/tdd/test_data_root_hardcoding_ratchet.py` (451 Z.).
- **Frontend-AST:** `deadTripOverviewComponentsRemoved.test.ts` (`ts.createSourceFile`),
  `thunderThresholdCatalogGuard.test.ts` (`svelte/compiler::parse(…, {modern:true})`).
  24 Dateien nutzen `svelte/compiler`. Frontend-Tests laufen mit **`node --test`**, kein vitest.
- **Live-Read Node→Python:** `execFileSync('uv', ['run','python3','-c', PY_SCRIPT])`, JSON über
  stdout. CI-Job `frontend-test` installiert dafür bereits uv + `uv sync` (ci.yml:94-102).
- ⚠️ **Umgekehrte Richtung ist verbrannt:** TS-Parsing *aus Python heraus* hat am 2026-07-24 die
  gesamte pytest-Collection zerstört (dokumentiert in
  `tests/unit/test_compare_metric_catalog_consistency.py:19-21`). ⇒ **Zwei Wächter, nicht einer.**

### Der bestehende Scan-Helfer taugt nicht als Basis

`tests/helpers/metrik_listen_scan.py` scheidet aus zwei an der Schnittstelle festgemachten Gründen
aus — nicht aus Bequemlichkeit:

1. `scanne_register_listen(wurzeln)` nimmt zwar die Scan-Wurzeln als Parameter, aber die **Soll-
   Menge** `KENNUNGEN` ist Modul-global auf `app.metric_catalog._METRICS` verdrahtet. Eine andere
   Domäne ginge nur per Monkeypatch.
2. `_seiten()` extrahiert **nur `ast.Constant`-Strings**. Ein Dict, das nach `ThunderLevel.MED`
   schlüsselt, ist ein `ast.Attribute` und damit **unsichtbar** — genau die Form, die #1474 als
   Kopie Nummer eins hatte (`_NUM = {ThunderLevel.NONE: 0, …}`).

Ihn umzubauen hieße, einen produktiven Wächter mit 46 registrierten Fundstellen anzufassen; ein
falsch schlagender Wächter blockiert **jede** laufende Session. Deshalb eigener Scanner — die
Nichtteilung gehört ausdrücklich in die Spec begründet (der Bestand hat mit `data_root` vs.
`repo_path` bereits einen unbegründeten Präzedenzfall; den nicht wiederholen).

## Fehlalarm-Quellen (anderes Konzept, nur Wort-Überschneidung)

| Datei:Zeile | Konzept |
|---|---|
| `src/services/alert_urgency.py:20-21` | Alarm-Dringlichkeit LOW/MODERATE/HIGH (3) |
| `src/services/deviation_alert_engine.py:39,253-262` | `ChangeSeverity` → generische Abweichungs-Schwere |
| `src/app/models.py:312-316` | `RiskLevel` low/moderate/high — über **alle** RiskTypes |
| `src/output/renderers/trip_report.py:906-919` | `_RISK_LABELS` auf `(RiskType, RiskLevel)`, weitgehend toter Pfad |
| `internal/model/trip.go:207-220` | Kanal-Dringlichkeits-Schwelle LOW/MODERATE/HIGH |
| `frontend/src/lib/types.ts:605`, `:71` | Kanal-Dringlichkeit bzw. `AlertSeverity` |
| `frontend/.../metricsEditor.ts:27` | UI-Hilfetext „keins / mittel / hoch / extrem" — eigene Fantasieworte |
| `src/services/weather_metrics.py:122-158` | Wind-/Niederschlagsstärke mit „mäßig"/„leicht"/„stark" — **wahrscheinlicher Ursprung des Wortdrifts** |

Die Zwei-von-vier-Regel trennt LOW/MODERATE/HIGH sauber ab (kennt nur zwei der vier Wörter).

## Risks & Considerations

1. 🔴 **Wächter trifft nichts und ist für immer grün** (`reference_regex_guard_matches_nothing_always_green`).
   Gegenmittel: Trefferzahl selbst behaupten (`> 0`) **und** Syntaxbaum statt Textmuster.
2. 🔴 **Gegen drei Korpora messen:** IST (Fehlalarme) · **VORHER** (`git show 860a3baf^:<datei>` —
   die neun echten, von Menschen geschriebenen Verstöße; misst Treffsicherheit) · SYNTH
   (konstruierte Umgehungsformen). Gegen IST allein misst **jede** Regel null, auch eine wertlose.
3. **Selbstbezug:** Fixture-Vorlagen außerhalb der Scanfläche ablegen, nicht die Regel schwächen.
4. **Ein falsch schlagender Wächter blockiert alle Sitzungen** — die Fehlalarmzahl über die volle
   Scanfläche muss **gezählt** vorliegen, nicht geschätzt.
5. **Ausnahmen nie per Zeilennummer schlüsseln** (#1466), sondern per qualifiziertem Symbolnamen.
6. **Bekannte Grenze:** Eine Duldungsliste verifiziert die geduldeten Kopien nicht auf
   Korrektheit — driftet eine erneut, bleibt der Wächter still, solange der Symbolname überlebt.
   Gehört in die Spec unter „Known Limitations".
7. **Regel-Budget:** Prüfdatum **2026-11-01**, maschinell auffindbar als Konstante (nicht nur
   Prosa — `metrik_listen_scan.py` macht es falsch, die beiden Pfad-Ratschen richtig). Eintrag in
   die Tabelle `docs/reference/gates_und_ratschen.md:179-196` (heute 11 Einträge, keiner fällig).

## Nebenbefunde (nicht Teil des Wächters — Triage nach CLAUDE.md)

| # | Befund | Triage |
|---|---|---|
| 1 | **Go kennt keine Stufe LOW.** `internal/model/forecast.go:8-14` hat keine `ThunderLow`-Konstante; `parseThunderLevel()` liefert nur HIGH/NONE. Fließt in `GET /api/forecast`, in `api_contract.md:1066` dokumentiert. Kein #1474-Regress (seit jeher binär), kein Aufrufer in `frontend/src` | Kein bestätigtes Nutzerleid ⇒ **#1199** |
| 2 | **Wortdrift in Telegram-Ausgaben.** `trip_command_processor.py` sagt „mäßig"/„keins", kanonisch ist „mittel"/„kein" | Nutzersichtbar ⇒ **eigenes Issue** (Kriterium a) |
| 3 | **`email/html.py:187-203` umgeht `thunder_ampel_band()`**, obwohl der Docstring Angleichung behauptet; der Zahlen-Fallback verschmilzt LOW/MED | Nutzersichtbar (falsche Ampelfarbe) ⇒ **eigenes Issue** |
| 4 | **`percentBoundToOrdinal` deckelt bei Index 2.** Bestandskorridore „hoch" (Prozent 67–100) landen auf Index 2 = heute „mittel", „mittel" auf „leicht" | **Erreichbarkeit wird geprüft** — erst danach Triage |
| 5 | Doppelt gepflegte Satzvorlagen in `trip_report_scheduler.py:2595` und `:2831` | Wartungsrisiko, kein Fehlverhalten ⇒ **#1199** |
| 6 | `test_compare_metric_catalog_endpoint.py:192-197`: Docstring sagt „26 Metriken", Assertion prüft 25 | ⇒ **#1196** |
| 7 | Stale Kommentare: `CorridorEditor.svelte:367`, `CorridorEditorMobile.svelte:351`, `corridorEditorState.ts:113` | kosmetisch ⇒ **#1199** |

## Existing Specs

- `docs/specs/modules/fix_1409b_repo_path_ratchet.md` — Bauform-Spec des Vorbild-Ratchets inkl.
  „Known Limitations"; Vorlage für Struktur und Abgrenzung.
- `docs/specs/modules/thunder_threshold_katalog.md` — Spec von #1911, definiert die Ableitung.
- Korpus-Quelle „VORHER": Commit `860a3baf` (#1474, vierte Stufe).
