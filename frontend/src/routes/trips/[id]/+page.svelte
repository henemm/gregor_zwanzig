<script lang="ts">
	// Issue #302 — Danger-Zone unter den Tabs (Spec §6).
	// Pause/Archive/Delete-Logik ist aus TripHeader hierhergewandert; Headerbuttons
	// (Briefing-Vorschau, Bearbeiten, Test-Briefing) leben in der neuen Header-Komponente.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { TripHeader, TripTabs } from '$lib/components/trip-detail';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import type { Trip } from '$lib/types';

	let { data } = $props();

	// Trip in lokales $state heben, damit Status-Updates (Pause/Archive)
	// reaktiv ohne Page-Reload sichtbar werden.
	let trip = $state<Trip>(data.trip);

	// Initial-Tab aus URL-Hash. $derived bleibt reaktiv falls user navigation triggert.
	const initialTab = $derived((page.url.hash || '').replace(/^#/, '') || 'overview');

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

<Dialog.Root open={archiveDialogOpen} onOpenChange={handleArchiveDialogOpenChange}>
	<Dialog.Content data-testid="trip-detail-archive-confirm-dialog">
		<Dialog.Header>
			<Dialog.Title>
				{status === 'archived' ? 'Trip reaktivieren?' : 'Trip archivieren?'}
			</Dialog.Title>
			<Dialog.Description>
				{status === 'archived'
					? 'Der Trip wird aus dem Archiv zurückgeholt und ist wieder aktiv.'
					: 'Der Trip wird ins Archiv verschoben — er kann später reaktiviert werden.'}
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn
				variant="outline"
				data-testid="trip-detail-archive-confirm-cancel"
				onclick={handleArchiveCancel}
			>
				Abbrechen
			</Btn>
			<Btn
				variant="primary"
				data-testid="trip-detail-archive-confirm-yes"
				onclick={handleArchiveConfirm}
				disabled={isLoading}
			>
				Bestätigen
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root open={deleteDialogOpen} onOpenChange={handleDeleteDialogOpenChange}>
	<Dialog.Content data-testid="trip-detail-delete-confirm-dialog">
		<Dialog.Header>
			<Dialog.Title>Trip endgültig löschen?</Dialog.Title>
			<Dialog.Description>
				Dieser Schritt löscht den Trip dauerhaft und kann nicht rückgängig gemacht werden.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn
				variant="outline"
				data-testid="trip-detail-delete-confirm-cancel"
				onclick={handleDeleteCancel}
			>
				Abbrechen
			</Btn>
			<Btn
				variant="destructive"
				data-testid="trip-detail-delete-confirm-yes"
				onclick={handleDeleteConfirm}
				disabled={isLoading}
			>
				Löschen
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

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
