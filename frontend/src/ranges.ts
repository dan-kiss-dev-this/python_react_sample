// Trading days shown per chart range
export const RANGES = { '3M': 63, '6M': 126, '1Y': 252, '2Y': Infinity } as const
export type Range = keyof typeof RANGES
