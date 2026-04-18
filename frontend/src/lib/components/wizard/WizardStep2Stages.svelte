<script lang="ts">
	import type { Stage } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import TrashIcon from '@lucide/svelte/icons/trash-2';

	interface Props {
		stages: Stage[];
	}
	let { stages = $bindable() }: Props = $props();

	const newId = (): string => crypto.randomUUID().slice(0, 8);
	const today = (): string => new Date().toISOString().slice(0, 10);

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

	let hasValidStage = $derived(
		stages.length > 0 && stages.every(s => s.waypoints.length > 0)
	);
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h3 class="text-lg font-medium">Etappen</h3>
		<Button variant="outline" size="sm" onclick={addStage}>
			<PlusIcon class="size-4 mr-1" />
			Etappe hinzufuegen
		</Button>
	</div>

	{#each stages as stage, si}
		<Card.Root data-testid="stage-card-{si}" class="p-4">
			<div class="space-y-3">
				<div class="flex items-center gap-2">
					<Input
						placeholder="Etappenname"
						bind:value={stage.name}
						class="flex-1"
					/>
					<Input type="date" bind:value={stage.date} class="w-40" />
					{#if stages.length > 1}
						<Button variant="ghost" size="icon-sm" onclick={() => removeStage(si)} title="Etappe entfernen">
							<TrashIcon class="size-4" />
						</Button>
					{/if}
				</div>

				<div class="ml-2 space-y-2">
					<Label class="text-sm text-muted-foreground">Wegpunkte</Label>
					{#each stage.waypoints as wp, wi}
						<div data-testid="waypoint-{wi}" class="flex items-center gap-2 text-sm">
							<Input
								placeholder="Name"
								bind:value={wp.name}
								class="w-32"
							/>
							<Input
								type="number"
								name="lat"
								placeholder="Lat"
								bind:value={wp.lat}
								step="0.0001"
								class="w-24"
							/>
							<Input
								type="number"
								name="lon"
								placeholder="Lon"
								bind:value={wp.lon}
								step="0.0001"
								class="w-24"
							/>
							<Input
								type="number"
								placeholder="Hoehe (m)"
								bind:value={wp.elevation_m}
								step="1"
								class="w-24"
							/>
							<Button variant="ghost" size="icon-sm" onclick={() => removeWaypoint(si, wi)} title="Wegpunkt entfernen">
								<TrashIcon class="size-3.5" />
							</Button>
						</div>
					{/each}
					<Button variant="outline" size="sm" onclick={() => addWaypoint(si)}>
						<PlusIcon class="size-3.5 mr-1" />
						Wegpunkt
					</Button>
				</div>
			</div>
		</Card.Root>
	{/each}

	{#if !hasValidStage}
		<p class="text-sm text-muted-foreground">Alle Etappen müssen mindestens einen Wegpunkt haben.</p>
	{/if}
</div>
