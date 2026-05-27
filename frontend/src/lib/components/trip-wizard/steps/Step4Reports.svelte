<script lang="ts">
	// Step 4: Reports (Issue #300 — Wizard-Redesign; Issue #412 — Kanal-Karte).
	// Quelle: docs/specs/modules/issue_412_422_wizard_step4.md
	//
	// Aufbau:
	//   Oben:  Karte "DEINE KANÄLE" (volle Breite) — pro Kanal eine Zeile mit
	//          Label · Kontaktangabe/Hinweis · <Switch> (an channels[key] gebunden).
	//   Darunter: 2×2-Grid der Report-Cards:
	//     1. Abend-Briefing  (card-evening)  — Checkbox + Uhrzeit
	//     2. Morgen-Update   (card-morning)  — Checkbox + Uhrzeit
	//     3. Warnungen       (card-alerts)   — AUTARK-Badge
	//     4. Mehrtages-Trend (card-trend)    — Hinweis: im Abend-Briefing enthalten
	//
	// State: getContext('trip-wizard-state'). Reports mutieren
	// wizard.briefings.reports.{morning|evening}.{enabled|time}. Kanäle teilen
	// alle Briefings: wizard.briefings.channels.{email|signal|telegram|sms}.
	// Kontaktdaten kommen aus getContext('trip-wizard-profile') (null-tolerant).
	// Save-Button kommt aus TripWizardShell (state.save()).

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { GCard } from '$lib/components/ui/g-card';
	import { Pill } from '$lib/components/ui/pill';
	import { Switch } from '$lib/components/atoms';
	import { maskPhone } from '../wizardHelpers';
	import type { WizardState } from '../wizardState.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	type ChannelKey = keyof WizardState['briefings']['channels'];

	const profile = getContext<{
		mail_to?: string;
		signal_phone?: string;
		telegram_chat_id?: string;
		email?: string;
	} | null>('trip-wizard-profile');

	// Kanal-Zeilen in fester Reihenfolge. `contact` ist die anzuzeigende
	// Kontaktangabe (maskiert bei Telefonnummern); leer ⇒ Switch disabled.
	const channelRows: { key: ChannelKey; label: string; contact: string; extra?: string }[] = [
		{ key: 'email', label: 'E-Mail', contact: profile?.mail_to || profile?.email || '' },
		{ key: 'signal', label: 'Signal', contact: maskPhone(profile?.signal_phone) },
		{ key: 'telegram', label: 'Telegram', contact: profile?.telegram_chat_id || '' },
		{ key: 'sms', label: 'SMS', contact: maskPhone(profile?.signal_phone), extra: 'Fallback' }
	];

	// --- Factory-Handler (Safari/Factory: benannte Handler) -----------------

	function makeEnabledHandler(report: 'morning' | 'evening') {
		return function handleToggleEnabled(e: Event) {
			wizard.briefings.reports[report].enabled = (e.target as HTMLInputElement).checked;
		};
	}

	function makeChannelHandler(key: ChannelKey) {
		return function handleToggleChannel(checked: boolean) {
			wizard.briefings.channels[key] = checked;
		};
	}
</script>

<div class="step4-reports py-4" data-testid="step4-reports">
	<!-- Karte: DEINE KANÄLE (oben, volle Breite) -->
	<GCard
		data-testid="card-channels"
		class="mb-4 rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
	>
		<Eyebrow>DEINE KANÄLE</Eyebrow>
		<ul class="flex flex-col gap-2">
			{#each channelRows as row (row.key)}
				<li
					class="flex items-center justify-between gap-3 text-sm"
					data-testid="channel-row-{row.key}"
				>
					<span class="flex flex-col gap-0.5">
						<span class="flex items-center gap-2">
							<span class="font-medium">{row.label}</span>
							{#if row.extra}
								<span class="text-xs text-[var(--g-ink-muted)]">({row.extra})</span>
							{/if}
						</span>
						{#if row.contact}
							<span class="font-mono text-xs text-[var(--g-ink-muted)]">{row.contact}</span>
						{:else}
							<span class="text-xs text-[var(--g-ink-muted)]">in Einstellungen hinterlegen</span>
						{/if}
					</span>
					<Switch
						size="lg"
						checked={wizard.briefings.channels[row.key]}
						onchange={makeChannelHandler(row.key)}
						disabled={!row.contact}
						aria-label={row.label}
					/>
				</li>
			{/each}
		</ul>
	</GCard>

	<div class="reports-grid grid gap-4 sm:grid-cols-2">
		<!-- Card 1: Abend-Briefing -->
		<GCard
			data-testid="card-evening"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Abend-Briefing</Eyebrow>
			<label class="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={wizard.briefings.reports.evening.enabled}
					onchange={makeEnabledHandler('evening')}
				/>
				Aktiv
			</label>
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
		</GCard>

		<!-- Card 2: Morgen-Update -->
		<GCard
			data-testid="card-morning"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Morgen-Update</Eyebrow>
			<label class="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={wizard.briefings.reports.morning.enabled}
					onchange={makeEnabledHandler('morning')}
				/>
				Aktiv
			</label>
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
		</GCard>

		<!-- Card 3: Warnungen (autark) -->
		<GCard
			data-testid="card-alerts"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Warnungen</Eyebrow>
			<Pill tone="accent">AUTARK</Pill>
			<p class="text-sm text-[var(--g-ink-muted)]">
				Warnungen werden automatisch ausgelöst, sobald eine Alarmregel überschritten wird.
			</p>
		</GCard>

		<!-- Card 4: Mehrtages-Trend (Teil des Abend-Briefings) -->
		<GCard
			data-testid="card-trend"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Mehrtages-Trend</Eyebrow>
			<p class="text-sm text-[var(--g-ink-muted)]">Im Abend-Briefing enthalten.</p>
		</GCard>
	</div>
</div>
