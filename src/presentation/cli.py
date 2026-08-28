"""python cli.py sources|add-source|generate|status|publish|profile-fit|profile-derive|
profile-classify-chapters|profile-derive-toc-chapters|profile-confirm-chapters|profile-auto"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from application.use_cases import (
    ChapterAllowlistError,
    GenerateError,
    PublishBlockedError,
    ValidationError,
)
from domain.manual_parsing import ConfirmedChapter
from domain.model import ParameterStatus
from domain.slug import slugify

from .composition import build_use_cases


def cmd_sources(uc, args) -> None:
    for row in uc.source_registry.list_sources():
        print(f"{row['manual_id']:45} {row.get('title', '')}")


def cmd_add_source(uc, args) -> None:
    uc.register_source(
        args.manual_id,
        {
            "maker": args.maker,
            "model": args.model,
            "title": args.title,
            "source_url": args.source_url,
            "retrieved_at": args.retrieved_at,
            "markets": args.markets.split(",") if args.markets else [],
            "license_state": args.license_state,
        },
    )
    print(f"registered {args.manual_id}")


def cmd_generate(uc, args) -> None:
    try:
        result = uc.generate(args.manual_id, args.chapter, chapter_label=args.chapter)
    except GenerateError as e:
        print(f"generate failed: {e}", file=sys.stderr)
        if e.available_chapters:
            print("available top-level chapters:", file=sys.stderr)
            for title in e.available_chapters:
                print(f"  - {title}", file=sys.stderr)
        sys.exit(1)
    counts = result.spec.counts()
    print(
        f"generated {counts['functions']} functions / {counts['requirements']} requirements / "
        f"{counts['thresholds']} thresholds ({counts['thresholds_unfilled']} unfilled) / "
        f"{counts['test_ready']} test-ready"
    )
    if result.unmatched_headings:
        print(f"{len(result.unmatched_headings)} heading(s) could not be matched to body text:")
        for title in result.unmatched_headings:
            print(f"  - {title}")


def cmd_status(uc, args) -> None:
    chapter_slug = slugify(args.chapter) if args.chapter else None
    if chapter_slug is None:
        chapters = uc.list_chapters(args.manual_id)
        if not chapters:
            print("not generated yet", file=sys.stderr)
            sys.exit(1)
        if len(chapters) > 1:
            print("multiple chapters generated, pass --chapter: " + ", ".join(chapters), file=sys.stderr)
            sys.exit(1)
        chapter_slug = chapters[0]
    spec = uc.load_spec(args.manual_id, chapter_slug)
    if spec is None:
        print("not generated yet", file=sys.stderr)
        sys.exit(1)
    for f in spec.functions:
        unfilled = [t for t in f.all_thresholds if t.status == ParameterStatus.UNFILLED]
        if unfilled:
            print(f"{f.chapter_number} {f.title}: {len(unfilled)} unfilled threshold(s)")
            for t in unfilled:
                print(f"    {t.threshold_id}  {t.matching_text!r}")


def cmd_publish(uc, args) -> None:
    chapter_slug = slugify(args.chapter)
    try:
        files = uc.publish(args.manual_id, chapter_slug, allow_restricted=args.allow_restricted)
    except PublishBlockedError as e:
        print(f"publish blocked: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"wrote {len(files)} file(s)")
    for f in files:
        print(f"  {f}")


def cmd_profile_fit(uc, args) -> None:
    try:
        report = uc.check_profile_fitness(args.manual_id, args.profile, chapter_prefix=args.chapter)
    except GenerateError as e:
        print(f"profile-fit failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"fits: {report.fits}")
    if report.bookmark_depth_ok is not None:
        print(f"  bookmark_depth_ok: {report.bookmark_depth_ok}")
    print(f"  column_match_ok: {report.column_match_ok}")
    if report.anomaly_ratio is not None:
        print(f"  anomaly_ratio: {report.anomaly_ratio:.1%}")
    for reason in report.reasons:
        print(f"  - {reason}")


def cmd_profile_derive(uc, args) -> None:
    try:
        report = uc.derive_profile_draft(args.manual_id)
    except GenerateError as e:
        print(f"profile-derive failed: {e}", file=sys.stderr)
        sys.exit(1)
    print("detected layout:")
    print(json.dumps(report.as_profile_layout_dict(), indent=2))
    print()
    print("notes:")
    for note in report.notes:
        print(f"  - {note}")
    if report.running_head_chapters:
        print()
        print("running-head chapters found:")
        for c in report.running_head_chapters:
            print(f"  - {c.label!r}: pages {c.page_start + 1}-{c.page_end}")

    out_path = Path("config") / "profiles" / f"{slugify(args.manual_id)}.draft.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"layout": report.as_profile_layout_dict()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print()
    print(f"draft written to {out_path} (not loaded automatically -- review before renaming to .json)")


def cmd_profile_classify_chapters(uc, args) -> None:
    try:
        reviews = uc.classify_running_head_chapters(args.manual_id)
    except GenerateError as e:
        print(f"profile-classify-chapters failed: {e}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for review in reviews:
        c, verdict, evidence = review.candidate, review.classification, review.evidence
        tag = "REAL " if verdict.is_real_chapter else "NOISE"
        renamed = "" if verdict.label == c.label else f" -> renamed to {verdict.label!r}"
        print(f"  [{tag}] {c.label!r}{renamed} -- {verdict.reason}")
        entries.append(
            {
                "original_label": c.label,
                "label": verdict.label,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "is_real_chapter": verdict.is_real_chapter,
                "reason": verdict.reason,
                "evidence": evidence,
            }
        )

    real_count = sum(1 for e in entries if e["is_real_chapter"])
    print()
    print(f"{real_count} of {len(entries)} candidate(s) look like real chapters")

    out_path = Path("workspace") / args.manual_id / "chapter_allowlist.review.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"candidates": entries}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print()
    print(f"unreviewed AI output written to {out_path} (not loaded automatically)")
    print(
        "review it -- edit is_real_chapter/label for any candidate the AI got wrong -- then run: "
        f"specgen.py profile-confirm-chapters {args.manual_id}"
    )


def cmd_profile_derive_toc_chapters(uc, args) -> None:
    try:
        candidates = uc.derive_toc_chapters(args.manual_id)
    except GenerateError as e:
        print(f"profile-derive-toc-chapters failed: {e}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for c in candidates:
        print(f"  {c.label!r} -- printed page {c.printed_page} (pages {c.page_start + 1}-{c.page_end})")
        entries.append(
            {
                "original_label": c.label,
                "label": c.label,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "is_real_chapter": True,
                "reason": f"found in the document's own printed table of contents (page {c.printed_page})",
                "evidence": c.subsection_evidence,
            }
        )

    print()
    print(f"{len(entries)} chapter(s) found in the printed table of contents")

    out_path = Path("workspace") / args.manual_id / "chapter_allowlist.review.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"candidates": entries}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print()
    print(f"deterministic TOC parse written to {out_path} (not loaded automatically)")
    print(
        "review it -- flip is_real_chapter to false for any chapter you don't want generated -- "
        f"then run: specgen.py profile-confirm-chapters {args.manual_id}"
    )


def cmd_profile_auto(uc, args) -> None:
    resolution = uc.resolve_manual_profile(args.manual_id)
    if resolution.status == "ready":
        print(f"ready: profile={resolution.profile_id!r}, chapters resolved -- generate can run directly")
        return

    print(f"needs review: profile={resolution.profile_id!r} (new: {resolution.profile_is_new})")
    if resolution.layout is not None:
        print("detected layout:")
        print(json.dumps(resolution.layout, indent=2))
    for note in resolution.notes:
        print(f"  - {note}")
    if resolution.toc_chapters:
        print()
        print("chapters found in the printed table of contents:")
        for c in resolution.toc_chapters:
            print(f"  - {c.label!r}: pages {c.page_start + 1}-{c.page_end}")
    if resolution.running_head_candidates:
        print()
        print("running-head candidates (unreviewed):")
        for c in resolution.running_head_candidates:
            print(f"  - {c.label!r}: pages {c.page_start + 1}-{c.page_end}")
    print()
    print(
        "review the above, then call UseCases.activate_derived_profile(...) "
        "(via the web UI's Confirm & Activate, or a script) to activate it."
    )


def cmd_profile_confirm_chapters(uc, args) -> None:
    review_path = Path("workspace") / args.manual_id / "chapter_allowlist.review.json"
    if not review_path.exists():
        print(
            f"no review file at {review_path} -- run profile-classify-chapters first",
            file=sys.stderr,
        )
        sys.exit(1)
    data = json.loads(review_path.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    chapters = [
        ConfirmedChapter(label=c["label"], page_start=c["page_start"], page_end=c["page_end"])
        for c in candidates
        if c["is_real_chapter"]
    ]
    try:
        uc.confirm_chapter_allowlist(args.manual_id, chapters)
    except ChapterAllowlistError as e:
        print(f"profile-confirm-chapters failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"activated {len(chapters)} of {len(candidates)} candidate(s) for {args.manual_id}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="specgen")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources")

    p = sub.add_parser("add-source")
    p.add_argument("--manual-id", required=True)
    p.add_argument("--maker", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--source-url", default="")
    p.add_argument("--retrieved-at", default="")
    p.add_argument("--markets", default="")
    p.add_argument("--license-state", default="unreviewed")

    p = sub.add_parser("generate")
    p.add_argument("manual_id")
    p.add_argument("--chapter", default=None)

    p = sub.add_parser("status")
    p.add_argument("manual_id")
    p.add_argument("--chapter", default=None)

    p = sub.add_parser("publish")
    p.add_argument("manual_id")
    p.add_argument("--chapter", required=True)
    p.add_argument("--allow-restricted", action="store_true")

    p = sub.add_parser("profile-fit")
    p.add_argument("manual_id")
    p.add_argument("--profile", required=True)
    p.add_argument("--chapter", default=None)

    p = sub.add_parser("profile-derive")
    p.add_argument("manual_id")

    p = sub.add_parser("profile-classify-chapters")
    p.add_argument("manual_id")

    p = sub.add_parser("profile-derive-toc-chapters")
    p.add_argument("manual_id")

    p = sub.add_parser("profile-confirm-chapters")
    p.add_argument("manual_id")

    p = sub.add_parser("profile-auto")
    p.add_argument("manual_id")

    args = parser.parse_args()
    uc = build_use_cases()

    try:
        {
            "sources": cmd_sources,
            "add-source": cmd_add_source,
            "generate": cmd_generate,
            "status": cmd_status,
            "publish": cmd_publish,
            "profile-fit": cmd_profile_fit,
            "profile-derive": cmd_profile_derive,
            "profile-classify-chapters": cmd_profile_classify_chapters,
            "profile-derive-toc-chapters": cmd_profile_derive_toc_chapters,
            "profile-confirm-chapters": cmd_profile_confirm_chapters,
            "profile-auto": cmd_profile_auto,
        }[args.command](uc, args)
    except ValidationError as e:
        print(f"invalid input: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
