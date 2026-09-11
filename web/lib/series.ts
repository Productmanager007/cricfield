// Categorical slots 1 and 2 of the dataviz reference palette, dark-mode steps,
// validated against the page surface #0D1117. They carry identity only: the
// first player is always blue and the second orange, wherever they appear.
export const SERIES = { a: "#3987e5", b: "#d95926" } as const;

export type Side = keyof typeof SERIES;
