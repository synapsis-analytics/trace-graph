/**
 * Ask — natural-language question over the graph (POST /api/ask).
 * The model is optional in TRACE: if no key is configured the API answers 503 and we say so
 * plainly, pointing at the parts of the tool that work without any model at all.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { MessagesSquare, Sparkles, Terminal } from "lucide-react";
import { TypeIcon } from "@/components/TypeBits";
import { Badge, Button, Card, Textarea, Spinner } from "@/components/ui/primitives";
import { api, HttpError } from "@/lib/api";
import type { AskResponse } from "@/lib/types";

const EXAMPLES = [
  "Which partners appear in more than three results under Market Intelligence?",
  "What evidence supports the varietal turnover outputs in Kenya?",
  "Which high-level outputs have budget but no reported results?",
  "Show the chain from the groundnut product profile result up to the programme.",
];

export default function Ask() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const ask = useMutation({
    mutationFn: (q: string) => api.ask(q),
    onSuccess: (data) => {
      setAnswer(data);
      setNotice(null);
    },
    onError: (e) => {
      setAnswer(null);
      if (e instanceof HttpError && e.status === 503) {
        setNotice(e.detail || "Ask is switched off on this environment because no model key is configured.");
      } else {
        setNotice((e as Error).message);
      }
    },
  });

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mx-auto max-w-3xl space-y-4">
        <header className="space-y-1">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
            <MessagesSquare className="h-5 w-5 text-brand" /> Ask the graph
          </h1>
          <p className="text-sm text-muted">
            A question in plain English. The model may only answer using the same API calls a person can make, and every
            object it leans on is cited below the answer so you can open it yourself.
          </p>
        </header>

        <Card className="space-y-3">
          <Textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Which institutions partner on more than three results in Kenya?"
            aria-label="Your question"
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && question.trim()) ask.mutate(question.trim());
            }}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" disabled={!question.trim() || ask.isPending} onClick={() => ask.mutate(question.trim())}>
              {ask.isPending ? <Spinner className="border-white/40 border-t-white" /> : <Sparkles className="h-4 w-4" />} Ask
            </Button>
            <span className="text-[11px] text-muted">⌘/Ctrl + Enter</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {EXAMPLES.map((e) => (
              <button key={e} type="button" onClick={() => setQuestion(e)} className="chip bg-bg text-muted hover:border-brand hover:text-ink">
                {e}
              </button>
            ))}
          </div>
        </Card>

        {notice ? (
          <Card className="border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10">
            <p className="text-sm font-medium text-amber-900 dark:text-amber-200">Ask is unavailable right now</p>
            <p className="mt-1 text-xs text-amber-900/90 dark:text-amber-200/90">{notice}</p>
            <p className="mt-2 text-xs text-amber-900/90 dark:text-amber-200/90">
              Everything else works without a model key: browse the{" "}
              <Link className="underline" to="/">
                graph
              </Link>
              , trace a{" "}
              <Link className="underline" to="/path">
                path
              </Link>
              , or query the{" "}
              <Link className="underline" to="/api-guide">
                API and MCP server
              </Link>{" "}
              directly.
            </p>
          </Card>
        ) : null}

        {answer ? (
          <Card className="space-y-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{answer.answer}</p>

            {answer.objects_cited && answer.objects_cited.length > 0 ? (
              <section>
                <h2 className="label mb-1">Objects cited</h2>
                <div className="flex flex-wrap gap-1">
                  {answer.objects_cited.map((o) => (
                    <Link key={o.id} to={`/?focus=${encodeURIComponent(o.id)}&depth=1`} className="chip bg-bg text-ink hover:border-brand">
                      <TypeIcon type={o.type} />
                      {o.label ?? o.id}
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}

            {answer.tool_calls && answer.tool_calls.length > 0 ? (
              <section>
                <h2 className="label mb-1 flex items-center gap-1">
                  <Terminal className="h-3 w-3" /> How it got there
                </h2>
                <ul className="space-y-1">
                  {answer.tool_calls.map((t, i) => (
                    <li key={`${t.name}-${i}`} className="flex items-start gap-2 text-xs">
                      <Badge className="bg-bg text-muted">{t.name}</Badge>
                      <code className="min-w-0 flex-1 break-all font-mono text-[11px] text-muted">{JSON.stringify(t.args ?? {})}</code>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </Card>
        ) : null}
      </div>
    </div>
  );
}
