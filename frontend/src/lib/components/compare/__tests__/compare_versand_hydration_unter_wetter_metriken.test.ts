// TDD RED — Issue #1743 (Spec feat_1743_reiter_aufraeumen §4, AC-3, AC-9): im Ortsvergleich-Hub
// haengen Versand- und Wetter-Hydration beide am Reiter `wetter-metriken`. Wer den Hub mit
// `?tab=wetter-metriken#versand` (oder dem Alt-Link `?tab=versand`) oeffnet, bekommt den
// Versand-Abschnitt mit den GESPEICHERTEN Werten — nie mit Platzhaltern.
//
// Messweise (Muster hub_reiter_gemeinsame_aufloesung.test.ts): das ECHTE Instanz-Skript von
// CompareTabs wird mit gesaetem Vergleich ausgewertet; ausgefuehrt wird der ECHTE
// Versand-Hydrations-Effekt (ausgewaehlt ueber den Aufruf `hydrateVersandFieldsFromPreset`).
// `wizardState` (Import aus `./compareWizardState.svelte`, vom Pruefstand nicht bindbar) wird als
// leeres Objekt gesaet — beobachtet wird, was der Effekt hineinschreibt.
// Zusaetzlich (Template-AST): der Baustein im Panel `wetter-metriken` haengt am Flag
// `versandHydrated` (umschliessender Block oder Prop) — er mountet also erst nach der Hydration.
//
// Grenze: „kein PUT mit Platzhaltern" bei verzoegerter Hydration im Browser misst Playwright (/50);
// der Speicherweg selbst ist in wetter_metriken_versand_panel_speicherung.test.ts bewacht.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei.
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { vollerVergleich } from '../../shared/__tests__/goMergeServerPruefstand.ts';
import { hydrateVersandFieldsFromPreset } from '../../shared/versandVergleichSpeicherung.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const HUB = join(HIER, '..', 'CompareTabs.svelte');
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

/** Vergleich mit gespeicherten Versandwerten, die sich von jedem Platzhalter unterscheiden. */
function gespeicherterVergleich(): Knoten {
	return {
		...vollerVergleich('c-1743'),
		morning_enabled: true,
		morning_time: '05:45:00',
		evening_enabled: true,
		evening_time: '19:15:00',
		send_email: true,
		send_telegram: true,
		send_sms: false
	};
}

async function hubOeffnen(tab: string): Promise<{ u: Knoten; ast: Knoten; quelle: string }> {
	(globalThis as Knoten).window = {
		location: { href: `http://localhost/compare/c-1743?tab=${tab}`, search: `?tab=${tab}`, pathname: '/compare/c-1743', hash: '' },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = { state: null, replaceState() {}, pushState() {} };
	const preset = gespeicherterVergleich();
	return umgebungFuer(
		HUB,
		{
			initialTab: tab,
			preset,
			locations: [],
			orteCount: 3,
			wizardState: {},
			goto: () => Promise.resolve(),
			page: { url: new URL(`http://localhost/compare/c-1743?tab=${tab}`) }
		},
		{ jsAlsTs: true }
	);
}

describe('#1743 AC-9: Versand-Hydration haengt am Reiter wetter-metriken', () => {
	for (const tab of ['wetter-metriken', 'versand']) {
		test(`?tab=${tab}: der Versand-Hydrations-Effekt fuellt die gespeicherten Werte (kein Platzhalter)`, async () => {
			const { u, ast, quelle } = await hubOeffnen(tab);
			assert.equal(u.activeTab, 'wetter-metriken', `Vorbedingung: ?tab=${tab} oeffnet Wetter-Metriken`);
			const effekte = effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset');
			assert.ok(effekte.length >= 1, 'Messaufbau: kein Versand-Hydrations-Effekt gefunden');
			for (const e of effekte) e();
			assert.equal(u.versandHydrated, true, 'die Versand-Hydration laeuft im Reiter wetter-metriken nicht');
			const soll = hydrateVersandFieldsFromPreset(u.currentPreset);
			for (const feld of ['morningEnabled', 'morningTime', 'eveningEnabled', 'eveningTime', 'sendEmail', 'sendTelegram', 'sendSms']) {
				assert.deepEqual(u.wizardState[feld], (soll as Knoten)[feld], `wizardState.${feld} traegt nicht den gespeicherten Wert`);
			}
		});
	}

	test('Gegenprobe: im Reiter Uebersicht wird der Versand nicht hydriert (lazy wie bisher)', async () => {
		const { u, ast, quelle } = await hubOeffnen('uebersicht');
		for (const e of effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset')) e();
		assert.equal(u.versandHydrated, false);
	});
});

// ── Template-AST: der Baustein mountet erst nach der Versand-Hydration ─────────

/** Einbettungen `name` samt umschliessender Knoten. */
function mitVorfahren(knoten: unknown, name: string): Array<{ k: Knoten; vorfahren: Knoten[] }> {
	const treffer: Array<{ k: Knoten; vorfahren: Knoten[] }> = [];
	(function lauf(n: unknown, kette: Knoten[]): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach((x) => lauf(x, kette));
		const k = n as Knoten;
		if (k.type === 'Component' && k.name === name) treffer.push({ k, vorfahren: kette });
		const weiter = typeof k.type === 'string' ? [...kette, k] : kette;
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], weiter);
	})(knoten, []);
	return treffer;
}

describe('#1743 AC-9 (Template): der Baustein im Panel wetter-metriken haengt an versandHydrated', () => {
	test('WetterMetrikenVersandPanel steht unter einer Bedingung mit versandHydrated oder erhaelt das Flag als Prop', async () => {
		const { ast, quelle } = await hubOeffnen('wetter-metriken');
		const treffer = mitVorfahren(ast.fragment, 'WetterMetrikenVersandPanel');
		assert.equal(treffer.length, 1, 'genau ein WetterMetrikenVersandPanel im Vergleichs-Hub erwartet');
		const { k, vorfahren } = treffer[0];
		const imBlock = vorfahren.some(
			(v) => v.type === 'IfBlock' && /\bversandHydrated\b/.test(quelle.slice(v.test.start, v.test.end))
		);
		const alsProp = ((k.attributes ?? []) as Knoten[]).some(
			(a) =>
				a.type === 'Attribute' &&
				a.value?.type === 'ExpressionTag' &&
				/\bversandHydrated\b/.test(quelle.slice(a.value.expression.start, a.value.expression.end))
		);
		assert.ok(imBlock || alsProp, 'der Versand-Abschnitt kann vor seiner Hydration mounten (Platzhalter-Risiko)');
	});
});
