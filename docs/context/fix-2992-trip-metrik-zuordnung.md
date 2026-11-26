# Context: fix-2992-trip-metrik-zuordnung

## Request Summary

Issue #2992 (aus Paritäts-Bestandsaufnahme #1986, Eintrag NEU-11): Die Zuordnung
„Vergleichs-Zeile (Renderer-ID) → Trip-Metrik-ID" ist doppelt von Hand gepflegt.
Zusammenführen zu einem Baustein, Verhalten unverändert.

Hinweis: Die Bestandsaufnahme nennt als Seite A `trip_metric_ids.py:15/:67`. Die
Zeilennummern passen aber zu `compare_metric_ids.py:15` (`FRONTEND_TO_RENDERER_METRIC_ID`)
und `:67` (`RENDERER_TO_TRIP_METRIC_ID`); `trip_metric_ids.py` enthält keine
ID-Zuordnung (nur `DEFAULT_TRIP_METRIC_IDS` aus dem Register + `resolve_trip_active_metrics`).
Der genannte „bewachende Test" `tests/unit/test_compare_metric_parity.py:232` prüft
Matrix-Zeilen der Vergleichsmail (#1324), nicht diese Zuordnung — es gibt heute
**keinen** Wächter, der `RENDERER_TO_TRIP_METRIC_ID` gegen den Katalog prüft.

## Die echte Doppelung (belegt)

- `src/output/renderers/compare_metric_ids.py:67` `RENDERER_TO_TRIP_METRIC_ID`:
  sechs getippte Paare `temp_max→temperature, cloud_avg→cloud_total,
  precip_sum→precipitation, pop_max→rain_probability, wind_max→wind, thunder_max→thunder`.
- `src/output/renderers/compare_metric_catalog.py:106` `COMPARE_METRIC_CATALOG`:
  jeder Eintrag trägt `key` (Frontend-ID) + `metric_id` (= Trip-/Register-ID) +
  `aggregation`. Über `FRONTEND_TO_RENDERER_METRIC_ID` ist daraus die Renderer-ID
  berechenbar; `compare_metric_ids.katalog_paar(renderer_id)` (#3101) liefert
  bereits `(metric_id, aggregation)`.
- Live geprüft (2026-11-26): `katalog_paar(r)[0] == RENDERER_TO_TRIP_METRIC_ID[r]`
  für alle sechs Einträge. Die Trip-ID steht also zweimal.

## Related Files

| Datei | Rolle |
|---|---|
| `src/output/renderers/compare_metric_ids.py:67` | getippte Tabelle (wird abgeleitet) |
| `src/output/renderers/compare_metric_ids.py:271-296` | `_katalog_paare`, `katalog_paar` — vorhandener Ableitungsweg |
| `src/output/renderers/compact_summary.py:693-730` | einziger Verbraucher: `format_location_summary` (context="vergleich", #1278) |
| `tests/helpers/metrik_listen_scan.py:359` | Metrik-Listen-Ratsche registriert `RENDERER_TO_TRIP_METRIC_ID` als „wert"-Liste (Literal-AST-Scan) |
| `tests/unit/test_compare_location_summary.py` | Verhaltens-Tests AC-5/AC-6 (Filter, Regen/Gewitter) |
| `docs/specs/modules/compare_location_summary.md` | Spec des Vergleichs-Satzes |

## Existing Patterns

- #3101: `_katalog_paare()` „gerechnet aus COMPARE_METRIC_CATALOG und
  FRONTEND_TO_RENDERER_METRIC_ID — keine zweite getippte Abbildung". Genau dieses
  Muster wird fortgesetzt.
- Import-Zyklus: `compare_metric_catalog` importiert `compare_metric_ids` auf
  Modulebene → Ableitung in `compare_metric_ids` muss in einer Funktion (lazy
  import) passieren, wie `_katalog_paare`.

## Design-Eckpunkte (für Analyse)

- Was bleibt eigenständig: die **Auswahl und Reihenfolge** der sechs
  Renderer-IDs (nur Größen mit `_format_*`-Zweig im Satz-Baustein,
  Satz-Reihenfolge). Das ist keine Doppelung, sondern eine eigene Festlegung.
- Was entfällt: die getippte Trip-ID je Eintrag → kommt aus `katalog_paar()[0]`.
- **Nicht** über Trip-ID filtern: `temp_min` hat ebenfalls `metric_id=temperature`;
  ein Filter „Trip-ID der gewählten Zeile ∈ Satz-Menge" würde temp_min allein die
  Temperatur im Satz einschalten lassen → Verhaltensänderung. Filter bleibt auf
  Renderer-ID.

## Dependencies / Dependents

- Abhängig von: `COMPARE_METRIC_CATALOG`, `FRONTEND_TO_RENDERER_METRIC_ID`.
- Abhängig ist: nur `format_location_summary` (Vergleichsmail-Fließtext, alle
  Kanäle, die den Satz zeigen).

## Risks

- Mail-Inhaltspfad → Renderer-Commit-Gate (Modus-Matrix-Test + Validator) greift.
- Metrik-Listen-Ratsche: Registrierung in `metrik_listen_scan.py` muss angepasst
  werden (neue Liste enthält Renderer-IDs, keine Register-Kennungen → nicht mehr
  Register-Liste; Eintrag entfernen bzw. umstellen), sonst „zeigt ins Leere".
- Neuer Wächter nötig: Satz-Renderer-ID ohne Katalog-Paar darf nicht still
  entfallen (Laufzeitfehler bzw. Test).

## Analysis

**Type:** Feature (Refactoring ohne Verhaltensänderung, Doppelung entfernen)

### Affected Files

| Datei | Change | Begründung |
|---|---|---|
| `src/output/renderers/compare_metric_ids.py` | MODIFY | getippte Trip-IDs ersetzen: Tupel `SUMMARY_SENTENCE_RENDERER_IDS` (sechs Renderer-IDs, Satz-Reihenfolge) + Funktion `renderer_to_trip_metric_id()` → `{rid: katalog_paar(rid)[0]}`; fehlt ein Katalog-Paar → `ValueError` mit Namen (kein stilles Entfallen) |
| `src/output/renderers/compact_summary.py` | MODIFY | `format_location_summary` liest die Funktion statt der Konstante (Docstring nachziehen) |
| `tests/helpers/metrik_listen_scan.py` | MODIFY | Registrierung `RENDERER_TO_TRIP_METRIC_ID` entfernen (kein Literal mehr; neues Tupel enthält Renderer-IDs, keine Register-Kennungen) — mit Kommentar #2992 |
| `tests/unit/test_compare_summary_trip_ids_from_catalog.py` (Name nach Verhalten) | CREATE | Wächter: Satz-Zuordnung == Katalog-Ableitung; jede Satz-Renderer-ID hat ein Katalog-Paar; Verhalten: temp_min allein schaltet die Temperatur im Satz NICHT ein; Reihenfolge der Satz-Teile unverändert |

Scope: 4 Dateien, ~60–80 LoC (davon ~45 Test). Innerhalb der Limits.

### Scope / Risk

- Risiko **niedrig**: einziger Verbraucher ist der Vergleichs-Fließtextsatz; heutige Werte sind nachweislich identisch zur Katalog-Ableitung (live geprüft), Ausgabe bleibt Byte-gleich.
- Mail-Inhaltspfad → Renderer-Commit-Gate (Modus-Matrix + Validator) beim Commit beachten.

### Technical Approach

1. Auswahl/Reihenfolge bleibt eine eigene Festlegung (Größen mit `_format_*`-Zweig), Trip-ID kommt aus `COMPARE_METRIC_CATALOG.metric_id` über das bestehende `katalog_paar()` (#3101-Muster, lazy import wegen Zyklus).
2. Filter bleibt auf Renderer-ID (nicht Trip-ID), damit `temp_min` allein den Temperatur-Satzteil nicht einschaltet.
3. Konstante `RENDERER_TO_TRIP_METRIC_ID` entfällt (einziger Import in `compact_summary.py`); kein Alias, damit keine zweite Quelle bleibt.
4. Der in #1986 genannte „bewachende Paritätstest" (`test_compare_metric_parity.py:232`) bewacht diese Zuordnung tatsächlich nicht und bleibt unverändert (Matrix-Zeilen-Test #1324).

### Dependencies

`COMPARE_METRIC_CATALOG`, `FRONTEND_TO_RENDERER_METRIC_ID`, `katalog_paar`; Dependent: `format_location_summary` (Vergleichsmail, alle Kanäle mit Satz).

### Open Questions

Keine (rein technisch, keine Produktentscheidung).
