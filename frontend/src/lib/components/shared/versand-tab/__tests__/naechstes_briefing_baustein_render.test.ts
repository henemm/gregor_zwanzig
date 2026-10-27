// TDD RED — Issue #1969 (Nächstes Briefing), AC-16 / AC-17 / AC-19 / AC-22.
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Echte SSR-Renders (svelte/server) des GETEILTEN Bausteins
// shared/versand-tab/VTNextBriefing.svelte (Props `nextBriefing`, `context`)
// und seiner Einbettung im geteilten VersandTab — in BEIDEN Kontexten.
// Wurzelelement trägt data-testid="vt-next-briefing"; das Etikett
// „Nächstes Briefing" rendert der Baustein, der Wert kommt aus
// formatNextBriefing (nextBriefingText.ts).
//
// Prozess-Zone ≠ Trip-Zone (AC-16): TZ=America/Los_Angeles. Eine Umrechnung von
// `at` in Browser-Zone ergäbe „Mi 22:00" statt „Do 07:00 (CEST)".
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_baustein_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const imp = async (rel: string) => (await import(pathToFileURL(path.join(FRONTEND, rel)).href)).default;
const VTNextBriefing = await imp('src/lib/components/shared/versand-tab/VTNextBriefing.svelte');
const VersandTab = await imp('src/lib/components/shared/VersandTab.svelte');

const TESTID = 'data-testid="vt-next-briefing"';

const MORGEN_DO = {
	at: '2026-10-22T07:00:00+02:00',
	local_date: '2026-10-22',
	local_time: '07:00',
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
};

const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');

/** HTML des Elements, das `marker` in seinem Start-Tag trägt (inkl. Kinder). */
function elementMit(html: string, marker: string): string {
	const i = html.indexOf(marker);
	assert.notEqual(i, -1, `${marker} fehlt im gerenderten HTML`);
	const start = html.lastIndexOf('<', i);
	const name = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start))![1];
	const re = new RegExp(`<${name}\\b|</${name}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	for (let m = re.exec(html); m; m = re.exec(html)) {
		tiefe += m[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return html.slice(start, m.index + m[0].length);
	}
	return html.slice(start);
}

/** Sichtbarer Text eines HTML-Schnipsels, Leerraum normalisiert. */
const text = (html: string) => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

const baustein = (props: Record<string, unknown>) => ohneKommentare(render(VTNextBriefing, { props }).body);

describe('AC-16/AC-17: ein Baustein, beide Kontexte, gleiches Ergebnis in Trip-Zone', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`context=${context}: Wurzel trägt die testid, Etikett + „Do 07:00 (CEST)"`, () => {
			const html = baustein({ nextBriefing: MORGEN_DO, context });
			const el = text(elementMit(html, TESTID));
			assert.ok(el.includes('Nächstes Briefing'), `Etikett fehlt: ${el}`);
			assert.ok(el.includes('Do 07:00 (CEST)'), `Trip-Zonen-Zeit fehlt: ${el}`);
			assert.ok(!el.includes('22:00'), `Browser-Zonen-Umrechnung sichtbar: ${el}`);
		});
	}

	test('route und vergleich zeigen denselben Text', () => {
		const r = text(elementMit(baustein({ nextBriefing: MORGEN_DO, context: 'route' }), TESTID));
		const v = text(elementMit(baustein({ nextBriefing: MORGEN_DO, context: 'vergleich' }), TESTID));
		assert.equal(r, v);
	});

	test('Grund statt Zeit (vergleich, manual) → „nur manueller Versand"', () => {
		const el = text(elementMit(baustein({ nextBriefing: { at: null, reason: 'manual' }, context: 'vergleich' }), TESTID));
		assert.ok(el.includes('nur manueller Versand'), el);
	});
});

describe('AC-19: Ladezustand / Fehler — kein Absturz, keine erfundene Zeit', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`context=${context}: nicht geladen (undefined) → keine Uhrzeit`, () => {
			const el = text(elementMit(baustein({ nextBriefing: undefined, context }), TESTID));
			assert.doesNotMatch(el, /\d{1,2}:\d{2}/, `erfundene Zeit im Ladezustand: ${el}`);
		});
		test(`context=${context}: Fehler (null) → „—"`, () => {
			const el = text(elementMit(baustein({ nextBriefing: null, context }), TESTID));
			assert.ok(el.includes('—'), el);
			assert.doesNotMatch(el, /\d{1,2}:\d{2}/, el);
		});
	}
});

describe('AC-22/AC-17: der geteilte VersandTab bettet den Baustein in beiden Kontexten genau einmal ein', () => {
	const tabs: Record<string, () => string> = {
		route: () => ohneKommentare(render(VersandTab, { props: { context: 'route', reportConfig: undefined } }).body),
		vergleich: () => ohneKommentare(render(VersandTab, { props: { context: 'vergleich', sendEmail: true } }).body)
	};
	for (const [context, html] of Object.entries(tabs)) {
		test(`VersandTab context=${context}: genau eine Zeile vt-next-briefing, ohne geladenen Wert keine Zeit`, () => {
			const out = html();
			assert.equal(out.split(TESTID).length - 1, 1, 'vt-next-briefing muss genau einmal vorkommen');
			const el = text(elementMit(out, TESTID));
			assert.ok(el.includes('Nächstes Briefing'), el);
			assert.doesNotMatch(el, /\d{1,2}:\d{2}/, `SSR ohne Backend-Wert zeigt eine Zeit: ${el}`);
		});
	}

	test('bestehende Versand-testids bleiben erhalten (Stichprobe)', () => {
		const out = tabs.route();
		for (const id of ['channel-email', 'channel-telegram', 'channel-sms']) {
			assert.ok(out.includes(`data-testid="${id}"`), `testid ${id} fehlt`);
		}
	});
});
