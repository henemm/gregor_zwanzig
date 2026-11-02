// doc-compliance-test (Strukturtest: liest Quelltexte und Kataloge als DATEN)
//
// Issue #2659 (i18n F10, Epic #2644) — AC-5: Trip und Ortsvergleich zeigen denselben
// Text aus demselben Schluessel. Die Compare-Flaechen holen Aktionen und Reiternamen
// aus `aktionen.*`; es gibt keinen Schluessel `vergleich.aktion*`, und kein Text steht
// unter zwei Schluesseln: ein `vergleich.*`-Wert (de) ist innerhalb von vergleich.*
// eindeutig und steht nicht schon unter aktionen.*, home.* oder listen.* (dort waere
// der vorhandene Schluessel zu verwenden). Plural-Paare `.one`/`.other` zaehlen als EIN Text.
// Spec: docs/specs/modules/i18n_f10_vergleich_flaechen_2659.md
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/vergleich_nutzt_gemeinsame_aktionen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HIER, '../../../..');
const MSG = path.join(SRC, 'lib', 'i18n', 'messages');
const FLAECHEN = ['lib/components/compare', 'lib/components/compare-new', 'lib/components/shared/hub-uebersicht', 'routes/compare/[id]', 'routes/compare/new'];

function dateien(verz: string): string[] {
	const aus: string[] = [];
	for (const n of readdirSync(verz)) {
		const p = path.join(verz, n);
		if (statSync(p).isDirectory()) {
			if (n !== '__tests__') aus.push(...dateien(p));
		} else if (/\.(svelte|ts)$/.test(n) && !/\.test\.ts$/.test(n)) aus.push(p);
	}
	return aus;
}
const quelle = (rel: string) => dateien(path.join(SRC, rel)).map((d) => readFileSync(d, 'utf-8')).join('\n');
const katalog = (lang: string, bereich: string) => JSON.parse(readFileSync(path.join(MSG, lang, `${bereich}.json`), 'utf-8')) as Record<string, string>;
const basis = (k: string) => k.replace(/\.(one|other)$/, '');

describe('AC-5: Compare-Flaechen nutzen die gemeinsamen Aktionen', () => {
	test('Messaufbau: alle Flaechen haben Quelltexte', () => {
		for (const f of FLAECHEN) assert.ok(dateien(path.join(SRC, f)).length > 0, f);
	});
	test('Aktionen und Reiternamen kommen aus aktionen.* (Hub-Seite, Uebersicht, Anlegen)', () => {
		const alle = FLAECHEN.map(quelle).join('\n');
		for (const k of ['aktionen.edit', 'aktionen.delete', 'aktionen.senden', 'aktionen.wird_gesendet', 'aktionen.weitere', 'aktionen.abbrechen', 'aktionen.pause', 'aktionen.reiter.orte', 'aktionen.reiter.wertebereiche', 'aktionen.zurueck_uebersicht'])
			assert.ok(alle.includes(`'${k}'`), k);
		assert.match(quelle('lib/components/compare'), /aktionen\./);
		// Aktionsliste und Reiter: die EINE Quelle (shared/subscriptionActions.ts, subscriptionTabs.ts).
		assert.match(quelle('routes/compare/[id]'), /subscriptionActions\('vergleich', lifecycle, 'hub'\)/);
		assert.match(quelle('lib/components/compare'), /subscriptionTabs\('vergleich'\)/);
		assert.match(quelle('lib/components/compare-new'), /anlegeKette\('vergleich'\)/);
	});
	test('kein Schluessel vergleich.aktion* — weder im Katalog noch in den Quelltexten', () => {
		for (const lang of ['de', 'en']) assert.deepEqual(Object.keys(katalog(lang, 'vergleich')).filter((k) => k.startsWith('vergleich.aktion')), [], lang);
		assert.ok(!FLAECHEN.map(quelle).join('\n').includes('vergleich.aktion'));
	});
	test('kein Text unter zwei Schluesseln: vergleich.* eindeutig und nicht schon in aktionen.*/home.*/listen.* (de)', () => {
		const v = katalog('de', 'vergleich');
		const geteilt = new Map<string, string>();
		for (const b of ['aktionen', 'home', 'listen']) for (const [k, w] of Object.entries(katalog('de', b))) geteilt.set(w, k);
		const gesehen = new Map<string, string>();
		const doppelt: string[] = [];
		for (const [k, w] of Object.entries(v)) {
			// vergleich.anlegen.* ist Bestand aus F9 (#2658, eigener Anker), nicht Gegenstand von F10.
			if (k.startsWith('vergleich.anlegen.')) continue;
			if (geteilt.has(w)) doppelt.push(`${k} = ${geteilt.get(w)} („${w}")`);
			const vorher = gesehen.get(w);
			if (vorher !== undefined && basis(vorher) !== basis(k)) doppelt.push(`${k} = ${vorher} („${w}")`);
			gesehen.set(w, k);
		}
		assert.deepEqual(doppelt, []);
	});
	test('de und en tragen dieselben Schluessel und Platzhalter in vergleich.*', () => {
		const de = katalog('de', 'vergleich');
		const en = katalog('en', 'vergleich');
		assert.deepEqual(Object.keys(en).sort(), Object.keys(de).sort());
		const ph = (s: string) => [...s.matchAll(/\{([a-z0-9_]+)\}/g)].map((m) => m[1]).sort();
		for (const k of Object.keys(de)) assert.deepEqual(ph(en[k]), ph(de[k]), k);
	});
});
