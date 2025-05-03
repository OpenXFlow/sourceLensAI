
**16. Initial State Preparation (`main.py`)**

This diagram details how command-line arguments override configuration values during the creation of the `shared_initial_state`.

```mermaid
sequenceDiagram
    participant CLI as CLI (main.py)
    participant Args as Parsed Arguments (argparse.Namespace)
    participant Config as Loaded Config Dictionary
    participant Shared as shared_initial_state (dict)

    Note over CLI: After successful config loading
    CLI->>CLI: _prepare_initial_state(args, config)
    activate CLI # self-call

    CLI->>Args: Read args.repo, args.dir, args.name, args.output, etc.
    CLI->>Config: Read config['source'], config['output'], config['project'], etc.

    alt args.name is provided
        CLI->>Shared: Set shared['project_name'] = args.name
    else config['project']['default_name'] exists
        CLI->>Shared: Set shared['project_name'] = config['project']['default_name']
    else
        CLI->>Shared: Set shared['project_name'] = derived name (from FetchCode later)
    end

    alt args.output is provided
        CLI->>Shared: Set shared['output_dir'] = args.output
    else
        CLI->>Shared: Set shared['output_dir'] = config['output']['base_dir']
    end

    %% Similar logic for include, exclude, max_size, language overrides...
    CLI->>Shared: Set shared['include_patterns'] = args.include or config['source']['default_include_patterns']
    CLI->>Shared: Set shared['max_file_size'] = args.max_size or config['source']['max_file_size_bytes']

    CLI->>Shared: Populate other state from config (llm_config, source_config, cache_config, github_token, etc.)
    CLI->>Shared: Initialize empty state lists (files, abstractions, chapters, etc.)

    CLI-->>CLI: return shared_initial_state
    deactivate CLI # end self-call