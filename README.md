# Ephemeral Environment Platform

![CI](https://github.com/anthonydip/ephemeral-env-platform/workflows/CI/badge.svg)

🚧 **Work in Progress** 🚧

Automated ephemeral preview environments for pull requests using Kubernetes, Python, and AWS.

## What This Does

Automatically creates isolated, full-stack preview environments for every pull request, then auto-destroys them when the PR closes.

## Problem It Solves

- Developers share one staging environment → conflicts when multiple PRs are open
- Reviewing PRs without seeing them live → harder to spot bugs
- Manual environment setup → wastes time
- QA/Product can't test features before merge → delays feedback

## Solution

Every PR automatically gets its own live environment with a unique URL. When the PR closes, the environment auto-deletes.

## Tech Stack

- **Python** - Automation/orchestration logic
- **Kubernetes (K3s)** - Container orchestration
- **Docker** - Containerization
- **AWS EC2** - Cloud hosting
- **GitHub Actions** - CI/CD trigger

## Current Status

- [ ] Phase 1: Local K8s Setup
- [ ] Phase 2: Core Automation
- [ ] Phase 3: Move to AWS
- [ ] Phase 4: GitHub Integration
- [ ] Phase 5: Polish & Documentation

## Project Goals

This project demonstrates:

- Cloud infrastructure automation
- Kubernetes orchestration
- CI/CD pipeline design
- Platform engineering concepts

---

_More documentation coming as the project develops._
