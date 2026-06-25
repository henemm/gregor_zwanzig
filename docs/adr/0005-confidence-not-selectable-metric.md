# ADR-0005: Confidence ist keine pro-Etappe wählbare Wetter-Metrik

- **Status:** Akzeptiert
- **Datum:** 2026-06-10
- **Bezug:** GitHub-Issue #710 (Regress nach #424-Fix), Issue #473 (frühere, unvollständige Entfernung)

## Kontext

`confidence_pct` (Vorhersage-Verlässlichkeit, abgeleitet aus der Open-Meteo-Ensemble-API) wurde
zeitweise wie eine wählbare Wetter-Metrik behandelt und tauchte im Trip-Editor / Wizard Step 3 in der
Metrik-Auswahl auf. Das ist konzeptionell falsch: Confidence ist eine **Meta-Aussage** über die
mehrtägige Ensemble-Divergenz — **keine** lokale Wettergröße wie Temperatur oder Wind. Die Funktion
wurde bereits einmal entfernt (#473), kam aber durch einen späteren Fix (#424) unbemerkt zurück (#710).
Genau dieser Regress war der Auslöser, die Entscheidung als verbindliches Record festzuhalten.

## Entscheidung

Confidence ist **keine** pro-Etappe wählbare Metrik. Sie darf **ausschließlich** erscheinen als:

1. **Vorhersage-Verlässlichkeits-Hinweis** im E-Mail-Textblock („Ab Mittwoch nimmt die Unsicherheit zu …")
2. **SMS-Token** (`C+` / `C~` / `C?` für Sicherheits-Bänder)
3. **Interne Aggregation/Scoring** (Berechnung, Persistenz)

**Niemals** wieder im Trip-Editor, Wizard Step 3, in der Metrik-Auswahl oder als pro-Etappe-Spalte.

Technisch umgesetzt: `MetricDefinition.selectable = false` für `confidence`; `GET /api/metrics`
filtert auf `selectable = true`. **Backward Compatibility:** Alte Trips mit aktiviertem `confidence`
in `display_config` laden weiterhin still, die Metrik wird in Render-Pfaden aber ignoriert (keine
Spalte, keine Vorschau-Werte).

## Verworfene Alternativen

- **Confidence als wählbare Metrik anbieten** — verworfen: vermischt eine Meta-Verlässlichkeitsaussage
  mit lokalen Wettergrößen; für Nutzer irreführend.
- **Confidence komplett aus dem System entfernen** — verworfen: als Verlässlichkeits-Hinweis,
  SMS-Token und internes Scoring ist sie wertvoll. Nur die *Auswählbarkeit als Metrik* entfällt.

## Konsequenzen

- **Positiv:** Klare konzeptionelle Trennung zwischen Wettergrößen und Verlässlichkeits-Meta-Aussage;
  Schutz vor erneutem Regress.
- **Negativ / Preis:** Sonderbehandlung von `confidence` (selectable-Flag, API-Filter,
  Render-Ignorierung für Alt-Trips) muss dauerhaft bestehen bleiben.
- **Folgepflichten:** **PO-Entscheidung, final.** Kein Fix und kein Feature darf `confidence` wieder
  selektierbar machen. Bei Berührung der Metrik-Auswahl ist diese Regel zu prüfen.
