# Context: #1856 — #1435 E7: Wächter gegen neue Metrik-Listen

**Workflow:** `fix-1856-e7-listen-waechter` · **Track:** Full Process (Score 5) · **Basis:** `origin/main` = `ad1e6a87`
**Erstellt:** 2026-08-15 · **Termin (PO):** E7 und E6 bis 20.08., E7 zuerst

## Request Summary

Die im Epic #1435 seit 31.07. zugesagte Ratsche bauen: jede Liste, die etwas je Wettergröße
festlegt, muss mit der Register-Kennung geschlüsselt sein, und ein Wächter meldet jede Kennung,
die das Register nicht kennt — beim Namen. E7 macht Abweichungen **sichtbar und fest**; die
Abweichungen selbst behebt E6.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py:675` | `SMS_SYMBOL_BY_METRIC` — 1:1-Abbildung, wird **zusätzlich für Schwellwerte** gelesen (#624) |
| `src/app/metric_catalog.py:710` | `SMS_MULTI_SYMBOLS_BY_METRIC` — die ungeprüfte Liste aus AC-1. **Liegt im Register-Modul selbst**, nicht in `sms_trip.py` wie im Issue behauptet |
| `src/app/metric_catalog.py:~665` | `SMS_SYMBOL_GRAMMAR` — dritte Kürzel-Tabelle (`TH:`, `NS24+`, `WD:`, `PT:`) |
| `src/app/metric_catalog.py` | `COMPACT_LABEL_EXCEPTIONS` — **Vorbild für AC-5**: Ausnahmeliste, Wert = Begründungssatz, Wächter besteht auf lesbarer Begründung |
| `src/app/metric_catalog.py` | `_kurzform_kuerzel()` — die bereits existierende zentrale Auflösung „welches Kürzel benennt diese Größe" |
| `tests/unit/test_sms_token_symbol_register_ratchet.py` | **415 Zeilen**, E3b-Ratsche. Vier Prüfstellen, `EXEMPT_FORECAST_FIELDS` + `EXEMPT_METRIC_IDS`. Muss nach AC-7 **erweitert, nicht ersetzt** werden |
| `tests/unit/test_telegram_kuerzel_folgt_register.py` | **460 Zeilen**, #1719 S4. Direktes Vorbild — und Quelle des Zielkonflikts unten |
| `api/routers/config.py:44-57` | `/api/sms-symbols` — löst beide Tabellen auf, Mehrfach hat Vorrang. Deckt die Frontend-Listen ab |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | Vorbild für AST-Auflösung im Wächterbau (#1409) |

## Existing Patterns

- **Bauprinzipien der E3b-Ratsche** (im Docstring, aus zwei grünen Wächtern entstanden, die nie
  etwas prüften): kein Regex über Quelltext · keine handgepflegte Symbolliste · **Nichtstun ist
  kein Bestehen** (Trefferzahl `> 0` behaupten) · Prüfling aus **diesem** Arbeitsbaum (#1409).
  AC-3 und AC-4 schreiben genau diese Prinzipien fort.
- **Ausnahmeliste mit Pflicht-Begründung**: `COMPACT_LABEL_EXCEPTIONS` — Schlüssel = Kennung,
  Wert = Begründungssatz; ein Eintrag ohne Satz ist keine Ausnahme. Muster aus `gz-eigenstaendig`
  (#1481 B) und `gz-main-path` (#1409).
- **Schlüssel ist das Datenfeld, nicht das Symbol** (E3b, `EXEMPT_FORECAST_FIELDS`): so kann eine
  Umbenennung des Symbols die Ausnahme nicht versehentlich mitschleppen.

## Dependencies

- **Upstream:** `app.metric_catalog.get_all_metrics()` / `get_sms_code()` — 28 Register-Einträge.
- **Downstream:** Der Wächter läuft im CI-Ampel-Job `test`. Zu scharf ⇒ blockiert jeden Commit;
  zu lasch ⇒ folgenlos. Kein Produktivcode wird geändert (das ist E6).

## Existing Specs

- `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` — AC-9 ist die bestehende Ratsche (AC-7-Bezug)
- `docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md` — siehe Zielkonflikt
- `docs/adr/` — ADR-0011 trägt den E3b-Nachtrag

## Risks & Considerations

### R1 — Zielkonflikt: die im Issue gemeldeten „Widersprüche" sind teils **entschieden**

`test_telegram_kuerzel_folgt_register.py` hält wörtlich fest:

> Das Soll-Kürzel ist das, was die Trip-SMS **tatsächlich sendet** — nicht `sms_code` allein: bei
> `temperature_night` führt das Register `TN`, gesendet wird aber `N` … Genau diese zwei Fälle
> sind der Kern des gemeldeten Defekts, sie dürfen also **nicht wegdefiniert werden**.

Die Mehrfach-Kürzel tragen im Code je eine ausdrückliche PO-Entscheidung: `WC` (#1450),
`TH+:` (#1482), `N`→`temperature_night` (#1484), `FN`→`wind_chill_night` (#1660). Die Semantik
lautet laut `_kurzform_kuerzel()`: **das erste Kürzel benennt die Größe, die weiteren benennen
Auswertungen** (Tagestiefst/-höchst). „Drei Kürzel für eine Metrik" ist also nicht per se Abdrift.

⇒ Der Wächter darf nicht blind „Register ≠ gesendet" melden, sonst ist er entweder unpassierbar
oder seine Ausnahmeliste besteht aus allem. Die Spec muss **trennen**: was ist entschiedene
Mehrfach-Zuordnung (→ AC-5-Ausnahme mit Ticket-Bezug), was echte Abdrift (→ E6). Genau diese
Trennung ist der Wert, den E7 für E6 liefert.

### R2 — AC-2 ist die eigentliche Schwierigkeit und hat im Repo zwei einschlägige Fehlschläge

Die Umkehrfrage („welche Liste legt etwas je Wettergröße fest, ohne das Register zu fragen?")
verlangt einen Scan über unbekannte Strukturen. Zwei belegte Muster im Projekt:

- **#1667 S1:** Ein AST-Wächter, der erlaubte Schreibweisen **aufzählt**, wurde dreimal trivial
  umgangen (Zwischenvariable, Liste, Tupel). Behoben war die demonstrierte *Form*, nicht die
  *Klasse*. Was funktionierte: Aufzählung entfernen, stattdessen die Elternkette fragen.
- **Prüfskript-Falle:** Wer eine Struktur nicht versteht, darf **nicht Entwarnung geben**.
  „Ich finde nichts" ≠ „es gibt nichts". Plausibilitätsprüfung der Struktur **vor** der Auswertung.

Dazu die Gegenkraft aus #1667: **Falsch-Positive sind schlimmer als eine Restlücke** — ein
Wächter, der harmlose Listen meldet, wird abgeschaltet.

### R3 — Der Katalog-Wächter-Blindfleck (#1703 S1, F001)

Liest der Wächter sein Soll aus derselben Quelle wie der Prüfling, kann er Fehler **in** dieser
Quelle prinzipiell nicht sehen. **Soll-Menge** („welche Metriken gibt es?") darf gerechnet werden;
**Soll-Zuordnung** („welches Kürzel gehört zu welcher Metrik?") braucht getippte Werte, sonst ist
sie eine Tautologie. Für AC-6 (Mutationsprobe je Liste) ist das die entscheidende Unterscheidung.

### R4 — Umfang der Klasse

Grobe Stichprobe (10 von 28 Kennungen, nur Zeilenanfang-Muster) findet bereits **12 Backend-Dateien**
mit Metrik-Kennungen als dict-Schlüssel — u.a. `channel_layout.py`, `email/helpers.py`,
`metric_format.py`, `hazard_symbols.py`, `official_alerts.py`, `compare_hourly_metric_ids.py`.
Das Epic nennt ~60 handgepflegte Listen. Die vollständige Auszählung ist Aufgabe von Phase 2.

### R5b — Die Analyse-Agenten haben nicht getragen

Von vier Agenten (drei Explore/Haiku, ein Plan/Sonnet) hat **einer** berichtet, und der in der
Kernfrage falsch: Er meldete „KEINE Dateien gefunden" und „Single Source of Truth: AKTIV, kein
Drift-Risiko erkannt" — die Gegenmessung ergab **vier** Dateien mit eigenen Metrik-Listen ohne
Register-Import. Sämtliche belastbaren Zahlen dieser Analyse stammen aus eigener Messung.
Konsequenz für Phase 6: Der Adversary-Lauf muss die Zahlen selbst nachrechnen, nicht übernehmen.

### R5 — LoC-Budget

Vergleichsmaß: E3b-Ratsche 415 Zeilen, Telegram-Wächter 460 Zeilen. Das getrennte Test-Budget
(500) dürfte reichen, das Produktiv-Budget (250) wird kaum berührt — E7 ändert keinen
Produktivcode. Ausnahmelisten könnten im Katalog-Modul landen (dann Produktiv-LoC).

---

# Analysis (Phase 2, 2026-08-15)

## Type

**Feature** (Wächterbau). Label am Ticket ist `bug`, aber die Fehlerklasse ist bereits diagnostiziert;
gebaut wird die im Epic zugesagte Ratsche. Kein Produktivcode-Fix — der ist E6.

## Befund 1 — eine Prämisse des Tickets ist am Code widerlegt

#1856 behauptet, `TF` und `TN` erschienen „in **keiner** Nachricht". Gemessen:

| Ausgabeweg | Quelle des Kürzels | `wind_chill` | Beleg |
|---|---|---|---|
| Trip-SMS | `SMS_MULTI_SYMBOLS_BY_METRIC` | `FK` `FD` `WC` | `sms_trip.py` |
| **Vergleichs-SMS** | **`get_sms_code()`** | **`TF`** | `comparison.py:647`, Docstring: „AUSSCHLIESSLICH aus dem zentralen Katalog" |
| **Alarm-SMS** | **`get_sms_code()`** | **`TF`** | `alert/render.py:93` |

`TF` und `TN` sind also **live** — in zwei von drei SMS-Wegen. Bestätigt durch die Tabelle in
`docs/specs/modules/fix_1719_s4_kuerzel_vereinheitlichung.md` Zeile 70.

**Es liegen nicht drei widersprüchliche Kürzel für eine Metrik vor, sondern zwei Ausgabewege
nebeneinander** — im Epic-Zielbild genau die Unterscheidung „Eigenschaft der Größe" (Register)
gegen „Vorliebe einer Ausgabe" (lokal). Die Messung im Ticket sah nur den Trip-Weg.

⇒ **AC-1 muss umformuliert werden.** In der Ticket-Lesart („meldet jede Abweichung, schlägt heute
für `temperature`, `wind_chill`, `temperature_night` an") meldet der Wächter drei **korrekte**
Zustände als Fehler; AC-5 nähme sie alle in die Ausnahmeliste auf, und AC-1 bewachte nichts.
Vorschlag zur Freigabe → siehe „Offene Fragen".

## Befund 2 — der erste Fang, noch vor dem Wächter

`src/output/renderers/channel_layout.py:60`, `METRIC_PRIORITY` (25 Einträge, entscheidet, welche
fünf Größen bei knappem Platz in den `primary`-Bucket kommen): **`temperature_night` und
`wind_chill_night` fehlen.** Beide seit #1484/#1660 eigenständig wählbar. Zeile 131 liest
`METRIC_PRIORITY.get(metric, 0)` ⇒ Priorität 0, hinter `cloud_high` (10) und `confidence` (8).
Die Datei importiert **nichts** aus `metric_catalog`.

Das ist der Fang-Beleg, den das Regel-Budget bei Einführung verlangt.

## Befund 3 — die Kandidatenmenge, beide Richtungen gemessen

AST-Scan über `src/` + `api/`, 843 dict-Literale, **0 nicht auflösbar**:

| Richtung | Rohtreffer | davon Quote 100 % | Bedeutung |
|---|---|---|---|
| Register-Kennung als **Schlüssel** | 23 | **12** | Eigenschaft/Vorliebe je Größe |
| Register-Kennung als **Wert** | 65 | **6** | Übersetzung **ins** Register |

Die 100-%-Schwelle trennt in beiden Richtungen sauber: Auf der Werteseite bleiben genau die sechs
echten Übersetzungstabellen (`FRONTEND_TO_HOURLY_METRIC_ID`, `_SUMMARY_KEY_TO_CATALOG_ID`,
`RENDERER_TO_TRIP_METRIC_ID`, `_COL_KEY_TO_METRIC_ID`, `_FALLBACK_COL_KEY_TO_METRIC_ID`,
`_AMPEL_KEY_TO_METRIC_ID`); die übrigen 59 sind Rauschen aus Datensatz-Literalen
(`{"id": "snow_depth", "field": "snow_depth_cm", …}`). `FRONTEND_TO_RENDERER_METRIC_ID` (3/26)
fällt korrekt heraus — es übersetzt Frontend→Renderer, nicht ins Register.

**Falsch-Positiv-Prüfstein:** `HAZARD_SMS_SYMBOLS` (`output/tokens/hazard_symbols.py:15`, 10 Schlüssel
`rain`, `snow`, `thunderstorm`, `wind_gust`, …) ist das Vokabular der amtlichen Warnungen und sieht
strukturell aus wie eine Metrik-Liste. Quote gegen das Register: **0/10** ⇒ die Regel lässt sie
korrekt in Ruhe.

## Befund 4 — die Trennregel allein reicht nicht (Umgehungsprobe)

Gemessen, welche Register-Listen in **anderen Formen als dict-Literalen** existieren:

| Form | Anzahl | Beispiel |
|---|---|---|
| `set` (nur Register-Kennungen) | 7 | `email/helpers.py:1336` (7 Kennungen) |
| `list` | 10 | `metric_catalog.py:925` (14 Kennungen) |
| `tuple` | 10 | `metric_catalog.py:620` (14 Kennungen) |
| `if metric_id == "…"`-Ketten | 32 | `email/helpers.py:735` |
| dict-Comprehension | 93 | `loader.py:658` |

Ein Wächter, der nur `ast.Dict` prüft, sieht **keine** davon. Das ist die #1667-Falle in Reinform:
eine Form aufzählen, alles andere entkommt — und diese Formen sind real belegt, nicht theoretisch.

**Bewertung:** Die vier Sammlungs-Literale (dict/set/list/tuple) sind eine **geschlossene** Menge —
sie aufzuzählen ist etwas anderes als das Aufzählen von Schreibweisen in #1667. Compare-Ketten und
Comprehensions sind dagegen eine offene Klasse und gehören als benannte Known Limitation in die Spec,
nicht in eine Behauptung von Vollständigkeit.

## Befund 5 — die Weichenstellung, an der man sich verrechnet

`_METRICS` hat **28** Einträge, `get_all_metrics()` nur **25** — der Filter entfernt
`selectable=False`: `cape`, `confidence`, `temperature_cold`. Wer gegen die wählbare Menge prüft,
meldet diese drei fälschlich als „Kennung, die das Register nicht kennt". (Mir selbst im ersten
Anlauf passiert.) Der Wächter muss gegen `_METRICS` prüfen.

Verwandt: das `selectable=False`-Kollateralschaden-Muster.

## Scope Assessment

| | |
|---|---|
| Dateien | 1 neu (`tests/unit/test_metrik_listen_register_ratchet.py`), 1 geändert (E3b-Ratsche, AC-1/AC-7), ggf. Ausnahmeliste |
| LoC | ~350–450 **Test**-Budget (Vergleich: E3b 415 Z., Telegram-Wächter 460 Z.); Produktiv nur, falls die Ausnahmeliste in `metric_catalog.py` liegt |
| Risiko | **MEDIUM–HIGH** |

**Risikobegründung:** Die CI-Ampel ruft `uv run pytest` **ohne Pfadangabe** auf
(`.github/workflows/ci.yml:58`, nur `--ignore=tests/red/` + tdd-Ausschlüsse). Ein neuer Wächter unter
`tests/unit/` läuft ab Merge automatisch mit und blockiert bei Rot **jeden** PR, auch die anderer
Sessions. Er muss am Tag der Einführung grün sein ⇒ jeder heutige Fund gehört in die AC-5-Liste,
einschließlich der beiden fehlenden Größen aus Befund 2.

## Technical Approach (Empfehlung)

1. **Erkennung ohne Namensmuster und ohne Positivliste:** Eine Sammlung gilt als Register-Liste, wenn
   **alle** ihre konstanten String-Elemente (dict-Schlüssel, dict-Werte, set/list/tuple-Elemente)
   Register-Kennungen sind und es mindestens zwei sind. Keine Namensheuristik (`_X_TO_Y`), kein
   Verzeichnis-Filter — beides wäre umgehbar und würde die Klasse verfehlen.
2. **Geprüft wird Gültigkeit, nicht Zuordnung** (AC-4): Jede Kennung existiert in `_METRICS`.
   Das ist auf alle Formen anwendbar und fängt Tippfehler und gelöschte Metriken.
3. **Vollständigkeit** nur dort, wo sie fachlich gilt — für `METRIC_PRIORITY` heißt das: jede
   **wählbare** Größe hat einen Eintrag. Das ist die Prüfung, die Befund 2 fängt.
4. **AC-1 als Existenz- und Eindeutigkeitsprüfung** statt als Gleichheitsprüfung (siehe Offene Fragen).
5. **Ausnahmeliste nach dem Muster `COMPACT_LABEL_EXCEPTIONS`**: Schlüssel = Fundstelle, Wert =
   Begründungssatz mit Ticket-Bezug; ein Eintrag ohne Satz ist keine Ausnahme. Darf nur schrumpfen
   (eigener Test).
6. **Bauprinzipien der E3b-Ratsche übernehmen**: echter Import statt Regex · Trefferzahl behaupten
   (`> 0`) · Prüfling aus **diesem** Arbeitsbaum (#1409).

## Open Questions (PO-Freigabe nötig)

- [ ] **AC-1:** Die Ticket-Lesart („Abweichung Register ↔ gesendet melden") würde drei entschiedene
      Zustände als Fehler melden. Vorschlag: AC-1 prüft stattdessen (a) jede Kennung in
      `SMS_MULTI_SYMBOLS_BY_METRIC` existiert im Register, (b) kein Kürzel ist zweimal vergeben,
      (c) jede Größe mit Kürzel im einen Weg hat auch eines im anderen. Einverstanden?
- [ ] **Umfang von AC-2:** Sammlungs-Literale (dict/set/list/tuple) werden bewacht;
      `if`-Ketten und Comprehensions als Known Limitation benannt. Oder soll E7 größer werden?
- [ ] **Befund 2** (`METRIC_PRIORITY`): in die AC-5-Ausnahmeliste mit E6-Bezug — oder ist das
      nutzersichtbar genug für einen sofortigen Fix in E7?
