---
entity_id: fix_2263_lpi_leiter_nach_liefernder_quelle
type: module
created: 2026-09-09
updated: 2026-09-09
status: draft
version: "1.0"
tags: [gewitter, thunder, lpi, fallback, vertretung, alarm]
---

# fix_2263_lpi_leiter_nach_liefernder_quelle

## Approval

- [ ] Approved

## Purpose

Die Blitzpotenzial-Schwellenleiter (LPI) wird künftig nach der **liefernden Quelle** geschlüsselt
statt rein geografisch nach dem Gebiet. Springt bei Ausfall der Primärquelle eine Vertretung ein
(ADR-0047), wird deren Wert damit gegen die für ihre Größe kalibrierte Leiter bewertet statt gegen
die Leiter des ursprünglichen Gebiets — heute verpufft das Signal für FR (Korsika) ganz und wird
für DE_ALPEN fehlerhaft überhöht.

## Source

- **File:** `src/providers/thunder_enrichment.py:279-304` (`_schwellen_fuer_reihe`)
- **Identifier:** `_schwellen_fuer_reihe` (Schicht: Python-Core, `src/providers/`, `src/app/`)

## Estimated Scope

- **LoC:** ~70–110
- **Files:** 4 (2 Code, 1 Test neu, 1 ADR neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/providers/thunder_routing.py` (`_REGIONS`, `_VERTRETUNG`) | Upstream | Liefert Gebietszuordnung und Vertretungstabelle (`fr_direct → eu_direct`, `de_direct → eu_direct`) |
| `src/app/model_registry.py` (`LPI_THRESHOLDS_JKG`, `lpi_thresholds_jkg()`) | Upstream | Bestehende Kalibrierungs-Leitern je Schlüssel (`DE_ALPEN`, `EU_REST`) — Werte und Signatur bleiben unverändert |
| `src/providers/dwd_eu.py` (`lpi_con_max → lpi`) | Upstream | Ersatzquelle liefert die Größe, für die `EU_REST` kalibriert ist |
| `ForecastMeta.fallback_metrics` | Upstream | Erkennungsmerkmal der Vertretung (Feldnamen, kein Providername) |
| `dp.thunder_level` (`src/output/metric_format.py`, Fusion) | Downstream | Speist alle vier Ausgabekanäle und alle Alarme (#1701) |

## Implementation Details

```
_schwellen_fuer_reihe(reihe):
    region = thunder_region_for(reihe.lat, reihe.lon)          # unverändert
    cape_schwellen = cape_thresholds(region, effective_cape_model_id(reihe.meta))  # unverändert

    primaerquelle = <Provider-ID der Reihe, z.B. "fr_direct" | "de_direct" | "eu_direct">
    if "lightning_potential_lpi_jkg" in (reihe.meta.fallback_metrics or ()):
        liefernde_quelle = thunder_vertretung_for(primaerquelle)   # z.B. "eu_direct"
    else:
        liefernde_quelle = primaerquelle

    lpi_schluessel = {
        "de_direct": "DE_ALPEN",
        "eu_direct": "EU_REST",
        "fr_direct": None,
    }[liefernde_quelle]

    lpi_schwellen = lpi_thresholds_jkg(lpi_schluessel) if lpi_schluessel else None
    # lpi_thresholds_jkg() selbst bleibt unverändert (Signatur + LPI_THRESHOLDS_JKG-Inhalt)
```

Die Übersetzungstabelle „liefernde Quelle → Kalibrierungs-Schlüssel" ist die einzige neue
Datenstruktur. `LPI_THRESHOLDS_JKG` bleibt der einzige Wertespeicher — keine Sprossen werden
kopiert oder neu kalibriert.

`reihe.meta.fallback_model` darf für die Leiterwahl **ausdrücklich nicht** herangezogen werden:
Das Feld kann zugleich vom Grundvorhersage-Fallback mit einer anderen Modell-Kennung belegt sein
(ADR-0047 Known Limitations Punkt 3) und trägt beim Gewitter-Fallback ohnehin nur den
Providernamen, keine normalisierte Modell-ID. Die Erkennung erfolgt ausschließlich über
`fallback_metrics`.

## Expected Behavior

- **Input:** Eine Zeitreihe (`reihe`) mit Ortskoordinate, Primärquelle und ggf. gesetztem
  `reihe.meta.fallback_metrics` (bei aktiver Vertretung).
- **Output:** Die für `_schwellen_fuer_reihe` gewählte LPI-Leiter entspricht der Kalibrierung der
  **tatsächlich liefernden** Quelle, nicht dem geografischen Gebiet der Koordinate.
- **Side effects:** Keine. `LPI_THRESHOLDS_JKG` und `lpi_thresholds_jkg()` bleiben inhaltlich und
  in der Signatur unverändert; `lpi_thresholds_jkg("FR") is None` bleibt wahr.

## Acceptance Criteria

- **AC-1:** Given eine Korsika-Koordinate (≈42,2 N / 9,1 O), bei der `fr_direct` mit einer eingespeisten `ThunderSourceUnavailableError` ausfällt und die Vertretung `eu_direct` daraufhin 60 J/kg Blitzpotenzial liefert / When `enrich_thunder` end-to-end durchläuft / Then ist `dp.thunder_level` MED (EU_REST-Leiter 7,14/23,81/86,16) — heute entsteht aus diesem Signal gar keine Stufe.
  - Test: Ruft `enrich_thunder` mit eingespeister `ThunderSourceUnavailableError` für `fr_direct` und einem `eu_direct`-Ersatzwert von 60 J/kg auf und prüft das resultierende `dp.thunder_level` auf MED, nicht durch isolierten Aufruf von `lpi_thresholds_jkg()` mit literal übergebenen Schwellen.

- **AC-2:** Given eine Alpen-Koordinate, bei der `de_direct` mit einer eingespeisten `ThunderSourceUnavailableError` ausfällt und die Vertretung `eu_direct` 60 J/kg Blitzpotenzial liefert / When `enrich_thunder` end-to-end durchläuft / Then ist `dp.thunder_level` MED — heute liefert dieselbe Situation fälschlich HIGH, weil der ICON-EU-Wert gegen die für ICON-D2 kalibrierte Leiter (1,0/30,0/50,0) bewertet wird.
  - Test: Ruft `enrich_thunder` mit eingespeister `ThunderSourceUnavailableError` für `de_direct` und einem `eu_direct`-Ersatzwert von 60 J/kg auf und prüft `dp.thunder_level` auf MED statt der heutigen Fehleskalation auf HIGH.

- **AC-3:** Given eine Alpen-Koordinate, bei der `de_direct` als Primärquelle selbst 60 J/kg Blitzpotenzial liefert (kein Ausfall) / When `enrich_thunder` end-to-end durchläuft / Then bleibt `dp.thunder_level` HIGH (DE_ALPEN-Leiter unverändert für die Primärquelle).
  - Test: Ruft `enrich_thunder` ohne eingespeisten Ausfall mit `de_direct`-Wert 60 J/kg auf und prüft `dp.thunder_level` auf HIGH, um Regression auf dem unveränderten Primärpfad auszuschließen.

- **AC-4:** Given eine Koordinate, bei der `eu_direct` als reguläre Primärquelle (kein Vertretungsfall) 60 J/kg Blitzpotenzial liefert / When `enrich_thunder` end-to-end durchläuft / Then ist `dp.thunder_level` MED über die EU_REST-Leiter.
  - Test: Ruft `enrich_thunder` ohne eingespeisten Ausfall mit `eu_direct`-Wert 60 J/kg auf und prüft `dp.thunder_level` auf MED, um den unveränderten Primärpfad für EU_REST zu bewachen.

- **AC-5:** Given eine Korsika-Koordinate, bei der `fr_direct` als reguläre Primärquelle (kein Ausfall) Blitzdichte statt Blitzpotenzial liefert / When `enrich_thunder` end-to-end durchläuft / Then entsteht kein Blitzpotenzial-Signal und `lpi_thresholds_jkg("FR")` bleibt `None`.
  - Test: Ruft `enrich_thunder` ohne eingespeisten Ausfall mit regulärer `fr_direct`-Blitzdichte auf und prüft sowohl, dass kein Blitzpotenzial-Signal in die Fusion einfließt, als auch direkt `lpi_thresholds_jkg("FR") is None` — dies ist die Zusicherung, die eine quellenbezogene Umschreibung am ehesten still bricht, und kein bestehender Test bewacht den Draht dorthin.

- **AC-6:** Given die Gewitter-Vertretung ist aktiv (`lightning_potential_lpi_jkg` steht in `fallback_metrics`) UND `fallback_model`/`fallback_reason` sind zugleich vom Grundvorhersage-Fallback mit einer ANDEREN Modell-Kennung belegt / When `eu_direct` 60 J/kg Blitzpotenzial liefert / Then ist `dp.thunder_level` weiterhin MED — die Leiterwahl hängt an `fallback_metrics`, nicht an `fallback_model`.
  - Test: Der Vertretungsfall wird mit zusätzlich besetztem Grundvorhersage-Fallback (andere Modell-Kennung in `fallback_model`/`fallback_reason`) durchlaufen; eine Implementierung, die `fallback_model` statt `fallback_metrics` liest, liefert hier eine andere Stufe und fällt durch.

## Known Limitations

- Der im Issue-Entwurf vorgesehene AC („`lpi_thresholds_jkg` liefert kein `None` ohne Spur") entfällt: `EU_REST` ist als Weltrechteck definiert, `thunder_region_for()` kann für reale Koordinaten nie `None` liefern — der Fall ist strukturell unerreichbar.
- Wer `reihe.meta` in `lpi_thresholds_jkg()` hineinfädelt statt den Fix in `_schwellen_fuer_reihe` zu halten, bricht drei bestehende Regressionswächter: `test_lpi_threshold_region_table.py:79,89-98,257-266` und `test_lpi_eu_rest_ladder.py:162-188`. Diese müssen grün bleiben.
- `fallback_model`/`fallback_reason` sind für die Leiterwahl **kein zulässiges Erkennungsmerkmal** — sie können gleichzeitig vom Grundvorhersage-Fallback belegt sein (ADR-0047 Known Limitations Punkt 3). Ein String-Vergleich auf `fallback_model == "eu_direct"` würde die fünf ursprünglichen ACs bestehen, aber an AC-6 scheitern.
- Wie häufig der Vertretungsfall real eintritt, ist offen (Priorisierungs-Eingabewert, kein Grund gegen den Fix).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0065 (neu, wird in Phase 5 geschrieben)
- **Rationale:** Der Fix stellt ADR-0047 §5 her und löst es nicht ab, ändert aber die in
  `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` festgelegte Schlüsselung der
  LPI-Leiter (Gebiet → liefernde Quelle). ADR-0065 muss diese Spec **ausschließlich in der
  Schlüsselungs-Frage** ausdrücklich als abgelöst benennen; ihre Werte und die FR-Aussparung
  bleiben gültig. Muster: ADR-0058 zu ADR-0018.

## Changelog

- 2026-09-09: Initial spec created
