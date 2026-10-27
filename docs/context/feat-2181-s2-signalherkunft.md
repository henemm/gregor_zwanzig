# Context: feat-2181-s2-signalherkunft

## Request Summary

Scheibe S2 aus #2181: die Thesen **T1–T5** prüfen — welcher Signalast die Gewitterstufen auf dem
Karnischen Höhenweg (24.08.–05.09.2026, 13 Etappentage) tatsächlich getragen hat, gemessen gegen
den in S1 korrigierten Maßstab.

## Ausgangslage aus S1 (bereits geliefert, Kommentar an #2181)

Der Maßstab für alle Trefferquoten steht neu und ist **nicht** mehr „4 eingetretene Tage":

- tagsüber nass auf der Route: **2 Tage** (29.08. 14 mm mit Gewitter · 02.09. 15,6 mm, 18 km neben
  dem Ziel), dazu 25.08. leichter Landregen ohne Gewittercharakter
- nachts nass: **2 Nächte** (28./29.08. · 31.08./01.09. mit dem PO-beobachteten Gewitter ab 22 h)
- Die Überprognose steht damit bei **2:13**, nicht 4:13.

Gesicherte Daten (außerhalb jeder Aufbewahrungsfrist):
`/home/hem/gz-messdaten/khw-2026-08-mitschnitt/` (Vorhersage-Mitschnitt, 2 246 Zeilen),
`…-rueckblick/` (ICON-D2), `…-stationen/` (GeoSphere-Messungen).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py:434` | `_signal_levels()` — **die** Rechnung; übersetzt jedes Signal einzeln in ein `ThunderLevel`, Schlüssel `wettercode`/`blitzdichte`/`cape`/`blitzpotenzial` |
| `src/output/metric_format.py:528` | `thunder_level_from_signals()` — Fusion, `max_thunder()` über die Signalwerte (`:597`). Keine Priorität, keine Reihenfolge |
| `src/output/metric_format.py:489` | `thunder_signal_carriers() -> list[str]` — nennt **jedes** Signal auf der Höchststufe, kürt keinen Gewinner |
| `src/output/metric_format.py:377-431` | `_gedaempft_durch_cin()` — die CIN-Dämpfung, ausschließlich um den CAPE-Ast gelegt |
| `src/providers/openmeteo.py:694-716` | Wettercode-Ast: `THUNDER_CODES = {95,96,99}` → `HIGH`, sonst `NONE` |
| `src/app/model_registry.py:120-132` | `CAPE_THRESHOLDS_JKG`, Schlüssel `(model_id, region)`; `icon_d2 × DE_ALPEN = 300.0` |
| `src/app/model_registry.py:228-243` | `cape_ladder_thresholds_jkg()` → (low, med, high) |
| `src/app/model_registry.py:174-177` | LPI-Schwellen je Gebiet |
| `src/providers/thunder_routing.py:80` | `thunder_region_for(lat, lon)` — Gebietszuordnung |
| `src/providers/thunder_enrichment.py:187-203` | `_fuse_thunder_levels()` — einziger produktiver Aufrufer; füllt `dp.thunder_level_signals` |
| `src/providers/thunder_enrichment.py:219-275` | Radar-Override — hebt auf `MED`, hängt Träger `"radar"` an |
| `src/app/models.py:218` | `thunder_level_signals: Optional[list[str]]` — die Herkunft am Datenpunkt |
| `src/services/trip_report_scheduler.py:3059-3093` | Stufe → Satz; Träger direkt dahinter als `" · "`-Liste |
| `src/services/forecast_capture.py` | Mitschnitt; führt `thunder_level_max` + `cape_max_jkg`, **nicht** die Herkunft |

## Existing Patterns

- **Die Herkunft ist bereits berechenbar und wird live geführt.** `thunder_signal_carriers()` läuft
  über dasselbe `_signal_levels()` wie die Fusion — Stufe und Herkunft können nicht auseinanderlaufen.
  Für T1 muss nichts erfunden werden, nur nachgerechnet.
- **Offline-Nachrechnung ist möglich.** `metric_format` importiert nur `app.metric_catalog`,
  `app.models`, `app.thunder_scale` — kein Netz. Schwellen über
  `cape_ladder_thresholds_jkg(model_id, region)` und `lpi_thresholds_jkg(region)`, Gebiet über
  `thunder_region_for(lat, lon)`. Alle sieben Schwellen-Keywords sind pflichtig ohne Default.
- **„Alles oder nichts" je Leiter:** fehlt eine der drei Sprossen, trägt das Signal gar nicht bei
  (`metric_format.py:467-484`). Ein fehlendes Signal erscheint nicht im Dict; sind alle abwesend,
  ist das Ergebnis `None` = „keine Aussage", nicht `NONE` = „geprüfte Entwarnung".

## Auf dem KHW anliegende Äste — drei, nicht vier

Das Ticket nennt vier Signale. Auf dem Karnischen Höhenweg (~46,6 N / 12,9 O → Gebiet `DE_ALPEN`)
liegen tatsächlich an:

| Ast | Auf dem KHW | Schwellen |
|---|---|---|
| **Wettercode** | ja | binär: 95/96/99 → `HIGH`, sonst `NONE` — **kann `LOW`/`MED` nicht erzeugen** |
| **CAPE** | ja | 300 / 750 / 1200 J/kg (icon_d2 × DE_ALPEN) |
| **Blitzpotenzial (LPI)** | ja, vom DWD | 1,0 / 30 / 50 |
| **Blitzdichte** | **nein** — strukturell abwesend, ist die Météo-France-Größe | 0,003 / 0,015 / 0,075 |
| *(Radar-Override)* | möglich | hebt auf `MED`, Träger `"radar"` |

## Die CIN-Bedingung — Angelpunkt für T2

CAPE eskaliert über `LOW` hinaus **genau dann**, wenn ein CIN-Wert vorliegt und `|CIN| ≤ 100`
(`metric_format.py:423-431`):

- `cin_jkg is None` → Deckel `LOW` („eine fehlende Hemmungsangabe ist keine schwache Hemmung")
- `|CIN| < 50` → volle Leiterstufe
- `50 ≤ |CIN| ≤ 100` → eine Stufe herunter
- `|CIN| > 100` → eine Stufe herunter **und** Deckel `LOW`

`dp.convective_inhibition_jkg` wird ausschließlich aus dem DWD-Signal `cin_ml` gefüllt
(`thunder_enrichment.py:44`); auf `DE_ALPEN` liefert `de_direct` (ICON-D2) es. Die GeoSphere-Felder
`cape_geosphere_jkg` / `convective_inhibition_geosphere_jkg` werden **absichtlich nirgends** in
`cin_jkg`/`cape_jkg` überführt (bewacht durch `tests/tdd/test_geosphere_cape_fusion_isolation.py`).

**Folge, die S2 messen muss:** Fällt der DWD-Abruf aus oder liefert er den Fehlwert −999,9
(`dwd.py:206/240`), ist CAPE auf `LOW` gedeckelt. Die Aussage aus der Messung vom 07.09., „mittel"
sei zu 95 % allein CAPE, setzt also voraus, dass an diesen Stunden CIN vorlag **und** klein war.
Ob das so war, ist offen — und entscheidet, ob die Grundlage von #2176 trägt.

## Dependencies

- **Upstream:** `providers/openmeteo.py` (Wettercode, CAPE), `providers/dwd.py` (CIN, LPI),
  `app/model_registry.py` (Schwellen), `providers/thunder_routing.py` (Gebiet)
- **Downstream:** `services/trip_report_scheduler.py` (Tagesaussage + Träger-Anzeige), alle vier
  Kanal-Renderer, Alarm-Auslösung

## Existing Specs

- `docs/specs/modules/fix_1592_s1_cape_modellschwelle.md` — Eichung der CAPE-Schwelle
- `docs/specs/modules/fix_1592_c2_cape_riskengine.md`, `fix_1592_c3_cape_delta_alarme.md`
- `docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md` — **widerspricht dem Ist-Zustand**,
  siehe #2182

## Risks & Considerations

- **Der Mitschnitt trägt die Herkunft nicht.** Er führt `thunder_level_max` und `cape_max_jkg`, aber
  weder Wettercode noch CIN noch LPI. T1 verlangt deshalb eine Nachrechnung aus Archivdaten — und
  die muss dieselben Eingangsgrößen beschaffen, die der Produktivpfad damals sah. Ob das Archiv
  `convective_inhibition` und `lightning_potential` für `icon_d2` liefert, ist in Phase 2 zu klären.
- **Nachrechnung ≠ Mitschnitt.** Eine Archiv-Nachrechnung ist eine Rekonstruktion, kein Beweis
  dessen, was der Dienst damals ausgab. Wo beide vorliegen (`thunder_level_max`, `cape_max_jkg`),
  muss die Rekonstruktion gegen den Mitschnitt geprüft werden — weicht sie ab, ist die
  Rekonstruktion die fragliche Größe, nicht der Mitschnitt.
- **Der Radar-Override ist nicht offline nachrechenbar** (`RadarNowcastService`). Stunden, in denen
  er gegriffen hat, sind aus der Rekonstruktion nicht rekonstruierbar und müssen als solche
  ausgewiesen werden, statt einem der drei Äste zugeschlagen zu werden.
- **`None` ≠ `NONE`.** „Keine Aussage" und „geprüfte Entwarnung" dürfen in der Auswertung nicht
  zusammenfallen — sonst zählt jede Lücke als Entwarnung (dieselbe Falle wie SYNOP `ww` in S1).
- T5 hängt am S1-Maßstab; T3 (CAPE-Zeitpunkt) und T4 (fehlender Auslösungsnachweis) sind aus
  denselben Archivdaten mitzurechnen, ohne dafür einen zweiten Abruf zu fahren.

---

## Analysis

### Type

Feature (Messwerkzeug + Auswertung). Kein Bugfix — es wird nichts repariert, sondern eine
Zusicherung nachgemessen.

### Der entscheidende Befund der Analyse: der Vorlauf-Versatz

Der Mitschnitt hält Vorhersagen mit **Median 21 h Vorlauf, 36 % über 48 h** (gemessen als
`fenster_start − fetched_at`, p25 = 0,5 h). `historical-forecast-api` gibt dagegen je Stunde den
**jüngsten** verfügbaren Lauf. Ein unbesehener Abgleich Rekonstruktion ↔ Mitschnitt misst deshalb
**Vorhersagedrift, nicht Rechenweise** — und würde eine korrekte Rekonstruktion verwerfen.

Zwei weitere Messfallen derselben Familie:

- **Nichtstun-Übereinstimmung:** 1358 von 2246 Zeilen sind `NONE`. Eine Trefferquote von 60 %
  entsteht ohne jede Leistung. Kalibriert wird auf `cape_max_jkg` (kontinuierlich, relative
  Abweichung quantifizierbar); Stufen werden **nur auf den Nicht-`NONE`-Zeilen** verglichen.
- **Teilmengen-Willkür:** 926 der 2246 Zeilen tragen `source: unbekannt`, nur 187 sind `briefing`.
  Die Aussage „13/13 leicht, 9× hoch" hängt an der gewählten Teilmenge. Sie muss **vorab in der
  Spec** festgeschrieben werden, mit Empfindlichkeitsangabe — sonst wiederholt S2 den S1-Fehler
  auf der Zeitachse.

### Konsequenz für T1: Ablation statt Gewinnerzuweisung

Produktiv kamen CIN und LPI vom **DWD** (`thunder_enrichment.py:44`), die Rekonstruktion nimmt sie
von **Open-Meteo**. Für den Mitschnitt gibt es zu beiden gar keinen Vergleichswert. Die Frage
„welcher Ast trug die Stufe damals?" ist damit nicht belastbar beantwortbar.

**T1 wird deshalb als Ablation gestellt:** *Welcher Ast erzeugt `HIGH` allein, wenn man die anderen
wegnimmt?* Das beantwortet dieselbe Handlungsfrage und ist robust gegen die Anbieterfrage.

### Der Prüfling

**Nicht** eine nachgebaute Fusionsfunktion — die existiert bereits (`_signal_levels()`), und eine
zweite wäre eine zweite Fusionsregel (ADR-0025 hält „eine Gewitter-Quelle" fest und weist eine
zweite Berechnung ab). Sie würde zudem nichts messen, weil per Konstruktion identisch.

Prüfling ist die **Auswertungsschicht davor und danach**, wo alle oben genannten Fehler sitzen:

1. Vorlauf-Auswahl (je Tag/Segment die Zeile mit kleinstem Vorlauf; negative Vorläufe raus)
2. Fensteraggregation Stunden → `fenster_start`/`fenster_ende` (muss `cape_max_jkg` reproduzieren)
3. Dreiwertigkeit `None` / `NONE` / Stufe — darf nirgends auf zwei kollabieren
4. Ablation: Stufe je Ast einzeln, bei fehlender Sprosse „keine Aussage" statt `NONE`

Prüfbar gegen Fixtures aus echten KHW-Archivstunden und echten Mitschnitt-Zeilen.
**Akzeptanzkriterien beschreiben die Messvorschrift, nie das Ergebnis** — ein AC der Form
„Then trägt der Wettercode ≥ 7 Tage" wäre keine Messung mehr, sondern eine vorweggenommene Antwort.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/analysis/thunder_replay.py` | CREATE | Auswertungsschicht: Vorlauf-Auswahl, Fensteraggregation, Dreiwertigkeit, Ablation. Ruft `_signal_levels()`, rechnet nicht selbst |
| `tests/tdd/test_thunder_replay.py` | CREATE | Verhaltensprüfung gegen Fixtures aus echten Archiv-/Mitschnitt-Daten |
| `tests/fixtures/khw_2026_08/*.json` | CREATE | Aufgezeichnete Stunden + Mitschnitt-Zeilen als versionierte Fixtures |

Der Abruf-/Report-Teil (Netz, Ausgabe des Protokolls) bleibt **außerhalb** des Repos unter
`/home/hem/gz-messdaten/`, weil er genau einmal läuft und keinen Wartungswert hat.

### Scope Assessment

- Files: 3 (2 neu im Repo + Fixtures)
- Estimated LoC: Modul ~120–180, Tests ~120 → **das 250er-Limit wird bei einer Scheibe eng**
- Risk Level: LOW für das System (kein Produktivpfad wird verändert), HIGH für die Aussagekraft
  (eine falsch geschnittene Messung erzeugt einen falschen Befund, der in #2176 weiterwirkt)

### Schnitt: S2a zuerst, S2b nach einem Kalibrier-Gate

| Scheibe | Thesen | Datenquelle |
|---|---|---|
| **S2a** (dieser Workflow) | **T2** (CAPE-Sprossen aus `cape_max_jkg`) · **T5** (9× HIGH gegen den S1-Maßstab 2:13) | **nur der Mitschnitt** — keine Rekonstruktion nötig, härtester Befund |
| *Kalibrier-Gate* | CAPE-Abgleich auf der Kurzvorlauf-Teilmenge (≤ 6 h) | entscheidet, ob S2b überhaupt aussagefähig ist |
| **S2b** (Folge-Workflow) | **T1** (Ablation) · **T4** (Stufe vs. Niederschlag) · **T3** (Zeitverlauf 29.08.) | Archiv-Nachrechnung |

Getrennt, weil S2b am Gate scheitern kann — T2 und T5 dürfen davon nicht mit in die
Unverwertbarkeit gezogen werden.

### Dependencies

- Upstream: `output/metric_format.py`, `app/model_registry.py`, `providers/thunder_routing.py`
- Downstream: keine — es wird kein Produktivpfad verändert. Die **Befunde** wirken auf #2176,
  #2182 und Epic #1419.

### Open Questions

- [x] Liefert das Archiv CIN und LPI für icon_d2? — **Ja**, verifiziert
- [x] Ist `metric_format` offline importierbar? — **Ja**, keine Netz-Abhängigkeit in der Kette
- [x] Sind die versendeten Briefing-Texte archiviert? — **Nein**, nur Metadaten; Nachrechnung
      ist der einzige Weg
- [ ] Welche Teilmenge des Mitschnitts trägt die Aussage? (in der Spec festzuschreiben)
- [ ] Nachzuziehen aus S1: die mittlere Aggregationszeile mit den **echten** Wegpunkten
      (3–7 je Etappe aus der Trip-Definition) statt der mitgeschnittenen

### Abgetrennt

Das **Mitschreiben der Signalherkunft** im Vorhersage-Mitschnitt gehört nicht in S2:
`_schreibgrund()` (`forecast_capture.py:109`) vergleicht das ganze `werte`-Dict, ein zusätzliches
Feld `thunder_level_signals` erzeugt Zeilen auch bei gleichbleibender Stufe und drückt gegen die
Tagesgrößen-Grenze. Eigener Designpunkt, eigenes Ticket.
