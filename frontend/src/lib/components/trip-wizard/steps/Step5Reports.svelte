<script lang="ts">
	// Step 5: Reports (Issue #432 — 3 Cards, Trend-Toggle, Kanal-Chips pro Card).
	// Quelle: docs/specs/modules/issue_432_step3_step5_polish.md §B
	//
	// Aufbau (3 Cards in einer Reihe):
	//   1. Abend-Briefing  (card-evening)  — Checkbox + Uhrzeit + Trend-Toggle + Kanal-Chips
	//   2. Morgen-Update   (card-morning)  — Checkbox + Uhrzeit + Kanal-Chips
	//   3. Warnungen       (card-alerts)   — Hinweis + Kanal-Chips
	//
	// State: getContext('trip-wizard-state'). Reports mutieren
	// wizard.briefings.reports.{morning|evening}.{enabled|time}. Kanäle teilen
	// alle Briefings: wizard.briefings.channels.{email|signal|telegram|sms}.
	// Kontaktdaten kommen aus getContext('trip-wizard-profile') (null-tolerant).
	// Save-Button kommt aus TripWizardShell (state.save()).
	//
	// Issue #432 (Scope-Erweiterung, schließt #437): Der Mehrtages-Trend-Toggle
	// persistiert via `wizard.trendEnabled` → `report_config.multi_day_trend_evening`.

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { GCard } from '$lib/components/ui/g-card';
	import Checkbox from '$lib/components/ui/checkbox/Checkbox.svelte';
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

	// Kanal-Zeilen in fester Reihenfolge. `contact` ist die anzuzeigende
	// Kontaktangabe (maskiert bei Telefonnummern); leer ⇒ Chip disabled.
	const channelRows: { key: ChannelKey; label: string; contact: string }[] = [
		{ key: 'email',    label: 'E-Mail',   contact: profile?.mail_to || profile?.email || '' },
		{ key: 'signal',   label: 'Signal',   contact: maskPhone(profile?.signal_phone) },
		{ key: 'telegram', label: 'Telegram', contact: profile?.telegram_chat_id || '' },
		{ key: 'sms',      label: 'SMS',      contact: maskPhone(profile?.signal_phone) }
	];

	// Typsichere ChannelKey-Liste — wird in template-Komponenten als `data-channels`-
	// Attribut benutzt, damit jede Report-Card explizit ihr Kanal-Inventory deklariert.
	// Siehe Snippet `channelChipsRow` unten.
	const CHANNEL_KEYS: readonly ChannelKey[] = ['email', 'signal', 'telegram', 'sms'] as const;

	// --- Factory-Handler (Safari/Factory: benannte Handler) -----------------

	function makeEnabledHandler(report: 'morning' | 'evening') {
		return function handleToggleEnabled(e: Event) {
			wizard.briefings.reports[report].enabled = (e.target as HTMLInputElement).checked;
		};
	}

	function makeChannelHandler(key: ChannelKey) {
		return function handleToggleChannel(e: Event) {
			wizard.briefings.channels[key] = (e.target as HTMLInputElement).checked;
		};
	}
</script>

<div class="step5-reports py-4" data-testid="step5-reports">
	<div
		class="reports-grid grid gap-4 sm:grid-cols-3"
		data-testid="reports-grid"
	>
		<!-- Card 1: Abend-Briefing -->
		<GCard
			data-testid="card-evening"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Abend-Briefing</Eyebrow>
			<div class="flex items-center gap-2 text-sm">
				<Checkbox
					checked={wizard.briefings.reports.evening.enabled}
					onchange={makeEnabledHandler('evening')}
				>
					Aktiv
				</Checkbox>
			</div>
			<label class="flex flex-col gap-1 text-sm">
				<span class="text-[var(--g-ink-muted)]">Uhrzeit</span>
				<input
					type="time"
					lang="de"
					data-testid="evening-time"
					bind:value={wizard.briefings.reports.evening.time}
					class="h-9 w-36 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 font-mono outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
				/>
			</label>

			<!-- Mehrtages-Trend-Toggle (Issue #432 Scope-Erw., persistiert in
			     wizard.trendEnabled → report_config.multi_day_trend_evening).
			     bind:checked ist hier korrekt: wizard.trendEnabled ist ein direkt
			     mutierbares $state-Feld auf dem WizardState (siehe wizardState.svelte.ts:69)
			     und wird ohne Mittlerschicht in toTripPayload geschrieben.
			     Test-Garant: issue_432_trend_persistence.test.ts AC-19. -->
			<div
				class="trend-toggle flex items-center gap-2 text-sm"
				data-testid="trend-toggle-row"
			>
				<Checkbox
					bind:checked={wizard.trendEnabled}
					data-testid="evening-trend-toggle"
					aria-label="3–7-Tage-Ausblick enthalten"
				/>
				<span class="text-[var(--g-ink-muted)]">3–7-Tage-Ausblick enthalten</span>
			</div>

			{@render channelChips('evening')}
		</GCard>

		<!-- Card 2: Morgen-Update -->
		<GCard
			data-testid="card-morning"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Morgen-Update</Eyebrow>
			<div class="flex items-center gap-2 text-sm">
				<Checkbox
					checked={wizard.briefings.reports.morning.enabled}
					onchange={makeEnabledHandler('morning')}
				>
					Aktiv
				</Checkbox>
			</div>
			<label class="flex flex-col gap-1 text-sm">
				<span class="text-[var(--g-ink-muted)]">Uhrzeit</span>
				<input
					type="time"
					lang="de"
					data-testid="morning-time"
					bind:value={wizard.briefings.reports.morning.time}
					class="h-9 w-36 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 font-mono outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
				/>
			</label>

			{@render channelChips('morning')}
		</GCard>

		<!-- Card 3: Warnungen -->
		<GCard
			data-testid="card-alerts"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Warnungen</Eyebrow>
			<p class="text-sm text-[var(--g-ink-muted)]">
				Warnungen werden automatisch ausgelöst, sobald eine Alarmregel überschritten wird.
			</p>

			{@render channelChips('alerts')}
		</GCard>
	</div>
</div>

{#snippet channelChips(reportKey: ReportKey)}
	<div
		class="channel-chips flex flex-wrap gap-1 mt-2"
		data-testid={`channel-chips-${reportKey}`}
		data-channels={CHANNEL_KEYS.join(',')}
	>
		{#each channelRows as row (row.key)}
			<label
				class="chip"
				data-testid={`channel-chip-${reportKey}-${row.key}`}
				data-channel={row.key}
			>
				<Checkbox
					checked={wizard.briefings.channels[row.key]}
					onchange={makeChannelHandler(row.key)}
					disabled={!row.contact}
					aria-label={row.label}
				/>
				<span class="chip-label">{row.label}</span>
				{#if row.contact}
					<span
						class="chip-contact"
						data-testid={`channel-contact-${reportKey}-${row.key}`}
					>
						{row.contact}
					</span>
				{/if}
			</label>
		{/each}
	</div>
{/snippet}

<style>
	.channel-chips {
		/* Chip-Reihe pro Card. */
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: var(--g-s-1, 0.25rem);
		padding: var(--g-s-1, 0.25rem) var(--g-s-2, 0.5rem);
		border: 1px solid var(--g-ink-faint);
		border-radius: 9999px;
		font-size: 0.75rem;
		cursor: pointer;
	}

	.chip-contact {
		color: var(--g-ink-muted);
		font-family: var(--g-font-mono, ui-monospace, SFMono-Regular, monospace);
		margin-left: var(--g-s-1, 0.25rem);
	}

	.trend-toggle {
		/* Toggle „3–7-Tage-Ausblick enthalten" */
	}
</style>
