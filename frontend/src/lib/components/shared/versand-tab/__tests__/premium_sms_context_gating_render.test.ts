// TDD RED — Issue #1717 (Scheibe S3): Premium-SMS in der Oberflaeche.
// Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md — AC-1.
//
// AC-1 ist die Kontext-Trennung: derselbe geteilte Kanal-Baustein
// (VTBriefingChannels) wird in VIER Mounts gerendert — einmal fuer das
// Trip-Briefing (`context="route"`, /trips/[id]) und dreimal fuer den
// Orts-Vergleich (`context="vergleich"`, /compare/[id] + /compare/new Desktop
// und Mobil, docs/context/feat-1717-s3-premium-sms-ui.md "Vier Mounts").
// Premium-SMS ist laut ADR-0049 ausschliesslich ein Trip-Briefing-Kanal; im
// Orts-Vergleich muss der feste "bald verfuegbar"-Platzhalter stehen bleiben.
//
// ZWEI NAEHTE, weil eine Naht die Zusicherung nicht traegt:
//   1. VTBriefingChannels selbst — rendert den schaltbaren Block nur, wenn die
//      Prop `onPremiumSmsChange` gesetzt ist (Muster `{#if onTelegramStyleChange}`,
//      VTBriefingChannels.svelte:155).
//   2. VersandTab — uebergibt diese Prop NUR im route-Zweig (:202-231), nie im
//      vergleich-Zweig (:232-285). Die in der Spec benannte Mutation
//      ("VersandTab uebergibt onPremiumSmsChange auch im vergleich-Zweig")
//      waere an Naht 1 allein UNSICHTBAR — deshalb wird hier der echte
//      Wirkort mitgemessen, nicht nur der Ort, an dem der Code steht.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponenten (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks.
//
// RED heute: beide Komponentenzweige rendern denselben fest deaktivierten
// Platzhalter (VTBriefingChannels.svelte:187-192) — es gibt weder die Prop
// `onPremiumSmsChange` noch das Testid `channel-status-premium-sms`.
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

describe('#1717 AC-1 — Premium-SMS ist nur im Trip-Briefing schaltbar', () => {
	test('premium_sms_switchable_only_in_route_context', () => {
		// ── Naht 1: der geteilte Baustein selbst, IDENTISCHES Profil ──────────
		const routeHtml = renderChannels(FRESH, true);
		const vergleichHtml = renderChannels(FRESH, false);

		assert.equal(
			isDisabled(checkboxInputTag(routeHtml, 'channel-premium-sms')),
			false,
			'AC-1 (route): Bei Premium-Tier und frischer Rueckadresse muss die Premium-SMS-Checkbox ' +
				'im Trip-Briefing editierbar sein (kein disabled-Attribut) — heute steht dort ein ' +
				'fest deaktivierter Platzhalter (VTBriefingChannels.svelte:187-192).'
		);
		assert.equal(
			isDisabled(checkboxInputTag(vergleichHtml, 'channel-premium-sms')),
			true,
			'AC-1 (vergleich): Ohne `onPremiumSmsChange` darf KEINE schaltbare Premium-SMS-Checkbox ' +
				'entstehen — Premium-SMS ist laut ADR-0049 kein Vergleichs-Kanal.'
		);

		// ── Naht 2: VersandTab — der Zweig, der die Prop uebergibt ────────────
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
			!tabVergleich.includes(SCHALTBAR_MARKER),
			'AC-1 (VersandTab vergleich): Der vergleich-Zweig darf `onPremiumSmsChange` NICHT ' +
				'uebergeben — sonst erscheint der schaltbare Premium-SMS-Block auf /compare/[id] und ' +
				'/compare/new (drei der vier Mounts).'
		);
	});

	test('vergleich_behaelt_den_unveraenderten_platzhalter_hinweis', () => {
		const vergleichHtml = renderChannels(FRESH, false);
		const tabVergleich = renderVersandTab('vergleich');
		const tabRoute = renderVersandTab('route');

		assert.ok(
			vergleichHtml.includes(PLATZHALTER_TEXT),
			`AC-1 (vergleich): Der unveraenderte "${PLATZHALTER_TEXT}"-Hinweis muss im Orts-Vergleich ` +
				'stehen bleiben.'
		);
		assert.ok(
			tabVergleich.includes(PLATZHALTER_TEXT),
			`AC-1 (VersandTab vergleich): "${PLATZHALTER_TEXT}" fehlt — der Vergleich haette dann ` +
				'einen Kanal ohne jede Erklaerung.'
		);
		assert.ok(
			!tabRoute.includes(PLATZHALTER_TEXT),
			`AC-1 (VersandTab route): "${PLATZHALTER_TEXT}" darf im Trip-Briefing NICHT mehr stehen — ` +
				'der Kanal ist seit S2a live und wird hier schaltbar.'
		);
	});
});
