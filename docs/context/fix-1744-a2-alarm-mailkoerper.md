# Context: fix-1744-a2-alarm-mailkoerper

**Issue:** #1744 Scheibe A2 · **Spec:** `docs/specs/modules/fix_1744_alarm_format_angleichen.md`
(AC-8 bis AC-12, freigegeben 2026-08-12) · **Vorgänger:** A1 live über `0861a9a8` (PR #1781)

## Request Summary

Die zwei Trip-Alarm-Mailtypen sollen denselben Aufbau bekommen. A1 hat die **Ortssprache**
vereinheitlicht (Segment-Kennung statt km-Spanne). A2 gleicht den **Mail-Körper** an: gleiche
Bausteinfolge, Fakten der amtlichen Warnung als Datenzeilen in der Bauform des Nowcasts.

## Ist-Zustand: die zwei Körper nebeneinander

Beide Pfade setzen HTML in Python-f-Strings zusammen — kein Jinja, kein Template.

| # | Nowcast/Abweichung (`render.py`) | Amtliche Warnung (`official_alerts.py`) |
|---|---|---|
| 1 | Badge „Radar-Nowcast" — `:242,272-274` | Verdict-Pille „N amtliche Warnung(en)" — `:940-962` |
| 2 | H1 „{Typ} in {N} Min" — `:243,275` | H1 „{Typen} für {Scope} gemeldet." — `:965-1008` |
| 3 | *(kein Analogon)* | **Warnstufen-Skala** GELB·ORANGE·ROT + „{niedrigste\|mittlere\|höchste} von drei" — `:1011-1059` (nur bei einheitlicher Stufe; sonst Balken-Meter `:1062-1090` **ohne** „von drei") |
| 4 | Verdict-Pille „N über Schwelle" (nur Abweichung) — `:476,551-553` | *(steckt in Baustein 1)* |
| 5 | **Datenzeilen** „Wo & wann", „Intensität", „Quelle", „Briefing" — `:246-252` | **Warn-Grid**: Typ links, Facts rechts („Gültig:", „Route:"/„Orte:" + Chips) — `:1143-1177,1107-1132` |
| 6 | Cooldown-Box „…höchstens einmal in {…}" — `:255-258,278-282` | *(fehlt — kein Cooldown-Hinweis im Modul)* |
| 7 | Stand-Zeile „Stand: heute {Zeit}" — `:254,283-285` | Stand-Zeile „Stand: heute {Zeit} · abgerufen bei {Quelle}" — `:1365-1369` |
| 8 | *(Quelle steckt in Datenzeile 5)* | **Quelle-Box** „Quelle: {Quelle} — {Regionen}. {Satz}" — `:1285-1315` |
| 9 | Herkunfts-Fußzeile (geteilt) — `:420-432` | Herkunfts-Fußzeile (geteilt) — `:1373-1378` |

**Zwei Bauformen für dieselbe Sache:** Der Nowcast rendert je Datenzeile eine
`<table role="presentation">` mit Label links / Wert rechtsbündig (`_datarow_html`,
`render.py:403-417`, Outlook-Begründung im Kommentar). Die amtliche Warnung rendert ein
CSS-Grid-`<div class="warn">` mit einem einzigen Facts-Block, in dem Label und Wert als
`<span class="k">Gültig:</span> … <br>` inline stehen (`official_alerts.py:1107-1132`).

## 🔴 Der Befund, der nicht in der Spec steht: die amtliche Warn-Mail hat keinen Klartext

- **Nowcast:** baut `html` **und** `plain` in derselben Funktion aus denselben Datenzeilen und
  übergibt den Klartext ausdrücklich — `notification_service.py:1322,1400-1405`.
- **Amtliche Warnung:** `render_official_alert_html()` liefert nur HTML;
  `send_official_alert` ruft `EmailOutput.send(...)` **ohne** `plain_text_body`
  (`notification_service.py:859-861`). Der Klartext entsteht danach per Regex-Strippen aus dem
  HTML — `src/output/channels/email.py:350-358`: Tags raus, Entities ersetzt, Leerzeilen
  gefaltet. Aus dem CSS-Grid wird dabei zwangsläufig Zeilensalat.
- `render_official_alert_notice_plain()` (`official_alerts.py:615-662`) existiert, wird aber
  **nur** für den in eine andere Mail eingebetteten Warnblock benutzt, nie für die eigenständige
  Warn-Mail.

Damit ist „gleicher Aufbau" im HTML herstellbar, im Klartext heute strukturell nicht.
**Offene Umfangsfrage an den PO** (unten unter „Zu entscheiden").

## 🔴 Wächter, die den Umbau ablehnen können

`renderer_mail_gate.py` verlangt beim Commit **zwei** frische Validator-Nachweise, weil A2 beide
Dateien anfasst: `*_radar_alert_validation.yaml` (für `render.py`/`model.py`/`project.py`) **und**
`*_official_alert_validation.yaml` (für `official_alerts.py`). Beide entstehen nicht durch
pytest, sondern im Validierungsschritt.

**`official_alert_mail_validator.py` prüft CSS-Klassen, nicht nur Text:**

| Prüfung | Stelle | Konsequenz für A2 |
|---|---|---|
| `_REQUIRED_CLASSES = {"verdict", "warn", "src", "body-foot"}` | `:73`, S-1 `:160-165` | 🔴 **Kollision:** Wird die Quelle-Box (Baustein 8) zur Datenzeile, verschwindet `class="src"` → Validator lehnt eine korrekte Mail ab |
| Skala nur als `stufe-line` **oder** `stacked`/`meter` | `:74-76`, S-2 `:167-174` | Die Skala muss ihre CSS-Klasse behalten (AC-9 fordert sie ohnehin inhaltlich) |
| `_LEVEL_WORD_RE = (GELB\|ORANGE\|ROT)` | `:60` | bleibt erfüllt, solange die Stufenwörter im Text stehen |
| Literale `"Quelle:"` + `"abgerufen bei"` | P-4 `:203-207` | müssen im Text überleben, egal in welchem Baustein |
| Literal `"Stand: heute"` | P-5 `:209-210` | Stand-Zeile bleibt pflichtig |
| `"Gültig:"`-Zeile braucht Wochentag+Datum | P-3 `:62-69,188-201` | Format der Gültigkeitsangabe darf nicht vereinfacht werden |

**`radar_alert_mail_validator.py`** zählt gültige Formen auf und lehnt jede neue ab — dieselbe
Falle, die in A1 zuschlug (`_SEGMENT_RE` kannte `🏁 Ziel` nicht):

- `_SEGMENT_RE` (`:65-68`) — Ortsformen
- `_INTENSITY_LABELS` (`:39-47`) — sieben erlaubte Intensitätslabel
- P-4 (`:140-143`) — Literal `"höchstens einmal in"` (Cooldown-Hinweis)

## Tests, die den Körper bewachen

Rund 40 Testdateien berühren die beiden Renderer. Für A2 relevant:

**Brechen absichtlich (Struktur-Prüfer der heutigen Bauform):**

| Datei | prüft |
|---|---|
| `tests/tdd/test_official_alert_standalone_render.py` | BeautifulSoup auf `.verdict/.stufe/.warns/.facts/.mono/.seg/.route-note` — der direkteste Gegenspieler des Umbaus |
| `tests/tdd/test_warn_block_render.py` | Struktur-Fidelity des Warnblocks gegen die Design-Vorlage |
| `tests/tdd/test_official_alert_warn_section.py` | Titel/Gültigkeit/Quelle-Box/Chips — **hier sitzt die ADR-0033-Zusicherung** |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | HTML-Struktur der Nowcast-Vorlage (Zeilenzahl, Marker) |
| `tests/tdd/test_multi_location_onset_alert.py` | einziger **byte-genauer** Vergleich (`EXPECTED_HTML`/`EXPECTED_PLAIN` inline im Modul) |

**🔴 Spec-Korrektur:** AC-11 nennt `test_official_alert_template_render.py` als ADR-0033-Nachweis.
Gemessen: Die ADR-0033-Zusicherung (`free_chips == []`, kein „übrige Strecke frei") steht in
`tests/tdd/test_official_alert_warn_section.py::test_ac11_trip_path_shows_only_affected_segment_chips`
(`:332-361`, zitiert ADR-0033 viermal). Wer nur die in AC-11 genannte Datei grün hält, hat
ADR-0033 **nicht** nachgewiesen. Prüfort ≠ Wirkort.

**🔴 Still deselektierte Dateien** — `pyproject.toml:65`: `addopts = "-q -m 'not email and not
live and not staging'"`. Modulweites `pytestmark` ⇒ die Datei läuft bei einem normalen Lauf
**nie**, ohne Fehlermeldung:

- `tests/tdd/test_952_onset_alert_e2e.py` (`email`)
- `tests/tdd/test_issue_1169_compare_alert_consumer.py` (`email`) — **in A1 als AC-4-Nachweis benannt**
- `tests/tdd/test_alert_sms_location_positions.py` (`live`)
- `tests/tdd/test_issue_1087_trip_official_alerts.py` (`email`)

**Goldens:** Für die Alarm-Mail existiert kein Golden-Verzeichnis. Aber `tests/golden/email/
corsica-vigilance-{html,plain}.txt` sichern byte-genau die **Briefing**-Mail mit eingebettetem
Warn-Badge über die geteilten Funktionen `render_official_alerts_html/plain`. Wer diese geteilten
Helfer anfasst, bricht die Briefing-Goldens mit.

**In `.github/ci_tdd_excludes.txt`** (laufen lokal, werden auf CI ignoriert):
`test_compare_official_alert.py`, `test_issue_1088_official_alert_triggers.py`,
`test_issue_816_alert_deviation.py`, `test_bundle_791_847_844_alerts.py`,
`test_telegram_html_escaping.py`, `test_telegram_kurzstil_{compare_official_alert,trip_alert}.py`.

## Bindende Zusicherungen

| Quelle | Status | Was bindet |
|---|---|---|
| **ADR-0033** `docs/adr/0033-warn-karte-nur-betroffene-segmente.md` | Akzeptiert | Warn-Karte nennt **ausschließlich** den betroffenen Umfang; `free_chips` im Trip-Pfad bleibt `[]`. Änderungen dürfen es nicht wieder befüllen, ohne das ADR abzulösen |
| **Warnmail-Spec** `docs/specs/modules/warnmail_official_alert_display.md` (`status: draft`) | — | AC-1 (keine durchgestrichenen Chips), AC-2 (nur deutscher Gefahren-Typ, in Betreff **und** Körper), AC-4 (beide Quellen nennen), AC-5 (Fußzeile zeigt echte Datenquelle), AC-6 (eingebetteter Block über `render_warn_block(variant="embedded")`) |
| dieselbe Spec, **AC-3** | — | betrifft den **Betreff**, nicht den Körper — die #1744-Spec zieht sie in AC-12 korrekt nur dafür heran |
| `sms_official_alert_tokens.md` | draft | Kurzform der amtlichen Warnung bleibt unberührt (A2 fasst SMS nicht an) |

**ADR-Pflicht:** Die Spec verlangt unter „Risiken" 3 ein neues ADR für den geänderten Aufbau mit
Verweis auf ADR-0033 als weiter bindend. Höchste vergebene Nummer ist ADR-0051 →
**nächste freie: ADR-0052**.

## Dependencies

- **Upstream:** `email/design_tokens.py` (Farb-/Font-Tokens, beide Pfade),
  `email/helpers.py` (`build_origin_footer`, beide), `alert/segments.py` (Ortsformatierung, seit A1
  geteilt), `_HAZARD_DISPLAY`/`hazard_symbols.py` (Gefahrenarten).
- **Downstream:** `notification_service.py` (`:1322` Nowcast-Versand, `:799-927` amtlicher
  Versand, `:1328-1360` eingebetteter Warnblock), `output/channels/email.py` (MIME-Bau und
  Klartext-Fallback), `comparison.py`/`narrow.py` (Telegram-Kompaktform des Ortsvergleichs).

**Nicht geteilt, obwohl äquivalent:** HTML-Escaping — `render.py:709-710` hat ein eigenes `_esc()`
(nur `&<>`), `official_alerts.py:16` nutzt `html.escape` (zusätzlich Anführungszeichen).

## Risiken

1. **Der Validator lehnt die richtige Mail ab.** `class="src"` ist Pflichtklasse; die Spec will
   die Quelle-Box zur Datenzeile machen. Der Wächter muss additiv mitgezogen werden — wie in A1
   bei `_SEGMENT_RE`. Nicht lockern, nur erweitern.
2. **Zwei Validator-Nachweise nötig**, weil beide Renderer-Dateien angefasst werden.
3. **AC-11 zeigt auf die falsche Testdatei** (s.o.) — beim TDD-RED korrigieren.
4. **Briefing-Goldens hängen mit dran**, sobald geteilte Badge-Funktionen berührt werden.
5. **Klartext-Lücke** — ohne Entscheidung bleibt „gleicher Aufbau" für Klartext-Leser unerfüllt.

## Zu entscheiden (PO)

**Bekommt die amtliche Warn-Mail einen echten Klartext-Teil?** Heute wird er aus dem HTML
gestrippt. AC-8 fordert gleiche Bausteinfolge in „beiden Mails" — ob das den Klartext einschließt,
legt die Spec nicht fest.
