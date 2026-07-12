# Context: feat-1214-metric-format-slice3

## Request Summary
Issue #1214 Scheibe 3: `src/output/renderers/email/helpers.py::fmt_val` (die zentrale Formatierungs-Funktion für JEDES Trip-Briefing — E-Mail HTML/Plain, Telegram) soll die in Scheibe 1+2 gebauten Bausteine aus `src/output/metric_format.py` nutzen, wo dies ohne Verhaltensänderung möglich ist. Deutlich höheres Blast-Radius als Scheibe 1+2 (Compare-Mail ist ein optionales Feature; `fmt_val` läuft bei JEDEM Versand).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:450-595` | `fmt_val` — ~15 metrikspezifische Zweige, siehe Klassifikation unten |
| `src/output/renderers/email/helpers.py:45-58` | `_effective_format_mode` — bereits Thin-Wrapper auf `loader._resolve_format_mode` (Issue #444, schon erledigt) |
| `src/output/renderers/email/helpers.py:380-434` | `_level_from_thresholds`, `ampel_dot`, `ampel_level` — bestehende Ampel-Infrastruktur (Trip-Briefing), analog zu `severity_for` aus Scheibe 1 |
| `src/output/renderers/trip_report.py:695-810` | `_fmt_val`-Methode — KEINE reine Kopie von `helpers.fmt_val`, hat eigene Divergenzen (2-Stufen-Highlight statt 4-Stufen-Ampel, fehlt Orange-Schwelle; toter CAPE-Pfad; verbotene englische Sichtweite-Wörter) — **Scheibe 4, nicht Teil dieses Workflows** |
| `src/output/renderers/narrow.py:65` | Telegram-Aufrufer, nutzt nur `friendly_keys`+`row`, nie `format_modes`/`indicator_keys`, immer `html=False` |
| `src/output/renderers/email/plain.py:49,64` | Plain-Text-Aufrufer, nutzt `friendly_keys`+`format_modes`, nie `indicator_keys`, nie `html=True` |
| `src/output/renderers/email/html.py:549,667` | Haupt-Aufrufer (Desktop-Tabelle mit voller Ampel-Logik; mobiler Plain-Fallback) — nutzt alle vier Parameter |
| `.claude/hooks/briefing_mail_validator.py` | Greift diesmal ECHT (nicht No-Op wie bei Compare) — prüft Stundentabellen-Heuristik, Temperatur-Range, Wind-Toleranz (±3 km/h), Sonnenschein-Toleranz (±5 min) gegen echte zugestellte Mail |

## Zweig-Klassifikation (vollständig, siehe Analyse-Agent-Bericht für Details)

**(a) Sicher migrierbar — Katalog-`decimals` stimmt bereits überein:**
`wind`/`gust`/`precip`/`pop`/`cape`/`freeze_lvl` — reine Zahlenformatierung kann auf `format_value` umgestellt werden; die HTML-Ampel-Levelquelle dieser 5 Metriken (wind/gust/precip/pop/cape) kann auf `severity_for` umgestellt werden (identisches Vokabular). Das CSS-Dot-Markup (`_ampel_dot_css`) bleibt lokal — kein `tone_css`-Äquivalent für Dots in dieser Scheibe.

**(b) Bewusste Ausnahme — echte Sonderregel, nicht katalog-ableitbar:**
- `thunder` — Wort-vs-Symbol je Modus, kein numerischer Katalogwert
- `temp`/`felt`/`dewpoint` — fix `.1f`, Katalog hätte `decimals=0`/`None`→0: Migration würde Tabellenpräzision sichtbar ändern (z.B. 14.2°C → 14°C)
- `cloud*` — Emoji-Schwellen 10/30/70/90 nicht im Katalog (`cloud_total` hat keine `display_thresholds`)
- `sunshine` — DNI/WMO/is_day-Emoji-Logik, komplett katalogfremd
- `snow_limit`/`snow_depth` — Falsy-0-Sonderfall (`if val else "–"`)
- `humidity` — kein Runden überhaupt, Katalog-Runden wäre Verhaltensänderung
- `pressure` — `.1f` vs. Katalog `decimals=None`→0
- `visibility` — ECHTE variable Rundung (`>=10000m→0, sonst 1 Dezimalstelle`), divergiert genuin von `format_value`s festem `decimals=1`

**(c) Reine Orchestrierung, unangetastet:**
Format-Modi-Präzedenz-Header (`mode`/`_use_ampel`-Berechnung), `wind_dir` (Modus-Logik, nicht Werteformatierung), Kompass-Anhängsel-Merge.

## Risks & Considerations
- **Asymmetrische Aufrufer:** `narrow.py`/`plain.py`/`html.py` übergeben unterschiedliche Teilmengen der vier Parameter (`friendly_keys`/`html`/`row`/`format_modes`/`indicator_keys`) — Migration darf die Funktions-Signatur/das Verhalten für KEINEN der drei brechen.
- **Fragilste Testsuiten:** `test_issue_435_format_modes.py`, `test_issue_759_email_ampel.py`, `test_issue_810_raw_format_ampel.py`, `test_issue_811_mode_matrix.py`, `test_ampel_css_dots.py`, `test_issue_831_mobile_einfach.py` — prüfen exakte String-/Farboutputs pro Modus-Kombination, brechen am ehesten bei falscher Migration.
- **Gate-Konsequenz:** Da diese Dateien echte Trip-Briefing-Dateien sind, greift `briefing_mail_validator.py` ECHT (nicht No-Op) — braucht eine echte, frisch versendete Trip-Briefing-Test-Mail zur Validierung vor dem Commit (anders als bei Compare in Scheibe 2).
- Scheibe 4 (`trip_report._fmt_val`) explizit NICHT Teil dieses Workflows, trotz gefundener eigener Bugs dort — separater Workflow, da eigene Root-Cause-Analyse + eigene ACs nötig.

## Existing Specs
`docs/specs/modules/issue_435_metric_format_modes.md` (Format-Modi-System, bleibt unverändert), `docs/specs/modules/issue_1214_metric_format_slice1_2.md` (Vorgänger-Scheibe, Architektur-Entscheidungen gelten fort).

## Analysis

### Kritischer Fund: `format_value` ist NICHT direkt einsetzbar für die Zahl
`format_value(metric_id, value, style="plain")` hängt IMMER die Einheit an (`"45 km/h"`). `fmt_val`s 6 migrierbare Zweige geben bewusst nackte Zahlen zurück (Einheit steht in der Spalten-Überschrift der Trip-Briefing-Tabelle) — ein naiver Aufruf hätte in JEDER Briefing-Zelle die Einheit eingefügt (Bruch aller Snapshot-Tests) und beim Wind mit dem Kompass-Anhängsel kollidiert (`"45 km/h N"` statt `"45 N"`). Die zunächst vermutete Tausendertrenner-Gefahr besteht NICHT (`format_value` nutzt nur `.{decimals}f}`, keine Gruppierung — das betrifft nur die separate, unveränderte `format_metric_value`).

### Technische Entscheidung (Tech-Lead, 2026-07-12)
`format_value` wird um einen neuen, additiven Stil `style="bare"` erweitert (reine Zahl, gerundet auf Katalog-`decimals`, inkl. `display_unit`-Konvertierung falls gesetzt, aber OHNE Einheiten-Suffix). Bestehendes `style="plain"`-Verhalten bleibt unverändert (Koexistenz, kein Bruch bestehender Scheibe-1-Tests). `fmt_val`s 6 migrierbare Zweige (`wind`/`gust`/`precip`/`pop`/`cape`/`freeze_lvl`) rufen `format_value(metric_id, val, style="bare")` für die Zahl auf; Ampel-Dot/Kompass-Anhängsel-Logik bleibt lokal in `helpers.py`.

**Ampel-Level-Migration:** NUR `fmt_val`s lokaler Ampel-Aufruf für die 5 Ampel-fähigen Metriken (wind/gust/precip/pop/cape) wird auf `severity_for(metric_id, val)` umgestellt — NICHT `ampel_level`/`html.py:574` selbst (das wird von `html.py` für beliebige Metriken zur Zell-Tönung genutzt, eine zentrale Umstellung hätte größeren, hier nicht beabsichtigten Blast Radius, u.a. weil `ampel_level` bei fehlenden Thresholds `"green"` liefert, `severity_for` aber bewusst `None` — Scheibe-1-Fix). Das CSS-Dot-Markup (`_ampel_dot_css`) bleibt lokal, keine `tone_css`-Migration für Dots in dieser Scheibe.

**Katalog-Verifikation:** Alle 5 Ampel-Metriken haben vollständige, nicht-invertierte Standard-Schwellen (`wind` 30/50/70, `gust` 50/65/80, `precipitation` 1/5/10, `rain_probability` 30/60/80, `cape` 1000/2500/3500) — keine hat die Visibility-Lücke aus Scheibe 1, `severity_for` liefert für alle 5 einen validen Level, nie `None`.

### Scope Assessment
- `src/output/metric_format.py`: neuer `style="bare"`-Zweig in `format_value` (+~15-20 LoC + Tests)
- `src/output/renderers/email/helpers.py`: 6 Zweige in `fmt_val` umgestellt (~30-50 LoC Diff)
- Betroffene Tests: `tests/tdd/test_metric_format.py` (neue bare-Style-Tests), `tests/tdd/test_issue_759_email_ampel.py`, `tests/tdd/test_issue_810_raw_format_ampel.py`, `tests/tdd/test_ampel_css_dots.py`, `tests/red/test_issue_435_format_modes.py` (Regressionsschutz)
- Risk Level: MEDIUM (kleiner, isolierter Diff dank Erkenntnis aus Punkt 1, aber kritischer Rendering-Pfad — braucht echten Trip-Briefing-Testmail-Nachweis für `briefing_mail_validator.py`)

### Explizit NICHT Teil dieser Scheibe
- `ampel_level`/`html.py:574` (zentrale Ampel-Migration — eigener, kleinerer Folge-Workflow falls gewünscht)
- Alle "(b)"/"(c)"-klassifizierten Zweige aus der Vorrecherche (thunder, temp/felt/dewpoint, cloud*, sunshine, snow_limit/depth, humidity, pressure, visibility, wind_dir-Modus-Logik)
- `trip_report.py::_fmt_val` (Scheibe 4, eigene gefundene Bugs dort brauchen eigene Root-Cause-Analyse)
