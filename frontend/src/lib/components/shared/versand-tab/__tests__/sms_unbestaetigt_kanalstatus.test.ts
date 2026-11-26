// TDD RED — Issue #2406 (S3 aus #2153, Epic #2138), AC-14: eine eingetragene,
// aber NICHT bestaetigte SMS-Nummer darf in der Kanal-Anzeige nicht als
// sendebereit erscheinen.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-14 (und der
// kontextfreie Teil von AC-13).
//
// Naht: der kontextfreie Helfer `channelConnectionStatus`, echt gerufen.
// #3385: die Render-Faelle am Kanal-Baustein (VTBriefingChannels, Waise ohne
// Aufrufer) sind mit dem Baustein geloescht.
//
// Anzeige-Vertrag: der Status-Text lautet bei unbestaetigter Nummer
// „eingetragen, unbestätigt"; „hinterlegt" bleibt der bestaetigten Nummer
// vorbehalten.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

const { channelConnectionStatus } = (await import(
	pathToFileURL(
		path.join(FRONTEND, 'src/lib/components/shared/versand-tab/channelConnectionStatus.ts')
	).href
)) as { channelConnectionStatus: (p: unknown) => { sms: { tone: string; label: string } } };

const NUMMER = '+491511234567';
const AUSSTEHEND = '+491519876543';
const UNBESTAETIGT_LABEL = 'eingetragen, unbestätigt';

const PROFIL_UNBESTAETIGT = {
	sms_to: NUMMER,
	sms_allowed: true,
	sms_verified: false,
	pending_sms_to: AUSSTEHEND
};
const PROFIL_BESTAETIGT = {
	sms_to: NUMMER,
	sms_allowed: true,
	sms_verified: true
};

describe('#2406 AC-14 — unbestaetigte SMS-Nummer erscheint nicht als sendebereit', () => {
	test('kontextfreier_helfer_meldet_unbestaetigt', () => {
		const status = channelConnectionStatus(PROFIL_UNBESTAETIGT).sms;
		assert.notEqual(
			status.label,
			'hinterlegt',
			'AC-14: eine unbestaetigte Nummer darf nicht als „hinterlegt" gelten — ' +
				'channelConnectionStatus.ts wertet sms_verified noch nicht aus.'
		);
		assert.equal(
			status.label,
			UNBESTAETIGT_LABEL,
			`AC-14: erwarteter Status-Text „${UNBESTAETIGT_LABEL}", bekommen „${status.label}".`
		);
		assert.notEqual(
			status.tone,
			'good',
			'AC-14: der Ton darf bei unbestaetigter Nummer nicht „good" sein.'
		);
	});

	test('kontextfreier_helfer_meldet_bestaetigte_nummer_weiterhin_hinterlegt', () => {
		// Gegenprobe: ohne sie waere auch eine Sperre gruen, die JEDE Nummer verwirft.
		const status = channelConnectionStatus(PROFIL_BESTAETIGT).sms;
		assert.equal(
			status.label,
			'hinterlegt',
			`AC-14 Gegenprobe: die bestaetigte Nummer bleibt „hinterlegt", bekommen „${status.label}".`
		);
		assert.equal(status.tone, 'good');
	});
});
