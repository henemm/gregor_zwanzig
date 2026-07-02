<script lang="ts">
	// Issue #611 — Archiv: reines Archiv für Trips UND Orts-Vergleiche.
	//
	// Kanonische Design-Quelle (1:1 inline styles): screen-archive.jsx
	// (claude-code-handoff/current/jsx/screen-archive.jsx). Genau zwei Aktionen
	// pro Eintrag: »Wieder aktivieren« und »Löschen«. Keine Forecast-Analytik.
	//
	// Spec: docs/specs/modules/issue_611_archiv_entruempeln.md

	import type { PageData } from './$types.js';
	import type { ArchiveEntry } from './+page.server.js';
	import { invalidateAll } from '$app/navigation';
	import { Card, Eyebrow, Btn } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';

	let { data }: { data: PageData } = $props();

	const TYPE_LABEL: Record<ArchiveEntry['type'], string> = { trip: 'Trip', compare: 'Vergleich' };

	let query = $state('');
	let filter = $state<'all' | 'trip' | 'compare'>('all');
	let deleteTarget: ArchiveEntry | null = $state(null);
	let busyId = $state<string | null>(null);
	let error: string | null = $state(null);

	const entries = $derived(data.entries as ArchiveEntry[]);

	const filtered = $derived(
		entries
			.filter((t) => filter === 'all' || t.type === filter)
			.filter((t) => t.name.toLowerCase().includes(query.toLowerCase()))
			.sort((a, b) => b.archived.localeCompare(a.archived))
	);

	const nTrips = $derived(entries.filter((t) => t.type === 'trip').length);
	const nCompares = $derived(entries.filter((t) => t.type === 'compare').length);
	const chips = $derived([
		{ id: 'all' as const, label: 'Alle', n: entries.length },
		{ id: 'trip' as const, label: 'Trips', n: nTrips },
		{ id: 'compare' as const, label: 'Vergleiche', n: nCompares }
	]);

	// Factory-Pattern für Button-Handler (Safari-Kompatibilität).
	function makeReactivate(item: ArchiveEntry) {
		return async () => {
			error = null;
			busyId = item.id;
			const url =
				item.type === 'trip'
					? `/api/trips/${item.id}/state`
					: `/api/compare/presets/${item.id}/state`;
			try {
				const res = await fetch(url, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ archived: false })
				});
				if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
				await invalidateAll();
			} catch (e: unknown) {
				error = (e as Error).message ?? 'Fehler beim Reaktivieren';
			} finally {
				busyId = null;
			}
		};
	}

	function makeDelete(item: ArchiveEntry) {
		return () => {
			deleteTarget = item;
		};
	}

	async function confirmDelete() {
		if (!deleteTarget) return;
		const item = deleteTarget;
		error = null;
		busyId = item.id;
		const url = item.type === 'trip' ? `/api/trips/${item.id}` : `/api/compare/presets/${item.id}`;
		try {
			const res = await fetch(url, { method: 'DELETE' });
			if (!res.ok) throw new Error(`DELETE failed: ${res.status}`);
			deleteTarget = null;
			await invalidateAll();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Löschen';
			deleteTarget = null;
		} finally {
			busyId = null;
		}
	}
</script>

<main style="flex:1;padding:32px 40px;overflow:auto">
	<!-- Header -->
	<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px">
		<div>
			<Eyebrow>Workspace · Archiv</Eyebrow>
			<div style="font-size:32px;font-weight:600;letter-spacing:-0.025em;margin-top:4px">Archiv</div>
			<div
				style="font-size:14px;color:var(--g-ink-3);margin-top:6px;max-width:620px;line-height:1.5"
			>
				Abgelegte Trips und Orts-Vergleiche. Trips wandern nach ihrem Enddatum automatisch
				hierher. Jeden Eintrag kannst du wieder aktivieren oder endgültig löschen.
			</div>
		</div>
	</div>

	{#if error}
		<p style="font-size:13px;color:var(--g-bad, #a83232);margin-bottom:16px">{error}</p>
	{/if}

	<!-- Suche + Typ-Filter (umbruchfähig — auf Mobile sonst unerreichbar, s. Mobile-Audit 2026-07-02) -->
	<div style="display:flex;gap:12px 16px;align-items:center;margin-bottom:20px;flex-wrap:wrap">
		<div style="position:relative;flex:1 1 240px;max-width:380px">
			<svg
				width="14"
				height="14"
				viewBox="0 0 24 24"
				fill="none"
				stroke="var(--g-ink-4)"
				stroke-width="2"
				style="position:absolute;top:11px;left:12px"
			>
				<circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
			</svg>
			<input
				bind:value={query}
				placeholder="Suchen…"
				style="width:100%;padding:9px 14px 9px 34px;border:1px solid var(--g-rule);border-radius:var(--g-r-pill);background:var(--g-card);font-family:var(--g-font-sans);color:var(--g-ink);outline:none"
			/>
		</div>
		<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
			{#each chips as c (c.id)}
				{@const active = filter === c.id}
				<button
					onclick={() => (filter = c.id)}
					style="display:inline-flex;align-items:center;gap:7px;padding:7px 12px;min-height:34px;background:{active
						? 'var(--g-ink)'
						: 'var(--g-card)'};color:{active
						? 'var(--g-paper)'
						: 'var(--g-ink-2)'};border:1px solid {active
						? 'var(--g-ink)'
						: 'var(--g-rule)'};border-radius:var(--g-r-pill);cursor:pointer;font-family:var(--g-font-mono);font-size:12px;font-weight:500;letter-spacing:0.02em"
				>
					{c.label}
					<span
						style="font-size:10px;padding:1px 6px;border-radius:8px;background:{active
							? 'rgba(255,255,255,0.18)'
							: 'var(--g-paper-deep)'};color:{active ? 'var(--g-paper)' : 'var(--g-ink-3)'}"
						>{c.n}</span
					>
				</button>
			{/each}
		</div>
	</div>

	<!-- Tabelle — auf Mobile horizontal wischbar (Design-Pattern B: H-Scroll statt gequetschter Spalten) -->
	<Card padding={0} style="overflow:hidden">
		<div style="overflow-x:auto">
			<div style="min-width:640px">
				<div
					style="display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:0;padding:12px 20px;background:var(--g-paper-deep);font-size:11px;font-family:var(--g-font-mono);letter-spacing:0.18em;text-transform:uppercase;color:var(--g-ink-3);font-weight:500;border-bottom:1px solid var(--g-rule)"
				>
					<div>Name</div>
					<div>Umfang</div>
					<div>Archiviert</div>
					<div style="text-align:right">Aktionen</div>
				</div>

				{#each filtered as item, i (item.id)}
					{@render archiveRow(item, i % 2 === 1)}
				{/each}
			</div>
		</div>

		{#if filtered.length === 0}
			<div style="padding:40px;text-align:center;color:var(--g-ink-3);font-size:13px">
				{#if query}
					Keine archivierten Einträge für »{query}« gefunden.
				{:else}
					Keine archivierten Einträge.
				{/if}
			</div>
		{/if}
	</Card>

	<!-- Footer-Zähler -->
	<div
		style="margin-top:14px;font-size:11px;color:var(--g-ink-4);font-family:var(--g-font-mono);letter-spacing:0.06em"
	>
		{filtered.length} von {entries.length} Einträgen · Trips auto-archiviert nach Trip-Ende
	</div>
</main>

<ConfirmDialog
	open={deleteTarget !== null}
	title="Endgültig löschen?"
	description={'"' + (deleteTarget?.name ?? '') + '" wird unwiderruflich gelöscht.'}
	confirmLabel="Löschen"
	confirmVariant="destructive"
	onConfirm={confirmDelete}
	onCancel={() => (deleteTarget = null)}
	onOpenChange={(o) => {
		if (!o) deleteTarget = null;
	}}
/>

<!-- ArchiveRow: Tabellenzeile, 4-Spalten-Grid wie Kopfzeile (screen-archive.jsx). -->
{#snippet archiveRow(item: ArchiveEntry, alt: boolean)}
	{@const isCompare = item.type === 'compare'}
	{@const dot = isCompare ? '#3d6b3a' : 'var(--g-ink-4)'}
	<div
		style="display:grid;grid-template-columns:2fr 1fr 1fr auto;align-items:center;padding:16px 20px;background:{alt
			? 'var(--g-paper-deep)'
			: 'transparent'};border-bottom:1px solid var(--g-rule-soft);gap:0"
	>
		<div style="display:flex;align-items:center;gap:10px;min-width:0">
			<span style="width:7px;height:7px;border-radius:50%;background:{dot};flex-shrink:0"></span>
			<span
				style="font-size:14px;font-weight:600;letter-spacing:-0.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
				>{item.name}</span
			>
			<span
				style="font-size:9.5px;font-family:var(--g-font-mono);letter-spacing:0.14em;text-transform:uppercase;color:{isCompare
					? '#3d6b3a'
					: 'var(--g-ink-3)'};border:1px solid {isCompare
					? 'rgba(61,107,58,0.35)'
					: 'var(--g-rule)'};border-radius:var(--g-r-pill);padding:2px 8px;flex-shrink:0"
				>{TYPE_LABEL[item.type]}</span
			>
		</div>
		<div style="font-size:13px;color:var(--g-ink-2);font-variant-numeric:tabular-nums">
			{item.detail}
		</div>
		<div
			style="font-size:13px;color:var(--g-ink-2);font-family:var(--g-font-mono);letter-spacing:0.02em"
		>
			{item.archived}
		</div>
		<div style="display:flex;gap:8px;justify-content:flex-end;align-items:center">
			<Btn variant="ghost" size="sm" onclick={makeReactivate(item)} disabled={busyId === item.id}>
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="var(--g-ink)"
					stroke-width="1.7"
					stroke-linecap="round"
					stroke-linejoin="round"
				>
					<path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" />
				</svg>
				Wieder aktivieren
			</Btn>
			<button
				title="Endgültig löschen"
				onclick={makeDelete(item)}
				disabled={busyId === item.id}
				style="display:inline-flex;align-items:center;gap:6px;padding:6px 10px;min-height:30px;background:transparent;border:1px solid var(--g-rule);border-radius:var(--g-r-2);cursor:pointer;font-size:12px;font-weight:500;font-family:var(--g-font-sans);color:var(--g-bad, #a83232)"
			>
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="var(--g-bad, #a83232)"
					stroke-width="1.7"
					stroke-linecap="round"
					stroke-linejoin="round"
				>
					<path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" />
				</svg>
				Löschen
			</button>
		</div>
	</div>
{/snippet}
