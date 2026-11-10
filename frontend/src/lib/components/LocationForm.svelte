<script lang="ts">
	import type { Location, Group, ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import { Btn, Input } from '$lib/components/atoms';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Select } from '$lib/components/ui/select';
	import { t, tr } from '$lib/i18n';

	interface Props {
		location?: Location;
		locations?: Location[];
		groups?: Group[];
		onsave: (loc: Location) => void;
		oncancel: () => void;
	}

	let { location, locations = [], groups = [], onsave, oncancel }: Props = $props();

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
	let dmsInput = $state('');

	function parseDMS(input: string): { lat: number; lon: number } | null {
		const pattern = /(\d+)°(\d+)'([\d.]+)"([NS])[,\s]+(\d+)°(\d+)'([\d.]+)"([EW])/;
		const m = input.match(pattern);
		if (!m) return null;
		let parsedLat = +m[1] + +m[2] / 60 + +m[3] / 3600;
		if (m[4] === 'S') parsedLat = -parsedLat;
		let parsedLon = +m[5] + +m[6] / 60 + +m[7] / 3600;
		if (m[8] === 'W') parsedLon = -parsedLon;
		return { lat: Math.round(parsedLat * 10000) / 10000, lon: Math.round(parsedLon * 10000) / 10000 };
	}

	function handleDmsInput() {
		const result = parseDMS(dmsInput);
		if (result) {
			lat = result.lat;
			lon = result.lon;
		}
	}
	let elevationM = $state(location?.elevation_m ?? 2000);
	let region = $state(location?.region ?? '');
	let bergfexSlug = $state(location?.bergfex_slug ?? '');
	let activityProfile = $state<ActivityProfile | ''>(location?.activity_profile ?? '');
	let groupId = $state(location?.group_id ?? '');
	let error = $state('');

	function save() {
		error = '';
		if (!name.trim()) {
			error = tr('listen.orte.form.name_fehlt');
			return;
		}
		if (Number(lat) === 0 && Number(lon) === 0) {
			error = tr('listen.orte.form.koordinaten_null');
			return;
		}
		// Read-Modify-Write: bestehende, nicht im Formular editierte Felder
		// (display_config, timezone, data_source, created_at) bleiben erhalten;
		// nur die vom Formular verwalteten Felder werden ueberschrieben.
		const result: Location = {
			...location,
			id: location?.id ?? toKebab(name),
			name: name.trim(),
			lat: Number(lat),
			lon: Number(lon),
			elevation_m: String(elevationM) !== '' ? Number(elevationM) : undefined,
			region: region.trim() || undefined,
			bergfex_slug: bergfexSlug.trim() || undefined,
			activity_profile: activityProfile || undefined,
			group_id: groupId || undefined,
		};
		onsave(result);
	}
</script>

<div class="space-y-4">
	<div>
		<Label for="location-name">{$t('listen.spalte.name')}</Label>
		<Input id="location-name" name="location-name" placeholder={$t('listen.orte.form.name_platzhalter')} bind:value={name} />
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	<div>
		<Label for="location-dms">{$t('listen.orte.form.dms')}</Label>
		<Input
			id="location-dms"
			name="location-dms"
			placeholder={$t('listen.orte.form.dms_platzhalter')}
			bind:value={dmsInput}
			oninput={handleDmsInput}
		/>
	</div>

	<div class="grid grid-cols-2 gap-3">
		<div>
			<Label for="location-lat">{$t('listen.orte.form.lat')}</Label>
			<Input id="location-lat" name="location-lat" type="number" step="0.000001" bind:value={lat} />
		</div>
		<div>
			<Label for="location-lon">{$t('listen.orte.form.lon')}</Label>
			<Input id="location-lon" name="location-lon" type="number" step="0.000001" bind:value={lon} />
		</div>
	</div>

	<div>
		<Label for="location-elevation">{$t('listen.orte.form.hoehe')}</Label>
		<Input id="location-elevation" name="location-elevation" type="number" bind:value={elevationM} />
	</div>

	<div>
		<Label for="location-region">{$t('listen.orte.form.region')}</Label>
		<Input id="location-region" name="location-region" placeholder={$t('listen.orte.form.region_platzhalter')} bind:value={region} />
	</div>

	<div>
		<Label for="location-bergfex">{$t('listen.orte.form.bergfex')}</Label>
		<Input id="location-bergfex" name="location-bergfex" placeholder={$t('listen.orte.form.bergfex_platzhalter')} bind:value={bergfexSlug} />
	</div>

	<div>
		<Label for="activity-profile">{$t('vergleich.neu.aktivitaetsprofil')}</Label>
		<Select
			id="activity-profile"
			options={[{ value: '', label: $t('vergleich.gruppe.kein_profil') }, ...ACTIVITY_PROFILE_OPTIONS]}
			value={activityProfile}
			onValueChange={(v) => (activityProfile = v as ActivityProfile | '')}
			class="w-full"
		/>
	</div>

	<div>
		<Label for="location-group">{$t('vergleich.ort.gruppe_optional')}</Label>
		<Select
			id="location-group"
			data-testid="location-form-group"
			options={[{ value: '', label: $t('listen.orte.form.keine_gruppe') }, ...groups.map((g) => ({ value: g.id, label: g.name }))]}
			bind:value={groupId}
			class="w-full"
		/>
	</div>

	<div class="flex justify-end gap-2 pt-2">
		<Btn variant="outline" onclick={oncancel}>{$t('aktionen.abbrechen')}</Btn>
		<Btn variant="primary" onclick={save}>{$t('aktionen.speichern')}</Btn>
	</div>
</div>
