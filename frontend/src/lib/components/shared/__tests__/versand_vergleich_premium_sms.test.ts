// TDD RED — Issue #2293 Scheibe S2 (AC-8, AC-14 Persistenz-Teil), Epic
// #1374/#2345 — löst #2448 mit auf (eigener Premium-SMS-Schalter im
// Versand-Reiter des Ortsvergleichs).
//
// Spec: docs/specs/modules/feat_2293_s2_compare_alarm_kanaele.md
//   Implementation Details Abschnitt 5, AC-8, AC-14 (Persistenz-Teil).
//
// Vor dieser Scheibe hatte der Versand-Reiter im Vergleichs-Zweig KEINEN
// Premium-SMS-Schalter — `VTBriefingChannels` bekam `onPremiumSmsChange` nur
// vom route-Zweig (VersandTab.svelte:373), im vergleich-Zweig
// (VersandTab.svelte:394-409) blieb die Prop weg und der feste
// "bald verfügbar"-Platzhalter stand. `versandPropsAus`/`VersandSnapshot`
// kannten `sendPremiumSms` gar nicht (Klasse-A-Feld fehlte).
//
// RED-Grund heute (gemessen): `versandPropsAus(wiz).sendPremiumSms` und
// `.onSendPremiumSmsChange` existieren nicht (undefined statt Wert/Funktion);
// `baueVersandNutzlast` sendet kein `send_premium_sms`; `VersandTab.svelte`
// bindet `sendPremiumSms`/`onSendPremiumSmsChange` nicht als Props und reicht
// im vergleich-Zweig kein `onPremiumSmsChange` an `VTBriefingChannels` durch.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei aufgelöst.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/versand_vergleich_premium_sms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { versandPropsAus } from '../../compare/versandPropsAus.ts';
import {
	baueVersandNutzlast,
	hydrateVersandFieldsFromPreset,
	versandSnapshotAus,
	rollbackVersandSnapshot,
	type VersandSnapshot
} from '../versandVergleichSpeicherung.ts';
import { findeKomponenten, attributAusdruck, type Knoten } from './svelteInstanzPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SHARED = join(HIER, '..');
const VERSAND_TAB = join(SHARED, 'VersandTab.svelte');

function _preset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cp-2293-ac8',
		name: 'AC8-Test',
		location_ids: ['loc-a'],
		schedule: 'manual',
		profil: 'ALLGEMEIN',
		hour_from: 8,
		hour_to: 17,
		empfaenger: ['a@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		corridors: [],
		...overrides
	} as ComparePreset;
}

// ─── versandPropsAus: sendPremiumSms als Klasse-A-Feld ─────────────────────

describe('AC-8: versandPropsAus fuehrt sendPremiumSms + onSendPremiumSmsChange', () => {
	test('das Buendel traegt sendPremiumSms als Wert (Default false ohne Bestand)', () => {
		const wiz: Record<string, unknown> = {};
		const props = versandPropsAus(wiz as never) as Record<string, unknown>;
		assert.strictEqual(
			props.sendPremiumSms,
			false,
			'AC-8: versandPropsAus muss sendPremiumSms fuehren (Default false ohne wiz.sendPremiumSms), ' +
				`erhalten: ${JSON.stringify(props.sendPremiumSms)}`
		);
	});

	test('das Buendel traegt sendPremiumSms unveraendert aus dem Wizard-Zustand', () => {
		const wiz: Record<string, unknown> = { sendPremiumSms: true };
		const props = versandPropsAus(wiz as never) as Record<string, unknown>;
		assert.strictEqual(props.sendPremiumSms, true);
	});

	test('onSendPremiumSmsChange schreibt auf wiz.sendPremiumSms zurueck', () => {
		const wiz: Record<string, unknown> = { sendPremiumSms: false };
		const props = versandPropsAus(wiz as never) as Record<string, unknown>;
		const onChange = props.onSendPremiumSmsChange as ((an: boolean) => void) | undefined;
		assert.strictEqual(
			typeof onChange,
			'function',
			`AC-8: versandPropsAus muss einen Rueckruf onSendPremiumSmsChange liefern, erhalten: ${typeof onChange}`
		);
		onChange!(true);
		assert.strictEqual(wiz.sendPremiumSms, true, 'onSendPremiumSmsChange(true) muss wiz.sendPremiumSms setzen.');
	});
});

// ─── Persistenzweg: VersandSnapshot/Hydration/Nutzlast ─────────────────────

describe('AC-8/AC-14 (Persistenz): sendPremiumSms laeuft durch den ganzen Versand-Speicherweg', () => {
	test('hydrateVersandFieldsFromPreset liest preset.send_premium_sms', () => {
		const preset = _preset({ send_premium_sms: true } as Partial<ComparePreset>);
		const snap = hydrateVersandFieldsFromPreset(preset) as unknown as Record<string, unknown>;
		assert.strictEqual(
			snap.sendPremiumSms,
			true,
			`AC-8: hydrateVersandFieldsFromPreset muss send_premium_sms in sendPremiumSms uebernehmen, erhalten: ${JSON.stringify(snap.sendPremiumSms)}`
		);
	});

	test('versandSnapshotAus fuehrt sendPremiumSms', () => {
		const target = { sendPremiumSms: true } as unknown as Parameters<typeof versandSnapshotAus>[0];
		const snap = versandSnapshotAus(target) as unknown as Record<string, unknown>;
		assert.strictEqual(snap.sendPremiumSms, true);
	});

	test('rollbackVersandSnapshot setzt sendPremiumSms auf den vorherigen Wert zurueck', () => {
		const state = { sendPremiumSms: true } as unknown as Parameters<typeof rollbackVersandSnapshot>[0];
		const before = { sendPremiumSms: false } as unknown as VersandSnapshot;
		const attempted = { sendPremiumSms: true } as unknown as VersandSnapshot;
		rollbackVersandSnapshot(state, before, attempted);
		assert.strictEqual(
			(state as unknown as Record<string, unknown>).sendPremiumSms,
			false,
			'AC-8: ein gescheiterter PUT muss sendPremiumSms auf den Vorwert zuruecksetzen.'
		);
	});

	test('baueVersandNutzlast sendet send_premium_sms aus current.sendPremiumSms', () => {
		const preset = _preset({ send_premium_sms: false } as Partial<ComparePreset>);
		const current = { sendPremiumSms: true } as unknown as VersandSnapshot;
		const { body } = baueVersandNutzlast(preset, current);
		assert.strictEqual(
			(body as unknown as Record<string, unknown>).send_premium_sms,
			true,
			'AC-8: baueVersandNutzlast muss send_premium_sms aus current.sendPremiumSms in den Body schreiben.'
		);
	});

	test('AC-14 (Persistenz-Teil): baueVersandNutzlast sendet NIEMALS alert_channels (Payload-Trennung)', () => {
		// preset traegt einen (moeglicherweise veralteten) alert_channels-Wert —
		// der Versand-Reiter darf ihn nie zurueckschreiben (Abschnitt 4 der Spec).
		const preset = _preset({
			alert_channels: { email: true, telegram: true, sms: false, premium_sms: true }
		} as Partial<ComparePreset>);
		const current = { sendPremiumSms: true } as unknown as VersandSnapshot;
		const { body } = baueVersandNutzlast(preset, current);
		assert.ok(
			!('alert_channels' in body),
			'AC-14/Abschnitt 4: die Versand-Nutzlast darf alert_channels (Alarm-Feld) NIE enthalten — ' +
				`gefunden: ${JSON.stringify((body as unknown as Record<string, unknown>).alert_channels)}`
		);
	});
});

// ─── VersandTab.svelte: Premium-SMS-Schalter im vergleich-Zweig freigeschaltet ─

describe('AC-8: VersandTab.svelte bindet die neuen Props und schaltet den vergleich-Zweig frei', () => {
	test('Props destrukturieren sendPremiumSms und onSendPremiumSmsChange', () => {
		const quelle = readFileSync(VERSAND_TAB, 'utf-8');
		const ast: Knoten = parse(quelle, { modern: true });
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
		const namen = ((muster!.id.properties as Knoten[]) ?? [])
			.map((p) => (p.key?.name ?? p.argument?.name) as string)
			.filter(Boolean);
		for (const pflicht of ['sendPremiumSms', 'onSendPremiumSmsChange']) {
			assert.ok(
				namen.includes(pflicht),
				`AC-8: VersandTab.svelte muss \`${pflicht}\` als Prop binden. Gebunden: ${namen.sort().join(', ')}`
			);
		}
	});

	test('der vergleich-Zweig reicht onPremiumSmsChange an VTBriefingChannels durch (Freischalt-Gate)', () => {
		const quelle = readFileSync(VERSAND_TAB, 'utf-8');
		const ast: Knoten = parse(quelle, { modern: true });
		const einbettungen = findeKomponenten(ast, 'VTBriefingChannels');
		// Der VERGLEICH-Zweig ist die ZWEITE Einbettung im Markup (erste ist
		// der route-Zweig, VersandTab.svelte:365-374).
		assert.ok(
			einbettungen.length >= 2,
			`Erwartet mindestens zwei <VTBriefingChannels>-Einbettungen (route + vergleich), gefunden: ${einbettungen.length}`
		);
		const vergleichsEinbettung = einbettungen[1];
		const ausdruck = attributAusdruck(vergleichsEinbettung, quelle, 'onPremiumSmsChange');
		assert.ok(
			ausdruck !== null,
			'AC-8: der vergleich-Zweig muss `onPremiumSmsChange` an <VTBriefingChannels> uebergeben — ' +
				'die ANWESENHEIT dieser Prop ist das bestehende Freischalt-Gate ' +
				'(VTBriefingChannels.svelte:57-63, ohne sie bleibt der feste "bald verfügbar"-Platzhalter stehen).'
		);
		const channelsAusdruck = attributAusdruck(vergleichsEinbettung, quelle, 'channels');
		assert.ok(
			channelsAusdruck !== null && channelsAusdruck.includes('premium_sms'),
			`AC-8: das \`channels\`-Objekt des vergleich-Zweigs muss ein premium_sms-Feld tragen, erhalten: ${channelsAusdruck}`
		);
	});
});
