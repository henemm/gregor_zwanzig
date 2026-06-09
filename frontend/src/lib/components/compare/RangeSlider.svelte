<script lang="ts">
	// Issue #680 — RangeSlider: Dual-Handle Slider für Idealwert-Bereiche (AC-6).
	// Pure UI-Komponente ohne Store-Abhängigkeit.

	interface Props {
		min: number;
		max: number;
		step: number;
		valueMin: number;
		valueMax: number;
		metricKey: string;
		onchange: (min: number, max: number) => void;
	}

	let { min, max, step, valueMin, valueMax, metricKey, onchange }: Props = $props();

	let activeHandle: 'min' | 'max' | null = null;

	function clamp(val: number, lo: number, hi: number): number {
		return Math.min(hi, Math.max(lo, val));
	}

	function snapToStep(val: number): number {
		return Math.round((val - min) / step) * step + min;
	}

	function pctToValue(pct: number): number {
		return snapToStep(min + pct * (max - min));
	}

	function getTrackPct(e: PointerEvent, trackEl: HTMLElement): number {
		const rect = trackEl.getBoundingClientRect();
		return clamp((e.clientX - rect.left) / rect.width, 0, 1);
	}

	let trackEl: HTMLElement;

	function onPointerDownMin(e: PointerEvent) {
		e.preventDefault();
		activeHandle = 'min';
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function onPointerDownMax(e: PointerEvent) {
		e.preventDefault();
		activeHandle = 'max';
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function onPointerMove(e: PointerEvent) {
		if (!activeHandle || !trackEl) return;
		const pct = getTrackPct(e, trackEl);
		const newVal = pctToValue(pct);
		if (activeHandle === 'min') {
			const clamped = clamp(newVal, min, valueMax - step);
			onchange(clamped, valueMax);
		} else {
			const clamped = clamp(newVal, valueMin + step, max);
			onchange(valueMin, clamped);
		}
	}

	function onPointerUp() {
		activeHandle = null;
	}

	function onKeyMin(e: KeyboardEvent) {
		let next = valueMin;
		if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = clamp(snapToStep(valueMin - step), min, valueMax - step);
		else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = clamp(snapToStep(valueMin + step), min, valueMax - step);
		else if (e.key === 'Home') next = min;
		else if (e.key === 'End') next = valueMax - step;
		else return;
		e.preventDefault();
		onchange(next, valueMax);
	}

	function onKeyMax(e: KeyboardEvent) {
		let next = valueMax;
		if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = clamp(snapToStep(valueMax - step), valueMin + step, max);
		else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = clamp(snapToStep(valueMax + step), valueMin + step, max);
		else if (e.key === 'Home') next = valueMin + step;
		else if (e.key === 'End') next = max;
		else return;
		e.preventDefault();
		onchange(valueMin, next);
	}

	const fillLeft = $derived(((valueMin - min) / (max - min)) * 100);
	const fillWidth = $derived(((valueMax - valueMin) / (max - min)) * 100);
	const minPct = $derived(((valueMin - min) / (max - min)) * 100);
	const maxPct = $derived(((valueMax - min) / (max - min)) * 100);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	style="position:relative; height:20px; display:flex; align-items:center; user-select:none;"
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
	onpointerleave={onPointerUp}
>
	<!-- Track -->
	<div
		bind:this={trackEl}
		style="position:relative; width:100%; height:8px; background:var(--g-rule-soft); border-radius:4px;"
	>
		<!-- Fill -->
		<div
			style="position:absolute; top:0; bottom:0; left:{fillLeft}%; width:{fillWidth}%; background:var(--g-accent); opacity:0.85; border-radius:4px; pointer-events:none;"
		></div>

		<!-- Min thumb -->
		<!-- svelte-ignore a11y_interactive_supports_focus -->
		<div
			data-testid={`compare-step3-slider-min-${metricKey}`}
			role="slider"
			tabindex={0}
			aria-valuemin={min}
			aria-valuemax={valueMax - step}
			aria-valuenow={valueMin}
			aria-label="Minimum"
			style="position:absolute; top:-3px; left:{minPct}%; width:14px; height:14px; margin-left:-7px; background:#fff; border:2px solid var(--g-accent); border-radius:50%; cursor:pointer; touch-action:none;"
			onpointerdown={onPointerDownMin}
			onkeydown={onKeyMin}
		></div>

		<!-- Max thumb -->
		<!-- svelte-ignore a11y_interactive_supports_focus -->
		<div
			data-testid={`compare-step3-slider-max-${metricKey}`}
			role="slider"
			tabindex={0}
			aria-valuemin={valueMin + step}
			aria-valuemax={max}
			aria-valuenow={valueMax}
			aria-label="Maximum"
			style="position:absolute; top:-3px; left:{maxPct}%; width:14px; height:14px; margin-left:-7px; background:#fff; border:2px solid var(--g-accent); border-radius:50%; cursor:pointer; touch-action:none;"
			onpointerdown={onPointerDownMax}
			onkeydown={onKeyMax}
		></div>
	</div>
</div>
