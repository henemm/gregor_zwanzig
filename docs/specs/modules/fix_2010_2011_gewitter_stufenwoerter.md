---
entity_id: fix_2010_2011_gewitter_stufenwoerter
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [gewitter, telegram, mail, ampel, renderer, issue-2010, issue-2011, issue-1480]
---

# Gewitter-Stufenwörter und -Ampelfarbe aus der kanonischen Quelle speisen (#2010 + #2011)

## Approval

- [ ] Approved

## Purpose

Zwei Kanäle bauen die Gewitter-Stufenskala (`ThunderLevel`: NONE/LOW/MED/HIGH) lokal statt
aus der kanonischen Quelle `src/output/metric_format.py::THUNDER_LABEL_DE` /
`thunder_ampel_band()` zu lesen: Telegram zeigt „mäßig"/„keins" statt „mittel"/„kein"
(#2010), und die Briefing-Mail-Ampelfarbe berechnet ihre eigene Stufen-Wort-Kette, obwohl
ihr eigener Docstring behauptet, sie nutze die kanonische Zuordnung (#2011). Beide Stellen
sind bereits **namentlich als Altlasten des #1480-Wächters erfasst** — diese Arbeit saniert
genau die sechs dort verzeichneten Fundstellen.

## Source

- **File:** `src/services/trip_command_processor.py`, `src/output/renderers/email/html.py`
- **Identifier:** `_THUNDER_LABEL`, `_thunder_fmt()` (Karten `_MAP_EMOJI`/`_MAP_PLAIN`),
  `_handle_hours_drilldown()`, `_thunder_risk_level()`

**Schicht:** ausschließlich Python-Core (`src/services/`, `src/output/renderers/`). Kein
Go, kein Frontend.

## Estimated Scope

- **LoC:** ~+25/−20
- **Files:** 2 Produktivdateien geändert, 3 Testdateien (2 mit Wortkorrektur, 1
  Wächter-Bereinigung)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `THUNDER_LABEL_DE` (`metric_format.py:283-288`) | kanonische Quelle | liefert die vier deutschen Wörter kein/leicht/mittel/hoch — Ziel der Ableitung für `_THUNDER_LABEL`/`_MAP_PLAIN` |
| `thunder_ampel_band()` (`metric_format.py:302-312`) | kanonische Quelle | liefert green/yellow/orange/red je Stufe — Ziel des tatsächlichen Aufrufs in `_thunder_risk_level()` |
| `docs/specs/modules/thunder_scale_guard.md` | bindender Mechanismus | definiert Regel A/B/C und die **dreistufige Duldung** (Whitelist / benannte Altlasten-Basislinie / Marker-Kommentar) — diese Arbeit bewegt zwei ALTLASTEN-Fundstellen von Stufe 2 auf „saniert" bzw. Stufe 3 |
| `tests/tdd/test_thunder_scale_local_copy_guard.py::ALTLASTEN` | Wächter-Basislinie | muss um exakt die sechs hier sanierten Einträge schrumpfen, sonst schlägt `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` an |
| `src/output/renderers/narrow.py`, `src/output/renderers/email/helpers.py` | Vorbild | importieren `THUNDER_LABEL_DE` bereits direkt statt eine eigene Zuordnung zu pflegen — Bauform, an die #2010/#2011 angeglichen werden |
| `_row_risk()` (`email/html.py:207-224`) | Downstream-Aufrufer | erwartet von `_thunder_risk_level()` weiterhin exakt das Vokabular `risk`/`watch`/`yellow`/`ok` — Rückgabewerte-Menge darf sich nicht ändern |
| zweiter Aufrufer bei `elif key == "thunder"` (`email/html.py:855-862`) | Downstream-Aufrufer | nutzt `_thunder_risk_level()` nur noch für den numerischen Legacy-Rohwert; String-/Enum-Rohwerte laufen bereits über `thunder_ampel_band()` direkt |
| `tests/tdd/test_command_reply_channel_emoji.py:157,190`, `tests/tdd/test_issue_654_telegram_thunder_drilldown.py:185` | Bestandsschutz | prüfen heute die (falschen) Wörter „mäßig"/„keins" — werden im selben Commit auf „mittel"/„kein" korrigiert |
| `tests/tdd/test_thunder_risk_dot_and_tint.py`, `test_row_risk_thunder_pair_escalation.py` | Bestandsschutz | prüfen `_thunder_risk_level`/`_row_risk`-Verhalten (Vokabular `risk/watch/yellow`) — darf durch #2011 nicht brechen |

## Implementation Details

```
#2010 — trip_command_processor.py:

_THUNDER_LABEL = {level.name: label for level, label in THUNDER_LABEL_DE.items()}
  -- ersetzt die bisherige Wert-Kopie (Zeile 139-146). Jede Wert-fuer-Wert-
     Handkorrektur waere derselbe Kopierfehler, den #2010 gerade behebt.

_thunder_fmt(): _MAP_PLAIN wird aus THUNDER_LABEL_DE abgeleitet (wie oben).
  _MAP_EMOJI kombiniert weiterhin einen hartcodierten Emoji-Praefix
  (⚪/🟢/🟡/🔴 -- kein Teil von THUNDER_LABEL_DE) mit dem abgeleiteten
  Wort-Suffix, z.B. {level.name: f"{emoji} {label}" fuer level,label in
  THUNDER_LABEL_DE.items(), emoji aus einer separaten festen Emoji-Zuordnung}.

_handle_hours_drilldown() (~Zeile 790-817): das if/elif mit eigenem
  "mäßig"-Literal verschwindet; die Stundenzeile liest dieselbe abgeleitete
  Karte (Wort ueber _MAP_PLAIN-Aequivalent, Symbol ueber die separate
  Emoji-Zuordnung aus _thunder_fmt). Der NONE-Sonderfall "—" bei fehlendem
  Wert bleibt ein eigener Zweig (kein Wort fuer "keine Daten").

Die drei reinen Lesestellen _THUNDER_LABEL.get(...) (~Zeilen 1028/1095/1155)
bleiben unveraendert, solange das Dict selbst korrekt gespeist wird.

#2011 — email/html.py:

_thunder_risk_level(): der String-Zweig (isinstance(thunder, str)) ruft
  thunder_ampel_band() tatsaechlich auf (loest den Docstring-Widerspruch)
  und uebersetzt dessen Vokabular explizit:
    {"green": "ok", "yellow": "yellow", "orange": "watch", "red": "risk"}
  NONE/green -> "ok" (bisher None) -- siehe Known Limitations.

  Der Zahlen-Fallback-Zweig (num > 20 -> "risk", num > 0 -> "watch") bleibt
  UNVERAENDERT bestehen -- er verarbeitet einen rohen Zahlenwert, keine
  diskrete Stufe, und ist deshalb kein Fall fuer thunder_ampel_band().
  Er bekommt einen Marker-Kommentar `# gz-thunder-scale: <Begruendung>`
  (Duldungsstufe 3 des #1480-Waechters, s. thunder_scale_guard.md) und
  wechselt damit von "benannte Altlast" auf "begruendete Duldung" --
  das ist der Mechanismus, ueber den Regel C an dieser Stelle sanktionsfrei
  bleibt, OHNE die Zahlen-Schwellen selbst zu aendern.

ALTLASTEN-Bereinigung (test_thunder_scale_local_copy_guard.py):
  Die sechs Eintraege zu html.py::_thunder_risk_level (Regel B, Regel C)
  und trip_command_processor.py::_THUNDER_LABEL / _MAP_EMOJI / _MAP_PLAIN /
  _handle_hours_drilldown werden aus ALTLASTEN gestrichen. Die drei
  uebrigen Eintraege (day_window.py, zwei trip_report_scheduler.py-Symbole)
  bleiben unangetastet.
```

## Expected Behavior

- **Input:** eine Telegram-Kommando-Antwort (Zusammenfassung, Emoji- und Klartext-Kanal,
  Stundendrilldown) bzw. eine gerenderte Trip-Briefing-HTML-Mail, jeweils mit
  Gewitterstufen aus der vollen Menge NONE/LOW/MED/HIGH.
- **Output:** Telegram zeigt in jedem Pfad die Wörter „kein"/„leicht"/„mittel"/„hoch" (nie
  „keins"/„mäßig"); die Mail-Ampelfarbe für Gewitter stimmt mit `thunder_ampel_band()`
  überein (übersetzt auf das bestehende Zeilen-Risiko-Vokabular). Der #1480-Wächter bleibt
  grün und ist um sechs Einträge geschrumpft.
- **Side effects:** keine — reine Formatierungs-/Ableitungsänderung, `ThunderLevel`-Werte
  selbst werden nicht verändert.

## Acceptance Criteria

- **AC-1 (#2010, Klartext-Pfad zeigt die vier korrekten Wörter):** Given die vier
  Gewitterstufen NONE/LOW/MED/HIGH / When der Telegram-Klartext-Konsument (kein
  Emoji-Modus, z.B. E-Mail-Kanal-Antwort auf `dd_thunder_today`) für jede Stufe gerendert
  wird / Then zeigt er genau „kein"/„leicht"/„mittel"/„hoch" — nirgends „keins" oder
  „mäßig".
  - Test: bestehenden bzw. erweiterten Testfall für alle vier Stufen durchlaufen lassen,
    Wortgleichheit prüfen und explizit die Abwesenheit von „keins"/„mäßig" im Antworttext
    nachweisen.

- **AC-2 (#2010, Emoji-Pfad behält Symbol UND korrigiert das Wort):** Given dieselben vier
  Stufen / When derselbe Konsument im Emoji-Modus (Telegram-Kanal) rendert / Then enthält
  die Antwort weiterhin das passende Kreis-Emoji (⚪/🟢/🟡/🔴) UND das korrigierte Wort
  („mittel" statt „mäßig" bei MED), beides gemeinsam in derselben Zeile.
  - Test: Emoji-Regex weiterhin erfüllt UND Wortsuche auf „mittel" (nicht „mäßig") in
    derselben Antwort.

- **AC-3 (#2010, Stundendrilldown ist ein unabhängiger zweiter Pfad):** Given eine
  Stundenübersicht-Anfrage (`dd_hours_today`/`dd_hours_tomorrow`) mit mindestens einer
  Stunde der Stufe MED / When `_handle_hours_drilldown` die Stundenzeilen baut / Then
  enthält die Zeile dieser Stunde „mittel" (Klartext) bzw. das gelb/orange Kreis-Emoji
  (Emoji-Modus) — nicht „mäßig". Dieser Nachweis ist unabhängig von AC-1/AC-2, weil
  `_handle_hours_drilldown` bislang eine eigene if/elif-Verzweigung mit eigenem
  „mäßig"-Literal besaß statt die Karte aus AC-1/AC-2 zu lesen.
  - Test: Stundendrilldown mit einer MED-Stunde rendern, Zeilentext auf „mittel"/korrektes
    Emoji prüfen, Abwesenheit von „mäßig" nachweisen.

- **AC-4 (#2010, Ableitung statt Wert-Kopie — Regressionsschutz):** Given ein temporär
  veränderter Wert für `THUNDER_LABEL_DE[ThunderLevel.MED]` (Test-lokal gesetzt, nicht die
  Produktionsquelle dauerhaft verändert) / When eine Telegram-Ausgabe für MED gerendert
  wird / Then folgt das angezeigte Wort dem veränderten Quellwert. Das beweist, dass
  `_THUNDER_LABEL`/`_MAP_PLAIN` tatsächlich aus `THUNDER_LABEL_DE` **abgeleitet** sind,
  nicht bloß einmalig wortgleich kopiert wurden.
  - Test: `THUNDER_LABEL_DE[ThunderLevel.MED]` im Testkontext überschreiben (z.B. via
    `monkeypatch`), Telegram-Rendering für MED erneut aufrufen, geänderten Wert im
    Ergebnis nachweisen.

- **AC-5 (#2011, Ampelübersetzung für alle vier Stufen abgeleitet statt kopiert):** Given
  die vier Gewitterstufen als String-/Enum-Rohwert in einer Stundentabellen-Zeile
  (`r["thunder"]`) / When `_thunder_risk_level()` bzw. `_row_risk()` für jede Stufe
  berechnet wird / Then liefert es „yellow" für LOW, „watch" für MED, „risk" für HIGH
  (unverändert sichtbares Vokabular) — UND ein temporär veränderter Eintrag in
  `_THUNDER_AMPEL_BAND[ThunderLevel.MED]` (Test-lokal) ändert das Ergebnis für MED
  entsprechend, als Beleg dafür, dass die Übersetzung jetzt tatsächlich über
  `thunder_ampel_band()` läuft statt über eine eigene Wort-Kette.
  - Test: alle vier Stufen durch `_thunder_risk_level()` schicken, Vokabular-Gleichheit
    zum bisherigen Verhalten prüfen; zusätzlich `_THUNDER_AMPEL_BAND`-Eintrag für MED
    testlokal überschreiben und geänderte Ausgabe nachweisen.

- **AC-6 (#2011, NONE liefert jetzt „ok" statt `None` — verhaltensneutral abgesichert):**
  Given die Gewitterstufe NONE (als String „NONE" und als `ThunderLevel.NONE`) / When
  `_thunder_risk_level()` direkt aufgerufen wird / Then liefert die Funktion `"ok"` (nicht
  mehr `None`) — UND ein zweiter Test belegt, dass sowohl `_row_risk()` als auch die
  Zell-Tönungs-Zuordnung bei `elif key == "thunder"` (html.py ~855-862) für `"ok"` exakt
  dasselbe sichtbare Ergebnis liefern wie zuvor für `None` (keine Zeile eskaliert
  fälschlich, keine Zelle bekommt einen Hintergrund). Die Änderung ist an der Wirkung
  nicht beobachtbar, nur intern.
  - Test: `_thunder_risk_level("NONE")` und `_thunder_risk_level(ThunderLevel.NONE)` auf
    `"ok"` prüfen; zusätzlich eine vollständig gerenderte Zeile mit NONE-Gewitter vor und
    nach dem Fix auf identische Zell-Tönung/Zeilen-Risiko vergleichen.

- **AC-7 (#2011, Zahlen-Fallback bleibt funktionsfähig — Regressionsschutz gegen
  versehentliches Entfernen):** Given eine Tabellenzeile, deren `thunder`-Rohwert ein
  reiner Zahlenwert ist (kein String/Enum, älterer Legacy-Datenpfad, #1425) / When die
  HTML-Mail-Zell-Tönung bei der `elif key == "thunder"`-Verzweigung (html.py ~855-862)
  für diesen numerischen Rohwert berechnet wird / Then bekommt die Zelle weiterhin einen
  Warnhintergrund (rot bei Werten > 20, orange bei Werten > 0) statt gar keinen
  Hintergrund — der Fallback-Zweig wurde nicht entfernt.
  - Test: numerische `thunder`-Rohwerte (z.B. 25.0 und 5.0) durch die Zell-Tönungslogik
    schicken, roten bzw. orangen Hintergrund nachweisen; Gegenprobe mit 0 liefert keinen
    Hintergrund.

- **AC-8 (ALTLASTEN-Wächter schrumpft um genau die sechs sanierten Einträge):** Given die
  sechs benannten Altlasten-Einträge zu `html.py::_thunder_risk_level` (Regel B, Regel C)
  und `trip_command_processor.py::_THUNDER_LABEL`/`_MAP_EMOJI`/`_MAP_PLAIN`/
  `_handle_hours_drilldown` in `ALTLASTEN` / When der #1480-Wächter
  (`tests/tdd/test_thunder_scale_local_copy_guard.py`) nach dem Fix läuft / Then sind
  diese sechs Einträge aus `ALTLASTEN` entfernt, `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag`
  bleibt grün, und die drei ursprünglich nicht betroffenen Einträge (`day_window.py`,
  zwei `trip_report_scheduler.py`-Symbole) bleiben unverändert in der Liste.
  - Test: struktureller Nachweis über den bestehenden Wächter-Test selbst (legitimer
    Nachweis für diese eine Bereinigung, keine neu erfundene String-Prüfung) — Länge und
    Inhalt von `ALTLASTEN` vor/nach dem Fix vergleichen (sechs `(Datei, Symbol, Regel)`-
    Tripel fehlen, drei bleiben), plus vollständiger, grüner Testlauf des gesamten
    Wächter-Moduls.

- **AC-9 (Regel-C-Fundstelle wechselt von Altlast auf begründete Marker-Duldung):** Given
  der `# gz-thunder-scale: <Begründung>`-Marker-Mechanismus (Duldungsstufe 3 des
  #1480-Wächters, `docs/specs/modules/thunder_scale_guard.md`) / When der numerische
  Fallback-Zweig in `_thunder_risk_level()` nach dem Fix weiterhin sein eigenes
  `num > 20`/`num > 0`-Schwellenpaar mit eigenen Rückgabe-Literalen führt (bewusst NICHT
  auf `thunder_ampel_band()` umgestellt, da er einen rohen Zahlenwert statt einer
  diskreten Stufe erhält) / Then trägt die Fundstelle einen Marker-Kommentar mit
  mindestens 15 sinnvollen Zeichen Begründung, und der Backend-Wächter meldet dort keinen
  neuen, ungedeckten Regel-C-Fund mehr.
  - Test: voller Wächter-Testlauf bleibt grün mit dem numerischen Fallback-Zweig
    unverändert im Code vorhanden (Positivkontrolle: ohne Marker-Kommentar meldet der
    Wächter an dieser Stelle einen Fund — Nachweis, dass der Marker tatsächlich wirkt und
    nicht nur zufällig grün ist).

## Known Limitations

- **NONE/green → „ok" ist eine bewusste, verhaltensneutrale Vokabular-Erweiterung.** Vor
  dieser Arbeit lieferte `_thunder_risk_level(NONE)` `None`; danach `"ok"`. Beide Werte
  wirken an jeder heute existierenden Prüfstelle (`_row_risk`, Zell-Tönungs-`.get(...)`)
  identisch wirkungslos — geprüft in AC-6. Ein künftiger Refactor, der `None` und `"ok"`
  irgendwo unterschiedlich behandelt, würde diesen Unterschied sonst versehentlich
  sichtbar machen; AC-6 ist die Absicherung dagegen.
- **`ThunderLevel` erbt von `str`.** Tests decken sowohl Enum-Instanzen
  (`ThunderLevel.MED`) als auch reine String-Werte (`"MED"`) ab, wo beide Formen in der
  Praxis vorkommen (Roundtrip über Persistenz/API liefert teils reine Strings).
- **Der Zahlen-Fallback-Zweig in `_thunder_risk_level()` wird NICHT auf
  `thunder_ampel_band()` umgestellt.** Er verarbeitet einen rohen Zahlenwert (kein
  `ThunderLevel`), für den es keine sinnvolle Stufen-Ableitung gibt, ohne selbst eine
  Schwellen-Klassifikation vorzunehmen. Er bleibt bestehen und wird stattdessen über den
  Marker-Kommentar-Mechanismus (AC-9) als begründete Duldung eingestuft statt als
  benannte Altlast getrackt. Eine Vereinheitlichung dieser dual gearteten Funktion (Stufe
  vs. Zahl) ist explizit außerhalb des Scopes dieser Arbeit.
- **Ortsvergleich, `narrow.py`, `day_window.py`, `trip_report_scheduler.py` sind nicht
  Teil dieser Arbeit** — weder betroffen noch verändert (siehe Context-Dokument).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Arbeit bewegt sich innerhalb ADR-0025 (Gewitter-Skala lebt zentral
  in `metric_format.py`, gilt für alle Briefing-Kanäle) und saniert zwei bereits durch den
  #1480-Wächter (`thunder_scale_guard.md`) benannte, bekannte Kopien. Kein neuer
  Architektur-Entscheidungsraum.

## Changelog

- 2026-08-22: Initial spec created (Issues #2010, #2011).
