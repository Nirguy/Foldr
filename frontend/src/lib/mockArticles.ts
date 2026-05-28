import { ArticleAnalysis } from "@/types/article";

export const MOCK_ARTICLES: ArticleAnalysis[] = [
  {
    id: "1",
    title: "Long-term effects of intermittent fasting on metabolic health markers",
    authors: ["Dr. Sarah Chen", "Prof. James Okafor"],
    publishedYear: 2023,
    journal: "Nature Metabolism",
    credibility: {
      score: 8.5,
      explanation:
        "Authors are affiliated with Johns Hopkins and the University of Lagos, both well-regarded institutions. The study was independently funded with no pharmaceutical sponsorship declared.",
      institutionKnown: true,
      conflictsOfInterest: false,
    },
    consensus: {
      verdict: "Mostly aligned",
      reasoning:
        "Findings are broadly consistent with existing meta-analyses on intermittent fasting. The magnitude of effect on insulin sensitivity is slightly higher than the current consensus range but within plausible bounds.",
    },
    methodology: {
      score: 7.5,
      weaknesses: [
        "Sample size of 84 participants is modest for a 12-month longitudinal study.",
        "Self-reported dietary adherence introduces recall bias.",
        "No active control group — comparison is against baseline only.",
      ],
    },
    bias: {
      warnings: ["Overconfident language"],
      confidenceLevel: "Medium",
      details:
        'Abstract uses phrases like "definitively demonstrates" which overstates certainty given the sample size. Statistical methods are otherwise sound.',
    },
    overallTrustScore: 7.8,
    context: {
      summary:
        "This 12-month RCT examined 84 adults following a 16:8 intermittent fasting protocol. Key findings include a 14% reduction in fasting insulin and modest improvements in LDL cholesterol. The authors conclude that IF is a viable long-term metabolic intervention.",
      keyConcerns: [
        "Small sample limits generalisability.",
        "Dropout rate of 22% may introduce survivorship bias.",
      ],
      relatedStudies: [
        {
          title: "Intermittent fasting and metabolic health: a meta-analysis (2022)",
          relation: "supports",
          url: "https://doi.org/10.1016/example",
        },
        {
          title: "No significant metabolic benefit of IF vs caloric restriction (2021)",
          relation: "contradicts",
        },
      ],
    },
  },
  {
    id: "2",
    title: "5G radiation and cognitive decline: a population-level analysis",
    authors: ["M. Holloway", "T. Brecht"],
    publishedYear: 2022,
    journal: "Journal of Speculative Medicine",
    credibility: {
      score: 2.1,
      explanation:
        "Authors' institutional affiliations are not verifiable. The journal has no impact factor and is not indexed in PubMed or Scopus. One author has previously published in retracted outlets.",
      institutionKnown: false,
      conflictsOfInterest: true,
    },
    consensus: {
      verdict: "Contradicts consensus",
      reasoning:
        "The WHO, IEEE, and ICNIRP have all concluded that 5G frequencies at regulated exposure levels pose no neurological risk. This paper's conclusions directly contradict that body of evidence without providing mechanistic justification.",
    },
    methodology: {
      score: 1.8,
      weaknesses: [
        "Correlation-only analysis with no causal mechanism proposed.",
        "Confounding variables (age, pre-existing conditions, socioeconomic status) not controlled.",
        "Data sourced from a single county with no replication.",
        "Statistical significance threshold set at p < 0.1, inflating false positives.",
      ],
    },
    bias: {
      warnings: [
        "Cherry-picked stats",
        "Correlation vs causation",
        "Overconfident language",
        "Misleading graphs",
      ],
      confidenceLevel: "High",
      details:
        "Graphs use non-zero y-axis baselines to exaggerate effect sizes. The paper selectively cites studies that support its conclusion while ignoring the broader literature. Causal language is used throughout despite purely observational data.",
    },
    overallTrustScore: 1.5,
    context: {
      summary:
        "This observational study claims a correlation between 5G tower density and cognitive decline rates in a single US county between 2019–2021. The authors argue this constitutes evidence of neurological harm from 5G radiation.",
      keyConcerns: [
        "No peer review from credible independent reviewers.",
        "Timeframe overlaps with COVID-19 pandemic — a major confound ignored entirely.",
        "Funding source undisclosed.",
      ],
      relatedStudies: [
        {
          title: "WHO review: health effects of 5G exposure (2020)",
          relation: "contradicts",
          url: "https://www.who.int/example",
        },
        {
          title: "ICNIRP guidelines on RF-EMF exposure (2020)",
          relation: "contradicts",
        },
      ],
    },
  },
  {
    id: "3",
    title: "CRISPR-Cas9 off-target editing rates in human embryonic stem cells",
    authors: ["Prof. Yuki Tanaka", "Dr. Amara Diallo", "Dr. Lena Fischer"],
    publishedYear: 2024,
    journal: "Cell",
    credibility: {
      score: 9.2,
      explanation:
        "All three authors are from top-tier research institutions (Kyoto University, Institut Pasteur, Max Planck). The study was funded by public research grants with full disclosure. No conflicts of interest declared.",
      institutionKnown: true,
      conflictsOfInterest: false,
    },
    consensus: {
      verdict: "Mixed evidence",
      reasoning:
        "The off-target rates reported are lower than some prior studies but higher than others. The field is actively debating measurement methodology, and this paper contributes meaningfully without resolving the debate.",
    },
    methodology: {
      score: 9.0,
      weaknesses: [
        "Results may not generalise beyond the specific cell lines tested.",
        "Long-term epigenetic effects of off-target edits not assessed.",
      ],
    },
    bias: {
      warnings: [],
      confidenceLevel: "Low",
      details:
        "Language is appropriately hedged throughout. Limitations are clearly stated. No manipulative presentation of data detected.",
    },
    overallTrustScore: 9.1,
    context: {
      summary:
        "This study used whole-genome sequencing to quantify CRISPR-Cas9 off-target editing events across five human embryonic stem cell lines. The authors report a median off-target rate of 0.003% per guide RNA and propose a refined scoring model for guide RNA selection.",
      keyConcerns: [
        "Cell line specificity limits direct clinical translation.",
        "Computational off-target prediction tools still lag behind empirical measurement.",
      ],
      relatedStudies: [
        {
          title: "High-fidelity CRISPR variants reduce off-target effects (2023)",
          relation: "supports",
        },
        {
          title: "Unexpectedly high off-target rates in primary T-cells (2022)",
          relation: "contradicts",
        },
      ],
    },
  },
];
