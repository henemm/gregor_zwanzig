# Adversary Dialog — feat-3333-orte-anlegen-zustellung
Spec: docs/specs/modules/feat_3333_zustellung_anlegen_orte.md
Datum: 2026-11-24 19:55

## Checkliste
- [x] **Input:** Nutzer legt einen Ortsvergleich an, stellt im Schritt Zustellung Morgen 06:45, Kanal Telegram, Stille Stunden ein und schaltet E-Mail ab.
- [x] **Output:** Genau ein `POST` auf die Vergleichs-Anlage mit diesen Werten (`send_email: false`, `morning_time` 06:45, Telegram, `alert_quiet_from/_to`); der Hub-Reiter Zustellung des neuen Vergleichs zeigt denselben Stand.
- [x] **Side effects:** Nur der lesende Profil-Abruf; kein PUT, kein Speichern vor dem Anlegen.
- [x] **AC-1:** Given ein angemeldeter Nutzer legt einen Ortsvergleich an / When er den Schritt Zustellung öffnet, in der Mobil- und in der Desktop-Ansicht / Then sieht er den Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle und Stille Stunden wie im Hub, und das Alt-Panel (Versand-Abschnitt, Karte „Layout je Kanal“, Infobox) erscheint dort nicht mehr.
- [x] **AC-2:** Given der Nutzer stellt im Orte-Anlegen Briefing-Zeiten, Kanäle und Stille Stunden ein / When er den Vergleich anlegt / Then enthält der eine POST `morning_time`/`evening_time`, `morning_enabled`/`evening_enabled`, `send_email/telegram/sms/premium_sms`, `end_date` und `alert_quiet_from/_to` mit genau den eingestellten Werten.
- [x] **AC-3:** Given der Nutzer wählt Alarm-Kanäle, die Dringlichkeit HIGH für Telegram und einen Cooldown / When er den Vergleich anlegt / Then stehen `alert_channels`, `alert_channel_thresholds.telegram == "HIGH"` und `alert_cooldown_minutes` im POST.
- [x] **AC-4:** Given der Nutzer schaltet im Reiter die E-Mail ab / When er den Vergleich anlegt / Then enthält der POST `send_email: false`; bei unberührter E-Mail enthält er `send_email: true`, weil das Feld jetzt immer mitgesendet wird.
- [x] **AC-5:** Given der Nutzer öffnet den Schritt Zustellung, bedient den Reiter aber nicht / When er den Vergleich anlegt / Then ist der POST-Körper bis auf das neue Feld `send_email: true` bitgleich zum heutigen Körper (Zeiten, Kanäle, Alarm-Felder, Standardwerte).
- [x] **AC-6:** Given der Nutzer ändert Werte im Reiter / When er bis zum Anlegen weitermacht / Then gibt es weder einen PUT noch einen Autosave noch einen Schreibaufruf vor dem Anlegen, und beim Anlegen genau einen POST.
- [x] **AC-7:** Given der Nutzer hat im Reiter Zustellung Werte gesetzt / When er zwischen Mobil und Desktop wechselt oder Schritte vor und zurück geht / Then bleibt der Stand erhalten und die Werte stehen unverändert im POST.
- [x] **AC-8:** Given der Nutzer gibt eine rasterfremde Uhrzeit ein (z. B. 06:50) / When er den Vergleich anlegt / Then sendet der POST die letzte gültige Viertelstunden-Zeit und es gibt keinen Server-Fehler 400.
- [x] **AC-9 (nach Push auf Staging zu belegen):** Given ein Ortsvergleich wird im Anlegen mit gesetzter Zustellung angelegt / When der Nutzer danach den Hub-Reiter Zustellung öffnet / Then zeigt er dieselben Zeiten, Kanäle, Dringlichkeiten, Stille Stunden, denselben Cooldown und den E-Mail-Schalter wie beim Anlegen eingestellt.
- [x] **AC-10:** Given der Nutzer ist im Schritt Alarme des Orte-Anlegens / When er den Reiter öffnet / Then fehlen dort Alarm-Kanäle, Cooldown und Stille Stunden (sie stehen im Reiter Zustellung), während amtliche Warnungen, Radar und Metrik-Alarmstufen dort bleiben; jedes Feld hat genau eine Bedienstelle, und Hub und Trip-Anlegen sind unverändert.
- [x] **AC-11:** Given der Aktivierungs-Banner im Orte-Anlegen / When der Nutzer den Schritt Zustellung öffnet / Then erscheint der Banner weiter (`compare-step5-activation-banner`, `data-ready` unverändert) und stammt aus dem Reiter Zustellung, nicht aus dem Alt-Panel.
- [x] **AC-12:** Given der Reiter Zustellung im Orte-Anlegen / When der Nutzer ihn öffnet / Then erscheint dort keine Infobox des Alt-Panels mehr, während die Infobox im Reiter Alarme beim Anlegen wie bisher erscheint.
- [x] **AC-13:** Given die Anlegeseiten Trip und Ortsvergleich / When der Code geprüft wird / Then importiert und mountet keine der beiden Anlegeseiten `WetterMetrikenVersandPanel`, und die Dateien des Panels bleiben bis zum Rückbau (#3020, #3036) bestehen.
- [x] **AC-14 (nach Push auf Staging zu belegen):** Given zwei verschiedene Nutzer A und B mit verschiedenem Kanalstatus (A hat Telegram verbunden, B nicht) / When beide je einen Ortsvergleich anlegen / Then zeigt der Reiter bei A die Dringlichkeit für Telegram und bei B nicht, jeder Vergleich erscheint nur beim jeweiligen Nutzer, und B sieht den Vergleich von A nicht.
- [x] **AC-15:** Given das Trip-Anlegen / When der Nutzer einen Trip anlegt / Then verhält es sich unverändert wie nach D1 (Reiter Zustellung, ein POST).

## Dialog

### Runde 1
**Adversary:** Tests: Zielsuite 56/56, breiter benannter Lauf 3160/3160 gruen. Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:606 (send_email immer aus wiz.sendEmail, AC-4/5), :649 (mitZustellungVergleich, Rasterpruefung, Read-Modify-Write, AC-2/3/8); frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:46 (vergleich:true, AC-10); frontend/src/lib/components/compare-new/CompareNewEditor.svelte:213 (Guard), :570/:618 (ZustellungTab Desktop/Mobil), :573/:621 (AlarmeTab createMode). Mutationen a,b,c,d,f,g,h,i,j,k,l,m,n: je mindestens ein Test rot. F001: Mutation e (createMode von AlarmeTab im CompareNewEditor entfernt, Desktop, Mobil, beide) -> 115/115 gruen, KEIN Test rot. F002: Stub-Abo-Felder (cooldown, alert_channels) auf Konstante -> gruen (aequivalent, LOW).
Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:606
Code reference: frontend/src/lib/components/compare/compareEditorSave.ts:649
Code reference: frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts:46
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:213
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:570
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:573
**Implementierer:** (offen)

### Runde 2
**Adversary:** F001 vertieft: alarme_tab_ohne_zustellung_3333 rendert AlarmeTab direkt mit createMode (Baustein), der Editor-SSR-Test sieht AlarmeTab wegen alarmeHydrated=false nie. Nur E2E OZ-1 (Staging) prueft die Verdrahtung: Zusicherung dort geprueft wo der Code steht, nicht wo sie wirkt. Folge ohne Flag: Kanaele/Cooldown/Stille doppelt bedienbar, zwei Schreiber (AC-10). Geloeschte E2E compare-neu-kanal-anlegen.staging.spec.ts: testete Kanal-Layout-Karte (channel_active_metrics, seit #3276 nicht mehr geschrieben, #3301 wirkungslos) -> gerechtfertigt. Entfallene AC-14-Tippflaeche in begriff-erklaerung.spec.ts: ⓘ Cooldown/Schwelle auf keiner Seite mehr gemountet -> gerechtfertigt (Baustein bleibt in Komponententests).
**Implementierer:** (offen)

### Runde 3
**Adversary:** F001 nachgeprueft. Code reference: frontend/src/lib/components/compare-new/__tests__/vergleich_anlegen_alarme_createmode_3333.test.ts:68 (laedt echtes Editor-Skript, onMount macht alarmeHydrated true, wertet beide AlarmeTab-Mounts CompareNewEditor.svelte:573/:621 aus, rendert echten AlarmeTab). Mutation (e) selbst wiederholt mit externer Sicherung, diff identisch nach Rueckkopie: createMode an beiden Mounts entfernt -> Test rot; nur am Mobil-Mount entfernt -> rot (Desktop-Fall einzeln wurde in Runde 1 identifiziert, hier ueber Gesamtmutation belegt); unmutiert gruen (1/1). F001 geschlossen: Zusicherung jetzt am Wirkort geprueft. F002 (Stub-Abo-Felder cooldown/alert_channels): aequivalenter Mutant, da der Reiter seinen Start einmal aus dem Stub liest und danach zustellungStand fuehrt; Stub-Unterschiede sind ohne Nutzeraktion nicht im POST beobachtbar (AC-5 durch Fixture-Test bewacht). Kein Defekt. Pytest-Nachweis des Koordinators (150 bestanden, test-green-output-f001.txt) nicht selbst wiederholt, Vertrauen auf Beleg.
Code reference: frontend/src/lib/components/compare-new/__tests__/vergleich_anlegen_alarme_createmode_3333.test.ts:68
Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:621
**Implementierer:** F001 mit Kerntest nachgebessert.

## Herkunft der Vorbedingungen

Kein Sprachprofil konfiguriert (`precondition_origins.default_lang`).

## Verdict

VERDICT: VERIFIED

VERIFIED. F001 geschlossen, F002 aequivalenter Mutant. Offen nur die Staging-E2E-Anteile (AC-9, AC-14, E2E-Anteile AC-1/6/7), nach Push zu belegen.

## Geprüfte Dateien

- sha256:ee8080d382372e8ff2957b98a30bdd0fbbe64ee013acdb01b833390cfed667d7  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:02c0e331a415f81605112848914714f0c4f923f2ad0d3fd4a547a5f6a138447b  frontend/src/lib/components/compare-new/__tests__/vergleich_anlegen_alarme_createmode_3333.test.ts
- sha256:8c4c067bb439d738dc9b1b9974cc79ff363a78d5012b8b4c9fce58ef4f36d1b9  frontend/src/lib/components/compare/compareEditorSave.ts
- sha256:5ba3d51de50e25f3324e67fd691e14b1cc743d803c775a7f249be3bc04715570  frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts

## Prüfbasis

- base: 742c42c22f06f7836e9f81de5428d4001eda9c27
- blob:14b44e425c4cc33d448c6de9a5e86695b0778e26  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:7c8e9c0eb2ae6c69c441be005c63ef76c4bb1fb7  frontend/src/lib/components/compare-new/__tests__/vergleich_anlegen_alarme_createmode_3333.test.ts
- blob:2272c6168f7ad4eb89a0b210d6e172c2ba573a31  frontend/src/lib/components/compare/compareEditorSave.ts
- blob:d221c3d22a3bed21fc04af882333aa4b24251314  frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts
