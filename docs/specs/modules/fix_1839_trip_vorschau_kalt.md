---
entity_id: fix_1839_trip_vorschau_kalt
type: module
created: 2026-11-07
updated: 2026-11-07
status: draft
version: "1.0"
tags: [bug, performance, preview, timeout, go-api, python-core, frontend, issue-1839, epic-2733]
---

# Trip-Vorschau bei kaltem Cache: kein 502 mehr (Restposten #1839, Epic #2733 Strang C)

## Approval

- [ ] Approved

## Purpose

Wer eine Vorschau als Erster nach einer Pause aufruft (kalter Wetter-Cache), bekommt heute
`502 upstream_unreachable`, obwohl der Python-Core korrekt weiterrechnet: der Go-Weiterleiter
gibt nach 30 s auf. Warm antwortet dieselbe Vorschau in unter 1 s. Dieser Restposten (die
Compare-Seite ist mit #1765 erledigt, Entblockung mit Scheibe A,
`fix_1765_1839_sa_vorschau_entblockung.md`) beseitigt den 502 an seinem **Wirkort**, der zu engen
Zeitgrenze, und verkuerzt die echte Rechenzeit dort, wo sie noch unnoetig seriell ist.

Die Analyse korrigiert die Ausgangslage aus dem Ticket: Die Wetterabrufe selbst laufen seit
#1539/#2439 bereits parallel (`_fetch_weather` per `fetch_ordered`, Trend-Etappen per
`_abrufe_fuer_etappen`), aber hinter einem Slot-Deckel `open_meteo` = 3. Mit rund 8 Abrufen von
10 bis 26 s ist kalt eine Groessenordnung von 45 bis 75 s zu erwarten (Schaetzung, nicht
gemessen); die alte Messung (121 s, 15.08.) ist veraltet. Parallelisierung allein bringt die
Vorschau daher voraussichtlich nicht unter 30 s. Beide Massnahmen sind noetig: **Zeitgrenze
anheben** (beseitigt den 502 sicher, unabhaengig von der Messung) und **den noch seriellen
Rest** (Nachtwetter vor Trend) nebenlaeufig machen.

**Wichtige Ist-Lage der Oberflaeche:** Die Briefing-Vorschau (E-Mail/Telegram im Reiter) ist mit
#1719 S3 und #1743 entfallen. Den Pfad `PreviewService._build_report` erreicht heute nur
`GET /api/preview/{trip_id}/sms` (Messweg der Staging-Specs, kein Reiter). Der einzige
nutzersichtbare Vorschau-Aufrufer, der durch `previewProxyTimeout` laeuft, ist die
**Alarm-Vorschau** (`AlertPreviewCard`, Trip und Ortsvergleich). Die Spec formuliert die
Nutzer-ACs deshalb auf die Alarm-Vorschau; der Python-Teil bleibt fuer den SMS-Messweg und
jeden kuenftigen Aufrufer von `_build_report` wirksam.

## Source

- **File:** `internal/handler/preview_proxy.go` (Go) · `src/services/preview_service.py` (Python) ·
  `frontend/src/lib/api.ts` · `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte`
- **Identifier:** `previewProxyTimeout` · `PreviewService._build_report` ·
  `ZEITLIMIT_ALARM_VORSCHAU_MS` · `AlertPreviewCard` (`loadPreview`)

> **Schicht-Hinweis:** Go-API (`internal/handler/`), Python-Core (`src/services/`), Frontend
> (`frontend/src/lib/`). Kein Code in einer falschen Schicht.

> **Querschnitts-Pruefpunkte:**
> - **Trip/Ortsvergleich-Teilung:** `AlertPreviewCard` ist bereits EIN Baustein fuer beide
>   Kontexte (`kind="route"|"vergleich"`, Abruf `alarmVorschau(kind, …)`); die Aenderung dort
>   erfolgt an dieser einen Stelle, kein Pendant, keine Neuanlage (Pendant-Sperre unberuehrt).
>   `previewProxyTimeout` und das Frontend-Zeitlimit gelten beide Kontexte gleichermassen.
>   Der Python-Teil betrifft nur den Trip-Pfad; das Compare-Pendant (`compare_preview_service`)
>   ist bereits parallel (`run_comparison_parallel`) und bleibt unveraendert.
> - **Mandantentrennung:** Es werden keine Nutzerdaten bewegt oder neu gelesen. `forwardPreview`
>   injiziert weiter die `user_id` aus dem Auth-Kontext, der Python-Zweig reicht dieselbe
>   `user_id` in beide Zweige durch (kein Fallback `"default"`). Test mit zwei Nutzern, siehe AC-5.
> - **Kanaele:** Briefing-/Alarm-**Inhalt** aendert sich nicht (gleicher Report, gleiche Reihenfolge
>   der Teile); alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) sind inhaltlich unberuehrt,
>   weil nur Wartezeit und Gleichzeitigkeit sich aendern.

## Estimated Scope

- **LoC:** ca. 120 (Go ~6, Python ~40, Frontend ~12, Tests der Rest)
- **Files:** Produktiv 5 (`preview_proxy.go`, `preview_service.py`, `api.ts`,
  `AlertPreviewCard.svelte`, `alarme.json` de + en), Tests 4
- **Effort:** medium (Threads im Vorschau-Pfad: Kontextvariablen, Fehlersemantik)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/proxy.go` (`stagesWeatherProxyTimeout` 120 s, `sendProxyTimeout` 300 s, `nginxProxyReadTimeout` 330 s) | Zeitgrenzen-Kette | Vorbild fuer Paket-`var` und obere Schranke (< nginx 330 s) |
| `internal/handler/proxy_timeout_chain_test.go` | Wächter | Kettenregel + Wirkort-Test ueber kurz gesetzte `var` werden fortgeschrieben |
| `internal/handler/briefing_preview.go` / `proxy.go` (`AlertPreviewProxyHandler`) | Aufrufer | beide rufen `forwardPreview` mit `previewProxyTimeout` (Alarm-Vorschau, explizit mitbetroffen) |
| `TripReportSchedulerService._fetch_weather`, `_build_stage_trend`, `fetch_night_weather`, `_build_thunder_forecast_from_trend_or_fetch` | Python | werden **nicht veraendert**, nur anders aufgerufen |
| `src/services/stage_weather.py` | Praezedenzfall | Thread-Parallelisierung mit Fehler-Wrapper je Zweig |
| `docs/reference/i18n_konventionen.md`, ADR-0104 | i18n | neue Nutzertexte nur ueber den Katalog (DE/EN) |

## Implementation Details

### Ae1 — Go: `previewProxyTimeout` 30 s auf 120 s als Paket-`var`

```go
// preview_proxy.go
var previewProxyTimeout = 120 * time.Second   // vorher const 30 s
```

Wie `stagesWeatherProxyTimeout` als `var`, damit ein Test den Wert kurz setzen und beobachten
kann, dass `forwardPreview` ihn **tatsaechlich** als `http.Client.Timeout` verwendet (Wirkort).
120 s = Wert des Wetter-Lesens, deutlich unter nginx 330 s (Puffer >= 30 s wie im Wächter).
Der Wert gilt fuer **alle** Aufrufer von `forwardPreview`: SMS-Messweg, Trip-Alarm-Vorschau
(`/api/trips/{id}/alert-preview`) und kind-neutrale Alarm-Vorschau
(`/api/briefings/{id}/alert-preview`). Kommentar an der Deklaration nennt die Kette. Veraltete
Kommentare ("30 s") in `preview_proxy.go`, `briefing_preview.go` und `proxy.go` werden
nachgezogen.

### Ae2 — Frontend: Zeitlimit der Alarm-Vorschau folgt der Kette

`ZEITLIMIT_ALARM_VORSCHAU_MS` (heute 40 s, Kommentar "Go-Proxy ca. 30 s") bricht die Anfrage
im Browser ab, **bevor** ein auf 120 s angehobener Go-Proxy antworten kann: der Nutzer sehe
sonst weiter "Vorschau konnte nicht geladen werden". Der Wert wird auf 130 s angehoben (gleiche
Staffelung wie `ZEITLIMIT_TEST_NACHRICHT_MS` = 130 s zu Go 120 s) und der Kommentar angepasst.
Die zugehoerigen Zeit-Tests (`apiZeitlimit.test.ts`, gestellte Uhr) werden fortgeschrieben.

### Ae3 — Python: Trend nebenlaeufig zu Hauptabruf und Nachtwetter

In `PreviewService._build_report` laufen heute nacheinander: `scheduler._fetch_weather(segments)`,
`fetch_night_weather(...)` (wartet auf `segment_weather[-1]`, ca. 25 s), danach
`_build_stage_trend(...)`. Der Trend ist von beidem unabhaengig. Neu:

```
trend_future = eigener Thread, gestartet mit contextvars.copy_context().run(...)
                -> scheduler._build_stage_trend(...)        (unveraendert aufgerufen)
segment_weather = scheduler._fetch_weather(...)             (Hauptthread, unveraendert)
night_weather   = fetch_night_weather(...)                  (Hauptthread, danach, unveraendert)
trend           = trend_future.result()                     (Zusammenfuehrung)
Thunder-Fallback laeuft DANACH (haengt von Trend + Nachtwetter ab)
```

Festlegungen:

- **Eigener Thread, nicht der gemeinsame Pool** (`parallel_fetch`): Dort liefe der innere Abruf
  inline seriell, wenn der Pool schon belegt ist; der Trend wuerde nicht schneller.
- **`contextvars.copy_context()`**, damit `call_log`-Quelle und weitere `ContextVar`-Werte im
  Zweig ankommen; `_tf_instance`-Lock (Scheibe A, Ae3) schuetzt die Zeitzonen-Initialisierung.
- `_fetch_weather` und `_build_stage_trend` bleiben **unangetastet** (6 bzw. mehrere Aufrufer im
  Versand/Alarm; Zuschnitt "außen" laut Vorarbeit V3, die `[triage:po]`-Entscheidung aus #1539
  wird nicht vorweggenommen).
- **Ergebnis und Reihenfolge unveraendert:** gleiche Rueckgabe `(report, segment_weather,
  stage_name, trip_tz)`, gleicher Inhalt wie sequenziell.
- **Fehlersemantik wie heute:** Wirft der Trend-Zweig, wird der Fehler beim Zusammenfuehren so
  behandelt wie bisher der serielle Aufruf (gleiche Ausnahme bzw. gleicher Fallback); wirft der
  Hauptabruf oder das Nachtwetter, wird der Trend-Thread nicht verwaist (wird abgewartet bzw.
  sein Fehler verworfen), und die Ausnahme des Hauptzweigs steigt wie heute auf. Ein Fehler in
  einem Zweig reisst den anderen nicht mit, ein Zweig verschluckt keinen Fehler still.
- `persist_backfill = False` und `user_id` gelten unveraendert fuer beide Zweige.

### Ae4 — Ladezustand "Vorschau wird berechnet…"

`AlertPreviewCard.svelte` ist die EINE Stelle (geteilt Trip/Vergleich, `kind`-Parameter): sie
zeigt heute im Lade-Fall nur "Lade…" auf dem Knopf. Neu: waehrend `loading` erscheint zusaetzlich
ein Hinweis "Vorschau wird berechnet…" (`role="status"`), damit der Nutzer bei einer Wartezeit
von bis zu zwei Minuten nicht an einen Absturz glaubt. Der Text kommt ausschliesslich aus dem
Katalog (`alarme.vorschau.berechnet` in `messages/de/alarme.json` und `messages/en/alarme.json`;
EN z. B. "Computing preview…"), kein hartkodierter String
(`keine_hartkodierten_nutzertexte.test.ts`). Es entsteht keine neue Komponente und keine
einseitige Trip- oder Compare-Variante. Sollte sich beim Umsetzen zeigen, dass der Ladezustand
nur durch eine zweite, getrennte Komponente erreichbar waere, entfaellt Ae4 aus diesem Ticket
und wird eigenes Ticket (kein Aufweichen der Teilung).

## Expected Behavior

- **Input:** Vorschau-Aufruf (SMS-Messweg oder Alarm-Vorschau, Trip oder Vergleich) bei kaltem
  Cache, Rechenzeit bis rund 120 s.
- **Output:** Normale Antwort mit dem Vorschau-Inhalt statt `502 upstream_unreachable`. Erst
  nach 120 s ohne Antwort des Python-Core bleibt es beim 502 (echter Ausfall). Warme
  Antwort weiterhin unter 1 s, Inhalt identisch.
- **Side effects:** Die Alarm-Vorschau hat dieselbe Obergrenze (120 s statt 30 s); ein
  haengender Python-Core bindet eine Verbindung laenger (akzeptiert, unter nginx 330 s).
  Keine Aenderung am Versand, an Alarmen oder am Wetter-Cache.

## Acceptance Criteria

- **AC-1:** Given der Python-Core braucht fuer eine Vorschau bei kaltem Cache laenger als 30 s
  (z. B. 100 s) / When ein Nutzer die Vorschau (Alarm-Vorschau oder SMS-Vorschau) aufruft /
  Then bekommt er sein Ergebnis statt `502 upstream_unreachable`, und erst nach Ablauf der
  Zeitgrenze von 120 s ohne Antwort erscheint der 502.
  - Test (Go, Wirkort, `proxy_timeout_chain_test.go`): `previewProxyTimeout` kurz setzen
    (100 ms); ein Test-Upstream antwortet nach 50 ms erfolgreich (Antwort kommt durch, kein
    502) und ein zweiter erst nach der Grenze (502 erst danach); die Handler `PreviewProxyHandler`,
    `AlertPreviewProxyHandler` und `BriefingAlertPreviewHandler` werden durchlaufen. Der
    Standardwert ist 120 s (Wert-Test wie `...SendProxyTimeoutIs300Seconds`).

- **AC-2:** Given die Zeitgrenzen-Kette Browser, Go-Weiterleiter, nginx / When die Grenzen
  fuer Vorschauen geprueft werden / Then liegt `previewProxyTimeout` (120 s) unter nginx
  (330 s) mit mindestens 30 s Puffer, und das Browser-Zeitlimit der Alarm-Vorschau liegt ueber
  dem Go-Wert, damit der Nutzer die Antwort noch bekommt.
  - Test (Go): `previewProxyTimeout` in `TestTimeoutChain_EveryProxyTimeoutBelowNginx` und im
    Puffer-Test aufgenommen. Test (Frontend, `apiZeitlimit.test.ts`, gestellte Uhr): die
    Alarm-Vorschau bricht nach 130 s ab, nicht schon nach 40 s.

- **AC-3:** Given eine Vorschau, bei der Nachtwetter und Etappen-Trend je mehrere Sekunden
  brauchen / When der Vorschau-Bericht berechnet wird / Then laufen Trend und
  Hauptabruf-plus-Nachtwetter gleichzeitig, die Gesamtdauer liegt nahe am laengeren der beiden
  Teile statt an deren Summe, und der fertige Bericht ist inhaltlich und in der Reihenfolge
  identisch zum bisherigen sequenziellen Ergebnis.
  - Test (Python, nach Verhalten benannt, z. B. `tests/test_preview_trend_laeuft_nebenlaeufig.py`):
    echte, kurze `time.sleep`-Funktionen als Ersatz der Abrufe (je ca. 0,3 s) ueber die
    Austauschstellen am Scheduler-Objekt (kein Mock der eigenen Annahme): gemessene Gesamtzeit
    deutlich unter der Summe, Zeitstempel zeigen Ueberlappung, Rueckgabe gleich der
    sequenziellen Referenz; Trend-Zweig sieht dieselben `ContextVar`-Werte.

- **AC-4:** Given in einer Vorschau scheitert ein Zweig (Trend ODER Hauptabruf/Nachtwetter) /
  When der Bericht berechnet wird / Then bleibt das Fehlerverhalten wie heute (gleiche
  Ausnahme bzw. gleicher Fallback), der andere Zweig laeuft nicht abgebrochen davon und bleibt
  nicht als verwaister Thread zurueck, und kein Fehler wird still verschluckt.
  - Test (Python, gleiche Datei): erster Lauf Trend wirft, zweiter Lauf Hauptabruf wirft; beide
    Male identische Ausnahme-Art wie in der sequenziellen Referenz, und nach dem Aufruf sind
    keine zusaetzlichen Threads aktiv.

- **AC-5:** Given zwei verschiedene Nutzer rufen gleichzeitig ihre Vorschau auf / When die
  Berichte nebenlaeufig berechnet werden / Then enthaelt jeder nur seine eigenen Etappen und
  Daten (`user_id` aus dem Auth-Kontext, nie `"default"`), auch in den neuen Zweigen.
  - Test (Python): zwei Nutzer mit unterscheidbarer Etappenzahl bzw. Etappennamen rufen
    `_build_report` parallel; jeder Bericht traegt nur die eigene Kennung (Mandantentest
    Pflicht). Go: `forwardPreview` verwirft eine mitgesendete Fremd-`user_id` weiterhin
    (bestehender Test bleibt gruen).

- **AC-6:** Given ein Nutzer startet die Alarm-Vorschau (Trip oder Ortsvergleich) / When die
  Berechnung laenger dauert / Then sieht er waehrend der Wartezeit den Hinweis "Vorschau wird
  berechnet…" (EN: gleichwertiger Katalogtext), und nach dem Ergebnis oder Fehler verschwindet
  der Hinweis wieder.
  - Test (Frontend, `node --test` bzw. E2E auf Staging): `AlertPreviewCard` fuer
    `kind="route"` und `kind="vergleich"` zeigt im Lade-Zustand das Statuselement mit dem
    Katalogtext in beiden Sprachen; der Hinweis ist nach Abschluss weg;
    `keine_hartkodierten_nutzertexte.test.ts` und der i18n-Paritaetstest (DE/EN-Schluessel)
    bleiben gruen.

- **AC-7:** Given der Aenderungsstand / When Versand (Briefing, Alarme) und Compare-Vorschau
  laufen / Then verhalten sie sich unveraendert, weil `_fetch_weather` und
  `_build_stage_trend` nicht angefasst werden und die Compare-Vorschau nicht beruehrt wird.
  - Test: bestehende Versand-/Alarm-/Compare-Tests bleiben unveraendert gruen (kein
    Verhaltensnachweis durch Dateiinhalt-Check).

## Scope

| Datei | Art | Beschreibung |
|-------|-----|--------------|
| `internal/handler/preview_proxy.go` | MODIFY | `previewProxyTimeout` 30 s auf 120 s, Paket-`var` |
| `internal/handler/proxy_timeout_chain_test.go` | MODIFY | Wirkort-Test und Kettenregel |
| `src/services/preview_service.py` | MODIFY | Trend nebenlaeufig zu Hauptabruf plus Nachtwetter |
| `frontend/src/lib/api.ts` | MODIFY | `ZEITLIMIT_ALARM_VORSCHAU_MS` 40 s auf 130 s |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | MODIFY | Ladehinweis "Vorschau wird berechnet…" |
| `alarme.json` (de + en) | MODIFY | Katalogschluessel `alarme.vorschau.berechnet` |
| neue Testdateien nach Verhalten benannt | CREATE | siehe Test Plan |

Geschaetzt: ca. 120 LoC, 9 Dateien. Nicht im Scope: siehe Nicht-Ziele.

## Definition of Done

- Eine kalte Vorschau, die laenger als 30 s rechnet, liefert bis 120 s ihr Ergebnis statt `502`.
- Die Zeitgrenzen-Kette bleibt geordnet: Go (120 s) unter nginx (330 s), Browser (130 s) ueber Go.
- Trend und Hauptabruf plus Nachtwetter laufen gleichzeitig, Ergebnis unveraendert.
- Die Alarm-Vorschau zeigt waehrend der Wartezeit den Hinweis in DE und EN.
- Alle sieben Acceptance Criteria durch Tests belegt; Kaltzeit auf Staging vorher/nachher gemessen.

## Test Plan

- Go: `internal/handler/proxy_timeout_chain_test.go` (AC-1, AC-2, AC-5), Wirkort ueber kurz gesetzte `var`.
- Python: neue Datei `tests/test_preview_trend_laeuft_nebenlaeufig.py` (AC-3, AC-4, AC-5), echte kurze Sleeps statt Mocks.
- Frontend: `apiZeitlimit.test.ts` ueber `node --test` (AC-2), `AlertPreviewCard`-Test und i18n-Paritaet (AC-6).
- Bestehende Versand-, Alarm- und Compare-Tests bleiben unveraendert gruen (AC-7).
- Staging: Kaltmessung vorher/nachher in `/e2e-verify`.

## Known Limitations

- **Keine Sekundenzusage.** Die Kaltzeit ist ungemessen (Schaetzung 45 bis 75 s). In
  `/e2e-verify` wird auf Staging vorher und nachher kalt gemessen (frisch gestarteter
  `gregor-python-staging` = leerer Cache; Staging-Auto-Deploy leert den Cache ebenfalls); die
  Messwerte kommen ins Ticket. Zugesagt wird nur: kein 502 bei kaltem Cache innerhalb 120 s.
- Der Slot-Deckel `open_meteo` = 3 bleibt; die Rechenzeit sinkt nur um den Anteil, den die
  Gleichzeitigkeit von Trend und Nachtwetter bringt.
- Die Briefing-Vorschau (E-Mail/Telegram) im Reiter existiert nicht mehr; die Python-Aenderung
  wirkt heute nur ueber den SMS-Messweg. Der Nutzer-Gewinn im Browser entsteht ueber die
  Alarm-Vorschau (Zeitgrenze, Ladezustand).
- Die Alarm-Vorschau laeuft ueber `compare_alert_preview_service` bzw. den Trip-Alarmpfad, nicht
  ueber `_build_report`; sie profitiert nur von Ae1, Ae2 und Ae4, nicht von Ae3.

## Nicht-Ziele

- Slot-Semaphore `open_meteo` = 3 anheben (gemeinsames Open-Meteo-Kontingent, Bezug #1539).
- Cache-Stampede bei gleichzeitigem Miss (bekannt, offen).
- Wurzel von #1539 (sequenzielle Orts-/Etappenverarbeitung, Scheduler-Ueberlappung).
- Vorwaermen beim Oeffnen der Seite (zusaetzliches Kontingent, Verfall bei Neustart).
- Aenderung von `_fetch_weather` oder `_build_stage_trend` (Versand und Alarme wuerden mitwandern).
- **Aufwaermlauf-Rueckbau entfaellt:** `frontend/e2e/trip-preview-thunder-origin.spec.ts`
  existiert nicht mehr (`git ls-files` ohne Treffer); es gibt nichts zurueckzubauen. Das wird im
  Ticket-Abschluss vermerkt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Entscheidungsflaeche: Die Zeitgrenzen-Kette (#2124) und die
  Aussen-Parallelisierung im Vorschau-Pfad (Vorarbeit V3) werden fortgeschrieben, nicht
  geaendert. Neue Nutzertexte laufen ueber den bestehenden Katalog (ADR-0104).

## Changelog

- 2026-11-07: Initial spec created (Issue #1839, Epic #2733 Strang C)
