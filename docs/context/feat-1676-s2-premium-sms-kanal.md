# Context: feat-1676-s2-premium-sms-kanal

**Issue:** #1676 S2 — Premium-SMS als vierter Versandkanal (Backend-Hälfte)
**Vorgänger:** S1 (Rückkanal + gelernte Rückadresse) ist live auf `597ea84f`
**Nachfolger:** S3 (Oberfläche), S4 = #1533 (Generalprobe auf dem Gerät, Frist 20.8.)
**Basis:** `origin/main` = `e76c99d6`

## Request Summary

Premium-SMS (Garmin inReach, seven.io-Nummer `4916092172595`) soll ein vollwertiger vierter
Versandkanal werden — Absender fest unsere Rufnummer, Empfänger die von S1 gelernte,
veränderliche Rückadresse, bei leer/veraltet **kein** Versand. S1 lernt die Adresse bereits;
ohne S2 geht nichts an das Gerät.

## Related Files

### Python — Versandweg

| Datei | Relevanz |
|---|---|
| `src/output/channels/sms.py` | **Vorbild für den neuen Kanal.** 102 Zeilen: `SMSOutput.send()` (`:77-102`) POSTet an seven.io mit `X-Api-Key`; `from` wird nur gesetzt, wenn `sms_from` gefüllt ist (`:85-86`). Zwei Sperren davor: `_guard_test_mode_sandbox_key()` (`:34-51`), `_guard_code_origin()` (`:53-75`). |
| `src/output/channels/base.py` | `Protocol OutputChannel` (`:16-49`): nur `name` + `send(subject, body)`. Fabrik `get_channel()` (`:66-102`) mit `if/elif`-Kette über Kanalnamen — **wird aber nur von der CLI benutzt** (`src/app/cli.py:256/258/280/282`), nicht vom Versandpfad. |
| `src/services/notification_service.py` | 1537 Zeilen, **die Hauptarbeit**. Fünf Versand-Anlässe, jeder mit eigener harter `if "email"/"telegram"/"sms"`-Kette. Für S2 zentral: `send_trip_report()` (`:275-460`), SMS-Zweig `:369-377`. Kanäle kommen dort aus drei Bool-Flags `send_email`/`send_sms`/`send_telegram` (`:87-89`), nicht aus `effective_channels`. |
| `src/services/alert_log.py:59` | `_ALL_CHANNELS = ("email", "telegram", "sms")` — harte Aufzählung, treibt `channels_not_sent` im Alarm-Protokoll. Nur für den Alarm-Pfad relevant. |
| `src/services/trip_alert.py:1446` | **Zweite, unabhängige Kopie** derselben Dreier-Liste, inline. Drift-Risiko. |
| `src/output/renderers/channel_layout.py:45-49` | `CHANNEL_LIMITS` — drei Einträge (`sms`: 153 Zeichen). `:97` fällt bei unbekanntem Kanal still auf **Telegram**-Limits zurück (4096 Zeichen). ⚠️ **Nachgemessen und eingegrenzt (Phase 2):** Dieser Rückfall betrifft den Briefing-Pfad **nicht** — `CHANNEL_LIMITS` wird ausschließlich von `comparison.py` und `compare_preview_service.py` gelesen, der Briefing-SMS-Text bekommt `max_length=160` fest übergeben (`src/output/renderers/trip_report.py:420`). Die Falle bleibt nur für den Vergleichs-Pfad und für S3 relevant. |
| `src/app/config.py` | `sms_to`/`sms_from`/`sms_gateway_url`/`seven_api_key`/`seven_sandbox_key` (`:155-162`). `with_user_profile()` (`:278-318`) übernimmt heute genau drei Profilfelder: `mail_to`, `telegram_chat_id`, `sms_to` (`:308-313`). |
| `src/app/loader.py:1081-1125` | `get_data_root()`/`get_data_dir()` — Datenwurzel per Modul-Override (Test-Isolation) > ENV `GZ_DATA_DIR` > `data/`. Jeder Lesezugriff auf `user.json` MUSS hierüber laufen. |
| `src/app/origin_guard.py:22-46` | Herkunftssperre. Vergleicht die Checkout-Wurzel **exakt** mit `/home/hem/gregor_zwanzig` bzw. `…_staging` — ein Worktree gilt deshalb als `"test"`. |
| `src/services/inbound_sms_reader.py` | S1-Gegenstück (nicht ändern). Konstanten: `GARMIN_MARKER = "inreachlink.com"` (`:58`), `LEARN_ENDPOINT` localhost:8090 (`:57`). |
| `src/services/user_tier.py:17-31` | `daily_alert_limit()` — free 2 / standard 4 / premium unbegrenzt. Premium-SMS ist laut `docs/specs/modules/epic_user_tiers_overview.md:29` ein **Premium-Tier**-Merkmal mit 15-Minuten-Mindestabstand. |

### Go — Modell, Persistenz, Auslösung

| Datei | Relevanz |
|---|---|
| `internal/model/user.go:37-38` | **S1-Bestand, nicht ändern:** `PremiumSmsReplyTo string` / `PremiumSmsReplyAt *time.Time`. Einziger Schreiber `internal/handler/premium_sms_connect.go:108-109`. **Heute liest sie außer dem Schreiber niemand** — S2 ist der erste Leser. |
| `internal/model/trip.go:161-163` | `SendEmail`/`SendSms`/`SendTelegram *bool` — nicht autoritativ, bei jedem Load/Save aus `ReportConfig` abgeleitet (`internal/store/trip.go:57-92`). |
| `internal/model/trip.go:187-206` | `AlertChannelsConfig` (Email/Telegram/Sms bool) und `AlertChannelThresholdsConfig` (drei `*string`). Nur Alarm-Pfad. |
| `internal/store/trip.go:214-255`, `store/user.go:67-79` | `SaveTrip`/`SaveUser` schreiben das **komplette** Struct neu. Da `Trip`/`User` typisierte Structs sind, verwirft `json.Unmarshal` unbekannte JSON-Felder — sie gehen beim nächsten Speichern **verloren**. Merge passiert nicht im Store, sondern im Handler (`internal/handler/trip.go:256-402`, freie Maps über `config_merge.go:11-22`). |
| `internal/router/router.go:169-175` | Vorschau-Routen mit Kanalname als **festes Literal** beim Registrieren. Keine Allowlist erlaubter Kanalnamen — `preview_proxy.go:76` baut die Python-URL aus dem festen String. |
| `internal/scheduler/scheduler.go:271-304, 545-584` | Go löst den echten Versand aus: `POST {python}/api/scheduler/trip-reports?user_id=…`, **ohne Body und ohne Kanalliste**. Python liest die Kanalauswahl selbst aus der Persistenz. Das heißt: **S2 braucht keine neue Go→Python-Leitung für den Versand.** |

## Existing Patterns

- **Kein Kanal-Register im Versandpfad.** `notification_service.py` konstruiert `EmailOutput`/`SMSOutput`/`TelegramOutput` direkt an jeder Sendestelle. `get_channel()` ist *nicht* die Naht — es bedient nur die CLI. Ein vierter Kanal muss entweder an jeder Stelle einzeln verdrahtet werden, oder der Briefing-Zweig wird auf eine Auflösung umgestellt.
- **Guards sind Handarbeit, nicht erzwungen.** `tests/tdd/test_channel_origin_guard_parity.py:85-155` prüft die Herkunftssperre namentlich nur für `EmailOutput` und `SMSOutput` — kein Scan über `src/output/channels/`. Ein neuer Kanal ohne Guards fällt der Testsuite **nicht** auf.
- **Test-Nähte: Sinks nur teilweise vorhanden.** `mail_sink`/`sms_sink`/`telegram_sink` (Docstring `notification_service.py:853-854`) existieren für amtliche Warnung und Vergleichs-Briefing. **`send_trip_report()` und `_dispatch_alert_message()` haben keinen `sms_sink`** — dort wird direkt gesendet. Für den Briefing-Pfad ist die belastbare Naht deshalb ein **echter lokaler HTTP-Stub** nach Vorbild `tests/tdd/test_issue_936_sms_stub.py` (kein Mock).
- **Read-Modify-Write im Handler, nicht im Store** (siehe oben) — Pflicht bei jedem neuen Persistenz-Feld.

## Dependencies

- **Upstream:** seven.io Gateway (`gateway.seven.io`, bereits `TEST_ACCESS` in `src/app/egress_guard.py:52`, deckungsgleich mit `internal/egress/inventory.go` — kein neuer Allowlist-Eintrag nötig) · gelernte Rückadresse aus `users/<id>/user.json` (S1) · `sms_trip`-Renderer für den Nachrichtentext.
- **Downstream:** S3 (Oberfläche) zeigt Kanal + Rückadresse · #1533 Generalprobe · `alert_log.json`-Protokoll, sobald der Kanal alarmfähig wird.

## Existing Specs

- `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` — S1, v1.5. **Schließt Versand ausdrücklich aus** (Z. 29: „Nur Empfangen, Erkennen, Lernen, Speichern … kein Versandkanal (folgt in S2/S3)"). Enthält R1 (nur Nachrichten mit `inreachlink.com` lernen), R3 (Zuordnung über gespeicherte Nummer, sonst genau ein Premium-Nutzer, sonst 409).
- `docs/specs/modules/egress_guard_sms.md` — seven.io-Sandbox-Isolation.
- `docs/specs/modules/epic_user_tiers_overview.md:29,107` — Premium-SMS als Premium-Tier-Merkmal, „existiert als Kanal noch nicht".
- `docs/reference/sms_format.md` — SMS-Token-Grammatik v2.23, wird unverändert weiterverwendet.
- **Für S2 existiert keine Spec** — sie ist in Phase 3 zu schreiben.

## Verpflichtungen aus ADRs

| ADR | Konsequenz für S2 |
|---|---|
| `0004-signal-channel-removed.md` | Legt fest: „Die unterstützten Kanäle sind **nur noch** E-Mail · Telegram · SMS" (Z. 16-17). Ein vierter Kanal weicht davon ab → nach CLAUDE.md („Abweichung ⇒ neues ADR") braucht S2 ein **neues ADR**, das ADR-0004 in diesem Punkt fortschreibt. Das ist eine Liefer-Position, kein Nebensatz. |
| `0015-dual-stack-zielarchitektur.md` | Alle Kanal-Renderer und -Transporte gehören in den Python-Kern. Der neue Kanal gehört also nach `src/output/channels/`, nicht nach Go. |
| `0017-output-paket-konsolidierung.md` | Z. 56-65: Gate-Pfadmuster müssen im selben Commit nachgezogen werden, sonst „stiller Schutzverlust". |
| `0046-alarm-kanal-schwelle.md` | Z. 101-105: jede neue Stelle, die ein Kanal-Set auflöst, muss die Kanal-Schwelle anwenden. Greift erst, wenn Premium-SMS alarmfähig wird. |
| `docs/reference/api_contract.md:740-806` | `AlertChannelsConfig`/`AlertChannelThresholdsConfig` sind dort als „alle drei Felder" dokumentiert — nachzuziehen, sobald der Kanal in diesen Structs auftaucht. |

## Wächter, die anschlagen werden

| Wächter | Bedingung | Betrifft welchen Schnitt |
|---|---|---|
| `tests/test_success_status_guard.py:1547-1586, 1792-1794` | Ratsche mit **exakter Erwartung 3** je Funktion, indexbasiert (`::0`/`::1`/`::2`) für `send_official_alert` und `_dispatch_alert_message`. Ein vierter `sent_channels.append()` dort erzeugt einen ungelisteten Fund → `test_no_unlisted_success_status_findings` rot. Anheben nur mit Nachzug in Spec `waechter_1405_erfolg_wirkung.md`. | **Nur Alarm-Pfad.** `send_trip_report` ist Z. 774 ausdrücklich „belegt verschont" — ein Briefing-Schnitt löst diese Ratsche **nicht** aus. Selbst nachgemessen. |
| `src/output/renderers/channel_layout.py:97` | Stiller Rückfall auf Telegram-Limits bei unbekanntem Kanal — kein Fehler, nur eine viel zu lange SMS. | Jeder Schnitt. Muss ein Eintrag in `CHANNEL_LIMITS` werden, und der Rückfall gehört bei einem SMS-artigen Kanal geprüft. |
| `.claude/hooks/data_schema_backup.py:25-31` | Präfix `internal/model/` — jede Änderung dort löst vor dem Edit ein `data/users/`-Backup aus. | Jeder Schnitt mit Go-Modell-Feld. |
| `.claude/hooks/touched_tests_gate.py:37` | Jede `.py` unter `src/`/`api/`; sucht Tests in `tests/unit/`. `tests/tdd/` zählt dort **nicht** mit → Meldung „UNGEPRUEFT" statt Blockade. | Jeder Schnitt. |
| `.claude/hooks/renderer_mail_gate.py:42-48` | Erfasst von `src/output/channels/` **nur** `email.py`. Eine neue `channels/premium_sms.py` löst es nicht aus; eine Änderung an `renderers/sms_trip.py` oder `renderers/email/helpers.py` schon. | Nur bei Renderer-Berührung. |
| `.claude/hooks/pendant_gate.py:54,160-164` | Nur `src/output/renderers` mit `compare_`/`trip_`-Präfix. `src/output/channels/` fällt nicht darunter. | Nur bei neuem präfigierten Renderer. |
| `tests/test_egress_inventory_drift.py:72-89` | Deckungsgleichheit Python↔Go-Inventar. `gateway.seven.io` ist beidseitig vorhanden → **kein Handlungsbedarf**, solange kein neuer Host dazukommt. | — |

## Risks & Considerations

1. **Der Nachweis ist teurer als die Änderung.** Deterministisch beweisbar: Nutzlast (`from` = `4916092172595`), Empfängerauflösung aus `premium_sms_reply_to`, fail-closed bei leer/veraltet, Zeichen-Limit. **Nicht** beweisbar vor S4: dass die SMS auf dem Gerät ankommt. Gründe, gemessen: der Staging-Scheduler führt keinen Job aus (alle zehn `last_run: null`), und die Herkunftssperre stuft jeden Worktree als `"test"` ein und erzwingt dort den Sandbox-Key, der laut seven.io „nie sendet, nie kostet". Echter Versand ist strukturell nur mit Produktions-Herkunft möglich → gehört in #1533, und zwar als SKIPPED ausgewiesen, nicht als bestanden behauptet.
2. **`extra="ignore"` in den Settings verschluckt neue Felder still** (`config.py:90`). Ein `premium_sms_reply_to`, das nur in `with_user_profile` ergänzt wird, ohne auf der `Settings`-Klasse deklariert zu sein, verschwindet lautlos. Prüfort muss die *Wirkung* sein (kommt der Wert im POST-Body an?), nicht die Existenz des Zweigs.
3. **`force_test` bei Staging** (`config.py:292-293`) schaltet auf `for_testing()` um — auf Staging ist der Premium-Versand also grundsätzlich sandboxiert. Das ist gewollt, macht aber jede Staging-„Zustellung" zum Nicht-Beweis.
4. **Zwei unabhängige Dreier-Listen** (`alert_log.py:59`, `trip_alert.py:1446`) werden bei einem alarmfähigen Kanal beide gebraucht — eine zu vergessen erzeugt ein stilles Loch im Protokoll, keinen Testfehler.
5. **Kostenstelle hat kein Vorbild.** Gemessen: keine Kosten-, Kontingent- oder Versandzähler-Erfassung je Kanal im Produktivcode. Das einzige Mengengerüst ist das Tier-Tageslimit für Alarme (`user_tier.py:17-31`). Eine „eigene Kostenstelle" ist damit ein eigenes Feature, nicht ein Feld.
6. **`api/routers/notify.py:15` kennt SMS gar nicht** — der Testversand-Endpunkt unterstützt nur `email`/`telegram` (`channel_test_service.py:30-41`). Ein Premium-SMS-Testversand über diesen Weg existiert nicht und müsste neu gebaut werden.
7. **Go-Persistenz verliert unbekannte Felder** (typisierte Structs, voller Rewrite). Jedes neue Kanal-Flag braucht explizites Struct-Feld **und** expliziten Merge-Zweig im Handler.

## Empfohlener Schnitt (Begründung für Phase 2/3)

Der im Issue beschriebene S2-Umfang (vierter Kanal überall, Alarme, Vergleich, Kostenstelle) ist
für einen Workflow zu groß und stellt das Dringendste hinten an. Vorschlag:

- **S2a — Trip-Briefing als Premium-SMS.** Neuer Kanal, Absender fest, Empfänger = gelernte
  Rückadresse, fail-closed bei leer/veraltet, SMS-Zeichenlimit, Premium-Tier-Gate, Go-Flag mit
  Merge, Guards nach SMS-Vorbild, neues ADR. Damit wird #1533 durchführbar — das ist die Frist.
- **S2b — Alarm- und Vergleichspfad.** `_ALL_CHANNELS`, `trip_alert.py:1446`, Kanal-Schwellen,
  Erfolgs-Ratsche anheben (mit Spec-Nachzug), `api_contract.md`.
- **S2c — Kostenstelle.** Eigenes Feature ohne Vorbild im Bestand.

Der Schnitt ist auch technisch begründet, nicht nur zeitlich: S2a umgeht die Erfolgs-Ratsche
vollständig (`send_trip_report` ist verschont), S2b läuft zwangsläufig hinein.

---

# Analysis (Phase 2)

## Type

**Feature** — es fehlt Funktionalität, die es nie gab. Kein Fehlverhalten.

## Der Versandweg, lückenlos verfolgt

Go löst aus (`internal/scheduler/scheduler.go:279` → `POST /api/scheduler/trip-reports?user_id=…`,
ohne Body und ohne Kanalliste) → `api/routers/scheduler.py:26` →
`trip_report_scheduler.py:299 send_reports_for_hour()` →
`dispatch_orchestrator.py:165 run_briefing_dispatch()` →
`trip_report_scheduler.py:825 _send_trip_report_outcome()` →
`trip_report_scheduler.py:1067 _build_trip_report_request()` →
`notification_service.py:275 send_trip_report()`.

**Entscheidend: es gibt genau ZWEI Stellen, an denen S2a ansetzen muss.**

1. **Kanal-Entscheidung:** `trip_report_scheduler.py:1303` — die einzige maßgebliche Stelle:
   `send_sms=config is not None and config.send_sms and sms_allowed(self._user_id)`.
   Tier-Gate und Nutzerwunsch sitzen in derselben Zeile. (Strukturgleiche Zweitkopie in
   `:965`, aber nur für den „keine Wetterdaten"-Hinweis.)
2. **Sendezweig:** `notification_service.py:369-377`.

Ausdrücklich **nicht** beteiligt, gegen die Vermutung geprüft: `report_config_resolver.py`
(klassifiziert die Kanal-Flags als `RENDER_NEUTRAL`, `:63-66`), `scheduler_dispatch_service.py`
(Vergleichs-Pfad), `trip_alert.py::_briefing_channels()` (nur Vererbungs-Default für Alarme).

Der Zeitplan ist **kanal-gemeinsam** (`trip_report_scheduler.py:345-360, 591-601`): ein
Morgen-/Abend-Paar je Trip, kein kanalspezifischer Slot.

## Korrekturen an Phase 1 (selbst nachgemessen)

| Phase-1-Annahme | Messung | Folge |
|---|---|---|
| Premium-SMS braucht 153 Zeichen aus `CHANNEL_LIMITS`, sonst greift der stille Telegram-Rückfall | Der Briefing-Pfad liest `CHANNEL_LIMITS` **nie**. `trip_report.py:420` übergibt `max_length=160` fest. 153 ist die Segmentgrenze **verketteter** SMS, 160 die einer einzelnen. | **Premium-SMS übernimmt `report.sms_text` unverändert.** Kein zweiter Render-Pfad, kein `premium_sms_text`-Feld, kein `renderer_mail_gate`-Auslöser. Spart Aufwand *und* hält „komplette Kopie von SMS" wörtlich ein. |
| Go verliert unbekannte Felder → Struct-Änderung nötig | `Trip.ReportConfig` ist `map[string]interface{}` (`trip.go:112`), Merge feldweise über `config_merge.go:11-22`. Der Verlust trifft nur die abgeleiteten Flach-Felder `SendEmail/SendSms/SendTelegram` (`trip.go:161-163`). | **Keine Go-Änderung in S2a.** Der Schlüssel `send_premium_sms` lebt in `report_config` und übersteht Speichern/Laden. Das Flach-Feld ist reine Frontend-Bequemlichkeit → S3. Damit entfällt auch der `data_schema_backup.py`-Auslöser. |

## Neuer Fund: die Vorgabe „niemals aus `.env`" ist nicht von selbst erfüllt

`SettingsConfigDict(env_prefix="GZ_")` (`config.py:87`) gilt uniform für **jedes** deklarierte
Feld. Sobald `premium_sms_reply_to` ein reguläres Settings-Feld ist — und das muss es sein, weil
`extra="ignore"` (`config.py:90`) undeklarierte Werte lautlos verschluckt — wäre
`GZ_PREMIUM_SMS_REPLY_TO` ein funktionierender Override. Bei `sms_to`/`mail_to` ist dieselbe Lücke
bis heute nur betrieblich geschlossen (keine solche Zeile in `.env`). Da die Vorgabe hier
ausdrücklich „niemals" sagt, braucht es eine Code-Sperre, Vorbild `_resend_default_deny`
(`config.py:194-217`).

**Gegenprobe zur Nicht-Editierbarkeit:** `UpdateProfileHandler` (`internal/handler/auth.go:530-586`)
dekodiert in ein lokales Struct ohne dieses Feld, Go verwirft unbekannte JSON-Schlüssel. Die
Nutzer-API kann die Rückadresse also heute nicht setzen — für S2a ist nichts zu tun, aber dieses
Struct darf das Feld nie aufnehmen (Leitplanke für S3).

## Design-Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| **D1** | Gemeinsame Basisklasse `src/output/channels/seven_io_base.py`; `SMSOutput` und `PremiumSmsOutput` erben `send()` als Template-Method und füllen nur `_resolve_recipient()`/`_resolve_sender()`. `sms.py` wird im **selben** Commit umgestellt. | Die beiden Sicherheits-Sperren existieren dann genau einmal statt zweimal. Eine Kopie hätte die Vergessbarkeit verdoppelt, die sie vermeiden soll — und `test_channel_origin_guard_parity.py:85-155` prüft nur namentlich genannte Klassen, würde eine vergessene Sperre also nicht bemerken. Ein Varianten-Parameter an `SMSOutput` wäre technisch am dichtesten, verstößt aber gegen die PO-Vorgabe „eigener Kanal". |
| **D2** | Zwei deklarierte Settings-Felder `premium_sms_reply_to` / `premium_sms_reply_at`, gefüllt in `with_user_profile()` im Muster der bestehenden drei Zeilen — **plus** Validator-Sperre gegen `GZ_`-Override. | Einziger bestehender Profil→Settings-Übersetzer; ein zweiter Auflöser-Dienst würde die `get_data_dir()`-Lesung duplizieren und bei Test-Isolation abweichen können. |
| **D3** | Die Fail-closed-Prüfung sitzt **in** der Kanal-Klasse (`_resolve_recipient()` wirft `OutputConfigError`), nicht als `if` am Aufrufort. | Der bestehende SMS-Zweig prüft `can_send_sms()` **vor** dem `try` — ist das falsch, passiert schlicht nichts: kein Log, kein Ergebnisfeld. Für SMS tolerierbar, für Premium-SMS durch die Vorgabe „kein stiller Fehlschlag" verboten. |
| **D4** | Neues Feld `NotificationResult.blocked_channels: dict[str, str]` (Kanal → Grund). | Macht „nicht gesendet, weil …" **messbar** statt nur protokolliert. Ohne das wäre die Zusicherung nur an einer Logzeile prüfbar — und eine Logzeile ist kein Nachweis. |
| **D5** | `report.sms_text` unverändert wiederverwenden (160 Zeichen). | Siehe Korrektur oben. Ein eigener Render-Pfad würde Inhalt zwischen SMS und Premium-SMS auseinanderlaufen lassen. |
| **D6** | Verfallsfrist als Modul-Konstante. **Vorschlag: 30 Tage.** | Beide Fehlermodi sind asymmetrisch schlimm: zu kurz ⇒ selbstverschuldeter Briefing-Ausfall mitten auf der Tour (das Gerät meldet sich im Wesentlichen einmal zu Tourbeginn); zu lang ⇒ kostenpflichtige SMS an eine Nummer, die Garmin inzwischen einem fremden Gerät zugeteilt hat, mit HTTP 200 als Scheinerfolg. 30 Tage deckt mehrwöchige Touren und begrenzt die Fremdnummer-Aussetzung auf einen Monat. **Gestützt** auf die Annahme, dass Touren Tage bis wenige Wochen dauern; **widerlegt** durch reale Touren > 30 Tage (dann trip-gebunden statt fix) oder durch einen Messwert, dass seven.io/Garmin die Nummer schneller neu vergibt. Kein gemessener Wert → PO-Entscheidung. |
| **D7** | Neue Funktion `premium_sms_allowed(user_id)` — nur `premium`. | `sms_allowed()` lässt `standard` **und** `premium` durch (`user_tier.py:6-14`). Premium-SMS ist laut `epic_user_tiers_overview.md:29` Premium-Merkmal. Das Gate wiederzuverwenden wäre ein stiller Rechte-Ausweitung. |
| **D8** | Keine Go-Änderung in S2a. | Siehe Korrektur oben. |
| **D9** | Kanalname verbindlich `premium_sms`, festgelegt in einem neuen ADR, das ADR-0004 fortschreibt. | ADR-0004 sagt „nur noch drei Kanäle"; die Projektregel verlangt bei Abweichung ein neues ADR. Zuerst schreiben, damit der Name nicht mitten in der Umsetzung wandert. |

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `docs/adr/00XX-premium-sms-vierter-kanal.md` | CREATE | Schreibt ADR-0004 fort, legt `premium_sms` fest |
| `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | CREATE | Spec mit ACs (Phase 3) |
| `src/output/channels/seven_io_base.py` | CREATE | Guards + HTTP-Transport, Template-Method |
| `src/output/channels/premium_sms.py` | CREATE | Absender fest, Empfänger gelernt, Frische-Prüfung |
| `src/output/channels/sms.py` | MODIFY | Auf Basisklasse umstellen (schrumpft) |
| `src/output/channels/base.py` | MODIFY | `get_channel("premium_sms")` für CLI-Parität |
| `src/app/config.py` | MODIFY | 2 Felder, `with_user_profile()`, `can_send_premium_sms()`, ENV-Sperre |
| `src/services/notification_service.py` | MODIFY | Sendezweig in `send_trip_report()`, `blocked_channels` |
| `src/services/trip_report_scheduler.py` | MODIFY | `send_premium_sms` in beiden Aufrufstellen (`:965`, `:1303`) |
| `src/services/user_tier.py` | MODIFY | `premium_sms_allowed()` |
| `src/app/models.py` | MODIFY | `TripReportConfig.send_premium_sms` |
| `src/app/loader.py` | MODIFY | Feld beim Trip-Laden übernehmen |
| `src/output/renderers/channel_layout.py` | MODIFY | Defensiver `CHANNEL_LIMITS`-Eintrag (1 Zeile, Vorsorge für S3) |
| `tests/unit/test_premium_sms_versand.py` | CREATE | HTTP-Stub: Nutzlast, fail-closed, TTL-Kante, Guard-Parität |
| `tests/unit/test_config_premium_sms.py` | CREATE | Settings, Profil-Übernahme, ENV-Sperre |
| `tests/unit/test_user_tier.py` | MODIFY | `premium_sms_allowed` |
| `tests/tdd/test_channel_origin_guard_parity.py` | MODIFY | `PremiumSmsOutput` in die Parität aufnehmen |

Testdateien liegen bewusst unter `tests/unit/` — `touched_tests_gate.py:37` sucht nur dort;
in `tests/tdd/` gälte der Commit als „UNGEPRUEFT". Namen nach Verhalten, nicht nach Issue-Nummer.

## Scope Assessment

- **Dateien:** 4 CREATE (2 Code, 2 Test) + 2 CREATE Doku + 11 MODIFY
- **LoC:** Python netto ≈ **+150** (Basisklasse +80, Premium-Kanal +50, `sms.py` schrumpft ≈ −60, Rest +80) · Tests ≈ **+400** · Doku zählt nicht mit → erwartet **≈ +550**, LoC-Override nötig (PO-Erlaubnis liegt vor)
- **Risiko:** **MEDIUM.** Kein Bestandsverhalten wird verändert außer dem `sms.py`-Refactor — und der ist durch die bestehende SMS-Testsuite abgedeckt. Der Rest ist additiv.

## Nachweis-Plan

Naht: **echter lokaler HTTP-Stub** (`http.server` auf `127.0.0.1`), Vorbild
`tests/tdd/test_issue_936_sms_stub.py` und `test_issue_1069_tier_channel_gating.py` — kein Mock,
keine `patch()`. Messbar:

1. `payload["from"] == "4916092172595"`, auch wenn `sms_from`/`GZ_SMS_FROM` bewusst abweichend gesetzt ist
2. `payload["to"]` stammt aus der Fixture-`user.json`, **nicht** aus `Settings.sms_to` (Test setzt `GZ_SMS_TO` abweichend)
3. Rückadresse leer → **null** POSTs beim Stub **und** `blocked_channels["premium_sms"]` gesetzt
4. TTL-Kante beidseitig: Frist − 1 s sendet, Frist + 1 s sendet nicht
5. Text bitidentisch zu `report.sms_text`, Länge ≤ 160 unter Extremwetter-Fixture
6. Guard-Parität: Testlauf-Herkunft erzwingt Sandbox-Key bzw. bricht ohne ihn hart ab
7. `premium_sms_allowed("standard")` ist `False` — obwohl `sms_allowed("standard")` `True` ist
8. ENV-Sperre: `GZ_PREMIUM_SMS_REPLY_TO` im Prozess-Environment führt zum lauten Abbruch, nicht zum Override

**Mit keiner Naht beweisbar → #1533:** dass die SMS auf dem Gerät ankommt und dort lesbar ist.
Gemessene Gründe: die Herkunftssperre stuft jeden Pfad außer `/home/hem/gregor_zwanzig` als
Testlauf ein und erzwingt den Sandbox-Key („sendet nie, kostet nie"); `force_test` sandboxiert
Staging zusätzlich (`config.py:292`); der Staging-Scheduler führt ohnehin keinen Job aus. Das ist
als **SKIPPED** auszuweisen, nicht als bestanden.

## Reihenfolge

1. **ADR** — legt den Namen fest, bevor Code ihn trägt
2. **Settings-Datenebene** — isoliert prüfbar, noch ohne Kanal
3. **Kanal-Code** (Basisklasse + Premium + `sms.py`-Umstellung, ein Commit) — hier liegt der Kern-Nachweis
4. **Verdrahtung** (`notification_service`, beide Scheduler-Stellen, Tier-Gate, Modell/Loader) — Ende-zu-Ende gegen den Stub
5. **Defensiver `CHANNEL_LIMITS`-Eintrag** — letzter, kleinster Schritt

## Open Questions (für die Spec-Freigabe)

- [ ] **Verfallsfrist:** 30 Tage wie vorgeschlagen (D6)? Der Wert ist begründet, aber nicht gemessen.
- [ ] **Schnitt:** S2a jetzt (Briefing), S2b (Alarme/Vergleich) und S2c (Kostenstelle) danach?
