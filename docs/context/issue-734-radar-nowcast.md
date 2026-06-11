# Context: Issue #734 — Echtes Radar/Blitz-Nowcast für Frankreich & global (GR20-Lücke)

## Request Summary
Der `RadarNowcastService` nutzt echtes Radar nur für DE (RADOLAN/BrightSky) und AT (INCA).
Für den Kern-Use-Case **GR20 = Korsika/Frankreich** fällt er auf Open-Meteo `minutely_15`
(generisches Modell, kein hochauflösendes Radar/Nowcast). Ziel: bessere, FR/Korsika-taugliche
Nowcast-Daten — und eine Klärung zur Blitz-Quelle.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `src/services/radar_service.py` | Kern: Quellen-Auswahl-Kette `_fetch_frames_with_fallback`, Bbox-Guards `_within_radolan`/`_within_inca`, `NowcastResult`, `format_now_text` |
| `src/providers/brightsky.py` | Vorbild-Provider + `RadarFrame`-Dataclass (`timestamp`, `precip_mm_h`, `is_convective`) |
| `src/providers/geosphere.py` | Vorbild für regionalen Provider (`fetch_nowcast`, Bbox), `BASE_URL`-Pattern |
| `src/providers/openmeteo.py` | Bestehender globaler Fallback (`minutely_15`) |
| `src/services/trip_command_processor.py:971` | `_show_now` — `JETZT`/`### now`-Befehl ruft `get_nowcast` + `format_now_text` |
| `src/services/trip_alert.py:466-565` | Proaktive Radar-Alerts nutzen denselben Service |
| `docs/specs/modules/radar_nowcast.md` | Bestehende Spec (#656) — Quellen-Wahl-Logik dokumentiert |
| `docs/specs/modules/radar_convective_stage.md` | Konvektions-/Gewitter-Stufen-Spec |

## Existing Patterns
- **Koordinaten-basierte Quellen-Kette:** `_fetch_frames_with_fallback(lat,lon)` prüft Bbox-Guards
  in Reihenfolge (RADOLAN → INCA → minutely_15), nimmt erste nicht-leere Antwort. Neue Quelle =
  weiterer Bbox-Guard + `_fetch_*`-Methode, fail-soft (Exception → `[]` → nächste Quelle).
- **`RadarFrame`** ist die gemeinsame Währung: `timestamp` (tz-aware), `precip_mm_h`, `is_convective`.
  Jeder Provider mappt sein Format auf mm/h.
- **Konvektion/Blitz** ist aktuell nur abgeleitet: `is_convective` aus WMO-Codes 95/96/99 — **keine echte Blitz-Quelle**.
- **Source-Label** in `format_now_text` (`radar`/`INCA`/`minutely_15`) — neue Quelle braucht neues Label.
- **Mock-frei (PFLICHT):** Tests via DI-Seam `frame_source=callable` oder echte API-Calls.

## Recherche-Ergebnis der Issue-Kandidaten
| Kandidat | Befund | Eignung |
|----------|--------|---------|
| **RainViewer** | Liefert **nur PNG-Radar-Kacheln**, keine mm/h am Punkt. Wert am Koordinatenpunkt erfordert Tile-Download + Pixel-/Farbdecodierung (grob quantisiert, fragil). Passt nicht zur Punkt-Architektur (`fetch_radar(lat,lon)->mm/h`). | ⚠️ technisch teuer/fragil |
| **Météo-France AROME-PI** | Hochauflösend (1.5 km HD, 15-min) über Frankreich **inkl. Korsika**. Direkt-API (`portail-api.meteofrance.fr`) = WMS/WCS/GRIB (komplex, API-Key). **Aber: dasselbe AROME-Modell ist via Open-Meteo `/v1/forecast` als Punkt-JSON mit `minutely_15=precipitation` verfügbar** (`arome_france_hd_15min`) — gleiche Form wie der bestehende Fallback, kein Key für Non-Commercial. | ✅ sauberster Fit |
| **Blitzortung.org** | **Kommerzielle Nutzung ausdrücklich verboten** ("commercial use ... strongly prohibited"; "demonstration ... via apps is not permitted"). Gregor Zwanzig ist ein kommerzielles Produkt → **rechtlich nicht nutzbar**. | ❌ ToS-Blocker |

## Dependencies
- **Upstream:** `httpx`, Open-Meteo `/v1/forecast` (bereits genutzt), ggf. Météo-France-Portal-API.
- **Downstream:** `_show_now` (JETZT-Befehl, E-Mail+Telegram), `trip_alert` (proaktive Radar-Alerts).

## Risks & Considerations
- **Begriffs-Konflikt:** Issue fordert wörtlich „echtes Radar" + „echte Blitz-Quelle". Technisch/rechtlich
  sauber erreichbar ist für FR/Korsika ein **hochauflösender Modell-Nowcast (AROME 1.5km/15-min)** — kein
  rohes Radar-Pixel. Für den Produkt-Use-Case („regnet's in ~20 Min auf meiner Etappe?") ist AROME-HD
  besser als der heutige generische Fallback und liefert mm/h direkt.
- **Blitz:** Keine saubere, kommerziell-nutzbare Echtzeit-Einschlag-Quelle frei verfügbar. Realistische
  Verbesserung = bessere Konvektions-Signale aus AROME statt separatem Strike-Feed.
- **Open-Meteo Commercial-Key:** Free-Tier ist Non-Commercial/<10k Calls. Projekt nutzt Open-Meteo bereits
  überall — gleiche Posture, kein neues Risiko, aber bei Skalierung perspektivisch Key.
- **Mandantenfähigkeit:** Pfad bleibt nutzergebunden (Trip → Etappe → Waypoint), keine neue user_id-Logik nötig.
- **Bbox-Reihenfolge:** FR-Bbox darf DE/AT nicht überlappend verdrängen (Grenzregionen) — Reihenfolge RADOLAN → INCA → FR-AROME → global.
