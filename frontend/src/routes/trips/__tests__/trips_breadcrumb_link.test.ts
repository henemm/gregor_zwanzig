// TDD RED/GUARD — Issue #2278 (Epic #2345 P3), AC-13: die Breadcrumbs "Trips" fuehren zur Liste /trips.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 9.
//
// Gemessen: im Trip-Hub ist "Trips" ein toter <span> (routes/trips/[id]/+page.svelte, Breadcrumb-Leiste).
// Im Trip-Anlegen-Editor steht "Trips" als `back`-Prop des geteilten PageHeader (BackLink) — die Spec
// nannte dort eine tote Stelle (~:363); gemessen auf dem Stand 6fafebf3e ist sie bereits ein Link.
// Dieser Test bewacht BEIDE: hat die Stelle einen Link auf /trips — entweder als <a href="/trips">
// im Template oder als `back={{href:'/trips', label:'Trips'}}` an einer Komponente, die dafuer ECHT
// einen <a href="/trips"> rendert (PageHeader wird hier gerendert, nicht angenommen).
//
// Erwartung: Hub RED, Anlegen-Editor GREEN (Guard gegen Rueckfall).
//
// Pfadregel #1409: relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/trips/__tests__/trips_breadcrumb_link.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { ladeSvelte, collect, literale } from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trips -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const PageHeader = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/atoms/PageHeader.svelte')).href)).default;

const HUB = path.join(HERE, '..', '[id]', '+page.svelte');
// Issue #2658 (i18n F9): die Beschriftung kommt aus dem Katalog (de „Trips").
const TRIPS_KEY = 'listen.trips.titel';
const { trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const EDITOR = path.join(FRONTEND, 'src/lib/components/trip-new/TripNewEditor.svelte');

/** Gibt es im Template einen Link auf /trips mit Text "Trips"? (direkt oder ueber `back`-Prop) */
function trips_link_vorhanden(datei: string): boolean {
	const ast = ladeSvelte(datei);
	const direkt = collect(
		ast.fragment,
		(n) =>
			n.type === 'RegularElement' &&
			n.name === 'a' &&
			(n.attributes ?? []).some((a: any) => a.name === 'href' && literale(a.value).has('/trips')) &&
			(collect(n.fragment, (t) => t.type === 'Text' && /Trips/.test(t.data)).length > 0 || literale(n.fragment).has(TRIPS_KEY))
	);
	if (direkt.length > 0) return true;
	const ueberBack = collect(
		ast.fragment,
		(n) =>
			(n.type === 'Component') &&
			(n.attributes ?? []).some((a: any) => a.name === 'back' && literale(a.value).has('/trips') && (literale(a.value).has('Trips') || literale(a.value).has(TRIPS_KEY)))
	);
	return ueberBack.length > 0;
}

describe('AC-13: Breadcrumb "Trips" ist ein Link auf /trips', () => {
	test('Baustein PageHeader rendert `back` als <a href="/trips">Trips</a>', () => {
		const h = render(PageHeader, { props: { back: { href: '/trips', label: 'Trips' }, compact: true } }).body;
		assert.match(h, /<a[^>]*href="\/trips"/);
		assert.match(h, />[^<]*Trips/);
	});

	test('Katalog: listen.trips.titel ist deutsch „Trips"', () => {
		assert.equal(trFor('de', TRIPS_KEY), 'Trips');
	});

	test('Trip-Hub: "Trips" ist verlinkt (heute toter <span>)', () => {
		assert.ok(trips_link_vorhanden(HUB), 'Trip-Hub: Breadcrumb "Trips" ist kein Link auf /trips');
	});

	test('Trip-Anlegen-Editor: "Trips" ist verlinkt (Guard)', () => {
		assert.ok(trips_link_vorhanden(EDITOR), 'TripNewEditor: Breadcrumb "Trips" ist kein Link auf /trips');
	});
});
