# Adversary Dialog — fix-2896-kontrast-zierpunkt-avatar
Spec: docs/specs/modules/fix_2896_kontrast_zierpunkt_avatar.md
Datum: 2026-11-09 17:52

## Checkliste
- [x] **Input:** Nutzer öffnet `/trips/new`, `/compare/new` oder `/archiv` am Desktop (1280 px) bzw. mobil (390x844).
- [x] **Output:** Der Punkt der Wortmarke in der Desktop-Sidebar ist mit mindestens 4,5:1 lesbar. Die Initialen im Konto-Kreis (Mobil-Navigation) und im Konto-Blatt stehen auf dunklerem Orange mit mindestens 4,5:1. Kein Text dort hat die berechnete Farbe `#9a958a` (Regression #2371).
- [x] **Side effects:** Keine. Logo-Punkt wird etwas dunkler, Konto-Kreis dunkleres Orange; Layout und Logik unverändert.
- [x] **AC-1:** Given die Seiten `/trips/new`, `/compare/new` und `/archiv` bei 1280 px Breite mit der Desktop-Sidebar / When der Kontrast des Wortmarken-Punkts (berechnete Textfarbe gegen den effektiven Hintergrund der Sidebar) gemessen wird / Then beträgt er mindestens 4,5:1 und die Farbe ist nicht `#9a958a`.
- [x] **AC-2:** Given das Archiv `/archiv` bei 390x844 mit der Mobil-Navigation und dem Konto-Kreis / When der Kontrast der Avatar-Initialen (`.konto-kreis__avatar`, Textfarbe gegen Hintergrundfarbe) gemessen wird / Then beträgt er mindestens 4,5:1.
- [x] **AC-3:** Given das geöffnete Konto-Blatt (`KontoSheet`) bei 390x844 / When der Kontrast der Avatar-Initialen (`.konto__avatar`) gemessen wird / Then beträgt er mindestens 4,5:1 und entspricht dem Wert des Konto-Kreises (gleicher Grund, ein Muster).
- [x] **AC-4:** Given die dunkle Variante der Wortmarke (`dark`) auf dunklem Grund / When der Kontrast des Punkts (Alpha 0,55 gegen den dunklen Grund gemischt) berechnet wird / Then beträgt er mindestens 4,5:1.
- [x] **AC-5:** Given der Kern-Test für die helle Wortmarke und `BrandUserBadge accent=true` / When Punktfarbe gegen `--g-paper-deep` und `--g-paper` bzw. Initialen gegen den Avatar-Grund berechnet werden / Then liegen alle Werte bei mindestens 4,5:1 (Punkt 4,66 bzw. 5,13; Badge 6,77).
- [x] **AC-6:** Given die Seiten `/trips/new`, `/compare/new` und `/archiv` bei 390x844 (Regression aus #2371) / When jeder sichtbare Textknoten geprüft wird / Then hat kein Textknoten die berechnete Farbe `#9a958a` (außer `::placeholder` und `:disabled`-Inputs), und die bestehenden Prüfungen (gesperrte Tabs, deaktiviertes Speichern, Trip/Compare-Parität) bleiben grün.

## Dialog

### Runde 1
**Adversary:**
Tests (6 benannte Dateien, node --test): 318 pass, 0 fail (adversary-test-output.txt).
Mutations-Gegenprobe (String-Ersetzung, externe Sicherung, danach Byte-Vergleich des Gesamt-Diffs = IDENTICAL, sha256 der 4 Svelte-Dateien OK):
- M1 Punkt hell zurueck auf --g-ink-4: rot (Kern AC-5 x4, f12 Golden, auth Golden). GEFANGEN.
- M2 Alpha dunkel 0,55 -> 0,45: rot (Kern AC-4 x2). GEFANGEN.
- M3 BottomNav-Avatar -> --g-accent: rot (Kern: Kontrast + Ein-Muster). GEFANGEN.
- M4 KontoSheet-Avatar -> --g-accent: rot (Kern). GEFANGEN.
- M5 BrandUserBadge -> --g-accent: rot (Kern). GEFANGEN.
Messort: AC-4/5 messen am gerenderten SSR-Markup (Punkt-Span, Badge) bzw. kompilierten Komponenten-CSS (Avatar) mit Token aus app.css, nicht am Quelltext.
Wirk-Ort: Sidebar rendert Wordmark.svelte -> BrandWordmark (Code reference: frontend/src/lib/components/ui/sidebar/Sidebar.svelte:81, Hintergrund --g-paper-deep Zeile 64ff.), also derselbe Punkt, den der Test rendert. Sidebar-Grund paper-deep -> 4,66:1 gerechnet.
Golden-Dateien: alle 12 Diffs aendern nur die Punktfarbe ink-4 -> ink-3 (per Skript geprueft); f12-SHA-Goldens nachgezogen.
Staging-Spec: Selektoren existieren (desktop-sidebar Sidebar.svelte:64, brand-wordmark BrandWordmark.svelte:47-68, konto-kreis BottomNav.svelte:73, konto-sheet KontoSheet.svelte:50); Messlogik rechnet Alpha/Opacity-Kette wie bisher; AC-3 vergleicht Hintergrund und Farbe von Kreis und Blatt.
**Implementierer:** keine Rueckmeldung (Adversary-Lauf ohne Dialogpartner).

### Runde 2
**Adversary:**
Zweiter Durchgang, gezielt gegen Luecken:
- Code reference frontend/src/lib/brand/BrandWordmark.svelte:34 (inkDot): kein audit:exempt mehr, kein ink-4 mehr in der Datei (grep leer); ink4_waechter gruen.
- Code reference frontend/src/lib/brand/BrandUserBadge.svelte:22 (avatarBg): accent=false bleibt --g-ink, unveraendert.
- Code reference frontend/src/lib/components/ui/sidebar/BottomNav.svelte:165 und KontoSheet.svelte:119: weisser Text (#ffffff) auf #8c3e1a = 7,45:1; beide gleicher Grund (Kern-Test 'ein Muster').
- Code reference frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts:72-73: nur die zwei Wordmark-Hashes erneuert; M1 faellt dort rot, Hashes bewachen also wirklich.
- Code reference frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts:77-125: Test prueft Wert, nicht nur Vorhandensein; Gegenproben (0,45; ink-4) laufen mit.
- Code reference frontend/e2e/ink4-kontrast.staging.spec.ts:131-160: AC-1 auf 3 Seiten bei 1280 px, AC-2/3 bei 390 px; AC-6 ist der unveraenderte Bestand. Nicht lokal ausfuehrbar (Staging), Selektoren/Logik plausibel.
Restrisiken (kein Finding): (a) Staging-Lauf AC-1 nimmt an, dass /compare/new und /trips/new bei 1280 px die Desktop-Sidebar zeigen; wird in /e2e-verify bestaetigt. (b) Alpha-Mischung des dunklen Punkts ist nur im Kern-Test (nicht im Browser) geprueft; die dunkle Variante wird in der Sidebar nicht verwendet. (c) 'zwanzig'-Akzent bleibt laut Spec ausserhalb des Scopes.
Ergebnis: keine Verfaelschung blieb unbemerkt; keine Spec-Verletzung gefunden.

Confirmations (maschinenlesbare Referenzen der oben genannten Prüfstellen):
Code reference: frontend/src/lib/brand/BrandWordmark.svelte:34
Code reference: frontend/src/lib/brand/BrandUserBadge.svelte:22
Code reference: frontend/src/lib/components/ui/sidebar/BottomNav.svelte:165
Code reference: frontend/src/lib/components/ui/sidebar/KontoSheet.svelte:119
Code reference: frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts:72
Code reference: frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts:77
Code reference: frontend/e2e/ink4-kontrast.staging.spec.ts:131
Code reference: frontend/src/lib/components/ui/sidebar/Sidebar.svelte:81
**Implementierer:** keine Rueckmeldung.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
**VERIFIED**

(lokal: AC-4, AC-5; AC-1/2/3/6 Staging-Messlauf offen fuer /e2e-verify). Tests: 318 passed, 0 failed. Mutationen: 5/5 gefangen. Findings: keine.

## Geprüfte Dateien

- sha256:be6a4c42c94673ff73fd76bb5cb94c6611991cf30476de8239949afb5a3277bb  frontend/e2e/ink4-kontrast.staging.spec.ts
- sha256:3864f2cb44e78f8b1f80e11faba3e3adc3c7c08b26f502d4c013a3b08a29681a  frontend/src/lib/brand/BrandUserBadge.svelte
- sha256:902600596c6b31601c262666d9c018649dd6e33966bc364f84fd3c2d108c48d2  frontend/src/lib/brand/BrandWordmark.svelte
- sha256:6e167cd178a3fe5197300c381c06b015797880deb581f49db38fd62a4bb3514a  frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts
- sha256:7c718d9b6abe7893afa6455911424ff519b9f81c53f7ee0a84d7e7f8c8bf565a  frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts
- sha256:ddf9838c6f15a1e40da2f001b59ad605ddf22b3d9f4e553aa8bb7b500278be4b  frontend/src/lib/components/ui/sidebar/BottomNav.svelte
- sha256:2fa088e6f76608623d85fa4297c5c9884ede6abdf9f9cb6c04c6a31066079815  frontend/src/lib/components/ui/sidebar/KontoSheet.svelte
- sha256:310de4e05117a263b56a148329021073fb687d72379e6f2f1a177963c4416a86  frontend/src/lib/components/ui/sidebar/Sidebar.svelte

## Prüfbasis

- base: 6b608f62b980fab01588e8b8372e70b6a4f60fe5
- blob:222fa13bc1639fda531e0b3216673440d9b3d00f  frontend/e2e/ink4-kontrast.staging.spec.ts
- blob:db15b8a26e6908d47e3be1e45743a6536dc26c99  frontend/src/lib/brand/BrandUserBadge.svelte
- blob:c74209fcf8dc8ba4a2da55ff513704d4472fa10d  frontend/src/lib/brand/BrandWordmark.svelte
- blob:386cabd65590a25e37069697aaee03fdce3cd3e5  frontend/src/lib/brand/__tests__/zierpunkt_avatar_kontrast.test.ts
- blob:c97e34862a7ab7b0f142316dd1c67abd9923f94e  frontend/src/lib/components/__tests__/f12_reste_sprache.test.ts
- blob:65705e59c1840983d7e9252568fc20948e197469  frontend/src/lib/components/ui/sidebar/BottomNav.svelte
- blob:df055590ab567ca3f78af96f82d423f17cb3af29  frontend/src/lib/components/ui/sidebar/KontoSheet.svelte
- blob:aa52548f336398b3aefa7b30063e84962811c83d  frontend/src/lib/components/ui/sidebar/Sidebar.svelte
