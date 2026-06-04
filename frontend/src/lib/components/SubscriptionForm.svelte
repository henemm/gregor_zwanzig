<script lang="ts">
	import type { Subscription, Location, ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import { Btn, Input } from '$lib/components/atoms';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';

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
	let sendTelegram = $state(subscription?.send_telegram ?? false);
	let allLocations = $state(
		!subscription || !subscription.locations || subscription.locations[0] === '*'
	);
	let selectedLocations = $state<string[]>(
		subscription?.locations?.filter((l) => l !== '*') ?? []
	);
	let activityProfile = $state<ActivityProfile>(subscription?.activity_profile ?? 'allgemein');
	let recipients = $state(subscription?.recipients?.join(', ') ?? '');
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
			id: subscription?.id || toKebab(name),
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
			send_telegram: sendTelegram,
			locations: allLocations ? ['*'] : selectedLocations,
			...(subscription?.display_config && { display_config: subscription.display_config }),
			activity_profile: activityProfile,
			recipients: sendEmail
				? recipients
						.split(',')
						.map((e: string) => e.trim())
						.filter((e: string) => e.includes('@'))
				: []
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
		<Checkbox id="sub-enabled" bind:checked={enabled}>Aktiv</Checkbox>
	</div>

	<!-- Schedule -->
	<div>
		<Label for="sub-schedule">Zeitplan</Label>
		<Select
			id="sub-schedule"
			name="sub-schedule"
			bind:value={schedule}
			class="w-full"
		>
			<option value="daily_morning">Täglich 07:00</option>
			<option value="daily_evening">Täglich 18:00</option>
			<option value="weekly">Wöchentlich</option>
		</Select>
	</div>

	<!-- Weekday (only if weekly) -->
	{#if schedule === 'weekly'}
		<div>
			<Label for="sub-weekday">Wochentag</Label>
			<Select
				id="sub-weekday"
				name="sub-weekday"
				bind:value={weekday}
				class="w-full"
			>
				{#each WEEKDAYS as day, i}
					<option value={i}>{day}</option>
				{/each}
			</Select>
		</div>
	{/if}

	<!-- Activity Profile -->
	<div>
		<Label for="sub-profile">Aktivitätsprofil</Label>
		<Select id="sub-profile" bind:value={activityProfile} class="w-full">
			{#each ACTIVITY_PROFILE_OPTIONS as opt}
				<option value={opt.value}>{opt.label}</option>
			{/each}
		</Select>
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
		<Select
			id="sub-forecast"
			name="sub-forecast"
			bind:value={forecastHours}
			class="w-full"
		>
			<option value={24}>24 Stunden</option>
			<option value={48}>48 Stunden</option>
			<option value={72}>72 Stunden</option>
		</Select>
	</div>

	<!-- Top N -->
	<div>
		<Label for="sub-topn">Top Locations</Label>
		<p class="text-xs text-muted-foreground">Anzahl Locations mit stündlichen Details im Report</p>
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
		<Checkbox id="sub-hourly" bind:checked={includeHourly}>Stündliche Daten einschließen</Checkbox>
	</div>

	<!-- Channels -->
	<div class="space-y-2">
		<p class="text-sm font-medium">Kanäle</p>
		<div class="flex items-center gap-3">
			<Checkbox id="sub-email" bind:checked={sendEmail}>E-Mail</Checkbox>
		</div>
		{#if sendEmail}
			<div>
				<Label for="sub-recipients">E-Mail-Empfänger</Label>
				<Input
					id="sub-recipients"
					placeholder="email@example.com, andere@example.com"
					bind:value={recipients}
				/>
				<p class="text-xs text-muted-foreground mt-1">
					Leer lassen für Standard-Empfänger. Komma-getrennt für mehrere.
				</p>
			</div>
		{/if}
		<div class="flex items-center gap-3">
			<Checkbox id="sub-telegram" bind:checked={sendTelegram}>Telegram</Checkbox>
		</div>
	</div>

	<!-- Locations -->
	<div class="space-y-2">
		<p class="text-sm font-medium">Locations</p>
		<div class="flex items-center gap-3">
			<Checkbox id="sub-all-locs" bind:checked={allLocations}>Alle Locations</Checkbox>
		</div>
		{#if !allLocations}
			<div class="max-h-40 overflow-y-auto rounded-lg border border-input p-2 space-y-1">
				{#each locations as loc}
					<div class="flex items-center gap-2">
						<Checkbox
							id={`loc-${loc.id}`}
							checked={selectedLocations.includes(loc.id)}
							onchange={() => toggleLocation(loc.id)}
						>{loc.name}</Checkbox>
					</div>
				{/each}
				{#if locations.length === 0}
					<p class="text-sm text-muted-foreground">Keine Locations vorhanden</p>
				{/if}
			</div>
		{/if}
	</div>

	<div class="flex justify-end gap-2 pt-2">
		<Btn variant="outline" onclick={oncancel}>Abbrechen</Btn>
		<Btn variant="primary" onclick={save}>Speichern</Btn>
	</div>
</div>
