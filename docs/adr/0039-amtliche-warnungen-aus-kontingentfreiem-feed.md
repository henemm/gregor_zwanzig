# ADR-0039: Amtliche Warnungen kommen aus dem kontingentfreien MeteoAlarm-Feed, nicht mehr aus der EDR-Index-API

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-01)
- **Datum:** 2026-08-01
- **Bezug:** Issue #1445 (S1 Italien, S3 Österreich), Issue #1397 (Ursprungsdefekt), Specs `docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md` und `feat_1445_s3_oesterreich_feed.md`, Analyse `docs/context/fix-1397-wiederanlauf-ausbruch.md`

## Kontext

Amtliche Unwetterwarnungen für Österreich und Italien wurden über die authentifizierte OGC-EDR-API `api.meteoalarm.org` bezogen. Diese Quelle ist mengenbegrenzt, und die Grenze erwies sich als **nicht stationär**.

Gemessen in Produktion, echte Netzabrufe zwischen zwei Anbietersperren:

| Öffnungszeitraum | offen | Abrufe bis zum nächsten 429 |
|---|---|---|
| 28.07. 12:00 → 29.07. 09:30 | 21,5 h | 138 |
| 30.07. 09:30 → 30.07. 14:00 | 4,5 h | 95 |
| 31.07. 14:00 → 31.07. 15:45 | 1,7 h | **64** |

Die durchgelassene Menge sank monoton; keine geprüfte Fensterbreite (24 h / 48 h / 72 h / 7 d) ergab eine konstante Grenze. Das eigene Budget von 100 Abrufen pro Tag lag zuletzt **über** dem, was der Anbieter real durchließ.

Verschärfend wirkte ein Rückkopplungseffekt: Fortschrittsmarke und Bestand lagen nur im Prozessspeicher. Nach jeder Sperre — und nach jedem Neustart — zog der Kaltstart das Abfragefenster auf die volle Rückschau von 23 Stunden, was 17–21 Seitenabrufe je Land bedeutete, also 35–45 Abrufe in wenigen Minuten. **Jede Sperre erzeugte damit beim Wiederanlauf den Ausbruch, der die nächste Sperre auslöste.** Der Dienst stand im Dauerzustand „rund 22 Stunden gesperrt, rund 2 Stunden offen"; amtliche Warnungen waren den größten Teil des Tages veraltet.

Das ist keine Effizienz-, sondern eine Sicherheitsfrage: Das Produkt ist ein Entscheidungswerkzeug für Weitwanderungen, und die gefährlichste Fehlerart ist die Mail, die erfolgreich aussieht, während die Warnung fehlt.

## Entscheidung

**Amtliche Warnungen werden aus dem öffentlichen Feed `feeds.meteoalarm.org` bezogen** (`/api/v1/warnings/feeds-<land>`), einem Angebot desselben Anbieters mit denselben Daten. `MeteoAlarmSource` (EDR-Index) ist nicht mehr registriert und wird im Produktivpfad nicht mehr aufgerufen.

Eigenschaften des gewählten Wegs, live geprüft:

- **Ein Abruf je Land und Auffrischung** statt bis zu 21 Seiten; keine Authentifizierung, keine Mengenbegrenzung.
- **Vollständiger CAP-Inhalt direkt in der Antwort** (Ereignis, Stufe, Gültigkeit, Gebiet, Gefahrenart), für Österreich auf Deutsch.
- **Rückschau rund 5,8 Tage** statt der harten 23-Stunden-Grenze der EDR-API — die dort als „strukturell unerreichbar" dokumentierte Lücke entfällt.
- **Momentaufnahme der gültigen Fassungen**, kein Archiv: Zurückgezogene Warnungen verschwinden von selbst.

Die Zuordnung Punkt → Warnzone kommt ohne neue Geodaten und ohne zusätzliche Abrufe aus:

- **Italien:** über die bereits eingecheckten DPC-Zonen; deren 20 Regionspräfixe entsprechen 1:1 den Zonenkennungen IT001…IT020.
- **Österreich:** über die Gemeindenummer aus der ZAMG-Antwort, die für jeden österreichischen Punkt ohnehin abgerufen und zwischengespeichert wird. Die ersten drei Stellen sind die Bezirkskennung (13 von 13 realen Orten verifiziert).

Der EDR-Apparat bleibt vorerst als Code erhalten, weil der ausstehende Äquivalenznachweis ihn als Vergleichsmaßstab braucht. Sein Rückbau ist eine eigene Folgearbeit.

## Verworfene Alternativen

- **Verbrauch weiter drosseln und verstetigen** (Token-Bucket, Rampe nach Sperre, Bestand über Neustarts persistieren) — technisch machbar, aber das Ziel ist unbekannt und beweglich; jede Kalibrierung wäre eine Wette. Zudem skaliert dieser Weg gegen die geplante Ländererweiterung: Mehr Länder teilen dasselbe Kontingent, während der Feed pro Land genau einen Abruf kostet.
- **Höheres Kontingent beim Anbieter erfragen** — sinnvoll parallel, aber mit unkalkulierbarer Antwortzeit; nach dem Wechsel ohnehin gegenstandslos.
- **Dauerhafter Parallelbetrieb beider Quellen** — schädlich: Solange die gesperrte EDR-Quelle für dasselbe Land als zuständig registriert bleibt, kippt ihr Fehlschlag den Hinweis „nicht abrufbar" für alle Nutzer, obwohl der Feed einwandfrei liefert. Der Quellenvergleich gehört in einen Test, nicht in die Registrierung.
- **MQTT-Push als alleiniger Bezugsweg** (Issue #1445 Ursprungsvorschlag) — der Broker existiert und akzeptiert unseren Zugang, liefert aber ohne Retained Messages **keinen Bestand**: Ein frisch verbundener Abonnent erfährt nur, was ab dem Verbindungszeitpunkt passiert. Push braucht deshalb zwingend eine Bestandsquelle; genau die ist dieser Feed. MQTT bleibt als spätere Ergänzung sinnvoll (Aktualität von Minuten auf Sekunden), nicht als Ersatz.

## Konsequenzen

- **Positiv:** Der Kontingentdruck entfällt vollständig — gemessen null Zugriffe auf den mengenbegrenzten Host. Amtliche Warnungen sind wieder durchgehend aktuell statt 22 Stunden am Tag veraltet. Die Rückschau ist länger, die Sprache besser, Rückzüge wirken automatisch. Weitere Länder kosten je einen Abruf statt eines Anteils am gemeinsamen Kontingent.
- **Negativ / Preis:** Der Feed liefert je Abruf die vollständige Landesdatei (Österreich 2,4 MB, Italien 1,4 MB) ohne Kompression und ohne Änderungskennung — die übertragene Datenmenge steigt, während die Abrufzahl sinkt. Für weitere Länder ist deshalb ein eigenes Auffrischraster vorzusehen. Österreich hängt bei der Zonenzuordnung am ZAMG-Endpunkt; fällt er aus, muss das „nicht abrufbar" erzeugen, nie „keine Warnung".
- **Folgepflichten:**
  1. **Drei Zustände bleiben strikt getrennt:** „hier gilt nichts" (Punkt außerhalb des Landes), „ich weiß es nicht" (Dienst gestört oder Antwort unbrauchbar) und „hier ist gerade nichts". Sieben der acht Findings der beiden Gegenprüfungen entstanden aus einer Vermischung dieser Zustände.
  2. **Die Absicherung dagegen darf keinen Daueralarm erzeugen.** Ein Wächter, der an guten Tagen anschlägt, wird abgeschaltet und schützt dann gar nicht mehr — Prüfungen auf beschädigte Daten greifen erst **nach** der Zonenfilterung.
  3. **Der Äquivalenznachweis ist nachzuziehen** (zeitgleiche Aufzeichnung beider Wege je Land). Bis dahin tragen die Gate-Tests eine Markierung, die sich meldet, sobald sie bestehen.
  4. Ein Wechsel zurück oder auf einen weiteren Bezugsweg erfordert ein neues ADR.
