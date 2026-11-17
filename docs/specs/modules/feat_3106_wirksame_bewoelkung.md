---
entity_id: feat_3106_wirksame_bewoelkung
type: module
created: 2026-11-17
updated: 2026-11-17
status: approved
version: "1.0"
tags: [cloud, weather, normalisierung, kanal-paritaet]
---

# Wirksame Bewölkung: Schleierwolken zählen halb, eine Regel für alle Kanäle

## Approval

- [x] Approved (PO-Freigabe 2026-11-17, Option „Freigeben“)

## Purpose

Die Größe „Bewölkung" zeigt künftig die **wirksame Bewölkung** am Standort: Dichte tiefe und mittelhohe Wolken zählen voll, dünne hohe Wolken (Cirrus, „Schleierwolken") nur halb. Damit erscheint ein Himmel voller Schleierwolken, unter dem die Sonne noch scheint, nicht mehr als ☁️ 100 %. Gleichzeitig werden die heute vier getrennten Rechenwege der Bewölkung auf **eine** Regel an **einer** Stelle zusammengeführt (Issue #3106, PO-Meldung Aabenraa 2026-11-17).

## Source

- **Neu (Domäne):** `src/app/cloud_cover.py`, `wirksame_bewoelkung()`, `normalisiere_bewoelkung()`
- **Anwendung (Normalisierung):** `src/providers/openmeteo.py` (`OpenMeteoProvider.fetch_forecast`, ein gemeinsamer Ausgang), `src/providers/fixture.py` (`FixtureProvider.fetch_forecast`)
- **Entfällt:** `WeatherMetricsService.calculate_effective_cloud` (`src/services/weather_metrics.py`) und alle Aufrufer
- **Schicht:** Python-Core. Go und Frontend rechnen nichts aus Bewölkungswerten (Survey 2026-11-17), keine Änderung dort.

## Ist-Stand (Analyse 2026-11-17)

Vier Wege führen die Bewölkung zum Nutzer, mit unterschiedlicher Regel:

1. **Roh direkt:** Mail-Zusammenfassungs-Pille (`email/helpers.py` `_pill_for_metric`), Trip-SMS-Token `CT` (`sms_trip.py`), Tagesmittel `_compute_cloud_cover` (`weather_metrics.py`, speist Trip-Zusammenfassung, Ausblick Trip und Vergleich, „vs. gestern"), Stunden-JSON `api/routers/compare.py`, Alt-CLI `aggregation.py`.
2. **Roh über den Katalog (`dp_field="cloud_total_pct"`):** alle Stundentabellen (Mail, Telegram, Vergleich), Nachtblöcke, Sonnen-Emoji-Rückfall, Ampel-Stundenmarke, Ad-hoc-Abfrage `CT`.
3. **Effektiv (`calculate_effective_cloud`, ab 2500 m ohne tiefe Wolken):** nur die Übersichtszeile des Ortsvergleichs (`comparison_engine.py`) inkl. Vergleichs-SMS und Bewertung, und der Sonnenstunden-Rückfall ohne DNI.
4. **Toter Rohpfad:** `cloud_min/max/avg` in `comparison_engine.fetch_forecast_for_location`, von keinem Aufrufer gelesen.

Folge schon heute: Der Ortsvergleich zeigt in der Übersicht einen anderen Wert als in den Stundenwerten derselben Stunden.

## Design

### Die eine Regel (`app/cloud_cover.py`, Domänenschicht, rein, ohne I/O)

```
HOHE_WOLKEN_GEWICHT = 0.5
HOCHLAGE_SCHWELLE_M = 2500   # wandert aus WeatherMetricsService hierher

wirksame_bewoelkung(gesamt, tief, mittel, hoch, hoehe_m) -> Optional[int]
  - fehlt mittel ODER hoch            -> gesamt unverändert (Anbieter ohne Schichten)
  - tief_zaehlt = hoehe_m is None or hoehe_m < HOCHLAGE_SCHWELLE_M
  - fehlt tief und tief_zaehlt        -> gesamt unverändert
  - dicht   = max(tief, mittel) wenn tief_zaehlt, sonst mittel
  - bezug   = gesamt               wenn tief_zaehlt und gesamt bekannt
              max(mittel, hoch)     sonst (tiefe Wolken unter dem Standort ausgeblendet)
  - wirksam = dicht + max(0, bezug - dicht) * HOHE_WOLKEN_GEWICHT
  - Ergebnis gerundet (round half up), auf 0..100 begrenzt
```

Begründung: Der Anteil der Gesamtbewölkung, der nicht durch tiefe oder mittelhohe Wolken erklärt ist, stammt aus hohen Wolken und wird halb gewichtet; die Überlappungsannahme des Modells bleibt im Gesamtwert erhalten. Das folgt der etablierten Praxis „modifizierte Gesamtbewölkung" (DWD `CLCT_MOD`, dünne hohe Wolken mit reduziertem Gewicht). Die bisherige Hochlagen-Formel `(mittel+hoch)//2` geht in derselben Regel auf; sie unterschätzte reine mittelhohe Bewölkung (mittel 100, hoch 0 → bisher 50).

### Wo die Regel angewendet wird: einmal, in der Normalisierung

- `normalisiere_bewoelkung(timeseries, hoehe_m)` setzt je Datenpunkt `cloud_total_model_pct` (neues Feld, Modellwert unverändert, nur Transparenz/Prüfung) und überschreibt `cloud_total_pct` mit der wirksamen Bewölkung. **Idempotent:** Ist `cloud_total_model_pct` schon gesetzt, wird von dort gerechnet.
- Aufruf **genau einmal** je Abruf am gemeinsamen Ausgang von `OpenMeteoProvider.fetch_forecast` (alle Rückgabepfade inkl. Modell-Rückfall und Anbieter-Totalausfall laufen durch einen Abschluss-Helfer) mit `location.elevation_m`, sowie in `FixtureProvider.fetch_forecast` (Offline-Testmodus spiegelt Open-Meteo).
- Damit erreicht derselbe Wert ohne weitere Leser-Änderung alle Wege aus 1 und 2 sowie die Ampel (Schwellen werten die wirksame Bewölkung).
- `calculate_effective_cloud` entfällt; `comparison_engine` mittelt `cloud_total_pct` direkt, `calculate_sunny_hours`-Rückfall nutzt `cloud_total_pct` direkt, `get_weather_symbol` ebenso. `above_low_clouds` (Stern-Markierung) liest `HOCHLAGE_SCHWELLE_M` aus `app/cloud_cover.py`.
- Toter Rohpfad (4) wird entfernt.
- Feldname `cloud_total_pct`, Katalog-`dp_field`, Kürzel `CT`/`C`, Ampel-Schwellen und gespeicherte Nutzerdaten bleiben unverändert (keine Migration).

### Verworfene Alternativen

- **Neues abgeleitetes Feld + `dp_field` umhängen:** gespeicherte Formate (`metric_formats`) und Stundenauswahlen sind teils über den Feldnamen verschlüsselt, das hätte eine Datenmigration erzwungen; zusätzlich blieben fünf Rohleser einzeln umzubauen.
- **Regel in jedem Leser:** genau der heutige Zustand mit vier Wegen.

## Estimated Scope

- **LoC:** ~120 Quellcode (davon ~50 neu in `app/cloud_cover.py`, Rest Entfernen/Umhängen), Tests zusätzlich
- **Files:** ~7 Quelldateien + Tests + Doku
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint` | Datenmodell | neues Feld `cloud_total_model_pct` |
| `OpenMeteoProvider` / `FixtureProvider` | Provider | Anwendung der Regel |
| `metric_format.cloud_emoji` | Darstellung | unveränderte Symbolskala (≤10 ☀️, ≤30 🌤️, ≤70 ⛅, ≤90 🌥️, >90 ☁️) |
| ADR-0122 | Entscheidung | wirksame Bewölkung als normalisierte Größe |

## Expected Behavior

- **Input:** Open-Meteo-Stundenwerte mit Gesamt-, tiefer, mittelhoher und hoher Bewölkung; Standorthöhe.
- **Output:** `cloud_total_pct` = wirksame Bewölkung, überall gleich verwendet; `cloud_total_model_pct` = Modellwert.
- **Side effects:** keine Datenmigration; neue Wetter-Schnappschüsse enthalten die wirksame Bewölkung.

## Acceptance Criteria

- **AC-1:** Given eine Stunde an einem Ort unter 2500 m mit nur hohen Wolken (tief 0 %, mittel 0 %, hoch 100 %, gesamt 100 %) / When für diesen Ort ein Ortsvergleich- oder Trip-Briefing erzeugt wird / Then zeigt die Bewölkung dieser Stunde 50 % bzw. im Einfach-Modus ⛅ statt ☁️, gleich in E-Mail, Telegram, SMS und Premium-SMS.
  - Test: Briefing aus Fixture-Daten rendern, Stundenwert in allen vier Kanälen prüfen.

- **AC-2:** Given eine Stunde mit dichter mittelhoher Bewölkung (tief 0 %, mittel 100 %, hoch 100 %, gesamt 100 %) / When das Briefing erzeugt wird / Then zeigt die Bewölkung weiterhin 100 % bzw. ☁️.
  - Test: wie AC-1 mit dichter Schicht.

- **AC-3:** Given eine gemischte Stunde (tief 20 %, mittel 0 %, hoch 80 %, gesamt 84 %) / When das Briefing erzeugt wird / Then zeigt die Bewölkung 52 % (20 + (84 − 20) × 0,5).
  - Test: Zahl im Roh-Modus der Stundentabelle.

- **AC-4:** Given ein Ort ab 2500 m mit nur tiefen Wolken unter dem Standort (tief 100 %, mittel 0 %, hoch 0 %) / When Ortsvergleich oder Trip erzeugt wird / Then zeigt die Bewölkung 0 % bzw. ☀️ in der Übersicht UND in den Stundenwerten, die Stern-Markierung „über den tiefen Wolken" bleibt im Ortsvergleich erhalten.
  - Test: Übersichtszeile und Stundentabelle desselben Orts.

- **AC-5:** Given ein Ort ab 2500 m mit dichter mittelhoher Bewölkung (tief 0 %, mittel 100 %, hoch 0 %) / When das Briefing erzeugt wird / Then zeigt die Bewölkung 100 % (bisher fälschlich 50 %).
  - Test: Übersichtszeile Ortsvergleich.

- **AC-6:** Given ein Datensatz ohne Wolkenschichten (nur Gesamtbewölkung, z. B. Ersatzanbieter bei Open-Meteo-Ausfall) / When das Briefing erzeugt wird / Then zeigt die Bewölkung unverändert die Gesamtbewölkung.
  - Test: Stundenwert mit fehlenden Schichten.

- **AC-7:** Given derselbe Ort mit denselben Stundenwerten / When Übersicht (Tagesmittel), Stundentabelle, Zusammenfassungs-Pille, SMS-Token `CT`, Ausblick und Ampel-Färbung erzeugt werden / Then beruhen alle auf derselben wirksamen Bewölkung (das Tagesmittel ist das Mittel der angezeigten Stundenwerte).
  - Test: Werte aller Flächen für einen Ort gegeneinander.

- **AC-8:** Given eine Stunde mit 100 % Schleierwolken bei der Ampel-Grundeinstellung für Bewölkung (gelb ab 70 %, rot ab 90 %) / When das Briefing erzeugt wird / Then ist diese Stunde nicht rot markiert.
  - Test: Ampel-Markierung in Mail und Telegram.

- **AC-9:** Given Daten mit Sonneneinstrahlung (DNI) / When die Sonnenstunden berechnet werden / Then bleiben sie unverändert (sie beruhen weiter auf der Einstrahlung, nicht auf der Bewölkung).
  - Test: Sonnenstunden vor/nach für denselben Datensatz gleich.

## Known Limitations

- **Übergangstag:** „vs. gestern" vergleicht am ersten Tag nach dem Ausrollen einen alten Schnappschuss (Gesamtbewölkung) mit einem neuen (wirksame Bewölkung). Der Unterschied verschwindet nach einem Tag.
- **Vorhersagefehler bleiben:** Kommt eine Front früher oder später als vorhergesagt (Aabenraa 2026-11-17: alle Modelle 1–2 h zu früh, zudem mittelhohe Wolken ab 10 Uhr vorhergesagt), behebt diese Änderung das nicht. Am Beispieltag hätte sie die Stunde 9 Uhr verbessert (☁️ 66 % → ⛅ 33 %), nicht 10–11 Uhr.
- **Go `/api/forecast`** liefert weiter die Rohwerte von Open-Meteo; keine Oberfläche zeigt daraus Bewölkung an.
- **Gewicht 0,5** ist eine feste Setzung nach Praxis, keine eigene Eichung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0122
- **Rationale:** Datenmodell/Normalisierung ist Entscheidungsfläche; die Größe „Bewölkung" ändert ihre Bedeutung von Modell-Gesamtwert zu wirksamer Bewölkung.

## Changelog

- 2026-11-17: v1.0 Entwurf (#3106).
- 2026-11-17: v1.0 vom PO freigegeben.
