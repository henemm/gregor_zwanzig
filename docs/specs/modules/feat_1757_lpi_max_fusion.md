---
entity_id: feat_1757_lpi_max_fusion
type: feature
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [gewitter, lpi, thunder-fusion, issue-1757, epic-1419]
---

# Blitzpotenzial-Fusion bevorzugt das Stundenmaximum `lpi_max` statt des Momentanwerts `lpi` (Issue #1757, Variante A mit Messauflage)

## Approval

- [x] Approved (PO Henning, 2026-08-19)

## Purpose

Die Gewitter-Fusion (`_fuse_thunder_levels()`) bezieht das Blitzpotenzial heute ausschließlich
aus dem DWD-Momentanwert `lightning_potential_lpi_jkg`. Ein Backtest vom 2026-08-11 zeigt eine
sehr niedrige Trefferquote (1 von 18 echten Gewitterstunden erkannt, Recall 5,6 %) — der
Momentanwert am Stundenrand verfehlt Gewitter systematisch. Seit Issue #1531 wird zusätzlich
`lightning_potential_max_lpi_jkg` (das DWD-Stundenmaximum, ICON-D2/DE_ALPEN) abgerufen, aber
nie gelesen. Diese Scheibe stellt die Fusion auf das Stundenmaximum um — bevorzugt, mit dem
Momentanwert als Rückfall dort, wo kein Stundenmaximum vorliegt — und macht die damit
verbundene Empfindlichkeitssteigerung vor der Auslieferung an echten Orten des Karnischen
Höhenwegs messbar, statt sie unbeobachtet in Produktion zu schicken.

## Source

- **File:** `src/providers/thunder_enrichment.py`
- **Identifier:** `_fuse_thunder_levels()` (Zeilen 100-156, konkret die Wertauswahl in Zeile
  145-146)

**Schicht:** ausschließlich Python-Core (`src/providers/`). Kein Go, kein Frontend — LPI ist
keine wählbare Metrik (Issue #710), diese Scheibe ändert nur die interne Werteauswahl vor der
Fusion, keine Bedienoberfläche.

## Estimated Scope

- **LoC:** ~10-15 Quellcode (eine neue kleine Auswahlfunktion oder ein Inline-Ausdruck in
  `_fuse_thunder_levels()`) + ~40-60 Tests (neue Fälle für Vorrang/Null-als-Messwert/Rückfall/
  Fehlen-beide, Anpassung des Invarianz-Wächters) ≈ **50-75 gesamt**, deutlich unter dem
  250-LoC-Workflow-Limit.
- **Files:** 1 geändert (Quellcode), 4 Testdateien angepasst (0 neu, 0 gelöscht), 2 Doku-Dateien
  nachgezogen (`docs/features/gewitter-gesamtkonzept.md`,
  `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md`).
- **Effort:** low — eine lokale Werteauswahl vor einem bereits bestehenden Aufruf, keine neue
  Infrastruktur, keine Signaturänderung an `thunder_level_from_signals()`. Der Aufwand liegt
  überwiegend in der Messauflage (AC-7), nicht im Code.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `docs/context/feat-1757-lpi-max-fusion.md` | Analyse dieser Phase | Vollständige Faktenlage, Risiken, Messzahlen; Grundlage dieser Spec |
| `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` | wird PRÄZISIERT | Legt die gebietsabhängige Schwellenleiter `LPI_THRESHOLDS_JKG` fest, die diese Scheibe unverändert übernimmt; Zeile 345-350 bindet 1/30/50 an den Momentanwert — wird in dieser Scheibe nachgezogen (AC-8) |
| `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md` | Vorgänger-Scheibe | Basis-Spec der LPI-Fusion; hält den Momentan-/Stundenmax-Bruch bereits als bekannte Grenze fest |
| `docs/features/gewitter-gesamtkonzept.md` §11 Rang 3 | bindender Rahmen, wird nachgezogen | Hält fest, dass ein Wechsel auf `lpi_max` „kein offener Arbeitsauftrag mehr" sei — bezog sich auf ein anderes Ziel (Gebietsbruch, inzwischen durch #1679 gelöst); diese Scheibe verfolgt das neue Ziel Trefferquote und muss die Zeile entsprechend präzisieren (AC-8) |
| `src/providers/dwd_eu.py:114` | Upstream, unverändert genutzt | Bildet ICON-EUs `lpi_con_max` bereits auf den Signalnamen `lpi` ab — Grund, warum der Rückfall auf `lightning_potential_lpi_jkg` außerhalb DE_ALPEN weiterhin ein Stundenmaximum liefert, kein Statistikbruch |
| `src/app/model_registry.py` `LPI_THRESHOLDS_JKG` | unverändert genutzt | Die Schwellenleiter, gegen die der fusionierte Wert gemessen wird — bleibt in dieser Scheibe unangetastet |
| Issue #1468 (Peer-Session) | Nachbar-Ticket, NICHT Teil dieser Scheibe | Onset-Verschiebungs-Alarm liest `dp.thunder_level`/`thunder_onset_utc`, die aus dieser Fusion entstehen; `src/app/models.py` ist von dieser Session gesperrt |

## Implementation Details

### Werteauswahl in `_fuse_thunder_levels()` (`src/providers/thunder_enrichment.py`)

Heute wird ausschließlich der Momentanwert in die Fusion gereicht (Zeile 145-146):

```python
werte = (dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg,
         dp.lightning_potential_lpi_jkg)
```

Neu: eine kleine, lokale Auswahl VOR dem Zusammenbau von `werte`, die das Stundenmaximum
bevorzugt und nur bei dessen Fehlen auf den Momentanwert zurückfällt. Die Prüfung erfolgt
ausdrücklich mit `is not None` — NICHT mit `or`, weil `0.0` (kein Blitzpotenzial) ein gültiger
Messwert und in Python unwahr ist:

```python
lpi_wert = (
    dp.lightning_potential_max_lpi_jkg
    if dp.lightning_potential_max_lpi_jkg is not None
    else dp.lightning_potential_lpi_jkg
)
werte = (dp.thunder_level, dp.lightning_density_per_km2_3h, dp.cape_jkg, lpi_wert)
```

`thunder_level_from_signals()` und `thunder_signal_carriers()` (`src/output/metric_format.py`)
bekommen weiterhin GENAU EINEN Blitzpotenzial-Wert an derselben Positionsstelle wie bisher —
keine Signaturänderung, kein neuer Parameter, kein zweites LPI-Feld an der Fusionsgrenze. Die
Herkunftsangabe `dp.thunder_level_signals` nennt das Signal unverändert `"blitzpotenzial"`
(`src/app/thunder_scale.py:103`), egal welche der beiden Quellzahlen tatsächlich eingeflossen
ist — die Fusion bleibt statistik-blind (Kontext-Dokument, Existing Patterns).

`LPI_THRESHOLDS_JKG` (`src/app/model_registry.py`) und `lpi_thresholds_jkg()` bleiben
unverändert — dieselbe Leiter (1/30/50 DE_ALPEN, 5/20/50 EU_REST) wird jetzt nur gegen eine
andere Statistik gemessen.

### Doku-Nachzug (AC-8)

- `docs/features/gewitter-gesamtkonzept.md` §11 Rang 3: die Zeile „kein offener Arbeitsauftrag
  mehr" wird um einen Verweis auf #1757 ergänzt — der Gebietsbruch-Einwand bleibt korrekt
  historisch dokumentiert, das NEUE Ziel (Trefferquote) bekommt eine eigene, aktuelle Zeile.
- `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` Known Limitations
  („Momentanwert-vs-60-Minuten-Maximum-Unterschied bleibt bestehen"): wird um einen Verweis
  ergänzt, dass die Fusion seit #1757 das Stundenmaximum bevorzugt, wo verfügbar — die dort
  beschriebene Kalibrierungsfrage (AC-8-Nachbarschaft, s. u. Known Limitations dieser Spec)
  bleibt bestehen und wird NICHT stillschweigend als gelöst dargestellt.

## Expected Behavior

- **Input:** ein Datenpunkt mit `lightning_potential_max_lpi_jkg` (Stundenmaximum,
  ICON-D2/DE_ALPEN) und/oder `lightning_potential_lpi_jkg` (Momentanwert, alle Gebiete; bei
  ICON-EU bereits ein 60-Minuten-Maximum unter anderem Signalnamen, s. `dwd_eu.py:114`).
- **Output:** die Fusion erhält GENAU EINEN LPI-Wert — das Stundenmaximum, wenn vorhanden
  (inklusive `0.0`), sonst den Momentanwert, sonst gar keinen. `dp.thunder_level` und
  `dp.thunder_level_signals` verhalten sich ab diesem Wert exakt wie bisher (unveränderte
  Leiter, unveränderte Herkunftsbeschriftung `"blitzpotenzial"`).
- **Side effects:** keine neuen Abrufe, keine neuen Felder, keine Signaturänderung an
  öffentlichen Funktionen — reine Werteauswahl vor einem bereits bestehenden Aufruf.

## Acceptance Criteria

- **AC-1:** Given ein Datenpunkt, an dem sowohl `lightning_potential_max_lpi_jkg` (z. B. 40.0
  J/kg) als auch `lightning_potential_lpi_jkg` (z. B. 12.0 J/kg) vorliegen / When
  `_fuse_thunder_levels()` die Fusion aufruft / Then wird `lightning_potential_max_lpi_jkg` in
  die Schwellenleiter gereicht, nicht der Momentanwert — die resultierende Stufe entspricht
  40.0 J/kg, nicht 12.0 J/kg.
  - Test: DE_ALPEN-Schwellen (1/30/50), Datenpunkt mit beiden Feldern gesetzt, erwartete Stufe
    MED (40.0 liegt zwischen 30 und 50), nicht LOW (12.0 läge zwischen 1 und 30).

- **AC-2:** Given ein Datenpunkt, an dem `lightning_potential_max_lpi_jkg` exakt `0.0` und
  `lightning_potential_lpi_jkg` z. B. `200.0` beträgt / When die Fusion aufgerufen wird / Then
  wird `0.0` verwendet, nicht der Momentanwert 200.0 — Null ist ein gültiger Messwert
  („kein Blitzpotenzial in dieser Stunde"), kein Fehlen.
  - Test: erwartete Stufe NONE (0.0 unterschreitet jede Schwelle), NICHT die Stufe, die 200.0
    ergäbe.
  - Gegenprobe (Mutationsprobe PFLICHT): Würde die Auswahl mit `dp.lightning_potential_max_lpi_jkg
    or dp.lightning_potential_lpi_jkg` statt mit einer expliziten `is not None`-Prüfung
    implementiert, würde `0.0` als unwahr gewertet und der Test fiele fälschlich auf 200.0
    zurück — der Test muss diese Mutation fangen.

- **AC-3:** Given ein Datenpunkt, an dem `lightning_potential_max_lpi_jkg` `None` ist und
  `lightning_potential_lpi_jkg` einen Wert trägt (z. B. 8.0 J/kg, EU_REST-typischer Fall, da
  ICON-EU dieses Feld nicht befüllt) / When die Fusion aufgerufen wird / Then wird der
  Momentanwert 8.0 verwendet — der Rückfall hält das Blitzpotenzial-Signal außerhalb DE_ALPEN
  unverändert wirksam.
  - Test: EU_REST-Schwellen (5/20/50), `lightning_potential_max_lpi_jkg=None`,
    `lightning_potential_lpi_jkg=8.0`, erwartete Stufe LOW — identisch zum Verhalten vor dieser
    Änderung.

- **AC-4:** Given ein Datenpunkt, an dem BEIDE Felder `None` sind / When die Fusion aufgerufen
  wird / Then trägt das Blitzpotenzial-Signal nichts zur Stufe bei — unverändertes
  Bestandsverhalten, „keine Aussage" erzeugt keinen Eintrag mit Stufe NONE in
  `dp.thunder_level_signals`.
  - Test: beide Felder `None`, alle übrigen Signale ebenfalls `None`, Fusion liefert `None`
    (keine Stufe), `dp.thunder_level_signals` enthält keinen `"blitzpotenzial"`-Eintrag.

- **AC-5:** Given ein Datenpunkt mit gesetztem `lightning_potential_max_lpi_jkg` / When die
  Fusion ein Ergebnis liefert und `dp.thunder_level_signals` befüllt / Then nennt der Eintrag
  weiterhin den Signalnamen `"blitzpotenzial"` (`src/app/thunder_scale.py:103`) — es entsteht
  KEIN neuer Signalname und keine neue Beschriftung, unabhängig davon, welche der beiden
  Quellzahlen eingeflossen ist.
  - Test: `dp.thunder_level_signals` nach der Fusion enthält den Schlüssel `"blitzpotenzial"`
    (nicht z. B. `"blitzpotenzial_max"`), Beschriftungstabelle in `thunder_scale.py` bleibt
    unverändert.

- **AC-6:** Given die öffentliche Fusionsgrenze `thunder_level_from_signals()` bzw.
  `thunder_signal_carriers()` / When diese Scheibe umgesetzt ist / Then nehmen beide Funktionen
  weiterhin GENAU EINEN Blitzpotenzial-Wert an derselben Positionsstelle entgegen — keine
  Signaturänderung, kein zweiter LPI-Parameter.
  - Test: Funktionssignatur-Prüfung (Parameteranzahl/-namen unverändert gegenüber dem Stand vor
    dieser Änderung) sowie ein bestehender Aufruf mit dem alten Argumentmuster läuft unverändert
    durch.

- **AC-7:** Given die fertige Implementierung (AC-1 bis AC-6 grün) VOR der Auslieferung nach
  Produktion / When an echten Orten des Karnischen Höhenwegs gemessen wird, in wie vielen
  Stunden sich die fusionierte Gewitterstufe gegenüber dem Bestand (reiner Momentanwert)
  ändert, aufgeschlüsselt nach Zielstufe (leicht/mittel/schwer) / Then wird das Ergebnis am
  Issue #1757 dokumentiert, BEVOR der Prod-Deploy-Schritt ausgeführt wird — die Messauflage ist
  Teil des Liefer-Workflows dieser Scheibe, kein optionaler Nachtrag.
  - Test: kein automatisierter Testfall (Messauflage, keine Code-Zusicherung) — Nachweis ist ein
    dokumentierter Issue-Kommentar mit den Stundenzahlen je Zielstufe für die KHW-Orte, vor dem
    `deploy-gregor-prod.sh`-Lauf dieser Scheibe erstellt.

- **AC-8:** Given die dokumentierte Aussage in `docs/features/gewitter-gesamtkonzept.md` §11
  Rang 3 („kein offener Arbeitsauftrag mehr") und die Momentanwert-Bindung in
  `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md` / When diese Scheibe
  umgesetzt ist / Then sind beide Dokumente nachgezogen — §11 verweist auf #1757 als das neue,
  andere Ziel (Trefferquote statt Gebietsbruch), `feat_1679` Known Limitations verweist auf die
  Umstellung. Eine dokumentierte Entscheidung wird nicht still rückgängig gemacht.
  - Test: `# doc-compliance-test` — Dateiinhalt-Prüfung, dass beide Dokumente den Verweis auf
    #1757 tragen (Ausnahme vom Verbot des Dateiinhalt-Checks, weil hier die Dokumentation selbst
    der Prüfling ist, nicht Ersatz für einen Verhaltensnachweis).

- **AC-9:** Given der Invarianz-Wächter `tests/tdd/test_thunder_output_invariance_new_signals.py`,
  der bisher ausdrücklich sichert, dass `lightning_potential_max_lpi_jkg` NICHT ausgabewirksam
  ist / When diese Scheibe umgesetzt ist / Then ist der Wächter mit Begründung angepasst, nicht
  gelöscht — die neue Erwartung ist „ausgabewirksam, wenn gesetzt (bevorzugt vor dem
  Momentanwert)" und referenziert im Testkommentar Issue #1757 sowie den PO-Entscheid für
  Variante A vom 2026-08-19.
  - Test: der angepasste Wächter prüft aktiv, dass ein gesetztes
    `lightning_potential_max_lpi_jkg` die Stufe gegenüber einem abweichenden Momentanwert
    verändert (ehemals: prüfte das Gegenteil) — Testname und Docstring nennen den
    Politikwechsel ausdrücklich, damit ein späterer Leser nicht auf einen Wackelkontakt schließt.

## Known Limitations

- **Empfindlichkeit steigt messbar, am oberen Ende am stärksten.** Aus der bereits gemessenen
  Tabelle in `docs/features/gewitter-gesamtkonzept.md` §4.3 folgt für ICON-D2 ein Faktor, um
  den ein Schwellenwert nach der Umstellung häufiger überschritten wird: ≈4,6× bei der
  Schwelle ≥5, ≈5,1× bei ≥20, ≈6,6× bei ≥50. Die Schwellenleiter bleibt unverändert (PO-Vorgabe)
  ⇒ die Stufe „schwer" wird rund 6,6-mal so oft vergeben wie bisher. Das ist keine Nebenwirkung,
  sondern eine bewusst erkaufte Produktänderung — deshalb die Messauflage AC-7 vor Auslieferung.
- **Die Eichbasis der DE_ALPEN-Leiter (1/30/50) bezüglich Momentanwert vs. Stundenmaximum ist
  nicht belegt.** Der Kommentar in `model_registry.py` bindet die Schwellen an Bína et al. 2022
  / COSMO-D2, sagt aber nicht wörtlich, ob sich die publizierten Werte auf einen Momentanwert
  oder ein Stundenmaximum beziehen. Die bisherige Zuordnung „Momentanwert" stammt aus
  `feat_1679` und ist dort selbst nur mittelbar hergeleitet. Ein Primärzitat, das dies eindeutig
  ausweist, existiert im Repo nicht (geprüft, mit Positivkontrolle am auffindbaren
  Schröder-Zitat für EU_REST). Diese Spec trifft dazu KEINE Aussage in die eine oder andere
  Richtung — die Umstellung erfolgt trotz dieser offenen Frage, weil die gemessene Trefferquote
  (Recall 5,6 %) das dringlichere, belegte Problem ist.
- **Eine Nachkalibrierung der Leiter auf das Stundenmaximum ist mit den verfügbaren
  Datenquellen nicht machbar.** Open-Meteo liefert für ICON-D2 nur den Momentanwert, kein
  Stundenmaximum; `lpi_max` kommt ausschließlich von `opendata.dwd.de` ohne Langzeitarchiv.
  Eine eigene Eichung über eine Konvektionssaison scheidet damit aus — dieselbe Datenlücke, die
  bereits #1678 zur publizierten Interim-Leiter für EU_REST gezwungen hat.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Referenz auf **ADR-0025** (Gewitter-Fusionsregel: eine Stufe kann
  durch ein Signal nur angehoben, nie gesenkt werden; die Skala selbst wohnt in
  `output/metric_format.py`).
- **Rationale:** Diese Scheibe ändert nicht die Fusionsregel und nicht die Skala, sondern nur,
  welche der beiden bereits vorhandenen Rohgrößen als Blitzpotenzial-Eingabe in die bestehende
  Regel eingespeist wird. Es entsteht keine neue Architektur-Entscheidungsfläche — Variante B
  aus dem Kontext-Dokument (zwei Statistiken für unterschiedliche Sprossen derselben Leiter)
  wurde deshalb verworfen: sie hätte ADR-0025 widersprochen, weil eine Sprosse dann eine andere
  physikalische Größe als die übrigen Sprossen derselben Leiter träfe.

## Verworfene Alternativen

- **(i) Harter Wechsel ohne Rückfall auf `lpi`.** `lightning_potential_max_lpi_jkg` wird
  ausschließlich von ICON-D2 (DE_ALPEN) befüllt. Ohne Rückfall verlören alle übrigen Gebiete
  (EU_REST) das Blitzpotenzial-Signal ersatzlos — eine stille Regression außerhalb der Alpen.
  Verworfen.
- **(ii) `lpi_max` nur für die unterste Sprosse (Nachweisschwelle), obere Sprossen weiter auf
  `lpi`.** Physikalisch am ehesten verteidigbar (die unterste Sprosse ist eine reine
  Nachweisfrage „blitzt es überhaupt"), aber zwei Statistiken innerhalb derselben Leiter —
  widerspricht der Ein-Fusionsregel-Prämisse aus ADR-0025 und ist gegenüber Nutzenden schwer
  erklärbar. Verworfen.
- **(iii) Ticket als überholt schließen (§11 folgen).** §11 Rang 3 bezog sich auf ein anderes
  Ziel (Gebietsbruch, inzwischen durch #1679 gelöst) und trifft die im Backtest gemessene
  Trefferquote nicht. Ein Schließen ohne Umsetzung ließe das belegte Recall-Problem (5,6 %)
  ungelöst. Verworfen.

## Auswirkungen

- **Kopplung zu Issue #1468 (Peer-Session, Onset-Verschiebungs-Alarm).** `thunder_onset_utc`
  (erste Stunde mit `thunder_level >= LOW`) entsteht aus genau der Fusion, die diese Scheibe
  ändert. Die dortigen Alarm-Schwellen sind asymmetrisch (1 h früher meldet, 3 h später erst)
  — dieser Umbau verschiebt die Erkennung ausschließlich nach vorne, also in die scharfe
  Richtung. Nach dem ersten Lauf mit dieser Änderung können einmalig Beginn-Alarme entstehen,
  ohne dass sich das tatsächliche Wetter geändert hat. Der Onset-Anker selbst
  (`src/app/models.py`, `tests/tdd/test_onset_computation_sources.py`,
  `tests/tdd/test_onset_shift_alert.py`) wird von dieser Scheibe NICHT angefasst; sollte er
  einmalig neu gesetzt werden müssen, ist das ein eigener Auftrag an #1468.

## Scope-Abgrenzung

**Bewusst NICHT Teil dieser Scheibe:**

- Nachkalibrierung der Schwellenleiter `LPI_THRESHOLDS_JKG` (mit den verfügbaren Datenquellen
  nicht machbar, s. Known Limitations).
- `sdi_2` (Supercell-Index) und Hagel-Signale — unverändert, unberührt von dieser Änderung.
- Änderungen an `src/app/models.py` — die betroffenen Felder existieren bereits seit #1531; die
  Datei ist außerdem von der Peer-Session #1468 gesperrt.
- Der Onset-Anker (`thunder_onset_utc`) selbst — s. Auswirkungen, gehört zu #1468.

## Changelog

- 2026-08-19: Initial spec created (Issue #1757, Variante A mit Messauflage, PO-Entscheid
  2026-08-19).
