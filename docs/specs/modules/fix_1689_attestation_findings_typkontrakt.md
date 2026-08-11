---
entity_id: fix_1689_attestation_findings_typkontrakt
type: bugfix
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.2"
tags: [gate, attestation, staging-gate, prod-selftest]
---

# Attestation-Findings: gemeinsamer Typkontrakt (hart schreiben, weich lesen)

## Approval

- [x] Approved — PO-Freigabe 2026-08-10 („auf 500 anheben, go"), inkl.
      `loc_limit_override = 500` für diesen Workflow

## Purpose

Der Pflicht-Post-Deploy-Selftest (`prod_selftest.py`) stürzt ab, wenn das
`findings`-Array einer Attestation Nicht-Dict-Einträge (Bare-Strings) enthält —
und `staging_gate.py` lässt genau solche Einträge still hinein, sobald der
Prüf-Agent statt einer JSON-**Liste** ein JSON-**Objekt** an `--findings-json`
übergibt. Zweimal am 2026-08-10 in zwei unabhängigen Sessions aufgetreten
(#1653, #1677), beide Male verzögerte sich der Deploy-Abschluss. Eine zweite
Gegenprobe fand dieselbe Fehlerklasse eine Ebene höher: auch das **Top-Level**
der Attestation selbst (nicht nur das `findings`-Array) wird an drei Stellen
per `.get()` verwendet, ohne zu prüfen, ob überhaupt ein Dict geladen wurde.
Diese Spec führt einen **gemeinsamen Typkontrakt für Attestation-Daten** ein
(Top-Level-Dict UND Findings-Array) und macht die Schreib- und
Deploy-Gate-Seite hart, die reinen Lese-/Report-Seiten weich, aber nicht
blind (überspringen + sichtbar melden statt Absturz oder stilles Falsch-Grün).

## Source

- **File:** `.claude/hooks/_e2e_paths.py`
- **Identifier:** `partition_findings(raw)` (neu) — von `staging_gate.py` und
  `prod_selftest.py` per `importlib` geladen (bereits bestehendes Muster,
  `staging_gate.py:47–52`, `prod_selftest.py:47–51`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/_e2e_paths.py` | module | Ort des neuen gemeinsamen Typkontrakts `partition_findings()`; wird von beiden Hooks bereits per `importlib.util.spec_from_file_location` geladen |
| `.claude/hooks/staging_gate.py::write_verdict` | function | Schreibseite (Mode A) — Eingangsprüfung + Merge-Bereinigung, `write_verdict` Z. 330–458; Merge-Lesepfad Z. 410 |
| `.claude/hooks/staging_gate.py::gate_check` | function | Deploy-Gate (Mode B) — Exakt-Match-Zweig Z. 551, aufgerufen von `deploy-gregor-prod.sh:174,210` im echten Prod-Deploy |
| `.claude/hooks/prod_selftest.py` | module | Leseseite — `_probe_ac` (Z. 239), `_derive_verdict` (Z. 547), `_render_full_report` (Z. 439), Exakt-Match-Zweig (Z. 689), Hauptlauf (Z. 748–776) |
| `.claude/agents/staging-validator.md` | agent | Erzeugt die `--findings-json`-Datei (Aufrufer, der den Fehler in #1653/#1677 produziert hat) |
| `.claude/commands/e2e-verify.md` | command | Zweiter Aufrufer von `staging_gate.py --write-verdict` |
| `docs/specs/modules/fix_1197_prod_selftest_internal_url_skip.md` | spec | Vorbild für einen neuen Skip-/Meldestatus auf der Leseseite |
| `docs/specs/modules/fix_1197_staging_gate_verdict_merge.md` | spec | Merge-Mechanik, die hier um die Bereinigung von Nicht-Dict-Altlasten erweitert wird |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/_e2e_paths.py` | MODIFY | Neue Funktion `partition_findings(raw)` → `(gueltige: list[dict], unverwertbare: list)`; einziger Ort, der die Form eines Findings kennt |
| `.claude/hooks/staging_gate.py` | MODIFY | `write_verdict`: Eingangsprüfung der geladenen `--findings-json` (hart, Exit ≠ 0 bei Nicht-Liste oder Nicht-Dict-Element); Merge (Z. 411–447) verwirft Nicht-Dict-Altlasten aus `existing_findings` und meldet die Anzahl; Merge-Lesepfad (Z. 410) behandelt ein Top-Level-Nicht-Dict wie eine kaputte Datei; `gate_check` (Z. 551) blockiert fail-closed bei Top-Level-Nicht-Dict |
| `.claude/hooks/prod_selftest.py` | MODIFY | Partitionierung der `findings` **vor** `pool.map` (Z. 758–759) über `_e2e_paths.partition_findings`; unverwertbare Einträge als eigener Bericht-Abschnitt (`_render_full_report`); neue Verdict-Regel „alles unverwertbar ⇒ nicht PASS"; Exakt-Match-Zweig (Z. 689) fällt bei Top-Level-Nicht-Dict auf die Ancestor-Suche zurück |
| `tests/tdd/test_attestation_findings_typsicher.py` | CREATE | Regressionstests aller drei Ebenen (Findings-Array, Top-Level-Merge-Lesepfad, Top-Level-Gate-Check/Selftest-Exaktmatch) + der gemeinsamen Funktion, kein Netz, Fixtures in den real vorgefundenen Fehlformen |

### Estimated Changes

- Files: 4 (3 MODIFY, 1 CREATE)
- LoC: ~+105 Code (Findings-Guard + 3 Top-Level-Guards), ~+150 Test (11 Testfälle inkl. Subprozess- und Boundary-Seam-Muster) → ~255 gesamt — **liegt über dem Workflow-Limit von 250**. Ein `loc_limit_override` ist vor der Implementierung beim PO einzuholen, nicht eigenmächtig zu setzen.
- Effort: medium — kleiner, gut umgrenzter Eingriff, aber in den Wächtern selbst (Sorgfaltspflicht hoch, einer der drei neuen Guards sitzt im echten Prod-Deploy-Pfad)

## Implementation Details

### Warum zentral

Dies ist bereits der **sechste** reaktiv nachgerüstete `isinstance(dict)`-Guard
an demselben Objektgraphen — vorherige fünf: `_e2e_paths.py:54, :72, :139,
:344` und `staging_gate.py:371/419/430/439`, entstanden aus #916, #1084,
#1130, #1382, #1327. `prod_selftest.py` hat dagegen bis heute **null** solche
Guards — genau dort liegt die akute Absturzstelle dieser Spec. Ausgerechnet
der Ancestor-Pfad (`_e2e_paths.py:344`) ist geschützt, der häufiger benutzte
Exakt-Match-Pfad in `staging_gate.py:551` und `prod_selftest.py:689` ist es
nicht — eine Asymmetrie, die nur auffällt, wenn man beide Pfade nebeneinander
liest. Genau das begründet, warum die neue Prüffunktion nach `_e2e_paths.py`
gehört statt zum siebten Einzelflicken an einer der beiden Aufrufer-Dateien
zu werden: beide Hooks laden das Modul bereits per `importlib`
(`staging_gate.py:47–52`, `prod_selftest.py:47–51`), es entsteht kein neues
Modul und kein neuer Import-Pfad.

1. **`_e2e_paths.py` — `partition_findings(raw)`:** Erwartet `raw` als
   beliebigen aus JSON geladenen Wert. Ist `raw` keine Liste, ist das gesamte
   Ergebnis unverwertbar (leere `gueltige`, `raw` selbst als einziger Eintrag
   in `unverwertbare`, oder eine äquivalente Markierung „kein Listentyp").
   Ist `raw` eine Liste, wird elementweise nach `isinstance(f, dict)`
   getrennt; die Reihenfolge bleibt erhalten. Reine Funktion, keine
   Seiteneffekte, kein Zugriff auf Dateisystem/Zeit.

2. **Schreibseite `staging_gate.py::write_verdict`** (vor der heutigen Z. 370,
   `[{**f, "workflow": w} if isinstance(f, dict) else f for f in findings]`):
   Nach dem Laden der `--findings-json` (Z. 357–361) wird `partition_findings`
   aufgerufen. Bleibt auch nur ein unverwertbarer Eintrag übrig oder war die
   Wurzel selbst keine Liste, bricht der Aufruf mit Exit ≠ 0 ab, **bevor**
   irgendein Artefakt geschrieben wird — analog zur bestehenden
   Verdict-Präfix-Prüfung im selben File (#1327, Z. 347–352: erst prüfen,
   dann erst der `_telegram_live_gate()`-Aufruf und das Schreiben). Die
   Meldung nennt den tatsächlich vorgefundenen Typ (z. B. `dict` statt
   `list`) bzw. bei einer Liste den Index und Typ des ersten unverwertbaren
   Elements. Ein Skalar (`5`, `true`, `null`) in der Datei fällt ebenfalls
   unter „keine Liste" und erzeugt keinen unbehandelten `TypeError` mehr.

3. **Merge-Bereinigung** (heutige Z. 411–447): `existing_findings` wird vor
   dem `kept = [...]`-Filter durch `partition_findings` geschickt; nur die
   `gueltige`-Hälfte fließt in den weiteren Merge (`kept`, `seen`, `merged`)
   ein. Die Anzahl verworfener Einträge wird auf stderr gemeldet (Muster wie
   `_log(...)` an anderen Stellen derselben Funktion). Damit heilt **jeder**
   reguläre Folgeschreibvorgang für denselben `verified_commit` ein bereits
   verschmutztes Artefakt — ohne Hand-Edit an der Gate-Datei (Marker-Schutz
   bleibt gewahrt, die Bereinigung passiert ausschließlich durch das
   Werkzeug selbst).

4. **Top-Level-Guard im Merge-Lesepfad** (`staging_gate.py:410`,
   `if existing is not None and existing.get("verified_commit") == sha:`):
   Vor dem `.get()`-Aufruf zusätzlich `isinstance(existing, dict)` prüfen.
   Trifft das nicht zu, wird die Datei wie eine kaputte/fehlende Attestation
   behandelt — regulär überschrieben, konsistent mit dem bestehenden
   Kommentar „Bei abweichendem/fehlendem/kaputtem verified_commit bleibt das
   reguläre Überschreiben" (Z. 404). Kein Exit-Abbruch an dieser Stelle, weil
   der reguläre Schreibvorgang selbst dadurch nicht verhindert werden darf.

5. **Top-Level-Guard im Gate-Check** (`staging_gate.py:551`,
   `verified_commit = data.get("verified_commit", "") if data is not None
   else ""`): **Fail-closed.** Ist `data` geladen, aber kein Dict, wird das
   NICHT wie `data is None` (→ kein Treffer, Ancestor-Relaxierung möglich)
   behandelt, sondern blockiert den Deploy sofort mit Exit ≠ 0 und einer
   eindeutigen Meldung, die den vorgefundenen Typ nennt. Dies ist der
   Exakt-Match-Zweig des echten Prod-Deploy-Gates
   (`deploy-gregor-prod.sh:174,210`) — hier gilt dieselbe Härte wie bei der
   Verdict-Präfix-Prüfung, weil ein Deploy sonst auf einer unlesbaren
   Attestation basieren könnte, ohne dass irgendjemand es bemerkt.

6. **Top-Level-Guard im Selftest-Exaktmatch** (`prod_selftest.py:689`,
   `if exact_data is not None and exact_data.get("verified_commit") ==
   head:`): Zusätzlich `isinstance(exact_data, dict)` prüfen. Trifft das
   nicht zu, wird wie „kein exakter Treffer" verfahren — die bestehende
   Ancestor-Suche (dieselbe geteilte `_e2e_paths._nearest_verified_ancestor`,
   die bereits an Z. 344 durch ihren eigenen Guard geschützt ist) greift
   automatisch, statt mit `AttributeError` abzustürzen. Analog zur
   Leseseite bei den Findings: weich, weil dies nach dem Deploy läuft und
   nur noch Altlasten trifft.

7. **Leseseite `prod_selftest.py`** (vor der heutigen Z. 758–759,
   `probes = list(pool.map(_probe_ac, findings))`): `findings = verified.get(
   "findings", [])` (Z. 748) wird durch `partition_findings` geschickt, statt
   direkt an `pool.map` übergeben zu werden. Die `unverwertbare`-Liste
   erscheint als eigener, sichtbarer Abschnitt im Bericht (`_render_full_report`,
   Z. 439 ff.) — z. B. eine zusätzliche Überschrift „## Unverwertbare Findings"
   mit den rohen Einträgen. Ab dieser Stelle fließen in `pool.map`,
   `_derive_verdict` (Z. 547) und `_render_full_report` garantiert nur noch
   Dicts — damit sind alle drei bekannten Absturzstellen (`_probe_ac`
   akut über `pool.map`; `_derive_verdict`/`_render_full_report` latent,
   sobald `_probe_ac` isoliert abgesichert würde) auf einen Schlag erledigt.
   Ein `findings`-Feld, das selbst gar keine Liste ist, wird von
   `partition_findings` identisch wie „alles unverwertbar" behandelt.

8. **🔴 Verdict-Regel gegen Falsch-Grün — am WIRKORT prüfen, nicht am
   Kurzschluss.** Waren unverwertbare Einträge dabei und bleibt nach dem
   Partitionieren **kein einziger** verwertbarer übrig, liefert der Selftest
   ausdrücklich **nicht** `PASS` (auch nicht `SKIPPED_ALL` o. ä.) und
   Exit ≠ 0. **Wichtig:** Diese Regel darf sich nicht allein auf die heutige
   Sonderbehandlung „leere Findings ⇒ PASS" (Z. 749–756) stützen, denn
   `_derive_verdict([])` liefert **selbst** PASS zurück, unabhängig davon,
   wo vorher gefiltert wurde: Z. 551 (`if probes and len(skipped_probes) ==
   len(probes)`) ist bei leerer Liste falsch, Z. 553
   (`if not pass_probes: return "PASS"`) trifft dann zu. Jede
   Fix-Variante, die am Ende `_derive_verdict` mit einer nach Partitionierung
   leeren Probe-Liste aufruft, tappt sonst in dieselbe Falle. Die Zusicherung
   muss deshalb am **Ergebnis des vollständigen Laufs** hängen (finaler
   Verdict-String + Prozess-Exit-Code), nicht an der Stelle, an der gefiltert
   wird: konkret muss vor dem Aufruf von `_derive_verdict` (oder als erste
   Prüfung darin) festgestellt werden „rohe Findings waren nicht leer UND
   unverwertbare waren vorhanden UND gueltige ist leer" ⇒ eigener
   Nicht-PASS-Pfad, unabhängig vom sonstigen `_derive_verdict`-Verhalten.
   Eine leere **rohe** Findings-Liste (kein unverwertbarer Eintrag vorhanden)
   bleibt PASS wie bisher. Bei Mischung (einige unverwertbar, andere gültig)
   entscheidet unverändert die Bewertung der gültigen Findings; die
   unverwertbaren stehen zusätzlich sichtbar im Bericht.

## Expected Behavior

- **Input (Schreibseite):** `--findings-json` zeigt auf eine Datei mit
  beliebigem JSON-Inhalt.
- **Output (Schreibseite):** Nur bei einer JSON-Liste aus ausschließlich
  Dict-Elementen wird die Attestation geschrieben (Exit 0 bei
  VERIFIED/AMBIGUOUS-Präfix, unverändert). Bei jeder anderen Form: Exit ≠ 0,
  kein Artefakt, Meldung mit dem vorgefundenen Typ auf stderr.
- **Input (Merge-Lesepfad / Gate-Check / Selftest-Exaktmatch):** eine
  bestehende `.claude/e2e_verified/<sha>.json`, deren Top-Level-JSON valide,
  aber kein Dict ist.
- **Output:** Merge-Lesepfad behandelt dies wie eine kaputte Datei (regulär
  überschreiben); Gate-Check blockiert fail-closed (Exit ≠ 0, Deploy-relevant);
  Selftest-Exaktmatch fällt weich auf die Ancestor-Suche zurück.
- **Input (Leseseite Findings):** `verified.get("findings", [])` aus einer
  bestehenden `.claude/e2e_verified/<sha>.json`.
- **Output (Leseseite Findings):** Kein Absturz unabhängig vom Inhalt.
  Gemischte Findings liefern ein Verdict nur aus den gültigen Einträgen,
  unverwertbare erscheinen im Bericht. Ausschließlich unverwertbare Findings
  liefern ein explizites Nicht-PASS mit Exit ≠ 0.
- **Side effects:** Merge-Bereinigung verändert bestehende
  `.claude/e2e_verified/<sha>.json`-Dateien beim nächsten regulären Schreiben
  desselben `verified_commit` (gewollt, siehe Punkt 3 oben). Kein
  Hand-Edit, keine Bash-Manipulation der Gate-Datei.

## Acceptance Criteria

- **AC-1:** Given eine gemischte Rohliste aus Findings (Dict- und
  Nicht-Dict-Einträgen in beliebiger Reihenfolge), When
  `_e2e_paths.partition_findings(raw)` aufgerufen wird, Then liefert sie ein
  Tupel `(gueltige, unverwertbare)`, in dem `gueltige` ausschließlich die
  Dict-Einträge und `unverwertbare` ausschließlich die Nicht-Dict-Einträge
  enthält, jeweils in ursprünglicher Reihenfolge.
  - Test: Direkter Aufruf der reinen Funktion mit einer Liste, die Dicts,
    Strings und eine Zahl mischt — kein Dateiinhalt-Check, echtes
    Funktionsverhalten.

- **AC-2:** Given eine `--findings-json`-Datei mit validem JSON, das aber
  KEINE Liste ist (z. B. ein Objekt `{"issue": "...", "commit": "..."}"`,
  eine Zahl oder `null`), When `staging_gate.py --write-verdict "VERIFIED: …"
  --findings-json <datei>` aufgerufen wird, Then bricht der Prozess mit
  Exit-Code ≠ 0 ab, es wird KEINE `.claude/e2e_verified/<sha>.json`
  geschrieben, und die stderr-Meldung nennt den tatsächlich vorgefundenen
  Typ (z. B. „dict" statt „list").
  - Test: Subprozess-Aufruf von `staging_gate.py` (Muster
    `test_staging_gate.py::_run_gate`) mit `--e2e-path` in `tmp_path`;
    Assertion auf Exit-Code, Nicht-Existenz der Zieldatei und Meldungsinhalt.

- **AC-3:** Given eine `--findings-json`-Datei mit einer JSON-Liste, die
  mindestens ein Nicht-Dict-Element enthält (z. B. `["issue", "commit",
  "steps", "cleanup", "skipped", "notes"]` — die reale Fehlform aus
  `.claude/e2e_verified/1001273d00382645824a11c96855a2ed9878fc51.json`), When
  `--write-verdict` aufgerufen wird, Then bricht der Prozess mit Exit-Code
  ≠ 0 ab, es wird kein Artefakt geschrieben, und die Meldung weist auf
  unverwertbare Elemente in der Liste hin.
  - Test: Subprozess-Aufruf wie AC-2, Fixture ist exakt die reale Fehlform.

- **AC-4:** Given eine bestehende Attestation für denselben `verified_commit`,
  deren `findings`-Array bereits Nicht-Dict-Altlasten enthält, When ein
  weiterer regulärer `--write-verdict`-Aufruf mit gültigen (Dict-)Findings
  für denselben Commit erfolgt, Then enthält die geschriebene Datei im
  `findings`-Array KEINE Nicht-Dict-Einträge mehr, und die Anzahl der
  verworfenen Einträge wird auf stderr gemeldet.
  - Test: Zwei aufeinanderfolgende `_run_gate`-Aufrufe auf dieselbe
    `tmp_path`-Attestation (Muster `test_staging_gate_verdict_merge.py`):
    erster Aufruf legt eine Attestation mit Bare-String-Findings direkt per
    `json.dump` an (simuliert Altlast), zweiter Aufruf ist ein regulärer
    `--write-verdict` mit sauberen Findings.

- **AC-5:** Given eine Attestation, deren `findings`-Array eine Mischung aus
  gültigen Dict-Findings und unverwertbaren Nicht-Dict-Einträgen enthält,
  When `prod_selftest.py` sie verarbeitet, Then löst dies weder
  `AttributeError` noch `TypeError` aus, die unverwertbaren Einträge
  erscheinen als eigener sichtbarer Abschnitt im erzeugten Bericht, und der
  Verdict richtet sich ausschließlich nach den gültigen Findings.
  - Test: Modul per `importlib` aus der Worktree-Kopie laden (Muster
    `test_prod_selftest_internal_url_skip.py`), `_e2e_verified_data` mit
    gemischten Findings präparieren. Der Health-Check wird als ehrlicher
    Boundary-Seam an der Netzgrenze ersetzt (Muster
    `test_prod_selftest_internal_url_skip.py`: `_http_get` per monkeypatch
    durch einen Recorder, der NIE die zu testende Logik zurückspiegelt) —
    ausschließlich um die Netzgrenze zu kontrollieren, kein Mock der
    Findings-Verarbeitung selbst. Bericht-Text auf den neuen Abschnitt
    prüfen.

- **AC-6:** Given eine Attestation, deren `findings`-Feld selbst gar keine
  Liste ist (z. B. ein Objekt statt einer Liste), When `prod_selftest.py`
  sie verarbeitet, Then löst dies keinen Absturz aus, sondern das Feld wird
  vollständig als unverwertbar behandelt und im Bericht entsprechend
  ausgewiesen.
  - Test: wie AC-5, aber `findings` im präparierten Attestation-Dict durch
    ein Objekt ersetzt.

- **AC-7:** Given eine Attestation, deren `findings`-Array ausschließlich
  aus unverwertbaren Nicht-Dict-Einträgen besteht (reale Fehlform:
  `["issue", "commit", "steps", "cleanup", "skipped", "notes"]`), When
  `prod_selftest.py` den **vollständigen Lauf** verarbeitet (nicht nur der
  Kurzschluss bei leerer Roh-Liste, sondern der reguläre Pfad bis
  `_derive_verdict`), Then ist das ENDGÜLTIGE Ergebnis AUSDRÜCKLICH NICHT
  PASS (weder `PASS` noch `SKIPPED_ALL` noch ein anderer Erfolgs-Status) und
  der Prozess-Exit-Code ist ≠ 0 — kein stiller Erfolg für einen unbrauchbaren
  Nachweis, auch nicht auf dem Umweg über eine nach Partitionierung leere
  Probe-Liste, die `_derive_verdict([])` sonst als PASS werten würde
  (`prod_selftest.py:553–556`).
  - Test: wie AC-5, `findings` exakt auf die reale Fehlform gesetzt;
    Assertion auf den **von der Hauptlauf-Funktion tatsächlich
    zurückgegebenen/geschriebenen** Verdict-String UND den Prozess-Exit-Code
    (nicht auf einen internen Zwischenwert oder nur auf einen der beiden —
    genau die Verwechslung, die den Bug erst unentdeckt ließ, #1689 Risk 5:
    „… | tail; echo $?" maskiert den echten Exit-Code). Der Test MUSS
    `_derive_verdict` mit dem tatsächlich partitionierten (leeren)
    Probe-Ergebnis durchlaufen lassen — der Kurzschluss darf nicht künstlich
    vorgezogen werden, sonst prüft der Test am eigentlichen Bugpfad vorbei.

- **AC-8:** Given eine bestehende Attestation-Datei für denselben
  `verified_commit`, deren Top-Level-JSON valide, aber KEIN Dict ist (z. B.
  eine Liste oder ein String), When `write_verdict` seinen Merge-Lesepfad
  durchläuft (`staging_gate.py:410`), Then wird die Datei wie eine kaputte
  Attestation behandelt und regulär überschrieben — kein `AttributeError`,
  kein Abbruch des regulären Schreibvorgangs.
  - Test: `--e2e-path` zeigt in `tmp_path` auf eine vorab per `json.dump`
    angelegte Datei mit Top-Level-Liste statt Dict; anschließender regulärer
    `--write-verdict`-Aufruf; Assertion, dass die Datei danach ein sauberes
    Dict mit den neuen Findings enthält.

- **AC-9:** Given eine Attestation-Datei, deren Dateiname exakt zum
  Ziel-Commit passt, deren Top-Level-JSON aber KEIN Dict ist, When
  `staging_gate.py --check` den Exakt-Match-Zweig durchläuft
  (`staging_gate.py:551`, aufgerufen von `deploy-gregor-prod.sh:174,210` im
  echten Prod-Deploy), Then blockiert der Gate-Check FAIL-CLOSED mit
  Exit-Code ≠ 0 und einer Meldung, die den vorgefundenen Typ nennt —
  niemals mit stillem Durchlassen (Exit 0) oder unbehandeltem Absturz.
  - Test: `_run_gate(["--check", ...])` mit `--e2e-path` auf eine
    vorbereitete Top-Level-Nicht-Dict-Datei; Assertion auf Exit-Code ≠ 0.

- **AC-10:** Given eine Attestation-Datei, deren Dateiname exakt zum
  Ziel-Commit (HEAD) passt, deren Top-Level-JSON aber KEIN Dict ist, When
  `prod_selftest.py` seinen Exakt-Match-Zweig durchläuft
  (`prod_selftest.py:689`), Then wird dies wie „kein exakter Treffer"
  behandelt, sodass die bestehende Ancestor-Suche
  (`_e2e_paths._nearest_verified_ancestor`) greift, statt mit
  `AttributeError` abzustürzen.
  - Test: wie AC-5/AC-9-Muster — exakt benannte Attestation-Datei mit
    Top-Level-Liste vorbereiten, optional einen gültigen Ancestor daneben
    anlegen; Assertion auf kein `AttributeError` und erwartetes
    Ancestor-Verhalten (PASS über Ancestor bzw. definierte Fail-Meldung,
    wenn kein Ancestor existiert).

## Invarianten / Was sich nicht ändern darf

- Alle heute grünen Fälle in `tests/tdd/test_staging_gate.py` bleiben grün:
  eine leere Findings-Liste und eine Liste ausschließlich aus Dicts sind
  weiterhin gültige Eingaben für `--write-verdict`.
- Alle heute grünen Fälle in `tests/tdd/test_staging_gate_verdict_merge.py`
  bleiben grün: der bestehende Merge/Dedup-Mechanismus für saubere
  Dict-Findings (Workflow-Tagging, Content-Dedup) ändert sich nicht.
- Bestehende, saubere Attestationen (`.claude/e2e_verified/*.json` mit
  Top-Level-Dict und ausschließlich Dict-Findings) liefern in
  `staging_gate.py --check` und `prod_selftest.py` unverändert dasselbe
  Verdict wie vor dieser Änderung.
- `_nearest_verified_ancestor()` (`_e2e_paths.py:292–359`) wird NICHT
  angefasst — ihr Guard (Z. 344) existiert bereits und bleibt Vorbild für
  die drei neu abgesicherten Stellen.

## Bestätigte Nicht-Risiken

- Stichprobe von 11 echten Attestationen im Repo: ausnahmslos saubere
  Top-Level-Dicts mit sauberen Dict-Findings. Eine strengere Eingangsprüfung
  hätte keine davon abgewiesen.
- `tests/tdd/conftest.py::_make_e2e_verified()` nutzt ebenfalls saubere
  Top-Level-Dicts mit Dict-Findings — kein bestehender Test wird durch
  diese Spec rot.

## Nicht in dieser Scheibe

- **Die real korrumpierte Datei
  `.claude/e2e_verified/1001273d00382645824a11c96855a2ed9878fc51.json` wird
  NICHT von Hand bereinigt.** Gate-State-Dateien werden nie per Hand/Bash
  verändert (Marker-Schutz). Der Fix macht die Datei harmlos (AC-4 greift
  beim nächsten regulären Schreiben desselben Commits; bis dahin verhindert
  AC-5/AC-7 einen Absturz oder ein Falsch-Grün beim Lesen). Sie bleibt
  bewusst als Live-Beleg liegen.
- **Kein Schema-Zwang auf die Feldnamen INNERHALB eines Findings oder einer
  Attestation.** Geprüft wird ausschließlich der Typ „Dict" (bzw. „Liste"
  für das Findings-Array) — keine Pflicht auf `ac`/`status`/`url`/`evidence`
  oder auf bestimmte Top-Level-Schlüssel. Ein zu strenger Feld-Zwang würde
  gültige Altbestände mit abweichenden, aber funktionierenden
  Feldkombinationen abweisen.
- **Keine Änderung an der Ancestor-Relaxierung selbst oder am übrigen
  Deploy-Block.** Der Prod-Deploy (`deploy-gregor-prod.sh:174,210`) ruft
  ausschließlich `staging_gate.py --check` auf; betroffen von dieser Spec
  ist der Exakt-Match-Zweig innerhalb von `gate_check` (AC-9) sowie die
  Nachweis-Kette bis zum Issue-Close (Schritt 4b/5, AC-2–AC-8/AC-10), nicht
  die Ancestor-Logik oder der restliche Deploy-Ablauf.
- **Randnotiz — anderer Fehlermodus, kein Teil dieser Scheibe:**
  `Path.write_text()` in `write_verdict` (Z. 449) ist nicht atomar. Bei
  echter Parallelität entstünde dadurch potenziell invalides JSON (bereits
  über den bestehenden `json.JSONDecodeError`-Fang sauber abgefangen), nicht
  valides JSON mit falschem Typ — ein anderer Fehlermodus als der hier
  behandelte.

## Test Plan

Neue Datei `tests/tdd/test_attestation_findings_typsicher.py` (Name nach
Verhalten, nicht nach Issue-Nummer). Kern-Schicht, kein Netz. Prüflinge
relativ zur Testdatei auflösen (`Path(__file__).resolve().parents[2]`,
Muster `test_prod_selftest_internal_url_skip.py` / `test_staging_gate.py`).

### Automated Tests (TDD RED)

- [ ] `test_partition_findings_splits_dicts_and_non_dicts` — AC-1: reine
      Funktion, gemischte Liste rein, korrekt getrenntes Tupel raus.
- [ ] `test_partition_findings_non_list_root_is_fully_unusable` — AC-1
      (Ergänzung): `raw` selbst kein Listentyp → alles landet in
      `unverwertbare`, `gueltige` ist leer.
- [ ] `test_write_verdict_rejects_object_instead_of_list` — AC-2: JSON-Objekt
      statt Liste, Exit ≠ 0, kein Artefakt, Meldung nennt Typ „dict".
- [ ] `test_write_verdict_rejects_list_with_bare_string_entries` — AC-3:
      reale Fehlform (6 Bare-Strings) als Liste, Exit ≠ 0, kein Artefakt.
- [ ] `test_write_verdict_merge_drops_non_dict_legacy_entries` — AC-4: Altlast
      in bestehender Attestation wird beim nächsten sauberen Schreiben
      entfernt, Anzahl auf stderr gemeldet.
- [ ] `test_prod_selftest_survives_mixed_findings_without_crash` — AC-5: kein
      Absturz, unverwertbare Einträge im Bericht sichtbar, Verdict nur aus
      gültigen Findings.
- [ ] `test_prod_selftest_survives_non_list_findings_field` — AC-6:
      `findings`-Feld selbst kein Listentyp, kein Absturz.
- [ ] `test_prod_selftest_all_unusable_findings_is_not_pass` — AC-7: reale
      Fehlform als vollständiger `findings`-Inhalt, Verdict explizit nicht
      PASS/SKIPPED_ALL, Exit-Code ≠ 0, Assertion läuft über den vollständigen
      Lauf bis `_derive_verdict`, nicht über einen künstlich vorgezogenen
      Kurzschluss.
- [ ] `test_write_verdict_merge_survives_non_dict_top_level_existing` — AC-8:
      bestehende Attestation mit Top-Level-Liste statt Dict, regulärer
      Folge-Schreibvorgang überschreibt sauber statt abzustürzen.
- [ ] `test_gate_check_fails_closed_on_non_dict_top_level` — AC-9: exakt
      benannte Attestation mit Top-Level-Nicht-Dict, `--check` liefert
      Exit-Code ≠ 0.
- [ ] `test_prod_selftest_falls_back_to_ancestor_on_non_dict_exact_match` —
      AC-10: exakt benannte Attestation mit Top-Level-Nicht-Dict, kein
      Absturz, Ancestor-Pfad greift.

## Mutations-Gegenprobe

Vier konkrete Verfälschungen, die je mindestens einen der obigen Tests rot
machen MÜSSEN (String-Ersetzung mit externer Sicherungskopie, kein
`git checkout/stash/reset`):

1. **Typprüfung auf der Schreibseite entfernen** — den neuen
   `partition_findings`-Aufruf in `write_verdict` durch die heutige Zeile
   `findings = json.loads(...)` ohne Prüfung ersetzen. Muss AC-2 und AC-3
   rot machen (Attestation würde trotz Objekt/Bare-Strings geschrieben).
2. **Partitionierung auf der Leseseite entfernen** — vor `pool.map` wieder
   direkt `findings = verified.get("findings", [])` ohne
   `partition_findings`-Aufruf verwenden. Muss AC-5 und AC-6 rot machen
   (Absturz statt Bericht-Abschnitt).
3. **„Alles unverwertbar ⇒ nicht PASS"-Regel entfernen** — die neue Regel
   weglassen, sodass ein vollständig unverwertbares `findings`-Array wie
   „leer" behandelt wird und `_derive_verdict([])` unverändert PASS mit
   Exit 0 zurückgibt. Muss AC-7 rot machen (Verdict wäre PASS statt
   explizit nicht-PASS) — UND zeigt, ob der Test den echten Pfad prüft: ein
   Test, der den Kurzschluss bei leerer Roh-Liste künstlich auslöst statt
   den vollständigen Lauf zu durchlaufen, bliebe an dieser Mutation
   fälschlich grün.
4. **Fail-closed-Guard im Gate-Check entfernen** — den neuen
   `isinstance(data, dict)`-Guard vor `staging_gate.py:551` weglassen, sodass
   `data.get(...)` bei einer Top-Level-Liste wieder mit `AttributeError`
   abstürzt (oder, falls stattdessen `data is None` genutzt würde, fälschlich
   in die Ancestor-Relaxierung des Deploy-Gates rutscht). Muss AC-9 rot
   machen.

## Known Limitations

- Method-bewusstes Proben (GET vs. POST) und Feldnamen-Schema innerhalb
  eines Findings oder einer Attestation bleiben unverändert außerhalb dieser
  Spec (siehe „Nicht in dieser Scheibe").
- Die Merge-Korrektur (AC-4) wirkt erst ab dem nächsten regulären
  `--write-verdict`-Lauf auf denselben `verified_commit`; bis dahin verlässt
  sich die Sicherheit gegen Absturz/Falsch-Grün ausschließlich auf die
  Leseseiten-Guards (AC-5/AC-6/AC-7/AC-10).
- Nicht-atomares Schreiben (`Path.write_text`) bleibt bestehen — siehe
  Randnotiz unter „Nicht in dieser Scheibe".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix an bestehenden Gate-Skripten, keine neue
  Entscheidungsfläche (kein neuer Kanal, Provider, Datenmodell oder
  Auth-Mechanismus betroffen). Die Entscheidung „hart schreiben, weich
  lesen" ist in dieser Spec begründet und braucht kein eigenes ADR.

## Changelog

- 2026-08-10: Initial spec created
- 2026-08-10: Nachtrag zweite Gegenprobe — Top-Level-Typkontrakt (AC-8/AC-9/
  AC-10), Präzisierung AC-7 auf den vollständigen Lauf/`_derive_verdict`,
  Abschnitt „Warum zentral" und „Bestätigte Nicht-Risiken" ergänzt
- 2026-08-10: Revision v1.2 — Testbeschreibungen (AC-5/AC-7, Testplan,
  Mutation 3) von „gemockt"/„mocken" auf ehrlichen Boundary-Seam-Wortlaut
  umformuliert (Mock-Theater-Verbot); LoC-Schätzung auf ~255 korrigiert
  (über dem 250-Limit — `loc_limit_override` vor Umsetzung beim PO
  einzuholen)
