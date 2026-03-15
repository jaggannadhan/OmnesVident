import { Vector3 } from "three";

/**
 * Apply deterministic pseudo-random jitter to a Vector3 on the globe surface.
 *
 * The offset is purely tangential (perpendicular to the radial direction) so
 * the blip stays at MARKER_RADIUS; no z-fighting and no story drifts inside
 * the sphere.
 *
 * @param position  - 3D point already on the sphere
 * @param seed      - integer seed (e.g. sum of dedup_group_id char codes)
 * @param magnitude - max tangential displacement in world units (default 0.045)
 */
export function applyJitter(position: Vector3, seed: number, magnitude = 0.045): Vector3 {
  // Two stable pseudo-random angles derived from the seed via Knuth-style hash
  const a1 = (((seed * 2654435761) >>> 0) % 10000) / 10000 * Math.PI * 2;
  const a2 = ((((seed + 137) * 2246822519) >>> 0) % 10000) / 10000 * Math.PI * 2;

  // Build two orthogonal tangent axes perpendicular to the sphere's radial direction
  const radial = position.clone().normalize();
  const ref    = Math.abs(radial.y) < 0.9 ? new Vector3(0, 1, 0) : new Vector3(1, 0, 0);
  const t1 = new Vector3().crossVectors(radial, ref).normalize();
  const t2 = new Vector3().crossVectors(radial, t1).normalize();

  return position.clone()
    .addScaledVector(t1, Math.cos(a1) * magnitude)
    .addScaledVector(t2, Math.sin(a2) * magnitude);
}

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

/**
 * ISO 3166-2 subdivision → [latitude, longitude] centroid.
 * Used when a story has a subdivision region_code (e.g. "IN-TN") but no
 * stored lat/lng — keeps blips at the local region, not the country centroid.
 */
export const SUBDIVISION_COORDS: Record<string, [number, number]> = {
  // India
  "IN-TN": [11.3324,  78.6099], "IN-MH": [19.5670,  76.4165],
  "IN-DL": [28.6328,  77.2198], "IN-KA": [14.9562,  75.7897],
  "IN-WB": [22.9965,  87.6856], "IN-AP": [15.9241,  80.1864],
  "IN-GJ": [22.3850,  71.7453], "IN-RJ": [26.8106,  73.7685],
  "IN-UP": [27.1303,  80.8597], "IN-KL": [10.3529,  76.5120],
  "IN-PB": [30.9293,  75.5005], "IN-TS": [17.8496,  79.1152],
  "IN-AS": [26.4074,  93.2551], "IN-BR": [25.6441,  85.9065],
  "IN-HR": [29.0000,  76.0000], "IN-HP": [31.9292,  77.1828],
  "IN-JH": [23.4560,  85.2557], "IN-JK": [33.6649,  75.1630],
  "IN-MP": [23.8143,  77.5341], "IN-MN": [24.7209,  93.9229],
  "IN-CH": [30.7298,  76.7841], "IN-UK": [30.0417,  79.0897],
  "IN-CT": [21.2787,  81.8661], "IN-OR": [20.9517,  85.0985],
  // United States (all 50 states + DC + territories)
  "US-AL": [33.2589,  -86.8295], "US-AK": [64.4460, -149.6809],
  "US-AZ": [34.3953, -111.7633], "US-AR": [35.2049,  -92.4479],
  "US-CA": [36.7015, -118.7560], "US-CO": [38.7252, -105.6077],
  "US-CT": [41.6500,  -72.7342], "US-DE": [38.6920,  -75.4013],
  "US-DC": [38.8938,  -76.9880], "US-FL": [27.7568,  -81.4640],
  "US-GA": [32.3294,  -83.1137], "US-HI": [19.5938, -155.4284],
  "US-ID": [43.6448, -114.0154], "US-IL": [40.0797,  -89.4337],
  "US-IN": [40.3270,  -86.1747], "US-IA": [41.9217,  -93.3123],
  "US-KS": [38.2731,  -98.5822], "US-KY": [37.5726,  -85.1551],
  "US-LA": [30.8704,  -92.0071], "US-ME": [45.7091,  -68.8590],
  "US-MD": [39.5162,  -76.9382], "US-MA": [42.3789,  -72.0324],
  "US-MI": [43.6212,  -84.6824], "US-MN": [45.9897,  -94.6113],
  "US-MS": [32.9715,  -89.7348], "US-MO": [38.7605,  -92.5618],
  "US-MT": [47.3753, -109.6388], "US-NE": [41.7370,  -99.5874],
  "US-NV": [39.5159, -116.8537], "US-NH": [43.4849,  -71.6554],
  "US-NJ": [40.0757,  -74.4042], "US-NM": [34.5802, -105.9960],
  "US-NY": [43.1562,  -75.8450], "US-NC": [35.6730,  -79.0393],
  "US-ND": [47.6201, -100.5407], "US-OH": [40.2254,  -82.6881],
  "US-OK": [34.9551,  -97.2684], "US-OR": [43.9793, -120.7373],
  "US-PA": [40.9700,  -77.7279], "US-RI": [41.7962,  -71.5992],
  "US-SC": [33.6874,  -80.4364], "US-SD": [44.6472, -100.3488],
  "US-TN": [35.7730,  -86.2820], "US-TX": [31.2639,  -98.5456],
  "US-UT": [39.4225, -111.7144], "US-VT": [44.5991,  -72.5003],
  "US-VA": [37.1232,  -78.4928], "US-WA": [47.2868, -120.2126],
  "US-WV": [38.4758,  -80.8408], "US-WI": [44.4309,  -89.6885],
  "US-WY": [43.1700, -107.5685], "US-PR": [18.2248,  -66.4858],
  "US-GU": [13.4500,  144.7652], "US-VI": [17.7892,  -64.7081],
  // China
  "CN-BJ": [40.1906, 116.4121], "CN-SH": [31.2313, 121.4700],
  "CN-GD": [23.1358, 113.1983], "CN-SC": [30.5000, 102.5000],
  "CN-HB": [31.0000, 112.0000], "CN-CQ": [30.0552, 107.8749],
  "CN-TJ": [39.3033, 117.4164], "CN-SN": [35.5896, 109.3013],
  "CN-JS": [33.0000, 120.0000], "CN-ZJ": [29.0000, 120.0000],
  "CN-LN": [41.2374, 122.9955], "CN-HL": [48.0000, 128.0000],
  "CN-JL": [43.7290, 126.1997], "CN-YN": [25.0000, 102.0000],
  "CN-GX": [24.0000, 109.0000], "CN-XJ": [42.4805,  85.4633],
  "CN-XZ": [29.8556,  90.8750], "CN-SD": [36.3990, 118.5056],
  "CN-HN": [27.6662, 111.7487], "CN-AH": [32.0000, 117.0000],
  "CN-FJ": [26.1932, 118.2209], "CN-JX": [28.0000, 116.0000],
  "CN-GZ": [27.0000, 107.0000], "CN-SX": [37.0000, 112.0000],
  "CN-GS": [38.0000, 102.0000], "CN-NM": [43.2443, 114.3252],
  // Brazil
  "BR-SP": [-22.0703, -48.4334], "BR-RJ": [-22.2753, -42.4194],
  "BR-MG": [-18.5265, -44.1589], "BR-CE": [ -5.3265, -39.7156],
  "BR-BA": [-12.2853, -41.9295], "BR-RS": [-29.8425, -53.7681],
  "BR-PR": [-24.4842, -51.8149], "BR-PE": [ -8.4116, -37.5920],
  "BR-AM": [ -4.4799, -63.5185], "BR-DF": [-15.7754, -47.7971],
  "BR-PA": [ -4.7494, -52.8973],
  // Canada
  "CA-ON": [50.0007,  -86.001], "CA-BC": [55.0013, -125.002],
  "CA-QC": [52.4761,  -71.826], "CA-AB": [55.0013, -115.002],
  "CA-MB": [55.0013,  -97.001], "CA-SK": [55.5321, -106.141],
  "CA-NS": [45.1960,  -63.165], "CA-NL": [53.8217,  -61.230],
  "CA-NB": [46.5003,  -66.750], "CA-PE": [46.3356,  -63.147],
  // Australia
  "AU-NSW": [-31.876, 147.287], "AU-VIC": [-36.599, 144.678],
  "AU-QLD": [-22.165, 144.585], "AU-WA":  [-25.230, 121.019],
  "AU-SA":  [-30.534, 135.630], "AU-TAS": [-42.035, 146.637],
  "AU-NT":  [-19.852, 133.230], "AU-ACT": [-35.488, 149.003],
  // South Africa
  "ZA-GT": [-26.200,  28.050], "ZA-WC": [-33.547,  20.728],
  "ZA-KZN":[-28.504,  30.888], "ZA-NL": [-29.000,  30.750],
  "ZA-EC": [-32.217,  26.639], "ZA-FS": [-28.785,  26.498],
  "ZA-NC": [-29.573,  21.205], "ZA-LP": [-23.474,  29.396],
  "ZA-MP": [-26.277,  30.150], "ZA-NW": [-26.135,  25.655],
  // United Kingdom
  "GB-ENG": [52.531,  -1.265], "GB-SCT": [56.786,  -4.114],
  "GB-WLS": [52.293,  -3.739], "GB-NIR": [54.586,  -6.959],
  "GB-LND": [51.516,  -0.092],
  // Germany
  "DE-BE": [52.517,  13.395], "DE-HH": [53.550,  10.001],
  "DE-BY": [48.947,  11.404], "DE-NW": [51.479,   7.554],
  // France
  "FR-IDF": [48.644,   2.754], "FR-ARA": [45.297,   4.661],
  "FR-NAQ": [45.404,   0.376],
  // Italy
  "IT-25": [45.570,   9.773], "IT-62": [41.981,  12.766],
  "IT-88": [40.091,   9.031],
  // Japan
  "JP-13": [35.677, 139.764], "JP-27": [34.620, 135.490],
  "JP-26": [35.243, 135.455], "JP-14": [35.434, 139.375],
  "JP-23": [35.000, 137.255], "JP-01": [43.452, 142.820],
  "JP-40": [33.625, 130.618],
  // South Korea
  "KR-36": [37.567, 126.978], "KR-26": [35.180, 129.075],
  "KR-28": [37.456, 126.705],
  // Ukraine
  "UA-30": [50.450,  30.524], "UA-63": [49.830,  36.379],
  "UA-51": [46.115,  29.957], "UA-46": [49.651,  23.827],
  // Nigeria
  "NG-LA": [ 6.527,   3.577], "NG-FC": [ 8.831,   7.173],
  "NG-KN": [11.895,   8.536],
  // Egypt
  "EG-C":   [30.033,  31.562], "EG-GZ":  [29.054,  29.419],
  "EG-ALX": [30.943,  29.766],
  // Saudi Arabia
  "SA-01": [23.333,  45.333], "SA-02": [21.670,  41.500],
  // Israel
  "IL-TA": [32.096,  34.806], "IL-JM": [31.743,  35.064],
};

// Precompute suffix → coords for last-resort fallback ("IN-TN" → try "TN")
// Last entry wins when suffixes conflict — acceptable as a best-effort fallback.
const _SUFFIX_COORDS: Record<string, [number, number]> = {};
for (const [code, coords] of Object.entries(SUBDIVISION_COORDS)) {
  const suffix = code.split("-")[1];
  if (suffix) _SUFFIX_COORDS[suffix] = coords;
}

/** Fallback for truly unknown region codes — Null Island */
const FALLBACK: [number, number] = [0, 0];

/**
 * Resolution chain:
 *   1. Country code exact match  ("IN"    → India centroid)
 *   2. Full subdivision code     ("IN-TN" → Tamil Nadu centroid)
 *   3. Subdivision suffix        ("IN-TN" → try "TN" — local region, not country)
 *   4. FALLBACK (0, 0)           — only for genuinely unknown codes
 */
export function regionToVector3(regionCode: string, radius: number): Vector3 {
  const code = regionCode.toUpperCase();
  const coords =
    REGION_COORDS[code] ??
    SUBDIVISION_COORDS[code] ??
    _SUFFIX_COORDS[code.split("-")[1]] ??
    FALLBACK;
  const [lat, lng] = coords;
  return latLngToVector3(lat, lng, radius);
}
