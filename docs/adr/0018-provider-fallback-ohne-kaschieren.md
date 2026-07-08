# ADR-0018: Modell-Fallback bei Wetter-Quell-Ausfall — mit Ausweichen, aber ohne Kaschieren

- **Status:** Akzeptiert (PO-„go" 2026-07-08)
- **Datum:** 2026-07-08
- **Bezug:** GitHub-Issue #1115, Spec `docs/specs/modules/issue_1115_openmeteo_model_fallback.md`; Folge-Issues #1127 (Cross-Provider-Redundanz), #1128 (Retry-Bug); verwandt [ADR-0002](0002-met-vs-mosmix-forecast-source.md) (Provider-Auswahl), [ADR-0009](0009-alerts-als-abweichungs-waechter.md)

## Kontext

Am 07./08.07.2026 fiel bei Open-Meteo für ~14 h **ein** Modell-Endpoint aus (`/v1/dwd-icon`, 203× HTTP 503), während alle anderen Endpoints (Météo-France/AROME, MetNo, ECMWF) parallel normal lieferten. Weil `fetch_forecast` stur beim regional gewählten Modell blieb, fielen **alle** Trip-Briefings aus. Open-Meteo ist kein eigener Wetterdienst, sondern ein Verteiler, der genau diese Original-Modelle durchreicht — der Ausfall traf also einen einzelnen Kanal, nicht die Datenlage insgesamt.

Zwei Randbedingungen prägen die Entscheidung: (1) Zuverlässigkeit und maximale Datenqualität sind der Kern des Produkts (Briefing-Werkzeug für Tourenentscheidungen). (2) Der Product Owner benannte als nicht verhandelbar, dass ein Ausweichen **niemals einen Fehler verstecken** darf — ein still degradierter Dauerzustand, der als „alles grün" durchgeht, ist genau das Muster, das in der Vergangenheit echte Probleme verdeckt hat.

## Entscheidung

1. **Intra-Open-Meteo-Modell-Fallback:** Bei HTTP-5xx/Timeout des regional gewählten Modell-Endpoints weicht `fetch_forecast` automatisch auf das nächstbeste abdeckende Modell der `REGIONAL_MODELS`-Prioritätskette aus (feinste Auflösung zuerst, bis globales ECMWF als garantierte Abdeckung). Endpoint-Deduplizierung, da mehrere Modell-Einträge sich denselben Endpoint teilen können.
2. **Kein Ausweichen bei Inhaltsfehler:** Bei 4xx (z. B. Datum außerhalb Vorhersagehorizont) wird **nicht** ausgewichen — dort scheitert jedes Modell, der Fehler muss sichtbar bleiben. Die 5xx/4xx-Unterscheidung läuft strukturell über `ProviderRequestError.status_code`.
3. **Nicht-Kaschieren-Invariante:** Jedes Ausweichen wird in den Daten markiert (`ForecastMeta.fallback_model` = tatsächlich erfolgreiches Modell, `fallback_reason`), protokolliert (`logger.warning` + `openmeteo_calls.jsonl`) und im Health-Aggregat sichtbar. Ein persistenter Ausfall erzeugt ein mit der Ausfalldauer **wachsendes** Signal (`provider_error_streak_since`, `provider_errors_recent_count` in `/api/scheduler/status`), das eine externe Eskalation bis zur Maximalstufe trägt — auch dann, wenn Briefings dank Ausweichen weiter zugestellt werden.

## Verworfene Alternativen

- **Anbieter-übergreifender Fallback (brightsky/geosphere) als erster Hebel** — verworfen: `brightsky` liefert nur Radar-Nowcast (kein `fetch_forecast`), `geosphere` ist AT-fokussiert ohne Coverage-Bounds und ohne Ensemble. Echte Infrastruktur-Unabhängigkeit (Original-Dienste direkt) ist größere, orthogonale Arbeit → ausgelagert nach #1127.
- **Stilles Ausweichen ohne Sichtbarkeit** — verworfen: widerspricht der Kern-Anforderung; hätte den 14-h-Ausfall sogar unsichtbarer gemacht (erfolgreicher Fallback → kein Ausfall-Marker → „grün").
- **Ausweichen auch bei 4xx** — verworfen: würde echte Inhaltsfehler durch Quell-Roulette verschleiern und Fehlalarme erzeugen.

## Konsequenzen

- **Positiv:** Ein einzelner Modell-Kanal-Ausfall führt nicht mehr zum Totalausfall aller Briefings; der reale Incident wäre vollständig abgefangen worden. Degradierte Briefings sind nachvollziehbar und alarmierbar.
- **Negativ / Preis:** Bei Downgrade auf ein gröberes Modell sinkt die räumliche Auflösung (z. B. AROME 1,3 km → ECMWF 40 km) — bewusst akzeptiert als „beste verfügbare Daten statt Totalausfall", sichtbar via `fallback_model`. Open-Meteo bleibt als Verteiler ein Single Point of Failure für den Totalausfall-Fall (→ #1127).
- **Folgepflichten:** Neue degradierbare Datenpfade müssen dieselbe Nicht-Kaschieren-Invariante erfüllen (Marker in Daten + wachsendes Health-Signal). Das Health-Signal zählt nur Kern-Briefing-Quellen (`briefing`, `briefing_nacht`), nicht Anreicherung (`ensemble`/`vergleich`/…) — bei neuen Kern-Quellen ist `coreBriefingSources` zu erweitern. Die BetterStack-Eskalationsleiter (Infra) muss das Signal auswerten.
