---
entity_id: compare_official_alert_channels
type: bugfix
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
workflow: fix-1332-compare-official-alerts
tags: [compare, official-alerts, sms, telegram, renderer, adr-0025]
---

<!-- Issue #1332 -->

# Compare: Amtliche Warnungen in SMS/Telegram konsistent zum Trip-Briefing

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich (Compare) meldet amtliche Warnungen heute anders als das
Trip-Briefing: Compare-SMS zeigt sie **gar nicht**, Compare-Telegram zeigt sie
**ungefiltert** (auch gelb/grün) und **ohne Kürzel/Stufe**. Dieser Fix bringt
beide Compare-Kanäle auf denselben Sicherheits-Standard, den #1318 für den
Trip-Pfad bereits etabliert hat: Filter ab Stufe orange (`MIN_SMS_LEVEL`),
Kürzel aus dem einzigen Katalog `hazard_symbols.py`. Reiner Renderer-Fix — die
Warndaten (`LocationResult.official_alerts`) liegen bereits vollständig vor,
kein Datenmodell-Fix.

## Source

- **File:** `src/output/renderers/comparison.py` — `render_compare_sms` (469–539), `_sms_location_part` (449–466), `render_compare_telegram` (361–434)
- **File:** `src/output/renderers/alert/official_alerts.py` — `render_official_alerts_plain` (234–252), `build_official_alert_notices` (1692), `render_official_alert_telegram` (1415), `official_alert_source_label` (103)
- **File:** `src/output/renderers/sms_trip.py` — `_official_alert_entries` (93–119)
- **File:** `src/output/tokens/hazard_symbols.py` — `sms_symbol_for`, `MIN_SMS_LEVEL`, `LEVEL_LETTERS`, `LEVELLESS_HAZARDS`
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` — Kürzel-Legende, Bedingung `context !== 'vergleich'` (Zeile 665)

> **Schicht-Hinweis:** Alle Backend-Änderungen liegen im Python-Core (`src/output/...`,
> Renderer-Schicht, keine Provider-/Domänen-Logik). Die Frontend-Änderung ist
> reine SvelteKit-UI (`frontend/src/lib/components/shared/`).

## Estimated Scope

- **LoC:** ~+90 / -10 (unter dem 250-Limit)
- **Files:** 3 Code-Dateien + 1 Frontend-Datei + mind. 2 Test-Dateien
- **Effort:** medium (Risk Level MEDIUM — betrifft zwei versendete Kanäle; Trip-Pfad darf nicht brechen)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/comparison.py` | MODIFY | Compare-SMS: Warn-Marker pro Ort ab orange. Compare-Telegram: Level-Filter + `build_official_alert_notices`/`render_official_alert_telegram` statt `render_official_alerts_plain` |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Neue geteilte Funktion `official_alerts_to_sms_entries()` (Extraktion des alert-basierten Kerns aus `sms_trip.py`) |
| `src/output/renderers/sms_trip.py` | MODIFY | `_official_alert_entries()` wird dünner Wrapper um `official_alerts_to_sms_entries()`; Trip-Verhalten bleibt bit-identisch |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Bedingung `context !== 'vergleich'` (Zeile 665) entfernen → Kürzel-Legende auch im Vergleich |
| `tests/tdd/test_compare_sms_official_alerts.py` | CREATE | Kern-Tests Compare-SMS mit amtlichen Warnungen (echte Fixtures) |
| `tests/tdd/test_compare_telegram_official_alerts.py` | CREATE | Kern-Tests Compare-Telegram mit amtlichen Warnungen (echte Fixtures) |
| `tests/tdd/test_sms_official_alert_tokens.py` | MODIFY | Charakterisierungstest: Trip-SMS-Verhalten vor/nach Extraktion bit-identisch |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.tokens.hazard_symbols.sms_symbol_for` | intern (Funktion) | Einziger SMS-Kürzel-Katalog, wird 1:1 wiederverwendet (kein zweiter Katalog) |
| `output.tokens.hazard_symbols.MIN_SMS_LEVEL` | intern (Konstante) | Sicherheits-Schwelle ab orange (3), identisch für Trip und Compare |
| `output.renderers.alert.official_alerts.dedupe_official_alerts` | intern (Funktion) | Geteilter Dedup-Baustein, keine eigene Dedup-Logik in Compare |
| `output.renderers.alert.official_alerts.build_official_alert_notices` / `render_official_alert_telegram` | intern (Funktion) | Kontext-agnostisches DTO (`OfficialAlertNotice`, `trip=None` bereits unterstützt) + Telegram-Renderer, geteilt mit dem Trip-Pfad (`narrow.py:_official_alert_bubble`) |
| `app.user.LocationResult.official_alerts` | intern (Datenmodell) | Bereits befüllte Warndaten pro Ort (`services/comparison_engine.py:223–224`), keine Änderung nötig |
| ADR-0025 (Eine Gewitter-Quelle für alle Briefing-Kanäle) | ADR | Verbietet widersprüchliche Kanal-Aussagen zur selben Gefahrenlage — dieser Fix schließt genau eine solche Divergenz |
| PO-Invariante Trip/Compare-Teilung (CLAUDE.md) | Konvention | Geteilte Bausteine wiederverwenden statt nachzubauen; Ausnahmen brauchen dokumentierte Begründung |

## Implementation Details

### 1. Gemeinsamer SMS-Kern wird extrahiert (Entscheidung der offenen Schnittfrage)

`sms_trip.py:_official_alert_entries(segments, tz)` filtert/dedupliziert/
kürzelt bereits korrekt, ist aber an `list[SegmentWeatherData]` gebunden. Der
**alert-basierte innere Kern** (Eingabe `list[OfficialAlert]`) wird nach
`output/renderers/alert/official_alerts.py` extrahiert (dort liegen bereits
`dedupe_official_alerts` und die Telegram-/Notice-Bausteine — natürlicher
Ort, keine neue Trip→Compare-Abhängigkeit):

```
def official_alerts_to_sms_entries(
    alerts: list["OfficialAlert"], tz: ZoneInfo | None = None,
) -> tuple[tuple[str, str, Optional[int]], ...]:
    """Dedup -> Filter (>= MIN_SMS_LEVEL) -> (Kuerzel, Stufenbuchstabe, Stunde).
    tz=None: Stunden-Teil entfaellt ersatzlos (kein Platzhalter)."""
```

`sms_trip.py:_official_alert_entries` wird zum dünnen Wrapper: Segmente zu
einer flachen Alert-Liste zusammenfassen, dann `official_alerts_to_sms_entries`
aufrufen. Das bestehende Verhalten des Trip-Pfads bleibt bit-identisch (durch
Charakterisierungstest abgesichert, siehe Test Plan).

`comparison.py` importiert `official_alerts_to_sms_entries` direkt und ruft es
mit `loc_result.official_alerts` auf — kein zweiter Katalog, keine
duplizierte Filterlogik.

### 2. Compare-SMS: Marker pro Ort (PO-go, fest)

`_sms_location_part` hängt nach den Metrik-Zellen einen Warn-Marker an, exakt
im Rendering-Vertrag des Trip-Pfads (`tokens/render.py:_fuse`, `!`-Präfix
genau einmal, Tokens `{Kürzel}:{Stufe}` bzw. blankes Kürzel für
`LEVELLESS_HAZARDS`, mit Leerzeichen getrennt):

```
Chamonix 18/8 !TH:H
```

Hat ein Ort einen anzuzeigenden Marker (mind. ein Alert `>= MIN_SMS_LEVEL`),
wird die Zahl der Metrik-Zellen für **diesen Ort** deterministisch auf 1 statt
2 reduziert (`_SMS_METRICS_PER_LOCATION`), damit der Marker garantiert Platz
hat — Sicherheit vor Optik (Design-Leitprinzip), kein fragiles
Nachträglich-Kürzen. Orte ohne Marker zeigen weiterhin 2 Metrik-Zellen
(unverändert). Die bestehende Orts-Kürzungskaskade (` +k`, ganze Ortsblöcke
weglassen bei Gesamt-Überlauf > 140 Zeichen) bleibt unverändert darüber
liegen.

`@Stunde` wird nur ergänzt, wenn `SavedLocation.timezone` gesetzt ist (dann
`ZoneInfo(location.timezone)` an `official_alerts_to_sms_entries` durchreichen);
ohne hinterlegte Zeitzone entfällt der Stunden-Teil ersatzlos — kein
Platzhalter, konsistent mit der bestehenden Trip-Konvention.

### 3. Compare-Telegram: Filter, ausgeschrieben wie Trip (PO-Korrektur 2026-07-23)

`render_compare_telegram` ersetzt den Aufruf von `render_official_alerts_plain`
(kein Filter, kein Kürzel) durch die geteilten Trip-Bausteine, exakt wie
`narrow.py:_official_alert_bubble` es für den Trip-Pfad bereits tut. **Kein**
SMS-Kürzel im Telegram — der Warn-Block ist identisch zum Trip-Telegram-Format
(ausgeschriebene Gefahrenbezeichnung + Stufe, kein `!TH:H`):

```
filtered = [a for a in loc_result.official_alerts if a.level >= MIN_SMS_LEVEL]
if filtered:
    notices = build_official_alert_notices(None, [(a, []) for a in filtered])
    sources = list(dict.fromkeys(official_alert_source_label(a.source) for a in filtered))
    block.append(render_official_alert_telegram(
        notices, prefix=loc_result.location.name,
        source_label=" · ".join(sources),
    ))
```

`trip=None` ist von `build_official_alert_notices` bereits vorgesehen (Docstring
`official_alerts.py:124–126`: "Trip UND Ortsvergleich füllen dasselbe DTO"),
die Segment-Scope-Verdichtung ("gesamte Route") entfällt dann einfach — für
einen einzelnen Ort ist sie ohnehin nicht sinnvoll. Orte ohne Warnung
`>= MIN_SMS_LEVEL` bekommen weiterhin keinen Warn-Block (unverändert). Der
`!`-Kürzel-Marker (`_official_alert_sms_marker`) bleibt exklusiv im
Compare-SMS-Pfad (`_sms_location_part`) — der Telegram-Pfad ruft ihn nicht
mehr auf.

### 4. Frontend: Kürzel-Legende auch im Vergleich

`WeatherMetricsTab.svelte:665` — Bedingung `context !== 'vergleich' && smsSymbols`
wird zu `smsSymbols` (Kontext-Ausnahme entfällt), weil die Legende nach dem
Backend-Fix für den Vergleich genauso zutrifft wie für den Trip. Kein weiteres
Markup ändert sich (geteiltes Snippet `officialAlertsToggle`).

## Expected Behavior

- **Input:** `ComparisonResult` mit `LocationResult.official_alerts` (mind. ein
  Ort mit Warnung `>= orange`, ein Ort mit nur gelber Warnung, ein Ort ohne
  Warnung)
- **Output:**
  - Compare-SMS: der Ort mit `>= orange`-Warnung trägt einen `!`-Kürzel-Marker
    direkt am Ort; die anderen beiden Orte bleiben unverändert (2 Metrik-Zellen,
    kein Marker)
  - Compare-Telegram: nur der `>= orange`-Ort bekommt einen ausgeschriebenen
    Warn-Block (identisches Format zum Trip-Telegram, kein SMS-Kürzel); die
    gelbe Warnung erscheint nicht mehr
  - Frontend: die Kürzel-Legende ist im Vergleich-Kontext sichtbar
- **Side effects:** keine — reiner Renderer-/UI-Fix, kein Datenmodell, kein
  Versandpfad-Wechsel

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit einem Ort, dessen amtliche Warnung
  Stufe orange oder rot erreicht / When die Compare-SMS gerendert wird / Then
  zeigt genau dieser Ort einen `!`-Kürzel-Marker direkt an seiner Stelle
  (z.B. `Chamonix 18/8 !TH:H`), während Orte ohne Warnung oder nur mit
  gelber Warnung unverändert (2 Metrik-Zellen, kein Marker) bleiben
  - Test: `render_compare_sms()` mit 3 Orten (rot, gelb, keine Warnung) —
    String-Vergleich der drei Ortsteile gegen den erwarteten Marker/Nicht-Marker

- **AC-2:** Given ein Orts-Vergleich mit gemischten Warnstufen (gelb, orange,
  rot) an verschiedenen Orten / When die Compare-Telegram-Nachricht gerendert
  wird / Then erscheinen nur die Orte mit Stufe orange/rot als Warn-Block —
  Compare-Telegram zeigt Warnungen ab Stufe orange **ausgeschrieben im
  selben Format wie das Trip-Telegram** (deutsche Bezeichnung + Stufe),
  **ohne** SMS-Kurzcode; gelbe/grüne erscheinen nicht
  - Test: `render_compare_telegram()` mit 3 Orten — Assertion, dass der
    gelbe Ort keinen `⚠️`/Warn-Block-Text enthält, der orange/rote Ort die
    ausgeschriebene Stufe (`Warnstufe ROT`) und Gefahrenbezeichnung trägt,
    und dass KEIN SMS-Kürzel (`!TH:H`) im Telegram erscheint

- **AC-3:** Given der bestehende Trip-SMS- und Trip-Telegram-Pfad (Issue
  #1318) / When derselbe Segment-Datensatz vor und nach diesem Fix gerendert
  wird / Then ist die Ausgabe byte-identisch — die Extraktion des
  gemeinsamen Kerns ändert das Trip-Verhalten nicht
  - Test: Charakterisierungstest in `tests/tdd/test_sms_official_alert_tokens.py`
    (bzw. Trip-Telegram-Pendant), der die Ausgabe vor/nach der Extraktion
    auf Gleichheit prüft

- **AC-4:** Given die Kürzel-Zuordnung amtlicher Gefahren / When Compare-SMS
  oder Compare-Telegram eine Warnung rendern / Then stammt das Kürzel
  ausschließlich aus `hazard_symbols.sms_symbol_for` — es existiert kein
  zweiter Kürzel-Katalog und keine zur Trip-Filterlogik abweichende
  Implementierung in `comparison.py`
  - Test: statischer Import-Check/Unit-Test, der bestätigt, dass
    `comparison.py` `sms_symbol_for`/`official_alerts_to_sms_entries`
    importiert statt eigene Kürzel-Strings zu definieren

- **AC-5:** Given ein Nutzer öffnet den Vergleich-Editor (Wetter-Metriken-Tab,
  `context='vergleich'`) / When der Amtliche-Warnungen-Schalter aktiviert ist
  / Then wird die Kürzel-Legende (analog Trip-Kontext) angezeigt statt
  ausgeblendet zu bleiben
  - Test: Frontend-Komponententest/E2E, der `data-testid="official-alerts-symbol-legend"`
    im Vergleich-Kontext auf Sichtbarkeit prüft

## Known Limitations

- Die `@Stunde`-Ergänzung im Compare-SMS-Marker greift nur, wenn der Ort eine
  Zeitzone (`SavedLocation.timezone`) hinterlegt hat; ohne Zeitzone entfällt
  sie ersatzlos (kein Platzhalter) — analog zur bestehenden Trip-Konvention
  bei fehlendem Gültigkeitszeitraum.
- Die Segment-Scope-Verdichtung ("gesamte Route") aus `build_official_alert_notices`
  ist für Compare irrelevant (ein Ort hat keine Segmente) und wird mit
  `trip=None` einfach nicht genutzt — kein Funktionsverlust, da Compare ohnehin
  nie Segment-Scope brauchte.
- Bei mehreren gleichzeitigen Warnungen an einem Ort (z.B. Gewitter + Sturm,
  beide >= orange) zeigt der SMS-Marker mehrere Kürzel hintereinander
  (`!TH:H W:M`); das kann bei sehr langen Ortsnamen die deterministische
  1-statt-2-Metrik-Zellen-Reduktion nicht immer kompensieren — dann greift die
  bestehende `+k`-Ortskürzungskaskade (Ort entfällt ganz, wird ausgewiesen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025 (Eine Gewitter-Quelle für alle Briefing-Kanäle)
- **Rationale:** ADR-0025 verbietet, dass verschiedene Kanäle (SMS, Telegram,
  E-Mail) zur selben Gefahrenlage widersprüchliche Aussagen treffen. Der
  aktuelle Zustand (Compare-SMS zeigt nichts, Compare-Telegram zeigt alles
  ungefiltert, Trip filtert korrekt ab orange) ist genau ein solcher
  Widerspruch zwischen Kanälen desselben Produkts. Dieser Fix stellt die
  ADR-0025-Konformität für den Compare-Pfad her, indem er dieselbe Filter-
  Schwelle (`MIN_SMS_LEVEL`) und denselben Kürzel-Katalog wie der Trip-Pfad
  verwendet — keine neue Architekturentscheidung nötig, nur konsequente
  Anwendung der bestehenden.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_compare_sms_official_alerts.py` (NEU) — GIVEN 3 Orte
  (einer mit Warnung Stufe rot, einer mit Stufe gelb, einer ohne Warnung) /
  WHEN `render_compare_sms()` gerendert wird / THEN trägt nur der rote Ort den
  `!`-Kürzel-Marker, die anderen beiden bleiben unverändert (2 Metrik-Zellen)
- [ ] `tests/tdd/test_compare_sms_official_alerts.py` (NEU) — GIVEN ein Ort mit
  mehreren Warnungen unterschiedlicher Hazards >= orange / WHEN gerendert wird
  / THEN erscheinen beide Kürzel hintereinander, dedupliziert über
  `dedupe_official_alerts`
- [ ] `tests/tdd/test_compare_telegram_official_alerts.py` (NEU) — GIVEN
  dieselben 3 Orte / WHEN `render_compare_telegram()` gerendert wird / THEN
  nur der rote Ort zeigt einen ausgeschriebenen Warn-Block (Trip-Format,
  kein SMS-Kürzel), der gelbe Ort zeigt keinen Warn-Block mehr
- [ ] `tests/tdd/test_sms_official_alert_tokens.py` (ERWEITERT) — Charakterisierungstest:
  bestehender Trip-Testfall vor/nach der Extraktion von
  `official_alerts_to_sms_entries` liefert byte-identische Ausgabe
- [ ] Frontend: bestehender/erweiterter Test für `WeatherMetricsTab.svelte`
  prüft, dass `data-testid="official-alerts-symbol-legend"` im
  `context='vergleich'` sichtbar ist (nicht mehr per `{#if}` ausgeblendet)

Alle Tests laufen in der **Kern-Schicht** (deterministisch, echte
Fixture-Objekte `LocationResult`/`OfficialAlert`, kein Mock-Theater) —
Netzzugriff/Live-Dienste sind für diesen Fix nicht nötig.

## Changelog

- 2026-07-23: Initial spec erstellt — Issue #1332
- 2026-07-23: AC-2 präzisiert nach PO-Entscheidung — Compare-Telegram narrativ
  wie Trip, kein SMS-Kürzel.
