# Adversary Dialog — feat-3323-servermessung
Spec: docs/specs/modules/testsuite_servermessung_parallel.md
Datum: 2026-11-27 15:54

## Checkliste
- [x] **Input:** Server-Worktree auf einem Commit; die zwei wörtlichen Gate-Formen; laufendes Prod und Staging.
- [x] **Output:** Messprotokoll mit beiden Läufen und Referenzdoku mit gemessenen Laufzeiten.
- [x] **Side effects:** Zusätzliche Last auf dem Server während ca. 1,5 h (parallele Form unter `nice -n 10`); keine Änderung an Prod-Daten oder Prod-Checkout.
- [x] **AC-1:** Given ein Abschlusslauf auf dem Server, auf demselben Commit wie die serielle Baseline und neben laufendem Prod und Staging / When die parallele Form einmal vollständig läuft und währenddessen `prod_selftest.py` ausgeführt wird / Then ist die Laufzeit kleiner als seriell auf demselben Commit und Server (Referenz 56:17 min vom 2026-11-22, anderer Commit)
- [x] **AC-2:** Given beide Läufe auf demselben Commit / When die roten Tests je Lauf ausgewertet werden / Then gibt es keine zusätzlichen roten Tests gegenüber der seriellen Baseline auf demselben Commit
- [x] **AC-3:** Given der parallele Lauf auf dem Server / When er läuft / Then sind Spitzen-RSS und CPU gemessen und protokolliert
- [x] **AC-4:** Given der parallele Lauf läuft neben Prod / When `prod_selftest.py` währenddessen ausgeführt wird / Then ist der Prod-Selftest während des Laufs grün (Exit 0)
- [x] **AC-5:** Given die Messung ist geplant / When die Läufe ausgeführt werden / Then laufen beide in einem eigenen Server-Worktree (nie im Prod-Checkout), streng nacheinander und mit den wörtlichen Gate-Formen aus der Referenzdoku
- [x] **AC-6:** Given der parallele Lauf mit Controller und zwei Workern / When der Speicherbedarf bestimmt wird / Then ist die Spitzen-RSS als Summe Controller plus Worker per Abtastung protokolliert, nicht nur das Max-RSS eines einzelnen Prozesses
- [x] **AC-7:** Given der Lauf läuft / When `MemAvailable` unter 1 GB fällt / Then wird der Lauf abgebrochen und als gescheitert (Speicher) protokolliert
- [x] **AC-8:** Given die Messung ist ausgewertet / When sie scheitert (nicht schneller, zusätzliche rote Tests, Selftest rot oder Speicherabbruch) / Then wird ein Folge-Issue zur Neubewertung (Rücknahme oder andere Worker-Zahl, Gate-Adversary 2 Runden) angelegt und #3278 bleibt offen; bei Erfolg kann #3278 geschlossen werden
- [x] **AC-9:** Given die Messung ist abgeschlossen / When die Referenzdoku gelesen wird / Then nennt `docs/reference/gates_und_ratschen.md` die gemessenen Laufzeiten beider Formen mit Datum und Commit und enthält keinen Satz „noch nicht gemessen (#3323)" mehr

## Dialog

### Runde 1
**Adversary:** Beleg je Punkt aus Rohdaten, nicht aus dem Protokolltext. Nachgerechnet:
- Laufzeit: `rohdaten/seriell-time.txt` 35:04.00, `rohdaten/parallel-time.txt` 20:48.25; parallel < seriell. CPU 64 % / 116 % entspricht (user+sys)/wall (1363/2104; 1453/1248).
- Summen-RSS-Maximum aus den TSV (awk): seriell 1459300 kB um 14:21:39, parallel 2210992 kB um 14:50:05 (max. 13 Prozesse); min. MemAvailable seriell 3244016 kB, parallel 2152692 kB um 14:42:43. Alle Protokollwerte stimmen; Max-RSS time -v 1012096 / 830520 kB getrennt ausgewiesen (AC-3, AC-6; Abtastintervall 10 s im Rahmen).
- Rote: `diff parallel-rote.txt seriell-rote.txt` leer, je 17; Resümee-Zeilen beider `*-zusammenfassung.txt` zeigen 17 failed, 26207 passed (AC-2).
- `ablauf.log`: ein COMMIT cf1a2db0d127b0e4b30696e0473cfd9410aa4eeb vor beiden Läufen; ENDE seriell 14:29:30 = START parallel 14:29:30 (streng nacheinander, AC-5); Selftest parallel-10min 14:39:31 liegt zwischen START parallel 14:29:30 und ENDE parallel 14:50:25, exit=0 (AC-4); Kontrollen vorher/nachher exit=0. Commit cf1a2db0d ist Vorfahr von origin/main, CI-Run 46006708021 für exakt diesen SHA `success` (gh).
- Befehle: beide Gate-Literale aus `docs/reference/gates_und_ratschen.md:260` und der Parallelzeile sind per Python-Teilstring-Test Zeichen für Zeichen in `messen.sh`, `ablauf.log` und beiden `*-time.txt` enthalten (AC-5).
- AC-9: `docs/reference/gates_und_ratschen.md:276` nennt Datum, Commit, 35:04/20:48; der Offen-Vermerk ist weg.
- Angriffspunkte: (a) `selftest-parallel-10min.txt` zeigt, dass prod_selftest einen Bericht nach `/home/hem/gregor_zwanzig/docs/artifacts/unknown/prod-selftest.md` schreibt, das Protokoll nennt den Aufruf "rein lesend" und die Spec fordert "keine Änderung am Prod-Checkout" (F001). (b) 38 skipped seriell vs. 37 parallel, im Protokoll nicht erklärt (F003). (c) nur ein Selftest während des Laufs (F005).
**Implementierer:** (nicht beteiligt, Messauftrag; Protokoll und Rohdaten sind die Antwort.)

### Runde 2
**Adversary:** AC-7 Gegenprobe: Sampler-Logik (Schwelle 1048576, `kill -TERM -- "-$pg"`, Protokollzeile, Abbruch-Datei) lokal mit Dummy-Prozessgruppe (setsid, zwei `sleep 300`) und Datei statt /proc/meminfo nachgestellt (Scratchpad `ap/sim.sh`): Bei 900000 kB wurde `ABBRUCH dummy: MemAvailable 900000 kB < 1 GB` geloggt, Datei `dummy-abbruch` geschrieben, Gruppe beendet (rc=143, keine Reste). Mechanik plausibel; real nie ausgelöst (min. 2,05 GB), Abtastung 10 s erfasst kurze Spitzen nicht (Messgrenze, hier unkritisch). Schwäche: nach Abbruch läuft `messen.sh` weiter (nächster Lauf, Selftest), und die Protokollzeile heißt "ABBRUCH", nicht wörtlich "gescheitert (Speicher)" (F002).
Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, danach per cmp wiederhergestellt und grün): rot wurden: Offen-Vermerk zurück; Laufzeitformat (mm:ss min) entfernt; Pflichtwort RSS bzw. Rote im Protokoll entfernt; alle Hex-Hashes im Protokoll entfernt. Unentdeckt: falsche Laufzeit in der Doku (99:48), Commit oder Datum aus der Doku entfernt, vollen Commit-Hash im Protokoll ersetzt (die CI-Job-ID mit 12 Ziffern erfüllt die Hex-Regex), Laufzeit parallel > seriell im Protokoll, Verdict BESTANDEN->GESCHEITERT, Selftest-Zeile auf Exit 1 (F004). Bei einem Messauftrag tragbar: Spec-Test-Plan verlangt nur Existenz und Abwesenheit des Satzes; Inhaltsrichtigkeit belegt dieser Adversary-Abgleich gegen die Rohdaten, kein Produktverhalten hängt daran.
Findings:
- Finding:
  ID: F001
  Severity: MEDIUM
  Category: spec_violation
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/selftest-parallel-10min.txt:3
  Description/Conflict/Remediation: und messprotokoll.md:78. prod_selftest legt im Prod-Checkout einen Bericht an; Protokoll behauptet "rein lesend". Spec Side effects: keine Änderung am Prod-Checkout. Konflikt: unwahre Aussage, Datei ist untracked, kein Datenschaden. Remediation: Satz im Protokoll korrigieren (Bericht unter docs/artifacts/unknown/ im Prod-Checkout), Datei auf dem Server prüfen/entfernen oder nächstes Mal `--workflow` setzen.
- Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh:18
  Description/Conflict/Remediation: Abbruch beendet nur den Lauf, das Skript fährt fort; Protokollzeile nennt nicht "gescheitert (Speicher)". Wirkung nur im nie eingetretenen Fall.
- Finding:
  ID: F003
  Severity: LOW
  Category: edge_case
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/parallel-zusammenfassung.txt:9
  Description/Conflict/Remediation: vs seriell-zusammenfassung.txt:9. 38 vs 37 skipped, 708 deselected nur seriell (xdist-Eigenheit); passed und rote Menge identisch, Differenz nicht erklärt. Kein AC betroffen.
- Finding:
  ID: F004
  Severity: LOW
  Category: anti_pattern
  Code reference: tests/test_servermessung_doku.py:26
  Description/Conflict/Remediation: Doc-Test fängt die oben genannten Mutationen nicht; Hex-Regex matcht auch reine Ziffernfolgen. Remediation optional: Commit-Hash gegen ablauf.log prüfen, Datum und Commit im Referenzabschnitt fordern (AC-9).
- Finding:
  ID: F005
  Severity: LOW
  Category: spec_violation
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/ablauf.log:6
  Description/Conflict/Remediation: Nur ein Selftest im Lauf (10 min), Spec sah zusätzlich "kurz vor Ende" vor; Protokoll begründet (25-min-Termin nach Laufende). AC-4 ("währenddessen", exit 0) erfüllt.
**Implementierer:** (nicht beteiligt.)

Confirmations:
- AC-1 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/parallel-time.txt:5 (20:48.25) vs seriell-time.txt:5 (35:04.00), gleicher Commit laut ablauf.log:1.
- AC-2 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/parallel-rote.txt:1 (diff gegen seriell-rote.txt leer, 17 = 17).
- AC-3 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/parallel-abtastung.tsv:1 (RSS, CPU time -v in parallel-time.txt:6,11).
- AC-4 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/selftest.log:2 (14:39:31 exit=0, innerhalb 14:29:30 bis 14:50:25).
- AC-5 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh:44 (Literale identisch mit docs/reference/gates_und_ratschen.md:260; eigener Worktree messung-3323 laut zusammenfassung-Pfaden).
- AC-6 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh:13 (ps -g Summe je 10 s; Max 2210992 kB).
- AC-7 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh:18 (Schwelle 1048576, kill -TERM Gruppe, Log); lokale Gegenprobe ausgelöst, real min. 2152692 kB.
- AC-8 CONFIRMED.
  Code reference: docs/artifacts/feat-3323-servermessung/messprotokoll.md:6 (Verdict BESTANDEN, kein Folge-Issue nötig, Erfolgspfad).
- AC-9 CONFIRMED.
  Code reference: docs/reference/gates_und_ratschen.md:276
- Weitere Prüfgegenstände (Abdeckung)
  Code reference: docs/artifacts/feat-3323-servermessung/messprotokoll.md:1
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/ablauf.log:1
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/seriell-abtastung.tsv:1
  Code reference: docs/artifacts/feat-3323-servermessung/rohdaten/selftest-parallel-10min.txt:1
  Code reference: tests/test_servermessung_doku.py:21

### Runde 3 (Nachprüfung nach Korrektur)
**Adversary:** `messprotokoll.md:78` nennt jetzt den Bericht `docs/artifacts/unknown/prod-selftest.md` im Prod-Checkout (git-ignoriert) statt "rein lesend"; das deckt sich mit `selftest-parallel-10min.txt:3` (Berichtspfad). Die Ignore-Eigenschaft und das Ordneralter sind Serverfakten des Koordinators, von mir ohne ssh nicht prüfbar; die Aussage ist nun nicht mehr falsch. F001 behoben. `messprotokoll.md:42` ergänzt den Skip-Unterschied 38 vs 37 (passt zu den Resümees `seriell-zusammenfassung.txt:8` / `parallel-zusammenfassung.txt:8`); Ursache nicht benannt, aber als nicht rot/grün-relevant eingeordnet, kein AC betroffen. F003 behoben (Einordnung genügt). Weitere Änderungen am Protokoll: keine; Zahlen unverändert. `uv run pytest tests/test_servermessung_doku.py -q`: Exit 0.
Status: F001 behoben, F003 behoben; F002, F004, F005 bleiben LOW und offen.
**Implementierer:** Korrektur eingearbeitet.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`). Kein Produktcode, keine Schreibstellen zu prüfen.

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Alle Zahlen des Protokolls stimmen mit den Rohdaten überein; 12/12 Punkte belegt. Findings F001 (MEDIUM, Protokollsatz "rein lesend" falsch korrigieren) und F002 bis F005 (LOW) blockieren das Ergebnis nicht.
Tests: 2 passed, 0 failed, 0 übersprungen (tests/test_servermessung_doku.py)
Mutationen: 6 von 11 gefangen, 5 unentdeckt (F004, für Messauftrag tragbar); Originale wiederhergestellt, grün.
Regressions: None found
Checklist: 12/12 points proven

## Geprüfte Dateien

- sha256:2fc90d4c436ab7d287d384c91686d37c52f7750916a755872e2084aabd0c4e05  docs/artifacts/feat-3323-servermessung/messprotokoll.md
- sha256:d050e50f712ff90d52fe38f3664eea91a50fb3ad57f68ccd67a6a185cb8c96e7  docs/artifacts/feat-3323-servermessung/rohdaten/ablauf.log
- sha256:a9a4730261445fd2f4ff51d6bc77c240ce28707f27ca4fc16fbb2dcee1699fc4  docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh
- sha256:16af9daf0ba7ebd86a325446c49c84cd42e9a6eda99d2b957a842c103c4e8a1a  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-abtastung.tsv
- sha256:eb13e018593e4ab24c8c24a24577ebe4069d4e9862167e5bacbafd602771a6bb  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-rote.txt
- sha256:423aeecfe21b33848ffcc2006d69d999200dd75721ce83b79adcb1125f0cd836  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-time.txt
- sha256:1892d10e591cd9e943ca979d4ac89d9107a3418cc952838cabca43c88ed8bf6d  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-zusammenfassung.txt
- sha256:255d0ab2fe5e759d8ae9fb06cef0ee1a006d9c311fd27ca1a153d45f844adf60  docs/artifacts/feat-3323-servermessung/rohdaten/selftest-parallel-10min.txt
- sha256:56f2e033170e1430a43812e31afc5361b4c7e4f7fe44e426b33f647b2209cab6  docs/artifacts/feat-3323-servermessung/rohdaten/selftest.log
- sha256:1925a555eab9658bfea496cbf0648a8433efd412e691d380cc42021c4e599574  docs/artifacts/feat-3323-servermessung/rohdaten/seriell-abtastung.tsv
- sha256:62942886ce9e6e8019830c71fe4c0d0fc937583e72e6162ac271e7599d89c3ba  docs/reference/gates_und_ratschen.md
- sha256:b68b494070dc27b10dcfa14b8163454e37ab462d55428fd82a927ea503806053  tests/test_servermessung_doku.py

## Prüfbasis

- base: 6f3db675db98d12d0db3f6c9dcd7d440f8afd44d
- blob:c69448cb11973b6ee649440ac2fdbec9ae46823f  docs/artifacts/feat-3323-servermessung/messprotokoll.md
- blob:a887d6765584ca6496d03160d4c5fd47119d7a07  docs/artifacts/feat-3323-servermessung/rohdaten/ablauf.log
- blob:791cb7899a9015282b2f0153755204c7540f6620  docs/artifacts/feat-3323-servermessung/rohdaten/messen.sh
- blob:189d9501a5650e529fb0fc8edd2885bfad9dda20  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-abtastung.tsv
- blob:271fb753b5e27131f7ec41a1c27c907a1af749b3  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-rote.txt
- blob:174fabbe3cb9337f341e40cfba2df9a17cffabbf  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-time.txt
- blob:2265e6ef284ae47b65876cfb27ddae6407aa9cfc  docs/artifacts/feat-3323-servermessung/rohdaten/parallel-zusammenfassung.txt
- blob:fc2c6cc15dd7f064e1738b94018329b287515336  docs/artifacts/feat-3323-servermessung/rohdaten/selftest-parallel-10min.txt
- blob:a4ce5aa52bdcc43a32104d9aae6e41a9165dbad0  docs/artifacts/feat-3323-servermessung/rohdaten/selftest.log
- blob:2419f4c8ec827ca0c8ee2193c937aa6a35676f28  docs/artifacts/feat-3323-servermessung/rohdaten/seriell-abtastung.tsv
- blob:9f3bec46f6a97054458558f0cf06b25085f07cf5  docs/reference/gates_und_ratschen.md
- blob:5c066297c2bc8e49c388ee49fe78fce03d21ce62  tests/test_servermessung_doku.py
