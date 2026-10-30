---
entity_id: i18n_p7_telegram_2669
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2669, python, docs, model-haiku]
---

# i18n P7: Telegram-Briefing (Bubbles) zweisprachig

**Issue:** #2669 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4 (Kurzform = Platzform: ADR-0104 Nr. 5), 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Englisch gewählt hat, liest das Telegram-Briefing auf Englisch: Kopf, `Summary`, `Outlook`, `Actions`, die Fußzeile mit Gewitter, Sicht und Nullgradgrenze, die Vortag-Zeile, den Hinweis „Briefing unvollständig“ und den Segment-Kopf. Auf dem Pass ist Telegram oft der gelesene Kanal (ADR-0095), daher trägt er denselben Inhalt wie die E-Mail. Kürzel (`compact_label`), Zahlenformate, Slash-Befehle und Button-Befehle bleiben unverändert; der Telegram-Kurzstil ist eine Platzform, keine Sprachwahl. Deutsch bleibt byte-gleich.

## Source

- **File:** `src/output/renderers/narrow.py`, `src/output/channels/telegram.py`, `docs/reference/telegram_format.md`
- **Identifier:** `render_telegram_bubbles` (narrow.py:659), `_tg_day_footer` (217), `_tg_vortag_line` (316), `_official_alert_bubble` (389), `_overview_line` (438), `_segment_mini_header` (566), `_outlook_lines` (578), `render_telegram_incomplete_hint` (640), `TelegramOutput` / `BOT_COMMANDS` (telegram.py:132, 176)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/`, `src/output/channels/`). Kein Go-, kein Frontend-Code. Der Transport (`TelegramOutput.send`) bleibt sprachneutral; Texte entstehen im Renderer `narrow.py`. Die Sprache wird von P9a/P9b durchgereicht.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Der Trip-Telegram-Renderer (`narrow.py`) und der Ortsvergleich-Telegram-Renderer (`comparison.py::render_compare_telegram`, P4) teilen den Hinweis `telegram_metric_notice` (`channel_layout.py`, von P4 sprachfähig gemacht, `context="route"`/`"vergleich"`); P7 ruft ihn nur mit `lang=lang` auf (narrow.py:858). Die amtlichen Warnungen laufen über den geteilten `render_official_alert_telegram` (P6). Kein neues Compare-Pendant.
> - **Mandantentrennung:** Reine Funktionen ohne Nutzerdaten und ohne Modul-Zustand; AC-6 beweist, dass zwei Aufrufe nacheinander (`en`, `de`) sich nicht beeinflussen. Das Live-Skript (AC-7) benutzt den bestehenden Test-Nutzer (ein Chat = ein Nutzer, `address_owner.go`), setzt dessen Sprache über die Go-API und stellt sie im `finally` zurück.
> - **Kanäle:** Briefing-Inhalt. Alle vier: Telegram (dieses Paket), E-Mail (P2/P3), SMS und Premium-SMS (P8; der Telegram-Kurzstil sendet den SMS-Text unverändert, `notification_service`/`trip_report.py`). Gleicher Inhalt, kanalgerechte Form.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/narrow.py` | MODIFY | `lang: Lang = "de"` (keyword-only) an `render_telegram_bubbles`, `_tg_day_footer`, `_tg_vortag_line`, `_official_alert_bubble`, `_segment_mini_header`, `_outlook_lines`, `render_telegram_incomplete_hint`; alle Nutzertexte über `t`/`tn` |
| `src/output/channels/telegram.py` | MODIFY (nur Kommentare) | `BOT_COMMANDS` (Zeile 132) und die Wächter-Texte (`_block(...)`, Zeilen 233-315, 503) bleiben UNVERÄNDERT; Wächter-Zeilen mit Umlaut erhalten `# i18n-log`. `BOT_COMMANDS` muss ein ausgeschriebenes Listen-Literal bleiben (`prod_selftest.py::_load_bot_commands` liest es per `ast.literal_eval`) |
| `src/output/renderers/alert/official_alerts.py` | unverändert | Telegram-Zweig (`render_official_alert_telegram`, `render_official_allclear_telegram`) wurde in P6 erledigt; P7 prüft nur, dass narrow.py `lang` übergibt |
| `src/i18n/messages/de/telegram.json`, `src/i18n/messages/en/telegram.json` | MODIFY | Neue Schlüssel `telegram.*` (nur diese Bereichsdateien anfassen) |
| `docs/reference/telegram_format.md` | MODIFY | Neuer Abschnitt „5. Sprache“ (siehe Implementation Details) |
| `scripts/staging_e2e_telegram_en.py` | CREATE | Live-Prüfung gegen Staging: Sprache des Test-Nutzers auf `en`, Briefing anfordern, Nachricht prüfen, im `finally` zurück auf `de`; läuft nur in `/e2e-verify` |
| `tests/golden/telegram_briefing/briefing_normalstil.de.txt`, `.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen) und Referenz `en`: Bubbles als eine Datei, getrennt durch `---` |
| `tests/golden/test_telegram_briefing_golden.py` | CREATE | Byte-Vergleich `de` |
| `tests/test_telegram_briefing_zweisprachig.py` | CREATE | Verhaltenstests der ACs |

## Estimated Scope

- **LoC:** ca. 85 Code (narrow.py ~70, telegram.py nur Kommentare, Skript ~40 zusätzlich); ohne Katalogdaten, Doku und Tests
- **Files:** 5 Code-/Doku-/Skript-Dateien, 2 Katalogdateien plus Tests und Golden-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 | Paket | `t`, `tn`, `fmt_weekday`, `fmt_date`, `MetricDefinition.label(lang)` |
| #2666 P4 | Paket | `telegram_metric_notice(..., lang)`, `fmt_date_numeric`, `lang`-fähige Gewitter-/Hagel-Wörter in `output/metric_format.py` (`thunder_label(level, lang)`, `format_hail_note(flag, lang)`) |
| #2664 P2 / #2665 P3 | Pakete | `render_official_alerts_unavailable_plain`, `render_starkregen_hint_plain`, `render_outlook_state_*` akzeptieren `lang` (narrow.py ruft sie mit `lang=lang`) |
| #2668 P6 | Paket | `render_official_alert_telegram(..., lang)`, `build_official_alert_notices(..., lang)` |
| #2667 P5 | Paket | Alarm-Telegram (`alert/render.py`) bereits zweisprachig; nicht Teil dieses Pakets |
| #2671 P9a, #2672 P9b (danach) | Pakete | reichen `lang` an `render_telegram_bubbles` durch |
| #2673 P10 (danach) | Paket | `ACTIONS_BUBBLE_BUTTONS` und die Antworttexte der Befehle (`KUERZEL`/`CODES`) sind Inbound-Texte in `trip_command_processor.py` |
| ADR-0104, ADR-0042, ADR-0095 | ADR | Sprache am Nutzer; Kurzform ist Platzform; Kanal-Parität |

## Implementation Details

**Katalog-Namensraum:** `telegram` (`src/i18n/messages/{de,en}/telegram.json`). Nur diese beiden Dateien anfassen. das im Glossar verbotene Produktwort ist untersagt (Produktbegriffe: Trip, Etappe, Ortsvergleich, Briefing).

**Signaturen (Abschnitt 4):** `*, lang: Lang = "de"` keyword-only:

```
def render_telegram_bubbles(*, segments, seg_tables, dc, report_type, tz, ..., lang: Lang = "de") -> list[TelegramBubble]
def render_telegram_incomplete_hint(missing_count: int, *, lang: Lang = "de") -> str
def _tg_day_footer(segments, enabled_metric_ids, *, night_weather=None, tz, ..., lang: Lang = "de") -> Optional[str]
```

**Beispiel-Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `telegram.kopf.zusammenfassung` | `Kurzübersicht` | `Summary` | narrow.py:772 |
| `telegram.kopf.ausblick` | `Ausblick` | `Outlook` | narrow.py:589, 892 |
| `telegram.kopf.aktionen` | `Aktionen` | `Actions` | narrow.py:895 |
| `telegram.fuss.luftmasse` | `Luftmasse {wort}` | `Air mass {wort}` | `_tg_day_footer`, narrow.py:283 |
| `telegram.fuss.sicht` | `Sicht {wort}` | `Visibility {wort}` | narrow.py:305 |
| `telegram.fuss.sicht_gut` / `_maessig` / `_schlecht` | `gut` / `mäßig` / `schlecht` | `good` / `fair` / `poor` | narrow.py:300-304 |
| `telegram.fuss.nullgradgrenze` | `0°C-Grenze {hoehe} m` | `Freezing level {hoehe} m` | narrow.py:309 |
| `telegram.vortag.zeile` | `Ggü. Vortag: {liste}` | `vs. yesterday: {liste}` | `_tg_vortag_line`, narrow.py:376 |
| `telegram.vortag.label_regen` | `Regen` | `Rain` | narrow.py:343 |
| `telegram.vortag.label_boeen` | `Böen` | `Gusts` | narrow.py:345 |
| `telegram.vortag.label_gewitter` | `Gewitter` | `Thunderstorm` | narrow.py:348 |
| `telegram.hinweis.unvollstaendig.one` | `⚠️ Briefing unvollständig — {count} Teil des Briefings ist nicht angekommen. Bitte fordere das Briefing gleich noch einmal an.` | `⚠️ Briefing incomplete — {count} part of the briefing did not arrive. Please request the briefing again shortly.` | narrow.py:653-655 |
| `telegram.hinweis.unvollstaendig.other` | `⚠️ Briefing unvollständig — {count} Teile des Briefings sind nicht angekommen. Bitte fordere das Briefing gleich noch einmal an.` | `⚠️ Briefing incomplete — {count} parts of the briefing did not arrive. Please request the briefing again shortly.` | narrow.py:653-655 |
| `telegram.segment.ziel` | `Ziel` | `Finish` | `_segment_mini_header`, narrow.py:574 |
| `telegram.segment.keine_daten` | `Seg {id}: keine Daten` | `Seg {id}: no data` | narrow.py:868 |
| `telegram.warnung.praefix` | `Amtliche Warnung` | `Official warning` | `_official_alert_bubble`, narrow.py:434 |

`Segment {id}` (narrow.py:574) und die Einheiten `km`, `m`, `km/h`, `°C` bleiben in beiden Sprachen gleich (kein Schlüssel nötig). Die Gewitterstufen-Wörter und der Hagel-Hinweis kommen aus den von P4 sprachfähig gemachten Funktionen (`thunder_label(level, lang)`, `format_hail_note(flag, lang)`); `THUNDER_LABEL_DE[...]` im Aufruf narrow.py:275/277 wird durch `thunder_label(level, lang)` ersetzt (für `de` identisch).

**Beispiel-Umstellung 1 (narrow.py:640-656, Plural), vorher:**

```
count = max(1, int(missing_count))
teile = "Teil" if count == 1 else "Teile"
ist_sind = "ist" if count == 1 else "sind"
return (f"⚠️ Briefing unvollständig — {count} {teile} des Briefings "
        f"{ist_sind} nicht angekommen. Bitte fordere das Briefing gleich "
        "noch einmal an.")
```

**nachher:**

```
count = max(1, int(missing_count))
return tn("telegram.hinweis.unvollstaendig", count, lang)
```

**Beispiel-Umstellung 2 (narrow.py:298-305, Sicht-Wort), vorher:**

```
if min_vis >= 10000:
    vis_word = "gut"
elif min_vis >= 4000:
    vis_word = "mäßig"
else:
    vis_word = "schlecht"
parts.append(f"Sicht {vis_word}")
```

**nachher** (Schlüssel als statische Zuordnung, kein dynamischer Schlüsselbau):

```
if min_vis >= 10000:
    vis_word = t("telegram.fuss.sicht_gut", lang)
elif min_vis >= 4000:
    vis_word = t("telegram.fuss.sicht_maessig", lang)
else:
    vis_word = t("telegram.fuss.sicht_schlecht", lang)
parts.append(t("telegram.fuss.sicht", lang, wort=vis_word))
```

**Kopfzeile (narrow.py:729-730):** `local_fmt(segments[0].segment.start_time, tz, "%d.%m.%Y")` bleibt für `de`; für `en` `fmt_date_numeric(...)` aus P4 (`29 Oct 2026`). `report_type.title()` (`Evening`, `Morning`) ist schon englisch und bleibt in beiden Sprachen. `WL: {label}` (Stabilitäts-Label) bleibt, sofern es kein Katalogwort enthält.

**Kurzform ist Platzform:** `_overview_line` (narrow.py:438) schreibt `{Kürzel} {Min}-{Max}@{Peak}` mit `compact_label`; das Kürzel, die Zahlen und `@HH` bleiben unverändert. Nur die Wörter ändern sich, die das Kürzel ersetzen (`Luftmasse`, `⚡ {Stufe}`, Hagel-Hinweis). Der Telegram-Kurzstil (`kurzform`, #2417) sendet den SMS-Text unverändert; seine Klartext-Anteile gehören zu P5/P8, seine Befehls-Antwort `KUERZEL`/`CODES` zu P10. `BOT_COMMANDS` (Bot-Menü) ist botweit und bleibt deutsch (siehe Known Limitations).

**Doku `docs/reference/telegram_format.md`:** Neuer Abschnitt „## 5. Sprache“ (nach „## 4. Quelle im Code“) mit diesen Aussagen: Sprache = Konto-Sprache des Nutzers (ADR-0104); Normalstil spricht Deutsch oder Englisch mit demselben Inhalt; Kurzstil und Kürzel (`compact_label`), Zahlenformat, Slash-Befehle, Button-Befehle bleiben unverändert (Platzform, ADR-0042); Bot-Menü-Beschreibungen sind botweit deutsch; Quelle der Texte: Katalog `telegram.*` und `allgemein.*`.

**Live-Skript `scripts/staging_e2e_telegram_en.py`:** Idempotent, nur gegen Staging: liest die Zugangsdaten aus der Staging-Umgebung (nie im Repo), setzt über `PUT /api/auth/profile` die Sprache des bestehenden Test-Nutzers auf `en`, fordert ein Briefing per Handversand an, liest die zugestellte Nachricht über den Test-Chat und prüft sie gegen `t(key, "en")`, setzt die Sprache im `finally` auf `de` zurück und fällt bei Fehlern laut durch (Exit ≠ 0).

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) den Präfix `src/output/renderers/narrow.py` entfernen (vorher `Glob tests/fixtures/i18n_python_allowlist.json`; existiert sie noch nicht, holt P11 den Schritt nach).

**Golden-Fixture:** Deterministisch (feste Zeit `2026-10-29T06:00+02:00`, feste Wetterwerte, Nutzer `golden-de`; Trip mit zwei Segmenten und Ziel, Gewitter, Sicht, Nullgradgrenze, Vortag-Delta, ein Ausblick, eine amtliche Warnung). **Zuerst** `*.de.txt` mit dem unveränderten Code erzeugen und committen, danach umstellen.

**Token-Wächter:** `tests/test_metric_tokens_eingefroren.py` bleibt grün; `compact_label`, `col_label` und `sms_code` werden nicht angefasst.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten, `BOT_COMMANDS` umbauen.

## Expected Behavior

- **Input:** Segment-Wetterdaten, Tabellenzeilen, Anzeige-Konfiguration, Berichtsart, Zeitzone, Trip-Name und `lang`.
- **Output:** Liste von `TelegramBubble`. `de` byte-gleich zu heute. `en`: Überschriften, Fußzeilen-Wörter, Vortag-Zeile, Hinweise, Segment-Kopf und Warnungs-Präfix englisch; Kürzel, Zahlen, Einheiten, Namen und Button-Befehle unverändert.
- **Side effects:** Keine. Beim Fehlen eines englischen Schlüssels fällt der Kern auf Deutsch zurück und loggt einmal; der Paritätstest verhindert das im Repo.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit zwei Segmenten und Nutzer-Sprache `en` / When die Telegram-Bubbles gerendert werden / Then sind Überschriften (`Summary`, `Outlook`, `Actions`), die Fußzeile (`Air mass`/`⚡ …`, `Visibility good`, `Freezing level 2800 m`), die Vortag-Zeile (`vs. yesterday:`) und das Warnungs-Präfix (`Official warning`) englisch, und es kommt kein deutsches Katalogwort vor.
  - Test: tests/test_telegram_briefing_zweisprachig.py — rendert die Golden-Fixture mit `lang="en"` und prüft über `t(key, "en")` die Texte sowie einen Scan der Bubbles auf deutsche Katalogwerte.

- **AC-2:** Given Sprache `de` / When die Bubbles der Golden-Fixture gerendert werden / Then ist jede Bubble byte-gleich zu den vorab eingecheckten `*.de.txt`-Dateien.
  - Test: tests/golden/test_telegram_briefing_golden.py — Byte-Vergleich je Bubble.

- **AC-3:** Given Sprache `en` / When die Kurzübersicht gerendert wird / Then sind Kürzel (`compact_label`), Zahlenformat (`{Min}-{Max}@{Stunde}`) und Slash-/Button-Befehle der Aktionen-Bubble identisch zur deutschen Ausgabe; nur Wörter wie `Luftmasse`/`Air mass` unterscheiden sich.
  - Test: tests/test_telegram_briefing_zweisprachig.py — vergleicht Kürzel- und Zahlen-Token der Zeilen zwischen `de` und `en` nach Entfernen der Katalogwörter und prüft `ACTIONS_BUBBLE_BUTTONS` auf Gleichheit.

- **AC-4:** Given fehlende Briefing-Teile (1 und 3) und Sprache `en` / When der Hinweis gerendert wird / Then lautet er `1 part … did not arrive` bzw. `3 parts … did not arrive`; mit `de` bleibt `1 Teil … ist nicht angekommen` bzw. `3 Teile … sind nicht angekommen`.
  - Test: tests/test_telegram_briefing_zweisprachig.py — Plural-Fälle über `tn("telegram.hinweis.unvollstaendig", n, lang)`, Gegenprobe `de` byte-gleich.

- **AC-5:** Given Sprache `en` und eine amtliche Warnung der Stufe ORANGE im Segment / When die Warnungs-Bubble gerendert wird / Then trägt sie das Präfix `Official warning` und den englischen Rahmen aus P6 (`ORANGE`, `Warning level`), der Behörden- und Ortsname bleibt unverändert.
  - Test: tests/test_telegram_briefing_zweisprachig.py — prüft Präfix und Rahmen über den Katalog; Eigennamen unverändert.

- **AC-6:** Given zwei aufeinanderfolgende Render-Aufrufe für zwei Nutzer, erst `en`, dann `de`, mit derselben Fixture / When die Ergebnisse verglichen werden / Then ist das zweite Ergebnis byte-gleich zur Golden-`de`-Ausgabe (kein Zustand zwischen Nutzern).
  - Test: tests/test_telegram_briefing_zweisprachig.py — Reihenfolge `en`, `de`, `en`.

- **AC-7:** Given der Staging-Test-Nutzer mit gesetzter Sprache `en` / When ein Briefing per Handversand an den Test-Chat gesendet wird / Then ist die zugestellte Telegram-Nachricht englisch, und die Sprache des Nutzers steht danach wieder auf `de` (auch bei Fehlschlag).
  - Test: scripts/staging_e2e_telegram_en.py — Live-Lauf in `/e2e-verify` (kein Mock); Rücksetzen im `finally` wird durch einen erzwungenen Fehlschlag-Lauf geprüft.

## Known Limitations

- Das Bot-Menü (`BOT_COMMANDS`, `setMyCommands`) ist botweit und bleibt deutsch mit den englischen Zusatzbefehlen aus #2417; Telegram erlaubt keine Sprache je Nutzer ohne Chat-Scope. Antworten auf Befehle (`HILFE`, `KUERZEL`/`CODES`, Schaltflächen-Beschriftungen) gehören zu P10 (#2673).
- Annahme: Die Kürzel-Legende des Kurzstils (`CODES` englisch / `KUERZEL` deutsch, `kuerzel_bedeutung_en/_de`) ist eine Befehlsantwort in `trip_command_processor.py` und damit P10, nicht Teil der Bubbles. P7 stellt sicher, dass der Kurzstil den SMS-Text unverändert sendet.
- Annahme: Der Telegram-Zweig der amtlichen Warnungen ist in P6 erledigt; P7 prüft nur.
- Annahme: `report_type.title()` (`Morning`/`Evening`) bleibt in beiden Sprachen unverändert (heute schon englisch).
- Annahme: Das Live-Skript ist neu, weil `.claude/hooks/e2e_telegram_live.py` nur das Close-Gate (Test-Chat gesetzt) prüft und keine Nachricht sendet.
- Bis P9a/P9b sendet das System weiter deutsch (keine Durchreichung von `lang`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042 für Kürzel und Kurzform, ADR-0095 für Kanal-Parität)
- **Rationale:** Die Sprache gehört dem Nutzer; Kürzel, Zahlen und Befehle sind Platz- und Protokollform und bleiben, damit Kurzstil und Selbsttests stabil sind.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
