// TDD RED — Issue #2154 Scheibe B: Premium-SMS-Verknüpfungscode im Konto.
// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md — AC-1,
// AC-2, AC-3, AC-4, AC-9, AC-11.
//
// `PremiumSmsLinkCard.svelte` existiert in der RED-Phase noch NICHT → der
// Import scheitert (Datei nicht gefunden) und alle Tests scheitern.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponente (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks, kein
// Dateiinhalt-Grep — Vorbild
// frontend/src/lib/components/shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts.
//
// Props-Vertrag (Spec, Abschnitt "Props-getriebene Karte statt Logik in
// +page.svelte"): { tier, exists, codeValue, busy, errorMsg,
// showRenewConfirm, onGenerateOrRenewClick, onDialogConfirm, onDialogCancel }.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/account/__tests__/premium_sms_link_card_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const PremiumSmsLinkCard = (
	await import(
		pathToFileURL(
			path.join(FRONTEND, 'src/lib/components/account/PremiumSmsLinkCard.svelte')
		).href
	)
).default;

interface CardProps {
	tier: 'free' | 'standard' | 'premium' | undefined;
	exists: boolean;
	codeValue: string | null;
	busy: boolean;
	errorMsg: string | null;
	showRenewConfirm: boolean;
	onGenerateOrRenewClick: () => void;
	onDialogConfirm: () => void;
	onDialogCancel: () => void;
}

function defaults(over: Partial<CardProps> = {}): CardProps {
	return {
		tier: 'premium',
		exists: false,
		codeValue: null,
		busy: false,
		errorMsg: null,
		showRenewConfirm: false,
		onGenerateOrRenewClick: () => {},
		onDialogConfirm: () => {},
		onDialogCancel: () => {},
		...over,
	};
}

function renderCard(over: Partial<CardProps> = {}): string {
	return render(PremiumSmsLinkCard, { props: defaults(over) }).body;
}

/** `<button .../>`-Tag direkt hinter dem gegebenen Testid (fuer disabled-Check). */
function tagAfterTestid(html: string, testid: string, tagStart = '<button'): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = html.indexOf(marker);
	assert.notEqual(markerIdx, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	// data-testid kann VOR oder NACH dem Tag-Start im Markup stehen — daher
	// rueckwaerts zum naechsten Tag-Start suchen, wenn testid ausserhalb liegt.
	let start = html.lastIndexOf(tagStart, markerIdx);
	if (start === -1) start = html.indexOf(tagStart, markerIdx);
	assert.notEqual(start, -1, `Kein "${tagStart}" um Testid "${testid}" gefunden.`);
	return html.slice(start, html.indexOf('>', start) + 1);
}

function isDisabled(tag: string): boolean {
	return /\bdisabled(=""|(?=[\s/>]))/.test(tag);
}

describe('AC-1: Premium-Nutzer ohne Code sieht "Code erzeugen", keinen Klartext', () => {
	test('exists=false, codeValue=null → Generate-Button da, Renew und Klartext fehlen', () => {
		const html = renderCard({ tier: 'premium', exists: false, codeValue: null });
		assert.ok(
			html.includes('data-testid="premium-sms-link-generate"'),
			'AC-1: "Code erzeugen"-Button fehlt bei fehlendem Code.'
		);
		assert.ok(
			!html.includes('data-testid="premium-sms-link-renew"'),
			'AC-1: "Code erneuern"-Button darf ohne bestehenden Code nicht erscheinen.'
		);
		assert.ok(
			!html.includes('data-testid="premium-sms-link-code-value"'),
			'AC-1: kein Klartext-Code darf sichtbar sein, wenn keiner erzeugt wurde.'
		);
	});
});

describe('AC-2: Nach erfolgreichem Erzeugen erscheint der Klartext-Code einmalig', () => {
	test('codeValue gesetzt → Klartext + Hinweis "wird nicht erneut angezeigt"', () => {
		const html = renderCard({ tier: 'premium', exists: true, codeValue: 'AB3CD9F' });
		assert.ok(
			html.includes('data-testid="premium-sms-link-code-value"'),
			'AC-2: der zurückgegebene Code muss angezeigt werden.'
		);
		assert.ok(html.includes('AB3CD9F'), 'AC-2: der tatsächliche Code-Wert fehlt im Markup.');
		assert.ok(
			html.includes('wird nicht erneut angezeigt'),
			'AC-2: der Hinweis, dass der Code nicht erneut erscheint, fehlt.'
		);
	});
});

describe('AC-3: Premium-Nutzer MIT bestehendem Code sieht "Code erneuern"', () => {
	test('exists=true, codeValue=null → Renew-Button da, Generate und Klartext fehlen', () => {
		const html = renderCard({ tier: 'premium', exists: true, codeValue: null });
		assert.ok(
			html.includes('data-testid="premium-sms-link-renew"'),
			'AC-3: "Code erneuern"-Button fehlt bei bestehendem Code.'
		);
		assert.ok(
			!html.includes('data-testid="premium-sms-link-generate"'),
			'AC-3: "Code erzeugen" darf bei bestehendem Code nicht erscheinen.'
		);
		assert.ok(
			!html.includes('data-testid="premium-sms-link-code-value"'),
			'AC-3: ohne frischen POST darf kein Klartext sichtbar sein.'
		);
	});
});

describe('AC-4: "Code erneuern" zeigt zuerst einen Bestätigungsdialog', () => {
	test('showRenewConfirm=true → Bestätigen/Abbrechen-Testids im Markup', () => {
		const html = renderCard({ tier: 'premium', exists: true, showRenewConfirm: true, codeValue: null });
		assert.ok(
			html.includes('data-testid="premium-sms-link-renew-confirm"'),
			'AC-4: Bestätigen-Button des Dialogs fehlt.'
		);
		assert.ok(
			html.includes('data-testid="premium-sms-link-renew-cancel"'),
			'AC-4: Abbrechen-Button des Dialogs fehlt.'
		);
	});

	test('showRenewConfirm=false → kein Dialog-Markup', () => {
		const html = renderCard({ tier: 'premium', exists: true, showRenewConfirm: false });
		assert.ok(
			!html.includes('data-testid="premium-sms-link-renew-confirm"'),
			'AC-4: der Dialog darf ohne showRenewConfirm nicht sichtbar sein.'
		);
	});
});

describe('AC-9: Fehlerfall zeigt eine verständliche Meldung', () => {
	test('errorMsg gesetzt → premium-sms-link-error erscheint mit dem Text', () => {
		const html = renderCard({ errorMsg: 'Code-Vorgang fehlgeschlagen' });
		assert.ok(
			html.includes('data-testid="premium-sms-link-error"'),
			'AC-9: Fehlermeldung fehlt im Markup.'
		);
		assert.ok(html.includes('Code-Vorgang fehlgeschlagen'), 'AC-9: Fehlertext fehlt im Markup.');
	});

	test('errorMsg=null → keine Fehlermeldung sichtbar', () => {
		const html = renderCard({ errorMsg: null });
		assert.ok(
			!html.includes('data-testid="premium-sms-link-error"'),
			'AC-9: ohne Fehler darf kein Fehler-Testid erscheinen.'
		);
	});
});

describe('AC-11: busy deaktiviert den sichtbaren Button', () => {
	test('exists=false, busy=true → Generate-Button ist disabled', () => {
		const html = renderCard({ tier: 'premium', exists: false, busy: true });
		assert.equal(
			isDisabled(tagAfterTestid(html, 'premium-sms-link-generate')),
			true,
			'AC-11: während eines laufenden Requests muss der Button deaktiviert sein.'
		);
	});

	test('exists=true, busy=true → Renew-Button ist disabled', () => {
		const html = renderCard({ tier: 'premium', exists: true, busy: true });
		assert.equal(
			isDisabled(tagAfterTestid(html, 'premium-sms-link-renew')),
			true,
			'AC-11: während eines laufenden Requests muss der Renew-Button deaktiviert sein.'
		);
	});

	test('busy=false → Button ist NICHT disabled', () => {
		const html = renderCard({ tier: 'premium', exists: false, busy: false });
		assert.equal(
			isDisabled(tagAfterTestid(html, 'premium-sms-link-generate')),
			false,
			'Ohne laufenden Request darf der Button nicht deaktiviert sein.'
		);
	});
});
