# Context: fix-1847-briefing-versand-ohne-zustellung

Issue: [#1847](https://github.com/henemm/gregor_zwanzig/issues/1847) · Label `bug`, `priority:high`
Track: Full Process (Intake-Score 5/6)

## Request Summary

`POST /api/trips/<id>/send` antwortet auf Staging mit `{"status":"ok","sent":true}` und
protokolliert `Trip report sent`, ohne dass eine E-Mail zugestellt wird. Betroffen ist damit
nicht nur das Feature, sondern der **Nachweisweg** aller Mail-Gates
(`renderer_mail_gate.py` → `briefing_mail_validator.py` verlangt eine echt zugestellte Mail).

## 🔴 AUFGELÖST (2026-08-15): Die Mail WURDE zugestellt — #1847 ist als Bug ungültig

**Beweis.** Beide vermissten Mails liegen in `gregor-staging@henemm.com`, sekundengenau
passend zu den Log-Zeilen:

```
Subject: [E2E 1671 Kompakt-Ausblick] Etappe 1 — Abend    To: gregor-staging@…  14 Aug 19:24:43
Subject: [E2E 1671 Kompakt-Ausblick] Etappe 1 — Morgen   To: gregor-staging@…  14 Aug 19:41:02
Log:     Trip report sent … (evening) 19:24:43,090  /  (morning) 19:41:02,918
```

**Ursache.** `/var/lib/gregor-staging/users/default/user.json` enthält
`mail_to: "gregor-staging@henemm.com"`, geschrieben am **2026-08-14 16:08**. Die
Sicherungskopie `user.json.bak-1243` (2026-07-14) hat **kein** `mail_to` — der Schlüssel wurde
an diesem Tag neu hinzugefügt. `with_user_profile()` übernimmt ihn (`src/app/config.py:385-386`)
und leitet damit jeden `default`-Versand am Test-Postfach vorbei.

**Warum es niemand sah — der eigentliche Fehler in der Beweisführung.** Die Systemd-Unit setzt
`Environment=GZ_DATA_DIR=/var/lib/gregor-staging` (Drop-in `1595-datenwurzel.conf`, #1595).
Der Ordner `/home/hem/gregor_zwanzig_staging/data/`, in dem das Ticket „KEIN `user.json`"
festgestellt hat, ist **Altbestand und wird vom Dienst nicht gelesen**. Dieselbe Falle hat auch
meine erste Gegenmessung getroffen: `Settings().with_user_profile('default')` ohne gesetztes
`GZ_DATA_DIR` liefert `mail_to='gregor-test@henemm.com'` — das misst die stillgelegte
Datenwurzel, nicht die des Dienstes. **Vor jeder Aussage über Staging-Nutzerdaten:
`systemctl cat <dienst> | grep GZ_DATA_DIR`.**

**Zeitleiste, die es bestätigt:**

| Zeit (UTC, 14.08.) | Ereignis | Postfach |
|---|---|---|
| 16:06:07 | `e2e-1680-s5b-origin` (User `default`) | **gregor-test** ✅ |
| 16:08 | `user.json` bekommt `mail_to: gregor-staging@` | — |
| 17:19:12 | `e2e-1801-ampel-check` (User `default`) | **gregor-staging** |
| 19:24:43 / 19:41:02 | `e2e-1671-kompakt` (User `default`) | **gregor-staging** |
| 15.08. 05:00:33 | Kontrollversand User `validator-issue110` (eigenes Profil) | **gregor-test** ✅ |

Der Kontrollversand belegt zugleich: der Versandweg auf dem **aktuellen** Staging-Stand
(`57e36375`) ist intakt. Es ist kein Code-Regress und keine Infrastrukturstörung.

**Vierte dokumentierte Wiederholung** derselben Falle — nach #1351, #1403, #1782.
Siehe [[reference_two_test_mailboxes_imap_user_trap]],
[[reference_staging_compare_versand_meldet_ok_ohne_zustellung]].

## Was davon trotzdem eine echte Aufgabe bleibt

Die Diagnose kostete rund eine Stunde, weil der Trip-Briefing-Pfad den Empfänger **nicht**
protokolliert. Im Compare-Pfad steht er wörtlich im Log — dort war dieselbe Falle 2026-08-12
in einer Minute aufgeklärt. Das Ticket sagt das selbst und hat damit recht; nur seine
Ursachen-Diagnose war falsch. Der verbleibende, tragfähige Kern steht unten unter
„Verbleibender Zuschnitt".

### Weitere Spuren aus dem Staging-Journal

```
19:24:36  POST …/send?report_type=evening&user_id=default → 409 Conflict   (Idempotenz-Lock #1756)
19:24:43  INFO trip_report_scheduler: Trip report sent: E2E 1671 Kompakt-Ausblick (evening)
19:41:02  INFO trip_report_scheduler: Trip report sent: E2E 1671 Kompakt-Ausblick (morning)
19:41:02  POST …/send?report_type=morning&user_id=default → 200 OK
```

- Der Versand dauert **~0,7 s** und hinterlässt **keine SMTP-Spur** — weder Erfolg noch Fehler.
- Der erste Versuch (19:24:36) lief auf **409**; das `Trip report sent` 7 s später gehört zu
  einem anderen Aufruf.
- Auf Staging ist der Egress-Wächter aktiv und blockt sichtbar externe Hosts
  (`EgressBlockedError` für `ensemble-api.open-meteo.com`, `warnungen.zamg.at`). Ob er auch
  den SMTP-Weg trifft, ist **nicht geprüft**.
- Staging-SMTP: `GZ_SMTP_HOST=mail.henemm.com`, Port 587, User `gregor-test` → also der
  **Stalwart-/Nicht-Resend-Pfad** in `email.py`, nicht Resend.

### Verbleibender Zuschnitt (Vorschlag nach der Auflösung)

1. **Empfänger im Trip-Briefing-Pfad protokollieren** — Vorbild
   `scheduler_dispatch_service.py:571`. Verhindert Wiederholung Nr. 5.
2. **Empfänger in `_append_briefing_log()` mitschreiben** (:1799-1830 schreibt heute nur
   `channels`) — damit der Nachweis auch nachträglich führbar ist.
3. **`api/routers/scheduler.py:286`** (`"sent": True` hartkodiert) — bekannter, geduldeter
   Verstoß B1 in `tests/test_success_status_guard.py:1518`. Unabhängig von #1847 real,
   aber ein **eigener** Zuschnitt.
4. **Entscheidung nötig:** Soll `default` auf Staging weiter nach `gregor-staging@` senden?
   Die Mail-Validatoren lesen `GZ_TEST_IMAP_USER` (= `gregor-test`), d.h. der dokumentierte
   Nachweisweg über einen `default`-Trip trägt so nicht.

### Nicht mehr zutreffend — Spuren aus der ursprünglichen Fehlersuche

*Der folgende Abschnitt entstand vor der Auflösung und wird nur als Protokoll aufbewahrt.*

### Was diese Spuren logisch erzwingen

`NotificationService` hängt `sent_channels.append("email")` **nach** `_send_email` an
(`src/services/notification_service.py:403-409`); `sent = bool(sent_channels)`
(:538-541). Die Erfolgszeile `Trip report sent` (`trip_report_scheduler.py:1578`) feuert nur
bei `result.sent`. Und `EmailOutput.send()` signalisiert Fehler **ausschließlich per Exception**
(`src/output/channels/email.py:607-616`, Rückgabetyp `-> None`).

⇒ `EmailOutput.send()` ist ohne Exception zurückgekehrt. Der Versand wurde also
**angenommen** und ist danach verschwunden. Die Analyse muss zwischen mindestens diesen
Möglichkeiten entscheiden:

1. SMTP-Übergabe an Stalwart erfolgreich, Zustellung danach verworfen (Stalwart-seitig).
2. Ein Guard hat den Empfänger stillschweigend umgeschrieben — `email.py:655-663`
   (`running_origin(...) == "test"` → Umschaltung auf `_ORIGIN_GUARD_TEST_RECIPIENT`).
3. Der Trip trug einen eigenen Empfänger-Override (`to=…`), der ins Leere lief.
4. Egress-Guard greift auf dem SMTP-Weg, ohne dass es eine Exception gibt.

Möglichkeit 2 ist deshalb aussichtsreich, weil sie eine **stille Umschaltung mit
Warn-Log** ist — und im Journal-Ausschnitt keine Warnung stand, was sie wiederum
unwahrscheinlich macht. **Nicht raten, messen.**

## Related Files

| File | Relevance |
|------|-----------|
| `api/routers/scheduler.py:204-286` | Endpoint `POST /trips/{trip_id}/send`. **Zeile 286: `return {"status": "ok", …, "sent": True}` ist hartkodiert** — der Erfolgsstatus folgt keinem Ergebnis. |
| `src/services/trip_report_scheduler.py:1141-1634` | `_send_trip_report_outcome()` — leitet `no_stage`/`no_weather`/`no_channels`/`channels_unreachable`/`sent` ab. Erfolgs-Log :1578 **ohne Empfänger**. |
| `src/services/trip_report_scheduler.py:405` | `Settings().with_user_profile(user_id)` — eine von **zwei unabhängigen** Auflösungen desselben Werts. |
| `src/services/notification_service.py:384-541` | `no_channel_configured` :384-391 · E-Mail-Versand :403-409 · `sent=bool(sent_channels)` :538-541 · Fehler-Weitergabe :527-529 (E-Mail-Fehler wird verschluckt, sobald **irgendein** anderer Kanal zustellte). |
| `src/app/config.py:355-402` | `with_user_profile()` — **drei stille `return base`**: fehlende Datei :376-377, JSON-/OSError :379-381, keine Overrides :400-401. |
| `src/app/config.py:148` | `mail_to: Optional[str]` — **ein einzelner String**, keine Empfängerliste. Die Ticket-Formulierung „Empfängerliste" existiert im Trip-Pfad nicht. |
| `src/app/config.py:305-312` | `can_send_email()` — die einzige Stelle, an der ein leeres `mail_to` überhaupt auffällt (→ 422 im Router :226-229). |
| `src/output/channels/email.py:607-616` | `send() -> None` — **kein Rückgabewert**, kein Early-Return; Fehlersignal nur per Exception. |
| `src/output/channels/email.py:643-650` | Empfänger-Fallback `recipients = list(to) if to else [self._to]`. |
| `src/output/channels/email.py:655-663` | **Herkunftssperre #1476** — bei Testlauf-Herkunft wird der Empfänger still auf die Test-Mailbox umgeschaltet (mit `logger.warning`). |
| `src/output/channels/email.py:713-770` | Empfänger-Guards: Resend-Allowlist (#1147/#1219) und Lokal-Guard (#1235). Beide werfen `OutputConfigError` — nie stiller Erfolg **innerhalb** des Kanals. |
| `src/services/scheduler_dispatch_service.py:410-415, 554, 571` | **Das Vorbild:** Compare-Pfad leitet `default_to` her, wirft `ValueError` bei fehlendem `mail_to` (fail-loud) und protokolliert `Compare preset %s sent to %s`. |

## Existing Patterns

- **Fail-loud vor dem Versand** (Compare-Pfad, `scheduler_dispatch_service.py:410-415`):
  Empfänger explizit herleiten, bei Fehlen `ValueError` werfen. Für den Trip-Briefing-Pfad
  existiert dieses Muster **nicht**.
- **Empfänger protokollieren** (Compare-Pfad, :571). Im Trip-Pfad kommt `mail_to`/`recipient`
  im gesamten Modul nicht vor; `_append_briefing_log()` :1799-1830 speichert nur `channels`,
  keine Adresse.
- **Outcome-Enum statt Boolean** (`trip_report_scheduler.py`): der Router hat für jeden
  Negativ-Outcome bereits einen eigenen 422-Zweig (#1403, #1325, #904, #1756). Das Muster
  ist etabliert — eine neue Ursache bekommt einen neuen Zweig, keine neue Mechanik.
- **Teilungsregel Trip ↔ Compare** (CLAUDE.md): Der Compare-Pfad kann hier ausnahmsweise als
  Referenz dienen, weil er dieselbe Frage bereits gelöst hat.

## Dependencies

- **Upstream:** `Settings` / `with_user_profile()` (`src/app/config.py`) ·
  `NotificationService` · `EmailOutput` + `build_mime_message` · Stalwart auf
  `mail.henemm.com:587` · Egress-Guard (`src/app/egress_guard.py`).
- **Downstream:** Go-API-Proxy (`internal/`) → Frontend-Sende-Dialog ·
  Go-Cron-Scheduler (ruft denselben Dienst stündlich) · **`briefing_mail_validator.py` und
  `renderer_mail_gate.py`** (der Nachweisweg selbst) · Alarm-Pfad, der über
  `_briefing_channels()` erbt.

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/waechter_1405_erfolg_wirkung.md` | AST-Wächter „Erfolg heißt Wirkung" (#1405). Belegte Vorfälle #1290/#1346/#1348/#1403 — **#1847 ist der nächste derselben Klasse.** |
| `docs/specs/modules/waechter_1405_stille_aufloesung.md` | Hälfte A — stille Auflösung. |
| `docs/specs/modules/fix_1756_send_idempotenz_lock.md` | Der 409 um 19:24:36. |
| `docs/specs/modules/fix_1662_versandfehler_nachliefern.md` · `fix_1629_briefing_anker_versandfehler.md` | Vorhandene Behandlung von Versandfehlern im Briefing-Pfad. |
| `docs/specs/modules/fix_1412_s3a_transport_kapselung_mail.md` | Transport-Kapselung Mail. |
| `docs/reference/mail_validators.md` | Der bedrohte Nachweisweg. |

## Bestehende Wächter — und ihre Lücke

- `tests/test_success_status_guard.py:1518-1520` **listet genau diesen Endpoint als bekannten,
  geduldeten Verstoß**:
  `"api/routers/scheduler.py::send_test_trip_report::0": "B1 (#1403/#1405) — send_test_trip_report: 'sent': True trotz outcome."`
  Der Wächter prüft laut eigenem Docstring (:135-142) **nicht**, ob alle Rückgabewerte
  abgedeckt sind — nur, ob der Status überhaupt vom Aufrufergebnis abhängt.
- `tests/unit/test_trip_send_endpoint_no_channels.py` deckt `no_channels` und
  `channels_unreachable` ab — **schließt den Empfänger-Fall aber strukturell aus**:
  `_patch_can_send_email` :169-178 setzt `can_send_email → True`, `_patch_email_transport`
  :160-165 ersetzt `NotificationService._send_email`. Beide Stellen, an denen ein
  Empfänger-Problem auffallen würde, sind ausgehängt.
- `tests/tdd/test_compare_alert_recipient_settings.py:448-462` sichert „kein stiller Erfolg"
  für den **Compare**-Pfad. **Kein Pendant für den Trip-Briefing-Pfad.**
- Kein Test behauptet „Empfänger-Problem ⇒ kein `sent=true`" für `POST /trips/{trip_id}/send`.

## Risks & Considerations

1. **Die Ursache ist unbekannt.** Der einzige dokumentierte Erklärungsansatz ist widerlegt.
   Die Analyse-Phase muss zuerst die Zustellung instrumentieren, bevor irgendetwas geändert
   wird — sonst härtet man den falschen Pfad
   ([[feedback_adversary_may_harden_the_wrong_path]]).
2. **Prüfort = Wirkort.** Ein Test, der `_send_email` oder `can_send_email` mockt, kann diesen
   Bug per Konstruktion nicht sehen — genau daran scheitert der bestehende Test heute. Der
   RED-Test muss bis zum echten Sendezweig laufen und darf nur den Steckdosenrand
   (`EmailOutput._dial_and_send`) ersetzen ([[reference_mail_sink_verdeckt_den_echten_sendeweg]]).
3. **Zwei unabhängige Settings-Auflösungen** (Router :226 und Service :405) können
   auseinanderlaufen — ein Riegel an nur einer Stelle wirkt nicht.
4. **E-Mail-Fehler werden verschluckt**, sobald ein anderer Kanal zustellte
   (`notification_service.py:527-529`). Ein Fix, der nur `sent` korrigiert, lässt den
   Teilausfall weiter unsichtbar.
5. **Der Wächter aus #1405 muss mitgezogen werden**: wird Zeile 286 repariert, muss der
   Eintrag aus der Verstoß-Liste in `test_success_status_guard.py` **entfernt** werden —
   sonst behauptet der Wächter weiter einen Verstoß, den es nicht mehr gibt.
6. **Staging-Egress-Guard** ist aktiv und blockt externe Hosts. Jede Messung auf Staging muss
   das mitdenken; ein lokal grüner Versandweg beweist dort nichts.
7. **Nachweis-Aufwand mitschätzen:** Der Nachweis braucht eine echt zugestellte Staging-Mail
   plus IMAP-Gegenprobe im richtigen Postfach — nicht nur einen grünen Unit-Test.
