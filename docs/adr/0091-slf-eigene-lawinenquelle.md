# ADR-0091: SLF als eigene Lawinenquelle mit geteiltem CAAML-Modul

- **Status:** Akzeptiert
- **Datum:** 2026-10-17
- **Bezug:** GitHub-Issue #1441 Scheibe S3, Spec `docs/specs/modules/feat_1441_s3_slf.md`;
  ergänzt ADR-0089 (Lawinen-Lagebericht, zweite Skala) und löst dessen Konsequenz „Ein weiteres
  Land ist ein Tabelleneintrag" für die Schweiz teilweise ab; nutzt ADR-0016 (Registry),
  ADR-0090 (Entwarnung), ADR-0041 (Zuständigkeit)

## Kontext

ADR-0089 hielt fest: „Ein weiteres Land ist ein Tabelleneintrag (`AVALANCHE_REGION_TABLE`) plus
Regionsdatei und Egress-Host — kein Parser-/Renderer-Code." Das gilt für avalanche.report, wo jede
Region ein eigenes statisches Dokument unter derselben URL-Form hat.

Der amtliche Schweizer Lagebericht des SLF (`aws.slf.ch`, CAAML6-JSON) weicht in fünf Punkten ab:

1. **Anderer Endpunkt, ein Dokument für die ganze Schweiz** (mit `activeAt` abfragbar) statt eines
   Dokuments je Region.
2. **Höhe steht im Problem, nicht im Rating:** `dangerRatings[]` tragen keine `elevation`; die
   Grenze steckt in `avalancheProblems[].elevation`, mehrere Probleme können verschiedene Grenzen haben.
3. **Kein Link-Feld** im Bulletin; der Link zum Originalbericht ist konstant.
4. **Außerhalb der Saison HTTP 200 mit `{"bulletins":[]}`** statt 404 oder abgelaufenem Dokument.
5. **Feinstufe** (`customData.CH.subdivision`: minus/neutral/plus) als amtliche Zusatzangabe.

Eine Tabellenzeile (Variante B) hätte `_row()` und `_fetch_document` mit Verzweigungen für den
Sonderfall belastet, die Bestandstests der Tabelle (vier Zeilen, ein Host) gebrochen und AT und CH
innerhalb einer Registry-Quelle vermischt — die Entwarnung (ADR-0090) bindet an den Registry-Namen
der Quelle, ein Quellenwechsel AT↔CH wäre dort nicht trennbar.

## Entscheidung

1. **Eigene Quelle `SlfSource`** (`src/services/official_alerts/slf.py`, Registry-Name
   `slf_bulletin`, `source="slf_bulletin:CH-xxxx"`), registriert direkt nach `AvalancheReportSource`.
2. **Geteiltes Modul `caaml.py`** nimmt die reinen CAAML-Funktionen auf, die bisher in
   `avalanche_report.py` standen. Das Verhalten der Quelle avalanche.report bleibt unverändert.
3. **Gleiche Gefahrenart und Skala:** `hazard="avalanche_bulletin"`, `scale="eaws"`, `native_level` 1–5,
   `level=min(native,4)`, `dedup_id=avalanche_bulletin:CH-xxxx` — alle Kanäle, Eskalation und
   Entwarnung bleiben quellenneutral (ADR-0089).
4. **Höhe nur aus Problemen, wenn das Rating keine hat,** und nur bei Eindeutigkeit: alle Probleme, die
   das Träger-Rating tragen (gleiche Stufe, passende Tageszeit), nennen dieselbe Grenze → wörtlich;
   verschiedene Grenzen, fehlende Grenze oder `lowerBound 0` → keine Höhe. Nichts wird erfunden.
5. **Zuständigkeit per Polygon** (CH-Mikroregionen), nie per BBox; keine Ausschlussliste für nie
   bewertete Regionen — „Region nicht im Bulletin" heißt „nicht zuständig".
6. **Leere Saison ist kein Ausfall:** 200 mit leerer Liste → „kein aktueller Bericht", höchstens 1800 s
   gecacht; Netz-/5xx-/Parse-Fehler → „nicht abrufbar".
7. **Feinstufe** (3-, 3, 3+) nur in Langformen (Mail, Telegram-Langform); SMS, Premium-SMS und
   Telegram-Kurzform bleiben `AV<Ziffer>`.
8. **Abschaltbar mit einer Zeile:** die Registrierung in `official_alerts/__init__.py` ist der einzige
   Schalter; ohne sie ist die Quelle vollständig inaktiv (Auflage des PO, Datenquellen-Antrag #7).
9. **Quellenangabe** „WSL-Institut für Schnee- und Lawinenforschung SLF", Link auf den Originalbericht
   und Hinweis, dass der Originalbericht maßgeblich ist.

## Verworfene Alternativen

- **Zeile in `AVALANCHE_REGION_TABLE` (Variante B)** — formal konform mit ADR-0089, faktisch gestreckt:
  Konfigurations-Flags im S1-Code, Bestandstests brechen, AT/CH in einer Quelle für die Entwarnung
  nicht trennbar.
- **Kopie des Parsers in `slf.py`** — zwei Pflegestellen für dieselbe CAAML-Logik.
- **BBox-Zuständigkeit** — reicht bis Vorarlberg, Westtirol, Aosta und den Schwarzwald; Innsbruck
  hätte „SLF nicht abrufbar" ausgelöst.
- **Ausschlussliste für nie bewertete Regionen (Mittelland)** — die Zahl bewerteter Regionen schwankt
  (120–135 in fünf Stichproben); eine feste Liste würde veralten und still Warnungen verschlucken.
- **Höhe „höchste Grenze" oder „erste Grenze" bei Mehrdeutigkeit** — wäre eine eigene Umdeutung einer
  amtlichen Angabe (Haftung).

## Konsequenzen

- **Positiv:** S1-Quelle bleibt unverändert; Renderer, Kanäle, Eskalation und Entwarnung brauchen
  keinen SLF-Sonderfall; ein weiteres Land mit eigenem Dokument-Zuschnitt folgt demselben Muster
  (eigene Quelle + `caaml.py`), ein Land mit der avalanche.report-Form weiter dem Tabelleneintrag.
- **Negativ / Preis:** Zwei Wege, ein Land anzubinden. Im Mittelland (nie bewertet) erzeugt ein
  SLF-Ausfall den generischen Ausfallhinweis, weil dort keine zweite Quelle zuständig ist und den
  Ausfall kompensiert. „Region verschwindet aus dem Bericht" gilt als „nicht zuständig" und ergibt
  keine Entwarnung „beendet" (nur eine echte Absenkung).
- **Folgepflichten:** Die Nutzungsklärung mit dem SLF (schriftliche Anfrage) ist offen; lehnt das SLF
  ab, wird die Registrierungszeile entfernt. Quellenangabe, Link und Maßgeblichkeitshinweis müssen in
  jeder Langform stehen. Eine neue Stufen-Renderstelle mit Feinstufe holt den Suffix aus demselben
  zentralen Helfer (`avalanche_bulletin_text`).
