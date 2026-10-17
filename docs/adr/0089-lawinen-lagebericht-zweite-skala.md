# ADR-0089: Lawinen-Lagebericht als zweite Skala neben der Awareness-Skala

- **Status:** Akzeptiert (teilweise ergänzt durch ADR-0091)
- **Datum:** 2026-10-13
- **Bezug:** GitHub-Issue #1441 Slice 1 (Epic #2258, erledigt #1473), Spec
  `docs/specs/modules/avalanche_report_bulletin.md`; ergänzt ADR-0016 (additiver Warntyp),
  nutzt ADR-0018 (fail-soft ohne Maskierung), ADR-0041 (Zuständigkeit), ADR-0044 (Ortszeit)

## Kontext

ADR-0016 führt `OfficialAlert` als additiven Datentyp ein und legt `level` auf die
Awareness-Skala 1-4 fest (grün/gelb/orange/rot). Der amtliche Lawinen-Lagebericht
(avalanche.report, CAAML v6) spricht eine andere Skala: die EAWS-Gefahrenstufe 1-5
(gering, mäßig, erheblich, groß, sehr groß) mit Höhengrenze und Lawinenproblem. MeteoAlarm
liefert daneben weiterhin eine Lawinen-*Warnung* auf der Awareness-Skala (`avalanche`, `AW`).

Würde der Lagebericht in `level` gequetscht, ginge Stufe 5 verloren (5 → 4) und die
Zusammenführung "höchste Stufe gewinnt" verglich zwei Skalen miteinander.

## Entscheidung

1. Eigene Gefahrenart `avalanche_bulletin` (SMS-Kürzel `AV`, exklusiv) neben `avalanche` (`AW`).
   Beide amtlichen Aussagen dürfen parallel erscheinen; es gibt keinen skalenübergreifenden
   Vergleich (Dublettenwahl in `base.py` arbeitet je Gefahrenart).
2. `OfficialAlert` erhält additive Felder mit Bestands-Defaults: `scale` (`"awareness"` /
   `"eaws"`), `native_level` (1-5, Originalstufe), `elevation_value`/`elevation_direction`
   (wörtlich, inkl. "Waldgrenze"), `problems` (CAAML-Codes), `time_of_day`.
3. `level` bleibt Pflichtfeld und ist für den Lagebericht nur die abgeleitete Farbe
   (1→1, 2→2, 3→3, 4→4, 5→4).
4. Vergleiche innerhalb einer Gefahrenart (Dublettenwahl, Eskalation, Melde-Gedächtnis) nutzen
   `native_level`, falls gesetzt, sonst `level` (`models.comparable_level`). Stufe 4 → 5 eskaliert.
5. Darstellung: Wortlaut des Warndienstes ("Lawinenstufe 4 (groß) oberhalb Waldgrenze ·
   Triebschnee") statt Awareness-Leiter ("n/3", GELB/ORANGE/ROT); SMS-Token `AV<Ziffer>` ohne
   Doppelpunkt und ohne L/M/H, im `!`-Warnblock, genau einmal (nicht mehr aus `_wintersport()`).
6. Eskalationsgedächtnis-Identität ist die Mikroregion (`dedup_id = avalanche_bulletin:<regionID>`),
   nicht die täglich wechselnde Bulletin-ID — gleiche Stufe am Folgetag alarmiert nicht neu.

## Konsequenzen

- Bestandswarnungen bleiben bit-identisch (alle neuen Felder mit Default).
- Ein weiteres Land ist ein Tabelleneintrag (`AVALANCHE_REGION_TABLE`) plus Regionsdatei und
  Egress-Host — kein Parser-/Renderer-Code. *(Teilweise ergänzt durch ADR-0091: Die Schweiz (SLF)
  folgt wegen anderem Dokument-Zuschnitt dem Muster eigene Quelle + geteiltes `caaml.py`.)*
- Jede Stufen-Renderstelle braucht für diese Gefahrenart eine explizite Zuordnung (Stufe 1 ist
  Info, nie HIGH; Stufe 5 nie schwächer als 4).
- Die toten DTOs `AvalancheDanger`/`AvalancheReport` in `src/app/models.py` werden nicht
  wiederbelebt.
