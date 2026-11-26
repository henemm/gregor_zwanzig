// #3399 S1 Fix-Loop 1 (Adversary F001, AC-1): Verdrahtung des Alarme-Reiters
// „Abo -> vorlagenIdLader -> Vorlagen-ID" im ECHTEN Laufzeitverhalten.
// Spec: docs/specs/modules/rework_3399_vorlage_aufloesung.md (AC-1, S1).
//
// Pruefling: shared/alarme-tab/aboVorlageId.svelte.ts — AlarmeTab liest daraus `aboVorlage.id`.
// Testart wie versand-tab/__tests__/naechstes_briefing_lader_laufzeit.test.ts: das Runen-Modul wird
// fuer die Svelte-CLIENT-Laufzeit uebersetzt (clientRunenHook.mjs) und unter `effect_root` + `flush`
// ausgefuehrt (echte Effekte, echte Abhaengigkeits-Verfolgung). Server: echtes `resolve_entwurf`
// per Subprozess (wetterTabDaten.ts); der Client kann nur verzoegern oder scheitern.
// Jeder Test nutzt eigene Eintraege (eindeutiger preset_name), weil der Lader-Cache modulweit ist.
//
//   cd frontend && npm test -- src/lib/components/shared/alarme-tab/__tests__/abo_vorlage_id_laufzeit_3399.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { aufgeloestVon, aufloesungPost } from '../../wetter-tab/__tests__/wetterTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VERSAND_TESTS = path.join(HERE, '..', '..', 'versand-tab', '__tests__');
register(pathToFileURL(path.join(VERSAND_TESTS, 'clientRunenHook.mjs')).href, pathToFileURL(VERSAND_TESTS + '/').href);

const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $ = (await import(CLIENT_LAUFZEIT)) as Record<string, any>;
const { erstelleAboVorlageId } = await import(pathToFileURL(path.join(HERE, '..', 'aboVorlageId.svelte.ts')).href);

type Json = any;
const echt = aufloesungPost();

async function setzen() {
	$.flush();
	for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
	$.flush();
}

/** Client um das echte Python; `halte()` haelt den naechsten Aufruf an, bis `oeffne()` kommt. */
function server(opts: { fehler?: boolean } = {}) {
	const aufrufe: number[] = [];
	let tor: Promise<void> | null = null;
	let oeffne = () => {};
	return {
		aufrufe,
		halte() {
			tor = new Promise<void>((r) => (oeffne = r));
		},
		oeffne: () => oeffne(),
		client: {
			async post<T>(pfad: string, rumpf: unknown): Promise<T> {
				aufrufe.push(((rumpf as Json)?.eintraege ?? []).length);
				const warte = tor;
				tor = null;
				if (warte) await warte;
				if (opts.fehler) throw new Error('503 Service Unavailable');
				return echt<T>(pfad, rumpf);
			}
		}
	};
}

function starte(abo: Json, client: unknown, extern?: string | null) {
	const signale = { abo: $.state(abo), extern: $.state(extern) };
	let ergebnis: any;
	const stopp = $.effect_root(() => {
		ergebnis = erstelleAboVorlageId(() => ({ abo: $.get(signale.abo), extern: $.get(signale.extern) }), client);
	});
	return { signale, get id() { return ergebnis.id; }, stopp };
}

const trip = (marke: string, dc: Json = {}): Json => ({ id: `t-${marke}`, name: 'T', stages: [], display_config: { preset_name: `x3399l-${marke}`, ...dc } });

describe('#3399 S1 AC-1: der Reiter uebernimmt die Vorlagen-ID des Servers', () => {
	test('„—" (null) waehrend des Ladens, danach die Server-Vorlage', async () => {
		const s = server();
		s.halte();
		const abo = trip('laden', { ampel: { template: 'skitouren' } });
		const l = starte(abo, s.client);
		await setzen();
		assert.deepEqual(s.aufrufe, [1], 'der Reiter fragt die Aufloesung fuer sein Abo an');
		assert.equal(l.id, null, 'solange die Antwort aussteht: keine ID (Anzeige „—")');
		s.oeffne();
		await setzen();
		assert.equal(l.id, aufgeloestVon(abo).vorlage_id);
		assert.equal(l.id, 'skitouren');
		l.stopp();
	});

	test('Vergleich mit Profil: ID aus resolve_entwurf (summer_trekking -> alpen-trekking)', async () => {
		const s = server();
		const preset = { id: 'v-p', name: 'V', location_ids: ['l1'], profil: 'summer_trekking', display_config: { preset_name: null } };
		const l = starte(preset, s.client);
		await setzen();
		assert.equal(l.id, aufgeloestVon(preset).vorlage_id);
		assert.equal(l.id, 'alpen-trekking');
		l.stopp();
	});

	test('Fehler der Aufloesung: null („—"), kein geratenes „allgemein"', async () => {
		const s = server({ fehler: true });
		const l = starte(trip('fehler'), s.client);
		await setzen();
		assert.equal(s.aufrufe.length, 1);
		assert.equal(l.id, null);
		l.stopp();
	});

	test('Abo-Wechsel: sofort null statt der alten ID, danach die neue Server-ID', async () => {
		const s = server();
		const l = starte(trip('wechsel-a', { ampel: { template: 'skitouren' } }), s.client);
		await setzen();
		assert.equal(l.id, 'skitouren', 'Messaufbau: erste ID geladen');
		s.halte();
		const neu = trip('wechsel-b', { ampel: { template: 'wandern' } });
		$.set(l.signale.abo, neu);
		await setzen();
		assert.equal(s.aufrufe.length, 2, 'der Abo-Wechsel loest eine neue Aufloesung aus');
		assert.equal(l.id, null, 'waehrend die neue Antwort aussteht, steht nie die alte ID');
		s.oeffne();
		await setzen();
		assert.equal(l.id, aufgeloestVon(neu).vorlage_id);
		assert.equal(l.id, 'wandern');
		l.stopp();
	});

	test('Wert von aussen (Testhaken): kein Abruf, Text und null werden durchgereicht', async () => {
		const s = server();
		const l = starte(trip('extern'), s.client, 'skitouren');
		await setzen();
		assert.equal(l.id, 'skitouren');
		$.set(l.signale.extern, null);
		await setzen();
		assert.equal(l.id, null);
		assert.equal(s.aufrufe.length, 0, 'mit gesetztem Haken laedt der Reiter nicht');
		l.stopp();
	});
});
