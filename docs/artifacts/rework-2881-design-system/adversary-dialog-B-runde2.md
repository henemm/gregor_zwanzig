# Adversary B Runde 2 (Zwischenstand): Setup laeuft, Code von 01d9f0c gelesen.
Stack lokal (wt-adv-b2, 8091/8000). DS+issue-498: 66 gruen, 1 rot (AC-15 stale, bekannt). AC-32 jetzt GRUEN (F-B1 geschlossen).
Probe-Spec e2e/zz-probe.spec.ts (untracked im Worktree): Funde vorlaeufig:
 P1 Tag "4" (Segment schliesst sofort) ohne Verlassen NICHT gespeichert (gehalten bis Blur)
 P3 Tag "3" angefangen, Kalender-Knopf, Tag 15 gewaehlt: nicht gespeichert (zu pruefen)
 P6 Anlegen: Jahr "20" angefangen, Blur: "Startdatum fehlt" erscheint NICHT (zu pruefen)
 P2/P4/P5/P7 ok (P5: Minute leeren => Startzeit zurueck auf 08:00)
Korrektur: P1/P3 (nach Korrektur der Probe: einstufiger Trip, sonst Kaskaden-Rueckfrage) GRUEN; P6/P9/P10: Jahr "20" aendert die Anzeige nicht (bits-ui), kein Befund; Anlegen Leeren (Tag/Jahr Backspace) gruen.
P11 (Rollback eines fehlgeschlagenen PUT trifft ein, waehrend Fokus im Monat): bits-ui behandelt die naechste Ziffer danach anders (Monat 01 + Sprung) — beobachtet, Anzeige = gespeichert, kein Datenverlust (LOW/Beobachtung).
Naechster Schritt: Mutationen M1..M12 auf segmentFeldMeldung.ts / DatumFeld / UhrzeitFeld.
Mutationen (Ziel: DS-Faelle + node segment_feld_meldung + issue-498 AC-32), rot=gefangen:
M1 ohne tipptIn: gruen(redundant) | M2 ohne zaehler: gruen(redundant) | M1+M2 (Runde-2 tippt): rot
M3 abschliessen no-op: rot (DS-1 Leeren, node) | M4 verwerfen bei fremdem Wechsel: GRUEN | M5 ohne tick: GRUEN
M7 fokus-reset weg: GRUEN | M9 trigger zaehlt: rot DS-1 de | M10 beforeinput weg: GRUEN
M11 Datum geleert-Pfad weg: GRUEN | M12 Datum leer nicht halten: GRUEN | M13 Uhr geleert weg: rot DS-2 Leeren
M14 Uhr ohne tippt: rot | M15 Uhr aufbau weg: GRUEN | M16 Datum aufbau weg: rot DS-2 Leeren
M17 year<1000 -> <1: GRUEN, real: Etappe Jahr "202" + Verlassen speichert 0202-08-01 (P12 belegt) | M18 iso===value verwerfen weg: GRUEN
