# Changelog fragments

Every pull request with a user-visible change must add one short fragment here.
Use the pull request number and the most specific type:

```text
changes/<pr-number>.<type>.md
```

Supported types are `breaking`, `feature`, `bugfix`, `deprecation`, `docs`, and
`security`. Write one sentence for users in the imperative voice and do not add
a heading or the version number.

Example:

```text
changes/123.feature.md
```

```markdown
Add named repositories for selecting shared index locations and devices.
```

Dependency updates marked `dependencies` do not require a fragment. Other
internal changes may omit one when a maintainer applies `skip-changelog` and
the pull request explains why.

Towncrier collects and removes fragments when a stable release is created.
Do not edit `CHANGELOG.md` directly.
