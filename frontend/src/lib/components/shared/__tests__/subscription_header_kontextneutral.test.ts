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
		// #2284 S2 v1.1: die Handy-Auswahl des Knopfs trägt eigene Options-testids
		// (`{p}-profil-auswahl-option-<wert>`) — ebenso neutralisieren und zusammenfassen.
		b = b.split(`${prefix}-profil-auswahl-option-${o.value}`).join('PFX-profil-auswahl-option-OPT');
		b = b.split(`${prefix}-profil-option-${o.value}`).join('PFX-profil-option-OPT');
	}
	b = b.split(`${prefix}-`).join('PFX-');
	const folge: string[] = [];
	for (const m of b.matchAll(/<([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>/g)) {
		const tid = /data-testid="([^"]+)"/.exec(m[2])?.[1];
		folge.push(tid ? `${m[1]}[${tid}]` : m[1]);
	}
	// Kachel-Gruppe (Kachel + ihre inneren Tags bis zur nächsten Kachel) zusammenfassen;
	// dasselbe für die Optionen der Handy-Auswahl (#2284 S2 v1.1).
	const istOption = (t: string) => /\[PFX-profil-(auswahl-)?option-OPT\]$/.test(t);
	const gruppen: string[][] = [];
	for (const t of folge) {
		if (istOption(t) || gruppen.length === 0) gruppen.push([t]);
		else gruppen[gruppen.length - 1].push(t);
	}
	const aus: string[] = [];
	let letzteKachel: string | null = null;
	for (const g of gruppen) {
		const key = g.join(' ');
		if (istOption(g[0]) && key === letzteKachel) continue;
		letzteKachel = istOption(g[0]) ? key : null;
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
		// nur die Kacheln zählen (#2284 S2 v1.1: die Handy-Auswahl hat eigene testids)
		const gewaehlt = [...body.matchAll(/<button[^>]*data-selected="true"[^>]*>/g)]
			.map((m) => /data-testid="([^"]+)"/.exec(m[0])?.[1])
			.filter((id) => id?.startsWith('compare-hub-profil-option-'));
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
		const textVon = async (profileLabel: string) =>
			(await html(vergleichProps({ profileLabel })))
				.replace(/<!--[\s\S]*?-->/g, '')
				.replace(/<[^>]+>/g, ' ')
				.replace(/\s+/g, ' ');
		const wandern = (t: string) => t.split('Wandern').length - 1;
		// „Wandern" steht auch in den Aktivitäts-Bedienelementen (Kachel; seit #2284
		// S2 v1.1 zusätzlich Handy-Knopf und dessen Auswahl) — gezählt wird darum
		// relativ: mit Label genau EIN Vorkommen mehr als ohne; ohne Label steht es
		// nicht in der Unterzeile.
		const ohne = await textVon('');
		assert.ok(!/·\s*·/.test(ohne), `doppelter Trenner: ${ohne}`);
		assert.ok(!(await unterzeile('')).includes('Wandern'), `Profil-Label trotz leerer Prop: ${ohne}`);
		const mit = await textVon('Wandern');
		assert.equal(wandern(mit), wandern(ohne) + 1, `Profil-Label fehlt in der Unterzeile: ${mit}`);
	});

	// Adversary F001 (#2284 S1 Fix-Loop 1): der Guard um das Profil-Label wirkt
	// erst MIT meta-Snippet (Seite: „ · 3 Orte") — ohne Guard entstünde dort
	// „Ötztal · · 3 Orte" bzw. ohne meta ein hängendes „Ötztal · ".
	const metaOrte = createRawSnippet(() => ({ render: () => `<span>${' · '}3 Orte</span>` }));
	// Unterzeile = Text nach der Region bis zum ersten Aktivitäts-Bedienelement
	// (Kachel ODER, seit #2284 S2 v1.1, Handy-Knopf — der kann vor den Kacheln stehen).
	async function unterzeile(profileLabel: string, meta?: unknown): Promise<string> {
		const roh = await html(vergleichProps(meta ? { profileLabel, meta } : { profileLabel }));
		const bisProfil = roh.split(/<[a-z]+[^>]*data-testid="compare-hub-profil-/)[0];
		return bisProfil
			.replace(/<!--[\s\S]*?-->/g, '')
			.replace(/<[^>]+>/g, ' ')
			.replace(/\s+/g, ' ')
			.split('Ötztal')[1]
			.trim();
	}

	test('profileLabel leer MIT meta ⇒ „Ötztal · 3 Orte" ohne doppelten Trenner', async () => {
		assert.equal(await unterzeile('', metaOrte), '· 3 Orte');
	});

	test('profileLabel leer OHNE meta ⇒ kein hängender Trenner', async () => {
		assert.equal(await unterzeile(''), '');
	});

	test('profileLabel gesetzt MIT meta ⇒ Label genau einmal, je ein Trenner', async () => {
		assert.equal(await unterzeile('Wandern', metaOrte), '· Wandern · 3 Orte');
	});
});

// ─── Issue #2284 S2 — AC-16 ──────────────────────────────────────────────────
// Spec: docs/specs/modules/feat_2284_s2_trip_kopf.md (Entscheidungen 1, 2, 12, 13)
// Neue optionale Props: `titleTestid` (Trip: 'trip-detail-h1'), Snippet `namePrefix`
// (Shortcode INNERHALB der Überschrift), `saveController` (der Baustein rendert den
// Speicher-Chip selbst, genau einmal). Region: `region || '—'` (Leerstring ⇒ „—").
// RED vor S2: Props unbekannt (keine testid, kein Präfix, kein Chip) und `region=""`
// erscheint als leere Zeile.

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Feldinitialisierer laufen unter
 *  node nicht) — dasselbe Muster wie tripMehrreiterPruefstand.erstelleController. */
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
		_tripId: 't-1',
		_resourceKind: 'trip'
	});
	return inst;
}

const praefix = createRawSnippet(() => ({
	render: () => `<span data-testid="probe-praefix">GR · </span>`
}));

async function tripSatz(extra: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
	return tripProps({ titleTestid: 'trip-detail-h1', namePrefix: praefix, saveController: await controller(), ...extra });
}

const zaehle = (body: string, id: string): number => body.split(`data-testid="${id}"`).length - 1;

/** Der sichtbare Region-Text: zwischen dem Namens-Stift und dem Region-Stift
 *  (dort steht nur die Region — badges/actions sind leer). Kommentare und Tags weg. */
function regionText(body: string, prefix: string): string {
	const nachName = body.split(`data-testid="${prefix}-name-edit-toggle"`)[1] ?? '';
	const bisRegion = nachName.split(`data-testid="${prefix}-region-edit-toggle"`)[0] ?? '';
	// ab dem Ende des Namens-Stifts
	const ab = bisRegion.slice(bisRegion.indexOf('</button>') + '</button>'.length);
	return ab
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<button[^>]*$/, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

describe('#2284 S2 AC-16 — titleTestid, namePrefix, saveController', () => {
	test('Trip-Satz: die Überschrift trägt data-testid="trip-detail-h1" genau einmal', async () => {
		const body = await html(await tripSatz());
		assert.equal(zaehle(body, 'trip-detail-h1'), 1, 'trip-detail-h1 nicht genau einmal');
		assert.match(body, /<h1[^>]*data-testid="trip-detail-h1"[^>]*>/, 'die testid sitzt nicht an der <h1>');
	});

	test('Vergleich-Satz (ohne titleTestid): keine testid an der Überschrift, kein trip-detail-h1', async () => {
		const body = await html(vergleichProps());
		assert.equal(zaehle(body, 'trip-detail-h1'), 0);
		const h1 = /<h1[^>]*>/.exec(body)?.[0] ?? '';
		assert.ok(h1, 'keine Überschrift');
		assert.ok(!h1.includes('data-testid'), `Überschrift trägt ohne Prop eine testid: ${h1}`);
	});

	test('namePrefix steht INNERHALB der Überschrift, vor dem Namen', async () => {
		const body = await html(await tripSatz());
		const h1 = /<h1[^>]*>([\s\S]*?)<\/h1>/.exec(body)?.[1] ?? '';
		assert.ok(h1.includes('data-testid="probe-praefix"'), `Präfix nicht in der Überschrift: ${h1}`);
		assert.ok(
			h1.indexOf('probe-praefix') < h1.indexOf('GR20 Nord'),
			`Präfix steht nicht vor dem Namen: ${h1}`
		);
		assert.equal(zaehle(body, 'probe-praefix'), 1, 'Präfix nicht genau einmal');
	});

	test('ohne namePrefix: die Überschrift ist genau der Name', async () => {
		const body = await html(vergleichProps());
		const h1 = (/<h1[^>]*>([\s\S]*?)<\/h1>/.exec(body)?.[1] ?? '').replace(/<!--[\s\S]*?-->/g, '');
		assert.equal(h1.trim(), 'Dolomiten Süd');
	});

	test('mit saveController: save-indicator genau einmal', async () => {
		const body = await html(await tripSatz());
		assert.equal(zaehle(body, 'save-indicator'), 1, 'der Baustein rendert den Chip nicht genau einmal');
	});

	test('ohne saveController: kein save-indicator', async () => {
		assert.equal(zaehle(await html(vergleichProps()), 'save-indicator'), 0);
		assert.equal(zaehle(await html(tripProps()), 'save-indicator'), 0);
	});

	test('Vergleich-Satz MIT saveController: Chip ebenfalls genau einmal (kein kind-Zweig)', async () => {
		const body = await html(vergleichProps({ saveController: await controller() }));
		assert.equal(zaehle(body, 'save-indicator'), 1);
	});
});

describe('#2284 S2 AC-16 — dieselbe Gerüststruktur, keine Markup-Verzweigung nach kind', () => {
	// Gleiche Props, nur `kind` verschieden: jede Abweichung im Markup (außer dem
	// Attribut data-kind) ist ein `kind`-Zweig (Mutationsgegenprobe (a) der S2-Spec).
	const ohneKind = (b: string) => b.replace(/data-kind="[^"]*"/g, 'data-kind="X"');

	test('voller Trip-Satz (titleTestid, namePrefix, saveController): kind="trip" ≡ kind="vergleich"', async () => {
		const satz = await tripSatz();
		const t = await html({ ...satz, kind: 'trip' });
		const v = await html({ ...satz, kind: 'vergleich' });
		assert.equal(ohneKind(t), ohneKind(v), 'das Markup verzweigt nach kind');
	});

	test('Vergleich-Satz ohne Zusatz-Props: kind="trip" ≡ kind="vergleich"', async () => {
		const satz = vergleichProps();
		const t = await html({ ...satz, kind: 'trip' });
		const v = await html({ ...satz, kind: 'vergleich' });
		assert.equal(ohneKind(t), ohneKind(v), 'das Markup verzweigt nach kind');
	});

	test('beide Sätze teilen das Grundgerüst (Überschrift, Region-Zeile, Kachelreihe)', async () => {
		const t = geruest(await html(await tripSatz()), 'trip', TRIP_OPTIONEN);
		const v = geruest(await html(vergleichProps()), 'compare-hub', VERGLEICH_OPTIONEN);
		for (const teil of ['button[PFX-name-edit-toggle]', 'button[PFX-region-edit-toggle]', 'button[PFX-profil-option-OPT]']) {
			assert.ok(t.includes(teil), `Trip-Gerüst ohne ${teil}`);
			assert.ok(v.includes(teil), `Vergleich-Gerüst ohne ${teil}`);
		}
		assert.ok(t.some((x) => x.startsWith('h1')) && v.some((x) => x.startsWith('h1')), 'Überschrift fehlt');
	});
});

describe('#2284 S2 AC-16 / AC-3 — Region-Platzhalter „—" (Normalisierung im Baustein)', () => {
	for (const [label, region, erwartet] of [
		['region="" ⇒ „—"', '', '—'],
		['region=undefined ⇒ „—"', undefined, '—'],
		['region="Nord" ⇒ „Nord"', 'Nord', 'Nord']
	] as const) {
		test(`Vergleich: ${label}`, async () => {
			const body = await html(vergleichProps({ region }));
			assert.equal(regionText(body, 'compare-hub'), erwartet);
		});
		test(`Trip: ${label}`, async () => {
			const body = await html(await tripSatz({ region }));
			assert.equal(regionText(body, 'trip'), erwartet);
		});
	}
});

// ─── Issue #2284 S2 v1.1 — AC-16 / AC-4: Handy-Knopf im selben Markup ────────
// Spec v1.1, Entscheidung 14: Auf dem Handy zeigt der Baustein die Aktivität als
// EINEN Knopf `{p}-profil-knopf` mit der gewählten Aktivität (z. B. „Trekking ▾"),
// Tippen öffnet die Auswahl `{p}-profil-auswahl` mit eigenen Options-testids
// `{p}-profil-auswahl-option-<wert>`. Desktop behält die Kachelreihe. Umschaltung
// NUR per CSS-Breakpoint ⇒ im SSR-Markup stehen Kacheln UND Knopf, in beiden
// Sätzen gleich (keine Verzweigung nach kind). Knopf trägt `data-selected-value`.
// Sichtbarkeit Knopf ⇔ Kacheln je Viewport beweist die E2E (SSR kennt keine
// Breakpoints).
// RED vor v1.1: der Baustein rendert keinen Knopf.

const NEUTRAL = 'Aktivität wählen';

function knopf(body: string, prefix: string): { tag: string; text: string } | null {
	const m = new RegExp(`<button([^>]*data-testid="${prefix}-profil-knopf"[^>]*)>([\\s\\S]*?)</button>`).exec(body);
	if (!m) return null;
	const text = m[2]
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
	return { tag: m[1], text };
}

describe('#2284 S2 v1.1 AC-16 — Kacheln UND Handy-Knopf im selben Markup', () => {
	for (const [satz, prefix, props, optionen] of [
		['Trip', 'trip', () => tripSatz(), TRIP_OPTIONEN],
		['Vergleich', 'compare-hub', async () => vergleichProps(), VERGLEICH_OPTIONEN]
	] as const) {
		test(`${satz}: alle Kacheln und genau ein Knopf ${prefix}-profil-knopf`, async () => {
			const body = await html(await props());
			for (const o of optionen) {
				assert.equal(zaehle(body, `${prefix}-profil-option-${o.value}`), 1, `Kachel ${o.value} fehlt/doppelt`);
			}
			assert.equal(zaehle(body, `${prefix}-profil-knopf`), 1, `AC-16: ${prefix}-profil-knopf nicht genau einmal im Markup`);
		});
	}

	test('Trip: Knopftext ist das Label der gewählten Aktivität („Trekking"), data-selected-value="trekking"', async () => {
		const k = knopf(await html(await tripSatz()), 'trip');
		assert.ok(k, 'AC-16: kein Knopf trip-profil-knopf');
		assert.ok(k.text.includes('Trekking'), `AC-4: Knopftext ohne gewählte Aktivität: „${k.text}"`);
		assert.ok(!k.text.includes('Skitour'), `AC-4: Knopftext nennt eine nicht gewählte Aktivität: „${k.text}"`);
		assert.match(k.tag, /data-selected-value="trekking"/, `Knopf ohne data-selected-value: ${k.tag}`);
	});

	test('Trip: gewählte Aktivität NICHT die erste Option ⇒ Knopftext folgt der Prop (Mutation i)', async () => {
		const k = knopf(await html(await tripSatz({ profile: 'skitour' })), 'trip');
		assert.ok(k, 'AC-16: kein Knopf trip-profil-knopf');
		assert.ok(k.text.includes('Skitour'), `AC-4: Knopftext zeigt nicht „Skitour": „${k.text}"`);
		assert.ok(!k.text.includes('Trekking'), `AC-4: Knopftext zeigt die erste statt der gewählten Option: „${k.text}"`);
		assert.match(k.tag, /data-selected-value="skitour"/);
	});

	test('Trip ohne Aktivität: neutraler Knopftext „Aktivität wählen", data-selected-value leer', async () => {
		const k = knopf(await html(await tripSatz({ profile: undefined })), 'trip');
		assert.ok(k, 'AC-16: kein Knopf trip-profil-knopf');
		assert.ok(k.text.includes(NEUTRAL), `AC-4: ohne Wert fehlt der neutrale Text: „${k.text}"`);
		for (const o of TRIP_OPTIONEN) assert.ok(!k.text.includes(o.label), `Knopf nennt ${o.label} ohne Wert`);
		assert.match(k.tag, /data-selected-value=""|^(?![\s\S]*data-selected-value=)/, `data-selected-value nicht leer: ${k.tag}`);
	});

	test('Vergleich: Knopftext ist das Label des gewählten Profils („Wintersport", nicht die erste Option)', async () => {
		const k = knopf(await html(vergleichProps({ profile: 'wintersport' })), 'compare-hub');
		assert.ok(k, 'AC-16: kein Knopf compare-hub-profil-knopf');
		assert.ok(k.text.includes('Wintersport'), `AC-4: Knopftext ohne gewähltes Profil: „${k.text}"`);
		assert.ok(!k.text.includes('Allgemein'), `AC-4: Knopftext zeigt die erste Option: „${k.text}"`);
		assert.match(k.tag, /data-selected-value="wintersport"/);
	});

	test('Vergleich ohne Profil: neutraler Knopftext', async () => {
		const k = knopf(await html(vergleichProps({ profile: undefined })), 'compare-hub');
		assert.ok(k, 'AC-16: kein Knopf compare-hub-profil-knopf');
		assert.ok(k.text.includes(NEUTRAL), `ohne Wert fehlt der neutrale Text: „${k.text}"`);
	});

	// Spec v1.2, Entscheidung 14 / AC-4 / AC-16 (Mutation u): der neutrale Knopftext
	// ist in BEIDEN Hubs „Aktivität wählen" — derselbe Text, keine kind-Verzweigung;
	// „Profil wählen" kommt in keiner Ausgabe vor (auch nicht außerhalb des Knopfs).
	test('ohne Wert: Trip und Vergleich zeigen denselben neutralen Knopftext, „Profil wählen" nirgends', async () => {
		const tripHtml = await html(await tripSatz({ profile: undefined }));
		const vergleichHtml = await html(vergleichProps({ profile: undefined }));
		const t = knopf(tripHtml, 'trip');
		const v = knopf(vergleichHtml, 'compare-hub');
		assert.ok(t && v, 'AC-16: Knopf fehlt in mindestens einem Satz');
		assert.equal(t.text, v.text, `AC-16: neutraler Knopftext unterscheidet sich (Trip „${t.text}" / Vergleich „${v.text}")`);
		assert.ok(v.text.includes(NEUTRAL), `AC-4: Vergleich ohne Profil zeigt nicht „${NEUTRAL}": „${v.text}"`);
		for (const body of [
			tripHtml,
			vergleichHtml,
			await html(await tripSatz()),
			await html(vergleichProps({ profile: 'wintersport' }))
		]) {
			assert.ok(!/Profil w(ä|&auml;|&#228;)hlen/.test(body), 'v1.2: „Profil wählen" darf in keiner Ausgabe vorkommen');
		}
	});

	test('Gerüst beider Sätze enthält Knopf und Auswahl-Optionen (kein kind-Zweig)', async () => {
		const t = geruest(await html(await tripSatz()), 'trip', TRIP_OPTIONEN);
		const v = geruest(await html(vergleichProps()), 'compare-hub', VERGLEICH_OPTIONEN);
		for (const teil of ['button[PFX-profil-knopf]', 'button[PFX-profil-auswahl-option-OPT]']) {
			assert.ok(t.includes(teil), `Trip-Gerüst ohne ${teil}: ${t.join(' ')}`);
			assert.ok(v.includes(teil), `Vergleich-Gerüst ohne ${teil}: ${v.join(' ')}`);
		}
	});
});
