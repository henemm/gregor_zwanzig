<script lang="ts">
	import type { Stage } from '$lib/types.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import TrashIcon from '@lucide/svelte/icons/trash-2';
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import ArrowDownIcon from '@lucide/svelte/icons/arrow-down';

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

	function moveStageUp(idx: number) {
		if (idx <= 0) return;
		[stages[idx - 1], stages[idx]] = [stages[idx], stages[idx - 1]];
	}

	function moveStageDown(idx: number) {
		if (idx >= stages.length - 1) return;
		[stages[idx], stages[idx + 1]] = [stages[idx + 1], stages[idx]];
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
		<Btn variant="outline" size="sm" onclick={addStage}>
			<PlusIcon class="size-4 mr-1" />
			Etappe hinzufuegen
		</Btn>
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
					<Input type="date" bind:value={stage.date} class="w-40 g-num-input" />
					<Btn
						data-testid="stage-move-up-{si}"
						variant="ghost"
						size="icon-sm"
						disabled={si === 0}
						onclick={() => moveStageUp(si)}
						title="Nach oben verschieben"
					>
						<ArrowUpIcon class="size-4" />
					</Btn>
					<Btn
						data-testid="stage-move-down-{si}"
						variant="ghost"
						size="icon-sm"
						disabled={si === stages.length - 1}
						onclick={() => moveStageDown(si)}
						title="Nach unten verschieben"
					>
						<ArrowDownIcon class="size-4" />
					</Btn>
					{#if stages.length > 1}
						<Btn variant="ghost" size="icon-sm" onclick={() => removeStage(si)} title="Etappe entfernen">
							<TrashIcon class="size-4" />
						</Btn>
					{/if}
				</div>

				<div class="ml-2 space-y-2">
					<Label class="text-sm text-muted-foreground">Wegpunkte</Label>
					<div class="hidden sm:grid grid-cols-[1fr_88px_88px_88px_32px] gap-1 px-1 mb-1">
						<span class="g-th">Name</span>
						<span class="g-th text-right">Lat</span>
						<span class="g-th text-right">Lon</span>
						<span class="g-th text-right">Höhe</span>
						<span></span>
					</div>
					{#each stage.waypoints as wp, wi}
						<div data-testid="waypoint-{wi}" class="flex flex-col gap-2 text-sm sm:grid sm:grid-cols-[1fr_88px_88px_88px_32px] sm:gap-1 sm:items-center sm:px-1">
							<!-- Mobile: Name + mobiler Trash in einer Zeile; Desktop: contents -> Name landet in Grid-Spalte 1 -->
							<div class="flex items-center justify-between gap-2 sm:contents">
								<Input
									data-testid="wp-name"
									placeholder="Name"
									bind:value={wp.name}
									class="flex-1 sm:w-full"
								/>
								<Btn
									data-testid="wp-trash-mobile"
									variant="ghost"
									size="icon"
									class="h-11 w-11 shrink-0 sm:hidden"
									onclick={() => removeWaypoint(si, wi)}
									title="Wegpunkt entfernen"
								>
									<TrashIcon class="size-4" />
								</Btn>
							</div>
							<Input
								data-testid="wp-lat"
								type="number"
								inputmode="decimal"
								name="lat"
								placeholder="Lat"
								bind:value={wp.lat}
								step="0.0001"
								class="g-num-input text-right w-full [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
							/>
							<Input
								data-testid="wp-lon"
								type="number"
								inputmode="decimal"
								name="lon"
								placeholder="Lon"
								bind:value={wp.lon}
								step="0.0001"
								class="g-num-input text-right w-full [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
							/>
							<label class="g-num-with-unit">
								<Input
									data-testid="wp-ele"
									type="number"
									inputmode="decimal"
									placeholder="Hoehe (m)"
									bind:value={wp.elevation_m}
									step="1"
									class="g-num-input text-right w-full pr-6 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
								/>
								<span class="g-num-unit" aria-hidden="true">m</span>
							</label>
							<Btn
								variant="ghost"
								size="icon-sm"
								class="hidden sm:inline-flex"
								onclick={() => removeWaypoint(si, wi)}
								title="Wegpunkt entfernen"
							>
								<TrashIcon class="size-3.5" />
							</Btn>
						</div>
					{/each}
					<Btn variant="outline" size="sm" onclick={() => addWaypoint(si)}>
						<PlusIcon class="size-3.5 mr-1" />
						Wegpunkt
					</Btn>
				</div>
			</div>
		</Card.Root>
	{/each}

	{#if !hasValidStage}
		<p class="text-sm text-muted-foreground">Alle Etappen müssen mindestens einen Wegpunkt haben.</p>
	{/if}
</div>

<style>
	.g-num-with-unit {
		position: relative;
		display: block;
	}
	.g-num-unit {
		position: absolute;
		right: 8px;
		top: 50%;
		transform: translateY(-50%);
		font-family: var(--g-font-data);
		font-size: 11px;
		color: var(--g-ink-faint);
		pointer-events: none;
	}
</style>
