---
entity_id: sms_daily_limit
type: feature
created: 2026-09-24
updated: 2026-09-24
status: draft
workflow: feat-2153-s4-sms-tageslimit
version: "1.0"
tags: [tiers, sms, premium-sms, cost-guard, epic-2138]
---

# SMS-/Premium-SMS-Tageslimit je Nutzer (S4a — Durchsetzung)

## Approval

- [ ] Approved

## Purpose

Deckelt den täglichen Versand über die Kanäle SMS und Premium-SMS je Nutzer, damit ein
einzelnes Nutzerkonto (durch viele Trip-Briefings oder eine Alarm-Häufung) keine unbegrenzten
Versandkosten verursacht. Briefing- und Alarm-SMS werden dabei je Kanal in EINEM Zähler
zusammengezählt, mit einer festen Reserve, die frühe Briefings nicht für spätere Alarme
aufbrauchen können — begründet dadurch, dass die Empfangslage unterwegs unvorhersehbar ist und
jeder Kanal jede Frage beantworten können muss (CLAUDE.md, PO-Korrektur 2026-09-05). Diese Spec
deckt ausschließlich die Durchsetzung im Python-Core ab (S4a); die Sichtbarkeit des Zählers im
Konto (S4b) ist ein eigener Folge-Workflow.

## PO-Entscheidungen (2026-09-24, verbindlich)

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Premium-SMS trotz „Premium: kein Tageslimit" (PO 2026-07-07, Alarm-FREQUENZ) deckeln? | Ja — Kosten-Deckel NUR für den Kanal Premium-SMS; E-Mail/Telegram bleiben für Premium unbegrenzt. Die Entscheidung vom 07.07. bleibt bestehen (sie betrifft die Alarm-Häufigkeit, nicht Kosten). |
| E2 | Tageswechsel | UTC-Mitternacht (= 02:00 MESZ / 01:00 MEZ) — reine Kosten-Referenzgröße pro Nutzerkonto, kein wetter-/tourfachlicher Kalendertag. |
| E3 | Limitwerte / Zähler | Zwei getrennte Zähler `sms` und `premium_sms`. `free` 0, `standard` 10 SMS/Tag, `premium` 10 SMS/Tag + 15 Premium-SMS/Tag. |
| E4 | Garmin-Antwort bei erreichtem Premium-SMS-Limit | Kleine feste Zusatzmenge (3/Tag) über dem Grundlimit, danach gesperrt. |

Alarm-Reserve (Tech-Lead-Default): Briefings dürfen nur bis `limit − reserve` belegen, Alarme
bis `limit`. Reserve 2 von 10 (SMS), 3 von 15 (Premium-SMS).

## Source

- **File:** `src/services/sms_daily_limit.py` (neu)
- **Identifier:** `check_and_reserve(user_id, kind, purpose, now)`, `release_reservation(user_id, kind, now)`

> **Schicht-Hinweis:** Neues Modul und beide Modify-Ziele liegen im Python-Core unter
> `src/services/` (FastAPI-Domain-Backend). Keine Go- oder Frontend-Änderung in dieser Scheibe
> (S4b bringt die Go-/Frontend-Anteile).

## Estimated Scope

- **LoC:** ~200–240 (Produktionscode, ohne Tests und Doku-Nachträge; oberer Rand, weil
  `send_official_alert`, `send_compare_report` und `_dispatch_compare_official_sms` zusätzlich zum
  reinen Gate auch neue `blocked_channels`-Felder/Parameter bekommen, s. Sendestellen-Tabelle)
- **Files:** 3 Produktionsdateien (`sms_daily_limit.py` neu, `user_tier.py`, `notification_service.py`) + 1 neue Testdatei + 2 Doku-Nachträge (zählen nicht ins LoC-Limit)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/file_lock.py` (`acquire_exclusive`, `LOCK_TIMEOUT_SECONDS`) | module | Exklusive Kurzsperre auf einer Sidecar-Lockdatei (nicht auf der Zieldatei selbst — Vorbild `throttle_store.py`) |
| `src/app/loader.py` (`get_data_dir(user_id)`) | module | Liefert den Nutzer-Datenordner, in dem `sms_daily_count.json` liegt |
| `src/services/user_tier.py` | module | Neue Limitwerte/Reserven je Tier und Kanal (Ergänzung neben bestehendem `sms_allowed`/`premium_sms_allowed`) |
| `src/services/throttle_store.py`, `src/services/forecast_budget.py` | pattern | Bauvorbild für Sidecar-Lock + atomares `tempfile`+`os.replace`-Schreiben UND für das projektweit etablierte Fail-Open-Verhalten bei Lock-Timeout (`throttle_store.py:165-206`, `forecast_budget.py:369-390`, beide: WARNING loggen, Schreiben/Prüfen überspringen, nie werfen) |
| `src/output/channels/base.py` (`ChannelBlockedError`) | module | Trägt den neuen `reason_code="sms_daily_limit_exceeded"` in `blocked_channels`/`blocked_reason_codes`. Ist `OutputConfigError`-Unterklasse — muss an JEDER der 12 Stellen lokal gefangen werden und darf NIE propagieren (ein bestehender `except OutputConfigError: raise`-Zweig existiert nur im Telegram-Pfad von `send_compare_report:1246-1248`, betrifft SMS/Premium-SMS nicht, aber macht das Catch-Gebot explizit) |
| `src/services/alert_daily_limit.py` | pattern | Bauvorbild für Reserve-Mechanik (`_FORECAST_CHANGE_RESERVE`) — NICHT als Laufzeit-Abhängigkeit; das bestehende Alarm-Frequenz-Limit bleibt ein eigener, vorgeschalteter Gate-Schritt |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py` (`_aufzeichner_installieren`, Zeilen 136-184) | pattern | Etabliertes Test-Muster: `monkeypatch.setattr(notification_service, "SMSOutput"/"PremiumSmsOutput", <Aufzeichner-Klasse>)` — kein `Mock()`/`patch()`, sondern eine echte Fake-Klasse, die Aufrufe aufzeichnet bzw. gezielt fehlschlagen lässt |
| `tests/conftest.py:186-209` | fixture | `_DATA_ROOT`-Umbiegung gilt nur SESSIONWEIT — jeder neue Test (auch der neue AC-8-Test) braucht eine eigene, eindeutige `user_id`, sonst leaken vorgeseedete Zählerdateien zwischen Tests |
| `src/services/inbound_sms_reader.py` | caller | Ruft `NotificationService(..., user_id=user_id).send_command_reply_premium_sms(...)` für Ad-hoc-Antworten auf eingehende SMS — grep-verifiziert: KEIN Aufruf von `send_trip_report` dort, Ad-hoc-Antworten zählen also immer als `purpose="reply"`, nie als Briefing |

## Scope: NUR S4a (Durchsetzung) — S4b ist eigener Folge-Workflow

**Ausdrücklich NICHT Teil dieser Spec:** `GET /api/_internal/sms/daily-usage`
(`api/routers/internal.py`), Go-Anbindung (`internal/handler/auth.go`, `internal/model/user.go`)
und die Anzeige in `frontend/src/routes/account/+page.svelte`. S4a liefert die Durchsetzung
vollständig; Sichtbarkeit bleibt vorerst Log + `blocked_channels`. **Folge für `/70-deploy`:**
Issue #2412 und Sammel-Issue #2153 bleiben nach diesem Deploy **OFFEN** — kein `gh issue close`,
stattdessen ein Stand-Kommentar auf #2412, der auf den ausstehenden S4b-Workflow verweist.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/sms_daily_limit.py` | CREATE | Neues Zähler-Modul, zwei Töpfe (`sms`/`premium_sms`), UTC-Tagesgrenze, Reserve-und-Rollback-Reservierung unter Sidecar-Sperre |
| `src/services/user_tier.py` | MODIFY | Neue Funktionen für Limitwerte/Reserven je Tier und Kanal (s. Implementation Details) |
| `src/services/notification_service.py` | MODIFY | Dünnes Gate an allen 12 Sendestellen für `SMSOutput`/`PremiumSmsOutput`; neuer/erweiterter `except ChannelBlockedError`-Zweig je Stelle; `sms_daily_limit.release_reservation(...)` im jeweiligen Fehlerzweig; drei Stellen bekommen zusätzlich neue `blocked_channels`/`blocked_reason_codes`-Verdrahtung, wo bisher keine existierte (`send_official_alert` SMS-Zweig, `send_compare_report`, `_dispatch_compare_official_sms` inkl. neuer Parameter) |
| `tests/tdd/test_sms_tageslimit.py` | CREATE | Verhaltens-Tests: Zwei-Nutzer-Isolation, UTC-Grenze, Reserve, Garmin-Zusatzmenge, Nebenläufigkeit, E-Mail/Telegram unberührt, bestehendes Alarm-Frequenz-Limit bleibt wirksam |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY (Doku, außerhalb LoC-Limit) | Zusatz „Nicht betroffen: der SMS-/Premium-SMS-Kostendeckel" nach der bestehenden Nicht-betroffen-Passage (Zeile 40) |
| `docs/specs/modules/epic_user_tiers_overview.md` | MODIFY (Doku, außerhalb LoC-Limit) | Nachtrag zur Tier-Tabelle (Zeilen 25–29): Premium-SMS bekommt trotz „kein Tageslimit für Alarm-Frequenz" (PO 2026-07-07) einen eigenen Kosten-Deckel |

## Sendestellen (verifiziert per Read/Grep, `src/services/notification_service.py`, Stand 84b50d72)

| Methode | Zeile(n) | Kanal | `purpose` | Vorhandener Sink/Fehlerzweig |
|---|---|---|---|---|
| `send_trip_report` | 600 / 618 | sms / premium_sms | briefing | Kein Sink, direkter `.send()`, Append NACH erfolgreichem `.send()` (korrekt). SMS: nur `logger.error`, kein `blocked_channels` heute (NEU ergänzen). Premium: bereits `blocked_channels` (623-624). |
| `send_no_data_hint` | 769 / 776 | sms / premium_sms | briefing | Kein Sink, Append NACH erfolgreichem `.send()` (korrekt). SMS: nur `logger.error` (NEU ergänzen). Premium: bereits `blocked_channels` (778-780). |
| `send_compare_report` | 1252-1260 (nur sms) | sms | briefing | Echter `sms_sink`-Parameter vorhanden. Append NACH Versuch (korrekt). **Kein `blocked_channels`/`blocked_reason_codes` in dieser Methode überhaupt** (`NotificationResult(sent=…, sent_channels=…)` bei 1262 — NEU: beide Dicts anlegen und in den Return aufnehmen). |
| `send_official_alert` | 1139-1149 (sms) / 1155-1164 (premium_sms) | sms / premium_sms | alert | Echter `sms_sink`-Parameter (sms) vorhanden. **Beide Kanäle: `sent_channels.append` steht VOR dem `try` (1140, 1156)** — dasselbe Muster wie bei `_dispatch_alert_message`, gehört mit in den Nebenbefund/Gate-vor-Append-Umbau. SMS: `failed_channels`, kein `blocked_channels` (NEU ergänzen). Premium: bereits `blocked_channels` (1161-1163). |
| `_dispatch_compare_official_sms` (SMS-Helfer, aufgerufen aus `send_multi_location_official_alert`) | 1436-1452, Aufruf 1354-1358 | sms | alert | Echter `sms_sink`-Parameter vorhanden. Gibt `bool` zurück; Aufrufer (1353-1358) appendet `sent_channels` UNBEDINGT nach dem Aufruf, unabhängig vom Rückgabewert — bei Sperre MUSS die Methode `False` zurückgeben (wie der Premium-Helfer daneben), damit der Aufrufer `failed_channels.append("sms")` auslöst und `delivered_channels` den Kanal korrekt ausschließt. Signatur wird um `blocked_channels`/`blocked_reason_codes`-Parameter erweitert (NEU, mirrort `_dispatch_compare_official_premium_sms`). |
| `_dispatch_compare_official_premium_sms` (Premium-Helfer, aufgerufen aus `send_multi_location_official_alert`) | 1454-1473, Aufruf 1366-1370 | premium_sms | alert | Kein Sink, direkter `.send()`. Bereits `blocked_channels`-Parameter vorhanden (1456), gibt bei Fehler bereits `False` zurück — Gate fügt sich in dasselbe Muster ein. |
| `_dispatch_alert_message` (Radar, aufgerufen von `send_radar_alert`) | 1783 / 1797 | sms / premium_sms | alert | Kein Sink, direkter `.send()`. **Beide Kanäle: `sent_channels.append` steht VOR dem `try` (1781, 1795)** — Nebenbefund, s.u. SMS: nur `logger.error`, kein `blocked_channels` (NEU ergänzen). Premium: bereits `blocked_channels` (1799-1800). |
| `send_command_reply_premium_sms` | 1834 | premium_sms | reply | Kein Sink, kein `NotificationResult` (`-> None`). Nur `logger.error`. Beobachtbar ausschließlich über Monkeypatch der `PremiumSmsOutput`-Klasse (kein Sink-Parameter vorhanden). |

Außerhalb dieser Scheibe: `api/routers/internal.py:195` (SMS-Verifikationscode, eigene
In-Memory-Bremse aus S3/#2406) und die Legacy-CLI (`src/app/cli.py`, Debug-Werkzeug).

## Implementation Details

**Modul `src/services/sms_daily_limit.py`:**
- Datenfile `<get_data_dir(user_id)>/sms_daily_count.json`, Schema
  `{"date": "YYYY-MM-DD", "sms": N, "premium_sms": M}` — EIN Datum für beide Töpfe (beide
  UTC-getaktet). Sperre liegt, wie in `throttle_store.py`/`forecast_budget.py` etabliert, auf
  einer **Sidecar-Datei** `sms_daily_count.json.lock`, NICHT auf der Datendatei selbst (die per
  `tempfile`+`os.replace` ihre Inode tauscht — ein Lock darauf würde nach dem Replace nichts mehr
  serialisieren).
- `now` ist durchgehend Funktionsparameter (Zeit-Injektion, kein `datetime.now()` im Modul
  selbst). Tageswechsel: `now.astimezone(timezone.utc).date()` gegen das gespeicherte `date`.
- `check_and_reserve(user_id, kind, purpose, now) -> None`: öffnet die Sidecar-Lockdatei, holt
  `file_lock.acquire_exclusive(fd, LOCK_TIMEOUT_SECONDS)`. Innerhalb der Sperre: Datendatei laden
  (Reset auf 0 bei Tageswechsel), Obergrenze (`cap`) für `kind`+`purpose` ermitteln (Tabelle
  unten), gegen den aktuellen Tageswert vergleichen. Ist `cap` erreicht: **kein Increment**,
  danach `raise ChannelBlockedError(kind, "SMS-Tageslimit erreicht", reason_code="sms_daily_limit_exceeded")`.
  Sonst: Zähler um 1 erhöhen (**Reservierung**), Datendatei atomar schreiben, normal zurückkehren.
- `release_reservation(user_id, kind, now) -> None`: Gegenstück zur Reservierung — dekrementiert
  den Tageswert für `kind` um 1 unter derselben Sperre. **Nur** aus dem `except`-Zweig eines
  tatsächlich fehlgeschlagenen `.send()`-Aufrufs gerufen, nie bei einer Sperre. **Randfall
  Tageswechsel:** stimmt das gespeicherte `date` beim Release nicht mit `date(now)` überein (z.B.
  Reservierung um 23:59:59, Fehlschlag-Meldung um 00:00:01), wird **nicht** dekrementiert
  (No-op) — ein Rückbuchen in den bereits zurückgesetzten neuen Tag wäre falsch. Der Zähler geht
  außerdem nie unter 0 (Floor). Beide Fälle sind bewusst konservative Näherungen, dokumentiert in
  Known Limitations.
- **Fail-Open bei Lock-Timeout** (`acquire_exclusive` liefert `False`), analog dem projektweit
  etablierten Verhalten in `throttle_store.py:175-198` UND `forecast_budget.py:369-390`:
  `check_and_reserve` wirft dann **nicht**, sondern loggt eine WARNING und kehrt normal zurück
  (Versand wird zugelassen, aber NICHT gezählt). `release_reservation` verhält sich bei
  Lock-Timeout ebenso (WARNING, kein Rollback). Begründung, warum hier bewusst Zustellung vor
  Zähltreue geht: die Sperre wird nur für Millisekunden gehalten (reines JSON-Lesen/Schreiben,
  kein Netzwerk), ein Timeout ist also ein extremes Randereignis; und #1701 verlangt, dass Alarme
  jeden Kanal erreichen — ein Fail-Closed würde in genau diesem seltenen Fall einen Alarm
  sperren, obwohl das Kontingent real noch nicht erschöpft sein muss.

**🔴 Abweichung von der Phase-2-Analyse — Reserve-und-Rollback statt „Zählen erst nach
erfolgreichem Send" (technische Verfeinerung, keine Produktentscheidung, ORCHESTRATOR PRÜFEN):**
Die Analyse („Technical Approach" Punkt 3) sah vor, ausschließlich im `try` NACH erfolgreichem
`.send()` zu zählen. Das schützt nicht vor der Race-Bedingung aus AC-9: zwei gleichzeitige
Sendungen am Limit könnten beide die Prüfung bestehen und beide senden, wenn Prüfung und Zählung
getrennte Sperren wären. Diese Spec reserviert daher **atomar unter derselben Sperre wie die
Prüfung** und rollt bei einem tatsächlichen Transportfehler zurück — das Endergebnis ist
identisch (gescheiterte Versände zählen nicht, AC-7), aber die Reihenfolge ist „reservieren →
senden → bei Fehler zurückrollen" statt „senden → bei Erfolg zählen". Die Sperre wird dabei
NICHT über den Netzwerkaufruf von `.send()` gehalten (kurze Haltezeit, kein Risiko für die
2-Sekunden-Zeitgrenze aus `file_lock.py`). **Wer diese Spec freigibt, entscheidet damit auch
über diese Abweichung** — falls unerwünscht, muss die Alternative (Sperre über check+send+record
halten) explizit angefordert werden.

**Obergrenzen-Tabelle (`cap` je `kind`/`purpose`, aus `user_tier.py`-Limitwerten E3/E4):**

| Tier | Kanal | Limit | Reserve | `briefing`-Cap | `alert`-Cap | `reply`-Cap |
|---|---|---|---|---|---|---|
| free | sms | 0 | – | 0 | 0 | – |
| free | premium_sms | 0 | – | 0 | 0 | 0 |
| standard | sms | 10 | 2 | 8 | 10 | – |
| standard | premium_sms | 0 | – | 0 | 0 | 0 |
| premium | sms | 10 | 2 | 8 | 10 | – |
| premium | premium_sms | 15 | 3 | 12 | 15 | 18 (15 + Garmin-Zusatz 3) |

`free`/`standard`-Werte für `premium_sms` bzw. `free` für `sms` sind Verteidigung in der Tiefe —
`effective_channels` filtert diese Kanäle für diese Tiers bereits vor Erreichen des Gates über
die bestehenden Resolver (`alert_channels.py`, `compare_alert_channels.py`,
`trip_report_scheduler.py`), das neue Gate greift dort in der Praxis nicht, blockt aber
korrekt, falls ein Resolver-Pfad das je übersehen sollte.

**`src/services/user_tier.py` (MODIFY):** neue Funktionen `daily_sms_limit(user_id) -> int`,
`daily_premium_sms_limit(user_id) -> int`, sowie Modul-Konstanten `SMS_ALARM_RESERVE = 2`,
`PREMIUM_SMS_ALARM_RESERVE = 3`, `PREMIUM_SMS_REPLY_OVERSHOOT = 3`. Tier-Lookup identisch zum
bestehenden Muster in `sms_allowed`/`daily_alert_limit` (liest `tier` aus `user.json`, Default
`free`).

**`src/services/notification_service.py` (MODIFY), alle 12 Stellen (Tabelle oben):** Gate wird
PRO STELLE einzeln eingefügt — **keine Konsolidierung** der Sendeaufrufe auf gemeinsame
Hilfsmethoden (vier verschiedene bestehende Fehlersemantiken je Stelle bleiben unverändert).
Gate steht **vor** dem jeweiligen `.send()`-Aufruf, **vor** jedem `sent_channels.append(...)` UND
**vor** dem `if <sink> is not None: <sink>(...) else: <Output>(...).send(...)`-Verzweigungspunkt,
wo ein Sink existiert — der Sink-Zweig wird also ebenfalls gegatet und gezählt, nicht nur der
Direkt-`.send()`-Zweig. Betrifft konkret den Gate-vor-Append-Umbau an
`_dispatch_alert_message:1781/1795` UND `send_official_alert:1140/1156` (beide Kanäle, beide
Stellen, s. Sendestellen-Tabelle). Das `ChannelBlockedError` der Gate-Prüfung wird an JEDER der
12 Stellen lokal gefangen und darf nie propagieren (weder als Absturz noch versehentlich über
einen bestehenden `except OutputConfigError`-Zweig hinaus). Wo heute noch kein
`blocked_channels`-Eintrag für SMS existiert (Tabelle „NEU ergänzen"), wird dieser als Teil des
Gates neu hinzugefügt, analog zur bereits vorhandenen Premium-SMS-Behandlung direkt daneben.
Muster je Stelle (illustrativ, keine der 12 Stellen wörtlich identisch):

```python
try:
    sms_daily_limit.check_and_reserve(self._require_user(), "sms", "alert", now)
except ChannelBlockedError as e:
    blocked_channels["sms"] = str(e)
    _record_block_reason_code(blocked_reason_codes, "sms", e)
else:
    sent_channels.append("sms")
    try:
        SMSOutput(self._settings).send(subject=subject, body=sms_body)
    except Exception as e:
        sms_daily_limit.release_reservation(self._require_user(), "sms", now)
        _log_error("sms", e)
```

**`_dispatch_compare_official_sms` (Rückgabewert bei Sperre):** die Methode gibt bei Sperre
`False` zurück (analog dem Premium-Pendant), NACHDEM sie die neuen `blocked_channels`/
`blocked_reason_codes`-Parameter befüllt hat — der Aufrufer (1353-1358) appendet `sent_channels`
zwar weiterhin unbedingt, aber `failed_channels.append("sms")` löst dann korrekt aus, sodass
`delivered_channels` den Kanal ausschließt.

**`send_compare_report` (neue Ergebnisfelder):** die Methode legt lokal
`blocked_channels: dict[str, str] = {}` und `blocked_reason_codes: dict[str, str] = {}` an
(existieren dort heute gar nicht) und reicht beide in den `NotificationResult`-Return bei Zeile
1262 durch.

An `send_command_reply_premium_sms` (Zeile 1834, kein `NotificationResult`, `-> None`) gibt es
kein `blocked_channels`-Ziel — bei Sperre bleibt der Aufruf beobachtbar darüber, dass die (per
Monkeypatch der `PremiumSmsOutput`-Klasse beobachtete) Sendeklasse gar nicht aufgerufen wird
(Assert über Aufruf-Zähler des Aufzeichners, nicht über Log-Text).

`now = datetime.now(timezone.utc)` wird an jeder der 12 Stellen lokal gebildet — anders als
`alert_daily_limit.py`/`trip_alert.py` gibt es in `notification_service.py` heute keine
injizierte Uhr. AC-5 (UTC-Grenze) wird deshalb auf Modul-Ebene gegen `sms_daily_limit` direkt
mit injiziertem `now` geprüft, nicht durch einen Zeit-Mock über `NotificationService`.

**Test-Beobachtung ohne Mock-Theater:** Wo ein echter `sms_sink`-Parameter existiert
(`send_official_alert`, `send_compare_report`, `_dispatch_compare_official_sms`), nutzen Tests
diesen direkt. Wo kein Sink existiert (`send_trip_report`, `send_no_data_hint`,
`_dispatch_alert_message`, `send_command_reply_premium_sms`, und JEDE Premium-SMS-Stelle
generell — es gibt keinen `premium_sms_sink`-Parameter im gesamten Modul), nutzen Tests das
bereits etablierte Muster aus `tests/tdd/test_kanaltreue_adhoc_antwort.py:136-184`:
`monkeypatch.setattr(notification_service, "SMSOutput"/"PremiumSmsOutput", <Aufzeichner-Klasse>)`
— eine echte Fake-Klasse, die reale Aufrufe entgegennimmt/aufzeichnet und für AC-7 gezielt eine
Exception werfen kann. Das ist kein `Mock()`/`patch()` im Sinne des Testverbots, sondern ein
etabliertes, bereits im Bestand verwendetes Test-Double.

**Reihenfolge gegenüber dem bestehenden Alarm-Frequenz-Limit (`alert_daily_limit.py`):** Dieses
Limit greift bereits VOR `notification_service.py` in `trip_alert.py`/`compare_alert.py` — ein
dort unterdrückter Alarm erreicht `NotificationService` gar nicht erst, das neue SMS-Gate sieht
ihn also nie. Beide Limits sind unabhängig und additiv, keines ersetzt das andere. E-Mail und
Telegram sind vom neuen SMS-Gate strukturell nie betroffen (#1701) — das Gate existiert nur an
den `SMSOutput`-/`PremiumSmsOutput`-Sendestellen.

**Einheit:** 1 `.send()`-Aufruf (bzw. 1 Sink-Aufruf) = 1 Zähleinheit (kein Client-seitiger Split
nach Nachrichtensegmenten in `seven_io_base.py:166-186`). Ob Seven.io je SMS-Segment separat
abrechnet, ist aus dem Repo nicht belegbar — offen vermerkt, keine Annahme getroffen.

## Expected Behavior

- **Input:** `user_id` (aus `self._require_user()` der jeweiligen `NotificationService`-Instanz),
  Kanal (`sms`/`premium_sms`), Kategorie (`briefing`/`alert`/`reply`), aktueller UTC-Zeitpunkt.
- **Output:** Versand wird ausgeführt, wenn der Tageswert des betroffenen Kanals unter der für
  Tier+Kategorie geltenden Obergrenze liegt; sonst wird NUR dieser eine Kanal für diesen einen
  Versand nicht ausgeführt (`ChannelBlockedError`, `reason_code="sms_daily_limit_exceeded"`,
  landet in `blocked_channels`/`blocked_reason_codes` und NICHT in `delivered_channels`, überall
  wo diese Felder existieren bzw. neu ergänzt werden). E-Mail/Telegram desselben Versands laufen
  unverändert.
- **Side effects:** Schreibt/aktualisiert `sms_daily_count.json` im Nutzer-Datenordner bei jeder
  Reservierung und jedem Rollback (außer bei Lock-Timeout, dort fail-open ohne Schreibzugriff).
  Keine proaktive Hinweis-Nachricht beim Erreichen der Obergrenze.

## Acceptance Criteria

- **AC-1:** Given ein Standard-Nutzer hat am aktuellen UTC-Kalendertag bereits 8 Trip-Briefing-SMS erhalten / When ein 9. Briefing für denselben Nutzer ausgelöst wird / Then wird die SMS dieses Briefings nicht versendet (`blocked_channels["sms"]` mit `reason_code="sms_daily_limit_exceeded"`), während E-Mail und Telegram desselben Briefings unverändert zugestellt werden.
  - Test: `sms_daily_count.json` mit `{"date": <heutiges UTC-Datum>, "sms": 8, "premium_sms": 0}` vorseeden (eigene, eindeutige `user_id`, s. Test-Isolation unten). Echten `send_trip_report`-Lauf ausführen, dabei `EmailOutput`/`SMSOutput`/`TelegramOutput` im `notification_service`-Modul per `monkeypatch.setattr` durch Aufzeichner-Klassen ersetzen (Muster `test_kanaltreue_adhoc_antwort.py:136-184`, kein Sink-Parameter an dieser Methode). Assert über den zurückgegebenen `NotificationResult` (`sms` in `blocked_channels`, Email-/Telegram-Aufzeichner haben je einen Eintrag, SMS-Aufzeichner NICHT aufgerufen) und unverändertem Zählerstand `sms=8` in der Datei danach.

- **AC-2:** Given ein Standard-Nutzer hat am aktuellen UTC-Kalendertag bereits 8 Briefing-SMS verbraucht (Reserve für Alarme noch offen) / When zwei Alarm-SMS für denselben Nutzer nacheinander ausgelöst werden / Then gehen die 9. und 10. SMS noch heraus, eine 11. wird gesperrt.
  - Test: Zählerdatei mit `sms=8` vorseeden, zwei echte `send_official_alert`-Läufe über den vorhandenen `sms_sink`-Parameter (Zeile 1139-1149) ausführen (erwartet: `sms_sink` beide Male aufgerufen, Zähler auf 9 dann 10), danach ein dritter Lauf (erwartet: `blocked_channels["sms"]`, `sms_sink` NICHT aufgerufen, `"sms" not in NotificationResult.delivered_channels`, Zähler bleibt bei 10) — Assert jeweils nach jedem Lauf. Die dritte Assertion (`delivered_channels`) deckt gezielt ab, dass der Append-vor-`try`-Umbau an dieser Stelle (1140) korrekt mit `failed_channels`/`blocked_channels` zusammenspielt.

- **AC-3:** Given ein Premium-Nutzer hat sein volles SMS-Tageskontingent (10) ausgeschöpft / When im selben Zeitraum eine Premium-SMS (Briefing) ausgelöst wird / Then wird die Premium-SMS trotzdem versendet, weil beide Kanäle getrennte Zähler führen — und umgekehrt blockiert ein ausgeschöpftes Premium-SMS-Kontingent keine normale SMS.
  - Test: Zählerdatei mit `sms=10, premium_sms=0` vorseeden, echten `send_trip_report`-Lauf mit `send_sms=True, send_premium_sms=True` ausführen, `SMSOutput`/`PremiumSmsOutput` per Aufzeichner-Monkeypatch beobachten; Assert: `sms` in `blocked_channels`, Premium-Aufzeichner wurde aufgerufen. Gegenprobe mit vertauschten Werten (`sms=0, premium_sms=15`) zeigt das umgekehrte Ergebnis.

- **AC-4:** Given ein Premium-Nutzer hat sein Premium-SMS-Tageskontingent von 15 vollständig ausgeschöpft / When er auf eine eingehende Kommando-SMS antwortet (Garmin, `send_command_reply_premium_sms`) und das bis zu viermal am selben UTC-Tag tut / Then gehen die Antworten 16, 17 und 18 noch heraus, die 19. Antwort wird nicht mehr gesendet.
  - Test: Zählerdatei mit `premium_sms=15` vorseeden, vier echte `send_command_reply_premium_sms`-Aufrufe ausführen, `PremiumSmsOutput` per Aufzeichner-Monkeypatch beobachten (kein Sink an dieser Methode); Assert ausschließlich über die Aufruf-Trefferzahl des Aufzeichners (3, nicht 4) — kein Log-String-Assert, der vierte Aufruf loggt zwar, das ist aber nicht der Verhaltensnachweis.

- **AC-5:** Given der SMS-Zähler eines Nutzers steht am 23:59 UTC bereits auf dem vollen Tageswert / When ein Versand um 00:00 UTC desselben Kalendertagwechsels ausgelöst wird (= 02:00 MESZ / 01:00 MEZ, unabhängig von der Ortszeit des Trips) / Then ist das volle Tageskontingent wieder verfügbar.
  - Test: Direkt gegen `sms_daily_limit.check_and_reserve`/`release_reservation` mit injiziertem `now` (`2026-09-24 23:59:00+00:00` dann `2026-09-25 00:00:00+00:00`) — kein Umweg über `NotificationService` (dort keine injizierte Uhr, s. Implementation Details); Assert, dass die zweite Prüfung trotz zuvor erschöpftem Kontingent erfolgreich reserviert und der Zählerstand für den neuen Tag bei 1 startet.

- **AC-6:** Given zwei verschiedene Nutzer (`user_id` A und B) haben unabhängige Zählerdateien, Nutzer A hat sein Tageskontingent ausgeschöpft / When Nutzer B im selben Zeitraum eine SMS versendet / Then bleibt Nutzer B davon vollständig unberührt (eigener Zählerstand, eigene Obergrenze).
  - Test: Zwei `NotificationService`-Instanzen mit unterschiedlichen, eindeutigen `user_id`, A mit vorgeseedetem `sms=10`, B ohne Vorbelegung; echte `send_official_alert`-Läufe über den `sms_sink`-Parameter für beide; Assert, dass B's `sms_sink` aufgerufen wird und B's Zählerdatei unabhängig von A's Datei fortgeschrieben wird (Mandantentrennung, zwei physisch getrennte Dateien unter `get_data_dir`).

- **AC-7:** Given eine SMS besteht die Tageslimit-Prüfung, der eigentliche Transportaufruf schlägt danach fehl (Aufzeichner-Klasse, deren `.send()` gezielt eine Exception wirft) / When der Versand endet / Then wird die Reservierung zurückgerollt — der Zählerstand ist identisch zum Stand vor diesem Versuch, während ein gesperrter (nie reservierter) Versand den Zähler ebenfalls unverändert lässt.
  - Test: `SMSOutput` per Monkeypatch durch eine Aufzeichner-Klasse ersetzen, deren `.send()` eine `RuntimeError` wirft (kein `patch()`, echte Fake-Klasse mit echtem Aufruf); `send_trip_report` bei bekanntem Ausgangszählerstand ausführen; Assert Zählerstand vor/nach Lauf identisch. Zweiter Lauf mit ausgeschöpftem Kontingent (gesperrt statt fehlgeschlagen) zeigt denselben unveränderten Zählerstand.

- **AC-8:** Given das bestehende Alarm-Frequenz-Limit (`alert_daily_limit.py`) hat das Tageskontingent eines Free-/Standard-Nutzers bereits erschöpft, BEVOR `NotificationService` überhaupt erreicht wird / When derselbe Alarm-Auslöser wie in den bestehenden Regressionstests eintritt / Then bleibt dieses Verhalten unverändert: kein SMS-Versand, und `sms_daily_count.json` bleibt unverändert oder unangelegt, weil `NotificationService` in diesem Fall gar nicht aufgerufen wird.
  - Test: NEUER Test (eigene `user_id`) seedet `alert_daily_count.json` am Limit, führt den echten Alarm-Lauf (`trip_alert.check_and_send_alerts`/`check_radar_alerts`) aus und prüft zusätzlich zum ausbleibenden Versand, dass `sms_daily_count.json` danach identisch zum Vorzustand ist (unverändert oder weiterhin nicht vorhanden). Zusätzlich vollständiger Regressionslauf ohne neue Fehlschläge: `tests/tdd/test_issue_1070_daily_alert_limit.py`, `test_issue_1069_tier_channel_gating.py`, `test_ruhezeit_und_zaehler_folgen_der_ortszone.py`, `test_alarm_szenario_tagesbezug_zeitzone.py`, `test_alarm_szenario_mandantentrennung.py`, `test_compare_alert_channel_delivery.py`, `test_compare_dispatch_channel_fanout.py`, `test_914_slice4_alert_sms_dispatch.py`, `test_kanaltreue_adhoc_antwort.py`.

- **AC-9:** Given zwei gleichzeitige Sendeversuche für denselben Nutzer und Kanal treffen ein, während der Tageszähler genau 1 unter der Obergrenze steht / When beide (quasi-)gleichzeitig `check_and_reserve` aufrufen / Then reserviert genau einer der beiden erfolgreich, der andere wird gesperrt — der Zählerstand überschreitet die Obergrenze nie.
  - Test: Zwei Threads/Prozesse rufen `check_and_reserve` für dieselbe `user_id`/`kind` bei Ausgangswert `cap - 1` echt parallel auf (reales `fcntl`-Locking über `file_lock.acquire_exclusive` auf der Sidecar-Lockdatei, kein Mock); Assert, dass genau einer eine `ChannelBlockedError` erhält und der Endstand exakt `cap` ist, nie `cap + 1`.

- **AC-10:** Given ein Nutzer, dessen Tageszähler für den jeweiligen Kanal (`sms` bzw. `premium_sms`) bereits voll ist / When über JEDE der übrigen Sendestellen ein Versand ausgelöst wird — Radar-Alarm (`send_radar_alert` → `_dispatch_alert_message`, SMS und Premium-SMS), Ortsvergleichs-Briefing (`send_compare_report`, SMS), Ortsvergleichs-Amtswarnung (`send_multi_location_official_alert`, SMS und Premium-SMS) sowie der Keine-Daten-Hinweis (`send_no_data_hint`, SMS und Premium-SMS) / Then geht an keiner dieser Stellen eine SMS bzw. Premium-SMS hinaus, der Kanal steht mit `sms_daily_limit_exceeded` in `blocked_channels` des Ergebnisses (bzw. beim Ortsvergleichs-Helfer als nicht zugestellt), und E-Mail/Telegram desselben Versands gehen trotzdem raus.
  - Test: Ein parametrisierter Test je Sendestelle (eigene `user_id` je Fall, Zählerdatei am Limit vorbelegt) löst den echten öffentlichen Einstiegspunkt aus und prüft über die Aufzeichner der Transportklassen, dass kein SMS-/Premium-SMS-Aufruf erfolgt, dass der Sperrgrund im Ergebnis steht und dass E-Mail/Telegram aufgezeichnet wurden. Zusammen mit AC-1/AC-2/AC-4 ist damit jede der 12 Sendestellen aus der Tabelle „Sendestellen" durch mindestens einen Test an der Stelle bewacht, an der die Sperre wirkt.

## Known Limitations

- **S4b (Sichtbarkeit im Konto) ist eigener Folge-Workflow.** `GET /api/_internal/sms/daily-usage`,
  Go-Profil-Anbindung und `/account`-Anzeige sind hier NICHT enthalten. Bis dahin ist der
  Zählerstand nur über Log/`blocked_channels` sichtbar, nicht für den Nutzer selbst im UI.
- **#2412 und #2153 bleiben nach diesem Deploy offen** — S4a schließt keines der beiden Issues,
  siehe Abschnitt „Scope: NUR S4a" oben.
- **Nebenbefund, NICHT Teil von S4a:** In `_dispatch_alert_message`
  (`notification_service.py:1781/1795`) UND in `send_official_alert` (`:1140/1156`) steht
  `sent_channels.append(...)` bei BEIDEN Kanälen vor dem `try` — ein technisch gescheiterter
  (nicht durch das neue Limit gesperrter) Versand gilt dort weiterhin als „gesendet" im Sinne von
  `sent_channels`. Das neue Gate greift davor und verhindert nur, dass eine SPERRE fälschlich als
  gesendet erscheint (über den zusätzlichen `failed_channels`/`blocked_channels`-Eintrag); das
  allgemeinere Problem (ein echter Transportfehler zählt weiterhin als `sent_channels`-Eintrag,
  nur `delivered_channels` filtert ihn über `failed_channels` heraus) bleibt unverändert bestehen
  und ist Zeile in #1199, kein eigenes Issue.
- **Reply-Reserve teilt sich den Premium-SMS-Zähler.** Es gibt keinen separaten Zähler für
  `purpose="reply"` — Garmin-Antworten füllen bis zu 3 zusätzliche Einheiten über das
  Premium-SMS-Grundlimit hinaus, können dabei aber faktisch auch die Alarm-Reserve mitbelegen,
  wenn viele Antworten UND viele Alarme am selben Tag zusammentreffen. Bewusste Vereinfachung
  nach PO-Entscheidung E4, keine eigenständige Reply-Quote.
- **`release_reservation` ist an der Tageswechsel-Grenze konservativ.** Fällt der Tageswechsel
  zwischen Reservierung und Fehlschlag-Meldung, wird NICHT dekrementiert (No-op statt falscher
  Rückbuchung in den neuen Tag) und der Zähler geht nie unter 0. Ein Absturz zwischen Reservieren
  und Senden lässt im ungünstigsten Fall eine Einheit zu viel gezählt — bewusst konservativ
  (fehlerhaftes Überzählen ist sicherer als eine mögliche Unterzählung, die das Limit unterläuft).
- **Fail-Open bei Lock-Timeout** (analog `throttle_store.py`/`forecast_budget.py`, s.
  Implementation Details für die Begründung): Ein Timeout beim Sperrenerwerb (2s, `file_lock.py`)
  lässt den Versand ungezählt durch, statt ihn zu sperren oder die Anfrage abzubrechen. Seltener
  Randfall (ein Nutzer sendet praktisch nie in hoher Nebenläufigkeit), aber theoretisch ein
  ungezählter Versand über das Limit hinaus.
- **Einheit ungeklärt bei Mehrfach-Segmenten:** 1 `.send()`-Aufruf zählt als 1 Einheit, unabhängig
  davon, ob Seven.io eine lange SMS intern in mehrere Segmente aufteilt und dafür mehrfach
  abrechnet. Aus dem Repo nicht belegbar, keine Korrektur in dieser Scheibe.
- **Keine proaktive Hinweis-Nachricht beim Erreichen der Obergrenze** — bewusst nach der
  Analyse-Entscheidung (Kosten-/Schleifenrisiko, „nur Daten"-Prinzip).
- **Verteidigung in der Tiefe für free/standard-Premium-SMS:** Die Obergrenzen-Tabelle setzt für
  Tiers ohne Kanalzugriff `0`, obwohl die bestehenden Resolver diese Kanäle bereits vorher aus
  `effective_channels` filtern — das Gate greift dort im Normalfall nie, ist aber als zweite
  Sicherung vorhanden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Zusatz zu ADR-0044, kein neues ADR)
- **Rationale:** Der neue Zähler folgt exakt dem bereits etablierten Read-Modify-Write-Muster für
  Nutzer-State (`throttle_store.py`/`forecast_budget.py`: Sidecar-Lock + atomares `os.replace`,
  Fail-Open bei Lock-Timeout) — einziger Unterschied ist ein zweiter Zähler-Topf im selben
  Datenfile und eine feste UTC-Taktung statt einer zonenbezogenen. Es entsteht kein neuer
  Architektur-Layer. **ADR-0044** („Heute"/„morgen" folgen der Ortszeit der Tour) bekommt einen
  additiven Zusatz „Nicht betroffen: der SMS-/Premium-SMS-Kostendeckel" nach der bestehenden
  Nicht-betroffen-Passage — dieser Zähler ist eine reine Kosten-Referenzgröße pro Nutzerkonto,
  kein wetter- oder tourfachlicher Kalendertag, analog zur bereits dokumentierten Ausnahme
  „Dauern" (Zeile 36). **ADR-0049** (Premium-SMS als 4. Kanal, Punkt 5 Tier-Gate) bleibt
  unberührt — dieser Deckel ist ein zusätzliches Mengen-Gate, kein Ersatz für das bestehende
  Tier-Gate. **ADR-0031** (Python schreibt Throttle-Dateien unter `data/users/<id>/`, Spannung zur
  dort beschriebenen „Go ist einziger Schreiber"-Kontextaussage) — diese Spannung besteht bereits
  seit `alert_daily_limit.py`/`throttle_store.py` und wird durch diese Spec nicht verschärft, nur
  ein weiteres Beispiel desselben etablierten Musters hinzugefügt.

## Test Plan

- **GWT-1:** Given ein Standard-Nutzer hat sein Briefing-Kontingent (8 von 10, Reserve 2) für den
  aktuellen UTC-Tag ausgeschöpft / When ein weiteres Briefing ausgelöst wird / Then bleibt die
  SMS dieses Briefings aus, während E-Mail/Telegram unverändert zugestellt werden (AC-1).
- **GWT-2:** Given zwei Sendeversuche desselben Nutzers und Kanals treffen exakt bei `cap - 1`
  gleichzeitig ein / When beide parallel die Tageslimit-Prüfung durchlaufen / Then reserviert
  genau einer erfolgreich, der Zählerstand überschreitet `cap` nie (AC-9).
- **Test-Isolation (PFLICHT für jeden neuen Test):** `tests/conftest.py:186-209` biegt
  `_DATA_ROOT` nur SESSIONWEIT um — jeder Test dieser Spec (inkl. des neuen AC-8-Tests) verwendet
  eine eigene, eindeutige `user_id`, sonst leaken vorgeseedete Zählerdateien zwischen Tests.

| AC | Testfokus |
|---|---|
| AC-1 | Standard-Nutzer, Briefing-SMS 9 blockiert, E-Mail/Telegram unberührt |
| AC-2 | Alarm-Reserve: 9./10. Alarm-SMS gehen raus, 11. blockiert, `delivered_channels` korrekt |
| AC-3 | Getrennte Zähler `sms`/`premium_sms`, beide Richtungen |
| AC-4 | Garmin-Reply-Zusatzmenge (3 über Premium-SMS-Grundlimit), Assert über Aufzeichner-Zähler |
| AC-5 | UTC-Mitternachtsreset, modulnahe Zeit-Injektion |
| AC-6 | Mandantentrennung zwischen zwei `user_id` |
| AC-7 | Rollback bei Transportfehler, unveränderter Zähler bei Sperre |
| AC-8 | Bestehendes Alarm-Frequenz-Limit bleibt unverändert wirksam (Regressionslauf + neuer Verhaltenstest) |
| AC-9 | Nebenläufigkeit zweier Sendeversuche am Limit |
| AC-10 | Sperre an allen übrigen Sendestellen (Radar, Ortsvergleich-Briefing, Ortsvergleich-Amtswarnung, Keine-Daten-Hinweis) |

## Changelog

- 2026-09-24: Initial spec created (S4a, Issue #2412, Sammel-Issue #2153, Epic #2138)
- 2026-09-24: AC-10 ergänzt — jede der 12 Sendestellen durch einen Test bewacht (PO-Briefing-Fund 3)
