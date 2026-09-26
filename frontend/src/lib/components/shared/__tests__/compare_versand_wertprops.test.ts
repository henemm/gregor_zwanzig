// TDD RED — Issue #2276 Scheibe S6e (Epic #2345): die Versand-Flaeche des
// Ortsvergleichs (`VersandTab.svelte`, `context="vergleich"`) arbeitet auf
// reinen WERTPROPS + Rueckrufen statt auf dem Wizard-Zustandsobjekt `wiz`. Das
// Buendel baut eine einzige Funktion `compare/versandPropsAus.ts`, die alle
// DREI Vergleichs-Mounts identisch einspeisen.
//
// Spec: docs/specs/modules/rework_2276_s6e_versand.md
//   AC-1  VersandTab ist im Vergleichs-Zweig wertprop-rein (kein `wiz`)
//   AC-2  Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Flaeche B (Hub)
//   AC-3  alle drei Vergleichs-Mounts speisen dasselbe Buendel ein, Aufrufform
//         geprueft (Markup-Ausdruck, nie eine Skript-Variable)
//   AC-4  `sendEmail` bleibt eigenstaendig interaktiv, ausserhalb der
//         Speicherweg-Bruecke `versandZustandsBruecke`
//   AC-5  die drei toten Legacy-Restfelder erreichen den Speicherweg: die
//         Bruecke reicht sie unveraendert an `versandSnapshotAus` weiter
//   AC-6  (Ratsche `context_herkunft_zweige_eingefroren.test.ts` — reiner
//         Strukturwaechter, siehe Vertragserweiterung dort statt hier)
//
// WAS HIER GEMESSEN WIRD — und was nicht:
//   Die Kernsuite ist SSR-only (`node --test` + `svelte/server`, kein DOM).
//   `$effect` laeuft dort nie von selbst. Diese Datei wertet deshalb die ECHTE
//   Herleitung des Instanz-Skripts gegen gesaete Props aus
//   (`svelteInstanzPruefstand.ts`) und FUEHRT den einen `$effect`-Rumpf, der
//   `vergleichSpeicherung` nennt, wirklich aus (`effekteVon()`). Gemessen
//   wird, was der Code mit den Props TUT — nicht, ob ein Bezeichner im
//   Quelltext steht. Der Wirkort „Browser" (Klick -> PUT -> Reload) ist damit
//   NICHT abgedeckt; dafuer bleibt `compare-versand-speichert-selbst.spec.ts`
//   (S5, unveraendert in der CI-Ampel) zustaendig (AC-7 der Spec).
//
// 🔴 VAKUUM-FALLE, bewusst entschaerft: `wiz` wird EXPLIZIT als `undefined`
// gesaet (nicht weggelassen) — solange der Quelltext `wiz` noch referenziert,
// liefert das einen deterministischen, sauber lesbaren roten Befund statt
// eines stillen ReferenceError, den `umgebungFuer()` beim Herleiten von
// `vergleichSpeicherung` schluckt. Nach der Umstellung ist der Saat-Eintrag
// wirkungslos, weil der Name nicht mehr vorkommt — genau das haelt AC-1 fest.
//
// Pfadregel #1409: alles relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/compare_versand_wertprops.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import {
	umgebungFuer,
	werte,
	effekteVon,
	findeKomponenten,
	attributNamen,
	type Knoten
} from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const COMPONENTS = join(SHARED, '..');
const TAB = join(SHARED, 'VersandTab.svelte');
const HUB = join(COMPONENTS, 'compare', 'CompareTabs.svelte');
const ANLEGE = join(COMPONENTS, 'compare-new', 'CompareNewEditor.svelte');
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..');

function holeAusdruck(u: Knoten, ausdruck: string, warum: string): unknown {
	try {
		return werte(ausdruck, u);
	} catch (e) {
		return assert.fail(
			`${warum}\n  \`${ausdruck}\` liess sich nicht auswerten: ${(e as Error).message}\n` +
				`  Herleitbar waren: ${JSON.stringify(Object.keys(u).sort())}`
		);
	}
}

/** Die WIRKSAM gebundenen Prop-Namen: das Destrukturierungsmuster von
 *  `$props()`, nicht der Kommentar der TS-Schnittstelle darueber. */
function gebundeneProps(ast: Knoten, quelle: string): string[] {
	const muster = ((ast.instance?.content?.body as Knoten[]) ?? [])
		.filter((s) => s.type === 'VariableDeclaration')
		.flatMap((s) => (s.declarations as Knoten[]) ?? [])
		.find(
			(d) =>
				d.id?.type === 'ObjectPattern' &&
				d.init &&
				quelle.slice(d.init.start, d.init.end).includes('$props()')
		);
	assert.ok(muster, 'Kein `let { … } = $props()` im Instanz-Skript gefunden.');
	return ((muster!.id.properties as Knoten[]) ?? [])
		.map((p) => (p.key?.name ?? p.argument?.name) as string)
		.filter(Boolean);
}

/** Alle Zeilennummern, an denen der Teilbaum den Bezeichner `name` nennt. */
function nennungen(knoten: unknown, quelle: string, name: string): string[] {
	const treffer: string[] = [];
	function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) {
			n.forEach(lauf);
			return;
		}
		const k = n as Knoten;
		if (k.type === 'Identifier' && k.name === name && typeof k.start === 'number') {
			treffer.push(`Zeile ${quelle.slice(0, k.start).split('\n').length}`);
		}
		for (const key of Object.keys(k)) {
			if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		}
	}
	lauf(knoten);
	return treffer;
}

/** Die in AC-1 woertlich freigegebenen Wertprops (Klasse A + Klasse B `sendEmail`). */
const WERTPROPS = [
	'sendEmail',
	'sendTelegram',
	'sendSms',
	'morningEnabled',
	'morningTime',
	'eveningEnabled',
	'eveningTime',
	'endDate'
] as const;

/** Die drei toten Legacy-Restfelder (Klasse C) — Wertprop OHNE eigenen Rueckruf. */
const LEGACY_LESEWERTE = ['alertCooldownMinutes', 'alertQuietFrom', 'alertQuietTo'] as const;

/** Die acht `onXChange`-Rueckrufe (Klasse A + Klasse B). */
const RUECKRUFE = [
	'onSendEmailChange',
	'onSendTelegramChange',
	'onSendSmsChange',
	'onMorningEnabledChange',
	'onMorningTimeChange',
	'onEveningEnabledChange',
	'onEveningTimeChange',
	'onEndDateChange'
] as const;

/** Die generische Rollback-Senke fuer die drei toten Legacy-Restfelder — KEIN
 *  Bedienelement schreibt hierueber (Muster `onAlarmFeldSetzen`, S6c). */
const ROLLBACK_SENKE = 'onVersandFeldSetzen';

/** Unveraenderte Props — weder Wertprop noch Rueckruf dieser Scheibe. */
const UNVERAENDERTE_PROPS = [
	'context',
	'trip',
	'onTripUpdate',
	'saveController',
	'reportConfig',
	'onChannelChange',
	'onJump',
	'activation',
	'preset',
	'onCompareUpdate',
	'enqueueHubWrite'
] as const;

/** Saat fuer den ORGANISMUS im Vergleichs-Zweig — ausschliesslich Wertprops.
 *  `wiz` wird explizit als `undefined` gesaet (siehe Kopfkommentar). */
function saatVergleich(zusatz: Knoten = {}): Knoten {
	return {
		context: 'vergleich',
		wiz: undefined,
		untrack: (fn: () => unknown) => fn(),
		api: { put: async () => ({}) },
		// acht Wertprops
		sendEmail: false,
		sendTelegram: false,
		sendSms: false,
		morningEnabled: true,
		morningTime: '07:00',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: null,
		// drei Legacy-Lesewerte (Klasse C)
		alertCooldownMinutes: undefined,
		alertQuietFrom: undefined,
		alertQuietTo: undefined,
		// neun Rueckrufe — vom Aufrufer ueberschrieben
		onSendEmailChange: () => {},
		onSendTelegramChange: () => {},
		onSendSmsChange: () => {},
		onMorningEnabledChange: () => {},
		onMorningTimeChange: () => {},
		onEveningEnabledChange: () => {},
		onEveningTimeChange: () => {},
		onEndDateChange: () => {},
		onVersandFeldSetzen: () => {},
		// unveraenderte Props
		trip: undefined,
		onTripUpdate: undefined,
		saveController: null,
		reportConfig: undefined,
		onChannelChange: undefined,
		onJump: undefined,
		activation: undefined,
		preset: null,
		onCompareUpdate: () => {},
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		...zusatz
	};
}

// ── AC-1 ────────────────────────────────────────────────────────────────────

describe('AC-1: VersandTab leitet den Vergleichs-Zweig aus Wertprops her', () => {
	test('die Prop-Schnittstelle bindet alle elf Wertprops/Lesewerte, alle neun Rueckrufe und die unveraenderten Props', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const namen = gebundeneProps(ast, quelle);

		for (const pflicht of [...WERTPROPS, ...LEGACY_LESEWERTE, ...RUECKRUFE, ROLLBACK_SENKE]) {
			assert.ok(
				namen.includes(pflicht),
				`AC-1 FAIL: die Komponente bindet kein \`${pflicht}\`. Gebunden: ${[...namen].sort().join(', ')}`
			);
		}
		for (const unveraendert of UNVERAENDERTE_PROPS) {
			assert.ok(
				namen.includes(unveraendert),
				`AC-1 FAIL: die unveraenderte Prop \`${unveraendert}\` ist verschwunden — diese ` +
					'Scheibe tauscht nur die Wizard-Quelle aus, sie nimmt der Flaeche A (Trip) nichts weg.'
			);
		}
		assert.ok(
			!namen.includes('wiz'),
			'AC-1 FAIL: `wiz` wird weiterhin als Prop gebunden. Die Umstellung ist an allen drei ' +
				'Vergleichs-Mounts vollstaendig oder sie unterbleibt.'
		);
	});

	test('nirgends im Instanz-Skript oder Markup steht noch eine `wiz`-Referenz', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const treffer = [
			...nennungen(ast.instance?.content, quelle, 'wiz'),
			...nennungen(ast.fragment, quelle, 'wiz')
		];
		assert.deepStrictEqual(
			treffer,
			[],
			`AC-1 FAIL: \`wiz\` wird noch ${treffer.length}x referenziert (${treffer.join(', ')}). ` +
				'„Wertprop wenn da, sonst `wiz`" ist genau das Anti-Muster, das S6 beseitigen soll ' +
				'(Spec § Known Limitations).'
		);
	});

	test('der Typ-Import von `CompareWizardState` ist verschwunden', async () => {
		const { ast, quelle } = await umgebungFuer(TAB, saatVergleich());
		const importe = ((ast.instance?.content?.body as Knoten[]) ?? [])
			.filter((s) => s.type === 'ImportDeclaration')
			.map((s) => quelle.slice(s.start, s.end));
		assert.deepStrictEqual(
			importe.filter((q) => q.includes('CompareWizardState')),
			[],
			'AC-1 FAIL: `VersandTab.svelte` importiert weiterhin den Wizard-Typ aus compare/ — die ' +
				'Klebeschicht bliebe damit Teil der Schnittstelle des geteilten Organismus.'
		);
	});
});

// ── AC-2 Wirkort-Guard + AC-4 Bruecken-Inhalt ────────────────────────────────
// Beide Bloecke teilen sich denselben Messaufbau: der eine `$effect`, der
// `vergleichSpeicherung` nennt (`VersandTab.svelte:283-291`), wird ueber
// `effekteVon()` registriert und wirklich ausgefuehrt. `versandSnapshotAus`
// wird durch einen Spion ersetzt (Vorbild AC-4 aus `compare_alarme_wertprops
// .test.ts`) — was er als Argument sieht, IST der Zustand, den die neue
// Bruecke `versandZustandsBruecke` dem Speicherweg reicht.

/** `vergleichSpeicherung` wird BEWUSST NICHT gesaet — die Umgebung leitet sie
 *  aus dem ECHTEN Produktivcode her (Fixture-Falle #2387: eine gesaete Null
 *  liesse genau die Bedingungskette aus, die den Wert erst null macht). */
async function effektAufbauen(zusatz: Knoten) {
	const gesehen: unknown[] = [];
	const spion = (ziel: unknown) => {
		gesehen.push(ziel);
		return {};
	};
	const { ast, quelle, u } = await umgebungFuer(
		TAB,
		saatVergleich({ versandSnapshotAus: spion, ...zusatz })
	);
	assert.strictEqual(
		u.versandSnapshotAus,
		spion,
		'Messaufbau kaputt: `versandSnapshotAus` ist nicht der Spion — dann stuende dort die echte ' +
			'Funktion, der Mitschnitt bliebe immer leer und der Test waere vakuum-gruen.'
	);
	assert.ok(
		'vergleichSpeicherung' in u,
		'Messaufbau kaputt: `vergleichSpeicherung` liess sich aus dem Produktivcode nicht herleiten ' +
			'(`umgebungFuer` schluckt Deklarations-Fehler still) — dann misst dieser Block nichts.'
	);
	const rueckrufe = effekteVon(ast, quelle, u, 'vergleichSpeicherung');
	assert.strictEqual(
		rueckrufe.length,
		1,
		`Messaufbau kaputt: ${rueckrufe.length} $effect-Ruempfe nennen \`vergleichSpeicherung\` ` +
			'(erwartet: genau einer). Eine leere Liste hiesse „nichts ausgefuehrt" — jede Zusicherung ' +
			'darunter waere dann wertlos.'
	);
	return { u, rueckruf: rueckrufe[0], gesehen };
}

function controller(): Knoten {
	return { schedule: () => {}, setDirty: () => {}, cancel: () => {}, markPristine: () => {} };
}

/** Fläche B (Hub): einzige Stelle mit `preset` + `saveController`. */
const flaecheB = (zusatz: Knoten = {}): Knoten => ({
	preset: { id: 'p1', name: 'x', location_ids: [], display_config: {} },
	saveController: controller(),
	sendTelegram: true,
	sendEmail: true,
	...zusatz
});

describe('AC-2 Wirkort-Guard: der Selbst-Speicher-Effekt wirkt nur an Flaeche B (Hub)', () => {
	test('Flaeche B (Hub, preset + saveController gesetzt): der Effekt meldet den Versandstand', async () => {
		const { u, rueckruf, gesehen } = await effektAufbauen(flaecheB());
		rueckruf();
		assert.strictEqual(
			gesehen.length,
			1,
			'AC-2 FAIL: an Flaeche B (preset + saveController gesetzt) meldet der Effekt-Rumpf den ' +
				'Versandstand nicht an `versandSnapshotAus`. Ohne diese Richtung misst der Guard nur ' +
				'„der Effekt laeuft nie" — vakuum-gruen.'
		);
		assert.ok(
			u.vergleichSpeicherung,
			'AC-2 FAIL: mit `preset` + `saveController` muss der Produktivcode eine ' +
				'Vergleichs-Speicherung erzeugen.'
		);
	});

	test('Flaeche A (Trip, context="route"): kein Versandstand gemeldet, keine Vergleichs-Speicherung', async () => {
		const { u, rueckruf, gesehen } = await effektAufbauen({
			context: 'route',
			trip: { id: 't-1' }
		});
		rueckruf();
		assert.strictEqual(
			gesehen.length,
			0,
			'AC-2 FAIL: der Trip-Zweig meldet einen Versandstand an den Vergleichs-Speicherweg. ' +
				'Faellt der Guard weg, laeuft die Trip in den Vergleichs-Speicherweg.'
		);
		assert.strictEqual(
			u.vergleichSpeicherung,
			null,
			'AC-2 FAIL: an der Trip darf es keine Vergleichs-Speicherung geben.'
		);
	});

	test('Flaeche C/D (Anlegen, ohne preset/saveController): kein Versandstand gemeldet, keine Vergleichs-Speicherung', async () => {
		const { u, rueckruf, gesehen } = await effektAufbauen({});
		rueckruf();
		assert.strictEqual(
			gesehen.length,
			0,
			'AC-2 FAIL: die Anlege-Seite meldet einen Versandstand, obwohl sie keine Basis und ' +
				'keinen Speicher-Controller hat — dort darf es keinen eigenen Speicherweg geben (sonst ' +
				'PUT auf einen Vergleich, den es noch nicht gibt).'
		);
		assert.strictEqual(
			u.vergleichSpeicherung,
			null,
			'AC-2 FAIL: auf der Anlege-Seite darf es keine Vergleichs-Speicherung geben.'
		);
	});
});

// ── AC-4 ─────────────────────────────────────────────────────────────────────

describe('AC-4: `sendEmail` bleibt eigenstaendig interaktiv, ausserhalb der Speicherweg-Bruecke', () => {
	test('die Bruecke, die der Effekt an `versandSnapshotAus` reicht, fuehrt `sendEmail` NICHT', async () => {
		const { rueckruf, gesehen } = await effektAufbauen(flaecheB({ sendTelegram: true, sendEmail: true }));
		rueckruf();
		assert.strictEqual(
			gesehen.length,
			1,
			'Messaufbau kaputt: siehe AC-2, Flaeche B — ohne einen gemeldeten Stand misst dieser ' +
				'Test nichts.'
		);
		const zustand = gesehen[0] as Record<string, unknown>;
		assert.strictEqual(
			zustand.sendTelegram,
			true,
			'Messaufbau kaputt: die Bruecke fuehrt nicht einmal die Snapshot-Felder, die sie ' +
				'fuehren MUSS — dann sagt die Abwesenheit von `sendEmail` gleich darunter nichts.'
		);
		assert.strictEqual(
			zustand.sendEmail,
			undefined,
			'AC-4 FAIL: die Bruecke, die `versandSnapshotAus()` sieht, fuehrt `sendEmail`. ' +
				'`VersandSnapshot`/`VersandHydrationTarget` kennen `sendEmail` nicht — ' +
				'`baueVersandNutzlast` sendet es nie. Naehme die Bruecke es dennoch auf, saehe der ' +
				'Payload-Baustein ein Feld, das er ignoriert: reines Rauschen im Diff-Gate.'
		);
	});
});

// ── AC-5 ─────────────────────────────────────────────────────────────────────
// Derselbe Messaufbau wie AC-2/AC-4, andere Blickrichtung: nicht die
// ABWESENHEIT von `sendEmail`, sondern die ANWESENHEIT der drei toten
// Legacy-Restfelder im Zustand, den der Effekt dem Speicherweg reicht.
// Warum hier und nicht im bestehenden S5-Netz: `versand_nutzlast_verliert_
// keine_daten.test.ts` ruft `baueVersandNutzlast` mit einem handgebauten
// Snapshot-Objekt auf und geht nie durch `VersandTab.svelte`s `werte()` —
// faellt dort ein Feld weg, bleibt jener Test strukturell gruen (Adversary
// F-S6e-1). Die Verdrahtung IM Baustein hat sonst keinen Kern-Test.

describe('AC-5: die drei toten Legacy-Restfelder erreichen den Speicherweg unveraendert', () => {
	test('die Bruecke, die der Effekt an `versandSnapshotAus` reicht, fuehrt alle drei Legacy-Werte', async () => {
		// Gesaet wird NICHT der Saat-Default `undefined` (sonst waere der Test
		// mit und ohne Verdrahtung gleich gruen), sondern drei unterscheidbare
		// Werte — auch eine Feld-Vertauschung faellt damit auf.
		const { rueckruf, gesehen } = await effektAufbauen(
			flaecheB({ alertCooldownMinutes: 42, alertQuietFrom: '23:15', alertQuietTo: '05:45' })
		);
		rueckruf();
		assert.strictEqual(
			gesehen.length,
			1,
			'Messaufbau kaputt: siehe AC-2, Flaeche B — ohne einen gemeldeten Stand misst dieser ' +
				'Test nichts.'
		);
		const zustand = gesehen[0] as Record<string, unknown>;
		for (const [feld, erwartet] of [
			['alertCooldownMinutes', 42],
			['alertQuietFrom', '23:15'],
			['alertQuietTo', '05:45']
		] as const) {
			assert.strictEqual(
				zustand[feld],
				erwartet,
				`AC-5 FAIL: die Bruecke reicht \`${feld}\` nicht an den Speicherweg weiter ` +
					`(gesehen: ${JSON.stringify(zustand[feld])}, gesaet: ${JSON.stringify(erwartet)}). ` +
					'Das Feld hat kein Bedienelement, muss aber durch Snapshot/Nutzlast/Rollback laufen — ' +
					'faellt es aus `werte()`, sendet `baueVersandNutzlast` `undefined` und der naechste ' +
					'PUT loescht den gespeicherten Wert (BUG-DATALOSS-GR221-Klasse).'
			);
		}
	});
});

// ── AC-3 Mounts ─────────────────────────────────────────────────────────────

/** Die `{...versandPropsAus(x)}`-Streuung einer Einbettung — als AST, nicht
 *  als Textmuster. Liefert den Quelltext des Aufrufs und den Namen des
 *  uebergebenen Zustands-Bezeichners. */
function streuung(
	einbettung: Knoten,
	quelle: string
): { ausdruck: string; zustand: string } | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'SpreadAttribute') continue;
		const e = a.expression as Knoten;
		if (e?.type !== 'CallExpression') continue;
		const callee = e.callee as Knoten;
		if (callee?.type !== 'Identifier' || callee.name !== 'versandPropsAus') continue;
		const arg = (e.arguments as Knoten[])?.[0];
		if (arg?.type !== 'Identifier') continue;
		return { ausdruck: quelle.slice(e.start, e.end), zustand: arg.name as string };
	}
	return null;
}

function einbettungen(datei: string): { quelle: string; treffer: Knoten[] } {
	const quelle = readFileSync(datei, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });
	return { quelle, treffer: findeKomponenten(ast, 'VersandTab') };
}

/** Ein vollstaendig besetzter Wizard-Zustand (alle elf Versandfelder). */
function wizStand(): Knoten {
	return {
		sendEmail: true,
		sendTelegram: true,
		sendSms: false,
		morningEnabled: true,
		morningTime: '06:30',
		eveningEnabled: true,
		eveningTime: '19:00',
		endDate: '2026-10-01',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00'
	};
}

const MOUNTS: [string, string, number][] = [
	['Hub /compare/[id] (Mount B)', HUB, 1],
	['Anlege-Seite /compare/new, Desktop + Mobil (Mounts C und D)', ANLEGE, 2]
];

describe('AC-3: alle drei Vergleichs-Mounts speisen dasselbe Buendel ein', () => {
	for (const [was, datei, anzahl] of MOUNTS) {
		test(`${was}: ruft \`versandPropsAus(<zustand>)\` IM Markup-Ausdruck auf und reicht kein \`wiz\` mehr durch`, () => {
			const { quelle, treffer } = einbettungen(datei);
			assert.strictEqual(
				treffer.length,
				anzahl,
				`AC-3 FAIL: ${treffer.length} VersandTab-Einbettungen in ${relative(FRONTEND, datei)} ` +
					`statt ${anzahl}.`
			);
			for (const [i, einbettung] of treffer.entries()) {
				const s = streuung(einbettung, quelle);
				assert.ok(
					s,
					`AC-3 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} streut kein ` +
						'`{...versandPropsAus(<zustand>)}`. 🔴 Form-Auflage der Spec (Design-Entscheidung ' +
						'1): der Aufruf steht IM Markup-Ausdruck, nicht in einer Skript-Variablen — ein ' +
						'einmal berechnetes, eingefrorenes Objekt bestuende SSR-Pruefstand und ' +
						'AST-Waechter anstandslos und fiele erst im Browser auf. Attribute heute: ' +
						`${attributNamen(einbettung).join(', ') || '—'}.`
				);
				assert.ok(
					!attributNamen(einbettung).includes('wiz'),
					`AC-3 FAIL: Einbettung ${i + 1} in ${relative(FRONTEND, datei)} reicht weiterhin ` +
						'`wiz` durch.'
				);
			}
		});

		test(`${was}: das gestreute Buendel traegt alle elf Werte/Lesewerte und alle acht Rueckrufe`, async () => {
			const { quelle: q0, treffer } = einbettungen(datei);
			const gestreut = treffer.map((e) => streuung(e, q0));
			assert.ok(
				gestreut.length > 0 && gestreut.every((s) => s !== null),
				`AC-3 FAIL: nicht jede VersandTab-Einbettung in ${relative(FRONTEND, datei)} streut ` +
					'`versandPropsAus(...)` — siehe vorigen Test.'
			);

			for (const [i, s] of gestreut.entries()) {
				const wiz = wizStand();
				const { u } = await umgebungFuer(datei, {
					[s!.zustand]: wiz,
					untrack: (fn: () => unknown) => fn()
				});
				const buendel = holeAusdruck(
					u,
					s!.ausdruck,
					`AC-3 FAIL: \`${s!.ausdruck}\` (Einbettung ${i + 1}) laesst sich nicht auswerten.`
				) as Knoten;
				assert.ok(
					buendel && typeof buendel === 'object',
					`AC-3 FAIL: \`${s!.ausdruck}\` liefert kein Objekt.`
				);

				for (const feld of [...WERTPROPS, ...LEGACY_LESEWERTE]) {
					assert.deepStrictEqual(
						buendel[feld],
						wiz[feld],
						`AC-3 FAIL: das Buendel traegt \`${feld}\` nicht unveraendert aus dem ` +
							`Wizard-Zustand (Einbettung ${i + 1}, ${relative(FRONTEND, datei)}). Jedes ` +
							'Feld, das der Weg vom Zustand zum Baustein verliert, faellt beim naechsten ' +
							'Speichern aus der Nutzlast.'
					);
				}
				for (const r of RUECKRUFE) {
					assert.strictEqual(
						typeof buendel[r],
						'function',
						`AC-3 FAIL: dem Buendel fehlt der Rueckruf \`${r}\` (Einbettung ${i + 1}, ` +
							`${relative(FRONTEND, datei)}). Ohne Rueckruf verpufft die zugehoerige Geste ` +
							'an diesem Mount — und Mounts C/D sind in der CI-Ampel strukturell unbewacht.'
					);
				}
				assert.strictEqual(
					typeof buendel[ROLLBACK_SENKE],
					'function',
					`AC-3 FAIL: dem Buendel fehlt die Rollback-Senke \`${ROLLBACK_SENKE}\` (Einbettung ` +
						`${i + 1}, ${relative(FRONTEND, datei)}) — ohne sie bliebe ein gescheiterter PUT ` +
						'ohne Schreibweg fuer die drei toten Legacy-Restfelder.'
				);

				// Rueckschreiben: jeder Rueckruf trifft GENAU sein Feld im Zustand.
				(buendel.onSendTelegramChange as (v: boolean) => void)(!wiz.sendTelegram);
				assert.strictEqual(
					wiz.sendTelegram,
					!wizStand().sendTelegram,
					'AC-3 FAIL: `onSendTelegramChange` schreibt nicht nach `sendTelegram`.'
				);
				(buendel.onEndDateChange as (v: string | null) => void)(null);
				assert.strictEqual(
					wiz.endDate,
					null,
					'AC-3 FAIL: `onEndDateChange` schreibt nicht nach `endDate` — „Bis auf Weiteres" ' +
						'bliebe wirkungslos.'
				);
				(buendel[ROLLBACK_SENKE] as (feld: string, wert: unknown) => void)(
					'alertCooldownMinutes',
					99
				);
				assert.strictEqual(
					wiz.alertCooldownMinutes,
					99,
					`AC-3 FAIL: \`${ROLLBACK_SENKE}\` schreibt nicht auf das benannte Feld zurueck — ` +
						'der diff-basierte Rollback der drei toten Legacy-Restfelder liefe ins Leere.'
				);
			}
		});
	}
});
