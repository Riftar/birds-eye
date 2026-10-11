"""Seed the 3 EXAMPLE posts from the spec at different stages.
python -m birdseye.seed   (idempotent: skips posts that already exist)"""
from . import core, adapters, status

SEEDS = [
    dict(post_id="2026-10-12-dealscout-listings", title="DealScout: new model confirmed 0 of 12 listings",
         pillar="failures-lessons", fmt="carousel", source_repo="Riftar/DealScout",
         hook="The new model confirmed 0 of 12 listings. The old one confirmed 3. Same pages."),
    dict(post_id="2026-10-13-tiktok-viral-sleep", title="tiktok-viral: 4 videos a day while I sleep",
         pillar="how-i-automate", fmt="short", source_repo="Riftar/tiktok-viral",
         hook="My AI posts 4 videos a day while I sleep. This is the pipeline."),
    dict(post_id="2026-10-14-stock-agent-cost", title="Stock-analysis agent monthly cost",
         pillar="failures-lessons", fmt="short", source_repo="Riftar/trading-signal-pipeline",
         hook="My stock-analysis agent costs $2.66 a month."),
]


def run():
    core.ensure_human_key()
    for s in SEEDS:
        if list(core.posts_dir().glob(f"*/{s['post_id']}/post.json")):
            print(f"skip {s['post_id']} (exists)")
            continue
        core.add("agent:ideas", s["title"], s["pillar"], s["fmt"], s["hook"], s["source_repo"],
                 example=True, post_id=s["post_id"])
    H = core.HUMAN
    # 1) DealScout carousel -> all the way to review (waiting on gate 2)
    d = "2026-10-12-dealscout-listings"
    if core.load(d)["status"] == "idea":
        core.approve(d, H, "Strong hook, honest numbers")
        t = core.claim(d, "agent:script")["token"]
        core.update(d, "agent:script", t, caption="Same pages, two models, very different answers. (example)",
                    slides=["0 of 12 vs 3 of 12", "What DealScout checks", "Where the new model failed",
                            "What I changed", "Lesson: eval before you upgrade"],
                    hashtags=["#buildinpublic", "#aiagents"])
        core.move(d, "agent:script", "scripted", t)
        t = core.claim(d, "agent:assets")["token"]
        core.attach(d, "agent:assets", "screenshot", "capture/listing-diff.png (example)", token=t)
        core.move(d, "agent:assets", "assets", t)
        t = core.claim(d, "agent:edit")["token"]
        adapters.carousel(d, "agent:edit", t)
        core.move(d, "agent:edit", "edited", t, note="carousel skips voiced")
        t = core.claim(d, "agent:edit")["token"]
        core.move(d, "agent:edit", "review", t)
        t = core.claim(d, "agent:publish")["token"]
        try:   # realistic refused attempt: agent tries to pass gate 2
            core.move(d, "agent:publish", "scheduled", t)
        except core.BirdsEyeError:
            pass
    # 2) tiktok-viral short stays at idea (waiting on gate 1)
    # 3) stock-agent-cost short -> scripted, with a human footage request open
    s = "2026-10-14-stock-agent-cost"
    if core.load(s)["status"] == "idea":
        core.approve(s, H)
        t = core.claim(s, "agent:script")["token"]
        core.update(s, "agent:script", t, caption="What it really costs to run my stock-analysis agent. (example)",
                    beats=["hook", "what it does", "cost breakdown", "lesson"],
                    hashtags=["#buildinpublic", "#aiagents"])
        (core.find_post_dir(s) / "script.md").write_text(
            "# Script (example)\n\n"
            "1. **Hook**: My stock-analysis agent costs $2.66 a month.\n"
            "2. **What it does**: trading-signal-pipeline, Riftar/trading-signal-pipeline.\n"
            "3. **Cost breakdown**: walk the pipeline tiers.\n"
            "4. **Lesson**: TBD by script agent.\n")
        core.move(s, "agent:script", "scripted", t)
        t = core.claim(s, "agent:assets")["token"]
        core.attach(s, "agent:assets", "screenshot", "capture/billing.png (example)", token=t)
        core.attach(s, "agent:assets", "footage", token=t, request="10s desk shot, laptop showing dashboard")
        try:   # realistic refused attempt: move while human footage is missing
            core.move(s, "agent:assets", "assets", t)
        except core.BirdsEyeError:
            pass
    status.write()
    print("seeded 3 example posts; see STATUS.md")


if __name__ == "__main__":
    run()
