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

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import {
	erstelleWetterMetrikenVergleichSpeicherung,
	wetterMetrikenHydrationAbgeschlossen
} from '../weatherMetricsCompareSave.ts';
import { createController, hydrierterWs, makePreset } from './wetterMetrikenVergleichPruefstand.ts';

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

describe('AC-3 (Mechanismus): erst NACH bestandenem Gate erzeugt — die spät eintreffende zweite Hydration löst KEINEN PUT aus', () => {
	const PRESET_ID = 'cp-2276-s4-hydration';
	let server: FakeTripServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createFakeTripServer();
		server.install();
	});

	afterEach(() => server.restore());

	const puts = () => server.calls.filter((c) => c.method === 'PUT');

	test('Orchestrierung entsteht ERST wenn wetterMetrikenHydrationAbgeschlossen() true liefert → kein PUT ohne Nutzergeste', async () => {
		const preset = makePreset(PRESET_ID);
		const ws = hydrierterWs(preset);
		// Zustand VOR der zweiten (Layout-)Hydration: wie beim Mount, bevor
		// hydrateLayoutTab() fertig ist — Platzhalter statt Server-Stand.
		ws.hourlyMetricKeys = null;
		ws.outlookMetricKeys = null;
		let hydrationsStand = { wetterMetrikenHydrated: true, layoutHydrated: false };

		let basis = preset;
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();

		// Die Layout-Hydration trifft NACH dem ersten Hydrations-Status ein —
		// korrekt implementiert wird die Orchestrierung ERST danach erzeugt
		// (Design-Entscheidung 4, untrack()-Konstruktion).
		ws.hourlyMetricKeys = ['wind_max_kmh', 'temp_max_c'];
		ws.outlookMetricKeys = ['temp_max_c'];
		hydrationsStand = { wetterMetrikenHydrated: true, layoutHydrated: true };
		assert.equal(wetterMetrikenHydrationAbgeschlossen(hydrationsStand), true, 'Vorbedingung: Gate jetzt erfüllt');

		erstelleWetterMetrikenVergleichSpeicherung({
			client: api,
			wiz: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});

		assert.equal(
			ctl.hasPending,
			false,
			'eine erst nach vollständiger Hydration erzeugte Orchestrierung darf ohne Nutzergeste nichts planen'
		);
		await ctl.flush();
		assert.equal(puts().length, 0, 'die nachgeholte Layout-Hydration allein darf nie einen PUT auslösen');
	});
});
