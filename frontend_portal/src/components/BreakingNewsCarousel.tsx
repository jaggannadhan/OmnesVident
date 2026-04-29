import { useState, useEffect, useRef, useCallback } from "react";
import type { StoryOut } from "../services/api";
import { regionLabel } from "../utils/regionLabels";

// ─── Constants ────────────────────────────────────────────────────────────────

const ROTATE_INTERVAL_MS = 6000;   // auto-advance every 6 s
const BREAKING_COLOR     = "#FF2020";
const SWIPE_THRESHOLD_PX = 40;     // distance required to commit a slow swipe
const FLICK_VELOCITY_PXMS = 0.35;  // px/ms — a fast flick commits even at short distance

// ─── BreakingNewsCarousel ─────────────────────────────────────────────────────

interface BreakingNewsCarouselProps {
  stories: StoryOut[];
}

export function BreakingNewsCarousel({ stories }: BreakingNewsCarouselProps) {
  // Sort by heat_score desc, then timestamp desc
  const sorted = [...stories].sort((a, b) => {
    if (b.heat_score !== a.heat_score) return b.heat_score - a.heat_score;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  const [activeIdx, setActiveIdx] = useState(0);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const swipeRef = useRef<HTMLDivElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const advance = useCallback(() => {
    setActiveIdx((i) => (i + 1) % sorted.length);
  }, [sorted.length]);

  const rewind = useCallback(() => {
    setActiveIdx((i) => (i - 1 + sorted.length) % sorted.length);
  }, [sorted.length]);

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(advance, ROTATE_INTERVAL_MS);
  }, [advance]);

  useEffect(() => {
    if (sorted.length === 0) return;
    resetTimer();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [sorted.length, resetTimer]);

  // Reset index when the stories list changes
  useEffect(() => { setActiveIdx(0); }, [sorted.length]);

  // ─── Swipe — native event listeners (most reliable across browsers) ─────────
  // Attaching natively (not via React synthetic events) avoids passive-listener
  // edge cases on iOS Safari and ensures touchmove fires during the gesture.
  useEffect(() => {
    const el = swipeRef.current;
    if (!el || sorted.length <= 1) return;

    const INTENT_THRESHOLD = 6;
    let startX = 0, startY = 0;
    let lastX = 0, lastT = 0;          // last move sample (for velocity)
    let intent: "unknown" | "horizontal" | "vertical" = "unknown";
    let active = false;

    const begin = (x: number, y: number, target: EventTarget | null): boolean => {
      if ((target as HTMLElement | null)?.closest("a, button")) return false;
      startX = x; startY = y;
      lastX  = x; lastT  = performance.now();
      intent = "unknown";
      active = true;
      if (timerRef.current) clearInterval(timerRef.current);
      return true;
    };

    const move = (x: number, y: number, ev?: Event) => {
      if (!active) return;
      const dx = x - startX, dy = y - startY;
      if (intent === "unknown") {
        if (Math.abs(dx) < INTENT_THRESHOLD && Math.abs(dy) < INTENT_THRESHOLD) return;
        intent = Math.abs(dx) > Math.abs(dy) ? "horizontal" : "vertical";
        if (intent === "horizontal") setIsDragging(true);
        else { active = false; return; }   // hand off vertical scroll to the browser
      }
      if (intent === "horizontal") {
        // Block the browser from also reading this as a scroll
        if (ev && ev.cancelable) ev.preventDefault();
        setDragOffset(dx);
        lastX = x; lastT = performance.now();
      }
    };

    const end = (x: number) => {
      if (!active && intent !== "horizontal") { resetTimer(); return; }
      const wasHorizontal = intent === "horizontal";
      const delta = x - startX;
      // Velocity over the LAST move sample, not whole gesture — a slow drag
      // followed by a quick release should still register as a flick.
      const elapsed = Math.max(1, performance.now() - lastT);
      const velocity = Math.abs((x - lastX) / elapsed);   // px / ms
      active = false;
      intent = "unknown";
      setIsDragging(false);
      setDragOffset(0);
      if (wasHorizontal) {
        const distancePass = Math.abs(delta) > SWIPE_THRESHOLD_PX;
        const flickPass    = velocity > FLICK_VELOCITY_PXMS && Math.abs(delta) > 10;
        if (distancePass || flickPass) {
          if (delta < 0) advance(); else rewind();
        }
      }
      resetTimer();
    };

    // Touch
    const onTouchStart = (e: TouchEvent) => {
      const t = e.touches[0]; if (!t) return;
      begin(t.clientX, t.clientY, e.target);
    };
    const onTouchMove = (e: TouchEvent) => {
      const t = e.touches[0]; if (!t) return;
      move(t.clientX, t.clientY, e);
    };
    const onTouchEnd = (e: TouchEvent) => {
      const t = e.changedTouches[0];
      end(t ? t.clientX : startX);
    };

    // Mouse
    const onMouseDown = (e: MouseEvent) => {
      if (!begin(e.clientX, e.clientY, e.target)) return;
      const onMove = (ev: MouseEvent) => move(ev.clientX, ev.clientY);
      const onUp   = (ev: MouseEvent) => {
        end(ev.clientX);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup",   onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup",   onUp);
    };

    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove",  onTouchMove,  { passive: false });  // need to preventDefault
    el.addEventListener("touchend",   onTouchEnd);
    el.addEventListener("touchcancel", onTouchEnd);
    el.addEventListener("mousedown",  onMouseDown);

    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove",  onTouchMove);
      el.removeEventListener("touchend",   onTouchEnd);
      el.removeEventListener("touchcancel", onTouchEnd);
      el.removeEventListener("mousedown",  onMouseDown);
    };
  }, [sorted.length, advance, rewind, resetTimer]);

  if (sorted.length === 0) return null;

  const story = sorted[Math.min(activeIdx, sorted.length - 1)];

  function relativeTime(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60_000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "rgba(8,10,24,0.96)",
        border: `1px solid ${BREAKING_COLOR}33`,
        borderLeft: `3px solid ${BREAKING_COLOR}`,
        borderRadius: "12px",
        overflow: "hidden",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px 8px",
          borderBottom: `1px solid ${BREAKING_COLOR}22`,
          background: `${BREAKING_COLOR}0d`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {/* Pulsing dot */}
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: BREAKING_COLOR,
              boxShadow: `0 0 8px ${BREAKING_COLOR}`,
              display: "inline-block",
              animation: "pulse 1.2s ease-in-out infinite",
            }}
          />
          <span
            style={{
              fontSize: "10px",
              fontWeight: 800,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: BREAKING_COLOR,
            }}
          >
            Breaking News
          </span>
        </div>
        <span style={{ fontSize: "9px", fontFamily: "monospace", color: "#475569" }}>
          {Math.min(activeIdx, sorted.length - 1) + 1}/{sorted.length}
        </span>
      </div>

      {/* Active story card — swipeable (handlers attached natively in useEffect) */}
      <div
        ref={swipeRef}
        style={{
          flex: 1,
          padding: "12px 14px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          minHeight: 0,
          // Allow vertical scroll until intent classifies as horizontal,
          // at which point our touchmove handler preventDefaults to take over.
          touchAction: "pan-y",
          cursor: sorted.length > 1 ? (isDragging ? "grabbing" : "grab") : "default",
          userSelect: isDragging ? "none" : "auto",
          transform: `translateX(${dragOffset}px)`,
          opacity: 1 - Math.min(0.4, Math.abs(dragOffset) / 400),
          transition: isDragging ? "none" : "transform 0.25s ease, opacity 0.25s ease",
        }}
      >
        {/* Meta: category + region + time */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: "8px",
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: BREAKING_COLOR,
              background: `${BREAKING_COLOR}18`,
              padding: "2px 5px",
              borderRadius: "3px",
            }}
          >
            {story.category}
          </span>
          <span
            style={{ fontSize: "8px", color: "#64748b", fontWeight: 600 }}
            title={story.region_code}
          >
            {regionLabel(story.region_code)}
          </span>
          <span style={{ fontSize: "8px", color: "#334155", fontFamily: "monospace" }}>
            {relativeTime(story.timestamp)}
          </span>
        </div>

        {/* Source */}
        <p style={{ margin: 0, fontSize: "8px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {story.source_name}
        </p>

        {/* Title */}
        <p
          style={{
            margin: 0,
            fontSize: "12px",
            fontWeight: 700,
            color: "#f1f5f9",
            lineHeight: 1.45,
            flex: 1,
          }}
        >
          {story.title.length > 120 ? story.title.slice(0, 117) + "…" : story.title}
        </p>

        {/* Snippet */}
        <p style={{ margin: 0, fontSize: "10px", color: "#64748b", lineHeight: 1.5 }}>
          {story.snippet.length > 100 ? story.snippet.slice(0, 97) + "…" : story.snippet}
        </p>

        {/* Read link */}
        <a
          href={story.source_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "9px",
            fontWeight: 700,
            color: BREAKING_COLOR,
            textDecoration: "none",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginTop: "auto",
          }}
        >
          Read full story ↗
        </a>
      </div>

      {/* Auto-rotate progress bar — animates 0→100% over ROTATE_INTERVAL_MS.
          Re-mounts on every slide change (key={activeIdx}) so the animation
          restarts from 0. Pauses while the user is dragging the card. */}
      {sorted.length > 1 && (
        <div
          style={{
            height: "2px",
            background: `${BREAKING_COLOR}1a`,
            flexShrink: 0,
            overflow: "hidden",
          }}
          aria-hidden="true"
        >
          <div
            key={activeIdx}
            style={{
              height: "100%",
              background: BREAKING_COLOR,
              boxShadow: `0 0 4px ${BREAKING_COLOR}`,
              animation: `breakingProgress ${ROTATE_INTERVAL_MS}ms linear forwards`,
              animationPlayState: isDragging ? "paused" : "running",
              transformOrigin: "left center",
            }}
          />
        </div>
      )}

      {/* Dot navigation + arrows — capped at 4 dots even for many stories */}
      {sorted.length > 1 && (() => {
        const MAX_DOTS  = 4;
        const dotCount  = Math.min(MAX_DOTS, sorted.length);
        // Evenly distribute the dots across the carousel — for 10 stories with
        // 4 dots, the dots correspond to story indexes [0, 2, 5, 7].
        const dotTarget = (i: number) => Math.floor((i * sorted.length) / dotCount);
        const activeDot = Math.min(
          dotCount - 1,
          Math.floor((activeIdx * dotCount) / sorted.length)
        );
        const arrowBtn: React.CSSProperties = {
          background: "none",
          border: "none",
          color: "#94a3b8",
          cursor: "pointer",
          fontSize: "18px",
          lineHeight: 1,
          padding: "4px 8px",
          borderRadius: "6px",
          transition: "color 0.15s ease, background 0.15s ease",
        };
        return (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "8px",
              padding: "8px 20px 10px",
              borderTop: `1px solid ${BREAKING_COLOR}14`,
              flexShrink: 0,
            }}
          >
            <button
              onClick={() => { rewind(); resetTimer(); }}
              style={arrowBtn}
              aria-label="Previous story"
              onMouseEnter={(e) => { e.currentTarget.style.color = BREAKING_COLOR; e.currentTarget.style.background = `${BREAKING_COLOR}14`; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "none"; }}
            >
              ‹
            </button>

            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              {Array.from({ length: dotCount }, (_, i) => (
                <button
                  key={i}
                  onClick={() => { setActiveIdx(dotTarget(i)); resetTimer(); }}
                  style={{
                    width:  i === activeDot ? "18px" : "6px",
                    height: "6px",
                    borderRadius: "3px",
                    background: i === activeDot ? BREAKING_COLOR : "#334155",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    transition: "width 0.2s ease, background 0.2s ease",
                    boxShadow: i === activeDot ? `0 0 6px ${BREAKING_COLOR}` : "none",
                  }}
                  aria-label={`Jump to story ${dotTarget(i) + 1}`}
                />
              ))}
            </div>

            <button
              onClick={() => { advance(); resetTimer(); }}
              style={arrowBtn}
              aria-label="Next story"
              onMouseEnter={(e) => { e.currentTarget.style.color = BREAKING_COLOR; e.currentTarget.style.background = `${BREAKING_COLOR}14`; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "#94a3b8"; e.currentTarget.style.background = "none"; }}
            >
              ›
            </button>
          </div>
        );
      })()}

      {/* Inline keyframes for the pulsing dot + auto-rotate progress bar */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(0.75); }
        }
        @keyframes breakingProgress {
          from { width: 0%; }
          to   { width: 100%; }
        }
      `}</style>
    </div>
  );
}
