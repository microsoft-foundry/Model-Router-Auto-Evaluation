"""Quick test: try baseline gpt-5 call using model router endpoint."""
import os
from dotenv import load_dotenv
load_dotenv()
from openai import AzureOpenAI

# Test 1: using AZURE_OPENAI_ENDPOINT (services.ai.azure.com)
print("=== Test 1: services.ai.azure.com endpoint ===")
try:
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
        api_version="2024-12-01-preview",
    )
    r = client.chat.completions.create(
        model="gpt-5", messages=[{"role": "user", "content": "Say hi"}], max_completion_tokens=10
    )
    print("SUCCESS:", r.choices[0].message.content)
except Exception as e:
    print("ERROR:", e)

# Test 2: using AZURE_MODEL_ROUTER_ENDPOINT (openai.azure.com)
print("\n=== Test 2: openai.azure.com endpoint ===")
try:
    client2 = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_MODEL_ROUTER_ENDPOINT"],
        api_key=os.environ["AZURE_MODEL_ROUTER_KEY"],
        api_version="2024-12-01-preview",
    )
    r2 = client2.chat.completions.create(
        model="gpt-5", messages=[{"role": "user", "content": "Say hi"}], max_completion_tokens=10
    )
    print("SUCCESS:", r2.choices[0].message.content)
except Exception as e:
    print("ERROR:", e)
