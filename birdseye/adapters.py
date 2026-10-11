"""STUB adapters. Nothing here calls a real service.

Each stub writes a placeholder file into the post folder, attaches it as an
artifact, and logs a fake cost entry labelled STUB. Real adapters (ElevenLabs,
Nexabot, HyperFrames, carousel renderer, Buffer/cogsend) replace these later.
"""
import json
from . import core


def _post_dir(post_id):
    return core.find_post_dir(post_id)


def voice(post_id, actor, token, fail_primary=False):
    """ElevenLabs primary, Nexabot fallback. fail_primary simulates an ElevenLabs failure."""
    post = core.load(post_id)
    provider = "nexabot" if fail_primary else "elevenlabs"
    d = _post_dir(post_id) / "voice"; d.mkdir(exist_ok=True)
    f = d / f"{provider}-stub.txt"
    f.write_text(f"STUB voiceover by {provider}\nscript beats: {post['script']['beats']}\n")
    core.attach(post_id, actor, "voice", str(f.relative_to(core.root())), token=token)
    core.log_cost(post_id, actor, provider, "voice", units=len(" ".join(post['script']['beats'])),
                  usd=0.0, token=token, note="STUB: no real TTS call")
    return provider, f


def render(post_id, actor, token):
    """HyperFrames HTML->MP4 stub."""
    d = _post_dir(post_id) / "out"; d.mkdir(exist_ok=True)
    f = d / "render-stub.mp4.txt"
    f.write_text("STUB: HyperFrames render would land here as out/render.mp4\n")
    core.attach(post_id, actor, "render", str(f.relative_to(core.root())), token=token)
    core.log_cost(post_id, actor, "hyperframes", "render", units=1, usd=0.0, token=token,
                  note="STUB: no real render")
    return f


def carousel(post_id, actor, token):
    """Slides -> PNG stub. Writes one placeholder per slide."""
    post = core.load(post_id)
    d = _post_dir(post_id) / "out" / "slides"; d.mkdir(parents=True, exist_ok=True)
    files = []
    for s in post["slides"]:
        f = d / f"slide-{s['n']:02d}.png.txt"
        f.write_text(f"STUB slide {s['n']}: {s['heading']}\n")
        core.attach(post_id, actor, "slide", str(f.relative_to(core.root())), token=token)
        files.append(f)
    core.log_cost(post_id, actor, "carousel-renderer", "render", units=len(files), usd=0.0,
                  token=token, note="STUB: internal renderer, placeholders only")
    return files


def publish_week(actor="agent:publish"):
    """Manual publisher: write publish/<year>-w<N>.json from posts at `scheduled`."""
    by_week = {}
    for p in core.all_posts():
        if p["status"] != "scheduled" or not p["schedule_at"]:
            continue
        y, w, _ = core.parse(p["schedule_at"]).isocalendar()
        by_week.setdefault(f"{y}-w{w:02d}", []).append({
            "id": p["id"], "at": p["schedule_at"], "publisher": p["publisher"],
            "platforms": p["platforms"], "caption": p["caption"], "hashtags": p["hashtags"],
            "checklist": ["download media from out/", "post on each platform",
                          f"run: birdseye move {p['id']} posted --url <link>"],
        })
    d = core.root() / "publish"; d.mkdir(exist_ok=True)
    written = []
    for wk, items in by_week.items():
        f = d / f"{wk}.json"
        f.write_text(json.dumps({"generated": "do not hand-edit", "publisher": "manual (STUB)",
                                 "week": wk, "items": sorted(items, key=lambda i: i["at"])}, indent=2) + "\n")
        written.append(f)
    return written
