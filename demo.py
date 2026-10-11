#!/usr/bin/env python3
"""Walk one short video and one carousel through the whole Birds Eye flow.

Runs in a throwaway folder (.demo/) so the seeded example posts are untouched.
Every step goes through the real CLI: python -m birdseye ...
"""
import os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE / ".demo"
shutil.rmtree(DEMO, ignore_errors=True); DEMO.mkdir()
ENV = {**os.environ, "BIRDSEYE_ROOT": str(DEMO), "PYTHONPATH": str(HERE)}
n = 0


def be(actor, *args, expect_fail=False, say=None):
    global n
    n += 1
    r = subprocess.run([sys.executable, "-m", "birdseye", "--as", actor, *args],
                       capture_output=True, text=True, env=ENV, cwd=HERE)
    out = (r.stdout + r.stderr).strip()
    ok = (r.returncode != 0) if expect_fail else (r.returncode == 0)
    mark = "BLOCKED" if expect_fail else "ok"
    print(f"{n:02d}. [{actor:14}] {say or ' '.join(args)}")
    print(f"      {mark}: {out.splitlines()[-1] if out else ''}")
    if not ok:
        print("DEMO FAILED: unexpected result"); sys.exit(1)
    return out


def token(out):
    return re.search(r"token=(\S+)", out).group(1)


print("=== Birds Eye demo: a short video and a carousel, idea -> posted ===\n")
be("human", "init-human", say="Riftar sets up the local human key (agents never get it)")

S = "short-demo"; C = "carousel-demo"
be("agent:ideas", "add", "--title", "Short demo: offline clipper", "--pillar", "how-i-automate",
   "--format", "short", "--hook", "I cut 2 hours of video offline in 4 minutes", "--source-repo", "Riftar/video-clipper",
   say="idea agent adds a SHORT idea")
be("agent:ideas", "add", "--title", "Carousel demo: 69 skills", "--pillar", "tool-breakdowns",
   "--format", "carousel", "--hook", "My agent setup has 69 skills", "--source-repo", "Riftar/agent-config",
   say="idea agent adds a CAROUSEL idea")
SID = next(p.name for p in (DEMO / "posts").glob("*/*short-demo*"))
CID = next(p.name for p in (DEMO / "posts").glob("*/*carousel-demo*"))

print("\n--- Gate 1: agents cannot approve ideas ---")
t = token(be("agent:script", "claim", SID, say=f"script agent claims {SID}"))
be("agent:script", "move", SID, "approved", "--token", t, expect_fail=True, say="script agent tries to self-approve")
be("agent:script", "move", SID, "scripted", "--token", t, expect_fail=True, say="script agent tries idea -> scripted (skip)")
be("agent:script", "approve", SID, expect_fail=True, say="script agent calls approve as itself")
be("human", "approve", SID, "--comment", "go", say="Riftar approves the short idea (gate 1)")
be("human", "approve", CID, "--comment", "go", say="Riftar approves the carousel idea (gate 1)")

print("\n--- Short: script -> assets -> voice -> render -> review ---")
t = token(be("agent:script", "claim", SID, say="script agent claims the short"))
be("agent:other", "claim", SID, expect_fail=True, say="a second agent tries to grab it")
be("agent:script", "move", SID, "scripted", "--token", t, expect_fail=True, say="move to scripted before writing a script")
be("agent:script", "update", SID, "--token", t, "--caption", "Offline clipping, 4 minutes.",
   "--beats", "hook,setup,demo,result", say="script agent writes beats + caption")
be("agent:script", "move", SID, "scripted", "--token", t, say="script agent moves to scripted")
t = token(be("agent:assets", "claim", SID, say="asset agent claims"))
be("agent:assets", "attach", SID, "--kind", "footage", "--file", "capture/desk.mp4", "--token", t,
   expect_fail=True, say="asset agent tries to attach human footage itself")
be("agent:assets", "attach", SID, "--kind", "footage", "--token", t, "--request", "15s screen recording of clipper run",
   say="asset agent requests footage from Riftar instead")
be("agent:assets", "move", SID, "assets", "--token", t, expect_fail=True, say="move to assets while footage missing")
be("human", "attach", SID, "--kind", "footage", "--file", "capture/clipper-run.mp4", say="Riftar uploads the footage")
t = token(be("agent:assets", "claim", SID, say="asset agent re-claims"))
be("agent:assets", "move", SID, "assets", "--token", t, say="asset agent moves to assets")
t = token(be("agent:voice", "claim", SID, say="voice agent claims"))
be("agent:voice", "run", "voice", SID, "--token", t, "--fail-primary",
   say="voice run: ElevenLabs fails -> Nexabot fallback (STUB)")
be("agent:voice", "move", SID, "voiced", "--token", t, say="voice agent moves to voiced")
t = token(be("agent:edit", "claim", SID, say="edit agent claims"))
be("agent:edit", "run", "render", SID, "--token", t, say="HyperFrames render (STUB)")
be("agent:edit", "move", SID, "edited", "--token", t, say="edit agent moves to edited")
t = token(be("agent:edit", "claim", SID, say="edit agent claims again for QA"))
be("agent:edit", "move", SID, "review", "--token", t, say="QA passed, moves to review")

print("\n--- Carousel: skips voiced ---")
t = token(be("agent:script", "claim", CID, say="script agent claims the carousel"))
be("agent:script", "update", CID, "--token", t, "--caption", "69 skills, sorted.",
   "--slides", "69 skills|How they load|Top 5|What I deleted|Steal this", say="writes 5 slides")
be("agent:script", "move", CID, "scripted", "--token", t, say="moves to scripted")
t = token(be("agent:assets", "claim", CID, say="asset agent claims"))
be("agent:assets", "attach", CID, "--kind", "screenshot", "--file", "capture/skills-tree.png", "--token", t, say="attaches a screenshot")
be("agent:assets", "move", CID, "assets", "--token", t, say="moves to assets")
t = token(be("agent:edit", "claim", CID, say="edit agent claims"))
be("agent:edit", "move", CID, "voiced", "--token", t, expect_fail=True, say="tries assets -> voiced (carousel)")
be("agent:edit", "run", "carousel", CID, "--token", t, say="renders slides to PNG (STUB)")
be("agent:edit", "move", CID, "edited", "--token", t, say="assets -> edited (voiced skipped)")
t = token(be("agent:edit", "claim", CID, say="edit agent claims for QA"))
be("agent:edit", "move", CID, "review", "--token", t, say="moves to review")

print("\n--- Gate 2: review ---")
t = token(be("agent:publish", "claim", SID, say="publish agent claims the short"))
be("agent:publish", "move", SID, "scheduled", "--token", t, expect_fail=True, say="publish agent tries to skip review")
be("human", "reject", CID, expect_fail=True, say="Riftar rejects carousel without a comment")
be("human", "reject", CID, "--comment", "Slide 3 too dense", "--return-to", "edited", say="Riftar rejects carousel back to edited")
t = token(be("agent:edit", "claim", CID, say="edit agent claims the fix"))
be("agent:edit", "move", CID, "review", "--token", t, say="re-renders, back to review")
be("human", "approve", SID, "--at", "2026-10-20T19:00:00+07:00", say="Riftar approves the short for Tue 19:00 WIB")
be("human", "approve", CID, "--at", "2026-10-21T19:00:00+07:00", say="Riftar approves the carousel for Wed 19:00 WIB")

print("\n--- Publish (manual adapter) ---")
be("agent:publish", "publish", say="publish agent builds the weekly queue file")
t = token(be("agent:publish", "claim", SID, say="publish agent claims the short"))
be("agent:publish", "move", SID, "posted", "--token", t, expect_fail=True, say="mark posted without a URL")
be("agent:publish", "move", SID, "posted", "--token", t, "--url", "https://tiktok.com/@riftar/video/demo1", say="marks short posted with URL")
be("human", "move", CID, "posted", "--url", "https://instagram.com/p/demo2", say="Riftar posts the carousel by hand")

print("\n--- Final board ---")
print(be("human", "status", say="regenerate STATUS.md").split("## Waiting")[0])
print("Demo passed. Files are in .demo/ (posts, STATUS.md, publish/, logs/).")
