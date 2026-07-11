/* ════════════════════════════════════════════════════════════════════════
 *  VERSAND-TAB — der geteilte Versand-Organism (Epic #29, Phase 4)
 * ════════════════════════════════════════════════════════════════════════
 *
 *  EIN Organism für beide Editoren. Ersetzt:
 *    - Compare-Editor · Versand-Tab       (CE_VersandTab   / CEM_VersandTab)
 *    - Trip-Editor    · Briefing-Zeitplan (TE2_ZeitplanTab / TM2_ZeitplanTab)
 *      + die notify-Zustellung, die bislang im Wertebereiche-Tab lag
 *      (AlertChannelPicker + Cooldown + Stille Stunden + Beispiel-Warnung).
 *
 *  Beide Editoren droppen nur <VersandTab context="route" | "vergleich" dense?/>.
 *  Kein Fork — Desktop + dense-Mobile über dasselbe Component.
 *
 *  Zusammensetzung (PO 2026-07-11, Phase 4):
 *    · Geplantes Briefing · Kanäle   — ChannelRow-Liste (an/aus)         · beide
 *    · Rhythmus / Zeitplan           — route: konfigurierbare Karten     · route ⊕
 *                                       vergleich: festes Zeitfenster-Info
 *    · Laufzeit                      — vergleich: editierbar (endDate)    · beide
 *                                       route: read-only aus Etappen
 *    · Alert-Zustellung (notify)     — AlertChannelPicker + Cooldown +
 *                                       Stille Stunden + Beispiel-Warnung · beide
 *
 *  Warum die ganze notify-Zustellung hier liegt (PO): EIN Ort für alles, was
 *  rausgeht. Der Wertebereiche-Tab ist dadurch rein der Korridor-Editor.
 *
 *  Lade-Reihenfolge:  … molecules · corridor-editor(-mobile) → versand-tab.jsx
 *  Prefix-Disziplin (CLAUDE.md): lokale Helfer tragen VT_-Prefix.
 *  Reuse (window): ChannelRow, Card, Btn, Eyebrow, Dot, TopoBg, Switch,
 *    ScreenScroll, MBtn, MSwitch, CompareEndDateControl(Mobile),
 *    AlertChannelPicker.
 * ──────────────────────────────────────────────────────────────────────── */

/* ─── Kontext-Copy ─── */
const VERSAND_CTX = {
  route: {
    crumbSubject: "Etappen",
    briefingLead: "Das Trip-Briefing ist eine Etappen-Tabelle — E-Mail trägt alle Spalten, Telegram die ersten 8, SMS läuft flach.",
    alertSubjectLabel: "Etappe · Zeitraum",
    alertHeadline: "KHW 403",
  },
  vergleich: {
    crumbSubject: "Orte",
    briefingLead: "Der Orts-Vergleich ist eine breite Tabelle — realistisch läuft er per E-Mail. Telegram trägt nur ≤ 8 Spalten, SMS wird flach.",
    alertSubjectLabel: "Ort · Zeitraum",
    alertHeadline: "Skitouren Hochkönig",
  },
};

const VT_CHANNEL_META = {
  email:    { label: "Email",    target: "gregor_zwanzig@henemm.com" },
  telegram: { label: "Telegram", target: "@henemm" },
  sms:      { label: "SMS",      target: "+49 151 12345 678" },
};

/* ═══════════ Kleine geteilte Bausteine ═══════════ */

/* Abschnitts-Label — Desktop = Eyebrow, dense = Mono-Caps-Zeile. */
function VT_Label({ children, dense, style }) {
  if (dense) {
    return (
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10, ...style }}>{children}</div>
    );
  }
  return <Eyebrow style={{ marginBottom: 10, ...style }}>{children}</Eyebrow>;
}

/* ─── Geplantes Briefing · Kanäle (an/aus) ─── */
function VT_BriefingChannels({ context, dense, channels, onToggle }) {
  const ctx = VERSAND_CTX[context] || VERSAND_CTX.route;
  const subFor = {
    email:    "Layout · volle Tabelle",
    telegram: "Layout · 8 Spalten",
    sms:      "Layout · flach, ≤ 140 Z.",
  };
  const order = ["email", "telegram", "sms"];
  return (
    <div>
      <VT_Label dense={dense}>Geplantes Briefing · Kanäle</VT_Label>
      <div style={{ fontSize: dense ? 12.5 : 12.5, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: dense ? 10 : 12, maxWidth: 620 }}>{ctx.briefingLead}</div>
      <Card padding={0}>
        <div style={{ padding: dense ? "2px 14px" : "4px 18px" }}>
          {order.map((k, i) => (
            <ChannelRow key={k} kind={VT_CHANNEL_META[k].label} target={VT_CHANNEL_META[k].target}
              active={!!channels[k]} sub={subFor[k]} onToggle={() => onToggle(k)}
              dense last={i === order.length - 1}/>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* VT_ZeitfensterInfo ENTFERNT (PO 2026-07-11): „Rhythmus" + „rollierend, jedes
 * Wochenende" waren kein gewolltes Feature. Der Vergleich-Versand funktioniert
 * identisch zum Trip — nur Briefing-Uhrzeiten (Morgen = heutiger Tag, Abend =
 * morgen), siehe VT_SchedulePlan(context="vergleich"). */

/* ─── Briefing-Zeitplan · Trip UND Vergleich (nur Uhrzeit wählen) ─── */
const VT_SCHEDULE_SEED = {
  route: [
    { id: "morning", title: "Morgen-Briefing", time: "06:00",    sub: "Gleicher Tag — alles für die heutige Etappe", on: true,  ch: { email: true, telegram: true, sms: false } },
    { id: "evening", title: "Abend-Briefing",  time: "18:00",    sub: "Nächster Tag — Ausblick auf morgen",         on: true,  ch: { email: true, telegram: false, sms: false } },
    { id: "trend",   title: "Mehrtages-Trend", time: "18:00", sub: "Sonntags · 3–7-Tage-Ausblick (optional)",       on: false, ch: { email: true, telegram: false, sms: false } },
  ],
  vergleich: [
    { id: "morning", title: "Morgen-Briefing", time: "07:00", sub: "Gleicher Tag — heutige Lage an allen Orten", on: true, ch: { email: true, telegram: false, sms: false } },
    { id: "evening", title: "Abend-Briefing",  time: "18:00", sub: "Nächster Tag — Ausblick auf morgen",         on: true, ch: { email: true, telegram: false, sms: false } },
  ],
};
function VT_SchedulePlan({ dense, activeChannels, context = "route" }) {
  const chLabel = { email: "Email", telegram: "Telegram", sms: "SMS" };
  const [cards, setCards] = React.useState(VT_SCHEDULE_SEED[context] || VT_SCHEDULE_SEED.route);
  React.useEffect(() => { setCards(VT_SCHEDULE_SEED[context] || VT_SCHEDULE_SEED.route); }, [context]);
  const toggleCard = (id) => setCards(cs => cs.map(c => c.id === id ? { ...c, on: !c.on } : c));
  const toggleCh   = (id, k) => setCards(cs => cs.map(c => c.id === id ? { ...c, ch: { ...c.ch, [k]: !c.ch[k] } } : c));
  const setTime    = (id, v) => setCards(cs => cs.map(c => c.id === id ? { ...c, time: v } : c));

  if (activeChannels.length === 0) {
    return (
      <div>
        <VT_Label dense={dense}>Briefing-Zeitplan</VT_Label>
        <div style={{ padding: dense ? "16px 14px" : "18px 20px", background: "rgba(192,138,26,0.07)", border: "1px solid var(--g-warn)", borderRadius: "var(--g-r-2)", fontSize: dense ? 13 : 14, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
          <strong style={{ color: "#8a6210" }}>Kein Kanal aktiv.</strong> Aktiviere oben mindestens einen Briefing-Kanal, damit hier Zeitplan-Optionen erscheinen.
        </div>
      </div>
    );
  }

  return (
    <div>
      <VT_Label dense={dense}>Briefing-Zeitplan</VT_Label>
      {context === "vergleich" && (
        <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: dense ? 10 : 12, maxWidth: 620 }}>
          Wie beim Trip: das <strong style={{ color: "var(--g-ink-2)" }}>Morgen-Briefing</strong> zeigt den heutigen Tag, das <strong style={{ color: "var(--g-ink-2)" }}>Abend-Briefing</strong> den morgigen. Du wählst nur die Uhrzeit.
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: dense ? "1fr" : "1fr 1fr", gap: dense ? 10 : 16 }}>
        {cards.map(c => (
          <Card key={c.id} padding={dense ? 14 : 18}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div>
                <div style={{ fontSize: dense ? 14 : 15, fontWeight: 600 }}>{c.title}</div>
                <div style={{ fontSize: dense ? 12 : 12.5, color: "var(--g-ink-3)", marginTop: 2 }}>{c.sub}</div>
              </div>
              {dense
                ? <MSwitch checked={c.on} onChange={() => toggleCard(c.id)}/>
                : <Switch checked={c.on} onChange={() => toggleCard(c.id)} tone="good"/>}
            </div>
            <div style={{ marginTop: dense ? 12 : 14, paddingTop: 12, borderTop: "1px solid var(--g-rule-soft)", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                <span className="mono" style={{ fontSize: dense ? 9 : 9.5, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Uhrzeit</span>
                <input type="time" value={c.time} disabled={!c.on} onChange={e => setTime(c.id, e.target.value)}
                  style={{
                    fontFamily: "var(--g-font-mono)", fontSize: 13, fontWeight: 600,
                    color: c.on ? "var(--g-ink)" : "var(--g-ink-4)",
                    background: c.on ? "var(--g-card)" : "var(--g-paper-deep)",
                    border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-1)",
                    padding: dense ? "8px 8px" : "5px 8px", minHeight: dense ? 40 : "auto",
                    cursor: c.on ? "text" : "not-allowed", colorScheme: "light",
                  }}/>
              </label>
              <span style={{ flex: 1 }}/>
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {activeChannels.map(k => (
                  <button key={k} onClick={() => toggleCh(c.id, k)} style={{
                    fontSize: dense ? 13 : 12, fontWeight: 500, padding: dense ? "6px 12px" : "4px 10px", borderRadius: 4, cursor: "pointer",
                    minHeight: dense ? 36 : "auto",
                    border: `1px solid ${c.ch[k] ? "var(--g-ink)" : "var(--g-rule)"}`,
                    background: c.ch[k] ? "var(--g-ink)" : "var(--g-paper-deep)",
                    color: c.ch[k] ? "var(--g-paper)" : "var(--g-ink-4)",
                  }}>{chLabel[k]}</button>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ─── Laufzeit · route = read-only aus Etappen ─── */
function VT_LaufzeitRoute({ dense, tripEnd, onOpenStages }) {
  return (
    <div>
      <VT_Label dense={dense}>Laufzeit</VT_Label>
      <div style={{ padding: dense ? "14px" : "16px 20px", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--g-good)", flexShrink: 0 }}/>
        <div style={{ flex: 1, minWidth: 180 }}>
          <div style={{ fontSize: dense ? 14 : 14.5, fontWeight: 600, color: "var(--g-ink)" }}>Läuft mit der Tour · endet {tripEnd}</div>
          <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 3, lineHeight: 1.5 }}>
            Das Enddatum ergibt sich aus den Etappen — es wird dort gepflegt, nicht hier.
          </div>
        </div>
        <button onClick={onOpenStages} style={{
          background: "transparent", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
          padding: dense ? "10px 12px" : "7px 12px", minHeight: dense ? 44 : "auto",
          cursor: "pointer", color: "var(--g-ink-2)", fontFamily: "var(--g-font-sans)", fontSize: 12.5, fontWeight: 500, whiteSpace: "nowrap",
        }}>Etappen öffnen →</button>
      </div>
    </div>
  );
}

/* ─── Alert-Zustellung (notify) · Cooldown + Stille Stunden ─── */
function VT_AlertTiming({ dense }) {
  const [cooldown, setCooldown] = React.useState(60);
  const [quietFrom, setQuietFrom] = React.useState("22:00");
  const [quietTo, setQuietTo] = React.useState("06:00");
  const numStyle = {
    width: dense ? 72 : 64, padding: dense ? "10px" : "6px 8px", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-1)",
    fontSize: dense ? 16 : 13, fontFamily: "var(--g-font-mono)", textAlign: "right", minHeight: dense ? 44 : "auto", boxSizing: "border-box",
  };
  const txtStyle = { ...numStyle, textAlign: "left" };
  return (
    <div>
      <VT_Label dense={dense}>Wann Warnungen rausgehen</VT_Label>
      <div style={{ display: "grid", gridTemplateColumns: dense ? "1fr" : "1fr 1fr", gap: dense ? 12 : 16, maxWidth: dense ? "none" : 560 }}>
        <Card padding={dense ? 14 : 16}>
          <VT_Label dense style={{ marginBottom: 8 }}>Cooldown</VT_Label>
          <div style={{ fontSize: dense ? 13 : 12, color: "var(--g-ink-3)", marginBottom: dense ? 10 : 12, lineHeight: 1.5 }}>
            Mindestabstand zwischen zwei Warnungen derselben Metrik — verhindert Spam bei schwankenden Werten.
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="number" value={cooldown} onChange={e => setCooldown(e.target.value)} style={numStyle}/>
            <span className="mono" style={{ fontSize: dense ? 13 : 12, color: "var(--g-ink-3)" }}>Minuten</span>
          </div>
        </Card>
        <Card padding={dense ? 14 : 16}>
          <VT_Label dense style={{ marginBottom: 8 }}>Stille Stunden</VT_Label>
          <div style={{ fontSize: dense ? 13 : 12, color: "var(--g-ink-3)", marginBottom: dense ? 10 : 12, lineHeight: 1.5 }}>
            In diesem Zeitraum keine Warnungen — gestaute Warnungen gehen mit dem nächsten Morgen-Briefing mit.
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="text" value={quietFrom} onChange={e => setQuietFrom(e.target.value)} style={txtStyle}/>
            <span className="mono" style={{ fontSize: dense ? 13 : 12, color: "var(--g-ink-3)" }}>–</span>
            <input type="text" value={quietTo} onChange={e => setQuietTo(e.target.value)} style={txtStyle}/>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ─── Beispiel-Warnung (kontext-abhängiges Subjekt) ─── */
const VT_ALERT_SAMPLE = {
  route: [
    { metric: "Gewitter",   from: "15 %",    to: "60 %",    subject: "Etappe 3 · 14–18 Uhr" },
    { metric: "Böen",       from: "45 km/h", to: "72 km/h", subject: "Etappe 3 · 14–16 Uhr" },
    { metric: "Sichtweite", from: "15 km",   to: "6 km",    subject: "Etappe 3 · 14–18 Uhr" },
  ],
  vergleich: [
    { metric: "Wind (Mittel)", from: "22 km/h", to: "48 km/h", subject: "Aberg · Fr 14–18 Uhr" },
    { metric: "Neuschnee",     from: "5 cm",    to: "18 cm",   subject: "Dientalm · Fr–Sa" },
    { metric: "Sichtweite",    from: "12 km",   to: "4 km",    subject: "Karbachalm · Sa 09–12" },
  ],
};
function VT_AlertSample({ context, dense }) {
  const ctx = VERSAND_CTX[context] || VERSAND_CTX.route;
  const rows = VT_ALERT_SAMPLE[context] || VT_ALERT_SAMPLE.route;
  return (
    <div>
      <VT_Label dense={dense} style={{ marginBottom: 4 }}>Beispiel-Warnung</VT_Label>
      <div style={{ fontSize: dense ? 12.5 : 13, color: "var(--g-ink-3)", marginBottom: dense ? 10 : 14, lineHeight: 1.5 }}>
        So sieht eine ausgelöste Warn-Mail aus, wenn ein Wert den Wertebereich verlässt.
      </div>
      <div style={{ background: "#fff", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", maxWidth: dense ? "none" : 560, overflow: "hidden", fontFamily: "Helvetica, Arial, sans-serif" }}>
        <div style={{ background: "var(--g-accent)", color: "#fff", padding: dense ? "11px 14px" : "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div className="mono" style={{ fontSize: dense ? 9.5 : 10, letterSpacing: "0.1em", opacity: 0.9 }}>ALERT · {ctx.alertHeadline}</div>
            <div style={{ fontSize: dense ? 15 : 16, fontWeight: 600, marginTop: 2 }}>Wetter-Änderung erkannt</div>
          </div>
          <div className="mono" style={{ fontSize: dense ? 9.5 : 10, opacity: 0.9, textAlign: "right", lineHeight: 1.5 }}>Mi 14.05.<br/>14:23</div>
        </div>
        {dense ? (
          <div>
            {rows.map((r, i) => (
              <div key={r.metric} style={{ padding: "10px 14px", borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)" }}>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)" }}>{r.metric}</span>
                  <span className="mono" style={{ fontSize: 12.5 }}>
                    <span style={{ color: "var(--g-ink-3)" }}>{r.from}</span>
                    <span style={{ color: "var(--g-ink-4)", margin: "0 5px" }}>→</span>
                    <span style={{ color: "var(--g-accent-deep)", fontWeight: 600 }}>{r.to}</span>
                  </span>
                </div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 2 }}>{r.subject}</div>
              </div>
            ))}
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontVariantNumeric: "tabular-nums" }}>
            <thead>
              <tr style={{ background: "rgba(196,90,42,0.05)" }}>
                <th style={{ textAlign: "left", padding: "8px 18px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.04em" }}>Metrik</th>
                <th style={{ textAlign: "right", padding: "8px 8px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>Vorher</th>
                <th style={{ textAlign: "right", padding: "8px 8px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>Nachher</th>
                <th style={{ textAlign: "left", padding: "8px 18px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>{ctx.alertSubjectLabel}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.metric} style={{ borderTop: "1px solid var(--g-rule-soft)" }}>
                  <td style={{ padding: "9px 18px", fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>{r.metric}</td>
                  <td className="mono" style={{ padding: "9px 8px", fontSize: 12, textAlign: "right", color: "var(--g-ink-3)" }}>{r.from}</td>
                  <td className="mono" style={{ padding: "9px 8px", fontSize: 12, textAlign: "right", color: "var(--g-accent-deep)", fontWeight: 600 }}>{r.to}</td>
                  <td className="mono" style={{ padding: "9px 18px", fontSize: 11, color: "var(--g-ink-3)" }}>{r.subject}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ─── Alert-Zustellung (gesamter Block: Kanäle + Timing + Beispiel) ─── */
function VT_AlertDelivery({ context, dense }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: dense ? 18 : 28, maxWidth: dense ? "none" : 620 }}>
      <AlertChannelPicker dense={dense}/>
      <VT_AlertTiming dense={dense}/>
      <VT_AlertSample context={context} dense={dense}/>
    </div>
  );
}

/* ════════════════════ VersandTab — DER Organism ════════════════════
 *  Props:
 *    context       "route" | "vergleich"
 *    dense         true → Mobile-Layout (ScreenScroll-Wrapper)
 *    channels      optional controlled { email, telegram, sms }
 *    onChannels    optional setter (bekommt das neue Objekt)
 *    endDate/onEndDate  optional controlled (vergleich-Laufzeit)
 *    tripEnd       route-Enddatum (read-only), default "14.06.2026"
 *    onOpenStages  route: Sprung zum Etappen-Tab
 *    activation    optional ReactNode am Ende (Compare-Aktivieren-Banner)
 */
function VersandTab({
  context = "route", dense = false,
  channels: channelsProp, onChannels,
  endDate: endDateProp, onEndDate,
  tripEnd = "14.06.2026", onOpenStages,
  activation,
}) {
  const isRoute = context === "route";

  /* Briefing-Kanäle: controlled oder self-managed */
  const defaultChannels = isRoute
    ? { email: true, telegram: true, sms: false }
    : { email: true, telegram: false, sms: false };
  const [chLocal, setChLocal] = React.useState(channelsProp || defaultChannels);
  React.useEffect(() => { if (!channelsProp) setChLocal(isRoute ? { email: true, telegram: true, sms: false } : { email: true, telegram: false, sms: false }); }, [context]);
  const channels = channelsProp || chLocal;
  const toggleChannel = (k) => {
    const next = { ...channels, [k]: !channels[k] };
    if (onChannels) onChannels(next); else setChLocal(next);
  };
  const activeChannels = ["email", "telegram", "sms"].filter(k => channels[k]);

  /* Laufzeit (vergleich) */
  const [endLocal, setEndLocal] = React.useState(endDateProp ?? null);
  const endDate = endDateProp !== undefined ? endDateProp : endLocal;
  const setEnd = (v) => { if (onEndDate) onEndDate(v); else setEndLocal(v); };

  const gap = dense ? 22 : 30;

  /* Sektionen je Kontext, klare Reihenfolge. */
  const sections = isRoute
    ? [
        <VT_BriefingChannels key="ch"    context={context} dense={dense} channels={channels} onToggle={toggleChannel}/>,
        <VT_SchedulePlan     key="plan"  context="route" dense={dense} activeChannels={activeChannels}/>,
        <VT_LaufzeitRoute    key="lauf"  dense={dense} tripEnd={tripEnd} onOpenStages={onOpenStages}/>,
        <VT_AlertDelivery    key="alert" context={context} dense={dense}/>,
      ]
    : [
        <VT_BriefingChannels key="ch"    context={context} dense={dense} channels={channels} onToggle={toggleChannel}/>,
        <VT_SchedulePlan     key="plan"  context="vergleich" dense={dense} activeChannels={activeChannels}/>,
        <VT_LaufzeitVergleich key="lauf" dense={dense} value={endDate} onChange={setEnd}/>,
        <VT_AlertDelivery    key="alert" context={context} dense={dense}/>,
      ];

  const body = (
    <div style={{ display: "flex", flexDirection: "column", gap }}>
      {sections}
      {activation && <div>{activation}</div>}
    </div>
  );

  if (dense) {
    return (
      <ScreenScroll padding={14} style={{ paddingBottom: 24 }}>
        {body}
      </ScreenScroll>
    );
  }

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 900 }}>
        {body}
      </div>
    </div>
  );
}

/* ─── Laufzeit · vergleich = editierbar (CompareEndDateControl) ─── */
function VT_LaufzeitVergleich({ dense, value, onChange }) {
  return (
    <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: dense ? 14 : "20px 22px" }}>
      {dense
        ? <CompareEndDateControlMobile value={value} onChange={onChange}/>
        : <CompareEndDateControl value={value} onChange={onChange}/>}
    </div>
  );
}

/* ─── Export ─── */
Object.assign(window, {
  VersandTab,
  VERSAND_CTX,
  VT_BriefingChannels, VT_SchedulePlan,
  VT_LaufzeitRoute, VT_LaufzeitVergleich,
  VT_AlertTiming, VT_AlertSample, VT_AlertDelivery,
});
