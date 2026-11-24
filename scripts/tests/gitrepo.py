"""Throwaway git repositories for tests that need the real git CLI."""

import contextlib
import os
import subprocess
from pathlib import Path

GIT_TEST_CONFIG = (
	"-c",
	"user.name=t",
	"-c",
	"user.email=t@t",
	"-c",
	"commit.gpgsign=false",
	"-c",
	"tag.gpgsign=false",
	"-c",
	"core.hooksPath=/dev/null",
)


def run_git(root, *args, check=True):
	"""Run git in `root` with a neutral identity and no hooks."""
	return subprocess.run(
		["git", *GIT_TEST_CONFIG, *args],
		cwd=root,
		check=check,
		capture_output=True,
		text=True,
	)


def write_files(root, **files):
	"""Write each keyword argument (slash-separated relative path) under `root`."""
	for relative, body in files.items():
		path = Path(root) / relative
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(body, encoding="utf-8")


def git_repo(root, **files):
	"""Initialise a repository in `root`, write `files` and stage them."""
	run_git(root, "init", "-q", "-b", "main")
	write_files(root, **files)
	run_git(root, "add", "-A")
	return Path(root)


@contextlib.contextmanager
def chdir(path):
	"""Temporarily change the working directory (tests run in-process)."""
	previous = os.getcwd()
	os.chdir(path)
	try:
		yield
	finally:
		os.chdir(previous)
