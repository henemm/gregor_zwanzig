# Mini-Spec: #1647 Météo-France 401 — die Naht messen statt raten

Erste Scheibe von Epic **#2257**. Beantwortet dessen „offene Klärung 1" und entscheidet damit
die Reihenfolge der übrigen sechs Mitglieder.

## Bereits geklärt — wird NICHT erneut gemessen

Diese drei Punkte standen als offen im Ticket und sind es nicht mehr. Sie hier festzuhalten
ist der halbe Zweck der Scheibe: sie haben die Analyse bisher in die falsche Richtung gezogen.

- **Der Coverage-Name ist nicht das Problem.** `LITOTA3` steht seit #1457 S2a (03.08.2026)
  nicht mehr im Code. `src/providers/meteofrance.py:194-196` verwendet
  `AVERAGE_LIGHTNING_STRIKE_DENSITY_OVER_3HOURS__GROUND_OR_WATER_SURFACE`, live verifiziert am
  02.08. mit echten Werten (Lauf 00Z: +12h=0.0, +14h=0.1, +16h=0.2). Die Messung vom 07.09.,
  die „`LITOTA3` kommt in keinem Katalog vor" ergab, prüfte einen Namen, den der Code seit
  einer Woche nicht mehr benutzte.
- **Der Staging-Schlüssel ist weder leer noch veraltet.** `GZ_METEOFRANCE_APIKEY` ist in
  `/home/hem/gregor_zwanzig_staging/.env` gesetzt und nicht leer; der SHA-256-Fingerabdruck der
  Zeile ist identisch mit dem in `/home/hem/gregor_zwanzig/.env` (Produktion). Staging und
  Produktion benutzen denselben Schlüssel. Schritt 2 aus #1647 ist damit erledigt.
- **Der Schlüssel authentifiziert.** GetCapabilities lieferte am 07.09. auf beiden WCS-APIs
  HTTP 200, Vigilance als Positivkontrolle ebenfalls.

Offen bleibt genau eine Frage: **Autorisiert derselbe Schlüssel auch einen Datenabruf
(GetCoverage) — und wenn ja, für welche Coverages?**

## Was ändert sich

- **Nichts am Produktivcode, nichts an der Konfiguration.** Reine Read-only-Messung gegen die
  Live-API von Météo-France.
- Ein Messskript im Session-Scratchpad stellt vier Abrufe mit dem konfigurierten
  `GZ_METEOFRANCE_APIKEY` gegen `BASE_URL` (`meteofrance.py:74-75`):

  | # | Abruf | Zweck | Erwartung |
  |---|---|---|---|
  | 1 | `GetCapabilities` | Positivkontrolle Netz + Authentifizierung | 200 |
  | 2 | Katalogsuche nach dem Blitzdichte-Namen aus `meteofrance.py:194-196` | schließt die Namensfrage sauber ab | Treffer |
  | 3 | `GetCoverage` auf `TEMPERATURE__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND` | Kontrolle: ein Datenabruf, der laut #1647 **nicht** betroffen ist | 200 |
  | 4 | `GetCoverage` auf die Blitzdichte-Coverage | der eigentliche Prüfling | ? |

- Abruf 3 und 4 verwenden **dieselben Parameter wie `_request_once()`**
  (`meteofrance.py:436-485`): `service=WCS`, `version=2.0.1`, `format=application/wmo-grib`,
  `subset=long/lat` um GR20 42.22/9.07, `subset=time(...)` aus einem Lauf nach der Regel von
  `_thunder_run_candidates` (`THUNDER_RUN_SAFETY_HOURS = 6`). Ein selbst erfundener
  Parametersatz würde eine andere Frage beantworten als die, die im Betrieb scheitert.
- Ergebnis als Kommentar an **#1647**: je Abruf Statuscode, Antwortgröße, Laufzeit; daraus die
  Ja/Nein-Antwort auf die Prämisse von Epic #2257.

## Die Messung entscheidet zwischen drei Welten

| Befund | Bedeutung | Folge für Epic #2257 |
|---|---|---|
| 3 = 200, 4 = 200 | Der Zugang trägt vollständig. Der 401 vom 09.08. war vorübergehend. | Prämisse trägt. #1647 wird zum Beobachtbarkeits-Ticket (dauerhafter Rückfall muss sichtbar werden). |
| 3 = 200, 4 = 401 | **Coverage-spezifisch**, kein Schlüsselproblem: der Schlüssel darf Grunddaten, aber keine Blitzdichte. | Prämisse wackelt — es braucht eine Berechtigung/Subskription bei Météo-France, keinen Codefix. |
| 3 = 401, 4 = 401 | Der Schlüssel authentifiziert (GetCapabilities 200), autorisiert aber keinen Datenabruf. Deckt sich mit der Falle des Vorläufers: pro WCS-API ein eigenes Token, ein neues invalidiert das alte. | Prämisse tot. Weg über `meteofrance-api` wie beim Vorläufer — **neues ADR**, kein Bugfix. |

## Was darf sich nicht ändern

- Kein Produktivcode, keine `.env`, kein Dienst-Neustart, kein Deploy.
- **Der Schlüssel wird nirgends ausgegeben** — nicht ins Log, nicht in eine Datei, nicht in den
  Issue-Kommentar. Scratchpad-Artefakte mit `umask 077` bzw. `install -m 600` (Security #199).
- **Kein pytest-Lauf.** `egress_guard.py:48` blockt den Météo-France-Host in Testläufen hart;
  ein Test würde die Sperre messen, nicht die API. Das Messskript läuft standalone aus dem
  Scratchpad.
- Der 401 gilt erst als reproduziert, wenn er in diesem Lauf gemessen wurde. Die Beobachtung
  vom 09.08. ist ein Monat alt und wird nicht als aktueller Stand ausgegeben.

## Manuelle Test-Schritte

1. Messskript ins Session-Scratchpad schreiben (`umask 077`), Schlüssel aus der Umgebung lesen.
2. Die vier Abrufe nacheinander ausführen, Statuscode/Größe/Laufzeit protokollieren.
3. Gegenprobe mit leerem `apikey`-Header wiederholen (siehe Inline-Test).
4. Protokoll gegen die Drei-Welten-Tabelle auswerten und als Kommentar an #1647 hängen.
5. Prüfen, dass im Protokoll und im Kommentar kein Schlüsselwert steht.

## Inline-Test

- [ ] **Positivkontrolle:** Abruf 1 (`GetCapabilities`) liefert 200 — sonst misst der Lauf die
      Netzstrecke oder eine Sperre, nicht die Berechtigung, und alle anderen Ergebnisse sind wertlos.
- [ ] **Negativkontrolle:** derselbe Abruf 4 mit leerem `apikey`-Header liefert 401 — sonst
      beweist ein 200 nichts darüber, dass der Schlüssel überhaupt gewirkt hat.
- [ ] **Geheimnis-Gegenprobe:** `grep` über Skript-Ausgabe, Scratchpad-Artefakte und den
      Kommentartext findet den Schlüsselwert nicht.
