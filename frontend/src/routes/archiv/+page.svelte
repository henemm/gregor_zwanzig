<script lang="ts">
	// Issue #388 — Archiv-Seite: Atomic-Migration + vollstaendige Listenansicht.
	//
	// Vorlage: docs/design-requests/issue_15_atomic_design/spec/screen-archive.jsx
	// Die Inline-Helper der JSX-Vorlage sind durch Atome ersetzt:
	//   Sort-Tabs       -> Segmented (atoms)
	//   Aktions-Buttons -> Btn variant="quiet" size="icon-sm" (atoms)
	//
	// Spec: docs/specs/modules/issue_388_archiv_atomic.md

	import type { PageData } from './$types.js';
	import type { Trip } from '$lib/types.js';
	import Segmented from '$lib/components/atoms/Segmented.svelte';
	import { Btn } from '$lib/components/atoms';
	import { Card, Eyebrow } from '$lib/components/atoms';
	import { Stat } from '$lib/components/molecules';
	import HistoryIcon from '@lucide/svelte/icons/history';
	import CopyIcon from '@lucide/svelte/icons/copy';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import SearchIcon from '@lucide/svelte/icons/search';
	import BriefingHistoryDialog from '$lib/components/briefing-history/BriefingHistoryDialog.svelte';
	import { formatEventSummary } from './archiveHelpers.js';

	let { data }: { data: PageData } = $props();

	const archiveStats = $derived(
		data.archiveStats ?? { briefings: {} as Record<string, number>, alerts: {} as Record<string, number> }
	);

	const SORT_OPTIONS = [
		{ value: 'recent', label: 'Neueste' },
		{ value: 'accuracy', label: 'Genauigkeit' },
		{ value: 'stages', label: 'Etappen' }
	];

	let query = $state('');
	let sort = $state('recent');
	let historyTripId = $state<string | null>(null);
	let historyTripName = $state('');

	// Tour-Zeitraum aus den Etappen-Daten (kein eigenes from/to im Trip-Modell).
	function stageDates(t: Trip): string[] {
		return (t.stages ?? []).map((s) => s.date).filter(Boolean).sort();
	}
	function rangeFrom(t: Trip): string {
		const d = stageDates(t);
		return d.length ? d[0] : (t.archived_at ?? '').slice(0, 10);
	}
	function rangeTo(t: Trip): string {
		const d = stageDates(t);
		return d.length ? d[d.length - 1] : (t.archived_at ?? '').slice(0, 10);
	}
	function alertCount(t: Trip): number {
		// Demo-Trips bringen alerts_count direkt mit (Issue #583).
		// Echte Trips zählen über archiveStats (Briefing-Log).
		return t.alerts_count ?? archiveStats.alerts[t.id] ?? 0;
	}
	function briefingCount(t: Trip): number {
		return t.briefings_count ?? archiveStats.briefings[t.id] ?? 0;
	}

	const filtered = $derived(
		(data.trips as Trip[])
			.filter((t) => t.name.toLowerCase().includes(query.toLowerCase()))
			.sort((a, b) => {
				if (sort === 'recent')
					return (b.archived_at ?? '').localeCompare(a.archived_at ?? '');
				if (sort === 'stages') return (b.stages?.length ?? 0) - (a.stages?.length ?? 0);
				// 'accuracy': kein Backend-Feld — bestehende Reihenfolge beibehalten.
				return 0;
			})
	);

	const totalTrips = $derived((data.trips as Trip[]).length);
	const totalBriefings = $derived(
		(data.trips as Trip[]).reduce((s, t) => s + briefingCount(t), 0)
	);
	const totalAlerts = $derived(
		(data.trips as Trip[]).reduce((s, t) => s + alertCount(t), 0)
	);
	const avgAccuracy = $derived.by(() => {
		const accs = (data.trips as Trip[])
			.map((t) => t.accuracy_pct)
			.filter((v): v is number => typeof v === 'number');
		return accs.length ? Math.round(accs.reduce((s, n) => s + n, 0) / accs.length) : null;
	});
</script>

<main style="padding:32px 40px;overflow:auto">
	<!-- Header -->
	<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px">
		<div>
			<Eyebrow>Workspace · Vergangene Trips</Eyebrow>
			<h1
				style="font-size:32px;font-weight:600;letter-spacing:-0.025em;margin-top:4px"
			>
				Archiv
			</h1>
			<p
				style="font-size:14px;color:var(--g-ink-3);margin-top:6px;max-width:620px;line-height:1.5"
			>
				Trips, deren Enddatum vorbei ist. Hier siehst du nachträglich, wie gut die
				Briefings getroffen haben, und kannst einen Trip als Vorlage für eine neue
				Planung übernehmen.
			</p>
		</div>
	</div>

	<!-- Toolbar: Suche + Sortierung -->
	<div style="display:flex;gap:16px;align-items:center;margin-bottom:20px">
		<div style="position:relative;flex:0 0 380px">
			<span style="position:absolute;top:9px;left:12px;color:var(--g-ink-4);display:inline-flex">
				<SearchIcon size={14} />
			</span>
			<input
				bind:value={query}
				placeholder="Suchen…"
				style="width:100%;padding:9px 14px 9px 34px;border:1px solid var(--g-rule);border-radius:var(--g-r-pill);background:var(--g-card);font-size:13px;font-family:var(--g-font-sans);color:var(--g-ink);outline:none"
			/>
		</div>
		<div
			style="display:flex;align-items:center;gap:8px;font-size:11px;font-family:var(--g-font-mono);letter-spacing:0.16em;text-transform:uppercase;color:var(--g-ink-3)"
		>
			<span>Sortieren</span>
			<Segmented options={SORT_OPTIONS} selected={sort} onselect={(v) => (sort = v)} />
		</div>
	</div>

	<!-- Stats-Strip -->
	<div
		style="display:flex;gap:32px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--g-rule-soft)"
	>
		<Stat layout="inline" label="Trips" value={totalTrips} />
		<Stat layout="inline" label="Briefings gesendet" value={totalBriefings} />
		<Stat
			layout="inline"
			label="Forecast-Treffer Ø"
			value={avgAccuracy != null ? `${avgAccuracy}%` : null}
			tone="accent"
		/>
		<Stat layout="inline" label="Alarme ausgelöst" value={totalAlerts} />
	</div>

	<!-- Tabelle -->
	<Card padding={0} style="overflow:hidden">
		<!-- Kopfzeile -->
		<div
			style="display:grid;grid-template-columns:1.7fr 0.7fr 1.1fr 0.9fr 1.6fr auto;gap:0;padding:12px 20px;background:var(--g-paper-deep);font-size:11px;font-family:var(--g-font-mono);letter-spacing:0.18em;text-transform:uppercase;color:var(--g-ink-3);font-weight:500;border-bottom:1px solid var(--g-rule)"
		>
			<div>Name</div>
			<div>Etappen</div>
			<div>Zeitraum</div>
			<div>Treffer</div>
			<div>Was passiert ist</div>
			<div style="text-align:right">Aktionen</div>
		</div>

		{#each filtered as trip, i (trip.id)}
			{@render archiveRow(trip, i % 2 === 1)}
		{/each}

		{#if filtered.length === 0}
			<div style="padding:40px;text-align:center;color:var(--g-ink-3);font-size:13px">
				{#if query}
					Keine archivierten Trips für »{query}« gefunden.
				{:else}
					Keine archivierten Trips.
				{/if}
			</div>
		{/if}
	</Card>

	<!-- Footer-Zaehler -->
	<div
		style="margin-top:14px;font-size:11px;color:var(--g-ink-4);font-family:var(--g-font-mono);letter-spacing:0.06em"
	>
		{filtered.length} von {totalTrips} archivierten Trips · auto-archiviert nach Trip-Ende
	</div>

	<BriefingHistoryDialog
		open={historyTripId !== null}
		tripId={historyTripId ?? ''}
		tripName={historyTripName}
		onclose={() => (historyTripId = null)}
	/>
</main>

<!-- ArchiveRow: Tabellenzeile, identisches 6-Spalten-Grid wie Kopfzeile. -->
{#snippet archiveRow(trip: Trip, alt: boolean)}
	{@const stageN = trip.stages?.length ?? 0}
	{@const alerts = alertCount(trip)}
	<div
		style="display:grid;grid-template-columns:1.7fr 0.7fr 1.1fr 0.9fr 1.6fr auto;align-items:center;padding:16px 20px;gap:0;border-bottom:1px solid var(--g-rule-soft);background:{alt
			? 'var(--g-paper-deep)'
			: 'transparent'}"
	>
		<div style="display:flex;align-items:center;gap:10px;min-width:0">
			<span
				style="width:7px;height:7px;border-radius:50%;background:var(--g-ink-4);flex-shrink:0"
			></span>
			<span
				style="font-size:14px;font-weight:600;letter-spacing:-0.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
				>{trip.name}</span
			>
			{#if alerts > 0}
				<span
					style:font-size="10px"
					style:font-family="var(--g-font-mono)"
					style:color="var(--g-accent-deep)"
					style:text-transform="uppercase"
					style:letter-spacing="0.16em"
					>· {alerts} alert{alerts > 1 ? 's' : ''}</span
				>
			{/if}
		</div>
		<div style="font-size:13px;color:var(--g-ink-2);font-variant-numeric:tabular-nums">
			{stageN}
			{stageN === 1 ? 'Etappe' : 'Etappen'}
		</div>
		<div
			style="font-size:13px;color:var(--g-ink-2);font-family:var(--g-font-mono);letter-spacing:0.02em"
		>
			{rangeFrom(trip)} → {rangeTo(trip)}
		</div>
		{@render accuracyBar(trip)}
		<div
			style="font-size:12px;color:var(--g-ink-3);line-height:1.4;padding-right:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
		>
			{trip.headline || formatEventSummary(archiveStats.briefings[trip.id] ?? 0, archiveStats.alerts[trip.id] ?? 0)}
		</div>
		<div style="display:flex;gap:4px;justify-content:flex-end">
			<Btn variant="quiet" size="icon-sm" title="Briefing-Verlauf öffnen"
				onclick={() => { historyTripId = trip.id; historyTripName = trip.name; }}>
				<HistoryIcon size={14} />
			</Btn>
			<Btn variant="quiet" size="icon-sm" title="Als Vorlage neu anlegen" href="/trips/new?from={trip.id}">
				<CopyIcon size={14} />
			</Btn>
			<span style="width:1px;height:18px;background:var(--g-rule);margin:0 4px"></span>
			<Btn variant="quiet" size="icon-sm" title="Endgültig löschen">
				<Trash2Icon size={14} />
			</Btn>
		</div>
	</div>
{/snippet}

<!-- AccuracyBar: zeigt accuracy_pct aus Trip-Daten oder Em-Dash wenn nicht gesetzt. -->
{#snippet accuracyBar(trip: Trip)}
	{@const value = trip.accuracy_pct ?? null}
	{@const color = value == null ? 'var(--g-ink-4)' : value >= 90 ? '#3d6b3a' : value >= 80 ? 'var(--g-ink-2)' : '#c08a1a'}
	<div style="display:flex;align-items:center;gap:10px;padding-right:16px">
		<div style="flex:1;height:4px;background:var(--g-rule-soft);border-radius:var(--g-r-pill);overflow:hidden;max-width:80px">
			<div style="width:{value ?? 0}%;height:100%;background:{color}"></div>
		</div>
		<span style="font-family:var(--g-font-mono);font-size:12px;font-weight:600;font-variant-numeric:tabular-nums;color:{color}">{value != null ? `${value}%` : '—'}</span>
	</div>
{/snippet}
