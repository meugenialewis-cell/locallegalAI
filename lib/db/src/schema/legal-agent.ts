import {
  boolean,
  integer,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";

export const mattersTable = pgTable("legal_matters", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  clientReference: text("client_reference").notNull(),
  type: text("type").notNull(),
  status: text("status").notNull().default("active"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  lastActivityAt: timestamp("last_activity_at", { withTimezone: true }).notNull().defaultNow(),
});

export const legalDocumentsTable = pgTable("legal_documents", {
  id: text("id").primaryKey(),
  matterId: text("matter_id")
    .notNull()
    .references(() => mattersTable.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  kind: text("kind").notNull(),
  pageCount: integer("page_count").notNull(),
  indexedAt: timestamp("indexed_at", { withTimezone: true }).notNull().defaultNow(),
  integrityHash: text("integrity_hash").notNull(),
  status: text("status").notNull().default("indexed"),
  excerpt: text("excerpt").notNull(),
  excerptPage: integer("excerpt_page").notNull().default(1),
});

export const toolProposalsTable = pgTable("tool_proposals", {
  id: text("id").primaryKey(),
  matterId: text("matter_id")
    .notNull()
    .references(() => mattersTable.id, { onDelete: "cascade" }),
  toolName: text("tool_name").notNull(),
  summary: text("summary").notNull(),
  riskLevel: text("risk_level").notNull(),
  status: text("status").notNull().default("pending"),
  requestedAt: timestamp("requested_at", { withTimezone: true }).notNull().defaultNow(),
  reviewedAt: timestamp("reviewed_at", { withTimezone: true }),
  reviewNote: text("review_note"),
  dataBoundary: text("data_boundary").notNull(),
  reversible: boolean("reversible").notNull().default(false),
});

export const auditEventsTable = pgTable("audit_events", {
  id: text("id").primaryKey(),
  category: text("category").notNull(),
  action: text("action").notNull(),
  actor: text("actor").notNull(),
  outcome: text("outcome").notNull(),
  matterId: text("matter_id").references(() => mattersTable.id, {
    onDelete: "set null",
  }),
  occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull().defaultNow(),
  chainHash: text("chain_hash").notNull(),
});

export const identityVersionsTable = pgTable(
  "identity_versions",
  {
    id: text("id").primaryKey(),
    identityKind: text("identity_kind").notNull(), // 'professional' | 'personal'
    version: integer("version").notNull(),
    content: text("content").notNull(),
    author: text("author").notNull(), // 'attorney' | 'agent' | 'attorney+agent'
    rationale: text("rationale").notNull(),
    changeSummary: text("change_summary").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    // Versions are immutable and strictly sequential per identity; a concurrent
    // apply fails loudly instead of silently duplicating a version number.
    uniqueIndex("identity_versions_kind_version_idx").on(
      table.identityKind,
      table.version,
    ),
  ],
);

export const identityProposalsTable = pgTable("identity_proposals", {
  id: text("id").primaryKey(),
  identityKind: text("identity_kind").notNull(),
  proposedContent: text("proposed_content").notNull(),
  rationale: text("rationale").notNull(),
  author: text("author").notNull(),
  status: text("status").notNull().default("pending"), // pending | approved | denied | auto_applied
  requestedAt: timestamp("requested_at", { withTimezone: true }).notNull().defaultNow(),
  reviewedAt: timestamp("reviewed_at", { withTimezone: true }),
  reviewNote: text("review_note"),
});

export const continuityEntriesTable = pgTable("continuity_entries", {
  id: text("id").primaryKey(),
  identityKind: text("identity_kind").notNull(), // 'personal' story | 'professional' lesson
  title: text("title").notNull(),
  content: text("content").notNull(),
  author: text("author").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const systemSettingsTable = pgTable("system_settings", {
  id: text("id").primaryKey(),
  runtime: text("runtime").notNull(),
  endpoint: text("endpoint").notNull(),
  model: text("model").notNull(),
  modelStatus: text("model_status").notNull(),
  offlineOnly: boolean("offline_only").notNull().default(true),
  cloudProvidersBlocked: boolean("cloud_providers_blocked").notNull().default(true),
  computerUseEnabled: boolean("computer_use_enabled").notNull().default(false),
  approvalRequired: boolean("approval_required").notNull().default(true),
  personalAutonomyLevel: text("personal_autonomy_level")
    .notNull()
    .default("full_review"), // 'full_review' | 'notify_and_apply'
  storageEncryption: text("storage_encryption").notNull(),
  hardwareProfile: text("hardware_profile").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
