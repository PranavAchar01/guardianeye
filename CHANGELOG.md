# Changelog

All notable changes to GuardianEye are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- AGPL-3.0 license.
- GitHub Actions CI that runs ruff and pytest on every push and pull request.
- `--version` flag on the `guardianeye` CLI.
- Each run now writes `config.json` (the exact settings used) alongside
  `metrics.json`, so any run is reproducible from its output directory.
- `py.typed` marker so downstream type checkers see GuardianEye's type hints.
- Contributor scaffolding: a CONTRIBUTING guide, issue and pull-request
  templates, an `.editorconfig`, and a pre-commit config.

### Changed

- Removed em dashes from docs, docstrings, and script text for a consistent
  house style.
- Cleaned up pre-existing lint in the promo-rendering script so `ruff check .`
  is green across the whole repository.

## [0.1.0]

Initial release for the Sports World Cup Hackathon 2026 (Track 4: Sports
Business and Operations).

### Added

- Collapse detection: YOLO11-pose posture classification plus a down-time state
  machine that confirms a medical incident only after sustained down-time.
- Crowd-crush early warning: depth-calibrated people-per-square-meter density
  with Fruin/Still risk levels and stagnation escalation.
- Edge Watch: depth-cliff hazard mapping with ego-motion-compensated trajectory
  prediction and time-to-edge estimates.
- Per-run outputs: annotated video, standalone HTML report, and per-frame
  metrics JSON.
