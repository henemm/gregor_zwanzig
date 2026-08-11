// TDD RED — Bugfix "Kontakt-Beschriftung + Verbindungsstatus der Kanal-
// Checkboxen bündeln" (#1510).
// Spec: docs/specs/modules/fix_1510_versand_ziel_dedupe.md — AC-2, AC-3, AC-4, AC-5, AC-6.
//
// ERWEITERT 2026-08-11 um Issue #1717 (Scheibe S3, Premium-SMS in der
// Oberflaeche) — Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md,
// AC-2, AC-3, AC-4, AC-9, AC-10. Diese Datei ist das Regressionsnetz, das die
// beiden Kanalblock-Kopien (VTBriefingChannels fuer /trips/[id],
// EditReportConfigSection fuer /trips/new) synchron haelt: jeder neue Fall wird
// gegen BEIDE Komponenten mit demselben Profil gemessen. Der #1717-Abschnitt
// steht unten unter "── #1717 ──".
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

const VT_FILE = path.join(
	FRONTEND,
	'src/lib/components/shared/versand-tab/VTBriefingChannels.svelte'
);
const EDIT_FILE = path.join(FRONTEND, 'src/lib/components/edit/EditReportConfigSection.svelte');

const { render } = await import('svelte/server');
const { channelContactLabel } = await import('../channelContactLabel.ts');
const VTBriefingChannels = (await import(pathToFileURL(VT_FILE).href)).default;
const EditReportConfigSection = (await import(pathToFileURL(EDIT_FILE).href)).default;

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

// ══════════════════════════════════════════════════════════════════════════════
// ── #1717 (S3) — Premium-SMS in der Oberflaeche ──────────────────────────────
// Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md — AC-2, AC-3, AC-4,
// AC-9, AC-10. Gemessen wird IMMER gegen beide Komponenten mit demselben
// Profil; genau das ist der Zweck dieser Datei.
//
// TESTID-VERTRAG, den dieser Abschnitt festnagelt (Implementierung Phase 6,
// Namensfamilie wie der Bestand `channel-sms` / `channel-status-sms` /
// `channel-sms-hint`):
//   channel-premium-sms              (Bestand) Checkbox + Beschriftung
//   channel-status-premium-sms       Dot + Mono-Status-Label
//   channel-premium-sms-hint         Prosa-Hinweis (drei Zustaende)
//   channel-premium-sms-reported-at  Meldedatum-Label ("zuletzt gemeldet am …")
//
// PROP-VERTRAG:
//   VTBriefingChannels: `channels.premium_sms: boolean` + `onPremiumSmsChange`
//     (Anwesenheit der Prop schaltet den Block frei, AC-1).
//   EditReportConfigSection: `reportConfig.send_premium_sms` — der
//     Anhak-Zustand muss BEIM RENDERN stehen. `svelte/server` fuehrt `onMount`
//     NICHT aus; eine Hydration allein in `onMount` ist deshalb hier nicht
//     sichtbar. Der State muss (analog `profile`, EditReportConfigSection.svelte:98
//     mit `untrack`) aus der Prop initialisiert werden.
// ══════════════════════════════════════════════════════════════════════════════

const { readFileSync } = await import('node:fs');
const { compile } = await import('svelte/compiler');

interface PremiumProfile extends Profile {
	premium_sms_allowed?: boolean;
	premium_sms_reply_to?: string;
	premium_sms_reply_at?: string;
	premium_sms_reply_state?: 'none' | 'stale' | 'fresh';
}

const REPLY_TO = '15551234567';
/** Fester Meldezeitpunkt — AC-4 prueft eine daraus abgeleitete Datumsdarstellung.
 * Mittags UTC, damit keine Zeitzonenverschiebung den Kalendertag dreht. */
const REPLY_AT = '2026-08-05T12:00:00Z';

const P_FRESH: PremiumProfile = {
	sms_to: SMS,
	sms_allowed: true,
	premium_sms_allowed: true,
	premium_sms_reply_to: REPLY_TO,
	premium_sms_reply_at: REPLY_AT,
	premium_sms_reply_state: 'fresh'
};
const P_STALE: PremiumProfile = { ...P_FRESH, premium_sms_reply_state: 'stale' };
const P_NONE: PremiumProfile = {
	sms_to: SMS,
	sms_allowed: true,
	premium_sms_allowed: true,
	premium_sms_reply_state: 'none'
};

function renderVTPremium(profile: PremiumProfile | null, premiumChecked = false): string {
	return render(VTBriefingChannels, {
		props: {
			channels: { email: false, telegram: false, sms: false, premium_sms: premiumChecked },
			onEmailChange: () => {},
			onTelegramChange: () => {},
			onSmsChange: () => {},
			onPremiumSmsChange: () => {},
			profileOverride: profile
		}
	}).body;
}

function renderEditPremium(profile: PremiumProfile | null, premiumChecked = false): string {
	return render(EditReportConfigSection, {
		props: {
			reportConfig: premiumChecked ? { send_premium_sms: true } : {},
			mode: 'edit',
			showMailContent: false,
			showSchedule: false,
			showChannels: true,
			profileOverride: profile
		}
	}).body;
}

/** Die beiden Renderer als Paar — jeder #1717-Fall laeuft gegen BEIDE. */
const BEIDE: Array<[string, (p: PremiumProfile | null, c?: boolean) => string]> = [
	['VTBriefingChannels', renderVTPremium],
	['EditReportConfigSection', renderEditPremium]
];

/** Aeusseres HTML des Elements, das das gegebene Testid traegt (Tag-Nesting-
 * zaehlend, damit verschachtelte gleichnamige Tags korrekt geschlossen werden). */
function outerHtml(html: string, testid: string): string {
	const marker = `data-testid="${testid}"`;
	const mi = html.indexOf(marker);
	assert.notEqual(
		mi,
		-1,
		`Testid "${testid}" fehlt im gerenderten HTML — der schaltbare Premium-SMS-Block ` +
			'existiert dort noch nicht (heute: fest deaktivierter Platzhalter). Erwartete Testids: ' +
			'siehe "TESTID-VERTRAG" im #1717-Kopf dieser Datei.'
	);
	const start = html.lastIndexOf('<', mi);
	const tag = /^<([a-zA-Z0-9-]+)/.exec(html.slice(start, start + 40))?.[1];
	assert.ok(tag, `Kein Tag-Name vor Testid "${testid}" gefunden.`);
	const re = new RegExp(`<${tag}\\b[^>]*>|</${tag}>`, 'g');
	re.lastIndex = start;
	let depth = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			depth--;
			if (depth === 0) return html.slice(start, m.index + m[0].length);
		} else if (m[0].endsWith('/>')) {
			if (m.index === start) return m[0];
		} else {
			depth++;
		}
	}
	assert.fail(`Element zu Testid "${testid}" nicht geschlossen.`);
}

function elementText(html: string, testid: string): string {
	return visibleText(outerHtml(html, testid));
}

/** Dot-Ton des Verbindungsstatus (Dot rendert `data-tone`, ui/dot/Dot.svelte). */
function dotTone(html: string, testid: string): string {
	const outer = outerHtml(html, testid);
	const m = /data-tone="([^"]*)"/.exec(outer);
	assert.ok(m, `Kein Dot (data-tone) innerhalb von "${testid}" — Verbindungsstatus fehlt.`);
	return m[1];
}

/** true nur, wenn das boolsche `checked`-Attribut im Tag gesetzt ist. */
function isChecked(inputTag: string): boolean {
	return /\bchecked(=""|(?=[\s/>]))/.test(inputTag);
}

/** Scoped CSS der Komponente — Daten, um die am gerenderten Element
 * TATSAECHLICH zugewiesene Textfarbe aufzuloesen (AC-9). */
function scopedCss(file: string): string {
	return compile(readFileSync(file, 'utf-8'), { generate: 'server', filename: file }).css?.code ?? '';
}

/** Farb-Token, das am gerenderten Element wirkt: inline `style` gewinnt, sonst
 * ueber die am Element zugewiesenen Klassen aus dem Komponenten-CSS. */
function resolveColorToken(outer: string, cssCode: string): string | null {
	const openTag = outer.slice(0, outer.indexOf('>') + 1);
	const inline = /style="([^"]*)"/.exec(openTag);
	if (inline) {
		const m = /color\s*:\s*var\(\s*(--[a-z0-9-]+)/i.exec(inline[1]);
		if (m) return m[1];
	}
	const cls = /class="([^"]*)"/.exec(openTag);
	if (!cls) return null;
	const names = cls[1].split(/\s+/).filter((c) => c && !c.startsWith('svelte-'));
	for (const name of names) {
		const rule = new RegExp(`\\.${name}\\b[^{}]*\\{([^}]*)\\}`, 'g');
		let m: RegExpExecArray | null;
		while ((m = rule.exec(cssCode))) {
			const c = /color\s*:\s*var\(\s*(--[a-z0-9-]+)/i.exec(m[1]);
			if (c) return c[1];
		}
	}
	return null;
}

// ─── #1717 AC-2 ──────────────────────────────────────────────────────────────

describe('#1717 AC-2: beide Komponenten zeigen denselben Premium-SMS-Zustand', () => {
	test('beide_komponenten_zeigen_fuer_identisches_profil_denselben_premium_sms_zustand', () => {
		for (const [name, profile] of [
			['none', P_NONE],
			['stale', P_STALE],
			['fresh', P_FRESH]
		] as Array<[string, PremiumProfile]>) {
			const vt = renderVTPremium(profile);
			const edit = renderEditPremium(profile);

			assert.equal(
				checkboxLabelText(vt, 'channel-premium-sms'),
				checkboxLabelText(edit, 'channel-premium-sms'),
				`AC-2 (${name}): Beschriftung der Premium-SMS-Checkbox weicht zwischen den beiden ` +
					'Komponenten ab — sie muessen denselben geteilten Helfer benutzen.'
			);
			assert.equal(
				elementText(vt, 'channel-status-premium-sms'),
				elementText(edit, 'channel-status-premium-sms'),
				`AC-2 (${name}): Verbindungsstatus-Label weicht ab.`
			);
			assert.equal(
				dotTone(vt, 'channel-status-premium-sms'),
				dotTone(edit, 'channel-status-premium-sms'),
				`AC-2 (${name}): Dot-Ton weicht ab.`
			);
			assert.equal(
				elementText(vt, 'channel-premium-sms-hint'),
				elementText(edit, 'channel-premium-sms-hint'),
				`AC-2 (${name}): Hinweistext weicht ab.`
			);
			assert.equal(
				isDisabled(checkboxInputTag(vt, 'channel-premium-sms')),
				isDisabled(checkboxInputTag(edit, 'channel-premium-sms')),
				`AC-2 (${name}): Deaktiviert-Zustand weicht ab — eine der beiden Seiten laesst ` +
					'einschalten, was die andere sperrt.'
			);
		}
	});
});

// ─── #1717 AC-3 ──────────────────────────────────────────────────────────────

describe('#1717 AC-3: drei Zustaende, drei verschiedene Hinweistexte', () => {
	test('premium_sms_drei_zustaende_zeigen_unterschiedlichen_hinweistext', () => {
		for (const [komponente, renderer] of BEIDE) {
			const hints = (
				[
					['none', P_NONE],
					['stale', P_STALE],
					['fresh', P_FRESH]
				] as Array<[string, PremiumProfile]>
			).map(([name, profile]) => {
				const text = elementText(renderer(profile), 'channel-premium-sms-hint');
				assert.ok(
					text.trim().length > 0,
					`AC-3 (${komponente}, ${name}): leerer Hinweistext — der Zustand bleibt unerklaert.`
				);
				return [name, text] as const;
			});

			for (let i = 0; i < hints.length; i++) {
				for (let j = i + 1; j < hints.length; j++) {
					assert.notEqual(
						hints[i][1],
						hints[j][1],
						`AC-3 (${komponente}): "${hints[i][0]}" und "${hints[j][0]}" zeigen denselben Text ` +
							`("${hints[i][1]}") — "keine Adresse" ist dann nicht von "veraltete Adresse" ` +
							'zu unterscheiden.'
					);
				}
			}
		}
	});
});

// ─── #1717 AC-4 ──────────────────────────────────────────────────────────────

describe('#1717 AC-4: frische Rueckadresse zeigt Zielnummer UND Meldedatum', () => {
	/** Plausible Darstellungen des Fixture-Datums. */
	const datumsKandidaten = (iso: string): string[] => {
		const d = new Date(iso);
		const j = d.getFullYear();
		const m = d.getMonth() + 1;
		const t = d.getDate();
		const pad = (n: number) => String(n).padStart(2, '0');
		return [
			`${pad(t)}.${pad(m)}.${j}`,
			`${t}.${m}.${j}`,
			`${j}-${pad(m)}-${pad(t)}`,
			`${pad(t)}.${pad(m)}.`,
			d.toLocaleDateString('de-DE')
		];
	};

	test('premium_sms_fresh_zeigt_zielnummer_und_meldedatum', () => {
		for (const [komponente, renderer] of BEIDE) {
			const html = renderer(P_FRESH);
			const sichtbar = [
				checkboxLabelText(html, 'channel-premium-sms'),
				elementText(html, 'channel-status-premium-sms'),
				elementText(html, 'channel-premium-sms-hint'),
				elementText(html, 'channel-premium-sms-reported-at')
			].join(' | ');

			assert.ok(
				sichtbar.includes(REPLY_TO),
				`AC-4 (${komponente}): Die gelernte Zielnummer "${REPLY_TO}" steht nicht im sichtbaren ` +
					`Text der Premium-SMS-Zeile — gerendert: "${sichtbar}".`
			);
			const kandidaten = datumsKandidaten(REPLY_AT);
			assert.ok(
				kandidaten.some((k) => sichtbar.includes(k)),
				`AC-4 (${komponente}): Kein Meldedatum sichtbar (erwartet eine Darstellung von ` +
					`${REPLY_AT}, z.B. ${kandidaten.slice(0, 3).join(' / ')}) — gerendert: "${sichtbar}".`
			);
		}
	});
});

// ─── #1717 AC-9 ──────────────────────────────────────────────────────────────

describe('#1717 AC-9: Meldedatum ist ein Daten-Label, keine Fussnote', () => {
	test('meldedatum_label_nutzt_nicht_die_platzhalter_kontrastfarbe', () => {
		const ERLAUBT = ['--g-ink', '--g-ink-1', '--g-ink-2', '--g-ink-3'];
		for (const [komponente, renderer, file] of [
			['VTBriefingChannels', renderVTPremium, VT_FILE],
			['EditReportConfigSection', renderEditPremium, EDIT_FILE]
		] as Array<[string, (p: PremiumProfile | null) => string, string]>) {
			const css = scopedCss(file);
			for (const [name, profile] of [
				['fresh', P_FRESH],
				['stale', P_STALE]
			] as Array<[string, PremiumProfile]>) {
				const outer = outerHtml(renderer(profile), 'channel-premium-sms-reported-at');
				const token = resolveColorToken(outer, css);

				assert.notEqual(
					token,
					'--g-ink-4',
					`AC-9 (${komponente}, ${name}): Das Meldedatum-Label nutzt --g-ink-4 (2,85:1 auf Weiss, ` +
						'strikt Platzhalter/Disabled vorbehalten). Es ist ein Daten-Label und braucht ' +
						'mindestens --g-ink-3, wie der bestehende Verbindungsstatus-Text.'
				);
				assert.ok(
					token !== null && ERLAUBT.includes(token),
					`AC-9 (${komponente}, ${name}): Am Meldedatum-Label wirkt keine explizite, ` +
						`kontrastgesicherte Textfarbe (aufgeloest: ${token ?? 'keine'}; erlaubt: ` +
						`${ERLAUBT.join(', ')}). Element: ${outer.slice(0, 160)}`
				);
			}
		}
	});
});

// ─── #1717 Kanalzaehler (Tech-Lead-Entscheid 2026-08-11) ─────────────────────
// Befund aus dem GREEN-Bericht zu S3: der Zaehler "wie viele Briefing-Kanaele
// sind aktiv?" kannte nur drei Kanaele (VersandTab.svelte activeChannelCount,
// EditReportConfigSection.svelte hasActiveChannel). Wer NUR Premium-SMS
// einschaltet, sah dadurch den Leerzustand "Kein Kanal aktiv" und keine
// Zeitplan-Optionen — waehrend das Briefing tatsaechlich rausgeht. Genau der
// Fehler, den diese Scheibe verhindern soll, nur an einer anderen Stelle.
//
// GEMESSEN WIRD AM WIRKORT, in beiden Seiten — und das sind hier NICHT die
// beiden Kanalblock-Kopien: den Zaehler haelt auf /trips/[id] die Ebene
// darueber (VersandTab, gibt `hasActiveChannel` an VTSchedulePlan), auf
// /trips/new EditReportConfigSection selbst. Der Leerzustand selbst lebt in
// VTSchedulePlan.svelte (`{#if !hasActiveChannel}`), Testid
// `briefings-channel-empty`.
//
// Jeder Fall traegt seine Gegenprobe: mit ALLEN Kanaelen aus MUSS der
// Leerzustand erscheinen. Ohne diese zweite Messung wuerde der Test auch dann
// gruen bleiben, wenn das Testid im gewaehlten Render-Aufbau nie entsteht (dann
// bewacht er nichts).

const EMPTY_TESTID = 'briefings-channel-empty';
const VERSAND_TAB_FILE = path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte');
const VersandTab = (await import(pathToFileURL(VERSAND_TAB_FILE).href)).default;

/** /trips/[id] — Trip-Editor-Versand-Tab (route-Zweig). */
function renderVersandTabRoute(cfg: Record<string, unknown>): string {
	return render(VersandTab, { props: { context: 'route', reportConfig: cfg } }).body;
}

/** /trips/new — dieselbe Zeitplan-Sektion, andere Fassung des Zaehlers.
 * `showChannels: false`, damit im HTML nur der EINE Leerzustand aus
 * VTSchedulePlan vorkommen kann (der Kanal-Gating-Leerzustand aus #617 traegt
 * dasselbe Testid, haengt aber an `weatherChannels` — hier nicht gesetzt). */
function renderEditSchedule(cfg: Record<string, unknown>): string {
	return render(EditReportConfigSection, {
		props: {
			reportConfig: cfg,
			mode: 'edit',
			showMailContent: false,
			showSchedule: true,
			showChannels: false,
			profileOverride: P_FRESH
		}
	}).body;
}

describe('#1717 Kanalzaehler: Premium-SMS allein ist ein aktiver Kanal', () => {
	const NUR_PREMIUM = {
		send_email: false,
		send_telegram: false,
		send_sms: false,
		send_premium_sms: true
	};
	const ALLE_AUS = { ...NUR_PREMIUM, send_premium_sms: false };

	test('nur_premium_sms_aktiv_zeigt_keinen_leerzustand_in_beiden_fassungen', () => {
		for (const [ort, renderer] of [
			['VersandTab (/trips/[id])', renderVersandTabRoute],
			['EditReportConfigSection (/trips/new)', renderEditSchedule]
		] as Array<[string, (c: Record<string, unknown>) => string]>) {
			// Gegenprobe: der Leerzustand ist in diesem Aufbau erreichbar.
			assert.ok(
				renderer(ALLE_AUS).includes(`data-testid="${EMPTY_TESTID}"`),
				`${ort}: Mit allen vier Kanaelen AUS muss der Leerzustand ` +
					`"${EMPTY_TESTID}" erscheinen. Fehlt er hier, prueft der Fall unten nichts.`
			);

			assert.ok(
				!renderer(NUR_PREMIUM).includes(`data-testid="${EMPTY_TESTID}"`),
				`${ort}: Nur Premium-SMS ist eingeschaltet — das Briefing geht raus, die ` +
					`Oberflaeche behauptet aber "Kein Kanal aktiv" (${EMPTY_TESTID}) und sperrt die ` +
					'Zeitplan-Optionen weg. Der Kanal-Zaehler muss send_premium_sms mitzaehlen.'
			);
		}
	});

	test('zeitplan_optionen_erscheinen_wenn_nur_premium_sms_aktiv_ist', () => {
		// Positivseite derselben Zusicherung: nicht nur "kein Leerzustand",
		// sondern der Inhalt, den der Leerzustand ersetzt, ist tatsaechlich da.
		for (const [ort, renderer] of [
			['VersandTab (/trips/[id])', renderVersandTabRoute],
			['EditReportConfigSection (/trips/new)', renderEditSchedule]
		] as Array<[string, (c: Record<string, unknown>) => string]>) {
			const html = renderer(NUR_PREMIUM);
			assert.ok(
				html.includes('data-testid="morning-master-switch"'),
				`${ort}: Bei aktivem Premium-SMS muessen die Zeitplan-Karten (Morgen-Briefing) ` +
					'gerendert sein — sonst kann der Nutzer die Sendezeit seines einzigen Kanals ' +
					'nicht einstellen.'
			);
		}
	});
});

// ─── #1717 AC-10 ─────────────────────────────────────────────────────────────

describe('#1717 AC-10: gespeicherter Anhak-Zustand wird gelesen', () => {
	test('premium_sms_checked_spiegelt_report_config_in_beiden_komponenten', () => {
		for (const [komponente, renderer] of BEIDE) {
			const angehakt = checkboxInputTag(renderer(P_FRESH, true), 'channel-premium-sms');
			assert.equal(
				isChecked(angehakt),
				true,
				`AC-10 (${komponente}): send_premium_sms=true ist gespeichert, die Checkbox rendert aber ` +
					`nicht angehakt (Tag: ${angehakt}). Bei EditReportConfigSection heisst das: der ` +
					'Zustand wird nur in onMount hydriert — beim Rendern ist er dann nicht da.'
			);

			const leer = checkboxInputTag(renderer(P_FRESH, false), 'channel-premium-sms');
			assert.equal(
				isChecked(leer),
				false,
				`AC-10 (${komponente}): Ohne send_premium_sms darf die Checkbox NICHT angehakt sein ` +
					`(Tag: ${leer}) — sonst schaltet die Anzeige einen kostenpflichtigen Kanal vor.`
			);
		}
	});
});
