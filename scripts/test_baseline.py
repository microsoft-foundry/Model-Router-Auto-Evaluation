"""Quick test: try the configured Foundry v1 endpoints."""
import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

print("=== Test 1: baseline Responses API ===")
try:
    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_KEY"],
    )
    r = client.responses.create(
        model=os.environ["AZURE_BASELINE_DEPLOYMENT"],
        input="Say hi",
        max_output_tokens=32,
    )
    print("SUCCESS:", r.output_text)
except Exception as e:
    print("ERROR:", e)

print("\n=== Test 2: Model Router Chat Completions API ===")
try:
    client2 = OpenAI(
        base_url=os.environ["AZURE_MODEL_ROUTER_ENDPOINT"],
        api_key=os.environ["AZURE_MODEL_ROUTER_KEY"],
    )
    r2 = client2.chat.completions.create(
        model=os.environ["AZURE_MODEL_ROUTER_DEPLOYMENT"],
        messages=[{"role": "user", "content": "Say hi"}],
        max_completion_tokens=32,
    )
    print("SUCCESS:", r2.choices[0].message.content)
except Exception as e:
    print("ERROR:", e)

print("\n=== Test 3: judge Responses API ===")
try:
    client3 = OpenAI(
        base_url=os.environ["AZURE_JUDGE_ENDPOINT"],
        api_key=os.environ["AZURE_JUDGE_KEY"],
    )
    r3 = client3.responses.create(
        model=os.environ["AZURE_JUDGE_DEPLOYMENT"],
        input="Reply with OK",
        max_output_tokens=32,
    )
    print("SUCCESS:", r3.output_text)
except Exception as e:
    print("ERROR:", e)
