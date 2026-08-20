# ADR-0058: Wegpunkt-Höhe wird an die Provider-Schnittstelle durchgereicht — keine eigene Höhenphysik

- **Status:** Akzeptiert (PO-„go" 2026-08-20)
- **Datum:** 2026-08-20
- **Bezug:** GitHub-Issue #1991, Spec `docs/specs/modules/wegpunkt_hoehe_provider.md`; verwandt [ADR-0018](0018-provider-fallback-ohne-kaschieren.md) (Provider-Asymmetrie/Fallback ohne Kaschieren)

## Kontext

`Location.elevation_m` (`src/app/config.py:92`) ist für jeden Trip-Wegpunkt und jeden
Ortsvergleichs-Ort gefüllt, wurde aber beim Bau der HTTP-Anfrage an Open-Meteo nie mitgeschickt —
weder in der Hauptvorhersage noch im Ensemble-Abruf, dem Wolken-Abruf über GeoSphere oder dem
Kurzfrist-Nowcast. Open-Meteo rechnet ohne diese Angabe mit der Höhe seiner eigenen, geglätteten
Geländekarte statt der echten Höhe des Wegpunkts. Eine Ausgangsmessung (2026-08-20, echte API)
zeigt Abweichungen bis 6,2 °C an einem einzigen Punkt (Dresdner Hütte, Stubai — Modell rechnet
776 m zu hoch), mitbetroffen sind Nullgradgrenze, Niederschlag und Wettercode.

Das Höhen-Soll war bislang nirgends festgelegt — weder „Modellhöhe akzeptieren" noch
„Höhenkorrektur selbst rechnen" war eine bewusste Entscheidung. Da dies die Provider-
Vertragsfläche betrifft, braucht es einen festgehaltenen Beschluss.

## Entscheidung

1. **Höhe wird durchgereicht, nicht selbst gerechnet.** Ist die Höhe eines Wegpunkts bekannt
   (`elevation_m is not None`), trägt jede Open-Meteo-Anfrage den Parameter `elevation` (gerundet
   auf ganze Meter). Fehlt die Höhe, bleibt der Parameter **vollständig weg** — kein
   Platzhalterwert, kein `elevation=` ohne Inhalt.
2. **Keine eigene Höhenphysik.** Gregor Zwanzig rechnet selbst keine Temperatur-Höhenkorrektur
   (z. B. über einen festen Gradienten °C/100 m). Die Korrektur überlässt das System vollständig
   der Provider-Quelle — sie kennt ihr eigenes Modellgitter und dessen Fehlerverhalten besser als
   ein pauschaler Gradient es könnte.
3. **Kein Transparenzhinweis im Briefing.** Die Anwendung der Höhenkorrektur ist ein
   Provider-internes Detail, kein Nutzer-sichtbares Merkmal — es gibt keinen Hinweistext à la
   „höhenkorrigiert" im Briefing.
4. **Ein gemeinsamer Erbauer für alle Aufrufstellen.** `_punkt_params()`
   (`src/providers/openmeteo.py`) ist die einzige Stelle, die `latitude`/`longitude`/`elevation`
   für eine Open-Meteo-Anfrage zusammensetzt; ein AST-Wächter
   (`tests/test_openmeteo_callsite_elevation_guard.py`) verhindert, dass eine künftige
   Aufrufstelle daran vorbei baut.
5. **Provider-Asymmetrie wird sichtbar, nicht kaschiert** (Fortführung von ADR-0018). Nicht jeder
   Provider nimmt eine Geländehöhe an:

   | Provider | Höhenparameter | Bemerkung |
   |---|---|---|
   | Open-Meteo (alle Endpunkte: Hauptvorhersage, Ensemble, Wolken-Sidecar, Nowcast/`minutely_15`, Luftqualität ausgenommen) | ja (`elevation`) | einzige Quelle, die die Höhe entgegennimmt |
   | Open-Meteo Luftqualität/CAMS (`_fetch_uv_data`) | nein | kennt keinen Höhenparameter — bewusste Ausnahme, kein Versehen |
   | DWD-GRIB2 | nein | liefert nur Gewitter-/Schneesignale, keine Temperatur |
   | DWD-EU | nein | wie DWD-GRIB2 |
   | GeoSphere-Zeitreihen (`fetch_nwp_forecast`, INCA-Nowcast) | nein | AT-Direktquelle ohne Höhenparameter |
   | MeteoFrance-WCS | nein | liefert nur Gewittersignale |

   Diese vier Provider bleiben ohne Höhenkorrektur. Im Regelbetrieb sind sie ausschließlich
   Gewitter-/Schnee-Zulieferer, keine Temperaturquelle für den Hauptpfad — die Asymmetrie greift
   praktisch nur beim in ADR-0018 bereits vorgesehenen Totalausfall aller Open-Meteo-Kandidaten
   (Cross-Provider-Fallback).

## Verworfene Alternativen

- **Eigene Höhenkorrektur über einen festen Temperatur-Gradienten** — verworfen: ein pauschaler
  Gradient (z. B. -0,65 °C/100 m) ignoriert Inversionslagen, Exposition und Modell-spezifisches
  Fehlerverhalten; die Provider-Quelle rechnet mit ihrem eigenen, besser informierten
  Geländemodell.
- **Transparenzhinweis im Briefing ("höhenkorrigiert")** — verworfen (PO-Entscheid 2026-08-20):
  die Korrektur ist die erwartete Normalität der Anfrage, kein meldepflichtiges Sonderereignis.
- **Anker beim Umschalten löschen, um den einmaligen Wertesprung zu vermeiden** — verworfen: ohne
  Anker gäbe es für die Dauer der laufenden Tour (bis zu 12 h) gar keinen Abweichungsalarm mehr —
  ein einmaliger, vom Melde-Gedächtnis auf einmal je Metrik/Etappe begrenzter Fehlalarm ist das
  kleinere Übel als eine blinde Wache.

## Konsequenzen

- **Positiv:** Vorhersagewerte für Gipfel- und Hüttenlagen entsprechen näher der echten Höhe statt
  der Modellhöhe — direkt wirksam auf Temperatur, Nullgradgrenze, Niederschlagsform und
  Wettercode.
- **Negativ / Preis:** Beim ersten Lauf nach der Umstellung können sich Werte einmalig sprunghaft
  ändern, was Abweichungsalarme auslösen kann (bewusst hingenommen, s. Spec Known Limitations).
  Höhen sind nur so verlässlich wie ihre Quelle (GPX-Datei bzw. externer Höhendienst) — bislang
  folgenlose Eingabefehler werden jetzt wirksam.
- **Folgepflichten:** Neue Open-Meteo-Aufrufstellen MÜSSEN über `_punkt_params()` laufen oder
  namentlich mit Begründung im AST-Wächter (`BEWUSSTE_AUSNAHMEN`,
  `tests/test_openmeteo_callsite_elevation_guard.py`) eingetragen werden.
