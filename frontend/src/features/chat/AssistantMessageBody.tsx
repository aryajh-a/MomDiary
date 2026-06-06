import type { JSX, ReactNode } from "react";
import type { ChatMessageSource } from "./types";

interface Props {
  text: string;
  sources?: ChatMessageSource[];
}

// The research agent always ends its answer with this exact disclaimer
// (see `_RESEARCH_INSTRUCTIONS` in backend/src/momdiary/agents/research_agent.py).
// We detect it so we can render it as a smaller, italic muted note rather
// than as a regular paragraph that competes with the answer body.
const DISCLAIMER_PREFIX = "This is general information, not medical advice";

/**
 * Lightweight renderer for assistant message bodies. Goals:
 *
 * - Show paragraphs as paragraphs (not one wall of `whitespace-pre-wrap`).
 * - Render `**bold**` inline.
 * - Render `- item` / `1. item` blocks as proper lists.
 * - Peel off the medical disclaimer into a styled footer.
 * - Render `sources` (if present) as a tidy chip list with hostnames.
 *
 * We intentionally avoid pulling in `react-markdown` — the research
 * agent's output is constrained to a small subset of formatting, and a
 * 60-line renderer keeps the bundle small.
 */
export function AssistantMessageBody({ text, sources }: Props): JSX.Element {
  const { body, disclaimer } = splitDisclaimer(text);
  const blocks = parseBlocks(body);

  return (
    <div className="flex flex-col gap-2">
      {blocks.map((block, i) =>
        block.kind === "list" ? (
          block.ordered ? (
            <ol
              key={i}
              className="list-decimal space-y-1 pl-5 text-slate-800 text-sm leading-snug"
            >
              {block.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ol>
          ) : (
            <ul
              key={i}
              className="list-disc space-y-1 pl-5 text-slate-800 text-sm leading-snug"
            >
              {block.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ul>
          )
        ) : (
          <p key={i} className="text-slate-800 text-sm leading-snug">
            {renderInline(block.text)}
          </p>
        ),
      )}

      {sources && sources.length > 0 ? <SourcesBlock sources={sources} /> : null}

      {disclaimer ? (
        <p className="border-orange-100 border-t pt-2 text-[11px] text-slate-500 italic leading-snug">
          {disclaimer}
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------

function SourcesBlock({ sources }: { sources: ChatMessageSource[] }): JSX.Element {
  return (
    <div className="mt-1 flex flex-col gap-1">
      <p className="font-medium text-[11px] text-slate-500 uppercase tracking-wide">
        Sources
      </p>
      <ol className="flex flex-col gap-1">
        {sources.map((s, i) => (
          <li key={s.url + i} className="flex items-baseline gap-2 text-xs">
            <span className="shrink-0 text-slate-400">{i + 1}.</span>
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="line-clamp-2 text-orange-700 underline decoration-orange-200 underline-offset-2 hover:decoration-orange-400"
              title={s.url}
            >
              {s.title || hostnameOf(s.url)}
              <span className="ml-1 text-[10px] text-slate-400">
                ({hostnameOf(s.url)})
              </span>
            </a>
          </li>
        ))}
      </ol>
    </div>
  );
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// Block + inline parsers (tiny markdown subset)
// ---------------------------------------------------------------------------

type Block =
  | { kind: "para"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

function splitDisclaimer(text: string): { body: string; disclaimer: string | null } {
  const idx = text.indexOf(DISCLAIMER_PREFIX);
  if (idx === -1) return { body: text, disclaimer: null };
  return {
    body: text.slice(0, idx).trimEnd(),
    disclaimer: text.slice(idx).trim(),
  };
}

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  // Split on blank lines so the model's paragraph breaks become real
  // paragraphs in the DOM.
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  for (const para of paragraphs) {
    const lines = para.split(/\n/);
    const unordered = lines.every((l) => /^\s*-\s+/.test(l));
    const ordered = lines.every((l) => /^\s*\d+\.\s+/.test(l));

    if (unordered && lines.length > 0) {
      blocks.push({
        kind: "list",
        ordered: false,
        items: lines.map((l) => l.replace(/^\s*-\s+/, "")),
      });
    } else if (ordered && lines.length > 0) {
      blocks.push({
        kind: "list",
        ordered: true,
        items: lines.map((l) => l.replace(/^\s*\d+\.\s+/, "")),
      });
    } else {
      // Collapse soft single line-breaks inside a paragraph into spaces.
      blocks.push({ kind: "para", text: lines.join(" ") });
    }
  }
  return blocks;
}

// Render `**bold**` spans inline; everything else is plain text.
function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      out.push(text.slice(lastIndex, match.index));
    }
    out.push(
      <strong key={`b-${key++}`} className="font-semibold text-slate-900">
        {match[1]}
      </strong>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    out.push(text.slice(lastIndex));
  }
  return out;
}
