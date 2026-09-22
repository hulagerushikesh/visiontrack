export function canonicalJson(value: unknown): string
export function sha256Canonical(value: unknown): Promise<string>
export function createDecisionRecord<T extends object>(content: T): Promise<T & { decision_id: string }>
export function serializeDecision(decision: unknown): string
