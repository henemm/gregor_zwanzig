# Context: #1680 Scheibe 4 — Herkunft der Gewitterstufe in der Trip-Stundentabelle

## Request Summary

Die Trip-Stundentabelle (Vollmail, Klartext + einfache HTML-Ansicht) soll wie die
Compare-Stundentabelle seit S3 die tragende Zutat der Gewitterstufe zeigen
(`14:00  leicht · CAPE`). Bisher zeigt sie nur die Stufe ohne Herkunft — der letzte
noch offene Ausgabeort, der ohne Änderung an `HourlyValue` oder `aggregate_stage()`
erreichbar ist.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/trip_report.py:653-688` | `TripReportFormatter._dp_to_row()` — DER echte Trip-Mail-Stundenzeilen-Pfad (pro Stunde). Setzt `row["_hail_flag"]` als Seitenkanal (Zeile 687). Analog muss `row["_thunder_signals"]` hier entstehen |
| `src/output/renderers/trip_report.py:534-651` | Nacht-Block-Aggregation (Name im Code: die Methode vor `_dp_to_row`, endet mit `return row` bei 651). Setzt `row["_hail_flag"]` über `hail_priority()` (Zeile 649) — mehrere `dp` werden zu EINER Zeile zusammengefasst. Braucht `union_of_max_carriers()`, nicht den rohen Wert |
| `src/output/renderers/email/helpers.py:693-757` | `fmt_val()` — DIE geteilte Zellwert-Formatierfunktion für Trip- UND Compare-Stundentabelle. `key == "thunder"`-Zweig (732-757) hängt den Hagel-Hinweis über `row["_hail_flag"]` an (`format_hail_note`), im Klartext-/Roh-Modus als `f"{label} · {note}"`. Im HTML-Ampel-Modus wird stattdessen ein Kreis gerendert (`_ampel_dot_css`, Zeile 754-757) — reiner Text hat dort keinen Platz |
| `src/output/renderers/email/compare_html.py:204-242` | `_fmt_thunder()` — das S1/S3-Vorbild für Compare. Nimmt `signals` als DRITTEN Parameter, baut `teile = [label]`, hängt `", ".join(thunder_signal_label(s) for s in signals)` an, dann den Hagel-Hinweis, verbindet mit `" · "`. Genau dieses Muster überträgt sich auf `fmt_val()`s Klartext-Zweig |
| `src/output/metric_format.py:559-600` | `union_of_max_carriers()` — vereinigt Träger der Paare, die die Höchststufe erreichen. Pflicht für die Nacht-Block-Zeile (mehrere `dp`) |
| `src/output/metric_format.py:382-390` | `thunder_signal_label()` — deutsche Beschriftung einer Zutat, Exakt-Treffer sonst roher Name (kein Erfinden) |
| `src/output/metric_format.py:448-` | `thunder_signal_carriers()` — liefert bei Stufe `NONE` bereits `[]` (die Garantie, auf die auch die Compare-Stundenzelle sich verlässt) |
| `src/providers/thunder_enrichment.py:131-151` | Setzt `dp.thunder_level_signals` PRO DATENPUNKT über `thunder_signal_carriers(...)` — schon vorhanden, kein neuer Datenkanal nötig |
| `src/app/models.py:204` | `ForecastDataPoint.thunder_level_signals: Optional[list[str]]` — das Feld existiert bereits |
| `src/output/renderers/comparison.py:329-342`, `compare_html.py:992-1004` | Compare-Stundentabelle (S3-Vorbild) reicht `dp.thunder_level_signals` **roh** durch, ohne `union_of_max_carriers()` — dokumentierter dünnster Punkt (s. Risiken) |

## Existing Patterns

- **Seitenkanal-Muster** (`row["_hail_flag"]`, `row["_wind_dir_deg"]`): Zusatzinformation reist neben dem eigentlichen Zellwert im `dict`, wird in `fmt_val()` per `row.get(...)` gelesen. `row["_thunder_signals"]` folgt exakt demselben Muster.
- **Pro-Stunde vs. Nacht-Block**: `_dp_to_row()` liest den rohen Wert eines einzelnen `dp` (kein Aggregieren nötig — `dp.thunder_level_signals` passt exakt zur gezeigten Stunde). Die Nacht-Block-Methode fasst mehrere `dp` zu einer Zeile zusammen und MUSS deshalb aggregieren (`union_of_max_carriers`, Muster `hail_priority`).
- **Zusatz an der Aufrufstelle, nicht im Rumpf** (`_fmt_thunder`-Docstring, Issue #1680 S3): Die Formatierlogik lebt zentral in `fmt_val()`, aber der Seitenkanal wird an jeder Konstruktionsstelle einzeln gesetzt — kein Rumpf-Zusatz, der versehentlich auch andere Aufrufer verändert.
- **Additiv, Default `None`/leere Liste**: Alle bisherigen Erweiterungen (`hail_flag`, `thunder_level_max_signals`) sind additive Felder mit sicherem Default — kein Bestandsaufrufer bricht.

## Dependencies

- **Upstream:** `dp.thunder_level_signals` (bereits live seit S1, durch `thunder_enrichment.py` befüllt), `union_of_max_carriers()`/`thunder_signal_label()` (`metric_format.py`, seit S1/S2 live).
- **Downstream:** `fmt_val()` wird sowohl von der Trip- als auch der Compare-Stundentabelle genutzt — eine Änderung dort wirkt auf **beide**. Muss daher rückwärtskompatibel sein (Default-Parameter, kein Verhaltenswechsel ohne gesetzten Seitenkanal).

## Existing Specs

- `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md`
- `docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md`
- `docs/specs/modules/feat_1680_s3_gewitter_herkunft_vier_orte.md`
- `docs/reference/metric_output_matrix.md` Zeile 110-112 (aktueller Live-Stand, gerade auf `main` gemergt)

## Risiken & Beobachtungen

1. **Ampel-/Kreis-Modus hat keinen Platz für Text.** Im HTML-Ampel-Modus rendert `fmt_val()` einen farbigen Kreis (`_ampel_dot_css`), keinen Text. Hagel bekommt dort einen Doppelring — für die Herkunft (variable Liste aus bis zu 4 Zutaten) gibt es kein Äquivalent, und keine der Scheiben S1-S3 hat je einen visuellen Indikator für die Herkunft gebaut (immer Text). **Vorschlag für die Spec:** Herkunft nur im Klartext-/Roh-Modus (`mode == "raw" or not html`), Ampel-Kreis-Modus bewusst unverändert — analog zur bestehenden Grenze „Stufe selbst bleibt unberührt" (AC-10 aus S2/S3).
2. **Zwei verschiedene Konstruktionsstellen, zwei verschiedene Aggregationsregeln.** Pro-Stunde-Zeile: roher Durchgriff (`dp.thunder_level_signals`). Nacht-Block-Zeile: `union_of_max_carriers()` über mehrere `dp`. Wer das verwechselt, baut entweder einen unnötigen Aggregationsaufruf für eine einzelne Stunde oder — schlimmer — lässt die Nacht-Block-Zeile eine falsche Einzelstunden-Herkunft zeigen.
3. **Bekannter dünnster Punkt aus S3 (Compare):** Der rohe Durchgriff auf `dp.thunder_level_signals` hält die „Stufe NONE ⇒ keine Herkunft"-Garantie NICHT aus eigener Kraft, sondern nur weil `thunder_signal_carriers()` bei `NONE` bereits `[]` liefert. Gilt für die Trip-Pro-Stunde-Zeile genauso — braucht dieselbe Gegenprobe wie `test_ac16_...` in S3.
4. **`email/helpers.py::dp_to_row()` (klein geschrieben, ohne führenden Unterstrich) ist für Trip-Mail toter Code** (s. Memory `reference_dp_to_row_dead_code_duplicate_trip_report`). Wirkort ist ausschließlich `trip_report.py::TripReportFormatter._dp_to_row()`. Nicht verwechseln — 13 Testdateien rufen die tote Funktion isoliert auf.
5. **`fmt_val()` ist geteilt zwischen Trip und Compare.** Jede Änderung am `thunder`-Zweig muss mit den S1/S3-Compare-Tests kompatibel bleiben (Regressionsgefahr, Pendant-Sperre/Renderer-Gate greift bei beiden Dateien).
6. **Kein Eingriff in `HourlyValue` oder `aggregate_stage()`** — bewusst außerhalb dieser Scheibe (siehe Known Limitation 7, S1/S2/S3). Betrifft nur den Mehrtages-Ausblick und die Gewitter-Vorschau, nicht die Trip-Stundentabelle.

## Analysis

### Type
Feature (Erweiterung eines bestehenden, dreimal wiederholten Musters — kein Bug).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | `_dp_to_row()` (Zeile ~687): `row["_thunder_signals"] = getattr(dp, "thunder_level_signals", None)` — roher Durchgriff, analog `_hail_flag`. Nacht-Block-Methode (Zeile ~649): `row["_thunder_signals"] = union_of_max_carriers((dp.thunder_level, getattr(dp, "thunder_level_signals", None)) for dp in dps)` — Aggregation über mehrere `dp` |
| `src/output/renderers/email/helpers.py` | MODIFY | `fmt_val()`, `key == "thunder"`-Zweig (Zeile ~750-753): im Klartext-/Roh-Pfad `teile`-Liste analog `_fmt_thunder()` aufbauen (Label → Signale via `thunder_signal_label()` → Hagel-Hinweis), mit `" · "` verbinden. Ampel-Kreis-Zweig bleibt unverändert (kein Textplatz) |
| `tests/tdd/test_thunder_origin_trip_hour_table.py` | CREATE | ACs für beide Konstruktionsstellen (Pro-Stunde, Nacht-Block) × beide Ausgabemodi (Klartext/Roh, HTML-Ampel unverändert) + Gegenprobe „NONE ⇒ keine Herkunft" (S3-Lehre) |
| `docs/reference/metric_output_matrix.md` | MODIFY (nach Liefer-Stand) | Zeile 111/112 aktualisieren: Trip-Stundentabelle von „weiterhin ohne" nach „live" verschieben |

### Scope Assessment
- Files: 3 Produktivpfad-relevant (2 `src/`, 1 Test) + 1 Doku-Nachzug
- Estimated LoC: **+35/-5** (Seitenkanal an 2 Stellen ~10 Zeilen, `fmt_val()`-Erweiterung ~15 Zeilen, Rest Kommentar/Docstring)
- Risk Level: **LOW-MEDIUM** — `fmt_val()` ist geteilt mit Compare (Regressionsgefahr bei falscher Parameterreihenfolge/Default), aber additiv mit sicherem Default (`row.get("_thunder_signals")` liefert `None`, wenn nicht gesetzt → zeichengleiches Verhalten für alle Alt-Aufrufer)

### Technical Approach

Zwei Konstruktionsstellen, zwei Regeln — deckungsgleich mit dem bereits etablierten `_hail_flag`-Muster in derselben Datei:

1. **Pro-Stunde** (`_dp_to_row`): roher Durchgriff auf `dp.thunder_level_signals`, keine Aggregation nötig (eine Zeile = ein Datenpunkt). Trägt dieselbe Garantie-Lücke wie die Compare-Stundenzelle (S3-Finding) — deshalb Pflicht-Gegenprobe im Test.
2. **Nacht-Block**: `union_of_max_carriers()` über alle `dp` des Blocks, exakt wie `hail_priority()` für `_hail_flag` an derselben Stelle.
3. **Formatierung**: `fmt_val()`s Klartext-Zweig übernimmt das `_fmt_thunder()`-Muster aus Compare (`teile`-Liste, `" · "`-Join) — keine neue Formatierlogik, Wiederverwendung des etablierten Wortlauts (`thunder_signal_label()`, `THUNDER_SIGNAL_LABEL_DE`).
4. **Ampel-Kreis-Modus bleibt unverändert** (Empfehlung, s. Risiko 1 oben) — konsistent mit S1-S3, die nie einen visuellen Indikator für die Herkunft gebaut haben, nur Text. Wird als eigenes AC in der Spec festgehalten, damit es explizit freigegeben wird statt stillschweigend zu gelten.

### Dependencies
- Upstream: `dp.thunder_level_signals` (live seit S1), `union_of_max_carriers()`/`thunder_signal_label()` (live seit S1/S2) — keine neuen Bausteine nötig.
- Downstream: `fmt_val()` wird auch von Compare genutzt — Renderer-Commit-Gate (#811) greift auf beide geänderten Dateien (`trip_report.py`, `email/helpers.py` matcht `email/*.py`). Vor Commit: `test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py` Exit 0.

### Open Questions
- [ ] Ampel-Kreis-Modus bewusst ohne Herkunft lassen (Empfehlung oben) — wird als AC zur Freigabe vorgelegt, keine Blockade hier.

## Bewusst NICHT in dieser Scheibe

- Mehrtages-Ausblick, Gewitter-Vorschau (brauchen `HourlyValue`-Erweiterung + `aggregate_stage()`-Anschluss)
- Go-DTO / Frontend (kein Verbraucher, s. S3-Begründung)
- SMS / Premium-SMS (PO-Entscheid seit S1: aktiv ohne Herkunft)
- Ampel-Kreis-/HTML-Indikator-Modus (s. Risiko 1)
