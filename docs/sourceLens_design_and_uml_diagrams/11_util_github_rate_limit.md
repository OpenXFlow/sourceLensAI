
**12. GitHub API Rate Limit Handling (`utils.github.py`)**

This diagram details the specific interaction when the GitHub API fetch encounters a rate limit error.

```mermaid
sequenceDiagram
    participant GitHubUtil as GitHubCrawler (_fetch_github_api)
    participant Requests as requests library
    participant ExternalGitHub as GitHub API
    participant Time as time module

    activate GitHubUtil

    GitHubUtil->>Requests: requests.get(api_url, headers, ...)
    activate Requests

    Requests->>ExternalGitHub: HTTP GET Request
    activate ExternalGitHub

    ExternalGitHub-->>Requests: HTTP 403/429 Response (Rate Limit Exceeded) with X-RateLimit-Reset header
    deactivate ExternalGitHub

    Requests-->>GitHubUtil: Response object (status=403/429)
    deactivate Requests

    Note over GitHubUtil: Detects rate limit error

    GitHubUtil->>GitHubUtil: _handle_rate_limit(response)
    activate GitHubUtil # self-call

    GitHubUtil->>Time: time.time()
    activate Time
    Time-->>GitHubUtil: current_timestamp
    deactivate Time

    Note over GitHubUtil: Calculates wait_time based on X-RateLimit-Reset header and current time

    GitHubUtil->>Time: time.sleep(wait_time)
    activate Time
    Note over Time: Pauses execution
    Time-->>GitHubUtil: done
    deactivate Time

    deactivate GitHubUtil # end self-call

    Note over GitHubUtil: Retries the original API request (or adds path back to stack)

    deactivate GitHubUtil