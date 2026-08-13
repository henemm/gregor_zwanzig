# Context: Epic #1703 Scheibe 6 — Form-Wächter über Grammatik-Klassen

## Request Summary

Epic #1703, Scheibe 6: Eigener Wächter über die SMS-Symbol-Register (`PRIORITY`,
`POSITIONAL` in `tokens/builder.py`, `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC`
in `metric_catalog.py`) — anders als Scheibe 1-5 iteriert diese Achse über **Symbole**
("Grammatik-Klassen"), nicht über Metrik-IDs. Ziel laut `docs/reference/metric_output_matrix.md`
Abschnitt 6 (Scheibe 6): jede Grammatik-Klasse hat genau eine Prioritätsstufe und eine
definierte Position; kein Kürzel kollidiert mit `HAZARD_SMS_SYMBOLS`.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/tokens/builder.py:47-65` (`PRIORITY`) | 36 Symbole → Kürzungs-Prioritätsstufe (1-11). Quelle für die meisten Symbole: `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` (Katalog) + 6 echte Systemzeichen ohne Katalogbezug (`DBG`, `AV`, `HR:`, `M:`, `MAX`, `Z:` — Debug/Fire/Vigilance). |
| `src/output/tokens/builder.py:78-99` (`POSITIONAL`, `POS_INDEX`) | 37 `(symbol, category)`-Paare, Sortier-Reihenfolge. `POS_INDEX` nutzt das Tupel als Schlüssel — `TH:` erscheint bewusst zweimal (`forecast` UND `vigilance`), abgesichert über `_POSITION_SORTABLE_CATEGORIES` (Zeile 110). |
| `src/app/metric_catalog.py:700-706` (`SMS_MULTI_SYMBOLS_BY_METRIC`) | 5 Metrik-IDs → Tupel mehrerer Kürzel (der 1:n-Strukturbruch, S6 im Sonderstrecken-Katalog): `temperature`→(K,D), `temperature_night`→(N,), `wind_chill`→(FK,FD,WC), `wind_chill_night`→(FN,), `thunder`→(TH:,TH+:). 9 eindeutige Symbole, alle bereits in `PRIORITY` vertreten. |
| `src/app/metric_catalog.py:665-668` (`SMS_SYMBOL_BY_METRIC`) | Die 1:1-Zwillingstabelle (22 Symbole: R, PR, W, G, HU, DP, WD, CP, PT, CT, CL, CM, CH, VS, SU, UV, HP, NL, SD, SL, NS24+, TH:). **Für einen vollständigen Wächter genauso Pflicht wie die Multi-Tabelle** — sonst meldet er 22 legitime Symbole fälschlich als „Waisen". |
| `src/output/tokens/hazard_symbols.py:15-26` (`HAZARD_SMS_SYMBOLS`) | Separates Register für amtliche Warnungen (10 Einträge: TH, FL, HR, W, SN, IC, HT, CD, FR, CL). Textuelle Überschneidung mit `PRIORITY`-Symbolen: exakt `W`, `CL` (und bei Doppelpunkt-Normalisierung `HR`, `TH`). |
| `src/output/tokens/builder.py:199-222` (`_vigilance()`, `_official_alerts()`) | Amtliche-Warnungen-Rendering nutzt FESTE `category`/Priorität, **nicht** `PRIORITY[symbol]`/`POS_INDEX[symbol]` — Kollisionsschutz ist strukturell in `render.py` über `category`-Branch verankert, nicht über Namensraum-Trennung der Kürzel selbst. |
| `src/output/tokens/builder.py:333-344` (`_gap_or()`, Wind-Token-Bau) | **Live-Kollision, verifiziert:** Ein Wind-Datenausfall rendert `Token("W", "?", ...)` → `Token.render()` (`dto.py:130-135`) gibt `f"{symbol}{value}"` = **„W?"** zurück — bytegleich mit `UNAVAILABLE_SYMBOL = "W?"` (`builder.py:74`, Bedeutung „amtliche Warnungen nicht abrufbar"). Beide Bedingungen sind unabhängig voneinander auslösbar; die resultierende SMS-Zeile ist für den Leser nicht unterscheidbar. |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` (331 Zeilen) | Bestehender Ratschen-Test — prüft NUR den Wintersport-Block + `SMS_SYMBOL_BY_METRIC` gegen `get_sms_code()`. Importiert `HAZARD_SMS_SYMBOLS` an keiner Stelle (verifiziert per Grep) — keine Kollisionsprüfung, keine Vollständigkeitsprüfung von `PRIORITY`/`POSITIONAL` als Ganzes. |
| `tests/tdd/test_channel_metric_matrix.py` (3663 Zeilen) | Bestehender Matrix-Wächter S1-S5, durchgehend über `get_all_metrics()`/Metrik-IDs parametrisiert — strukturell nicht das richtige Zuhause für eine symbol-basierte Achse (s. Analysis). |

## Existing Patterns

- **Option C bleibt gültig** (Erweiterung eines budgetierten Gates, kein neues Pflicht-Gate) —
  aber die Matrix-Doku selbst legt für Scheibe 6 fest: „Form-Dimension als eigene Achse, **nicht
  in die Hauptmatrix gemischt**" (Abschnitt 7b, PO-entschieden). D.h. eine neue, eigenständige
  Testdatei ist hier die vom Dokument selbst vorgesehene Lösung, kein Abweichen vom Muster.
- **„Rechnen statt tippen"** (S1-S5-Lehre): Soll-Mengen aus den Produktivmodulen selbst ableiten
  (`PRIORITY.keys()`, `SMS_MULTI_SYMBOLS_BY_METRIC.values()`, `SMS_SYMBOL_BY_METRIC.values()`),
  nie eine eigene Symbolliste tippen.
- **Vorbild-Ratschenmuster** bereits im Repo: `test_sms_token_symbol_register_ratchet.py`
  (echte Importe statt Regex, Vakuum-Schutz `> 0`, Prüfling aus dem eigenen Worktree #1409) —
  dieselben Bauprinzipien gelten für den neuen Wächter.

## Dependencies

- **Upstream:** `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` (metric_catalog.py) als
  Soll-Symbolquelle; `PRIORITY`/`POSITIONAL`/`POS_INDEX` (builder.py) als Prüfling;
  `HAZARD_SMS_SYMBOLS` (hazard_symbols.py) als zweites, unabhängiges Register.
- **Downstream:** `render.py` (Fusion/Kürzung/Sortierung liest `PRIORITY`/`POS_INDEX`),
  `_official_alerts()`/`_vigilance()` (Rendering der Warn-Tokens mit fester Kategorie).

## Existing Specs

- `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` (AC-9) — Spec des bestehenden
  Ratschen-Tests, Vorbild für Bauprinzipien.
- `docs/reference/metric_output_matrix.md` Abschnitt 3 (Sonderstrecken-Katalog S1-S6, insb.
  S6 = `SMS_MULTI_SYMBOLS_BY_METRIC`), Abschnitt 5 Punkt 1 (Form-Dimension-Entscheidung),
  Abschnitt 6 (Scheibe-6-Text), Abschnitt 7 PO-Entscheidung (b).

## Risks & Considerations

- **Verifizierter, LIVE erreichbarer Fund (kein Verdacht):** `W?` entsteht sowohl bei einem
  Wind-Datenausfall (`_gap_or()`, `builder.py:333-344`) als auch als dedizierter
  `UNAVAILABLE_SYMBOL` für „amtliche Warnungen nicht abrufbar" — **bytegleich**, in derselben
  SMS-Zeile möglich, für den Leser nicht unterscheidbar. Beide Bedingungen sind unabhängig
  voneinander wahr/falsch. Das ist eine Sicherheits-relevante Ambiguität (könnte verschleiern,
  dass amtliche Warnungen nicht abrufbar waren), nicht nur kosmetisch — anders als der
  Em-Dash/Hyphen-Fund aus Scheibe 5. **Muss der Spec als eigener, klar benannter Befund
  vorgelegt werden — PO-Entscheidung nötig: charakterisieren oder fixen (z. B. distinktes
  Symbol für `UNAVAILABLE_SYMBOL`)?**
- **Verifizierter, aber toter Fund:** `TH:`/`HR:` kollidieren strukturell zwischen
  `HAZARD_SMS_SYMBOLS` (amtliche Warnung) und `VIGI_TH`/`VIGI_HR` (Météo-France-Vigilance,
  `_vigilance()`) — beide würden bei Level+Stunde identisch als `{symbol}:{level}@{hour}`
  rendern. Nachgemessen: **kein** produktiver `NormalizedForecast(...)`-Aufruf setzt
  `provider="meteofrance"` (Default `"open-meteo"`, `dto.py:76`) — `_vigilance()` liefert im
  Live-Pfad immer `[]`. Analog zu `CorridorEvent`/`OnsetEvent` aus Scheibe 1: benannter,
  unbewachter toter Pfad, kein Fix nötig, aber zu dokumentieren (Grenzen-Abschnitt).
- **`W`/`CL` sind format-sicher** (nachgemessen über `Token.render()`): amtliche Warnungen
  tragen immer ein `:`-Suffix bei Stufe bzw. bleiben bar bei levellosen Hazards (`access_ban`),
  Forecast-Token tragen immer einen numerischen Wert oder `-`/`?`. Keine echte Textkollision
  im heutigen Renderpfad — aber die Trennung ist eine **Format-Invariante**, keine
  **strukturelle Namensraum-Trennung**: ein künftiger Formatwechsel könnte sie stillschweigend
  aufheben, ohne dass ein Test es bemerkt.
- **Zwei Referenztabellen nötig, nicht eine:** Ein Wächter, der nur gegen
  `SMS_MULTI_SYMBOLS_BY_METRIC` prüft, meldet die 22 `SMS_SYMBOL_BY_METRIC`-Symbole und die 6
  echten Systemzeichen (`DBG`, `AV`, `HR:`, `M:`, `MAX`, `Z:`) fälschlich als unzugeordnet —
  beide Register + eine benannte Systemzeichen-Ausnahmeliste sind Pflicht.
- **Testort-Frage vorentschieden, nicht offen:** Die Matrix-Doku selbst (PO-Entscheidung b)
  sagt „eigene Achse, nicht in die Hauptmatrix" — spricht für eine **neue, eigenständige
  Testdatei**, nicht für `AC-S6-*` in `test_channel_metric_matrix.py`. Zu bestätigen in der
  Spec, aber keine offene Designfrage mehr.
- **Risiko laut Matrix-Dokument: niedrig-mittel. Größe: klein-mittel.** Durch den `W?`-Fund
  tendenziell am oberen Ende dieser Spanne, nicht am unteren.

## Analysis

### Type
Feature (neuer, eigenständiger Test-Wächter) mit einem eingebetteten, echten Bug-Kandidaten
(`W?`-Doppelbedeutung) — die Spec muss für diesen Teil explizit Charakterisierung vs. Fix
entscheiden, analog zu den PO-Entscheidungen in Scheibe 4/5.

### Bestätigter Kernbefund (eigene Nachrecherche, mit Code-Zeilen verifiziert)

1. **Vollständigkeits-Achse ist unproblematisch:** Alle 9 Multi-Symbole stecken in `PRIORITY`;
   alle `PRIORITY`-Symbole haben einen `POSITIONAL`-Eintrag (Ausnahme `UNAVAILABLE_SYMBOL`,
   bewusst — nutzt eine eigene Konstante statt `PRIORITY[...]`). Kein Fix nötig, reine
   Charakterisierung wie S1/S3.
2. **`W?`-Kollision ist real und live** — unabhängig voneinander auslösbar, bytegleiches
   Ergebnis, sicherheitsrelevant (verschleiert ggf. Warnungs-Ausfall). Größter Einzelfund
   dieser Scheibe.
3. **`TH:`/`HR:`-Kollision ist real, aber strukturell tot** (kein Aufrufer aktiviert
   `provider="meteofrance"`) — Charakterisierung als benannte Grenze, kein Fix.
4. **`W`/`CL` sind heute sicher, aber nur durch eine Format-Invariante, nicht durch
   Namensraum-Trennung** — ein Wächter sollte das als Regressions-Schutz festhalten (Vorbild
   AC-S2-8-Mutationsdenken: welche Änderung würde die Trennung stillschweigend aufheben?).

### Affected Files (voraussichtlich)
| File | Change Type | Description |
|------|-------------|--------------|
| `tests/unit/test_sms_symbol_grammar_classes.py` (Name vorläufig) | CREATE | Neue, eigenständige Testdatei — Vollständigkeit (PRIORITY/POSITIONAL/Multi+Single-Tabellen), Kollisionsprüfung gegen HAZARD_SMS_SYMBOLS inkl. Format-Invarianten, W?-Charakterisierung/Fix je nach PO-Entscheidung. |
| `docs/specs/modules/fix_1703_s6_form_waechter.md` | CREATE | Spec analog S1-S5. |
| `docs/reference/metric_output_matrix.md` | MODIFY | Scheibe 6 nach Abschluss auf erledigt umtragen (DoD). |
| `src/output/tokens/builder.py` (`UNAVAILABLE_SYMBOL`) | MÖGLICH, PO-Entscheidung nötig | Nur falls die W?-Kollision gefixt statt charakterisiert wird (z. B. neues, kollisionsfreies Symbol). |

### Scope Assessment
- Files: 2-4 (neue Testdatei, Spec, Matrix-Dokument-Update, ggf. 1 Zeile Produktivcode bei
  Fix-Entscheidung zu W?)
- Estimated LoC: Testcode ~150-250 Zeilen (kleiner als S2/S4/S5 — die Symbolmenge ist klein,
  ~36-46 Symbole gesamt, keine 25er-Metrik-Vollparametrisierung nötig)
- Risk Level: MEDIUM — wegen des echten, sicherheitsrelevanten W?-Fundes höher als die
  Matrix-Doku ursprünglich einschätzte ("niedrig-mittel")

### Technical Approach (Empfehlung)

**Primär Charakterisierung + Vollständigkeitswächter, mit EINER offenen Fix-Frage (W?).**
Die Vollständigkeits-/Positions-Prüfung (Punkt 1 oben) ist reine Charakterisierung wie
S1/S3 — kein strukturelles Problem gefunden. Die `TH:`/`HR:`-Kollision wird wie
`CorridorEvent`/`OnsetEvent` in S1 als benannte, tote Grenze dokumentiert, nicht gefixt.

Die `W?`-Kollision braucht eine PO-Entscheidung, die die Spec vorlegt (nicht selbst
entscheidet): (a) charakterisieren (Ist-Zustand bewachen, Nebenbefund-Eintrag #1199) oder
(b) fixen (z. B. `UNAVAILABLE_SYMBOL` auf ein garantiert kollisionsfreies Kürzel ändern —
das wäre ein winziger, gezielter Produktivcode-Fix außerhalb des sonst reinen
Charakterisierungs-Musters dieser Epic-Scheiben, aber laut CLAUDE.md-Nebenbefund-Triage
Kriterium (b) „Sicherheitsrisiko" ein Kandidat für sofortige Behebung statt Sammel-Eintrag).

### Open Questions (für Spec-Freigabe zu klären)

- [ ] **(a) `W?`-Kollision:** Charakterisieren oder fixen? Empfehlung: **fixen** — anders als
      der kosmetische Em-Dash/Hyphen-Fund aus S5 betrifft dieser Fund die Erkennbarkeit eines
      Warnungs-Ausfalls, ein Sicherheitsrisiko nach CLAUDE.md-Kriterium (b). Kleinstmöglicher
      Fix: `UNAVAILABLE_SYMBOL` auf ein Kürzel ändern, das strukturell (nicht nur zufällig)
      mit keinem Wetter-Symbol kollidieren kann (z. B. ein Zeichen außerhalb des
      Wetter-Symbol-Alphabets). Zu verifizieren: gibt es Bestandstests, die exakt `"W?"` als
      String erwarten (Byte-Golden), die ein Symbolwechsel bräche?
- [ ] **(b) Testort:** Neue eigenständige Testdatei (Empfehlung, siehe Matrix-Doku-Entscheidung
      b) — zu bestätigen, Namensvorschlag `tests/unit/test_sms_symbol_grammar_classes.py`.
- [ ] **(c) `TH:`/`HR:`-Vigilance-Kollision:** Nur als Known Limitation dokumentieren (Analog
      CorridorEvent/OnsetEvent), da strukturell toter Pfad — keine offene Frage, sondern
      Empfehlung zur Bestätigung.

## Related Non-Scope

- Scheibe 7 (Reihenfolge jenseits E-Mail/Telegram-rich) — andere Fläche, blockiert bis 7a.
- Scheibe 8 (Compare-Kanal-Tabs Frontend) — kein Bezug zu SMS-Symbolen.
- Alle Metrik-ID-basierten Achsen (S1-S5) — diese Scheibe iteriert bewusst über Symbole, nicht
  über Metrik-IDs; kein Duplikat der bestehenden Achsen.
