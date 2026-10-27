# ADR-0100: Regel-Budget — jede neue Pflicht-Regel ersetzt eine bestehende oder trägt ein Prüfdatum (+90 Tage)

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — PO-go 2026-07-09, Commit `ad637d57c`)
- **Datum:** 2026-10-21
- **Bezug:** CLAUDE.md §„Backlog & Nebenbefunde" (Absatz „Regel-Budget"), `docs/analysis/backlog-spirale-2026-07.md` (Fix R4), `docs/reference/gates_und_ratschen.md` §„Regel-Budget: Prüfdaten im Überblick", Gate-Audit #1197

## Kontext

Die Tiefenanalyse vom 2026-07-09 (`backlog-spirale-2026-07.md`, Anlass „jeder gelöste Issue erzeugt
drei neue", Datenbasis 1182 Issues und 2114 Workflow-Logs) fand mehrere selbstverstärkende
Schleifen. Eine davon: Regeln, Gates und Pflicht-Validatoren kamen hinzu, wurden aber nie wieder
abgebaut. Die Analyse setzte vier Fixes R1–R4; R4 ist das Regel-Budget.

## Entscheidung

1. Jede neue Pflicht-Regel, jedes neue Gate und jeder neue Pflicht-Validator **ersetzt beim
   Einführen eine bestehende Regel** oder **trägt ein Prüfdatum (+90 Tage)**.
2. Am Prüfdatum gilt: kein nachweisbarer Fang → Rückbau. Verlängerungen sind möglich, wenn sie
   belegt sind (Beispiel: `tests/test_adr_index_drift.py`, verlängert 2026-10-21 durch den PO, weil
   der Doku-Audit reale Drift fand).
3. Die Prüfdaten stehen gesammelt in `docs/reference/gates_und_ratschen.md` §„Regel-Budget:
   Prüfdaten im Überblick", mit Fang-Beleg bei Einführung. Gates tragen ihr Prüfdatum zusätzlich im
   Code (z. B. `PRUEFDATUM` in `.claude/hooks/pendant_gate.py`).

## Verworfene Alternativen

- **Regeln ohne Ablauf:** verworfen — genau das ist die Schleife, die die Analyse belegt.
- **Feste Obergrenze der Regelzahl:** nicht beschlossen; das Budget wirkt über Ersatz oder
  Fang-Nachweis.

## Konsequenzen

- **Positiv:** Wächter, die nichts fangen, verschwinden wieder; Falsch-Blockierungen werden nicht
  zum Dauerzustand.
- **Negativ / Preis:** Jedes Prüfdatum braucht einen Audit-Termin (#1197) und einen Fang-Nachweis.
- **Folgepflichten:** Neue Regeln tragen das Prüfdatum sichtbar an der Regel und in der
  Prüfdaten-Tabelle.
