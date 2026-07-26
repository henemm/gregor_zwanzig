# Kontext & Analyse: fix-1366-leerauswahl-heisst-leer

**Etappe:** S3 Scheibe B von Epic #1372 (Kind von Dach-Epic #1374)
**Tickets:** #1366 + #1361 Befund 3
**Stand:** 2026-07-26, HEAD `a05af6b1` (nach #1373 Scheibe B)
**Typ:** Bug (nutzersichtbares Fehlverhalten)

## Etappen-Vorprüfung (Arbeitsregel #1374)

S3 ist regulär dran, es wird nichts übersprungen:

- Blockade **#1381** (Mail-Validator gegen einstellbare Spaltenreihenfolge) — geschlossen 2026-07-26 06:42.
- **S2** — #1373 geschlossen 2026-07-26 16:45, #1387 live, #1384 ausdrücklich nach S6 verschoben.
- S3 wurde in drei nacheinander lieferbare Scheiben geschnitten (PO-Freigabe 2026-07-26):
  **B** (diese) → **C** #1378 zwei Zeitbasen → **A** #1368 + #1361 Befund 2 konfigurierbarer Ausblick.
  Begründung der Reihenfolge: die Regel „leer heißt leer" ist die Grundlage jeder Zuordnung je Ausgabe;
  der Ausblick als *dritte* Ausgabe darf nicht auf der defekten Regel aufgebaut werden.

## Problem aus Nutzersicht

Wer im Ortsvergleich **alle** Wettergrößen abwählt, bekommt in der Mail **alle** statt keiner —
das genaue Gegenteil der Eingabe (#1366).
Wer drei Stundenwerte anhakt, deren Kennungen der Stundentabelle unbekannt sind, bekommt **neun**
Spalten statt drei, ohne jede Rückmeldung (#1361 Befund 3).

## Ursache — belegt

Die **Renderer** setzen die richtige Bedeutung bereits um und unterscheiden sauber
„nicht gesetzt" (`None`) von „bewusst leer" (`[]`):

| Stelle | Verhalten |
|---|---|
| `src/output/renderers/email/compare_html.py:488` `_visible_metrics` | `is None` → alle; `[]` → nur Warn-Zeile |
| `src/output/renderers/email/compare_html.py:620` `_visible_hour_metrics` | `is None` → alle; `[]` → keine Spalten |
| `src/output/renderers/comparison.py:109` `_ordered_rows` | Docstring: „Eine leere Liste bleibt leer (AC-8)" |

Die Falle sitzt **ausschließlich** in den beiden vorgelagerten Auflösern, die `[]` gar nicht erst
bis dorthin durchlassen:

| # | Stelle | Fehler |
|---|---|---|
| **P1** | `src/output/renderers/compare_metric_ids.py:147-148` | `if not active_metrics: return None` — fängt `[]` mit |
| **P1b** | `src/output/renderers/compare_metric_ids.py:170` | `return resolved or None` — komplett unauflösbare Auswahl → alles |
| **P2** | `src/output/renderers/compare_hourly_metric_ids.py:44-45` | gleiche Falle für die Stundenspalten |
| **P2b** | `src/output/renderers/compare_hourly_metric_ids.py:53` | gleiche zweite Falle |

Beide Auflöser haben in der gesamten Produktion **genau zwei** Aufrufstellen
(`src/services/report_config_resolver.py:238/239`) — ein Eingriff dort wirkt vollständig und
gleichzeitig auf HTML, Klartext, Telegram und SMS. Ein umgehender Lesepfad existiert nicht.

**Stille Verwerfung:** Der Übersichts-Auflöser meldet unauflösbare Einträge bereits per
`logger.warning` (`compare_metric_ids.py:158-164`, aus #1296). Der **Stunden-Auflöser meldet gar
nichts** — das Modul importiert nicht einmal `logging`. Das ist #1361 Befund 3.
Zusatz: Sind *alle* Einträge unauflösbar, greift `resolved or None` und der Renderer zeigt **alles** —
die vorhandene Warnung sagt dann das Gegenteil dessen, was passiert.

## Zwei Nebenstellen, die mitmüssen

Sie sind heute harmlos, **weil** `[]` und „fehlt" dasselbe bedeuten. Kippt diese Bedeutung, werden
sie zu Fehlern:

| # | Stelle | Nach der Umstellung |
|---|---|---|
| **F1** | `frontend/src/lib/components/compare/compareEditorSave.ts:289-293` | Beim **Neuanlegen** wird der Schlüssel bei Leerauswahl ganz weggelassen → die bewusste Leerauswahl geht verloren und kippt in „alle". Der Bearbeiten-Pfad (`:102-121`) schreibt `[]` bereits korrekt. |
| **F2** | `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts:60-66` | `applyHourlyMetricToggle` materialisiert bei leerer Auswahl erst die Vorgabemenge und wendet dann den Umschalter an → ein Klick aus „nichts" erzeugt „Vorgabe minus eins". |

## Der Pflicht-Validator — geprüft

`.claude/hooks/email_spec_validator.py` (Pflicht-Gate für Vergleichs-Mails):

- **Übersichtstabelle leer: unkritisch.** Die Tabelle wird an der Warn-Zeile erkannt
  (`:263-266`), und die bleibt bei leerer Auswahl bestehen. Die scheinbare Mindestzahl-Prüfung
  (`:339-343`) ist **toter Code** — durch den Guard in `:265` strukturell unerreichbar.
  Eine Winner-Box wird **nicht** verlangt, sie wäre ein Verstoß (`:232-235`, v2-Vertrag).
- **Stundentabelle leer: hartes Blockieren.** `:380-386` verlangt je Ort
  „Zeit + mindestens eine Wert-Spalte". Eine Stundentabelle mit nur der Zeit-Spalte lässt das Gate
  je Ort durchfallen. Einziger sauberer Ausweg: die leere Stundenauswahl auf **„Stundenverlauf
  entfällt"** abbilden (`hourly_enabled=false`) — dann entfällt die Prüfung regulär (`:353`).

## Bestandsdaten — keine betroffen

Gezählt als `claude-gregor` (als `hem` nicht lesbar):

| Umgebung | Vergleiche | `active_metrics: []` | `hourly_metrics: []` |
|---|---|---|---|
| Produktion | 5 | **0** | **0** (Feld fehlt bei 5/5) |
| Staging | 103 | **0** | **0** (Feld fehlt bei 102/103) |

Die Umstellung ändert an **keinem** bestehenden Vergleich das Verhalten; sie wirkt nur für künftige
bewusste Abwahlen. **Keine Migration nötig.** Eine Leerauswahl übersteht das Speichern bereits
unbeschadet (`internal/handler/config_merge.go:18-20`) — die Datenseite braucht keinen Eingriff.

## Betroffene Dateien

| Datei | Art | Beschreibung |
|---|---|---|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | P1/P1b: `is None` statt truthiness; unauflösbare Auswahl → `[]` statt `None` |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | P2/P2b dito + Meldung bei unauflösbaren Kennungen (fehlt heute ganz) |
| `src/services/report_config_resolver.py` | MODIFY | Leere Stundenauswahl auf „Stundenverlauf entfällt" abbilden (siehe Entscheidung) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | F1: Neuanlage schreibt `[]` ausdrücklich |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | MODIFY | F2: Umschalter materialisiert keine Vorgabemenge mehr |
| `tests/unit/test_compare_metric_order.py` | MODIFY | `xfail(strict=True)`-Marker `:426-430` entfernen (schlägt sonst als XPASS fehl) |
| `tests/tdd/test_issue_1104_compare_config_foundation.py` | MODIFY | `:53-57` schreibt „leer → None" fest |
| `tests/unit/test_compare_active_metrics_dual_format.py` | MODIFY | `:213-221` dito, verweist selbst auf #1366 |
| `tests/tdd/test_issue_1106_hourly_metrics_config.py` | MODIFY | `:136-140` dito für die Stundenspalten |

**Muss unverändert bleiben** — `tests/unit/test_compare_metric_order.py:393-398`: fehlt das Feld ganz
(Altbestand), bleibt es bei „alle Größen". Nur `[]` wird umgedeutet, **nicht** „Feld fehlt".

## Eigenschaften, die der Eingriff nicht brechen darf

1. **Reihenfolge** = Erstvorkommen in der Auswahl (#1335/#1359) — bestimmt Zeilenfolge in Mail und
   Telegram und über das SMS-Budget, *welche* Größen die SMS überhaupt erreichen.
2. **Entdopplung** auf die Renderer-Kennung, erstes Vorkommen gewinnt.
3. **Gemischte Speicherformate** in derselben Liste (Zeichenkette alt + Objekt neu, #1373 Restrisiko R1).
4. **Kein Absturz** bei beliebigem Fremd-Inhalt (Nicht-Liste, `int`, `None`-Einträge).

## Scope

- Dateien: 5 Quell- + 4 Testdateien
- Geschätzt: ~90–130 Zeilen netto
- Risiko: **MEDIUM** — Verhaltensänderung an einer zentralen Stelle mit vier Ausgabewegen; entschärft
  dadurch, dass kein Bestandsdatensatz betroffen ist und die Renderer die Zielbedeutung schon umsetzen.

## Abgrenzung — NICHT in dieser Scheibe

- **#1361 Befund 2** und **#1368** (konfigurierbarer 3-Tages-Ausblick) → Scheibe A
- **#1378** (zwei Zeitbasen) → Scheibe C
- **Trip-Seite, gleiche Fehlerklasse, anderes Speicherformat** (Auswahl = Liste mit `enabled`-Flags):
  Metriken-Überblick fällt auf eine fest verdrahtete Siebener-Liste zurück
  (`email/html.py:1157-1163`, `email/plain.py:155-161`), Vortagszeile auf eine Alt-Zusammenfassung
  (`services/day_comparison.py:178`), und sind *alle* Kanal-Listen leer, greift die globale Liste
  (`app/loader.py:796-801`) — im Widerspruch zum eigenen Vertrag in `app/models.py:604-606`.
  → eigenes Ticket, nutzersichtbar.
- `corridors or None` (`services/report_config_resolver.py:241`) — gleiche Bauart bei den
  Wertebereichen → Sammel-Eintrag.
- Toter Prüfzweig im Mail-Validator (`:339-343`) — verspricht eine Mindestzahl-Prüfung, die es nicht
  gibt → Sammel-Eintrag (Gate-Befund).
- Zwei auseinanderlaufende Stände desselben Vergleichs (Alt-Ablage
  `data/users/henning/compare_presets.json` führt 6 Größen, maßgebliche Ablage unter `briefings/`
  führt 11) → Sammel-Eintrag.

## Offene Entscheidung (PO)

**Was bedeutet eine leere Stundenauswahl?** Der Pflicht-Validator lässt eine Stundentabelle mit nur
der Zeit-Spalte nicht durch. Empfehlung: leere Auswahl = **der Stundenblock entfällt ganz** — eine
Tabelle nur mit Uhrzeiten hat keinen Nutzwert, und die Bedeutung „ich will hier nichts" wird ehrlich
umgesetzt, ohne das Gate aufzuweichen.
