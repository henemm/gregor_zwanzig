<script lang="ts">
	import type { Location } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';

	interface Props {
		location?: Location;
		onsave: (loc: Location) => void;
		oncancel: () => void;
	}

	let { location, onsave, oncancel }: Props = $props();

	function toKebab(s: string): string {
		return s
			.trim()
			.toLowerCase()
			.replace(/[^a-z0-9äöüß]+/g, '-')
			.replace(/^-|-$/g, '');
	}

	let name = $state(location?.name ?? '');
	let lat = $state(location?.lat ?? 47.0);
	let lon = $state(location?.lon ?? 11.0);
	let elevationM = $state(location?.elevation_m ?? 2000);
	let region = $state(location?.region ?? '');
	let bergfexSlug = $state(location?.bergfex_slug ?? '');
	let activityProfile = $state(location?.activity_profile ?? '');
	let error = $state('');

	function save() {
		error = '';
		if (!name.trim()) {
			error = 'Name ist erforderlich';
			return;
		}
		if (Number(lat) === 0 && Number(lon) === 0) {
			error = 'Koordinaten dürfen nicht beide 0 sein';
			return;
		}
		const result: Location = {
			id: location?.id ?? toKebab(name),
			name: name.trim(),
			lat: Number(lat),
			lon: Number(lon),
			elevation_m: Number(elevationM) || undefined,
			region: region.trim() || undefined,
			bergfex_slug: bergfexSlug.trim() || undefined,
			activity_profile: (activityProfile as Location['activity_profile']) || undefined,
			...(location?.display_config && { display_config: location.display_config })
		};
		onsave(result);
	}
</script>

<div class="space-y-4">
	<div>
		<Label for="location-name">Name</Label>
		<Input id="location-name" name="location-name" placeholder="Name der Location" bind:value={name} />
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	<div class="grid grid-cols-2 gap-3">
		<div>
			<Label for="location-lat">Breitengrad (Lat)</Label>
			<Input id="location-lat" name="location-lat" type="number" step="0.000001" bind:value={lat} />
		</div>
		<div>
			<Label for="location-lon">Längengrad (Lon)</Label>
			<Input id="location-lon" name="location-lon" type="number" step="0.000001" bind:value={lon} />
		</div>
	</div>

	<div>
		<Label for="location-elevation">Höhe (m)</Label>
		<Input id="location-elevation" name="location-elevation" type="number" bind:value={elevationM} />
	</div>

	<div>
		<Label for="location-region">Region (optional)</Label>
		<Input id="location-region" name="location-region" placeholder="z.B. AT-07-23-02" bind:value={region} />
	</div>

	<div>
		<Label for="location-bergfex">Bergfex Slug (optional)</Label>
		<Input id="location-bergfex" name="location-bergfex" placeholder="z.B. hochfuegen" bind:value={bergfexSlug} />
	</div>

	<div>
		<Label for="activity-profile">Aktivitätsprofil</Label>
		<select
			id="activity-profile"
			name="activity-profile"
			bind:value={activityProfile}
			class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
		>
			<option value="">— Kein Profil —</option>
			<option value="wintersport">Wintersport</option>
			<option value="wandern">Wandern</option>
			<option value="allgemein">Allgemein</option>
		</select>
	</div>

	<div class="flex justify-end gap-2 pt-2">
		<Button variant="outline" onclick={oncancel}>Abbrechen</Button>
		<Button onclick={save}>Speichern</Button>
	</div>
</div>
