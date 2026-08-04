# Context: feat-1474-blitzpotenzial-stufen

Issue: [#1474](https://github.com/henemm/gregor_zwanzig/issues/1474) — S3 zu #1419, **letzter offener Restpunkt**
Vorgänger-Scheiben live: `860a3baf` (vierte Stufe `LOW` aus Blitzdichte + CAPE), `a75a5ae5` (Cockpit-Farbe, Erwähnungsschwelle)
Stand der Messung: Worktree `intake-1465`, HEAD `c31f777c`

## Request Summary

Das DWD-Blitzpotenzial (`lightning_potential_lpi_jkg`) liegt seit #1457 S2b/S2c an, fließt
aber nicht in die Gewitterstärke ein. Es soll als **viertes Signal** in die bestehende
Fusion andocken — mit **eigener Schwellentabelle**, weil es eine andere Größe auf einer
anderen Skala ist als die Blitzdichte.

## Der Eingriff ist klein und der Andockpunkt existiert

`thunder_level_from_signals(wettercode_level, lightning_density, cape_jkg)`
(`src/output/metric_format.py:317-353`) übersetzt **jedes Signal eigenständig** in ein
`ThunderLevel` und nimmt dann `max_thunder()` über die Nicht-`None`-Signale. Der
Docstring nennt das Ziel ausdrücklich: „keine Sonderlogik für die Blitzdichte, damit ein
künftiges Signal mit derselben Struktur andockt."

Aufrufer ist die einzige Stelle `_fuse_thunder_levels` (`src/providers/thunder_enrichment.py:84-100`),
die im gemeinsamen Anreicherungsweg hängt und **immer** läuft — auch außerhalb eines
Zuständigkeitsgebiets und bei Abruf-Fehlschlag.

Nötig sind damit genau drei Dinge: vierter Parameter + eigene Schwellenleiter in
`thunder_level_from_signals`, Durchreichen von `dp.lightning_potential_lpi_jkg` in
`_fuse_thunder_levels`, und die Aufhebung der bewussten Aussparung in
`thunder_enrichment.py:125-128` (S2b AC-8, „keine Stufenbildung in dieser Scheibe").

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/metric_format.py:299-304` | `_LIGHTNING_{LOW,MED,HIGH}_MIN` — Vorbild für die neue Schwellentabelle, inkl. Quellenbeleg im Kommentar |
| `src/output/metric_format.py:306-315` | `_cape_low_min_jkg()` — Vorbild „Schwelle aus dem Katalog lesen statt duplizieren" |
| `src/output/metric_format.py:317-353` | `thunder_level_from_signals` — der Prüfling |
| `src/output/metric_format.py:290-295` | `max_thunder` — kanonische Ordnung, nacktes `max()` wäre alphabetisch falsch |
| `src/providers/thunder_enrichment.py:84-100` | `_fuse_thunder_levels` — einziger Aufrufer |
| `src/providers/thunder_enrichment.py:125-128` | Die Aussparung aus S2b, die hier fällt |
| `src/app/models.py:153-161` | Feld + Skalen-Kommentar („Messwerte bis ~225") |
| `src/providers/dwd.py:86` / `dwd_eu.py:88,96` | Die zwei Quellen: `lpi` (ICON-D2) und `lpi_con_max` (ICON-EU, auf Signalschlüssel `lpi` gemappt) |
| `tests/tdd/test_thunder_level_from_signals_fusion.py` | 8 Tests der Fusion |
| `tests/tdd/test_thunder_enrichment_fuses_level_shared_path.py` | 2 Tests des gemeinsamen Wegs |

## Existing Patterns

- **Je Signal eine eigene Skala** (#1419 Abs. 3.1, ADR-0025): 88 und 0,2 sehen aus wie
  Werte derselben Skala. Eine gemeinsame Grenze wäre ein stiller Fehler.
- **Schwellen belegen, nicht erfinden** — PO-Vorgabe, deshalb #1456 ersatzlos geschlossen.
  Die Blitzdichte-Konstanten tragen ihre ECMWF-Fundstelle im Kommentar; der eine **nicht**
  publizierte Wert (`0.075`) ist als Known Limitation ausgewiesen. Dasselbe Muster hier.
- **Schwelle aus dem Katalog lesen, wenn es einen Eintrag gibt** — CAPE tut das
  (`risk_thresholds["medium"]`). Für Blitzdichte und -potenzial gibt es **keinen**
  Katalogeintrag (gemessen: `metric_catalog.py` kennt `cape`, aber weder `lightning_density`
  noch `lightning_potential`; beide sind keine wählbaren Metriken). Also Modulkonstanten
  mit Quellenbeleg, wie bei der Dichte.
- **`None` ≠ `NONE`**: kein Signal → `None` („keine Aussage"); Signal unter der Schwelle →
  `ThunderLevel.NONE` („geprüft, unauffällig"). Nie als Entwarnung lesen.

## Dependencies

- **Upstream:** `lightning_potential_lpi_jkg` aus `de_direct` (ICON-D2) und `eu_direct`
  (ICON-EU) über `thunder_enrichment`. Beide füllen **dasselbe** Feld (bewusst,
  `feat_1457_s2c_...md` Known Limitation 4).
- **Downstream:** `dp.thunder_level` → Renderer (Mail-Prosa, Stundentabelle, Telegram,
  SMS-Token), Risiko-Übersicht, Cockpit-Farbe, **Alarme**. ADR-0025: `dp.thunder_level`
  ist die einzige zulässige Rohdatenquelle für die Gewitteraussage.

## Risks & Considerations

1. **Blast Radius ist europaweit, nicht nur DE/Alpen.** Seit S2c ist `eu_direct` die
   Catch-all-Zeile der Zuständigkeitstabelle — das Potenzial liegt damit für nahezu jeden
   europäischen Ort an. Bisher trieb außerhalb Frankreichs nur Wettercode und CAPE die
   Stufe. Über `max_thunder()` kann eine zu niedrige Schwelle die Gewitterstufe
   flächendeckend anheben und Alarme auslösen. **Das ist das eigentliche Risiko dieser
   Scheibe, nicht der Codeumfang.**
2. **Ein Feld, zwei Modelle mit unterschiedlicher Bildungsvorschrift.** ICON-D2 liefert
   `lpi` als **Momentanwert** (2,2 km), ICON-EU `lpi_con_max` als **60-Minuten-Maximum**
   (~6,5 km, `dwd_eu.py:42-45`). Ein Stundenmaximum liegt systematisch über einem
   Momentanwert — dieselbe Schwelle lässt ICON-EU-Gebiete eher eskalieren. Gemessene
   Wertebereiche liegen dennoch nah beieinander (D2 bis ~225, EU 0…269). Muss als Known
   Limitation benannt werden, nicht verschwiegen.
3. **Schwellenwahl ist die einzige echte Entscheidung.** Belegt sind: DWD betrieblich
   **5 J/kg**; publizierte Verifikation **30–90 % Blitzwahrscheinlichkeit für Grenzen
   zwischen 0 und 50**. Die Trennung „mittel/hoch" innerhalb dieser Spanne ist eine
   Produktentscheidung, keine Forschungsfrage — und muss wie `0.075` bei der Dichte als
   nicht-publiziert ausgewiesen werden.
   Plausibilitätsanker aus der Messung vom 2026-08-02: GR20/Petra Piana bei realer
   Gewitterlage **88,2**; Zillertal am selben Tag ruhig **0,9**.
4. **DRY: die Schwellenleiter darf nicht kopiert werden.** Der Dichte-Block
   (`metric_format.py:338-346`) ist eine inline if/elif-Leiter. Ein zweites Signal per
   Copy-Paste danebenzusetzen ist genau das Pendant-Muster, das #1481 unterbindet — und es
   widerspricht dem eigenen Docstring-Versprechen („damit ein künftiges Signal mit
   derselben Struktur andockt"). Empfehlung: **eine** Leiter-Funktion
   `(wert, low, med, high) -> ThunderLevel`, von beiden Signalen genutzt.
5. **Mutations-Gegenprobe ist Pflicht und hier besonders scharf zu stellen.** Ein Test,
   der nur `thunder_level_from_signals` direkt füttert, beweist nicht, dass das Potenzial
   den Produktionspfad erreicht — die Aussparung sitzt in `_fuse_thunder_levels`, nicht in
   der Fusion. Genau die Konstellation, in der #1457 dreimal ein grünes AC ohne Wirkung
   erzeugte. Mindestens ein AC muss über `enrich_thunder` laufen.
6. **#1491 wird sichtbarer.** Prosa-Satz und Stundentabelle widersprechen sich bereits
   heute; ein zusätzliches Signal, das die Stufe häufiger anhebt, verschärft das. Eigenes
   Ticket, aber beim Staging-Nachweis im Blick behalten.

## Existing Specs

- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` — Fusion, `None` ≠ `NONE`,
  AC-9 (ein Anschluss, kein Sonderweg)
- `docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md` — Vorgänger-Scheibe
- `docs/specs/modules/feat_1457_s2b_gewitter_dwd_alpen.md` — AC-8 (die Aussparung, die hier fällt)
- `docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md` — Known Limitation 4 (ein Feld, zwei Quellen)
- ADR-0025 — eine Gewitterquelle je Kanal, Skalen nie vermischen, Beweispflicht Produktionspfad
