// TDD RED — Issue #2796 S4a (ADR-0108 P3): Übersicht und Listenkarte nennen die Vorlage.
// Spec: docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md (AC-7)
//
// Karte „Wetter" der Hub-Übersicht (Orts-Vergleich) und Listenkarte (`SubscriptionCard`)
// zeigen den Namen der AUFGELÖSTEN Vorlage (ampel.template → profil → „allgemein") in der
// Sprache des Nutzers, nicht mehr den Profilnamen — mit und ohne geladene Vorlagenliste.
// Echte Module bzw. echte Komponente (svelte/server), kein Mock.
//
//   cd frontend && npm test -- src/lib/components/shared/hub-uebersicht/__tests__/vorlage_statt_profil_2796.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { live } from '../../wetter-tab/__tests__/wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const LIB = join(FRONTEND, 'src', 'lib');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const lade = async (p: string): Promise<Json> => import(pathToFileURL(p).href);
const { render } = await import('svelte/server');
const { locale } = await lade(join(LIB, 'i18n', 'index.ts'));
const am = await lade(join(LIB, 'components', 'shared', 'wetter-tab', 'ampelModell.ts'));
const VORLAGEN = am.vorlagenAusTemplates(live().templates);

afterEach(() => locale.set('de'));

function preset(profil: string | undefined, vorlage: string | undefined): Json {
	return {
		id: 'cp-2796', name: 'Tirol', location_ids: ['a', 'b', 'c'], schedule: 'daily',
		...(profil ? { profil } : {}),
		display_config: vorlage ? { ampel: { template: vorlage } } : {}
	};
}

const FAELLE: Array<[string, Json, string, string]> = [
	['Vorlage weicht vom Profil ab', preset('wandern', 'wintersport'), 'Wintersport', 'Winter sports'],
	['nur Profil summer_trekking', preset('summer_trekking', undefined), 'Alpen-Trekking', 'Alpine trekking'],
	['weder Profil noch Vorlage', preset(undefined, undefined), 'Allgemein', 'General']
];

async function wetterTitel(p: Json, vorlagen: Json): Promise<string> {
	const m = await lade(join(HIER, '..', 'hubUebersichtModell.ts'));
	return m.deriveVergleichKennzahlen(p, 'active', null, [], vorlagen).wertebereicheKarte.titel;
}

describe('#2796 AC-7: Karte „Wetter" = Name der aufgelösten Vorlage', () => {
	for (const [name, p, de, en] of FAELLE) {
		for (const [stand, vorlagen] of [['Vorlagen geladen', VORLAGEN], ['Vorlagen nicht geladen', null]] as const) {
			test(`${name} (${stand}): DE „${de}", EN „${en}"`, async () => {
				locale.set('de');
				assert.equal(await wetterTitel(p, vorlagen), de);
				locale.set('en');
				assert.equal(await wetterTitel(p, vorlagen), en);
			});
		}
	}
});

const Card = (await lade(join(LIB, 'components', 'organisms', 'SubscriptionCard.svelte'))).default;
describe('#2796 AC-7: Listenkarte „{n} Orte · {Vorlagenname}"', () => {
	const meta = (p: Json) => render(Card, { props: { kind: 'vergleich', sub: p, dense: true } }).body
		.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]+>/g, '\n').split('\n').map((z: string) => z.trim())
		.find((z: string) => /\b(Orte|locations)\b/.test(z));
	for (const [name, p, de, en] of FAELLE) {
		test(`${name}: DE „3 Orte · ${de}", EN „3 locations · ${en}"`, async () => {
			locale.set('de');
			assert.equal(meta(p), `3 Orte · ${de}`);
			locale.set('en');
			assert.equal(meta(p), `3 locations · ${en}`);
		});
	}
});

// Adversary F4: `aboVorlagenName` mit und ohne geladene Vorlagenliste. `/api/templates` liefert nur
// Systemvorlagen (Python `get_templates` über AMPEL_TEMPLATES), das Abo speichert nur deren IDs —
// die Liste ist für den NAMEN daher wirkungsgleich mit der eingebauten Systemmenge. Gewacht wird,
// dass beide Wege für jede Systemvorlage denselben Namen liefern und eine unbekannte ID wie die
// Mail (`_bekannte_vorlage`) auf „Allgemein" fällt — nie die rohe ID, nie ein Katalogschlüssel.
describe('#2796 F4: Vorlagenname mit/ohne Vorlagenliste, unbekannte ID wie die Mail', async () => {
	const { aboVorlagenName } = await lade(join(LIB, 'components', 'shared', 'wetter-tab', 'vorlageName.ts'));
	test('jede Systemvorlage: mit Liste == ohne Liste, in DE und EN', () => {
		const ids = Object.keys(VORLAGEN);
		assert.ok(ids.length >= 7, `Messaufbau: Systemvorlagen ${ids.join(', ')}`);
		for (const lang of ['de', 'en'] as const) {
			for (const id of ids) {
				const p = preset('wandern', id);
				assert.equal(aboVorlagenName(lang, p, VORLAGEN), aboVorlagenName(lang, p, null), `${lang}/${id}`);
				assert.notEqual(aboVorlagenName(lang, p, VORLAGEN), id, `${lang}/${id}: rohe ID statt Katalogname`);
			}
		}
	});
	test('unbekannte Vorlagen-ID ⇒ „Allgemein"/„General" (wie die Mail), mit und ohne Liste', () => {
		for (const v of [VORLAGEN, null]) {
			assert.equal(aboVorlagenName('de', preset('wandern', 'eigene-xyz'), v), 'Allgemein');
			assert.equal(aboVorlagenName('en', preset('wandern', 'eigene-xyz'), v), 'General');
		}
	});
});
