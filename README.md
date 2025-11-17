# Ephemeral Environment Platform

> Automated ephemeral Kubernetes preview environments for pull requests

[![CI](https://github.com/anthonydip/ephemeral-env-platform/workflows/CI/badge.svg)](https://github.com/anthonydip/ephemeral-env-platform/actions)

A Python CLI and GitHub Action that automates the creation and deletion of isolated preview environments in Kubernetes. Each pull request gets its own namespace with deployed services, accessible via unique URLs through Traefik ingress routing.

<p align="center" width="100%">
  <video src="https://github.com/user-attachments/assets/097660b5-8a3c-44e9-9079-b3a74e8cb91c" width="80%" controls></video>
</p>

_Watch a full development cycle: Opening a PR triggers automated builds, Kubernetes deployment, and posts preview URLs in under 90 seconds._

**Related:** [GitHub Action](https://github.com/anthonydip/ephemeral-env-action) • [Demo App](https://github.com/anthonydip/ephemeral-app-demo)

## The Problem

In typical development workflows, teams share a single staging environment. This creates bottlenecks:

- Multiple PRs waiting to be tested one at a time
- Deployments overriding each other
- No easy way for reviewers to see changes live
- QA blocked by environment conflicts

## The Solution

This platform deploys each PR to an isolated Kubernetes namespace with path-based routing. PR #123 gets deployed to `http://your-host/pr-123/`, completely separate from PR #124 at `http://your-host/pr-124/`. When the PR closes, the entire namespace is deleted automatically.

## Quick Start

### Using the GitHub Action

Add the [GitHub Action](https://github.com/anthonydip/ephemeral-env-action) to your repository:

```yaml
# .github/workflows/preview.yml
name: Preview Environments

on:
  pull_request:
    types: [opened, synchronize, reopened, closed]

jobs:
  manage-preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: anthonydip/ephemeral-env-action@v1
        with:
          action: ${{ github.event.action == 'closed' && 'delete' || 'create' }}
          pr-number: ${{ github.event.pull_request.number }}
          kubeconfig: ${{ secrets.KUBECONFIG }}
          ingress-host: ${{ secrets.INGRESS_HOST }}
```

See the [action documentation](https://github.com/anthonydip/ephemeral-env-action) for complete setup instructions.

### Using the CLI

Install and run directly:

```bash
pip install git+https://github.com/anthonydip/ephemeral-env-platform

# Create environment for PR #123
ephemeral create 123 --config .ephemeral-config.yaml

# Delete environment
ephemeral delete 123
```

## How It Works

The platform automates the full lifecycle:

1. Reads your service configuration from `.ephemeral-config.yaml`
2. Creates an isolated Kubernetes namespace `pr-<number>`
3. Deploys your services from Jinja2 templates
4. Configures Traefik ingress with path-based routing (`/pr-123/*`)
5. Posts a GitHub comment on the PR with the preview URLs
6. Automatically cleans up everything when the PR closes

## Configuration

Create `.ephemeral-config.yaml` in your repository:

```yaml
services:
  - name: frontend
    image: mycompany/frontend:pr-123
    port: 80
    ingress:
      enabled: true
      path: "/"

  - name: backend
    image: mycompany/backend:pr-123
    port: 3000
    ingress:
      enabled: true
      path: "/api"
    env:
      DATABASE_URL: postgres://db:5432/myapp
      NODE_ENV: production
```

The platform deploys these as Kubernetes Deployments, Services, and Ingress resources. See [examples/](examples/) for more configurations.

**Note:** When using the [GitHub Action](https://github.com/anthonydip/ephemeral-env-action), you can use `{{PR_NUMBER}}` template variables for dynamic image tags. See the action documentation for details.

## Prerequisites

- Kubernetes cluster (K3s, GKE, EKS, AKS, etc.)
- Traefik ingress controller
- Python 3.9+
- Docker images for your services

## Architecture

Built with modular Python components:

- Kubernetes API client with input validation
- Jinja2-based template rendering for manifests
- GitHub integration PR comments
- Structured logging with operation tracking

**Kubernetes Resources Created:**

- Namespace (isolation boundary)
- Deployments (application containers)
- Services (internal networking)
- Ingress (external routing via Traefik)
- Middleware (Traefik path prefix stripping)

**Template System:**
All Kubernetes manifests are generated from Jinja2 templates in `automation/templates/`, allowing customization without changing code.

## Installation

```bash
git clone https://github.com/anthonydip/ephemeral-env-platform
cd ephemeral-env-platform
pip install -e .
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run integration tests (requires Kubernetes cluster)
pytest tests/test_integration.py -v

# Skip integration tests
pytest tests/ -v -m "not integration"

# Code formatting
black .
ruff check .
```

## Cloud Provider Support

Works with any Kubernetes cluster:

- AWS (EC2, EKS)
- Google Cloud (GKE, Compute Engine)
- Azure (AKS, VMs)
- DigitalOcean Kubernetes
- On-premises clusters
- Local development (Minikube, kind, k3d)

## CLI Reference

```bash
# Create environment
ephemeral create <pr-number> \
  --config .ephemeral-config.yaml \
  --templates automation/templates/ \
  --log-level INFO

# Delete environment
ephemeral delete <pr-number>

# Additional options
--skip-github        # Skip GitHub PR comment integration
--log-format json    # Output format: text, structured, or json
```
