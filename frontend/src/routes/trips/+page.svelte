<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { Btn, Input, Dot, Eyebrow, Pill, Stat, Card } from '$lib/components/atoms';
	import { ConfirmDialog, ReportConfigDialog, TestReportDialog } from '$lib/components/molecules';
	import SearchIcon from '@lucide/svelte/icons/search';
	import BellIcon from '@lucide/svelte/icons/bell';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PlayIcon from '@lucide/svelte/icons/play';
import PauseIcon from '@lucide/svelte/icons/pause';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import SendIcon from '@lucide/svelte/icons/send';
	import { deriveTripStatus, tripStatus, type HomeTripStatus } from '$lib/utils/tripStatus';

	// #706 — Portal-Action: hängt das Element an document.body statt in den overflow-Baum
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return { destroy() { node.remove(); } };
	}

	const now = new Date();

	let { data } = $props();

	let trips: Trip[] = $state(data.trips);
	let refetching = $state(false);
	async function refetchTrips() {
		refetching = true;
		try { trips = await api.get<Trip[]>('/api/trips'); }
		finally { refetching = false; }
	}
	let search = $state('');
	let filteredTrips = $derived(
		trips.filter(t => t.name.toLowerCase().includes(search.toLowerCase()))
	);
	let mobileFilter = $state<'all' | HomeTripStatus>('all');
	let mobileFiltered = $derived(
		filteredTrips.filter(t => mobileFilter === 'all' || tripStatus(t, now) === mobileFilter)
	);
	let deleteTarget: Trip | null = $state(null);
	let archiveTarget: Trip | null = $state(null);
	let error: string | null = $state(null);

	// Report Config Dialog
	let reportConfigTarget: Trip | null = $state(null);
	let reportConfigLoading = $state(false);
	let reportConfigSaving = $state(false);
	let reportConfigError: string | null = $state(null);
	let reportConfig = $state({
		morning_time: '07:00:00',
		evening_time: '18:00:00',
		enabled: true,
		send_email: true,
		send_sms: false,
		send_telegram: false,
		alert_on_changes: true,
		change_threshold_temp_c: 5,
		change_threshold_wind_kmh: 20,
		change_threshold_precip_mm: 10,
		show_compact_summary: true,
		show_daylight: true,
		wind_exposition_min_elevation_m: null as number | null,
		multi_day_trend_reports: ['evening'] as string[]
	});

	// Test Report
	let testReportTarget: Trip | null = $state(null);
	let testReportHour: 7 | 18 | null = $state(null);
	let testReportRunning = $state(false);
	let testReportResult: string | null = $state(null);
	let testReportError: string | null = $state(null);

	// Mobile Action Sheet (Issue #268)
	let sheetTrip: Trip | null = $state(null);

	// Desktop Overflow-Menü (Issue #486): welche Trip-ID hat ihr Menü gerade offen
	let openMenuId: string | null = $state(null);
	// #706 — position:fixed Menü-Koordinaten (rechtsbündig unterhalb des "…"-Buttons)
	let menuPos = $state({ top: 0, right: 0 });
	// Anker-Rect des auslösenden "…"-Buttons — für Flip-Korrektur nach dem Rendern
	let menuAnchorRect = $state<DOMRect | null>(null);
	// Das aktive Trip-Objekt für das außerhalb-der-Card-Portal-Menü
	let openMenuTrip = $derived(openMenuId ? (filteredTrips.find(t => t.id === openMenuId) ?? null) : null);

	function openMenuAtBtn(e: MouseEvent, tripId: string) {
		e.stopPropagation();
		if (openMenuId === tripId) { openMenuId = null; menuAnchorRect = null; return; }
		const btn = e.currentTarget as HTMLElement;
		const rect = btn.getBoundingClientRect();
		menuAnchorRect = rect;
		// Vorläufige Position unterhalb des Buttons — wird ggf. vom $effect korrigiert
		menuPos = { top: rect.bottom + 6, right: window.innerWidth - rect.right };
		openMenuId = tripId;
	}

	// Flip-Korrektur: nach dem Rendern messen ob das Menü unten aus dem Viewport ragt.
	// Falls ja: Menü oberhalb des Buttons öffnen (und links clampen).
	// untrack() verhindert, dass menuPos als reaktive Dependency des Effects registriert
	// wird — der Effect schreibt menuPos, darf es aber nicht auch lesen (Reaktiv-Schleife).
	let menuEl = $state<HTMLElement | null>(null);
	$effect(() => {
		if (!menuEl || !menuAnchorRect) return;
		const menuRect = menuEl.getBoundingClientRect();
		const vp = window.innerHeight;
		const GAP = 6;
		const MARGIN = 8;
		// Lese den aktuellen menuPos-Zustand untracked, damit kein Selbst-Triggern entsteht.
		const currentPos = untrack(() => ({ ...menuPos }));
		// Vertikaler Flip: ragt das Menü unter den Viewport?
		if (menuRect.bottom > vp) {
			const flippedTop = menuAnchorRect.top - menuRect.height - GAP;
			menuPos = { ...currentPos, top: Math.max(MARGIN, flippedTop) };
		}
		// Horizontales Clampen: ragt das Menü links heraus?
		const menuWidth = menuRect.width;
		const rightFromLeft = window.innerWidth - currentPos.right;
		if (rightFromLeft - menuWidth < MARGIN) {
			menuPos = { ...currentPos, right: window.innerWidth - (menuWidth + MARGIN) };
		}
	});

	$effect(() => {
		if (openMenuId === null) return;
		const close = () => { openMenuId = null; menuAnchorRect = null; };
		// Defer scroll/resize listener by one frame so Playwright's scroll-into-view
		// (triggered by the click) doesn't immediately close the freshly opened menu.
		let timerId: ReturnType<typeof setTimeout>;
		timerId = setTimeout(() => {
			window.addEventListener('scroll', close, { capture: true, passive: true });
			window.addEventListener('resize', close, { passive: true });
		}, 0);
		return () => {
			clearTimeout(timerId);
			window.removeEventListener('scroll', close, { capture: true });
			window.removeEventListener('resize', close);
		};
	});

	let primaryActionLoading: string | null = $state(null);

	function statusTone(trip: Trip): 'success' | 'info' | 'warning' | 'danger' {
		const status = deriveTripStatus(trip, now);
		if (status === 'active') return 'success';
		if (status === 'planned') return 'info';
		if (status === 'paused') return 'warning';
		return 'danger';
	}

	function primaryLabel(trip: Trip): string {
		const s = tripStatus(trip, now);
		if (s === 'aktiv' || s === 'geplant') return 'Briefing-Vorschau';
		if (s === 'draft') return 'Fertigstellen';
		return trip.archived_at ? 'Dearchivieren' : 'Archivieren';
	}

	async function handlePrimaryAction(trip: Trip) {
		const s = tripStatus(trip, now);
		if (s === 'aktiv' || s === 'geplant') {
			goto(`/trips/${trip.id}?tab=preview`);
			return;
		}
		if (s === 'draft') {
			goto(`/trips/${trip.id}/wizard`);
			return;
		}
		if (!trip.archived_at) {
			archiveTarget = trip;
			return;
		}
		primaryActionLoading = trip.id;
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: false })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Statuswechsel';
		} finally {
			primaryActionLoading = null;
		}
	}

	async function handleArchive() {
		if (!archiveTarget) return;
		primaryActionLoading = archiveTarget.id;
		try {
			const res = await fetch(`/api/trips/${archiveTarget.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: true })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			archiveTarget = null;
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Archivieren';
		} finally {
			primaryActionLoading = null;
		}
	}

	async function handlePauseToggle(trip: Trip) {
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ paused: !trip.paused_at })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Pausieren';
		}
	}

	function dateRange(trip: Trip): string {
		if (!trip.stages?.length) return '-';
		const dates = (trip.stages?.map((s) => s.date) ?? []).sort();
		if (dates.length === 1) return dates[0];
		return `${dates[0]} — ${dates[dates.length - 1]}`;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = null;
		try {
			await api.del(`/api/trips/${deleteTarget.id}`);
			trips = trips.filter((t) => t.id !== deleteTarget!.id);
			deleteTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Löschen';
		}
	}

	function openCreate() {
		goto('/trips/new');
	}

	function openEdit(trip: Trip) {
		goto(`/trips/${trip.id}`);
	}

	async function openReportConfig(trip: Trip) {
		reportConfigTarget = trip;
		reportConfigError = null;
		reportConfigLoading = true;
		try {
			const full = await api.get<Trip>(`/api/trips/${trip.id}`);
			if (full.report_config) {
				const rc = full.report_config as typeof reportConfig;
				reportConfig = {
					morning_time: rc.morning_time ?? '07:00:00',
					evening_time: rc.evening_time ?? '18:00:00',
					enabled: rc.enabled ?? true,
					send_email: rc.send_email ?? true,
					send_sms: rc.send_sms ?? false,
						send_telegram: rc.send_telegram ?? false,
					alert_on_changes: rc.alert_on_changes ?? true,
					change_threshold_temp_c: rc.change_threshold_temp_c ?? 5,
					change_threshold_wind_kmh: rc.change_threshold_wind_kmh ?? 20,
					change_threshold_precip_mm: rc.change_threshold_precip_mm ?? 10,
					show_compact_summary: rc.show_compact_summary ?? true,
					show_daylight: rc.show_daylight ?? true,
					wind_exposition_min_elevation_m: rc.wind_exposition_min_elevation_m ?? null,
					multi_day_trend_reports: rc.multi_day_trend_reports ?? ['evening']
				};
			} else {
				reportConfig = {
					morning_time: '07:00:00',
					evening_time: '18:00:00',
					enabled: true,
					send_email: true,
					send_sms: false,
								send_telegram: false,
					alert_on_changes: true,
					change_threshold_temp_c: 5,
					change_threshold_wind_kmh: 20,
					change_threshold_precip_mm: 10,
					show_compact_summary: true,
					show_daylight: true,
					wind_exposition_min_elevation_m: null as number | null,
					multi_day_trend_reports: ['evening'] as string[]
				};
			}
		} catch (e: unknown) {
			reportConfigError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			reportConfigLoading = false;
		}
	}

	async function saveReportConfig() {
		if (!reportConfigTarget) return;
		reportConfigSaving = true;
		reportConfigError = null;
		try {
			const full = await api.get<Trip>(`/api/trips/${reportConfigTarget.id}`);
			await api.put<Trip>(`/api/trips/${reportConfigTarget.id}`, {
				...full,
				report_config: reportConfig
			});
			await refetchTrips();
			reportConfigTarget = null;
		} catch (e: unknown) {
			reportConfigError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern';
		} finally {
			reportConfigSaving = false;
		}
	}

	async function runTestReport(trip: Trip, hour: 7 | 18) {
		testReportTarget = trip;
		testReportHour = hour;
		testReportRunning = true;
		testReportResult = null;
		testReportError = null;
		try {
			await api.post(`/api/scheduler/trip-reports?hour=${hour}`, {});
			testReportResult = `Test-Report (${hour === 7 ? 'Morning' : 'Evening'}) wurde ausgelöst. Alle aktiven Trips für ${hour}:00 Uhr werden verarbeitet.`;
		} catch (e: unknown) {
			testReportError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Auslösen des Test-Reports';
		} finally {
			testReportRunning = false;
		}
	}

</script>

<div class="space-y-4">
	<div class="flex items-start justify-between gap-4">
		<div>
			<Eyebrow>WORKSPACE · TRIPS</Eyebrow>
			<h1 style="font-size: 32px; font-weight: 600; letter-spacing: -0.025em; margin-top: 4px;">Trips</h1>
			<p class="text-sm text-muted-foreground mt-1">Alle Trips auf einen Blick — Status, Zeitraum und Aktionen.</p>
		</div>
		<Btn variant="accent" onclick={() => goto('/trips/new')}>+ Neuer Trip</Btn>
	</div>

	{#if trips.length > 0}
		{@const countAktiv = trips.filter(t => tripStatus(t, now) === 'aktiv').length}
		{@const countGeplant = trips.filter(t => tripStatus(t, now) === 'geplant').length}
		{@const countFertig = trips.filter(t => tripStatus(t, now) === 'fertig').length}
		{@const countDraft = trips.filter(t => tripStatus(t, now) === 'draft').length}
		<div class="hidden desktop:flex" style="gap: 24px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--g-rule-soft);">
			<Stat label="Aktiv"        value={countAktiv}   layout="inline" tone="accent" />
			<Stat label="Geplant"      value={countGeplant} layout="inline" />
			<Stat label="Abgeschlossen" value={countFertig} layout="inline" />
			<Stat label="Drafts"       value={countDraft}   layout="inline" />
		</div>
	{/if}

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if trips.length === 0}
		<div class="flex flex-col items-center gap-3 py-12">
			<Eyebrow>Noch keine Trips</Eyebrow>
			<p class="text-sm text-muted-foreground mt-1">Erstelle deinen ersten Trip, um Briefings zu erhalten.</p>
			<Btn onclick={openCreate} variant="primary">Neuer Trip</Btn>
		</div>
	{:else}
		<div class="relative mb-3 max-w-[380px]">
			<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
			<Input placeholder="Suchen..." class="pl-8 rounded-full" bind:value={search} />
		</div>
		{#if refetching}
			<div class="space-y-3">
				{#each Array(3) as _}
					<div class="h-12 w-full animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else}
		<!-- Mobile Filter-Pills (Issue #413) -->
		<div class="desktop:hidden flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
			{#each [
				{ label: 'Alle',    value: 'all'     as const, count: filteredTrips.length },
				{ label: 'Aktiv',   value: 'aktiv'   as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'aktiv').length },
				{ label: 'Geplant', value: 'geplant' as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'geplant').length },
				{ label: 'Fertig',  value: 'fertig'  as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'fertig').length },
			] as f (f.value)}
				<button
					class="shrink-0 cursor-pointer inline-flex items-center min-h-[44px]"
					aria-pressed={mobileFilter === f.value}
					onclick={() => { mobileFilter = f.value; }}
				>
					<Pill tone={mobileFilter === f.value ? 'accent' : 'default'}>
						{f.label} ({f.count})
					</Pill>
				</button>
			{/each}
		</div>
		<!-- Mobile Card-Stack (Issue #268 + #413) -->
		<div data-testid="trip-card-stack" class="desktop:hidden flex flex-col gap-2">
			{#each mobileFiltered as trip (trip.id)}
				<div data-testid="trip-card" data-slot="g-card" class="flex flex-col px-3 py-2">
					<div class="flex items-center gap-3">
						<Dot tone={statusTone(trip)} size="sm" class="shrink-0" />
						<button
							data-testid="trip-card-content-btn"
							class="flex-1 flex flex-col items-start text-left min-h-[44px] justify-center min-w-0"
							onclick={() => goto(`/trips/${trip.id}`)}
						>
							<span class="font-medium text-sm truncate w-full">
								{trip.name}
								<span class="text-[10px] font-normal tracking-wider uppercase text-muted-foreground ml-1">· {tripStatus(trip, now)}</span>
							</span>
							{#if trip.region}
								<span class="text-xs text-muted-foreground truncate w-full">{trip.region}</span>
							{/if}
							<span class="text-xs text-muted-foreground truncate w-full">
								{(trip.stages?.length ?? 0)} Etappen · {dateRange(trip)}
							</span>
						</button>
						<button
							data-testid="trip-card-menu-btn"
							class="shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg -mr-1 hover:bg-muted/60 transition-colors"
							onclick={(e) => { e.stopPropagation(); sheetTrip = trip; }}
							aria-label="Aktionen für {trip.name}"
						>
							<EllipsisVerticalIcon class="size-5" />
						</button>
					</div>
				</div>
			{/each}
		</div>
		<!-- Desktop Grid-Tabelle (Issue #580) -->
		<div class="hidden desktop:block">
		<Card padding={0} style="overflow: hidden;">
			<!-- Header-Zeile -->
			<div style="display: grid; grid-template-columns: 1.6fr 0.8fr 1.4fr auto; gap: 0; padding: 12px 20px; background: var(--g-paper-deep); font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.18em; text-transform: uppercase; color: var(--g-ink-3); font-weight: 500; border-bottom: 1px solid var(--g-rule);">
				<div>Name</div>
				<div>Etappen</div>
				<div>Zeitraum</div>
				<div style="text-align: right;">Aktionen</div>
			</div>
			<!-- Trip-Zeilen (Issue #486: Overflow-Menü statt Icon-Geschwader) -->
			{#each filteredTrips as trip, i (trip.id)}
				{@const st = tripStatus(trip, now)}
				{@const isActive = st === 'aktiv'}
				{@const dotColor = st === 'aktiv' ? 'var(--g-accent)' : st === 'geplant' ? '#3d6b3a' : st === 'fertig' ? 'var(--g-ink-3)' : 'var(--g-ink-4)'}
				<div
					role="button"
					tabindex="0"
					title="{trip.name} öffnen"
					onclick={() => goto(`/trips/${trip.id}`)}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goto(`/trips/${trip.id}`); } }}
					style="display: grid; grid-template-columns: 1.6fr 0.8fr 1.4fr auto; align-items: center; padding: 16px 20px; background: {i % 2 === 1 ? 'var(--g-paper-deep)' : 'transparent'}; border-bottom: 1px solid var(--g-rule-soft); gap: 0; cursor: pointer; transition: background 120ms;"
					onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-card-alt, #f1eee6)'; }}
					onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = i % 2 === 1 ? 'var(--g-paper-deep)' : 'transparent'; }}
				>
					<!-- Spalte 1: Name -->
					<div style="display: flex; align-items: center; gap: 10px;">
						<span style="width: 7px; height: 7px; border-radius: 50%; background: {dotColor}; flex-shrink: 0;"></span>
						<span style="font-size: 14px; font-weight: 600; letter-spacing: -0.01em;">{trip.name}</span>
						<span class="status-caption" style="font-size: 10px; font-family: var(--g-font-mono); color: var(--g-ink-4); text-transform: uppercase; letter-spacing: 0.16em;">· {st}</span>
					</div>
					<!-- Spalte 2: Etappen -->
					<div style="font-size: 13px; color: var(--g-ink-2); font-variant-numeric: tabular-nums;">
						{trip.stages?.length ?? 0} {(trip.stages?.length ?? 0) === 1 ? 'Etappe' : 'Etappen'}
					</div>
					<!-- Spalte 3: Zeitraum -->
					<div style="font-size: 13px; color: var(--g-ink-2); font-family: var(--g-font-mono); letter-spacing: 0.02em;">
						{dateRange(trip)}
					</div>
					<!-- Spalte 4: Aktionen (stopPropagation verhindert Zeilen-Navigation) -->
					<div role="presentation" onclick={(e) => e.stopPropagation()} style="display: flex; gap: 8px; justify-content: flex-end; align-items: center; position: relative;">
						{#if isActive}
							<button onclick={(e) => { e.stopPropagation(); runTestReport(trip, 7); }} style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; height: 32px; background: transparent; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink); white-space: nowrap;">
								<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink)" stroke-width="1.7" stroke-linecap="round"><path d="M7 5l12 7-12 7z"/></svg>
								Briefing senden
							</button>
						{/if}
						<button
							data-testid="trip-row-menu-btn"
							title="Aktionen"
							aria-haspopup="menu"
							aria-expanded={openMenuId === trip.id}
							onclick={(e) => openMenuAtBtn(e, trip.id)}
							style="width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; background: {openMenuId === trip.id ? 'var(--g-paper-deep)' : 'transparent'}; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); cursor: pointer;"
						>
							<!-- three-dot icon -->
							<svg width="15" height="15" viewBox="0 0 24 24" fill="none">
								<circle cx="5" cy="12" r="1.4" fill="var(--g-ink-2)"/>
								<circle cx="12" cy="12" r="1.4" fill="var(--g-ink-2)"/>
								<circle cx="19" cy="12" r="1.4" fill="var(--g-ink-2)"/>
							</svg>
						</button>
						<span style="display: inline-flex; color: var(--g-ink-4); margin-left: 2px;">
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
						</span>
					</div>
				</div>
			{/each}
			{#if filteredTrips.length === 0}
				<div style="padding: 40px; text-align: center; color: var(--g-ink-3); font-size: 13px;">
					Keine Trips für »{search}« gefunden.
				</div>
			{/if}
		</Card>
		<div style="margin-top: 14px; font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); letter-spacing: 0.06em;">
			{filteredTrips.length} von {trips.length} Trips
		</div>
		</div>
		{/if}
	{/if}
</div>

{#if openMenuTrip !== null}
	<!-- Overlay zum Schließen bei Außenklick (portal → document.body) -->
	<div use:portal role="presentation" onkeydown={(e)=>{ if(e.key==='Escape') { openMenuId=null; menuAnchorRect=null; } }} onclick={(e) => { e.stopPropagation(); openMenuId = null; menuAnchorRect = null; }} style="position: fixed; inset: 0; z-index: 40;"></div>
	<!-- Overflow-Menü (#706: portal → document.body, kein overflow-Ancestor) -->
	<div use:portal bind:this={menuEl} role="menu" style="position: fixed; top: {menuPos.top}px; right: {menuPos.right}px; z-index: 41; min-width: 232px; background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); box-shadow: var(--g-shadow-2, 0 8px 28px rgba(30,26,18,.16)); padding: 6px;">
		<!-- Briefing jetzt senden -->
		<button role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) runTestReport(t, 7); }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" stroke-width="1.7" stroke-linecap="round"><path d="M7 5l12 7-12 7z"/></svg>
			Briefing jetzt senden
		</button>
		<!-- Email-Vorschau -->
		<button role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) goto(`/trips/${t.id}?tab=preview`); }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
			Email-Vorschau
		</button>
		<!-- Alert-Konfiguration -->
		<button role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) openReportConfig(t); }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></svg>
			Alert-Konfiguration
		</button>
		<!-- Wetter-Metriken -->
		<button role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) goto(`/trips/${t.id}#weather`); }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M12 4v1.5M12 18.5V20M4 12h1.5M18.5 12H20M6 6l1 1M17 17l1 1M6 18l1-1M17 7l1-1"/></svg>
			Wetter-Metriken
		</button>
		<!-- Bearbeiten -->
		<button data-testid="trip-edit-btn" role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) openEdit(t); }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>
			Bearbeiten
		</button>
		<!-- Trenner -->
		<div style="height: 1px; background: var(--g-rule-soft); margin: 6px 8px;"></div>
		<!-- Löschen (danger) -->
		<button role="menuitem" onclick={(e) => { const t = openMenuTrip; e.stopPropagation(); openMenuId = null; menuAnchorRect = null; if (t) deleteTarget = t; }} style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-bad, #a83232);"
			onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)'; }}
			onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-bad, #a83232)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>
			Löschen
		</button>
	</div>
{/if}

<ConfirmDialog
	open={deleteTarget !== null}
	title="Trip löschen"
	description="Diese Aktion kann nicht rückgängig gemacht werden."
	confirmLabel="Löschen"
	confirmVariant="destructive"
	onConfirm={handleDelete}
	onCancel={() => (deleteTarget = null)}
	onOpenChange={(o) => { if (!o) deleteTarget = null; }}
/>

<ConfirmDialog
	open={archiveTarget !== null}
	title="Trip archivieren?"
	description="Archivierte Trips erhalten keine Briefings mehr."
	confirmLabel="Archivieren"
	onConfirm={handleArchive}
	onCancel={() => (archiveTarget = null)}
	onOpenChange={(o) => { if (!o) archiveTarget = null; }}
/>

<ReportConfigDialog
	open={reportConfigTarget !== null}
	trip={reportConfigTarget}
	bind:config={reportConfig}
	loading={reportConfigLoading}
	saving={reportConfigSaving}
	error={reportConfigError}
	onSave={saveReportConfig}
	onClose={() => (reportConfigTarget = null)}
/>

<TestReportDialog
	open={testReportTarget !== null}
	hour={testReportHour}
	running={testReportRunning}
	result={testReportResult}
	error={testReportError}
	onClose={() => { testReportTarget = null; testReportResult = null; testReportError = null; }}
/>

<!-- Bottom-Sheet Backdrop + Panel (Issue #268) -->
{#if sheetTrip !== null}
	<div
		class="fixed inset-0 z-[70] bg-black/50 desktop:hidden"
		onclick={() => (sheetTrip = null)}
		role="presentation"
	></div>
	<div
		data-testid="trip-action-sheet"
		class="fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl border-t"
		style="background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom);"
		role="dialog"
		aria-modal="true"
		aria-label="Aktionen"
	>
	<div class="flex justify-center pt-3 pb-1">
		<div class="w-10 h-1 rounded-full bg-muted-foreground/25"></div>
	</div>
	<div class="px-4 py-2 text-sm font-semibold truncate">{sheetTrip?.name ?? ''}</div>
	<div class="h-px mx-4 bg-border"></div>
	<div class="py-2">
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; goto(`/trips/${t.id}?tab=preview`); }}>
			<SendIcon class="size-4 text-muted-foreground shrink-0" /> Briefing senden
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; openReportConfig(t); }}>
			<BellIcon class="size-4 text-muted-foreground shrink-0" /> Alerts justieren
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; goto(`/trips/${t.id}#weather`); }}>
			<CloudSunIcon class="size-4 text-muted-foreground shrink-0" /> Wetter-Konfiguration
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; openEdit(t); }}>
			<PencilIcon class="size-4 text-muted-foreground shrink-0" /> Bearbeiten
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; handlePauseToggle(t); }}>
			<PauseIcon class="size-4 text-muted-foreground shrink-0" /> {sheetTrip?.paused_at ? 'Reaktivieren' : 'Pausieren'}
		</button>
		<div class="h-px mx-4 bg-border"></div>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; runTestReport(t, 7); }}>
			<PlayIcon class="size-4 text-muted-foreground shrink-0" /> Test Morgen-Report
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; runTestReport(t, 18); }}>
			<PlayIcon class="size-4 text-muted-foreground shrink-0" /> Test Abend-Report
		</button>
		<div class="h-px mx-4 bg-border"></div>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm text-destructive hover:bg-destructive/10 active:bg-destructive/15"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; deleteTarget = t; }}>
			<Trash2Icon class="size-4 shrink-0" /> Löschen
		</button>
	</div>
	<div class="h-2"></div>
	</div>
{/if}
