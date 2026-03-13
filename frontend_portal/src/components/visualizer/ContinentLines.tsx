import { useState, useEffect, useMemo } from "react";
import * as THREE from "three";
import { latLngToVector3 } from "./utils/geoUtils";
import { GLOBE_RADIUS } from "./Earth";

/**
 * Renders all country / coastline borders from the world-atlas TopoJSON dataset.
 *
 * Strategy (no extra npm packages required):
 *  1. Fetch countries-110m.json at runtime from jsDelivr CDN (~120 KB gzipped).
 *  2. Decode TopoJSON arcs inline — delta-unpacking + scale/translate is ~15 lines.
 *  3. Convert every arc segment pair to 3D points via latLngToVector3.
 *  4. Batch everything into a single THREE.LineSegments for GPU performance.
 *
 * Must be rendered inside Earth's rotating <group> so borders track the globe.
 */

const TOPO_URL =
  "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

/** Slightly above the sphere surface so lines don't z-fight with the globe mesh. */
const BORDER_R = GLOBE_RADIUS + 0.012;

// ─────────────────────────────────────────────────────────────────────────────
// Minimal inline TopoJSON arc decoder — no external library needed.
//
// TopoJSON stores arcs as delta-encoded integer sequences plus a linear
// scale/translate transform.  Decoding is:
//   x_abs[0] = x_delta[0]
//   x_abs[i] = x_abs[i-1] + x_delta[i]
//   lon = x_abs * scale[0] + translate[0]
//   lat = y_abs * scale[1] + translate[1]
// ─────────────────────────────────────────────────────────────────────────────

interface TopoTransform {
  scale: [number, number];
  translate: [number, number];
}

interface TopoJSON {
  arcs: number[][][];
  transform: TopoTransform;
}

function decodeTopoArcs(topo: TopoJSON): [number, number][][] {
  const [sx, sy] = topo.transform.scale;
  const [tx, ty] = topo.transform.translate;

  return topo.arcs.map((arc) => {
    let x = 0,
      y = 0;
    return arc.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * sx + tx, y * sy + ty] as [number, number];
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────

export function ContinentLines() {
  const [arcs, setArcs] = useState<[number, number][][]>([]);

  // Fetch once on mount — runs in the user's browser, not the build step.
  useEffect(() => {
    let cancelled = false;
    fetch(TOPO_URL)
      .then((r) => r.json())
      .then((topo: TopoJSON) => {
        if (!cancelled) setArcs(decodeTopoArcs(topo));
      })
      .catch((err) => console.warn("[ContinentLines] fetch failed:", err));
    return () => {
      cancelled = true;
    };
  }, []);

  // Build a single batched THREE.LineSegments from all arc segments.
  const lineSegments = useMemo(() => {
    if (arcs.length === 0) return null;

    const pts: THREE.Vector3[] = [];

    for (const arc of arcs) {
      for (let i = 0; i < arc.length - 1; i++) {
        const [lon0, lat0] = arc[i];
        const [lon1, lat1] = arc[i + 1];
        // LineSegments expects pairs: start of segment, end of segment
        pts.push(latLngToVector3(lat0, lon0, BORDER_R));
        pts.push(latLngToVector3(lat1, lon1, BORDER_R));
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setFromPoints(pts);

    const mat = new THREE.LineBasicMaterial({
      color: "#67e8f9", // sky-cyan — pops cleanly against the deep-blue sphere
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });

    return new THREE.LineSegments(geo, mat);
  }, [arcs]);

  if (!lineSegments) return null;

  return <primitive object={lineSegments} />;
}
