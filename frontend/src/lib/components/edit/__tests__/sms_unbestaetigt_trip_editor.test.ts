// Issue #2406 (S3 aus #2153, Epic #2138), AC-14 — Wirkstelle Trip-Editor.
// Spec: docs/specs/modules/sms_nummer_verifikation.md
//
// Schwester-Test zu
// shared/versand-tab/__tests__/sms_unbestaetigt_kanalstatus.test.ts (dort:
// kontextfreier Helfer + VTBriefingChannels). Diese Datei bewacht die
// BAUSTEIN-EIGENEN Stellen von EditReportConfigSection.svelte, die kein
// anderer Test erreicht:
//   1. die lokale Kanal-Verfuegbarkeit `availableChannels.sms`
//      (EditReportConfigSection.svelte:123) — sie steuert `disabled` der
//      SMS-Checkbox; ohne `&& !!profile?.sms_verified` verspraeche der
//      Schalter einen Versand, den die Sperre in config.py verwirft (AC-1);
//   2. der Hinweis-Zweig `channel-sms-hint` (Zeile 427) — „Nummer noch nicht
//      bestaetigt".
// `channel_checkbox_dedupe_render.test.ts` rendert diese Komponente zwar,
// aber nur mit einem vollstaendig BESTAETIGTEN Profil und prueft nur
// Testid-Paritaet — der unbestaetigte Fall war unbewacht.
//
// Drei Testids unter einem Dach: `channel-sms-hint` wird von DREI sich
// gegenseitig ausschliessenden Zweigen getragen (sms_allowed === false /
// unbestaetigt / Nummer fehlt). Deshalb wird der TEXT geprueft, nicht die
// blosse Anwesenheit — sonst bliebe der Test gruen, wenn der
// Unbestaetigt-Zweig wegfaellt und stattdessen „Handynummer fehlt" erscheint.
//
// Echtes serverseitiges Rendern der echten Komponente (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks, kein
// Dateiinhalt-Grep. `profileOverride` ist der bestehende SSR-Testzugang der
// Komponente (Zeile 45-50) — `onMount` laeuft serverseitig nie.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/edit/__tests__/sms_unbestaetigt_trip_editor.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> edit -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const EditReportConfigSection = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/edit/EditReportConfigSection.svelte'))
			.href
	)
).default;

const NUMMER = '+491511234567';
const AUSSTEHEND = '+491519876543';

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

function renderEditor(profil: Record<string, unknown>): string {
	return render(EditReportConfigSection, {
		props: { reportConfig: {}, mode: 'edit', profileOverride: profil }
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

describe('#2406 AC-14 — Trip-Editor sperrt den SMS-Schalter bei unbestaetigter Nummer', () => {
	test('unbestaetigte_nummer_macht_den_sms_schalter_nicht_auswaehlbar', () => {
		const html = renderEditor(PROFIL_UNBESTAETIGT);
		assert.equal(
			istDeaktiviert(inputTag(html, 'channel-sms')),
			true,
			'AC-14: bei eingetragener, aber unbestaetigter Nummer muss die SMS-Checkbox im ' +
				'Trip-Editor deaktiviert sein (EditReportConfigSection.svelte:123).'
		);
	});

	test('unbestaetigte_nummer_erklaert_den_grund_im_hinweis', () => {
		const hinweis = textZuTestId(renderEditor(PROFIL_UNBESTAETIGT), 'channel-sms-hint');
		assert.ok(
			hinweis.includes('nicht bestätigt'),
			'AC-14: der Hinweis muss sagen, dass die Nummer noch nicht bestaetigt ist — ' +
				`bekommen: „${hinweis}" (EditReportConfigSection.svelte:427).`
		);
		assert.ok(
			!hinweis.includes('fehlt'),
			'AC-14: der Hinweis darf NICHT behaupten, die Nummer fehle — sie ist eingetragen, ' +
				`nur unbestaetigt. Bekommen: „${hinweis}".`
		);
	});

	test('unbestaetigte_nummer_zeigt_denselben_status_text_wie_der_versand_reiter', () => {
		// AC-14 verlangt denselben Wortlaut in BEIDEN rendernden Bausteinen.
		assert.equal(
			textZuTestId(renderEditor(PROFIL_UNBESTAETIGT), 'channel-status-sms'),
			'eingetragen, unbestätigt',
			'AC-14: der Trip-Editor muss denselben Status-Text zeigen wie VTBriefingChannels.'
		);
	});

	test('gegenprobe_bestaetigte_nummer_bleibt_schaltbar_und_ohne_hinweis', () => {
		// Ohne diese Gegenprobe waere auch eine Sperre gruen, die JEDE Nummer verwirft.
		const html = renderEditor(PROFIL_BESTAETIGT);
		assert.equal(
			istDeaktiviert(inputTag(html, 'channel-sms')),
			false,
			'AC-14 Gegenprobe: eine bestaetigte Nummer muss im Trip-Editor schaltbar bleiben.'
		);
		assert.equal(
			html.includes('data-testid="channel-sms-hint"'),
			false,
			'AC-14 Gegenprobe: bei bestaetigter Nummer darf KEIN SMS-Hinweis erscheinen.'
		);
	});
});
