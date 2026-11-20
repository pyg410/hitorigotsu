# Release guide

The repository is ready to build, but no remote repository, PyPI registration or
release was created by the implementation task. Choose your actual GitHub owner
and repository URL when publishing; no fabricated URL is present in package metadata.

1. Publish this repository, set its description and add the real repository/issue URLs
   under `[project.urls]` in `pyproject.toml`.
2. Run `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run pytest -q`, and `uv build`. Review the CI matrix on all three OSes.
3. Install the built wheel in a separate environment and try generated media. Run
   `HITORIGOTSU_AUDIO_TEST=1 uv run pytest -k real_audio_controls` on audio hardware.
   Run the opt-in YouTube test with a URL you may download. A 403 is a failed E2E,
   not evidence that playback succeeded.
4. Check PyPI name availability. Configure a PyPI pending/trusted publisher for the
   actual repository, `publish.yml` workflow and `pypi` environment. Protect that
   GitHub environment with required reviewers.
5. Update `__version__` and `project.version` together, run `uv lock`, tag the release,
   and dispatch the Publish workflow from the tested revision. It builds distributions
   and uses OIDC, without a stored PyPI password/token.
6. Test `uv tool install hitorigotsu-cli` after publication and attach wheel/sdist to
   the GitHub release. Do not attach cached or copyrighted media.

The manually dispatched publishing workflow does not create tags or GitHub releases.
Maintainers remain responsible for passing CI and release review before dispatch.
Only code/generated geometric images are MIT; dependency licenses remain their own.
