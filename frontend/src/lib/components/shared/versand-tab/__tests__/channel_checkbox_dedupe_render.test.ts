// TDD RED — Bugfix "Kontakt-Beschriftung + Verbindungsstatus der Kanal-
// Checkboxen bündeln" (#1510).
// Spec: docs/specs/modules/fix_1510_versand_ziel_dedupe.md — AC-2, AC-3, AC-4, AC-5, AC-6.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponenten
// (svelte/server `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs).
// Keine Mocks, keine reine Datei-Inhalt-Prüfung (Ausnahme AC-6: Testid-Existenz
// ist per Definition eine DOM-Prüfung, nicht Quelltext-Scan — der HTML-String
// IST hier das geprüfte Verhalten, nicht der .svelte-Quelltext).
//
// RED heute:
//   - `../channelContactLabel.ts` existiert nicht → die Datei crasht komplett
//     beim Import (ERR_MODULE_NOT_FOUND), ALLE Tests unten schlagen fehl.
//   - Zusätzlich, sobald `channelContactLabel.ts` existiert (nächste Phase):
//     AC-4 bleibt rot, weil `VTBriefingChannels.svelte`/`EditReportConfigSection.svelte`
//     die E-Mail-Checkbox heute an `!!profile?.mail_to` sperren (nicht an
//     `channelConnectionStatus(profile).email.tone === 'good'`) — eine
//     hinterlegte, aber unbestätigte Adresse macht die Checkbox heute NICHT
//     disabled, obwohl AC-4 das verlangt.
//   - AC-6 bleibt rot, weil `EditReportConfigSection.svelte` heute keine
//     `channel-status-*`-Testids rendert (nur `VTBriefingChannels.svelte` tut das).
//
// `profileOverride`-Prop (RED-Infrastruktur, s. beide .svelte-Dateien): Beide
// Komponenten laden `profile` sonst per `onMount`/`fetch`, das `svelte/server`s
// `render()` nicht ausführt — ohne den Override bliebe `profile` in SSR immer
// `null`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts

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
const { channelContactLabel } = await import('../channelContactLabel.ts');
const VTBriefingChannels = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/versand-tab/VTBriefingChannels.svelte')).href
	)
).default;
const EditReportConfigSection = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/edit/EditReportConfigSection.svelte')).href
	)
).default;

interface Profile {
	mail_to?: string;
	email_verified?: boolean;
	telegram_chat_id?: string;
	sms_to?: string;
	sms_allowed?: boolean;
}

const MAIL = 'anna@example.org';
const CHAT_ID = '4711';
const SMS = '+49150000000';

/** Sichtbarer Text eines SSR-Ergebnisses (Tags + Svelte-Kommentar-Anker raus). */
function visibleText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function renderBriefingChannels(profile: Profile | null): string {
	return render(VTBriefingChannels, {
		props: {
			channels: { email: false, telegram: false, sms: false },
			onEmailChange: () => {},
			onTelegramChange: () => {},
			onSmsChange: () => {},
			profileOverride: profile
		}
	}).body;
}

function renderEditSection(profile: Profile | null): string {
	return render(EditReportConfigSection, {
		props: {
			reportConfig: {},
			mode: 'edit',
			showMailContent: false,
			showSchedule: false,
			showChannels: true,
			profileOverride: profile
		}
	}).body;
}

/** Sichtbarer Text GENAU des Checkbox-Labels (Box + Beschriftung), das direkt
 * hinter dem gegebenen Testid gerendert wird — robust gegen umgebende
 * Markup-Unterschiede zwischen den beiden Komponenten. */
function checkboxLabelText(html: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = html.indexOf(marker);
	assert.notEqual(markerIdx, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const labelStart = html.indexOf('<label', markerIdx);
	assert.notEqual(labelStart, -1, `Kein <label> nach Testid "${testid}" gefunden.`);
	const labelEnd = html.indexOf('</label>', labelStart);
	assert.notEqual(labelEnd, -1, `Kein schliessendes </label> nach Testid "${testid}" gefunden.`);
	return visibleText(html.slice(labelStart, labelEnd + '</label>'.length));
}

/** `<input .../>`-Tag direkt hinter dem gegebenen Testid. */
function checkboxInputTag(html: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const markerIdx = html.indexOf(marker);
	assert.notEqual(markerIdx, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const inputStart = html.indexOf('<input', markerIdx);
	assert.notEqual(inputStart, -1, `Kein <input> nach Testid "${testid}" gefunden.`);
	const inputEnd = html.indexOf('>', inputStart);
	return html.slice(inputStart, inputEnd + 1);
}

/** true nur, wenn das boolsche `disabled`-Attribut im Tag gesetzt ist
 * (Svelte-SSR rendert es als `disabled=""`, oder laesst es bei `false` ganz weg). */
function isDisabled(inputTag: string): boolean {
	return /\bdisabled(=""|(?=[\s/>]))/.test(inputTag);
}

// ─── AC-2 ────────────────────────────────────────────────────────────────────

describe('AC-2: VTBriefingChannels zeigt die E-Mail-Beschriftung aus channelContactLabel()', () => {
	test('E-Mail-Checkbox-Text = "E-Mail" + channelContactLabel(profile).email', () => {
		const profile: Profile = { mail_to: MAIL, email_verified: true };
		const html = renderBriefingChannels(profile);
		const text = checkboxLabelText(html, 'channel-email');
		const expected = 'E-Mail' + channelContactLabel(profile).email;

		assert.equal(
			text,
			expected,
			`AC-2: Erwartet exakt "${expected}" als E-Mail-Checkbox-Text, gerendert "${text}".`
		);
	});
});

// ─── AC-3 ────────────────────────────────────────────────────────────────────

describe('AC-3: EditReportConfigSection zeigt dieselbe Kontakt-Beschriftung wie VTBriefingChannels', () => {
	test('E-Mail-Checkbox-Text von EditReportConfigSection = channelContactLabel(profile).email-Suffix', () => {
		const profile: Profile = { mail_to: MAIL, email_verified: true };
		const html = renderEditSection(profile);
		const text = checkboxLabelText(html, 'channel-email');
		const expected = 'E-Mail' + channelContactLabel(profile).email;

		assert.equal(
			text,
			expected,
			`AC-3: Erwartet exakt "${expected}" als E-Mail-Checkbox-Text in EditReportConfigSection, gerendert "${text}".`
		);
	});

	test('beide Komponenten zeigen für IDENTISCHES Profil denselben E-Mail-Checkbox-Text', () => {
		const profile: Profile = { mail_to: MAIL, email_verified: true };
		const vtText = checkboxLabelText(renderBriefingChannels(profile), 'channel-email');
		const editText = checkboxLabelText(renderEditSection(profile), 'channel-email');

		assert.equal(
			vtText,
			editText,
			`AC-3: VTBriefingChannels ("${vtText}") und EditReportConfigSection ("${editText}") weichen für dasselbe Profil ab.`
		);
	});
});

// ─── AC-4 ────────────────────────────────────────────────────────────────────

describe('AC-4: E-Mail-Checkbox nur bei bestätigter Adresse anklickbar — in BEIDEN Komponenten', () => {
	const FAELLE: Array<{ name: string; profile: Profile; erwartetDisabled: boolean }> = [
		{ name: 'keine mail_to', profile: {}, erwartetDisabled: true },
		{ name: 'mail_to gesetzt, email_verified: false', profile: { mail_to: MAIL, email_verified: false }, erwartetDisabled: true },
		{ name: 'mail_to gesetzt, email_verified: true', profile: { mail_to: MAIL, email_verified: true }, erwartetDisabled: false }
	];

	for (const fall of FAELLE) {
		test(`VTBriefingChannels — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderBriefingChannels(fall.profile), 'channel-email');
			assert.equal(
				isDisabled(inputTag),
				fall.erwartetDisabled,
				`AC-4 (VTBriefingChannels, ${fall.name}): erwartet disabled=${fall.erwartetDisabled}, Tag: ${inputTag}`
			);
		});

		test(`EditReportConfigSection — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderEditSection(fall.profile), 'channel-email');
			assert.equal(
				isDisabled(inputTag),
				fall.erwartetDisabled,
				`AC-4 (EditReportConfigSection, ${fall.name}): erwartet disabled=${fall.erwartetDisabled}, Tag: ${inputTag}`
			);
		});
	}
});

// ─── AC-5 ────────────────────────────────────────────────────────────────────

describe('AC-5: Telegram-/SMS-Checkbox-Sperre bleibt unverändert (Regression)', () => {
	const TELEGRAM_FAELLE: Array<{ name: string; profile: Profile; erwartetDisabled: boolean }> = [
		{ name: 'keine telegram_chat_id', profile: {}, erwartetDisabled: true },
		{ name: 'telegram_chat_id gesetzt', profile: { telegram_chat_id: CHAT_ID }, erwartetDisabled: false }
	];
	const SMS_FAELLE: Array<{ name: string; profile: Profile; erwartetDisabled: boolean }> = [
		{ name: 'keine sms_to', profile: {}, erwartetDisabled: true },
		{ name: 'sms_to gesetzt, sms_allowed: true', profile: { sms_to: SMS, sms_allowed: true }, erwartetDisabled: false },
		{ name: 'sms_to gesetzt, sms_allowed: false', profile: { sms_to: SMS, sms_allowed: false }, erwartetDisabled: true }
	];

	for (const fall of TELEGRAM_FAELLE) {
		test(`Telegram — VTBriefingChannels — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderBriefingChannels(fall.profile), 'channel-telegram');
			assert.equal(isDisabled(inputTag), fall.erwartetDisabled, `AC-5 (VT, Telegram, ${fall.name}): Tag ${inputTag}`);
		});
		test(`Telegram — EditReportConfigSection — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderEditSection(fall.profile), 'channel-telegram');
			assert.equal(isDisabled(inputTag), fall.erwartetDisabled, `AC-5 (Edit, Telegram, ${fall.name}): Tag ${inputTag}`);
		});
	}

	for (const fall of SMS_FAELLE) {
		test(`SMS — VTBriefingChannels — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderBriefingChannels(fall.profile), 'channel-sms');
			assert.equal(isDisabled(inputTag), fall.erwartetDisabled, `AC-5 (VT, SMS, ${fall.name}): Tag ${inputTag}`);
		});
		test(`SMS — EditReportConfigSection — ${fall.name} → disabled === ${fall.erwartetDisabled}`, () => {
			const inputTag = checkboxInputTag(renderEditSection(fall.profile), 'channel-sms');
			assert.equal(isDisabled(inputTag), fall.erwartetDisabled, `AC-5 (Edit, SMS, ${fall.name}): Tag ${inputTag}`);
		});
	}
});

// ─── AC-6 ────────────────────────────────────────────────────────────────────

describe('AC-6: EditReportConfigSection zeigt Dot+Label-Verbindungsstatus wie VTBriefingChannels', () => {
	test('alle drei channel-status-* Testids erscheinen bei vollständig hinterlegtem Profil', () => {
		const profile: Profile = {
			mail_to: MAIL,
			email_verified: true,
			telegram_chat_id: CHAT_ID,
			sms_to: SMS,
			sms_allowed: true
		};
		const html = renderEditSection(profile);

		for (const testid of ['channel-status-email', 'channel-status-telegram', 'channel-status-sms']) {
			assert.ok(
				html.includes(`data-testid="${testid}"`),
				`AC-6: Testid "${testid}" fehlt in EditReportConfigSection — heute existiert dort kein ` +
					'Dot+Label-Verbindungsstatus (nur in VTBriefingChannels).'
			);
		}
	});
});
