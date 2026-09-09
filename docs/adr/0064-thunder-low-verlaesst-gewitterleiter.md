# ADR-0064: `ThunderLevel.LOW` verlässt die vier-stufige Gewitterleiter

- **Status:** Akzeptiert
- **Datum:** 2026-09-08
- **Bezug:** GitHub-Issue #2176, Spec `docs/specs/modules/feat_2176_luftmasse_statt_gewitteransage.md`,
  Kontext `docs/context/feat-2176-luftmasse-statt-gewitteransage.md`, Epic #1419 Abschnitt 9,
  löst einen Punkt aus ADR-0048 ab (s. dort)

## Kontext

`ThunderLevel.LOW` ("leicht") wurde in allen vier Kanälen als Gewitter-**Ereignis** formuliert
("Leichtes Gewitter möglich ab 14:00", "⚡ Gewitter möglich", "Gewitter leicht"), maß aber
nachweislich nur eine labile Luftmasse: an Trip KHW 403 (24.08.–05.09.2026, 1 582 Zeilen
ICON-D2) lag JEDE "leicht"-Messung über der CAPE-Sprosse (100 %), 73 % ohne jeden
Niederschlag.

ADR-0048 hält weiterhin unverändert ("Status: Akzeptiert") fest: "CAPE misst Energie, kein
Ereignis, und eskaliert nie über LOW." Diese Aussage war bereits durch #1679 (CAPE-Leiter,
`feat_1679_cin_paarung_cape_leiter.md`) im Code widerlegt, ohne dass ADR-0048 dafür abgelöst
wurde. Die vorliegende Entscheidung macht die Formulierung zusätzlich grundsätzlich hinfällig:
Wenn CAPE nie über LOW eskaliert, LOW selbst aber die vier-stufige, nutzersichtbare
Gewitterleiter (`keine/möglich/wahrscheinlich/akut`, Epic #1419 Abschnitt 9, PO 2026-07-29)
verlässt, ist der ADR-0048-Satz gegenstandslos für den Teil der Leiter, den er ursprünglich
begründen sollte.

## Entscheidung

**`ThunderLevel.LOW` verlässt die vier-stufige, nutzersichtbare Gewitterleiter vollständig**
(PO-Entscheidung Henning, 2026-09-08, final). Die vier Stufen `keine/möglich/wahrscheinlich/
akut` beginnen künftig bei `ThunderLevel.MED`. "leicht" wird eine eigene, alarmlose
Luftmassen-Größe außerhalb dieser Leiter.

Konkret:

1. In keinem der vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) erscheint für `LOW` mehr eine
   Ereignisbehauptung ("Gewitter" als Wort, ⚡ als Ereignis-Symbol unmittelbar vor dem
   Stufenwort). Als reiner, levelunabhängiger Spalten-/Metrik-Kennzeichner (Tabellenkopf,
   Katalogeintrag `id="thunder"`, `label_de="Gewitter"`) bleibt "Gewitter" zulässig — er
   benennt dort die Metrik, nicht ein Ereignis dieser Stunde.
2. Der zugrundeliegende CAPE-Wert bleibt sichtbar: er steht direkt an der neuen LOW-Aussage
   (E-Mail-/Telegram-Fließtext), nicht nur potentiell erreichbar über die separate
   CAPE-Spalte der Stundentabelle.
3. Das Stufenwort selbst (`THUNDER_LABEL_DE`, "leicht") ändert sich nicht und bleibt, wo ein
   Kanal es ohnehin knapp führt (SMS-Legende, Telegram-Fußzeile, Outlook-Token), erkennbar —
   nur die umgebende Satzform mit "Gewitter" entfällt.
4. `MED`/`HIGH` bleiben unverändert Teil der Leiter mit der bestehenden Formulierung
   ("Gewitter möglich"/"Gewitter {stufe}", `TH:M`/`TH:H`).
5. Die Alarm-Logik (`ORDINAL_LEVEL_BOUNDS`, `_ordinal_change_triggers`) bleibt unverändert —
   reine Darstellungsänderung, kein Eingriff in die Auslöseschwellen.

Der Satz "CAPE misst Energie, kein Ereignis, und eskaliert nie über LOW" in ADR-0048 wird an
seiner Fundstelle als durch diese Entscheidung abgelöst markiert. ADR-0048 bleibt für die
übrigen Regeln (modellabhängige Schwellentabelle je Modell × Gebiet, keine feste
Modellgrenzen-Schwelle) unverändert in Kraft und trägt weiterhin **Status: Akzeptiert** — nur
der eine, hier genannte Satz ist betroffen.

## Verworfene Alternativen

- **LOW bleibt in der Leiter, nur der Wortlaut wird entschärft** ("Gewitter möglich (schwach)")
  — verworfen, weil "Gewitter" im Satz stehen bliebe und damit weiterhin eine Ereignisbehauptung
  ausgesprochen würde, die die Messung (100 % über CAPE-Sprosse, 73 % ohne Niederschlag) nicht
  trägt.
- **LOW und die CAPE-Leiter für MED/HIGH (#2178) in einer Scheibe bündeln** — verworfen
  (PO-Entscheidung 2026-09-08 zum Zuschnitt): #2176 wird einzeln umgesetzt, #2178 bleibt eigener
  Zuschnitt. Konsequenz: die Tages-Höchststufe bleibt an den meisten KHW-403-Tagen (9 von 13)
  eine Gewitteransage, weil dort tatsächlich MED/HIGH vorlag — das ist beabsichtigt, nicht ein
  Mangel dieser Entscheidung.
- **ADR-0048 komplett als "Abgelöst" markieren** — verworfen: die Regeln zur modellabhängigen
  Schwellentabelle selbst sind von dieser Entscheidung nicht berührt und bleiben in Kraft; eine
  vollständige Ablösung würde diese weiterhin gültigen Regeln fälschlich entwerten.

## Konsequenzen

- **Positiv:** Die Darstellung entspricht wieder der tatsächlichen Messung — eine reine
  Luftmassen-/Signal-Aussage statt einer nicht getragenen Ereignisbehauptung. Der CAPE-Wert
  wird an der Stelle sichtbar, an der er gebraucht wird (AC-2), statt nur potentiell in einer
  Nebenspalte.
- **Negativ / Preis:** Die vier nutzersichtbaren Gewitterstufen aus Epic #1419 Abschnitt 9
  beginnen jetzt bei `MED` statt bei `LOW` — eine sichtbare Abweichung von der ursprünglichen
  Grundsatzentscheidung, die dokumentiert bleiben muss, damit sie nicht als Regression
  missverstanden wird. Die Tages-Schlagzeile bleibt an den meisten Tagen unverändert eine
  Gewitteransage (Wirkungsgrenze, s. Spec Known Limitations) — nur 3 von 13 gemessenen
  KHW-403-Tagen (Höchststufe "leicht") verlieren sie durch diese Entscheidung.
- **Folgepflichten:**
  - Jede künftige Änderung an der Gewitterleiter-Definition (Epic #1419) muss diese
    Entscheidung als Startzustand nehmen: die Leiter beginnt bei `MED`, nicht bei `LOW`.
  - #2178 (CAPE-Leiter für MED/HIGH) ist der explizit benannte Folgeschritt, der die
    verbliebene Wirkungsgrenze (Tages-Schlagzeile an 10 von 13 Tagen) adressiert.
  - Die Ampelfarbe für LOW (`thunder_ampel_band(LOW)` = "yellow", `fix_1491_gewitter_
    ampelkreis.md` AC-7) ist von dieser Entscheidung NICHT berührt und bleibt offen für eine
    gesonderte PO-Antwort.
