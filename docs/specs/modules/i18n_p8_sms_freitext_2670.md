---
entity_id: i18n_p8_sms_freitext_2670
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [i18n, epic-2644, issue-2670, python, docs, model-haiku]
---

# i18n P8: SMS und Premium-SMS (Klartext-Anteile, Token unverändert, Längen-Wächter)

**Issue:** #2670 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt(e) 2, 4 (Token-Wächter), ADR-0104 Nr. 4 und 5

## Approval

- [ ] Approved

## Purpose

SMS und Premium-SMS (Garmin inReach, ADR-0049) bestehen fast nur aus Protokoll-Token (`sms_code`, Zahlenformat, Trennzeichen, Reihenfolge); diese bleiben in beiden Sprachen byte-identisch. Dieses Paket setzt die wenigen verbleibenden Klartext-Anteile der Briefing-SMS in die Nutzersprache und sichert mit Wächtern ab, dass kein Token sich ändert und jede SMS in `en` die Grenze von 160 Zeichen (Alarme 140, Ortsvergleich 153) hält. Wer unterwegs nur eine SMS empfängt, bekommt in beiden Sprachen dieselben Zahlen an derselben Stelle.

## Source

- **File:** `src/output/renderers/sms_trip.py`, `docs/reference/sms_format.md`, `docs/reference/premium_sms_format.md`
- **Identifier:** `SMSTripFormatter.format_sms` (sms_trip.py:547), `SMSTripFormatter.format_alert_sms` (730), `_sms_stage_prefix` (50), Rückfall `stage_name or "Etappe"` (726)

> **Schicht-Hinweis:** Reiner Python-Core (`src/output/renderers/`, `src/output/channels/`). Kein Go-, kein Frontend-Code. **Der SMS-Bestätigungscode der Nummern-Verifikation (#2406) wird in Go versendet** (`internal/handler/sms_verify.go`, `internal/store/user.go`) und gehört zu den Go-Paketen G2/G4, nicht zu diesem Paket.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Trip-SMS (`sms_trip.py`) und Ortsvergleich-SMS (`comparison.py::render_compare_sms`, P4) bleiben getrennte Token-Bauer mit geteiltem Katalog `kurzform_kuerzel`. P8 ändert nichts an der Teilung; der Längen-Wächter prüft beide gemeinsam.
> - **Mandantentrennung:** Reine Funktionen ohne Nutzerdaten-Zugriff und ohne Modul-Zustand. AC-5 beweist, dass zwei Aufrufe nacheinander (`en`, `de`) sich nicht beeinflussen. Auflösung der Sprache (`resolve_user_lang(user_id)` aus dem Auth-Kontext) macht P9b.
> - **Kanäle:** Briefing- und Alarm-Inhalt. Alle vier: SMS (dieses Paket, `sms_trip.py`), Premium-SMS (sendet exakt denselben Text über `PremiumSmsOutput`, AC-7), E-Mail (P2/P3) und Telegram (P7; der Telegram-Kurzstil sendet den SMS-Text unverändert). Kanalgerechte Form: Token bleiben identisch.

### Scope-Klärung (nach Code-Prüfung am 2026-10-30)

Die Issue-Skizze nennt Alarm-Präfixe, „kein Empfang“, den Bestätigungscode-Text und Antwort-Kurztexte. Die Code-Prüfung zeigt, wo diese Texte tatsächlich liegen:

| Text | Liegt in | Zuständig |
|---|---|---|
| Alarm-Präfix `Erg ` (Nachtrag), Tageskürzel, Alarm-SMS | `src/output/renderers/alert/render.py` | P5 (#2667) |
| Ortsvergleich-SMS (`Vergleich 29.10.:`, `+N Orte`) | `src/output/renderers/comparison.py` | P4 (#2666) |
| Bestätigungscode-SMS (#2406) | `internal/handler/sms_verify.go` | Go-Pakete (G2/G4) |
| Antwort-Kurztexte auf Befehle (`HILFE`, `KUERZEL`, `CODES`) | `src/services/trip_command_processor.py` | P10 (#2673) |
| Kanal-Sperrgründe (`premium_sms.py::check_reply_address`, `seven_io_base.py`) | Betreiber-/Ergebnistexte mit `reason_code` | P9a (#2671, `send_outcomes.py`) |
| Kurzzusammenfassung-Prosa (`mäßiger Regen`, `Gewitter möglich`) | `src/output/renderers/compact_summary.py` | P3 (#2665) |
| Etappen-Rückfallwort der Trip-SMS | `src/output/renderers/sms_trip.py:726` | **dieses Paket** |

`src/output/channels/sms.py` enthält keine Nutzertexte (verifiziert). Dieses Paket ist deshalb klein: Es setzt das eine Klartext-Wort der Trip-SMS und liefert die Wächter und die Doku, die für alle SMS-Erzeuger gelten.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `src/output/renderers/sms_trip.py` | MODIFY | `format_sms(..., *, lang: Lang = "de")` und `format_alert_sms(..., *, lang: Lang = "de")`; Rückfallwort `"Etappe"` (Zeile 726) über `t("sms.etappe.rueckfall", lang)`; `_sms_stage_prefix` bekommt den Rückfall als Parameter (die Regex `_ETAPPE_RE` und `E{N}` bleiben) |
| `src/output/renderers/trip_report.py` | MODIFY | Nur der Aufruf `SMSTripFormatter().format_sms(...)` (Zeile ~464) reicht `lang=lang` weiter (eine Zeile; `lang` existiert dort seit P2/P3) |
| `src/output/channels/premium_sms.py`, `src/output/channels/seven_io_base.py` | MODIFY (nur Kommentare) | Sperr- und Fehlertexte (`check_reply_address`, `_block(...)`, `OutputError`) bleiben unverändert; Zeilen mit Umlaut/Signalwort erhalten den Kommentar `# i18n-log` |
| `src/output/channels/sms.py` | unverändert | geprüft: keine Nutzertexte |
| `src/i18n/messages/de/sms.json`, `src/i18n/messages/en/sms.json` | MODIFY | Schlüssel `sms.*` (nur diese Bereichsdateien anfassen) |
| `docs/reference/sms_format.md` | MODIFY | Neuer Abschnitt „## 13. Sprache: nur Klartext-Anteile“ |
| `docs/reference/premium_sms_format.md` | MODIFY | Neuer Abschnitt „## 6. Sprache: nur Klartext-Anteile“ |
| `tests/golden/sms/` (vorhandene `*.txt`) | unverändert | bleiben der `de`-Golden; neue Fälle in `tests/golden/sms_sprachen/` |
| `tests/golden/sms_sprachen/etappe_rueckfall.de.txt`, `.en.txt` | CREATE | Golden `de` (VOR der Umstellung erzeugen) und Referenz `en` für Trip ohne Etappenname |
| `tests/test_sms_sprachen_laenge_und_token.py` | CREATE | Längen- und Token-Wächter über alle SMS-Erzeuger in beiden Sprachen |
| `tests/test_sms_katalog_laenge.py` | CREATE | Katalog-Wächter `# doc-compliance-test`: jeder Schlüssel mit Namenssegment `sms` hat `len(en) <= len(de)` |
| `tests/test_premium_sms_text_unveraendert.py` | CREATE | Premium-SMS sendet denselben Text wie die SMS |

## Estimated Scope

- **LoC:** ca. 25 Code (sms_trip.py ~15, trip_report.py 1, Kommentare ~10); ohne Katalogdaten, Doku und Tests
- **Files:** 4 Code-Dateien, 2 Katalogdateien, 2 Doku-Dateien plus Tests
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2662 P1 | Paket | `t`, Katalog `sms`, Token-Wächter `tests/test_metric_tokens_eingefroren.py` mit `tests/fixtures/metric_tokens_frozen.json` |
| #2666 P4 | Paket | `render_compare_sms(..., lang)` (Ortsvergleich-SMS, `vergleich.sms.*`) |
| #2667 P5 | Paket | `render_sms(..., lang)` (Alarm-SMS, `alarm.sms.*`) |
| #2664 P2 / #2665 P3 | Pakete | `trip_report.py` reicht `lang` an die Renderer; `compact_summary.py` |
| #2672 P9b (danach) | Paket | reicht `lang` an `trip_report` durch |
| `fold_ascii`, `_ETAPPE_RE` | Funktion/Konstante | ASCII-Faltung und Etappen-Erkennung des Präfixes (bleiben) |
| ADR-0104, ADR-0042, ADR-0049 | ADR | Sprache am Nutzer; Token sind Klasse 1; Premium-SMS |

## Implementation Details

**Katalog-Namensraum:** `sms` (`src/i18n/messages/{de,en}/sms.json`). Nur diese beiden Dateien anfassen. das im Glossar verbotene Produktwort ist untersagt.

**Schlüssel (de wörtlich wie heute, en laut Glossar):**

| Schlüssel | de | en | Stelle |
|---|---|---|---|
| `sms.etappe.rueckfall` | `Etappe` | `Stage` | sms_trip.py:726 |

Weitere SMS-Schlüssel gehören den Paketen, die den Text erzeugen (`alarm.sms.*` in P5, `vergleich.sms.*` in P4). **Regel für alle Schlüssel mit Namenssegment `sms`:** der englische Text ist nicht länger als der deutsche (Platzform). Beispiele, die der Wächter AC-4 prüft: `alarm.sms.nachtrag_praefix` (`Erg ` / `Add `), `vergleich.sms.orte_ueberlauf` (` +{n} Orte` / ` +{n} locs`).

**Beispiel-Umstellung (sms_trip.py:722-727, Rückfallwort), vorher:**

```
stage_name=_sms_stage_prefix(stage_name or "Etappe"),
```

**nachher:**

```
stage_name=_sms_stage_prefix(stage_name or t("sms.etappe.rueckfall", lang)),
```

`_sms_stage_prefix` selbst bleibt: `Etappe N`-Namen werden weiter zu `E{N}` (Kürzel, kein Katalog), Nutzernamen bleiben unverändert (`fold_ascii(name)[:10]`).

**Doku-Abschnitte (Inhalt):**

- `sms_format.md` „## 13. Sprache: nur Klartext-Anteile“: Die Sprache folgt der Konto-Sprache (ADR-0104). Token (`sms_code`, Zahlenformat, Trennzeichen, Reihenfolge, Stufenbuchstaben) sind ADR-0042 Klasse 1 und bleiben in beiden Sprachen byte-identisch. Klartext-Anteile sind nur das Etappen-Rückfallwort, der Nachtrags-Präfix der Alarm-SMS (`Erg `/`Add `), die Ortsvergleich-Köpfe (`Vergleich`/`Compare`) und der Orts-Überlauf (`Orte`/`locs`). Englische Klartexte sind nie länger als die deutschen; die Grenzen (Briefing 160, Alarm 140, Ortsvergleich 153) gelten in beiden Sprachen und werden von `tests/test_sms_sprachen_laenge_und_token.py` geprüft. Wochentagskürzel in Alarm-Token folgen der Nutzersprache (`Do15`/`Thu15`, siehe P5).
- `premium_sms_format.md` „## 6. Sprache: nur Klartext-Anteile“: Premium-SMS sendet denselben Text wie die SMS; die Befehlswörter des Rückkanals sind Platzform (englische Kurzbefehle bleiben, ADR-0104 Nr. 5); die Antworttexte auf Befehle folgen der Nutzersprache (P10).

**Wächter `tests/test_sms_sprachen_laenge_und_token.py`:** Erzeugt mit der deterministischen Fixture (feste Zeit `2026-10-29T06:00+02:00`, Nutzer `golden-de`) je Sprache: Trip-Briefing-SMS (alle fünf vorhandenen Golden-Fälle aus `tests/golden/sms/`), Abweichungs-Alarm, Regen-Alarm mit Tagesversatz, Ortsvergleich mit zwölf Orten. Prüft: (a) `len(text) <= Limit` je Erzeuger und Sprache (160, 140, 140, 153 laut `CHANNEL_LIMITS["sms"]["max_chars"]`), (b) die Token-Folge der Trip-SMS ist in `en` und `de` byte-identisch, (c) bei Alarm- und Ortsvergleich-SMS unterscheiden sich `de` und `en` nur in den Katalog-Klartextteilen und im Wochentagskürzel.

**Token-Wächter:** Der Wächter aus P1 (`tests/test_metric_tokens_eingefroren.py`) bleibt grün; `sms_code`, `compact_label`, `col_label` und `kurzform_kuerzel` werden nicht angefasst.

**Allowlist-Eintrag, der entfällt:** In `tests/fixtures/i18n_python_allowlist.json` (Ratsche P11) den Präfix `src/output/renderers/sms_trip.py` entfernen (vorher `Glob tests/fixtures/i18n_python_allowlist.json`; existiert sie noch nicht, holt P11 den Schritt nach). `premium_sms.py` und `seven_io_base.py` liegen nicht im Prüfumfang der Ratsche (`src/output/**` schon): ihre Texte tragen `# i18n-log`.

**Pflicht für den Developer-Agenten:** (1) RED-Tests der ACs grün, (2) deutsche Golden-Ausgabe byte-gleich, (3) Allowlist-Eintrag entfernen, (4) Paritäts- und Ratschen-Test grün, (5) keine Änderung an `col_label`/`compact_label`/`sms_code`/Kürzeln. Nicht tun: andere Bereichsdateien ändern, Schlüssel umbenennen, deutsche Texte „verbessern“, neue Abhängigkeiten, Sperrgrund-Texte übersetzen.

## Expected Behavior

- **Input:** Trip-Berichtsdaten, Etappenname (optional), `lang`.
- **Output:** SMS-Text. Token-Folge in `de` und `en` byte-identisch; ohne Etappenname lautet das Präfix `Etappe` bzw. `Stage`; Länge ≤ 160 Zeichen (Alarm 140, Ortsvergleich 153).
- **Side effects:** Keine. Die Transporte (`SMSOutput`, `PremiumSmsOutput`) übersetzen nichts.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Bericht mit Etappenname `Etappe 1: Calenzana` und Sprache `en` / When die Trip-SMS gerendert wird / Then ist der Text byte-identisch zur deutschen SMS desselben Berichts (nur Token, `E1` bleibt) und höchstens 160 Zeichen lang.
  - Test: tests/test_sms_sprachen_laenge_und_token.py — Byte-Vergleich `de` gegen `en` für alle fünf Fixtures aus `tests/golden/sms/`.

- **AC-2:** Given ein Trip-Bericht ohne Etappenname und Sprache `en` / When die Trip-SMS gerendert wird / Then beginnt sie mit `Stage` statt `Etappe`, der Rest der Token-Folge ist identisch zur deutschen SMS; mit `de` bleibt die Ausgabe byte-gleich zur bisherigen.
  - Test: tests/test_sms_sprachen_laenge_und_token.py — Fall `etappe_rueckfall`: `de` gegen die vorab eingecheckte `*.de.txt`, `en` gegen `t("sms.etappe.rueckfall", "en")` plus Rest-Gleichheit.

- **AC-3:** Given die eingefrorene Token-Fixture aus P1 / When P8 gemergt ist / Then bleibt der Wächter grün (kein `sms_code`, `compact_label`, `col_label` verändert), und eine Mutation eines `sms_code` lässt ihn rot werden.
  - Test: tests/test_metric_tokens_eingefroren.py (aus P1) — unverändert grün; die Mutation prüft der Adversary.

- **AC-4:** Given alle Katalogschlüssel mit Namenssegment `sms` (`sms.*`, `alarm.sms.*`, `vergleich.sms.*`) / When ihre deutschen und englischen Texte verglichen werden / Then ist jeder englische Text höchstens so lang wie der deutsche.
  - Test: tests/test_sms_katalog_laenge.py — `# doc-compliance-test` (Katalog-Wächter, Paritätstest-Ausnahme); zählt Zeichen je Schlüssel über alle Bereichsdateien.

- **AC-5:** Given Abweichungs-Alarm, Regen-Alarm mit Tagesversatz und Ortsvergleich mit zwölf Orten in `en` und `de` / When die SMS gerendert werden / Then hält jede Ausgabe ihre Grenze (140/140/153) und unterscheidet sich zwischen den Sprachen nur in Katalog-Klartext und Wochentagskürzel.
  - Test: tests/test_sms_sprachen_laenge_und_token.py — Grenzprüfung und Differenz-Analyse nach Entfernen der Katalogtexte.

- **AC-6:** Given zwei aufeinanderfolgende Render-Aufrufe für zwei Nutzer, erst `en`, dann `de` / When die Ergebnisse verglichen werden / Then ist das zweite Ergebnis byte-gleich zur Golden-`de`-Ausgabe (kein Zustand zwischen Nutzern).
  - Test: tests/test_sms_sprachen_laenge_und_token.py — Reihenfolge `en`, `de`, `en`.

- **AC-7:** Given ein Nutzer mit Sprache `en` und Premium-SMS als Versandkanal / When der Ortsvergleich-SMS-Text über die Sink-Naht `premium_sms_sink` versendet wird / Then erhält die Naht exakt den Text, den `render_compare_sms(..., lang="en")` geliefert hat (keine Ergänzung, keine Übersetzung im Transport).
  - Test: tests/test_premium_sms_text_unveraendert.py — Sink-Mitschnitt gegen den gerenderten Text (echte Funktionen, kein Spiegel-Mock).

## Known Limitations

- Annahme (Scope-Klärung oben): Die in der Issue genannten Texte (Alarm-Präfixe, Bestätigungscode, Antwort-Kurztexte, Sperrgründe) liegen in P5, P4, G2/G4, P10 und P9a; P8 dupliziert sie nicht. Fehlt dort ein Schlüssel, gilt der Wächter AC-4 für alle Pakete.
- Annahme: Etappennamen sind Nutzertext und bleiben unverändert; nur das Rückfallwort ohne Namen folgt der Sprache.
- Annahme: `compact_summary.py` ist in P3 abgedeckt und hat in P8 keinen Eingriff; fehlt dort nach P3 ein `lang`, ist das ein Finding für P3, nicht für P8.
- Sperr- und Fehlertexte der Kanäle bleiben Betreiber-/Ergebnistexte (deutsch, `# i18n-log`); ihre Nutzersicht regelt `send_outcomes.py` in P9a.
- Bis P9b sendet das System die SMS weiter deutsch (keine Durchreichung von `lang`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (zusätzlich ADR-0042 für Token und Platzform, ADR-0049 für Premium-SMS)
- **Rationale:** Token sind Protokoll und bleiben byte-identisch; nur das wenige Klartext-Wort folgt der Nutzersprache, und Wächter sichern Länge und Token in beiden Sprachen.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
