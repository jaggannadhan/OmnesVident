import { useMemo } from "react";
import * as THREE from "three";
import { latLngToVector3 } from "./utils/geoUtils";
import { GLOBE_RADIUS } from "./Earth";

/**
 * Draws clean latitude / longitude grid lines using explicit THREE.Line objects.
 * Replaces the old sphereGeometry wireframe which only showed triangulation edges.
 *
 * Must be rendered inside Earth's rotating <group> so the grid rotates with the globe.
 */

const GRID_R = GLOBE_RADIUS + 0.006; // just above the sphere surface
const SEGMENTS = 128;               // smoothness of each curve

/** Points for a latitude ring (constant lat, full 360° lon sweep). */
function makeLatRing(lat: number): THREE.Vector3[] {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= SEGMENTS; i++) {
    const lon = (i / SEGMENTS) * 360 - 180;
    pts.push(latLngToVector3(lat, lon, GRID_R));
  }
  return pts;
}

/** Points for a longitude meridian (constant lon, full −90→+90 lat sweep). */
function makeLonMeridian(lon: number): THREE.Vector3[] {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= SEGMENTS; i++) {
    const lat = (i / SEGMENTS) * 180 - 90;
    pts.push(latLngToVector3(lat, lon, GRID_R));
  }
  return pts;
}

export function GlobeGrid() {
  const primitive = useMemo(() => {
    const group = new THREE.Group();

    const addLine = (pts: THREE.Vector3[], color: string, opacity: number) => {
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity,
        depthWrite: false,
      });
      group.add(new THREE.Line(geo, mat));
    };

    // ── Latitude rings every 30° ──────────────────────────────────────────
    for (const lat of [-60, -30, 30, 60]) {
      addLine(makeLatRing(lat), "#1e3a8a", 0.25);
    }
    // Equator — slightly more prominent
    addLine(makeLatRing(0), "#3b82f6", 0.42);

    // ── Longitude meridians every 30° ─────────────────────────────────────
    for (let lon = -180; lon < 180; lon += 30) {
      // Prime meridian (0°) slightly brighter
      const opacity = lon === 0 ? 0.32 : 0.2;
      addLine(makeLonMeridian(lon), "#1e3a8a", opacity);
    }

    return group;
  }, []);

  return <primitive object={primitive} />;
}
