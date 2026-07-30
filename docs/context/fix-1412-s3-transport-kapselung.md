# Context: fix-1412-s3-transport-kapselung

Issue #1412, Lieferung **S3 — Transport-Kapselung**. Vorgänger S1 (`1e4cc6b7`),
S2a (`ee922264`), S2b (`279cc6dc`) sind live. Grundlage:
`docs/context/fix-1412-versandweg-basis.md` (Bestandsaufnahme aller 26
Versandwege) und die vier Abschluss-Kommentare an #1412.

Alle Angaben unten sind **am Code gemessen**, Stand `279cc6dc`, nicht aus der
Vorgeschichte übernommen. Drei parallele Lese-Recherchen (E-Mail-Sendeweg /
Telegram-Guards / SMS+Totcode+Test-Vorbilder), Ergebnisse zusammengeführt.

## Request Summary

Jeder der drei Python-Kanäle soll **genau einen** Punkt haben, durch den der
Netzverkehr läuft — `email.py::_dial_and_send`, `sms.py::_post`,
`telegram.py::_post` — abgesichert durch einen Struktur-Test, der jeden
weiteren `smtplib.SMTP(`/`httpx.post(` in `src/` + `api/` verbietet. Der
funktionsfähige, ungeschützte Sendeweg `src/app/core.py` fällt ersatzlos.

## Scope laut Zuschnitt

| # | Gegenstand |
|---|---|
| 1 | `email.py`: `_dial_and_send` einführen, Primärweg + **beide** Ersatzwege darauf umstellen (Entwurf liegt aus S1 vor: `docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md:124-176`) |
| 2 | `sms.py`: `_post`-Kapselung um den einen `httpx.post` |
| 3 | `telegram.py`: Guards nach `_post` ziehen; ADR-0012 + ADR-0014 unberührt |
| 4 | AST-Struktur-Test, Prüfdatum +90 Tage (**2026-10-28**) |
| 5 | `src/app/core.py` + `tests/test_core.py` ersatzlos löschen |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/channels/email.py` (695 Z.) | drei Dial-Stellen :589, :638, :682 · Guards :469-528 (Resend) / :529-567 (lokal) · `_fallback_recipients_blocked` :389-408 · **Gate #811 greift** |
| `src/output/channels/telegram.py` (584 Z.) | `_post` :267-304 (zwei `httpx.post`: :286 Primär, :304 nach Drosselung) · drei Guards :153/:174/:192 · sieben `_post`-Aufrufer |
| `src/output/channels/sms.py` (76 Z.) | ein `httpx.post` :61-66 · Guard :32-49 · Antwort-Auswertung :67-74 |
| `src/app/core.py` (23 Z.) | ungeschützter `smtplib.SMTP` + `sendmail`, Empfänger aus `os.getenv("MAIL_TO")` :10 — **löschen** |
| `tests/test_core.py` (8 Z.) | einziger Aufrufer von `core.send_mail` — **löschen** |
| `src/lib/mq_notify.py:45` | `httpx.post` an localhost, kein Endnutzer-Empfänger — **begründete Ausnahme** |
| `src/services/inbound_telegram_reader.py:397` | `httpx.post`, localhost, kein Endnutzer-Empfänger — **begründete Ausnahme** |
| `src/services/notification_service.py` | 6 SMS-Aufrufstellen (:315, :429, :703, :791, :941, :1105) · **Bubble-Schleife :351-366 mit frischer `TelegramOutput`-Instanz je Bubble :354** (ADR-0014) |

## Existing Patterns

- **Gemeinsamer Ausgang existiert bei Telegram schon** (`_post`, #1370) — aber
  ausdrücklich guard-frei (Docstring :271-283: „Bewusst KEINE Guards"). Genau
  das Muster, das #1412 ablösen will.
- **Sink am Transportrand statt isolierter Guard-Aufruf** ist die
  Nachweisform des Projekts: `tests/tdd/test_telegram_test_isolation.py:78-89`,
  `test_telegram_test_mode_guard.py:278-303`, `test_sms_test_isolation.py:94`.
  Alle patchen **global** (`httpx.post` bzw. `smtplib.SMTP`), nicht die
  Kanal-Methode — deshalb sind sie gegenüber dem Umbau blind, solange der
  Guard vor dem Netzzugriff feuert.
- **Vorbilder für den Struktur-Test:**
  - `tests/tdd/test_repo_path_hardcoding_ratchet.py` — AST + Konstanten-
    Auflösung, Ausnahme als Zeilenkommentar (`# gz-main-path: <Grund>`,
    ≥15 sinnvolle Zeichen), `EXPIRY = date(...)` als Modul-Konstante plus
    Test, dass das Datum als Text auffindbar ist (:209-218), Repo-Wurzel
    `Path(__file__).resolve().parents[2]` (:52).
  - `tests/test_mail_recipient_parity.py` — Ausnahmen-Deckel
    (`ausnahmen_hoechstzahl`, :141-145) + Frist + Begründungspflicht je
    Ausnahme; **direktestes Vorbild für die zwei geplanten Ausnahmen.**
  - `tests/test_egress_inventory_drift.py` — eigene Seite über echten Import,
    fremde Seite als Text, Zeilen am ersten `//` abschneiden.

## Dependencies

- **Upstream:** `smtplib`, `httpx`, `Settings` (`config.py`),
  `_load_resend_allowlist`/`_is_local_mail_domain`/`_is_reserved_test_domain`
  (Guard-Bausteine in `email.py`), `app.loader.get_data_root`.
- **Downstream:** `notification_service.py` (18 der 26 Versandwege),
  `radar_alert_service.py`, `channel_test_service.py`, `api/main.py`,
  `api/routers/debug.py`, `inbound_telegram_reader.py`, Sink-Pfade. **Keiner
  davon wird in S3 angefasst** — alle rufen ausschließlich die öffentlichen
  Kanal-Methoden auf.

## Existing Specs

- `docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md` — enthält
  in `:124-176` den **vollständigen `_dial_and_send`-Entwurf**, damals
  ausdrücklich „gilt für S3, nicht S1" stehengelassen.
- `docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md`,
  `fix_1412_s2b_divergenzen_aufloesen.md` — das Paritäts-Werkzeug, dessen
  Verzweigungs-Ratsche mit S3 kollidiert (s. Risiko R-A).
- `docs/specs/modules/egress_guard_telegram.md` — Spec hinter
  `test_telegram_test_isolation.py` (AC-1…AC-8).
- `docs/specs/modules/smtp_mailer.md` — **Spec für die zu löschende
  `core.py`**, Status „implemented", Stand 2025-12-27, nennt den Weg noch
  „einziger aktiver Kommunikationskanal im MVP". Muss mit ins Archiv.
- `docs/adr/0012-telegram-parse-mode-html.md` (400-HTML-Nachsendung, :51-56),
  `docs/adr/0014-telegram-multi-bubble-format.md` (Sequenz separater
  `sendMessage`-Aufrufe, :32-34) — unberührt zu halten.

---

## Befund 1 — Die drei E-Mail-Dial-Blöcke sind NICHT gleich

Zusammenziehen ohne Entscheidung ist unmöglich: zwei der Unterschiede sind
Verhalten, nicht Form.

| Merkmal | Primär :589 | Ersatz 1 :638 (4xx) | Ersatz 2 :682 (OSError) |
|---|---|---|---|
| Host | `self._host` | `self._fallback_host` | `self._fallback_host` |
| Port | `self._port` | **hart `587`** | **hart `587`** |
| Zugang | `self._user`/`_password` | `self._fallback_user`/`_pass` | dito |
| Variablenname | `server` | `fb_server` | `fb_server` |
| **Fehler bei EINEM Empfänger** | **wird protokolliert, Rest läuft weiter** (:596-601) | **reißt gesamten Versand ab** | **reißt gesamten Versand ab** |
| Erfolgs-Protokoll | nur wenn `attempt > 0`, außerhalb des `with` (:604) | unbedingt, `[SMTP-FALLBACK] sent via fallback SMTP` (:646) | wortgleich (:690) |
| Guard-Wiederholung davor | nein | `_fallback_recipients_blocked` (:636) | dito (:680) |
| Fehlertext beim Scheitern | — | `… {e.smtp_code} … (fallback also failed: …)` | `Connection error: {e} (fallback also failed: …)` |

**Die Zeile in Fettdruck ist der Kern.** Beim Sammelversand an mehrere
Empfänger fasst nur der Primärweg jeden Empfänger einzeln ein. Eine
gemeinsame Funktion muss sich für **eine** der beiden Varianten entscheiden —
jede Wahl ändert Verhalten auf einem der Wege:

- Einfassung übernehmen ⇒ Ersatzwege werden **duldsamer** (ein schwieriger
  Empfänger blockiert die anderen nicht mehr). Nutzersichtbar besser, aber
  eine Verhaltensänderung im Sicherheitspfad, die der Zuschnitt („null
  Verhaltensänderung") nicht vorsieht.
- Einfassung weglassen ⇒ Primärweg wird **strenger**: ein einzelner
  abgelehnter Empfänger nimmt allen anderen die Post weg. **Echte
  Verschlechterung, kommt nicht in Frage.**
- Beides parametrisiert erhalten ⇒ null Verhaltensänderung, dafür ein
  Schalter in der gemeinsamen Funktion, der genau die Asymmetrie
  konserviert, die man loswerden wollte.

⇒ **Muss in der Spec entschieden werden, mit PO-Freigabe.** Das ist die
einzige Stelle in S3, an der Nutzerverhalten auf dem Spiel steht.

### Kontrollfluss (gemessen)

```
:587  for attempt in range(4):
:588    try:
:589-606    DIAL PRIMÄR (self._host, self._port) → Erfolg: return :606
:608    except SMTPAuthenticationError      → raise sofort, KEIN Ersatzweg
:614    except SMTPResponseException as e
:617        smtp_code >= 500                → raise sofort, KEIN Ersatzweg
:623        nicht letzter Versuch           → sleep(backoff), weiter
:632        letzter Versuch:
:636            fallback_host gesetzt UND nicht _fallback_recipients_blocked
:638-652            ERSATZ 1 → Erfolg: return / Fehler: raise
:653            sonst                       → raise
:659    except SMTPException                → raise sofort, KEIN Ersatzweg
:663    except OSError as e
:665        nicht letzter Versuch           → sleep(backoff), weiter
:675        letzter Versuch:
:680            fallback_host gesetzt UND nicht _fallback_recipients_blocked
:682-693            ERSATZ 2 → Erfolg: return / Fehler: raise
:694            sonst                       → raise
```

Beide Ersatzwege sind ausschließlich über den **letzten** von vier Versuchen
erreichbar. Sie unterscheiden sich nur im auslösenden Fehlertyp.

## Befund 2 — Telegram: sieben Aufrufer, drei Guard-Kombinationen, zwei ohne

| Methode | Endpunkt | Guards heute | Chat-Herkunft | `chat_id=` an `_post` |
|---|---|---|---|---|
| `send` :306 | sendMessage | Token :330 + `_guard_test_mode_chat_id` :331 | `settings.telegram_chat_id` | ja |
| `_send_fallback_without_parse_mode` :386 | sendMessage | Token :395 + `_guard_test_mode_target_chat` :396 | Argument | ja |
| `delete_message` :425 | deleteMessage | Token :438 + target :439 | Argument | ja |
| `edit_message_text` :467 | editMessageText | Token :475 + target :476 | Argument | ja |
| `set_my_commands` :523 | setMyCommands | **nur Token** :530 | kein Chat | nein |
| `answer_callback_query` :500 | answerCallbackQuery | **keiner** | kein Chat | nein |
| `get_my_commands` :548 | getMyCommands | **keiner** | kein Chat | nein |

**Vier Kollisionsstellen für die Verlagerung:**

- **K1 — chat-lose Methoden.** Ein unbedingter `_guard_test_mode_target_chat`
  in `_post` bekommt für drei Methoden `chat_id=None` und blockt im
  Testbetrieb **immer** (`str(None) != test_chat_id`). Der gemeinsame Weg
  muss „kein Empfänger" von „falscher Empfänger" unterscheiden können.
- **K2 — zwei Guards prüfen dasselbe, verschieden.**
  `_guard_test_mode_chat_id` (:153) liest den Chat aus den Einstellungen,
  vergleicht **ohne** `str()`, Fehlertext trägt `#1288`.
  `_guard_test_mode_target_chat` (:192) nimmt ihn als Argument, vergleicht
  **mit** `str()`, Fehlertext trägt `#1363`. Inhaltlich dieselbe Frage.
- **K3 — der Wortlaut ist Testvertrag.** `test_telegram_test_isolation.py`
  AC-7 (:378-427) prüft den `#1288`-Wortlaut **wörtlich** für `send()`.
  Wird `send()` bei der Zusammenlegung auf den anderen Guard umgehängt,
  bricht AC-7 — zu Recht.
- **K4 — die Methodennamen sind Testvertrag.** AC-6 (:332-372) ruft
  `_guard_test_mode_bot_token()` und `_guard_test_mode_target_chat(...)`
  **direkt** als No-Op-Beweis auf. Sie dürfen nicht in den `_post`-Rumpf
  hineinverschmolzen werden.
- **K5 — `_post` hat zwei Netzzugriffe**, nicht einen (:286 Primär, :304
  nach Drosselung). Der Struktur-Test muss beide als „innerhalb" erkennen.

**ADR-Lage geprüft:** ADR-0012 (400-Nachsendung) und ADR-0014 (Multi-Bubble)
sind von einer Verlagerung **nicht** betroffen. Die Nachsende-Methode ruft
heute beide Guards ein zweites Mal auf (:395-396) — redundant, aber
harmlos; im gemeinsamen Weg entfällt die Redundanz von selbst, ohne die
Nachsende-Logik zu berühren. Multi-Bubble erzeugt je Bubble eine frische
Instanz und ruft `send()` einzeln — Guards laufen schon heute je Aufruf.

**Korrektur an der Bestandsaufnahme:** ADR-0014s Instanzerzeugung steht
**nicht** in `telegram.py:139-140` (dort nur ein veralteter Verweis-Kommentar),
sondern in `src/services/notification_service.py:354`, innerhalb der
Bubble-Schleife `:351-366`.

## Befund 3 — SMS ist der einfache Teil

`send()` :51-75: Guard :53 → Nutzlast :54-59 → **`httpx.post` :61-66** →
HTTP-Status-Prüfung :67-71 → seven.io-Textcode `"100"` :72-74 → Protokoll :75.
Die Grenze liegt hinter dem POST: alles ab :67 hängt an der Antwort. Die
Kapselung gibt die rohe Antwort zurück, die Auswertung bleibt in `send()` —
analog `telegram.py::_post`.

Kein Test bricht: `test_sms_test_isolation.py` patcht `httpx.post` global
(:94 u.a.), `test_issue_936_sms_stub.py` fährt einen echten lokalen Server.

## Befund 4 — `src/app/core.py` ist nachweislich tot

Geprüft, nicht angenommen: `send_mail` ist der einzige definierte Name.
Repo-weite Suche über `*.py`, `*.go`, `*.md`, `*.sh`, `*.ini`, `*.toml`,
`*.json` findet als Aufrufer **ausschließlich** `tests/test_core.py:7`. Keine
dynamischen Importe (`app.core`/`importlib`) — kein Treffer. Kein Gate, kein
Hook, kein CI-Prüfer hängt an der Existenz der Dateien. Die Umgebungsvariable
`MAIL_TO` (zu unterscheiden von der produktiv genutzten `GZ_MAIL_TO`) kommt
sonst nur in Doku vor, die den Weg bereits als tot beschreibt.

**Doku-Nacharbeit (Pflicht, zählt nicht auf das LoC-Budget):**
`docs/specs/modules/smtp_mailer.md` ins Archiv · Abhängigkeitszeile
`docs/specs/modules/cli.md:31` · `tests/INDEX.md:11,28`.

## Risks & Considerations

**R-A — S3 schaltet das Werkzeug aus S2a ab (verifiziert).**
`tests/test_mail_recipient_parity.py:560-576` findet die Empfängerprüfung
dadurch, dass sie eine `If`-Anweisung **unmittelbar im Rumpf von
`EmailOutput.send()`** ist (`for anweisung in methode.body` — nur oberste
Ebene, kein `ast.walk`). Wandert die Prüfung nach `_dial_and_send`, meldet
der Läufer „Region verloren, die Ratsche prüft nichts mehr" (AC-7 dort).
Die Verzweigungszahl `verzweigungen_python: 15` (`faelle.json:131`) gilt
ebenfalls für diese Region.
⇒ Entweder bleibt die Prüfung in `send()` (dann ist `_dial_and_send` reiner
Transport), oder das S2a-Werkzeug wird mitgeändert und die Zahl neu gemessen.
**Nicht beides ignorieren.**

**R-B — Die Leitfrage von S3 hängt an R-A.** Bei Telegram lautet der Auftrag
„Guards **in** den gemeinsamen Weg". Bliebe `email.py`s gemeinsamer Weg
bewusst prüfungsfrei, baute dieselbe Scheibe genau das Muster ein, das #1412
abschafft. Gegenrechnung: S1 hat empirisch belegt, dass die Prüfung vor der
Schleife **ausreicht** (der als ROT geplante Test war grün, über alle
Host×Verifikations-Kombinationen), und die Verlagerung würde die Allowlist
bis zu 4× pro Versand von der Platte lesen (S1-Spec, Known Limitations).
⇒ Entscheidung mit Begründung in die Spec; Konsistenz-Argument gegen
Kosten-Argument, nicht stillschweigend.

**R-C — `tests/test_outputs.py:117` bindet die Aufrufform.**
`mock_smtp.assert_called_once_with("smtp.example.com", 587)` — genau zwei
positionelle Angaben, keine Schlüsselwörter, kein Timeout. `_dial_and_send`
darf dem Verbindungsaufbau nichts hinzufügen.

**R-D — Gate #811.** Sobald `src/output/channels/email.py` gestaged ist,
blockiert der Commit bis (1) `tests/tdd/test_issue_811_mode_matrix.py` grün
und (2) ein frischer, erfolgreicher `briefing_mail_validator.py`-Lauf gegen
Staging vorliegt. **Reihenfolge:** erst stagen, dann Nachweise, mit
gesetzter Workflow-Kennung in der Umgebung.

**R-E — Struktur-Test darf nicht am Prüfling vorbeimessen.** Repo-Wurzel
zwingend `Path(__file__).resolve().parents[N]` relativ zur Testdatei
(Pfadregel #1409, `tests/tdd/test_repo_path_hardcoding_ratchet.py`) — sonst
prüft er aus dem Worktree die unveränderte Hauptrepo-Kopie und meldet
falsches Grün.

**R-F — Regel-Budget.** Der Struktur-Test ist ein neues Gate ⇒ Prüfdatum
**2026-10-28** (+90 Tage), maschinell als Text auffindbar. Ausnahmen mit
Deckel, Frist und Begründungspflicht nach Vorbild
`test_mail_recipient_parity.py:141-145`.

**R-G — Risiko der Scheibe insgesamt: HOCH.** Produktiver Sicherheitspfad,
alle drei Kanäle gleichzeitig, live genutzter Ersatz-Sendeweg. Staging-Nachweis
mit echtem Versand ist Pflicht; genau **ein** Versand (Kontingent, nur
Test-Trip), danach Prüfung per IMAP.

## Offene Fragen für Phase 2 (Analyse)

1. **Fehler-Einfassung je Empfänger** — welche der drei Varianten aus
   Befund 1? (Nutzersichtbar, braucht PO-Freigabe.)
2. **Prüfung im gemeinsamen Weg oder daneben** — R-A/R-B, einheitlich für
   E-Mail und Telegram begründen.
3. **Telegram-Guard-Zusammenlegung** — wie K1 (chat-lose Methoden) und K2
   (zwei Guards, eine Frage) auflösen, ohne K3/K4 zu brechen?
4. **Bekommen `answer_callback_query`/`get_my_commands` erstmals einen
   Schutz?** Beide senden heute ohne jede Prüfung mit dem Zugangsschlüssel
   los. Ein Token-Guard im gemeinsamen Weg würde sie mitschützen — richtig,
   aber eine Verhaltensänderung, die ausdrücklich zu entscheiden ist.

---

# Analysis (Phase 2)

Grundlage: strategische Bewertung (Plan/Sonnet) + zwei Lücken-Recherchen,
alle Kernaussagen vom Orchestrierer am Code nachgeprüft. Wo die Bewertung
korrigiert wurde, steht es dabei.

### Type

**Bug** (strukturell) — Issue #1412 ist als `bug` etikettiert; S3 ist die
Struktur-Scheibe daraus.

## Antwort auf Frage 1 — Fehler-Einfassung je Empfänger

**Der Sammelversand ist produktiv erreichbar** (nachgeprüft): ein
Ortsvergleich-Preset trägt eine Empfängerliste (`empfaenger`,
`scheduler_dispatch_service.py:333`, Fallback auf `mail_to` bei leer :338),
`notification_service.py:762` gibt sie als `to=recipients` weiter,
`email.py:450-454` macht daraus mehr als einen Empfänger. Kein toter Zweig.

**Neuer Fund, der die Entscheidung dreht** (`email.py:592-606`, gelesen):
Werden bei mehreren Empfängern **alle** abgelehnt, wird jede Ablehnung
einzeln protokolliert — und die Funktion kehrt danach **normal zurück**
(`return` :606). `send()` meldet Erfolg für einen Versand, der niemanden
erreicht hat. Der Hauptweg hat also nicht „das bessere" Verhalten, sondern
ein duldsames Verhalten **mit blindem Fleck**.

⇒ Die naheliegende Vereinheitlichung („Einfassung überall übernehmen")
würde diesen blinden Fleck auf die Ersatzwege ausbreiten. Sie ist damit
keine Verbesserung, sondern Verbreitung eines Defekts.

**Entscheidung (Empfehlung an den PO):** S3 bleibt **verhaltensneutral** —
die Asymmetrie wird in `_dial_and_send` als Parameter erhalten
(Primärweg fasst je Empfänger ein, Ersatzwege nicht), und zwei
Regressionstests schreiben beide Verhalten ausdrücklich als Soll fest.
Der zusammengesetzte Defekt (Ersatzweg alles-oder-nichts **plus** stiller
Erfolg bei Totalablehnung) ist als **#1426** angelegt — nutzersichtbares
Fehlverhalten, Triage-Kriterium (a), abhängig von S3a. Er ist danach klein zu beheben, weil
`_dial_and_send` dann existiert.

## Antwort auf Frage 2 — Prüfung im gemeinsamen Weg oder daneben

**Kriterium (nicht Geschmack): Zahl der unabhängigen Aufrufer.** Eine
Prüfung gehört in den geteilten Weg, wenn mehrere Aufrufer existieren, von
denen einer sie vergessen kann.

| Kanal | Aufrufer des gemeinsamen Wegs | Entscheidung |
|---|---|---|
| E-Mail | **einer** (`send()`), der bereits einmal vor der ganzen Schleife prüft | `_dial_and_send` = **reiner Transport** |
| Telegram | **sieben** | Prüfungen wandern **in** `_post` |

Begründung E-Mail: S1 hat empirisch belegt, dass die Prüfung vor der
Schleife ausreicht (der als ROT geplante Test war grün, über alle
Host×Bestätigungs-Kombinationen). Das Verschieben kostet dagegen zweierlei:
das S2a-Werkzeug müsste mitgeändert und neu vermessen werden (R-A), und die
Allowlist würde bis zu 4× pro Versand von der Platte gelesen (S1, Known
Limitations) — Kosten ohne belegten Nutzen.

Begründung Telegram: `_post` hat sieben Aufrufer und ist ausdrücklich
prüfungsfrei gehalten (`:271-283`). Der achte Aufrufer ist der, der die
Prüfung vergisst. Genau der Fall, den #1412 unbaubar machen will.

**Wichtige Trennung:** „Prüfung im gemeinsamen Weg" und „genau ein Ort, an
dem Netzverkehr entsteht" sind **zwei** Ziele. S3 liefert das zweite für
alle drei Kanäle und das erste dort, wo die Aufruferzahl es rechtfertigt.
Die strengere Form (Prüfung immer im Transport) ist Sache von S4, wo der
Empfängervertrag scharf geschaltet wird.

## Antwort auf Frage 3 — Telegram: Empfänger an der Nutzlast erkennen

**Trägt alle fünf Kollisionen.** Der gemeinsame Weg liest an der Nachricht
selbst ab, ob ein Empfänger im Spiel ist (`"chat_id" in payload`) —
verifiziert: genau die vier Methoden mit Empfänger setzen den Schlüssel
(`send` :342, Nachsendung :400, `delete_message` :442,
`edit_message_text` :485), die drei chat-losen nicht. Das ist **keine
Angabe des Aufrufers**, die man vergessen kann, sondern die Nachricht selbst.

| # | Auflösung |
|---|---|
| K1 chat-lose Methoden | `"chat_id" in payload` ist dort falsch ⇒ Chat-Prüfung läuft gar nicht, `None` blockt nichts |
| K2 zwei Guards, eine Frage | **beide Funktionen bleiben unverändert**; nur die drei Direktaufrufe wandern zentral. Gleiches Argument, gleiches Ergebnis |
| K3 `#1288`-Wortlaut ist Testvertrag | `send()` behält seinen eigenen, **vorgeschalteten** Aufruf ⇒ AC-7 bricht nicht |
| K4 Methodennamen sind Testvertrag | beide Guard-Methoden bleiben einzeln aufrufbar ⇒ AC-6 bleibt gültig |
| K5 zwei Netzzugriffe in `_post` | Prüfblock **vor** beiden (:286, :304); der Struktur-Test zählt `_post` als einen Bereich mit zwei erlaubten Zugriffen |

**Die Doppelung bei `send()` ist beweisbar harmlos, nicht bloß
wahrscheinlich:** `_guard_test_mode_chat_id` vergleicht **ohne**
Typwandlung (`chat_id != test_chat_id`), `_guard_test_mode_target_chat`
**mit** (`str(...) != str(...)`). Die ungewandelte Prüfung ist also
strenger-oder-gleich und feuert immer zuerst. Es gibt keinen Fall, in dem
die zusätzliche Prüfung in `_post` einen bisher erfolgreichen `send()`
neu blockiert. Außerhalb des Testbetriebs sind beide Prüfungen Leerläufe
(erste Zeile `if not is_test_mode: return`) — im Produktivbetrieb kostet
die Doppelung nichts.

**Muss in der Spec stehen**, damit niemand später „vereinfacht" und dabei
die Verankerung von AC-7 zerstört.

## Antwort auf Frage 4 — die zwei ungeschützten Methoden

**Ja, mitschützen.** Nachgeprüft: `answer_callback_query` hat eine echte
Produktiv-Aufrufkette (`inbound_telegram_reader.py:338` →
`notification_service.py:1215` → `telegram.py:500`). Und
`Settings.for_testing()` fällt bei fehlendem Test-Bot-Zugang still auf den
Produktions-Zugang zurück (`config.py:255,269`) — genau die Lücke, die
#1363 für die anderen vier Methoden geschlossen hat, bliebe hier offen:
eine unvollständig eingerichtete Testumgebung spräche stillschweigend mit
dem Produktions-Bot. `get_my_commands` hat keinen Produktiv-Aufrufer, wird
aus Konsistenz mitgenommen.

**Kosten: null zusätzliche Zeilen** — fällt aus der Zentralisierung des
Token-Guards in `_post` ab. Kein Test bricht: die Tests, die diese Methoden
aufrufen (`test_issue_671_bot_menu_autoset.py`,
`test_issue_650_telegram_foundation.py`), setzen den Testbetrieb nicht,
die Prüfung ist dort ein Leerlauf.

## Antwort auf die Umgehungsfläche des Struktur-Tests

Drei Löcher im geplanten Zuschnitt, alle heute mit **null** Vorkommen und
daher ohne Ausnahmeliste schließbar:

1. `src/app/core.py:20` — echter Versand mit echtem Empfänger außerhalb der
   drei Funktionen. **Wird in dieser Scheibe gelöscht** ⇒ passt zusammen.
2. `smtplib.SMTP_SSL(` / `smtplib.LMTP(` — von einer Suche nach
   `smtplib.SMTP(` nicht erfasst.
3. `httpx.Client(...).post(` / `.request(` / `.send(` — von einer Suche nach
   `httpx.post(` nicht erfasst. `src/app/egress_guard.py:5-9,72-73,148-149`
   greift die echten Transport-Grundfunktionen ab
   (`httpx.HTTPTransport.handle_request`, `smtplib.SMTP.connect`) und zeigt
   damit, welche Formen es real gibt.

**Bewusst NICHT erweitert auf `httpx.get(`:** Daten werden per GET geholt
(20+ Provider-Dateien, Gruppe (b) der Lückenprüfung), gesendet wird
ausschließlich per POST. Ein weiter gefasster Test würde die Provider
einsammeln und bräuchte eine Ausnahmeliste in Dutzendgröße — das wäre ein
Gate, das sich selbst erodiert.

**Ausnahmen bleiben bei zwei:** `src/lib/mq_notify.py:45` (localhost:3457,
prozessintern), `src/services/inbound_telegram_reader.py:397`
(localhost:8090, kein Endnutzer-Empfänger).
Separat zu benennen, weil in keine der drei Gruppen passend:
`api/routers/scheduler.py:164` (Heartbeat-Ping an BetterStack) — kein
Endnutzer-Empfänger, aber auch kein Datenabruf. Nutzt `httpx.post`?
**In Phase 3 prüfen** und entweder als dritte Ausnahme aufnehmen oder
belegen, dass es GET ist.

## Affected Files

| Datei | Änderung | Scheibe |
|---|---|---|
| `src/output/channels/email.py` | MODIFY — `_dial_and_send` extrahieren, drei Aufrufstellen, Einfass-Parameter | S3a |
| `src/app/core.py` | DELETE | S3a |
| `tests/test_core.py` | DELETE | S3a |
| `tests/tdd/test_egress_single_dial_point.py` | CREATE — Struktur-Test, `smtplib`-Teil | S3a |
| `docs/specs/modules/smtp_mailer.md` | MOVE → `_archive/` | S3a |
| `docs/specs/modules/cli.md` | MODIFY — Abhängigkeitszeile :31 | S3a |
| `tests/INDEX.md` | MODIFY — Zeilen :11, :28 | S3a |
| `src/output/channels/telegram.py` | MODIFY — Prüfungen nach `_post`, Nutzlast-Erkennung | S3b |
| `src/output/channels/sms.py` | MODIFY — `_post`-Kapselung | S3b |
| `tests/tdd/test_egress_single_dial_point.py` | MODIFY — `httpx`-Teil ergänzen | S3b |

## Scope Assessment

| | Dateien (Code) | LoC (added+deleted) | Gate #811 | Risiko |
|---|---|---|---|---|
| **S3a** E-Mail + Löschung + Struktur-Test | 4 | ~221 | **ja** | HOCH |
| **S3b** Telegram + SMS + Test-Erweiterung | 3 | ~111 | nein | MITTEL |
| ungeteilt | 7 | **~332** | ja | HOCH |

Ungeteilt reißt das Limit von 250 und bräuchte eine PO-Ausnahme. Geteilt
bleiben beide unter dem Limit, und der teure Staging-Mailversand fällt nur
für S3a an.

## PO-Entscheidungen 2026-07-30

1. **S3 bleibt verhaltensneutral.** Die Ersatzweg-Schwäche wird nicht
   mitgenommen; sie ist als **#1426** angelegt (abhängig von S3a).
2. **Zwei Scheiben:** **S3a** (E-Mail + Löschung + Struktur-Test,
   Gate #811) und **S3b** (Telegram + SMS + Test-Erweiterung). Kein
   LoC-Override nötig.

**Dieser Workflow liefert S3a.** S3b bekommt einen eigenen Workflow.
