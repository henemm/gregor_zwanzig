// TDD RED — Issue #3399 Scheibe S2 (AC-5): „Vergleich als Kopie" übernimmt die Vorlage der Quelle
// aus der Server-Auflösung (POST /api/ampel/aufloesung → resolve_entwurf), nicht aus der
// Frontend-Rangfolge `vorlageIdFuer`.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (S2, AC-5)
//
// Kein Mock-Theater: Referenz und Client sind das ECHTE Python `resolve_entwurf`
// (`aufloesungPost`/`aufgeloestVon` aus wetterTabDaten.ts, Subprozess). Der Fehlerfall nutzt
// einen Client, der wie ein ausgefallener Server wirft bzw. eine unbrauchbare Antwort liefert.
//
// Warum heute rot: `vorlageIdDerQuelle` fehlt, und `feldsatzAusVorlage` ignoriert eine
// übergebene Vorlagen-ID (rechnet sie selbst über die Rangfolge).
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/kopie_vorlage_aufloesung_3399.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset, Location } from '../../../types.ts';
import * as modul from '../compareNewVorlage.ts';
import { aufgeloestVon, aufloesungPost } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

type Feldsatz = Record<string, unknown>;
type Client = { post<T>(pfad: string, rumpf: unknown): Promise<T> };

function vorlageIdDerQuelle(client: Client, preset: ComparePreset): Promise<string | null> {
	const fn = (modul as Record<string, unknown>).vorlageIdDerQuelle;
	if (typeof fn !== 'function') {
		throw new Error('VERTRAG FEHLT (#3399 S2): compareNewVorlage.ts exportiert kein `vorlageIdDerQuelle(client, preset)`');
	}
	return (fn as (c: Client, p: ComparePreset) => Promise<string | null>)(client, preset);
}

const feldsatz = (p: ComparePreset, id: string | null): Feldsatz =>
	(modul.feldsatzAusVorlage as unknown as (p: ComparePreset, l: Location[], id: string | null) => Feldsatz)(p, ORTE, id);

const ORTE = ['loc-a', 'loc-b'].map((id) => ({ id, name: id }) as unknown as Location);

function quelle(over: Record<string, unknown> = {}): ComparePreset {
	return {
		id: 'cmp-quelle',
		name: 'Skitouren Tirol',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wintersport',
		empfaenger: [],
		display_config: { region: 'Tirol' },
		...over
	} as unknown as ComparePreset;
}

const pythonClient = (): Client & { aufrufe: number } => {
	const post = aufloesungPost();
	const c = {
		aufrufe: 0,
		async post<T>(pfad: string, rumpf: unknown): Promise<T> {
			c.aufrufe++;
			return post<T>(pfad, rumpf);
		}
	};
	return c;
};

describe('AC-5: vorlageIdDerQuelle — Vorlage der Quelle vom Server', () => {
	const faelle: Array<[string, ComparePreset]> = [
		['nur profil wintersport', quelle()],
		['ampel.template wassersport schlägt profil', quelle({ profil: 'wandern', display_config: { region: 'Tirol', ampel: { template: 'wassersport' } } })],
		['preset_name gesetzt, kein ampel.template', quelle({ profil: 'wandern', display_config: { region: 'Tirol', preset_name: 'wintersport' } })],
		['unbekannte Vorlage der Quelle', quelle({ profil: 'wandern', display_config: { region: 'Tirol', ampel: { template: 'gibt-es-nicht' } } })]
	];
	for (const [name, q] of faelle) {
		test(`${name}: Ergebnis gleich echtem resolve_entwurf, ein Aufruf`, async () => {
			const c = pythonClient();
			const id = await vorlageIdDerQuelle(c, q);
			assert.equal(id, aufgeloestVon(q as never).vorlage_id, 'Vorlage weicht vom Server ab');
			assert.equal(c.aufrufe, 1, 'genau ein Auflösungsaufruf erwartet');
		});
	}

	test('Server fällt aus (Client wirft) ⇒ null, wirft nie', async () => {
		const id = await vorlageIdDerQuelle({ post: async () => { throw new Error('502 Bad Gateway'); } }, quelle());
		assert.equal(id, null);
	});

	test('unbrauchbare Antwort ⇒ null, kein geratener Wert', async () => {
		const id = await vorlageIdDerQuelle({ post: async <T>() => ({ ergebnisse: [] }) as T }, quelle());
		assert.equal(id, null);
	});
});

describe('AC-5: feldsatzAusVorlage übernimmt die übergebene Vorlagen-ID', () => {
	test('ID vom Server gewinnt gegen die Rangfolge der Quelle (profil wintersport, ID wassersport)', () => {
		assert.equal(feldsatz(quelle(), 'wassersport').vorlageId, 'wassersport');
	});

	test('ID null ⇒ kein vorlageId im Feldsatz (Anlege-Voreinstellung greift), übrige Felder übernommen', () => {
		const f = feldsatz(quelle(), null);
		assert.equal('vorlageId' in f && f.vorlageId !== undefined, false, `geratene Vorlage: ${JSON.stringify(f.vorlageId)}`);
		assert.deepEqual(f.pickedIds, ['loc-a', 'loc-b'], 'Orte der Quelle fehlen');
		assert.equal(f.region, 'Tirol', 'Region der Quelle fehlt');
		assert.match(String(f.name), /Skitouren Tirol/, 'Name der Quelle fehlt');
	});
});
