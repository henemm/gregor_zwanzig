# ADR-0043: Die Empfindlichkeitsstufe ist der einzige Alarm-Regler — bei Gefahrenstufen-Größen wirkt sie über das erreichte Niveau (löst ADR-0040 ab)

- **Status:** Akzeptiert (PO-„go" 2026-08-02, erweitert 2026-08-03)
- **Datum:** 2026-08-03
- **Bezug:** Issue #1460 (Epic #1458 Scheibe 2, Teil 1), Spec `docs/specs/modules/rework_1460_t1_relevanzfilter.md`; **löst ADR-0040 ab**; bestätigt ADR-0009 (Alarme sind Abweichungs-Wächter) und ADR-0013 (`threshold` ist Δ-Sensitivität); berührt ADR-0016 (amtliche Warnungen als additiver Typ), ADR-0021 (geteilte `DeviationAlertEngine`)

## Kontext

ADR-0040 hat auf einen echten Betriebsbefund reagiert: Der Trip „KHW 403" lief
sechs Wochen mit gesetzten Wertebereichen und meldete nie ein Gewitter. Die
Diagnose war richtig — **Stille bei anhaltender Gefahr** ist ein reales
Versagensmuster. Die Antwort war es nicht: Sie führte mit dem Schwellen-Alarm
einen zweiten Alarm-Typ ein, dessen Auslöser eine **absolute Grenze** ist.

Damit hatte das Produkt zwei Regler für dieselbe Frage („wann ist eine
Wetterlage meldenswert?"): die Empfindlichkeitsstufe (`metric_alert_levels`,
entspannt · standard · sensibel) und den Wertebereich (`corridors[].notify`).
Zwei Regler, die sich weder gegenseitig kennen noch demselben Prinzip folgen —
der eine vergleicht gegen den letzten Briefing-Stand, der andere gegen einen
festen Zahlenwert. Genau diese Doppelung widerspricht ADR-0009, das absolute
Schwellen ausdrücklich verworfen hat.

Die Analyse zu #1460 hat gezeigt, dass der Befund von ADR-0040 gar keinen
zweiten Alarm-Typ braucht — er hatte eine schlichtere Ursache. Bei Gewitter,
der einzigen Gefahrenstufen-Größe des Produkts (`ThunderLevel`: kein Gewitter ·
mittel · hoch), meldete **keine** der drei Empfindlichkeitsstufen einen Sprung
um genau eine Stufe. Grund: Die Stufen-Tabelle trägt für Gewitter in allen drei
Stufen denselben Delta-Wert `1`, und der Änderungs-Wächter vergleicht
`abs(delta) > threshold` — bei einem Sprung von genau einer Stufe ist
`1 > 1` falsch. Es meldete also nur der volle Sprung über zwei Stufen, und das
in allen drei Stufen gleich. Die Empfindlichkeitsstufe war für Gewitter faktisch
wirkungslos.

Ein Nutzer, der Gewitter auf „sensibel" gestellt hat, hätte den KHW-403-Fall
korrekt gemeldet bekommen, sobald die Vorhersage von „kein Gewitter" auf
„mittel" steigt. Der Regler war da; er hat nur nichts getan.

## Entscheidung

**Die Empfindlichkeitsstufe ist der einzige Alarm-Regler. Der Wertebereich
(`corridors[].notify`) verliert seine Alarm-Wirkung ersatzlos.**

Bei Gefahrenstufen-Größen entscheidet die Stufe über das erreichte bzw.
verlassene **Niveau**, nicht über die Sprunggröße:

| Empfindlichkeit | meldet die Verschärfung, wenn … | meldet die Entwarnung, wenn … |
|---|---|---|
| sensibel | die Gefahrenstufe überhaupt steigt | sie überhaupt sinkt |
| standard | die höchste Stufe erreicht wird | die höchste Stufe verlassen wird |
| entspannt | sie von „keine Gefahr" direkt auf die höchste Stufe springt | sie von der höchsten Stufe direkt auf „keine Gefahr" zurückgeht |

Ein unveränderter Wert meldet nie. **Beide Richtungen melden symmetrisch** — für
den Wanderer ist „die Gefahr ist weg" eine ebenso entscheidungsrelevante
Nachricht wie „die Gefahr kommt": beide werfen seine Planung um, und genau das
ist laut ADR-0009 das Auslöse-Kriterium. Die stetigen Größen (Böen, Regen,
Temperatur) melden über `abs(delta)` ohnehin seit jeher beide Richtungen; die
ordinale Sonderbehandlung führt dieses Verhalten fort, statt es für
Gefahrenstufen-Größen als Sonderfall zu brechen.

**ADR-0009 und ADR-0013 werden bestätigt, nicht berührt.** Die Auswertung bleibt
in beiden Fällen ein Vergleich gegen den zuletzt versendeten Briefing-Stand, nie
gegen einen absoluten Systemwert. Bei Gefahrenstufen-Größen ist die
„Δ-Sensitivität" nur keine Zahl mehr, sondern ein Niveau — eine Präzisierung der
bestehenden Entscheidung, keine neue.

`Corridor.notify` bleibt im Datenmodell und in der Persistenz **erhalten** und
lädt/speichert unverändert; es verliert ausschließlich seine Wirkung. Kein
Bestandstrip verliert Daten. `Corridor.range`/`Corridor.mark` (Anzeige-Markierung
im Ortsvergleich) sind davon ohnehin unberührt — sie waren nie ein Alarm-Auslöser.

## Verworfene Alternativen

- **ADR-0040 stehen lassen und beide Regler nebeneinander betreiben.** Verworfen:
  Zwei Regler für dieselbe Frage sind für den Nutzer nicht erklärbar („warum
  meldet meine Grenze, obwohl ich auf entspannt stehe?") und für die
  Weiterentwicklung doppelte Arbeit — jede neue alarmfähige Größe müsste in
  beiden Wächtern bedacht werden. Der Preis, den ADR-0040 unter „Negativ"
  selbst benannt hat, ist eingetreten, bevor der Nutzen eingetreten war.
- **Den Wertebereich behalten, aber nur als „zweite Meinung" ohne eigene
  Meldung.** Verworfen: Eine Konfigurationsfläche ohne sichtbare Wirkung ist
  genau der Fehler, den #1425 S2c schon einmal beseitigt hat.
- **Eine allgemeine Registry „welche Größen sind ordinal" bauen.** Verworfen für
  jetzt: Es gibt exakt eine solche Größe (Gewitter). Eine generische
  Erkennungs-Infrastruktur wäre Struktur ohne zweiten Anwendungsfall; kommt eine
  zweite Gefahrenstufen-Größe hinzu, macht die Wiederholung sichtbar, ob sich
  eine Verallgemeinerung lohnt. Bis dahin steht die Stufen-Tabelle an genau
  einer Stelle (`services/alert_preset.py`, `ORDINAL_LEVEL_BOUNDS`).
- **Nur die Verschärfung melden, die Entwarnung unterdrücken.** So stand es in
  der ersten Fassung der Spec, begründet mit ADR-0009. Diese Berufung war falsch:
  ADR-0009 fordert den Vergleich gegen den Briefing-Stand statt gegen eine
  absolute Schwelle und sagt zur **Richtung** der Abweichung nichts. Der PO hat
  am 2026-08-03 entschieden: „Ja, eine Entwarnung ist auch wichtig, also wenn
  sich der Forecast positiv entwickelt."

## Konsequenzen

- **Positiv:** Ein Regler statt zwei. Die Empfindlichkeitsstufe tut endlich, was
  ihr Name verspricht — auch bei Gewitter. Der KHW-403-Fall wäre auf „sensibel"
  gemeldet worden. Der Render-Vertrag für Schwellen-Treffer wird nie wieder
  gefüttert; es bleibt eine Meldungsart statt zweier.
- **Negativ / Preis:** Eine Tour, die bisher **ausschließlich** über
  Wertebereiche alarmiert wurde, alarmiert nach dieser Entscheidung gar nicht
  mehr, bis ihr Besitzer eine Empfindlichkeitsstufe setzt. Das ist sichtbar
  gemacht, nicht stillschweigend in Kauf genommen (AC-1 der Spec).
- **Mehr Meldungen bei Gewitter**, in beiden Richtungen — heute stumm bei genau
  einem Stufenwechsel. Das ist der Zweck der Reparatur; die Tages-Obergrenze
  (`alert_daily_limit`) bleibt die Grenze nach oben.
- **Offene Restarbeit:** Der Korridor-Render-Vertrag (`to_corridor_events()`,
  `CorridorEvent`, `services/corridor_threshold.py`,
  `alert_log.register_pairs_from_corridor_hits()`) bleibt bestehen, wird aber nie
  mehr mit Inhalt aufgerufen. Sein Rückbau ist eine Aufräumarbeit über alle
  Ausgabewege hinweg und gehört nicht in diese Scheibe.
- **Solange die Mittelstufe keine Datenquelle hat** (`_parse_thunder_level()`
  liefert heute nur „kein Gewitter" oder „hoch", #1419 S3), verhalten sich
  „standard" und „entspannt" im Live-Betrieb identisch. Sobald #1419 S3 der
  Mittelstufe eine Quelle gibt, muss deren Einstufung genau der Tabelle oben
  entsprechen — sonst driften Datenbeschaffung und Alarm-Semantik auseinander.
