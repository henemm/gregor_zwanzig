# Adversary-Dialog #2880 (rework-2880-paritaet)

Runde 1: Basislauf PF-1..PF-6 + anlege-rahmen-paritaet + hub-anlegen-ablauf: 97 passed, 6 failed (nur AR-21/AR-22, bekannt flaky auf main).
Hinweis: nach vielen Registrierungen schlagen PF-4/5 wegen 429 fehl (Stack-Neustart noetig, Rauschen, kein Befund); Mutationslaeufe mit Stack-Neustart je Lauf.

Runde 2: Mutationen (String-Ersetzung, Sicherung im Scratchpad, am Ende diff identisch, git status sauber)

| Mutation | Ergebnis |
|---|---|
| a .tab-panel-Padding 1.5rem zurueck | gefangen PF-1/2/3 |
| b Trip-Uebersicht 4px Abstandhalter INNERHALB der Reiterflaeche | NICHT GEFANGEN (PF-1 misst nur die Flaeche selbst, nicht das erste echte Inhaltselement) |
| c Trip Name ohne pflicht | gefangen PF-4/5 |
| d2 Vergleich optional:false | nicht beobachtbar (Vergleich hat keinen optionalen Schritt) |
| e aria-required Vergleich entfernt | gefangen PF-4 |
| f Stern in Field entfernt | gefangen PF-4 |
| g Mobil min-height 44 -> 36 | NICHT GEFANGEN (natuerliche Hoehe 13+13+Zeile >= 44) |
| h gesperrter Reiter ruft onWahl nicht | gefangen nur von issue-661/682 AC-2, nicht von PF/ablauf |
| i Handy-Padding 20 -> 24 | gefangen PF-3 |
| j MField side entfernt | gefangen PF-5 |
| k aria-disabled entfernt | gefangen PF-6 |
| l Optional-Pille aus | gefangen PF-6 |
| m tabindex entfernt (gesperrter Reiter fokussierbar) | NICHT GEFANGEN |
| n Sperr-Marker entfernt | gefangen AN-1, PF-6 |
| o max-width 1480 entfernt | NICHT GEFANGEN (kein Breitbild-Test) |

## Fix-Loop (Developer, 2026-11-09)

Tech-Lead-Entscheidungen zu den Findings: F001 (MEDIUM) PF-1/PF-2 messen das erste Inhaltselement in der Reiterflaeche; F002 (LOW) Mindesthoehe am Handy direkt pruefen; F003 gesperrte Schritt-Reiter bleiben per Tastatur erreichbar (WAI-ARIA, neues AC-8 / PF-7); F004 (LOW) PF-3 auch bei 1920 px; Mutation h bleibt bei issue-661/682 (keine Aenderung).

Umsetzung:
- `frontend/e2e/hub-anlegen-paritaet-flaechen.spec.ts`: `messeHub()` liefert zusaetzlich `inhalt` = erstes sichtbares Kind der Reiterflaeche mit Inhalt (Text oder Bild/SVG/Eingabe; leere Abstandhalter zaehlen nicht). PF-1/PF-2 vergleichen dessen linken Rand und Abstand zur Oberkante der Flaeche (Bezug Flaeche statt Leiste, weil die Trip-Etappen-Flaeche am Computer unter dem Etappen-Band steht; ihre Lage zur Leiste sichert PF-3). PF-6 prueft am Handy zusaetzlich `getComputedStyle().minHeight >= 44`. PF-3 laeuft zusaetzlich bei 1920 x 1080 mit Breite <= 1480 und Trip = Vergleich. Neu PF-7 (1440/390, je Trip und Vergleich): aktiver Reiter fokussiert, Pfeil rechts erreicht den gesperrten Reiter (aria-disabled=true), Enter und Leertaste wechseln nicht.
- `shared/anlege-rahmen/AnlegeReiter.svelte`: roving tabindex (aktiver Reiter 0, sonst -1; vorher gesperrt -1, sonst 0), Pfeil links/rechts und Pos1/Ende bewegen den Fokus ueber ALLE Reiter inkl. gesperrter; Enter/Leertaste bleiben native Button-Aktivierung -> `onWahl` -> Aufrufer zeigt Hinweis/Toast und wechselt nicht.
- Golden f9/f10 (de/en, je 6 Anlege-Faelle) neu geschrieben: Diff ausschliesslich `tabindex`-Werte der Schritt-Reiter (geprueft: nach Normalisierung `tabindex="X"` byte-gleich zu HEAD).
- Spec: AC-8 (Tech-Lead-Ergaenzung aus F003), Test Plan, DoD, Changelog. CI: `E2E_MIN_EXECUTED_HAUPT` 646 -> 650 (+2 PF-3 1920, +2 PF-7).

Mutationsnachweis (String-Ersetzung, Sicherung in scratchpad/bak-fl2880, nach jedem Lauf zurueckgespielt und byte-verglichen; git status danach nur die beabsichtigten Aenderungen):

| Mutation | Ziel | Ergebnis |
|---|---|---|
| b1 Trip-Uebersicht: `<div style="height:4px">` als erstes Kind IN der Reiterflaeche | F001 | gefangen PF-1 + PF-2 Uebersicht (ist 28/20, soll 32/24) |
| b2 Trip-Uebersicht: Huelle mit `margin-top:4px` IN der Reiterflaeche | F001 | gefangen PF-1 + PF-2 Uebersicht |
| g Handy `min-height: 44px` -> `36px` | F002 | gefangen PF-6 (390) „min-height am Handy >= 44 px" |
| m1 Altstand: gesperrt `tabindex=-1`, keine Pfeiltasten | F003 | gefangen PF-7 (1440 + 390) |
| m2 Pfeiltasten ueberspringen gesperrte Reiter (`:not([aria-disabled])`) | F003 | gefangen PF-7 (1440 + 390) |
| m3 Vergleich `switchTab` ohne Sperr-Waechter (Enter wechselt) | F003 | gefangen PF-7 (1440) „vergleich: Enter wechselt nicht" |
| o `max-width: 1480px` entfernt | F004 | gefangen PF-3 (1920) Uebersicht + Etappen/Orte; 1440/390 blieben gruen |

Laeufe am Endstand: PF-Datei 25/25 (inkl. setup); PF + hub-anlegen-ablauf + issue-661 + issue-682 + trip-new-loads-without-effect-loop 75/75 (Stack frisch gestartet); Unit-Tests mit AnlegeReiter/Trip-/Vergleich-Anlegen 753/753 (53 Dateien); Golden trip_hub_sprache + vergleich_hub_sprache 546/546.
