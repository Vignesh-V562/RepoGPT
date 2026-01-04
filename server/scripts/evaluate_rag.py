import os
import sys
import asyncio
import random
import json
import logging
from google import genai
from dotenv import load_dotenv

# Add server directory to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.supabase_client import supabase
from app.rag import query_repo

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL_NAME = 'gemini-2.0-flash'

async def generate_synthetic_questions(repo_id: str, count: int = 3):
    """
    Randomly selects file summaries and generates specific technical questions.
    """
    logger.info(f"--- Generating {count} synthetic questions for repo {repo_id} ---")
    
    res = supabase.table("file_summaries").select("file_path, summary").eq("repository_id", repo_id).limit(30).execute()
    
    if not res.data:
        logger.error("No file summaries found for this repo. Ensure ingestion is complete.")
        return []

    # Pick random files to test
    samples = random.sample(res.data, min(len(res.data), count))
    test_set = []
    
    for sample in samples:
        prompt = f"""
        Analyze this file summary for '{sample['file_path']}' and generate ONE specific, technical question 
        that would require understanding the code in this file to answer.
        
        Summary: {sample['summary']}
        
        Question:
        """
        try:
            resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            question_text = resp.text.strip().strip('"')
            test_set.append({
                "question": question_text,
                "file_path": sample['file_path'],
                "ground_truth_context": sample['summary']
            })
            logger.info(f"Generated Q: {question_text}")
        except Exception as e:
            logger.error(f"Failed to generate question for {sample['file_path']}: {e}")
    
    return test_set

async def evaluate_answer(question: str, answer: str, context: str):
    """
    LLM-as-a-judge evaluation for Faithfulness and Relevancy.
    """
    prompt = f"""
    Evaluate the following RAG (Retrieval-Augmented Generation) output.
    
    QUESTION: {question}
    CONTEXT (Source Knowledge): {context}
    ANSWER (Model Output): {answer}
    
    Assign a score from 1-10 for:
    1. FAITHFULNESS: Is the answer entirely derived from the context? Does it avoid hallucinations?
    2. RELEVANCY: Does the answer directly and comprehensively address the question?
    
    Return ONLY a JSON object:
    {{
        "faithfulness": <score>,
        "relevancy": <score>,
        "explanation": "<short reasoning>"
    }}
    """
    
    try:
        resp = client.models.generate_content(
            model=MODEL_NAME, 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(resp.text)
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return {"faithfulness": 0, "relevancy": 0, "explanation": str(e)}

async def run_evaluation(repo_id_arg=None):
    """
    Main evaluation loop.
    """
    if repo_id_arg:
        repo_res = supabase.table("repositories").select("id, name").eq("id", repo_id_arg).execute()
    else:
        # Get the most recently indexed 'ready' repo
        repo_res = supabase.table("repositories").select("id, name").eq("status", "ready").order("created_at", desc=True).limit(1).execute()
    
    if not repo_res.data:
        logger.error("No suitable repository found for evaluation.")
        return

    repo = repo_res.data[0]
    logger.info(f"Starting Evaluation for: {repo['name']} (ID: {repo['id']})")
    
    questions = await generate_synthetic_questions(repo['id'])
    
    results = []
    for test in questions:
        logger.info(f"\n--- Testing Question: {test['question']} ---")
        
        full_answer = ""
        # Simulate streaming response aggregation
        async for event in query_repo(repo['id'], test['question']):
            if isinstance(event, dict) and event.get("type") == "token":
                full_answer += event["content"]
        
        logger.info(f"RAG Answer Generated ({len(full_answer)} chars)")
        
        metrics = await evaluate_answer(test['question'], full_answer, test['ground_truth_context'])
        results.append({
            "test": test,
            "answer": full_answer,
            "metrics": metrics
        })
        
        print(f"   [RESULT] Faithfulness: {metrics['faithfulness']}/10 | Relevancy: {metrics['relevancy']}/10")
        print(f"   [WHY] {metrics['explanation']}")

    if results:
        print("\n" + "="*40)
        print("📊 AGGREGATE EVALUATION REPORT")
        print("="*40)
        avg_f = sum(r['metrics']['faithfulness'] for r in results) / len(results)
        avg_r = sum(r['metrics']['relevancy'] for r in results) / len(results)
        print(f"Average Faithfulness Score: {avg_f:.2f} / 10.0")
        print(f"Average Relevancy Score:    {avg_r:.2f} / 10.0")
        print("="*40)

if __name__ == "__main__":
    import sys
    # Optional repo_id as cmd line arg
    target_repo = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_evaluation(target_repo))
