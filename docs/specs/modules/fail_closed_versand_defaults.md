---
entity_id: fail_closed_versand_defaults
type: module
created: 2026-10-05
updated: 2026-10-05
status: approved
version: "1.0"
tags: [bug, versand-zuverlaessigkeit, fail-closed, premium-sms, briefing-slots, epic-2505]
---

# Fail-closed-Defaults im Versandpfad (Issue #2231)

## Approval

- [x] Approved (PO, 2026-10-05: „approved“)

## Purpose

Drei Stellen im Versandpfad behandeln einen ungültigen oder unbekannten Zustand
so, als sei alles in Ordnung — und geben damit den Versand frei. Sollverhalten
(PO, 2026-10-05): **Jeder ungültige oder unbekannte Zustand sperrt den Versand
und protokolliert das**, statt ihn freizugeben. Teil von Epic #2505
(Versand-Zuverlässigkeit).

## Source

- **File:** `src/output/channels/premium_sms.py` · **Identifier:** `PremiumSmsOutput._resolve_recipient`
- **File:** `internal/model/premium_sms.go` · **Identifier:** `DerivePremiumSmsReplyState` (Go-Pendant derselben Frist, s. Befund 1b)
- **File:** `src/services/trip_report_scheduler.py` · **Identifier:** `TripReportScheduler._dispatch_due_item`
- **File:** `src/services/briefing_slots.py` · **Identifier:** `BriefingSlotStore._load` / `_update` / Leser

## Befunde (Ist-Zustand)

1. **C4-20 — Premium-SMS-Rückadresse mit Zeitstempel in der Zukunft.**
   `age = now - reply_at`; geblockt wird nur `age > 30 Tage`. Liegt `reply_at`
   in der Zukunft (Uhrfehler, kaputte/manipulierte `user.json`), ist `age`
   negativ und die Verfallsfrist greift **nie** — die Adresse gälte unbegrenzt
   als frisch. Garmin kann die Nummer inzwischen einem fremden Gerät zugeteilt
   haben ⇒ Wetter-SMS an Fremde.
   - **1b (Go-Pendant, gleicher Fehler):** `DerivePremiumSmsReplyState` meldet
     für einen Zukunfts-Zeitstempel `fresh`. Das wirkt an zwei Stellen: die
     Oberfläche zeigt „verbunden", obwohl der Python-Sendepfad nach dem Fix
     blockt (Anzeige ≠ Verhalten), und `resolvePremiumSmsTarget` bestätigt
     eingehende Nachrichten **ohne Code** für einen „frischen" Treffer. Der
     Go-Kommentar dort verlangt ausdrücklich „dieselbe Frist-Semantik wie im
     Sendepfad und in der Oberfläche" — deshalb gehört die Go-Zeile in diesen Fix.
2. **C4-31 — Unbekannter Versand-Ausgang gibt den Slot wieder frei.**
   `_dispatch_due_item` vermerkt den Ausgang nur für die vier bekannten Werte
   (`sent`, `no_stage`, `no_weather`, `no_channels`); **jeder andere** Wert
   landet im `else: store.release(...)`. Ein künftiger oder fehlerhafter
   Ausgang öffnet damit den Slot erneut ⇒ im 3-Stunden-Nachholfenster bis zu
   drei Versände an alle Kanäle, Premium-SMS inklusive. Beabsichtigter
   Nachholfall ist allein `channels_unreachable`.
3. **C4-32 — Beschädigte `briefing_slots.json` hebt den Doppelversand-Schutz auf.**
   `_load()` schluckt `JSONDecodeError`/`OSError` (und Nicht-Objekt-Inhalt)
   und liefert `{}`. Folgen: (a) alle Slots gelten als „offen" ⇒ jeder bereits
   versendete Slot des Tages geht im Nachholfenster erneut raus; die
   Log-Ableitung aus `briefing_log.json` springt nicht ein, weil die Datei ja
   existiert; (b) der nächste Schreibvorgang (`reserve`) **überschreibt** die
   beschädigte Datei mit einem fast leeren Stand — die übrigen Vermerke sind
   verloren.

## Estimated Scope

- **LoC:** ~60 Produktivcode (Python ~50, Go ~3) + Tests
- **Files:** 4 Produktivdateien, 3 Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ChannelBlockedError` / `BLOCK_REASON_REPLY_ADDRESS_STALE` | Python | vorhandener, nutzersichtbarer Sperrgrund („Rückadresse veraltet") |
| `PremiumSmsStateStale` | Go | vorhandener Zustand, Oberfläche fordert bereits zum Neu-Melden auf |
| `VERMERK_AUSGAENGE` | Python | Menge der den Slot abschließenden Ausgänge (#1725) |

## Implementation Details

```
# 1 — premium_sms.py, _resolve_recipient
age = _now() - _as_aware(reply_at)
if age < timedelta(0):
    raise ChannelBlockedError(name, "Zeitstempel der Rückadresse liegt in der
        Zukunft (<reply_at>) — ungültig, Versand abgebrochen …",
        reason_code=BLOCK_REASON_REPLY_ADDRESS_STALE)   # kein neuer Code:
        # Nutzerhandlung ist dieselbe (Gerät neu melden), Mail-Hinweis und
        # Frontend kennen den Code bereits
if age > PREMIUM_SMS_REPLY_TTL: ... (unverändert)

# 1b — premium_sms.go, DerivePremiumSmsReplyState
if age < 0 || age > PremiumSmsReplyTTL { return PremiumSmsStateStale }

# 2 — trip_report_scheduler.py, _dispatch_due_item
if outcome in VERMERK_AUSGAENGE:
    store.record_outcome(..., outcome)
elif outcome == "channels_unreachable":
    store.release(...)
else:
    logger.error("Unbekannter Versand-Ausgang %r … — Slot gesperrt, kein Nachholversand")
    store.record_outcome(..., outcome if isinstance(outcome, str) and outcome else "unknown")

# 3 — briefing_slots.py
_load(): unlesbar (JSONDecodeError/OSError/kein Objekt) ⇒ Sentinel „unlesbar"
         + logger.error (Pfad, Grund), NICHT {}
Leser  is_recorded / is_recorded_or_claimed: unlesbar ⇒ True (Slot gilt als
         abgeschlossen ⇒ kein Versand; Alarm-Sperre #1594 hält NICHT —
         Alarme gehen weiter raus, sie sind dann der einzige Infoweg)
_update(): unlesbar ⇒ nichts schreiben, False zurück
         ⇒ reserve() == False ⇒ kein Versandversuch; die beschädigte Datei
         bleibt byte-identisch liegen (Beweismittel, kein Überschreiben)
```

## Expected Behavior

- **Input:** ungültiger/unbekannter Zustand an einer der drei Stellen
- **Output:** kein Versand über den betroffenen Weg
- **Side effects:** je eine Protokollzeile auf ERROR- (2, 3) bzw. Sperrgrund im
  Versandprotokoll (1); beschädigte Datei bleibt unverändert erhalten

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat Premium-SMS aktiv und seine gelernte Rückadresse trägt einen Zeitstempel in der Zukunft / When ein Briefing oder Alarm über Premium-SMS versendet werden soll / Then geht keine Premium-SMS raus, der Kanal meldet den Sperrgrund `premium_sms_reply_address_stale` mit einem Text, der den Zukunfts-Zeitstempel als Ursache nennt — die übrigen Kanäle werden davon nicht berührt.
  - Test: echter `PremiumSmsOutput` mit Settings `reply_at = jetzt + 1 Tag` → `ChannelBlockedError` mit Reason-Code, kein HTTP-Aufruf an das Gateway; Gegenprobe `reply_at = jetzt − 1 Tag` sendet weiter.

- **AC-2:** Given dieselbe Rückadresse mit Zukunfts-Zeitstempel / When die Go-API den Premium-SMS-Zustand ableitet (Oberfläche, Inbound-Zuordnung ohne Code) / Then lautet der Zustand `stale` statt `fresh` — die Oberfläche zeigt also nicht „verbunden", und eine eingehende Nachricht wird ohne Code nicht diesem Nutzer zugeordnet.
  - Test: Go-Unit-Test `DerivePremiumSmsReplyState` mit `now + 24h` → `stale`; Grenzfälle `now − 1h` → `fresh`, `now − 31d` → `stale`.

- **AC-3:** Given ein fälliges Trip-Briefing, dessen Versandversuch einen Ausgang liefert, der weder zu den vier abschließenden Ausgängen noch zu `channels_unreachable` gehört / When der Scheduler den Slot verarbeitet und im Nachholfenster erneut läuft / Then bleibt der Slot gesperrt — es gibt keinen zweiten Versandversuch für diesen Slot und Tag, und eine ERROR-Protokollzeile nennt den unbekannten Ausgang.
  - Test: echter `BriefingSlotStore` in `tmp_path`; Versandschritt liefert `"weird_new_outcome"` → danach `is_recorded` = True, zweiter `_dispatch_due_item`-Aufruf löst keinen Versand aus; Log enthält den Ausgang.

- **AC-4:** Given ein Versandversuch mit Ausgang `channels_unreachable` / When der Scheduler den Slot verarbeitet / Then wird der Slot wie bisher freigegeben und im Nachholfenster erneut versucht (Regressionsschutz für den einzigen beabsichtigten Nachholfall).
  - Test: Ausgang `channels_unreachable` → `is_recorded` = False, Folgeaufruf versucht erneut.

- **AC-5:** Given die `briefing_slots.json` eines Nutzers ist beschädigt (kein gültiges JSON oder kein Objekt) / When der Scheduler einen fälligen Slot prüft und reservieren will / Then findet kein Versand statt, eine ERROR-Protokollzeile nennt die Datei, und die beschädigte Datei bleibt byte-identisch erhalten (wird nicht überschrieben).
  - Test: Datei mit Inhalt `{"entries": [` bzw. `[]` → `is_recorded_or_claimed` = True, `reserve` = False, `is_recorded` = True; Dateiinhalt vorher == nachher; `record_outcome`/`release` schreiben ebenfalls nicht.

- **AC-6:** Given zwei Nutzer, bei Nutzer A ist `briefing_slots.json` beschädigt, bei Nutzer B intakt / When für beide ein Slot fällig ist / Then wird nur A gesperrt; B reserviert und versendet normal (Mandantentrennung, die Sperre greift nicht über Nutzergrenzen).
  - Test: zwei `BriefingSlotStore`-Instanzen mit getrennten Verzeichnissen; A `reserve` = False, B `reserve` = True.

## Known Limitations

- **Beschädigte `briefing_slots.json` sperrt alle regulären Briefings dieses
  Nutzers, bis die Datei repariert oder entfernt ist** — bewusst, gemäß
  Sollverhalten „sperren statt freigeben". Sichtbar ist das nur über die
  ERROR-Zeile im Log; Alarme laufen weiter (die Alarm-Sperre #1594 gibt frei,
  weil der Slot als abgeschlossen gilt). Eine nutzer- oder monitoring-sichtbare
  Meldung („Briefing gesperrt: Vermerkdatei beschädigt") wäre ein eigenes
  Folge-Ticket unter #2505 — nicht Teil dieses Fixes.
- Kein Toleranzfenster für Uhrabweichung bei AC-1/AC-2: Go schreibt und Python
  liest auf demselben Host mit derselben Uhr; jede Zukunft ist damit ein
  ungültiger Zustand.
- Der Zukunfts-Fall bekommt keinen eigenen Reason-Code (Nutzerhandlung ist
  identisch: Gerät neu melden). Der Unterschied steht im Sperrtext.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer Grundsatz — die Speicher (#1725/#1897) und der
  Premium-SMS-Kanal (#1676) sind bereits als fail-closed spezifiziert; dieser
  Fix schließt drei Lücken in genau dieser Linie.

## Changelog

- 2026-10-05: Initial spec created (Issue #2231)
- 2026-10-05: ACs vom PO freigegeben
- 2026-10-06: AC-5 (Dauersperre bei beschädigter `briefing_slots.json`) abgelöst durch `docs/specs/modules/fix_2231_slot_reparatur.md` — automatische, verlustfreie Reparatur statt Sperre (PO-Entscheid „Reparatur nachliefern“)
