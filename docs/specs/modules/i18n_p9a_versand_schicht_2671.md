---
entity_id: i18n_p9a_versand_schicht_2671
type: module
created: 2026-10-30
updated: 2026-11-01
status: approved
version: "1.1"
tags: [i18n, epic-2644, issue-2671, python, model-haiku]
---

# i18n P9a: Versand-Schicht zweisprachig (Betreffe, `X-GZ-Lang`, Benachrichtigungstexte, Test-Versand)

**Issue:** #2671 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 1, 4, 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Englisch gewählt hat, bekommt Betreffzeilen, Ausfall- und Vorschau-Hinweise, den Test-Versand und die Fehlermeldungen des Handversands auf Englisch; jede E-Mail trägt den Marker `X-GZ-Lang`, aus dem die Mail-Validatoren ihre Erwartungen bilden. Die Versand-Schicht ist der Ort, an dem alle bereits zweisprachigen Renderer (P2 bis P8) zusammenlaufen: sie liest die Sprache des Nutzers einmal und reicht sie an jeden Renderer und Kanal weiter. Deutsch bleibt byte-gleich.

## Source

- **File:** `src/output/channels/email.py`, `src/output/subject.py`, `src/services/notification_service.py`, `src/services/send_outcomes.py`, `src/services/channel_test_service.py`, `api/routers/briefings_send.py`, `src/output/renderers/trip_report.py`
- **Identifier:** `build_mime_message` (email.py:306), `EmailOutput.send` (email.py:657), `build_email_subject` (subject.py:148), `_report_type_label`/`_translate_risk` (subject.py:45/51), `NotificationService.__init__` (notification_service.py:607), `_AMTL_HINWEIS_SMS_TOKEN` (66), `send_no_data_hint` (968), `_send_telegram_incomplete_hint` (946), `_apply_prefixes` (2361), `SEND_OUTCOMES`/`error_body` (send_outcomes.py:12/63), `send_test_message` (channel_test_service.py:41), `_sperre_email` (19)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/channels/`, `src/output/`, `src/services/`, `api/routers/`). Kein Go-, kein Frontend-Code. Die Nutzersprache liegt in `data/users/<id>/user.json` (`language`, Feld aus S1) und wird mit `resolve_user_lang(user_id)` gelesen, der `user_id` aus dem Auth-Kontext (Go-Proxy setzt sie; im Router die Query-Variable `user_id`).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Alle Texte dieses Pakets bedienen beide Flächen (Trip-Briefing, Ortsvergleich-Briefing, Handversand beider Arten, Test-Versand). Sie liegen in `versand.*`; es entsteht kein Trip- oder Compare-Pendant. `SEND_OUTCOMES` ist schon die geteilte Zuordnung für beide.
> - **Mandantentrennung:** `NotificationService` ist je Nutzer instanziiert (`NotificationService(settings, user_id)`); die Sprache wird **einmal im Konstruktor aus dieser `user_id`** gelesen und am Objekt gehalten, nicht modulglobal. `user_id` kommt aus dem Auth-Kontext, nie `"default"` (`_require_user()` bleibt fail-closed). AC-4 beweist mit **zwei Nutzern verschiedener Sprache im selben Prozess und Lauf**, dass jeder seine Sprache bekommt.
> - **Kanäle:** Briefing- und Alarm-Inhalt. E-Mail (Betreff, Header, Hinweise) und Telegram im Normalstil (`render_telegram_incomplete_hint`, Alarm-/Briefing-Renderer, Ausfall-Meldung) folgen der Nutzersprache; die Weitergabe von `lang` an alle Langform-Renderer-Aufrufe ist Teil dieses Pakets. **PO-Korrektur 2026-10-31** (ADR-0104 Präzisierung): SMS, Premium-SMS und der Telegram-Kurzstil bleiben in JEDER Sprache byte-gleich zu heute. `_AMTL_HINWEIS_SMS_TOKEN` (`+ amtl. Warnung s. E-Mail/Telegram`) bleibt deutsch, es gibt keinen Schlüssel `versand.sms.amtl_hinweis`; der SMS-/Premium-SMS-Text der Ausfall-Meldung bleibt deutsch; die SMS-Renderer (`render_alert_sms`, `render_official_alert_sms*`, `format_sms`) bekommen kein `lang`.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/channels/email.py` | MODIFY | `build_mime_message(..., lang: str = "de")` setzt den Header `X-GZ-Lang` in beiden Zweigen (HTML und Plain); `EmailOutput.send(..., lang: str = "de")` reicht ihn weiter (Aufruf Zeile ~855). Operator-Texte (`Test-Versand über Resend ist gesperrt.`, Herkunftssperre, Zeilen 454-456, 726, 807, 839) bleiben deutsch und erhalten `# i18n-log` |
| `src/output/subject.py` | MODIFY | `build_email_subject(token_line, *, max_length=78, lang="de")`; `_report_type_label(report_type, lang)`, `_translate_risk(risk, lang)` über Katalog; `_REPORT_TYPE_DE`/`_RISK_DE` werden `_REPORT_TYPE_KEYS`/`_RISK_KEYS` (Grep zuerst nach Importen in `tests/`) |
| `src/output/renderers/trip_report.py` | MODIFY | Nur Durchreichen: `_generate_subject(...)` (Zeile 892) ruft `build_email_subject(..., lang=lang)` |
| `src/services/notification_service.py` | MODIFY | `self._lang` im Konstruktor; `lang=self._lang` an alle `EmailOutput(...).send(...)`-Aufrufe (Zeilen ~997, 1379, 1514, 1712, 2067, 2232 und die übrigen) und an alle Renderer-Aufrufe (`render_email`, `render_subject`, `render_telegram`, `render_sms`, `render_official_alert_*`, `render_telegram_bubbles`, `render_telegram_incomplete_hint`, `render_compare_*`); eigene Texte: `send_no_data_hint` (986-990; SMS/Premium-SMS-Text bleibt deutsch, PO-Korrektur 2026-10-31), `_AMTL_HINWEIS_SMS_TOKEN` (66) bleibt unverändert, `_apply_prefixes` (2363-2372), Betreff Zeile 2452, `context_label="Ortsvergleich"` (1654) |
| `src/services/send_outcomes.py` | MODIFY | `SEND_OUTCOMES: dict[str, tuple[int, str]]` hält (Status, **Katalogschlüssel**) statt deutschem Text; `error_body(code, *, lang="de", **values)` löst über `t(key, lang, **values)` auf; `SendOutcomeError`-Meldung und Code bleiben (Betreiber-Text) |
| `src/services/channel_test_service.py` | MODIFY | `send_test_message(channel, user_id)` liest `lang = resolve_user_lang(user_id)` und nutzt `t("versand.test.*", lang)`; `_sperre_email(user_id, lang)`; Betreff, Text, Sperrtext, `Unbekannter Kanal` über Katalog |
| `api/routers/briefings_send.py` | MODIFY | Hilfsfunktion `_err(...)` (Zeile ~27) gibt `lang=resolve_user_lang(user_id)` an `error_body`; `user_id` ist die vorhandene Query-Variable |
| `src/services/inbound_telegram_reader.py`, `inbound_email_reader.py`, `inbound_sms_reader.py` | unverändert | Inbound-Antworten gehören zu P10 (#2673) |
| `src/i18n/messages/de/versand.json`, `src/i18n/messages/en/versand.json` | MODIFY | Neue Schlüssel `versand.*` (nur diese Bereichsdateien anfassen) |
| `tests/golden/versand/betreffe.de.txt`, `betreffe.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen) und Referenz `en`: Betreffe, Ausfall-Hinweis, Vorschau-Hinweise, Test-Versand, SMS-Hinweis (in `en` byte-gleich zu `de`), Fehlertexte |
| `tests/golden/test_versand_texte_golden.py` | CREATE | Byte-Vergleich `de` |
| `tests/test_versand_zweisprachig.py` | CREATE | Verhaltenstests der ACs 1, 2, 5, 6 |
| `tests/test_versand_zwei_nutzer_sprachen.py` | CREATE | Zwei-Nutzer-Test (AC-4) über die Sink-Naht |

## Estimated Scope

- **LoC:** ca. 150 Code (notification_service ~70 Aufrufstellen und Texte, subject ~25, send_outcomes ~20, channel_test_service ~20, email ~12, Rest Einzeiler); ohne Katalogdaten und Tests
- **Files:** 7 Code-Dateien, 2 Katalogdateien plus Tests und Golden-Dateien
- **Effort:** medium (`notification_service.py` hat 2.400 Zeilen; die Weitergabe von `lang` ist mechanisch, aber breit)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2646 S1 | Paket | `language` in `user.json`, `resolve_user_lang(user_id)` |
| #2662 P1 | Paket | `t`, `tn`, `fmt_date_numeric` (von P4 ergänzt) |
| #2663 PV | Paket | Marker `X-GZ-Lang` und sprachfähige Validatoren (PV legt das Gerüst; P9a macht den Wert nutzerabhängig) |
| #2664 bis #2670 (P2 bis P8) | Pakete | Die Renderer akzeptieren `lang`; P9a reicht es an jeden Aufruf |
| #2672 P9b (danach) | Paket | Scheduler-/Alarm-Orchestrierung ruft `NotificationService(settings, user_id, lang=...)` mit der einmal je Nutzer gelesenen Sprache |
| #2674 P11 (danach) | Paket | übrige `api/routers/**`-Meldungen und die Ratsche |
| `app.loader.get_data_dir` | Funktion | Pfadlogik, die `resolve_user_lang` benutzt |
| ADR-0104, ADR-0095, ADR-0003 | ADR | Sprache am Nutzer; Kanal-Parität; Mandantentrennung ohne `"default"` |

## Implementation Details

**Katalog-Namensraum:** `versand` (`src/i18n/messages/{de,en}/versand.json`). Nur diese beiden Dateien anfassen. das im Glossar verbotene Produktwort ist untersagt. Glossar: Versand = delivery, Briefing = briefing.

**Sprache im Dienst:** `NotificationService.__init__(settings=None, user_id=None, *, lang: Lang | None = None)`: `self._lang = lang or (resolve_user_lang(user_id) if user_id else "de")`. Die Sprache ist ein Attribut der Instanz (je Nutzer), nie Modul- oder Klassenvariable. P9b übergibt `lang`, damit der Scheduler sie nicht doppelt liest.

**Header (Abschnitt 4):** `build_mime_message(..., lang: str = "de")` setzt `msg["X-GZ-Lang"] = lang if lang in ("de", "en") else "de"` in **beiden** Zweigen (HTML ab Zeile 343, Plain ab Zeile 370), direkt neben `X-GZ-Mail-Type`. Der Header ist immer gesetzt (auch bei `de`), damit die Validatoren nach A2 Pflicht prüfen können.

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `versand.betreff.bericht.morgen` | `Morgen` | `Morning` | `_REPORT_TYPE_DE`, subject.py:18 |
| `versand.betreff.bericht.abend` | `Abend` | `Evening` | subject.py:19 |
| `versand.betreff.risiko.gewitter` | `Gewitter` | `Thunderstorm` | `_RISK_DE`, subject.py:27 |
| `versand.betreff.risiko.kaelte` | `Kälte` | `Cold` | subject.py:30 |
| `versand.betreff.wetterdaten_fehlen` | `[{trip}] Wetterdaten nicht verfügbar` | `[{trip}] Weather data unavailable` | notification_service.py:986 |
| `versand.betreff.wetterdaten_fehlen_ascii` | `[{trip}] Wetterdaten nicht verfuegbar` | `[{trip}] Weather data unavailable` | notification_service.py:2452 |
| `versand.hinweis.wetterdienst_ausfall` | `Wetterdienst aktuell nicht erreichbar — wir versuchen es weiter und liefern das Briefing nach, sobald Daten verfügbar sind.` | `Weather service currently unavailable — we keep trying and will deliver the briefing as soon as data is available.` | notification_service.py:987-990 |
| `versand.hinweis.test_vorschau` | `Test-Vorschau für {etappe} am {datum}` | `Test preview for {etappe} on {datum}` | notification_service.py:2368 |
| `versand.hinweis.auf_anfrage` | `Briefing auf Anfrage für {etappe} am {datum}` | `Briefing on request for {etappe} on {datum}` | notification_service.py:2372 |
| `versand.etappe.rueckfall` | `Etappe` | `Stage` | notification_service.py:2363 |
| `versand.test.betreff` | `Gregor 20 — Testmeldung` | `Gregor 20 — Test message` | channel_test_service.py:51 |
| `versand.test.text` | `Dein Kanal funktioniert!` | `Your channel works.` | channel_test_service.py:52 |
| `versand.test.kanal_unbekannt` | `Unbekannter Kanal: {kanal}` | `Unknown channel: {kanal}` | channel_test_service.py:77 |
| `versand.test.mail_gesperrt` | `Die Testmail wurde nicht gesendet: Für dein Konto ist keine bestätigte E-Mail-Adresse hinterlegt. Bitte bestätige zuerst deine Adresse im Profil.` | `The test email was not sent: your account has no confirmed email address. Please confirm your address in your profile first.` | channel_test_service.py:13-16 |
| `versand.ergebnis.already_in_progress` | `Versand läuft bereits — bitte warten` | `Delivery is already in progress — please wait` | send_outcomes.py:15 |
| `versand.ergebnis.no_weather` | `Kein Briefing versendet — keine Wetterdaten verfügbar` | `No briefing sent — no weather data available` | send_outcomes.py:19 |

Weitere Schlüssel `versand.ergebnis.<code>` für die übrigen Codes von `SEND_OUTCOMES` (`kind_required`, `not_found`, `no_stage`, `no_channels`, `channels_unreachable`, `invalid_report_type`, `smtp_not_configured`, `invalid_preset`, `send_failed`) mit denselben Platzhaltern (`{entity_id}`, `{report_type}`, `{reason}`). Die zwei Betreff-Schlüssel mit und ohne Umlaut bleiben getrennt, weil `de` wörtlich bleibt (Rechtschreibkorrekturen sind nicht Teil des Epics); `en` ist gleich.

**Beispiel-Umstellung 1 (subject.py:17-52 und 161-162), vorher:**

```
_REPORT_TYPE_DE = {"morning": "Morgen", "evening": "Abend", "update": "Update"}
def _report_type_label(report_type: str) -> str:
    return _REPORT_TYPE_DE.get(report_type, report_type)
...
report_de = _report_type_label(token_line.report_type)
```

**nachher:**

```
_REPORT_TYPE_KEYS = {"morning": "versand.betreff.bericht.morgen",
                     "evening": "versand.betreff.bericht.abend",
                     "update": "versand.betreff.bericht.update"}
def _report_type_label(report_type: str, lang: Lang = "de") -> str:
    key = _REPORT_TYPE_KEYS.get(report_type)
    return t(key, lang) if key else report_type
...
report_de = _report_type_label(token_line.report_type, lang)
```

Die Kürzungskaskade (`DEFAULT_MAX_LENGTH = 78`) und die Token `D`/`W`/`G`/`HR`/`TH` bleiben unverändert; das längere englische Wort (`Morning` statt `Morgen`) wird von der bestehenden Kürzung aufgefangen, der Betreff bleibt ≤ 78 Zeichen (AC-2).

**Beispiel-Umstellung 2 (notification_service.py:2363-2372, Vorschau-Hinweise), vorher:**

```
stage_name = request.stage_name or "Etappe"
human_date = target_date.strftime("%d.%m.%Y")
if request.test_prefix:
    hint = f"Test-Vorschau für {stage_name} am {human_date}"
```

**nachher:**

```
stage_name = request.stage_name or t("versand.etappe.rueckfall", self._lang)
human_date = fmt_date_numeric(target_date, self._lang)   # de: dd.mm.yyyy
if request.test_prefix:
    hint = t("versand.hinweis.test_vorschau", self._lang, etappe=stage_name, datum=human_date)
```

`[TEST]` (Zeile 2369) bleibt unverändert (Marker, kein Nutzertext).

**Beispiel-Umstellung 3 (send_outcomes.py:63-66), vorher:**

```
def error_body(code: str, **values: str) -> tuple[int, dict]:
    status, template = SEND_OUTCOMES[code]
    return status, {"detail": template.format(**values), "code": code}
```

**nachher:**

```
def error_body(code: str, *, lang: Lang = "de", **values: str) -> tuple[int, dict]:
    status, key = SEND_OUTCOMES[code]
    return status, {"detail": t(key, lang, **values), "code": code}
```

`code` bleibt stabil (snake_case) und ist der Vertrag mit dem Frontend (Konvention Abschnitt 5, Fehlerobjekt `{code, message}`); `api/routers/briefings_send.py` prüft nur `outcome in SEND_OUTCOMES` und bleibt dafür unverändert.

**Nicht ändern:** Kanal-Sperrgründe und Betreiber-Texte (`ChannelBlockedError`, `OutputError`, `reason_code`), `logger`-Texte, `mail_type`-Werte, Header-Namen, Bot- und SMS-Transport. Log-/Debug-Zeilen mit Umlaut/Signalwort erhalten `# i18n-log`.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) die Präfixe `src/output/channels/email.py`, `src/output/subject.py`, `src/services/notification_service.py`, `src/services/send_outcomes.py`, `src/services/channel_test_service.py` entfernen (vorher `Glob tests/fixtures/i18n_python_allowlist.json`; existiert sie noch nicht, holt P11 den Schritt nach).

**Validatoren:** Die vier Mail-Validatoren lesen `X-GZ-Lang` (PV). P9a ändert keinen Validator, sorgt aber dafür, dass der Header an jeder Mail steht, die `EmailOutput` sendet (Trip-Briefing, Ortsvergleich, Alarm, amtliche Warnung, Test-Versand). Der Staging-Lauf in beiden Sprachen gehört zu `/e2e-verify`.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten, Sperrgrund-Texte übersetzen.

## Expected Behavior

- **Input:** Versand-Anfrage mit `user_id` (aus Auth-Kontext), Trip- oder Ortsvergleich-Daten; Test-Versand mit Kanal und `user_id`; Handversand-Fehlercodes.
- **Output:** E-Mails mit Betreff und Hinweisen in der Nutzersprache und Header `X-GZ-Lang`; SMS und Premium-SMS (inkl. SMS-Hinweis und Ausfall-Text) in jeder Sprache unverändert deutsch (PO-Korrektur 2026-10-31); Fehlerobjekt `{"detail": <Text in Nutzersprache>, "code": <stabil>}`. `de` byte-gleich zu heute.
- **Side effects:** Lesen von `data/users/<user_id>/user.json` (nur Feld `language`) beim Anlegen des Dienstes bzw. Test-Versands. Keine Schreibzugriffe, kein globaler Zustand.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Sprache `en` und bestätigter Adresse / When ein Test-Versand per E-Mail ausgelöst wird / Then lautet der Betreff `Gregor 20 — Test message`, der Text `Your channel works.`, und die Mail trägt den Header `X-GZ-Lang: en`.
  - Test: tests/test_versand_zweisprachig.py — ruft `send_test_message("email", user_id)` über die bestehende Mail-Naht des Tests auf und liest Betreff, Text und Header aus der gebauten MIME-Nachricht; Erwartung über `t(key, "en")`.

- **AC-2:** Given Nutzer-Sprache `en` und ein Trip-Briefing (Typ `morning`, Hauptrisiko `Thunder`) / When der Betreff gebaut wird / Then lautet er `[GR20] … — Morning — Thunderstorm D13 W30 G55` (Token unverändert) und hat höchstens 78 Zeichen; mit `de` bleibt `… — Morgen — Gewitter …` byte-gleich.
  - Test: tests/test_versand_zweisprachig.py — `build_email_subject(token_line, lang=...)` für beide Sprachen und mehrere Längen (Kürzungskaskade), `de` gegen Golden.

- **AC-3:** Given Sprache `de` / When Betreffe, Ausfall-Hinweis, Vorschau-Hinweise, Test-Versand-Texte, SMS-Hinweis und Fehlertexte erzeugt werden / Then ist jede Ausgabe byte-gleich zu den vorab eingecheckten `betreffe.de.txt`, und der Header lautet `X-GZ-Lang: de`.
  - Test: tests/golden/test_versand_texte_golden.py — Byte-Vergleich je Text; Header-Prüfung an `build_mime_message` (HTML- und Plain-Zweig).

- **AC-4:** Given zwei Nutzer, `golden-de` (Sprache `de`) und `golden-en` (Sprache `en`), im selben Prozess und Lauf, je mit eigenem `NotificationService` / When beide ein Briefing, eine Ausfall-Meldung und einen Ortsvergleich über die Sink-Naht senden / Then erhält jede Mail die Sprache ihres Nutzers (Betreff, Hinweis, Header), und die Reihenfolge der Aufrufe (`de`, `en`, `de`) ändert nichts.
  - Test: tests/test_versand_zwei_nutzer_sprachen.py — zwei Dienstobjekte mit echten `user.json`-Dateien im Test-Datenverzeichnis, Mitschnitt über `mail_sink`; kein Spiegel-Mock der Sprache.

- **AC-5:** Given ein Handversand-Fehler `no_weather` und Nutzer-Sprache `en` / When die Antwort des Routers gebaut wird / Then ist `detail` = `No briefing sent — no weather data available`, `code` = `no_weather` und der Status 422 (unverändert); mit `de` bleibt der deutsche Text byte-gleich.
  - Test: tests/test_versand_zweisprachig.py — `error_body("no_weather", lang=...)` und der Router-Hilfsaufruf mit `user_id` zweier Nutzer.

- **AC-6:** Given ein Nutzer ohne bestätigte Adresse und Sprache `en` / When ein Test-Versand per E-Mail versucht wird / Then erscheint der englische Sperrtext (`The test email was not sent …`), es wird keine Mail gebaut, und für `user_id` leer oder `"default"` bleibt die Sperre bestehen.
  - Test: tests/test_versand_zweisprachig.py — `_sperre_email`/`send_test_message` für die drei Fälle (bestätigt, unbestätigt, `"default"`).

- **AC-7:** Given Nutzer-Sprache `en` / When die Ausfall-Meldung per SMS und Premium-SMS sowie ein Alarm mit amtlichem Zusatz per SMS und Premium-SMS versendet werden / Then ist jeder SMS-Text byte-gleich zur Ausgabe für einen `de`-Nutzer (PO-Korrektur 2026-10-31), während E-Mail und Telegram der Ausfall-Meldung englisch sind.
  - Test: tests/test_versand_zweisprachig.py — beide Nutzer über die Draht-Gegenstellen (`KanalRig`), Vergleich der gesendeten SMS-Texte.

## Known Limitations

- Annahme: Der Header `X-GZ-Lang` wird in `build_mime_message` immer gesetzt (Wert `de` oder `en`); falls PV ihn schon mit Vorgabe `de` setzt, ersetzt P9a nur die Vorgabe durch die Nutzersprache.
- Annahme: `SEND_OUTCOMES` hält jetzt Katalogschlüssel statt Text; weil der Router nur auf Mitgliedschaft prüft, ändert sich dort nichts. Tests, die den deutschen Text direkt aus `SEND_OUTCOMES` lesen, werden auf `error_body(code, lang="de", ...)` umgestellt (Grep in `tests/` zuerst).
- Annahme: Betreiber- und Sperrgrund-Texte der Kanäle (`ChannelBlockedError`, `OutputError`) bleiben deutsch; ihre Nutzersicht entsteht über `reason_code` und `send_outcomes`.
- PO-Korrektur 2026-10-31 (ADR-0104 Präzisierung, hat Vorrang vor Version 1.0): Es gibt keinen englischen SMS-Hinweis; `_AMTL_HINWEIS_SMS_TOKEN` bleibt in jeder Sprache `+ amtl. Warnung s. E-Mail/Telegram`.
- Bis P9b (#2672) rendern `scheduler_dispatch_service` (Ortsvergleich-Inhalt) und `trip_report_scheduler` (Nachlieferungs-/Teilausfall-Präfixe) noch deutsch; `NotificationService` liest die Sprache aber schon aus `user_id`. Ein Ortsvergleich-Briefing eines `en`-Nutzers trägt bis dahin `X-GZ-Lang: en` bei deutschem Inhalt.
- Die Antworten auf Befehle (Inbound) und die übrigen `api/routers/**`-Meldungen sind P10 und P11.
- Admin-Mails an den Betreiber bleiben deutsch (Epic-Abgrenzung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0095 für Kanal-Parität, ADR-0003 für Mandantentrennung)
- **Rationale:** Die Sprache ist eine Eigenschaft des Nutzers und wird je Dienstobjekt einmal gelesen und durchgereicht; der Marker `X-GZ-Lang` macht die Mail für die Validatoren prüfbar.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
- 2026-11-01: PO-Korrektur 2026-10-31 eingearbeitet (SMS/Premium-SMS/Telegram-Kurzstil sprachunabhängig, `versand.sms.amtl_hinweis` entfällt, AC-7 neu); Übergangslage bis P9b vermerkt
