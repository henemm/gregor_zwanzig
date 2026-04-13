<script lang="ts">
	import type { Trip, Stage, Waypoint } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Card from '$lib/components/ui/card/index.js';

	interface Props {
		trip?: Trip;
		onsave: (t: Trip) => void;
		oncancel: () => void;
	}

	let { trip, onsave, oncancel }: Props = $props();

	const newId = () => crypto.randomUUID().slice(0, 8);
	const today = () => new Date().toISOString().slice(0, 10);

	let tripName = $state(trip?.name ?? '');
	let tripId = $state(trip?.id ?? '');
	let stages: Stage[] = $state(
		trip ? JSON.parse(JSON.stringify(trip.stages)) : []
	);
	let error = $state('');

	function addStage() {
		stages.push({
			id: newId(),
			name: `Etappe ${stages.length + 1}`,
			date: today(),
			waypoints: []
		});
	}

	function removeStage(idx: number) {
		stages.splice(idx, 1);
	}

	function addWaypoint(stageIdx: number) {
		stages[stageIdx].waypoints.push({
			id: newId(),
			name: `Punkt ${stages[stageIdx].waypoints.length + 1}`,
			lat: 47.0,
			lon: 11.0,
			elevation_m: 2000
		});
	}

	function removeWaypoint(stageIdx: number, wpIdx: number) {
		stages[stageIdx].waypoints.splice(wpIdx, 1);
	}

	function save() {
		error = '';
		if (!tripName.trim()) {
			error = 'Trip-Name ist erforderlich';
			return;
		}
		const result: Trip = {
			id: tripId || newId(),
			name: tripName.trim(),
			stages,
			...(trip && {
				avalanche_regions: trip.avalanche_regions,
				aggregation: trip.aggregation,
				weather_config: trip.weather_config,
				display_config: trip.display_config,
				report_config: trip.report_config
			})
		};
		onsave(result);
	}
</script>

<div class="space-y-4">
	<div>
		<Label for="trip-name">Trip Name</Label>
		<Input id="trip-name" name="trip-name" placeholder="Name des Trips" bind:value={tripName} />
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	<div class="space-y-3">
		<div class="flex items-center justify-between">
			<h3 class="text-sm font-medium">Etappen</h3>
			<Button variant="outline" size="sm" onclick={addStage}>+ Etappe hinzufügen</Button>
		</div>

		{#each stages as stage, si}
			<Card.Root class="p-3">
				<div class="space-y-2">
					<div class="flex items-center gap-2">
						<Input
							placeholder="Etappenname"
							bind:value={stage.name}
							class="flex-1"
						/>
						<Input type="date" bind:value={stage.date} class="w-40" />
						<Button variant="ghost" size="sm" onclick={() => removeStage(si)}>×</Button>
					</div>

					<div class="ml-4 space-y-1">
						{#each stage.waypoints as wp, wi}
							<div class="flex items-center gap-2 text-sm">
								<Input
									name="waypoint-name"
									placeholder="Name"
									bind:value={wp.name}
									class="w-32"
								/>
								<Input
									type="number"
									placeholder="Lat"
									bind:value={wp.lat}
									step="0.000001"
									class="w-24"
								/>
								<Input
									type="number"
									placeholder="Lon"
									bind:value={wp.lon}
									step="0.000001"
									class="w-24"
								/>
								<Input
									type="number"
									placeholder="Höhe (m)"
									bind:value={wp.elevation_m}
									class="w-24"
								/>
								<Button variant="ghost" size="sm" onclick={() => removeWaypoint(si, wi)}>×</Button>
							</div>
						{/each}
						<Button variant="outline" size="sm" onclick={() => addWaypoint(si)}>+ Wegpunkt</Button>
					</div>
				</div>
			</Card.Root>
		{/each}
	</div>

	<div class="flex justify-end gap-2 pt-2">
		<Button variant="outline" onclick={oncancel}>Abbrechen</Button>
		<Button onclick={save}>Speichern</Button>
	</div>
</div>
