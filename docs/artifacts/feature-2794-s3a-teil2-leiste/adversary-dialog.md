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

### Runde 5
**Adversary:**
Anlass: CI-E2E-Regression nach Runde 4 (zwei PUTs je Cooldown-Geste, Cooldown nach sofortigem Neuladen verloren). Ursache: im Ortsvergleich sind `VersandTab` und `AlarmeTab` im Reiter `zustellung` gleichzeitig gemountet; `versandSnapshotAus` las `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` mit, der Versand-Speicherer feuerte bei jeder Cooldown-Geste mit (Owner-Verdrängung im Controller). Runden 1 bis 4 hatten dieses Muster (zwei Owner auf einem Feld durch Zusammenlegen der Reiter) nicht geprüft; der Kern-Wächter `s3a2794_speicher_owner_waechter.test.ts` prüft Owner-Strings, nicht die Felder-Überschneidung. Das war eine Lücke dieses Dialogs.

Testlauf: Kern-Gesamtlauf `npm test -- "src/**/*.test.ts"`, Ausgabe `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Der neue Test `frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_ein_speicherer.test.ts` ist kein Mock-Theater: beide echten Speicherer (Versand und Alarme), echter Controller, echte Hub-Queue, Transport über echtes `api` gegen den Go-Merge-Prüfserver, gemeinsamer Feldsatz; er zählt die PUTs am Server.

Mutationsgegenprobe am Fix (String-Ersetzung, Sicherung im Scratchpad `r5/`, danach `cmp` identisch):
- M1 alle drei alert-Felder wieder in `versandSnapshotAus`: ROT (3 von 4 Tests). Gefangen dort, wo es wirkt (zwei echte Speicherer, PUT-Zählung am Server).
- M2 nur `alertQuietTo` wieder im Snapshot: ROT (1 Test, Stille-Stunden-Test), jedes einzelne Feld ist bewacht.
- M3 Rollback-Liste plus `alertCooldownMinutes`: im neuen Test grün, in den übrigen Versand-Tests ROT (1). M4 Rollback ohne `endDate`: ROT (1). M5 ohne `eveningTime` und `endDate`: ROT (2). M6 ohne `sendTelegram`: ROT (1). Die Rollback-Liste ist durch die Altsuite bewacht, nicht durch den neuen Test; ausreichend.
- Frage 3 (Nebenwirkung Rollback ohne alert-Felder): Den Rollback der Zustellungsfelder übernimmt der Alarme-Speicherer, dessen Rollback-Liste die drei Felder führt. Mutation A1 (die drei aus `rollbackAlarmSnapshot` gestrichen): ROT (`F205` in den Alarme-/Retry-Tests, 47 pass, 1 fail). Die Verantwortung ist eindeutig und bewacht; der Versand-Fehlerpfad fasst die Felder nicht mehr an (zuvor war er ein zweiter, unnötiger Schreiber).

Suche nach derselben Fehlerklasse (zwei Owner auf einem Feld bei gemeinsam gemounteten Speicherern):
- Reiter `zustellung` (Vergleich): Wetter-Panel (Owner `wetter-metriken`, `bereich="zustellung"`), `VersandTab`, `AlarmeTab`. Versand-Snapshot {sendTelegram, sendSms, sendPremiumSms, morning*, evening*, endDate}; Alarme {officialAlerts*, radar, metricAlertLevels, cooldown, quiet*, telegramStyle, channelThresholds, channels, alertMetricChannels}; Wetter {activeMetricKeys, channelActiveMetricKeys, officialAlertsEnabled, dayWindow*, hourly*, outlook*}. Einzige verbleibende Überschneidung: `officialAlertsEnabled` (Wetter und Alarme). Der Schalter liegt im Wetter-Abschnittsfilter, nicht in `ZUSTELLUNGS_SECTIONS` (`frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86`), und der Alarme-Teil mutiert das Feld nicht (nur Anzeige `amtlicheWarnungenImBericht`). Keine gleichzeitige Gesten-Quelle, kein Finding.
- Reiter `wetter` (Vergleich): Wetter-Panel und `CorridorEditor`; Überschneidung `activeMetricKeys` und `metricAlertLevels`. `CorridorEditor` ist seit #2792 S1c-3 `gesperrt = true` (patch/add/remove sind No-op, `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte:287`), meldet also nie. `hub-wertebereiche-speichert-selbst.spec.ts` erwartet KEINEN PUT. Kein Finding.
- Trip-Hub (`TripTabs.svelte`): Wetter-Panel, `BriefingScheduleTab` (Owner `versand`) und `AlarmeScheduleTab` speichern über `saveController.schedule(..., owner)` mit Eigenfeld-Nutzlasten (`pickEigenfelder`, `buildAlarmeDeliveryPayload`); die Felder sind disjunkt. Kein Finding.
- Anlege-Ketten (`TripNewEditor`, `CompareNewEditor`): Create-Modus ohne Controller/Preset, `versandVergleichSpeicherungAktiv` ist falsch, `scheduleAutoSave` bricht bei `createMode` ab. Kein Speicherer aktiv, die Fehlerklasse ist strukturell ausgeschlossen.

E2E-Specs (23 umgestellt, Stichprobe per Diff gegen die Basis): `hub-versand-aufbau.spec.ts` VA-1: die seitenweite Prüfung wurde auf den Abschnitt begrenzt und um `alert-metric-level-table` ergänzt (strenger, nicht schwächer; fachlich korrekt, weil Versand und Alarme jetzt im selben Reiter stehen). `design-compliance-group-a.spec.ts` AC-1a/1c: Reiternamen auf den Soll `Wetter`/`Zustellung` (`exact: true`), `Wertebereiche` neu mit `toHaveCount(0)`. Kein `skip`, keine verlängerten Timeouts, keine entfernten `expect`. Keine Abschwächung gefunden.

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107
  Evidence: `versandSnapshotAus` liest nur die Versandfelder; die Cooldown-Geste erzeugt genau einen PUT über den Alarme-Owner, der Wert steht am Server (`server.stand(ID).alert_cooldown_minutes`); M1/M2 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T1
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:213
  Evidence: Rollback des Versands fasst die alert-Felder nicht mehr an, Nutzlast unverändert Eigenfelder (`VERSAND_TOP`); Alarme-Rollback führt die drei Felder (`frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:265`, A1 rot). Owner-Strings unverändert.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T3
  Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:152
  Evidence: Wertebereiche-Speicherer im Reiter `wetter` ohne Gesten-Quelle (Korridor gesperrt), keine Überschneidung mit `zustellung`; Hydration und Flush-Liste unverändert (`frontend/src/lib/components/shared/subscriptionTabs.ts:126`).
  Status: CONFIRMED

### Runde 6
**Adversary:**
Zweite Runde, bewusst skeptisch gegen Runde 5.

Finding:
  ID: F011
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:36
  Description: Der Typ `VersandSnapshot` führt `alertCooldownMinutes`/`alertQuietFrom`/`alertQuietTo` weiter als optionale Felder, obwohl `versandSnapshotAus` sie nie mehr füllt; ein künftiger Aufrufer könnte sie wieder einschleusen (das Diff-Gate würde sie mitvergleichen). Die Rückkehr ist durch den Kern-Test bewacht (M1/M2 rot), nicht durch den Typ.
  Spec requirement: AC-2.T1 — gleicher Request, Feld-Besitz je Owner.
  Conflict: Kein aktueller Fehler; das Typ-Signal ist irreführend.
  Remediation: Felder aus `VersandSnapshot` entfernen, sobald Hydration und Snapshot-Typ getrennt sind (Folgeschritt, kein Blocker).

Weitere Versuche, den Fix zu brechen (ohne Befund):
- Fehlerpfad: `rollbackVersandSnapshot` läuft nur bei Nicht-412 (`frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:304`). Scheitert ein Alarme-PUT mit 500, setzt der Alarme-Rollback den Cooldown zurück (A1 rot). Scheitert ein Versand-PUT, bleibt ein ungespeicherter Cooldown stehen, was richtig ist (er gehört dem Alarme-Owner).
- Bestands-Preset mit Cooldown plus Versand-Änderung: die Nutzlast sendet die alert-Felder nicht (`VERSAND_TOP`); der Test bewacht das am Server (`'alert_cooldown_minutes' in puts()[0]` ist false). Ampel, Etappen und Orte bleiben unverändert, weil der Go-Merge-Prüfserver Teilfeld-Nutzlasten mergt.
- Hydration: `hydrateVersandFieldsFromPreset` (`frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:84`) füllt die Cooldown-Wertprops weiter; die Anzeige im Alarme-Teil kommt aus `frontend/src/lib/components/compare/alarmePropsAus.ts:134`, unverändert.
- Browserhälfte (Neuladen, PUT-Zählung der drei CI-Specs) ist nur auf Staging prüfbar und gehört in /e2e-verify, kein Finding.

Dateien der Pflichtliste, je mit Fundstelle:
- Code reference: frontend/playwright.2794-s3a2.staging.config.ts:28 (Staging-Specs, nur /e2e-verify)
- Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32 (`tailUnlocked`, Kette Wetter dann Zustellung)
- Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:152 (Wertebereiche-Speicherer)
- Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99 (`VERSAND_ZIEL` Reiter Zustellung)
- Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24 (Infobox `zustellung`)
- Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126 (Umleitung `briefings` auf `zustellung`)
- Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107 (Fix: Snapshot ohne alert-Felder)
- Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86 (`ZUSTELLUNGS_SECTIONS`)
- Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35 (`TAIL` Wetter und Zustellung)

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86
  Evidence: Vereinigung der Abschnitts-Bereiche ist alles; der Fix ändert die Darstellung nicht.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35
  Evidence: Anlege-Ketten im Create-Modus ohne Speicherer, Fehlerklasse ausgeschlossen.
  Status: CONFIRMED

### Runde 7
**Adversary:**
Prüfung der Merge-Auflösung (Konflikt #2794 gegen #2880, `origin/main` in Arbeit, noch kein Commit). Vergleich je Datei per Diff gegen HEAD (unsere Seite vorher) und gegen MERGE_HEAD (main-Seite). Testlauf: voller Kern-Lauf `cd frontend && npm test` 8363 Tests, 8358 pass, 0 fail, 5 skip (Alt-Skips); Ausgabe in `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Leitfrage: ist jede Zusicherung dort geprüft, wo sie WIRKT?

Befund der Auflösung: Gegenüber main ist in den drei Konfliktdateien nur #2794 hinzugekommen (Reiter wetter/zustellung, Kennungen, ZustellungTab, Flush-Liste, TAIL), gegenüber unserer Seite nur #2880 (HubReiterflaeche um Übersicht, Etappen/Orte; `.compare-tabs-content`-Rand und `.tab-panel` entfallen). Von main wurde nichts still verworfen außer den alten Reitern wetter-metriken, wertebereiche und alarme. Die #2880-Spec verlangt die Reiterfläche nur für Übersicht, Etappen und Orte; Reiter mit eigenem Rand (CorridorEditor, AlarmeTab, VersandTab, WeatherMetricsTab tragen je 28/40/60) bleiben ohne Behälter, also ist Wetter/Zustellung ohne HubReiterflaeche spec-konform. Die umgestellte PF-Spec misst Wetter und Zustellung in PF-1/PF-2 gegeneinander, die Änderung beschränkt sich auf den Austausch der Reiterliste.

Mutationen (String-Ersetzung, Sicherung im Scratchpad, danach cmp identisch, unstaged Diff leer). Zielsuite: 3488 Tests aus compare, shared, trip-detail, trip-new, compare-new und routes/compare.
- M1 HubReiterflaeche-Hülle der Vergleichs-Übersicht entfernt: 5 rot (Goldens hub_uebersicht/hub_seite, AC-3 Ist-Stand). GEFANGEN.
- M2 Hülle des Orte-Reiters entfernt: 1 rot (Golden hub_orte.de). GEFANGEN, nur durch das Golden.
- M3 Trip-Hülle der Übersicht entfernt: 2 rot (Goldens hub_seite, hub_reiter). GEFANGEN.
- M4 Zustellung-Panel im Trip-Hub durch alten Reiter alarme ersetzt: 7 rot (Panel-Weiche, AC-2.T2, F004 Versand-Sprung). GEFANGEN.
- M5 alten Behälterrand 28/40/80 im Vergleich wieder eingeführt (doppelte Einrückung): 3 rot (Goldens). GEFANGEN.
- M7 Zustellung aus der Trip-Flush-Liste entfernt: 3 rot (AC-2.T3, AC-7, AC-26). GEFANGEN.
- M8 TAIL des Vergleich-Editors so verdrahtet, dass Zustellung an Wetter hängt: 12 rot. GEFANGEN.
- M9 Standardwerte-Vorbelegung im Vergleich-Editor entfernt: 3 rot (AC-7). GEFANGEN.
- M6 Alarm-Hydration-Bedingung vor dem Mount des Reiters Zustellung im Vergleich entfernt: 0 rot. ÜBERLEBT (F012).
- M10 CorridorEditor (Wertebereiche, Desktop) aus dem Reiter Wetter im Trip-Hub entfernt: 0 rot. ÜBERLEBT (F013).

Finding:
  ID: F012
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827
  Description: Der Mount von ZustellungTab im Vergleich hängt an `wetterMetrikenLayoutHydrationBereit && versandHydrated && alarmeHydrated`. Entfernt man `alarmeHydrated`, bleibt die gesamte Zielsuite grün. Die Bedingung stammt aus unserer Seite, nicht aus dem Merge, ist aber nirgends bewacht (`s3a2794_flush_hydration_kette.test.ts` prüft die Hydrations-Auslösung, nicht den Mount-Wächter).
  Spec requirement: AC-2.T3 — Lazy-Hydration des Vergleichs greift unter wetter und zustellung, sodass nach Wechsel und Neuladen nichts verloren ist.
  Conflict: Ohne Wächter kann der Alarm-Bereich mit Platzhalterwerten gemountet werden und beim ersten Speichern Cooldown/Stille Stunden überschreiben; kein Test fällt auf.
  Remediation: AST-Test, dass der ZustellungTab-Mount unter einer Bedingung steht, die `alarmeHydrated` enthält (Muster `s3a2794Ast.ts`), plus Laufzeitfall mit nicht hydriertem Alarm-Zustand.

Finding:
  ID: F013
  Severity: MEDIUM
  Category: spec_violation
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223
  Description: Der Reiter Wetter des Trip-Hubs bindet unter der Metrik-Auswahl die Wertebereiche ein (CorridorEditor Desktop, CorridorEditorMobile mobil). Wird der Desktop-Zweig gelöscht, bleibt jede Suite grün; kein Test hält fest, dass die Wertebereiche im Trip-Reiter Wetter stehen.
  Spec requirement: Spec-Checkliste Output — Wetter zeigt die bisherige Metrik-Oberfläche plus Wertebereiche (bis Teil-PR 3).
  Conflict: Der Verlust der Wertebereiche im Trip-Hub (Desktop) würde unbemerkt durchgehen; im Vergleich bewacht ein Test den Mount, im Trip nicht (Pendant-Lücke).
  Remediation: AST-Test in der Art von `s3a2794_eine_wmt_instanz.test.ts`: TripTabs-Zweig `wetter` enthält genau einen CorridorEditor je Viewport und kein CorridorEditor unter `zustellung`.

Finding:
  ID: F014
  Severity: LOW
  Category: regression
  Code reference: frontend/e2e/layout-tab-vergleich.spec.ts:112
  Description: Die lokal roten Fälle sind nicht durch den Merge entstanden. AC-11 (`channel-tab-email` darf nicht vorkommen) ist schon auf main falsch: `LayoutTab` mit `LTChannelPicker` stand dort im Reiter wetter-metriken (WeatherMetricsTab) und steht jetzt im Reiter Zustellung; #2794 verschiebt ihn nur. AC-7 (`compare-layout-hourly-metric-temp_c`, `-wind_kmh`) hängt an den Katalogzeilen aus `CompareHourlyLayoutControls.svelte`, die gegenüber main unverändert sind (Katalog/Profil der Umgebung). Die Datei steht nicht in `.github/ci_e2e_specs.txt`, läuft also nicht in CI.
  Spec requirement: Spec #2794 AC-7 — alle Bedienelemente vorhanden (kein Verbot des Kanal-Umschalters).
  Conflict: Veraltete Zusicherung (Attrappen-Verbot aus F2a), kein Fehler der Implementierung; stört nur, wer die Datei lokal laufen lässt.
  Remediation: Spec-Datei an den Ist-Stand anpassen oder streichen (Folgeticket); kein Blocker für diesen Merge.

### Runde 8
**Adversary:**
Zweite Runde, bewusst skeptisch gegen Runde 7: Wurden Zusicherungen des Merges nur dort geprüft, wo der Code steht? Ergebnis: Hülle (M1 bis M3, M5) und Kennungen (M4, M7, M8, M9) sind an den Wirkstellen bewacht, die Reiterfläche aber nur über Goldens und die PF-Playwright-Spec (Staging, nicht im Kern). Die Goldens wurden neu erzeugt; sie sind kein unabhängiges Soll und würden jede Änderung mittragen, die jemand neu erzeugt. Das ist eine Schwäche, kein Fehler: die Kern-Wächter M1 bis M5 sind rot, und PF-1 bis PF-3 messen unabhängig auf Staging (Pflicht in /e2e-verify, nicht Teil dieses Laufs).

Weitere Prüfungen ohne Befund:
- Keine doppelte Einrückung: `compare-tabs-content` trägt nur `position: relative` (`frontend/src/lib/components/compare/CompareTabs.svelte:700`), `.tab-panel` ist entfernt; Wetter und Zustellung stehen ohne Behälter und tragen ihren Rand selbst.
- AnlegeReiter mit optional-Flag in TripNewEditor (`frontend/src/lib/components/trip-new/TripNewEditor.svelte:588`) und CompareNewEditor unverändert gegenüber main; Field/MField (pflicht/side) ohne Abweichung zu main (leerer Diff gegen MERGE_HEAD).
- Anlege-Ketten: 4 Pflicht-Segmente, Wegpunkte optional (Trip 5 Reiter); Tests `trip_new_reiterleiste_besuchs_flags.test.ts` und `fortschritt_in_beiden_editoren_gleich.test.ts` angepasst, nicht abgeschwächt (Reiterzahl 5 bzw. 4 geprüft).
- Fremdänderungen gegenüber main, die nicht #2794 sind: keine (WeatherSummaryCard und zwei Tests sind #2794-Nachzug der Kennung `wetter`).

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:53
  Evidence: Reiter Übersicht, Etappen, Wetter, Zustellung aus der einen Definition; TripTabs-Panels für genau diese Kennungen (`frontend/src/lib/components/trip-detail/TripTabs.svelte:226`); M4 rot.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:722
  Evidence: Orte-Reiter mit Badge, Wetter und Zustellung im Vergleich; M2 rot (Golden). Mount-Wächter Zustellung siehe F012.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:1
  Evidence: Leistenoptik aus dem geteilten Baustein, durch den Merge unverändert; Kern-Wächter grün, Staging in /e2e-verify.
  Status: CONFIRMED

Confirmation:
  AC: AC-36
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1
  Evidence: Kopf-Baustein unverändert; Regressionswächter grün (8363 Tests, 0 fail).
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:1
  Evidence: Pill-Leiste mit vier Reitern, der Merge ändert sie nicht; Staging in /e2e-verify.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126
  Evidence: Umleitung briefings/versand auf zustellung, Adressanker `#versand` in TripTabs (`ankerDerAdresse`); M4 rot im F004-Test.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96
  Evidence: TAIL Wetter dann Zustellung; M8 12 Tests rot, M9 3 rot; Trip: `frontend/src/lib/components/trip-new/tripNewLogic.ts:35`.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86
  Evidence: `ZUSTELLUNGS_SECTIONS` unverändert; ZustellungTab im Trip (`frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1`) und Vergleich gemountet; Inventar-Wächter grün. Einschränkung: Wertebereiche-Mount im Trip ungeprüft (F013).
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107
  Evidence: Cooldown-Fix unverändert, Versand-Snapshot ohne alert-Felder; Kern-Test grün.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T1
  Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99
  Evidence: Owner-Strings unverändert im Code (Wächter `s3a2794_speicher_owner_waechter.test.ts` grün).
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T2
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:226
  Evidence: höchstens eine WMT-Instanz; M4 rot im AC-2.T2-Test.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T3
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:174
  Evidence: Flush-Liste wetter/zustellung/etappen; M7 rot. Hydration unter wetter und zustellung im Vergleich (`frontend/src/lib/components/shared/subscriptionTabs.ts:126`); der Alarm-Mount-Wächter ist ungeprüft (F012).
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T4
  Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32
  Evidence: Vorbelegung `corridors` im Anlege-Weg; M9 rot (3 Tests), Standardwerte warten auf `wertebereicheVorbelegt`.
  Status: CONFIRMED

Dateien der Pflichtliste, je mit Fundstelle:
- Code reference: frontend/playwright.2794-s3a2.staging.config.ts:20 (Staging-Specs, nur /e2e-verify)
- Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827 (Mount-Wächter Zustellung, F012; Reiterflächen 707 und 722)
- Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:1 (Leiste)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1 (AST-Helfer der Wächter)
- Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32 (`tailUnlocked`)
- Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99 (Wertebereiche-Speicherer)
- Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99 (`VERSAND_ZIEL`)
- Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24 (Infobox `zustellung`)
- Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126 (Umleitung)
- Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107 (Cooldown-Fix)
- Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86 (`ZUSTELLUNGS_SECTIONS`)
- Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1 (Übergangsreiter)
- Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223 (Wertebereiche im Reiter Wetter, F013; Reiterfläche 205, ZustellungTab 226, Flush 174)
- Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:588 (AnlegeReiter)
- Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35 (`TAIL`)
- Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96 (`TAIL` des Vergleichs)

### Runde 9
**Adversary:**
Prüfung der Nachbesserung für F012/F013 und der erweiterten Merge-Auflösung (origin/main bis aa87c363d, #2371 und #2879, noch nicht committet). Vergleich je Datei per `git diff HEAD --cached` (unsere Seite) und `git diff aa87c363d --cached` (main-Seite). Voller Kern-Lauf `cd frontend && npm test`: 8379 Tests, 8374 pass, 0 fail, 5 skip (Alt-Skips); Ausgabe in `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Leitfrage: ist die Zusicherung dort geprüft, wo sie WIRKT, und nicht nur dort, wo der Code steht?

Gegenprobe zu F012/F013 (Mutation per String-Ersetzung über ein Hilfsskript im Scratchpad, Sicherungskopie vorher, danach `cmp` identisch, unstaged Diff des Produktionscodes leer):
- M6 `alarmeHydrated` aus der Mount-Bedingung des ZustellungTab im Vergleich entfernt: `s3a2794_zustellung_vergleich_mount_hydration.test.ts` 2 von 3 rot. GEFANGEN, F012 geschlossen.
- M6b stattdessen `versandHydrated` entfernt: 2 rot. GEFANGEN.
- M6c stattdessen `wetterMetrikenLayoutHydrationBereit` entfernt: 1 rot (Kombinationstest über alle 8 Flag-Belegungen). GEFANGEN.
- M10 CorridorEditor (Desktop-Zweig) im Reiter Wetter des Trip-Hubs entfernt: `s3a2794_trip_hub_wetter_wertebereiche.test.ts` 3 von 5 rot. GEFANGEN, F013 geschlossen.
- M10b CorridorEditorMobile entfernt: 3 von 5 rot. GEFANGEN.
Die Wächter messen den AST der echten Komponenten und werten die Weichen-Bedingung für alle Flag-Kombinationen aus; sie prüfen also Verschiedenheit (nur alle drei Flags zugleich mounten) und nicht bloß Vorhandensein. Kein Mock, kein Textmuster.

Merge-Auflösung #2879/#2371, Befund je Datei gegen die main-Seite (aa87c363d):
- Btn.svelte, StandardwerteSpeichernKnopf.svelte, app.css: gegenüber aa87c363d kein Unterschied (nicht in `git diff aa87c363d --cached`), also vollständig von main übernommen; `aria-disabled` und Sperr-Stil ohne Opacity (#2371) sowie Accent-Fläche `--g-accent-deep` (#2879) stehen unverändert da. Nichts still verworfen.
- MTabBar.svelte: Abweichung gegenüber main nur #2794 (Wurzel ohne `data-slot="segmented"`, Badge 10 px, aktiver Reiter 600, `border: none`). Der #2879-Zweig des Handy-Reiters (aktiver Reiter `--g-accent-deep`/Papier, Zeilen 189 bis 192) ist erhalten; die Selektoren hängen an `.mtabbar :global([data-slot='segmented-item'])`, nicht an der Wurzel, die Entfernung von `data-slot="segmented"` schwächt #2879 also nicht.
- TripNewEditor.svelte: einziger Konflikt. Auflösung im Wegpunkte-Schritt: Knopf ruft `makeEtappenContinueHandler('wetter')` und trägt `background: var(--g-accent-deep)` (#2879) statt `--g-accent`; ebenso der Handy-Zweig und der Fuß. Sonst gegenüber main nur #2794 (Besuchs-Flags wtVisited/zuVisited, eine WMT-Instanz mit `bereich`, CorridorEditor im Schritt Wetter, Zustellung-Weiter). Die `--g-ink-3`-Schrift der Überspringen-Knöpfe aus #2879 bleibt. Kein `wetter-metriken`, `wertebereiche` oder `alarme` mehr als Ziel.
- CompareTabs.svelte, TripTabs.svelte, CompareNewEditor.svelte: gegenüber main nur #2794-Deltas (Reiter wetter/zustellung, Kennungen `compare-editor-continue-wetter`/`-zustellung`, TAIL, Flush, Mount-Wächter); keine #2879/#2371-Zeile verloren (Filter auf ink/opacity/disabled/accent in den Diffs: nur die ersetzten Weiter-Kennungen).

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80
  Evidence: Wurzel `.mtabbar` ohne Segmented-Box, aktiver Reiter 600, Badge 10 px (Zeilen 114 bis 150); #2879-Handy-Zweig (Zeilen 183 bis 199) erhalten.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96
  Evidence: TAIL Wetter dann Zustellung; Trip-Pendant `frontend/src/lib/components/trip-new/tripNewLogic.ts:35`; Anlege-Reiterleiste `frontend/src/lib/components/trip-new/TripNewEditor.svelte:588`. Einschränkung: Weiter-Ziel des Wegpunkte-Schritts ungeprüft (F015, Runde 10).
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T3
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827
  Evidence: Mount-Bedingung `wetterMetrikenLayoutHydrationBereit && versandHydrated && alarmeHydrated`, durch M6/M6b/M6c bewacht (F012 zu); Flush-Liste im Trip `frontend/src/lib/components/trip-detail/TripTabs.svelte:174`.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223
  Evidence: Wertebereiche im Reiter Wetter (Desktop 223, mobil 221), ZustellungTab 226; M10/M10b rot (F013 zu).
  Status: CONFIRMED

### Runde 10
**Adversary:**
Zweite Runde, bewusst skeptisch gegen Runde 9: Dort wurde der Merge nur per Diff gelesen. Frage: bewacht irgendein Test die in der Konfliktauflösung wirksam gewordenen Zusicherungen? Mutationen an der Stelle, die der Nutzer erreicht (der Weiter-Knopf des Wegpunkte-Schritts im Trip-Anlegen):
- M11 Ziel des Knopfs „Wegpunkte übernehmen" (`TripNewEditor.svelte:817`) von `'wetter'` auf `'zustellung'` umgebogen: voller Kern-Lauf (8379 Tests) 0 rot; auch `s3a2794_zustellung_ziel_und_bereich.test.ts` (3 grün) und `anlege_weiter_knopf_zielt_auf_existierenden_reiter.test.ts` (4 grün) bleiben grün. ÜBERLEBT (F015). Der Alt-Test prüft nur, dass das Ziel ein existierender Reiter der Kette ist; der Fall F007 (Zielbindung an die Beschriftung) deckt nur die Knöpfe „Zustellung einrichten" und „Wetter" ab, nicht die drei Wegpunkte-Knöpfe (Zeilen 781, 813, 817). Nutzerwirkung: der Nutzer überspringt Wetter (Metrik-Auswahl und Wertebereiche) ohne Hinweis; der Schritt Wetter bleibt mit Standardwerten vorbelegt, daher kein Datenverlust, aber ein Bruch der Kette AC-6.
- M12 dieselbe Schaltfläche von `--g-accent-deep` zurück auf `--g-accent` (Verlust von #2879): 8 Tests der Besuchs-Flags/Reiterleiste grün. Der Kern-Lauf ist blind dafür; geprüft wird die Farbe nur im Staging-E2E `frontend/e2e/kontrast-trip-vergleich.spec.ts` (KO-5 überfährt jeden sichtbaren Accent-Knopf, KO-3 misst den Schritt „Wegpunkte prüfen"). Das ist ein Staging-Wächter, kein Kern-Wächter; Hinweis, kein eigenes Finding, da die Spec #2879 den Nachweis ausdrücklich im Browser verlangt. M12 lief nur mit einer einzelnen Testdatei, nicht mit dem vollen Lauf.
- Falle des Hilfsskripts: ein Ordner als Argument (`npm test -- <Ordner>`) läuft nicht und wurde als „rot" gemeldet; das ist kein Treffer und wurde verworfen. Gültig sind nur benannte Dateien oder der volle Lauf.

KO-3 in `frontend/e2e/kontrast-trip-vergleich.spec.ts` (nur statisch): `tripReiter(page, mobil, nr)` (Zeile 222) wählt die Reiter nach Position. Position 1 ist Etappen (Zeile 232), Position 2 Wegpunkte (Zeile 252). Unsere Kette ist `route, etappen, wegpunkte, wetter, zustellung` (`frontend/src/lib/components/trip-new/tripNewLogic.ts:27`); Position 2 ist also weiterhin Wegpunkte, die Zusicherung passt. Auch die Wirkstellen stimmen: Testid `tn-mobile-tabbar` trägt der geteilte Baustein (`TripNewEditor.svelte:934`), Desktop `.tn-desktop` (Zeile 562). Der Wegpunkte-Reiter wird erst nach GPX-Upload entsperrt (`etDone`); die Spec prüft `not.toHaveAccessibleName(/⊘/)` vorher. Die neuen Schritte Wetter (Position 3) und Zustellung (Position 4) misst KO-3 absichtlich nicht (Kopfkommentar „außerhalb der Reiter Wetter-Metriken/Wertebereiche/Alarme (#2794)"); der Kommentar nennt noch die alten Namen (F016, LOW). Auch der Vergleich hat Wetter und Zustellung nicht in der Messkette.

Weitere Randfälle ohne Befund: Testzahl 8363 auf 8379 (plus 8 neue Wächter, plus Zugänge aus main) ohne Verlust; die zwei neuen Testdateien stehen ungestagt im Arbeitsbaum (`??`) und müssen mit committet werden, sonst fehlt der Wächter im PR; die Staging-Konfig `frontend/playwright.2794-s3a2.staging.config.ts` matcht weiterhin nur die zwei #2794-Specs (Zeile 28) und zielt auf Staging, nie auf Produktion (baseURL Zeile 17).

Finding:
  ID: F015
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:817
  Description: Die drei Weiter-Knöpfe des Wegpunkte-Schritts (Zeilen 781, 813, 817; Zeile 817 ist die Konfliktzeile des Merges) rufen `makeEtappenContinueHandler('wetter')`. Wird das Ziel auf `'zustellung'` geändert, bleibt der gesamte Kern-Lauf grün (M11, 8379 Tests).
  Spec requirement: AC-6 — die Anlege-Kette des Trips führt Route, Etappen, Wegpunkte, Wetter, Zustellung; kein Schritt führt auf einen falschen Reiter.
  Conflict: Die Zusicherung ist nur gegen „existierender Reiter" geprüft (Alt-Test) und für die Knöpfe „Wetter" und „Zustellung" an die Beschriftung gebunden (F007); der Knopf, den die Konfliktauflösung berührt hat, hat keinen Wächter. Ein künftiger Merge könnte ihn unbemerkt auf einen anderen Reiter stellen.
  Remediation: Test in der Art von `s3a2794_zustellung_ziel_und_bereich.test.ts`: onclick-Ausdrücke der drei Wegpunkte-Knöpfe gegen das echte Instanz-Skript des Editors (`svelteInstanzPruefstand`) ausführen und `activeTab === 'wetter'` nach dem Klick prüfen; Handy-Weg `makeMobileWegpunkteContinueHandler` mitprüfen.

Finding:
  ID: F016
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/e2e/kontrast-trip-vergleich.spec.ts:8
  Description: Der Kopfkommentar von KO-3 beschreibt die ausgenommenen Schritte noch mit den alten Reitern „Wetter-Metriken/Wertebereiche/Alarme"; mit #2794 sind es Wetter und Zustellung. Die Messung selbst (Position 1 und 2) ist korrekt.
  Spec requirement: Spec #2879 AC-3 — jeder ohne Netz erreichbare Schritt außerhalb der von #2794 umgebauten Reiter ist gemessen.
  Conflict: Veralteter Kommentar; die Kontrastmessung für die neuen Reiter Wetter und Zustellung beim Anlegen fehlt, bis Teil-PR 3 sie abdeckt.
  Remediation: Kommentar nachziehen und die Ausnahme in Teil-PR 3 aufheben; kein Blocker.

Confirmation:
  AC: AC-1
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:53
  Evidence: Reiter Übersicht, Etappen, Wetter, Zustellung aus der einen Definition (Zeilen 52 und 53); TripTabs-Panels `frontend/src/lib/components/trip-detail/TripTabs.svelte:226`; CompareTabs-Reiterflächen `frontend/src/lib/components/compare/CompareTabs.svelte:707` und `:722` (Hülle nur Übersicht und Orte; Behälter `:700` trägt nur `position: relative`).
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126
  Evidence: Umleitung briefings/versand/alarme auf zustellung unverändert (Zeilen 126 bis 135).
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107
  Evidence: Cooldown-Fix im Versand-Snapshot unverändert; Owner-Strings `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99` unverändert.
  Status: CONFIRMED

Confirmation:
  AC: AC-36
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1
  Evidence: AST-Helfer; beide neuen Wächter nutzen ihn (`frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts:25`, `frontend/src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts:22`).
  Status: CONFIRMED

Dateien der Pflichtliste, je mit Fundstelle:
- Code reference: frontend/playwright.2794-s3a2.staging.config.ts:17 (baseURL Staging; testMatch Zeile 28, nur /e2e-verify)
- Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827 (Mount-Wächter Zustellung; Behälter 700, Reiterflächen 707 und 722)
- Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80 (Leiste)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1 (AST-Helfer der Wächter)
- Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32 (`tailUnlocked`)
- Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99 (Wertebereiche-Speicherer)
- Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99 (`VERSAND_ZIEL`)
- Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24 (Infobox `zustellung`)
- Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126 (Umleitung)
- Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107 (Cooldown-Fix)
- Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86 (`ZUSTELLUNGS_SECTIONS`)
- Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1 (Übergangsreiter)
- Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223 (Wertebereiche im Reiter Wetter; Flush 174, ZustellungTab 226)
- Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:817 (Weiter-Ziel Wegpunkte, F015; AnlegeReiter 588)
- Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35 (`TAIL`)
- Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96 (`TAIL` des Vergleichs)
- Code reference: frontend/src/lib/components/ui/btn/Btn.svelte:74 (`aria-disabled`, #2371, von main übernommen)
- Code reference: frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte:30 (`aria-disabled`, #2371)
- Code reference: frontend/src/app.css:366 (Accent-Fläche `--g-accent-deep`, #2879; Disabled-Stil 443, #2371)
- Code reference: frontend/e2e/kontrast-trip-vergleich.spec.ts:222 (KO-3, Reiter nach Position)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts:25 (F012-Wächter)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts:22 (F013-Wächter)

### Runde 11
**Adversary:**
Prüfung des F015-Wächters `frontend/src/lib/components/shared/__tests__/s3a2794_wegpunkte_weiter_ziel_wetter.test.ts` (Zeilen 54 bis 90, Messung in Zeile 84) und des Kommentars F016. Produktionscode seit Runde 10 unverändert (kein unstaged Diff in `frontend/src`). Der Wächter wertet die onclick-Ausdrücke aller Knöpfe in den drei Zweigen `activeTab === wegpunkte` (Desktop, Mobil-Inhalt, Mobil-Fuß) gegen das echte Instanz-Skript aus und erwartet danach `activeTab === wetter`. Er prüft damit die Wirkung (der Schalter wird wirklich umgelegt), nicht nur das Vorhandensein einer Zeichenkette. Der Messaufbau ist selbst abgesichert: genau 3 Zweige (Zeile 78) und mindestens 6 Knöpfe (Zeile 80), sonst rot; ein ausgelassener Knopf oder eine zu lockere Zweig-Zählung würde also nicht still grün bleiben.

Mutationen (String-Ersetzung per Hilfsskript im Scratchpad, Sicherungskopie `TNE.orig` vorher, nach jeder Mutation Rückkopie; am Ende `cmp` identisch). Nur die benannte Wächter-Datei lief je Mutation:
- M11 Zeile 817 Ziel `zustellung`: ROT (button@41187 schaltet auf zustellung). GEFANGEN.
- M14 Zeile 813: ROT. M15 Zeile 830: ROT. M16 Zeile 834: ROT. Alle GEFANGEN.
- M18 Zeile 817 Knopf macht nichts (`(() => {})`): ROT (bleibt auf wegpunkte). GEFANGEN.
- M17 Handy-Fabrik `makeMobileWegpunkteContinueHandler` schaltet auf zustellung: ROT (MBtn@66095). GEFANGEN.
- M19 Wurzel `switchTab` leitet wetter auf zustellung um: ROT. GEFANGEN (der Wächter wirkt auch an der gemeinsamen Stelle, nicht nur am Knopf).
- M13 Zeile 781 Ziel `zustellung`: Wächter GRÜN. ÜBERLEBT: Zeile 781 liegt im Schritt Etappen (Zweig `etDone`, Knopf „Wetter direkt"), nicht im Wegpunkte-Schritt; der Wächter ist dafür nicht zuständig. Gegenprobe über den vollen Kern-Lauf: Zeile 781 und die Handy-Entsprechung Zeile 1205 gleichzeitig auf `zustellung`: 8380 Tests, 0 fail. ÜBERLEBT (F017).
Zufallstreffer-Prüfung: die rote Meldung nennt jedes Mal den betroffenen Knopf und das tatsächliche Ziel; kein Treffer durch Fehlinterpretation (jede Mutation mit benannter Datei, kein Ordner-Argument).

Kontrolle F012/F013 (Mutation, danach cmp identisch): M6 `alarmeHydrated` aus `frontend/src/lib/components/compare/CompareTabs.svelte:827` entfernt: `s3a2794_zustellung_vergleich_mount_hydration.test.ts` 2 von 3 rot. M10 CorridorEditor in `frontend/src/lib/components/trip-detail/TripTabs.svelte:223` entfernt: `s3a2794_trip_hub_wetter_wertebereiche.test.ts` 3 von 5 rot. Beide Wächter bleiben wirksam.

F016: Kommentar in `frontend/e2e/kontrast-trip-vergleich.spec.ts:9` nennt jetzt „Wetter/Zustellung (#2794)". Behoben. Messung `tripReiter` (Zeile 222) unverändert, Position 1 und 2.

Finding:
  ID: F017
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:781
  Description: Der Knopf „Wetter direkt" im Schritt Etappen (Desktop Zeile 781, Handy Zeile 1205) ruft `makeEtappenContinueHandler(wetter)`. Wird das Ziel auf `zustellung` gestellt, bleibt der volle Kern-Lauf grün (8380 Tests, 0 fail).
  Spec requirement: AC-6 — die Anlege-Kette des Trips führt Route, Etappen, Wegpunkte, Wetter, Zustellung; kein Schritt führt auf einen falschen Reiter.
  Conflict: Gleiche Lücke wie F015, nur im Nachbarschritt: der Nutzer überspringt Wetter ohne Hinweis. Der Alt-Test prüft nur „existierender Reiter".
  Remediation: Den neuen Wächter auf den Zweig `activeTab === etappen` erweitern (Knopf mit `etDone`, Desktop und Handy) und `activeTab === wetter` erwarten.

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:817
  Evidence: Wegpunkte-Schritt: alle Weiter-Knöpfe (813, 817, 830, 834, Handy 1213/1214) führen auf wetter; Wächter fängt M11, M14 bis M19. Einschränkung F017.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80
  Evidence: Wurzel `.mtabbar` unverändert gegenüber Runde 10.
  Status: CONFIRMED

### Runde 12
**Adversary:**
Zweite Runde, bewusst skeptisch gegen Runde 11 (dort stützte ich die Aussage „Wächter wirkt" auf Mutationen am Knopf). Gegenfrage: sehen die Wächter die Wirkung auch dort, wo der Nutzer sie erreicht, und sind die Pflichtdateien weiter unverändert? Voller Kern-Lauf ohne Mutation: `cd frontend && npm test`, 8380 Tests, 8375 pass, 0 fail, 5 skip (Alt-Skips); Ausgabe in `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Der Zuwachs von 8379 auf 8380 ist genau der neue F015-Wächter. Die Mutation M13 plus Handy-Entsprechung (voller Lauf, 0 fail) zeigt: der Wächter schützt den Wegpunkte-Schritt vollständig, der Etappen-Schritt bleibt offen (F017). Nutzerwirkung F017: Wetter (Metrik-Auswahl, Wertebereiche) wird übersprungen; Standardwerte bleiben vorbelegt, kein Datenverlust. Alle Mutationen wurden zurückgenommen, `cmp` für `TripNewEditor.svelte`, `CompareTabs.svelte` und `TripTabs.svelte` gegen die Sicherungskopien identisch; unstaged Diff des Produktionscodes leer.

Dateien der Pflichtliste, je mit Fundstelle (aktuelle Zeilen):
- Code reference: frontend/playwright.2794-s3a2.staging.config.ts:17 (baseURL Staging; testMatch Zeile 28, nur /e2e-verify)
- Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827 (Mount-Wächter Zustellung)
- Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80 (Leiste)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1 (AST-Helfer der Wächter)
- Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32 (`tailUnlocked`)
- Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99 (Wertebereiche-Speicherer)
- Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99 (`VERSAND_ZIEL`)
- Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24 (Infobox `zustellung`)
- Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126 (Umleitung)
- Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107 (Cooldown-Fix)
- Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86 (`ZUSTELLUNGS_SECTIONS`)
- Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1 (Übergangsreiter)
- Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223 (Wertebereiche im Reiter Wetter; ZustellungTab 226)
- Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:588 (AnlegeReiter; Weiter-Ziele 781, 817, 1205, Handy-Fabrik 284)
- Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35 (`TAIL`)
- Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96 (`TAIL` des Vergleichs)
- Code reference: frontend/src/lib/components/ui/btn/Btn.svelte:74 (`aria-disabled`, #2371)
- Code reference: frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte:30 (`aria-disabled`, #2371)
- Code reference: frontend/src/app.css:366 (Accent-Fläche #2879; Disabled-Stil 443, #2371)
- Code reference: frontend/e2e/kontrast-trip-vergleich.spec.ts:222 (KO-3, Reiter nach Position; Kommentar F016 Zeile 9)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts:25 (F012-Wächter)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts:22 (F013-Wächter)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_wegpunkte_weiter_ziel_wetter.test.ts:84 (F015-Wächter, Messung)

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:284
  Evidence: Handy-Fabrik schaltet auf wetter; Wächter fängt M17.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223
  Evidence: M10 rot (3 von 5), F013 bleibt zu.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T3
  Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827
  Evidence: M6 rot (2 von 3), F012 bleibt zu.
  Status: CONFIRMED

### Runde 13
**Adversary:**
Gegenstand: der neue Sammelwächter `frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts` (Soll-Tabellen Zeile 56 und 93, Messung Zeile 205, Abgleich Zeile 224) gegen F017 und gegen die Spec. Produktionscode seit Runde 12 unverändert (unstaged Diff von `frontend/src` leer).

Soll-Tabelle gegen Spec, nicht gegen den Ist-Stand: AC-6 verlangt die Kette Route, Etappen, Wegpunkte, Wetter, Zustellung (Trip) und Vergleich, Orte, Wetter, Zustellung (Orte). Die Tabelle schreibt Route nach Etappen (Zeile 58), Wegpunkte nach Wetter (Zeile 66, F015), Wetter nach Zustellung (Zeile 69), im Vergleich Vergleich nach Orte, Orte nach Wetter, Wetter nach Zustellung (Zeilen 95 bis 97). Das ist der Nachfolger in der Kette, nicht bloß der Ist-Stand. Zwei Einträge weichen vom reinen Nachfolger ab: „Wetter direkt" im Schritt Etappen (Zeile 63 und 88) zielt auf Wetter statt Wegpunkte. Das deckt die Spec, weil `subscriptionTabs.ts:59` Wegpunkte als `optional: true` führt; im Stand vor dem Umbau (Hauptzweig) zielte derselbe Knopf auf den Vorgänger-Reiter `wetter-metriken` (umbenannt zu `wetter`), die Semantik ist also unverändert. Der Eintrag „Zustellung einrichten" (Zeile 69) ersetzt die entfallenen Knöpfe auf `wertebereiche` und `alarme` und führt auf den einzigen Folgeschritt. Kein Soll-Ziel führt auf einen entfallenen Reiter.

F017 geschlossen. Mutationen (String-Ersetzung per Hilfsskript, Sicherungskopien `TNE.svelte`, `CNE.svelte`, `tnl.ts`, `st.ts` vorher im Scratchpad, nur die benannte Wächterdatei):
- M1 `TripNewEditor.svelte:781` Ziel `zustellung`: ROT („Trip etappen#0 Knopf 4 … Ergebnis 'zustellung', Soll 'wetter'"). GEFANGEN.
- M2 `TripNewEditor.svelte:1205` (Handy-Fuß): ROT („etappen#2 Knopf 2"). GEFANGEN.
- M11 Knopf 781 wirkungslos (`() => {}`): ROT („bleibt"). GEFANGEN. Die Prüfung geschieht an der Wirkung (Instanz-Skript wird ausgeführt), nicht am Quelltext.
- M12 `CompareNewEditor.svelte:539` „Zustellung einrichten" zielt auf `wetter`: ROT („bleibt"). GEFANGEN.
- M6 `CompareNewEditor.svelte` `handleMobileNext` springt zwei Schritte: ROT („vergleich#2 … Ergebnis 'wetter', Soll 'orte'"). GEFANGEN, also auch an der gemeinsamen Stelle, die Handy-Fuß und Sticky-Knöpfe teilen.
Zählung je Zweig und Zweig-Liste (Zeilen 231 bis 242) sind festgeschrieben; ein neuer oder entfallener Knopf wird rot.

Aktive Suche nach Lücken, die der Wächter strukturell nicht sieht (Navigation, die nicht über einen onclick in einem Schritt-Zweig läuft):
- Schrittleiste: `<AnlegeReiter onWahl=…>` (Trip `TripNewEditor.svelte:588` Desktop, 934 Handy; Vergleich 482, 570) liegt außerhalb der Schritt-Zweige. M3 `makeTabHandler` springt immer auf `zustellung`: Wächter plus fünf Anlege-Tests (44 Tests) GRÜN. M8 dieselbe Umleitung in `makeTabHandler` des Vergleichs: GRÜN. ÜBERLEBT (F018).
- Sperr-Logik: M5 (Trip, `makeMobileTabHandler` ohne Sperre) GRÜN, M7 (Vergleich, `switchTab` ohne `unlocked`-Prüfung) GRÜN. Die Sperr-Berechnung selbst (`tailUnlocked`, `unlockedTabs`) hat eigene Tests; die Verdrahtung Handler zu Sperre hat in der Kern-Schicht keinen. Kein Gegenstand dieser Spec (Sperr-Verhalten ist #661, unverändert).
- Prop-Navigation `onJump`: M4 `onVersandJump` springt auf `wetter` statt `etappen`: GRÜN. Der Sprung gehört zum Knopf „Etappen öffnen" in `VersandTab.svelte:309`, im Anlege-Fluss nicht als Zielwert der Spec benannt (AC-6 nennt nur die Reihenfolge der Schritte).
- Knöpfe im Schleifenkontext (je Etappe, je Profil): sie lassen sich nicht ausführen und werden nur dann akzeptiert, wenn der onclick keinen Wechsler nennt (Zeile 217). M10 `makeGpxRemoveHandler` ruft zusätzlich `switchTab('zustellung')`: GRÜN. ÜBERLEBT (F019), weil der Ausdruck `makeGpxRemoveHandler(stage.id)` keinen Wechsler nennt; der Wechsler steckt im Handler-Rumpf.

Bewertung: F018 und F019 betreffen keine Zusicherung der Spec. AC-6 verlangt die Schritt-Reihenfolge und dass kein Schritt auf einen entfallenen Reiter führt; beides sichert `s3a2794_reiter_definition.test.ts` (Kette aus einer Quelle) plus der neue Wächter für jeden Weiter-Knopf. Der Leisten-Klick ist in der Playwright-Schicht erfasst (mehrere Specs klicken `trip-new-tab-*` und `compare-editor-tab-*` und prüfen den Inhalt, u. a. `hub-anlegen-ablauf.spec.ts`), läuft aber erst in CI-e2e und /e2e-verify. Beide als LOW.

Finding:
  ID: F018
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:239
  Description: `makeTabHandler` (Trip) und `makeTabHandler` (Vergleich, `CompareNewEditor.svelte:280`) sowie die Sperrprüfung in `switchTab` des Vergleichs und `makeMobileTabHandler` des Trips sind in der Kern-Schicht nicht gemessen. Umleitung aller Leistenklicks auf `zustellung` (M3, M8) und Entfernen der Sperrprüfung (M5, M7) lassen die Kern-Läufe grün.
  Spec requirement: AC-6 (Kette der Schritte, kein Schritt auf falschem Reiter); die Leiste selbst nur über Playwright belegt.
  Conflict: Kein Widerspruch zur Spec; reine Härtungslücke in der Kern-Schicht, Playwright deckt den Klickpfad.
  Remediation: Optional den Sammelwächter um einen Lauf erweitern, der `makeTabHandler(id)` für jede Kennung der Kette gegen das Instanz-Skript misst (Ziel = Kennung, gesperrt = bleibt).

Finding:
  ID: F019
  Severity: LOW
  Category: anti_pattern
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts:217
  Description: Knöpfe im Schleifenkontext werden bei Ausführungsfehler als „ohne-navigation" akzeptiert, sofern der onclick-Text keinen Wechsler nennt; ein Wechsler im Rumpf der Fabrik (M10) bleibt unsichtbar.
  Spec requirement: AC-6 — kein Schritt führt auf einen falschen Reiter.
  Conflict: Kein Spec-Bezug (ein Entfernen-Knopf, der navigiert, wäre ein Fremdfehler, den Nutzertests sehen); Messlücke des Wächters.
  Remediation: Optional Schleifenkontext mit einer Beispiel-Etappe belegen und die Knöpfe ausführen, oder die Fabrik-Rümpfe per AST auf `switchTab` prüfen.

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts:56
  Evidence: Soll-Tabelle entspricht der Kette der Spec (nicht nur dem Ist-Stand); M1, M2, M6, M11, M12 rot.
  Status: CONFIRMED

### Runde 14
**Adversary:**
Zweite Runde, skeptisch gegen Runde 13: stimmen die Aussagen „Wächter wirkt" und „Produktionscode unverändert"? Voller Kern-Lauf ohne Mutation, `cd frontend && npm test`: 8382 Tests, 8377 pass, 0 fail, 5 skip (Alt-Skips). Zuwachs 8380 auf 8382 sind die zwei Tests des neuen Sammelwächters (Zeilen 252 und 271, Trip und Vergleich). Ausgabe in `docs/artifacts/feature-2794-s3a-teil2-leiste/adversary-test-output.txt`. Alle Mutationen zurückgenommen: `cmp` von `TripNewEditor.svelte`, `CompareNewEditor.svelte`, `tripNewLogic.ts`, `subscriptionTabs.ts` gegen die Sicherungskopien identisch; unstaged Diff von `frontend/src` leer.

Zufallstreffer-Prüfung der roten Mutationen: jede rote Meldung nennt den betroffenen Knopf, den Zweig-Schlüssel und das tatsächliche Ziel (z. B. „Trip etappen#0 Knopf 4 … Ergebnis 'zustellung', Soll 'wetter'"); kein Treffer durch Aufbaufehler (Messaufbau-Assertions Zeilen 261 und 280 grün). Testdaten und Prüfling stimmen überein: der Wächter wertet die echte Instanz aus, nicht einen Spiegel; Verschiedenheit wird geprüft (Ziel gegen Soll je Knopf, nicht nur Vorhandensein).

Pflichtliste aus Runde 12, je mit aktueller Fundstelle:
- Code reference: frontend/playwright.2794-s3a2.staging.config.ts:17 (baseURL Staging; testMatch Zeile 28, nur /e2e-verify)
- Code reference: frontend/src/lib/components/compare/CompareTabs.svelte:827 (Mount-Wächter Zustellung)
- Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80 (Leiste)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts:1 (AST-Helfer)
- Code reference: frontend/src/lib/components/shared/anlegeLockEngine.ts:32 (`tailUnlocked`)
- Code reference: frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts:99 (Wertebereiche-Speicherer)
- Code reference: frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:99 (`VERSAND_ZIEL`)
- Code reference: frontend/src/lib/components/shared/infoboxKeys.ts:24 (Infobox `zustellung`)
- Code reference: frontend/src/lib/components/shared/subscriptionTabs.ts:126 (Umleitung)
- Code reference: frontend/src/lib/components/shared/versandVergleichSpeicherung.ts:107 (Versand-Snapshot; Cooldown-Felder 97 und 120)
- Code reference: frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts:86 (`ZUSTELLUNGS_SECTIONS`)
- Code reference: frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte:1 (Übergangsreiter)
- Code reference: frontend/src/lib/components/trip-detail/TripTabs.svelte:223 (Wertebereiche im Reiter Wetter; ZustellungTab 226)
- Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:588 (AnlegeReiter; Weiter-Ziele 781, 817, 1205, Handy-Fabrik 285)
- Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35 (`TAIL`)
- Code reference: frontend/src/lib/components/compare-new/CompareNewEditor.svelte:96 (`TAIL` des Vergleichs)
- Code reference: frontend/src/lib/components/ui/btn/Btn.svelte:74 (`aria-disabled`, #2371)
- Code reference: frontend/src/lib/components/shared/StandardwerteSpeichernKnopf.svelte:30 (`aria-disabled`, #2371)
- Code reference: frontend/src/app.css:366 (Accent-Fläche #2879; Disabled-Stil 443)
- Code reference: frontend/e2e/kontrast-trip-vergleich.spec.ts:222 (KO-3, Reiter nach Position)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts:53 (F012-Wächter)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_trip_hub_wetter_wertebereiche.test.ts:37 (F013-Wächter)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_wegpunkte_weiter_ziel_wetter.test.ts:68 (F015-Wächter, Messung Zeile 84)
- Code reference: frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts:205 (neuer Sammelwächter; Soll-Tabellen 56 und 93, Abgleich 224)

Gegenprobe Überlappung: der ältere F015-Wächter bleibt neben dem Sammelwächter bestehen und ist durch ihn nicht ersetzt, aber doppelt gedeckt. Kein Konflikt. Einschränkung unverändert: Browserhälfte von AC-3, AC-4, AC-7, AC-8, AC-36 und das Leisten-Klickverhalten laufen erst in /e2e-verify (Staging-Specs `s3a2794-hub-reiter-wetter-zustellung`, `s3a2794-zustellung-inventar-speicherweg`).

Confirmation:
  AC: AC-6
  Code reference: frontend/src/lib/components/trip-new/TripNewEditor.svelte:781
  Evidence: „Wetter direkt" (781, Handy 1205) führt auf `wetter`; Wächter fängt M1, M2, M11. F017 zu.
  Status: CONFIRMED

Confirmation:
  AC: AC-2.T4
  Code reference: frontend/src/lib/components/trip-new/tripNewLogic.ts:35
  Evidence: Kette `TAIL` unverändert; Kern-Lauf 0 fail.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/mobile/MTabBar.svelte:80
  Evidence: Wurzel `.mtabbar` unverändert; Kern-Wächter grün.
  Status: CONFIRMED

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

F017 ist geschlossen: der Sammelwächter fängt die Umstellung von „Wetter direkt" auf Desktop und Handy (M1, M2, M11) sowie falsche Ziele im Vergleich (M6, M12) an der Wirkung. Die Soll-Tabelle bildet die Kette aus AC-6 ab (Route, Etappen, Wegpunkte, Wetter, Zustellung bzw. Vergleich, Orte, Wetter, Zustellung), nicht nur den Ist-Stand; „Wetter direkt" überspringt den laut Spec optionalen Schritt Wegpunkte. Offen sind zwei LOW-Härtungswünsche ohne Spec-Bezug: F018 (Schrittleisten-Klick und Sperr-Verdrahtung in der Kern-Schicht nicht gemessen, Playwright deckt den Klickpfad) und F019 (Knöpfe im Schleifenkontext: Wechsler im Fabrik-Rumpf unsichtbar).
Tests: 8382 gelaufen, 8377 passed, 0 failed, 5 skipped (Alt-Skips).
Mutationen: M1, M2, M6, M11, M12 rot; M3, M4, M5, M7, M8, M10 überleben (F018, F019, beide LOW). Wiederherstellung per cmp identisch, Produktionscode-Diff unverändert.
Checklist: alle ACs belegt (AC-1 bis AC-8, AC-36, AC-2.T1 bis AC-2.T4); Staging-Lauf in /e2e-verify bleibt Pflicht (Browserhälfte AC-3/4/7/8/36).

## Geprüfte Dateien

- sha256:038908372b2a8eb1ebbc0bc2d807fbc889cb2315e7eca7fb3c7a3f66e4438d9d  frontend/e2e/kontrast-trip-vergleich.spec.ts
- sha256:f4404bbb928e7b8a093569d6e36075525b1d1187df6b5a945bbd9d0db49ef26f  frontend/e2e/layout-tab-vergleich.spec.ts
- sha256:3cbe0326956c7ed61c717102db9bd8d8e018ee6bc6911fdcdfb9e7ca0ec47e2f  frontend/playwright.2794-s3a2.staging.config.ts
- sha256:27c29d562e09a0a5e94ec41903e7e7a482d3932de05fde740513edcaf79fd62c  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- sha256:bbfaf4f52c4a3ef2c74749c4528f9fafc283d87788800b22004503614bedeebe  frontend/src/lib/components/compare/CompareTabs.svelte
- sha256:285c73ed2f6ada1f178452017f5765a1f27c08a8add0bf5a0cbb2397b99daa37  frontend/src/lib/components/mobile/MTabBar.svelte
- sha256:178d1dc1259b4d77cca02c7394db6ef45cd70b7d420779a9b5536a5cddb6b0cc  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- sha256:43b01a03c27bae54419b1f5aa0426382cdc00fe88af206c1f760f1bedc44f3a0  frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts
- sha256:8d044031675ac177bace2ae4792df7238e207b54eaef3fbc38de68298a89c2f5  frontend/src/lib/components/shared/anlegeLockEngine.ts
- sha256:76576f7305e7d4c5b6c85227da7f9bb4e3e8092c2024175a7696f7f3a78c950b  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- sha256:868fe1fa658733d8fd0f717ef87bc267e910b05f6a9f767d20750bbbf7a30afb  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- sha256:282fb7b279ce1c3c6fa210ad5dfbad3583523579330e027e919570da88f08eaa  frontend/src/lib/components/shared/infoboxKeys.ts
- sha256:bce62d1fb18c247eda6fbdc863b0bb6d2d5c73a7dfa09c5da66ba217ef269daf  frontend/src/lib/components/shared/subscriptionTabs.ts
- sha256:a1dd5f7c24c8d8c3cabee7d31f938bdc28d94416a097c9c892e778970ec0b34b  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- sha256:5db767f42779d23556a4e9658e28f58b4bedf32d24714d45fcdcd35871573994  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts
- sha256:a6bfa6551df1c1ed71f2d36f4d00c4c489130c937410e76c0fa8d43f22ac5f94  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- sha256:0f1598b1a4a62f1a9f40b7211c9193a87a45ceb1caaaba1d9931caafb27e3aa9  frontend/src/lib/components/trip-detail/TripTabs.svelte
- sha256:710ac159c6c60d7e716f8f6847d18f500ad8f47108e3fc56de977a0185628dc1  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- sha256:00ef7997c0bffe85408e3b07470b186e055cedb436b021e5594e9898a9f453c3  frontend/src/lib/components/trip-new/tripNewLogic.ts

## Prüfbasis

- base: ae02a35165c3fcfa1d25077a145a2a5fc96ee2ca
- blob:3b6397d08916b67c2155a3984534b1d3380b7723  frontend/e2e/kontrast-trip-vergleich.spec.ts
- blob:1df10bc9056acedcd3d8eab6519ae16db762d7d4  frontend/e2e/layout-tab-vergleich.spec.ts
- blob:471411928f4486a9e08e868866d5e08a3030e333  frontend/playwright.2794-s3a2.staging.config.ts
- blob:5892c1ae784fcb62a4058df9741ed1ebbf1f1af6  frontend/src/lib/components/compare-new/CompareNewEditor.svelte
- blob:71c0af6a4061a9854dfd61e1b9c6204af3f173d5  frontend/src/lib/components/compare/CompareTabs.svelte
- blob:65212b90dfda6706677c5e00eb8080e3c5327fd9  frontend/src/lib/components/mobile/MTabBar.svelte
- blob:4c7bd19ead17e938fcb21dcbe9e7262f45fa3f74  frontend/src/lib/components/shared/__tests__/s3a2794Ast.ts
- blob:b1dd01780f359d495e7c06602c704ca4d26fdb90  frontend/src/lib/components/shared/__tests__/s3a2794_anlege_weiter_ziele.test.ts
- blob:83978d969ee6aededb6793c5d8c89261bc28ab2e  frontend/src/lib/components/shared/anlegeLockEngine.ts
- blob:0d940debc060efcfb12fbe2a1bbf4066f218b5c2  frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
- blob:bd7d033554ffc068e7cc979b48e2d1e0cfc76cf5  frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts
- blob:2b203ead7f7b8115e37f58defe9dcc1d0af68f56  frontend/src/lib/components/shared/infoboxKeys.ts
- blob:b204e3d5f93c3a8afa8d5cbcd6838c0c30f43d17  frontend/src/lib/components/shared/subscriptionTabs.ts
- blob:9bb7efeef0222a316a4e98fa2ec1809532c79096  frontend/src/lib/components/shared/versandVergleichSpeicherung.ts
- blob:ce21f922eb742985086b882619c1120c5f87d5bf  frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts
- blob:deea933481ef4eb66cc4c297aae5f4b829e9aa3b  frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte
- blob:c9ec4c9920bdde84b987eea0da1f1865a3c922bf  frontend/src/lib/components/trip-detail/TripTabs.svelte
- blob:204f3f1215408da77bcd073df8ab43aa0dbd2ff0  frontend/src/lib/components/trip-new/TripNewEditor.svelte
- blob:39e7c396b5711cf5cb726bfb924a6c31758609ca  frontend/src/lib/components/trip-new/tripNewLogic.ts
