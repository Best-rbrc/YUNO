"""
Identity Matcher - Match face embeddings against database
Uses ArcFace embeddings with cosine similarity
Based on arcface_test.py logic with THRESHOLD = 0.45
"""

import sqlite3
import pickle
import numpy as np
from typing import Dict


# Thresholds for ArcFace cosine similarity - matching arcface_test.py
THRESHOLD = 0.45  # Cosine similarity threshold (matching arcface_test.py)
THRESHOLD_SUGGESTION = 0.40  # Minimum similarity to show as "best guess" for unknown persons


def match_identity(embedding: np.ndarray, db_path: str = None, 
                   threshold: float = THRESHOLD) -> Dict:
    """
    Match a face embedding against all stored embeddings in the database.
    
    Uses cosine similarity with ArcFace embeddings - matching arcface_test.py logic.
    
    Args:
        embedding: 512-dimensional ArcFace embedding to match
        db_path: Path to SQLite database (None = use default)
        threshold: Similarity threshold (default: 0.45, matching arcface_test.py)
    
    Returns:
        Dictionary with:
        - match_found: bool
        - person_id: int (if match found)
        - name: str (if match found)
        - similarity: float (cosine similarity, 0-1)
        - best_candidates: list of top 3 candidates with their similarities
    """
    if db_path is None:
        from src.path_manager import get_db_path
        db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Fetch all persons with embeddings
        c.execute('SELECT id, name, embedding FROM persons WHERE embedding IS NOT NULL')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {
                "match_found": False,
                "person_id": None,
                "name": None,
                "similarity": 0.0,
                "best_candidates": []
            }
        
        # Calculate similarities with all stored embeddings - matching arcface_test.py logic
        candidates = []
        
        for person_id, name, emb_blob in rows:
            stored_embedding = pickle.loads(emb_blob)
            
            # Calculate cosine similarity (simple dot product for normalized embeddings)
            similarity = cosine_similarity(embedding, stored_embedding)
            
            candidates.append({
                "person_id": person_id,
                "name": name,
                "similarity": float(similarity)
            })
        
        # Sort by similarity (descending) - matching arcface_test.py
        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Get top 3 candidates
        best_candidates = [
            {
                "person_id": c["person_id"],
                "name": c["name"],
                "similarity": c["similarity"]
            }
            for c in candidates[:3]
        ]
        
        # Check if best match exceeds threshold - matching arcface_test.py logic
        best_match = candidates[0]
        similarity = best_match["similarity"]
        
        if similarity >= threshold:
            return {
                "match_found": True,
                "person_id": best_match["person_id"],
                "name": best_match["name"],
                "similarity": similarity,
                "best_candidates": best_candidates
            }
        else:
            return {
                "match_found": False,
                "person_id": None,
                "name": None,
                "similarity": similarity,
                "best_candidates": best_candidates
            }
    
    except Exception as e:
        print(f"Error matching identity: {e}")
        return {
            "match_found": False,
            "person_id": None,
            "name": None,
            "similarity": 0.0,
            "best_candidates": []
        }


def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    For normalized embeddings (L2 norm = 1), this is just the dot product.
    Matching arcface_test.py implementation.
    Returns value between -1 and 1 (typically 0.2-0.9 for faces).
    """
    return float(np.dot(emb1, emb2))




if __name__ == "__main__":
    # Test
    print("Identity Matcher using ArcFace + Cosine Similarity")
    print(f"Thresholds:")
    print(f"  Default threshold: {THRESHOLD} (matching arcface_test.py)")
    print(f"  Suggestion threshold: {THRESHOLD_SUGGESTION}")
