# Mini-Spec: Trip-Briefing protokolliert den E-Mail-Empfänger

Issue: [#1847](https://github.com/henemm/gregor_zwanzig/issues/1847) · Fast Track
Kontext & Beweisführung: `docs/context/fix-1847-briefing-versand-ohne-zustellung.md`

## Approval

- [x] Approved — PO Henning, 2026-08-15 („gogogo"). Freigegeben sind AC-1 bis AC-4 samt
  der drei benannten Tech-Lead-Entscheidungen: Empfänger **unmaskiert**, Endpoint-Status
  und `send()`-Signatur **außerhalb** dieser Scheibe, bekannte Grenze (konfigurierter statt
  post-Guard-Empfänger) akzeptiert.

## Anlass

#1847 wurde als „Staging meldet `sent:true`, es kommt keine Mail" gemeldet. Die Mail **war**
zugestellt — an `gregor-staging@henemm.com` statt an `gregor-test@henemm.com`, weil
`/var/lib/gregor-staging/users/default/user.json` ein abweichendes `mail_to` trug. Die
Diagnose kostete rund eine Stunde. Im **Ortsvergleich**-Pfad steht der Empfänger wörtlich im
Protokoll (`src/services/scheduler_dispatch_service.py:571`), weshalb dieselbe Falle dort am
2026-08-12 in einer Minute aufgeklärt war. Der Trip-Briefing-Pfad hat diese Zeile nicht.

Das ist die **vierte** Wiederholung derselben Falle (#1351, #1403, #1782, #1847). Diese
Scheibe zieht die bereits bewährte Zeile aus dem Compare-Pfad nach — sie erfindet keine neue
Regel, sie schließt eine Lücke gegenüber der bestehenden Norm.

## Was ändert sich

- `src/services/trip_report_scheduler.py`, Erfolgszweig bei :1578: die Zeile
  `Trip report sent: {trip.name} ({report_type})` nennt zusätzlich die **zugestellten Kanäle**
  und — sofern E-Mail dabei war — den **E-Mail-Empfänger** (`self._settings.mail_to`).
  Vorbild für Wortlaut und Detailtiefe: `scheduler_dispatch_service.py:571`.
- `src/services/trip_report_scheduler.py`, `_append_briefing_log()` (:1799-1830): der Eintrag
  bekommt zusätzlich den E-Mail-Empfänger, damit der Nachweis auch **nachträglich** führbar
  ist und nicht nur im flüchtigen Journal steht.

## Was darf sich nicht ändern

- **Der Erfolgs-/Fehlerzweig selbst.** Die Unterscheidung `no_channel_configured` /
  `not result.sent` / Erfolg (:1567-1578) bleibt unangetastet; es wird nur die vorhandene
  Erfolgszeile angereichert. Kein neuer Outcome, kein geänderter HTTP-Status.
- **Die Bedingung, wann `_append_briefing_log` überhaupt schreibt.** Ein Eintrag mit
  `channels=[]` würde der Cockpit-Kachel (#393/#1007) einen Versand vortäuschen — diese
  Zusicherung ist im Docstring festgehalten und bleibt gültig.
- **Bestehende Schlüssel im `briefing_log.json`-Eintrag** (`trip_id`, `kind`, `sent_at`,
  `channels`, `on_demand`). Es wird ausschließlich **ergänzt**. Go liest die Datei nur
  (`store.LoadBriefingLog`) und ignoriert unbekannte Felder — im Docstring bereits so
  dokumentiert, deshalb ist das Ergänzen abwärtskompatibel.
- **Der Empfänger wird nicht maskiert.** Bewusste Entscheidung: eine Maskierung wie
  `g***@henemm.com` hätte `gregor-test@` und `gregor-staging@` **nicht** unterscheidbar
  gemacht und damit genau den Zweck verfehlt. Der Compare-Pfad protokolliert ebenfalls
  unmaskiert; das Journal ist nur mit erhöhten Rechten lesbar.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivem E-Mail-Kanal und `mail_to = "gregor-test@henemm.com"`,
  When das Briefing erfolgreich versendet wird, Then enthält die Protokollzeile des
  erfolgreichen Versands die Zeichenkette `gregor-test@henemm.com` — geprüft am tatsächlich
  ausgegebenen Log-Datensatz, nicht am Quelltext.
- **AC-2:** Given derselbe erfolgreiche Versand, When danach `briefing_log.json` gelesen wird,
  Then trägt der neu angehängte Eintrag den E-Mail-Empfänger, und die Schlüssel `trip_id`,
  `kind`, `sent_at`, `channels`, `on_demand` sind unverändert vorhanden.
- **AC-3:** Given ein Trip, dessen einziger aktiver Kanal Telegram ist (kein E-Mail-Versand),
  When das Briefing erfolgreich versendet wird, Then nennt die Protokollzeile **keinen**
  E-Mail-Empfänger und der `briefing_log`-Eintrag behauptet keinen E-Mail-Empfänger — eine
  Zeile, die bei jedem Versand eine Adresse nennt, wäre keine Zustell-Aussage.
- **AC-4:** Given ein Trip, bei dem der E-Mail-Versand fehlschlägt und kein anderer Kanal
  zustellt, When der Versand ausgewertet wird, Then wird **keine** Erfolgszeile
  protokolliert und **kein** `briefing_log`-Eintrag geschrieben; die bestehende
  Fehlerzeile `E-Mail send failed …` bleibt unverändert und die Ausnahme wird unverändert
  weitergereicht.

  > **Korrektur 2026-08-15 (nach PO-Freigabe, Substanz unverändert).** Die freigegebene
  > Fassung verlangte hier die Warnzeile `Trip report NOT sent …`. Das ist am Code nicht
  > erreichbar und war ein Fehler in dieser Spec, nicht in der Umsetzung: bei leerem
  > `sent_channels` wirft `notification_service.py:527-528` die Ausnahme weiter,
  > `trip_report_scheduler.py:1522-1535` fängt sie, schreibt Fehlervermerk und Anker und
  > reicht sie durch — die Dreier-Auswertung bei :1566-1578 wird nie betreten. Die
  > Warnzeile gehört zum Fall „Kanal konfiguriert, aber unerreichbar" (Telegram) und ist
  > dort bereits von `tests/unit/test_trip_send_endpoint_no_channels.py` abgedeckt.
  > **Die zugesicherte Wirkung ist dieselbe:** kein stiller Erfolg, kein Log-Eintrag.
  > Gefunden vom Developer-Agent vor dem ersten Edit, vom Orchestrator am Code
  > gegengeprüft.

## Manuelle Test-Schritte

1. Auf Staging ein Briefing unter `user_id=default` auslösen:
   `curl -X POST "http://localhost:8001/api/scheduler/trips/<id>/send?user_id=default&report_type=morning"`
2. `sudo -n journalctl -u gregor-python-staging | grep "Trip report sent" | tail -1` →
   die Zeile nennt `gregor-test@henemm.com`.
3. `sudo -n python3 -c "import json;print(json.load(open('/var/lib/gregor-staging/users/default/briefing_log.json'))['entries'][-1])"`
   → der Eintrag trägt denselben Empfänger.
4. Gegenprobe im Postfach (`GZ_TEST_IMAP_USER`): die Mail liegt bei genau dieser Adresse.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] AC-1/AC-2: Versand über den **echten** Pfad, nur `EmailOutput._dial_and_send`
      ersetzt (nicht `_send_email`, nicht `can_send_email` — beides hängt genau die Stellen
      aus, an denen der Empfänger sichtbar würde; siehe
      `tests/unit/test_trip_send_endpoint_no_channels.py:160-178` als Gegenbeispiel).
      Prüfung über `caplog` und die geschriebene `briefing_log.json`.
- [ ] AC-3: Telegram-only-Trip — Zusicherung, dass keine Adresse auftaucht. **Zweiter
      Netzrand PFLICHT:** zusätzlich `TelegramOutput._post` ersetzen und Dummy-Zugangsdaten
      per `monkeypatch.setenv` setzen, sonst sendet der Testfall echt an Telegram. Anlass
      ist kein hypothetisches Risiko: am 2026-08-03 gingen so echte Nachrichten an den
      Produktiv-Chat des PO (#1477).
- [ ] AC-4: E-Mail-Fehler ohne Ersatzkanal — Warnzeile bleibt, kein Log-Eintrag.
- [ ] Mutations-Gegenprobe: Empfänger aus der Log-Zeile entfernen ⇒ AC-1 muss rot werden.

## Nicht in dieser Scheibe

- **`api/routers/scheduler.py:286`** (`"sent": True` hartkodiert). Real, aber eigenes Thema —
  bereits als Verstoß **B1** in `tests/test_success_status_guard.py:1518` geführt.
- **`EmailOutput.send() -> None`** (kein Erfolgssignal an den Aufrufer, Klasse 4 desselben
  Wächters). Eine Signaturänderung dort zieht das Renderer-Commit-Gate (#811) nach sich und
  gehört in eine eigene Scheibe.
- **Telegram-/SMS-/Premium-SMS-Empfänger.** Diese Scheibe adressiert die belegte Falle
  (E-Mail-Postfach). Für die anderen Kanäle ist keine entsprechende Fehlklasse belegt.

## Bekannte Grenze

Protokolliert wird der **konfigurierte** Empfänger (`settings.mail_to`), den
`_send_email` ohne `to=`-Override an den Kanal gibt (`notification_service.py:1726-1745`,
`email.py:643-650`). Die Herkunftssperre #1476 (`email.py:655-663`) kann den Empfänger im
Kanal noch umschalten — das greift ausschließlich bei Testlauf-Herkunft und ist im
Serverbetrieb nicht erreichbar. Im gemeldeten Fehlerbild sind konfigurierter und
tatsächlicher Empfänger deshalb identisch, und die Zeile hätte #1847 in einer Minute
aufgeklärt. Der post-Guard-Wert wäre nur über eine Signaturänderung an `send()` zu bekommen —
siehe „Nicht in dieser Scheibe".
