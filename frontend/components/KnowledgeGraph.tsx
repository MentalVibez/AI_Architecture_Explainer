"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

// react-force-graph-2d uses canvas — must be client-only
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-64 text-[#6d7f9f] font-mono text-xs">
      Loading graph…
    </div>
  ),
});

// ----- Types mirroring backend FileOut / EdgeOut -----

interface FileNode {
  path: string;
  language: string;
  role: string;
  is_entrypoint: boolean;
  is_on_critical_path: boolean;
  loc: number;
  complexity_score: number;
  caller_count: number;
  sensitive_operations: string[];
  confidence: number;
  was_truncated: boolean;
}

interface DepEdge {
  source_path: string;
  target_path: string | null;
  raw_import: string;
  kind: string;
  confidence: string;
  unresolved_reason: string | null;
}

// ForceGraph node/link shapes
interface GraphNode extends FileNode {
  id: string;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  confidence: string;
}

// ----- Colour map -----

const ROLE_COLORS: Record<string, string> = {
  entrypoint: "#4d7cff",
  service: "#35c58b",
  test: "#f0a500",
  config: "#f5e642",
  module: "#8a8a9a",
  utility: "#8a8a9a",
  unknown: "#555570",
};

function roleColor(role: string): string {
  return ROLE_COLORS[role] ?? ROLE_COLORS.unknown;
}

function edgeColor(confidence: string): string {
  if (confidence === "confirmed") return "rgba(100,140,220,0.7)";
  if (confidence === "inferred") return "rgba(100,140,220,0.35)";
  return "rgba(100,140,220,0.15)";
}

// ----- Component -----

interface Props {
  resultId: number;
}

type RoleFilter = "all" | string;

export default function KnowledgeGraph({ resultId }: Props) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ w: 800, h: 520 });

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDimensions({ w: el.clientWidth, h: Math.max(400, el.clientHeight) });
    });
    ro.observe(el);
    setDimensions({ w: el.clientWidth, h: el.clientHeight || 520 });
    return () => ro.disconnect();
  }, []);

  // Fetch graph data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const baseUrl =
      typeof window !== "undefined"
        ? ""
        : process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    Promise.all([
      fetch(`${baseUrl}/api/results/${resultId}/files?limit=1000`).then((r) => r.json()),
      fetch(`${baseUrl}/api/results/${resultId}/edges?limit=5000`).then((r) => r.json()),
    ])
      .then(([files, edges]: [FileNode[], DepEdge[]]) => {
        if (cancelled) return;
        const nodeMap = new Set(files.map((f) => f.path));
        setNodes(files.map((f) => ({ ...f, id: f.path })));
        setLinks(
          edges
            .filter((e) => e.target_path && nodeMap.has(e.target_path))
            .map((e) => ({
              source: e.source_path,
              target: e.target_path as string,
              confidence: e.confidence,
            }))
        );
        setLoading(false);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e));
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [resultId]);

  const handleNodeClick = useCallback((node: object) => {
    setSelected(node as GraphNode);
  }, []);

  const roles = ["all", ...Array.from(new Set(nodes.map((n) => n.role))).sort()];

  const visibleNodeSet = new Set(
    nodes
      .filter((n) => {
        if (roleFilter !== "all" && n.role !== roleFilter) return false;
        if (search && !n.path.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      })
      .map((n) => n.id)
  );

  const graphData = {
    nodes: nodes.filter((n) => visibleNodeSet.has(n.id)),
    links: links.filter(
      (l) => visibleNodeSet.has(l.source as string) && visibleNodeSet.has(l.target as string)
    ),
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-[#6d7f9f] font-mono text-xs">
        Loading knowledge graph…
      </div>
    );
  }

  if (error) {
    return (
      <div className="font-mono text-xs text-[#c84b4b] p-4">
        Failed to load graph: {error}
      </div>
    );
  }

  return (
    <div className="flex gap-4 h-[600px]">
      {/* Graph canvas */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        {/* Controls */}
        <div className="flex flex-wrap gap-2 items-center">
          <input
            type="text"
            placeholder="Filter by path…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#0e1117] border border-white/10 rounded-lg px-3 py-1.5 font-mono text-xs text-[#c2d3f2] placeholder-[#4a5568] focus:outline-none focus:border-[#4d7cff]/50 w-48"
          />
          <div className="flex gap-1 flex-wrap">
            {roles.map((role) => (
              <button
                key={role}
                onClick={() => setRoleFilter(role)}
                className="px-2 py-1 rounded font-mono text-[10px] border transition-colors"
                style={{
                  borderColor: roleFilter === role ? (roleColor(role) === "#8a8a9a" ? "#8a8a9a" : roleColor(role)) : "rgba(255,255,255,0.1)",
                  color: roleFilter === role ? roleColor(role) : "#6d7f9f",
                  backgroundColor: roleFilter === role ? `${roleColor(role)}18` : "transparent",
                }}
              >
                {role}
              </button>
            ))}
          </div>
          <span className="font-mono text-[10px] text-[#4a5568] ml-auto">
            {graphData.nodes.length} nodes · {graphData.links.length} edges
          </span>
        </div>

        {/* Force graph */}
        <div
          ref={containerRef}
          className="flex-1 rounded-xl overflow-hidden bg-[#080b12] border border-white/5"
        >
          <ForceGraph2D
            width={dimensions.w}
            height={dimensions.h}
            graphData={graphData}
            nodeId="id"
            nodeLabel="path"
            nodeColor={(n) => roleColor((n as GraphNode).role)}
            nodeRelSize={4}
            nodeVal={(n) => {
              const node = n as GraphNode;
              return Math.max(1, Math.min(4, node.complexity_score));
            }}
            linkColor={(l) => edgeColor((l as GraphLink).confidence)}
            linkWidth={0.8}
            backgroundColor="#080b12"
            onNodeClick={handleNodeClick}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            cooldownTicks={100}
          />
        </div>

        {/* Legend */}
        <div className="flex gap-4 flex-wrap">
          {Object.entries(ROLE_COLORS)
            .filter(([k]) => k !== "unknown")
            .map(([role, color]) => (
              <div key={role} className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="font-mono text-[10px] text-[#6d7f9f]">{role}</span>
              </div>
            ))}
        </div>
      </div>

      {/* Side panel — node details */}
      <div className="w-64 shrink-0 panel rounded-[20px] p-4 overflow-auto">
        {selected ? (
          <div className="space-y-3">
            <div>
              <p className="font-mono text-[10px] text-[#6d7f9f] uppercase tracking-wider mb-1">
                File
              </p>
              <p className="font-mono text-xs text-[#c2d3f2] break-all leading-relaxed">
                {selected.path}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              <Detail label="role" value={selected.role} />
              <Detail label="language" value={selected.language} />
              <Detail label="LOC" value={String(selected.loc)} />
              <Detail label="complexity" value={selected.complexity_score.toFixed(1)} />
              <Detail label="callers" value={String(selected.caller_count)} />
              <Detail
                label="confidence"
                value={(selected.confidence * 100).toFixed(0) + "%"}
              />
            </div>
            {selected.is_entrypoint && (
              <Badge color="#4d7cff">entrypoint</Badge>
            )}
            {selected.is_on_critical_path && (
              <Badge color="#35c58b">critical path</Badge>
            )}
            {selected.sensitive_operations.length > 0 && (
              <div>
                <p className="font-mono text-[10px] text-[#6d7f9f] uppercase tracking-wider mb-1">
                  Sensitive ops
                </p>
                <div className="flex flex-wrap gap-1">
                  {selected.sensitive_operations.map((op) => (
                    <span
                      key={op}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#3d1a1a] text-[#c84b4b] border border-[#c84b4b]/20"
                    >
                      {op}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="font-mono text-xs text-[#4a5568] mt-2">
            Click a node to see file details.
          </p>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[9px] text-[#4a5568] uppercase tracking-wider">{label}</p>
      <p className="font-mono text-xs text-[#c2d3f2]">{value}</p>
    </div>
  );
}

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="inline-block px-2 py-0.5 rounded-full font-mono text-[10px] border"
      style={{ color, borderColor: `${color}40`, backgroundColor: `${color}12` }}
    >
      {children}
    </span>
  );
}
