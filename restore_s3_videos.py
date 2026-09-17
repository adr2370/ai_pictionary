"""One-off: restore missing pictionary videos to S3 from local + E: backups.

- Catalog: parts 1..7800 (contiguous), keyed in S3 as
  videos/the_worlds_longest_game_of_pictionary_part_N.mp4  (matches CSV URLs).
- Sources: local videos/ (7501-7800) preferred, else E: backup (1-7500).
- Idempotent: skips parts already present in S3, so re-running resumes.
"""
import os
import re
import sys
import time

import boto3
from botocore.exceptions import ClientError

BUCKET = "ai-pictionary-videos-adr2370"
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-1")
CATALOG_MAX = 7800
LOCAL = r"C:\Users\adr23\Projects\ai_pictionary\videos"
EBACKUP = r"E:\AI Pictionary Backup\videos"
CANON = "the_worlds_longest_game_of_pictionary_part_{}.mp4"
PART_RE = re.compile(r"part_(\d+)\.mp4$", re.IGNORECASE)


def log(msg):
    print(msg, flush=True)


def scan(d):
    """Map part_number -> filepath for every part_N.mp4 in dir d."""
    mp = {}
    if not os.path.isdir(d):
        log(f"WARNING: source dir missing: {d}")
        return mp
    for e in os.scandir(d):
        m = PART_RE.search(e.name)
        if m:
            mp[int(m.group(1))] = e.path
    return mp


def main():
    s3 = boto3.client("s3")

    # --- Phase 0: preflight ---
    log("[preflight] listing existing S3 videos/ ...")
    present = set()
    paginator = s3.get_paginator("list_objects_v2")
    for pg in paginator.paginate(Bucket=BUCKET, Prefix="videos/"):
        for o in pg.get("Contents", []):
            m = PART_RE.search(o["Key"])
            if m:
                present.add(int(m.group(1)))
    log(f"[preflight] already in S3: {len(present)}")

    needed = [n for n in range(1, CATALOG_MAX + 1) if n not in present]
    log(f"[preflight] missing from S3: {len(needed)}")

    log("[preflight] scanning local videos/ ...")
    local_map = scan(LOCAL)
    log(f"[preflight] local source files: {len(local_map)}")
    log("[preflight] scanning E: backup (slow) ...")
    e_map = scan(EBACKUP)
    log(f"[preflight] E: backup source files: {len(e_map)}")

    plan = []
    unresolved = []
    for n in needed:
        src = local_map.get(n) or e_map.get(n)
        if src:
            plan.append((n, src))
        else:
            unresolved.append(n)

    total_bytes = sum(os.path.getsize(s) for _, s in plan)
    log(f"[preflight] resolved to a source: {len(plan)}")
    log(f"[preflight] UNRESOLVED (no backup found): {len(unresolved)}")
    if unresolved:
        log(f"[preflight] unresolved sample: {unresolved[:50]}")
    log(f"[preflight] total upload size: {total_bytes/1e9:.2f} GB")

    if not plan:
        log("[preflight] nothing to upload. Done.")
        return

    # --- Phase 1: upload ---
    log(f"[upload] starting {len(plan)} uploads ...")
    done = 0
    failed = []
    t0 = time.time()
    for i, (n, src) in enumerate(plan, 1):
        key = f"videos/{CANON.format(n)}"
        for attempt in range(3):
            try:
                s3.upload_file(
                    src, BUCKET, key, ExtraArgs={"ContentType": "video/mp4"}
                )
                done += 1
                break
            except (ClientError, OSError) as ex:
                if attempt == 2:
                    failed.append((n, str(ex)))
                    log(f"[upload] FAILED part {n}: {ex}")
                else:
                    time.sleep(2 * (attempt + 1))
        if i % 100 == 0:
            rate = i / max(time.time() - t0, 1)
            eta = (len(plan) - i) / max(rate, 0.001) / 60
            log(
                f"[upload] {i}/{len(plan)}  ok={done} failed={len(failed)}  "
                f"{rate:.1f}/s  ETA {eta:.0f} min"
            )

    log(f"[upload] DONE. uploaded={done} failed={len(failed)}")
    if failed:
        log(f"[upload] failures: {failed[:50]}")

    # --- Phase 2: verify count ---
    present2 = set()
    for pg in paginator.paginate(Bucket=BUCKET, Prefix="videos/"):
        for o in pg.get("Contents", []):
            m = PART_RE.search(o["Key"])
            if m:
                present2.add(int(m.group(1)))
    still_missing = [n for n in range(1, CATALOG_MAX + 1) if n not in present2]
    log(f"[verify] S3 now has {len(present2)} / {CATALOG_MAX} parts")
    log(f"[verify] still missing: {len(still_missing)}")
    if still_missing:
        log(f"[verify] still-missing sample: {still_missing[:50]}")


if __name__ == "__main__":
    sys.exit(main())
