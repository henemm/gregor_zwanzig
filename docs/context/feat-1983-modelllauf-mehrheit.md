# Context: feat-1983-modelllauf-mehrheit

## Request Summary
Issue #1983 (Gewitter S6 aus Epic #1419): Die Gewitterstufe soll das bereits in der Stufen-Regel
(#1419 Abschnitt 4) genannte, aber nie verdrahtete Kriterium „Mehrheit der Modellläufe →
mindestens wahrscheinlich, Minderheit → möglich" bekommen. **Erster Schritt ist eine Messung des
Mehrverbrauchs (AC-1)**, bevor Code entsteht; untragbarer Verbrauch ⇒ Ticket mit Messergebnis
zurückstellen. Ausfall des Ensemble-Abrufs darf keine Entwarnung erzeugen (AC-4).

## Related Files
| File | Relevance |
|------|-----------|
| `src/providers/openmeteo.py:66-68,722-807` | `_fetch_ensemble_spread`: fragt nur `temperature_2m,precipitation` für `ecmwf_ifs04,icon_seamless,gfs_seamless` ab, berechnet Streuung; **kein `weather_code` je Member**; Fehler ⇒ `{}` |
| `src/providers/openmeteo.py:949-968,1148-1178` | `fetch_forecast(enrich_ensemble=…)` setzt `spread_*`/`confidence_pct` |
| `src/providers/openmeteo.py:274,680-702` | `THUNDER_CODES={95,96,99}`, `_parse_thunder_level` |
| `src/services/trip_report_scheduler.py:2294-2362` | `_enrich_ensemble_for_trip`: EIN Abruf am **letzten Wegpunkt der ganzen Tour**, per `_apply_ensemble_spreads` auf alle Segmente übertragen — räumlich ungeeignet für eine Gewittermehrheit je Segment |
| `src/services/trip_report_scheduler.py:1432,2489/2527,2981/2996` | weitere Ensemble-Aufrufe (Ausblick bis 3×, Gewitter-Fallback je künftiger Etappe) — „1 pro Report" (#288) stimmt nicht mehr |
| `src/services/trip_alert.py:2461-2466` | Alarm-Pfad bewusst `enrich_ensemble=False` („würde Tageskontingent in ~30 Min verbrauchen") |
| `src/output/metric_format.py:433-596` | Fusion: `_signal_levels`, `thunder_signal_carriers`, `thunder_level_from_signals` (max über nicht-None-Signale) |
| `src/providers/thunder_enrichment.py:36-55,143-203,219-276,327-394` | `_fuse_thunder_levels`, Radar-Override-Muster, `enrich_thunder` |
| `src/app/thunder_scale.py:118-124,138,227` | Herkunfts-Labels (#1680), Stufenwörter |
| `src/app/models.py:194-199,211-218` | `thunder_probability_pct` (für S6 vorbereitet, leer), `thunder_level_signals` |
| `src/services/forecast_budget.py:40` | `DAILY_BUDGET=9000`; `record_call()` nur in `segment_weather.py:196` — **Ensemble-Abrufe zählt das Budget nicht** |
| `src/providers/call_log.py` + `scripts/analyze_openmeteo_calls.py` | Abruf-Journal (Quelle `ensemble` per Stack-Marker) — Grundlage der Messung |
| `src/app/metric_catalog.py:424-438` | `confidence` `selectable=False` — nicht anfassen |

## Existing Patterns
- **Eine Fusion, eine Skala (ADR-0025):** neue Signale als weiterer Schlüssel in `_signal_levels`, Herkunft in `thunder_level_signals`, Label in `THUNDER_SIGNAL_LABEL_DE`.
- **Nachträgliche Anhebung:** Radar-Override (`thunder_enrichment.py:219-276`) hebt nur an, senkt nie.
- **Fehlendes Signal = `None`, nie 0/NONE** (`thunder_enrichment.py:346-347`, `metric_format.py:447-450`) — genau die AC-4-Garantie.
- Additive Quellen je Gebiet (ADR-0057), Regionen FR/DE_ALPEN/EU_REST (`thunder_routing.py:57-61`).

## Dependencies
- Upstream: Open-Meteo Ensemble-API (`ensemble-api.open-meteo.com/v1/ensemble`), Tageskontingent 9000 (gemeinsam für alle Nutzer, vgl. #2150).
- Downstream: Gewitterstufe fließt in alle vier Kanäle (Mail, Telegram, SMS, Premium-SMS) und in Alarme.

## Existing Specs / ADRs
- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` §5 (`:282-299`) — S6 „Verbrauch vorher messen"
- `docs/specs/modules/forecast_confidence.md`, `_archive/.../bug_288_ensemble_api_limit.md`, `_archive/.../bug_338_openmeteo_call_counter.md`, `fix_1329_forecast_cache_budget.md`
- `docs/specs/modules/feat_1680_*` (Herkunft), `fix_2010_2011_gewitter_stufenwoerter.md`, `fix_2012_gewitter_stufen_migration.md`
- ADR-0005 (confidence nicht wählbar), 0025, 0048, 0057, 0064 (LOW verlässt Leiter), 0071

## Risks & Considerations
- **Kontingent:** Ensemble-Abrufe laufen am Budget-Zähler vorbei; gemeinsames Kontingent (#2150) — Mehrverbrauch trifft alle Nutzer. Wie Open-Meteo Ensemble-Abrufe gewichtet (Member × Variablen), ist **ungemessen**.
- **Räumlicher Anker:** heutiger Abruf nur am Tour-Endpunkt ⇒ für Gewitter je Segment nicht verwendbar; mehr Anker = mehr Abrufe.
- **Alarm-Pfad** nutzt bewusst kein Ensemble — S6 dort nur mit Messung/Entscheid.
- **Modellnamen/Memberzahl** (`ecmwf_ifs04` evtl. veraltet; „40 Läufe" unbestätigt) und ob die Ensemble-API `weather_code` je Member liefert — ungeprüft.
- **AC-4:** Ausfall ⇒ `{}` ⇒ Signal muss `None` bleiben, nie „keine Gefahr".
- Abgrenzung #710/ADR-0005: keine neue wählbare Metrik; allenfalls `thunder_probability_pct`/Fusionssignal.
- Stufenwort-Abbildung möglich/wahrscheinlich ↔ MED/HIGH nach ADR-0064 prüfen.

## Analysis

### Type
Feature (S6 aus Epic #1419)

### Messung (AC-1) — schriftliches Ergebnis
**Belegt:**
- `/v1/ensemble` liefert `weather_code_memberNN_<modell>` je Member (curl 19.09., Punkt Wolayersee). Ungültige Variable ⇒ API-Fehler, nicht `null`.
- Heutiger Abruf (`openmeteo.py:738-743`) liefert 145 Spalten: ICON-EPS 39 Member + Kontrolle, GEFS 30 + Kontrolle. **`ecmwf_ifs04` ist bei Open-Meteo kein Ensemble mehr** (keine Member) — kostet Gewicht, bringt keinen Lauf.
- Ensemble-Abrufe je Briefing-Fenster: 1 (Hauptlauf `trip_report_scheduler.py:1432`) + bis 3 (Ausblick `:2489/2527`) + Gewitter-Fallback (`:2981/2996`). 2 Fenster/Tag/Trip.
- Ensemble-Abrufe laufen **am internen Budget-Zähler vorbei** (`record_call()` nur `segment_weather.py:196`).
- Prod-Status (`localhost:8090/api/scheduler/status`, 19.09.): `trip_reports_hourly.users.total = 3`, `forecast_budget.calls_today = 0`, letzter Gewitterabruf 05.09. (KHW-Ende) — derzeit keine aktive Tour. Realistische Spitzenlast: 1–3 gleichzeitig aktive Trips.

**Inferenz (nicht gemessen):** Open-Meteo gewichtet Ensemble-Abrufe nach Member × Variablen; einziger Beleg ist das Doku-Beispiel (1 Variable × ICON-EPS 40 Member, 7 Tage ≈ 4,0 Calls). Daraus: heutiger Abruf ≈ 14 Calls, mit `weather_code` ≈ 21. Kein Gewichts-Header in der Antwort ⇒ direkt nicht messbar.

**Ergebnis:** je Trip und Tag heute bis ≈ 140 gewichtete Ensemble-Calls (5 Abrufe × 14 × 2 Fenster), mit `weather_code` im bestehenden Abruf ≈ 210. Bei 1–3 aktiven Trips ≈ 200–650 von 10.000/Tag (Free-Tier; interner Deckel 9000) ⇒ **Kosten tragbar, solange der Anker bleibt wie heute.** Anker je Etappe multipliziert mit der Etappenzahl (Ausblick-Abrufe existieren bereits je künftiger Etappe, Hauptlauf nicht).

### Inhaltliche Befunde (entscheidend, nicht die Kosten)
1. **Max-Fusion kann nur anheben.** Als 5. Signal in `_signal_levels` (`metric_format.py:433-486`) trägt S6 nur an Tagen bei, an denen bisher kein Signal feuerte. Auf dem KHW ist das dokumentierte Problem Über­prognose (#2181/#2206: 9 von 13 Tagen „hoch" gegen 1 realen Gewittertag). AC-2/AC-3 wie im Ticket verschärfen das. Alternative: **dämpfend** — Uneinigkeit der Läufe senkt eine Einzelmodell-Einstufung (Muster `_gedaempft_durch_cin`, `metric_format.py:376-430`). ⇒ PO-Entscheidung (Produktsemantik).
2. **Schwellen fehlen.** „Minderheit" wörtlich = ≥1 von ~70 Membern (1,4 %) feuert an fast jedem Sommertag. Keine belegte Quelle im Epic.
3. **Räumlicher Anker:** Hauptlauf fragt am letzten Wegpunkt der Tour ab und überträgt auf alle Segmente (`trip_report_scheduler.py:2318-2362`) — für eine Gewitteraussage je Etappe ungültig.
4. Alarm-Pfad bleibt ohne Ensemble (`trip_alert.py:2461-2466`), unverändert.

### Affected Files (falls Bau)
| File | Change | Description |
|---|---|---|
| `src/providers/openmeteo.py:722-807` | MODIFY | `weather_code` mitabrufen, Anteil Gewitter-Member je Stunde |
| `src/services/trip_report_scheduler.py:2294-2362` | MODIFY | Anker je Etappe, Anteil auf `thunder_probability_pct` |
| `src/output/metric_format.py:433-596` | MODIFY | neues Signal bzw. Dämpfer |
| `src/providers/thunder_enrichment.py:143-203` | MODIFY | Durchreichen, Herkunft |
| `src/app/thunder_scale.py:118-124` | MODIFY | Herkunfts-Label |
| `tests/tdd/test_thunder_*` | CREATE/MODIFY | inkl. Wächter-Anpassung `test_thunder_probability_field_prepared_empty.py` |

### Scope Assessment
- Files: 5–7 + Tests · Estimated LoC: +150–300 · Risk: HIGH (alle vier Kanäle, Überprognose)

### Technical Approach (Empfehlung)
Kein Zurückstellen aus Kostengründen — die Messung trägt. Bau nur mit geklärter Semantik: (a) dämpfend statt anhebend oder beides mit belegter Schwelle, (b) Anker je Etappe. Bis zur PO-Entscheidung keine Spec-ACs.

### Nebenbefund
`ecmwf_ifs04` im Ensemble-Abruf liefert keine Member, kostet aber Gewicht (und verzerrt ggf. `confidence_pct`) ⇒ Sammel-Eintrag #1199, nicht im Rahmen von #1983 mitfixen (nutzersichtbar über `confidence_pct`, Spec `forecast_confidence.md`).

### Open Questions (PO, fachlich)
- [ ] Anhebend (wie Ticket) oder dämpfend (Uneinigkeit senkt)?
- [ ] Schwelle „Mehrheit"/„Minderheit"

### PO-Entscheid 2026-09-19 (Henning)
**„Beides, mit Schwellen":** Deutliche Mehrheit der Läufe mit Gewittercode hebt an; nur wenige Läufe ⇒ eine Einzelmodell-Einstufung wird gedämpft (gesenkt). Ziel ist ausdrücklich, die KHW-Überprognose (#2181) zu bekämpfen, nicht zu verstärken. Schwellenwerte (obere/untere) legt die Spec mit Begründung fest; AC-2/AC-3 des Tickets werden entsprechend umformuliert. Kostenseite trägt (siehe Messung), Anker je Etappe nötig.
