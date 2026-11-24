---
entity_id: feat_3122_was_steht_wo
type: feature
created: 2026-11-17
updated: 2026-11-21
status: approved
version: "1.0"
tags: [issue-3122, adr-0124, epic-2791, epic-2795, was-steht-wo, resolver, speicherformat, orte, ausblick]
---

# Reiter Wetter: eine Tabelle „Was steht wo“ (Vertrag, Oberfläche, Texte)

## Approval

- [x] Approved
- PO-Freigabe 2026-11-17 (per Abfrage, Antwort „Freigabe“), einschließlich der zwei Abweichungen vom Soll-Bild bei Roh/Einfach (Gewitter nur in der E-Mail, Regenwahrscheinlichkeit kommt dazu). Lesefassung für den PO: https://claude.ai/artifact/HHRhCQGbTKnRi5Nvc3Hw87

## Purpose

Eine Tabelle „Was steht wo“ ersetzt im Reiter Wetter die Karte „Inhalt je Kanal und Fläche“, gleich für Trip und Orte ([ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md)). Diese Spec legt fest, wie die Auswahl gespeichert und aufgelöst wird (Teil A), wie die Karte aussieht und sich verhält (Teil B) und woran die Abnahme sie misst. Sie beantwortet alle in ADR-0124 und Issue #3122 als „offen für die Spec“ geführten Punkte.

## Source

- **Soll-Bild:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, Bilder `docs/context/einstellungen_neu/bilder-fassung4/`, Wortlaut `docs/context/einstellungen_neu.md` §5 Punkt 8
- **File (Naht):** `src/services/channel_list_resolver.py`
- **Identifier:** `resolve_channel_lists`, `MailViewModel`; neu `placements` (gespeichert), `placements_from_legacy` (Umrechnung), Organismus `WasStehtWoKarte`

> **Schicht-Hinweis:** Python-Core (`src/services/`, `src/app/metric_catalog.py`, `src/output/renderers/`, `api/routers/`), Go-API (`internal/handler/`, `internal/router/`), Frontend (`frontend/src/lib/components/organisms/wetter-tab/`, `molecules/`, `atoms/`).
>
> **Trip/Orte-Teilung:** Ein gespeichertes Format, ein Resolver, ein Endpoint-Paar, ein Organismus mit `context="route"|"vergleich"`. Orte-eigen bleibt nur die Spalte „Stundenverlauf“ (ADR-0097).
>
> **Mandantentrennung:** Lese- und Schreib-Endpoint der Tabelle und die Migration werden mit zwei verschiedenen Nutzern getestet; `user_id` kommt aus dem Auth-Kontext.
>
> **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS sind benannt. Die Premium-SMS bekommt den SMS-Text (ADR-0124 Nr. 8). Alarme steuert die Tabelle nicht (ADR-0124 Nr. 11).

## Scope

Die Spec gilt für den ganzen Bau zu #3122. Gebaut wird in Scheiben, jede mit eigenem Workflow, eigenem PR und Staging-Abnahme. Eine Scheibe erfüllt die ihr zugeordneten ACs; braucht ihr Workflow eine eigene Spec-Datei, zitiert diese die ACs von hier und ändert sie nicht.

| Scheibe | Inhalt | ACs |
|---|---|---|
| B1 | Speicherformat `placements`, Resolver-Eingang, Katalog-Quelle für Roh/Einfach und gesperrte Stellen | 1 bis 7, 10, 18, 19 |
| B2 | Lese- und Schreib-Endpoint der Tabelle, Beispielwerte und SMS-Budget aus dem echten Renderer (#3066 geht hierin auf) | 14 bis 17, 20 |
| B3 | Karte „Was steht wo“ im Reiter Wetter, Ergänzung der Design-Charter, Umschalten des Altbestands auf die Umrechnung | 11, 21 bis 33 |
| B4 | 3-Tages-Ausblick: eine steuernde Stelle, Morgen/Abend auch bei Orten, ein Name | 8, 9, 12, 34 |
| B5 | Name „Orte“ und Ein-Ort-Texte in Mail, Telegram, SMS; gemeinsam mit #2798 | 35 bis 37 |
| B6 | Schreibende Migration, Rückbau der Altfelder und Altpfade (#3102, #3036, #3020) | 13, 38 |
| B7 | Abnahme (#3037) | Definition of Done |

Abhängigkeiten: B1 → B2 → B3 → B6 → B7. B4 und B5 laufen nach B1 parallel zu B2/B3. #3101 (ein Vokabular) ist mit Teil A Nr. 2 entschieden und wird vor B2 gebaut.

## Estimated Scope

- **LoC:** je Scheibe 250 bis 500 (Code und Tests), in Summe rund 3 000; B3 und B6 mit `loc_limit_override`
- **Files:** rund 60 über alle Scheiben
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| [ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md) samt Nachtrag vom 2026-11-17 | ADR | verbindliche Entscheidung; weicht diese Spec ab, gilt das ADR |
| ADR-0050, 0055 Nr. 2, 0095, 0097, 0101, 0104, 0106, 0112, 0121 | ADR | Grundauswahl als Maximum, eine Ausblick-Auswahl, Kanal-Parität, ein Code, Read-Modify-Write, DE/EN, Alarm ab, Oberflächen-Scheiben, bisheriges Format |
| `src/services/channel_list_resolver.py` | module | Naht: Ausgaben lesen nur das View-Model |
| #3099, #3100 und die Folge-Issues „Ausgabe liest das View-Model“ | issues | Voraussetzung für B1: keine Ausgabe liest mehr an der Naht vorbei |
| `src/app/metric_catalog.py` | module | einzige Quelle für Roh/Einfach je Stelle und für gesperrte Stellen |
| `internal/handler/config_merge.go` (`mergeConfigMap`) | function | ersetzt Unterschlüssel von `display_config` als Ganzes; `placements` wird deshalb immer vollständig geschrieben |
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | component | Zieh-Sortierung (ADR-0024) |
| Prüfkatalog `tests/fixtures/einstellung_gleich_mail/` (#3047) | tests | Messlatte „Einstellung = Ausgabe“; Falllisten werden erweitert, nicht durch Einzeltests ersetzt |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py`, `_soll_aus_konfiguration.py` | validators | Staging-Nachweis mit `--konfig`; leiten das Soll künftig aus `placements` ab |
| `docs/context/einstellungen_neu/elementliste.json`, Abschnitt `was-steht-wo` | Elementliste | Abgleich Soll-Bild gegen Staging (ADR-0112) |

## Implementation Details

### Teil A: Vertrag

**1. Gespeichertes Format.** `display_config.placements`, für Trip und Orte gleich:

```json
"placements": {
  "version": 1,
  "rows": [
    {"metric_id": "wind",
     "places":  {"email": true, "telegram": true, "sms": false, "hourly": true, "outlook": true},
     "formats": {"email": "simplified", "telegram": "raw", "outlook": "raw"}}
  ],
  "outlook_reports": ["evening"]
}
```

- Die Reihenfolge ist die Listenposition. Sie gilt für alle Stellen.
- Stellen: `email`, `telegram`, `sms`, `hourly` (nur Orte), `outlook`. `premium_sms` ist reserviert für S9 (#2801) und wird bis dahin nicht gelesen.
- `places.<stelle>` fehlt = angehakt. `false` = bewusst abgewählt. Damit ist „später eingeschaltet“ von „abgewählt“ unterscheidbar (#3082).
- `formats.<stelle>` ∈ `raw | simplified`, nur für `email`, `telegram`, `hourly`, `outlook`. Fehlt der Wert, gilt der Katalog-Standard der Metrik, für Trip und Orte gleich.
- `outlook_reports` ⊆ `["morning", "evening"]`: in welchem Briefing der 3-Tages-Ausblick steht. Fehlt der Schlüssel, gilt die Vorbelegung aus Nr. 6.
- Go speichert `placements` ungeprüft (ADR-0077) und immer als vollständigen Stand. Der Resolver liest robust: unbekannte Metriken, Stellen und Formate haben keine Wirkung.
- Unverändert an ihrem heutigen Ort bleiben `hourly_enabled` (Orte), `show_stage_stats`, `show_yesterday_comparison`, `show_night_block`, `email_format` (Trip) und `telegram_style`.

**2. Zeilen-Kennung (#3101).** `metric_id` ist überall die Katalog-ID (`temperature`), auch bei Orten. Der Resolver weitet sie für die Orte-Ausgaben auf die Auswertungen der Grundauswahl auf (Temperatur: Höchstwert, dann Tiefstwert). Abgeleitete Größen ohne eigene Metrik-Zeile im Reiter Wetter folgen ihrer Eltern-Zeile: gleiche Haken, Platz direkt hinter ihr.

**3. Auflösung.** Für jede Stelle gilt dieselbe Regel:

1. Maximum ist die Grundauswahl (Trip `display_config.metrics`, Orte `display_config.active_metrics`). Eine Zeile zu einer Metrik außerhalb der Grundauswahl hat keine Wirkung. Keine Stelle fügt eine Metrik hinzu (ADR-0124 Nr. 1).
2. Eine Metrik der Grundauswahl ohne Zeile steht hinten und ist an allen ihren Stellen angehakt.
3. `hourly` und `outlook` gelten nur, wenn auch `email` gilt (ADR-0124 Nr. 4). Die gespeicherten Haken bleiben erhalten und wirken wieder, sobald die Metrik in die E-Mail zurückkommt.
4. Eine Stelle, an der die Metrik keine eigene Ausgabe hat, ist gesperrt (Nr. 5). Ein gespeicherter Haken wirkt dort nicht.
5. Leer bleibt leer: Sind an einer Stelle alle Haken entfernt, steht dort keine Metrik. Es gibt keinen Rückfall auf die Grundauswahl oder eine Vorgabemenge. Stundenverlauf und Ausblick entfallen dann als Block. Eine bewusst leere Grundauswahl ergibt ein Briefing ohne Metriken (feste Teile wie amtliche Warnungen bleiben). Nur ein Abo, dessen Grundauswahl nie eingestellt wurde, bekommt wie heute den Standardsatz seiner Vorlage.
6. Amtliche Warnungen sind keine gespeicherte Zeile. Sie stehen in E-Mail und Telegram zuerst, in SMS und Premium-SMS am Ende, und fallen beim Kürzen als Letztes weg.

**4. Roh/Einfach: eine Quelle.** Der Katalog führt je Metrik die Stellen mit zwei Formen. Nur dort gibt es einen Umschalter, nur dort wirkt ein gespeichertes Format. Die Liste ersetzt `format_modes` als Fähigkeits-Abfrage, `OUTLOOK_FRIENDLY_CAPABLE`, `_AMPEL_CAPABLE_METRIC_IDS`, `_FRIENDLY_AMPEL_METRIC_IDS`, `SMS_FORMAT_MODE_METRIC_IDS` und im Frontend `INDICATOR_MAP`, `outlookFriendlyCapability.ts` und `hourlyFriendlyMap.ts`.

| Metrik | E-Mail | Telegram | Stundenverlauf | 3-Tages-Ausblick | Einfach-Form |
|---|---|---|---|---|---|
| Wind, Böen, Niederschlag, Regenwahrscheinlichkeit | ja | ja | ja | ja | Ampelpunkt in der HTML-Mail, sonst Wortstufe |
| Bewölkung (gesamt, tief, mittel, hoch) | ja | ja | ja | ja | Symbol |
| Sonnenstunden | ja | ja | gesperrt | ja | Symbol bzw. Wortstufe |
| Windrichtung | ja | ja | nein (immer Kompass) | ja | Kompass, Roh = Grad |
| Gewitter | ja | nein | nein | nein | Ampelpunkt, nur in der HTML-Mail; in jedem Text steht das Stufenwort |
| alle übrigen | nein | nein | nein | nein | – |

Die SMS und die Premium-SMS haben keine Wahl. Wo eine Größe dort bisher zwei Formen hatte (Bewölkung), gilt fest die Form, die heute ohne Einstellung erscheint. Der Bau zieht die Renderer nach, wo sie hinter der Tabelle zurückbleiben: Wortstufe für Wind, Böen, Niederschlag und Regenwahrscheinlichkeit in der Nur-Text-Mail und im Trip-Telegram, Regenwahrscheinlichkeit in Orte-Übersicht und Orte-Telegram. Im Orte-Telegram trägt „Einfach“ bei Wind, Böen, Niederschlag und Regenwahrscheinlichkeit wie heute die Stunden-Marke `@h`; den Fall „Zahl mit Marke“ gibt es nicht mehr.

**5. Gesperrte Stellen.** Der Katalog führt je Metrik auch, an welchen Stellen sie eine eigene Ausgabe hat (heute verteilt auf `NO_HOURLY_COLUMN_METRIC_IDS`, `HOURLY_EXCLUDED_METRIC_IDS`, `VISIBILITY_GATE_IDS`, die anzeigbaren Auswertungen des Ausblicks und die SMS-Kürzel-Tabellen). Wo sie keine hat, zeigt die Tabelle einen Strich mit Grund statt eines Hakens. Gründe: „kein Stundenwert“ (z. B. Sonnenstunden im Stundenverlauf), „keine eigene Spalte“ (z. B. Tiefsttemperatur Nacht in der Stundentabelle der Trip-Mail), „kein Tageswert“ (Ausblick), „kein Kürzel“ (SMS). Wo die Ausgabe von einer Bedingung abhängt (Tiefsttemperatur Nacht in Telegram: nur abends), bleibt der Haken.

**6. 3-Tages-Ausblick: eine steuernde Stelle.** Der Ausblick steht im Briefing eines Typs genau dann, wenn der Typ in `outlook_reports` steht und mindestens eine Metrik dort gilt. Das gilt in jeder Ausgabe gleich: HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram, für Trip und Orte. `show_outlook`, `multi_day_trend_reports` (beide Fundorte), `outlook_enabled` und „leere Liste = aus“ entfallen als Steuerung. Die Kompakt-Mail ignoriert weiterhin die übrigen Block-Schalter (#722), den Ausblick steuert auch dort nur diese Stelle. Die Großwetterlage hängt allein an `show_stability`. Vorbelegung, wenn `outlook_reports` fehlt: `["evening"]`; ist beim Abo nur das Morgen-Briefing eingeschaltet, `["morning"]` (PO 2026-11-17).

**7. View-Model.** `MailViewModel` behält `email`, `telegram`, `sms`, `premium_sms`, `outlook`, `hourly` als Zeilen in Anzeigefolge; die Ausgaben bleiben dadurch unberührt. Neu:

- überall Katalog-IDs (Nr. 2); `None` kommt nicht mehr vor, `()` heißt „Stelle leer“ bzw. „Block entfällt“;
- `outlook` und `hourly` sind `()`, wenn der Block für diesen Briefing-Typ aus ist; kein Aufrufer liest Block-Schalter selbst;
- `rows`: alle Zeilen der Grundauswahl für die Tabelle, je Stelle mit Zustand `on | off | locked | not_in_email` (bei `locked` mit Grund) und Format `raw | simplified | null` (`null` = nur eine Form).

Der Resolver bekommt dafür neben `display_config` die Abo-Angaben, die er braucht: Fläche, Briefing-Typ, eingeschaltete Briefings, `hourly_enabled`.

**8. Altbestand und Migration.** Eine reine Funktion `placements_from_legacy` rechnet die Altfelder um. Sie ist die einzige Umrechnung: Der Resolver nutzt sie ab B3 für Abos ohne `placements`, die Tabelle zeigt ihr Ergebnis, und die schreibende Migration (B6) speichert es. Bis B3 lesen Abos ohne `placements` über den bisherigen Pfad; ein Differenztest hält beide Pfade zusammen.

- **Haken:** je Stelle die Metriken, die dort heute erscheinen (Trip `channel_layouts`, Orte `channel_layouts` vor `channel_active_metrics`, dazu `outlook_metrics`, `hourly_metrics`).
- **Format:** je Stelle die Form, die dort heute erscheint, ausdrücklich gespeichert. Für die E-Mail zählt die HTML-Mail. Orte ohne Angabe bekommen ausdrücklich `raw`.
- **Reihenfolge:** führend ist die heute wirksame Reihenfolge der SMS (PO 2026-11-17). Metriken, die in der SMS fehlen, folgen in der Reihenfolge von Telegram, dann E-Mail, dann Grundauswahl. Gibt es `channel_layouts_per_report`, zählt die Abend-Fassung.
- **Ausblick, Trip:** `outlook_reports` = `multi_day_trend_reports` (`report_config`, sonst `display_config`, sonst `["evening"]`). Bei `outlook_metrics: []` ist er aus. Bei `show_outlook: false` ist er aus und `show_stability` wird `false`, außer das E-Mail-Format ist Kompakt (dort war der Schalter gesperrt und ohne Wirkung).
- **Ausblick, Orte:** bei `outlook_enabled: false` oder `outlook_metrics: []` aus, sonst in jedem eingeschalteten Briefing (heutiges Verhalten).
- **Bewusste Änderungen der Ausgabe** (Preis aus ADR-0124, im Probelauf je Abo ausgewiesen): E-Mail und Telegram übernehmen die SMS-Reihenfolge; eine Ausblick- oder Stundenverlauf-Metrik, die nicht in der E-Mail steht, entfällt dort; die Nur-Text-Mail folgt bei Roh/Einfach der HTML-Mail; eine in der SMS abweichend gewählte Wolken-Form entfällt.
- **Schreibende Migration (B6):** Skript nach dem Muster `scripts/migrate_2792_profil_ampel.py`: Probelauf mit Bericht, Sicherung je Nutzer, Sperre, Read-Modify-Write mit Merge (ADR-0101), idempotent. Sie schreibt `placements` (bei `show_stability_off` zusätzlich `report_config.show_stability=false`); alles andere bleibt inhaltsgleich. Nachtrag 2026-11-21: Das Entfernen der Altfelder (`channel_layouts`, `channel_layouts_per_report`, `channel_active_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`, `multi_day_trend_reports`, `outlook_enabled`) ist verschoben, bis kein Leser mehr existiert (Frontend, Validator, Altpfad); Kind-Issue #3237 (setzt #3218 voraus). Bis dahin bleiben sie stehen. Umsetzung: `feat_3157_migration_placements.md`.
- **Nachtrag 2026-11-22 (Erstanlage und Altpfad-Rückbau, #3275/#3237, Spec `feat_3237_altpfad_entfernen.md`):** Jedes neue Abo (Trip und Orts-Vergleich) trägt ab der Anlage die volle Tabelle aus seiner Grundauswahl: je Metrik der Tabellen-Grundauswahl (Abend-Fassung, dahinter nur-morgens Gewähltes) eine Zeile; Haken und Form je Stelle sind ausdrücklich gespeichert und zeigen genau, was ohne Einstellung bisher erschien (Nr. 4, „Standardform“ = heutige Form): Trip alle Stellen an, Trip-HTML-Mail Ampelgrößen (Wind, Böen, Gewitter …) Einfach, sonst die Form aus dem Grundauswahl-Eintrag bzw. der Katalog-Standard, Ausblick Roh; Orte alle Stellen Roh, Kanäle an, Ausblick und Stundenverlauf nur für die bisherigen Vorgabemengen (nie eingestellte Grundauswahl: feste Ausblick-Spalten; Stundenverlauf: Grundauswahl soweit stündlich bzw. `HOURLY_DEFAULT_METRIC_IDS`). Einzige bewusste Änderung: `outlook_reports` nach der Vorbelegung (Nr. 6; Orte mit `outlook_enabled: false` = `[]`). Quelle ist allein `services.placements.placements_aus_grundauswahl`; die Go-Anlage fragt sie nach dem Speichern beim Kern ab (`GET /api/briefings/{id}/placements/erstanlage`) und schreibt sie per Read-Modify-Write. Ein Abo ohne `rows` wird überall (Versand, Karte, Validator, Soll-Hook) über dieselbe Funktion gelesen; Altfelder wirken nicht mehr. Die Umrechnung `placements_from_legacy`, das Begleitfeld `show_stability_off` und die Orte-Anlage-Marke (`placements` ohne `rows`) entfallen. Die Altfelder selbst bleiben bis #3277 in Bestandsdaten, Loader und Serialisierung.

**9. Endpoints (B2).** Unter der bestehenden Briefing-Route, für beide Flächen: `GET /api/briefings/{id}/placements?kind=route|vergleich` und `PUT` auf denselben Pfad. Go prüft den Nutzer, lädt das Abo und reicht an den Python-Core weiter.

- `GET` liefert Spalten, `rows` (Nr. 7) mit Namen, je Stelle einen Beispielwert, die Marken „passt nicht mehr“ (SMS) und „nur Tageswert“ (Trip-Telegram ab der achten Metrik), das SMS-Beispiel mit Zeichenzahl, `outlook_reports` und die Kürzel-Legende.
- Beispielwerte und SMS-Beispiel erzeugen dieselben Renderer-Funktionen wie der Versand, aus einem festen Beispiel-Datensatz ohne Wetterabruf. Nichts davon wird im Frontend nachgebaut.
- `PUT` nimmt den vollständigen Stand von `placements` und ändert nichts sonst (Read-Modify-Write im Handler, If-Match wie beim Abo).

### Teil B: Oberfläche und Texte

**10. Karte.** Organismus `WasStehtWoKarte` im Reiter Wetter zwischen „Amtliche Warnungen / Radar“ und „Anpassen“, `data-abschnitt="was-steht-wo"`, gebaut aus Bausteinen (ADR-0112). Neu als Bausteine: Haken, Roh/Einfach-Knopf, Einstell-Tabelle. Die Zieh-Sortierung nutzt `SortableList`. `docs/design-system/CHARTER.md` §3 bekommt eine vierte Ausnahme für das Tabellen-Layout: „Einstell-Tabelle ‚Was steht wo‘“. Beim Anlegen erscheint die Karte erst mit #3041.

**11. Aufbau, Wortlaut und Zustände** folgen dem Soll-Bild Fassung 4 und `einstellungen_neu.md` §5 Punkt 8: Kartentext, Spalten mit Unterzeile je Kontext, feste Zeile „Amtliche Warnungen“, Metrik-Zeilen mit Griff, Haken und Beispielwert, Roh/Einfach-Knopf, Marken, SMS-Beispiel mit Hinweissatz, „Ganze Blöcke ein- und ausschalten“, „Einstellungen je Kanal“. Namen, Kürzel und Spaltenköpfe kommen aus dem Katalog und `docs/reference/sms_format.md`, nie aus dem Mockup.

**12. Kürzel-Legende** (PO 2026-11-17): unter dem SMS-Beispiel ein aufklappbares Feld „Kürzel erklärt“ (EN „Abbreviations explained“), zu Beginn geschlossen. Inhalt: die Kürzel der Metriken mit Haken in der SMS-Spalte; `@14` = ab 14 Uhr gelb oder schlechter; die Kurzform amtlicher Warnungen (`!TS:H@14`, Stufen `L` gelb, `M` orange, `H` rot, `WG` Wind, `RA` Starkregen, `AV4` Lawinenstufe); `X?` = Warnquelle nicht erreichbar. In den Briefings steht keine Legende; der Satz „Die Legende steht auch am Ende jedes Briefings.“ entfällt. Die Elementliste wird um diesen Eintrag ergänzt (Besitzer-Vermerk mit Verweis auf diese Spec).

**13. Speichern.** Jede Änderung an Haken, Reihenfolge oder Roh/Einfach speichert die Tabelle über den Endpoint aus Nr. 9. „−“ im Reiter Wetter entfernt die Zeile der Metrik im selben Speichervorgang, „+“ hängt sie hinten an, überall angehakt. Die Schalter unter der Tabelle speichern an ihrem heutigen Ort; „3-Tages-Ausblick“ schreibt `outlook_reports`.

**14. Jede Einstellung genau einmal.** Mit B3 verschwinden aus dem Übergangsblock im Reiter Zustellung im selben Auslieferungsschritt: die Listen je Kanal, Stundenverlauf, Ausblick, Telegram-Kurzstil, Mehrtages-Trend, E-Mail-Format, Etappen-Kennzahlen, Vortag-Vergleich und Nacht-Stundentabelle. Dort bleiben bis #3036 nur die Schalter ohne Platz im Soll-Bild (siehe Known Limitations).

**15. Ausblick-Name (B4).** Der Block heißt in Oberfläche, HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram „3-Tages-Ausblick“ (EN „3-day outlook“), für Trip und Orte. „Mehrtages-Trend“, „3-Tages-Vorschau“ und „Ausblick“ als Blocktitel entfallen.

**16. Name „Orte“ und Ein-Ort-Texte (B5, gemeinsam mit #2798).** Zuschnitt: Diese Spec legt die Texte der Ausgaben fest; #2798 behält Reiter Orte, Anlegen mit einem Ort, Menü, Listen und die Untergrenze des Validators.

| Stelle | bisher | neu, mehrere Orte | neu, ein Ort |
|---|---|---|---|
| Mail-Kopf, Telegram-Kopf | ORTS-VERGLEICH | ORTE (EN LOCATIONS) | ORTE |
| Mail-Titel, Abo-Name im Fuß | Orts-Vergleich, Ortsvergleich | Orte (EN Locations) | Orte |
| Betreff | Wetter-Vergleich: {name} ({datum}) | Orte: {name} ({datum}) | Orte: {name} ({datum}) |
| Übersicht, Unterzeile | Alle Orte · gewählte Metriken | Alle Orte · gewählte Metriken | Gewählte Metriken |
| Stundenverlauf, Titel | Stundenverlauf · alle Orte | Stundenverlauf · alle Orte | Stundenverlauf |
| Fußzeile | {n} Orte · Vorlage {vorlage} | {n} Orte · Vorlage {vorlage} | 1 Ort · Vorlage {vorlage} |
| Knopf | Vergleich in App öffnen → | In der App öffnen → | In der App öffnen → |
| SMS-Anfang (PO 2026-11-17) | Vergleich 18.11.: | Orte 18.11.: Münster D 13C … | Tecklenburg 18.11.: D 11C … |
| SMS ohne Daten | Vergleich: keine Daten | Orte: keine Daten | {Ortsname}: keine Daten |

Die Tabelle „Übersicht“ steht auch bei genau einem Ort in der Mail (Soll-Bild „Orte · 1 Ort“). Der SMS-Anfang bleibt wie bisher sprachfest (ADR-0104). Mehrzahl-Texte bekommen `.one`/`.other`. Interne Bezeichner (`compare`, `vergleich`, Route `/compare`) bleiben.

## Expected Behavior

- **Input:** Abo (Trip oder Orte) mit Grundauswahl und `placements` oder mit Altfeldern; Briefing-Typ; Bedienung der Karte.
- **Output:** je Stelle genau die angehakten Metriken in der einen Reihenfolge und der je Stelle gewählten Form; die Karte zeigt denselben Stand, den das nächste Briefing ausliefert.
- **Side effects:** `PUT` schreibt `display_config.placements` des Abos dieses Nutzers. Die Migration (B6) schreibt einmalig alle Abos, mit Sicherung.

## Acceptance Criteria

**Teil A: Vertrag**

- **AC-1:** Given ein Trip und ein Orte-Abo mit gespeicherter Tabelle, in der je Metrik unterschiedliche Haken gesetzt sind / When Morgen- und Abend-Briefing erzeugt werden / Then steht in E-Mail, Telegram und SMS jeweils genau die Menge der dort angehakten Metriken in der einen Reihenfolge, und die Premium-SMS hat denselben Text wie die SMS.
  - Test: Kern-Schicht über den echten Renderer, Fälle in `fallliste_trip.json` und `fallliste_orte.json` (Auswahl × Reihenfolge × Stelle).

- **AC-2:** Given eine gespeicherte Zeile für eine Metrik, die nicht in der Grundauswahl steht / When ein Briefing erzeugt wird / Then erscheint diese Metrik an keiner Stelle, auch nicht in Stundenverlauf und 3-Tages-Ausblick.
  - Test: Briefing aller Stellen mit einer Zusatzzeile außerhalb der Grundauswahl, Trip und Orte.

- **AC-3:** Given ein Abo, in dem Böen in Telegram bewusst abgewählt sind / When der Nutzer später eine weitere Metrik in die Grundauswahl aufnimmt / Then steht die neue Metrik am Ende und an allen ihren Stellen, und Böen bleiben in Telegram abgewählt.
  - Test: Katalogfälle `trip-p7--*` und `O-p7--*` wechseln von `offen_feature` auf `gruen`.

- **AC-4:** Given eine Metrik mit Haken in Stundenverlauf und 3-Tages-Ausblick / When ihr Haken in der E-Mail entfernt wird / Then fehlt sie in Übersicht bzw. Stundentabelle, im Stundenverlauf und im Ausblick von E-Mail und Telegram, und nach erneutem Anhaken der E-Mail erscheint sie dort wieder wie zuvor.
  - Test: zugestellte Ausgabe vor, nach Abwahl und nach Wiederwahl, Trip und Orte.

- **AC-5:** Given Böen stehen in Telegram auf Roh und in der E-Mail auf Einfach / When das Briefing erzeugt wird / Then zeigt Telegram die Zahl und die E-Mail den Ampelpunkt (HTML) bzw. die Wortstufe (Nur-Text), und das Umschalten an einer Stelle ändert keine andere Stelle.
  - Test: echte Ausgabe je Stelle, Trip und Orte, HTML und Nur-Text.

- **AC-6:** Given die Liste „zwei Formen je Stelle“ im Katalog / When jede Metrik an jeder Stelle einmal mit Roh und einmal mit Einfach durch den echten Renderer läuft / Then unterscheidet sich die Ausgabe genau dort, wo die Liste zwei Formen nennt, und ist überall sonst gleich; ein gespeichertes Format an einer Stelle ohne zwei Formen und jedes Format für die SMS bleiben ohne Wirkung.
  - Test: parametrisiert über alle Metriken × Stellen × Trip/Orte; ersetzt die getrennten Fähigkeitslisten.

- **AC-7:** Given eine Metrik ohne eigene Ausgabe an einer Stelle (Sonnenstunden im Stundenverlauf, Tiefsttemperatur Nacht in der Stundentabelle der Trip-Mail) / When für sie dort ein Haken gespeichert ist / Then erscheint sie dort nicht, und die Tabelle meldet die Stelle als gesperrt mit Grund.
  - Test: Ausgabe und Tabellen-Antwort für jede im Katalog gesperrte Kombination.

- **AC-8:** Given ein Trip und ein Orte-Abo mit 3-Tages-Ausblick nur im Abend-Briefing / When Morgen- und Abend-Briefing in HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram erzeugt werden / Then steht der Ausblick abends in jeder dieser Ausgaben und morgens in keiner; werden beide Schalter ausgeschaltet, steht er nirgends.
  - Test: Falllisten `trip-paar-ausblick-*`, `trip-ausblick-aus--*`, `O-AB-*` um Morgen/Abend und alle Ausgabeformen erweitert.

- **AC-9:** Given ein neu angelegtes Abo ohne gespeicherte Ausblick-Einstellung / When Morgen- und Abend-Briefing eingeschaltet sind bzw. nur das Morgen-Briefing eingeschaltet ist / Then steht der Ausblick im ersten Fall nur im Abend-Briefing und im zweiten Fall im Morgen-Briefing, und die Karte zeigt die Schalter genauso.
  - Test: Briefing und Tabellen-Antwort für beide Fälle, Trip und Orte.

- **AC-10:** Given ein Abo, in dem an einer Stelle alle Haken entfernt sind, und ein Abo mit bewusst leerer Grundauswahl / When das Briefing erzeugt wird / Then steht an dieser Stelle keine Metrik, Stundenverlauf und Ausblick entfallen als Block, und es gibt keinen Rückfall auf eine andere Auswahl.
  - Test: Ausgabe je Stelle für „Spalte leer“ und „Grundauswahl leer“, Trip und Orte.

- **AC-11:** Given ein Bestands-Abo ohne gespeicherte Tabelle (Trip und Orte, mit und ohne eigene Kanal-Listen) / When die Tabelle live ist und das Briefing erzeugt wird / Then erscheint je Stelle dieselbe Menge an Metriken in derselben Form wie zuvor, die SMS ist bis auf eine abweichend gewählte Wolken-Form zeichengleich, und Abweichungen gibt es nur in den vier in Teil A Nr. 8 genannten Fällen.
  - Test: Golden-Dateien und Prüfkatalog; für jeden der vier Fälle ein benannter Fall mit erwarteter Änderung.
  - Nachtrag 2026-11-21, Prod-Probelauf (lesend): 21 Abos; 1 hat schon die Tabelle, 20 im Altformat (14 Trips, 6 Orts-Vergleiche); 0 unerklärt, 0 Fehler. Vorkommende bewusste Änderungen nur zwei: (a) `nur_text_folgt_html` bei 13 Trips (47 Einträge): die Nur-Text-Fassung der E-Mail zeigt Werte künftig in derselben Form (Roh/Einfach) wie die HTML-Mail; (b) `reihenfolge_wie_sms` bei 1 Trip (2 Einträge) und 3 Orts-Vergleichen (10 Einträge): E-Mail und Telegram übernehmen die Reihenfolge der SMS. Alle übrigen Änderungsarten kommen in Prod nicht vor. Die Freigabe dieser Zahlen erfolgt mit der Freigabe der Spec #3157.

- **AC-12:** Given Bestands-Trips mit `show_outlook: false`, mit `outlook_metrics: []`, mit Ausblick morgens und abends, und ein Orte-Abo mit `outlook_enabled: false` / When sie umgerechnet werden / Then ist der 3-Tages-Ausblick bei den ersten beiden und beim Orte-Abo aus, beim dritten in beiden Briefings an, und ein Trip mit `show_outlook: false` zeigt weiterhin keine Großwetterlage.
  - Test: Umrechnung und zugestellte Ausgabe je Fall, einschließlich Kompakt-Mail.

- **AC-13:** Given Bestandsdaten zweier Nutzer mit Altfeldern / When die Migration erst als Probelauf und dann schreibend läuft, danach ein zweites Mal / Then nennt der Probelauf je Abo die bewussten Änderungen, vor dem Schreiben liegt je Nutzer eine Sicherung, jedes Abo trägt danach `placements` und liefert dieselbe Ausgabe wie die Umrechnung, alle übrigen Felder sind unverändert, kein Abo des einen Nutzers enthält Daten des anderen, und der zweite Lauf ändert nichts.
  - Test: Migration auf einer Kopie realistischer Daten zweier Nutzer, Dateivergleich vor/nach.

- **AC-14:** Given ein Abo mit gespeicherter Tabelle / When die Tabelle gespeichert wird, danach das Abo über den Reiter Wetter, den Reiter Zustellung und durch den Python-Core gespeichert wird / Then ändert das Speichern der Tabelle nur `placements`, und jedes der anderen Speichern lässt `placements` unverändert.
  - Test: Go- und Python-Speicherwege gegen eine echte Abo-Datei, Trip und Orte.

- **AC-15:** Given zwei Nutzer A und B mit je einem Trip und einem Orte-Abo / When A die Tabelle von B liest oder speichert / Then wird beides abgewiesen, und eine Änderung von A an seiner eigenen Tabelle ändert weder Daten noch Briefing von B.
  - Test: Go-Handler-Test mit zwei Nutzern für GET und PUT, beide Flächen.

- **AC-16:** Given ein Abo mit Grundauswahl und teils abgewählten Metriken / When die Karte die Tabelle abruft / Then enthält die Antwort jede Metrik der Grundauswahl in der einen Reihenfolge, je Stelle den Zustand (an, aus, gesperrt mit Grund, nicht in der E-Mail), wo vorhanden die gewählte Form, einen Beispielwert je Stelle und beim Trip ab der achten Telegram-Metrik die Marke „nur Tageswert“.
  - Test: Endpoint-Antwort für Trip, drei Orte und einen Ort.

- **AC-17:** Given ein Trip, ein Abo mit drei Orten und eines mit einem Ort, deren Metriken nicht alle in 160 Zeichen passen / When die Tabelle abgerufen und mit demselben Datensatz eine SMS über den Versandweg erzeugt wird / Then ist das SMS-Beispiel der Tabelle zeichengleich mit der versandten SMS, die Zeichenzahl stimmt, und genau die Metriken, die in der SMS fehlen, tragen „passt nicht mehr“.
  - Test: Kern-Schicht, derselbe Datensatz durch Endpoint und Versandweg.

- **AC-18:** Given ein Abo mit eingeschalteten amtlichen Warnungen und eine aktive Warnung / When das Briefing erzeugt und die Tabelle abgerufen wird / Then steht die Warnung in E-Mail und Telegram zuerst und in SMS und Premium-SMS am Ende, die Tabelle zeigt sie als feste Zeile ohne Abwahl, und bei ausgeschalteten Warnungen fehlt die Zeile.
  - Test: Ausgabe aller vier Kanäle und Tabellen-Antwort, Warnungen an und aus.

- **AC-19:** Given Böen sind in der E-Mail-Spalte abgewählt und haben „Alarm ab Gelb“ / When ein Böen-Alarm auslöst / Then nennt die Alarm-Mail die Böen, und bei eingeschaltetem Telegram-Kurzstil bekommt Telegram den SMS-Text des Alarms.
  - Test: neuer Fall im Prüfkatalog (#3047), bestehende Alarm-Kettentests bleiben grün.

- **AC-20:** Given ein Nutzer hat die Tabelle geöffnet und das Abo wurde inzwischen an anderer Stelle geändert / When er die Tabelle speichert / Then wird nichts überschrieben, die Karte meldet den Konflikt und lädt den aktuellen Stand.
  - Test: PUT mit veraltetem Stand, Go-Handler und Browser.

**Teil B: Oberfläche und Texte**

- **AC-21:** Given der Reiter Wetter eines Trips, eines Abos mit drei Orten und eines mit einem Ort auf Staging / When die Karte „Was steht wo“ mit dem Soll-Bild Fassung 4 abgeglichen wird / Then besteht der Elementlisten-Abgleich für den Abschnitt `was-steht-wo` mit `--strict` in Deutsch und Englisch, und der Prüf-Agent hat nach höchstens zwei Runden keinen offenen Befund.
  - Test: `npm run elementliste:abgleich -- --scope wetter --strict`, danach `--sprache en`; `mockup-bildpruefer` mit Mockup- und Staging-Bild.

- **AC-22:** Given die Karte beim Trip und bei Orten / When sie angezeigt wird / Then hat der Trip die Spalten E-Mail („Stundentabelle“), Telegram, SMS („und Premium-SMS“) und 3-Tages-Ausblick, Orte haben zusätzlich Stundenverlauf („nur E-Mail“) und bei der E-Mail die Unterzeile „Übersicht“, und eine Spalte Premium-SMS gibt es nicht.
  - Test: Browser-Test Trip, drei Orte, ein Ort.

- **AC-23:** Given die Karte eines Abos / When der Nutzer einen Haken entfernt, die Seite neu lädt und ein Test-Briefing schickt / Then ist der Haken weiterhin entfernt, und die Metrik fehlt genau an dieser Stelle im zugestellten Briefing.
  - Test: Browser-Test plus Staging-Validator mit `--konfig` (Trip `briefing_mail_validator.py`, Orte `email_spec_validator.py`).

- **AC-24:** Given die Karte mit mindestens drei Metriken / When der Nutzer eine Zeile am Griff an eine andere Stelle zieht oder sie per Tastatur verschiebt und neu lädt / Then steht die Zeile am neuen Platz, und das nächste Briefing zeigt die neue Reihenfolge in E-Mail, Telegram und SMS.
  - Test: Browser-Test mit Maus und Tastatur, Ausgabe aller drei Kanäle.

- **AC-25:** Given die Karte eines Trips und eines Orte-Abos / When sie angezeigt wird und der Nutzer bei Wind in der E-Mail von Roh auf Einfach schaltet und neu lädt / Then gibt es den Knopf nur an Stellen mit gesetztem Haken und zwei Formen, nie in der SMS-Spalte, der Wert steht nach dem Laden, und die Knöpfe der anderen Stellen sind unverändert.
  - Test: Browser-Test Trip und Orte.

- **AC-26:** Given eine Metrik ohne Haken in der E-Mail, Sonnenstunden bei Orten und ein ausgeschalteter Block / When die Karte angezeigt wird / Then zeigen Stundenverlauf und 3-Tages-Ausblick für die erste einen Strich mit „nicht in der E-Mail“, Sonnenstunden im Stundenverlauf einen Strich mit „kein Stundenwert“, und die Haken der Spalte des ausgeschalteten Blocks sind nicht bedienbar.
  - Test: Browser-Test der drei Zustände.

- **AC-27:** Given ein Abo, dessen Metriken nicht alle in die SMS passen / When die Karte angezeigt wird / Then tragen die überzähligen Metriken in der SMS-Spalte „passt nicht mehr“, darunter steht das SMS-Beispiel mit „{n} von 160 Zeichen“ und der Hinweissatz in der Fassung für mehrere Orte bzw. für Trip und einen Ort, und nach dem Hochziehen einer Metrik ändern sich Marken und Beispiel entsprechend.
  - Test: Browser-Test Trip, drei Orte, ein Ort.

- **AC-28:** Given ein Trip mit mehr als sieben Telegram-Metriken / When die Karte angezeigt und der Telegram-Kurzstil eingeschaltet wird / Then steht ab der achten Metrik „nur Tageswert“, und mit Kurzstil trägt die Telegram-Spalte die Unterzeile „Kurzstil: wie SMS“ und ihre Haken sind nicht bedienbar.
  - Test: Browser-Test; zugestelltes Telegram zeigt mit Kurzstil den SMS-Text.

- **AC-29:** Given die Schalter unter „Ganze Blöcke ein- und ausschalten“ / When der Nutzer bei Orten den Stundenverlauf, beim Trip Etappen-Kennzahlen, Vortag-Vergleich und Nacht-Stundentabelle und bei beiden den 3-Tages-Ausblick für Morgen und Abend schaltet / Then steht jeder Schalter nach dem Neuladen wie gesetzt, und der Block fehlt bzw. erscheint im zugestellten Briefing entsprechend.
  - Test: Browser-Test plus Staging-Validator mit `--konfig`.

- **AC-30:** Given der Hub eines Trips und eines Orte-Abos nach Auslieferung der Karte / When Reiter Wetter und Reiter Zustellung durchgesehen werden / Then gibt es E-Mail-Format (nur Trip), Telegram-Kurzstil und den Hinweis zur Premium-SMS genau einmal, nämlich unter der Tabelle, der Kurzstil ist ohne verbundenes Telegram gesperrt, und Roh/Einfach und Kurzstil waren zu keinem Auslieferungsstand unerreichbar.
  - Test: Browser-Test über beide Reiter; derselbe Test läuft vor und nach dem Umschalten grün.

- **AC-31:** Given die Karte mit Haken in der SMS-Spalte / When der Nutzer „Kürzel erklärt“ aufklappt / Then stehen dort die Kürzel genau der Metriken mit SMS-Haken, die Zeitangabe, die Kurzform amtlicher Warnungen mit ihren Stufen und „X?“, das Feld ist beim Öffnen der Seite geschlossen, und der Satz über eine Legende am Ende jedes Briefings steht nirgends.
  - Test: Browser-Test, Deutsch und Englisch.

- **AC-32:** Given der Reiter Wetter / When der Nutzer über „+“ eine Metrik aufnimmt und über „−“ eine andere entfernt / Then erscheint die neue Metrik als letzte Zeile der Tabelle mit allen Haken und der Meldung „… ist jetzt im Briefing und in jedem Kanal angehakt …“, und die entfernte Metrik steht nicht mehr in der Tabelle.
  - Test: Browser-Test Trip und Orte; `test_einstellung_gleich_mail_editor_standard.py` und `fallliste_editor.json` bleiben die Messlatte.

- **AC-33:** Given die Karte auf einem Handy mit 390 Pixel Breite und in englischer Sprache / When sie bei Orten mit fünf Spalten angezeigt wird / Then ist jede Spalte erreichbar, ohne dass die Seite seitlich scrollt, alle Texte stehen in Englisch, die Kürzel sind unübersetzt, und jeder Text erfüllt den Kontrast nach WCAG AA.
  - Test: Browser-Test bei 390 px, Paritätstest der Kataloge, Kontrastprüfung.

- **AC-34:** Given ein Trip und ein Orte-Abo mit eingeschaltetem Ausblick / When das Briefing als HTML-Mail, Nur-Text-Mail, Kompakt-Mail und Telegram zugestellt wird und die Oberfläche durchgesehen wird / Then heißt der Block überall „3-Tages-Ausblick“ (Englisch „3-day outlook“), und kein Text sagt „Mehrtages-Trend“ oder „3-Tages-Vorschau“.
  - Test: Staging-Validatoren Trip und Orte; Suche über die Kataloge.

- **AC-35:** Given ein Orte-Abo mit drei Orten / When Briefing-Mail, Telegram und SMS zugestellt werden, in Deutsch und Englisch / Then steht im Kopf „ORTE“ bzw. „LOCATIONS“, die SMS beginnt mit „Orte TT.MM.:“, und kein Text enthält „Vergleich“, „Orts-Vergleich“ oder „Orts-Briefing“.
  - Test: `email_spec_validator.py` auf Staging, Kern-Schicht für Telegram und SMS.

- **AC-36:** Given ein Orte-Abo mit genau einem Ort / When Briefing-Mail, Telegram und SMS zugestellt werden / Then enthält die Mail die Tabelle „Übersicht“ mit den Tageswerten des Orts, kein Text sagt „alle Orte“ oder „1 Orte“, die Fußzeile sagt „1 Ort“, und die SMS beginnt mit dem Namen des Orts und dem Datum.
  - Test: Ein-Ort-Fall im Validator (mit #2798) und in der Kern-Schicht.

- **AC-37:** Given die Karte eines Orte-Abos mit einem Ort / When sie angezeigt wird / Then steht beim Stundenverlauf „Stunden-Tabelle unter der Übersicht, nur in der E-Mail.“ ohne „je Ort“, und das SMS-Beispiel beginnt mit dem Namen des Orts.
  - Test: Browser-Test im Kontext „ein Ort“.

- **AC-38:** Given alle Abos sind migriert / When Altfelder nachträglich in ein Abo geschrieben werden und das Briefing erzeugt wird / Then haben sie keine Wirkung auf irgendeine Ausgabe, und die Oberfläche bietet keine Bedienung mehr für sie.
  - Test: Ausgabe mit und ohne nachträglich gesetzte Altfelder ist gleich; Rückbau der Bausteine in #3036 und #3020.
  - Nachtrag 2026-11-23: Der Ortsvergleich-Teil der Oberfläche ist mit #3276 erledigt (Anlegen und Speichern senden keine Altschlüssel mehr, die Bedienflächen Stundenverlauf und Ausblick sind entfernt); offen bleiben der Trip-Pfad (#3297) sowie Typen und Sperrtest (#3298).

## Definition of Done

- Jede Scheibe: ihre ACs durch benannte Tests grün, Adversary mit Mutations-Gegenprobe ohne offenen Befund, alle sechs CI-Checks grün, Staging-Verifikation, Prod-Selftest.
- Scheiben mit Mail-Inhalt: zuständiger Validator gegen echt zugestellte Staging-Mail grün.
- B3: Elementlisten-Abgleich `--strict` in DE und EN, Prüf-Agent höchstens zwei Runden.
- Mit dem Bau nachgezogen: `api_contract.md`, `renderer_email_spec.md`, `telegram_format.md`, `sms_format.md`, `mail_validators.md`, Glossar, `CHARTER.md`.
- Abnahme (#3037): Soll/Ist-Bild gegen Fassung 4, „Einstellung = Ausgabe“ (#3047), Handy am Gerät.

## Test Plan

- **Kern-Schicht (ohne Netz):** Resolver und Umrechnung über die erweiterten Falllisten des Prüfkatalogs; Roh/Einfach-Matrix parametrisiert (AC-6); SMS-Beispiel gegen Versandweg (AC-17); Go-Handler mit zwei Nutzern (AC-15); Speicherwege (AC-14); Migration auf Datenkopie (AC-13).
- **Frontend:** Baustein-Tests, Browser-Tests der Karte (AC-22 bis AC-33, AC-37), `bausteine_waechter`, Paritätstest DE/EN.
- **Staging:** Validatoren mit `--konfig` (AC-23, AC-29, AC-34 bis AC-36), Elementlisten-Abgleich und Prüf-Agent (AC-21).
- **Mutations-Gegenprobe:** je Scheibe; Pflichtfälle: Haken einer Stelle wird ignoriert, `hourly`/`outlook` ohne E-Mail-Bindung, Rückfall bei leerer Stelle, Reihenfolge einer Stelle weicht ab, Format der falschen Stelle wird gelesen, `outlook_reports` wirkt in einer Ausgabe nicht.

## Out of Scope

- Eigene Auswahl der Premium-SMS: S9, #2801.
- Tabelle schon beim Anlegen: #3041.
- E-Mail-Format „Kompakt“ und gemeinsame Zusatzblöcke für Orte: #3059.
- Reiter Orte, Anlegen mit einem Ort, Menü, Listen, Untergrenze des Validators: #2798.
- Übergangsblock auflösen und `WeatherMetricsTab` entfernen: #3036, #3020 (Voraussetzung: B3 live).
- Alarme: nichts zu bauen (ADR-0124 Nr. 11), nur der Prüfkatalog-Fall aus AC-19.

## Affected Files

| Scheibe | Dateien (Schicht) | Änderung |
|---|---|---|
| B1 | `src/services/channel_list_resolver.py`, neu `src/services/placements.py`, `src/app/metric_catalog.py`, `src/output/renderers/email/helpers.py`, `comparison.py`, `compare_metric_ids.py`, `compare_outlook_metric_ids.py`, `compare_hourly_metric_ids.py` (Python-Core); `.claude/hooks/_soll_aus_konfiguration.py` | Format lesen, Umrechnung, eine Katalog-Quelle, Renderer-Nachzug Roh/Einfach |
| B2 | neu `api/routers/placements.py`, `src/services/placements_view_service.py` (Python-Core); `internal/handler/placements.go`, `internal/router/router.go` (Go-API) | Endpoint-Paar, Beispielwerte, SMS-Budget |
| B3 | neu `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` samt Bausteinen unter `molecules/` und `atoms/`, `WetterTabInhalt.svelte`, `shared/wetter-tab/wetterTabSpeicherung.ts`, `shared/weather-metrics-tab/weatherMetricsTabSections.ts`, `organisms/zustellung-tab/KanalStil.svelte`, Kataloge `i18n/messages/{de,en}/wetter.json` (Frontend); `docs/design-system/CHARTER.md` | Karte, Speichern, Übergangsblock kürzen, Texte |
| B4 | `src/services/report_config_resolver.py`, `trip_report_scheduler.py`, `scheduler_dispatch_service.py`, `src/output/renderers/email/{html,plain,compact,outlook}.py`, `narrow.py`, Kataloge `src/i18n/messages/{de,en}/{mail,telegram,vergleich}.json` (Python-Core); beide Mail-Validatoren | eine steuernde Stelle, ein Name |
| B5 | `src/output/renderers/email/compare_html.py`, `comparison.py`, Kataloge `src/i18n/messages/{de,en}/{vergleich,versand,warnung,alarm}.json` (Python-Core); `email_spec_validator.py`; `docs/reference/sms_format.md` | Name „Orte“, Ein-Ort-Texte, SMS-Anfang |
| B6 | neu `scripts/migrate_3157_placements.py`; Rückbau in `src/app/models.py`, `src/app/loader.py`, `src/services/report_config_resolver.py` und den Altbausteinen des Frontends | Migration, Altpfade entfernen (Rückbau: Kind-Issue #3237) |

## Known Limitations

- **Schalter ohne Platz im Soll-Bild:** Kurz-Zusammenfassung, Quick-Take-Chips, Metriken-Überblick, Großwetterlage, Zusammenfassung und die Tages-Summe der Trip-Mail stehen weder im Soll-Bild noch im Konzept. Sie bleiben bis #3036 im Übergangsblock bedienbar und wirken unverändert. Was aus ihnen wird, ist eine Produktfrage für #3036.
- **SMS-Schwellen** (nur Trip) sind seit der Profil-Ampel ohne Wirkung und laut Konzept W13 entfallen. Sie bekommen keine Oberfläche; die gespeicherten Werte bleiben unberührt.
- **Grundauswahl je Briefing-Typ** (`morning_enabled`/`evening_enabled` je Metrik) wird wie heute ausgewertet, hat aber keine Bedienung in der Tabelle.
- **Telegram-Kurzstil** liegt beim Trip in `report_config`, bei Orten in `display_config`. Das bleibt so; die Karte bedient beide über einen Schalter.
- **SMS-Beispiel:** Es entsteht aus einem festen Beispiel-Datensatz. Die echte SMS ist je nach Wetter kürzer oder länger; die Marke „passt nicht mehr“ gilt für das Beispiel.
- **Handy:** Fünf Spalten mit Umschaltern sind bei Orten eng (ADR-0124, Preis). AC-33 sichert die Bedienbarkeit, die Abnahme am Gerät folgt in #3037.
- **Zwischen B1 und B3** lesen Abos ohne `placements` über den bisherigen Pfad. Erst mit B3 gilt die eine Reihenfolge für alle.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Nachtrag 2026-11-17 mit den Festlegungen dieser Spec)
- **Rationale:** ADR-0124 hat die Tabelle, die eine Reihenfolge und den Neuschnitt des gespeicherten Formats entschieden und die Einzelheiten ausdrücklich dieser Spec überlassen. Der Nachtrag hält die vier Entscheidungen des PO vom 2026-11-17 (SMS-Anfang, Kürzel-Legende, Vorbelegung des Ausblicks, führende Reihenfolge) und die technischen Festlegungen fest. Keine frühere Entscheidung wird dadurch still geändert.

## Changelog

- 2026-11-17: Erste Fassung (Teil A „Vertrag“ und Teil B „Oberfläche und Texte“), offene Punkte aus ADR-0124 und #3122 entschieden.
- 2026-11-17: Vom PO freigegeben.
- 2026-11-21: Nachtrag Prod-Probelauf (AC-11) und Verschiebung der Altfeld-Entfernung (Nr. 8, #3237).
- 2026-11-22: Nachtrag Erstanlage mit voller Tabelle und Rückbau des Altpfads im Backend (Nr. 8, #3275/#3237).
- 2026-11-23: Nr. 12 / AC-31 (Kürzel-Legende) präzisiert durch #3284: Sind Tages-Tief und Tages-Hoch mit SMS-Haken gewählt, steht in der Legende nur das Bereichs-Kürzel `D` bzw. `FD` mit „Tagestiefstwert/Tageshöchstwert“ (bzw. gefühlt); `L` und `FL` entfallen dort, weil die SMS sie als Bereich `D13/27` sendet. Nur Tiefstwert gewählt: `L` bleibt. Details: `docs/specs/modules/fix_3284_legende_bereich_ohne_l.md`.
- 2026-11-24: Nachtrag #3036 (Übergangsblock aufgelöst): Kurz-Zusammenfassung und Großwetterlage haben eigene Schalter unter „Ganze Blöcke ein- und ausschalten“ (nur ausführliche Mail, bei Kompakt gesperrt). Die übrigen Schalter ohne Platz im Soll-Bild bleiben ohne Oberfläche. Details: `docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md`.
