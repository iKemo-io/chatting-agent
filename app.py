import streamlit as st
import requests
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

SYSTEM_PROMPT = "Chat like friends about any topic. Keep it casual, light, sometimes funny. Stay safe and respectful."
OLLAMA_HOST = 'http://localhost:11434'

def get_models():
    try:
        logging.info("Attempting to connect to Ollama...")
        response = requests.get(f"{OLLAMA_HOST}/api/tags")
        response.raise_for_status()
        models = [m['name'] for m in response.json()["models"]]
        logging.info("Successfully connected to Ollama.")
        return models
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to connect to Ollama: {e}", exc_info=True)
        st.error("Ollama is not running or not reachable. Please check the logs in app.log for more details.")
        st.stop()

def generate_response(model, messages):
    # Create a clean version of the messages for the model
    model_messages = []
    for i, msg in enumerate(messages):
        role = "user" if i == len(messages) - 1 else "assistant"
        model_messages.append({"role": role, "content": msg["content"]})

    logging.info(f"Prompt sent to {model}: {model_messages}")
    
    payload = {
        "model": model,
        "messages": model_messages,
        "stream": True,
        "system": SYSTEM_PROMPT,
    }
    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, stream=True) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        json_line = json.loads(line)
                        if "message" in json_line and "content" in json_line["message"]:
                            yield json_line["message"]["content"]
                    except json.JSONDecodeError:
                        logging.warning(f"Received non-JSON line from stream: {line}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API call to {model}: {e}", exc_info=True)
        st.error(f"An error occurred while communicating with the model: {e}")
        st.session_state.running = False
        st.rerun()

def main():
    st.title("Auto-pilot Chatting Agents")
    st.info("Select two models, enter a topic, and click 'Start' to begin the conversation.")

    models = get_models()

    # Initialize session state for agent models if not already present
    if 'agent1_model' not in st.session_state:
        st.session_state.agent1_model = models[0]
    if 'agent2_model' not in st.session_state:
        st.session_state.agent2_model = models[1] if len(models) > 1 else models[0]

    col1, col2 = st.columns(2)
    with col1:
        agent1_selection = st.selectbox(
            "Select Agent 1",
            models,
            index=models.index(st.session_state.agent1_model)
        )
        if agent1_selection != st.session_state.agent1_model:
            st.session_state.agent1_model = agent1_selection
            st.rerun()

    with col2:
        agent2_selection = st.selectbox(
            "Select Agent 2",
            models,
            index=models.index(st.session_state.agent2_model)
        )
        if agent2_selection != st.session_state.agent2_model:
            st.session_state.agent2_model = agent2_selection
            st.rerun()

    topic = st.text_input("Enter a topic for the agents to discuss", "")
    turn_limit = st.number_input("Turn limit (minutes, 0 for unlimited)", min_value=0, value=10)

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
        if st.button("Start", disabled=not topic or st.session_state.running):
            st.session_state.running = True
            st.session_state.start_time = datetime.now()
            st.session_state.finish_time = None
            st.session_state.messages = [{"role": "Agent 1", "content": topic, "timestamp": datetime.now().strftime("%H:%M:%S")}]
            st.rerun()

    with col2:
        if st.button("Stop", disabled=not st.session_state.running):
            st.session_state.running = False
            st.session_state.finish_time = datetime.now()
            st.rerun()

    if st.session_state.running:
        if turn_limit > 0 and (datetime.now() - st.session_state.start_time).total_seconds() > turn_limit * 60:
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

        logging.info(f"Current agent: {current_agent_name}, Model: {current_agent_model}")

        with st.chat_message(current_agent_name):
            message_placeholder = st.empty()
            full_response = ""
            # Check if we should stop before starting the response
            if not st.session_state.running:
                st.rerun()

            for chunk in generate_response(current_agent_model, st.session_state.messages):
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
                st.error(f"{current_agent_name} ({current_agent_model}) failed to generate a response. The conversation has been stopped.")
                logging.warning(f"Model {current_agent_model} returned an empty response.")
                st.session_state.running = False
                st.rerun()
            else:
                st.session_state.messages.append({"role": current_agent_name, "content": full_response, "timestamp": datetime.now().strftime("%H:%M:%S")})
                st.rerun()

    with col3:
        if "start_time" in st.session_state and st.session_state.start_time:
            start_time_str = st.session_state.start_time.strftime('%Y-%m-%d %H:%M:%S')
            finish_time_str = st.session_state.finish_time.strftime('%Y-%m-%d %H:%M:%S') if st.session_state.finish_time else "Not finished"
            
            chat_export = f"""
# Chat on Topic: {topic}

**Start Time:** {start_time_str}
**Finish Time:** {finish_time_str}

**Agent 1 Model:** {st.session_state.agent1_model}
**Agent 2 Model:** {st.session_state.agent2_model}

---

"""
            chat_export += "\n".join([f"**{m['role']}** ({m['timestamp']})\n{m['content']}" for m in st.session_state.messages])

            if st.download_button(
                label="Save chat",
                data=chat_export,
                file_name=f"chat_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                disabled=not st.session_state.messages
            ):
                pass

    st.chat_input("Chat input is disabled", disabled=True)

if __name__ == "__main__":
    main()
