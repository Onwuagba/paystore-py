# Contributing

Thank you for contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run tests: `poetry run pytest`
6. Submit a pull request

## Smoke testing against real sandboxes

`pytest` never makes real network calls — everything is mocked. Before a
release, run `scripts/smoke_test.py` with real sandbox credentials to
catch anything the mocks can't (wrong field names, wrong URLs, wrong
status codes against a provider's actual API):

```bash
export PAYSTACK_SECRET_KEY=sk_test_...
export FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-...
export STRIPE_SECRET_KEY=sk_test_...
export REMITA_SECRET_KEY=...  # plus REMITA_API_SECRET/MERCHANT_ID/SERVICE_TYPE_ID

python scripts/smoke_test.py
```

Only providers with credentials set are tested; the rest are skipped.
It never moves money (no `charge_authorization` call) and refuses to
run against anything that looks like a live key.

## Code Style

- Use Black for formatting
- Follow PEP 8
- Add type hints
- Write docstrings

## Releasing (maintainers)

`paystore` core and `paystore-django` are separate PyPI projects released
independently, each with its own version and git tag.

### paystore (core)

1. Bump the version in `pyproject.toml` and `paystore/__version__.py` (kept in sync).
2. Update `CHANGELOG.md`.
3. Merge to `main`, then create a GitHub Release with tag `vX.Y.Z` matching the version.
4. `.github/workflows/publish.yml` builds and publishes to PyPI via
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) on release — no token
   needed in CI, but the PyPI project must have this repo/workflow (`publish.yml`)
   registered as a trusted publisher first, under a `pypi` GitHub Environment.
5. Manual fallback if Actions isn't available: `poetry build && poetry publish`
   from the repo root (needs `poetry config pypi-token.pypi <token>` set locally first).

### paystore-django

Released the same way, from the `paystore-django/` directory, with its own
version in `paystore-django/pyproject.toml` and a `paystore-django-vX.Y.Z`
tag (to avoid colliding with core's `vX.Y.Z` tags in the same repo). It
depends on a published `paystore` version (see its `pyproject.toml`), so
bump core and publish it *first* if paystore-django needs a new core
feature. No dedicated GitHub Actions publish workflow exists for it yet —
publish manually: `cd paystore-django && poetry build && poetry publish`.
