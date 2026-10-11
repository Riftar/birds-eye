import os, tempfile, unittest
from datetime import timedelta
from birdseye import core


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BIRDSEYE_ROOT"] = self.tmp.name
        core.ensure_human_key()

    def tearDown(self):
        self.tmp.cleanup()

    def new(self, fmt="short"):
        return core.add("agent:ideas", f"t {fmt}", "build-in-public", fmt, "hook", "Riftar/x")["id"]

    def claim(self, pid, who="agent:a"):
        return core.claim(pid, who)["token"]

    def expect(self, code, fn, *a, **k):
        with self.assertRaises(core.BirdsEyeError) as cm:
            fn(*a, **k)
        self.assertEqual(cm.exception.code, code)


class Gates(Base):
    def test_agent_cannot_pass_gate1_even_with_claim(self):
        pid = self.new(); t = self.claim(pid)
        self.expect("HUMAN_ONLY", core.move, pid, "agent:a", "approved", t)
        self.expect("HUMAN_ONLY", core.approve, pid, "agent:a")
        self.assertEqual(core.load(pid)["status"], "idea")

    def test_human_needs_local_key(self):
        pid = self.new(); os.remove(core.human_key_path())
        self.expect("HUMAN_ONLY", core.approve, pid, "human")

    def test_gate2_human_only_and_reject_needs_comment(self):
        pid = self.new("carousel"); self._to_review(pid)
        t = self.claim(pid)
        self.expect("HUMAN_ONLY", core.move, pid, "agent:a", "scheduled", t)
        self.expect("SCHEMA_INVALID", core.reject, pid, "human", "")
        core.reject(pid, "human", "redo slide 2")
        self.assertEqual(core.load(pid)["status"], "edited")

    def test_gate2_approve_schedules(self):
        pid = self.new("carousel"); self._to_review(pid)
        p = core.approve(pid, "human", schedule_at="2026-10-20T19:00:00+07:00")
        self.assertEqual(p["status"], "scheduled"); self.assertEqual(p["review"]["decision"], "approved")

    def _to_review(self, pid):
        core.approve(pid, "human")
        t = self.claim(pid); core.update(pid, "agent:a", t, caption="c", slides=["a", "b", "c"])
        core.move(pid, "agent:a", "scripted", t)
        t = self.claim(pid); core.move(pid, "agent:a", "assets", t)
        t = self.claim(pid)
        for i in range(3):
            core.attach(pid, "agent:a", "slide", f"s{i}.png", token=t)
        core.move(pid, "agent:a", "edited", t)
        t = self.claim(pid); core.move(pid, "agent:a", "review", t)


class Transitions(Base):
    def test_cannot_skip(self):
        pid = self.new(); core.approve(pid, "human"); t = self.claim(pid)
        self.expect("INVALID_TRANSITION", core.move, pid, "agent:a", "assets", t)

    def test_carousel_skips_voiced_short_does_not(self):
        s, c = self.new("short"), self.new("carousel")
        self.assertEqual(core.allowed_targets({**core.load(s), "status": "assets"})[0], "voiced")
        self.assertEqual(core.allowed_targets({**core.load(c), "status": "assets"})[0], "edited")
        self.assertNotIn("voiced", core.allowed_targets({**core.load(c), "status": "edited"}))

    def test_missing_requirements_block_and_write_nothing(self):
        pid = self.new(); core.approve(pid, "human"); t = self.claim(pid)
        before = core.load(pid)
        self.expect("MISSING_ASSETS", core.move, pid, "agent:a", "scripted", t)
        self.assertEqual(core.load(pid), before)

    def test_backward_needs_note(self):
        pid = self.new(); core.approve(pid, "human"); t = self.claim(pid)
        self.expect("INVALID_TRANSITION", core.move, pid, "agent:a", "idea", t)
        core.move(pid, "agent:a", "idea", t, note="rethink")

    def test_one_history_entry_per_change(self):
        pid = self.new(); n = len(core.load(pid)["history"])
        core.approve(pid, "human")
        self.assertEqual(len(core.load(pid)["history"]), n + 1)

    def test_agent_cannot_attach_footage(self):
        pid = self.new(); t = self.claim(pid)
        self.expect("HUMAN_ONLY", core.attach, pid, "agent:a", "footage", "x.mp4", token=t)


class Claims(Base):
    def test_exclusive(self):
        pid = self.new(); self.claim(pid, "agent:a")
        self.expect("ALREADY_CLAIMED", core.claim, pid, "agent:b")

    def test_wrong_token_and_no_claim_refused(self):
        pid = self.new(); core.approve(pid, "human")
        self.expect("CLAIM_LOST", core.update, pid, "agent:a", None, caption="x")
        self.claim(pid)
        self.expect("CLAIM_LOST", core.update, pid, "agent:a", "bad", caption="x")

    def test_expired_claim_can_be_taken_and_old_holder_refused(self):
        pid = self.new(); t = self.claim(pid, "agent:a")
        def expire(p): p["claim"]["until"] = core.iso(core.now() - timedelta(minutes=1))
        core.mutate(pid, "test", "expire", expire)
        self.claim(pid, "agent:b")
        self.expect("CLAIM_LOST", core.update, pid, "agent:a", t, caption="x")


if __name__ == "__main__":
    unittest.main()
