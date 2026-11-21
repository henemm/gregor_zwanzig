---
entity_id: feat_3260_s1a_ratsche_ein_katalog
type: feature
created: 2026-11-21
updated: 2026-11-21
status: approved
version: "1.0"
tags: [issue-3260, adr-0127, ratsche, metrik-katalog, verarbeitung, schritt-1]
supersedes: []
---

# Schritt 1, Scheibe A: Ratsche „Ein Katalog, eine Verarbeitung“

## Approval

- [x] Approved
- PO-Freigabe 2026-11-21, Issue #3260 (Entscheidungen E1–E5 und Antwort „Alles, ohne Rückfrage“; Pflicht-Nachtrag P1–P3 im ersten Kommentar). ACs aus dem Pflicht-Nachtrag (AC-P4) übernommen und verfeinert.

## Purpose

Macht die PO-Vorgabe „nur ein Ort für Metrik-Wissen, nur ein Ort für Metrik-Verarbeitung“ maschinell prüfbar, bevor irgendetwas umgebaut wird: Jede neue zweite Liste, jede neue Verzweigung auf eine Metrik-Kennung, jeder neue feste Schwellenvergleich außerhalb des Verarbeitungsmoduls und jeder Produktimport in einem Mail-Validator macht einen Kern-Test rot. Der heutige Bestand steht in einer Ausnahmeliste, die nur schrumpfen darf (ADR-0127).

## Source

- **Neu:** `tests/helpers/katalog_verarbeitung_scan.py` (Erkennung), `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` (Ratsche + Gegenproben), `tests/unit/ein_katalog_ausnahmen.json` (Ausnahmeliste).
- **Doku:** `docs/adr/0127-ein-katalog-eine-verarbeitung.md`, `docs/reference/gates_und_ratschen.md` (Eintrag mit Prüfdatum), `.claude/agents/implementation-validator.md` (Epic-Spec-Pflicht).
- Kein Produktcode wird geändert.

## Estimated Scope

- **LoC:** ~450 Testcode + JSON-Liste; 0 Produktcode.

## Dependencies

- `src/app/metric_catalog.py` (`_METRICS`: Menge der Kennungen; Soll aus dem Register, nicht von Hand).
- Vorlage `tests/helpers/metrik_listen_scan.py` (AST-Ansatz, Prüfling aus diesem Arbeitsbaum).

## Implementation Details

**Erlaubte Orte** (werden nicht gescannt): `src/app/metric_catalog.py` (Wissen), `src/output/metric_format.py` bzw. ein späteres Paket `src/output/metric_format/` (Verarbeitung), `src/app/ampel_templates.py` und `src/app/ampel.py` (Ampel-Grenzen als Vorlagen-Daten und ihre Auflösung, ADR-0106). Nicht gescannt werden Tests, `scripts/`, `tools/`, `src/analysis/` (Analyse-Werkzeuge ohne Produktpfad), generierte Dateien.

**Arten** (je Fund: Datei, Zeile, Art, Auszug):

1. `ID_SAMMLUNG` (Python, AST): `dict` (Schlüssel und Werte getrennt), `set`, `list`, `tuple` mit ≥ 2 verschiedenen konstanten Strings, die alle Metrik-Kennungen sind. Anders als #1856 zählt auch ein Tupel rechts von `in`.
2. `ID_VERZWEIGUNG` (Python, AST): Vergleich `==`/`!=` mit einem String-Literal, das eine Metrik-Kennung ist (z. B. `if metric_id == "wind"`), sowie `match`-`case` auf eine Kennung.
3. `SCHWELLE` (Python, AST): Vergleich (`<`, `<=`, `>`, `>=`) mit einer Zahl-Konstante, wenn der andere Operand nach Quelltext (`ast.unparse`) wie ein Messwert heißt. Muster (Groß/Klein egal): `wind|gust|boe|böe|precip|rain|regen|niederschlag|temp|chill|cloud|wolk|uv|snow|schnee|cape|visib|sicht|sun|sonne|thunder|gewitter|humid|feucht|pressure|druck|dewpoint|freezing|kmh|_mm\b|pct|\bval\b|value|wert`; ausgenommen Operanden mit `len(`. Kette `a < x < b` zählt einmal.
4. `VERARBEITUNG_AUSSEN` (Python, AST): Definition einer Verarbeitungsfunktion außerhalb des Moduls und jeder Aufruf dorthin. Die Namen stehen als Liste in der Erkennung (Ausgangsbestand aus P2): `fmt_val`, `_friendly_outlook_text`, `_friendly_hour_text`, `format_outlook_value`, `_hour_einfach_text`, `_friendly_overview_html`, `_plain_metric_cell`, die Wortfunktionen aus `src/services/weather_metrics.py` (alle dort definierten Funktionen, die einen Wert in ein Wort übersetzen; der Entwickler ermittelt sie und listet sie namentlich), die Wort-/Schwellenfunktionen aus `compact_summary.py` und `narrow.py`, die Bewertungsfunktionen aus `risk_engine.py`.
5. `FRONTEND_LISTE` (TS/Svelte unter `frontend/src/`, ohne `*.test.ts`, `*.spec.ts`, `e2e/`) und `GO_LISTE` (`internal/`, `cmd/`, ohne `_test.go`): innerste Klammer-Spanne (`[]`, `{}`, `()`), in der ≥ 2 verschiedene Metrik-Kennungen als String-Literal oder als Objekt-/Map-Schlüssel vorkommen; zusätzlich `=== "<kennung>"`, `== "<kennung>"` und `case "<kennung>"` als Verzweigung (Art `FRONTEND_VERZWEIGUNG` / `GO_VERZWEIGUNG`). Kommentare werden vorher entfernt.
6. `VALIDATOR_IMPORT` (`.claude/hooks/*.py`): jeder Import aus `app.metric_catalog`, `app.ampel_templates`, `app.ampel`, `output.*`, `services.*` sowie Importe von Namen aus Produktmodulen, auch verzögert innerhalb von Funktionen.

**Ausnahmeliste** `tests/unit/ein_katalog_ausnahmen.json`: `{"hoechststand": N, "eintraege": {"<pfad>": {"<ART>": anzahl}}}`. Die Ratsche ist rot, wenn (a) eine Datei/Art mehr Funde hat als gelistet (Meldung: jede Fundstelle dieser Datei/Art mit Datei:Zeile und Auszug), (b) weniger Funde als gelistet (Meldung: Liste verkleinern, damit der Rückgang festgeschrieben ist), (c) die Summe der Liste `hoechststand` übersteigt, (d) `hoechststand` größer ist als der im Test als Konstante festgeschriebene Höchststand (beide werden nur gesenkt). Ein Hilfsaufruf (`python -m tests.helpers.katalog_verarbeitung_scan --schreibe-ausnahmen`) erzeugt die Liste aus dem aktuellen Stand; der Test selbst schreibt nie.

**Gegenproben im Test** (AC-P4, Wirksamkeit): In ein temporäres Verzeichnis mit Renderer-ähnlichem Pfad werden geschrieben: eine zweite Liste `("wind", "gust")`, ein Vergleich `if wind_kmh > 40:`, ein `if metric_id == "precipitation":`, eine TS-Datei mit `const X = ["wind", "gust"]`, eine Go-Datei mit `map[string]float64{"wind": 1, "gust": 2}`, ein Hook mit `from app.metric_catalog import AMPEL_METRIC_IDS`. Jede muss genau ihre Art melden, mit Datei und Zeile. Eine harmlose Datei (`if len(items) > 2`, `("a", "b")`) meldet nichts.

**Regel-Budget:** Die Ratsche ersetzt die Entdeckungsstufe der Metrik-Listen-Ratsche aus #1856 (Prüfdatum 2026-11-15 abgelaufen; deren Stufe 2, Tippfehler-Prüfung registrierter Listen, bleibt bis zum Abbau der Listen); Prüfdatum der neuen Ratsche 2027-02-19.

**Abweichungen bei der Umsetzung (2026-11-21, Developer):**

- **Kennungen:** neben den 32 `_METRICS`-Ids zählen die Alarm-Identitäten aus dem Register (`alert_metrics`-Werte und `change_alert_metric` je Metrik, z. B. `wind_gust`, `temperature_min`). Ohne sie bliebe die Alarm-Vokabular-Kopie in Go (`AlertableMetrics`, `DefaultDeltaThreshold`) unsichtbar. Soll weiterhin aus dem Register, nicht von Hand.
- **TS/Go-Konstanten:** ein Bezeichner, der als Konstante an eine Kennung gebunden ist (TS `const X = 'wind'`, Go `const X [Typ] = "wind"` einzeln oder im `const ( … )`-Block), zählt in einer Klammer-Spanne wie das Literal. Verzweigungen bleiben literal (wie in Python).
- **TS/Go-Verzweigung:** neben `===`/`==` auch `!==`/`!=` und das Literal links vom Vergleich (Gleichklang mit Python `==`/`!=`); bei `case "a", "b":` zählt jedes Literal der Liste. Verzweigungs-Literale zählen nicht zusätzlich für eine Klammer-Spanne (je Literal genau eine Art). Kennungen einer bereits gemeldeten Unter-Spanne zählen für die äußere nicht mehr. Unquotierte Objektschlüssel zählen nur nach `{`, `,`, `;` oder am Zeilenanfang (kein Ternär-Rauschen). Gemeldete Zeile einer Liste = Zeile der öffnenden Klammer.
- **SCHWELLE-Muster:** `wind(?!ow)` statt `wind` und `(?<!at)temp` statt `temp` (sonst meldeten `day_window_*`, `window` und `attempt` falsch); ergänzt um `speed`, `\bmm\b`, `dni` (sonst blieben die Wind-Wortgrenzen `speed > 60/35/15` in `compact_summary.py`, `mm > 10` und `dni_wm2 >= 600` unsichtbar).
- **VERARBEITUNG_AUSSEN:** gezählt werden Definition und jeder lesende Verweis (`Name`/`Attribute` im Lese-Kontext), also Aufrufe und Übergaben als Funktionswert (`partial(_friendly_overview_html, …)`). Namensliste: Spec-Ausgangsbestand plus aus `weather_metrics.py` `get_weather_emoji`, `_night_emoji`, `_dni_emoji`, `_cloud_pct_emoji`, `format_wind_strength`, `format_precip_intensity`, `format_precip_daily_sum`, `format_rain_probability_scale`, `format_sunshine_scale`, `degrees_to_compass`, `get_weather_symbol`; aus `compact_summary.py` `_format_clouds`, `_format_precipitation`, `_precip_adjective`, `_find_rain_pattern`, `_format_wind`, `_find_wind_peak`, `_format_thunder`; aus `narrow.py` `_thunder_severity`, `_day_window_thunder_severity`, `_tg_day_footer`, `_gelb`; aus `risk_engine.py` `_check_thunder`, `_check_catalog_metric`, `_check_confidence`, `_check_wind_exposition`. Gleichnamige Funktionen anderswo zählen mit (z. B. `src/utils/geo.py::degrees_to_compass`).
- **VALIDATOR_IMPORT (Tech-Lead-Entscheid 2026-11-21, ersetzt „Importe von Namen aus Produktmodulen“):** gezählt wird nur Metrik-Wissen: Importe (auch verzögert in Funktionen und per `importlib.import_module`) aus `app.metric_catalog`, `app.ampel_templates`, `app.ampel`, jedem `app.*`-Modul mit `metric` oder `compare` im Namen, `output.*` und `services.*` (ein vorangestelltes `src.` wird ignoriert). `app.config`, `i18n`, `app.models`, `app.user`, `app.loader`, `utils.*` usw. zählen nicht. Je importiertem Namen ein Fund (ein zusätzlicher Name in einer bestehenden Importzeile macht rot).
- **Frontend-Ausnahmen:** zusätzlich `__tests__/`, `*.d.ts`, `generated/` und `*.generated.*`.
- **Startstand:** 447 Funde (ID_SAMMLUNG 48, ID_VERZWEIGUNG 57, SCHWELLE 134, VERARBEITUNG_AUSSEN 102, FRONTEND_LISTE 51, FRONTEND_VERZWEIGUNG 6, GO_LISTE 8, GO_VERZWEIGUNG 2, VALIDATOR_IMPORT 39).

**Adversary mit Epic-Spec:** `.claude/agents/implementation-validator.md` bekommt die Pflicht: Bei einer Scheibe eines größeren Auftrags erhält und prüft der Adversary zusätzlich die übergeordnete Vorgabe (Epic-Spec bzw. Auftrags-Issue mit allen ACs und Pflicht-Nachträgen) und meldet jeden Widerspruch der Scheibe zu ihr als Finding (#3256 Abschnitt 1 Nr. 3).

## Expected Behavior

- **Input:** Arbeitsbaum des Repos.
- **Output:** Kern-Test grün auf dem heutigen Stand mit vollständiger Ausnahmeliste; rot mit Datei:Zeile bei jeder neuen Verletzung.
- **Side effects:** keine.

## Acceptance Criteria

- **AC-1:** Given der heutige Stand mit vollständig erzeugter Ausnahmeliste / When die Ratsche läuft / Then ist sie grün, und jede der sechs Arten hat im Bestand mindestens einen Fund (die Erkennung arbeitet überall).
- **AC-2:** Given jemand fügt in einen Renderer eine zweite Metrik-Liste oder einen festen Schwellenvergleich auf einen Messwert ein / When die Kern-Tests laufen / Then schlägt die Ratsche fehl und nennt Datei, Zeile und Art.
- **AC-3:** Given jemand fügt im Frontend oder in Go eine Liste mit zwei Metrik-Kennungen ein / When die Ratsche läuft / Then schlägt sie fehl und nennt Datei und Zeile.
- **AC-4:** Given ein Mail-Validator importiert eine Produktliste aus Katalog oder Renderer / When die Ratsche läuft / Then schlägt sie fehl; handgeschriebene Erwartungen im Validator melden nichts.
- **AC-5:** Given eine Scheibe baut eine gelistete Stelle ab, ohne die Ausnahmeliste zu verkleinern / When die Ratsche läuft / Then schlägt sie fehl und verlangt das Verkleinern; ein Erhöhen von Anzahl oder Höchststand macht sie ebenfalls rot.
- **AC-6:** Given eine harmlose Datei ohne Metrik-Bezug (Längenvergleich, Liste fremder Wörter) / When die Erkennung sie prüft / Then meldet sie nichts.

## Definition of Done

Ratsche grün auf main, Gegenproben grün, Adversary-Mutationen (Erkennung je Art ausgeschaltet) machen den Test rot, Eintrag in `gates_und_ratschen.md`, ADR-0127 im Index.

## Test Plan

Kern-Schicht: `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`. Keine Live-Schicht (kein Produktverhalten geändert).

## Out of Scope

Abbau von Fundstellen (Schritte 1b–6). Form je Stelle im Katalog und Tabellentest (Scheibe 1b).

## Affected Files

Siehe Source.

## Known Limitations

Musterbasierte Erkennung (Namensmuster für Messwerte, Klammer-Spannen in TS/Go): berechnete Sammlungen und Messwerte mit neutralem Namen bleiben unsichtbar. Grenzfälle werden durch Umbau aufgelöst, nicht durch zusätzliche Ausnahmen.

## Architektur-Entscheidung (ADR)

ADR-0127.

## Changelog

- 2026-11-21: angelegt (Issue #3260 Schritt 1, Scheibe A).
- 2026-11-21: umgesetzt; Abweichungen der Erkennung (Alarm-Identitäten, TS/Go-Konstanten, `!=`-Verzweigung, SCHWELLE-Muster, Verweise statt nur Aufrufe, Import je Name) unter Implementation Details dokumentiert.
- 2026-11-21: VALIDATOR_IMPORT auf Metrik-Wissen eingeengt (Tech-Lead-Entscheid: `app.config`, `i18n`, `app.models`, `app.user` usw. zählen nicht); Startstand 447 Funde (VALIDATOR_IMPORT 39).
