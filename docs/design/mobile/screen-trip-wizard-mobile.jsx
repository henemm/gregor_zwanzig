/* Mobile · Trip-Wizard
 * Pattern: Jeder Schritt = eigener Vollbild-Screen.
 * Sticky Top: Schritt-Indikator + Abbrechen.
 * Sticky Bottom: Zurück / Weiter Action-Bar.
 * Bottom-Nav ausgeblendet (Wizard ist fokussierter Modal-Flow).
 */

const ACTIVITY_PROFILES_M = [
  { id: "trekking",   label: "Trekking & Wandern", sub: "Hütten- & Höhenwanderung", pace: "4 km/h · ↑300 m/h", icon: "▲" },
  { id: "skitour",    label: "Skitour",            sub: "Aufstieg + Abfahrt",       pace: "300 hm/h",          icon: "◆" },
  { id: "alpine",     label: "Hochtour",           sub: "Gletscher, Fels, Eis",     pace: "350 hm/h",          icon: "▲▲" },
  { id: "ferrata",    label: "Klettersteig",       sub: "Gesicherte Routen",        pace: "200 hm/h",          icon: "≈" },
  { id: "mtb",        label: "MTB",                sub: "Mountainbike-Touren",      pace: "12 km/h",           icon: "○○" },
];

function ScreenTripWizardMobile({ initialStep = 1 }) {
  const [step, setStep] = React.useState(initialStep);
  const [profile, setProfile] = React.useState("trekking");
  const trip = MOCK_TRIP;

  const stepTitles = {
    1: "Profil & Eckdaten",
    2: "GPX-Import",
    3: "Wegpunkte",
    4: "Briefings",
  };

  const next = step < 4 ? () => setStep(step + 1) : null;
  const prev = step > 1 ? () => setStep(step - 1) : null;

  const right = (
    <button style={{
      padding: "8px 12px", minHeight: 44, background: "transparent", border: "none",
      fontSize: 14, color: "var(--g-ink-3)", cursor: "pointer", fontWeight: 500,
    }}>Abbrechen</button>
  );

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title={stepTitles[step]}
          eyebrow={`Schritt ${step} von 4 · Neuer Trip`}
          leftIcon={prev ? "back" : "close"}
          right={right}
          onMenu={prev}
        />

        {/* Stepper-Strip */}
        <div style={{
          display: "flex", gap: 4, padding: "8px 16px 12px",
          borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0,
        }}>
          {[1,2,3,4].map(n => (
            <div key={n} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: n <= step ? "var(--g-accent)" : "var(--g-rule)",
            }}/>
          ))}
        </div>

        <ScreenScroll padding={16}>
          {step === 1 && <WStepProfile profile={profile} onProfile={setProfile}/>}
          {step === 2 && <WStepGpx/>}
          {step === 3 && <WStepStages trip={trip}/>}
          {step === 4 && <WStepBriefings/>}
        </ScreenScroll>

        {/* Bottom Action-Bar */}
        <div style={{
          flexShrink: 0, padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8,
        }}>
          {prev && <MBtn variant="ghost" size="lg" onClick={prev} style={{ flex: 1 }}>← Zurück</MBtn>}
          {next ? (
            <MBtn variant="primary" size="lg" onClick={next} style={{ flex: prev ? 1.6 : 1 }}>
              Weiter · {stepTitles[step + 1]} →
            </MBtn>
          ) : (
            <MBtn variant="accent" size="lg" style={{ flex: prev ? 1.6 : 1 }}>
              Trip anlegen
            </MBtn>
          )}
        </div>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Schritt 1 · Profil ─────────────────── */
function WStepProfile({ profile, onProfile }) {
  return (
    <>
      <Card padding={16} style={{ marginBottom: 12 }}>
        <Eyebrow>Trip-Eckdaten</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, marginBottom: 14 }}>Wie soll der Trip heißen?</div>
        <MField label="Trip-Name">
          <MInput defaultValue="Karnischer Höhenweg 403" placeholder="z.B. KHW 2026"/>
        </MField>
        <MField label="Kürzel" sub="Erscheint in Briefing-Header und SMS">
          <MInput defaultValue="KHW 403"/>
        </MField>
        <MField label="Reisezeitraum" sub="Tatsächliche Daten kommen aus den GPX-Files">
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 6, alignItems: "center" }}>
            <MInput defaultValue="06.05.2026"/>
            <span style={{ color: "var(--g-ink-4)", textAlign: "center" }}>–</span>
            <MInput defaultValue="12.05.2026"/>
          </div>
        </MField>
      </Card>

      <Card padding={16}>
        <Eyebrow>Aktivitätsprofil</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, marginBottom: 4 }}>Was für eine Tour?</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 14, lineHeight: 1.5 }}>
          Bestimmt ETA-Tempo an Wegpunkten und schlägt ein passendes Metrikenset für die Briefings vor.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {ACTIVITY_PROFILES_M.map(p => (
            <ProfileChipM key={p.id} profile={p} active={p.id === profile} onClick={() => onProfile(p.id)}/>
          ))}
        </div>
      </Card>
    </>
  );
}

function ProfileChipM({ profile, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "14px 14px", textAlign: "left", cursor: "pointer", minHeight: 56,
      background: active ? "var(--g-accent-tint)" : "var(--g-card-alt)",
      border: active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)",
      display: "flex", alignItems: "center", gap: 12,
    }}>
      <span className="mono" style={{
        width: 36, height: 36, borderRadius: "var(--g-r-2)",
        background: active ? "var(--g-accent)" : "var(--g-paper-deep)",
        color: active ? "#fff" : "var(--g-ink-3)",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 14, flexShrink: 0,
      }}>{profile.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{profile.label}</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 1 }}>{profile.sub}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 4, letterSpacing: "0.04em" }}>
          Tempo: {profile.pace}
        </div>
      </div>
      {active && <MIcon kind="check" size={20} color="var(--g-accent)"/>}
    </button>
  );
}

/* ─────────────────── Schritt 2 · GPX-Import ─────────────────── */
function WStepGpx() {
  const items = [
    { id: "g1", file: "tag1_birnlücke.gpx",     from: "Kasseler Hütte", to: "Birnlücke",  km: 14.2, ascent: 980 },
    { id: "g2", file: "tag2_clarahütte.gpx",    from: "Birnlücke",      to: "Clarahütte", km: 11.8, ascent: 420 },
    { id: "p1", pause: true, name: "Pausentag · Clarahütte" },
    { id: "g3", file: "tag4_essener_hütte.gpx", from: "Clarahütte",     to: "Essener H.", km: 16.4, ascent: 1320 },
  ];
  return (
    <>
      {/* Drop-Zone */}
      <div style={{
        padding: "24px 16px", marginBottom: 14,
        border: "2px dashed var(--g-rule)", borderRadius: "var(--g-r-3)",
        textAlign: "center", background: "var(--g-card-alt)",
      }}>
        <MIcon kind="plus" size={28} color="var(--g-ink-3)"/>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)", marginTop: 8 }}>
          GPX-Dateien wählen
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 4, lineHeight: 1.5 }}>
          Mehrfachauswahl möglich<br/>
          Komoot · Outdooractive · Garmin · FootPath
        </div>
      </div>

      {/* Items */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <Eyebrow>Etappen-Liste · {items.length}</Eyebrow>
          <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>
            {items.filter(i => !i.pause).length} GPX · {items.filter(i => i.pause).length} Pause
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((it, i) => <GpxItemM key={it.id} item={it} index={i}/>)}
        </div>
      </div>

      {/* Vorlagen Accordion */}
      <Card padding={14}>
        <button style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          width: "100%", padding: 0, background: "transparent", border: "none", cursor: "pointer",
          minHeight: 32,
        }}>
          <div style={{ textAlign: "left" }}>
            <Eyebrow style={{ marginBottom: 2 }}>Vorlagen statt eigenem Trip</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--g-ink-2)" }}>Bekannte Mehrtagestouren importieren</div>
          </div>
          <MIcon kind="chevron-down" size={18} color="var(--g-ink-3)"/>
        </button>
      </Card>
    </>
  );
}

function GpxItemM({ item, index }) {
  const num = String(index + 1).padStart(2, "0");
  if (item.pause) {
    return (
      <div style={{
        display: "flex", alignItems: "center", gap: 10, minHeight: 56,
        padding: "10px 12px", background: "var(--g-card-alt)",
        border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-3)",
      }}>
        <MIcon kind="drag" size={16} color="var(--g-ink-4)"/>
        <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-ink-3)", minWidth: 26 }}>T{num}</span>
        <div style={{ flex: 1, minWidth: 0, fontSize: 13, color: "var(--g-ink-2)", fontStyle: "italic" }}>
          {item.name}
          <div style={{ fontStyle: "normal", fontSize: 11, color: "var(--g-ink-4)", marginTop: 2 }}>keine GPX nötig</div>
        </div>
        <IconBtn kind="trash" label="Entfernen"/>
      </div>
    );
  }
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, minHeight: 56,
      padding: "10px 12px", background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
    }}>
      <MIcon kind="drag" size={16} color="var(--g-ink-4)"/>
      <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-accent)", minWidth: 26 }}>T{num}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {item.from} <span style={{ color: "var(--g-ink-4)", fontWeight: 400 }}>→</span> {item.to}
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {item.file} · {item.km}km · ↑{item.ascent}
        </div>
      </div>
      <IconBtn kind="more" label="Mehr"/>
    </div>
  );
}

/* ─────────────────── Schritt 3 · Wegpunkte ─────────────────── */
function WStepStages({ trip }) {
  const [active, setActive] = React.useState(1);
  const stage = trip.stages[active];
  return (
    <>
      {/* Etappen-Pill-Scroller */}
      <div style={{ marginBottom: 14 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Etappe wählen · {trip.stages.length}</Eyebrow>
        <div style={{
          display: "flex", gap: 6, overflowX: "auto", padding: "2px 0 6px",
          WebkitOverflowScrolling: "touch", scrollbarWidth: "none",
        }}>
          {trip.stages.map((s, i) => {
            const isActive = i === active;
            return (
              <button key={s.id} onClick={() => setActive(i)} style={{
                flexShrink: 0, padding: "8px 12px", minHeight: 40,
                background: isActive ? "var(--g-accent)" : "var(--g-card)",
                color: isActive ? "#fff" : "var(--g-ink-2)",
                border: `1px solid ${isActive ? "var(--g-accent)" : "var(--g-rule)"}`,
                borderRadius: "var(--g-r-pill)", cursor: "pointer",
                fontSize: 12, fontFamily: "var(--g-font-mono)", fontWeight: 600,
                letterSpacing: "0.04em", whiteSpace: "nowrap",
              }}>{s.code}</button>
            );
          })}
        </div>
      </div>

      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow>KI-Vorschläge prüfen</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, marginBottom: 4 }}>
          {stage.title.replace(/^[^:]+: /,"")}
        </div>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 12 }}>
          {stage.waypoints.filter(w=>w.ai).length} Wetterscheiden vorgeschlagen — Punkte mit signifikanter Höhen- oder Expositions-Änderung.
        </div>
        <ProfileSVG stage={stage}/>
      </Card>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
        {stage.waypoints.map((wp, i) => (
          <WaypointRowM key={i} wp={wp} index={i}/>
        ))}
      </div>

      <div style={{
        padding: 12, background: "var(--g-accent-tint)",
        borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-2)",
        fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5,
      }}>
        <strong>Tipp:</strong> Wegpunkte kannst du später auf der Karte umsetzen — keine Lat/Lon-Eingabe.
      </div>
    </>
  );
}

function ProfileSVG({ stage }) {
  const W = 313, H = 90;
  const min = Math.min(...stage.profile), max = Math.max(...stage.profile);
  const range = max - min || 1;
  const pts = stage.profile.map((v, i) => {
    const x = (i / (stage.profile.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 12) - 6;
    return [x, y];
  });
  const path = "M" + pts.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fill = path + ` L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block", background: "var(--g-card-alt)", borderRadius: "var(--g-r-2)" }}>
      <path d={fill} fill="rgba(196, 90, 42, 0.1)"/>
      <path d={path} fill="none" stroke="var(--g-accent)" strokeWidth="1.5"/>
      {stage.waypoints.map((wp, i) => {
        const t = i / (stage.waypoints.length - 1);
        const idx = Math.round(t * (stage.profile.length - 1));
        const [x, y] = pts[idx];
        return <circle key={i} cx={x} cy={y} r="4" fill={wp.ai ? "rgba(196,90,42,0.2)" : "#fff"} stroke="var(--g-accent)" strokeWidth="1.5" strokeDasharray={wp.ai ? "2,1.5" : "0"}/>;
      })}
    </svg>
  );
}

function WaypointRowM({ wp, index }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, minHeight: 56,
      padding: "10px 12px", background: "var(--g-card)",
      borderRadius: "var(--g-r-3)",
      border: wp.ai ? "1px dashed var(--g-accent)" : "1px solid var(--g-rule)",
    }}>
      <span style={{
        width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: wp.ai ? "rgba(196,90,42,0.15)" : "var(--g-paper)",
        border: `2px ${wp.ai ? "dashed" : "solid"} var(--g-accent)`,
        fontFamily: "var(--g-font-mono)", fontSize: 11, fontWeight: 700, color: "var(--g-accent-deep)",
      }}>{index + 1}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.3 }}>{wp.name}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
          {wp.elev} m · ETA {wp.time} {wp.ai && <span style={{ color: "var(--g-accent)", fontWeight: 600 }}>· Vorschlag</span>}
        </div>
      </div>
      {wp.ai ? (
        <div style={{ display: "flex", gap: 4 }}>
          <button aria-label="Übernehmen" style={{ width: 36, height: 36, borderRadius: "var(--g-r-2)", background: "var(--g-accent)", border: "none", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
            <MIcon kind="check" size={16} color="#fff"/>
          </button>
          <button aria-label="Verwerfen" style={{ width: 36, height: 36, borderRadius: "var(--g-r-2)", background: "var(--g-card)", border: "1px solid var(--g-rule)", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
            <MIcon kind="close" size={16} color="var(--g-ink-3)"/>
          </button>
        </div>
      ) : (
        <span className="mono" style={{ fontSize: 10, color: "var(--g-good)", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600 }}>fix</span>
      )}
    </div>
  );
}

/* ─────────────────── Schritt 4 · Briefings ─────────────────── */
function WStepBriefings() {
  return (
    <>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow>Deine Kanäle</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, marginBottom: 4 }}>Wohin sollen Briefings?</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 12, lineHeight: 1.5 }}>
          Pro Kanal aktivierbar. Mehr in Einstellungen.
        </div>
        <ChannelLineM kind="Email"    target="gregor_zwanzig@henemm.com" active/>
        <ChannelLineM kind="Signal"   target="+49 151 ••• 8847" active/>
        <ChannelLineM kind="Telegram" target="@gregor_henemm"/>
        <ChannelLineM kind="SMS"      target="+49 151 ••• 8847" sub="Fallback" last/>
      </Card>

      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Briefings · Wann & was</Eyebrow>
        <ReportToggleM label="Morgen-Briefing" time="06:00" sub="Vor Etappenstart" enabled/>
        <ReportToggleM label="Abend-Briefing" time="18:00" sub="Ausblick morgen" enabled last/>
      </Card>

      <Card padding={14}>
        <Eyebrow style={{ marginBottom: 4 }}>Alert-Schwellen</Eyebrow>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 10 }}>
          Sofort bei Überschreitung
        </div>
        <ThresholdM label="Windböen" value="≥ 50 km/h"/>
        <ThresholdM label="Niederschlag" value="≥ 10 mm/h"/>
        <ThresholdM label="Gewitter-Wahrsch." value="≥ 40 %"/>
        <ThresholdM label="Schneefallgrenze" value="−200 m unter Tour" last/>
      </Card>
    </>
  );
}

window.ScreenTripWizardMobile = ScreenTripWizardMobile;
