---
entity_id: konzept_1514_metrik_ausgabeorte
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [konzept, doku, metric-catalog, output-channels, po-decision]
---

<!-- Issue #1514 (triage:po) — Konzept: zentrale Übersicht der Metrik-Ausgabeorte je Kanal -->

# Konzept 1514 — Metrik-Ausgabeorte je Kanal

## Approval

- [ ] Approved

## Purpose

Ein Referenzdokument schaffen, das für jede Weather-Metrik/jedes Signal beantwortet:
„An welchen benannten Stellen, in welchen Kanälen, in welcher Form, in welcher
Reihenfolge erscheint sie — und welcher Test bewacht das?" Anlass ist #1475
(Hagel): drei Recherche-Runden waren nötig, um 12 Ausgabeorte zu finden, und
S5a ging mit nur 4 von 12 live, ohne dass Adversary oder Entwickler-Report es
bemerkten. Dieser Workflow liefert ausschließlich die Analyse/das Dokument —
kein Produktivcode, keine neuen Gates.

## Source

- **File:** `docs/reference/metric_output_matrix.md` (NEU, reines Dokument)
- **Identifier:** kein Code-Symbol — Liefer-Artefakt ist Dokumentation

> **Schicht-Hinweis:** Dieser Workflow berührt keine Schicht (Frontend/Go-API/
> Python-Core). Er dokumentiert Ausgabeorte über alle drei Schichten hinweg,
> ändert aber keine davon.

## Estimated Scope

- **LoC:** ~250–400 Zeilen Markdown (zählt nicht ins LoC-Limit: `docs/`)
- **Files:** 1 neu (`docs/reference/metric_output_matrix.md`); `docs/context/konzept-1514-metrik-ausgabeorte.md` bleibt unverändert (bereits vom Explore-/Plan-Agent befüllt)
- **Effort:** medium (Recherche liegt vollständig im Kontext vor; Aufwand liegt in Redaktion, Strukturierung und der PO-Entscheidungsvorlage)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/konzept-1514-metrik-ausgabeorte.md` | Doku | Vollständige Recherche- und Analyse-Grundlage (Datei:Zeile-Belege, strategische Bewertung) — primäre Quelle für das neue Dokument |
| `tests/tdd/test_channel_metric_matrix.py` (#1677 B) | Test | Einziger bestehender Matrix-Wächter — Ankerpunkt für die Anti-Veraltungs-Mechanik und die Folge-Scheiben-Empfehlung |
| `src/app/metric_catalog.py` | Code | SSoT `MetricDefinition`, 26 Metriken, 44 Nicht-Test-Konsumenten — Grundlage der Metrik×Kanal-Landschaft |
| `docs/features/gewitter-gesamtkonzept.md` §8 | Doku | Vorbild für Ort-Tabelle mit Fundstelle (metrikspezifisch) |
| `docs/reference/sms_format.md` | Doku | Vorbild für gepflegtes Register-Format (SMS-Token) |
| `docs/adr/README.md` (ADR-0042) | ADR | Maßgebliche Form-Taxonomie (Namensform × Platzgrenze) für die Form-Dimension |
| `tests/test_adr_index_drift.py` | Test | Vorbild-Muster für den empfohlenen `doc-compliance-test` |

## Implementation Details

Das neue Dokument `docs/reference/metric_output_matrix.md` gliedert sich in
sieben Abschnitte, in dieser Reihenfolge:

```
1. Zweck & Leitfrage
   — "Wo erscheint Metrik X, in welcher Form, in welcher Reihenfolge,
      welcher Test bewacht das?" als durchgehendes Prüfschema je Zelle.

2. Metrik×Kanal-Landschaft (Kernmatrix)
   Trip:    E-Mail-Tabelle · E-Mail-Pill · Ausblick (outlook) · Kurzform/Compact
            Telegram rich · Telegram kurz · SMS
   Compare: HTML-Übersicht · Klartext · Telegram · SMS · Ausblick
   Alarme:  Betreff/Mail/Telegram/SMS (Registry-generisch)
   Kommandos/Drilldown (_DRILLDOWN_METRICS)
   Je Zelle: Datei:Zeile-Beleg · katalog-getrieben vs. handgeschrieben ·
   bewachender Test oder "unbewacht"

3. Sonderstrecken-Katalog (außerhalb des Metrik-Katalogs)
   thunder_forecast-Datenkanal · Hazard-Symbole · System-Blöcke (Kurzform DEC-4) ·
   TokenLine.filter_for_subject-Stub · Wintersport-Block ·
   SMS_MULTI_SYMBOLS_BY_METRIC (1:n-Strukturbruch)

4. Unbewachte Flächen mit Priorisierung
   Alle 10 Flächen aus der Recherche, sortiert nach Risiko/Größe;
   Top-3 (Alarm-Renderer, Ausblick-Tabelle, selectable-Blindstelle
   metric_catalog.py:695) explizit als Priorität 1 markiert.

5. Grundsatz-Entscheidung: Register-Strategie (Option A/B/C)
   A (reines Dokument) / B (zweites maschinenlesbares Register) /
   C (Hybrid: bestehenden Matrix-Test um Achsen erweitern + schlankes
   Dokument nur für nicht-Testbares) — Empfehlung C mit Regel-Budget-
   Begründung (Erweiterung von #1677 B statt neuem Gate).

6. Folge-Scheiben-Empfehlung (8 Einträge, issue-fähig)
   Je Eintrag: Kurzbeschreibung, Risiko-/Größeneinschätzung, Abhängigkeiten
   (z.B. Scheibe 7 erst nach PO-Entscheidung Compare-Kanal-Tabs).

7. PO-Entscheidungsvorlage
   (a) Compare-Kanal-Tabs ja/nein
   (b) Form-Dimension als eigene Achse bestätigen
   (c) Folge-Scheiben als Epic bündeln oder Einzel-Issues
   Alle drei EXPLIZIT als offen markiert, keine Vorwegnahme im Fließtext.

8. Anti-Veraltungs-Mechanik
   Drift-Schutz durch Parametrisierung über den Katalog (automatisch) +
   künftiger doc-compliance-test (Vorbild test_adr_index_drift.py) für die
   Prosa-Teile + Pflegeregel (wann muss das Dokument angefasst werden).
```

## Expected Behavior

- **Input:** `docs/context/konzept-1514-metrik-ausgabeorte.md` (vollständige Recherche + strategische Bewertung des Plan-Agenten)
- **Output:** `docs/reference/metric_output_matrix.md`, ~250–400 Zeilen, mit den 8 Abschnitten aus „Implementation Details"
- **Side effects:** keine — kein Produktivcode, keine neuen Tests, keine State-Datei-Änderungen in diesem Workflow

## Acceptance Criteria

- **AC-1:** Given das Referenzdokument `docs/reference/metric_output_matrix.md` / When ein Entwickler den Abschnitt zur Metrik×Kanal-Landschaft aufschlägt (Trip: E-Mail-Tabelle/Pill/Ausblick/Kurzform, Telegram rich+kurz, SMS; Compare: HTML/Klartext/Telegram/SMS/Ausblick; Alarme; Kommandos/Drilldown) / Then findet er für jeden Ausgabeort einen Datei:Zeile-Beleg, die Klassifikation katalog-getrieben vs. handgeschrieben, und den bewachenden Test oder ausdrücklich „unbewacht"
  - Test: manuelle Stichprobe — 5 zufällig gewählte Ausgabeorte im Dokument gegen die tatsächliche Codezeile nachschlagen, Beleg muss stimmen

- **AC-2:** Given den Abschnitt Sonderstrecken-Katalog / When ein Entwickler nach einem Datenkanal ohne Katalogeintrag sucht (thunder_forecast, Hazard-Symbole, System-Blöcke DEC-4, TokenLine.filter_for_subject-Stub, Wintersport-Block, SMS_MULTI_SYMBOLS 1:n) / Then findet er ihn mit Datei:Zeile-Beleg gelistet, getrennt von den katalog-getriebenen Orten aus AC-1
  - Test: alle 6 in der Recherche genannten Sonderstrecken im Dokument auffindbar, keine davon fehlt

- **AC-3:** Given den Abschnitt unbewachte Flächen / When ein Entwickler die Priorisierung liest / Then sind alle 10 aus der Recherche stammenden Flächen aufgeführt und die Top-3-Priorität (Alarm-Renderer, Ausblick-Tabelle, selectable-Blindstelle `metric_catalog.py:695`) ist explizit als Priorität 1 begründet
  - Test: Zählung der aufgeführten Flächen == 10, Priorität-1-Markierung vorhanden

- **AC-4:** Given die Grundsatz-Entscheidung / When ein Entwickler den Abschnitt zur Register-Strategie liest / Then sind Option A (reines Dokument), B (zweites Register) und C (Hybrid) mit Vor-/Nachteilen gegenübergestellt, und C ist als Empfehlung mit Regel-Budget-Begründung (Erweiterung des bestehenden Gates #1677 B statt neuem Pflicht-Gate) markiert
  - Test: alle drei Optionen mit mind. einem Nachteil je verworfener Option (A, B) im Text vorhanden

- **AC-5:** Given den Abschnitt Folge-Scheiben / When ein Entwickler die Liste liest / Then sind die 8 empfohlenen Scheiben als eigenständige, issue-fähige Einträge mit Kurzbeschreibung und Risiko-/Größeneinschätzung aufgeführt, und keine davon ist in diesem Workflow umgesetzt
  - Test: Zählung der Folge-Scheiben-Einträge == 8; kein Code-Diff außerhalb `docs/` im Workflow

- **AC-6:** Given die drei PO-Entscheidungsfragen (Compare-Kanal-Tabs, Form-Dimension als eigene Achse, Epic-Bündelung der Folge-Scheiben) / When ein Entwickler oder der PO das Dokument liest / Then sind sie sichtbar als offene Entscheidung markiert (z.B. Checkbox-Zeile „PO-Entscheidung ausstehend") und an keiner Stelle im Fließtext als bereits getroffen dargestellt
  - Test: alle drei Fragen als `- [ ]` oder gleichwertig markierte offene Punkte auffindbar, kein widersprechender Aussagesatz im übrigen Dokument

- **AC-7:** Given den Abschnitt Anti-Veraltungs-Mechanik / When ein Entwickler ihn liest / Then beschreibt er konkret, wie das Dokument aktuell gehalten werden soll — Verweis auf `tests/tdd/test_channel_metric_matrix.py` als Achsen-Erweiterungspfad und auf `test_adr_index_drift.py` als Vorbild für einen künftigen `doc-compliance-test` — nicht nur eine allgemeine Pflegeabsicht
  - Test: beide Datei-Referenzen (Matrix-Test, ADR-Index-Drift-Test) namentlich im Abschnitt vorhanden

- **AC-8:** Given den Scope dieses Workflows / When ein Entwickler die Spec oder das Dokument liest / Then ist explizit festgehalten, dass in diesem Workflow kein Produktivcode geändert und kein neues Gate/kein neuer Test eingeführt wird — beides ist ausschließlich als Folge-Scheibe vermerkt
  - Test: Abschnitt „Scope/Non-Goals" (dieser Spec) und Kopf des Referenzdokuments enthalten diese Abgrenzung wortwörtlich oder sinngemäß

## Scope / Non-Goals

**In Scope:**
- Genau eine neue Datei: `docs/reference/metric_output_matrix.md`
- Analyse und Strukturierung der bereits recherchierten Ausgabeorte, Sonderstrecken, unbewachten Flächen
- Dokumentierte Grundsatz-Entscheidung (Option C Hybrid) inkl. Abwägung
- PO-Entscheidungsvorlage mit drei explizit offenen Fragen

**Non-Goals (ausdrücklich NICHT Teil dieses Workflows):**
- Kein Produktivcode-Change in `src/`, `api/`, `internal/`, `frontend/`
- Keine neuen Tests, kein neues Gate, keine Erweiterung von `tests/tdd/test_channel_metric_matrix.py` — das ist Folge-Scheibe 1–8, nicht dieser Workflow
- Keine Entscheidung der drei PO-Fragen — nur deren Aufbereitung
- Kein maschinenlesbares Register (Option B) — bewusst verworfen, siehe Abschnitt 5 des Dokuments

## Known Limitations

- Das Dokument erfasst den Stand 2026-08-10 (Codebase-Momentaufnahme). Es gibt in diesem Workflow noch KEINE Ratsche-artige Aktualitätsgarantie — die entsteht erst mit der Folge-Scheibe zum `doc-compliance-test` (Abschnitt 8, Vorbild `test_adr_index_drift.py`).
- Die Metrik×Kanal-Landschaft (Abschnitt 2) kann strukturell nur Katalog-Konsumenten vollständig abbilden; Sonderstrecken (Abschnitt 3) sind eine kuratierte, nicht automatisch vollständige Liste — ein neuer Sonderpfad, der nach 2026-08-10 entsteht, taucht im Dokument nicht automatisch auf.
- Die Form-Dimension (Aggregation, `format_mode`, Token-Grammatik) wird im Dokument als eigene, bewusst separate Achse beschrieben (Empfehlung), aber nicht in der Kernmatrix mitgeführt — 1:n-Fälle wie `SMS_MULTI_SYMBOLS_BY_METRIC` würden die Matrix sonst strukturell verzerren.
- Compare-Kanal-Tabs (offene PO-Frage) bleiben bis zur Entscheidung ein struktureller Bruch zwischen Trip-Editor (`channel_layouts`) und Compare-Editor (`wiz.activeMetricKeys`) — das Dokument beschreibt diesen Zustand, löst ihn aber nicht auf.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dieser Workflow liefert ein Konzept-/Referenzdokument, keine Code- oder Architekturänderung. Die im Dokument beschriebene Register-Strategie (Option C Hybrid) ist eine dokumentierte Empfehlung für künftige Folge-Scheiben, kein sofortiger Architektur-Eingriff — ein ADR wäre erst bei Umsetzung einer Folge-Scheibe (z.B. neues Gate) sinnvoll. ADR-0042 (Namensform × Platzgrenze) bleibt die maßgebliche Referenz für die Form-Taxonomie und wird im Dokument zitiert, nicht abgelöst.

## Changelog

- 2026-08-10: Initial spec erstellt — Issue #1514, Konzept-Workflow `konzept-1514-metrik-ausgabeorte`
