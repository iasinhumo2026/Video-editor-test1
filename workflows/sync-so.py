#!/usr/bin/env python3
"""sync-so.py: lip-sync a video to a new audio take through the sync.so v2 API, and record how it was made.

  uv run workflows/sync-so.py <video> <audio> --out <out.mp4> --source-note "raw frame 6552+, crop x=1404 w=1216"
  uv run workflows/sync-so.py <video> <audio> --model sync-3 --sync-mode cut_off --out <out.mp4> --dry-run
  uv run workflows/sync-so.py --fetch <generation-id> --out <out.mp4>

  --model M         sync.so model (default sync-3, the one the re-recorded CTAs shipped on)
  --sync-mode S     how a video/audio length mismatch is handled (default cut_off)
  --out PATH        the lip-synced mp4; refused if it, or its provenance file, already exists
  --source-note T   where <video> came from (raw frame range, crop, scale); recorded, never inferred
  --fetch ID        finish a run that stopped after its generation was submitted (a failed download, the poll
                    timeout, an interrupt): reads <out>.provenance.json, which must name ID, waits for the generation,
                    downloads it and completes the provenance. Nothing is uploaded or generated again.
  --dry-run         probe and hash the inputs, print the requests and the provenance it would write; no network

What it does: uploads both files as assets (POST /v2/assets/upload -> PUT to the presigned URL -> POST /v2/assets),
prints the cost estimate (POST /v2/analyze/cost; an estimate that fails is recorded, never fatal), generates
(POST /v2/generate), polls GET /v2/generate/{id} every 15 s, downloads the output, and writes
<out>.provenance.json beside it: both inputs with sha1 + an ffprobe summary + their asset ids, the output the same,
the model, the mode, the generation id, the cost estimate, the source note and the timestamps.

The provenance is written the moment the generation is submitted, with "incomplete" carrying the --fetch command
that finishes it, so a paid generation is never lost to anything that fails after it; the download fills in
"output" and clears "incomplete". A generation that ends FAILED or REJECTED has no take to fetch, so its provenance
is removed and the exit message carries the id and the error.

Why this exists (2026-09-22/23): the client was written mid-session inside one job and copied to the next with the
key read from an absolute home path, and nothing recorded which raw frames or crop a take was cut from, so that had
to be reverse-engineered by audio and pixel matching, and the recipe was recovered from old session logs. A paid
generation's download also 403'd once and was recovered with a hand-typed curl.

Every request, the presigned PUT and the CDN download included, sends a curl user agent: api.sync.so and its output
CDN sit behind Cloudflare, which answers Python-urllib's default one with 403 "error code: 1010". When urllib is
still refused (403) on the download, it is retried once with the curl binary, the path the first takes were fetched on. The API key
goes to api.sync.so only, never to the upload or download hosts, and is never printed.

Auth: SYNC_API_KEY in the environment, or in the repo-root .env (found relative to this file).
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"
API = "https://api.sync.so"
UA = "curl/8.7.1"                     # Cloudflare 1010-blocks Python-urllib's default user agent
POLL_S = 15
MAX_WAIT_S = 3600                     # a generation still running after an hour is recorded for --fetch, not waited on
TERMINAL = ("COMPLETED", "FAILED", "REJECTED")
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime"}
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}
PROBE_KEYS = ("index", "codec_type", "codec_name", "profile", "width", "height", "pix_fmt", "r_frame_rate",
              "nb_frames", "sample_rate", "channels", "duration")


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def parse_env(text, name="SYNC_API_KEY"):
    """The value of `name` in dotenv text: `export` prefix, quotes and an unquoted ` # comment` handled."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, sep, v = line.partition("=")
        if not sep or k.strip() != name:
            continue
        v = v.strip()
        if v[:1] in ('"', "'") and v.endswith(v[0]) and len(v) > 1:
            return v[1:-1]
        return v.split(" #", 1)[0].strip()
    return ""


def load_key(env_file=None):
    """(key, where it came from). The environment wins; the repo-root .env is the fallback."""
    key = os.environ.get("SYNC_API_KEY", "").strip()
    if key:
        return key, "environment"
    env_file = Path(env_file) if env_file else ENV_FILE
    if env_file.exists():
        key = parse_env(env_file.read_text(encoding="utf-8"))
        if key:
            return key, ".env"
    sys.exit(f"SYNC_API_KEY missing: set it in the environment or add SYNC_API_KEY=... to {env_file.name} at the repo root")


def curl_download(url, dest):
    """The download through the curl binary; False when there is none. Same UA, no key, and the signed URL is never
    echoed (curl's -sS error names only the HTTP status)."""
    exe = shutil.which("curl")
    if not exe:
        return False
    r = subprocess.run([exe, "-sSfL", "-A", UA, "-o", str(dest), url], capture_output=True, text=True)
    if r.returncode:
        raise ApiError(r.returncode, f"curl download -> exit {r.returncode}: {r.stderr.strip()[-300:]}")
    return True


class Client:
    def __init__(self, key):
        self.key = key

    def redact(self, text):
        return text.replace(self.key, "[redacted]") if self.key else text

    def request(self, method, url, body=None, *, data=None, headers=None, timeout=120):
        """One HTTP call. The curl UA on every one; the key only on api.sync.so."""
        h = {"User-Agent": UA, **(headers or {})}
        if url.startswith(API + "/"):
            h["x-api-key"] = self.key
        if body is not None:
            data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(url, method=method, data=data, headers=h)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            where = url[len(API):] if url.startswith(API) else url.split("?", 1)[0]
            raise ApiError(e.code, self.redact(f"{method} {where} -> {e.code}: {e.read().decode(errors='replace')[:500]}"))

    def api(self, method, path, body=None):
        with self.request(method, API + path, body) as r:
            return json.loads(r.read() or b"{}")

    def upload(self, path, ctype, atype):
        size = path.stat().st_size
        pre = self.api("POST", "/v2/assets/upload", {"fileName": path.name, "contentType": ctype, "size": size})
        with path.open("rb") as fh, self.request("PUT", pre["uploadUrl"], data=fh, timeout=600,
                                                 headers={"Content-Type": ctype, "Content-Length": str(size)}) as r:
            if r.status not in (200, 201, 204):
                raise ApiError(r.status, f"PUT {path.name} to the presigned URL -> {r.status}")
        asset = self.api("POST", "/v2/assets", {"url": pre["url"], "type": atype, "name": path.name})
        print(f"uploaded {path.name} ({size / 1e6:.1f} MB) -> asset {asset['id']}", flush=True)
        return asset["id"]

    def wait(self, gen_id):
        """Poll every POLL_S until a terminal status, for at most MAX_WAIT_S; the last status seen is returned.
        A 5xx or dropped connection is a retry, not a lost generation."""
        g = {"id": gen_id, "status": None}
        for _ in range(MAX_WAIT_S // POLL_S):
            time.sleep(POLL_S)
            try:
                g = self.api("GET", f"/v2/generate/{gen_id}")
            except OSError as e:                      # URLError, a timeout, a reset connection
                print(f"{time.strftime('%H:%M:%S')} poll failed ({e}), retrying", flush=True)
                continue
            except ApiError as e:
                if e.code < 500:
                    raise
                print(f"{time.strftime('%H:%M:%S')} poll failed ({e}), retrying", flush=True)
                continue
            print(time.strftime("%H:%M:%S"), g.get("status"), flush=True)
            if g.get("status") in TERMINAL:
                break
        return g

    def download(self, url, dest):
        try:
            with self.request("GET", url, timeout=600) as r, dest.open("wb") as fh:
                while chunk := r.read(1 << 20):
                    fh.write(chunk)
        except ApiError as e:
            if e.code != 403 or not curl_download(url, dest):
                raise
            print(f"urllib download refused ({e.code}); fetched with the curl binary", flush=True)


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def sha1(path):
    h = hashlib.sha1()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=format_name,duration,size:stream=" + ",".join(PROBE_KEYS), "-of", "json", str(path)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffprobe could not read {path}: {r.stderr.strip()[-300:]}")
    d = json.loads(r.stdout or "{}")
    return {"format": d.get("format", {}),
            "streams": [{k: s[k] for k in PROBE_KEYS if k in s} for s in d.get("streams", [])]}


def shown(path):
    """Repo-relative when the file is inside the repo, so a provenance file carries no home directory. Always with
    forward slashes: a Windows path's backslashes are eaten when the recorded --fetch command is pasted into Git Bash
    (`--out projects\\job\\take.mp4` reaches Python as `projectsjobtake.mp4`), and Python on Windows takes `/`."""
    p = path.resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def describe(path, role, types):
    """The input's record, refusing anything that would waste a paid generation."""
    if not path.is_file():
        sys.exit(f"{role} not found: {path}")
    ctype = types.get(path.suffix.lower())
    if not ctype:
        sys.exit(f"{role} {path.name}: use one of {', '.join(types)} (convert with ffmpeg first)")
    info = probe(path)
    if not any(s.get("codec_type") == role for s in info["streams"]):  # role doubles as the ffprobe codec_type
        sys.exit(f"{role} {path.name} has no {role} stream (video and audio swapped?)")
    return {"path": shown(path), "name": path.name, "content_type": ctype, "bytes": path.stat().st_size,
            "sha1": sha1(path), "ffprobe": info}


def duration(record):
    try:
        return float(record["ffprobe"]["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def cost_usd(est):
    """The $ total of a cost estimate. The API answers one object ({"estimatedFrameCount": 232,
    "estimatedGenerationCost": 1.24, "estimatedCredits": null}, 2026-09-22/23); a list is summed."""
    costs = [e.get("estimatedGenerationCost") for e in (est if isinstance(est, list) else [est]) if isinstance(e, dict)]
    costs = [c for c in costs if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return sum(costs) if costs else None


def generation_body(model, sync_mode, video_id, audio_id):
    return {"model": model, "input": [{"type": "video", "assetId": video_id}, {"type": "audio", "assetId": audio_id}],
            "options": {"sync_mode": sync_mode}}


def generation_record(g):
    return {"id": g.get("id"), "status": g.get("status"), "created_at": g.get("createdAt"),
            "output_duration": g.get("outputDuration")}


def save(prov_path, prov):
    """Written whole and swapped in, so an interrupt never leaves half a provenance file."""
    tmp = prov_path.with_name(prov_path.name + ".tmp")
    tmp.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    tmp.replace(prov_path)


def fetch_command(gen_id, out):
    return f"uv run workflows/sync-so.py --fetch {gen_id} --out {shown(out)}"


def stop(prov, prov_path, out, reason):
    """A submitted generation that did not reach --out: the provenance keeps it and names the --fetch that ends it."""
    gen_id = prov["generation"]["id"]
    prov["incomplete"] = {"reason": reason, "fetch": fetch_command(gen_id, out), "at": now()}
    save(prov_path, prov)
    sys.exit(f"{reason}\ngeneration {gen_id} is recorded in {prov_path}; finish it with:\n  {fetch_command(gen_id, out)}")


def finish(client, prov, prov_path, out, poll_now=False):
    """Wait for the recorded generation, download it to --out and complete the provenance."""
    gen_id = prov["generation"]["id"]
    try:
        g = client.api("GET", f"/v2/generate/{gen_id}") if poll_now else {"id": gen_id, "status": None}
        if poll_now:
            print(time.strftime("%H:%M:%S"), g.get("status"), flush=True)
        if g.get("status") not in TERMINAL:
            g = client.wait(gen_id)
    except (ApiError, OSError) as e:
        stop(prov, prov_path, out, f"polling failed: {client.redact(str(e))}")
    prov["generation"] = {**generation_record(g), "id": gen_id}
    if g.get("status") not in TERMINAL:
        stop(prov, prov_path, out, f"generation still {g.get('status')} after {MAX_WAIT_S // 60} min")
    prov["timestamps"]["finished"] = now()
    if g["status"] != "COMPLETED":
        prov_path.unlink(missing_ok=True)             # no take exists or ever will: nothing to record or fetch
        sys.exit(f"generation {gen_id} {g['status']}: {g.get('error')} {g.get('errorCode') or ''}".rstrip())
    part = out.with_name(out.name + ".part")
    try:
        client.download(g["outputUrl"], part)
    except (ApiError, OSError) as e:
        stop(prov, prov_path, out, f"download failed: {client.redact(str(e))}")
    if out.exists():                                  # another process wrote it while this one generated
        stop(prov, prov_path, out, f"{out} appeared during the run; the download is kept at {part}")
    part.rename(out)
    prov["timestamps"]["downloaded"] = now()
    prov["output"] = {"path": shown(out), "name": out.name, "bytes": out.stat().st_size, "sha1": sha1(out),
                      "ffprobe": probe(out)}
    prov["incomplete"] = None
    save(prov_path, prov)
    print(f"saved {out} ({out.stat().st_size / 1e6:.1f} MB), outputDuration {g.get('outputDuration')}")
    print(f"provenance {prov_path}")
    return 0


def fetch(a, out, prov_path):
    """--fetch: finish the generation the provenance beside --out records; never upload or generate."""
    if not prov_path.is_file():
        sys.exit(f"no {prov_path}: --fetch finishes a run this tool submitted, whose provenance names the generation")
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    recorded = (prov.get("generation") or {}).get("id")
    if recorded != a.fetch:
        sys.exit(f"{prov_path.name} records generation {recorded}, not {a.fetch}: fetch into the --out it was made for")
    key, key_from = load_key()
    if a.dry_run:
        print(f"dry run, no network calls. SYNC_API_KEY found in the {key_from}.")
        print(f"  GET /v2/generate/{a.fetch}, then every {POLL_S} s until {'/'.join(TERMINAL)}, then download to {out}")
        return 0
    prov.setdefault("timestamps", {})["fetch_started"] = now()
    return finish(Client(key), prov, prov_path, out, poll_now=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("video", nargs="?")
    ap.add_argument("audio", nargs="?")
    ap.add_argument("--model", default="sync-3")
    ap.add_argument("--sync-mode", default="cut_off")
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-note")
    ap.add_argument("--fetch", metavar="GENERATION_ID")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.fetch and (a.video or a.audio):
        ap.error("--fetch takes no video or audio: it finishes the run its provenance records")
    if not a.fetch and not (a.video and a.audio):
        ap.error("video and audio are required (or --fetch <generation-id> to finish a submitted run)")

    out = Path(a.out)
    prov_path = out.with_name(out.name + ".provenance.json")
    if out.exists():
        sys.exit(f"refusing to overwrite {out}: pick a new --out (a re-take gets its own name)")
    if a.fetch:
        return fetch(a, out, prov_path)
    if prov_path.exists():
        sys.exit(f"refusing to overwrite {prov_path}: pick a new --out (a re-take gets its own name), or finish the "
                 f"generation it records with --fetch <id>")
    if not out.parent.is_dir():
        sys.exit(f"--out folder does not exist: {out.parent}")

    started = now()
    key, key_from = load_key()
    video = describe(Path(a.video), "video", VIDEO_TYPES)
    audio = describe(Path(a.audio), "audio", AUDIO_TYPES)
    dv, da = duration(video), duration(audio)
    if dv is not None and da is not None:
        print(f"video {dv:.4f} s, audio {da:.4f} s, audio - video = {da - dv:+.4f} s ({a.sync_mode})")
    if not a.source_note:
        print("⚠ no --source-note: record the raw frame range and crop this video was cut from, or the next "
              "session reverse-engineers it")

    prov = {"tool": "workflows/sync-so.py", "api": API, "model": a.model, "sync_mode": a.sync_mode,
            "source_note": a.source_note, "inputs": {"video": video, "audio": audio},
            "cost_estimate": None, "cost_estimate_error": None, "generation": None, "output": None,
            "incomplete": None, "timestamps": {"started": started}}

    if a.dry_run:
        body = generation_body(a.model, a.sync_mode, "<video asset id>", "<audio asset id>")
        print(f"dry run, no network calls. SYNC_API_KEY found in the {key_from}.")
        for role, rec in (("video", video), ("audio", audio)):
            print(f"  POST /v2/assets/upload {json.dumps({'fileName': rec['name'], 'contentType': rec['content_type'], 'size': rec['bytes']})}")
            print(f"  PUT <presigned uploadUrl> ({rec['bytes']} bytes), then POST /v2/assets type {role.upper()}")
        print(f"  POST /v2/analyze/cost {json.dumps(body)}")
        print(f"  POST /v2/generate {json.dumps({**body, 'outputFileName': out.stem})}")
        print(f"  GET /v2/generate/<id> every {POLL_S} s until {'/'.join(TERMINAL)}, then download to {out}")
        print(f"would write {prov_path} (as soon as the generation is submitted):")
        print(json.dumps(prov, indent=2))
        return 0

    client = Client(key)
    try:
        video["asset_id"] = client.upload(Path(a.video), video["content_type"], "VIDEO")
        audio["asset_id"] = client.upload(Path(a.audio), audio["content_type"], "AUDIO")
        body = generation_body(a.model, a.sync_mode, video["asset_id"], audio["asset_id"])
        try:
            est = client.api("POST", "/v2/analyze/cost", body)
            prov["cost_estimate"] = est
            usd = cost_usd(est)
            print(f"cost estimate: {json.dumps(est)}" + (f" (${usd:.2f})" if usd is not None else ""), flush=True)
        except (ApiError, OSError) as e:
            prov["cost_estimate_error"] = client.redact(str(e))
            print(f"cost estimate unavailable: {prov['cost_estimate_error']}", flush=True)
        g = client.api("POST", "/v2/generate", {**body, "outputFileName": out.stem})
    except (ApiError, OSError) as e:                  # nothing submitted yet, so nothing paid and nothing to record
        sys.exit(client.redact(str(e)))
    prov["timestamps"]["submitted"] = now()
    prov["generation"] = generation_record(g)
    prov["incomplete"] = {"reason": "submitted; the output has not been downloaded yet",
                          "fetch": fetch_command(g["id"], out), "at": prov["timestamps"]["submitted"]}
    save(prov_path, prov)                             # the paid generation is on disk before anything can fail
    print("generation", g["id"], g.get("status"), flush=True)
    return finish(client, prov, prov_path, out)


if __name__ == "__main__":
    sys.exit(main())
