/**
 * Where sent requests (for idempotency) and received callbacks (results) are kept.
 *
 * MemoryStore is fine for tests and single-process scripts. In production, implement
 * Store on your database so a restart never forgets what was already paid.
 */

import type { Parsed } from "./helpers.ts";

/** Only FAILED may be re-sent under the same idempotency key: ACCEPTED and UNKNOWN might still complete. */
export type Status = "ACCEPTED" | "SUCCESS" | "FAILED" | "UNKNOWN";
export const OPEN_STATUSES: readonly Status[] = ["ACCEPTED", "UNKNOWN"];

export interface RequestRecord {
  key: string;
  kind: string;
  status: Status;
  response: Record<string, any>;
  ids: string[];
}

export interface Store {
  /** By idempotency key, or by any Daraja ID saved with the request. */
  getRequest(keyOrId: string): Promise<RequestRecord | undefined>;
  saveRequest(record: RequestRecord): Promise<void>;
  /** Record a result and move any matching open request to its final status. */
  addResult(correlationIds: string[], status: Status, parsed: Parsed): Promise<void>;
  /** The most recent result stored under any of these IDs. */
  latestResult(ids: string[]): Promise<{ status: Status; parsed: Parsed } | undefined>;
}

export class MemoryStore implements Store {
  private requests = new Map<string, RequestRecord>();
  private index = new Map<string, string>();
  private results: { id: string; status: Status; parsed: Parsed }[] = [];

  async getRequest(keyOrId: string) {
    const rec = this.requests.get(keyOrId) ?? this.requests.get(this.index.get(keyOrId) ?? "");
    return rec && structuredClone(rec);
  }

  async saveRequest(record: RequestRecord) {
    const prev = this.requests.get(record.key);
    const ids = [...new Set([...(prev?.ids ?? []), ...record.ids.filter(Boolean)])];
    this.requests.set(record.key, structuredClone({ ...record, ids }));
    for (const id of ids) this.index.set(id, record.key);
  }

  async addResult(correlationIds: string[], status: Status, parsed: Parsed) {
    for (const id of new Set(correlationIds.filter(Boolean))) {
      this.results.push({ id, status, parsed: structuredClone(parsed) });
      const rec = this.requests.get(this.index.get(id) ?? "");
      if (rec && OPEN_STATUSES.includes(rec.status)) rec.status = status;
    }
  }

  async latestResult(ids: string[]) {
    const wanted = new Set(ids.filter(Boolean));
    for (let i = this.results.length - 1; i >= 0; i--) {
      const r = this.results[i];
      if (wanted.has(r.id)) return { status: r.status, parsed: structuredClone(r.parsed) };
    }
    return undefined;
  }
}
