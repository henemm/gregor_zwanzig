# Context: fix-1409b-pfad-waechter

Issue: [#1409](https://github.com/henemm/gregor_zwanzig/issues/1409) Punkt 4 — Lieferung B (Wächter)
Vorgänger: Lieferung A live als `e0c60d23`; Bestandsaufnahme und Klassen A/B/C in `docs/context/fix-1409-worktree-pfade.md`

## Request Summary

Ein Wächter soll verhindern, dass wieder Tests entstehen, die ihren Prüfling über den festen Hauptrepo-Pfad laden und aus einem Worktree falsches Grün melden. Er muss die bewusst festen Pfade (Klasse B) und die Nicht-Zugriffe (Klasse C) durchlassen.

## Bestand nach Lieferung A

33 Treffer in 29 Dateien: **19× Klasse B, 14× Klasse C, 0× Klasse A**. Der Ist-Stand allein kann also nur Fehlalarme messen, keine Treffsicherheit.

## Empirische Messung (2026-07-29)

Gemessen wurde gegen **drei** Korpora, weil der Ist-Stand keine Verstöße mehr enthält:

| Korpus | Inhalt | misst |
|---|---|---|
| IST (`e0c60d23`) | 33 Treffer, alle erlaubt | Fehlalarme |
| VORHER (`e0c60d23^`) | enthält die **6 echten Klasse-A-Zeilen** aus 5 Dateien | Treffsicherheit an realen Fällen |
| SYNTH | 15 konstruierte Fälle (10 Verstöße, 5 erlaubt) | Umgehungsformen |

| Kandidatenregel | VORHER gefangen | Fehlalarme (IST) | Umfang |
|---|---|---|---|
| **R1** Textliteral + `git ls-files` | 3/6 | 0 | klein |
| **R2** R1, nur AST-Codeliterale (ohne Docstrings/Kommentare) | 3/6 | 0 | +15 Z. |
| **R2j** R2 + Auflösung von `KONSTANTE / "rel/pfad"` | **6/6** | 0 | +10 Z. |
| **R2+** R2j + f-Strings, `+`-Verkettung, `os.path.join` | **6/6** (SYNTH 9/10) | 0 | ~90 Codezeilen, Laufzeit 1,9 s |
| **R4** reine Allowlist (ursprünglicher Vorschlag) | **4/6** | ~13 Fehlalarme/Monat | 33 Einträge |

## Warum die reine Allowlist ausscheidet

Drei gemessene Gründe:

1. **Strukturell blind für die Hälfte der realen Fälle.** Bei `test_issue_603` und `test_622` lautete die Trefferzeile `REPO = Path("/home/hem/gregor_zwanzig")` — ein Verzeichnis, das als Klasse B **zu Recht** in der Allowlist stünde. Der Verstoß entsteht erst in der Folgezeile (`REPO / ".claude/hooks/design_fidelity_diff.py"`) ohne eigenes Literal. Ein Textvergleich sieht ihn nie.
2. **Wartungslast, an der Historie gemessen:** 4 Treffer vor 60 Tagen → 20 vor 30 Tagen → 33 heute. Rund **13 neue, durchweg berechtigte Fundstellen pro Monat**, jede davon ein roter Testlauf bis jemand von Hand nachträgt.
3. **Sie wälzt die Einordnung auf den Editierenden ab** — und genau die ist fehleranfällig: das Ticket selbst hat `test_issue_348` (Suchmuster) und `test_issue_1004` (Fallback) fälschlich als Verstöße geführt.

## Technische Entscheidung

**R2+ mit Marker-Kommentar als Ausnahme.** Begründung:

- Falsch-negativ ist der teure Fehler (durchgelassener Verstoß = wieder falsches Grün). Nur R2j/R2+ fangen 6 von 6 realen historischen Verstößen.
- Null Fehlalarme über 33 Ist-Treffer **und** die 31 B/C-Treffer des VORHER-Korpus. Die Ausnahmeliste startet **leer**.
- **Verzeichnisliterale lösen sich von selbst:** `REPO_DIR = Path("/home/hem/gregor_zwanzig")` und `HARDCODED_PREFIX = ".../.claude/hooks"` zeigen auf kein `git ls-files`-Ziel. Das ist Konstruktion, kein Sonderfall — **Voraussetzung: kein Präfix-Vergleich gegen den Index**, sonst wären die Soll-Bild-Konstanten sofort Fehlalarm.
- **Ausnahmen als Marker-Kommentar an der Zeile** (`# gz-main-path: <Begründung>`), nicht als zentrale Liste. Die Begründung steht dort, wo sie gelesen wird — dieselbe Form, die Lieferung A für Klasse B/C etabliert hat. Kein zweiter Ort, der driften kann.
- R2 gegenüber R1 lohnt trotz 0 gemessener Ersparnis: fünf Klasse-C-Einträge sind Docstrings mit absolutem Pfad; dass keiner davon eine getrackte Datei nennt, ist Zufall der aktuellen Belegung.

**Absehbare erste Ausnahme:** git-getrackte Soll-Bilder, die bewusst aus dem Hauptrepo kommen (`SOLL_DIR = MAIN_REPO / "claude-code-handoff/current/soll"`, begründet in `test_issue_603:39-42`). Heute entgehen sie der Regel nur, weil der Dateiname per f-String entsteht — schreibt jemand ihn wörtlich, kostet das eine Kommentarzeile.

## Was der Wächter ausdrücklich nicht fängt

1. **Tote Pfade** (Ziel existiert nirgends) — der `test_ac3`-Fall aus Lieferung A. „Nicht getrackt" ist von „gibt es nicht" nicht unterscheidbar. Ein Zusatzcheck wäre möglich (~5 Zeilen, 0 Fehlalarme heute), prüft aber **Hostzustand statt Code** und schlüge auf einem Host ohne `.env` oder ohne gebautes `gregor-api` falsch an. Bewusst **nicht** aufgenommen.
2. Zur Laufzeit gebaute Pfade (`os.environ`, Funktionsrückgaben) — statisch nicht auflösbar.
3. Ziele, die noch nicht `git add`-et sind.
4. Alles außerhalb `tests/` und alles unter `/home/hem/gregor_zwanzig_staging/`.
5. Prüflinge, die **selbst** hart verdrahtet sind (`prod_selftest.py:56`) — das repariert keine Testpfadwahl.

## Scope Assessment

- Neue Datei: `tests/tdd/test_repo_path_hardcoding_ratchet.py`, ~90 Codezeilen, Laufzeit ~2 s
- Sparvariante ohne `os.path.join`/`+`-Verkettung: ~70 Codezeilen, VORHER weiterhin 6/6 (beide Formen kommen im Bestand nirgends vor). Die **Konstantenauflösung des `/`-Joins ist nicht verhandelbar** — sie trägt die Hälfte der Trefferquote.
- Risiko: niedrig. Kein Produktivcode, keine Änderung an bestehenden Tests.

## Regel-Budget

Ersetzt keine bestehende Regel → **Prüfdatum 2026-10-27** (+90 Tage) in der Datei, Vorbild `test_naming_gate.py`. Keine Überschneidung mit der #1402/#1405-Wächterserie: jene bewacht Laufzeitverhalten der Anwendung (stilles Verschlucken), diese die Testinfrastruktur.

## Open Questions

Keine offen.
