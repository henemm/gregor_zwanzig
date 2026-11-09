// TDD RED — Issue #2794 S3a, Teil-PR 2: Umleitung alter Adressen (AC-5).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-5 (Kern-Schicht: resolveTab,
// bereinigteTabAdresse, versandSprungStart) plus der ECHTE Hub (TripTabs/CompareTabs) im
// Instanz-Pruefstand (Muster hub_reiter_gemeinsame_aufloesung.test.ts): welcher Reiter
// aktiv wird und was der Hub in die Adresszeile schreibt.
//
// „Anker gewinnt gegen Reiterkennung" (Spec §1): `?tab=wetter-metriken#versand` landet in
// `zustellung` mit Anker `versand`. Gemessen am echten Hub mit `window.location.hash`, damit
// die Zusicherung nicht an einer bestimmten Funktionssignatur haengt.
//
// RED heute: LEGACY zeigt auf wetter-metriken/wertebereiche; wetter/zustellung sind unbekannt.
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/shared/__tests__/s3a2794_umleitung_alt_kennungen.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from './svelteInstanzPruefstand.ts';
import { vollerVergleich } from './goMergeServerPruefstand.ts';
import { resolveTab, bereinigteTabAdresse, versandSprungStart } from '../subscriptionTabs.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const TRIP_HUB = join(HIER, '..', '..', 'trip-detail', 'TripTabs.svelte');
const VERGLEICH_HUB = join(HIER, '..', '..', 'compare', 'CompareTabs.svelte');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type Kind = 'trip' | 'vergleich';

/** Erwartung je Alt-Kennung: [neuer Reiter, Anker]. `punkte` = kind-eigener Punkte-Reiter. */
const ALT: Array<[string, string, 'versand' | null]> = [
	// AC-5 (wörtlich): die fünf alten Kennungen
	['wetter-metriken', 'wetter', null],
	['wertebereiche', 'wetter', null],
	['layout', 'wetter', null],
	['alarme', 'zustellung', null],
	['versand', 'zustellung', 'versand'],
	// Spec §1: übrige Alt-Kennungen auf das passende neue Ziel
	['briefings', 'zustellung', 'versand'],
	['weather', 'wetter', null],
	['alerts', 'wetter', null],
	['idealwerte', 'wetter', null],
	['overview', 'uebersicht', null],
	['preview', 'uebersicht', null],
	['vorschau', 'uebersicht', null],
	['stages', 'punkte', null]
];

const ALLE_ALT = ['wetter-metriken', 'wertebereiche', 'layout', 'alarme', 'versand', 'briefings', 'weather', 'alerts', 'idealwerte', 'overview', 'preview', 'vorschau', 'stages'];

const punkte = (kind: Kind) => (kind === 'trip' ? 'etappen' : 'orte');
const ziel = (kind: Kind, z: string) => (z === 'punkte' ? punkte(kind) : z);

// ── Kern: resolveTab / bereinigteTabAdresse / versandSprungStart ──────────────

for (const kind of ['trip', 'vergleich'] as Kind[]) {
	describe(`AC-5 (${kind}): resolveTab + bereinigteTabAdresse leiten jede Alt-Kennung um`, () => {
		for (const [alt, neu, anker] of ALT) {
			test(`s3a2794_ac5_${kind}_${alt}_wird_${neu}${anker ? '_mit_anker' : ''}`, () => {
				const r = resolveTab(kind, alt);
				assert.equal(r.tab, ziel(kind, neu), `?tab=${alt} → ${r.tab}`);
				assert.equal(r.known, true);
				assert.equal(r.legacy, true, `?tab=${alt} muss als Alt-Kennung gelten (Adresse wird bereinigt)`);
				assert.equal(r.anchor, anker ?? undefined, `?tab=${alt}: Anker`);
				const adr = bereinigteTabAdresse(`http://localhost/x/1?tab=${alt}`, r);
				assert.ok(adr !== null, `?tab=${alt}: Adresse wird nicht bereinigt`);
				const u = new URL(adr!, 'http://localhost');
				assert.equal(u.searchParams.get('tab'), ziel(kind, neu));
				assert.equal(u.hash, anker ? '#versand' : '');
				for (const a of ALLE_ALT) {
					if (a === ziel(kind, neu)) continue;
					assert.ok(!u.search.includes(`tab=${a}`), `bereinigte Adresse ${adr} enthält noch die Alt-Kennung ${a}`);
				}
				assert.equal(versandSprungStart(r), anker ? 1 : 0, `?tab=${alt}: Sprung-Startwert`);
			});
		}

		for (const neu of ['wetter', 'zustellung']) {
			test(`s3a2794_ac5_${kind}_neue_kennung_${neu}_bleibt_unveraendert`, () => {
				const r = resolveTab(kind, neu);
				assert.deepEqual({ tab: r.tab, legacy: r.legacy, known: r.known }, { tab: neu, legacy: false, known: true });
				assert.equal(bereinigteTabAdresse(`http://localhost/x/1?tab=${neu}`, r), null, 'neue Kennung darf die Adresse nicht umschreiben');
			});
		}
	});
}

// ── Echter Hub im Instanz-Pruefstand ─────────────────────────────────────────

let schreibungen: Array<{ url: string; replace: boolean }> = [];
const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

function adresszeile(pfad: string, tab: string | null, hash: string): string {
	schreibungen = [];
	const search = tab === null ? '' : `?tab=${encodeURIComponent(tab)}`;
	const href = `http://localhost${pfad}${search}${hash}`;
	(globalThis as Knoten).window = {
		location: { href, search, pathname: pfad, hash },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = {
		state: null,
		replaceState: (_s: unknown, _t: string, url: string | URL) => schreibungen.push({ url: String(url), replace: true }),
		pushState: (_s: unknown, _t: string, url: string | URL) => schreibungen.push({ url: String(url), replace: false })
	};
	return href;
}

const gotoAufzeichnung = (url: string, opt?: { replaceState?: boolean }) => {
	schreibungen.push({ url: String(url), replace: opt?.replaceState === true });
	return Promise.resolve();
};

async function hubOeffnen(kind: Kind, roh: string | null, hash = ''): Promise<{ u: Knoten; fehler: string[] }> {
	const pfad = kind === 'trip' ? '/trips/t-1' : '/compare/c-1';
	const href = adresszeile(pfad, roh, hash);
	const initialTab = roh ?? undefined;
	const saat: Knoten =
		kind === 'trip'
			? { initialTab, goto: gotoAufzeichnung, page: { url: new URL(href) }, badges: {} }
			: { initialTab, preset: vollerVergleich('c-1'), locations: [], orteCount: 3, goto: gotoAufzeichnung, page: { url: new URL(href) } };
	const { u, ast, quelle } = await umgebungFuer(kind === 'trip' ? TRIP_HUB : VERGLEICH_HUB, saat, { jsAlsTs: true });
	const fehler: string[] = [];
	for (const e of effekteVon(ast, quelle, u, 'initialTab')) {
		try {
			e();
		} catch (err) {
			fehler.push(String(err));
		}
	}
	return { u, fehler };
}

const adr = (url: string) => new URL(url, 'http://localhost/x');

for (const kind of ['trip', 'vergleich'] as Kind[]) {
	const hub = kind === 'trip' ? 'TripTabs' : 'CompareTabs';

	describe(`AC-5 (${hub}): der echte Hub öffnet den neuen Reiter und bereinigt die Adresszeile einmal`, () => {
		for (const [alt, neu, anker] of ALT) {
			test(`s3a2794_ac5_hub_${kind}_${alt}_oeffnet_${neu}`, async () => {
				const { u, fehler } = await hubOeffnen(kind, alt);
				assert.equal(u.activeTab, ziel(kind, neu), `${hub}: ?tab=${alt} öffnet '${String(u.activeTab)}'; Effekt-Fehler ${JSON.stringify(fehler)}`);
				assert.equal(schreibungen.length, 1, `genau EINE Adresszeilen-Schreibung erwartet: ${JSON.stringify(schreibungen)}`);
				assert.equal(schreibungen[0].replace, true, 'kein zusätzlicher Verlaufseintrag');
				assert.equal(adr(schreibungen[0].url).searchParams.get('tab'), ziel(kind, neu));
				assert.equal(adr(schreibungen[0].url).hash, anker ? '#versand' : '');
			});
		}

		test(`s3a2794_ac5_hub_${kind}_anker_versand_gewinnt_gegen_wetter_metriken`, async () => {
			// routes/compare/[id]/+page.svelte verlinkte bisher `?tab=wetter-metriken#versand`.
			const { u, fehler } = await hubOeffnen(kind, 'wetter-metriken', '#versand');
			assert.equal(u.activeTab, 'zustellung', `${hub}: ?tab=wetter-metriken#versand öffnet '${String(u.activeTab)}' (Anker muss gewinnen); ${JSON.stringify(fehler)}`);
			assert.ok(schreibungen.length >= 1, 'Adresszeile wird nicht bereinigt');
			const letzte = adr(schreibungen[schreibungen.length - 1].url);
			assert.equal(letzte.searchParams.get('tab'), 'zustellung');
			assert.equal(letzte.hash, '#versand');
			assert.ok(Number(u.versandSprung) >= 1, 'Sprung zum Versand-Abschnitt wird nicht ausgelöst');
		});

		for (const neu of ['wetter', 'zustellung']) {
			test(`s3a2794_ac5_hub_${kind}_neue_kennung_${neu}_ohne_umschreibung`, async () => {
				const { u } = await hubOeffnen(kind, neu);
				assert.equal(u.activeTab, neu);
				assert.deepEqual(schreibungen, [], 'neue Kennung darf die URL nicht umschreiben');
			});
		}
	});
}
