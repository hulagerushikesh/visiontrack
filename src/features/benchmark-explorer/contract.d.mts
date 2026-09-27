export type BenchmarkValidation = { valid: true } | { valid: false; error: string }
export function validateBenchmarkReport(value: unknown): BenchmarkValidation
