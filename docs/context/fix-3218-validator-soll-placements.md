# Context: fix-3218-validator-soll-placements

## Request Summary
Das Validator-Soll (`--konfig` von `briefing_mail_validator.py` und `email_spec_validator.py`)
leitet die Darstellung Roh/Einfach nur aus Altfeldern ab (`metrics[].use_friendly_format`/
`format_mode`, `channel_layouts`) und ignoriert `display_config.placements.rows[].formats`.
Folge: Fehlalarm (12 SOLL-Verletzungen „soll Zahl (Roh) zeigen“) bei korrekt gerenderter
Mail, sobald Alt- und Neufelder auseinanderlaufen; nach Migration B6 (Altfelder weg) prüft
der Validator nur noch Standardwerte. Zusätzlich: `orte`-Hülle von
`email_spec_validator --konfig` dokumentieren (Mapping Kennung→Name; eine Liste → TypeError).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/_soll_aus_konfiguration.py` | Soll-Ableitung. Trip: `_modus` (Z. 225), `_formen_stunden` (Z. 298), `trip_soll` (Z. 492, `darstellung_stunden`, `formen_stunden`, `ausblick` über `outlook_metric_formats`). Orte: `_einfach_eintrag`/`_orte_einfach`/`_orte_formen` (Z. 612–685, aus `channel_layouts.email`), `orte_soll` (Z. 848, `ausblick` über `outlook_metric_formats`). Hülle: `soll_aus_daten` (Z. 927, `daten["orte"]` wird per `**` gemischt → Liste = TypeError) |
| `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py` | Verbraucher von `darstellung_*`/`formen_*`/`uebersicht_einfach`/`uebersicht_formen`/`ausblick.formen` |
| `src/services/placements.py` | Produktregel: `read_placements`, `_cell` (Z. 170: `fmt = row.format(stelle) or standard_form(mid)` nur an `zwei_formen_stellen`), `heutige_form` (Altpfad) |
| `src/app/metric_catalog.py` | Statisches Register: `zwei_formen_stellen` (Z. 1204), `standard_form` (Z. 1225), `AMPEL_METRIC_IDS`, `OUTLOOK_FRIENDLY_CAPABLE` |
| `src/services/channel_list_resolver.py` | `placements_view` (Z. 257): mit Tabelle gelten Auswahl, Folge UND Format aus `placements` (email/telegram/sms/outlook/hourly) |
| `docs/reference/mail_validators.md` | Validator-Doku (Abschnitt `--konfig`, Hülle, #3155-Ausnahme) |
| `tests/tdd/test_einstellung_gleich_mail_validatoren.py` (+ `_trip`, `_orte`, `_trip_tabelle`, `_orte_tabelle`) | Bestehende Kern-Tests des Soll |

## Existing Patterns
- Soll liest NUR rohes JSON + statisches Register, nie `resolve_*` des Produkts (Spiegel-Test-Verbot); einzige dokumentierte Ausnahme: `ausblick_briefings` (#3155) nutzt `services.placements`.
- `formats.<stelle>` ∈ `raw|simplified` nur an Stellen mit zwei Formen; fehlt = Katalog-Standard (`standard_form`), Trip und Orte gleich (Spec feat_3122 Teil A Nr. 1/4).
- Tabelle vorhanden ⇔ `read_placements(...)` ≠ None (`placements.rows` ist Liste); Helfer `_hat_tabelle` existiert bereits.

## Dependencies
- Upstream: `app.metric_catalog` (Register), `services.placements` (bereits importiert für Ausblick).
- Downstream: beide Mail-Validatoren (Staging-E2E-Nachweise, Deploy-Gates).

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` — Format der Tabelle, Auflösung, „eine Quelle“ Roh/Einfach
- `docs/specs/modules/feat_3156_renderer_nachzug_roh_einfach.md` — Renderer-Darstellung Roh/Einfach (Ampel HTML, Wortstufe Klartext)
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` — Soll-Regeln
- `docs/specs/modules/feat_3155_ein_name_ausblick.md` — Ausnahme vom resolve-Verbot

## Risks & Considerations
- Mit Tabelle bestimmt der Renderer auch Auswahl/Folge aus `placements`; das Soll liest Auswahl/Folge weiter aus den Altfeldern. Issue nennt nur Formate — in der Analyse entscheiden, ob Auswahl/Folge mitgezogen werden (sonst gleicher Fehlalarm nach B6) oder als eigenes Issue.
- Ampel-Ausnahme: im HTML hängt der Ampelpunkt bisher an `use_friendly_format`; mit Tabelle an `formats.email` (bzw. Standard).
- Ausblick-Formate: Tabelle `formats.outlook` vor `outlook_metric_formats`.
- Orte-Stundenverlauf (`formats.hourly`) prüft das Soll heute nicht auf Form — kein Scope-Zuwachs ohne Bedarf.
- Kein Spiegel: Soll darf `_cell`/`placements_view` nicht aufrufen; Ableitung aus Rohfeldern + `zwei_formen_stellen`/`standard_form` (Register).

## Analysis

### Type
Bug (Prüfwerkzeug: Fehlalarm des Validator-Solls bei Abos mit Tabelle `placements`).

### Root Cause (bestätigt)
Mit Tabelle kommt das View-Model des Renderers allein aus `placements_view` (`src/services/channel_list_resolver.py` `resolve_channel_lists`, `ALTBESTAND_UEBER_UMRECHNUNG = False`); Form je Zelle = `formats[stelle]` an `zwei_formen_stellen(mid)`, fehlend → `standard_form(mid)` (`placements._cell`); Abbildung auf `MetricConfig` über `helpers.mit_zeilen_format` (raw → `format_mode=raw`, `use_friendly_format=False`; simplified → `format_mode=simplified`, wenn der Katalog den Modus kennt, sonst Katalog-Standard scale/symbol, `use_friendly_format=True`). Das Soll (`_modus`, `_formen_stunden`, `_orte_einfach`, `_ausblick_spalten`) liest nur Altfelder.
Der Editor schreibt per `PUT /api/briefings/{id}/placements` nur `placements` (`internal/handler/placements.go`) → Alt- und Neufelder laufen auseinander.

### Scope-Entscheidung (Tech Lead)
- **#3218:** nur Darstellung Roh/Einfach (Trip Stundentabelle HTML/Klartext inkl. Ampel-Ausnahme, Orte Vergleichstabelle, Ausblick Trip+Orte) + `orte`-Hülle (Doku + klare Fehlermeldung statt TypeError bei Liste).
- **Auswahl/Reihenfolge mit Tabelle** → eigenes Issue **#3242** (Sub-Issue Epic #3122, Voraussetzung für #3237, dort kommentiert). Grund: verlangt Nachbildung von `_ordered_rows` (abgeleitete Größen, Sperren) bzw. eine resolve-Ausnahme — eigene Grundsatzfrage. Restlücke in `docs/reference/mail_validators.md` benennen.
- Orte-Stundenverlauf (`formats.hourly`): Soll prüft dort keine Form, bleibt so.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | Helfer `_form(dc, mid, stelle)` (nur bei `_hat_tabelle`; erste Zeile je `metric_id`; nur `zwei_formen_stellen`; Werte gefiltert wie `_read_row`: Stelle in FORMAT_STELLEN, Wert raw/simplified; sonst `standard_form`), `_modus_aus_form`, Überlagerung `_mit_tabelle(liste, dc)` → `format_mode`/`use_friendly_format` der E-Mail-Liste; Einbau in `trip_soll` (`darstellung_stunden`, `formen_stunden`, `wind_richtung`), `_orte_einfach` (Tabellenzweig), Ausblick-Formate in `trip_soll`/`orte_soll` (`formats.outlook` statt `outlook_metric_formats`); `soll_aus_daten`: `orte` als Liste → klare Fehlermeldung; Docstring-Kopf |
| `docs/reference/mail_validators.md` | MODIFY | `--konfig`: Quelle der Form (Tabelle vor Altfeldern, fehlend = Katalog-Standard), Restlücke Auswahl/Folge (#3242), `orte`-Hülle `{"preset": …, "orte": {"<Kennung>": "<Name>"}}` |
| `tests/tdd/test_einstellung_gleich_mail_soll_placements.py` | CREATE | Kern-Tests ohne Mock: Konflikt Altfeld vs. `placements` (Trip HTML/Klartext mit Ampel- und Nicht-Ampel-Größe, Orte, Ausblick), fehlendes `formats` = Standard, Müllwerte ohne Wirkung, Altbestand ohne Tabelle unverändert, Hülle-Liste → Fehlermeldung |

### Scope Assessment
- Files: 3
- Estimated LoC: +~70 Quelle, +~10 Doku, +~120 Tests / −~5
- Risk Level: LOW — betrifft nur das Prüfwerkzeug; alles hinter `_hat_tabelle`, Altbestand bytegleich (Vorher/Nachher über Fixtures `tests/fixtures/einstellung_gleich_mail/fallliste_*.json`).

### Technical Approach
Überlagerung statt neuer Zweige: die Einträge der E-Mail-Liste bekommen bei Tabelle `format_mode`/`use_friendly_format` aus `_form(dc, mid, "email")` (Abbildung wie `mit_zeilen_format`); `_formen_stunden`/`_modus`/`_wind_verschmolzen` bleiben unverändert und folgen damit automatisch (Ampel-Ausnahme hängt an `use_friendly_format`). Orte: `erste[m] = _form(dc, m, "email") == "simplified" and len(format_modes) > 1`. Ausblick: `{m: _form(dc, m, "outlook") == "simplified"}` für `_ausblick_spalten`. Kein Aufruf von `_cell`/`placements_view` (Spiegel-Verbot); Regel aus rohem JSON + Register (`zwei_formen_stellen`, `standard_form`).

### Risiken / Randfälle
- Abgeleitete Größen ohne eigene Zeile erben im Produkt die Formate der Eltern-Zeile (`_ordered_rows`); Soll ohne Zeile → `standard_form`. Mit Test prüfen; ggf. Eltern-Format über `_DERIVED_METRIC_RULES` (statisch) übernehmen.
- Windrichtung: `simplified` → `default_format_mode` (scale), sonst bricht `_wind_verschmolzen`.
- Doppelte `metric_id`: erste Zeile gilt.
- Bestehende Kern-Tests importieren das Soll nur in `tests/tdd/test_einstellung_gleich_mail_validatoren.py`; Fälle mit Tabelle + widersprüchlichen Altfeldern wechseln absichtlich zur Tabelle.

### Dependencies
`app.metric_catalog` (`zwei_formen_stellen`, `standard_form`, `AMPEL_METRIC_IDS`, Register), `services.placements` (nur `_hat_tabelle`, schon importiert). Verbraucher: beide Mail-Validatoren (Staging-E2E, Deploy-Gates).

### Abnahme
Staging-Fall aus #3156 (rain_probability `formats.email=simplified`, cloud_total ohne `formats`, Altfelder `use_friendly_format: false`): Validator meldet keine SOLL-Verletzung mehr.

### Open Questions
- keine (keine Produktentscheidung berührt; Scope-Teilung ist Tech-Lead-Entscheidung, Folge in #3242)
