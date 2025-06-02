# Regulens-AI

Regulens-AI is a desktop application designed to assist with compliance analysis tasks by leveraging a Retrieval Augmented Generation (RAG) pipeline. It helps users analyze sets of control documents, procedural documents, and evidence files to assess compliance status.

## Features (Updated)

*   **Project-based workflow**: Organize your compliance assessments into projects.
*   **Three-column data input**: Clearly define paths for Controls, Procedures, and Evidence documents.
*   **Automated RAG Pipeline**: Processes your documents to find relevant information and generate compliance insights.
*   **Local Vector Store**: Utilizes FAISS for efficient similarity searches on document embeddings.
*   **LLM Integration**: Leverages Large Language Models (e.g., OpenAI GPT series) for assessment and judgment.
*   **Markdown Reporting**: Generates detailed reports of the findings.
*   **Sample Projects**: Automatically creates sample projects on first launch to demonstrate functionality.
*   **Configurable Settings**: Adjust OpenAI API key, embedding/LLM models, and other pipeline parameters through a settings dialog.

## Development Setup

1.  **Create a virtual environment and install dependencies**:
    ```bash
    # Create a virtual environment
    python -m venv .venv

    # Activate the virtual environment
    # On macOS and Linux:
    source .venv/bin/activate
    # On Windows:
    # .\.venv\Scripts\activate

    # Install dependencies
    pip install -r requirements.txt
    ```

2.  **Configure Settings**:
    *   On the first launch, the application will create sample projects.
    *   Before running any analysis, open the **Settings dialog** (File > Settings...).
    *   You **must** configure your **OpenAI API Key**.
    *   Review and set the desired **Embedding Model** and **LLM Model**. Other parameters can also be adjusted.

3.  **Run the application**:
    ```bash
    python -m app
    ```
    This command runs the main application GUI from the `app` module.

## Sample Projects

On the first launch (or if `~/regulens-ai/projects.json` is not found), Regulens-AI will automatically create two sample projects and their associated data files in your user's home directory under `~/regulens-ai/sample_data/`.

This allows you to explore the application's features without needing your own documents immediately.

**Directory Structure for Sample Data (`~/regulens-ai/sample_data/`)**:

*   **Sample 1: 強密碼合規範例 (Strong Password Compliance Example)**
    *   Purpose: Demonstrates a typical log audit or technical configuration verification scenario. For example, checking system configurations or logs against strong password policies.
    *   Files:
        *   `sample1/controls/control1.txt` (e.g., password policy document)
        *   `sample1/procedures/procedure1.txt` (e.g., steps to audit password settings)
        *   `sample1/evidences/evidence1.txt` (e.g., system configuration export or log snippets)

*   **Sample 2: 風險清冊範例 (Risk Register Example)**
    *   Purpose: Illustrates mapping items from a risk register or an IT asset inventory to applicable controls and procedures. For example, ensuring each identified risk has corresponding mitigation procedures and controls in place.
    *   Files:
        *   `sample2/controls/controlA.txt` (e.g., a set of security controls)
        *   `sample2/procedures/procedureA.txt` (e.g., risk management procedures)
        *   `sample2/evidences/evidenceA.txt` (e.g., excerpts from a risk register)

Each `.txt` file will contain placeholder text relevant to its purpose.

## Screenshots (Coming Soon)

*   `[Placeholder for Screenshot: Main interface showing the three-column layout for Controls, Procedures, and Evidences]`
*   `[Placeholder for Screenshot: Sidebar with sample projects "強密碼合規範例" and "風險清冊範例" highlighted, showing their distinct tags/colors]`
*   `[Placeholder for Screenshot: Updated Settings Dialog focusing on OpenAI API key, Embedding Model, and LLM Model configuration]`

## Running Tests

The project uses `pytest`. To execute the test suite locally (ensure development dependencies are installed):

```bash
pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. This project is released under the [MIT License](LICENSE).

## Project Structure

-   `app/`: Contains the core application modules, including the UI, pipeline logic, and data models.
-   `assets/`: Stores icons and style sheets (currently placeholder).
-   `config_default.yaml`: Provides default application settings. These can be overridden via the in-app Settings Dialog, which are then stored in a user-specific configuration file.
-   `docs/`: Contains technical specification documents.
-   `tests/`: Contains automated tests for the application.
-   `~/regulens-ai/sample_data/`: **User-specific directory** created on first launch to store sample project data. Not part of the repository.
-   `~/regulens-ai/cache/`: **User-specific directory** for caching embeddings and other pipeline artifacts. Not part of the repository.
-   `~/.config/regulens-ai/projects.json`: **User-specific file** storing the list of user-created projects. Not part of the repository.

The design document in `docs/TechSpec.md` describes the planned GUI and full feature set, though some aspects may have evolved.
