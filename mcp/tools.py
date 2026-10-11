"""MCP STUB. Not a server. Lists the intended MCP tools (spec 7.2) and the CLI
command each one wraps. The real server (Phase 1b) should import birdseye.core
directly and keep params identical to the CLI (parity test in NEXT.md P0-4).

Human-only actions (approve, reject, on_hold, spend override) are deliberately
NOT exposed over MCP.
"""
TOOLS = {
    # mcp tool          : (cli command,                                   status in prototype)
    "add_post":           ("birdseye add --title --pillar --format --hook --source-repo --platforms", "cli done"),
    "list_posts":         ("birdseye list [--status] [--blocked-on human]", "cli done"),
    "get_post":           ("birdseye show <id>", "cli done"),
    "claim_post":         ("birdseye claim <id> --ttl", "cli done"),
    "renew_claim":        ("birdseye renew <id> --token --ttl", "todo"),
    "release_claim":      ("birdseye release <id> --token", "todo"),
    "update_post":        ("birdseye update <id> --token --caption --beats --slides", "cli partial"),
    "attach_artifact":    ("birdseye attach <id> --kind --file --token", "cli done"),
    "request_human_asset":("birdseye attach <id> --kind footage --request <desc>", "cli done (via attach)"),
    "check_post":         ("birdseye check <id>", "todo (core.missing_for exists)"),
    "move_post":          ("birdseye move <id> <stage> --token --note --url", "cli done"),
    "comment_post":       ("birdseye comment <id> --text", "todo"),
    "schedule_post":      ("birdseye schedule <id> --at --publisher", "todo (approve sets schedule)"),
    "build_publish_week": ("birdseye publish [--week] [--dry-run]", "cli stub"),
    "log_cost":           ("birdseye cost <id> --provider --units --usd", "todo (core.log_cost exists)"),
    "estimate_cost":      ("birdseye cost <id> --estimate", "todo"),
    "record_metrics":     ("birdseye metrics <id> --h48 k=v / --d7 k=v", "todo"),
    "get_status":         ("birdseye status [--blocked-on]", "cli done"),
}

if __name__ == "__main__":
    for name, (cli, state) in TOOLS.items():
        print(f"{name:20} {state:28} {cli}")
