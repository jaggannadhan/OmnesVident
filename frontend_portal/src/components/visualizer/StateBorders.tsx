import { useMemo } from "react";
import * as THREE from "three";
import { latLngToVector3 } from "./utils/geoUtils";
import { GLOBE_RADIUS } from "./Earth";

/**
 * Renders actual state / province borders for covered countries using the
 * Natural Earth 50m Admin-1 dataset (filtered to OmnesVident's 20 countries).
 *
 * Coverage:
 *   US (51), IN (36), CN (31), BR (27), CA (13), ZA (9), AU (9) = 176 features
 *   Remaining 13 covered countries fall back to the ContinentLines country layer.
 *
 * Source: nvkelso/natural-earth-vector ne_50m_admin_1_states_provinces.geojson
 *   Filtered to covered countries, minified → 1.5 MB raw / ~380 KB gzip.
 */

// @ts-ignore — local GeoJSON asset
import adminRaw from "../../data/ne_admin1_110m.json";

/** Just below ContinentLines (+0.012) so cyan country borders stay on top */
const BORDER_R = GLOBE_RADIUS + 0.007;

type Position = [number, number];
type Ring = Position[];

interface GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: Ring[] | Ring[][];
  };
}

interface FeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
}

/** Extract all rings from a Polygon or MultiPolygon geometry */
function getRings(feature: GeoJSONFeature): Ring[] {
  const { type, coordinates } = feature.geometry;
  if (type === "Polygon") {
    return coordinates as Ring[];
  }
  // MultiPolygon: array of polygon coordinate arrays
  return (coordinates as Ring[][]).flat();
}

const FEATURE_COLLECTION = adminRaw as unknown as FeatureCollection;

export function StateBorders() {
  const lineSegments = useMemo(() => {
    const pts: THREE.Vector3[] = [];

    for (const feature of FEATURE_COLLECTION.features) {
      for (const ring of getRings(feature)) {
        for (let i = 0; i < ring.length - 1; i++) {
          const [lon0, lat0] = ring[i];
          const [lon1, lat1] = ring[i + 1];
          pts.push(latLngToVector3(lat0, lon0, BORDER_R));
          pts.push(latLngToVector3(lat1, lon1, BORDER_R));
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setFromPoints(pts);

    const mat = new THREE.LineBasicMaterial({
      color: "#ffffff",
      transparent: true,
      opacity: 0.15,
      depthWrite: false,
    });

    return new THREE.LineSegments(geo, mat);
  }, []);

  return <primitive object={lineSegments} />;
}