"""birdseye CLI: python -m birdseye <command> ...  (all commands accept --as and --json)"""
import argparse
import json
import os
import sys
from . import core, status, adapters


def _out(args, obj, text):
    print(json.dumps(obj, indent=2, ensure_ascii=False) if args.json else text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="birdseye")
    ap.add_argument("--as", dest="actor", default=os.environ.get("BIRDSEYE_ACTOR", "agent:unknown"))
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add"); a.add_argument("--title", required=True); a.add_argument("--pillar", required=True)
    a.add_argument("--format", required=True); a.add_argument("--hook", default="")
    a.add_argument("--source-repo", required=True); a.add_argument("--platforms", default="tiktok,instagram")
    l = sub.add_parser("list"); l.add_argument("--status"); l.add_argument("--blocked-on")
    s = sub.add_parser("show"); s.add_argument("id")
    c = sub.add_parser("claim"); c.add_argument("id"); c.add_argument("--ttl", type=int, default=30)
    m = sub.add_parser("move"); m.add_argument("id"); m.add_argument("stage")
    m.add_argument("--token"); m.add_argument("--note"); m.add_argument("--url")
    u = sub.add_parser("update"); u.add_argument("id"); u.add_argument("--token"); u.add_argument("--caption")
    u.add_argument("--beats", help="comma separated"); u.add_argument("--slides", help="pipe separated headings")
    at = sub.add_parser("attach"); at.add_argument("id"); at.add_argument("--kind", required=True)
    at.add_argument("--file"); at.add_argument("--token"); at.add_argument("--request", help="ask human for this")
    ap_ = sub.add_parser("approve"); ap_.add_argument("id"); ap_.add_argument("--comment"); ap_.add_argument("--at")
    rj = sub.add_parser("reject"); rj.add_argument("id"); rj.add_argument("--comment"); rj.add_argument("--return-to")
    r = sub.add_parser("run", help="STUB adapters"); r.add_argument("adapter", choices=["voice", "render", "carousel"])
    r.add_argument("id"); r.add_argument("--token"); r.add_argument("--fail-primary", action="store_true")
    sub.add_parser("publish", help="manual publisher: write publish/<year>-w<N>.json")
    sub.add_parser("status")
    sv = sub.add_parser("serve"); sv.add_argument("--port", type=int, default=8787)
    sub.add_parser("init-human", help="create .birdseye/human.key on this machine")

    args = ap.parse_args(argv)
    who = args.actor
    try:
        if args.cmd == "add":
            p = core.add(who, args.title, args.pillar, args.format, args.hook, args.source_repo,
                         args.platforms.split(","))
            _out(args, p, f"added {p['id']} (idea)")
        elif args.cmd == "list":
            posts = core.all_posts()
            if args.blocked_on == "human":
                w = core.waiting_on_human(posts)
                return _out(args, w, "\n".join(f"{x['id']:40} {x['what']}" for x in w) or "nothing waiting")
            if args.status:
                posts = [p for p in posts if p["status"] == args.status]
            _out(args, posts, "\n".join(f"{p['id']:40} {p['format']:9} {p['status']:10} {p['owner']}" for p in posts))
        elif args.cmd == "show":
            print(json.dumps(core.load(args.id), indent=2, ensure_ascii=False))
        elif args.cmd == "claim":
            c = core.claim(args.id, who, args.ttl)
            _out(args, c, f"claimed {args.id} until {c['until']} token={c['token']}")
        elif args.cmd == "move":
            p = core.move(args.id, who, args.stage, args.token, args.note, args.url)
            _out(args, p, f"{args.id} -> {p['status']}")
        elif args.cmd == "update":
            p = core.update(args.id, who, args.token, caption=args.caption,
                            beats=args.beats.split(",") if args.beats else None,
                            slides=args.slides.split("|") if args.slides else None)
            _out(args, p, f"updated {args.id}")
        elif args.cmd == "attach":
            p = core.attach(args.id, who, args.kind, args.file, token=args.token, request=args.request)
            _out(args, p["artifacts"][-1], f"{'requested' if args.request else 'attached'} {args.kind} on {args.id}")
        elif args.cmd == "approve":
            p = core.approve(args.id, who, args.comment, args.at)
            _out(args, p, f"approved {args.id} -> {p['status']}")
        elif args.cmd == "reject":
            p = core.reject(args.id, who, args.comment, args.return_to)
            _out(args, p, f"rejected {args.id} -> {p['status']}")
        elif args.cmd == "run":
            if args.adapter == "voice":
                prov, f = adapters.voice(args.id, who, args.token, args.fail_primary)
                print(f"[STUB] voice via {prov} -> {f.name}")
            elif args.adapter == "render":
                print(f"[STUB] hyperframes render -> {adapters.render(args.id, who, args.token).name}")
            else:
                print(f"[STUB] carousel -> {len(adapters.carousel(args.id, who, args.token))} slide placeholders")
        elif args.cmd == "publish":
            for f in adapters.publish_week(who):
                print(f"[STUB manual publisher] wrote {f.relative_to(core.root())}")
        elif args.cmd == "init-human":
            print(f"human key at {core.ensure_human_key()}")
        elif args.cmd == "serve":
            status.write(); from .server import serve; serve(args.port)
        if args.cmd not in ("status", "serve", "show", "list"):
            status.write()
        if args.cmd == "status":
            print(status.render() if not args.json else json.dumps(core.waiting_on_human()))
            status.write()
        return 0
    except core.BirdsEyeError as e:
        print(f"REFUSED {e.code}: {e.message}", file=sys.stderr)
        return 2
