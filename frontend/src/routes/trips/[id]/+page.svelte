<script lang="ts">
	// Issue #302 — Danger-Zone unter den Tabs (Spec §6).
	// Pause/Archive/Delete-Logik ist aus TripHeader hierhergewandert; Headerbuttons
	// (Briefing-Vorschau, Bearbeiten, Test-Briefing) leben in der neuen Header-Komponente.
	import { page } from '$app/state';
	import { goto, beforeNavigate } from '$app/navigation';
	import { TripHeader } from '$lib/components/organisms';
	import { TripTabs } from '$lib/components/trip-detail';
	import { Btn, TopoBg } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';
	import { createSaveStatus } from '$lib/stores/saveStatusStore.svelte';

	let { data } = $props();

	// Trip in lokales $state heben, damit Status-Updates (Pause/Archive)
	// reaktiv ohne Page-Reload sichtbar werden.
	let trip = $state<Trip>(data.trip);

	// Issue #758: SaveStatus-Controller — eine Instanz pro Trip-Seite (kein Singleton!).
	const tripSaveCtl = createSaveStatus();

	// Issue #758: Flush ausstehender Auto-Saves vor Navigation (AC-5).
	beforeNavigate(({ cancel, to, willUnload }) => {
		if (willUnload) return; // Browser-Navigation, kein Flush möglich
		if (tripSaveCtl.hasPending) {
			cancel();
			const targetUrl = to?.url?.href ?? null;
			void tripSaveCtl.flush().then(() => {
				if (targetUrl) void goto(targetUrl);
			});
		}
	});

	// Issue #516 — Initial-Tab aus ?tab=…-Query (kanonisches Schema, kein #hash mehr).
	// $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived(page.url.searchParams.get('tab') || 'overview');

	const now = new Date();
	const status = $derived(deriveTripStatus(trip, now));

	let archiveDialogOpen = $state(false);
	let deleteDialogOpen = $state(false);
	let isLoading = $state(false);
	let errorMsg = $state<string | null>(null);
	let testBriefingLoading = $state(false);
	let testBriefingStatus = $state<'idle' | 'ok' | 'error'>('idle');
	let testBriefingMessage = $state<string | null>(null);
	let testBriefingTimer: ReturnType<typeof setTimeout> | undefined;
	let testBriefingMenuOpen = $state(false);

	async function sendStateUpdate(paused?: boolean, archived?: boolean): Promise<void> {
		const body: Record<string, boolean> = {};
		if (paused !== undefined) body.paused = paused;
		if (archived !== undefined) body.archived = archived;
		isLoading = true;
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			if (!res.ok) throw new Error(`PATCH /state failed: ${res.status}`);
			const updated: Trip = await res.json();
			errorMsg = null;
			trip = updated;
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : String(e);
		} finally {
			isLoading = false;
		}
	}

	function handlePauseClick(): void {
		const nextPaused = status !== 'paused';
		void sendStateUpdate(nextPaused, undefined);
	}

	function handleArchiveClick(): void {
		archiveDialogOpen = true;
	}

	function handleArchiveCancel(): void {
		archiveDialogOpen = false;
	}

	function handleArchiveConfirm(): void {
		const nextArchived = status !== 'archived';
		archiveDialogOpen = false;
		void sendStateUpdate(undefined, nextArchived);
	}

	function handleArchiveDialogOpenChange(open: boolean): void {
		archiveDialogOpen = open;
	}

	function handleDeleteClick(): void {
		deleteDialogOpen = true;
	}

	function handleDeleteCancel(): void {
		deleteDialogOpen = false;
	}

	async function handleDeleteConfirm(): Promise<void> {
		isLoading = true;
		try {
			const res = await fetch(`/api/trips/${trip.id}`, { method: 'DELETE' });
			if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
			void goto('/trips');
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : String(e);
		} finally {
			isLoading = false;
			deleteDialogOpen = false;
		}
	}

	function handleDeleteDialogOpenChange(open: boolean): void {
		deleteDialogOpen = open;
	}

	function handleStatusChange(updated: Trip): void {
		trip = updated;
	}

	function handleTripUpdate(updated: Trip): void {
		trip = updated;
	}

	async function handleTestBriefing(reportType: 'morning' | 'evening'): Promise<void> {
		testBriefingMenuOpen = false;
		clearTimeout(testBriefingTimer);
		testBriefingLoading = true;
		testBriefingStatus = 'idle';
		try {
			const res = await fetch(`/api/trips/${trip.id}/send?report_type=${reportType}`, {
				method: 'POST'
			});
			if (res.ok) {
				testBriefingStatus = 'ok';
				testBriefingMessage = null;
			} else {
				testBriefingStatus = 'error';
				let detail: string | undefined;
				try {
					const body = await res.json();
					detail = body?.detail;
				} catch {
					/* kein JSON-Body */
				}
				if (res.status >= 500) {
					// AC-1/AC-3: Serverfehler → handlungsleitende Meldung, roher detail wird
					// NICHT angezeigt; Statuscode + Rohtext werden observierbar geloggt.
					console.error(`Test-Briefing fehlgeschlagen: HTTP ${res.status}`, detail);
					testBriefingMessage = 'Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
				} else if (detail) {
					testBriefingMessage = detail; // AC-2: qualifizierte 4xx-Meldung bleibt
				} else {
					testBriefingMessage = 'Versand fehlgeschlagen — bitte später erneut versuchen.';
				}
			}
		} catch (e) {
			console.error(e);
			testBriefingStatus = 'error';
			testBriefingMessage = 'Versand fehlgeschlagen — bitte später erneut versuchen.';
		} finally {
			testBriefingLoading = false;
		}
		clearTimeout(testBriefingTimer);
		testBriefingTimer = setTimeout(() => { testBriefingStatus = 'idle'; }, 4000);
	}
</script>

<svelte:head><title>{trip.name} — Gregor Zwanzig</title></svelte:head>

<main style="position: relative; overflow: hidden;">
	<TopoBg opacity={0.14} />
	<div class="breadcrumb-bar" data-testid="trip-detail-breadcrumb-bar">
		<div class="mono breadcrumb-path" style="font-size: 11px; color: var(--g-ink-3); letter-spacing: 0.06em;">
			<span style="opacity: 0.6;">Trips</span>
			<span style="margin: 0 8px;">/</span>
			<span style="color: var(--g-ink);">{trip.shortcode ?? trip.name}</span>
		</div>
		<div class="breadcrumb-actions">
			<Btn variant="ghost" size="sm" onclick={handlePauseClick} disabled={isLoading || status === 'archived'}>
				{status === 'paused' ? 'Fortsetzen' : 'Pausieren'}
			</Btn>
			<Btn variant="ghost" size="sm" onclick={handleArchiveClick} disabled={isLoading}>
				{status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
			</Btn>
			<div style="position: relative; display: inline-block;">
				<Btn
					variant="accent"
					size="sm"
					data-testid="test-briefing-menu-toggle"
					onclick={() => { testBriefingMenuOpen = !testBriefingMenuOpen; }}
					disabled={testBriefingLoading}
				>
					{testBriefingLoading ? 'Wird gesendet…' : 'Test-Briefing senden'}
				</Btn>
				{#if testBriefingMenuOpen}
					<div
						class="test-briefing-menu"
						style="position: absolute; top: calc(100% + 4px); left: 0; z-index: 20; display: flex; flex-direction: column; gap: 4px; padding: 6px; background: var(--g-card, #ffffff); border: 1px solid var(--g-line, #d8d4ca); border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.12);"
					>
						<Btn
							variant="ghost"
							size="sm"
							data-testid="test-briefing-option-morning"
							onclick={() => handleTestBriefing('morning')}
						>
							Morgen
						</Btn>
						<Btn
							variant="ghost"
							size="sm"
							data-testid="test-briefing-option-evening"
							onclick={() => handleTestBriefing('evening')}
						>
							Abend
						</Btn>
					</div>
				{/if}
			</div>
			{#if testBriefingStatus === 'ok'}
				<span data-testid="test-briefing-success" style="font-size: 12px; color: var(--g-success, #2e7d32);">Test-Briefing gesendet!</span>
			{:else if testBriefingStatus === 'error'}
				<span data-testid="test-briefing-error" style="font-size: 12px; color: var(--g-error, #c62828);">{testBriefingMessage ?? 'Fehler beim Senden'}</span>
			{/if}
		</div>
	</div>
	<TripHeader {trip} {now} onStatusChange={handleStatusChange} onTripUpdate={handleTripUpdate} saveController={tripSaveCtl} />
	<TripTabs {initialTab} badges={{}} {trip} onTripUpdate={handleTripUpdate} saveController={tripSaveCtl} />
</main>

<ConfirmDialog
	open={archiveDialogOpen}
	title={status === 'archived' ? 'Trip reaktivieren?' : 'Trip archivieren?'}
	description={status === 'archived'
		? 'Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv.'
		: 'Archivierte Trips erhalten keine Briefings mehr.'}
	confirmLabel={status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
	confirmVariant="primary"
	data-testid="trip-detail-archive-confirm-dialog"
	cancelTestid="trip-detail-archive-confirm-cancel"
	confirmTestid="trip-detail-archive-confirm-yes"
	disabled={isLoading}
	onConfirm={handleArchiveConfirm}
	onCancel={handleArchiveCancel}
	onOpenChange={handleArchiveDialogOpenChange}
/>

<ConfirmDialog
	open={deleteDialogOpen}
	title="Trip endgültig löschen?"
	description="Dieser Schritt löscht den Trip dauerhaft und kann nicht rückgängig gemacht werden."
	confirmLabel="Löschen"
	confirmVariant="destructive"
	data-testid="trip-detail-delete-confirm-dialog"
	cancelTestid="trip-detail-delete-confirm-cancel"
	confirmTestid="trip-detail-delete-confirm-yes"
	disabled={isLoading}
	onConfirm={handleDeleteConfirm}
	onCancel={handleDeleteCancel}
	onOpenChange={handleDeleteDialogOpenChange}
/>

<style>
	.breadcrumb-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 40px;
		border-bottom: 1px solid var(--g-rule-soft);
		gap: 16px;
		flex-wrap: wrap;
	}
	.breadcrumb-actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
</style>
