// Issue #3020 S1 — vom F6-Pruefstand abgetrennter Teil: SSR-Renders des Alt-Reiters Versand (VersandTab, VT*,
// TelegramKurzstilToggle in dessen Verdrahtung) und seiner Texte, die kein Nutzer mehr sieht. Faellt mit S4.
// Pfadregel #1409: alles relativ zu DIESER Datei.

import path from 'node:path';
import { html, komp, NB, PROFILE, VT, type Kontext } from './f6VersandSsr.ts';

const VersandTab = await komp(path.join(VT, '..', 'VersandTab.svelte'));
const VTBriefingChannels = await komp(path.join(VT, 'VTBriefingChannels.svelte'));
const VTSchedulePlan = await komp(path.join(VT, 'VTSchedulePlan.svelte'));
const VTLaufzeitRoute = await komp(path.join(VT, 'VTLaufzeitRoute.svelte'));
const VTLaufzeitVergleich = await komp(path.join(VT, 'VTLaufzeitVergleich.svelte'));
const VTNextBriefing = await komp(path.join(VT, 'VTNextBriefing.svelte'));
const TelegramKurzstilToggle = await komp(path.join(VT, '..', 'TelegramKurzstilToggle.svelte'));
const { vtBriefingLeadText, vtBriefingSubTexts } = await import('../vtBriefingChannelsText.ts');

const nix = () => {};

/** Kanal-Block mit Profil (wie VersandTab ihn je Kontext verdrahtet). */
export function kanaeleRendern(context: Kontext, profil: Record<string, unknown> | null, ohnePremium = false): string {
	const props: Record<string, unknown> = {
		context,
		channels: { email: true, telegram: true, sms: false, premium_sms: false },
		onEmailChange: nix,
		onTelegramChange: nix,
		onSmsChange: nix,
		telegramStyle: 'rich',
		profileOverride: profil
	};
	if (!ohnePremium) props.onPremiumSmsChange = nix;
	if (context === 'route') props.onTelegramStyleChange = nix;
	return html(VTBriefingChannels, props);
}

/** Der ganze Reiter (SSR: Profil noch nicht geladen). */
export function tabRendern(context: Kontext): string {
	if (context === 'route') {
		return html(VersandTab, { context, trip: { id: 't1', stages: [{ date: '2026-10-28' }, { date: '2026-10-31' }] } });
	}
	return html(VersandTab, { context, sendEmail: true, sendTelegram: false, endDate: null, preset: { id: 'p1' } });
}

/** #2869: nur der Baustein „Nächstes Briefing" (VTNextBriefing) mit einem Backend-Wert. */
export function naechstesBriefingRendern(nextBriefing: Record<string, unknown> | null, context: Kontext): string {
	return html(VTNextBriefing, { nextBriefing, context });
}

/** Restliche Zustaende, die der Reiter nur in Sonderfaellen zeigt. */
export function bausteineRendern(): string {
	const plan = (context: Kontext, aktiv: boolean) =>
		html(VTSchedulePlan, {
			context,
			hasActiveChannel: aktiv,
			morning_enabled: true,
			morning_time: '07:00',
			evening_enabled: false,
			evening_time: '18:00',
			onMorningToggle: nix,
			onEveningToggle: nix,
			onMorningTime: nix,
			onEveningTime: nix
		});
	return [
		plan('route', false),
		plan('vergleich', true),
		kanaeleRendern('route', {}),
		kanaeleRendern('vergleich', { mail_to: 'x@example.org', email_verified: false, sms_to: '+4915', sms_allowed: true, premium_sms_allowed: true, premium_sms_reply_state: 'none' }),
		kanaeleRendern('vergleich', null, true),
		html(TelegramKurzstilToggle, { style: 'kurzform', onchange: nix, disabled: false }),
		html(TelegramKurzstilToggle, { style: 'rich', onchange: nix, disabled: true }),
		html(VTLaufzeitRoute, { tripEnd: null, onOpenStages: nix }),
		html(VTLaufzeitVergleich, { value: '2026-11-15', onChange: nix }),
		...Object.keys(NB).map((k) => html(VTNextBriefing, { nextBriefing: NB[k], context: k === 'beendet' ? 'vergleich' : 'route' }))
	].join('\n');
}

/** Golden-Faelle HTML: drei Profile x zwei Kontexte, plus Sonderzustaende. */
export function altFaelle(): Record<string, () => string> {
	const f: Record<string, () => string> = {};
	for (const name of Object.keys(PROFILE)) {
		for (const context of ['route', 'vergleich'] as const) {
			f[`${name}_${context}`] = () => kanaeleRendern(context, PROFILE[name]) + '\n' + tabRendern(context);
		}
	}
	f.bausteine = bausteineRendern;
	return f;
}

/** Zeilen der Funktionstabelle zu den Texten des Alt-Reiters. */
export function altFunktionsTabelle(): string {
	const j = (v: unknown) => JSON.stringify(v);
	const z: string[] = [];
	for (const context of ['route', 'vergleich'] as const) {
		z.push(`vtBriefingLeadText(${context}) → ${j(vtBriefingLeadText(context))}`);
		for (const stil of ['rich', 'kurzform'] as const) z.push(`vtBriefingSubTexts(${context}, ${stil}) → ${j(vtBriefingSubTexts(context, stil))}`);
	}
	return z.join('\n');
}
