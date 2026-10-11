import json, os, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from birdseye import core, server


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BIRDSEYE_ROOT"] = self.tmp.name
        core.ensure_human_key()
        self.s = core.add("agent:ideas", "short one", "build-in-public", "short", "h", "Riftar/x")["id"]
        self.c = core.add("agent:ideas", "carousel one", "build-in-public", "carousel", "h", "Riftar/x")["id"]

    def tearDown(self):
        self.tmp.cleanup()


class DetailLib(Base):
    def test_comment_adds_history_without_state_change(self):
        n = len(core.load(self.s)["history"])
        p = core.comment(self.s, "human", "use the dark theme")
        self.assertEqual(p["status"], "idea")
        self.assertEqual(len(p["history"]), n + 1)
        self.assertEqual(p["history"][-1]["action"], "comment")

    def test_empty_comment_refused_and_logged(self):
        with self.assertRaises(core.BirdsEyeError):
            core.comment(self.s, "human", "  ")
        self.assertEqual(core.refused_attempts(self.s)[-1]["error"], "SCHEMA_INVALID")

    def test_refused_gate_attempt_is_logged(self):
        with self.assertRaises(core.BirdsEyeError):
            core.approve(self.s, "agent:sneaky")
        r = core.refused_attempts(self.s)
        self.assertEqual((r[-1]["actor"], r[-1]["error"]), ("agent:sneaky", "HUMAN_ONLY"))

    def test_stage_path_and_checklist(self):
        self.assertNotIn("voiced", core.stage_path(core.load(self.c)))
        self.assertIn("voiced", core.stage_path(core.load(self.s)))
        t = core.claim(self.s, "agent:a")["token"]
        core.attach(self.s, "agent:a", "footage", token=t, request="desk shot")
        items = core.asset_checklist(core.load(self.s))
        req = [i for i in items if i["state"] == "requested"]
        self.assertEqual(len(req), 1); self.assertEqual(req[0]["by"], "human")
        self.assertTrue(any(i["label"] == "Voiceover" for i in items))
        self.assertFalse(any(i["label"] == "Voiceover" for i in core.asset_checklist(core.load(self.c))))

    def test_detail_gate(self):
        self.assertEqual(core.detail(self.s)["gate"], "gate1")
        core.approve(self.s, "human")
        self.assertIsNone(core.detail(self.s)["gate"])


class DetailHTTP(Base):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()
        super().tearDown()

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            return 200, json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_api_post_and_comment(self):
        d = json.load(urllib.request.urlopen(f"{self.base}/api/post?id={self.s}"))
        self.assertEqual(d["post"]["id"], self.s)
        code, p = self._post("/api/comment", {"id": self.s, "text": "nice hook"})
        self.assertEqual(code, 200); self.assertEqual(p["history"][-1]["note"], "nice hook")
        code, err = self._post("/api/comment", {"id": self.s, "text": ""})
        self.assertEqual((code, err["error"]), (400, "SCHEMA_INVALID"))

    def test_files_no_traversal(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(f"{self.base}/files/.birdseye/human.key")


if __name__ == "__main__":
    unittest.main()
