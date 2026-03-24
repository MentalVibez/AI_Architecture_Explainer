/**
 * components/AnalysisTabs.tsx
 *
 * Renders the Setup, Debug, and Change tabs for a completed analysis result.
 *
 * Data contract: receives the raw JSON fields directly from the API response.
 * No view model transformation — the JSON shape from the analyzer is the
 * same shape rendered here. This keeps the frontend honest about what
 * static analysis can and cannot claim.
 *
 * Claim boundary enforcement:
 * - Every tab shows tier_disclosure when rendered
 * - No tab invents language stronger than what the API returned
 * - SCAN_FAILED renders a warning card, not an error page
 * - NOT_FOUND renders "Not yet analyzed", not "No issues found"
 */

import React, { useState } from "react";

// ─────────────────────────────────────────────────────────
// Types — mirrors the API response shapes exactly
// ─────────────────────────────────────────────────────────

type ScanState = "found" | "not_found" | "scan_failed";
type RiskLevel = "low" | "medium" | "high";

interface EvidenceSignal {
  source_file: string;
  rule: string;
  detail?: string | null;
}

interface RiskItem {
  category: string;
  reason: string;
  rule: string;
  evidence: EvidenceSignal[];
}

// Setup Risk
interface SetupRisk {
  scan_state: ScanState;
  score: number | null;
  level: RiskLevel | null;
  confidence: number;
  missing_env_vars: string[];
  env_example_present: boolean;
  likely_start_commands: string[];
  required_services: string[];
  detected_manifests: string[];
  risks: RiskItem[];
  scan_errors: string[];
}

// Debug Readiness
interface SubSignal {
  scan_state: ScanState;
  framework?: string;
  frameworks?: string[];
  routes_found?: string[];
  sentry_found?: boolean;
  otel_found?: boolean;
  print_only_detected?: boolean;
}

interface DebugReadiness {
  scan_state: ScanState;
  score: number | null;
  level: RiskLevel | null;
  confidence: number;
  logging: SubSignal;
  error_handling: SubSignal;
  health_checks: SubSignal;
  tracing: SubSignal;
  test_harness: SubSignal;
  risks: RiskItem[];
  scan_errors: string[];
}

// Change Risk
interface BlastRadiusHotspot {
  path: string;
  category: string;
  reason: string;
}

interface CISignal {
  scan_state: ScanState;
  platforms: string[];
  has_test_gate: boolean;
  has_lint_gate: boolean;
}

interface MigrationRiskSignal {
  scan_state: ScanState;
  migration_paths: string[];
  has_migration_tests: boolean;
}

interface ChangeRisk {
  scan_state: ScanState;
  score: number | null;
  level: RiskLevel | null;
  confidence: number;
  ci: CISignal;
  test_gates: SubSignal;
  migration_risk: MigrationRiskSignal;
  blast_radius_hotspots: BlastRadiusHotspot[];
  risky_to_change: string[];
  risks: RiskItem[];
  scan_errors: string[];
}

interface AnalysisResult {
  setup_risk: SetupRisk | null;
  debug_readiness: DebugReadiness | null;
  change_risk: ChangeRisk | null;
  tier_disclosure: string;
  analysis_tier: string;
  runtime_verified: boolean;
}

// ─────────────────────────────────────────────────────────
// Shared primitives
// ─────────────────────────────────────────────────────────

const LEVEL_STYLES: Record<RiskLevel | "unknown", string> = {
  low:     "bg-green-50 text-green-700 border border-green-200",
  medium:  "bg-yellow-50 text-yellow-800 border border-yellow-200",
  high:    "bg-red-50 text-red-700 border border-red-200",
  unknown: "bg-gray-100 text-gray-500 border border-gray-200",
};

const STATE_LABEL: Record<ScanState, string> = {
  found:       "Analyzed",
  not_found:   "Not yet analyzed",
  scan_failed: "Analysis failed",
};

function LevelBadge({ level }: { level: RiskLevel | null }) {
  const key = (level ?? "unknown") as RiskLevel | "unknown";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${LEVEL_STYLES[key]}`}>
      {level ? level.charAt(0).toUpperCase() + level.slice(1) + " risk" : "Unknown"}
    </span>
  );
}

function ScanFailedCard({ errors }: { errors: string[] }) {
  return (
    <div className="rounded border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-medium text-amber-800">Analysis failed for this section</p>
      {errors.length > 0 && (
        <p className="mt-1 text-xs text-amber-700 font-mono">{errors[0]}</p>
      )}
    </div>
  );
}

function NotAnalyzedCard() {
  return (
    <div className="rounded border border-gray-200 bg-gray-50 p-4">
      <p className="text-sm text-gray-500">Not yet analyzed</p>
    </div>
  );
}

function SectionHeader({ label, state, level }: {
  label: string;
  state: ScanState;
  level: RiskLevel | null;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-base font-semibold text-gray-900">{label}</h3>
      <div className="flex items-center gap-2">
        {state === "found" && <LevelBadge level={level} />}
        {state !== "found" && (
          <span className="text-xs text-gray-400">{STATE_LABEL[state]}</span>
        )}
      </div>
    </div>
  );
}

function FoundIcon() {
  return <span className="text-green-500">✓</span>;
}

function MissingIcon() {
  return <span className="text-red-400">✗</span>;
}

function Row({ label, found, detail }: {
  label: string;
  found: boolean;
  detail?: string;
}) {
  return (
    <div className="flex items-start gap-2 py-1.5 text-sm">
      <span className="mt-0.5 w-4 shrink-0">{found ? <FoundIcon /> : <MissingIcon />}</span>
      <span className="text-gray-700">{label}</span>
      {detail && <span className="ml-auto text-xs text-gray-400 font-mono">{detail}</span>}
    </div>
  );
}

function CodeList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (items.length === 0) return <p className="text-xs text-gray-400">{emptyLabel}</p>;
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="font-mono text-xs bg-gray-100 rounded px-2 py-1 text-gray-700">
          {item}
        </li>
      ))}
    </ul>
  );
}

function RiskList({ risks }: { risks: RiskItem[] }) {
  if (risks.length === 0) return null;
  return (
    <div className="mt-4 space-y-2">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Risk signals</p>
      {risks.map((risk, i) => (
        <div key={i} className="rounded border border-gray-200 bg-white px-3 py-2">
          <p className="text-sm text-gray-800">{risk.reason}</p>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Setup Tab
// ─────────────────────────────────────────────────────────

function SetupTab({ data }: { data: SetupRisk | null }) {
  if (!data) return <NotAnalyzedCard />;
  if (data.scan_state === "scan_failed") return <ScanFailedCard errors={data.scan_errors} />;
  if (data.scan_state === "not_found") return <NotAnalyzedCard />;

  return (
    <div className="space-y-5">
      <SectionHeader label="Setup Risk" state={data.scan_state} level={data.level} />

      <div className="divide-y divide-gray-100 rounded border border-gray-200 bg-white">
        <div className="px-4 py-3">
          <Row
            label=".env.example present"
            found={data.env_example_present}
          />
          <Row
            label="Start commands detected"
            found={data.likely_start_commands.length > 0}
          />
          <Row
            label="No missing env vars"
            found={data.missing_env_vars.length === 0}
          />
        </div>
      </div>

      {data.likely_start_commands.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Likely start commands
          </p>
          <CodeList items={data.likely_start_commands} emptyLabel="None detected" />
        </div>
      )}

      {data.required_services.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Required services
          </p>
          <CodeList items={data.required_services} emptyLabel="None detected" />
        </div>
      )}

      {data.missing_env_vars.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Env vars referenced but undocumented
          </p>
          <CodeList items={data.missing_env_vars} emptyLabel="" />
        </div>
      )}

      <RiskList risks={data.risks} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Debug Tab
// ─────────────────────────────────────────────────────────

function DebugTab({ data }: { data: DebugReadiness | null }) {
  if (!data) return <NotAnalyzedCard />;
  if (data.scan_state === "scan_failed") return <ScanFailedCard errors={data.scan_errors} />;
  if (data.scan_state === "not_found") return <NotAnalyzedCard />;

  return (
    <div className="space-y-5">
      <SectionHeader label="Debug Readiness" state={data.scan_state} level={data.level} />

      <div className="divide-y divide-gray-100 rounded border border-gray-200 bg-white px-4 py-2">
        <Row
          label="Structured logging"
          found={data.logging.scan_state === "found"}
          detail={data.logging.framework ?? undefined}
        />
        <Row
          label="Error handling / exception middleware"
          found={data.error_handling.scan_state === "found"}
          detail={data.error_handling.framework ?? undefined}
        />
        <Row
          label="Health check endpoint"
          found={data.health_checks.scan_state === "found"}
          detail={data.health_checks.routes_found?.join(", ") ?? undefined}
        />
        <Row
          label="Error tracking (Sentry / OpenTelemetry)"
          found={data.tracing.scan_state === "found"}
          detail={[
            data.tracing.sentry_found ? "Sentry" : null,
            data.tracing.otel_found   ? "OTel"   : null,
          ].filter(Boolean).join(", ") || undefined}
        />
        <Row
          label="Test harness"
          found={data.test_harness.scan_state === "found"}
          detail={data.test_harness.frameworks?.join(", ") ?? undefined}
        />
        {data.logging.print_only_detected && (
          <Row
            label="print() used for logging (weak signal)"
            found={false}
          />
        )}
      </div>

      <RiskList risks={data.risks} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Change Tab
// ─────────────────────────────────────────────────────────

function ChangeTab({ data }: { data: ChangeRisk | null }) {
  if (!data) return <NotAnalyzedCard />;
  if (data.scan_state === "scan_failed") return <ScanFailedCard errors={data.scan_errors} />;
  if (data.scan_state === "not_found") return <NotAnalyzedCard />;

  return (
    <div className="space-y-5">
      <SectionHeader label="Change Risk" state={data.scan_state} level={data.level} />

      {/* CI and test gates */}
      <div className="divide-y divide-gray-100 rounded border border-gray-200 bg-white px-4 py-2">
        <Row
          label="CI pipeline"
          found={data.ci.scan_state === "found"}
          detail={data.ci.platforms.join(", ") || undefined}
        />
        <Row
          label="Test gate in CI"
          found={data.ci.has_test_gate}
        />
        <Row
          label="Test framework"
          found={data.test_gates.scan_state === "found"}
          detail={data.test_gates.frameworks?.join(", ") ?? undefined}
        />
        <Row
          label="Migrations present"
          found={data.migration_risk.scan_state === "found"}
        />
        {data.migration_risk.scan_state === "found" && (
          <Row
            label="Migration tests present"
            found={data.migration_risk.has_migration_tests}
          />
        )}
      </div>

      {/* Blast radius hotspots */}
      {data.blast_radius_hotspots.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Blast radius hotspots
          </p>
          <div className="space-y-2">
            {data.blast_radius_hotspots.map((h, i) => (
              <div
                key={i}
                className="rounded border border-gray-200 bg-white px-3 py-2"
              >
                <p className="font-mono text-xs text-gray-700 mb-0.5">{h.path}</p>
                <p className="text-xs text-gray-500">{h.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <RiskList risks={data.risks} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Tier disclosure — always rendered at the bottom
// ─────────────────────────────────────────────────────────

function TierDisclosure({ disclosure, tier }: { disclosure: string; tier: string }) {
  return (
    <div className="rounded border border-blue-100 bg-blue-50 px-4 py-3 mt-6">
      <p className="text-xs text-blue-700">
        <span className="font-medium">Analysis type: </span>
        {tier} — {disclosure}
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main export
// ─────────────────────────────────────────────────────────

const TAB_LABELS = ["Setup", "Debug", "Change"] as const;
type TabLabel = (typeof TAB_LABELS)[number];

export default function AnalysisTabs({ result }: { result: AnalysisResult }) {
  const [active, setActive] = useState<TabLabel>("Setup");

  return (
    <div>
      {/* Tab bar */}
      <div className="flex border-b border-gray-200 mb-4">
        {TAB_LABELS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={[
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              active === tab
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:text-gray-700",
            ].join(" ")}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-48">
        {active === "Setup"  && <SetupTab  data={result.setup_risk} />}
        {active === "Debug"  && <DebugTab  data={result.debug_readiness} />}
        {active === "Change" && <ChangeTab data={result.change_risk} />}
      </div>

      {/* Always-present claim disclosure */}
      <TierDisclosure
        disclosure={result.tier_disclosure}
        tier={result.analysis_tier}
      />
    </div>
  );
}
