# Context: fix-1418-gewitter-risikopunkt

Issue: [#1418](https://github.com/henemm/gregor_zwanzig/issues/1418) · Scheibe **S1** von Epic [#1419](https://github.com/henemm/gregor_zwanzig/issues/1419)
Track: Standard · Erstellt: 2026-07-29

## Request Summary

Der Risiko-Punkt am Ende jeder Stundenzeile in der Briefing-Mail springt bei Gewitter
nie auf Rot, weil der Code den Gewitterwert als Zahl liest, tatsächlich aber ein
Stufenwort geliefert bekommt. S1 stellt die Reaktion auf Gewitter wieder her — mit
dem heutigen Stufenmodell (NONE/MED/HIGH). Das Vier-Stufen-Modell aus #1419 ist
ausdrücklich **nicht** Teil dieser Scheibe.

## Kern des Befunds (im Code verifiziert)

`r["thunder"]` trägt im gesamten Produktivpfad ein `ThunderLevel`-Enum oder `None` —
**nie** eine Zahl:

| Schreiber | Zeile | Wert |
|---|---|---|
| `src/output/renderers/email/helpers.py` | 112 | `getattr(dp, "thunder_level")` → `ThunderLevel`/`None` |
| `src/output/renderers/email/helpers.py` | 170–173 | `max_thunder(values)` → `ThunderLevel` |
| `src/output/renderers/trip_report.py` | 498 | `getattr(dp, "thunder_level")` → `ThunderLevel` |
| `src/output/renderers/trip_report.py` | 428–430 | `max_thunder(values)` → `ThunderLevel` |

`ThunderLevel` ist ein `str`-Enum (`src/app/models.py:35-39`) — `float("HIGH")` wirft
`ValueError`, der still auf den Default zurückfällt.

### Drei Ausfallstellen, dieselbe Ursache

| # | Stelle | Wirkung | im aktiven Pfad? |
|---|---|---|---|
| 1 | `email/html.py:157-158` — `_safe_float(r.get("thunder")) > 20` | Risiko-Punkt wird bei Gewitter nie rot | **ja** |
| 1b | `email/html.py:176` — `thunder > 0` | Punkt wird bei Gewitter auch nie orange | **ja** |
| 2 | `email/html.py:658` — `numeric > _THUNDER_THRESHOLD` (`numeric` ist bei Enum `None`) | **Zell-Hintergrund der Gewitterspalte feuert nie** | **ja** |
| 3 | `email/html.py:240,259,262` — `thunder_pct` | folgenlos | nein, toter Code |

**Stelle 2 steht nicht im Issue** — sie ist derselbe Fehler eine Ebene tiefer und
gehört fachlich in dieselbe Scheibe: Ohne sie bliebe die Gewitterspalte weiterhin
ungefärbt, während der Punkt wieder rot würde. Das wäre ein widersprüchliches Bild.

### Was heute funktioniert

Der Zell**text** ist korrekt: `email/helpers.py:620` vergleicht gegen
`ThunderLevel.HIGH`/`MED` und rendert „hoch"/„mögl." bzw. ⚡⚡/⚡. Der Nutzer sieht
also das Gewittersymbol — aber ohne farbliche Hinterlegung und ohne roten Punkt.
Genau diese Diskrepanz ist der sichtbare Schaden.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/html.py` | `_row_risk` (148–179), Zell-Tönung (622–660), Punkt-Farben `_RISK_DOT_COLORS` (182–186), einziger Aufrufer `:673` |
| `src/output/metric_format.py` | **Werkzeug liegt bereit**: `thunder_ordinal()` (221–229) — kanonische Ordnung NONE<MED<HIGH, nimmt Enum *und* rohen String |
| `src/output/renderers/email/compare_html.py` | Vorbild eines robusten Lesers: `_THUNDER_SEV` (157), `_sev_thunder` (186–197) |
| `src/output/renderers/email/helpers.py` | korrekter Enum-Leser für den Zelltext (620) |
| `src/app/metric_catalog.py` | `thunder`-Eintrag (248–264) — **kein `display_thresholds`** |
| `tests/tdd/test_renderer_katalog_schwellen.py` | Tests 246–262 zementieren die falsche Annahme (füttern Zahlen) |
| `docs/specs/modules/ampel_schwellen_renderer.md` | „Known Limitations" ab 328 — Gewitter dort bewusst ausgeklammert |

## Existing Patterns

- **Kanonische Stufenordnung statt Zahlenvergleich:** `thunder_ordinal()` ist die
  bestehende, dokumentierte Quelle. Sieben weitere Module nutzen sie bereits
  (`narrow.py:170`, `day_window.py:51`, `weather_metrics.py:1137`, …).
- **Robuster Leser gegen beide Datenformen:** `compare_html.py:186-197` behandelt
  Enum und String gleich — der Ortsvergleich hat den Fehler nicht.
- **Zwei Skalen, nie vermischen (ADR-0025):** `thunder_ordinal()` {0,1,2} ist die
  Vergleichsordnung, `thunder_label_value()` {0,2,3} die SMS-Render-Skala. Für S1
  ist ausschließlich `thunder_ordinal()` richtig.

## Dependencies

- **Upstream:** `ThunderLevel` (`app/models.py:35`), befüllt einzig von
  `providers/openmeteo.py:754` aus WMO-Code 95/96/99.
- **Downstream:** jede Briefing-Mail mit Stundentabelle (`full` und `compact`),
  inklusive Mobilansicht (`_render_mobile_compact_rows` → `_render_html_table`).
- **Golden-Snapshots** (`tests/golden/email/*-html.txt`) konservieren den heutigen
  Zustand „nie roter Gewitterpunkt" und werden sich ändern.

## Existing Specs

- `docs/specs/modules/ampel_schwellen_renderer.md` — regelt die Katalog-Schwellen
  der übrigen Größen; Gewitter ist dort ausdrücklich ausgenommen. Diese Spec muss
  in ihren „Known Limitations" nachgezogen werden.
- `docs/adr/` — ADR-0025 (zwei Gewitterskalen).

## Risks & Considerations

1. **Der Katalogweg trägt nicht.** `severity_for("thunder", …)` liefert für jeden
   Wert `None`, weil der Katalog kein `display_thresholds` für `thunder` führt und
   `severity_from_thresholds` bei fehlenden Schlüsseln bewusst `None` statt „green"
   zurückgibt (`metric_format.py:130-134`). Wer Gewitter naiv in den `severity_for`-
   Pfad hängt, färbt weiterhin gar nichts — und merkt es nicht.
2. **Zwei Datenformen unter demselben Schlüssel.** `"thunder"` trägt in den
   Stunden-Rows ein Enum, in den Stage-/Trend-Rows (`outlook.py:186`,
   `helpers.py:831`) einen rohen Namen-String. `thunder_ordinal()` verträgt beide;
   jede eigene Lösung muss das ebenfalls.
3. **Bestehende Tests sind falsch geeicht.** `test_ac7_thunder_row_risk_unchanged`
   (`:246-252`) und `test_ac7_thunder_cell_tint_unchanged` (`:256-262`) prüfen mit
   `{"thunder": 25}` — einer Datenform, die in Produktion nicht existiert. Sie
   prüfen veraltetes Verhalten und werden nach Test-Politik ersetzt, nicht umgangen.
4. **Renderer-Commit-Gate #811** greift, weil `html.py` eine Mail-Inhalts-Datei ist:
   vor dem Commit müssen `tests/tdd/test_issue_811_mode_matrix.py` grün sein und ein
   erfolgreicher `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte
   Staging-Mail vorliegen.
5. **MED ist heute unerreichbar** (#1418 Fehler 2 = S2 des Epics). Die Abbildung muss
   MED trotzdem korrekt behandeln, damit S2 ohne weiteren Eingriff wirksam wird.
6. **„Keine Aussage" bleibt vorerst wie heute.** Ein fehlender Gewitterwert (`None`)
   trägt nicht zum Punkt bei. Das widerspricht dem `None`-Kontrakt aus #1377, dessen
   saubere Auflösung aber an S3/S4 des Epics hängt (Gewitter überlebt heute keinen
   Providerausfall). Als Grenze festhalten, nicht in S1 lösen.

## Nebenbefunde (nicht Teil von S1)

- Die Risiko-Legende (`html.py:1381-1386`) führt **vier** Farben, gerendert werden
  aber nur **drei** (`_RISK_DOT_COLORS`) — und keine der vier ist mit den drei
  identisch. Kandidat für #1199.
- `_render_mobile_hour_list` (`html.py:216`) ist seit `bf5ef21f` ohne Aufrufer.
  Bereits als #1199-Kandidat in der Spec vermerkt.
