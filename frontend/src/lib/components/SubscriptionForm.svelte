<script lang="ts">
	import type { Subscription, Location } from '$lib/types.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';

	interface Props {
		subscription?: Subscription;
		locations: Location[];
		onsave: (sub: Subscription) => void;
		oncancel: () => void;
	}

	let { subscription, locations, onsave, oncancel }: Props = $props();

	const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

	function toKebab(s: string): string {
		return s
			.trim()
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '');
	}

	let name = $state(subscription?.name ?? '');
	let enabled = $state(subscription?.enabled ?? true);
	let schedule = $state<Subscription['schedule']>(subscription?.schedule ?? 'daily_morning');
	let weekday = $state(subscription?.weekday ?? 0);
	let timeWindowStart = $state(subscription?.time_window_start ?? 6);
	let timeWindowEnd = $state(subscription?.time_window_end ?? 20);
	let forecastHours = $state(subscription?.forecast_hours ?? 24);
	let topN = $state(subscription?.top_n ?? 3);
	let includeHourly = $state(subscription?.include_hourly ?? false);
	let sendEmail = $state(subscription?.send_email ?? true);
	let sendSignal = $state(subscription?.send_signal ?? false);
	let sendTelegram = $state(subscription?.send_telegram ?? false);
	let allLocations = $state(
		!subscription || !subscription.locations || subscription.locations[0] === '*'
	);
	let selectedLocations = $state<string[]>(
		subscription?.locations?.filter((l) => l !== '*') ?? []
	);
	let activityProfile = $state<string>(subscription?.activity_profile ?? 'allgemein');
	let error = $state('');

	function toggleLocation(id: string) {
		if (selectedLocations.includes(id)) {
			selectedLocations = selectedLocations.filter((l) => l !== id);
		} else {
			selectedLocations = [...selectedLocations, id];
		}
	}

	function save() {
		error = '';
		if (!name.trim()) {
			error = 'Name ist erforderlich';
			return;
		}
		if (timeWindowStart >= timeWindowEnd) {
			error = 'Zeitfenster Start muss vor Ende liegen';
			return;
		}
		if (topN < 1 || topN > 10) {
			error = 'Top N muss zwischen 1 und 10 liegen';
			return;
		}
		if (!allLocations && selectedLocations.length === 0) {
			error = 'Mindestens eine Location auswählen oder "Alle" aktivieren';
			return;
		}

		const result: Subscription = {
			id: subscription?.id ?? toKebab(name),
			name: name.trim(),
			enabled,
			schedule,
			weekday: schedule === 'weekly' ? weekday : 0,
			time_window_start: timeWindowStart,
			time_window_end: timeWindowEnd,
			forecast_hours: forecastHours as 24 | 48 | 72,
			top_n: topN,
			include_hourly: includeHourly,
			send_email: sendEmail,
			send_signal: sendSignal,
			send_telegram: sendTelegram,
			locations: allLocations ? ['*'] : selectedLocations,
			...(subscription?.display_config && { display_config: subscription.display_config }),
			activity_profile: activityProfile as Subscription['activity_profile']
		};
		onsave(result);
	}
</script>

<div class="space-y-4">
	<div>
		<Label for="sub-name">Name</Label>
		<Input id="sub-name" name="sub-name" placeholder="Name der Subscription" bind:value={name} />
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	<!-- Enabled -->
	<div class="flex items-center gap-3">
		<input
			id="sub-enabled"
			type="checkbox"
			bind:checked={enabled}
			class="h-4 w-4 rounded border-input"
		/>
		<Label for="sub-enabled">Aktiv</Label>
	</div>

	<!-- Schedule -->
	<div>
		<Label for="sub-schedule">Zeitplan</Label>
		<select
			id="sub-schedule"
			name="sub-schedule"
			bind:value={schedule}
			class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
		>
			<option value="daily_morning">Täglich 07:00</option>
			<option value="daily_evening">Täglich 18:00</option>
			<option value="weekly">Wöchentlich</option>
		</select>
	</div>

	<!-- Weekday (only if weekly) -->
	{#if schedule === 'weekly'}
		<div>
			<Label for="sub-weekday">Wochentag</Label>
			<select
				id="sub-weekday"
				name="sub-weekday"
				bind:value={weekday}
				class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
			>
				{#each WEEKDAYS as day, i}
					<option value={i}>{day}</option>
				{/each}
			</select>
		</div>
	{/if}

	<!-- Activity Profile -->
	<div>
		<Label for="sub-profile">Aktivitätsprofil</Label>
		<select id="sub-profile" bind:value={activityProfile}
			class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3">
			<option value="allgemein">Allgemein</option>
			<option value="wintersport">Wintersport</option>
			<option value="wandern">Wandern</option>
		</select>
	</div>

	<!-- Time Window -->
	<div class="grid grid-cols-2 gap-3">
		<div>
			<Label for="sub-start">Zeitfenster Start (Stunde)</Label>
			<Input
				id="sub-start"
				name="sub-start"
				type="number"
				min="0"
				max="23"
				bind:value={timeWindowStart}
			/>
		</div>
		<div>
			<Label for="sub-end">Zeitfenster Ende (Stunde)</Label>
			<Input
				id="sub-end"
				name="sub-end"
				type="number"
				min="0"
				max="23"
				bind:value={timeWindowEnd}
			/>
		</div>
	</div>

	<!-- Forecast Hours -->
	<div>
		<Label for="sub-forecast">Vorhersage-Horizont (Stunden)</Label>
		<select
			id="sub-forecast"
			name="sub-forecast"
			bind:value={forecastHours}
			class="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-3"
		>
			<option value={24}>24 Stunden</option>
			<option value={48}>48 Stunden</option>
			<option value={72}>72 Stunden</option>
		</select>
	</div>

	<!-- Top N -->
	<div>
		<Label for="sub-topn">Top N Locations</Label>
		<Input
			id="sub-topn"
			name="sub-topn"
			type="number"
			min="1"
			max="10"
			bind:value={topN}
		/>
	</div>

	<!-- Include Hourly -->
	<div class="flex items-center gap-3">
		<input
			id="sub-hourly"
			type="checkbox"
			bind:checked={includeHourly}
			class="h-4 w-4 rounded border-input"
		/>
		<Label for="sub-hourly">Stündliche Daten einschließen</Label>
	</div>

	<!-- Channels -->
	<div class="space-y-2">
		<p class="text-sm font-medium">Kanäle</p>
		<div class="flex items-center gap-3">
			<input
				id="sub-email"
				type="checkbox"
				bind:checked={sendEmail}
				class="h-4 w-4 rounded border-input"
			/>
			<Label for="sub-email">E-Mail</Label>
		</div>
		<div class="flex items-center gap-3">
			<input
				id="sub-signal"
				type="checkbox"
				bind:checked={sendSignal}
				class="h-4 w-4 rounded border-input"
			/>
			<Label for="sub-signal">Signal</Label>
		</div>
		<div class="flex items-center gap-3">
			<input
				id="sub-telegram"
				type="checkbox"
				bind:checked={sendTelegram}
				class="h-4 w-4 rounded border-input"
			/>
			<Label for="sub-telegram">Telegram</Label>
		</div>
	</div>

	<!-- Locations -->
	<div class="space-y-2">
		<p class="text-sm font-medium">Locations</p>
		<div class="flex items-center gap-3">
			<input
				id="sub-all-locs"
				type="checkbox"
				bind:checked={allLocations}
				class="h-4 w-4 rounded border-input"
			/>
			<Label for="sub-all-locs">Alle Locations</Label>
		</div>
		{#if !allLocations}
			<div class="max-h-40 overflow-y-auto rounded-lg border border-input p-2 space-y-1">
				{#each locations as loc}
					<div class="flex items-center gap-2">
						<input
							id={`loc-${loc.id}`}
							type="checkbox"
							checked={selectedLocations.includes(loc.id)}
							onchange={() => toggleLocation(loc.id)}
							class="h-4 w-4 rounded border-input"
						/>
						<label for={`loc-${loc.id}`} class="text-sm">{loc.name}</label>
					</div>
				{/each}
				{#if locations.length === 0}
					<p class="text-sm text-muted-foreground">Keine Locations vorhanden</p>
				{/if}
			</div>
		{/if}
	</div>

	<div class="flex justify-end gap-2 pt-2">
		<Button variant="outline" onclick={oncancel}>Abbrechen</Button>
		<Button onclick={save}>Speichern</Button>
	</div>
</div>
