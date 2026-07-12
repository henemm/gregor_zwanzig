<script lang="ts">
	// CorridorEditor.svelte — Issue #1231, Slice 3: Port aus
	// claude-code-handoff/current/jsx/corridor-editor.jsx (CorridorEditor +
	// CorridorRow/CorridorBand/CorridorBound/CorridorEffect), context="route".
	// Ersetzt AlertsTab.svelte + AlertMetricLevelTable.svelte im Trip-Editor.
	//
	// Band-Drag (Pointer-Capture, Port aus JSX-Zeilen 107-179): testbarer Kern
	// (Pointer->Wert, Clamping) liegt in corridorEditorState.ts, hier nur die
	// duenne DOM-Event-Verdrahtung (PO-Vorgabe: Geste muss funktionieren).
	import { Eyebrow } from '$lib/components/atoms';
	import { api } from '$lib/api';
	import type { Trip, SensLevel } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import {
		buildRoutePool, addRow, removeRow, patchRow, validateCorridorRows,
		buildCorridorSavePayload, ROUTE_CTX_DEFAULTS, valueAtPointer, clampDragValue, clampBoundInput,
		type CorridorRowState,
	} from './corridorEditorState.ts';

	interface Props {
		trip: Trip;
		onTripUpdate?: (t: Trip) => void;
		saveController?: SaveStatus;
	}
	let { trip, onTripUpdate, saveController }: Props = $props();

	// AC-10: "zuletzt bekannte Stufe" bezieht sich auf den beim Mount geladenen
	// Stand, nicht auf einen laufenden Zwischenstand dieser Session.
	const originalLevels = (trip.display_config?.metric_alert_levels ?? {}) as Record<string, SensLevel>;

	const initial = buildRoutePool(trip.corridors ?? []);
	let rows = $state<CorridorRowState[]>(initial.rows);
	let poolLeft = $state(initial.poolLeft);
	// F002-Fix (Adversary HIGH): Metriken, die per "✕ entfernen" aus rows
	// verschwunden sind — buildCorridorSavePayload setzt deren Level explizit
	// auf "off", sonst warnt der Δ-Wächter unsichtbar mit der alten Stufe weiter.
	let removedMetrics = $state<string[]>([]);

	const validation = $derived(validateCorridorRows(rows));
	const notifyN = $derived(rows.filter((r) => r.notify).length);
	const markN = $derived(rows.filter((r) => r.mark).length);

	function buildSaveFn() {
		const payload = buildCorridorSavePayload(rows, originalLevels, removedMetrics);
		return async () => {
			const updated = await api.put<Trip>(`/api/trips/${trip.id}`, {
				corridors: payload.corridors,
				display_config: { ...trip.display_config, metric_alert_levels: payload.metric_alert_levels },
			});
			onTripUpdate?.(updated);
		};
	}

	// F001-Fix (Adversary HIGH): bei AC-12-Verletzung gar nicht schedulen —
	// saveController.doSave() ruft nach jedem Save unbedingt setSaved() auf,
	// ein No-op-Save haette faelschlich "Gespeichert ✓" gezeigt.
	function maybeSchedule() {
		if (validateCorridorRows(rows).valid) saveController?.schedule(buildSaveFn());
	}

	function patch(metric: string, p: Partial<Pick<CorridorRowState, 'min' | 'max' | 'notify' | 'mark'>>) {
		rows = patchRow(rows, metric, p);
		maybeSchedule();
	}
	function remove(metric: string) {
		rows = removeRow(rows, metric);
		removedMetrics = [...removedMetrics, metric];
		maybeSchedule();
	}
	function add(metric: string) {
		const next = addRow(rows, poolLeft, metric, ROUTE_CTX_DEFAULTS);
		rows = next.rows;
		poolLeft = next.poolLeft;
		maybeSchedule();
	}
	function numOrNull(v: string): number | null {
		return v === '' ? null : Number(v);
	}

	// Dual-Handle-Drag: dünne DOM-Verdrahtung, Wertelogik in valueAtPointer/clampDragValue.
	let dragging = $state<{ metric: string; side: 'min' | 'max'; track: HTMLElement } | null>(null);
	function onHandleDown(e: PointerEvent, metric: string, side: 'min' | 'max') {
		const track = (e.currentTarget as HTMLElement).closest('.ce-band-track') as HTMLElement | null;
		if (track) dragging = { metric, side, track };
	}
	function onWindowPointerMove(e: PointerEvent) {
		if (!dragging) return;
		const row = rows.find((r) => r.metric === dragging!.metric);
		if (!row) return;
		const rect = dragging.track.getBoundingClientRect();
		const raw = valueAtPointer(e.clientX, rect.left, rect.width, row.scale, row.step);
		const value = clampDragValue(dragging.side, raw, row.min, row.max);
		patch(row.metric, dragging.side === 'min' ? { min: value } : { max: value });
	}
	function onWindowPointerUp() {
		dragging = null;
	}
</script>

<svelte:window onpointermove={onWindowPointerMove} onpointerup={onWindowPointerUp} />

<div class="corridor-editor" data-testid="corridor-editor-route">
	<Eyebrow>Wertebereiche · Warn-Schwellen</Eyebrow>
	<h2 class="ce-h2">Sag mir, wenn das Wetter aus dem Rahmen läuft</h2>
	<p class="ce-lead">
		Ein Wertebereich je Metrik legt fest, welche Werte du auf der Tour noch akzeptierst. Verlässt
		ein Wert den Bereich, bekommst du zwischen den Briefings eine Sofort-Meldung.
	</p>

	<div class="ce-legend">
		<span class="ce-legend-title">So liest sich ein Wertebereich</span>
		<span class="ce-legend-item"><span class="ce-swatch mark"></span> im Bereich = <strong class="ce-good">markiert</strong></span>
		<span class="ce-legend-item"><span class="ce-swatch warn"></span> außerhalb = <strong class="ce-warn">Warnung</strong></span>
		<span class="ce-legend-note">Beide Wirkungen je Metrik frei kombinierbar.</span>
	</div>

	{#if !validation.valid}
		<p class="ce-error" role="alert" data-testid="corridor-editor-error">
			Mindestens eine Grenze (Von oder Bis) ist Pflicht: {validation.errors.join(', ')}
		</p>
	{/if}

	<div class="ce-table" data-testid="corridor-editor-table">
		{#each rows as row (row.metric)}
			{@const span = row.scale[1] - row.scale[0] || 1}
			{@const leftPct = row.min == null ? 0 : Math.max(0, Math.min(1, (row.min - row.scale[0]) / span)) * 100}
			{@const rightPct = row.max == null ? 100 : Math.max(0, Math.min(1, (row.max - row.scale[0]) / span)) * 100}
			<div class="ce-row" data-testid="corridor-row-{row.metric}">
				<div class="ce-info">
					<span class="ce-label">{row.label}</span>
					<span class="ce-unit">{row.unit}</span>
					{#if row.note}<div class="ce-note">{row.note}</div>{/if}
				</div>
				<div class="ce-band-col">
					<div class="ce-band-track">
						<div class="ce-band-fill" class:mark={row.mark} style="left:{leftPct}%;width:{rightPct - leftPct}%"></div>
						{#if row.min == null}<span class="ce-open ce-open-left">◂ offen</span>{/if}
						{#if row.max == null}<span class="ce-open ce-open-right">offen ▸</span>{/if}
						{#if row.min != null}
							<div class="ce-handle" style="left:{leftPct}%" onpointerdown={(e) => onHandleDown(e, row.metric, 'min')}></div>
						{/if}
						{#if row.max != null}
							<div class="ce-handle" class:mark={row.mark} style="left:{rightPct}%" onpointerdown={(e) => onHandleDown(e, row.metric, 'max')}></div>
						{/if}
					</div>
					<div class="ce-bounds">
						<label class="ce-bound">Von
							{#if row.min == null}
								<button type="button" class="ce-open-btn" onclick={() => patch(row.metric, { min: row.scale[0] })}>offen · + Grenze</button>
							{:else}
								<input type="number" step={row.step} value={row.min} oninput={(e) => patch(row.metric, { min: clampBoundInput(numOrNull(e.currentTarget.value), 'min', row) })} />
								<button type="button" class="ce-clear-btn" title="Grenze öffnen" onclick={() => patch(row.metric, { min: null })}>×</button>
							{/if}
						</label>
						<label class="ce-bound">Bis
							{#if row.max == null}
								<button type="button" class="ce-open-btn" onclick={() => patch(row.metric, { max: row.scale[1] })}>offen · + Grenze</button>
							{:else}
								<input type="number" step={row.step} value={row.max} oninput={(e) => patch(row.metric, { max: clampBoundInput(numOrNull(e.currentTarget.value), 'max', row) })} />
								<button type="button" class="ce-clear-btn" title="Grenze öffnen" onclick={() => patch(row.metric, { max: null })}>×</button>
							{/if}
						</label>
					</div>
				</div>
				<div class="ce-effects">
					<button type="button" class="ce-effect notify" class:on={row.notify} aria-pressed={row.notify} onclick={() => patch(row.metric, { notify: !row.notify })}>Warnen</button>
					<button type="button" class="ce-effect mark" class:on={row.mark} aria-pressed={row.mark} onclick={() => patch(row.metric, { mark: !row.mark })}>Markieren</button>
					<button type="button" class="ce-remove" onclick={() => remove(row.metric)}>✕ entfernen</button>
				</div>
			</div>
		{/each}
		{#if poolLeft.length > 0}
			<div class="ce-pool">
				<span class="ce-pool-label">Metrik hinzufügen:</span>
				{#each poolLeft as m (m.metric)}
					<button type="button" class="ce-pool-btn" onclick={() => add(m.metric)}>＋ {m.label}</button>
				{/each}
			</div>
		{/if}
	</div>

	<div class="ce-summary">
		<span>{notifyN} × Warnen</span>
		<span>{markN} × Markieren</span>
	</div>
</div>

<style>
	.corridor-editor { padding: 28px 40px 60px; max-width: 1040px; }
	.ce-h2 { font-size: 26px; font-weight: 600; letter-spacing: -0.01em; margin: 6px 0 8px; color: var(--g-ink); }
	.ce-lead { font-size: 13.5px; color: var(--g-ink-2); line-height: 1.55; max-width: 680px; margin-bottom: 20px; }
	.ce-legend { display: flex; flex-wrap: wrap; gap: 18px; align-items: center; padding: 12px 16px; margin-bottom: 20px; background: var(--g-card-alt); border: 1px solid var(--g-rule-soft); border-radius: var(--g-r-3, 10px); font-size: 12.5px; color: var(--g-ink-2); }
	.ce-legend-title { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--g-ink-4); }
	.ce-legend-note { font-size: 12px; color: var(--g-ink-3); }
	.ce-swatch { width: 22px; height: 8px; border-radius: 4px; display: inline-block; }
	.ce-swatch.mark { background: var(--g-good); opacity: 0.85; }
	.ce-swatch.warn { background: rgba(192, 138, 26, 0.28); }
	.ce-good { color: var(--g-good); }
	.ce-warn { color: #8a6210; }
	.ce-error { color: #8a6210; background: rgba(192, 138, 26, 0.12); border: 1px solid rgba(192, 138, 26, 0.35); border-radius: var(--g-r-2, 6px); padding: 8px 12px; font-size: 13px; margin-bottom: 12px; }
	.ce-table { background: var(--g-card); border: 1px solid var(--g-rule-soft); border-radius: var(--g-r-3, 10px); overflow: hidden; }
	.ce-row { display: grid; grid-template-columns: 190px 1fr 224px; gap: 22px; padding: 18px 20px; border-bottom: 1px solid var(--g-rule-soft); align-items: start; }
	.ce-label { font-size: 14px; font-weight: 600; color: var(--g-ink); }
	.ce-unit { font-size: 10px; color: var(--g-ink-4); margin-left: 6px; }
	.ce-note { font-size: 11px; color: var(--g-ink-4); font-style: italic; margin-top: 2px; }
	.ce-band-track { position: relative; height: 10px; margin: 8px 0; border-radius: 5px; background: var(--g-rule-soft); }
	.ce-band-fill { position: absolute; top: 0; bottom: 0; border-radius: 5px; background: var(--g-ink-3); opacity: 0.4; }
	.ce-band-fill.mark { background: var(--g-good); opacity: 0.85; }
	.ce-handle { position: absolute; top: 50%; width: 16px; height: 16px; margin-left: -8px; margin-top: -8px; border-radius: 50%; background: #fff; border: 2px solid var(--g-accent); cursor: ew-resize; touch-action: none; z-index: 3; }
	.ce-handle.mark { border-color: var(--g-good); }
	.ce-open { position: absolute; top: -18px; font-size: 9px; color: var(--g-ink-4); letter-spacing: 0.04em; }
	.ce-open-left { left: 2px; }
	.ce-open-right { right: 2px; }
	.ce-bounds { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; }
	.ce-bound { display: flex; align-items: center; gap: 6px; font-size: 9.5px; color: var(--g-ink-4); text-transform: uppercase; }
	.ce-bound input { width: 58px; padding: 4px 6px; text-align: right; border: 1px solid var(--g-rule); border-radius: var(--g-r-2, 4px); }
	.ce-open-btn, .ce-clear-btn { border: 1px dashed var(--g-rule); background: transparent; border-radius: var(--g-r-2, 4px); cursor: pointer; color: var(--g-ink-4); font-size: 11.5px; padding: 4px 8px; }
	.ce-clear-btn { border: none; font-size: 13px; padding: 2px; }
	.ce-effects { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
	.ce-effect { padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: transparent; color: var(--g-ink-4); border: 1px solid var(--g-rule); cursor: pointer; }
	.ce-effect.notify.on { color: var(--g-warn); border-color: var(--g-warn); background: rgba(192, 138, 26, 0.12); }
	.ce-effect.mark.on { color: var(--g-good); border-color: var(--g-good); background: rgba(61, 107, 58, 0.12); }
	.ce-remove { background: transparent; border: none; color: var(--g-ink-4); font-size: 11px; cursor: pointer; padding: 0; }
	.ce-pool { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding: 14px 20px; border-top: 1px dashed var(--g-rule-soft); }
	.ce-pool-label { font-size: 10.5px; color: var(--g-ink-4); }
	.ce-pool-btn { border: 1px solid var(--g-rule); background: transparent; border-radius: 999px; padding: 4px 10px; cursor: pointer; font-size: 12px; }
	.ce-summary { display: flex; gap: 16px; margin-top: 16px; font-size: 12.5px; color: var(--g-ink-2); }
	@media (max-width: 899px) {
		.corridor-editor { padding: 1rem; max-width: 100%; }
	}
</style>
