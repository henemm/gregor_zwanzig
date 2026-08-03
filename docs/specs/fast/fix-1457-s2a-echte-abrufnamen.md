# Mini-Spec: S2a fragt beim echten Dienst nach Namen, die es dort nicht gibt

**Gefunden:** 2026-08-03 beim Auslieferungs-Nachweis. **PO-Entscheidung:** erst
korrigieren, dann ausliefern. Vollständiger Befund: Issue #1457, Kommentar vom 2026-08-03.

## Der Fehler (live belegt, nicht vermutet)

| | Code fragt | Wirklichkeit laut `GetCapabilities` |
|---|---|---|
| Name der Größe | `LITOTA3` | **0 Treffer.** Korrekt: `AVERAGE_LIGHTNING_STRIKE_DENSITY_OVER_3HOURS__GROUND_OR_WATER_SURFACE` |
| Modell-Lauf | jüngster 3h-Lauf **minus 3 h** (`meteofrance.py:207-213`) | um 09:27Z war der jüngste fertige Lauf `03.00.00Z` = **6,5 h** alt; der errechnete `06.00.00Z` existierte nicht |

Folge: **jeder** Abruf endet in `404`. Fail-soft schluckt es, also lautlos.

Beweis der Lösung — ein Abruf mit korrigierten Angaben:
`HTTP 200 | 81.005 Bytes | 0,42 s | Dateikopf "GRIB"`

## Was sich ändert

1. **Coverage-Name korrigieren** auf die ausgeschriebene Form. Der Name gehört als
   benannte Konstante an eine Stelle — heute steckt die Kurzform im Abrufpfad.
2. **Lauf-Ermittlung robust machen.** Zwei Teile, beide nötig:
   - Sicherheitsabstand von 3 h auf **6 h** erhöhen (gemessen: 6,5 h waren nötig; der
     Lauf ist rund 3–4 h nach seiner Nominalzeit fertig).
   - **Rückfall auf ältere Läufe:** Antwortet der gewählte Lauf mit `404`, wird der
     nächstältere versucht, **höchstens zwei Stufen** (= bis 12 h zurück). Danach
     aufgeben und wie bisher `None` liefern. Der Rückfall wird **einmal je Lauf**
     protokolliert, nicht je Stunde — sonst 24 gleiche Zeilen.
   - Der ermittelte Lauf steckt bereits im Schlüssel des Zwischenspeichers; das muss
     so bleiben, sonst werden alte Daten als frische ausgeliefert.

## Was sich nicht ändern darf

- **Fail-soft bleibt:** Ein fehlgeschlagener Gewitterabruf darf die Vorhersage nie
  mitreißen. Auf Staging belegt — muss belegt bleiben.
- **Die Gebiets-Zuständigkeit bleibt:** Orte außerhalb Frankreichs erzeugen weiterhin
  **null** Abrufe.
- **`None` heißt „keine Aussage"**, nie `0`.
- Kein Umbau des Sammelabrufs, des Zwischenspeichers oder der Zeitgrenzen.
- Die aufgezeichnete Testdatei bleibt gültig (sie enthält echte Daten; nur ihr
  Dateiname trägt die alte Kurzform — **Umbenennen ist optional**, kein Muss).

## Acceptance Criteria

- **AC-1:** Given ein Ort auf Korsika und ein normal erreichbarer Météo-France-Dienst /
  When eine Vorhersage über den **regulären** Weg abgerufen wird / Then trägt
  **mindestens ein** Zeitpunkt einen gefüllten Blitzdichte-Wert. Das ist die Wirkung,
  um die es geht — heute ist sie null.
- **AC-2:** Given der Name der Blitzdichte-Größe, wie er **im Produktivcode** steht /
  When das Angebot des Dienstes (`GetCapabilities`) abgefragt wird / Then kommt genau
  dieser Name dort vor. Der Test liest den Namen **aus dem Produktivcode**; ein zweiter,
  im Test wiederholter Namensstring wäre wertlos, weil er sich selbst prüft.
- **AC-3:** Given der Modell-Lauf, den der Code für „jetzt" ermittelt / When das Angebot
  des Dienstes abgefragt wird / Then wird genau dieser Lauf dort angeboten. Damit fällt
  ein zu knapper Sicherheitsabstand auf, statt lautlos in 404 zu enden.
- **AC-4:** Given der zuerst gewählte Lauf antwortet mit `404` / When die Blitzdichte
  geholt wird / Then wird der nächstältere Lauf versucht, **höchstens zwei** Stufen weit.
- **AC-5:** Given alle versuchten Läufe antworten mit `404` / When die Vorhersage gebaut
  wird / Then bleibt die Blitzdichte **leer** (`None`, nie `0`) **und** die Vorhersage
  ist vollständig — Temperatur und Wind sind unversehrt vorhanden.
- **AC-6:** Given ein Ort außerhalb Frankreichs / When eine Vorhersage abgerufen wird /
  Then wird **kein einziger** Gewitter-Abruf ausgelöst — die Gebiets-Zuständigkeit aus
  S2a bleibt unangetastet wirksam.
- **AC-7:** Given ein Rückfall auf einen älteren Lauf findet statt / When die Stunden
  eines Ortes geholt werden / Then erscheint die Rückfall-Meldung im Protokoll **genau
  einmal je Lauf**, nicht einmal je Stunde — sonst 24 gleichlautende Zeilen.
- **AC-8:** Given zwei Abrufe für dieselbe Kachel bei zwischenzeitlich gewechseltem
  Modell-Lauf / When der Zwischenspeicher befragt wird / Then werden die Daten des alten
  Laufs **nicht** als frische ausgeliefert — der ermittelte Lauf bleibt Teil des
  Speicherschlüssels.

## Der eigentliche Nachweis (das Wichtigste an dieser Arbeit)

Der Fehler konnte entstehen, weil **kein einziger Test die Naht zum fremden Dienst
berührt**. Alle 24 lesen eine gespeicherte Datei. Deshalb ist Pflicht:

**Ein Test gegen den echten Dienst** (Marker `live`, läuft nicht im Commit-Gate):
- fragt `GetCapabilities` ab und prüft, dass der **im Code verwendete** Coverage-Name
  dort **tatsächlich vorkommt**. Nicht ein hart hineingeschriebener Vergleichsstring —
  der Name muss aus dem Produktivcode gelesen werden, sonst prüft der Test sich selbst.
- prüft, dass der **vom Code ermittelte Lauf** in der Angebotsliste steht.

Damit fällt jede künftige Umbenennung durch den Dienst auf — auch bei S2b/S2c.

Zusätzlich im Kern (deterministisch, ohne Netz):
- Ein Test, der belegt, dass bei `404` auf den nächstälteren Lauf zurückgefallen wird.
- Ein Test, der belegt, dass nach zwei erfolglosen Stufen `None` herauskommt und die
  Vorhersage vollständig bleibt.

## Gegenprobe (Mutations-Pflicht)

Jede der folgenden Verfälschungen **muss** einen Test rot machen. Wird eine nicht
gefangen, ist der Fix nicht fertig:

1. Coverage-Name zurück auf `LITOTA3` → der Live-Test muss rot werden.
2. Sicherheitsabstand zurück auf 3 h → der Live-Test (Lauf im Angebot?) muss rot werden.
3. Rückfall-Schleife entfernen → der Kern-Test muss rot werden.
4. `None` → `0.0` im Anreicherungsweg → muss rot werden (bestehende Zusicherung).

## Manuelle Bestätigung nach dem Fix

Ein echter Abruf für einen Korsika-Ort liefert **mindestens einen** Datenpunkt mit
gefüllter Blitzdichte, und ein Ort in Österreich erzeugt weiterhin **null** Abrufe.
