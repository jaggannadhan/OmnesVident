import { useRef, useMemo, useEffect } from "react";
import { useThree, useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import type { Vector3 } from "three";
import type { StoryOut } from "../../services/api";

// ─── Card geometry constants (must match the CSS below) ───────────────────────
const CARD_W    = 240;  // px  — matches width: "240px"
const CARD_H    = 174;  // px  — estimated card height
const CARD_DX   = 14;   // px  — matches translate(14px, ...)

// ─── Category accent colours ──────────────────────────────────────────────────
const CATEGORY_COLORS: Record<string, string> = {
  WORLD:         "#38bdf8",
  POLITICS:      "#f87171",
  TECHNOLOGY:    "#22d3ee",
  BUSINESS:      "#34d399",
  SCIENCE:       "#a78bfa",
  HEALTH:        "#6ee7b7",
  ENTERTAINMENT: "#f472b6",
  SPORTS:        "#fb923c",
};

// ─── CardTethers ──────────────────────────────────────────────────────────────
//
// Draws 4 projection lines from the blip to the 4 corners of the HUD card.
//
// Architecture:
//  • An invisible <group ref={anchorRef}> sits INSIDE Earth's rotating group
//    at the blip's local position.  getWorldPosition() on it gives the correct
//    world position even while the globe is frozen at an arbitrary rotation.
//  • The four THREE.Line objects are added directly to the scene ROOT via
//    scene.add() so their vertices are always in world space — no parent
//    transform to fight.
//  • useFrame recomputes the card-corner world positions each frame by
//    projecting the blip to screen space, computing pixel corners, then
//    unprojecting back to world space at the blip's NDC depth.

interface TethersProps {
  localPosition: Vector3;
  accent: string;
}

function CardTethers({ localPosition, accent }: TethersProps) {
  const { camera, size, scene } = useThree();

  // Invisible anchor in Earth's group — used only for getWorldPosition()
  const anchorRef = useRef<THREE.Group>(null);

  // Reusable scratch vectors — avoids GC pressure inside useFrame
  const scratch = useRef({
    blipWorld:   new THREE.Vector3(),
    ndc:         new THREE.Vector3(),
    cornerWorld: new THREE.Vector3(),
  });

  // Build the 4 line objects once and add them to the scene root
  const { linesGroup, posAttribs } = useMemo(() => {
    const mat = new THREE.LineBasicMaterial({
      color: accent,
      transparent: true,
      opacity: 0.45,
      depthTest:  false,  // always draw on top — command-centre aesthetic
      depthWrite: false,
    });

    const grp    = new THREE.Group();
    const attribs: THREE.BufferAttribute[] = [];

    for (let i = 0; i < 4; i++) {
      const arr  = new Float32Array(6);          // 2 points × 3 floats
      const attr = new THREE.BufferAttribute(arr, 3);
      attr.setUsage(THREE.DynamicDrawUsage);
      const geo  = new THREE.BufferGeometry();
      geo.setAttribute("position", attr);
      const line = new THREE.Line(geo, mat);
      line.frustumCulled = false;                // never cull — we manage visibility
      grp.add(line);
      attribs.push(attr);
    }

    return { linesGroup: grp, posAttribs: attribs };
  }, [accent]);

  // Mount: add to scene root.  Unmount: remove cleanly.
  useEffect(() => {
    scene.add(linesGroup);
    return () => { scene.remove(linesGroup); };
  }, [linesGroup, scene]);

  useFrame(() => {
    if (!anchorRef.current) return;

    const { blipWorld, ndc, cornerWorld } = scratch.current;

    // Resolve actual world position through Earth's rotation matrix
    anchorRef.current.updateWorldMatrix(true, false);
    anchorRef.current.getWorldPosition(blipWorld);

    // Project to NDC
    ndc.copy(blipWorld).project(camera);

    // Hide lines if blip is behind the camera
    if (ndc.z >= 1) { linesGroup.visible = false; return; }
    linesGroup.visible = true;

    // NDC → screen pixels (origin: top-left)
    const bx = (ndc.x * 0.5 + 0.5) * size.width;
    const by = (1 - (ndc.y * 0.5 + 0.5)) * size.height;

    // The 4 card corners in screen space (matches CSS translate + dimensions)
    const corners: [number, number][] = [
      [bx + CARD_DX,            by - CARD_H / 2],  // top-left
      [bx + CARD_DX + CARD_W,   by - CARD_H / 2],  // top-right
      [bx + CARD_DX,            by + CARD_H / 2],  // bottom-left
      [bx + CARD_DX + CARD_W,   by + CARD_H / 2],  // bottom-right
    ];

    corners.forEach(([cx, cy], i) => {
      // Screen pixels → NDC → world (at the same depth as the blip)
      const cndcX =   (cx / size.width)  * 2 - 1;
      const cndcY = -((cy / size.height) * 2 - 1);
      cornerWorld.set(cndcX, cndcY, ndc.z).unproject(camera);

      const attr = posAttribs[i];
      attr.setXYZ(0, blipWorld.x,   blipWorld.y,   blipWorld.z);
      attr.setXYZ(1, cornerWorld.x, cornerWorld.y, cornerWorld.z);
      attr.needsUpdate = true;
    });
  });

  // The anchor lives inside Earth's group (so rotation is tracked)
  return <group ref={anchorRef} position={localPosition} />;
}

// ─── HudOverlay ───────────────────────────────────────────────────────────────

interface HudOverlayProps {
  story: StoryOut;
  position: Vector3;
  onClose: () => void;
}

export function HudOverlay({ story, position, onClose }: HudOverlayProps) {
  const accent = CATEGORY_COLORS[story.category] ?? "#38bdf8";

  return (
    <>
      {/* Projection lines from blip to each card corner */}
      <CardTethers localPosition={position} accent={accent} />

      <Html
        position={position}
        zIndexRange={[200, 100]}
        occlude={false}
        style={{ pointerEvents: "none" }}
      >
        {/* Offset the card slightly up-right from the marker */}
        <div
          style={{
            transform: "translate(14px, -50%)",
            pointerEvents: "auto",
            width: "240px",
            background: "rgba(8, 10, 24, 0.92)",
            border: `1px solid ${accent}55`,
            borderLeft: `3px solid ${accent}`,
            borderRadius: "8px",
            padding: "10px 12px",
            backdropFilter: "blur(8px)",
            boxShadow: `0 0 20px ${accent}22`,
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
            <span style={{ fontSize: "9px", fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: accent }}>
              {story.category} · {story.region_code}
            </span>
            <button
              onClick={onClose}
              style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: "12px", lineHeight: 1, padding: "0 0 0 8px" }}
            >
              ✕
            </button>
          </div>

          {/* Source */}
          <p style={{ fontSize: "9px", color: "#64748b", margin: "0 0 5px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {story.source_name}
          </p>

          {/* Title */}
          <p style={{ fontSize: "11px", fontWeight: 600, color: "#f1f5f9", margin: "0 0 6px", lineHeight: 1.4 }}>
            {story.title.length > 90 ? story.title.slice(0, 87) + "…" : story.title}
          </p>

          {/* Snippet */}
          <p style={{ fontSize: "10px", color: "#94a3b8", margin: "0 0 8px", lineHeight: 1.5 }}>
            {story.snippet.length > 100 ? story.snippet.slice(0, 97) + "…" : story.snippet}
          </p>

          {/* Link */}
          <a
            href={story.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              fontSize: "9px", fontWeight: 600, color: accent,
              textDecoration: "none", letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Read full story ↗
          </a>
        </div>
      </Html>
    </>
  );
}
