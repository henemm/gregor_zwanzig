---
entity_id: fix_1856_e7_metrik_listen_waechter
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [metric-catalog, ratchet, ast-guard, test-only, register]
workflow: fix-1856-e7-listen-waechter
---

# Fix #1435 Etappe E7 — Wächter gegen neue Metrik-Listen

## Approval

- [x] Approved — PO-Freigabe 2026-08-15 („go"), inkl. der geänderten AC-1-Fassung

## Purpose

Das Epic #1435 hat seit dem 31.07. ein Zielbild formuliert, aber nie gebaut:
„Keine Liste darf ein eigenes Vokabular erfinden. Jede Liste, die etwas je
Wettergröße festlegt, wird mit der Register-Kennung geschlüsselt, und ein
Wächter meldet jede Kennung, die das Register nicht kennt — beim Namen."
Anlass war die PO-Frage, wofür `WC` bei den Wettermetriken steht — weder
Oberfläche noch Register geben Auskunft, weil eine Liste (die
Mehrfach-Kürzel-Tabelle `SMS_MULTI_SYMBOLS_BY_METRIC`) am bestehenden
Wächter aus E3b vorbeiläuft. E7 baut diese Ratsche. **Sie behebt nichts** —
gefundene Abweichungen werden mit E6 behoben, direkt im Anschluss.

## Hintergrund: die drei bekannten Kürzel-Abweichungen (Dokumentation, keine Prüfung)

Die PO-Frage „wofür steht `WC`?" führte zu drei gemessenen Abweichungen
zwischen dem, was die Trip-SMS tatsächlich sendet, und dem Register-Kürzel
(`get_sms_code()`): `temperature` sendet `K`/`D` statt `D` (PO-Entscheid
#1415), `wind_chill` sendet `FK`/`FD`/`WC` statt `TF` (#1415/#1450),
`temperature_night` sendet `N` statt `TN` (#1484). Alle drei sind
**getroffene Entscheidungen**, keine Fehler — Grund ist, dass zwei
Ausgabewege nebeneinander existieren: Trip-SMS liest
`SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC`, Vergleichs-SMS
(`comparison.py:647`) und Alarm-SMS (`alert/render.py:93`) lesen
`get_sms_code()` direkt. `TF`/`TN` erscheinen entgegen einer früheren
Ticket-Behauptung **nicht** in „keiner Nachricht" — sie sind live in zwei
von drei SMS-Wegen.

**Diese drei Fakten stehen hier zur Einordnung, nicht als Ergebnis einer
automatisierten Prüfung.** Ein Wächter, der die beiden Ausgabewege direkt
gegeneinander vergleicht („Parität"), wurde erwogen und verworfen (s.
„Verworfene Alternativen") — er wäre fast tautologisch gewesen. AC-1 prüft
stattdessen zwei andere, tatsächlich scharfe Eigenschaften (s. u.).

## Source

> **Schicht-Hinweis:** ausschließlich Testschicht (`tests/unit/`), keine
> Produktivcode-Änderung. Der neue Wächter liest `src/app/metric_catalog.py`
> als Soll-Quelle und scannt `src/` + `api/` als Prüfmenge, ändert daran aber
> nichts.

- **File:** `tests/unit/test_sms_token_symbol_register_ratchet.py` (Erweiterung, nicht Ersetzung — s. AC-7)
- **File (neu):** `tests/unit/test_metrik_listen_register_ratchet.py`
- **Identifier (Soll-Quelle, gelesen):** `app.metric_catalog._METRICS`, `get_all_metrics()`, `get_sms_code()`, `SMS_MULTI_SYMBOLS_BY_METRIC`, `SMS_SYMBOL_BY_METRIC`, `_kurzform_kuerzel()`

## Estimated Scope

- **LoC:** ~380–480 **Test**-Budget (Vergleichsmaß: E3b-Ratsche 415 Zeilen,
  Telegram-Wächter 460 Zeilen). Passt ins getrennte Test-Budget (500) ohne
  Override-Anfrage. **0 Zeilen Produktivcode** — Registrierung und
  Ausnahmelisten liegen im Testfile, wie bereits `EXEMPT_FORECAST_FIELDS`/
  `EXEMPT_METRIC_IDS` in der bestehenden Ratsche.
- **Files:** 1 neue Testdatei, 1 bestehende Testdatei erweitert, 0
  Produktivdateien geändert.
- **Effort:** medium — die Erkennungslogik (AC-2) ist der eigentliche
  Aufwand; sie muss eine geschlossene Klasse (vier Sammlungsformen) robust
  behandeln, ohne bei jeder heute schon vorhandenen, harmlosen Liste
  Fehlalarm zu geben (Falsch-Positiv-Prüfstein `HAZARD_SMS_SYMBOLS`, s. u.).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog._METRICS` (28 Einträge) | READ (Soll-Menge) | **Nicht** `get_all_metrics()` (25) — der Filter entfernt `selectable=False` (`cape`, `confidence`, `temperature_cold`), die sonst fälschlich als „unbekannte Kennung" gemeldet würden |
| `app.metric_catalog.get_all_metrics()` (25 Einträge) | READ (Soll-Menge für Vollständigkeit) | Nur für den opt-in Vollständigkeits-Check (s. AC-4) — dort geht es um „jede *wählbare* Größe", nicht um jede Registereinheit |
| `app.metric_catalog.get_sms_code()`, `_kurzform_kuerzel()` | READ | Soll-Kürzel je Metrik; `_kurzform_kuerzel()` ist die bereits produktiv genutzte Auflösung „welches Kürzel benennt die Größe" (auch von `/api/sms-symbols` verwendet) — AC-1 nutzt sie, statt sie ein zweites Mal im Test nachzubauen |
| `app.metric_catalog.SMS_MULTI_SYMBOLS_BY_METRIC` | READ (Prüfling AC-1) | Die ungeprüfte Liste, die den Anlassfall auslöste |
| `output.renderers.channel_layout.METRIC_PRIORITY` (Zeile 60) | READ (Beispiel-Registrierung, Befund 2) | Fehlen `temperature_night`/`wind_chill_night` — der Fang-Beleg dieser Etappe (s. Regel-Budget) |
| `output.tokens.hazard_symbols.HAZARD_SMS_SYMBOLS` (Zeile 15) | READ (Falsch-Positiv-Prüfstein) | Vokabular amtlicher Warnungen, sieht strukturell wie eine Metrik-Liste aus, Quote gegen das Register 0/10 — muss unauffällig bleiben |
| `ast` (Python-Standardbibliothek) | intern | Erkennung über echten Syntaxbaum statt Regex — Bauprinzip aus E3b/#1409 |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | ERWEITERT | bekommt eine fünfte Prüfstelle (AC-1); die vier bestehenden bleiben unverändert (AC-7) |

## Implementation Details

### Zwei Stufen, unabhängig voneinander

Die beiden Fragen dürfen nicht aneinanderhängen — sonst senkt ein einzelner
Tippfehler die berechnete Quote einer Liste unter die Erkennungsschwelle,
die Liste fällt aus der Prüfmenge, und der Wächter schweigt genau dort, wo
er reden sollte. Das ist der subtilste Konstruktionsfehler dieses Entwurfs
und wird deshalb architektonisch ausgeschlossen, nicht nur vermieden:

**Stufe 1 — Entdeckung (AC-2/AC-3), bei jedem Lauf frisch berechnet.**
Ein AST-Scan über `src/` + `api/` sucht Sammlungs-Literale (`dict`, `set`,
`list`, `tuple` — eine geschlossene Menge, s. „Verworfene Alternativen").
Eine Sammlung gilt als **Register-Liste**, wenn:

- sie mindestens **zwei** konstante String-Elemente hat (Mindestgröße gegen
  Zufallstreffer — eine einzelne zufällig passende Zeichenkette beweist
  nichts), und
- **alle** ihre konstanten String-Elemente Register-Kennungen sind (Element
  ∈ `{m.id für m in _METRICS}`). Bei `dict`-Literalen zählen Schlüssel und
  Werte **getrennt** — eine Übersetzungstabelle *ins* Register (z. B.
  `{"snow_depth": "sd", ...}` im Sinne eines fremden Schlüssels) hat die
  Kennungen als Werte, nicht als Schlüssel.

Ist eine so gefundene Sammlung **nicht** in der Registrierung aus Stufe 2
verzeichnet, ist das ein Fund: der Test wird rot, nennt Datei:Zeile und —
soweit ermittelbar — den Namen der Sammlung.

**Stufe 2 — Gültigkeitsprüfung (AC-4/AC-6), fest verdrahtete
Registrierung.** Eine gepflegte, im Testfile lebende Tabelle (Modul + Name
+ eine Funktion, die die tatsächlich verwendeten Kennungen liefert) der
bekannten Register-Listen. Für **jede** registrierte Liste gilt
unabhängig von ihrer in Stufe 1 berechneten Quote:

```python
@dataclass(frozen=True)
class RegisteredList:
    ist: Callable[[], set[str]]          # tatsaechlich verwendete Kennungen
    ort: str                             # "datei.py:zeile Name" fuer Meldungen
    soll_vollstaendig: Optional[Callable[[], set[str]]] = None
    fehlend_erlaubt: frozenset[str] = frozenset()  # nur bei soll_vollstaendig

REGISTERED_LISTS: dict[str, RegisteredList] = {
    # Schluesselseite: die Kennung STEHT als dict-Schluessel/Element.
    "channel_layout.METRIC_PRIORITY": RegisteredList(
        ist=lambda: set(METRIC_PRIORITY.keys()),
        ort="src/output/renderers/channel_layout.py:60",
        soll_vollstaendig=lambda: {m.id for m in get_all_metrics()},
        # Befund #1856 (Etappe E7): temperature_night/wind_chill_night
        # fehlen. Behoben in E6, nicht hier. Darf nur schrumpfen.
        fehlend_erlaubt=frozenset({"temperature_night", "wind_chill_night"}),
    ),
    # Werteseite: die Kennung steht als dict-WERT, der Schluessel ist
    # bewusst fremdes Vokabular (hier: Frontend-Metrik-ID) und wird NIE
    # gegen das Register geprueft -- nur die Werte durchlaufen die
    # Gueltigkeitspruefung.
    "trip_metric_map.FRONTEND_TO_HOURLY_METRIC_ID": RegisteredList(
        ist=lambda: set(FRONTEND_TO_HOURLY_METRIC_ID.values()),
        ort="<Fundstelle aus AC-2-Scan>",
    ),
    # ... weitere Fundstellen aus dem AC-2-Scan, s. "Vollstaendigkeit der
    # Registrierung" unten.
}
```

Jede Kennung in `ist()` muss in `_METRICS` stehen (**Gültigkeit**) — das ist
auf jede der vier Sammlungsformen anwendbar und fängt Tippfehler und
gelöschte Metriken. **🔴 Diese Prüfung hängt bewusst nicht an der Quote aus
Stufe 1** — sie läuft über die Registrierung, komplett unabhängig davon, ob
der Scan die Liste heute (noch) als „100 % Quote" einstufen würde.

**Schlüsselseite und Werteseite bekommen unterschiedliche Prüfungen, nie
eine gemeinsame.** Schlüsselseite: alle Schlüssel sind gültige Kennungen.
Werteseite (die Übersetzungstabellen, s. „Vollständigkeit der Registrierung"
unten): alle **Werte** sind gültige Kennungen; die Schlüssel sind
absichtlich fremdes Vokabular (`col_key`, `frontend_key` o. Ä.) und dürfen
**niemals** gegen das Register geprüft werden — das wäre eine falsche
Zusicherung, keine strengere.

🔴 **Zahlenstand nach der Umsetzung (2026-08-15, am Code nachgemessen).** Die
Planungszahl **18** in einer früheren Fassung dieses Absatzes war zu niedrig:
Sie zählte nur Wörterbücher. Die Regel erfasst aber alle vier Sammlungsformen
(`dict`/`set`/`list`/`tuple`). Verbindlich ist:

| Zahl | Bedeutung |
|---|---|
| **42** | registrierte Listen = Fundstellen des Scans, in **12 von 200** Dateien |
| 40 | davon in `_BESTAND`; die übrigen 2 sind Laufzeit-Einträge (`METRIC_PRIORITY`, `HOURLY_EXCLUSION_REASON` — s. Known Limitations) |
| 47 | Rohtreffer **ohne** den `in`-Ausschluss (fünf `if metric_id in (…)`-Vergleiche, keine Listen) |
| 34 | eigenständige Sammlungen nach Namensgruppierung (`WEATHER_TEMPLATES` 7→1, `_ALERT_METRIC_TO_CATALOG_ID` 2→1, `_DERIVED_METRIC_RULES` 2→1) |

Stand **nach #1728 Scheibe 1** (`c18f8eb7`, 2026-08-15), am Code nachgemessen.
Vor dieser Scheibe lauteten dieselben vier Zahlen 40 / 39 / 45 / 33; #1728 hat
vier Größen ergänzt (Register 28 → 32, wählbar 25 → 29) und dabei zwei
Fundstellen in `loader._DERIVED_METRIC_RULES` sowie eine umbenannte,
gewachsene Liste (`_NIGHT_SCALAR_IDS` → `VISIBILITY_GATE_IDS`) hinterlassen.
Der Wächter hat alle drei gemeldet — das ist sein erster Fang im Betrieb.

Alle vier Zahlen sind gültig, meinen aber **verschiedene Zähleinheiten** — sie
wurden in der Umsetzung gegeneinander verwechselt (Adversary-Finding F003).
Wer sie zitiert, nennt die Einheit mit.
Eine gemeinsame **Erkennung** (Stufe 1, „Element ∈ Register-Kennungen") ist
für beide Seiten richtig; eine gemeinsame **Validierung** wäre falsch.

### Vollständigkeit — begründete, opt-in Erweiterung von AC-4 (Designentscheidung)

Der Team-Auftrag zu dieser Spec beschreibt zwei Stufen (Entdeckung,
Gültigkeit). Das Ticket-AC-4 prüft nur eine Richtung: „steht eine
**vorhandene** Kennung nicht im Register?" Befund 2 (`METRIC_PRIORITY`
fehlen zwei wählbare Größen) ist die **umgekehrte** Richtung: eine gültige
Kennung **fehlt** in einer Liste, die fachlich alle wählbaren Größen führen
sollte. Ohne eine Prüfung dieser Richtung bliebe Befund 2 eine bloße
Beobachtung dieser Spec-Analyse, nicht ein Fund, den der Wächter selbst
reproduzierbar macht — und das Regel-Budget verlangt einen echten,
nachprüfbaren Fang.

Deshalb bekommt die Registrierung aus Stufe 2 ein **optionales** Feld
`soll_vollstaendig`: nur Listen, bei denen Vollständigkeit fachlich gilt
(wie `METRIC_PRIORITY` — sie entscheidet die Top-5-Anzeige für **alle**
wählbaren Größen), tragen es. Das ist dieselbe Gültigkeitsprüfung aus
Stufe 2, nur in beide Richtungen gelesen — keine dritte, universelle Stufe.
Listen ohne dieses Feld (die meisten) werden weiterhin ausschließlich auf
„keine ungültige Kennung" geprüft. `fehlend_erlaubt` folgt demselben Muster
wie `EXEMPT_METRIC_IDS`: Ticket-Bezug, darf nur schrumpfen, eigener Test
(AC-5).

### Fluchtventil

Kommentar `# gz-fremdvokabular: <Begründung>` (mindestens 15 sinnvolle
Zeichen) in den ersten 20 Zeilen um die Fundstelle — Muster von
`gz-eigenstaendig` (#1481 B) und `gz-main-path` (#1409). Im heutigen
Bestand kommt der Fall nicht vor (`HAZARD_SMS_SYMBOLS` fällt bereits über
die 0/10-Quote korrekt heraus), die Möglichkeit gehört trotzdem
dokumentiert, nicht stillschweigend ausgeschlossen — eine kleine, zufällig
voll-quotierte Liste ohne Register-Bezug ist theoretisch möglich.

### Vollständigkeit der Registrierung (Implementierungsschritt, nicht Teil der Spec-Festlegung)

Welche konkreten Listen heute in Stufe 2 eingetragen werden müssen, ergibt
sich erst aus dem tatsächlichen Lauf des AC-2-Scans zum Implementierungs-
zeitpunkt (Prinzip 3 „Nichtstun ist kein Bestehen" verlangt, dass der Scan
läuft, nicht dass diese Spec seine Ausgabe vorwegnimmt). Nach der
Kandidatenmessung dieser Etappe sind es **18** Listen: **12** auf der
Schlüsselseite (Register-Kennung als dict-Schlüssel bzw. Element von
`set`/`list`/`tuple`) — darunter `METRIC_PRIORITY` (s. o.),
`SMS_MULTI_SYMBOLS_BY_METRIC` und `SMS_SYMBOL_BY_METRIC` (deren
Eindeutigkeit zusätzlich über die erweiterte E3b-Ratsche geprüft wird, s.
AC-1/AC-7) — und **6** auf der Werteseite, die sechs Übersetzungstabellen
aus der Kandidatenmessung (`FRONTEND_TO_HOURLY_METRIC_ID`,
`_SUMMARY_KEY_TO_CATALOG_ID`, `RENDERER_TO_TRIP_METRIC_ID`,
`_COL_KEY_TO_METRIC_ID`, `_FALLBACK_COL_KEY_TO_METRIC_ID`,
`_AMPEL_KEY_TO_METRIC_ID`).

### Verworfene Alternativen

- **Namensmuster (`_X_TO_Y` = Übersetzungstabelle).** Widerlegt durch
  `_id_to_sms_symbol` (5/5 Quote) und `_METRIC_ID_TO_ENTRY_ATTR`
  (15/15 Quote) — beide heißen wie eine Übersetzungstabelle, sind aber
  echte Register-Listen. Das Namensmuster hätte den Verstoß freigesprochen.
- **Richtung allein (Kennung als Schlüssel vs. als Wert).**
  `_METRIK_KLARTEXT` (5/24) und `_PARAM_TO_FIELD` (4/19) sind auf der
  Schlüsselseite fremd — Richtung ist nur ein Sonderfall der Quote, kein
  eigenständig tragfähiges Kriterium.
- **Reine Positivliste (nur Stufe 2, ohne Stufe 1).** Löst AC-4/AC-6, aber
  AC-2 gar nicht — eine neue, ungeschlüsselte Liste bliebe unsichtbar, bis
  jemand sie von Hand einträgt. Genau diese Lücke soll E7 schließen.
- **Formaufzählung ohne Grenze.** `if`-Ketten und Comprehensions wurden
  erwogen, aber verworfen — s. Known Limitations.
- **AC-1 wörtlich („Mehrfach-Tabelle folgt dem Register").** Die
  Ticket-Fassung würde `SMS_MULTI_SYMBOLS_BY_METRIC` direkt gegen
  `get_sms_code()` vergleichen und für jede Abweichung eine Ausnahme
  verlangen. Die drei heute existierenden Abweichungen sind aber
  **entschieden** (#1415/#1450/#1484) — nach dem ersten Lauf, an dem alle
  drei in die Ausnahmeliste wandern, findet diese Prüfung strukturell
  nichts mehr, weil die Tabelle genau dafür existiert, gewollte
  Abweichungen zu halten. Erfüllt das Regel-Budget-Kriterium „mindestens
  ein Fang, der sonst entgangen wäre" nach dem ersten Lauf nicht mehr.
- **Parität zwischen den Wegen** (jede Größe mit Kürzel im Trip-SMS-Weg hat
  auch eines im Register-Weg, und umgekehrt). Gemessen: nur `confidence`
  (kein `sms_code` im Register) und `temperature_cold` (kein Trip-SMS-
  Kürzel) weichen ab, beide `selectable=False` und damit ohnehin bewusst
  außerhalb der nutzersichtbaren Kürzel-Welt. Die Prüfung wäre nahezu
  tautologisch und bräuchte sofort zwei Ausnahmen, ohne einen echten Fehler
  abzudecken.

## Expected Behavior

- **Input:** Der Wächter läuft als Teil von `uv run pytest tests/unit/` —
  bei jedem Commit-Gate-Lauf, in der CI-Ampel ohne Pfadangabe (`test`-Job).
- **Output:** Grün, solange (a) jede registrierte Liste nur gültige
  Kennungen führt (bzw. bei `soll_vollstaendig` nur dokumentiert fehlende),
  und (b) kein neues, ungeschlüsseltes Vokabular im Scan auftaucht. Rot mit
  konkreter Datei:Zeile- und Kennungsangabe sonst.
- **Side effects:** keine — reiner Lesezugriff auf Quelltext und Register,
  kein Produktivverhalten wird berührt.

## Acceptance Criteria

- **AC-1:** Given die Tabelle der Mehrfach-Kürzel
  (`SMS_MULTI_SYMBOLS_BY_METRIC`, `src/app/metric_catalog.py:710`) und die
  Einzel-Kürzel-Tabelle (`SMS_SYMBOL_BY_METRIC`) / When der erweiterte
  Kürzel-Wächter läuft / Then prüft er zwei getrennte Eigenschaften:

  **(a) Gültigkeit — braucht keinen eigenen Test.** Jede Kennung in
  `SMS_MULTI_SYMBOLS_BY_METRIC` muss im Register existieren. Die Tabelle
  hat Quote 5/5 (alle fünf Schlüssel sind gültige Metrik-Kennungen) und ist
  damit ohnehin eine der in Stufe 2 registrierten Listen (AC-2/AC-4) — die
  Prüfung fällt dort automatisch an und wird für AC-1 nicht doppelt gebaut.

  **(b) Eindeutigkeit je Ausgabeweg** — kein Kürzel bezeichnet zwei
  **verschiedene** Größen. Zwei getrennte Prüfungen, nie gemischt:
  - **Trip-SMS-Weg:** für jede Metrik-Kennung aus der Vereinigung von
    `SMS_SYMBOL_BY_METRIC.keys()` und `SMS_MULTI_SYMBOLS_BY_METRIC.keys()`
    wird über die **bestehende** `_kurzform_kuerzel()` genau ein Kürzel
    ermittelt (nicht neu nachgebaut). Erst danach — nach **Metrik-Kennung**
    gruppiert, nicht nach Kürzel-Wert — wird geprüft, ob zwei
    verschiedenen Kennungen dasselbe Kürzel zugewiesen ist.
  - **Register-Weg:** für jede Metrik in `_METRICS` wird `sms_code`
    genommen; dieselbe Eindeutigkeitsprüfung, unabhängig vom Trip-SMS-Weg.

  🔴 **Fallstrick, gemessen und zu vermeiden:** Gruppiert man stattdessen
  nach dem rohen Kürzel-**Wert**, erscheint `TH` zweimal — einmal aus
  `SMS_SYMBOL_BY_METRIC["thunder"]` (`"TH:"`), einmal aus
  `SMS_MULTI_SYMBOLS_BY_METRIC["thunder"][0]` (`"TH:"`) —, beide Male aber
  für **dieselbe** Größe `thunder`. Das ist bereits bekannt und an anderer
  Stelle abgesichert (`tests/tdd/test_sms_snow_symbols.py:647`,
  `test_ac2_thunder_appears_once_with_two_symbols_no_duplicate` — der
  `/api/sms-symbols`-Endpunkt dedupliziert genau diesen Fall). Wer hier
  nach Kürzel statt nach Metrik-Kennung gruppiert, meldet beim ersten Lauf
  einen Fehler, der keiner ist.

  Beide Prüfungen sind **heute grün** (nachgemessen: Register-Weg 27
  geprüfte Kürzel, 0 Kollisionen; Trip-SMS-Weg 26 geprüfte Kürzel — nur
  `confidence` und `temperature_cold`, beide `selectable=False`, führen gar
  kein Trip-SMS-Kürzel —, ebenfalls 0 Kollisionen).

  🔴 **Zweiter Fallstrick, gemessen:** Das Register hat 28 Einträge, aber nur
  **27** Kürzel — `confidence` führt einen **leeren** `sms_code` (bewusst: die
  Größe ist `selectable=False` und erscheint laut PO-Entscheid #710 nie als
  wählbare Metrik). Die Eindeutigkeitsprüfung muss leere Kürzel **überspringen**,
  nicht gruppieren. Sonst gilt: sobald eine zweite Größe ohne Kürzel hinzukommt,
  meldet der Wächter zwei leere Zeichenketten als „Kollision" — ein Fehlalarm,
  der keine echte Doppelvergabe ist. Das ist gewollt: AC-1
  bewacht eine **künftige** Copy-Paste-Kollision, nicht die drei bekannten
  Abweichungen aus dem „Hintergrund"-Abschnitt oben — die sind Ergebnis
  einer PO-Entscheidung, nicht Ergebnis einer Prüfung, und brauchen deshalb
  **keine** vorbefüllte Ausnahmeliste. Eine **vierte**, neue,
  unbegründete Kollision macht den Wächter trotzdem sofort rot.
  - **Formulierungs-Korrektur 2026-08-15 (zweiter Durchgang,
    Team-Lead-Rückmeldung):** Eine erste Fassung dieser AC verglich das
    über `_kurzform_kuerzel()` ermittelte führende Kürzel direkt gegen
    `get_sms_code()` und verlangte für jede Abweichung einen
    Ausnahme-Eintrag. Das ist verworfen (s. „Verworfene Alternativen",
    „Parität zwischen den Wegen") — eine solche Prüfung wäre nach dem
    ersten Lauf strukturell taub: Sie fängt genau die drei heute bekannten
    Fälle, danach nie wieder etwas, weil `SMS_MULTI_SYMBOLS_BY_METRIC` und
    `SMS_SYMBOL_BY_METRIC` genau dafür existieren, gewollte Abweichungen zu
    halten. Die jetzige Eindeutigkeitsprüfung bleibt dagegen dauerhaft
    scharf, weil sie nichts Bekanntes ausnimmt.
  - Test: zwei neue, eng verwandte Testfunktionen in
    `tests/unit/test_sms_token_symbol_register_ratchet.py` (fünfte
    Prüfstelle im Sinne von AC-7), eine je Ausgabeweg. Keine neue
    Ausnahmeliste nötig, da beide Prüfungen heute kollisionsfrei sind.

- **AC-2:** Given eine **neu angelegte** Sammlung (`dict`/`set`/`list`/
  `tuple`) irgendwo unter `src/` oder `api/`, deren konstante
  String-Elemente (bei `dict`: Schlüssel und Werte getrennt gezählt)
  vollständig aus Register-Kennungen bestehen und mindestens zwei sind /
  When sie **nicht** in der Registrierung aus Stufe 2 verzeichnet ist /
  Then meldet der AST-Scan sie mit Datei:Zeile und — soweit ermittelbar —
  Name. Die Frage ist umgekehrt gestellt: nicht „kenne ich diese Liste?",
  sondern „welche Liste legt etwas je Wettergröße fest, ohne registriert zu
  sein?".
  - Test: `tests/unit/test_metrik_listen_register_ratchet.py` — AST-Scan
    über `src/` + `api/`, Ergebnis-Set gegen `REGISTERED_LISTS.keys()`
    abgeglichen. Falsch-Positiv-Gegenprobe: `HAZARD_SMS_SYMBOLS`
    (0/10-Quote) taucht **nicht** im Fund-Set auf.

- **AC-3:** Given der AST-Scan aus AC-2 / When er über `src/` + `api/`
  läuft / Then behauptet er seine eigene Trefferzahl — findet er
  **weniger** als eine bekannte Mindestzahl an Sammlungen, die das Muster
  erfüllen (Erkennungs- **und** Registrierungsseite je einzeln, jeweils
  `> 0`), schlägt der Test fehl statt grün durchzulaufen. Nichtstun ist
  kein Bestehen (Bauprinzip 3 aus E3b).
  - Test: `tests/unit/test_metrik_listen_register_ratchet.py::test_scan_hat_pruefmaterial`
    — `assert len(gefundene_kandidaten) > 0` und
    `assert len(REGISTERED_LISTS) > 0`.

- **AC-4:** Given eine der in Stufe 2 registrierten Listen, unabhängig von
  der in Stufe 1 berechneten Quote / When eine ihrer Kennungen **nicht** in
  `_METRICS` steht (Tippfehler oder gelöschte Metrik) / Then meldet der
  Wächter sie namentlich mit Datei:Zeile, statt sie stillschweigend zu
  überspringen. **Erweiterung (Designentscheidung, s. Implementation
  Details „Vollständigkeit"):** Trägt eine Registrierung zusätzlich
  `soll_vollstaendig`, prüft dieselbe Testfunktion auch die umgekehrte
  Richtung — fehlt eine wählbare Größe (`get_all_metrics()`) in der Liste
  und steht sie nicht in `fehlend_erlaubt`, ist das ebenfalls ein Fund.
  - Test: parametrisiert über `REGISTERED_LISTS`; Fixture mit absichtlich
    verfälschter, lokaler Kopie (Tippfehler-Kennung eingefügt) beweist die
    Existenzrichtung, Fixture mit entferntem `fehlend_erlaubt`-Eintrag für
    `METRIC_PRIORITY` beweist die Vollständigkeitsrichtung (s. AC-6 für den
    protokollierten Mutationsnachweis am echten Code).

- **AC-5:** Given der neue Wächter / When er eine bestehende Abweichung
  findet, die in dieser Etappe **nicht** behoben wird / Then steht sie in
  einer kommentierten Ausnahmeliste mit Ticket-Bezug — nicht als stiller
  Filter. Die Liste darf nur schrumpfen. Konkretes Beispiel: `#1856`,
  `METRIC_PRIORITY` (`channel_layout.py:60`) fehlen `temperature_night`
  und `wind_chill_night` (seit #1484/#1660 eigenständig wählbar, nie
  nachgezogen) — Eintrag `fehlend_erlaubt={"temperature_night",
  "wind_chill_night"}` mit Kommentarverweis auf #1856/E6.
  - Test: `test_ausnahmeliste_nur_schrumpft` — vergleicht die Größe jedes
    `fehlend_erlaubt`-Sets je Registrierung (aktuell nur `METRIC_PRIORITY`)
    gegen einen im Test hartcodierten Vorzustand (Stand dieser Spec);
    zusätzlich Begründungslängen-Check (≥ 15 sinnvolle Zeichen je
    Kommentar, Muster `pendant_gate.py`). AC-1 selbst braucht keine
    Ausnahmeliste (s. dort) — dieser Test prüft ausschließlich die
    Vollständigkeits-Ausnahmen aus AC-4.

- **AC-6:** Given eine registrierte Liste wird gezielt verfälscht
  (Mutationsprobe) / When der Wächter läuft / Then wird er rot und benennt
  die betroffene Kennung sowie die Fundstelle. Pflicht **für jede** neu
  bewachte Liste einzeln — parametrisiert über die Registrierung, nicht als
  Einzelfunktionen (sonst platzt das Zeilenbudget beim Wachsen der
  Registrierung).
  - Test: protokollierter Nachweis nach dem Muster „Wirksamkeitsnachweis
    der Ratsche" aus E3b — für **eine** repräsentative Registrierung
    (`METRIC_PRIORITY`) wird in einer lokalen, nicht committeten Kopie (1)
    eine gültige Kennung durch einen Tippfehler ersetzt UND (2) der
    `fehlend_erlaubt`-Eintrag entfernt; beide Läufe werden protokolliert
    (rot, Kennung benannt), die Verfälschung danach zurückgenommen. Die
    **automatisierte** Parametrisierung über `REGISTERED_LISTS` deckt alle
    übrigen Einträge strukturell ab (dieselbe Prüffunktion, andere Daten) —
    sie ersetzt nicht den protokollierten Einzelnachweis, ergänzt ihn.
  - **Katalog-Wächter-Blindfleck beachtet:** Die Soll-Menge (`_METRICS`,
    28 Kennungen) darf berechnet werden, die Soll-**Zuordnung** (welches
    Kürzel zu welcher Metrik gehört) nicht — deshalb prüft AC-1
    `_kurzform_kuerzel()` gegen `get_sms_code()`, zwei getippte,
    unabhängig gepflegte Werte, keine Tautologie.

- **AC-7:** Given die bestehende Ratsche
  `tests/unit/test_sms_token_symbol_register_ratchet.py` (E3b, 415 Zeilen)
  / When E7 fertig ist / Then ist sie **erweitert, nicht ersetzt** — ihre
  vier bisherigen Prüfstellen (`test_ratchet_inspects_the_code_of_this_worktree`,
  `test_ratchet_actually_has_material_to_check`,
  `test_wintersport_token_symbols_match_register`,
  `test_sms_symbol_by_metric_matches_register`) bleiben unverändert
  wirksam; eine fünfte kommt hinzu (AC-1).
  - Test: Diff-Review im PR zeigt ausschließlich Ergänzungen an der
    bestehenden Datei (neue Funktion + neue Ausnahmeliste), keine Löschung
    oder inhaltliche Änderung der vier bestehenden Testfunktionen.

## Regel-Budget

Prüfdatum **2026-11-15**. Der neue Wächter ersetzt keinen bestehenden,
sondern erweitert die E3b-Ratsche um eine zweite, umgekehrt gestellte
Frage. **Fang-Kriterium:** mindestens eine Abweichung oder neue
ungeschlüsselte Liste, die er fängt und die den anderen Wächtern entgangen
wäre.

**Fang-Beleg bei Einführung:** `src/output/renderers/channel_layout.py:60`,
`METRIC_PRIORITY` (25 Einträge) entscheidet, welche fünf Größen bei knappem
Platz in den `primary`-Bucket kommen (Zeile 131:
`METRIC_PRIORITY.get(pair[1], 0)`). `temperature_night` und
`wind_chill_night` fehlen — beide seit #1484/#1660 eigenständig wählbar,
nie nachgezogen. Ohne Eintrag Priorität 0, hinter `cloud_high` (10) und
`confidence` (8). Die Datei importiert nichts aus `metric_catalog` — kein
anderer heute laufender Wächter hätte das gefangen. Behoben wird das in
**E6**; hier dient es als Beleg, dass die Vollständigkeits-Erweiterung aus
AC-4 einen echten, bis heute unentdeckten Fehler mechanisch reproduziert
(nicht nur dokumentiert), sobald der `fehlend_erlaubt`-Eintrag probeweise
entfernt wird (s. AC-6).

**Risiko, das dieses Budget einordnet:** Die CI-Ampel ruft `uv run pytest`
**ohne Pfadangabe** auf (`.github/workflows/ci.yml:58`). Ein neuer Wächter
unter `tests/unit/` läuft ab Merge automatisch mit und blockiert bei Rot
**jeden** PR, auch die anderer Sessions — der Wächter muss am Tag der
Einführung grün sein. **Eingeschränkt gegenüber einer früheren Fassung
dieser Spec:** AC-1 selbst braucht dafür **keine** vorbefüllte
Ausnahmeliste mehr (beide Eindeutigkeitsprüfungen sind heute kollisionsfrei
— s. AC-1). Atomar in einer Lieferung kommen müssen weiterhin die
`soll_vollstaendig`-Registrierungen aus AC-4 mit ihren `fehlend_erlaubt`-
Einträgen — konkret `METRIC_PRIORITY` mit `{"temperature_night",
"wind_chill_night"}` (AC-5). Ohne diesen Eintrag wäre der Wächter am Tag
der Einführung rot.

## Nicht in dieser Etappe

- **Die gefundenen Abweichungen selbst beheben** — das ist **E6**, direkt
  im Anschluss (#1435). E7 macht sie nur sichtbar und schreibt sie fest.
- **Die sieben Vokabulare vereinheitlichen** — ausdrücklich nicht
  vorgesehen (#1435, „Ausdrücklich NICHT vorgeschlagen").
- **Frontend-Listen** — soweit sie über `/api/sms-symbols` aus dem Backend
  lesen, sind sie bereits gedeckt; ein separater Frontend-Wächter ist nicht
  nötig (Muster aus E3b).
- **Go-Seite.**
- **`if metric_id == "..."`-Ketten und dict-Comprehensions** — s. Known
  Limitations.

## Known Limitations

- **`if`-Ketten (32 gemessen) und dict-Comprehensions (93 gemessen) werden
  nicht erfasst.** Die vier Sammlungs-Literale (`dict`/`set`/`list`/
  `tuple`) sind eine geschlossene Menge — sie aufzuzählen ist etwas anderes
  als das Aufzählen von *Schreibweisen* innerhalb einer Form. `if`-Ketten
  und Comprehensions sind dagegen eine offene Klasse. Wer sie mitnehmen
  will, landet in derselben Aufzählungsfalle, an der ein früherer
  AST-Wächter dieses Repos dreimal gescheitert ist (Zwischenvariable, dann
  Liste und Tupel-Rückgabe umgingen die Erkennung trivial) —
  dokumentiert in `docs/specs/modules/fix_1667_s1_fixture_wanduhr.md`
  (Issue #1667 Scheibe S1). Gelöst wurde es dort durch ein **strukturelles**
  Muster (Elternkette fragen: „fließt der Wert in einen Aufruf/Dict-Wert/
  return?") statt durch Aufzählung von Schreibweisen. Diese Etappe geht das
  Risiko bewusst nicht ein, solange die geschlossene Vier-Formen-Menge noch
  nicht ausgeschöpft ist — eine strukturelle Lösung für `if`-Ketten wäre
  eine eigene, größere Folge-Etappe.
- **Eine vollständig fremd benannte, inhaltlich aber per-Metrik geführte
  Liste** (Quote 0 %) bleibt unsichtbar. Bewusste Grenze: Falsch-Positive
  sind schlimmer als eine Restlücke — ein Wächter, der harmlose Listen
  meldet (wie `HAZARD_SMS_SYMBOLS`, wäre die Quote-Schwelle niedriger),
  wird abgeschaltet.
- **Vollständigkeit wird nur dort geprüft, wo ein Registrierungseintrag es
  ausdrücklich verlangt (`soll_vollstaendig`).** Das ist eine bewusste,
  begründete Erweiterung über die im Ticket wörtlich beschriebenen ACs
  hinaus (s. Implementation Details) — sie deckt nur die Listen ab, die
  jemand als „muss vollständig sein" registriert hat, nicht jede denkbare
  Register-Liste automatisch. Eine Liste, die fachlich Vollständigkeit
  bräuchte, aber nie mit diesem Flag registriert wurde, bleibt bezüglich
  fehlender Einträge unbewacht — nur bezüglich ungültiger Einträge.
- **Zur Laufzeit berechnete Sammlungen sieht der AST nicht — zwei
  Registrierungen lesen deshalb das echte Objekt statt des Quelltexts.**
  `_literal` löst jede Registrierung über ihren Namen im Quelltext auf und
  sieht damit nur, was dort **literal** steht. Für **40 der 42**
  Registrierungen bleibt es dabei; **zwei** lesen bewusst den Laufzeitstand:

  | Registrierung | Warum Laufzeit |
  |---|---|
  | `channel_layout.METRIC_PRIORITY` | Für die Vollständigkeitsrichtung (`soll_vollstaendig`) zählt der Stand zur Laufzeit, nicht die Schreibweise. |
  | `compare_hourly_metric_ids.HOURLY_EXCLUSION_REASON` | #1728 Scheibe 1 trägt **vier der sieben** Schlüssel per Schleife nach (`compare_hourly_metric_ids.py:84-96`). Literal gelesen prüfte die Registrierung 3 von 7 — und da Stufe 1 Schleifen ohnehin nicht sieht, entkäme ein Tippfehler in genau den vier neuen Kennungen **beiden** Stufen. |

  Gemessen (A/B an einer Kopie, `wind_chill_day_high` → `wind_chill_day_hihg`
  **nur** in der Schleife, das Literal bleibt heil): literal gelesen 3
  Kennungen sichtbar / **0 Befunde**, zur Laufzeit 7 Kennungen sichtbar /
  **1 Befund** mit Namensnennung.

  **Warum nicht alle Registrierungen so:** Laufzeit-Lesen setzt voraus, dass
  sich der Prüfling **importieren** lässt. Der Wirksamkeitsnachweis dieses
  Wächters (AC-2/AC-3) arbeitet aber mit erfundenen Wegwerf-Modulen — die
  lassen sich scannen, aber nicht sinnvoll importieren. Läse alles zur
  Laufzeit, wäre der Wächter nur noch gegen den Bestand prüfbar, und genau
  daran sind in E3a zwei Wächter gescheitert (grün, ohne je etwas geprüft zu
  haben). Der Regelfall bleibt literal; Laufzeit-Lesen ist die je Fundstelle
  begründete Ausnahme. Mechanisch festgehalten:
  `test_per_schleife_nachgetragene_schluessel_werden_mitgeprueft` wird rot,
  sobald `HOURLY_EXCLUSION_REASON` wieder literal gelesen wird (gemessen:
  Rückfall auf `_registriere` sieht 3 statt 7 Kennungen ⇒ Zusicherung
  `literal < ist` verletzt).

  **Restlücke, bewusst offen:** eine **neue**, zur Laufzeit aufgebaute
  Sammlung an anderer Stelle bleibt unsichtbar — Stufe 1 findet sie nicht,
  und ohne Fundstelle registriert sie niemand. Das Laufzeit-Lesen schließt
  die Lücke also je Eintrag, nicht als Klasse.
- **Go-Seite und Frontend** sind nicht Gegenstand: beide lesen über
  `/api/metrics` bzw. `/api/sms-symbols` aus dem Backend.
- **Eigenschaftslisten als Liste von Datensätzen** (`[{"id": "snow_depth",
  "field": "…", "unit": "…"}, …]`) statt als flaches Wörterbuch bleiben für
  die Quote-Regel unsichtbar — jeder einzelne Datensatz liegt bei
  33–50 % Quote, weit unter der 100-%-Schwelle aus Stufe 1. Diese Form
  existiert real (`src/output/renderers/compare_metric_catalog.py:77-159`,
  `src/output/renderers/email/compare_html.py:316-374`). AC-2 spricht im
  Ticket wörtlich von „Wörterbuch mit Metrik-Kennungen als Schlüssel" — die
  Lücke liegt damit außerhalb des Ticket-Wortlauts. Sie zu schließen wäre
  eine Erweiterung dieses Auftrags (eine fünfte Sammlungsform:
  „Liste von Datensätzen mit einem Kennungs-Feld"), kein Bestandteil von
  E7.

## Test-Plan (AC-Mapping)

| AC | Testdatei | Testfunktion (Name kann bei Implementierung leicht variieren) |
|---|---|---|
| AC-1 | `test_sms_token_symbol_register_ratchet.py` | 5. Prüfstelle: zwei Eindeutigkeitsprüfungen (Trip-SMS-Weg, Register-Weg), Gültigkeit läuft über AC-4 mit |
| AC-2 | `test_metrik_listen_register_ratchet.py` | AST-Scan vs. `REGISTERED_LISTS`, inkl. `HAZARD_SMS_SYMBOLS`-Gegenprobe |
| AC-3 | `test_metrik_listen_register_ratchet.py` | `test_scan_hat_pruefmaterial` (Trefferzahl `> 0` auf beiden Seiten) |
| AC-4 | `test_metrik_listen_register_ratchet.py` | parametrisiert über `REGISTERED_LISTS`, Existenz- und (opt-in) Vollständigkeitsrichtung |
| AC-5 | `test_metrik_listen_register_ratchet.py` | `test_ausnahmeliste_nur_schrumpft` + Begründungslängen-Check |
| AC-6 | `test_metrik_listen_register_ratchet.py` | protokollierter Mutationsnachweis (`METRIC_PRIORITY`, zwei Verfälschungen) + parametrisierte Struktur |
| AC-7 | `test_sms_token_symbol_register_ratchet.py` | PR-Diff-Review: vier bestehende Funktionen unverändert |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Reine Testschicht, keine Produktivcode-Änderung, keine der
  ADR-Trigger-Flächen aus CLAUDE.md (Kanäle, Provider, Datenmodell/
  Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie) betroffen.
  Die Registerherrschaft über Renderer-Vokabulare ist bereits etablierte
  Praxis (ADR-0011, fortgeführt in E1a/E1b/E3a/E3b) — E7 baut das dort
  zugesagte Werkzeug, ändert aber keine Architektur-Entscheidung.

## Changelog

- 2026-08-15: Initial spec created. Analyse aus
  `docs/context/fix-1856-e7-listen-waechter.md` übernommen, AC-1 gemäß
  Befund 1 umformuliert (Existenz/Eindeutigkeit statt Gleichheit,
  PO-Entscheide #1415/#1450/#1484/#1660 referenziert), Vollständigkeits-
  prüfung für `METRIC_PRIORITY` als begründete, opt-in Erweiterung von AC-4
  ergänzt, um Befund 2 zu einem mechanisch nachweisbaren Fang zu machen
  (Regel-Budget). Quellenangabe zur Aufzählungsfalle korrigiert: das
  vorgelegte Briefing zitierte `fix_1396_s2_store_scope_guard.md` (Go-
  Store-Scope-Wächter, anderes Thema) — die tatsächliche, durch Memory und
  Dateiinhalt bestätigte Quelle ist #1667 S1 /
  `fix_1667_s1_fixture_wanduhr.md`.
- 2026-08-15 (zweiter Durchgang): AC-1 grundlegend überarbeitet nach
  Team-Lead-Rückmeldung. Der direkte Vergleich „führendes Kürzel gegen
  Register-Kürzel" (erste Fassung) ist verworfen — er wäre nach dem ersten
  Lauf strukturell taub gewesen (fängt die drei bekannten, entschiedenen
  Abweichungen einmalig, danach nichts mehr). AC-1 prüft jetzt zwei
  getrennte Eigenschaften: Gültigkeit (fällt aus AC-2/AC-4 automatisch an,
  kein Sonderfall) und Eindeutigkeit je Ausgabeweg (Trip-SMS-Weg,
  Register-Weg, je für sich, nach Metrik-Kennung gruppiert — sonst
  Fehlalarm bei `thunder`/`TH`, s. `test_sms_snow_symbols.py:647`). Beide
  Prüfungen sind heute nachgemessen grün, brauchen also **keine**
  vorbefüllte Ausnahmeliste — das CI-Ampel-Atomaritätsrisiko im
  Regel-Budget-Abschnitt betrifft dadurch nur noch AC-4/AC-5
  (`METRIC_PRIORITY`), nicht mehr AC-1. Die drei bekannten Kürzel-
  Abweichungen sind in einen neuen Abschnitt „Hintergrund" gewandert —
  dort als Dokumentation einer PO-Entscheidung, nicht als Ergebnis einer
  Prüfung. „Parität zwischen den Wegen" als weitere verworfene Alternative
  ergänzt (gemessen: fast tautologisch, nur `confidence`/`temperature_cold`
  betroffen). Registrierung auf 18 Listen präzisiert (12 Schlüsselseite +
  6 Werteseite, mit expliziter Regel: Werteseiten-Schlüssel werden nie
  gegen das Register geprüft). Known Limitation „Datensatz-Listen"
  ergänzt (`compare_metric_catalog.py:77-159`,
  `email/compare_html.py:316-374` — Quote 33–50 % je Datensatz, für die
  Quote-Regel unsichtbar, außerhalb des Ticket-Wortlauts von AC-2).
