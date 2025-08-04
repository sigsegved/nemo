# Continuous Integration (CI) Documentation

This document describes the CI/CD setup for the Nemo Volatility Harvest Bot project.

## Overview

The project uses GitHub Actions for continuous integration, with a comprehensive pipeline that validates code quality, runs tests, and ensures the project maintains high standards across all changes.

## Workflow Triggers

The CI pipeline runs on:
- **Pull Requests** to `main` and `develop` branches
- **Direct pushes** to `main` and `develop` branches  
- **Manual dispatch** via GitHub Actions UI

## Pipeline Jobs

### 1. Test Job (`test`)
**Matrix Strategy**: Runs on Python 3.9, 3.10, 3.11, and 3.12

**Steps:**
- Code checkout
- Python environment setup with caching
- System dependencies installation (build-essential)
- Python dependencies installation with retry logic
- Python syntax validation
- Code formatting check (Black)
- Linting (Flake8)
- Type checking (MyPy)
- Test execution (Pytest)
- Coverage reporting (Codecov)

**Resilience Features:**
- Graceful degradation when dependencies fail to install
- Non-blocking warnings for development-stage issues
- Retry mechanisms for network-dependent operations
- Fallback validation methods

### 2. Basic Validation Job (`basic-validation`)
**Purpose**: Ensures fundamental project integrity

**Checks:**
- Python syntax validation for all `.py` files
- Project structure validation
- Required files existence check
- Import statement analysis
- Basic code quality indicators

### 3. Dependency Analysis Job (`dependency-analysis`)
**Purpose**: Validates project dependencies

**Checks:**
- `requirements.txt` syntax validation
- Dependency counting and categorization
- Security vulnerability scanning (with Safety)

### 4. Quality Gate Job (`quality-gate`)
**Purpose**: Final validation and summary

**Requirements:**
- Basic validation must pass (required)
- Dependency analysis should pass (recommended)
- Test job issues are logged but non-blocking during early development

## Configuration Files

### Code Quality Tools

#### Black (Code Formatting)
- **Config**: `pyproject.toml`
- **Line Length**: 88 characters
- **Target**: Python 3.9-3.12

#### Flake8 (Linting)
- **Config**: `setup.cfg`
- **Max Line Length**: 88 characters
- **Compatibility**: Black-compatible settings
- **Exclusions**: Test files have relaxed rules

#### MyPy (Type Checking)
- **Config**: `mypy.ini`
- **Mode**: Gradual typing (relaxed for early development)
- **Import Handling**: Ignore missing imports for external packages

#### Pytest (Testing)
- **Config**: `pyproject.toml` and `pytest.ini`
- **Features**: Async support, coverage reporting, custom markers
- **Coverage**: Source code only, excludes tests and virtual environments

### Dependency Management

#### Production Dependencies (`requirements.txt`)
Full dependency list including trading APIs and analysis libraries.

#### CI Dependencies (`requirements-ci.txt`)
Curated subset excluding problematic packages:
- Excludes `ta-lib` (compilation complexity)
- Excludes `uvloop` (platform-specific)
- Includes security scanning tools
- Focuses on core testing and quality tools

### Pre-commit Hooks (`.pre-commit-config.yaml`)
Optional developer setup for local validation:
- Trailing whitespace removal
- YAML/JSON/TOML validation
- Black formatting
- Flake8 linting
- MyPy type checking
- Import sorting (isort)

## Usage

### For Contributors

1. **Local Development Setup**:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Running Tests Locally**:
   ```bash
   pytest tests/ -v
   pytest tests/ --cov=src  # With coverage
   ```

3. **Code Quality Checks**:
   ```bash
   black --check src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

### For Maintainers

1. **Monitor CI Status**:
   - Check GitHub Actions tab for pipeline status
   - Review quality gate summaries
   - Monitor coverage reports via Codecov

2. **Adding New Dependencies**:
   - Add to `requirements.txt` for production
   - Test in CI; add to `requirements-ci.txt` if needed
   - Update documentation if dependency affects development workflow

3. **Adjusting Quality Standards**:
   - Update configuration files (`setup.cfg`, `mypy.ini`, `pyproject.toml`)
   - Consider backward compatibility with existing code
   - Test configuration changes in development branches

## Best Practices

### Code Quality
- **Formatting**: Use Black for consistent code formatting
- **Linting**: Address Flake8 errors; warnings are acceptable during early development
- **Type Hints**: Gradually add type hints; enforce in critical modules (models)
- **Documentation**: Add docstrings for public APIs

### Testing
- **Coverage**: Aim for reasonable test coverage; 100% not required initially
- **Test Categories**: Use pytest markers (`unit`, `integration`, `slow`, `network`)
- **Async Testing**: Use `pytest-asyncio` for async code testing

### Dependencies
- **Security**: Regularly update dependencies and monitor security alerts
- **Compatibility**: Test with multiple Python versions
- **CI Reliability**: Use `requirements-ci.txt` for stable CI runs

## Troubleshooting

### Common Issues

1. **Dependency Installation Failures**:
   - Check network connectivity
   - Review `requirements-ci.txt` for CI-compatible alternatives
   - Consider dependency pinning for stability

2. **Test Failures**:
   - Review test output in GitHub Actions logs
   - Run tests locally to reproduce issues
   - Check for environment-specific problems

3. **Code Quality Issues**:
   - Run tools locally: `black --diff src/`, `flake8 src/`, `mypy src/`
   - Review configuration files for project-specific settings
   - Consider gradual improvement for legacy code

### GitHub Actions Debugging

1. **View Detailed Logs**:
   - Click on failed job in GitHub Actions
   - Expand step output for detailed error messages
   - Check "Quality gate summary" for overall status

2. **Re-running Jobs**:
   - Use "Re-run failed jobs" for transient failures
   - Use "Re-run all jobs" for systematic issues

3. **Manual Workflow Dispatch**:
   - Trigger pipeline manually for testing
   - Useful for dependency or configuration changes

## Future Enhancements

### Planned Improvements
- **Performance Testing**: Add performance benchmarks for trading strategies
- **Security Scanning**: Enhanced dependency vulnerability scanning
- **Docker Integration**: Containerized testing environments
- **Release Automation**: Automated versioning and release creation

### Advanced Features
- **Multi-environment Testing**: Test against different market data sources
- **Load Testing**: Validate system performance under trading loads
- **Integration Testing**: End-to-end testing with paper trading accounts

## Support

For CI-related issues:
1. Check this documentation
2. Review existing GitHub Issues
3. Create new issue with "CI" label
4. Include relevant logs and error messages

---

*This CI setup follows best practices for Python projects and is designed to grow with the project's needs while maintaining reliability and developer productivity.*