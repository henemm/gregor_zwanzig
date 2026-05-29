<script lang="ts">
	// Issue #443 — Step 5: Versand + Aktivierung.
	// Spec: docs/specs/modules/issue_443_compare_wizard_step5_versand.md
	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { GCard } from '$lib/components/ui/g-card';
	import ChannelToggle from '$lib/components/trip-wizard/steps/ChannelToggle.svelte';
	import { maskPhone } from '$lib/components/trip-wizard/wizardHelpers';
	import type { CompareWizardState } from '../compareWizardState.svelte';

	const state = getContext<CompareWizardState>('compare-wizard-state');

	const profile = getContext<{
		mail_to?: string;
		signal_phone?: string;
		telegram_chat_id?: string;
		email?: string;
	} | null>('compare-wizard-profile');

	// Abgeleitete Werte (Svelte $derived für Overlap-Check)
	const hasTimeOverlap = $derived(state.timeWindowStart >= state.timeWindowEnd);
	const allChannelsOff = $derived(!state.sendEmail && !state.sendSignal && !state.sendTelegram);

	// Factory-Handler (Safari-Pattern)
	function makeChannelHandler(field: 'sendEmail' | 'sendSignal' | 'sendTelegram') {
		return function handleChannel(checked: boolean): void {
			state[field] = checked;
		};
	}
</script>

<div data-testid="compare-wizard-step-5" class="space-y-6 py-4">
	<!-- Kanal-Liste -->
	<section class="space-y-2">
		<Eyebrow>Kanäle</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="space-y-3">
				<ChannelToggle
					label="E-Mail"
					checked={state.sendEmail}
					onchange={makeChannelHandler('sendEmail')}
					testid="compare-step5-channel-email"
					hint={profile?.mail_to || profile?.email || undefined}
				/>
				<ChannelToggle
					label="Signal"
					checked={state.sendSignal}
					onchange={makeChannelHandler('sendSignal')}
					testid="compare-step5-channel-signal"
					hint={maskPhone(profile?.signal_phone) || undefined}
				/>
				<ChannelToggle
					label="Telegram"
					checked={state.sendTelegram}
					onchange={makeChannelHandler('sendTelegram')}
					testid="compare-step5-channel-telegram"
					hint={profile?.telegram_chat_id || undefined}
				/>
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
			<select
				data-testid="compare-step5-forecast-hours"
				bind:value={state.forecastHours}
				class="w-full border rounded px-3 py-2 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
			>
				<option value={24}>Heute (24 h)</option>
				<option value={48}>Morgen (48 h)</option>
				<option value={72}>Übermorgen (72 h)</option>
			</select>
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

	<!-- Aktivierungs-Banner (nur Create-Modus) -->
	{#if !state.isEditMode}
		<div
			data-testid="compare-step5-activation-banner"
			class="rounded-md p-4 text-white text-sm"
			style:background="var(--g-good)"
		>
			Nach dem Aktivieren erhältst du ab dem nächsten Versandzeitpunkt automatisch dein
			Briefing.
		</div>
	{/if}
</div>
