# Context: rework-3263-doppelte-tests-2795

## Request Summary
Issue #3263 (Teil von #1196, abgespalten aus #3208, Gruppe G4): die Fix-Runden- und
Migrations-Testdateien zu #2795/#2792 auf doppelte Zusicherungen prüfen und Dopplungen
entfernen. Kriterium wie #3208 (`docs/context/rework-3208-doppelte-tests.md`): entfernt wird nur,
was identisch ist (Funktion + Eingabe + Erwartung) oder echte Teilmenge einer bleibenden
Zusicherung; „ähnlich" (andere Schicht, andere Werte, anderer Eingangsweg) bleibt.
Je Gruppe Mutationsnachweis vorher/nachher, Kern-Schicht 100 % grün.

## Related Files
| File | Relevance |
|------|-----------|
| tests/test_2795_fixrunde1.py (316) | Briefing-Uhrzeit 06:45, Nachhol-Hinweise, migrate_2795, Kanal-Auflösung; liefert Helfer an fixrunde2 |
| tests/test_2795_fixrunde2.py (192) | Totalausfall/overdue/Vermerk-Minute, migrate_2795 mit Regeln+Altschlüssel |
| tests/test_2795_fixrunde3.py (122) | zweiter Fehlschlag, no_weather, unlesbare Minute |
| tests/test_2795_alert_metric_channels_ignoriert.py (363) | Altschlüssel `alert_metric_channels` ohne Wirkung (Trip/Vergleich); liefert Helfer an alte_regel |
| tests/test_2795_alte_regel_kanaele_ignoriert.py (117) | alte `alert_rules[].channels` ohne Wirkung |
| tests/test_2795_migration_alert_metric_channels.py (227) | migrate_2795 Probelauf/Execute/Sicherung/Idempotenz |
| tests/tdd/test_migration_2792_profil_ampel.py (545) | migrate_2792 Profil-Ampel, AC-8…AC-23 |
| scripts/migrate_2792_profil_ampel.py | Produktionsstelle der einzigen Dopplung (Z. 56–62 `_NICHT_ZUORDENBAR`, Z. 118–121 Berichtstext) |

## Existing Patterns
- Methode und Kriterium aus #3208 (Mutation per String-Ersetzung mit externer Sicherungskopie).
- Helfer-Importe zwischen Testdateien: alte_regel ← alert_metric_channels_ignoriert; fixrunde2 ← fixrunde1;
  fixrunde1/2 ← test_2795_viertelstunden_faelligkeit, tdd/test_compare_mail_fuss_naechster_versand;
  fixrunde2/3 ← tdd/test_compare_briefing_nachholen.

## Dependencies
- Upstream: nur Testcode; Produktionscode unverändert.
- Downstream: Doku-Verweise auf Dateinamen (specs feat_2795_s3b_teil1, feat_2792_s1, context-Dokus),
  Kommentare in tests/tdd/test_alert_metric_channel_reader.py — alle auf Dateien, keiner auf den
  entfallenden Testnamen. Messprotokolle `docs/artifacts/perf-3209-pytest-laufzeit/collect-*.txt` nennen ihn,
  werden aber von nichts gelesen (historisches Protokoll, bleibt).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (AC-23), `docs/specs/modules/feat_2795_s3b_teil1_zustellung.md`.

## Analysis (Summe 1: Kontext und Analyse in einem Durchgang, 1× Agent-Auswertung 2026-11-23)

### Befund
Nach dem strengen Kriterium gibt es **genau eine echte Teilmenge**:

- `tests/tdd/test_migration_2792_profil_ampel.py::test_ac23_neu_erkannte_nicht_zuordenbare_schluessel_stehen_im_bericht`
  (5 Fälle: wind_direction_deg, cloud_mid_avg_pct, cloud_high_avg_pct, pressure_avg_hpa, precip_type_dominant)
  ⊂ `…::test_ac23_nicht_zuordenbar_mit_begruendung_und_bereich_bleibt_erhalten` (7 Fälle, enthält alle 5).
  Gleicher Aufruf `_vgl_ampel(tmp_path, [_band(key, 1, 9)])`; der bleibende Test prüft den vollen Berichtstext
  (`nicht zuordenbar: {key} [1, 9] (corridors): {grund}, erhalten, nicht migriert` ⊃ `nicht zuordenbar: {key}`),
  `not ampel.get("metrics")` und zusätzlich den Erhalt der `corridors`. Keine Zusatz-Zusicherung zu übernehmen.
  (Selbst gegengeprüft gegen Quelltext Z. 487–523.)

In den sechs 2795-Dateien ist nichts identisch und nichts echte Teilmenge. Ähnlich, aber bleibt (Auswahl, Grund):
- alte_regel hoch/gering ↔ ac29_trip hoch/gering: anderer Eingangsweg (alte Regel-Kanäle vs. Altschlüssel).
- ac29_trip_altschluessel_aendert_nichts ↔ ac29_trip_hoch: aendert_nichts fährt zusätzlich „ohne Altschlüssel".
- ac29_vergleich_kette ↔ dispatcher: kette prüft zusätzlich `split_by_threshold`; versandweg = andere Schicht.
- f005_loader ↔ test_trip_alert_metric_channels_roundtrip: andere Werte.
- f001 ↔ f010, f002_vergleich ↔ f011 ↔ f013, f011_bestandsvermerk ↔ f015, f003 ↔ f012 ↔ ac28 ↔ 10a0:
  jeweils andere Zweige/Eingaben/Dateiinhalte.
- 2792 ratsche (Band 5,50, alle Schlüssel), gewitter_und_cape (andere Bänder): bleiben.

**Keine ganze Datei entfällt** (jede trägt eigene Zusicherungen; fixrunde1 und alert_metric_channels_ignoriert
liefern zudem Helfer). Fachliches Umbenennen/Zusammenlegen wäre Umbau, nicht Gegenstand von #3263.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_migration_2792_profil_ampel.py | MODIFY | `test_ac23_neu_erkannte_…` samt Parametrisierung entfernen (≈ −10 LoC), Kommentar am bleibenden Test „deckt auch die bei #2792 neu erkannten Schlüssel ab" |
| docs/context/rework-3263-doppelte-tests-2795.md | MODIFY | Mutationsprotokoll vorher/nachher |

### Mutationsnachweis (Plan)
- **M1 beide rot (vorher):** `scripts/migrate_2792_profil_ampel.py` Z. 119 `"    nicht zuordenbar: {key}` →
  `"    nicht-zuordenbar: {key}` ⇒ neu_erkannte UND begruendung rot; nachher begruendung allein rot.
- **M2 Gegenprobe (bleibender Test strenger):** Eintrag `"wind_direction_deg": …` aus `_NICHT_ZUORDENBAR` entfernen ⇒
  Schlüssel fällt in den allgemeinen Text Z. 125; neu_erkannte[wind_direction_deg] bleibt grün,
  begruendung[wind_direction_deg] wird rot.

### Scope Assessment
- Dateien: 1 Testdatei + Kontext-Doku; LoC ≈ −10/+2. Risk LOW (nur Testcode).

### Risks & Considerations
- Abdeckungsverlust: durch M1/M2 ausgeschlossen.
- Ergebnis „fast nichts doppelt" ist selbst ein Befund für #1196: die 2795-Dateien sind trotz Fix-Runden-Namen
  inhaltlich disjunkt; fachliche Umbenennung wäre ein eigenes Thema (nicht Teil dieses Issues).

## Mutationsprotokoll (Phase 5, RED-Lauf „vorher", 2026-11-23)

Lauf per Skript `docs/artifacts/rework-3263-doppelte-tests-2795/mutation_lauf.sh <vorher|nachher>` (Ordner ist
gitignored, liegt nur lokal im Worktree; Vollausgabe daneben in `test-red-output.txt`). Ablauf: Migrationsskript in
den Scratchpad sichern, Mutation per String-Ersetzung, nur die benannte Testdatei laufen lassen
(`-o addopts="" -m "not email and not live and not staging"` für vollständige Zusammenfassungszeilen),
Wiederherstellung per Kopie aus der Sicherung, `cmp` gegen die Sicherung. Kein git checkout/stash/reset.

| Mutation | vorher | nachher (Phase 6) |
|---|---|---|
| Basis | 12/12 AC-23-Fälle grün | offen |
| M1 (`f"    nicht zuordenbar: {key}` → `nicht-zuordenbar`, 2 Stellen Z. 119/125) | 12 rot: alle 5 `neu_erkannte` + alle 7 `begruendung` | offen (erwartet: 7 `begruendung` rot) |
| M2 (`wind_direction_deg` aus `_NICHT_ZUORDENBAR`) | `neu_erkannte[wind_direction_deg]` **grün** (fängt nicht), `begruendung[wind_direction_deg]` rot | offen (erwartet: `begruendung` rot) |
| Wiederherstellung | byte-identisch zur Sicherung, Datei 44/44 grün | offen |
| Collect | 44 Tests, davon 5 `neu_erkannte` + 7 `begruendung` | offen (erwartet: 39, nur 7 `begruendung`) |

M2 belegt schon vorher: der zu entfernende Test fängt diese Mutation nicht, der bleibende schon.

## Mutationsprotokoll (Phase 6, Lauf „nachher“, 2026-11-23)

Gleiches Skript (`mutation_lauf.sh nachher`, Sicherung im Scratchpad der aktuellen Sitzung), Vollausgabe in
`docs/artifacts/rework-3263-doppelte-tests-2795/mutation-nachher-output.txt` (reiner Grünlauf: `test-green-output.txt`). Stand: `test_ac23_neu_erkannte_...` samt
Parametrisierung entfernt, `test_ac23_nicht_zuordenbar_mit_begruendung_...` inhaltlich unverändert (nur Kommentar).

- **M1 nachher:** 2 Ersetzungen; 7 failed / 32 deselected, rot sind genau die 7 `begruendung`-Fälle
  (thunder_level_max, cape_max_jkg, wind_direction_deg, cloud_mid_avg_pct, cloud_high_avg_pct, pressure_avg_hpa,
  precip_type_dominant). Die Mutation wird weiterhin für alle 5 ehemals doppelt geprüften Schlüssel gefangen.
- **M2 nachher:** `begruendung[wind_direction_deg]` rot (1 failed / 38 deselected).
- **Wiederherstellung:** `cmp` byte-identisch zur Sicherung, Datei 39/39 grün;
  `git diff origin/main -- scripts/migrate_2792_profil_ampel.py` leer.
- **Collect:** vorher 44, nachher 39 Tests; keine `neu_erkannte`-Fälle mehr, alle 7 `begruendung`-Fälle vorhanden,
  keine Collect-Fehler.
- **Benannte Dateien** (2792-Migration + sechs `test_2795_*.py`): 87 passed, 0 failed.

| Mutation | vorher | nachher |
|---|---|---|
| Basis | 12/12 AC-23-Fälle grün | 7/7 AC-23-Fälle grün |
| M1 (`nicht zuordenbar` → `nicht-zuordenbar`, Z. 119/125) | 12 rot (5 `neu_erkannte` + 7 `begruendung`) | 7 rot (alle `begruendung`) |
| M2 (`wind_direction_deg` aus `_NICHT_ZUORDENBAR`) | `neu_erkannte[wind_direction_deg]` grün, `begruendung[wind_direction_deg]` rot | `begruendung[wind_direction_deg]` rot |
| Wiederherstellung | byte-identisch, 44/44 grün | byte-identisch, 39/39 grün |
| Collect | 44 | 39 (−5 = genau die Fälle des entfernten Tests) |

Ergebnis: keine Mutation ist nachher grün; durch das Entfernen geht kein Schutz verloren.
