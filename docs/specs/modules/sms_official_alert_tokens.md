---
entity_id: sms_official_alert_tokens
type: feature
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.1"
tags: [sms, telegram, official_alerts, tokens, single-source-of-truth]
workflow: feat-1318-1220-kurzform-ziel-warn
---

# Amtliche Warnungen im Trip-Briefing-SMS und -Telegram (Warn-Block `!`)

## Approval

- [x] Approved — PO-Freigabe 2026-07-20

Mit der Freigabe ebenfalls bestätigt:
1. **Lieferung in zwei Scheiben** (siehe Estimated Scope): Scheibe A (sicherheitskritischer
   Kern, ~160–200 LoC) zuerst, danach Scheibe B (Telegram + Konfigurationsoberfläche). Beide
   Scheiben bleiben damit im 250-LoC-Rahmen — **kein** `loc_limit_override` nötig.
2. **`@h`-Anzeigeregel** wie in Abschnitt 2 beschrieben: die Stunde erscheint, wenn die Warnung
   zu einer bestimmten Stunde beginnt; bei ganztägiger Gültigkeit entfällt sie ersatzlos
   (`W:M`, nicht `W:M@0`). Damit ist die in den Known Limitations vermerkte Ableitungs-Unsicherheit
   aufgelöst.

## Purpose

Amtliche Unwetterwarnungen (`official_alerts`, alle Provider, 9 Gefahrenarten) erscheinen
heute ausschließlich im großen E-Mail-Briefing (Warn-Kasten). Die Trip-Briefing-SMS und das
Telegram-Trip-Briefing werten `SegmentWeatherData.official_alerts` nicht aus, obwohl die
Daten am Aufrufpunkt bereits vorliegen. Für den Weitwanderer unterwegs ist die SMS oft der
einzige erreichbare Kanal — eine sicherheitsrelevante amtliche Warnung kann so folgenlos
untergehen (Issue #1318, abgespalten aus #1317). Zusätzlich verifiziert diese Spec, dass die
Ankunftsstunden-Fensterlücke der Natursprache-Kurzzusammenfassung (Issue #1220) durch die
zwischenzeitliche Umstellung auf das geteilte `day_window`-Modul (#1317/#1319 Scheibe A)
bereits behoben ist, und sichert das per Regressionstest ab.

**Nachtrag 2026-07-20 (PO-Entscheidung, s. Changelog):** die Spec vereinheitlicht zusätzlich
den SMS-Kürzel-Katalog für amtliche Warnungen über **beide** SMS-Pfade (Trip-Briefing-
Token-Zeile UND die eigenständige amtliche-Warnung-SMS aus Issue #1216) — das war ursprünglich
als „bewusst geduldete Divergenz" eingeordnet, ist aber tatsächlich der Kern dessen, was
verhindert werden soll: derselbe Nutzer darf für dieselbe Gefahr nicht zwei verschiedene Codes
in zwei verschiedenen Nachrichten bekommen.

## Source

- **File:** `src/output/renderers/sms_trip.py` — `_segments_to_normalized_forecast()`, `SMSTripFormatter.format_sms()`
- **File:** `src/output/tokens/builder.py` — `build_token_line()`, `_vigilance()`
- **File:** `src/output/tokens/dto.py` — `NormalizedForecast`, `Token`, `TokenCategory`
- **File:** `src/output/renderers/narrow.py` — `render_telegram_bubbles()`
- **File:** `src/output/renderers/alert/official_alerts.py` — `render_official_alert_telegram()`, `render_official_alert_sms()`, `_HAZARD_DISPLAY`
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` — `officialAlertsToggle`-Snippet, `SMS_THRESHOLD_METRIC_IDS`
- **File:** `src/output/renderers/compact_summary.py` — `_collect_hourly_data()` (Verifikation #1220)
- **Identifier:** `class SMSTripFormatter`, `def build_token_line`, `def render_telegram_bubbles`, `def render_official_alert_sms`

**Schicht:** Python-Core/Domain-Backend (`src/output/...`), Frontend-UI (`frontend/src/lib/components/shared/WeatherMetricsTab.svelte`). Kein Go-API-Anteil — die SMS-/Telegram-Rendering-Pfade laufen vollständig im Python-Core (`api.main:app` → Scheduler → Renderer).

## Estimated Scope

Der Gesamtumfang liegt über dem 250-LoC-Standardlimit. Empfehlung: **Zwei-Scheiben-Teilung**,
damit jede Scheibe im Rahmen bleibt und die sicherheitsrelevante SMS zuerst ausgeliefert wird.

| Scheibe | Inhalt | LoC (Code+Tests) | Effort |
|---|---|---|---|
| **A — sicherheitskritischer Kern** | `hazard_symbols.py`-Katalog; Vereinheitlichung `_HAZARD_DISPLAY`/`render_official_alert_sms` auf den neuen Katalog; Warn-Block in der Trip-Briefing-SMS (`dto.py`/`builder.py`/`render.py`/`sms_trip.py`); `sms_format.md`, `issue_1216_official_alert_template.md`, `fix_1249_sms_telegram_scope.md` aktualisiert; AC-1 bis AC-7, AC-11 bis AC-15 | ~160–200 | high |
| **B — Telegram + Konfigurationsoberfläche** | Warn-Bubble in `narrow.py` über `render_official_alert_telegram`; Kürzel-Anzeige + Legende in `WeatherMetricsTab.svelte`/`ThresholdMetricRow`; Katalog-Auslieferung ans Frontend; AC-8 bis AC-10 | ~80–110 | medium |
| **Gesamt** | | ~240–310 | — |

- **Files:** ~10–11 Code-Dateien + `docs/reference/sms_format.md` + 2 Alt-Specs + 3–4 Testdateien
- **Effort:** high (Gesamt), aber je Scheibe einzeln handhabbar

**Hinweis LoC-Limit:** Scheibe A liegt am oberen Rand, Scheibe B im Rahmen des
Standard-250-LoC-Limits. Falls eine Scheibe dennoch überschritten wird: vor Implementierung
`workflow.py set-field loc_limit_override <N>` — **nur nach PO-Freigabe**, nicht eigenmächtig
setzen (CLAUDE.md: „Kein LoC-Override ohne Permission").

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `official_alerts`-Dienst (`SegmentWeatherData.official_alerts`) | Daten | Amtliche Quelle je Segment, bereits geladen (`trip_report_scheduler.py:764-775`) — **andere Quelle** als die Vorhersage-Token, keine neue Datenbeschaffung nötig |
| `output.renderers.alert.official_alerts` (geteiltes Modul, ADR-0011) | Modul | `_HAZARD_DISPLAY`-Muster, `render_official_alert_telegram()`, `render_official_alert_sms()`, `_sort_notices()`, `dedupe_official_alerts()` — Telegram-Pfad UND Standalone-Warn-SMS hängen sich hier ein, kein neuer Renderer |
| `docs/reference/sms_format.md` v2.7 | SSOT | Wire-Format der Token-Zeile; diese Spec erweitert §2/§3 auf v2.8/v3.0, siehe unten |
| `docs/specs/modules/issue_1216_official_alert_template.md` | Alt-Spec | hazard→(Anzeige, SMS-Kürzel)-Tabelle; SMS-Kürzel-Spalte wechselt auf `hazard_symbols.py` als Quelle (Liefergegenstand dieser Spec) |
| `docs/specs/modules/fix_1249_sms_telegram_scope.md` | Alt-Spec | dessen AC-5 (Kürzel-Non-Regression) wird durch diese Spec überholt — als überholt markiert, nicht gelöscht (Liefergegenstand dieser Spec) |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | ADR | Konsistenz-Invariante: amtliche Warnung darf der Vorhersage nicht widersprechen, muss als eigene Kategorie erkennbar sein — hier über den `!`-Marker gelöst |
| `day_window.build_day_window_points()` | Modul | Bereits für #1220 verifiziert (Scheibe A der #1319-Zerlegung) — Ankunftsstunde inklusiv, kein Änderungsbedarf |

**Downstream:** `trip_report.py` (Rendering-Zusammenbau), Versand-Kanäle SMS/Telegram, `notification_service.py` (Standalone-Warn-Alarm).

## Implementation Details

### 1. Fachliches Modell (PO-Freigabe 2026-07-20, verbindlich, nicht neu erfinden)

**Ein Phänomen — ein Kürzel.** Vorhersage und amtliche Warnung nutzen dasselbe internationale
Kürzel; unterschieden werden sie durch einen eigenen Warn-Block, eingeleitet mit `!`
(1 Zeichen, GSM-7-sicher, kein Emoji). Das generalisiert das bestehende Prinzip aus
`sms_format.md` §3.4 (zwei `TH:`-Tokens, per **Position** unterschieden) auf **Marker-basierte**
Unterscheidung, weil jetzt mehr als zwei Tokens dasselbe Kürzel teilen können.

| hazard | Kürzel | Herkunft |
|---|---|---|
| `thunderstorm` | `TH` | identisch zum Forecast-Token |
| `rain` | `HR` | identisch zum (strukturell toten) Vigilance-Token §3.3 |
| `wind_gust` | `W` | identisch zum Forecast-Token |
| `snow` | `SN` | identisch zum Forecast-Token |
| `black_ice` | `IC` | neu (ICe) |
| `extreme_heat` | `HT` | neu (HeaT) |
| `extreme_cold` | `CD` | neu (ColD) |
| `wildfire_risk` | `FR` | neu (FiRe) |
| `access_ban` | `CL` | neu (CLosed) — Sonderfall, siehe unten |

**Stufe:** die vorhandene `L/M/H`-Skala (`tokens/metrics.py:LEVELS`), abgebildet
amtlich-gelb(2)→`L`, amtlich-orange(3)→`M`, amtlich-rot(4)→`H`. Keine neue Stufen-Sprache.

**Filter (sicherheitsrelevant, PO-Entscheidung):** NUR Stufe orange (3) und rot (4) erscheinen
in SMS und Telegram. Gelb (2) und grün (1) werden vor dem Rendern verworfen — `L` bleibt im
Mapping strukturell vorhanden (Symmetrie zur Skala), ist aber durch den Filter praktisch nie
sichtbar (analoge Situation wie die bestehende Fußnote zu `L` bei `TH`/`TH+` in §3.2).

**Sonderfall `access_ban` (`CL`):** eine Zugangssperre ist ein binärer Zustand ohne
Schweregrad-Abstufung (analog zu den bestehenden `Z:`/`M:`-Fire-Tokens, die ebenfalls keine
Stufe tragen) — sie erscheint als bloßes `CL` ohne Doppelpunkt/Stufe, nicht als `CL:H`.

**Datenquelle:** ausschließlich der moderne `official_alerts`-Dienst (alle Provider, 9
hazards), der pro Segment bereits geladen ist. Der alte, nie fertig verdrahtete
`get_warning_full()`-Vigilance-Pfad (`_vigilance()` in `builder.py`, nur bei
`fc.provider == "meteofrance"`) wird **nicht** wiederbelebt und bleibt unverändert — er ist im
SMS-Trip-Pfad heute strukturell unerreichbar, da `_segments_to_normalized_forecast()` nie
`provider="meteofrance"` setzt. Die Symbol-Wiederverwendung `HR`/`TH` zwischen dem (toten)
Vigilance-Pfad und dem neuen Warn-Block ist beabsichtigt (siehe Known Limitations).

### 1b. Katalog-Vereinheitlichung über BEIDE SMS-Pfade (PO-Entscheidung 2026-07-20, Pflicht-Scope)

**Diese Vereinheitlichung ist Liefergegenstand, keine Known Limitation.** `src/output/tokens/
hazard_symbols.py` (siehe Abschnitt 3) ist der **einzige** SMS-Kürzel-Katalog für amtliche
Warnungen im gesamten Code — für beide existierenden SMS-Nachrichtentypen:

1. Die **Trip-Briefing-SMS** (`sms_trip.py`, neu in dieser Spec, Abschnitt 3).
2. Die **eigenständige amtliche-Warnung-SMS** (`official_alerts.py::render_official_alert_sms`,
   Issue #1216/#1249, bereits produktiv) — ihre SMS-Kürzel-Komponente bezieht sich künftig
   ebenfalls auf `hazard_symbols.py`, statt einer eigenen, deutsch abgeleiteten Liste in
   `_HAZARD_DISPLAY`.

`_HAZARD_DISPLAY` (`official_alerts.py`) behält seine **Anzeige-Komponente** (deutsche
Klartext-Labels „Gewitter", „Sturm", „Hitze" …) unverändert — nur die SMS-Kürzel-Komponente
(`[1]` des Tupels) liest künftig aus `hazard_symbols.py`. Die alten, deutsch abgeleiteten
Kürzel verschwinden **ersatzlos**:

| hazard | alt (`_HAZARD_DISPLAY`, vor #1318) | neu (`hazard_symbols.py`, ab #1318) |
|---|---|---|
| extreme_heat | `HZ` | `HT` |
| thunderstorm | `TH` | `TH` (unverändert) |
| extreme_cold | `KL` | `CD` |
| wind_gust | `ST` | `W` |
| rain | `RR` | `HR` |
| snow | `SN` | `SN` (unverändert) |
| black_ice | `GL` | `IC` |
| access_ban | `ZG` | `CL` |
| wildfire_risk | `WB` | `FR` |

**Begründung (PO):** derselbe Nutzer darf für dieselbe Gefahr nicht zwei verschiedene Codes in
zwei verschiedenen Nachrichten bekommen; die alten Kürzel sind deutsch abgeleitet und verletzen
die Vorgabe „international verständlich"; die Kürzel-Legende in der Konfigurationsoberfläche
(Abschnitt 5) wäre sonst nur für die Hälfte der versendeten Nachrichten korrekt.

**Nicht Teil dieser Vereinheitlichung:** die restliche Formatlogik von
`render_official_alert_sms` (Kopfzeile `AMT {STUFE}N/3:`, Ortszusatz, Budget-Rückfallstufen,
Bündelung) — diese bleibt exakt wie in #1216/#1249 spezifiziert. Nur die Kürzel-Herkunft
wechselt.

### 2. Beispiele (verbindlich, aus der PO-Freigabe)

```
Nur Vorhersage:   GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16
Mit Warnung:      GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16 !TH:H@14 W:M
Brand + Sperrung: GR20 E5: N9 D28 R- W12@11 TH:- !FR:H CL
```

Ableitungsregel für `@h` (aus den Beispielen abgeleitet, siehe Known Limitations): die Stunde
erscheint, wenn `OfficialAlert.valid_from` einen **nicht-ganztägigen** Beginn liefert (Vorbild:
die bestehende Ganztags-Erkennung in `official_alerts.py::_format_validity`/`_tag_time`), sonst
entfällt `@h` ersatzlos. `access_ban` trägt nie eine Stunde (Sonderfall wie oben).

Bei **mehreren gleichzeitig aktiven Warnungen** erscheint `!` genau **einmal**, vor dem ersten
Token des Blocks; die übrigen Warn-Token folgen mit normalem Leerzeichen (kein zweites `!`).
Sortierung: Stufe absteigend (rot vor orange), bei Gleichstand feste Katalog-Reihenfolge (siehe
Tabelle oben) — deterministisch, keine Abhängigkeit von `valid_from`.

### 3. Backend — SMS (Issue #1318, Scheibe A)

- **Kürzel-Katalog:** EIN neues, kleines Modul `src/output/tokens/hazard_symbols.py` definiert
  `HAZARD_SMS_SYMBOLS: dict[str, str]` (die 9 Einträge aus Abschnitt 1) und die
  Filter-Konstante (Stufe ≥ 3). Das ist der **einzige** Ort, an dem diese 9 Kürzel gepflegt
  werden. Konsumenten: `sms_trip.py`/`builder.py` (Trip-Briefing-SMS), `narrow.py`
  (Telegram, Scheibe B), `official_alerts.py::_HAZARD_DISPLAY`/`render_official_alert_sms`
  (Standalone-Warn-SMS, Abschnitt 1b), und die Frontend-Katalog-Auslieferung (Scheibe B,
  Abschnitt 5).
- `NormalizedForecast` (`tokens/dto.py`) bekommt ein neues Feld für die gefilterten,
  kürzel-gemappten amtlichen Warnungen des Tages (z. B. eine Tupel-Sequenz aus
  Hazard-Kürzel/Stufenbuchstabe/optionaler Stunde). Additiv, kein Breaking Change an
  bestehenden Feldern.
- `_segments_to_normalized_forecast()` (`sms_trip.py`) liest `seg.official_alerts` über alle
  Segmente, dedupliziert über die geteilte `dedupe_official_alerts()` (kein eigener
  Dedup-Code, Lehre #1217/#1218), filtert auf Stufe ≥ orange und befüllt das neue Feld.
- `build_token_line()`/eine neue `_official_alert_warn_block()`-Funktion analog zu
  `_vigilance()` in `builder.py` erzeugt die Warn-Token. Empfehlung: eigene
  `TokenCategory`-Ausprägung (z. B. `"official_alert"`) statt Wiederverwendung von
  `"vigilance"` — semantisch sauberer (unterschiedliche Datenquelle), minimal-invasiv
  (`render.py`s Truncation-Loop muss die neue Kategorie im „Last-Resort"-Zweig zusätzlich
  berücksichtigen, `DROP_ORDER` bleibt unverändert, da die neue Kategorie dort nicht gelistet
  ist und daher erst im letzten Truncation-Schritt fällt).
- **Priorität** (`PRIORITY`-Dict, §6 Truncation): der Warn-Block bekommt einen Wert **höher**
  als der bisherige Maximalwert (aktuell 10, z. B. 11) — „amtliche Warnung hat Vorrang vor
  schwächeren Vorhersage-Tokens" heißt: sie wird beim Kürzen als letztes entfernt, nach `PR`,
  `D`, `N` und selbst nach `W`/`G`/`TH:`.

### 4. Backend — Telegram (Issue #1318, Scheibe B)

- `render_telegram_bubbles()` (`narrow.py`) hängt in der Kurzübersicht-Bubble (oder einer
  neuen eigenen Bubble, Entscheidung beim Implementieren anhand Bubble-Längen-Budget) den
  vorhandenen `render_official_alert_telegram()` (`official_alerts.py`) ein — **kein neuer
  Renderer**, keine 160-Zeichen-Beschränkung (Telegram ist ausgeschrieben).
- Die Filterung auf Stufe ≥ orange erfolgt **vor** dem Aufruf, über dasselbe
  `hazard_symbols`-Modul (Konsistenz mit SMS — beide Kanäle zeigen dieselbe Teilmenge der
  amtlichen Warnungen, nur unterschiedlich lang ausformuliert).
- `render_telegram_bubbles()` bekommt dafür Zugriff auf das, was `build_official_alert_notices()`
  benötigt (Trip-Segmentkontext für `scope_label`); falls das aktuell fehlende `trip`/
  Segment-ID-Kontext einen neuen optionalen Parameter erfordert, ist das additiv und ändert
  bestehende Aufrufer nicht (Default `None` → keine Warn-Bubble, heutiges Verhalten
  bit-identisch).

### 5. Frontend — Konfigurationsoberfläche (Issue #1318, Scheibe B)

`WeatherMetricsTab.svelte` (geteilter Baustein Trip **und** Ortsvergleich, `context="route"|
"vergleich"` — CLAUDE.md-Invariante beachten):

- (a) Je Metrik in `ThresholdMetricRow` (die 7 SMS-schwellenwertfähigen Metriken) wird das
  zugehörige SMS-Kürzel (`R`, `PR`, `W`, `G`, `TH`, `SN`, `SFL`) neben dem Label angezeigt.
- (b) Beim Schalter „Amtliche Warnungen im Bericht" (`officialAlertsToggle`-Snippet, bereits
  geteilt zwischen Trip und Vergleich) erscheint eine Legende: `!`-Block-Erklärung, die 9
  Kürzel mit Klartext-Bezeichnung, L/M/H = gelb/orange/rot.
- Beide Kürzel-Quellen kommen aus dem Backend (kein zweites, hartkodiertes TS-Array) — Weg:
  Erweiterung einer bestehenden Katalog-Auslieferung (z. B. Metrik-Katalog-Antwort um
  `sms_symbol`-Felder je Metrik plus einen neuen, schreibgeschützten Abschnitt für die 9
  Hazard-Kürzel) ODER ein kleiner neuer read-only Endpoint, der `hazard_symbols.py` 1:1
  serialisiert. Exakte Wahl ist Implementierungs-Entscheidung; die Prüfung erfolgt AC-basiert
  (Abgleich Backend-Katalog ↔ gerenderter Legenden-Text), nicht über eine vorgeschriebene
  Route.

### 6. Dokumentation (SSOT-Pflicht, Liefergegenstand)

`docs/reference/sms_format.md` MUSS aktualisiert werden:
- §2 Token-Reihenfolge: neuer optionaler Warn-Block-Abschnitt nach dem bisherigen
  `HR:TH:`-Vigilance-Block, vor Fire/Wintersport/DBG.
- Neuer Unterabschnitt §3.4c „Amtliche Warn-Token (`!`-Block)" mit der 9-Kürzel-Tabelle,
  Filterregel, `@h`-Regel, `access_ban`-Sonderfall, Mehrfachwarnung-Beispiel.
- §3.4-Überschrift/-Text erweitern: Disambiguierung generalisiert von „zwei `TH:`-Tokens per
  Position" auf „geteilte Kürzel, Vorhersage vs. amtlich per `!`-Marker unterschieden".
- §9 Datenquellen-Mapping: „⚠️ Provider TODO" bei `HR`/`TH` (Vigilance-Zeilen) wird NICHT
  fälschlich auf „✅ vorhanden" gesetzt (der alte Vigilance-Pfad bleibt tot) — stattdessen wird
  eine neue Zeile für den Warn-Block ergänzt, Status „✅ vorhanden (via `official_alerts`,
  Issue #1318)", mit Verweis, dass sie eine andere Quelle als die alten Vigilance-Zeilen ist.
- Versionstabelle §12: neuer Eintrag (v2.8 oder v3.0, je nachdem was zum Zeitpunkt der
  Implementierung der aktuelle Stand ist — `sms_format.md` steht bereits bei v2.7).

**Zusätzlich zwei Alt-Specs MÜSSEN mitgezogen werden (Liefergegenstand, nicht Nacharbeit):**
- `docs/specs/modules/issue_1216_official_alert_template.md` — die hazard→(Anzeige,
  SMS-Kürzel)-Tabelle auf die neuen internationalen Kürzel umstellen, mit Verweis auf diese
  Spec und `hazard_symbols.py` als neue SSOT für die Kürzel-Spalte. **Bereits erledigt** als
  Teil dieses Nachtrags (2026-07-20) — siehe dortiger Changelog.
- `docs/specs/modules/fix_1249_sms_telegram_scope.md` — dessen AC-5 („Kürzel bleiben identisch
  zum Stand vor #1249") ist durch diese PO-Entscheidung überholt, als überholt gekennzeichnet
  (nicht gelöscht), mit Verweis auf AC-13/AC-14 dieser Spec. **Bereits erledigt** als Teil
  dieses Nachtrags (2026-07-20) — siehe dortiger Changelog.

**Bestehende Tests, die mit dem alten Kürzel-Stand verknüpft sind, müssen angepasst werden**
(bewusste, PO-freigegebene Formatänderung, keine Regression): `tests/tdd/
test_official_alert_channel_scope.py` und `tests/tdd/test_official_alert_template_render.py`
enthalten literale Erwartungen an die alten Kürzel (`HZ`/`ST`/`RR`/`GL`/`ZG`/`WB`) und sind auf
die neuen (`HT`/`W`/`HR`/`IC`/`CL`/`FR`) umzustellen. Die Non-Regression-Zusicherung AC-4 dieser
Spec (bit-identische Trip-Briefing-Token-Zeile ohne aktive Warnung) ist davon **nicht**
betroffen — sie gilt unverändert weiter, da sie einen anderen Nachrichtentyp betrifft.

## Expected Behavior

- **Input:** `SegmentWeatherData`-Liste mit befüllten `official_alerts` (0..n pro Segment,
  Stufe 1–4, 9 mögliche `hazard`-Werte).
- **Output:** SMS-Token-Zeile mit optionalem `!`-Warn-Block (nur Stufe ≥ orange, dedupliziert,
  gekürzelt); Telegram-Bubble mit ausgeschriebenen amtlichen Warnungen derselben gefilterten
  Menge; eigenständige amtliche-Warnung-SMS und Konfigurationsoberfläche nutzen denselben
  Kürzel-Katalog wie die Trip-Briefing-SMS.
- **Side effects:** keine (reine Rendering-Funktionen, keine Schreiboperationen). Persistenz
  unberührt.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Segment mit einer amtlichen Gewitterwarnung der Stufe ROT (Beginn
  14:00, nicht ganztägig) / When die Trip-Briefing-SMS für diesen Trip erzeugt wird / Then
  enthält die SMS-Token-Zeile den Block `!TH:H@14` nach den regulären Vorhersage-Token.
  - Test: `SMSTripFormatter().format_sms(segments, ...)` mit einem Segment, dessen
    `official_alerts` genau eine `OfficialAlert(hazard="thunderstorm", level=4, ...)` mit
    14:00-Beginn enthält; Assertion auf die exakte Teilzeichenkette `!TH:H@14` in der
    zurückgegebenen SMS-Zeichenkette.

- **AC-2:** Given zwei amtliche Warnungen gleichzeitig (Gewitter Stufe ROT mit Uhrzeit, Sturm
  Stufe ORANGE ganztägig) / When die SMS erzeugt wird / Then erscheint genau ein `!`-Marker vor
  dem ersten (schwereren) Warn-Token, gefolgt vom zweiten Warn-Token ohne eigenes `!` und ohne
  Uhrzeit-Anhang: `!TH:H@14 W:M`.
  - Test: zwei `OfficialAlert`-Objekte (thunderstorm/4, wind_gust/3) an ein Segment gehängt,
    Assertion auf die exakte Teilzeichenkette `!TH:H@14 W:M` und dass die Zeichenkette
    insgesamt nur ein `!` enthält (`sms.count("!") == 1`).

- **AC-3:** Given eine amtliche Warnung der Stufe GELB (2) oder GRÜN (1) ohne gleichzeitige
  Warnung ≥ orange / When die SMS erzeugt wird / Then enthält die Token-Zeile keinen
  `!`-Warn-Block (die gelbe/grüne Warnung wird gefiltert, nicht angezeigt).
  - Test: Segment mit `OfficialAlert(hazard="rain", level=2, ...)`; Assertion `"!" not in sms`.

- **AC-4 (Non-Regression, Golden):** Given ein Trip-Segment ohne amtliche Warnungen (leere
  `official_alerts`-Liste, wie bei allen bestehenden Golden-Fixtures) / When die SMS erzeugt
  wird / Then ist die erzeugte Token-Zeile **bit-identisch** zum bisherigen Verhalten (kein
  `!`, keine Längenänderung, keine Positionsverschiebung anderer Token).
  - Test: `tests/golden/test_sms_golden.py` läuft unverändert grün (alle bestehenden
    Golden-Assertions bleiben exakt gleich); zusätzlich eine explizite Vorher/Nachher-
    String-Gleichheits-Assertion auf mindestens einem bestehenden Golden-Fixture mit
    `official_alerts=[]`.

- **AC-5 (alle 9 Hazards):** Given je eine amtliche Warnung der Stufe ORANGE für jeden der 9
  `hazard`-Werte (`thunderstorm`, `rain`, `wind_gust`, `snow`, `black_ice`, `extreme_heat`,
  `extreme_cold`, `wildfire_risk`, `access_ban`), einzeln getestet / When die SMS erzeugt wird
  / Then erscheint jeweils das in Abschnitt 1 der Spec festgelegte Kürzel (`TH`, `HR`, `W`,
  `SN`, `IC`, `HT`, `CD`, `FR`, `CL`) im Warn-Block, alle Zeichen ASCII/GSM-7-konform.
  - Test: parametrisierter Test über die 9 Hazards, je ein Assertion-Paar (Kürzel enthalten,
    kein Nicht-ASCII-Zeichen im Ergebnis via `sms.isascii()` bzw. `fold_ascii`-Idempotenz).

- **AC-6 (access_ban-Sonderfall):** Given eine amtliche Zugangssperre (`access_ban`, Stufe
  ROT) ohne gleichzeitige andere Warnung / When die SMS erzeugt wird / Then erscheint `CL` als
  bloßes Kürzel **ohne** Doppelpunkt und **ohne** Stufenbuchstaben (nicht `CL:H`).
  - Test: Segment mit `OfficialAlert(hazard="access_ban", level=4, ...)`; Assertion `"!CL"` in
    SMS und `"CL:"` NICHT in SMS.

- **AC-7 (Truncation-Vorrang):** Given eine Token-Zeile, die mit aktivem Warn-Block ohne
  Kürzung > 160 Zeichen wäre (viele aktive Vorhersage-Metriken + ein Warn-Block) / When die SMS
  gerendert wird / Then bleibt der Warn-Block im Ergebnis erhalten, während `PR` (und bei Bedarf
  `D`/`N`) zuerst aus der Zeile entfernt werden, bis das 160-Zeichen-Budget eingehalten ist.
  - Test: synthetisches Segment mit vielen aktiven Schwellenwert-Metriken (R, PR, W, G,
    thunder) plus einer amtlichen Warnung, `max_length=160`; Assertion, dass `!`-Block in der
    finalen Zeichenkette vorkommt und `len(sms) <= 160`, während mindestens `PR` fehlt.

- **AC-8 (Telegram):** Given ein Segment mit einer amtlichen Warnung der Stufe ORANGE/ROT /
  When das Telegram-Trip-Briefing gerendert wird / Then enthält eine der erzeugten Bubbles die
  amtliche Warnung ausgeschrieben (über `render_official_alert_telegram`, keine
  160-Zeichen-Kürzung, keine gelbe/grüne Warnung dabei).
  - Test: `render_telegram_bubbles(segments=..., ...)` mit demselben Fixture wie AC-1;
    Assertion, dass mindestens eine `TelegramBubble.text` den Warnungstext (Hazard-Label aus
    `_display_label`) enthält, und dass ein Fixture mit ausschließlich einer gelben Warnung
    KEINE entsprechende Bubble erzeugt.

- **AC-9 (Konfigurationsoberfläche):** Given ein Trip-Editor mit dem Wetter-Metriken-Tab /
  When der Nutzer den Schalter „Amtliche Warnungen im Bericht" betrachtet / Then zeigt die
  Legende alle 9 Kürzel mit Klartext-Bezeichnung, den `!`-Marker-Hinweis und die
  L/M/H-Stufenzuordnung (gelb/orange/rot), und die angezeigten Kürzel stimmen mit dem
  Backend-Katalog (`hazard_symbols.py`) überein — keine hartkodierte, abweichende zweite
  Liste im Frontend.
  - Test: Staging-Playwright- oder Komponententest lädt den Wetter-Metriken-Tab, liest den
    Legenden-Text aus dem DOM aus und vergleicht ihn gegen eine im selben Testlauf über die
    Backend-API abgerufene Katalog-Antwort (kein separat im Test hartkodiertes Kürzel-Set).

- **AC-10 (SSOT-Dokumentation `sms_format.md`, doc-compliance-test):** Given die aktualisierte
  `docs/reference/sms_format.md` / When die Datei gelesen wird / Then enthält sie den neuen
  `!`-Block-Abschnitt mit allen 9 Kürzeln, die Filterregel (Stufe ≥ orange) und einen
  aufgelösten (nicht mehr „⚠️ Provider TODO") Eintrag für die neue Warn-Block-Datenquelle in
  §9.
  - Test: `# doc-compliance-test` — Datei-Text-Assertion auf das Vorhandensein der 9
    Kürzel-Strings, des `!`-Markers und der aufgelösten Provider-Zeile (ausdrücklich als
    Doku-Konformitätstest markiert, kein Verhaltensnachweis).

- **AC-11 (#1220 Regression, Ankunftsstunde):** Given eine Etappe, deren Ankunft exakt in eine
  Regenstunde fällt (Regen ausschließlich in der Ankunftsstunde, keine Stunde davor/danach über
  dem Schwellenwert) / When die Natursprache-Kurzzusammenfassung (`format_stage_summary`)
  erzeugt wird / Then benennt der Text den Regen (z. B. „leichter Regen…"), NICHT „trocken".
  - Test: neuer Regressionstest mit Segmenten, deren letztes Segment exakt zur
    Ankunftsstunde endet und dort einen `precip_1h_mm`-Wert über der Erkennungsschwelle trägt;
    Assertion, dass der zurückgegebene Text NICHT die Zeichenkette „trocken" enthält. Rot vor
    Verifikation wäre der Bug-Beweis — die Analyse erwartet GRÜN (Fix bereits über
    `day_window.py` vorhanden); falls der Test tatsächlich rot ist, ist ein Mini-Fix analog
    #1146 in `compact_summary.py`/`day_window.py` nachzuziehen (dann ist die Spec um diesen
    Fix zu ergänzen, bevor sie als erfüllt gilt).

- **AC-12 (Mehrbenutzer-Isolation):** Given zwei Nutzer mit je einem eigenen Trip, bei dem nur
  der Trip von Nutzer A eine amtliche Warnung ≥ orange trägt / When für beide Nutzer die
  Trip-Briefing-SMS erzeugt wird / Then enthält nur die SMS von Nutzer A einen `!`-Block, die
  SMS von Nutzer B bleibt unverändert ohne Warn-Block — keine Vermischung der
  `official_alerts`-Daten zwischen den beiden Nutzern.
  - Test: zwei unabhängige Segment-Fixtures (unterschiedliche `user_id`-Zuordnung über
    getrennte Trip-Objekte) werden nacheinander durch `format_sms()` geschickt; Assertion, dass
    nur die SMS von Nutzer A den `!`-Block enthält.

- **AC-13 (Standalone-Warn-SMS nutzt die neuen Kürzel):** Given amtliche Warnungen der Typen
  Sturm (`wind_gust`), Hitze (`extreme_heat`), Starkregen (`rain`), Glatteis (`black_ice`),
  Zugangssperre (`access_ban`) und Waldbrand (`wildfire_risk`) / When die eigenständige
  amtliche-Warnung-SMS (`render_official_alert_sms`) für jeweils eine dieser Warnungen erzeugt
  wird / Then enthält der Text die neuen internationalen Kürzel (`W`, `HT`, `HR`, `IC`, `CL`,
  `FR`), und die alten deutsch abgeleiteten Kürzel (`ST`, `HZ`, `RR`, `GL`, `ZG`, `WB`)
  erscheinen **nirgends** im erzeugten Text.
  - Test: parametrisierter Test über die 6 geänderten Hazards, je eine Notice an
    `render_official_alert_sms` übergeben; Assertion auf Vorhandensein des neuen Kürzels UND
    Abwesenheit aller 6 alten Kürzel als eigenständige Zeichenketten (Wortgrenzen-sicher, um
    Teilstring-Zufallstreffer auszuschließen, z. B. `HZ` in einem Ortsnamen).

- **AC-14 (Anti-Divergenz, beide SMS-Pfade liefern dasselbe Kürzel):** Given denselben
  `hazard`-Wert, einmal in einem Segment für die Trip-Briefing-SMS und einmal in einer Notice
  für die Standalone-Warn-SMS, für jeden der 9 Hazards einzeln / When beide SMS-Texte erzeugt
  werden / Then enthalten beide exakt dasselbe Kürzel für diesen Hazard (aus
  `hazard_symbols.py` gelesen, nicht aus zwei unabhängig gepflegten Werten).
  - Test: parametrisierter Test über alle 9 Hazards; für jeden Hazard wird sowohl
    `SMSTripFormatter().format_sms(...)` als auch `render_official_alert_sms(...)` mit
    demselben Hazard aufgerufen, und beide Ergebnis-Strings werden auf dasselbe Kürzel
    geprüft. Das ist die eigentliche Absicherung gegen erneutes Auseinanderlaufen der beiden
    Kataloge.

- **AC-15 (Alt-Specs mitgezogen, doc-compliance-test):** Given die aktualisierten Dateien
  `docs/specs/modules/issue_1216_official_alert_template.md` und `docs/specs/modules/
  fix_1249_sms_telegram_scope.md` / When die Dateien gelesen werden / Then enthält
  `issue_1216_official_alert_template.md` die neuen internationalen Kürzel in der
  hazard→SMS-Tabelle mit einem Verweis auf `hazard_symbols.py` als SSOT, und
  `fix_1249_sms_telegram_scope.md` markiert AC-5 sichtbar als überholt mit einem Verweis auf
  diese Spec.
  - Test: `# doc-compliance-test` — Datei-Text-Assertion auf die neuen Kürzel-Strings in der
    einen Datei und auf einen „überholt"-Hinweis samt Verweis auf `sms_official_alert_tokens.md`
    in der anderen.

- **AC-16 (unbekannte Gefahrenart geht nie verloren — Adversary F001, CRITICAL):** Given eine
  amtliche Warnung der Stufe ORANGE oder ROT, deren `hazard`-Wert **nicht** im 9er-Katalog steht
  (z. B. ein neu hinzukommender Provider-Typ) / When die Trip-Briefing-SMS erzeugt wird / Then
  erscheint die Warnung dennoch im `!`-Block mit einem aus dem `hazard`-String abgeleiteten
  Kürzel — sie wird **nicht** stillschweigend verworfen. Der Stufenfilter (≥ orange) bleibt
  davon unberührt wirksam.
  - Test: `OfficialAlert(hazard="volcanic_ash", level=4, …)` erzeugt einen `!`-Block; dieselbe
    Warnung mit `level=2` erzeugt keinen. Zusätzlich: beide SMS-Pfade liefern für den
    unbekannten `hazard` dasselbe Kürzel (Erweiterung von AC-14 über den Katalog hinaus).
  - Hintergrund: `_official_alert_entries()` verwarf unbekannte hazards zunächst per `continue`,
    während der Standalone-Pfad bereits einen Fallback hatte — die schärfste Form der Divergenz
    („sichtbar vs. unsichtbar") und genau der Schaden, den der Purpose-Absatz verhindern will.
    Präzedenzfall: fehlendes `wildfire_risk`-Mapping → Produktionsbug #1239 F004.

- **AC-17 (Rückfall-Kürzel kollidiert nie mit dem Katalog — Adversary F002, HIGH):** Given eine
  amtliche Warnung mit unbekanntem `hazard`, dessen Anfangsbuchstaben auf ein bereits vergebenes
  Katalog-Kürzel führen würden (z. B. `thunder_squall` → `TH`, `snow_drift` → `SN`) / When das
  Kürzel gebildet wird / Then unterscheidet sich das Ergebnis von **allen** 9 Katalog-Kürzeln
  (deterministische Verlängerung auf 3 Buchstaben, z. B. `THU`/`SNO`), sodass zwei verschiedene
  Gefahren im SMS-Text nie identisch aussehen.
  - Test: parametrisiert über unbekannte hazards, die auf Katalog-Kürzel führen würden;
    Assertion, dass kein Ergebnis in `HAZARD_SMS_SYMBOLS.values()` liegt, dass gleichzeitige
    `thunderstorm`- und `thunder_squall`-Warnungen unterscheidbare Token ergeben, dass das
    Ergebnis deterministisch und ASCII-rein ist.
  - Begründung: eine Warnung, die sich als eine **andere** Gefahr ausgibt, ist Fehlinformation
    in einer Sicherheitsmeldung — schlimmer als eine fehlende Angabe. Dass alle heutigen
    Provider-Adapter unbekannte Typen bereits beim Einlesen wegfiltern, macht das Fallback
    nicht überflüssig: es ist das Sicherheitsnetz für genau den Tag, an dem ein neuer Typ
    dazukommt, und muss dann korrekt sein.

## Known Limitations

- **`L`-Stufe strukturell unerreichbar im Warn-Block:** Analog zur bestehenden Fußnote zu `TH`/
  `TH+` — das Mapping kennt `L` (gelb), der Stufe-≥-orange-Filter verhindert aber, dass sie
  jemals gerendert wird.
- **Legacy-Vigilance-Pfad bleibt tot:** `_vigilance()`/`get_warning_full()` (§3.3) werden nicht
  angefasst, bleiben im SMS-Trip-Pfad strukturell unerreichbar (Provider nie `"meteofrance"`).
  Die Kürzel-Wiederverwendung `HR`/`TH` zwischen totem Vigilance-Pfad und neuem Warn-Block ist
  beabsichtigt, keine Kollision in der Praxis (unterschiedliche Provider-Bedingung).
- **`@h`-Anzeigeregel ist abgeleitet, nicht wörtlich PO-spezifiziert:** Die Regel „Stunde nur
  bei nicht-ganztägigem Beginn" wurde aus den drei verbindlichen PO-Beispielen abgeleitet
  (Vorbild bestehendes `_format_validity`/`_tag_time`-Muster). Bei Freigabe explizit bestätigen
  oder korrigieren.
- **E-Mail-Kurzzusammenfassung bewusst ausgenommen:** PO-Entscheidung — die amtliche Warnung
  steht in derselben Mail bereits im großen Warn-Kasten; eine zweite Anzeige wäre eine
  Dopplung. `compact_summary.py` bekommt in diesem Workflow **keine** Warn-Block-Logik.
- **#1325 (Staging-E2E-Werkzeug) läuft in paralleler Sitzung**, nicht Teil dieser Spec.
- **Frontend-Katalog-Auslieferungsweg ist bewusst offen gelassen** (bestehender Endpoint
  erweitert vs. neuer schreibgeschützter Endpoint) — Implementierungsentscheidung, AC-9 prüft
  nur das Ergebnis (Konsistenz DOM ↔ Backend), nicht den Transportweg.
- **`#1220`:** falls der Regressionstest (AC-11) entgegen der Analyse-Erwartung ROT ist, deckt
  diese Spec den dann nötigen Mini-Fix noch nicht im Detail ab — Umfang wäre in `day_window.py`
  bzw. `compact_summary.py` nachzuziehen, analog zum Präzedenzfall #1146.
- **Restliche Formatlogik der Standalone-Warn-SMS unverändert:** die Kürzel-Vereinheitlichung
  (Abschnitt 1b) rührt ausschließlich an der Kürzel-Herkunft von `render_official_alert_sms`;
  Kopfzeile, Ortszusatz, Budget-Rückfallstufen und Bündelung aus #1216/#1249 bleiben unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Spec ist eine rückwärtskompatible, additive Weiterentwicklung des
  bestehenden Token-Zeilen-Modells (`sms_format.md` SSOT) — sie generalisiert das bereits per
  ADR-freiem Präzedenzfall etablierte Disambiguierungsprinzip aus §3.4 (Positions- statt
  Marker-basiert) und fügt sich in die bestehende geteilte Alert-Renderer-Architektur
  (ADR-0011) sowie die Gewitter-Konsistenz-Invariante (ADR-0025) ein, ohne ein neues
  Architekturmuster einzuführen. Die Katalog-Vereinheitlichung (Abschnitt 1b) ist eine reine
  Korrektheits-Konsolidierung auf eine bereits etablierte SSOT-Praxis (ADR-0011: ein
  gemeinsamer Renderer statt Kopie), keine neue Architektur. Sollte der PO eine eigenständige
  Dokumentation dieser Entscheidung wünschen (z. B. weil künftige Kanäle denselben
  `!`-Block wiederverwenden sollen), ist ein Folge-ADR sinnvoll — das liegt außerhalb des
  Spec-Scopes.

## Changelog

- 2026-07-20: Initial spec created
- 2026-07-20 (Nachtrag, PO-Entscheidung): Known-Limitation-Punkt „Divergenter Kürzel-Katalog"
  war eine Fehldeutung der PO-Entscheidung #2 aus der Analyse — diese legte nur den
  RENDERING-WEG der Briefing-SMS fest (Token-Zeile statt AMT-Format), nicht die Duldung zweier
  Kataloge. Abschnitt 1b neu eingefügt (Katalog-Vereinheitlichung als Pflicht-Scope statt
  Limitation); AC-13/AC-14/AC-15 ergänzt; Estimated Scope auf Zwei-Scheiben-Teilung (A:
  sicherheitskritischer Kern inkl. Vereinheitlichung, B: Telegram + Konfigurationsoberfläche)
  umgestellt; `docs/specs/modules/issue_1216_official_alert_template.md` und `docs/specs/
  modules/fix_1249_sms_telegram_scope.md` als Alt-Specs mitgezogen (dort je eigener
  Changelog-Eintrag).
