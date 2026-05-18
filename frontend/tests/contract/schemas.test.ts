import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  agentWriteResponseSchema,
  appointmentListResponseSchema,
  errorBodySchema,
  feedListResponseSchema,
  poopListResponseSchema,
  sleepListResponseSchema,
} from "@/shared/types";

const fx = (name: string) =>
  JSON.parse(fs.readFileSync(path.resolve(__dirname, "../fixtures", name), "utf8"));

describe("contract: JSON fixtures parse against Zod schemas", () => {
  it("feeds.list.json", () => {
    expect(feedListResponseSchema.parse(fx("feeds.list.json"))).toBeDefined();
  });
  it("sleeps.list.json", () => {
    expect(sleepListResponseSchema.parse(fx("sleeps.list.json"))).toBeDefined();
  });
  it("poops.list.json", () => {
    expect(poopListResponseSchema.parse(fx("poops.list.json"))).toBeDefined();
  });
  it("appointments.list.json", () => {
    expect(appointmentListResponseSchema.parse(fx("appointments.list.json"))).toBeDefined();
  });
  it("entries.created.json", () => {
    expect(agentWriteResponseSchema.parse(fx("entries.created.json"))).toBeDefined();
  });
  it("entries.clarification.json", () => {
    expect(agentWriteResponseSchema.parse(fx("entries.clarification.json"))).toBeDefined();
  });
  it("error.validation.json", () => {
    expect(errorBodySchema.parse(fx("error.validation.json"))).toBeDefined();
  });
});
