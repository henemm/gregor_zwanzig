<script lang="ts">
	// Issue #587 — Wetter-Metriken-Tab v2: Abschnitt 3 Reihenfolge & Darstellung.
	// 1:1 nach WM2_Reihenfolge / WM2_ReihenfolgeRow / WM2_CutLine aus JSX.
	// Kein „→ Detail"-Knopf, keine Detail-Zeile (PO-Entscheidung 2026-06-06).
	// Orange gestrichelte Schnittlinie nach Position 8 NUR wenn activeChannel=telegram.
	// Issue #848 — Drag & Drop ersetzt Pfeiltasten.
	// Issue #1272 / ADR-0024 — handverdrahtetes HTML5-Drag raus, geteilter
	// Baustein `shared/dnd/SortableList` rein. Vertrag jetzt
	// onDndReorder(newOrder: string[]) statt (fromId, toId). Die Cut-Line ist
	// bedingtes Markup INNERHALB des Item-Wrappers — als Sibling in der Zone
	// wuerde `dndzone` sie aus dem DOM entfernen.
	// Issue #1232 Scheibe 3b: Cut-Line-Markup durch geteiltes Primitiv
	// `LTCutLine` ersetzt (KL-1 aus Scheibe 3a wird hiermit aufgelöst).
	// Issue #1719 Scheibe S3 (ADR-0050 Regel 4): "Aus in diesem Kanal"-Gruppe
	// unter der sortierbaren Liste — eine im Kanal abgewählte Metrik bleibt
	// sichtbar und wieder einschaltbar, statt aus der Liste zu verschwinden.
	// Nur der Trip-Kanal-Reiter (WeatherMetricsTab.svelte) übergibt
	// `offColumns`/`onRestore` — die drei Vergleichs-Einbettungen (Übersicht,
	// Ausblick, Stundenverlauf) haben ein anderes Datenmodell (flaches Array,
	// bereits ein funktionierender Rückweg über eine Checkbox darüber) und
	// bleiben unverändert (Spec Abschnitt 1/4, AC-13 Lackmustest).
	import type { MetricEntry } from '../../trip-detail/metricsEditor.ts';
	import { indicatorCapable, CHANNEL_COL_BUDGET } from '../../trip-detail/metricsEditor.ts';
	import type { Highlight } from '../../trip-detail/metricsEditor.ts';
	import { Segmented } from '$lib/components/atoms';
	import LTCutLine from '$lib/components/shared/layout-tab/LTCutLine.svelte';
	import SortableList from '$lib/components/shared/dnd/SortableList.svelte';
	import DragHandle from '$lib/components/shared/dnd/DragHandle.svelte';
	// Issue #1888 (E6 Scheibe B, Staging-Befund): die Legende sitzt in DERSELBEN
	// Komponente wie die Marken und wird aus DENSELBEN Props gespeist. Vorher
	// hing sie einmalig in WeatherMetricsTab am Reihenfolge-Block — die Seite
	// traegt aber mehrere Marken-Bloecke (Trip: Reihenfolge + Ausblick;
	// Vergleich: zusaetzlich Stundenverlauf), und deren Marken blieben
	// unerklaert. Hier ist „Marke ohne Erklaerung" baulich unmoeglich statt nur
	// getestet: jeder Block bringt seine Legende mit.
	import { buildKuerzelLegende } from './kuerzelLegende.ts';

	interface Props {
		primaryColumns: string[];
		metricById: Record<string, MetricEntry>;
		friendlyMap: Record<string, boolean>;
		activeChannel: string;
		highlight: Highlight | null;
		onRemove: (id: string) => void;
		onDndReorder: (newOrder: string[]) => void;
		onMode: (id: string, useIndicator: boolean) => void;
		/** Issue #1719 S3: `undefined` = Bauteil verhält sich EXAKT wie bisher
		 *  (keine Aus-Gruppe). Verzweigung auf ANWESENHEIT, nicht auf `.length`
		 *  — ein leeres Array heißt "übergeben, aktuell nichts Aus", das ist
		 *  etwas anderes als "nicht übergeben" (kein Default-Wert hier). */
		offColumns?: string[];
		onRestore?: (id: string) => void;
		/** Issue #1719 S4: ALLE Kürzel, die der Kanal DIESER Fläche für eine
		 *  Größe sendet (metric_id -> Kürzel-Liste). Die Quelle richtet sich
		 *  nach der Fläche und wird deshalb von der Einbettung geliefert, nicht
		 *  hier bestimmt: der Touren-Editor reicht `/api/sms-symbols` durch
		 *  (Mehrfach-Token `FK FD WC`, Grammatikformen), die drei
		 *  Vergleichs-Editoren das Register-Kürzel `sms_code` — die
		 *  Vergleichs-SMS rendert aus `get_sms_code()` (comparison.py). Eine
		 *  flächenblinde Quelle würde den Vergleich falsch beschriften. Größen
		 *  ohne Eintrag bekommen GAR KEINE Marke, keine leere (AC-9). */
		kuerzelById: Record<string, string[]>;
		/** Issue #2049: welche Groessen einen Roh/Einfach-Umschalter bekommen.
		 *  Ohne Uebergabe bleibt es bei `indicatorCapable()` — der Kanal-Reiter
		 *  (Stundentabelle der Mail) verhaelt sich damit unveraendert. Der
		 *  3-Tages-Ausblick uebergibt seine EIGENE Liste
		 *  (`outlookFriendlyCapable`), weil dort andere Groessen eine
		 *  Einfach-Form haben (kein `thunder`/`cape`, dafuer `sunshine`) und
		 *  weil Sichtbarkeit und Backend-Wirkung an derselben Quelle haengen
		 *  muessen. */
		modeCapable?: (id: string) => boolean;
	}

	let {
		primaryColumns, metricById, friendlyMap, activeChannel, highlight, onRemove, onDndReorder, onMode,
		offColumns, onRestore, kuerzelById, modeCapable = indicatorCapable,
	}: Props = $props();

	const tgBudget = CHANNEL_COL_BUDGET.telegram;
	const showCutLine = $derived(activeChannel === 'telegram');

	function itemLabel(id: string, i: number): string {
		return `${i + 1}. ${metricById[id]?.label ?? id}`;
	}

	// Issue #1888: die Zeilen der Kuerzel-Legende dieses Blocks — aus GENAU den
	// Groessen, die er zeigt (sortierbare Liste plus Aus-Gruppe), und aus GENAU
	// den Props, aus denen auch die Marken kommen. Damit kann die Legende nicht
	// von den Marken daneben abweichen.
	const legende = $derived(
		buildKuerzelLegende([...primaryColumns, ...(offColumns ?? [])], kuerzelById, metricById)
	);
</script>

<div class="reihenfolge" data-testid="wm2-reihenfolge">
	<div class="section-subhead">
		Reihenfolge
		<span class="count">· {primaryColumns.length} Metriken</span>
		<span class="hint-right mono">links → rechts in der Email-Tabelle</span>
	</div>
	<SortableList
		items={primaryColumns}
		{onDndReorder}
		ariaLabel="Metriken, Reihenfolge"
		{itemLabel}
	>
		{#snippet row(id: string, i: number)}
			{@const m = metricById[id]}
			{@const hl = highlight && highlight.id === id}
			{@const hasInd = modeCapable(id)}
			{@const useIndicator = friendlyMap[id] === true}
			{@const kurzform = kuerzelById[id]}
			{#if showCutLine && i === tgBudget}
				<div data-testid="wm2-cut-line">
					<LTCutLine label="Telegram" max={tgBudget} />
				</div>
			{/if}
			<div class="row" class:hl data-testid="wm2-reihenfolge-row" data-metric-id={id}>
				<div class="pos mono">{i + 1}</div>
				<DragHandle size={14} />
				<div class="label-cell">
					{#if m}
						<span class="metric-label">{m.label}</span>
						{#if m.unit}
							<span class="metric-unit mono">{m.unit}</span>
						{/if}
						{#if m.aggregation_label}
							<!-- Issue #1401 (A1): Auswertung als eigenes Element neben dem
							     Namen. Nur im Ortsvergleich gesetzt — im Trip fehlt das
							     Feld, dort bleibt die Zeile unveraendert. -->
							<span class="aggregation-badge" data-testid="wm2-aggregation-badge">{m.aggregation_label}</span>
						{/if}
						<!-- Issue #1453 (AC-7) / #1719 S4: alle DREI Namensformen
						     nebeneinander — ausgeschriebener deutscher Name (oben),
						     englische Fachkurzform der Mail-Stundentabelle und ALLE
						     Kuerzel der Kurzform. Seit S4 tragen die Marken ihre
						     Beschriftung SICHTBAR ("Mail"/"Kurzform"): ein blosses
						     "TF" ist nicht aufloesbar, solange der Nutzer nicht
						     weiss, ob es in seiner Mail oder in seiner SMS steht. -->
						{#if m.col_label}
							<span class="col-badge" data-testid="wm2-mail-badge" title="Kurzform in der Mail-Stundentabelle">
								<span class="badge-key">Mail</span>
								<span class="badge-val mono">{m.col_label}</span>
							</span>
						{/if}
						{#if kurzform && kurzform.length}
							<span class="kurzform-badge" data-testid="wm2-kurzform-badge" title="Kürzel in SMS, Premium-SMS und Telegram">
								<span class="badge-key">Kurzform</span>
								<span class="badge-val mono">{kurzform.join(' ')}</span>
							</span>
						{/if}
					{:else}
						<span class="metric-label">{id}</span>
					{/if}
				</div>
				<div class="controls">
					{#if hasInd}
						<Segmented
							size="sm"
							value={useIndicator ? 'indicator' : 'raw'}
							onChange={(v: string) => onMode(id, v === 'indicator')}
							items={[{ id: 'raw', label: 'Roh' }, { id: 'indicator', label: 'Einfach' }]}
						/>
					{/if}
					<button
						type="button"
						class="btn-aus"
						onclick={() => onRemove(id)}
						title="Aus Briefing entfernen"
					>
						Aus
					</button>
				</div>
			</div>
		{/snippet}
	</SortableList>
	{#if offColumns !== undefined}
		<div class="aus-gruppe" data-testid="wm2-aus-gruppe">
			<div class="section-subhead aus-subhead">Aus in diesem Kanal</div>
			{#each offColumns as id (id)}
				{@const m = metricById[id]}
				{@const kurzform = kuerzelById[id]}
				<div class="row aus-row" data-testid="wm2-aus-row" data-metric-id={id}>
					<div class="label-cell">
						{#if m}
							<span class="metric-label">{m.label}</span>
							{#if m.unit}
								<span class="metric-unit mono">{m.unit}</span>
							{/if}
							{#if m.aggregation_label}
								<span class="aggregation-badge" data-testid="wm2-aggregation-badge">{m.aggregation_label}</span>
							{/if}
							{#if m.col_label}
								<span class="col-badge" data-testid="wm2-mail-badge" title="Kurzform in der Mail-Stundentabelle">
									<span class="badge-key">Mail</span>
									<span class="badge-val mono">{m.col_label}</span>
								</span>
							{/if}
							{#if kurzform && kurzform.length}
								<span class="kurzform-badge" data-testid="wm2-kurzform-badge" title="Kürzel in SMS, Premium-SMS und Telegram">
									<span class="badge-key">Kurzform</span>
									<span class="badge-val mono">{kurzform.join(' ')}</span>
								</span>
							{/if}
						{:else}
							<span class="metric-label">{id}</span>
						{/if}
					</div>
					<div class="controls">
						<button
							type="button"
							class="btn-ein"
							onclick={() => onRestore?.(id)}
							title="Wieder ins Briefing aufnehmen"
						>
							Ein
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
	<!-- Issue #1888 (E6 Scheibe B): Legende zu den Marken DIESES Blocks. Sie
	     steht hier und nicht beim Aufrufer, damit jeder Marken-Block sie
	     mitbringt — der Staging-Befund entstand daran, dass eine einzelne
	     Legende weiter oben die Marken der Bloecke „Ausblick" und
	     „Stundenverlauf" nicht abdeckte. Fail-soft wie die Warnungs-Legende:
	     ohne Zeilen erscheint gar nichts, statt einer leeren Liste (AC-4). -->
	{#if legende.eintraege.length}
		<div data-testid="metric-kuerzel-legend" class="kuerzel-legende text-xs">
			<p>So heißen diese Größen in SMS und Telegram-Kurzform:</p>
			<ul class="legend-symbols">
				{#each legende.eintraege as eintrag, i (eintrag.kuerzel + ' ' + eintrag.bedeutung + ' ' + i)}
					<li data-testid="metric-kuerzel-legend-row"><code>{eintrag.kuerzel}</code> <span>{eintrag.bedeutung}</span></li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<style>
	/* Issue #1888: Kuerzel-Legende. Farbe bewusst --g-ink-muted (6,91:1 auf
	   Weiss, im Browser gegen Staging gemessen) und NICHT --g-ink-4 (2,85:1) —
	   Design-Leitprinzip: --g-ink-4 nur fuer Placeholder/Disabled, nie fuer
	   Daten-Labels (AC-7, WCAG AA 4.5:1).
	   Umbruch statt Ueberlauf: die Zeilen fliessen und brechen innerhalb des
	   Blocks, damit auch bei 320 px nichts abgeschnitten wird (AC-6). */
	.kuerzel-legende {
		color: var(--g-ink-muted);
		line-height: 1.5;
		padding: 10px 16px 14px;
		border-top: 1px solid var(--g-rule-soft);
	}
	.kuerzel-legende p {
		margin: 0 0 4px;
	}
	.kuerzel-legende .legend-symbols {
		display: flex;
		flex-wrap: wrap;
		column-gap: 16px;
		row-gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.kuerzel-legende li {
		display: flex;
		gap: 6px;
		max-width: 100%;
	}
	.kuerzel-legende code {
		flex: none;
		font-weight: 600;
	}
	.kuerzel-legende li span {
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.reihenfolge {
		display: flex;
		flex-direction: column;
		gap: 0;
	}
	.section-subhead {
		display: flex;
		align-items: baseline;
		gap: 0;
		padding: 14px 16px 10px;
		border-bottom: 1px solid var(--g-rule-soft);
		font-size: 16px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.count {
		color: var(--g-ink-4);
		font-weight: 400;
		font-size: 13px;
		margin-left: 4px;
	}
	.hint-right {
		font-size: 10px;
		color: var(--g-ink-4);
		margin-left: auto;
	}
	.row {
		display: grid;
		grid-template-columns: 28px 16px 1fr auto;
		gap: 10px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--g-rule-soft);
		border-top: 2px solid transparent;
		align-items: center;
		background: transparent;
		transition: background 0.15s;
		cursor: grab;
	}
	.row:active {
		cursor: grabbing;
	}
	.row.hl {
		background: var(--g-accent-tint);
	}
	.pos {
		font-size: 11px;
		font-weight: 600;
		color: var(--g-ink-4);
		text-align: right;
	}
	.label-cell {
		display: flex;
		align-items: baseline;
		gap: 0;
		min-width: 0;
	}
	/* Issue #1719 S4: `min-width: 0` ist der eigentliche Fix — ohne ihn hat ein
	   Flex-Element `min-width: auto` (= min-content, bei `nowrap` die volle
	   Textbreite) und kann NICHT schrumpfen. Die Zelle holte sich den fehlenden
	   Platz stattdessen bei den Marken, deren Inhalt dadurch beschnitten wurde.
	   Bei Platzmangel kuerzt jetzt der NAME, nie ein Kuerzel: der Name ist der
	   Klartext und bleibt auch angerissen erkennbar, das Kuerzel daneben ist
	   die Aufloesung und waere beschnitten wertlos. */
	.metric-label {
		font-size: 13.5px;
		font-weight: 500;
		color: var(--g-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
		flex-shrink: 1;
	}
	.metric-unit {
		font-size: 10.5px;
		color: var(--g-ink-4);
		margin-left: 6px;
		white-space: nowrap;
	}
	/* Issue #1401: Auswertung — eigenes Element, gleiches Badge-Muster wie
	   col-badge, aber ohne Mono (deutscher Fliesstext, kein Kuerzel). */
	.aggregation-badge {
		font-size: 10.5px;
		color: var(--g-ink-3);
		background: var(--g-paper);
		border: 1px solid var(--g-rule-soft);
		border-radius: 3px;
		padding: 0 5px;
		margin-left: 6px;
		line-height: 1.6;
		white-space: nowrap;
	}
	/* Issue #1719 S4: die beiden Marken sind UNVERKUERZBAR. `flex-shrink: 0`
	   plus `white-space: nowrap` ist die Zusicherung aus AC-12 — nimmt man sie
	   heraus, wird der Inhalt der Marke zusammengedrueckt (`scrollWidth >
	   clientWidth`) und der Browser-Nachweis rot. Das war der gemessene Defekt:
	   unter 900px rettete `flex-wrap: wrap` alles, ab 900px gab es keinen
	   Umbruch, und den Marken fehlte `flex-shrink: 0`. */
	.col-badge,
	.kurzform-badge {
		font-size: 10px;
		color: var(--g-ink-3);
		background: var(--g-paper);
		border: 1px solid var(--g-rule-soft);
		border-radius: 3px;
		padding: 0 4px;
		line-height: 1.6;
		white-space: nowrap;
		flex-shrink: 0;
	}
	.col-badge {
		margin-left: 6px;
	}
	.kurzform-badge {
		margin-left: 4px;
	}
	/* Die Beschriftung gehoert IN die Marke, nicht ins title-Attribut: ein
	   Kuerzel ohne sichtbare Herkunft ist nicht aufloesbar (der Nutzer weiss
	   sonst nicht, ob "TF" in seiner Mail oder in seiner Kurzform steht).
	   Unterscheidung ueber Schriftschnitt statt Farbe -- --g-ink-4 waere hier
	   Hilfstext und ist dafuer gesperrt (Design-Leitprinzipien). */
	.badge-key {
		font-weight: 600;
	}
	.badge-val {
		font-weight: 500;
	}
	.controls {
		display: flex;
		gap: 8px;
		align-items: center;
		justify-content: flex-end;
		flex-wrap: wrap;
	}
	.btn-aus {
		padding: 5px 9px;
		font-size: 11.5px;
		font-family: inherit;
		font-weight: 500;
		border: 1px solid rgba(168, 50, 50, 0.35);
		border-radius: 3px;
		background: var(--g-card);
		color: var(--g-bad);
		cursor: pointer;
		white-space: nowrap;
	}
	.btn-aus:hover {
		background: rgba(168, 50, 50, 0.06);
	}
	/* Issue #1719 S3: "Aus in diesem Kanal"-Gruppe — nicht sortierbar, daher
	   ohne Positionsnummer/Ziehgriff (die würden nichts bedeuten, das
	   Datenmodell kennt für Aus-Metriken keine Reihenfolge). */
	.aus-gruppe {
		border-top: 1px solid var(--g-rule-soft);
	}
	.aus-subhead {
		padding: 12px 16px 6px;
		font-size: 12.5px;
		font-weight: 600;
		color: var(--g-ink-3);
	}
	.row.aus-row {
		grid-template-columns: 1fr auto;
		cursor: default;
		opacity: 0.75;
	}
	.btn-ein {
		padding: 5px 9px;
		font-size: 11.5px;
		font-family: inherit;
		font-weight: 500;
		border: 1px solid rgba(61, 107, 58, 0.35);
		border-radius: 3px;
		background: var(--g-card);
		color: var(--g-good);
		cursor: pointer;
		white-space: nowrap;
	}
	.btn-ein:hover {
		background: rgba(61, 107, 58, 0.06);
	}
	@media (max-width: 899px) {
		.metric-label {
			white-space: normal;
			overflow: visible;
			text-overflow: clip;
		}
		.label-cell {
			flex-wrap: wrap;
		}
		/* Issue #1719 S4, Notausgang fuer schmale Fenster (320px): hier bricht
		   die Zelle ohnehin um. Reicht eine ganze Zeile fuer eine Marke nicht
		   aus, bricht sie ZWISCHEN ihren Kuerzeln um (`normal` bricht nur an
		   Leerzeichen, `overflow-wrap: normal` nie innerhalb eines Kuerzels) --
		   statt aus der Zeile zu ragen und die Seite waagerecht scrollen zu
		   lassen. Alle Zeichen bleiben sichtbar, nur eben zweizeilig. Bewusst
		   NUR hier: ab 900px muessen die Marken einzeilig und unverkuerzbar
		   bleiben, sonst waere die Gegenprobe zu AC-12 blind. */
		.col-badge,
		.kurzform-badge {
			white-space: normal;
			overflow-wrap: normal;
			max-width: 100%;
		}
		.controls {
			flex-direction: column;
			align-items: flex-end;
			gap: 4px;
		}
	}
</style>
