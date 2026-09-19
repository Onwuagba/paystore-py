# Contributing

Thank you for contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run tests: `poetry run pytest`
6. Submit a pull request

## Code Style

- Use Black for formatting
- Follow PEP 8
- Add type hints
- Write docstrings

## Releasing (maintainers)

1. Bump the version in `pyproject.toml` and `paystore/__version__.py` (kept in sync).
2. Update `CHANGELOG.md`.
3. Merge to `main`, then create a GitHub Release with tag `vX.Y.Z` matching the version.
4. Publishing `.github/workflows/publish.yml` builds and publishes to PyPI via
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — no token needed in CI,
   but the PyPI project must have this repo/workflow (`publish.yml`) registered as a
   trusted publisher first, under a `pypi` GitHub Environment.
