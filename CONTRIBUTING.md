# Contributing to OrnisLab

Thanks for helping. These guidelines apply to every OrnisLab repository, unless a repository has its own `CONTRIBUTING.md`.

## Ways to contribute

- **Report a bug.** Open an issue with the version you used, what you expected and what happened instead.
- **Suggest an improvement.** Open an issue that describes the problem you want to solve before proposing a solution.
- **Improve detection content, integrations or docs.** Small, focused pull requests are the easiest to review.
- **Fix a bug or build a feature.** Look for issues labeled `good first issue` or `help wanted`.

Security problems are the exception: report them privately as described in [SECURITY.md](SECURITY.md).

## Before you open a pull request

1. For anything larger than a small fix, open or comment on an issue first so we can agree on the approach.
2. Fork the repository and create a branch from `main`.
3. Keep each pull request to one change, and add or update tests and documentation with it.
4. Make sure the project’s tests and linters pass locally.
5. Describe what changed and why, and link the related issue.

## Commit messages

We recommend [Conventional Commits](https://www.conventionalcommits.org/), for example:

```text
feat(recon): add MISP feed collector
fix(guard): handle empty alert payloads
docs: explain on-premises deployment
```

## Detection and intelligence content

- Never include real customer data, internal hostnames, credentials or non-public indicators.
- Map detections to MITRE ATT&CK techniques where it applies.
- Include a short note on known false positives and how the content was tested.

## Licensing

By contributing, you agree that your contribution is licensed under the license of the repository you are contributing to.

## Be respectful

Assume good intent, keep feedback about the work, and help keep OrnisLab a welcoming place for everyone.
