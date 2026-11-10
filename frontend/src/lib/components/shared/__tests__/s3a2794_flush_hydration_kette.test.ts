// TDD RED — Issue #2794 S3a, Teil-PR 2: Sichern beim Reiterwechsel, Vergleichs-Hydration,
// Anlege-Ketten-Logik.
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-2.T3, AC-6 (Logik-Anteil), §5, §6
//
// Gemessen wird, was der Code TUT (keine Quelltext-Suche):
//   - Trip-Hub (TripTabs.svelte) und Vergleichs-Hub (CompareTabs.svelte) im Instanz-Pruefstand
//     (Muster hub_reiter_gemeinsame_aufloesung.test.ts): Reiterwechsel weg von `wetter` bzw.
//     `zustellung` mit ausstehender Speicherung flusht VOR dem Wechsel (echter SaveStatus-Controller).
//   - SELBST_SPEICHERNDE_VERGLEICH_REITER + sichereSelbstSpeichererVorReiterwechsel (echte Funktion).
//   - Lazy-Hydration des Vergleichs: die echten $effect-Rumpfe von CompareTabs laufen mit
//     `activeTab = 'wetter'` bzw. `'zustellung'`; danach muessen die Hydrations-Flags der dort
//     gezeigten Bausteine gesetzt sein (sonst zeigt der Reiter Standard- statt gespeicherter Werte).
//   - anlegeLockEngine.canFinish (letzterId), tripNewLogic PROGRESS_STEPS/canSave, infoboxKey.
//
// RED heute: `wetter`/`zustellung` sind keine Reiter; die Listen/Effekte haengen an den alten Kennungen.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_flush_hydration_kette.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';
import { createController } from './versandVergleichPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';
import { subscriptionTabs } from '../subscriptionTabs.ts';
import {
	SELBST_SPEICHERNDE_VERGLEICH_REITER,
	sichereSelbstSpeichererVorReiterwechsel
} from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { canFinish } from '../anlegeLockEngine.ts';
import { infoboxKey } from '../infoboxKeys.ts';
import { PROGRESS_STEPS, canSave } from '../../trip-new/tripNewLogic.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const TRIP_HUB = join(HIER, '..', '..', 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type Kind = 'trip' | 'vergleich';

const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function adresszeile(pfad: string, tab: string): string {
	const href = `http://localhost${pfad}?tab=${tab}`;
	(globalThis as Knoten).window = {
		location: { href, search: `?tab=${tab}`, pathname: pfad, hash: '' },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = { state: null, replaceState() {}, pushState() {} };
	return href;
}

const gotoStumm = () => Promise.resolve();

async function hubOeffnen(kind: Kind, tab: string, extra: Knoten = {}): Promise<{ u: Knoten; ast: Knoten; quelle: string; fehler: string[] }> {
	const pfad = kind === 'trip' ? '/trips/t-1' : '/compare/c-1';
	const href = adresszeile(pfad, tab);
	const saat: Knoten =
		kind === 'trip'
			? { initialTab: tab, goto: gotoStumm, page: { url: new URL(href) }, badges: {}, ...extra }
			: { initialTab: tab, preset: vollerVergleich('c-1'), locations: [], orteCount: 3, goto: gotoStumm, page: { url: new URL(href) }, ...extra };
	const { u, ast, quelle } = await umgebungFuer(kind === 'trip' ? TRIP_HUB : VERGLEICH_HUB, saat, { jsAlsTs: true });
	const fehler: string[] = [];
	for (const e of effekteVon(ast, quelle, u, 'initialTab')) {
		try {
			e();
		} catch (err) {
			fehler.push(String(err));
		}
	}
	return { u, ast, quelle, fehler };
}

function ausstehend(): { ctl: ReturnType<typeof createController>; laeufe: () => number } {
	const ctl = createController('s3a2794-guard');
	let n = 0;
	ctl.schedule(async () => {
		n += 1;
	}, 60_000);
	return { ctl, laeufe: () => n };
}

// ── AC-2.T3: Flush beim Reiterwechsel ────────────────────────────────────────

for (const kind of ['trip', 'vergleich'] as Kind[]) {
	const hub = kind === 'trip' ? 'TripTabs' : 'CompareTabs';
	describe(`AC-2.T3 (${hub}): Wechsel weg von wetter/zustellung sichert ausstehende Änderungen`, () => {
		for (const reiter of ['wetter', 'zustellung']) {
			test(`s3a2794_t3_${kind}_wechsel_aus_${reiter}_flusht_vor_dem_wechsel`, async () => {
				const { ctl, laeufe } = ausstehend();
				const { u, fehler } = await hubOeffnen(kind, reiter, { saveController: ctl });
				assert.equal(u.activeTab, reiter, `Vorbedingung: ${hub} steht im Reiter '${reiter}' (aktiv: ${String(u.activeTab)}); ${JSON.stringify(fehler)}`);
				await (u.handleValueChange as (v: string) => Promise<void>)('uebersicht');
				assert.equal(laeufe(), 1, `${hub}: Flush-Guard greift für '${reiter}' nicht — Änderung ginge beim Wechsel verloren`);
				assert.equal(u.activeTab, 'uebersicht');
				ctl.cancel?.();
			});
		}

		test(`s3a2794_t3_${kind}_wechsel_aus_uebersicht_flusht_nicht`, async () => {
			const { ctl, laeufe } = ausstehend();
			const { u } = await hubOeffnen(kind, 'uebersicht', { saveController: ctl });
			await (u.handleValueChange as (v: string) => Promise<void>)('wetter');
			assert.equal(laeufe(), 0, 'Gegenprobe: der Guard darf nicht für jeden Reiter flushen');
			ctl.cancel?.();
		});
	});
}

describe('AC-2.T3: SELBST_SPEICHERNDE_VERGLEICH_REITER auf die neuen Kennungen', () => {
	test('s3a2794_t3_liste_enthaelt_wetter_und_zustellung', () => {
		const liste = [...SELBST_SPEICHERNDE_VERGLEICH_REITER] as string[];
		assert.ok(liste.includes('wetter'), `wetter fehlt: ${JSON.stringify(liste)}`);
		assert.ok(liste.includes('zustellung'), `zustellung fehlt: ${JSON.stringify(liste)}`);
	});

	test('s3a2794_t3_liste_fuehrt_nur_bestehende_hub_reiter', () => {
		const hubReiter = subscriptionTabs('vergleich').map((t) => t.id);
		const tot = ([...SELBST_SPEICHERNDE_VERGLEICH_REITER] as string[]).filter((r) => !hubReiter.includes(r));
		assert.deepEqual(tot, [], `Kennungen ohne Reiter in der Liste (tote Einträge): ${tot.join(', ')}`);
	});

	for (const reiter of ['wetter', 'zustellung']) {
		test(`s3a2794_t3_generischer_guard_flusht_aus_${reiter}`, async () => {
			const { ctl, laeufe } = ausstehend();
			await sichereSelbstSpeichererVorReiterwechsel(reiter, 'uebersicht', ctl);
			assert.equal(laeufe(), 1, `Wechsel aus '${reiter}' flusht nicht`);
		});
	}
});

// ── AC-2.T3: Lazy-Hydration des Vergleichs an wetter/zustellung ──────────────

async function hydrationNach(tab: string): Promise<{ u: Knoten; fehler: string[] }> {
	const { u, ast, quelle, fehler } = await hubOeffnen('vergleich', tab);
	// alle Effekte, die `activeTab` nennen (Hydrations-Weichen), einmal laufen lassen
	for (const e of effekteVon(ast, quelle, u, 'activeTab')) {
		try {
			e();
		} catch (err) {
			fehler.push(String(err));
		}
	}
	for (let i = 0; i < 30; i++) await new Promise((r) => setTimeout(r, 0));
	return { u, fehler };
}

describe('AC-2.T3: CompareTabs hydriert die Bausteine des geöffneten Reiters', () => {
	test('s3a2794_t3_positivkontrolle_pruefstand_misst_hydration_alt_link_alarme', async () => {
		// Positivkontrolle (heute UND nach der Umsetzung gruen): `?tab=alarme` oeffnet heute den
		// Reiter alarme, danach (Umleitung) zustellung — beide Male muss die Alarm-Hydration laufen.
		// Bleibt das rot, misst der Pruefstand nichts, und die Faelle unten waeren wertlos.
		const { u, fehler } = await hydrationNach('alarme');
		assert.equal(u.alarmeHydrated, true, `Prüfstand: Alarm-Hydration nicht beobachtbar; ${JSON.stringify(fehler)}`);
	});

	test('s3a2794_t3_hydration_wetter_metriken_layout_und_wertebereiche', async () => {
		const { u, fehler } = await hydrationNach('wetter');
		assert.equal(u.activeTab, 'wetter', `Vorbedingung: Reiter wetter offen (aktiv: ${String(u.activeTab)})`);
		assert.equal(u.wetterMetrikenHydrated, true, `Metrik-Auswahl im Reiter wetter nicht hydriert; ${JSON.stringify(fehler)}`);
		assert.equal(u.layoutHydrated, true, 'Layout-Hydration (Gate der WetterTab-Montage, F012) im Reiter wetter nicht gelaufen');
		// Teil-PR 3: der WetterTab mountet erst, wenn dieses Gate offen ist (AC-38/F012) — das Gate
		// selbst muss nach dem Oeffnen des Reiters wetter offen sein, sonst bliebe der Reiter leer.
		// (Der Pruefstand rechnet $derived nicht nach — das Gate wird mit der echten Gate-Funktion
		// des Hubs aus den hydrierten Flags bestimmt.)
		const gate = (u.wetterMetrikenHydrationAbgeschlossen as (f: object) => boolean)({ wetterMetrikenHydrated: u.wetterMetrikenHydrated, layoutHydrated: u.layoutHydrated });
		assert.equal(gate, true, 'Gate wetterMetrikenLayoutHydrationBereit nach Hydration im Reiter wetter zu (WetterTab erschiene nie)');
		assert.equal(u.idealwerteHydrated, true, 'Wertebereiche-Feldsatz unter Wetter nicht hydriert');
	});

	test('s3a2794_t3_hydration_zustellung_versand_alarme_und_wmt', async () => {
		const { u, fehler } = await hydrationNach('zustellung');
		assert.equal(u.activeTab, 'zustellung', `Vorbedingung: Reiter zustellung offen (aktiv: ${String(u.activeTab)})`);
		assert.equal(u.versandHydrated, true, `Versand-Abschnitt im Reiter zustellung nicht hydriert; ${JSON.stringify(fehler)}`);
		assert.equal(u.alarmeHydrated, true, 'AlarmeTab im Reiter zustellung nicht hydriert');
		assert.equal(u.wetterMetrikenHydrated, true, 'WMT (bereich=zustellung) ohne hydrierte Metrik-Auswahl gemountet');
		assert.equal(u.layoutHydrated, true, 'Layout je Kanal / Ausblick / Stundenverlauf im Reiter zustellung nicht hydriert');
	});
});

// ── AC-6 / §5: Anlege-Ketten-Logik ──────────────────────────────────────────

describe('AC-6: Anlegen endet mit dem Schritt zustellung', () => {
	test('s3a2794_ac6_lock_engine_letzter_schritt_ist_zustellung', () => {
		assert.equal(canFinish(new Set(['zustellung'])), true, 'canFinish: Besuch von zustellung schaltet Speichern nicht frei');
		assert.equal(canFinish(new Set(['alarme'])), false, 'canFinish: die entfallene Kennung alarme schaltet noch frei');
	});

	test('s3a2794_ac6_trip_progress_steps_ohne_entfallene_schritte', () => {
		assert.deepEqual([...PROGRESS_STEPS], ['route', 'etappen', 'wetter', 'zustellung']);
	});

	test('s3a2794_ac6_trip_speichern_frei_nach_zustellung', () => {
		assert.equal(canSave(new Set(['route', 'etappen', 'wetter', 'zustellung']) as never), true);
		assert.equal(canSave(new Set(['route', 'etappen', 'wetter']) as never), false, 'Speichern frei, obwohl zustellung nicht besucht');
	});

	test('s3a2794_ac6_infobox_schluessel_fuer_neue_kennungen', () => {
		for (const ctx of ['route', 'vergleich'] as const) {
			for (const reiter of ['wetter', 'zustellung']) {
				assert.ok(
					(infoboxKey as (c: string, r: string) => string | undefined)(ctx, reiter),
					`infoboxKey(${ctx}, ${reiter}) fehlt — Anlege-Schritt ohne Infobox`
				);
			}
		}
	});
});
