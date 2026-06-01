<script lang="ts">
	// Issue #302 — Danger-Zone unter den Tabs (Spec §6).
	// Pause/Archive/Delete-Logik ist aus TripHeader hierhergewandert; Headerbuttons
	// (Briefing-Vorschau, Bearbeiten, Test-Briefing) leben in der neuen Header-Komponente.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { TripHeader } from '$lib/components/organisms';
	import { TripTabs } from '$lib/components/trip-detail';
	import { Btn, Eyebrow } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';

	let { data } = $props();

	// Trip in lokales $state heben, damit Status-Updates (Pause/Archive)
	// reaktiv ohne Page-Reload sichtbar werden.
	let trip = $state<Trip>(data.trip);

	// Issue #516 — Initial-Tab aus ?tab=…-Query (kanonisches Schema, kein #hash mehr).
	// $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived(page.url.searchParams.get('tab') || 'overview');

	const now = new Date();
	const status = $derived(deriveTripStatus(trip, now));

	let archiveDialogOpen = $state(false);
	let deleteDialogOpen = $state(false);
	let isLoading = $state(false);
	let errorMsg = $state<string | null>(null);

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
</script>

<svelte:head><title>{trip.name} — Gregor Zwanzig</title></svelte:head>

<main class="container mx-auto max-w-5xl p-4">
	<TripHeader {trip} {now} onStatusChange={handleStatusChange} />
	<TripTabs {initialTab} badges={{}} {trip} />

	<section class="danger-zone" data-testid="danger-zone">
		<div class="danger-zone-header">
			<Eyebrow>Selten gebraucht</Eyebrow>
		</div>
		<div class="danger-zone-actions">
			<div class="danger-zone-left">
				<Btn variant="outline" size="sm" disabled>Trip duplizieren</Btn>
				<Btn variant="outline" size="sm" disabled>GPX neu importieren</Btn>
				<Btn
					variant="outline"
					size="sm"
					data-testid="trip-detail-action-pause"
					onclick={handlePauseClick}
					disabled={isLoading || status === 'archived'}
				>
					{status === 'paused' ? 'Fortsetzen' : 'Briefings pausieren'}
				</Btn>
				<Btn
					variant="outline"
					size="sm"
					data-testid="trip-detail-action-archive"
					onclick={handleArchiveClick}
					disabled={isLoading}
				>
					{status === 'archived' ? 'Reaktivieren' : 'Archivieren'}
				</Btn>
			</div>
			<div class="danger-zone-right">
				<Btn
					variant="destructive"
					size="sm"
					data-testid="trip-detail-action-delete"
					onclick={handleDeleteClick}
					disabled={isLoading}
				>
					Trip löschen
				</Btn>
			</div>
		</div>
		{#if errorMsg}
			<p class="danger-zone-error" data-testid="danger-zone-error">{errorMsg}</p>
		{/if}
	</section>
</main>

<ConfirmDialog
	open={archiveDialogOpen}
	title={status === 'archived' ? 'Trip reaktivieren?' : 'Trip archivieren?'}
	description={status === 'archived'
		? 'Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv.'
		: 'Der Trip wird ins Archiv verschoben — er kann später reaktiviert werden.'}
	confirmLabel="Bestätigen"
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
	.danger-zone {
		margin-top: 2.5rem;
		padding: 1.25rem 0 1.5rem;
		border-top: 1px solid var(--g-ink-faint);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.danger-zone-actions {
		display: flex;
		gap: 1rem;
		justify-content: space-between;
		flex-wrap: wrap;
	}
	.danger-zone-left {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.danger-zone-right {
		display: flex;
	}
	.danger-zone-error {
		margin: 0;
		font-size: 0.875rem;
		color: var(--g-danger, #b34a2a);
	}
</style>
