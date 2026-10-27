# Context: fix-2178-cape-leiter-absolutwerte

## Request Summary
`cape_ladder_thresholds_jkg()` (`src/app/model_registry.py:253-268`) soll fuer die Sprossen
`med`/`high` von regional hochgerechneten Verhaeltniswerten (2,5x/4x auf die geeichte `low`-
Schwelle) auf die belegten NWS/SPC-Absolutwerte 1000 J/kg bzw. 2500 J/kg umgestellt werden.
`low` bleibt unveraendert regional/modellgeeicht ueber `cape_threshold_jkg()`. PO-Entscheid
(2026-09-16): Umstellung ja, #1896 (CIN-Kalibrierung) bleibt separates Ticket.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/model_registry.py:215-268` | Zielfunktion: `CAPE_LEITER_MED_NOMINAL_JKG`/`CAPE_LEITER_HIGH_NOMINAL_JKG` (aktuell 2500/4000, nominal fuer die Umrechnung), `cape_ladder_thresholds_jkg()` selbst |
| `src/providers/thunder_enrichment.py:305` (`_schwellen_fuer_reihe`, aufgerufen von `enrich_thunder` L385) | Einziger Produktionspfad: holt die Leiter, reicht `(low, med, high)` unveraendert an `_fuse_thunder_levels()` (L143-201) |
| `src/output/metric_format.py:436-489` (`thunder_level_from_signals`/`thunder_signal_carriers`) | Nutzt `cape_med_min`/`cape_high_min` zur Bestimmung der Alarmstufe LOW/MED/HIGH je Datenpunkt — hier wirkt die Aenderung im Briefing |
| `src/analysis/thunder_replay.py` | Bekommt die Leiter vom Aufrufer gereicht (Mitschnitt-Auswertung #2181), nicht selbst betroffen |
| `tests/tdd/test_cape_cin_pairing.py:78-100` | `test_ac1_cape_ladder_thresholds_jkg_proportional_zur_kalibrierung` erwartet HART `(300.0, 750.0, 1200.0)` bzw. `(420.0, 1050.0, 1680.0)` — wird nach der Umstellung ROT, muss auf feste 1000.0/2500.0 angepasst werden |
| `tests/tdd/test_cape_cin_pairing.py:123-137,299-320,437-455,738-750` | Nutzen die Leiter relativ (`+100`/`+500`), bleiben robust |
| `tests/tdd/test_thunder_replay.py:52,420`, `test_thunder_ablation.py:66` | Rufen die Leiter live auf, keine hartcodierten med/high-Werte |
| `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` | Hauptspec der Leiter, begruendet aktuell die proportionale Skalierung inkl. Beispielwerten 300/750/1200 — braucht Aktualisierung |
| `docs/specs/modules/feat_2181_s2a_gewitter_mitschnitt_auswertung.md`, `feat_2181_s2c_gewitter_archiv_ablation.md` | Referenzieren 300/750/1200 als Beispielwerte, nicht normativ fuer die Leiter selbst |
| `docs/specs/modules/feat_2176_luftmasse_statt_gewitteransage.md` | Nennt #2178 explizit als "ausserhalb des Scopes" dieser Spec — keine Kollision |

## Existing Patterns
- `cape_delta_threshold_jkg(nominal, model_id, region)` rechnet `nominal * geeicht/CAPE_REFERENZ_NIVEAU_JKG` — bleibt als Funktion bestehen, wird aber in `cape_ladder_thresholds_jkg()` fuer `med`/`high` NICHT mehr aufgerufen, da diese Sprossen kuenftig fest sind.
- `None`-Semantik durchgaengig: unbekannte Modell/Region-Kombination ⇒ `None`, kein Rueckfall auf Rohwerte (gilt weiter fuer `low`/`cape_threshold_jkg`; `med`/`high` sind ab jetzt konstant und brauchen keine Kalibrierung mehr, ausser wenn `low is None` — dann muss die Gesamtfunktion weiterhin `None` liefern, siehe Risiken).

## Dependencies
- **Upstream:** `cape_threshold_jkg()` (`model_registry.py:135-141`, Tabelle `CAPE_THRESHOLDS_JKG` L119-130) liefert `low`; bleibt unveraendert.
- **Downstream:** `thunder_enrichment.py` → `_fuse_thunder_levels()` → `metric_format.thunder_level_from_signals()` → Alarmstufe im Briefing (SMS/E-Mail/Telegram/Premium-SMS gleichermassen, da die Stufe zentral bestimmt wird, nicht pro Kanal).

## Existing Specs
- `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` — muss die Herleitung von absolut statt proportional umstellen.

## Nicht anfassen (aus Explore-Recherche bestaetigt)
- `CAPE_REFERENZ_NIVEAU_JKG` (`model_registry.py:220`) und `cape_delta_threshold_jkg()` haben einen ZWEITEN, unabhaengigen Aufrufer ausserhalb der Leiter: `src/services/weather_change_detection.py:811,817` — rechnet die Aenderungsalarm-Presets (`services/alert_preset.py:68`, `(CAPE, DELTA, 1200, 600, 200)`) um. Andere Nominalwerte, fachlich unabhaengig — NICHT anfassen.
- `docs/specs/modules/fix_1592_c3_cape_delta_alarme.md` — separate Leiter (1200/600/200) fuer Aenderungsalarme, nicht die Ladder-Sprossen.
- #1896 (CIN-Kalibrierung fuer ICON) — laut PO-Entscheid separates Ticket, hier nicht mitnehmen.

## Risks & Considerations
- **Test-Bruch:** `test_ac1_cape_ladder_thresholds_jkg_proportional_zur_kalibrierung` muss in derselben Aenderung angepasst werden (roter Test ist erwartbar/gewollt als TDD-Nachweis, siehe `/40-tdd-red`).
- **`None`-Fall bewahren:** Wenn `cape_threshold_jkg()` fuer eine Modell/Region-Kombination `None` liefert (keine Eichung), muss `cape_ladder_thresholds_jkg()` weiterhin `None` fuer die GESAMTE Leiter liefern (nicht `(None, 1000.0, 2500.0)`) — Konsistenz mit der bisherigen "nicht belegt = ueberall nicht belegt"-Semantik.
- **`CAPE_LEITER_MED_NOMINAL_JKG`/`CAPE_LEITER_HIGH_NOMINAL_JKG`:** Umbenennung/Umwidmung noetig, da sie kuenftig keine "nominalen" Umrechnungswerte mehr sind, sondern die tatsaechlichen festen Schwellen. Kommentar an `CAPE_LEITER_*` (L242-251) muss die neue Herleitung (absolut, nicht mehr proportional) dokumentieren.
- **31.08.-Ereignis:** Faellt mit den neuen Werten von "mittel/hoch" auf "leicht" zurueck (PO-akzeptierter Preis) — kein Testfall verlangt explizit "31.08. = mittel", daher keine Kollision mit bestehenden Tests ausserhalb der Leiter-Werte selbst erwartet, aber bei Mitschnitt-basierten Tests (`test_thunder_replay.py`, `test_thunder_ablation.py`) genau pruefen, ob ein konkretes Datum/Ereignis hartcodiert eine Stufe erwartet.
- **Spec-Update Pflicht:** `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` referenziert die alten Werte normativ — muss in derselben PR aktualisiert werden (Doku-Only, zaehlt nicht gegen LoC-Limit).
