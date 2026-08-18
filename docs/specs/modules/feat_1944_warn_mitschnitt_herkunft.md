---
entity_id: feat_1944_warn_mitschnitt_herkunft
type: feature
created: 2026-08-18
updated: 2026-08-18
status: draft
workflow: feat-1944-warn-mitschnitt-luecken
version: "1.0"
tags: [alarm, observability, official_alerts]
---

# Warn-Mitschnitt: Herkunft mitführen statt rekonstruieren (Issue #1944, Scheibe 2 aus #1929)

## Approval

- [x] Approved — PO (Henning), 2026-08-18, Antwort „Freigabe" auf die AC-Vorlage

## Purpose

Die Kennung (`capture_id`) eines Eingangs-Mitschnitts amtlicher Warnungen (seit #1948 S1,
`warn_egress.cached_fetch`) wird von ihrer Entstehung bis zum `alert_log`-Eintrag der
versendeten Warnung MITGEFÜHRT statt am Versandpunkt per Zeitfenster-/Namens-Lookup
rekonstruiert. Damit lässt sich künftig für jede tatsächlich verschickte amtliche Warnung
exakt der Roh-Datensatz nachweisen, der sie ausgelöst hat — genau die Frage, die im Vorfall
#1929 (zwei byte-identische Meldungen, keine Zuordnung möglich) unbeantwortet blieb.

## Source

- **File:** `src/services/official_alerts/warn_egress.py`
- **Identifier:** `cached_fetch()`, neuer Rückkanal `observe_capture_id()`/`_capture_id_sink`

> Schicht: Python-Core (`src/services/`) — kein Go-/Frontend-Anteil in dieser Scheibe.

## Estimated Scope

- **LoC:** ~65-100 (produktiv, innerhalb des 250-LoC-Limits)
- **Files:** 6 Code-Dateien (`src/services/official_alerts/warn_egress.py`,
  `src/services/official_alerts/models.py`, `src/services/official_alerts/base.py`,
  `src/services/official_alerts/massif_closure.py`, `src/services/trip_alert.py`,
  `src/services/compare_official_alert.py`) + 1 kleine additive Erweiterung in
  `src/services/alert_log.py` (neuer optionaler Parameter `capture_ids`, gleiches additives
  Muster wie `capture_id` selbst, Z. 338/434 — siehe Implementation Details) plus Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/warn_egress.py::cached_fetch` (#1348/#1397/#1422/#1948) | module | Einziger Netzweg aller 7 Warnquellen; Rückkanal-Muster `_fetch_failure_sink` als Vorbild (Z. 56-98) |
| `src/services/alert_input_capture.py::capture_system` | module | Erzeugt/schreibt den Mitschnitt und liefert `capture_id` als Rückgabewert — bereits vorhanden, kein Neubau |
| `src/services/official_alerts/base.py::get_official_alerts_with_status` | module | Gemeinsame Naht aller 7 Quellen (Z. 148), zentraler Anreicherungspunkt |
| `src/services/official_alerts/models.py::OfficialAlert` | module | Trägt künftig ein additives `capture_id`-Feld |
| `src/services/official_alerts/massif_closure.py::MassifClosureSource.fetch` | module | Einzige Quelle mit mehrfachem Abruf je Aufruf im Produktivpfad — muss die Kennung selbst an die gewinnende Meldung binden |
| `src/services/trip_alert.py::_send_official_alert_only` | module | Versandpunkt Trip, `alert_log.append_entry(...)` Z. 1765 |
| `src/services/compare_official_alert.py` (Z. 201-214) | module | Versandpunkt Ortsvergleich, Parität zum Trip-Pfad |
| `src/services/alert_log.py::append_entry` | module | `capture_id` bereits additiv vorhanden (Z. 261/338); bekommt zusätzlich additiven `capture_ids`-Listenparameter für den Mehrfach-Mitschnitt-Fall |

## Implementation Details

### Rückkanal in `warn_egress` (Vorbild `_fetch_failure_sink`)

`cached_fetch()` behält seinen Rückgabewert (`entry["data"]`/`data`) UNVERÄNDERT — Bestandsaufrufer
laufen bit-identisch weiter. Eine zweite, nestbare `contextvars.ContextVar`
(`_capture_id_sink`, exaktes Vorbild `warn_egress.py:56-98`) trägt die während des Aufrufs
beobachtete(n) `capture_id`(s) als Seiteninformation:

- **Cache-Hit** (Z. 352-364): der Zwischenspeicher-Eintrag bekommt zusätzlich zu `"data"`/
  `"fetched_at"`/`"ttl"` ein `"capture_id"`-Feld. Ein Treffer meldet diesen Wert an den aktiven
  Rückkanal — **kein zusätzlicher Schreibvorgang**, Lücke (a) ist damit geschlossen.
- **Echter Abruf** (Z. 391-401): der bisher verworfene Rückgabewert von
  `alert_input_capture.capture_system(...)` wird in einer lokalen Variablen gehalten. Bei
  wiederholten Versuchen innerhalb der Ratenbremsen-Schleife (Z. 410-429) überschreibt jeder
  Durchlauf diese Variable — nach `break` enthält sie exakt die Kennung des Abrufs, dessen
  Response tatsächlich zum finalen Cache-Eintrag führt (Erfolg, terminales 429, `not_covered`,
  `>=400` oder Parse-Fehler). Diese Kennung wandert in **jeden** der bestehenden
  `cache[cache_key] = {...}`-Schreibpunkte als `"capture_id"` und wird an den Rückkanal
  gemeldet.
- Schlägt `request_fn()` selbst mit einer Exception fehl, findet kein Capture statt (wie
  bisher) — kein `"capture_id"`-Feld, Rückkanal bleibt unberührt.

### Additives Feld an `OfficialAlert`

`capture_id: Optional[str] = None` (`models.py:15`, letztes Feld nach `dedup_id`) — frozen
dataclass, alle Felder ab `valid_from` haben bereits Defaults, kein Bruch bestehender
Konstruktoraufrufe.

### Anreicherung an der gemeinsamen Naht (`base.py:148`)

`get_official_alerts_with_status` öffnet um jeden `source.fetch(lat, lon)`-Aufruf zusätzlich
zum bestehenden `observe_fetch_failure()` einen `observe_capture_id()`-Kontext und sammelt
alle währenddessen gemeldeten Kennungen. Nach dem Aufruf:

- **genau eine** unterschiedliche Kennung beobachtet → sie wird per `dataclasses.replace(...)`
  auf jedes zurückgelieferte `OfficialAlert` angewendet, das **noch keine eigene** `capture_id`
  trägt (additiv, überschreibt nie eine bereits gesetzte).
- **keine oder mehr als eine** unterschiedliche Kennung beobachtet → nichts wird angereichert;
  die Alerts behalten `capture_id=None`. Das ist die geforderte Mehrdeutigkeits-Regel (AC-4):
  eine falsche Zuordnung ist schlimmer als keine.

Die 6 einfach-abrufenden Quellen (GeoSphere, Vigilance, DPC, Météo-Forêts,
`MeteoAlarmFeedSource("AT")`, `MeteoAlarmFeedSource("IT")`) rufen `cached_fetch()` je
`fetch()`-Aufruf genau einmal auf und werden dadurch automatisch korrekt angereichert.

### `massif_closure.py` — Sonderfall mehrfacher Abruf je Quellen-Aufruf

`fetch()` (Z. 124-141) ruft `_get_cached_daily_json()` in einer Schleife über alle
betroffenen Massive und behält nur die Meldung mit dem höchsten `level`. Ein naives
"letzter gewinnt" (oder die generische Naht-Regel aus `base.py`, die bei mehreren
beobachteten Kennungen `None` liefern würde) verlöre entweder die Zuordnung ganz oder hängte
sie versehentlich an ein NICHT gewähltes Massiv. Die Schleife öffnet daher pro Iteration
einen **eigenen, engen** `observe_capture_id()`-Kontext um genau den einen
`_get_cached_daily_json()`-Aufruf dieses Massivs und bindet die daraus beobachtete Kennung
sofort per `dataclasses.replace(alert, capture_id=...)` an den JEWEILIGEN Kandidaten-Alert,
bevor `best_alert` aktualisiert wird. Der am Ende zurückgelieferte `best_alert` trägt dadurch
IMMER die Kennung des Abrufs, der ihn tatsächlich erzeugt hat — unabhängig von der
Iterationsreihenfolge. Da `OfficialAlert.capture_id` an dieser Stelle bereits gesetzt ist,
überschreibt die generische Anreicherung in `base.py` sie nicht (additive Regel oben).

Die verschachtelten `ContextVar`-Kontexte laufen korrekt nacheinander ab: solange der enge
Massiv-Kontext aktiv ist, "gewinnt" er die Kontextvariable — der äußere, in `base.py`
geöffnete Kontext sieht während dieser Zeit keine Meldung (kein Fehlverhalten, siehe Known
Limitations).

### Protokolleintrag — Trip und Ortsvergleich (Parität)

An beiden Versandpunkten (`trip_alert.py` ~Z. 1765, `compare_official_alert.py` ~Z. 201-214)
werden die distinct `capture_id`-Werte der gerade versendeten `OfficialAlert`-Objekte
gesammelt (`{a.capture_id for a, _ in official_notices/tagged_alerts if a.capture_id}`):

- **0 Kennungen** (kein Alert trug eine, z.B. wegen Mehrdeutigkeit oder Fail-open-Fehlschlag)
  → weder `capture_id=` noch `capture_ids=` an `append_entry()` übergeben (Bestandsverhalten).
- **genau 1** → `capture_id=<diese Kennung>` (bestehendes, additives Feld, unverändert genutzt).
- **mehr als 1** (Bündel mehrerer Quellen im Trip bzw. mehrerer Orte im Ortsvergleich — genau
  der Vorfall aus #1929) → `capture_ids=<sortierte, entdoppelte Liste>`. `capture_id` bleibt
  bewusst UNGESETZT statt eine der Kennungen willkürlich zu wählen — eine Auswahl würde exakt
  die Frage wieder verschließen, die dieses Ticket beantworten soll.

`alert_log.append_entry()` bekommt dafür einen neuen, additiven Parameter
`capture_ids: Optional[Iterable[str]] = None`, nach demselben Muster wie `capture_id` selbst
ergänzt (`alert_log.py:338`: `if capture_id is not None: entry["capture_id"] = capture_id`) —
`if capture_ids: entry["capture_ids"] = sorted(set(capture_ids))`. Alt-Einträge ohne dieses
Feld bleiben unverändert lesbar (Read-Modify-Write, Bestandsschutz).

## Expected Behavior

- **Input:** unverändert — interne Aufrufe der bestehenden Alarm-Pfade (kein neuer externer
  Endpoint, keine neue Nutzereingabe).
- **Output:** Zwischenspeicher-Einträge tragen `capture_id`; `alert_log`-Einträge amtlicher
  Warnungen tragen `capture_id` (ein Mitschnitt) oder `capture_ids` (mehrere Mitschnitte) —
  in Trip UND Ortsvergleich.
- **Side effects:** keine neuen Dateischreibvorgänge (Lücke a ist ein reiner Rückkanal, kein
  zusätzlicher Mitschnitt). SMS/E-Mail/Telegram-Inhalt, Auslösung und Format bleiben
  bit-identisch — reine Beweisaufnahme.

## Test Plan

Deterministischer Kern, keine Mock-Theater: `cached_fetch()` wird über das bestehende
`request_fn`-Seam mit echten Fixture-Antworten aufgerufen, geschriebene/gelesene JSON-Dateien
werden strukturell (geladen + Feldvergleich) statt per String-Suche geprüft.

### Automated Tests (TDD RED)

- [ ] `tests/unit/test_warn_egress_capture_id_passthrough.py` — Cache-Hit liefert dieselbe
  `capture_id` wie der Ursprungsabruf, ohne erneuten Mitschnitt. → AC-1
- [ ] `tests/unit/test_trip_alert_official_alert_capture_correlation.py` — `alert_log`-Eintrag
  im Trip-Pfad trägt `capture_id` des auslösenden Mitschnitts. → AC-2
- [ ] `tests/unit/test_compare_official_alert_capture_correlation.py` — dasselbe für den
  Ortsvergleich-Pfad, Paritätsnachweis zu AC-2. → AC-3
- [ ] `tests/unit/test_massif_closure_capture_ambiguity.py` — mehrere Massiv-Treffer:
  gewinnende Meldung trägt die korrekte, eigene Kennung; ein generischer
  Mehrfach-Abruf-Stub (Stellvertreter für die stillgelegte `meteoalarm.py`) liefert
  `capture_id=None`. → AC-4
- [ ] `tests/unit/test_warn_egress_capture_id_after_retry.py` — nach einer
  Ratenbremsen-Wiederholung trägt der finale Cache-Eintrag die Kennung des LETZTEN
  verwerteten, nicht eines verworfenen Zwischenversuchs. → AC-5
- [ ] `tests/unit/test_alert_log_capture_ids_bundle.py` — ein Versand mit zwei
  unterschiedlichen `capture_id`-Werten erzeugt einen Eintrag mit `capture_ids` (Liste) statt
  eines willkürlich gewählten `capture_id`. → AC-6
- [ ] `tests/unit/test_official_alert_capture_failopen.py` — ein Fehlschlag im
  Herkunfts-Pfad (Rückkanal/Mitschnitt) verhindert den Alarmversand NICHT. → AC-7
- [ ] `tests/unit/test_official_alert_output_unchanged.py` — SMS-/E-Mail-/Telegram-Ausgabe vor
  und nach der Änderung ist byte-identisch bei gleicher Eingabe. → AC-8
- [ ] `tests/unit/test_warn_egress_special_paths_unchanged.py` — Netzwerk-Ausnahme, gecachter
  Fehlschlag, `not_covered_statuses`, `self_throttled` bleiben in ihrem beobachtbaren Verhalten
  unverändert. → AC-9

## Acceptance Criteria

- **AC-1:** Given ein amtlicher Warndienst wurde bereits erfolgreich über `cached_fetch()`
  abgerufen und der Zwischenspeicher-Eintrag ist noch innerhalb seiner TTL gültig, When ein
  zweiter Aufruf mit demselben `cache_key` erfolgt (ohne dass `request_fn` erneut aufgerufen
  werden darf), Then liefert der Rückkanal für diesen zweiten Aufruf exakt dieselbe
  `capture_id` wie der erste, echte Abruf — ohne einen zusätzlichen Mitschnitt zu schreiben.
  - Test: `cached_fetch()` zweimal mit demselben `cache_key` aufrufen; beim zweiten Aufruf
    wirft ein injiziertes `request_fn` eine Exception (Positivkontrolle: würde die Funktion
    fälschlich erneut abrufen, schlägt der Test hart fehl statt nur die Kennung falsch zu
    melden). Über `observe_capture_id()` die gemeldete Kennung beider Aufrufe strukturell
    vergleichen; Anzahl der Dateien unter `data/debug/alert_input/official_alert/` bleibt bei 1.

- **AC-2:** Given eine amtliche Warnung wird im Trip-Pfad tatsächlich verschickt und ihr
  zugrundeliegender `OfficialAlert` trägt eine `capture_id`, When
  `_send_official_alert_only` den `alert_log`-Eintrag schreibt, Then enthält dieser Eintrag
  ein `capture_id`-Feld mit exakt diesem Wert.
  - Test: `_send_official_alert_only` mit einem `official_notices`-Tupel aufrufen, dessen
    `OfficialAlert.capture_id` gesetzt ist; den geschriebenen `alert_log.json`-Eintrag laden
    (`json.loads`) und das Feld strukturell mit dem erwarteten Wert vergleichen.

- **AC-3:** Given eine amtliche Warnung wird im Ortsvergleich-Pfad tatsächlich verschickt und
  ihr zugrundeliegender `OfficialAlert` trägt eine `capture_id`, When der `alert_log`-Eintrag
  für den Ortsvergleich geschrieben wird, Then enthält dieser Eintrag dasselbe `capture_id`-
  Feld wie im Trip-Pfad (AC-2) — Paritätsnachweis zwischen beiden Flächen.
  - Test: dieselbe Struktur wie AC-2, aber über den Ortsvergleich-Versandpunkt
    (`compare_official_alert.py`); Vergleich der beiden geschriebenen Einträge auf identisches
    Feldschema.

- **AC-4:** Given eine Quelle ruft `cached_fetch()` mehrfach innerhalb EINES
  `fetch()`-Aufrufs auf und liefert nur EINE gewinnende Meldung zurück (`massif_closure.py`
  bei mehreren überlappenden Massiven; strukturell ebenso die stillgelegte `meteoalarm.py`),
  When nicht eindeutig feststellbar ist, welcher Abruf zur gewinnenden Meldung gehört, Then
  trägt die gewinnende Meldung entweder die KORREKTE eigene Kennung (massif_closure bindet sie
  bereits während der eigenen Iteration) oder — wenn die Zuordnung strukturell unbestimmbar
  bleibt — `capture_id=None`, NIE die Kennung eines nicht gewählten Abrufs.
  - Test (negative Probe): zwei Massiv-Treffer mit unterschiedlichem Niveau und
    unterschiedlichen, injizierten Abruf-Antworten so anordnen, dass die Iterationsreihenfolge
    NICHT mit der Gewinner-Reihenfolge übereinstimmt; strukturell nachweisen, dass
    `best_alert.capture_id` zur Antwort des GEWINNENDEN Massivs gehört, nicht zur zuletzt
    ausgeführten Iteration. Zusätzlich ein generischer Quellen-Stub mit zwei `cached_fetch()`-
    Aufrufen unter der `base.py`-Naht: `capture_id` der zurückgelieferten Alerts ist `None`.

- **AC-5:** Given ein Warndienst antwortet zunächst mit HTTP 429 und einer konfigurierten
  Kurzzeit-Ratenbremse (`RateLimitRetryPolicy`), When `cached_fetch()` daraufhin einen
  Zwischenversuch verwirft und einen weiteren, diesmal erfolgreichen Versuch unternimmt, Then
  trägt der finale Zwischenspeicher-Eintrag die `capture_id` des LETZTEN, tatsächlich
  verwerteten Versuchs — nicht die des verworfenen Zwischenversuchs.
  - Test: `request_fn` liefert beim ersten Aufruf 429, beim zweiten Aufruf 200 mit
    unterschiedlichem Body; beide Aufrufe erzeugen je einen eigenen Mitschnitt-Datensatz;
    strukturell nachweisen, dass der im Cache-Eintrag hinterlegte `capture_id`-Wert auf den
    ZWEITEN (verwerteten) Mitschnitt-Datensatz zeigt, nicht auf den ersten.

- **AC-6:** Given ein einzelner Versand bündelt amtliche Warnungen aus MEHREREN
  Mitschnitten (mehrere Quellen im Trip-Pfad bzw. mehrere Orte im Ortsvergleich, wie im
  Vorfall #1929), When der `alert_log`-Eintrag geschrieben wird, Then enthält er ein additives
  `capture_ids`-Feld mit allen beteiligten, entdoppelten Kennungen, und das skalare
  `capture_id`-Feld bleibt UNGESETZT (keine willkürliche Auswahl einer der Kennungen).
  - Test: zwei `OfficialAlert`-Objekte mit unterschiedlichen `capture_id`-Werten in einem
    Versand kombinieren; den geschriebenen `alert_log.json`-Eintrag strukturell laden und
    prüfen, dass `"capture_ids"` beide Werte sortiert/entdoppelt enthält und `"capture_id"`
    NICHT im Eintrag vorkommt.

- **AC-7:** Given ein Fehler tritt irgendwo im Herkunfts-Pfad auf (Rückkanal-Meldung, Lesen/
  Schreiben der Mitschnitt-Zuordnung, `dataclasses.replace`), When der umgebende Alarm-Zweig
  weiterläuft, Then wird die amtliche Warnung trotzdem wie gewohnt geprüft, gefiltert und
  verschickt — der Fehler wird höchstens als Log-Warnung sichtbar, nie als Exception nach
  oben gereicht und nie als ausbleibender Versand.
  - Test: die Herkunfts-Ermittlung (z.B. `capture_system`-Rückgabewert oder Rückkanal-Zugriff)
    gezielt zum Werfen bringen (injizierte Fehlerquelle); nachweisen, dass `result.sent`
    weiterhin `True` ist und der `alert_log`-Eintrag ohne `capture_id`/`capture_ids`, aber sonst
    vollständig geschrieben wird.

- **AC-8:** Given identische Eingabedaten (Trip/Ortsvergleich-Fixture, amtliche Warnung), When
  SMS-, E-Mail- und Telegram-Ausgabe vor und nach dieser Änderung gerendert werden, Then sind
  Inhalt und Format BYTE-IDENTISCH — kein sichtbares Verhalten ändert sich (reine
  Beweisaufnahme).
  - Test: bestehende Renderer-Fixture-Läufe (unverändert, da `official_alerts.py:1896-2104`
    nicht angefasst wird) vor/nach der Implementierung strukturell vergleichen (Diff auf dem
    gerenderten String, nicht auf dem Vorhandensein einer Teilzeichenkette).

- **AC-9:** Given die bestehenden Sonderpfade von `cached_fetch()` (Netzwerk-Ausnahme,
  gecachter Fehlschlag mit `data=None`, `not_covered_statuses`, `self_throttled`-Rückzug),
  When diese Pfade nach der Erweiterung erneut durchlaufen werden, Then bleiben Rückgabewert,
  TTL, `log_warn_service_call`-Argumente und Verhalten in jedem dieser Pfade unverändert zum
  Bestand vor dieser Scheibe.
  - Test: bestehende Tests aus `fix_1422_warn_ausfall_alarm.md` und den #1397-Ratenbremsen-
    Tests unverändert erneut ausführen (grüner Regressionsnachweis); ergänzend je Sonderpfad
    das zurückgegebene Cache-Entry-Dict strukturell auf die BISHERIGEN Schlüssel prüfen, das
    neue `capture_id`-Feld ist rein additiv und darf keinen bestehenden Wert verändern.

## Known Limitations

- **Retention-Grenze (50 Datensätze je Ablage) bleibt unverändert und ungemessen.**
  `/var/lib/gregor` war aus dieser Arbeitssitzung nicht lesbar — die reale Mitschnitt-Rate
  ließ sich nicht ermitteln. Offen bleibt, wie viele Tage rückwirkend eine Vorfallanalyse mit
  dieser Grenze tatsächlich reicht.
- **`src/output/renderers/alert/official_alerts.py:1896-2104` bleibt Sperrzone (#1929)** und
  wird durch diese Scheibe nicht angefasst — die Anreicherung liegt strukturell davor, im
  Abruf-/Versand-Layer.
- **Die stillgelegte `meteoalarm.py`-Quelle wird NICHT reaktiviert.** Der
  Mehrdeutigkeits-Mechanismus (AC-4) deckt ihre Risikoklasse strukturell ab (mehrfacher Abruf
  ohne Selbstbindung), ein Reaktivierungs-Test läuft aber gegen einen Stub, nicht gegen den
  echten, weiterhin unregistrierten Quellcode.
- **Die äußere Ambiguitäts-Beobachtung an der `base.py`-Naht sieht während
  `massif_closure.fetch()` strukturell nichts** — der enge, quelleneigene Kontext
  "gewinnt" die geteilte `ContextVar` für die Dauer seiner Iteration. Kein Fehlverhalten
  (massif_closure bindet die Kennung bereits selbst korrekt), aber beim Lesen des Codes ohne
  diese Notiz leicht misszuverstehen.
- **In-Memory-Cache pro Prozess:** die Zwischenspeicher-Dicts der Warnquellen leben nur im
  Prozessspeicher. Ein Prozess-Neustart verliert Cache-Eintrag UND die mitgeführte
  `capture_id` gemeinsam — unverändertes Bestandsverhalten von `cached_fetch()`, hier nur
  explizit festgehalten, weil die Kennung diesen Lebenszyklus jetzt sichtbar teilt.
- Diese Scheibe ändert KEIN sichtbares Alarm-Format (SMS/E-Mail/Telegram bleiben
  bit-identisch, AC-8) — reines Beweisaufnahme-Feature.

## Verworfene Alternative

**Zeitfenster-Lookup über den Dienstnamen am Versandpunkt** (Vorbild Nowcast-Zweig,
`latest_capture_id(branch, source_key, max_age=...)`, wie im Issue-Body vorgeschlagen) wurde
geprüft und verworfen — zwei unabhängige, je für sich ausreichende Bruchgründe, beide am Code
verifiziert:

1. **Namens-Bruch.** `OfficialAlert.source` ist nicht der Schlüssel, unter dem der Mitschnitt
   abgelegt wird:
   - Vigilance meldet `OfficialAlert.source="meteofrance_vigilance"` (`vigilance.py:130`),
     schreibt den Mitschnitt aber unter `service="vigilance"` (`vigilance.py:94`, wird als
     `source_key` an `capture_system()` durchgereicht, `warn_egress.py:394`).
   - `MeteoAlarmFeedSource` meldet `OfficialAlert.source="meteoalarm"` (bewusst konstant,
     `meteoalarm_feed.py:276-277`), schreibt den Mitschnitt aber unter
     `service=f"meteoalarm_feed:{country}"` → `meteoalarm_feed:AT`/`meteoalarm_feed:IT`
     (`meteoalarm_feed.py:212`).

   Ein Lookup über `OfficialAlert.source` fände für diese Quellen NIE einen Mitschnitt-
   Datensatz — die Schlüssel stimmen strukturell nicht überein.

2. **Zu grobe Körnung.** Der Mitschnitt-`source_key` ist der konstante Dienstname
   (`warn_egress.py:394`, z.B. immer `"vigilance"`), während der eigentliche
   Zwischenspeicher-`cache_key` provider-spezifisch pro Koordinate gerundet ist. Liegen zwei
   Touren im selben 15-Minuten-Prüftakt bei derselben Quelle (z.B. zwei GeoSphere-Orte), teilen
   sich ihre Mitschnitte denselben `source_key` — ein Zeitfenster-Lookup fände beide und müsste
   den jüngeren wählen, in rund der Hälfte der Fälle den FREMDEN. Das verletzt die
   Randbedingung „falsche Zuordnung ist schlimmer als keine" im Regelbetrieb, nicht nur
   theoretisch.

Gewählt wurde stattdessen das Mitführen der Kennung durch den Abruf hindurch — die Zuordnung
entsteht dort, wo sie eindeutig ist (am Ursprungsabruf), statt hinterher aus zwei nicht
übereinstimmenden Schlüsselräumen geraten zu werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein additive Erweiterung dreier bereits etablierter Muster — Rückkanal per
  `ContextVar` (identisch zu `_fetch_failure_sink`, `warn_egress.py:56-98`), additives
  dataclass-Feld (`OfficialAlert.capture_id`, gleiches Muster wie `dedup_id`) und additiver
  Listen-Parameter in `alert_log.append_entry` (gleiches Muster wie `capture_id` selbst,
  `alert_log.py:338`). Keine neue Persistenztechnologie, keine neue externe Abhängigkeit,
  keine Rücknahme einer bestehenden Architekturentscheidung — dieselbe Einordnung wie die
  Vorgänger-Spec (`alarm_eingangsprotokoll.md`, #1948 S1).

## Changelog

- 2026-08-18: Initial spec created (Scheibe 2 aus #1929, Folge-Ticket #1944 zu #1948 S1).
