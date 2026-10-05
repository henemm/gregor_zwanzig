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

// ─── Issue #2284 S2 — AC-10 (SSR-Anteil), AC-4 ───────────────────────────────
// Spec: docs/specs/modules/feat_2284_s2_trip_kopf.md
// (1) Baustein mit dem Trip-Satz (trip-*-testids, titleTestid, saveController, 8
//     Aktivitäten): jede Kopf-testid und der Chip genau einmal.
// (2) Die Hülle `TripHeader.svelte` mountet den Baustein: im gerenderten Trip-Kopf
//     steht jede Kopf-testid und `save-indicator` genau einmal — der Chip kommt vom
//     Baustein, nicht zusätzlich von der Hülle (Mutation (e) der Spec auf Trip-Seite).
//     Die Zählung auf SEITEN-Ebene (ohne `:visible`) bewacht die E2E.
// RED vor S2: Baustein kennt titleTestid/saveController nicht; TripHeader hat weder
// Region-Stift noch Aktivitäts-Kacheln.

const TRIP_AKTIVITAETEN = [
	{ value: 'trekking', label: 'Trekking' },
	{ value: 'skitour', label: 'Skitour' },
	{ value: 'hochtour', label: 'Hochtour' },
	{ value: 'klettersteig', label: 'Klettersteig' },
	{ value: 'mtb', label: 'MTB' },
	{ value: 'fahrrad_15', label: 'Fahrrad (15 km/h)' },
	{ value: 'fahrrad_20', label: 'Fahrrad (20 km/h)' },
	{ value: 'fahrrad_25', label: 'Fahrrad (25 km/h)' }
];

/** Echte SaveStatus-Instanz ohne Konstruktor (Muster tripMehrreiterPruefstand.erstelleController). */
async function controller(): Promise<unknown> {
	const { SaveStatus } = await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/stores/saveStatusStore.svelte.ts')).href
	);
	const inst = Object.create(SaveStatus.prototype) as Record<string, unknown>;
	Object.assign(inst, {
		state: 'idle',
		savedAt: null,
		error: null,
		_timer: null,
		_pendingFn: null,
		_inflight: null,
		_lastFailed: null,
		_unresolvedError: null,
		_tripId: 't-2284',
		_resourceKind: 'trip'
	});
	return inst;
}

const zaehle = (body: string, id: string): number => body.split(`data-testid="${id}"`).length - 1;

const TRIP_KOPF_IDS = [
	'trip-detail-h1',
	'trip-name-edit-toggle',
	'trip-region-edit-toggle',
	...TRIP_AKTIVITAETEN.map((o) => `trip-profil-option-${o.value}`),
	// #2284 S2 v1.1 (Entscheidung 14): Handy-Knopf samt Auswahl. Die Auswahl und
	// ihre 8 Optionen MÜSSEN im SSR-Markup stehen (versteckt per CSS/hidden, NICHT
	// per `{#if offen}`) — sonst wären sie hier 0× und die „genau einmal"-Zusicherung
	// (Spec-Test-Plan AC-10) nicht prüfbar. Eigene Options-testids, damit keine
	// Kachel-testid doppelt im DOM steht (Strict-Mode der E2E-Locator).
	'trip-profil-knopf',
	'trip-profil-auswahl',
	...TRIP_AKTIVITAETEN.map((o) => `trip-profil-auswahl-option-${o.value}`),
	'save-indicator'
];

describe('#2284 S2 AC-10 — Baustein mit Trip-Satz: jede Kopf-testid und der Chip genau einmal', () => {
	async function tripHtml(): Promise<string> {
		const Komponente = await lade();
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		return render(Komponente as any, {
			props: {
				kind: 'trip',
				name: 'GR20 Nord',
				region: 'Korsika',
				profile: 'trekking',
				profileOptions: TRIP_AKTIVITAETEN,
				regionMaxLength: 60,
				testidPrefix: 'trip',
				titleTestid: 'trip-detail-h1',
				saveController: await controller(),
				onSaveField: async () => {}
			}
		}).body;
	}
	for (const id of TRIP_KOPF_IDS) {
		test(`${id} kommt genau einmal vor`, async () => {
			const n = zaehle(await tripHtml(), id);
			assert.equal(n, 1, `${id}: ${n}× im SSR-Output (erwartet genau 1)`);
		});
	}
});

describe('#2284 S2 AC-10/AC-4 — TripHeader mountet den Baustein: alles genau einmal', () => {
	async function tripHeaderHtml(trip: Record<string, unknown>, mitChip = true): Promise<string> {
		const Kopf = (
			await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-detail/TripHeader.svelte')).href)
		).default;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		return render(Kopf as any, {
			props: {
				trip,
				now: new Date(2026, 9, 2, 10, 0),
				...(mitChip ? { saveController: await controller() } : {})
			}
		}).body;
	}
	const TRIP = {
		id: 't-2284',
		name: 'GR20 Nord',
		shortcode: 'GR',
		region: 'Korsika',
		activity: 'trekking',
		stages: [
			{ id: 'T1', name: 'E1', date: '2026-10-10', waypoints: [] },
			{ id: 'T2', name: 'E2', date: '2026-10-12', waypoints: [] }
		]
	};

	const HUELLE_IDS = [
		...TRIP_KOPF_IDS,
		'trip-detail-status-supplement',
		'trip-detail-meta',
		'trip-header-mobile-metrics'
	];
	for (const id of HUELLE_IDS) {
		test(`${id} kommt im Trip-Kopf genau einmal vor`, async () => {
			const n = zaehle(await tripHeaderHtml(TRIP), id);
			assert.equal(n, 1, `${id}: ${n}× im gerenderten TripHeader (erwartet genau 1)`);
		});
	}

	test('genau ein <header class="trip-header"> (Anker der Ratschen-Specs 336/616)', async () => {
		const body = await tripHeaderHtml(TRIP);
		assert.equal((body.match(/<header[^>]*class="[^"]*\btrip-header\b/g) ?? []).length, 1);
	});

	test('ohne saveController: kein Chip im Trip-Kopf', async () => {
		assert.equal(zaehle(await tripHeaderHtml(TRIP, false), 'save-indicator'), 0);
	});

	test('AC-4: acht Aktivitäts-Kacheln in fester Reihenfolge mit den Beschriftungen des bisherigen Etappen-Reiters', async () => {
		const body = await tripHeaderHtml(TRIP);
		const kacheln = [...body.matchAll(/<button[^>]*data-testid="trip-profil-option-([^"]+)"[^>]*>([\s\S]*?)<\/button>/g)].map(
			(m) => ({ value: m[1], label: m[2].replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, '').trim() })
		);
		assert.deepEqual(kacheln, TRIP_AKTIVITAETEN);
	});

	test('AC-4: gespeicherte Aktivität „trekking" ist die einzige gewählte Kachel', async () => {
		const body = await tripHeaderHtml(TRIP);
		// nur Kacheln zählen (die Handy-Auswahl hat eigene testids, #2284 S2 v1.1)
		const gewaehlt = [...body.matchAll(/<button[^>]*data-selected="true"[^>]*>/g)]
			.map((m) => /data-testid="([^"]+)"/.exec(m[0])?.[1])
			.filter((id) => id?.startsWith('trip-profil-option-'));
		assert.deepEqual(gewaehlt, ['trip-profil-option-trekking']);
	});

	test('AC-4: Trip ohne gespeicherte Aktivität — alle Kacheln ungewählt', async () => {
		const body = await tripHeaderHtml({ ...TRIP, activity: undefined });
		assert.equal((body.match(/data-testid="trip-profil-option-/g) ?? []).length, 8, 'Vorbedingung: 8 Kacheln');
		assert.equal((body.match(/data-selected="true"/g) ?? []).length, 0);
	});

	// #2284 S2 v1.1 — die Hülle reicht die Aktivitäts-Beschriftungen durch: der
	// Handy-Knopf zeigt das Label der gespeicherten Aktivität bzw. neutral.
	const knopfText = (body: string): string | null => {
		const m = /<button[^>]*data-testid="trip-profil-knopf"[^>]*>([\s\S]*?)<\/button>/.exec(body);
		return m ? m[1].replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : null;
	};

	test('AC-4 (Handy-Knopf): gespeicherte Aktivität „trekking" ⇒ Knopftext „Trekking"', async () => {
		const t = knopfText(await tripHeaderHtml(TRIP));
		assert.ok(t !== null, 'AC-4: der Trip-Kopf rendert keinen Knopf trip-profil-knopf');
		assert.ok(t.includes('Trekking'), `AC-4: Knopftext „${t}"`);
	});

	test('AC-4 (Handy-Knopf): „fahrrad_20" ⇒ Knopftext „Fahrrad (20 km/h)"', async () => {
		const t = knopfText(await tripHeaderHtml({ ...TRIP, activity: 'fahrrad_20' }));
		assert.ok(t !== null, 'AC-4: der Trip-Kopf rendert keinen Knopf trip-profil-knopf');
		assert.ok(t.includes('Fahrrad (20 km/h)'), `AC-4: Knopftext „${t}"`);
		assert.ok(!t.includes('Trekking'), `AC-4: Knopftext zeigt die erste Option: „${t}"`);
	});

	test('AC-4 (Handy-Knopf): ohne Aktivität ⇒ „Aktivität wählen"', async () => {
		const t = knopfText(await tripHeaderHtml({ ...TRIP, activity: undefined }));
		assert.ok(t !== null, 'AC-4: der Trip-Kopf rendert keinen Knopf trip-profil-knopf');
		assert.ok(t.includes('Aktivität wählen'), `AC-4: neutraler Knopftext fehlt: „${t}"`);
	});
});
