---
entity_id: fix_1927_risk_dot_kombi_regel
type: bugfix
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.1"
tags: [trip-briefing, html-renderer, risk-dot, metric-format]
workflow: fix-1927-risk-dot-kombi-regel
---

# Risk-Punkt: echte 4-Stufigkeit + fachliche Kombi-Eskalation (Issue #1927, Wiedereröffnung)

## Approval

- [ ] Approved (Revision v1.1 — wartet auf Freigabe der geänderten ACs)
- [x] Approved (Henning, 2026-08-19) — **galt für v1.0**, durch Adversary-Verdict
  BROKEN und PO-Scope-Entscheid vom 2026-08-19 abgelöst (siehe Changelog).

## Purpose

Der Risk-Punkt am Zeilenende einer Trip-Briefing-Stundentabelle (`_row_risk()`)
kollabiert aktuell die 4 Ampelstufen der Einzelzellen (grün/gelb/orange/rot) auf ein
3-wertiges Vokabular (`ok`/`watch`/`risk`) — "gelb" und "orange" landen beide auf
Punktfarbe Orange. Diese Spec macht den Punkt echt 4-stufig (zeigt künftig auch Gelb)
und führt zusätzlich eine eng begrenzte, fachlich begründete Kombi-Eskalation ein:
**drei** fest definierte Metrik-Paare eskalieren die Zeile eine Stufe höher, wenn beide
Partner gleichzeitig gelb sind — unabhängige Gelb-Kombinationen eskalieren nicht.

**Revision v1.1 (2026-08-19):** Der Adversary-Dialog gegen v1.0 stellte fest, dass 3
von 4 ursprünglich geplanten Paaren über den echten Datenpfad `_row_risk()`
strukturell nie erreichbar waren (Verdict: BROKEN — Details Changelog). Nach PO-Entscheid
wird das Gewitter-Paar per Verdrahtungskorrektur nachgezogen (keine neue Schwelle nötig),
das Neuschnee-Paar erhält eine extern belegte Schwelle (SLF/EAWS), und die Paare
Nullgradgrenze sowie Schneehöhe werden mangels belastbarer Ampel-Absolutwerte
zurückgestellt (siehe Non-Goals/Known Limitations).

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `def _row_risk(r: dict) -> str` (Zeile 202-237), `_RISK_LEVEL_TO_AMPEL` (Zeile 245)
- **File:** `src/output/metric_format.py`
- **Identifier:** neue Funktion neben `severity_for`/`severity_from_thresholds` (Zeile ~130-196), Kandidat-Name `escalate_pair_watch()` o.ä.

> Schicht: Python-Core / Domain-Backend (`src/output/`, FastAPI-Core-Renderer). Kein
> Frontend-, Go-API- oder Alarm-/Versandpfad betroffen.

## Estimated Scope

- **LoC:** ~150-250 (Produktivcode ~50-90, Testcode ~100-160)
- **Files:** 4 (2 Produktivdateien, 2 Testdateien angepasst/neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `severity_for()` / `severity_from_thresholds()` (`src/output/metric_format.py:130-196`) | function | SSoT-Ampel-Bewertung pro Einzelmetrik anhand Katalog-Schwellen — bleibt unverändert, wird von der neuen Kombi-Funktion konsumiert |
| `metric_catalog.py` (`display_thresholds`) | data | Liefert Gelb/Orange/Rot-Schwellen je Metrik (u.a. `precipitation`, `rain_probability`, `wind`, `gust`, `visibility`, `uv_index`) |
| `_AMPEL_DOT_COLORS` (`src/output/renderers/email/helpers.py:591-596`) | data | Zielpalette für Punktfarben, bereits vollständig 4-stufig (`green`/`yellow`/`orange`/`red`) — unverändert |
| `_thunder_risk_level()` (`html.py`, nahe `_row_risk`) | function | Hartcodierte Gewitter-Zellfärbung ohne Katalog-Schwellen (bestehendes Known Limitation, unverändert) |
| `felt`/`wind_chill`-Metrik (`src/app/metric_catalog.py:200-218`) | metric | Bereits bestehende physikalische Wind+Temp- bzw. Temp+Feuchte-Kombination mit eigenen Schwellen — Grund, warum Windchill/Hitzeindex NICHT als eigene Paar-Regel gebraucht werden |
| `tests/tdd/test_renderer_katalog_schwellen.py` | test | Enthält `test_ac10_row_risk_gust_30_becomes_achtung` — wird durch diese Spec bewusst abgelöst |
| `tests/tdd/test_risk_dot_matches_ampel_palette.py` | test | Wird um den "yellow"-Fall ergänzt |
| `_THUNDER_AMPEL_BAND` (`src/output/metric_format.py:291-296`) | function/data | **Neu in v1.1.** Bestehende Zell-Ampel-Zuordnung `NONE→green, LOW→yellow, MED→orange, HIGH→red` — Quelle für die Gewitter-Gelb-Stufe, die `_thunder_risk_level()` in `html.py` bisher NICHT kennt (dort landet LOW zusammen mit MED auf "watch"). Kein neuer Schwellenwert, nur Angleichung an eine bereits kalibrierte Quelle. |
| SLF/EAWS "kritische Neuschneemengen" (europäische Lawinen-Gefahrenskala) | external reference | **Neu in v1.1.** Quelle für `fresh_snow`-`display_thresholds`: 10–20 cm/24h (ungünstige Verhältnisse), 20–30 cm (mittel), 30–50 cm (günstig) — https://www.avalanches.org/education/avalanche-danger-scale-2/ und SLF-Gefahrenskala-PDF. Verwendet als gelb=10, orange=20, rot=30 (konservative untere Schwelle jeder Bandbreite). |

## Implementation Details

**Slice S1 — 4-Stufen-Umstellung (Voraussetzung):**
`_row_risk()` gibt künftig statt `"ok"/"watch"/"risk"` ein 4-wertiges Vokabular
zurück, das direkt an `_AMPEL_DOT_COLORS`-Keys anschließt (`green`/`yellow`/`orange`/`red`
oder ein äquivalentes 4-wertiges internes Vokabular, das `_RISK_LEVEL_TO_AMPEL` um einen
"yellow"-Eintrag erweitert). `worst == "yellow"` liefert künftig Gelb statt Orange;
`worst == "orange"` liefert weiterhin Orange; `red`/`green`-Pfade unverändert. Gewitter-Level
`"watch"` (Gewitter unterhalb `"risk"`-Schwelle) bleibt auf mindestens Gelb/Orange gemappt
wie bisher — Detailmapping ist Implementierungssache, solange die Regressions-ACs (rot/grün
unverändert) halten.

**Slice S2 — Paar-Eskalation (auf S1 aufgesetzt), Revision v1.1:**
Neue Funktion in `metric_format.py`, aufgerufen ausschließlich von `_row_risk`. Nimmt das
Dict der Einzelmetrik-Severities der aktuellen Zeile entgegen und liefert eine optionale
Eskalation. Eine modul-level Konstante `_PAIR_WATCH_ESCALATIONS` (`metric_format.py`)
listet exakt folgende **drei** Paare aus Katalog-`col_key`s (v1.1: von ursprünglich vier
auf drei reduziert — siehe Non-Goals):

1. `precipitation` + `temperature` (Vereisungsgefahr nahe 0°C) — **produktiv, unverändert
   seit v1.0**
2. `thunder` + (`wind`/`gust`) (Blitzschlag + Böenfront-Sturzgefahr) — **v1.1:
   Verdrahtungskorrektur.** `_thunder_risk_level()` (`html.py:168-197`) mappt `LOW`
   bisher zusammen mit `MED` auf `"watch"` (Orange). Wird auf die bereits bestehende
   `_THUNDER_AMPEL_BAND`-Zuordnung (`metric_format.py:291-296`) ausgerichtet:
   `NONE→None, LOW→"yellow", MED→"watch", HIGH→"risk"`. Zusätzlich übergibt `_row_risk`
   künftig `"thunder": thunder_level` im `severities`-Dict an `escalate_pair_watch` (bisher
   fehlte dieser Key komplett — Paar 3 war dadurch strukturell nie prüfbar). Kein neuer
   Schwellenwert, reine Angleichung an eine bereits kalibrierte Quelle.
3. `visibility` + `fresh_snow` (Weg unter Neuschnee, keine Fernsicht) — **v1.1: `fresh_snow`
   erhält erstmals `display_thresholds`** in `metric_catalog.py`
   (`{"yellow": 10.0, "orange": 20.0, "red": 30.0}`, Einheit cm/24h passend zu
   `default_aggregations=("sum",)`), abgeleitet aus den SLF/EAWS-"kritischen
   Neuschneemengen" (siehe Dependencies). `snow_depth` ist **nicht mehr** Teil dieses
   Paares (v1.0-Fassung hatte `snow_depth`/`fresh_snow` als Alternativen) — für
   `snow_depth` gibt es keine belegbare Ampel-Absolutschwelle (siehe Non-Goals).

**Entfallen in v1.1:** Das ursprüngliche Paar 2 (`precipitation`/`rain_probability` +
`freeze_lvl`, Schneefall in tieferen Lagen) wird gestrichen — `freezing_level` bekommt
in dieser Spec KEINE `display_thresholds` (siehe Non-Goals). Die zugehörige AC-3 aus v1.0
entfällt ersatzlos (siehe Acceptance Criteria).

Regel unverändert: Sind beide Partner-Metriken eines Paares gleichzeitig `"yellow"`,
eskaliert die Zeile genau eine Stufe (`yellow` → `orange`). Keine weitere Eskalation bei
`yellow`+`orange`-Kombinationen. Ist nur eine Partner-Metrik gelb, erfolgt KEINE
Eskalation. Gelb-Paare außerhalb der drei gelisteten Kombinationen eskalieren NICHT.

`_row_risk` ruft zuerst die bestehende Maximalwert-Logik auf (liefert das 4-stufige
Rohergebnis aus S1), dann die neue Paar-Funktion, die bei Treffer genau eine Stufe
hochsetzt — nie mehr. Der finale Rückgabe-Zweig wird um `thunder_level == "yellow"`
ergänzt (`if worst == "yellow" or thunder_level == "yellow": return "yellow"`), damit
ein alleinstehendes `LOW`-Gewitter (kein weiterer gelber Wert in der Zeile) korrekt Gelb
statt weiterhin fälschlich Grün liefert.

## Expected Behavior

- **Input:** Dict `r` mit Rohwerten pro Trip-Briefing-Stundenzeile (`gust`, `wind`,
  `precip`, `pop`, `visibility`, `thunder`, plus neu benötigte Keys für Paar-Partner:
  `temp`, `freeze_lvl`, `snow_depth`/`fresh_snow` — je nach Katalog-`col_key` in `r`
  vorhanden oder fehlend).
- **Output:** Vierwertiger Risk-Level, gemappt auf die entsprechende Punktfarbe aus
  `_AMPEL_DOT_COLORS` (`green`/`yellow`/`orange`/`red`).
- **Side effects:** Keine. Reine Rendering-Funktion ohne Persistenz-, Alarm- oder
  Versandwirkung (`_row_risk` hat keinen zweiten Aufrufer im Repo, verifiziert).

## Acceptance Criteria

- **AC-1 (Ablösung von AC-10):** Given eine Trip-Briefing-Stundenzeile mit genau einer
  gelben Einzelmetrik ohne Partner im Paar (z.B. `gust=30`, alle anderen Metriken grün) /
  When `_row_risk()` ausgewertet wird / Then liefert die Funktion den Level, der auf
  Punktfarbe Gelb mappt (NICHT mehr Orange wie vor dieser Änderung).
  - Test: `_row_risk({"gust": 30})` liefert künftig den Gelb-Level; ersetzt/überschreibt
    `test_ac10_row_risk_gust_30_becomes_achtung` in `test_renderer_katalog_schwellen.py`.

- **AC-2 (Paar 1 — Niederschlag+Temperatur):** Given eine Zeile mit `precipitation` UND
  `temp` beide auf Gelb-Schwelle / When `_row_risk()` ausgewertet wird / Then eskaliert
  die Zeile auf Orange (Vereisungsgefahr).
  - Test: Fixture mit beiden Metriken exakt auf Gelb-Schwelle erwartet Orange-Ergebnis.

- **AC-3 (ENTFÄLLT in v1.1):** Ursprünglich Paar 2 (Niederschlag/PoP+Nullgradgrenze).
  Gestrichen — `freezing_level` bekommt keine `display_thresholds`, siehe Non-Goals.
  Kein Ersatztest; ein evtl. vorhandener Test für dieses Paar wird gelöscht, nicht
  umgeschrieben.

- **AC-4 (Paar 2 — Gewitter+Wind/Böen, v1.1 über echten Datenpfad erreichbar):** Given
  eine Trip-Briefing-Zeile mit `thunder=ThunderLevel.LOW` (bzw. String `"LOW"`) UND
  `wind`/`gust` auf Gelb-Schwelle, sonst harmlose Werte / When `_row_risk()` ausgewertet
  wird / Then eskaliert die Zeile auf Orange (`"watch"`).
  - Test: `_row_risk({"thunder": ThunderLevel.LOW, "gust": 30, ...})` → `"watch"`.
  - Zusätzliche Regressions-AC: `_row_risk({"thunder": ThunderLevel.LOW}, ...harmlos)`
    (kein Partner gelb) → `"yellow"` (NICHT mehr `"ok"` wie vor der
    Verdrahtungskorrektur, NICHT `"watch"` wie fälschlich vor v1.1 — echte Gelb-Stufe
    für alleinstehendes LOW-Gewitter).
  - Regression: `ThunderLevel.MED` alleinstehend bleibt `"watch"` (unverändert,
    `test_thunder_med_enum_becomes_at_least_watch` bleibt grün).

- **AC-5 (Paar 3 — Sicht+Neuschnee, v1.1 mit belegter Schwelle):** Given eine Zeile mit
  `visibility` gelb UND `fresh_snow >= 10` (Gelb-Schwelle SLF/EAWS) / When `_row_risk()`
  ausgewertet wird / Then eskaliert die Zeile auf Orange (Weg unter Neuschnee nicht
  erkennbar, keine Fernsicht). `snow_depth` ist NICHT mehr Partner dieses Paares.
  - Test: Fixture mit `visibility` gelb + `fresh_snow=10.0` erwartet Orange-Ergebnis.

- **AC-6 (Kein Partner, keine Eskalation):** Given eine Zeile, bei der nur eine Metrik
  eines der vier Paare gelb ist und der Partner grün oder ohne Wert bleibt / When
  `_row_risk()` ausgewertet wird / Then bleibt der Punkt Gelb, keine Eskalation auf Orange.
  - Test: Fixture mit z.B. `precipitation="yellow"`, `temp` grün erwartet Gelb-Ergebnis.

- **AC-7 (Unabhängige Gelb-Kombination, keine Eskalation):** Given eine Zeile mit zwei
  gelben Metriken, die KEINEM der vier definierten Paare angehören (z.B. `uv_index` gelb
  UND `temp` gelb) / When `_row_risk()` ausgewertet wird / Then bleibt der Punkt Gelb,
  keine Eskalation.
  - Test: Fixture mit UV+Temp beide gelb erwartet Gelb-Ergebnis (kein Orange).

- **AC-8 (Regression Rot/Grün unverändert):** Given bestehende Zeilen-Fixtures, die vor
  dieser Änderung `"risk"` (rot) bzw. `"ok"` (grün) lieferten / When `_row_risk()` nach
  der Änderung ausgewertet wird / Then liefern dieselben Fixtures weiterhin Rot bzw.
  Grün, unverändert gegenüber dem Verhalten vor dieser Spec.
  - Test: Bestehende Rot-/Grün-Fixtures aus `test_renderer_katalog_schwellen.py` und
    `test_row_risk_gewitter.py` laufen unverändert grün durch.

- **AC-9 (Windchill/Hitzeindex lösen keine zusätzliche Paar-Eskalation aus):** Given
  eine Zeile mit niedriger Temperatur und hohem Wind (Windchill-Fall) bzw. hoher
  Temperatur und hoher Luftfeuchtigkeit (Hitzeindex-Fall), wobei die kombinierte
  `felt`-Metrik bereits ihre eigene Ampel liefert / When `_row_risk()` ausgewertet wird /
  Then wird ausschließlich die `felt`-Ampel berücksichtigt, es gibt KEINE zusätzliche
  Eskalation über eine separate Wind+Temp- oder Temp+Feuchte-Paar-Regel (solche Paare
  existieren nicht in der Vier-Paar-Liste).
  - Test: Fixture mit `wind` gelb + `temp` gelb (kein `felt`-Paar in der Liste) erwartet
    KEINE Eskalation über die Kombi-Regel hinaus dessen, was die Einzelmetriken ohnehin
    liefern.

## Known Limitations

- **Nullgradgrenze-Paar (v1.0-AC-3) zurückgestellt:** `freezing_level` bekommt in
  dieser Spec KEINE `display_thresholds`. Grund ist nicht nur fehlende Quelle, sondern
  ein strukturelles Problem: Icing-Gefahr hängt vom Verhältnis Nullgradgrenze zur
  tatsächlichen Wegehöhe ab (Beispiel: 1700 m Nullgradgrenze ist harmlos im Tal,
  gefährlich auf einem 2200-m-Pass) — ein fester Absolutwert wäre über alle Trips
  hinweg (GR20 ~2000–2700 m, Karnischer Höhenweg ~1500–2200 m) nur eine grobe Näherung,
  anders als bei physikalischen Größen wie CAPE. Eine trip-relative Lösung (Vergleich
  gegen Segment-Höhe) wäre ein eigenständiges Feature-Ticket.
- **Schneehöhe (`snow_depth`) kein Paar-Partner:** Recherche (Repo + extern) fand keine
  belastbare Ampel-Absolutschwelle. Die einzigen im Repo vorhandenen Zahlen
  (`comparison_scoring.py:55-60`, ≥100/50/30 cm) sind Wintersport-Bewertungsboni —
  fachlich das Gegenteil einer Gefahren-Ampel. Externe Quellen nennen für Schneehöhe
  (im Unterschied zu Neuschnee) nur qualitative Aussagen ("schon dünne Schneedecke
  verdeckt Wegmarkierungen"), keinen Zentimeterwert.
- **Wind + Böen kein eigenständiges Paar:** `wind` und `gust` messen dieselbe Gefahr
  (Windbelastung) doppelt — keine unabhängige Verstärkung, daher keine Eskalationsregel
  zwischen diesen beiden.
- **UV + Temperatur kein Paar:** vom PO explizit als Beispiel für "kein fachlicher
  Zusammenhang" genannt — beide können unabhängig voneinander gelb sein, ohne dass sich
  ein gemeinsames Risiko ergibt.
- **Kälte + Wind (Windchill) kein eigenes Paar:** bereits vollständig durch die
  bestehende Metrik `felt`/`wind_chill` abgedeckt (`metric_catalog.py:200-218`,
  eigene Schwellen `yellow_lt: 0.0, orange_lt: -5.0, red_lt: -15.0`). Eine zusätzliche
  Wind+Temp-Paar-Regel würde dieselbe Gefahr doppelt eskalieren.
- **Hitze + Luftfeuchtigkeit (Hitzeindex) kein eigenes Paar:** ebenfalls durch `felt`
  abgedeckt — Open-Meteos `apparent_temperature` (`src/providers/openmeteo.py:392-397`)
  rechnet Wind und Feuchte bereits in eine gefühlte Temperatur ein; eigene Hitze-Schwellen
  `yellow: 28.0, orange: 31.0, red: 34.0` (`metric_catalog.py:214-217`).
- **Keine Aktivitäts-Differenzierung:** `ActivityProfile` (`src/app/profile.py:14-17`)
  beeinflusst aktuell nur Aggregationslogik und Standard-Metrik-Sichtbarkeit
  (`WEATHER_TEMPLATES`), nicht Risiko-Schwellen. Diese Spec verknüpft die Paar-Regel
  NICHT mit der Aktivität — eine einzige, aktivitätsunabhängige Paar-Liste gilt für alle
  Trips. Eine Aktivitäts-Verknüpfung wäre ein eigenständiges Feature-Ticket.
- **Keine pauschale N×Gelb=Orange-Regel:** bewusst verworfen (Fehlalarm-Risiko bei
  unabhängigen Größen, Präzedenzfall #1377 zu verstreuten Schwellenquellen). Nur die vier
  fachlich benannten Paare eskalieren.
- **Scope-Grenze auf Trip-Briefing:** `outlook.py` (Trip-Ausblick) und
  `compare_html.py` (Ortsvergleich) haben aktuell keine äquivalente "ein Punkt pro
  Zeile"-Aggregation — sie färben nur Einzelzellen über dieselbe `severity_for`-SSoT.
  Eine Ausweitung dorthin ist NICHT Teil dieser Spec (Non-Goal, siehe unten) und wäre
  ein eigenes Feature-Ticket, falls dort je ein vergleichbarer Zeilen-Indikator gewünscht
  wird.
- **Gewitter-Zellfärbung bleibt hartcodiert:** `thunder` hat weiterhin keine
  `display_thresholds` im Katalog (unverändert aus dem vorigen #1927-Zyklus). v1.1
  ändert NUR die interne `_thunder_risk_level()`-Zuordnung in `html.py` (LOW bekommt
  jetzt eine eigene Gelb-Stufe statt mit MED verschmolzen zu werden) — das ist keine
  Katalog-Erweiterung, sondern eine Angleichung an die bereits bestehende
  `_THUNDER_AMPEL_BAND`-Logik.

## Non-Goals

- Keine Ausweitung der Zeilen-Aggregation auf `outlook.py` oder `compare_html.py`.
- Keine Aktivitäts-abhängige Paar-Liste oder Aktivitäts-abhängige Schwellen.
- Keine Eskalation über mehr als eine Stufe (kein gelb+orange → rot).
- Keine neue, vierte oder weitere Paar-Kombination über die drei genannten hinaus ohne
  erneute PO-Freigabe.
- **v1.1:** Kein Nullgradgrenze-Paar (`freezing_level` bleibt ohne `display_thresholds`
  — trip-relatives Problem, eigenes Ticket nötig).
- **v1.1:** Kein Schneehöhe-Paar (`snow_depth` bleibt ohne `display_thresholds` — keine
  belegbare Ampel-Absolutschwelle gefunden, weder repo-intern noch extern).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Renderer-Logik-Änderung innerhalb einer bestehenden Datei-Schicht
  (`src/output/`), kein neuer Kanal, kein neues Datenmodell, keine neue
  Provider-/Auth-/Deploy-Entscheidung. Fällt nicht unter die ADR-pflichtigen
  Entscheidungsflächen aus `CLAUDE.md`.

## Changelog

- 2026-08-19: Initial spec created (v1.0) — Wiedereröffnung von Issue #1927, löst die
  3-stufige Punktfarben-Entscheidung aus `fix_1927_risk_dot_farbpalette.md` bewusst ab
  (echte 4-Stufigkeit + fachliche Kombi-Eskalation für 4 benannte Metrik-Paare).
- 2026-08-19: v1.0 implementiert (47/47 Tests grün), Adversary-Dialog gegen v1.0
  ergab **VERDICT: BROKEN** — 3 von 4 Paaren (AC-3/4/5) waren über den in der Spec
  vorgeschriebenen Aufrufpfad `_row_risk()` strukturell nie erreichbar: `freezing_level`/
  `snow_depth`/`fresh_snow` hatten keine `display_thresholds`, und der `severities`-Dict
  enthielt keinen `"thunder"`-Key. Nur AC-2 (Niederschlag+Temperatur) war produktiv
  wirksam. Vollständiges Protokoll:
  `docs/artifacts/fix-1927-risk-dot-kombi-regel/adversary-dialog.md`.
- 2026-08-19: **Revision v1.1** (PO-Scope-Entscheid nach BROKEN-Befund) — Recherche
  (repo-intern + extern, SLF/EAWS-Lawinen-Gefahrenskala) ergab: Gewitter-Paar per
  Verdrahtungskorrektur lösbar (keine neue Zahl nötig, `_THUNDER_AMPEL_BAND` liefert
  die Gelb-Schwelle bereits), Neuschnee-Paar mit belegter SLF/EAWS-Schwelle
  (gelb=10/orange=20/rot=30 cm) umsetzbar. Für Nullgradgrenze und Schneehöhe fand sich
  KEINE belastbare Ampel-Absolutschwelle (Nullgradgrenze zusätzlich strukturell
  trip-relativ). PO-Entscheid: diese zwei Paare zurückstellen, drei von vier Paaren
  ausliefern. AC-3 (v1.0) entfällt, AC-4/AC-5 werden auf die neue Grundlage umgeschrieben.
  Spec braucht erneute ACs-Freigabe vor Fortsetzung der Implementierung.
