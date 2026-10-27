# Context: fix-2168-antwort-an-den-fragenden

**Issue:** #2168 — Antwort an unbekannte Absender geht an den Betreiber statt an den Fragenden
**Herkunft:** herausgelöst aus #2126 (Scheibe S3 von Epic #2133)
**Erstellt:** 2026-09-07 · **Track:** Bug
**Basis:** `origin/main` @ `c7949887`

## Analysis

### Type

**Bug.**

### Request Summary

Schreibt jemand dem Telegram-Bot von einer Chat-ID, die keinem Nutzerprofil zugeordnet ist,
geht der Registrierungshinweis an die Chat-ID des **Basis-/Betreiberprofils** statt an den
Fragenden. Der Fragende bekommt nichts, der Betreiber bekommt es bei jeder fremden Nachricht
erneut — zugleich ein Flut-Vektor gegen den Betreiber-Chat.

### Ist-Stand — die Bestandserhebung hat den Ticket-Umfang auf ein Drittel reduziert

Das Issue nannte **drei** Fundstellen. Nachgemessen hält **eine** stand.

| Ticket-Fundstelle | Befund |
|---|---|
| Telegram `_process_update`, Zweig `user_id == "default"` (`inbound_telegram_reader.py:181-191`) | ✅ **Defekt bestätigt** |
| Telegram-Callback (`inbound_telegram_reader.py:305-317`) | ❌ **widerlegt** — korrekt |
| E-Mail (`inbound_email_reader.py:106,121-132`) | ❌ **widerlegt** — unerreichbar |
| SMS / Premium-SMS | ❌ kein Antwort-Rückkanal vorhanden |

#### A) Der bestätigte Defekt — genau eine Zeile

```
inbound_telegram_reader.py:182-191   send_telegram_message(chat_id=chat_id, …, settings=settings)
                                                                                        ^^^^^^^^
                                                        Basis-Settings statt der Absender-Adresse
  notification_service.py:1828-1845  send_telegram_message(...)  ← chat_id NUR im Fehler-Log (:1844)
    telegram.py:379-403              TelegramOutput.send(...)    ← kein Chat-Parameter
      :403                           chat_id = self._guard_code_origin(self._settings.telegram_chat_id)
```

Der Aufruf übergibt die richtige `chat_id` — sie wird nur nirgends **verwendet**. Die
tatsächlich gesendete Adresse ist `settings.telegram_chat_id`.

#### B) Nur der `default`-Zweig weicht ab — alle anderen sechs Aufrufer sind korrekt

| Aufrufer in `inbound_telegram_reader.py` | übergebene `settings` | Adresse == Absender? |
|---|---|---|
| `:182-191` Registrierungshinweis (`user_id=="default"`) | `settings` (Basis) | **NEIN — der Defekt** |
| `:203-208` kein aktiver Trip | `user_settings` | ja |
| `:217-224` unbekannter Befehl | `user_settings` | ja |
| `:241-246` Lade-Nachricht | `user_settings` | ja |
| `:268-272` / `:277-281` `send_command_reply_telegram` | `user_settings` | ja |
| `:437-442` `_process_start_command` | `settings.model_copy(update={"telegram_chat_id": chat_id})` | ja — **Muster-Beleg** |

Warum die sechs strukturell stimmen: `_resolve_user_for_chat` (`:406-423`) findet den `user_id`
per `lookup_user_by_telegram_chat_id` (`app/loader.py:1244-1265`) **exakt über den Treffer auf
`profile["telegram_chat_id"] == chat_id`**, und `with_user_profile` (`app/config.py:387-388`)
übernimmt diesen Wert 1:1. Bei jedem Treffer ist `user_settings.telegram_chat_id == chat_id`
per Konstruktion. Nur `with_user_profile("default")` fällt mangels
`data/users/default/user.json` unverändert auf die Basis zurück (`config.py:376-377`) — genau
die Adresse des Betreibers.

**Leere/ungültige `chat_id`?** Ausgeschlossen: `:166` filtert vorher (`if not text or not
chat_id: return False`), `:165` liefert immer einen gestringten Telegram-Integer.

#### C) Warum der Callback-Pfad korrekt ist

`edit_telegram_message_text` (`notification_service.py:1859-1864`) reicht `chat_id` an
`TelegramOutput.edit_message_text(chat_id, …)` durch, und die Methode setzt sie in den Payload
(`telegram.py:550,561`). Der Button-Klick eines unbekannten Chats wird in **seinem** Chat
editiert. Die Nachbarfunktion sah nur gleich aus.

#### D) Warum der E-Mail-Pfad unerreichbar ist

`_authorize` (`inbound_email_reader.py:188-202`) läuft in `_process_single` **vor** dem
Trip-Lookup (`:107-109`) und lässt nur Absender durch, die `mail_to` oder `inbound_address` des
aufgelösten Profils sind. Für `user_id == "default"` ist das die Betreiber-Adresse; ein Fremder
wird auf `\Seen` gesetzt und verworfen — es geht **gar keine** Antwort raus, an niemanden.

Gegenprobe auf einen Umgehungsweg: kein zweiter Einlass. Die einzige Instanziierung von
`InboundEmailReader` außerhalb von Tests ist `api/routers/scheduler.py:130,138`
(`POST /api/scheduler/inbound-commands`) → `poll_and_process` → `_process_single` → `_authorize`.

#### E) Missbrauchsfrage aus „Zu klären vor der Umsetzung" — entschieden

Die Telegram-Bot-API erlaubt `sendMessage` nur an Chats, die den Bot selbst angeschrieben
haben. Eine Antwort an den Fragenden kann also **nicht** genutzt werden, um unbeteiligte Dritte
zu belästigen. Der heutige Zustand ist der riskantere: er lenkt jede fremde Nachricht in den
Betreiber-Chat um. Für E-Mail (Absender fälschbar, echter Verstärker-Vektor) stellt sich die
Frage nicht, weil dort ohnehin nicht geantwortet wird. **Entscheidung: antworten, wie heute
beabsichtigt — nur an die richtige Adresse.**

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_telegram_reader.py` | MODIFY | `:190` — `settings=settings` → `settings.model_copy(update={"telegram_chat_id": chat_id})`, spiegelbildlich zu `:436` |
| `tests/tdd/test_antwort_an_den_fragenden.py` | CREATE | Kern-Tests AC-1/AC-3/AC-4 (Telegram) |
| `tests/tdd/test_unbekannter_absender_bleibt_unbeantwortet.py` | CREATE | Kern-Test AC-2 (E-Mail-Schweigen + Positivkontrolle) |

**Ausdrücklich NICHT anzufassen:** `notification_service.py:1809-1845` (keine Signaturänderung
nötig), `telegram.py:162-252` (Wächter bleiben unverändert), `inbound_email_reader.py`
Produktivcode (kein Defekt — nur Testlücke), `inbound_telegram_reader.py:305-317` (korrekt).

### Scope Assessment

- Files: **3** (1 MODIFY, 2 CREATE)
- Estimated LoC: Produktivcode **+2/-1**, Tests **+100…170** → unter dem Limit von 250
- Risk Level: **LOW**

### Technical Approach

**Gewählt: `settings.model_copy(update={"telegram_chat_id": chat_id})` am Aufrufort.**

Begründung gegenüber der Alternative (neuer `chat_id`-Parameter an `TelegramOutput.send()`):
Die drei Telegram-Wächter `_guard_code_origin` (`telegram.py:162-195`),
`_guard_test_mode_chat_id` (`:197-216`) und `_guard_test_mode_target_chat` (`:236-252`) hängen
an `settings.telegram_chat_id`. Setzt der Fix genau diese Größe, greifen alle drei unverändert,
weil sie dann die **tatsächlich verwendete** Adresse messen. Ein zusätzlicher Parameter würde
`_guard_test_mode_chat_id` an der falschen Größe messen lassen — der Wächter würde still zum
Stellvertreter. Zudem existiert das Muster bereits im selben Modul (`:436`), es wird an einer
Stelle nur nicht angewendet.

### Nachweisform — die Messstelle ist erzwungen, nicht frei gewählt

**Am Draht (`httpx.post`-Payload) ist der Empfänger nicht messbar.** `_guard_code_origin`
(`telegram.py:162-195`) hängt nicht an `is_test_mode`, sondern an der **Herkunft des Codes**
(`app/origin_guard.py:30-41`, exakter Pfadvergleich gegen die Prod-/Staging-Wurzel). Aus jedem
Worktree — also in jedem Testlauf — schaltet er die Ziel-Chat-ID auf `telegram_test_chat_id`
um oder bricht hart ab. Ein Payload-Test sähe immer nur die Test-Chat-ID und wäre ein blinder
Wächter.

**Die höchste erreichbare Messstelle ist damit die Konstruktor-Naht von `TelegramOutput`** —
dort liegt die Adresse fest, die `send()` benutzen wird. Muster im Bestand:
`Kanalmitschrift` / `_aufzeichner_installieren`
(`tests/tdd/test_kanaltreue_adhoc_antwort.py:115-192`, konkret `:178`) ersetzt
`notification_service.TelegramOutput` durch eine echte Klasse, die
`settings.telegram_chat_id` in `__init__` mitschneidet. `Mock()`-frei, wiederverwendbar.

**Korrektur einer naheliegenden Falle:** Ein Test, der am Notifier nur das **`chat_id`-Argument**
abgreift (Muster `_MitschnittNotifier`,
`tests/tdd/test_kommandoliste_einzelquelle.py:234-247`), wäre **heute schon grün** — dieses
Argument wird bereits korrekt übergeben, es wird nur nicht verwendet. Gemessen werden muss die
**verwendete Adresse**, nicht das ignorierte Argument. Der Notifier-Aufzeichner darf nur als
Einstiegs-Blaupause dienen (`:250-272` zeigt den Aufruf über
`reader._process_update(update, settings)` mit gesetztem `reader._notification_service`), nicht
als Messgröße.

**Einstieg für alle Telegram-ACs:** `InboundTelegramReader._process_update(update, settings)` mit
einer **nicht** registrierten `chat_id`. Der Einstieg über `TripCommandProcessor().process(...)`
(wie `test_kanaltreue_adhoc_antwort.py:255-261`) erreicht den `default`-Zweig **nicht** — er
überspringt den Reader.

### Dependencies

- `app/config.py` — `with_user_profile` (`:355-399`), `telegram_chat_id` (`:207`, reines `str`
  ohne Validator), `is_test_mode` (`:167,328,344`)
- `app/loader.py:1244-1265` — `lookup_user_by_telegram_chat_id`
- `output/channels/telegram.py:162-252` — die drei Wächter (bleiben unverändert)
- `app/origin_guard.py:30-41` — Herkunftssperre, bestimmt die Messstelle

### Vorgeschlagene Acceptance Criteria (Freigabe in `/30-write-spec`)

- **AC-1:** Given eine Telegram-Nachricht von einer Chat-ID, die keinem Nutzerprofil zugeordnet
  ist / When das System mit dem Registrierungshinweis antwortet / Then ist die zum Versand
  verwendete Adresse **genau diese** Chat-ID und nicht die des Basis-/Betreiberprofils.
- **AC-2:** Given eine E-Mail von einem Absender ohne Nutzerprofil / When der Reader sie
  verarbeitet / Then wird **überhaupt keine** Antwort versendet — weder an ihn noch an den
  Betreiber; und dieselbe Testanordnung sendet bei einem bekannten Absender sehr wohl
  (Positivkontrolle, sonst belegt das Ausbleiben nur einen kaputten Testaufbau).
- **AC-3:** Given ein erkannter Nutzer / When er einen Befehl schickt / Then bleibt das
  Verhalten unverändert — die verwendete Adresse ist seine Profil-Adresse.
- **AC-4:** Given die Zusicherung aus AC-1 / When die Adress-Auflösung im Produktivcode wieder
  auf die Basis-Adresse zurückfällt / Then wird mindestens ein Test rot
  (Mutations-Gegenprobe).

### Open Questions

- [x] Soll auf Nachrichten unbekannter Absender überhaupt geantwortet werden? → **Ja**, siehe
  Abschnitt E. Kein Verstärker-Risiko bei Telegram; der heutige Zustand ist der riskantere.
- [x] Scope auf Telegram eingrenzen? → **Ja.** E-Mail und SMS haben keinen wirksamen Defekt;
  E-Mail bekommt nur den fehlenden Wächter (AC-2).
- [ ] **Bewusst zu entscheidender Randfall (in der Spec festzuhalten):** Trägt die
  Basis-`settings` bereits `is_test_mode=True` (Staging), prüft
  `_guard_test_mode_chat_id` (`telegram.py:206-216`) die neu gesetzte echte Absender-Chat-ID
  gegen `telegram_test_chat_id` und wirft `OutputConfigError`. Das `try/except` in
  `send_telegram_message` (`notification_service.py:1838-1845`) fängt sie — der Hinweis geht
  dann an **niemanden** statt an den Betreiber. Bewertung: **gewünschtes Fail-Closed**; Staging
  darf keine echten Fremden anschreiben. Heute deckt kein Test diese Kombination ab.

### Nebenbefund (nicht Teil dieses Zuschnitts)

`user_id == "default"` dient als reiner String-Sentinel für „kein Profil-Treffer"
(`inbound_telegram_reader.py:181`, `:305`, `:422`). Ein *echter* Nutzer mit `user_id ==
"default"` würde fälschlich in diesen Zweig fallen; kein Code-Invariant verbietet das, der
Docstring `:178-180` schließt es nur über die Datenlage aus. → Kandidat für die Sammelstelle
#1199.
