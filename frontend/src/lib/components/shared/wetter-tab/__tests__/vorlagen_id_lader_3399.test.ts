// #3399 S1 (AC-6, AC-4-Grundlage): gebuendelter, gecachter Lader „Abo -> vorlage_id".
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md („Implementation Details", S1).
//
// Vertrag (im RED-Schritt festgelegt, Vorbild hub-uebersicht/tripAufloesung.ts):
//   wetter-tab/vorlagenIdLader.ts (neu, ohne Svelte-/Browser-Import)
//     type VorlageIdZustand = { zustand: 'laedt' | 'geladen' | 'fehler'; vorlageId: string | null }
//     erstelleVorlagenIdLader(client: AufloesungClient, melde: (zustaende: VorlageIdZustand[]) => void)
//       : { laden(abos: Abo[]): Promise<void> }
//     laden: Schluessel je Abo = JSON.stringify(eintragAusAbo(abo)). Ist alles im (modulweiten) Cache,
//       meldet laden sofort 'geladen' und sendet nichts. Sonst sofort (synchron) melde mit 'laedt' fuer die
//       ungecachten und 'geladen' fuer die gecachten Abos (Reihenfolge = abos); ALLE ungecachten Eintraege
//       gehen gebuendelt durch loeseAmpelnAuf (Pakete a 32); danach melde mit dem Endstand bzw. bei jedem
//       Fehler 'fehler' (vorlageId null) fuer die ungecachten. Gescheiterte Eintraege werden nicht
//       gecacht. Ein Ticket verwirft Antworten, wenn seither ein neueres laden begann. Das Promise
//       scheitert nie. Verwendet wird nur `vorlage_id`.
//
// Server: echtes `resolve_entwurf` per Subprozess (wetterTabDaten.ts), der Client zaehlt nur und kann
// verzoegern/scheitern (Transport um den echten Aufloeser, kein Mock des Prueflings).
// Jeder Test nutzt eigene Abos (eindeutiger preset_name), weil der Cache modulweit ist.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/vorlagen_id_lader_3399.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { aufgeloestVon, aufloesungPost } from './wetterTabDaten.ts';
import { erstelleVorlagenIdLader } from '../vorlagenIdLader.ts';

type Json = any;
type Zustand = { zustand: 'laedt' | 'geladen' | 'fehler'; vorlageId: string | null };

const echt = aufloesungPost();

/** Client um das echte Python: zaehlt Aufrufe und Eintraege je Aufruf; optional Tor/Fehler. */
function zaehlClient(opts: { tor?: () => Promise<void>; fehler?: 'wirft' | 'unbrauchbar' } = {}) {
	const aufrufe: number[] = [];
	return {
		aufrufe,
		client: {
			async post<T>(pfad: string, rumpf: unknown): Promise<T> {
				aufrufe.push(((rumpf as Json)?.eintraege ?? []).length);
				if (opts.tor) await opts.tor();
				if (opts.fehler === 'wirft') throw new Error('503 Service Unavailable');
				if (opts.fehler === 'unbrauchbar') return { ergebnisse: [] } as T;
				return echt<T>(pfad, rumpf);
			}
		}
	};
}

function sammler() {
	const meldungen: Zustand[][] = [];
	return { meldungen, melde: (z: Zustand[]) => meldungen.push(z.map((x) => ({ ...x }))), letzte: () => meldungen[meldungen.length - 1] };
}

/** Abo mit eindeutiger (unbekannter) Vorlage: der Server loest auf „allgemein" auf. */
const abo = (marke: string, extra: Json = {}): Json => ({ id: `id-${marke}`, name: `Name ${marke}`, display_config: { preset_name: `x3399-${marke}` }, ...extra });
const vid = (a: Json) => aufgeloestVon(a).vorlage_id;

describe('#3399 S1: Lader liefert die Vorlagen-ID des Servers', () => {
	test('Ampel-Vorlage, Vorlagenname, Profil und Standard: je Abo die ID aus resolve_entwurf', async () => {
		const abos = [
			{ id: 'a', display_config: { ampel: { template: 'skitouren' } } },
			{ id: 'b', display_config: { preset_name: 'wandern' } },
			{ id: 'c', display_config: {}, profil: 'summer_trekking' },
			abo('standard-1')
		];
		const { client } = zaehlClient();
		const s = sammler();
		await erstelleVorlagenIdLader(client, s.melde).laden(abos);
		const ids = s.letzte().map((z) => z.vorlageId);
		assert.deepEqual(ids, abos.map(vid), 'je Abo genau die ID, die der Server aufloest');
		assert.deepEqual(ids, ['skitouren', 'wandern', 'alpen-trekking', 'allgemein']);
		assert.ok(s.letzte().every((z) => z.zustand === 'geladen'));
	});

	test('Zustaende: zuerst „laedt" (synchron, vor der Antwort), dann „geladen"', async () => {
		const { client } = zaehlClient();
		const s = sammler();
		const p = erstelleVorlagenIdLader(client, s.melde).laden([abo('laedt-1')]);
		assert.deepEqual(s.meldungen[0], [{ zustand: 'laedt', vorlageId: null }], 'sofort „laedt", nie eine geratene ID');
		await p;
		assert.deepEqual(s.letzte(), [{ zustand: 'geladen', vorlageId: 'allgemein' }]);
	});
});

describe('#3399 S1 AC-6: Buendelung und Cache', () => {
	test('alle ungecachten Abos in EINEM Aufruf', async () => {
		const z = zaehlClient();
		await erstelleVorlagenIdLader(z.client, () => {}).laden([abo('b1'), abo('b2'), abo('b3')]);
		assert.deepEqual(z.aufrufe, [3], 'ein Aufruf mit drei Eintraegen, nicht drei Aufrufe');
	});

	test('mehr als 32 Eintraege: Pakete a 32 (zweiter Aufruf erst ab Eintrag 33)', async () => {
		const z = zaehlClient();
		const abos = Array.from({ length: 33 }, (_, i) => abo(`p33-${i}`));
		const s = sammler();
		await erstelleVorlagenIdLader(z.client, s.melde).laden(abos);
		assert.deepEqual(z.aufrufe, [32, 1]);
		assert.equal(s.letzte().length, 33);
		assert.ok(s.letzte().every((x) => x.zustand === 'geladen' && x.vorlageId === 'allgemein'));
	});

	test('dieselben Abos nochmal (auch ueber einen neuen Lader): kein weiterer Aufruf, sofort „geladen"', async () => {
		const z = zaehlClient();
		const abos = [abo('c1'), abo('c2', { display_config: { ampel: { template: 'radtour' } } })];
		await erstelleVorlagenIdLader(z.client, () => {}).laden(abos);
		assert.equal(z.aufrufe.length, 1);
		const s = sammler();
		const p = erstelleVorlagenIdLader(z.client, s.melde).laden(abos);
		assert.deepEqual(s.meldungen[0].map((x) => x.zustand), ['geladen', 'geladen'], 'aus dem Cache, ohne „laedt"-Aufblitzen');
		assert.deepEqual(s.meldungen[0].map((x) => x.vorlageId), abos.map(vid));
		await p;
		assert.equal(z.aufrufe.length, 1, 'Hub, Karte und Reiter fragen identische Eintraege nicht erneut');
	});

	test('Schluessel ist der Eintrag, nicht das Abo: andere ID/Name, gleicher Eintrag => aus dem Cache', async () => {
		const z = zaehlClient();
		await erstelleVorlagenIdLader(z.client, () => {}).laden([abo('k1')]);
		const anderes = { ...abo('k1'), id: 'ganz-andere-id', name: 'Anderer Name' };
		await erstelleVorlagenIdLader(z.client, () => {}).laden([anderes]);
		assert.equal(z.aufrufe.length, 1);
	});

	test('Mischung: nur die ungecachten Eintraege gehen raus', async () => {
		const z = zaehlClient();
		await erstelleVorlagenIdLader(z.client, () => {}).laden([abo('m1')]);
		const s = sammler();
		await erstelleVorlagenIdLader(z.client, s.melde).laden([abo('m1'), abo('m2'), abo('m3')]);
		assert.deepEqual(z.aufrufe, [1, 2], 'zweiter Aufruf nur mit m2 und m3');
		assert.ok(s.letzte().every((x) => x.zustand === 'geladen'));
	});
});

describe('#3399 S1 AC-6: Ticket gegen veraltete Antworten', () => {
	test('eine langsame, aelter angefragte Antwort ueberschreibt die neuere nicht', async () => {
		let oeffneAlt!: () => void;
		let aufruf = 0;
		const z = zaehlClient({
			tor: () => (++aufruf === 1 ? new Promise<void>((r) => (oeffneAlt = r)) : Promise.resolve())
		});
		const s = sammler();
		const lader = erstelleVorlagenIdLader(z.client, s.melde);
		const alt = lader.laden([abo('t-alt', { display_config: { ampel: { template: 'skitouren' } } })]);
		const neu = lader.laden([abo('t-neu', { display_config: { ampel: { template: 'wandern' } } })]);
		await neu;
		assert.deepEqual(s.letzte(), [{ zustand: 'geladen', vorlageId: 'wandern' }]);
		const vorher = s.meldungen.length;
		oeffneAlt();
		await alt;
		assert.equal(s.meldungen.length, vorher, 'die veraltete Antwort meldet nichts mehr');
		assert.deepEqual(s.letzte(), [{ zustand: 'geladen', vorlageId: 'wandern' }]);
	});

	test('ein veralteter Fehler ueberschreibt die neuere Antwort nicht', async () => {
		let scheitereAlt!: () => void;
		let aufruf = 0;
		const client = {
			async post<T>(pfad: string, rumpf: unknown): Promise<T> {
				if (++aufruf === 1) await new Promise<void>((_, rej) => (scheitereAlt = () => rej(new Error('503'))));
				return echt<T>(pfad, rumpf);
			}
		};
		const s = sammler();
		const lader = erstelleVorlagenIdLader(client, s.melde);
		const alt = lader.laden([abo('te-alt')]);
		await lader.laden([abo('te-neu')]);
		const vorher = s.meldungen.length;
		scheitereAlt();
		await alt;
		assert.equal(s.meldungen.length, vorher, 'auch der alte Fehler meldet nichts mehr');
		assert.equal(s.letzte()[0].zustand, 'geladen');
	});
});

describe('#3399 S1: Fehler', () => {
	test('Netzfehler: „fehler" ohne ID (kein geratenes „allgemein"), das Promise scheitert nie', async () => {
		const z = zaehlClient({ fehler: 'wirft' });
		const s = sammler();
		await assert.doesNotReject(erstelleVorlagenIdLader(z.client, s.melde).laden([abo('f1'), abo('f2')]));
		assert.deepEqual(s.letzte(), [
			{ zustand: 'fehler', vorlageId: null },
			{ zustand: 'fehler', vorlageId: null }
		]);
	});

	test('unbrauchbare Antwort (zu wenige Ergebnisse) ist ebenfalls „fehler"', async () => {
		const z = zaehlClient({ fehler: 'unbrauchbar' });
		const s = sammler();
		await assert.doesNotReject(erstelleVorlagenIdLader(z.client, s.melde).laden([abo('u1')]));
		assert.deepEqual(s.letzte(), [{ zustand: 'fehler', vorlageId: null }]);
	});

	test('Fehler wird nicht gecacht: der naechste Versuch fragt erneut und gelingt', async () => {
		const kaputt = zaehlClient({ fehler: 'wirft' });
		const gut = zaehlClient();
		const abos = [abo('r1')];
		await erstelleVorlagenIdLader(kaputt.client, () => {}).laden(abos);
		const s = sammler();
		await erstelleVorlagenIdLader(gut.client, s.melde).laden(abos);
		assert.equal(gut.aufrufe.length, 1, 'gescheiterte Eintraege werden neu angefragt');
		assert.deepEqual(s.letzte(), [{ zustand: 'geladen', vorlageId: 'allgemein' }]);
	});

	test('leere Abo-Liste: kein Aufruf, kein Fehler', async () => {
		const z = zaehlClient();
		const s = sammler();
		await assert.doesNotReject(erstelleVorlagenIdLader(z.client, s.melde).laden([]));
		assert.equal(z.aufrufe.length, 0);
	});
});
