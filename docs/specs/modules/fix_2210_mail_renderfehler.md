---
entity_id: fix_2210_mail_renderfehler
type: module
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
tags: [rendering, email, i18n, temperatur, bugfix]
---

# Fix #2210: Vier Renderfehler in zugestellten Mails (Wochentag, negative Temperaturspanne, toter Mobil-Code, leere Stundentabelle)

## Approval

- [ ] Approved

## Purpose

Sammel-Issue #2210 (aus der Triage #1199) bündelt vier kleine, voneinander unabhängige
Renderfehler in den Mails. Drei davon sind für den Empfänger sichtbar, einer ist Altlast:

1. **C2-52 — englischer Wochentag:** Die Klartext-Kopfzeile der Vergleichs-Mail schreibt im
   deutschen Zweig `strftime('%A, %d.%m.%Y')`. Das hängt von der Systemsprache des Servers ab und
   liefert dort „Monday, 02.11.2026" statt „Montag, 02.11.2026". Der englische Zweig nutzt
   bereits die sprachfesten Helfer `fmt_weekday`/`fmt_date_numeric`.
2. **C2-79 — negative Temperaturspanne:** `format_temp_span` baut `lo–hi°C`. Bei negativen Werten
   entsteht `-12–-4°C`: Gedankenstrich und Minuszeichen laufen zusammen, die Spanne ist schwer
   lesbar und missverständlich.
3. **C3-35 — toter Code:** `_render_mobile_hour_list` hat keinen einzigen Aufrufer (Grep über
   `src/` und `tests/` findet nur die Definition). Mehrere Specs nennen sie bereits „toter Code".
   Die Funktion enthält eine eigene, nie ausgelieferte Gewitter-Darstellung und lädt zu
   Fehlanalysen ein (siehe #1794, #1927). Sie wird zurückgebaut statt „repariert".
4. **C3-41 — leeres Gerüst bei abgewählten Metriken:** Sind alle Metriken eines Zeitraums
   abgewählt, ist `allowed_col_keys` eine leere Menge. `_render_mobile_compact_rows` bricht dann
   korrekt mit `""` ab, `_render_html_table` (Desktop-Pfad) zeichnet trotzdem ein Gerüst mit den
   Spalten „Time" und „Risk". „Abgewählt heißt abgewählt" (#1405 Scheibe 3) gilt damit nur auf
   dem Handy, nicht am Desktop.

Die Korrekturen sind klein und eigenständig; sie werden in einem Workflow geliefert, haben aber
je eigene Akzeptanzkriterien.

## Source

Alle Pfade Python-Core (`src/output/...`, `src/i18n/...`); kein Go- und kein Frontend-Code.
Fundstellen am Stand `origin/main` 906731153 geprüft:

- **File:** `src/output/renderers/comparison.py`
  - **Identifier:** Klartext-Renderer der Vergleichs-Mail, Datumszeile (Z.224-227,
    `target_date.strftime('%A, %d.%m.%Y')` im `de`-Zweig; `en`-Zweig nutzt schon
    `fmt_weekday(..., 'en', kurz=False)` und `fmt_date_numeric(..., 'en')`)
- **File:** `src/i18n/format.py`
  - **Identifier:** `fmt_weekday` (Z.37), `fmt_date_numeric` — bestehende, sprachfeste Helfer (de/en,
    ohne Locale-Abhängigkeit); werden nur aufgerufen, nicht geändert
- **File:** `src/output/renderers/email/helpers.py`
  - **Identifier:** `format_temp_span` (Z.1523-1534; Rückgabe aktuell `f"{lo}°C" if lo == hi else
    f"{lo}–{hi}°C"`), Aufrufer in `_aggregation_pill_text` (Z.1558, Kachelzeile)
- **File:** `src/output/renderers/compact_summary.py`
  - **Identifier:** Aufruf `format_temp_span(lo, hi, decimals=0)` (Z.380, „gefühlt"-Spanne der
    Kurzzusammenfassung) — erbt die Änderung ohne eigenen Eingriff
- **File:** `src/output/renderers/email/html.py`
  - **Identifier:** `_render_mobile_hour_list` (Z.311, ohne Aufrufer → Löschen)
  - **Identifier:** `_render_html_table` (Z.653; Spaltenbildung Z.~666-668) → Leer-Abbruch
  - **Identifier:** `_render_mobile_compact_rows` (Z.861; Vorbild: `if not cols: return ""`)
  - Aufrufer von `_render_html_table` mit `allowed_col_keys`: Z.1199 und Z.1253 (Desktop-Abschnitte,
    werden per String-Konkatenation eingebettet — `""` ist dort unkritisch); Z.1304 (Nacht-Zeilen)
    übergibt kein `allowed_col_keys` und bleibt unberührt.
- **Nicht geändert:** `_range_pill` (`helpers.py:1493`, gleiche Formel `min–max`). Begründung: die
  Funktion bedient ausschließlich Nicht-Temperatur-Größen (Wolken %, ähnliche Prozent-/Größen-
  Spannen), die nie negativ werden. Ein Eingriff hätte keine Wirkung und nur Golden-Risiko.

## Estimated Scope

- **LoC:** ca. +40 / -110 (die Löschung der toten Funktion überwiegt)
- **Files:** 4 Source-Dateien (`comparison.py`, `email/helpers.py`, `email/html.py`; `compact_summary.py`
  nur indirekt), 1-2 neue Testdateien
- **Effort:** medium; Risiko MEDIUM, weil `format_temp_span` geteilt ist (Kachel + Kurzzusammenfassung)
  und alle drei Source-Dateien dem Renderer-Commit-Gate unterliegen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/i18n/format.py` (`fmt_weekday`, `fmt_date_numeric`) | Upstream | Sprachfeste Wochentag-/Datumsformate |
| `visible_cols` / Metrikregister / `UnifiedWeatherDisplayConfig` | Upstream | Bestimmen die sichtbaren Spalten; `_allowed_col_keys_for_horizon` liefert bei komplett abgewählten Metriken schon eine leere Menge (#1405 S3, AC-24) |
| `_render_mobile_compact_rows` | Vorbild/Aufrufer | Hat den Leer-Abbruch bereits; reicht `allowed_col_keys` an `_render_html_table` durch |
| Trip-Briefing full/compact, Vergleichs-Mail (Klartext) | Downstream | Nutzersichtbare Wirkung |
| #1405 Scheibe 3 | Konvention | „Abgewählt heißt abgewählt" |
| #1794, #1927, #1418 | Historie | Specs, die `_render_mobile_hour_list` als toten Code erwähnen |

## Implementation Details

```
(1) C2-52  comparison.py, Datumszeile der Klartext-Kopfzeile:
      datum = f"{fmt_weekday(target_date, lang, kurz=False)}, {fmt_date_numeric(target_date, lang)}"
    Der Sprach-Zweig (if lang == "en" ... else strftime) entfällt; beide Sprachen laufen
    über dieselben i18n-Helfer. Der Kommentar "de: bisheriger strftime-Ausdruck ..." wird entfernt.
    Ergebnis de: "Montag, 02.11.2026"; en: unverändert "Monday, 2 Nov 2026".

(2) C2-79  helpers.py format_temp_span:
      lo, hi = gerundet formatiert (wie bisher)
      if lo == hi:            -> f"{lo}°C"                 (unverändert)
      elif min_v < 0 or max_v < 0 (mindestens ein Wert negativ, nach Rundung):
                              -> f"{lo} bis {hi}°C"        # "-12 bis -4°C", "-3 bis 5°C"
      else:                   -> f"{lo}–{hi}°C"            (unverändert, z. B. "8–14°C")
    Die Prüfung "negativ" richtet sich nach dem ANGEZEIGTEN Wert (lo/hi als Text beginnt mit "-"),
    damit "-0" nach Rundung nicht fälschlich "bis" auslöst. Wirkt automatisch auf Kachel
    (helpers.py:1558) und Kurzzusammenfassung (compact_summary.py:380); kein Eingriff dort.
    Begründung des Trennworts: "bis" ist die bestehende deutsche Konvention für Bereiche mit
    Vorzeichen; der Gedankenstrich bleibt für Plusgrade, damit dort nichts im Golden wandert.

(3) C3-35  html.py: _render_mobile_hour_list vollständig löschen (Definition Z.311 bis Funktionsende),
    danach ungenutzte Hilfs-Imports/-Konstanten entfernen, die ausschließlich von ihr benutzt wurden
    (per Grep prüfen; gemeinsam genutzte bleiben). In den Specs fix_1794, fix_1418, fix_1927 und
    ampel_schwellen_renderer bleibt der historische Text stehen; je ein Changelog-Satz
    "Funktion mit #2210 zurückgebaut" ersetzt keine Aussage, ergänzt nur den Verbleib.

(4) C3-41  html.py _render_html_table, direkt nach dem Filtern mit allowed_col_keys:
      cols = visible_cols(rows)
      if allowed_col_keys is not None:
          cols = [... if k in allowed_col_keys]
          if not cols:
              return ""          # abgewählt heißt abgewählt, wie _render_mobile_compact_rows
    Greift NUR bei gesetztem allowed_col_keys UND leerer Spaltenmenge. Der Fall allowed_col_keys=None
    (alle Aufrufer ohne Filter) und der Fall rows == [] (Minimal-Gerüst, Test bug305) bleiben
    unverändert. Aufrufer an Z.1199/1253 betten das Ergebnis per String-Konkatenation ein; ein
    leerer String erzeugt dort keinen Folgefehler.
```

## Expected Behavior

- **Input:** (1) Vergleichs-Mail mit Sprache `de`; (2) Trip mit Tiefsttemperatur unter 0 °C;
  (3) kein Laufzeit-Input; (4) Zeitraum, in dem der Nutzer alle Metriken abgewählt hat.
- **Output:** (1) Klartext-Kopfzeile „Datum: Montag, 02.11.2026"; (2) „-12 bis -4°C" statt „-12–-4°C";
  (3) Funktion existiert nicht mehr; (4) keine Stundentabelle statt eines leeren „Time/Risk"-Gerüsts.
- **Side effects:** Keine Datenmodell-Änderung. Plusgrad-Spannen, englische Mails, alle anderen
  Tabellen und die Kanäle SMS/Telegram/Premium-SMS bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given eine Vergleichs-Mail in deutscher Sprache für Montag, den 2. November 2026,
  gerendert auf einem Server mit englischer Systemsprache / When die Klartext-Fassung der Mail
  erzeugt wird / Then beginnt die Datumszeile der Kopfzeile mit „Montag, 02.11.2026" und enthält
  keinen englischen Wochentag (kein „Monday").
  - Test: echter Renderaufruf der Klartext-Vergleichs-Mail (`lang="de"`), Locale des Prozesses
    auf `C`/`en_US` gestellt; geprüft wird die Kopfzeile des Ergebnistexts.
- **AC-2:** Given dieselbe Vergleichs-Mail in englischer Sprache / When die Klartext-Fassung
  erzeugt wird / Then bleibt die Datumszeile unverändert englisch („Monday, 2 Nov 2026").
- **AC-3:** Given eine Etappe mit Tiefsttemperatur -12 °C und Höchsttemperatur -4 °C / When die
  Temperatur-Kachel der Trip-Mail gerendert wird / Then steht dort „-12 bis -4°C" und an keiner
  Stelle die Folge „-12–-4".
- **AC-4:** Given eine Etappe mit Tiefsttemperatur -3 °C und Höchsttemperatur 5 °C (Vorzeichenwechsel)
  / When die Temperatur-Kachel gerendert wird / Then steht dort „-3 bis 5°C".
- **AC-5:** Given eine Etappe mit Tiefsttemperatur 8 °C und Höchsttemperatur 14 °C (keine negativen
  Werte) / When die Temperatur-Kachel gerendert wird / Then steht dort unverändert „8–14°C".
- **AC-6:** Given eine Kurzzusammenfassung der Mail mit gefühlter Temperatur von -12 bis -4 °C /
  When der Fließtext der Kurzzusammenfassung erzeugt wird / Then enthält er „-12 bis -4°C" (die
  geteilte Spannenformel wirkt auch dort) und nicht „-12–-4°C".
- **AC-7:** Given der Quelltext des E-Mail-Renderers nach dem Rückbau / When das Modul
  `src/output/renderers/email/html.py` geladen und nach dem Namen `_render_mobile_hour_list` gefragt
  wird / Then existiert das Symbol nicht mehr, und der Import des Moduls sowie das Rendern einer
  Trip-Mail (full und compact) laufen ohne Fehler durch.
  - Test: `# doc-compliance-test` (Symbol-Abwesenheit ist hier der Nachweis für entfernten toten
    Code); die Rendern-Teile sind echte Verhaltensaufrufe.
- **AC-8:** Given ein Zeitraum, in dem der Nutzer alle Metriken abgewählt hat (leere Menge erlaubter
  Spalten), aber Stundenzeilen vorliegen / When die Stundentabelle für den Desktop-Abschnitt der Trip-
  Mail gerendert wird / Then entsteht keine Tabelle: das Ergebnis ist leer, die Mail enthält weder
  eine Kopfzeile „Time" noch eine Spalte „Risk" für diesen Zeitraum.
- **AC-9:** Given dieselbe Konstellation wie AC-8 / When die ganze Trip-Mail (full und compact,
  Desktop und Mobil) gerendert wird / Then entsteht eine gültige Mail ohne Fehler, die übrigen
  Abschnitte (Kopf, Kacheln, Zusammenfassung) sind vorhanden, und die Mobil-Ansicht verhält sich
  wie zuvor (kein Tabellengerüst).
- **AC-10:** Given ein Zeitraum mit mindestens einer sichtbaren Metrik / When die Stundentabelle
  gerendert wird / Then erscheinen weiterhin „Time", die gewählten Spaltenüberschriften und „Risk"
  wie bisher; ebenso bleibt der Aufruf ohne Spaltenfilter (`allowed_col_keys=None`) und mit leerer
  Zeilenliste (Minimal-Gerüst) unverändert.

## Test-Plan

Nur echte Verhaltenstests: der jeweilige Renderer wird real aufgerufen, geprüft wird der
ausgelieferte Text bzw. das HTML. Kein `Mock()`/`patch()`, keine Dateiinhalt-Checks als
Verhaltensnachweis (einzige Ausnahme AC-7, Symbol-Abwesenheit, mit `# doc-compliance-test`).
Testdateien nach Verhalten benannt, Prüfling relativ zur Testdatei aufgelöst; **kein**
`uv run pytest` ohne benannte Dateien.

- `tests/tdd/test_vergleichsmail_kopfzeile_wochentag_deutsch.py` — AC-1, AC-2 (Locale-unabhängig,
  Prozess-Locale auf `C` gesetzt, Gegenprobe `en`).
- `tests/tdd/test_temperaturspanne_negative_werte.py` — AC-3 bis AC-6 (`format_temp_span` direkt
  plus Kachel über `_aggregation_pill_text` und Kurzzusammenfassung aus `compact_summary.py`).
- `tests/tdd/test_mail_stundentabelle_abgewaehlte_metriken.py` — AC-7 bis AC-10 (leere
  Spaltenmenge über den echten Render-Weg `_allowed_col_keys_for_horizon` → `render_html`,
  Mobil und Desktop, Zwei-Zweig-Gegenprobe mit sichtbarer Metrik).
- Bestehende Tests, die `_render_html_table` aufrufen (`tests/tdd/test_bug305_mobile_email.py`,
  `test_issue_888_896_902_mail_bundle.py` u. a.), müssen unverändert grün bleiben; vorhandene
  de-Golden zur Kopfzeile des Vergleichs-Texts und zu negativen Spannen werden vor der Änderung
  gesucht und bei Bedarf bewusst angepasst (mit Begründung im Commit).
- Mutations-Gegenprobe (Pflicht, `implementation-validator`): (a) im Wochentag-Zweig `fmt_weekday`
  wieder durch `strftime` ersetzen → AC-1 muss rot werden; (b) in `format_temp_span` die
  Negativbedingung entfernen → AC-3/4/6 rot; (c) in `_render_html_table` den neuen Leer-Abbruch
  entfernen → AC-8 rot. Für den Rückbau (C3-35) ist eine Mutation sinnlos (toter Code), er wird
  durch AC-7 abgesichert.
- Renderer-Commit-Gate: Modus-Matrix-Test frisch grün, dazu Validator gegen echt zugestellte
  Staging-Mail — Trip-Briefing: `briefing_mail_validator.py`; Vergleichs-Mail:
  `uv run python3 .claude/hooks/email_spec_validator.py` (Exit 0).

## Known Limitations

- **Risiko Golden/Format:** Das Trennwort „bis" für negative Spannen ist eine Darstellungs-
  entscheidung (Spec-Vorschlag, an die deutsche Konvention angelehnt, keine PO-Rückfrage nötig).
  Die englische Mail hat dieselbe Formel (`format_temp_span` kennt keine Sprache) und zeigt
  künftig ebenfalls „bis" bei negativen Spannen; eine Sprachvariante wäre ein eigenes Ticket.
- **Risiko geteilte Funktion:** `format_temp_span` wirkt gleichzeitig auf Kachel und
  Kurzzusammenfassung; beide werden per AC abgedeckt.
- **Risiko Renderer-Commit-Gate:** Änderungen an `comparison.py`, `email/helpers.py`,
  `email/html.py` lösen das Gate aus; Commit erst nach frischem Modus-Matrix-Test und
  grünem Validator.
- `_range_pill` bleibt bewusst unverändert (nur nicht-negative Größen, s. Source).

## Nicht-Ziele

- Keine Änderung an Confidence (`confidence_pct` bleibt nicht wählbar, #710).
- Keine Änderung der Kanalformate SMS, Telegram und Premium-SMS; reine E-Mail-Korrekturen.
- Keine Änderung der Spaltenauswahl-Logik `_allowed_col_keys_for_horizon` oder des
  Metrikregisters.
- Kein Umbau der Mobil-Ansicht (`_render_mobile_compact_rows` bleibt wie sie ist).
- Keine Gewitter-Darstellung ändern (die „0 %"-Anzeige im Issue-Titel stammte aus dem toten Code
  und existiert im produktiven Pfad nicht).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Vier Renderer-Bugfixes innerhalb bestehender Konventionen (i18n-Helfer,
  „Abgewählt heißt abgewählt", geteilte Spannenformel). Keine der Entscheidungsflächen aus
  `docs/adr/README.md` (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie)
  wird berührt. Kanalparität (ADR-0095) bleibt gewahrt, da nur die E-Mail-Darstellung betroffen ist
  und keine Information zwischen Kanälen verschoben wird.

## Changelog

- 2026-11-01: Initial spec created (Issue #2210, Workflow fix-2210-mail-renderfehler)
