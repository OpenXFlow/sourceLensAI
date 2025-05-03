Extending `sourceLens` to interact with an MPC (Multi-Party Computation) server API instead of the current direct LLM API calls.

**Understanding the Concept**

First, it's crucial to understand what an "MPC server API" implies in this context. MPC allows multiple parties to jointly compute a function over their private inputs without revealing those inputs to each other. For `sourceLens`, this could mean:

*   **Scenario A (Code Privacy):** `sourceLens` (Party 1) holds the private source code/prompt. An external service (Party 2) holds a private LLM model. They use MPC to compute the LLM inference (`prompt -> response`) without Party 2 seeing the code/prompt and Party 1 seeing the raw model.
*   **Scenario B (Model Privacy):** Similar to A, but the focus is on protecting Party 2's LLM model intellectual property.
*   **Scenario C (Combined Privacy):** Both code and model are kept private from the other party.

The "MPC server API" wouldn't be a single endpoint like a typical REST API. It would be an interface to a distributed system that coordinates the MPC protocol between the participating parties (e.g., `sourceLens` instance and the model host).

**How to Extend `sourceLens`**

Integrating an MPC API would follow a similar pattern to adding a new LLM provider, but with significantly more complexity in the implementation step:

1.  **Define MPC Provider Type:** Choose a name for this interaction method in your configuration, e.g., `"mpc_secure_llm"`.
2.  **Update Configuration (`config.py`):**
    *   **Schema (`LLM_PROVIDER_SCHEMA`):** Add your new provider name (`"mpc_secure_llm"`) to the `enum` list for the `"provider"` property.
    *   **Schema Parameters:** Add new properties required for MPC configuration within the provider object schema. This could include:
        *   Endpoints for the MPC coordinator or participating party servers.
        *   Paths to cryptographic keys or credentials needed for the MPC protocol.
        *   Specific MPC protocol identifiers or parameters.
        *   Job identifiers or session management details.
    *   **Validation:** Add a specific validation section (e.g., an `elif provider == "mpc_secure_llm":` block within `_validate_active_llm_config`) to check for the presence and validity of these MPC-specific parameters.

3.  **Implement MPC API Interaction (`utils/`)**
    *   **New Module:** Create a new file, e.g., `utils/_mpc_llm_api.py`.
    *   **New Function:** Define a function like `call_mpc_llm(prompt: str, llm_config: dict) -> str`.
    *   **Inside the function:**
        *   **Retrieve MPC Config:** Extract the MPC-specific endpoints, keys, and parameters from `llm_config`.
        *   **Install Libraries:** You will likely need specific Python libraries for interacting with the chosen MPC framework/protocol and possibly for cryptographic operations. Add these to `pyproject.toml`.
        *   **Input Preparation:** Prepare the `prompt` (and potentially context/code snippets) according to the MPC protocol's input requirements. This might involve secret sharing the input or encrypting it in a specific way.
        *   **API Interaction:** This is the complex part. It likely involves:
            *   Connecting to the MPC coordinator/servers.
            *   Authenticating `sourceLens` as a participant.
            *   Initiating the secure computation job (LLM inference).
            *   Submitting `sourceLens`'s private input share(s).
            *   Waiting/Polling for the MPC computation to complete across all parties. This might be asynchronous.
            *   Retrieving the resulting output share(s) (the LLM response).
            *   Reconstructing the final cleartext LLM response from the output shares, if necessary.
        *   **Error Handling:** Implement robust error handling for MPC-specific issues: communication failures between parties, protocol violations, computation errors, timeouts. Consider defining a new `MpcApiError` in `_exceptions.py`.
        *   **Return Result:** Return the final, reconstructed LLM response string.

4.  **Update Dispatcher (`utils/llm_api.py`)**
    *   In the `call_llm` function, add an `elif` block to handle the new provider type:
        ```python
        elif provider == "mpc_secure_llm":
            response_text = _mpc_llm_api.call_mpc_llm(prompt, llm_config)
        ```

5.  **Update Examples (`config.example.json`)**
    *   Add an example configuration block for the `"mpc_secure_llm"` provider, showing the required parameters (with placeholders).

6.  **Testing:** This will be the most challenging part. You'll need access to a running instance of the MPC server system (or a sophisticated mock) to test the integration properly.

**Advantages of Using MPC API:**

1.  **Enhanced Privacy/Confidentiality:** This is the primary driver. MPC could allow `sourceLens` to analyze highly sensitive or proprietary source code using a powerful external LLM without exposing the raw code content to the LLM provider. Similarly, it could protect a proprietary LLM model from the party providing the code.
2.  **Trust Reduction:** Reduces the need to fully trust the other party (e.g., the LLM provider) with your sensitive data (code/prompts) or vice-versa (proprietary model). The computation happens without revealing the inputs.
3.  **Potential for Collaboration:** Could enable scenarios where multiple parties contribute private data (different code modules, security rules) to a joint analysis securely.

**Disadvantages of Using MPC API:**

1.  **Massive Complexity:** Implementing, configuring, deploying, and debugging MPC protocols is significantly more complex than standard REST API calls. It requires specialized cryptographic and distributed systems knowledge.
2.  **Performance Overhead (Latency & Computation):** MPC protocols inherently introduce substantial overhead due to cryptographic operations (encryption, hashing, zero-knowledge proofs) and extensive network communication between parties. LLM inference via MPC would be **significantly slower** (potentially orders of magnitude) than direct API calls.
3.  **Throughput Limitations:** The communication-intensive nature limits how many requests can be processed concurrently compared to standard APIs.
4.  **Infrastructure Cost & Availability:** Running the distributed infrastructure needed for MPC is complex and potentially expensive. General-purpose, easy-to-use "MPC for LLM Inference" APIs are not yet widespread or standardized. You might need to build or rely on a very specific, niche service.
5.  **Protocol Brittleness & Error Handling:** MPC protocols can be sensitive to network partitions or participants dropping out. Handling failures gracefully in a distributed computation is challenging.
6.  **Limited Functionality:** Translating complex operations like attention mechanisms within LLMs into efficient MPC protocols is an active area of research and might impose limitations on the supported models or inference features.
7.  **Debugging Difficulty:** Debugging why a secure computation failed or produced an incorrect result when intermediate values are encrypted or secret-shared is extremely difficult.
8.  **Necessity Questionable for Many Use Cases:** For analyzing open-source code or internal code where trust in a cloud provider (with appropriate agreements) or a local LLM is sufficient, the extreme privacy guarantees of MPC might be overkill given the significant performance and complexity costs.

**Conclusion:**

While technically feasible to integrate `sourceLens` with an MPC API, it represents a **major architectural shift** with **significant implementation complexity and severe performance trade-offs**. The primary benefit is enhanced privacy for code or models. This approach would only be justifiable if the absolute confidentiality of the source code during analysis by an untrusted LLM provider is a paramount, non-negotiable requirement, and the performance degradation is acceptable. For most common use cases, using trusted cloud providers, environment variables for keys, or running local LLMs offers a much more practical balance.