# Herkunft: MeteoAlarm-Warnungen awareness_type 12/13 (Issue #1427 S1)

Aufgezeichnet am **2026-07-31** vom oeffentlichen, auth-freien JSON-Feed
`https://feeds.meteoalarm.org/api/v1/warnings/feeds-romania` (verbraucht NICHT
das EDR-Tageskontingent, s. Spec `docs/specs/modules/feat_1427_dpc_warn_fallback.md`
Abschnitt "Test Plan").

## Dateien

- `cap_flooding_type12_ro.json` — **Rohaufzeichnung**, vollstaendiger,
  unveraenderter `alert`-Datensatz aus dem Feed. `awareness_type = "12; flooding"`,
  `awareness_level = "1; green; Minor"`, Gebiet u.a. "Alba" (Rumaenien).
- `cap_rainflood_type13_ro.json` — dieselbe Rohaufzeichnung fuer
  `awareness_type = "13; rain-flood"`, gleiches Bulletin, gleicher Abrufzeitpunkt.
- `cap_flooding_type12_ro.xml` / `cap_rainflood_type13_ro.xml` — **mechanische**
  CAP-1.2-XML-Transkription der jeweiligen JSON-Rohaufzeichnung (Feldname zu
  XML-Element 1:1, kein Wert veraendert). Grund: die bestehenden
  MeteoAlarm-Parser-Tests (seit #2266 `tests/tdd/test_meteoalarm_cap_mapper.py`,
  `_extract_alerts_from_cap()`) laden CAP als XML; der oeffentliche Feed
  liefert aber JSON. Die Provenienz steht zusaetzlich als Kommentar am
  Dateianfang jeder XML-Datei.

## Bekannte Einschraenkung

Beide Warnungen tragen `awareness_level = "1; green; Minor"` — der
Bestandscode filtert `level < 2` vor jeder Nutzeranzeige heraus. Ein
durchgehender Nachweis "gruene Wiese bis Briefing" ist damit mit diesen
Fixtures NICHT moeglich. Die S1-Tests pruefen deshalb die
Gefahren-Zuordnungsstelle direkt (`_TYPE_HAZARD_MAP` ueber die echten
CAP-Werte `awareness_type`), nicht den kompletten `_extract_alerts_from_cap()`-
Pfad inklusive Level-Filter.

**Diese Dateien werden NICHT von Hand veraendert** (insbesondere nicht
`awareness_type`/`awareness_level` hochgesetzt) — das waere keine
Aufzeichnung mehr.

## `feed_avalanche_type9.json` (Issue #1430, AC-2) — ABGELEITET

- **ABGELEITET, nicht aufgezeichnet.** JSON erlaubt keinen Kommentar; der Vermerk steht im
  Schluessel `_ABGELEITET` am Dateikopf.
- Dict `{"IT":…, "AT":…, "DE":…}`, je Land ein Feed (`{"warnings":[…]}`) mit genau einem
  Eintrag, kopiert aus `tests/fixtures/meteoalarm_feed/feed_{italy,austria,germany}_sample.json`.
  Ersetzt: `awareness_type` -> `9; avalanche`, `awareness_level` -> `3; orange; Severe`,
  `severity`, `event`, `headline`. Zeitfenster und Zonen unveraendert.

## `feed_avalanche_type9.json` (Issue #1430, AC-2) — ABGELEITET

- **ABGELEITET, nicht aufgezeichnet.** JSON erlaubt keinen Kommentar; der Vermerk steht im
  Schluessel `_ABGELEITET` am Dateikopf.
- Dict `{"IT":…, "AT":…, "DE":…}`, je Land ein Feed (`{"warnings":[…]}`) mit genau einem
  Eintrag, kopiert aus `tests/fixtures/meteoalarm_feed/feed_{italy,austria,germany}_sample.json`.
  Ersetzt: `awareness_type` -> `9; avalanche`, `awareness_level` -> `3; orange; Severe`,
  `severity`, `event`, `headline`. Zeitfenster und Zonen unveraendert.
