# ADR-0053: Der Ortsvergleich bekommt kanal-eigene Metrikauswahl für die Übersichtstabelle zurück (löst ADR-Bezug aus #1287/#1291/#1351 ab)

- **Status:** Akzeptiert
- **Datum:** 2026-08-13
- **Bezug:** Issue #1703 Scheibe 8, Spec
  `docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md` (AC-S8-1 bis
  AC-S8-15), Kontext-Dokument `docs/context/feat-1703-s8-compare-kanal-tabs.md`.
  PO-Entscheid 2026-08-10, Issue #1514, Entscheidung (a). Löst die
  Abschaffungs-Entscheidungen aus #1287/#1291 (2026-07-18) und #1351 Teil 2
  (2026-07-24) ab; **schreibt ADR-0050** (Metrik-Kaskade) unverändert für
  Compare fort, statt sie zu duplizieren.

## Kontext

Der Ortsvergleich führte bereits einmal eine kanalweise Metrikauswahl
(Step4Layout, Issue #442, 2026-05-29). Sie wurde in drei Schritten wieder
abgeschafft:

| Datum | Issue | Was |
|---|---|---|
| 2026-07-18 | #1287/#1291 | Kanal-Metrikauswahl aus der **Bedienung** entfernt — Begründung wörtlich „Attrappen" |
| 2026-07-24 | #1351 Teil 2 | Feld `channel_layouts` aktiv aus dem Compare-**Speicherweg** entfernt (`compareEditorSave.ts`), samt Bestands-Migration `scripts/migrate_1351_drop_compare_channel_layouts.py` |
| 2026-07-29 | #1359 | Ersatzweg: **eine** flache Liste (`active_metrics`), in Telegram/SMS nur budgetbasiert gekürzt, nie anders ausgewählt |

`docs/specs/modules/rework_1351_compare_catalog.md:215-217` hielt für eine
etwaige Rückkehr ausdrücklich fest: „sollte in Zukunft doch eine
Kanal-spezifische Metrikauswahl für Compare gewünscht werden, ist das eine
**neue Spec** (widerspricht aktuell #1287/#1291 und der Konvergenz-Richtung)".

**Der eigentliche Grund der damaligen Abschaffung — der Kern dieser
Entscheidung:** Die Kanal-Auswahl wurde nicht entfernt, weil sie
unerwünscht war, sondern weil sie **wirkungslos** war. Die Oberfläche bot
eine Kanal-Auswahl an; `report_config_resolver.py` las dabei nie mehr als
eine einzige flache Liste (`display_config.get("active_metrics")`) und
reichte sie unverändert an alle Renderer durch — unabhängig davon, was der
Editor je Kanal anzeigte. Eine Bedienoberfläche ohne Wirkung auf die
zugestellte Ausgabe ist eine Attrappe; sie zu entfernen war zum damaligen
Zeitpunkt richtig.

Am 2026-08-10 entschied der PO in #1514 (Entscheidung (a)): Compare soll
Kanal-Layouts bekommen wie der Trip-Editor. Das ist eine bewusste
**Entscheidungs-Umkehr** einer bereits dokumentierten Entscheidung — CLAUDE.md
verlangt dafür zwingend ein neues ADR mit Status „Abgelöst durch", statt die
Vorentscheidung still zu überschreiben.

## Entscheidung

**1. Compare bekommt kanal-eigene Metrikauswahl für die Übersichtstabelle
zurück — beschränkt auf `active_metrics`.** Umgesetzt in #1703 Scheibe 8.
Ausblick (`outlook_metrics`) und Stundenverlauf (`hourly_metrics`) bleiben
in dieser Scheibe bewusst global — eigene, getrennt gespeicherte
Auswahllisten ohne Kanal-Ebene (Scheiben-Schnitt, kein Widerspruch zur
Kaskaden-Zusage aus ADR-0050, weil diese sich auf Kanäle bezieht, nicht auf
Ausgabeflächen).

**2. Die Bedingung, die den Rückfall diesmal verhindert: die ganze Kette,
nicht nur die Oberfläche.** Diese Scheibe liefert Oberfläche, Speicherweg,
Resolver UND Renderer gemeinsam; der Nachweis hängt an der **zugestellten**
Ausgabe, nicht am PUT-Body. Konkret:

- `resolve_channel_enabled_metrics()`
  (`src/output/renderers/compare_metric_ids.py:200-241`) wendet ADR-0050
  Regel 1/2 als reine ID-Mengen-Operation auf zwei bereits aufgelöste
  Listen an — Kanal-Liste wird gegen die globale Liste geschnitten
  (`allowed = set(global_metrics)`, Zeile 240-241).
- `CompareRenderOptions.enabled_metrics_by_channel`
  (`src/services/report_config_resolver.py:206-208`) wird additiv neben
  dem bestehenden `enabled_metrics`-Feld geführt;
  `resolve_compare_render_options()` füllt es einmal für alle drei Kanäle
  (Zeilen 296-313).
- **Acht kanalweise Aufrufstellen** lesen das neue Feld statt der
  gemeinsamen Liste: drei in `scheduler_dispatch_service.py` (Zeilen 439,
  505, 509) und fünf in `compare_preview_service.py` (Zeilen 65, 70, 105,
  122, 186).
- Der deterministische Wirkungs-Wächter
  `tests/unit/test_compare_channel_metrics_reach_the_renderer.py` prüft
  nicht `CompareRenderOptions` (dort wäre die Mechanik korrekt, aber die
  Wirkung ungeprüft), sondern die **fertige gerenderte Zeichenkette** je
  Kanal — Prüfort == Wirkort. Er fängt jede der acht Aufrufstellen
  **einzeln**: die Fixture wählt für E-Mail, Telegram und SMS je eine
  ANDERE Metrik ab, sodass ein Rückfall auf die gemeinsame Liste an genau
  der betroffenen Stelle auffällt, nicht nur summarisch. Vor dieser
  Scheibe fing offline **kein** Test diese Klasse von Regression.

**3. ADR-0050 gilt für Compare unverändert — Regeln 1–4 werden zitiert,
nicht dupliziert.** Grundauswahl ist das Maximum, ein Kanal darf nur
abwählen, eine globale Abwahl wirkt sofort in allen Kanälen, „Aus" ist ein
Zustand (keine Löschung). Diese Entscheidung fügt ADR-0050 keine neue Regel
hinzu, sondern wendet die bestehenden auf eine zweite Domäne (Compare
`active_metrics`) an, die bislang keine Kanal-Ebene besaß.

**4. Besonderheit gegenüber dem Trip: `None` und `[]` bedeuten
Verschiedenes.** `resolve_channel_enabled_metrics()` unterscheidet
`global_metrics is None` (Feld `active_metrics` fehlt komplett — es gibt
**kein** Maximum, also wird nicht geschnitten) von `global_metrics == []`
(bewusste Leerauswahl — das **ist** ein Maximum, nämlich die leere Menge;
jeder Kanal wird auf `[]` geschnitten). Der Trip behandelt beide Fälle
gleich: `_clip_to_global_maximum()` (`src/app/models.py:893`) prüft
`if not self.metrics:` (Zeile 913) — eine leere Liste UND ein fehlendes
Feld lösen dort denselben Zweig aus. Das ist **kein Widerspruch, sondern
Absicht**: im Compare-Datenmodell bedeuten `null` und `[]` bei
`active_metrics` seit #1366 („leer heißt leer, nicht alle") unterschiedliche
Dinge, im Trip-Datenmodell (`MetricConfig`-Liste mit `enabled`-Flags pro
Eintrag) fällt diese Unterscheidung strukturell nicht an. Beide Renderer
respektieren damit die jeweils eigene, bereits etablierte Leer-Semantik
ihres Datenmodells — ADR-0050 selbst trifft dazu keine Aussage.

## Verworfene Alternativen

- **Nur die Technik liefern, die Oberfläche folgt in einer Folge-Scheibe.**
  Verworfen (Analyse-Phase, F1): wäre zwar attrappenfrei in die andere
  Richtung (Wirkung ohne Bedienweg ist nicht dieselbe Sünde wie Bedienweg
  ohne Wirkung), löst aber **keine Nutzer-Zusage** ein — niemand kann
  `channel_active_metrics` ohne Editor befüllen. Das Verzeichnis selbst
  liefert das mahnende Gegenbeispiel:
  `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte`
  liegt seit #1719 S3 mit rund 300 Zeilen ohne einen einzigen Importeur
  herum — genau das Ergebnis eines gebauten, aber nie angeschlossenen
  Bausteins.
- **Kanal-Auswahl auch für Ausblick und Stundenverlauf sofort mitliefern.**
  Verworfen für diese Scheibe: hätte die Kette (Resolver, Persistenz,
  Editor) zweimal parallel neu bauen müssen und das LoC-Budget der Scheibe
  gesprengt. Bewusster Scheiben-Schnitt, keine Auslassung — eine Folge-Scheibe
  müsste dieselbe Kette für `outlook_metrics`/`hourly_metrics` wiederholen.
- **`None`/`[]` wie beim Trip vereinheitlichen (beide als „kein Filter"
  behandeln).** Verworfen: hätte die seit #1366 geltende Compare-Semantik
  „leer heißt leer, nicht alle" für `active_metrics` gebrochen und wäre eine
  stille Verhaltensänderung für jedes Preset mit bewusster Leerauswahl
  gewesen. Die Divergenz zum Trip ist eine Eigenschaft der beiden
  unterschiedlichen Datenmodelle, keine Inkonsistenz, die es zu beheben gilt.

## Konsequenzen

- **Positiv:** Die Nutzer-Zusage „andere Wettergrößen je Kanal — und es
  kommt auch so an" ist für die Übersichtstabelle eingelöst und über einen
  Wächter abgesichert, der die zugestellte Ausgabe prüft, nicht nur den
  Speicherweg. #1287/#1291/#1351 gelten für die Übersichtstabelle als
  überholt, ohne dass ihre ursprüngliche Begründung („Attrappen") entwertet
  wird — sie war zum damaligen Zeitpunkt korrekt.
- **Negativ / Preis:** Zwei Datenmodelle für Metrik-Auswahl bestehen jetzt
  nebeneinander mit unterschiedlicher `None`/`[]`-Semantik (Compare vs.
  Trip) — wer künftig Code zwischen beiden teilt, muss diesen Unterschied
  kennen und darf ihn nicht als Bug lesen. Drei Zeilen im Frontend
  (`frontend/src/lib/components/compare/CompareTabs.svelte:710`, `:737`,
  `:782` — Snapshot-Kopie, Hydration, Rollback von
  `channelActiveMetricKeys`) sind offline nicht bewachbar: das Projekt hat
  kein DOM, `.svelte`-Dateien sind unter `node:test`
  (ADR-0020) nicht importierbar. Nur Playwright-Klickpfade gegen Staging
  decken sie ab.
- **Folgepflicht:** Ausblick und Stundenverlauf bleiben bis zu einer
  eigenen Folge-Scheibe global — eine Erwartung „das funktioniert doch
  überall wie bei der Übersicht" ist für diese beiden Flächen falsch und
  muss bei jeder Anfrage dazu richtiggestellt werden. Jede künftige
  Erweiterung der Compare-Kanal-Kaskade übernimmt ADR-0050 Regeln 1–4
  unverändert (Zitat, keine Neuformulierung) und muss die `None`/`[]`-
  Unterscheidung aus Abschnitt „Entscheidung" Punkt 4 respektieren.
