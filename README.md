# GitHub Actions CI/CD Platform

A reusable GitHub Actions platform for Python services: shared CI, security
scanning, signed container releases, and environment-gated deployments —
defined once as **reusable workflows** (`workflow_call`) plus a **composite
action**, and consumed by a sample service in this repo.

> Platform engineering goal: application repos should need ~15 lines of
> YAML to get lint + tests + coverage, three security scanners, an
> SBOM-attested, cosign-signed container image, and a gated deploy.

## Layout

```
.github/
  workflows/
    reusable-ci-python.yml      # matrix CI: ruff + pytest + coverage
    reusable-docker-build.yml   # Buildx -> GHCR, SBOM, cosign signing
    reusable-security-scan.yml  # Trivy + gitleaks + pip-audit + dependency review
    reusable-release.yml        # semver from conventional commits + GitHub Release
    service-ci.yml              # caller: sample service PR/push pipeline
    service-release.yml         # caller: tag/manual release pipeline
    service-deploy.yml          # caller: environment-gated manual deploy
  actions/
    setup-python-app/           # composite action: Python + pip cache + deps
  dependabot.yml                # pip + github-actions + docker updates
service/                        # sample consumer (FastAPI app + tests + Dockerfile)
```

## Reusable workflow catalog

### `reusable-ci-python.yml` — Python CI

Runs a version matrix with ruff linting and pytest, uploading an XML
coverage report per Python version.

| Input | Type | Default | Description |
|---|---|---|---|
| `python-versions` | string | `["3.11", "3.12"]` | JSON array of versions for the matrix |
| `working-directory` | string | `.` | Directory containing the project |
| `requirements-file` | string | `requirements.txt` | Runtime deps (relative to working dir) |
| `dev-requirements-file` | string | `requirements-dev.txt` | Dev deps (relative to working dir) |
| `run-lint` | boolean | `true` | Run `ruff check` |
| `lint-paths` | string | `.` | Paths passed to ruff |
| `run-coverage` | boolean | `true` | Collect coverage and upload the artifact |
| `coverage-source` | string | `app` | Package/path measured by coverage |
| `pytest-args` | string | `""` | Extra pytest arguments |
| `runs-on` | string | `ubuntu-latest` | Runner label |

Outputs: none (results are the job status + coverage artifacts).

Uses the bundled composite action
[`.github/actions/setup-python-app`](.github/actions/setup-python-app/action.yml)
via a relative path, which resolves against the caller's checked-out repo —
when consuming cross-repo, vendor that one small folder into your repo.

### `reusable-docker-build.yml` — Build, SBOM & sign

Builds with Buildx, computes tags/labels with `docker/metadata-action`,
attaches BuildKit SBOM + provenance attestations, emits a standalone SPDX
SBOM artifact, and — only when `push: true` — pushes to GHCR and signs the
image digest with **cosign keyless signing** (Sigstore, via the workflow's
OIDC identity; no private keys stored anywhere).

| Input | Type | Default | Description |
|---|---|---|---|
| `image-name` | string | — (required) | Fully qualified image, e.g. `ghcr.io/owner/app` |
| `context` | string | `.` | Build context |
| `dockerfile` | string | `Dockerfile` | Dockerfile, relative to context |
| `platforms` | string | `linux/amd64` | Buildx target platforms |
| `push` | boolean | `false` | Push + sign instead of build-only |
| `tags` | string | branch/PR/semver/sha set | metadata-action tag rules |
| `build-args` | string | `""` | Newline-separated build args |
| `sign-image` | boolean | `true` | Cosign-sign the pushed image |
| `runs-on` | string | `ubuntu-latest` | Runner label |

| Output | Description |
|---|---|
| `image-digest` | Digest of the built image (`sha256:...`) |
| `image-tags` | Tags produced by metadata-action |
| `image-version` | Version label from metadata-action |

Caller must grant: `contents: read`, `packages: write`, `id-token: write`,
`attestations: write` when pushing.

### `reusable-security-scan.yml` — Security scanning

| Scanner | What it catches |
|---|---|
| Trivy (fs) | Known CVEs in dependencies/IaC; SARIF uploaded to the Security tab |
| gitleaks | Secrets committed anywhere in git history |
| pip-audit | Vulnerable Python packages (optional, `run-pip-audit`) |
| Dependency review | Risky dependency changes on PRs (PR events only) |

| Input | Type | Default | Description |
|---|---|---|---|
| `working-directory` | string | `.` | Directory to scan |
| `fail-on-severity` | string | `HIGH` | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` threshold that fails the job |
| `trivy-ignore-unfixed` | boolean | `true` | Only report fixable vulnerabilities |
| `upload-sarif` | boolean | `true` | Upload SARIF to the Security tab |
| `run-pip-audit` | boolean | `false` | Also run pip-audit |
| `requirements-file` | string | `requirements.txt` | pip-audit target (relative to working dir) |
| `runs-on` | string | `ubuntu-latest` | Runner label |

Caller must grant: `contents: read`, `security-events: write`,
`pull-requests: write`.

### `reusable-release.yml` — Version, changelog, release

Computes the next semantic version, generates a changelog grouped by
conventional-commit type, creates the tag, and publishes a GitHub Release
via the `gh` CLI.

| Input | Type | Default | Description |
|---|---|---|---|
| `tag` | string | `""` | Explicit tag (e.g. `v1.4.0`); overrides bumping |
| `bump` | string | `auto` | `auto`/`major`/`minor`/`patch` |
| `prerelease` | boolean | `false` | Mark as pre-release |
| `generate-changelog` | boolean | `true` | Grouped changelog vs. GitHub auto-notes |
| `target` | string | caller SHA | Commit the tag is created on |
| `runs-on` | string | `ubuntu-latest` | Runner label |

| Output | Description |
|---|---|
| `tag` | Tag created/released (e.g. `v1.4.0`) |
| `version` | Version without the leading `v` |

`auto` bump rules: breaking change (`type!:` or `BREAKING CHANGE:`) →
major, `feat:` → minor, everything else → patch.

Caller must grant: `contents: write`.

## Use it from another repository

Pin to a **major version tag** of this repo (create the `v1` tag on a
release of this platform repo), or better, to a full commit SHA — see the
hardening notes below.

```yaml
# .github/workflows/ci.yml in YOUR repo
name: CI
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write
  pull-requests: write

jobs:
  test:
    uses: venkateswarlu429/github-actions-cicd-platform/.github/workflows/reusable-ci-python.yml@v1
    with:
      working-directory: .
      python-versions: '["3.11", "3.12"]'

  security:
    uses: venkateswarlu429/github-actions-cicd-platform/.github/workflows/reusable-security-scan.yml@v1
    with:
      fail-on-severity: "HIGH"
      run-pip-audit: true

  release-image:
    if: github.ref_type == 'tag'
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    uses: venkateswarlu429/github-actions-cicd-platform/.github/workflows/reusable-docker-build.yml@v1
    with:
      image-name: ghcr.io/${{ github.repository_owner }}/my-app
      context: .
      push: true
```

## Sample consumer: `service/`

A minimal FastAPI service (`/`, `/healthz`, `/greet/{name}`) with pytest
tests and a non-root, health-checked Dockerfile. It consumes the platform
through three caller workflows:

- **`service-ci.yml`** — PRs and pushes: reusable CI + security scan, plus a
  build-only (never push) Docker check on PRs.
- **`service-release.yml`** — on `v*.*.*` tag pushes or manual dispatch:
  reusable release, then build + push + cosign-sign with semver tags.
- **`service-deploy.yml`** — manual dispatch to `staging`/`production`
  GitHub Environments (required reviewers gate production), serialized by a
  per-environment concurrency guard, deploying an exact tag or digest. The
  rollout step is a documented placeholder; a fully commented **AWS OIDC**
  variant (IAM role assumption via `aws-actions/configure-aws-credentials`,
  all ARNs/regions via repository variables — no account IDs in code) sits
  at the bottom of the file.

Run the service locally:

```bash
cd service
pip install -r requirements.txt -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

## Security hardening notes

- **Pin actions to full commit SHAs** in production (`uses: actions/checkout@<sha> # v4`), with Dependabot (configured in this repo) proposing bumps. Tags are mutable; SHAs are not.
- **Least-privilege `permissions:` everywhere.** Every workflow here declares an explicit block; reusable workflows request only what they need, and callers cannot grant more than they declare — the effective token is the more restrictive of the two.
- **OIDC over stored secrets.** Cosign signs keylessly with the workflow's OIDC identity (Sigstore Fulcio/Rekor transparency log); the AWS deploy sketch assumes an IAM role the same way. The only token used is the automatic, short-lived `GITHUB_TOKEN`.
- **Supply-chain evidence.** Release images carry BuildKit SBOM + provenance attestations, a downloadable SPDX SBOM artifact, and a cosign signature verifiable with `cosign verify ghcr.io/<owner>/sample-service:<tag>`.
- **Environment protection.** Production deploys sit behind GitHub Environment required reviewers and a no-cancel concurrency guard, so a deploy can never be silently replaced mid-flight.
- **PRs can't publish.** The Docker workflow defaults to build-only; pushing and signing require the explicit `push: true` input that PR callers never pass.

## What this demonstrates

- Reusable workflows (`workflow_call`) with typed inputs/outputs/secrets discipline and least-privilege tokens
- Composite actions for shared setup logic (pip caching, dependency install)
- Matrix testing, coverage artifacts, and ruff in a single reusable CI contract
- Container supply-chain security: Buildx cache, metadata-driven tagging, SBOM (BuildKit + Syft/Anchore), provenance, cosign keyless signing
- Layered scanning: Trivy SARIF → Security tab, gitleaks, pip-audit, dependency review, with a configurable fail threshold
- Conventional-commit semantic versioning and automated GitHub Releases
- Environment-gated, concurrency-safe deployments with OIDC-based cloud auth
- Dependabot grouping for Actions, pip, and Docker base images

## License

MIT — © 2026 Venkateswarlu Maddula. See [LICENSE](LICENSE).
