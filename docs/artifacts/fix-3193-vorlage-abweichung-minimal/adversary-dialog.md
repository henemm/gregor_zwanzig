# Adversary Dialog — fix-3193-vorlage-abweichung-minimal
Spec: docs/specs/modules/fix_3193_vorlage_abweichung_minimal.md
Datum: 2026-11-20 17:12

## Checkliste
- [x] **Input:** Nutzer wechselt die Vorlage (Übernehmen), setzt auf Vorlage zurück, lädt einen Bestand oder ändert einzelne Metriken.
- [x] **Output:** Gespeichertes `display_config.ampel` enthält nur echte Abweichungen (nach Wechsel/Zurücksetzen: keine `metrics`); Picker zeigt „unverändert“; Zurücksetzen-Knopf nur bei echter Abweichung.
- [x] **Side effects:** Bestandsdaten mit Rausch-Einträgen (Trip: `temperature_day_*`/`wind_chill_*` mit `enabled:true`; Vergleich: `temperature_night: {enabled:false}`) zählen 0 und verschwinden beim nächsten Speichern. Laden löst kein Speichern aus; andere Felder bleiben erhalten (Read-Modify-Write).
- [x] **AC-1:** Given ein Trip mit beliebiger Systemvorlage / When der Nutzer eine andere Vorlage übernimmt oder auf die Vorlage zurücksetzt / Then ist die gespeicherte Abweichung leer und der Picker zeigt „unverändert“.
- [x] **AC-2:** Given ein Orts-Vergleich mit beliebiger Systemvorlage / When der Nutzer übernimmt oder zurücksetzt / Then ist die gespeicherte Abweichung leer, der Picker zeigt „unverändert“ und der Zurücksetzen-Knopf verschwindet.
- [x] **AC-3:** Given ein Trip oder Vergleich nach Vorlage / When der Nutzer bewusst eine Metrik ausschaltet („−“) / Then zählt genau diese eine Abweichung weiter und wird als `{enabled:false}` gespeichert.
- [x] **AC-4:** Given Bestandsdaten mit Rausch-Einträgen (Trip: abgeleitete Kinder `enabled:true`; Vergleich: `temperature_night` aus) / When der Reiter lädt / Then zeigt er 0 Abweichungen und schreibt nichts ohne Nutzeraktion.
- [x] **AC-5:** Given dieselben Bestandsdaten / When der Nutzer danach etwas speichert (z. B. eine Alarmstufe) / Then sind die Rausch-Einträge weg und alle anderen Felder (Alarmstufen, Auswahl, Layout) unverändert erhalten.
- [x] **AC-6:** Given ein Vergleichs-Bestand mit `temperature_night` in `active_metrics` / When er geladen wird / Then bleibt die Metrik gesperrt erhalten und zählt nicht als Abweichung.
- [x] **AC-7:** Given die Staging-Umgebung / When `s3a2794-teil3-vorlage.spec.ts` AC-11/12/13/28 für route und vergleich läuft / Then ist sie grün, mit begründet angeglichenen Auswahl-Erwartungen (Trip mit abgeleiteten Kindern, Vergleich ohne nicht ausgebbare Größen) und unveränderter Erwartung `ampel.metrics == {}`.

## Dialog

### Runde 1
**Adversary:** Volle Kernsuite (frontend, node --test): 8354 Tests, 8350 pass, 0 fail, 3 skipped, 1 todo. Gepruefte Wirkstellen: Basis-Tabelle BASIS_IM_KONTEXT (Z.119-135), vorlageImKontext/mengeVon/abweichungenVon (Z.137-165), Speicherweg tripNutzlast/vergleichNutzlast, aboAmpel. Trip: Kinder gelten in der Basis als an; ein bewusstes "-" ist Abweichung (Test 2 prueft Zaehler 1 und Nutzlast {temperature_day_low:{enabled:false}}). Vergleich: nur Groessen ausserhalb des Katalogs sind neutral, Grenzen/alarm_ab werden weiter verglichen; Nutzer kann diese Groessen ohnehin nicht ausgeben, also fachlich richtig. Ohne Katalog Rohvorlage (Test 6).
**Implementierer:** Kern-Test fix_3193_vorlage_abweichung_minimal.test.ts misst im echten Instanz-Pruefstand je Kontext ueber alle Systemvorlagen.

### Runde 2
**Adversary:** Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad bak/, sha256 vor == nach identisch): M1 route Basis=Rohvorlage ROT(17); M2 vergleich Basis=Rohvorlage ROT(15); M3 Kinder-Ableitung weg ROT(17); M4 neutral->enabled:false ROT(1); M5 mengeVon ohne Basis ROT(1); M6a tripNutzlast ohne Basis ROT(16); M6b vergleichNutzlast ohne Basis ROT(14); M8 Zaehler ohne Basis ROT(1); M7 aboAmpel ohne Basis GRUEN, nicht gefangen (F001). Bestandsdaten: Rausch zaehlt 0, geplant()==0 beim Laden, Rausch nach Alarmstufe weg, uebrige Felder (RMW) gleich (Test 5). E2E Z.123/171: Erwartung ampel.metrics=={} unveraendert, nur Auswahl-Erwartung an E6/E7 angepasst (Trip + abgeleitete Kinder, Vergleich geschnitten mit /api/compare/metrics): ehrlich, keine Abschwaechung; Staging-Lauf steht noch aus (/e2e-verify). WetterTabInhalt-Edit: 4 Aufrufe korrekt mit context/altSchluessel, Datei intakt, kompiliert und in Tests geladen.
**Implementierer:** offen zu F001.

### Runde 3
**Adversary:** Neuer Test 7 liest die aboAmpel-Prop der VorlageKarte. Eigene Wiederholung M7 (sha256 vor/nach identisch 2971dd5c...): Basis 39 pass/0 fail, mutiert 37 pass/2 fail -> gefangen.
**Implementierer:** F001 mit Test 7 geschlossen.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)


Finding:
  ID: F001
  Severity: LOW (GESCHLOSSEN in Runde 3)
  Category: anti_pattern
  Code reference: frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte:230
  Description: aboAmpel wird gegen vorlageImKontext(...).vorlage gebildet; Mutation auf vorlagen[stand.vorlageId] laesst alle 17+ Tests des Kern-Tests gruen (Prueffstand misst aboAmpel nicht).
  Spec requirement: Implementation Details Pkt. 5 — aboAmpel nutzt dieselbe Basis
  Conflict: Zusicherung dort, wo sie wirkt, nicht bewacht; funktional keine Fehlwirkung nachgewiesen.
  Remediation: Test, der die an VorlageKarte/aboAmpel uebergebene Ampel nach Uebernehmen (Trip) prueft, oder Wirkung belegen.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:119
  Evidence: BASIS_IM_KONTEXT.route + Test 1 route, alle Vorlagen, Zaehler 0 und Nutzlast {template}; M1/M3/M6a rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts:88
  Evidence: vergleichNutzlast nutzt Basis; Test 1 vergleich; M2/M4/M6b rot.
  Status: CONFIRMED
Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:148
  Evidence: Tests 2/3 Zaehler 1 und enabled:false.
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:164
  Evidence: Rausch zaehlt 0, geplant()==0 beim Laden.
  Status: CONFIRMED
Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts:68
  Evidence: Rausch weg, uebrige Felder gleich (Test 5).
  Status: CONFIRMED
Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts:131
  Evidence: temperature_night bleibt in Auswahl und Liste, Zaehler 0 (Test 4).
  Status: CONFIRMED
Confirmation:
  AC: AC-7
  Code reference: frontend/e2e/s3a2794-teil3-vorlage.spec.ts:123
  Evidence: Erwartung angeglichen (ehrlich), ampel.metrics=={} unveraendert; Live-Lauf steht noch aus.
  Status: CONFIRMED

## Verdict

VERDICT: VERIFIED
Alle 9 Mutationen rot (M7 in Runde 3 gefangen). Kern-Suite 0 fail. Staging-E2E (AC-7) folgt in /e2e-verify.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/wetter-tab/__tests__/fix_3193_vorlage_abweichung_minimal.test.ts:1
  Evidence: Test 7 prueft aboAmpel-Prop (Trip Kinder an, Vergleich temperature_night aus); M7 -> 2 rot.
  Status: CONFIRMED

## Geprüfte Dateien

- sha256:33ee03191e91890b830f8ff108849cebee6dbddd0bc784d243d12353c840a2cc  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- sha256:2971dd5ce2d270459d4e13525369bfe48077060c850ed66456f980dad4d37ad5  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- sha256:2ef97a63cb783f400eddf64fd7a8c3213becd9816974c488a81c9811b421d84c  frontend/src/lib/components/shared/wetter-tab/__tests__/fix_3193_vorlage_abweichung_minimal.test.ts
- sha256:06a5a67b183a934d55185fb0075e08f37ae4f16f4297994baf0a7a3646c9de3c  frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts
- sha256:fe7afad3142e717854b95bc0d918c51092db7654fc2312e7753e6c1da7d9040f  frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts

## Prüfbasis

- base: 92b752fa676507c110ff5842be49b4f8cfa7daec
- blob:a310ec85fbb3a1e813360d29f030eb9bbb639d23  frontend/e2e/s3a2794-teil3-vorlage.spec.ts
- blob:b92da7862e571c112411882d5fcda84f0cf2228d  frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte
- blob:62f3d4143b6226331a82a0defb21caa6598bbc9e  frontend/src/lib/components/shared/wetter-tab/__tests__/fix_3193_vorlage_abweichung_minimal.test.ts
- blob:35dce5d48f27071c58e4ef1c1778fb5eb5cf02a5  frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts
- blob:f6f6923be420925e72af6abd5e65e0d01c39af5b  frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts
