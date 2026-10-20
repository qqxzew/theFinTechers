export interface Win {
  id: string;
  skim_lo: number;
  skim_hi: number;
  delay_bin: number;
  dormant: 0 | 1;
  day_lo: number;
  day_hi: number;
  obs: number;
  expected: number;
  banks: number;
  p: number;
  strength: string;
}

export interface Evidence {
  type: string;
  window?: { skim_lo: number; skim_hi: number; delay_bin: number; dormant: 0 | 1; day_lo: number; day_hi: number };
  totals: { observed: number; expected: number };
  banks: number;
  p_value: number;
  strength: string;
}

export interface Raised {
  client: string;
  evidence: Evidence;
}

export interface Day {
  t: number;
  date: string;
  banks: Record<string, number[][]>;
  total: number[][];
  windows: Win[];
  raised: Record<string, Raised[]>;
}

export interface Data {
  world: string;
  demo_view: boolean;
  hub_mode: string;
  script_jitter: string;
  banks: string[];
  delay_labels: string[];
  days: Day[];
}
