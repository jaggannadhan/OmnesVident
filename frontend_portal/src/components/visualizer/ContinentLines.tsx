import { useMemo } from "react";
import * as THREE from "three";
import { mesh } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import { latLngToVector3 } from "./utils/geoUtils";
import { GLOBE_RADIUS } from "./Earth";

/**
 * Renders country / coastline borders using topojson-client's mesh() API.
 *
 * mesh() with a filter of (a, b) => a !== b returns only interior borders
 * (borders shared between two different countries), giving cleaner country
 * outlines without duplicate coastline segments.
 */

// @ts-ignore — world-atlas ships plain JSON; no bundled type defs needed
import topoRaw from "world-atlas/countries-110m.json";

const BORDER_R = GLOBE_RADIUS + 0.012;

const topo = topoRaw as unknown as Topology;
const countries = (topo.objects as Record<string, GeometryCollection>).countries;

// mesh() returns a GeoJSON MultiLineString of all country border arcs
const BORDER_LINES = mesh(topo, countries);

export function ContinentLines() {
  const lineSegments = useMemo(() => {
    const pts: THREE.Vector3[] = [];

    for (const lineString of BORDER_LINES.coordinates) {
      for (let i = 0; i < lineString.length - 1; i++) {
        const [lon0, lat0] = lineString[i] as [number, number];
        const [lon1, lat1] = lineString[i + 1] as [number, number];
        pts.push(latLngToVector3(lat0, lon0, BORDER_R));
        pts.push(latLngToVector3(lat1, lon1, BORDER_R));
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setFromPoints(pts);

    const mat = new THREE.LineBasicMaterial({
      color: "#67e8f9",
      transparent: true,
      opacity: 0.75,
      depthWrite: false,
    });

    return new THREE.LineSegments(geo, mat);
  }, []);

  return <primitive object={lineSegments} />;
}