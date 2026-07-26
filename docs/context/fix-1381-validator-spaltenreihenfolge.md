# Context: fix-1381-validator-spaltenreihenfolge

## Request Summary

Der Pflicht-Validator des Ortsvergleichs-Mailpfads (`.claude/hooks/email_spec_validator.py`)
weist eine korrekt gerenderte Mail zurück, sobald die Spalten der Stundentabelle nicht in
der intern kodierten Kanon-Reihenfolge stehen. Diese Reihenfolge ist seit #1359 frei
einstellbar. Der Validator ist Teil des Renderer-Commit-Gates (#811) und blockiert damit
jede Arbeit am Vergleichs-Renderer.

## Belegter Befund (Ist-Zustand)

Fehlgeschlagener Lauf gegen eine echte Staging-Mail (Preset `cp-21e198c1b74020dd`,
3 Orte, UV ans Ende sortiert):

```
STRUKTUR: Stundentabelle fuer Ort 'Innsbruck (E2E)' (Vorkommen 1) hat Spalten
['Zeit','Temp','Gef.','Wind','Böen','Regen','Gew.','Regen-W.','Sicht','UV'],
erwartet eine gueltige Teilmenge (in Reihenfolge) von
['Zeit','Temp','Gef.','Wind','Böen','Regen','UV','Gew.','Regen-W.','Sicht']
```

Quelle: `.claude/worktrees/bug-khw-sms-und-maildesign/docs/artifacts/fix-1361-stundenverlauf-ehrlich/email_spec_validator_output.txt`
(im Arbeitsordner der #1361-Sitzung, nicht im Bestand versioniert).

Die Mail war inhaltlich korrekt: dieselben zehn Spalten, nur eine andere Reihenfolge.

## Die eine Fundstelle

`.claude/hooks/email_spec_validator.py:383` in `validate_structure()`:

```python
if [c for c in _HOUR_COLUMNS_V2 if c in header_cols] != header_cols:
```

Die Listen-Komprehension projiziert die gefundenen Spalten auf die Kanon-Reihenfolge
`_HOUR_COLUMNS_V2` (`:219-221`) und vergleicht mit dem Original. Jede Abweichung von der
Kanon-Reihenfolge schlägt fehl. Eingeführt mit #1106 als Lockerung (Teilmenge statt
Exakt-Vergleich) — die Reihenfolge blieb dabei bewusst hart, weil sie damals fix war.

## Was diese Prüfung heute noch leistet (darf nicht verloren gehen)

| Leistung | Wo | Bleibt |
|---|---|---|
| Nur bekannte Spalten (`_HOUR_COLUMNS_V2`) sind zulässig | `:383` (implizit) | ja |
| Keine doppelten Spalten | `:383` (implizit, durch die Projektion) | ja — muss künftig **explizit** geprüft werden |
| `Zeit` ist erste Spalte, mind. 1 Wert-Spalte | `:376` | unverändert |
| Alle Orte einer Mail haben **identische** Spaltenliste | `:392-400` | unverändert (Reihenfolge-Gleichheit über Orte hinweg bleibt Pflicht) |

Die implizite Duplikat-Ablehnung ist der Grund, warum ein reiner Mengen-Vergleich eine
echte Abschwächung wäre.

## Punkt 2 des Tickets: Zeilen der Übersichtstabelle — geprüft, kein Befund

Seit #1359 ist auch die Reihenfolge der Metrik-**Zeilen** einstellbar. Der Validator
macht dort jedoch **keine** Reihenfolge-Annahme:

- `validate_plausibility()` (`:427-457`) und `validate_format()` (`:460-485`) iterieren
  über `rows[1:]` und schlagen das Label in `_OVERVIEW_METRIC_CHECKS` nach — Position egal.
- `extract_table_rows()` (`:257-265`) verlangt, dass die **erste Datenzeile**
  „Amtliche Warnungen" ist. Das ist weiterhin ein gültiger Renderer-Vertrag:
  `_visible_metrics()` (`src/output/renderers/email/compare_html.py:476-491`) stellt die
  Warn-Zeile ausdrücklich immer an die erste Stelle („immer sichtbar UND immer erste").
- `extract_locations()` (`:268-283`) nimmt die Ortsspalten in Fundreihenfolge, ohne eine
  bestimmte zu erwarten — die seit #1359 einstellbare Ortsreihenfolge stört nicht.

→ Nur eine Fundstelle ist zu ändern.

## Warum der Weg „erwartete Reihenfolge aus dem Preset lesen" ausscheidet

Der Validator arbeitet ausschließlich über IMAP gegen das zugestellte Postfach
(`_fetch_latest_message()`, `:113 ff.`) und hat keinen Zugriff auf die Konfiguration des
geprüften Vergleichs. Die Reihenfolge als Mail-Kopfzeile mitzuliefern wäre eine Änderung
am Renderer — und genau die ist durch dieses Gate blockiert. Zirkelschluss, deshalb
verworfen.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/email_spec_validator.py` | Die zu ändernde Datei; `:219-221` Kanon-Liste, `:376-400` Spalten-Prüfung |
| `src/output/renderers/email/compare_html.py` | Erzeugt die Stundentabelle; `HOUR_METRICS`, `_visible_hour_metrics()` (`:609-622`) — Quelle der tatsächlichen Spaltenfolge |
| `.claude/hooks/renderer_mail_gate.py` | Commit-Gate #811, ruft diesen Validator als Pflichtnachweis auf |
| `docs/reference/mail_validators.md` | Referenz der Plausibilitäts-Schwellen und der Anti-Stale-Mechanik |

## Existing Patterns

- **Präzedenz #1242** (`:494-501`): Derselbe Fehlertyp schon einmal — der Validator
  erwartete `09:00`, der Renderer schrieb `09`. Damals wie heute gilt: *„Der Prüfer muss
  dasselbe Format erwarten, das der Renderer erzeugt, sonst weist er eine korrekte Mail
  zurück."*
- **Präzedenz #1106**: Exakt-Vergleich → Teilmenge-mit-Reihenfolge, als die Spaltenauswahl
  konfigurierbar wurde. Jetzt derselbe Schritt für die Reihenfolge.
- **Präzedenz #1150 / Adversary F001+F002**: Lockerungen wurden dort jeweils durch eine
  neue, engere Prüfung gegengewichtet (Vorkommens-Index, Cross-Location-Konsistenz).
  Dieses Muster ist hier fortzusetzen: Reihenfolge-Freigabe **plus** explizite
  Duplikat-Ablehnung.

## Dependencies

- **Upstream:** IMAP-Postfach `gregor-test@henemm.com` (`GZ_IMAP_*`), Header
  `X-GZ-Mail-Type: compare`, `X-GZ-Compare-Hourly-Enabled`.
- **Downstream:** `renderer_mail_gate.py` (Commit-Gate), der `/e2e-verify`-Ablauf, jede
  künftige Arbeit an `compare_html.py` — insbesondere Etappe S2/S3 des Epics #1372.

## Existing Specs

- `docs/reference/mail_validators.md` — Dispatch der zwei Mail-Pfade und ihrer Validatoren
- CLAUDE.md, Abschnitt „Mail-Validatoren & Renderer-Gate (ZWINGEND)"

## Risks & Considerations

1. **Gate-Erosion** ist das Hauptrisiko. Die Änderung darf ausschließlich die
   Reihenfolge-Annahme aufgeben; jede andere Prüfung bleibt gleich streng oder wird
   strenger. Nachweis über einen Gold-Standard-Test: umsortierte Mail wird **angenommen**,
   Mail mit unbekannter/doppelter Spalte und Mail mit über Orte hinweg abweichender
   Spaltenfolge werden weiterhin **abgelehnt**.
2. **Eigener Workflow ist Pflicht** (Präzedenz #1110): Ein Validator darf nie in demselben
   Workflow geändert werden, dessen Ergebnis er prüft. Hier ist der Validator das
   Lieferergebnis — die Bedingung ist erfüllt.
3. **Sensitive-File-Prompt**: Ein Eingriff in `.claude/hooks/` löst die Rückfrage an den
   PO aus. Das ist gewollte Sichtbarkeit, kein Hindernis.
4. **Nachweislage**: Der Beleg aus #1361 liegt nur unversioniert im fremden Arbeitsordner.
   Die Fixture für den Gold-Standard-Test muss in den Bestand aufgenommen werden, damit
   der Nachweis wiederholbar ist (dieselbe Lücke, die #1372 für #1361 bemängelt).
5. **Reihenfolge zum Deploy**: Der Validator-Fix muss vor Etappe S2 (#1373/#1384) live
   sein, weil dort am Vergleichs-Renderer gearbeitet wird.
