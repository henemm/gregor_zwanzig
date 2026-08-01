# Kontext & Analyse: #1448 Scheibe S3 — Telegram-Bremse und open-meteo ohne Zeitgrenze

**Workflow:** `fix-1448-s3-telegram-openmeteo` · **Typ:** Bug · **Issue:** #1448 (Blockierer B2 + Nachtrag)
**Erstellt:** 2026-08-01 · **Vorgänger:** S1 (`5b97542a`) und S2 (`a14a152c`) live

## Type

Bug — nutzersichtbares Fehlverhalten: beide Stellen können einen Alarm-Lauf unbegrenzt
anhalten und damit eine Wetterwarnung verzögern. Letzte der drei Scheiben.

## Befund A — Telegram-Drosselbremse ohne Obergrenze

`src/output/channels/telegram.py:210-250`, `_reserve_send_slot()`:

- `while True`-Schleife. Liegen ≥ `telegram_rate_limit_max_per_window` (18) Zeitstempel im
  gleitenden Fenster (60 s), wird geschlafen, **bis der älteste herausfällt** — und danach
  **erneut geprüft**. Jede Runde kann bis zu einer vollen Fensterlänge warten, und die Zahl
  der Runden ist **nicht begrenzt**.
- Die Buchführung zählt **alle** Schreibzugriffe desselben Chats mit. Ein Alarm kann also an
  den Nachrichten eines langen Briefings hängen.
- Aufgerufen in `_post()` (`:285`), **vor** dem eigentlichen `httpx.post`.

**Die Autoren kannten das Problem bereits** — Kommentar bei `:301-305`: „…sonst hängte an der
gedeckelten Wartezeit die **UNGEDECKELTE** Wartezeit von `_reserve_send_slot` (bis zu einer
vollen Fensterlänge) dran". Sie haben es an *einer* Stelle umgangen (keine zweite Reservierung
nach 429), die Wurzel aber stehen lassen.

**Was bereits korrekt gedeckelt ist und NICHT angefasst wird:** die 429-Wiederholung selbst
(`:252-265`, ≤45 s, konform zu `docs/specs/modules/telegram_send_pacing.md`).

**Die Spec kennt die Größenordnung schon** (`telegram_send_pacing.md:208-218`, vom damaligen
Adversary nachgemessen): Serien ab ~40 Teilen brauchen allein durch die Drosselung ~120 s; zwei
echte 429 in einer Serie ergäben ~150 s. Damals als „jenseits des spezifizierten Umfangs,
funktional unschädlich" eingestuft und als Restrisiko nach #1199 gegeben — **diese Bewertung
ist durch #1447 S1 überholt**: Der Alarm-Lauf hat jetzt ein Budget von 90 s
(`ALERT_RUN_DEADLINE_SECONDS`, `trip_alert.py:40`). Was damals nur „der Go-Zeitplaner gibt
vorher auf" bedeutete, verzögert heute messbar eine Warnung.

## Befund B — open-meteo ohne Gesamt-Zeitbudget

`src/providers/openmeteo.py`. Als **einziger** Wetterquelle fehlt ihr die Schranke, die die
beiden anderen haben (`dwd.py:69`, `meteofrance.py:85`, je `FETCH_DEADLINE_SECONDS = 180.0`).
Belegt in der #1447-Analyse, dort bewusst nach #1448 verschoben.

Rechnung für **einen** `_request`-Aufruf (`:505-512`):

| Größe | Wert | Fundstelle |
|---|---|---|
| HTTP-Timeout je Versuch | 30 s | `:61` `TIMEOUT`, `:248` |
| Versuche | 5 | `:97` `RETRY_ATTEMPTS` |
| Backoff | `wait_exponential(min=2, max=60)` ⇒ 2+4+8+16 = 30 s | `:98-99`, `:507` |

⇒ **bis ~180 s je `_request`.** Dazu ruft `fetch_forecast` die Kandidaten-Modelle nacheinander
(`:823`, `_candidate_models`); Folge-Kandidaten haben zwar nur einen Versuch
(`FALLBACK_RETRY_ATTEMPTS = 1`, `:103`, Issue #1155), aber je 30 s Timeout. Und der ganze
Vorgang läuft **je Segment**.

## Werte-Vorschlag mit Begründung

| Konstante | Wert | Begründung |
|---|---|---|
| `SEND_SLOT_MAX_WAIT_SECONDS` (telegram) | 30.0 | Im Normalfall wartet die Bremse **gar nicht** (unter 18 Nachrichten/60 s wird sofort gesendet). 30 s trifft nur den echten Stau und bleibt deutlich unter dem 90-s-Lauf-Budget. |
| `FETCH_DEADLINE_SECONDS` (openmeteo) | 60.0 | Der Normalfall liegt **unter 1 s** (belegt in der #1447-Analyse: hunderte Läufe, Ausreißer 27 s/49 s). 60 s sind ~60-fache Reserve und bleiben unter den 90 s des Alarm-Laufs. |

**Warum openmeteo 60 s statt der 180 s von dwd/meteofrance:** Die beiden anderen sind
**Fallback**-Quellen, die selten und einzeln greifen. open-meteo ist die **Hauptquelle** und wird
**je Segment** aufgerufen — 180 s je Aufruf wären im Alarm-Kontext sinnlos, weil die
Lauf-Grenze (90 s) längst vorher zuschlägt und der Lauf dann als Teilerfolg endet, ohne dass
die Provider-Ebene je aufgegeben hätte. Die Abweichung ist also begründet, nicht nachlässig.

## Was bei Überschreitung passieren soll

- **open-meteo:** `ProviderRequestError` werfen — exakt das Muster von `dwd.py:185-189` /
  `meteofrance.py:202-206`. Der Aufrufer hat bereits eine Fallback-Kette; ein Provider, der
  aufgibt, ist ein vorgesehener Zustand.
- **Telegram:** Fehler statt endlosem Warten (so auch der Issue-Vorschlag). **Konsequenz klar
  benennen:** Die betroffene Nachricht geht dann *nicht* raus. Das ist der bewusste Tausch —
  aber der Fall tritt nur ein, wenn derselbe Chat bereits ≥18 Nachrichten in 60 s bekommen hat
  **und** die Wartezeit 30 s übersteigt. Eine Alarm-Nachricht hinter einem solchen Stau käme
  ohnehin verspätet. Die Alternative „trotzdem senden" wurde verworfen: sie verletzt die
  Drossel-Zusage aus `telegram_send_pacing.md` und riskiert eine Telegram-seitige Sperre.

**Die Lehre aus S1/S2 gilt auch hier:** Eine neue Zeitgrenze verwandelt lautes Hängen in stille
Fehler, wenn ein zu breiter `except` im Weg sitzt. Beide Abbrüche müssen **sichtbar** sein
(WARNING/ERROR mit Kontext), und es ist zu prüfen, ob ein Aufrufer den neuen Fehler verschluckt.

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/channels/telegram.py` | MODIFY | Obergrenze für `_reserve_send_slot`, Fehler + Logzeile bei Überschreitung |
| `src/providers/openmeteo.py` | MODIFY | `FETCH_DEADLINE_SECONDS` + mitgeführte Deadline in `fetch_forecast`/`_request` |
| `docs/specs/modules/telegram_send_pacing.md` | MODIFY | Restrisiko-Eintrag (`:208-218`) auf den nun begrenzten Stand ziehen |
| `tests/tdd/test_send_slot_and_fetch_deadline.py` | CREATE | Nachweis für beide Grenzen |

## Scope Assessment

- Dateien: 2 Quellcode, 1 Spec-Nachzug, 1 Testdatei
- Geschätzt: ~+70/-15 Code, ~+200 Test ⇒ über dem 250er-Budget, Freigabe nötig
- Risiko: **MITTEL** — `telegram.py` ist Versandpfad (aber **keine** Mail-Inhalts-Datei ⇒ kein
  Renderer-Mail-Gate). `openmeteo.py` ist die Hauptwetterquelle: ein zu knappes Budget würde
  unter echter Last Abrufe abbrechen, die heute noch durchkommen.

## Bekannte Grenze, die S3 NICHT schliesst

Die **Provider-Kette als Ganzes** hat weiterhin kein Budget: Gibt open-meteo nach 60 s auf,
darf die Fallback-Kette (dwd/meteofrance, je 180 s) danach erneut ansetzen. Die Summe kann also
weiterhin über dem Lauf-Budget liegen — abgefangen wird das dann von der Lauf-Grenze aus
#1447 S1 (Teilerfolg), nicht von der Provider-Ebene. Ein Ketten-Budget wäre eine eigene Scheibe.

## Nachweis (Muster)

`tests/tdd/test_meteofrance_direct_fallback.py:476-517` — echter langsamer lokaler Server,
Grenzen per `monkeypatch` auf Millisekunden, Erwartung ist ein sichtbarer Fehler statt
unbegrenztem Warten. Kein Mock. Für Telegram: **kein** Live-Versand — die Bremse ist reine
lokale Buchführung (`TelegramOutput._rate_limit_stamps`) und lässt sich ohne Netz füllen.

⚠️ **Falle:** Die Drossel-Buchführung ist ein **Klassenattribut**
(`TelegramOutput._rate_limit_stamps`, `:227`) — sie überlebt zwischen Tests. Ohne Zurücksetzen
in einer Fixture beeinflussen sich Tests gegenseitig und werden zufällig grün oder rot.

## Open Questions

- [x] Werfen oder trotzdem senden bei Telegram-Überschreitung? → werfen; „trotzdem senden"
      verletzt die Drossel-Zusage und riskiert eine Telegram-Sperre.
- [ ] Die zwei Sekundenwerte (30 / 60) — in der Spec mit Rechnung, PO-Freigabe über die ACs.
