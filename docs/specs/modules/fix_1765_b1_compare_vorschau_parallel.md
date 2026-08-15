---
entity_id: fix_1765_b1_compare_vorschau_parallel
type: module
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [bug, performance, preview, python-core, issue-1765]
---

# Vergleichs-Vorschau parallelisieren (Scheibe B1, #1765)

## Approval

- [x] Approved — PO-Freigabe („Go") am 2026-08-15 auf die neun Acceptance Criteria

## Purpose

Die Vergleichs-Vorschau (`POST /api/preview/compare/{preset_id}`) berechnet die Orte eines
Presets heute nacheinander (~25 Sekunden je Ort) und reißt dadurch bei drei oder mehr Orten
die 60-Sekunden-Zeitgrenze zwischen Go-API und nginx — der Nutzer bekommt keine Vorschau,
sondern einen Timeout-Fehler. Diese Spec stellt ausschließlich diesen einen Aufrufweg auf
gleichzeitige Ortsverarbeitung um, nach dem bereits im Repo bewährten Vorbild der
Etappen-Wetter-Berechnung. Ein neuer, geteilter Baustein entsteht dabei so, dass die beiden
verbleibenden Aufrufwege (Versand, Sofortvergleich) ihn in einer Folgescheibe nur noch
benutzen müssen, statt ihn selbst zu bauen.

**Diese Scheibe schließt Issue #1765 NICHT.** Sie ist die erste von zwei Scheiben unter
derselben Nummer — Begründung im Abschnitt „Abgrenzung — was diese Scheibe NICHT umfasst".

## Source

- **File:** `src/services/compare_preview_service.py:163` (Änderungsort) ·
  `src/providers/call_log.py` (Änderungsort) · `src/services/comparison_engine.py:127`
  (Vorbild-Referenz, **bleibt unangetastet**)
- **Identifier:** neues Modul `src/services/comparison_parallel.py`, Funktion
  `run_comparison_parallel(...)`

## Estimated Scope

- **LoC:** ~65 Produktivcode (Baustein ~40, `call_log`-Erweiterung ~15, Umstellung der
  Aufrufstelle ~10) + ~140–180 Testcode (Nachweise + Umbau des abgelösten Vertrags) —
  Gesamt ~205–245 LoC, unter dem 250er-Limit ohne Override
- **Files:** 2 neue Produktivdateien-Anteile (1 neue Datei, 1 geänderte Bestandsdatei) + 1
  geänderte Aufrufstelle + 2 neue Testdateien + 1 geänderte Bestandstestdatei
- **Effort:** medium — die Mechanik ist am Code als äquivalent zum heutigen Verhalten geprüft
  (Kontextdokument, Abschnitt „Äquivalenz von `run(locations=[loc])` je Ort"), der Aufwand
  liegt im Nachweis, nicht im Mechanismus

**🔴 Nachtrag 2026-08-15 — die Schätzung oben ist überholt. Gemessen wurden 215 Zeilen
Produktivcode (geschätzt 65, Faktor 3,3) und 732 Zeilen Testcode (geschätzt 140–180,
Faktor ~4,5).** Die Abweichung ist erklärbar, war aber nicht vorhergesehen:

| Ursache | trifft |
|---|---|
| Der abgelöste Bestandsvertrag saß an **drei** Stellen statt an einer (RED-Nachtrag) | Testcode |
| F001 (Adversary) verlangte eine **eigene Wirkort-Testdatei** über den echten Router — `test_compare_vorschau_systemfehler.py`, 207 Zeilen | Testcode |
| F002 (Adversary) verlangte einen Vorrang-Test, der zuvor niemandem fehlte | Testcode |
| Docstrings und die Begründung der Fehler-Einordnung im Baustein selbst | Produktivcode |

**Lehre für künftige Schätzungen dieser Art:** Nicht die Schätzung des Mechanismus lag
daneben, sondern die des Nachweises — um ein Vielfaches. Wo Nebenläufigkeit im Spiel ist,
braucht **jeder einzelne** Nachweis einen eigenen Aufbau (Treffpunkt-Sperre, gedrehte
Fertigstellung, echter Router), der sich zwischen den Kriterien nicht teilen lässt. Der
Faustwert „der Nachweis kostet mehr als der Mechanismus" ist hier zu niedrig gegriffen;
realistisch ist **Faktor 3–4 auf den Testanteil**.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `stage_weather.py:170-183` (`compute_stage_weather`) | Vorbild im Repo | Executor-Aufbau, indexierte Vorbelegung statt Append, dünner Fehler-Wrapper je Einheit — vollständig zu übernehmen |
| `official_alerts/warn_egress.py:55-57` (`_fetch_failure_sink`) | Vorbild im Repo | ContextVar-Muster mit Getter/Setter-Paar für threadübergreifende Werte |
| `src/services/comparison_engine.py` (`ComparisonEngine.run`) | unverändert genutzt | `@staticmethod`, keine Instanzattribute — pro Ort einzeln aufrufbar ohne Änderung an der Engine selbst (am Code geprüft, Kontextdokument) |
| Scheibe A (#1765/#1839, bereits ausgeliefert, Commit `62f066bf`) | vorausgesetzter Zustand | Die Zusicherung „`/api/health` bleibt während einer laufenden Vorschau erreichbar" ist bereits hergestellt (13 Handler `def` statt `async def`); diese Scheibe darf sie nicht wieder aufheben, stellt sie aber nicht selbst her |
| `docs/reference/decision_matrix.md:231-254` | Betriebsdaten | Begründet die Parallelitätsgrenze `MAX_PARALLEL_LOCATIONS = 4` (Météo-France: geteiltes, ungedrosseltes Konto) |

## Implementation Details

### Neues Modul `src/services/comparison_parallel.py`

Eine neutrale, geteilte Datei — bewusst **nicht** in `comparison_engine.py` und **nicht** in
`compare_preview_service.py`, damit „`comparison_engine.py` bleibt unangetastet" mechanisch
nachprüfbar ist und die künftigen Aufrufer (Versand, Sofortvergleich) andocken können, ohne
etwas umzubauen.

```
def run_comparison_parallel(
    locations, time_window, target_date,
    forecast_hours=COMPARE_FORECAST_HOURS, profile=None,
    official_alerts_enabled=True, *, call_source=None,
) -> ComparisonResult
```

Ablauf, fünf Schritte, nach dem Vorbild `stage_weather.py:170-183`:

1. `created_at = datetime.now()` **einmal**, bevor die parallele Verarbeitung startet.
2. `fetched: list[Optional[LocationResult]] = [None] * len(locations)` — eine vorbelegte
   Liste in Ortsreihenfolge, kein Anhängen bei Fertigstellung.
3. `ThreadPoolExecutor(max_workers=min(len(locations), MAX_PARALLEL_LOCATIONS))` mit einer
   `future → Index`-Zuordnung; das Ergebnis jedes Orts landet über seinen Index, unabhängig
   davon, in welcher Reihenfolge die Berechnungen fertig werden.
4. Ein dünner Wrapper je Ort: setzt die Diagnose-Quelle für den eigenen Verarbeitungspfad,
   ruft `ComparisonEngine.run(locations=[loc], …)` mit den unveränderten Parametern auf und
   gibt `result.locations[0]` zurück. Ein Fehler bei einem Ort wird — wie in
   `stage_weather.py:52-57` — abgefangen, statt die anderen Orte mitzureißen. Das ist zum
   großen Teil bereits Bestand: `ComparisonEngine.run()` fängt Ortsfehler heute schon intern
   ab und liefert dafür ein `LocationResult(error=…)` statt zu werfen — der Wrapper schützt
   nur zusätzlich gegen Unerwartetes davor (z. B. bei der internen Konfigurationsauflösung).
5. Zusammenführen: `ComparisonResult(locations=fetched, time_window=…, target_date=…,
   created_at=created_at)`.

`MAX_PARALLEL_LOCATIONS = 4` als benannte Konstante, mit Kommentar-Verweis auf
`decision_matrix.md:231-254` — bewusst niedriger als das Vorbild (`min(len, 8)`), weil das
Météo-France-Konto von allen Nutzern gemeinsam genutzt und nicht aktiv gedrosselt wird.

### `src/providers/call_log.py` — Diagnose-Quelle über den Verarbeitungspfad-Wechsel hinweg

Die Diagnose-Funktion, die jedem Wetter-Abruf im Journal eine Quelle wie `"vergleich"` oder
`"briefing"` zuordnet, liest heute die Namen der aufrufenden Funktionen aus dem Aufruf-Stapel
desjenigen Verarbeitungspfads, der den Abruf tatsächlich ausführt. Bei paralleler
Ortsverarbeitung ist das nicht mehr derselbe Pfad, der die ursprüngliche Anfrage
entgegengenommen hat — die bisherigen 11 Namens-Marker (`"vergleich"`, `"vorschau"`, …)
tauchen dort nicht mehr auf, und das Journal verzeichnet fälschlich `"unbekannt"`. Dieser
Mangel ist bereits heute belegt (7,4 % `"unbekannt"` im Diagnose-Journal, Cluster beim
bereits parallelisierten Etappen-Wetter-Pfad) und wird mit dieser Scheibe behoben —
prozessweit, nicht nur für den Vergleich.

Ergänzung: ein Override-Wert, der gezielt für den jeweiligen Verarbeitungspfad gesetzt werden
kann, samt zugehörigem „Zurücksetzen"-Mechanismus, und eine Prüfung dieses Override-Werts
**vor** der bisherigen Stapel-Inspektion. Die 11 Bestandsmarker bleiben als Rückfall
bestehen — Aufrufer, die keinen Override setzen, verhalten sich unverändert wie heute. Der
Baustein aus `comparison_parallel.py` setzt den Override-Wert für die Quelle `"vergleich"`,
bevor er `ComparisonEngine.run()` für den jeweiligen Ort aufruft, und setzt ihn danach wieder
zurück — sonst könnte ein wiederverwendeter Verarbeitungspfad den Wert in eine spätere,
fachlich andere Anfrage hinein „vererben".

**Name festgelegt (RED-Phase 2026-08-15):** Der Mechanismus heißt
`providers.call_log.override_call_source(quelle)` und ist ein **Context-Manager**
(`with`-Block mit automatischem Zurücksetzen am Ende). Die RED-Tests fordern genau diesen
Namen und diese Bauform — eine abweichende Umsetzung lässt die AC-4-Tests rot. Die Spec hatte
zuvor nur „Override-Wert samt Zurücksetzen-Mechanismus" beschrieben, ohne Namen; die
Festlegung stammt aus der Testphase, nicht aus der Freigabe.

Vorbild im Repo: `official_alerts/warn_egress.py:55-57` — dort existiert bereits ein Wert
genau dieser Bauart für einen anderen Zweck, mit dem Kommentar „isoliert korrekt über
Threads/Tasks". Wichtig, weil hier abweichend vom sonst üblichen Fall: der genutzte
Ausführungs-Mechanismus (`ThreadPoolExecutor`) reicht einen gesetzten Override-Wert **nicht**
automatisch an die Arbeits-Einheiten weiter — anders als bei manchen anderen
Nebenläufigkeits-Mechanismen im Repo. Jeder Wrapper aus Schritt 4 muss den Wert deshalb selbst
in seinem eigenen Verarbeitungspfad setzen, nicht der aufrufende Code vorab.

### `src/services/compare_preview_service.py:163` — einzige umgestellte Aufrufstelle

Der bisherige einzelne Aufruf `ComparisonEngine.run(locations=locations, …)` innerhalb von
`_prepare()` wird durch `run_comparison_parallel(locations=locations, …, call_source="vergleich")`
ersetzt. Alle übrigen Parameter (Tagesfenster, Vorhersage-Horizont, Profil, Status der
amtlichen Warnungen) werden unverändert durchgereicht. Die vier öffentlichen Methoden
(`render_all_channels`, `render_email_preview`, `render_telegram_preview`,
`render_sms_preview`) rufen weiterhin gemeinsam `_prepare()` auf und bleiben dadurch
unverändert — nur was innerhalb von `_prepare()` passiert, ändert sich.

## Expected Behavior

- **Input:** unverändert — derselbe Endpunkt, dieselben Preset- und Ortsdaten wie heute.
- **Output:** inhaltlich unverändert (dieselben Metriken, dieselbe Ortsreihenfolge, dieselben
  Fehlerformen). Verändert ist ausschließlich die Laufzeit bei mehreren Orten: bei 3–4 Orten
  fällt sie von der Summe aller Einzelzeiten (~75 s bei drei Orten) auf ungefähr die Zeit des
  langsamsten einzelnen Orts (~26 s).
- **Side effects:** keine neuen fachlichen Seiteneffekte. Eine bereits bestehende
  Diagnose-Verzerrung (Journal-Einträge ohne erkennbare Quelle) wird behoben statt vergrößert.

## Korrekturen am Kontextdokument (bereits eingearbeitet)

Zwei Annahmen aus dem gemeinsamen Ursachendokument (`docs/context/fix-1765-1839-vorschau-laufzeit.md`)
sind für diese Scheibe geprüft und korrigiert worden — beide Korrekturen sind in den
Abschnitten oben bereits berücksichtigt, hier nur zur Nachvollziehbarkeit festgehalten:

1. **Die Zeitzonen-Datenbank-Ladung war als offene Aufgabe für diese Scheibe vermerkt — ist
   aber bereits erledigt.** Sie wurde mit Scheibe A (#1765/#1839, `src/utils/timezone.py:21-34`)
   gegen gleichzeitigen Erstzugriff abgesichert und ist mit einem eigenen Regressionstest
   belegt. Diese Scheibe muss dort nichts mehr tun.
2. **Der vermeintlich vorhandene Nachweis, dass die Ortsreihenfolge bei Parallelverarbeitung
   erhalten bleibt, existiert an der Stelle, an der er wirken müsste, nicht.** Der bestehende
   Test baut die Vergleichsergebnisse von Hand und prüft nur die vier Ausgabe-Oberflächen —
   nicht die Stelle, an der eine Parallelisierung die Reihenfolge tatsächlich kippen würde
   (das Zusammenführen der Einzelergebnisse). Dieser Nachweis wird mit dieser Scheibe **neu**
   gebaut (AC-2 unten).

Messgrundlage für beide Korrekturen sowie für alle Zahlen in dieser Spec:
`docs/context/fix-1765-compare-vorschau-parallel.md`.

## Ein abzulösender Bestandsvertrag

`tests/tdd/test_compare_preview_service.py:285-311` sichert heute zu, dass die
Wetter-Berechnung (`ComparisonEngine.run`) bei einem Vorschau-Aufruf **genau einmal** läuft,
unabhängig davon, wie viele Orte das Preset enthält (`calls.count == 1`). Diese Zusicherung
ist im Docstring von `compare_preview_service.py:52-55` als „AC-7" verankert („EIN
Engine-Lauf, ALLE Kanäle fertig gerendert in EINER Antwort").

**Nach dieser Scheibe stimmt „genau einmal je Aufruf" nicht mehr — es läuft einmal je Ort.**
Der Test wird ohne Anpassung rot. Das ist beabsichtigt und wird hier ausdrücklich als neue
Zusicherung festgehalten, nicht stillschweigend übergangen:

- **Alte Zusicherung:** ein Vorschau-Aufruf löst genau eine Wetter-Berechnung aus.
- **Neue Zusicherung:** ein Vorschau-Aufruf löst genau eine Wetter-Berechnung **je Ort** aus
  (parallel statt nacheinander), deren Ergebnisse zu **einer** Antwort mit allen Kanälen
  zusammengeführt werden. Der Teil der ursprünglichen Zusicherung, der dem Nutzer tatsächlich
  etwas nützt — alle Kanäle in einer Antwort, kein zusätzlicher Kanalwechsel-Aufruf — bleibt
  unverändert bestehen und wird durch AC-7 unten weiterhin geprüft.

Der Test bei `:285-311` wird entsprechend umgebaut: Statt `calls.count == 1` prüft er
`calls.count == len(locations)` (im dortigen Fall: 2 Orte → 2 Läufe). Der Docstring-Verweis
„AC-7" in `compare_preview_service.py:52-55` wird auf die neue Zusicherung umformuliert.

Die übrigen Tests derselben Datei (`:332`, `:371`, `:400`), die prüfen, dass Tagesfenster und
Vorhersage-Horizont korrekt bei der Engine ankommen, nutzen durchweg Presets mit **einem**
Ort — bei einem Ort ist „einmal je Ort" identisch zu „einmal insgesamt", diese Tests bleiben
unverändert bestehen und müssen nach dem Umbau weiterhin grün sein. Sie sind der Nachweis,
dass beim Aufteilen der Ortsliste in parallele Einzelaufrufe kein Parameter verloren geht.

**🔴 Nachtrag aus der RED-Phase (2026-08-15): der Vertrag sitzt an DREI Stellen, nicht an
einer.** Beim Schreiben der Tests kamen zwei weitere Fundstellen derselben Zusicherung ans
Licht, die diese Spec zunächst übersehen hatte. Beide gehören zu Presets mit **zwei** Orten
und werden mit der Umstellung ebenfalls rot:

| Stelle | Zusicherung heute | nach dem Umbau |
|---|---|---|
| `:231` | `calls.count == 1` (Preset mit 2 Orten) | `== len(locations)` |
| `:232` | beide Orte kommen in **einem** Engine-Aufruf an (`locations_seen[0] == ["loc-ibk","loc-bz"]`) | jeder Aufruf sieht **genau einen** Ort — Prüfung auf die Vereinigung über alle Aufrufe umstellen, Reihenfolge erhalten |
| `:277` | `calls.count == 1` (Preset mit 2 Orten) | `== len(locations)` |

Die Unterscheidung, die diese Spec ursprünglich zu grob getroffen hatte, lautet **nicht**
„`:285-311` gegen den Rest", sondern: **jede** Stelle mit einem Mehr-Ort-Preset trägt den
abgelösten Vertrag, **jede** Stelle mit einem Ein-Ort-Preset nicht. Wer nur die in dieser
Spec zuerst genannte Zeile umbaut, läuft in eine berechtigte Blockade des
Commit-Gates `touched_tests_gate.py`.

## Abgrenzung — was diese Scheibe NICHT umfasst

**Diese Scheibe schließt #1765 nicht.** `ComparisonEngine.run()` hat drei unabhängige
Aufrufstellen im Produktivsystem; diese Scheibe stellt genau eine davon um.

| Aufrufweg | Grenze | in dieser Scheibe? |
|---|---|---|
| Vergleichs-Vorschau (`compare_preview_service.py:163`) | interaktiv, ein Nutzer sieht den Fehler sofort | **ja** |
| Versand (`scheduler_dispatch_service.py:451`, auch der tägliche Cron-Lauf) | läuft unbeaufsichtigt, schreibt Zustand (letzter Versand, Alarm-Anker) | **nein — Folgescheibe B1b** |
| Sofortvergleich (`api/routers/compare.py:71`, öffentlich erreichbar) | interaktiv, aber eigener Aufrufweg | **nein — Folgescheibe B1b** |

Der Grund für den Zuschnitt in zwei Scheiben: Die drei Aufrufwege sind technisch identisch
betroffen, aber ihre Betriebsrisiken unterscheiden sich grundlegend. Die Vorschau läuft in
einer einzelnen, beaufsichtigten Sitzung — schlägt etwas fehl, sieht der Nutzer sofort einen
Fehler und lädt neu. Der Versand läuft unbeaufsichtigt per Cron, unter Umständen für mehrere
Nutzer gleichzeitig, und schreibt dauerhaften Zustand — ein Fehler dort fällt niemandem sofort
auf und kann ein falsches oder ausgefallenes Briefing bedeuten. Eine neu eingeführte
Nebenläufigkeit wird deshalb zuerst im beaufsichtigten, risikoärmeren Pfad erprobt; der
unbeaufsichtigte Pfad bekommt sie erst, wenn der beaufsichtigte sie nachweislich trägt. Der
geteilte Baustein (`comparison_parallel.py`) wird bereits jetzt so gebaut, dass die
Folgescheibe die beiden übrigen Aufrufwege nur noch umhängen muss, statt selbst etwas
umzubauen.

**Ebenfalls nicht Teil dieser Scheibe:**

- Der Nachweis, dass im Versandpfad der „oberste Ort" (`scheduler_dispatch_service.py:460`)
  nach dem Umbau weiterhin korrekt ist — dieser Wert wird direkt aus der Merge-Reihenfolge
  gelesen und braucht deshalb einen eigenen Nachweis im Versandpfad selbst (Folgescheibe).
- Die Frage, ob mehrere gleichzeitig laufende Nutzer-Presets im täglichen Cron-Lauf zusammen
  mit der neuen Ortsparallelität das gemeinsame, ungedrosselte Météo-France-Kontingent
  überlasten können — das lässt sich aus dem Code allein nicht beantworten und wird in der
  Folgescheibe mit echten Betriebsdaten aus dieser Scheibe entschieden.
- Änderungen an `comparison_engine.py` selbst — die Ortsschleife dort bleibt unangetastet.
- U4 (fehlender Grundvorhersage-Cache im Vergleichspfad) — dokumentierte, separate
  Zurückstellung, hilft dem hier behandelten Problem strukturell ohnehin nicht.
- Die Timeout-Grenzen zwischen Go-API und nginx (heute 60 s ohne Puffer) — bei 3–4 parallel
  verarbeiteten Orten liegt die neue Laufzeit bei rund 26 s, deutlich darunter; ein Nachziehen
  der Grenzen ist hier nicht nötig.
- Der Trip-Vorschau-Pfad (#1839) — eigener, getrennter Workflow.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit drei oder mehr Orten, dessen Vorschau bisher wegen
  der Zeitgrenze fehlschlug / When die Vorschau (E-Mail, Telegram oder SMS) für dieses Preset
  angefordert wird / Then liefert die Vorschau innerhalb der Zeitgrenze ein vollständiges
  Ergebnis für alle Orte zurück, statt mit einem Zeitüberschreitungs-Fehler abzubrechen.

- **AC-2:** Given ein Orts-Vergleich mit mehreren Orten, bei dem absichtlich der zuerst
  konfigurierte Ort am längsten und der zuletzt konfigurierte Ort am kürzesten braucht, bis
  seine Wetterdaten vorliegen / When die Vorschau berechnet wird / Then erscheinen die Orte im
  Ergebnis trotzdem in der ursprünglich konfigurierten Reihenfolge, nicht in der Reihenfolge,
  in der ihre Berechnung fertig wurde.

- **AC-3:** Given ein Orts-Vergleich, bei dem für genau einen von mehreren Orten die
  Wetterdaten nicht abrufbar sind / When die Vorschau berechnet wird / Then zeigen die
  übrigen Orte trotzdem ihre vollständigen Wetterdaten, und nur der betroffene Ort erscheint
  mit einer Fehlermeldung — ein einzelner fehlerhafter Ort darf die Vorschau der anderen Orte
  nicht verhindern.

- **AC-4:** Given eine Vergleichs-Vorschau mit mehreren Orten, deren Wetterdaten gleichzeitig
  in getrennten Verarbeitungspfaden abgerufen werden / When jeder dieser Abrufe im internen
  Diagnose-Journal aufgezeichnet wird / Then trägt jeder Eintrag weiterhin korrekt „Vergleich"
  als Herkunft, statt als „unbekannt" verzeichnet zu werden — die Umstellung auf gleichzeitige
  Verarbeitung darf die Nachvollziehbarkeit im Diagnose-Journal nicht verschlechtern.

- **AC-5:** Given eine Vergleichs-Vorschau mit mehreren Orten wird einmal ausgelöst / When alle
  Orte gleichzeitig berechnet werden / Then trägt das fertige Ergebnis genau einen
  „Erstellt am"-Zeitstempel für den gesamten Lauf — nicht einen eigenen Zeitstempel je Ort.

- **AC-6:** Given ein Orts-Vergleich-Preset mit einem bestimmten Tagesfenster und einem
  bestimmten Vorhersage-Zeitraum / When die Vorschau für mehrere Orte gleichzeitig berechnet
  wird / Then rechnet **jeder einzelne** Ort mit exakt demselben Tagesfenster und demselben
  Vorhersage-Zeitraum wie zuvor — keiner der Orte darf beim Aufteilen der Arbeit ein falsches
  oder fehlendes Fenster bekommen.

- **AC-7 (unverändert bleibt):** Given ein Orts-Vergleich mit mehreren Orten in einer vom
  Nutzer festgelegten Reihenfolge / When die Vorschau als E-Mail, als Telegram-Nachricht, als
  SMS-Text und in der Weboberfläche dargestellt wird / Then erscheinen die Orte in allen vier
  Darstellungen weiterhin in genau der vom Nutzer festgelegten Reihenfolge — unverändert
  gegenüber dem heutigen Verhalten.

- **AC-8 (unverändert bleibt):** Given eine Anfrage an die Vergleichs-Vorschau, die heute mit
  „Preset nicht gefunden", „ungültige Eingabe" oder „Wetterdaten aktuell nicht verfügbar"
  beantwortet wird / When dieselbe Anfrage nach dieser Umstellung erneut gestellt wird / Then
  bleibt die Fehlermeldung in Form und Inhalt identisch zu vorher.

- **AC-9 (unverändert bleibt, Scheibe-A-Ratsche):** Given eine Vergleichs-Vorschau mit
  mehreren Orten wird gerade berechnet / When währenddessen der allgemeine
  Erreichbarkeits-Check des Dienstes aufgerufen wird / Then antwortet dieser weiterhin sofort
  und erfolgreich — die neue gleichzeitige Ortsverarbeitung darf die mit Scheibe A bereits
  hergestellte Erreichbarkeit während einer laufenden Vorschau nicht wieder aufheben.

## Testplan

**Schicht:** ausschließlich Kern (deterministisch, kein Netz, keine Live-Dienste) — passend
zur Test-Politik dieses Repos. Mock-Theater (`Mock()`/`patch()`/`MagicMock`, die nur die
eigene Annahme zurückspiegeln) und Dateiinhalt-Prüfungen als Verhaltensnachweis sind
verboten. Für AC-2 ist eine künstliche, unterschiedlich lange Verzögerung je Ort **legitim
und notwendig** — nur so lässt sich die Fertigstellungsreihenfolge gezielt gegen die
Einreichungsreihenfolge drehen; ohne diese Drehung würde der Test auch bei falscher
Merge-Logik zufällig grün sein.

**Neue Testdateien:**

- `tests/unit/test_comparison_parallel.py` — Nachweise für AC-2 (Reihenfolge bei gedrehter
  Fertigstellung, gestubbte `ComparisonEngine.run`), AC-3 (ein Ortsfehler reißt die anderen
  nicht mit), AC-5 (genau ein `created_at` für den gesamten Lauf), AC-6 (Tagesfenster und
  Vorhersage-Zeitraum kommen bei jedem Ort einzeln geprüft an, nicht nur beim ersten).
- `tests/unit/test_call_source_ueber_threadgrenze.py` — Nachweis für AC-4: mindestens zwei
  gleichzeitig laufende Verarbeitungspfade, jeder protokolliert einen Abruf; geprüft wird die
  tatsächlich im Journal verzeichnete Quelle je Eintrag, nicht die bloße Anwesenheit der
  Override-Funktion im Quelltext.

**Geänderte Bestandsdatei:**

- `tests/tdd/test_compare_preview_service.py:285-311` — Umbau der abgelösten Zusicherung
  (`calls.count == 1` → `calls.count == len(locations)`), wie oben unter „Ein abzulösender
  Bestandsvertrag" beschrieben. Die Tests bei `:332`, `:371`, `:400` bleiben unverändert und
  müssen nach dem Umbau weiterhin grün sein (Ein-Ort-Presets — dort ist „je Ort" identisch zu
  „insgesamt").

**Wirkungs-Nachweis für AC-1 — über eine Treffpunkt-Sperre, NICHT über die Uhr.**
Der naheliegende Test („Gesamtdauer liegt nahe der längsten Einzeldauer statt nahe der
Summe") misst Wanduhr-Zeit und wäre auf einem ausgelasteten CI-Läufer flakeanfällig: er
würde gelegentlich rot, ohne dass etwas kaputt ist, und träfe damit genau die Sorte
Testfehler, die man später ignoriert statt untersucht.

Stattdessen wird die **Gleichzeitigkeit selbst** geprüft, deterministisch und uhrunabhängig:
Der Nachweis nutzt eine Treffpunkt-Sperre (`threading.Barrier(n)`) — jeder der n Orte meldet
sich beim Betreten seiner Berechnung an und wartet, bis **alle** n angekommen sind. Läuft die
Verarbeitung nacheinander, erreicht der zweite Ort den Treffpunkt nie, weil der erste dort
noch wartet: die Sperre läuft in ihre Zeitschranke und der Test wird rot. Läuft sie
gleichzeitig, lösen alle n den Treffpunkt gemeinsam auf und der Test wird grün. Es gibt
keinen Zwischenzustand, der zufällig grün werden könnte. Dasselbe Muster ist im Repo bereits
erprobt: `tests/unit/test_timezone_singleton_threadsicher.py:72-124`.

Zusätzlich zu prüfen: Bei **einem** Ort und bei einer **leeren** Ortsliste darf der Baustein
nicht in eine Sperre laufen und muss sich wie heute verhalten (`min(len(locations), 4)` mit
`len == 0` ist ein ungültiger Wert für die Arbeiterzahl — der Fall muss abgefangen sein,
Vorbild `stage_weather.py:172` prüft `if flat:` vor dem Aufbau des Executors).

**Mutations-Gegenprobe (PFLICHT im TDD-RED-Schritt):** mindestens diese Verfälschungen
müssen je mindestens einen Test rot machen:

1. Die indexierte Rückgabe (`fetched[idx] = …`) wird versuchsweise durch ein Anhängen bei
   Fertigstellung ersetzt → AC-2-Test muss rot werden.
2. Die Fehlerkapselung je Ort im Wrapper wird versuchsweise entfernt → AC-3-Test muss rot
   werden (ein Ortsfehler wirft dann durch und reißt den gesamten Lauf mit).
3. Das Setzen der Diagnose-Quelle im jeweiligen Verarbeitungspfad wird versuchsweise
   weggelassen → AC-4-Test muss rot werden (Journal verzeichnet „unbekannt" statt
   „Vergleich").
4. `created_at` wird versuchsweise je Ort statt einmal vor dem Start berechnet → AC-5-Test
   muss rot werden.
5. Der Executor wird versuchsweise auf einen einzigen Arbeiter gesetzt (`max_workers=1`,
   also faktisch wieder nacheinander) → der AC-1-Test muss rot werden. Diese Mutation ist
   die wichtigste: Sie prüft, ob der Nachweis die **Wirkung** bewacht (gleichzeitige
   Verarbeitung) oder nur das Vorhandensein von Code, der so aussieht.

Mutationen ausschließlich per String-Ersetzung mit externer Sicherungskopie, nie per
`git checkout`/`stash`/`reset`.

## Known Limitations

- **Thundering-Herd-Risiko bei den national geschlüsselten Warndiensten für Frankreich und
  Italien wird in dieser Scheibe NICHT behoben, nur benannt.** Die amtlichen Warndienste für
  Italien und Frankreich cachen ihre Ergebnisse heute mit einem einzigen, für alle Orte
  gemeinsamen Schlüssel, ungesichert gegen gleichzeitigen Zugriff. Solange die Orte
  nacheinander verarbeitet wurden, traf in der Regel nur der erste Ort auf einen leeren
  Zwischenspeicher, alle folgenden Orte fanden bereits ein Ergebnis vor. Bei gleichzeitiger
  Verarbeitung sehen mehrere Orte denselben leeren Zwischenspeicher gleichzeitig und lösen
  redundante Abrufe gegen denselben amtlichen Dienst aus — gegen ein Tageskontingent, das
  zwar begrenzt und dagegen abgesichert ist, aber dadurch schneller ausgeschöpft würde als
  nötig. Betrifft nur Orte in Frankreich und Italien, nicht den Karnischen Höhenweg
  (Österreich/Deutschland). Kein Datenverlust und keine falsche Anzeige — eine unnötige
  Lastspitze. Details: Kontextdokument, Risiko R7.
- **Die Cron-Überlagerungsfrage (mehrere Nutzer-Presets gleichzeitig gegen dasselbe
  Météo-France-Kontingent) ist aus dem Code allein nicht beantwortbar** und wird bewusst der
  Folgescheibe überlassen, in der sie erstmals auftritt (Versandpfad).
- **`comparison_engine.py` bleibt unverändert.** Die Ortsschleife dort läuft weiterhin
  nacheinander innerhalb eines einzelnen Aufrufs mit genau einem Ort — die Parallelität
  entsteht ausschließlich außerhalb, im neuen Baustein.
- 🔴 **AC-9 ist im Kern NICHT eigenständig nachgewiesen — der Beleg gehört auf Staging.**
  Der zugeordnete Test `tests/unit/test_event_loop_bleibt_frei.py:160` stammt **unverändert**
  aus Scheibe A (`git diff` gegen den Abzweigpunkt ist leer). Er ersetzt
  `preview.ComparePreviewService` **vollständig** durch einen Schlaf-Stub und prüft damit nur,
  dass der Router-Handler `def` bleibt und Starlette ihn in den Threadpool legt — den neuen
  `ThreadPoolExecutor` berührt er nie. Er kann eine Regression, die **gerade** durch die neue,
  verschachtelte Nebenläufigkeit entstünde, strukturell nicht sehen. Das ist erneut
  Prüfort ≠ Wirkort, diesmal geerbt statt neu gebaut.
  **Bewusst nicht durch einen weiteren Kern-Test geschlossen:** Ein Kern-Test müsste den
  Threadpool erneut nachbauen und würde wieder nur den Nachbau prüfen. Der Wirkort ist der
  laufende Dienst. **Verbindliche Folge: Die Staging-Verifikation dieser Scheibe MUSS
  `/api/health` WÄHREND einer echten Vergleichs-Vorschau mit 3+ Orten abfragen** und das
  Ergebnis in der Attestation festhalten. Ohne diese Messung gilt AC-9 als unbelegt, nicht
  als erfüllt.
- **Grenze der Systemfehler-Erkennung (Adversary-Runde 3, 2026-08-15).** Scheitern **alle**
  Orte mit einer Ausnahme, gilt die Störung als systemisch und die Ausnahme des Orts mit dem
  **niedrigsten Index** wird weitergereicht (→ 503). Werfen dabei verschiedene Orte
  Ausnahmen **verschiedenen Typs** — zwei zeitgleiche, voneinander unabhängige systemische
  Ursachen —, entscheidet damit der erste konfigurierte Ort über die Fehlerart; ein
  `ValueError` dort ergäbe 422 statt 503. Kein AC fordert für diesen Fall eine Antwort, und
  vor dem Umbau konnte er nicht auftreten (ein Engine-Lauf für alle Orte kannte nur *einen*
  Fehler). **Nicht zufällig, sondern deterministisch:** Die Einsammel-Schleife iteriert über
  `future_to_idx.items()` — Einreichungsreihenfolge, nicht Fertigstellungsreihenfolge. Über
  fünf Wiederholungsläufe mit gedrehter Fertigstellung kam stets dieselbe Ausnahme heraus.
  Die Fehlermeldung an den Nutzer schwankt also nicht zwischen zwei Aufrufen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** ADR-0015 (Python-Core ist Owner der Wetter-Domäne) deckt diese
  Parallelisierung ab — derselbe Präzedenzfall wie bei der bereits umgesetzten
  Etappen-Wetter-Parallelisierung (`docs/specs/modules/stage_weather_python_endpoint.md:126-129`).
  Es existiert kein eigenes ADR zu Nebenläufigkeit im Python-Core, das dieser Fix umgehen oder
  ablösen würde. Die Umsetzung „außen" (neuer Baustein, `comparison_engine.py` unangetastet)
  vermeidet bewusst eine Änderung innerhalb der Engine selbst, die Versand und Alarme
  mitträfe und damit ADR-würdig wäre.

## Changelog

- 2026-08-15: Initial spec created (Scheibe B1 von #1765; schließt das Ticket nicht — Scheibe
  B1b folgt für Versand und Sofortvergleich)
