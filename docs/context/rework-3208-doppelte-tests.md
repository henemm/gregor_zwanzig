# Context: rework-3208-doppelte-tests

## Request Summary
Issue #3208 (Teil von Sammelprojekt #1196, Schritt 2 der Bestandsaufnahme vom 2026-11-20):
Issue-benannte Python-Testdateien gegen den aktuellen Stand prüfen und doppelte
Zusicherungen (gleiche Funktion, gleiche Eingaben, gleiche Erwartung in mehreren Dateien)
in die fachlich benannte Testdatei zusammenlegen; Issue-Bezug als Kommentar erhalten.
Abschlusskriterium: je Gruppe Mutation der geprüften Stelle vorher/nachher rot gefangen,
Kern-Schicht 100 % grün.

Vorgänger: #3207 (abgelöste Funktionen, geschlossen) — dort entstand die Regel
„tote Tests im selben Umbau mitentfernen" (Prüfdatum 2027-02-19). Schwester: #3209 (Laufzeit).

## Bestand (gemessen 2026-11-21, Stand origin/main ca6b81edd)
- 1.811 Python-Testdateien unter `tests/`, davon 368 mit Issue-Nummer/`issue` im Namen
  (Regex `(issue|_\d{3,4}(_|\.|$)|^test_\d{3,4})`), Bestandsaufnahme nannte 287 (engere Zählung).
- **Wörtlich gleiche `assert`-Texte (≥40 Zeichen) in >1 Issue-Datei: nur 45** — echte Dopplung
  ist also überwiegend *semantisch* (gleiche Funktion + Eingaben, anders formuliert), nicht textgleich.
- Methode (Skript in der Session-Scratchpad, AST-basiert): (a) gleiche Assert-Texte,
  (b) gleiche Aufrufe mit nur Literal-Argumenten über Testdateien hinweg.

## Kandidatengruppen (zur Prüfung in /20-analyse)
| Gruppe | Dateien | Geprüfte Stelle |
|---|---|---|
| G1 Gehzeit (Issue-Beispiel) | `tests/test_3196_trip_tempo_dav.py` (12), `tests/test_3197_tempo_je_etappe.py` (14), `tests/tdd/test_gehzeit_etappenregel.py` (6), `tests/tdd/test_gehzeit_folgt_wegstrecke.py` (5), `tests/tdd/test_naismith_hhmm_wrap_parity.py` (3), `tests/tdd/test_naismith_midnight_wrap_segments.py` (1), `tests/tdd/test_issue_296_be_arrival.py` (3), `tests/tdd/test_issue_802_fahrrad_segment_zeit.py` (10), `tests/unit/test_segment_builder.py` | `src/core/naismith.py` (`compute_stage_arrivals`, `derive_tempo`, `speeds_for_tempo`, `dav_hours`, `_format_hhmm`), `core/segment_builder.compute_hiking_time` |
| G2 Kanal-Layout je Berichtstyp | `tests/tdd/test_issue_429_channel_layouts.py` (8), `tests/tdd/test_issue_434_per_report_layouts.py` (8), `tests/tdd/test_reports_pro_typ.py` (15), `tests/tdd/test_3057_channel_list_resolver.py` (15) | `display_config.get_metrics_for_report_type/get_metrics_for_channel` |
| G3 Kanal-Resolver | `tests/tdd/test_3096_mail_resolver.py`, `test_3098_telegram_resolver.py`, `test_3099_sms_resolver.py`, `test_3100_premium_sms_fallliste.py` (3 gleiche Asserts 3098/3099, gleiche Helfer `_mc`, `_trip_dict`, `ChannelRow(...)`) | Kanal-Listen-Resolver |
| G4 Fix-Runden-Dateien 2795 | `tests/test_2795_fixrunde1/2/3.py`, `test_2795_alert_metric_channels_ignoriert.py`, `test_2795_alte_regel_kanaele_ignoriert.py`, `test_2795_migration_alert_metric_channels.py`, `tests/tdd/test_migration_2792_profil_ampel.py` | Alarm-Metrik-Kanäle / Migration |
| G5 Nowcast/Radar | `test_feature_656_radar_nowcast.py`/`test_feature_660_convective_stage.py` (`intensity_to_text`), `test_feature_734_arome_france_nowcast.py`/`test_feature_761_icon_d2_nowcast.py` (3 gleiche Asserts) | Radar-/Nowcast-Service |
| G6 Provider-Fallback | `test_issue_1115/1141/1142/1155_*` | Fallback-Kette |
| G7 Fixloop-Dateien | `test_compare_channel_layouts_3039(_fixloop).py`, `test_s1c4b_fixloop1/2/3_*`, `test_3047_runde7_*`/`r7`/`r8py`/`r9` (11 Dateien) | diverse |
| G8 Sprachkatalog (Issue-Beispiel) | ~30 Dateien `test_i18n_*`, `*_zweisprachig.py` — meist fachlich benannt, Issue-Dateien selten | `src/i18n` Katalog |

## Existing Patterns
- Fachlich benannte Testdateien existieren bereits (z. B. `test_gehzeit_etappenregel.py`) — Zielort.
- #3207 hat tote Tests entfernt und eine Collect-Baseline gemischter Dateien angelegt; dieselben
  Wächter (Doku-Wächter #316, `tests/test_stillgelegte_testdateien.py`) greifen bei Löschungen.
- Gemeinsame Helfer: `tests/helpers/` (`kanal_liste_orakel`, `versand_fixture`, `scheduler_sprache_fixture`).
- Test-Politik: kein Mock-Theater; `uv run pytest` nur mit benannten Dateien (#1477).

## Dependencies / Dependents
- Upstream: nur Testcode; Produktionscode bleibt unverändert.
- Downstream: Verweise auf Testdateinamen in Doku/Specs/Gates (z. B. `docs/specs/**`, `.claude/workflows/*.json`
  `test_files`, Ratschen-Listen, `tests/test_stillgelegte_testdateien.py`). Vor Umbenennen/Löschen
  per `grep -rn <dateiname>` prüfen.

## Existing Specs
- `docs/reference/gates_und_ratschen.md` (Test-Politik), Spec aus #3207 (`docs/specs/` — Regel „tote Tests mitentfernen").

## Risks & Considerations
- **Scope:** 368 Dateien sind für einen Durchlauf zu viel. Analyse muss eine erste, abgeschlossene
  Scheibe wählen (z. B. G1 Gehzeit + G2 Kanal-Layout + G3 Resolver) — Rest als eigene Issues
  im Sammelprojekt #1196 (PO-Regel: Epic mit eigenen Issues, keine Teilaufgaben-Listen).
- Abdeckungsverlust: Zusammenlegen darf keine Zusicherung verlieren → Mutationsnachweis vorher/nachher je Gruppe.
- Unterschiedliche Fixtures/Zeitfixierung (freezegun) in den Quell-Dateien: beim Verschieben mitnehmen.
- Verweise auf alte Dateinamen in Workflow-JSONs/Specs/Gates können Gates brechen.
- Renderer-Commit-Gate könnte bei Testdateien zu Mail-Inhalten anspringen.

## Analysis

### Type
Rework (nur Testcode, Produktionscode unverändert)

### Befund je Gruppe (Explore-Auswertung 2026-11-21)
- **G1 Gehzeit — echte Dopplungen vorhanden.**
  - `tests/tdd/test_gehzeit_etappenregel.py` ac4/ac7 sind laut eigenem Text „Regressionswächter für #2042 AC-1/AC-2"
    und prüfen dasselbe wie `tests/tdd/test_gehzeit_folgt_wegstrecke.py` ac1/ac2 (gleiche Helfer `_stage`/`_wp`,
    gleiche Eingaben, gleiche Erwartung). wegstrecke ac3 (Rückfall je Etappe, Lücke an G3) ~ etappenregel ac3
    (Lücke an G2); wegstrecke ac4 (km 12→4) ~ etappenregel ac2[kleiner] (km 5→4): gleiche Äquivalenzklasse,
    in /30 je Fall entscheiden (Zusatz-Zusicherung „folgt >0" in wegstrecke ac4 beachten).
    wegstrecke ac5 (Go-Paritätswert 10:30) ist einzigartig → wandert nach etappenregel.
    ⇒ `test_gehzeit_folgt_wegstrecke.py` geht in `test_gehzeit_etappenregel.py` auf, Datei entfällt,
    #2042-Bezug als Kommentar.
  - `tests/test_3196_trip_tempo_dav.py::test_save_trip_schreibt_tempo_und_rechnet_dav` (08:00/10:30/12:12)
    == `tests/test_3197_tempo_je_etappe.py::test_bestand_ohne_ueberschreibung_unveraendert` (gleiche Geometrie S1,
    fuss 4). Einer entfällt (3197 behält den Etappen-Tempo-Fokus).
  - `tests/tdd/test_issue_802_fahrrad_segment_zeit.py`: ac3[W] == ac4 (identisch, gleiche Datei); ac3[A] ⊂ ac1
    (ac1 zusätzlich Persistenz).
  - Bleiben (andere Schicht): 3197 Grenzwert-Paare Loader vs. `stage_speeds` direkt; 3196 `dav_hours`-Falltabelle
    vs. `save_trip`.
  - Unberührt: `tests/unit/test_segment_builder.py` (einzige Abdeckung `compute_hiking_time`),
    `test_naismith_hhmm_wrap_parity.py`, `test_naismith_midnight_wrap_segments.py`,
    `test_issue_296_be_arrival.py` (Scheduler-Test nur „ähnlich" zu 802 ac6, andere Werte).
- **G2 Kanal-Layout — keine Dopplung.** 429/434/`test_reports_pro_typ.py` prüfen ähnliche Muster auf
  verschiedenen Ebenen (Kanal vs. Bericht) mit anderen Fixtures; `test_3057` ac1 ist ein Orakel über alle
  Kombinationen (Obermenge der Eigenschaft, ohne Nachweis, dass es jede Mutation fängt). Kein Umbau.
  Nebenbefund: veraltete „RED, noch nicht existierende API"-Docstrings in 429/434.
- **G3 Kanal-Resolver — überwiegend kanalspezifisch.** 3098/3099 haben gleiche Eingaben, aber je Kanal andere
  Soll-Strings ⇒ höchstens parametrisierbar (Refactor, nicht Gegenstand von #3208).
  **Einzige echte Teilmenge:** `tests/tdd/test_3099_sms_resolver.py::test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene`
  vs. `tests/tdd/test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms` (3100 breiter:
  drei Premium-Ebenen × Befehle über den echten Eingang). ac6 trägt zusätzlich den Festwert
  `"E1 R2.0@4 G45@4 CT:SCT@4"` → vor dem Entfernen in einen bleibenden SMS-Test übernehmen; `<=153` deckt 3100 ab.
  **Pflicht:** ac6 steht in zwei Falllisten (`tests/fixtures/einstellung_gleich_mail/fallliste_sms.json`
  id `sms-premium-gleich-sms-text`, `fallliste_premium_sms.json` id `psms-trip-versand-abweichend`); der Wächter
  `tests/tdd/test_einstellung_gleich_mail_fallliste.py` prüft diese Verweise ⇒ Einträge auf den Ersatztest umstellen.
  Helfer-Duplikate (`_mc`, `_orte_liste`, `_trip_dict`, `_AbweichendesModell`) nur ähnlich → nicht in dieser Scheibe.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_gehzeit_etappenregel.py | MODIFY | nimmt einzigartige Fälle aus wegstrecke auf (ac5 Go-Parität, ggf. ac3/ac4-Zusatz), #2042-Kommentar |
| tests/tdd/test_gehzeit_folgt_wegstrecke.py | DELETE | vollständig in etappenregel aufgegangen |
| tests/test_3196_trip_tempo_dav.py bzw. tests/test_3197_tempo_je_etappe.py | MODIFY | doppelten save_trip-Fall S1 einmal entfernen |
| tests/tdd/test_issue_802_fahrrad_segment_zeit.py | MODIFY | ac3[W]/ac4-Dopplung und ac3[A]⊂ac1 auflösen |
| tests/tdd/test_3099_sms_resolver.py | MODIFY | ac6 entfernen, Festwert in bleibenden SMS-Test übernehmen |
| tests/fixtures/einstellung_gleich_mail/fallliste_sms.json, fallliste_premium_sms.json | MODIFY | Testverweis von 3099 ac6 auf Ersatztest |
| Kommentar-/Doku-Verweise auf die gelöschte Datei (z. B. Go-Testkommentar, docs/specs) | MODIFY | nur Kommentar/Doku |
| docs/context/rework-3208-doppelte-tests.md | MODIFY | Mutationsprotokoll vorher/nachher, G2-Begründung |

### Scope Assessment
- Dateien: ~8–10 (davon 1 DELETE), nur Tests/Fixtures/Doku
- Estimated LoC: +60 / −200
- Risk Level: LOW (kein Produktionscode; Risiko = versehentlicher Abdeckungsverlust, abgesichert durch Mutationsnachweis)

### Technical Approach
1. **Kriterium:** entfernt wird nur, was identisch ist (Funktion+Eingabe+Erwartung) oder echte Teilmenge einer
   bleibenden Zusicherung. „Ähnlich" (andere Ebene/andere Werte) bleibt. Kein Parametrisieren aus Optik.
2. **Mutationsnachweis je Gruppe vorher/nachher** (Mutation per String-Ersetzung mit externer Sicherungskopie,
   nie per git zurücksetzen; nur benannte Testdateien):
   - G1a `core/naismith.compute_stage_arrivals`: gemessene Strecke ignorieren (immer Luftlinie) → rot in etappenregel ac4.
   - G1b: Rückfall bei fehlender/fallender Strecke kippen → rot in etappenregel ac2/ac7.
   - G1c: Grundtempo in `speeds_for_tempo` bzw. Steigungsgewicht in `dav_hours` ändern → rot in 3196/3197/802.
   - G1d: Aufstiegsrate ändern → rot im übernommenen Go-Paritätstest (10:30).
   - G3: Premium-Zweig liest Premium-Liste statt SMS-Liste → rot in 3100 ac1; SMS-Kürzel ändern → rot im übernommenen Festwert.
   Protokoll (Mutation · Testmenge vorher rot? · Testmenge nachher rot?) im Context-Dokument.
3. Vor jedem Löschen: Namenssuche über tests/, docs/, internal/, frontend/, .claude/; Imports zwischen
   Testdateien prüfen; Collect-Only vorher/nachher vergleichen (Baseline #3207,
   `tests/test_stillgelegte_testdateien.py`, Doku-Wächter #316).
4. Dateien 3096/3098/3099/3100/3196/3197/802 werden **nicht** umbenannt (Wächter, Spec- und Frontend-Verweise).

### Dependencies
- Wächter `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (PY_TEST_GLOBS + Falllisten-JSON).
- 3100 importiert `_orte_sms` aus 3099 (bleibt erhalten).
- Frontend `naismith_stage_tempo_3197.test.ts` nennt `tests/test_3197_tempo_je_etappe.py` (Datei bleibt).

### Abspaltung (Pflicht in /30: eigene Issues im Epic #1196, strang:a-plattform)
- G4 Fix-Runden 2795 · G5 Nowcast/Radar (734/761, 656/660) · G6 Provider-Fallback (1115/1141/1142/1155)
- G7 Fixloop-Dateien (11) · G8 Sprachkatalog (~30)
- G2 nur dokumentiert (keine Dopplung), kein Issue. G3-Helfer-Konsolidierung optional als eigenes Issue.

### Befunde gegen den Plan
- Die Ausbeute ist klein: nur 45 wörtlich gleiche Asserts in 368 Dateien, in G2/G3 fast keine echte Dopplung.
  #3208 liefert Methode + erste Scheibe, keinen Großumbau. So ehrlich berichten.
- Korrektur zum Plan-Entwurf: der doppelte save_trip-Fall liegt in `tests/test_3196_trip_tempo_dav.py`, nicht in
  `test_3196_migration_trip_tempo.py`.

### Open Questions
- Keine Produktfrage. Einzelentscheidungen (wegstrecke ac3/ac4 aufgehen lassen oder behalten) trifft /30 nach Lesen der Tests.

## TDD RED: Mutationsnachweis „vorher" (2026-11-21, Stand ca6b81edd)

Kein neuer Produktcode, daher kein klassischer RED-Test (Spec, Test Plan): der RED-Schritt ist
die Gegenprobe vor dem Umbau. Skript: String-Ersetzung im Produktcode mit externer
Sicherungskopie (Session-Scratchpad), Lauf nur der benannten Testdateien, Wiederherstellung
aus der Sicherung mit SHA-256-Vergleich, danach Kontroll-Lauf grün. Rohprotokoll:
`docs/artifacts/rework-3208-doppelte-tests/mutation-vorher.txt`; Collect-Baseline (208 Tests in
den 8 berührten Dateien): `collect-vorher.txt`.

| Mutation | Stelle | vorher | gefangen u. a. von |
|---|---|---|---|
| G1a gemessene Strecke ignoriert | `compute_stage_arrivals` | ROT (27) | etappenregel ac4, ac5; wegstrecke ac1, ac5; 3196; 3197 |
| G1b-abschnitt Rückfall je Abschnitt statt je Etappe | `compute_stage_arrivals` | ROT (3) | etappenregel ac1, ac5; **wegstrecke ac3** |
| G1b-monotonie Monotonie-Prüfung aus | `stage_measured_distances` | **GRÜN** | — (siehe Befund) |
| G1b-rückfall-aus Monotonie + Plausibilität aus | `stage_measured_distances` | ROT (4) | etappenregel ac1, ac2[gleich], ac2[kleiner]; wegstrecke ac4 |
| G1c-grundtempo v × 1,25 | `speeds_for_tempo` | ROT (52) | wegstrecke ac5; 802 ac2; 3196; 3197 |
| G1c-gewicht min/3 statt min/2 | `dav_hours` | ROT (35) | wegstrecke ac5; 3196; 3197 |
| G1d Aufstiegsrate zu Fuß 350 | `_REFERENZ` | ROT (40) | wegstrecke ac5; 802 ac3[W], ac4; 3196; 3197 |
| G3a Premium liest Premium-Liste | `trip_report` Premium-Text | ROT (10) | 3099 ac6; 3100 ac1 (6×), ac3, ac4 |
| G3b Kürzel Niederschlag Q statt R | `metric_catalog` | ROT (38) | 3099 ac2–ac10 (u. a. ac6) |

Alle Wiederherstellungen bit-gleich (SHA-256), Kontroll-Lauf jeweils grün; `git status src/` leer.

### Befunde für /50-implement (Erwartung „nachher" präzisiert)
- **G1b-monotonie ist schon heute unbeobachtbar:** Bei fallendem oder gleichem Kilometerwert
  greift immer auch die Plausibilitätsprüfung (Teilstrecke ≤ 0 < Luftlinie), solange die beiden
  Wegpunkte verschiedene Koordinaten haben. Die Monotonie-Regel ist dadurch redundant abgesichert,
  nicht ungeschützt; kein Abdeckungsverlust durch #3208. Für den Nachher-Vergleich zählt
  G1b-rückfall-aus (beide Prüfungen aus). Kein Umbau an Produktcode (außerhalb des Umfangs).
- **G1b-abschnitt** fängt heute neben etappenregel ac1/ac5 die wegstrecke ac3; nachher muss der
  übernommene `test_ac3b_luecke_am_etappenende_entwertet_die_etappe` rot werden.
- **G1b-rückfall-aus** fängt heute wegstrecke ac4 und etappenregel ac2[kleiner]; nachher genügt ac2[kleiner].
- **G1c** trifft 802 nur über ac2 (Grundtempo), nicht ac3[W]/ac1; ac3[W] und ac4 fängt G1d.
  Spec-Tabelle G1c („rot in 802 ac3[W], ac1") ist damit für 802 zu eng formuliert: maßgeblich
  ist „rot in 3196, 3197 und mindestens einem 802-Test"; ac4 → ac3[W] bleibt durch G1d belegt.
- **G1d** und **G1c** fangen heute wegstrecke ac5; nachher muss der übernommene
  `test_ac8_paritaet_erwartungswerte_fuer_die_go_seite` rot werden.
- **G3a/G3b:** nachher 3100 ac1 (G3a) bzw. der neue Festwert-Test in 3099 (G3b) rot.

Reproduktion (für den Nachher-Lauf in /50-implement): `python3 docs/artifacts/rework-3208-doppelte-tests/mutate.py nachher docs/artifacts/rework-3208-doppelte-tests/mutation-nachher.txt`
(Phase `nachher` lässt die gelöschte Wegstrecken-Datei automatisch weg; Sicherungen per `mkdtemp` außerhalb des Repos).

## GREEN: Mutationsnachweis „nachher" (2026-11-21, nach dem Umbau)

Gleiches Skript wie vorher, Phase `nachher` (Wegstrecken-Datei entfällt aus dem Lauf). Rohprotokoll:
`docs/artifacts/rework-3208-doppelte-tests/mutation-nachher.txt`. Jede Wiederherstellung per SHA-256 gegen
das Original geprüft, Kontroll-Lauf danach jeweils grün (exit 0); `git status --short src/` leer.

| Mutation | vorher | nachher | gefangen von (bleibender Test) | wiederhergestellt grün |
|---|---|---|---|---|
| G1a gemessene Strecke ignoriert | ROT (27) | ROT (26) | etappenregel ac4, ac5, **ac8_paritaet**; 3196; 3197 | ja (106 passed) |
| G1b-abschnitt Rückfall je Abschnitt | ROT (3) | ROT (3) | etappenregel ac1, ac5, **ac3b_luecke_am_etappenende** | ja |
| G1b-monotonie Monotonie-Prüfung aus | GRÜN | GRÜN | — (vorher schon redundant durch die Plausibilitätsprüfung, siehe Befund RED; kein Abdeckungsverlust) | ja |
| G1b-rückfall-aus Monotonie + Plausibilität aus | ROT (4) | ROT (3) | etappenregel ac1, ac2[gleich], **ac2[kleiner]** | ja |
| G1c-grundtempo v × 1,25 | ROT (52) | ROT (52) | etappenregel ac8_paritaet; **802 ac2**; 3196; 3197 | ja |
| G1c-gewicht min/3 statt min/2 | ROT (35) | ROT (35) | etappenregel ac8_paritaet; 3196; 3197 | ja |
| G1d Aufstiegsrate zu Fuß 350 | ROT (40) | ROT (39) | **etappenregel ac8_paritaet**; **802 ac3[W]**; 3196; 3197 | ja |
| G3a Premium liest Premium-Liste | ROT (10) | ROT (9) | **3100 ac1** (6×), ac3, ac4 | ja (72 passed) |
| G3b Kürzel Niederschlag Q statt R | ROT (38) | ROT (38) | 3099 ac2–ac10, u. a. **ac2_sms_folge_niederschlag_boe_bewoelkung** | ja |

Die Rückgänge der Rot-Zahl (G1a −1, G1b-rückfall-aus −1, G1d −1, G3a −1) sind genau die entfernten Fälle
(wegstrecke ac1/ac5 → etappenregel ac4/ac8; wegstrecke ac4 → ac2[kleiner]; 802 ac4 → ac3[W]; 3099 ac6 → 3100 ac1);
G1a und G1d zählen netto nur −1, weil die neue ac8 die wegfallende wegstrecke ac5 ersetzt. Keine Mutation, die
vorher rot war, ist nachher grün.

### Collect-Differenz vorher/nachher

`collect-vorher.txt` 208 Tests → `collect-nachher.txt` 203 Tests (dieselben 7 bestehenden Dateien; die
Wegstrecken-Datei entfällt), keine Collect-Fehler. Differenz exakt nach Plan:
- weg: `test_gehzeit_folgt_wegstrecke.py` ac1–ac5 (5), `test_issue_802_fahrrad_segment_zeit.py::test_ac3_python_naismith_matches_fixed_contract[A]`,
  `::test_ac4_wanderer_default_naismith_sum`, `test_3099_sms_resolver.py::test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene` (8)
- neu: `test_gehzeit_etappenregel.py::test_ac3b_luecke_am_etappenende_entwertet_die_etappe`,
  `::test_ac8_paritaet_erwartungswerte_fuer_die_go_seite`, `test_3099_sms_resolver.py::test_ac2_sms_folge_niederschlag_boe_bewoelkung` (3)
- netto −5 (Wegstrecke −3, 802 −2, 3099 ±0).

### Geprüft, keine echte Dopplung (bleibt unverändert)
- **G2 Kanal-Layout** (429, 434, `test_reports_pro_typ.py`, 3057): ähnliche Muster auf verschiedenen Ebenen
  (Kanal vs. Bericht) mit anderen Fixtures; 3057 ac1 ist ein Orakel über alle Kombinationen. Weder identisch
  noch Teilmenge, kein Umbau (siehe Analysis).
- **3196 vs. 3197** (`test_save_trip_schreibt_tempo_und_rechnet_dav` vs. `test_bestand_ohne_ueberschreibung_unveraendert`):
  3196 belegt den Vorrang des gespeicherten Tempos vor `activity="fahrrad_20"` und den Erhalt von `activity`,
  3197 prüft ohne `activity` zusätzlich `stage_speeds == tempo_speeds` und S2. Nur der Zahlenwert ist gleich;
  beide bleiben (Spec, Einzelentscheidung 2).

### Verwaiste Verweise
Suche nach `test_gehzeit_folgt_wegstrecke`, `test_ac4_wanderer_default_naismith_sum`,
`test_ac6_premium_gleich_sms_trotz_abweichender_premium_ebene` über tests/, docs/, internal/, frontend/, .claude/:
umgestellt in beiden Falllisten (auf `test_3100_premium_sms_fallliste.py::test_ac1_trip_eingang_premium_gleich_sms`,
`AC-1`, Befund „ersetzt #3099 AC-6 (#3208)"), in `docs/context/feat-3100-premium-sms-fallliste.md` und in
`docs/specs/_archive/tests/issue_802_fahrrad_segment_zeit_tests.md`. Verbleibend nur der von der Spec verlangte
Herkunfts-Kommentar im Kopf von `test_gehzeit_etappenregel.py` sowie dieses Dokument, Spec und Artefakte.
