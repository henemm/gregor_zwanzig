// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-3: die beiden Katalog-
// Ladevorgänge (Wetter-Metriken-Auswahl, Stundenverlauf/Ausblick) schließen zu
// unterschiedlichen Zeitpunkten ab — solange nicht BEIDE fertig sind, darf die
// kombinierte Orchestrierung weder erzeugt werden noch einen PUT auslösen.
// Wird sie erzeugt, sobald NUR die erste Hydration fertig ist, diffed ihr
// Baseline-Snapshot gegen einen unvollständigen Stand — die SPÄTER
// eintreffende zweite Hydration schreibt danach in denselben Wizard-Zustand
// und erscheint dem Diff-Gate als Nutzeränderung: ein PUT OHNE Nutzergeste.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-3
// Kontext-Dokument Abschnitt 1.2/4.2 (Design-Entscheidung 4: `untrack()`-
// Konstruktion, erst NACH Abschluss BEIDER Katalog-Ladevorgänge).
//
// Da `svelte/server` weder `$effect` noch die `untrack()`-Konstruktion von
// CompareTabs.svelte ausführt (SSR, kein DOM/Reaktivität), ist die konkrete
// Gate-Bedingung ("beide Hydrationen fertig?"), die CompareTabs vor dem
// Erzeugen der Orchestrierung abfragt, als eigenes, exportiertes Prädikat
// testbar zu machen — Muster `wertebereicheVergleichSpeicherungAktiv` (S3):
// die Kontext-/Bereitschaftsprüfung wandert aus der `.svelte`-Datei in eine
// pure Funktion, die hier UND von CompareTabs.svelte verwendet wird.
//
// Zielschnittstelle (existiert noch NICHT → RED):
//
//   frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts
//   wetterMetrikenHydrationAbgeschlossen({
//     wetterMetrikenHydrated: boolean,
//     layoutHydrated: boolean
//   }): boolean
//
// Mutations-Gegenprobe (Spec): Gate nur an `wetterMetrikenHydrated` binden
// (`wetterMetrikenHydrated` statt `wetterMetrikenHydrated && layoutHydrated`)
// ⇒ `{wetterMetrikenHydrated:true, layoutHydrated:false}` liefert `true` ⇒ rot.
//
// Prüfort ≠ Wirkort: dass CompareTabs.svelte die Orchestrierung wirklich erst
// nach diesem Prädikat (und nicht früher) per `untrack()` erzeugt, ist eine
// `.svelte`-Verdrahtungsfrage — dafür zusätzlich ein Verhaltens-Nachweis über
// die reale Orchestrierung (zweiter Testblock unten): wird sie mit einem
// Wizard-Zustand erzeugt, der die zweite Domäne noch NICHT hydriert hat, und
// hydriert die zweite Domäne DANACH nach (wie es bei einer verfrühten
// Erzeugung geschähe), erscheint das dem Diff-Gate als Änderung — das ist der
// konkrete Datenverlust-/Fehlalarm-Mechanismus, den das Prädikat verhindern
// muss.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts

// Issue #3389: der Block „AC-3 (Mechanismus)“ entfiel mit dem toten Wetter-Metriken-Speicherer;
// das lebende Prädikat prüft der Block „AC-3 (Prädikat)“.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { wetterMetrikenHydrationAbgeschlossen } from '../weatherMetricsCompareSave.ts';

describe('AC-3 (Prädikat): das Gate verlangt BEIDE Hydrationen', () => {
	test('nur Wetter-Metriken hydriert → nicht bereit', () => {
		assert.equal(
			wetterMetrikenHydrationAbgeschlossen({ wetterMetrikenHydrated: true, layoutHydrated: false }),
			false
		);
	});

	test('nur Layout hydriert → nicht bereit', () => {
		assert.equal(
			wetterMetrikenHydrationAbgeschlossen({ wetterMetrikenHydrated: false, layoutHydrated: true }),
			false
		);
	});

	test('keine der beiden hydriert → nicht bereit', () => {
		assert.equal(
			wetterMetrikenHydrationAbgeschlossen({ wetterMetrikenHydrated: false, layoutHydrated: false }),
			false
		);
	});

	test('beide hydriert → bereit', () => {
		assert.equal(
			wetterMetrikenHydrationAbgeschlossen({ wetterMetrikenHydrated: true, layoutHydrated: true }),
			true
		);
	});

	test('zeitlich versetzter Abschluss: erst Wetter-Metriken, dann Layout — Gate kippt erst beim ZWEITEN Abschluss', () => {
		const stand = { wetterMetrikenHydrated: false, layoutHydrated: false };
		assert.equal(wetterMetrikenHydrationAbgeschlossen(stand), false, 'noch nichts hydriert');
		stand.wetterMetrikenHydrated = true;
		assert.equal(wetterMetrikenHydrationAbgeschlossen(stand), false, 'erst EINE von zwei Hydrationen fertig');
		stand.layoutHydrated = true;
		assert.equal(wetterMetrikenHydrationAbgeschlossen(stand), true, 'jetzt sind beide fertig');
	});
});
