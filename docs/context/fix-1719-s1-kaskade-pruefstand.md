# Kontext — #1719 Scheibe 1: Kaskaden-Festlegung + Prüfstand

> Erhoben 2026-08-11. Prod-Commit zum Messzeitpunkt: `64b78c63`.
> Alle Zahlen unten sind **gemessen**, nicht hergeleitet — Messbefehle jeweils genannt.

## 1. Anlass

Trip **KHW `5f534011`** (Nutzer `henning`, Produktion) lieferte eine Kurzform, die Metriken
enthielt, die im SMS-Reiter **abgewählt** waren:

```
E4: FK10 FD21 R- PR55%@15(88%@17) W16@16 G22@6(26@17) TH:L@11(H@18) TH+:L@10
    HU85@20 WDN CT100@5 CL65@13 VS18.9@18 UV5@12 NL4070@12 WC10
```

136 Zeichen bei Grenze 160 ⇒ **keine Kürzung**; das Fehlen von `SL` ist also kein Platzproblem.

## 2. Die entscheidende Messung

Quelle: `/var/lib/gregor/users/henning/briefings/5f534011.json` (Lesepfad laut
[[reference_staging_trip_read_path_briefings_not_trips]] — **nicht** `trips/`, die ist tot).

Die Datei enthält **zwei einander widersprechende Ebenen**:

| Ebene | JSON-Feld | Einträge | `wind_chill` |
|---|---|---|---|
| Grundauswahl (global) | `display_config.metrics` | 26, davon **15 aktiv** | **AN** |
| SMS-Kanal-Layout | `display_config.channel_layouts.sms` | 26, davon **13 aktiv** | **AUS** |

**Abgleich der gelieferten Token gegen beide Listen:**

- gegen `channel_layouts.sms` → **passt nicht** (`FK`, `FD`, `WC` dürften nicht erscheinen)
- gegen `metrics` (global) → **passt exakt**, Kürzel für Kürzel, inklusive Reihenfolge

Global aktiv sind 15: `cape` (nicht renderbar, `selectable=False`), `cloud_low`, `cloud_total`,
`freezing_level`, `gust`, `humidity`, `precipitation`, `rain_probability`, `snowfall_limit`,
`thunder`, `uv_index`, `visibility`, `wind`, **`wind_chill`**, `wind_direction`. Das ergibt
genau die beobachteten Token; `SL` fehlt, weil im August real keine Schneefallgrenze vorliegt.

**Die Reihenfolge der gelieferten Token entspricht 1:1 `POSITIONAL`** (`tokens/builder.py:78`),
nicht der Nutzer-`order`. Konsistent damit, dass bei Kaskadenquelle `global` die Positionen
bewusst nicht angewendet werden (#1677 DEC).

## 3. Was der heutige Code mit dieser Datei tut

Gegenprobe mit dem **echten Loader** auf die **echte Datei**:

```
_parse_display_config(khw["display_config"])
  → per_channel_layouts: ['sms']   per_report_layouts: None   metrics: 26
  → cascade_source_for_channel("sms", "evening") == 'per_channel'
  → 13 aktive Metriken, wind_chill NICHT dabei
```

Und durch den **echten Renderpfad** (`TripReportFormatter().format_email(...).sms_text`):

```
E7: W12@4(45@10) WD- R0.5@5(8.4@11) PR40%@5(95%@11) TH:M@11 TH+:- G22@4(70@10)
    VS- CL- CT50@4 SL1800 UV- HU55@4 NL-
```

⇒ **korrekt**: genau die 13 gewählten Größen, genau in der Nutzer-Reihenfolge.

**Wichtige Einschränkung, die in der Spec stehen muss:** Die Trip-Datei wurde am 2026-08-11 um
**05:53 UTC** geschrieben, das Morgen-Briefing lief um **05:00 UTC** (07:00 Ortszeit). Der
Konfigurationsstand zum Sendezeitpunkt ist damit **nicht rekonstruierbar**. Die Aussage „der
Renderer ist in Ordnung" gilt für den **jetzigen** Dateizustand, nicht für den Sendezeitpunkt.
Der Konstruktionsfehler (zwei Ebenen ohne definierte Beziehung) besteht unabhängig davon.

## 4. Ursache im Frontend

Zwei Bedienelemente im selben Reiter schreiben in **zwei verschiedene Ebenen**:

| Bedienelement | Datei:Zeile | schreibt nach |
|---|---|---|
| Grundauswahl an/aus (`onToggleMetric`) | `WeatherMetricsTab.svelte:662-673` | **global** (`buckets`) |
| „Aus"-Knopf (`onRemove`) | `WeatherMetricsTab.svelte:684-692` | **aktiver Kanal** |
| Zustand Roh/Einfach (`onMode`) | `WeatherMetricsTab.svelte:651-658` | **aktiver Kanal** |
| Sortieren (`onDndReorder`) | `WeatherMetricsTab.svelte:697 ff.` | **aktiver Kanal** |

`channelView()` (`:245-247`) bevorzugt einen vorhandenen Kanal-Eintrag ⇒ sobald die Kanal-Ebene
einmal existiert, ist die Grundauswahl für diesen Kanal dauerhaft und unsichtbar wirkungslos
(`models.py:826-846`).

Zusätzlich entfernt „Aus" die Zeile physisch aus der Anzeige (`metricsEditor.ts:294-304`,
`move(... 'primary' → 'off')`; Liste speist sich nur aus `primary`,
`WeatherMetricsTab.svelte:1281`) — im Kanal-Reiter gibt es keinen Weg zurück.

## 5. Warum der bestehende Wächter das nicht fängt

`tests/tdd/test_channel_metric_matrix.py` (#1677 Scheibe B), AC-15 — grün, und strukturell blind:

| # | Konstruktionsfehler | Belegstelle |
|---|---|---|
| 1 | baut `UnifiedWeatherDisplayConfig` **im Speicher**; Frontend, Speichern und Laden werden übersprungen — genau die fehlerhafte Strecke | `_single_metric_dc` / `_two_metric_dc` / `_sms_order_dc` |
| 2 | „abgewählt" wird als **„gar nicht in der Liste"** geprüft; Produktion hat den Eintrag **drin mit `enabled: false`** — anderer Codeweg | `sms_off = _render_sms(_single_metric_dc(partner_id, enabled=True))` |
| 3 | **nie mehr als 2 Metriken**; echter Trip hat 26. Zwei widersprechende Ebenen entstehen nie | `_two_metric_dc`, `_sms_order_dc` |
| 4 | bei 1:n-Metriken nur das **erste** Kürzel; `wind_chill` hat drei (`FK`,`FD`,`WC`) | `_representative_symbol()` |
| 5 | Fixture setzt künstlich `snow_depth_cm=20`, `snowfall_limit_m=1800`, `snow_new_sum_cm=3`, damit **jede** Metrik ein Kürzel erzeugt | `_matrix_segment()` |

**Übergeordnet:** Es gab **keine Zusage**, gegen die man hätte testen können — 49 ADRs, keines
zur Kaskade. Der Test prüfte, was der Code *tut*. Vgl.
[[reference_nachweis_als_bericht_ist_kein_schutz]], [[reference_pruefort_muss_dem_wirkort_entsprechen]].

## 6. PO-Entscheid 2026-08-11 (die fehlende Zusage)

**Verfeinerung statt Ersetzung:**

1. **Grundauswahl = das MAXIMUM** an Metriken für diesen Trip.
2. **Je Kanal darf nur ABGEWÄHLT werden** — nie hinzugefügt.
3. **Abwahl in der Grundauswahl wirkt sofort in ALLEN Kanälen.**
4. **„Aus" ist ein ZUSTAND, keine Löschung** — die Zeile bleibt mit Zustandsanzeige stehen.
5. Reihenfolge und Darstellungsform bleiben **je Kanal** einstellbar.

Gilt für alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS).

## 7. Weitere gemessene Befunde (Umfang anderer Scheiben/Issues)

- **`CHANNEL_COL_BUDGET.sms = 0`** (`metricsEditor.ts:231`) kodiert „SMS kann keine
  Reihenfolge" — seit #1677 (2026-08-10) **falsch**. Folgetexte: `LTCapNote.svelte:31`
  („entscheidungskritische Werte", **geteilter** Baustein ⇒ auch Ortsvergleich),
  `ltChannels.ts` („≤ 140 Zeichen" — Code kürzt bei **160**),
  `WeatherV2MailPreview.svelte:317`. Verstößt gegen den PO-Grundsatz „keine Bevormundung"
  ([[feedback_keine_bevormundung_nutzer_entscheidet_was_wichtig_ist]]). → #1719 S3
- **Auswertungswahl** (Abschnitt „05 — Auswertungen") existiert für **genau zwei** Metriken
  (`temperature`, `wind_chill`); Hilfetext verspricht „Überblick der E-Mail", steuert seit
  #1660 aber **auch** die SMS-Token; Quelle ist ausdrücklich die **globale** Liste
  (`trip_report.py:387` DEC-2), also nicht je Kanal einstellbar. → #1728
  **PO-Entscheid 2026-08-11:** Die Trennlinie ist **Platz, nicht Kanal**. Ausgabeorte mit
  Stundenauflösung (Stundentabelle, Nachttabelle, Telegram-rich Detail) brauchen keine
  Min/Max-Wahl; Orte mit genau einem Tageswert (Überblick-Pillen, Kurzform-Mail, SMS,
  Telegram-Kurzform, Premium-SMS, 3-Tages-Vorschau) schon. **In der Vollmail wird immer die
  Spanne gezeigt, ohne Bedienelement** ⇒ Abschnitt „05 — Auswertungen" entfällt ersatzlos.
  Wirkorte gemessen: `email/html.py:1429-1437` (Pillen), `email/compact.py:173-181`
  (Kurzform-Mail), `trip_report.py:382-404` (SMS) — die Stundentabelle ist **nicht** dabei.
- **3-Tages-Vorschau** der Mail: feste Spalten (`outlook.py:174-187`), Aufruf ohne `metrics=`
  (`html.py:1357`); Spalte `N` heißt „Nacht-Tief", enthält das **Tages**-Minimum
  (`outlook.py:211-213`). → #1720 / #1721
- **`show_night_block`** (Vorgabe `True`) hat keinerlei Bedienoberfläche. → #1721
- **Live-Vorschau** „So kommt es an" wird auf PO-Entscheid ersatzlos entfernt. → #1719 S3

## 8. Umfang dieser Scheibe (S1)

**Nur Festlegung + Prüfstand. Kein Produktivcode-Fix.**

1. ADR zur Metrik-Kaskade (Ziffern 1–5 aus Abschnitt 6).
2. Prüfstand, der die fünf Konstruktionsfehler aus Abschnitt 5 vermeidet:
   echte Trip-Datei als versionierte Kopie → echter Loader → echter Renderpfad; Widerspruchsfall
   als Pflichtprüfung; **alle** Kürzel je Metrik; keine künstlich aufgefüllten Wetterdaten;
   je Kanal.
3. Der Prüfstand muss den Fall aus Abschnitt 2 **rot** zeigen, bevor irgendetwas repariert wird.

**Nicht in dieser Scheibe:** Backend-Umbau auf Verfeinerung (S2), Frontend (S3), Legende (S4).

## 9. Testauflage (PO, 2026-08-11, wörtlich: „Das ist KRITISCH!!!!!")

Jede Scheibe mit Frontend-Anteil braucht einen **echten Browserlauf mit Klickpfad** unter
`frontend/e2e/`. Das Deploy-Gate #1558 lädt sechs Seiten und prüft Konsolenfehler — es klickt
keinen AC durch und genügt als Nachweis **nicht**.
S1 selbst ist ohne Frontend-Anteil; die Auflage greift ab S3.
