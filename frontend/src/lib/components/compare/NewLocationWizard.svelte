<script lang="ts">
	// Issue #249 — Compare-Screen 3-Schritt-Wizard fuer neue Locations.
	//
	// Spec: docs/specs/modules/issue_249_locations_rail.md
	//
	// Schritte: Verortung (Lat/Lon/Hoehe) -> Benennung (Name, Gruppe) ->
	// Aktivitaetsprofil. Speichern persistiert via POST /api/locations und liefert
	// die neue Location via onsave() an die Page zurueck.

	import type { Location, ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import Stepper from '$lib/components/trip-wizard/Stepper.svelte';
	import { toKebabCase } from './locationHelpers.js';

	interface Props {
		locations: Location[];
		onsave: (loc: Location) => void;
		oncancel: () => void;
	}

	let { locations, onsave, oncancel }: Props = $props();

	let step = $state<1 | 2 | 3>(1);
	let lat = $state('47.0');
	let lon = $state('11.0');
	let elevationM = $state('');
	let name = $state('');
	let group = $state('');
	let activityProfile = $state<ActivityProfile>('allgemein');
	let saving = $state(false);
	let error = $state<string | null>(null);

	function prevStep() {
		if (step > 1) step = (step - 1) as 1 | 2 | 3;
		error = null;
	}

	function nextStep() {
		if (step === 1 && Number(lat) === 0 && Number(lon) === 0) {
			error = 'Bitte gültige Koordinaten eingeben';
			return;
		}
		if (step === 2 && !name.trim()) {
			error = 'Name ist erforderlich';
			return;
		}
		error = null;
		step = (step + 1) as 1 | 2 | 3;
	}

	async function save() {
		if (saving) return;
		saving = true;
		error = null;
		try {
			const loc: Location = {
				id: toKebabCase(name),
				name: name.trim(),
				lat: Number(lat),
				lon: Number(lon),
				elevation_m: elevationM !== '' ? Number(elevationM) : undefined,
				group: group.trim() || undefined,
				activity_profile: activityProfile,
			};
			await api.post<Location>('/api/locations', loc);
			onsave(loc);
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			error = body?.detail ?? body?.error ?? 'Fehler beim Speichern';
		} finally {
			saving = false;
		}
	}

	let existingGroups = $derived(
		[...new Set(locations.map((l) => l.group).filter((g): g is string => Boolean(g)))],
	);
</script>

<div data-testid="location-wizard" class="space-y-6 py-2">
	<div data-testid="location-wizard-stepper">
		<Stepper
			current={step as 1 | 2 | 3 | 4}
			labels={['Verortung', 'Benennung', 'Aktivitätsprofil']}
		/>
	</div>

	{#if step === 1}
		<div class="space-y-4">
			<div class="grid grid-cols-2 gap-3">
				<div>
					<Label for="wiz-lat">Breitengrad (Lat)</Label>
					<Input
						data-testid="location-wizard-lat"
						id="wiz-lat"
						type="number"
						step="0.000001"
						bind:value={lat}
					/>
				</div>
				<div>
					<Label for="wiz-lon">Längengrad (Lon)</Label>
					<Input
						data-testid="location-wizard-lon"
						id="wiz-lon"
						type="number"
						step="0.000001"
						bind:value={lon}
					/>
				</div>
			</div>
			<div>
				<Label for="wiz-elev">Höhe über NN (m, optional)</Label>
				<Input id="wiz-elev" type="number" bind:value={elevationM} />
			</div>
			<p class="text-xs text-muted-foreground">
				URL-Import (Komoot, Google Maps) folgt in einem Update.
			</p>
		</div>
	{/if}

	{#if step === 2}
		<div class="space-y-4">
			<div>
				<Label for="wiz-name">Name <span class="text-destructive">*</span></Label>
				<Input
					data-testid="location-wizard-name"
					id="wiz-name"
					placeholder="z.B. Hintertuxer Gletscher"
					bind:value={name}
				/>
			</div>
			<div>
				<Label for="wiz-group">Gruppe (optional)</Label>
				<input
					id="wiz-group"
					list="wiz-group-opts"
					bind:value={group}
					placeholder="z.B. Zillertal"
					class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
				/>
				<datalist id="wiz-group-opts">
					{#each existingGroups as g}
						<option value={g}></option>
					{/each}
				</datalist>
			</div>
		</div>
	{/if}

	{#if step === 3}
		<div class="grid grid-cols-2 gap-3">
			{#each ACTIVITY_PROFILE_OPTIONS as opt}
				<button
					type="button"
					onclick={() => (activityProfile = opt.value)}
					class="rounded-lg border p-3 text-left transition-colors
						{activityProfile === opt.value
						? 'border-[var(--g-accent)] bg-[var(--g-accent)]/10 font-medium'
						: 'border-input hover:border-[var(--g-accent)]/50'}"
				>
					<span class="text-sm">{opt.label}</span>
				</button>
			{/each}
		</div>
	{/if}

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	<div class="flex justify-between pt-2">
		<Btn variant="outline" onclick={step === 1 ? oncancel : prevStep}>
			{step === 1 ? 'Abbrechen' : 'Zurück'}
		</Btn>
		{#if step < 3}
			<Btn data-testid="location-wizard-next" variant="primary" onclick={nextStep}>
				Weiter
			</Btn>
		{:else}
			<Btn
				data-testid="location-wizard-save"
				variant="primary"
				onclick={save}
				disabled={saving}
			>
				{saving ? 'Speichern…' : 'Speichern'}
			</Btn>
		{/if}
	</div>
</div>
