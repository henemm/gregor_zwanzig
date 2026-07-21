---
entity_id: official_alert_dedup_timespan
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [official-alerts, dedup, bug, "1245"]
---

# Amtliche-Warnung-Dedup: Zeitraum als Identitätsbestandteil (#1245)

## Approval

- [ ] Approved

## Purpose

`dedupe_official_alerts` verwirft still den zweiten von zwei Gültigkeitszeiträumen, wenn zwei amtliche Warnungen dieselbe Region und Gefahr, aber unterschiedliche Zeiträume haben — der Empfänger unterschätzt die Dauer der Gefahr. Diese Spec macht den Zeitraum zum Bestandteil der Warn-Identität, sodass unterschiedliche Perioden getrennt erhalten bleiben, hält dabei die bestehende Dedup-/Eskalations-Semantik und macht die getrennten Perioden auch in den kompakten Darstellungen unterscheidbar.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
  - **Identifier:** `dedupe_official_alerts` (Z.254–298), `render_official_alerts_html` (Z.154–210), `render_official_alerts_plain` (Z.213–221)
- **File:** `src/services/trip_alert.py` — **Identifier:** `check_official_alert_triggers` / `_record_official_alert_state` (Z.929–954)
- **File:** `src/services/compare_official_alert.py` — **Identifier:** `_detect` / `_record_state` (Z.151–181)

Schicht: **Python-Core / Domain-Backend** (`src/output/`, `src/services/`). Kein Frontend-, kein Go-Anteil.

## Estimated Scope

- **LoC:** ~60–100 (Quellcode; Tests/Docs zählen nicht aufs Limit)
- **Files:** 3 Quellcode + 1–2 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlert` (`src/services/official_alerts/models.py:14–33`) | Datenmodell | liefert `valid_from`/`valid_to`, `dedup_id`, `region_label`, `label`, `hazard`, `level` |
| `dedupe_official_alerts` | kanonische Dedup-Stufe | speist alle 8 Konsumenten (Notice, Badge, Plain, Compact, Compare-Streifen, HTML-Warnblock, Trip-Trigger, Compare-Trigger) |
| `_bundle_by_hazard_level` | 2. Verdichtungsstufe (nur Warn-Sektion) | hält Zeitraum bereits als Schlüssel — bleibt unverändert |

## Implementation Details

```
PRIMÄRER VERLUSTORT (Trigger-/Ein-Ort-Fluss) — base.py get_official_alerts_for_location:
  Der Cross-Source-Kollaps läuft VOR dedupe_official_alerts und kollabierte bisher
  nach reinem `hazard`-Schlüssel → zwei Perioden gleicher Gefahr an EINEM Ort
  verschwanden hier, bevor dedupe sie je sah.
  Künftig QUELLEN-PARTITIONIERUNG (PO-Entscheidung 2026-07-15 „nie doppelt"):
    - Pass 1: bestimme je `hazard` die BESTE Quelle = höchstes `level` unter ihren
      Alerts; bei Gleichstand die zuerst gesammelte (= zuerst registrierte) Quelle.
    - Pass 2: behalte ausschließlich die Alerts DIESER besten Quelle für die Gefahr,
      inkl. ALLER ihrer Perioden (verschiedene valid_from/valid_to bleiben getrennt →
      #1245); exakte Dubletten derselben Quelle (gleicher Zeitraum) → höchstes Level.
  Damit: (a) #1086 „nie doppelt" bleibt strikt erhalten — Cross-Source liefert nie
  zwei Karten, unabhängig davon ob die Quellen abweichende Zeiträume tragen (die
  echte Gefahr, dass geosphere_warn.py/meteoalarm.py reale, minut-abweichende
  Zeiträume setzen); (b) transitiv & reihenfolge-deterministisch (kein greedy-Merge
  über eine mutierende Liste → kein Verschlucken von Same-Source-Perioden, Adversary
  F003); (c) der #1245-Kernfall (eine Single-Source-Quelle wie Vigilance mit mehreren
  Perioden) bleibt vollständig, weil diese Quelle für ihre Gefahr die einzige und
  damit „beste" ist.

KERN — dedupe_official_alerts (official_alerts.py:280–298):
  Schlüssel bisher:   key = (ident, a.hazard)
  Schlüssel künftig:  key = (ident, a.hazard, a.valid_from, a.valid_to)
    ident = ("id",dedup_id) | ("region",region_label) | ("label",label)  [unverändert]
  → (valid_from, valid_to) EINHEITLICH in alle drei Namespaces (nicht nur region/label).
    Massiv-Sperren (dedup_id) tragen strukturell None/None (massif_closure.py:66–69),
    daher kein Verhaltensunterschied für sie — aber kein Sonderfall-Code und keine
    künftige "dedup_id-mit-Zeitraum"-Falle.
  Rest der Funktion unverändert: bei Schlüssel-Gleichstand gewinnt weiter der höchste
    level (`elif a.level > best[key].level`), Segment-ID-Union unverändert.

INVARIANTE — Trigger-Zustands-Key = Dedup-Identität:
  trip_alert.py:935,952 und compare_official_alert.py:161,179 bauen heute
    key = f"official_alert:{region_label}:{hazard}"
  → künftig muss der State-Key dieselbe Identität wie die Dedup tragen, d.h. die
    diskriminierenden Felder (ident inkl. dedup_id, hazard, valid_from, valid_to)
    aufnehmen, z.B. f"official_alert:{ident}:{hazard}:{valid_from_iso}:{valid_to_iso}".
  Ohne das kollidieren zwei getrennte Perioden im Zustand (last-write-wins) →
    verschluckte Eskalation oder Flapping.

SICHTBARKEIT — kompakte Renderer:
  render_official_alerts_html (Badge) und render_official_alerts_plain hängen bei
    vorhandenem Zeitraum (valid_from UND valid_to nicht None) einen kompakten
    Zeitraum-Zusatz an (Badge: "· {kompakt}", Plain: " ({kompakt})"). Ohne Zeitraum
    KEIN Zusatz und kein "unbekannt"-Platzhalter (Non-Regression zeitloser Warnungen).
```

## Expected Behavior

- **Input:** Liste amtlicher Warnungen (evtl. mehrere Perioden gleicher Region+Gefahr).
- **Output:** Entdoppelte Liste, in der Warnungen mit unterschiedlichem `(valid_from, valid_to)` als getrennte Einträge erhalten bleiben; echte Dubletten/Eskalationen am selben Zeitraum kollabieren weiter zum höchsten Level.
- **Side effects:** Alarm-Trigger speichern/vergleichen pro Periode getrennt; kompakte Mail-Renderer zeigen je Periode einen unterscheidbaren Zeitraum.

## Acceptance Criteria

- **AC-1:** Given zwei amtliche Warnungen mit identischer Region und Gefahr, gleicher Stufe, aber unterschiedlichen Gültigkeitszeiträumen (Vigilance Hitze Stufe 3: Mo 04:00–22:00 UTC und Mo 22:00–Di 22:00 UTC) / When sie `dedupe_official_alerts` durchlaufen / Then bleiben ZWEI getrennte Einträge mit ihren jeweiligen `valid_from`/`valid_to` erhalten, keiner verschwindet.
  - Test: `dedupe_official_alerts` mit beiden Alerts aufrufen → Ergebnis-Länge 2, beide Zeiträume im Ergebnis vorhanden.

- **AC-2:** Given zwei Warnungen mit identischer Identität, Gefahr UND identischem Zeitraum, aber unterschiedlicher Stufe (Level 3 und Level 4) / When sie `dedupe_official_alerts` durchlaufen / Then kollabieren sie zu EINEM Eintrag mit der höchsten Stufe (4) — echte Eskalation am selben Zeitraum, bestehende Semantik.
  - Test: `dedupe_official_alerts` → Länge 1, `level == 4`.

- **AC-3:** Given zwei Massiv-Sperren mit gleicher `dedup_id`, `region_label=None`, ohne Zeitraum (`valid_from`/`valid_to = None`), Stufe 3 und Stufe 4 / When sie `dedupe_official_alerts` durchlaufen / Then kollabieren sie weiterhin zu EINEM Eintrag Stufe 4 (Massiv-Eskalations-Non-Regression #1172/#1200/#1217/#1218).
  - Test: mit produktionsrealer Fixture (`_massif_alert`-Form: region_label=None, dedup_id konstant, None/None) → Länge 1, `level == 4`.

- **AC-4:** Given der Trip-Alarm-Trigger hat eine Warn-Periode A (Region R, Gefahr H, Zeitraum T1) bereits mit Stufe X im Zustand gespeichert / When eine echte neue Periode B (Region R, Gefahr H, Zeitraum T2 ≠ T1) im nächsten Lauf auftritt / Then wird B als neuer Alarm erkannt und unter einem eigenen Zustands-Key gespeichert, ohne A zu überschreiben.
  - Test: Trigger-Lauf mit A, dann Lauf mit A+B → B löst Alarm aus, Zustand enthält beide Perioden getrennt.

- **AC-5:** Given zwei VERSCHIEDENE Massiv-Sperren (unterschiedliche `dedup_id`, beide `region_label=None`, Gefahr `access_ban`) treffen denselben Trigger-Lauf / When der Trigger den Zustand schreibt / Then erhalten beide getrennte Zustands-Keys (keine gegenseitige Überschreibung durch den heute kollidierenden `official_alert:None:access_ban`-Key).
  - Test: Trigger mit zwei Massiven unterschiedlicher `dedup_id` → Zustand enthält zwei Einträge; eine spätere Eskalation eines der beiden wird korrekt erkannt.

- **AC-6:** Given zwei Perioden gleicher Region+Gefahr+Stufe mit unterschiedlichen Zeiträumen erreichen die kompakten Renderer (`render_official_alerts_html` Badge, `render_official_alerts_plain`) / When die Mail gerendert wird / Then unterscheiden sich die beiden erzeugten Badges/Zeilen durch einen kompakten Zeitraum-Zusatz (keine zwei textidentischen Ausgaben).
  - Test: `render_official_alerts_html`/`render_official_alerts_plain` mit 2-Perioden-Fixture → die zwei Ausgabe-Fragmente sind verschieden und enthalten je ihren Zeitraum.

- **AC-7:** Given eine Warnung ohne Zeitraum (`valid_from`/`valid_to = None`, z.B. Waldbrand oder Massiv) / When ein kompakter Renderer sie ausgibt / Then erscheint KEIN Zeitraum-Zusatz und KEIN „unbekannt"-Platzhalter (zeitlose Warnungen bleiben unverändert).
  - Test: `render_official_alerts_html`/`_plain` mit None/None-Alert → Ausgabe ohne Zeit-Suffix (byte-stabil zum bisherigen Verhalten).

## Known Limitations

- **Kein Interval-Merging (PO-Entscheidung 2026-07-15):** Aneinander anschließende oder überlappende Perioden werden NICHT zu einem Gesamtzeitraum verschmolzen — sie bleiben getrennte Einträge/Karten. Bewusst gewählt (einfacher, robuster; „nichts verschwindet still" ist erfüllt).
- `_bundle_by_hazard_level` bündelt weiterhin nur bei identischem `(hazard, level, label, valid_from, valid_to)`; zwei Perioden mit verschiedenem Zeitraum werden dort nicht zusammengefasst — konsistent mit „getrennt zeigen".
- Badge-/Kurzlisten-Zeitraum ist ein **kompaktes** Format (Wochentag + Stunden, ggf. Tagesübergang), keine volle Datums-/Jahresangabe; die ausführliche „Gültig:"-Zeile bleibt der Standalone-Alarm-Notice vorbehalten.
- Der wiederholte Ausbau des Dedup-Schlüssels (label → region_label → dedup_id → Zeitraum) legt langfristig eine ADR zur „stabilen Identität einer amtlichen Warnung" nahe; für diesen Fix nicht erforderlich.
- **Cross-Source-Verlust (PO-akzeptiert 2026-07-15, „nie doppelt"):** Melden ZWEI Quellen mit überlappender geografischer Abdeckung für **denselben `hazard`-String** an derselben Koordinate, und eine Quelle meldet eine Periode, die die andere nicht kennt, so kann diese exklusive Periode der NICHT-besten Quelle wegfallen (die Partitionierung behält nur die höherstufige Quelle). Bewusst gewählt gegenüber „nie eine Warnung verschlucken" (die dafür gelegentlich zwei fast identische Warnungen zeigt).
  - **Umfang (F004-Korrektur):** Die Partitionierung ist **länder-agnostisch** — sie gruppiert rein nach `hazard`-String über alle Quellen. Dominanter realer Fall ist AT/IT (GeoSphere + MeteoAlarm decken dieselben Punkte ab). **Strukturell** aber nicht darauf begrenzt: `VigilanceSource.covers()` teilt die übergroße AROME-FR-Bounding-Box (bis ~10°E, reicht nach Westösterreich/Norditalien) und geteilte `hazard`-Strings (`wind_gust`/`thunderstorm`/`extreme_heat` mit GeoSphere/MeteoAlarm; `wildfire_risk` zwischen `meteo_forets` und `meteoalarm`) — d.h. in Grenzregionen kann der Effekt auch FR-Quellen betreffen. Ob das mit Live-Daten real feuert, ist nicht abschließend bestätigt; die Möglichkeit ist strukturell gegeben. Single-Source-Punkte (nur eine zuständige Quelle je Gefahr) sind nie betroffen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Inkrementelle Erweiterung eines bestehenden Dedup-Schlüssels plus Kopplung des Alarm-Zustands-Keys an dieselbe Dedup-Identität — keine neue Architektur, kein neues Modul, keine geänderte Schnittstelle. Bewegt sich innerhalb des etablierten Zwei-Stufen-Verdichtungsmusters (#1172/#1239).

## Changelog

- 2026-07-15: Initial spec created (Issue #1245); Semantik „getrennt statt merge" + Sichtbarkeit-Zusatz per PO-go; Scope um Trigger-State-Key erweitert nach analysis-challenger (Blocker B1/B2, Massiv-State-Kollision kohärent mitbehoben).
- 2026-07-15: Faktenkorrektur nach Implementierung — primärer Verlustort im Trigger-/Ein-Ort-Fluss ist `base.py` (`get_official_alerts_for_location`, Cross-Source-Kollaps vor dedupe), nicht dedupe allein. Trigger-State-Key über neuen Helper `official_alert_state_key()`. Bestehender Test `test_issue_1088...TestAC6Dedupe` (Fixture an altes State-Key-Literal gekoppelt) auf echte Produktionslogik repariert.
- 2026-07-15: Adversary Runde 3 (BROKEN) — der erste `(hazard, valid_from, valid_to)`-Schlüssel bricht #1086 (AT-Quellen tragen ECHTE, minut-abweichende Zeiträume, nicht None/None); der greedy-Merge-Nachbesserungsversuch war nicht-transitiv und verschluckte Same-Source-Perioden (F003). **PO-Entscheidung „nie doppelt"** → base.py auf **Quellen-Partitionierung** umgestellt (beste Quelle je Gefahr behält alle Perioden). Neue Known Limitation: exklusive Periode einer nicht-besten AT-Quelle kann wegfallen (PO-akzeptiert).
