---
entity_id: feat_2417_befehle_e2e_echter_eingang
type: module
created: 2026-09-25
updated: 2026-09-25
status: draft
version: "1.0"
tags: [tests, telegram, email, premium-sms, befehle, zielauflösung]
---

# Befehle Ende-zu-Ende durch den echten Kanal-Eingang (#2417)

## Approval

- [ ] Approved

## Purpose

Der PO nutzt die vier Antwort-Kanäle produktiv und meldet: „HILFE funktioniert nicht!!!" — belegt für Telegram (B1) und E-Mail (B2), das Telegram-Menü ist unvollständig (B3). Alle bisherigen Tests prüfen `TripCommandProcessor` auf Processor-Ebene; die Fehler sitzen aber im **Eingang davor** (Reader, Zielauflösung, Betreff-/Body-Parsing) — geprüft wurde, wo der Code steht, nicht wo er wirkt (U6). Diese Spec baut die Testschicht neu auf **jeden angebotenen Befehl durch den echten Eingang jedes Kanals bis zur tatsächlich versendeten Antwort** und behebt in derselben Spec die damit aufgedeckten Ursachen U1–U5. Sie **löst AC-4 von `feat_2282_ortsvergleich_eingangskanaele.md` ab**: Nur noch `pause`/`weiter` (die einzigen `_BEIDE_KINDS`-Befehle) fragen bei Trip+Ortsvergleich nach — jeder andere angebotene Befehl (inkl. `hilfe`) erreicht sein Ziel ohne Rückfrage.

## Source

- **Files:**
  - `src/services/trip_selection.py` (`resolve_active_target`, `_vergleich_ist_aktiv`, `KEIN_KANDIDAT_TEXT`)
  - `src/services/inbound_telegram_reader.py` (`_process_update`, `_process_callback_query`, `_CALLBACK_QUERY_MAP`, `_SHORTCUT_MAP`)
  - `src/services/inbound_sms_reader.py` (`_verarbeite_befehl`)
  - `src/services/inbound_email_reader.py` (`_process_single`, `_extract_plain_body`)
  - `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `_show_help`, `command_rows`, `command_overview`, `unknown_command_body`)
  - `src/output/channels/telegram.py` (`BOT_COMMANDS`)
- **Identifier:** siehe Affected Files unten.

> Schicht-Hinweis: alle betroffenen Dateien liegen im Python-Core (`src/services/`, `src/output/`) — keine Go-/Frontend-Änderung nötig.

## Estimated Scope

- **LoC:** produktiv ~200–250 (Hinweis: `workflow.py set-field loc_limit_override 500` einsetzen, falls die Reihenfolge-Umstellung in den drei Readern mehr Zeilen braucht als geschätzt); Tests ~700 (zählen nicht gegen das Limit)
- **Files:** 6 produktiv (MODIFY), 5 Testdateien (CREATE), 2 Testdateien (MODIFY), 1 Doku (MODIFY)
- **Effort:** high — zentraler Befehlseingang aller Kanäle, Ablösung einer freigegebenen AC

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_COMMAND_SPECS` (`trip_command_processor.py:222`) | Upstream | einzige Quelle der 12 Steuerbefehlswörter + `kinds` (`_ROUTE_ONLY`/`_BEIDE_KINDS`) |
| `get_all_metrics()` (Metrik-Katalog) | Upstream | Quelle der Wetter-Kürzel (nur `selectable=True`) |
| `resolve_active_target` (`trip_selection.py`) | Upstream | bisherige (jetzt zu erweiternde) Ziel-Auflösung Trip↔Vergleich |
| `NotificationService` (Telegram/E-Mail/Premium-SMS-Versand) | Upstream | tatsächlicher Versand — Zusicherungspunkt der neuen Tests |
| `tests/tdd/_gsm7_charset.py` | Upstream | GSM-7-Erweiterungszeichen-Tabelle für `sms_segments()` |
| `feat_2282_ortsvergleich_eingangskanaele.md` (AC-4) | Downstream | wird durch diese Spec fachlich abgelöst (Doku-Vermerk, kein neuer Code) |
| `test_eingangsauswahl_trip_und_vergleich.py:374` | Downstream | Erwartung wird auf `pause`/`weiter` verengt |

## Befehls- × Lagen-Matrix (löst #2282 AC-4 ab)

Diese Tabelle ist die verbindliche Referenz sowohl für die Fix- als auch für die Test-ACs. Sie gilt **identisch** für Telegram-Text, Telegram-Knöpfe (Callback) und Premium-SMS — alle drei nutzen dieselbe, gemeinsame Auflösungsfunktion. E-Mail ist nicht Teil dieser Tabelle: dort bestimmt der `[Name]` im Betreff das Ziel bereits eindeutig, es gibt keine Mehrdeutigkeits-Lage.

Spalten (Lagen):

| Kürzel | Lage |
|---|---|
| L1 | 0 Trips, 0 aktive Vergleiche |
| L2 | 1 Trip, 0 aktive Vergleiche |
| L3 | 1 Trip, ≥1 aktive Vergleiche |
| L4 | 0 Trips, genau 1 aktiver Vergleich |
| L5 | 0 Trips, ≥2 aktive Vergleiche |
| L6 | ≥2 Trips, 0 aktive Vergleiche (`pick_active_trip` wählt vorab genau einen — verhält sich danach wie L2) |

„Aktiv" = nicht archiviert, `end_date` nicht in der Vergangenheit (`_vergleich_ist_aktiv`, unverändert).

Zeilen (Befehlsklassen) × Ergebnis je Lage:

| Klasse | Beispiele | L1 | L2 | L3 | L4 | L5 | L6 |
|---|---|---|---|---|---|---|---|
| **Ziellos** | `hilfe`, `columns` | Hilfe | Hilfe | Hilfe | Hilfe | Hilfe | Hilfe |
| **`_ROUTE_ONLY`** | `heute`, `morgen`, `jetzt`/`now`, `gewitter`, `strecke`, `ruhetag`, `status`, `skip`, `stop` | Hinweis „kein aktiver Trip oder Ortsvergleich" | Antwort an Trip | **Antwort an Trip (NEU)** | **Hinweis „kein aktives Ziel" (NEU)** | **Hinweis „kein aktives Ziel" (NEU)** | Antwort an Trip |
| **Metrik-Kürzel + Query-Keys** | Wetter-Kürzel (z. B. `TMAX`), `glance`, `timeline_heute`, `timeline_morgen` | Hinweis „kein aktiver Trip oder Ortsvergleich" | Antwort an Trip | **Antwort an Trip (NEU)** | **Hinweis „kein aktives Ziel" (NEU)** | **Hinweis „kein aktives Ziel" (NEU)** | Antwort an Trip |
| **`_BEIDE_KINDS`** | `pause`, `weiter` | Hinweis „kein aktiver Trip oder Ortsvergleich" | Antwort an Trip | Rückfrage mit Namen (unverändert, alte AC-4) | Antwort an Vergleich | Rückfrage mit Namen (unverändert, alte AC-4) | Antwort an Trip |

Erläuterungen:

- **„Kein aktiver Trip oder Ortsvergleich" (L1, alle Zeilen)** ist der unveränderte, kanalgleiche Text aus `trip_selection.KEIN_KANDIDAT_TEXT` (bisherige AC-5 von #2282) — bleibt exakt so.
- **„kein aktives Ziel" (L4/L5, Zeilen `_ROUTE_ONLY` und Metrik/Query)** ist ein **neuer**, von `KEIN_KANDIDAT_TEXT` bewusst unterschiedener Text: es existiert etwas (ein oder mehrere Vergleiche), aber der jeweilige Befehl kann keinen Vergleich adressieren. Verwechslung mit L1 wäre für den Nutzer irreführend („es gibt doch etwas Aktives").
- **L3/L5 bei `_BEIDE_KINDS`** ist die **einzige** verbleibende Mehrdeutigkeits-Lage aus der alten AC-4 — sie bleibt unverändert bestehen (Rückfrage-Text, `process()` wird nicht aufgerufen, keine Schreiboperation).
- **L6** verhält sich wie L2, weil `pick_active_trip` bereits vor der Vergleichs-Betrachtung genau einen Trip auswählt (unverändert seit #2282 AC-3) — keine neue Mehrdeutigkeit durch mehrere Trips.
- Ein vorangestellter, tolerant normalisierter Name (Trip- oder Vergleichsname) sticht in **jeder** Lage die Tabelle aus und adressiert das benannte Ziel direkt (unverändert, #2282 AC-6/AC-7).

## Premium-SMS-Kurzhilfe

`hilfe` liefert im Premium-SMS-Kanal heute die volle Langhilfe (≈2.000 Zeichen, mit `–`/`→`/`°` ⇒ UCS-2 ⇒ ~31 bezahlte Segmente, U5). Neu: eine Kurzform, die

- **denselben Inhalt wie die Langhilfe** trägt, nur knapper (CLAUDE.md: jeder Kanal beantwortet jede Frage, kein Kanal ist nachrangig): **jedes der 12 `_COMMAND_SPECS`-Befehlswörter mit einer kurzen englischen Bedeutung** und gegebenenfalls seinem Parameter (z. B. `PAUSE 2d`), dazu **alle Wetter-Kürzel** aus `get_all_metrics()` (selectable), wie sie die Langhilfe listet, als kompakte Kürzelliste. Ein neuer Befehl oder eine neue Metrik erscheint automatisch (Vollständigkeits-AC gilt auch hier).
- **nicht auf einen anderen Kanal verweist** („full help via email/Telegram" o. ä. ist verboten). Wer nur Premium-SMS empfängt, muss mit dieser Antwort alle Befehle nutzen können.
- **GSM-7-sauber** ist (kein `–`, `→`, `°`, keine Emojis — Test: `assert_gsm7_clean` bzw. Ableitung über `_gsm7_sicher`),
- die erklärenden Wörter **auf Englisch** hält (PO-Vorgabe: Premium-SMS-Kurznachrichten sind englisch), während die Befehlswörter selbst unverändert bleiben (`HEUTE`, `PAUSE`, … — das sind keine übersetzbaren Labels, sondern die tatsächlich zu sendenden Wörter).

Segmentrechnung (Beleg, keine Wortwahl-Vorschrift): Die 12 Befehle mit englischer Kurzbedeutung, etwa `HEUTE today, MORGEN tomorrow, JETZT now, GEWITTER storms, STRECKE route, RUHETAG rest day, STATUS stages, PAUSE 2d pause, SKIP skip stage, STOP end, WEITER resume, HILFE help`, ergeben ≈ 190 Zeichen. Die Wetter-Kürzel als Liste (2–4 Zeichen je Kürzel) kommen auf ≈ 80–120 Zeichen. Zusammen sind das ≈ 270–310 Zeichen. Mehrteil-SMS tragen je Segment 153 GSM-7-Zeichen (User-Data-Header), also 2 Segmente = 306 und 3 Segmente = 459 Zeichen. **AC-Ziel: ≤ 3 Segmente**, gemessen mit `sms_segments()` am tatsächlich übergebenen Text. Das sind ~3 statt heute ~31 bezahlter Segmente, bei vollem Inhalt. Kürzer auf Kosten des Inhalts ist nicht zulässig.

Die Segmentzählung selbst erfolgt über einen gemeinsamen Test-Helfer `sms_segments(text)` (neu, in `tests/tdd/_befehl_e2e_fixtures.py`): GSM-7 160 Zeichen (1 Segment) / 153 Zeichen je Segment (Mehrteil), unter Einbezug der 2-Septet-Erweiterungszeichen aus `tests/tdd/_gsm7_charset.py::GSM7_EXTENDED_TWO_SEPTET_CHARS` (dort zählt 1 Zeichen = 2 Septets, keine 1:1-Längenrechnung); Fallback UCS-2 70/67 Zeichen falls ein Zeichen nicht GSM-7-faltbar ist (Regressionsschutz, sollte nach Fix nicht mehr eintreten).

## BOT_COMMANDS — Merge, nicht Ersatz

`BOT_COMMANDS` (`telegram.py:111-120`) ist heute eine von `_COMMAND_SPECS` unabhängige, handgepflegte Liste mit 8 Einträgen (`glance`, `heute`, `morgen`, `now`, `heute_gewitter`, `timeline_heute`, `timeline_morgen`, `hilfe`) — `strecke`, `ruhetag`, `pause`, `skip`, `stop`, `weiter` fehlen (B3). Die neue Ableitung bildet die **Vereinigung**: bestehende Einträge bleiben erhalten (sie haben kein 1:1-Pendant in `_COMMAND_SPECS`, z. B. `now`/`heute_gewitter`/`timeline_*`), zusätzlich wird für jedes fehlende `_COMMAND_SPECS`-Wort ein Menüeintrag mit Beschreibung aus `_COMMAND_SPECS` erzeugt, **ausnahmslos, also auch `status`**.

**Auflösung der `/status`-Kollision (Tech-Lead-Entscheidung):** `/status` ist heute in `_SHORTCUT_MAP` als Alias auf `glance` verdrahtet. Das stammt aus der archivierten Spec #651 (`docs/specs/_archive/modules/issue_651_telegram_query_glance.md`), aus einer Zeit, in der der Wetter-Überblick keinen eigenen Menüpunkt hatte. Seither steht `/glance` selbst im Menü, der Alias wird also nicht mehr gebraucht. Gleichzeitig verletzt er die Kanalgleichheit: `STATUS` liefert per E-Mail, Premium-SMS und als nacktes Telegram-Wort die Etappenliste, `/status` in Telegram aber etwas anderes. Deshalb entfällt der Alias. `/status` führt künftig wie `status` die Etappenliste aus, der Wetter-Überblick bleibt über `/glance` und den Knopf `glance` erreichbar. Damit kann `status` ohne Ausnahme ins Menü, und die Lücke aus B3 schließt sich vollständig.

Randbedingung (Telegram Bot-API): Kommandoname `^[a-z0-9_]{1,32}$`, Beschreibung ≤ 256 Zeichen. Alle betroffenen `_COMMAND_SPECS`-Wörter (`strecke`, `ruhetag`, `pause`, `skip`, `stop`, `weiter`) erfüllen das bereits.

## E-Mail-Normalisierung (U2)

`_extract_plain_body` liest ausschließlich `text/plain` (`inbound_email_reader.py:274-287`); eine `multipart/alternative`-Mail mit **nur** `text/html` (Apple-Mail-Standardstruktur bei Antworten auf iPhone) liefert `""` → `_parse_command` findet nichts → „Unbekannter Befehl" (B2, jede Mail-Antwort vom iPhone scheitert). Fix: fehlt `text/plain`, wird der `text/html`-Teil dekodiert und in Text gewandelt, dabei:

- Zitat ab dem ersten `<blockquote type="cite">` abgeschnitten,
- Signatur/Nachsatz ab dem Marker-Element mit `id="lineBreakAtBeginningOfSignature"` abgeschnitten,
- führendes BOM, Zero-Width-Space und Satzzeichen unmittelbar am Befehlswort toleriert (z. B. `﻿Hilfe`, `Hilfe.`, `Hilfe!`).

Die Fixtures bilden exakt die belegte MIME-Struktur nach (QP-kodiert, `charset=utf-8`, `multipart/alternative` nur mit `text/html`-Teil) — **synthetisch**, keine echte Produktionsmail wird committet (Adressen/Inhalte wären personenbezogen). Getestet werden drei Mailformen: reines `text/plain`, reines Apple-Mail-`text/html` (Reproduktion B2), sowie `multipart/alternative` mit beiden Teilen (Regressionsschutz: `text/plain` bleibt bevorzugt, wenn vorhanden).

## Callback-Pfad (U4)

`_process_callback_query` (`inbound_telegram_reader.py:407-432`) verwendet die alte, vergleichsblinde `_find_active_trip` — ein Knopf tut bei „nur Vergleich aktiv" oder bei Mehrdeutigkeit **nichts** (kein Text, nur der Spinner endet). Fix: derselbe klassifizierende Auflösungsweg wie beim Telegram-Text-Eingang, angewendet auf das durch `_CALLBACK_QUERY_MAP` kodierte Kommando (`act_help`→ziellos, `act_pause`→`_BEIDE_KINDS`, `act_skip`/`act_overview`→`_ROUTE_ONLY`/Query, `act_columns`→ziellos, `tl_*`/`glance`/`now`/`dd_*`→Query-Keys). `act_help` sendet dabei **eine neue Nachricht** (nicht `editMessageText` auf die angeklickte Nachricht) — die Aktionen-Bubble mit ihren Knöpfen bleibt dadurch erhalten und bedienbar, statt durch den Hilfetext überschrieben zu werden.

## Test-Architektur (RED zuerst) — echter Eingang, Transport-Fake nur am Netzrand

Kein Mock-Theater: abgefangen wird ausschließlich am äußersten Netzrand —

- `httpx`-Transport für die Telegram-Bot-API (`sendMessage`, `editMessageText`, `answerCallbackQuery`) und für seven.io (Premium-SMS-Versand),
- `smtplib.SMTP` für die Antwortmail.

**Alle** Schichten davor laufen echt:

- **Telegram:** `TestClient` gegen `/api/internal/telegram-webhook` mit korrektem Secret-Header (Text, Slash-Befehl, Callback-Query) — alternativ direkter Aufruf von `_process_update`/`_process_callback_query`, aber niemals eine nachgebaute Pipeline wie in `_telegram_live_fixture.py:316` (die genau deshalb B1 nicht fangen konnte).
- **E-Mail:** `_process_single` mit Fake-IMAP (Muster `tests/test_inbound_reader_no_default_settings_lookup.py:107`) und echten RFC822-Bytes.
- **Premium-SMS:** über den Journal-Eingang (`_poll_journal`/`_verarbeite_befehl`), nicht über einen direkten Funktionsaufruf, der die Lern-/Zuordnungsschritte überspringt.

Zusicherung ausschließlich auf den **tatsächlich versendeten Payload** (Text, `chat_id`/Empfänger, Segmentzahl) am Transport-Fake — nie auf Rückgabewerte eigener Funktionen (sonst wird nur die eigene Annahme gespiegelt). Alle Kern-Tests laufen mit `--disable-socket`.

**PO-Lage-Fixture** (neu, `tests/tdd/_befehl_e2e_fixtures.py`): ein realistischer Nutzer mit genau einem aktiven Trip **und** mehreren aktiven Ortsvergleichen ohne `end_date` — die tatsächliche Lage des PO (KHW 403 + mehrere Vergleiche), nicht die bisherige vergleichsfreie Testlage, die B1 strukturell verdeckt hat. Enthält echte `user.json` (telegram_chat_id, verifizierte `mail_to`, `premium_sms_reply_to`), echte Trip-/Preset-Dateien (Helfer aus `test_eingangsauswahl_trip_und_vergleich.py:57-150` in dieses gemeinsame Modul gehoben).

**Parametrisierung** erfolgt aus den Angebots-Quellen selbst (`_COMMAND_SPECS`, `BOT_COMMANDS`, `_CALLBACK_QUERY_MAP`-Werte, `get_all_metrics()` mit `selectable=True`) — ein neuer Befehl/Knopf/Kürzel wird dadurch automatisch mitgetestet, ohne die Testdatei anzufassen.

## Implementation Details

```
Reader (Telegram-Text, Callback, Premium-SMS):
  1. Befehl klassifizieren, BEVOR das Ziel aufgelöst wird
     (ziellos | _ROUTE_ONLY | Metrik-Kürzel/Query-Key | _BEIDE_KINDS)
  2. ziellos           -> sofort beantworten, keine Trip-/Vergleichs-Ladung noetig
  3. _BEIDE_KINDS       -> bisheriger resolve_active_target() unveraendert
     (Trip+Vergleich bzw. >=2 Vergleiche bleiben mehrdeutig)
  4. sonst (Trip-only)  -> Ziel = pick_active_trip(trips, now_utc); existiert er,
     Antwort an Trip (Vergleiche werden ignoriert); existiert er NICHT,
     aber >=1 Vergleich existiert -> neuer Hinweistext "kein aktives Ziel";
     existiert gar nichts -> KEIN_KANDIDAT_TEXT (unveraendert)
  5. vorangestellter Name sticht Schritt 2-4 immer aus (unveraendert, #2282 AC-6/7)

E-Mail-Reader:
  _extract_plain_body: text/plain vorhanden -> unveraendert;
  sonst text/html-Teil dekodieren, ab erstem <blockquote type="cite">
  und ab lineBreakAtBeginningOfSignature abschneiden, auf Text reduzieren;
  Befehlswort-Erkennung toleriert BOM/ZWSP/Satzzeichen am Wortanfang/-ende.

trip_command_processor.py:
  neue Kurzhilfe-Variante fuer channel="premium_sms" (GSM-7-sauber, Englisch,
  <=3 Segmente, alle Befehle mit Bedeutung + alle Wetter-Kuerzel, kein
  Kanalverweis), Langhilfe fuer email/telegram unveraendert.

telegram.py:
  BOT_COMMANDS als Vereinigung aus bestehenden Eintraegen und den
  _COMMAND_SPECS-Woertern, ohne Ausnahme (auch "status").

inbound_telegram_reader.py:
  _SHORTCUT_MAP: Eintrag "/status" -> "glance" entfaellt; /status fuehrt wie
  das nackte "status" die Etappenliste aus. Glance bleibt ueber /glance.
```

## Expected Behavior

- **Input:** ein angebotener Befehl (Text, Slash, Knopf oder Premium-SMS-Wort) eines Nutzers mit Trip **und** mehreren aktiven Ortsvergleichen, über den echten Kanal-Eingang.
- **Output:** genau die in der Befehls-×-Lagen-Matrix festgelegte Antwort, tatsächlich versendet über den jeweiligen Transport.
- **Side effects:** mutierende Befehle (`pause`, `skip`, `stop`, `ruhetag`, `weiter`) schreiben ausschließlich die Datei des tatsächlich getroffenen Ziels (Trip **oder** Preset, Read-Modify-Write) — nie beide, nie bei Rückfrage/Hinweis.

## Acceptance Criteria

### Tests zuerst (RED an B1–B3/U1–U6, PO-Schwerpunkt)

- **AC-1:** Given der PO-Lage-Nutzer (1 aktiver Trip, mehrere aktive Ortsvergleiche ohne `end_date`) / When er über den echten Telegram-Webhook-Eingang nacheinander jeden `_ROUTE_ONLY`-Befehl sowie jedes Metrik-Kürzel und jeden Query-Key ohne vorangestellten Namen sendet / Then erhält er in jedem Fall die Antwort für seinen einzigen aktiven Trip — keine Rückfrage, kein Fehler, kein „Unbekannter Befehl".
  - Test: `test_befehle_telegram_e2e.py`, parametrisiert über `_COMMAND_SPECS` (Kind `_ROUTE_ONLY`) ∪ `get_all_metrics(selectable=True)` ∪ Query-Keys, Zusicherung auf den tatsächlich per Telegram-Bot-API-Fake gesendeten Text.

- **AC-2:** Given derselbe PO-Lage-Nutzer / When er `hilfe` (oder den Knopf-Äquivalent) sendet / Then antwortet das System **sofort** mit der Befehlsübersicht — reproduziert B1 als roten Test vor dem Fix, grün danach.
  - Test: `test_befehle_telegram_e2e.py::test_hilfe_bei_trip_und_vergleich_antwortet_sofort`.

- **AC-3:** Given derselbe PO-Lage-Nutzer / When er `pause` bzw. `weiter` ohne Namen sendet / Then erhält er weiterhin die Rückfrage mit allen Kandidatennamen (Trip + alle aktiven Vergleiche) — diese eine Zelle der Matrix bleibt unverändert.
  - Test: `test_befehle_telegram_e2e.py::test_pause_weiter_bleiben_mehrdeutig`.

- **AC-4:** Given ein Nutzer ohne aktiven Trip und mit ≥1 aktivem Ortsvergleich / When er einen `_ROUTE_ONLY`-Befehl oder ein Metrik-Kürzel sendet / Then erhält er den neuen Hinweis „kein aktives Ziel" — unterscheidbar vom Text für „gar nichts aktiv".
  - Test: `test_befehle_telegram_e2e.py` **und** `test_befehle_premium_sms_e2e.py`, parametrisiert über L4/L5-Fixturen, Textvergleich gegen beide unterschiedlichen Konstanten.

**Matrix-Vollabdeckung (gilt für alle Test-ACs):** Die Befehls-×-Lagen-Tabelle (4 Befehlsklassen × 6 Lagen L1–L6) wird in **jedem Kanal, der sie benutzt**, vollständig durchlaufen — Telegram-Text, Telegram-Knöpfe **und** Premium-SMS —, jeweils durch den echten Eingang und mit der von der Tabelle vorgeschriebenen Antwort als Zusicherung. Die Tests leiten ihre Fälle aus einer im Fixture-Modul hinterlegten Soll-Tabelle ab; **fehlt für einen Kanal eine Zelle, schlägt ein Vollständigkeits-Test fehl.** E-Mail ist ausgenommen, weil dort das Ziel über den `[Name]` im Betreff bestimmt wird und die Tabelle nicht greift.

- **AC-5:** Given der PO-Lage-Nutzer / When er dieselben Befehle über den echten Premium-SMS-Journal-Eingang sendet, jeden Befehl **einmal ohne und einmal mit** angehängtem `inreachlink.com`-Kartenlink (der Link ist eine abschaltbare Geräteeinstellung, beide Formen sind Normalfall) (kein bezahlter Versand — nur der `httpx`-Transport zu seven.io ist gefaked) / Then ist das Ergebnis inhaltlich identisch zu AC-1 (dieselbe geteilte Auflösung).
  - Test: `test_befehle_premium_sms_e2e.py`, gleiche Parametrisierung wie AC-1, Zusicherung auf den an den seven.io-Fake übergebenen Text und die Empfängernummer.

- **AC-6:** Given eine echte, synthetisch nachgebaute Apple-Mail-Antwort (`multipart/alternative`, nur `text/html`, QP, `Hilfe` als erstes sichtbares Wort vor Zitat/Signatur) / When sie über `_process_single` mit Fake-IMAP verarbeitet wird / Then wird `hilfe` erkannt und die Befehlsübersicht per Antwortmail verschickt — reproduziert B2 als roten Test vor dem Fix.
  - Test: `test_befehle_email_e2e.py::test_apple_mail_nur_html_wird_erkannt`.

- **AC-7:** Given dieselbe MIME-Fixture-Familie in allen drei Formen — reines `text/plain`, `multipart/alternative` mit beiden Teilen und die Apple-Mail-Form aus AC-6 (nur `text/html` mit Zitat und Signatur) / When jeweils **jeder** `_COMMAND_SPECS`-Befehl per E-Mail gesendet wird / Then wird er in allen drei Formen korrekt ausgeführt, und die tatsächlich über SMTP versendete Antwortmail enthält das für diesen Befehl festgelegte Inhaltsmerkmal (siehe „Inhaltsmerkmal je Befehl" unten) — „es kam irgendeine Antwort" genügt nicht.
  - Test: `test_befehle_email_e2e.py`, parametrisiert über `_COMMAND_SPECS` × 3 MIME-Formen.

**Inhaltsmerkmal je Befehl (gilt für AC-1, AC-5, AC-7, AC-8):** `tests/tdd/_befehl_e2e_fixtures.py` führt eine Tabelle `ERWARTETES_MERKMAL`, die für **jeden** angebotenen Befehl, jedes Metrik-Kürzel/Query-Key und jeden Knopf (`callback_data`) festlegt, woran die richtige Antwort erkennbar ist — abgeleitet aus den Fixture-Daten, nicht aus dem Produktcode. Beispiele: `heute` → Name der heutigen Etappe des Fixture-Trips; `morgen` → Name der morgigen Etappe; `strecke` → alle Etappennamen in Reihenfolge; `hilfe`/`act_help` → alle 12 `_COMMAND_SPECS`-Befehlswörter; Metrik-Kürzel → Anzeigename der Metrik; `pause`/`skip`/`stop`/`ruhetag`/`weiter` → Bestätigungstext **und** Plattenzustand (AC-13); `act_columns` → Metrik-Auswahlknöpfe im gesendeten `reply_markup`. Jede Antwort muss außerdem frei von den Fehlertexten sein (Mehrdeutig, Unbekannter Befehl, kein aktives Ziel — außer dort, wo die Matrix genau diesen Hinweis verlangt). **Fehlt für einen aus den Angebotsquellen abgeleiteten Fall ein Tabelleneintrag, schlägt der Test fehl** — ein neuer Befehl kann so nicht mit bloßem „kam eine Antwort" durchrutschen.

- **AC-8:** Given der PO-Lage-Nutzer / When er per Telegram nacheinander jeden in `_CALLBACK_QUERY_MAP` angebotenen Knopf klickt (`act_overview`, `act_pause`, `act_skip`, `act_columns`, `act_help`, `tl_today`, `tl_tomorrow`, `glance`, `heute`, `morgen`, `now`) / Then reagiert jeder Knopf mit der laut Matrix erwarteten Antwort, deren tatsächlich gesendeter Text bzw. `reply_markup` das Inhaltsmerkmal des Knopfes aus `ERWARTETES_MERKMAL` enthält — Stillschweigen oder eine beliebige Antwort genügt nicht. Dasselbe gilt für einen Nutzer in Lage L4 (0 Trips, genau 1 aktiver Vergleich) und in Lage L5 (0 Trips, ≥2 Vergleiche): jeder Knopf erzeugt einen tatsächlich versendeten Telegram-Aufruf mit der Antwort, die die Matrix für diese Zelle vorschreibt (Vergleichs-Antwort mit Vergleichsname, Hinweis „kein aktives Ziel" oder Rückfrage mit allen Vergleichsnamen) — reproduziert U4 als roten Test vor dem Fix.
  - Test: `test_befehle_telegram_e2e.py`, parametrisiert über `_CALLBACK_QUERY_MAP` × Lagen {PO-Lage, L4, L5}; deckt AC-22 ab.

- **AC-9:** Given `act_help` wird auf eine Aktionen-Bubble mit Knöpfen geklickt / When die Hilfeantwort ankommt / Then ist sie eine **neue** Nachricht, und die ursprüngliche Aktionen-Bubble samt ihrer Knöpfe bleibt unverändert im Chat bestehen und weiterhin bedienbar.
  - Test: `test_befehle_telegram_e2e.py::test_act_help_ueberschreibt_die_aktionen_bubble_nicht` — prüft, dass `editMessageText` auf die ursprüngliche `message_id` NICHT aufgerufen wird und stattdessen `sendMessage` mit neuem Text erfolgt.

- **AC-10:** Given `_COMMAND_SPECS` gilt als Angebotsquelle / When das Telegram-Menü (`BOT_COMMANDS`) und die Langhilfe (E-Mail/Telegram) sowie die Premium-SMS-Kurzhilfe geprüft werden / Then enthalten Menü, Langhilfe und Kurzhilfe alle 12 Befehlswörter, ohne Ausnahme. Lang- und Kurzhilfe enthalten zusätzlich jedes Wetter-Kürzel aus `get_all_metrics()` (selectable), und die Kurzhilfe enthält keinen Verweis auf einen anderen Kanal.
  - Test: `test_befehlsangebot_vollstaendig.py`, drei Teilprüfungen (Menü, Langhilfe, Kurzhilfe) gegen `_COMMAND_SPECS` ∪ Metrik-Kürzel als Referenzmenge, dazu die Negativprüfung „kein `email`/`Telegram`/`Mail` in der Kurzhilfe".

- **AC-11:** Given die Premium-SMS-Kurzhilfe aus AC-10 / When sie über den echten seven.io-Fake versendet wird / Then ist sie GSM-7-sauber (kein `–`, `→`, `°`, keine Emojis) und benötigt höchstens 3 Segmente, gemessen mit `sms_segments()` auf dem tatsächlich übergebenen Text.
  - Test: `test_befehle_premium_sms_e2e.py::test_kurzhilfe_hoechstens_drei_segmente` (Schwelle 3, gemessen mit `sms_segments()`).

- **AC-12:** Given zwei verschiedene Nutzer A und B mit je eigenem Trip/Vergleichen und eigener `telegram_chat_id` / When Nutzer A per Telegram einen Befehl sendet / Then trifft die Ausführung ausschließlich Trips/Vergleiche von A, und die Antwort geht ausschließlich an A's `chat_id` — B's Daten werden weder gelesen noch beantwortet.
  - Test: `test_befehle_telegram_e2e.py::test_mandantentrennung_am_telegram_eingang`.

- **AC-13:** Given ein mutierender Befehl (`pause`, `skip`, `stop`, `ruhetag`, `weiter`) wird über einen der drei Eingänge ausgeführt / When die tatsächlich geschriebene Trip- bzw. Preset-Datei danach gelesen wird / Then entspricht ihr Inhalt der erwarteten Änderung (Read-Modify-Write, kein Datenverlust an unbeteiligten Feldern) — Zusicherung auf Plattenzustand, nicht auf Rückgabewert.
  - Test: parametrisierter Block in `test_befehle_telegram_e2e.py`/`test_befehle_premium_sms_e2e.py`/`test_befehle_email_e2e.py`.

- **AC-14:** Given `test_eingangsauswahl_trip_und_vergleich.py:374` zementiert bislang Mehrdeutigkeit für **jeden** Befehl ohne Namen bei Trip+Vergleich / When diese Spec umgesetzt ist / Then ist die Erwartung dort auf `pause`/`weiter` verengt, alle anderen dort zuvor mitgeprüften Befehle werden gemäß AC-1 auf „Antwort an Trip" umgestellt.
  - Test: Anpassung von `test_eingangsauswahl_trip_und_vergleich.py` selbst (keine neue Datei), Kernschicht bleibt 100 % grün.

### Fixes (GREEN, gedeckt durch die Tests oben)

- **AC-15:** Given ein Nutzer mit 1 aktivem Trip und ≥1 aktivem Ortsvergleich / When er `hilfe` oder den Knopf `act_help`/`act_columns` sendet / Then wird **keine** Zielauflösung (Trip/Vergleich) durchgeführt, bevor geantwortet wird — der Reader erkennt „ziellos" vor jeder Ladung von Trips/Presets.

- **AC-16:** Given dieselbe Lage / When ein `_ROUTE_ONLY`-Befehl, ein Metrik-Kürzel oder ein Query-Key ohne Namen gesendet wird / Then wird er direkt an den einzigen aktiven Trip weitergeleitet, unabhängig von der Anzahl aktiver Ortsvergleiche.

- **AC-17:** Given kein aktiver Trip, aber ≥1 aktiver Ortsvergleich / When einer der Befehle aus AC-16 gesendet wird / Then antwortet das System mit dem neuen Hinweis „kein aktives Ziel" statt mit der alten Mehrdeutigkeits-Rückfrage oder einem stillen Fehlschlag.

- **AC-18:** Given Premium-SMS nutzt dieselbe Auflösungsfunktion wie Telegram / When AC-15–AC-17 für Premium-SMS wiederholt werden / Then ist das Verhalten identisch — eine Änderung an der geteilten Stelle wirkt in beiden Kanälen gleichzeitig.

- **AC-19:** Given eine eingehende Mail ohne `text/plain`-Teil, aber mit `text/html` / When `_process_single` sie verarbeitet / Then wird der HTML-Teil in Text gewandelt, das Zitat ab dem ersten `<blockquote type="cite">` und der Anhang ab `lineBreakAtBeginningOfSignature` abgeschnitten, bevor der Befehl erkannt wird.

- **AC-20:** Given ein Befehlswort ist von einem BOM, einem Zero-Width-Space, einem geschützten Leerzeichen, Leerraum oder unmittelbar folgenden Satzzeichen umgeben / When es über den echten Eingang von E-Mail (in allen drei Mailformen aus AC-7), Telegram oder Premium-SMS ankommt / Then wird der Befehl trotzdem erkannt und genauso beantwortet wie das nackte Wort.
  - Test: `test_befehlswort_toleranz_e2e.py`, parametrisiert über Kanal {E-Mail, Telegram, Premium-SMS} × Variante. Die Varianten mindestens: `Hilfe.`, `HILFE!`, `hilfe?`, `Hilfe,`, `﻿Hilfe` (BOM davor), `Hilfe​` (Zero-Width-Space danach), ` Hilfe ` (geschützte Leerzeichen), `  hilfe  \n`, `Heute.`, `Pause!`. Zusicherung: Der tatsächlich gesendete Antworttext entspricht dem der nackten Form (gleiches Inhaltsmerkmal, kein „Unbekannter Befehl"). Gegenprobe: Ein echtes Fremdwort wie `Hilfen` oder `Heutegestern` wird **nicht** als Befehl erkannt. Die Toleranz darf also nicht in beliebiges Präfix-Matching ausarten.

- **AC-21:** Given `BOT_COMMANDS` wird aus `_COMMAND_SPECS` abgeleitet / When das Menü zusammengestellt wird / Then enthält es zusätzlich zu den bestehenden 8 Einträgen **jedes der 12 `_COMMAND_SPECS`-Wörter als eigenen Eintrag unter genau diesem Namen**, also auch `jetzt` und `gewitter` neben den bestehenden `now` und `heute_gewitter`, dazu `strecke`, `ruhetag`, `status`, `pause`, `skip`, `stop`, `weiter`, und jeder Menüeintrag löst beim Antippen genau den Befehl aus, den seine Beschreibung nennt.

- **AC-28:** Given der PO-Lage-Nutzer / When er in Telegram `/status` über das Menü oder als Text sendet / Then erhält er dieselbe Etappenliste wie mit `STATUS` per E-Mail oder Premium-SMS und nicht mehr den Wetter-Überblick. Der Wetter-Überblick kommt weiterhin mit `/glance`.

### Einbettung Epic #2133 („jede Metrik, ab jetzt, auf jedem Kanal“)

Epic #2133 ist geschlossen, alle Scheiben (S1 #2134, S2 #2185/#2186, S3 #2168/#2126, S4 #2184, S5 #2207) gelten als ausgeliefert. Diese Spec prüft ihre Zusagen ebenfalls durch den echten Eingang, denn genau dieses „als fertig gemeldet“ ist der Anlass von #2417. Wird dabei ein Test rot, gehört der Fix in diesen Workflow (Test→Fix-Kopplung). Übersteigt er den Rahmen, wird er mit konkretem Befund eskaliert und nicht still ausgeklammert.

- **AC-30:** Given der PO-Lage-Nutzer / When er über den echten Eingang **jedes der drei Kanäle** (E-Mail in allen drei Mailformen, Telegram, Premium-SMS) jede wählbare Wetter-Größe aus `get_all_metrics()` abfragt, und zwar sowohl mit dem deutschen Katalogwort als auch mit dem Kürzel / Then liefert jede Abfrage einen Verlauf genau dieser Größe mit ihrer Katalog-Einheit, unabhängig von der Metrikauswahl des Trips. Der Nebelfall aus dem Epic („Wolken“ bzw. „Sicht“) ist als benannter Einzelfall in allen drei Kanälen enthalten.
  - Test: `test_abruf_jede_metrik_e2e.py`, parametrisiert über Kanal × Metrik × Schreibweise, abgeleitet aus dem Katalog (neue Metrik ⇒ automatisch mitgetestet).
- **AC-31:** Given eine eingefrorene Uhrzeit mitten am Tag (z. B. 15:00 Ortszeit) / When eine Größe oder `heute` abgefragt wird / Then beginnt der gesendete Verlauf bei der aktuellen Stunde, enthält keine vergangenen Stunden, und Tageswerte rechnen keine vergangenen Stunden mit (Zusagen S2/#2186). Premium-SMS und Telegram-Kurzform zeigen Wechselpunkte mit Katalog-Kürzeln statt einer Tabelle (Zusage S5).
  - Test: `test_abruf_jede_metrik_e2e.py::test_ab_jetzt_*` mit fester Uhr und Fixture-Wetterdaten, deren Vormittagswerte sich erkennbar von den Nachmittagswerten unterscheiden.
- **AC-32:** Given ein Befehl oder eine Abfrage kommt über genau einen Kanal von einem bestimmten Absender / When die Antwort verschickt wird / Then geht sie **nur** über diesen Eingangskanal und **nur** an diesen Absender (Telegram-`chat_id` des Absenders, `From`-Adresse der Mail, Absendernummer der SMS). Auf keinem anderen Kanal entsteht ein Versand (Zusage S3/#2126/#2168). Der Zwei-Nutzer-Test aus AC-12 gilt entsprechend für E-Mail und Premium-SMS.
  - Test: `test_befehle_*_e2e.py`: Die Transport-Fakes aller Kanäle zeichnen jeden Versand auf. Zugesichert wird genau ein Versand, auf dem richtigen Kanal, an den richtigen Empfänger.
- **AC-33:** Given eine abgefragte Größe ist im Gebiet des Trips nicht befüllt (Fixture-Wetterdaten ohne diese Größe) / When sie in einem der drei Kanäle abgefragt wird / Then sagt die gesendete Antwort ausdrücklich, dass für diese Größe keine Daten vorliegen, statt zu schweigen, eine Fehlermeldung zu schicken oder „Unbekannter Befehl“ zu melden („geführt ≠ gefüllt“ aus dem Epic).
  - Test: `test_abruf_jede_metrik_e2e.py::test_fehlende_groesse_wird_benannt`.

- **AC-29:** Given ein Nutzer spricht einen Ortsvergleich an (eindeutig oder per Namen) / When er die Hilfe für den Vergleich abruft oder `pause 2d` an den Vergleich sendet / Then bietet die Vergleichshilfe (`_show_help_for_kind("vergleich")`) `PAUSE` **ohne** Daueranhang an, und die Antwort auf `pause 2d` sagt ausdrücklich, dass die Pause beim Ortsvergleich unbefristet gilt, bis `WEITER` kommt, und dass die Dauer nicht ausgewertet wurde. Das Verhalten selbst (unbefristete Pause, #2282 AC-8) bleibt unverändert, nur Angebot und Antwort stimmen jetzt damit überein. In der Trip-Hilfe bleibt `PAUSE [2d/12h]` unverändert.
  - Test: `test_befehle_telegram_e2e.py` und `test_befehle_premium_sms_e2e.py`: Die Vergleichshilfe enthält `PAUSE`, aber keine Dauerangabe. `pause 2d` an einen Vergleich liefert einen gesendeten Text, der „unbefristet"/„bis WEITER" und den Hinweis auf die nicht ausgewertete Dauer enthält, und der Plattenzustand zeigt die unbefristete Pause.
  - Test: `test_befehle_telegram_e2e.py`: `/status` und `status` liefern denselben gesendeten Inhalt (Etappennamen des Fixture-Trips), `/glance` liefert weiterhin den Überblick. Zusätzlich prüft `test_befehlsangebot_vollstaendig.py` für **jeden** `BOT_COMMANDS`-Eintrag, dass sein Befehl über den echten Eingang das Inhaltsmerkmal aus `ERWARTETES_MERKMAL` liefert. Ein Menüpunkt, der etwas anderes auslöst als beschrieben, wird dadurch rot.

- **AC-22:** Given ein Knopf wird geklickt, während nur ein Ortsvergleich (kein Trip) aktiv ist, oder während eine Mehrdeutigkeits-Lage besteht / When `_process_callback_query` läuft / Then erhält der Nutzer eine sichtbare Antwort (Ziel-Antwort, Hinweis oder Rückfrage) statt eines stillen No-Ops.

- **AC-23:** Given Premium-SMS-Kanal / When `hilfe` gesendet wird / Then wird die neue Kurzhilfe (≤ 3 Segmente, voller Inhalt, siehe oben) verschickt statt der bisherigen Langhilfe.

### Live-Schicht (Staging, Marker `live`/`staging`)

- **AC-24:** Given der Staging-Live-Testnutzer `tg-live-e2e` bekommt zusätzlich einen echten Ortsvergleich über die Staging-API (Pflichtfelder `id` und `schedule`, da `hem` keinen Dateizugriff auf Staging-Nutzerdaten hat) / When die Live-Pipeline (`_telegram_live_fixture.py`) auf den echten `_process_update`-Pfad umgestellt wird und dieselben Kern-Befehle gegen den Staging-Bot sendet / Then bestätigt eine echte Telegram-Zustellung dasselbe Verhalten wie die Kernschicht — insbesondere B1 tritt auf Staging nicht mehr auf.

- **AC-25:** Given der Staging-Bot / When `getMyCommands` gegen ihn aufgerufen wird / Then entspricht die zurückgegebene Liste exakt der in AC-21 festgelegten, vollständigen Menüliste.

- **AC-26:** Given die bestehende Stalwart-Testzustellung (`gregor-test@henemm.com`) / When eine reine `text/html`-Mail (Apple-Mail-Form) dorthin zugestellt und automatisch verarbeitet wird / Then wird der enthaltene Befehl erkannt und beantwortet — Live-Nachweis für AC-6/AC-19 auf echtem Zustellweg.
  - Test: `tests/tdd/test_befehle_email_live.py` (CREATE, Marker `live` + `email`). Er stellt eine synthetische Apple-Mail-Antwort (nur `text/html`, Zitat, Signatur, Betreff `Re: [<Testtrip>] …`) mit `Hilfe` über SMTP an das Stalwart-Testpostfach zu, löst die Verarbeitung aus und liest die Antwortmail per IMAP ab. Zusicherung: Die Antwort enthält alle 12 Befehlswörter. Das Muster der Zustellung stammt aus `test_issue_1009_1019_inbound_robustness.py:185`. Pflicht in `/e2e-verify`, nicht optional.

- **AC-27 (echter Premium-SMS-Dialog, zweite seven.io-Nummer statt Garmin-Gerät):** Given die zweite seven.io-Nummer des PO übernimmt die Rolle des Garmin-inReach (sie ist die gespeicherte Premium-SMS-Rückadresse des PO-Kontos, und ihr Eingang ist über das seven.io-Journal lesbar) / When nach dem Prod-Deploy von dieser Nummer SMS an die Premium-SMS-Empfangsnummer geschickt werden, nacheinander für `hilfe`, `status` und ein Wetter-Kürzel, und zwar **überwiegend ohne Kartenlink** (Normalfall-Prüfung: der `inreachlink.com`-Kartenlink ist eine **abschaltbare** Geräteeinstellung und darf nie Voraussetzung sein; seit #2323 gilt die Nachricht als Eingang, weil sie an die Service-Nummer geht) und **einmal mit** angehängtem Kartenlink (der Link wird vom Befehl abgetrennt und stört nicht) / Then läuft jede Nachricht durch den **echten Produktions-Eingang** (Journal-Poll, Absender-Zuordnung, Zielauflösung, Befehlsverarbeitung, Versand), und die Antwort kommt **an der zweiten Nummer an**. Die ausführende Sitzung liest das selbst über das seven.io-Eingangsjournal (`journal/inbound`) ab, **nicht der PO und nicht am Gerät**. Geprüft wird für jede Antwort: Sie kommt innerhalb von 15 Minuten an (drei Poll-Zyklen), trägt das Inhaltsmerkmal aus `ERWARTETES_MERKMAL`, ist vollständig und unverstümmelt (GSM-7, keine Ersatzzeichen), und `hilfe` kommt mit höchstens 3 Segmenten an (AC-11). Bleibt eine Antwort aus, ist das ein Befund und kein Flake: Es wird stufenweise geprüft (Ausgangsjournal: verschickt? Eingangsjournal Premium-Nummer: angekommen? Prod-Log: verarbeitet?), wie in #2322. Kosten: ca. 6 bezahlte SMS je Auslieferung. Die Nummern kommen aus der Konfiguration, nie aus Spec- oder Testtext. Der Lauf ist Pflichtschritt nach dem Prod-Deploy, weil die Herkunftssperre den Premium-SMS-Eingang außerhalb der Produktion bewusst abschaltet (Staging teilt sich den seven.io-Posteingang).

## Out of Scope

- Nicht angeboten, aber vom Processor akzeptiert (`abbruch`, `startdatum`, `report`, Tippwort `columns` als Text statt Knopf) — eigenes Issue **#2420** (anbieten oder entfernen, je Befehl), kein Fix hier.
- Ortsvergleichs-Mail bietet grundsätzlich keine Befehle (kein Antwort-Kommando-Block in der Vergleichs-Mail) — eigenes Issue **#2420** (ändert das Compare-Mail-Template, eigener Renderer-Gate-Pfad).
- Die Produktfrage, ob ein Ortsvergleich künftig **befristet** pausierbar sein soll (Ablösung von #2282 AC-8), bleibt in Issue **#2418**. Den Widerspruch zwischen Hilfe-Angebot und Verhalten schließt diese Spec mit AC-29.
- Test am physischen Garmin-Gerät. Die zweite seven.io-Nummer ersetzt es vollständig: Sie sendet wie das Gerät und empfängt wie das Gerät (AC-27).

## Testplan

| Datei | Inhalt |
|---|---|
| `tests/tdd/_befehl_e2e_fixtures.py` (CREATE) | PO-Lage-Nutzer (Trip + mehrere Vergleiche), Transport-Fakes (httpx-Transport Telegram/seven.io, smtplib.SMTP), `sms_segments(text)` |
| `tests/tdd/test_befehle_telegram_e2e.py` (CREATE) | AC-1, AC-2, AC-3, AC-4, AC-8 (Knöpfe in PO-Lage, L4, L5 — sichert AC-22), AC-9, AC-12, AC-13 (Telegram-Anteil) |
| `tests/tdd/test_befehle_email_e2e.py` (CREATE) | AC-6, AC-7, AC-13 (E-Mail-Anteil) |
| `tests/tdd/test_befehle_premium_sms_e2e.py` (CREATE) | AC-4 (Premium-SMS-Anteil), AC-5, AC-11, AC-13 (Premium-SMS-Anteil), Matrix-Vollabdeckung L1–L6 |
| `tests/tdd/test_premium_sms_empfang_live.py` (CREATE, Marker `live`, nur mit ausdrücklicher Freigabevariable) | AC-27: echter Dialog in Produktion. Von der zweiten seven.io-Nummer werden `hilfe`, `status` und ein Wetter-Kürzel an die Premium-Nummer geschickt, überwiegend ohne Kartenlink (Link abschaltbar) und einmal mit `inreachlink.com`-Link. Danach wird `journal/inbound` der zweiten Nummer abgefragt und je Antwort Inhalt, Unverstümmeltheit, Segmentzahl und Laufzeit geprüft (Nummern aus Env). **Pflichtschritt nach dem Prod-Deploy**, vor dem Issue-Close. |
| `tests/tdd/test_befehlsangebot_vollstaendig.py` (CREATE) | AC-10, AC-21, AC-28 (jeder Menüeintrag löst den beschriebenen Befehl aus) |
| `tests/tdd/test_abruf_jede_metrik_e2e.py` (CREATE) | AC-30, AC-31, AC-33 (Epic #2133 durch den echten Eingang) |
| `tests/tdd/test_befehlswort_toleranz_e2e.py` (CREATE) | AC-20 (Satzzeichen, BOM, Zero-Width-Space, geschützte Leerzeichen × E-Mail/Telegram/Premium-SMS, mit Fremdwort-Gegenprobe) |
| `tests/tdd/test_issue_651_telegram_query_glance.py`, `tests/tdd/test_adhoc_abruf_am_telegram_draht.py` (MODIFY) | Erwartung `/status` → `glance` wird zu `/status` → `status` (AC-28); `/s` → `glance` bleibt unverändert |
| `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` (MODIFY) | AC-14 |
| `tests/tdd/_telegram_live_fixture.py`, `test_issue_686_telegram_functional_live.py` (MODIFY) | AC-24, AC-25 |
| `tests/tdd/test_befehle_email_live.py` (CREATE, live/email) | AC-26: iPhone-Mail-Form über echte Stalwart-Zustellung, Antwort per IMAP geprüft (Muster aus `test_issue_1009_1019_inbound_robustness.py:185`) |

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_selection.py` | MODIFY | befehlsklassenbewusste Auflösung, neuer „kein aktives Ziel"-Text |
| `src/services/inbound_telegram_reader.py` | MODIFY | Text- + Callback-Pfad mit neuer Auflösung; `act_help` als neue Nachricht |
| `src/services/inbound_sms_reader.py` | MODIFY | neue Auflösung; Kurzhilfe-Weiterleitung |
| `src/services/inbound_email_reader.py` | MODIFY | HTML-Fallback + Zeichen-Normalisierung |
| `src/services/trip_command_processor.py` | MODIFY | Premium-SMS-Kurzhilfe |
| `src/output/channels/telegram.py` | MODIFY | `BOT_COMMANDS` aus `_COMMAND_SPECS` abgeleitet |
| `tests/tdd/_befehl_e2e_fixtures.py` | CREATE | PO-Lage-Nutzer, Transport-Fakes, `sms_segments` |
| `tests/tdd/test_befehle_telegram_e2e.py` | CREATE | E2E-Matrix Telegram (Text + Callback) |
| `tests/tdd/test_befehle_email_e2e.py` | CREATE | E2E-Matrix E-Mail (drei MIME-Formen) |
| `tests/tdd/test_befehle_premium_sms_e2e.py` | CREATE | E2E-Matrix Premium-SMS + Segmentgrenze |
| `tests/tdd/test_befehlsangebot_vollstaendig.py` | CREATE | Vollständigkeit Menü/Langhilfe/Kurzhilfe |
| `tests/tdd/test_befehlswort_toleranz_e2e.py` | CREATE | AC-20: Satzzeichen/unsichtbare Zeichen × drei Kanäle |
| `tests/tdd/test_abruf_jede_metrik_e2e.py` | CREATE | AC-30, AC-31, AC-33: Epic-#2133-Zusagen (jede Metrik, ab jetzt, Lücke benannt) × drei Kanäle |
| `tests/tdd/test_befehle_email_live.py` | CREATE | AC-26: Live-Zustellung iPhone-Mailform |
| `tests/tdd/test_premium_sms_empfang_live.py` | CREATE | AC-27: echter Premium-SMS-Dialog, zweite seven.io-Nummer als Testgerät |
| `tests/tdd/test_issue_651_telegram_query_glance.py`, `tests/tdd/test_adhoc_abruf_am_telegram_draht.py` | MODIFY | `/status`-Erwartung (AC-28) |
| `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` | MODIFY | Mehrdeutig-Erwartung auf `pause`/`weiter` verengt |
| `tests/tdd/_telegram_live_fixture.py` | MODIFY | echter `_process_update`-Pfad, Live-Nutzer mit Vergleich |
| `tests/tdd/test_issue_686_telegram_functional_live.py` | MODIFY | `getMyCommands`-Abgleich (AC-25) |
| `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md` | MODIFY | Status-Vermerk bei AC-4: „abgelöst durch feat_2417" |

## Known Limitations

- Der neue Hinweistext „kein aktives Ziel" ist ein Produkttext-Neuzugang; sein genauer Wortlaut wird während der Implementierung festgelegt (muss sich nur von `KEIN_KANDIDAT_TEXT` unterscheiden lassen).
- Der echte, bezahlte Premium-SMS-Dialog läuft nicht in jedem Testlauf, sondern einmal je Auslieferung nach dem Prod-Deploy (AC-27). Die zweite seven.io-Nummer ist dabei das Testgerät.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Die Ablösung von #2282 AC-4 ist eine Verhaltenskorrektur einer freigegebenen Spec-AC (Kanal-Eingang), keine neue Grundsatzentscheidung über Kanäle/Provider/Datenmodell/Auth/Editor-Paradigma/Test-Strategie im Sinne der ADR-Kriterien aus `CLAUDE.md`. Die Ablösung wird stattdessen über den dokumentierten Spec-Supersede-Mechanismus vollzogen (Status-Vermerk in `feat_2282_ortsvergleich_eingangskanaele.md`, siehe Affected Files).

## Changelog

- 2026-09-25: Initial spec created (Issue #2417, PO-Klarstellung 25.09.: Test-Schwerpunkt vor Einzel-Fix).
- 2026-09-25: PO-Rückfrage bei der Freigabe. Die STATUS-Ausnahme im Menü entfällt: Der `/status`→`glance`-Alias wird aufgelöst (neue AC-28). AC-20 gilt jetzt für alle drei Kanäle und hat einen eigenen Test. AC-27 prüft den echten Premium-SMS-Empfang über die zweite seven.io-Nummer. Die Premium-SMS-Kurzhilfe trägt den vollen Inhalt: alle Befehle mit Bedeutung und alle Wetter-Kürzel, ohne Verweis auf andere Kanäle, ≤ 3 Segmente. Der Live-Test für AC-26 ist als eigene Datei fest eingeplant. Neue AC-29: Vergleichshilfe und Vergleichs-Pause-Antwort stimmen mit dem unbefristeten Verhalten überein. Die PO-Rückfrage zum Epic #2133 ist eingearbeitet: Neue AC-30 bis AC-33 prüfen dessen Zusagen durch den echten Eingang aller drei Kanäle (jede Metrik in beiden Schreibweisen, ab jetzt, Antwort nur an den Fragenden auf dem Eingangskanal, fehlende Daten benannt).
