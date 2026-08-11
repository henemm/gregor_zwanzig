---
entity_id: feat_1701_alarm_premium_sms
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [sms, premium, garmin, alarm, ortsvergleich, kanal-schwelle, alert-log]
---

<!-- Issue #1701 (Scheibe S2b von #1676) -- Premium-SMS wird vierter Kanal im
     Alarm- UND Ortsvergleich-Pfad. Vorgaenger: S2a (Trip-Briefing, gemergt,
     ADR-0049). Nachfolger: S2c (#1702, Kostenstelle), S3 (Oberflaeche). -->

# Premium-SMS als vierter Alarm-/Vergleichs-Kanal — S2b

## Approval

- [ ] Approved

## Purpose

Premium-SMS (Garmin inReach) ist seit S2a ein vollwertiger vierter Versandkanal — aber
ausschließlich für das planmäßige Trip-Briefing. Diese Scheibe zieht ihn durch den
**Alarm-Pfad** (Trip-Änderungs-/Regenradar-Alarme, amtliche Trip-Warnungen) und den
**Ortsvergleich-Pfad** (dieselben drei Alarmarten für gespeicherte Vergleichs-Orte) nach —
inklusive der zugehörigen Kanal-Schwelle (ADR-0046) und der maschinenlesbaren Sperrgrund-
Buchung im Alarm-Protokoll. Ohne diese Scheibe erreicht ein Nutzer, der auf einer Hütte
ausschließlich per Satellit erreichbar ist (Karnischer Höhenweg, PO-Fall ab 20.08.), zwar
weiterhin sein Briefing per Premium-SMS — aber **keinen einzigen Gewitteralarm**, weil jeder
der drei Alarmpfade den Kanal heute strukturell nicht kennt.

## Abgrenzung (nicht in dieser Scheibe)

- **S2a — Trip-Briefing (#1676, gemergt):** liefert den Kanal selbst
  (`PremiumSmsOutput`, Tier-Gate, Fail-Closed, ADR-0049) und die geteilte Infrastruktur
  (`NotificationResult.blocked_channels`/`blocked_reason_codes`, `_record_block_reason_code`),
  auf der diese Scheibe additiv aufbaut. Nicht neu zu bauen.
- **S2c — Kostenstelle (#1702):** Kosten-/Kontingent-/Versandzähler je Kanal existieren im
  Bestand nirgends (nur das Tier-Tageslimit für Alarme, `user_tier.py:17-31`). Eigenes
  Feature ohne Vorbild, nicht Teil dieser Scheibe.
- **S3 — Oberfläche:** die Kanal-Auswahl `alert_channels.premium_sms` bzw.
  `send_premium_sms` im Ortsvergleich-Preset wird in dieser Scheibe ausschließlich über die
  API setzbar (Go-Feld, Merge, Persistenz) — noch kein UI-Kontrollelement. Auch die
  Premium-SMS-Kanal-Schwelle bleibt ohne Bedienelement.
- **#1533 — Generalprobe auf dem Gerät:** dass ein Alarm tatsächlich am Garmin-Gerät
  ankommt, ist mit den Mitteln dieser Scheibe strukturell nicht beweisbar (gleiche
  Sandbox-Einschränkung wie in S2a, siehe „Nachweisgrenzen").

## Source

> **Schicht-Hinweis:** Python-Core (`src/services/`) für den Versand-/Protokoll-Teil,
> Go-API (`internal/model/`, `internal/handler/`) für Persistenz/Merge des vierten Kanal-Flags.

- **File:** `src/services/alert_log.py` (MODIFY, ~15 LoC) — `_ALL_CHANNELS` (`:59`) um
  `"premium_sms"` erweitert; `append_entry()` (`:130-221`) und `_channels_not_sent()`
  (`:113-132`) bekommen einen neuen optionalen Parameter `blocked_reason_codes`, der für
  einen Kanal mit Eintrag den generischen `REASON_DELIVERY_FAILED` durch die spezifische
  Kennung ersetzt (D5).
- **File:** `src/services/trip_alert.py` (MODIFY, ~20 LoC) —
  `_effective_alert_channels()` (`:1461-1513`), zwei Stellen: die scharfe
  `alert_channels`-Ableitung (`:1492-1494`, Tupel `("email","telegram","sms")` → `+ "premium_sms"`)
  und `_briefing_channels()` (`:1515-1527`, neuer `if getattr(config, "send_premium_sms", False)`-Zweig).
  `_radar_effective_channels()` (`:825-846`) bekommt denselben vierten Zweig, gegated über
  `premium_sms_allowed(self._user_id)` (NICHT `sms_allowed`, D2). Import
  `from services.user_tier import sms_allowed, premium_sms_allowed` (`:33`).
- **File:** `src/services/compare_alert_channels.py` (MODIFY, ~6 LoC) —
  `effective_compare_channels()` (`:28-36`) bekommt einen vierten Zweig
  `if preset.get("send_premium_sms") and premium_sms_allowed(user_id): channels.add("premium_sms")`
  — bewusst OHNE `settings.can_send_premium_sms()` (D2: diese Methode wurde in S2a
  absichtlich entfernt, s.u.).
- **File:** `src/services/notification_service.py` (MODIFY, ~90 LoC) — vier separate
  Stellen, siehe „Implementation Details":
  - `_dispatch_alert_message()` (`:1200-1417`): vierter Kanal-Zweig nach dem
    SMS-Zweig (`:1405-1411`), `_log_error()` (`:1299-1305`) Label-Dict gehärtet.
  - `send_official_alert()` (`:794-899`): vierter Kanal-Zweig nach dem SMS-Zweig
    (`:881-894`).
  - `send_compare_official_alert()` (`:995-1081`) + neue Hilfsfunktion
    `_dispatch_compare_official_premium_sms()` (Vorbild `_dispatch_compare_official_sms`,
    `:1140-1157`).
  - Alle sechs `alert_log.append_entry(...)`-Aufrufstellen (s.u.) reichen zusätzlich
    `blocked_reason_codes=result.blocked_reason_codes` durch.
- **File:** `src/services/trip_alert.py` (dieselbe Datei, bereits oben gezählt) — zwei
  `alert_log.append_entry(...)`-Aufrufstellen (`:316`, `:1097`, `:1404` laut Messung des
  Kontextdokuments — drei, nicht zwei; korrigiert) bekommen `blocked_reason_codes=`.
- **File:** `src/services/compare_alert.py` (MODIFY, 1 Zeile) — `append_entry`-Aufruf
  (`:256`) bekommt `blocked_reason_codes=`.
- **File:** `src/services/compare_radar_alert.py` (MODIFY, 1 Zeile) — `append_entry`-Aufruf
  (`:202`) bekommt `blocked_reason_codes=`.
- **File:** `src/services/compare_official_alert.py` (MODIFY, 1 Zeile) — `append_entry`-Aufruf
  (`:171`) bekommt `blocked_reason_codes=`.
- **File:** `internal/model/trip.go` (MODIFY, ~20 LoC) —
  `AlertChannelsConfig` (`:187-191`) von `bool`-Feldern auf `*bool` umgestellt (Email,
  Telegram, Sms) **plus** neues Feld `PremiumSms *bool`; Docstring-Prämisse „All-or-nothing"
  (`:185-186`) entfällt (D3). `AlertChannelThresholdsConfig` (`:202-206`) bekommt
  `PremiumSms *string` als viertes Geschwisterfeld (ADR-0046-Pflicht, D6) — dieser Typ ist
  identisch für Trip und Ortsvergleich, also automatisch auf beiden Seiten wirksam.
- **File:** `internal/handler/trip.go` (MODIFY, ~20 LoC) — der bisherige
  Ganzobjekt-Ersatz `if req.AlertChannels != nil { existing.AlertChannels = req.AlertChannels }`
  (`:367-369`) wird durch Feld-Level-Merge ersetzt (Vorbild `AlertChannelThresholds`,
  `:375-386`, D3). Der bestehende Threshold-Merge-Block (`:375-386`) bekommt einen vierten
  `if req.AlertChannelThresholds.PremiumSms == nil ...`-Zweig.
- **File:** `internal/model/compare_preset.go` (MODIFY, ~4 LoC) — neues Feld
  `SendPremiumSms *bool` (Vorbild `SendTelegram`/`SendSms`, `:91-92`).
- **File:** `internal/handler/compare_preset.go` (MODIFY, ~8 LoC) — Merge-Block
  `:407-411` bekommt einen dritten `if updated.SendPremiumSms == nil { ... }`-Zweig;
  der Threshold-Merge-Block (`:419-429`) bekommt den vierten `PremiumSms`-Zweig
  (identisches Muster wie im Trip-Handler).
- **File:** `docs/reference/api_contract.md` (MODIFY, Doku, zählt nicht zum LoC-Budget) —
  `AlertChannelsConfig`/`AlertChannelThresholdsConfig`-Codeblöcke (`:740-770`) und die
  zugehörige Prosa (`:773-807`) auf vier Kanäle nachziehen; „all-or-nothing" für
  `AlertChannelsConfig` entfällt.
- **File:** `tests/test_success_status_guard.py` (MODIFY, ~10 LoC) — die
  indexbasierte Ratsche für `send_official_alert` (`:1547-1554`, `:1792`) und
  `_dispatch_alert_message` (`:1579-1586`, `:1794`) wird von **3** auf **4** angehoben
  (D7), plus ein Nachzug-Eintrag für die neue Fundstelle
  `send_compare_official_alert::3` (falls der Scanner sie dort listet — am Bestand
  nachzumessen, s. „Known Limitations").
- **File:** `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (MODIFY, Doku) —
  Pflicht-Nachzug der neuen Ratschen-Zahlen (dort wörtlich verlangt).
- **File:** `tests/unit/test_alert_channel_premium_sms.py` (CREATE, ~180 LoC) —
  echter lokaler HTTP-Stub, Trip-Änderungs-/Radar-Alarm + amtlicher Trip-Alarm über
  Premium-SMS, Tier-Gate, Totalausfall-Schutz.
- **File:** `tests/unit/test_compare_alert_premium_sms.py` (CREATE, ~120 LoC) —
  dieselben drei Alarmarten für den Ortsvergleich.
- **File:** `tests/unit/test_alert_log_premium_sms_channel.py` (CREATE, ~80 LoC) —
  `_ALL_CHANNELS`, `blocked_reason_codes`-Weiterreichung, kein stilles Loch im Protokoll.
- **File:** `tests/unit/test_alert_channel_threshold_premium_sms.py` (CREATE, ~60 LoC) —
  Kanal-Schwelle greift für Premium-SMS wie für die drei Bestandskanäle.
- **File:** `internal/handler/trip_alert_channels_test.go` (MODIFY, ~40 LoC) —
  Feld-Level-Merge-Fälle für `PremiumSms`, Bestandsdaten-Erhalt bei fehlendem vierten Feld.
- **File:** `internal/handler/trip_alert_channel_thresholds_test.go` (MODIFY, ~15 LoC) —
  vierter Schwellenwert-Fall.
- **File:** `internal/handler/compare_preset_official_alerts_test.go` (MODIFY, ~15 LoC) —
  `SendPremiumSms`-Merge-Fall.
- **File:** `internal/handler/compare_preset_alert_channel_thresholds_test.go`
  (MODIFY, ~15 LoC) — vierter Schwellenwert-Fall für den Ortsvergleich.

## Estimated Scope

- **LoC (Produktivcode, Python + Go):** ≈ +180 (alert_log +15, trip_alert +20,
  compare_alert_channels +6, notification_service +90, sechs `append_entry`-Aufrufstellen
  +6, Go-Modell +24, Go-Handler +28, Ratsche +10 — Doku zählt nicht mit).
- **LoC (Tests):** geschätzt ≈ +450 (vier neue Python-Testdateien ≈ 440, vier Go-Test-
  Ergänzungen ≈ 85 — **konservativ geschätzt**, S2a lag beim tatsächlichen RED-Stand um mehr
  als das Doppelte über der Schätzung, weil echte HTTP-Stub-Fixtures und Kantenfälle teurer
  sind als vermutet).
- **Gesamt erwartet:** ≈ +630, realistisch eher **800–1200** nach S2a-Erfahrung.
  **Das im Workflow gesetzte LoC-Budget von 400 reicht nicht** — ein Override auf
  mindestens **1200** ist vor der Implementierung einzuholen, nicht erst wenn das Limit
  reißt. Begründung: diese Scheibe berührt DREI unabhängige Versand-Dispatcher in
  `notification_service.py` (nicht einen wie in S2a), zwei Go-Structs mit Merge-Pflicht
  statt keinem, und die Ratschen-Nachzugpflicht.
- **Files:** 4 CREATE (Tests) + 20 MODIFY (13 Python/Doku, 7 Go/Go-Tests).
- **Effort:** high.
- **Risiko:** MEDIUM-HOCH. Kein bestehendes Verhalten der drei etablierten Kanäle
  ändert sich (rein additiv), aber die Zahl der Ansatzpunkte ist hoch — ein vergessener
  Ansatzpunkt erzeugt keinen Testfehler, sondern ein stilles Loch (Präzedenzfall:
  `_ALL_CHANNELS` in `alert_log.py` liefert bei Vergessen einfach kein Protokoll-Feld für
  `premium_sms`, kein Crash).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | Vorgänger-Spec | liefert `PremiumSmsOutput`, `premium_sms_allowed()`, `NotificationResult.blocked_channels`/`blocked_reason_codes`, `_record_block_reason_code()` — alles wiederverwendet, nichts neu gebaut |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | ADR | legt den Kanalnamen bereits fest; diese Scheibe braucht **kein neues ADR** |
| `docs/adr/0046-alarm-kanal-schwelle.md` | ADR | verpflichtet: jede neue Stelle, die ein Kanal-Set auflöst, muss die Kanal-Schwelle anwenden — hier eingelöst (AC-8) |
| `src/services/user_tier.py::premium_sms_allowed` | module | Tier-Gate, NICHT `sms_allowed` (lässt `standard` durch) |
| `src/services/alert_channel_threshold.py::split_by_threshold` | module | kanal-agnostisch (Default `LOW`), kein Code-Eingriff nötig — nur das Go-Feld zum Setzen fehlt |
| `internal/model/trip.go::AlertChannelThresholdsConfig` | Vorbild | Pointer-Feld-Merge-Muster, das `AlertChannelsConfig` jetzt übernimmt (D3) |
| `internal/handler/compare_preset.go` Merge-Block `:407-429` | Vorbild | identisches Muster bereits für Telegram/Sms/Thresholds vorhanden |
| `tests/test_success_status_guard.py` | Wächter | Erfolgs-Ratsche, MUSS angehoben werden (D7), NICHT umgangen |

## Implementation Details

### D1 — Fünf plus zwei: die tatsächliche Zahl der Enumerationen

Der ursprüngliche Befund nannte fünf hart verdrahtete Kanal-Aufzählungen. Beim Nachmessen für
diese Spec kamen zwei weitere hinzu, die dieselbe Struktur haben, aber nicht in der
ursprünglichen Liste standen:

1. `alert_log.py:59` `_ALL_CHANNELS`
2. `trip_alert.py:1492-1494` (`_effective_alert_channels`, scharfes Set)
3. `trip_alert.py:1515-1527` (`_briefing_channels`, Vererbung)
4. `trip_alert.py:825-846` (`_radar_effective_channels`, bewusst getrennt seit #1467 S3)
5. `compare_alert_channels.py:28-36` (`effective_compare_channels`)
6. **NEU gemessen:** `notification_service.py:794-899` (`send_official_alert`, drei
   `if "<kanal>" in effective_channels`-Zweige)
7. **NEU gemessen:** `notification_service.py:995-1081` +
   `_dispatch_compare_official_{email,telegram,sms}` (`:1083-1157`) — der
   Ortsvergleich-Pendant zu (6), strukturell identisch, aber eine eigene Funktionsfamilie.

`_dispatch_alert_message()` (`:1200-1417`) ist KEINE eigene Enumeration im selben Sinn wie
(6)/(7) — sie liest `effective_channels` bereits als aufgelöstes Set (aus (2)/(3)/(4)/(5))
und muss nur um einen vierten `if "premium_sms" in effective_channels:`-Zweig ergänzt werden.
Trotzdem ist sie eine eigene Ansatzstelle, weil sie den Versand selbst auslöst
(`PremiumSmsOutput(...).send(...)`), nicht nur das Set berechnet.

### D2 — Kein `settings.can_send_premium_sms()` im Alarm-Pfad

S2a hat genau diese Methode nach einem Adversary-Fund (F003) **entfernt**: eine
vorgeschaltete Bereitschaftsfrage im Sendezweig hätte die Fail-Closed-Prüfung in
`PremiumSmsOutput._resolve_recipient()` *abgeschirmt* — bei einem Bug in der Vorprüfung
wäre die eigentliche Sperre nie erreicht worden, und der Test dafür wäre grün geblieben.
Diese Scheibe **darf diese Methode nicht wieder einführen**, auch nicht implizit über eine
andere Bereitschaftsfrage mit ähnlichem Namen. Folge: `effective_compare_channels()` und
`_radar_effective_channels()` gaten Premium-SMS ausschließlich über Opt-in (`preset.get(...)`
bzw. `config.send_premium_sms`) und Tier (`premium_sms_allowed`) — genau wie die drei anderen
Kanäle NICHT über `can_send_sms()`/`can_send_telegram()` im Alarm-Pfad geprüft werden
(diese Methoden gaten dort schon heute nur die technische Konfiguration, nicht die
Empfänger-Frische — bei Premium-SMS gibt es aber gar keine technische Konfiguration zu
prüfen, nur die Rückadresse, und die prüft ausschließlich der Kanal selbst).

### D3 — Go-Merge: das vierte Feld darf kein fünftes Datenverlust-Muster werden

`AlertChannelsConfig` trägt heute die explizite Prämisse „All-or-nothing: alle drei Felder
werden vom Client immer explizit gesendet". Diese Prämisse ist mit einem vierten Feld, das
die Oberfläche (S3) noch gar nicht kennt, sofort falsch: ein PUT eines alten Frontend-Builds
schickt weiterhin nur drei Felder, Go dekodiert das fehlende vierte als Zero-Value `false`,
und der bisherige Ganzobjekt-Ersatz (`existing.AlertChannels = req.AlertChannels`) würde
einen bereits aktivierten Premium-Alarmkanal bei **jedem** Speichern eines Trips über die
alte Oberfläche stillschweigend abschalten — ein Muster wie BUG-DATALOSS-GR221 (#102).

Lösung: `Email`/`Telegram`/`Sms`/`PremiumSms` werden `*bool`, und der Handler übernimmt das
Feld-Level-Merge-Muster, das für `AlertChannelThresholdsConfig` direkt daneben bereits
etabliert ist (`trip.go:202-206`, `handler/trip.go:375-386`): fehlt ein Feld im Body (`nil`),
bleibt der Bestandswert erhalten; ist es explizit gesetzt (auch `false`), gewinnt der neue
Wert. Damit verhält sich `AlertChannelsConfig` konsistent mit seinem direkten
Geschwisterfeld, statt zwei unterschiedliche Merge-Philosophien nebeneinander zu pflegen.

### D4 — Der Totalausfall-Fund: `_log_error()` stürzt heute ab

`notification_service.py:1301` — `label = {"email": "Email", "telegram": "Telegram",
"sms": "SMS"}[channel]` ist ein direkter Dict-Zugriff ohne Rückfall, in einem
Exception-Handler. Sobald `_dispatch_alert_message()` einen `"premium_sms"`-Zweig bekommt
und der Versand fehlschlägt, wirft dieser Zugriff selbst einen `KeyError` — **innerhalb**
der Fehlerbehandlung des ursprünglichen Fehlers. Python propagiert diesen zweiten Fehler
nach oben, `_dispatch_alert_message()` bricht komplett ab, und alle Kanäle, die in der
Aufrufreihenfolge NACH Premium-SMS liegen, erhalten ihren Alarm ebenfalls nicht — aus einem
Teilausfall wird ein Totalausfall.

Fix: `label = {"email": "Email", "telegram": "Telegram", "sms": "SMS",
"premium_sms": "Premium-SMS"}.get(channel, channel)` — das `.get()` mit Fallback macht die
Stelle zusätzlich robust gegen einen fünften, künftigen Kanal, der denselben Fehler sonst
wiederholen würde.

### D5 — Sperrgrund im Alarm-Protokoll: maschinenlesbar statt generisch

Heute kennt `alert_log._channels_not_sent()` genau drei Gründe für „nicht zugestellt":
`channel_disabled` (Kanal aus), `below_channel_threshold` (#1461) und `delivery_failed`
(Sammelbecken für alles andere). Ein blockierter Premium-SMS-Versand (leere/veraltete
Rückadresse) landet damit ununterscheidbar von einem echten Transportfehler im selben
Sammelbecken — genau die Kopplung, die S2a mit `ChannelBlockedError.reason_code` bereits für
das Briefing gelöst hat.

`append_entry()` bekommt einen neuen optionalen Parameter `blocked_reason_codes:
Optional[dict[str, str]] = None` (Kanal → `reason_code`, z.B.
`premium_sms_no_reply_address`). `_channels_not_sent()` prüft ihn VOR den bisherigen drei
Fällen: hat ein nicht zugestellter Kanal einen Eintrag in `blocked_reason_codes`, wird dessen
Wert als Grund übernommen statt `REASON_DELIVERY_FAILED`. Alle drei Alarm-Dispatcher
(`_dispatch_alert_message`, `send_official_alert`, `send_compare_official_alert`) füllen
`NotificationResult.blocked_reason_codes` für Premium-SMS über `_record_block_reason_code()`
(bereits aus S2a vorhanden, unverändert wiederverwendet) — für die drei Bestandskanäle bleibt
das Feld leer, ihr Verhalten ändert sich nicht.

### D6 — Kanal-Schwelle: nur das Go-Feld fehlt

`alert_channel_threshold.split_by_threshold()` ist bereits kanal-agnostisch (iteriert über
das übergebene Kanal-Set, Default `"LOW"` für unbekannte Kanäle) — hier ist **kein**
Python-Code-Eingriff nötig. Die ADR-0046-Pflicht „jede Stelle, die ein Kanal-Set auflöst,
muss die Schwelle anwenden" ist für Premium-SMS damit automatisch erfüllt, sobald der Kanal
im aufgelösten Set auftaucht — vorausgesetzt, der Nutzer kann die Schwelle überhaupt SETZEN.
Das fehlende Stück ist ausschließlich `AlertChannelThresholdsConfig.PremiumSms *string` in Go
plus der zugehörige Merge-Zweig (Vorbild: die drei bestehenden Zweige direkt daneben).

### D7 — Erfolgs-Ratsche anheben, nicht umgehen

`tests/test_success_status_guard.py` erwartet für `send_official_alert` und
`_dispatch_alert_message` exakt drei `sent_channels.append()`-Aufrufe vor dem jeweiligen
`try` (B14a/B14c, dokumentierter Mangel: „Marker vor der Tat"). Mit dem vierten Kanal wird
daraus vier. **Der naheliegende Schluss — die Buchung hinter den `try` ziehen, damit die
Ratsche bei 0 bleibt — ist FALSCH** (zwei frühere Sitzungen sind unabhängig darauf
hereingefallen, s. Memory): `alert_log.append_entry()` nimmt bewusst ZWEI getrennte Listen
(`sent_channels`=„versucht", `reachable_channels`=„erreichbar") entgegen, und alle sechs
Aufrufstellen übergeben beide. Eine Verschiebung der Buchung würde diese Unterscheidung
zerstören. Richtiger Zug: die erwartete Zahl in `test_success_status_guard.py` von 3 auf 4
anheben, mit Pflicht-Nachzug in `docs/specs/modules/waechter_1405_erfolg_wirkung.md`
(dort steht wörtlich, Ratschen-Zahlen würden „IN DER SPEC beschlossen und dort nachgezogen").

**Offen für die Implementierung:** ob `send_compare_official_alert()` (die neue
`_dispatch_compare_official_premium_sms`-Erweiterung) vom selben Scanner überhaupt als
Fundstelle erkannt wird — die Funktion `sent_channels.append("email")` UNBEDINGT vor dem
`if not self._dispatch_compare_official_email(...)`-Aufruf ist strukturell dieselbe Klasse,
aber in der aktuellen Ratschen-Liste nicht als eigene Zeile geführt (nur `send_compare_preset`
ist als B12 gelistet, ein anderes Muster). Vor dem Anheben ist am Bestand zu messen, ob der
Scanner hier überhaupt reagiert — siehe „Known Limitations".

### D8 — Ortsvergleich: `SendPremiumSms` als eigenes Go-Feld, kein Wiederverwenden

`ComparePreset` hat heute `SendTelegram`/`SendSms *bool` (`compare_preset.go:91-92`) als
Kanal-Opt-in — kein Pendant zu `Trip.AlertChannels` (der Ortsvergleich hat kein
`alert_channels`-Sub-Objekt, die Kanäle sind flache Top-Level-Felder). Premium-SMS bekommt
konsequent ein eigenes `SendPremiumSms *bool`, Merge nach demselben Muster wie die beiden
Nachbarfelder (`handler/compare_preset.go:407-411`).

## Expected Behavior

- **Input:** ein ausgelöster Alarm (Abweichung, Regenradar-Onset, amtliche Warnung) für
  einen Trip oder Ortsvergleich, dessen effektives Kanal-Set `"premium_sms"` enthält.
- **Output:** ein POST an `gateway.seven.io` mit fester Absendernummer und der gelernten
  Rückadresse als Empfänger (identisch zu S2a) — der Alarmtext statt des Briefing-Texts.
  Bei blockiertem/gescheitertem Versand: die anderen effektiven Kanäle werden trotzdem
  bedient, und `alert_log.json` trägt einen auswertbaren Grund für `premium_sms`.
- **Side effects:** keine neue Persistenz außer dem einen neuen Go-Feld je betroffenem
  Struct (`AlertChannelsConfig.PremiumSms`, `AlertChannelThresholdsConfig.PremiumSms`,
  `ComparePreset.SendPremiumSms`). Bestandsdaten aller drei bestehenden Felder bleiben beim
  Speichern unverändert erhalten (Read-Modify-Write, kein Replace).

## Acceptance Criteria

- **AC-1:** Given ein Premium-Tier-Nutzer hat in seinem Trip `alert_channels.premium_sms = true` UND eine gültige, frische gelernte Rückadresse / When ein Abweichungs- oder Regenradar-Alarm für diesen Trip ausgelöst wird / Then geht eine Premium-SMS mit dem Alarmtext an das Gerät hinaus — genauso zuverlässig wie bei gleicher Konfiguration für E-Mail, Telegram oder SMS.
  - Prüfort: `payload["to"]`/`payload["text"]` am lokalen HTTP-Stub, ausgelöst über `TripAlertService._send_alert()` bzw. `check_radar_alerts()`.
  - Test: `tests/unit/test_alert_channel_premium_sms.py::test_deviation_alert_reaches_premium_sms_when_opted_in`, `::test_radar_alert_reaches_premium_sms_when_opted_in`

- **AC-2:** Given ein Trip hat kein scharfes `alert_channels`-Set (`None`) UND im Trip-Briefing ist `send_premium_sms=true` aktiv / When ein Alarm für diesen Trip ausgelöst wird / Then erbt der Alarmpfad den Premium-SMS-Kanal automatisch mit — kein Trip verliert den vierten Kanal nur deshalb, weil er nie ein scharfes Alarm-Kanal-Set gesetzt hat, genau wie es heute für die drei bestehenden Kanäle gilt.
  - Prüfort: `_briefing_channels()`-Rückgabe UND End-zu-Ende am HTTP-Stub mit einer Fixture, deren `trip.alert_channels is None`.
  - Test: `tests/unit/test_alert_channel_premium_sms.py::test_legacy_trip_inherits_premium_sms_from_briefing_config`

- **AC-3:** Given Premium-SMS ist im effektiven Kanal-Set eines Trips für amtliche Warnungen enthalten / When eine amtliche Warnung für diesen Trip eintrifft / Then wird auch dafür eine Premium-SMS mit dem amtlichen Kurztext versendet — der amtliche Warnpfad (`send_official_alert`) ist eine von `_dispatch_alert_message` unabhängige Funktion und wäre sonst der stille vierte blinde Fleck.
  - Prüfort: HTTP-Stub gegen `NotificationService.send_official_alert()` direkt, mit `effective_channels={"email","premium_sms"}`.
  - Test: `tests/unit/test_alert_channel_premium_sms.py::test_official_trip_alert_reaches_premium_sms`

- **AC-4:** Given ein Ortsvergleich-Preset hat `send_premium_sms=true` (Nutzer ist Premium-Tier) / When ein Änderungs-, Regenradar- oder amtlicher Alarm für einen betroffenen Vergleichsort ausgelöst wird / Then wird der Ort in allen drei Fällen zusätzlich per Premium-SMS gemeldet — nicht nur bei E-Mail/Telegram/SMS, wie es heute für alle drei Ortsvergleichs-Alarmpfade gilt.
  - Prüfort: HTTP-Stub gegen `compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` (bzw. `send_compare_official_alert()` direkt), je ein Fall pro Alarmart.
  - Test: `tests/unit/test_compare_alert_premium_sms.py::test_compare_deviation_alert_reaches_premium_sms`, `::test_compare_radar_alert_reaches_premium_sms`, `::test_compare_official_alert_reaches_premium_sms`

- **AC-5:** Given ein Nutzer mit Tier `standard` hat (fälschlich oder testweise) `alert_channels.premium_sms=true` bzw. `send_premium_sms=true` im Ortsvergleich gesetzt / When ein Alarm für Trip oder Ortsvergleich ausgelöst wird / Then bleibt der Premium-SMS-Kanal in allen drei Alarmpfaden inaktiv — dasselbe strenge Tier-Gate (`premium_sms_allowed`) wie im Trip-Briefing, nicht das schwächere `sms_allowed`, das `standard` durchlässt.
  - Prüfort: HTTP-Stub bleibt leer (`stub.received == []`) für den Premium-Kanal bei einer `standard`-Tier-Fixture, in allen drei Dispatchern.
  - Test: `tests/unit/test_alert_channel_premium_sms.py::test_standard_tier_never_reaches_premium_sms_via_alerts`, `tests/unit/test_compare_alert_premium_sms.py::test_standard_tier_never_reaches_premium_sms_via_compare_alerts`

- **AC-6:** Given ein Alarm geht an mehrere Kanäle gleichzeitig, darunter Premium-SMS, UND der Premium-Versand schlägt fehl (z.B. keine gelernte Rückadresse) / When der Alarm verarbeitet wird / Then erreichen die übrigen konfigurierten Kanäle (E-Mail/Telegram/SMS) den Nutzer trotzdem, unbeeinträchtigt vom Premium-Fehlschlag.
  - Prüfort: Fixture mit vier aktiven Kanälen, Premium-SMS gezielt blockiert (leere Rückadresse) — die anderen drei POSTs kommen am jeweiligen Stub an, KEIN unbehandelter `KeyError`/Absturz in `_log_error()`.
  - Test: `tests/unit/test_alert_channel_premium_sms.py::test_failed_premium_sms_does_not_abort_remaining_channels`

- **AC-7:** Given ein bestehender Trip hat bereits `alert_channels` mit gesetzten Werten für E-Mail/Telegram/SMS gespeichert / When der Nutzer über die API ein PUT ohne das vierte Feld `premium_sms` schickt (z.B. eine ältere Frontend-Version) / Then bleiben die drei bestehenden Kanal-Einstellungen unverändert erhalten UND ein zuvor gesetzter Premium-SMS-Wert wird NICHT auf `false` zurückgesetzt.
  - Prüfort: Go-Handler-Test, zwei aufeinanderfolgende PUTs — erster setzt alle vier Felder, zweiter schickt nur drei; danach wird der volle gespeicherte Trip gelesen und das vierte Feld geprüft.
  - Test: `internal/handler/trip_alert_channels_test.go::TestAlertChannels_FourthFieldMissingInBody_PreservesExistingValue`

- **AC-8:** Given ein Nutzer hat für Premium-SMS eine Dringlichkeits-Schwelle „HIGH" eingestellt UND ein ausgelöster Alarm hat die Dringlichkeit „MODERATE" / When der Alarm verarbeitet wird / Then bleibt die Premium-SMS diesmal aus (unter der Schwelle), exakt wie es heute für die drei bestehenden Kanäle gilt — Premium-SMS ist von der Kanal-Schwelle nicht ausgenommen.
  - Prüfort: `alert_channel_threshold.split_by_threshold()` mit einem Kanal-Set, das `"premium_sms"` enthält, und einer Trip-Fixture mit `alert_channel_thresholds.premium_sms="HIGH"`.
  - Test: `tests/unit/test_alert_channel_threshold_premium_sms.py::test_premium_sms_suppressed_below_configured_threshold`

- **AC-9:** Given eine Alarm-Meldung sollte per Premium-SMS gehen, aber die gelernte Rückadresse ist leer oder älter als 30 Tage / When der Alarm-Lauf abgeschlossen ist / Then zeigt das Alarm-Protokoll (`alert_log.json`) den Kanal `premium_sms` unter `channels_not_sent` mit dem spezifischen Grund (`premium_sms_no_reply_address` bzw. `premium_sms_reply_address_stale`) — nicht mit dem generischen „technisch gescheitert" und nicht als spurloses Fehlen im Protokoll.
  - Prüfort: `alert_log.json` nach dem Testlauf gelesen (kein Mock des Protokolls selbst), `channels_not_sent`-Eintrag für `premium_sms` mit dem erwarteten `reason`-Wert.
  - Test: `tests/unit/test_alert_log_premium_sms_channel.py::test_blocked_premium_sms_reason_is_specific_not_generic`

- **AC-10:** Given der Adversary verfälscht die neue Verdrahtung so, dass ein Kanal als „versucht" (`sent_channels`) gebucht wird, obwohl `PremiumSmsOutput.send()` nie aufgerufen wurde (oder umgekehrt: der Aufruf erfolgt, ohne dass er gebucht wird) / When die Ratschen-Testsuite (`test_success_status_guard.py`) läuft / Then schlägt genau der dafür benannte Test fehl — die Erfolgs-Ratsche wurde bewusst von 3 auf 4 angehoben, nicht deaktiviert, umgangen oder durch Verschieben der Buchung hinter den `try` unterlaufen.
  - Prüfort: `test_no_unlisted_success_status_findings` bzw. der spezifische Index-Test für `send_official_alert`/`_dispatch_alert_message`.
  - Test: `tests/test_success_status_guard.py` (MODIFY, erwartete Zahl 3→4 je Funktion)

## Was sich NICHT ändern darf (Invarianten)

- Die drei bestehenden Kanäle (E-Mail, Telegram, SMS) verhalten sich in allen drei
  Alarm-Dispatchern (`_dispatch_alert_message`, `send_official_alert`,
  `send_compare_official_alert`) byte-identisch zu vorher — keine der bestehenden
  Testsuiten für diese Kanäle darf sich ändern müssen.
- `alert_log.append_entry()` bleibt für alle Bestandsaufrufe ohne `blocked_reason_codes`
  (Default `None`) exakt beim heutigen Verhalten: generischer `delivery_failed`.
- Die Unterscheidung `sent_channels` („betreten/versucht") vs. `reachable_channels`
  („erreichbar") bleibt bestehen — die Ratschen-Anhebung (D7) verschiebt keine Buchung
  zwischen diesen beiden Ebenen.
- `settings.can_send_premium_sms()` wird NICHT wieder eingeführt (D2) — auch nicht unter
  anderem Namen mit gleicher Wirkung (vorgeschaltete Bereitschaftsfrage, die die
  Fail-Closed-Prüfung im Kanal abschirmt).
- Bestandsdaten aller drei bereits gespeicherten `AlertChannelsConfig`-Felder und aller drei
  `AlertChannelThresholdsConfig`-Felder bleiben bei jedem PUT ohne das vierte Feld
  unverändert erhalten (Read-Modify-Write, niemals Replace) — AC-7.

## Bewusst nicht in dieser Scheibe

- Kein UI-Kontrollelement für `alert_channels.premium_sms`, `send_premium_sms` (Compare)
  oder die Premium-SMS-Kanal-Schwelle (folgt S3).
- Kein neues ADR — ADR-0049 legt den Kanalnamen bereits fest, ADR-0046 verpflichtet bereits
  zur Schwellenanwendung; diese Scheibe löst beide Verpflichtungen ein, ohne sie zu ändern.
- Keine Kostenstelle/kein Kontingent für Premium-SMS-Alarme (S2c/#1702).
- Kein Eingriff in `alert_channel_threshold.split_by_threshold()` selbst — die Funktion ist
  bereits kanal-agnostisch.

## Nachweisgrenzen — was diese Scheibe NICHT beweist

Wie in S2a strukturell nicht beweisbar: dass eine Alarm-Premium-SMS tatsächlich auf dem
Garmin-Gerät ankommt. Dieselben Gründe wie in S2a (Herkunftssperre erzwingt Sandbox-Key,
`force_test` sandboxiert Staging zusätzlich, Staging-Scheduler führt keinen Job aus) gelten
unverändert. Dieser Nachweis ist als **SKIPPED** auszuweisen und gehört in **#1533**.

Zusätzlich in dieser Scheibe strukturell offen: ob der Ratschen-Scanner
(`test_success_status_guard.py`) die neue `_dispatch_compare_official_premium_sms`-Erweiterung
überhaupt als eigene Fundstelle erkennt (D7, „Known Limitations"). Das ist am Bestand vor der
Implementierung zu messen, nicht anzunehmen.

## Mutations-Gegenprobe

| AC | Gezielte Verfälschung | Test, der dadurch rot werden MUSS |
|---|---|---|
| AC-1 | `_dispatch_alert_message()`: Premium-Zweig fehlt / prüft falschen Kanalnamen | `test_deviation_alert_reaches_premium_sms_when_opted_in` |
| AC-2 | `_briefing_channels()`: `send_premium_sms`-Zweig entfernt | `test_legacy_trip_inherits_premium_sms_from_briefing_config` |
| AC-3 | `send_official_alert()`: Premium-Zweig liest `config.send_sms` statt eigenem Flag / fehlt ganz | `test_official_trip_alert_reaches_premium_sms` |
| AC-4 | `effective_compare_channels()`: `send_premium_sms`-Zweig entfernt | alle drei Compare-Tests in `test_compare_alert_premium_sms.py` |
| AC-5 | `premium_sms_allowed()`-Aufruf durch `sms_allowed()` ersetzt (an einer der drei Gate-Stellen) | jeweiliger `test_standard_tier_never_reaches_premium_sms_via_*`-Test |
| AC-6 | `_log_error()`-Label-Dict-Fix zurückgenommen (harter `[channel]`-Zugriff) | `test_failed_premium_sms_does_not_abort_remaining_channels` — die anderen Kanäle bekämen keinen Request mehr |
| AC-7 | `handler/trip.go`: Feld-Level-Merge durch Ganzobjekt-Ersatz zurückgetauscht | `TestAlertChannels_FourthFieldMissingInBody_PreservesExistingValue` |
| AC-8 | `AlertChannelThresholdsConfig.PremiumSms` beim Auflösen ignoriert (Default `"LOW"` immer verwendet) | `test_premium_sms_suppressed_below_configured_threshold` |
| AC-9 | `_channels_not_sent()`: `blocked_reason_codes`-Vorrang entfernt | `test_blocked_premium_sms_reason_is_specific_not_generic` |
| AC-10 | Ratschen-Zahl nicht angehoben (bleibt 3) ODER Buchung hinter `try` verschoben | `test_success_status_guard.py`-Ratschentests selbst (rot bzw. — bei verschobener Buchung — eine der Alarm-Tests, die `sent_channels` vs. `reachable_channels` unterscheiden) |

## Known Limitations

- **Ratschen-Reichweite für `send_compare_official_alert` ungeklärt (D7).** Ob der
  Scanner diese Funktion als eigene B14a-artige Fundstelle listet, ist vor der
  Implementierung zu messen (aktuell nur `send_compare_preset` als B12 gelistet, ein
  strukturell anderes Muster). Fällt sie darunter, braucht auch sie eine
  Zahlen-Anhebung; fällt sie nicht darunter, ist nichts zu tun. Diese Spec trifft die
  Entscheidung nicht vorab, weil eine falsche Annahme hier entweder unnötigen Code oder
  eine übersehene Ratschen-Lücke erzeugen würde.
- **Kein Frontend, keine Sichtbarkeit für den Nutzer** — wie in S2a, folgt in S3.
- **`AlertChannelsConfig` verliert die „All-or-nothing"-Garantie (D3).** Das ist
  beabsichtigt (Voraussetzung für Bestandsschutz), bedeutet aber: ein Client, der künftig
  gezielt einen Kanal auf `false` setzen will, muss ihn jetzt explizit im Body mitschicken —
  das war vorher implizit durch „immer alle drei" gegeben. Für S3 zu beachten, nicht Teil
  dieser Scheibe.
- **Kanal-Schwelle bleibt ohne Bedienelement** — ein per API gesetzter Wert wirkt, ist aber
  bis S3 nur über direkte API-Aufrufe erreichbar.
- **Nachweis am Gerät bleibt #1533**, unverändert zu S2a.

## Test Coverage

- `tests/unit/test_alert_channel_premium_sms.py` (CREATE) — Trip-Alarmpfade (AC-1, AC-2,
  AC-3, AC-5 Trip-Teil, AC-6).
- `tests/unit/test_compare_alert_premium_sms.py` (CREATE) — Ortsvergleich-Alarmpfade
  (AC-4, AC-5 Compare-Teil).
- `tests/unit/test_alert_log_premium_sms_channel.py` (CREATE) — Protokoll-Verhalten (AC-9),
  `_ALL_CHANNELS`-Erweiterung ohne stilles Loch.
- `tests/unit/test_alert_channel_threshold_premium_sms.py` (CREATE) — Kanal-Schwelle (AC-8).
- `internal/handler/trip_alert_channels_test.go` (MODIFY) — Feld-Level-Merge Trip (AC-7).
- `internal/handler/trip_alert_channel_thresholds_test.go` (MODIFY) — vierte Schwelle Trip.
- `internal/handler/compare_preset_official_alerts_test.go` (MODIFY) — `SendPremiumSms`-Merge
  Ortsvergleich.
- `internal/handler/compare_preset_alert_channel_thresholds_test.go` (MODIFY) — vierte
  Schwelle Ortsvergleich.
- `tests/test_success_status_guard.py` (MODIFY) — Ratsche (AC-10).

Testdateien liegen unter `tests/unit/` (`touched_tests_gate.py:37`) bzw. `internal/handler/`
(Go-Testkonvention). Namen nach Verhalten, nicht nach Issue-Nummer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue).
- **Rationale:** ADR-0049 legt den Kanalnamen `premium_sms` bereits verbindlich fest —
  diese Scheibe erweitert seine Reichweite auf zwei weitere Versandanlässe, ohne die
  Entscheidung selbst zu ändern. ADR-0046 verpflichtet bereits zur Anwendung der
  Kanal-Schwelle an jeder neuen Kanal-Set-Auflösungsstelle; diese Scheibe löst diese
  Verpflichtung für Premium-SMS ein (AC-8), statt sie zu widerrufen oder zu erweitern.

## Changelog

- 2026-08-11: Initial spec erstellt — Issue #1701, Scheibe S2b von #1676
