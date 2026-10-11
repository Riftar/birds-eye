# Rules for agents working in Birds Eye

- Every change goes through `python -m birdseye ...` (or the future MCP server). Never edit `post.json` or `STATUS.md` by hand.
- Always pass `--as agent:<role>`. Claim before you write: `claim <id>` gives a token; pass `--token` on every write. Claims expire after 30 min; a move releases the claim.
- You cannot approve ideas, approve reviews, reject, or put posts on hold. Those are Riftar's gates.
- You cannot attach human footage (screen/desk recordings). Request it with `attach <id> --kind footage --request "<what to shoot>"`.
- Every voice/render run must log a cost entry (adapters do this for you).
- Prototype: adapters are stubs. See NEXT.md before building real ones.
