import csv
import os
import uuid
from typing import List
from typing_extensions import TypedDict

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.agents import create_agent
from langgraph.store.base import BaseStore

# Import AgentCore runtime and memory integrations
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph_checkpoint_aws import AgentCoreMemorySaver, AgentCoreMemoryStore
from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, ModelResponse
from dotenv import load_dotenv

_ = load_dotenv()

app = BedrockAgentCoreApp()
# AgentCore Memory Configuration
REGION = "us-east-2"
MEMORY_ID = "quaki_customer_care_agent_memory-nzvliw7L6V"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize memory components
checkpointer = AgentCoreMemorySaver(memory_id=MEMORY_ID)
store = AgentCoreMemoryStore(memory_id=MEMORY_ID)


def load_faq_csv(path: str) -> List[Document]:
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row["question"].strip()
            a = row["answer"].strip()
            docs.append(Document(page_content=f"Q: {q}\nA: {a}"))
    return docs


docs = load_faq_csv("./lauki_qna.csv")
emb = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
chunks = splitter.split_documents(docs)
faq_store = FAISS.from_documents(chunks, emb)


@tool
def search_faq(query: str) -> str:
    """Search the FAQ knowledge base for relevant information.
    Use this tool when the user asks questions about products, services, or policies.
    
    Args:
        query: The search query to find relevant FAQ entries
        
    Returns:
        The most relevant FAQ entry
    """
    # Only get top 1 result to minimize token usage (Groq free tier has 6000 TPM limit)
    results = faq_store.similarity_search(query, k=1)
    
    if not results:
        return "No relevant FAQ entries found."
    
    return results[0].page_content


@tool
def search_detailed_faq(query: str) -> str:
    """Search the FAQ knowledge base with more results for complex queries.
    Use this only when the first search doesn't have the answer.
    
    Args:
        query: The search query
        
    Returns:
        Top 2 FAQ entries
    """
    # Limited to 2 results to stay under Groq free tier limits
    results = faq_store.similarity_search(query, k=2)
    
    if not results:
        return "No relevant FAQ entries found."
    
    return "\n---\n".join([doc.page_content for doc in results])


# Simplified to single tool to reduce token usage
tools = [search_faq]


class MemoryMiddleware(AgentMiddleware):
    # Pre-model hook: saves messages and retrieves long-term memories
    def pre_model_hook(self, state: AgentState, config: RunnableConfig, *, store: BaseStore):
        """
        Hook that runs before LLM invocation to:
        1. Save the latest human message to long-term memory
        2. Retrieve relevant user preferences and memories
        3. Append memories to the context
        """
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        
        # Namespace for this specific session
        namespace = (actor_id, thread_id)
        messages = state.get("messages", [])
        
        # Save the last human message to long-term memory
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                store.put(namespace, str(uuid.uuid4()), {"message": msg})
                
                # OPTIONAL: Retrieve user preferences from long-term memory
                # Search across all sessions for this actor
                user_preferences_namespace = ("preferences", actor_id)
                try:
                    preferences = store.search(
                        user_preferences_namespace, 
                        query=msg.content, 
                        limit=5
                    )
                    
                    # If we found relevant memories, add them to the context
                    if preferences:
                        memory_context = "\n".join([
                            f"Memory: {item.value.get('message', '')}" 
                            for item in preferences
                        ])
                        # You can append this to the messages or use it another way
                        print(f"Retrieved memories: {memory_context}")
                except Exception as e:
                    print(f"Memory retrieval error: {e}")
                break
        
        return {"messages": messages}


    # OPTIONAL: Post-model hook to save AI responses
    def post_model_hook(state, config: RunnableConfig, *, store: BaseStore):
        """
        Hook that runs after LLM invocation to save AI messages to long-term memory
        """
        actor_id = config["configurable"]["actor_id"]
        thread_id = config["configurable"]["thread_id"]
        namespace = (actor_id, thread_id)
        
        messages = state.get("messages", [])
        
        # Save the last AI message
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                store.put(namespace, str(uuid.uuid4()), {"message": msg})
                break
        
        return state


# Initialize the LLM - Using OpenAI for better rate limits and instruction following
llm = ChatOpenAI(
    model="gpt-4o-mini",  # Fast and affordable
    temperature=0,
    api_key=OPENAI_API_KEY,
    max_tokens=300
)

system_prompt = """You are a helpful FAQ assistant for Lauki Phones telecom.

When you receive a question:
1. Use the search_faq tool to find the answer
2. Read the tool result carefully
3. Respond with the information from the tool result

Keep responses to 2-3 sentences. Do not use tables or bullet lists."""


# AgentCore Entrypoint
@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation in AgentCore runtime with memory support"""
    print("=== NEW INVOCATION ===")
    print("Received payload:", payload)
    print("Context:", context)
    
    # Extract query from payload - check multiple possible keys
    query = payload.get("input") or payload.get("prompt") or payload.get("query") or payload.get("message")
    print(f"Extracted query: {query}")
    
    if not query:
        return {"result": "No input provided. Please send a message.", "error": True}
    
    # Create a FRESH agent for each invocation to avoid state issues
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )
    
    # Invoke the agent with the query
    print(f"Invoking agent with query: {query}")
    result = agent.invoke({"messages": [("human", query)]})
    
    print("Agent result:", result)
    
    # Extract the final answer from the result
    messages = result.get("messages", [])
    answer = messages[-1].content if messages else "No response generated"
    
    # Return the answer
    return {
        "result": answer,
        "query": query
    }


if __name__ == "__main__":
    app.run()