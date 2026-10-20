const css = (name: string): string => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const rgb = (hex: string): [number, number, number] => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number];

function mix(a: string, b: string, t: number): string {
  const A = rgb(a);
  const B = rgb(b);
  return "#" + A.map((x, i) => Math.round(x + (B[i] - x) * t).toString(16).padStart(2, "0")).join("");
}

/** Sequential luminance ramp (theme-aware through CSS variables); 0 stays the paper tone. */
export function heat(v: number, max: number): string {
  if (!v) return css("--heat-0");
  const t = Math.min(1, Math.log1p(v) / Math.log1p(max));
  const stops = ["--heat-1", "--heat-2", "--heat-3", "--heat-4"].map(css);
  const k = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(k));
  return mix(stops[i], stops[i + 1], k - i);
}
