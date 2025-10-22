# Auto-pilot Chatting Agents

This is a Streamlit application that allows two LLMs to chat with each other. It supports local Ollama models and OpenAI-compatible providers like LM Studio or any custom base URL.

![App Demo](demo.gif)


## Features

- **Settings Panel (Top)**: Select your LLM provider and connection details.
- **Provider Options**:
  - **Ollama**: Use local Ollama server (default `http://localhost:11434`).
  - **LM Studio**: OpenAI-compatible API (default `http://localhost:1234/v1`).
  - **Other**: Custom OpenAI-compatible base URL and API key.
- **Model Selection**: Choose two models for the agents (lists from provider; text input fallback if listing fails).
- **Conversation Control**: Start/Stop and optional time limit.
- **Real-time Streaming**: See messages stream in as they are generated.
- **Save Chat**: Download the entire conversation as a Markdown file.


## Requirements

- Python 3.9+
- Packages: `streamlit`, `requests`

Install dependencies:

```bash
pip install streamlit requests
```


## Providers

### Ollama

- Install and run Ollama: https://ollama.com
- Ensure the server is running (default `http://localhost:11434`).
- The app lists models via `GET /api/tags` and chats via `POST /api/chat`.

### LM Studio

- Install LM Studio: https://lmstudio.ai
- Start the OpenAI-compatible local server from LM Studio.
- Default base URL in the app is `http://localhost:1234/v1`.
- The app lists models via `GET {base_url}/models` and chats via `POST {base_url}/chat/completions` with streaming.

### Other (OpenAI-compatible)

- Provide a custom base URL (e.g., `https://api.example.com/v1`).
- Provide an API key if required by your provider.
- Must implement OpenAI-compatible endpoints:
  - `GET {base_url}/models`
  - `POST {base_url}/chat/completions` (SSE streaming)


## How to run the app

1. Ensure your chosen provider is running/accessible.
2. Install dependencies:
   ```bash
   pip install streamlit requests
   ```
3. Start the app:
   ```bash
   streamlit run app.py
   ```
4. In the app, use the **Settings** panel to select:
   - Provider: `Ollama` | `LM Studio` | `Other`
   - Host/Base URL and optional API key
   - Then select the two models for Agent 1 and Agent 2
5. Enter a topic and press **Start**.


## Troubleshooting

- If model listing fails, you can still type model names manually in the model fields.
- For LM Studio/Other providers, ensure the base URL ends with `/v1` and the server exposes `/models` and `/chat/completions`.
- For custom providers requiring auth, add a valid API key in the **Settings** panel.
- See `app.log` for detailed error messages.
