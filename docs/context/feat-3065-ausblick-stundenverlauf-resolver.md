# Context: feat-3065-ausblick-stundenverlauf-resolver

> **Hinweis (2026-11-17, [ADR-0124](../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Diese Notiz ist Historie eines gebauten Schritts. Wo sie die Karte „Inhalt je Kanal und Fläche“ (eigene Liste je Kanal und Fläche, #3031–#3037, PR #3042, #3060) als künftiges Soll nennt, gilt das nicht mehr: ADR-0124 (PO 2026-11-17) ersetzt die Karte durch **eine** Tabelle „Was steht wo“ im Reiter Wetter. Aktueller Stand: ADR-0124 und `docs/context/einstellungen_neu.md`. 3-Tages-Ausblick und Stundenverlauf folgen dann der E-Mail-Auswahl statt eigener Listen (ADR-0124 Nr. 4).

Issue #3065 (Phase 2b von Epic #3047 „Einstellung = Mail“). Vorgänger: #3057 (Phase 2, Resolver für die vier Versandkanäle, ADR-0121, live). Stand origin/main nach PR #3068/#3072 (#3047-Nachlieferungen 1+2).

## Request Summary

Der Kanal-Listen-Resolver (`src/services/channel_list_resolver.py`) liefert heute nur `email | telegram | sms | premium_sms`. Er soll zusätzlich die Flächen-Listen **`outlook`** (3-Tages-Ausblick, Trip und Orte: Reihenfolge + Roh/Einfach je Zeile, Erben der Grundauswahl wie ADR-0059) und **`hourly`** (Stundenverlauf, nur Orte, ohne Roh/Einfach) liefern. **Rein lesend**, zugestellte Mail unverändert; Nachweis per Differenztest gegen den Altpfad.

## Scope-Schnitt (Intake 2026-11-16)

- **Nicht Teil:** Speicherung bewusster Abwahl je Liste (Übergabe „Nachprüfung Punkt 7“) → eigenes Kind-Issue **#3082** (Speicherformat, Go-Merge auf Unterschlüssel).
- **Nicht Teil:** Roh/Einfach im Stundenverlauf (`O-SV-H/K-DARST`, `offen_feature`) → Phase 3 (#3058). Lese-Endpoint für den Editor → #3066. Renderer-Umstellung auf den Resolver → #3058.
- **Voraussetzung erfüllt:** Kommentar 1 verlangte, den Differenztest erst nach Merge der Nachlieferung aufzusetzen. PR #3068 (Stundenverlauf aus Grundauswahl) und #3072 (nie eingestellt = null, Trip bewusst leer) sind gemerged. Der Adapter bildet den Stand **nach** #3068 ab, nicht `HOURLY_DEFAULT_METRIC_IDS` als feste Vorgabe.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/channel_list_resolver.py` (208 Z.) | `MailViewModel` (frozen, Felder email/telegram/sms/premium_sms/layout_channels), `ChannelRow(metric_id, enabled, format, order)`, `_trip_view`, `_compare_view`. Hier kommen `outlook` und `hourly` dazu. |
| `src/output/renderers/compare_outlook_metric_ids.py` | Altpfad Ausblick: `_erbe_grundauswahl` (:151, gemeinsame Regel None/[]/Schnitt/Rückfall), `resolve_trip_outlook_metrics(dc, report_type)` (:201, Grundauswahl aus `allowed_metric_ids_for_report_type` + Folge `get_metrics_for_report_type` = #3047 T1), `resolve_compare_outlook_metrics(outlook_metrics, enabled_metrics)` (:239), `_kennungen_aus_renderer_ids` (:260), `resolve_trip_outlook_formats` / `resolve_compare_outlook_formats` (:280/:297, `{id: bool}` via `normalize_outlook_metric_formats`, None = alles Roh), `outlook_columns` (:313). |
| `src/output/renderers/compare_hourly_metric_ids.py` | Altpfad Stundenverlauf: `resolve_hourly_metrics(hourly_metrics, enabled_metrics)` (:170) → `dp_field`-Liste oder None; `_standard_aus_grundauswahl` (:227, #3047 H1), `_schnitt_mit_grundauswahl` (:249, Rückfall Vorgabemenge ∩ Basis), `HOURLY_DEFAULT_METRIC_IDS` (:114), `HOURLY_MERGE_ONLY_METRIC_IDS` (wind_direction). |
| `src/services/report_config_resolver.py` | `resolve_compare_render_options` (:257): ruft `resolve_hourly_metrics` (:307), `has_visible_hour_columns`-Abschaltung (:312), `resolve_channel_lists(display_config,"compare")` (:340), `resolve_compare_outlook_metrics` (:359) + `outlook_enabled`-Abschaltung bei `[]`, `resolve_compare_outlook_formats` (:377). Kandidat Adapter (Ausblick/Stunden aus dem View lesen). |
| `src/output/renderers/trip_report.py:223` | Trip-Ausblick EINMAL aus `_dc_uncollapsed` aufgelöst (`resolve_trip_outlook_metrics`). |
| `src/output/renderers/email/outlook.py:646-661` | `build_outlook_row`: Fallback-Auflösung Trip-Ausblick + Formate. |
| `src/app/models.py:921` | Verweis Ausblick-Kopplung; `allowed_metric_ids_for_report_type`, `get_metrics_for_report_type`. |
| `docs/adr/0121-kanonische-kanal-liste.md` | Punkt 1: `outlook`/`hourly` als Schlüssel **reserviert** für #3065; Punkt 7: Migration lazy, Resolver schreibt nie, neue Schlüssel erst mit Editor (#3060). Bekommt Nachtrag für 2b. |
| `docs/specs/modules/feat_3057_kanal_liste_resolver.md` | Spec-Muster (ACs) für Phase 2. |
| `tests/tdd/test_3057_channel_list_resolver.py` + `tests/helpers/kanal_liste_orakel.py` | Differenztest-Muster: Altpfad-Orakel, Kombinationen, Phase-1-Fixtures, Eingabe unverändert/eingefroren, kein Dateizugriff. |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` (Abschnitte AB/SV, Fälle `O-SV-*-H1-*`, `VO-14`), `fallliste_trip.json` (`trip-paar-ausblick-*`) | Messlatte laut Issue-Kommentar 1; müssen grün bleiben. |

## Existing Patterns

- **Resolver bündelt Primitive, schreibt keine Regel neu** (ADR-0097/0121): Trip-Kaskade über `_models._cascade_source_for_channel`, Orte über `resolve_channel_layout_rows`. Primitive werden zur Laufzeit am Modul nachgeschlagen, damit Mutationsproben wirken.
- **Eine Regel für beide Flächen:** `_erbe_grundauswahl` für Ausblick Trip und Orte; `_kennungen_aus_renderer_ids` als einzige Umkehrtabelle.
- **Zwei Vokabulare:** Ausblick liefert Katalog-Kennungen (`metric_id`), Stundenverlauf liefert Renderer-Feldnamen (`dp_field`), Orte-Kanäle Renderer-Kennungen. `ChannelRow.metric_id` muss je Liste festgelegt sein (Spec-Entscheidung).
- **None vs [] Semantik:** None = nie eingestellt / kein Filter (Renderer-Vorgabe), [] = bewusst leer (Block entfällt). Rückfall bei Totalschnitt ≠ leer (#1848 A3 AC-10).
- Orte-Ausblick-Klartext = HTML seit PR #3051; Trip-Folge ohne `outlook_metrics` = Editor-Position (T1).

## Dependencies

- Upstream: `app.models` (UnifiedWeatherDisplayConfig, Kaskaden-Primitive), `app.loader._parse_display_config`, `app.metric_catalog.normalize_outlook_metric_formats`, `compare_metric_ids.resolve_enabled_metrics`, `compare_metric_catalog`.
- Downstream: heute nur `report_config_resolver.resolve_compare_render_options` und `models.get_metrics_for_channel` (Adapter aus #3057). Renderer lesen Ausblick/Stunden weiter über die Altfunktionen (Umstellung #3058). Später #3066 (Endpoint), #3060 (UI), #3082 (Abwahl).

## Existing Specs / ADRs

- ADR-0121 (kanonische Kanal-Liste), ADR-0059 (Ausblick erbt Grundauswahl), ADR-0055 (Trip-Ausblick wählbar, keine Kanal-Ebene), ADR-0037, ADR-0050, ADR-0053 (abgelöst Punkt 1), ADR-0119 (Orte Default Roh).
- Specs: `feat_3057_kanal_liste_resolver.md`, `feat_3047_einstellung_gleich_mail_pruefkatalog.md`.

## Risks & Considerations

- **Report-Typ:** Trip-Ausblick hängt am `report_type` (Grundauswahl morning/evening) — Resolver bekommt ihn schon; Orte ohne Report-Typ.
- **Ungekollabierter Stand:** Trip-Ausblick muss gegen den kanal-neutralen Stand schneiden (Adversary F001 #1720) — ein enges `channel_layouts.email` darf den Ausblick nicht schneiden.
- **Format-Default Ausblick:** None = alles Roh (beide Flächen) — anders als Trip-Kanäle (Katalog-Standard). `ChannelRow.format` muss das ohne Mail-Änderung abbilden (z. B. `"simplified"` aus `{id: True}`, sonst `None`/`"raw"`).
- **Stundenverlauf None:** `resolve_hourly_metrics` liefert None (Renderer-Vorgabemenge) bei Altbestand ohne Grundauswahl; `hourly_enabled`-Abschaltung bei unsichtbaren Spalten passiert im Aufrufer, nicht in der Liste. Der View muss None/[]/Liste verlustfrei tragen.
- **Abschaltflags** `hourly_enabled`/`outlook_enabled` (Top-Level am Preset) sind nicht Teil von `display_config` — klären, ob der View sie abbildet oder bewusst draußen lässt.
- **Trip-Stundenverlauf** existiert nicht als eigene Liste (Haupttabelle = E-Mail-Liste) → `hourly` für Trip = nicht vorhanden (Feld None/fehlt), nicht leer.
- **Parallele Arbeit:** #3067 (Orte-Ausblick nach gescheitertem Speichern), #3048 (Trip-Altbestand) berühren benachbarten Code; vor Implementierung gegen origin/main abgleichen.
- `MailViewModel` ist frozen mit positionalen Feldern; neue Felder brauchen Default, damit bestehende Konstruktionen nicht brechen.

## Analysis

### Type
Feature (rein lesend, keine Mail-Änderung)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/channel_list_resolver.py` | MODIFY | `MailViewModel` + `outlook: Rows = None`, `hourly: Rows = None` (hinter `layout_channels`, beide Konstruktionen sind per Keyword); `_trip_view` füllt `outlook`, `hourly` bleibt None; `_compare_view` füllt beide, `global_metrics` wiederverwenden |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | `resolve_hourly_metrics` in ID-Stufe (Katalog-IDs, inkl. `_standard_aus_grundauswahl`/`_schnitt_mit_grundauswahl`) + dp_field-Schritt zerlegen; öffentliche Signatur/Rückgabe unverändert |
| `tests/helpers/kanal_liste_orakel.py` | MODIFY | Orakel für Ausblick/Stundenverlauf aus den Altfunktionen |
| `tests/tdd/test_3065_*.py` | CREATE | Differenztest + Fixtures + Eingabe-eingefroren + kein Dateizugriff |
| `docs/specs/modules/feat_3065_*.md` | CREATE | Spec mit ACs |
| `docs/adr/0121-kanonische-kanal-liste.md` | MODIFY | Nachtrag 2b (Vokabular, None-Vertrag, Abschaltflags draußen) |

### Scope Assessment
- Files: 6
- Estimated LoC: Produktivcode ca. +75/-5, Tests ca. +250, Doku ca. +80
- Risk Level: LOW (niemand liest `view.outlook`/`view.hourly` in dieser Scheibe; einziger Eingriff in Mail-Code ist der verhaltensgleiche Hourly-Split, abgesichert durch Differenztest)

### Technical Approach (Entscheidungen)
1. **Altfunktionen nur aufrufen, keine Regel neu schreiben** (ADR-0097/0121). Trip-Ausblick: `resolve_trip_outlook_metrics(dc, report_type)` auf dem Modell aus `_trip_model` = ungekollabiert (F001 #1720). Orte-Ausblick: `resolve_compare_outlook_metrics(outlook_metrics, global_metrics)`. Orte-Stundenverlauf: neue ID-Stufe von `resolve_hourly_metrics(hourly_metrics, global_metrics)`.
2. **Vokabular `metric_id`: Katalog-Kennung für beide neuen Listen.** Ausblick liefert sie schon; der Editor (#3066) speichert Katalog-IDs. Geprüft: unter den stündlich wählbaren IDs ist `dp_field` heute eindeutig (keine Kollision), trotzdem keine Rückübersetzungstabelle (wäre ein weiteres Vokabular) → ID-Stufe aus `resolve_hourly_metrics` herauslösen. Orte-Kanäle bleiben Renderer-Kennungen (bewusste, im ADR-Nachtrag dokumentierte Zwei-Vokabular-Lage).
3. **Format Ausblick = wirksamer Wert:** `normalize_outlook_metric_formats` (nur ausblick-fähige IDs); `True` → `"simplified"`, explizit `False` → `"raw"`, kein Eintrag/nicht fähig → `None` (Flächen-Standard = Roh). Stundenverlauf: `format` immer `None` (Roh/Einfach → #3058).
4. **None-Vertrag:** `outlook`/`hourly` = `None` heißt bei Orte „Renderer-Vorgabemenge“ (Altbestand ohne Grundauswahl), `()` = Block entfällt (bewusst leer bzw. leere Grundauswahl), sonst Zeilen. Trip `hourly` ist IMMER `None` = „Liste existiert nicht“ (Haupttabelle = E-Mail-Liste) — eigener AC + Test.
5. `wind_direction` (Merge-only) wird nicht weggefiltert, Zeile wie im Altpfad.
6. **Kein Adapter-Umbau** in `resolve_compare_render_options`/Trip-Renderer (→ #3058); sonst misst der Differenztest den Adapter gegen sich selbst. Abschaltflags `hourly_enabled`/`outlook_enabled` (Preset-Top-Level, nicht `display_config`) bleiben dokumentiert draußen.
7. **Tests:** Orakel analog test_3057 über Kombinationen `active_metrics` × `outlook_metrics` × `hourly_metrics` × formats je None/[]/Liste/Totalschnitt, `report_type` morning/evening; Trip-Fälle mit engem `channel_layouts.email` (darf Ausblick nicht schneiden) und Altbestand ohne `metrics`; Fixtures `fallliste_orte.json` (AB/SV, `O-SV-*-H1-*`, `VO-14`) und `fallliste_trip.json` (`trip-paar-ausblick-*`); Differenz `dp_field(ID-Stufe) == resolve_hourly_metrics` für den Split.

### Dependencies
Upstream: `app.models`, `app.loader._parse_display_config`, `app.metric_catalog` (`normalize_outlook_metric_formats`, `get_metric`), `compare_metric_ids.resolve_enabled_metrics`, `compare_metric_catalog`. Downstream unverändert (Renderer lesen weiter Altfunktionen). Vor Implementierung gegen origin/main abgleichen (#3067, #3048 Nachbarcode).

### Open Questions
- keine Produktfrage offen (rein lesend, Mail unverändert)
