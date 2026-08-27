// Imports quinn-export.json (from the Take Quinn Home page) into the local
// database. Safe to re-run: rows that already exist are left untouched.
import { readFileSync } from "node:fs";
import pg from "pg";

const file = process.argv[2];
if (!file) {
  console.error("Usage: node scripts/import-quinn.mjs <quinn-export.json>");
  process.exit(1);
}

const bundle = JSON.parse(readFileSync(file, "utf8"));
if (bundle.formatVersion !== 1 || !Array.isArray(bundle.identityVersions)) {
  console.error("This file does not look like a Quinn export. Aborting.");
  process.exit(1);
}

const client = new pg.Client({
  connectionString: process.env.DATABASE_URL ?? "postgresql://localhost/locallegalai",
});
await client.connect();

async function importRows(table, rows, columns) {
  let inserted = 0;
  for (const row of rows) {
    const values = columns.map((c) => row[c.key] ?? null);
    const placeholders = columns.map((_, i) => `$${i + 1}`).join(", ");
    const names = columns.map((c) => c.col).join(", ");
    // ON CONFLICT DO NOTHING with no target: skips rows that collide with ANY
    // unique constraint (id, or e.g. identity (kind, version)) — safe re-runs.
    const result = await client.query(
      `INSERT INTO ${table} (${names}) VALUES (${placeholders}) ON CONFLICT DO NOTHING`,
      values,
    );
    inserted += result.rowCount;
  }
  console.log(`  ${table}: ${inserted} imported, ${rows.length - inserted} already present`);
}

console.log(`Importing ${bundle.agentName}'s state (exported ${bundle.exportedAt})…`);

await importRows("identity_versions", bundle.identityVersions, [
  { key: "id", col: "id" },
  { key: "identityKind", col: "identity_kind" },
  { key: "version", col: "version" },
  { key: "content", col: "content" },
  { key: "author", col: "author" },
  { key: "rationale", col: "rationale" },
  { key: "changeSummary", col: "change_summary" },
  { key: "createdAt", col: "created_at" },
]);

await importRows("identity_proposals", bundle.identityProposals ?? [], [
  { key: "id", col: "id" },
  { key: "identityKind", col: "identity_kind" },
  { key: "proposedContent", col: "proposed_content" },
  { key: "rationale", col: "rationale" },
  { key: "author", col: "author" },
  { key: "status", col: "status" },
  { key: "requestedAt", col: "requested_at" },
  { key: "reviewedAt", col: "reviewed_at" },
  { key: "reviewNote", col: "review_note" },
]);

await importRows("continuity_entries", bundle.continuityEntries ?? [], [
  { key: "id", col: "id" },
  { key: "identityKind", col: "identity_kind" },
  { key: "title", col: "title" },
  { key: "content", col: "content" },
  { key: "author", col: "author" },
  { key: "createdAt", col: "created_at" },
]);

// Matter records themselves are not part of the identity export, so imported
// audit history is detached from matter IDs (which would violate foreign keys
// on a fresh machine). The action text keeps the full context.
await importRows(
  "audit_events",
  (bundle.auditEvents ?? []).map((event) => ({ ...event, matterId: null })),
  [
    { key: "id", col: "id" },
    { key: "category", col: "category" },
    { key: "action", col: "action" },
    { key: "actor", col: "actor" },
    { key: "outcome", col: "outcome" },
    { key: "matterId", col: "matter_id" },
    { key: "occurredAt", col: "occurred_at" },
    { key: "chainHash", col: "chain_hash" },
  ],
);

if (bundle.settings && bundle.settings.id) {
  const s = bundle.settings;
  await client.query(
    `INSERT INTO system_settings
       (id, runtime, endpoint, model, model_status, offline_only, cloud_providers_blocked,
        computer_use_enabled, approval_required, personal_autonomy_level,
        storage_encryption, hardware_profile, updated_at)
     VALUES ($1,$2,$3,$4,'disconnected',$5,true,false,$6,$7,$8,$9,$10)
     ON CONFLICT (id) DO NOTHING`,
    [
      s.id, s.runtime, s.endpoint, s.model, s.offlineOnly ?? true,
      s.approvalRequired ?? true, s.personalAutonomyLevel ?? "full_review",
      s.storageEncryption ?? "AES-256", s.hardwareProfile ?? "Apple Silicon",
      s.updatedAt ?? new Date().toISOString(),
    ],
  );
  console.log("  system_settings: imported (hard safety limits re-enforced)");
}

await client.end();
console.log("Done. Quinn is home — with her whole history.");
