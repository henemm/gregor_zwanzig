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

	import { onMount, untrack } from 'svelte';
	import { Eyebrow, Card, Dot } from '$lib/components/atoms';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
	import { channelConnectionStatus, type ConnectionProfile } from './channelConnectionStatus';
	import { channelContactLabel } from './channelContactLabel';
	import { premiumSmsChannelState } from './premiumSmsChannelState';
	import TelegramKurzstilToggle from '$lib/components/shared/TelegramKurzstilToggle.svelte';

	interface Channels {
		email: boolean;
		telegram: boolean;
		sms: boolean;
		/** Issue #1717 S3 — vierter Briefing-Kanal, nur im route-Kontext schaltbar. */
		premium_sms?: boolean;
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
		/** Issue #1260 S5: Trip-Kurzstil-Schalter (report_config.telegram_style).
		 * Nur im route-Zweig gesetzt — im vergleich-Zweig ist das Briefing
		 * E-Mail-only; der Compare-Kurzstil sitzt bei den amtlichen Warnungs-
		 * Kanaelen im Alarme-Tab (dieselbe geteilte Komponente). */
		telegramStyle?: 'rich' | 'kurzform';
		onTelegramStyleChange?: (style: 'rich' | 'kurzform') => void;
		/** Issue #1717 S3: Premium-SMS (Garmin inReach). Die ANWESENHEIT dieser
		 * Prop schaltet den schaltbaren Premium-SMS-Block frei — exakt das
		 * Gating-Muster von onTelegramStyleChange oben. VersandTab uebergibt sie
		 * nur im route-Zweig; im vergleich-Zweig bleibt der feste
		 * "bald verfuegbar"-Platzhalter stehen, weil Premium-SMS laut ADR-0049
		 * ausschliesslich ein Trip-Briefing-Kanal ist (AC-1). */
		onPremiumSmsChange?: (e: Event) => void;
		/** RED-Infrastruktur (#1510): optionaler SSR-Test-Override fuer `profile`.
		 * Falls gesetzt (auch explizit `null`) wird `profile` daraus initialisiert
		 * und der `onMount`-Fetch uebersprungen — `svelte/server`s `render()` fuehrt
		 * `onMount` nicht aus, ohne diesen Override bliebe `profile` in SSR-Tests
		 * immer `null`. Ohne Uebergabe unveraendertes Verhalten (Fetch in onMount). */
		profileOverride?: Profile | null;
	}
	let {
		context = 'route',
		channels,
		onEmailChange,
		onTelegramChange,
		onSmsChange,
		emailTestid = 'channel-email',
		telegramTestid = 'channel-telegram',
		smsTestid = 'channel-sms',
		telegramStyle = 'rich',
		onTelegramStyleChange,
		onPremiumSmsChange,
		profileOverride
	}: Props = $props();

	/** Issue #1717 S3: EINE kanonische Profilform (channelConnectionStatus.ts)
	 * statt einer lokalen Kopie je Komponente — sonst muesste jedes neue
	 * Profilfeld an drei Stellen nachgezogen werden. */
	type Profile = ConnectionProfile;
	let profile = $state<Profile | null>(
		untrack(() => (profileOverride !== undefined ? profileOverride : null))
	);

	let availableChannels = $derived({
		email: !!profile?.mail_to,
		telegram: !!profile?.telegram_chat_id,
		sms: !!profile?.sms_to && profile?.sms_allowed !== false
	});

	// Issue #1258 S6 (R5): ehrlicher Verbindungsstatus je Kanal (Dot + Label),
	// additiv zu den bestehenden Checkboxen.
	let connectionStatus = $derived(channelConnectionStatus(profile));
	let contactLabel = $derived(channelContactLabel(profile));
	// Issue #1717 S3: geteilter Zustands-Helfer — dieselbe Quelle, die
	// EditReportConfigSection benutzt (keine zweite Kopie der Logik).
	let premiumSms = $derived(premiumSmsChannelState(profile));

	onMount(() => {
		if (profileOverride !== undefined) return;
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
					<Checkbox checked={channels.email} disabled={connectionStatus.email.tone !== 'good'} onchange={onEmailChange}
						>E-Mail{contactLabel.email}</Checkbox
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
						>Telegram{contactLabel.telegram}</Checkbox
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
				{#if onTelegramStyleChange}
					<div class="vt-telegram-style pl-6">
						<TelegramKurzstilToggle
							{context}
							style={telegramStyle}
							disabled={!channels.telegram}
							onchange={onTelegramStyleChange}
						/>
					</div>
				{/if}
			</div>

			<div class="text-sm">
				<span data-testid={smsTestid} class="inline-flex items-center gap-2">
					<Checkbox checked={channels.sms} disabled={!availableChannels.sms} onchange={onSmsChange}
						>SMS{contactLabel.sms}</Checkbox
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
				<!-- Premium-SMS (Garmin inReach) — Issue #1717 S3. Schaltbar NUR wenn
				     onPremiumSmsChange uebergeben wurde (route-Zweig von VersandTab);
				     im vergleich-Zweig bleibt der Platzhalter aus #1069 unveraendert
				     stehen, weil Premium-SMS laut ADR-0049 kein Vergleichs-Kanal ist. -->
				{#if onPremiumSmsChange}
					<div class="text-sm" style="margin-top: 6px;">
						<span data-testid="channel-premium-sms" class="inline-flex items-center gap-2">
							<Checkbox
								checked={channels.premium_sms ?? false}
								disabled={premiumSms.disabled}
								onchange={onPremiumSmsChange}
								>Premium-SMS (Garmin inReach){premiumSms.contactLabel}</Checkbox
							>
						</span>
						<span data-testid="channel-status-premium-sms" class="vt-channel-status">
							<Dot tone={premiumSms.tone} size={7} />
							<span class="vt-channel-status-label">{premiumSms.statusLabel}</span>
						</span>
						<p data-testid="channel-premium-sms-hint" class="vt-channel-sub pl-6">
							{premiumSms.hint}
						</p>
						{#if premiumSms.reportedAtLabel}
							<p data-testid="channel-premium-sms-reported-at" class="vt-premium-reported-at pl-6">
								{premiumSms.reportedAtLabel}
							</p>
						{/if}
					</div>
				{:else}
					<div class="text-sm" style="margin-top: 6px;">
						<span data-testid="channel-premium-sms" class="inline-flex items-center gap-2">
							<Checkbox checked={false} disabled={true}>Premium-SMS (Garmin inReach)</Checkbox>
						</span>
					</div>
					<div class="pl-6 text-xs text-muted-foreground">bald verfügbar</div>
				{/if}
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
	.vt-telegram-style {
		margin-top: 8px;
	}
	/* Issue #1717 S3 (AC-9): das Meldedatum der gelernten Rueckadresse ist ein
	   DATEN-Label, keine Fussnote — deshalb dieselbe Farbe wie
	   .vt-channel-status-label (--g-ink-3) und ausdruecklich NICHT --g-ink-4
	   (2,85:1 auf Weiss, strikt Platzhalter/Disabled vorbehalten). Auf einem
	   Handydisplay entscheidet genau dieser Kontrast, ob man der Anzeige traut. */
	.vt-premium-reported-at {
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		margin: 2px 0 0;
	}
</style>
