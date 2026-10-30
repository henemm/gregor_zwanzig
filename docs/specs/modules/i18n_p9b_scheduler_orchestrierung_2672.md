---
entity_id: i18n_p9b_scheduler_orchestrierung_2672
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2672, python, model-haiku]
---

# i18n P9b: Scheduler- und Alarm-Orchestrierung zweisprachig (Sprache einmal je Nutzer auflösen und durchreichen)

**Issue:** #2672 · **Epic:** #2644 · **Modell:** Haiku (große Dateien: bei zweitem Fehlversuch Sonnet) · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 1, 4, 7

## Approval

- [ ] Approved

## Purpose

Der Scheduler ist der Ort, an dem aus „fällig“ eine Nachricht wird: Er kennt den Nutzer, ruft Wetter ab und löst Renderer und Kanäle aus. Dieses Paket lässt ihn die Sprache des Nutzers **einmal je Nutzer** lesen und an alle Renderer (P2 bis P8) und den Versand (P9a) weiterreichen; so sprechen Trip-Briefing, Ortsvergleich, Alarme, Ausfall-Meldung und Nachlieferungs-Hinweise bei einem englischen Nutzer Englisch, bei einem deutschen Nutzer im selben Lauf weiter Deutsch. Eigene Nutzertexte des Schedulers (Nachlieferungs-Präfixe, Teilausfall-Hinweis, Ortsvergleich-Betreff, Nachtrag-Bezug) werden zweisprachig. Deutsch bleibt byte-gleich.

## Source

- **File:** `src/services/trip_report_scheduler.py`, `src/services/trip_alert.py`, `src/services/scheduler_dispatch_service.py`, `src/services/compare_alert.py`, `src/services/compare_radar_alert.py`, `src/services/compare_official_alert.py`, `src/services/compare_preview_service.py`
- **Identifier:** `TripReportSchedulerService.__init__` (trip_report_scheduler.py:681), Nachlieferungs-Präfixe (1031-1043), Teilausfall-Hinweis `partial_outage_hint` (1805-1808), Anfrage-Bau `TripReportRequest(...)` (2238), Gewitter-Satz der Etappen-Vorschau (3318-3370, 3600-3620), `TripAlertService.__init__` (trip_alert.py:536), Cooldown-Anzeige (2664-2668), Wochentag `onset_weekday` (2704-2733), Nachtrag-Bezug `_bezug` (2871-2880), `send_one_compare_preset` (scheduler_dispatch_service.py:460), `build_compare_preset_subject` (401)

> **Schicht-Hinweis:** Reiner Python-Core (`src/services/`). Kein Go-, kein Frontend-Code. Der Cron-Takt kommt aus Go (`POST /api/scheduler/*`); der Python-Core entscheidet die Fälligkeit und versendet. Die Nutzersprache liegt in `data/users/<id>/user.json` (`language`) und wird nur über `resolve_user_lang(user_id)` gelesen.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Flächen laufen durch denselben Mechanismus (Sprache je Dienstobjekt/Aufruf, `NotificationService`, geteilte Texte `versand.*`/`alarm.*`). Es entsteht kein Compare-Pendant; die Compare-Dienste (`compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py`) reichen nur durch.
> - **Mandantentrennung:** Zentral für dieses Paket. `user_id` kommt aus dem Auth-Kontext bzw. aus der Iteration über die Nutzer des Cron-Laufs (nie `"default"`); jede Dienstinstanz trägt die Sprache **ihres** Nutzers als Attribut. Es gibt keinen Modul- oder Prozess-Zustand. AC-1 und AC-2 beweisen das mit **zwei verschiedenen Nutzern (`de`/`en`) im selben Lauf**.
> - **Kanäle:** Briefing- und Alarm-Inhalt. Alle vier: E-Mail, Telegram, SMS, Premium-SMS bekommen `lang` über `NotificationService` (P9a) und die Renderer-Aufrufe; AC-3 prüft die Ausfall-Meldung auf **allen** konfigurierten Kanälen (#1701, ADR-0095).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/services/trip_report_scheduler.py` | MODIFY | `self._lang = resolve_user_lang(user_id)` im Konstruktor (einmal je Nutzer); `NotificationService(self._settings, user_id, lang=self._lang)` (Zeile 690); `lang=self._lang` in `TripReportRequest(...)` (2238) und an alle Renderer-/Formatter-Aufrufe; Präfixe 1031-1043 und Teilausfall-Hinweis 1805-1808 über Katalog; Gewitter-Satz (3318-3370, 3600-3620) mit `lang`; Operator-Meldung Zeile 509 (`... beim Laden uebersprungen`) bleibt deutsch mit `# i18n-log` |
| `src/services/trip_alert.py` | MODIFY | `self._lang = resolve_user_lang(user_id)` im Konstruktor (Zeile 536-560); `NotificationService(..., lang=self._lang)` (557); Cooldown-Anzeige (2664-2668) über `tn("alarm.dauer.stunden"/"alarm.dauer.minuten", ..., lang)`; `_de_weekday_short` (2704, 2733) durch `fmt_weekday(..., self._lang)`; Nachtrag-Bezug (2871-2880) über `alarm.nachtrag.*`; `lang=self._lang` an `to_alert_message`, `build_onset_alert_message` und die Alarm-Versandaufrufe; Log-Zeilen mit Umlaut erhalten `# i18n-log` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `send_one_compare_preset`: `lang = resolve_user_lang(user_id)` einmal am Eintritt (Zeile ~533); `lang=lang` an `render_compare_email` (648), `render_compare_sms` (720), `render_compare_telegram` (727), `build_compare_preset_subject` (401), `NotificationService(settings, user_id, lang=lang)` (733) |
| `src/services/compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` | MODIFY | nur Durchreichen: `lang = resolve_user_lang(self._user_id)` je Dienstobjekt bzw. je Lauf-Nutzer; `lang` an Projektion, Renderer und `NotificationService` (P5/P6/P9a-Signaturen); Log-Zeilen mit Umlaut erhalten `# i18n-log` |
| `src/services/compare_preview_service.py` | MODIFY | nur Durchreichen: Vorschau-Aufrufe der Compare-Renderer (Zeilen ~59-152) bekommen `lang` aus dem Aufruf (die Vorschau-API liefert `user_id` aus dem Auth-Kontext) |
| `src/services/first_briefing.py`, `briefing_slots.py`, `compare_slot_scheduler.py`, `dispatch_orchestrator.py` | unverändert | geprüft 2026-10-30: keine Nutzertexte (nur Kommentare, Logs, Fälligkeitslogik); die Orchestrierer übergeben die Nutzer-Iteration an die oben geänderten Dienste |
| `src/app/thunder_scale.py` | MODIFY (nur falls nötig) | Vor dem Anlegen mit Grep prüfen, ob P2/P3/P4 `thunder_headline_sentence`, `thunder_low_statement*` schon mit `lang` versehen haben; falls nicht, `lang: Lang = "de"` (keyword-only) ergänzen, Texte über `t("versand.gewitter.*", lang)` |
| `src/i18n/messages/de/versand.json`, `src/i18n/messages/en/versand.json` | MODIFY | Schlüssel `versand.scheduler.*` anhängen (P9a ist gemergt, kein Konflikt) |
| `src/i18n/messages/de/alarm.json`, `src/i18n/messages/en/alarm.json` | MODIFY (nur falls nötig) | Falls P5 einen der Schlüssel `alarm.nachtrag.abweichung`, `alarm.nachtrag.amtlich`, `alarm.nachtrag.von` nicht angelegt hat, hier ergänzen |
| `tests/golden/scheduler_texte/*.de.txt`, `*.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen) und Referenz `en`: Nachlieferungs-Präfixe, Teilausfall-Hinweis, Ortsvergleich-Betreff, Nachtrag-Bezug, Cooldown-Anzeige |
| `tests/golden/test_scheduler_texte_golden.py` | CREATE | Byte-Vergleich `de` |
| `tests/test_scheduler_sprache_je_nutzer.py` | CREATE | Zwei-Nutzer-Tests (AC-1, AC-2, AC-5) |
| `tests/test_scheduler_ausfall_alle_kanaele.py` | CREATE | Totalausfall und Nachlieferung in `en` auf allen Kanälen (AC-3, AC-4) |

## Estimated Scope

- **LoC:** ca. 130 Code (trip_report_scheduler ~45, trip_alert ~30, scheduler_dispatch_service ~15, compare_*-Durchreichen ~25, Rest Kommentare `# i18n-log` ~15); ohne Katalogdaten und Tests
- **Files:** 7 Code-Dateien (+ `thunder_scale.py` falls nötig), 2 bis 4 Katalogdateien plus Tests und Golden-Dateien
- **Effort:** medium (Dateien sehr groß, Eingriffe an vielen Stellen, aber mechanisch)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2646 S1 | Paket | `language` in `user.json`, `resolve_user_lang(user_id)` |
| #2662 P1 | Paket | `t`, `tn`, `fmt_weekday` |
| #2664 bis #2670 (P2 bis P8) | Pakete | Renderer mit `lang`-Signaturen (Voraussetzung dieses Pakets laut Issue) |
| #2671 P9a | Paket | `NotificationService(settings, user_id, *, lang=None)` und `send_no_data_hint`, `_apply_prefixes` mit Katalogtexten |
| #2667 P5 | Paket | `alarm.dauer.*`, `alarm.nachtrag.*`, `build_onset_alert_message(..., lang)`, `to_alert_message(..., lang)` |
| #2673 P10 (parallel) | Paket | Inbound-Antworten (nicht dieses Paket) |
| `services.send_outcomes` | Modul | `SendOutcomeError`-Codes; `outcome_from_result` bleibt |
| ADR-0104, ADR-0095, ADR-0003 | ADR | Sprache am Nutzer; Kanal-Parität; Mandantentrennung ohne `"default"` |

## Implementation Details

**Katalog-Namensraum:** `versand` (Unterbaum `versand.scheduler.*`) und wiederverwendet `alarm.*`; kein neuer Bereich. Nur `versand.json` (und ggf. `alarm.json`) anfassen. das im Glossar verbotene Produktwort ist untersagt (Produktbegriffe: Trip, Etappe, Ortsvergleich, Briefing).

**Muster (Konvention Abschnitt 4):** Einmal `lang = resolve_user_lang(user_id)` am Eintritt je Nutzer, durchreichen, **kein** globaler Zustand:

```
class TripReportSchedulerService:
    def __init__(self, settings=None, *, user_id: str) -> None:
        ...
        self._lang: Lang = resolve_user_lang(user_id)
        self._notification_service = NotificationService(self._settings, user_id, lang=self._lang)
```

`resolve_user_lang` liefert für fehlendes Feld, leeren Wert oder unbekannten Wert `de` (kein Fehler). `user_id` ist in allen betroffenen Konstruktoren Pflicht (`*, user_id: str`); es gibt keinen Pfad mit `"default"`.

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `versand.scheduler.nachgeliefert` | `Nachgeliefert — der Wetterdienst war um {stunde}:00 nicht erreichbar` | `Delivered late — the weather service was unavailable at {stunde}:00` | trip_report_scheduler.py:1031-1034 |
| `versand.scheduler.aktualisiert_unvollstaendig` | `Aktualisiert — weiterhin unvollständig, Details im Hinweis` | `Updated — still incomplete, see the note for details` | :1041 |
| `versand.scheduler.aktualisiert_vollstaendig` | `Aktualisiert — jetzt mit vollständigen Daten` | `Updated — now with complete data` | :1043 |
| `versand.scheduler.teilausfall` | `Hinweis: Für folgende Abschnitte liegen aktuell keine Wetterdaten vor ({abschnitte}) — eine Aktualisierung wird nachgeliefert.` | `Note: weather data is currently missing for the following sections ({abschnitte}) — an update will follow.` | :1805-1808 |
| `versand.scheduler.abschnitt` | `Segment {id}` | `Segment {id}` | :1804 |
| `versand.scheduler.vergleich_betreff` | `Wetter-Vergleich: {name} ({datum})` | `Weather comparison: {name} ({datum})` | `build_compare_preset_subject`, scheduler_dispatch_service.py:410 |
| `alarm.nachtrag.abweichung` | `Ergänzung zur gemeldeten Wetterabweichung` | `Addendum to the reported weather deviation` | trip_alert.py:2872 |
| `alarm.nachtrag.amtlich` | `Ergänzung zur amtlichen Warnung` | `Addendum to the official warning` | trip_alert.py:2874 |
| `alarm.nachtrag.von` | ` von {zeit}` | ` from {zeit}` | trip_alert.py:2878 |
| `alarm.dauer.stunden.one` / `.other` | `{count} Stunde` / `{count} Stunden` | `{count} hour` / `{count} hours` | trip_alert.py:2666 (Schlüssel aus P5) |

`Segment {id}` ist in beiden Sprachen gleich; der Schlüssel bleibt, weil der Satz um ihn herum übersetzt wird und die Platzhaltermengen paritätisch sein müssen. Das Datum im Ortsvergleich-Betreff nutzt `fmt_date_numeric(target_date, lang)` (P4; für `de` identisch zu `%d.%m.%Y`).

**Beispiel-Umstellung 1 (trip_report_scheduler.py:1031-1043, Nachlieferungs-Präfixe), vorher:**

```
if was_complete_failure:
    prefix = (
        f"Nachgeliefert — der Wetterdienst war um "
        f"{entry.get('slot_hour')}:00 nicht erreichbar"
    )
elif failed_ids_now:
    prefix = "Aktualisiert — weiterhin unvollständig, Details im Hinweis"
else:
    prefix = "Aktualisiert — jetzt mit vollständigen Daten"
```

**nachher:**

```
if was_complete_failure:
    prefix = t("versand.scheduler.nachgeliefert", self._lang, stunde=entry.get("slot_hour"))
elif failed_ids_now:
    prefix = t("versand.scheduler.aktualisiert_unvollstaendig", self._lang)
else:
    prefix = t("versand.scheduler.aktualisiert_vollstaendig", self._lang)
```

**Beispiel-Umstellung 2 (scheduler_dispatch_service.py:401-410 und 533/648/720/727/733), vorher:**

```
def build_compare_preset_subject(name: str, target_date: date) -> str:
    return f"Wetter-Vergleich: {name} ({target_date.strftime('%d.%m.%Y')})"
...
html_body, text_body = render_compare_email(result, undelivered=undelivered, ...)
send_result = NotificationService(settings, user_id).send_compare_report(...)
```

**nachher:**

```
def build_compare_preset_subject(name: str, target_date: date, *, lang: Lang = "de") -> str:
    return t("versand.scheduler.vergleich_betreff", lang, name=name,
             datum=fmt_date_numeric(target_date, lang))
...
lang = resolve_user_lang(user_id)          # einmal am Eintritt von send_one_compare_preset
html_body, text_body = render_compare_email(result, ..., lang=lang)
send_result = NotificationService(settings, user_id, lang=lang).send_compare_report(...)
```

**Beispiel-Umstellung 3 (trip_alert.py:2870-2880, Nachtrag-Bezug), vorher:**

```
_bezug = (
    "Ergänzung zur gemeldeten Wetterabweichung"
    if _identity_gate.addendum_source == "deviation"
    else "Ergänzung zur amtlichen Warnung"
)
if _identity_gate.addendum_reported_at is not None:
    _bezug += f" von {local_fmt(_identity_gate.addendum_reported_at, tz)}"
```

**nachher:**

```
_bezug = t(
    "alarm.nachtrag.abweichung" if _identity_gate.addendum_source == "deviation"
    else "alarm.nachtrag.amtlich", self._lang)
if _identity_gate.addendum_reported_at is not None:
    _bezug += t("alarm.nachtrag.von", self._lang,
                zeit=local_fmt(_identity_gate.addendum_reported_at, tz))
```

(Die bedingte Schlüsselwahl mit zwei Literalen ist erlaubt; kein dynamisch zusammengesetzter Schlüssel.)

**Durchreichen an die Renderer:** Mit Grep alle Aufrufe in den betroffenen Dateien finden und `lang=` ergänzen: `render_telegram_bubbles`, `SMSTripFormatter().format_sms`, `render_email`/`render_subject`/`render_telegram`/`render_sms` (Alarm), `render_official_alert_*`, `build_official_alert_notices`, `build_email_subject`, `render_compare_*`, `to_alert_message`, `build_onset_alert_message`. Die Aufrufe in `notification_service.py` gehören P9a und sind dort erledigt; P9b stellt sicher, dass jede Stelle, die `NotificationService(...)` baut, `lang` übergibt.

**Nicht ändern:** Fälligkeitslogik, Slots, Pausen-Prüfung (`trip_pausiert`), Marker-Dateien (`pending`), Dedup-/Melde-Gedächtnis-Schlüssel, Operator-Benachrichtigung `_notify_corrupt` (Zeile 509, geht an den Betreiber über MQ und bleibt deutsch mit `# i18n-log`), alle `logger`-Texte, SMS-Token.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) die Präfixe `src/services/trip_report_scheduler.py`, `src/services/trip_alert.py`, `src/services/scheduler_dispatch_service.py`, `src/services/compare_alert.py`, `src/services/compare_radar_alert.py`, `src/services/compare_official_alert.py`, `src/services/compare_preview_service.py` entfernen (vorher `Glob tests/fixtures/i18n_python_allowlist.json`; existiert sie noch nicht, holt P11 den Schritt nach). Zeilen, die in der Ratsche anschlagen, weil sie Log-Text mit Umlaut sind, erhalten `# i18n-log`.

**Golden-Fixture:** Deterministisch (feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`, festes Wetter über die vorhandenen Test-Nähte der Dienste). **Zuerst** `*.de.txt` mit dem unveränderten Code erzeugen und committen, danach umstellen.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten, Fälligkeitslogik anfassen.

## Expected Behavior

- **Input:** Cron-Lauf über die Nutzer eines Mandanten (je Nutzer ein Dienstobjekt mit `user_id`), Trips und Ortsvergleiche, Wetter- und Radar-Daten.
- **Output:** Jede Nachricht (E-Mail, Telegram, SMS, Premium-SMS) in der Sprache **ihres** Nutzers; bei `de` byte-gleich zu heute. Eigene Hinweise des Schedulers (Nachlieferung, Teilausfall, Ortsvergleich-Betreff, Nachtrag) zweisprachig.
- **Side effects:** Lesen von `data/users/<user_id>/user.json` (nur `language`) einmal je Dienstobjekt bzw. je `send_one_compare_preset`-Aufruf. Keine Schreibzugriffe, kein Modul-Zustand.

## Acceptance Criteria

- **AC-1:** Given zwei Nutzer, `golden-de` (Sprache `de`) und `golden-en` (Sprache `en`), mit je einem fälligen Briefing im selben Lauf / When der Scheduler beide Nutzer nacheinander bedient (Reihenfolge `de`, `en`, `de`) / Then ist jede Mail in der Sprache ihres Nutzers (Betreff, Hinweis, Header `X-GZ-Lang`), und die Reihenfolge ändert nichts.
  - Test: tests/test_scheduler_sprache_je_nutzer.py — zwei `TripReportSchedulerService(user_id=...)` mit echten `user.json`-Dateien im Test-Datenverzeichnis, Mitschnitt über die Sink-Naht; kein Spiegel-Mock der Sprache.

- **AC-2:** Given zwei Nutzer verschiedener Sprache mit je einem fälligen Ortsvergleich / When `send_one_compare_preset` für beide läuft / Then tragen E-Mail, Telegram-Text und SMS-Text je die Sprache ihres Nutzers, der Betreff lautet `Weather comparison: …` bzw. `Wetter-Vergleich: …`, und `NotificationService` wird mit der Sprache des jeweiligen Nutzers gebaut.
  - Test: tests/test_scheduler_sprache_je_nutzer.py — beide Aufrufe mit Test-Nähten (`mail_sink`, `sms_sink`, `telegram_sink`, `premium_sms_sink`), Vergleich der Texte gegen `t(key, lang)`.

- **AC-3:** Given Totalausfall aller Wetter-Provider bei einem Nutzer mit Sprache `en` und aktiven Kanälen E-Mail, Telegram und SMS / When der Scheduler das Briefing versucht / Then geht die Ausfall-Meldung (`[GR20] Weather data unavailable` bzw. `Weather service currently unavailable …`) auf allen drei konfigurierten Kanälen in Englisch hinaus; derselbe Fall mit `de` bleibt byte-gleich.
  - Test: tests/test_scheduler_ausfall_alle_kanaele.py — erzwungener Provider-Ausfall über die Test-Naht, Mitschnitt aller Kanäle, Erwartung über Katalog.

- **AC-4:** Given eine ausstehende Nachlieferung (Marker aus einem Totalausfall um 6 Uhr) und Sprache `en` / When die Nachlieferung gelingt, teilweise gelingt und vollständig gelingt / Then lauten die Präfixe `Delivered late — the weather service was unavailable at 6:00`, `Updated — still incomplete, see the note for details` und `Updated — now with complete data`; der Teilausfall-Hinweis nennt die Abschnitte (`Segment 2, Segment 3`) auf Englisch.
  - Test: tests/test_scheduler_ausfall_alle_kanaele.py — drei Nachlieferungs-Fälle über `_process_pending_markers`-nahe Naht, Texte gegen den Katalog.

- **AC-5:** Given ein Nutzer mit Sprache `en` und ein Radar-Alarm mit Cooldown 120 Minuten und Nachtrag zu einer amtlichen Warnung von 16:15 / When `TripAlertService` den Alarm versendet / Then lautet der Cooldown-Satz `… at most once every 2 hours …`, der Nachtrag-Bezug `Addendum to the official warning from 16:15`, das Wochentagskürzel im SMS-Token `Thu`; ein Nutzer ohne Feld `language` bekommt im selben Lauf Deutsch.
  - Test: tests/test_scheduler_sprache_je_nutzer.py — `TripAlertService(user_id=...)` mit `mail_sink`, Fall `en` und Fall ohne `language`-Feld (Bestandsnutzer).

- **AC-6:** Given Sprache `de` / When Nachlieferungs-Präfixe, Teilausfall-Hinweis, Ortsvergleich-Betreff, Nachtrag-Bezug und Cooldown-Anzeige erzeugt werden / Then ist jede Ausgabe byte-gleich zu den vorab eingecheckten `*.de.txt`-Dateien.
  - Test: tests/golden/test_scheduler_texte_golden.py — Byte-Vergleich je Text.

## Known Limitations

- Annahme: Die Sprache wird beim Anlegen des Dienstobjekts gelesen; ändert ein Nutzer sie während eines Laufs, gilt sie ab dem nächsten Lauf. Das ist bewusst (ein Zustand je Lauf und Nutzer, keine zweite Lesestelle).
- Annahme: `compare_preview_service.py` wird mitgeführt, weil P4 die Durchreichung für die Vorschau an P9b delegiert hat; die Vorschau-API stellt `user_id` aus dem Auth-Kontext bereit.
- Annahme: Die Gewitter-Sätze der Etappen-Vorschau (`thunder_headline_sentence`, `thunder_low_statement*` in `src/app/thunder_scale.py`) werden hier nur ergänzt, falls kein früheres Paket sie schon sprachfähig gemacht hat (Grep zuerst).
- Annahme: Die Cooldown-Anzeige in `trip_alert.py` wird nicht mit der Kopie in `radar_alert_service.py` zusammengeführt (eigene Bereinigung, kein Teil des Epics); beide benutzen dieselben Katalogschlüssel.
- Annahme: `first_briefing.py`, `briefing_slots.py`, `compare_slot_scheduler.py`, `dispatch_orchestrator.py` enthalten keine Nutzertexte (geprüft) und bleiben unverändert; „keine Etappe heute“ und Pausen-Hinweise sind Ausgangscodes (`no_stage`, `channels_unreachable` in `send_outcomes.py`, P9a) bzw. Antworten der Befehle (P10).
- Der Operator-Hinweis `_notify_corrupt` an den Betreiber bleibt deutsch (Epic-Abgrenzung: Admin-/Betreiber-Meldungen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0095 für Kanal-Parität, ADR-0003 für Mandantentrennung)
- **Rationale:** Die Sprache ist Nutzer-Eigenschaft und wird einmal je Nutzer an der Dienstgrenze gelesen und als Attribut gehalten; so teilen zwei Nutzer im selben Lauf keinen Zustand.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
