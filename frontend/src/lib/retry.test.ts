// Unit tests for retrying busy reads: node --test (npm run test:unit)
import assert from "node:assert/strict";
import { test } from "node:test";
import { BUSY_RETRIES, busyRetryDelay } from "./retry.ts";

const half = () => 0.5;

test("a busy read is retried after about Retry-After seconds", () => {
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "5", 0, half), 5000);
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "5", 0, () => 0), 2500);
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "5", 0, () => 0.999), 7495);
});

test("missing or silly Retry-After values are kept within 1 to 10 seconds", () => {
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", null, 0, half), 5000);
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "0", 0, half), 5000);
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "600", 0, half), 10000);
});

test("only busy reads are retried, and only a few times", () => {
  assert.equal(busyRetryDelay("POST", 503, "SERVER_BUSY", "5", 0), null); // could repeat an answer
  assert.equal(busyRetryDelay("GET", 503, "CONTENT_NOT_SEEDED", "5", 0), null);
  assert.equal(busyRetryDelay("GET", 429, "TOO_MANY_EXPLANATION_REQUESTS", "5", 0), null);
  assert.equal(busyRetryDelay("GET", 503, "SERVER_BUSY", "5", BUSY_RETRIES), null);
});
