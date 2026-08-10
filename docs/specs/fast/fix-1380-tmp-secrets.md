# Mini-Spec: #1380 — Klartext-Zugangsdaten aus /tmp entfernen

- **Issue:** #1380
- **Track:** Fast Track
- **created:** 2026-08-10

## Ausgangslage (gemessen, nicht angenommen)

Scan aller 275.159 Dateien unter `/tmp` gegen die 17 aktuell gültigen Geheimwerte aus
`gregor_zwanzig/.env`, `gregor_zwanzig_staging/.env` und `.claude/validator.env`:

- 15 der 17 Werte haben Klartext-Treffer, insgesamt ~248 Dateien, davon **105 weltlesbar**
- **75 davon entstanden nach dem 2026-07-25**, also nachdem `secret_egress_guard.py` scharf war
- `/tmp/claude-1000` steht auf `700 hem:hem`; Gegentest als `claude-security`: *Permission denied*.
  Damit sind 99 der 105 Dateien für andere Serverbenutzer **nicht** erreichbar.
- **Real erreichbar sind 6 Dateien direkt unter `/tmp`** (fünf pytest-Logs vom 02./04.08.,
  eine Validator-Belegdatei vom 07.06.)

Ursache des jüngsten Zuwachses: fehlschlagende Tests drucken `os.environ`-Diffs mit Klartextwerten
(`tests/tdd/test_issue_1014_live_optin.py:89`), und der Testlauf wird nach `/tmp` statt ins
Sitzungs-Scratchpad umgeleitet. Der Guard prüft Tool-**Inputs** und kann Prozess-**Ausgaben**
konstruktionsbedingt nicht sehen.

## Was ändert sich

- Die 6 weltlesbaren Fundstellen direkt unter `/tmp` werden **gelöscht**
- Der Altbestand im Sitzungsordner (99 Dateien) wird **gelöscht**, soweit er nicht zu einer
  laufenden Sitzung gehört
- Ein Nachweis (Pfad, Datum, betroffene Schlüsselnamen — **niemals Werte**) wird als
  Issue-Kommentar in #1380 abgelegt; #1380 wird geschlossen
- #1635 erhält einen Kommentar, der die dortige Einordnung „kein aktiver Vorfall" mit den
  gemessenen Zahlen korrigiert — die Prävention bleibt fachlich dort

## Was darf sich nicht ändern

- **Keine Rotation** von Zugangsdaten (PO-Entscheidung 2026-08-10, wie schon 2026-07-25)
- **Kein Anfassen der Arbeitsordner laufender Claude-Sitzungen** — Löschkandidaten werden gegen
  die Sitzungs-UUIDs laufender Prozesse gefiltert
- Kein Produktivcode, keine Gates, keine Hooks werden in diesem Workflow geändert
- Kein Geheimwert erscheint in Ausgabe, Nachweis, Commit-Text oder Issue-Kommentar
- `/tmp/claude-1000` bleibt auf `700`

## Acceptance Criteria

**AC-1:** Gegeben ein erneuter Scan aller Dateien direkt unter `/tmp` gegen die 17 aktuell
gültigen Geheimwerte, wenn dieser nach der Aufräumaktion läuft, dann meldet er dort **null**
Treffer — weder weltlesbar noch gesperrt.

**AC-2:** Gegeben der Altbestand im Sitzungsordner `/tmp/claude-1000`, wenn die Aufräumaktion
gelaufen ist, dann sind alle Fundstellen gelöscht **außer** denen, die zu einer zum Zeitpunkt
der Aktion laufenden Claude-Sitzung gehören; die verbliebenen werden namentlich benannt.

**AC-3:** Gegeben der Nachweis, der in #1380 dokumentiert wird, wenn man ihn gegen die 17
Geheimwerte prüft, dann enthält er **keinen einzigen** Klartextwert, sondern ausschließlich
Schlüsselnamen, Pfade, Zeitstempel und Zähler.

**AC-4:** Gegeben Issue #1635, wenn dieser Workflow abgeschlossen ist, dann trägt es einen
Kommentar mit den gemessenen Zahlen, der die dortige Aussage „kein aktiver Vorfall" richtigstellt
und den Entstehungskanal (Prozessausgabe statt Tool-Input) benennt.

## Manuelle Test-Schritte

1. `python3 scan_tmp_leaks.py` erneut laufen lassen → Abschnitt „TREFFER" enthält keine Datei
   direkt unter `/tmp` (AC-1)
2. Verbliebene Treffer im Sitzungsordner gegen die Liste laufender Sitzungs-UUIDs halten (AC-2)
3. Den vorbereiteten Issue-Kommentar gegen die 17 Werte greppen → 0 Treffer (AC-3)
4. `stat -c '%a' /tmp/claude-1000` → `700` (unverändert)

## Inline-Test

- [ ] Nachweis-Datei wird vor dem Posten maschinell gegen alle 17 Geheimwerte geprüft (AC-3);
      ein absichtlich eingefügter Testwert muss dabei erkannt werden — sonst prüft der Test nichts

## Ausdrücklich NICHT in diesem Workflow

- Prävention gegen künftige Laufzeit-Lecks → **#1635**
- Maskierung von `os.environ`-Diffs in Testausgaben → **#1535** (bereits umgesetzt, PR #1674)
- Umleitung von Testläufen nach `/tmp` statt ins Scratchpad → offen, kein eigenes Ticket
