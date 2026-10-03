// TDD RED — Issue #2284 Scheibe S1: geteilter Kopf-Baustein `SubscriptionHeader`.
// Spec: docs/specs/modules/feat_2284_s1_subscription_header.md (AC-6, AC-7)
//
// WAS HIER BEWACHT WIRD: Der Baustein ist EIN Markup für Trip und Vergleich.
// Unterschiede laufen nur über Props (testidPrefix, profileOptions, Snippets),
// nie über einen `{#if kind === …}`-Zweig im Markup (Entscheidung 4).
// Deshalb reicht es nicht, Präfix und Optionenzahl zu prüfen — ein zusätzlicher
// Knoten nur für `kind="trip"` bliebe davon unberührt. AC-6 vergleicht darum die
// normalisierte Tag-Folge beider Renderings (Mutationsgegenprobe (a)).
//
// Echte Komponente, serverseitig gerendert (svelte/server, Hooks:
// frontend/test-svelte-ssr-hooks.mjs) — kein Mock, kein Datei-Grep.
// SSR führt keine Klick-Handler aus: Speicher-/Fehlerpfade (AC-1 … AC-5) und
// die Region-Eingabe samt `maxlength` (AC-10, nur im Bearbeitungsmodus im DOM)
// werden im E2E bewacht (frontend/e2e/compare-hub-kopf-einmal.spec.ts).
//
// RED HEUTE: `shared/subscription-header/SubscriptionHeader.svelte` existiert
// nicht. Der Import steckt bewusst in `lade()`, damit jeder Test einzeln mit
// eigener Meldung scheitert statt die ganze Datei beim Laden abzubrechen.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/subscription_header_kontextneutral.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');

const PRUEFLING = path.join(
	FRONTEND,
	'src/lib/components/shared/subscription-header/SubscriptionHeader.svelte'
);

async function lade(): Promise<unknown> {
	return (await import(pathToFileURL(PRUEFLING).href)).default;
}

const VERGLEICH_OPTIONEN = [
	{ value: 'allgemein', label: 'Allgemein' },
	{ value: 'wintersport', label: 'Wintersport' },
	{ value: 'wandern', label: 'Wandern' },
	{ value: 'summer_trekking', label: 'Sommer-Trekking' }
];
const TRIP_OPTIONEN = [
	{ value: 'trekking', label: 'Trekking' },
	{ value: 'skitour', label: 'Skitour' }
];

const keinSpeichern = async (): Promise<void> => {};

function vergleichProps(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		kind: 'vergleich',
		name: 'Dolomiten Süd',
		region: 'Ötztal',
		profile: 'wandern',
		profileOptions: VERGLEICH_OPTIONEN,
		profileLabel: 'Wandern',
		regionMaxLength: 60,
		testidPrefix: 'compare-hub',
		onSaveField: keinSpeichern,
		...extra
	};
}

function tripProps(extra: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		kind: 'trip',
		name: 'GR20 Nord',
		region: 'Korsika',
		profile: 'trekking',
		profileOptions: TRIP_OPTIONEN,
		profileLabel: 'Trekking',
		regionMaxLength: 80,
		testidPrefix: 'trip',
		onSaveField: keinSpeichern,
		...extra
	};
}

async function html(props: Record<string, unknown>): Promise<string> {
	const Komponente = await lade();
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(Komponente as any, { props }).body;
}

function testids(body: string): string[] {
	return [...body.matchAll(/data-testid="([^"]+)"/g)].map((m) => m[1]);
}

/**
 * Tag-Folge des Gerüsts, kontextneutral: Kommentare weg, Präfix und
 * Optionswerte neutralisiert, nur Tagname + (neutralisierte) testid je
 * öffnendem Tag. Aufeinanderfolgende gleiche Options-Kacheln fallen zu einer
 * zusammen, damit 4 vs. 2 Optionen das Gerüst nicht unterscheiden.
 */
function geruest(body: string, prefix: string, optionen: { value: string }[]): string[] {
	let b = body.replace(/<!--[\s\S]*?-->/g, '');
	for (const o of optionen) {
		b = b.split(`${prefix}-profil-option-${o.value}`).join('PFX-profil-option-OPT');
	}
	b = b.split(`${prefix}-`).join('PFX-');
	const folge: string[] = [];
	for (const m of b.matchAll(/<([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>/g)) {
		const tid = /data-testid="([^"]+)"/.exec(m[2])?.[1];
		folge.push(tid ? `${m[1]}[${tid}]` : m[1]);
	}
	// Kachel-Gruppe (Kachel + ihre inneren Tags bis zur nächsten Kachel) zusammenfassen
	const kachel = 'button[PFX-profil-option-OPT]';
	const gruppen: string[][] = [];
	for (const t of folge) {
		if (t === kachel || gruppen.length === 0) gruppen.push([t]);
		else gruppen[gruppen.length - 1].push(t);
	}
	const aus: string[] = [];
	let letzteKachel: string | null = null;
	for (const g of gruppen) {
		const key = g.join(' ');
		if (g[0] === kachel && key === letzteKachel) continue;
		letzteKachel = g[0] === kachel ? key : null;
		aus.push(...g);
	}
	return aus;
}

describe('#2284 S1 AC-6 — ein Markup für Trip und Vergleich, Unterschiede nur über Props', () => {
	test('Vergleich-Satz trägt nur compare-hub-testids und genau seine vier Optionen', async () => {
		const ids = testids(await html(vergleichProps()));
		assert.ok(ids.includes('compare-hub-name-edit-toggle'), `Name-Stift fehlt: ${ids.join(', ')}`);
		assert.ok(ids.includes('compare-hub-region-edit-toggle'), `Region-Stift fehlt: ${ids.join(', ')}`);
		const optionen = ids.filter((i) => i.startsWith('compare-hub-profil-option-'));
		assert.deepEqual(
			optionen.sort(),
			VERGLEICH_OPTIONEN.map((o) => `compare-hub-profil-option-${o.value}`).sort()
		);
		assert.equal(ids.filter((i) => i.startsWith('trip-')).length, 0, `trip-testid im Vergleich: ${ids.join(', ')}`);
	});

	test('Trip-Satz trägt nur trip-testids und genau seine zwei Optionen', async () => {
		const ids = testids(await html(tripProps()));
		assert.ok(ids.includes('trip-name-edit-toggle'), `Name-Stift fehlt: ${ids.join(', ')}`);
		assert.ok(ids.includes('trip-region-edit-toggle'), `Region-Stift fehlt: ${ids.join(', ')}`);
		const optionen = ids.filter((i) => i.startsWith('trip-profil-option-'));
		assert.deepEqual(optionen.sort(), ['trip-profil-option-skitour', 'trip-profil-option-trekking']);
		assert.equal(
			ids.filter((i) => i.startsWith('compare-hub-')).length,
			0,
			`compare-hub-testid im Trip: ${ids.join(', ')}`
		);
	});

	test('gewählte Kachel kommt aus der Prop `profile` — genau eine mit data-selected="true"', async () => {
		const body = await html(vergleichProps({ profile: 'wintersport' }));
		const gewaehlt = [...body.matchAll(/<button[^>]*data-selected="true"[^>]*>/g)].map(
			(m) => /data-testid="([^"]+)"/.exec(m[0])?.[1]
		);
		assert.deepEqual(gewaehlt, ['compare-hub-profil-option-wintersport']);
	});

	test('Name als einzige <h1>, Region als Text im Kopf', async () => {
		const body = await html(vergleichProps());
		assert.equal((body.match(/<h1[\s>]/g) ?? []).length, 1, 'genau eine Überschrift');
		assert.match(body, /<h1[^>]*>[\s\S]*?Dolomiten Süd[\s\S]*?<\/h1>/);
		assert.ok(body.includes('Ötztal'), 'Region fehlt im Kopf');
	});

	test('beide Prop-Sätze ergeben dieselbe Gerüststruktur (keine Verzweigung nach kind)', async () => {
		const v = geruest(await html(vergleichProps()), 'compare-hub', VERGLEICH_OPTIONEN);
		const t = geruest(await html(tripProps()), 'trip', TRIP_OPTIONEN);
		assert.ok(v.includes('h1'), `Gerüst ohne Überschrift: ${v.join(' ')}`);
		assert.ok(v.includes('button[PFX-profil-option-OPT]'), `Gerüst ohne Kachelreihe: ${v.join(' ')}`);
		assert.deepEqual(t, v, 'Trip- und Vergleich-Gerüst weichen ab — Markup verzweigt nach kind');
	});
});

describe('#2284 S1 AC-7 — leere Slots hinterlassen keine Wrapper', () => {
	test('ohne actions/meta/badges/eyebrow: kein leeres Element im Kopf', async () => {
		const body = (await html(vergleichProps())).replace(/<!--[\s\S]*?-->/g, '');
		const leer = [...body.matchAll(/<(div|span|section|header|nav|p)(\s[^>]*)?>\s*<\/\1>/g)].map((m) => m[0]);
		assert.deepEqual(leer, [], `leere Wrapper im DOM: ${leer.join(' | ')}`);
	});

	test('übergebene Snippets erscheinen je genau einmal', async () => {
		const snip = (id: string, text: string) =>
			createRawSnippet(() => ({ render: () => `<span data-testid="${id}">${text}</span>` }));
		const body = await html(
			vergleichProps({
				actions: snip('probe-actions', 'Aktion'),
				meta: snip('probe-meta', '· 3 Orte'),
				badges: snip('probe-badges', 'Aktiv'),
				eyebrow: snip('probe-eyebrow', 'Orts-Vergleich · Hub')
			})
		);
		const ids = testids(body);
		for (const id of ['probe-actions', 'probe-meta', 'probe-badges', 'probe-eyebrow']) {
			assert.equal(ids.filter((i) => i === id).length, 1, `${id} nicht genau einmal: ${ids.join(', ')}`);
		}
	});

	test('profileLabel leer ⇒ kein führendes oder doppeltes „ · " in der Unterzeile', async () => {
		const body = (await html(vergleichProps({ profileLabel: '' }))).replace(/<!--[\s\S]*?-->/g, '');
		const text = body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
		assert.ok(!/·\s*·/.test(text), `doppelter Trenner: ${text}`);
		assert.ok(!text.includes('Wandern'), `Profil-Label trotz leerer Prop: ${text}`);
	});
});
