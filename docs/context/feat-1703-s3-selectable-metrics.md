# Context: #1703 Scheibe 3 — Nicht-wählbare Register-Metriken

## Request Summary

Epic #1703 (Folgearbeit aus #1514) baut den Matrix-Wächter `tests/tdd/test_channel_metric_matrix.py`
(#1677 B) achsenweise aus. Scheibe 3 muss laut PO-Reihenfolge **zuerst** laufen: die
`get_all_metrics()`-Blindstelle (`src/app/metric_catalog.py:693`) filtert `selectable=False`-
Metriken aus JEDER Vollständigkeitsprüfung, die auf ihr aufbaut — Scheiben 1/2/4/5 würden sie
sonst erben. Ziel: ein Wächter, der für jede nicht-wählbare Register-Metrik mit Ausgabefeld
(`sms_code`, `alert_label`, `summary_fields`, …) prüft, dass sie dort ankommt (oder dokumentiert
NICHT ankommt), wo das Feld sie hinschickt.

## Ausgangslage: DREI nicht-wählbare Metriken, DREI verschiedene Sollzustände

`grep "selectable=False" src/app/metric_catalog.py` (Stand 2026-08-10):

| Metrik | Ausgabefelder | PO-Regel / Soll |
|---|---|---|
| `confidence` (#710/#715, final) | keine (`sms_code`/`alert_label` fehlen) | NUR 3 erlaubte Orte: E-Mail-Textblock (`build_confidence_hint`), SMS-Token, interne Aggregation. NIE als Spalte/Metrik-Auswahl |
| `temperature_cold` (#914) | `sms_code="N"`, `alert_label="Temp"`, `summary_fields={"min": "temp_min_c"}` | Kältealarm MUSS ankommen (Alarm-Renderer, Compare-Aktivierung); Mail-Spalte fällt bewusst in den `remaining`-Fallback (Bestand, s.u.) |
| `cape` (#1585, PO-Regel final) | `sms_code="CP"`, `alert_label="CAPE"` | Darf **nirgends** sichtbar sein — nur interne Berechnung (`thunder_level_from_signals`, CAPE-Delta-Alarm #1592) |

Ein naiver Wächter „nicht-wählbar + hat `sms_code` ⇒ muss ankommen" würde für `cape` das exakte
Gegenteil der PO-Entscheidung festschreiben. Die drei Fälle brauchen **je eigene** Zusicherung,
keine gemeinsame Formel.

## Bereits vorhandene Infrastruktur (NICHT neu erfinden)

- **`_is_selectable()` + `_SELECTABLE_GATE_EXEMPT`** (`src/app/models.py:613-650`, #1585): zentraler
  Choke-Point, den `_filter_metrics_by_report_type()` (models.py:653, speist E-Mail+SMS+Telegram)
  nutzt. Exemption-Liste ist klein, benannt, darf nur schrumpfen — aktuell nur `temperature_cold`.
- **`is_alert_metric_active()`** (`src/services/weather_change_detection.py:181-236`, #1585):
  prüft das `_ALERT_METRIC_TO_CATALOG_ID`-Tupel als Ganzes (nicht Glied-für-Glied) — verhindert,
  dass ein Filter auf `temperature_cold` den `TEMPERATURE_MIN`-Alarm stumm schaltet.
- **Bestehende Charakterisierungstests je Metrik** (nicht Gegenstand dieser Scheibe, aber Referenz):
  `tests/tdd/test_cape_not_selectable.py` (AC-3/AC-9, Choke-Points `_filter_metrics_by_report_type`
  + `is_alert_metric_active`), `tests/tdd/test_issue_715_confidence_not_selectable.py`,
  `tests/unit/test_metric_catalog.py::test_ac4_temperature_cold_bleibt_unveraendert_n`.

## Gemessene Lücke: weitere `.selectable`-Stellen OHNE Exemption-Bewusstsein

`grep "\.selectable\b" src/` findet **8 weitere** Stellen, die den rohen Katalog-Flag prüfen,
NICHT über `_is_selectable()` (die die Exemption-Liste kennt):

| Datei:Zeile | Kontext | Bewertung |
|---|---|---|
| `output/renderers/email/helpers.py:311` (`resolve_metric_col_order`) | Spaltenreihenfolge E-Mail/Plain | **Bewusste Ausnahme, dokumentiert** (models.py:619-625): `temperature_cold` fällt hier raus, landet aber über den `remaining`-Zweig (`email/html.py:681`) hinten in der Tabelle — bestehender, testgehaltener Zustand (`test_mail_column_order.py::test_legacy_config_without_order_keeps_catalog_order`) |
| `output/renderers/email/helpers.py:120`, `:177` (`dp_to_row` Stundentabelle) | Stundenverlauf Trip | Kein Kommentar zu `temperature_cold`/Exemption — muss geprüft werden, ob das Fehlen dort Bestand oder Lücke ist |
| `output/renderers/email/helpers.py:288` (`get_hourly_metric_ids` neuer Pfad) | Stundenverlauf-Spaltenauswahl | dito |
| `output/renderers/compare_metric_catalog.py:284` | Compare-Katalog-Label-Auflösung | Kommentiert als Issue #1585/CAPE-Fall — `temperature_cold` nicht erwähnt, aber `temperature_cold` ist nie Teil von `COMPARE_METRIC_CATALOG` (nur Trip-Alarm-Pseudogröße), also strukturell nicht betroffen — verifizieren |
| `output/renderers/compare_metric_ids.py:140` (`_non_selectable_keys`) | Compare gespeicherte Auswahl | Analog, generisch aus Katalog abgeleitet |
| `app/metric_catalog.py:615/661/869/945` | katalog-intern (`get_metric`-Familien, Template-Filter) | Katalog-eigene Konsistenz, kein externer Ausgabeort |

**Kernbefund:** Es gibt zwei parallele "ist die Größe wählbar?"-Prüfungen im Code — die
exemption-bewusste `_is_selectable()` und die rohe `mdef.selectable`-Prüfung an mehreren Stellen.
Das ist laut Code-Kommentar für `resolve_metric_col_order` **bewusst** (mit kompensierendem
Fallback). Für die beiden Stundentabellen-Stellen (`dp_to_row`, `get_hourly_metric_ids`) ist nicht
dokumentiert, ob ein künftiges `temperature_cold`-Vorkommen dort ebenfalls einen Fallback hätte
oder einfach lautlos verschwindet — das ist eine der beiden Fragen, die die Spec-Phase klären muss.

## Related Files

| File | Relevance |
|---|---|
| `src/app/metric_catalog.py` | Katalog, `get_all_metrics()` (Blindstelle), 3 `selectable=False`-Definitionen |
| `src/app/models.py:613-686` | `_SELECTABLE_GATE_EXEMPT`, `_is_selectable()`, `_filter_metrics_by_report_type()` |
| `src/services/weather_change_detection.py:181-236` | `is_alert_metric_active()`, Tupel-weise Prüfung |
| `src/output/renderers/email/helpers.py:100-320` | 4 Stellen mit rohem `.selectable`-Check |
| `src/output/renderers/compare_metric_catalog.py`, `compare_metric_ids.py` | Compare-seitige `.selectable`-Checks |
| `src/services/compare_alert.py:59` | `_SUMMARY_KEY_TO_CATALOG_ID` mappt `temp_min_c` → `temperature_cold` (Compare-Aktivierungssignal) |
| `tests/tdd/test_channel_metric_matrix.py` | Ziel-Datei für die neue Achse (Option C, kein neues Gate) |
| `tests/tdd/test_cape_not_selectable.py` | Bestehende Charakterisierung CAPE (Referenzmuster für Scheibe-3-Assertions) |
| `tests/tdd/test_issue_715_confidence_not_selectable.py` | Bestehende Charakterisierung confidence |
| `docs/reference/metric_output_matrix.md` §6 Scheibe 3 | Auftragsbeschreibung, Definition of Done (Doku-Zelle umtragen) |

## Existing Specs

- `docs/specs/modules/feat_1585_cape_selectable_false.md` — Vorgänger-Spec, gleiches Muster
- `docs/specs/modules/fix_1677_sms_reihenfolge.md` — AC-13/14/15, definiert den bestehenden
  Matrix-Test, den Scheibe 3 erweitert (Option C: kein neuer Test, neue Achse in derselben Datei)
- `docs/specs/modules/konzept_1514_metrik_ausgabeorte.md` — Ursprungskonzept, Herkunft von #1703

## Risks & Considerations

- **Kollateralschaden-Muster (#1585, memory `reference_selectable_gate_collateral_damage_pattern`):**
  ein neuer generischer Filter kann eine ANDERE, bereits etablierte Ausnahme treffen. Vor jeder
  Code-Änderung: alle 3 non-selectable Metriken einzeln durchspielen (bereits oben getan) — gilt
  für neue Testerwartungen genauso wie für Produktivcode.
- **KORREKTUR (2026-08-10, per echtem Rendering widerlegt — vormals hier als „empirisch geklärt"
  behauptet):** `temperature_cold` erscheint SEHR WOHL als eigene Stundenspalte „TmpMin" in der
  Trip-Mail, mit identischem Wert zu „Temp" in jeder Stunde (echte Dublette, per
  `TripReportFormatter().format_email()`-Rendering nachgemessen). Der Fehler in der ursprünglichen
  Analyse: `email/helpers.py::dp_to_row()`/`get_hourly_metric_ids()` (dort sitzt der geprüfte
  `.selectable`-Check) hat **keinen einzigen Produktions-Aufrufer** in `src/` — der tatsächliche
  Trip-Mail-Pfad läuft über `TripReportFormatter._dp_to_row()`/`_aggregate_night_block()`
  (`trip_report.py:627`/`534`), eine ZWEITE, gleichnamige Implementierung OHNE eigenen
  `.selectable`-Check. Sie verlässt sich vollständig auf die vorgelagerte, exemption-bewusste
  Kollabierung `dc.get_metrics_for_channel("email", report_type)` (`trip_report.py:135-138` →
  `_is_selectable()`) — und die lässt `temperature_cold` (Exemption) durch, unverändert `enabled=True`,
  bis in die Zeilen-Builder. Zwei Lehren: (1) „Prüfort = Wirkort" gilt auch für den eigenen
  Analyseschritt, nicht nur für Tests — ein gleichnamiger Funktionsname beweist nicht denselben
  Wirkort; (2) die ~13 Testdateien, die `email/helpers.py::dp_to_row()` isoliert aufrufen (u.a.
  `test_cape_not_selectable.py`, `test_issue_715_confidence_not_selectable.py`), prüfen für den
  Trip-Mail-Aspekt eine produktiv tote Funktion — für `cape`/`confidence` zufällig folgenlos (beide
  werden schon VOR `_dp_to_row()` aus `dc.metrics` entfernt), aber strukturell die falsche Stelle.
  `temperature_cold` kommt weiterhin in `COMPARE_METRIC_CATALOG` nicht vor (grep bestätigt leer) —
  die Compare-seitigen `.selectable`-Checks bleiben für sie gegenstandslos, relevant nur für
  `cape`/`confidence`.
- **Scope-Grenze:** Scheibe 3 soll laut Doku „klein" sein — die Recherche bestätigt das jetzt: kein
  Produktivcode-Fix nötig, nur ein Wächter, der die oben hergeleiteten Fakten in Tests gießt.
- **Kein neues Pflicht-Gate:** Erweiterung des bestehenden budgetierten Gates #1677 B — Regel-Budget
  beachten (kein Ersatz nötig, ist Erweiterung eines bestehenden Gates).
- **Definition of Done laut Epic:** nach Abschluss die „unbewacht"-Zelle in
  `docs/reference/metric_output_matrix.md` §4 auf den neuen Wächter umtragen.

## Next Step

`/20-analyse` (bzw. direkt in Spec-Phase, da Standard Track Context+Analyse kombiniert) — die
offene Frage aus „Risks" (Stundentabellen-Verhalten für `temperature_cold`) muss vor der Spec
per Messung (kleiner Testlauf) beantwortet werden.
