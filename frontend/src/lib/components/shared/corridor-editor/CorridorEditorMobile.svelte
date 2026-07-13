<script lang="ts">
	// CorridorEditorMobile.svelte — Issue #1231, Slice 5: Mobile-Pendant zu
	// CorridorEditor.svelte (Desktop). Port aus
	// claude-code-handoff/current/jsx/corridor-editor-mobile.jsx.
	//
	// Reine Praesentationsschicht: importiert Daten + Logik 1:1 aus
	// corridorEditorState.ts/corridorMatch.ts (AC-15) — KEIN zweites
	// Datenmodell. Die duenne Svelte-Reaktivitaets-Verdrahtung (Save/Sync/
	// Patch) ist bewusst analog zu CorridorEditor.svelte dupliziert (Desktop
	// bleibt unangetastet) — die eigentliche Business-Logik lebt ausschliesslich
	// in corridorEditorState.ts.
	//
	// JSX-Abweichungen (Design-Referenz ist verbindlich; Begruendung im
	// Rueckmeldungstext an den Product Owner):
	//  - kein Live-Vorschau-Chips (JSX-Zeilen 160-184, 257-273, 296-299,
	//    220-225) — Desktop-Praezedenzfall (Slice 3/4) baut das ebenfalls
	//    nicht, MOCK_COMPARE_ROWS/MOCK_LOCATIONS existieren nur im JSX-Demo.
	//  - kein footer-Slot (JSX-Zeilen 245, 321) — Zustell-Controls sind seit
	//    #1232 in VersandTab.svelte, der alte Mobile-AlertsTab zeigte nur
	//    Heading+Onboarding+Tabelle (kein Footer-Inhalt vorhanden).
	//  - kein profileLabel (JSX-Zeile 245, 280) — Desktop hat kein Pendant.
	//  - CompareEndDateControlMobile (JSX-Zeilen 326-372) nicht verdrahtet —
	//    laut Spec Phase-2/Epic #29.
	//  - Warnen-Sperre fuer alarmCapable===false (Effekt-Buttons) ist NICHT im
	//    JSX enthalten, aber bindende Team-Lead-Vorgabe (Desktop-Praezedenz).
	import { getContext } from 'svelte';
	import { Eyebrow, Dot } from '$lib/components/atoms';
	import ScreenScroll from '$lib/components/mobile/ScreenScroll.svelte';
	import MBtn from '$lib/components/mobile/MBtn.svelte';
	import { api } from '$lib/api';
	import { toCompareProfile, type Trip, type SensLevel, type Corridor } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import type { ProfileKey } from '$lib/components/compare/compareMetricDefs';
	import { corridorFmt } from './corridorMatch.ts';
	import {
		buildRoutePool, addRow, removeRow, patchRow, validateCorridorRows,
		buildCorridorSavePayload, ROUTE_CTX_DEFAULTS, valueAtPointer, clampDragValue, clampBoundInput,
		saveGateDecision, openBoundValue, type CorridorRowState,
		COMPARE_METRIC_DEFS, buildComparePool, addCompareRow, VERGLEICH_CTX_DEFAULTS,
		buildCompareCorridorSavePayload, buildComparePrefillRows,
		type RouteMetricDef, type CompareMetricDef,
	} from './corridorEditorState.ts';

	interface Props {
		context?: 'route' | 'vergleich';
		trip?: Trip;
		onTripUpdate?: (t: Trip) => void;
		saveController?: SaveStatus;
	}
	let { context = 'route', trip, onTripUpdate, saveController }: Props = $props();

	const ws = context === 'vergleich' ? getContext<CompareWizardState>('compare-wizard-state') : undefined;

	// AC-10: "zuletzt bekannte Stufe" bezieht sich auf den beim Mount geladenen
	// Stand — analog Desktop (CorridorEditor.svelte), gilt fuer beide Kontexte.
	const originalLevels = (
		context === 'vergleich'
			? (ws?.metricAlertLevels as Record<string, SensLevel> | undefined)
			: trip?.display_config?.metric_alert_levels
	) ?? {} as Record<string, SensLevel>;
	const originalActiveMetricKeys: string[] = context === 'vergleich' ? [...(ws?.activeMetricKeys ?? [])] : [];

	const isFreshCompareCreate = context === 'vergleich' && !ws?.isEditMode && (ws?.corridors ?? []).length === 0;
	function computeInitialCompare(): { rows: CorridorRowState[]; poolLeft: CompareMetricDef[]; unknownCorridors: Corridor[] } {
		if (!isFreshCompareCreate) return buildComparePool(ws?.corridors ?? []);
		const profileKey = ws?.activityProfile ? (toCompareProfile(ws.activityProfile) as ProfileKey) : 'ALLGEMEIN';
		const prefillRows = buildComparePrefillRows(profileKey);
		const poolLeft = COMPARE_METRIC_DEFS.filter((d) => !prefillRows.some((r) => r.metric === d.metric));
		return { rows: prefillRows, poolLeft, unknownCorridors: [] };
	}
	const initial = context === 'vergleich' ? computeInitialCompare() : { ...buildRoutePool(trip?.corridors ?? []), unknownCorridors: [] };
	let rows = $state<CorridorRowState[]>(initial.rows);
	let poolLeft = $state<(RouteMetricDef | CompareMetricDef)[]>(initial.poolLeft);
	const unknownCorridors: Corridor[] = initial.unknownCorridors;
	let removedMetrics = $state<string[]>([]);

	const validation = $derived(validateCorridorRows(rows));
	const notifyN = $derived(rows.filter((r) => r.notify).length);
	const markN = $derived(rows.filter((r) => r.mark).length);

	function buildSaveFn() {
		const payload = buildCorridorSavePayload(rows, originalLevels, removedMetrics);
		return async () => {
			const updated = await api.put<Trip>(`/api/trips/${trip!.id}`, {
				corridors: payload.corridors,
				display_config: { ...trip!.display_config, metric_alert_levels: payload.metric_alert_levels },
			});
			onTripUpdate?.(updated);
		};
	}
	function syncToWizard() {
		if (!ws) return;
		const payload = buildCompareCorridorSavePayload(rows, removedMetrics, {
			idealRanges: ws.idealRanges,
			activeMetricKeys: ws.activeMetricKeys,
			metricAlertLevels: ws.metricAlertLevels as Record<string, SensLevel | undefined>,
		}, unknownCorridors);
		ws.corridors = payload.corridors;
		ws.idealRanges = payload.idealRanges;
		ws.activeMetricKeys = payload.activeMetricKeys;
		ws.metricAlertLevels = payload.metricAlertLevels;
	}
	if (isFreshCompareCreate && rows.length > 0) syncToWizard();

	function maybeSchedule() {
		if (context === 'vergleich') {
			if (saveGateDecision(rows) === 'schedule') syncToWizard();
			return;
		}
		if (saveGateDecision(rows) === 'schedule') saveController?.schedule(buildSaveFn());
		else saveController?.setDirty();
	}
	function patch(metric: string, p: Partial<Pick<CorridorRowState, 'min' | 'max' | 'notify' | 'mark'>>) {
		rows = patchRow(rows, metric, p);
		maybeSchedule();
	}
	function patchBound(row: CorridorRowState, side: 'min' | 'max', value: number | null) {
		patch(row.metric, side === 'min' ? { min: value } : { max: value });
	}
	function remove(metric: string) {
		rows = removeRow(rows, metric);
		removedMetrics = [...removedMetrics, metric];
		maybeSchedule();
	}
	function add(metric: string) {
		const next = context === 'vergleich'
			? addCompareRow(rows, poolLeft as CompareMetricDef[], metric, VERGLEICH_CTX_DEFAULTS, originalActiveMetricKeys.includes(metric))
			: addRow(rows, poolLeft as RouteMetricDef[], metric, ROUTE_CTX_DEFAULTS);
		rows = next.rows;
		poolLeft = next.poolLeft;
		maybeSchedule();
	}

	// Touch-Band: dual-handle Pointer-Drag (JSX-Zeilen 17-82) — setPointerCapture
	// fuer stabile Touch-Gesten, Wertelogik in valueAtPointer/clampDragValue.
	let dragging = $state<{ metric: string; side: 'min' | 'max'; track: HTMLElement } | null>(null);
	function onHandleDown(e: PointerEvent, metric: string, side: 'min' | 'max') {
		(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
		const track = (e.currentTarget as HTMLElement).closest('.cem-band-track') as HTMLElement | null;
		if (track) dragging = { metric, side, track };
	}
	function onWindowPointerMove(e: PointerEvent) {
		if (!dragging) return;
		const row = rows.find((r) => r.metric === dragging!.metric);
		if (!row) return;
		const rect = dragging.track.getBoundingClientRect();
		const raw = valueAtPointer(e.clientX, rect.left, rect.width, row.scale, row.step);
		const value = clampDragValue(dragging.side, raw, row.min, row.max);
		patchBound(row, dragging.side, value);
	}
	function onWindowPointerUp() {
		dragging = null;
	}

	// Stepper (CM_Bound, JSX-Zeilen 85-132): +/- je Grenze statt Zahlen-Tastatur.
	function fallbackFor(row: CorridorRowState, side: 'min' | 'max'): number {
		const [lo, hi] = row.scale;
		return side === 'min' ? lo + (hi - lo) * 0.25 : lo + (hi - lo) * 0.75;
	}
	function nudge(row: CorridorRowState, side: 'min' | 'max', dir: 1 | -1) {
		const current = side === 'min' ? row.min : row.max;
		const base = current ?? fallbackFor(row, side);
		const next = Math.round((base + dir * row.step) / row.step) * row.step;
		const clamped = Math.max(row.scale[0], Math.min(row.scale[1], next));
		patchBound(row, side, clampBoundInput(clamped, side, row));
	}
	function openBound(row: CorridorRowState, side: 'min' | 'max') {
		patchBound(row, side, openBoundValue(row, side));
	}
	function rangeLabel(row: CorridorRowState): string {
		if (row.kind === 'ordinal') {
			const lbl = (i: number | null) => (i == null ? null : (row.ordinalLabels?.[i] ?? String(i)));
			if (row.min != null && row.max != null) return `${lbl(row.min)} … ${lbl(row.max)}`;
			if (row.min != null) return `≥ ${lbl(row.min)}`;
			if (row.max != null) return `≤ ${lbl(row.max)}`;
			return 'offen';
		}
		if (row.min != null && row.max != null) return `${corridorFmt(row.min, '')} … ${corridorFmt(row.max, row.unit)}`;
		if (row.min != null) return `≥ ${corridorFmt(row.min, row.unit)}`;
		if (row.max != null) return `≤ ${corridorFmt(row.max, row.unit)}`;
		return 'offen';
	}
</script>

<svelte:window onpointermove={onWindowPointerMove} onpointerup={onWindowPointerUp} />

<ScreenScroll padding={14}>
	<div class="cem" data-testid="corridor-editor-mobile-{context}">
		{#if context === 'vergleich'}
			<Eyebrow>Wertebereiche · Idealbereiche</Eyebrow>
			<div class="cem-title">Sag mir, welche Werte dir ideal sind</div>
			<div class="cem-lead">Ein Wertebereich je Metrik legt deinen Idealbereich fest. Werte im Bereich werden im Briefing pro Ort grün markiert — kein Score, kein Ranking, nur eine Lese-Hilfe.</div>
		{:else}
			<Eyebrow>Wertebereiche · Warn-Schwellen</Eyebrow>
			<div class="cem-title">Sag mir, wenn das Wetter aus dem Rahmen läuft</div>
			<div class="cem-lead">Ein Wertebereich je Metrik legt fest, welche Werte du auf der Tour noch akzeptierst. Verlässt ein Wert den Bereich, bekommst du zwischen den Briefings eine Sofort-Meldung.</div>
		{/if}

		<div class="cem-legend">
			<span><span class="cem-swatch mark"></span> im Bereich = <strong class="cem-good">markiert</strong></span>
			<span><span class="cem-swatch warn"></span> außerhalb = <strong class="cem-warn">Warnung</strong></span>
		</div>

		{#if !validation.valid}
			<p class="cem-error" role="alert" data-testid="corridor-editor-mobile-error">
				Mindestens eine Grenze (Von oder Bis) ist Pflicht: {validation.errors.join(', ')}
			</p>
		{/if}

		{#each rows as row (row.metric)}
			{@const span = row.scale[1] - row.scale[0] || 1}
			{@const leftPct = row.min == null ? 0 : Math.max(0, Math.min(1, (row.min - row.scale[0]) / span)) * 100}
			{@const rightPct = row.max == null ? 100 : Math.max(0, Math.min(1, (row.max - row.scale[0]) / span)) * 100}
			<div class="cem-card" data-testid="corridor-mobile-row-{row.metric}">
				<div class="cem-head">
					<div>
						<span class="cem-label">{row.label}</span>
						<span class="cem-unit">{row.unit}</span>
					</div>
					<span class="cem-range">{rangeLabel(row)}</span>
				</div>
				{#if row.note}<div class="cem-note">{row.note}</div>{/if}

				<div class="cem-band-track" data-testid="corridor-mobile-band-{row.metric}">
					<div class="cem-band-fill" class:mark={row.mark} style="left:{leftPct}%;width:{rightPct - leftPct}%"></div>
					{#if row.min == null}<span class="cem-open cem-open-left">◂ offen</span>{/if}
					{#if row.max == null}<span class="cem-open cem-open-right">offen ▸</span>{/if}
					{#if row.min != null}
						<div class="cem-handle" style="left:{leftPct}%" onpointerdown={(e) => onHandleDown(e, row.metric, 'min')}></div>
					{/if}
					{#if row.max != null}
						<div class="cem-handle" class:mark={row.mark} style="left:{rightPct}%" onpointerdown={(e) => onHandleDown(e, row.metric, 'max')}></div>
					{/if}
				</div>
				<div class="cem-band-scale">
					<span>{corridorFmt(row.scale[0], '')}</span><span>{corridorFmt(row.scale[1], '')}</span>
				</div>

				<div class="cem-bounds">
					{#each ['min', 'max'] as const as side}
						{@const value = side === 'min' ? row.min : row.max}
						<div class="cem-bound">
							<div class="cem-bound-label">{side === 'min' ? 'Von' : 'Bis'}</div>
							{#if value == null}
								<button type="button" class="cem-open-btn" onclick={() => openBound(row, side)}>offen · + Grenze</button>
							{:else if row.kind === 'ordinal'}
								<div class="cem-ordinal-group" data-testid="corridor-mobile-ordinal-{side}-{row.metric}">
									{#each row.ordinalLabels ?? [] as lbl, idx (lbl)}
										<button type="button" class="cem-ordinal-btn" class:on={value === idx} onclick={() => patchBound(row, side, clampBoundInput(idx, side, row))}>{lbl}</button>
									{/each}
									<button type="button" class="cem-clear-btn" title="Grenze öffnen" onclick={() => patchBound(row, side, null)}>×</button>
								</div>
							{:else}
								<!-- AC-14 vs. JSX-Optik (Tech-Lead-Entscheidung): Hit-Area-Technik —
								     .cem-step-btn selbst ist 44x44 (getBoundingClientRect-pflichtig),
								     .cem-step-btn-glyph bleibt die 40px-JSX-Optik (Z. 100-105) innen zentriert. -->
								<div class="cem-stepper">
									<button type="button" class="cem-step-btn" onclick={() => nudge(row, side, -1)}><span class="cem-step-btn-glyph">−</span></button>
									<div class="cem-step-value">
										<div class="cem-step-num">{value}</div>
										<div class="cem-step-unit">{row.unit}</div>
									</div>
									<button type="button" class="cem-step-btn" onclick={() => nudge(row, side, 1)}><span class="cem-step-btn-glyph">+</span></button>
									<button type="button" class="cem-clear-btn" title="Grenze öffnen" onclick={() => patchBound(row, side, null)}>×</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>

				<div class="cem-effects">
					{#if row.alarmCapable === false}
						<button type="button" class="cem-effect notify disabled" disabled title="nur Markieren – für diese Metrik gibt es keinen Alarm-Abgleich">Warnen</button>
					{:else}
						<button type="button" class="cem-effect notify" class:on={row.notify} aria-pressed={row.notify} onclick={() => patch(row.metric, { notify: !row.notify })}>Warnen</button>
					{/if}
					<button type="button" class="cem-effect mark" class:on={row.mark} aria-pressed={row.mark} onclick={() => patch(row.metric, { mark: !row.mark })}>Markieren</button>
				</div>

				<div class="cem-remove-row">
					<button type="button" class="cem-remove" onclick={() => remove(row.metric)}>✕ entfernen</button>
				</div>
			</div>
		{/each}

		{#if poolLeft.length > 0}
			<div class="cem-pool">
				<div class="cem-pool-label">Metrik hinzufügen</div>
				{#each poolLeft as m (m.metric)}
					<MBtn block variant="ghost" size="lg" onclick={() => add(m.metric)}>＋ {m.label}</MBtn>
				{/each}
			</div>
		{/if}

		<div class="cem-summary">
			<span class="cem-summary-item"><Dot tone="warn" /> {notifyN} × Warnen</span>
			<span class="cem-summary-item"><Dot tone="good" /> {markN} × Markieren</span>
		</div>
		{#if context === 'vergleich'}
			<div class="cem-neutral" data-testid="corridor-editor-mobile-neutral-hint">kein Score · kein Rang · Wertebereiche markieren nur, sie sortieren nicht</div>
			{#if unknownCorridors.length > 0}
				<div class="cem-neutral" data-testid="corridor-editor-mobile-unknown-hint">
					{unknownCorridors.length} weitere{unknownCorridors.length === 1 ? 'r Eintrag bleibt' : ' Einträge bleiben'} erhalten
				</div>
			{/if}
		{/if}
	</div>
</ScreenScroll>

<style>
	.cem { font-family: var(--g-font-sans); }
	.cem-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; margin: 6px 0; color: var(--g-ink); }
	.cem-lead { font-size: 13px; color: var(--g-ink-2); line-height: 1.5; margin-bottom: 14px; }
	.cem-legend { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px; margin-bottom: 14px; background: var(--g-card-alt); border: 1px solid var(--g-rule-soft); border-radius: var(--g-r-3, 10px); font-size: 12.5px; color: var(--g-ink-2); }
	.cem-swatch { width: 22px; height: 8px; border-radius: 4px; display: inline-block; vertical-align: middle; margin-right: 6px; }
	.cem-swatch.mark { background: var(--g-good); opacity: 0.85; }
	.cem-swatch.warn { background: rgba(192, 138, 26, 0.28); }
	.cem-good { color: var(--g-good); }
	.cem-warn { color: #8a6210; }
	.cem-error { color: #8a6210; background: rgba(192, 138, 26, 0.12); border: 1px solid rgba(192, 138, 26, 0.35); border-radius: var(--g-r-2, 6px); padding: 8px 12px; font-size: 13px; margin-bottom: 12px; }
	.cem-card { background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3, 10px); padding: 14px 14px 12px; margin-bottom: 10px; }
	.cem-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
	.cem-label { font-size: 15px; font-weight: 600; color: var(--g-ink); }
	.cem-unit { font-size: 10px; color: var(--g-ink-4); margin-left: 6px; }
	.cem-range { font-size: 13px; font-weight: 600; color: var(--g-ink); white-space: nowrap; }
	.cem-note { font-size: 11.5px; color: var(--g-ink-4); margin-top: 2px; font-style: italic; }
	.cem-band-track { position: relative; height: 14px; margin-top: 22px; margin-bottom: 8px; border-radius: 7px; background: var(--g-rule-soft); }
	.cem-band-fill { position: absolute; top: 0; bottom: 0; border-radius: 7px; background: var(--g-ink-3); opacity: 0.4; }
	.cem-band-fill.mark { background: var(--g-good); opacity: 0.85; }
	.cem-handle { position: absolute; top: 50%; width: 24px; height: 24px; margin-left: -12px; margin-top: -12px; border-radius: 50%; background: #fff; border: 2px solid var(--g-accent); cursor: ew-resize; touch-action: none; z-index: 3; }
	.cem-handle.mark { border-color: var(--g-good); }
	/* AC-14 Hit-Area-Technik (Tech-Lead-Entscheidung, kein Playwright-Pflichtziel
	   fuer den Handle selbst — AC-14-Test erfasst nur Stepper/Toggle-Buttons):
	   unsichtbare 44x44-Trefffläche um den 24px-Punkt, Optik bleibt JSX-treu. */
	.cem-handle::before { content: ''; position: absolute; top: 50%; left: 50%; width: 44px; height: 44px; transform: translate(-50%, -50%); }
	.cem-open { position: absolute; top: -18px; font-size: 10px; color: var(--g-ink-4); }
	.cem-open-left { left: 2px; }
	.cem-open-right { right: 2px; }
	.cem-band-scale { display: flex; justify-content: space-between; font-size: 10px; color: var(--g-ink-4); }
	.cem-bounds { display: flex; gap: 12px; margin-top: 12px; }
	.cem-bound { flex: 1; min-width: 0; }
	.cem-bound-label { font-size: 9.5px; color: var(--g-ink-4); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 5px; }
	.cem-open-btn { width: 100%; min-height: 44px; border: 1px dashed var(--g-rule); background: transparent; border-radius: var(--g-r-2, 6px); cursor: pointer; color: var(--g-ink-4); font-size: 12px; }
	.cem-stepper, .cem-ordinal-group { display: flex; align-items: center; gap: 6px; }
	/* AC-14 Hit-Area-Technik: Trefffläche 44x44 (Playwright-messbar), Glyph-Optik bleibt 40px wie im JSX. */
	.cem-step-btn { width: 44px; height: 44px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; border: none; background: transparent; padding: 0; cursor: pointer; }
	.cem-step-btn-glyph { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border: 1px solid var(--g-rule); background: var(--g-card); border-radius: var(--g-r-2, 6px); color: var(--g-ink); font-size: 20px; line-height: 1; }
	.cem-step-value { flex: 1; min-width: 0; text-align: center; padding: 0 2px; }
	.cem-step-num { font-size: 16px; font-weight: 600; color: var(--g-ink); font-variant-numeric: tabular-nums; line-height: 1.1; }
	.cem-step-unit { font-size: 9px; color: var(--g-ink-4); }
	.cem-ordinal-btn { flex: 1; min-height: 44px; padding: 4px 6px; font-size: 11.5px; border-radius: var(--g-r-2, 6px); border: 1px solid var(--g-rule); background: transparent; color: var(--g-ink-3); cursor: pointer; }
	.cem-ordinal-btn.on { border-color: var(--g-accent); color: var(--g-accent-deep); background: var(--g-accent-tint); }
	.cem-clear-btn { width: 30px; height: 40px; flex-shrink: 0; border: none; background: transparent; cursor: pointer; color: var(--g-ink-4); font-size: 15px; }
	.cem-effects { display: flex; gap: 8px; margin-top: 12px; }
	.cem-effect { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 0 12px; border-radius: var(--g-r-3, 10px); cursor: pointer; font-size: 14px; font-weight: 600; background: transparent; color: var(--g-ink-4); border: 1px solid var(--g-rule); }
	.cem-effect.notify.on { color: var(--g-warn, #8a6210); border-color: var(--g-warn, #8a6210); background: rgba(192, 138, 26, 0.12); }
	.cem-effect.mark.on { color: var(--g-good); border-color: var(--g-good); background: rgba(61, 107, 58, 0.12); }
	.cem-effect.disabled { opacity: 0.4; cursor: not-allowed; }
	.cem-remove-row { display: flex; justify-content: flex-end; margin-top: 8px; }
	.cem-remove { background: transparent; border: none; padding: 6px 2px; color: var(--g-ink-4); cursor: pointer; font-size: 11.5px; }
	.cem-pool { display: flex; flex-direction: column; gap: 8px; margin: 4px 0 6px; }
	.cem-pool-label { font-size: 10px; color: var(--g-ink-4); letter-spacing: 0.08em; text-transform: uppercase; }
	.cem-summary { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-top: 10px; font-size: 12.5px; color: var(--g-ink-2); }
	.cem-summary-item { display: inline-flex; align-items: center; gap: 7px; }
	.cem-neutral { font-size: 10.5px; color: var(--g-ink-4); margin-top: 8px; letter-spacing: 0.02em; line-height: 1.5; }
</style>
