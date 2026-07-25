# Context: fix-1370-telegram-pacing

Issue: [#1370](https://github.com/henemm/gregor_zwanzig/issues/1370) — „Telegram: stiller Verlust halber Briefings bei langen Touren"

## Request Summary

Bei mehrsegmentigen Touren erzeugt ein Telegram-Briefing zweistellige Nachrichtenzahlen, die ohne Pause an denselben Chat gehen. Telegram antwortet ab ~20 Nachrichten/Minute mit HTTP 429; der Produktivcode erkennt 429 nicht als Rate-Limit, wirft `OutputError` und bricht die Bubble-Serie mit `break` ab — der Nutzer bekommt ein halbes Briefing ohne jede Fehlermeldung.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/channels/telegram.py:234, 289, 330, 375, 398, 421, 443` | **Sieben separate `httpx.post`-Aufrufe ohne gemeinsamen Helfer.** Kein Pacing, kein 429-Zweig (`else` ab Z. 257 wertet jeden Nicht-200 als Permanentfehler) |
| `src/services/notification_service.py:340-358` | Bubble-Schleife des Trip-Reports — **einzige Stelle mit N Nachrichten in Folge**; `break` bei Fehler (Z. 356), nur `logger.error` |
| `src/services/trip_report_scheduler.py:45, 265` | **Vorbild im Haus:** `INTER_MAIL_DELAY_SECONDS = 2` + `time.sleep()` zwischen Mails verschiedener Trips |
| `src/services/official_alerts/warn_egress.py:82-96, 141-203` | **Vorbild im Haus:** zentrale 429-Behandlung mit `_parse_retry_after()` (liest Sekunden aus Antwort), lautes Logging |
| `src/output/channels/email.py:529-618` | Vorbild: Exponential Backoff 5s/15s/30s, unterscheidet temporär vs. permanent |
| `src/services/inbound_telegram_reader.py:172-258, 300-335, 406` | Sendet Lade-Nachricht + `delete_message`/`edit_message_text` **um die Bubble-Serie herum** — zählt auf dasselbe Chat-Limit |
| `src/output/renderers/narrow.py:457, 514-517` | `render_telegram_bubbles()` — erzeugt Kopf + Warn-Bubbles + Übersicht + eine Bubble je Segment + Ausblick + Aktionen |
| `tests/tdd/_telegram_live_fixture.py:42-91` | **Bewiesene Referenzlösung** (nur Testpfad): 3,5 s Pacing + `retry_after`-Backoff, max 2 Versuche, gepatcht auf `httpx.post` |
| `internal/scheduler/scheduler.go:82, 371-398` | Go-Scheduler ruft den Python-Core mit **`http.Client{Timeout: 120s}`** — harte Obergrenze für den gesamten Versandlauf |

## Existing Patterns

- **Pacing existiert bereits** im Haus (`INTER_MAIL_DELAY_SECONDS`), aber nur für E-Mail und nur zwischen Trips.
- **429-Parsing existiert bereits** (`warn_egress._parse_retry_after`) — beim Abruf amtlicher Warnungen, nicht beim Senden.
- **Retry-Muster:** Wetter-Provider nutzen `tenacity` (`@retry`, `wait_exponential`), Mail nutzt handgeschriebenen Backoff, SMS gar keinen.
- **Sichtbarer Hinweis bei fehlenden Daten** (#1348) ist ein **eigener Baustein innerhalb der Nachricht**, keine Extra-Nachricht: `render_official_alerts_unavailable_*` in E-Mail als Danger-Box, in Telegram als eigene `TelegramBubble` direkt nach dem Kopf (`narrow.py:34-37`).
- **Egress-Guards** (#1288/#1363/#1337): vor **jedem** POST an api.telegram.org müssen Token-Guard **und** Chat-Guard gelaufen sein, fail-closed. Abgesichert durch `tests/tdd/test_telegram_test_isolation.py` (AC-1…AC-8, prüft `calls == []`) und `test_telegram_test_mode_guard.py`.

## Dependencies

- **Upstream:** `httpx` (kein zentraler HTTP-Client-Wrapper vorhanden), `Settings` (Token/Chat-IDs), Egress-Guards.
- **Downstream (Aufrufer der Bubble-Schleife):**
  - `trip_report_scheduler.py:932` — geplanter Versand (Morgen/Abend)
  - `trip_command_processor.py:525` — On-Demand `/heute`, `/morgen`
  - `api/routers/scheduler.py:29, 114` — HTTP-Trigger, aufgerufen vom Go-Scheduler
- **Downstream (Einzel-Nachrichten, ebenfalls limitrelevant):** alle Alert-Pfade (`trip_alert.py`, `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py`) sowie sämtliche Inbound-Reader-Antworten.

## Existing Specs

- `docs/specs/modules/api_retry.md` — Retry-Politik der Wetter-Provider (Tenacity-Muster, retryable Status-Codes)
- ADR-0012 (Telegram-Renderpfad) — vom 400-Fallback in `telegram.py:274-279` referenziert; Änderungen am Sendepfad dürfen nicht dagegen laufen

## Risks & Considerations

1. **Go-Timeout 120 s ist die harte Grenze.** 15 Bubbles × 3,5 s = ~53 s allein für Telegram, zuzüglich Wetterabruf und Rendering im selben Request. Ein 8-Wegpunkte-Tag kann die 120 s reißen — dann bricht der Go-Scheduler den Lauf ab und der Fix hätte den Fehler nur verschoben. **Pacing-Wert muss gegen dieses Budget gerechnet werden**, nicht blind aus dem Test-Fixture übernommen.
2. **Pacing gehört in den Kanal, nicht in die Schleife.** Nur die Bubble-Schleife zu pacen ließe Lade-Nachricht, `delete_message` und Alert-Versand ungepact — die zählen aufs selbe Chat-Limit. Sieben `httpx.post`-Aufrufe ohne gemeinsamen Helfer ⇒ zuerst auf **einen** privaten POST-Helfer konsolidieren, dort Pacing + 429 einbauen (deckt sich mit der Projektregel „Code-Duplikate konsolidieren").
3. **Kern-Tests dürfen nicht wirklich schlafen.** `pyproject.toml:63` setzt `timeout = 30` für alle Tests; `test_issue_1001_telegram_bubbles.py:347-404` sendet 3+ Bubbles ohne Timeout-Override. Die Pause muss konfigurierbar/injizierbar sein (z. B. Pacing-Sekunden aus Settings, im Test 0) — sonst laufen bestehende Tests in den Timeout.
4. **Egress-Guard-Invariante darf nicht brechen.** Beim Konsolidieren auf einen POST-Helfer müssen beide Guards weiterhin **vor** dem POST laufen; `test_telegram_test_isolation.py` prüft das für fünf Methoden.
5. **Retry verlängert im Fehlerfall zusätzlich.** Ein `retry_after` von 35–43 s in einem 120-s-Budget lässt höchstens einen Wiederholversuch zu — mehr als ein Retry ist im Scheduler-Kontext nicht finanzierbar.
6. **Offene Produktentscheidung (gehört in die Spec):** Bei endgültigem Fehlschlag einer Bubble — restliche Bubbles trotzdem senden (Lücke in der Mitte) oder abbrechen mit sichtbarem „Briefing unvollständig"-Hinweis? Das Haus-Muster (#1348) spricht für einen sichtbaren Hinweis-Baustein statt stillem Verschlucken.
7. **Gleichzeitigkeit:** Scheduler-Versand und ein parallel getipptes `/heute` desselben Nutzers addieren sich auf denselben Chat. Ein prozessweiter Pacing-Zeitstempel (wie im Fixture) deckt das nur innerhalb eines Prozesses ab — Python-Core und Go-Scheduler laufen getrennt, aber beide Wege münden im selben Python-Prozess (`api/routers/scheduler.py`), daher praktisch ausreichend.

---

## Analysis

### Type

Bug (Ursache im Issue mit Datei:Zeile belegt, hier durch Code-Lesen bestätigt).

### Wie viele Nachrichten entstehen wirklich? (belegt, nicht geschätzt)

`render_telegram_bubbles()` (`narrow.py:457-574`) erzeugt: Kopf (1) + optionaler „nicht abrufbar"-Hinweis (0/1) + **eine gebündelte** Warn-Bubble für alle Warnungen (0/1) + Kurzübersicht (1) + **eine Bubble je Segment** + optionaler Ausblick (0/1, nur abends) + Aktionen (1).

Ein Tag mit N Wegpunkten ergibt exakt N Segmente (`trip_segments.py:213-259`: N-1 Wander-Segmente + 1 „Ziel"-Segment). **Formel: B = N + 3 + w + o.**

| Wegpunkte | Bubbles minimal | typisch abends | worst case |
|---|---|---|---|
| 2 (Test-Trip) | 5 | 6 | 7 |
| 6 | 9 | 10 | 11 |
| 8 | 11 | 12 | 13 |

Bei `/heute` kommen Lade-Nachricht + deren Löschung hinzu (`inbound_telegram_reader.py:234-250`) ⇒ **bis 14 POSTs** an denselben Chat in einem Lauf. Warnungen vervielfachen die Zahl **nicht** (sie werden in eine Bubble gebündelt).

### Zeitbudget — zwei Pfade, zwei völlig verschiedene Grenzen

- **Scheduler (geplanter Versand):** `internal/scheduler/scheduler.go:82` — `http.Client{Timeout: 120s}`, **pro Nutzer**. Der Versand liegt synchron darin (`api/routers/scheduler.py:28-44` ist kein `async def` → `dispatch_orchestrator.run_briefing_dispatch` → Bubble-Schleife). Nach Abzug von Wetterabruf/Rendering und einem reservierten 429-Retry (~40 s) bleiben rechnerisch **max. ~4,3 s Pacing pro Nachricht** bei 8 Wegpunkten.
- **On-Demand (`/heute`) — im Kontext zunächst übersehen:** `internal/handler/telegram_webhook.go:38` leitet den Webhook mit einem **5-s-Client** an den Python-Core weiter (`api/routers/webhook.py:50-72`, ebenfalls synchron). Jedes nennenswerte Pacing reißt diese 5 s. **Funktional unschädlich:** Go antwortet Telegram unbedingt mit 200 (`telegram_webhook.go:72`), der synchrone Python-Handler läuft im Thread zu Ende — der Nutzer bekommt sein Briefing. Nebeneffekt ist eine irreführende `forward error`-Logzeile in Go.

### Entscheidung: gleitendes Zeitfenster statt starrer Pause

Eine konstante Pause von 3,5 s pro Nachricht (wie im Test-Fixture) würde **jedes** Briefing verlangsamen — auch das typische mit 5-7 Bubbles, das heute in ~2 s zugestellt wird (dann ~20 s). Das ist eine Verschlechterung für den Normalfall, um einen Randfall zu heilen.

Telegrams Grenze ist tatsächlich ein gleitendes Fenster (~20 Nachrichten/Minute pro Chat). Deshalb: **Zähler über die letzten 60 s pro Chat, Obergrenze 18.** Solange weniger als 18 Nachrichten im Fenster liegen, wird **gar nicht** gewartet; erst danach wartet der Sender, bis wieder Platz ist.

Wirkung: **kein einziges reales Briefing (5-13 Bubbles) wird langsamer** — die Bremse greift erst ab ~15 Wegpunkten am Tag. Der 5-s-Webhook bleibt im Normalfall eingehalten, das Scheduler-Budget von 120 s wird nicht angetastet, und gleichzeitiger Scheduler- + `/heute`-Versand an denselben Chat wird korrekt mitgezählt.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/channels/telegram.py` | MODIFY | Ein privater POST-Helfer ersetzt die 7 `httpx.post`-Zeilen; darin Zeitfenster-Bremse + 429-Wiederholung |
| `src/app/config.py` | MODIFY | Zwei Settings-Felder (Fenster-Obergrenze, max. Wiederholungen) nach bestehendem `Field(default=...)`-Muster |
| `src/services/notification_service.py` | MODIFY | Bubble-Schleife: kein stiller Abbruch mehr |
| `src/output/renderers/narrow.py` | MODIFY | Textbaustein „Briefing unvollständig" analog zum Nicht-verfügbar-Hinweis (#1348) |
| `tests/…` | CREATE/MODIFY | Kern-Tests für Bremse + 429; zwei live-markierte Bubble-Tests nachziehen |

### Scope Assessment

- Dateien: 4 Produktivdateien + Tests
- Geschätzt: ~+130 / -20 LoC (Produktivcode ~+80)
- Risiko: **MEDIUM**

### Technical Approach

Der private Helfer kapselt **ausschließlich** POST + Bremse + 429-Wiederholung und gibt die rohe Antwort zurück. Die Egress-Guards bleiben unverändert **vor** dem Helfer in jeder öffentlichen Methode stehen, und die Auswertung des Statuscodes (Ausnahme werfen vs. fail-soft vs. 400-Fallback) bleibt je Methode wie bisher — beides darf der Helfer **nicht** vereinheitlichen. Grund: `test_telegram_test_isolation.py` sichert die Guard-Reihenfolge für fünf Methoden ab, und `answer_callback_query`/`get_my_commands` haben bewusst **keine** Chat-Guards; ein guard-aufrufender Helfer würde deren Verhalten ändern.

`retry_after` wird aus dem **JSON-Rumpf** gelesen (`response.json()["parameters"]["retry_after"]`, wie im bewiesenen Live-Fixture) — **nicht** über `warn_egress._parse_retry_after()`, das den HTTP-Header eines anderen Dienstes liest.

### Risks

- `tests/tdd/test_telegram_test_isolation.py` (AC-1…AC-8) muss unverändert grün bleiben — nur gegeben, wenn der Helfer keine eigenen Guards mitbringt.
- `tests/tdd/test_issue_1001_telegram_bubbles.py:349-404` und `:842-879` schreiben das heutige „still abbrechen"-Verhalten fest (live-markiert, laufen nicht in der Kern-Suite) — müssen ans neue Verhalten angepasst werden, sonst driften sie ab.
- Tests, die Bubble-Anzahlen exakt zählen, brechen durch die zusätzliche Hinweis-Nachricht.
- Betrieb: `forward error`-Lograuschen in Go bei sehr langen On-Demand-Briefings.

### Open Questions

- [ ] Verhalten bei endgültigem Fehlschlag einer Nachricht: Rest trotzdem senden, oder abbrechen mit sichtbarem Hinweis? (Produktentscheidung — dem PO vorgelegt)
