<script lang="ts">
	// EditStagesPanelNew — Tab-Inhalt "Etappen & Wegpunkte" (Issue #503).
	// Spec: docs/specs/modules/issue_503_etappen_waypoints.md (Option B von Claude Design)
	//
	// Architektur: Karte + Höhenprofil + Wegpunkt-Sidebar als Tab-Inhalt (kein eigener
	// Screen, keine 6. Tab-Position). Page-Chrome (Speichern/Abbrechen) liegt in
	// TripEditView; dieses Panel kümmert sich nur um den Editor-Kern.
	//
	// Wichtige Änderungen ggü. #296-FE:
	//   - MapCanvas (Leaflet/OpenTopoMap) ist eingebunden
	//   - Layout: grid 1fr / 360px (links Karte+Profil-Cards, rechts Wegpunkte)
	//   - KI/Auto/Manuell-Unterscheidung entfernt — alle Wegpunkte gleichwertig
	//   - ProfileEditor.onProfileAdd fügt einen Wegpunkt ohne KI-Markierung ein

	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import MapCanvas from '$lib/components/trip-detail/waypoints/MapCanvas.svelte';
	import ProfileEditor from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import PauseStageView from '$lib/components/trip-detail/waypoints/PauseStageView.svelte';
	import MapControl from './MapControl.svelte';
	import ProfileSheetEmbedded from './ProfileSheetEmbedded.svelte';
	import StageSelectSheet from './StageSelectSheet.svelte';
	import StageDateField from './StageDateField.svelte';
	import { addDays, computeCascadeDelta } from './cascade.ts';
	import { Eyebrow, Btn, Dot, Pill } from '$lib/components/atoms';
	import { computeArrivalTimes } from '$lib/utils/naismith';
	import { interpolateWaypoint } from '$lib/utils/waypointEditor';
	import type { Stage, Waypoint } from '$lib/types';
	import { api } from '$lib/api.js';

	interface Props {
		stages: Stage[];
		tripId?: string;
		showSave?: boolean;
	}
	let { stages = $bindable(), tripId, showSave = true }: Props = $props();

	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);
	let addModeHint = $state(false);
	let mobileSnap = $state<'peek' | 'half' | 'full'>('half');
	let mobileSizeKey = $state(0);
	let stageSheetOpen = $state(false);

	async function save(): Promise<void> {
		if (!tripId) return;
		saving = true;
		saveError = null;
		try {
			await api.put(`/api/trips/${tripId}`, { stages: stages });
			saveSuccess = true;
			setTimeout(() => { saveSuccess = false; }, 3000);
		} catch (e: unknown) {
			saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	// Pausentag = Etappe ohne Wegpunkte (Spec-Definition §5/AC-10).
	const isPause = (s: Stage): boolean => s.waypoints.length === 0;

	let activeStageId = $state<string>(
		stages.find((s) => !isPause(s))?.id ?? stages[0]?.id ?? ''
	);
	let activeWaypointId = $state<string | null>(null);

	const activeStage = $derived(stages.find((s) => s.id === activeStageId) ?? null);
	const activeIsPause = $derived(activeStage ? isPause(activeStage) : false);
	const activeStageIndex = $derived(stages.findIndex((s) => s.id === activeStageId));
	const prevStage = $derived(activeStageIndex > 0 ? stages[activeStageIndex - 1] : null);
	const nextStage = $derived(
		activeStageIndex >= 0 && activeStageIndex < stages.length - 1
			? stages[activeStageIndex + 1]
			: null
	);
	const arrivals = $derived(
		activeStage ? computeArrivalTimes(activeStage, activeStage.start_time) : []
	);

	const newId = (): string => crypto.randomUUID().slice(0, 8);

	// Issue #498 — Kaskaden-Strip: bei Tourstart-Verschiebung Folge-Etappen mitnehmen?
	interface CascadeState {
		days: number;
		count: number;
		done: boolean;
	}
	let cascade = $state<CascadeState | null>(null);

	function handleDateChange(stageId: string, newDate: string): void {
		const idx = stages.findIndex((s) => s.id === stageId);
		if (idx < 0) return;
		const oldDate = stages[idx].date;

		// Datum + dateOverridden-Flag setzen, ohne andere Stages anzufassen.
		stages = stages.map((s, i) =>
			i === idx ? { ...s, date: newDate, dateOverridden: true } : s,
		);

		// Kaskaden-Vorschlag nur bei erster Etappe und gültigem altem Datum.
		if (idx === 0 && oldDate) {
			const delta = computeCascadeDelta(oldDate, newDate);
			if (delta !== 0 && stages.length > 1) {
				cascade = { days: delta, count: stages.length - 1, done: false };
			} else {
				cascade = null; // F001: stalen Cascade zurücksetzen wenn delta=0
			}
		}
	}

	function applyCascade(): void {
		if (!cascade || cascade.done) return;
		const days = cascade.days;
		stages = stages.map((s, i) => {
			if (i === 0) return s;
			if (!s.date) return s;
			return { ...s, date: addDays(s.date, days), dateOverridden: true };
		});
		cascade = { ...cascade, done: true };
	}

	function dismissCascade(): void {
		cascade = null;
	}

	// EtappenStrip-Handler
	function handleStagesReorder(reordered: Stage[]): void {
		stages = reordered;
	}
	function handleStageActivate(stageId: string): void {
		if (stageId === activeStageId) return;
		activeStageId = stageId;
		activeWaypointId = null;
		addModeHint = false;
	}
	function handlePauseInsert(afterIndex: number): void {
		const newPause: Stage = { id: newId(), name: 'Pausentag', date: '', waypoints: [] };
		const updated = [...stages];
		updated.splice(afterIndex + 1, 0, newPause);
		stages = updated;
	}

	// Profil-Klick → interpolierten Wegpunkt einfügen.
	// Issue #503: KEIN suggested-Flag mehr — alle Wegpunkte sind gleichwertig.
	function handleProfileAdd(fraction: number): void {
		if (!activeStage) return;
		const { lat, lon, elevation_m, insertAfterIndex } = interpolateWaypoint(
			activeStage.waypoints,
			fraction
		);
		const newWp: Waypoint = {
			id: newId(),
			name: 'Neuer Punkt',
			lat,
			lon,
			elevation_m
		};
		stages = stages.map((s) => {
			if (s.id !== activeStage.id) return s;
			const wps = [...s.waypoints];
			wps.splice(insertAfterIndex + 1, 0, newWp);
			return { ...s, waypoints: wps };
		});
		activeWaypointId = newWp.id;
		addModeHint = false;
	}

	function handleWaypointActivate(waypointId: string): void {
		activeWaypointId = waypointId;
	}

	function handleMapClick(lat: number, lon: number): void {
		if (!activeStage || activeIsPause) return;
		const stage = activeStage;
		const newWp: Waypoint = { id: newId(), name: '', lat, lon, elevation_m: 0 };
		stages = stages.map((s) =>
			s.id !== stage.id ? s : { ...s, waypoints: [...s.waypoints, newWp] }
		);
		activeWaypointId = newWp.id;
	}

	// Waypoint-Mutations (Factory-Pattern fuer WaypointCard-Callbacks).
	// Issue #503: nur noch Umbenennen + Löschen — kein Confirm/Reject mehr.
	function makeActivateHandler(waypointId: string) {
		return function handleActivate() {
			activeWaypointId = waypointId;
		};
	}
	function makeRenameHandler(stageId: string, waypointId: string) {
		return function handleRename() {
			const newName = prompt('Neuer Name:');
			if (!newName) return;
			stages = stages.map((s) =>
				s.id !== stageId
					? s
					: {
							...s,
							waypoints: s.waypoints.map((w) => (w.id !== waypointId ? w : { ...w, name: newName }))
						}
			);
		};
	}
	function makeDeleteHandler(stageId: string, waypointId: string) {
		return function handleDelete() {
			stages = stages.map((s) =>
				s.id !== stageId ? s : { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
</script>

<div data-testid="edit-stages-panel" class="flex flex-col gap-4">
	<!-- EtappenStrip (volle Breite, eigene Navigations-Achse) -->
	<EtappenStrip
		{stages}
		{activeStageId}
		onStagesReorder={handleStagesReorder}
		onStageActivate={handleStageActivate}
		onPauseInsert={handlePauseInsert}
	/>

	{#if activeStage}
		{#if activeIsPause}
			<PauseStageView
				stage={activeStage}
				{prevStage}
				{nextStage}
				onDateChange={(newDate) => handleDateChange(activeStage!.id, newDate)}
			/>
		{:else}
			<!-- Etappen-Header mit editierbarem Datum (Issue #498) -->
			<div class="flex items-start justify-between gap-8">
				<div class="min-w-0 flex-1">
					<Eyebrow>Etappe</Eyebrow>
					<p class="truncate text-lg font-semibold">{activeStage.name}</p>
				</div>
				<StageDateField
					value={activeStage.date}
					isFirst={activeStageIndex === 0}
					onchange={(newDate) => handleDateChange(activeStage!.id, newDate)}
				/>
			</div>

			{#if cascade && activeStageIndex === 0}
				{#if !cascade.done}
					<div class="cascade-prompt" data-testid="cascade-strip">
						<p>
							<strong
								>Tourstart um {cascade.days > 0 ? '+' : ''}{cascade.days}
								{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} verschoben.</strong
							>
							Sollen die {cascade.count} Folge-Etappen um denselben Betrag mitverschoben werden?
						</p>
						<div class="cascade-actions">
							<Btn variant="accent" size="sm" onclick={applyCascade}>Alle mitverschieben</Btn>
							<Btn variant="outline" size="sm" onclick={dismissCascade}>Nur diese Etappe</Btn>
						</div>
					</div>
				{:else}
					<div class="cascade-done" data-testid="cascade-done">
						<Dot tone="success" />
						<span>
							<strong>{cascade.count} Folge-Etappen verschoben</strong> · alle Daten um
							{cascade.days > 0 ? '+' : ''}{cascade.days}
							{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} angepasst.
						</span>
						<Btn variant="ghost" size="sm" onclick={dismissCascade}>Schließen</Btn>
					</div>
				{/if}
			{/if}

			<!-- Issue #542: Mobile-Editor (@media max-width: 899px) -->
			<div class="mobile-editor" data-testid="mobile-editor">
				<div class="mobile-map-wrap" style="position:relative;width:100%;height:calc(100dvh - 56px)">
					<MapCanvas
						stage={activeStage}
						{activeWaypointId}
						onWaypointActivate={handleWaypointActivate}
						onMapClick={handleMapClick}
						sizeKey={mobileSizeKey}
					/>
					<!-- EtappenSwitcher-Pill oben links (AC-3/AC-4) -->
					<button
						type="button"
						class="stage-switcher-pill"
						data-testid="stage-switcher-pill"
						onclick={() => { stageSheetOpen = true; }}
					>
						{activeStageIndex + 1} / {stages.length} · {activeStage.name}
					</button>
					{#if !activeIsPause}
						<MapControl onAddWaypoint={() => { addModeHint = true; }} />
					{/if}
				</div>
				<ProfileSheetEmbedded
					stage={activeStage}
					{activeWaypointId}
					snapPosition={mobileSnap}
					onWaypointActivate={handleWaypointActivate}
					onProfileAdd={handleProfileAdd}
					onSnapChange={(snap) => { mobileSnap = snap; mobileSizeKey++; }}
				/>
				{#if stageSheetOpen}
					<StageSelectSheet
						{stages}
						activeIndex={activeStageIndex}
						open={true}
						onSelect={(i) => { handleStageActivate(stages[i].id); stageSheetOpen = false; }}
						onClose={() => { stageSheetOpen = false; }}
					/>
				{/if}
			</div>

			<!-- Issue #503: Grid 1fr / 360px — Karte+Profil links, Wegpunkte rechts -->
			<div class="editor-grid" data-testid="editor-grid">
				<!-- Linke Spalte: Karte-Card + Profil-Card -->
				<div class="editor-left">
					<!-- Karten-Card (Leaflet/OpenTopoMap) -->
					<div class="editor-card" data-testid="map-card">
						<div class="editor-card-header">
							<Eyebrow>Karte · OpenTopoMap (OSM + SRTM)</Eyebrow>
							<Pill tone="ghost">Topo</Pill>
						</div>
						<MapCanvas
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
						/>
					</div>

					{#if addModeHint}
						<div class="add-mode-hint" role="status" data-testid="add-mode-hint">
							<span>Klicke im Höhenprofil, um einen Wegpunkt einzufügen</span>
							<button class="add-mode-hint-close" aria-label="Hinweis schließen" onclick={() => { addModeHint = false; }}>×</button>
						</div>
					{/if}

					<!-- Profil-Card (Höhenprofil) -->
					<div class="editor-card editor-card--padded" data-testid="profile-card">
						<div class="editor-card-header editor-card-header--inline">
							<Eyebrow>Höhenprofil · synchron mit Karte</Eyebrow>
						</div>
						<ProfileEditor
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
							onProfileAdd={handleProfileAdd}
						/>
					</div>
				</div>

				<!-- Rechte Spalte: Wegpunkt-Sidebar-Card -->
				<div class="editor-card editor-sidebar" data-testid="waypoint-sidebar">
					<div class="editor-card-header sidebar-header">
						<div>
							<Eyebrow>Wegpunkte</Eyebrow>
							<div class="sidebar-count">{activeStage.waypoints.length} insgesamt</div>
						</div>
						<Btn variant="ghost" size="sm" data-testid="waypoint-add-on-route-btn" onclick={() => { addModeHint = true; }}>
							+ auf Route
						</Btn>
					</div>
					<div class="sidebar-list">
						{#each activeStage.waypoints as waypoint, i (waypoint.id)}
							<WaypointCard
								{waypoint}
								index={i}
								active={waypoint.id === activeWaypointId}
								arrival={arrivals[i] ?? null}
								onActivate={makeActivateHandler(waypoint.id)}
								onRename={makeRenameHandler(activeStage.id, waypoint.id)}
								onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
							/>
						{/each}
						{#if activeStage.waypoints.length === 0}
							<p class="sidebar-empty">Keine Wegpunkte.</p>
						{/if}
					</div>
				</div>
			</div>
		{/if}
	{/if}

	{#if showSave}
		<div class="save-bar">
			<Btn variant="primary" size="sm" onclick={save} disabled={saving || !tripId}>
				{saving ? 'Speichern …' : 'Etappen speichern'}
			</Btn>
			{#if saveSuccess}<span class="save-ok">Gespeichert ✓</span>{/if}
			{#if saveError}<span class="save-err">{saveError}</span>{/if}
		</div>
	{/if}
</div>

<style>
	/* Issue #498 — Cascade-Strip (Tourstart-Verschiebung Folge-Etappen?) */
	.cascade-prompt,
	.cascade-done {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px;
		background: var(--g-accent-tint);
		border: 1px solid var(--g-rule);
		border-left: 3px solid var(--g-accent-deep);
		border-radius: 4px;
		font-size: 13px;
		color: var(--g-ink);
	}
	.cascade-prompt p {
		flex: 1;
		margin: 0;
	}
	.cascade-actions {
		display: flex;
		gap: 6px;
		flex-shrink: 0;
	}
	.cascade-done span {
		flex: 1;
	}

	/* Issue #503 — Grid-Layout: Karte+Profil links (1fr), Wegpunkte rechts (360px). */
	.editor-grid {
		display: grid;
		grid-template-columns: 1fr 360px;
		gap: 24px;
		align-items: start;
	}
	.editor-left {
		display: flex;
		flex-direction: column;
		gap: 16px;
		min-width: 0;
	}

	/* Issue #503 — Karten-/Profil-/Wegpunkt-Cards (weiße Surface, hoher Kontrast). */
	.editor-card {
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md, 6px);
		overflow: hidden;
		box-shadow: var(--g-shadow-1, 0 1px 3px rgba(0, 0, 0, 0.08));
	}
	.editor-card--padded {
		padding-bottom: 8px;
	}
	.editor-card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 18px;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.editor-card-header--inline {
		border-bottom: none;
		padding-bottom: 4px;
	}

	.editor-sidebar {
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.sidebar-header {
		gap: 12px;
	}
	.sidebar-count {
		font-size: 14px;
		font-weight: 600;
		color: var(--g-ink);
		margin-top: 2px;
	}
	.sidebar-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 4px 6px 8px;
		overflow-y: auto;
	}
	.sidebar-empty {
		padding: 14px;
		font-size: var(--g-text-sm, 13px);
		color: var(--g-ink-muted);
		margin: 0;
	}

	/* Issue #542: Mobile-Editor — Vollbild-Karte + Bottom-Sheet */
	.mobile-editor {
		display: none;
	}

	.stage-switcher-pill {
		position: absolute;
		top: 12px;
		left: 12px;
		z-index: 20;
		padding: 6px 14px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: 20px;
		box-shadow: var(--g-shadow-2, 0 2px 6px rgba(26, 26, 24, 0.12));
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink);
		cursor: pointer;
		white-space: nowrap;
		font-family: var(--g-font-mono, 'JetBrains Mono', monospace);
	}

	/* Mobile: zeige Mobile-Editor, verstecke Desktop-Grid */
	@media (max-width: 899px) {
		.mobile-editor {
			display: block;
		}
		.editor-grid {
			display: none;
		}
	}
	.save-bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-top: 0.5rem;
	}
	.save-ok {
		font-size: 0.875rem;
		color: var(--g-success);
	}
	.save-err {
		font-size: 0.875rem;
		color: var(--g-danger, #b34a2a);
	}

	/* Bug #524 — Info-Strip „+ auf Route" Klick-Hinweis */
	.add-mode-hint {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 12px;
		background: var(--g-surface-2, #f0ede8);
		border-left: 3px solid var(--g-accent);
		font-size: 13px;
		color: var(--g-ink-2);
		margin-bottom: 4px;
		border-radius: 3px;
	}
	.add-mode-hint-close {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 16px;
		line-height: 1;
		color: var(--g-ink-3);
		padding: 0 4px;
	}
</style>
