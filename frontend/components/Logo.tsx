/**
 * CodebaseAtlas logo mark — 3-node architecture graph
 *
 * Three nodes connected by lines, directly representing the architecture
 * diagrams the product generates. Amber on transparent background.
 *
 * Usage:
 *   <Logo />              // default 20×20
 *   <Logo size={32} />    // larger
 */

export default function Logo({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Edges */}
      <line x1="12" y1="3"  x2="3"  y2="19" stroke="#c8a96e" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="12" y1="3"  x2="21" y2="19" stroke="#c8a96e" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="3"  y1="19" x2="21" y2="19" stroke="#c8a96e" strokeWidth="1.5" strokeLinecap="round" />

      {/* Nodes */}
      <circle cx="12" cy="3"  r="2.2" fill="#c8a96e" />
      <circle cx="3"  cy="19" r="2.2" fill="#c8a96e" />
      <circle cx="21" cy="19" r="2.2" fill="#c8a96e" />
    </svg>
  );
}
