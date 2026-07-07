<script lang="ts">
	// Issue #443 — Step 5: Versand + Aktivierung.
	// Spec: docs/specs/modules/issue_443_compare_wizard_step5_versand.md
	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { GCard } from '$lib/components/ui/g-card';
	import { Select } from '$lib/components/ui/select';
	import ChannelToggle from '$lib/components/trip-wizard/steps/ChannelToggle.svelte';
	import { maskPhone } from '$lib/components/trip-wizard/wizardHelpers';
	import type { CompareWizardState } from '../compareWizardState.svelte';

	const state = getContext<CompareWizardState>('compare-wizard-state');

	let { versandVisited = false }: { versandVisited?: boolean } = $props();

	const profile = getContext<{
		mail_to?: string;
		telegram_chat_id?: string;
		email?: string;
		sms_to?: string;
	} | null>('compare-wizard-profile');

	// Abgeleitete Werte (Svelte $derived für Overlap-Check)
	const hasTimeOverlap = $derived(state.timeWindowStart >= state.timeWindowEnd);
	const allChannelsOff = $derived(!state.sendEmail && !state.sendTelegram && !state.sendSms);

	// Factory-Handler (Safari-Pattern)
	function makeChannelHandler(field: 'sendEmail' | 'sendTelegram' | 'sendSms') {
		return function handleChannel(checked: boolean): void {
			state[field] = checked;
		};
	}
</script>

<div data-testid="compare-wizard-step-5" class="space-y-6 py-4">
	<!-- 3-Kacheln-Grid: Versandzeit / Zeitfenster / Horizont (Issue #681 AC-5) -->
	<div
		style:display="grid"
		style:grid-template-columns="1fr 1fr 1fr"
		style:gap="10px"
		style:margin-bottom="28px"
	>
		<button
			type="button"
			data-testid="compare-step5-schedule-tile"
			class="kachel"
		>
			<span class="mono kachel-label">Versand</span>
			<span class="kachel-value">{state.schedule === 'daily_evening' ? '18:00 Uhr' : '07:00 Uhr'}</span>
			<span class="kachel-sub">täglich</span>
		</button>
		<button
			type="button"
			data-testid="compare-step5-timewindow-tile"
			class="kachel"
		>
			<span class="mono kachel-label">Zeitfenster</span>
			<span class="kachel-value">{state.timeWindowStart}–{state.timeWindowEnd} Uhr</span>
			<span class="kachel-sub">bewertet</span>
		</button>
		<button
			type="button"
			data-testid="compare-step5-horizon-tile"
			class="kachel"
		>
			<span class="mono kachel-label">Horizont</span>
			<span class="kachel-value">+{state.forecastHours}h</span>
			<span class="kachel-sub">
				{state.forecastHours === 24 ? 'heute' : state.forecastHours === 48 ? 'morgen + übermorgen' : 'übermorgen + Folgetag'}
			</span>
		</button>
	</div>

	<!-- Kanal-Liste -->
	<section class="space-y-2">
		<Eyebrow>Kanäle</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="space-y-3">
				<div>
					<ChannelToggle
						label="E-Mail"
						checked={state.sendEmail}
						onchange={makeChannelHandler('sendEmail')}
						testid="compare-step5-channel-email"
						hint={profile?.mail_to || profile?.email || undefined}
					/>
					<span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)">Layout · alle Spalten + Detail</span>
				</div>
				<div>
					<ChannelToggle
						label="Telegram"
						checked={state.sendTelegram}
						onchange={makeChannelHandler('sendTelegram')}
						testid="compare-step5-channel-telegram"
						hint={profile?.telegram_chat_id || undefined}
					/>
					<span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)">Layout · max 8 Spalten</span>
				</div>
				<div>
					<ChannelToggle
						label="SMS"
						checked={state.sendSms}
						onchange={makeChannelHandler('sendSms')}
						testid="compare-step5-channel-sms"
						hint={profile?.sms_to || undefined}
						disabled={!profile?.sms_to}
					/>
					<span class="mono" style:font-size="10.5px" style:color="var(--g-ink-4)">Layout · flach, ≤ 140 Z.</span>
				</div>
				<div>
					<ChannelToggle
						label="Amtliche Warnungen"
						checked={state.officialAlertsEnabled}
						onchange={(checked) => (state.officialAlertsEnabled = checked)}
						testid="compare-step5-official-alerts-toggle"
					/>
				</div>
			</div>
			{#if allChannelsOff}
				<p
					data-testid="compare-step5-channel-error"
					class="text-[var(--g-danger)] text-sm mt-3"
				>
					Mindestens ein Kanal muss aktiv sein.
				</p>
			{/if}
		</GCard>
	</section>

	<!-- Horizont -->
	<section class="space-y-2">
		<Eyebrow>Horizont</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<Select
				data-testid="compare-step5-forecast-hours"
				bind:value={state.forecastHours}
				class="w-full"
			>
				<option value={24}>Heute (24 h)</option>
				<option value={48}>Morgen (48 h)</option>
				<option value={72}>Übermorgen (72 h)</option>
			</Select>
		</GCard>
	</section>

	<!-- Zeitfenster -->
	<section class="space-y-2">
		<Eyebrow>Zeitfenster</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="flex items-center gap-3">
				<input
					type="number"
					min="0"
					max="23"
					data-testid="compare-step5-time-window-start"
					bind:value={state.timeWindowStart}
					class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
				/>
				<span class="text-[var(--g-ink-muted)]">bis</span>
				<input
					type="number"
					min="0"
					max="23"
					data-testid="compare-step5-time-window-end"
					bind:value={state.timeWindowEnd}
					class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
				/>
				<span class="text-[var(--g-ink-muted)] text-sm">Uhr</span>
			</div>
			{#if hasTimeOverlap}
				<p
					data-testid="compare-step5-time-overlap-error"
					class="text-[var(--g-danger)] text-sm mt-2"
				>
					Endzeit muss nach der Startzeit liegen.
				</p>
			{/if}
		</GCard>
	</section>

	<!-- Versandzeit -->
	<section class="space-y-2">
		<Eyebrow>Versandzeit</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="flex gap-2" data-testid="compare-step5-schedule">
				<button
					type="button"
					onclick={() => {
						state.schedule = 'daily_morning';
					}}
					class={`flex-1 py-2 px-3 rounded border text-sm transition-colors ${
						state.schedule === 'daily_morning'
							? 'border-[var(--g-accent)] bg-[var(--g-accent)]/10 text-[var(--g-accent-deep)]'
							: 'border-[var(--g-ink-faint)] hover:border-[var(--g-ink-muted)]'
					}`}
				>
					Morgen-Briefing (07:00)
				</button>
				<button
					type="button"
					onclick={() => {
						state.schedule = 'daily_evening';
					}}
					class={`flex-1 py-2 px-3 rounded border text-sm transition-colors ${
						state.schedule === 'daily_evening'
							? 'border-[var(--g-accent)] bg-[var(--g-accent)]/10 text-[var(--g-accent-deep)]'
							: 'border-[var(--g-ink-faint)] hover:border-[var(--g-ink-muted)]'
					}`}
				>
					Abend-Briefing (18:00)
				</button>
			</div>
		</GCard>
	</section>

	<!-- Aktivierungs-Banner (nur Create-Modus, Issue #681 AC-5) -->
	{#if !state.isEditMode}
		<div
			data-testid="compare-step5-activation-banner"
			data-ready={versandVisited ? 'true' : 'false'}
			class="rounded-md p-4 text-white text-sm"
			style:background={versandVisited ? 'var(--g-good)' : 'var(--g-ink)'}
		>
			<div class="mono" style:font-size="10px" style:letter-spacing="0.12em" style:text-transform="uppercase" style:color="rgba(255,255,255,0.55)" style:margin-bottom="4px">Bereit zum Aktivieren</div>
			<div style:font-size="15px" style:font-weight="600">„{state.name || 'Neuer Vergleich'}" · {state.pickedIds?.length ?? 0} Orte</div>
			<div style:font-size="12.5px" style:color="rgba(255,255,255,0.75)" style:margin-top="4px" style:line-height="1.5">
				{#if versandVisited}Versand konfiguriert — klicke „Briefing aktivieren".{:else}Versand einrichten zum Aktivieren.{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.kachel {
		padding: 12px 14px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		text-align: left;
		cursor: pointer;
		font-family: var(--g-font-sans);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.kachel:hover {
		border-color: var(--g-ink-muted);
	}
	.kachel-label {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.10em;
		text-transform: uppercase;
	}
	.kachel-value {
		font-size: 17px;
		font-weight: 600;
		color: var(--g-ink);
		font-variant-numeric: tabular-nums;
	}
	.kachel-sub {
		font-size: 11px;
		color: var(--g-ink-3);
	}
</style>
