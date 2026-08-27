import { createHash, randomUUID } from "node:crypto";
import { execFile, spawn } from "node:child_process";
import { Router, type IRouter } from "express";
import { and, count, desc, eq } from "drizzle-orm";
import {
  auditEventsTable,
  continuityEntriesTable,
  db,
  identityProposalsTable,
  identityVersionsTable,
  legalDocumentsTable,
  mattersTable,
  systemSettingsTable,
  toolProposalsTable,
} from "@workspace/db";
import {
  ConnectLocalModelBody,
  CreateMatterBody,
  CreateMatterQueryBody,
  CreateMatterQueryParams,
  CreateMatterQueryResponse,
  CreateMatterResponse,
  GetDashboardResponse,
  GetMatterParams,
  GetMatterResponse,
  GetSystemSettingsResponse,
  ListAuditEventsQueryParams,
  ListAuditEventsResponse,
  ListMatterDocumentsParams,
  ListMatterDocumentsResponse,
  ListMattersResponse,
  ListToolProposalsResponse,
  ReviewToolProposalBody,
  ReviewToolProposalParams,
  ReviewToolProposalResponse,
  UpdateSystemSettingsBody,
  UpdateSystemSettingsResponse,
  CreateContinuityEntryBody,
  CreateContinuityEntryResponse,
  CreateIdentityProposalBody,
  CreateIdentityProposalResponse,
  DeleteContinuityEntryParams,
  DeleteContinuityEntryResponse,
  GetIdentityOverviewResponse,
  ListContinuityEntriesResponse,
  ListIdentityProposalsResponse,
  ListIdentityVersionsParams,
  ListIdentityVersionsResponse,
  ReviewIdentityProposalBody,
  ReviewIdentityProposalParams,
  ReviewIdentityProposalResponse,
  UpdateAutonomyLevelBody,
  UpdateAutonomyLevelResponse,
  ConnectLocalModelResponse,
  DownloadLocalModelResponse,
  ExportQuinnStateResponse,
  GetLocalModelStatusResponse,
} from "@workspace/api-zod";

const AGENT_NAME = "Quinn";

const router: IRouter = Router();

// Calls a local (loopback-only) OpenAI-compatible or Ollama endpoint.
// Returns null on any failure so callers can fall back honestly.
async function generateWithLocalModel(
  endpoint: string,
  model: string,
  system: string,
  prompt: string,
): Promise<string | null> {
  const base = endpoint.replace(/\/+$/, "");
  const attempts = [
    {
      url: `${base}/v1/chat/completions`,
      body: {
        model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: prompt },
        ],
        stream: false,
      },
      pick: (data: any): string | undefined =>
        data?.choices?.[0]?.message?.content,
    },
    {
      url: `${base}/api/chat`,
      body: {
        model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: prompt },
        ],
        stream: false,
      },
      pick: (data: any): string | undefined => data?.message?.content,
    },
  ];
  for (const attempt of attempts) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 120_000);
      const response = await fetch(attempt.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(attempt.body),
        signal: controller.signal,
        redirect: "error", // a loopback URL must never redirect us elsewhere
      });
      clearTimeout(timer);
      if (!response.ok) continue;
      const data = await response.json();
      const text = attempt.pick(data);
      if (typeof text === "string" && text.trim().length > 0) {
        return text.trim();
      }
    } catch {
      // try next shape
    }
  }
  return null;
}

function iso(value: Date): string {
  return value.toISOString();
}

async function documentCountForMatter(matterId: string): Promise<number> {
  const [row] = await db
    .select({ value: count() })
    .from(legalDocumentsTable)
    .where(eq(legalDocumentsTable.matterId, matterId));
  return Number(row?.value ?? 0);
}

async function serializeMatter(matter: typeof mattersTable.$inferSelect) {
  return {
    id: matter.id,
    name: matter.name,
    clientReference: matter.clientReference,
    type: matter.type,
    status: matter.status,
    documentCount: await documentCountForMatter(matter.id),
    lastActivityAt: iso(matter.lastActivityAt),
    createdAt: iso(matter.createdAt),
  };
}

async function appendAuditEvent(input: {
  category: string;
  action: string;
  actor: string;
  outcome: string;
  matterId?: string | null;
}): Promise<void> {
  const [previous] = await db
    .select({ chainHash: auditEventsTable.chainHash })
    .from(auditEventsTable)
    .orderBy(desc(auditEventsTable.occurredAt))
    .limit(1);
  const occurredAt = new Date();
  const id = `audit-${randomUUID()}`;
  const chainHash = createHash("sha256")
    .update(
      [
        previous?.chainHash ?? "genesis",
        id,
        input.category,
        input.action,
        input.actor,
        input.outcome,
        input.matterId ?? "",
        occurredAt.toISOString(),
      ].join("|"),
    )
    .digest("hex")
    .slice(0, 16);

  await db.insert(auditEventsTable).values({
    id,
    ...input,
    matterId: input.matterId ?? null,
    occurredAt,
    chainHash,
  });
}

type IdentityVersionRow = typeof identityVersionsTable.$inferSelect;

function serializeIdentityVersion(row: IdentityVersionRow) {
  return {
    id: row.id,
    identityKind: row.identityKind,
    version: row.version,
    content: row.content,
    author: row.author,
    rationale: row.rationale,
    changeSummary: row.changeSummary,
    createdAt: iso(row.createdAt),
  };
}

async function activeIdentityVersion(
  kind: "professional" | "personal",
): Promise<IdentityVersionRow | undefined> {
  const [row] = await db
    .select()
    .from(identityVersionsTable)
    .where(eq(identityVersionsTable.identityKind, kind))
    .orderBy(desc(identityVersionsTable.version))
    .limit(1);
  return row;
}

function serializeIdentityProposal(
  proposal: typeof identityProposalsTable.$inferSelect,
) {
  return {
    id: proposal.id,
    identityKind: proposal.identityKind,
    proposedContent: proposal.proposedContent,
    rationale: proposal.rationale,
    author: proposal.author,
    status: proposal.status,
    requestedAt: iso(proposal.requestedAt),
    reviewedAt: proposal.reviewedAt ? iso(proposal.reviewedAt) : null,
    reviewNote: proposal.reviewNote ?? null,
  };
}

async function applyIdentityProposal(
  proposal: typeof identityProposalsTable.$inferSelect,
): Promise<void> {
  const current = await activeIdentityVersion(
    proposal.identityKind as "professional" | "personal",
  );
  await db.insert(identityVersionsTable).values({
    id: `identity-${randomUUID()}`,
    identityKind: proposal.identityKind,
    version: (current?.version ?? 0) + 1,
    content: proposal.proposedContent,
    author: proposal.author,
    rationale: proposal.rationale,
    changeSummary:
      proposal.status === "auto_applied"
        ? "Applied under notify-and-apply autonomy (personal identity only)"
        : "Applied after attorney review",
    createdAt: new Date(),
  });
}

router.get("/identity", async (_req, res): Promise<void> => {
  const [professional, personal, settings, pendingRows] = await Promise.all([
    activeIdentityVersion("professional"),
    activeIdentityVersion("personal"),
    db
      .select()
      .from(systemSettingsTable)
      .where(eq(systemSettingsTable.id, "default"))
      .then((rows) => rows[0]),
    db
      .select({ value: count() })
      .from(identityProposalsTable)
      .where(eq(identityProposalsTable.status, "pending")),
  ]);
  if (!professional || !personal) {
    res.status(404).json({ error: "Identity not initialized" });
    return;
  }

  res.json(
    GetIdentityOverviewResponse.parse({
      agentName: AGENT_NAME,
      professional: serializeIdentityVersion(professional),
      personal: serializeIdentityVersion(personal),
      autonomyLevel: settings?.personalAutonomyLevel ?? "full_review",
      pendingProposalCount: Number(pendingRows[0]?.value ?? 0),
    }),
  );
});

router.get(
  "/identity/:identityKind/versions",
  async (req, res): Promise<void> => {
    const params = ListIdentityVersionsParams.safeParse(req.params);
    if (!params.success) {
      res.status(400).json({ error: params.error.message });
      return;
    }
    const rows = await db
      .select()
      .from(identityVersionsTable)
      .where(eq(identityVersionsTable.identityKind, params.data.identityKind))
      .orderBy(desc(identityVersionsTable.version));
    res.json(ListIdentityVersionsResponse.parse(rows.map(serializeIdentityVersion)));
  },
);

router.patch("/identity/autonomy", async (req, res): Promise<void> => {
  const body = UpdateAutonomyLevelBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  // The autonomy dial only governs personal-identity proposals. Hard safety
  // settings and the professional identity are unaffected by design.
  await db
    .update(systemSettingsTable)
    .set({ personalAutonomyLevel: body.data.autonomyLevel, updatedAt: new Date() })
    .where(eq(systemSettingsTable.id, "default"));

  await appendAuditEvent({
    category: "identity",
    action: `Set personal-identity autonomy level to ${body.data.autonomyLevel.replace("_", "-")}`,
    actor: "Attorney",
    outcome: "Applied",
  });

  const [professional, personal, pendingRows] = await Promise.all([
    activeIdentityVersion("professional"),
    activeIdentityVersion("personal"),
    db
      .select({ value: count() })
      .from(identityProposalsTable)
      .where(eq(identityProposalsTable.status, "pending")),
  ]);
  if (!professional || !personal) {
    res.status(404).json({ error: "Identity not initialized" });
    return;
  }
  res.json(
    UpdateAutonomyLevelResponse.parse({
      agentName: AGENT_NAME,
      professional: serializeIdentityVersion(professional),
      personal: serializeIdentityVersion(personal),
      autonomyLevel: body.data.autonomyLevel,
      pendingProposalCount: Number(pendingRows[0]?.value ?? 0),
    }),
  );
});

router.get("/identity-proposals", async (_req, res): Promise<void> => {
  const rows = await db
    .select()
    .from(identityProposalsTable)
    .orderBy(desc(identityProposalsTable.requestedAt));
  res.json(ListIdentityProposalsResponse.parse(rows.map(serializeIdentityProposal)));
});

router.post("/identity-proposals", async (req, res): Promise<void> => {
  const body = CreateIdentityProposalBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  const [settings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));

  // Routing rule: professional identity ALWAYS requires attorney review,
  // regardless of the autonomy dial. Personal identity may auto-apply only
  // when the dial is set to notify_and_apply.
  const autoApply =
    body.data.identityKind === "personal" &&
    body.data.author === "agent" &&
    settings?.personalAutonomyLevel === "notify_and_apply";

  const now = new Date();
  const [proposal] = await db
    .insert(identityProposalsTable)
    .values({
      id: `idprop-${randomUUID()}`,
      identityKind: body.data.identityKind,
      proposedContent: body.data.proposedContent,
      rationale: body.data.rationale,
      author: body.data.author,
      status: autoApply ? "auto_applied" : "pending",
      requestedAt: now,
      reviewedAt: autoApply ? now : null,
      reviewNote: autoApply
        ? "Applied automatically under notify-and-apply autonomy; remains reversible."
        : null,
    })
    .returning();

  if (autoApply) {
    await applyIdentityProposal(proposal);
  }

  await appendAuditEvent({
    category: "identity",
    action: `${body.data.author === "agent" ? AGENT_NAME : "Attorney"} proposed a ${body.data.identityKind} identity change`,
    actor: body.data.author === "agent" ? AGENT_NAME : "Attorney",
    outcome: autoApply ? "Auto-applied (notify-and-apply)" : "Pending attorney review",
  });

  res
    .status(201)
    .json(CreateIdentityProposalResponse.parse(serializeIdentityProposal(proposal)));
});

router.post(
  "/identity-proposals/:proposalId/review",
  async (req, res): Promise<void> => {
    const params = ReviewIdentityProposalParams.safeParse(req.params);
    const body = ReviewIdentityProposalBody.safeParse(req.body);
    if (!params.success) {
      res.status(400).json({ error: params.error.message });
      return;
    }
    if (!body.success) {
      res.status(400).json({ error: body.error.message });
      return;
    }

    const [existing] = await db
      .select()
      .from(identityProposalsTable)
      .where(eq(identityProposalsTable.id, params.data.proposalId));
    if (!existing) {
      res.status(404).json({ error: "Identity proposal not found" });
      return;
    }
    if (existing.status !== "pending") {
      res.status(400).json({ error: "Proposal has already been resolved" });
      return;
    }

    // Conditional update: only a still-pending proposal can be resolved, so two
    // concurrent reviews cannot both apply.
    const [proposal] = await db
      .update(identityProposalsTable)
      .set({
        status: body.data.decision,
        reviewedAt: new Date(),
        reviewNote: body.data.note,
      })
      .where(
        and(
          eq(identityProposalsTable.id, params.data.proposalId),
          eq(identityProposalsTable.status, "pending"),
        ),
      )
      .returning();
    if (!proposal) {
      res.status(409).json({ error: "Proposal was already resolved" });
      return;
    }

    if (proposal.status === "approved") {
      await applyIdentityProposal(proposal);
    }

    await appendAuditEvent({
      category: "identity",
      action: `Reviewed ${proposal.identityKind} identity change proposal`,
      actor: "Attorney",
      outcome: body.data.decision,
    });

    res.json(
      ReviewIdentityProposalResponse.parse(serializeIdentityProposal(proposal)),
    );
  },
);

router.get("/continuity-entries", async (_req, res): Promise<void> => {
  const rows = await db
    .select()
    .from(continuityEntriesTable)
    .orderBy(desc(continuityEntriesTable.createdAt));
  res.json(
    ListContinuityEntriesResponse.parse(
      rows.map((entry) => ({
        id: entry.id,
        identityKind: entry.identityKind,
        title: entry.title,
        content: entry.content,
        author: entry.author,
        createdAt: iso(entry.createdAt),
      })),
    ),
  );
});

router.post("/continuity-entries", async (req, res): Promise<void> => {
  const body = CreateContinuityEntryBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  const [entry] = await db
    .insert(continuityEntriesTable)
    .values({
      id: `cont-${randomUUID()}`,
      ...body.data,
      createdAt: new Date(),
    })
    .returning();

  await appendAuditEvent({
    category: "identity",
    action: `Added a ${entry.identityKind === "personal" ? "story" : "lesson"} continuity entry: ${entry.title}`,
    actor: entry.author === "agent" ? AGENT_NAME : "Attorney",
    outcome: "Recorded",
  });

  res.status(201).json(
    CreateContinuityEntryResponse.parse({
      id: entry.id,
      identityKind: entry.identityKind,
      title: entry.title,
      content: entry.content,
      author: entry.author,
      createdAt: iso(entry.createdAt),
    }),
  );
});

router.delete("/continuity-entries/:entryId", async (req, res): Promise<void> => {
  const params = DeleteContinuityEntryParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [removed] = await db
    .delete(continuityEntriesTable)
    .where(eq(continuityEntriesTable.id, params.data.entryId))
    .returning();
  if (!removed) {
    res.status(404).json({ error: "Continuity entry not found" });
    return;
  }

  await appendAuditEvent({
    category: "identity",
    action: `Removed continuity entry: ${removed.title}`,
    actor: "Attorney",
    outcome: "Removed",
  });

  res.json(DeleteContinuityEntryResponse.parse({ deleted: true }));
});

router.get("/dashboard", async (_req, res): Promise<void> => {
  const [matterTotal] = await db.select({ value: count() }).from(mattersTable);
  const [documentTotal] = await db
    .select({ value: count() })
    .from(legalDocumentsTable);
  const [approvalTotal] = await db
    .select({ value: count() })
    .from(toolProposalsTable)
    .where(eq(toolProposalsTable.status, "pending"));
  const [settings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));
  const recentRows = await db
    .select()
    .from(mattersTable)
    .orderBy(desc(mattersTable.lastActivityAt))
    .limit(3);
  const recentMatters = await Promise.all(recentRows.map(serializeMatter));

  res.json(
    GetDashboardResponse.parse({
      activeMatterCount: Number(matterTotal?.value ?? 0),
      indexedDocumentCount: Number(documentTotal?.value ?? 0),
      pendingApprovalCount: Number(approvalTotal?.value ?? 0),
      storageMode: "Local-only matter vault",
      modelStatus: settings?.modelStatus ?? "disconnected",
      recentMatters,
    }),
  );
});

router.get("/matters", async (_req, res): Promise<void> => {
  const rows = await db
    .select()
    .from(mattersTable)
    .orderBy(desc(mattersTable.lastActivityAt));
  const matters = await Promise.all(rows.map(serializeMatter));
  res.json(ListMattersResponse.parse(matters));
});

router.post("/matters", async (req, res): Promise<void> => {
  const body = CreateMatterBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  const now = new Date();
  const [matter] = await db
    .insert(mattersTable)
    .values({
      id: `matter-${randomUUID()}`,
      ...body.data,
      status: "active",
      createdAt: now,
      lastActivityAt: now,
    })
    .returning();

  await appendAuditEvent({
    category: "matter",
    action: `Created isolated matter workspace: ${matter.name}`,
    actor: "Attorney",
    outcome: "Completed",
    matterId: matter.id,
  });

  res.status(201).json(CreateMatterResponse.parse(await serializeMatter(matter)));
});

router.get("/matters/:matterId", async (req, res): Promise<void> => {
  const params = GetMatterParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [matter] = await db
    .select()
    .from(mattersTable)
    .where(eq(mattersTable.id, params.data.matterId));
  if (!matter) {
    res.status(404).json({ error: "Matter not found" });
    return;
  }

  res.json(GetMatterResponse.parse(await serializeMatter(matter)));
});

router.get("/matters/:matterId/documents", async (req, res): Promise<void> => {
  const params = ListMatterDocumentsParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const documents = await db
    .select()
    .from(legalDocumentsTable)
    .where(eq(legalDocumentsTable.matterId, params.data.matterId))
    .orderBy(desc(legalDocumentsTable.indexedAt));

  res.json(
    ListMatterDocumentsResponse.parse(
      documents.map((document) => ({
        id: document.id,
        matterId: document.matterId,
        name: document.name,
        kind: document.kind,
        pageCount: document.pageCount,
        indexedAt: iso(document.indexedAt),
        integrityHash: document.integrityHash,
        status: document.status,
      })),
    ),
  );
});

router.post("/matters/:matterId/queries", async (req, res): Promise<void> => {
  const params = CreateMatterQueryParams.safeParse(req.params);
  const body = CreateMatterQueryBody.safeParse(req.body);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  const [matter] = await db
    .select()
    .from(mattersTable)
    .where(eq(mattersTable.id, params.data.matterId));
  if (!matter) {
    res.status(404).json({ error: "Matter not found" });
    return;
  }

  const documents = await db
    .select()
    .from(legalDocumentsTable)
    .where(eq(legalDocumentsTable.matterId, matter.id))
    .orderBy(legalDocumentsTable.indexedAt)
    .limit(4);
  // Both active identities are composed into every model interaction as the
  // preamble; the versions used are returned with the answer for traceability.
  const [professionalIdentity, personalIdentity] = await Promise.all([
    activeIdentityVersion("professional"),
    activeIdentityVersion("personal"),
  ]);
  const citations = documents.slice(0, 3).map((document) => ({
    documentId: document.id,
    documentName: document.name,
    page: document.excerptPage,
    excerpt: document.excerpt,
  }));

  const [querySettings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));

  let answer: string | null = null;
  let disclaimer =
    "Demo retrieval uses indexed excerpts only. The local model is not connected in this environment. Verify every citation and conclusion.";

  if (
    querySettings?.modelStatus === "connected" &&
    isLoopbackEndpoint(querySettings.endpoint)
  ) {
    const preamble = [
      professionalIdentity?.content ?? "",
      personalIdentity?.content ?? "",
      "Answer only from the provided excerpts. Cite or abstain. Never invent authority.",
    ].join("\n\n");
    const context = citations
      .map((c) => `[${c.documentName}, p.${c.page}] ${c.excerpt}`)
      .join("\n");
    answer = await generateWithLocalModel(
      querySettings.endpoint,
      querySettings.model,
      preamble,
      `Matter: ${matter.name}\n\nExcerpts:\n${context}\n\nQuestion: ${body.data.question}`,
    );
    if (answer !== null) {
      disclaimer =
        "Generated by your local model from indexed excerpts only. Verify every citation and conclusion.";
    }
  }

  if (answer === null) {
    answer =
      documents.length === 0
        ? "No indexed documents are available in this matter. Add and index source material before asking a grounded question."
        : `The indexed record supports a preliminary, matter-scoped synthesis: ${citations
            .map((citation) => citation.excerpt)
            .join(" ")} This is a retrieval preview, not a legal conclusion.`;
  }

  await db
    .update(mattersTable)
    .set({ lastActivityAt: new Date() })
    .where(eq(mattersTable.id, matter.id));
  await appendAuditEvent({
    category: "retrieval",
    action: "Ran a matter-scoped document query",
    actor: "Attorney",
    outcome: `${citations.length} citations returned`,
    matterId: matter.id,
  });

  res.json(
    CreateMatterQueryResponse.parse({
      id: `answer-${randomUUID()}`,
      matterId: matter.id,
      question: body.data.question,
      answer,
      disclaimer,
      citations,
      createdAt: new Date().toISOString(),
      identityVersions: {
        agentName: AGENT_NAME,
        professionalVersion: professionalIdentity?.version ?? 0,
        personalVersion: personalIdentity?.version ?? 0,
      },
    }),
  );
});

router.get("/tool-proposals", async (_req, res): Promise<void> => {
  const rows = await db
    .select({
      proposal: toolProposalsTable,
      matterName: mattersTable.name,
    })
    .from(toolProposalsTable)
    .innerJoin(mattersTable, eq(toolProposalsTable.matterId, mattersTable.id))
    .orderBy(desc(toolProposalsTable.requestedAt));

  res.json(
    ListToolProposalsResponse.parse(
      rows.map(({ proposal, matterName }) => ({
        id: proposal.id,
        matterId: proposal.matterId,
        matterName,
        toolName: proposal.toolName,
        summary: proposal.summary,
        riskLevel: proposal.riskLevel,
        status: proposal.status,
        requestedAt: iso(proposal.requestedAt),
        reviewedAt: proposal.reviewedAt ? iso(proposal.reviewedAt) : null,
        dataBoundary: proposal.dataBoundary,
        reversible: proposal.reversible,
      })),
    ),
  );
});

router.post(
  "/tool-proposals/:proposalId/review",
  async (req, res): Promise<void> => {
    const params = ReviewToolProposalParams.safeParse(req.params);
    const body = ReviewToolProposalBody.safeParse(req.body);
    if (!params.success) {
      res.status(400).json({ error: params.error.message });
      return;
    }
    if (!body.success) {
      res.status(400).json({ error: body.error.message });
      return;
    }

    const [proposal] = await db
      .update(toolProposalsTable)
      .set({
        status: body.data.decision,
        reviewedAt: new Date(),
        reviewNote: body.data.note,
      })
      .where(eq(toolProposalsTable.id, params.data.proposalId))
      .returning();
    if (!proposal) {
      res.status(404).json({ error: "Tool proposal not found" });
      return;
    }
    const [matter] = await db
      .select()
      .from(mattersTable)
      .where(eq(mattersTable.id, proposal.matterId));

    await appendAuditEvent({
      category: "tool",
      action: `Reviewed ${proposal.toolName} proposal`,
      actor: "Attorney",
      outcome: body.data.decision,
      matterId: proposal.matterId,
    });

    res.json(
      ReviewToolProposalResponse.parse({
        id: proposal.id,
        matterId: proposal.matterId,
        matterName: matter?.name ?? "Unknown matter",
        toolName: proposal.toolName,
        summary: proposal.summary,
        riskLevel: proposal.riskLevel,
        status: proposal.status,
        requestedAt: iso(proposal.requestedAt),
        reviewedAt: proposal.reviewedAt ? iso(proposal.reviewedAt) : null,
        dataBoundary: proposal.dataBoundary,
        reversible: proposal.reversible,
      }),
    );
  },
);

router.get("/audit-events", async (req, res): Promise<void> => {
  const query = ListAuditEventsQueryParams.safeParse(req.query);
  if (!query.success) {
    res.status(400).json({ error: query.error.message });
    return;
  }
  const rows = await db
    .select()
    .from(auditEventsTable)
    .orderBy(desc(auditEventsTable.occurredAt))
    .limit(query.data.limit ?? 30);

  res.json(
    ListAuditEventsResponse.parse(
      rows.map((event) => ({
        id: event.id,
        category: event.category,
        action: event.action,
        actor: event.actor,
        outcome: event.outcome,
        matterId: event.matterId,
        occurredAt: iso(event.occurredAt),
        chainHash: event.chainHash,
      })),
    ),
  );
});

router.get("/settings", async (_req, res): Promise<void> => {
  const [settings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));
  if (!settings) {
    res.status(404).json({ error: "Settings not initialized" });
    return;
  }

  res.json(GetSystemSettingsResponse.parse(settings));
});

router.patch("/settings", async (req, res): Promise<void> => {
  const body = UpdateSystemSettingsBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }
  if (body.data.endpoint !== undefined && !isLoopbackEndpoint(body.data.endpoint)) {
    res.status(400).json({
      error:
        "Only local endpoints (localhost) are accepted. Cloud model providers are blocked by design.",
    });
    return;
  }

  const [settings] = await db
    .update(systemSettingsTable)
    .set({
      ...body.data,
      modelStatus: "disconnected",
      cloudProvidersBlocked: true,
      computerUseEnabled: false,
      updatedAt: new Date(),
    })
    .where(eq(systemSettingsTable.id, "default"))
    .returning();

  await appendAuditEvent({
    category: "settings",
    action: "Updated local model configuration",
    actor: "Attorney",
    outcome: "Saved; connection check required on Mac",
  });

  res.json(UpdateSystemSettingsResponse.parse(settings));
});

// --- Take Quinn Home: export, local model runtime -------------------------

// Hosted preview (Replit) vs. running on the attorney's own machine.
const RUNTIME_ENVIRONMENT: "hosted" | "local" = process.env.REPL_ID
  ? "hosted"
  : "local";

// Only loopback endpoints are ever accepted; cloud model providers stay
// blocked regardless of what is stored in settings or identity content.
function isLoopbackEndpoint(raw: string): boolean {
  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" && url.protocol !== "https:") return false;
    const host = url.hostname.toLowerCase();
    return (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "::1" ||
      host === "[::1]"
    );
  } catch {
    return false;
  }
}

function detectOllama(): Promise<boolean> {
  return new Promise((resolve) => {
    execFile("which", ["ollama"], (error, stdout) => {
      resolve(!error && stdout.trim().length > 0);
    });
  });
}

let modelDownloadState: { inProgress: boolean; detail: string } = {
  inProgress: false,
  detail: "",
};

async function localModelStatusPayload() {
  const [settings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));
  const runtimeDetected = await detectOllama();
  return {
    runtime: settings?.runtime ?? "ollama",
    endpoint: settings?.endpoint ?? "http://localhost:11434",
    model: settings?.model ?? "",
    modelStatus: modelDownloadState.inProgress
      ? "downloading"
      : (settings?.modelStatus ?? "disconnected"),
    environment: RUNTIME_ENVIRONMENT,
    runtimeDetected,
    detail: modelDownloadState.inProgress
      ? modelDownloadState.detail
      : RUNTIME_ENVIRONMENT === "hosted"
        ? "This is the hosted preview. Model download and connection happen on your own Mac after you bring Quinn home."
        : runtimeDetected
          ? "Local runtime detected."
          : "No local runtime found. The setup script installs Ollama for you.",
  };
}

router.get("/export", async (_req, res): Promise<void> => {
  const [identityVersions, identityProposals, continuityEntries, settingsRows, auditEvents] =
    await Promise.all([
      db.select().from(identityVersionsTable).orderBy(identityVersionsTable.createdAt),
      db.select().from(identityProposalsTable).orderBy(identityProposalsTable.requestedAt),
      db.select().from(continuityEntriesTable).orderBy(continuityEntriesTable.createdAt),
      db.select().from(systemSettingsTable).where(eq(systemSettingsTable.id, "default")),
      db.select().from(auditEventsTable).orderBy(auditEventsTable.occurredAt),
    ]);

  await appendAuditEvent({
    category: "identity",
    action: "Exported Quinn's full state bundle",
    actor: "Attorney",
    outcome: "Export generated",
  });

  res.setHeader(
    "Content-Disposition",
    `attachment; filename="quinn-export.json"`,
  );
  res.json(
    ExportQuinnStateResponse.parse({
      exportedAt: new Date().toISOString(),
      agentName: AGENT_NAME,
      formatVersion: 1,
      identityVersions,
      identityProposals,
      continuityEntries,
      settings: settingsRows[0] ?? {},
      auditEvents,
    }),
  );
});

router.get("/local-model/status", async (_req, res): Promise<void> => {
  res.json(GetLocalModelStatusResponse.parse(await localModelStatusPayload()));
});

router.post("/local-model/download", async (_req, res): Promise<void> => {
  if (RUNTIME_ENVIRONMENT === "hosted") {
    res.status(409).json(
      DownloadLocalModelResponse.parse({
        started: false,
        message:
          "Model downloads only run on your own Mac. Bring Quinn home first — the guide on this page walks you through it.",
      }),
    );
    return;
  }
  const runtimeDetected = await detectOllama();
  if (!runtimeDetected) {
    res.status(409).json(
      DownloadLocalModelResponse.parse({
        started: false,
        message:
          "Ollama isn't installed on this machine yet. Run the setup command from the guide — it installs everything needed.",
      }),
    );
    return;
  }
  if (modelDownloadState.inProgress) {
    res.json(
      DownloadLocalModelResponse.parse({
        started: true,
        message: "A download is already in progress.",
      }),
    );
    return;
  }

  const [settings] = await db
    .select()
    .from(systemSettingsTable)
    .where(eq(systemSettingsTable.id, "default"));
  const modelTag = settings?.model?.trim() || "qwen3.6:27b";
  modelDownloadState = {
    inProgress: true,
    detail: `Downloading ${modelTag} — this can take a while on first run.`,
  };

  const child = spawn("ollama", ["pull", modelTag], { stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", (chunk: Buffer) => {
    const line = chunk.toString().trim().split("\n").pop();
    if (line) modelDownloadState.detail = line.slice(0, 200);
  });
  child.on("close", (code) => {
    modelDownloadState = { inProgress: false, detail: "" };
    void (async () => {
      if (code === 0) {
        await db
          .update(systemSettingsTable)
          .set({ model: modelTag, modelStatus: "connected", updatedAt: new Date() })
          .where(eq(systemSettingsTable.id, "default"));
        await appendAuditEvent({
          category: "settings",
          action: `Downloaded local model ${modelTag}`,
          actor: "Attorney",
          outcome: "Model ready",
        });
      } else {
        await appendAuditEvent({
          category: "settings",
          action: `Local model download failed (${modelTag})`,
          actor: "Attorney",
          outcome: `Exit code ${code}`,
        });
      }
    })();
  });

  await appendAuditEvent({
    category: "settings",
    action: `Started local model download (${modelTag})`,
    actor: "Attorney",
    outcome: "Download started",
  });
  res.json(
    DownloadLocalModelResponse.parse({
      started: true,
      message: `Downloading ${modelTag}. You can watch progress here — nothing leaves your machine.`,
    }),
  );
});

router.post("/local-model/connect", async (req, res): Promise<void> => {
  const body = ConnectLocalModelBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }
  if (RUNTIME_ENVIRONMENT === "hosted") {
    res.status(409).json({
      error:
        "Model connections only happen on your own Mac. In this hosted preview there is no local model to connect to.",
    });
    return;
  }
  if (!isLoopbackEndpoint(body.data.endpoint)) {
    res.status(400).json({
      error:
        "Only local endpoints (localhost) are accepted. Cloud model providers are blocked by design.",
    });
    return;
  }

  let reachable = false;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);
    const probe = await fetch(body.data.endpoint, {
      signal: controller.signal,
      redirect: "error",
    });
    clearTimeout(timer);
    reachable = probe.status < 500;
  } catch {
    reachable = false;
  }

  const [settings] = await db
    .update(systemSettingsTable)
    .set({
      endpoint: body.data.endpoint,
      model: body.data.model,
      modelStatus: reachable ? "connected" : "disconnected",
      cloudProvidersBlocked: true,
      computerUseEnabled: false,
      updatedAt: new Date(),
    })
    .where(eq(systemSettingsTable.id, "default"))
    .returning();

  await appendAuditEvent({
    category: "settings",
    action: `Tested local model connection (${body.data.model})`,
    actor: "Attorney",
    outcome: reachable ? "Connected" : "Not reachable",
  });

  res.json(
    ConnectLocalModelResponse.parse({
      runtime: settings?.runtime ?? "ollama",
      endpoint: settings?.endpoint ?? body.data.endpoint,
      model: settings?.model ?? body.data.model,
      modelStatus: settings?.modelStatus ?? "disconnected",
      environment: RUNTIME_ENVIRONMENT,
      runtimeDetected: await detectOllama(),
      detail: reachable
        ? "Connected. Quinn's answers will now come from your local model."
        : "No local model answered at that address. Make sure the runtime is running, then try again.",
    }),
  );
});

export default router;
