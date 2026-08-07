# Context: feat-1492-s2b-fallback-sichtbarkeit

**Workflow:** `feat-1492-s2b-fallback-sichtbarkeit` · **Issue:** #1492 Scheibe 2b
**Gemessen am Stand:** `63383ddb` (= Prod-Stand nach Auslieferung von 2a)
**Vorgänger:** S1 (`e34d9bc9`), S2a (`63383ddb`, ADR-0047)
**Übergeordneter Kontext:** `docs/context/feat-1492-gewitter-fallback-kette.md` (Abschnitt
„Scheibe 2 — PO-Entscheidungen 2026-08-06", Punkte E1/E2/E3)

## Request Summary

Scheibe 2a hält seit dem 2026-08-06 fest, *dass* eine Gewitter-Direktquelle vertreten wurde —
aber nur intern in `ForecastMeta`. Der Nutzer sieht davon nichts. 2b macht die Vertretung im
Briefing sichtbar: **E-Mail und Telegram**, in **Klartext statt Technik**, und stellt den
bestehenden technischen Hinweis der Hauptvorhersage mit um.

## Bereits entschieden (nicht neu aufmachen)

| # | Entscheidung | Quelle |
|---|---|---|
| E1 | Kanäle: **E-Mail + Telegram**. SMS ausdrücklich ausgenommen | Kontext-Doc 2026-08-06 |
| E2 | Klartext, **auch für den Bestandshinweis** — kein Nebeneinander zweier Stile | Kontext-Doc 2026-08-06 |
| — | ADR-0007 („Daten statt Empfehlungen") ist nicht berührt: Herkunft ist ein Fakt | Kontext-Doc 2026-08-06 |
| — | 2b muss **`fallback_metrics` mit auswerten**, nicht nur `fallback_model` | ADR-0047 Folgepflichten, 2a-Spec KL 3 |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/html.py:528-539` | Erzeugt den heutigen Hinweis (HTML). Kommentar dort: „spiegelt plain.py" — **bewusst dupliziert, nicht geteilt** |
| `src/output/renderers/email/plain.py:362-367` | Erzeugt den heutigen Hinweis (Plaintext). Identische Formatlogik |
| `src/output/renderers/email/helpers.py:468-517` | `build_origin_footer` / `render_origin_footer_text` / `render_origin_footer_html` — **der geteilte Fußzeilen-Helper**, von *allen* Mail-Renderern benutzt (plain, compact, html, compare_html, alert/render, alert/official_alerts). Kennt heute **kein** Fallback-Konzept |
| `src/output/renderers/email/compact.py:258-265` | Kompakt-Briefing: nutzt die geteilte Herkunfts-Fußzeile, zeigt aber **keinen** Fallback-Hinweis |
| `src/output/renderers/email/compare_html.py:1388-1391` | Ortsvergleichs-Mail: `build_origin_footer("compare", source="Open-Meteo")` — fester String, **kein** Fallback-Hinweis |
| `src/output/renderers/narrow.py:215-309` | `_tg_day_footer` — Telegram-Tagesfußzeile, heute ⚡/Sicht/0°C-Grenze |
| `src/output/renderers/narrow.py:606,733-742` | `render_telegram_bubbles` — einziger Produktiv-Aufruf der Fußzeile |
| `src/providers/thunder_enrichment.py:280-292` | Schreibstelle der Gewitter-Markierung (2a) |
| `src/app/models.py:80-95` | `ForecastMeta.fallback_model` / `fallback_metrics` / `fallback_reason` |
| `tests/unit/test_model_metric_fallback.py:179-255` | `TestFooterFallbackInfo` — 4 Tests, bewachen den heutigen Wortlaut |
| `tests/tdd/test_issue_1141_cross_provider_fallback.py:430-459` | Fünfter Test auf denselben Wortlaut (`"Fallback: at_direct"`) |
| `tests/tdd/test_telegram_footer_metric_gating.py:106-149` | 3 Tests, bewachen die Telegram-Fußzeile |

## Gemessener Ist-Stand

### Der Hinweis erscheint heute in 2 von 7 Ausgaben

| Ausgabe | Fallback-Hinweis heute |
|---|---|
| Trip-Briefing E-Mail HTML (`full`) | ✅ `Fallback cape, visibility: icon_eu` |
| Trip-Briefing E-Mail Plaintext (`full`) | ✅ derselbe Text |
| Trip-Briefing E-Mail (`compact`) | ❌ 0 Treffer |
| Ortsvergleichs-Mail | ❌ 0 Treffer |
| Telegram-Langform (Bubbles) | ❌ 0 Treffer |
| Telegram-Kurzform / SMS | ❌ 0 Treffer (bewusst, E1) |
| Alarm-Mails (`alert/render.py`, `official_alerts.py`) | ❌ 0 Treffer |

### 🔴 `fallback_metrics` mischt zwei Namenssysteme

Das ist der wichtigste Einzelbefund dieser Phase. Dieselbe Liste enthält je nach Auslöser
**unterschiedlich benannte** Einträge:

| Auslöser | `fallback_reason` | Inhalt von `fallback_metrics` | Beispielwerte |
|---|---|---|---|
| Metrik-Lücke (#1115/WEATHER-05b) | `metric_gap` | **Open-Meteo-Parameternamen** (`_PARAM_TO_FIELD`) | `cape`, `temperature_2m`, `weather_code`, `visibility` |
| Modell-5xx | `model_5xx` | dieselben Parameternamen | wie oben |
| Cross-Provider-Totalausfall | `cross_provider_total_outage` | — | — |
| Schnee-Anreicherung | `snow_geosphere` | **Feldnamen** des Datenpunkts | aus `_stamp_snow` |
| **Gewitter-Vertretung (2a)** | `thunder_source_unavailable` | **Feldnamen** des Datenpunkts (`thunder_enrichment.py:283-285`) | `lightning_density_per_km2_3h`, `lightning_potential_lpi_jkg`, `hail_potential_grau_gsp` |

**Folge für 2b:** Die Klartext-Übersetzung muss beide Namenssysteme abbilden. Und der einzige
**zuverlässige** Nachweis einer Gewitter-Vertretung ist das Vorkommen eines der drei
Gewitter-**Feldnamen** in `fallback_metrics` — nicht `fallback_model` (Merge-Schutz, s.u.) und
auch nicht `fallback_reason` allein (kann im Kollisionsfall vom Grundvorhersage-Fallback belegt
sein).

Die drei Gewitter-Feldnamen sind abschließend definiert in
`thunder_enrichment.py:36-43` (`_SIGNAL_ZU_FELD` + `_EINZELWERT_FELD`).

### 🔴 Der Merge-Schutz aus 2a macht `fallback_model` unzuverlässig

`thunder_enrichment.py:286-288`: `fallback_model`/`fallback_reason` werden **nur** gesetzt, wenn
noch `None`. Liegt bereits ein Grundvorhersage-Fallback (#1115) vor, steht dort dessen
Modellname — eine Gewitter-Vertretung hat trotzdem stattgefunden. `fallback_metrics` ist
davon nicht betroffen (immer `extend`).

Umgekehrt gilt es auch: steht in `fallback_model` ein Gewitterquellen-Name, kann gleichzeitig
ein Metrik-Fallback in `fallback_metrics` stehen. Die heutige Formulierung
`Fallback {metrics}: {model}` **verknüpft beide Angaben ungeprüft** und behauptet damit im
Kollisionsfall einen Zusammenhang, den es nicht gibt. Das ist ein bestehender Darstellungsfehler,
der durch 2a erst erreichbar wurde.

### Wertebereiche für das Klartext-Mapping

`fallback_model` (gemessen, alle Schreibstellen in `src/providers/`):

| Wert | Woher | Bedeutung |
|---|---|---|
| `at_direct`, `de_direct`, `fr_direct` | `openmeteo.py:1055` (Cross-Provider-Totalausfall), `region_routing.py:33-36` | nationale Direktquelle |
| `fr_direct`, `de_direct`, `eu_direct` | `thunder_enrichment.py:287` | Gewitter-Ersatzquelle |
| `meteofrance_arome`, `icon_d2`, `metno_nordic`, `icon_eu`, `ecmwf_ifs04` | `openmeteo.py:1077,1167`, `REGIONAL_MODELS` | Open-Meteo-Rechenmodell |

`icon_seamless` ist **kein** Fallback-Wert (nur `meta.model`).

### Telegram: Datenfluss und Abgrenzung zur Kurzform

- `_tg_day_footer(segments, enabled_metric_ids, *, night_weather, tz, has_gap, …)`
  (`narrow.py:215-224`) bekommt `segments` bereits übergeben ⇒ `segments[0].timeseries.meta`
  ist erreichbar, **keine Signaturerweiterung nötig**. Präzedenz: `plain.py:362`, `html.py:528`.
- Die Fußzeile erscheint **einmal pro Nachrichten-Rendervorgang** (nicht pro Tag, nicht pro
  Segment), als letzter Baustein der Kurzübersicht-Bubble (`narrow.py:733-742`).
- Zeichengrenzen: in `narrow.py` **keine** Kürzung — nur Umbruch (`_TG_PROSE_WIDTH = 56`,
  `_TG_TABLE_WIDTH = 32`, `_wrap()`). Harte Grenze erst auf Kanal-Ebene bei 4096 Zeichen
  (`src/output/channels/telegram.py:18`). Eine Zusatzzeile ist unkritisch.
- **Telegram-Kurzform erreicht `narrow.py` gar nicht:** bei `telegram_style == "kurzform"`
  sendet `notification_service.py:353-372` den bereits gerenderten `report.sms_text`
  (`SMSTripFormatter`, 160-Zeichen-Budget), die Bubbles werden nie gelesen. Ein Hinweis in
  `_tg_day_footer` ist damit **strukturell** von der SMS-Ausgabe getrennt — E1 ist auf diesem
  Weg ohne Sonderfallcode erfüllbar.

## Existing Patterns

- **Geteilte Fußzeile existiert schon:** `build_origin_footer` wird von allen sechs
  Mail-Renderern aufgerufen. Es ist das etablierte Muster für „eine Aussage, alle Mail-Ausgaben".
- **Duplikation ist der Ist-Zustand des Fallback-Hinweises:** `html.py` spiegelt `plain.py`
  ausdrücklich per Kommentar. Das ist genau die Sorte Kopie, die die Projektregel zur
  Code-Teilung meidet.
- **Nicht-Kaschieren als Invariante:** ADR-0018 (Grundvorhersage), ADR-0047 (Gewitter). Beide
  verlangen den Vermerk, keiner schreibt seinen Wortlaut fest.
- **Herkunftsangabe als Fakt, nicht als Empfehlung:** ADR-0034 hat Zeile 2 der Fußzeile bereits
  von „interner Renderer-Pfad" auf „reale Datenquelle" umgestellt — dieselbe Denkrichtung wie E2.

## Dependencies

- **Upstream:** `ForecastMeta` (`app/models.py:80-95`), befüllt von `openmeteo.py` (4 Stellen)
  und `thunder_enrichment.py:280-292`. 2b **liest** nur — kein Eingriff in die Datenerhebung.
- **Downstream:** alle Briefing-Mails und Telegram-Nachrichten. Kein Frontend, keine Go-API,
  kein Datenmodell.

## Existing Specs & ADRs

- `docs/adr/0047-gewitter-vertretung-zwischen-direktquellen.md` — Folgepflicht „Sichtbarkeit
  ist 2b", inkl. der `fallback_metrics`-Auflage
- `docs/adr/0018-provider-fallback-ohne-kaschieren.md` — Ursprung der Invariante
- `docs/adr/0034-herkunftsfusszeile-reale-datenquelle.md` — geteilte Fußzeile, Zeile-2-Regel
- `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` — Abgrenzung
- `docs/specs/modules/feat_1492_s2a_thunder_vertretung.md` — KL 3 (Übergabe an 2b)
- `docs/specs/modules/model_metric_fallback.md` — Spec des Bestandsmechanismus

## Risks & Considerations

1. **Fünf Bestandstests brechen planmäßig** (4× `test_model_metric_fallback.py:213-255`,
   1× `test_issue_1141_cross_provider_fallback.py:430-459`). Sie prüfen `"fallback" in
   body.lower()` und den Rohwert `"icon_eu"`/`"at_direct"`. Sie müssen **mitgezogen**, nicht
   gelöscht werden — sie bewachen echte Zusicherungen (u.a. das `" : "`-Artefakt aus #1145).
   ⚠️ `test_no_fallback_no_hint` überlebt eine Eindeutschung wörtlich, bewacht danach aber
   nichts mehr Substanzielles — er braucht eine neue Prüfung gegen den deutschen Text.

2. **Renderer-Commit-Gate #811 greift.** `src/output/renderers/email/*.py` steht auf der
   Sperrliste. Vor dem Commit müssen `tests/tdd/test_issue_811_mode_matrix.py` grün sein und
   ein `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail bestanden
   haben.

3. **Umfangsfrage, die die Spec beantworten muss:** 2 von 7 Ausgaben zeigen den Hinweis heute.
   Wird der Hinweis auf Kompakt-Mail / Ortsvergleichs-Mail ausgedehnt (E1 sagt „E-Mail", nicht
   „Trip-Briefing-Vollversion"), wächst der Umfang deutlich. Vorschlag zur Entscheidung durch
   den PO.

4. **Regel zur Trip/Compare-Teilung:** Eine dritte Kopie der Formulierungslogik (Telegram)
   neben den zwei bestehenden wäre ein Verstoß. Der geteilte Ort ist bereits vorhanden
   (`email/helpers.py`) — allerdings ist er ein *E-Mail*-Modul, während Telegram ihn ebenfalls
   braucht. Die Ablage der geteilten Funktion ist eine bewusste Entscheidung für die Spec.
   Zusätzlich: `pendant_gate.py` blockiert neue Dateien mit `trip_`/`compare_`-Präfix unter
   `src/output/renderers/**` — ein neutraler Name ist Pflicht.

5. **Wortlaut ist PO-Sache.** Die Übersetzung technischer Kennungen (`eu_direct`,
   `meteofrance_arome`, `cape`) in Klartext ist eine Produktentscheidung, keine technische.
   Die Spec legt eine vollständige Tabelle zur Freigabe vor.

6. **Der ungeprüfte Zusammenhang** zwischen `fallback_metrics` und `fallback_model` (s.o.)
   ist ein bestehender Darstellungsfehler. Ob 2b ihn mitbehebt oder als eigener Befund
   gebucht wird, entscheidet die Spec.

7. **Telegram-Kurzform bleibt ohne Hinweis** — sie sendet den SMS-Text. Fachlich konsistent mit
   E1 (160-Zeichen-Budget), aber ein Nutzer mit `telegram_style="kurzform"` bekommt „Telegram"
   und trotzdem keinen Hinweis. Als Known Limitation festzuhalten.
