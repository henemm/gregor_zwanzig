# Context: feat-1757-lpi-max-fusion

Issue #1757 · erstellt 2026-08-11 (`[triage:po]`, Backtest-Session) · Teil von Epic #1419
Kontext-Phase 2026-08-19.

## Request Summary

Die Gewitter-Fusion soll das Blitzpotenzial nicht mehr aus dem Momentanwert `lpi` beziehen,
sondern aus dem Stundenmaximum `lpi_max` (seit #1531 abgerufen, aber nie gelesen) — mit `lpi`
als Rückfall. Ziel laut Issue: die gemessen sehr niedrige Trefferquote des LPI-Signals heben
(Backtest 2026-08-11: 1 von 18 echten Gewitterstunden erkannt, Recall 5,6 %).

## 🔴 Zentraler Konflikt — vor der Spec zu klären

Zwei Artefakte **desselben Tages** (2026-08-11) widersprechen sich:

| Quelle | Aussage |
|---|---|
| Issue #1757 (21:03 Uhr, PO-beauftragt) | „`lpi_max` fließt weiterhin nicht in die Fusion ein" — Arbeitsauftrag, Doku-Tabelle §11 trage den Fehler „Entscheidung ≠ Umsetzung" |
| `docs/features/gewitter-gesamtkonzept.md` §11, Rang 3 | Zeile durchgestrichen, Stand „🟡 **überholt** (2026-08-11) … ein nachträglicher Wechsel auf `lpi_max` liefe dort gegen die falsche Statistik. **Kein offener Arbeitsauftrag mehr**" |

Auflösung des Widerspruchs (Analyse dieser Phase): **beide haben in ihrem eigenen Bezugsrahmen
recht, weil sie von verschiedenen Zielen sprechen.**

- Rang 3 war ursprünglich als Mittel gegen den **Gebietsbruch** ICON-D2 ↔ ICON-EU gedacht.
  Dieses Ziel hat #1679 anders erreicht (gebietsabhängige Schwellentabellen). In DIESEM Sinn
  ist Rang 3 tatsächlich überholt — §11 ist insoweit korrekt.
- Issue #1757 verfolgt ein **anderes, neues Ziel**: die Trefferquote des Signals. Dazu sagt
  §11 nichts. Der dort genannte Einwand („falsche Statistik") bleibt aber gültig und trifft
  #1757 voll.

⇒ Das Ziel des Tickets ist legitim, das im Ticket vorgeschlagene Mittel ist so, wie es dort
steht, statistisch unsauber. Siehe „Entscheidungsbedarf".

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/thunder_enrichment.py:130-156` | `_fuse_thunder_levels()` — **der einzige Produktionsaufrufer** der Fusion; hier wird `dp.lightning_potential_lpi_jkg` hineingereicht. Der Umbau gehört hierhin. |
| `src/output/metric_format.py:382-434` | `_signal_levels()` — bildet das Blitzpotenzial auf die Leiter ab (Schlüssel `"blitzpotenzial"`). Kennt nur „eine Zahl", nicht deren Statistik. **Muss nicht geändert werden.** |
| `src/output/metric_format.py:437-545` | `thunder_signal_carriers()` / `thunder_level_from_signals()` — beide delegieren an `_signal_levels()`. |
| `src/app/model_registry.py:145-177` | `LPI_THRESHOLDS_JKG` — DE_ALPEN (1/30/50), EU_REST (7,14/23,81/86,16). Die Leiter, gegen die gemessen wird. |
| `src/providers/dwd_eu.py:114` | Bildet ICON-EUs `lpi_con_max` auf den Signalnamen `lpi` ab ⇒ landet in `lightning_potential_lpi_jkg`. **Ursache dafür, dass ein harter Wechsel EU_REST stumm schaltete.** |
| `src/providers/thunder_enrichment.py:46` | `"lpi_max" → "lightning_potential_max_lpi_jkg"` — nur ICON-D2/DE_ALPEN befüllt dieses Feld. |
| `src/app/models.py:160,175` | Beide Felder. Wird **nicht** angefasst (Sperre #1468). |
| `src/app/thunder_scale.py:103` | `THUNDER_SIGNAL_LABEL_DE["blitzpotenzial"]` — sichtbarer Name der Herkunft; bleibt unverändert. |

## Existing Patterns

- **Alles-oder-nichts je Signal** (`_signal_levels`): fehlt der Wert ODER eine Sprosse der
  Leiter, trägt das Signal gar nichts bei — kein stiller Rückfall auf eine Ersatzprüfung.
- **Kein stiller Rückfall** ist projektweite Linie (ADR-0025, PO-Korrektur 2026-08-08):
  Schwellen kommen keyword-only ohne Default herein.
- **Fusion = `max_thunder()`** über die vorhandenen Einzelsignale. Ein größerer LPI-Wert kann
  eine Stufe nur heben, nie senken.
- Die Fusion ist **statistik-blind**: sie bekommt eine Zahl und eine Leiter. Welche Statistik
  die Zahl trägt, entscheidet der Aufrufer. Das ist der Grund, warum der Umbau in
  `thunder_enrichment.py` gehört und nicht in `metric_format.py`.

## Dependencies

- **Upstream:** `providers/dwd.py` (ICON-D2, liefert `lpi` und `lpi_max`), `providers/dwd_eu.py`
  (ICON-EU, liefert `lpi_con_max` unter dem Namen `lpi`), `app/model_registry.lpi_thresholds_jkg()`,
  `providers/thunder_routing.thunder_region_for()`.
- **Downstream:** `dp.thunder_level` / `dp.thunder_level_signals` sitzen am Datenpunkt, wirken
  daher ohne weiteren Aufruf in **allen** Ausgabepfaden: `compact_summary.py:603`,
  `trip_report.py:651,691`, `email/outlook.py:539`, `email/compare_html.py:994,1005`,
  `email/helpers.py:1761`, `day_window.py:80`, `comparison.py:342`,
  `services/weather_metrics.py:438,616`. Also Trip-Briefing, Ortsvergleich, Ausblick, GLANCE,
  Telegram, SMS.

## Existing Specs

| Spec | Aussage zur LPI-Eingabe |
|---|---|
| `docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md` | Basis-Spec der LPI-Fusion; Known Limitations halten den Momentan-/Stundenmax-Bruch als bekannt fest |
| `docs/specs/modules/feat_1679_lpi_schwellen_region_tabelle.md:345-350` | DE_ALPEN 1/30/50 **„kalibriert auf den Momentanwert `lpi`"**; Bruch „bleibt bestehen" |
| `docs/specs/modules/feat_1678_lpi_eu_schwellenleiter.md` | EU_REST-Leiter (Schröder et al. 2022); liest ebenfalls `lightning_potential_lpi_jkg` |

## Risks & Considerations

1. **Harter Wechsel wäre eine Regression.** `lightning_potential_max_lpi_jkg` wird nur von
   ICON-D2 (DE_ALPEN) befüllt. Ohne Rückfall auf `lpi` verlören alle übrigen Gebiete das
   Blitzpotenzial-Signal ersatzlos. Der Rückfall ist fachlich sauber, weil ICON-EUs
   `lpi_con_max` bereits ein 60-Minuten-Maximum ist — es vergleicht dann Maximum gegen Maximum.
2. **`or` wäre falsch.** LPI `0.0` ist ein gültiger Wert („kein Blitzpotenzial"), aber in Python
   unwahr. `max_lpi or lpi` fiele bei exakt 0,0 still auf den Momentanwert zurück. Es braucht
   eine ausdrückliche `is not None`-Prüfung — als AC festzunageln, mit Mutationsprobe.
3. **Empfindlichkeit steigt messbar — und am oberen Ende am stärksten.** Aus der bereits
   gemessenen Tabelle in §4.3 des Gesamtkonzepts (Verhältnis der beiden Spalten) folgt für
   ICON-D2 der Faktor, um den ein Schwellenwert häufiger überschritten wird:

   | Schwelle | `lpi` überschreitet | `lpi_max` überschreitet | Faktor |
   |---|---|---|---|
   | ≥ 5 | 235× seltener als EU | 51× seltener als EU | **≈ 4,6×** |
   | ≥ 20 | 137× | 27× | **≈ 5,1×** |
   | ≥ 50 | 57× | 8,7× | **≈ 6,6×** |

   Die Leiter bleibt unverändert ⇒ „schwer" (≥ 50) würde rund **6,6-mal so oft** vergeben.
   Das ist keine Feinheit, sondern eine Produktänderung.
4. **Eichbasis ist nur mittelbar belegt.** Der Kommentar in `model_registry.py:145-152` bindet
   1/30/50 an Bína et al. 2022 / COSMO-D2, sagt aber **nicht wörtlich** „Momentanwert". Die
   Zuordnung stammt aus `feat_1679`. Ein Primärzitat, das die Bína-Schwellen ausdrücklich als
   instantan oder als Stundenmaximum ausweist, existiert im Repo **nicht** (geprüft, mit
   Positivkontrolle am Schröder-Zitat, das sehr wohl auffindbar ist). Nicht raten.
5. **Nachkalibrierung ist nicht verfügbar.** Der Weg über Open-Meteo scheidet aus (liefert für
   ICON-D2 nur `lpi`, kein `lpi_max`); `lpi_max` kommt von `opendata.dwd.de` ohne Langzeitarchiv.
   Eine eigene Eichung über eine Konvektionssaison ist mit den vorhandenen Quellen **nicht**
   machbar — dieselbe Datenlücke, die schon #1678 zur publizierten Leiter gezwungen hat.
6. **Ein Wächter kippt absichtlich.** `tests/tdd/test_thunder_output_invariance_new_signals.py`
   sichert ausdrücklich, dass `lightning_potential_max_lpi_jkg` **nicht** ausgabewirksam ist.
   Er wird durch diese Änderung rot — das ist kein Flake, sondern die bewusste Umkehr einer
   dokumentierten Entscheidung. Erfordert Anpassung **mit** Begründung, nicht Löschung.
   Ebenfalls berührt: `test_thunder_enrichment_fuses_level_shared_path.py` (Produktionspfad,
   echte GRIB2-Fixture) sowie `test_thunder_named_signals_enrichment.py` /
   `test_thunder_new_signals_enrichment.py`.
7. **Kopplung #1468 (Peer-Session, Onset-Verschiebungs-Alarm).** Dort entsteht
   `thunder_onset_utc` = erste Stunde mit `thunder_level >= LOW` aus genau dieser Fusion. Die
   Alarm-Schwellen sind **asymmetrisch** (1 h früher meldet, 3 h später erst) — dieser Umbau
   schiebt ausschließlich nach vorne, also in die scharfe Richtung. Beim ersten Lauf nach dem
   Merge können Beginn-Alarme entstehen, ohne dass sich das Wetter geändert hat. Wächter dort:
   `tests/tdd/test_onset_computation_sources.py`, `tests/tdd/test_onset_shift_alert.py`.
   Der Anker wird von #1757 **nicht** angefasst.
8. **Dokumentierte Entscheidung wird umgekehrt.** §11 Rang 3 sagt „kein offener Arbeitsauftrag
   mehr". Eine Abweichung erfordert nach Projektregel eine dokumentierte Umkehr (Konzept-Zeile
   nachziehen; ADR prüfen, da ADR-0025 die Skala trägt).

## Entscheidungsbedarf (PO)

Nicht durch Recherche auflösbar, weil es eine Produktabwägung ist:

- **A — Umsetzen wie beauftragt** (`lpi_max` bevorzugt, `lpi` Rückfall, Leiter unverändert).
  Behebt die Trefferquote, erkauft sie mit rund 5–6,6× häufigeren Meldungen, am stärksten bei
  „schwer". Fachliches Argument dafür: die unterste Sprosse ist eine **Nachweisschwelle**
  („blitzt es überhaupt"), und für die Frage „blitzt es in dieser Stunde" ist das Stundenmaximum
  die richtige Größe — der Momentanwert am Stundenrand verfehlt Gewitter systematisch, was den
  Recall von 5,6 % genau erklärt.
- **B — Nur die Nachweis-Sprosse auf `lpi_max`,** obere Sprossen weiter auf `lpi`. Physikalisch
  am ehesten verteidigbar, aber zwei Statistiken in einer Leiter — widerspricht „eine
  Fusionsregel" (ADR-0025) und ist schwer erklärbar.
- **C — Ticket als überholt schließen** (§11 folgen) und die Trefferquote als eigenes,
  sauber geschnittenes Ticket behandeln.

Empfehlung: **A**, mit der Empfindlichkeitszahl aus Punkt 3 ausdrücklich als Teil der
Freigabe — nicht als Nebenwirkung im Kleingedruckten.
