import { z } from "zod";

// ---------- Enums ----------

export const feedTypeSchema = z.enum(["breast_milk", "formula", "solids", "water"]);
export type FeedType = z.infer<typeof feedTypeSchema>;

export const feedUnitSchema = z.enum(["ml", "g"]);
export type FeedUnit = z.infer<typeof feedUnitSchema>;

export const poopConsistencySchema = z.enum(["watery", "soft", "formed", "hard"]);
export type PoopConsistency = z.infer<typeof poopConsistencySchema>;

export const entryTypeSchema = z.enum(["feed", "sleep", "poop", "appointment"]);
export type EntryType = z.infer<typeof entryTypeSchema>;

// ---------- Wire entities ----------

const isoString = z.string().min(1);

export const feedEntrySchema = z.object({
  id: z.number().int().positive(),
  feed_type: feedTypeSchema,
  quantity: z.number().positive(),
  unit: feedUnitSchema,
  occurred_at: isoString,
  created_at: isoString,
  updated_at: isoString,
});
export type FeedEntry = z.infer<typeof feedEntrySchema>;

export const sleepEntrySchema = z.object({
  id: z.number().int().positive(),
  start_at: isoString,
  end_at: isoString,
  duration_minutes: z.number().int().nonnegative(),
  created_at: isoString,
  updated_at: isoString,
});
export type SleepEntry = z.infer<typeof sleepEntrySchema>;

export const poopEntrySchema = z.object({
  id: z.number().int().positive(),
  occurred_at: isoString,
  consistency: poopConsistencySchema,
  created_at: isoString,
  updated_at: isoString,
});
export type PoopEntry = z.infer<typeof poopEntrySchema>;

export const appointmentNoteSchema = z.object({
  id: z.number().int().positive(),
  body: z.string().min(1).max(2000),
  added_at: isoString,
});
export type AppointmentNote = z.infer<typeof appointmentNoteSchema>;

export const appointmentEntrySchema = z.object({
  id: z.number().int().positive(),
  scheduled_at: isoString,
  notes: z.array(appointmentNoteSchema),
  created_at: isoString,
  updated_at: isoString,
});
export type AppointmentEntry = z.infer<typeof appointmentEntrySchema>;

// ---------- List wrappers ----------

const dateString = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

function listResponse<T extends z.ZodTypeAny>(item: T) {
  return z.object({ date: dateString, items: z.array(item) });
}

export const feedListResponseSchema = listResponse(feedEntrySchema);
export type FeedListResponse = z.infer<typeof feedListResponseSchema>;

export const sleepListResponseSchema = listResponse(sleepEntrySchema);
export type SleepListResponse = z.infer<typeof sleepListResponseSchema>;

export const poopListResponseSchema = listResponse(poopEntrySchema);
export type PoopListResponse = z.infer<typeof poopListResponseSchema>;

export const appointmentListResponseSchema = listResponse(appointmentEntrySchema);
export type AppointmentListResponse = z.infer<typeof appointmentListResponseSchema>;

// ---------- Direct PATCH bodies (per-entry edit) ----------

export const feedUpdateSchema = z
  .object({
    feed_type: feedTypeSchema.optional(),
    quantity: z.number().positive().optional(),
    unit: feedUnitSchema.optional(),
    occurred_at: isoString.optional(),
  })
  .strict();
export type FeedUpdate = z.infer<typeof feedUpdateSchema>;

export const sleepUpdateSchema = z
  .object({
    start_at: isoString.optional(),
    end_at: isoString.optional(),
  })
  .strict();
export type SleepUpdate = z.infer<typeof sleepUpdateSchema>;

export const poopUpdateSchema = z
  .object({
    occurred_at: isoString.optional(),
    consistency: poopConsistencySchema.optional(),
  })
  .strict();
export type PoopUpdate = z.infer<typeof poopUpdateSchema>;

export const appointmentUpdateSchema = z
  .object({
    scheduled_at: isoString.optional(),
  })
  .strict();
export type AppointmentUpdate = z.infer<typeof appointmentUpdateSchema>;

// ---------- Direct POST body (feed quick-log) ----------

export const feedCreateSchema = z
  .object({
    feed_type: feedTypeSchema,
    quantity: z.number().positive(),
    unit: feedUnitSchema,
    occurred_at: isoString,
  })
  .strict();
export type FeedCreate = z.infer<typeof feedCreateSchema>;

export const poopCreateSchema = z
  .object({
    occurred_at: isoString,
    consistency: poopConsistencySchema,
  })
  .strict();
export type PoopCreate = z.infer<typeof poopCreateSchema>;

export const sleepCreateSchema = z
  .object({
    start_at: isoString,
    end_at: isoString,
  })
  .strict();
export type SleepCreate = z.infer<typeof sleepCreateSchema>;

export const appointmentCreateSchema = z
  .object({
    scheduled_at: isoString,
    note: z.string().min(1).max(2000).optional(),
  })
  .strict();
export type AppointmentCreate = z.infer<typeof appointmentCreateSchema>;

// ---------- Agent write envelope ----------

export const agentWriteRequestSchema = z.object({
  message: z.string().min(1),
  reference_date: dateString.optional(),
});
export type AgentWriteRequest = z.infer<typeof agentWriteRequestSchema>;

const anyEntrySchema = z.union([
  feedEntrySchema,
  sleepEntrySchema,
  poopEntrySchema,
  appointmentEntrySchema,
]);

const correlationId = z.string().min(1);

export const agentCreatedSchema = z.object({
  outcome: z.literal("created"),
  entry_type: entryTypeSchema,
  entry: anyEntrySchema,
  agent_message: z.string(),
  correlation_id: correlationId,
  session_id: z.string().optional(),
});

export const agentUpdatedSchema = z.object({
  outcome: z.literal("updated"),
  entry_type: entryTypeSchema,
  entry: anyEntrySchema,
  agent_message: z.string(),
  correlation_id: correlationId,
  session_id: z.string().optional(),
  unchanged: z.boolean().optional(),
});

export const agentDeletedSchema = z.object({
  outcome: z.literal("deleted"),
  entry_type: entryTypeSchema,
  entry: anyEntrySchema,
  agent_message: z.string(),
  correlation_id: correlationId,
  session_id: z.string().optional(),
});

export const targetCandidateSchema = z.object({
  entry_type: entryTypeSchema,
  entry_id: z.number().int().positive(),
  preview: z.string().optional(),
});

export const agentClarificationSchema = z.object({
  outcome: z.literal("clarification_requested"),
  agent_message: z.string(),
  suggested_candidates: z.array(targetCandidateSchema).optional(),
  correlation_id: correlationId,
  session_id: z.string().optional(),
});

export const agentRejectedSchema = z.object({
  outcome: z.literal("rejected"),
  agent_message: z.string(),
  correlation_id: correlationId,
  session_id: z.string().optional(),
});

export const agentWriteResponseSchema = z.discriminatedUnion("outcome", [
  agentCreatedSchema,
  agentUpdatedSchema,
  agentDeletedSchema,
  agentClarificationSchema,
  agentRejectedSchema,
]);
export type AgentWriteResponse = z.infer<typeof agentWriteResponseSchema>;

// ---------- Errors ----------

export const errorBodySchema = z.object({
  error: z.string(),
  message: z.string(),
  correlation_id: correlationId,
});
export type ErrorBody = z.infer<typeof errorBodySchema>;

// ---------- Auth & profiles (feature 006) ----------

export const okResponseSchema = z.object({ ok: z.literal(true) });

const emailSchema = z.string().email().max(254);
const passwordSchema = z.string().min(12).max(128);
const displayNameSchema = z.string().min(1).max(80);
const colorTagSchema = z.string().max(16);
const dateOfBirth = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

export const userPublicSchema = z.object({
  id: z.number().int().positive(),
  email: emailSchema,
  display_name: displayNameSchema,
  active_baby_id: z.number().int().positive().nullable(),
});
export type UserPublic = z.infer<typeof userPublicSchema>;

export const authMeSchema = z.object({ user: userPublicSchema });

export const registerRequestSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  display_name: displayNameSchema,
});
export type RegisterRequest = z.infer<typeof registerRequestSchema>;

export const loginRequestSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});
export type LoginRequest = z.infer<typeof loginRequestSchema>;

export const userUpdateSchema = z.object({
  display_name: displayNameSchema,
});
export type UserUpdate = z.infer<typeof userUpdateSchema>;

export const setActiveBabyRequestSchema = z.object({
  baby_id: z.number().int().positive(),
});
export type SetActiveBabyRequest = z.infer<typeof setActiveBabyRequestSchema>;

export const babySchema = z.object({
  id: z.number().int().positive(),
  owner_user_id: z.number().int().positive(),
  display_name: displayNameSchema,
  date_of_birth: dateOfBirth,
  color_tag: colorTagSchema.nullable(),
  created_at: isoString,
  updated_at: isoString,
});
export type Baby = z.infer<typeof babySchema>;

export const babyListResponseSchema = z.object({
  items: z.array(babySchema),
});
export type BabyListResponse = z.infer<typeof babyListResponseSchema>;

export const babyCreateSchema = z.object({
  display_name: displayNameSchema,
  date_of_birth: dateOfBirth,
  color_tag: colorTagSchema.optional(),
});
export type BabyCreate = z.infer<typeof babyCreateSchema>;

export const babyUpdateSchema = z.object({
  display_name: displayNameSchema.optional(),
  date_of_birth: dateOfBirth.optional(),
  color_tag: colorTagSchema.optional(),
});
export type BabyUpdate = z.infer<typeof babyUpdateSchema>;
