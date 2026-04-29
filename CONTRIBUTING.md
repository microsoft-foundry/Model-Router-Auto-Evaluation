# Contributing to Model Router Auto Evaluation

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit <https://cla.opensource.microsoft.com>.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## How to Contribute

1. **Fork** the repository and create a feature branch from `main`
2. **Set up** your development environment:
   ```bash
   python -m venv .venv
   # Windows: .\.venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. **Make your changes** — keep PRs focused on a single concern
4. **Run tests** before submitting:
   ```bash
   pytest tests/ -v -m "not integration"
   ```
5. **Lint** your code:
   ```bash
   ruff check src/ tests/ scripts/
   ```
6. **Open a pull request** with a clear description of what you changed and why

## Reporting Issues

- Use [GitHub Issues](../../issues) to report bugs or suggest features
- Include steps to reproduce, expected vs actual behavior, and your Python version
- For security vulnerabilities, see [SECURITY.md](SECURITY.md) instead

## Code Style

- Follow existing patterns in the codebase
- Use [Ruff](https://docs.astral.sh/ruff/) for linting (configured in `pyproject.toml`)
- Keep line length ≤ 100 characters
- Target Python 3.9+ compatibility
