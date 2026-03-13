import { Vector3 } from "three";

/**
 * Convert WGS84 lat/lng to a point on a sphere of the given radius.
 * Uses the standard spherical coordinate transform (right-hand Y-up).
 */
export function latLngToVector3(lat: number, lng: number, radius: number): Vector3 {
  const phi   = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
     radius * Math.cos(phi),
     radius * Math.sin(phi) * Math.sin(theta)
  );
}

/**
 * ISO alpha-2 → [latitude, longitude] country centroid.
 * Coordinates are approximate geographic centres suitable for globe placement.
 */
export const REGION_COORDS: Record<string, [number, number]> = {
  // Americas
  US: [37.09,  -95.71],
  CA: [56.13,  -106.35],
  MX: [23.63,  -102.55],
  AR: [-38.42, -63.62],
  BR: [-14.24, -51.93],
  // Europe
  GB: [55.38,  -3.44],
  DE: [51.17,   10.45],
  FR: [46.23,    2.21],
  IT: [41.87,   12.57],
  UA: [48.38,   31.17],
  // Asia-Pacific
  JP: [36.20,  138.25],
  CN: [35.86,  104.19],
  IN: [20.59,   78.96],
  AU: [-25.27, 133.78],
  KR: [35.91,  127.77],
  // Middle East & Africa
  IL: [31.05,   34.85],
  SA: [23.89,   45.08],
  EG: [26.82,   30.80],
  ZA: [-30.56,  22.94],
  NG: [9.08,     8.68],
};

/** Fallback for unknown region codes — centre of the globe view */
const FALLBACK: [number, number] = [0, 0];

export function regionToVector3(regionCode: string, radius: number): Vector3 {
  const [lat, lng] = REGION_COORDS[regionCode.toUpperCase()] ?? FALLBACK;
  return latLngToVector3(lat, lng, radius);
}
