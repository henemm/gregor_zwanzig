---
entity_id: fix_1628_nowcast_datenluecke
type: bugfix
created: 2026-08-09
updated: 2026-08-09
status: draft
version: "1.0"
tags: [alerts, nowcast, radar, issue-1628, observability]
---

# NowCast-Radarpfad: Datenlücke von "kein Regen" unterscheidbar machen (Issue #1628, S0+S1+S3)

## Approval

- [x] Approved — PO-„go" 2026-08-09 (Beleg: Issue-Kommentar zu #1628)

## Purpose

Der NowCast-Radarpfad (`RadarNowcastService`) liefert heute für JEDEN Fehlerfall — echter
HTTP-Fehler, Zeitüberschreitung, Kontingent-Bremse, Parsefehler — genau dasselbe Ergebnis wie
"geprüft, es regnet nicht": leere Frame-Liste, `onset_minutes=None`, Label "Kein Niederschlag".
Weder der Nutzer (`/jetzt`-Kommando) noch der Betrieb können "wir wissen es nicht" von "wir
haben geprüft, es ist trocken" unterscheiden. Diese Scheibe schafft die Unterscheidung an der
Quelle (bereits vorhandenes, bisher verworfenes Instanzattribut) und macht sie an der einzigen
Stelle sichtbar, an der der Nutzer sie sieht — sowie senkt vorab die Häufigkeit über einen
gemessenen Zeitversatz der beiden Radar-Cron-Jobs.

Vollständige Herleitung, Messungen und Ursachenkette: `docs/context/fix-1628-nowcast-datenluecke.md`.
Diese Spec wiederholt nichts davon, sondern zieht den Scope daraus.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `class NowcastResult`, `RadarNowcastService.format_now_text`,
  `RadarNowcastService._derive_result`
- Nebendateien: `internal/scheduler/scheduler.go` (S0)

Betroffene Schicht: **Python-Core** (`src/services/`) für S1/S3, **Go-API**
(`internal/scheduler/`) für S0. Kein Frontend-Code — `format_now_text` wird ausschließlich über
Telegram-Text (`/jetzt`) konsumiert, nicht über die SvelteKit-UI.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `fix_1329_c2_radar_nowcast_cache` | module | liefert `throttled`, `ForecastBudgetGate`, den Formel-Präzedenzfall (`throttled = bool(...) and not frames`) und die "Known Limitation", die diese Scheibe schließt |
| `radar_convective_stage` (#660) | module | `convective_checked` — zweites, bereits funktionierendes Ausfallsignal derselben Klasse; bleibt unverändert |
| `radar_nowcast` (#656) | module | Grund-Spec der Quellenkette, unverändert |
| `rework_1467_s3_nowcast` | module | gemeinsamer Freigabe-Baustein beider Nowcast-Pfade — prüft NUR Ruhezeit/Sperrzeit/Tageslimit, nicht Datengrundlage; von dieser Scheibe nicht berührt |
| ADR-0018 | decision | "Provider-Fallback ohne Kaschieren" — trägt diese Scheibe, s. Regel-Budget |
| ADR-0041 | decision | Muster B (All-None-Antwort = korrekte "nicht zuständig"-Auskunft) — Grenze, die S1 einhalten MUSS |

## Estimated Scope

- **LoC:** < 250 Produktivcode (S0 < 20, S1 < 60, S3 < 60 — deutlich unter der harten Grenze;
  Tests zählen nicht mit).
- **Files:** 2 Produktivdateien geändert (`internal/scheduler/scheduler.go`,
  `src/services/radar_service.py`), 2–3 Testdateien neu/geändert.
- **Effort:** low-medium — kein neuer Aufrufer, kein neues Modul, keine Migration.

## Nicht in dieser Scheibe

- **S2 (Log-Lücke im INCA/DPC-Primärabruf, `providers/geosphere.py:348-349`,
  `providers/radar_dpc.py`, `providers/brightsky.py`).** Betrifft ausschließlich Defekt B
  (abgeschwächter Gewitter-Alarm bei Orten MIT Regionalquelle) und ist von S1 unabhängig lieferbar
  — S1 deckt beide Defekte bereits über das gemeinsame `_openmeteo_unavailable_this_call` ab, S2
  würde zusätzlich noch die tiefere Fehlerursache (welcher Provider, welcher Statuscode) sichtbar
  machen. Eigene Scheibe, eigenes Issue.
- **S4 (Journal/Status-Endpunkt für den Radarpfad, Erweiterung von `call_log.py`).** Blockiert
  durch #1633 (Diagnose-Journale schreiben aktuell in den falschen — nicht überwachten —
  Programmordner; ein neuer Radar-Eintrag dort wäre für den Betrieb bis zur Behebung von #1633
  faktisch unsichtbar). Außerdem eine echte neue Dauerpflicht (Regel-Budget-relevant, im
  Unterschied zu S0–S3), die erst mit #1633 sauber eingeführt werden kann.
- **(c) "Quellenkette für Grenzregionen" aus dem ursprünglichen Issue-Titel.** Nach der Messung im
  Kontextdokument gegenstandslos: die Koordinate aus dem Issue wird tatsächlich von INCA bedient,
  keine Bounding-Box-Lücke. Kein Handlungsbedarf.

## Implementation Details

### S0 — Zeitversatz der beiden Radar-Cron-Jobs

`internal/scheduler/scheduler.go`, aktuell (Zeilen 149/152):

```
{"*/15 * * * *", s.radarAlertChecks, "radar_alert_checks", ...}
{"*/15 * * * *", s.compareRadarAlertChecks, "compare_radar_alert_checks", ...}
```

Beide Cron-Ausdrücke ändern auf `7,22,37,52 * * * *`. **Ausschließlich diese zwei Jobs.** Die
übrigen vier `*/15`-Jobs (`alert_checks`, `inbound_command_poll` mit `*/5`,
`data_write_selftest`, `compare_alert_checks`, `compare_official_alert_checks`) sowie
`briefing_dispatch` (`0 * * * *`) bleiben **unverändert** — die im Kontextdokument gemessene
Fehlerhäufung auf `:00`/`:30` ist ausschließlich am Radarpfad gemessen, `data_write_selftest` hat
keinerlei externen Bezug, und eine pauschale Verschiebung aller Jobs wäre unbegründetes
Scope-Kriechen in #1329.

Begründung, warum das kein "Kaschieren" im ADR-0018-Sinn ist: die Ursache ist nachweislich extern
(HTTP 503 mit Open-Meteos eigenem Overload-Text, kein einziger 429 im 9-Tage-Fenster — schließt
unsere eigene Kontingent-Bremse aus). Einer gemessenen, zyklischen Lastspitze eines Fremddienstes
zeitlich auszuweichen ist Betriebsführung, kein Verstecken eines eigenen Defekts.

### S1 — Fetch-Fehler von "genuinely dry" unterscheidbar machen

`NowcastResult` (`radar_service.py:79-92`) bekommt ein zusätzliches Feld, gespeist aus dem
bereits vorhandenen Instanzattribut `_openmeteo_unavailable_this_call` — analog zur bestehenden
Formel für `throttled` (`:563`):

```
throttled     = bool(self._budget_throttled_this_call) and not frames
fetch_failed  = bool(self._openmeteo_unavailable_this_call) \
                and not bool(self._budget_throttled_this_call) \
                and not frames
```

(Feldname ein Vorschlag, in der Umsetzung besser benennbar — z. B. `data_unavailable`. Verbindlich
ist die Formel, nicht der Bezeichner.)

**Warum der zusätzliche `and not bool(self._budget_throttled_this_call)`-Teil zwingend ist:** beim
Kontingent-Drosseln setzt `_fetch_openmeteo_15` (`:431-434`) BEIDE Flags gleichzeitig
(`_budget_throttled_this_call = True` UND `_openmeteo_unavailable_this_call = True`, letzteres als
Doppelverbrauch-Sperre für den Rest des Aufrufs). Ohne diesen Ausschluss würde jede
Kontingent-Drosselung fälschlich auch als "Fetch-Fehler" gezählt und das bestehende, korrekt
funktionierende `throttled`-Signal mit dem neuen Signal vermengt — genau das verbietet die
Randbedingung "S1 Budget" unten.

Bei einem echten Fehlschlag (`httpx.HTTPStatusError`, Timeout, Verbindungsfehler — abgefangen im
breiten `except` `:476-481`) bleibt `_budget_throttled_this_call` auf seinem Startwert `False`
(zurückgesetzt bei jedem `get_nowcast()`-Aufruf, `:175-176`) — die Formel liefert dort korrekt
`fetch_failed=True`.

**Wo die Grenze "nicht zuständig" ↔ "zuständig, aber ausgefallen" verläuft (ADR-0041-Bezug):**
NICHT bei "liegt der Punkt in der Bounding-Box" — Boxen sind nur ein netzfreier Vorfilter (ADR-0041
Muster C). Die Grenze verläuft bei "erzeugte die konkrete Anfrage einen Fehlerstatus". Der
All-None-Guard (`:460-461`, ein Regionalmodell antwortet mit `precipitation=[None, ...]` für einen
Punkt außerhalb seines rotierten Gitters) ist die korrekte Auskunft "dieser Punkt liegt außerhalb
meines Gitters" (ADR-0041 Muster B) — er `return`et VOR dem `except`-Block und setzt
`_openmeteo_unavailable_this_call` bewusst **nicht**. Diese Unterscheidung existiert im Code
bereits korrekt; S1 darf sie nicht verändern, nur den vorhandenen Fehlerfall zusätzlich nach außen
tragen. Wer All-None mit einem Fehlschlag verwechselt, erzeugt Dauerwarnungen für Punkte, an denen
strukturell nie eine Quelle zuständig war — dieser Fehler ist im Projekt bereits zweimal passiert
(ADR-0041, #1397).

**Beide Alarmwege ohne Codeänderung an sich selbst:** `trip_alert.py::check_radar_alerts` und
`compare_radar_alert.py::_detect_triggered_locations` lesen `NowcastResult` bereits heute über
dieselbe `RadarNowcastService`-Instanz-Methode `get_nowcast()`. Die Felderweiterung landet damit
automatisch bei beiden, ohne dass eine Zeile in einer der beiden Dateien geändert werden muss —
das ist eine Beobachtung über die bestehende Architektur (eine Quelle, zwei Konsumenten), keine
Vorgabe, die die Umsetzung erzwingen müsste. Der Verhaltensnachweis dafür ist AC-8.

### S3 — Die Datenlücke im Nutzertext sichtbar machen

`format_now_text` (`:227-277`), aktueller `onset_minutes is None`-Zweig:

```
if result.onset_minutes is None:
    lines.append(result.intensity_label + ".")
    lines.append("In den nächsten 2 Stunden kein Regen erwartet.")
```

**Beide Zeilen sind bei `fetch_failed=True` unzutreffend, nicht nur die zweite:** Da bei einem
Fetch-Fehler `frames=[]` ist, berechnet `_derive_result` `max_rate=0.0` und damit
`intensity_label = "Kein Niederschlag"` — dieselbe falsche Entwarnung wie der Folgesatz. Die
Implementierung muss im `fetch_failed=True`-Fall BEIDE Zeilen durch einen Hinweis ersetzen, der
sagt: die Kurzfrist-Prüfung konnte nicht durchgeführt werden — nicht, dass sie durchgeführt wurde
und trocken blieb.

Wortlaut-Vorbild `src/output/renderers/email/unavailable_hint.py` (Issue #1348) — Prinzip dort:
*"'keine Warnung' bedeutet hier nicht sicher 'alles ruhig'."* Übertragen auf den Regen-Kontext,
NICHT wörtlich zu übernehmen (die Vorlage handelt von amtlichen Warnungen, hier geht es um die
Radar-Kurzfristprüfung selbst): sinngemäß "Regen-Kurzfristprüfung aktuell nicht möglich —
bitte selbst beobachten." Endgültiger Wortlaut ist Implementierungsdetail.

Der bestehende `convective_checked`-Zweig (`:271-272`, "Gewitter-Check nicht verfügbar.") bleibt
unverändert und unabhängig — er wird von einem eigenen Flag gespeist, das in den relevanten
Fehlerfällen dieser Scheibe (Punkte ohne Regionalquelle, Defekt A) ohnehin auf seinem Default
`True` bleibt, weil der INCA/DPC-Zweig dort gar nicht erst erreicht wird.

## Expected Behavior

- **Input:** Koordinaten eines Wegpunkts, `priority` (`"user_briefing"` für `/jetzt`, `"polling"`
  für Scheduler-Läufe).
- **Output:** `NowcastResult` mit dem neuen Feld; `format_now_text()` liefert im Fehlerfall einen
  "nicht geprüft"-Hinweis statt einer Entwarnung.
- **Side effects:** keine neuen. Kein zusätzlicher HTTP-Aufruf, kein neues Log, kein neues
  Journal (harte Nebenbedingung, s. u.).

**🔴 Wo die Wirkung beim Nutzer tatsächlich ankommt — und wo NICHT:** Ein Alarm wird ausschließlich
verschickt, wenn tatsächlich Regen erkannt wurde (`radar_alert_due()` liefert bei
`onset_minutes=None` in JEDEM Fall `False` — ob "echt trocken" oder "Datenlücke", macht dafür
keinen Unterschied). Diese Scheibe kann und soll KEINEN Alarm herbeizaubern, der aus einer
Datenlücke resultiert — das wäre auch fachlich falsch (eine Datenlücke ist kein Regen-Ereignis).
Sichtbar wird der Fix ausschließlich dort, wo ohnehin etwas gerendert oder abgefragt wird:

- **`/jetzt`-Telegram-Kommando** (`TripCommandProcessor._show_now()`,
  `trip_command_processor.py:1293-1299`) — ruft `format_now_text()` direkt auf und liefert die
  Antwort unmittelbar an den fragenden Nutzer zurück. **Das ist der Haupt-Nachweisweg dieser
  Scheibe** — hier UND NUR hier prüft der Nutzer aktiv nach und bekommt heute eine falsche
  Entwarnung statt eines ehrlichen "weiß ich nicht".
- **Starkregen-Hinweis im Briefing** (`TripReportScheduler._build_starkregen_hint()`,
  `trip_report_scheduler.py:1152-1178`) bleibt in dieser Scheibe **unverändert** — s. u.,
  "Nicht in dieser Scheibe" ergänzend begründet.
- **Beide Alarm-Checker** (`trip_alert.py::check_radar_alerts`,
  `compare_radar_alert.py::_detect_triggered_locations`) bleiben unverändert (s. Randbedingung
  unten) — sie lesen `NowcastResult`, rufen aber `format_now_text()` nicht auf und werten
  `onset_minutes`/`intensity_label` direkt aus, nicht den formatierten Text.

**Warum `_build_starkregen_hint()` bewusst NICHT angefasst wird:** die Funktion gibt bei
`onset_minutes is None` bereits heute `None` zurück — unabhängig davon, ob der Grund "echt
trocken" oder ein Fetch-Fehler ist (`trip_report_scheduler.py:1175-1176`). Anders als
`format_now_text()` behauptet sie dabei NICHTS Falsches: sie äußert sich einfach gar nicht, und
"kein Hinweis im Briefing" ist bereits der weit überwiegende Normalzustand (die meisten Tage ohne
Starkregen). Eine Datenlücken-Kennzeichnung an dieser Stelle hätte keinen Adressaten (der Hinweis
erscheint nur, wenn ohnehin Text gerendert wird) und würde eine neue, bei den meisten Läufen
zutreffende Zeile ins Briefing einführen — das wäre eine eigene Designentscheidung mit eigenem
Abwägungsbedarf (Rauschen vs. Vollständigkeit), kein Nebenprodukt dieser Bugfix-Scheibe.

## Randbedingungen

- **Kein zusätzlicher HTTP-Abruf.** Weder S0 noch S1 noch S3 fügen einen neuen Netzwerk-Aufruf
  hinzu — S0 verschiebt nur den Zeitpunkt bestehender Aufrufe, S1 liest ausschließlich ein bereits
  vorhandenes Instanzattribut aus, S3 formatiert nur Text. Der Radar-Pfad dominiert das
  Open-Meteo-Kontingent (#1329) — jede Lösung, die zusätzliche Abrufe erzeugt (Retry,
  Ersatzquelle), ist damit ausgeschlossen.
- **S1 Budget:** die bestehende Drosselungs-Kennzeichnung `throttled` bleibt unverändert bestehen
  und wird durch das neue Feld NICHT mitgezählt — s. Formel oben. Eine Kontingent-Drosselung ist
  weiterhin ausschließlich `throttled=True`, niemals zusätzlich `fetch_failed=True`.
- **Sprengweite (#1467 S3 Finding F004):** "laut scheitern" ohne Begrenzung riss einmal den
  gesamten Nowcast-Lauf für alle Nachbarn ab. Beide Aufrufer (`trip_alert.py`,
  `compare_radar_alert.py`) fangen bereits heute Ausnahmen je Entität separat ab
  (`trip_report_scheduler.py:1166-1173` als Beispielmuster). S1/S3 dürfen an dieser
  Fehlerbegrenzung nichts ändern — das neue Feld wird innerhalb des bestehenden `try/except`
  gefüllt, wirft selbst nie.
- **Trip/Ortsvergleich teilen sich EINEN Nachweis.** `trip_alert.py` und
  `compare_radar_alert.py` müssen für diese Scheibe NICHT geändert werden — beide lesen dieselbe
  `NowcastResult`-Instanz derselben `RadarNowcastService`-Klasse. Eine Felderweiterung auf
  `NowcastResult` erreicht beide Pfade automatisch (Idealfall der Teilungsregel: eine Quelle,
  zwei Konsumenten). Das ist eine erwartete Wirkung der Architektur, keine Beschränkung, die eine
  spätere Anpassung dieser Dateien aus anderem Grund verbieten würde.
- **Mandantentrennung:** unberührt — diese Scheibe fügt keine neue Persistenz und keinen neuen
  `user_id`-Pfad hinzu.

## Acceptance Criteria

**S0 — Zeitversatz**

- **AC-1:** Given die Job-Liste des Go-Schedulers, When sie initialisiert wird, Then feuern
  ausschließlich `radar_alert_checks` und `compare_radar_alert_checks` zu den Minuten 7/22/37/52
  jeder Stunde, während die übrigen vier `*/15`-Jobs sowie `briefing_dispatch` unverändert zu
  ihren bisherigen Zeitpunkten registriert sind.
  - Test: Job-Definitionen (bzw. deren registrierte Cron-Ausdrücke) für alle Job-IDs auslesen und
    gegen die erwartete Tabelle vergleichen — zwei geänderte, vier plus Briefing unverändert.

**S1 — Fehlerfall unterscheidbar (Kern der Scheibe — heute existiert dafür kein einziger Test)**

- **AC-2:** Given ein `get_nowcast()`-Aufruf, bei dem der abschließende Open-Meteo-Abruf mit
  einem echten HTTP-Fehlerstatus antwortet (kein Budget-Drosseln, keine All-None-Antwort), When
  der Aufruf beendet ist, Then trägt das zurückgegebene `NowcastResult` das neue Fehlerfeld als
  wahr, UND `frames` ist leer, UND `onset_minutes` ist `None`.
  - Test: `RadarNowcastService` mit einer Koordinate ohne Regionalquelle (z. B. Atlantik, nur
    generischer `minutely_15`-Zweig erreichbar) aufrufen, dabei `httpx.Client` testweise durch
    eine deterministische Ersatzklasse ersetzen, die auf `.get()` einen dokumentierten 503 mit
    Open-Meteos eigenem Fehlerkörper zurückgibt bzw. `raise_for_status()` einen
    `httpx.HTTPStatusError` auslösen lässt (kein echtes Netz, Muster wie
    `tests/unit/test_radar_budget_and_priority.py::_TripwireClient`) — Ergebnisfeld ist gesetzt.

- **AC-3:** Given denselben Aufruf wie in AC-2, aber mit erfolgreichem Abruf und trockenen
  Bildern (kein einziges Bild über der Regenschwelle), When der Aufruf beendet ist, Then trägt das
  zurückgegebene `NowcastResult` das neue Fehlerfeld als falsch — der Normalfall "echt geprüft,
  wirklich trocken" bleibt vom neuen Feld unberührt.
  - Test: dieselbe Koordinate, `.get()` liefert eine echte Erfolgsantwort mit ausschließlich
    `precipitation: 0.0`-Werten (z. B. die bestehende Fixture `fixtures/radar/minutely_15.json`
    oder eine gleichwertige Erfolgsantwort) — Fehlerfeld bleibt `False`.

- **AC-4:** Given eine Koordinate, für die ein Regionalmodell mit `models`-Parameter eine
  All-None-Antwort liefert (Punkt außerhalb seines rotierten Gitters — der bestehende
  All-None-Guard greift), When die Kette zum nächsten Modell durchfällt, Then bleibt das neue
  Fehlerfeld an dieser Stelle `False` — eine All-None-Antwort ist kein Ausfall, sondern die
  Auskunft der Quelle "für diesen Punkt bin ich nicht zuständig", und sie darf das Fehlerfeld
  nicht setzen (ADR-0041 Muster B).
  - Test: `.get()` für den regionalen Zweig liefert `precipitation: [None, None, ...]` bei
    gesetztem `models`-Parameter, Kette fällt zum nächsten Modell durch — Fehlerfeld bleibt
    `False` für dieses Zwischenergebnis, unabhängig vom Endresultat der Kette.

- **AC-5:** Given ein `get_nowcast()`-Aufruf, bei dem ausschließlich die Kontingent-Bremse greift
  (kein echter HTTP-Fehler), When der Aufruf beendet ist, Then bleibt `throttled=True` wie bisher,
  UND das neue Fehlerfeld ist `False` — Drosselung und echter Ausfall bleiben zwei getrennte,
  nicht vermengte Signale.
  - Test: `ForecastBudgetGate` so vorbelegen, dass `allow()` `False` liefert, Aufruf durchführen
    — `throttled=True` und Fehlerfeld `False` gleichzeitig.

**S3 — Sichtbarkeit im Nutzertext**

- **AC-6 (Wirkungs-AC — belegt die Nutzer-sichtbare Änderung):** Given ein `NowcastResult` mit
  gesetztem Fehlerfeld (Datenlücke), When der Nutzer per `/jetzt`-Telegram-Kommando abfragt
  (`TripCommandProcessor._show_now()`), Then enthält die an den Nutzer gesendete Antwort einen
  Hinweis, dass die Regen-Kurzfristprüfung nicht möglich war — UND enthält NICHT den Satz "In den
  nächsten 2 Stunden kein Regen erwartet." und NICHT das Label "Kein Niederschlag" als
  Tatsachenbehauptung.
  - Test: `_show_now()` (bzw. `format_now_text()` direkt, mit demselben Ergebnis wie in AC-2) mit
    einem Fehlerfeld-Ergebnis aufrufen — der zurückgegebene `confirmation_body` enthält den neuen
    Hinweistext, nicht die alte Entwarnungsformulierung.

- **AC-7:** Given ein `NowcastResult` ohne gesetztes Fehlerfeld und ohne Onset (echt trocken,
  entspricht AC-3), When `format_now_text()` aufgerufen wird, Then bleibt der Ausgabetext
  identisch zum bisherigen Wortlaut ("Kein Niederschlag." / "In den nächsten 2 Stunden kein Regen
  erwartet.") — der Normalfall darf sich nicht ändern.
  - Test: `format_now_text()` mit einem Erfolgsergebnis (Fehlerfeld `False`, `onset_minutes=None`)
    aufrufen, Text zeichenidentisch mit dem Stand vor dieser Scheibe vergleichen.

**Beide Pfade bekommen die Unterscheidung**

- **AC-8:** Given einen fehlschlagenden Abruf (dieselbe Ersatz-`.get()`-Methode wie in AC-2), When
  BEIDE Alarmwege je einmal über ihren echten Einstiegspunkt laufen — Trip
  (`TripAlertService.check_radar_alerts()`) und Ortsvergleich
  (`CompareRadarAlertService._detect_triggered_locations()`) — Then liefert das jeweils intern
  abgefragte `NowcastResult` in BEIDEN Fällen das neue Fehlerfeld als wahr — die Unterscheidung
  kommt bei beiden Alarmwegen an, nicht nur beim `/jetzt`-Kommando.
  - Test: für einen Trip und für ein Ortsvergleich-Preset je eine Entität mit einer Koordinate
    ohne Regionalquelle anlegen, denselben deterministischen Fehlerfall wie in AC-2 auf dem
    HTTP-Client erzwingen, beide echten Einstiegspunkte aufrufen, das je zugrundeliegende
    `NowcastResult` (z. B. über einen Zähl-/Abgriff-Seam auf `RadarNowcastService.get_nowcast()`)
    prüfen — Fehlerfeld ist in beiden Fällen `True`. Kein Diff auf `trip_alert.py`/
    `compare_radar_alert.py` als Testbedingung — die Abwesenheit einer Codeänderung dort ist eine
    Beobachtung (s. Implementation Details), kein prüfbares Verhalten.

**Kontingent**

- **AC-9:** Given den Produktivcode nach dieser Scheibe, When ein vollständiger `get_nowcast()`-
  Aufruf durchläuft (Erfolgs- oder Fehlerfall), Then ist die Anzahl der ausgehenden HTTP-Anfragen
  identisch zum Stand vor dieser Scheibe — kein zusätzlicher Aufruf durch S0, S1 oder S3.
  - Test: Aufrufzähler auf der Ersatz-`.get()`-Methode (wie in AC-2) vor und nach der Umsetzung
    vergleichen, für identische Szenarien identische Zählung.

## Known Limitations

- **Defekt B (abgeschwächter Gewitter-Alarm) wird durch S1 formal mit erfasst, aber nicht
  gezielt sichtbar gemacht.** Das bereits existierende `convective_checked=False`-Signal deckt
  diesen Fall inhaltlich ab (`format_now_text` zeigt bereits "Gewitter-Check nicht verfügbar.") —
  diese Scheibe ändert daran nichts und führt keine zusätzliche Kennzeichnung für Defekt B ein.
- **`_build_starkregen_hint()` bleibt ohne Datenlücken-Hinweis** — bewusste Entscheidung, s.
  "Expected Behavior" oben. Wer künftig eine Kennzeichnung dort will, braucht eine eigene
  Abwägung (Rauschen vs. Vollständigkeit) und damit eine eigene Spec.
- **Die "Quelle:"-Zeile in `format_now_text()` bleibt im Fehlerfall unverändert** und kann einen
  Quellennamen zeigen (z. B. "Open-Meteo (global)"), obwohl von dort keine Daten kamen — die
  letzte in der Kette erreichte Quellenbezeichnung wird unabhängig vom Erfolg durchgereicht. Nicht
  Teil dieser Scheibe; wer das stört, kann `include_source` am neuen Hinweis-Zweig gezielt
  unterdrücken, das ist aber ein eigenständiger Designentscheid, keine Pflicht dieser Spec.
- **Verifikation am lebenden Symptom ist derzeit nicht möglich.** Der dominante Defekt A
  (Provence-Orte, Ortsvergleich "Le Var") ist seit 2026-07-31 pausiert (`compare_alert_guard`
  schweigt seither, #1467 S2 AG6) — die Kette wird für diesen konkreten Fall aktuell gar nicht
  mehr abgefragt. Sobald der Ortsvergleich reaktiviert wird oder ein anderer Ort südlich von 44° N
  hinzukommt, ist der Defekt sofort wieder aktiv. Staging-Verifikation muss deshalb gezielt
  provoziert werden, s. "Verifikation" unten.

## Verifikation

Weil Defekt A derzeit schläft, ist ein Nachweis am lebenden Symptom nicht möglich — die
Verifikation erfolgt zweistufig:

1. **Kern-Suite (deterministisch, Pflicht vor Commit):** ein aufgezeichneter 503 als Fixture
   (Muster `_TripwireClient` aus `tests/unit/test_radar_budget_and_priority.py`, angepasst auf
   einen dokumentierten Fehlerstatus statt einer reinen Netz-Tripwire) belegt AC-2 bis AC-9 ohne
   jedes echte Netz.
2. **Staging-Nachweis über `/jetzt` mit einem echten Testort:** ein Testort/Trip auf Staging
   anlegen, dessen Koordinate nachweislich außerhalb aller Regionalquellen liegt (z. B. eine der
   im Kontextdokument gemessenen Provence-Koordinaten, 43.2447/6.2628), UND für diesen Lauf einen
   echten Fehlerfall provozieren — entweder durch einen zeitlich getroffenen Livetest während
   einer der gemessenen Open-Meteo-Lastspitzen (`:00`/`:30`), oder durch eine testweise
   herabgesetzte Timeout-Konstante (`HTTPX_TIMEOUT`) gegen den echten Staging-Endpunkt, NUR für
   die Dauer des Verifikationslaufs, danach zurückgesetzt. Erwartung: `/jetzt` liefert den neuen
   Hinweistext statt "kein Regen erwartet". Kein Massenversand, nur der eine Testort (Live-E2E-
   Regel: nur Test-Trip, kein Sammelversand).

Ein bestandener Kern-Testlauf allein genügt NICHT als "E2E bestanden" — der Staging-Nachweis über
`/jetzt` ist Pflicht, weil er der einzige tatsächlich vom Nutzer erreichbare Pfad ist.

## Regel-Budget

S0–S3 erzeugen **keine neue Dauerpflicht** — kein neues Journal, kein Status-Block, kein neues
Gate. Sie lösen eine **bestehende, unerfüllte** Zusage ein: ADR-0018 ("Provider-Fallback ohne
Kaschieren") fordert bereits *"Neue degradierbare Datenpfade müssen dieselbe
Nicht-Kaschieren-Invariante erfüllen"* — der Radarpfad war dort nie erwähnt und erfüllte sie
nicht. Diese Scheibe ist Ersatz für eine unerfüllte Regel, kein Neuzugang. Kein Prüfdatum nötig.

## Risiken

| | Risiko | Test, der es fängt |
|---|---|---|
| **R1** | Sprengweite: eine unvorsichtige Änderung reißt den gesamten Nowcast-Lauf für alle Nachbarn ab (#1467 S3 Finding F004, CRITICAL) | Randbedingung "Sprengweite" oben — S1/S3 ändern nichts an den bestehenden `try/except`-Grenzen je Entität; AC-8 belegt, dass beide Alarmwege weiterhin funktionieren |
| **R2** | Kontingent: eine der drei Scheiben fügt versehentlich einen zusätzlichen HTTP-Aufruf hinzu | AC-9 |
| **R3** | Verwechslung "nicht zuständig" (All-None) mit "ausgefallen" — erzeugt Dauerwarnungen für Punkte, an denen strukturell nie eine Quelle zuständig war (bereits zweimal passiert: ADR-0041, #1397) | AC-4 |
| **R4** | Vermengung von `throttled` und dem neuen Fehlerfeld — eine Kontingent-Drosselung würde fälschlich auch als Ausfall gezählt | AC-5 |
| **R5** | S3 ersetzt nur die zweite Textzeile, nicht `intensity_label` — die falsche Entwarnung "Kein Niederschlag." bliebe stehen | AC-6 |
| **R6** | Verifikation vorgetäuscht: Kern-Suite grün, aber Defekt A schläft (pausierter Ortsvergleich) — "Verbrauchstest grün, weil der Dienst tot ist" | Verifikation-Sektion — Staging-Nachweis mit gezielt provoziertem Fehlerfall ist Pflicht, nicht optional |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — löst eine bestehende Zusage aus ADR-0018 ein (s. Regel-Budget). Kein
  ADR-Nachtrag nötig, da ADR-0018 bereits allgemein genug formuliert ist ("Neue degradierbare
  Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen") und keine Korrektur, nur eine
  Umsetzung ist.
- **Rationale:** Der Radarpfad besitzt die Unterscheidung "Fehler vs. genuinely dry" bereits als
  Instanzattribut (`_openmeteo_unavailable_this_call`) und verwirft sie nur beim Verlassen der
  Klasse. Kein neues Architekturprinzip — konsequente Anwendung des bestehenden
  Nicht-Kaschieren-Prinzips (ADR-0018) auf den letzten noch nicht erfassten Datenpfad, mit
  derselben "Drosselung ≠ Ausfall"-Formel, die für `throttled` bereits etabliert ist
  (`fix_1329_c2_radar_nowcast_cache`).

## Changelog

- 2026-08-09: Initiale Spec. Scope auf S0+S1+S3 begrenzt (S2/S4 ausdrücklich ausgeschlossen, S4
  blockiert durch #1633). Formel für das neue Feld leitet sich aus dem bestehenden
  `throttled`-Muster ab, ergänzt um den notwendigen Ausschluss der Budget-Drosselung (sonst
  Vermengung der beiden Signale). Grenze "nicht zuständig" (All-None-Guard, ADR-0041 Muster B)
  vs. "ausgefallen" (echte Ausnahme) explizit als eigenes AC verankert.
- 2026-08-09: AC-8 von einem Diff-basierten Testbedingung (Dateiinhalt-Check, kein
  Verhaltensnachweis) auf einen Wirkungsnachweis über beide echte Alarm-Einstiegspunkte
  umgeschrieben. Verunglückten Satz in AC-4 korrigiert (All-None-Antwort ist kein Ausfall,
  sondern die korrekte "nicht zuständig"-Auskunft der Quelle).
