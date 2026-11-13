# ADR-0117: Interaktive Abrufe bekommen ein eigenes Kontingent am fairen Anteil und lassen eine Reserve für Briefings und Alarme frei

- **Status:** Akzeptiert
- **Datum:** 2026-11-13
- **Bezug:** GitHub-Issue #2961 (Sicherheits-Härtung nach Review 2026-11, Welle 2), Spec
  `docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md`; **ergänzt
  [ADR-0075](0075-forecast-budget-fairness-je-nutzer.md)** (Tagestopf und fairer Anteil) und
  **[ADR-0076](0076-go-dockt-ueber-internen-endpunkt-an-das-kontingent-gate-an.md)** (Go dockt am
  Gate an); verwandt [ADR-0114](0114-ausgehende-abrufe-nutzerbestimmter-ziele-nur-ueber-abgeschotteten-client.md)
  (Mengenbremsen je Nutzer in Go), [ADR-0018](0018-provider-fallback-ohne-kaschieren.md) (nichts
  still weglassen), [ADR-0058](0058-wegpunkt-hoehe-an-provider-api.md) (Höhe an den Anbieter)

## Kontext

Das Open-Meteo-Tageskontingent ist ein globaler Topf (`DAILY_BUDGET = 9000`, ADR-0075). Die
Priorität `user_briefing` wird nie gedrosselt — gedacht für den Zeitplan-Versand. Dieselbe
Priorität hing aber auch an Wegen, die ein angemeldeter Nutzer beliebig oft auslösen kann:
Sofortvergleich, Etappenwetter, Vorschauen. Ein einzelnes Konto konnte so mit vielen Aufrufen und
wechselnden Orten das Kontingent aller aufbrauchen; danach wären Alarm-Prüfungen für alle
gesperrt. Die Mengenbremsen aus ADR-0114 begrenzen die Geschwindigkeit, nicht den Tagesverbrauch.

## Entscheidung

1. **Eigene Priorität `user_interactive`.** Alles, was ein Nutzer von Hand und beliebig oft
   auslöst, bucht interaktiv: Sofortvergleich (`GET /api/compare`), Etappenwetter, SMS-Vorschau,
   Alarm-Vorschau (Trip und Ortsvergleich) und die Go-Vorhersage `GET /api/forecast`. Die
   Markierung geschieht einmal je Anfrage an der Route (`forecast_budget.interaktiver_abruf()`,
   ein Kontext, der in Arbeiter-Threads per `contextvars.copy_context()` weiterreist); der
   Segment-Weg bucht innerhalb dieses Kontexts jede Priorität als `user_interactive`.
   `user_briefing` bleibt ausschließlich Zeitplan-Versand **und Handversand** vorbehalten
   (Handversand ist durch die Go-Bremse auf 20 je Stunde begrenzt und soll nie am Kontingent
   scheitern).
2. **Interaktives Tageskontingent je Nutzer** = fairer Anteil an der interaktiven Obergrenze
   (`6300 / N`, N = heute aktive Nutzer wie in ADR-0075), **mindestens der Sockel 1500 Einheiten**.
   Der Sockel deckt normale Nutzung (30 Vergleiche à 10 Orte plus 50 Etappenwetter-Abrufe einer
   Tour mit bis zu 24 Abschnitten, alles ohne Cache-Treffer) ohne Drosselung ab; Herleitung in der
   Spec. Der interaktive Verbrauch wird global (`interactive_calls`) und je Nutzer
   (`interactive`) getrennt geführt und zählt **nicht** in die Fairness von `alert_check` und
   `polling` — Alarme desselben Nutzers bleiben unberührt.
3. **Globale Reserve.** `reserve("user_interactive")` bucht nur, solange der gesamte
   Tageszähler plus die neuen Einheiten höchstens **70 %** der Tagesmenge erreicht
   (`INTERACTIVE_THRESHOLD`). Begründung aus den vorhandenen Schwellen: Polling wird ab 80 %
   (Stufe 1) gedrosselt, Alarm-Prüfungen ab 95 %. Endet interaktiv bei 70 %, kann interaktiver
   Verbrauch allein keine dieser Schwellen auslösen; zwischen 70 % und 80 % bleiben 900 Einheiten
   Puffer, bis 95 % 2250 Einheiten, die nur Briefings, Alarme und Polling verbrauchen. Die Regel
   „Zeitplan-Briefings nie gedrosselt" bleibt unverändert.
4. **Erschöpft heißt: Cache ja, Neuabruf nein, und es wird gesagt.** Cache-Treffer buchen nichts
   und werden weiter geliefert. Ein nicht gecachter Ort im Vergleich trägt den übersetzten Hinweis
   `vergleich.ort.abruf_kontingent_erschoepft` und `error_code`; liefert keine Einheit der Anfrage
   Daten, antwortet die Route mit **429** `abruf_kontingent_erschoepft` und `Retry-After` bis zum
   UTC-Tageswechsel. Eine Etappe mit abgelehntem Abschnitt wird nicht aus Teildaten bewertet,
   sondern als `null` geliefert und in `gedrosselt` samt Hinweis benannt (ADR-0018).
5. **Eingaben begrenzt.** Sofortvergleich: `forecast_hours` 1–96 (der größte Horizont, den das
   Produkt selbst nutzt, `COMPARE_FORECAST_HOURS`), Stundenfenster 0–23, Datum im ISO-Format,
   sonst 422 mit Katalogtext; Anzahl der Orte höchstens die Orte-Quote des Tarifs (Go, Admins und
   Ausnahmen frei, 422 `limit_exceeded`).
6. **Cache-Schlüssel bleibt genau.** Der Schlüssel rundet Koordinaten auf vier Nachkommastellen
   (rund 11 m) und enthält die Höhe; eine Verschiebung um wenige Meter erzwingt damit einen neuen
   Abruf. Der Schlüssel wird **nicht** auf das Modellraster gerundet: der Anbieter rechnet mit der
   übergebenen Höhe und Lage (ADR-0058), eine Rundung änderte die Vorhersage. Auch „je Rasterzelle
   nur einmal buchen" ist verworfen — echte Abrufe blieben dann ungebucht und der Kontoschutz
   würde schwächer. Stattdessen kostet jede Verschiebung eine Einheit **des eigenen** interaktiven
   Kontingents; die Menge ist damit je Nutzer und insgesamt begrenzt.
7. **Sichtbarkeit.** `/api/scheduler/status` nennt `interactive_calls_today`,
   `interactive_budget` und `interactive_throttled`, `GET /api/admin/users` je Nutzer
   `open_meteo_interactive_calls_today`. Stellt ein Nutzer mehr als die Hälfte des interaktiven
   Tagesverbrauchs (ab einem Gesamtverbrauch in Höhe des Sockels), schreibt das Gate einmal je Tag
   und Nutzer eine Warnzeile mit maskierter Kennung.

## Verworfene Alternativen

- **Interaktiv als `polling` buchen.** Polling ist an den Alarm-Fairness-Anteil gebunden; ein
  Vielnutzer hätte damit seine eigenen Alarme ausgebremst, und vor 80 % gäbe es keine Grenze.
- **Fester Sockel ohne fairen Anteil.** Bei wenigen Nutzern bliebe Kontingent ungenutzt, das
  niemand sonst braucht.
- **Interaktiv mit eigenem Topf neben dem globalen.** Hätte die Tagesmenge gegenüber dem Anbieter
  vergrößert (gleicher Einwand wie ADR-0075 Punkt 1).
- **Handversand interaktiv buchen.** Widerspricht dem Produktgrundsatz, dass ein von Hand
  ausgelöstes Briefing ankommt; die Menge begrenzt bereits die Go-Bremse.

## Konsequenzen

- Bei vielen gleichzeitig aktiven Vielnutzern (mehr als vier mit voll genutztem Sockel) erreicht
  der interaktive Gesamtverbrauch die 70-%-Grenze; dann bekommen alle nur noch Cache-Daten, während
  Briefings und Alarme weiterlaufen. Das ist gewollt; die Diagnose steht im Betriebsstatus.
- Antwortbefehle über die Kanäle (Telegram, SMS, Premium-SMS) bleiben bewusst bei ihrer bisherigen
  Priorität: sie sind der Weg unterwegs und dürfen nicht an einem Bürotag-Kontingent scheitern.
- Die nutzerfreie Radar-Anreicherung im Anbieter (ADR-0075 Punkt 4) bucht weiterhin
  unattributiert und wird vom interaktiven Kontext nicht erfasst.

## Nachtrag 2026-11-13 (Gegenprüfung, Fix-Runde): `user_manual`, feste Grenze je Nutzer, Anreicherung

Die Gegenprüfung (Verdict BROKEN) zeigte, dass ein einzelnes Konto das Kontingent weiter leeren
konnte. Dieser Nachtrag **ändert Punkt 1 und Punkt 2** und hebt die zwei letzten Konsequenzen oben
auf; alles Übrige gilt unverändert.

1. **Neue Priorität `user_manual`** (ändert Punkt 1). Handversand (Trip, Ortsvergleich,
   kind-neutral) und die Antwort-Befehle aller Kanäle (Telegram, E-Mail, SMS, Premium-SMS) buchen
   nicht mehr `user_briefing`. Begründung: Ein Free-Konto erreichte mit drei Trips und einem
   Ortsvergleich über die erlaubten 480 Handversände je Tag rund 8800 von 9000 Einheiten, mit
   wegpunktreichen Touren schon nach wenigen Versänden. `user_briefing` bleibt ausschließlich dem
   Zeitplan-Versand vorbehalten.
   - **Je Nutzer 1500 Einheiten am Tag.** Ein typischer Versand (Etappe mit vier Abschnitten,
     Nacht, drei Trend-Etappen) kostet 17 Einheiten, also rund 88 Versände oder Antworten je Tag.
   - **Global nie über 90 %** (8100 Einheiten). Alarm-Prüfungen werden erst ab 95 % gedrosselt
     und bleiben damit geschützt; Zeitplan-Briefings nie.
   - **Kein Teil-Briefing.** Ein Versand oder Befehl bucht beim ersten Abruf seine ganze
     Obergrenze auf einmal (`manuelles_kontingent.py`: die vier abschnittsreichsten Etappen plus
     Nacht plus Anreicherung der Zieletappe, beim Ortsvergleich zwei je Ort, mindestens sieben).
     Passt sie nicht mehr, wird nichts abgerufen und nichts zugestellt: Web antwortet 429
     `kontingent_erschoepft` mit Katalogtext und `Retry-After`, ein Antwort-Befehl mit der kurzen
     Antwort „Tageskontingent für Abrufe erschöpft, automatische Briefings und Alarme laufen
     weiter" (Kurzform-Kanäle englisch, unter 160 Zeichen). Nicht verbrauchtes Guthaben (Cache-
     Treffer) wird nach dem Versand erstattet; Cache-Treffer zählen also nicht.
   - Die Fairness von `alert_check`/`polling` rechnet ohne interaktiven und manuellen Verbrauch.
2. **Feste Grenze je Nutzer für `user_interactive`** (ändert Punkt 2): 1500 Einheiten, kein Teilen
   durch die aktiven Nutzer mehr. Vorher konnte der erste aktive Nutzer des Tages (N = 1) die ganzen
   6300 allein verbrauchen. Die globale Grenze 6300 bleibt zusätzlich.
   **Restrisiko „mehrere abgestimmte Konten":** ab fünf Konten mit voll genutzter Grenze ist der
   interaktive Topf (6300) dicht, ebenso können sechs Konten den manuellen Topf bis 90 % füllen.
   Briefings und Alarme bleiben in beiden Fällen unberührt (Reserven bis 70 % bzw. 90 %, Alarme ab
   95 %). Gebremst ist das durch die Registrierungsbremse (5 je Stunde und IP), die
   Bestätigungspflicht der Adresse und die Mengenbremsen je Nutzer aus ADR-0114.
   `GET /api/forecast` bekommt dieselbe Mengenbremse wie die übrigen Abrufwege (60 je Minute,
   höchstens 4 gleichzeitig).
3. **Anreicherung wird zugerechnet** (hebt die letzte Konsequenz oben auf). Innerhalb einer
   markierten interaktiven oder manuellen Anfrage bucht auch die Radar-/Gewitter-Anreicherung im
   Anbieter beim auslösenden Nutzer mit dessen Priorität. Lehnt das Kontingent ab, entfällt nur die
   Anreicherung mit dem üblichen Verhalten „ohne Anreicherung" (`NowcastResult.throttled`,
   Health-Journal `self_throttled`, ADR-0018/0047): die Vorhersage bleibt, nichts wird kaschiert.
   Außerhalb markierter Anfragen bleibt sie nutzerfrei wie bisher (ADR-0075 Punkt 4).
4. **Sichtbarkeit:** Betriebsstatus `manual_calls_today`, `manual_budget`, `manual_throttled`;
   Admin-Liste `open_meteo_manual_calls_today`.
