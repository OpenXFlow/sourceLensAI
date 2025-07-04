
# How to Integrate `sourceLens` with an MPC (Multi-Party Computation) Interface

This document provides an expert analysis and technical guide for extending the `sourceLens` tool to support interactions with an LLM through an interface based on Multi-Party Computation (MPC), replacing direct API calls with a secure computation protocol.

## 1. Conceptual Overview: What is an "MPC LLM Interface"?

Unlike a standard REST API, an "MPC LLM Interface" is not a simple `request-response` model. It represents a **client-side implementation of an MPC protocol**, where `sourceLens` acts as one of the parties in a distributed computation.

The core principle is that multiple parties (e.g., `sourceLens` and an LLM provider) can jointly compute a function (in this case, LLM inference) on their private inputs without revealing those inputs to each other.

**Relevant Scenarios for `sourceLens`:**

*   **Scenario A: Data Privacy (Source Code Protection):**
    *   **Party 1 (`sourceLens`):** Holds the private source code / prompt.
    *   **Party 2 (LLM Provider):** Holds a public or proprietary model.
    *   **Goal:** To generate a response without the LLM provider ever seeing the source code in cleartext. `sourceLens` would only submit cryptographically-processed shares of its input.

*   **Scenario B: Model Privacy (IP Protection):**
    *   **Party 1 (`sourceLens`):** Holds a public prompt.
    *   **Party 2 (LLM Provider):** Holds a proprietary, private LLM.
    *   **Goal:** To allow `sourceLens` to use the model without the provider revealing its architecture or weights.

## 2. Architectural Impact on `sourceLens`

Integrating MPC would fundamentally alter the `llm_api.py` module.

*   **Synchronous vs. Asynchronous:** MPC computations are long-running and stateful. The simple, synchronous `call_llm` function would be replaced by an asynchronous process managing the entire lifecycle of a secure computation job:
    1.  **Initialization:** Establish a connection to the MPC coordinator.
    2.  **Input Sharing:** Prepare and submit cryptographic shares of the prompt.
    3.  **Polling/Waiting:** Actively wait for the distributed computation to complete.
    4.  **Result Reconstruction:** Receive the resulting shares and reconstruct the final cleartext response.

*   **Change in `_get_llm_response`:** Instead of a simple dispatching logic, this function would call a complex MPC session manager.

## 3. Implementation Steps

The integration would follow the pattern of adding a new provider, but with a significantly more complex implementation step.

**Step 1: Define Provider Type and Configuration**

1.  **Provider Name:** Define a new provider type in `config.json`, e.g., `"mpc_secure_llm"`.
2.  **Configuration Profile:** Create a new profile in `llm_profiles` that includes MPC-specific parameters.

    ```json
    {
      "provider_id": "mpc_provider_main",
      "provider": "mpc_secure_llm", // The key for the dispatcher
      "is_local_llm": false, // Technically a distributed system
      "model": "model_id_for_mpc_protocol",
      "api_key_env_var": "MPC_AUTH_TOKEN_ENV", // Auth token for the MPC system
      "api_key": null,
      "mpc_config": {
        "coordinator_url": "https://mpc-coordinator.example.com:8080",
        "party_endpoints": ["https://party1.example.com", "https://party2.example.com"],
        "private_key_path": "/path/to/sourcelens_private_key.pem",
        "protocol_id": "secure_llm_inference_v1"
      }
    }
    ```

**Step 2: Implement the MPC API Interaction**

1.  **New Module:** Create a new file: `src/sourcelens/utils/_mpc_llm_api.py`.
2.  **Required Libraries:** Add specialized libraries for MPC and cryptography (e.g., `syft`, `tf-encrypted`, or a proprietary SDK) to `pyproject.toml`.
3.  **New Function:** Define an asynchronous function: `async def call_mpc_llm(prompt: str, llm_config: LlmConfigDict) -> str:`.
    *   **Load Config:** Extract MPC-specific URLs, key paths, and parameters from `llm_config['mpc_config']`.
    *   **Prepare Input:** Implement the "secret sharing" logic to split the `prompt` into cryptographic shares.
    *   **Manage MPC Protocol:**
        *   Connect to the coordinator and other parties.
        *   Authenticate using the cryptographic keys.
        *   Submit the input shares and initiate the computation.
        *   Implement `asyncio.sleep` or another mechanism for polling/waiting for the job to complete.
        *   Receive the resulting output shares.
    *   **Reconstruct Output:** Assemble the received shares into the final cleartext response.
    *   **Error Handling:** Define and raise a new exception (e.g., `MpcApiError`) for specific failures like protocol violations, timeouts, or computation errors.

**Step 3: Update the LLM Dispatcher**

*   **Location:** `src/sourcelens/utils/llm_api.py`, within the `_get_llm_response` function.
*   **Action:** Add an `elif provider == "mpc_secure_llm":` block. This would likely require refactoring `call_llm` and its callers to be `async`.

## 4. Strategic Assessment

| Advantages                               | Disadvantages & Challenges                                                                                                                              |
| :--------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ✅ **Maximum Confidentiality:** Absolute protection of source code from the LLM provider (and vice-versa). Enables analysis of highly sensitive projects. | ❌ **Extreme Complexity:** Implementation requires deep knowledge of cryptography and distributed systems, far exceeding standard API integration. |
| ✅ **Reduced Trust Requirements:** Eliminates the need to fully trust a third party. The computation is mathematically secured. | ❌ **Performance Overhead:** **The biggest drawback.** MPC introduces massive latency (seconds to minutes per request) due to cryptographic operations and network communication. |
| ✅ **Enables Secure Collaboration:** Opens the door for scenarios where multiple parties securely contribute private data to a joint analysis. | ❌ **Limited Throughput:** The communication-intensive nature drastically reduces the number of concurrent requests possible.                               |
|                                          | ❌ **Infrastructure Cost & Availability:** Standardized "MPC-as-a-Service" for LLMs is not yet a commodity. It would require a niche, expensive provider or custom infrastructure. |
|                                          | ❌ **Model Limitations:** Translating modern LLM architectures (e.g., attention mechanisms) into MPC-efficient protocols is a cutting-edge research problem. Not all models would be supported. |
|                                          | ❌ **Debugging Difficulty:** Diagnosing failures in a distributed, cryptographically secure computation is extremely challenging. |

## Conclusion

Integrating an MPC interface into `sourceLens` is a technically fascinating but major architectural undertaking with severe performance and complexity trade-offs.

*   **When is it justified?** Only in extreme cases where **absolute, mathematically-provable confidentiality of the source code is a non-negotiable requirement**, and the resulting performance degradation is acceptable.
*   **The Practical Alternative:** For 99% of use cases (including commercial and sensitive projects), the combination of **trusted cloud providers** (with appropriate data processing agreements), **secure API key management**, and **locally-hosted LLMs** offers a far more pragmatic and effective balance between security, performance, and complexity.
