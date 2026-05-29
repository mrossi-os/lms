#!/usr/bin/env python3
"""Reassign orphaned Discussion Topic / Discussion Reply records to a placeholder user.

When a User is deleted, the `owner` of their Discussion Topics / Replies keeps
pointing at the now-missing user. Frappe's core `DiscussionReply.after_insert`
renders `discussions/sidebar.html`, which resolves `topic.owner` via
`get_value("User", owner)` and feeds it to the `avatar()` macro. With a deleted
owner this raises a Jinja `UndefinedError` ("'dict object' has no attribute
'name'") -> HTTP 500, so nobody can reply on those threads anymore.

This one-off script does NOT delete anything: it finds every topic/reply whose
`owner` no longer exists in `tabUser` and reassigns `owner` to a single
placeholder user (disabled, full_name "Utente eliminato"). The avatar resolves,
the 500 is gone, and the original reply text stays intact and visible.

Usage (from the host, dry-run first):
    docker compose -f docker/docker-compose.yml exec frappe \
        bash -lc 'cd /home/frappe/bench-data/frappe-bench && \
        ./env/bin/python /workspace/scripts/fix_orphan_discussions.py --site lms.localhost'

Add --apply to actually write changes:
        ... --site lms.localhost --apply

By default the script runs in dry-run mode and only prints a summary.
"""

from __future__ import annotations

import argparse
import sys

import frappe

PLACEHOLDER_EMAIL = "deleted-user@deleted.invalid"
PLACEHOLDER_NAME = "Utente eliminato"

DOCTYPES = ("Discussion Topic", "Discussion Reply")


def find_orphans(doctype: str) -> list[dict]:
	"""Return [{name, owner}] for records whose owner is missing from tabUser."""
	return frappe.db.sql(
		f"""
		SELECT d.name AS name, d.owner AS owner
		FROM `tab{doctype}` d
		LEFT JOIN `tabUser` u ON u.name = d.owner
		WHERE u.name IS NULL
		""",
		as_dict=True,
	)


def ensure_placeholder_user(email: str, apply: bool) -> None:
	"""Create the disabled placeholder user if it doesn't exist yet."""
	if frappe.db.exists("User", email):
		print(f"  placeholder user already exists: {email}")
		return

	if not apply:
		print(f"  [dry-run] would create placeholder user: {email} ({PLACEHOLDER_NAME})")
		return

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = PLACEHOLDER_NAME
	user.enabled = 0
	user.user_type = "Website User"
	user.flags.ignore_permissions = True
	user.flags.no_welcome_mail = True
	user.insert(ignore_permissions=True)
	print(f"  created placeholder user: {email} ({PLACEHOLDER_NAME})")


def reassign(doctype: str, orphans: list[dict], email: str, apply: bool) -> None:
	by_owner: dict[str, int] = {}
	for row in orphans:
		by_owner[row["owner"]] = by_owner.get(row["owner"], 0) + 1

	print(f"\n{doctype}: {len(orphans)} orphaned record(s) across {len(by_owner)} missing owner(s)")
	for owner, count in sorted(by_owner.items()):
		print(f"  - {owner or '(empty)'}: {count}")

	if not apply:
		print(f"  [dry-run] would reassign owner -> {email} for {len(orphans)} record(s)")
		return

	for row in orphans:
		frappe.db.set_value(doctype, row["name"], "owner", email, update_modified=False)
	print(f"  reassigned owner -> {email} for {len(orphans)} record(s)")


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--site", required=True, help="Frappe site name (e.g. lms.localhost)")
	parser.add_argument(
		"--sites-path",
		default="sites",
		help="Path to the bench 'sites' directory (default: sites, i.e. run from bench root)",
	)
	parser.add_argument("--placeholder", default=PLACEHOLDER_EMAIL, help="Placeholder user email")
	parser.add_argument("--apply", action="store_true", help="Persist changes (default: dry-run)")
	args = parser.parse_args(argv)

	frappe.init(site=args.site, sites_path=args.sites_path)
	frappe.connect()

	try:
		all_orphans = {dt: find_orphans(dt) for dt in DOCTYPES}
		total = sum(len(v) for v in all_orphans.values())

		if not total:
			print("No orphaned discussions found. Nothing to do.")
			return 0

		print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}  Site: {args.site}")
		ensure_placeholder_user(args.placeholder, args.apply)

		for dt in DOCTYPES:
			reassign(dt, all_orphans[dt], args.placeholder, args.apply)

		if args.apply:
			frappe.db.commit()
			print("\nChanges committed.")
		else:
			print("\nDry-run only. Re-run with --apply to persist.")
		return 0
	finally:
		frappe.destroy()


if __name__ == "__main__":
	sys.exit(main())
