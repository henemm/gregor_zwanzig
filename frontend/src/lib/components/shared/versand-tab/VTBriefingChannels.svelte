<script lang="ts">
	// VT_BriefingChannels — Issue #1232 Scheibe 1: "Geplantes Briefing · Kanäle"
	// im geteilten VersandTab-Organism (context="route").
	//
	// 1:1-Struktur aus claude-code-handoff/current/jsx/versand-tab.jsx
	// (VT_BriefingChannels), aber mit den bestehenden Checkbox-Kontrollen
	// (statt Switch-Atom) — die vorhandenen Playwright-Suiten erwarten
	// `getByRole('checkbox')` auf `channel-email`/`channel-telegram`/
	// `channel-sms` (AC-7: testids unveraendert).
	//
	// Spec: docs/specs/modules/versand_tab_route.md (AC-2, AC-7)

	import { onMount } from 'svelte';
	import { Eyebrow, Card, Dot } from '$lib/components/atoms';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
	import { channelConnectionStatus } from './channelConnectionStatus';

	interface Channels {
		email: boolean;
		telegram: boolean;
		sms: boolean;
	}
	interface Props {
		context?: 'route' | 'vergleich';
		channels: Channels;
		onEmailChange: (e: Event) => void;
		onTelegramChange: (e: Event) => void;
		onSmsChange: (e: Event) => void;
		/** Issue #1232 Scheibe 2b: Testid-Präfix-Parametrisierung — der
		 * vergleich-Zweig muss die bestehenden `compare-step5-channel-*`-Testids
		 * behalten (bestehende Playwright-Specs), Default bleibt `channel-*`
		 * (route-Zweig, Scheibe 1, unverändert). */
		emailTestid?: string;
		telegramTestid?: string;
		smsTestid?: string;
	}
	let {
		context = 'route',
		channels,
		onEmailChange,
		onTelegramChange,
		onSmsChange,
		emailTestid = 'channel-email',
		telegramTestid = 'channel-telegram',
		smsTestid = 'channel-sms'
	}: Props = $props();

	interface Profile {
		mail_to?: string;
		telegram_chat_id?: string;
		sms_to?: string;
		sms_allowed?: boolean;
		email_verified?: boolean;
	}
	let profile = $state<Profile | null>(null);

	let availableChannels = $derived({
		email: !!profile?.mail_to,
		telegram: !!profile?.telegram_chat_id,
		sms: !!profile?.sms_to && profile?.sms_allowed !== false
	});

	// Issue #1258 S6 (R5): ehrlicher Verbindungsstatus je Kanal (Dot + Label),
	// additiv zu den bestehenden Checkboxen.
	let connectionStatus = $derived(channelConnectionStatus(profile));

	onMount(() => {
		fetch('/api/auth/profile', { credentials: 'same-origin' })
			.then((r) => (r.ok ? r.json() : null))
			.then((p) => {
				profile = p as Profile | null;
			})
			.catch(() => {
				profile = null;
			});
	});

	// Issue #1232 Scheibe 3a: einzige Kappungs-Quelle CHANNEL_COL_BUDGET (metricsEditor.ts).
	const CTX_LEAD: Record<string, string> = {
		route: `Das Trip-Briefing ist eine Etappen-Tabelle — E-Mail trägt alle Spalten, Telegram die ersten ${CHANNEL_COL_BUDGET.telegram}, SMS läuft flach.`,
		vergleich: `Der Orts-Vergleich ist eine breite Tabelle — realistisch läuft er per E-Mail. Telegram trägt nur ≤ ${CHANNEL_COL_BUDGET.telegram} Spalten, SMS wird flach.`
	};
	// Issue #1232 Scheibe 3a: einzige Kappungs-Quelle CHANNEL_COL_BUDGET (metricsEditor.ts).
	const SUB = {
		email: 'Layout · volle Tabelle',
		telegram: `Layout · ${CHANNEL_COL_BUDGET.telegram} Spalten`,
		sms: 'Layout · flach, ≤ 140 Z.'
	} as const;
</script>

<div>
	<Eyebrow style="margin-bottom: 10px;">Geplantes Briefing · Kanäle</Eyebrow>
	<p class="vt-lead">{CTX_LEAD[context] ?? CTX_LEAD.route}</p>
	<Card padding={0}>
		<div class="vt-channels-body">
			<div class="text-sm">
				<span data-testid={emailTestid} class="inline-flex items-center gap-2">
					<Checkbox checked={channels.email} disabled={!availableChannels.email} onchange={onEmailChange}
						>E-Mail{profile?.mail_to ? ` (${profile.mail_to})` : ''}</Checkbox
					>
				</span>
				<span data-testid="channel-status-email" class="vt-channel-status">
					<Dot tone={connectionStatus.email.tone} size={7} />
					<span class="vt-channel-status-label">{connectionStatus.email.label}</span>
				</span>
				<p class="vt-channel-sub pl-6">{SUB.email}</p>
				{#if !availableChannels.email}
					<div data-testid="channel-email-hint" class="pl-6 text-xs text-muted-foreground">
						E-Mail-Adresse fehlt — <a href="/account">im Account einrichten</a>
					</div>
				{/if}
			</div>

			<div class="text-sm">
				<span data-testid={telegramTestid} class="inline-flex items-center gap-2">
					<Checkbox
						checked={channels.telegram}
						disabled={!availableChannels.telegram}
						onchange={onTelegramChange}
						>Telegram{profile?.telegram_chat_id ? ` (${profile.telegram_chat_id})` : ''}</Checkbox
					>
				</span>
				<span data-testid="channel-status-telegram" class="vt-channel-status">
					<Dot tone={connectionStatus.telegram.tone} size={7} />
					<span class="vt-channel-status-label">{connectionStatus.telegram.label}</span>
				</span>
				<p class="vt-channel-sub pl-6">{SUB.telegram}</p>
				{#if !availableChannels.telegram}
					<div data-testid="channel-telegram-hint" class="pl-6 text-xs text-muted-foreground">
						Telegram-Chat-ID fehlt — <a href="/account">im Account einrichten</a>
					</div>
				{/if}
			</div>

			<div class="text-sm">
				<span data-testid={smsTestid} class="inline-flex items-center gap-2">
					<Checkbox checked={channels.sms} disabled={!availableChannels.sms} onchange={onSmsChange}
						>SMS{profile?.sms_to ? ` (${profile.sms_to})` : ''}</Checkbox
					>
				</span>
				<span data-testid="channel-status-sms" class="vt-channel-status">
					<Dot tone={connectionStatus.sms.tone} size={7} />
					<span class="vt-channel-status-label">{connectionStatus.sms.label}</span>
				</span>
				<p class="vt-channel-sub pl-6">{SUB.sms}</p>
				{#if profile?.sms_allowed === false}
					<div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
						SMS ab Level Standard verfügbar
					</div>
				{:else if !availableChannels.sms}
					<div data-testid="channel-sms-hint" class="pl-6 text-xs text-muted-foreground">
						Handynummer fehlt — <a href="/account">im Account einrichten</a>
					</div>
				{/if}
				<div class="text-sm" style="margin-top: 6px;">
					<span data-testid="channel-premium-sms" class="inline-flex items-center gap-2">
						<Checkbox checked={false} disabled={true}>Premium-SMS (Garmin inReach)</Checkbox>
					</span>
				</div>
				<div class="pl-6 text-xs text-muted-foreground">bald verfügbar</div>
			</div>
		</div>
	</Card>
</div>

<style>
	.vt-lead {
		font-size: 12.5px;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0 0 12px;
		max-width: 620px;
	}
	.vt-channels-body {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 14px 18px;
	}
	.vt-channel-sub {
		font-size: 11px;
		color: var(--g-ink-3);
		margin: 2px 0 0;
	}
	/* Issue #1258 S6 (R5): Verbindungsstatus-Dot + Mono-Label additiv, siehe
	   claude-code-handoff/current/jsx/screen-compare-detail.jsx:289-309.
	   --g-ink-3 statt --g-ink-4 in beiden Zustaenden (Kontrast-Leitprinzip). */
	.vt-channel-status {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin-left: 10px;
	}
	.vt-channel-status-label {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.04em;
		color: var(--g-ink-3);
	}
</style>
