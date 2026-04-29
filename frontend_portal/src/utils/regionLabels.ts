/**
 * regionLabels.ts — turns a story's `region_code` into a human-readable label.
 *
 *   "US"     → "United States"
 *   "GB"     → "United Kingdom"
 *   "US-CA"  → "California, US"
 *   "IN-TN"  → "Tamil Nadu, IN"
 *   "ZZ"     → "ZZ"  (unknown — falls back to the raw code)
 *
 * The country and subdivision tables stay in sync with:
 *   - frontend_portal/src/components/RegionCombobox.tsx (REGION_GROUPS)
 *   - ingestion_engine/regions_to_track.json
 */

// ─── Country names — ISO 3166-1 alpha-2 ──────────────────────────────────────
export const COUNTRY_NAMES: Record<string, string> = {
  // Americas
  US: "United States",
  CA: "Canada",
  BR: "Brazil",
  MX: "Mexico",
  AR: "Argentina",
  // Europe
  GB: "United Kingdom",
  DE: "Germany",
  FR: "France",
  IT: "Italy",
  UA: "Ukraine",
  // Asia-Pacific
  JP: "Japan",
  CN: "China",
  IN: "India",
  AU: "Australia",
  KR: "South Korea",
  // Middle East & Africa
  IL: "Israel",
  SA: "Saudi Arabia",
  EG: "Egypt",
  ZA: "South Africa",
  NG: "Nigeria",
};

// ─── Subdivision names — ISO 3166-2 ──────────────────────────────────────────
// Mirrors ingestion_engine/regions_to_track.json (and a few common extras).
export const SUBDIVISION_NAMES: Record<string, string> = {
  // United States
  "US-CA": "California",
  "US-TX": "Texas",
  "US-NY": "New York",
  "US-FL": "Florida",
  "US-WA": "Washington",
  "US-IL": "Illinois",
  "US-PA": "Pennsylvania",
  "US-OH": "Ohio",
  "US-GA": "Georgia",
  "US-NC": "North Carolina",
  "US-MI": "Michigan",
  "US-AZ": "Arizona",
  "US-CO": "Colorado",
  "US-VA": "Virginia",
  "US-TN": "Tennessee",
  "US-DC": "Washington, DC",

  // India
  "IN-MH": "Maharashtra",
  "IN-DL": "Delhi",
  "IN-KA": "Karnataka",
  "IN-TN": "Tamil Nadu",
  "IN-WB": "West Bengal",
  "IN-GJ": "Gujarat",
  "IN-RJ": "Rajasthan",
  "IN-UP": "Uttar Pradesh",
  "IN-TS": "Telangana",
  "IN-AP": "Andhra Pradesh",
  "IN-KL": "Kerala",
  "IN-PB": "Punjab",
  "IN-OR": "Odisha",

  // China
  "CN-BJ": "Beijing",
  "CN-SH": "Shanghai",
  "CN-GD": "Guangdong",
  "CN-SC": "Sichuan",
  "CN-HB": "Hubei",
  "CN-ZJ": "Zhejiang",
  "CN-JS": "Jiangsu",
  "CN-SN": "Shaanxi",
  "CN-SD": "Shandong",
  "CN-HN": "Henan",

  // Brazil
  "BR-SP": "São Paulo",
  "BR-RJ": "Rio de Janeiro",
  "BR-MG": "Minas Gerais",
  "BR-CE": "Ceará",
  "BR-BA": "Bahia",
  "BR-RS": "Rio Grande do Sul",
  "BR-PR": "Paraná",
  "BR-PE": "Pernambuco",
  "BR-GO": "Goiás",
  "BR-AM": "Amazonas",

  // Canada
  "CA-ON":  "Ontario",
  "CA-BC":  "British Columbia",
  "CA-QC":  "Québec",
  "CA-AB":  "Alberta",
  "CA-MB":  "Manitoba",
  "CA-SK":  "Saskatchewan",
  "CA-NS":  "Nova Scotia",

  // Australia
  "AU-NSW": "New South Wales",
  "AU-VIC": "Victoria",
  "AU-QLD": "Queensland",
  "AU-WA":  "Western Australia",
  "AU-SA":  "South Australia",
  "AU-TAS": "Tasmania",
  "AU-ACT": "Canberra",

  // South Africa
  "ZA-GT":  "Gauteng",
  "ZA-WC":  "Western Cape",
  "ZA-KZN": "KwaZulu-Natal",
  "ZA-EC":  "Eastern Cape",
  "ZA-LP":  "Limpopo",
  "ZA-MP":  "Mpumalanga",
};

/**
 * Long form: "California, US" / "United States" / unknown → raw code.
 * Used for tooltips and full-text labels.
 */
export function regionLabel(code: string | null | undefined): string {
  if (!code) return "";
  if (code.includes("-")) {
    const [country] = code.split("-");
    const sub = SUBDIVISION_NAMES[code];
    return sub ? `${sub}, ${country}` : code;
  }
  return COUNTRY_NAMES[code] ?? code;
}

/**
 * Short form: "California" / "United States" / unknown → raw code.
 * Used for compact chips where the country prefix is implied by context.
 */
export function regionLabelShort(code: string | null | undefined): string {
  if (!code) return "";
  if (code.includes("-")) {
    return SUBDIVISION_NAMES[code] ?? code;
  }
  return COUNTRY_NAMES[code] ?? code;
}
