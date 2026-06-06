<script lang="ts">
	// Step 5: Reports (Issue #432 — 3 Cards, Trend-Toggle, Kanal-Chips pro Card).
	// Issue #584: Design-Fidelity 1:1 nach screen-trip-wizard.jsx
	//   - Card-Titel: "Vor dem Schlafen" / "Vor Etappenstart" / "Sofort, wenn nötig"
	//   - Uhrzeit: große Mono-Zahl (22px) + "24h"-Label + "Ändern"-Button
	//   - Trend-Toggle: g-card-alt Block + g-rule-soft Border
	//   - Kanal-Chips: <span>-Elemente (nicht Checkbox-Label), accent-tint/rule-border

	import { getContext } from 'svelte';
	import { Eyebrow, Btn, Card } from '$lib/components/atoms';
	import Switch from '$lib/components/atoms/Switch.svelte';
	import { maskPhone } from '../wizardHelpers';
	import type { WizardState } from '../wizardState.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	type ChannelKey = keyof WizardState['briefings']['channels'];
	type ReportKey = 'evening' | 'morning' | 'alerts';

	const profile = getContext<{
		mail_to?: string;
		signal_phone?: string;
		telegram_chat_id?: string;
		email?: string;
	} | null>('trip-wizard-profile');

	// Kanal-Chip-Reihenfolge — Email, Telegram, SMS (#610: Signal entfernt)
	const CHANNEL_CHIPS: { id: ChannelKey; label: string }[] = [
		{ id: 'email',    label: '✉ Email' },
		{ id: 'telegram', label: '→ Telegram' },
		{ id: 'sms',      label: '* SMS' },
	];

	// Typsichere ChannelKey-Liste — Backward-Compat für data-channels-Attribut
	const CHANNEL_KEYS: readonly ChannelKey[] = ['email', 'telegram', 'sms'] as const;

	// Factory-Handler — Switch calls onchange with boolean (not Event)
	function makeEnabledHandler(report: 'morning' | 'evening') {
		return function handleToggleEnabled(checked: boolean) {
			wizard.briefings.reports[report].enabled = checked;
		};
	}

	function makeChannelToggle(key: ChannelKey) {
		return function handleToggleChannel() {
			wizard.briefings.channels[key] = !wizard.briefings.channels[key];
		};
	}
</script>

<div class="step5-reports py-4" data-testid="step5-reports">
	<!-- AC-9 #584: 3-Spalten-Grid, je Card minHeight 280, flex column -->
	<div
		class="reports-grid"
		data-testid="reports-grid"
		style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;"
	>
		<!-- Card 1: Abend-Briefing — AC-9: "Vor dem Schlafen" -->
		<Card
			padding={18}
			data-testid="card-evening"
			style="min-height: 280px; display: flex; flex-direction: column;"
		>
			<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px;">
				<div>
					<Eyebrow>Abend-Briefing</Eyebrow>
					<div style="font-size: 16px; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em;">Vor dem Schlafen</div>
				</div>
				<Switch
					checked={wizard.briefings.reports.evening.enabled}
					onchange={makeEnabledHandler('evening')}
					tone="accent"
				/>
			</div>

			<!-- Sub-Text — AC-9 -->
			<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin-bottom: 14px;">
				Plan &amp; Vorhersage für morgen.
			</div>

			<!-- Uhrzeit als große Mono-Zahl — AC-10 -->
			<div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px;">
				<div style="flex: 1;">
					<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.06em; text-transform: uppercase;">Uhrzeit</div>
					<div class="mono" style="font-size: 22px; font-weight: 600; color: var(--g-ink); margin-top: 4px; letter-spacing: 0.02em;">
						{wizard.briefings.reports.evening.time || '18:00'}<span style="font-size: 11px; color: var(--g-ink-4); margin-left: 6px; font-weight: 400;">24h</span>
					</div>
				</div>
				<Btn variant="ghost" size="sm">Ändern</Btn>
			</div>

			<!-- Trend-Toggle in eigenem g-card-alt Block — AC-11 -->
			<div
				data-testid="trend-toggle-row"
				style="padding: 10px 12px; margin-bottom: 12px;
				       background: var(--g-card-alt); border: 1px solid var(--g-rule-soft);
				       border-radius: var(--g-r-2);
				       display: flex; align-items: center; gap: 10px;"
			>
				<Switch
					checked={wizard.trendEnabled}
					onchange={(v) => { wizard.trendEnabled = v; }}
					tone="accent"
					size="sm"
					aria-label="3–7-Tage-Ausblick enthalten"
				/>
				<div style="flex: 1; min-width: 0;">
					<div style="font-size: 12.5px; font-weight: 500; color: var(--g-ink);">
						3–7-Tage-Ausblick enthalten
					</div>
					<div style="font-size: 11px; color: var(--g-ink-3); margin-top: 1px;">
						Mehrtages-Trend wird mitgeschickt
					</div>
				</div>
			</div>

			<!-- Kanal-Chips — AC-12 -->
			<div style="margin-top: auto;">
				{@render channelChipRow('evening')}
			</div>
		</Card>

		<!-- Card 2: Morgen-Update — AC-9: "Vor Etappenstart" -->
		<Card
			padding={18}
			data-testid="card-morning"
			style="min-height: 280px; display: flex; flex-direction: column;"
		>
			<div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px;">
				<div>
					<Eyebrow>Morgen-Update</Eyebrow>
					<div style="font-size: 16px; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em;">Vor Etappenstart</div>
				</div>
				<Switch
					checked={wizard.briefings.reports.morning.enabled}
					onchange={makeEnabledHandler('morning')}
					tone="accent"
				/>
			</div>

			<!-- Sub-Text — AC-9 -->
			<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin-bottom: 14px;">
				Aktuelle Bedingungen für heute.
			</div>

			<!-- Uhrzeit als große Mono-Zahl — AC-10 -->
			<div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px;">
				<div style="flex: 1;">
					<div class="mono" style="font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.06em; text-transform: uppercase;">Uhrzeit</div>
					<div class="mono" style="font-size: 22px; font-weight: 600; color: var(--g-ink); margin-top: 4px; letter-spacing: 0.02em;">
						{wizard.briefings.reports.morning.time || '06:00'}<span style="font-size: 11px; color: var(--g-ink-4); margin-left: 6px; font-weight: 400;">24h</span>
					</div>
				</div>
				<Btn variant="ghost" size="sm">Ändern</Btn>
			</div>

			<!-- Kanal-Chips — AC-12 -->
			<div style="margin-top: auto;">
				{@render channelChipRow('morning')}
			</div>
		</Card>

		<!-- Card 3: Warnungen — AC-9: "Sofort, wenn nötig" -->
		<Card
			padding={18}
			data-testid="card-alerts"
			style="min-height: 280px; display: flex; flex-direction: column;"
		>
			<div style="margin-bottom: 8px;">
				<Eyebrow>Warnungen</Eyebrow>
				<div style="font-size: 16px; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em;">Sofort, wenn nötig</div>
			</div>

			<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin-bottom: 14px;">
				Alert, sobald eine Alarmregel überschritten wird.
			</div>

			<!-- Kanal-Chips — AC-12 -->
			<div style="margin-top: auto;">
				{@render channelChipRow('alerts')}
			</div>
		</Card>
	</div>
</div>

{#snippet channelChipRow(reportKey: ReportKey)}
	<!-- AC-12 #584: <span>-Chips (kein Checkbox-Label), accent-tint aktiv / rule inaktiv -->
	<div
		class="channel-chips"
		data-testid={`channel-chips-${reportKey}`}
		data-channels={CHANNEL_KEYS.join(',')}
		style="display: flex; gap: 6px; flex-wrap: wrap;"
	>
		{#each CHANNEL_CHIPS as chip (chip.id)}
			{@const on = wizard.briefings.channels[chip.id]}
			<span
				class="mono"
				role="button"
				tabindex="0"
				data-testid={`channel-chip-${reportKey}-${chip.id}`}
				data-channel={chip.id}
				onclick={makeChannelToggle(chip.id)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') makeChannelToggle(chip.id)(); }}
				style="padding: 4px 10px; border-radius: 999px;
				       font-size: 10px; font-weight: 600; letter-spacing: 0.04em; cursor: pointer;
				       border: {on ? '1px solid var(--g-accent)' : '1px solid var(--g-rule)'};
				       background: {on ? 'var(--g-accent-tint)' : 'transparent'};
				       color: {on ? 'var(--g-accent-deep)' : 'var(--g-ink-4)'};"
			>{chip.label}</span>
		{/each}
	</div>
{/snippet}
