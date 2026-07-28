# Context: fix-1377-ampel-schwellen-ssot

Issue: [#1377](https://github.com/henemm/gregor_zwanzig/issues/1377) — S5 im Ortsvergleich-Rework (#1374/#1372)

## Request Summary

Dieselbe Vorhersage bekommt im Trip-Briefing und in der Ortsvergleichs-Mail verschiedene
Warnfarben, weil mehrere unabhängige Stellen die Schwellen für Gelb/Orange/Rot führen.
Alle sollen auf den zentralen Metrik-Katalog zurückgeführt werden — mit vorgeschalteter
PO-Vorlage je abweichender Größe (Auflage aus dem Issue).

## Ist-Stand: die Schwellenquellen

Das Issue nennt sechs Fundstellen. Die Bestandsaufnahme findet **sieben** Entscheider,
davon zwei bereits teilweise auf den Katalog zurückgeführt (Vorarbeit #1214 Scheibe 1+2).

| # | Fundstelle | Rolle |
|---|---|---|
| 1 | `src/app/metric_catalog.py` — `display_thresholds` | Zentraler Katalog (Soll-Quelle) |
| 2 | `src/output/metric_format.py:103-144` `severity_for` | Katalog-Leser, kanonisches Vokabular |
| 3 | `src/output/renderers/email/helpers.py:498-515` `_level_from_thresholds` + `:561-573` `ampel_level` | Zweiter, wortgleicher Katalog-Leser |
| 4 | `src/output/renderers/email/html.py:615-628` | Zellfärbung Trip-Stundentabelle, hartcodiert |
| 5 | `src/output/renderers/email/html.py:147-161` `_row_risk` | Zeilen-Ampel Trip, eigene grobe 3-Stufen |
| 6 | `src/output/renderers/email/outlook.py:57-72, 197-200` | Trip-Ausblick, eigene Schwellen-Tupel |
| 7 | `src/output/renderers/email/compare_html.py:88-123` (`_sev_*`) | Ortsvergleich, acht eigene Funktionen |

### Schwellen im Vergleich (Gelb / Orange / Rot)

| Größe | Katalog (Soll) | Trip-Stundentabelle | Trip-Ausblick | Ortsvergleich |
|---|---|---|---|---|
| Niederschlag mm | 1 / 5 / 10 | >1 / >4 / >8 | ≥2 / ≥5 / ≥8 | >1 / >4 / >8 |
| Regenwahrscheinlichkeit % | 30 / 60 / 80 | >50 / >70 / >85 | ≥50 / ≥70 / ≥85 | ≥40 / ≥60 / ≥80 |
| Böen km/h | 50 / 65 / 80 | >30 / >45 / >60 | ≥30 / ≥45 / ≥60 | >30 / >45 / >60 |
| Wind km/h | 30 / 50 / 70 | >20 / >30 (nur 2 Stufen) | ≥20 / ≥30 (2 Stufen) | **Katalog** (seit #1214) |
| Sichtweite | nur `orange_lt` 500 m | <2 / <1 / <0,5 km | — | <5000 / <3000 / <1000 m |
| Temperatur °C | **keine** | — | — | ≥28 / ≥31 / ≥34 |
| UV-Index | **keine** | — | — | ≥3 / ≥6 / ≥8 |
| CAPE J/kg | 300 / 800 / 1500 | — | — | **Katalog** (seit #1214) |
| Gewitter | keine | >20 / >30 (`_row_risk`: >20) | MED/HIGH | MED/HIGH |

**Drei Befunde, die über das Issue hinausgehen:**

1. **Der Ausblick ist eine siebte Quelle** mit nochmals eigenen Werten — Niederschlag
   startet dort erst bei 2 mm gelb, in der Stundentabelle derselben Mail schon bei 1 mm.
   Damit weicht das Trip-Briefing bereits **in sich selbst** ab, nicht nur gegen den Vergleich.
2. **Die Trip-Stundentabelle hat zwei Pfade nebeneinander** (`html.py:603-628`): Spalten in
   `indicator_keys` gehen über `ampel_level` (Katalog), alle anderen über die hartcodierte
   `elif`-Kette. Derselbe Messwert kann also je nach Spaltenkonfiguration verschieden gefärbt
   werden — innerhalb einer Mail.
3. **Der Katalog kann heute nicht alles bedienen.** Schwellen existieren nur für `wind`,
   `gust`, `precipitation`, `rain_probability`, `cape` und — unvollständig — `visibility`.
   Für **Temperatur, UV-Index und Gewitter**, die der Ortsvergleich färbt, hat der Katalog
   keine Werte. Ohne Katalog-Erweiterung würden diese Spalten farblos.

### Sichtweite: bekannte Sperre

`severity_for` unterstützt **invertierte Schwellen** (niedriger = kritischer) bewusst nicht
(`metric_format.py:113-117`, dokumentierte Known Limitation aus #1214). Der Katalog führt für
Sichtweite nur `orange_lt: 500`. Die Sichtweite ist damit nicht nur ein Schwellen-, sondern ein
**Datenmodell-Thema** — sie ist der aufwendigste Teil der Umstellung.

Zusätzlich uneinheitlich: die Einheit. Trip rechnet in Kilometern, Vergleich in Metern
(`compare_html.py:117-119` vs. `html.py:625-628`), mit Heuristik `>100 ⇒ Meter`.

## Vokabular und Farben

- Kanonisch: `green/yellow/orange/red` (`severity_for`, `ampel_level`)
- Ortsvergleich-lokal: `ok/caution/warn/danger`, übersetzt in `compare_html.py:62-63`
- Die Übersetzung ist verlustfrei; die Umbenennung ist reine Aufräumarbeit ohne sichtbare Wirkung
- Farbwerte: `#fbeeb8` / `#fad6b8` / `#f6c5bf` stehen hartcodiert in `html.py:608-628`,
  `outlook.py:67-71,157` und kommen im Vergleich bereits aus `tone_css` (`compare_html.py:70-74`).
  Die Werte sind identisch ⇒ die Umstellung auf `tone_css` ist sichtbar folgenlos.

## Bestehende Muster

- **#1214 Scheibe 1+2 ist das Vorbild:** Wind und CAPE wurden bereits auf `severity_for`
  umgestellt, inklusive bewusst in Kauf genommener sichtbarer Änderung, dokumentiert im
  Code-Kommentar (`compare_html.py:93-97`). Genau dieses Muster setzt #1377 fort.
- `metric_format.py:122-125` benennt die Doppelung zu `helpers.ampel_level` selbst als
  aufgeschobene Konsolidierung — Punkt 2 des Issues ist also vorbereitet.

## Abhängigkeiten

- **Aufwärts:** `metric_catalog.get_metric()`, `design_tokens.tone_css`
- **Abwärts:** Trip-Mail (`html.py`, `outlook.py`), Ortsvergleichs-Mail (`compare_html.py`),
  Warnblock/amtliche Warnungen (`_ALERT_LEVEL_CELL` — **eigene Farbskala, bleibt unberührt**)

## Risiken

1. **Renderer-Commit-Gate #811 greift zwingend** — alle betroffenen Dateien stehen auf der
   Liste. Vor jedem Commit: Modus-Matrix-Test grün + frischer Briefing-Validator-Lauf.
2. **Beide Mail-Pfade brauchen Nachweis** — Trip-Briefing über `briefing_mail_validator.py`,
   Ortsvergleich über `email_spec_validator.py`. Beide gegen echte Staging-Mails.
3. **Sichtbare Änderung ist gewollt, aber PO-pflichtig** — die Vorlage je Größe ist Auflage,
   nicht Kür.
4. **Katalog-Erweiterung nötig** (Temperatur, UV, Gewitter, invertierte Sichtweite) — sonst
   verliert der Ortsvergleich Farben. Das ist der Scope-Treiber.
5. **Bestehende Tests nageln die alten Werte fest** — u.a. `test_official_alert_badge_color.py`
   lockt laut Kommentar `_RISK_CELL`. Mitziehen statt Schwellen anpassen
   (Test-Schwellen niemals anheben, um grün zu werden).
6. **Staging-Verifikation kostet Kontingent** — ein Versand je Mail-Art, dann per IMAP prüfen.

## Analysis

### Type
Bug (nutzersichtbares Fehlverhalten, `[triage:a]`)

### PO-Entscheidung Schwellen (2026-07-28, Auflage aus #1377 erfüllt)

| Metrik | Gelb | Orange | Rot | Herkunft / Wirkung |
|---|---|---|---|---|
| `gust` | 30 | 45 | 60 | **Katalog wird angepasst** (bisher 50/65/80). Mail-Optik bleibt unverändert |
| `rain_probability` | 30 | 60 | 80 | Katalog bleibt. Beide Mails färben früher als heute |
| `precipitation` | 1 | 5 | 10 | Katalog bleibt. Rot kommt später (bisher 8) |
| `wind` | 30 | 50 | 70 | Katalog bleibt. Trip färbt später, bekommt erstmals Rot |
| `visibility` | <2000 m | <1000 m | <500 m | **Katalog wird erweitert** (invertiert). Trip-Optik bleibt, Compare färbt später |
| `temperature` | 28 | 31 | 34 | **Neu im Katalog** (heutige Compare-Werte). Trip färbt künftig ebenfalls |
| `uv_index` | 3 | 6 | 8 | **Neu im Katalog** (heutige Compare-Werte). Trip färbt künftig ebenfalls |

### Gewitter: bewusst NICHT Teil dieses Fixes

Trip-Stundentabelle färbt Gewitter über eine **Prozentzahl** (`thunder_pct`, `html.py:222,623`),
der Ortsvergleich über die **Stufe** MED/HIGH (`compare_html.py:131`). Der Katalog führt
`thunder` mit `dp_field="thunder_level"` — die Stufe ist also die kanonische Größe.

Das ist keine Schwellen-, sondern eine **Datenform-Divergenz**: zwei Seiten messen dasselbe
Phänomen in verschiedenen Einheiten. Eine gemeinsame Schwelle kann das nicht auflösen. Gehört
damit zu Epic #1372 („eine Größe, mehrere Auswertungen"), nicht hierher. In #1377 bleibt die
Gewitter-Färbung auf beiden Seiten **unverändert**.

### Affected Files

| File | Change | Beschreibung |
|---|---|---|
| `src/app/metric_catalog.py` | MODIFY | `gust` anpassen; `visibility` invertierte Bänder; `temperature`, `uv_index` neu |
| `src/output/metric_format.py` | MODIFY | `severity_for` lernt invertierte Schwellen (hebt Known Limitation aus #1214 auf) |
| `src/output/renderers/email/helpers.py` | MODIFY | `_level_from_thresholds` entfällt, `ampel_level` delegiert an `severity_for` |
| `src/output/renderers/email/html.py` | MODIFY | `elif`-Kette :615-628 → `severity_for` + `tone_css`; `_row_risk` konsistent |
| `src/output/renderers/email/outlook.py` | MODIFY | `_outlook_cell_bg` → `severity_for` + `tone_css` |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_sev_*` entfallen; Vokabular kanonisch |
| `tests/golden/email/*.txt` (4 Dateien) | MODIFY | Mail-Schnappschüsse mitziehen |
| `tests/fixtures/outlook_trip_parity/*.html` | MODIFY | Ausblick-Paritäts-Fixture mitziehen |
| ~10 Testdateien in `tests/tdd/` | MODIFY | nageln heute alte Schwellen/Farben fest |

### Scope Assessment
- Dateien: 6 Quell-Dateien + ~15 Test-/Fixture-Dateien
- LoC: grob +180 / −140 im Quellcode (viel Ersatz, wenig Zuwachs)
- Risiko: **MEDIUM-HIGH** — nutzersichtbarer Mail-Inhalt beider Pfade, Gate #811 greift

### Technischer Ansatz — Empfehlung: zwei Scheiben

**Scheibe A (unsichtbar):** Katalog auf die entschiedenen Werte bringen und `severity_for`
invertierte Schwellen beibringen. Danach kann der Katalog alles, was die Mails brauchen —
**ohne dass sich eine einzige Mail ändert**, weil noch niemand die neue Fähigkeit nutzt.
Prüfbar allein mit deterministischen Tests.

**Scheibe B (sichtbar):** Die vier Renderer-Stellen auf `severity_for` + `tone_css`
verdrahten, `_level_from_thresholds` löschen, Vokabular vereinheitlichen. Erst hier ändern
sich Mails, Golden-Dateien und Farben — mit Staging-Nachweis beider Mail-Arten.

Begründung: Scheibe A hat null Regressionsrisiko und macht Scheibe B zu reiner Verdrahtung.
Bei einem Fehlschlag in B ist der Katalog trotzdem schon sauber. Das folgt dem Muster, mit
dem #1214 Scheibe 1+2 bereits Wind und CAPE erfolgreich umgestellt hat.

### Dependencies
`metric_catalog.get_metric()` · `design_tokens.tone_css` · Gate #811 (Renderer-Commit-Gate)

### Open Questions
- [x] Schwellenwerte je Größe — PO-Entscheidung 2026-07-28, s.o.
- [x] Gewitter — abgegrenzt nach #1372
- [ ] Zeilen-Ampel `_row_risk`: mitziehen oder eigenständig lassen? (s.u.)

## Offene Frage für die Spec

Ob die Zeilen-Ampel `_row_risk` (`html.py:147-161`, grobe 3-Stufen `ok/watch/risk`) mit
umgestellt wird oder als eigenständige Zeilen-Zusammenfassung bestehen bleibt — sie beantwortet
eine andere Frage („ist in dieser Stunde irgendetwas auffällig?") als die Zellfärbung
(„wie schlimm ist dieser eine Wert?"). Sie nutzt aber dieselben Zahlen und muss mindestens
konsistent zu den neuen Schwellen sein.
