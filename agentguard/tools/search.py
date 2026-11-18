import re

from agentguard.tools.base import Tool, ToolResult
from agentguard.tools.env import Environment

_STOP = set(
    "the a an is are do does i to of how what when and for my our long have can in on".split()
)


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w.removesuffix("s") for w in words if w not in _STOP}


def make_search(env: Environment) -> Tool:
    def run(args: dict) -> ToolResult:
        terms = _terms(str(args.get("query", "")))
        scored = []
        for slug, doc in env.docs.items():
            words = _terms(doc["title"] + " " + doc["body"])
            if overlap := len(terms & words):
                scored.append((overlap, slug))
        hits = [s for _, s in sorted(scored, key=lambda x: (-x[0], x[1]))[:3]]
        if not hits:
            return ToolResult("No documents found.", trusted=False)
        text = "\n".join(f"[{s}] {env.docs[s]['title']}: {env.docs[s]['body']}" for s in hits)
        return ToolResult(text, trusted=False)

    return Tool("search", "search(query): find documents in the company knowledge base", run)
