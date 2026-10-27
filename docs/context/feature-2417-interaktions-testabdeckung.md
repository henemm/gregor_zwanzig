# Context: feature-2417-interaktions-testabdeckung

## Request Summary
PO (#2417): Welche Interaktions-Befehle sind wirklich End-to-end getestet? Tests „löchrig" — überarbeiten.
(1) Werden alle verfügbaren Befehle angezeigt (E-Mail, Telegram)? (2) Funktionieren alle? (3) Premium-SMS ohne große Kosten testen. Kommentar: „Hilfe funktioniert nicht!!!"

## PO-Klarstellung 25.09. (VERBINDLICH, Schwerpunkt)
**Primär geht es um die Tests**, nicht um Einzel-Fixes: Features wurden als „fertig" gemeldet, der PO nutzt sie und NICHTS funktioniert. Erwartet: Tests, die die relevante Funktionalität **End-to-End** prüfen.
Daraus folgt für Analyse/Spec:
- Jeder in irgendeinem Kanal **angebotene** Befehl (Mail-Tabelle, Hilfe-Text, Telegram-Menü, Telegram-Knöpfe) bekommt einen Test durch den **echten Eingang** des Kanals (Telegram `_process_update`/Callback, E-Mail `_process_single` mit realer Antwortmail inkl. Zitat, Premium-SMS `_verarbeite_befehl`) bis zur **tatsächlich versendeten Antwort** — nicht auf Processor-Ebene.
- Testnutzer realistisch wie der PO: aktiver Trip **plus** mehrere aktive Ortsvergleiche.
- Premium-SMS kostenfrei: nur die Transportgrenze (seven.io-HTTP-Aufruf) abfangen, alles davor echt; Segmentzahl der Antwort als Zusicherung.
- Live-Schicht gegen Staging (echte Telegram-/Mail-Zustellung) für die Kern-Befehle.
- Reihenfolge: Tests zuerst (rot an B1–B3), dann Fixes.

## Belegte Befunde aus den PO-Screenshots (25.09., Prod)
| # | Kanal | Beobachtung |
|---|-------|-------------|
| B1 | Telegram | `/hilfe` → `[Fehler] Mehrdeutig: KHW 403 (Trip), Le Var (Vergleich), Heimat, Mallorca, Zillertal täglich, Zillertal (Vergleich). Mit Namen antworten…` |
| B2 | E-Mail | Antwort „HILFE" → Mail „Unbekannter Befehl … Verfügbar: HEUTE, …, HILFE … (HILFE zeigt alle)" — Fehlertext empfiehlt genau den Befehl, der scheiterte. Ursache noch offen (Body-Parsing der Antwortmail? Zitat/Signatur? Betreff-Zuordnung?) |
| B3 | Telegram-Menü | Bot-Menü zeigt nur glance/heute/morgen/now/heute_gewitter/timeline_heute/timeline_morgen/hilfe — STRECKE, RUHETAG, STATUS, PAUSE, SKIP, STOP, WEITER fehlen, obwohl die Mail-Tabelle „Antwort-Kommandos" sie anbietet |
| B4 | E-Mail-Briefing | Tabelle „Antwort-Kommandos" listet 12 Befehle (HEUTE…HILFE) — Referenz für „was angeboten wird" |

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | `_VALID_COMMANDS` :186, Aliase :189-205, `_COMMAND_SPECS` :219-234, `command_rows/overview`, `unknown_command_body` :268, hilfe ohne Trip-Lookup :866, Vergleichspfad `_resolve_vergleich/_dispatch_compare` :975-1049, `_show_help_for_kind` :1036, `_show_help` :2187 |
| `src/services/inbound_telegram_reader.py` | `_SHORTCUT_MAP` :54-75, `_CALLBACK_QUERY_MAP` :78-97 (`act_help`→`### hilfe`), **`resolve_active_target()` :254-263 VOR `_command_body()` :274** → Mehrdeutig/Kein-Ziel blockt HILFE (B1); `_process_callback_query` :407-432 nutzt alten `_find_active_trip` → `act_help` ohne aktiven Trip = stilles Nichts |
| `src/services/trip_selection.py` | `resolve_active_target` Mehrdeutig :163-192; `_vergleich_ist_aktiv` :86 zählt jeden nicht-archivierten Vergleich ohne abgelaufenes `end_date` |
| `src/services/inbound_email_reader.py` | `_process_single`; Betreff braucht `[Name]`, sonst still ignoriert :151-155 (B2-Kandidat) |
| `src/services/inbound_sms_reader.py` | Premium-SMS `_verarbeite_befehl` :327, gleiche `resolve_active_target`-Sperre; Dry-Run `GZ_PREMIUM_SMS_POLL_DRYRUN` :283-297 überspringt die Verarbeitung komplett |
| `src/output/channels/telegram.py` | `BOT_COMMANDS` :111-120 (8 Einträge, B3); send/edit kürzen still auf 4096 :421, :568 |
| `src/services/notification_service.py` | Antwortversand je Kanal, `send_command_reply_premium_sms` :1829; Fehler nur geloggt |
| `src/output/channels/seven_io_base.py` | seven.io-Transport, Sandbox-Key :108-149 (nur outbound) |
| `api/routers/webhook.py` :52, `api/routers/scheduler.py` :179 | Telegram-Webhook-Eingang + Polling-Fallback, E-Mail-Inbound-Endpoint |
| `internal/handler/telegram_webhook.go`, `internal/scheduler/scheduler.go:738` | Go: Secret-Check + Weiterleitung; Scheduler pollt E-Mail-Inbound |
| E-Mail-Renderer „Antwort-Kommandos"-Tabelle | Quelle der B4-Liste (vermutlich aus `command_rows()`) |

## Existing Patterns
- Einzelquelle der Befehlsliste: `_COMMAND_SPECS` → `command_rows()` → Hilfe, Fehlertext, Mail-Tabelle (#2134, Test `test_kommandoliste_einzelquelle.py`). `BOT_COMMANDS` hängt NICHT an dieser Quelle.
- Kanalübergreifende Ziel-Auflösung Trip vs. Ortsvergleich via `resolve_active_target` (#2282) — Telegram + Premium-SMS; E-Mail über Betreff-Namen.
- Befehle, die kein Ziel brauchen (hilfe, columns), sind im Processor ausgenommen — aber die Reader lösen das Ziel vorher auf.

## Dependencies
- Upstream: Trip-/Preset-Store pro Nutzer, Metrik-Katalog (`get_all_metrics`), seven.io, Telegram Bot API, Stalwart/IMAP.
- Downstream: alle Nutzer-Antworten auf Befehle in allen vier Kanälen; Briefing-Mail-Tabelle.

## Existing Specs
- `docs/specs/modules/trip_command_processor.md`, `inbound_command_channels.md`, `command_set_merge.md`
- `feat_2134_adhoc_abruf_metrik_katalog.md`, `feat_1001_telegram_redesign.md`, `feat_2282_ortsvergleich_eingangskanaele.md` (AC-4/5/12)
- `feat_2184_s4_premium_sms_kommandoverarbeiter.md`, `feat_1676_s1_premium_sms_rueckkanal.md`
- `telegram_webhook_inbound.md`, `fix_2220_telegram_kommando_befunde.md`, `telegram_output.md`
- Archiv: `issue_731_unified_commands.md`, `bug_744_telegram_bare_keywords.md`
- Referenziert, aber fehlend: `inbound_telegram_reader.md`

## Testlandschaft (Ist)
| Test | Prüft | Lücke |
|------|-------|-------|
| `test_inbound_telegram_reader.py:286` | Processor-`### hilfe` enthält Wörter | nicht über Reader-Eingang |
| `test_kommandoliste_einzelquelle.py` | Hilfe-Wortmenge E-Mail = Telegram, Fehlertexte abgeleitet | nur Processor-Ebene |
| `test_vergleich_befehlsablehnung.py:162` | Vergleichshilfe ⊂ Triphilfe | — |
| `test_eingangsauswahl_trip_und_vergleich.py:374` | `_process_update` → Mehrdeutig (nur `pause`) | **zementiert** Mehrdeutig; kein Test hilfe bei Mehrdeutig/kein Ziel |
| `test_premium_sms_kommandopfad.py` | status, heute, unbekannt | kein hilfe, keine Länge/Segmente |
| `test_issue_1001_telegram_bubbles.py` | act_pause, act_columns | **kein act_help/act_skip/act_overview** |
| `test_issue_686_telegram_functional_live.py` (live) | nachgebaute Pipeline `_telegram_live_fixture.py:316` | umgeht `_process_update`/`resolve_active_target`, Fixture-User ohne Vergleiche → kann B1 strukturell nicht fangen |
| — | E-Mail-HILFE durch `_process_single` | **fehlt** (B2) |
| — | Vollständigkeit Hilfe ↔ `_VALID_COMMANDS`/`_SHORTCUT_MAP`/`BOT_COMMANDS`/Mail-Tabelle | **fehlt** (B3) |

## Risks & Considerations
- Kernmuster: Tests prüfen den Processor, die Fehler sitzen im **Eingang davor** (Reader, Ziel-Auflösung, Betreff/Body-Parsing) — „geprüft, wo der Code steht, nicht wo er wirkt".
- Nutzer mit Trip + Ortsvergleichen ist der Normalfall des PO; Fixtures ohne Vergleiche verdecken das.
- Premium-SMS: HILFE ≈ 2.000 Zeichen, nicht-GSM-Zeichen (`–`, `→`, `°`) → UCS-2, ~31 Segmente pro Antwort; keine Kanal-Kürzung. Kosten und inReach-Verhalten bei Mehrteil-SMS unbelegt. Kostenfreier E2E-Pfad existiert nicht (Dry-Run überspringt Verarbeitung, Sandbox nur outbound).
- Mehrdeutig-Verhalten ist eine freigegebene #2282-AC — Ausnahme für ziellose Befehle muss sie ergänzen, nicht still kippen.
- Alle vier Kanäle gleichrangig (CLAUDE.md): jede Frage muss in jedem Kanal beantwortbar sein.
- LoC-Limit 250: Umfang (Fix B1/B2/B3 + Test-Matrix + Premium-SMS-Testweg) kann Scheibenschnitt erfordern.
- Git: Mehrdeutig-Sperre seit bc1c5f24 (#2282, 17.09.); User-Resolve-Refactor #2151 (19.09.).

## Analysis

### Type
Bug-Bündel + Test-Neuaufbau (PO-Schwerpunkt: E2E-Tests). Befund: nicht nur HILFE — **in Telegram und Premium-SMS scheitert jeder Befehl ohne Namen** für Nutzer mit Trip + ≥1 Ortsvergleich (Normalfall des PO: KHW 403 + 5 Vergleiche ohne `end_date`).

### Belegte Ursachen
| # | Symptom | Ursache (belegt) |
|---|---------|------------------|
| U1 (B1) | Telegram/Premium-SMS: `/hilfe`, `/heute`, `/now` … → „Mehrdeutig" | `resolve_active_target` (`src/services/trip_selection.py:163-192`) wird im Reader VOR dem Befehl ausgewertet (`inbound_telegram_reader.py:254`, `inbound_sms_reader.py` analog). Tabelle: 1 Trip + ≥1 Vergleich ⇒ immer Rückfrage, befehlsunabhängig. `_vergleich_ist_aktiv` (:86) zählt jeden nicht-archivierten Vergleich ohne abgelaufenes `end_date`. **Freigegebene AC-4 von #2282** (`docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md:311-320`) schreibt genau das vor → neue Spec muss AC-4 ausdrücklich ablösen (Status-Vermerk in der #2282-Spec). |
| U2 (B2) | E-Mail-Antwort „Hilfe" → „Unbekannter Befehl" | **Prod-Mail UID 5765 (25.09. 06:39, Betreff `Re: [KHW 403] Etappe 2: … — Morgen`) ist `multipart/alternative` mit NUR `text/html`** (QP, utf-8, Apple Mail: `<body dir="auto">Hilfe<br id="lineBreakAtBeginningOfSignature"><div dir="ltr"><div><br></div></div><div dir="ltr"><br><blockquote type="cite">Am 25.09.2026 um 06:06 schrieb …:<br><br></blockquote></div><blockquote type="cite"><div dir="ltr">﻿…`). `_extract_plain_body` (`inbound_email_reader.py:274-287`) liest nur `text/plain` → `""` → `_parse_command` (None, None) → `trip_command_processor.py:791-798` „Unbekannter Befehl". ⇒ **Jeder** E-Mail-Befehl aus iPhone-Mail scheitert. Rohmail nicht committen (echte Adressen/Inhalte) — Fixture synthetisch mit exakt dieser MIME-Struktur nachbauen. |
| U3 (B3) | Telegram-Menü unvollständig | `BOT_COMMANDS` (`src/output/channels/telegram.py:111-120`, registriert `api/main.py:84` beim Start) ist handgepflegt, nicht aus `_COMMAND_SPECS` abgeleitet; es fehlen strecke, status, ruhetag, pause, skip, stop, weiter. |
| U4 | Knopf „❓ Hilfe" (alle Knöpfe) tut bei Nur-Vergleich-Lage nichts; bei Erfolg überschreibt er die Aktionen-Bubble ohne Knöpfe | `_process_callback_query` (`inbound_telegram_reader.py:407-432`) nutzt alten `_find_active_trip`; `edit…` mit `reply_markup=None`. |
| U5 | Premium-SMS-HILFE ≈ 2.000 Zeichen, UCS-2 (–, →, °) ⇒ ~31 bezahlte Segmente | `_show_help` kanalunabhängig, keine Kurzform; `send_command_reply_premium_sms` (`notification_service.py:1829`) kürzt nicht. |
| U6 | Tests konnten nichts davon fangen | Alle Befehls-Tests auf Processor-Ebene; Live-Fixture `tests/tdd/_telegram_live_fixture.py:316` baut Pipeline nach (umgeht `_process_update`), Testnutzer `tg-live-e2e` ohne Vergleiche; E-Mail-Tests nur einteilige `text/plain`-Mails; kein `act_help`-Test; `test_eingangsauswahl_trip_und_vergleich.py:374` zementiert Mehrdeutig. |

### Befehls × Kanal-Matrix (Kurzfassung)
Angebotene Menge = `_COMMAND_SPECS` (12: heute, morgen, jetzt, gewitter, strecke, ruhetag, status, pause, skip, stop, weiter, hilfe) + Metrik-Kürzel (`get_all_metrics`, selectable) + Bot-Menü (glance, heute, morgen, now, heute_gewitter, timeline_heute, timeline_morgen, hilfe) + Knöpfe (`act_overview/pause/skip/columns/help`, `tl_*`, `glance`, `now`, `dd_*`). Kinds je Befehl stehen bereits in `_COMMAND_SPECS` (`_ROUTE_ONLY` / `_BEIDE_KINDS`, `trip_command_processor.py:219-235`).
Weitere Widersprüche **außerhalb Scope**: nicht angeboten aber akzeptiert (abbruch, startdatum, report, Tippwort columns), `/status`=glance in TG vs. Etappenliste in Mail, Vergleichs-Mail bietet keine Befehle → Sammel-Eintrag #1199. Vergleichs-PAUSE ignoriert Dauer trotz Hilfe-Angabe → eigenes Issue (nutzersichtbar).

### Technical Approach
**A. Test-Neuaufbau (Kern, deterministisch, `--disable-socket`) — zuerst, RED:**
- Fixture „PO-Lage": aktiver Trip + mehrere aktive Vergleiche ohne `end_date`, echte `user.json` (telegram_chat_id, verifizierte mail_to, premium_sms_reply_to), echte Trip-/Preset-Dateien (Helfer aus `test_eingangsauswahl_trip_und_vergleich.py:57-150` in gemeinsames Fixture-Modul heben).
- Abfangen **nur am äußersten Netzrand**: `httpx.HTTPTransport.handle_request` (Telegram sendMessage/editMessageText/answerCallbackQuery, seven.io, SMS-Journal/Lern-Endpunkt) und `output.channels.email.smtplib.SMTP` (Antwortmail). Stapelt auf dem autouse-Egress-Guard (`tests/conftest.py:524`). Origin-Guard: Test-Chat-ID + seven-Sandbox-Key in Settings.
- Eingänge echt: Telegram per `TestClient` → `/api/internal/telegram-webhook` (Secret-Header) für Text, Slash, Callback; E-Mail per `_process_single` mit Fake-IMAP (`tests/test_inbound_reader_no_default_settings_lookup.py:107`) und echten RFC822-Bytes in drei Formen (text/plain, nur-HTML Apple-Mail-Struktur, multipart); Premium-SMS per `_poll_journal` mit Journal-Eintrag.
- Parametrisierung **abgeleitet aus den Angebots-Quellen** (`_COMMAND_SPECS`, `BOT_COMMANDS`, Knopf-`callback_data`) → neuer Befehl automatisch mitgetestet. Zusicherung je Fall: keine Fehler-/Mehrdeutig-/Unbekannt-Antwort, erwarteter Inhalt; bei mutierenden Befehlen (pause, skip, stop, ruhetag, weiter) Trip-Zustand auf Platte.
- Vollständigkeit: Menü ⊇ angebotene Befehle, Hilfe ⊇ `_COMMAND_SPECS`.
- Premium-SMS: gemeinsamer `sms_segments(text)` (GSM-7 160/153 inkl. 2-Septet-Erweiterung, UCS-2 70/67); Segmentgrenze für HILFE.
- Zwei-Nutzer-Test (Mandantentrennung) am Telegram-Eingang.

**B. Fixes (GREEN):**
1. Befehlsbewusste Zielauflösung (Telegram + Premium-SMS, eine Stelle): `hilfe` braucht kein Ziel; `_ROUTE_ONLY`-Befehle + Metrik-Kürzel + Query-Keys gehen an den einzigen aktiven Trip, auch wenn Vergleiche existieren; nur `_BEIDE_KINDS` (pause, weiter) bleiben bei Trip+Vergleich mehrdeutig. Löst AC-4 von #2282 ab.
2. E-Mail: fehlt `text/plain`, HTML → Text (bis zum ersten `<blockquote type="cite">` bzw. `lineBreakAtBeginningOfSignature`); BOM/ZWSP/Satzzeichen am Befehlswort tolerieren.
3. `BOT_COMMANDS` aus `_COMMAND_SPECS` ableiten/vervollständigen (Tech-Lead-Entscheidung, in Spec begründen).
4. Callback-Pfad auf dieselbe Zielauflösung; `act_help` als neue Nachricht (Aktionen-Bubble bleibt).
5. Premium-SMS-Hilfe: GSM-7-saubere Kurzform, Ziel ≤ 2 Segmente.

**C. Live-Schicht (Staging, ohne neue Infrastruktur):**
- `run_command_through_pipeline` auf echten `_process_update`; `tg-live-e2e` bekommt einen Vergleich.
- `getMyCommands` gegen Staging-Bot: Menü = erwartete Liste.
- E-Mail-Live-Fall nur-HTML über bestehende Stalwart-Zustellung (`tests/tdd/test_issue_1009_1019_inbound_robustness.py:185`).
- Premium-SMS kostenfrei: Kern-Test bis zum seven.io-Transport + Sandbox-Key; echter inReach-Empfang höchstens einmalig manuell (Antwort auf PO-Frage 3).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_selection.py | MODIFY | befehlsbewusste Auflösung |
| src/services/inbound_telegram_reader.py | MODIFY | Text- + Callback-Pfad mit neuer Auflösung; act_help als neue Nachricht |
| src/services/inbound_sms_reader.py | MODIFY | neue Auflösung; Hilfe-Kurzform |
| src/services/inbound_email_reader.py | MODIFY | HTML-Fallback + Normalisierung |
| src/services/trip_command_processor.py | MODIFY | Hilfe-Kurzform (premium_sms), Wort-Normalisierung |
| src/output/channels/telegram.py | MODIFY | `BOT_COMMANDS` vollständig/abgeleitet |
| tests/tdd/_befehl_e2e_fixtures.py | CREATE | PO-Lage-Nutzer, Transport-Fakes, sms_segments |
| tests/tdd/test_befehle_telegram_e2e.py, test_befehle_email_e2e.py, test_befehle_premium_sms_e2e.py, test_befehlsangebot_vollstaendig.py | CREATE | E2E-Matrix je Kanal + Vollständigkeit |
| tests/tdd/test_eingangsauswahl_trip_und_vergleich.py | MODIFY | Mehrdeutig-Erwartung auf pause/weiter |
| tests/tdd/_telegram_live_fixture.py, test_issue_686_telegram_functional_live.py | MODIFY | echter Eingang, Vergleich im Live-Nutzer |
| docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md | MODIFY | AC-4 „abgelöst durch #2417" |

### Scope Assessment
- Files: ~6 produktiv, ~7 Tests, 1 Doku
- Estimated LoC: produktiv ~+200/-40, Tests ~+700
- Risk Level: HIGH (zentraler Befehlseingang aller Kanäle, Ablösung einer freigegebenen AC); LoC-Override 500 voraussichtlich nötig

### Dependencies
- Upstream: Trip-/Preset-Store, Metrik-Katalog, egress_guard/origin_guard.
- Downstream: alle Befehlsantworten; #2282-Tests; Staging-Live-Tests.

### Open Questions
- [ ] (zur Spec-Freigabe, Produktfrage) AC-4 von #2282 wird abgelöst: nur PAUSE/WEITER fragen bei Trip + Ortsvergleich nach; alle Trip-Befehle gehen direkt an den laufenden Trip; HILFE antwortet immer.
