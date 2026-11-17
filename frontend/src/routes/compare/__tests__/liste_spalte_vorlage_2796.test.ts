// TDD RED — Issue #2796 S4a (ADR-0108 P3, Spec §4): die Orte-Liste (Desktop-Tabelle) zeigt die
// aufgelöste Vorlage statt des Profils — Spaltenkopf „Vorlage"/„Template", Zelle = Vorlagenname
// in der Sprache des Nutzers (wie die Listenkarte SubscriptionCard).
// Spec: docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md (AC-7)
//
// Ausgewertet werden die ECHTEN Spaltendefinitionen (`compareColumns`) des Instanz-Skripts
// von routes/compare/+page.svelte (svelteInstanzPruefstand.ts) — kein Mock, kein Datei-Grep.
//
//   cd frontend && npm test -- src/routes/compare/__tests__/liste_spalte_vorlage_2796.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { umgebungFuer, type Knoten } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { locale, trFor } from '../../../lib/i18n/index.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../..');
const SEITE = join(FRONTEND, 'src/routes/compare/+page.svelte');
const basis = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);

afterEach(() => locale.set('de'));

type Spalte = { key: string; header: string; render: (row: unknown) => unknown };

async function spalten(): Promise<Spalte[]> {
	const { u } = await umgebungFuer(SEITE, {}, { jsAlsTs: true });
	const s = u.compareColumns as Spalte[] | undefined;
	assert.ok(Array.isArray(s), 'Messaufbau: compareColumns aus +page.svelte nicht herleitbar');
	return s;
}

const ZEILE = (profil: string | undefined, vorlage: string | undefined): Knoten => ({
	id: 'cp-2796', name: 'Tirol', location_ids: ['a', 'b'], schedule: 'daily',
	...(profil ? { profil } : {}), display_config: vorlage ? { ampel: { template: vorlage } } : {}
});

describe('#2796 AC-7: Orte-Liste — Spalte Vorlage statt Profil', () => {
	for (const lang of ['de', 'en'] as const) {
		test(`${lang}: Kopf „${trFor(lang, 'listen.spalte.vorlage' as never)}", Zelle = aufgelöste Vorlage`, async () => {
			locale.set(lang);
			const alle = await spalten();
			const s = alle.find((x) => x.key === 'vorlage');
			assert.ok(s, `keine Spalte „vorlage": ${alle.map((x) => x.key).join(', ')}`);
			assert.equal(alle.filter((x) => x.key === 'profil').length, 0, 'Spalte „profil" steht noch');
			assert.equal(s.header, lang === 'de' ? 'Vorlage' : 'Template');
			assert.equal(s.render(ZEILE('wandern', 'wintersport')), lang === 'de' ? 'Wintersport' : 'Winter sports');
			assert.equal(s.render(ZEILE('summer_trekking', undefined)), lang === 'de' ? 'Alpen-Trekking' : 'Alpine trekking');
			assert.equal(s.render(ZEILE(undefined, undefined)), lang === 'de' ? 'Allgemein' : 'General');
		});
	}
});
