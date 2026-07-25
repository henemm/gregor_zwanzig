---
entity_id: telegram_send_pacing
type: bug
created: 2026-07-25
updated: 2026-07-25
status: draft
version: "1.0"
tags: [telegram, egress, rate-limit, notification_service]
---

<!-- Issue #1370 — Telegram: stiller Verlust halber Briefings bei langen Touren -->

# Telegram Send Pacing — Drosselung, 429-Wiederholung, sichtbarer Unvollständig-Hinweis

## Approval

- [ ] Approved

## Purpose

Telegram-Briefings mit vielen Segmenten (lange Touren, viele Wegpunkte) senden
mehrere Einzelnachrichten in schneller Folge an denselben Chat. Telegram
drosselt ab ~20 Nachrichten/Minute pro Chat mit HTTP 429; der heutige Code
erkennt das nicht als Drosselung, sondern bricht die Sendeserie mit `break`
ab (`notification_service.py:355`) — der Nutzer bekommt ein halbes Briefing
ohne jede Fehlermeldung. Dieses Modul führt eine chat-bezogene Drossel-Bremse,
eine begrenzte 429-Wiederholung und einen sichtbaren „Briefing unvollständig"-
Hinweis ein, ohne den heute funktionierenden Normalfall zu verlangsamen.

## Source

- **File:** `src/output/channels/telegram.py` — `class TelegramOutput`, sieben
  `httpx.post`-Aufrufe (`send`, `_send_fallback_without_parse_mode`,
  `delete_message`, `edit_message_text`, `answer_callback_query`,
  `set_my_commands`, `get_my_commands`) werden auf einen privaten POST-Helfer
  konsolidiert
- **File:** `src/services/notification_service.py:340-358` — Bubble-Sendeschleife
  des Trip-Reports (`break` bei Z. 355 entfällt)
- **File:** `src/output/renderers/narrow.py:457-574` — `render_telegram_bubbles()`,
  neuer Baustein für den Unvollständig-Hinweis
- **File:** `src/app/config.py` — `class Settings`, neue `Field(default=...)`-Einträge
  für die Drossel-Schwellen (Präfix `GZ_`, analog `telegram_bot_token` Z. 165 ff.)

> Schicht-Hinweis (Python-Core/Domain-Backend): alle Änderungen liegen in
> `src/` (Python-Core). Kein Go-Code (`internal/`, `cmd/`) betroffen — der im
> Kontext dokumentierte Go-Webhook-Nebeneffekt ist explizit Nicht-Ziel dieses
> Fixes (s. Known Limitations).

## Estimated Scope

- **LoC:** ~+130 / -20 (Produktivcode ~+80)
- **Files:** 4 Produktivdateien (`telegram.py`, `config.py`,
  `notification_service.py`, `narrow.py`) + Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `httpx` | Upstream | HTTP-Client für alle Telegram-POSTs, kein zentraler Wrapper vorhanden vor diesem Fix |
| `app.config.Settings` | intern | Trägt Bot-Token/Chat-IDs sowie die neuen Drossel-Schwellenwerte |
| Egress-Guards (`_guard_test_mode_bot_token`, `_guard_test_mode_chat_id`, `_guard_test_mode_target_chat`) | intern | Müssen vor jedem tatsächlichen POST unverändert laufen (#1288/#1363) |
| `output.renderers.email.unavailable_hint` | intern (Vorbild) | Bauart-Vorbild für den neuen „Briefing unvollständig"-Baustein (#1348), nicht direkt wiederverwendet — Telegram-Bubble statt HTML-Box |
| `internal/scheduler/scheduler.go:82` (120s) / `internal/handler/telegram_webhook.go:38` (5s) | Downstream, Go | Zeitbudgets, gegen die die Drossel-Parameter gerechnet sind — nicht Teil des Scopes |
| `tests/tdd/test_telegram_test_isolation.py` (AC-1…AC-8) | Test | Sichert die Guard-Reihenfolge für 5 Methoden ab — darf durch die Konsolidierung nicht brechen |
| `tests/tdd/test_issue_1001_telegram_bubbles.py:349-404, 842-879` | Test | Schreibt das heutige Abbruch-Verhalten fest — muss ans neue Verhalten angepasst werden |

## Implementation Details

**1. Ein privater POST-Helfer** in `telegram.py` ersetzt die 7 einzelnen
`httpx.post`-Aufrufe. Er kapselt ausschließlich POST + Drossel-Bremse +
429-Wiederholung und gibt die rohe `httpx.Response` zurück. Er ruft selbst
**keine** Guards auf — die bleiben unverändert vor dem Helferaufruf in jeder
öffentlichen Methode stehen (Guard-Reihenfolge bleibt Methoden-Sache, s.
`test_telegram_test_isolation.py`). Die Fehlerauswertung je Statuscode
(Ausnahme werfen vs. fail-soft vs. 400-HTML-Fallback) bleibt ebenfalls je
Methode wie heute — der Helfer vereinheitlicht sie nicht.

**2. Gleitendes 60-Sekunden-Fenster pro Chat, Obergrenze 18.** Ein
Zeitstempel-Zähler pro `chat_id` (nicht global) zählt **alle** Schreibzugriffe
mit — Briefing-Bubbles, Lade-Nachricht, `delete_message`, `edit_message_text`,
Alarme. Solange weniger als 18 Einträge im Fenster liegen, wird nicht
gewartet; erst darüber blockiert der Sender, bis wieder Platz ist. Die
Obergrenze (18) und die Fensterlänge (60 s) sind über `Settings`
(`Field(default=...)`, Präfix `GZ_`) einstellbar — Kern-Tests setzen sie auf
Werte, die keine echten Wartezeiten erzeugen (kein Test-Sonderpfad im
Produktivcode, reine Konfiguration).

**3. HTTP 429 als Drosselung.** `retry_after` wird aus dem JSON-Rumpf gelesen
(`response.json()["parameters"]["retry_after"]`, wie im bewiesenen
Live-Fixture `tests/tdd/_telegram_live_fixture.py:53-79`) — nicht über
`warn_egress._parse_retry_after()` (liest HTTP-Header eines anderen
Diensts). Maximal 1 Wiederholung; die gewartete Zeit wird auf einen
konfigurierbaren Höchstwert gedeckelt (Vorschlag 45 s), damit ein einzelner
Retry das 120-Sekunden-Budget des Scheduler-Laufs nicht sprengt.

**4. Kein Abbruch der Serie mehr.** `notification_service.py`s
Bubble-Sendeschleife (Z. 340-358) fängt einen endgültigen Fehlschlag je
Bubble ab, protokolliert ihn, sendet aber die restlichen Bubbles trotzdem
weiter. Am Ende der Serie wird — nur falls mindestens eine Bubble endgültig
gescheitert ist — eine zusätzliche Bubble mit einem kurzen, sichtbaren
Hinweistext gesendet (Bauart analog `unavailable_hint.py`, als eigene
`TelegramBubble` wie der Nicht-abrufbar-Hinweis in `narrow.py:514-517`).

## Expected Behavior

- **Input:** Eine Serie von Telegram-Schreibzugriffen an denselben Chat
  (Briefing-Bubbles, Lade-Nachricht, Löschen/Bearbeiten, Alarme), erzeugt
  durch geplanten Versand oder On-Demand-Befehle (`/heute`, `/morgen`)
- **Output:** Alle Nachrichten kommen beim Nutzer an — im Normalfall
  (≤18 Zugriffe/60s) unverändert schnell wie heute, bei Überschreitung
  verzögert statt verloren; bei endgültigem Einzelfehlschlag kommt der Rest
  der Serie plus ein sichtbarer Unvollständig-Hinweis an, statt dass die
  Serie kommentarlos abbricht
- **Side effects:** Kein Datenverlust mehr durch stillen Abbruch; ein
  bekannter, akzeptierter Nebeneffekt bei sehr langen On-Demand-Serien ist im
  Go-Webhook-Log sichtbar (s. Known Limitations) — funktional unschädlich

## Acceptance Criteria

- **AC-1:** Given ein Tagesbriefing mit 5-13 Bubbles (der reale, heute
  übliche Umfang) wird per Telegram versendet / When der Versand läuft /
  Then kommen alle Bubbles in unveränderter Reihenfolge und Anzahl beim
  Nutzer an, ohne spürbare Zusatzverzögerung und ohne Zusatznachricht —
  identisch zum heutigen Verhalten.
  - Test (Kern): aufgezeichnete/simulierte Serie von 5-13 erfolgreichen
    Sendungen an denselben Chat — Reihenfolge, Anzahl und Gesamtlaufzeit
    bleiben wie vor dem Fix.

- **AC-2:** Given ein Tagesbriefing besteht aus 20 Teilen an denselben Chat
  (sehr lange Etappe mit vielen Wegpunkten) / When der Versand läuft und
  Telegram dabei anfängt zu drosseln / Then kommen alle 20 Teile beim Nutzer
  an — keiner geht verloren, und der Versand schlägt nicht fehl.
  - Test (Kern): simulierte Serie von 20 Sendungen an denselben Chat gegen
    eine Gegenstelle, die ab der Drosselschwelle mit 429 antwortet — alle 20
    gelten am Ende als zugestellt.

- **AC-3:** Given Telegram antwortet während des Versands einmalig mit
  HTTP 429 und einem `retry_after`-Wert / When der Sender diese Antwort
  erhält / Then wird die betroffene Nachricht nach der (gedeckelten)
  angegebenen Wartezeit erneut gesendet und kommt beim Nutzer an, statt dass
  die Serie mit einem Fehler abbricht.
  - Test (Kern): aufgezeichnete 429-Antwort mit `parameters.retry_after` im
    JSON-Rumpf, gefolgt von einer 200-Antwort beim zweiten Versuch — die
    Nachricht gilt als zugestellt.

- **AC-4:** Given eine einzelne Nachricht in der Serie scheitert endgültig
  (bleibt auch nach dem einen erlaubten Wiederholversuch fehlerhaft) / When
  noch weitere Nachrichten der Serie ausstehen / Then werden diese
  restlichen Nachrichten trotzdem weiter gesendet, statt dass die gesamte
  Serie an dieser Stelle abbricht.
  - Test (Kern): simulierte Serie mit einem endgültig scheiternden Element
    in der Mitte — alle nachfolgenden Elemente werden dennoch zugestellt.

- **AC-5:** Given mindestens eine Nachricht der Serie ist endgültig
  fehlgeschlagen / When die Serie fertig gesendet ist / Then erhält der
  Nutzer eine zusätzliche, deutlich sichtbare Nachricht darüber, dass das
  Briefing unvollständig ist und wie viele bzw. welche Teile fehlen.
  - Test (Kern): simulierte Serie mit einem endgültigen Fehlschlag — am Ende
    der zugestellten Nachrichten liegt eine erkennbare Unvollständig-Bubble
    mit einer für den Nutzer verständlichen Aussage zur fehlenden Anzahl.

- **AC-6:** Given der Test-Modus ist aktiv, aber die Test-Zugangsdaten fehlen
  oder weichen von den konfigurierten ab / When irgendeine schreibende
  Telegram-Funktion aufgerufen wird / Then verlässt keine einzige Nachricht
  den Server — der Aufruf wird mit einem Konfigurationsfehler abgewiesen,
  exakt wie vor diesem Fix.
  - Test (Kern): bestehende Suite `tests/tdd/test_telegram_test_isolation.py`
    (AC-1…AC-8) läuft unverändert grün und ohne Anpassung ihrer Zusicherungen.

- **AC-7:** Given ein Nutzer erhält im selben Zeitraum ein Briefing und
  zusätzlich weitere Telegram-Nachrichten an denselben Chat (Lade-Hinweis,
  Löschungen, Alarme) / When diese zusammen so viele werden, dass Telegram zu
  drosseln beginnt / Then kommen trotzdem alle Nachrichten an — auch dann,
  wenn die Briefing-Teile für sich allein die Drosselschwelle nie erreicht
  hätten.
  - Test (Kern): simulierte Mischserie aus Lade-Nachricht, Briefing-Teilen und
    Löschungen an denselben Chat — alle Vorgänge werden vollständig
    ausgeführt, keiner scheitert an der Drosselung.

- **AC-8:** Given die Kern-Tests decken auch sehr lange Sendeserien und
  Drossel-Antworten ab / When die Kern-Testsuite ohne Netzzugriff läuft /
  Then ist sie in Sekundenbruchteilen fertig und reißt den globalen
  30-Sekunden-Test-Timeout (`pyproject.toml:63`) nicht — ohne dass dafür ein
  Sonderpfad im Produktivcode existiert, der nur unter Tests greift.
  - Test (Kern): die neue Testdatei läuft vollständig im Millisekundenbereich;
    die Grenzwerte stammen aus der normalen Konfiguration, nicht aus einer
    Test-Erkennung im Produktivcode.

## Known Limitations

- **Akzeptierter Nebeneffekt (kein Blocker, außerhalb des Scopes):** Bei
  sehr langen On-Demand-Briefings (`/heute`) kann der Go-Webhook-
  Weiterleiter (`internal/handler/telegram_webhook.go:38`, 5-Sekunden-Client)
  in ein Timeout laufen, während der Python-Core den Versand serverseitig
  zu Ende führt. Go antwortet Telegram dennoch mit 200; der Nutzer bekommt
  sein Briefing. Nebeneffekt ist eine irreführende `forward error`-Logzeile
  in Go — funktional unschädlich, kein Datenverlust.
- Ein prozessweiter Zeitstempel-Zähler pro Chat deckt Gleichzeitigkeit nur
  innerhalb desselben Python-Prozesses ab. Scheduler-Versand und paralleles
  `/heute` desselben Nutzers münden beide im selben Python-Core-Prozess
  (`api/routers/scheduler.py`), daher praktisch ausreichend — kein
  prozessübergreifender Lock.
- Kein Umbau auf asynchrone Warteschlangen, keine Änderung an anderen
  Renderern außer dem neuen Hinweis-Baustein, keine Änderung am Go-Code,
  kein neues Retry-Framework (`tenacity`) für Telegram — bewusst
  ausgeschlossen (Nicht-Ziele).
- **Bezifferte Obergrenzen des Zeitbudgets** (vom Adversary unabhängig
  nachgemessen, Standardwerte 18/60/45): eine 20-teilige Serie mit **einem**
  echten 429 braucht ~105 s und bleibt unter den 120 s des Zeitplaners. Zwei
  echte 429 in derselben Serie ergäben ~150 s, Serien ab ~40 Teilen allein
  durch die Drosselung ~120 s. Beides liegt jenseits des spezifizierten
  Umfangs (AC-1: 5-13 Teile, AC-2: 20 als Extremfall) und wäre funktional
  unschädlich — der Python-Core führt den Versand serverseitig zu Ende, auch
  wenn der Go-Zeitplaner vorher aufgibt (dasselbe Muster wie beim
  5-Sekunden-Webhook oben). Verbleibt als Restrisiko-Eintrag in der
  Nebenbefund-Sammlung (#1199), kein Blocker.
- **Wiederholung bei gleichzeitiger Drosselung:** Werden mehrere Nachrichten
  desselben Chats **gleichzeitig** gedrosselt, kann die Wiederholung die
  konfigurierte Obergrenze kurzzeitig überschreiten (belegt: 26 Anfragen in
  0,3 s bei Obergrenze 18). Innerhalb eines Briefing-Laufs unmöglich — die
  Sendeschleife ist streng sequenziell — und nur über die oben beschriebene
  Mehrstrom-Ausnahme erreichbar. Kein Datenverlust.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — ADR-0012 (Telegram-Renderpfad, 400-HTML-Fallback
  in `send()`) bleibt unverändert bestehen und wird durch diesen Fix nicht
  berührt; der neue POST-Helfer übernimmt die bestehende Statuscode-Logik
  unverändert je Methode.
- **Rationale:** Die Änderung ist eine Bugfix-Härtung eines bestehenden
  Sendepfads (Drosselung erkennen statt als Dauerfehler werten), keine
  Grundsatzentscheidung über Kanäle, Provider oder Datenmodell.

## Test Coverage

Neue Kern-Testdatei nach Verhalten benannt (nicht nach Issue-Nummer):
`tests/tdd/test_telegram_rate_limit.py` — deckt AC-1 bis AC-8 mit
aufgezeichneten/simulierten HTTP-Antworten, keine echten Netzzugriffe, keine
echten Sleeps über Millisekunden hinaus (Settings auf testfreundliche Werte).

Anzupassende Bestandstests:
- `tests/tdd/test_issue_1001_telegram_bubbles.py:349-404`
  (`TestAC5LiveAbortAfterFirstFailure`) schreibt das heutige
  „bricht bei erstem Fehlschlag ab"-Verhalten fest — muss auf „sendet Rest
  der Serie weiter + Unvollständig-Hinweis" umgestellt werden.
- `tests/tdd/test_issue_1001_telegram_bubbles.py:842-879`
  (`TestF003BriefingLogOmitsTelegramOnLoopAbort`) prüft, dass das
  Briefing-Log `telegram` bei Abbruch nicht als vollständig gesendet
  verzeichnet — muss ans neue "teilweise gesendet, mit Hinweis"-Verhalten
  angepasst werden (Log-Semantik ggf. auf "unvollständig" statt "fehlt
  ganz" ändern).

Live-Tests (Marker `live`, Opt-in `GZ_TELEGRAM_LIVE=1`, gegen
`tests/tdd/_telegram_live_fixture.py`):
- Echte lange Serie (≥20 Bubbles) gegen den Staging-Test-Chat, die Drossel-
  Bremse tatsächlich auslöst — bestätigt, dass alle Teile ankommen und die
  Gesamtlaufzeit innerhalb des 120-Sekunden-Scheduler-Budgets bleibt.
- Bestehende Guard-Suite `tests/tdd/test_telegram_test_isolation.py`
  (AC-1…AC-8) bleibt unverändert grün.

## Changelog

- 2026-07-25: Initial spec erstellt — Issue #1370
