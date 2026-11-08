<script lang="ts">
	// Issue #2837 S2b (Epic #2345, ADR-0110) — EIN Fortschrittsbalken für /trips/new und
	// /compare/new, Computer (`variante="desktop"`, im AnlegeRahmen) und Handy (`variante="mobil"`,
	// an der Handy-Stelle des Editors).
	// Spec: docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md
	//
	// EIN Markup: `variante` wählt nur Segmentbreite (24px fest / flex: 1) und Zählertext
	// („n von 5 Abschnitten" / „n/5"). Farbregel: erledigt ⇒ var(--g-accent), sonst var(--g-rule).
	// Der aktive Schritt wird bewusst NICHT getönt (Entscheidung 2); `aktiv` setzt nur
	// `aria-current`. Der Zähler ist letztes Kind des Testid-Containers (Regex-Auslese in
	// compare_new_lock_engine_wirkstelle.test.ts). Kein <style>-Block: Klassen bleiben genau "mono".
	import { t } from '$lib/i18n';

	interface Props {
		/** Schritt-Kennungen in Reihenfolge (PROGRESS_STEPS). */
		steps: readonly string[];
		/** Zahl erledigter Schritte (Ergebnis von `progressCount`) — Zähler; ohne `erledigt` auch Segmentfarbe (i < done). */
		done: number;
		/** Menge erledigter Schritte (Adversary F003): gesetzt ⇒ Segment i erledigt ⇔ erledigt.has(steps[i]). */
		erledigt?: ReadonlySet<string>;
		/** Kennung des aktiven Schritts — nur `aria-current`, keine Optik. */
		aktiv?: string;
		variante: 'desktop' | 'mobil';
		/** Container-Testid; Segmente heißen `${testidPrefix}-segment`. */
		testidPrefix: string;
	}

	let { steps, done, erledigt, aktiv, variante, testidPrefix }: Props = $props();

	const mobil = $derived(variante === 'mobil');
	// Färbung je Schritt wie der Altbestand (done.has(step)); Rückfall positional.
	const istErledigt = (step: string, i: number) => (erledigt ? erledigt.has(step) : i < done);
	const zaehler = $derived(
		mobil
			? $t('trip.anlegen.abschnitte_kurz', { n: done, gesamt: steps.length })
			: done === 0
				? $t('trip.anlegen.nichts_eingerichtet')
				: $t('trip.anlegen.abschnitte', { n: done, gesamt: steps.length })
	);
</script>

<div
	data-testid={testidPrefix}
	style="display: flex; align-items: center; gap: {mobil ? '8px' : '10px'};{mobil ? ' flex: 1;' : ' margin-top: 7px;'}"
>
	<div style="display: flex; gap: 3px;{mobil ? ' flex: 1;' : ''}">
		{#each steps as step, i (step)}
			<div
				data-testid={`${testidPrefix}-segment`}
				data-done={istErledigt(step, i) ? 'true' : 'false'}
				aria-current={step === aktiv ? 'step' : undefined}
				style="{mobil ? 'flex: 1' : 'width: 24px'}; height: 3px; border-radius: 2px; background: {istErledigt(step, i) ? 'var(--g-accent)' : 'var(--g-rule)'}; transition: background 350ms;"
			></div>
		{/each}
	</div>
	<span class="mono" style="font-size: 11px; color: var(--g-ink-4); flex-shrink: 0;{mobil ? '' : ' letter-spacing: 0.04em;'}">{zaehler}</span>
</div>
