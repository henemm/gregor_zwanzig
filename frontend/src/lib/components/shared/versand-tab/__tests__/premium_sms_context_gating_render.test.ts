// Issue #1717 (Scheibe S3): Premium-SMS in der Oberflaeche.
// Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md — AC-1.
//
// 🔴 Issue #2293 Scheibe S2 (#2448, Architektur-Entscheidung): die urspruengliche
// AC-1-Zusicherung dieser Datei ("Premium-SMS ist laut ADR-0049 ausschliesslich
// ein Trip-Briefing-Kanal, im Orts-Vergleich bleibt der feste Platzhalter")
// beruhte auf einem irrefuehrenden Code-Kommentar, keinem ADR-Beschluss —
// ADR-0049 aeussert sich nicht zum Ortsvergleich (sie beschreibt ausdruecklich
// nur die S2a-Lieferung fuers Trip-Briefing). Mit #2448 bekommt der
// Versand-Reiter des Ortsvergleichs einen EIGENEN, echten Premium-SMS-Schalter
// (AC-8/AC-9/AC-14 der Spec `feat_2293_s2_compare_alarm_kanaele.md`) — DIESELBE
// Naht-2-Verdrahtung wie im Trip-Briefing. Die Tests unten sind auf die NEUE
// Zusicherung umgestellt (schaltbar in BEIDEN Kontexten), nicht geloescht.
//
// ZWEI NAEHTE, weil eine Naht die Zusicherung nicht traegt:
//   1. VTBriefingChannels selbst — rendert den schaltbaren Block nur, wenn die
//      Prop `onPremiumSmsChange` gesetzt ist (Muster `{#if onTelegramStyleChange}`,
//      VTBriefingChannels.svelte:155). Diese Naht bleibt unveraendert wichtig:
//      OHNE Handler bleibt der feste Platzhalter — das ist weiterhin das
//      strukturelle Freischalt-Gate der geteilten Komponente.
//   2. VersandTab — uebergibt diese Prop seit #2293 S2 in BEIDEN Zweigen
//      (route UND vergleich).
//
// Echtes serverseitiges Rendern der echten Svelte-Komponenten (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts

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
const VersandTab = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte')).href
	)
).default;

interface PremiumProfile {
	sms_to?: string;
	sms_allowed?: boolean;
	premium_sms_allowed?: boolean;
	premium_sms_reply_to?: string;
	premium_sms_reply_at?: string;
	premium_sms_reply_state?: 'none' | 'stale' | 'fresh';
}

/** Vollstaendig gueltiges Premium-Profil (Premium-Tier, frische Rueckadresse). */
const FRESH: PremiumProfile = {
	sms_to: '+49150000000',
	sms_allowed: true,
	premium_sms_allowed: true,
	premium_sms_reply_to: '15551234567',
	premium_sms_reply_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
	premium_sms_reply_state: 'fresh'
};

/** `<input .../>`-Tag direkt hinter dem gegebenen Testid. */
function checkboxInputTag(html: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = html.indexOf(marker);
	assert.notEqual(markerIdx, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const inputStart = html.indexOf('<input', markerIdx);
	assert.notEqual(inputStart, -1, `Kein <input> nach Testid "${testid}" gefunden.`);
	return html.slice(inputStart, html.indexOf('>', inputStart) + 1);
}

/** true nur, wenn das boolsche `disabled`-Attribut im Tag gesetzt ist. */
function isDisabled(inputTag: string): boolean {
	return /\bdisabled(=""|(?=[\s/>]))/.test(inputTag);
}

function renderChannels(profile: PremiumProfile | null, withPremiumHandler: boolean): string {
	const props: Record<string, unknown> = {
		channels: { email: false, telegram: false, sms: false, premium_sms: false },
		onEmailChange: () => {},
		onTelegramChange: () => {},
		onSmsChange: () => {},
		profileOverride: profile
	};
	if (withPremiumHandler) props.onPremiumSmsChange = () => {};
	return render(VTBriefingChannels, { props }).body;
}

function renderVersandTab(context: 'route' | 'vergleich'): string {
	return render(VersandTab, { props: { context } }).body;
}

const SCHALTBAR_MARKER = 'data-testid="channel-status-premium-sms"';
const PLATZHALTER_TEXT = 'bald verfügbar';

describe('#1717 AC-1 / #2293 S2 (#2448) — Premium-SMS ist in BEIDEN Kontexten schaltbar', () => {
	test('premium_sms_checkbox_gating_folgt_der_handler_praesenz', () => {
		// ── Naht 1: der geteilte Baustein selbst, IDENTISCHES Profil ──────────
		// Strukturelles Gate unveraendert: OHNE `onPremiumSmsChange` bleibt die
		// Checkbox gesperrt, unabhaengig vom Kontext-Label.
		const handlerPresentHtml = renderChannels(FRESH, true);
		const handlerAbsentHtml = renderChannels(FRESH, false);

		assert.equal(
			isDisabled(checkboxInputTag(handlerPresentHtml, 'channel-premium-sms')),
			false,
			'Bei Premium-Tier und frischer Rueckadresse muss die Premium-SMS-Checkbox editierbar ' +
				'sein (kein disabled-Attribut), sobald `onPremiumSmsChange` gesetzt ist.'
		);
		assert.equal(
			isDisabled(checkboxInputTag(handlerAbsentHtml, 'channel-premium-sms')),
			true,
			'Ohne `onPremiumSmsChange` darf KEINE schaltbare Premium-SMS-Checkbox entstehen — das ' +
				'ist weiterhin das strukturelle Freischalt-Gate der geteilten Komponente ' +
				'(VTBriefingChannels.svelte:208).'
		);

		// ── Naht 2: VersandTab — beide Zweige uebergeben die Prop (#2293 S2) ──
		// Ohne Profil (SSR fuehrt onMount/fetch nicht aus) unterscheidet nicht das
		// disabled-Attribut die beiden Zweige, sondern OB der schaltbare Block
		// ueberhaupt gerendert wird.
		const tabRoute = renderVersandTab('route');
		const tabVergleich = renderVersandTab('vergleich');

		assert.ok(
			tabRoute.includes(SCHALTBAR_MARKER),
			'AC-1 (VersandTab route): Der route-Zweig muss `onPremiumSmsChange` uebergeben, damit der ' +
				`schaltbare Premium-SMS-Block (${SCHALTBAR_MARKER}) entsteht.`
		);
		assert.ok(
			tabVergleich.includes(SCHALTBAR_MARKER),
			'AC-8/#2448 (VersandTab vergleich): der vergleich-Zweig muss seit Issue #2293 S2 ' +
				`ebenfalls \`onPremiumSmsChange\` uebergeben, damit der schaltbare Premium-SMS-Block ` +
				`(${SCHALTBAR_MARKER}) auf /compare/[id] und /compare/new entsteht — die Anwesenheit ` +
				'dieser Prop ist das bestehende Freischalt-Gate der Komponente.'
		);
	});

	test('der feste Platzhalter-Hinweis steht nur noch OHNE Handler — in keinem der beiden Kontexte mehr', () => {
		const handlerAbsentHtml = renderChannels(FRESH, false);
		const tabVergleich = renderVersandTab('vergleich');
		const tabRoute = renderVersandTab('route');

		assert.ok(
			handlerAbsentHtml.includes(PLATZHALTER_TEXT),
			`Ohne \`onPremiumSmsChange\` muss der feste "${PLATZHALTER_TEXT}"-Hinweis weiterhin stehen ` +
				'(strukturelles Gate der geteilten Komponente).'
		);
		assert.ok(
			!tabVergleich.includes(PLATZHALTER_TEXT),
			`AC-8/#2448 (VersandTab vergleich): "${PLATZHALTER_TEXT}" darf im Ortsvergleich NICHT mehr ` +
				'stehen — der Kanal ist seit #2293 S2 live und wird hier schaltbar (eigener ' +
				'Versand-Schalter, AC-8).'
		);
		assert.ok(
			!tabRoute.includes(PLATZHALTER_TEXT),
			`AC-1 (VersandTab route): "${PLATZHALTER_TEXT}" darf im Trip-Briefing NICHT mehr stehen — ` +
				'der Kanal ist seit S2a live und wird hier schaltbar.'
		);
	});
});
