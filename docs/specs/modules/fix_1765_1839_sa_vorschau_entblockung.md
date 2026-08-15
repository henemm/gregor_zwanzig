---
entity_id: fix_1765_1839_sa_vorschau_entblockung
type: module
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [bug, performance, preview, python-core, issue-1765, issue-1839]
---

# Vorschau-Entblockung: Handler ohne `await` + abgesicherte Zeitzonen-Lazy-Init (Scheibe A, #1765 + #1839)

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-15 auf AC-1 bis AC-4

## Purpose

Während eine E-Mail-, SMS-, Telegram- oder Vergleichs-Vorschau berechnet wird, ist der
gesamte Python-Core heute **taub** — `/api/health` antwortet nicht, andere Nutzer bekommen
keine Antwort, und ein einzelner langsamer Vorschau-Aufruf sieht von außen wie ein
Dienstausfall aus (das hat am 2026-08-12 einen unnötigen Neustart von
`gregor-python-staging` ausgelöst). Scheibe A beseitigt die **Ursache** dieser Blockade: 13
Route-Handler sind als `async def` deklariert, obwohl sie kein `await` enthalten und damit
im Event-Loop-Thread statt im Threadpool laufen.

**Scheibe A macht die Vorschau NICHT schnell** — dazu siehe „Abgrenzung zu Scheibe B" unten.
Sie sorgt dafür, dass eine laufende Vorschau den restlichen Dienst nicht mehr lahmlegt und
beendet damit die Fehlalarme der Überwachung, die schon einmal zu einem unnötigen
Dienstneustart geführt haben. **Das ist ein eigenständiger Gewinn, keine Vorstufe zu etwas
Größerem** — Scheibe A liefert ihn vollständig und für sich genommen aus.

Ä1 hat eine Nebenwirkung, die Teil der Spezifikation ist, nicht nur eine Randnotiz: Die 13
Handler waren bisher als `async def` ohne `await` faktisch **serialisiert** — der blockierte
Event-Loop ließ eine zweite gleichzeitige Vorschau-Anfrage erst beginnen, wenn die erste
fertig war. Genau das ist der zu behebende Fehler. Sobald diese Handler `def` sind, laufen
sie im Threadpool und damit **erstmals wirklich gleichzeitig** — jeder gemeinsame,
veränderliche Zustand, der bisher durch die zufällige Serialisierung geschützt war, wird ab
Ä1 tatsächlich parallel erreicht. Scheibe A umfasst deshalb eine zweite Änderung Ä3, die den
einzigen dabei gefundenen ungeschützten Zustand absichert (siehe „Nebenwirkung von Ä1" unten).

**Scheibe A besteht aus genau Ä1 + Ä3, sonst nichts.** Eine ursprünglich vorgesehene dritte
Änderung (eigene Abrufpolitik für die Trip-Vorschau, vormals „Ä2") ist **vollständig nach
Scheibe B verschoben** — Grund und Beleg dafür stehen in „Abgrenzung zu Scheibe B" unten.

## Source

- **File:** `api/routers/preview.py` · `api/routers/internal.py` · `api/routers/validator.py` ·
  `api/routers/notify.py` (Ä1) · `src/utils/timezone.py` (Ä3)
- **Identifier:** 13 Route-Handler (Liste unten) · `_get_tf()` (`src/utils/timezone.py:23`)

## Estimated Scope

- **LoC:** ~15 (Produktivcode, ohne Tests) — Ä1 ist reine Schlüsselwort-Entfernung, Ä3 ist
  eine ~6-Zeilen-Ergänzung nach vorhandenem Muster (Lock-Import, Modul-Lock, doppelt geprüfte
  Sperre)
- **Files:** 5 Produktivdateien (4 Router + `timezone.py`) + neue Testdatei(en)
- **Effort:** low (Ä1 ist mechanisch, kein `await` vorhanden, das brechen könnte; Ä3 kopiert
  ein im Repo dreifach vorhandenes Muster wortgleich)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Starlette-Threadpool (anyio, Framework-Default) | Laufzeitverhalten | `def`-Handler laufen automatisch im Threadpool; keine Konfigurationsänderung nötig, siehe „Risiken" |
| Doppelt-geprüfte-Sperre-Muster (`src/services/weather_cache.py:300-305` `get_shared_weather_cache()`, wortgleich in `src/providers/thunder_window_cache.py:158-163`, `src/services/radar_cache.py:115-119`) | pattern | Ä3 kopiert dieses im Repo dreifach vorhandene Muster für `_get_tf()`; kein neues Muster erfinden |

## Implementation Details

### Ä1 — 13 Route-Handler von `async def` zu `def`

Kein einziger der folgenden Handler enthält ein `await` (zweifach gemessen: statisch per AST
über den `api/`-Baum und zur Laufzeit an `app.routes` via `inspect.iscoroutinefunction`,
Kontextdokument `docs/context/fix-1765-1839-vorschau-laufzeit.md`). Die Änderung ist in jedem
Fall identisch: `async def` → `def`, keine weitere Anpassung im Funktionskörper.

| Datei:Zeile | Handler |
|---|---|
| `api/routers/preview.py:30` | `preview_email` |
| `api/routers/preview.py:56` | `preview_sms` |
| `api/routers/preview.py:86` | `preview_compare` |
| `api/routers/preview.py:129` | `preview_telegram` |
| `api/routers/internal.py:30` | `loaded_trip` |
| `api/routers/internal.py:56` | `stages_weather` |
| `api/routers/validator.py:167` | `format_metric` |
| `api/routers/validator.py:181` | `detector_thresholds` |
| `api/routers/validator.py:244` | `alert_preview` |
| `api/routers/validator.py:272` | `metrics_for_channel` |
| `api/routers/validator.py:317` | `compare_email_preview` |
| `api/routers/validator.py:339` | `sms_fidelity_preview` |
| `api/routers/notify.py:19` | `test_notify` |

**Nicht anfassen:** `api/routers/gpx.py:23 parse_gpx` — einziger Handler mit echtem `await`
(`await file.read()`, Zeile 36) und bleibt deshalb `async def`.

Nach Ä1 ist der Hausstil **einheitlich**: alle Route-Handler ohne `await` sind `def`, der
einzige verbleibende `async def`-Handler nutzt `await` tatsächlich.

### Nebenwirkung von Ä1 — Scheibe A führt erstmals echte Nebenläufigkeit im Anfragepfad ein

Bevor der Umfang dieser Scheibe festgelegt wurde, ist **nach `global`-Anweisungen in `src/`
und `api/` gesucht** worden, um zu prüfen, welcher geteilte, veränderliche Zustand von der
neuen Nebenläufigkeit aus Ä1 betroffen sein könnte.

**Reichweite dieser Suche — Korrektur nach Adversary-Lauf am 2026-08-15 (F002):** Hier stand
zunächst, es seien „alle `global`-Anweisungen durchgesehen" worden und außer `_get_tf()` sei
nichts Offenes zurückgeblieben. Diese Vollständigkeitsaussage ging zu weit und ist widerlegt.
Eine Suche nach dem Schlüsselwort `global` findet **prinzipiell** eine ganze Klasse geteilten
Zustands nicht: Dekorator-basierte Zwischenspeicher (`functools.lru_cache`, `functools.cache`),
Klassenattribute und veränderliche Standardargumente kommen ohne `global` aus. Genau ein Fall
dieser Klasse liegt im umgestellten Pfad (`_lookup_department_cached()`, Zeile unten) und wurde
von der ursprünglichen Suche übersehen. Die Tabelle ist deshalb **kein** Vollständigkeitsbeweis,
sondern eine Liste geprüfter Stellen — die beiden zuletzt aufgenommenen Zeilen stammen aus dem
Adversary-Lauf, nicht aus der ursprünglichen Durchsicht.

| Stelle | Zustand | Bewertung |
|---|---|---|
| `src/services/weather_cache.py:300-305` `get_shared_weather_cache()` | doppelt geprüfte Sperre | sicher |
| `src/providers/thunder_window_cache.py:158-163` `get_shared_thunder_window_cache()` | doppelt geprüfte Sperre | sicher |
| `src/services/radar_cache.py:115-119` `get_shared_radar_cache()` | doppelt geprüfte Sperre | sicher |
| **`src/utils/timezone.py:23-29` `_get_tf()`** | **Lazy-Singleton OHNE Sperre** | **muss repariert werden → Ä3** |
| `_warned_missing_key` in `src/services/official_alerts/vigilance.py:63`, `meteoalarm.py:496`, `meteo_forets.py:63` | „einmal warnen"-Merker ohne Sperre | unkritisch, **nicht** angefasst — schlimmstenfalls wird eine Warnung doppelt protokolliert |
| `api/routers/webhook.py:57` `telegram_webhook`, `api/routers/scheduler.py:174` `trigger_inbound_telegram` | Lazy-Singletons ohne Sperre | **nicht** angefasst, bewusste Abgrenzung — diese Handler sind bereits heute `def` und damit schon vor Scheibe A nebenläufig erreichbar; Ä1 verursacht dieses Bestandsrisiko nicht und vergrößert es nicht |
| `src/services/official_alerts/department_mapper.py:335-336` `_lookup_department_cached()` — **von der `global`-Suche strukturell nicht auffindbar** (`@functools.lru_cache`, kein `global`) | prozessweiter Zwischenspeicher ohne eigene Sperre | **geprüft, unkritisch — nicht angefasst.** Erreichbar aus dem umgestellten `preview_compare`: `comparison_engine.py:322` → `get_official_alerts_with_status()` (`official_alerts/base.py:90`) → `lookup_department()` (`department_mapper.py:376`, dort Zeile 411) → `_lookup_department_cached()`. Der Pfad ist im Normalfall aktiv (`official_alerts_enabled` steht auf `True`, `comparison_engine.py:104`). `lru_cache` ist in CPython intern abgesichert; ein Wettlauf führt zu **doppelter Berechnung**, nicht zu Datenverfälschung oder verfälschtem Cache-Inhalt — dieselbe Risikoklasse, die diese Spec bei `_get_tf()` (dort: zwei kurzzeitige `TimezoneFinder`-Instanzen) ohnehin als unkritisch einstuft und nur wegen der 12-MB-Größe repariert. Hier fehlt dieser Größen-Anlass. |
| `src/app/egress_guard.py:139-140` `install_egress_guard()` (`_installed`, `_orig_*`) | Modul-Globals ohne Sperre | **geprüft, unkritisch — nicht angefasst.** Läuft einmalig in `lifespan()` (`api/main.py:96`), also **bevor** die Anwendung Anfragen annimmt; zur Laufzeit schreibt niemand mehr in diese Globals. Ä1 macht die Stelle nicht neu erreichbar. |

`_get_tf()` bleibt das einzige durch Ä1 neu erreichbare Risiko, das **repariert** wird (→ Ä3).
Alles andere ist entweder bereits abgesichert, ein Bestandsrisiko außerhalb dieser Scheibe oder
— wie die beiden zuletzt aufgenommenen Zeilen — geprüft und in der Wirkung folgenlos.

### Ä3 — `_get_tf()` in `src/utils/timezone.py` gegen gleichzeitige Erstinitialisierung absichern

`src/utils/timezone.py:23-29` lädt `TimezoneFinder` (~12 MB) beim ersten Aufruf und schreibt
das Ergebnis in das ungeschützte Modul-Global `_tf_instance`:

```python
_tf_instance = None

def _get_tf():
    """Lazy singleton — TimezoneFinder loads ~12MB on first call."""
    global _tf_instance
    if _tf_instance is None:
        from timezonefinder import TimezoneFinder
        _tf_instance = TimezoneFinder()
    return _tf_instance
```

Treffen zwei Threads gleichzeitig auf `_tf_instance is None` (z. B. zwei parallele
Vorschau-Anfragen, die beide `tz_for_coords()` bzw. `location_tz()` aufrufen), sehen **beide**
`None` und bauen je eine eigene `TimezoneFinder`-Instanz — ein kurzzeitiger 24-MB-Ausschlag,
eine der beiden Instanzen wird kommentarlos verworfen. Keine Datenverfälschung (beide
Instanzen liefern dieselbe Antwort), aber vermeidbar — und genau die Klasse Fehler, die eine
neu eingeführte Nebenläufigkeit nicht unbeaufsichtigt mitliefern darf.

Betroffen sind **beide** Vorschau-Pfade: Trip über `tz_for_coords()` →
`preview_service.py:180`, Vergleich über `location_tz()` → `comparison_engine.py:155`. Die
Funktion liegt also mitten im Vorschau-Pfad, nicht daneben.

Reparatur — doppelt geprüfte Sperre, wortgleich zum Muster in
`weather_cache.py:300-305` (kein neues Muster erfinden):

```python
from threading import Lock
# ...
_tf_instance = None
_tf_lock = Lock()

def _get_tf():
    """Lazy singleton — TimezoneFinder loads ~12MB on first call.
    Thread-safe (double-checked locking, Muster weather_cache.py:300-305)."""
    global _tf_instance
    if _tf_instance is None:
        with _tf_lock:
            if _tf_instance is None:
                from timezonefinder import TimezoneFinder
                _tf_instance = TimezoneFinder()
    return _tf_instance
```

## Expected Behavior

- **Input:** unverändert — dieselben Endpunkte, dieselben Query-/Body-Parameter wie heute.
- **Output:** unverändert in Inhalt, Statuscode und Fehlerform (siehe AC-3). Verändert ist
  ausschließlich, *wie* der Prozess während der Berechnung reagiert (Nebenläufigkeit).
- **Side effects:** keine neuen fachlichen Seiteneffekte. Ä1 ändert nur die Ausführungsebene
  (Threadpool statt Event-Loop), keine Logik. Ä3 ändert an der Rückgabe von `_get_tf()`
  nichts — sie liefert weiterhin dieselbe (Prozess-weite) `TimezoneFinder`-Instanz, jetzt
  aber garantiert nur eine statt gelegentlich zwei.

## Abgrenzung zu Scheibe B

Scheibe A entblockt nur den Prozess (Ä1) und sichert die dadurch neu entstehende
Nebenläufigkeit ab (Ä3) — sie macht die Vorschau **nicht schnell genug**. Gemessen wurden
25,1–25,6 s je Ort im Vergleich und 121 s kalt beim Trip. Nach Scheibe A reißt die
Trip-Vorschau weiterhin die 30-s-Grenze des Go-Weiterleiters
(`internal/handler/preview_proxy.go:81`) und der Vergleich bei 3 Orten weiterhin die
60-s-Grenze von nginx — **das ist so beabsichtigt**, nicht ein offener Mangel dieser Scheibe.
Die eigentliche Beschleunigung (U3, Parallelisierung der Orts-/Segmentschleife nach dem
Vorbild `stage_weather.py:173`) ist Gegenstand einer eigenen, separaten Spec für Scheibe B
und **nicht** Teil dieser Spezifikation.

**Eine eigene, schlanke Abrufpolitik für die Trip-Vorschau (ursprünglich als „Ä2" für
Scheibe A vorgesehen) gehört vollständig zu Scheibe B, nicht hierher.** Grund: Alle drei
Codestellen, über die eine Trip-Vorschau tatsächlich Wetter abruft, wurden nachgemessen und
nachgezählt (Kontextdokument, N1/N2, Fenster 12:57:49–12:59:50 UTC, störungsfrei):

| Aufrufstelle | Segmente | Dauer (N1) | Wiederholversuche heute |
|---|---|---|---|
| `preview_service.py:173` (Hauptabruf, heutige Etappe) | 2 | 12,3 s / 12,1 s | bis zu 3, über `_fetch_weather` |
| `preview_service.py:238` → `_build_stage_trend()` → `_fetch_weather` (`trip_report_scheduler.py:2254`), Ausblick +1/+2 Tage | 4 | 25,4 / 25,9 / 10,1 / 10,1 s | bis zu 3, über `_fetch_weather` |
| `fetch_night_weather()` (`segment_weather.py:424`), Nachtwetter | 1 | 24,6 s | **keine** — direkter Aufruf, hatte nie eine Retry-Schleife |

Mittel ~17,3 s, Summe 120,46 s von 121,14 s Gesamtzeit. Kostentreiber ist **nicht** der
HTTP-Abruf (< 50 ms Antwortzeit), sondern die DWD-Gewitter-Anreicherung je Segment.

Eine Vorschau-eigene Abrufpolitik, die nur die erste Zeile dieser Tabelle abdeckt (2 von 7
Segmenten), träfe genau die **falschen** zwei — die vier Ausblicks-Segmente in Zeile 2 sind
die langsamsten (25,4–25,9 s) und stellen den größten Teil der Gesamtzeit. Deshalb drei
Festlegungen für Scheibe B statt eines Teil-Fixes in Scheibe A:

- **(a) Scheibe B muss alle drei Aufrufstellen erfassen, sonst verfehlt sie ihr Ziel.** Eine
  Nahtstelle, die 2 von 7 Abrufen abdeckt und ausgerechnet die vier langsamsten ausspart,
  trägt weder die Beschleunigung noch die Retry-Straffung.
- **(b) `_build_stage_trend()` ist geteilter Code zwischen Vorschau
  (`preview_service.py:238`) und Versand (`trip_report_scheduler.py:1398`)** — sein interner
  `_fetch_weather`-Aufruf verlangt dieselbe Vorsicht wie eine direkte Änderung an
  `_fetch_weather` selbst (6 Produktiv-Aufrufer, 4 davon Versand/Alarme). Der Zuschnitt „außen"
  (Parallelisierung/Retry-Straffung um den bestehenden Aufruf herum, ohne den geteilten
  Funktionskörper zu verändern) ist entsprechend zu wählen — dasselbe Prinzip, das für
  `ComparisonEngine.run()` bereits als Variante V3 „außen" gewählt wurde.
- **(c) Die ~26-s-Schätzung unten gilt nur bei flacher Parallelisierung über alle sieben
  Abrufe.** Bleiben die vier Ausblicks-Segmente seriell, landet die Trip-Vorschau weiterhin
  bei über 100 s — die Beschleunigung fiele aus, unabhängig davon, was mit den übrigen drei
  Abrufen passiert. Der Ausblickspfad ist damit keine Restarbeit, die man später nachreicht,
  sondern eine **harte Voraussetzung** von Scheibe B.

**Vertrags-Detail für Scheibe B, aus der Analyse dieser Spec übernommen:** Welche
Umgestaltung Scheibe B auch wählt — ein gescheitertes Segment muss weiterhin ein
`SegmentWeatherData`-Objekt mit `has_error=True` an seiner Position liefern
(`trip_report_scheduler.py:2018-2026`), **nicht** ausgelassen werden. Sonst ändert sich die
Länge/Form der Rückgabeliste gegenüber heute, und nachgelagerte Verarbeitung (Renderer,
Fehlerbehandlung) bricht.

- **Die Sorge „Parallelisierung allein reicht nicht" ist widerlegt** — unter Annahme (c).
  Parallelisiert läge die Gesamtzeit bei etwa dem **langsamsten Einzelsegment**, also
  **~26 s** — unter der 30-s-Grenze des Go-Weiterleiters.
- **Aber die Reserve ist dünn** (~26 von 30 s, rund **87 %** des Budgets). Deshalb wird die
  Timeout-Leiter in Scheibe B **doch** nachgezogen — nicht um einen Fehler zu verstecken,
  sondern als Sicherheitsabstand, **nachdem** die Beschleunigung greift und die neue Laufzeit
  bekannt ist. Reihenfolge: erst schneller, dann Luft schaffen. In **Scheibe A** bleibt die
  Leiter unangetastet — sie jetzt anzuheben, während die Trip-Vorschau kalt noch 121 s
  braucht, ließe den Nutzer **länger auf denselben Fehler** warten, messbar schlechter statt
  besser.

**U4 (fehlender Grundvorhersage-Cache im Vergleichspfad)** bleibt außen vor. Das ist eine
dokumentierte, bewusste Zurückstellung aus
`docs/specs/modules/fix_1329_forecast_cache_budget.md:399-407`, keine neue Entscheidung
dieses Workflows.

## Acceptance Criteria

- **AC-1 (Kernzusicherung — der Dienst bleibt während einer Vorschau erreichbar):** Given eine
  Vorschau (Trip- oder Vergleichs-) wird gerade im Python-Core berechnet / When während dieser
  laufenden Berechnung `/api/health` aufgerufen wird / Then antwortet `/api/health`
  durchgehend innerhalb von 2 Sekunden mit Erfolg — nicht erst nach Abschluss der Vorschau.
  Heute gemessen: 74,5 von 75,8 Sekunden lang stumm (25 Timeouts in Folge).
  - Test: Kern-Test mit einer künstlich langsamen Vorschau-Stub-Funktion; `/health` wird
    nebenläufig aus einem zweiten Thread abgefragt, während die Vorschau läuft.

- **AC-2 (Vollständigkeit der Klasse — kein blockierender Handler bleibt übrig):** Given die
  vollständig gebaute FastAPI-Anwendung mit allen registrierten Routen / When jede Route
  darauf geprüft wird, ob ihr Handler eine Koroutine ist (`inspect.iscoroutinefunction`) /
  Then ist **kein** Route-Handler mehr eine Koroutine, mit genau einer Ausnahme: der
  GPX-Upload-Handler, der weiterhin echtes `await` nutzt und deshalb `async def` bleiben darf.
  - Test: Kern-Test iteriert `app.routes` und prüft die Eigenschaft an der laufenden
    Anwendung, nicht am Quelltext — sonst würde nur die Schreibweise geprüft, nicht die
    Wirkung.

- **AC-3 (keine Verhaltensänderung der Vorschau-Inhalte):** Given dieselbe Anfrage an einen der
  13 umgestellten Endpunkte mit denselben Eingaben und denselben Fixture-Daten wie vor der
  Umstellung / When die Anfrage nach der Umstellung erneut gestellt wird / Then sind
  Statuscode und Antwortkörper identisch — sowohl im Erfolgsfall als auch in den
  Fehlerfällen 404 (nicht gefunden), 422 (ungültige Eingabe) und 503 (Wetterdaten nicht
  verfügbar).
  - Test: Bestehende Regressionssuite `tests/tdd/test_epic_140_preview_endpoints.py` (und
    verwandte Preview-Tests) bleibt vollständig grün, ergänzt um einen Fehlerfall-Test je
    Statuscode, falls die Bestandssuite eine der drei Fehlerformen noch nicht abdeckt.

- **AC-4 (Zeitzonen-Datenbank wird bei gleichzeitigem Zugriff nur einmal geladen):** Given
  zwei Threads rufen gleichzeitig zum allerersten Mal eine Funktion auf, die eine Zeitzone zu
  Koordinaten auflöst (`tz_for_coords()` bzw. `location_tz()`) / When beide Aufrufe exakt
  gleichzeitig auf den noch leeren Zustand treffen / Then wird die zugrunde liegende
  Zeitzonen-Datenbank (`TimezoneFinder`) **genau einmal** aufgebaut, und beide Threads
  erhalten dieselbe Instanz zurück.
  - Test: Kern-Test mit zwei Threads und einer Barriere, die beide Threads erst gleichzeitig
    auf `_tf_instance is None` treffen lässt (deterministisch, kein Zufalls-Timing); ein
    Zähler auf der `TimezoneFinder`-Konstruktion muss danach exakt `1` sein. Ein Test, der
    nur prüft, dass irgendeine Sperre *existiert*, zählt nicht — geprüft wird die Wirkung
    (Aufrufzähler), nicht die Anwesenheit von `Lock()` im Quelltext.

## Testplan

**Schicht:** ausschließlich Kern (deterministisch, kein Netz, keine Live-Dienste,
kein Staging-Zugriff) — passend zur Test-Politik dieses Repos. Mock-Theater
(`Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme zurückspiegeln) und
Dateiinhalt-Prüfungen (`assert "def " in datei.read_text()`) als Verhaltensnachweis sind
verboten. Ein Test, der nur die Funktionssignatur im Quelltext prüft, ist wertlos — geprüft
werden muss an der Stelle, an der die Zusicherung **wirkt**: der laufende Server-Thread
(AC-1, AC-2) bzw. die tatsächliche Aufrufzahl der `TimezoneFinder`-Konstruktion (AC-4), nicht
die Schreibweise im Quelltext.

**Bauplan für AC-1 (bereits prototypisch nachgewiesen, netzfrei, ~7 s Laufzeit):** zwei
identische Mini-Apps, uvicorn je in einem eigenen Thread gestartet — eine mit `async def` +
blockierender Arbeit (heutiger Zustand, Kontrollgruppe), eine mit `def` + identischer
blockierender Arbeit (Zielzustand). Während die blockierende Arbeit läuft, wird `/health`
gepollt. Gemessen im Prototyp: `async def` → Timeout nach 2,02 s; `def` → HTTP 200 nach
0,03 s. Dieser Aufbau ist der Bauplan für den RED-Test.

**Alternative, plausibel aber NICHT verifiziert:** eine gemeinsame `FastAPI()`-Instanz mit
**einem** `TestClient`, bei der der Vorschau-Dienst per Monkeypatch auf einen künstlich
langsamen Stub zeigt und `/health` aus einem zweiten Thread nebenläufig abgefragt wird,
während der erste Thread die langsame Vorschau anstößt. Diese Variante ist eleganter (eine
App statt zwei), aber **ungeprüft** — sie wird hier als Option genannt, nicht als Vorgabe.

**Falle, die im TDD-RED-Schritt explizit auszuschließen ist:** Werden **zwei** getrennte
`TestClient`-Instanzen verwendet (eine für die Vorschau, eine für `/health`), bekommt jede
ihren eigenen Event-Loop — die langsame Anfrage liefe dann isoliert vom `/health`-Aufruf, und
der Test würde **still immer grün** sein, unabhängig davon, ob `async def` oder `def`
verwendet wird. Das ist keine Randnotiz, sondern der Punkt, an dem der Test im RED-Schritt
beweisen muss, dass er beim heutigen `async def`-Zustand tatsächlich rot wird.

**Mutations-Gegenprobe (PFLICHT):** Mindestens diese zwei gezielten Verfälschungen müssen
je mindestens einen Test rot machen:

1. Ein Handler (z. B. `preview_email`) wird versuchsweise wieder zu `async def` gemacht →
   AC-1- und/oder AC-2-Test muss rot werden.
2. Die Sperre in `_get_tf()` wird versuchsweise wieder entfernt (Rückbau auf den
   unverriegelten Lazy-Singleton von oben) → AC-4-Test muss rot werden (Konstruktions-Zähler
   > 1 bei den beiden gleichzeitigen Aufrufen).

Mutationen ausschließlich per String-Ersetzung mit externer Sicherungskopie, nie per
`git checkout`/`stash`/`reset`.

## Known Limitations

- **Die Trip-Vorschau erbt weiterhin die volle Wiederhol-Politik des Versandpfads
  (bis zu 3 Versuche mit `time.sleep`-Backoff je Segment über `_fetch_weather`).** Das ist
  in dieser Scheibe unverändert und ausdrücklich **kein** Nebenbefund, sondern der harte
  Kern von Scheibe B — siehe „Abgrenzung zu Scheibe B" für die vollständige
  Aufrufstellen-Tabelle und die Begründung, warum eine Teillösung hier keinen Sinn ergäbe.
- **Die Timeout-Leiter (R6) bleibt widersprüchlich** (Vergleichs-Vorschau Go 60 s == nginx
  60 s ohne Puffer; Trip-Vorschau Go 30 s, obwohl nginx 60 s zuließe). Nachziehen ist
  Scheibe B vorbehalten, nachdem die dort gemessene neue Laufzeit vorliegt.
- **Der Starlette-Threadpool ist nirgends konfiguriert** (anyio-Default 40 Threads). Siehe
  „Risiken".
- **Zwei weitere ungeschützte Lazy-Singletons bleiben bewusst unangetastet:**
  `api/routers/webhook.py:57` (`telegram_webhook`) und `api/routers/scheduler.py:174`
  (`trigger_inbound_telegram`) haben dieselbe Bauform wie das reparierte `_get_tf()` — ohne
  Sperre —, sind aber bereits **heute** `def`-Handler und damit schon vor Scheibe A
  nebenläufig erreichbar. Ä1 verursacht dieses Bestandsrisiko nicht und vergrößert es nicht;
  eine Reparatur ist ein eigenständiger Nebenbefund (→ #1199), kein Teil dieser Scheibe.
- **Die `_warned_missing_key`-Merker** in `src/services/official_alerts/vigilance.py:63`,
  `meteoalarm.py:496` und `meteo_forets.py:63` bleiben ebenfalls unangetastet — ungeschützt,
  aber folgenlos: schlimmstenfalls wird eine Warnung im Log doppelt statt einmal geschrieben,
  kein Datenverlust, keine falsche Nutzer-Ausgabe.

## Risiken

- **Die eigentliche Wirkung von Scheibe A ist eine Zustandsänderung des Systems, nicht nur
  eine Reparatur.** Vorher: „ein Aufruf legt alles lahm, dafür läuft nie etwas gleichzeitig".
  Nachher: „vieles läuft gleichzeitig". Der Tausch ist eindeutig richtig — die heutige
  Blockade ist der gemeldete, nutzersichtbare Fehler —, aber er verschiebt die Fehlerklasse
  von **Blockade** zu **Nebenläufigkeit**. Die Tabelle unter „Nebenwirkung von Ä1" oben
  listet die daraufhin geprüften Stellen. **Sie ist ausdrücklich kein Vollständigkeitsbeweis**
  — hier stand bis zum Adversary-Lauf am 2026-08-15 die Behauptung, es seien „alle
  `global`-Anweisungen in `src/` und `api/`" geprüft worden und außer `_get_tf()` (→ Ä3) sei
  nichts Offenes zurückgeblieben. Das war widerlegbar und wurde widerlegt (F002): Die
  Suchmethode („Schlüsselwort `global`") kann Dekorator-basierte Zwischenspeicher,
  Klassenattribute und veränderliche Standardargumente prinzipiell nicht finden, und genau so
  ein Fall liegt im umgestellten Pfad (`_lookup_department_cached()`, `@functools.lru_cache`).
  Sachlich blieb es folgenlos — der Fall ist geprüft und unkritisch, siehe Tabelle —, aber die
  **Aussage** war zu stark. Wer diese Scheibe fortschreibt, darf sich nicht darauf verlassen,
  dass die Tabelle jeden geteilten Zustand im Anfragepfad kennt.
- **Threadpool-Erschöpfung bei mehr als 40 gleichzeitigen langsamen Vorschauen.** Der
  anyio-Threadpool-Default liegt bei 40 Threads; eine 41. gleichzeitige langsame Vorschau
  würde warten müssen, bis ein Thread frei wird. Das ist gegenüber dem **heutigen** Zustand
  trotzdem eine klare Verbesserung: heute blockiert bereits **eine einzige** laufende
  Vorschau den gesamten Prozess inklusive `/health`; nach Ä1 blockiert eine einzelne
  Vorschau nur noch ihren eigenen Thread. Eine explizite Threadpool-Konfiguration ist nicht
  Teil dieser Scheibe — bei nachgewiesener Erschöpfung (Monitoring, `/health` wird trotz Ä1
  wieder langsam) ist das ein Folge-Nebenbefund für #1199, kein Grund, Scheibe A
  zurückzuhalten.
- **`call_log.resolve_call_source()` (R1 aus dem Kontextdokument) betrifft diese Scheibe
  NICHT.** Ä1 verlagert Handler in den Threadpool, aber jeder Request läuft weiterhin in
  genau einem Thread ohne parallele Unter-Tasks — anders als die künftige Scheibe-B-
  Parallelisierung, die mehrere Orte/Segmente gleichzeitig in verschiedenen Threads
  abarbeitet. Die Diagnose-Zuordnung über `inspect.stack()` bleibt in Scheibe A unverändert
  intakt.

## Verifikation auf Staging

Nach dem Deploy wird derselbe Messaufbau wie M1 im Kontextdokument wiederholt: eine
Trip- oder Vergleichs-Vorschau anstoßen und währenddessen `/api/health` **sekündlich** mit
einer 2-Sekunden-Grenze pollen. Vor der Änderung: 25 Timeouts in Folge (74,5 von 75,8 s
stumm). **Erwartung nach der Änderung: durchgehend HTTP 200**, kein einziger Timeout während
der laufenden Vorschau.

**Zwei getrennte Störquellen vor jeder Messung prüfen** (der zunächst vermutete
78,64-s-Ausreißer bei warmem Cache ist inzwischen **belegt erklärt**, nicht mehr nur
vermutet — `journalctl` zeigt einen PID-Wechsel von `gregor-python-staging.service` um
13:00:22 UTC, also einen Auto-Deploy-Neustart genau in diesem Fenster):

- **Ein Staging-Neustart leert den prozessweiten Cache.** Nach jedem Auto-Deploy (Cron
  `*/5`) ist der erste Aufruf wieder kalt, unabhängig von einer vorherigen warmen Messung —
  das war die tatsächliche Ursache des 78,64-s-Ausreißers, nicht Fremdlast.
- **Parallele Fremdnutzung besteht davon unabhängig.** Staging wird parallel von anderen
  Sitzungen genutzt, und der Python-Core läuft als Single-Worker-Prozess — ein fremder
  Vorschau-Aufruf einer anderen Sitzung verfälscht jede Zeitmessung zusätzlich nach oben.

Vor jeder Wiederholungsmessung deshalb **beides** prüfen: den Zeitpunkt des letzten
Staging-Deploys (z. B. `systemctl status gregor-python-staging` bzw. `journalctl`) und
Fremdlast (z. B. über `/api/scheduler/status` oder Rücksprache mit anderen aktiven
Sitzungen), bevor ein Ergebnis als Befund gewertet wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Diese Änderung stellt einen bereits vorherrschenden Hausstil her, sie
  eröffnet keine neue architektonische Weiche. Vor der Änderung sind 22 der 36 Route-Handler
  im `api/`-Baum bereits `def` (laufen im Threadpool), 14 sind `async def` — die 13
  `await`-losen `async def`-Handler sind die Abweichung, nicht die Mehrheit. Es existiert
  auch kein bestehendes ADR zu Nebenläufigkeit/Prozessmodell des Python-Core, das dieser
  Fix umgehen oder ablösen würde (geprüft: `docs/adr/README.md`, keine Treffer für
  „async"/„Threadpool"/„Event-Loop"). Die Änderung berührt keine der in CLAUDE.md genannten
  Entscheidungsflächen (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie). Vorbild für diese Begründungsform: `stage_weather_python_endpoint.md:126-129`.
  Ä3 wirft dieselbe Frage nicht neu auf: die doppelt geprüfte Sperre ist im Repo bereits
  dreifach etabliertes Muster (`weather_cache.py`, `thunder_window_cache.py`,
  `radar_cache.py`) — Ä3 wendet es auf einen vierten Fall an, führt kein neues Muster ein.

## Changelog

- 2026-08-15: Initial spec created (Scheibe A von #1765 + #1839; Wurzel #1539 bleibt offen
  und wird nicht vorweggenommen)
- 2026-08-15: Nachtrag — Ä3 (`_get_tf()` in `src/utils/timezone.py` gegen gleichzeitige
  Erstinitialisierung absichern) und AC-5 ergänzt. Grund: Ä1 macht die 13 Handler erstmals
  wirklich nebenläufig (vorher waren sie durch den blockierten Event-Loop unfreiwillig
  serialisiert) — eine systematische Durchsicht aller `global`-Anweisungen in `src/`/`api/`
  fand genau eine ungeschützte Stelle im Vorschau-Pfad (`_get_tf()`); alle anderen sind
  bereits abgesichert oder liegen außerhalb dieser Scheibe (siehe „Known Limitations").
- 2026-08-15: Nachtrag — Befund beim Abgleich mit der aktualisierten N1/N2-Nachmessung im
  Kontextdokument: Ä2 (in ihrer engen Fassung, nur `preview_service.py:173`) deckt nur 2 der
  7 Segment-Abrufe einer typischen Trip-Vorschau ab; die 4 Mehrtages-Ausblick-Segmente laufen
  weiterhin über einen unveränderten, geteilten `_fetch_weather`-Aufruf in
  `_build_stage_trend()` (`trip_report_scheduler.py:2254`). AC-3 entsprechend präzisiert
  (Geltungsbereich benannt statt pauschal „die Trip-Vorschau"), Befund als eigener Punkt in
  „Known Limitations" aufgenommen statt stillschweigend mitgezogen.
- 2026-08-15: Korrektur — Ä2-Begründung war unbelegt und teils falsch: N2 misst 0
  Wiederholversuche im störungsfreien Normalbetrieb (121 s echte Arbeit), Ä2 ist damit für
  die heutige Latenz **wirkungslos**, nicht latenzverbessernd. Begründung in Purpose und
  Ä2-Implementierungsdetails auf die tatsächliche, dreiteilige Reihenfolge umgestellt
  (gemessen wirkungslos → strukturelle Nahtstelle für Scheibe B → bedingter
  Robustheitsgewinn bei Störung). „Abgrenzung zu Scheibe B" um die N1-Segmentstruktur
  (7 Abrufe, ~26 s parallelisiert, 87 % Budgetauslastung, offene Designfrage zu den drei
  Abrufschritten) ergänzt. „Verifikation auf Staging" korrigiert: der 78,64-s-Ausreißer ist
  durch einen Staging-Auto-Deploy-Neustart (PID-Wechsel 13:00:22 UTC, `journalctl`-belegt)
  erklärt, nicht durch Fremdlast allein — beide Störquellen jetzt getrennt benannt. AC-3
  inhaltlich unverändert (Aufrufzahl 1 vs. 3 bleibt die geprüfte Zusicherung).
- 2026-08-15: Entscheidung — Ä2 vollständig aus Scheibe A entfernt und nach Scheibe B
  verschoben (nicht nur eng belassen). Grund: Ä2 hatte nur noch die Nahtstellen-Begründung
  für Scheibe B als tragende Rechtfertigung, deckte davon aber nur 2 der 7 tatsächlichen
  Segment-Abrufe ab und ausgerechnet nicht die vier langsamsten (Ausblick +1/+2 Tage,
  25,4–25,9 s) — die ~26-s-Schätzung für Scheibe B setzt flache Parallelisierung über alle
  sieben Abrufe voraus, der Ausblickspfad ist also harte Voraussetzung, keine Restarbeit.
  Scheibe A besteht jetzt aus genau Ä1 + Ä3 (~15 statt ~35–50 LoC, 5 statt 6
  Produktivdateien). Entfernt: AC-3 (Retry-Zusicherung), die Ä2-Implementierungssektion, die
  Ä2-Zeilen in Dependencies/Source/Estimated Scope, der Ä2-Known-Limitations-Punkt samt
  Folge-Ticket-Vorschlag (die Lücke ist Kern von Scheibe B, kein Nebenbefund). AC-4 → AC-3,
  AC-5 → AC-4 umnummeriert, Mutations-Gegenprobe auf zwei Punkte reduziert. „Abgrenzung zu
  Scheibe B" trägt jetzt die vollständige Drei-Aufrufstellen-Tabelle mit Dauer und
  Retry-Status sowie die drei Festlegungen (a)/(b)/(c) für den Zuschnitt von Scheibe B; die
  `SegmentWeatherData`-Vertragsüberlegung (has_error statt Auslassen) ist dorthin
  übernommen, damit sie nicht verloren geht.
- 2026-08-15: Korrektur nach Adversary-Lauf (Verdict AMBIGUOUS, zwei MEDIUM-Findings) —
  **kein Produktivcode geändert**, beide Findings sind Aussage- bzw. Testdokumentations-Mängel.
  **F002:** Die Vollständigkeitsaussage in „Nebenwirkung von Ä1" und unter „Risiken" („alle
  `global`-Anweisungen in `src/`/`api/` durchgesehen, außer `_get_tf()` nichts Offenes") ist
  **widerlegt** — die Suchmethode findet Dekorator-basierte Zwischenspeicher, Klassenattribute
  und veränderliche Standardargumente prinzipiell nicht. Belegter Fall:
  `_lookup_department_cached()` (`department_mapper.py:335-336`, `@functools.lru_cache`),
  erreichbar aus dem umgestellten `preview_compare` über `comparison_engine.py:322` →
  `get_official_alerts_with_status()` → `lookup_department()`, im Normalfall aktiv. Sachlich
  unkritisch (`lru_cache` ist in CPython intern abgesichert; Wettlauf = doppelte Berechnung,
  keine Datenverfälschung) — deshalb als **geprüft und unkritisch** in die Tabelle aufgenommen
  statt repariert. Ebenfalls aufgenommen: `egress_guard.py:139-140` (`global`, aber einmalig in
  `lifespan()` vor Annahme von Anfragen). Die zu weit gehende Aussage wurde **nicht
  stillschweigend geglättet**, sondern an beiden Stellen ausdrücklich als widerlegt und
  korrigiert markiert. **F001:** `tests/unit/test_route_handler_ohne_await.py` zählt `await`
  rein per AST, ohne Erreichbarkeit im Kontrollfluss — ein Handler mit `if False: await …`
  gefolgt von `time.sleep()` käme grün durch (Adversary-Sonde). Bewusst **nicht gelöst**
  (kein Bestandsfall, Erreichbarkeitsanalyse unverhältnismäßig), sondern als Abschnitt
  „Bekannte Grenze" im Docstring des Tests benannt, samt zweiter Verteidigungslinie
  (`test_event_loop_bleibt_frei.py`, deckt aber nur die Vorschau-Handler ab).
