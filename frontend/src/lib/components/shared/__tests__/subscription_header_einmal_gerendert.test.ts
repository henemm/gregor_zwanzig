// TDD RED — Issue #2284 Scheibe S1: der Kopf-Baustein rendert EIN Markup für
// Desktop und Mobil (Entscheidung 5). Spec:
// docs/specs/modules/feat_2284_s1_subscription_header.md (AC-8)
//
// Heute baut `routes/compare/[id]/+page.svelte` den Kopf zweimal (Desktop- und
// Mobil-Block mit denselben testids, einer per CSS ausgeblendet). Der Baustein
// darf diese Doppelung nicht in sich hineintragen: jede Kopf-testid kommt im
// SSR-Output GENAU EINMAL vor (Mutationsgegenprobe (d) auf Baustein-Ebene).
// Die Doppelung auf SEITEN-Ebene bewacht die E2E
// frontend/e2e/compare-hub-kopf-einmal.spec.ts (Zählung ohne `:visible`).
//
// Grenze: SSR startet im Anzeigemodus (kein Klick, kein Edit-State). Die
// Bearbeiten-testids (`-name-edit`, `-name-save`, …) sind hier nicht im DOM;
// sie zählt die E2E nach dem Klick auf den Stift.
//
// RED HEUTE: Baustein existiert nicht (Import in `lade()`, je Test eigenes Rot).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/subscription_header_einmal_gerendert.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');

async function lade(): Promise<unknown> {
	return (
		await import(
			pathToFileURL(
				path.join(FRONTEND, 'src/lib/components/shared/subscription-header/SubscriptionHeader.svelte')
			).href
		)
	).default;
}

const OPTIONEN = [
	{ value: 'allgemein', label: 'Allgemein' },
	{ value: 'wintersport', label: 'Wintersport' },
	{ value: 'wandern', label: 'Wandern' },
	{ value: 'summer_trekking', label: 'Sommer-Trekking' }
];

async function vergleichHtml(): Promise<string> {
	const Komponente = await lade();
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(Komponente as any, {
		props: {
			kind: 'vergleich',
			name: 'Dolomiten Süd',
			region: 'Ötztal',
			profile: 'wandern',
			profileOptions: OPTIONEN,
			profileLabel: 'Wandern',
			regionMaxLength: 60,
			testidPrefix: 'compare-hub',
			onSaveField: async () => {}
		}
	}).body;
}

describe('#2284 S1 AC-8 — jede Kopf-testid genau einmal im Baustein', () => {
	const kopfIds = [
		'compare-hub-name-edit-toggle',
		'compare-hub-region-edit-toggle',
		...OPTIONEN.map((o) => `compare-hub-profil-option-${o.value}`)
	];
	for (const id of kopfIds) {
		test(`${id} kommt genau einmal vor`, async () => {
			const body = await vergleichHtml();
			const n = body.split(`data-testid="${id}"`).length - 1;
			assert.equal(n, 1, `${id}: ${n}× im SSR-Output (erwartet genau 1)`);
		});
	}

	test('Name steht genau einmal im Kopf (keine zweite, ausgeblendete Namenszeile)', async () => {
		const body = (await vergleichHtml()).replace(/<!--[\s\S]*?-->/g, '');
		const text = body.replace(/<[^>]+>/g, ' ');
		const n = text.split('Dolomiten Süd').length - 1;
		assert.equal(n, 1, `Name ${n}× im Kopf`);
	});

	test('Region steht genau einmal im Kopf', async () => {
		const body = (await vergleichHtml()).replace(/<!--[\s\S]*?-->/g, '');
		const text = body.replace(/<[^>]+>/g, ' ');
		const n = text.split('Ötztal').length - 1;
		assert.equal(n, 1, `Region ${n}× im Kopf`);
	});
});
