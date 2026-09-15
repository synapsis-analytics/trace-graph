/**
 * Deterministic fixture graph for the TRACE mock API (~260 objects across every type
 * and predicate in PLAN.md §3). Shapes follow the CONTRACT exactly; values are plausible
 * SP01 "Breeding for Tomorrow" material but are INVENTED — this is a mock, not data.
 */

/** xorshift32 — deterministic so every run of the mock renders the same graph. */
function rng(seed = 20260915) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

const rand = rng();
const pick = (arr) => arr[Math.floor(rand() * arr.length) % arr.length];
const pickN = (arr, n) => {
  const out = new Set();
  const k = Math.min(n, arr.length);
  let guard = 0;
  while (out.size < k && guard++ < 200) out.add(pick(arr));
  return [...out];
};
const chance = (p) => rand() < p;
const band = () => (chance(0.68) ? "high" : chance(0.75) ? "medium" : "low");

const PROGRAMS = [
  ["sp01", "Breeding for Tomorrow"],
  ["sp02", "Better Diets and Nutrition"],
  ["sp03", "Climate Action"],
  ["sp04", "Food Frontiers and Security"],
  ["sp05", "Genetic Innovation Accelerator"],
  ["sp06", "Multifunctional Landscapes"],
  ["sp07", "Policy Innovations"],
  ["sp08", "Sustainable Farming"],
  ["sp09", "Scaling for Impact"],
  ["sp10", "Capacity Sharing Accelerator"],
  ["sp11", "Digital Transformation Accelerator"],
  ["sp12", "Gender and Inclusion Accelerator"],
  ["sp13", "Breeding Resources"],
];

const AOWS = [
  ["aow01", "Market Intelligence"],
  ["aow02", "Trait Discovery and Product Design"],
  ["aow03", "Breeding Pipelines and Networks"],
  ["aow04", "Seed Systems and Varietal Turnover"],
];

const HLO_TITLES = [
  "Steer to impact: investment cases for priority crops",
  "Target markets defined with demand-led product profiles",
  "Trait pipelines aligned to client segments",
  "Genomic selection deployed in national programmes",
  "Breeding networks co-designed with NARES",
  "Varietal turnover accelerated in target seed systems",
  "Data systems for breeding decisions in routine use",
  "Gender-responsive product profiles adopted",
];

const OUTCOMES = [
  ["i-oc-3-5", "I-OC 3.5 National programmes use demand-led product profiles", "I-OC"],
  ["i-oc-4-1", "I-OC 4.1 Breeding networks apply shared quality standards", "I-OC"],
  ["2030-oc-2", "2030-OC 2 Farmers adopt climate-resilient varieties at scale", "2030-OC"],
  ["2030-oc-5", "2030-OC 5 Seed markets deliver improved genetics within five years", "2030-OC"],
  ["eoi-oc-1", "EoI-OC 1 Public breeding investment reallocated to priority pipelines", "EoI"],
  ["eoi-oc-2", "EoI-OC 2 Women farmers' trait preferences embedded in product design", "EoI"],
];

const COUNTRIES = [
  ["ke", "Kenya"], ["ng", "Nigeria"], ["et", "Ethiopia"], ["tz", "Tanzania"], ["ug", "Uganda"],
  ["gh", "Ghana"], ["ml", "Mali"], ["zm", "Zambia"], ["mw", "Malawi"], ["zw", "Zimbabwe"],
  ["in", "India"], ["bd", "Bangladesh"], ["np", "Nepal"], ["vn", "Viet Nam"], ["pe", "Peru"],
  ["co", "Colombia"], ["mx", "Mexico"], ["sn", "Senegal"],
];

const REGIONS = [
  ["essa", "Eastern and Southern Africa"],
  ["wca", "Western and Central Africa"],
  ["sasia", "South Asia"],
];

const INSTITUTIONS = [
  [1234, "International Maize and Wheat Improvement Center (CIMMYT)", "CGIAR Center"],
  [1235, "International Institute of Tropical Agriculture (IITA)", "CGIAR Center"],
  [1236, "International Rice Research Institute (IRRI)", "CGIAR Center"],
  [1237, "International Crops Research Institute for the Semi-Arid Tropics (ICRISAT)", "CGIAR Center"],
  [1238, "International Potato Center (CIP)", "CGIAR Center"],
  [1239, "Alliance of Bioversity International and CIAT", "CGIAR Center"],
  [2101, "Kenya Agricultural and Livestock Research Organization", "National Research Institute"],
  [2102, "Ethiopian Institute of Agricultural Research", "National Research Institute"],
  [2103, "National Agricultural Research Organisation, Uganda", "National Research Institute"],
  [2104, "Institut d'Economie Rurale, Mali", "National Research Institute"],
  [2105, "Tanzania Agricultural Research Institute", "National Research Institute"],
  [2106, "Zambia Agriculture Research Institute", "National Research Institute"],
  [3101, "Makerere University", "University"],
  [3102, "Wageningen University & Research", "University"],
  [3103, "University of Queensland", "University"],
  [4101, "East African Seed Company", "Private Sector"],
  [4102, "Seed Trade Association of Kenya", "Private Sector"],
  [4103, "Bill & Melinda Gates Foundation", "Foundation"],
  [4104, "Excellence in Breeding Platform", "Platform"],
  [4105, "African Seed Access Index", "NGO"],
];

const PROJECTS = [
  ["01-GATES W2 DLC Groundnut ESA", 2450000, "Bill & Melinda Gates Foundation"],
  ["02-GATES Accelerated Varietal Improvement", 3100000, "Bill & Melinda Gates Foundation"],
  ["03-FCDO Seed Systems Development", 1280000, "FCDO"],
  ["04-USAID Feed the Future Sorghum", 960000, "USAID"],
  ["05-BMZ Market Intelligence for NARES", 740000, "BMZ"],
  ["06-EU DeSIRA Climate Resilient Maize", 1890000, "European Union"],
  ["07-SDC Varietal Turnover Zambia", 520000, "SDC"],
  ["08-ACIAR Legume Breeding Networks", 690000, "ACIAR"],
  ["09-IFAD Smallholder Seed Access", 1140000, "IFAD"],
  ["10-Norway Gender in Breeding", 430000, "Norad"],
  ["11-Gates Genomic Selection Scale-up", 2760000, "Bill & Melinda Gates Foundation"],
  ["12-World Bank Seed Sector Reform", 1520000, "World Bank"],
];

const MELIA = [
  "Adoption study: improved groundnut varieties in Eastern Zambia",
  "Impact assessment: market intelligence use by NARES breeders",
  "Process evaluation: breeding network governance",
  "Outcome study: varietal turnover in Kenyan maize seed markets",
  "Gender study: trait preference elicitation with women farmers",
  "Ex-ante study: returns to genomic selection investment",
  "Learning review: data systems adoption in three programmes",
  "Impact assessment: seed system reform in Nigeria",
];

const CONCEPTS = [
  ["L2-0074", "plant breeding", 2], ["L2-0075", "crop improvement", 2],
  ["L2-0088", "seed systems", 2], ["L2-0089", "varietal turnover", 2],
  ["L2-0101", "market intelligence", 2], ["L2-0102", "product profile", 2],
  ["L2-0110", "genomic selection", 2], ["L2-0111", "phenotyping", 2],
  ["L2-0124", "gender equality", 2], ["L2-0125", "social inclusion", 2],
  ["L2-0140", "capacity development", 2], ["L2-0141", "knowledge sharing", 2],
  ["L2-0150", "food security", 2], ["L2-0151", "nutrition", 2],
  ["L2-0160", "smallholder farmers", 2], ["L2-0161", "farmer organizations", 2],
  ["L2-0170", "maize", 2], ["L2-0171", "groundnut", 2], ["L2-0172", "sorghum", 2],
  ["L2-0173", "cassava", 2], ["L2-0174", "common bean", 2], ["L2-0175", "rice", 2],
  ["L2-0180", "policy dialogue", 2], ["L2-0181", "regulatory framework", 2],
  ["L3-0012", "climate adaptation", 3], ["L3-0013", "drought tolerance", 3],
  ["L3-0014", "heat stress", 3], ["L3-0015", "climate resilient varieties", 3],
  ["L3-0016", "adaptive capacity", 3],
  ["L2-0190", "agricultural research", 2], ["L2-0191", "data management", 2],
  ["L2-0192", "digital agriculture", 2], ["L2-0193", "decision support", 2],
  ["L2-0200", "value chains", 2], ["L2-0201", "market access", 2],
  ["L1-0301", "demand-led breeding", 1], ["L1-0302", "product advancement meeting", 1],
  ["L1-0303", "stage-gate review", 1], ["L1-0304", "trait deployment pipeline", 1],
  ["L1-0305", "last-mile seed delivery", 1],
];

const RESULT_TYPES = [
  ["Knowledge product", 12], ["Innovation development", 10], ["Capacity sharing for development", 8],
  ["Other output", 8], ["Innovation use", 6], ["Other outcome", 4], ["Policy change", 2],
];

const RESULT_TITLES = {
  "Knowledge product": [
    "Demand-led product profiles for %s in %s",
    "Genomic prediction accuracy for %s breeding pipelines in %s",
    "Market segmentation report: %s seed markets in %s",
    "Varietal turnover dashboard for %s systems, %s",
    "Trait preference study among smallholder %s growers in %s",
  ],
  "Innovation development": [
    "Rapid-cycle %s breeding scheme piloted in %s",
    "Low-cost phenotyping protocol for %s under drought in %s",
    "Decision-support tool for %s product advancement in %s",
  ],
  "Capacity sharing for development": [
    "Training course on genomic selection for %s breeders, %s",
    "NARES data-management workshop for %s programmes in %s",
    "Mentoring programme for women %s breeders in %s",
  ],
  "Other output": [
    "Breeding network governance charter for %s in %s",
    "Standard operating procedures for %s trial data capture, %s",
    "Annual stage-gate review of the %s pipeline in %s",
  ],
  "Innovation use": [
    "National programme adopts %s product profiles in %s",
    "Seed company deploys %s decision-support tool in %s",
  ],
  "Other outcome": [
    "Breeders in %s reallocate %s crossing resources to priority segments",
    "%s seed regulators shorten variety release timelines (%s)",
  ],
  "Policy change": [
    "Revised seed regulation recognises %s quality-declared classes in %s",
  ],
};

const CROPS = ["maize", "groundnut", "sorghum", "cassava", "common bean", "rice", "cowpea", "potato"];

const KP_TITLES = [
  "Plan of Results and Budget 2025: CGIAR Science Program on Breeding for Tomorrow",
  "Demand-led breeding: a practitioner's guide",
  "Market intelligence for genetic innovation: 2025 synthesis",
  "Genomic selection in public breeding programmes: lessons from five countries",
  "Seed systems and varietal turnover: measurement handbook",
  "Trait preferences of women farmers in East Africa",
  "Breeding network quality standards: version 2",
  "Annual report of the crop breeding data platform",
];

const sha = (s) => {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h).toString(16).padStart(12, "0").slice(0, 12);
};

const iso = (daysAgo) => new Date(Date.UTC(2026, 8, 15) - daysAgo * 86400000).toISOString();

export function buildFixture() {
  const objects = new Map();
  const links = [];
  const claims = [];
  let clm = 0;
  let lnk = 0;

  const addObject = (o) => {
    objects.set(o.id, {
      description: "",
      attrs: {},
      alt_ids: [],
      source: { system: "mock", ref: o.id, snapshot: "mock_20260915" },
      created_at: iso(120 + Math.floor(rand() * 200)),
      updated_at: iso(Math.floor(rand() * 40)),
      claim_count: 1,
      qa: { band: "high", score: 0.95 },
      ...o,
    });
    return objects.get(o.id);
  };

  const addClaim = (c) => {
    clm += 1;
    const id = `clm_01J${String(clm).padStart(6, "0")}`;
    const b = c.qa?.band ?? band();
    const status = b === "high" ? "accepted" : b === "medium" ? (chance(0.5) ? "review" : "accepted") : chance(0.5) ? "review" : "rejected";
    const claim = {
      id,
      kind: "assert_object",
      subject: null,
      predicate: null,
      object: null,
      payload: {},
      attested_by: "ingest:prms@synapsis",
      provenance: "harvested",
      signature: null,
      evidence: [],
      taxonomy_version: "v0.2.0",
      source: { system: "mock", ref: "fixture", snapshot: "mock_20260915" },
      created_at: iso(Math.floor(rand() * 90)),
      supersedes: null,
      ...c,
      qa: {
        band: b,
        score: b === "high" ? 0.86 + rand() * 0.13 : b === "medium" ? 0.6 + rand() * 0.24 : rand() * 0.59,
        checks: qaChecks(b),
        status,
        decided_by: status === "accepted" && chance(0.3) ? "person:j.berenguer" : null,
        decided_at: null,
        ...(c.qa ?? {}),
      },
    };
    claims.push(claim);
    return claim;
  };

  const qaChecks = (b) => {
    const all = [
      ["well_formed", true, "schema and predicate known"],
      ["id_resolvable", true, "both ends resolve"],
      ["duplicate", b !== "low", b === "low" ? "fuzzy title match 0.94 with an existing object" : "no exact alt-id match"],
      ["taxonomy_resolvable", b === "high", b === "high" ? "term found in Lexicon v0.2.0" : "term not in layer 2/3 — routed as candidate"],
      ["plausible_geo", b !== "low", b === "low" ? "country outside the programme PORB list" : "ISO code valid"],
      ["plausible_time", true, "year within 2022–2026"],
      ["evidence_present", b !== "low", b === "low" ? "no URL, handle or DOI attached" : "evidence URL present"],
      ["provenance_strength", true, "harvested"],
    ];
    return all.map(([name, ok, note]) => ({ name, ok, note }));
  };

  const addLink = (subject, predicate, object, attrs = {}, qaBand) => {
    if (!objects.has(subject) || !objects.has(object)) return null;
    lnk += 1;
    const b = qaBand ?? band();
    const claim = addClaim({
      kind: "assert_link",
      subject,
      predicate,
      object,
      payload: { attrs },
      qa: { band: b },
      evidence: chance(0.5) ? [{ kind: "url", value: "https://cgspace.cgiar.org/handle/10568/175922" }] : [],
    });
    const link = {
      id: `lnk_${String(lnk).padStart(6, "0")}`,
      subject,
      predicate,
      object,
      attrs,
      claim_id: claim.id,
      qa: { band: b },
    };
    links.push(link);
    return link;
  };

  // ---- programs -----------------------------------------------------------
  for (const [code, name] of PROGRAMS) {
    const o = addObject({
      id: `trace:program:${code}`,
      type: "program",
      label: name,
      description: `CGIAR Science Program ${code.toUpperCase()} — ${name}. Portfolio spine object so cross-program links are possible.`,
      attrs: { code: code.toUpperCase(), portfolio: "CGIAR 2025-2030", budget_usd_2025: 18000000 + Math.floor(rand() * 40) * 1000000 },
      alt_ids: [{ scheme: "clarisa_initiative_code", value: code.toUpperCase() }],
      source: { system: "porb", ref: `PORB_MASTER!Program=${name}`, snapshot: "PORB_13Aug2026" },
    });
    addClaim({ kind: "assert_object", subject: o.id, payload: { type: "program", label: name }, attested_by: "ingest:porb@synapsis", qa: { band: "high" } });
  }

  // ---- SP01 results framework --------------------------------------------
  const aowIds = [];
  AOWS.forEach(([code, name], i) => {
    const id = `trace:aow:sp01-${code}`;
    addObject({
      id, type: "aow", label: `${code.toUpperCase()} ${name}`,
      description: `Area of Work ${i + 1} of Breeding for Tomorrow: ${name}.`,
      attrs: { code: code.toUpperCase(), program: "SP01" },
      source: { system: "porb", ref: `PORB_MASTER!HLO!AOW=${code}`, snapshot: "PORB_13Aug2026" },
    });
    aowIds.push(id);
    addLink(id, "PART_OF", "trace:program:sp01", {}, "high");
  });

  const hloIds = [];
  HLO_TITLES.forEach((title, i) => {
    const aowIdx = i % AOWS.length;
    const code = `HLO${i + 1}.AOW${aowIdx + 1}.IO${(i % 3) + 1}`;
    const id = `trace:hlo:sp01-hlo${i + 1}-aow${aowIdx + 1}-io${(i % 3) + 1}`;
    addObject({
      id, type: "hlo", label: `${code} ${title}`,
      description: `High-level output under ${AOWS[aowIdx][1]}. Budget lives on this node and is deliberately NOT propagated to neighbours (boundary rule).`,
      attrs: {
        code,
        budget_usd: 400000 + Math.floor(rand() * 30) * 100000,
        kpi_type: pick(["Number", "Percentage", "Binary"]),
        target_2025: 3 + Math.floor(rand() * 20),
        center: pick(INSTITUTIONS.slice(0, 6))[1],
        assumption: "NARES partners keep trial capacity at 2024 levels.",
      },
      source: { system: "porb", ref: `PORB_MASTER!HLO!${code}`, snapshot: "PORB_13Aug2026" },
    });
    hloIds.push(id);
    addLink(id, "PART_OF", aowIds[aowIdx], {}, "high");
    // funding + partners + countries on the HLO (PORB sheets)
  });

  const indicatorIds = [];
  hloIds.forEach((hlo, i) => {
    for (let k = 0; k < 2; k++) {
      const id = `trace:indicator:sp01-kpi-${i + 1}-${k + 1}`;
      addObject({
        id, type: "indicator",
        label: `KPI ${i + 1}.${k + 1} ${pick(["Number of NARES programmes using the product profile", "Share of crossing blocks aligned to target segments", "Number of varieties released", "Percentage of trials with digital data capture", "Number of breeders trained", "Share of seed volume from varieties < 10 years old"])}`,
        description: "KPI line reported under the high-level output (PORB HLO sheet / PRMS indicator).",
        attrs: { unit: pick(["count", "percent"]), baseline: Math.floor(rand() * 10), target: 5 + Math.floor(rand() * 40) },
        source: { system: "porb", ref: `PORB_MASTER!HLO!KPI`, snapshot: "PORB_13Aug2026" },
      });
      indicatorIds.push(id);
      addLink(id, "PART_OF", hlo, {}, "high");
    }
  });

  const outcomeIds = [];
  OUTCOMES.forEach(([code, label, kind]) => {
    const id = `trace:outcome:sp01-${code}`;
    addObject({
      id, type: "outcome", label,
      description: `Theory-of-change outcome (${kind}) for Breeding for Tomorrow.`,
      attrs: { outcome_type: kind, geography: pick(["Global", "Sub-Saharan Africa", "South Asia"]), target_2030: `${10 + Math.floor(rand() * 40)}%` },
      source: { system: "porb", ref: "PORB_MASTER!Outcomes", snapshot: "PORB_13Aug2026" },
    });
    outcomeIds.push(id);
    addLink(id, "PART_OF", "trace:program:sp01", {}, "high");
  });

  // ---- countries, regions, institutions ----------------------------------
  const countryIds = COUNTRIES.map(([iso2, name]) => {
    const id = `trace:country:${iso2}`;
    addObject({
      id, type: "country", label: name,
      description: `Country object (ISO-3166 alpha-2 ${iso2.toUpperCase()}). The same node serves portfolio-level and result-level statements — lenses decide which paths through it are valid.`,
      attrs: { iso2: iso2.toUpperCase() },
      alt_ids: [{ scheme: "iso2", value: iso2.toUpperCase() }],
      source: { system: "clarisa", ref: `country=${iso2}`, snapshot: "clarisa_2026" },
    });
    return id;
  });

  const regionIds = REGIONS.map(([code, name]) => {
    const id = `trace:region:${code}`;
    addObject({ id, type: "region", label: name, attrs: { code: code.toUpperCase() }, source: { system: "clarisa", ref: `region=${code}`, snapshot: "clarisa_2026" } });
    return id;
  });
  // countries → regions
  countryIds.slice(0, 10).forEach((c, i) => addLink(c, "LOCATED_IN", regionIds[i % 2], {}, "high"));
  countryIds.slice(10, 14).forEach((c) => addLink(c, "LOCATED_IN", regionIds[2], {}, "high"));

  const institutionIds = INSTITUTIONS.map(([cid, name, itype]) => {
    const id = `trace:institution:clarisa-${cid}`;
    addObject({
      id, type: "institution", label: name,
      description: `${itype} registered in CLARISA (id ${cid}).`,
      attrs: { institution_type: itype, clarisa_id: cid, acronym: name.match(/\(([^)]+)\)/)?.[1] ?? null },
      alt_ids: [{ scheme: "clarisa_institution_id", value: String(cid) }],
      source: { system: "clarisa", ref: `institution=${cid}`, snapshot: "clarisa_2026" },
    });
    return id;
  });

  // ---- projects (PORB W3/bilateral) --------------------------------------
  const projectIds = PROJECTS.map(([title, amount, donor]) => {
    const id = `trace:project:porb-${sha(`Breeding for Tomorrow|${title}`)}`;
    addObject({
      id, type: "project", label: title,
      description: `W3/bilateral project reported in the SP01 PORB. Amounts are attributes of the funding link, never prorated across neighbours.`,
      attrs: { amount_usd: amount, donor, start_year: 2023 + Math.floor(rand() * 2), end_year: 2026 + Math.floor(rand() * 2) },
      alt_ids: [{ scheme: "porb_row", value: `W3-Bilateral!${title.slice(0, 2)}` }],
      source: { system: "porb", ref: "PORB_MASTER!W3-Bilateral", snapshot: "PORB_13Aug2026" },
    });
    return id;
  });
  projectIds.forEach((p, i) => {
    const hlo = hloIds[i % hloIds.length];
    addLink(hlo, "FUNDED_BY", p, { amount_usd: PROJECTS[i][1], fiscal_year: 2025 }, "high");
    addLink(p, "LOCATED_IN", countryIds[i % countryIds.length], { share_pct: 40 + Math.floor(rand() * 60) }, "medium");
  });

  // ---- MELIA studies -----------------------------------------------------
  const meliaIds = MELIA.map((title, i) => {
    const id = `trace:melia:porb-${sha(title)}`;
    addObject({
      id, type: "melia_study", label: title,
      description: "MELIA study listed in the SP01 PORB MELIA sheet.",
      attrs: { study_type: pick(["Adoption study", "Impact assessment", "Process evaluation", "Learning review"]), year: 2025 + (i % 2) },
      source: { system: "porb", ref: "PORB_MASTER!MELIA", snapshot: "PORB_13Aug2026" },
    });
    addLink(outcomeIds[i % outcomeIds.length], "STUDIED_BY", id, {}, "high");
    addLink(id, "LOCATED_IN", countryIds[(i * 3) % countryIds.length], {}, "medium");
    return id;
  });

  // ---- concepts ----------------------------------------------------------
  const conceptIds = CONCEPTS.map(([tid, label, layer]) => {
    const id = `trace:concept:${tid}`;
    addObject({
      id, type: "concept", label,
      description: `Taxonomy term (layer ${layer}) from the MELIAF taxonomy service v0.2.0.`,
      attrs: { layer, term_id: tid, status: layer === 1 ? "candidate" : "published" },
      alt_ids: [
        { scheme: "taxonomy_term_id", value: tid },
        { scheme: "taxonomy_uri", value: `https://taxonomy.synapsis-analytics.com/term/${tid}` },
      ],
      source: { system: "taxonomy", ref: tid, snapshot: "v0.2.0" },
      qa: { band: layer === 1 ? "medium" : "high", score: layer === 1 ? 0.72 : 0.97 },
    });
    return id;
  });
  // BROADER chains + candidate suggestions
  addLink("trace:concept:L2-0075", "BROADER", "trace:concept:L2-0074", {}, "high");
  addLink("trace:concept:L2-0089", "BROADER", "trace:concept:L2-0088", {}, "high");
  addLink("trace:concept:L3-0013", "BROADER", "trace:concept:L3-0012", {}, "high");
  addLink("trace:concept:L3-0015", "BROADER", "trace:concept:L3-0012", {}, "high");
  addLink("trace:concept:L2-0102", "BROADER", "trace:concept:L2-0101", {}, "high");
  addLink("trace:concept:L1-0301", "CANDIDATE_FOR", "trace:concept:L2-0074", { similarity: 0.71, note: "Layer 1 term seen 34× with no layer-2 match" }, "medium");
  addLink("trace:concept:L1-0302", "CANDIDATE_FOR", "trace:concept:L2-0102", { similarity: 0.64 }, "medium");
  addLink("trace:concept:L1-0304", "CANDIDATE_FOR", "trace:concept:L2-0074", { similarity: 0.68 }, "low");

  // ---- knowledge products (CGSpace) --------------------------------------
  const kpIds = [];
  for (let i = 0; i < 40; i++) {
    const handle = `10568/${175000 + i * 7}`;
    const id = `trace:kp:hdl-${handle.replace("/", "-")}`;
    const title = i < KP_TITLES.length
      ? KP_TITLES[i]
      : `${pick(["Working paper", "Journal article", "Report", "Brief", "Dataset", "Book chapter"])}: ${pick(CROPS)} ${pick(["breeding pipeline performance", "varietal adoption", "trait preferences", "seed market structure", "genomic prediction"])} in ${pick(COUNTRIES)[1]}`;
    addObject({
      id, type: "kp", label: title,
      description: `CGSpace item ${handle}. Abstract: ${pick(["Evidence from multi-site trials", "Synthesis of programme reporting", "Household survey analysis", "Method note"])} on ${pick(CROPS)} ${pick(["breeding", "seed systems", "market intelligence"])}, produced under Breeding for Tomorrow.`,
      attrs: {
        handle,
        item_type: pick(["Journal Article", "Report", "Working Paper", "Brief", "Dataset"]),
        issued: `${2024 + (i % 3)}-${String(1 + (i % 12)).padStart(2, "0")}-01`,
        open_access: chance(0.8),
        license: pick(["CC-BY-4.0", "CC-BY-NC-4.0"]),
      },
      alt_ids: [
        { scheme: "cgspace_handle", value: handle },
        ...(chance(0.5) ? [{ scheme: "doi", value: `10.1234/trace.${1000 + i}` }] : []),
      ],
      source: { system: "cgspace", ref: `handle=${handle}`, snapshot: "weai_registry_20260912" },
      qa: { band: band(), score: 0.7 + rand() * 0.3 },
    });
    kpIds.push(id);
  }
  // programme PORB document + KP link
  const porbDoc = addObject({
    id: "trace:document:porb-sp01-2025",
    type: "document",
    label: "SP01 Plan of Results and Budget 2025 (workbook)",
    description: "The PORB workbook as a whole, so we can point at the source document as one object.",
    attrs: { pages: 84, approved: "2025-03-14" },
    source: { system: "porb", ref: "PORB_MASTER_All_Programs_13Aug2026.xlsx", snapshot: "PORB_13Aug2026" },
  });
  addObject({
    id: "trace:document:results-framework-2025",
    type: "document",
    label: "CGIAR Portfolio Results Framework 2025-2030",
    description: "High-level results framework document behind the program → AoW → HLO → indicator hierarchy.",
    attrs: { version: "2025.1" },
    source: { system: "porb", ref: "results-framework", snapshot: "PORB_13Aug2026" },
  });
  addLink("trace:program:sp01", "EVIDENCED_BY", kpIds[0], { note: "Published PORB on CGSpace" }, "high");
  addLink("trace:program:sp01", "EVIDENCED_BY", porbDoc.id, {}, "high");

  // ---- persons -----------------------------------------------------------
  const personIds = ["A. Mwangi", "B. Tesfaye", "C. Diallo", "D. Sharma", "E. Nakato", "F. Banda"].map((name) => {
    const id = `trace:person:${name.toLowerCase().replace(/[^a-z]+/g, "-")}`;
    addObject({ id, type: "person", label: name, description: "Author of a CGSpace item (optional object type).", attrs: { role: "author" }, source: { system: "cgspace", ref: "dc.contributor.author", snapshot: "weai_registry_20260912" } });
    return id;
  });
  kpIds.slice(0, 18).forEach((kp, i) => {
    addLink(kp, "AUTHORED_BY", personIds[i % personIds.length], { position: 1 }, "medium");
  });

  // ---- results (PRMS) ----------------------------------------------------
  const resultIds = [];
  let rcount = 0;
  for (const [rtype, n] of RESULT_TYPES) {
    for (let i = 0; i < n; i++) {
      rcount += 1;
      const prmsId = 24000 + rcount * 13;
      const id = `trace:result:prms-${prmsId}`;
      const crop = pick(CROPS);
      const country = pick(COUNTRIES);
      const tpl = pick(RESULT_TITLES[rtype]);
      const label = tpl.replace("%s", crop).replace("%s", country[1]);
      addObject({
        id, type: "result", label,
        description: `PRMS result ${prmsId} (Reporting 2025, Quality Assessed). ${rtype} reported under Breeding for Tomorrow.`,
        attrs: {
          result_type: rtype,
          year: 2025,
          status: "Quality Assessed",
          result_code: `RES-${prmsId}`,
          geo_scope: pick(["National", "Sub-national", "Regional", "Global"]),
          ...(rtype === "Innovation use" ? { innovation_readiness: 6 + Math.floor(rand() * 4) } : {}),
        },
        alt_ids: [
          { scheme: "prms_result_id", value: String(prmsId) },
          { scheme: "prms_result_code", value: `RES-${prmsId}` },
        ],
        source: { system: "prms", ref: `result.id=${prmsId}`, snapshot: "prdb_20260913" },
        qa: { band: band(), score: 0.6 + rand() * 0.4 },
      });
      resultIds.push(id);

      addLink(id, "REPORTED_UNDER", "trace:program:sp01", { role: "primary" }, "high");
      addLink(id, "CONTRIBUTES_TO", pick(hloIds), { via: "PORB HLO sheet heuristic (centre + AoW)", heuristic: true }, "medium");
      if (chance(0.5)) addLink(id, "CONTRIBUTES_TO", pick(outcomeIds), {}, "medium");
      if (chance(0.35)) addLink(id, "CONTRIBUTES_TO", pick(indicatorIds), {}, "medium");
      addLink(id, "PRODUCED_BY", institutionIds[Math.floor(rand() * 6)], { role: "lead centre" }, "high");
      for (const inst of pickN(institutionIds.slice(6), 1 + Math.floor(rand() * 3))) {
        addLink(id, "WITH_PARTNER", inst, { role: "contributing" }, band());
      }
      for (const c of pickN(countryIds, 1 + Math.floor(rand() * 2))) {
        addLink(id, "LOCATED_IN", c, { share_pct: 100 }, band());
      }
      if (rtype === "Knowledge product") {
        const kp = kpIds[rcount % kpIds.length];
        addLink(id, "SAME_AS", kp, { basis: "PRMS knowledge-product handle == CGSpace handle" }, "high");
        addLink(id, "EVIDENCED_BY", kp, {}, "high");
      } else if (chance(0.6)) {
        addLink(id, "EVIDENCED_BY", pick(kpIds), { url: "https://cgspace.cgiar.org/handle/10568/175922" }, band());
      }
      for (const cid of pickN(conceptIds.slice(0, 35), 2 + Math.floor(rand() * 3))) {
        const via = chance(0.6) ? "pref_label" : chance(0.5) ? "alt_label" : "stem";
        addLink(id, "TAGGED_WITH", cid, { matched_text: objects.get(cid).label, via, layer: objects.get(cid).attrs.layer, confidence: via === "pref_label" ? 0.98 : 0.74 }, via === "pref_label" ? "high" : "medium");
      }
      if (chance(0.25)) addLink(id, "FUNDED_BY", pick(projectIds), { amount_usd: 20000 + Math.floor(rand() * 200) * 1000 }, "medium");
    }
  }

  // ---- innovations -------------------------------------------------------
  const innovationIds = [];
  for (let i = 0; i < 10; i++) {
    const id = `trace:innovation:prms-inn-${500 + i * 3}`;
    addObject({
      id, type: "innovation",
      label: `${pick(["Rapid-cycle", "Low-cost", "Digital", "Community-based", "Gender-responsive"])} ${pick(["phenotyping kit", "product advancement protocol", "seed tracking app", "trial data capture workflow", "variety demonstration model"])}`,
      description: "Innovation development/use detail reported in PRMS.",
      attrs: { readiness_level: 4 + Math.floor(rand() * 6), innovation_type: pick(["Technological", "Capacity", "Policy/Organisational"]) },
      source: { system: "prms", ref: `results_innovations_dev.id=${500 + i * 3}`, snapshot: "prdb_20260913" },
      qa: { band: band(), score: 0.65 + rand() * 0.35 },
    });
    innovationIds.push(id);
    addLink(pick(resultIds), "EVIDENCED_BY", id, { note: "innovation detail of the result" }, "medium");
    addLink(pick(kpIds), "DESCRIBES", id, {}, "medium");
    for (const cid of pickN(conceptIds.slice(0, 30), 2)) {
      addLink(id, "TAGGED_WITH", cid, { via: "pref_label", layer: 2, confidence: 0.95 }, "high");
    }
  }

  // ---- PORB partner / country / synergy links on HLOs --------------------
  hloIds.forEach((hlo, i) => {
    for (const inst of pickN(institutionIds, 2 + Math.floor(rand() * 2))) {
      addLink(hlo, "WITH_PARTNER", inst, { source_sheet: "Partners", role: pick(["Implementing", "Co-designing", "Scaling"]) }, "high");
    }
    for (const c of pickN(countryIds, 2 + Math.floor(rand() * 3))) {
      addLink(hlo, "LOCATED_IN", c, { share_pct: 10 + Math.floor(rand() * 60), sheet: "Countries of Implementation" }, "high");
    }
    const other = PROGRAMS[(i % 12) + 1];
    addLink(hlo, "SYNERGY_WITH", `trace:program:${other[0]}`, { sheet: "Synergy Programs" }, "medium");
    for (const cid of pickN(conceptIds.slice(0, 30), 2)) {
      addLink(hlo, "TAGGED_WITH", cid, { via: "pref_label", layer: 2, confidence: 0.96 }, "high");
    }
  });
  outcomeIds.forEach((oc) => {
    for (const cid of pickN(conceptIds.slice(0, 30), 2)) addLink(oc, "TAGGED_WITH", cid, { via: "alt_label", layer: 2, confidence: 0.8 }, "medium");
    addLink(oc, "LOCATED_IN", pick(regionIds), {}, "medium");
  });
  kpIds.forEach((kp) => {
    for (const cid of pickN(conceptIds.slice(0, 35), 1 + Math.floor(rand() * 3))) {
      addLink(kp, "TAGGED_WITH", cid, { via: chance(0.5) ? "pref_label" : "stem", layer: objects.get(cid).attrs.layer, confidence: 0.6 + rand() * 0.4 }, band());
    }
    if (chance(0.6)) addLink(kp, "LOCATED_IN", pick(countryIds), {}, "medium");
    if (chance(0.3)) addLink(kp, "PRODUCED_BY", institutionIds[Math.floor(rand() * 6)], {}, "medium");
  });

  // a couple of pending / superseded claims for the registry page
  const reviewSubjects = resultIds.slice(0, 6);
  reviewSubjects.forEach((s, i) => {
    const c = addClaim({
      kind: i % 3 === 0 ? "assert_attr" : "assert_link",
      subject: s,
      predicate: i % 3 === 0 ? null : "WITH_PARTNER",
      object: i % 3 === 0 ? null : institutionIds[i % institutionIds.length],
      payload: i % 3 === 0 ? { attrs: { budget_usd: 68600 } } : { attrs: { role: "contributing" } },
      attested_by: pick(["partner:demo-ngo", "person:j.berenguer", "agent:opus-5"]),
      provenance: pick(["signed", "recorded"]),
      evidence: [{ kind: "url", value: "https://example.org/evidence/partner-report.pdf" }],
      qa: { band: "medium", status: "review" },
    });
    c.qa.status = "review";
  });
  const superseded = addClaim({
    kind: "assert_attr",
    subject: resultIds[0],
    payload: { attrs: { status: "Submitted" } },
    attested_by: "ingest:prms@synapsis",
    qa: { band: "high", status: "accepted" },
  });
  addClaim({
    kind: "assert_attr",
    subject: resultIds[0],
    payload: { attrs: { status: "Quality Assessed" } },
    attested_by: "ingest:prms@synapsis",
    supersedes: superseded.id,
    qa: { band: "high", status: "accepted" },
  });
  addClaim({
    kind: "candidate_concept",
    subject: "trace:concept:L1-0301",
    object: "trace:concept:L2-0074",
    payload: { term: "demand-led breeding", occurrences: 34, layer: 1 },
    attested_by: "agent:opus-5",
    provenance: "recorded",
    qa: { band: "medium", status: "review" },
  });

  // claim_count per object
  const counts = new Map();
  for (const c of claims) {
    if (c.subject) counts.set(c.subject, (counts.get(c.subject) ?? 0) + 1);
    if (c.object) counts.set(c.object, (counts.get(c.object) ?? 0) + 1);
  }
  for (const [id, o] of objects) o.claim_count = counts.get(id) ?? 1;

  return { objects, links, claims };
}

export const LENSES = [
  {
    name: "portfolio",
    description: "Structure only: how the results framework is put together — program → area of work → high-level output → indicator/outcome. Use it to read the architecture, not the delivery.",
    paths: [
      ["program", "PART_OF", "aow", "PART_OF", "hlo", "PART_OF", "indicator"],
      ["program", "PART_OF", "outcome"],
      ["aow", "PART_OF", "program"],
      ["hlo", "PART_OF", "aow"],
      ["indicator", "PART_OF", "hlo"],
    ],
  },
  {
    name: "delivery",
    description: "What was delivered, where and by whom: result → high-level output/outcome/program, result → institution, result → country. The everyday reporting view.",
    paths: [
      ["result", "CONTRIBUTES_TO", "hlo", "PART_OF", "aow", "PART_OF", "program"],
      ["result", "CONTRIBUTES_TO", "outcome", "PART_OF", "program"],
      ["result", "CONTRIBUTES_TO", "indicator", "PART_OF", "hlo"],
      ["result", "REPORTED_UNDER", "program"],
      ["result", "PRODUCED_BY", "institution"],
      ["result", "WITH_PARTNER", "institution"],
      ["result", "LOCATED_IN", "country"],
      ["country", "LOCATED_IN", "region"],
    ],
  },
  {
    name: "evidence",
    description: "The evidence chain: innovation → result → knowledge product (SAME_AS / EVIDENCED_BY) → taxonomy concept. Follow a claim back to the artefact that supports it.",
    paths: [
      ["result", "SAME_AS", "kp"],
      ["result", "EVIDENCED_BY", "kp", "TAGGED_WITH", "concept"],
      ["result", "EVIDENCED_BY", "innovation"],
      ["kp", "DESCRIBES", "innovation"],
      ["kp", "AUTHORED_BY", "person"],
      ["result", "TAGGED_WITH", "concept", "BROADER", "concept"],
      ["concept", "CANDIDATE_FOR", "concept"],
      ["program", "EVIDENCED_BY", "kp"],
      ["program", "EVIDENCED_BY", "document"],
    ],
  },
  {
    name: "money",
    description: "Funding only: project → high-level output (FUNDED_BY) and budgets held as attributes on the HLO. It deliberately does NOT traverse result → country, because money cannot be prorated across neighbours.",
    paths: [
      ["project", "FUNDED_BY", "hlo", "PART_OF", "aow", "PART_OF", "program"],
      ["project", "FUNDED_BY", "result"],
      ["hlo", "WITH_PARTNER", "institution"],
    ],
    excludes: [["result", "LOCATED_IN", "country"]],
  },
  {
    name: "partnership",
    description: "Who works with whom: institution ↔ result ↔ program and institution ↔ high-level output (PORB partners) ↔ country.",
    paths: [
      ["institution", "WITH_PARTNER", "result", "REPORTED_UNDER", "program"],
      ["institution", "PRODUCED_BY", "result"],
      ["institution", "WITH_PARTNER", "hlo", "LOCATED_IN", "country"],
      ["hlo", "PART_OF", "aow", "PART_OF", "program"],
    ],
  },
];
