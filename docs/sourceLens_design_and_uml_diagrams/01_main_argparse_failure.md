Argument Parsing Failure (main.py)
This diagram shows what happens if the user runs the command with invalid arguments (e.g., missing required --repo or --dir).

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py / argparse)
    participant System as Operating System / Shell

    User->>CLI: Executes `sourcelens` (with invalid args, e.g., missing --repo/--dir)
    activate CLI

    CLI->>CLI: parse_arguments()
    Note over CLI: argparse attempts to parse argv

    CLI-->>System: Prints help/error message (from argparse)
    Note over CLI: Argparse exits due to parsing error (e.g., "the following arguments are required: --repo/-r or --dir/-d")

    CLI-->>User: Exits with non-zero status code
    deactivate CLI