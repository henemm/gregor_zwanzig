---
entity_id: fix_1794_arome_precip_prob_null
type: module
created: 2026-09-18
updated: 2026-09-18
status: approved
version: "1.0"
tags: [rendering, none-handling, rain-probability, sms, telegram, premium-sms]
---

# Fix #1794: `pop_pct=None` wird im geteilten SMS/Telegram/Premium-SMS-Token als "-" statt als Fehlend-Marker angezeigt

## Approval

- [x] Approved

## Purpose

Wenn `precipitation_probability` (`pop_pct`) trotz des bereits produktiven Fallback-Mechanismus
(WEATHER-05a/05b, `src/providers/openmeteo.py:337-469`) für ein ganzes Segment `None` bleibt
(Cache-/Probe-Fehlschlag, Fallback-Kandidat erschöpft, Netzfehler), zeigt der gemeinsame
`PR`-Token-Baustein (genutzt von SMS, Telegram UND Premium-SMS/Garmin) ein `"-"` — identisch zur
Darstellung "geprüft, kein Regen". Das ist irreführend: Der Nutzer liest "kein Regen erwartet",
tatsächlich liegt aber "keine Daten vor" vor. Der Grund: `compute_has_gap()`
(`src/services/notification_service.py:356-389`) prüft nur, ob für jede erwartete Fensterstunde
überhaupt ein Datenpunkt existiert — NICHT, ob ein einzelnes Feld (`pop_pct`) innerhalb eines
vorhandenen Datenpunkts `None` ist. Eine vollständige Stundenreihe, bei der jeder Datenpunkt
`pop_pct=None` trägt, ergibt also `has_data_gap=False`, während die abgeleiteten `pop_hourly`-
Samples trotzdem leer bleiben — ein isolierter Pro-Metrik-Fehlbestand, den die bestehende
Gap-Markierung (`"?"`, `_gap_or`) nicht erkennt.

**🔴 Korrektur nach TDD-RED (18.09.2026) — zwei ursprünglich angenommene Fundstellen entfallen
komplett, nicht nur eine AC:**

1. **`_row_risk` (html.py:234):** Der `_safe_float`-Default-Bug dort hat rechnerisch KEINE
   beobachtbare Wirkung auf den gerenderten Risiko-Punkt. `worst = max((lvl for lvl in levels if
   lvl is not None), default="green", key=_STAGES.index)` — "green" ist gleichzeitig die
   niedrigste Stufe in `_STAGES` UND der Default bei leerer Liste. Ein fälschlich auf `"green"`
   gesetztes `pop_sev` (statt korrekt herausgefiltertem `None`) kann `worst` in KEINEM Szenario
   verändern. Dasselbe gilt für die Paar-Eskalation (`escalate_pair_watch`, nur bei
   `worst=="yellow"` relevant) — `pop_sev` ist nie `"yellow"`, wenn `pop` `None` ist.
2. **`_render_mobile_hour_list` (html.py:320-348, inkl. der vermeintlichen `"(0%)"`-Anzeige
   Z.443-450):** Diese Funktion ist **toter Code** — im gesamten Repo gibt es außer ihrer eigenen
   Definition KEINEN Aufrufer (verifiziert per Repo-weitem Grep). Die tatsächlich produktiv
   genutzte Mobilansicht ist `_render_mobile_compact_rows` (html.py:912, aufgerufen aus
   `render_html()` Z.1241/1299/1325), die über `_render_html_table` (Z.705) auf `fmt_val()`
   (`helpers.py:762`) zurückgreift. `fmt_val()` hat eine frühe Guard-Klausel
   `if val is None: return "–"` (helpers.py:777-778) — VOR jeder Key-spezifischen Verzweigung,
   also auch vor dem `"pop"`-Zweig (helpers.py:890-894). Der produktive E-Mail-Renderpfad ist für
   `pop_pct=None` damit **bereits vollständig korrekt** — kein Fix, kein Test nötig.

Beide Funde bedeuten: **Diese Spec behandelt ausschließlich noch den `PR`-Token in
`src/output/tokens/`.** E-Mail-Rendering (Desktop UND Mobil) ist bereits None-sicher und nicht
mehr Gegenstand.

**Nicht Gegenstand:** die Ursache (Météo-France/`meteofrance_seamless` liefert
`precipitation_probability` strukturell `null`) und der Fallback-Mechanismus selbst — beide
bleiben unverändert. E-Mail-Rendering ist bereits korrekt (s. o.). Betroffen ist ausschließlich
der `PR`-Token-Aufbau für SMS/Telegram/Premium-SMS im Restfall, in dem `pop_pct` trotz Fallback
`None` bleibt.

## Source

- **File:** `src/output/tokens/builder.py`
  - **Identifier:** `_gap_or` (Z.156-166) — segmentweites `has_data_gap`-Flag, nicht pro Metrik
  - **Identifier:** `PR`-Token-Aufbau, Kernschleife (Z.387-402, konkret `("PR", today.pop_hourly, False)` Z.389)
- **File:** `src/output/tokens/metrics.py`
  - **Identifier:** `render_threshold_peak_value` (Z.29-67, konkret `if not samples: return "-"` Z.47-48)
- **File:** `src/output/renderers/sms_trip.py`
  - **Identifier:** `pop_hourly`-Konstruktion (Z.321-323: `pop = getattr(dp, "pop_pct", None); if pop is not None and pop > 0: pop_samples.append(...)`), `has_data_gap` kommt 1:1 von außen aus `compute_has_gap()` rein (Docstring Z.221-224), NICHT aus `pop_pct`-Vollständigkeit — daher die Entkopplung
- **Explizit NICHT betroffen (s. Purpose-Korrektur):** `src/output/renderers/email/html.py`
  (`_row_risk`, `_render_mobile_hour_list` — toter Code) sowie `_render_mobile_compact_rows`/
  `_render_html_table`/`fmt_val` (bereits None-sicher)

> Schicht-Hinweis: reine Python-Core-Änderung (`src/output/tokens/`, ggf. `src/output/renderers/sms_trip.py`), kein Go-/Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~15-30 (eine gezielte, metrik-lokale Ergänzung am `PR`-Token-Pfad + Tests)
- **Files:** ~2-3 (builder.py und/oder metrics.py, plus 1 neue Testdatei)
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/openmeteo.py:337-469` (WEATHER-05a/05b) | Upstream | Liefert `pop_pct` im Normalfall bereits belegt; erzeugt nur im Restfall `None` — dieser Fix reagiert auf das Ergebnis, ändert den Mechanismus nicht |
| `src/services/notification_service.py:356-389` (`compute_has_gap`) | Kontext | Segmentweite, nicht pro-Metrik-Gap-Erkennung — Ursache der Entkopplung, bleibt unverändert |
| `tests/tdd/test_sms_unknown_on_missing_data.py` | Vorbild | Bestehender Präzedenzfall für "fehlender Wert → `?` statt stiller `-`-Entwarnung", gleiches Fixture-Muster (`_dp()`, `_regular_segment()`, `compute_has_gap()` real aufgerufen) |
| `src/app/metric_catalog.py:408-421` (`rain_probability`) | Kontext | `default_enabled=False` — Sichtbarkeit bleibt auf manuell aktivierte Nutzer beschränkt |

## Implementation Details

```
SMS/Telegram/Premium-SMS PR-Token (builder.py + metrics.py):
  - render_threshold_peak_value() rendert heute "-" sowohl bei "keine Samples wegen
    Segment-Gap" als auch bei "isoliert fehlender Einzelwert" (alle Datenpunkte im Fenster
    vorhanden, aber jeder mit pop_pct=None). Diese zwei Fälle müssen unterscheidbar werden:
    wenn die pop-Samples für das Segment leer sind, OBWOHL has_data_gap=False ist (sonst
    vollständiger Fetch), muss der PR-Token trotzdem ein Fehlend-Symbol zeigen (bestehende
    Konvention: "?", siehe _gap_or, Z.156-166) statt "-".
  - Der Fix darf die bestehende segmentweite has_data_gap-Logik nicht verändern, sondern
    ergänzt eine metrik-lokale Prüfung für pop/rain_probability an der PR-Token-Stelle
    (z. B.: leere pop_hourly-Samples UND alle zugrundeliegenden Datenpunkte im Fenster
    tatsächlich vorhanden, aber pop_pct durchgängig None → Fehlend-Symbol statt "-").
```

## Expected Behavior

- **Input:** Ein Segment, dessen Datenpunkte im Fenster vollständig vorhanden sind
  (`has_data_gap=False`), bei dem aber jeder Datenpunkt `pop_pct=None` trägt (WEATHER-05b-
  Fallback für dieses Feld fehlgeschlagen).
- **Output:** SMS/Telegram/Premium-SMS (`PR`-Token): Fehlend-Symbol statt `"-"`, auch wenn
  `has_data_gap=False` bleibt.
- **Side effects:** keine — reine Darstellungskorrektur, keine Datenmodell-Änderung, kein
  Einfluss auf andere Metriken, auf E-Mail-Rendering oder auf den Fallback-Mechanismus selbst.

## Acceptance Criteria

- **AC-1:** Given ein Segment mit isoliert fehlendem `pop_pct` (alle Datenpunkte im
  Fenster vorhanden, jeder trägt `pop_pct=None`, `has_data_gap=False` bleibt korrekt) / When
  der `PR`-Token für SMS, Telegram und Premium-SMS gebaut wird (gemeinsamer Code-Pfad) / Then
  zeigt der Token ein Fehlend-Symbol statt `"-"` für die Regenwahrscheinlichkeit.
  - Test: Segment über den echten Konstruktionsweg aufbauen (echte `ForecastDataPoint`-Objekte
    mit `pop_pct=None`, `compute_has_gap()` real aufrufen und `has_data_gap is False`
    verifizieren), `SMSTripFormatter().format_sms(...)` aufrufen und den resultierenden
    `PR`-Token-Wert prüfen — er darf nicht `"-"` sein, sondern muss das Fehlend-Symbol zeigen;
    identisch für Telegram und Premium-SMS, da sie denselben Builder-Code teilen.

## Known Limitations

- **Telegram-Verifikation (TDD GREEN, 18.09.2026):** Telegram hat zwei Codepfade.
  `telegram_style="kurzform"` sendet `report.sms_text` — läuft über denselben
  `SMSTripFormatter()`/`builder.py`-Pfad wie SMS/Premium-SMS und ist damit vom
  implementierten Fix automatisch mitabgedeckt. `telegram_style="rich"` (Default,
  `render_telegram_bubbles()`, `narrow.py:659`) war bereits vor diesem Fix None-sicher: die
  Stundentabelle nutzt `fmt_val()` (wie E-Mail, `val is None → "–"`), die Kurzübersichtszeile
  zeigt bei fehlendem `pop_pct` `"–"` statt einer falschen Null/Entwarnung — kein reproduzierbares
  Fehlverhalten im Sinne dieser Spec. Kleine Inkonsistenz (`"–"` statt `"?"` in der
  Kurzübersichtszeile, andere Symbolkonvention als builder.py) bewusst NICHT Teil dieses Fixes —
  rein kosmetisch, kandidat für #1199 falls gewünscht.
- **E-Mail-Rendering (Desktop und Mobil) ist NICHT Teil dieses Fixes** — beide Pfade sind bereits
  None-sicher (`fmt_val()`, `_ampel_dot_severity()`) bzw. der ursprünglich vermutete Bug lag in
  totem, nie aufgerufenem Code (`_render_mobile_hour_list`). Kein Fix, kein Test dafür nötig.
- `_row_risk`/html.py:234 bewusst ausgeklammert: der dortige `_safe_float`-Default-Bug hat keine
  beobachtbare Wirkung auf den gerenderten Risiko-Punkt (Beweis s. Purpose). Kein Fix, kein Test.
- `_safe_float(..., default=0.0)` in `_row_risk` betrifft identisch auch `gust`, `wind`, `precip`,
  `thunder`, `visibility`, `uv`, `freezing_level` — bereits oben als wirkungslos für `pop`
  nachgewiesen; für die anderen Metriken nicht geprüft und nicht Teil dieses Fixes. Gehört als
  Nebenbefund in das rollierende Sammel-Issue #1199, falls dort ein echter Effekt vermutet wird.
- Die hier behandelte Restlücke tritt nur ein, wenn zusätzlich zum ursprünglichen API-seitigen
  `null` auch der WEATHER-05b-Fallback fehlschlägt. Es gibt keinen belastbaren
  Häufigkeits-Nachweis für diesen Restfall — er ist strukturell selten, aber nicht
  ausgeschlossen, und muss deshalb korrekt dargestellt werden.
- Der WEATHER-05a/05b-Mechanismus selbst bleibt unverändert und ist nicht Gegenstand dieser
  Spec (siehe `docs/specs/modules/metric_availability_probe.md`,
  `docs/specs/modules/model_metric_fallback.md` — beide Status "draft", Code aber produktiv).
- Keine Doku-Ergänzung in `docs/reference/decision_matrix.md` nötig — der ursprüngliche
  Lösungsvorschlag aus Issue #1794 ("bekannte Lücke dokumentieren") ist durch den
  Live-Befund überholt: Es gibt keine dauerhafte Lücke mehr, nur eine seltene Restlücke,
  die als Anzeige-Bug im Token-Builder behandelt wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Renderer-Bugfix innerhalb bestehender Konventionen (None-sichere
  Darstellung ist bereits etablierter Standard in `helpers.py`, hier auf den Token-Builder
  übertragen) — keine neue Grundsatzentscheidung zu Kanälen, Provider, Datenmodell, Auth oder
  Editor-Paradigma betroffen. Keine der in `docs/adr/README.md` definierten Entscheidungsflächen
  wird berührt.

## Changelog

- 2026-09-18: Initial spec created
- 2026-09-18: TDD-RED-Korrektur 1 — `_row_risk`/html.py:234-AC gestrichen (rechnerisch
  wirkungslos, kein zulässiger Bug-Nachweis möglich)
- 2026-09-18: TDD-RED-Korrektur 2 — E-Mail-Mobilansicht-AC vollständig gestrichen: Zielfunktion
  `_render_mobile_hour_list` ist toter Code (kein Aufrufer im Repo), die produktiv genutzte
  `_render_mobile_compact_rows`/`fmt_val`-Pipeline ist bereits None-sicher. Spec behandelt jetzt
  ausschließlich den `PR`-Token (SMS/Telegram/Premium-SMS), einzige verbliebene AC neu als AC-1
  nummeriert, Scope-Schätzung entsprechend deutlich reduziert.
