/**
 * Pieces both nodes share: a Daraja client from the credential, and a Store kept in the
 * workflow's static data so idempotency keys and callback results outlive one execution.
 */

import type { IDataObject } from "n8n-workflow";
import type { Daraja, Parsed, RequestRecord, Status, Store } from "mpesa-daraja";

// mpesa-daraja is ESM and n8n loads nodes with require(), so it is imported dynamically.
export const lib = () => import("mpesa-daraja");

const OPEN: Status[] = ["ACCEPTED", "UNKNOWN"];
const MAX_RESULTS = 500;

interface Data {
  requests: Record<string, RequestRecord>;
  index: Record<string, string>;
  results: { id: string; status: Status; parsed: Parsed }[];
}

/**
 * n8n saves static data only for production (active-workflow) executions, at the end of each
 * execution. Manual test runs start empty every time.
 */
export class StaticDataStore implements Store {
  private d: Data;
  constructor(staticData: IDataObject) {
    staticData.mpesa ??= { requests: {}, index: {}, results: [] };
    this.d = staticData.mpesa as unknown as Data;
  }

  async getRequest(keyOrId: string) {
    const rec = this.d.requests[keyOrId] ?? this.d.requests[this.d.index[keyOrId] ?? ""];
    return rec && structuredClone(rec);
  }

  async saveRequest(record: RequestRecord) {
    const prev = this.d.requests[record.key];
    const ids = [...new Set([...(prev?.ids ?? []), ...record.ids.filter(Boolean)])];
    this.d.requests[record.key] = structuredClone({ ...record, ids });
    for (const id of ids) this.d.index[id] = record.key;
  }

  async addResult(correlationIds: string[], status: Status, parsed: Parsed) {
    for (const id of new Set(correlationIds.filter(Boolean))) {
      this.d.results.push({ id, status, parsed: structuredClone(parsed) });
      const rec = this.d.requests[this.d.index[id] ?? ""];
      if (rec && OPEN.includes(rec.status)) rec.status = status;
    }
    this.d.results.splice(0, Math.max(0, this.d.results.length - MAX_RESULTS));
  }

  async latestResult(ids: string[]) {
    const wanted = new Set(ids.filter(Boolean));
    for (let i = this.d.results.length - 1; i >= 0; i--) {
      const r = this.d.results[i];
      if (wanted.has(r.id)) return { status: r.status, parsed: structuredClone(r.parsed) };
    }
    return undefined;
  }
}

export async function client(creds: IDataObject, store: Store, approved = false): Promise<Daraja> {
  const { Daraja } = await lib();
  const text = (k: string) => (typeof creds[k] === "string" && (creds[k] as string).trim()) || undefined;
  const threshold = Number(creds.approvalThreshold ?? 0);
  return new Daraja({
    env: creds.environment === "production" ? "production" : "sandbox",
    consumerKey: text("consumerKey") ?? "",
    consumerSecret: text("consumerSecret") ?? "",
    shortcode: text("shortcode"),
    passkey: text("passkey"),
    initiatorName: text("initiatorName"),
    securityCredential: text("securityCredential"),
    allowLiveMoneyMovement: creds.allowLiveMoneyMovement === true,
    readOnly: creds.readOnly === true,
    approvalThreshold: threshold > 0 ? threshold : undefined,
    allowedRecipients: text("allowedRecipients")?.split(","),
    // n8n has no prompt mid-run: approval comes from the node's Approved field, e.g. after a Wait/approval step.
    approve: () => approved,
    store,
  });
}
