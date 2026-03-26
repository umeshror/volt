# Contributing to VOLT

Thank you for your interest in contributing to VOLT. We operate under rigorous engineering standards to ensure the framework remains highly performant, secure, and reliable for resource-constrained IoT devices. 

This guide outlines our engineering culture, development lifecycle, and the standards required for all code merging into the `main` branch.

---

## 📑 Table of Contents
1. [Code of Conduct](#1-code-of-conduct)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [Developer Certificate of Origin (DCO)](#3-developer-certificate-of-origin-dco)
4. [Engineering Standards](#4-engineering-standards)
5. [Local Development Environment](#5-local-development-environment)
6. [Conventional Commits](#6-conventional-commits)
7. [Pull Request Lifecycle](#7-pull-request-lifecycle)

---

## 1. Code of Conduct
We enforce a strict [Code of Conduct](CODE_OF_CONDUCT.md). All contributors are expected to maintain professional, blameless, and constructive communication at all times. 

## 2. Security Vulnerabilities
**Do not file public issues for security vulnerabilities.** 
If you discover a vulnerability (e.g., an unauthenticated OTA vector, buffer overflow in the network stack), please email `sarukumesh@gmail.com`. We will respond within 48 hours with a coordinated disclosure plan.

## 3. Developer Certificate of Origin (DCO)
All contributions must be signed off to certify that you have the right to submit the code under the project's license. 
Ensure every commit includes a `Signed-off-by` line:
```bash
git commit -s -m "feat(connectivity): add TLS support for MQTT"
```

## 4. Engineering Standards

### 4.1. MicroPython Constraints
Code targeting the `volt/` package runs on embedded hardware. Reviewers will harshly reject PRs that:
- **Block the async loop:** All I/O must use `uasyncio`. Synchronous delays (`time.sleep`) are strictly prohibited.
- **Trigger excessive GC pauses:** Minimize allocations in hot paths (e.g., sensor polling, network loops). Pre-allocate buffers and reuse data structures where possible.
- **Add external dependencies:** The core framework must remain dependency-free.

### 4.2. Testing & Coverage
- **100% Branch Coverage:** All new features or bug fixes must include corresponding tests in `tests/`. PRs dropping total coverage below 95% will be automatically rejected by CI.
- **Hardware Integration Tests:** Core modifications heavily impacting scheduling or networking must be accompanied by hardware test validation logs.

### 4.3. Code Quality
- All Python code must be typed using standard `typing`.
- We use `black` (formatting), `ruff` (linting), and `mypy` (static type checking).
- Architecture changes should be preempted by an Architecture Decision Record (ADR) in `docs/architecture/`.

---

## 5. Local Development Environment

We utilize `tox` and `pre-commit` to guarantee reproducible environments.

### Requirements
- Python 3.10+
- `git`

### Bootstrap
```bash
git clone https://github.com/your-org/volt.git
cd volt

# Set up the isolated environment and install hooks
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

### Running Checks
Before pushing, ensure all checks pass natively:
```bash
pytest tests/ -v --cov=volt
black volt/ volt_cli/ tests/
ruff check volt/ volt_cli/
mypy volt_cli/
```

---

## 6. Conventional Commits
We strictly adhere to [Conventional Commits](https://www.conventionalcommits.org/). This enables automated changelog generation and semantic versioning.

**Format:**
```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

**Allowed Types:**
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Formatting, missing semi colons, etc
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools

**Examples:**
- `feat(mqtt): implement QoS 1 delivery guarantees`
- `fix(scheduler): resolve GC memory leak in _when_loop`
- `docs(readme): update dependency installation instructions`

---

## 7. Pull Request Lifecycle

1. **Issue Triaging:** Ensure there is an open issue for your work. Unsolicited architectural refactors will be closed.
2. **Draft PR:** Open a Draft PR early to align on implementation details. Link to the relevant issue.
3. **CI Pipeline:** Push your code. GitHub Actions will run the test matrix (OSes and Python versions), linting, and calculating coverage metrics.
4. **Code Review:** A core maintainer will review the code. We utilize iterative, blameless reviews. Address all comments.
5. **Squash and Merge:** Once approved and CI is green, the PR will be squash-merged into `main`. The commit message must follow the Conventional Commits format.

---
Thank you for elevating the engineering quality of VOLT. Let's build something exceptional.
