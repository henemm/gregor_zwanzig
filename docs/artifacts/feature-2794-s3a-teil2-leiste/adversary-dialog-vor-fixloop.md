# Adversary Dialog — feature-2794-s3a-teil2-leiste
Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md
Datum: 2026-11-09 10:01

## Checkliste
- [x] **Input:** Aufruf von Hub oder Anlege-Kette, auch über alte Adressen (`?tab=…`, `#versand`); Bedienung der Reiter Wetter und Zustellung.
- [x] **Output:** vier Reiter nach Soll; Zustellung zeigt alle 16 Inventar-Elemente; Wetter zeigt die bisherige Metrik-Oberfläche (ohne Zustellungs-Blöcke) plus nur lesende Wertebereiche; Anlege-Ketten mit den neuen Schritten.
- [x] **Side effects:** keine. Gespeicherte Daten und Speicherwege bleiben gleich; Adresszeile wird bei Alt-Kennungen bereinigt.
- [x] **AC-1:** Given ein Trip / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Etappen · Wetter · Zustellung in der Leiste (kein Reiter Wertebereiche, Alarme oder Wetter-Metriken), auf Deutsch und auf Englisch
- [x] **AC-2:** Given ein Orts-Briefing / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Orte · Wetter · Zustellung in der Leiste, der Badge am Reiter Orte zeigt die Zahl der Orte
- [x] **AC-3:** Given der Hub eines Trips oder Orts-Briefings am Desktop / When der Nutzer die Leiste ansieht / Then hat sie genau eine Grundlinie, der aktive Reiter ist 600 stark mit 2px-Unterstrich in der Akzentfarbe, und Badges sind kleine neutrale Mono-Marken (keine orangen Kreise, keine Segmented-Box) — Runde 3: Kern-Wächter belegt, Staging-Lauf in /e2e-verify ausstehend
- [x] **AC-36:** Given der Hub eines Trips und eines Orts-Briefings am Desktop (Breite ≥ 1024 px) / When der Nutzer den Seitenkopf ansieht / Then hat die Seitenüberschrift (h1) eine berechnete Schriftgröße zwischen 30 und 38 px (Soll Atomic Design; Regressionswächter: am Desktop heute bereits 38 px gemessen), in beiden Kontexten aus demselben Kopf-Baustein; mobil bleibt die Überschrift im Soll der mobilen Kopfzeile — Runde 3: Kern-Wächter belegt, Staging-Lauf in /e2e-verify ausstehend
- [x] **AC-4:** Given ein Mobilgerät (schmale Breite) / When der Nutzer einen Hub öffnet / Then zeigt die Leiste weiter die Pill-Form mit denselben vier Reitern und alle vier sind erreichbar — Runde 3: Kern-Wächter belegt, Staging-Lauf in /e2e-verify ausstehend
- [x] **AC-5:** Given Lesezeichen mit den alten Adressen / When `?tab=wetter-metriken`, `?tab=wertebereiche` oder `?tab=layout` geöffnet wird / Then landet der Nutzer im Reiter Wetter, und bei `?tab=alarme` oder `?tab=versand` (auch `#versand`) im Reiter Zustellung, jeweils für Trip und Orts-Briefing, und die Adresszeile zeigt danach die neue Kennung
- [x] **AC-6:** Given der Nutzer legt einen Trip über `/trips/new` bzw. ein Orts-Briefing über `/compare/new` an / When er durch die Schritte geht / Then lauten die Schritte beim Trip Route · Etappen · Wegpunkte · Wetter · Zustellung und bei Orten Vergleich · Orte · Wetter · Zustellung, kein Schritt führt auf einen entfallenen Reiter, und der angelegte Trip bzw. Vergleich ist danach vollständig gespeichert
- [x] **AC-7:** Given ein Trip mit gesetzten Alarm- und Versand-Einstellungen vor dem Umbau / When der Nutzer den Reiter Zustellung öffnet / Then ist jedes der 16 Bedienelemente aus dem Inventar (Alarm-Kanäle und Dringlichkeit je Kanal, Kanal je Wettergröße, Telegram-Kurzstil, Cooldown, Stille Stunden, Briefing-Kanäle, Morgen/Abend mit Uhrzeit, Mehrtages-Trend, Laufzeit, Aktivieren, Mail-Inhalt, Layout je Kanal, 3-Tages-Ausblick, Nacht-Block, Stundenverlauf, Beispiel-Warnung) vorhanden, zeigt seinen gespeicherten Wert, und das Gleiche gilt im Orts-Briefing für die dort vorhandenen Elemente — Runde 3: Kern-Wächter belegt, Staging-Lauf in /e2e-verify ausstehend
- [x] **AC-8:** Given der Reiter Zustellung / When der Nutzer einen Wert ändert (z. B. Cooldown, Stille Stunden, Briefing-Uhrzeit, Alarm-Kanal) und speichert / Then bleibt der Wert nach Neuladen erhalten, wirkt über denselben Speicherweg wie vor dem Umbau, und alle anderen gespeicherten Felder des Abos (Ampel, Etappen, Orte) bleiben unverändert — Runde 3: Kern-Wächter belegt, Staging-Lauf in /e2e-verify ausstehend
- [x] **AC-2.T1:** Given die Speicher-Owner `'wetter-metriken'`, `'wetter-metriken-report-config'`, `'versand'`, `'alarme'` und `'wertebereiche'` / When der Nutzer im Reiter Zustellung oder Wetter einen Wert ändert und speichert / Then erzeugt das Speichern denselben Request (gleiche Adresse, gleicher Besitzer, gleiche Felder) wie vor dem Umbau, und die fünf Owner-Strings kommen unverändert im Code vor
- [x] **AC-2.T2:** Given Hub und Anlege-Kette von Trip und Orts-Briefing / When der Nutzer durch die Reiter bzw. Schritte wechselt / Then ist zu jedem Zeitpunkt höchstens eine `WeatherMetricsTab`-Instanz gemountet, sodass keine zwei Instanzen einander mit veraltetem Stand überschreiben
- [x] **AC-2.T3:** Given ungespeicherte Änderungen in Wetter oder Zustellung / When der Nutzer den Reiter wechselt / Then werden die Änderungen gesichert (Trip: Flush-Liste in `TripTabs.svelte`, Vergleich: `SELBST_SPEICHERNDE_VERGLEICH_REITER`), und die Lazy-Hydration des Vergleichs greift unter `wetter` und `zustellung`, sodass nach dem Wechsel und Neuladen nichts verloren ist
- [x] **AC-2.T4:** Given das Anlegen eines Trips ohne eigenen Wertebereiche-Schritt / When der Nutzer „Speichern“ oder „Mit Standardwerten speichern“ wählt / Then enthält das neue Abo weiterhin die Wertebereiche-Vorbelegung (`corridors`), und „Mit Standardwerten speichern“ wartet weiter, bis `wertebereicheVorbelegt` gesetzt ist

## Dialog

### Runde 1
**Adversary:**
Testlauf: Kern-Gesamtlauf `npm test -- "src/**/*.test.ts"` 8306 Tests, 8301 pass, 0 fail, 5 skip (Alt-Skips); neue Dateien `s3a2794*.test.ts` 140/140 (Ausgabe: `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`). `playwright test --list` fehlerfrei (17 Tests in 2 Dateien). Leitfrage: Ist jede Zusicherung dort geprüft, wo sie WIRKT? 23 Mutationen per String-Ersetzung (externe Sicherung im Scratchpad, danach `cmp` identisch, Diff-Statistik der Arbeitskopie unverändert 212 Dateien).

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:43
  Evidence: `REITER_DEFINITION` = uebersicht, punkte[kind], schwanz [wetter, zustellung]; Labels über Katalog `aktionen.reiter.wetter/zustellung` DE/EN (de/aktionen.json:28-29, en/aktionen.json:28-29). `s3a2794_reiter_definition.test.ts` grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:43
  Evidence: gleiche Definition mit punkte.vergleich = orte; Badge-Quelle unverändert (Orte-Zähler), der Trip-Badge Wertebereiche entfällt in `frontend/src/lib/components/trip-detail/TripTabs.svelte:22-60`.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:153
  Evidence: `LEGACY` (Zeile 121) mappt wetter-metriken/wertebereiche/layout -> wetter, alarme/versand/briefings -> zustellung; `resolveTab(kind, raw, hash)` lässt `#versand` gewinnen; beide Hubs reichen `window.location.hash` durch (TripTabs.svelte:111-124, CompareTabs.svelte `ankerDerAdresse`). Mutationen M1, M2, M19 rot (je 2 bis 5 Tests, inklusive echter Hub-Render-Tests).
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35
  Evidence: Trip-Kette route/etappen/wegpunkte/wetter/zustellung (`TAIL`); Vergleich `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:92-93` vergleich/orte/wetter/zustellung; `canFinish` letzter Schritt zustellung (`frontend/src/lib/components/shared/anlegeLockEngine.ts:49`, Mutation M17 rot); Infobox-Schlüssel `frontend/src/lib/components/shared/infoboxKeys.ts:24`.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T1
  Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:37
  Evidence: ZustellungTab hat keine eigene Speicherlogik; Owner-Strings unverändert (Mutation M5 rot am Wächter `s3a2794_speicher_owner_waechter.test.ts`). Request-Gleichheit selbst nur per Staging-E2E nachweisbar (siehe F004).
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T3
  Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:256
  Evidence: `SELBST_SPEICHERNDE_VERGLEICH_REITER = ['wetter','zustellung']`, Trip-Flush `frontend/src/lib/components/trip-detail/TripTabs.svelte:172`; Lazy-Hydration in CompareTabs für wetter/zustellung; Mutationen M3, M4, M9, M13 rot. Alarm-Hydration kann nicht scheitern (`.catch(() => [])`), Zustellung blockiert also nie dauerhaft.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T4
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:910
  Evidence: CorridorEditor dauerhaft gemountet im Schritt wetter (`style:display`), `corridors` im Payload (Zeile 487), Wartebedingung `wertebereicheVorbelegt` (Zeile 206). M7 rot (neuer Test); M6 (corridors aus Payload) nur vom Alt-Test `AC-20 Race` rot, nicht von den neuen (F005).
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T2 (Trip-Hub, Trip-Anlegen)
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:896
  Evidence: Trip-Hub mountet per if-Kette (TripTabs.svelte:217 `bereich="wetter"`, :224 ZustellungTab); Anlegen: EINE dauerhafte Instanz je Viewport mit `bereich` nach Schritt. Verborgener Versand-Abschnitt (Abweichung 7): `VersandTab` ist keine WMT-Instanz, speichert im createMode nicht (kein PUT), hält Zustand über `bind:reportConfig` und liest ihn beim Neu-Mounten über `ladeReportZustand` zurück (VersandTab.svelte:140-200); beim Wechsel Zustellung -> Wetter -> Zustellung geht nichts verloren, keine doppelte Speicherung. M11 rot.
  Status: CONFIRMED

Finding:
  ID: F001
  Severity: HIGH
  Category: edge_case
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:839
  Description: Der Vergleichs-Hub reicht den Alarm-Baustein als Snippet-Attribut `alarmeBereich` (Snippet hubAlarme ab Zeile 862) und die Aktivierungs-Karte als Attribut `activation` (Zeile 838) an ZustellungTab. Mutation M22 (Zeile 839 gelöscht): Im Reiter Zustellung des Orts-Briefings verschwinden ALLE Alarme. Ergebnis: Kern-Gesamtlauf 8306 Tests, 0 rot. M21 (Aktivierungs-Karte entfernt): nur ein unbeteiligter Alt-Test rot („Versand-Abschnitt hat keinen Sammel-Wrapper"), kein neuer Test.
  Spec requirement: AC-7 — jedes Bedienelement des Inventars im Reiter Zustellung vorhanden, auch im Orts-Briefing; DoD „Kein Bedienelement aus dem 16-Punkte-Inventar verschwunden".
  Conflict: Der Wächter `s3a2794_zustellung_enthaelt_alarmetab_vollstaendig` prüft nur ZustellungTab (Snippet-Zweig), nicht dass der Hub das Snippet übergibt; die E2E-Spec `s3a2794-hub-reiter-wetter-zustellung.spec.ts:14` schließt AC-7 ausdrücklich aus. Die Zusicherung ist dort geprüft, wo der Code steht, nicht dort, wo sie wirkt.
  Remediation: Kern-Test (AST/SSR) auf CompareTabs: die ZustellungTab-Einbettung trägt `alarmeBereich` und `activation`, das Snippet hubAlarme enthält `AlarmeTab context="vergleich"`; AC-7-Inventarlauf zwingend in /e2e-verify vor Prod-Deploy.

Finding:
  ID: F002
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:81
  Description: `TAB_LITERAL` ist ein nicht globaler Regex und liest nur das ERSTE `activeTab === '…'` einer Weichenbedingung. Mutation M8 (if-Bedingung `activeTab === 'wetter' || activeTab === 'zustellung'` am Wetter-Panel in `frontend/src/lib/components/compare/CompareTabs.svelte:787`, also zwei WMT-Instanzen im Reiter Zustellung): alle 140 neuen Tests grün, `paarweise_exklusiv` meldet keine Überschneidung. Gefangen nur zufällig von einem Alt-Test (Sammel-Wrapper).
  Spec requirement: AC-2.T2 — höchstens eine WeatherMetricsTab-Instanz zu jedem Zeitpunkt; Mutation „zweite WMT-Instanz" muss einen Test rot machen.
  Conflict: Der Hauptwächter ist für ODER-Bedingungen blind; genau diese Form ist die naheliegende Fehlkonstruktion.
  Remediation: Alle `===`-Literale einer Bedingung sammeln (matchAll) und `schliessenSichAus` auf Mengenschnitt prüfen.

Finding:
  ID: F003
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80
  Description: Die AC-3-Änderungen (Wurzel ohne `data-slot="segmented"`, aktiv 600, Badge 10 px) haben keinen Kern-Test. Mutationen M14 (data-slot wieder ergänzt), M14b (font-weight 500), M14c (Badge var(--g-text-xs)): `src/lib/components/mobile/**` 15/15 grün; nur die Staging-E2E-Spec (`s3a2794-hub-reiter-wetter-zustellung.spec.ts:132-170`) misst es.
  Spec requirement: AC-3 — genau eine Grundlinie, aktiv 600 + 2px Akzent, Badge Mono neutral, keine Segmented-Box.
  Conflict: Ein Kern-Regressionsschutz fehlt; die Leiste kann bis /e2e-verify unbemerkt zurückkippen.
  Remediation: Kleiner Kern-Test auf `MTabBar.svelte` (Wurzelattribut, Stilregeln aktiv/Badge).

Finding:
  ID: F004
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:224
  Description: Das Attribut `versandSprung` an ZustellungTab entfernt (M23): weder `s3a2794*` noch trip-detail-Suite (754 Tests) rot. Folge: `?tab=versand`/`#versand` landet im Reiter Zustellung, scrollt aber nicht zum Versand-Abschnitt. Zudem sind AC-7/AC-8/AC-2.T1/T3/T4 laut Kopf der E2E-Spec (Zeile 14) bewusst NICHT enthalten, also derzeit ohne automatisierten Nachweis der Wirkung (Request-Gleichheit, Erhalt nach Neuladen, Inventar).
  Spec requirement: AC-5 / Spec §1 — Anker `#versand` gewinnt und springt in den Abschnitt; AC-7, AC-8.
  Conflict: Wirkung nur durch noch nicht vorhandene Staging-Läufe prüfbar.
  Remediation: Wertprop-Wächter für `versandSprung` an der ZustellungTab-Einbettung im Trip-Hub; Speicherweg-/Inventar-Spec vor Prod-Deploy nachliefern.

Finding:
  ID: F005
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:487
  Description: M6 (`corridors` aus dem Anlege-Payload) wird von keinem neuen Test gefangen, nur vom Alt-Test `AC-20 Race: Standardwerte-Knopf (Trip) wartet auf die Wertebereiche-Vorbelegung` (Suite trip-new, 2 rot).
  Spec requirement: AC-2.T4 — neues Abo enthält weiterhin `corridors`.
  Conflict: Mutation aus dem Test Plan ist rot, aber nicht durch die neue Absicherung.
  Remediation: Im neuen T4-Wächter `corridors` im Payload ausdrücklich prüfen.

Finding:
  ID: F006
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:918
  Description: Der Weiter-Knopf Wetter -> Zustellung (Abweichung 5) trägt „Alarme einrichten →" / „Set up alerts →" (`trip.anlegen.alarme_einrichten`), führt aber auf den Schritt Zustellung (Versand plus Alarme).
  Spec requirement: AC-6 — Schritte heißen Wetter · Zustellung.
  Conflict: Beschriftung benennt nur einen Teil des Ziels; kein Funktionsfehler.
  Remediation: Katalogtext „Zustellung festlegen →" / „Set up delivery →".

Einordnung der Abweichungen (green-uebergabe.md): (1) `resolveTab` mit Hash korrekt, beide Hubs rufen konsistent (M2 rot). (2) ZustellungTab ohne `context`-Weiche: Snippet-Weg funktional, im Hub aber ungeprüft (F001). (3) MTabBar nur Wurzel-`data-slot`: akzeptabel, siehe F003. (4) E2E MS-2 mit 2 PUTs: nur Staging. (5) siehe F006. (6) Heredoc-Edits: Endstand konsistent, Gesamtlauf grün. (7) verborgener Versand-Abschnitt: keine Verletzung von AC-2.T2 (keine WMT-Instanz), keine doppelte Speicherung (createMode ohne PUT), Neu-Mounten stellt den Zustand aus `reportConfig` wieder her.

**Implementierer:**
(offen; Findings F001 bis F006 gehen an den Orchestrator)

### Runde 2
**Adversary:**
Nachprüfung unter dem Blickwinkel „Wirkstelle": (a) Hub-Mount der Vergleichs-Zustellung (`frontend/src/lib/components/compare/CompareTabs.svelte:833-839`) mountet nach `wetterMetrikenLayoutHydrationBereit && versandHydrated && alarmeHydrated`; alle drei Flags werden unter `zustellung` gesetzt (M9, M13 rot), Hydration ist fehlertolerant, kein Dauer-Leerlauf. (b) Zwei WMT-Instanzen im Hub sind strukturell ausgeschlossen (je Reiter ein Panel), belastbar geschützt ist aber nur der Trip-Hub (F002). (c) Bereich-Filter `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:70`: disjunkt, Vereinigung = alles (M16 rot); Stundenverlauf bleibt compare-exklusiv, `report_config`/`nachtblock` nur Trip. (d) Sprungziele `frontend/src/routes/compare/[id]/+page.svelte:370` und `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99` zeigen auf `zustellung#versand` (M18 rot). (e) `frontend/playwright.2794-s3a2.staging.config.ts:11` lädt nur die neue Spec; AC-7/AC-8/T1/T3/T4 und AC-36 laufen dort nicht und müssen in /e2e-verify nachgeliefert werden. Kein produktiver Defekt gefunden; die Findings betreffen Wirkungsprüfungen.
**Implementierer:**
(offen)

### Runde 3
**Adversary:**
Nachprüfung nach Fix-Loop 1. Testlauf: Kern-Gesamtlauf `npm test -- "src/**/*.test.ts"` 8327 Tests, 8322 pass, 0 fail, 5 skip (Alt-Skips), Ausgabe `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`; neue Wächter (`s3a2794*` shared + mobile) 151/151. `playwright test --config frontend/playwright.2794-s3a2.staging.config.ts --list` fehlerfrei (21 Tests in 3 Dateien inkl. Setup). Die neuen Tests sind kein Mock-Theater: AST der echten Hub-Komponenten, Auswertung des echten Instanz-Skripts mit `?tab=versand` (`s3a2794_hub_zustellung_verdrahtung.test.ts`), echter SSR-Render von `MTabBar` plus Kaskadenrechnung der scoped Regeln (`s3a2794_mtabbar_leiste_soll.test.ts`); keine reinen Dateiinhalt-Checks ohne Verhaltens- oder Struktur-Aussage.

Wiederholte Mutationen (String-Ersetzung, Sicherung im Scratchpad, danach `cmp` identisch):
- M22 (`alarmeBereich={hubAlarme}` entfernt): ROT durch neuen F001-Wächter. M21 (`activation=…` entfernt): ROT. Geschlossen.
- M23 Trip und Vergleich (`versandSprung` entfernt): je 4 rot; Variante Festwert `versandSprung={0}` rot für `versand` und `briefings` (Wertmessung, nicht nur Vorhandensein). Geschlossen.
- M8 (ODER-Weiche `activeTab === 'wetter' || activeTab === 'zustellung'` am Wetter-Panel) und M8b (`!== 'uebersicht' && …`): ROT durch `paarweise_exklusiv` (matchAll). Geschlossen.
- M6 (`corridors` aus Anlege-Payload): ROT durch die neuen T4-Tests (Speichern und Standardwerte). Geschlossen.
- M14 (data-slot wieder an der Wurzel), M14b (aktiv 500), M14c (Badge `var(--g-text-xs)`): je ROT im neuen Kern-Test; zusätzlich M14d (Unterstrich 1px), M14e (Unterstrich nicht Akzent), M14f (Badge-Farbe), M14h (Rahmen an der Wurzel): ROT. Geschlossen, bis auf M14g (siehe F010).
- F006: Katalogtext DE zurückgedreht (`Alarme einrichten →`): ROT (Goldens + F9-Katalog-Anker). Der Knopf trägt den neuen Schlüssel in Trip und Vergleich, Desktop und Mobil.
- Eigene neue Mutationen gegen die Fix-Loop-Wächter, ROT: N3 (Vergleichs-Weiter-Knopf zielt auf `wetter`), N4 (`LEGACY.alarme -> wetter`), N5 (`nachtblock` aus `ZUSTELLUNGS_SECTIONS`), N6 (`zustellung` aus Trip-Flush-Liste), N7 (`zustellung` aus `SELBST_SPEICHERNDE_VERGLEICH_REITER`), N8 (`VERSAND_ZIEL` auf `wetter`), N10 (Alarm-Hydration an `wetter` statt `zustellung`).
- NICHT gefangen (Gesamtlauf 8322/8322 grün): N2, N11, N12, M14g (F007 bis F010).

Bewertung der neuen Staging-Spec `frontend/e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts` (statisch, noch kein Staging-Lauf): prüft AC-7 aus Nutzersicht (Trip und Vergleich je mit per API gesetzten Alarm-/Versand-Werten, jedes Inventar-Element des Kontexts per `data-testid` im Reiter Zustellung sichtbar, dazu Werte: Cooldown 90, Stille Stunden 22:00/06:00, Uhrzeiten 07:00/19:00, Telegram-Alarm an mit Dringlichkeit HIGH, Kurzstil, Mehrtages-Trend nur Trip) und AC-8 (Cooldown und Morgen-Uhrzeit ändern, nur `PUT` auf das Objekt, Neuladen, Etappen/Orte, `corridors`, Name und übrige Werte unverändert). Alle verwendeten Testids existieren im Quelltext; Inventar je Kontext deckt sich mit der Analyse (Trip 14 von 16, ohne Aktivieren und Stundenverlauf; Vergleich 13, ohne Mail-Inhalt, Nacht-Block, Mehrtages-Trend). Schwäche: Alarm-Kanal, Kurzstil und Dringlichkeit werden nur gelesen, nicht geändert und gespeichert (AC-8 nennt „Alarm-Kanal" und „Stille Stunden" als Beispiele); die Wertänderung deckt Owner `alarme` (Cooldown) und `versand` (Uhrzeit) ab. Vertretbar, Staging-Lauf bleibt Pflicht in /e2e-verify.

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:78
  Evidence: Wurzel `role="tablist"` ohne `data-slot="segmented"`; aktiv 600 (Zeile 136), Unterstrich 2px Akzent (Zeilen 120/134), Badge Mono 10 px neutral (Zeilen 146-151). Kern-Wächter `frontend/src/lib/components/mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts` fängt M14/b/c/d/e/f/h.
  Status: CONFIRMED

Confirmation:
  AC: AC-5, AC-2.T3
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:224
  Evidence: `{versandSprung}` an ZustellungTab, Vergleichs-Pendant `frontend/src/lib/components/compare/CompareTabs.svelte:844`; Wächter `frontend/src/lib/components/shared/__tests__/s3a2794_hub_zustellung_verdrahtung.test.ts` misst den ankommenden Wert (M23 rot, Wertvariante rot). Flush: `frontend/src/lib/components/trip-detail/TripTabs.svelte:172` (N6 rot).
  Status: CONFIRMED

Confirmation:
  AC: AC-7 (Orts-Briefing: Alarme, Aktivieren)
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:838
  Evidence: `activation={hubActivationCard}` und `alarmeBereich={hubAlarme}` (Zeile 839) werden vom neuen Verdrahtungs-Wächter an der Hub-Einbettung geprüft (M21, M22 rot). Der Inventar-Lauf selbst folgt per Staging-Spec.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T2
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:83
  Evidence: `TAB_LITERAL` global, `reiterVon` sammelt alle Literale; ODER-Weiche (M8) und Gegenbedingung (M8b) rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T4, AC-6
  Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35
  Evidence: `TAIL` wetter/zustellung; Anlege-Kette Vergleich `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:555` (Weiter-Knopf auf `zustellung`, N3 rot); `corridors` im Payload `frontend/src/lib/components/trip-new/TripNewEditor.svelte:487` (M6 rot); Sperre `frontend/src/lib/components/shared/anlegeLockEngine.ts:49`; Infobox-Schlüssel `frontend/src/lib/components/shared/infoboxKeys.ts:24` (siehe F009). Katalogschlüssel `trip.anlegen.zustellung_einrichten`: `frontend/src/lib/i18n/messages/de/trip.json:271`, `frontend/src/lib/i18n/messages/en/trip.json:271`, Goldens `frontend/src/lib/components/trip-detail/__tests__/f9KatalogAnker.ts:347`.
  Status: CONFIRMED

Confirmation:
  AC: AC-5 (Sprungziele), AC-2.T1
  Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99
  Evidence: `VERSAND_ZIEL = { tab: 'zustellung', anchor: 'versand' }`, N8 rot (6 Tests); Alt-Kennung `alarme` -> Zustellung `frontend/src/lib/components/shared/subscriptionTabs.ts:121` (N4 rot); Flush-Liste Vergleich `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:256` (N7 rot); Bereich-Filter `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86` (N5 rot).
  Status: CONFIRMED

Confirmation:
  AC: AC-7, AC-8 (Nachweis ausstehend)
  Code reference: frontend/playwright.2794-s3a2.staging.config.ts:28
  Evidence: `testMatch` lädt beide Specs (`--list` fehlerfrei, 21 Tests). Lauf gegen Staging folgt in /e2e-verify und ist Pflicht-Gate vor Prod.
  Status: CONFIRMED

Finding:
  ID: F007
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:913
  Description: Der Weiter-Knopf Wetter -> Zustellung des Trip-Anlegens ruft `makeEtappenContinueHandler('zustellung')`. Mutation N2 (Ziel `'wetter'`): Kern-Gesamtlauf 8327 Tests, 0 rot. Das Vergleichs-Pendant (`frontend/src/lib/components/compare-new/CompareNewEditor.svelte:555`) wird vom Test `F002 Ortsvergleich-Anlegen: jeder Weiter-Knopf schaltet auf den Reiter seiner testid` gefangen (N3 rot), im Trip gibt es keinen gleichwertigen Test.
  Spec requirement: AC-6 — kein Schritt führt auf einen falschen Reiter; Kette Route · Etappen · Wegpunkte · Wetter · Zustellung.
  Conflict: Der neue Knopf „Zustellung einrichten →" im Trip-Anlegen kann auf den Reiter Wetter zeigen, ohne dass ein Test rot wird (Wirkstelle ungeprüft).
  Remediation: Trip-Pendant des F002-Tests: Klick auf `trip-new-continue-zustellung` (und mobil) setzt `activeTab === 'zustellung'`.

Finding:
  ID: F008
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:37
  Description: ZustellungTab setzt fest `bereich="zustellung"` am Panel. Mutation N12 (`bereich="alles"`): Gesamtlauf 8322 grün. Folge im Hub: der Reiter Zustellung zeigt zusätzlich Metrik-Auswahl, Wertebereiche und weitere Wetter-Abschnitte, doppelt zum Reiter Wetter.
  Spec requirement: AC-1/AC-7 — Zustellung zeigt die Inventar-Elemente, Wetter die Metrik-Oberfläche ohne Zustellungs-Blöcke.
  Conflict: Die Aufteilung ist am Filter (`frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:70`) geprüft, nicht an dem Wert, den ZustellungTab tatsächlich ans Panel gibt; die Staging-Spec prüft nur Vorhandensein der Inventar-Elemente, nicht Abwesenheit der Wetter-Abschnitte.
  Remediation: Wächter an der Einbettung `WetterMetrikenVersandPanel` in ZustellungTab (Attribut `bereich` Literal `zustellung`), analog zur F001-Technik.

Finding:
  ID: F009
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24
  Description: Der Anlege-Schritt `zustellung` zeigt seine Infobox über `INFOBOX_KEYS.route.zustellung = 'info.versand.route'` (Vergleich Zeile 32). Mutation N11 (`'info.alarme.route'`): Gesamtlauf grün; der Schlüssel-Verwender-Test prüft nur, dass der Schlüssel existiert, nicht welcher.
  Spec requirement: AC-6 / Infobox der Anlege-Schritte.
  Conflict: falscher Infotext im Schritt Zustellung unbemerkt möglich.
  Remediation: Test auf die Zuordnung Schritt -> Schlüssel (route und vergleich).

Finding:
  ID: F010
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:119
  Description: `border: none` am Reiter hält die senkrechten Segmented-Trenner aus `frontend/src/app.css:519` (`:not(:last-child)` Rahmen rechts) fern. Mutation M14g (Zeile entfernt): Kern 14/14 grün; auch die Staging-Spec misst nur `border-bottom`.
  Spec requirement: AC-3 — keine Segmented-Optik an der Leiste.
  Conflict: Rückfall auf senkrechte Trenner wird weder im Kern noch im Staging-Lauf bemerkt.
  Remediation: Kern-Test: Kaskade `border-right` des Reiters (Desktop) ohne Wert; E2E: `borderRightWidth === '0px'`.

### Runde 4
**Adversary:**
Nachprüfung nach Fix-Loop 2 (nur Tests ergänzt, kein Produktivcode). Testlauf: Kern-Gesamtlauf `npm test -- "src/**/*.test.ts"` 8337 Tests, 8332 pass, 0 fail, 5 skip (Alt-Skips), Ausgabe `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Neue Tests sind kein Mock-Theater und keine reinen Dateiinhalt-Checks: `frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_ziel_und_bereich.test.ts` wertet den onclick-Ausdruck des Knopfs gegen das echte Instanz-Skript des Editors aus (gemessen: `activeTab` nach dem Klick) und bindet den Knopf über testid bzw. Katalogschlüssel der sichtbaren Beschriftung; der `bereich`-Wert kommt aus dem AST der echten Einbettung und wird durch den echten Filter `weatherMetricsTabSections` gejagt. `frontend/src/lib/components/shared/__tests__/s3a2794_infobox_zustellung.test.ts` rendert die echte `Infobox.svelte` per svelte/server und vergleicht den sichtbaren Text von `zustellung`/`wetter` mit dem des Bausteins (je Kontext) plus exakter Schlüssel. `frontend/src/lib/components/mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts` rechnet die Kaskade des gerenderten MTabBar (F010).

Wiederholte Mutationen (String-Ersetzung, Sicherung im Scratchpad `r4/`, danach `cmp` identisch):
- F007 Desktop (`TripNewEditor.svelte:913` Ziel `'wetter'`): ROT (`s3a2794_f007_trip_zustellung_einrichten_klick_fuehrt_auf_zustellung`). F007 Mobil (`TripNewEditor.svelte:1263`): ROT (derselbe Test). Geschlossen.
- F008 (`ZustellungTab.svelte:37` `bereich="alles"`): ROT, 3 Tests (F008-Test, genau-ein-WMT-Träger, enthält-section-versand). Geschlossen.
- F009 (`infoboxKeys.ts:24` `zustellung: 'info.alarme.route'`): ROT; Vergleich-Variante `'info.alarme.vergleich'` ROT; zusätzlich `wetter` (vergleich) auf Versand-Schlüssel ROT. Geschlossen.
- F010 (`MTabBar.svelte:119` `border: none` entfernt): ROT, 2 Tests (inaktiv/aktiv nicht letzter Reiter ohne senkrechten Strich). Geschlossen.
- Eigene neue Mutationen: N1 `LEGACY.alarme -> wetter` ROT (5); N2 `LEGACY.layout -> zustellung` ROT (4); N3 `tailUnlocked` gibt Zustellung ohne Wetter-Besuch frei: in den 2794-Tests grün, im Komponenten-Gesamtlauf ROT (20, u. a. `anlege_lock_engine`-Altsuite, `compare_anlege_freischaltung`) — bewacht, nur nicht in der benannten 2794-Teilmenge; N4 `tailDone` Zustellung an `metrikenVisited` gehängt: ROT (u. a. canActivate-Wirkstelle); N5 `LEGACY_ANKER` ohne `briefings`: ROT (6); N6 Prüfung `r.tab === VERSAND_REITER` entfernt: ROT (`bereinigteTabAdresse`, Schleifenfreiheit). Nebenprobe: Mutation `alarme: 'info.versand.route'` (Eintrag Alarme, nicht Teil dieser Änderung) bleibt grün — außerhalb des Umfangs, kein Finding.
- Keine Mutation bleibt unbemerkt.

Nur auf Staging prüfbar (Staging-Lauf in /e2e-verify Pflicht, kein Finding): AC-3 / AC-4 / AC-36 (Browserhälfte), AC-7 und AC-8 mit `frontend/e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts` und `frontend/e2e/s3a2794-hub-reiter-wetter-zustellung.spec.ts` über `frontend/playwright.2794-s3a2.staging.config.ts:28`.

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:913
  Evidence: Weiter-Knopf Wetter -> Zustellung ruft `makeEtappenContinueHandler('zustellung')` (Mobil Zeile 1263); `frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_ziel_und_bereich.test.ts` misst `activeTab` nach dem Klick, Mutation Desktop und Mobil rot. Lock-Kette `frontend/src/lib/components/shared/anlegeLockEngine.ts:36` (N3/N4 rot), `frontend/src/lib/components/trip-new/tripNewLogic.ts:35`.
  Status: CONFIRMED

Confirmation:
  AC: AC-1, AC-7
  Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:37
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:76
  Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:36
  Evidence: `bereich="zustellung"` am Panel, Filter `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:76`; Mutation `alles` rot (3 Tests). Hub-Modell `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99`, Speicher-Owner `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:256`.
  Status: CONFIRMED

Confirmation:
  AC: AC-5, AC-6 (Infobox)
  Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24
  Evidence: `zustellung -> info.versand.*`, `wetter -> info.wetter-metriken.*`; echter Render-Vergleich in `frontend/src/lib/components/shared/__tests__/s3a2794_infobox_zustellung.test.ts`, drei Mutationen rot. Umleitung `frontend/src/lib/components/shared/subscriptionTabs.ts:121` (N1/N2/N5/N6 rot).
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:119
  Evidence: `border: none` hält die Segmented-Trenner fern; Test `frontend/src/lib/components/mobile/__tests__/s3a2794_mtabbar_leiste_soll.test.ts` rot bei Entfernung.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

Fix-Loop 2 schließt F007, F008, F009, F010 (Mutationen jeweils rot; neue Tests messen Verhalten bzw. echtes Render/Instanz-Skript, kein Mock-Theater). Keine offenen Findings.
Tests: 8337 gelaufen, 8332 passed, 0 failed, 5 skipped (Alt-Skips).
Mutationen: F007 (Desktop+Mobil), F008, F009 (3 Varianten), F010 plus N1 bis N6 wiederholt/neu, alle rot (N3 nur im Komponenten-Gesamtlauf, dort rot); Wiederherstellung per cmp identisch.
Checklist: alle ACs belegt. Staging-Lauf in /e2e-verify Pflicht für AC-3, AC-4, AC-36 (Browserhälfte), AC-7, AC-8 (beide Staging-Specs noch nicht gelaufen).

## Geprüfte Dateien

- sha256:3cbe0326956c7ed61c717102db9bd8d8e018ee6bc6911fdcdfb9e7ca0ec47e2f  frontend/playwright.2794-s3a2.staging.config.ts
- sha256:1d47dbb9f788ecd54cb856d1ed92a7441dd3509288fae3f0cbe82e203c1a9d0e  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:bd7688d6ede27a176238fff146cfea9654061b9c49444151e264d1eb46f771f6  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:178d1dc1259b4d77cca02c7394db6ef45cd70b7d420779a9b5536a5cddb6b0cc  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- sha256:76576f7305e7d4c5b6c85227da7f9bb4e3e8092c2024175a7696f7f3a78c950b  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- sha256:868fe1fa658733d8fd0f717ef87bc267e910b05f6a9f767d20750bbbf7a30afb  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- sha256:282fb7b279ce1c3c6fa210ad5dfbad3583523579330e027e919570da88f08eaa  frontend/src/lib/components/shared/infoboxKeys.ts
- sha256:bce62d1fb18c247eda6fbdc863b0bb6d2d5c73a7dfa09c5da66ba217ef269daf  frontend/src/lib/components/shared/subscriptionTabs.ts
- sha256:a6bfa6551df1c1ed71f2d36f4d00c4c489130c937410e76c0fa8d43f22ac5f94  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:a1655a06a5b1502ab931e886dbb085dd925e7ac8df585ae672a8d1bcadb7ad21  frontend/src/lib/components/trip-detail/TripTabs.svelte
- sha256:47ee99c660d5f5c7d78deaaecdca4baec3895aae801c690d37139ec58fe563c7  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:00ef7997c0bffe85408e3b07470b186e055cedb436b021e5594e9898a9f453c3  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Prüfbasis

- base: c5af91376e2c5b370315c49c9f34ac5d5d3ab290
- blob:471411928f4486a9e08e868866d5e08a3030e333  frontend/playwright.2794-s3a2.staging.config.ts
- blob:bafc7e3036311c02cb08e43ecf0ccffb7c35452b  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:ec8d311ffa40baba07db3304572729b8c680b563  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:4c7bd19ead17e938fcb21dcbe9e7262f45fa3f74  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- blob:0d940debc060efcfb12fbe2a1bbf4066f218b5c2  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- blob:bd7d033554ffc068e7cc979b48e2d1e0cfc76cf5  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- blob:2b203ead7f7b8115e37f58defe9dcc1d0af68f56  frontend/src/lib/components/shared/infoboxKeys.ts
- blob:b204e3d5f93c3a8afa8d5cbcd6838c0c30f43d17  frontend/src/lib/components/shared/subscriptionTabs.ts
- blob:deea933481ef4eb66cc4c297aae5f4b829e9aa3b  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:d528144752b42f86c63168a0d499f9aff64aebe6  frontend/src/lib/components/trip-detail/TripTabs.svelte
- blob:3cfdcac2e5418f21d920154dd03dab1c46641d84  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:39e7c396b5711cf5cb726bfb924a6c31758609ca  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Geprüfte Dateien

- sha256:3cbe0326956c7ed61c717102db9bd8d8e018ee6bc6911fdcdfb9e7ca0ec47e2f  frontend/playwright.2794-s3a2.staging.config.ts
- sha256:1d47dbb9f788ecd54cb856d1ed92a7441dd3509288fae3f0cbe82e203c1a9d0e  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:bd7688d6ede27a176238fff146cfea9654061b9c49444151e264d1eb46f771f6  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:178d1dc1259b4d77cca02c7394db6ef45cd70b7d420779a9b5536a5cddb6b0cc  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- sha256:8d044031675ac177bace2ae4792df7238e207b54eaef3fbc38de68298a89c2f5  frontend/src/lib/components/shared/anlegeLockEngine.ts
- sha256:76576f7305e7d4c5b6c85227da7f9bb4e3e8092c2024175a7696f7f3a78c950b  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- sha256:868fe1fa658733d8fd0f717ef87bc267e910b05f6a9f767d20750bbbf7a30afb  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- sha256:282fb7b279ce1c3c6fa210ad5dfbad3583523579330e027e919570da88f08eaa  frontend/src/lib/components/shared/infoboxKeys.ts
- sha256:bce62d1fb18c247eda6fbdc863b0bb6d2d5c73a7dfa09c5da66ba217ef269daf  frontend/src/lib/components/shared/subscriptionTabs.ts
- sha256:5db767f42779d23556a4e9658e28f58b4bedf32d24714d45fcdcd35871573994  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts
- sha256:a6bfa6551df1c1ed71f2d36f4d00c4c489130c937410e76c0fa8d43f22ac5f94  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:a1655a06a5b1502ab931e886dbb085dd925e7ac8df585ae672a8d1bcadb7ad21  frontend/src/lib/components/trip-detail/TripTabs.svelte
- sha256:47ee99c660d5f5c7d78deaaecdca4baec3895aae801c690d37139ec58fe563c7  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:00ef7997c0bffe85408e3b07470b186e055cedb436b021e5594e9898a9f453c3  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Prüfbasis

- base: 08e0d9f1a72513161abbec98c81baf8f5c128945
- blob:471411928f4486a9e08e868866d5e08a3030e333  frontend/playwright.2794-s3a2.staging.config.ts
- blob:bafc7e3036311c02cb08e43ecf0ccffb7c35452b  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:ec8d311ffa40baba07db3304572729b8c680b563  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:4c7bd19ead17e938fcb21dcbe9e7262f45fa3f74  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- blob:83978d969ee6aededb6793c5d8c89261bc28ab2e  frontend/src/lib/components/shared/anlegeLockEngine.ts
- blob:0d940debc060efcfb12fbe2a1bbf4066f218b5c2  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- blob:bd7d033554ffc068e7cc979b48e2d1e0cfc76cf5  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- blob:2b203ead7f7b8115e37f58defe9dcc1d0af68f56  frontend/src/lib/components/shared/infoboxKeys.ts
- blob:b204e3d5f93c3a8afa8d5cbcd6838c0c30f43d17  frontend/src/lib/components/shared/subscriptionTabs.ts
- blob:ce21f922eb742985086b882619c1120c5f87d5bf  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts
- blob:deea933481ef4eb66cc4c297aae5f4b829e9aa3b  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:d528144752b42f86c63168a0d499f9aff64aebe6  frontend/src/lib/components/trip-detail/TripTabs.svelte
- blob:3cfdcac2e5418f21d920154dd03dab1c46641d84  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:39e7c396b5711cf5cb726bfb924a6c31758609ca  frontend/src/lib/components/trip-new/tripNewLogic.ts
