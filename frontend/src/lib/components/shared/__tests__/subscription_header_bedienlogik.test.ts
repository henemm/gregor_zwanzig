// Issue #2284 S1, Fix-Loop 1 (Adversary F002–F005): Bedienlogik des geteilten
// Kopf-Bausteins `SubscriptionHeader`. Spec:
// docs/specs/modules/feat_2284_s1_subscription_header.md (Entscheidung 7, AC-4,
// AC-6, AC-10).
//
// Die Kernsuite ist SSR-only (kein DOM, keine Klicks). Gemessen wird deshalb
// der ECHTE Funktionskörper des Instanz-Skripts (start/cancel/save) gegen
// gesäte Props (svelteInstanzPruefstand.ts) und der ECHTE Attribut-Ausdruck
// im Markup, ausgewertet gegen dieselbe Umgebung — kein Mock, kein Datei-Grep.
// Klickverhalten im Browser bewacht frontend/e2e/compare-hub-kopf-einmal.spec.ts.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/subscription_header_bedienlogik.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, werte, ohneTypen, type Knoten } from './svelteInstanzPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const BAUSTEIN = join(FRONTEND, 'src/lib/components/shared/subscription-header/SubscriptionHeader.svelte');

register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

type SaveField = (field: string, value: string, schliessen?: () => void) => Promise<void>;

async function baustein(saat: Knoten = {}): Promise<{ ast: Knoten; quelle: string; u: Knoten }> {
	const { ast, quelle, u } = await umgebungFuer(BAUSTEIN, {
		kind: 'trip',
		name: 'GR20 Nord',
		region: 'Korsika',
		profile: 'trekking',
		profileOptions: [{ value: 'trekking', label: 'Trekking' }],
		profileLabel: 'Trekking',
		regionMaxLength: 80,
		testidPrefix: 'trip',
		onSaveField: async () => {},
		...saat
	});
	for (const f of ['start', 'cancel', 'save']) {
		assert.equal(typeof u[f], 'function', `Messaufbau: \`${f}\` aus dem Baustein nicht herleitbar`);
	}
	for (const s of ['open', 'draft', 'saving', 'errors']) {
		assert.equal(typeof u[s], 'object', `Messaufbau: Zustand \`${s}\` nicht herleitbar`);
	}
	return { ast, quelle, u };
}

/** Erstes Element `tag` im Markup, dessen Attribut `merkmal` den Text `enthaelt` trägt. */
function element(ast: Knoten, quelle: string, tag: string, merkmal: string, enthaelt: string): Knoten {
	let treffer: Knoten | null = null;
	function lauf(n: unknown): void {
		if (treffer || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'RegularElement' && k.name === tag) {
			const a = (k.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === merkmal);
			if (a && quelle.slice(a.start, a.end).includes(enthaelt)) {
				treffer = k;
				return;
			}
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	}
	lauf(ast.fragment);
	assert.ok(treffer, `Messaufbau: <${tag} ${merkmal}~"${enthaelt}"> nicht im Markup`);
	return treffer!;
}

/** Wert eines Attributs, wie Svelte ihn setzen würde: Ausdruck ausgewertet, Text wörtlich. */
function attributWert(el: Knoten, quelle: string, name: string, u: Knoten): unknown {
	const a = (el.attributes as Knoten[]).find((x) => x.type === 'Attribute' && x.name === name);
	if (!a) return undefined;
	const v = a.value;
	if (v === true) return true;
	if (v?.type === 'ExpressionTag') return werte(ohneTypen(quelle, v.expression), u);
	if (Array.isArray(v) && v.length === 1 && v[0].type === 'ExpressionTag') {
		return werte(ohneTypen(quelle, v[0].expression), u);
	}
	return (v as Knoten[]).map((t) => t.data ?? '').join('');
}

describe('#2284 S1 F004 — maxlength der Region-Eingabe kommt aus regionMaxLength', () => {
	for (const n of [80, 60]) {
		test(`regionMaxLength=${n} ⇒ maxlength ${n}`, async () => {
			const { ast, quelle, u } = await baustein({ regionMaxLength: n });
			const eingabe = element(ast, quelle, 'input', 'aria-label', 'Region bearbeiten');
			assert.equal(Number(attributWert(eingabe, quelle, 'maxlength', u)), n);
		});
	}
});

describe('#2284 S1 F003 — Profil-Kacheln während des Speicherns gesperrt', () => {
	test('saving.profile ⇒ Kachel disabled; danach wieder frei', async () => {
		const { ast, quelle, u } = await baustein();
		const kachel = element(ast, quelle, 'button', 'data-testid', 'profil-option-');
		u.opt = { value: 'trekking', label: 'Trekking' };
		u.saving.profile = true;
		assert.equal(attributWert(kachel, quelle, 'disabled', u), true, 'Kachel muss während des Speicherns gesperrt sein');
		u.saving.profile = false;
		assert.equal(attributWert(kachel, quelle, 'disabled', u), false);
	});

	test('save("profile") setzt saving.profile, solange der Aufruf läuft', async () => {
		let freigeben: () => void = () => {};
		let waehrend: boolean | undefined;
		const { u } = await baustein({
			onSaveField: (() =>
				new Promise<void>((r) => {
					waehrend = undefined;
					freigeben = r;
				})) as SaveField
		});
		const laeuft = (u.save as SaveField)('profile', 'skitour');
		waehrend = u.saving.profile;
		freigeben();
		await laeuft;
		assert.equal(waehrend, true, 'während onSaveField läuft, muss saving.profile true sein');
		assert.equal(u.saving.profile, false, 'nach Abschluss wieder frei');
	});
});

describe('#2284 S1 F002 — Fehlermeldung: Text aus error, sonst Fallback', () => {
	test('Fehler MIT error ⇒ dieser Text', async () => {
		const { u } = await baustein({
			onSaveField: (async () => {
				throw { error: 'Serverfehler', status: 500 };
			}) as SaveField
		});
		await (u.save as SaveField)('profile', 'skitour');
		assert.equal(u.errors.profile, 'Serverfehler');
	});

	test('Fehler OHNE error (z. B. 500 mit leerem Rumpf) ⇒ „Speichern fehlgeschlagen"', async () => {
		const { u } = await baustein({
			onSaveField: (async () => {
				throw { status: 500 };
			}) as SaveField
		});
		u.start('name');
		u.draft.name = 'Neu';
		await (u.save as SaveField)('name', u.draft.name);
		assert.equal(u.errors.name, 'Speichern fehlgeschlagen');
		assert.equal(u.open.name, true, 'bei Fehler bleibt das Feld offen');
		assert.equal(u.draft.name, 'Neu', 'eingetippter Wert bleibt erhalten');
	});
});

describe('#2284 S1 F003/F005 — Öffnen belegt vor, Abbrechen verwirft Fehler', () => {
	test('Stift öffnen ⇒ Entwurf trägt den aktuellen Namen bzw. die Region', async () => {
		const { u } = await baustein();
		u.start('name');
		u.start('region');
		assert.equal(u.draft.name, 'GR20 Nord');
		assert.equal(u.draft.region, 'Korsika');
		assert.equal(u.open.name, true);
		assert.equal(u.open.region, true);
	});

	test('Fehler → Abbrechen ⇒ Feld zu, Fehler weg; erneut öffnen ⇒ kein Fehler', async () => {
		const { u } = await baustein({
			onSaveField: (async () => {
				throw { error: 'Serverfehler' };
			}) as SaveField
		});
		u.start('region');
		u.draft.region = 'Wallis';
		await (u.save as SaveField)('region', u.draft.region);
		assert.equal(u.errors.region, 'Serverfehler', 'Messaufbau: Fehler muss zuerst stehen');
		u.cancel('region');
		assert.equal(u.open.region, false);
		assert.equal(u.errors.region, null, 'Abbrechen muss den Fehler verwerfen');
		u.start('region');
		assert.equal(u.errors.region, null);
		assert.equal(u.draft.region, 'Korsika', 'erneutes Öffnen verwirft die alte Eingabe');
	});
});

describe('#2284 S1 / #1433 — drei Ausgänge des Speicherns: übernommen, Konflikt, Fehler', () => {
	for (const feld of ['name', 'region'] as const) {
		test(`${feld}: Seite ruft schliessen ⇒ Feld zu, kein Fehler`, async () => {
			const { u } = await baustein({
				onSaveField: (async (_f: string, _v: string, schliessen?: () => void) => {
					schliessen?.();
				}) as SaveField
			});
			u.start(feld);
			await (u.save as SaveField)(feld, 'Neu');
			assert.equal(u.open[feld], false, 'übernommen ⇒ Feld schließt');
			assert.equal(u.errors[feld], null);
			assert.equal(u.saving[feld], false);
		});

		test(`${feld}: Konflikt (erfüllt OHNE schliessen) ⇒ Feld bleibt offen, keine Meldung; späteres schliessen() ⇒ zu`, async () => {
			let spaeter: () => void = () => {};
			const { u } = await baustein({
				onSaveField: (async (_f: string, _v: string, schliessen?: () => void) => {
					if (schliessen) spaeter = schliessen;
				}) as SaveField
			});
			u.start(feld);
			u.draft[feld] = 'Meine Eingabe';
			await (u.save as SaveField)(feld, u.draft[feld]);
			assert.equal(u.open[feld], true, 'Konflikt ⇒ das Eingabefeld darf NICHT schließen (Eingabe ginge verloren)');
			assert.equal(u.draft[feld], 'Meine Eingabe');
			assert.equal(u.errors[feld], null, 'Konflikt ⇒ keine eigene Meldung, „Nochmal speichern" zeigt');
			assert.equal(u.saving[feld], false, 'Konflikt ⇒ Speichern-Knopf wieder frei');
			spaeter();
			assert.equal(u.open[feld], false, '„Nochmal speichern" erfolgreich ⇒ Feld schließt jetzt');
		});
	}

	test('Fehler ⇒ Feld offen, Meldung am Feld, Speichern wieder frei', async () => {
		const { u } = await baustein({
			onSaveField: (async () => {
				throw { error: 'Kaputt' };
			}) as SaveField
		});
		u.start('name');
		await (u.save as SaveField)('name', 'X');
		assert.equal(u.open.name, true);
		assert.equal(u.errors.name, 'Kaputt');
		assert.equal(u.saving.name, false);
	});
});
