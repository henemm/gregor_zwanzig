# Kontext & Analyse: #1492 — Gewitter S4, Ausfallschutz

**Workflow:** `feat-1492-gewitter-fallback-kette` · **Stand:** 2026-08-05, gemessen an `94e4f331`
**PO-Entscheidung 2026-08-05:** voller Umfang (inkl. Mehrquellen-Redundanz), nicht nur der kleine Fix.

> Hinweis: Ein gleichnamiges Kontext-Dokument aus dem Vorlauf vom 2026-08-04 existiert nirgends
> mehr (weder Worktree, Hauptrepo noch Git-Verlauf) — vermutlich mit einem aufgeräumten
> Arbeitsbereich verloren. Die Befunde von damals sind im Issue-Kommentar zu #1492 erhalten und
> unten eingearbeitet. Dieses Dokument ersetzt es.

## Type

Feature (Architektur-relevant, ADR-pflichtig)

---

## 1. Was das Ticket will — und wo die Wirklichkeit abweicht

Ticket-Prämisse: „Gewitter überlebt den Providerausfall." Die Analyse zeigt **zwei getrennte
Ausfallarten** mit sehr unterschiedlicher Schwere:

| # | Ausfallart | Heute | Folge für den Nutzer | Schwere |
|---|---|---|---|---|
| **A1** | Open-Meteo-Primärmodell liefert kein `weather_code` | Ersatzmodell wird abgerufen und liefert es — aber die Zusammenführung verwirft es still | **Gewitteraussage verschwindet komplett** | 🔴 hoch |
| **A2** | Direktquelle (Météo-France WCS / DWD GRIB) fällt aus | fail-soft, Signalfelder bleiben `None` | Aussage bleibt, wird nur **gröber** (nur Wettercode + CAPE) | 🟠 mittel |

Das Ticket zielte auf A2. **A1 ist der gravierendere, bisher unbemerkte Fall** — dort geht die
Aussage ganz verloren, nicht nur an Schärfe.

---

## 2. Teil A1 — `weather_code` wird beim Modell-Fallback verworfen

### Mechanik (belegt)

- `PROBE_PARAMS` (`openmeteo.py:207-214`) enthält `weather_code` ⇒ es kann als „fehlend" erkannt werden
- Der Ersatz-Abruf fordert `weather_code` mit an (`openmeteo.py:1112`)
- `_PARAM_TO_FIELD` (`openmeteo.py:378-397`, 18 Einträge) enthält **kein** `weather_code`
- `merge_missing_fields` (`merge.py:38-40`): `field_name = param_to_field.get(param)` → `None` → `continue`
  ⇒ **stiller Verwurf**

### 🔴 Neuer Befund: der Fix ist NICHT einzeilig

`weather_code` erzeugt beim Parsen **drei** Felder (`openmeteo.py:846-848`):

```python
thunder_level=self._parse_thunder_level(get_int("weather_code", i)),   # 846
wmo_code=get_int("weather_code", i),                                   # 847
hail_flag=self._parse_hail_flag(get_int("weather_code", i)),           # 848
```

`merge_missing_fields` ist aber strikt **1:1** (`param_to_field: Dict[str, str]`, `merge.py:22`).
Ein einzelner Eintrag füllt genau ein Feld. Damit sind drei Wege denkbar — **das ist eine
Design-Entscheidung für die Spec**, kein Implementierungsdetail:

| Weg | Wirkung | Preis |
|---|---|---|
| (a) `weather_code` → `thunder_level` | Gewitteraussage kehrt zurück | `wmo_code` + `hail_flag` bleiben leer ⇒ Hagel-Kennzeichen (#1475) bleibt bei Modellausfall „unbekannt" |
| (b) `weather_code` → `wmo_code` + Nachableitung nach dem Merge | alle drei Felder korrekt | `merge.py` braucht einen Nachbearbeitungs-Schritt (neuer Mechanismus) |
| (c) `param_to_field` auf 1:N erweitern | alle drei Felder, generisch | Signaturänderung an gemeinsam genutzter Stelle, betrifft auch Schnee-Merge |

**Semantik ist bereits sauber gelöst** (Entwarnung zur alten Sorge im Issue-Kommentar):
`_parse_thunder_level(None)` liefert `None`, nicht `ThunderLevel.NONE` — Issue #1474 AC-4 hat die
Unterscheidung ausdrücklich eingeführt („fehlt der Wettercode ist das *keine Aussage*, NICHT die
geprüfte Entwarnung", `openmeteo.py:634-640`). Die Merge-Bedingung `getattr(dp, feld) is None`
greift damit genau richtig: fehlende Aussage wird gefüllt, geprüfte Entwarnung nicht überschrieben.

---

## 3. Teil A2 — Vertretung bei Ausfall der Direktquelle

### Heutiger Stand

`thunder_routing.py:63-67` — first-match-wins, **genau ein** Provider je Ort:

```python
_REGIONS: tuple[_ThunderRegion, ...] = (
    _ThunderRegion("FR",       41.3,  51.1,  -5.2,   9.7,  "fr_direct"),
    _ThunderRegion("DE_ALPEN", 43.17, 58.09, -3.95, 20.35, "de_direct"),
    _ThunderRegion("EU_REST",  -90.0, 90.0, -180.0, 180.0, "eu_direct"),
)
```

Einziger Aufrufer: `thunder_enrichment.py:181`. Fehlerbehandlung: `try/except Exception` auf
oberster Ebene (`thunder_enrichment.py:157-160`) — schluckt alles, Felder bleiben `None`, **keine
Ausweichlogik, keine Herkunftsangabe**.

### 🟢 Entschärfender Befund: das Muster existiert bereits — ADR-0018

Der Abhängigkeits-Bericht fand das entscheidende Vorbild: **ADR-0018 „Modell-Fallback ohne
Kaschieren"** ist bereits akzeptiert und im Grundvorhersage-Pfad implementiert
(`openmeteo.py`, `REGIONAL_MODELS`-Kette bei 5xx/Timeout), inklusive der Transparenz-Pflicht:
`ForecastMeta.fallback_model`, `fallback_reason`, `logger.warning`, `openmeteo_calls.jsonl`,
plus Health-Signale im Status-Endpunkt.

⇒ Eine Vertretungskette für Gewitter ist **kein Architektur-Neuland**, sondern die Anwendung
eines bereits beschlossenen Musters auf eine zweite Domäne. Das ADR für #1492 kann sich darauf
stützen statt eine neue Grundsatzentscheidung zu erfinden.

**Heute fehlt die Nicht-Kaschieren-Hälfte komplett:** Für Gewitter gibt es keinerlei
Herkunftsmarker — der Ausfall degradiert **still**. Das ist unabhängig von der Vertretung schon
ein Mangel gemessen an ADR-0018.

**Die Datenstruktur dafür ist aber schon da:** `ForecastMeta` (`app/models.py:81-95`) trägt
bereits `fallback_model`, `fallback_reason` und `fallback_metrics` (aus #1115/ADR-0018). Für
Gewitter ist keines davon je gesetzt (Grep ohne Treffer). Scheibe 2 muss also **kein neues
Meldemodell erfinden**, sondern das vorhandene befüllen — weiterer Beleg dafür, dass hier ein
etabliertes Muster ausgedehnt und nicht eine Architektur neu erfunden wird.

### Fachliche Plausibilität der Vertretung

| Primär | Vertretung | Feld-Sicht | Bewertung |
|---|---|---|---|
| `de_direct` (ICON-D2) | `eu_direct` (ICON-EU) | **dasselbe Feld** `lightning_potential_lpi_jkg` | 🟢 sauber — `api_contract.md` beschreibt beide bereits als „zwei Quellen, ein Feld". Preis: kein `grau_gsp` (Hagel) bei ICON-EU (KL-3) |
| `fr_direct` (MF AROME) | `eu_direct` (ICON-EU) | **anderes Feld**: Blitzdichte → LPI | 🟠 fachlich vertretbar (beide speisen dieselbe Fusion), aber ein echter Wechsel der Messgröße — begründungspflichtig |
| `eu_direct` | — | — | keine weitere Quelle vorhanden |

---

## 4. Kollisionen mit bestehenden Festlegungen

| Festlegung | Fundstelle | Kollidiert? |
|---|---|---|
| **AC-8** „first-match-wins tragend", mit Mutations-Gegenprobe | `feat_1457_s2c_icon_eu_luekenfueller.md:251-261` | **Nein**, wenn die *Primärauswahl* first-match-wins bleibt und die Vertretung nur im Fehlerfall greift. Ja, wenn `_REGIONS` grundsätzlich zur Kandidatenliste umgebaut wird. |
| **`api_contract.md`** „Herkunft ist über `thunder_provider_for()` rekonstruierbar" | `api_contract.md:241` | **Ja** — bei Vertretung stimmt die Positions-Rückrechnung nicht mehr. Muss ergänzt werden: Herkunft im Vertretungsfall **explizit festhalten** (deckt sich mit ADR-0018 Nicht-Kaschieren). |
| **`decision_matrix.md`** „Die Reihenfolge ist tragend" | `decision_matrix.md:113-144` | **Nein** bei Primär/Vertretung-Trennung; Text braucht einen Zusatz zur Vertretung. |
| **ADR-0025** „genau eine Rohdaten-Quelle für die Gewitteraussage" | ADR-0025, Entscheidung 1 | **Nein** — ADR-0025 meint `dp.thunder_level` als einzige *Ausgabe*-Quelle für alle Kanäle, nicht die Anzahl der *Bezugsquellen*. Sollte im neuen ADR ausdrücklich abgegrenzt werden, sonst wirkt es wie ein Widerspruch. |
| **KL-4** „Herkunfts-Transparenz über Routing rekonstruierbar" | `feat_1457_s2b...md` | **Ja**, dieselbe Sache wie `api_contract.md:241` — dieselbe Abhilfe. |

**Kein einziger Test setzt heute „mehrere Provider pro Ort" voraus oder verbietet es** — die
bestehenden Tests prüfen ortsspezifische Zuständigkeit, die bei Primär/Vertretung-Trennung
gültig bleibt.

---

## 5. Empfehlung (Tech Lead)

**Vertretungskette statt genereller Kandidatenliste**, in zwei Scheiben:

- **Scheibe 1 — A1 schließen** (`weather_code`-Merge): der schwerere Fehler, kleiner Umfang,
  keine Architektur-Kollision. Braucht nur die Entscheidung (a)/(b)/(c) aus Abschnitt 2.
- **Scheibe 2 — A2 Vertretung + Transparenz**: `_REGIONS` behält first-match-wins für die
  Primärwahl; je Region eine **benannte Vertretung**; im Vertretungsfall Herkunft explizit
  festhalten (ADR-0018-Muster). Eigenes ADR, das ADR-0018 auf Gewitter ausdehnt und die
  Abgrenzung zu ADR-0025 festhält.

Warum nicht die generelle Kandidatenliste: sie kauft keinen fachlichen Mehrwert (es gibt je Ort
maximal eine sinnvolle Vertretung), kostet aber AC-8, den `decision_matrix`-Grundsatz und die
Herkunfts-Eindeutigkeit.

---

## 6. Scope-Schätzung

| | Scheibe 1 | Scheibe 2 |
|---|---|---|
| Dateien | 2 (`openmeteo.py`, ggf. `merge.py`) + Tests | 3–4 (`thunder_routing.py`, `thunder_enrichment.py`, Modell/Meta, Doku) + Tests |
| LoC | ~40–80 je nach Weg (a)/(b)/(c) | ~120–180 |
| Risiko | niedrig | mittel (kritischer Datenpfad, alle Kanäle) |
| ADR nötig | nein | **ja** |
| Doku-Folgeänderungen | keine | `api_contract.md:241`, `decision_matrix.md:113-144`, KL-4 |

Zusammen deutlich über 250 LoC ⇒ **zwei getrennte Workflows**, nicht einer.

---

## 7. PO-Entscheidungen (2026-08-05, nach Erläuterung des Gesamtkonstrukts)

- [x] **F1 (Scheibe 1) → Weg (b):** Gewitteraussage **und** Hagel-Kennzeichen müssen den
      Modellausfall überleben. Begründung des PO-Entscheids: sonst zeigt das Briefing bei
      Modellausfall „Hagel unbekannt", obwohl das Ersatzmodell „Gewitter mit Hagel" gemeldet hat —
      Widerspruch zur gerade ausgelieferten Hagel-Arbeit (#1475). Der generische 1:N-Umbau
      (Weg c) wurde **nicht** gewählt: kein Eingriff an der gemeinsam genutzten Merge-Signatur.
      ⇒ Umsetzung: `weather_code` → `wmo_code` mergen, danach `thunder_level` und `hail_flag`
      aus dem gemergten Rohcode **nachableiten** (derselbe Weg, den `_parse_response` geht).
      Die Nachableitung darf einen vorhandenen Wert **nie** überschreiben (Merge-Invariante).
- [x] **F2 (Scheibe 2) → ja:** `fr_direct` darf im Ausfall durch `eu_direct` vertreten werden,
      obwohl die Messgröße von Blitzdichte auf Blitzpotenzial wechselt. Begründung: eine etwas
      anders hergeleitete Gewitterstufe ist besser als keine — Bedingung ist, dass der Wechsel
      **transparent vermerkt** wird (ADR-0018-Muster, `ForecastMeta`).
- [x] **F3 → zwei Lieferungen:** erst Scheibe 1 (A1, verschwindende Gewitteraussage), danach
      Scheibe 2 (A2, Vertretung + ADR).

## 8. Nicht in diesem Umfang

- Hagel-Fusion in die Gewitterstufe (bleibt #1475/S5, bewusst getrennt)
- `thunder_probability_pct` (#1419 S6, von keiner Quelle befüllt)
- Kontingent-Steuerung für DWD/Météo-France-Abrufe: eigene Dienste, zählen **nicht** gegen das
  Open-Meteo-Budget (`forecast_budget.py`) — eine Vertretung erhöht die Last dort trotzdem
  messbar, gehört als Beobachtungs-AC in Scheibe 2, nicht als eigener Zähler.

---

# Scheibe 2 — PO-Entscheidungen 2026-08-06

Scheibe 1 ist seit 2026-08-05 live (`e34d9bc9`). Ergänzend zu Abschnitt 7 wurden für Scheibe 2
folgende Fragen entschieden:

## E1 — Sichtbarkeit: Vertretung wird IMMER erwähnt

Nicht nur intern vermerken. Der Nutzer soll erfahren, wenn die Gewitterdaten aus einer
Ersatzquelle stammen.

- **Kanäle: E-Mail + Telegram.** SMS bewusst **ausgenommen** — bei 160 Zeichen verdrängt ein
  Herkunftshinweis echte Wetterinformation (vgl. `feedback_kurznachricht_nennt_keinen_ort`,
  `feedback_sms_three_states_already_unambiguous`).
- Anknüpfungspunkte existieren beidseitig: E-Mail-Fußzeile (`email/html.py:531-535`,
  `email/plain.py:362-367`) und Telegram-Tagesfußzeile (`narrow.py:215 _tg_day_footer`).
- ADR-0007 („Daten statt Empfehlungen") ist **nicht** berührt: eine Herkunftsangabe ist ein Fakt,
  keine Handlungsempfehlung.

## E2 — Formulierung wird verständlich, auch im Bestand

Der heutige Hinweis lautet technisch `Fallback lightning: eu_direct`. Er wird in Klartext
überführt (z.B. „Gewitterdaten von Ersatzquelle (DWD Europa, gröbere Auflösung)"). **Der
bestehende Hinweis für die Hauptvorhersage wird mit umgestellt** — kein Nebeneinander von
technischem und verständlichem Stil.

⚠️ Folge: Damit ändert Scheibe 2 auch eine **bestehende, heute ausgelieferte Ausgabe**. Die
zugehörige Zusicherung `TestFooterFallbackInfo` (`tests/unit/test_model_metric_fallback.py:179`)
muss mitgezogen werden.

## E3 — Auslöser: nur bei echtem Dienstfehler

Die Vertretung springt **nicht** allein deshalb ein, weil Signale fehlen. Heute sind drei Fälle
ununterscheidbar, weil `except Exception` alles schluckt:

1. Dienst nicht erreichbar / Zeitüberschreitung ⇒ **Vertretung sinnvoll**
2. Ort außerhalb des Modellgebiets ⇒ Vertretung sinnlos (Gebiet ändert sich nicht)
3. Kein Gewitter in Sicht ⇒ Vertretung sinnlos (die Antwort ist korrekt leer)

Die Fehlerbehandlung wird so nachgerüstet, dass (1) von (2) und (3) unterscheidbar wird.
**Gemessen:** allein in `thunder_enrichment.py`, `dwd.py`, `dwd_eu.py` und `meteofrance.py`
stehen **zehn** `except Exception`-Stellen.

🔴 **Sicherheitsauflage:** Die fail-soft-Zusicherung darf dabei NICHT fallen — der Vertrag in
`base.py` („wirft NIE; Ausfall der Gewitterquelle darf die Grundvorhersage nicht kippen") bleibt
nach außen unverändert. Unterschieden wird **innerhalb** der Anreicherung, nicht durch
Weiterreichen von Ausnahmen.

## Umfangsfolge — Scheibe 2 zerfällt in 2a und 2b

Zusammen deutlich über der 250-LoC-Grenze (grobe Schätzung: ~195 Zeilen Produktivcode plus
Tests), und die beiden Hälften sind unabhängig prüfbar:

| | Inhalt | Kernfrage |
|---|---|---|
| **2a** | Fehlerunterscheidung, Vertretungstabelle, Vertretungsaufruf, Herkunft in `ForecastMeta` festhalten, **ADR** | *Funktioniert die Vertretung?* |
| **2b** | Klartext-Formulierung, E-Mail-Fußzeile umgestellt, Telegram-Fußzeile neu | *Sieht der Nutzer sie?* |

2a ist ohne 2b sinnvoll auslieferbar (Vertretung wirkt, Herkunft ist im System nachvollziehbar);
2b ist ohne 2a wirkungslos. Reihenfolge daher **2a zuerst**.
