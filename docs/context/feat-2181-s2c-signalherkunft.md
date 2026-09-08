# Context: feat-2181-s2c-signalherkunft

## Request Summary

Scheibe S2c aus #2181: die Thesen **T1** (welcher Signalast trug die erreichte Stufe?), **T3**
(lag das CAPE-Maximum am 29.08. vor dem Ereignis?) und **T4** (wie oft stand „hoch" bei
vorhergesagtem Niederschlag nahe null?) prüfen — für den Karnischen Höhenweg
(24.08.–05.09.2026, 13 Etappentage), gemessen gegen den in S1 korrigierten Maßstab.

Vorarbeit auf diesem Ticket: **S1** (T6, geliefert, PR-unabhängig als Kommentar) hat den Maßstab
von „4 eingetretene Tage" auf **2:13** korrigiert. **S2a** (`feat-2181-s2a-mitschnitt-auswertung`,
PR #2187, `c3251097`) hat `src/analysis/thunder_replay.py` gebaut — die Auswertungsschicht für
T2/T5, ausschließlich auf dem bereits gesicherten Vorhersage-Mitschnitt, keine Archiv-Rekonstruktion
nötig. **S2b** (T2/T5 mit dem Werkzeug tatsächlich messen und als Protokoll kommentieren) und diese
Scheibe **S2c** stehen beide noch aus; S2c läuft zuerst, weil die dafür gesicherte Archiv-Kopie
(s.u.) terminlich enger ist als der reine Mitschnitt.

## Ausgangslage aus S1 (bereits geliefert, Kommentar an #2181)

Der Maßstab für alle Trefferquoten steht neu und ist **nicht** mehr „4 eingetretene Tage":

- tagsüber nass auf der Route: **2 Tage** (29.08. 14 mm mit Gewitter · 02.09. 15,6 mm, 18 km neben
  dem Ziel), dazu 25.08. leichter Landregen ohne Gewittercharakter
- nachts nass: **2 Nächte** (28./29.08. · 31.08./01.09. mit dem PO-beobachteten Gewitter ab 22 h)
- Die Überprognose steht damit bei **2:13**, nicht 4:13.

Gesicherte Daten (außerhalb jeder Aufbewahrungsfrist):
`/home/hem/gz-messdaten/khw-2026-08-mitschnitt/` (Vorhersage-Mitschnitt, 2 246 Zeilen, führt
`thunder_level_max` + `cape_max_jkg`, **nicht** die Signalherkunft), `…-rueckblick/` (ICON-D2
punktgenaue Rückblick-Läufe, S1-Material), `…-stationen/` (GeoSphere-Beobachtungsstationen).

## Live-Machbarkeitsprüfung heute (2026-09-08) — korrigiert einen eigenen Fehlschluss

Ich hatte zunächst angenommen, CIN und Blitzpotenzial (LPI) seien für den KHW-Zeitraum nicht mehr
beschaffbar, weil sie produktiv vom DWD-OpenData-GRIB-Spiegel kommen
(`opendata.dwd.de/weather/nwp/icon-d2/grib/`, hält nur ~48 h vor). **Das ist die falsche Quelle für
eine Archiv-Rekonstruktion.** Direkt gegen `historical-forecast-api.open-meteo.com` geprüft
(Modell `icon_d2`, 46.6123/12.8672 = Wolayersee-Hütte, 29.08.2026):

```
15:00  code=96  cape=0.0   cin=0.0   lpi=2.6   precip=12.0  showers=0.2
16:00  code=99  cape=20.0  cin=65.0  lpi=0.0   precip=29.2  showers=0.1
13:00  code=2   cape=790.0 cin=0.0   lpi=0.0   precip=0.0   showers=0.0
```

`weather_code`, `cape`, `convective_inhibition` UND `lightning_potential` sind alle vier über
dieselbe Open-Meteo-Archiv-API abrufbar, mit plausiblen, variierenden Werten (nicht durchgehend
Füllwert/Null — Gegenprobe an einem ruhigen Tag, 25.08., zeigt LPI durchgehend 0.0 und CIN meist
0–1, während der Gewittertag deutlich davon abweicht). Die volle Drei-Äste-Ablation (Wettercode,
CAPE, Blitzpotenzial — Blitzdichte bleibt strukturell FR-only, s.u.) ist damit möglich, **kein**
eingeschränkter Ersatzbefund nötig.

Rohdaten der Probe unter
`/tmp/claude-1000/-home-hem-gregor-zwanzig/2da2a554-b229-426e-82e7-fae490715441/scratchpad/probe_29aug_wolayersee.json`
gesichert (nur zur Nachvollziehbarkeit dieser Session, kein Repo-Artefakt).

## Auf dem KHW anliegende Äste — drei, nicht vier

| Ast | Auf dem KHW | Schwellen | Archiv-Feld |
|---|---|---|---|
| **Wettercode** | ja | binär: 95/96/99 → `HIGH`, sonst `NONE` — **kann `LOW`/`MED` nicht erzeugen** | `weather_code` |
| **CAPE** | ja | 300 / 750 / 1200 J/kg (icon_d2 × DE_ALPEN) | `cape` |
| **Blitzpotenzial (LPI)** | ja | 1,0 / 30 / 50 (Gebietsleiter) | `lightning_potential` |
| **Blitzdichte** | **nein** — strukturell abwesend, ist die Météo-France-Größe | 0,003 / 0,015 / 0,075 | — |
| *(Radar-Override)* | möglich, im Mitschnitt bereits eingerechnet | hebt auf `MED`, Träger `"radar"` | nicht rekonstruierbar |

## Die CIN-Bedingung — Angelpunkt für die CAPE-Ablation

CAPE eskaliert über `LOW` hinaus **genau dann**, wenn ein CIN-Wert vorliegt und `|CIN| ≤ 100`
(`metric_format.py:377-431`, `_gedaempft_durch_cin`):

- `cin_jkg is None` → Deckel `LOW` („eine fehlende Hemmungsangabe ist keine schwache Hemmung") —
  **irrelevant für S2c**, da CIN jetzt real vorliegt (siehe Machbarkeitsprüfung)
- `|CIN| < 50` → volle Leiterstufe
- `50 ≤ |CIN| ≤ 100` → eine Stufe herunter
- `|CIN| > 100` → eine Stufe herunter **und** Deckel `LOW`

Produktiv liefert `dp.convective_inhibition_jkg` ausschließlich der DWD (`cin_ml`,
`thunder_enrichment.py:44`, geholt über `de_direct`); die Rekonstruktion nimmt CIN stattdessen von
Open-Meteos Archiv-Spiegel desselben `icon_d2`-Modells — andere Bezugsquelle, aber dieselbe
Modellgröße, kein Verfahrenswechsel.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py:434` | `_signal_levels()` — übersetzt jedes Signal einzeln in ein `ThunderLevel` |
| `src/output/metric_format.py:489` | `thunder_signal_carriers() -> list[str]` — nennt **jedes** Signal auf der Höchststufe, kürt keinen Gewinner (genau der Ablations-Baustein für T1) |
| `src/output/metric_format.py:528` | `thunder_level_from_signals()` — Fusion, `max_thunder()` über die Signalwerte |
| `src/output/metric_format.py:377-431` | `_gedaempft_durch_cin()` — die CIN-Dämpfung, ausschließlich um den CAPE-Ast gelegt |
| `src/providers/openmeteo.py:269` | `THUNDER_CODES = {95, 96, 99}` — wiederverwendbare Konstante, keine zweite Kopie |
| `src/providers/openmeteo.py:694-716` | `_parse_thunder_level()` — Referenzverfahren Wettercode → `ThunderLevel` |
| `src/app/model_registry.py:228-243` | `cape_ladder_thresholds_jkg(model_id, region)` → (low, med, high) |
| `src/app/model_registry.py:180-187` | `lpi_thresholds_jkg(region)` → (low, med, high) |
| `src/providers/thunder_routing.py:80` | `thunder_region_for(lat, lon)` — Gebietszuordnung, liefert `DE_ALPEN` für den KHW |
| `src/analysis/thunder_replay.py` | S2a-Modul (Vorlauf-Auswahl, Tages-Aggregation, Dreiwertigkeit) — Muster für S2c, ggf. Erweiterung statt Neubau |
| `tests/tdd/test_thunder_replay.py` | S2a-Tests — Fixture-Stil, an dem sich S2c-Tests orientieren |
| `src/services/forecast_capture.py` | Mitschnitt; führt `thunder_level_max` + `cape_max_jkg` je Etappentag, Grundlage für den Kalibrier-Abgleich |

## Existing Patterns

- **Die Ablation existiert bereits als Funktion.** `thunder_signal_carriers()` läuft über
  dasselbe `_signal_levels()` wie die Fusion — für T1 muss keine zweite Fusionsregel entstehen
  (ADR-0025), nur mit rekonstruierten Rohwerten aufgerufen werden.
- **„Alles oder nichts" je Leiter:** fehlt eine der drei Sprossen, trägt das Signal gar nicht bei.
  Ein fehlendes Signal erscheint nicht im Dict; sind alle abwesend, ist das Ergebnis `None` =
  „keine Aussage", nicht `NONE` = „geprüfte Entwarnung" — dieselbe Dreiwertigkeits-Disziplin wie
  in S2a (AC-4/AC-5 dort).
- **S2a hat das Fixture-/Test-Muster bereits etabliert:** echte aufgezeichnete Zeilen als
  versionierte JSON-Fixtures, reine Funktionen ohne Netz/DB, Test pro AC.

## Der entscheidende Befund: der Vorlauf-Versatz (aus der Vorarbeit zu S2, übernommen)

Der Mitschnitt hält Vorhersagen mit **Median 21 h Vorlauf, 36 % über 48 h** (gemessen als
`fenster_start − fetched_at`). `historical-forecast-api` gibt dagegen je Stunde offenbar den
**reifsten verfügbaren** Wert (der 29.08. zeigt am Nachmittag scharfe, ereignisnahe Werte). Ein
unbesehener Abgleich Rekonstruktion ↔ Mitschnitt-Gesamtmenge misst deshalb eher
**Vorhersagedrift als Rechenweise-Fehler** — und würde eine korrekte Rekonstruktion zu Unrecht
verwerfen. **Konsequenz für den Kalibrier-Schritt:** der CAPE-Abgleich (Archiv gegen Mitschnitt)
läuft NUR auf der kurzvorlauf-nächsten Teilmenge des Mitschnitts (kleinster verfügbarer Vorlauf je
Tag/Segment — dieselbe Auswahlfunktion `waehle_vorlauf_aermste()` aus `thunder_replay.py`), nicht
auf dem gesamten Mitschnitt.

Zwei weitere Messfallen aus derselben Familie, für S2c übernommen:

- **Nichtstun-Übereinstimmung:** ein Großteil der Mitschnitt-Zeilen ist `NONE`. Eine hohe
  Trefferquote allein daraus wäre keine Leistung — der Kalibrier-Abgleich vergleicht deshalb den
  **kontinuierlichen** `cape_max_jkg`-Wert (relative Abweichung quantifizierbar), nicht nur die
  Dreistufigkeit.
- **Teilmengen-Willkür:** welche `source`-Teilmenge des Mitschnitts als Vergleichsgrundlage dient,
  muss vorab feststehen (S2a hat dafür bereits `TEILMENGE_PRIMAER` definiert) — nicht im Nachhinein
  passend gewählt werden.

## T1 — Ablation statt Gewinnerzuweisung

**T1 wird als Ablation gestellt:** Für jeden Etappentag, an dem der Mitschnitt eine Stufe ≥ `LOW`
zeigt, wird geprüft, welche(r) Ast/Äste (Wettercode/CAPE/Blitzpotenzial) bei rekonstruierten
Rohwerten dieselbe Höchststufe allein erzeugen — via `thunder_signal_carriers()`, ungeändert
aufgerufen. Kein neuer Gewinner wird gekürt (mehrere Äste können gleichzeitig Träger sein, exakt
wie im Produktivpfad).

**Bekannte Grenze, die in die Spec muss:** Der Radar-Override (`RadarNowcastService`) ist im
Mitschnitt bereits eingerechnet, aber aus der Archiv-Rekonstruktion strukturell nicht sichtbar —
ein Tag, an dem der Radar die Stufe auf `MED` gehoben hat, kann in der Ablation als „kein Ast
erreicht die Mitschnitt-Stufe" erscheinen, ohne dass das ein Fehler der Rekonstruktion ist. Muss
als eigene Kategorie ausgewiesen werden, nicht der Ablation angelastet werden.

## T3 — CAPE-Zeitverlauf am 29.08.

Braucht nur `cape` und `weather_code` aus derselben Archiv-Abfrage für die Wolayersee-Hütte,
29.08., alle 24 Stunden. Ereignisstunden werden aus `weather_code` (Codes in `THUNDER_CODES`)
selbst abgeleitet — keine externe Zeitangabe nötig. Frage: liegt das CAPE-Maximum 1–3 h VOR der
ersten Ereignisstunde? Aus der Live-Probe oben bereits ablesbar: Maximum 790 J/kg um 13:00, erste
Ereignisstunde (Code 96) um 15:00 — **2 h Vorlauf**, im behaupteten Fenster. Das ist noch keine
Auswertung (nur eine Stichprobe aus der Machbarkeitsprüfung), muss aber als Testfall in die
Fixtures.

## T4 — Stufe vs. vorhergesagter Niederschlag

Braucht **keine neue Fusion** — paart die bereits im Mitschnitt stehende `thunder_level_max` je
Etappentag (aus `thunder_replay.tageswerte_je_teilmenge()`, S2a-Funktion, unverändert
wiederverwendet) gegen die archiv-rekonstruierte Tagessumme von `precipitation`/`showers` an
demselben Etappenziel. Kein Schwellenwert wird im Modul festgelegt („nahe null" ist eine
Berichts-Interpretation, keine Modul-Konstante) — das Modul liefert die rohen Paare
(Stufe, Niederschlagssumme, Schauersumme) je Tag, die Bewertung geschieht im Bericht außerhalb
des Repos (S2a-Präzedenzfall: „kein Freitext-Bericht — der Bericht selbst entsteht außerhalb des
Repos").

## Affected Files (vorläufig, Bestätigung in der Spec)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/analysis/thunder_replay.py` | MODIFY (Erweiterung) oder `src/analysis/thunder_ablation.py` CREATE | Archiv-Stundenzeilen-Verarbeitung: Ablation (T1), Ereignisfenster+CAPE-Verlauf (T3), Stufe-Niederschlag-Paarung (T4), Kalibrier-Abgleich Kurzvorlauf-CAPE |
| `tests/tdd/test_thunder_replay.py` (Erweiterung) oder neue Testdatei | CREATE/MODIFY | Verhaltensprüfung gegen Fixtures aus echten Archiv-Antworten |
| `tests/fixtures/khw_2026_08_archiv/*.json` | CREATE | Aufgezeichnete Archiv-Stunden (u.a. die 29.08.-Probe oben) als versionierte Fixtures |

Ob Erweiterung oder neues Modul: Entscheidung gehört in die Spec (Implementation Details), nicht
hierher vorweggenommen — Kriterium: unterschiedliche Eingangsgranularität (Stunde vs. bereits
tagesaggregierter Mitschnitt) spricht für ein eigenes Modul, gemeinsame Hilfsfunktionen
(`thunder_ordinal`, Dreiwertigkeits-Disziplin) sprechen für Wiederverwendung aus `thunder_replay.py`.

Der Abruf-/Report-Teil (Netz, Ausgabe des Protokolls) bleibt **außerhalb** des Repos unter
`/home/hem/gz-messdaten/`, wie bei S1/S2a — genau ein Lauf, kein Wartungswert.

## Existing Specs

- `docs/specs/modules/feat_2181_s2a_gewitter_mitschnitt_auswertung.md` — Vorgänger-Spec (S2a),
  Known Limitations dort benennen explizit diese Scheibe als Folgearbeit
- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` — Eichung der CAPE-Schwelle
- `docs/adr/0025-...` (eine Gewitter-Fusionsquelle) — bindend für den Ablations-Ansatz
- `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md` — widerspricht dem Ist-Zustand,
  siehe #2182 (nicht Gegenstand dieser Scheibe)

## Dependencies

- **Upstream:** `output/metric_format.py` (`thunder_signal_carriers`, `_signal_levels`),
  `app/model_registry.py` (Schwellen), `providers/thunder_routing.py` (Gebiet),
  `providers/openmeteo.py` (`THUNDER_CODES`), `src/analysis/thunder_replay.py` (Vorlauf-Auswahl,
  Dreiwertigkeit, `thunder_ordinal`)
- **Downstream:** keine — kein Produktivpfad wird verändert. Die **Befunde** wirken auf #2176
  (Gewitterstufe-als-Ansage-Formulierung), #2182 (ADR-0048-Bruch) und Epic #1419.

## Risks & Considerations

- **Nachrechnung ≠ Mitschnitt.** Eine Archiv-Rekonstruktion ist eine Rekonstruktion, kein Beweis
  dessen, was der Dienst damals ausgab — der Kalibrier-Abgleich (Kurzvorlauf-CAPE) muss VOR der
  T1-Ablation stehen und deren Aussagekraft explizit einschränken, falls er divergiert.
- **Der Radar-Override ist aus der Rekonstruktion nicht sichtbar** — Stunden, in denen er
  gegriffen hat, dürfen nicht einem der drei Äste zugeschlagen werden, sondern brauchen eine
  eigene Kategorie „durch Radar gehoben, Ablation nicht aussagekräftig".
- **`None` ≠ `NONE`.** „Keine Aussage" und „geprüfte Entwarnung" dürfen in der Auswertung nicht
  zusammenfallen — dieselbe Disziplin wie in S2a AC-4/AC-5.
- **Akzeptanzkriterien beschreiben die Messvorschrift, nie das Ergebnis** — ein AC der Form „Then
  trägt CAPE ≥ 7 Tage" wäre keine Messung mehr, sondern eine vorweggenommene Antwort (S2a-Lehre).
- **T3-Beispielwert oben ist eine Stichprobe, kein Befund** — darf nicht als vorweggenommenes
  Ergebnis in eine Spec-Formulierung einfließen, nur als Testfall-Rohmaterial.

## Analysis

### Type

Feature (Messwerkzeug + Auswertung). Kein Bugfix — es wird nichts repariert, sondern eine
Zusicherung nachgemessen (identisch zur Einordnung von S2a).

### Scope Assessment

- Files: 3 (1-2 Code-Dateien im Repo + Fixture-Verzeichnis)
- Estimated LoC: Modul ~120-180, Tests ~120-150 → im 250er-Limit, aber eng wie bei S2a
  (dort musste `loc_limit_override` nicht gezogen werden — als Referenz brauchbar)
- Risk Level: LOW für das System (kein Produktivpfad verändert, reine Funktionen ohne Netz/DB),
  MEDIUM-HIGH für die Aussagekraft (T1 hängt am Kalibrier-Abgleich; ein zu großzügig bestandener
  Abgleich würde einen falschen Befund erzeugen, der in #2176 weiterwirkt — dieselbe Familie von
  Fehler, die die Untersuchung am 07.09. zweimal getroffen hat)

### Empfehlung

Standard Track bestätigt sich: die eigentliche Unsicherheit war die Datenverfügbarkeit (jetzt
geklärt: JA, via Open-Meteo-Archiv, nicht DWD-Direktabruf), nicht die Code-Komplexität. Weiter mit
`/30-write-spec` — Spec muss den Kalibrier-Abgleich als AC VOR der Ablations-ACs führen (Reihenfolge
ist inhaltlich zwingend, nicht nur redaktionell), und die drei Known Limitations (Radar-Override,
Vorlauf-Versatz, T3-Stichprobe-nicht-Befund) wörtlich übernehmen.

## Open Questions

- [x] Liefert das Archiv CIN und LPI für icon_d2? — **Ja**, heute live verifiziert
- [x] Ist `metric_format` offline importierbar? — **Ja** (aus S2a bereits bestätigt)
- [ ] Erweiterung von `thunder_replay.py` oder neues Modul? — Entscheidung in der Spec
- [ ] Toleranzschwelle für den Kalibrier-Abgleich (relative CAPE-Abweichung) — Entscheidung in der
      Spec, mit Begründung (kein willkürlicher Prozentwert ohne Bezug)
