```mermaid
classDiagram
    direction TD

    %% ==================================
    %% --- Class/Interface Definitions ---
    %% ==================================

    class BaseNode {
        <<Abstract>>
        +max_retries: int
        +wait: int
        +__init__(max_retries, wait)
        +prep(shared: SharedState)* : PrepResultType
        +exec(prep_res: PrepResultType)* : ExecResultType
        +post(shared: SharedState, prep_res: PrepResultType, exec_res: ExecResultType)* : void
        #_get_required_shared(shared, key) : Any
        #_log_info(message) : void
        #_log_warning(message) : void
        #_log_error(message, exc=None) : void
    }

    class BaseBatchNode {
        <<Abstract>>
        +prep(shared: SharedState)* : Iterable[PrepItemType]
        +exec(item: PrepItemType)* : ExecItemResultType
        +post(shared: SharedState, prep_res: Iterable[PrepItemType], exec_res_list: list[ExecItemResultType])* : void
    }

    class FetchCode {
        +prep(shared) : bool
        +exec(prep_res) : None
        +post(shared, prep_res, exec_res) : void
        -_derive_project_name(shared) : str
    }

    class IdentifyAbstractions {
        +prep(shared) : dict
        +exec(prep_res) : AbstractionsList
        +post(shared, prep_res, exec_res) : void
        -_format_prompt(...) : str
        -_parse_and_validate_indices(...) : list[int]
    }

    class AnalyzeRelationships {
        +prep(shared) : dict
        +exec(prep_res) : RelationshipsDict
        +post(shared, prep_res, exec_res) : void
        -_format_prompt(...) : str
        -_parse_and_validate_relationships(...) : tuple
    }

    class OrderChapters {
        +prep(shared) : dict
        +exec(prep_res) : ChapterOrderList
        +post(shared, prep_res, exec_res) : void
        -_format_prompt(...) : str
        -_parse_and_validate_order(...) : ChapterOrderList
    }

    class WriteChapters {
        +prep(shared) : Iterable[dict]
        +exec(item) : ChapterContent
        +post(shared, prep_res, exec_res_list) : void
        -_format_prompt_for_chapter(item) : str
        -_prepare_chapter_metadata(...) : tuple
    }

    class CombineTutorial {
        +prep(shared) : bool
        +exec(prep_res) : None
        +post(shared, prep_res, exec_res) : void
        -_generate_mermaid_diagram(...) : str
        -_prepare_index_content(...) : str
        -_write_output_files(...) : bool
    }

    class CacheProtocol {
        <<Interface>>
        +get(prompt: str)* : Optional[str]
        +put(prompt: str, response: str)* : void
    }

    class LlmCache {
        -cache_file_path: Path
        -cache: dict
        +__init__(path)
        +get(prompt) : Optional[str]
        +put(prompt, response) : void
        -_load_cache() : dict
        -_save_cache() : void
    }

    class DummyCache {
        +get(prompt) : None
        +put(prompt, response) : void
    }

    class Exception {
      <<Builtin>>
    }

    class LlmApiError {
      +status_code: Optional[int]
      +provider: Optional[str]
      +__init__(message, status_code=None, provider=None)
    }

    class GithubApiError {
       +__init__(message)
    }

    class ValidationFailure {
       +raw_output: Optional[str]
       +__init__(message, raw_output=None)
    }

    class ConfigError {
       +__init__(message)
    }


    %% ==========================
    %% --- Relationships ---
    %% ==========================

    %% Node Inheritance
    BaseNode <|-- BaseBatchNode
    BaseNode <|-- FetchCode
    BaseNode <|-- IdentifyAbstractions
    BaseNode <|-- AnalyzeRelationships
    BaseNode <|-- OrderChapters
    BaseNode <|-- CombineTutorial
    BaseBatchNode <|-- WriteChapters

    %% Cache Implementation
    CacheProtocol <|.. LlmCache
    CacheProtocol <|.. DummyCache

    %% Exception Inheritance
    Exception <|-- LlmApiError
    Exception <|-- GithubApiError
    Exception <|-- ValidationFailure
    Exception <|-- ConfigError