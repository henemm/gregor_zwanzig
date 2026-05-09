<script lang="ts">
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Dot } from '$lib/components/ui/dot';
	import type { SchedulerStatus, SchedulerJob } from '$lib/types.js';

	interface Props {
		schedulerStatus: SchedulerStatus | null;
	}

	let { schedulerStatus }: Props = $props();

	const JOB_LABELS: Record<string, string> = {
		morning: 'Morgenbriefing',
		morning_subscriptions: 'Morgen-Report',
		evening: 'Abendbriefing',
		evening_subscriptions: 'Abend-Report',
		alert: 'Alert-Check',
		trip_reports_hourly: 'Trip-Reports'
	};

	function dotTone(job: SchedulerJob): 'success' | 'danger' | 'info' {
		if (!job.last_run) return 'info';
		return job.last_run.status === 'ok' ? 'success' : 'danger';
	}

	function timeAgo(iso: string | null | undefined): string {
		if (!iso) return '—';
		const diff = Date.now() - new Date(iso).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'gerade eben';
		if (mins < 60) return `vor ${mins} Min`;
		const hours = Math.floor(mins / 60);
		if (hours < 24) return `vor ${hours} Std`;
		const days = Math.floor(hours / 24);
		return `vor ${days} Tag${days > 1 ? 'en' : ''}`;
	}

	function formatNextRun(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			const date = new Date(iso);
			const time = date.toLocaleString('de-AT', {
				timeZone: 'Europe/Vienna',
				hour: '2-digit',
				minute: '2-digit'
			});
			return time;
		} catch {
			return '—';
		}
	}
</script>

<div data-testid="briefings-timeline">
	<GCard class="p-6">
		<Eyebrow>Was geht raus</Eyebrow>
		{#if schedulerStatus && schedulerStatus.jobs && schedulerStatus.jobs.length > 0}
			<ul class="space-y-2 mt-2">
				{#each schedulerStatus.jobs as job (job.id)}
					<li class="flex items-center gap-2 text-sm flex-wrap">
						<Dot tone={dotTone(job)} size="sm" />
						<span>{JOB_LABELS[job.id] ?? job.name}</span>
						<span class="ml-auto text-muted-foreground">
							nächste: {formatNextRun(job.next_run)}
						</span>
						{#if job.last_run}
							<span class="text-muted-foreground">
								· zuletzt: {timeAgo(job.last_run.time)}
							</span>
						{/if}
					</li>
				{/each}
			</ul>
		{:else}
			<p class="text-muted-foreground mt-2 text-sm">Scheduler nicht verfügbar</p>
		{/if}
	</GCard>
</div>
