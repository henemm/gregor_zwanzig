---
entity_id: fix_1448_s3_telegram_openmeteo
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.1"
tags: [telegram, openmeteo, zeitbudget, alerts]
---

# Fix #1448 Scheibe S3 — Telegram-Drosselbremse und open-meteo bekommen eine Obergrenze

## Approval

- [ ] Approved

## Purpose

Zwei Stellen im Alarm-Versandpfad können heute unbegrenzt hängen: die
Telegram-Drosselbremse `_reserve_send_slot()` (`while True` ohne
Wall-Clock-Obergrenze) und der open-meteo-Provider `fetch_forecast()`
(einzige Wetterquelle ohne `FETCH_DEADLINE_SECONDS`). Beides verzögert
nutzersichtbar eine Wetterwarnung. Diese Scheibe gibt beiden eine harte,
im Test schrumpfbare Zeitgrenze nach dem etablierten Muster von
`FETCH_DEADLINE_SECONDS` (`src/providers/dwd.py:69`,
`meteofrance.py:85`) und schließt damit die letzte der drei #1448-Scheiben
ab (nach S1 `fix_1448_s1_mail_zeitgrenze.md` und S2
`fix_1448_s2_dateisperren.md`).

**Wichtig für open-meteo (PO-Rückmeldung 2026-08-01):** Die Zeitgrenze muss
bereits **innerhalb eines einzelnen `_request`-Aufrufs** greifen, nicht erst
beim Wechsel zum nächsten Modell-Kandidaten — genau das ist der im Ticket
beschriebene Hauptfall (ein einzelner hängender Aufruf). Eine Prüfung, die
nur zwischen Kandidaten stattfindet, würde im Hauptfall nicht greifen und
wäre keine echte Obergrenze.

## Source

- **Datei A:** `src/output/channels/telegram.py`, Methode
  `TelegramOutput._reserve_send_slot()` (`:210-250`)
- **Datei B:** `src/providers/openmeteo.py`, Methoden
  `OpenMeteoProvider.fetch_forecast()` (`:787-`) und `_request()`
  (`:512-552`, `@retry`-Dekorator `:505-511`)

> **Schicht-Hinweis:** Reine Python-Core-Änderung (`src/output/channels/`,
> `src/providers/`). Keine Go-, keine Frontend-Änderung.

## Estimated Scope

- **LoC:** ~+90/-15 Code (Kontext-Schätzung plus Aufschlag für die
  `_request`-Signaturerweiterung und die zusammengesetzte
  `stop`-Bedingung, s. Implementation Details B) plus ~+220 Test — liegt
  über dem 250er-Workflow-Budget, PO-Freigabe über `loc_limit_override`
  nötig.
- **Files:** 4 (2 geänderte Quelldateien, 1 neue Testdatei, 1 Doku-Folgeänderung
  an einer bestehenden Spec)
- **Effort:** medium — zwei unabhängige, klar umrissene Mechanismen nach
  etabliertem Vorbild (`FETCH_DEADLINE_SECONDS`), aber mit einer echten
  Testfalle (Klassenattribut `_rate_limit_stamps` überlebt zwischen Tests)
  und der Notwendigkeit, die Restzeit **innerhalb** einer laufenden
  `tenacity`-Wiederholkette mitzuführen (s. Implementation Details B).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.dwd.FETCH_DEADLINE_SECONDS` / `_fetch_series` (`dwd.py:69`, `:175-193`) | Referenz-Pattern (nicht importiert) | Monotone Uhr, Prüfung vor jedem weiteren Einzel-Call statt unbegrenztem Warten — Ausgangsmuster; open-meteo geht wegen der PO-Vorgabe (s. Purpose) einen Schritt weiter und bindet die Grenze zusätzlich in die Wiederholkette selbst ein (s. u.) |
| `tenacity.stop_after_delay` / `stop_any` (Paket-Version 9.1.2, bereits Projektabhängigkeit über `tenacity.retry` hinaus) | Python-Bibliotheksfunktion | Kombinierbar mit `stop_after_attempt` per `|` (ergibt `stop_any`) — begrenzt die GESAMTE Wiederholkette eines `_request`-Aufrufs zeitlich, nicht nur die Versuchszahl |
| `src/services/trip_alert.py::ALERT_RUN_DEADLINE_SECONDS` (#1447 S1) | Konstante (nicht importiert) | Äußere Job-Lauf-Grenze (90 s) des Alarm-Laufs — Begründung für die Wahl 30 s (Telegram) / 60 s (open-meteo) statt der 180 s von dwd/meteofrance |
| `fix_1448_s1_mail_zeitgrenze.md` / `fix_1448_s2_dateisperren.md` (Schwester-Scheiben) | Spec (bestehend) | Liefern die Lehre, die diese Scheibe trägt: eine neue Zeitgrenze hinter einem zu breiten `except` wird zum stillen Fehler (F001, CRITICAL in S1); S1 lehrt zusätzlich, dass eine Grenze je Einzeloperation nicht reicht — die Restzeit muss innerhalb der laufenden Operation mitgeführt werden (dort: Socket-Phasen, hier: `tenacity`-Versuche) |
| `output.channels.telegram.reset_telegram_rate_limit_for_tests()` (`telegram.py:574-585`) | Python-Funktion (bestehend, wiederverwendet) | Bereits vorhandener Reset-Helfer für die prozessweite Buchführung `TelegramOutput._rate_limit_stamps` — löst die in S2 gelernte Klassenattribut-Falle, muss NICHT neu gebaut werden |
| `src/services/trip_alert.py:525` (`except Exception as e: logger.error(...)`) | Python-Aufrufstelle (nicht geändert) | Fängt `check_and_send_alerts()` pro Trip ab und loggt sichtbar auf ERROR-Ebene — Nachweis, dass der neue `OutputError` NICHT stillschweigend verschluckt wird (s. „Was bei Überschreitung passiert") |
| `src/services/segment_weather.py:192-202` (`except ProviderRequestError as e:`) | Python-Aufrufstelle (nicht geändert) | Fängt `fetch_forecast()` bereits heute gezielt auf `ProviderRequestError` ab — dieselbe Exception-Klasse, die S3 bei Deadline-Überschreitung wirft; kein neuer Fehlerpfad, den ein Aufrufer übersehen könnte |
| `docs/specs/modules/telegram_send_pacing.md` (bestehend) | Spec (bestehend) | Restrisiko-Eintrag `:208-217` wird durch diese Scheibe überholt (s. „Folgeänderung") |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/channels/telegram.py` | MODIFY | Modulkonstante `SEND_SLOT_MAX_WAIT_SECONDS = 30.0`; `_reserve_send_slot()` bricht nach Überschreitung mit `OutputError` ab statt weiter zu schlafen; Logzeile mit `chat_key` und gewarteter Zeit vor dem Abbruch |
| `src/providers/openmeteo.py` | MODIFY | `import time` ergänzt; Modulkonstante `FETCH_DEADLINE_SECONDS = 60.0`; `_request()` bekommt einen neuen optionalen Parameter `deadline_at`, begrenzt damit sowohl den HTTP-Timeout des einzelnen Versuchs als auch — über eine zusammengesetzte `tenacity`-`stop`-Bedingung — die gesamte eigene Wiederholkette; `fetch_forecast()` reicht `deadline_at` bei jedem Aufruf (erster Kandidat UND Fallback-Kandidaten) durch |
| `tests/tdd/test_send_slot_and_fetch_deadline.py` | CREATE | Nachweis für beide Grenzen |
| `docs/specs/modules/telegram_send_pacing.md` | MODIFY (Folgeschritt, nicht durch diese Datei selbst) | Restrisiko-Eintrag `:208-217` auf den nun begrenzten Stand ziehen |

### Estimated Changes

- Files: 4 (2 Quelldateien, 1 neue Testdatei, 1 bestehende Spec)
- LoC: +90/-15 Code, +220 Test (Kontext-Schätzung)

## Implementation Details

### A) `telegram.py` — `SEND_SLOT_MAX_WAIT_SECONDS`

```
SEND_SLOT_MAX_WAIT_SECONDS = 30.0  # analog FETCH_DEADLINE_SECONDS (dwd.py:69):
# im Normalfall wartet die Bremse GAR NICHT (unter 18 Nachrichten/60s wird
# sofort gesendet). 30s treffen nur den echten Stau und bleiben deutlich
# unter dem 90s-Alarm-Lauf-Budget (ALERT_RUN_DEADLINE_SECONDS,
# trip_alert.py:40, #1447 S1).
```

`_reserve_send_slot()` merkt sich beim Eintritt `deadline_at =
time.monotonic() + SEND_SLOT_MAX_WAIT_SECONDS`. Vor jedem `time.sleep(...)`
in der bestehenden `while True`-Schleife (`:226-250`) wird geprüft, ob
`time.monotonic() >= deadline_at`. Ist das der Fall, wird **vor** dem
Abbruch eine Logzeile geschrieben (WARNING oder ERROR, mit `chat_key` und
der insgesamt gewarteten Zeit) und danach `OutputError("telegram", ...)`
geworfen — dieselbe Fehlerklasse, die `send()` an anderen Stellen bereits
für Transportfehler wirft (`output.channels.base.OutputError`, importiert
`:11`, verwendet u. a. `:378`). **Nicht angefasst:** die 429-Wiederholung
(`:252-265`/`:290-304`) und ihr Kommentar `:297-303` zur bewusst
ausbleibenden zweiten Slot-Reservierung.

Die Logzeile muss **vor** dem `raise` stehen, nicht danach — sonst würde
ein Fehler im Logging-Aufruf selbst den sichtbaren Abbruch verschlucken
(dieselbe Reihenfolge-Lehre wie in `fix_1448_s2_dateisperren.md`,
Implementation Details).

### B) `openmeteo.py` — `FETCH_DEADLINE_SECONDS`, wirksam INNERHALB eines einzelnen Aufrufs

```
FETCH_DEADLINE_SECONDS = 60.0  # analog dwd.py:69/meteofrance.py:85, aber
# bewusst NICHT 180s: open-meteo ist die Hauptquelle und wird JE SEGMENT
# aufgerufen (nicht selten wie ein Fallback); der Normalfall liegt unter 1s
# (#1447-Analyse: hunderte Läufe, Ausreißer 27s/49s), 60s sind ~60-fache
# Reserve und bleiben unter den 90s des Alarm-Laufs
# (ALERT_RUN_DEADLINE_SECONDS, trip_alert.py:40).
```

**PO-Vorgabe, verbindlich für die Implementierung:** Eine Prüfung, die nur
*zwischen* Kandidaten stattfindet (Vorbild `dwd.py:184-189`), reicht hier
**nicht** — der Hauptfall aus dem Ticket ist genau der eine, dauerhaft
hängende Aufruf, nicht erst der Kandidatenwechsel. Die Zeitgrenze muss
deshalb **in die laufende `tenacity`-Wiederholkette von `_request` selbst**
eingebunden werden, zusätzlich zur bestehenden Prüfung vor jedem weiteren
Kandidaten.

`fetch_forecast()` setzt einmalig `deadline_at = time.monotonic() +
FETCH_DEADLINE_SECONDS`, direkt nach der Kandidatenermittlung (`:823-828`),
und reicht diesen Wert bei **jedem** `_request`-Aufruf mit — beim ersten
Kandidaten (bisher unbedingter Aufruf `:896`) genauso wie bei den
Fallback-Kandidaten (`:901-904`).

`_request()` bekommt einen neuen optionalen Parameter `deadline_at:
Optional[float] = None`.

**PRÄZISIERUNG (Team-Lead, 2026-08-01, nach der RED-Phase — ersetzt den
ursprünglichen Wortlaut dieses Absatzes):** Bei `deadline_at = None` bildet
`_request()` intern die Ersatzfrist `time.monotonic() +
FETCH_DEADLINE_SECONDS` ab Aufrufbeginn. Der Parameter dient also nur dazu,
eine **gemeinsame** Frist über mehrere Kandidaten hinweg durchzureichen — er
ist **nicht** der Schalter, der die Absicherung überhaupt erst einschaltet.

*Ursprünglich stand hier:* „Default `None` erhält das bestehende Verhalten
für alle anderen Aufrufer, z. B. `_fetch_uv_data`/Ensemble-Pfade, die keine
Deadline übergeben." Das ist **verworfen**.

*Begründung:* Sonst hinge der gesamte Schutz daran, dass **jede** Aufrufstelle
den Parameter auch wirklich durchreicht — und genau solche Lücken haben in
S1 (Adversary-Fund F001, CRITICAL: ein zu breiter `except` verschluckte die
neue Zeitgrenze) und S2 (ungefangene Mutation: fehlender `return` schrieb
ohne gehaltene Sperre) je einen Befund gekostet. Eine Absicherung, die man
vergessen kann einzuschalten, ist im Ernstfall keine. Die betroffenen
Zusatzpfade (`_fetch_uv_data`, Ensemble) sind Best-Effort-Daten; bricht dort
etwas nach 60 s ab, fehlen Zusatzwerte — gegenüber einem unbegrenzt
hängenden Abruf ist das der klar bessere Zustand.

*Auswirkung auf die Nachweise:* Der AC-6-Haupttest ruft `_request()` bewusst
**ohne** `deadline_at` auf und misst die Wanduhr — er wäre mit dem alten
Wortlaut nicht erfüllbar gewesen. Ein zweiter Test belegt zusätzlich, dass ein
explizit übergebenes `deadline_at` die Ersatzfrist übersticht.

Zwei Anpassungen innerhalb der Methode, aus der laufenden Restzeit abgeleitet:

1. **HTTP-Timeout je Versuch auf die Restzeit gedeckelt** (analog der
   Socket-Phasen-Deckelung in `fix_1448_s1_mail_zeitgrenze.md`): vor
   `self._client.get(...)` wird `restzeit = deadline_at -
   time.monotonic()` berechnet; ist `restzeit <= 0`, wird sofort
   `ProviderRequestError` geworfen, ohne den Versuch zu starten; sonst
   `self._client.get(url, params=params, timeout=min(TIMEOUT, restzeit))`.
   Ohne diese Deckelung könnte ein bereits laufender einzelner Versuch die
   Frist noch um bis zu `TIMEOUT` (30 s) überziehen.
2. **Die gesamte Wiederholkette des Aufrufs zeitlich gedeckelt:** die
   bestehende `stop=stop_after_attempt(RETRY_ATTEMPTS)`-Bedingung wird um
   eine zeitbasierte Bedingung erweitert, aus der laufenden Restzeit
   abgeleitet — `tenacity` erlaubt das Kombinieren von Abbruchbedingungen
   per `|` (`stop_after_attempt(N) | stop_after_delay(restzeit)`, ergibt
   intern `stop_any`). **Die konkrete Bauform ist Implementierungsdetail**
   (z. B. eine pro Aufruf neu berechnete `retry_with(stop=...)`-Variante
   nach dem bereits bestehenden Vorbild an `:901-904`, ein `Retrying`-Objekt
   statt des Dekorators, oder eine eigene `stop`-Callable, die auf
   `deadline_at` schließt) — verbindlich ist nur das Ergebnis: die Anzahl
   der `tenacity`-Versuche **und** die dafür verstreichende Zeit sind beide
   durch die Restzeit bis `deadline_at` begrenzt, nicht nur die Versuchszahl
   allein.

Damit ist ein **einzelner** hängender Aufruf spätestens nach
`FETCH_DEADLINE_SECONDS` (ab Eintritt in `fetch_forecast()`) beendet — nicht
erst nach dessen eigenem `RETRY_ATTEMPTS × TIMEOUT + Backoff`-Maximum von
bis zu ~180 s. Die bestehende Prüfung vor jedem weiteren Kandidaten
(`:884`, analog `dwd.py:184-189`) bleibt zusätzlich bestehen — sie verhindert
den Start eines neuen Kandidaten, dessen Restzeit bereits aufgebraucht ist,
und bleibt damit sinnvoll, ist aber nach dieser Änderung nicht mehr die
einzige Absicherung.

Das Modul importiert bislang kein `time`; der Import wird ergänzt.

**Nicht angefasst:** `RETRY_ATTEMPTS = 5` bleibt als Obergrenze der
Versuchszahl bestehen (jetzt per `stop_any` mit der Zeitgrenze
UND-verknüpft — im Normalfall bleibt weiterhin `stop_after_attempt` die
bindende Bedingung, da genug Restzeit vorhanden ist, s. AC-4), ebenso
`RETRY_WAIT_MIN`/`RETRY_WAIT_MAX`, die Fallback-Kandidatenlogik
(`FALLBACK_RETRY_ATTEMPTS=1`, #1155), die Cross-Provider-Weiche bei
komplettem Open-Meteo-Ausfall (`:922-945`).

## Expected Behavior

- **Input:** unverändert — `TelegramOutput.send(...)` /
  `OpenMeteoProvider.fetch_forecast(location, ...)`.
- **Output (Normalfall, keine Drossel/kein Hänger):** unverändert —
  Telegram sendet sofort, open-meteo liefert wie heute.
- **Output (Telegram-Drossel überschreitet die Frist):** `send()` wirft
  `OutputError`, die betroffene Nachricht wird **nicht** zugestellt; eine
  WARNING/ERROR-Logzeile mit `chat_key` und gewarteter Zeit erscheint vorher.
- **Output (open-meteo überschreitet die Frist — sowohl bei einem einzelnen
  hängenden Aufruf als auch beim Kandidatenwechsel):** `fetch_forecast()`
  wirft `ProviderRequestError`; der bestehende Aufrufer
  (`segment_weather.py:192-202`) behandelt das wie jeden anderen
  Provider-Fehler (Segment bleibt lückenhaft, Lauf läuft weiter).
- **Side effects:** eine neue Logzeile bei Telegram-Timeout; sonst keine
  neuen Log-Formate.

## Was bei Überschreitung passiert (Konsequenz, bewusster Tausch)

Bei Telegram-Überschreitung geht die betroffene Nachricht **nicht** raus.
Das ist der bewusste Tausch — die Alternative „trotzdem senden" wurde
verworfen: sie verletzt die Drossel-Zusage aus `telegram_send_pacing.md`
und riskiert eine Telegram-seitige Sperre. Der Fall tritt nur ein, wenn
derselbe Chat bereits ≥18 Nachrichten in 60 s bekommen hat **und** die
Wartezeit 30 s übersteigt — eine Alarm-Nachricht hinter einem solchen Stau
käme ohnehin verspätet an.

**Nachweis, dass kein Aufrufer den neuen Fehler verschluckt:**

- Telegram: `send()` propagiert `OutputError` unverändert (kein neuer
  `except`-Zweig fängt ihn ab, da `OutputError` weder `httpx.TimeoutException`
  noch `httpx.HTTPError` ist, die einzigen umschließenden `except`-Zweige an
  dieser Stelle, `:379-382`). Der äußere Aufrufer `trip_alert.py:514-526`
  fängt `Exception` pro Trip **und loggt sichtbar auf ERROR-Ebene**
  (`:525-526`) — kein `except: pass`, wie es der CRITICAL-Fund F001 in S1
  war. Der Lauf läuft für andere Trips weiter (fail-soft pro Trip, bestehend,
  unverändert).
- open-meteo: `ProviderRequestError` ist bereits die Exception-Klasse, die
  `fetch_forecast()` an anderen Stellen wirft; der bestehende Aufrufer
  `segment_weather.py:192-202` fängt sie bereits gezielt ab. Kein neuer
  Fehlerpfad, den ein Aufrufer übersehen könnte.

## Was sich NICHT ändert

- Die 429-Wiederholung in Telegram (`:252-265`/`:290-304`), inklusive ihres
  Deckels `telegram_retry_after_cap_seconds` (Standard 45 s) und der
  bewusst ausbleibenden zweiten Slot-Reservierung nach 429.
- Die Drossel-Parameter `telegram_rate_limit_max_per_window` (18) und
  `telegram_rate_limit_window_seconds` (60).
- Das Verhalten im Normalfall: unter 18 Nachrichten/60 s wird sofort
  gesendet, ohne jede Wartezeit; bei open-meteo mit ausreichend Restzeit
  bleibt `stop_after_attempt(RETRY_ATTEMPTS)` die bindende Bedingung, die
  neue Zeitgrenze greift nicht früher ein als bisher.
- `RETRY_ATTEMPTS = 5` als Obergrenze der Versuchszahl, `RETRY_WAIT_MIN`/
  `RETRY_WAIT_MAX` von open-meteo.
- Die Fallback-Kandidatenlogik von open-meteo
  (`FALLBACK_RETRY_ATTEMPTS = 1`, #1155) und die Cross-Provider-Weiche bei
  komplettem Ausfall (`:922-945`).

## Folgeänderung an `docs/specs/modules/telegram_send_pacing.md`

Wird im selben Implementierungsschritt an der bestehenden Spec-Datei
vorgenommen (hier nur beschrieben, nicht durch diese Datei selbst
geändert):

- **Restrisiko-Eintrag `:208-217`** — Wortlaut „…wäre funktional
  unschädlich — der Python-Core führt den Versand serverseitig zu Ende,
  auch wenn der Go-Zeitplaner vorher aufgibt" ist durch #1447 S1 überholt:
  Der Alarm-Lauf hat seit S1 ein eigenes Budget von 90 s
  (`ALERT_RUN_DEADLINE_SECONDS`, `trip_alert.py:40`) und endet als
  Teilerfolg statt den Versand serverseitig zu Ende zu führen — die
  Verzögerung ist seither messbar und nutzersichtbar, nicht mehr
  „jenseits des spezifizierten Umfangs". Der Eintrag wird ersetzt durch
  einen Verweis auf `SEND_SLOT_MAX_WAIT_SECONDS` (diese Spec,
  `fix_1448_s3_telegram_openmeteo.md`) als neue, garantierte Obergrenze:
  eine einzelne Slot-Reservierung wartet höchstens 30 s, danach bricht der
  Versand dieser einen Nachricht sichtbar ab, statt die Serie unbegrenzt zu
  verzögern. Die dort genannten Serien-Rechnungen (105 s/150 s/120 s für
  Extremfälle) bleiben als Beleg für die GRÖSSENORDNUNG stehen, aber ohne
  die „unschädlich, da serverseitig zu Ende geführt"-Begründung.
- Der zweite Punkt zum prozessweiten Zeitstempel-Zähler (`:199-203`, kein
  prozessübergreifender Lock) und der Punkt zur gleichzeitigen Drosselung
  (`:218-223`) bleiben unverändert — beide betreffen eine andere
  Eigenschaft der Bremse (Prozessgrenze bzw. Mehrstrom-Konkurrenz), nicht
  die hier behobene fehlende Obergrenze.

## Gate-Hinweis

Weder `src/output/channels/telegram.py` noch `src/providers/openmeteo.py`
sind Mail-Inhalts-Dateien im Sinne des Renderer-Commit-Gates #811 (Liste:
`src/output/renderers/email/*.py`,
`src/output/renderers/{trip_report,sms_trip,compact_summary}.py`,
`src/output/renderers/alert/*.py`, `src/output/channels/email.py`) — das
Gate greift auf keiner der beiden Dateien.

## Test-Plan / Test-Politik

Alle Tests in `tests/tdd/test_send_slot_and_fetch_deadline.py`,
Namensregel nach Verhalten (keine Issue-Nummer im Dateinamen). Pfadregel
#1409: Prüfling relativ zur eigenen Testdatei auflösen
(`Path(__file__).resolve().parents[2]`). `pytest-timeout` steht global auf
30 s (`pyproject.toml:63`) — alle Tests bleiben mit geschrumpften
Konstanten deutlich darunter.

**Telegram-Bremse — kein Live-Versand.** Die Bremse ist reine lokale
Buchführung (`TelegramOutput._rate_limit_stamps`) und lässt sich ohne Netz
füllen; `_reserve_send_slot()` wird direkt aufgerufen, kein `httpx.post`
nötig.

**Falle (identisch zu S2's file_lock-Falle, hier bereits gelöst):** Die
Drossel-Buchführung ist ein **Klassenattribut** und überlebt zwischen
Tests. `reset_telegram_rate_limit_for_tests()` (`telegram.py:574-585`)
existiert bereits als Reset-Helfer — jeder Test in dieser Datei ruft ihn in
einer Fixture vor UND nach dem Testlauf auf. Kein neuer Reset-Mechanismus
nötig.

**open-meteo — echter langsamer lokaler Server.** Vorbild
`tests/tdd/test_meteofrance_direct_fallback.py:476-517`: ein echter,
absichtlich hängender lokaler HTTP-Server, `FETCH_DEADLINE_SECONDS`,
`TIMEOUT` und die Retry-Wartewerte per `monkeypatch` auf Millisekunden
geschrumpft. Für den Nachweis des **einzelnen** hängenden Aufrufs (AC-6)
wird `_request(endpoint, params, deadline_at=...)` gezielt direkt
aufgerufen statt über `fetch_forecast()` — das isoliert den Mechanismus
von der Kandidaten-Schleife und schließt einen versehentlichen
Kandidatenwechsel als Erklärung für ein bestandenes Ergebnis aus. Kein
Mock, kein Mock-Theater.

## Acceptance Criteria

- **AC-1:** Given die Drossel-Buchführung für einen Chat enthält bereits
  ≥ `telegram_rate_limit_max_per_window` Zeitstempel im aktuellen Fenster,
  sodass `_reserve_send_slot()` in die Warteschleife eintritt, UND
  `SEND_SLOT_MAX_WAIT_SECONDS` ist per Test auf Millisekunden geschrumpft /
  When `_reserve_send_slot(chat_key)` aufgerufen wird / Then kehrt der
  Aufruf spätestens nach `SEND_SLOT_MAX_WAIT_SECONDS` mit `OutputError`
  zurück, statt unbegrenzt weiter zu schlafen.
  - Test: `test_reserve_send_slot_raises_output_error_after_max_wait` —
    Buchführung künstlich mit ≥18 aktuellen Zeitstempeln gefüllt (kein
    Netz), `SEND_SLOT_MAX_WAIT_SECONDS` per `monkeypatch` geschrumpft,
    gemessene Rückkehrzeit liegt innerhalb der erwarteten Obergrenze,
    `OutputError` wird geworfen.

- **AC-2:** Given dieselbe Ausgangslage wie AC-1 / When
  `_reserve_send_slot()` die Frist überschreitet und abbricht / Then
  erscheint vorher eine Log-Zeile (WARNING oder ERROR), die den
  `chat_key` und die insgesamt gewartete Zeit enthält.
  - Test: `test_reserve_send_slot_logs_chat_key_and_waited_time_on_timeout`
    — dieselbe Fixture wie AC-1, `caplog` prüft Log-Level sowie dass
    `chat_key` und eine Zeitangabe im Log-Text vorkommen.

- **AC-3:** Given ein lokaler HTTP-Server, gegen den open-meteo aufgelöst
  ist, nimmt Verbindungen an, antwortet aber nie — für ALLE erreichbaren
  Kandidaten / When `fetch_forecast()` aufgerufen wird und die verstrichene
  Zeit `FETCH_DEADLINE_SECONDS` übersteigt / Then wird `ProviderRequestError`
  geworfen, statt weitere Kandidaten unbegrenzt zu versuchen.
  - Test: `test_fetch_forecast_raises_provider_request_error_after_deadline`
    — echter lokaler TCP-Server ohne Antwort, `FETCH_DEADLINE_SECONDS` und
    die HTTP-/Retry-Zeitwerte per `monkeypatch` auf Millisekunden
    geschrumpft, `ProviderRequestError` wird erwartet, gemessene
    Gesamtlaufzeit liegt innerhalb der erwarteten Obergrenze (nahe
    `FETCH_DEADLINE_SECONDS`, nicht erst nach mehreren vollen
    Kandidaten-Retry-Zyklen — Beleg für das Zusammenspiel mit AC-6).

- **AC-4:** Given der Normalfall in beiden Mechanismen — (a) weniger als
  `telegram_rate_limit_max_per_window` Zeitstempel liegen im Fenster, (b)
  der open-meteo-Server antwortet sofort mit einer gültigen Antwort / When
  (a) `_reserve_send_slot()` bzw. (b) `fetch_forecast()` aufgerufen wird /
  Then bleibt das Verhalten in beiden Fällen unverändert schnell: (a) kein
  `time.sleep`-Aufruf, sofortige Rückkehr; (b) das gewohnte Ergebnis ohne
  zusätzlichen Aufruf oder Verzögerung durch die neue Deadline-Prüfung.
  - Test: `test_normal_case_unaffected_by_new_deadlines` — zwei
    Teilfälle in derselben Testdatei: `time.sleep` als Spion belauscht
    (Telegram-Teil) und ein sofort antwortender lokaler Server
    (open-meteo-Teil); beide bestätigen unverändertes Verhalten.

- **AC-5:** Given Telegram antwortet auf einen Sendeversuch mit HTTP 429
  und einem `retry_after`-Wert unterhalb des bestehenden
  `telegram_retry_after_cap_seconds`-Deckels / When `_post()` die
  bestehende Wiederholung nach 429 durchläuft (`:290-304`) / Then bleibt
  diese Wiederholung von den neuen Konstanten unberührt — insbesondere
  wird nach dem 429 **keine** erneute Slot-Reservierung ausgelöst, und die
  Wartezeit bleibt weiterhin auf `telegram_retry_after_cap_seconds`
  gedeckelt.
  - Test: `test_429_retry_skips_new_slot_reservation_and_stays_capped` —
    injizierte 429-Antwort (kein Live-Telegram), `_reserve_send_slot`
    per `monkeypatch` gezählt: wird nach dem 429 nachweislich nicht ein
    zweites Mal für dieselbe Nachricht aufgerufen; die tatsächlich
    verwendete Wartezeit überschreitet den Cap nicht.

- **AC-6 (PO-Rückmeldung 2026-08-01, Kern des Tickets):** Given ein
  lokaler HTTP-Server nimmt die Verbindung für einen **einzelnen**
  `_request`-Aufruf an, antwortet aber nie — OHNE dass ein Wechsel zum
  nächsten Modell-Kandidaten stattfindet / When `_request(endpoint,
  params, deadline_at=...)` mit einer (per Test geschrumpften)
  `FETCH_DEADLINE_SECONDS`-Restzeit aufgerufen wird / Then bricht bereits
  DIESER EINE Aufruf spätestens nach der verbleibenden Zeit bis
  `deadline_at` mit `ProviderRequestError` ab — nicht erst nach seinem
  eigenen `RETRY_ATTEMPTS × TIMEOUT + Backoff`-Maximum von bis zu ~180 s.
  - Test:
    `test_single_hanging_request_aborts_within_deadline_without_candidate_switch`
    — echter lokaler TCP-Server, der Verbindungen annimmt, aber nie
    antwortet; `_request(...)` wird direkt aufgerufen (nicht über
    `fetch_forecast()`, um einen Kandidatenwechsel als Erklärung
    auszuschließen); `FETCH_DEADLINE_SECONDS`, `TIMEOUT` und
    `RETRY_WAIT_MAX` per `monkeypatch` auf Millisekunden geschrumpft;
    `ProviderRequestError` wird erwartet, gemessene Gesamtdauer liegt
    deutlich unter dem unbegrenzten `RETRY_ATTEMPTS`-Maximum und nahe der
    übergebenen Restzeit.

## Known Limitations

- **Provider-Kette als Ganzes hat weiterhin kein Budget.** Gibt open-meteo
  nach 60 s auf, darf die Fallback-Kette (dwd/meteofrance, je 180 s)
  danach erneut ansetzen. Die Summe kann also weiterhin über dem
  Lauf-Budget liegen — abgefangen wird das von der Lauf-Grenze aus #1447 S1
  (Teilerfolg), nicht von der Provider-Ebene. Ein Ketten-Budget wäre eine
  eigene Scheibe, nicht Teil von S3. Das ist eine echte, bewusst offene
  Grenze — anders als die (mit AC-6 geschlossene) Lücke innerhalb eines
  einzelnen open-meteo-Aufrufs.
- **Nebenbefund über das Vorbild `dwd.py` (nicht Teil dieser Scheibe):**
  `dwd.py`s eigene Deadline-Prüfung (`_fetch_series`, `:183-193`) greift
  ebenfalls nur *zwischen* Einzel-Calls, nicht innerhalb der
  `tenacity`-Wiederholkette des jeweiligen `_request`-Aufrufs — dieselbe
  Struktur, die für open-meteo in dieser Scheibe bewusst NICHT übernommen,
  sondern durch die kombinierte `stop`-Bedingung (s. Implementation
  Details B) geschlossen wird. Ob `dwd.py`/`meteofrance.py` dieselbe
  Lücke haben und ob sie relevant ist (ihre Fallback-Rolle macht den
  Hauptfall aus dem Ticket dort seltener), ist ein Nebenbefund für die
  Sammel-Triage (#1199), keine eigene Reparatur in S3.
- **`SEND_SLOT_MAX_WAIT_SECONDS = 30.0` und `FETCH_DEADLINE_SECONDS = 60.0`
  sind konservative, aus der Belegrechnung hergeleitete erste Werte**,
  keine empirisch in Produktion gehärteten Zahlen — analog zur Einordnung
  von `ALERT_RUN_DEADLINE_SECONDS` in #1447 S1 und
  `LOCK_TIMEOUT_SECONDS` in `fix_1448_s2_dateisperren.md`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer architektureller Grundsatz. Diese Scheibe
  wendet dasselbe bereits etablierte Muster (monotone Zeitgrenze statt
  unbegrenztem Warten, Vorbild `FETCH_DEADLINE_SECONDS`) auf die
  Telegram-Drosselbremse und die letzte Wetterquelle ohne eigene
  Zeitgrenze an, das S1/S2 bereits auf E-Mail-Versand und Dateisperren
  angewendet haben — hier zusätzlich verfeinert um die S1-Lehre, dass die
  Grenze innerhalb einer laufenden Wiederholoperation mitgeführt werden
  muss, nicht nur je Einzeloperation. ADR-0038 schließt „einzelne in sich
  unbegrenzt blockierende Schritte" ausdrücklich aus seinem
  Geltungsbereich aus und benennt Issue #1448 als die Stelle, an der sie
  gesondert behandelt werden — diese Spec ist Teil dieser gesonderten
  Behandlung, kein Widerspruch und keine neue Grundsatzentscheidung.

## Changelog

- 2026-08-01: Initial spec created
- 2026-08-01: PO-Rückmeldung eingearbeitet — Deadline muss innerhalb eines
  einzelnen `_request`-Aufrufs greifen (kombinierte `tenacity`-`stop`-
  Bedingung + auf Restzeit gedeckelter HTTP-Timeout), nicht nur zwischen
  Kandidaten; AC-6 ergänzt (Limit auf 6 ACs angehoben); Known-Limitations-
  Eintrag zur Kandidaten-Granularität durch einen Nebenbefund über das
  Vorbild `dwd.py` ersetzt.
