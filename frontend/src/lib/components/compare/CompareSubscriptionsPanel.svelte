<script lang="ts">
	import type { Subscription } from '$lib/types.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Dot } from '$lib/components/ui/dot/index.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import PencilIcon from '@lucide/svelte/icons/pencil';

	interface Props {
		subscriptions: Subscription[];
		onsavebriefing: () => void;
	}

	let { subscriptions, onsavebriefing }: Props = $props();

	const WEEKDAYS = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];

	function scheduleLabel(sub: Subscription): string {
		if (sub.schedule === 'daily_morning') return 'Täglich 07:00';
		if (sub.schedule === 'daily_evening') return 'Täglich 18:00';
		if (sub.schedule === 'weekly') return `Wöchentlich ${WEEKDAYS[sub.weekday ?? 0]}`;
		return sub.schedule;
	}

	function locationsLabel(sub: Subscription): string {
		if (!sub.locations || sub.locations.length === 0 || sub.locations[0] === '*') return 'Alle Orte';
		return `${sub.locations.length} Orte`;
	}

	function formatLastRun(ts: string | undefined): string {
		if (!ts) return '';
		return new Intl.DateTimeFormat('de-AT', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		}).format(new Date(ts));
	}
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between">
		<h3 class="text-base font-semibold">Auto-Reports</h3>
		<Btn variant="outline" size="sm" onclick={onsavebriefing}>
			Aktuellen Vergleich speichern
		</Btn>
	</div>

	{#if subscriptions.length === 0}
		<p class="text-sm text-muted-foreground">Noch keine Auto-Reports gespeichert.</p>
	{:else}
		<div class="space-y-2">
			{#each subscriptions as sub}
				<Card.Root>
					<Card.Content class="py-3">
						<div class="flex items-start justify-between gap-2">
							<div class="flex items-center gap-2 min-w-0">
								<Dot tone={sub.enabled ? 'success' : 'default'} size="sm" />
								<div class="min-w-0">
									<p class="truncate font-medium text-sm">{sub.name}</p>
									<p class="text-xs text-muted-foreground">
										{scheduleLabel(sub)} · {locationsLabel(sub)}
									</p>
									{#if sub.last_run}
										<p class="text-xs text-muted-foreground mt-0.5">
											Zuletzt: {formatLastRun(sub.last_run)}
											{#if sub.last_status === 'ok'}
												<Pill tone="success">ok</Pill>
											{:else if sub.last_status === 'error'}
												<Pill tone="danger">Fehler</Pill>
											{/if}
										</p>
									{/if}
								</div>
							</div>
							<Btn variant="ghost" size="icon-sm" title="Bearbeiten">
								<PencilIcon class="size-3.5" />
							</Btn>
						</div>
					</Card.Content>
				</Card.Root>
			{/each}
		</div>
	{/if}
</div>
