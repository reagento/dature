## 0.16.0

### Features

- Reworked masking configuration: replaced `mask_char`, `min_visible_chars`, `min_length_for_partial_mask`, and `fixed_mask_length` with `mask`, `visible_prefix`, and `visible_suffix`. Default masking now fully redacts values as `<REDACTED>` instead of showing partial content.

### Docs

- Extracted all inline Python code blocks from docs into executable example files with assertions. Affected pages: `masking.md`, `why-not-pydantic-settings.md`, `why-not-dynaconf.md`, `why-not-hydra.md`.

### Misc

- Added coverage for test coverage tracking in CI.


## 0.15.3

### Features

- `Merge` now accepts `sources` as a positional argument: `Merge(Source(...), Source(...))`. ([#merge-positional-sources](https://github.com/reagento/dature/issues/merge-positional-sources))


## 0.15.2

### Bugfixes

- Fixed placeholder values in ``ByteSize`` and ``PaymentCardNumber`` examples that prevented them from running.

### Docs

- Fixed incorrect code examples in comparison docs (``Merge`` keyword args, ``MergeStrategy`` enum values, validator import paths). Replaced ``docs/changelog.md`` with a symlink to root ``CHANGELOG.md``.


## 0.15.1

### Features

- Switched to hatch-vcs for dynamic versioning from git tags and towncrier for changelog management. Removed PAT token dependency from all CI workflows.


# Changelog

## Unreleased

## 0.15.0

### Improvements
- Refactored and renamed the `load_metadata` function for better clarity and consistency.

### Docs
- Updated documentation across multiple files to reflect changes related to the `load_metadata` function.

## 0.14.4

### Docs
- Improved documentation for the "Why not Pydantic Settings" section.
- Updated the configuration of the documentation site.

## 0.14.3

### Docs
- Fixed issues in the documentation for improved clarity and accuracy.
- Updated the configuration for Read the Docs integration in the documentation.
- Updated the JavaScript configuration for Read the Docs.

## 0.14.2

### Fixes
- Corrected issues in the documentation related to JavaScript integration.

## 0.14.1

### Docs
- Updated documentation for clarity and consistency.
- Improved the CI workflow for better integration with documentation generation.
- Enhanced stylesheets for improved readability in documentation.
- Refactored documentation generation scripts for better maintainability.
- Resolved various issues in the documentation.

## 0.14.0

### Improvements
- Refactored error handling in the exceptions module to provide clearer messages.
- Enhanced the sources loader to improve performance and reliability.
- Updated validation examples to demonstrate new features and best practices.
- Improved error handling in the loading module to prevent crashes on invalid inputs.

### Fixes
- Resolved issues with error reporting in the validation module.
- Fixed bugs in the masking examples to ensure accurate functionality.
- Corrected various test cases to improve coverage and reliability.
- Addressed errors in the source loading process to enhance stability.
- Fixed errors related to loading configurations from different sources.

## 0.13.0

### Features
- Introduced a new strategy for configuration loading.

### Improvements
- Enhanced the `int_from_string` function to correctly cast boolean values to integers.
- Improved documentation for advanced configuration options.

### Fixes
- Updated the README to reflect recent changes and improvements.
- Addressed comments from Devin regarding code clarity and documentation.

## 0.12.4

### Fixes
- Ensured JSON5 support is now correctly required in the configuration loader.
- Resolved issues related to loading configurations from JSON5 files.

## 0.12.3

### Improvements
- Refactored the strict retort functionality for enhanced performance.
- Added a fallback mechanism for Read the Docs (RTD) to improve documentation accessibility.

### Fixes
- Resolved issues in various source loader files to ensure better compatibility and functionality.

## 0.12.2

### Improvements
- Removed duplicate error messages for better clarity.
- Eliminated unnecessary traceback information to streamline error reporting.

### Fixes
- Fixed the Read the Docs configuration in the CI workflow to ensure proper documentation generation.

## 0.12.1

### Improvements
- Enhanced the changelog generation process to ensure accurate updates.
- Updated documentation to include support for `timedelta` as a valid type.
- Resolved security issues to improve overall safety.

### Docs
- Corrected documentation tags for clarity and consistency.

### Features
- Added logging functionality to `dature`.
- Added Docker Secrets loader.
- Added `SecretStr`, `PaymentCardNumber`, and `ByteSize` special field types.
- Added secret masking in error messages (by field name and heuristic detection).
- Added ENV variable expansion in config values.
- Added field alias provider for flexible field name mapping.
- Added `configure()` for global masking, error display, and loading settings.
- Added `F` field path objects with field mapping support.
- Added field group support for merge rules.
- Added custom merge functions and merge strategies (`append`, `prepend`, `first_wins`, etc.).
- Added `skip_invalid` and `skip_broken` merge options (global and per-source).
- Added mypy plugin.

### Improvements
- Restructured source code into subpackages: `errors/`, `expansion/`, `fields/`, `loading/`, `masking/`, `merging/`.
- Restructured tests to mirror `src/` layout.
- Improved path finders for YAML, TOML, JSON, JSON5, and INI formats.
- Improved error formatting with source location context.
- Improved source loader base with better type safety.
- Improved ENV loader with strip and type handling.
- Skipped lint/test jobs on tag push in CI (already verified on main push).
- Improved CI configurations for better stability and reliability.

### Fixes
- Fixed various issues in the CI configuration.
- Resolved multiple bugs affecting functionality and stability.

### Docs
- Added documentation site (MkDocs + Material) with full coverage: getting started, features, advanced topics, API reference.
- Added `CHANGELOG.md` with AI-generated entries on PR creation.
- Added social cards, minify, 8-bit themed headings, and custom color scheme to docs.
- Added changelog workflow: AI generates changelog entries per PR, release job extracts them for GitHub Releases.
- Added CI support for tag push: `pypi-publish`, `github-release`, and `trigger-rtd` now run on tag events.
- Added `trigger-rtd` job supporting both `latest` (main) and `stable` (tag) RTD builds.
- Added version-bump, dependency-review, scorecard, and docs CI workflows.
- Added dependabot configuration.
- Added CODEOWNERS and SECURITY.md.
- Added comprehensive examples for all features.
- Slimmed down `README.md` in favor of documentation site.

