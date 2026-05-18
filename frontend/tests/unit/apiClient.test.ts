import { beforeEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { ApiError, apiClient } from "@/shared/apiClient";
import { server } from "../_msw/setup";

const BASE = "http://localhost:8000";

describe("apiClient", () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it("getFeeds hits /v1/feeds?date=... and returns parsed payload", async () => {
    let seenUrl = "";
    let seenCid = "";
    server.use(
      http.get(`${BASE}/v1/feeds`, ({ request }) => {
        seenUrl = request.url;
        seenCid = request.headers.get("X-Correlation-ID") ?? "";
        return HttpResponse.json({ date: "2026-05-17", items: [] });
      }),
    );
    const res = await apiClient.getFeeds(new Date(2026, 4, 17));
    expect(res).toEqual({ date: "2026-05-17", items: [] });
    expect(seenUrl).toContain("/v1/feeds?date=2026-05-17");
    expect(seenCid).toMatch(/[0-9a-f-]{8,}/i);
  });

  it("postEntry posts JSON body and parses union response", async () => {
    let captured: unknown = null;
    server.use(
      http.post(`${BASE}/v1/entries`, async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({
          outcome: "clarification_requested",
          agent_message: "Need more info",
          correlation_id: "abc-123",
        });
      }),
    );
    const res = await apiClient.postEntry({ message: "hi" });
    expect(captured).toEqual({ message: "hi" });
    expect(res.outcome).toBe("clarification_requested");
  });

  it("maps non-2xx error envelopes into ApiError", async () => {
    server.use(
      http.get(`${BASE}/v1/feeds`, () =>
        HttpResponse.json(
          { error: "validation_error", message: "bad date", correlation_id: "cid-1" },
          { status: 400 },
        ),
      ),
    );
    await expect(apiClient.getFeeds(new Date())).rejects.toBeInstanceOf(ApiError);
    try {
      await apiClient.getFeeds(new Date());
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(400);
      expect(err.code).toBe("validation_error");
      expect(err.correlationId).toBe("cid-1");
    }
  });

  it("throws schema_error when the body does not match the schema", async () => {
    server.use(
      http.get(`${BASE}/v1/feeds`, () => HttpResponse.json({ wrong: true })),
    );
    try {
      await apiClient.getFeeds(new Date());
      expect.fail("should have thrown");
    } catch (e) {
      expect((e as ApiError).code).toBe("schema_error");
    }
  });

  it("emits a unique X-Correlation-ID per call", async () => {
    const seen: string[] = [];
    server.use(
      http.get(`${BASE}/v1/feeds`, ({ request }) => {
        seen.push(request.headers.get("X-Correlation-ID") ?? "");
        return HttpResponse.json({ date: "2026-05-17", items: [] });
      }),
    );
    await apiClient.getFeeds(new Date());
    await apiClient.getFeeds(new Date());
    expect(seen).toHaveLength(2);
    expect(seen[0]).not.toBe(seen[1]);
  });
});

// Ensure the type is consumed
void vi;
