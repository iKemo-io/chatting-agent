import streamlit as st
import requests
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

SYSTEM_PROMPT = "Chat like friends about any topic. Keep it casual, light, sometimes funny. Stay safe and respectful."
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"


def get_models(provider: str, base_url: str):
    try:
        if provider == "Ollama":
            logging.info("Attempting to connect to Ollama...")
            response = requests.get(f"{base_url}/api/tags", timeout=10)
            response.raise_for_status()
            models = [m["name"] for m in response.json()["models"]]
            logging.info("Successfully connected to Ollama.")
            return models
        else:
            # OpenAI-compatible (LM Studio or Other)
            logging.info(
                f"Attempting to list models from OpenAI-compatible provider at {base_url}..."
            )
            response = requests.get(
                f"{base_url.rstrip('/')}/models",
                timeout=10,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            # OpenAI-compatible returns {"data": [{"id": "model"}, ...]}
            if isinstance(data, dict) and "data" in data:
                return [
                    m.get("id")
                    for m in data["data"]
                    if isinstance(m, dict) and m.get("id")
                ]
            # Fallback: try to parse as list
            if isinstance(data, list):
                return [
                    m.get("id") or m.get("name")
                    for m in data
                    if isinstance(m, dict) and (m.get("id") or m.get("name"))
                ]
            return []
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Failed to list models from {provider} at {base_url}: {e}", exc_info=True
        )
        return []


def generate_response(provider: str, base_url: str, api_key: str, model: str, messages):
    # Create a clean version of the messages for the model
    model_messages = []
    for i, msg in enumerate(messages):
        role = "user" if i == len(messages) - 1 else "assistant"
        model_messages.append({"role": role, "content": msg["content"]})

    logging.info(f"Prompt sent to {provider}:{model}: {model_messages}")

    try:
        if provider == "Ollama":
            payload = {
                "model": model,
                "messages": model_messages,
                "stream": True,
                "system": SYSTEM_PROMPT,
            }
            with requests.post(
                f"{base_url}/api/chat", json=payload, stream=True, timeout=60
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            json_line = json.loads(line)
                            if (
                                "message" in json_line
                                and "content" in json_line["message"]
                            ):
                                yield json_line["message"]["content"]
                        except json.JSONDecodeError:
                            logging.warning(
                                f"Received non-JSON line from stream: {line}"
                            )
        else:
            # OpenAI-compatible streaming endpoint
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model,
                "messages": (
                    [{"role": "system", "content": SYSTEM_PROMPT}] + model_messages
                ),
                "stream": True,
            }
            with requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                stream=True,
                timeout=60,
            ) as response:
                response.raise_for_status()
                for raw in response.iter_lines():
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore")
                    if line.startswith("data: "):
                        data = line[len("data: ") :].strip()
                    else:
                        data = line.strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        delta = event.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        logging.warning(f"Received non-JSON SSE line: {line}")
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Error during API call to {provider}:{model}: {e}", exc_info=True
        )
        st.error(f"An error occurred while communicating with the model: {e}")
        st.session_state.running = False
        st.rerun()


def main():
    st.title("Auto-pilot Chatting Agents")
    st.info(
        "Select two models, enter a topic, and click 'Start' to begin the conversation."
    )

    # Settings panel for provider selection
    if "provider" not in st.session_state:
        st.session_state.provider = "Ollama"
    if "ollama_host" not in st.session_state:
        st.session_state.ollama_host = DEFAULT_OLLAMA_HOST
    if "oa_base_url" not in st.session_state:
        st.session_state.oa_base_url = DEFAULT_LM_STUDIO_BASE_URL
    if "oa_api_key" not in st.session_state:
        st.session_state.oa_api_key = ""

    with st.container():
        st.subheader("Settings")
        colp1, colp2, colp3 = st.columns([1, 2, 2])
        with colp1:
            provider = st.radio(
                "Provider",
                options=["Ollama", "LM Studio", "Other"],
                index=["Ollama", "LM Studio", "Other"].index(st.session_state.provider),
            )
        with colp2:
            if provider == "Ollama":
                ollama_host = st.text_input(
                    "Ollama Host", value=st.session_state.ollama_host
                )
            else:
                base_default = (
                    DEFAULT_LM_STUDIO_BASE_URL
                    if provider == "LM Studio"
                    else st.session_state.oa_base_url
                )
                oa_base = st.text_input(
                    "OpenAI-compatible Base URL",
                    value=base_default,
                    help="Example: http://localhost:1234/v1",
                )
        with colp3:
            if provider == "Other":
                oa_key = st.text_input(
                    "API Key", value=st.session_state.oa_api_key, type="password"
                )
            else:
                oa_key = st.text_input(
                    "API Key",
                    value=st.session_state.oa_api_key,
                    type="password",
                    disabled=True,
                    help="LM Studio usually doesn't require a key",
                )

        # Persist settings and trigger rerun when changed
        changed = False
        if provider != st.session_state.provider:
            st.session_state.provider = provider
            changed = True
        if provider == "Ollama":
            if ollama_host != st.session_state.ollama_host:
                st.session_state.ollama_host = ollama_host
                changed = True
            active_base = st.session_state.ollama_host
        else:
            if oa_base != st.session_state.oa_base_url:
                st.session_state.oa_base_url = oa_base
                changed = True
            if oa_key != st.session_state.oa_api_key:
                st.session_state.oa_api_key = oa_key
                changed = True
            active_base = st.session_state.oa_base_url
        if changed:
            st.rerun()

    # Fetch models for current provider
    if st.session_state.provider == "Ollama":
        models = get_models("Ollama", st.session_state.ollama_host)
    else:
        models = get_models("OpenAI", st.session_state.oa_base_url)

    # Initialize session state for agent models if not already present
    if "agent1_model" not in st.session_state:
        st.session_state.agent1_model = models[0] if models else ""
    if "agent2_model" not in st.session_state:
        st.session_state.agent2_model = (
            models[1] if len(models) > 1 else (models[0] if models else "")
        )

    col1, col2 = st.columns(2)
    with col1:
        if models:
            agent1_selection = st.selectbox(
                "Select Agent 1",
                models,
                index=(
                    models.index(st.session_state.agent1_model)
                    if st.session_state.agent1_model in models
                    else 0
                ),
            )
        else:
            agent1_selection = st.text_input(
                "Agent 1 Model", value=st.session_state.agent1_model
            )
        if agent1_selection != st.session_state.agent1_model:
            st.session_state.agent1_model = agent1_selection
            st.rerun()

    with col2:
        if models:
            agent2_selection = st.selectbox(
                "Select Agent 2",
                models,
                index=(
                    models.index(st.session_state.agent2_model)
                    if st.session_state.agent2_model in models
                    else 0
                ),
            )
        else:
            agent2_selection = st.text_input(
                "Agent 2 Model", value=st.session_state.agent2_model
            )
        if agent2_selection != st.session_state.agent2_model:
            st.session_state.agent2_model = agent2_selection
            st.rerun()

    topic = st.text_input("Enter a topic for the agents to discuss", "")
    turn_limit = st.number_input(
        "Turn limit (minutes, 0 for unlimited)", min_value=0, value=10
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "running" not in st.session_state:
        st.session_state.running = False

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(f"**{message['role']}** ({message['timestamp']})")
            st.markdown(message["content"])

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(
            "Start",
            disabled=not topic
            or st.session_state.running
            or not (st.session_state.agent1_model and st.session_state.agent2_model),
        ):
            st.session_state.running = True
            st.session_state.start_time = datetime.now()
            st.session_state.finish_time = None
            st.session_state.messages = [
                {
                    "role": "Agent 1",
                    "content": topic,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                }
            ]
            st.rerun()

    with col2:
        if st.button("Stop", disabled=not st.session_state.running):
            st.session_state.running = False
            st.session_state.finish_time = datetime.now()
            st.rerun()

    if st.session_state.running:
        if (
            turn_limit > 0
            and (datetime.now() - st.session_state.start_time).total_seconds()
            > turn_limit * 60
        ):
            st.session_state.running = False
            st.session_state.finish_time = datetime.now()
            st.warning("Time limit reached. Conversation stopped.")
            st.rerun()

        # Determine the current agent and model from session state
        if len(st.session_state.messages) % 2 != 0:
            current_agent_model = st.session_state.agent2_model
            current_agent_name = "Agent 2"
        else:
            current_agent_model = st.session_state.agent1_model
            current_agent_name = "Agent 1"

        logging.info(
            f"Current agent: {current_agent_name}, Model: {current_agent_model}"
        )

        with st.chat_message(current_agent_name):
            message_placeholder = st.empty()
            full_response = ""
            # Check if we should stop before starting the response
            if not st.session_state.running:
                st.rerun()

            # Select active base and key
            if st.session_state.provider == "Ollama":
                base = st.session_state.ollama_host
                key = ""
                provider_name = "Ollama"
            else:
                base = st.session_state.oa_base_url
                key = st.session_state.oa_api_key
                provider_name = "OpenAI"

            for chunk in generate_response(
                provider_name if provider_name == "Ollama" else "OpenAI",
                base,
                key,
                current_agent_model,
                st.session_state.messages,
            ):
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")
                # Check if the stop button was pressed during generation
                if not st.session_state.running:
                    break

            message_placeholder.markdown(full_response)

        # Only add the message if the run was not stopped mid-generation
        if st.session_state.running:
            # Validate the response
            if not full_response or not full_response.strip():
                st.error(
                    f"{current_agent_name} ({current_agent_model}) failed to generate a response. The conversation has been stopped."
                )
                logging.warning(
                    f"Model {current_agent_model} returned an empty response."
                )
                st.session_state.running = False
                st.rerun()
            else:
                st.session_state.messages.append(
                    {
                        "role": current_agent_name,
                        "content": full_response,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                )
                st.rerun()

    with col3:
        if "start_time" in st.session_state and st.session_state.start_time:
            start_time_str = st.session_state.start_time.strftime("%Y-%m-%d %H:%M:%S")
            finish_time_str = (
                st.session_state.finish_time.strftime("%Y-%m-%d %H:%M:%S")
                if st.session_state.finish_time
                else "Not finished"
            )

            chat_export = f"""
 # Chat on Topic: {topic}

 **Start Time:** {start_time_str}
 **Finish Time:** {finish_time_str}

 **Agent 1 Model:** {st.session_state.agent1_model}
 **Agent 2 Model:** {st.session_state.agent2_model}

 ---

 """
            chat_export += "\n".join(
                [
                    f"**{m['role']}** ({m['timestamp']})\n{m['content']}"
                    for m in st.session_state.messages
                ]
            )

            if st.download_button(
                label="Save chat",
                data=chat_export,
                file_name=f"chat_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                disabled=not st.session_state.messages,
            ):
                pass

    st.chat_input("Chat input is disabled", disabled=True)


if __name__ == "__main__":
    main()
