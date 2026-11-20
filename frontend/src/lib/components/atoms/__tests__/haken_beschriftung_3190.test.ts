// TDD RED — Issue #3190 (Epic #2913): Haken-Atom mit klickbarer Beschriftung.
// Spec: docs/specs/modules/feat_3190_vorlage_dialog_inline.md — Implementation Details 5, AC-8.
//
// Vertrag: atoms/Haken.svelte bekommt den optionalen Prop `beschriftung?: string`.
//   an/aus + beschriftung → GENAU EIN <label> (kein Verschachteln), darin das echte Kontrollkästchen
//                           und der sichtbare Text; `testid` sitzt an diesem <label> (ganzer Text klickbar).
//   ohne beschriftung     → Markup wie bisher (Bestand der Einstell-Tabelle „Was steht wo“, #3122).
//
//   cd frontend && npm test -- src/lib/components/atoms/__tests__/haken_beschriftung_3190.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const HAKEN = path.resolve(HERE, '..', 'Haken.svelte');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const H = (await import(pathToFileURL(HAKEN).href)).default;

const html = (props: Record<string, unknown>) => render(H, { props }).body.replace(/<!--[\s\S]*?-->/g, '').trim();
const labels = (h: string) => (h.match(/<label\b/g) ?? []).length;
/** Inhalt des (einzigen) <label>…</label>. */
const labelInhalt = (h: string) => h.match(/<label\b[^>]*>([\s\S]*)<\/label>/)?.[1] ?? '';
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

describe('#3190 Haken mit Beschriftung: ein <label>, Text klickbar', () => {
	for (const zustand of ['an', 'aus'] as const) {
		test(`${zustand} + beschriftung → genau ein <label> mit Kontrollkästchen und sichtbarem Text`, () => {
			const h = html({ zustand, name: 'Als Standard für neue Trips', beschriftung: 'Als Standard für neue Trips', testid: 'save-preset-is-default' });
			assert.equal(labels(h), 1, `erwartet genau ein <label>, Markup: ${h}`);
			const inhalt = labelInhalt(h);
			assert.match(inhalt, /<input\b[^>]*\stype="checkbox"/, 'Kontrollkästchen liegt nicht im <label>');
			assert.ok(text(inhalt).includes('Als Standard für neue Trips'), `Beschriftung nicht im <label>: ${inhalt}`);
			const offen = h.match(/<label\b[^>]*>/)![0];
			assert.match(offen, /\sdata-testid="save-preset-is-default"/, 'testid gehört an das beschriftete <label>');
			if (zustand === 'an') assert.match(inhalt, /<input\b[^>]*\schecked\b/);
			else assert.doesNotMatch(inhalt, /<input\b[^>]*\schecked\b/);
		});
	}
	test('Beschriftung ist sichtbarer Text, nicht aria-hidden', () => {
		const h = html({ zustand: 'aus', name: 'Default for new locations', beschriftung: 'Default for new locations' });
		const versteckt = h.match(/<[a-z]+\b[^>]*aria-hidden="true"[^>]*>[\s\S]*?<\/[a-z]+>/g) ?? [];
		for (const v of versteckt) assert.ok(!text(v).includes('Default for new locations'), 'Beschriftung steckt in aria-hidden');
		assert.ok(text(h).includes('Default for new locations'));
	});
	test('ohne beschriftung: kein zusätzlicher Text im Label, Markup wie bisher', () => {
		const h = html({ zustand: 'an', name: 'Wind in E-Mail', testid: 'hk' });
		assert.equal(labels(h), 1);
		assert.equal(text(labelInhalt(h)), '', `ohne beschriftung kein sichtbarer Text: ${h}`);
		assert.match(h, /<input\b[^>]*\saria-label="Wind in E-Mail"/);
	});
});
