---
entity_id: waechter_1405_erfolg_wirkung
type: module
created: 2026-07-28
updated: 2026-07-28
status: implemented
version: "1.2"
tags: [tests, guard, success-status, issue-1405]
---

<!-- Issue #1405 — Wächter 2 von 5, Hälfte B ("Erfolg heißt Wirkung") -->

# Wächter 1405 — Erfolgsstatus ohne Wirkungsnachweis

## Approval

- [x] Approved — PO Henning, 2026-07-28 („go"), Version 1.2, inkl.
  Änderungsbudget **2800** Zeilen. Zugleich PO-Entscheidung zum Zuschnitt:
  **am Stück durchziehen**, nicht in zwei Arbeitseinheiten teilen — die
  Vorgabe ist nach drei Härtungsrunden gegen den echten Code belastbar, ein
  weiterer Zuschnitt brächte mehr Reibung als Nutzen. Bekanntes Restrisiko:
  die Adversary-Runde muss fünf Signaturen auf einmal beurteilen (bei
  Hälfte A fand sie bei einer Signatur einen echten HIGH-Befund) — daher
  ist die Gegenprüfung hier ausdrücklich klassenweise zu führen.

  Vorgeschichte: Version 1.0 freigegeben mit Budget 1700, Version 1.1 mit
  2200. Beide Male wuchs der Umfang, weil die Signaturen am Schreibtisch
  entworfen statt aus dem Code abgeleitet wurden.

## Purpose

Ein AST-basierter Wächter-Test erkennt künftig jeden neuen Fall, in dem ein
`ok`/`sent`/`success`-Status **nicht** aus dem tatsächlichen Ergebnis
abgeleitet wird — sei es, weil er einem Aufruf-Ergebnis nicht folgt (Klasse
1), weil eine Erfolgs-Sammlung vor dem riskanten Versand befüllt wird
(Klasse 1c), weil ein Teilerfolg strukturell nicht als Teilerfolg erkennbar
ist (Klasse 2), weil eine Erfolgsmeldung (Heartbeat) nie an den echten
Vorgang angeschlossen wurde (Klasse 3), oder weil ein Versand-Aufruf im
Versandkontext dem Aufrufer strukturell gar kein Erfolgssignal zurückgibt
(Klasse 4, jetzt auf den Versandkontext eingeschränkt — s. „Anlass der
zweiten Überarbeitung"). Belegte Vorfälle: #1290, #1346, #1348, #1403. Wie
bei Hälfte A existiert die Norm bereits im eigenen Code
(`run_briefing_dispatch()`/`(sent, failed)`-Tupel,
`api/routers/scheduler.py:42-44`) — dieser Wächter rollt sie auf die
restlichen Erfolgsmeldungen aus, statt eine neue Regel zu erfinden. Diese
Arbeitseinheit ändert **keinen Produktivcode** — Wächter vor Reparatur
(Ticket-Reihenfolge, Lehre aus #1402, fortgeführt in Hälfte A).

**Anlass der ersten Überarbeitung (2026-07-28, Version 1.1):** die
ursprünglichen drei Klasse-1/2-Signaturen wurden am Schreibtisch entworfen
und passten nachweislich nicht auf den echten Code. Eine Ableitung aus den
tatsächlichen Fundstellen hat tragfähige Muster geliefert.

**Anlass der zweiten Überarbeitung (2026-07-28, Version 1.2):** die RED-Phase
gegen Version 1.1 hat zehn Befunde gemeldet (S-1 bis S-10). Drei zeigten,
dass Signaturen **zu weit** gefasst waren (Klasse-2-Bedingung 3
widersprach der eigenen Attrappen-Gegenprobe AC-8; Klasse 4 traf 18 statt 3
Stellen, davon 15 Persistenz-Helfer außerhalb des eigentlichen Themas;
„undurchsichtiger Aufruf" hätte 15 harmlose Aggregations-Funktionen in
`weather_metrics.py` mitgerissen). Mehrere weitere waren echte, bislang
übersehene Fundstellen (ein dateiweites Muster in
`trip_command_processor.py`, zwei zu Unrecht als „kein Fund" erklärte
Inbound-Reader). Diese Version zieht Spec und Restliste auf beide Befunde
nach — verengt, wo die Signatur nachweislich zu weit war, und erweitert,
wo echte Funde fehlten — **bevor** implementiert wird.

## Source

- **File:** `tests/test_success_status_guard.py` (bestehend, RED-Stand
  1797 Zeilen — s. „Estimated Scope" zur neuen Größenschätzung)
- **Identifier:** Modul-Ebene — kein Produktivcode-Symbol, sondern ein
  Test-Wächter mit mehreren `test_*`-Funktionen und Hilfsfunktionen je
  Bugklasse (`_find_constant_success_violations()` /
  `_find_pre_try_success_marker_violations()` /
  `_find_partial_success_blind_violations()` /
  `_find_unwired_heartbeat_violations()` /
  `_find_unacknowledged_dispatch_violations()` / `_all_violations()`)

> **Schicht-Hinweis:** reines Python-Core-Testartefakt (`tests/`). Scanfläche
> ist `api/routers/**` + `src/services/**` (Python-Core, s. „Implementation
> Details" zur exakten Abgrenzung). Kein Frontend-, Go-API- oder
> `internal/`-Bezug — die übrigen Heartbeat-Aufrufe in
> `internal/notify/mq.go`/`internal/config/config.go` liegen außerhalb der
> Reichweite eines Python-Scans (s. „Aus dem Scope ausgeschlossen").

## Estimated Scope

- **LoC:** realistisch **2400–2800** (vorher 1600–2200 in Version 1.1).
  Begründung der Verschiebung gegenüber der RED-Schätzung (≈2400–2500):
  - **E2 (Klasse-4-Zusatzbedingung, Versandkontext):** ein zusätzlicher
    strukturneller Check „enthält der Rumpf einen Aufruf auf
    `EmailOutput`/`TelegramOutput`/`SMSOutput`(`.send(...)`) oder einen
    übergebenen Sink-Parameter" — ein eigener AST-Baustein, ~30–50 LoC.
    Verkleinert den Zuwachs NICHT wie in Version 1.1 angenommen (18 → 3),
    weil eine unabhängige Verifikation drei WEITERE echte
    Versandkontext-Treffer gefunden hat (B21, s. u.) — netto bleibt Klasse 4
    bei sechs statt drei Fundstellen.
  - **E3 (dateiweites Muster `trip_command_processor.py`, B18):** zehn neue
    Funktionsschlüssel (`_handle_query` mit vier Treffern, neun weitere mit
    je einem), macht 13 neue Restlisten-Zeilen á ~10–15 LoC (Kommentar +
    Begründung) plus die AC-1-Tabellenzeilen: ~150–200 LoC.
  - **E4 (Inbound-Reader, B19/B20):** zwei Funktionsschlüssel wandern von
    „kein Fund" (Textabsatz) in die Restliste (Klasse 2) — ~20–30 LoC,
    dazu ein Absatz weniger in „Ausnahmekandidaten".
  - **E6 (Klasse-2-Trennschärfe „undurchsichtiger Aufruf"):** eine feste
    Ausschlussliste (Python-Builtins `len`/`sum`/`max`/`min`/`round`/`abs`/
    `getattr`/`hasattr`/`isinstance` sowie `math.*`-Aufrufe zählen NICHT
    als undurchsichtig) plus eine Verschont-Probe mit mind. fünf
    `weather_metrics.py`-Funktionen: ~40–60 LoC.
  - **E1/E5 (S-1, S-6 bis S-9):** Korrekturen an bestehender (noch nicht
    gebauter) Logik, keine große Flächen-Erweiterung, aber zusätzliche
    Verzweigungen + je ein synthetischer Nachweis für S-7 (Dekorator-
    Ausschluss) und S-9 (nacktes `return`): ~60–100 LoC.
  - **B21 (drei weitere Klasse-4-Funde im Versandkontext,
    `notification_service.py`):** drei neue Funktionsschlüssel, ~30–45 LoC.
  - Summe der Zuwächse gegenüber der RED-Schätzung: ~330–485 LoC, davon ein
    Teil bereits in der Entwickler-Schätzung (2400–2500) enthalten. Die
    hier ausgewiesene Bandbreite (2400–2800) ist die aktualisierte
    Gesamtschätzung, nicht eine Summe on top.
- **Files:** 1 geändert (Testdatei, bestehend seit RED). **0
  Produktivdateien geändert.**
- **Effort:** high

**Freigabepunkt:** `python3 .claude/hooks/workflow.py set-field
loc_limit_override 2800` ist vor der Implementierungsphase beim PO
**erneut** einzuholen (das 2200-Budget aus Version 1.1 deckt die
zusätzlichen Restlisten-Blöcke B18–B21 und die Klasse-4/Klasse-2-Präzisierungen
nicht ab).

**Regel-Budget (CLAUDE.md):** unverändert — Prüfdatum **2026-10-26** (+90
Tage, identisch mit Hälfte A).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/fix-1405-b-erfolg-waechter.md` | Faktenbasis | Die gegen `0627612d` verifizierte Bestandsaufnahme (16 Fundstellen, Signaturvorschläge, Ausnahmekandidaten) — Quelle aller ursprünglichen Restlisten-Angaben (B1–B14). B15–B17 stammen aus der Tech-Lead-Entscheidung 2026-07-28 (Version 1.1); B18–B21 aus der RED-Phase-Nachschärfung 2026-07-28 (Version 1.2), gegen `0627612d` per `grep -n` + `Read` nachverifiziert |
| `tests/test_resolution_loss_guard.py` (Hälfte A, #1405) | Bauform-Vorbild | AST-Scan, `KNOWN_VIOLATIONS`-Restliste als `dict[str, str]`, zwei gekoppelte Ratschen-Tests, synthetische Wirkungsnachweise, `_scopes()`/`_walk_local()`-Bausteine wiederverwendbar |
| `src/services/dispatch_orchestrator.py:157` `run_briefing_dispatch()` | Referenzmuster | Die durchsetzbare Hausnorm: `(sent, failed)`-Tupel aus einer fehler-isolierten Schleife, Status rein aus `failed > 0` abgeleitet — MUSS strukturell ausgeschlossen bleiben |
| `api/routers/scheduler.py:42-44`/`:142-144` | Referenzmuster | Zwei Vorbild-Endpunkte, die die Hausnorm bereits korrekt anwenden (`status = "partial" if failed > 0 else "ok"`) |
| `src/services/channel_test_service.py::send_test_message` (Z. 12-45) | Referenzmuster | `{"status": "ok"}` (Z. 42) NUR wenn `output.send()` ohne Ausnahme durchläuft, `except`-Zweig gibt `{"error": str(exc)}` zurück (Z. 43-44) — MUSS strukturell ausgeschlossen bleiben (Gegenprobe „except divergiert", AC-5) |
| `src/services/forecast_budget.py::ForecastBudgetGate.snapshot` (Z. 87-113) | Referenzmuster | Zweites Beleg-Beispiel „except divergiert": `"status": "ok"` (Z. 102) im `try`, `except Exception` liefert `"status": "unavailable"` (Z. 112) — andere Literal, korrekt ausgeschlossen |
| `src/services/official_alerts/meteoalarm_budget.py::MeteoAlarmBudgetGate.snapshot` (Z. 130-153) | Referenzmuster | Drittes Beleg-Beispiel, identisches Muster (`"ok"` Z. 143 / `"unavailable"` Z. 152) |
| `src/services/notification_service.py::_dispatch_compare_official_email/_telegram/_sms` (Z. 878, 891, 929) | Fundort (Klasse 4, Versandkontext) | B14b — reines `try/except`, Handler nur `logger.error`, kein `return`-Wert, ruft `EmailOutput`/`TelegramOutput`/`SMSOutput`(`.send(...)`) |
| `src/services/notification_service.py::_send_telegram_incomplete_hint/send_command_reply_email/_send_service_error_email` (Z. 385, 1115, 1293) | Fundort (Klasse 4, NEU Version 1.2, B21) | Dieselbe Mechanik wie B14b — try/except mit Logger-only-Handler, kein `return`-Wert, ruft `TelegramOutput`/`EmailOutput`(`.send(...)`) im eigenen Rumpf. Bei der E2-Verifikation zusätzlich zu den drei bekannten B14b-Helfern gefunden — die Erwartung „nur drei Treffer" aus der Tech-Lead-Vorgabe hat sich als zu niedrig erwiesen (s. „Geklärte Punkte" 9) |
| `src/services/alert_state.py::save/reset`, `src/services/weather_snapshot.py::save`, `src/services/compare_weather_snapshot.py::save` | Bewusst nicht erfasst (Persistenz) | Erfüllen die UNEINGESCHRÄNKTE Klasse-4-Form (try/except, Logger-only-Handler, kein Rückgabewert), aber OHNE Aufruf auf einen Kanal-Ausgang — E2 schließt sie deshalb strukturell aus. Eigener Befund, weiterverfolgt in #1199 (s. „Aus dem Scope ausgeschlossen") |
| `src/services/trip_command_processor.py::_handle_query/_handle_drilldown/_handle_hours_drilldown/_apply_ruhetag/_show_status/_apply_pause/_apply_skip/_show_now/_cancel_trip/_resume_trip` | Fundort (Klasse 1, NEU Version 1.2, B18) | Dateiweites Muster — dieselbe Mechanik wie B15/B16: ein abgeleiteter oder unzugewiesener Aufruf, danach ein hartkodiertes `success=True` im `CommandResult`-Konstruktor, das den abgeleiteten Wert nicht referenziert |
| `src/services/inbound_email_reader.py::poll_and_process` (Z. 50/77), `src/services/inbound_telegram_reader.py::poll_and_process` (Z. 91/107) | Fundort (Klasse 2, NEU Version 1.2, B19/B20) | `for`-Schleife über `uids`/`updates`, Zähler `processed` nur aus dem undurchsichtigen Aufruf `self._process_single(...)`/`self._process_update(...)` erhöht, kein Fehlerzähler, `return processed` (bloßer Skalar) — dieselbe Mechanik wie B9–B11c |
| `src/services/weather_metrics.py` (≥15 Aggregationsfunktionen), `src/services/aggregation.py`, `src/services/day_comparison.py`, `src/services/comparison_engine.py` | Verschont-Probe (Klasse 2, NEU Version 1.2) | Zählschleifen/Comprehensions, deren Aufrufe AUSSCHLIESSLICH Python-Builtins (`len`/`sum`/`max`/`min`/`round`/`getattr`/`hasattr`/`isinstance`) oder `math.*` sind — MÜSSEN strukturell ausgeschlossen bleiben (s. „Implementation Details", Klasse 2, „Verschont-Ausschlussliste") |
| `ast` (stdlib) | Parser | Strukturelle Erkennung ohne Regex-Rateraten |
| CLAUDE.md → Test-Politik / Regel-Budget | Prozess | Kern-Schicht-Pflicht, Prüfdatum-Pflicht für neue Pflicht-Tests |
| Epic #1372 „Kein stilles Verwerfen" | Vorgabe | Zielbild-Satz 2: „Ein `ok`/`sent`/`success` wird aus dem tatsächlichen Ergebnis abgeleitet, nie konstant gesetzt" |

## Implementation Details

### Scanfläche

`api/routers/**/*.py` (rekursiv) + `src/services/**/*.py` (rekursiv, inkl.
`official_alerts/`). Deckt alle Fundstellen ab. `tests/` und `internal/`
(Go) sind bewusst nicht Teil der Scanfläche (s. „Aus dem Scope
ausgeschlossen").

### Fünf Signaturen — je eine eigene Erkennung, EIN gemeinsames Ergebnis-Dict

Alle Detektoren liefern Funde in derselben Form wie Hälfte A:
`{"pfad:zeile": "<klasse>::<funktionsname>"}`, zu einem gemeinsamen
`KNOWN_VIOLATIONS`/Ratschen-Paar zusammengeführt (Bauform 1:1 von Hälfte A;
`KIND_CONSTANT_SUCCESS` / `KIND_PRE_TRY_SUCCESS_MARKER` /
`KIND_PARTIAL_SUCCESS_BLIND` / `KIND_HEARTBEAT_UNWIRED` /
`KIND_UNACKNOWLEDGED_DISPATCH` als Klassen-Präfix).

**Mehrfachtreffer auf derselben `pfad:zeile` (S-6, NEU 2026-07-28):**
kollidieren zwei Detektoren auf demselben Schlüssel (z. B. weil eine
Funktion sowohl Klasse 3 als auch — vor der E2-Einschränkung — Klasse 4
erfüllt hätte), gewinnt KEINER still: GREEN führt beide Arten im Wert
(z. B. `"heartbeat_unwired+unacknowledged_dispatch::_ping_heartbeat_compare"`)
statt eine zu überschreiben. Das gilt auch bei der Zusammenführung über
mehrere Detektor-DURCHLÄUFE (Klasse-3-Lauf über die ganze Scanfläche PLUS
die vier dateiweisen Detektoren je Datei), nicht nur innerhalb eines
einzelnen Detektors. **Hinweis zur Aktualität dieses Beispiels:** der
ursprünglich gemeldete Kollisionsfall `api/routers/scheduler.py:147`
(`_ping_heartbeat_compare`) kollidiert nach der E2-Einschränkung (s. u.)
NICHT mehr — die Funktion ruft `httpx.get(...)`, keinen Kanal-Ausgang, und
erfüllt Klasse 4 damit nicht mehr. Die Merge-Regel bleibt trotzdem
verbindlicher Bestandteil dieser Spec (Verteidigung in der Tiefe): ein
künftiger Fund kann jederzeit auf zwei Detektoren zugleich treffen, und die
Zusammenführung darf das nie verschweigen.

**Klasse 1 — konstanter Erfolgswert aus einem Aufruf (`KIND_CONSTANT_SUCCESS`):**
Eine Funktion ist Klasse-1-Fund, wenn

- (a) sie eine Variable aus einem Aufruf ableitet (`V = <Call>(...)`)
  **oder** einen Aufruf tätigt, dessen Rückgabewert gar nicht zugewiesen
  wird, **und**
- (b) sie danach ein `return` mit einem Dict/Response-Objekt liefert, dessen
  Erfolgs-Schlüssel (`status`/`sent`/`success`/`ok`) ein **hartkodiertes
  Literal** trägt — ein Ausdruck, der `V` nicht referenziert.

**Ausschluss „Dekorator zählt nicht als Aufruf" (S-7, NEU 2026-07-28):**
`ast.Call`-Knoten im `decorator_list` einer Funktion (z. B.
`@router.get("/health")`) erfüllen Bedingung (a) NICHT — ein Dekorator wird
im UMSCHLIESSENDEN Geltungsbereich ausgewertet (Modul-/Klassenebene), nicht
im Funktionsraum der dekorierten Funktion selbst, und ist syntaktisch KEIN
Aufruf INNERHALB des Funktionskörpers. Ohne diesen Ausschluss würde ein
naiver `ast.walk()` über den kompletten `FunctionDef`-Knoten (der
`decorator_list` als Kind-Feld enthält) `health()` fälschlich zum
Klasse-1-Fund machen, weil `@router.get(...)` ein unzugewiesener Call ist —
AC-16 wäre damit strukturell nicht erfüllbar. Der Scanner darf für Bedingung
(a) ausschließlich `node.body` (plus verschachtelte, nicht-Funktions-Kinder
davon) durchsuchen, nie `node.decorator_list`/`node.args`/`node.returns`.

**Schlüsselwortargumente zählen wie Dict-Schlüssel (S-8, NEU
2026-07-28):** Bedingung (b) prüft nicht nur `ast.Dict`-Literale
(`{"status": "ok"}`), sondern auch Schlüsselwortargumente eines
Konstruktor-/Funktionsaufrufs (`CommandResult(success=True, ...)`,
`NotificationResult(sent=True, ...)`). Ohne diese Gleichstellung wären B12,
B15, B16 und das gesamte B18-Muster in `trip_command_processor.py` (das
ausschließlich über `CommandResult(success=True, ...)`-Konstruktoraufrufe
läuft) nicht erreichbar.

Kernaussage in Worten: *„Du hast einen aussagekräftigen Wert geholt — und
dein Erfolgsstatus hängt am Ende gar nicht von ihm ab."* Ausdrücklich NICHT
geprüft wird, ob eine vorhandene Werteprüfung VOLLSTÄNDIG ist (s. „Known
Limitations").

**Ausschluss „except divergiert":** ein `except`-Handler, der selbst ein
`return` mit einem anderen Wert enthält, schließt den Fund aus. Belegt
korrekt ausgeschlossen: `channel_test_service.py:42`, `forecast_budget.py:102`,
`official_alerts/meteoalarm_budget.py:143`.

Trifft `B1`–`B8`, `B12`, `B15`, `B16`, `B18` (zehn Funktionsschlüssel, s.
Restliste). Trifft `channel_test_service.py`, `forecast_budget.py` und
`meteoalarm_budget.py` NICHT (Gegenprobe AC-5) und `health.py` NICHT (keine
vorherige Ein-/Ausgabe im Funktionsrumpf, s. AC-16 und S-7-Ausschluss).

**Klasse 1c — Erfolgsmarker vor dem Versand (`KIND_PRE_TRY_SUCCESS_MARKER`,
unverändert):** ein Erfolgsmarker in Form einer Sammlung, die vor bzw.
unabhängig vom Ausgang des nachfolgenden risikobehafteten Aufrufs befüllt
wird — der `append`-Aufruf auf die Erfolgs-Sammlung steht als
Geschwister-Anweisung **vor** einem `Try`-Knoten im selben Block (nicht
darin). Trifft `send_official_alert` (B14a) und `_dispatch_alert_message`
(B14c) mit je 3 Kanal-Vorkommen. Belegt verschont: `send_trip_report` und
`send_compare_report`.

**Klasse 2 — teilerfolg-blind (`KIND_PARTIAL_SUCCESS_BLIND`):** Eine
Funktion ist Klasse-2-Fund, wenn

- sie über eine Sammlung iteriert — `for`-Anweisung **oder**
  `sum(<genexp>)`/eine Comprehension —, **und**
- der gezählte Zustand aus einem **undurchsichtigen Aufruf** stammt
  (Methoden-/Funktionsaufruf mit Argumenten, nicht ein einfacher
  Feldzugriff oder Vergleich, s. „Verschont-Ausschlussliste" unten), **und**
- es keine zweite Variable gibt, die **ausschließlich** im Fehlerfall
  erhöht wird und ebenfalls in die Rückgabe fließt.

**Bedingung „bloßer Skalar" ersatzlos gestrichen (S-1, NEU 2026-07-28):**
Version 1.1 verlangte zusätzlich, dass die Funktion „einen bloßen Skalar
zurückgibt (kein Tupel/Paar/Objekt mit zwei Zählern)". Diese Bedingung
widersprach der eigenen Attrappen-Gegenprobe AC-8 direkt: die dortige
Attrappe (`dispatch_all_presets`) gibt syntaktisch ein Tupel `(sent,
failed)` zurück und wäre an der „bloßer Skalar"-Bedingung gescheitert,
BEVOR die eigentlich entscheidende vierte Bedingung (kein echter
Gegenzähler) überhaupt geprüft würde — eine UND-Verknüpfung schlägt fehl,
sobald eine Teilbedingung nicht zutrifft. Die verbleibende Bedingung („kein
Name, der ausschließlich im Fehlerfall erhöht wird und in die Rückgabe
fließt") trägt die Aussage vollständig und korrekt: **der Rückgabetyp
spielt ausdrücklich keine Rolle.** Eine Attrappe, die syntaktisch
`(sent, failed)` liefert, aber `failed` nie in einem Fehlerzweig erhöht,
bleibt Fund — nicht weil sie „kein Skalar" ist (das war nie das
Kriterium), sondern weil ihr der echte Gegenzähler fehlt.

**Verschont-Ausschlussliste für „undurchsichtiger Aufruf" (E6, NEU
2026-07-28):** ein Aufruf zählt NICHT als undurchsichtig, wenn sein Ziel

1. ein Python-Builtin aus der festen Menge `{len, sum, max, min, round,
   abs, getattr, hasattr, isinstance}` ist, **oder**
2. ein Attributzugriff auf das `math`-Modul ist (`math.sin`, `math.cos`,
   `math.radians`, `math.degrees`, `math.atan2`, …).

Begründung aus dem Code (nicht am Schreibtisch entworfen): die drei echten
Klasse-2-Treffer (`trip_alert.check_all_trips`/`check_radar_alerts`,
`compare_alert.check_all_compare_presets`,
`compare_radar_alert.check_all_compare_presets`,
`compare_official_alert.check_all_compare_presets`) zählen ausnahmslos über
einen Aufruf auf ein GESCHÄFTSOBJEKT, das selbst eine Wirkung auslöst oder
externe Daten holt (`self.check_and_send_alerts(...)`,
`self._check_one_preset(...)`, `notification_service.
send_multi_location_deviation_alert(...)`, `radar_svc.get_nowcast(...)`) —
keiner davon ist ein Builtin oder `math.*`. Eine geprüfte Gegenprobe gegen
fünf `weather_metrics.py`-Funktionen (`_compute_temperature`,
`_compute_wind`, `_compute_precipitation`, `_compute_cloud_cover`,
`_compute_wind_direction`) UND gegen `aggregation.py::_circular_mean_deg`
zeigt: ALLE dortigen Zählschleifen/Comprehensions rufen ausschließlich
Builtins (`sum`/`len`/`max`/`min`/`round`/`getattr`) oder `math.*`-Funktionen
auf (`_compute_wind_direction` z. B. `sum(math.sin(math.radians(d)) for d
in dirs)`) — OHNE die Ausschlussliste würden mindestens diese sechs plus
weitere ~9 gleich gebaute `weather_metrics.py`-Aggregationsfunktionen
(insgesamt ≥15, s. „Verschont-Probe" in „Dependencies") fälschlich als
Klasse-2-Fund erkannt. Eine reine „Bindung an `self.`"-Heuristik (ohne
Ausschlussliste, aber IMMERHIN als Idee des Tech Leads geprüft) wurde
VERWORFEN, weil sie zwei echte Treffer verloren hätte
(`notification_service.send_multi_location_deviation_alert(...)` und
`radar_svc.get_nowcast(...)` sind beide Aufrufe auf FREMDE Objekte, nicht
auf `self`).

Kernaussage: *„Erfolg wird über einen undurchsichtigen Aufruf gezählt, aber
es gibt keinen Gegenzähler für Fehlschlag."* Die Fehlerbehandlung muss dafür
**nicht** in der scannenden Funktion sichtbar sein.

Trifft `B9`–`B11`, `B11b`, `B11c`, `B17`, `B19`, `B20`. Belegt verschont:
`dispatch_orchestrator.py`, `official_alerts/base.py:119-146`, sowie
`comparison_scoring.py`, `trip_segments.py`, `warn_egress.py`,
`massif_closure.py`, **und (NEU Version 1.2)** die o. g. sechs
`weather_metrics.py`/`aggregation.py`-Funktionen (Verschont-Probe für die
neue Ausschlussliste).

**Klasse 3 — Heartbeat ohne Wirkung (`KIND_HEARTBEAT_UNWIRED`, unverändert):**
eine Funktion mit `heartbeat`/`betterstack` im Namen, deren Name
**außerhalb** ihrer eigenen Definition und **außerhalb** von `tests/` in der
Scanfläche kein einziges Mal als Aufruf auftaucht. Trifft `B13`
(`_ping_heartbeat_compare` — null Aufrufer).

**Klasse 4 — Aufruf ohne Rückmeldung im Versandkontext
(`KIND_UNACKNOWLEDGED_DISPATCH`, auf den Versandkontext eingeschränkt,
E2 NEU 2026-07-28):** eine Funktion, deren Körper im Wesentlichen ein
`try/except` ist, dessen Handler nur protokolliert (`logger.*`-Aufruf,
keine weitere Wirkung), die dem Aufrufer **kein Erfolgssignal**
zurückgibt (kein `return` mit Wert in irgendeinem Pfad), **UND** die im
eigenen Rumpf selbst einen **Ausgabe-/Versandaufruf** enthält.

**Zusatzbedingung „Versandkontext" (E2):** ein Ausgabe-/Versandaufruf ist
ein Aufruf auf `EmailOutput`/`TelegramOutput`/`SMSOutput` (bzw. deren
`.send(...)`-Methode) ODER ein Aufruf auf einen übergebenen
Sink-Parameter (z. B. `mail_sink(...)`, `telegram_sink(...)`,
`sms_sink(...)`). Diese Zusatzbedingung ist NOTWENDIG, weil die
uneingeschränkte Form (nur „try/except, Logger-only-Handler, kein
Rückgabewert") in der RED-Phase 18 statt 3 Stellen getroffen hat, davon 15
Persistenz-Helfer (`alert_state.save`/`reset`, `weather_snapshot.save`,
`compare_weather_snapshot.save` u. a. — s. „Bewusst nicht erfasst"): ein
`save()`, das jeden Fehler schluckt, ist ein verwandtes, aber ANDERES
Problem — dieses Ticket heißt „Erfolg heißt Wirkung" und zielt auf
Erfolgs*meldungen*, nicht auf Persistenz.

**Ergebnis der Verifikation (E2, gemessen gegen `0627612d`): SECHS statt
drei Treffer.** Die Tech-Lead-Erwartung „Klasse 4 trifft die drei
gelisteten Helfer und nichts sonst" hat sich bei der Messung als zu niedrig
erwiesen: DREI WEITERE Funktionen in `notification_service.py` erfüllen
exakt dieselbe Struktur — Rumpf ist ein reines `try/except`, Handler
protokolliert nur, kein `return` mit Wert, UND ein Aufruf auf
`EmailOutput`/`TelegramOutput`(`.send(...)`) im eigenen Rumpf:

- `_send_telegram_incomplete_hint` (Z. 385) — ruft `TelegramOutput(...).
  send(...)`, keine Rückmeldung an `send_trip_report`.
- `send_command_reply_email` (Z. 1115) — ruft `EmailOutput(...).
  send(...)`, keine Rückmeldung an den Aufrufer (Inbound-Reader).
- `_send_service_error_email` (Z. 1293) — ruft `EmailOutput(...).
  send(...)` nach einer Vorspann-Prüfung (`is_sms_only`), keine
  Rückmeldung.

Diese drei sind vom Detektor STRUKTURELL nicht von den drei bekannten
B14b-Helfern zu unterscheiden — beide Gruppen sind Ein-Funktion-Prüfungen
(Klasse 4 sieht nicht, was der Aufrufer mit einem etwaigen Rückgabewert
täte, s. „Known Limitations"), und beide rufen einen Kanal-Ausgang auf. Eine
künstliche Verengung, die genau diese drei ausschließt, ohne die
Grundmechanik zu ändern, wäre Signatur-Verengung zur Zahlenkosmetik (in
CLAUDE.md ausdrücklich verboten: „Test-Schwellen NIEMALS anheben/Neue Funde
werden NICHT durch Verengung der Signatur wegdefiniert"). Diese drei
Funktionen werden deshalb als **B21** in die Restliste aufgenommen statt
wegdefiniert zu werden (s. „Geklärte Punkte" 9).

**Ausschluss „nacktes `return` ist kein Erfolgssignal" (S-9, NEU
2026-07-28):** ein wertloses `return` (`ast.Return(value=None)`, keine
Konstante, kein Ausdruck) zählt NICHT als Rückmeldung — es liefert `None`
wie das Funktionsende auch. Ohne diesen Ausschluss würde
`_dispatch_compare_official_telegram` (Z. 916, `return` im
Kurzform-Zweig) fälschlich als „hat eine Rückmeldung" durchgehen und ein
Drittel der B14b-Erwartung verschwände. Ein `-> None`-Annotation ist ein
zusätzliches Indiz, aber nicht erforderlich (nicht jede Fundstelle ist
annotiert).

Trifft (nach E2-Einschränkung, verifiziert gegen `0627612d`): B14b (drei
Helfer: `_dispatch_compare_official_email/_telegram/_sms`) UND B21 (drei
weitere Helfer: `_send_telegram_incomplete_hint`,
`send_command_reply_email`, `_send_service_error_email`) — sechs
Funktionsschlüssel insgesamt, alle in `notification_service.py`.

### Ausnahmeliste — Begründung als Datenstruktur, nicht als Kommentar

`INTENTIONAL_CONSTANT_SUCCESS: dict[str, str]` (Schlüssel `pfad:zeile`, Wert
= fachliche Begründung), analog zu `KNOWN_VIOLATIONS`, aber semantisch
umgekehrt: ein Eintrag hier bedeutet „bewusst erlaubt", nicht „Reparatur
ausstehend". Ein Fund, der auf dieser Liste steht, zählt NICHT als
`KNOWN_VIOLATIONS`-Eintrag und macht die Ratsche nicht rot.

Einziger bekannter Eintrag: `api/routers/webhook.py:72`
(`telegram_webhook`) — Begründungstext MUSS wörtlich die Unterscheidung
tragen: „Protokoll-Empfangsbestätigung an Telegram, kein fachlicher
Erfolgsstatus — verhindert Retry-Sturm (dokumentiert im Docstring, Z.
54f.)". `health.py` braucht KEINEN Eintrag — die Signatur trifft dort gar
nicht zu (kein Aufruf im Funktionsrumpf; der Dekorator zählt nicht, s.
S-7).

## Restliste B1–B21 (verifiziert gegen `0627612d`, 1:1 in `KNOWN_VIOLATIONS`
zu übernehmen)

B1–B17 unverändert aus Version 1.1 (s. Changelog dort für die Herleitung).
B18–B21 sind NEU in Version 1.2 (Tech-Lead-Entscheidung E2–E4, plus B21 als
eigene Verifikations-Ergänzung).

| # | Datei:Zeile | Funktion | Klasse | Befund |
|---|---|---|---|---|
| B1 | `api/routers/scheduler.py:217` | `send_test_trip_report` | 1 | Der #1403-Fall. `"no_channels"` wird vom Router nicht abgefangen — fällt durch bis `"sent": True` |
| B2 | `api/routers/scheduler.py:54` | `trigger_alert_checks` | 1 | `status: "ok"` fest; `count` echt, fließt nicht in den Status |
| B3 | `api/routers/scheduler.py:64` | `trigger_compare_alert_checks` | 1 | dito |
| B4 | `api/routers/scheduler.py:74` | `trigger_radar_alert_checks` | 1 | dito |
| B5 | `api/routers/scheduler.py:84` | `trigger_compare_radar_alert_checks` | 1 | dito |
| B6 | `api/routers/scheduler.py:94` | `trigger_compare_official_alert_checks` | 1 | dito |
| B7 | `api/routers/scheduler.py:111` | `trigger_inbound` | 1 | dito |
| B8 | `api/routers/scheduler.py:126` | `trigger_inbound_telegram` | 1 | dito (Feld heißt `"processed"`) |
| B9 | `src/services/trip_alert.py:275` | `check_all_trips` | 2 | try/except je Trip, nur `alerts_sent` hoch, `return alerts_sent` (int) |
| B10 | `src/services/trip_alert.py:606` | `check_radar_alerts` | 2 | analoges Muster über `radar_svc.get_nowcast(...)`, `return sent` (int) |
| B11 | `src/services/compare_alert.py:80` | `check_all_compare_presets` | 2 | Zähler über `notification_service.send_multi_location_deviation_alert(...).sent`, kein Fehlerzähler |
| B11b | `src/services/compare_radar_alert.py:66` | `CompareRadarAlertService.check_all_compare_presets` | 2 | Gleiches Muster über `self._check_one_preset(...)` |
| B11c | `src/services/compare_official_alert.py:72` | `CompareOfficialAlertService.check_all_compare_presets` | 2 | `sum(1 for preset in presets if self._check_one_preset(...))` — kein Fehlerzähler, kein `try/except` im Rumpf |
| B12 | `src/services/scheduler_dispatch_service.py:443` | `send_compare_preset` | 1 | `top_ort, actual_empfaenger` zugewiesen, aber `"status"` fest `"ok"` |
| B13 | `api/routers/scheduler.py:147` | `_ping_heartbeat_compare` | 3 | Toter Code. Kein Aufrufer außerhalb der Definition; `trigger_compare_presets_daily` ruft sie nicht auf |
| B14a | `src/services/notification_service.py:660` | `send_official_alert` | 1c | `sent_channels.append("email")` (analog telegram Z. 672, sms Z. 694) vor dem `try` — 3 Kanal-Vorkommen |
| B14b (email) | `src/services/notification_service.py:878` | `_dispatch_compare_official_email` | 4 | try/except, Handler nur `logger.error`, kein `return`-Wert, ruft `EmailOutput(...).send(...)` |
| B14b (telegram) | `src/services/notification_service.py:891` | `_dispatch_compare_official_telegram` | 4 | dito, Telegram-Kanal; nacktes `return` (Z. 916) zählt NICHT als Rückmeldung (S-9) |
| B14b (sms) | `src/services/notification_service.py:929` | `_dispatch_compare_official_sms` | 4 | dito, SMS-Kanal |
| B14c | `src/services/notification_service.py:1066` | `_dispatch_alert_message` | 1c | dito wie B14a, 3 Kanal-Vorkommen (Z. 1066/1082/1103) |
| B15 | `src/services/trip_command_processor.py:888` | `_trigger_report` | 1 | `service.send_test_report(trip, report_type)` unzugewiesen, danach bedingungslos `return CommandResult(success=True, ...)` |
| B16 | `src/services/trip_command_processor.py:526` | `_trigger_on_demand` | 1 | `outcome` geprüft, Bestätigungstext variiert korrekt, `success` nicht |
| B17 | `src/services/trip_report_scheduler.py:240` | `send_reports` | 2 | Toter Code. `sent_count` ohne Gegenzähler, `return sent_count` (int) |
| **B18** | `src/services/trip_command_processor.py` (zehn Funktionen, s. u.) | `_handle_query` (4×) / `_handle_drilldown` / `_handle_hours_drilldown` / `_apply_ruhetag` / `_show_status` / `_apply_pause` / `_apply_skip` / `_show_now` / `_cancel_trip` / `_resume_trip` | 1 | **NEU (E3, Tech-Lead-Entscheidung 2026-07-28).** Dateiweites Muster, dieselbe Mechanik wie B15/B16 — s. „B18-Detailtabelle" unten. Reparatur sinnvollerweise am Stück (eine Entscheidung über `CommandResult.success`, nicht zehn Einzelfixes) |
| **B19** | `src/services/inbound_email_reader.py:77` | `poll_and_process` | 2 | **NEU (E4).** `for uid in uids: ... processed += self._process_single(...)`, `except Exception: logger.error(...)` (kein Gegenzähler), `return processed`. Bislang fälschlich als „kein Fund" geführt („zählt nur tatsächlich Verarbeitetes" ist fachlich richtig, aber KEIN strukturelles Ausschlusskriterium) |
| **B20** | `src/services/inbound_telegram_reader.py:107` | `poll_and_process` | 2 | **NEU (E4).** Identisches Muster über `self._process_update(...)`, `return processed` |
| **B21** | `src/services/notification_service.py:385/1115/1293` | `_send_telegram_incomplete_hint` / `send_command_reply_email` / `_send_service_error_email` | 4 | **NEU (eigene Verifikation der E2-Einschränkung).** Erfüllen nach der Versandkontext-Einschränkung dieselbe Klasse-4-Signatur wie B14b — try/except, Logger-only-Handler, kein `return`-Wert, Aufruf auf `EmailOutput`/`TelegramOutput`(`.send(...)`) im Rumpf |

**B18-Detailtabelle** (Funktionsschlüssel, Zeile des jeweils
hartkodierten `success=True`-`return`, vorausgehender Aufruf):

| Funktion | Zeile(n) `return CommandResult(success=True, ...)` | Vorausgehender Aufruf/Ableitung |
|---|---|---|
| `_handle_query` | 470, 479, 487, 496 (vier unabhängige Zweige) | `body = self._fmt_glance(...)` / `self._fmt_gewitter(...)` / `self._fmt_timeline(...)` (je Zweig) |
| `_handle_drilldown` | 595 | `res = WeatherExtractor(user_id).drilldown(...)` |
| `_handle_hours_drilldown` | 677 | `r_temp = ex.drilldown(...)` (plus drei weitere) |
| `_apply_ruhetag` | 866 | `save_trip(new_trip, user_id)` (unzugewiesen) |
| `_show_status` | 950 | `today = date.today()` (trivialer Aufruf — s. „Offene Punkte" 3) |
| `_apply_pause` | 1047 | `save_trip(new_trip, user_id)` (unzugewiesen) |
| `_apply_skip` | 1070 | `save_trip(new_trip, user_id)` (unzugewiesen) |
| `_show_now` | 1120 | `result = svc.get_nowcast(...)`, `body = svc.format_now_text(...)` |
| `_cancel_trip` | 1135 | `save_trip(new_trip, user_id)` (bedingt, unzugewiesen) |
| `_resume_trip` | 1149 | `save_trip(new_trip, user_id)` (bedingt, unzugewiesen) |

Zehn Funktionsschlüssel, 13 Treffer (`_handle_query` vierfach, die übrigen
neun je einfach) — s. AC-1-Tabelle.

**Mindest-Trefferzahlen für AC-1** (`SPEC_LISTED_FINDINGS`, Format
`"pfad::funktion" -> Mindestzahl`, gezählt über das rohe, zeilenscharfe
Scan-Ergebnis):

| Funktionsschlüssel | Mindestzahl |
|---|---|
| `api/routers/scheduler.py::send_test_trip_report` | 1 |
| `api/routers/scheduler.py::trigger_alert_checks` | 1 |
| `api/routers/scheduler.py::trigger_compare_alert_checks` | 1 |
| `api/routers/scheduler.py::trigger_radar_alert_checks` | 1 |
| `api/routers/scheduler.py::trigger_compare_radar_alert_checks` | 1 |
| `api/routers/scheduler.py::trigger_compare_official_alert_checks` | 1 |
| `api/routers/scheduler.py::trigger_inbound` | 1 |
| `api/routers/scheduler.py::trigger_inbound_telegram` | 1 |
| `src/services/trip_alert.py::check_all_trips` | 1 |
| `src/services/trip_alert.py::check_radar_alerts` | 1 |
| `src/services/compare_alert.py::check_all_compare_presets` | 1 |
| `src/services/compare_radar_alert.py::check_all_compare_presets` | 1 |
| `src/services/compare_official_alert.py::check_all_compare_presets` | 1 |
| `src/services/scheduler_dispatch_service.py::send_compare_preset` | 1 |
| `api/routers/scheduler.py::_ping_heartbeat_compare` | 1 |
| `src/services/notification_service.py::send_official_alert` | **4** |
| `src/services/notification_service.py::_dispatch_alert_message` | **4** |
| `src/services/notification_service.py::_dispatch_compare_official_email` | 1 |
| `src/services/notification_service.py::_dispatch_compare_official_telegram` | 1 |
| `src/services/notification_service.py::_dispatch_compare_official_sms` | 1 |
| `src/services/trip_command_processor.py::_trigger_report` | 1 |
| `src/services/trip_command_processor.py::_trigger_on_demand` | 1 |
| `src/services/trip_report_scheduler.py::send_reports` | 1 |
| `src/services/trip_command_processor.py::_handle_query` | **4** |
| `src/services/trip_command_processor.py::_handle_drilldown` | 1 |
| `src/services/trip_command_processor.py::_handle_hours_drilldown` | 1 |
| `src/services/trip_command_processor.py::_apply_ruhetag` | 1 |
| `src/services/trip_command_processor.py::_show_status` | 1 |
| `src/services/trip_command_processor.py::_apply_pause` | 1 |
| `src/services/trip_command_processor.py::_apply_skip` | 1 |
| `src/services/trip_command_processor.py::_show_now` | 1 |
| `src/services/trip_command_processor.py::_cancel_trip` | 1 |
| `src/services/trip_command_processor.py::_resume_trip` | 1 |
| `src/services/inbound_email_reader.py::poll_and_process` | 1 |
| `src/services/inbound_telegram_reader.py::poll_and_process` | 1 |
| `src/services/notification_service.py::_send_telegram_incomplete_hint` | 1 |
| `src/services/notification_service.py::send_command_reply_email` | 1 |
| `src/services/notification_service.py::_send_service_error_email` | 1 |

**Summe der Mindest-Treffer = 45**, verteilt über **38** Funktionsschlüssel
(23 aus Version 1.1 + 10 aus B18 + 2 aus B19/B20 + 3 aus B21), die **23**
Ticket-Fundstellen abbilden (19 aus Version 1.1 + B18 als ein Punkt + B19
und B20 als zwei Punkte + B21 als ein gebündelter Punkt). Rechnung
gegenüber Version 1.1 (23 Schlüssel, Summe 27): +10 Schlüssel/+13 Treffer
(B18) +2/+2 (B19/B20) +3/+3 (B21) = +15 Schlüssel/+18 Treffer → 38/45.

Diese Tabelle stammt aus eigener Zeilen-für-Zeilen-Verifikation gegen
`0627612d` (nicht nur aus der Tech-Lead-Nachricht abgeschrieben) — alle
B18–B21-Fundorte wurden per `grep -n` und `Read` einzeln nachgelesen.

### Bewusst nicht erfasst (Persistenz-Helfer, E2)

Diese Funktionen erfüllen die UNEINGESCHRÄNKTE Klasse-4-Form (Rumpf im
Wesentlichen try/except, Handler protokolliert nur, kein `return`-Wert),
aber OHNE Aufruf auf einen Kanal-Ausgang — E2 schließt sie deshalb
strukturell aus. Konkret verifiziert:

- `src/services/alert_state.py::save` (Z. 60), `::reset` (Z. 68)
- `src/services/weather_snapshot.py::save` (Z. 61)
- `src/services/compare_weather_snapshot.py::save` (Z. 52)

**Ehrlicher Hinweis zur Tech-Lead-Schätzung „15 Persistenz-Helfer":** die
o. g. vier Funktionen sind mit vertretbarem Aufwand eindeutig als
„Rumpf ist NUR ein try/except" verifizierbar. Weitere Kandidaten
(`weather_snapshot.py::save_dated`, `scheduler_dispatch_service.py::
save_compare_preset_status/save_compare_preset_pause`,
`weather_snapshot.py::_prune_dated_snapshots`) haben zusätzliche
Kontrollstruktur (mehrere `try`-Blöcke, Vorspann-Guards mit `return`,
Schleifen) und lassen sich ohne eine im GREEN tatsächlich implementierte
Schwelle für „im Wesentlichen try/except" nicht eindeutig einordnen. Für
das Ergebnis dieser Spec ist das FOLGENLOS (E2 schließt sie ohnehin aus,
weil keiner von ihnen einen Kanal-Ausgang ruft) — die genaue Zahl „15" ist
daher NICHT load-bearing für eine AC und wird hier nicht als verifizierte
Tatsache behauptet. Der zugrunde liegende, aber andere Fund (Persistenz-
Fehler werden geschluckt) bleibt als Sammel-Eintrag in #1199 vermerkt,
sobald S4 dort ansetzt.

### Ausnahmekandidaten (kein Fund, mit Begründung — s. „Ausnahmeliste" oben)

| Stelle | Begründung | Mechanismus |
|---|---|---|
| `api/routers/health.py:9` | Reine Lebendmeldung, kein Aufruf im Funktionsrumpf (Dekorator zählt nicht, S-7) | Strukturell ausgeschlossen — AC-16 |
| `api/routers/webhook.py:72` | Protokoll-Empfangsbestätigung an Telegram, kein fachlicher Erfolgsstatus (verhindert Retry-Sturm) | Explizit in `INTENTIONAL_CONSTANT_SUCCESS` mit Begründungstext — AC-14 |

**Korrektur gegenüber Version 1.1 (E4):** `inbound_email_reader.py:50/77`
und `inbound_telegram_reader.py:91/107` waren hier fälschlich als „kein
Fund, bereits erfolgsbereinigt" geführt. Das Argument „`processed` zählt
nur tatsächlich Verarbeitetes" ist FACHLICH richtig, aber KEIN
strukturelles Ausschlusskriterium — die Signatur von Klasse 2 fragt nicht
„ist der Zähler fachlich korrekt", sondern „gibt es einen Gegenzähler für
den Fehlerfall, der in dieselbe Rückgabe fließt". Beide Funktionen haben
keinen — sie sind jetzt B19/B20 in der Restliste.

## Aus dem Scope ausgeschlossen

- **S3** (Mengenerhalt-Nachweise über die gerenderte Ausgabe) und **S4**
  (Reparatur der Restliste B1–B21) — eigene Scheiben, PO-Entscheidung
  2026-07-28. Diese Einheit ändert keinen Produktivcode.
- **Go-Code (`internal/`)** — ein Python-`ast`-Scan erreicht diesen Baum
  strukturell nicht (AC-15).
- **Issue #1407** (unverdrahteter Compare-Heartbeat, `B13`) — der Wächter
  MELDET den Fund weiterhin, die Reparatur läuft ausschließlich in #1407.
- **Der genaue Fund-Status der Persistenz-Helfer** (`save()`-Funktionen
  in `alert_state.py`/`weather_snapshot.py`/`compare_weather_snapshot.py`
  u. a., s. „Bewusst nicht erfasst") — verwandtes, aber ANDERES Problem als
  „Erfolg heißt Wirkung"; weiterverfolgt als Sammel-Eintrag in #1199, nicht
  Teil dieser Restliste oder ihrer Reparatur.

## Expected Behavior

- **Input:** der aktuelle Stand von `api/routers/**` und `src/services/**`
  beim Testlauf.
- **Output:** `pytest`-Grün/Rot. Rot mit `Code reference: pfad:zeile` bei
  jedem neuen, unlisteten Fund, jedem veralteten Restlisten-Eintrag oder
  jedem unbegründeten Ausnahme-Eintrag.
- **Side effects:** keine — reiner Lesezugriff auf den Quellbaum.

## Acceptance Criteria

- **AC-1:** Given die in dieser Spec namentlich gelisteten Fundstellen B1–B21 / When der Wächter über die Scanfläche läuft / Then schlägt er in jeder der 38 zugehörigen Funktionen mindestens so oft an wie in der Mindestzahl-Tabelle festgelegt, Summe 45.
  - Test: `test_scanner_finds_every_spec_listed_finding()`.

- **AC-2:** Given ein neuer, bislang unbekannter Fund mit einer der fünf Signaturen irgendwo in der Scanfläche / When der Wächter läuft / Then schlägt der Test fehl und benennt Datei:Zeile.
  - Test: `test_no_unlisted_success_status_findings()`.

- **AC-3:** Given ein Eintrag in `KNOWN_VIOLATIONS`, den der Scanner am aktuellen Code nicht mehr findet / When der Wächter läuft / Then schlägt der Test mit „veraltet — aus der Liste entfernen" fehl.
  - Test: `test_known_violations_only_shrink()`.

- **AC-4:** Given eine synthetische Datei mit dem Muster „eine Variable wird aus einem Aufruf abgeleitet (oder ein Aufruf bleibt unzugewiesen), danach folgt ein Rückgabe-Dict/-Konstruktoraufruf mit festem `status`/`success`, das diese Variable nicht referenziert" / When der Scanner sie einliest / Then wird die Stelle als Klasse-1-Fund erkannt.
  - Test: `test_scanner_detects_constant_success_from_call_in_synthetic_file(tmp_path)`.

- **AC-5:** Given eine synthetische Datei nach dem „except divergiert"-Muster / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_diverging_except_return_in_synthetic_file(tmp_path)`.

- **AC-6:** Given eine synthetische Datei nach dem `B14a`/`c`-Muster (Erfolgsmarker VOR dem riskanten Aufruf) / When der Scanner sie einliest / Then wird die Stelle als Klasse-1c-Fund erkannt; die Gegenprobe (Marker NACH dem Aufruf) meldet keinen Fund.
  - Test: `test_scanner_detects_pre_try_success_marker_in_synthetic_file(tmp_path)`.

- **AC-7:** Given eine synthetische Datei mit einer Zählschleife, deren Funktion nur einen Erfolgszähler aus einem undurchsichtigen Aufruf führt und keinen Namen besitzt, der ausschließlich im Fehlerzweig erhöht wird und in den `return` fließt / When der Scanner sie einliest / Then wird die Stelle als Klasse-2-Fund erkannt — UNABHÄNGIG davon, ob im Rumpf ein `try/except` steht.
  - Test: `test_scanner_detects_partial_success_blind_loop_in_synthetic_file(tmp_path)`.

- **AC-8:** Given eine synthetische Attrappen-Funktion, die syntaktisch ein Tupel `(sent, failed)` zurückgibt, aber `failed` niemals in einem Fehlerzweig erhöht / When der Scanner sie einliest / Then wird die Stelle TROTZDEM als Klasse-2-Fund erkannt (Bedingung „bloßer Skalar" existiert seit Version 1.2 nicht mehr — der Rückgabetyp spielt keine Rolle, s. S-1).
  - Test: `test_scanner_detects_tuple_shaped_decoy_without_real_failure_counter(tmp_path)`.

- **AC-8b (NEU, E6):** Given fünf synthetische Nachbauten der `weather_metrics.py`-Aggregationsfunktionen (Zählschleife/Comprehension, deren Aufruf AUSSCHLIESSLICH ein Builtin aus `{len, sum, max, min, round, abs, getattr, hasattr, isinstance}` oder eine `math.*`-Funktion ist) / When der Scanner sie einliest / Then wird KEIN Fund gemeldet — die Verschont-Ausschlussliste greift.
  - Test: `test_scanner_ignores_pure_computation_calls_in_synthetic_file(tmp_path)`.

- **AC-9:** Given eine synthetische Datei nach der Hausnorm (`(sent, failed)`, `failed` im Fehlerzweig erhöht) / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_house_norm_sent_failed_tuple_in_synthetic_file(tmp_path)`.

- **AC-10:** Given eine synthetische Datei mit einer Funktion, deren Name `heartbeat`/`betterstack` enthält und die in der gesamten übrigen Scanfläche kein einziges Mal als Aufruf auftaucht / When der Scanner sie einliest / Then wird die Stelle als Klasse-3-Fund erkannt.
  - Test: `test_scanner_detects_unwired_heartbeat_function_in_synthetic_file(tmp_path)`.

- **AC-11:** Given dieselbe synthetische Heartbeat-Funktion, diesmal mit einem echten Aufruf hinter einer Erfolgsbedingung / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_wired_heartbeat_call_in_synthetic_file(tmp_path)`.

- **AC-12:** Given eine synthetische Datei nach dem `B14b`/`B21`-Muster (try/except mit Logger-only-Handler, kein `return`-Wert, Aufruf auf `EmailOutput`/`TelegramOutput`(`.send(...)`) im Rumpf) / When der Scanner sie einliest / Then wird die Stelle als Klasse-4-Fund erkannt. Ein nacktes `return` in einem der Zweige (S-9) ändert daran nichts.
  - Test: `test_scanner_detects_unacknowledged_dispatch_in_synthetic_file(tmp_path)`.

- **AC-13:** Given dieselbe Struktur, diesmal mit einem `return`-Statement mit echtem Wert in mindestens einem Pfad / When der Scanner sie einliest / Then wird kein Fund gemeldet.
  - Test: `test_scanner_ignores_acknowledged_dispatch_in_synthetic_file(tmp_path)`.

- **AC-13b (NEU, E2):** Given eine synthetische Datei nach dem Persistenz-Muster (try/except, Logger-only-Handler, kein `return`-Wert, aber OHNE Aufruf auf `EmailOutput`/`TelegramOutput`/`SMSOutput`/Sink-Parameter — Nachbau von `alert_state.py::save`) / When der Scanner sie einliest / Then wird KEIN Klasse-4-Fund gemeldet — die Versandkontext-Zusatzbedingung (E2) greift.
  - Test: `test_scanner_ignores_persistence_only_swallow_in_synthetic_file(tmp_path)`.

- **AC-14:** Given der Ausnahme-Eintrag für `api/routers/webhook.py:72` in `INTENTIONAL_CONSTANT_SUCCESS` / When der Wächter läuft / Then zählt die Stelle NICHT als `KNOWN_VIOLATIONS`-Fund, UND ein zusätzlicher Test stellt sicher, dass jeder Eintrag eine nichtleere Begründung trägt.
  - Test: `test_webhook_ack_is_documented_exception_not_silent_pass()` und `test_intentional_exceptions_carry_nonempty_justification()`.

- **AC-15:** Given der Go-Code unter `internal/` / When die Scanfläche des Wächters bestimmt wird / Then ist `internal/` nicht Teil der gescannten Dateien.
  - Test: `test_scan_scope_excludes_go_internal_tree()`.

- **AC-16:** Given `api/routers/health.py` (reine Lebendmeldung ohne jede vorgelagerte Aktion) / When der Wächter über die Scanfläche läuft / Then wird dafür kein Fund gemeldet, weil die Klasse-1-Signatur strukturell nicht zutrifft (kein Aufruf im Funktionsrumpf; der Dekorator zählt nicht, S-7) — ohne dass die Datei dafür auf eine Ausnahmeliste muss.
  - Test: `test_scanner_ignores_pure_liveness_endpoint()`.

- **AC-16b (NEU, S-7):** Given eine synthetische Funktion mit einem Dekorator, der selbst ein `ast.Call` ist (`@router.get("/health")`), aber ohne jeden Aufruf im eigenen Funktionsrumpf / When der Scanner sie einliest / Then wird KEIN Klasse-1-Fund gemeldet — der Dekorator erfüllt Bedingung (a) nicht.
  - Test: bereits Teil von `test_scanner_ignores_pure_liveness_endpoint()` (synthetischer Zwilling); kein zusätzlicher Test nötig, da AC-16 den Dekorator-Fall bereits mit abdeckt.

- **AC-17 (NEU, E3/B18):** Given die zehn in `trip_command_processor.py` gelisteten Funktionen (B18) / When der Wächter über die Scanfläche läuft / Then schlägt er in `_handle_query` mindestens 4× und in den übrigen neun je mindestens 1× an (Teil der AC-1-Gesamtprüfung, hier als eigene AC benannt, weil B18 ein dateiweites Muster ist, dessen Einzelnachweis sonst in der Summenzahl untergehen würde).
  - Test: Teil von `test_scanner_finds_every_spec_listed_finding()` (AC-1); keine separate Testfunktion.

- **AC-18 (NEU, E4/B19+B20):** Given `inbound_email_reader.py::poll_and_process` und `inbound_telegram_reader.py::poll_and_process` / When der Wächter läuft / Then werden beide als Klasse-2-Fund erkannt (nicht mehr als „kein Fund" behandelt).
  - Test: Teil von `test_scanner_finds_every_spec_listed_finding()` (AC-1); die frühere Behauptung „kein Fund" ist entfallen (kein eigener Negativ-Test mehr nötig).

## Known Limitations

- **Ehrliche Grenze — Vollständigkeit einer Werteprüfung ist mit
  Ein-Funktions-Analyse nicht entscheidbar.**
- **Ehrliche Grenze — Struktur, nicht Fachlichkeit:** `failed > 5` statt
  `failed > 0` bleibt für den Wächter unsichtbar.
- **Go-Code bleibt ungeprüft.**
- **Heartbeat-Erkennung ist eine Aufrufer-Suche, keine Ausführungsanalyse.**
- **Attrappen-Gegenprobe deckt nur die naheliegendste Umgehung ab.**
- **Klasse 4 prüft nur die scannende Funktion selbst, keine transitive
  Rückmeldungskette** — genau deshalb sind B14b und B21 strukturell nicht
  voneinander zu unterscheiden (beide „Ein-Funktion-Ansicht: try/except,
  Logger-only, kein Rückgabewert, Kanal-Aufruf im Rumpf"); die
  Versandkontext-Bedingung (E2) grenzt gegen Persistenz ab, nicht gegen
  weitere Versand-Fundstellen — es kann jederzeit noch mehr als sechs
  geben, sobald neuer Code entsteht (AC-2 fängt das ab).
- **Klasse-1-Signatur ist rein syntaktisch, nicht risikobewusst (NEU,
  Version 1.2, s. „Offene Punkte" 3):** Bedingung (a) unterscheidet nicht
  zwischen einem „riskanten" Aufruf (z. B. ein Versand, eine
  Netzwerkanfrage) und einem trivialen, deterministischen Aufruf (z. B.
  `date.today()`). `_show_status`/`_show_now` (B18) matchen über
  `date.today()`, obwohl dieser Aufruf nie fehlschlagen kann — die
  Restliste nimmt sie trotzdem auf (Arbeitsvorrat, keine Vorab-Filterung,
  analog B15–B17 in Version 1.1), aber diese Grenze der Signatur ist hier
  ausdrücklich benannt, damit sie nicht als Bug am Scanner missverstanden
  wird.
- **Keine Mehrfunktions-Datenflüsse.**

## Geklärte Punkte (aus dem Kontextdokument + Tech-Lead-Entscheidungen
2026-07-28, Version 1.1 UND 1.2)

1.–8. unverändert aus Version 1.1 (Klasse 2/3 getrennt, Ausnahmeliste als
Datenstruktur, `webhook.py` explizit dokumentiert, B13/#1407-Trennung,
Klasse-1-Datenfluss-Signatur, Klasse-2-Verallgemeinerung, B14b-Umhängung,
B15–B17-Aufnahme trotz totem Code).

9. **Klasse-2-Bedingung „bloßer Skalar" gestrichen (E1/S-1, NEU
   Version 1.2).** Sie widersprach der eigenen Attrappen-Gegenprobe AC-8
   (Tupel-Rückgabe hätte die UND-Verknüpfung vorzeitig scheitern lassen).
   Die verbleibende Bedingung „kein echter Gegenzähler" trägt die Aussage
   vollständig — der Rückgabetyp spielt keine Rolle.
10. **Klasse 4 auf den Versandkontext eingeschränkt (E2, NEU
    Version 1.2) — UND als Ergebnis SECHS statt drei Treffer.** Die
    Zusatzbedingung „Aufruf auf einen Kanal-Ausgang im Rumpf" schließt die
    Persistenz-Helfer korrekt aus, hat aber bei der Verifikation zusätzlich
    zu den drei erwarteten B14b-Helfern drei WEITERE echte Treffer
    (B21) offengelegt, die vom Detektor strukturell nicht von B14b zu
    unterscheiden sind. Eine engere Fassung, die genau diese drei
    ausschließt, wäre Signatur-Verengung zur Zahlenkosmetik und wurde
    deshalb verworfen — B21 kommt stattdessen in die Restliste.
11. **Dateiweites Muster in `trip_command_processor.py` (E3/B18, NEU
    Version 1.2).** Die ~15 vermuteten weiteren Treffer sind bei
    Verifikation zehn Funktionsschlüssel mit 13 Treffern (nicht 15 Zeilen)
    — `_handle_query` trägt allein vier der 13 Treffer (vier unabhängige
    `CommandResult(success=True, ...)`-Zweige nach je einer Ableitung aus
    einem Renderer-Aufruf). Dieselbe Mechanik wie B15/B16, keine
    Fehlalarme. Reparatur (S4) sinnvollerweise am Stück: eine Entscheidung
    darüber, was `CommandResult.success` bedeuten soll (Antwort erfolgreich
    verfasst vs. zugrundeliegende Aktion erfolgreich), statt zehn
    Einzelfixes.
12. **Inbound-Reader sind Klasse-2-, nicht „kein"-Fund (E4/B19+B20, NEU
    Version 1.2).** Die Version-1.1-Begründung „`processed` zählt nur
    tatsächlich Verarbeitetes" ist fachlich richtig, aber kein
    strukturelles Ausschlusskriterium für Klasse 2 — beiden
    `poll_and_process`-Funktionen fehlt der Gegenzähler für den
    Fehlerfall exakt wie B9–B11c.
13. **„Undurchsichtiger Aufruf" braucht eine Verschont-Ausschlussliste
    (E6, NEU Version 1.2).** Eine reine `self.`-Heuristik (Tech-Lead-
    Vorschlag als Ausgangspunkt) wurde geprüft und verworfen — sie hätte
    zwei echte Treffer verloren (`notification_service.
    send_multi_location_deviation_alert(...)`, `radar_svc.get_nowcast(...)`,
    beide Aufrufe auf FREMDE Objekte). Die tragfähige Unterscheidung ist
    stattdessen eine feste Ausschlussliste für Python-Builtins
    (`len`/`sum`/`max`/`min`/`round`/`abs`/`getattr`/`hasattr`/`isinstance`)
    und `math.*`-Aufrufe — verifiziert gegen sechs echte
    `weather_metrics.py`/`aggregation.py`-Funktionen, die ausschließlich
    solche Aufrufe enthalten.
14. **Dekoratoren zählen nicht als Aufruf im Funktionsrumpf (S-7, NEU
    Version 1.2).** Ohne diesen Ausschluss würde ein naiver AST-Walk über
    den kompletten `FunctionDef`-Knoten `health()` fälschlich zum
    Klasse-1-Fund machen (der Dekorator ist ein unzugewiesener Call).
15. **Schlüsselwortargumente zählen wie Dict-Schlüssel (S-8, NEU
    Version 1.2).** Ohne diese Gleichstellung wären B12, B15, B16 und das
    gesamte B18-Muster (ausschließlich Konstruktoraufrufe) nicht
    erreichbar.
16. **Nacktes `return` ist kein Erfolgssignal (S-9, NEU Version 1.2).**
    Sonst verlöre Klasse 4 ein Drittel der B14b-Erwartung
    (`_dispatch_compare_official_telegram`, Kurzform-Zweig).
17. **Mehrfachtreffer auf derselben `pfad:zeile` werden nie überschrieben
    (S-6, NEU Version 1.2).** Der ursprünglich gemeldete Kollisionsfall
    (`_ping_heartbeat_compare`, Klasse 3 + Klasse 4) entfällt zwar durch
    die E2-Einschränkung, die Merge-Regel bleibt aber als generelle
    Absicherung Teil der Spec.

## Offene Punkte

1. **LoC-Limit-Freigabe steht erneut aus** — vor der Implementierungsphase
   beim PO einzuholen (2800 statt 2200).
2. **Exakte Trefferzahl für B14a/c (3 vs. 1 je Funktion)** unverändert aus
   Version 1.1 — hängt von der konkreten Scanner-Implementierung ab.
3. **Klasse-1-Signatur ist risiko-blind (NEU, Version 1.2).** `date.today()`
   und ähnliche triviale, garantiert erfolgreiche Aufrufe erfüllen
   Bedingung (a) genauso wie ein echter Versand-/Netzwerkaufruf. Das ist
   keine Fehlfunktion (die Restliste ist Arbeitsvorrat, keine
   Vorab-Bewertung, s. „Geklärte Punkte" aus Version 1.1), aber eine
   bewusst nicht geschärfte Grenze — sollte S4 zeigen, dass zu viele
   „triviale" Klasse-1-Funde die Reparatur-Priorisierung erschweren, ist
   eine Verfeinerung (z. B. eine Ausschlussliste analog E6 für
   `date.today`/`datetime.now`) ein Kandidat für eine spätere Scheibe —
   NICHT rückwirkend in dieser Spec, um keine Signatur-Verengung ohne
   PO-Entscheidung einzuführen.
4. **Persistenz-Helfer-Zahl „15" nicht abschließend verifiziert (NEU,
   Version 1.2, s. „Bewusst nicht erfasst").** Vier Funktionen sind
   eindeutig verifiziert; weitere Kandidaten hängen von einer im GREEN
   erst zu implementierenden Schwelle für „im Wesentlichen try/except" ab.
   Folgenlos für diese Spec (E2 schließt sie über das fehlende
   Versandkontext-Kriterium ohnehin aus), aber als Prüfpunkt für S4/#1199
   festgehalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reiner Test-Wächter ohne Produktivcode-Änderung und ohne
  Auswirkung auf Kanäle, Provider, Datenmodell/Persistenz, Auth oder
  Editor-Paradigma.

## Changelog

- 2026-07-28: Initial spec erstellt — Issue #1405, Hälfte B.
- 2026-07-28 (Version 1.1): Klasse 1 auf Datenfluss-Signatur umgestellt,
  Klasse 2 verallgemeinert, B14b umgehängt, Klasse 4 eingeführt, B15–B17
  aufgenommen. 16 ACs statt 14. Größenschätzung 1600–2200 LoC.
- 2026-07-28 (Version 1.2): RED-Phase-Nachschärfung gegen zehn Befunde
  (S-1 bis S-10). Klasse-2-Bedingung „bloßer Skalar" gestrichen (E1/S-1).
  Klasse 4 auf Versandkontext eingeschränkt (E2) — Verifikation ergab
  SECHS statt drei Treffer (B14b + neues B21). Dateiweites Muster in
  `trip_command_processor.py` aufgenommen (E3/B18, zehn Funktionsschlüssel,
  13 Treffer). Zwei Inbound-Reader von „kein Fund" zu Klasse-2-Funden
  korrigiert (E4/B19+B20). „Undurchsichtiger Aufruf" um eine
  Builtin-/`math.*`-Ausschlussliste geschärft, verifiziert gegen sechs
  `weather_metrics.py`/`aggregation.py`-Funktionen (E6). Fünf technische
  Präzisierungen ergänzt: Mehrfachtreffer-Merge (S-6), Dekorator-Ausschluss
  (S-7), Schlüsselwortargumente als Dict-Schlüssel (S-8), nacktes `return`
  kein Erfolgssignal (S-9). AC-1-Tabelle neu gerechnet: 38 Funktionsschlüssel
  (vorher 23), Summe 45 (vorher 27), 23 Ticket-Fundstellen (vorher 19). Vier
  neue ACs (AC-8b, AC-13b, AC-16b als Klarstellung ohne neuen Test, AC-17,
  AC-18) — 20 ACs statt 16. Größenschätzung auf 2400–2800 LoC angehoben
  (vorher 1600–2200) — Freigabe erneut beim PO einzuholen. Approval
  zurückgesetzt.
- 2026-08-11 (Nachzug Issue #1701, S2b): Premium-SMS wird vierter
  Versandkanal in `send_official_alert` (B14a) und `_dispatch_alert_message`
  (B14c) — die Mindest-Trefferzahl beider Funktionsschlüssel steigt von 3
  auf 4 (Tabelle oben), `SPEC_LISTED_FINDINGS`-Summe von 40 auf 42.
  Funktionsschlüssel-Zahl (33) unverändert. Dies ist genau die in „Offene
  Punkte" 2 vorgesehene, hier beschlossene Korrektur.
