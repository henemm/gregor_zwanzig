<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import FootprintsIcon from '@lucide/svelte/icons/footprints';
	import GitCompareIcon from '@lucide/svelte/icons/git-compare';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import CalendarIcon from '@lucide/svelte/icons/calendar';
	import ClockIcon from '@lucide/svelte/icons/clock';
	import { goto } from '$app/navigation';

	let { data } = $props();

	const WEEKDAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

	function formatDate(dateStr: string): string {
		const d = new Date(dateStr);
		return d.toLocaleDateString('de-DE', { day: 'numeric', month: 'long' });
	}

	function getScheduleLabel(sub: any): string {
		const hour = String(sub.time_window_start ?? 0).padStart(2, '0');
		const time = `${hour}:00`;
		if (sub.schedule === 'daily_morning' || sub.schedule === 'daily_evening') {
			return `t\u00e4gl. ${time}`;
		}
		if (sub.schedule === 'weekly') {
			const day = WEEKDAYS[sub.weekday ?? 0];
			return `${day} ${time}`;
		}
		return sub.schedule ?? '';
	}

	function getReportLabel(trip: any): string | null {
		const rc = trip.report_config;
		if (!rc?.reports?.length) return null;
		const r = rc.reports[0];
		return r.label ?? r.type ?? null;
	}

	function getFirstDate(trip: any): string | null {
		if (!trip.stages?.length) return null;
		const first = trip.stages[0];
		if (!first.date) return null;
		return formatDate(first.date);
	}
</script>

<div class="space-y-8">
	{#if data.trips.length === 0 && data.subscriptions.length === 0}
		<div class="flex flex-col items-center gap-6 py-16 text-center">
			<h1 class="text-2xl font-bold">Willkommen bei Gregor 20</h1>
			<p class="text-muted-foreground">
				Leg deine erste Tour oder deinen ersten Orts-Vergleich an.
			</p>
			<div class="flex gap-4">
				<Button href="/trips"><PlusIcon class="mr-2 size-4" />Erste Tour anlegen</Button>
				<Button variant="outline" href="/compare"
					><PlusIcon class="mr-2 size-4" />Ersten Vergleich erstellen</Button
				>
			</div>
		</div>
	{:else}
		<h1 class="text-2xl font-bold">Startseite</h1>

		{#if data.trips.length > 0}
			<section>
				<h2 class="mb-4 text-lg font-semibold">Meine Touren</h2>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{#each data.trips as trip}
						{@const firstDate = getFirstDate(trip)}
						{@const reportLabel = getReportLabel(trip)}
						<Card.Root
							class="cursor-pointer transition-shadow hover:shadow-md"
							data-testid="trip-card"
							onclick={() => goto('/trips')}
						>
							<Card.Header>
								<Card.Title class="flex items-center gap-2">
									<FootprintsIcon class="size-4" />
									{trip.name}
								</Card.Title>
							</Card.Header>
							<Card.Content class="space-y-1 text-sm text-muted-foreground">
								{#if firstDate}
									<p><CalendarIcon class="mr-1 inline size-3" />{firstDate}</p>
								{/if}
								<p>
									{trip.stages?.length ?? 0}
									{(trip.stages?.length ?? 0) === 1 ? 'Etappe' : 'Etappen'}
								</p>
								{#if reportLabel}
									<p><ClockIcon class="mr-1 inline size-3" />{reportLabel}</p>
								{/if}
							</Card.Content>
						</Card.Root>
					{/each}
				</div>
			</section>
		{/if}

		{#if data.subscriptions.length > 0}
			<section>
				<h2 class="mb-4 text-lg font-semibold">Orts-Vergleiche</h2>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{#each data.subscriptions as sub}
						{@const scheduleLabel = getScheduleLabel(sub)}
						<Card.Root
							class="cursor-pointer transition-shadow hover:shadow-md"
							data-testid="subscription-card"
							onclick={() => goto('/compare')}
						>
							<Card.Header>
								<Card.Title class="flex items-center gap-2">
									<GitCompareIcon class="size-4" />
									{sub.name}
								</Card.Title>
							</Card.Header>
							<Card.Content class="space-y-1 text-sm text-muted-foreground">
								<p><ClockIcon class="mr-1 inline size-3" />{scheduleLabel}</p>
								{#if sub.locations?.length > 0}
									<p>{sub.locations[0]}</p>
								{/if}
							</Card.Content>
						</Card.Root>
					{/each}
				</div>
			</section>
		{/if}

		<div class="flex gap-3">
			<Button href="/trips" size="sm"><PlusIcon class="mr-2 size-4" />Neue Tour</Button>
			<Button href="/compare" size="sm" variant="outline"
				><PlusIcon class="mr-2 size-4" />Neuer Vergleich</Button
			>
		</div>
	{/if}
</div>
