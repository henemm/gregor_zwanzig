---
entity_id: issue_1216_official_alert_template
type: module
created: 2026-07-10
updated: 2026-07-20
status: draft
version: "1.1"
tags: [official-alerts, alert-rendering, email, telegram, sms, design-fidelity]
---

# Amtliche-Warnung-Alarm: Format-Fidelity zur Design-Vorlage (Slice 1: gemeinsame Renderer + Trip-Standalone)

## Approval

- [x] Approved (PO „go", 2026-07-10)

## Purpose

Die eigenständige amtliche-Warnung-Alarm-Mail (heute: nackter Text, Betreff „[KHW 403] Amtliche Warnung", keine SMS) folgt der freigegebenen Claude-Design-Vorlage `Gregor 20 - Alert Amtliche Warnung.html` über alle drei Kanäle. Diese Spec liefert die **kontext-agnostischen Präsentations-Renderer** (von Beginn an für Trip UND Ortsvergleich gebaut) und verdrahtet den **Trip-Standalone-Alarm** damit. Der Ortsvergleich-Standalone-Alarm nutzt dieselben Renderer in Slice 2 (Folge unter #1216).

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` (MODIFY — 4 neue Renderer + hazard-Mapping + DE-Wochentag)
- **File:** `src/services/notification_service.py` (MODIFY — `send_official_alert` verdrahten)
- **File:** `src/services/trip_alert.py` (MODIFY klein — `total_segments`/Kurzname durchreichen)
- **Identifier:** `render_official_alert_subject`, `render_official_alert_html`, `render_official_alert_telegram`, `render_official_alert_sms`, `OfficialAlertNotice`

Schicht: **Python-Core / Domain-Backend** (`src/output/`, `src/services/`) — kein Frontend, kein Go.

## Estimated Scope

- **LoC:** ~200–240 (renderer-lastig; nahe am 250-Limit — falls überschritten, PO vor Override fragen)
- **Files:** 3 MODIFY + 1–2 CREATE (Tests)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `dedupe_official_alerts` (official_alerts.py) | reuse | Bündelung (dedup_id\|region_label\|label, hazard; höchste Stufe je Gruppe) + Segment-ID-Union |
| `format_segment_reference` (official_alerts.py) | reuse | Segment-Bezug (Range/Aufzählung/Verdichtung, 🏁 Ziel) |
| `email/design_tokens.py` | reuse | Farben/Fonts fürs HTML (G_INK, G_PAPER, G_ALERT_L2/L3/L4, G_SUCCESS, FONT_UI, FONT_DATA) |
| `utils.timezone.local_fmt` | reuse | Lokale Zeitformatierung |
| `OfficialAlert` (official_alerts/models.py) | consume | Felder: hazard, level 1–4, label, valid_from/to, region_label, url, dedup_id |
| Trip-Modell (`total_waypoints`/Segmentzahl) | consume | „gesamte Route"-Erkennung |

## Implementation Details

### Eingabe-Kontrakt (kontext-agnostisch)
Die vier Renderer nehmen eine bereits deduplizierte Liste `list[OfficialAlertNotice]` — ein leichtgewichtiges Präsentations-DTO, das der Aufrufer (Trip heute, Compare in Slice 2) füllt:

```python
@dataclass(frozen=True)
class OfficialAlertNotice:
    alert: OfficialAlert          # Stufe, hazard, label, valid_from/to, region_label, url
    affected_scope: str           # vorformatierter Ortsbezug: "Segment 2–4, 🏁 Ziel" (Trip) | "nur Ort B" (Compare)
    affected_segment_ids: list[str]   # für Chip-Darstellung betroffen/frei (Trip); Compare: Ortsschlüssel
    all_segment_ids: list[str]        # Gesamtmenge → "gesamte Route"/"alle Orte"-Erkennung + durchgestrichene Chips
```

Der Aufrufer dedupliziert via `dedupe_official_alerts` und baut `affected_scope` über `format_segment_reference` (Trip) bzw. Orts-Formatter (Compare) — die Renderer sind damit frei von Trip-/Compare-Spezifika.

### Stufen-Abbildung
- Level → Wort/Emoji: 2=GELB 🟡, 3=ORANGE 🟠, 4=ROT 🔴 (Level 1 GRÜN → siehe Known Limitations).
- Skala-Position „N/3": GELB=1/3, ORANGE=2/3, ROT=3/3.
- Betreff/Reihenfolge/Meter: **höchste Stufe führt** (level absteigend), bei Gleichstand nach `valid_from`.

### hazard → (Anzeige, SMS-Kürzel) — Mapping

> **Aktualisiert 2026-07-20 (PO-Entscheidung, Nachtrag zu Issue #1318/#1220,
> `docs/specs/modules/sms_official_alert_tokens.md`):** die SMS-Kürzel-Spalte dieser Tabelle
> war ursprünglich eine eigene, deutsch abgeleitete Liste, unabhängig vom Trip-Briefing-SMS.
> Das ist durch #1318 aufgelöst worden — **es gibt nur noch einen Kürzel-Katalog**
> (`src/output/tokens/hazard_symbols.py`), international verständlich, von diesem Renderer UND
> der Briefing-Token-Zeile gemeinsam genutzt. Die alten, hier ursprünglich definierten Kürzel
> `HZ`/`ST`/`RR`/`GL`/`ZG`/`WB` sind **ersatzlos ersetzt** (nur `TH`/`SN` stimmten zufällig
> bereits überein). Die **Anzeige-Spalte** (deutsches Klartext-Label) bleibt unverändert und
> weiterhin hier verantwortet — nur die SMS-Kürzel-Spalte wechselt die Quelle. Details, ACs und
> Rationale: siehe `sms_official_alert_tokens.md` AC-13/AC-14.

| hazard | Anzeige | SMS (ab #1318, aus `hazard_symbols.py`) | SMS (vor #1318, Original dieser Spec) |
|--------|---------|------------------------------------------|-----------------------------------------|
| extreme_heat | Hitze | `HT` | ~~HZ~~ |
| thunderstorm | Gewitter | `TH` | TH (unverändert) |
| extreme_cold | Kälte | `CD` | ~~KL~~ |
| wind_gust | Sturm | `W` | ~~ST~~ |
| rain | Starkregen | `HR` | ~~RR~~ |
| snow | Schneefall | `SN` | SN (unverändert) |
| black_ice | Glatteis | `IC` | ~~GL~~ |
| access_ban | Zugang gesperrt | `CL` | ~~ZG~~ |
| wildfire_risk | Waldbrand-Gefahr | `FR` | ~~WB~~ (Nachzug #1239 Runde 2, F004) |
| (unbekannt) | `label` | erste 2 ASCII-Großbuchstaben aus hazard (unverändert) | — |

### DE-Wochentag
Neuer Helfer `_de_weekday_short(dt, tz)` → {Mo,Di,Mi,Do,Fr,Sa,So} (ersetzt locale-abhängiges `%a`, das „Fri" statt „Fr" liefert). Datum `%d.%m.`.

### Gültigkeit-Formatierung
- valid_from 00:00 und valid_to 23:59 desselben Tages → „`<Tag> <dd.mm.>` · ganztägig".
- sonst → „`<Tag> <dd.mm.>` · `HH:MM`–`HH:MM`" (gleicher Tag) bzw. mit zweitem Datum bei Tagesübergang.
- fehlende Zeiten → „Gültig: unbekannt".

### E-Mail-HTML (Vorlagen-Struktur)
Verdict-Badge („N amtliche Warnungen"; bei gemischt „· höchste Stufe X") → H1-Satz → **einheitliche Stufe: Warnstufen-Leiter** GELB→ORANGE→ROT (aktive Stufe hervorgehoben) / **gemischte Stufen: pro Warnung Eskalations-Meter** (gefüllte Punkte = Stufe, „X · N/3") → Warnungs-Block (Typ, Gültig, Route mit Segment-Chips: betroffen normal, frei durchgestrichen) → Quelle-Zeile → Footer „Stand: heute HH:MM · abgerufen bei <Quelle>". Farben/Fonts aus Design-Tokens.

### Telegram
Fette erste Zeile: `<kurz> · <Reichweite> · Warnstufe <Stufe> (N/3)` (einheitlich) bzw. `… · höchste Stufe <Stufe> (N/3)` (gemischt). Darunter je Warnung `<emoji> <Typ> — <Gültig>`; Abschlusszeile Reichweite + Quelle. Höchste Stufe zuerst.

### SMS (GSM-7, ≤140, ASCII)
- Einheitliche Stufe: `<KHW> AMT <STUFE>N/3: <code> <Tag>[<zeit>] + …, <scope>`.
- Gemischte Stufen: `<KHW> AMT: <code> <STUFE> <Tag><zeit> <seg> + …` — jede Warnung mit Stufen-Wort, höchste zuerst.
- Kein Emoji, kein Δ/Pfeil; `_ascii()`-Normalisierung; Budget-Kürzung analog `render_sms`.
- `<code>` = das SMS-Kürzel aus der Tabelle oben (ab #1318 aus `hazard_symbols.py`, siehe Update-Hinweis).

### Verdrahtung `send_official_alert`
- E-Mail: `render_official_alert_html` → `send(..., html=True, mail_type="official-alert")` (statt Plain).
- Betreff: `render_official_alert_subject(...)` (statt `[{trip.name}] Amtliche Warnung`).
- Telegram: `render_official_alert_telegram(...)`.
- **SMS: neuer Zweig** `render_official_alert_sms(...)` → `SMSOutput.send(...)`, wenn `sms` in `effective_channels` und `can_send_sms()`.
- `trip_alert._send_official_alert_only` reicht Gesamt-Segmentzahl + Trip-Kurzname durch.

## Expected Behavior

- **Input:** deduplizierte `list[OfficialAlertNotice]` (Trip-Aufrufer), Trip-Kurzname, Zeitzone.
- **Output:** Betreff-String, HTML+Plain-Mailbody, Telegram-Text, SMS-Text — alle im Vorlagen-Format.
- **Side effects:** Versand über konfigurierte Kanäle; `alert_state` fortschreiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip „KHW 403" mit zwei amtlichen GELB-Warnungen (Hitze Fr ganztägig, Gewitter Sa 15–21 Uhr), beide über die gesamte Route / When der Trip-Standalone-Alarm erzeugt wird / Then lautet der **Betreff** `[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)` (Reichweite „gesamte Route", weil betroffene Segmente = alle; höchste/einzige Stufe GELB; beide Typen mit Tag, „+ "-verbunden).
  - Test: Betreff-String-Assert auf `render_official_alert_subject` mit zwei Notice-Objekten; kein Dateiinhalt-Check.

- **AC-2:** Given dieselben zwei GELB-Warnungen / When die **E-Mail-HTML** gerendert wird / Then enthält sie (a) einen Verdict-Badge „2 amtliche Warnungen", (b) genau **eine** Warnstufen-Leiter mit GELB→ORANGE→ROT und GELB als aktiver Stufe (kein Eskalations-Meter, da einheitlich), (c) je Warnung Typ + Gültigkeit („Fr … · ganztägig" bzw. „Sa … · 15:00–21:00") + Segment-Chips, (d) eine Quelle-Zeile mit „GeoSphere Austria". Der String enthält weder „→" noch „%"-Delta (kein Deviation-Vokabular).
  - Test: HTML-Rendering-Assert auf strukturelle Marker + Abwesenheit von Δ/Pfeil; Plausibilität, keine reine String-Presence.

- **AC-3:** Given eine ORANGE-Gewitter-Warnung (Segment 3) und eine GELB-Hitze-Warnung (Segment 1), also **gemischte Stufen** / When Betreff, HTML, Telegram und SMS gerendert werden / Then führt überall die **höchste Stufe (ORANGE)** zuerst: Betreff `[KHW 403] Segment 3 · ORANGE Gewitter (Sa) + GELB Hitze (Fr)`; HTML zeigt **pro Warnung ein Eskalations-Meter** (ORANGE 2/3, GELB 1/3) statt gemeinsamer Leiter; Telegram-Kopf `… · höchste Stufe ORANGE (2/3)`; SMS `KHW403 AMT: TH ORANGE …` vor `HT ORANGE …` (Kürzel ab #1318 aus `hazard_symbols.py` — der ursprüngliche Wortlaut dieses ACs nannte hier `HZ`, siehe Update-Hinweis).
  - Test: je Kanal ein Assert auf Reihenfolge (ORANGE-Warnung vor GELB) + Meter-statt-Leiter im HTML.

- **AC-4:** Given eine einzelne GELB-Gewitter-Warnung, die **nur Segment 2–4** eines 4-Segment-Trips (Segmente 1,2,3,4 + Ziel) betrifft / When Betreff und HTML gerendert werden / Then nennt der Betreff `Segment 2–4` (nicht „gesamte Route"), und im HTML sind die **nicht betroffenen** Segment-Chips (Segment 1, Ziel) **durchgestrichen** dargestellt, die betroffenen normal.
  - Test: Betreff-Assert + HTML-Assert auf durchgestrichen-Markup genau für die freien Segmente.

- **AC-5:** Given ein Trip mit `sms` in den aktiven Kanälen und eine GELB-Hitze- + GELB-Gewitter-Warnung über die gesamte Route / When `send_official_alert` läuft / Then wird eine **SMS versendet** (heute gar keine), im GSM-7/ASCII-Format ≤140 Zeichen, Inhalt beginnt mit `KHW403 AMT GELB1/3:` und enthält die Kürzel `HT` und `TH` (ab #1318; ursprünglich `HZ`/`TH`, siehe Update-Hinweis) sowie den Reichweiten-Token `ges.Route`; sie enthält kein Emoji und kein „→".
  - Test: Über `mail_sink`/SMS-Spy prüfen, dass der SMS-Kanal aufgerufen wird; Assert auf Länge ≤140, ASCII-only, Token-Inhalt.

- **AC-6:** Given eine amtliche Warnung mit valid_from = Freitag 00:00 und valid_to = Freitag 23:59 (lokale Zeit) / When die Gültigkeit gerendert wird / Then erscheint „**Fr** … · ganztägig" — deutsches Wochentagskürzel „Fr" (nicht „Fri") und „ganztägig" statt „00:00–23:59".
  - Test: Assert auf `_de_weekday_short`/Gültigkeits-Formatter für ganztägigen Zeitraum, deutsch.

- **AC-7:** Given der Trip-Standalone-Alarm mit E-Mail als aktivem Kanal / When `send_official_alert` läuft / Then wird die E-Mail als **HTML** versendet (`html=True`), nicht mehr als reiner Text (`html=False`), und der Betreff ist der neue sprechende Betreff aus AC-1 — der frühere Betreff `[KHW 403] Amtliche Warnung` erscheint nicht mehr.
  - Test: `send_official_alert` mit E-Mail-Spy; Assert auf `html=True` und neuen Betreff; Abwesenheit des alten Betreffs.

## Known Limitations

- **Nur Trip-Standalone (Slice 1).** Ortsvergleich-Standalone-Alarm (gleiche Renderer, Orts-Scope, Trigger/State) folgt in Slice 2 unter #1216. Eingebettete Warn-Sektion **innerhalb** der Briefing-/Vergleichs-Mail bleibt unverändert — dafür existiert keine Vorlage (bei Bedarf Claude-Design-Anfrage).
- **Level 1 (GRÜN):** Standalone-Alarme feuern praktisch nur bei neu/eskaliert (Level ≥ 2). Tritt Level 1 dennoch auf, wird es als GRÜN mit Position „0/3" behandelt (kein aktives Leiter-Segment) — Randfall, kein Vorlagen-Bild vorhanden.
- **`[KHW …]`-Präfix** kommt beim Trip aus `trip.name`. Der Ortsvergleich-Kurzname wird in Slice 2 festgelegt.
- **SMS-Kürzel-Spalte seit 2026-07-20 fremdverwaltet:** die SMS-Kürzel-Spalte der hazard-Tabelle wird nicht mehr in diesem Modul gepflegt, sondern importiert aus `src/output/tokens/hazard_symbols.py` (SSOT ab Issue #1318). Änderungen an den Kürzeln gehören künftig dorthin, nicht in `_HAZARD_DISPLAY`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bestehend — ein gemeinsamer Renderer für amtliche Warnungen). Diese Spec erweitert ihn additiv um die Präsentations-Renderer (subject/html/telegram/sms) und das kontext-agnostische `OfficialAlertNotice`-DTO; keine neue ADR nötig, da im Rahmen der etablierten Renderer-Konsolidierung + Konvergenz-Richtung (Epic #1204).
- **Rationale:** Kontext-agnostischer Renderer erfüllt die PO-Vorgabe „gleiche Funktionen für Trip und Ortsvergleich, nichts neu erfinden".

## Changelog

- 2026-07-10: Initial spec (Slice 1) erstellt
- 2026-07-20: **SMS-Kürzel-Spalte aktualisiert** (PO-Entscheidung, Nachtrag zu Issue #1318/#1220): die hazard→SMS-Kürzel-Tabelle wechselt von einer eigenen, deutsch abgeleiteten Liste auf den international verständlichen Katalog aus `src/output/tokens/hazard_symbols.py`, geteilt mit dem Trip-Briefing-SMS. AC-3/AC-5 entsprechend mit den neuen Kürzeln versehen (Kürzel-Änderung selbst ist Gegenstand von `sms_official_alert_tokens.md` AC-13/AC-14, hier nur nachgezogen). Datei nicht gelöscht (Transparenz-Prinzip), nur die betroffene Spalte/ACs aktualisiert.
