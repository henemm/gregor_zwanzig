# Übergabe: #1401 nach Scheibe A2a (Stand 2026-07-28)

Kurzzettel für die Sitzung nach einem `/clear`. Ausführlich steht alles in
`docs/context/fix-1401-namensregister-a.md` (Analyse, Messwerte, PO-Entscheidungen)
und in den beiden Specs.

## Erledigt und live

**#1401 Scheibe A1** — `21a82c12`, Prod verifiziert 2026-07-28.
Der zentrale Wetterkatalog (`src/app/metric_catalog.py`) ist das Namensregister;
`compare_metric_catalog.py` leitet den Anzeigenamen daraus ab und liefert die
Auswertung als eigenes Feld `aggregation_label`. Vier Auswahlflächen des
Ortsvergleichs zeigen Name und Auswertung getrennt. Spec:
`docs/specs/modules/fix_1401_a1_namensregister.md`. Workflow archiviert.

Mail-Nachweis lief über eine echt zugestellte Staging-Mail (UID 12396):
Übersichts- und Stundentabelle unverändert in HTML **und** Klartext,
`email_spec_validator.py` Exit 0; Ausblick-Spalten tragen wie freigegeben
`Tag · Temperatur Maximum · Temperatur Minimum · Böen`.

## Erledigt: Scheibe A2a

Die 26 Metrik-Zeilen von `CV2_METRICS` (`src/output/renderers/email/compare_html.py`)
tragen jetzt `metric_id` + `aggregation` — die Übersichtstabelle der Vergleichsmail
nennt damit für jede Zeile ihre zentrale Wettergröße. **Keine sichtbare Änderung:**
jedes getippte `"label"` ist unangetastet, festgenagelt Zeichen für Zeichen durch
`tests/unit/test_compare_mail_labels_unchanged.py` (26 Übersichtszeilen + 9
Stundenspalten, HTML **und** Klartext, wörtliche Literale).

Der Wächter `tests/unit/test_compare_mail_metric_link_completeness.py` schlägt an,
sobald eine Zeile ihre Verknüpfung nicht hat — genau der Fehler, der in #1296 und
#1324 zweimal unbemerkt durchging. Adversary hat alle fünf Fehlerarten real
injiziert; der Wächter wurde jedes Mal rot und nannte die Zeile beim Namen.

**Abweichung von der ursprünglichen Spec (Tech-Lead-Entscheid, Changelog 2026-07-28b):**
`HOUR_METRICS` bekommt **kein** `aggregation`. Die Stundentabelle zeigt Momentanwerte;
keiner der zentralen Auswertungswerte (`min`/`max`/`avg`) ist dafür sachlich richtig,
und das Kollisions-Suffix aus A2b kann bei 9 paarweise verschiedenen `metric_id`
strukturell nie greifen. Der Wächter weist ein dort gesetztes `aggregation` aktiv
zurück.

## Als Nächstes

1. **#1404** ✅ **geliefert** (2026-07-28, eigener Workflow
   `fix-1404-validator-spaltennamen`, Spec
   `docs/specs/modules/fix_1404_validator_spaltennamen.md`). Der Validator
   akzeptiert jetzt **beide** Spaltenfassungen als Übergang (`_HOUR_COLUMNS_V2`
   um `Feels`/`Gust`/`Rain`/`Thdr`/`Rain%`/`Visib` erweitert, strikt additiv,
   Prüfdatum 2026-10-26) und prüft die Übersichtstabelle für 24 statt 5 Zeilen.

   **Was A2b daraus mitnehmen MUSS:**
   - `_OVERVIEW_METRIC_CHECKS` ist **nicht** union-basiert — es kennt nur die
     heutigen deutschen Labels. Sobald A2b auf die englische Kurzform umstellt,
     greift keine der 24 Prüfungen mehr, bis die Tabelle nachgezogen ist.
     **Das gehört in A2b hinein**, sonst reißt die eben geschlossene stille
     Lücke sofort wieder auf.
   - `tests/unit/test_compare_mail_overview_plausibility_coverage.py` wird bei
     A2b **planmäßig rot**. Das ist kein Regress, sondern der Wächter, der
     genau dieses Nachziehen erzwingt.
   - Nach A2b: Rückbau der Übergangs-Union (alte Spaltennamen entfernen) plus
     der aufgeschobene Schritt „unbekannte Beschriftung = lauter Befund" —
     beides gehört in eine eigene Lieferung **nach** A2b, nicht hinein.
2. **A2b** — Beschriftung aus `col_label` ableiten + Kollisionsregel, inkl.
   `comparison.py::_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` (vierte Namensquelle, Klartext).
   Braucht #1404 zuerst. Umfang liegt über dem Deckel, PO-Freigabe für eine
   angehobene Grenze einholen, sobald die echte Zahl feststeht.
3. **Scheibe B** (Stundenverlauf `compareHourlyMetricDefs.ts`, Alarme
   `AlertMetricLevelTable.svelte` + divergente Zweitkopie `alertMetricLabels.ts`),
   dann **Scheibe C** (Begründung statt Leerstelle).

**Erleichterung für A2b:** Die Beschriftungen in `CV2_METRICS` und
`comparison.py::_PLAIN_ROWS` sind heute Zeichen für Zeichen identisch (alle 26
geprüft). Die von der Spec befürchtete Abweichung zwischen HTML und Klartext
existiert bei der Übersichtstabelle nicht — AC-2 ist dort schon erfüllt und wäre
reine Absicherung gegen Rückfall.

## Fallen, die schon Zeit gekostet haben

- **`compare_html.py` fällt unter das Renderer-Commit-Gate #811.** Für eine reine
  Compare-Änderung verlangt es **nur** den Compare-Nachweis
  (`email_spec_validator.py`), nicht den Trip-Pfad — `briefing_staged` ist leer,
  Matrix-Test und Briefing-Validator sind dann automatisch erfüllt. Der Nachweis
  muss **frischer** sein als die mtime von `compare_html.py`.
- **Der Validator schreibt seine Kennung aus `OPENSPEC_ACTIVE_WORKFLOW`**, das Gate
  liest sie als `workflow_id`. Nur `GZ_ACTIVE_WORKFLOW` zu setzen ergibt ein Log mit
  `workflow_id: unknown`, das das Gate verwirft. **Beide Variablen setzen.**
  (Nebenbefund in #1199.)
- **Der Ausblick der Mail liest das Label direkt** aus `COMPARE_METRIC_CATALOG`
  (`compare_outlook_metric_ids.py:98`), nicht über `compare_html.py`. Wer nur
  Importe prüft, hält eine Katalogänderung fälschlich für mail-frei.
- **Staging-Vergleichsmail auslösen:** `POST http://127.0.0.1:8001/api/scheduler/compare-presets/cp-21e198c1b74020dd/send?user_id=default`
  (Preset `default`, 3 Orte, Empfänger `gregor-test@henemm.com`). Damit der
  Ausblick rendert: `outlook_enabled` steht **top-level** (ein gespeichertes
  `null` schaltet ihn ab), `outlook_metrics` in `display_config` und erwartet
  **Dicts** `{metric_id, aggregation}` — Compare-Keys werden verworfen.
  Jeder Versand kostet open-meteo-Kontingent: einmal senden, dann per IMAP prüfen.
  Ein erneuter Validator-Lauf braucht **keinen** neuen Versand.
- **Umfangszähler rechnet Dokumentation mit.** CLAUDE.md sagt, `docs/`/`*.md`
  zählen nicht — `openspec.yaml::scope_guard.loc_exclude_patterns` schließt sie aber
  nicht aus. Spec + Übergabezettel schlugen bei A2a mit ~540 Zeilen zu Buche.
  (Nebenbefund in #1199.)
- **Rebase vor jedem Commit**: das Bash-Gate blockt, sobald der Branch hinter
  `origin/main` liegt; parallele Sitzungen pushen häufig dazwischen. Nach einem
  Rebase den Compare-Nachweis erneuern, falls er dadurch älter als die Datei wird.

## Offene Tickets

- **#1401** bleibt offen bis A2b/B/C geliefert sind.
- **#1404** Validator-Härtung, angelegt 2026-07-28.
- Nebenbefunde sind in **#1199** eingetragen (SMS-Kürzel-Widerspruch,
  `PROFILE_METRICS_WITH_SCALES`, `LTComparePreview.svelte`, Staging-Preset,
  Validator-Kennung, Umfangszähler).
- Epic **#1372**: Fortschrittstabelle ist auf Stand (S1–S3 ✅, S2 mit A1 sichtbar
  abgeschlossen, Restarbeit von #1401 als eigene Zeile).
