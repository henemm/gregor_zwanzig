# Context: feat-2184-premium-sms-kommando

**Issue:** #2184 — Premium-SMS erreicht den Kommandoverarbeiter
**Epic:** #2133 „Ad-hoc-Abruf so reich wie das Briefing", Scheibe **S4**
**Erstellt:** 2026-09-08 · **Basis:** `origin/main` @ `ccd7c955`

## Request Summary

Eine eingehende Garmin-inReach-Nachricht löst heute ausschließlich das Lernen der Rückadresse
aus; der Nachrichtentext wird verworfen und der `TripCommandProcessor` nie aufgerufen. Diese
Scheibe schließt den vierten Eingangsweg an: Der Text vor dem Kennzeichen `inreachlink.com`
wird als Befehl verarbeitet und über den Premium-SMS-Rückkanal beantwortet.

## Vorlauf: es gibt bereits einen Spec-Entwurf

`docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` (Commit `54144c26`,
07.09., `status: draft`, **Approval nicht angehakt**) enthält Ist-Analyse, Implementierungs-
vorschlag und 7 AC-Entwürfe. Der zugehörige Workflow `feat-2184-premium-sms-kommandos` wurde
am selben Tag **abgebrochen** (Grund: Scheibenwahl auf #2185/S2 korrigiert) — Phase 1, kein
Artefakt, kein Kontextdokument.

**Alle Belegzeilen des Entwurfs sind gegen den heutigen `main` nachgemessen und bestätigt.**
Zwei Befunde gehen jedoch über den Entwurf hinaus (Abschnitt „Risks", Punkte 1 und 2).

## Ist-Stand (nachgemessen 2026-09-08 gegen `ccd7c955`)

### A) Der Text wird an genau einer Stelle fallengelassen

`InboundSmsReader._poll_journal` (`src/services/inbound_sms_reader.py:122`) pollt das
seven.io-Journal (`JOURNAL_URL` `:56`, kein Webhook, kein IMAP):

```
:161  text = message.get("text", "") or ""
:162  if GARMIN_MARKER not in text:        # `text` dient NUR als Filter
:163      max_seen = max(max_seen, msg_id); continue
:166  sender = message.get("from", "")
:167  payload: dict = {"from": sender}     # ← `text` fliesst nirgends hinein
:171  response = httpx.post(LEARN_ENDPOINT, json=payload, timeout=5)
```

Der Reader importiert weder `TripCommandProcessor` noch `InboundMessage` noch
`NotificationService`. Es gibt **kein** halbfertiges Stück, kein TODO, keinen abgeschalteten
Zweig.

### B) Die `user_id` liegt bereits vor — sie wird nur nicht gelesen

Der Go-Endpunkt `POST /api/internal/premium-sms-learn`
(`internal/handler/premium_sms_connect.go:31`, registriert `internal/router/router.go:79`,
localhost-only `:33`) antwortet:

| Fall | Status | Body | Zeile |
|---|---|---|---|
| Erfolg | 200 | `{"status":"ok","user_id":"<id>"}` | `:115` |
| Dry-Run, Treffer | 200 | `{"status":"dry_run","outcome":"would_learn","user_id":…,"masked_from":…}` | `:89-94` |
| Dry-Run, kein Treffer | 200 | `{"status":"dry_run","outcome":"would_skip","reason":"no_unique_premium_candidate"}` | `:81-86` |
| Mehrdeutig / kein Kandidat | **409** | `{"status":"skipped","reason":"no_unique_premium_candidate"}` | `:99-104` |

Die R3-Auflösung (`:52-73`) verlangt Tier `premium` und fällt **nie** auf `"default"` zurück
(`:16`). Im Nicht-Dry-Run liest Python den 200er-Body heute gar nicht (`:191`) — die `user_id`
verfällt. Es gibt in Python kein `lookup_user_by_phone`; der Endpunkt ist die **einzige**
Quelle. **Go bleibt unverändert.**

### C) Alles Nachgelagerte trägt bereits

| Glied | Stand | Beleg |
|---|---|---|
| `_resolve_channel_flags(..., restrict_to_channel)` kennt `"premium_sms"` inkl. Tier-Gate | ✅ | `trip_report_scheduler.py:1711-1757`, `:1743` |
| `send_on_demand_report(..., restrict_to_channel="premium_sms")` | ✅ dokumentiert | `trip_report_scheduler.py:1095-1101`, Docstring `:1238-1240` |
| `PremiumSmsOutput.send(subject, body)` inkl. 30-Tage-Frischesperre, fail-closed | ✅ | `premium_sms.py:52-93`, `seven_io_base.py:155-184` |
| `Settings.with_user_profile(user_id)` liefert `premium_sms_reply_to/_at` | ✅ | `config.py:366`, `:407-411` |
| `InboundMessage.channel` ist ein freier `str`, kanalneutral verarbeitet | ✅ | `trip_command_processor.py:55-63` |

**Damit ist S3 (#2126) die tragende Vorleistung:** `heute`/`morgen` lösen bei
`restrict_to_channel="premium_sms"` bereits ein Briefing aus, das ausschließlich per
Premium-SMS geht — ohne eine einzige neue Zeile Kanalauswahl.

### D) Was fehlt — drei Lücken

1. **Textextraktion + `InboundMessage`-Bau + `process()`-Aufruf** im Garmin-Zweig
   (`inbound_sms_reader.py:160-209`).
2. **`NotificationService.send_command_reply_premium_sms`** — die Familie ist heute
   zweigliedrig: `send_command_reply_email` (`notification_service.py:1795-1807`),
   `send_command_reply_telegram` (`:1809-1826`). Für SMS/Premium-SMS existiert nichts.
3. **Trip-Auflösung.** Der Reader hat kein `_find_active_trip`. Das Telegram-Vorbild liegt in
   `inbound_telegram_reader.py:363-405` (Datum-Overlap am **Ortstag**, ADR-0044; Fallback
   nächster zukünftiger Trip; `now_utc` als Pflichtparameter, ADR-0051 Regel 3). Das
   E-Mail-Muster (Trip-Name aus der Betreff-Klammer) scheidet aus — im Satellitentext kostet
   jedes Zeichen.

### E) Das gemeinsame Muster der bestehenden Reader

```
User-Auflösung → Trip-Auflösung → InboundMessage(channel=…) →
TripCommandProcessor().process() →
if not result.suppress_email_reply: send_command_reply_<kanal>(result, user_settings)
→ alles in try/except; Dedup-Fortschritt UNABHÄNGIG vom Verarbeitungserfolg
```

| Reader | `InboundMessage`-Bau | `process()` | Antwort | Dedup |
|---|---|---|---|---|
| E-Mail | `inbound_email_reader.py:144-151` | `:153-154` | `:155-156` | `finally: +FLAGS \Seen` `:161-162` (#1009) |
| Telegram | `:231-238`, Callback `:327-334` | `:249`, `:278`, `:335` | `:270-274`, `:279-283` | `self._offset` `:116-127` |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/inbound_sms_reader.py` | **Hauptwirkort.** `poll_and_process` `:87`, `_poll_journal` `:122`, Garmin-Zweig `:160-209`, Zeiger `_load/_save_last_seen_id` `:234`/`:244`, `GARMIN_MARKER` `:58`, `DRYRUN_ENV_VAR` `:59` |
| `src/services/notification_service.py` | neue `send_command_reply_premium_sms`; Vorbilder `:1795-1826`; bestehende `PremiumSmsOutput.send`-Aufrufe `:598`, `:756`, `:1139`, `:1447`, `:1777` |
| `src/services/trip_command_processor.py` | `InboundMessage` `:55-63`, `CommandResult` `:74-86`, `process` `:567`; **Kollisionskommentare `:1373-1376`, `:1444-1448`** |
| `src/services/inbound_telegram_reader.py` | Vorbild für Trip-Auflösung `_find_active_trip` `:363-405`, Ablaufmuster `:151-283` |
| `src/services/trip_report_scheduler.py` | `_resolve_channel_flags` `:1711-1757`, `send_on_demand_report` `:1095` — **keine Änderung nötig** |
| `src/output/channels/premium_sms.py` | `PremiumSmsOutput` `:52`, `_resolve_recipient` `:64-93`, TTL `:49` |
| `src/app/config.py` | `with_user_profile` `:366`, `premium_sms_reply_to/_at` `:207`, `:211`, `:407-411` |
| `internal/handler/premium_sms_connect.go` | Antwort mit `user_id` `:115`, `:92` — **unverändert** |
| `api/routers/scheduler.py` | Trigger `:143-168`, `last_failed_count` → `ok`/`partial` |

## Existing Patterns

- **Reader-Muster (s. E)** — S4 kopiert es, erfindet nichts.
- **Fail-closed beim Premium-SMS-Versand** — fehlende oder veraltete Rückadresse ergibt
  `ChannelBlockedError` mit `reason_code`, nicht stilles Schweigen (`premium_sms.py:75-92`).
- **Dedup-Zeiger unabhängig vom Verarbeitungserfolg** — E-Mail setzt `\Seen` im `finally`,
  Telegram schiebt `_offset` je Update. Für S4 ist das die F001-Zeigersemantik.
- **Empfänger kommt aus `Settings`, nicht als Parameter** — kein Kanal außer E-Mail hat einen
  Empfänger-Parameter; die Adresse entsteht über `with_user_profile(user_id)` (#2168).

## Dependencies

- **Aufwärts:** Go-Learn-Endpunkt (`user_id`), `TripCommandProcessor.process`,
  `_resolve_channel_flags`/`send_on_demand_report` (S3), `PremiumSmsOutput`,
  `Settings.with_user_profile`, `_find_active_trip`-Logik.
- **Abwärts:** `briefing_log.channels` (Go liest es für die Cockpit-Kachel) — bei einer
  Premium-SMS-Anfrage steht künftig `["premium_sms"]` drin. Bester Messpunkt ohne
  Stellvertreter. Ferner `api/routers/scheduler.py` → `internal/scheduler/scheduler.go`
  (`ok`/`partial`), das an `last_failed_count` hängt.
- **Epic:** setzt **S3 (#2126, geschlossen, in `main`)** voraus. S5 (Kurzform-Verlauf,
  Kürzungsregel) baut darauf auf und ist **nicht** Teil dieser Scheibe.

## Existing Specs

| Spec | Kernaussage |
|---|---|
| `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` | **Entwurf für dieses Ticket** (draft, unapproved), 7 AC-Entwürfe |
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` (v1.5) | der bestehende Poll lernt **nur** die Rückadresse; F001/F003/F004-Historie |
| `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | Premium-SMS als Versandkanal (fester Absender, gelernte Adresse, fail-closed, Tier `premium`) |
| `docs/specs/modules/inbound_command_channels.md` | `:90` „Antwort auf gleichem Kanal"; `:335-368` skizziert einen SMS-Reader und hält ausdrücklich fest, dass der reale Reader das **nicht** tut — **diese Stelle schreibt S4 fort** |
| `docs/specs/modules/trip_command_processor.md` (v2.1) | kanalneutraler Verarbeiter, `CommandResult` für den Aufrufer |
| `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` | S3; `:269` benennt Premium-SMS-Eingang ausdrücklich als S4 |
| `docs/specs/modules/feat_1680_s5a_…md:337`, `feat_1680_s5b_…md:456` | **„SMS und Premium-SMS bleiben ohne Herkunft"** (AC-12 bzw. AC-9) — s. Risiko 1 |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | Premium-SMS ist ein eigenständiger vierter Kanal, kein SMS-Sonderfall. Kein neues ADR nötig — `premium_sms` wird nicht eingeführt, nur angeschlossen. |
| ADR-0044 (Ortstag), ADR-0051 Regel 3 (keine Umgebungsuhr), ADR-0015 (Kanal-Transporte) | binden die Trip-Auflösung |

## Test-Ist-Stand

| Datei | Was sie bewacht |
|---|---|
| `tests/unit/test_inbound_sms_reply_learning.py` (13 Tests) | **Die natürliche Heimat für S4-Tests.** Journal-Poll komplett: Marker-Erkennung `:167`, ohne Marker ignoriert `:202`, Dedup-Zeiger `:278`, Herkunftssperre `:310`, Dry-Run-Payload `:342`, F001 transienter Fehler hält Zeiger `:426`, 5xx `:487`, 409 schiebt Zeiger `:540`, Router `partial` `:573`. Fakes: `_FakeJournal` `:77`, Learn-Recorder `:92` |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py` | **Bestes Vorbild für AC-1/AC-7.** `ALLE_KANAELE` `:77`, Premium-SMS-Buchung über `premium_sms_reply_to` `:170`, Fixture-Profil `:216-217`, Tier-Gate-Gegenprobe `:634`/`:667`, Zwei-Nutzer-Isolation `:884` |
| `tests/unit/test_premium_sms_versand.py` | Versand am echten POST: fester Absender `:359`, gelernte Adresse `:398`, fail-closed `:430`, TTL `:453`/`:475`, ≤160 Zeichen `:499` |
| `tests/tdd/test_trip_command_processor.py` (29 Tests) | Parsing, Ruhetag, Startdatum, Abbruch, Unknown → Hilfe |
| `tests/tdd/test_antwort_an_den_fragenden.py` | #2168 — Antwort geht an die Absenderadresse |
| weitere | `test_config_premium_sms.py`, `test_premium_sms_preflight_check.py`, `test_premium_sms_ttl_drift.py`, `test_alert_channel_premium_sms.py`, `internal/handler/premium_sms_connect_test.go` |

**Keine Datei-Fixtures für eingehende Premium-SMS** — Journal-Einträge werden inline erzeugt
(`id`/`from`/`text`). Realer Garmin-Aufbau (Beleg #1676 S1, 10.08.):
`"Test über App inreachlink.com/g-0Oh3D2H2f… (51.9956, 7.7136)"` — **Nutzertext steht vor dem
Kennzeichen**, danach Garmin-Link und Koordinaten.

**Kein Test bewacht heute, dass der Text verarbeitet wird** — konsistent damit, dass er den
Prozessor nie erreicht.

## Risks & Considerations

1. **🔴 Kollision mit der PO-Abwahl „SMS ohne Herkunft" — im Entwurf nicht erfasst.**
   Zwei Kommentare im Prozessor schreiben die heutige Zweier-Annahme ausdrücklich fest:
   `trip_command_processor.py:1373-1376` (GLANCE) und `:1444-1448` (GEWITTER) —
   „`InboundMessage` hat genau diese zwei Erzeuger; einen SMS-/Premium-SMS-Kommandopfad gibt
   es nicht, die PO-Abwahl ‚SMS ohne Herkunft' greift hier **strukturell**." Sobald der Reader
   ein dritter Erzeuger wird, fällt diese strukturelle Sicherung weg und die Gewitter-Herkunft
   (`thunder_signals`, #1680) erscheint in Premium-SMS-Antworten — gegen
   `feat_1680_s5a_…md:337` / `feat_1680_s5b_…md:456`. **Zu entscheiden in der Analyse**, mit
   Vorschlag in der Spec. Die Kommentare sind in jedem Fall mitzuführen, sonst bleibt eine
   falsche Begründung im Code stehen.

2. **Dritte Produktivdatei durch die Trip-Auflösung.** Der Entwurf nennt 2 Produktivdateien;
   `_find_active_trip` liegt aber im Telegram-Reader (`:363-405`). Kopieren wäre ein Duplikat
   an einer datumsempfindlichen Stelle (Ortstag, ADR-0044) — Teilen ist der bessere Weg,
   kostet aber eine dritte Datei und eine Signatur-Berührung im Telegram-Pfad. **Zuschnitt-
   Entscheidung für die Analyse.**

3. **F001-Zeigersemantik ist der gefährlichste Ort.** Der Garmin-Zweig `:160-209` enthält zwei
   `break`-Anweisungen (`:179`, `:209`), die den Zeiger bewusst stehenlassen. Ein neues
   `except` an falscher Stelle klassifiziert einen Verarbeitungsfehler als transienten
   Lernfehler, lässt den Zeiger stehen und erzeugt eine Endlosschleife über dieselbe Nachricht
   — mit Kostenwirkung pro Antwort-SMS. Der neue Block braucht ein **eigenes**, nachgelagertes
   `try/except`, das `failed` nicht anfasst.

4. **Antwortlänge ist ungeregelt.** `PremiumSmsOutput.send()` hat kein Limit; `subject` wird
   verworfen (`seven_io_base.py:167`). Für Briefings wird fest auf 160 Zeichen gerendert, für
   Kommando-Antworten existiert **keine** Kürzung. Eine lange `confirmation_body` wird zur
   mehrteiligen, kostenpflichtigen SMS. Der Entwurf grenzt die Kürzungsregel als **S5** aus —
   das ist vertretbar, muss aber als bekannte Grenze in der Spec stehen, nicht stillschweigend.

5. **Erstverbindungsnachricht.** „Test über App …" enthält keinen Befehl und löst nach AC-3 des
   Entwurfs eine kostenpflichtige Antwort-SMS aus. Produktentscheidung, dem PO bei der
   Spec-Freigabe vorzulegen.

6. **Trockenlauf muss nebenwirkungsfrei bleiben.** `GZ_PREMIUM_SMS_POLL_DRYRUN=1` ist heute die
   einzige Art, den Poll außerhalb von `production` laufen zu lassen (`:97-113`). Kein
   `process()`, kein Versand im Dry-Run — sonst verschickt eine Staging-Prüfung echte
   Satelliten-SMS.

7. **Mandantentrennung.** Die `user_id` kommt vom Go-Endpunkt und ist nie `"default"`. Jeder
   neue datenbewegende Pfad ist mit **zwei verschiedenen Nutzern** zu testen (AC-7 des
   Entwurfs); `test_kanaltreue_adhoc_antwort.py:884` ist das Vorbild.

8. **Mutations-Gegenprobe muss an der Wirkstelle ansetzen.** Ein Test, der nur prüft, dass ein
   `InboundMessage` mit `channel="premium_sms"` entsteht, bewacht nichts. Der Nachweis beginnt
   am Journal-Eintrag und endet am tatsächlich abgesetzten seven.io-POST bzw. an
   `briefing_log.channels == ["premium_sms"]`.

9. **Referenzfeger.** Wird `_find_active_trip` geteilt oder eine Signatur berührt:
   `grep -rln "<name>" tests/ src/`. Werden zusätzliche Abrufe eingebaut statt Signaturen
   erweitert, schlägt der Feger nicht an — dann nach dem Naht-Namen fegen.

## Offene Fragen für die Analyse-Phase

- **Gewitter-Herkunft auf Premium-SMS** (Risiko 1): mitliefern oder für `channel="premium_sms"`
  unterdrücken? Produktentscheidung mit Vorschlag in der Spec.
- **Trip-Auflösung** (Risiko 2): `_find_active_trip` teilen oder im Reader kopieren?
- **Erstverbindungsnachricht** (Risiko 5): AC-3-Antwort oder Sonderregel?
- **Zuschnitt/LoC:** Der Entwurf schätzt +90–150 Produktivcode; S3 riss die Schätzung deutlich
  (real +817 inkl. Tests). `loc_limit_override` ist einzuplanen.

---

## Analysis

### Type

**Feature.** Kein Bugfix — das heutige Verhalten war nie anders spezifiziert:
`feat_1676_s1_premium_sms_rueckkanal.md` beschreibt den Poll ausdrücklich als reinen
Adress-Lerner. #2184 schließt den vierten Eingangsweg an einen bereits kanalneutralen
Verarbeiter an.

### Technical Approach (Entscheidungen)

**Reihenfolge:** erst die Bausteine, zuletzt der riskante Garmin-Zweig — so wird die
F001-Zeigersemantik nur einmal, mit fertigen Teilen, berührt.

**1. Trip-Auswahl als geteilter Baustein — aber am Schnitt NACH dem Laden.**

Neues Modul `src/services/trip_selection.py` mit einer reinen Auswahlfunktion:

```python
def pick_active_trip(trips: list[Trip], now_utc: datetime) -> Trip | None
```

Sie enthält bit-identisch die heutige Auswahlregel aus
`inbound_telegram_reader._find_active_trip` (`:385-406`): Overlap am **Ortstag dieses Trips**
(`trip_local_today`, ADR-0044), Rückfall auf den frühesten zukünftigen Trip.

**Entscheidend ist der Schnitt:** `load_all_trips(user_id)` bleibt **im jeweiligen Reader**.
`_find_active_trip` wird zur zweizeiligen Hülle (`trips = load_all_trips(user_id)` →
`return pick_active_trip(trips, now_utc)`), der SMS-Reader macht dasselbe mit eigenem Import.

- Gegen **Kopieren**: die Ortstag-Regel an zwei Stellen zu pflegen ist genau das Duplikat, das
  erst an einer Tourgrenze auffällt.
- Gegen **Import des Telegram-Readers**: ein Kanal-Reader, der einen fremden Kanal-Reader
  instanziiert, ist der falsche Schichtenschnitt.
- Gegen **`load_all_trips` mit ins Modul zu ziehen** (Vorschlag des Plan-Agenten): vier
  Testdateien patchen `services.inbound_telegram_reader.load_all_trips` auf dem **Modulpfad**
  (`test_inbound_telegram_reader.py:58-131`, `test_befehlspfade_folgen_ortszone.py:362-490`,
  `test_bug_824_archived_trip_filter.py:184-208`, `_telegram_live_fixture.py:347`). Wandert der
  Aufruf, greifen alle vier Patches ins Leere und laufen still gegen echte Daten statt gegen
  Fixtures — ein falsches Grün. Der gewählte Schnitt lässt sie **unberührt** und spart den
  Referenzfeger ganz. Präzedenz für die Extraktion selbst: `src/services/trip_day.py`
  („Verschoben aus `services.trip_command_processor` (#1470) — bit-identisches Verhalten, nur
  `self.` entfernt").

**2. `NotificationService.send_command_reply_premium_sms(result, settings)`** — Spiegelbild von
`send_command_reply_email` (`:1795-1807`). Der Empfänger kommt wie bei allen Nicht-E-Mail-Kanälen
aus `settings.premium_sms_reply_to` (`with_user_profile(user_id)`), es gibt keinen
Empfänger-Parameter (#2168).

**3. Gewitter-Herkunft für `sms`/`premium_sms` in Kommando-Antworten unterdrücken — in DIESER
Scheibe.** Die PO-Abwahl „SMS und Premium-SMS bleiben ohne Herkunft"
(`feat_1680_s5a_…md:337` AC-12, `feat_1680_s5b_…md:456` AC-9) ist **kanalbezogen** formuliert.
Bewacht ist heute nur der Briefing-Pfad (`test_thunder_origin_trip.py:357-387`); im
Kommando-Pfad wird sie ausschließlich **strukturell** durchgesetzt — durch die Annahme
„`InboundMessage` hat genau diese zwei Erzeuger", die an **drei** Stellen als Kommentar steht
(`trip_command_processor.py:1373-1376`, `:1444-1448`, `:1502-1503`). #2184 widerlegt diese
Annahme durch Konstruktion. Wer sie nicht ersetzt, liefert ab Merge CAPE-/Blitzpotenzial-Suffixe
(15–30 Zeichen) auf einem Kanal aus, der pro Zeichen Geld und Garmin-Kontingent kostet — und
bricht eine sichtbare PO-Entscheidung über einen Pfad, den der PO beim Abwählen nicht kannte.
Der Eingriff ist klein und folgt dem vorhandenen Muster: `channel` ist an der Aufrufstelle
bereits lokale Variable (`:763`, `:866`), die drei Formatierer bekommen einen `channel`-Parameter
wie `_handle_drilldown` & Co. (`:928`, `:1027`, `:1053`, dort `with_emoji = channel ==
"telegram"`), hier `zeige_herkunft = channel not in ("sms", "premium_sms")`. Die drei Kommentare
werden auf die neue, echte Begründung umgeschrieben — sonst bleibt eine falsche Begründung im
Code stehen.

**4. Garmin-Zweig in `_poll_journal` (`:160-209`) zuletzt.** Nach dem **unveränderten** Lernblock:
Gate `status_code == 200 and not dry_run` → `user_id = response.json().get("user_id")`
(fehlt/leer ⇒ loggen, keine Verarbeitung — der 200er-Vertrag ist nicht durch einen Contract-Test
abgesichert) → Befehlstext `text.split(GARMIN_MARKER, 1)[0].strip()` → `load_all_trips` +
`pick_active_trip` → `InboundMessage(channel="premium_sms", …)` → `process()` → bei
`not result.suppress_email_reply` antworten. **Eigener, nachgelagerter `try/except`**, der nur
loggt und `max_seen`/`learned`/`failed` nicht anfasst.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `src/services/trip_selection.py` | CREATE | `pick_active_trip(trips, now_utc)` — Auswahlregel, ohne Laden |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_find_active_trip` wird Delegations-Hülle (`load_all_trips` bleibt hier) |
| `src/services/inbound_sms_reader.py` | MODIFY | Garmin-Zweig: `user_id` konsumieren, Text extrahieren, Trip auflösen, `process()`, Antwort — eigener `try/except` |
| `src/services/notification_service.py` | MODIFY | `send_command_reply_premium_sms` |
| `src/services/trip_command_processor.py` | MODIFY | `channel` an `_fmt_day_agg`/`_fmt_gewitter`/`_fmt_timeline`; Herkunfts-Guard; drei Kommentare korrigieren |
| `tests/unit/test_inbound_sms_reply_learning.py` | MODIFY | AC-1…AC-7 am bestehenden Journal-Fake |
| `tests/tdd/test_gewitter_herkunft_ohne_kommandokanal.py` | CREATE | Guard über alle drei Formatierer, beide Richtungen |
| `tests/unit/test_trip_selection.py` | CREATE | Auswahlregel neutral (Overlap, Zukunfts-Fallback, leer) |
| `docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md` | MODIFY | Entwurf → freigabereife Spec (Herkunft, Trip-Auswahl, `user_id`-Guard ergänzen) |
| `docs/specs/modules/inbound_command_channels.md` | MODIFY | `:335-368` fortschreiben — Premium-SMS **ist** jetzt ein Befehlskanal |

**Unberührt (belegt):** Go vollständig — der Learn-Endpunkt liefert `user_id` bereits
(`premium_sms_connect.go:115`), der Scheduler-Job ist registriert und
`triggerPremiumSmsPollEndpoint` wertet `failed` schon aus (`internal/scheduler/scheduler.go:207`,
`:470-517`). Ebenso `trip_report_scheduler.py` (S3 trägt `restrict_to_channel="premium_sms"`
bereits), `src/output/channels/premium_sms.py`, Frontend.

### Scope Assessment

- **Dateien:** 5 Produktivcode (1 CREATE, 4 MODIFY) + 3 Test + 2 Doku
- **LoC:** Produktivcode ~110–150, Tests ~220–330 → **~330–480**
- **LoC-Limit 250 wird gerissen** → `workflow.py set-field loc_limit_override 400`, sobald
  `status` es zeigt. (S3/#2126 schätzte 120–180 und landete real bei +817 — 400 ist die
  konservativere, aber realistische Marke.)
- **Risk Level: MEDIUM–HIGH.** Der neue Zweig liegt unmittelbar neben der F001-Zeigersemantik,
  und jeder Fehler dort hat **Kostenwirkung pro Poll-Zyklus** (Satelliten-SMS).

### Dependencies

- **Aufwärts:** Go-Learn-Endpunkt (`user_id`), `TripCommandProcessor.process`,
  `send_on_demand_report(restrict_to_channel=…)` aus S3, `PremiumSmsOutput`,
  `Settings.with_user_profile`, `trip_local_today` (ADR-0044).
- **Abwärts:** `briefing_log.channels` (Cockpit-Kachel) — bei Premium-SMS-Anfragen künftig
  `["premium_sms"]`; `last_failed_count` → `api/routers/scheduler.py:167-168` →
  `internal/scheduler/scheduler.go:470-517` (`ok`/`partial`). **Der neue Zweig darf
  `last_failed_count` nicht erhöhen** — sonst meldet der Go-Scheduler `partial` für einen
  reinen Verarbeitungsfehler.
- **Epic:** S3 (#2126) ist Voraussetzung und liegt in `main`. S5 baut auf S4 auf.

### Mutationen, an denen sich die Gegenprobe messen muss

1. **`if not result.suppress_email_reply` entfernen.** Ein Test, der nur „bei `heute` kommt eine
   Premium-SMS" prüft, bleibt grün — die Briefing-SMS kommt ja. Fängt es nur: ein Test, der
   **genau eine** abgesetzte Premium-SMS zählt, nicht zwei.
2. **`break` bei `:179`/`:209` zu `continue`.** Fängt nur ein Test über **zwei** Poll-Läufe, der
   den Zeigerstand nachmisst — nicht einer, der `learned == 0` prüft.
3. **Herkunfts-Guard in nur einem der drei Formatierer.** Fängt nur ein parametrisierter Test
   über alle drei Pfade (GLANCE, GEWITTER, Timeline) mit einer Fixture, die garantiert eine
   Zutat trägt.
4. **`response.json().get("id")` statt `.get("user_id")`.** Ein Ein-Nutzer-Test bleibt grün, weil
   der Rückfall auf die Basis-Settings eine plausible SMS erzeugt. Fängt nur der
   Zwei-Nutzer-Test (AC-7).
5. **Verarbeitungs-`except` in den Lernblock hineingezogen.** Fängt nur ein Test, der den
   Lernaufruf **erfolgreich** mockt und `process()` werfen lässt und dann prüft: Zeiger wandert
   **und** `last_failed_count == 0`.
6. **Dry-Run-Gate hinter die Verarbeitung geschoben.** Fängt nur ein Test, der den
   Premium-SMS-Versand selbst beobachtet und **null** Aufrufe fordert — nicht einer, der nur
   `learned == 0` prüft.

### Open Questions (PO)

- [ ] **Gewitter-Herkunft auf Premium-SMS** — Empfehlung: unterdrücken (s. o.). Geht als AC in
      die Spec; Bestätigung mit der Spec-Freigabe.
- [ ] **Erstverbindungsnachricht** („Test über App …") — Empfehlung: wie jeder unbekannte Befehl
      behandeln, also mit einer Antwort-SMS. Konsistent mit dem Epic-Leitsatz „jeder Kanal,
      dieselbe Aussage"; eine Bestätigung „deine erste Nachricht ist angekommen" hat für den
      Wanderer sogar eigenen Wert. Kostet eine SMS.
- [x] **Trip-Auflösung** — entschieden: geteilte Auswahlfunktion, Laden bleibt im Reader.
- [x] **Antwortlänge/Kürzung** — bleibt Scheibe S5, als bekannte Grenze in der Spec benannt.
