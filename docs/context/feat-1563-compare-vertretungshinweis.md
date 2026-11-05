# Context: feat-1563-compare-vertretungshinweis

**Workflow:** `feat-1563-compare-vertretungshinweis` · **Issue:** #1563 (Folgescheibe aus #1492 S2b, Epic #2259)
**Gemessen am Stand:** `origin/main` 2026-11-04 (nach PR #2817)

## Request Summary

Die Ortsvergleichs-Mail verschweigt, wenn bei einem Ort die Gewitter-Direktquelle (oder
die Grundvorhersage) durch eine Ersatzquelle vertreten wurde. ADR-0018/ADR-0047 verbieten
diese stille Degradation; im Trip-Pfad ist der Hinweis seit #1492 S2b sichtbar.
Zu klären und zu bauen: wie die Mehrort-Zuordnung („welcher Ort?") dargestellt wird.

## Befund (gemessen)

1. **Der Compare-Datenweg verwirft `ForecastMeta`.** `fetch_forecast_for_location`
   (`src/services/comparison_engine.py:482`) holt `forecast` (mit `forecast.meta`),
   reicht aber nur `forecast.data` als `raw_data` weiter. `LocationResult`
   (`src/app/user.py:117`) hat kein Feld für Fallback/Herkunft. Es gibt in
   `comparison_engine.py` und `comparison_parallel.py` 0 Treffer für `.meta`.
   → Das Rendern allein reicht nicht: die Daten müssen erst bis zum Renderer getragen werden.
2. **Footer ist fest verdrahtet:** `compare_html.py:1617-1621` (`_render_app_footer`)
   ruft `build_origin_footer("compare", source="Open-Meteo", lang=lang)`.
3. **Plain-Variante hat keinen Hinweis-Platz:** `render_comparison_text`
   (`src/output/renderers/comparison.py:177`) kennt keine Herkunftszeile.
4. **Geteiltes Modul fertig:** `src/output/renderers/fallback_notice.py` —
   `build_fallback_lines(meta, lang=)` ist kanal-neutral und getestet.
   `select_fallback_meta(segments)` passt NICHT (liefert das erste Segment, verwirft
   die Ortszuordnung).
5. **Kanäle:** `render_comparison_text/_html` werden von `notification_service.py`,
   `scheduler_dispatch_service.py`, `compare_alert_preview_service.py` und
   `compare_official_alert.py` genutzt. Die Kanalparität (ADR-0095: jeder Kanal jede
   Frage) betrifft auch die Compare-Telegram-/SMS-Ausgaben — Umfang in der Analyse klären.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/comparison_engine.py:482` ff., `:228`, `:424` | Hier geht `forecast.meta` verloren; `LocationResult(...)` wird gebaut |
| `src/services/comparison_parallel.py:162` | zweiter `LocationResult`-Bau (paralleler Abruf) |
| `src/app/user.py:117` | `LocationResult` — braucht ein transientes, additives Feld |
| `src/output/renderers/fallback_notice.py` | geteilte Formulierung (nicht kopieren, Gate!) |
| `src/output/renderers/email/compare_html.py:1608` | HTML-Footer |
| `src/output/renderers/comparison.py:177` | Klartext-Renderer |
| `src/services/validator_render_service.py:428` | dritter `LocationResult`-Bau (Validator-Pfad) |
| `docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md` | Known Limitations Punkt 1, R1–R11 |

## Existing Patterns

- Transiente, additive `LocationResult`-Felder mit Default (z. B. `official_alert_query`,
  `outlook_hourly_data`) — kein Persistenz-Risiko, bestehende Aufrufer bleiben gültig.
- Herkunft der Gewitterstufe je Ort: #1680 S1 (`loc_thunder_signals`) — Vorbild für
  Pro-Ort-Information in der Übersichtszeile.
- Trip: `select_fallback_meta` + `build_fallback_lines` in HTML/Plain/Compact/Telegram.

## Dependencies

- Upstream: `ForecastMeta` (`app/models.py:81`: `fallback_model`, `fallback_metrics`, `fallback_reason`), `_fetch_compare_series`.
- Downstream: Compare-Mail HTML + Plain, ggf. Telegram-Compare; Golden-/Byte-Identitäts-Tests der Compare-Mail.

## Risks & Considerations

- **Trip/Compare-Teilung ist Gate:** Formulierung bleibt in `fallback_notice.py`; erlaubt ist nur die Compare-Darstellung (Zuordnung zum Ort).
- **Renderer-Commit-Gate** und `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`) — nicht der Briefing-Validator.
- **Byte-Identität/Goldens:** ohne Vertretung darf sich die Mail NICHT ändern (Normalfall = keine Zeile).
- **Cache:** Der Compare-Abruf läuft über Cache/Single-Flight (#2234) — `meta` muss aus dem Cache-Treffer ebenfalls stammen.
- **Mehrort-Schleife** (#1461): naive Schleife verdoppelte Nachrichten — hier nur Darstellung, kein Versand.
- Klartext darf `Fallback`, `icon_eu`, `eu_direct` nirgends zeigen.
- **PO-Entscheidung nötig (in Spec):** Darstellung — betroffene Orte namentlich nennen / nur „mindestens ein Ort" / Markierung in der Spalte. Empfehlung: Orte namentlich nennen (nur dort steckt die Information).

## Analysis

### Type
Feature (Folgescheibe; nutzersichtbare stille Degradation, ADR-0018/0047).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/user.py` (`LocationResult`) | MODIFY | transientes, additives Feld `forecast_meta: Optional[ForecastMeta] = None` |
| `src/services/comparison_engine.py` (`fetch_forecast_for_location` ~:525, Bau :424) | MODIFY | `forecast.meta` in `result["forecast_meta"]` tragen, ins `LocationResult` reichen (Cache-Treffer liefert dasselbe `meta`, siehe `_fetch_compare_series`) |
| `src/services/comparison_parallel.py` | prüfen | baut nur Fehler-`LocationResult`; vermutlich keine Änderung |
| `src/services/validator_render_service.py:428` | prüfen | Default `None` genügt, Validator-Pfad unverändert |
| `src/output/renderers/fallback_notice.py` | MODIFY (klein) | neue Funktion `build_compare_fallback_lines(location_results, lang)`: je Ort `build_fallback_lines(meta)` (Formulierung unverändert), Ortsname vorangestellt; 0 Zeilen im Normalfall |
| `src/output/renderers/email/compare_html.py` (`_render_app_footer` :1611, Aufruf :1834) | MODIFY | Hinweisblock aus den Ortszeilen, Footer-String bleibt |
| `src/output/renderers/comparison.py` (`render_comparison_text` :177, `render_compare_telegram` :762) | MODIFY | Klartext- und Telegram-Zeile |
| `src/i18n/` Katalog | MODIFY | ein Muster `Ort: <Zeile>` bzw. Überschrift DE/EN (nur falls nötig) |
| `tests/…` | CREATE | Verhaltenstests (Engine trägt meta; HTML/Plain/Telegram mit/ohne Vertretung; zwei Orte, nur einer betroffen; Byte-Identität im Normalfall) |

### Scope Assessment
- Files: ~7 Quell-, 2–3 Testdateien · Estimated LoC: +120/−5 (Quellcode ~70, i18n ~10) · Risk: MITTEL
  (Mail-Inhalts-Dateien ⇒ Renderer-Commit-Gate, `email_spec_validator.py`; Normalfall muss byte-identisch bleiben).

### Technical Approach
1. **Datenweg:** `ForecastMeta` je Ort bis zum Renderer tragen (transient, kein Persistenzrisiko, bestehende Aufrufer unverändert durch Default `None`).
2. **Formulierung:** ausschließlich `build_fallback_lines` (Trip/Compare-Gate). `select_fallback_meta` bleibt ungenutzt (verwirft die Ortszuordnung); neu nur eine dünne Mehrort-Hülle, die pro Ort aufruft.
3. **Darstellung (Empfehlung):** ein Hinweisblock unter der Vergleichstabelle, je betroffenem Ort eine Zeile mit Ortsname; Orte ohne Vertretung erscheinen nicht; ohne Vertretung gar kein Block. Fehlerorte (`error`) werden übersprungen.
4. **Kanäle:** HTML + Klartext (zwingend), Telegram-Compare-Langform (wie Trip S2b, ADR-0095). SMS/Premium-SMS (≤160 Zeichen) bewusst nicht — wie bei Trip S2b; als Known Limitation in die Spec.
5. **Prüfung:** echt zugestellte Staging-Compare-Mail via `email_spec_validator.py`; Vertretung erzwingen per Test-Seam im Staging oder Nachweis auf Datenweg-Ebene (Staging liefert i. d. R. keine Vertretung).

### Dependencies
Upstream: `ForecastMeta` (`app/models.py:81`), `_fetch_compare_series` (Cache/Single-Flight #2234). Downstream: `notification_service`, `scheduler_dispatch_service`, `compare_alert_preview_service`, `compare_official_alert` (alle rufen die Renderer; Alarm-Mails brauchen den Hinweis nicht — Spec klärt: nur Briefing-Compare-Mail).

### Open Questions
- [ ] Darstellung: namentlich je Ort (Empfehlung) · nur „mindestens ein Ort" · Markierung in der Spalte — PO-Entscheidung in der Spec (Empfehlung: namentlich, nur dort steckt die Information).
- [ ] Telegram-Compare mit in den Umfang (Empfehlung: ja, ADR-0095)? Alarm-/Vorschau-Pfade ausgenommen?
- [ ] Cache-Treffer: trägt der gecachte `forecast` sein `meta` unverändert? (in Phase 4 per RED-Test klären)
