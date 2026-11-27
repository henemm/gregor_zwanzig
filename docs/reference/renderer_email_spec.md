# Renderer Specification – E-Mail Reports

This document defines how E-Mail reports are generated in Gregor Zwanzig.

**Last Updated:** 2026-11-21 (Issue #3139 — Niederschlagsart `precip_type` zeigt das Wort der Nutzersprache statt Programmname, Zeile „Wort" in der Anzeige-Tabelle)

**Vorher:** 2026-09-15 (Issue #2136/ADR-0068 — Pfad 1 des Ausblicks („Altform-Zweig")
verliert seine hartkodierte Kürzel-Namensliste `N · D · R · PR · Wind · Böen · Gew`; Spaltenköpfe
(HTML) und Klartext-Tokenpräfixe kommen jetzt aus `MetricDefinition.col_label` desselben
zentralen Registers, das auch die Etappentabelle speist — dieselbe Quelle, mit der Pfad 2 seither
ebenfalls arbeitet (vorher deutscher Langname aus dem Compare-Katalog))

**Vorher:** 2026-08-23 (Issue #2098 — ACC-Spalte erscheint jetzt auch im konfigurierbaren
Ausblick-Zweig, fest hinter den gewählten Metriken, mit Klartext-Wort statt nur Farbpunkt;
Sonnenstunden werden beim Etappen-Aggregat mit der Regel `sum` zusammengefasst statt `–` zu zeigen)

**Vorherige Aktualisierung:** 2026-08-22 (Issue #2011 — `_thunder_risk_level()` ruft für String-/Enum-Rohwerte
jetzt tatsächlich `thunder_ampel_band()` auf statt einer eigenen Stufen-Wort-Kette; nur der
numerische Legacy-Fallback bleibt hartcodiert, s.u.)

**Davor:** 2026-08-22 (Issue #2049 — Abgrenzung „Metric Display Contract" (Sektion 4/5)
gegen die eigene, unabhängige Roh/Einfach-Entscheidung des 3-Tages-Ausblicks (Sektion 6,
`display_config.outlook_metric_formats`) ergänzt)

**Acceptance Validators (seit Issue #733):**
- **Trip-Briefing-Mail** (beide Formate: `full` HTML / `compact` Nur-Text): `.claude/hooks/briefing_mail_validator.py` (dispatcht auf `X-GZ-Mail-Type` + `X-GZ-Format` Header)
- **Orts-Vergleich-Mail**: `.claude/hooks/email_spec_validator.py` (fest auf Vergleichstabelle/Winner-Box verdrahtet)

Siehe CLAUDE.md für Scope-Details und Pflicht-Gate-Dokumentation.

---

## Principles
- E-Mail reports are **long-form**, human-friendly, but must remain concise and structured.
- They always include the **compact token line** (identical to the SMS).
- They may add **human-readable summaries** and **tables per stage/etappen points**.
- Debug information is appended at the end in plain text, identical to console output.
- Outgoing mails carry marker headers (`X-GZ-Mail-Type`, `X-GZ-Format`) for deterministic routing to acceptance validators.

---

## Layout (seit Issue #884 – HTML-Mail Fidelity)

### Sektionen im HTML-Briefing (8 gesamt, 7 implementiert)

**Neu seit Issue #884 (2026-06-26):** Die HTML-Briefing-Mail folgt einer vollständigen, designgeleiteten Struktur mit 8 Abschnitten (7 implementiert; Stirnlampe entfällt nach PO-Entscheidung):

| Nr. | Sektion | Status | Beschreibung |
|---|---|---|---|
| 1 | **Header** (zweispaltig + Stats-Grid) | LIVE | Kopfzeile mit Etappen-Code + Titel + Datum (links) und Tripname + Etappennummer (rechts); darunter 5-er Stats-Grid (Distanz, Aufstieg, Abstieg, Max-Höhe, Segmente) |
| 2 | **Quick-Take + Tags** | LIVE | Kompakte Zusammenfassung des Briefing-Inhalts; farbige Tags (tone=warn/ok/info/risk) für Kontexte |
| 3 | **Stirnlampe** | ENTFÄLLT | (PO-Entscheidung aus Issue #790 — nicht mehr in neuem Cloud-Design) |
| 4 | **Segmente** (Stundentabellen) | LIVE | Pro Etappensegment: Segment-Header + zwei-stufige Desktop-Tabelle (Gruppen-Row TEMP/WIND/NIEDERSCHLAG + Einheiten-Row) + Mobile-Variante (`EmailHourList` zwei-Zeilen-Format) |
| 5 | **Wetter am Ziel** (abgesetzte Sektion) | LIVE | Eigene abgesetzte Sektion mit accent-Eyebrow, Zielname, Ankunftszeiten-Range, identische Tabelle wie Segmente |
| 6 | **3-Tages-Ausblick** (Folge-Etappen) | LIVE | Bis zu 3 Folge-Etappen (Trip) bzw. die 3 Folgetage je Ort (Ortsvergleich) als kompakte Zeilen-Tabelle (Korrektur 2026-11-17, #3122: hier stand „Nächste 4 Tage“; Beleg `_build_stage_trend()` `future_stages[:3]`, `comparison_engine.py` `_outlook_days … [:3]`). Blockname seit #3155 in jeder Ausgabe „3-Tages-Ausblick“ / EN „3-day outlook“: HTML-Eyebrow `mail.ausblick.eyebrow` (Orte `vergleich.ausblick.eyebrow`), Nur-Text- und Kompakt-Titel `mail.ausblick.name` (Kompakt in ASCII), Zustandshinweis `mail.ausblick.titel`; Trip zeigt Wochentag + Code + Name+Note + Temp-Range + (konfigurierbare Metriken) + ACC-Spalte + Risk-Dot; Ortsvergleich ohne ACC-Spalte; Gewitter-Badge falls vorhanden |
| 7 | **Antwort-Kommandos** | LIVE | Dedizierte Sektion mit 3-spaltigem Grid der Befehle (HEUTE, MORGEN, JETZT/NOW, GEWITTER, STRECKE [km], RUHETAG [N], STATUS, PAUSE [2d/12h], SKIP, STOP, WEITER, HILFE/HELP) + Hinweistext |
| 8 | **Footer** (zweigeteilt) | LIVE | Obere Zeile: Brand + Briefing-Typ; untere Zeile: Links (Trip-Übersicht, Zeitplan, Abmelden) |

Detaillierte Sektionsspezifikationen: siehe `docs/specs/_archive/modules/issue_884_mail_fidelity.md` (AC-1..AC-10).

### HTML-Rendering-Details (Issue #884)

#### Header (Sektion 1)
- **Struktur:** `<table>` mit zwei `<td>` (Desktop: Zweisspaltenlayout; Mobile: volle Breite)
- **Hintergrund:** `#fbfaf6` (G_HEADER_BG, neues Design-Token), `border-bottom:1px solid #e6e1d3`
- **Linke Spalte:** Eyebrow `"MORGEN-BRIEFING · {STAGE_CODE}"` (mono 10px, `#c45a2a`), Titel (22px desktop / 18px mobile), Datum (mono 13px desktop / 12px mobile)
- **Rechte Spalte:** `"GREGOR ZWANZIG"` (mono 10px, `#9a978d`), Trip-Kurzname (14px), Etappennummer (mono 12px)
- **Stats-Grid:** 5-Spalten-`<table>` (desktop) / 3 Spalten in 2 Zeilen (mobile); mit `border-right:1px solid #e6e1d3` als Trennlinie
  - Labels: Distanz · Aufstieg · Abstieg · Max-Höhe · Segmente

#### Segmente (Sektion 4)
- **Desktop-Tabelle:** zwei Ebenen
  - Gruppen-Row: Hintergrund `#fbfaf6`, Spaltenkopfgruppen (TEMP, WIND, NIEDERSCHLAG, SICHT/UV, HÖHE) mit Colspan
  - Einheiten-Row: Spalten-Labels mit Einheiten
  - Datenzellen: kritische Werte bekommen einen getönten Zellhintergrund (gelb `#fdf4cd` /
    orange `#fbe3cc` / rot `#f7d3e2`; Farben seit Bug #1801 S2, vormals `#fbeeb8`/`#fad6b8`/
    `#f6c5bf` — SSoT ist `design_tokens.py::tone_css()`), nicht farbigen Fettdruck. Seit
    Issue #1377 Scheibe B1 (`506c25f4`) stammt die Stufe für
    Wind/Böen/Regen/Regenwahrscheinlichkeit/Sicht
    einheitlich aus `severity_for`/`ampel_level` und den Katalog-Schwellen der
    „Best-Practice-Schwellen"-Tabelle unten (Wind z.B. 30/50/70 km/h, nicht mehr die alte
    fixe 20-km/h-Grenze). Gewitter läuft für String-/Enum-Rohwerte seit #2011 über die
    kanonische `thunder_ampel_band()` (`green/yellow/orange/red` → `ok/yellow/watch/risk`,
    `metric_format.py`); nur der numerische Legacy-Fallback (seltener Rohdatenpfad #1425)
    bleibt ausdrücklich hartcodiert, zweistufig, ohne `display_thresholds` im Katalog:
    rot ab >20, orange >0-20 (`_thunder_risk_level()`, `html.py:171-203`).
- **Mobile-Tabelle:** `EmailHourList` zwei-Zeilen-Format (neu ab Issue #884; ersetzt `_render_mobile_compact_rows`)
  - Hauptzeile: Zeit (mono bold, 26px breit) · Wetter-Glyph · Temp · gefühlte Temp · Risk-Dot
  - Detailzeile: Wind/Regen/Sicht/UV/Höhe komprimiert
  - Hintergrund: transparent oder leicht warn-getönt bei kritischen Werten

#### Wetter am Ziel (Sektion 5)
- **Sektion:** eigener Block, `bg #fbfaf6`, `border-top:1px solid #e6e1d3`
- **Kopfzeile:** Zweispaltig space-between; Links accent-Eyebrow `"ANKUNFT · WETTER AM ZIEL"` (`#c45a2a`) + Zielname; Rechts Zeitraum-String
- **Tabelle:** identischer Stil wie Segment-Tabellen (Desktop + Mobile)

#### 3-Tages-Ausblick (Sektion 6)

> **Gebaut mit B4 (#3155):** Der Block heißt in HTML-, Nur-Text- und Kompakt-Mail sowie im Zustandshinweis „3-Tages-Ausblick“ / EN „3-day outlook“ (Kompakt ASCII „3-Tages-Ausblick“); „Nächste Etappen“, „Ausblick · nächste 3 Tage“ und „Mehrtages-Trend“ entfallen. Gesteuert wird er an **einer** Stelle: mit Tabelle `outlook_reports`, ohne Tabelle die Umrechnungsregel `_legacy_outlook_reports` (Trip: `show_outlook: false` außer im Kompakt-Format und leere `outlook_metrics` = aus, sonst `multi_day_trend_reports`; Orte: `outlook_enabled`, sonst die Anlage-Marke `placements.outlook_reports` ohne `rows`). `show_outlook` steuert ohne Tabelle nur noch die Großwetterlage.

> **Soll ab #3122 ([ADR-0124](../adr/0124-was-steht-wo-eine-tabelle.md), PO 2026-11-17):** Der Block heißt überall „3-Tages-Ausblick“. Er bekommt keine eigene, unabhängige Liste mehr: er folgt der E-Mail-Auswahl (Spalte „3-Tages-Ausblick“ der Tabelle „Was steht wo“, je Metrik abwählbar, Roh/Einfach je Stelle; ADR-0124 Nr. 4 und 5) und hat **eine** steuernde Stelle „Morgen-Briefing“/„Abend-Briefing“ für Trip und Orte (Nr. 6). Bis zum Bau gilt das hier Beschriebene (`outlook_metrics`, `outlook_metric_formats`, `show_outlook`, `multi_day_trend_reports`, Orte `outlook_enabled`); Renderer und Validatoren werden nur zusammen geändert.

- **Struktur:** `<table>` mit einer `<tr>` pro Folge-Etappe
- **Zwei Render-Zweige**, unterschieden am Parameter `metrics` von `render_outlook_table()` /
  `render_outlook_plain()` — **nicht** an der Mail-Art:
  - **Altform-Zweig** (`metrics=None`): acht feste Spalten (Tag + sieben Wettergrößen), ACC-Spalte
    je nach `show_acc`. Trip und Ortsvergleich fuhren früher hierüber; heute nur noch Altbestand
    ohne aufgelöste Metrik-Auswahl. Die Spaltenköpfe sind seit #2136/ADR-0068 (2026-09-15) **keine**
    eigene Namensliste mehr — sie kommen aus `MetricDefinition.col_label` (dieselbe Quelle wie die
    Etappentabelle), mit `aggregation_label_de()` als Kollisionsauflösung für die beiden
    Temperatur-Spalten Tief/Hoch. Vorher hartkodiert: `N · D · R · PR · Wind · Böen · Gew`.
  - **Konfigurierbarer Zweig** (`metrics` gesetzt): die gewählten Metrik-Spalten in
    Auswahl-Reihenfolge, dahinter die ACC-Spalte je nach `show_acc`. **Trip** fährt seit #1848 A3
    hierüber, der **Ortsvergleich** seit #1361/#1368.
- **ACC je Mail-Art:** Trip `show_acc=True` (Spalte erscheint), Ortsvergleich `show_acc=False`
  (Kopfzelle UND Datenzellen entfallen vollständig). Gilt in **beiden** Zweigen gleich.
- **Risk-Dot:** `border-radius:50%`, 10×10px, Farbe aus `_AMPEL_DOT_COLORS` (4-stufig seit #1927):
  - green (ok): `#15803d` + `rgba(21,128,61,0.18)`
  - yellow (watch-mild): `#d69500` + `rgba(214,149,0,0.20)`
  - orange (watch-mittel): `#d4530a` + `rgba(212,83,10,0.20)`
  - red (risk): `#a8104a` + `rgba(168,16,74,0.22)`
- **ACC-Spalte** (Prognose-Genauigkeit; im konfigurierbaren Zweig seit Issue #2098): vier Stufen
  aus der kanonischen Quelle `_ACC_STUFEN` — **eigene Farbwerte, nicht `_AMPEL_DOT_COLORS`**:
  - HTML: Farbpunkt — `#2f8a3e` (≥80) · `#e3b008` (≥60) · `#e07b1a` (≥40) · `#c52a22` (<40)
  - Klartext: deutsches Wort — **hoch** (≥80) / **mittel** (≥60) / **niedrig** (≥40) /
    **sehr niedrig** (<40)
  - Fehlender oder nicht lesbarer Wert: `–` in beiden Fassungen
  - **Keine wählbare Metrik:** `confidence` trägt `selectable=False` (ADR-0005/#710) und kann in
    der Metrik-Auswahl nicht erscheinen. Die Spalte wird am `outlook_columns()`/`cells`-Mechanismus
    vorbei fest hinter den gewählten Metriken angehängt.
- **Sonnenstunden im Ausblick (seit Issue #2098):** Werden beim Aggregieren mehrerer Segmente zu einer Etappe mit der Regel `sum` zusammengefasst (nicht `–`; `sunny_hours` trägt Katalog-Definition `summary_fields={"sum": "sunny_hours"}`)
- **Gewitter-Badge:** `⚡ Gewitter {zeitangabe}` in `#a8104a` mit light-red Hintergrund und Border

#### Antwort-Kommandos (Sektion 7 – NEU)
- **Grid:** 3 Spalten, zeilenweise gefüllt via `<table>` (12 Einträge → 4 Zeilen)
- **12 Einträge, aus `_COMMAND_SPECS` abgeleitet — identisch in Klartext- und HTML-Fußzeile
  (Issue #2134; vorher fehlte STRECKE in beiden, RUHETAG zusätzlich in HTML):**
  HEUTE, MORGEN, JETZT (auch NOW), GEWITTER, STRECKE [km], RUHETAG [N], STATUS,
  PAUSE [2d / 12h], SKIP, STOP, WEITER, HILFE (auch HELP)
- **Stil:** CMD mono 11px bold + Beschreibung mono 10px `#9a978d`
- **Hinweistext:** mono 10px, color `#b8b4a8`: "Antworte auf diese E-Mail mit einem Schlüsselwort."

#### Footer (Sektion 8)
- **Gesamter Footer:** `bg #1d1c1a`, `color #9a978d`, mono 11px
- **Obere Zeile:** Links `"GREGOR ZWANZIG"` (`#fff`, bold, letterSpacing 0.06em) + " · " (`#5a5750`) + Briefing-Typ; Rechts (desktop-only) Datum + Provider + Icon
- **Untere Zeile:** Nach `border-top:1px solid #3a3835`, Link-Zeile: "Trip-Übersicht öffnen →" (`#c45a2a`) · "Briefing-Zeitplan" · "Abmelden" (alle plain text, keine `href`)

### Legacy: Token Line & Debug Block

#### 2) Token Line
- First block of the body.
- Exact 1:1 copy of the SMS token line.
- **Format-Definition:** siehe [`docs/reference/sms_format.md`](sms_format.md) (v2.0) — Single Source of Truth.
- Beispiel (mit Vigilance-Block und Fire-Block für Korsika):
  ```
  Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17) VR:M@17VT:H@17 Z:HIGH208 M:24
  ```
- Beispiel (ohne Vigilance/Fire, internationaler Trip):
  ```
  Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 TH+:- DBG[MET MED]
  ```

#### 3) Human-Friendly Summary (Quick-Take)
- Short list (dl) of the same values in words, e.g.:
  - Temperatur: Nacht-Min 15°C · Tages-Max 25°C
  - Regen: Menge –, Wahrscheinlichkeit 20% @14 Uhr
  - Wind: 22 km/h @14 Uhr, Böen 35 km/h @14 Uhr (Peak 48 km/h @19 Uhr)
  - Gewitter: Level M @14 Uhr

#### 4a) Klartext-Hinweis bei niedriger Konfidenz (Issue #121, ab Issue #715 einziger Confidence-Output in Tabelle)

Im E-Mail-Body wird ein Klartext-Hinweis ausgegeben, wenn an mindestens einer Stunde in T+0..72h `confidence_pct < 60` liegt. Dies ist der **einzige visuelle Confidence-Hinweis in der E-Mail-Tabelle** (Spalte wurde mit Issue #715 entfernt; Verlässlichkeit erscheint nur noch als Textblock und SMS-Token). Andernfalls erscheint **kein** Hinweis (Visual-Noise-Vermeidung).

- Format: `"Ab {Wochentag} nimmt die Unsicherheit zu (Temperatur-Spreizung {N} °C)."`
- Wochentag: erster betroffener Tag in T+0..72h (Deutsch: Montag–Sonntag).
- Spread: `max(spread_t2m_k)` über alle unsicheren Stunden dieses Tages, gerundet auf ganze Kelvin/°C.
- HTML: `<p class="confidence-hint">…</p>` in einem gelb hinterlegten Block, positioniert zwischen `summary` und `changes`.
- Plain: eigene Zeile mit Leerzeile davor/dahinter, gleicher Position.

#### Debug Block
- Always appended at the end, in `<pre>` formatted text.
- Content identical to console output.
- Must include:
  - `cfg.path`
  - `report` (morning/evening/update)
  - `channel` (console/email/sms)
  - `debug` flag
  - `dry_run` flag
  - `source.decision`
  - `source.chosen`
  - `source.confidence`
  - `source.coords`
  - `source.meta` (provider, run, model)
  - token line used
- Example:
  ```
  (Beispiel aus der MVP-Ära entfernt — das damalige source.decision/MOSMIX-Format
  existiert nicht mehr im Code. Maßgeblich ist der tatsächliche Debug-Block der
  gerenderten Mail; Provider-Ist-Stand: docs/reference/decision_matrix.md.)
  ```

---

## Rules
- **Token line** is the single source of truth → all other representations must derive from it.
- **Debug block** must be identical between console and email.
- **Tables** may extend beyond 160 chars (no SMS limit).
- **Times** in tables use **leading zeros** for clarity.
- All numbers are integers unless explicitly defined as float (e.g. rainfall `R`).

---

## Ortsvergleich-Alarm: Ortsname einmal, kein „km 0–0" (seit Issue #2598)

Im Ortsvergleich (Änderungs- und Radar-Alarm) steht der Ortsname im Betreff nur im `[Name]`-Präfix; ein Kilometer- oder Etappenteil entfällt (Kennzeichen: `AlertMessage.location_label` gesetzt, Trip setzt es nie und bleibt unverändert). Ereigniszeilen nennen den Ort statt `km 0–0`.

- Änderung, 1 Ort: Betreff `[Ort Eins] ↑ Böen: 30 km/h→60 km/h`, Mail `Wo & wann: Ort Eins · stärkste Stunde 14:00`
- Bündel, 2 Orte: Betreff `[Ort Eins, Ort Zwei] ↑ 2 über Schwelle: …`
- Beginn-Verschiebung, 1 Ort: Betreff `[Ort Eins] Gewitter-Beginn 10:00 (2 h früher)`, Zeile `Gewitter-Beginn: 12:00 → 10:00 (2 h früher · Ort Eins)`
- Radar, 1 Ort: Betreff `[Ort Eins] Regen in 30 Min`, Mail `Wo & wann: Ort Eins · ab 14:30`
- Trip unverändert: `[GR20] Segment 3 · ↑ Böen: …`

Spec: `docs/specs/modules/fix_2598_ortsvergleich_alarm_kopfzeile.md`.

## Abweichungs-Alarm: Stundenzeilen (seit Issue #1737)

Die Abweichungs-Alarm-Mail (Trip und Ortsvergleich; `src/output/renderers/alert/render.py::render_email`) zeigt unter der Kopfzeile **jedes Ereignisses** einen eigenen Block mit einer Tabellenzeile je betroffener Stunde: `HH:MM | alt → neu` (Ortszeit, `local_fmt`). Keine gemeinsame Tabelle über mehrere Ereignisse.

- **Darstellung Trip:** wie das Briefing desselben Kanals und Trips — ROH = Stufenwort bzw. Wert, EINFACH = farbiger Punkt aus HTML/CSS (**keine Emojis**, #2220). Modus aus der Anzeige-Konfiguration des jeweiligen Nutzers.
- **Darstellung Ortsvergleich:** Stundenwerte immer roh (wie die Stundentabelle der Vergleichs-Mail, PO-Entscheid 2026-10-21), Zeilen nur unter betroffenen Orten.
- **Auswahl** (`alert/hours.py`): Metrik mit Stufe = Stufenwechsel; Metrik ohne Stufe = Stundendifferenz ≥ Alarmschwelle der Metrik; angezeigt wird der zusammenhängende Bereich erste bis letzte betroffene Stunde. Alt/neu werden per UTC-Zeitstempel gepaart.
- **Kappung:** höchstens 6 Zeilen (die stärksten, in Zeitfolge) plus Hinweiszeile „betroffen HH:MM–HH:MM".
- **Summen-Metriken** (z. B. Niederschlag): Summe bleibt in der Kopfzeile, die Zeilen zeigen Stundenwerte.
- **Fallbacks:** ohne Anker nur der neue Wert (ohne „alt →"); ohne Stundenreihe byte-gleich zur Ausgabe vor #1737.
- Nur Uhrzeiten und Werte, keine Empfehlung, keine berechnete Prozentangabe. Die Alarm-Mail trägt weiterhin den Marker-Header `X-GZ-Mail-Type: deviation-alert` (Trip und Ortsvergleich, `notification_service.py`).

Spec: `docs/specs/modules/feat_1737_alarm_stundenzeilen.md`.

## Abweichungs-Alarm: Farbsatz der Ampel (seit Issue #2793 S2b)

Der Abweichungs-Alarm folgt der Profil-Ampel des Abos (ADR-0106 P4). Für die Ampel-Metriken (Temperatur, Wind, Böen, Niederschlag, Neuschnee, Sicht, UV, Gewitter) steht statt des Urteils „Änderung über/unter deiner Alarm-Schwelle ({schwelle})" ein Farbsatz aus dem Katalog (`alarm.ampel.*`, DE/EN):

- Verschärfung: „{label} von {farbe_von} auf {farbe_bis} gestiegen: {von} → {bis}" (EN „{label} rose from {farbe_von} to {farbe_bis}: {von} → {bis}")
- Sprung: „{label} weiter {farbe}, großer Sprung: {von} → {bis}" (EN „{label} still {farbe}, large jump: …")
- Entwarnung: „Entwarnung {label}: von {farbe_von} auf {farbe_bis} zurückgegangen ({von} → {bis})" (EN „All clear {label}: back from … to … (…)")

Einzelereignis: der Satz steht im Urteils-Badge, die zweite Datenzeile zeigt „Änderung {Δ}: {farbe_von} → {farbe_bis}". Mehrere Ereignisse: je Ereignis eine Zeile mit dem Satz, Zähler „{n} Änderungen seit dem Briefing". Bei Temperatur nennt `{label}` die Seite („Tageshöchst"/„Tagestief", EN „Daily high"/„Daily low"). Der Bezug aufs Briefing bleibt in der Fußzeile („verglichen mit {Zeit}", ADR-0056). Nullgradgrenze und Beginn-Verschiebung (D4) behalten bis S7 Text und Urteil von vorher. Stundenzeilen unverändert.

Spec: `docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md` §4.

---

## Marker Headers and Validation Routing (seit Issue #733)

`build_mime_message()` in `src/output/channels/email.py` setzt optionale Marker-Header zur deterministischen Klassifikation:

### Header-Format

```
X-GZ-Mail-Type: trip-briefing | compare
X-GZ-Format:    full | compact
X-GZ-Lang:      de | en
```

`X-GZ-Lang` nennt die Sprache des Inhalts (ADR-0104, seit #2663). Er wird in jeder Mail gesetzt; Details und Übergangsregel: `docs/reference/mail_validators.md`, Abschnitt „Sprache".

### Routing

| Mail-Typ | Format | Quelle | Validator |
|----------|--------|--------|-----------|
| `trip-briefing` | `full` | `trip_report_scheduler.py` (Briefing-Versand) → `src/services/trip_briefing_aufbau.py` (Aufbau der Mail, seit #3128) | `.claude/hooks/briefing_mail_validator.py` (AC-1/4) |
| `trip-briefing` | `compact` | `trip_report_scheduler.py` (compact-Renderer seit #722) → `src/services/trip_briefing_aufbau.py` (Aufbau der Mail, seit #3128) | `.claude/hooks/briefing_mail_validator.py` (AC-2/6) |
| `compare` | `full` | `src/services/scheduler_dispatch_service.py` → `src/services/compare_briefing_aufbau.py` (Aufbau der Mail, seit #2983) → `notification_service.py` (Scheduler-Lauf + „Senden“-Button) | `.claude/hooks/email_spec_validator.py` (AC-3) |
| `compare` | `compact` | wie `compare/full`; `compare_email_rendern` zweigt bei `display_config.email_format == "compact"` auf `src/output/renderers/email/compact_compare.py` (`render_compare_compact`, seit #3059) ab und liefert leeres HTML → `send_compare_report` sendet einen Textteil (`html=False`, `X-GZ-Format: compact`) | `.claude/hooks/email_spec_validator.py` (Kompakt-Zweig, #3059) |

### Validierungslogik

- **`briefing_mail_validator.py`** prüft Trip-Briefing-Mails format-spezifisch:
  - `trip-briefing/full`: multipart/alternative, HTML + Plain Parts, ≥1 sequenzielle Stundentabelle, Werte selbst-konsistent
  - `trip-briefing/compact`: single text/plain, 7bit, isascii, < 2 KB, Kopf + Metriken + Ausblick + Footer (keine Stundentabelle)
  - `compare`-getaggte Mails: sauberes No-Op (Exit 0, falscher Validator)

- **`email_spec_validator.py`** prüft Orts-Vergleich-Mails (Vergleichstabelle, Winner-Box, min-locations). Für andere Mail-Typen nicht zuständig.
  - `compare/compact` (#3059): single text/plain, 7bit/quoted-printable, isascii, < 2 KB, keine Stundentabelle; mit `--konfig` je Ort genau eine Ortszeile (beginnt mit dem ASCII-gefalteten Namen) in der Ortsfolge, Kürzungs-Hinweis `+N …` erlaubt das Fehlen der letzten N Orte; Format gegen `display_config.email_format` (`SOLL: Format '<ist>' statt '<soll>'`).

**Orte-Kompakt-Mail (seit #3059):** Kopf „Orte – Datum“ (EN „Locations“), je Ort eine Zeile `Name: [!] K Wert …` (Kürzel = `compact_label` des Katalogs, Warnmarker `!`/`!!`/`!!!` nach amtlicher Warnstufe), darunter eingerückt eine Zeile „3-Tages-Ausblick: Tag … | Tag …“ nur bei eingeschaltetem Ausblick, kein Stundenverlauf; Fuß „Orte · Kompakt · Quelle“. Grenze 2 KB inklusive Hinweis „+N Orte nicht gezeigt“ (EN „+N locations not shown“), gekürzt vom Listenende. Vorschau und Testversand zeigen denselben Text (`compare_email_rendern` ist der gemeinsame Punkt). Unbekannte Metrik-Kennungen werden in der Kompakt-Mail ausgelassen und per Log-Warnung (`logger.warning`, #3059) gemeldet, nicht still verworfen.

**Orte-Mail: Bereichsname und Ein-Ort-Texte (seit #3122 B5, ADR-0124 Nr. 10 und Nachtrag Nr. 13):** Der Bereich heißt „Orte“ (EN „Locations“), auch bei einem Ort; „Vergleich“, „Orts-Vergleich“, „Ortsvergleich“ und „Orts-Briefing“ stehen in keiner Ausgabe mehr. Interne Bezeichner (`compare`, `vergleich`, `X-GZ-Mail-Type: compare`) bleiben.

| Stelle (Katalog) | mehrere Orte | genau ein Ort |
|---|---|---|
| Kopf HTML/Klartext/Telegram (`vergleich.kopf.titel`) | `ORTE` (EN `LOCATIONS`) | `ORTE` |
| Mail-Titel, Marke im Fuß, Abo-Name (`vergleich.kopf.titel_kurz`, `vergleich.fuss.abo_name`) | `Orte` (EN `Locations`) | `Orte` |
| Herkunftszeile (`mail.herkunft.vergleich`) | `Orte` | `Orte` |
| Betreff (`versand.scheduler.vergleich_betreff`) | `Orte: {name} ({datum})` (EN `Locations: …`) | dasselbe |
| Übersicht, Unterzeile (`vergleich.uebersicht.titel.one/.other`) | `Alle Orte · gewählte Metriken` | `Gewählte Metriken` |
| Stundenverlauf, Titel (`vergleich.stunden.titel.one/.other`) | `Stundenverlauf · alle Orte` | `Stundenverlauf` |
| Fuß (`vergleich.fuss.abo_zeile.one/.other`) | `{n} Orte · Vorlage {vorlage}` | `1 Ort · Vorlage {vorlage}` |
| Umfang einer amtlichen Warnung (`warnung.umfang.alle_orte`, Code `official_alerts.py`) | `alle Orte` (EN `all locations`) | der Ortsname selbst, nie „alle Orte“ (#3153 AC-2, Abo mit genau einem Ort) |
| Knopf (`vergleich.fuss.app_oeffnen`) | `In der App öffnen →` (EN `Open in app →`) | dasselbe |

Die Stundenverlauf-Überschrift steht in Klartext und HTML nur, wenn mindestens ein Ort ohne Fehler Stundendaten hat; ohne solchen Ort entfällt der Block, der Ausblick bleibt (feat_3122 AC-10, seit 2026-11-27 in beiden Fassungen gleich, #3425).

Die Tabelle „Übersicht“ steht auch bei genau einem Ort in der Mail. Der Befehlsblock nennt „Briefing für heute/morgen jetzt senden“ statt „Vergleich …“, der Hinweis auf gewählte Größen ohne Wert endet auf „in der Übersicht“, die leere Mail sagt „Keine Wetterdaten verfügbar.“

**Acceptance Gating:** Nur Exit 0 der entsprechenden Validator erlaubt „E2E Test bestanden".

---

## Metric Display Contract (seit Issue #814)

### Einfach (use_friendly_format=True) vs. Roh (use_friendly_format=False)

Der vollständige Vertrag aller Wetter-Metriken in der Briefing-Mail wird hier **einmalig** festgelegt.
Die **alleinige Quelle** der Anzeige-Entscheidung ist `use_friendly_format` in `MetricConfig`.

**Abgrenzung (seit Issue #2049):** Dieser Vertrag gilt für die Stundentabellen/Segmente
(Sektion 4/5). Der **3-Tages-Ausblick** (Sektion 6, Trip **und** Ortsvergleich) hat seit
#2049 eine eigene, unabhängige Roh/Einfach-Entscheidung —
`display_config.outlook_metric_formats` statt `use_friendly_format` —, eigene
Fähigkeitsliste (`OUTLOOK_FRIENDLY_CAPABLE`, zehn statt fünfzehn Größen; seit #3156 aus `STELLEN_ZWEI_FORMEN`, Stelle `outlook`, abgeleitet) und teils eigene
Wortskalen (Regenwahrscheinlichkeit/Sonnenstunden/Niederschlag-Tagessumme sind hier neu
und weichen bei Niederschlag bewusst von den Stunden-Schwellen dieser Tabelle ab). Details:
`docs/reference/api_contract.md` (`outlook_metric_formats`), Spec
`docs/specs/modules/fix_2049_ausblick_darstellungsform.md`. **Seit #3260 S1b** (Spec
`feat_3260_s1b_form_je_stelle.md`, ADR-0127) gilt im Ausblick die Form je Ausgabeart aus
`metric_catalog.STELLEN_FORMEN`, gebaut von `metric_format.darstellung`: Wind, Böen,
Niederschlag und Regenwahrscheinlichkeit auf Einfach zeigen in der HTML-Mail den Ampelpunkt
(Farbe der Abo-Ampel), in Nur-Text, Kompakt-Mail und Telegram die Wortstufe; Bewölkung in
der Kompakt-Mail die Wortstufe (klar/heiter/wolkig/stark bewölkt/bedeckt) statt eines
Emoji-Kurznamens.

**Orte-Stundenverlauf (seit Issue #3097, ADR-0121 Nachtrag 3b):** Der Stundenverlauf der Orts-Vergleich-Mail hat eine eigene Roh/Einfach-Entscheidung je Zeile: `display_config.hourly_metric_formats` (fehlt = Roh). Unabhängig von `use_friendly_format`, von `channel_layouts.email` (Vergleichstabelle) und von `outlook_metric_formats`. Einfach bei Wind, Böen, Niederschlag und Regenwahrscheinlichkeit (die beiden letzten seit #3260 S1b): Ampelpunkt in der Farbe der Abo-Ampel im HTML, Wortstufe im Klartext (dort kein Farbpunkt); Wolken Symbol; Niederschlag im Klartext nach der **Stunden**-Skala (trocken/leicht/mäßig/stark), nicht der Tagessummen-Skala. Temperatur und Gewitter haben keinen Umschalter. Seit #3156 wirkt ein gespeichertes Einfach nur, wo `STELLEN_ZWEI_FORMEN` die Stelle `hourly` nennt (Sonnenstunden und Windrichtung fallen heraus, Ausgabe dort wie Roh). Details: `docs/reference/api_contract.md` (`hourly_metric_formats`), Spec `docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md`.

> **Soll ab #3122 (ADR-0124, PO 2026-11-17):** Der Orte-Stundenverlauf wird eine Spalte der Tabelle „Was steht wo“ und folgt der E-Mail: ein Haken ist dort nur möglich, wenn die Metrik in der E-Mail (Übersicht) steht; vorbelegt wie die E-Mail, je Metrik abwählbar; Metriken ohne Stundenwert sind gesperrt; Roh/Einfach bleibt je Stelle getrennt, aber nur bei Metriken mit zwei Formen (ADR-0124 Nr. 4, 5). Der Block-Schalter „Stundenverlauf an/aus“ steht unter der Tabelle (Nr. 6). Die Unabhängigkeit von `channel_layouts.email`, die dieser Absatz beschreibt, gilt bis zum Bau. Der Bereich heißt dann „Orte“, die E-Mail-Tabelle „Übersicht“ (Nr. 10); die Namen „Orts-Vergleich“ und „Vergleichstabelle“ in diesem Dokument beschreiben den heutigen Stand.

**Single Source of Truth: Metrik-spezifische Anzeige-Regeln**

| Kategorie | Metriken | Einfach (HTML) | Einfach (Plain) | Roh (HTML) | Roh (Plain) | Notiz |
|---|---|---|---|---|---|---|
| **Severity-Ampel** 🟢🟡🟠🔴 | wind, gust, precip, pop | Ampelpunkt nach Profil-Ampel des Abos (seit #2792 S1c-4b) | Zahl + Einheit; bei gespeichertem `format_mode="simplified"` die Wortstufe (pop seit #3156: Skala 25/50/75 wie Orts-Vergleich und Ausblick) | Zahl + Einheit, **keine Markierung** | Zahl + Einheit | Nur HTML hat Ampel. Die Menge ist `metric_catalog.AMPEL_METRIC_IDS` (abgeleitet aus `STELLEN_ZWEI_FORMEN`, E-Mail-Stelle, plus Ampel-Schwellen; #3156); im Orts-Vergleich zeigt Einfach bei allen vier den Ampelpunkt. **CAPE trägt keine Farbe** (nackte Zahl, nie „–“) |
| **Wetterbild-Piktogramm** | cloud_total, cloud_low, cloud_mid, cloud_high, sunshine | Emoji (☀️🌤️⛅🌥️☁️) | Emoji (gleich) | Zahl | Zahl | Emoji in Einfach (HTML+Plain), Zahl in Roh — unverändert seit #435 |
| **Severity-Ampel** 🟢🟡🟠🔴 | thunder | Ampelpunkt (NONE=grün, LOW=gelb, MED=orange, HIGH=rot); **keine Aussage (`None`) = „–"** | deutsches Wort (kein / leicht / mittel / hoch) | deutsches Wort | deutsches Wort | Seit #1491 reguläre Ampel-Spalte: kein ⚡, kein „mögl." mehr. „–" heißt ausschließlich „keine Aussage", nie „keine Gefahr" (`thunder_ampel_band()` liefert für `None` bewusst `None`). Die Gewitter-Pille im Prosa-Block (Zeile 87) behält ihr ⚡ — sie ist nicht Teil der Spalte. 🔴 **Nur die Trip-Stundentabelle zeigt bei `NONE` einen grünen Punkt** — die Übersichtsmatrix des **Orts-Vergleichs** lässt `NONE` bewusst **unmarkiert** (`compare_html._sev_thunder` liefert dort `None`). Bewusste Unterscheidung, kein Versehen: die Trip-Tabelle listet jede Stunde und braucht die Aussage „geprüft, ruhig"; die Vergleichsmatrix zeigt Tageswerte und würde sonst flächig grün markiert. Ein Umbau, der `NONE` über die geteilte Bandzuordnung laufen lässt, kippt das still um (passiert in #1491, korrigiert in `99da3131`) |
| **Zahl (kein Modus-Unterschied)** | visibility, temperature, wind_chill, dewpoint, humidity, pressure, uv_index, freezing_level, snowfall_limit, snow_depth, fresh_snow | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Zahl + Einheit | Unverändert in beiden Modi |
| **Wort (kein Modus-Unterschied, seit #3139)** | precip_type | Wort der Nutzersprache (Regen / Schnee / Mischniederschlag / Eisregen; EN Rain / Snow / Mixed precipitation / Freezing rain) | gleich | gleich | gleich | Keine Ampel. Fehlender oder unbekannter Wert `–`. Quelle `precip_type_label()` in `src/output/metric_format.py`, geteilt mit Telegram und Orts-Vergleich |

### Best-Practice-Schwellen (Ampelpunkte für Severity-Metriken)

| Metrik | 🟡 (Gelb) | 🟠 (Orange) | 🔴 (Rot) | Basis |
|---|---|---|---|---|
| wind (km/h) | 30 | 50 | 70 | Beaufort 5/7/8–9 |
| gust (km/h) | 30 | 45 | 60 | PO-Entscheidung #1377: die Werte, die die Stundentabelle bereits färbte |
| precip (mm/h) | 1 | 5 | 10 | Regenintensität leicht/mäßig/stark |
| pop (%) | 30 | 60 | 80 | Niederschlagswahrscheinlichkeit |
| cape (J/kg) | – | – | – | seit #2792 S1c-4b ohne Farbe (früher 300/800/1500) |
| temperature / wind_chill (°C) | ≥28 · <0 | ≥31 · <−5 | ≥34 · <−15 | PO-Entscheidung #1377, beidseitig (Hitze und Kälte) |
| uv_index | 3 | 6 | 8 | PO-Entscheidung #1377 |

Quelle ist immer `display_thresholds` im Metrik-Katalog; ausgewertet wird ausschließlich über
`metric_format.severity_for` (Issue #1377). Die Tabelle hier ist Abschrift, nicht Quelle.

Seit #2792 S1c-1 (2026-11-05) liest kein Renderer `display_thresholds` mehr selbst: die Schwellen
kommen über das keyword-only Pflichtparameter-Objekt `ampel=` (`src/app/ampel.py`: `resolve_ampel`,
`ampel_for`) bis an jede Farbentscheidung; `AlertMessage` trägt das Pflichtfeld `ampel`. Die Einstiege
übergaben in S1c-1 noch `resolve_ampel(None)` (Vorlage „Allgemein“ = obige Werte, byte-gleich).
**Seit S1c-4b (2026-11-06/07)** lösen alle Einstiege die Ampel des jeweiligen Abos auf (Vorlage plus
eigene Abweichungen); die Tabelle zeigt damit nur die Vorlage „Allgemein“. Ratsche: `tests/tdd/test_kein_leser_liest_display_thresholds.py` (kein Lesezugriff auf
`display_thresholds` in `src/output/**`).

**Nicht verwechseln:** `risk_thresholds` (Risk Engine, `api_contract.md` §7) ist eine getrennte
Größe mit eigener LOW/MODERATE/HIGH-Skala und wird von der Ampel nicht berührt.

### Visibility: kein Ampelpunkt in der Tabelle, aber Zellhintergrund und Klartext-Block

Für die **Tabellenspalte** gilt die Entscheidung aus #814 unverändert: kein Ampelpunkt/-Emoji.
Echte Wetterdaten zeigen Median 16–54 km, ≥10 km in 90–100 % aller Stunden — eine Spaltenampel
wäre dauergrün und wertlos, die nackte km-Zahl trägt mehr Information. `visibility` steht
deshalb weiterhin nicht in `_COL_KEY_TO_METRIC_ID` (`html.py:565`, das Mapping für den
Ampelpunkt der Ampel-fähigen Metriken wind/gust/precip/pop; ein toter `cape`-Eintrag steht
dort noch, wirkt aber nicht, seit CAPE keine Farbe mehr trägt, #2792 S1c-4b).

**Seit Issue #1377 Scheibe B1 (`506c25f4`) bekommt die Sicht-Zelle aber einen getönten
Hintergrund:** Der Roh-Modus-Fallback in `_render_html_table` fragt für `vis`/`visibility`
`_FALLBACK_COL_KEY_TO_METRIC_ID` (`html.py:576`) und darüber `severity_for("visibility", …)`
mit den Katalog-Schwellen (2000/1000/500 m) — der Wert wird dafür auf Meter normalisiert
(`html.py:644-649`). Die vorherige Aussage „Sicht bekommt in der Tabelle nie eine Färbung"
gilt also nicht mehr uneingeschränkt: kein Ampelpunkt, aber seit B1 eine Zellhintergrund-
Tönung wie bei den übrigen Ampel-Metriken.

Für die **Klartext-Zeile** gilt seit #1377 das Gegenteil: Meldet sie eine Unterschreitung
(„Sicht <2 km ab 14:00"), wird sie nach den invertierten Schwellen 2000/1000/500 m gefärbt.
Bis #1377 war sie bei jedem Nebelwert grün, weil die halb hinterlegte Schwelle stillschweigend
als „unbedenklich" gelesen wurde — ein Fehler, kein Feature. Der Unterschied ist konsistent:
Die Zeile erscheint überhaupt nur bei einer Unterschreitung, sie kann also nicht dauergrün sein.

### Implementierungs-Hinweis: Roh-Modus — Zahlen statt Ampeln, aber Zell-Tönung bleibt

Im Roh-Modus sind alle Ausgaben numerisch/textlich: keine Ampel-Emojis/-Punkte und
**keine inline-Highlights** (insbesondere nicht Gelb-Highlight bei CAPE oder
Orange-Highlight bei Sicht — `highlight_color` war nie gewollt).

**Die Zell-Hintergrund-Tönung (`cell_bg`) gilt dagegen IMMER** — unabhängig von
Roh/Einfach-Modus (`html.py`, seit #911; als gewollte Invariante PO-approved,
AC-2-Negativ-Test im Bundle #888/#896/#902: Roh-Zelle Wind=25 trägt `background:#fdf4cd`,
vormals `#fbeeb8` — Farbwert seit Bug #1801 S2, s.o.).
Seit dem #888-Fix folgt die Tönung bei Ampel-Zellen dem Katalog-Ampel-Level, im
Roh-Modus den bestehenden Legacy-Schwellen. Die frühere Absolutform „Roh ist Roh =
gar kein Styling" ist damit überholt (Doku-Abgleich #985/#1198).

### Windrichtung: Färbung nach Gegenwind bzw. Sektor (seit Issue #3228, 2026-11-20)

Die Windrichtung ist eine abgeleitete Ampelgröße (ADR-0126). Gefärbt wird nicht nach der Gradzahl,
sondern nach dem Wert `wind_unerwuenscht_kmh` je Stunde (Helfer `zeilen_wert_kmh` in
`src/services/windrichtung.py`; Schwellen über `AMPEL_ABGELEITET` in `src/app/ampel.py`; die Ampel
`hat_ampel` bleibt für Windrichtung `False`).

- **Trip, Modus `gegenwind`** (Vorlage `radtour`): Gegenwindkomponente der Etappe, Fahrtpeilung = Luftlinie
  Start → Ende. Unter 300 m Luftlinie (Rundkurs) gibt es keine Peilung und damit keine Färbung.
- **Modus `sektoren`** (Trip und Ortsvergleich): volle Windstärke, wenn der Wind aus einem markierten
  Sektor kommt; sonst 0.
- **Ortsvergleich mit geerbtem `gegenwind`:** ohne Fahrtrichtung kein Wert, also keine Färbung.
- **Standardfall (Kompass in der Wind-Zelle):** Die Zelle zeigt die höhere der beiden Stufen aus
  Windstärke und Gegenwind/Sektor, nicht die Summe. Zellfarbe, Ampelpunkt und Zeilenpunkt nutzen dieselbe
  Stufe (`mit_windrichtung` in `src/output/renderers/email/helpers.py`).
- **Roh-Modus mit eigener WDir-Spalte:** die Spalte wird nach dem km/h-Wert gefärbt, nicht nach dem Grad.
- **Ortsvergleich:** die Stufe der Windrichtungs-Zelle ist die des höchsten Stundenwerts
  (`src/output/renderers/email/compare_html.py`, `_sev_windrichtung`).
- **Ausblick-Spalte** (`outlook.py`): abgeleitete Ampelgrößen werden nie nach dem Gradwert gefärbt; die
  Ausblick-Zelle bleibt bis zur Scheibe S3 ungefärbt.
- Rückenwind, Seitenwind und Windstärken unter der gelben Grenze bleiben ungefärbt. Alt-Trips ohne
  Feld `modus` bleiben unverändert.
- Telegram, SMS und Premium-SMS bleiben in S2 unverändert; sie folgen in S3 (Epic #3222).

---

## Viewport-spezifisches Rendering (ab Issue #831)

Die HTML-Briefing-Mail enthält zwei Stundentabellen-Varianten, die per CSS-Mediaqueries
geschaltet werden:

| Viewport | CSS-Klasse | Rendering | Display |
|----------|-----------|-----------|---------|
| Desktop (≥601px) | `.desktop-only` | `_render_html_table()` mit `html=True` | HTML-Tabelle mit Ampel-Emojis im Einfach-Modus |
| Mobile (≤600px) | `.mobile-compact` | `_render_mobile_compact_rows()` → delegiert an `_render_html_table` | IMMER bordierte HTML-Tabelle (byte-identisch zur Desktop-Tabelle, in `overflow-x:auto` gewickelt) — auch im Roh-Modus |

**Mobile rendert IMMER als Tabelle** (fix-mobile-grid-decouple-ampel): `_render_mobile_compact_rows`
delegiert in beiden Modi an `_render_html_table`; `indicator_keys` steuert nur noch die
Ampel-FÄRBUNG innerhalb der Zellen, nicht mehr Tabelle-vs-Monospace. Der frühere
Monospace-`<pre>`-Block im Roh-Modus (Issue #636) ist abgelöst — die frühere Fassung
dieses Absatzes (#831) beschrieb ihn noch als aktuell (Doku-Abgleich #1198; Ist-Verhalten
gemessen bei #1432: beide Fassungen jeder Stundentabelle sind `<table>`-Blöcke).

**Resultat:** Kein Modus-Mismatch mehr zwischen Desktop- und Mobile-Ansicht derselben Nachricht.

## Sprache

Die Sprache der Mail folgt der **Kontosprache** des Empfängers (`language`, ADR-0104). Sie gilt für
alle Mail-Arten; der Kopf `X-GZ-Lang` nennt sie (`de` oder `en`).

**Was wechselt:** Betreff, Abschnitts- und Tabellenüberschriften, Hinweise und Legendenzeilen aus den
Katalogbereichen `mail.*`, `vergleich.*`, `alarm.*` und `warnung.*` (`src/i18n/messages/{de,en}/`);
Wettergrößen in voller Form über `label(lang)` aus dem Metrik-Register (`src/app/metric_catalog.py`). Die Niederschlagsart (`precip_type`) ist ein Wort aus `vergleich.niederschlagsart.*` über `precip_type_label()` (`src/output/metric_format.py`, seit 2026-11-21, #3139); Trip-Mail und Orts-Vergleich nutzen dieselbe Quelle.

**Was bleibt:** Spaltenkürzel `col_label` und `compact_label`, Kürzel und Token-Zeile, `sms_code`,
Kanal- und Providernamen, Orte, Trip-Namen. Amtliche Warntexte bleiben in ihrer Quellsprache.

**Woher:** `resolve_user_lang(user_id)` einmal je Nutzer im Orchestrierer; der Renderer bekommt
`lang` als Schlüsselwort mit Default `"de"`. Kein Modulzustand, keine Sprache aus dem Empfänger
einer Adresse.

**Prüfung:** Golden-Dateien `tests/golden/<paket>/<fall>.de.(html|txt)` sind byte-genau gleich zur
deutschen Ausgabe; `<fall>.en.*` ist die englische Review-Fassung derselben Fixture. Der
Mail-Validator (`docs/reference/mail_validators.md`) prüft die Erwartungen in der Kopfsprache.
