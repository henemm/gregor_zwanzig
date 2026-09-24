# Kontext: Issue #2153 Scheibe S4 — Tageslimit für SMS und Premium-SMS je Nutzer

> Analyse-Dokument für `/30-write-spec`. Keine Implementierung, keine Spec-Datei.
> Workflow: `feat-2153-s4-sms-tageslimit` (Epic #2138, Sammel-Issue #2153, Sub-Issue #2412).
> Erhoben 2026-09-24 im Worktree `splendid-forging-orbit`, Stand `origin/main` 84b50d72.

## 0. Auftrag

Tageslimit für SMS und Premium-SMS je Nutzer — Briefing-SMS + Alarm-SMS zusammen
gezählt, Zähler sichtbar im Konto (`/account`). Heute: nur proaktive Alarme sind
gedeckelt (`src/services/user_tier.py:45-64`, free 2 / standard 4 / premium ∞,
kanalunspezifisch), Briefing-SMS ungedeckelt, Premium-SMS ohne Deckel. S5
(Quoten je Tier für Trips/Orte) ist ausdrücklich NICHT Teil dieser Scheibe.

## 1. Bestand — wer sendet heute worüber

### 1.1 Tatsächliche Sendeaufrufe (`.send()` auf `SMSOutput`/`PremiumSmsOutput`)

Alle produktiven Sendeaufrufe liegen in EINER Datei, `src/services/notification_service.py`
(12 Aufrufstellen; `self._user_id`/`self._require_user()` bereits vorhanden,
`notification_service.py:439-462`):

| Methode | Zeilen | Kategorie |
|---|---|---|
| `send_trip_report` | 600, 618 | Briefing (Trip) |
| `send_no_data_hint` | 769, 776 | Briefing-Variante (Trip) |
| `send_compare_report` | 1257 (nur SMS) | Briefing (Vergleich) |
| `send_official_alert` | 1146, 1159 | Alarm (Trip) |
| `send_multi_location_official_alert` | 1448, 1467 | Alarm (Vergleich) |
| `send_radar_alert` | 1783, 1797 | Alarm (Trip) |
| `send_command_reply_premium_sms` | 1834 | Eingehende Antwort (Garmin, kostet ebenfalls) |

`send_compare_report` sendet bewusst KEIN Premium-SMS — CLAUDE.md: „Premium-SMS
als Versandkanal nur im Trip-Briefing verdrahtet (kein Ortsvergleich-Versand)."

Außerhalb des Produktivpfads, empfohlen außerhalb dieser Scheibe:

- `api/routers/internal.py:174-197` (`send_sms_verification_code`, S3/#2406) —
  eigene Mengenbremse (3/h je Nutzer) aus S3, einmaliger Vorgang je
  Nummernwechsel, kein laufender Betrieb.
- `src/app/cli.py` (Legacy-CLI) — laut CLAUDE.md Debug-Werkzeug, kein
  Produktivpfad.

### 1.2 Warum `SevenIoChannelBase.send()` NICHT der Gate-Punkt ist

`SevenIoChannelBase.__init__(self, settings: Settings)` (`seven_io_base.py:58-60`)
kennt keinen `user_id`. `Settings.with_user_profile(user_id)`
(`src/app/config.py:394-420`) lädt userbezogene Felder (u.a. `sms_to`), hält
`user_id` aber nicht als eigenes Attribut fest. Ein Gate in der Transport-Basis
würde `user_id`-Threading durch `Settings` erfordern — größerer struktureller
Eingriff als nötig. Empfehlung: Gate an den 12 Aufrufstellen in
`notification_service.py`, konsolidiert auf 1-2 private Hilfsmethoden
(`_send_sms`/`_send_premium_sms`).

### 1.3 Drei verstreute Tier-Gate-Stellen (heute: "wird der Kanal versucht", nicht "wie oft")

- `src/services/alert_channels.py:89-92` — geteilte Alarm-Kanal-Auflösung
  (Trip + Vergleich, `resolve_alert_channels`/`effective_alert_channels`).
- `src/services/compare_alert_channels.py:49-52` — Vergleichs-Briefing
  (`effective_compare_briefing_channels`).
- `src/services/trip_report_scheduler.py:1766-1780` — Trip-Briefing, EIGENE
  Funktion (`_effective_channels`), delegiert NICHT an die geteilte
  Alarm-Auflösung aus 1.

Alle drei prüfen `sms_allowed`/`premium_sms_allowed` (`user_tier.py:9-42`)
unabhängig voneinander — ein neues Tageslimit müsste NICHT zwingend an all
diesen drei Stellen ansetzen, wenn stattdessen am Sendepunkt
(`notification_service.py`) gegated wird; die drei Resolver bleiben unverändert
zuständig für "welcher Kanal ist fachlich aktiv", das neue Gate für
"wie oft heute schon gesendet".

### 1.4 Bauvorbilder

- **Zähler-Mechanik:** `src/services/alert_daily_limit.py` — atomarer
  Read-Modify-Write (`tempfile` + `os.replace`), Datei
  `<get_data_dir(user_id)>/alert_daily_count.json`, Reset am Kalendertag-Wechsel
  IN EINER ZONE je Objekt (bewusste Vervielfachung bei mehreren Zonen,
  Kommentar Z. 9-14). Zählt aber ALLE Alarme kanalunspezifisch, nicht SMS-spezifisch.
- **UTC-getakteter Kosten-Deckel:** `api/routers/internal.py:116-128`
  (`_sekunden_bis_utc_mitternacht`, `ForecastBudgetGate`) — Reset an der
  UTC-Mitternacht. Passender Präzedenzfall für einen reinen Kosten-Zähler ohne
  Wetter-Fachbezug (s. offene Frage 3).
- **Reserve-Mechanik gegen Erschöpfung vor dem Ernstfall:** `_FORECAST_CHANGE_RESERVE`
  (`alert_daily_limit.py:100-105`, #1555) und `_MAX_ESCALATION_BREAKTHROUGHS`
  (`alert_daily_limit.py:126-130`, #2050 S3b) — Vorbild für eine Alarm-Reserve
  im neuen SMS-Zähler (offene Frage 2).

## 2. ADR-Bezug

- **ADR-0031** (`docs/adr/0031-persistenz-dateibasiert-data-users.md`): Kontext
  sagt „Go-API ist der einzige Schreiber, Python liest". `alert_daily_limit.py`
  schreibt bereits seit #1213/#1726 Throttle-Dateien unter `data/users/<id>/` —
  Spannung zur gelebten Praxis, keine Blockade. Ob ein ADR-Zusatz nötig ist,
  entscheidet die Spec-Phase.
- **ADR-0049** (Premium-SMS als 4. Kanal): Punkt 5 „Eigenes Tier-Gate"
  (`premium_sms_allowed()`, ausschließlich `premium`) bleibt unberührt. Das neue
  Tageslimit ist ein ZUSÄTZLICHES Mengen-Gate. Offene Frage 1: ein gemeinsamer
  oder zwei getrennte Zähler (SMS vs. Premium-SMS)?

## 3. /account-Anbindung (Go-API ↔ Python-Core)

- Go-Profil (`internal/handler/auth.go:780-831`, `toProfileResponse`/
  `GetProfileHandler`) dupliziert die Tier-Gates bereits read-only für die
  Anzeige (`internal/model/user.go`: `model.SmsAllowed`, `model.PremiumSmsAllowed`).
- Etabliertes Cross-Prozess-Muster „Go fragt Python nach computed state":
  `POST /api/_internal/sms/verification-code` (S3/#2406),
  `internal/handler/telegram_webhook.go:36-63` (`pythonCoreURL`).
- Empfehlung: neuer, EIGENSTÄNDIGER Endpoint `GET /api/_internal/sms/daily-usage`
  in Python, von Go gelesen — NICHT in `GetProfileHandler` eingebettet, damit
  `/account` auch lädt, wenn Python-Core down ist.
- Frontend liest bereits `data.profile` mit SMS-Feldern
  (`frontend/src/routes/account/+page.svelte:27-34`) — dort wäre der Zähler zu
  ergänzen.

## 4. Vorschlag: Schnitt in zwei Unterscheiben

Begründung: 12 Sendeaufrufstellen (auch wenn in einer Datei) + neues Zähler-Modul
+ Limitwerte + Go/Frontend-Sichtbarkeit sprengen 4-5 Dateien/250 LoC in einem
Workflow.

- **S4a — Durchsetzung (Python, Kern-Gate):** `src/services/sms_daily_limit.py`
  (neu, Musterbaustein `alert_daily_limit.py`, UTC-Tagesgrenze statt Pro-Zone),
  Limitwerte in `src/services/user_tier.py`, Konsolidierung der 12 Sendeaufrufe
  in `notification_service.py` auf 1-2 private Hilfsmethoden, inkl.
  `send_command_reply_premium_sms`. Enforcement vollständig, Sichtbarkeit
  zunächst nur Log/`blocked_channels`.
- **S4b — Sichtbarkeit im Konto:** `GET /api/_internal/sms/daily-usage`
  (`api/routers/internal.py`), Go-Anbindung (`internal/handler/auth.go`, ggf.
  `internal/model/user.go`), Frontend (`frontend/src/routes/account/+page.svelte`).
  Baut auf S4a auf. Zwei-Nutzer-Test PFLICHT (CLAUDE.md).

## 5. Offene Produktfragen mit Tech-Lead-Empfehlung (PO-Bestätigung nötig)

1. **Ein gemeinsamer Zähler (SMS+Premium-SMS gepoolt) oder zwei getrennte?**
   Empfehlung: **zwei getrennte** Zähler, je einer summiert Briefing+Alarm für
   seinen Kanal. Begründung: ADR-0049 führt Premium-SMS bewusst als
   eigenständigen Kanal mit eigenem Tier-Gate ein, um Rechte-/Kosten-Vermischung
   zu vermeiden — ein gepoolter Zähler würde das unterlaufen (ein Premium-Nutzer
   mit vielen Garmin-Alarmen würde sonst auch seine normale SMS blockieren).
2. **Verhalten bei Erreichen — mit Alarm-Reserve.** Empfehlung: betroffener
   Kanal wird für diesen Versand NICHT ausgeführt (fail-closed mit sichtbarem
   Grund, neuer `reason_code` `sms_daily_limit_exceeded` im
   `blocked_channels`-Ergebnis, analog ADR-0049 Punkt 4). E-Mail/Telegram
   bleiben unberührt (CLAUDE.md: „Alarme müssen alle Kanäle erreichen", #1701).
   Zusätzlich eine Alarm-Reserve analog `_FORECAST_CHANGE_RESERVE`/
   `_MAX_ESCALATION_BREAKTHROUGHS`, damit ein frühes Briefing das Kontingent
   nicht vor einem späteren Gewitteralarm aufbraucht (auf der Hütte kann
   SMS/Premium-SMS der einzige tragende Kanal sein). KEINE zusätzliche
   proaktive Hinweis-Nachricht beim Erreichen — der Zähler in /account (S4b)
   ist der passive Hinweisweg.
3. **Zeitzone des Tageswechsels — UTC.** Empfehlung: fester Reset an der
   UTC-Mitternacht, analog `ForecastBudgetGate`. Begründung: `alert_daily_limit.py`
   ist an ein Wetter-Zielobjekt gebunden und akzeptiert bewusst Vervielfachung
   bei mehreren Zonen — bei einem Kosten-Deckel pro Nutzerkonto wäre das der
   unerwünschte Effekt. Kein Widerspruch zur Lehre aus #1726 („zone ist
   PFLICHT"): jene Lehre betrifft eine GERATENE Zone für einen wetterfachlichen
   Wert; UTC ist hier eine explizit gewählte Referenz für einen reinen
   Kosten-Zähler ohne Wetter-Fachbezug.
4. **Limitwerte je Tier (je Kanal, pro Kalendertag).** Ausgangspunkt für die
   Spec: `free` faktisch 0 (kein SMS-Zugriff ohnehin), `standard` 10 SMS/Tag,
   `premium` 10 SMS/Tag + 15 Premium-SMS/Tag. Feinjustierung in der Spec-Phase.

## 6. Ausdrücklich außerhalb dieser Scheibe

- S5 (Quoten je Tier für Trips/Ortsvergleiche/Orte/Empfängerkanäle aus #2153).
- SMS-Verifikationscode-Versand (`api/routers/internal.py:174`, eigene
  Mengenbremse aus S3).

## 7. Bestehende Specs (Nachtrag Phase 1)

- `docs/specs/modules/alert_daily_limit.md` — Bauvorbild Zähler (Alarm-Tageslimit je Nutzer)
- `docs/specs/modules/epic_user_tiers_overview.md` — Tier-Modell free/standard/premium
- `docs/specs/modules/sms_nummer_verifikation.md` — S3 (#2406), Vorbedingung für SMS-Versand
- `docs/specs/modules/account_page.md`, `account_page_extend.md` — Ort des Zählers (S4b)
- `docs/specs/modules/egress_guard_sms.md`, `fix_2323_premium_sms_gate_generisch.md` — bestehende Versand-Wächter, die das neue Limit NICHT ersetzen darf

## 8. Dependents / Tests, die den Bestand bewachen

Kerntests rund um Tier-Gate und Alarm-Tageslimit, die beim Umbau grün bleiben müssen:
`tests/tdd/test_issue_1070_daily_alert_limit.py`, `test_issue_1069_tier_channel_gating.py`,
`test_ruhezeit_und_zaehler_folgen_der_ortszone.py`, `test_alarm_szenario_tagesbezug_zeitzone.py`,
`test_alarm_szenario_mandantentrennung.py`, `test_compare_alert_channel_delivery.py`,
`test_compare_dispatch_channel_fanout.py`, `test_914_slice4_alert_sms_dispatch.py`,
`test_kanaltreue_adhoc_antwort.py`.

## 9. Risiken

- 🔴 **Tageswechsel-Zone:** Der bestehende Alarm-Zähler folgt nachweislich der **Ortszone**
  (`test_ruhezeit_und_zaehler_folgen_der_ortszone.py`). Die Empfehlung „UTC" für den SMS-Kostendeckel
  weicht davon ab — in `/20-analyse` gegen die Entscheidung hinter diesem Test prüfen, bevor sie in die Spec geht.
- Zwei Limits nebeneinander (Alarm-Tageslimit je Tier + neuer SMS-Tagesdeckel) — Wechselwirkung und
  Reihenfolge der Prüfung klären, sonst doppelte bzw. widersprüchliche Unterdrückungsgründe im Journal.
- Eingehende Antwort-SMS (`notification_service.py:1834`, Ad-hoc-Antwort) zählt sie mit? Kanaltreue-Regel beachten.
- Mandantentrennung: Zähler strikt je `user_id`, Zwei-Nutzer-Test Pflicht.
- ADR-0031 (Python schreibt in `data/users`) — bestehende Spannung durch `alert_daily_limit.py`, nicht verschärfen ohne Begründung.

## Analysis

> Phase 2, 2026-09-24. Verbindlich für `/30-write-spec` — wo dieser Abschnitt vom Issue-Text
> #2412 oder von §1–§9 oben abweicht, gilt **dieser Abschnitt**.

### Type
Feature (Kostenschutz, Epic #2138 / Sammel-Issue #2153, Scheibe S4 = #2412).

### PO-Entscheidungen (2026-09-24, per Rückfrage beantwortet)

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Premium-SMS trotz „Premium: kein Tageslimit" (PO 2026-07-07) deckeln? | **Ja** — Kosten-Deckel NUR für den Kanal Premium-SMS; E-Mail/Telegram bleiben für Premium unbegrenzt. Die Entscheidung vom 07.07. (Alarm-FREQUENZ, kanalübergreifend) bleibt bestehen; Nachtrag in `docs/specs/modules/epic_user_tiers_overview.md:26` nötig. |
| E2 | Tageswechsel | **UTC-Mitternacht** (= 02:00 MESZ / 01:00 MEZ). Begründung wie ADR-0075:119 (Kostenbezug, nicht Nutzerkalender); verhindert Kontingent-Vervielfachung über mehrere Ortszonen. ADR-0044 nennt Tagesgrenzen eine Produktentscheidung (Z.22) — **Zusatz in ADR-0044 („Nicht betroffen")** nötig, damit `test_ruhezeit_und_zaehler_folgen_der_ortszone.py` nicht als Gegenargument gilt. §9 Risiko 1 ist damit entschieden. |
| E3 | Limitwerte / Zähler | **Zwei getrennte Zähler** `sms` und `premium_sms`, je Briefing+Alarm summiert. `free` 0 (ohnehin kein SMS-Zugriff), `standard` 10 SMS/Tag, `premium` 10 SMS/Tag + 15 Premium-SMS/Tag. |
| E4 | Garmin-Antwort (`send_command_reply_premium_sms`) bei erreichtem Limit | **Kleine Extra-Reserve**: zählt mit, darf das Premium-SMS-Limit um eine kleine feste Zusatzmenge (Vorschlag 3/Tag) überschreiten, danach gesperrt. |

Alarm-Reserve (Tech-Lead-Default, keine PO-Frage): Briefings dürfen nur bis `limit − reserve`
belegen, Alarme bis `limit` (Muster `_FORECAST_CHANGE_RESERVE`, `alert_daily_limit.py:100-105`).
Vorschlag Reserve: 2 von 10 (SMS), 3 von 15 (Premium-SMS). **Begründung (korrigiert):** Die
Empfangslage unterwegs ist unvorhersehbar (CLAUDE.md, PO-Korrektur 2026-09-05) — jeder Kanal muss
jede Frage beantworten können; ein früh am Tag aufgebrauchtes Kontingent darf einen späteren Alarm
auf diesem Kanal nicht stumm machen. Die frühere Begründung in §5.2/#2412 („auf der Hütte ist
SMS/Premium-SMS der einzige tragende Kanal") ist vom PO widerrufen und darf NICHT in die Spec.

### Scope dieses Workflows: NUR S4a (Durchsetzung)
S4b (Zähler im Konto: `GET /api/_internal/sms/daily-usage` + Go-Profil + `/account`-Anzeige,
Zwei-Nutzer-Test, `resets_at` in UTC mitliefern) wird **eigener Workflow**. Folge für `/70`:
**#2412 und #2153 bleiben nach diesem Deploy OFFEN** (S4b ausstehend) — kein `gh issue close`,
stattdessen Stand-Kommentar auf #2412.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/sms_daily_limit.py` | CREATE | Zähler je Nutzer, zwei Töpfe (`sms`/`premium_sms`), UTC-Tag, Datei `sms_daily_count.json` im Nutzer-Datenordner (`get_data_dir(user_id)`); Lock über `src/services/file_lock.py` (`acquire_exclusive`, wie `forecast_budget.py`/`throttle_store.py`) — NICHT das `os.replace`-only-Muster aus `alert_daily_limit.py` (dort Read-Modify-Write ungeschützt → Limit um 1 überschreitbar). API etwa `check(user_id, kind, purpose, now)` / `record(user_id, kind, now)`, `purpose ∈ {briefing, alert, reply}`. |
| `src/services/user_tier.py` | MODIFY | Limitwerte je Tier/Kanal + Reserven (E3/E4). |
| `src/services/notification_service.py` | MODIFY | Dünnes Gate an allen 12 Sendestellen (s.u.); neuer Reason-Code `sms_daily_limit_exceeded`. |
| `tests/tdd/test_sms_tageslimit*.py` | CREATE | Verhaltens-Tests (Kern): Zwei-Nutzer-Isolation, UTC-Grenze, Reserve, Garmin-Zusatzmenge, E-Mail/Telegram unberührt. |
| `docs/adr/0044-…md`, `docs/specs/modules/epic_user_tiers_overview.md` | MODIFY (Doku) | Zusatz E2 bzw. Nachtrag E1 — zählt nicht ins LoC-Limit. |

### Sendestellen (verifiziert, `notification_service.py`)
- SMS: 600 (`send_trip_report`), 769 (`send_no_data_hint`), 1146 (`send_official_alert`),
  1257 (`send_compare_report`), 1448 (`_dispatch_compare_official_sms`), 1783 (`_dispatch_alert_message`/Radar).
- Premium-SMS: 618, 776, 1159, 1467, 1797, 1834 (`send_command_reply_premium_sms`; Aufrufer
  `src/services/inbound_sms_reader.py:361,383` bauen `NotificationService(..., user_id=user_id)` — echter Nutzer, kein `"default"`).
- Einordnung: Briefing = `send_trip_report`/`send_no_data_hint`/`send_compare_report`;
  Alarm = `send_official_alert`/Compare-Official/Radar; Antwort = Command-Reply.
- Außerhalb: `api/routers/internal.py:195` (Verifikationscode; eigene Bremse in Go, in-memory 3/h) und Legacy-CLI.

### Technical Approach (Entscheidungen, überstimmen Issue-Text)
1. **KEINE Konsolidierung der 12 Stellen auf 1–2 Sende-Helfer.** Die Stellen haben vier
   verschiedene Fehlersemantiken (nur loggen · `failed_channels` · `return False` ·
   `sent_channels.append` VOR dem `try`); Vereinheitlichung wäre Verhaltensänderung außerhalb des Auftrags.
2. **Dünnes Gate VOR jedem `.send()`** — auch vor der sink/send-Weiche (Test-Seams `sms_sink`
   etc. sind produktiv immer `None`) und **vor** jedem `sent_channels.append`. Limit erreicht ⇒
   `ChannelBlockedError(channel, msg, reason_code="sms_daily_limit_exceeded")`
   (`src/output/channels/base.py:64-93`) ⇒ `blocked_channels[ch]` +
   `_record_block_reason_code` (`notification_service.py:160-174`). SMS erscheint damit erstmals in
   `blocked_channels`; Konsument `alert_log.py:238-256` ist generisch (Sperrgrund vor Schwelle vor
   technisch gescheitert) — kein Whitelist-Zwang.
3. **Zählen NUR im `try` direkt nach erfolgreichem `.send()`** — nie aus
   `sent_channels`/`delivered_channels` ableiten (dort steht der Kanal teils schon vor dem Versand).
4. Einheit: **1 `.send()`-Aufruf = 1 Zähleinheit** (kein Client-Split in `seven_io_base.py:166-186`;
   ob Seven.io je Segment abrechnet, ist aus dem Repo nicht belegbar — offen vermerkt).
5. Reihenfolge gegenüber `daily_alert_limit`: das bestehende Alarm-Frequenz-Limit greift
   **zuerst** (ganzer Alarm unterdrückt); der SMS-Deckel wirkt danach nur auf den einzelnen Kanal.
   E-Mail/Telegram sind vom SMS-Deckel nie betroffen (#1701).
6. Keine proaktive Hinweis-Nachricht beim Erreichen (Kosten-/Schleifenrisiko; „nur Daten").

### Scope Assessment
- Produktiv-Dateien: 3 (`sms_daily_limit.py` neu, `user_tier.py`, `notification_service.py`) + Tests + 2 Doku-Dateien
- Estimated LoC: +190…230 / −0 (produktiv) — unter 250
- Risk Level: **MEDIUM** — berührt alle SMS-Sendepfade (Briefing, Alarm, Garmin-Antwort) in der zentralen Versanddatei

### Dependencies
- Nutzt: `file_lock.acquire_exclusive`, `get_data_dir(user_id)`, `user_tier` (Tier aus `user.json`), `ChannelBlockedError`.
- Muss grün bleiben: `test_issue_1070_daily_alert_limit.py`, `test_issue_1069_tier_channel_gating.py`,
  `test_ruhezeit_und_zaehler_folgen_der_ortszone.py`, `test_alarm_szenario_*`, `test_compare_alert_channel_delivery.py`,
  `test_compare_dispatch_channel_fanout.py`, `test_914_slice4_alert_sms_dispatch.py`, `test_kanaltreue_adhoc_antwort.py`.
- Testisolation: `tests/conftest.py:186-209` biegt `_DATA_ROOT` nur sessionweit um ⇒ je Test eindeutige `user_id`.

### Nebenbefund (nicht S4a)
`sent_channels.append("sms"|"premium_sms")` steht in `_dispatch_alert_message`
(`notification_service.py:1781`, `:1795`) VOR dem `try` — ein gesperrter/gescheiterter Versand gilt
dort als „gesendet". Eigenes Issue nur, falls nutzersichtbar (Journal/UI); sonst Zeile in #1199.
S4a darf den Zähler davon NICHT ableiten (Punkt 3).

### Open Questions
- [x] E1–E4 vom PO entschieden (s.o.).
- [ ] Genaue Garmin-Zusatzmenge (Vorschlag 3/Tag) und Reservegrößen — Spec setzt die Vorschläge als Default.
