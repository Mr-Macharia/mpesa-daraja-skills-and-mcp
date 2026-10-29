/**
 * Checks before money moves. Same order and rules as the MCP server; both pass
 * shared/fixtures/guardrails.json.
 */

import { normalizePhone } from "./helpers.ts";
import type { Store } from "./store.ts";

/** Asked for payouts above approvalThreshold, with a one-line summary. Return true to send. */
export type Approver = (summary: string) => boolean | Promise<boolean>;

export interface Guardrails {
  env: "sandbox" | "production";
  /** Production charges and payouts are refused unless this is true. */
  allowLiveMoneyMovement?: boolean;
  /** Refuse every call that moves money. */
  readOnly?: boolean;
  /** Payouts above this many shillings need `approve` to return true. */
  approvalThreshold?: number;
  /** Payouts may only go to these phones (any format) or shortcodes. */
  allowedRecipients?: string[];
  approve?: Approver;
}

/** A guardrail refused the request. Nothing was sent. */
export class GuardrailError extends Error {
  override name = "GuardrailError";
}

export function guardMoney(g: Guardrails): void {
  if (g.readOnly) throw new GuardrailError("Refusing to move money: this client runs read-only (DARAJA_READ_ONLY=true).");
  if (g.env === "production" && !g.allowLiveMoneyMovement) {
    throw new GuardrailError(
      "Refusing to move real money: set allowLiveMoneyMovement (DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true) " +
        "to enable production payouts and charges.",
    );
  }
}

function allowed(list: string[] | undefined): Set<string> | undefined {
  if (!list?.length) return undefined;
  // Phones in any accepted format compare as 2547XXXXXXXX; shortcodes compare as written.
  return new Set(list.map((e) => e.trim()).filter(Boolean).map((e) => (e.length >= 9 ? normalizePhone(e) : e)));
}

/**
 * Allowlist and approval checks for money leaving the business. A key that was already sent
 * (and did not fail) skips both: the stored request is returned without paying again.
 */
export async function guardPayout(
  g: Guardrails, store: Store, key: string, amount: number, recipient: string | null, summary: string,
): Promise<void> {
  const previous = await store.getRequest(key);
  if (previous && previous.status !== "FAILED") return;
  const list = allowed(g.allowedRecipients);
  if (list && recipient !== null && !list.has(recipient)) {
    throw new GuardrailError(`Refusing to pay ${recipient}: not in DARAJA_ALLOWED_RECIPIENTS. Nothing was sent.`);
  }
  const threshold = g.approvalThreshold;
  if (threshold === undefined || threshold === null || amount <= threshold) return;
  const needs = `${summary} is above DARAJA_APPROVAL_THRESHOLD (KES ${threshold.toLocaleString("en-KE")}) and needs approval.`;
  if (!g.approve) throw new GuardrailError(`${needs} No approve callback was given, so nothing was sent.`);
  if (!(await g.approve(`${needs} Send it?`))) throw new GuardrailError("Payout not approved. Nothing was sent.");
}
