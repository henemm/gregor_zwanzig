<script lang="ts">
	// Issue #251 — PresetHeader: Steuerungs-Card für den Compare-Screen.
	//
	// Spec: docs/specs/modules/issue_251_compare_main_stage.md §2
	// Presentational; State (Datum, Zeitfenster, Profil) wird via $bindable() aus der Page geteilt.

	import type { ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Select } from '$lib/components/ui/select';
	import { Field } from '$lib/components/molecules/index.js';

	interface Props {
		compareDate: string;
		twStart: number;
		twEnd: number;
		forecastHours: number;
		activityProfile: ActivityProfile;
		locationCount: number;
		loading: boolean;
		onrun: () => void;
		onsavebriefing: () => void;
		onprofilechange?: () => void;
	}

	let {
		compareDate = $bindable(),
		twStart = $bindable(),
		twEnd = $bindable(),
		forecastHours = $bindable(),
		activityProfile = $bindable(),
		locationCount,
		loading,
		onrun,
		onsavebriefing,
		onprofilechange,
	}: Props = $props();
</script>

<Card.Root data-testid="compare-preset-header">
	<Card.Header>
		<Card.Title>Einstellungen</Card.Title>
	</Card.Header>
	<Card.Content class="space-y-4">
		<div class="flex flex-wrap items-end justify-between gap-4">
			<!-- Linke Seite: Eingaben -->
			<div class="grid flex-1 grid-cols-2 gap-3 md:grid-cols-5">
				<Field label="Datum" dense={false}>
					<input
						id="cmp-date"
						aria-label="Datum"
						data-testid="compare-preset-date-input"
						type="date"
						bind:value={compareDate}
						class="block w-full rounded-md border px-3 py-2 text-sm font-mono"
					/>
				</Field>
				<Field label="Von" dense={false}>
					<Select
						id="cmp-start"
						aria-label="Von"
						bind:value={twStart}
						class="block w-full"
					>
						{#each Array.from({ length: 24 }, (_, i) => i) as h}
							<option value={h}>{String(h).padStart(2, '0')}:00</option>
						{/each}
					</Select>
				</Field>
				<Field label="Bis" dense={false}>
					<Select
						id="cmp-end"
						aria-label="Bis"
						bind:value={twEnd}
						class="block w-full"
					>
						{#each Array.from({ length: 24 }, (_, i) => i) as h}
							<option value={h}>{String(h).padStart(2, '0')}:00</option>
						{/each}
					</Select>
				</Field>
				<Field label="Horizont" dense={false}>
					<Select
						id="cmp-hours"
						aria-label="Horizont"
						bind:value={forecastHours}
						class="block w-full"
					>
						<option value={24}>24h</option>
						<option value={48}>48h</option>
						<option value={72}>72h</option>
					</Select>
				</Field>
				<Field label="Profil" dense={false}>
					<Select
						id="cmp-profile"
						aria-label="Profil"
						data-testid="compare-preset-profile-select"
						bind:value={activityProfile}
						class="block w-full"
						onchange={() => onprofilechange?.()}
					>
						{#each ACTIVITY_PROFILE_OPTIONS as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</Select>
				</Field>
			</div>

			<!-- Rechte Seite: Buttons -->
			<div class="flex flex-wrap items-center gap-2">
				<Btn variant="ghost" disabled={true}>Preset laden</Btn>
				<Btn
					variant="outline"
					data-testid="compare-preset-save-btn"
					onclick={onsavebriefing}
				>
					Als Auto-Briefing speichern
				</Btn>
				<Btn
					variant="accent"
					data-testid="compare-preset-run-btn"
					onclick={onrun}
					disabled={loading}
				>
					{loading ? 'Lädt…' : 'Vergleich starten'}
				</Btn>
			</div>
		</div>

		<p data-testid="compare-preset-summary" class="text-sm text-muted-foreground">
			{locationCount} Locations · {String(twStart).padStart(2, '0')}:00–{String(twEnd).padStart(2, '0')}:00 Uhr · {forecastHours}h
		</p>
	</Card.Content>
</Card.Root>
