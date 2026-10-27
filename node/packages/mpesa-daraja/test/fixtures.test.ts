// The shared fixtures in shared/fixtures/: the Python package runs the same cases.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, test } from "node:test";

import {
  correlationIds, explainCode, guardMoney, guardPayout, MemoryStore, normalizePhone, parseCallback, RESULT_CODES,
  stkPassword, timestamp, validate, validateAmount,
} from "../src/index.ts";

const load = (name: string) => JSON.parse(readFileSync(new URL(`../../../../shared/fixtures/${name}`, import.meta.url), "utf8"));

describe("phones", () => {
  const data = load("phones.json");
  for (const c of data.valid) test(c.input, () => assert.equal(normalizePhone(c.input), c.msisdn));
  for (const raw of data.invalid) test(`invalid ${JSON.stringify(raw)}`, () => assert.throws(() => normalizePhone(raw)));
});

describe("amounts", () => {
  for (const c of load("amounts.json").cases) {
    test(`${JSON.stringify(c.amount)} >= ${c.minimum}`, () => {
      if (c.error) assert.throws(() => validateAmount(c.amount, c.minimum));
      else assert.equal(validateAmount(c.amount, c.minimum), c.ok);
    });
  }
});

test("STK password and timestamp", () => {
  const data = load("stk_password.json");
  for (const c of data.passwords) assert.equal(stkPassword(c.shortcode, c.passkey, c.timestamp), c.password);
  for (const c of data.timestamps) assert.equal(timestamp(new Date(c.utc)), c.eat);
});

test("result codes", () => {
  const data = load("result_codes.json");
  assert.deepEqual({ ...RESULT_CODES }, data.codes);
  assert.equal(explainCode("no-such-code"), data.unknown);
});

describe("validation", () => {
  for (const c of load("validation.json").cases) {
    test(c.name, () => {
      const errors = validate(c.api, c.body);
      assert.equal(errors.length, c.errors, JSON.stringify(errors));
      for (const text of c.contains) assert.ok(errors.some((e) => e.includes(text)), `${text} in ${JSON.stringify(errors)}`);
    });
  }
});

describe("callbacks", () => {
  const data = load("callbacks.json");
  for (const c of data.cases) {
    test(c.name, () => {
      const parsed = parseCallback(c.payload);
      assert.deepEqual(parsed, c.parsed);
      assert.deepEqual(correlationIds(parsed), c.correlation_ids);
    });
  }
  for (const p of data.unrecognised) test(`unrecognised ${JSON.stringify(p)}`, () => assert.throws(() => parseCallback(p)));
});

describe("guardrails", () => {
  for (const c of load("guardrails.json").cases) {
    test(c.name, async () => {
      const store = new MemoryStore();
      if (c.previous_status) await store.saveRequest({ key: "key-1", kind: "b2c", status: c.previous_status, response: {}, ids: [] });
      const answer = ({ yes: true, no: false } as Record<string, boolean>)[c.approver];
      const g = {
        env: c.env, allowLiveMoneyMovement: c.allow_live, readOnly: c.read_only,
        approvalThreshold: c.threshold ?? undefined, allowedRecipients: c.allowlist ?? undefined,
        approve: answer === undefined ? undefined : () => answer,
      };
      try {
        guardMoney(g);
        await guardPayout(g, store, "key-1", c.amount, c.recipient, "Payout");
        const previous = await store.getRequest("key-1");
        assert.equal(previous && previous.status !== "FAILED" ? "duplicate" : "send", c.expect);
      } catch (exc) {
        if (exc instanceof assert.AssertionError) throw exc;
        assert.equal(c.expect, "refuse", String(exc));
        assert.ok(String(exc).includes(c.contains), String(exc));
      }
    });
  }
});
