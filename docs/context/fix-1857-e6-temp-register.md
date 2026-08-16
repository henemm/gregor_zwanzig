# Context: fix-1857-e6-temp-register

**Issue:** #1857 — „#1435 E6: Temperatur-Kürzel ins Register, Legende in die Oberfläche, Feldname klären"
**Epic:** #1435 · **Vorgänger:** #1856 (E7, geschlossen, live `94aa6fcd`)
**Erhoben:** 2026-08-15, Track Full Process

## Request Summary

Die SMS-Kürzel der Temperatur-Familie sollen aus einer zweiten Tabelle ins zentrale Register
zurückgeführt werden (AC-1/AC-2), die Oberfläche soll erklären, was ein Kürzel bedeutet (AC-3/AC-5),
und der irreführende Feldname `wind_chill_c` soll geklärt werden (AC-4) — alles ohne den Inhalt
zugestellter Kurznachrichten zu verändern (AC-6).

## 🔴 Der Ticket-Text ist an drei Stellen überholt

Der Body von #1857 entstand **2026-08-15 07:22 Uhr**. Danach gingen zwei Scheiben von #1728 live:
**S1 um 10:52** (`5056726a`) und **S2 um 16:34** (`0fe1c6e2`). Beide fassen genau diese Metriken an.

| Aussage im Ticket | Gemessener Stand |
|---|---|
| `SMS_MULTI_SYMBOLS_BY_METRIC` liegt in `sms_trip.py` | **Falsch.** Liegt seit #1719 S4 in `metric_catalog.py:778-787`; `sms_trip.py:23-24` ist nur noch Re-Export (Zirkelimport-Vermeidung) |
| Der Wächter kennt die Mehrfach-Tabelle nicht | **Überholt.** #1856 (E7) hat sie aufgenommen; `tests/helpers/metrik_listen_scan.py` führt 42 Registrierungen |
| Die Kürzel `K`/`D`/`FK`/`FD` hängen an `temperature`/`wind_chill` | **Überholt.** #1728 S1 hat vier eigene Größen eingeführt, die sie tragen |

**Konsequenz:** Die Analyse-Phase misst den Ist-Stand neu, statt die Ticket-Tabelle zu übernehmen.
Das ist in dieser Epic-Reihe zum dritten Mal nötig (vorher: toter Code in E3a, Wintersport-Pfad in E3b).

## Gemessener Ist-Stand: Register vs. Versand

Quelle: `src/app/metric_catalog.py` — Feld `sms_code` je `MetricDefinition` gegen
`SMS_MULTI_SYMBOLS_BY_METRIC` (`:778-787`).

| Metrik | `sms_code` (Register) | Mehrfach-Tabelle | Bewertung |
|---|---|---|---|
| `temperature` | `D` | — | ⚠️ Altlast: belegt `D`, sendet aber selbst nichts (→ G4/G5) |
| `temperature_day_low` | `K` | `("K",)` | ✅ deckungsgleich |
| `temperature_day_high` | `TD` | `("D",)` | 🔴 **Abweichung** |
| `temperature_night` | `TN` | `("N",)` | 🔴 **Abweichung** |
| `wind_chill` | `TF` | `("WC",)` | 🔴 **Abweichung** |
| `wind_chill_day_low` | `FK` | `("FK",)` | ✅ deckungsgleich |
| `wind_chill_day_high` | `FD` | `("FD",)` | ✅ deckungsgleich |
| `wind_chill_night` | `FN` | `("FN",)` | ✅ deckungsgleich |
| `thunder` | `TH` | `("TH:", "TH+:")` | Grammatik-Ausnahme (dokumentiert seit E3b) |

**Drei echte Abweichungen** — dieselbe Anzahl wie im Ticket, aber teils an anderen Kennungen.
`TD` und `TN` erscheinen in keiner Nachricht; `TF` erscheint als Telegram-Spaltenkopf
(`compact_label`, per `COMPACT_LABEL_EXCEPTIONS` fest verdrahtet), nicht in der SMS.

⚠️ Die Zeile zu `temperature` war in der ersten Fassung als sichtbare Kollision notiert — die
Messung in G4 widerlegt das. Sie bleibt relevant als **Blockierer der Lösungsrichtung** (G5).

## Related Files

### Backend — Register & Kürzel

| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py:27-87` | `MetricDefinition`, 30 Felder inkl. `sms_code`, `compact_label`, `col_label` |
| `src/app/metric_catalog.py:92-653` | `_METRICS` — das Register selbst |
| `src/app/metric_catalog.py:738-741` | `SMS_SYMBOL_BY_METRIC` — **abgeleitet**, nicht gepflegt |
| `src/app/metric_catalog.py:778-787` | `SMS_MULTI_SYMBOLS_BY_METRIC` — **die zweite Tabelle, um die es geht** |
| `src/app/metric_catalog.py:1207-1213` | `get_sms_code()` |
| `src/output/renderers/sms_trip.py:23-24` | Re-Export beider Tabellen |
| `src/output/renderers/trip_report.py:316-317, 412-421` | Ableitung `disabled_sms_specs`; `_AGG_GATE_SYMBOLS` **entfallen** (S1) |
| `src/output/tokens/builder.py:52, 109, 273` | Erzeugt `WC` im Wintersport-Block |
| `api/routers/config.py:30-69` | `/api/sms-symbols` — DTO `{metrics:[{metric_id, sms_symbols[]}], hazards:[…]}` |

### Frontend — Kürzel-Anzeige

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:478` | Lädt `/api/sms-symbols` |
| `…/WeatherMetricsTab.svelte:1216-1238` | **Vorbild für AC-3:** `official-alerts-symbol-legend` — `<code>Symbol</code> Bedeutung`, fail-soft |
| `…/WeatherMetricsTab.svelte:1575-1745` | Abschnitt „04 — Schwellwerte", 7× `ThresholdMetricRow` + 8× `MultiSymbolMetricRow` |
| `…/weather-metrics-tab/ThresholdMetricRow.svelte:37` | Einzel-Kürzel als `<code>` |
| `…/weather-metrics-tab/MultiSymbolMetricRow.svelte:20-21` | Mehrfach-Kürzel als `<code>`-Reihe |
| `…/weather-metrics-tab/WeatherV2Reihenfolge.svelte:115-126, 168-178` | Marken „Mail" (`col_label`) + „Kurzform" (`sms_symbols`), mit `title`-Tooltips |

### `wind_chill_c` — Feldname

| Datei | Relevanz |
|---|---|
| `src/providers/openmeteo.py:394` | `"apparent_temperature": "wind_chill_c"` — **die Fehlbenennung, ohne Kommentar** |
| `src/providers/openmeteo.py:910` | Zuweisung |
| `src/providers/geosphere.py:129, 552, 573` | 🔴 Berechnet **echten** Wind Chill (nordamerikanische Formel, nur T ≤ 10 °C) |
| `src/app/models.py:128` | `ForecastDataPoint.wind_chill_c` — **persistiert** |
| `src/app/models.py:436-439` | `wind_chill_min_c` / `wind_chill_max_c` (Tages-Aggregat) |
| `internal/model/forecast.go:60` | `WindChillC *float64 \`json:"wind_chill_c,omitempty"\`` — **API-Vertrag** |
| `internal/model/segment.go:18` | `WindChillMinC` |

## Existing Patterns

- **Kürzel werden abgeleitet, nicht gepflegt.** `SMS_SYMBOL_BY_METRIC` rechnet aus `get_sms_code()`
  (E3b). Der Weg für AC-1 ist derselbe: die Mehrfach-Tabelle aus dem Register ableiten.
- **Schichtgrenze `src/output/tokens/` → `src/app/`:** Der Token-Ordner importiert **nichts** aus
  `src/app/` — Absicht seit E3b. Übereinstimmung wird über eine **Ratsche in der Testschicht**
  gesichert (`tests/unit/test_sms_token_symbol_register_ratchet.py`), nicht per Import.
  **Das begrenzt, was AC-1 überhaupt tun kann.**
- **Legenden-Muster:** `official-alerts-symbol-legend` — bedingtes Rendern auf geladene Symbole,
  `<ul>` mit `<code>` + Klartext. Direkt übertragbar auf Metrik-Kürzel.
- **Ausnahmelisten mit Ticket-Bezug** (AC-5 des Vorgängers): Marker `# gz-fremdvokabular: <Grund>`
  (≥15 Zeichen + Ticket-Nummer) bzw. Einträge in `REGISTERED_LISTS`
  (`tests/helpers/metrik_listen_scan.py:354-400`).
- **Geteilte Bausteine:** `ThresholdMetricRow`, `MultiSymbolMetricRow`, `WeatherV2Reihenfolge`,
  `WeatherMetricsTab` liegen alle in `shared/` mit `context: 'route' | 'vergleich'`. Eine
  Kürzel-Legende **muss** dort entstehen, nicht als Compare- oder Trip-Sonderweg.

## Dependencies

**Upstream:** `metric_catalog._METRICS` · `/api/sms-symbols` · `/api/compare/metrics` (liefert
`sms_code` für die drei Vergleichs-Flächen — andere Quelle als Trip!)

**Downstream:** SMS-/Premium-SMS-/Telegram-Renderer · Trip-Editor · Compare-Editor ·
Ausblick-Layout · die beiden Ratschen aus E3b und E7

**Ticket-Abhängigkeiten:**

| Issue | Stand | Bedeutung für E6 |
|---|---|---|
| #1856 (E7) | ✅ geschlossen, live | Liefert den Wächter, der die Abweichungsliste erzeugt |
| #1728 | 🟡 offen — S1+S2 live, **S3 als PR #1884 offen** | 🔴 **Echter Blocker.** Der PR fasst `metric_catalog.py`, `metrik_listen_scan.py` und `WeatherMetricsTab.svelte` an — alle drei Kern-Dateien von E6. Details in G7 |
| #1848 | offen | Vereinheitlicht Compare-/Ausblick-Vokabular. Thematisch benachbart, **eigenständig** — AC-1 hier betrifft nur die SMS-Kürzel |
| #1450 | ✅ **behoben** | Das Profil-Gate ist entfernt, Wintersport-Kürzel werden erzeugt. **Kehrt die Prämisse von AC-5 um** → G1 |

## Existing Specs

- `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` — Vorgänger-Muster für Kürzel-Ableitung
- `docs/specs/modules/feat_1728_s1_temp_aufloesung.md` (16 ACs) / `feat_1728_s2_editor.md` (12 ACs)
- `docs/specs/modules/fix_1472_spaltenkuerzel_legende.md` — Legende in der **Mail** (#1472, geschlossen);
  E6 AC-3 betrifft die **Oberfläche**, nicht die Mail
- `docs/reference/metric_output_matrix.md` — ⚠️ nennt zweimal den veralteten Namen `_NIGHT_SCALAR_IDS`
  (Nachlauf aus E7)
- ADR-0042 (Namensform folgt der Platzgrenze), ADR-0050 (Kanal-Ebene darf nur abwählen)

## Risks & Considerations

### R1 — AC-6 (Bestandsschutz) kollidiert mit AC-1/AC-2 🔴

Die drei Abweichungen aufzulösen heißt zu entscheiden, **welche Seite gewinnt**. Gewinnt das
Register, ändert sich der gesendete Text (`D`→`TD`, `N`→`TN`, `WC`→`TF`) — das verletzt AC-6
direkt. Gewinnt der Versand, muss `sms_code` im Register geändert werden — dann kollidiert
`temperature_day_high` (`D`) mit `temperature` (`D`). **Das ist die zentrale Designfrage der Spec,
und sie braucht wahrscheinlich einen PO-Entscheid.**

### R2 — `wind_chill_c` umbenennen ist ein Daten-Schema-Rework

Gemessen: **166 Dateien, >840 Fundstellen** (`src/` 18/31 · Go 2/2 · `frontend/src/` 20/128 ·
`tests/` 126/680). Das Feld ist **persistiert** (`models.py:128`) und trägt einen **Go-JSON-Tag**
(`forecast.go:60`) — Umbenennung = Migrationspflicht nach CLAUDE.md. AC-4 erlaubt ausdrücklich die
Kommentar-Variante. **Empfehlung für die Analyse: Kommentar, nicht Umbenennung.** Der Aufwand steht
in keinem Verhältnis, und das Risiko-Profil (Read-Modify-Write, BUG-DATALOSS-GR221) ist bekannt teuer.

### R3 — Zwei Provider legen fachlich Verschiedenes in dasselbe Feld 🔴 (nicht im Ticket)

Open-Meteo liefert `apparent_temperature` (ganzjährig, mit Feuchte und Strahlung). Geosphere
**berechnet echten Wind Chill** (nordamerikanische Formel, nur T ≤ 10 °C, Wind ≥ 4,8 km/h) —
`geosphere.py:552, 573`. Der Feldname ist also nicht bloß irreführend: **je nach Provider steht dort
eine andere Größe.** Ein Kommentar, der nur „enthält apparent_temperature" sagt, wäre für den
Geosphere-Pfad schlicht falsch. Instanz von „gleicher Name, anderes Zeitfenster" — hier: gleicher
Name, andere Formel.

### R4 — Wirkt `WC` überhaupt? (AC-5)

`WC` entsteht in `src/output/tokens/builder.py:273` im Wintersport-Block. Laut E3b-Befund ruft
`sms_trip.py:417` `build_token_line()` **ohne** `profile=` auf; einziger Aufrufer mit
`profile="wintersport"` ist die Legacy-CLI (→ #1450). **Ist das noch so, ist `WC` in keiner
zugestellten Nachricht** und AC-5 löst sich zur Streichung auf. Muss an der zugestellten Ausgabe
gemessen werden, nicht am Quelltext.

### R5 — PO-Entscheid aus #1728 steht möglicherweise gegen AC-5

#1728 hält als PO-Entscheid E3 fest: **„WC bleibt an `wind_chill`"**. AC-5 stellt das Kürzel wieder
zur Disposition. Vor einem Vorschlag zur Streichung ist zu klären, ob der Entscheid noch gilt oder
sich nur auf die S1-Zuordnung bezog.

### R6 — Der Wächter bewacht Vollständigkeit, nicht Zuordnung

`tests/helpers/metrik_listen_scan.py` liest sein Soll aus demselben Register wie der Prüfling.
Vertauscht jemand zwei `sms_code`-Werte **im Register**, bleibt er grün. Für AC-2 („keine Abweichung
mehr") braucht es einen zweiten, bewusst redundanten Wächter mit **getippten** Erwartungswerten —
sonst ist die Zusicherung eine Tautologie.

### R7 — Wer ein Kürzel ändert, muss die Tests suchen, die es als Selektor benutzen

Aus #1719 S4: Ein Bestandstest wählte seine Zeile am Zeichen `⚡` und traf nach der Umstellung still
die falsche Zeile. **`grep` nach dem alten Kürzel, nicht nur nach dem Metriknamen.**

### R8 — Zuschnitt

Backend-Register (AC-1/AC-2/AC-4) und Frontend-Legende (AC-3/AC-5) sind zwei getrennte Schichten mit
getrennten Nachweiswegen. #1728 wurde aus demselben Grund in S1/S2/S3 zerlegt. Ein Scheiben-Schnitt
ist wahrscheinlich — er gehört in `/20-analyse`, mit eigener Issue-Nummer je Scheibe.

---

# Analysis (Phase 2, 2026-08-15)

## Type

**Bug** (Label `bug`) — aber inhaltlich Aufräumarbeit an einer Entscheidungsfläche, kein Fehlverhalten,
das ein Nutzer als Defekt meldet. Kein nutzersichtbarer Ausfall; die Kosten sind Verwechslungsgefahr
und Wartungsaufwand.

## Was gemessen wurde (nicht gelesen)

### G1 — `WC` steht in jeder ausgelieferten Trip-SMS 🔴 Ticket-Prämisse widerlegt

Gemessen am echten Renderer (`SMSTripFormatter().format_sms()`, offline, ohne Mocks):

```
Stubaier: N2 D2/6 FN-6 FD-6/-1 R- PR- W25@8 G- TH:- TH+:- WC-6
```

**Grund:** Issue #1450 **ist behoben** — das Profil-Gate wurde ersatzlos entfernt,
`build_token_line()` hat heute **keinen `profile`-Parameter mehr**. Die Annahme in AC-5
(„#1450 legt nahe, dass der Briefing-Pfad gar keine Wintersport-Kürzel erzeugt") beschreibt den
Zustand **vor** dem Fix. Auch die Projekt-Memory zu E3b ist an dieser Stelle veraltet.

Sichtbarkeit steuert allein die An-/Abwahl von „Gefühlte Temperatur" (`_visible()`,
`builder.py:129`) — kein Wintersport-Schalter. `default_enabled=True`.

Premium-SMS versendet denselben Text (kein zweiter Renderer). Ortsvergleichs-SMS und Alarm-SMS
erreichen `WC` **nicht** (kein Import von `build_token_line`).

### G2 — `WC` verdoppelt exakt den Wert von `FK` 🔴 nicht im Ticket

Im Beleg oben: `FD-6/-1` ist der verschmolzene Tagesbereich (FK = −6, FD = −1), `WC-6` zeigt
**dieselbe −6**. `WC` liest `day.wind_chill_c`, das in `sms_trip.py:471` als `felt_min` gesetzt wird —
also derselbe Wert, den `FK` trägt.

**Das ist die belegte Antwort auf die PO-Frage:** `WC` ist nicht „noch eine Größe", sondern eine
Wiederholung der gefühlten Tages-Tiefsttemperatur unter einem englischen Namen. Es kostet
Zeichen im 160er-Budget, ohne Information hinzuzufügen.

### G3 — Die gesendeten Kürzel stehen als Literale, nicht im Register

`TD`, `TN`, `TF` kommen in `src/output/tokens/*.py` **null Mal** vor (gemessen per grep).
Die gesendeten Zeichen stammen aus Literalen in `src/output/tokens/builder.py`:

| Kürzel | Literal | Metrik |
|---|---|---|
| `N` | `builder.py:320` | `temperature_night` |
| `K` | `builder.py:321` | `temperature_day_low` |
| `D` | `builder.py:322` | `temperature_day_high` |
| `FN` | `builder.py:323` | `wind_chill_night` |
| `FK` | `builder.py:324` | `wind_chill_day_low` |
| `FD` | `builder.py:325` | `wind_chill_day_high` |
| `WC` | `builder.py:273` | `wind_chill` |

Das ist **Absicht, keine Schlamperei**: `src/output/tokens/` importiert bewusst nichts aus
`src/app/` (Schichtgrenze seit E3b). Die Übereinstimmung sichert eine Ratsche in der Testschicht.
**AC-1 kann diese Literale nicht auflösen, ohne die Schichtgrenze zu brechen.**

### G4 — Die `D`-Kollision wirkt nicht (Korrektur zur Kontext-Phase)

`temperature` steht in **keiner** der beiden Kürzel-Tabellen und erscheint deshalb weder in
`/api/sms-symbols` noch in `disabled_sms_specs`. Kein Nutzer sieht zwei Zeilen mit `D`.
Der veraltete `sms_code="D"` am Eintrag `temperature` ist trotzdem relevant — siehe G5.

Unabhängig davon vorbestehend: `/api/compare/metrics` liefert `sms_code="D"` für **zwei** Zeilen
(`temperature_max`, `temperature_min`). Anderer Fall, nicht Teil von E6.

### G5 — Die Auflösungsrichtung: gemessene Kosten beider Optionen

| | (a) Register ans Gesendete angleichen | (b) Gesendetes ans Register angleichen |
|---|---|---|
| Tests rot (gemessen) | **3** | ≥44 Zusicherungsstellen in 7 Dateien (75 Tests, Baseline grün) |
| Zugestellte Trip-SMS ändert sich | **nein** | **ja** — `N11 D3/20` → `TN11 TD3/20` |
| Zeichenbudget (160) | unberührt | belastet, längere Kürzel |
| Compare-SMS-Zelle | `wind_chill`: `TF` → `WC` | unberührt |
| Telegram-Spaltenkopf | **keine** (gemessen: `_kurzform_kuerzel()` ignoriert `sms_code`, wenn die Mehrfach-Tabelle greift) | keine |

**(b) verletzt AC-6 direkt** („Inhalt bleibt für Bestandsnutzer unverändert"). Damit ist (a) die
einzige Richtung, die das Ticket zulässt.

**Aber (a) hat einen Blockierer:** `temperature.sms_code == "D"` (`:113`) und
`temperature_cold.sms_code == "N"` (`:127`) belegen die Zielwerte bereits. Drei Tests bewachen die
globale Eindeutigkeit von `sms_code`. **Ohne diese beiden Altlasten aufzulösen, ist (a) nicht
durchführbar.** Beide sind Rückstände: `temperature` ist seit #1728 S1 nicht mehr die
Tages-Höchst-Größe, `temperature_cold` ist eine Alarm-Pseudogröße (`selectable=False`).

### G6 — `wind_chill_c`: zwei Provider, zwei verschiedene Größen

| Provider | Datei:Zeile | Was landet im Feld |
|---|---|---|
| Open-Meteo | `openmeteo.py:394, 910` | `apparent_temperature` — ganzjährig, mit Feuchte und Strahlung |
| Geosphere | `geosphere.py:129, 552, 573` | **berechneter echter Wind Chill** — nordamerikanische Formel, nur T ≤ 10 °C, Wind ≥ 4,8 km/h |

Der Feldname ist also nicht bloß irreführend — **je nach Provider steht dort eine andere Größe**.
Ein Kommentar, der nur „enthält apparent_temperature" sagt, wäre für den Geosphere-Pfad falsch.

Umbenennung gemessen: **166 Dateien, >840 Fundstellen**; Feld ist persistiert (`models.py:128`) und
trägt einen Go-JSON-Tag (`forecast.go:60`) ⇒ Daten-Schema-Rework mit Migrationspflicht.
**Empfehlung: Kommentar, keine Umbenennung** — AC-4 erlaubt das ausdrücklich.

### G7 — #1728 S3 ist ein offener PR, kein theoretischer Hinweis

PR **#1884** (Branch `worktree-intake-1728`, Commit `ac8501f5`, 2026-08-15 20:33 UTC), Status offen,
4/6 Checks grün (`test`, `e2e` laufen).

| Datei | von S3 angefasst | von E6 gebraucht |
|---|---|---|
| `src/app/metric_catalog.py` | −14 | ✅ Kern von Scheibe A |
| `tests/helpers/metrik_listen_scan.py` | +33/−… | ✅ Ratschen-Registrierung |
| `frontend/.../WeatherMetricsTab.svelte` | −25/+… | ✅ Kern von Scheibe B |
| `api/routers/config.py` | `GET /api/metrics` (~:105-119) | `GET /api/sms-symbols` (:30-69) — **andere Funktion, keine Zeilenüberlappung** |

Keine Überschneidung bei `trip_report.py` / `sms_trip.py`. `.claude/file_claims.lock` existiert nicht.

**Folge: E6 setzt nach dem Merge von #1884 auf.** Das entspricht der Ticket-Vorgabe („E6 beginnt erst
danach") und ist jetzt konkret terminierbar statt offen.

## Technical Approach (Empfehlung)

### Der Kern: ein Register-Feld statt einer Nebentabelle

`MetricDefinition` bekommt ein Feld für **alle** SMS-Kürzel einer Größe (Tupel).
`SMS_MULTI_SYMBOLS_BY_METRIC` wird daraus **abgeleitet** — genau das Muster, mit dem E3b bereits
`SMS_SYMBOL_BY_METRIC` aus `get_sms_code()` abgeleitet hat. Damit erfüllt AC-1 („keine zweite
Tabelle daneben"), ohne die Schichtgrenze zu `src/output/tokens/` zu brechen.

Die Werte folgen dem **Gesendeten** (Option a), damit AC-6 hält. Voraussetzung ist das Auflösen der
beiden Altlasten aus G5.

Die Literale in `builder.py` bleiben, weil die Schichtgrenze das erzwingt. Sie werden weiterhin von
der Testschicht-Ratsche bewacht — **aber die Ratsche braucht getippte Erwartungswerte**, sonst ist
sie eine Tautologie (siehe R6).

### Scheiben-Zuschnitt

Backend und Frontend haben getrennte Nachweiswege (Python-Testschicht vs. echter Browser). #1728
wurde aus demselben Grund geteilt.

| Scheibe | Inhalt | ACs | Schließt |
|---|---|---|---|
| **A — Register** | Mehrfach-Kürzel ins Register, Ableitung, Altlasten `temperature`/`temperature_cold` auflösen, Ratsche mit getippten Werten, Kommentar an beiden Provider-Zuweisungen | AC-1, AC-2, AC-4, AC-6 | nein |
| **B — Legende** | Kürzel-Legende im Reiter „Wetter-Metriken", Vorbild `official-alerts-symbol-legend`, geteilter Baustein für Trip **und** Ortsvergleich | AC-3, AC-5 | ja, #1857 |

Jede Scheibe braucht eine eigene Issue-Nummer.

## Scope Assessment

| Scheibe | Dateien | LoC Produktiv | LoC Tests | Risiko |
|---|---|---|---|---|
| A | ~6 Produktiv + ~4 Test | ~60–90 | ~120–180 | **MEDIUM** — berührt das Register, das alles liest; Bestandsschutz ist die Zusicherung |
| B | ~3 Produktiv + ~3 Test | ~80–120 | ~100–140 | LOW–MEDIUM — reine Anzeige, aber geteilter Baustein in zwei Kontexten |

Das 250er-LoC-Limit dürfte je Scheibe halten; der **Nachweis** ist teurer als der Mechanismus
(Erfahrungswert: doppelt ansetzen).

## Open Questions

- [ ] **F1 (PO): Soll `WC` bleiben?** Gemessen verdoppelt es exakt den `FK`-Wert und kostet Zeichen
      im 160er-Budget. Streichen würde die zugestellte SMS ändern und damit AC-6 verletzen.
      #1728 hält als PO-Entscheid fest „WC bleibt an `wind_chill`" — das war aber vor dieser Messung.
      **Empfehlung:** In E6 **bleibt** `WC` (AC-6 hat Vorrang); die Redundanz wird als eigenes Ticket
      erfasst, damit sie entscheidbar bleibt statt zu verschwinden.
- [ ] **F2: Was wird aus `temperature.sms_code` und `temperature_cold.sms_code`?**
      Vorschlag: `temperature` verliert seinen SMS-Code (es ist die Quelle des *Stundenwerts*, sendet
      selbst kein Tages-Token); bei `temperature_cold` ist zu prüfen, ob der Alarm-Pfad `N` liest.
      Das ist eine Messung, kein Entscheid — gehört in die Spec-Phase.
- [ ] **F3: Terminlage.** PO-Frist ist der 20.08. Scheibe A kann nach dem Merge von #1884 starten.
