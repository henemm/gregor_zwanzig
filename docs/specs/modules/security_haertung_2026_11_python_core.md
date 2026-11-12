---
entity_id: security_haertung_2026_11_python_core
type: module
created: 2026-11-12
updated: 2026-11-12
status: approved
version: "1.0"
tags: [security, python-core, mail, telegram, gpx, dependencies]
---

# Sicherheits-Härtung Python-Core (Review 2026-11)

## Approval

- [x] Approved — Auftrag des Product Owners zu Issue #2961: alle Befunde des
  Sicherheits-Reviews ohne Rückfrage beheben. Diese Spec hält das umgesetzte
  Soll-Verhalten fest.

## Purpose

Der Python-Core nimmt Anfragen, Mails und Telegram-Nachrichten nur in der
erwarteten Form an, gibt nach außen keine internen Details preis, prüft
Gegenstellen per Zertifikat und begrenzt Mengen, die ein einzelner Absender
auslösen kann. Diese Spec beschreibt das geforderte sichere Verhalten; sie ist
bewusst keine Anleitung zu den behobenen Schwächen.

## Source

- **Files:** `api/main.py`, `api/fehler.py`, `api/routers/gpx.py`,
  `src/output/channels/email.py`, `src/output/channels/telegram.py`,
  `src/output/renderers/email/html.py`, `src/output/renderers/email/starkregen_hint.py`,
  `src/services/inbound_email_reader.py`, `src/services/inbound_reply_limit.py` (neu),
  `src/services/inbound_telegram_reader.py`, `src/services/notification_service.py`,
  `src/services/channel_test_service.py`, `src/services/gpx_processing.py`,
  `src/core/gpx_parser.py`, `src/validation/ground_truth.py`, `src/app/config.py`,
  `src/app/loader.py`, `src/services/trip_command_processor.py`,
  `src/services/preview_service.py`, `src/services/scheduler_dispatch_service.py`,
  `api/routers/validator.py`, `uv.lock`
- **Schicht:** ausschließlich Python-Core (FastAPI hinter der Go-API). Go und
  Frontend werden parallel in eigenen Paketen gehärtet.

> **Querschnitts-Prüfpunkte:** keine neue Oberfläche, kein Trip/Ortsvergleich-
> Pendant. Mandantentrennung: GPX-Grenzen und Fehlerantwort-Drossel gelten je
> Nutzer und sind mit zwei Nutzern getestet. Kanäle: Mail (Schleifenschutz,
> HTML-Ausgabe) und Telegram (unbekannte Chats) sind betroffen; SMS und
> Premium-SMS unverändert.

## Estimated Scope

- **LoC:** ~450 Produktivcode, ~900 Tests
- **Files:** ~25
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/adr/0062-python-core-authentifiziert-gegenueber-go.md` | ADR | Core-Auth, hier um Host-Prüfung ergänzt |
| `docs/specs/modules/bug_inbound_email_loop.md` | Spec | AC-4 dort durch AC-4 hier abgelöst |
| `docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md` | Spec | AC-8 dort durch AC-5 hier teilweise abgelöst |
| `docs/reference/api_contract.md` | Vertrag | neue Fehlerantworten von `POST /api/gpx/parse` |

## Implementation Details

- **Core-Auth:** Ausnahme `/health` am Pfad aus dem ASGI-Scope; Host-Header muss
  `localhost`, `127.0.0.1`, `::1` oder (Tests) `testserver` sein, erweiterbar per
  `GZ_CORE_ALLOWED_HOSTS` (kommagetrennt), sonst `400`.
- **TLS:** volle Zertifikats- und Namensprüfung (`ssl.create_default_context()`)
  für STARTTLS und IMAPS, ohne Schalter; IMAP-Zeitgrenze 30 s. Einzige Ausnahme
  (`src/utils/mail_tls.py`): Ist der Host wörtlich `localhost` oder eine
  Loopback-IP (`127.0.0.1`, `::1`, …), wird das Zertifikat nicht geprüft — der
  Verkehr verlässt den Rechner nicht (Stalwart auf demselben Server) — und eine
  Info-Zeile protokolliert.
- **HTML-Ausgabe:** `html.escape` für Trip-Name, Etappentitel, Trip-Link,
  Hinweistexte, Starkregen-Hinweis und Service-Fehlermail.
- **Mail-Schleifen:** Kopf `Auto-Submitted: auto-generated` auf jeder
  ausgehenden Mail; Eingang verwirft automatisch erzeugte Mails (Auto-Submitted
  außer `no`, Precedence bulk/junk/auto_reply/list, X-Autoreply); bei
  `X-Auto-Response-Suppress` (Bitte, nicht automatisch zu antworten) wird der
  Befehl ausgeführt, aber keine Fehlerantwort geschickt; System-Adressen
  sind nie Befehlsgeber; Fehlerantworten ≤ 5 je Nutzer und Stunde, gespeichert
  in `data/users/<id>/inbound_fehlerantworten.json`.
- **Fehlertexte:** Ausnahmen ohne Code → Katalogtext `api.fehler.unbekannt`,
  Kanaltest → `versand.test.fehlgeschlagen`, GPX → `api.fehler.gpx_ungueltig`;
  Details nur im Log.
- **GPX:** ≤ 10 MB je Datei (`413`), ≤ 200 Dateien und ≤ 200 MB je Nutzer
  (`409`), gleichnamige Datei wird erst nach erfolgreichem Lesen ersetzt.
- **Eingaben/Konfiguration:** Bergfex-Kurzname `[a-z0-9-]+`, keine
  Weiterleitungen; Kennungsprüfung per `fullmatch`; Geheimnisfelder in `repr`
  und `str` maskiert; ohne Nutzerprofil kein Mail-Empfänger und (außer
  Testmodus) kein Telegram-Chat.
- **Telegram:** Registrierungshinweis je unbekanntem Chat höchstens einmal je
  Stunde (prozesslokale Tabelle, höchstens 10 000 Einträge); Antworten an
  unbekannte Chats warten nie in der Sende-Drossel.
- **Mail-Abruf:** erst Kopfzeilen samt Größe, Rumpf nur für autorisierte
  Absender, ≤ 50 Mails je Lauf, Mails > 2 MB werden als gelesen markiert und
  übersprungen. Logs: Adresse maskiert, Befehl nur als gekürztes Befehlswort.
- **Abhängigkeiten:** `uv.lock` auf Stände ohne bekannte Lücken angehoben.

## Expected Behavior

- **Input:** HTTP-Anfragen von Go, eingehende Mails (IMAP), Telegram-Updates, GPX-Uploads.
- **Output:** unverändert für legitime Aufrufer; abgewiesene oder gedrosselte
  Fälle mit klaren Statuscodes und Katalogtexten.
- **Side effects:** neue Datei `data/users/<id>/inbound_fehlerantworten.json`.

## Acceptance Criteria

**AC-1:** Given der Python-Core mit konfiguriertem gemeinsamen Geheimnis / When eine Anfrage mit einem Host-Header außerhalb der erlaubten Namen eintrifft (mit oder ohne Geheimnis) / Then antwortet der Core mit 400 und liefert keine Nutzdaten; Anfragen mit erlaubtem Host bleiben unverändert (mit Geheimnis 200, ohne 401, `/health` immer 200).
- Test: `tests/tdd/test_core_auth_host_header.py`, `tests/tdd/test_core_auth_enforcement.py`

**AC-2:** Given ein Mail-Server mit einem nicht vertrauenswürdigen Zertifikat, angesprochen über einen Hostnamen, der keine Loopback-Adresse ist / When der Core Mails versendet (STARTTLS) oder den Posteingang abruft (IMAPS) / Then bricht der Verbindungsaufbau ab, bevor Zugangsdaten gesendet werden; mit vertrauenswürdigem Zertifikat funktioniert beides wie bisher; ist der Host wörtlich `localhost` oder eine Loopback-IP, wird ohne Zertifikatsprüfung verbunden und das protokolliert.
- Test: `tests/tdd/test_mail_tls_zertifikatspruefung.py` (TLS-Server auf Loopback mit frisch erzeugtem Zertifikat; strenger Zweig über einen nicht auflösbaren Namen, dessen Namensauflösung auf den Loopback-Port zeigt; Kontextwahl je Hostname)

**AC-3:** Given ein Trip-, Etappen-, Orts- oder Abo-Name bzw. ein Hinweis- oder Provider-Fehlertext mit HTML-Sonderzeichen / When die Mail gerendert wird (Trip-Briefing, Service-Fehlermail, Hinweiszeile, Alarm, Ortsvergleich) / Then erscheint der Text im HTML-Teil genau einmal escaped und im Klartext-Teil unverändert.
- Test: `tests/tdd/test_mail_html_nutzertext_escaping.py`

**AC-4:** Given der Mail-Posteingang / When eine automatisch erzeugte Mail (Auto-Submitted ungleich `no`, Precedence bulk/junk/auto_reply/list, X-Autoreply) oder eine Mail von einer System-Adresse (Absender-, Eingangs-, Postfachadresse) eintrifft / Then wird sie ohne Antwort als gelesen markiert; eine Mail mit `X-Auto-Response-Suppress` wird als Befehl ausgeführt und bei Erfolg beantwortet, bekommt aber keine Fehlerantwort; jede ausgehende Mail trägt `Auto-Submitted: auto-generated`; Fehlerantworten per Mail gehen je Nutzer höchstens fünfmal pro Stunde raus, Erfolgsantworten ungedrosselt.
- Test: `tests/tdd/test_mail_schleifenschutz.py`, `tests/tdd/test_bug_inbound_email_loop.py`

**AC-5:** Given eine Ausnahme ohne Fehlercode, ein fehlgeschlagener Kanaltest oder eine unlesbare GPX-Datei / When der Core dem Client antwortet / Then enthält die Antwort einen Katalogtext in der Sprache des Nutzers ohne Pfade, Hostnamen oder Konfigurationsnamen, und die Details stehen im Log.
- Test: `tests/tdd/test_fehlertexte_ohne_interna.py`, `tests/tdd/test_api_fehler_nutzersprache.py`

**AC-6:** Given ein Nutzer lädt eine GPX-Datei hoch / When sie größer als 10 MB ist bzw. seine Ablage schon 200 Dateien oder 200 MB umfasst / Then antwortet der Core mit 413 bzw. 409 und Katalogtext und speichert nichts; eine gleichnamige Datei wird ersetzt (nicht dupliziert), aber nur, wenn die neue lesbar ist; die Grenzen gelten je Nutzer.
- Test: `tests/tdd/test_gpx_upload_grenzen.py`

**AC-7:** Given ein Ort mit Bergfex-Kurzname, ein Settings-Objekt mit Geheimnissen bzw. ein Nutzer ohne lesbares Profil / When Schneedaten abgerufen, die Settings protokolliert bzw. die Nutzer-Settings gebildet werden / Then werden Kurznamen außerhalb `[a-z0-9-]+` abgelehnt und Weiterleitungen nicht verfolgt, erscheint kein Geheimnis im Klartext und gibt es keinen Mail-Empfänger (kein Rückfall auf die globale Adresse).
- Test: `tests/tdd/test_eingaben_streng_geprueft.py`, `tests/unit/test_entity_id_pattern_parity.py` (geteilte Wahrheitstabelle, u. a. Steuerzeichen, `?`, `#`, `%` ungültig)

**AC-8:** Given ein Telegram-Chat ohne zugeordnetes Konto / When er mehrfach schreibt bzw. die Sende-Drossel für ihn voll ist / Then erhält er höchstens einen Registrierungshinweis pro Stunde, die Merktabelle bleibt beschränkt, und der Webhook-Worker wartet nie in der Drossel.
- Test: `tests/tdd/test_telegram_unbekannte_chats.py`

**AC-9:** Given die gesperrten Python-Abhängigkeiten in `uv.lock` / When sie mit `pip-audit` gegen die bekannten Schwachstellen geprüft werden / Then meldet die Prüfung keine bekannte Lücke.
- Test: `uv export --no-dev --format requirements-txt --no-hashes` + `uvx pip-audit -r … --no-deps --disable-pip` (Lauf im Bericht zu #2961)

**AC-10:** Given ungelesene Mails im Posteingang / When der Abruf läuft / Then lädt er zuerst nur Kopfzeilen und Größe, den Rumpf nur für autorisierte Absender, höchstens 50 Mails je Lauf, überspringt Mails über 2 MB (als gelesen markiert) und protokolliert weder volle Adressen noch volle Befehlstexte.
- Test: `tests/tdd/test_mail_schleifenschutz.py`, `tests/tdd/test_logs_ohne_klartext_nutzerdaten.py`

## Known Limitations

- Die Host-Prüfung setzt voraus, dass `GZ_PYTHON_CORE_URL` in Prod/Staging einen
  der erlaubten Namen trägt (Standard `http://localhost:8000`); sonst muss der
  Name in `GZ_CORE_ALLOWED_HOSTS` stehen.
- Kennungsmuster: Python `VALID_ENTITY_ID_RE` und Go `store.ValidEntityIDRe`
  sperren gleichlautend zusätzlich Steuerzeichen (`\x00`–`\x1f`, `\x7f`) sowie
  `?`, `#`, `%`; Leerzeichen bleiben erlaubt. Die geteilte Wahrheitstabelle
  `tests/fixtures/entity_id_pattern_parity/faelle.json` enthält diese Fälle; der
  Go-Paritätstest besteht sie erst zusammen mit dem verschärften Go-Muster.
- Loopback-Ausnahme der TLS-Prüfung gilt nur für wörtliche Loopback-Hosts; ein
  Name, der erst per DNS auf 127.0.0.1 zeigt, wird streng geprüft.
- Die Telegram-Hinweistabelle ist prozesslokal; nach einem Neustart darf ein
  unbekannter Chat einmal erneut einen Hinweis bekommen.
- Nicht Teil dieser Spec (Welle 2): Abruf-Kontingent interaktiver Routen,
  Premium-SMS-Rückkanal, Mengenbudget für Handversand.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Härtungen innerhalb bestehender Entscheidungen (ADR-0062
  Core-Auth, Kanal-Architektur); keine neue Entscheidungsfläche. Abgelöste
  Einzel-ACs sind in den betroffenen Specs vermerkt.

## Changelog

- 2026-11-12: Erstfassung (Issue #2961).
