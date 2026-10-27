// Issue #1743 (Spec §9, letzter Punkt): auf den Anlege-Seiten gibt es KEIN Autosave.
// Der geteilte Baustein WetterMetrikenVersandPanel speichert im Hub ueber den
// saveController (Besitzer 'wetter-metriken'/'versand') bzw. im Trip-Hub ueber
// BriefingScheduleTab (Knopf „Briefing-Zeitplan speichern" mit PUT auf trip.id).
// Beim Anlegen darf weder das eine noch das andere verdrahtet sein — persistiert wird
// ausschliesslich beim POST (Trip: buildAndSave, Vergleich: wiz.saveNewPreset).
//
// Messweise: (1) gerendertes /trips/new im Schritt Wetter-Metriken (SSR, echte Komponente):
// Versand-Inhalt da, BriefingScheduleTab-Speicherknopf NICHT; (2) Template-AST beider
// Anlege-Editoren: jeder Baustein-Mount ohne saveController/onTripUpdate/preset/
// enqueueHubWrite/onCompareUpdate, Trip-Mounts mit createMode={true}.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { renderTripNew, countTestid } from '../../trip-new/__tests__/tripNewSsr.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const TRIP_NEW = join(HIER, '..', '..', 'trip-new', 'TripNewEditor.svelte');
const COMPARE_NEW = join(HIER, '..', '..', 'compare-new', 'CompareNewEditor.svelte');

type Knoten = Record<string, any>;

function panelMounts(datei: string): Knoten[] {
	const ast = parse(readFileSync(datei, 'utf-8'), { modern: true });
	const treffer: Knoten[] = [];
	const besuche = (n: unknown): void => {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(besuche);
		const k = n as Knoten;
		if (k.type === 'Component' && k.name === 'WetterMetrikenVersandPanel') treffer.push(k);
		for (const key of Object.keys(k)) if (key !== 'parent') besuche(k[key]);
	};
	besuche(ast.fragment);
	return treffer;
}
const propNamen = (m: Knoten): string[] =>
	(m.attributes ?? []).filter((a: Knoten) => a.type === 'Attribute' || a.type === 'BindDirective').map((a: Knoten) => a.name);

const VERBOTEN = ['saveController', 'onTripUpdate', 'preset', 'enqueueHubWrite', 'onCompareUpdate'];

describe('#1743: Anlege-Seiten ohne Autosave', () => {
	for (const mobil of [false, true]) {
		test(`/trips/new ${mobil ? 'mobil' : 'Desktop'}: Versand-Inhalt ohne Speicherknopf des Trip-Hubs`, () => {
			const html = renderTripNew({ activeTab: 'wetter-metriken', isMobileViewport: mobil, name: 'X', startDate: '2026-07-01' });
			assert.equal(countTestid(html, 'versand-tab'), 1, 'Messaufbau: Versand-Inhalt fehlt im Schritt Wetter-Metriken');
			assert.equal(countTestid(html, 'briefings-save'), 0, 'Anlege-Seite zeigt den Speicherknopf des Trip-Hubs (PUT auf trip.id)');
		});
	}

	for (const [name, datei] of [['/trips/new', TRIP_NEW], ['/compare/new', COMPARE_NEW]] as const) {
		test(`${name}: Baustein-Mounts tragen keine Speicher-Verdrahtung`, () => {
			const mounts = panelMounts(datei);
			assert.equal(mounts.length, 2, `${name}: erwartet 2 Baustein-Mounts (Desktop + Mobil)`);
			for (const m of mounts) {
				const props = propNamen(m);
				for (const v of VERBOTEN) assert.ok(!props.includes(v), `${name}: Prop „${v}" verdrahtet einen Speicherweg (Autosave)`);
				if (datei === TRIP_NEW) assert.ok(props.includes('createMode'), `${name}: Baustein ohne createMode — mountet BriefingScheduleTab`);
			}
		});
	}
});
