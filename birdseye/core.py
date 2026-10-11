"""Core: post store, state machine, gates, claims, history.

Every write goes through this module. CLI, dashboard and (future) MCP server
are thin wrappers. Prototype quality: stdlib only, no schema validation yet.
"""
import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

WIB = timezone(timedelta(hours=7), "WIB")

STAGES = ["idea", "approved", "scripted", "assets", "voiced", "edited",
          "review", "scheduled", "posted", "measured"]
SIDE = ["rejected", "on_hold"]
FORMATS = ["short", "carousel"]
PILLARS = ["build-in-public", "failures-lessons", "how-i-automate", "tool-breakdowns"]
HUMAN = "human"
DEFAULT_TTL_MIN = 30
MAX_TTL_MIN = 240


class BirdsEyeError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------- paths / time ----------

def root():
    return Path(os.environ.get("BIRDSEYE_ROOT", os.getcwd())).resolve()


def now():
    return datetime.now(WIB).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(WIB).isoformat()


def parse(ts):
    return datetime.fromisoformat(ts)


def posts_dir():
    return root() / "posts"


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40].strip("-") or "post"


# ---------- human key (R2) ----------

def human_key_path():
    return root() / ".birdseye" / "human.key"


def ensure_human_key():
    p = human_key_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(16))
    return p


def require_human(actor):
    """Prototype gate: actor must be 'human' AND the local key file must exist.
    Real build: check a signed token from the key; agents never see the key."""
    if actor != HUMAN:
        raise BirdsEyeError("HUMAN_ONLY", f"only the human can do this (actor was {actor!r})")
    if not human_key_path().exists():
        raise BirdsEyeError("HUMAN_ONLY", "no .birdseye/human.key on this machine")


# ---------- store ----------

def find_post_dir(post_id):
    for p in posts_dir().glob(f"*/{post_id}/post.json"):
        return p.parent
    raise BirdsEyeError("NOT_FOUND", f"no post {post_id!r}")


def load(post_id):
    return json.loads((find_post_dir(post_id) / "post.json").read_text())


def all_posts():
    out = []
    for p in sorted(posts_dir().glob("*/*/post.json")):
        out.append(json.loads(p.read_text()))
    return out


def _write(post):
    d = posts_dir() / post["id"][:7] / post["id"]
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "post.json.tmp"
    tmp.write_text(json.dumps(post, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, d / "post.json")  # atomic


@contextmanager
def locked(post_id):
    lock = root() / ".birdseye" / "locks" / f"{post_id}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(50):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise BirdsEyeError("LOCKED", f"{post_id} is locked by another writer")
    try:
        yield
    finally:
        os.close(fd)
        os.unlink(lock)


def log_activity(actor, command, post_id, result, code=None, message=None):
    d = root() / "logs" / "activity"
    d.mkdir(parents=True, exist_ok=True)
    line = {"at": iso(now()), "actor": actor, "command": command,
            "post": post_id, "result": result, "error": code}
    if message:
        line["message"] = message
    with open(d / f"{now().date()}.jsonl", "a") as f:
        f.write(json.dumps(line) + "\n")


def _history(post, actor, action, frm, to, note=None):
    post["history"].append({"at": iso(now()), "actor": actor, "action": action,
                            "from": frm, "to": to, "note": note})


def mutate(post_id, actor, command, fn):
    """Load under lock, apply fn(post), write. Refused calls write nothing."""
    try:
        with locked(post_id):
            post = load(post_id)
            fn(post)
            _write(post)
        log_activity(actor, command, post_id, "ok")
        return post
    except BirdsEyeError as e:
        log_activity(actor, command, post_id, "refused", e.code, e.message)
        raise


# ---------- create ----------

def add(actor, title, pillar, fmt, hook, source_repo, platforms=None, example=False, post_id=None):
    if fmt not in FORMATS:
        raise BirdsEyeError("SCHEMA_INVALID", f"format must be one of {FORMATS}")
    if pillar not in PILLARS:
        raise BirdsEyeError("SCHEMA_INVALID", f"pillar must be one of {PILLARS}")
    if not (title and source_repo):
        raise BirdsEyeError("SCHEMA_INVALID", "title and source_repo are required")
    pid = post_id or f"{now().date()}-{slugify(title)}"
    if list(posts_dir().glob(f"*/{pid}/post.json")):
        raise BirdsEyeError("SCHEMA_INVALID", f"post {pid} already exists")
    post = {
        "schema_version": 1, "id": pid, "example": example,
        "pillar": pillar, "format": fmt, "platforms": platforms or ["tiktok", "instagram"],
        "title": title, "hook": hook or "", "source_repo": source_repo,
        "artifacts": [], "script": None, "slides": [], "caption": "", "hashtags": [],
        "voice": {"provider": "elevenlabs", "voice_id": "TBD", "model": "TBD",
                  "fallback": {"provider": "nexabot", "voice_id": "Achernar"}} if fmt == "short" else None,
        "status": "idea", "owner": actor, "claim": None,
        "approved_by": None, "approved_at": None, "review": None,
        "history": [], "schedule_at": None, "publisher": "manual",
        "publisher_post_id": None, "post_url": None,
        "metrics": {"h48": None, "d7": None}, "notes": "", "cost": [],
    }
    _history(post, actor, "add", None, "idea")
    _write(post)
    log_activity(actor, "add", pid, "ok")
    return post


# ---------- claims ----------

def _claim_active(post):
    c = post.get("claim")
    return c if c and parse(c["until"]) > now() else None


def claim(post_id, actor, ttl_min=DEFAULT_TTL_MIN):
    ttl_min = max(1, min(int(ttl_min), MAX_TTL_MIN))

    def fn(post):
        c = _claim_active(post)
        if c and c["by"] != actor:
            raise BirdsEyeError("ALREADY_CLAIMED", f"held by {c['by']} until {c['until']}")
        post["claim"] = {"by": actor, "until": iso(now() + timedelta(minutes=ttl_min)),
                         "token": "c-" + secrets.token_hex(3)}
        post["owner"] = actor
        _history(post, actor, "claim", post["status"], post["status"], f"ttl {ttl_min}m")
    return mutate(post_id, actor, "claim", fn)["claim"]


def _check_claim(post, actor, token):
    """R5: agents must hold a live claim and pass its token. Human may write freely."""
    if actor == HUMAN:
        return
    c = _claim_active(post)
    if not c or c["by"] != actor or c["token"] != token:
        raise BirdsEyeError("CLAIM_LOST", f"{actor} does not hold a live claim with that token")


# ---------- state machine ----------

def next_stage(post):
    i = STAGES.index(post["status"])
    if i + 1 >= len(STAGES):
        return None
    nxt = STAGES[i + 1]
    if nxt == "voiced" and post["format"] == "carousel":
        nxt = "edited"   # carousels skip voiced
    return nxt


def allowed_targets(post):
    """Return the stages a post may move to (ignoring who is asking)."""
    st = post["status"]
    if st in SIDE:
        return []
    out = []
    nxt = next_stage(post)
    if nxt:
        out.append(nxt)
    out += [s for s in STAGES[:STAGES.index(st)]
            if not (s == "voiced" and post["format"] == "carousel")]  # backward with reason
    return out


def missing_for(post, target):
    """Requirements to enter `target`. Prototype subset of spec section 4."""
    miss = []
    arts = post["artifacts"]
    has = lambda kind: any(a["kind"] == kind and a.get("path_or_url") for a in arts)
    if target == "scripted":
        if post["format"] == "short" and not (post.get("script") and post["script"].get("beats")):
            miss.append("script.beats")
        if post["format"] == "carousel" and not (3 <= len(post["slides"]) <= 10):
            miss.append("slides (3-10)")
        if not post["caption"]:
            miss.append("caption")
    elif target == "assets":
        for a in arts:
            if a.get("required") and not a.get("path_or_url"):
                who = "human" if a.get("provided_by") == HUMAN else "agent"
                miss.append(f"{a['kind']} ({who}): {a.get('request') or a['id']}")
    elif target == "voiced":
        if not has("voice"):
            miss.append("voice artifact")
    elif target in ("edited", "review"):
        if post["format"] == "short" and not has("render"):
            miss.append("render artifact (mp4)")
        if post["format"] == "carousel" and sum(1 for a in arts if a["kind"] == "slide") < len(post["slides"]):
            miss.append("one slide png per slide")
    elif target == "posted":
        if not (post.get("post_url") or post.get("publisher_post_id")):
            miss.append("post_url or publisher_post_id")
    elif target == "measured":
        if not (post["metrics"].get("h48") and post["metrics"].get("d7")):
            miss.append("metrics.h48 and metrics.d7")
    return miss


def move(post_id, actor, to, token=None, note=None, url=None):
    def fn(post):
        frm = post["status"]
        if to in ("approved", "rejected", "on_hold") or (frm == "review" and to == "scheduled"):
            raise BirdsEyeError("HUMAN_ONLY", f"{frm} -> {to} is a human gate; use `approve`/`reject`")
        _check_claim(post, actor, token)
        if to not in allowed_targets(post):
            raise BirdsEyeError("INVALID_TRANSITION",
                                f"{frm} -> {to} not allowed (allowed: {allowed_targets(post)})")
        backward = STAGES.index(to) < STAGES.index(frm)
        if backward and not note:
            raise BirdsEyeError("INVALID_TRANSITION", "moving backward needs --note with a reason")
        if url and to == "posted":
            post["post_url"] = url
        if not backward:
            miss = missing_for(post, to)
            if miss:
                raise BirdsEyeError("MISSING_ASSETS", "; ".join(miss))
        post["status"] = to
        post["claim"] = None  # release on move
        _history(post, actor, "move", frm, to, note)
    return mutate(post_id, actor, "move", fn)


def _human_or_log(actor, command, post_id):
    try:
        require_human(actor)
    except BirdsEyeError as e:
        log_activity(actor, command, post_id, "refused", e.code, e.message)
        raise


def approve(post_id, actor, comment=None, schedule_at=None, publisher="manual"):
    _human_or_log(actor, "approve", post_id)

    def fn(post):
        st = post["status"]
        if st == "idea":                                  # gate 1
            post["status"] = "approved"
            post["approved_by"], post["approved_at"] = HUMAN, iso(now())
            post["owner"] = "agent:script"
            _history(post, actor, "approve", "idea", "approved", comment)
        elif st == "review":                              # gate 2
            at = schedule_at or iso((now() + timedelta(days=1)).replace(hour=19, minute=0, second=0))
            post["review"] = {"decision": "approved", "by": HUMAN, "at": iso(now()),
                              "comment": comment, "return_to": None}
            post["schedule_at"], post["publisher"] = at, publisher
            post["status"], post["owner"] = "scheduled", "agent:publish"
            _history(post, actor, "approve", "review", "scheduled", comment)
        else:
            raise BirdsEyeError("INVALID_TRANSITION", f"nothing to approve at stage {st!r}")
        post["claim"] = None
    return mutate(post_id, actor, "approve", fn)


def reject(post_id, actor, comment, return_to=None):
    _human_or_log(actor, "reject", post_id)
    if not comment:
        raise BirdsEyeError("SCHEMA_INVALID", "reject needs --comment")

    def fn(post):
        st = post["status"]
        if st == "idea":
            post["status"] = "rejected"
            _history(post, actor, "reject", "idea", "rejected", comment)
        elif st == "review":
            back = return_to or "edited"
            if back not in STAGES[:STAGES.index("review")]:
                raise BirdsEyeError("INVALID_TRANSITION", f"cannot return to {back}")
            post["review"] = {"decision": "rejected", "by": HUMAN, "at": iso(now()),
                              "comment": comment, "return_to": back}
            post["status"] = back
            _history(post, actor, "reject", "review", back, comment)
        else:
            raise BirdsEyeError("INVALID_TRANSITION", f"nothing to reject at stage {st!r}")
        post["claim"] = None
    return mutate(post_id, actor, "reject", fn)


# ---------- content + artifacts ----------

def update(post_id, actor, token=None, caption=None, beats=None, slides=None, hashtags=None):
    def fn(post):
        _check_claim(post, actor, token)
        changed = []
        if caption is not None:
            post["caption"] = caption; changed.append("caption")
        if beats:
            post["script"] = {"path": "script.md", "beats": beats, "est_seconds": 8 * len(beats)}
            changed.append("script")
        if slides:
            post["slides"] = [{"n": i + 1, "heading": h, "body": "", "notes": ""}
                              for i, h in enumerate(slides)]
            changed.append("slides")
        if hashtags:
            post["hashtags"] = hashtags; changed.append("hashtags")
        if post["status"] in ("scheduled",) and changed:   # R6
            frm = post["status"]; post["status"] = "review"
            _history(post, actor, "revert", frm, "review", "content edited after gate 2")
        _history(post, actor, "update", post["status"], post["status"], ", ".join(changed))
    return mutate(post_id, actor, "update", fn)


def attach(post_id, actor, kind, path=None, required=True, token=None, request=None, provided_by=None):
    """Attach an artifact, or (with request=...) ask the human for one (R4)."""
    def fn(post):
        _check_claim(post, actor, token)
        by = provided_by or (HUMAN if actor == HUMAN else "agent")
        if path and kind == "footage" and actor != HUMAN:
            raise BirdsEyeError("HUMAN_ONLY", "footage is human-shot; agents can only request it")
        if path:
            for a in post["artifacts"]:   # fulfil an open request of the same kind
                if a["kind"] == kind and not a.get("path_or_url"):
                    a.update(path_or_url=path, added_at=iso(now()))
                    _history(post, actor, "attach", post["status"], post["status"], f"{kind}: {path} (fulfils request)")
                    return
        art = {"id": f"a{len(post['artifacts']) + 1}", "kind": kind, "path_or_url": path,
               "required": required, "provided_by": HUMAN if request else by,
               "added_by": actor, "added_at": iso(now())}
        if request:
            art["request"] = request
        post["artifacts"].append(art)
        _history(post, actor, "request" if request else "attach", post["status"], post["status"],
                 f"{kind}: {request or path}")
    return mutate(post_id, actor, "attach", fn)


def log_cost(post_id, actor, provider, kind, units, usd, token=None, note="STUB"):
    def fn(post):
        _check_claim(post, actor, token)
        entry = {"at": iso(now()), "provider": provider, "kind": kind, "units": units,
                 "usd": usd, "agent": actor, "run_id": "stub-" + secrets.token_hex(3),
                 "approved_override": None, "note": note}
        post["cost"].append(entry)
        d = root() / "logs" / "cost"; d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{now():%Y-%m}.jsonl", "a") as f:
            f.write(json.dumps({"post": post_id, **entry}) + "\n")
    return mutate(post_id, actor, "cost", fn)


def set_published(post_id, actor, token=None, publisher_post_id=None):
    def fn(post):
        _check_claim(post, actor, token)
        post["publisher_post_id"] = publisher_post_id
    return mutate(post_id, actor, "publish", fn)


# ---------- views ----------

def waiting_on_human(posts=None):
    """Items blocked on Riftar: gate 1, gate 2, human footage requests."""
    out = []
    for p in posts if posts is not None else all_posts():
        if p["status"] == "idea":
            out.append({"id": p["id"], "kind": "gate1", "what": "Approve idea"})
        elif p["status"] == "review":
            out.append({"id": p["id"], "kind": "gate2", "what": "Review finished post"})
        for a in p["artifacts"]:
            if a.get("provided_by") == HUMAN and not a.get("path_or_url") and p["status"] not in SIDE:
                out.append({"id": p["id"], "kind": "footage", "what": f"Shoot: {a.get('request')}"})
    return out


# ---------- detail view helpers ----------

def comment(post_id, actor, text):
    """Note on a post, no state change. Anyone may comment (no claim needed)."""
    text = (text or "").strip()

    def fn(post):
        if not text:
            raise BirdsEyeError("SCHEMA_INVALID", "comment text is required")
        if len(text) > 2000:
            raise BirdsEyeError("SCHEMA_INVALID", "comment too long (max 2000 chars)")
        _history(post, actor, "comment", post["status"], post["status"], text)
    return mutate(post_id, actor, "comment", fn)


def stage_path(post):
    """Stages this post walks through (carousels skip voiced)."""
    return [s for s in STAGES if not (s == "voiced" and post["format"] == "carousel")]


def file_link(post, path):
    """Root-relative path if the artifact file exists on disk, else None.
    Accepts root-relative paths or paths relative to the post folder."""
    if not path:
        return None
    for cand in (root() / path, root() / "posts" / post["id"][:7] / post["id"] / path):
        try:
            if cand.resolve().is_file() and posts_dir().resolve() in cand.resolve().parents:
                return str(cand.resolve().relative_to(root()))
        except OSError:
            pass
    return None


def asset_checklist(post):
    """Everything the post needs, grouped by the stage that requires it.
    Each item: {stage, label, state: done|missing|requested, path, by}."""
    items = []
    fmt, arts = post["format"], post["artifacts"]

    def add(stage, label, ok, path=None, by=None, state=None):
        items.append({"stage": stage, "label": label, "state": state or ("done" if ok else "missing"),
                      "path": path, "file": file_link(post, path), "by": by})

    if fmt == "short":
        add("scripted", "Script beats", bool(post.get("script") and post["script"].get("beats")),
            (post.get("script") or {}).get("path"))
    else:
        add("scripted", f"Slides (3-10), have {len(post['slides'])}", 3 <= len(post["slides"]) <= 10)
    add("scripted", "Caption", bool(post["caption"]))
    for a in arts:
        if a["kind"] in ("voice", "render", "slide"):
            continue
        if a.get("provided_by") == HUMAN and not a.get("path_or_url"):
            add("assets", f"{a['kind'].title()}: {a.get('request')}", False, by=HUMAN, state="requested")
        else:
            add("assets", a["kind"].title() + ("" if a.get("required") else " (optional)"),
                bool(a.get("path_or_url")), a.get("path_or_url"),
                HUMAN if a.get("provided_by") == HUMAN else a.get("added_by"))
    if fmt == "short":
        v = next((a for a in arts if a["kind"] == "voice" and a.get("path_or_url")), None)
        add("voiced", "Voiceover", bool(v), v and v["path_or_url"], v and v["added_by"])
        r = next((a for a in arts if a["kind"] == "render" and a.get("path_or_url")), None)
        add("edited", "Render (mp4)", bool(r), r and r["path_or_url"], r and r["added_by"])
    else:
        slides = [a for a in arts if a["kind"] == "slide" and a.get("path_or_url")]
        for s in post["slides"]:
            a = slides[s["n"] - 1] if s["n"] <= len(slides) else None
            add("edited", f"Slide {s['n']} PNG", bool(a), a and a["path_or_url"], a and a["added_by"])
    add("posted", "Post URL", bool(post.get("post_url") or post.get("publisher_post_id")), post.get("post_url"))
    return items


def refused_attempts(post_id):
    """Refused calls for this post from logs/activity/*.jsonl (oldest first)."""
    out = []
    for f in sorted((root() / "logs" / "activity").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("post") == post_id and e.get("result") == "refused":
                out.append(e)
    return out


def detail(post_id):
    """Everything the card detail view needs, in one call."""
    post = load(post_id)
    gate = "gate1" if post["status"] == "idea" else "gate2" if post["status"] == "review" else None
    return {"post": post, "stages": stage_path(post), "gate": gate,
            "next": next_stage(post), "missing_next": missing_for(post, next_stage(post)) if next_stage(post) else [],
            "checklist": asset_checklist(post), "refused": refused_attempts(post_id),
            "return_to_options": [s for s in stage_path(post) if s in STAGES[2:STAGES.index("review")]],
            "cost_total_usd": round(sum(c.get("usd") or 0 for c in post["cost"]), 4),
            "now": iso(now())}
