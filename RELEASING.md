# Releasing, and quirks of this pipeline

This repo is set up as a template for other Tildagon apps: CI (lint + static analysis +
tests) gates every PR, and pushes to `main` run `semantic-release` to cut a versioned
GitHub release the [app store](https://apps.badge.emfcamp.org/) picks up automatically.

None of this is documented in one place upstream, and several parts are non-obvious or
outright surprising. This file is the "read before you copy this repo" doc.

## How a release happens

1. Commits on `main` must follow [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `chore:`, `ci:`, ...). `feat:` bumps minor, `fix:` bumps patch,
   `chore:`/`ci:`/`docs:`/etc. don't trigger a release at all. A footer containing
   `BREAKING CHANGE:` bumps major.
2. On push to `main`, once `lint` / `static-analysis` / `test` all pass, the `release` job
   runs `semantic-release`, which:
   - figures out the next version from commits since the last release,
   - runs `scripts/stamp_version.py <version>` to rewrite the `version` field in
     `tildagon.toml`,
   - commits that change back to `main` (message `chore(release): X.Y.Z [skip ci]`),
   - tags it `vX.Y.Z` and creates a GitHub Release.

## Quirks / gotchas we hit setting this up

### The app store expects one app per repo, at the repo root

`app.py` and `tildagon.toml` are expected at the **repository root** - this is undocumented
but confirmed by asking the docs directly and by every real published app following this
shape. A monorepo of multiple apps (subdirectories, each with their own `tildagon.toml`)
is **not** supported. If this repo is a dev monorepo with several apps, each one that gets
published needs splitting out into its own repo, structured like this one.

### The repo must be public

Private repos are invisible to the app store, full stop. There's no partial/preview
publish option.

### The store needs the `tildagon-app` GitHub topic

Set on the repo (Settings -> General -> Topics, or `gh repo edit --add-topic tildagon-app`).
Without it the store won't discover the repo even if everything else is correct.

### `tildagon.toml`'s `version` field is not derived from the git tag

The store's displayed "Version" comes from parsing `tildagon.toml` **at the released
commit**, not from the `vX.Y.Z` tag name. If you only tag releases and never update the
file, the store keeps showing a stale version forever. This is why `@semantic-release/git`
commits the stamped `tildagon.toml` back to `main` as part of every release - skipping that
step silently defeats the point of automating versioning.

### The app's real ID is not `github/<owner>/<repo>/<sha>`

That format is what shows up for **failed** apps on the store's `/errors/` page (it's
useful for finding *why* an app failed to import), but successfully published apps get an
unrelated short numeric ID assigned by the store (e.g. `34431234`), used as
`https://apps.badge.emfcamp.org/apps/<id>/`. Don't try to compute the URL from the repo/tag
- find it by searching `https://apps.badge.emfcamp.org/latest` (or the category page) for
the app's name after a release.

### The store is a statically-generated site, not a live API

`apps.badge.emfcamp.org` is an Astro static build - there's no listing/search API to query.
"Should show up within ~15 minutes" refers to a periodic rebuild, not a live index. If an
app doesn't appear yet, check `/errors/` first (confirms it's not silently failing
validation) and `/latest` (newest apps, easiest place to spot a fresh, not-yet-common-ID
release) before assuming something's broken.

### Testing app.py needs firmware stubs

`app.py` imports badge-only modules (`app`, `app_components`, `events.input`,
`events.emote`, `system.eventbus`) that don't exist off-badge. `tests/badge_stubs/`
provides minimal stand-ins, and `tests/conftest.py` puts them on `sys.path` *before*
loading `app.py` - which it does via `importlib.util.spec_from_file_location` under the
module name `snake_app_under_test`, not `app`. This matters because the repo's own file is
also called `app.py` and does `import app` to reach the badge framework; if it were loaded
under the name `app`, that import would resolve to itself instead of the stub, and
recurse/fail.

### pytest chokes on the repo root's own `__init__.py`

The repo root has an `__init__.py` (required so the badge can `from .app import
SnakeApp`). If pytest's rootdir is the repo root, its `Package` collector tries to eagerly
import that `__init__.py` too - which fails outside the badge runtime with `ImportError:
attempted relative import with no known parent package`, even though no test references it.
Fix: `tests/pytest.ini` (not the root `pyproject.toml`) gives pytest a rootdir scoped to
`tests/`, away from the offending file. Always run tests as `pytest tests`, not bare
`pytest`, so this rootdir resolution kicks in correctly.

### bandit flags `random.choice`/`random.randrange` by default

Bandit's B311 check flags the standard `random` module as unsuitable for security-sensitive
use. For a snake game, it's just picking a food tile - not a security concern. Skipped via
`[tool.bandit] skips = ["B311"]` in `pyproject.toml`. If a future app under this template
*does* use randomness security-sensitively, don't blanket-copy this skip.

### `GITHUB_TOKEN` cannot push the version-bump commit once `main` is protected

This is the big one. Required-status-checks branch protection blocks **any** update to the
branch - PR merge or direct push - unless the pushed commit already has passing checks (or
the pusher has an explicit bypass). A fresh commit from `@semantic-release/git` has never
been checked, so it gets rejected. GitHub's default `GITHUB_TOKEN` is documented as
**unable** to bypass branch protection, by design (otherwise any workflow could route
around required checks). Some form of separate, bypass-capable identity is required for
this one push.

We deliberately did **not** use a personal PAT (ties the pipeline to one person's account -
breaks if they leave, rotates 2FA, etc.) or reach first for a GitHub App (more setup: app
creation, installation, JWT/installation-token minting per run). We used a **deploy key**
instead:

- It has no user or org identity attached - purely a repo-scoped SSH credential.
- It only grants git-level access (clone/push) - it can't call the REST API, so creating
  the actual GitHub Release (an API call, not a branch push) still uses the ordinary
  `GITHUB_TOKEN`; only the version-bump `git push` needs the key.
- Add it with write access, put the private half in the `DEPLOY_KEY` repo secret, and
  `actions/checkout`'s `ssh-key:` input handles cloning-and-configuring-push-over-SSH
  automatically - no manual git remote surgery needed.
- It must be added to the `main` branch ruleset's **bypass list** to actually skip required
  status checks. Classic branch protection doesn't support a granular bypass list (only a
  blanket "administrators bypass everything" toggle); this needs a **Ruleset**
  (Settings -> Rules -> Rulesets), not classic branch protection rules.

### Deploy keys can be disabled at the *org* level

`zemlab` had `deploy_keys_enabled_for_repositories: false` set org-wide, which rejects
*any* deploy key on *any* repo in the org with "Deploy keys are disabled for this
repository" - a repo-level error message for what is actually an org-level setting. Check
`gh api orgs/<org> --jq .deploy_keys_enabled_for_repositories` before assuming a deploy key
will just work; flipping it (`gh api orgs/<org> -X PATCH -F
deploy_keys_enabled_for_repositories=true`) is an org-wide policy change, worth calling out
explicitly rather than doing quietly.

## Template checklist for a new app repo

1. Copy `app.py`, `__init__.py`, `metadata.json`, `tildagon.toml`, `LICENSE`,
   `tests/`, `pyproject.toml`, `package.json`, `release.config.js`, `scripts/`,
   `.github/workflows/ci.yml`, and this file. Update `tildagon.toml` (name, description,
   author, url) and `metadata.json` for the new app; reset `version` to `0.0.0` or similar
   and let semantic-release take it from there.
2. Create the repo **public**, add the `tildagon-app` topic.
3. Generate a fresh deploy key per repo (don't reuse one across apps) and set it as that
   repo's `DEPLOY_KEY` secret.
4. Set up the `main` Ruleset: required checks `lint` / `static-analysis` / `test`, bypass
   actor = that repo's deploy key.
5. Use Conventional Commit messages on `main` from the first commit onward.
