# Regulens-AI

Regulens-AI is a Windows desktop application for comparing regulation documents via the RAGCore-X service. The project is in its early stages and follows the design outlined in [docs/TechSpec.md](docs/TechSpec.md).

## Development Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python -m app
   ```

## Running Tests

The project uses `pytest`. To execute the test suite locally:

```bash
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. This project is released under the [MIT License](LICENSE).

## Project Structure

- `app/` contains the application modules such as `ApiClient`, `CompareManager`, and export helpers.
- `assets/` stores icons and style sheets (currently empty).
- `config_default.yaml` provides example API configuration.

The design document in `docs/TechSpec.md` describes the planned GUI and full feature set.
