# Context: #1420 — Mail-Prüfer lernt die neuen Übersichts-Beschriftungen

Workflow `fix-1420-validator-uebersichtslabels`. Vorbedingung für #1401 A2b.
Direkte Fortsetzung von #1404. Analyse stammt aus dem A2b-Lauf
(`docs/context/fix-1401-a2b.md`, Abschnitt „Der Prüfwerkzeug-Konflikt").

## Request Summary

`_OVERVIEW_METRIC_CHECKS` im Pflicht-Prüfer kennt nur die heutigen deutschen
Beschriftungen der Vergleichs-Übersichtstabelle. #1401 A2b stellt alle 26 auf
englische Kurzformen um. Ohne Vorarbeit fallen 24 Plausibilitätsprüfungen
still aus **und** ein Kern-Test wird rot. Dieses Ticket erweitert den Prüfer
auf Alt∪Neu — strikt additiv, Muster `_HOUR_COLUMNS_V2` aus #1404.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/email_spec_validator.py:576` | `_OVERVIEW_METRIC_CHECKS` — 24 deutsche Schlüssel, MODIFY |
| `.claude/hooks/email_spec_validator.py:848,885` | `check = ….get(label); if check is None: continue` — der stille Durchfall |
| `.claude/hooks/email_spec_validator.py:528,541` | `_HOUR_COLUMNS_V2` + `_HOUR_COLUMNS_V2_REVIEW_DATE` — **Vorbild** der Übergangs-Union |
| `tests/unit/test_compare_mail_overview_plausibility_coverage.py:44,46` | `EXEMPT_LABELS` (wörtlich deutsch), `NUMERIC_LABELS` (liest `CV2_METRICS` zur Laufzeit), MODIFY |
| `tests/unit/test_compare_mail_validator_column_order.py` | Bestandsschutz aus #1404 — muss unverändert grün bleiben, NICHT anfassen |
| `docs/specs/modules/fix_1401_a2_mailtabellen.md` | Quelle der Ziel-Beschriftungen („Ziel-Beschriftung je Zeile") |
| `docs/specs/modules/fix_1404_validator_spaltennamen.md` | Vorgänger, Begründung der Union-Mechanik |

## Ziel-Abbildung alt → neu (aus der A2-Spec, PO-freigegeben 2026-07-28)

Bleiben gleich: `Temp max`, `Temp min`, `Wind`, `CAPE`.
Neu hinzu: `Sonne`→`Sun` · `Wolken`→`Cloud` · `UV max`→`UV` · `Regen`→`Rain` ·
`Regenwahrscheinlichkeit`→`Rain%` · `Sicht min`→`Visib` · `Schneehöhe`→`SnowH` ·
`Neuschnee`→`NewSn` · `Böen`→`Gust` · `Nullgradgrenze`→`0°Line` ·
`Windrichtung`→`WDir` · `Gefühlte Temp. min`→`Feels min` ·
`Gefühlte Temp. max`→`Feels max` · `Wolken tief`→`CldLow` ·
`Wolken mittel`→`CldMid` · `Wolken hoch`→`CldHi` ·
`Luftfeuchtigkeit Ø`→`Humid` · `Taupunkt Ø`→`Cond°` · `Luftdruck Ø`→`hPa` ·
`Schneefallgrenze`→`SnowL`.

**Kollisionsvarianten sind Pflicht:** Der Auswertungs-Zusatz in A2b ist
auswahlabhängig. Wählt der Nutzer nur den Höchstwert, heißt die Zeile `Temp`
(ohne Zusatz); wählt er beide, `Temp max`/`Temp min`. Also müssen **alle drei**
Formen je betroffener Größe eingetragen sein: `Temp`, `Temp max`, `Temp min`
sowie `Feels`, `Feels max`, `Feels min`.

Ausnahmeliste (`EXEMPT_LABELS`, keine Zahlenwerte): `Amtliche Warnungen`
bleibt; `Gewitter` bekommt `Thdr` dazu, `Niederschlagsart` bekommt `PType`.

## Dependencies

- **Upstream:** keine — reine Prüfwerkzeug-Änderung.
- **Downstream:** #1401 A2b ist ohne diese Lieferung nicht committefähig.
- Regex und Wertebereich je Zeile werden **unverändert** vom alten Eintrag
  übernommen; für die zusatzlose Form (`Temp`, `Feels`) gilt der jeweils
  weitere der beiden Bereiche, weil offen ist, welche Auswertung dahintersteht.

## Risks & Considerations

1. **Kein Verhaltenszweig auf dem Prüfdatum.** Wie in #1404: ein Datum, das
   die Union am Stichtag selbst verengt, würde die dann korrekte Mail wieder
   ablehnen. Reiner Erinnerungsmarker.
2. **Gold-Standard braucht drei Richtungen**, nicht zwei: neue Fassung
   akzeptiert, heutige Fassung akzeptiert, Fremd-Beschriftung weiterhin
   namentlich abgelehnt. Ohne die dritte ist es nur eine längere Erlaubt-Liste.
3. **Änderung an einer Infrastruktur-Datei** (`.claude/hooks/`) — braucht
   ausdrückliche PO-Freigabe, wie bei #1404.
4. **Nicht in diesem Ticket:** „unbekannte Beschriftung = lauter Befund"
   und der Rückbau der Union — beides gehört in die bereits vorgesehene
   Lieferung **nach** A2b. Kein Eingriff in `compare_html.py`/`comparison.py`.
