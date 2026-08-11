# Context: fix-1689-attestation-robustheit

Issue: [#1689](https://github.com/henemm/gregor_zwanzig/issues/1689) · `bug`, `priority:medium`, triage:c
(fälschlich blockierendes/crashendes Gate)

## Request Summary

Der Pflicht-Post-Deploy-Selftest stürzt ab, wenn das `findings`-Array einer Attestation
Nicht-Dict-Einträge (Bare-Strings) enthält — und `staging_gate.py` lässt genau solche Einträge
still hinein, sobald der Prüf-Agent statt einer JSON-**Liste** ein JSON-**Objekt** an
`--findings-json` übergibt. Zweimal am 2026-08-10 in zwei unabhängigen Sessions aufgetreten
(#1653, #1677); beide Male verzögerte sich der Deploy-Abschluss.

## Befund am Code (selbst nachgeprüft, nicht aus dem Issue übernommen)

### Schreibseite — `.claude/hooks/staging_gate.py`

| Zeile | Beobachtung |
|---|---|
| 358 | `findings = json.loads(findings_path.read_text())` — **kein Typ-Check**. Ein JSON-Objekt wird zu einem `dict`. |
| 370–373 | `[{**f, "workflow": w} if isinstance(f, dict) else f for f in findings]` — die Iteration über ein `dict` liefert dessen **Schlüssel** (Strings); der `else f`-Zweig reicht sie unverändert durch. Exit 0, keine Meldung. |
| 411–447 | Merge: `kept` filtert nur über `isinstance(f, dict) and f.get("workflow")`. Nicht-Dict-Altlasten fallen in keinen Filter und werden bei **jedem** Folgeschreiben unverändert mitgeschleppt. |

Zusätzlich (über den Issue-Text hinaus): ein **Skalar** in der Findings-Datei (`5`, `true`)
lässt `for f in findings` mit `TypeError` abbrechen — unbehandelter Traceback statt Meldung.

### Leseseite — `.claude/hooks/prod_selftest.py`

| Zeile | Beobachtung |
|---|---|
| 748 | `findings = verified.get("findings", [])` — kein Typ-Check auf das Feld selbst. |
| 759 | `pool.map(_probe_ac, findings)` — die Exception aus dem Worker schlägt beim Einsammeln durch. |
| 239–244 | `_probe_ac`: `finding.get("status")` → `AttributeError: 'str' object has no attribute 'get'`. |
| 547–577 | `_derive_verdict`: filtert ebenfalls über `p.get("status")` — würde an Nicht-Dicts genauso scheitern. |
| 455–463 | `_render_full_report(..., probes)` — dritte Stelle, die Dicts voraussetzt. |

**Präzisierung nach Gegenprobe (Challenger):** Es sind **eine akute + zwei latente**
Absturzstellen, nicht drei aktuelle. `_probe_ac` läuft als erstes und reißt den Lauf über
`pool.map` sofort ab — `_derive_verdict` und `_render_full_report` werden in diesem Durchlauf
nie erreicht. Latent werden sie genau dann, wenn man `_probe_ac` isoliert absichert (z. B. per
`try/except`, das den rohen String durchreicht). Konsequenz unverändert: Die Reparatur gehört
**vor** das `pool.map` — dort erledigt sie alle drei auf einmal.

### 🔴 Falle bei der naheliegenden Umsetzung

`_derive_verdict` liefert bei „keine PASS-Findings" **PASS** (Zeile 553–556), und Zeile 748–753
werten ein leeres `findings` als PASS mit Exit 0. Ein reines „Nicht-Dicts wegfiltern und
weitermachen" würde bei einer Attestation, die **nur** aus Bare-Strings besteht, einen stummen
Gesamt-PASS erzeugen — also aus einem lauten Crash ein leises Falsch-Grün machen. Das ist die
bekannte Klasse „Gate bestand mit Foto der Anmeldemaske". Muss in den ACs abgedeckt sein.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/staging_gate.py` | `write_verdict()` (Z. 330–452) — Eingangsvalidierung + Merge |
| `.claude/hooks/prod_selftest.py` | `_probe_ac` (239), Hauptlauf (748–776), `_derive_verdict` (547) |
| `.claude/hooks/_e2e_paths.py` | Auflösung `.claude/e2e_verified/<sha>.json` (unverändert) |
| `.claude/agents/staging-validator.md:88` | erzeugt die Findings-Datei — Aufrufer, der den Fehler produziert hat |
| `.claude/commands/e2e-verify.md:148` | zweiter Aufrufer |
| `tests/tdd/test_staging_gate.py` | Muster Subprozess-Aufruf `_run_gate`, `--e2e-path` in `tmp_path` |
| `tests/tdd/test_staging_gate_verdict_merge.py` | Muster Merge-Tests (#1197) |
| `tests/tdd/test_prod_selftest_internal_url_skip.py` | **Vorlage für den Regressionstest**: lädt `prod_selftest.py` per `importlib` aus der Worktree-Kopie, kein Netz |

## Existing Patterns

- **Fail-loud auf der Schreibseite, fail-soft auf der Leseseite.** Präzedenz: `write_verdict`
  lehnt seit #1327 Verdict-Texte ohne `VERIFIED`/`AMBIGUOUS`-Präfix mit Exit 1 ab (Z. 347–352) —
  exakt die Bauform, die `--findings-json` fehlt.
- **Skip-Status statt FAIL** auf der Leseseite: `SKIPPED_NO_URL`, `SKIPPED_PREVIEW_TEST_TRIP`,
  `SKIPPED_NOT_MAPPABLE` (#788/#1197) — ein neuer Status für unbrauchbare Einträge fügt sich ein.
- **Testpfad-Regel #1409:** Prüfling relativ zur Testdatei auflösen
  (`Path(__file__).resolve().parents[2]`), sonst prüft der Test die unveränderte Hauptrepo-Kopie.
- **Testnamensregel:** nach Verhalten benennen, nicht nach Issue-Nummer.

## Dependencies

- **Upstream** (erzeugen die Eingabe): `staging-validator`-Agent, `/e2e-verify`-Command — beide
  schreiben eine Findings-JSON nach `/tmp` und übergeben den Pfad.
- **Downstream** (lesen das Artefakt): `prod_selftest.py` (Findings als HTTP-Proben),
  `staging_gate.py --check` (nur `verified_commit`/`staging_verdict`/`scope`, **nicht** die
  Findings), `deploy-gregor-prod.sh` (ruft `--check` auf, liest die Findings nicht selbst).
  ⇒ Der Deploy-Block hängt nicht an den Findings; betroffen ist der **Issue-Close** hinter
  Schritt 4b.

## Existing Specs

- `docs/specs/modules/fix_1197_staging_gate_verdict_merge.md` — die Merge-Mechanik, die hier
  erweitert wird
- `docs/specs/modules/fix_1197_prod_selftest_internal_url_skip.md` — Vorbild für einen neuen
  Skip-/Meldestatus
- `docs/specs/modules/fix_1382_deploy_gate_evidence.md` — Nachweis-Ablage pro Stand
- `docs/specs/_archive/modules/issue_521_staging_validator.md` — Ursprungs-Kontrakt von Mode A

## Risks & Considerations

1. **Falsch-Grün statt Crash** (s. o.) — die Hauptgefahr der Umsetzung.
2. **Bestehende Attestationen** dürfen durch eine strengere Leseseite nicht plötzlich blockieren;
   alle `.claude/e2e_verified/*.json` mit sauberen Dict-Findings müssen unverändert PASS liefern.
3. **Verschärfung der Schreibseite** darf keinen gültigen Lauf abweisen — die bestehenden
   `test_staging_gate.py`-Fälle (leere Liste, Liste von Dicts) müssen grün bleiben.
4. **Merge-Bereinigung**: Nicht-Dict-Altlasten beim Folgeschreiben zu verwerfen ändert eine
   bestehende Datei. Das ist gewollt („laut sagen"), berührt aber den Marker-Schutz — die
   Bereinigung darf **nur** durch das Werkzeug selbst passieren, nie per Hand/Bash.
5. **Exit-Code-Messung**: Der ursprüngliche Crash wurde als PASS fehlgelesen, weil
   `… | tail; echo $?` den Exit der Pipe meldet. Für die Verifikation gilt: Exit direkt messen
   (`cmd > datei; echo $?`), nie durch eine Pipe.
6. **Kein Netz im Regressionstest** — Kern-Schicht, Muster aus `test_prod_selftest_internal_url_skip.py`.

## Analysis

### Type

**Bug** — fälschlich crashendes Gate (triage:c). Kein Verhalten der Anwendung betroffen,
ausschließlich die Nachweis-Kette der Auslieferung.

### Technical Approach (Empfehlung)

**Zwei Verteidigungslinien mit unterschiedlicher Härte** — das ist die Kernentscheidung:

| Seite | Verhalten | Begründung |
|---|---|---|
| **Schreibseite** `staging_gate.py` | **hart: Exit ≠ 0**, kein Artefakt | Der Prüf-Agent steht noch am Werkzeug und kann seine Datei sofort korrigieren. Ein kaputtes Artefakt entsteht gar nicht erst. Präzedenz im selben File: Verdict-Präfix-Prüfung (#1327, Z. 347–352). |
| **Leseseite** `prod_selftest.py` | **weich: überspringen + melden** | Läuft nach dem Deploy und trifft nur noch Altlasten. Ein kaputtes Artefakt darf den Wächter nicht abschießen — es soll als „Nachweis nicht sauber" **im Bericht stehen**. |

Konkret:

1. `staging_gate.py::write_verdict` — vor Z. 370 eine Eingangsprüfung: die geladene JSON muss
   eine **Liste** sein, und **jedes** Element ein **Dict**. Sonst Exit 1 mit einer Meldung, die
   den tatsächlichen Typ nennt und auf die erwartete Form hinweist. Deckt auch den
   Skalar-Fall ab (`TypeError` beim Iterieren).
2. `staging_gate.py` Merge (Z. 411–447) — Nicht-Dict-Einträge aus `existing_findings`
   **verwerfen** und die Zahl der verworfenen Einträge auf stderr melden. Damit heilt jedes
   reguläre Folgeschreiben ein bereits verschmutztes Artefakt, ohne Hand-Edit (Marker-Schutz
   bleibt gewahrt).
3. `prod_selftest.py` — **vor** dem `pool.map` (Z. 759) die Findings in verwertbar/unverwertbar
   trennen. Unverwertbare erscheinen als eigener Abschnitt im Bericht. Damit sind alle drei
   Absturzstellen (`_probe_ac`, `_derive_verdict`, `_render_full_report`) auf einen Schlag
   erledigt, weil ab dort garantiert nur noch Dicts fließen. Ebenso abgesichert: ein
   `findings`-Feld, das gar keine Liste ist (Z. 748).
4. **Gegen das Falsch-Grün:** Waren unverwertbare Einträge dabei und bleibt **kein einziger**
   verwertbarer übrig, ist das Ergebnis ausdrücklich **nicht PASS** — der Nachweis beweist
   dann nichts. Exit ≠ 0 mit klarer Meldung. Bei Mischung (einige unverwertbar, andere gültig)
   entscheidet wie bisher die Bewertung der gültigen Findings; die unverwertbaren stehen
   sichtbar im Bericht.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `.claude/hooks/_e2e_paths.py` | MODIFY | **neue gemeinsame Funktion** `partition_findings(raw)` → `(gültige, unverwertbare)`; einziger Ort, der die Form der Findings kennt |
| `.claude/hooks/staging_gate.py` | MODIFY | Eingangsprüfung `--findings-json` (hart, Exit 1); Merge verwirft Nicht-Dict-Altlasten laut |
| `.claude/hooks/prod_selftest.py` | MODIFY | Partitionierung vor `pool.map`; Bericht-Abschnitt; Verdict-Regel „alles unverwertbar" |
| `tests/tdd/test_attestation_findings_typsicher.py` | CREATE | Regressionstests beider Seiten, kein Netz, Fixture in der **realen** Objektform |

### Scope Assessment

- Dateien: 4 (3 MODIFY, 1 CREATE)
- Geschätzte LoC: ~+90 Code, ~+130 Test → **~220**, unter dem Limit 250, aber ohne viel Luft
- Risk Level: **MEDIUM** — kleiner, gut umgrenzter Eingriff, aber in den Wächtern selbst

### Dependencies / Reihenfolge

Schreib- und Leseseite sind unabhängig; die Leseseite ist die dringendere (sie crasht). Beides
in einer Scheibe, weil die Regressionstests dieselbe Fixture-Form teilen.

### Gegenprobe durch `analysis-challenger` (Verdict: NEEDS REVIEW) — eingearbeitet

1. **🔴 Der Bug liegt scharf im Repo, nicht nur in der Vergangenheit.**
   `.claude/e2e_verified/1001273d00382645824a11c96855a2ed9878fc51.json` trägt **heute**
   `"findings": ["issue", "commit", "steps", "cleanup", "skipped", "notes"]` — sechs nackte
   Strings. `verified_commit` passt zum Dateinamen, `staging_verdict` beginnt mit `VERIFIED`,
   `verified_at` = 2026-08-10T08:42:28Z. Die Datei besteht damit **jede** Metadaten-Prüfung in
   `gate_check()` und `_nearest_verified_ancestor()` und würde, sobald sie als exakter Treffer
   oder nächster Vorfahre gewählt wird, den Selftest zum Absturz bringen. Sie liegt innerhalb
   des Retention-Fensters (`ATTESTATION_RETENTION=20`, `staging_gate.py:62`), ist nach mtime
   ca. die achtälteste und überlebt noch mehrere Schreibvorgänge. Die 19 anderen Attestationen
   sind sauber — der Fehler ist selten, aber real.
   **Nicht anfassen** (Marker-Schutz, Regel „Gate-State-Dateien nie per Hand"): der Fix macht
   sie harmlos, und sie ist der beste Live-Beleg für die Wirkung.
2. **🔴 Die reale Fehlform ist nicht „Liste vergessen".** Die Schlüssel `issue/commit/steps/
   cleanup/skipped/notes` sehen nach einer **Report-/Changelog-Struktur** aus, nicht nach dem
   AC-Schema `ac/status/url/evidence` (`.claude/agents/staging-validator.md:60–91`). Eine
   Fixture, die nur „leeres Objekt statt Liste" simuliert, träfe den echten Fall womöglich
   nicht. Die Regressionstests bilden **genau diese Objektform** nach.
3. **Strukturell statt punktuell.** `staging_gate.py` trägt 40, `prod_selftest.py` 24
   Issue-Referenzen in Kommentaren — beide Dateien wurden wieder und wieder gegen dieselbe
   Klasse (kaputte/fehlende/veraltete Attestation-Daten) einzeln nachgerüstet, ohne dass es je
   **eine** Stelle für die Form der Findings gab. Deshalb: die Prüf-/Normalisierungsfunktion
   nach **`_e2e_paths.py`** — beide Hooks laden dieses Modul ohnehin schon per `importlib`
   (`staging_gate.py:47–52`, `prod_selftest.py:47–51`), teilen dann **einen** Typkontrakt und
   die nächste Konsumstelle erbt ihn automatisch.
4. **Reichweite (4) bestätigt, jetzt am Original.** `gate_check()` (`staging_gate.py:461–654`)
   und `_nearest_verified_ancestor()` (`_e2e_paths.py:292–359`) lesen nur
   `verified_commit`/`staging_verdict`/`verified_at`. `deploy-gregor-prod.sh` (Z. 174, 210) ruft
   ausschließlich `staging_gate.py --check` auf und liest die Findings nirgends selbst —
   nachgelesen im Originalskript, nicht aus der Doku abgeleitet.
5. **Kein heute grüner Test bricht.** Weder `test_staging_gate.py` noch
   `test_staging_gate_verdict_merge.py` übergeben Nicht-Dict-Findings oder ein JSON-Objekt.

### Open Questions

- [ ] Keine blockierenden. Die einzige echte Entscheidung — hart schreiben / weich lesen, und
      „alles unverwertbar ⇒ nicht PASS" — geht als AC in die Spec und wird dort freigegeben.
