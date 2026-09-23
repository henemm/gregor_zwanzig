// TDD RED — Issue #2406 (S3 aus #2153, Epic #2138), AC-14: eine eingetragene,
// aber NICHT bestaetigte SMS-Nummer darf in der Kanal-Anzeige nicht als
// sendebereit erscheinen.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-14 (und der
// kontextfreie Teil von AC-13).
//
// Zwei Naehte, beide echt gerendert bzw. echt gerufen:
//   1. der kontextfreie Helfer `channelConnectionStatus` — die gemeinsame
//      Quelle beider Aufrufer (VTBriefingChannels, EditReportConfigSection);
//   2. der context-bewusste Baustein `VTBriefingChannels.svelte`, gerendert
//      EINMAL mit context="route" und EINMAL mit context="vergleich" — die
//      Pendant-Regel (CLAUDE.md) verlangt identisches Verhalten in beiden
//      Kontexten; eine Sonderbehandlung je Kontext waere ein Verstoss.
//
// Echtes serverseitiges Rendern der echten Komponente (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks, kein
// Dateiinhalt-Grep.
//
// Anzeige-Vertrag fuer /50 (einzige Vorgabe an die Form): der Status-Text bei
// `data-testid="channel-status-sms"` lautet bei unbestaetigter Nummer
// „eingetragen, unbestätigt"; „hinterlegt" bleibt der bestaetigten Nummer
// vorbehalten. Die Checkbox `channel-sms` ist bei unbestaetigter Nummer
// deaktiviert (sie verspricht sonst einen Versand, den die Sperre in
// config.py ohnehin verhindert, AC-1).
//
// RED heute: `channelConnectionStatus` kennt `sms_verified` nicht und meldet
// bei gesetztem `sms_to` „hinterlegt" (channelConnectionStatus.ts:60).
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const VTBriefingChannels = (
	await import(
		pathToFileURL(
			path.join(FRONTEND, 'src/lib/components/shared/versand-tab/VTBriefingChannels.svelte')
		).href
	)
).default;
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

function renderKanaele(profil: Record<string, unknown>, context: 'route' | 'vergleich'): string {
	return render(VTBriefingChannels, {
		props: {
			context,
			channels: { email: false, telegram: false, sms: false },
			onEmailChange: () => {},
			onTelegramChange: () => {},
			onSmsChange: () => {},
			profileOverride: profil
		}
	}).body;
}

/** Sichtbarer Text des Elements zum testid (SSR-Kommentare/Tags entfernt). */
function textZuTestId(html: string, testid: string): string {
	const marker = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(marker, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const start = html.lastIndexOf('<', marker);
	const tag = (html.slice(start).match(/^<([a-zA-Z0-9-]+)/) ?? [])[1];
	assert.ok(tag, `Kein Tag-Name zu data-testid="${testid}".`);
	const re = new RegExp(`<${tag}[\\s>]|</${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			tiefe -= 1;
			if (tiefe === 0) {
				return html
					.slice(start, m.index + m[0].length)
					.replace(/<!--[\s\S]*?-->/g, '')
					.replace(/<[^>]+>/g, ' ')
					.replace(/\s+/g, ' ')
					.trim();
			}
		} else {
			tiefe += 1;
		}
	}
	assert.fail(`Element zu data-testid="${testid}" nicht geschlossen.`);
}

/** `<input …>`-Tag direkt hinter dem testid. */
function inputTag(html: string, testid: string): string {
	const markerIdx = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(markerIdx, -1, `Testid "${testid}" nicht gefunden.`);
	const inputStart = html.indexOf('<input', markerIdx);
	assert.notEqual(inputStart, -1, `Kein <input> nach Testid "${testid}".`);
	return html.slice(inputStart, html.indexOf('>', inputStart) + 1);
}

function istDeaktiviert(tag: string): boolean {
	return /\bdisabled(=""|(?=[\s/>]))/.test(tag);
}

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

	for (const context of ['route', 'vergleich'] as const) {
		test(`baustein_zeigt_unbestaetigt_im_context_${context}`, () => {
			const html = renderKanaele(PROFIL_UNBESTAETIGT, context);
			assert.equal(
				textZuTestId(html, 'channel-status-sms'),
				UNBESTAETIGT_LABEL,
				`AC-14 (${context}): der SMS-Status muss „${UNBESTAETIGT_LABEL}" zeigen.`
			);
			assert.equal(
				istDeaktiviert(inputTag(html, 'channel-sms')),
				true,
				`AC-14 (${context}): die SMS-Checkbox muss bei unbestaetigter Nummer deaktiviert sein.`
			);
		});
	}

	test('beide_kontexte_verhalten_sich_identisch', () => {
		// Pendant-Regel (CLAUDE.md): kein context-eigener Sonderweg.
		const route = textZuTestId(renderKanaele(PROFIL_UNBESTAETIGT, 'route'), 'channel-status-sms');
		const vergleich = textZuTestId(
			renderKanaele(PROFIL_UNBESTAETIGT, 'vergleich'),
			'channel-status-sms'
		);
		assert.equal(
			route,
			vergleich,
			`AC-14: route („${route}") und vergleich („${vergleich}") muessen denselben SMS-Status zeigen.`
		);
		const routeB = textZuTestId(renderKanaele(PROFIL_BESTAETIGT, 'route'), 'channel-status-sms');
		const vergleichB = textZuTestId(
			renderKanaele(PROFIL_BESTAETIGT, 'vergleich'),
			'channel-status-sms'
		);
		assert.equal(routeB, vergleichB, 'AC-14: auch der bestaetigte Fall muss identisch sein.');
		assert.notEqual(
			route,
			routeB,
			'AC-14: bestaetigt und unbestaetigt duerfen nicht denselben Text zeigen.'
		);
	});

	test('bestaetigte_nummer_bleibt_schaltbar', () => {
		for (const context of ['route', 'vergleich'] as const) {
			const html = renderKanaele(PROFIL_BESTAETIGT, context);
			assert.equal(
				istDeaktiviert(inputTag(html, 'channel-sms')),
				false,
				`AC-14 Gegenprobe (${context}): die bestaetigte Nummer muss schaltbar bleiben.`
			);
		}
	});
});
