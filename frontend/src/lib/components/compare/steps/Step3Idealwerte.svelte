<script lang="ts">
	// Issue #441 — Step 3: Idealwerte (Min/Max pro Metrik je Aktivitätsprofil).
	// Issue #680 — Slice 3: Dual-Handle-Slider, Segmented-Control, Metrik add/remove.
	// Spec: docs/specs/modules/issue_680_compare_editor_slice3.md
	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import {
		PROFILE_METRICS_WITH_SCALES,
		IDEAL_DEFAULTS,
		ALL_METRICS,
		deriveIdealText,
		validateIdealRanges,
		type ProfileKey
	} from '../compareMetricDefs';
	import { toCompareProfile } from '$lib/types';
	import RangeSlider from '../RangeSlider.svelte';

	const ws = getContext<CompareWizardState>('compare-wizard-state');

	// Profil-Mapping: ActivityProfile → ProfileKey, Fallback ALLGEMEIN.
	const profileKey = $derived<ProfileKey>(
		ws.activityProfile
			? (toCompareProfile(ws.activityProfile) as ProfileKey)
			: 'ALLGEMEIN'
	);

	const metrics = $derived(
		PROFILE_METRICS_WITH_SCALES[profileKey] ?? PROFILE_METRICS_WITH_SCALES.ALLGEMEIN
	);

	// Defaults aus IDEAL_DEFAULTS in ws.idealRanges schreiben — nur wenn Key
	// noch nicht belegt ist (sonst würden Edit-Modus-Werte überschrieben).
	$effect(() => {
		const defaults = IDEAL_DEFAULTS[profileKey] ?? {};
		let next = ws.idealRanges;
		let changed = false;
		for (const [key, range] of Object.entries(defaults)) {
			if (!(key in next)) {
				if (!changed) {
					next = { ...next };
					changed = true;
				}
				next[key] = range;
			}
		}
		if (changed) ws.idealRanges = next;
	});

	// AC-4/AC-5: activeMetricKeys aus Profil-Defaults initialisieren (nur wenn nicht manuell geändert)
	$effect(() => {
		if (ws.activeMetricKeys.length === 0 && !ws.metricsManuallyEdited) {
			ws.activeMetricKeys = metrics.map((m) => m.key);
		}
	});

	// AC-5: Profil-Wechsel aktualisiert activeMetricKeys (sofern nicht manuell geändert)
	$effect(() => {
		// Zugriff auf profileKey registriert die Abhängigkeit
		const currentProfileKey = profileKey;
		if (!ws.metricsManuallyEdited && ws.activeMetricKeys.length > 0) {
			const profileMetricKeys = (
				PROFILE_METRICS_WITH_SCALES[currentProfileKey] ??
				PROFILE_METRICS_WITH_SCALES.ALLGEMEIN
			).map((m) => m.key);
			// Nur zurücksetzen wenn Profil tatsächlich wechselte (andere Keys)
			const same =
				profileMetricKeys.length === ws.activeMetricKeys.length &&
				profileMetricKeys.every((k) => ws.activeMetricKeys.includes(k));
			if (!same) {
				ws.activeMetricKeys = profileMetricKeys;
			}
		}
	});

	// Aktive Metriken: aus ALL_METRICS filtern nach activeMetricKeys
	const activeMetrics = $derived(
		ALL_METRICS.filter((m) => ws.activeMetricKeys.includes(m.key))
	);

	// Verfügbare Metriken für "hinzufügen"
	const availableMetrics = $derived(
		ALL_METRICS.filter((m) => !ws.activeMetricKeys.includes(m.key))
	);

	// Issue #718: Keys mit ungültigem min >= max (nur range-Metriken)
	const invalidKeys = $derived(
		validateIdealRanges(ws.idealRanges, ws.activeMetricKeys).invalidKeys
	);

	let showAddMenu = $state(false);

	function setMin(key: string, raw: number) {
		const val = Number.isNaN(raw) ? null : raw;
		const prev = ws.idealRanges[key] ?? {};
		ws.idealRanges = { ...ws.idealRanges, [key]: { ...prev, min: val } };
	}

	function setMax(key: string, raw: number) {
		const val = Number.isNaN(raw) ? null : raw;
		const prev = ws.idealRanges[key] ?? {};
		ws.idealRanges = { ...ws.idealRanges, [key]: { ...prev, max: val } };
	}

	function setEnumMax(key: string, val: string) {
		ws.idealRanges = { ...ws.idealRanges, [key]: { max: val } };
	}

	function removeMetric(key: string) {
		ws.activeMetricKeys = ws.activeMetricKeys.filter((k) => k !== key);
		ws.metricsManuallyEdited = true;
	}

	function addMetric(key: string) {
		ws.activeMetricKeys = [...ws.activeMetricKeys, key];
		ws.metricsManuallyEdited = true;
		showAddMenu = false;
	}
</script>

<div data-testid="compare-wizard-step-3" style="padding:28px 40px 60px; position:relative; max-width:820px;">
	<!-- Header -->
	<div style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px; border-bottom:1px solid var(--g-rule-soft); background:var(--g-card-alt); border-radius:var(--g-r-3) var(--g-r-3) 0 0; margin-bottom:0;">
		<Eyebrow style="margin:0;">{activeMetrics.length} Metriken</Eyebrow>
		<div style="position:relative;">
			<button
				data-testid="compare-step3-add-metric-btn"
				type="button"
				onclick={() => { showAddMenu = !showAddMenu; }}
				style="background:transparent; border:1px solid var(--g-rule); padding:4px 10px; font-size:12px; color:var(--g-ink-3); cursor:pointer; border-radius:var(--g-r-2); font-family:var(--g-font-sans);"
			>＋ Metrik hinzufügen</button>
			{#if showAddMenu}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					style="position:absolute; right:0; top:calc(100% + 4px); min-width:200px; background:var(--g-card); border:1px solid var(--g-rule); border-radius:var(--g-r-2); z-index:10; box-shadow:0 4px 12px rgba(0,0,0,0.08);"
					onmouseleave={() => { showAddMenu = false; }}
				>
					{#if availableMetrics.length === 0}
						<div style="padding:12px 14px; font-size:12px; color:var(--g-ink-4); text-align:center;">Alle Metriken bereits hinzugefügt</div>
					{:else}
						{#each availableMetrics as m (m.key)}
							<button
								data-testid={`compare-step3-add-metric-option-${m.key}`}
								type="button"
								onclick={() => addMetric(m.key)}
								style="display:block; width:100%; text-align:left; padding:9px 14px; font-size:13px; color:var(--g-ink); background:transparent; border:none; border-bottom:1px solid var(--g-rule-soft); cursor:pointer; font-family:var(--g-font-sans);"
							>{m.label}{m.unit ? ` (${m.unit})` : ''}</button>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<!-- Metrik-Tabelle -->
	<div style="background:var(--g-card); border:1px solid var(--g-rule); border-radius:0 0 var(--g-r-3) var(--g-r-3); overflow:hidden;">
		{#if activeMetrics.length === 0}
			<div style="padding:32px 20px; text-align:center; color:var(--g-ink-4); font-size:13px;">
				Keine Metriken aktiv. Klicke oben auf „＋ Metrik hinzufügen".
			</div>
		{:else}
			{#each activeMetrics as metric, i (metric.key)}
				<div
					data-testid={`compare-step3-metric-${metric.key}`}
					style="padding:16px 20px; border-bottom:{i < activeMetrics.length - 1 ? '1px solid var(--g-rule-soft)' : 'none'}; display:grid; grid-template-columns:200px 1fr 180px 28px; gap:20px; align-items:center;"
				>
					<!-- Label -->
					<div>
						<div style="font-size:13.5px; font-weight:600; color:var(--g-ink);">{metric.label}</div>
					</div>

					<!-- Slider / Segmented-Control -->
					{#if metric.kind === 'range'}
						<div>
							<RangeSlider
								min={metric.rangeMin ?? 0}
								max={metric.rangeMax ?? 100}
								step={metric.step ?? 1}
								valueMin={ws.idealRanges[metric.key]?.min ?? metric.rangeMin ?? 0}
								valueMax={ws.idealRanges[metric.key]?.max as number ?? metric.rangeMax ?? 100}
								metricKey={metric.key}
								onchange={(vMin, vMax) => { setMin(metric.key, vMin); setMax(metric.key, vMax); }}
							/>
							<!-- Skalen-Labels + Compat-Testids -->
							<div style="display:flex; justify-content:space-between; margin-top:6px; font-family:var(--g-font-mono); font-size:10px; color:var(--g-ink-4);">
								<span data-testid={`compare-step3-scale-min-${metric.key}`}>{metric.rangeMin}</span>
								<span data-testid={`compare-step3-scale-max-${metric.key}`}>{metric.rangeMax}</span>
							</div>
							<!-- Hidden compat inputs for existing tests -->
							<input type="hidden" data-testid={`compare-step3-min-${metric.key}`} value={ws.idealRanges[metric.key]?.min ?? ''} />
							<input type="hidden" data-testid={`compare-step3-max-${metric.key}`} value={ws.idealRanges[metric.key]?.max ?? ''} />
							<!-- Issue #718: Inline-Fehlermeldung bei min >= max -->
							{#if invalidKeys.includes(metric.key)}
								<div
									data-testid={`compare-step3-error-${metric.key}`}
									style="margin-top:4px; font-size:11.5px; color:var(--g-danger, #a83232); font-family:var(--g-font-sans);"
								>
									Min-Wert muss kleiner als Max-Wert sein
								</div>
							{/if}
						</div>
					{:else if metric.kind === 'enum'}
						<div style="display:flex; gap:4px;" data-testid={`compare-step3-max-${metric.key}`}>
							{#each metric.enumValues ?? [] as val (val)}
								<button
									type="button"
									onclick={() => setEnumMax(metric.key, val)}
									style="padding:5px 10px; font-size:12px; font-family:var(--g-font-mono); border-radius:var(--g-r-2); cursor:pointer; border:1.5px solid {(ws.idealRanges[metric.key]?.max as string) === val ? 'var(--g-accent)' : 'var(--g-rule)'}; background:{(ws.idealRanges[metric.key]?.max as string) === val ? 'var(--g-accent-tint)' : 'transparent'}; color:{(ws.idealRanges[metric.key]?.max as string) === val ? 'var(--g-accent-deep)' : 'var(--g-ink-3)'};"
								>{val}</button>
							{/each}
							<!-- Hidden min compat testid -->
							<input type="hidden" data-testid={`compare-step3-min-${metric.key}`} value="" />
						</div>
					{:else}
						<div></div>
					{/if}

					<!-- Ideal-Text -->
					<span
						data-testid={`compare-step3-ideal-text-${metric.key}`}
						style="font-family:var(--g-font-mono); font-size:12.5px; font-weight:600; color:var(--g-accent-deep); text-align:right;"
					>{deriveIdealText(ws.idealRanges[metric.key] ?? {}, metric.unit)}</span>

					<!-- ✕ Metrik entfernen -->
					<button
						data-testid={`compare-step3-remove-metric-${metric.key}`}
						type="button"
						onclick={() => removeMetric(metric.key)}
						style="background:transparent; border:none; padding:4px; color:var(--g-ink-4); cursor:pointer; font-size:12px;"
					>✕</button>
				</div>
			{/each}
		{/if}
	</div>
</div>
