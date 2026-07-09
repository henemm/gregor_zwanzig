# Backlog-Spirale: Tiefenanalyse und Struktur-Fix (2026-07-09)

**Anlass:** PO-Beobachtung „jeder gelöste Issue erzeugt drei neue". Datenbasis: alle 1182 Issues
(GitHub-API, Stand 2026-07-09), 2114 Workflow-Logs, Testkorpus, Gate-Tooling.

## 1. Befund in Zahlen

| Messgröße | Wert | Bedeutung |
|---|---|---|
| Issues gesamt (seit 2026-04) | 1182 in ~3,5 Monaten (~12/Tag) | Fließband, kein Backlog im klassischen Sinn |
| Juli (9 Tage) | 257 neu, netto +63 | Erzeugungsrate steigt schneller als Schließrate |
| Folge-/Nebenbefund-Issues | 36 % aller Issues; 57 % der (vor Triage) offenen | Die Spirale ist eingebaut, nicht zufällig |
| Prüf-Maschinerie-Issues | ~1/3 der offenen | Tests/Gates/Validatoren erzeugen eigene Arbeit |
| Workflow-Typen Juli | 81 fix vs. ~20 feature | ~80 % der Tokens fließen in Fehlerbehebung |
| Issues <24 h geschlossen | 68 % | Kleinst-Issues: Prozess-Overhead > Nutzarbeit |
| Testcode | 126k LoC (Produkt: 132k LoC) | Zweites Produkt ohne Pflegekonzept |
| Issue-benannte Testdateien | 262 von 374 in tests/tdd/ | Append-only-Archiv statt kuratierter Suite |
| Vollsuite-Zustand | 42 dauerrot (#984), Massenfehlschläge (#1180), hängt (#1157) | Kein verlässliches Regressionssignal mehr |

## 2. Der Kern: vier sich selbst verstärkende Schleifen — und keine bremsende

Die Einzelphänomene (kaputte Tests, Gate-Bugs, Issue-Flut) sind Symptome von vier
Rückkopplungsschleifen. Jede war einzeln eine rationale Reaktion auf einen echten Vorfall;
ihre Summe ist die Spirale.

**R1 — Nebenbefund-Schleife.** Regel „IMMER Folge-Issue für Nebenbefunde" + Adversary-Pflicht
pro Workflow ⇒ jeder Workflow produziert 1–3 neue Issues, unabhängig davon, ob sie je Wert
stiften. Jedes dieser Issues durchläuft wieder einen Workflow mit Adversary ⇒ neue Nebenbefunde.
36 % aller Issues entstanden so.

**R2 — Flaky-Test-Schleife.** „Keine Mocks" in Absolutform ⇒ Tests hängen an Live-Diensten
(Staging-IMAP, Wetter-APIs, Radar-Lagen, Tages-Sendelimits) ⇒ Tests scheitern wetter-,
reihenfolge- und limitabhängig ⇒ jeder Fehlschlag wird pflichtgemäß als Issue erfasst
(z. B. #1118 warnlagenabhängig, #1167 Tageslimit, #1187 Radar-Box, #1189 Send-Gate) ⇒ mehr
Issues, aber kein besseres Signal. Gleichzeitig: Ein Test pro Issue-Nummer, nie konsolidiert,
nie gelöscht ⇒ bei jeder Produktänderung veralten Dutzende Tests gleichzeitig ⇒
„Test veraltet"-Issues (#1139, #1183, #1193 …).

**R3 — Gate-Bug-Schleife.** Die Prüf-Maschinerie (~7,5k LoC lokale Hooks + Plugin) ist selbst
Software ⇒ hat selbst Bugs (#1031, #1112, #1137, #1163) ⇒ erzeugt Issues UND blockiert
fälschlich Feature-Arbeit ⇒ Umgehungen/Nacharbeiten ⇒ neue Regeln (siehe R4).

**R4 — Regel-Ratsche.** Nach jeder Panne kommt eine neue Regel/ein neues Gate dazu; es gibt
keinen Mechanismus, der je eine Regel entfernt. Empirischer Beleg für Überdimensionierung:
Der ADR-Guard war seit der Plugin-Migration wochenlang komplett inaktiv (#1164) — und
niemand hat einen Unterschied bemerkt.

**Die fehlende bremsende Schleife:** Nirgends im System gibt es „wird nicht gemacht",
Verfallsdaten, Lösch-Regeln oder Kosten-Nutzen-Triage. Ein System, das nur addieren kann,
wird monoton teurer — unabhängig davon, wie gut jede einzelne Regel ist.

## 3. Struktur-Fix (PO-go 2026-07-09)

Jede Maßnahme adressiert genau eine Schleife. Umgesetzt in CLAUDE.md (Abschnitte
„Test-Politik: Zwei Schichten", „Nebenbefund-Triage", „Regel-Budget") und auf GitHub.

| Schleife | Fix | Mechanik |
|---|---|---|
| R1 | **Nebenbefund-Triage** | Eigenes Issue nur bei (a) nutzersichtbarem Fehlverhalten, (b) Datenverlust-/Sicherheitsrisiko, (c) fälschlich blockierendem Gate. Rest → Sammel-Issue #1199, Verfall nach 30 Tagen ohne PO-Bestätigung. |
| R2 | **Zwei-Schichten-Tests** | Deterministischer Kern (ohne Netz, echte aufgezeichnete Fixtures, MUSS 100 % grün — fixen oder löschen) + Live-E2E-Schicht (nur bei Deploy; Flake → Retry, kein Issue). Neue Tests nach Verhalten benannt, nicht nach Issue-Nummer. Bestandssanierung: #1196 (23 gebündelte Issues). |
| R3 | **Gate-Audit** | Pro Gate: Fang-Nachweis der letzten 30 Tage oder Rückbau. Falsch-blockierend schlägt falsch-durchlassend. Bestand: #1197 (9 gebündelte Issues). |
| R4 | **Regel-Budget** | Jede neue Pflicht-Regel ersetzt eine bestehende ODER trägt Prüfdatum (+90 Tage); ohne Fang bis dahin → Rückbau. |

Zusätzlich einmalig: Backlog-Entschuldung 94 → 46 offene Issues (19 geschlossen als
erledigt/Duplikat/wird-nicht-gemacht, 35 in #1196/#1197/#1198 gebündelt, 1 → henemm-infra#112).

## 4. Was bewusst NICHT geändert wurde

- **Adversary-Verifikation bleibt** — sie findet echte Fehler; nur ihre LOW-/kosmetischen
  Findings werden jetzt Sammel-Einträge statt Issues.
- **Live-E2E gegen Staging bleibt Pflicht vor Prod** — die Zweischicht-Politik verschiebt nur,
  WANN Live-Tests laufen, nicht OB.
- **Mail-Validatoren bleiben** — sie haben nachweislich echte Regressionen gefangen; ihre
  bekannten Fehlklassifikationen sind Teil des Gate-Audits #1197.
- **Gate-Code selbst** wird hier nicht angefasst (Konvention „Validator-Änderungen = eigener
  Workflow" gilt weiter); dieses Dokument ändert nur Prozessregeln.

## 5. Erfolgsmessung

Monatlich (1 Kommando-Satz, vgl. Triage-Session 2026-07-09):

1. **Erzeugungsrate:** neue Issues/Monat, davon Anteil Nebenbefund-Herkunft (Ziel: < 20 %).
2. **Arbeitsmix:** fix- vs. feature-Workflows in `.claude/workflows/_log/` (Ziel: Features ≥ 50 %).
3. **Suite-Gesundheit:** Standard-`uv run pytest` Exit 0, 0 rote Kern-Tests, hängt nicht.
4. **Backlog-Niveau:** offene Issues (Ziel: stabil < 50, ohne Bündel-Tricks).

Wenn nach 6 Wochen (Mitte August 2026) der Arbeitsmix nicht kippt, ist die nächste Eskalation
der Rückbau weiterer Gates aus #1197 — nicht neue Regeln.
