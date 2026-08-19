# Context: fix-1927-risk-dot-kombi-regel

## Request Summary
Issue #1927 wurde am 19.08.2026 wiedereröffnet (nachdem die Farbpaletten-Vereinheitlichung
aus PR #1946 / Commit `fc6dd420` bereits ausgeliefert war). PO-Befund: Der Risk-Punkt am
Zeilenende zeigt bei „gelben" Zellen trotzdem Orange, weil er nur 3 Stufen (grün/orange/rot)
kennt statt der 4 Stufen der Einzelzellen (grün/**gelb**/orange/rot).

PO-Entscheidung (nach Trade-off-Diskussion, 19.08.2026): Zwei Teile.
1. Risk-Punkt wird echt 4-stufig (zeigt auch Gelb).
2. Zusätzlich: fachlich zusammenhängende Metrik-**Paare**, die beide gleichzeitig "gelb"
   sind, eskalieren die Zeile eine Stufe höher (z. B. auf Orange) — unabhängige
   Gelb-Kombinationen (Beispiel PO: UV+Temperatur) eskalieren NICHT.

Verworfen wurden: (a) reine Maximalwert-Lösung ohne Kombi-Regel, (b) pauschale
"N×Gelb=Orange"-Summenregel unabhängig vom fachlichen Zusammenhang — Begründung siehe
Kommentar-Historie auf #1927 (Fehlalarm-Risiko bei unabhängigen Größen, Präzedenzfall #1377
zu verstreuten Schwellenquellen).

## Root Cause (bestätigt)
`_row_risk()` — `src/output/renderers/email/html.py:202-237` — fasst die Einzelwert-Ampeln
einer Zeile bewusst auf ein 3-wertiges Vokabular (`ok`/`watch`/`risk`) zusammen: sowohl
`yellow` als auch `orange` werden zu `watch` (→ Punktfarbe Orange) kollabiert.

**Wichtig:** Das ist keine Regression, sondern eine explizite, im vorigen #1927-Zyklus
getroffene und dokumentierte PO-Design-Entscheidung — siehe
`docs/specs/modules/fix_1927_risk_dot_farbpalette.md:95-111` (Commit `fc6dd420`), Begründung
dort: "die schärfere der beiden Nachbarfarben ist die sicherere Wahl". Die heutige
Wiedereröffnung hebt diese Entscheidung bewusst auf. **Die neue Spec muss das explizit als
Revision der bestehenden AC benennen**, nicht stillschweigend überschreiben.

Mapping Zeilen-Level → Punktfarbe: `_RISK_LEVEL_TO_AMPEL` (`html.py:245`), aktuell
`{"ok": "green", "watch": "orange", "risk": "red"}` — kein `"yellow"`-Wert vorhanden, obwohl
die Zielpalette (`_AMPEL_DOT_COLORS`, `helpers.py:591-596`) bereits vollständig 4-stufig ist
(`green`/`yellow`/`orange`/`red` inkl. Hex-Werten). Die Zielfarbe für Gelb existiert also
schon — sie wird vom Mapping nur nicht erreicht.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/html.py:202-237` | `_row_risk()` — Zeilen-Aggregation, kollabiert 4→3 Stufen |
| `src/output/renderers/email/html.py:245-254` | `_RISK_LEVEL_TO_AMPEL` / `_RISK_DOT_COLORS` — Mapping ohne "yellow" |
| `src/output/renderers/email/helpers.py:591-596` | `_AMPEL_DOT_COLORS` — Zielpalette, bereits 4-stufig vollständig |
| `src/output/metric_format.py:130-196` | `severity_for()` / `severity_from_thresholds()` — SSoT für Einzelmetrik-Ampel, Kandidat-Ort für neue Paar-Eskalationsfunktion |
| `src/app/metric_catalog.py` | `display_thresholds` je Metrik (wind, gust, precipitation, rain_probability, uv_index, visibility, …) |
| `src/providers/geosphere.py:176-189` | `_calculate_wind_chill()` — Windchill als bereits bestehende physikalische Wind+Temp-Kombination (eigene Metrik `felt`, eigene Schwelle) |
| `tests/tdd/test_renderer_katalog_schwellen.py:332-343` | `test_ac10_row_risk_gust_30_becomes_achtung` — **bricht bewusst** durch die 4-Stufen-Umstellung, muss in der Spec als Ablösung benannt und der Test umgeschrieben werden |
| `tests/tdd/test_risk_dot_matches_ampel_palette.py` | prüft aktuell nur grün/orange/rot, sollte um "yellow" ergänzt werden |
| `tests/tdd/test_row_risk_gewitter.py` | Einzelmetrik-Fixtures, kein Konflikt mit Paar-Regel, unberührt von 3→4-Umstellung (Fixture-Werte liegen unter Gelb) |

## Existing Patterns
- `_row_risk` hat **keinen zweiten Aufrufer im Repo** (verifiziert) — Scope ist sauber auf
  die Trip-Briefing-Stundentabelle begrenzt.
- `outlook.py` (Trip-Ausblick) und `compare_html.py` (Ortsvergleich) haben **keine
  äquivalente Zeilen-Aggregation** ("ein Punkt pro Zeile aus mehreren Metriken") — sie färben
  ausschließlich einzelne Zellen über dieselbe SSoT (`severity_for()`). Das #1377-Muster
  (Logik an mehreren Orten dupliziert) betraf die Zell-Schwellenwerte, die bereits
  konsolidiert sind — **nicht** die hier betroffene Zeilen-Aggregations-Logik, die
  architektonisch einzigartig für `html.py`/Trip ist.
- Windchill (`felt`) ist der bestehende Präzedenzfall für "zwei physikalische Größen werden
  zu einer kombinierten Bewertung" — aber als eigene Metrik mit eigener Schwelle, nicht als
  Aggregationsregel über zwei Ampel-Stufen. Das ursprünglich diskutierte Beispiel-Paar
  "Wind+Kälte" ist dadurch bereits abgedeckt und braucht **keine neue** Kombi-Logik.

## Scope-Entscheidung (Empfehlung aus Strategie-Bewertung, noch nicht PO-freigegeben)
- Kombi-Logik als eigene, benannte, testbare Funktion in `metric_format.py` (neben
  `severity_for`), aufgerufen ausschließlich von `_row_risk`. Kein Vorgriff auf
  Wiederverwendung durch outlook/compare (YAGNI) — aber am SSoT-Ort platziert, falls später
  ein eigenständiges Feature-Ticket dort ein Äquivalent einführen will.
- Scope bleibt **ausschließlich Trip-Briefing-Zeilenpunkt**. Ausweitung auf
  `outlook.py`/`compare_html.py` ist technisch nicht sinnvoll ohne eigenes Feature-Ticket
  (dort existiert noch gar kein Zeilen-Indikator, der erweitert werden könnte) — Spec bekommt
  einen expliziten "Non-Goals"-Absatz dazu.
- Zwei Slices in einer Spec: S1 = 3→4-Stufen-Umstellung (Voraussetzung), S2 = Paar-Eskalation
  darauf aufgesetzt.
- Konkrete Paar-Liste (Kandidat: Wind/Böen + Niederschlag/Regenwahrscheinlichkeit) ist eine
  PO-Entscheidung für die Spec-Phase, kein Implementierungsdetail.

## Scope Assessment
- Dateien: 2-3 Produktivdateien (`html.py`, `metric_format.py`, ggf. unverändert
  `helpers.py`) + 2 Testdateien angepasst/neu.
- Geschätzte LoC: ~150-250 (Produktivcode ~50-90, Testcode ~100-160) — nahe am 250-LoC-Limit;
  `loc_limit_override` vorsorglich prüfen, falls Paar-Matrix >1-2 Paare oder
  Golden-Snapshot-Tests (`test_issue_890_email_render_drift.py`) nachgezogen werden müssen.
- Risk Level: MEDIUM — kein Blast-Radius außerhalb der Trip-Mail-Renderer (kein
  Alarm-/Versandpfad betroffen), aber ein bestehender PO-freigegebener Test
  (AC-10-Nachfolger) bricht bewusst und muss in der Spec als Revision dokumentiert sein.

## Dependencies
- Upstream: `severity_for()`/Katalog-Schwellen (unverändert korrekt).
- Downstream: nur die visuelle Darstellung der Trip-Briefing-Mail (HTML-Renderer). Keine
  Alarm-/Versandlogik betroffen (bestätigt: `_row_risk` ohne zweiten Aufrufer).

## Open Questions (für Spec-Phase)
- [ ] Konkrete Paar-Liste: reicht "Wind/Böen + Niederschlag" allein, oder gibt es weitere
      fachlich begründete Paare (z. B. Gewitter + Wind für Böenfront)?
- [ ] Eskaliert ein Paar immer genau eine Stufe (gelb+gelb → orange), oder auch bei
      gelb+orange → rot?
- [ ] Bricht `test_ac10_row_risk_gust_30_becomes_achtung` wie erwartet — wird der Test
      umgeschrieben oder ersetzt?
