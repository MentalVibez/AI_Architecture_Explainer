import Link from "next/link";
import type { Metadata } from "next";

import { getCodebaseGuide, getResult } from "@/lib/api";
import { normalizeStackItems } from "@/lib/types";
import DeveloperSummary from "@/components/DeveloperSummary";
import HiringManagerSummary from "@/components/HiringManagerSummary";
import DiagramPanel from "@/components/DiagramPanel";
import WorkspaceSync from "@/components/workspace/WorkspaceSync";
import WorkspaceRunSync from "@/components/workspace/WorkspaceRunSync";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const result = await getResult(Number(id));
    const evidence = (result.raw_evidence?.[0] as Record<string, unknown>) ?? {};
    const repo = (evidence.repo as Record<string, string>) ?? {};
    const repoLabel = repo.owner && repo.name ? `${repo.owner}/${repo.name}` : `Report #${id}`;
    return {
      title: `${repoLabel} — Atlas Workspace | CodebaseAtlas`,
      description: `Architecture diagram, framework detection, and plain-English summaries for ${repoLabel}.`,
      openGraph: {
        title: `${repoLabel} — Atlas Workspace`,
        description: `Architecture diagram, framework detection, and summaries for ${repoLabel}.`,
        url: `https://www.codebaseatlas.com/results/${id}`,
      },
      robots: { index: false },
    };
  } catch {
    return {
      title: "Atlas Workspace | CodebaseAtlas",
      robots: { index: false },
    };
  }
}

export default async function ResultPage({ params }: Props) {
  const { id } = await params;
  const resultId = Number(id);
  const [result, guide] = await Promise.all([
    getResult(resultId),
    getCodebaseGuide(resultId),
  ]);

  const evidence = (result.raw_evidence?.[0] as Record<string, unknown>) ?? {};
  const repo = (evidence.repo as Record<string, string>) ?? {};
  const filesScanned = (evidence.tree_paths as string[])?.length ?? 0;
  const repoLabel = repo.owner && repo.name ? `${repo.owner}/${repo.name}` : null;
  const repoUrl = repoLabel ? `https://github.com/${repoLabel}` : null;
  const dependencyCount =
    (result.dependencies.npm?.length ?? 0) + (result.dependencies.python?.length ?? 0);
  const topStack = getTopStackSignals(result);
  const nextPaths = result.folder_map.slice(0, 4);
  const priorityActions = getAtlasNextActions({
    repoLabel,
    hasApiSurface: topStack.some((item) => item.category === "backend"),
    hasUnknowns: result.caveats.length > 0,
  });

  return (
    <div className="page-shell pt-14 space-y-8">
      {repoLabel && <WorkspaceSync repo={repoLabel} url={repoUrl} provider="github" />}
      {repoLabel && (
        <WorkspaceRunSync
          id={String(result.id)}
          kind="atlas"
          repo={repoLabel}
          href={`/results/${result.id}`}
          title="Architecture workspace"
          completedAt={result.created_at}
        />
      )}

      <header className="panel-strong rounded-[32px] p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#4d7cff]/25 bg-[#4d7cff]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-[#a9c2ff]">
                Atlas workspace
              </span>
              <span className="hero-kicker">
                Report #{result.id}
              </span>
            </div>
            <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-[-0.04em] text-[#f5f8ff] sm:text-5xl">
              {repoLabel ?? `Result #${result.id}`}
            </h1>
            <p className="mt-4 max-w-3xl text-[15px] leading-relaxed text-[#d7e4ff]">
              Deterministic evidence collected first, then translated into architecture and codebase guidance.
            </p>
          </div>

          <div className="flex w-full flex-col gap-2 rounded-[20px] border border-white/10 bg-white/[0.03] p-2 sm:w-auto sm:flex-row sm:flex-wrap sm:rounded-full sm:p-1">
            <Link
              href="/"
              className="rounded-full bg-[#4d7cff] px-4 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-white"
            >
              Analyze another repo
            </Link>
            <Link
              href={repoLabel ? `/review?repo=${encodeURIComponent(repoLabel)}` : "/review"}
              className="rounded-full px-4 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
            >
              Open Review
            </Link>
            <Link
              href={repoLabel ? `/map?repo=${encodeURIComponent(repoLabel)}` : "/map"}
              className="rounded-full px-4 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
            >
              Open Map
            </Link>
          </div>
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Files in evidence window" value={String(filesScanned)} />
          <Metric label="Detected dependencies" value={String(dependencyCount)} />
          <Metric label="Confidence" value={result.confidence_score != null ? result.confidence_score.toFixed(2) : "—"} />
          <Metric label="Entry points" value={String(result.entry_points.length)} />
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          {repoUrl && (
            <a
              href={repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:border-white/15 hover:text-white"
            >
              View repository ↗
            </a>
          )}
          {repoLabel && (
            <Link
              href={`/map?repo=${encodeURIComponent(repoLabel)}`}
              className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:border-white/15 hover:text-white"
            >
              Map this repo
            </Link>
          )}
        </div>
      </header>

      <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="panel rounded-[28px] p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#a9c2ff]">
            Key takeaways
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {topStack.length > 0 ? (
              topStack.map((item) => (
                <TakeawayCard
                  key={`${item.category}-${item.name}`}
                  label={item.category}
                  title={item.name}
                  detail={item.detail}
                />
              ))
            ) : (
              <TakeawayCard
                label="stack"
                title="No strong framework signal"
                detail="Use the diagram and folder map to orient manually."
              />
            )}
            <TakeawayCard
              label="entry"
              title={
                result.entry_points.length > 0
                  ? result.entry_points[0]
                  : "No clear entrypoint detected"
              }
              detail={
                result.entry_points.length > 1
                  ? `${result.entry_points.length} entry candidates detected.`
                  : "Best starting path from deterministic evidence."
              }
            />
            <TakeawayCard
              label="deps"
              title={
                dependencyCount > 0
                  ? summarizeDependencies(result)
                  : "No dependencies detected"
              }
              detail="High-signal packages surfaced from manifests."
            />
            <TakeawayCard
              label="confidence"
              title={confidenceLabel(result.confidence_score)}
              detail={
                result.caveats.length > 0
                  ? `${result.caveats.length} caveat${result.caveats.length === 1 ? "" : "s"} to keep in mind.`
                  : "No major caveats surfaced in the current evidence window."
              }
            />
          </div>
        </div>

        <div className="panel rounded-[28px] p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
            What to inspect next
          </p>
          <div className="mt-4 space-y-3">
            {priorityActions.map((action, index) => (
              <ActionRow key={`${index}-${action.title}`} index={index + 1} {...action} />
            ))}
          </div>
        </div>
      </section>

      {nextPaths.length > 0 && (
        <section className="panel rounded-[28px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
                High-signal paths
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
                Start with the files most likely to explain the shape of the repo.
              </h2>
            </div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
              Folder map preview
            </p>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {nextPaths.map((item) => (
              <div key={item.path} className="surface-note">
                <p className="font-mono text-[12px] text-[#edf4ff] break-all">{item.path}</p>
                <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[#7f95ba]">
                  {item.role}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <CodebaseGuideSection guide={guide} />

      {result.diagram_mermaid && <DiagramPanel mermaid={result.diagram_mermaid} />}

      <section id="developer-summary">
        <DeveloperSummary result={result} />
      </section>

      <HiringManagerSummary result={result} />
    </div>
  );
}

function CodebaseGuideSection({
  guide,
}: {
  guide: Awaited<ReturnType<typeof getCodebaseGuide>>;
}) {
  return (
    <section id="codebase-guide" className="panel-strong rounded-[32px] p-6 sm:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#a9c2ff]">
            Codebase Guide
          </p>
          <h2 className="mt-2 max-w-2xl text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
            Understand the system before you change it.
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[#a9bce0]">
            {guide.overview}
          </p>
        </div>
        <div className="grid min-w-[220px] grid-cols-2 gap-2">
          <Metric label="Reading path" value={String(guide.reading_path.length)} />
          <Metric label="Setup notes" value={String(guide.setup_blockers.length)} />
        </div>
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
            Investigation path
          </p>
          <div className="mt-4 space-y-3">
            {guide.week_plan.map((item) => (
              <div key={item.phase} className="surface-note">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#a9c2ff]">
                  {item.phase}
                </p>
                <h3 className="mt-2 text-base font-semibold text-[#f5f8ff]">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[#9fb2d2]">{item.goal}</p>
                <div className="mt-3 space-y-2">
                  {item.actions.slice(0, 4).map((action) => (
                    <p key={action} className="text-sm leading-relaxed text-[#d8e5ff]">
                      {action}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
            Code reading path
          </p>
          <div className="mt-4 space-y-3">
            {guide.reading_path.length > 0 ? (
              guide.reading_path.map((item, index) => (
                <div key={item.path} className="surface-note">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#4d7cff]/25 bg-[#4d7cff]/10 font-mono text-[10px] text-[#cfe0ff]">
                      {index + 1}
                    </span>
                    <div>
                      <p className="break-all font-mono text-[12px] text-[#edf4ff]">{item.path}</p>
                      <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{item.reason}</p>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="surface-note">
                <p className="text-sm leading-relaxed text-[#94a8cb]">
                  Atlas did not have enough path evidence to rank files. Start with the summary and ask a project owner for the main entry point.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <CodebaseGuideList
          title="Safe contribution paths"
          items={guide.starter_tasks.map((task) => ({
            title: task.title,
            detail: task.why_safe,
            meta: task.related_paths.join(", "),
          }))}
        />
        <CodebaseGuideList
          title="Change risk coach"
          items={guide.risk_notes.map((note) => ({
            title: note.title,
            detail: note.guidance,
            meta: note.related_paths.join(", "),
          }))}
        />
        <CodebaseGuideList
          title="Team questions"
          items={guide.team_questions.map((question) => ({
            title: question,
            detail: "",
            meta: "",
          }))}
        />
      </div>

      {guide.concepts.length > 0 && (
        <div className="mt-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
            Concept explainer
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {guide.concepts.map((concept) => (
              <div key={concept.name} className="surface-note">
                <h3 className="text-base font-semibold text-[#f5f8ff]">{concept.name}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{concept.explanation}</p>
                {concept.evidence.length > 0 && (
                  <p className="mt-3 break-all font-mono text-[11px] text-[#7f95ba]">
                    {concept.evidence[0]}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {guide.setup_blockers.length > 0 && (
        <div className="mt-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
            Setup readiness
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {guide.setup_blockers.map((blocker) => (
              <div key={blocker.title} className="surface-note">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#ffd98f]">
                  {blocker.severity}
                </p>
                <h3 className="mt-2 text-base font-semibold text-[#f5f8ff]">{blocker.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{blocker.guidance}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function CodebaseGuideList({
  title,
  items,
}: {
  title: string;
  items: Array<{ title: string; detail: string; meta: string }>;
}) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
        {title}
      </p>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div key={item.title} className="surface-note">
            <h3 className="text-sm font-semibold leading-relaxed text-[#edf4ff]">{item.title}</h3>
            {item.detail && <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{item.detail}</p>}
            {item.meta && <p className="mt-3 break-all font-mono text-[11px] text-[#7f95ba]">{item.meta}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-note">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">{label}</p>
      <p className="mt-2 font-mono text-[12px] text-[#dce8ff]">{value}</p>
    </div>
  );
}

function TakeawayCard({
  label,
  title,
  detail,
}: {
  label: string;
  title: string;
  detail: string;
}) {
  return (
    <div className="surface-note">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">{label}</p>
      <h3 className="mt-2 text-base font-semibold text-[#f5f8ff]">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{detail}</p>
    </div>
  );
}

function ActionRow({
  index,
  title,
  detail,
  href,
}: {
  index: number;
  title: string;
  detail: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 hover:bg-white/[0.05]"
    >
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#4d7cff]/25 bg-[#4d7cff]/10 font-mono text-[10px] text-[#cfe0ff]">
        {index}
      </span>
      <div>
        <p className="text-sm font-semibold text-[#edf4ff]">{title}</p>
        <p className="mt-1 text-sm leading-relaxed text-[#94a8cb]">{detail}</p>
      </div>
    </Link>
  );
}

function getTopStackSignals(result: Awaited<ReturnType<typeof getResult>>) {
  const categories = [
    { key: "backend", label: "backend" },
    { key: "frontend", label: "frontend" },
    { key: "database", label: "database" },
    { key: "infra", label: "infra" },
  ] as const;

  return categories
    .map(({ key, label }) => {
      const items = normalizeStackItems(result.detected_stack[key] ?? []);
      const top = items.sort((a, b) => b.confidence - a.confidence)[0];
      if (!top) {
        return null;
      }

      return {
        category: label,
        name: top.name,
        detail:
          top.evidence[0] ??
          `${Math.round(top.confidence * 100)}% confidence from repository evidence.`,
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .slice(0, 3);
}

function summarizeDependencies(result: Awaited<ReturnType<typeof getResult>>) {
  const npm = result.dependencies.npm ?? [];
  const python = result.dependencies.python ?? [];
  const top = [...npm, ...python].slice(0, 3);
  return top.join(", ");
}

function confidenceLabel(value: number | null) {
  if (value == null) return "Unknown confidence";
  if (value >= 0.85) return "High confidence";
  if (value >= 0.65) return "Moderate confidence";
  return "Low confidence";
}

function getAtlasNextActions({
  repoLabel,
  hasApiSurface,
  hasUnknowns,
}: {
  repoLabel: string | null;
  hasApiSurface: boolean;
  hasUnknowns: boolean;
}) {
  const repoQuery = repoLabel ? encodeURIComponent(repoLabel) : "";

  return [
    {
      title: "Open the architecture summary",
      detail: "Use the technical summary to verify the app boundary, stack, and likely runtime shape.",
      href: "#developer-summary",
    },
    {
      title: hasApiSurface ? "Map the API surface" : "Open Map for route confirmation",
      detail: hasApiSurface
        ? "Move straight into endpoint grouping and auth clues for the detected backend stack."
        : "Use Map to confirm whether the repo exposes a meaningful API surface.",
      href: repoQuery ? `/map?repo=${repoQuery}` : "/map",
    },
    {
      title: "Run a repository review",
      detail: hasUnknowns
        ? "Review is the best next pass when Atlas surfaced caveats or uncertain signals."
        : "Review will score quality, reliability, testing, and operational readiness.",
      href: repoQuery ? `/review?repo=${repoQuery}` : "/review",
    },
  ];
}
