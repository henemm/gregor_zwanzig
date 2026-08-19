# Context: feat-1848-c-waechter-gehzeit

## Request Summary

Die vier Gehzeit-Größen bleiben laut PO-Entscheid vom 2026-08-19 **trip-exklusiv** und werden im
Ortsvergleich nie angeboten. Diese Scheibe sichert die Unterscheidung gegen stilles Verschwinden ab
(Wächter) und räumt drei Kommentar-Aussagen auf, die durch den Entscheid überholt oder schon vorher
falsch waren.

Betroffene Kennungen: `temperature_day_low`, `temperature_day_high`, `wind_chill_day_low`,
`wind_chill_day_high`.

## Gemessener Ist-Stand (vor der Arbeit)

Damit der Wächter nicht als Reparatur erscheint, die er nicht ist:

| Prüfung | Ergebnis | Beleg |
|---|---|---|
| Kommen die vier im Ortsvergleich-Katalog vor? | **Nein**, 0 Treffer in allen drei Compare-Dateien | `compare_metric_catalog.py`, `compare_metric_ids.py`, `compare_outlook_metric_ids.py` |
| Positivkontrolle desselben Suchmusters | `temp_min_c` wird gefunden ⇒ Suchweg trägt | `compare_metric_catalog.py` |
| Tragen alle vier „(Gehzeit)" im `label_de`? | **Ja**, alle vier | `src/app/metric_catalog.py:173,190,260,271` |
| Stundenverlauf-Ausschluss vorhanden? | **Ja**, benannte Menge mit Begründungstext | `src/output/renderers/compare_hourly_metric_ids.py:59-64`, Begründung ab `:85-95` |

**Die Invariante hält heute. Der Wächter ist vorbeugend, nicht korrigierend.**

## Die eigentliche Lücke (Kern dieser Scheibe)

Der bestehende Drift-Wächter `tests/unit/test_compare_catalog_derives_from_central_catalog.py` führt
die vier Kennungen in der Ausnahmeliste `CENTRAL_METRICS_COVERED_ELSEWHERE` (`:44-82`). Diese Liste
wird an **genau einer** Stelle benutzt — sie wird von der Prüfmenge **abgezogen**:

```
:130     - set(CENTRAL_METRICS_COVERED_ELSEWHERE)
```

Damit gilt: Für diese vier Kennungen ist die Zusicherung „hat keinen Compare-Eintrag" **trivial
wahr**, weil sie aus der Prüfung herausgenommen sind. Bekäme eine der vier morgen einen
Compare-Eintrag, würde **kein Test rot** — die Ausnahme würde stillschweigend zur Lüge, und die
fachliche Unterscheidung (Gehzeit-Fenster vs. konfiguriertes Tagesfenster) wäre verloren. Genau das
benennt Punkt 4 der PO-Folgearbeiten.

**Die Asymmetrie ist der Beleg, dass hier etwas fehlt:** Die Schwesterliste
`AGGREGATION_CHECK_EXEMPTIONS` hat sehr wohl einen Wächter, der sie bewacht —
`test_aggregation_exemptions_only_shrink` (`:317`) prüft auf `stale` und `fixed` Einträge, und
`test_aggregation_check_exemptions_empty_after_1391_1392_fix` (`:305`) nagelt fest, dass sie leer
ist. Für `CENTRAL_METRICS_COVERED_ELSEWHERE` existiert nichts davon.

Fehlerklasse: [[reference_ausschluss_erzeugt_die_bedingung_die_ihn_begruendet]] — der Ausschluss
erzeugt die Bedingung, mit der er begründet wird.

## Zu korrigierende Aussagen

1. **Überholter Rückbaupfad** (`tests/unit/test_compare_catalog_derives_from_central_catalog.py:72-78`):
   behauptet „Rueckbaupfad: #1848 … Danach fallen diese vier Zeilen ersatzlos weg." Der PO-Entscheid
   vom 2026-08-19 sagt das Gegenteil: sie bleiben trip-exklusiv.
2. **Vier Einzelvermerke** (`:79-82`): jeder der vier Einträge trägt zusätzlich den Text
   `Rueckbau mit #1848`. Auch das ist überholt — es genügt nicht, nur den Blockkommentar zu ändern.
3. **Falscher Funktionsname** (`src/app/metric_catalog.py:168,187,256,267`): Die Blockkommentare
   nennen `_collect_hiking_window_dps()`. **Diese Funktion existiert nicht.** Sie heißt
   `collect_hiking_window_points()` (`src/output/renderers/day_window.py:186`). Gefunden beim
   Auszählen dieser Scheibe — der Kommentar, den der PO-Entscheid ausdrücklich für „tragend"
   erklärt, zeigt auf einen Namen, den es nicht gibt.

## Related Files

| Datei | Relevanz |
|---|---|
| `tests/unit/test_compare_catalog_derives_from_central_catalog.py` | Trägt die Ausnahmeliste und die überholten Kommentare; hier kommt der neue Wächter hin oder daneben |
| `src/app/metric_catalog.py:167-275` | Die vier Register-Einträge samt tragender „(Gehzeit)"-Beschriftung und der vier falschen Funktionsnamen |
| `src/output/renderers/compare_metric_catalog.py` | Kuratierter Ortsvergleich-Katalog (26 Einträge), `get_compare_metric_catalog()` |
| `src/output/renderers/compare_hourly_metric_ids.py:59-64` | `HOURLY_EXCLUDED_METRIC_IDS` — zweiter Weg in die Ortsvergleich-Auswahl |
| `src/output/renderers/compare_outlook_metric_ids.py` | Dritter Weg: 3-Tages-Ausblick |
| `src/output/renderers/day_window.py:186` | `collect_hiking_window_points()` — der echte Name |

## Existing Patterns

- **Mengen-Vergleich statt harter Anzahl** — Vorbild laut Docstring des Drift-Wächters:
  `tests/unit/test_compare_metric_catalog_consistency.py`.
- **Wirkungsnachweis im Test selbst**: der Drift-Wächter enthält Tests, die den Guard *künstlich
  brechen* (`test_guard_actually_fails_when_a_central_metric_has_no_compare_entry:428`,
  `test_aggregation_guard_actually_fails_on_a_wrong_aggregation:463`). Nur **Kopien** werden
  manipuliert, nie die echten Katalog-Listen. Dieses Muster übernimmt der neue Wächter.
- **Ausnahmeliste, die nur schrumpfen darf**, mit Test dagegen: `:317`.
- **Kern-Schicht-Reinheit**: kein Netz, kein Mock, kein Datei-I/O (Docstring `:15-17`).

## Risks & Considerations

- **Ein Abwesenheits-Test ohne Positivkontrolle ist wertlos** — er ist auch grün, wenn er am
  falschen Ort sucht. Der Wächter MUSS mitprüfen, dass sein Suchweg eine Kennung findet, die dort
  vorkommen muss (z. B. `temperature`). Vgl. [[reference_erreichbarkeit_vor_schwere_pruefen]]
- **Drei Wege in die Ortsvergleich-Auswahl** (Katalog, Stundenverlauf, 3-Tages-Ausblick). Ein
  Wächter, der nur den Katalog prüft, lässt zwei Türen offen.
- **Kommentar-Zusicherungen nicht an feste Zeilennummern hängen** — ein absoluter Zeilenanker bricht
  beim nächsten Einschub. Muster #1466: laufzeitaufgelöst prüfen.
  Vgl. [[reference_formataenderung_macht_test_hilfsparser_blind]]
- **Fremde Arbeit an derselben Datei:** #1468 (`feat-1468-onset-verschiebung`, noch nicht gemerged)
  fügt `src/app/metric_catalog.py` **additiv** zwei Register-Einträge und eine Aggregationsart
  `onset` hinzu, ohne `unit`/`decimals` bestehender Einträge zu ändern. Vereinbarte Reihenfolge:
  #1468 zuerst. Ein neuer Register-Eintrag darf den Wächter nicht rot machen — er darf nur auf die
  vier benannten Kennungen zielen, nicht auf „alles mit `_day_` im Namen".
- **Kein Produktivcode-Verhalten ändert sich.** Erwartete Ausgabe-Wirkung: keine. Damit ist die
  Staging-Verifikation ausgabeneutral und braucht den Nachweis am Baum statt an einer Mail
  (Muster #1758 AC-9).

## Existing Specs

- `docs/specs/modules/feat_1373_s2_ein_katalog.md` — Spec des bestehenden Drift-Wächters (AC-1/2/5)
- `docs/specs/modules/feat_1848_a_kaskade_eine_quelle.md` — Scheibe A dieses Epics
- `docs/specs/modules/feat_1848_b_einheiten_register.md` — Scheibe B dieses Epics
- `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md` — trägt die „compare-exklusiv"-Zusage, die laut Issue-Kommentar vom 2026-08-15 neu zu messen ist (abgetrennt als eigene Scheibe)

## Abgrenzung

**Nicht in dieser Scheibe:** die Auditfrage aus dem Issue-Kommentar vom 2026-08-15 („welche weiteren
‚Am Code gemessen'-Feststellungen hängen an aufgehobenen Voraussetzungen?"). Gemessener Umfang: 18
Spec-Dateien nennen `metrics=None`, 4 tragen eine „compare-exklusiv"-Zusage. Offenes Ergebnis, kann
PO-Entscheide auslösen — eigene Scheibe, PO-bestätigt beim Intake 2026-08-19.
