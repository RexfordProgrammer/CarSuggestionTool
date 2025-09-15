#!/usr/bin/env python3
"""
Deploy Vite-built site (dist/) to S3 with ideal cache headers.
- Non-HTML (JS/CSS/media/fonts): long cache (immutable)
- HTML: no-cache (so updates show immediately)
- Removes stale objects in the target prefix by default (--delete). Use --no-delete to disable.
- Optional CloudFront invalidation.

Usage examples:
  python deploy.py --profile rexford
  python deploy.py --profile rexford --distribution-id E123ABC456DEF
  python deploy.py --profile rexford --prefix ""          # bucket root (default)
  python deploy.py --profile rexford --prefix site/       # deploy to s3://bucket/site/
  python deploy.py --profile rexford --no-delete          # keep old files
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

def run(cmd: List[str], dry_run: bool = False) -> None:
    print("→", " ".join(shlex.quote(c) for c in cmd))
    if dry_run:
        return
    p = subprocess.run(cmd)
    if p.returncode != 0:
        sys.exit(p.returncode)

def aws_base(profile: Optional[str], region: Optional[str]) -> List[str]:
    base = ["aws"]
    if profile:
        base += ["--profile", profile]
    if region:
        base += ["--region", region]
    return base

def s3_sync(
    src: Path,
    dest_uri: str,
    profile: Optional[str],
    region: Optional[str],
    delete: bool,
    dry_run: bool,
    extra_args: List[str],
) -> None:
    cmd = aws_base(profile, region) + ["s3", "sync", str(src), dest_uri] + extra_args
    if delete:
        cmd += ["--delete"]
    run(cmd, dry_run=dry_run)

def deploy(
    dist: Path,
    bucket: str,
    prefix: str,
    profile: Optional[str],
    region: Optional[str],
    delete: bool,
    dry_run: bool,
) -> None:
    if not dist.exists():
        print(f"✗ dist folder not found: {dist.resolve()}")
        sys.exit(1)

    # Normalize prefix → "foo/bar/" or ""
    prefix = prefix.strip("/")
    s3_uri = f"s3://{bucket}/{prefix}/" if prefix else f"s3://{bucket}"

    # Pass 1: Non-HTML (JS/CSS/images/fonts/etc) with long cache
    # NOTE: This sets headers when a file is actually uploaded/updated.
    # Hashed Vite assets always change name on rebuild, so you're covered.
    s3_sync(
        src=dist,
        dest_uri=s3_uri,
        profile=profile,
        region=region,
        delete=delete,
        dry_run=dry_run,
        extra_args=[
            "--exclude", "*.html",
            "--cache-control", "public,max-age=31536000,immutable",
        ],
    )

    # Pass 2: HTML only with no-cache
    s3_sync(
        src=dist,
        dest_uri=s3_uri,
        profile=profile,
        region=region,
        delete=delete,
        dry_run=dry_run,
        extra_args=[
            "--exclude", "*",
            "--include", "*.html",
            "--cache-control", "no-cache",
        ],
    )

def invalidate_cf(
    distribution_id: str,
    paths: str,
    profile: Optional[str],
    region: Optional[str],
    dry_run: bool,
) -> None:
    cmd = aws_base(profile, region) + [
        "cloudfront",
        "create-invalidation",
        "--distribution-id",
        distribution_id,
        "--paths",
        paths,
    ]
    run(cmd, dry_run=dry_run)

def main() -> None:
    ap = argparse.ArgumentParser(description="Deploy dist/ to S3 (and optionally invalidate CloudFront).")
    ap.add_argument("--dist", default="dist", help="Path to built site (default: dist)")
    ap.add_argument("--bucket", default="rexforddorchester-website-bucket", help="S3 bucket name")
    ap.add_argument("--prefix", default="", help="Key prefix in bucket (e.g. 'site/' or blank for root)")
    ap.add_argument("--profile", default=None, help="AWS CLI profile name (optional)")
    ap.add_argument("--region", default=None, help="AWS region override (optional)")
    # Deletion: on by default (safer for a dedicated bucket/prefix). Use --no-delete to disable.
    ap.add_argument("--no-delete", action="store_true", help="Do NOT delete remote files that are not in local dist/")
    ap.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    ap.add_argument("--distribution-id", default=None, help="CloudFront distribution ID (optional)")
    ap.add_argument("--invalidate-paths", default="/*", help="CloudFront paths to invalidate (default: /*)")
    args = ap.parse_args()

    delete = not args.no_delete

    dist_path = Path(args.dist)
    deploy(
        dist=dist_path,
        bucket=args.bucket,
        prefix=args.prefix,
        profile=args.profile,
        region=args.region,
        delete=delete,
        dry_run=args.dry_run,
    )

    if args.distribution_id:
        invalidate_cf(
            distribution_id=args.distribution_id,
            paths=args.invalidate_paths,
            profile=args.profile,
            region=args.region,
            dry_run=args.dry_run,
        )
        print("✓ CloudFront invalidation requested.")

    print("✓ Deploy complete.")

if __name__ == "__main__":
    main()
