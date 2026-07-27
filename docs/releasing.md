# Release process

VidXP publishes prerelease and stable packages from `main`. The old `release`
branch is retained only as historical ancestry for `v0.1.0`; it is not an active
publication branch.

## Prereleases

A release-relevant merge to `main` runs CI, lets Python Semantic Release
calculate the next version, creates a `b` prerelease tag and GitHub prerelease,
builds the distributions, and publishes them to TestPyPI. Commits that do not
require a semantic version bump do not publish a package.

Pending Towncrier fragments remain in `changes/` during prereleases.

## Stable releases

1. Confirm that `main` is green and its TestPyPI prerelease is usable.
2. Confirm that every user-visible merged pull request has an accurate fragment.
3. Run the **Release (main → PyPI)** workflow.
4. Approve the protected `pypi` environment deployment.
5. Confirm the new tag, GitHub release, PyPI package, and emptied pending
   fragment set.

The workflow always checks out `main`. Python Semantic Release is the only
version authority. During its build step, Towncrier receives that calculated
version, updates `CHANGELOG.md`, and removes the released fragments before the
release commit and tag are created.

Release and CI tools are declared once in `utils/build-requirements.txt`. Do not
duplicate their versions in workflow files.
