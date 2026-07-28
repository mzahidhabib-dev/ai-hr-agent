from src.retrieval.vector_search import vector_search
from src.retrieval.bm25_search import BM25Index
from src.retrieval.self_query import rewrite_query

def hybrid_search(query: str, document_id: str, top_k: int = 10, retrieval_method: str = "hybrid") -> list[dict]:
    """Combines semantic search and BM25 search mathematically using Reciprocal Rank Fusion."""
    
    if retrieval_method == "vector":
        return vector_search(query, document_id, top_k)
    elif retrieval_method == "bm25":
        index = BM25Index(document_id)
        return index.search(query, top_k)
        
    # Hybrid fusion
    pool_size = max(top_k * 3, 20)
    
    semantic_results = vector_search(query, document_id, top_k=pool_size)
    bm25_index = BM25Index(document_id)
    bm25_results = bm25_index.search(query, top_k=pool_size)
    
    k = 60
    rrf_scores = {}
    
    for rank, res in enumerate(semantic_results, 1):
        cid = res["chunk_id"]
        if cid not in rrf_scores:
            rrf_scores[cid] = {"data": res, "score": 0.0}
        rrf_scores[cid]["score"] += 1.0 / (k + rank)
        
    for rank, res in enumerate(bm25_results, 1):
        cid = res["chunk_id"]
        if cid not in rrf_scores:
            rrf_scores[cid] = {"data": res, "score": 0.0}
        rrf_scores[cid]["score"] += 1.0 / (k + rank)
        
    sorted_chunks = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)
    
    final_results = []
    for item in sorted_chunks[:top_k]:
        row = item["data"].copy() # Don't mutate original
        row["score"] = item["score"]
        final_results.append(row)
        
    return final_results

def search_with_self_query(user_question: str, document_id: str, top_k: int = 10) -> list[dict]:
    """
    Rewrites the question via Gemini, runs hybrid search, and boosts scores of the preferred chunk type.
    """
    query_data = rewrite_query(user_question)
    search_query = query_data.get("search_query", user_question)
    preferred_type = query_data.get("preferred_chunk_type", "any")
    
    print(f"\n[DEBUG] Original: '{user_question}'\n[DEBUG] Rewritten: '{search_query}' (Prefers: {preferred_type})")
    
    results = hybrid_search(search_query, document_id, top_k=max(top_k * 2, 20))
    
    if preferred_type != "any":
        for result in results:
            if result["chunk_type"] == preferred_type:
                result["score"] *= 1.3
                
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
