# Mini-Spec: Gewitter-Tests nehmen nachfolgenden Tests die echten Wetterquellen weg

**Gefunden:** 2026-08-03 beim Ausliefern von #1457 S2a, vor dem Push.
**Art:** Testhygiene. **Kein Produktivcode.**

## Der Fehler

`providers/base.get_provider()` lädt die echten Wetterquellen **nur, wenn die
Registry noch leer ist** (`base.py:197`, `if not _PROVIDER_FACTORIES`).

Drei Stellen in den S2a-Tests tragen ihre Test-Attrappen per `register_provider()`
ein, **ohne vorher die echten Quellen zu laden**:

- `tests/tdd/test_thunder_budget_and_failsoft.py:228`
- `tests/tdd/test_thunder_enrichment_shared_path.py:188`
- `tests/tdd/test_thunder_enrichment_shared_path.py:245`

Danach ist die Registry nicht mehr leer ⇒ `_load_providers()` läuft **nie** ⇒
`fr_direct` und alle anderen echten Quellen fehlen für den **Rest des Testlaufs**.
Aufgeräumt wird ebenfalls nicht — die Attrappen bleiben stehen.

**Belegt:** Die fünf S2a-Testdateien einzeln = alle grün. Zusammen in einem Lauf =
2 rot (`test_ac7_regulaerer_weg_liefert_blitzdichte_ohne_ausfall`,
`test_ac9_zweiter_ort_in_der_naehe_kostet_keine_zusaetzlichen_abrufe`) mit
`ProviderNotFoundError: Unknown provider: fr_direct. Available: test_werfende_quelle,
test_zweite_quelle, test_lueckenhafte_quelle`.

Die Schadwirkung endet nicht bei den eigenen Tests: **jeder** danach laufende Test,
der eine echte Quelle anfordert, bekommt sie nicht mehr.

## Was sich ändert

Die drei Stellen übernehmen das **bereits im Repo etablierte** Muster aus
`tests/tdd/test_meteofrance_direct_fallback.py:227-238`:

1. `if not base_module._PROVIDER_FACTORIES: base_module._load_providers()` —
   echte Quellen zuerst laden
2. vorherigen Eintrag merken
3. im Teardown wiederherstellen bzw. den Test-Eintrag entfernen

Kein neues Muster erfinden. Wenn sich der Dreischritt in den betroffenen Dateien
mehrfach wiederholt, darf er zu **einer** lokalen Fixture zusammengezogen werden.

## Was sich nicht ändern darf

- **Kein Produktivcode.** `src/providers/base.py` wird **nicht** angefasst —
  `register_provider` selbst nachladen zu lassen birgt Zirkelimport-Risiko
  (das Modul warnt ausdrücklich davor) und gehört nicht in eine Auslieferung.
- Die fachliche Aussage der betroffenen Tests bleibt identisch: sie prüfen
  weiterhin Fail-Soft der Gewitterquelle bzw. den gemeinsamen Anreicherungsweg.
- Keine Schwelle, kein Assert wird abgeschwächt, kein Test übersprungen.
- Die vier bestehenden Fremd-Dateien mit `register_provider` bleiben unberührt.

## Nachweis (Pflicht, in dieser Reihenfolge)

1. **Vorher rot:** die fünf Dateien in **einem** Lauf ⇒ 2 Fehlschläge (Ist-Zustand).
2. **Nachher grün:** dieselben fünf Dateien in **einem** Lauf ⇒ 24 grün.
3. **Gegenprobe Reihenfolge:** derselbe Lauf mit umgekehrter Dateireihenfolge ⇒ grün.
4. **Kein Rückschritt:** die vier Fremd-Dateien mit `register_provider`
   (`test_issue_1141_cross_provider_fallback.py`, `test_issue_1142_geosphere_direct_fallback.py`,
   `test_meteofrance_direct_fallback.py`, `test_dwd_direct_fallback.py`)
   gemeinsam mit den fünf ⇒ kein neuer Fehlschlag.
5. **Gegenprobe der Wirkung:** Die Aufräum-Zeile wieder entfernen ⇒ ein Test **muss**
   rot werden. Wird nichts rot, bewacht die Änderung nichts und der Fix ist nicht fertig.

## Manuelle Test-Schritte

Entfällt — reine Testhygiene, keine Nutzerwirkung.
