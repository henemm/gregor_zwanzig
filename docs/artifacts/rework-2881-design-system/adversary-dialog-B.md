# Adversary Lieferung B (#2881) — Kopf 565283e

VERDICT: AMBIGUOUS (kein AC rot, Pflicht-Mutationen d/e/f gefangen; mehrere Zusicherungen nicht bewacht, ein Regress in einer Spec ausserhalb der CI-Positivliste)

Tests: design-system-trip-vergleich 22/22 gruen; 10 geaenderte Node-Testdateien 607/607 gruen.
Breiter Lauf der 36 geaenderten e2e-Specs (410 Faelle): 361 gruen, 49 rot. Davon nicht aus B: anlege-rahmen-paritaet (22, Spec nicht auf CI-Liste, Segmentzahl/Abblenden aus A/#2794), locations (4, Anlegen laeuft ueber LocationNewModal, nie Dialog), issue-675 AC-3/4/5 ("Etappen speichern" gibt es nicht mehr), versandzeit-stundenwahl AC-4, issue-498 AC-15 (auch auf Basis A rot). DS-5 leer ist zustandsabhaengig (gruen auf frischem Stack, rot nach Vorlaeufen). Neu durch B rot, auf Basis A gruen: issue-498 AC-32 (F-B1).

## Mutationstabelle
| Mutation | roter Test |
|---|---|
| d BackLink 44->36 | ja DS-6 |
| e DatumFeld gibt MM/DD/YYYY | ja DS-1 de/en, DS-2, DS-3, DS-9 |
| f SaveIndicator Dot -> ✓ | ja DS-3 (4 Faelle) |
| AnlegeReiter Dot -> ✓ | ja DS-3 |
| en-Locale DatumFeld en-US | ja DS-1 en, DS-3 en |
| weekStartsOn 1 -> 0 | ja DS-1 (3) |
| Mail-Format onChange immer 'full' | ja DS-4 |
| Chip 44 -> 36 / ⓘ 44 -> 36 / Standardwerte 44 -> 36 | ja DS-6 |
| VTSchedulePlan Select-Wert verworfen | ja hub-versand-* (nicht DS) |
| DatumFeld sperren()+aufbau / nur aufbau entfernt | NEIN (nur issue-498 AC-15/AC-32, beide ohne Mutation schon rot, Spec nicht auf CI-Liste) |
| DatumFeld tipptIn(feld) -> false | NEIN |
| UhrzeitFeld leerMelden entfernt (#675 AC-5) | NEIN (issue-675 stale rot) |
| Select LEER-Abbildung entfernt ('Standard' -> '__gz_leer__') | NEIN |
| Segmented roving tabindex entfernt | NEIN |
| UhrzeitFeld en: en-US ohne hourCycle 24 (AM/PM im en-UI) | NEIN (DS-2 nur de) |
| UhrzeitFeld hourCycle 24 -> 12 | NEIN (vermutlich wirkungslos mit de-DE) |

## Findings
F-B1 MEDIUM regression: issue-498 AC-32 rot auf B, gruen auf A. Im Fehlerzustand (Kaskaden-PUT scheitert) geht beim Tippen in Etappe 3 der Zwischenstand "02.08.2026" (erste Ziffer 2) als PUT raus; s3 bleibt gespeichert 2026-08-02, waehrend das Feld 26.08.2026 zeigt. Code: frontend/src/lib/components/molecules/DatumFeld.svelte:70 (meldung.aendern(iso, tipptIn(feld))) / segmentFeldMeldung.ts tipptIn. Ohne Fehlerzustand nur ein PUT (geprueft 30/150/400 ms). Spec liegt nicht auf .github/ci_e2e_specs.txt, wird nicht bewacht.
F-B2 MEDIUM edge_case: Leeren eines Datumsfelds meldet nichts nach aussen (DatumFeld.svelte:67 `if (!neu || neu.year < 1000) return`). Native Felder meldeten ''. Beim Anlegen: Feld zeigt Teilwert (z. B. "01.01.202"), Hinweis "Startdatum fehlt" erscheint nicht, Datum im Modell bleibt der letzte vollstaendige Zwischenwert. Etappe: Backspace auf Tag zeigt "tt.mm.jjjj", API und Neuladen behalten altes Datum.
F-B3 MEDIUM anti_pattern (Mutation): sperren()/aufbau (DatumFeld.svelte:57-58, UhrzeitFeld.svelte:50-51) und tipptIn (DatumFeld.svelte:70), leerMelden (UhrzeitFeld.svelte:74) und Select-LEER (ui/select/Select.svelte:28 `aussen`) haben keinen gruenen Test an der Wirkstelle; Melde-Regel nur als Klasse im Node-Test (segment_feld_meldung.test.ts), nicht verdrahtet; Etappenwechsel-Schutz nur durch off-list Spec.
F-B4 LOW spec_violation(R3): ✓ bleibt sichtbar im Reiter Wetter (WeatherV2Grundauswahl.svelte:60, Anlege-Schritt und Hub-Wetter), weil DS-3 diesen Reiter nicht prueft; AC-3 nennt ihn nicht, ADR-0111 Punkt 7 sagt allgemein.
F-B5 LOW: 24-h im en-UI (UhrzeitFeld.svelte hourCycle/locale) nicht getestet (nur de).
F-B6 LOW: DS-5 leer haengt vom Stack-Zustand ab (rot nach Fremdlaeufen).

## Geprueft ohne Befund
Etappenwechsel (de/en, 1280): s2 zeigt 02.08./08:00, s3 06:45, s1 09:15, kein API-Schreiben beim Wechsel; Zeit tippen + sofort wechseln speichert. Datum/Zeit nach Neuladen YYYY-MM-DD/HH:MM, de/en. Select: Maus, Enter/Pfeil/Enter, Standard-Option, Escape schliesst nur Liste im Dialog (LocationForm, mit Profil- und Gruppenfeld). CreateGroupDialog/WeatherConfigDialog sind ungenutzt (kein Aufrufer). Mandantentrennung: keine Aenderung an Go/Python, nicht beruehrt.
