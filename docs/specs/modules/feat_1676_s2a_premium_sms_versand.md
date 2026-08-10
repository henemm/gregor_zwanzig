---
entity_id: feat_1676_s2a_premium_sms_versand
type: module
created: 2026-08-10
updated: 2026-08-10
status: draft
version: "1.0"
tags: [sms, premium, garmin, seven-io, channel, dual-stack]
---

<!-- Issue #1676 (Scheibe S2a) -- Premium-SMS als vierter Versandkanal,
     nur Trip-Briefing. Vorgaenger: S1 (feat_1676_s1_premium_sms_rueckkanal.md,
     live). Nachfolger: S2b/#1701 (Alarme/Vergleich), S2c/#1702 (Kostenstelle),
     S3 (Oberflaeche), S4/#1533 (Generalprobe auf dem Geraet). -->

# Premium-SMS als vierter Versandkanal — S2a: Trip-Briefing

## Approval

- [x] Approved — PO-Freigabe 2026-08-10 ("freigabe"), inkl. 30-Tage-Frist (D6)
      und Schnitt S2a (S2b → #1701, S2c → #1702)

## Purpose

Premium-SMS (Garmin inReach) wird ein vollwertiger, eigenständiger vierter
Versandkanal `premium_sms` — ausschließlich für das Trip-Briefing. Fester
Absender (unsere seven.io-Dienstnummer), Empfänger ausschließlich die in S1
gelernte, veränderliche Rückadresse aus `user.json`. Bei fehlender oder älter
als 30 Tage alter Rückadresse geht **keine** SMS hinaus — mit einem sichtbaren,
auswertbaren Grund statt einem stillen Ausbleiben. S1 lernt die Rückadresse
bereits; ohne diese Scheibe geht nichts an das Gerät.

## Abgrenzung (nicht in dieser Scheibe)

- **S2b — Alarm- und Vergleichspfad (#1701):** `_ALL_CHANNELS`
  (`alert_log.py:59`), die zweite unabhängige Dreier-Liste
  (`trip_alert.py:1446`), Kanal-Schwellen (ADR-0046), die Erfolgs-Ratsche
  `test_success_status_guard.py`, `api_contract.md`-Nachzug für
  `AlertChannelsConfig`/`AlertChannelThresholdsConfig`. Diese Scheibe rührt
  den Alarm-Pfad nicht an — `send_trip_report()` ist von der Erfolgs-Ratsche
  ausdrücklich verschont (nachgemessen), ein reiner Briefing-Schnitt löst sie
  nicht aus.
- **S2c — Kostenstelle (#1702):** Kosten-/Kontingent-/Versandzähler je Kanal
  existieren im Bestand nirgends (nur das Tier-Tageslimit für Alarme,
  `user_tier.py:17-31`). Eigenes Feature ohne Vorbild, nicht Teil dieser
  Scheibe.
- **S3 — Oberfläche:** Kanal-Auswahl und gelernte Rückadresse im Frontend
  sichtbar/schaltbar. Diese Scheibe bleibt reines Backend; `send_premium_sms`
  ist in S2a nur über den freien `report_config`-Schlüssel setzbar, noch
  nicht über ein UI-Kontrollelement.
- **#1533 — Generalprobe auf dem Gerät (Frist 20.8.):** der einzige Nachweis,
  dass eine Premium-SMS tatsächlich am Garmin-Gerät ankommt. Siehe
  „Nachweisgrenzen" unten.

## Source

- **File:** `src/output/channels/seven_io_base.py` (NEU, ~80 LoC) — gemeinsame
  Basisklasse `SevenIoChannelBase`: beide Sicherheitssperren
  (`_guard_test_mode_sandbox_key`, `_guard_code_origin`, Vorbild
  `sms.py:34-75`) und der HTTP-Transport (Vorbild `sms.py:77-102`) als
  Template-Method, genau einmal statt zweimal.
- **File:** `src/output/channels/premium_sms.py` (NEU, ~50 LoC) —
  `PremiumSmsOutput`, `name == "premium_sms"`, fester Absender
  `4916092172595`, `_resolve_recipient()` prüft leer/veraltet fail-closed.
- **File:** `src/output/channels/sms.py` (MODIFY, ≈−60 LoC) — auf die
  Basisklasse umgestellt, Verhalten unverändert. Selber Commit wie die neue
  Basisklasse (D1) — sonst wären die Sicherheitssperren zwischenzeitlich
  dupliziert statt vereinheitlicht.
- **File:** `src/output/channels/base.py` (MODIFY, +~40 LoC) —
  `get_channel("premium_sms")` für CLI-Parität (Vorbild `:93-95`), **plus**
  `ChannelBlockedError(OutputConfigError)` mit Pflichtfeld `reason_code`
  (Nachtrag 2026-08-10, s. D10).
- **File:** `src/app/config.py` (MODIFY) — zwei Felder
  `premium_sms_reply_to`/`premium_sms_reply_at`, Übernahme in
  `with_user_profile()` (Muster `:307-313`), ENV-Sperre gegen
  `GZ_PREMIUM_SMS_REPLY_TO` **und** `GZ_PREMIUM_SMS_REPLY_AT`.
  **Korrektur nach Adversary-Runde 1 (F003):** ein zunächst gebautes
  `can_send_premium_sms()` ist wieder **entfernt**. Eine vorgeschaltete
  Bereitschaftsfrage im Versandzweig würde die Fail-closed-Prüfung im Kanal
  *abschirmen* — die Mutations-Gegenprobe zu AC-3 (Prüfung im Kanal entfernt)
  wäre dann grün geblieben. An ihrer Stelle steht eine Begründung im Code plus
  ein Wächter-Test, der ihre Rückkehr rot macht.
- **File:** `src/services/notification_service.py` (MODIFY, +~25 LoC) —
  Sendezweig in `send_trip_report()` neben dem bestehenden SMS-Zweig
  (`:369-377`), neues Feld `NotificationResult.blocked_channels`.
- **File:** `src/services/trip_report_scheduler.py` (MODIFY, +~10 LoC) —
  `send_premium_sms=config is not None and config.send_premium_sms and
  premium_sms_allowed(self._user_id)` an beiden Kanal-Entscheidungsstellen
  (`:965`, `:1303`).
- **File:** `src/services/user_tier.py` (MODIFY, +~10 LoC) —
  `premium_sms_allowed(user_id)`, ausschließlich Tier `premium`.
- **File:** `src/app/models.py` (MODIFY, +1 LoC) —
  `TripReportConfig.send_premium_sms: bool = False` (Muster `:924-926`).
- **File:** `src/app/loader.py` (MODIFY) — Feld an **zwei** Stellen mitziehen:
  Lesen in `_parse_trip` (`:574-579`) und Schreiben in `_trip_to_dict`
  (`:1600-1605`), beide auf der `report_config`-Ebene.
  **Korrektur 2026-08-10:** eine frühere Fassung dieser Zeile nannte fünf
  Stellen. Die drei weiteren gehören zum flachen Dual-Read-Mechanismus
  (`trip.send_sms`/`send_telegram`, #1250 Scheibe 4) — dort ist **kein**
  `send_premium_sms`-Pendant angelegt und auch keines nötig: der Sendepfad
  liest ausschließlich `trip.report_config.send_premium_sms`
  (`trip_report_scheduler.py:971`, `:1315`). Die Parität zum flachen Feld wird
  erst mit S3 relevant. Die alte Zeile behauptete Umfang, den der Code nicht
  einlöst.
- **File:** `src/output/renderers/channel_layout.py` (MODIFY, +1 Zeile) —
  defensiver `CHANNEL_LIMITS["premium_sms"]`-Eintrag; verhindert den stillen
  Telegram-Rückfall (`:97`), falls ein künftiger Aufrufer (S3) den Kanal dort
  nachschlägt. Der Briefing-Pfad selbst liest `CHANNEL_LIMITS` nicht (s.
  Implementation Details) — reine Vorsorge, kein funktionaler Bestandteil
  dieser Scheibe.
- **File:** `docs/adr/0049-premium-sms-vierter-kanal.md` (NEU) — schreibt
  ADR-0004 fort, legt den Kanalnamen `premium_sms` verbindlich fest, VOR dem
  Code.
- **File:** `tests/unit/test_premium_sms_versand.py` (NEU, ~250 LoC) —
  HTTP-Stub gegen `PremiumSmsOutput`/`send_trip_report()`.
- **File:** `tests/unit/test_config_premium_sms.py` (NEU, ~80 LoC) —
  Settings-Felder, Profil-Übernahme, ENV-Sperre.
- **File:** `tests/unit/test_user_tier.py` (**CREATE**, ~70 LoC) —
  `premium_sms_allowed()`. Korrektur 2026-08-10: die Spec nahm diese Datei
  als Bestand an, sie existierte nicht. `sms_allowed()` wird heute nur
  beiläufig in `tests/tdd/`-Dateien mitgeprüft (u. a.
  `test_issue_1069_tier_channel_gating.py`), es gibt keinen eigenen
  Tier-Test unter `tests/unit/`. Die Datei enthält deshalb zusätzlich einen
  Bestandsnachweis für `sms_allowed()` als Kontrast zu AC-8.
- **File:** `tests/tdd/test_channel_origin_guard_parity.py` (MODIFY,
  +~30 LoC) — `PremiumSmsOutput` in die bestehende Guard-Parität
  aufgenommen (dort heute nur `EmailOutput`/`SMSOutput` namentlich geprüft).

## Estimated Scope

- **LoC (Produktivcode):** ≈ +150 netto (Basisklasse +80, Premium-Kanal +50,
  `sms.py` schrumpft ≈ −60, Rest +80).
- **LoC (Tests):** geschätzt ≈ +400, **gemessen nach RED: +874**
  (`test_premium_sms_versand.py` 539, `test_config_premium_sms.py` 156,
  `test_user_tier.py` 69, `test_channel_origin_guard_parity.py` +110).
  Die Schätzung war um mehr als das Doppelte zu niedrig. Gründe, benannt statt
  weggerundet: der echte lokale HTTP-Server samt Trip-Fixtures ist Aufbau vor
  der ersten Zusicherung; AC-10 prüft vier Schaltkombinationen; AC-4/AC-5 sind
  ein Kantenpaar mit je eigener Fixture; AC-7 wird am eingegangenen Request
  gemessen statt am Transport-Sink der Bestandstests.
- **Gesamt erwartet:** ≈ +1024 (874 Tests + ≈ 150 Produktivcode) — LoC-Override
  auf 1200 gesetzt. Doku zählt nicht mit.
- **Files:** 5 CREATE (2 Code, 2 Test, 1 ADR) + 10 MODIFY.
- **Effort:** medium.
- **Risiko:** MEDIUM. Kein Bestandsverhalten ändert sich außer dem
  `sms.py`-Refactor — der ist durch die bestehende SMS-Testsuite abgedeckt.
  Der Rest ist additiv.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | Vorgänger-Spec | liefert `premium_sms_reply_to`/`premium_sms_reply_at` in `user.json` — alleinige Datenquelle dieser Scheibe |
| `src/output/channels/sms.py` | Vorbild/Umbau | Template-Method-Basis, Guards, HTTP-Transport (D1) |
| `src/app/config.py::with_user_profile` | module | einziger Profil→Settings-Übersetzer (D2), einzige Stelle, die `get_data_dir()`-Isolation respektiert |
| `src/services/user_tier.py::sms_allowed` | Vorbild, NICHT wiederverwendet | Struktur für `premium_sms_allowed` — `sms_allowed` lässt `standard` durch, das darf Premium-SMS nicht (D7) |
| `src/services/notification_service.py::send_trip_report` | module | Sendezweig-Integrationspunkt, einzige maßgebliche Stelle im Briefing-Pfad |
| `src/services/trip_report_scheduler.py` | module | beide Kanal-Entscheidungsstellen (`:965`, `:1303`) |
| `docs/adr/0004-signal-channel-removed.md` | ADR | wird fortgeschrieben (D9), nicht widerrufen |
| `tests/tdd/test_issue_936_sms_stub.py` | Test-Vorbild | lokaler HTTP-Stub-Aufbau (kein Mock) |
| `tests/tdd/test_channel_origin_guard_parity.py` | Test-Vorbild, MODIFY | Guard-Parität-Muster, wird um `PremiumSmsOutput` erweitert |
| `src/app/egress_guard.py` | module | `gateway.seven.io` bereits `TEST_ACCESS` (`:52`) — kein neuer Eintrag nötig |

## Implementation Details

### Kanal-Klasse: Template-Method über eine gemeinsame Basis (D1)

`seven_io_base.py` trägt beide Sicherheitssperren und den HTTP-Transport
genau einmal. `SMSOutput` und `PremiumSmsOutput` überschreiben nur
Empfänger-/Absender-Auflösung (Skizze, nicht wörtlicher Endstand):

```python
class SMSOutput(SevenIoChannelBase):
    name = "sms"
    def _resolve_sender(self) -> str | None:
        return self._settings.sms_from or None
    def _resolve_recipient(self) -> str:
        return self._settings.sms_to

class PremiumSmsOutput(SevenIoChannelBase):
    name = "premium_sms"
    PREMIUM_SMS_SENDER = "4916092172595"
    def _resolve_sender(self) -> str:
        return self.PREMIUM_SMS_SENDER
    def _resolve_recipient(self) -> str:
        reply_to = self._settings.premium_sms_reply_to
        reply_at = self._settings.premium_sms_reply_at
        if not reply_to or not reply_at:
            raise OutputConfigError("premium_sms", "keine gelernte Rueckadresse")
        if _now() - reply_at > PREMIUM_SMS_REPLY_TTL:
            raise OutputConfigError("premium_sms", "Rueckadresse veraltet (>30 Tage)")
        return reply_to
```

Eine Kopie statt einer gemeinsamen Basis hätte die Vergessbarkeit der beiden
Sperren verdoppelt — genau das, was sie verhindern sollen. Ein
Varianten-Parameter an `SMSOutput` wäre technisch dichter, verstößt aber
gegen die PO-Vorgabe „eigener Kanal, keine Variante".

### Fail-Closed sitzt in der Kanal-Klasse, nicht am Aufrufort (D3)

`_resolve_recipient()` wirft `OutputConfigError`; `send()` in der Basisklasse
ruft sie vor jedem HTTP-Call auf. Der bestehende SMS-Zweig prüft
`can_send_sms()` vorher (`notification_service.py:369`) — das reicht bei
Premium-SMS nicht: „leer" und „veraltet" sind erst zur Sendezeit final
bekannt, und die Vorgabe verlangt einen sichtbaren, keinen stillen
Fehlschlag.

### Sichtbarkeit des Fehlschlags: `blocked_channels` (D4)

`NotificationResult` bekommt ein neues Feld `blocked_channels: dict[str,
str]` (Kanal → Grund). Der Sendezweig in `send_trip_report()` fängt
`OutputConfigError`/`OutputError` von `PremiumSmsOutput` ab und trägt den
Grund dort ein, statt ihn nur zu loggen — eine Logzeile ist kein Nachweis.

### Maschinenlesbarer Sperrgrund (D10, Nachtrag 2026-08-10, PO-freigegeben)

Der Wert in `blocked_channels` ist deutscher Klartext — als Diagnose brauchbar, als Quelle für
das Alarm-Protokoll nicht: `alert_log.py:40-52` führt stabile Kurzschlüssel
(`channel_disabled`, `delivery_failed`, `below_channel_threshold`). Die Session, die S2b
(#1701) baut, hätte auf deutschen Prosatext vergleichen müssen, um die zwei Sperrfälle zu
unterscheiden — eine Kopplung, die beim ersten Umformulieren still bricht.

Deshalb trägt die Ursache eine **maschinenlesbare Kennung**:
`ChannelBlockedError(OutputConfigError)` in `base.py` mit Pflichtfeld `reason_code`, Werte
`premium_sms_no_reply_address` und `premium_sms_reply_address_stale` (als Konstanten
`BLOCK_REASON_*` aus `premium_sms.py` importierbar).

Warum eine Unterklasse und nicht ein Attribut an `OutputError`: der Alarmpfad sieht **nur die
Ausnahme** des Kanals, nicht `NotificationResult` — ein zweites Ergebnisfeld hätte ihn
strukturell nie erreicht. Die Basisklasse anzufassen hätte den von E-Mail, Telegram und SMS
geteilten Vertrag verändert, ohne etwas zu gewinnen: im generischen `except` braucht der
Aufrufer ohnehin `getattr(exc, "reason_code", None)`, weil es Ausnahmen ohne Kennung gibt
(HTTP-Störung, SMTP-Fehler). Der Klartext bleibt unverändert daneben stehen.

**Diese Ergänzung geht über die ursprünglich freigegebene Spec hinaus** und wurde am
2026-08-10 gesondert freigegeben. Auslöser war ein Hinweis der S2b-Session, nicht ein eigener
Fund — festgehalten, damit die Herkunft der Entscheidung nachvollziehbar bleibt.

**Nachtrag aus Adversary-Runde 1 (F002):** Die Kennung liegt zusätzlich als Ergebnisfeld
`NotificationResult.blocked_reason_codes` vor, gefüllt an **beiden** Sperrstellen (Briefing und
Wetterausfall-Hinweis). Bewusst **ohne Ersatzwert**: ein fehlender Eintrag *ist* die Aussage
„das war keine bewusste Sperre, sondern ein Fehler". Genau daran unterscheidet die AC-3-Prüfung
jetzt einen Zufallsabsturz von einer Sperre — vorher akzeptierte sie jede nicht-leere
Fehlermeldung als Grund, und der Adversary hat das mit einer Mutation ausgenutzt.

### Text unverändert aus `report.sms_text` (D5)

Kein eigener Render-Pfad, kein `premium_sms_text`-Feld. `PremiumSmsOutput`
bekommt denselben `body=report.sms_text or report.email_plain` wie der
bestehende SMS-Zweig (`notification_service.py:373`). Der Briefing-Pfad
liest `CHANNEL_LIMITS` (`channel_layout.py:45-49`) nicht — `trip_report.py:420`
übergibt `max_length=160` fest; die 153 dort sind die Segmentgrenze
**verketteter** SMS, hier irrelevant.

### Verfallsfrist als Modul-Konstante (D6, PO-Entscheid 2026-08-10)

`PREMIUM_SMS_REPLY_TTL = timedelta(days=30)` in `premium_sms.py`. Begründung
und Widerlegungsbedingungen: siehe Known Limitations.

### Eigenes Tier-Gate (D7)

`premium_sms_allowed(user_id)` prüft ausschließlich `tier == "premium"` —
keine Wiederverwendung von `sms_allowed()`, das `standard` **und** `premium`
durchlässt (`user_tier.py:6-14`). Wiederverwendung wäre eine stille
Rechte-Ausweitung.

### Kein Go-*Produktivcode* in S2a (D8)

**Präzisierung 2026-08-10:** Diese Entscheidung hieß zuerst „keine Go-Änderung". Wörtlich trifft
das nicht mehr zu — `internal/handler/fix_go_rmw_merge_1082_1103_test.go` hat **zwölf Zeilen**
bekommen (der neue Schlüssel im bestehenden Merge-Regressionstest). Das ist ein **Test**, kein
Struct und kein Handler; die Substanz der Entscheidung — kein neues Go-Feld, kein
`data_schema_backup.py`-Auslöser — bleibt unberührt. Der Test entstand als Beleg für die
Ganzobjekt-Frage (s. u.), nicht als Funktionsänderung.

`send_premium_sms` lebt als freier Schlüssel in `Trip.ReportConfig`
(`map[string]interface{}`, `trip.go:112`), überlebt Speichern/Laden über den
bestehenden feldweisen Merge (`config_merge.go:11-22`) ohne neues
Go-Struct-Feld. Ein Flach-Feld analog `SendSms`/`SendEmail`
(`trip.go:161-163`) ist reine Frontend-Bequemlichkeit und folgt erst mit S3.
Damit entfällt auch der `data_schema_backup.py`-Auslöser für diese Scheibe.

### Neuer Kanalname im ADR, vor dem Code (D9)

Reihenfolge laut Kontextdokument: (1) ADR — legt `premium_sms` fest, (2)
Settings-Datenebene, (3) Kanal-Code (Basisklasse + Premium + `sms.py`-Umbau,
ein Commit), (4) Verdrahtung (Scheduler, Tier-Gate, Modell/Loader), (5)
defensiver `CHANNEL_LIMITS`-Eintrag.

### ENV-Sperre gegen `GZ_PREMIUM_SMS_REPLY_TO`

`SettingsConfigDict(env_prefix="GZ_")` (`config.py:87`) gilt uniform für
jedes deklarierte Feld; `extra="ignore"` (`config.py:90`) verschluckt
undeklarierte Werte lautlos — `premium_sms_reply_to` muss aber deklariert
sein, sonst verschwindet der Profilwert selbst lautlos. Ein
`model_validator(mode="after")` prüft, ob `GZ_PREMIUM_SMS_REPLY_TO` im
Prozess-Environment gesetzt ist, und bricht dann die Konstruktion mit
`ValueError` ab — anders als `_resend_default_deny` (`:194-217`, stille
Umlenkung), weil die Vorgabe „niemals editierbar" strenger ist als die
Resend-Regel: ein stiller Reroute wäre hier selbst ein Verstoß gegen
„niemals".

## Expected Behavior

- **Input:** Trip-Briefing-Auslösung wie bisher (`Go-Scheduler →
  send_trip_report()`), kein neuer Trigger, kein neuer HTTP-Eingang.
- **Output:** bei aktivem `send_premium_sms`, Premium-Tier und einer
  gültigen, frischen (≤ 30 Tage) Rückadresse: ein POST an
  `gateway.seven.io` mit `from=4916092172595`, `to=<gelernte Adresse>`,
  `text=<report.sms_text>`. Sonst kein POST;
  `blocked_channels["premium_sms"]` trägt den Grund.
- **Side effects:** keine neue Persistenz, kein Schreiben irgendwo, keine
  Änderung an S1s Lernpfad. `sent_channels`/`blocked_channels` im
  `NotificationResult` sind die einzigen neuen beobachtbaren Zustände.

## Acceptance Criteria

- **AC-1:** Given ein Premium-Nutzer hat eine gültige, frische gelernte Rückadresse UND `sms_from`/`GZ_SMS_FROM` sind bewusst auf eine andere Nummer gesetzt / When das Trip-Briefing über Premium-SMS versendet wird / Then trägt die tatsächlich abgesendete Nachricht als Absender ausnahmslos die feste Nummer `4916092172595` — die abweichende `sms_from`-Einstellung hat keinerlei Wirkung auf den Premium-Kanal.
  - Prüfort: `payload["from"]` am lokalen HTTP-Stub (Vorbild `tests/tdd/test_issue_936_sms_stub.py`), NICHT das Settings-Objekt — die Zusicherung wirkt am ausgehenden POST, nicht am Konstruktor.
  - Test: `tests/unit/test_premium_sms_versand.py::test_sender_is_fixed_number_regardless_of_sms_from`

- **AC-2:** Given die gelernte Rückadresse eines Premium-Nutzers steht in dessen `user.json` UND `Settings.sms_to`/`GZ_SMS_TO` sind im selben Testlauf auf eine andere Nummer gesetzt / When das Briefing über Premium-SMS versendet wird / Then geht die Nachricht ausschließlich an die gelernte Rückadresse — `sms_to` wird für diesen Kanal an keiner Stelle gelesen.
  - Prüfort: `payload["to"]` am HTTP-Stub, mit `GZ_SMS_TO` im Prozess-Environment bewusst widersprüchlich gesetzt.
  - Test: `tests/unit/test_premium_sms_versand.py::test_recipient_comes_from_learned_reply_to_not_sms_to`

- **AC-3:** Given ein Premium-Nutzer hat noch keine gelernte Rückadresse (`premium_sms_reply_to` leer) / When das Trip-Briefing versendet wird / Then geht keine Premium-SMS hinaus, kein HTTP-Aufruf findet statt, und der Grund ist im Versandergebnis unter dem Kanalnamen `premium_sms` als auswertbarer Text hinterlegt — nicht nur in einer Logzeile.
  - Prüfort: doppelt gemessen — (a) der HTTP-Stub bleibt komplett unbenutzt (`stub.received == []`), (b) `NotificationResult.blocked_channels["premium_sms"]` ist gesetzt. Nur beide Messpunkte zusammen beweisen „ausbleibender Versand UND sichtbarer Grund".
  - Test: `tests/unit/test_premium_sms_versand.py::test_empty_reply_to_blocks_send_with_visible_reason`

- **AC-4:** Given ein Premium-Nutzer hat eine gelernte Rückadresse, deren Zeitstempel exakt eine Sekunde über der 30-Tage-Frist liegt / When das Briefing versendet wird / Then geht keine Premium-SMS hinaus und der Grund benennt die veraltete Rückadresse — unabhängig davon, dass die Nummer selbst syntaktisch gültig aussieht.
  - Prüfort: wie AC-3, mit einer Fixture-`user.json`, deren `premium_sms_reply_at` bewusst auf `jetzt − 30 Tage − 1 Sekunde` gesetzt ist.
  - Test: `tests/unit/test_premium_sms_versand.py::test_reply_to_older_than_ttl_blocks_send`

- **AC-5:** Given ein Premium-Nutzer hat eine gelernte Rückadresse, deren Zeitstempel exakt eine Sekunde unter der 30-Tage-Frist liegt / When das Briefing versendet wird / Then geht die Premium-SMS regulär hinaus — die Frist blockiert nicht vorsorglich früher als spezifiziert.
  - Prüfort: derselbe Stub, Fixture mit `premium_sms_reply_at = jetzt − 30 Tage + 1 Sekunde`. Zusammen mit AC-4 beweist dieser Kantentest, dass die Frist exakt bei 30 Tagen liegt, nicht ungefähr.
  - Test: `tests/unit/test_premium_sms_versand.py::test_reply_to_just_within_ttl_still_sends`

- **AC-6:** Given ein Trip-Briefing mit einer Extremwetter-Fixture (viele Warnungen/Token im SMS-Text) wird für einen Premium-Nutzer mit gültiger Rückadresse gerendert / When es über Premium-SMS versendet wird / Then ist der tatsächlich abgesendete Text bitidentisch mit `report.sms_text` und nicht länger als 160 Zeichen.
  - Prüfort: `payload["text"]` am HTTP-Stub, verglichen mit dem von `TripReportFormatter.format_email()` tatsächlich erzeugten `report.sms_text` derselben Fixture — nicht mit einer im Test hart codierten Erwartungskonstante, sonst bliebe ein gemeinsamer Kopierfehler in Renderer und Test unentdeckt.
  - Test: `tests/unit/test_premium_sms_versand.py::test_text_matches_sms_text_verbatim_under_extreme_weather`

- **AC-7:** Given der Testcode läuft — wie jeder pytest-Lauf in einem Arbeitsordner — aus einer Testlauf-Herkunft (die Herkunftssperre vergleicht die Checkout-Wurzel **exakt** mit `/home/hem/gregor_zwanzig`, ein Worktree darunter gilt deshalb als Testlauf) / When Premium-SMS gesendet wird / Then wird ausschließlich der Sandbox-Key verwendet, und ist kein Sandbox-Key konfiguriert, bricht der Versand laut ab, bevor ein HTTP-Aufruf stattfindet — exakt wie beim bestehenden SMS-Kanal.
  - Prüfort: `X-Api-Key`-Header am HTTP-Stub (Sandbox-Fall) bzw. `OutputConfigError` vor jedem Stub-Aufruf (Fehlerfall) — Vorbild `tests/tdd/test_channel_origin_guard_parity.py:131-144`, dort um `PremiumSmsOutput` erweitert.
  - Test: `tests/tdd/test_channel_origin_guard_parity.py::test_premium_sms_test_origin_switches_to_sandbox_key`, `::test_premium_sms_test_origin_without_sandbox_key_hard_aborts`

- **AC-8:** Given ein Nutzer hat Tier `standard` (nicht `premium`) UND `send_premium_sms` ist in seinem Trip aktiviert / When das Briefing-Versandfenster prüft, ob Premium-SMS gesendet werden darf / Then wird keine Premium-SMS versendet, obwohl derselbe Nutzer für den normalen SMS-Kanal (`sms_allowed`) als berechtigt gilt.
  - Prüfort: End-zu-Ende gegen den HTTP-Stub mit einer `standard`-Tier-Fixture — der Stub darf keinen Request erhalten; zusätzlich eine reine Funktionsprüfung von `premium_sms_allowed("standard") is False` als zweiter, günstigerer Messpunkt.
  - Test: `tests/unit/test_user_tier.py::test_premium_sms_allowed_excludes_standard_tier`, `tests/unit/test_premium_sms_versand.py::test_standard_tier_never_triggers_premium_sms_send`

- **AC-9:** Given im Prozess-Environment ist `GZ_PREMIUM_SMS_REPLY_TO` **oder** `GZ_PREMIUM_SMS_REPLY_AT` gesetzt (Versuch, die gelernte Rückadresse oder deren Alter per Umgebungsvariable zu überschreiben) / When `Settings()` konstruiert wird / Then schlägt die Konstruktion laut fehl, statt den Wert stillschweigend zu übernehmen — die gelernte Rückadresse und ihr Zeitstempel bleiben ausschließlich über `user.json` erreichbar.
  - Prüfort: die `Settings(...)`-Konstruktion selbst, je Variable ein eigener Fall — der Prüfort ist der Konstruktionszeitpunkt, nicht ein späterer Sendeversuch, weil ein still akzeptierter Wert sonst erst beim nächsten Versand sichtbar würde.
  - **Beide Variablen, nicht nur der Empfänger:** Ein Override des Zeitstempels würde die 30-Tage-Frist künstlich auffrischen und damit den Versand an eine längst veraltete Nummer freigeben. Die Nummer wäre dabei formal korrekt, die Sperre aus AC-4 aber wirkungslos — eine Sperre, die man mit einer Umgebungsvariable abschalten kann, ist keine.
  - Test: `tests/unit/test_config_premium_sms.py::test_env_override_for_reply_to_is_rejected_loudly`, `::test_env_override_for_reply_at_is_rejected_loudly`

- **AC-10:** Given ein Nutzer hat `send_sms=false` und `send_premium_sms=true` (oder umgekehrt) / When das Briefing versendet wird / Then wird ausschließlich der jeweils aktivierte Kanal tatsächlich angesprochen — Premium-SMS ist vom bestehenden SMS-Kanal vollständig unabhängig schaltbar, keiner setzt den anderen voraus oder schließt ihn ein.
  - Prüfort: HTTP-Stub gegen `send_trip_report()` mit allen vier Kombinationen aus `send_sms`/`send_premium_sms`, unterschieden am `to`-Wert der eingegangenen Requests (beide Kanäle senden an dieselbe seven.io-URL).
  - Test: `tests/unit/test_premium_sms_versand.py::test_premium_sms_and_sms_are_independently_switchable`

## Nachweisgrenzen — was diese Scheibe NICHT beweist

Dass die Premium-SMS tatsächlich auf dem Garmin-Gerät ankommt und dort lesbar
ist, ist mit den Mitteln dieser Scheibe **strukturell nicht** beweisbar:

- Die Herkunftssperre (`origin_guard.running_origin()`) stuft jeden Pfad
  außer `/home/hem/gregor_zwanzig` als Testlauf ein und erzwingt dann den
  Sandbox-Key, der laut seven.io-Dokumentation nie eine echte SMS sendet und
  nie kostet (AC-7 prüft genau diesen Mechanismus, nicht seine Umgehung).
- `force_test` (`config.py:292-293`) sandboxiert Staging zusätzlich — jede
  „Zustellung" dort ist folglich kein Beweis.
- Der Staging-Scheduler führt derzeit keinen einzigen Job aus (`last_run:
  null` für alle zehn Jobs, gemessen) — selbst ein scharf geschalteter
  Versand würde auf Staging nie automatisch ausgelöst.
- Ein bestandener Testlauf dieser Spec bedeutet ausschließlich: Nutzlast
  korrekt, Empfänger korrekt aufgelöst, Fail-Closed wirksam, Guards greifen —
  **nicht** „kommt auf dem Gerät an".

Dieser Nachweis ist ausdrücklich als **SKIPPED** auszuweisen (nicht als
bestanden zu behaupten) und gehört in **#1533** (Generalprobe, Frist 20.8.).

## Mutations-Gegenprobe

Pflicht laut Projektregel — je AC eine gezielte Verfälschung, die mindestens
einen Test rot machen MUSS:

| AC | Gezielte Verfälschung | Test, der dadurch rot werden MUSS |
|---|---|---|
| AC-1 | `_resolve_sender()` liefert `self._settings.sms_from` statt der festen Nummer | `test_sender_is_fixed_number_regardless_of_sms_from` |
| AC-2 | `_resolve_recipient()` liest `self._settings.sms_to` statt `premium_sms_reply_to` | `test_recipient_comes_from_learned_reply_to_not_sms_to` |
| AC-3 | Fail-Closed-Prüfung in `_resolve_recipient()` entfernt (leerer String wird durchgereicht) | `test_empty_reply_to_blocks_send_with_visible_reason` — Stub bekommt plötzlich einen Request |
| AC-4/5 | `PREMIUM_SMS_REPLY_TTL` von 30 auf z. B. 300 Tage geändert | `test_reply_to_older_than_ttl_blocks_send` schlägt fehl, weil jetzt trotzdem gesendet wird — der Kantentest deckt genau diese Verschiebung auf |
| AC-6 | Sendezweig übergibt `report.email_plain` statt `report.sms_text` | `test_text_matches_sms_text_verbatim_under_extreme_weather` |
| AC-7 | `PremiumSmsOutput.send()` ruft `_guard_code_origin()` beim Erben nicht auf (Copy-Paste-Fehler) | `test_premium_sms_test_origin_without_sandbox_key_hard_aborts` |
| AC-8 | `premium_sms_allowed()` delegiert an `sms_allowed()` statt eigener Tier-Prüfung | `test_premium_sms_allowed_excludes_standard_tier` |
| AC-9 | ENV-Sperre-Validator entfernt/deaktiviert | `test_env_override_for_reply_to_is_rejected_loudly` |
| AC-10 | Sendezweig prüft `request.send_sms or request.send_premium_sms` (ODER statt unabhängig) | `test_premium_sms_and_sms_are_independently_switchable` |

## Known Limitations

- **Die 30-Tage-Frist ist eine begründete Setzung, kein Messwert (D6).**
  Widerlegt durch: (a) reale Touren länger als 30 Tage — dann müsste die
  Frist trip-gebunden statt fix sein; (b) ein Messwert, dass seven.io/Garmin
  die Rufnummer schneller (oder deutlich langsamer) neu vergibt als
  angenommen. Ohne eine solche Messung bleibt 30 Tage der PO-entschiedene
  Wert (2026-08-10).
- **Der `sms.py`-Refactor auf die gemeinsame Basisklasse ist das einzige
  Bestandsrisiko dieser Scheibe** — er berührt den produktiven
  SMS-Versandweg. Abgesichert durch die bestehende SMS-Testsuite (u. a.
  `test_channel_origin_guard_parity.py`), die unverändert grün bleiben muss;
  `SMSOutput.send()` darf sich im Verhalten nicht ändern, nur in der
  internen Struktur.
- **Die ENV-Sperre deckt beide Felder ab** (`GZ_PREMIUM_SMS_REPLY_TO` und
  `GZ_PREMIUM_SMS_REPLY_AT`, AC-9). Sie wurde beim Schreiben der Spec
  bewusst über die wörtliche PO-Vorgabe („Empfänger niemals aus der
  Konfiguration") hinaus auf den Zeitstempel ausgedehnt, weil eine
  Verfallsfrist, die per Umgebungsvariable auffrischbar ist, keine Sperre
  wäre. Nicht abgedeckt bleibt der Fall, dass jemand die Datei `user.json`
  direkt bearbeitet — das ist Dateisystem-Zugriff auf dem Server und liegt
  außerhalb dessen, was ein Anwendungs-Wächter leisten kann.
- **Kein Frontend, keine Sichtbarkeit für den Nutzer.** `send_premium_sms`
  ist in dieser Scheibe nirgends im UI schaltbar (folgt in S3).
- **Go bleibt unverändert (D8).** `send_premium_sms` lebt ausschließlich im
  freien `report_config`-Feld, noch kein eigenes Struct-Feld.
- **Der `CHANNEL_LIMITS`-Eintrag ist reine Vorsorge.** Der Briefing-Pfad
  liest ihn nicht (s. Implementation Details) — relevant erst, sobald ein
  künftiger Aufrufer (S3, Vergleichspfad) den Kanal dort nachschlägt.
- **Der S1-Lern-/Rückkanal-Mechanismus ist unverändert** und wird von dieser
  Scheibe nicht erneut geprüft — die dortigen ACs bleiben die alleinige
  Grundlage für „gelernte Rückadresse korrekt".

## Test Coverage

- `tests/unit/test_premium_sms_versand.py` — echter lokaler HTTP-Stub
  (`http.server` auf `127.0.0.1`, Vorbild `test_issue_936_sms_stub.py`), kein
  Mock, kein `patch()`:
  - `test_sender_is_fixed_number_regardless_of_sms_from` (AC-1)
  - `test_recipient_comes_from_learned_reply_to_not_sms_to` (AC-2)
  - `test_empty_reply_to_blocks_send_with_visible_reason` (AC-3)
  - `test_reply_to_older_than_ttl_blocks_send` (AC-4)
  - `test_reply_to_just_within_ttl_still_sends` (AC-5)
  - `test_text_matches_sms_text_verbatim_under_extreme_weather` (AC-6)
  - `test_standard_tier_never_triggers_premium_sms_send` (AC-8)
  - `test_premium_sms_and_sms_are_independently_switchable` (AC-10)
- `tests/unit/test_config_premium_sms.py`:
  - `test_env_override_for_reply_to_is_rejected_loudly` (AC-9)
  - Settings-Feld-Deklaration, `with_user_profile()`-Übernahme
- `tests/unit/test_user_tier.py` (MODIFY):
  - `test_premium_sms_allowed_excludes_standard_tier` (AC-8)
- `tests/tdd/test_channel_origin_guard_parity.py` (MODIFY):
  - `test_premium_sms_test_origin_switches_to_sandbox_key` (AC-7)
  - `test_premium_sms_test_origin_without_sandbox_key_hard_aborts` (AC-7)

Testdateien liegen bewusst unter `tests/unit/` (Ausnahme: die Erweiterung
der bestehenden `tests/tdd/test_channel_origin_guard_parity.py`) —
`touched_tests_gate.py:37` sucht nur unter `tests/unit/`. Namen nach
Verhalten, nicht nach Issue-Nummer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** **0049** — `docs/adr/0049-premium-sms-vierter-kanal.md`
  (nächste freie Nummer, gemessen: höchster Bestand ist 0048).
- **Rationale:** ADR-0004 legt fest: „Die unterstützten Kanäle sind nur noch
  E-Mail · Telegram · SMS." Die PO-Vorgabe verlangt Premium-SMS als eigenen,
  vierten Kanal `premium_sms` — nach CLAUDE.md-Regel „Abweichung ⇒ neues
  ADR" schreibt das neue ADR ADR-0004 in diesem Punkt fort, statt es
  stillschweigend zu unterlaufen. Es legt den Kanalnamen fest, **bevor** der
  Code ihn trägt (Reihenfolge-Punkt 1).

## Changelog

- 2026-08-10: Initial spec erstellt — Issue #1676, Scheibe S2a
  (Trip-Briefing als Premium-SMS)
