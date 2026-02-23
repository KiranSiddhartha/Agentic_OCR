# """
# Embedding-based Document & Policy Classifier
# --------------------------------------------
# - sentence-transformers (MiniLM)
# - NOT an LLM
# - Deterministic
# - Lazy-loaded
# - Safe fallback compatible
# """

# import os
# import joblib
# import numpy as np
# from sentence_transformers import SentenceTransformer

# # ============================================================
# # PATH SETUP (ABSOLUTE, STABLE)
# # ============================================================

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# MODEL_DIR = os.path.join(BASE_DIR, "models")

# DOC_MODEL_PATH = os.path.join(MODEL_DIR, "doc_type_clf.joblib")
# POLICY_MODEL_PATH = os.path.join(MODEL_DIR, "policy_type_clf.joblib")

# # ============================================================
# # EMBEDDING MODEL (LOAD ONCE)
# # ============================================================

# MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# _EMBEDDER = SentenceTransformer(MODEL_NAME)

# _doc_clf = None
# _policy_clf = None

# # ============================================================
# # INTERNAL LOADERS (LAZY)
# # ============================================================

# def _load_doc_model():
#     global _doc_clf
#     if _doc_clf is None:
#         if not os.path.exists(DOC_MODEL_PATH):
#             raise FileNotFoundError(f"Missing document model: {DOC_MODEL_PATH}")
#         _doc_clf = joblib.load(DOC_MODEL_PATH)
#     return _doc_clf


# def _load_policy_model():
#     global _policy_clf
#     if _policy_clf is None:
#         if not os.path.exists(POLICY_MODEL_PATH):
#             raise FileNotFoundError(f"Missing policy model: {POLICY_MODEL_PATH}")
#         _policy_clf = joblib.load(POLICY_MODEL_PATH)
#     return _policy_clf

# # ============================================================
# # HELPERS
# # ============================================================

# def _embed(lines: list[str]) -> np.ndarray:
#     text = " ".join(lines).lower().strip()
#     if not text:
#         raise ValueError("Empty text for embedding")
#     return _EMBEDDER.encode([text])

# # ============================================================
# # PUBLIC API (USED BY ORCHESTRATOR)
# # ============================================================

# def classify_document_ml(lines: list[str]) -> str:
#     """
#     Returns document type.
#     Raises exception if model missing → orchestrator fallback.
#     """
#     clf = _load_doc_model()
#     vec = _embed(lines)
#     return clf.predict(vec)[0]


# def classify_policy_ml(lines: list[str]) -> str:
#     """
#     Returns policy type.
#     Raises exception if model missing → orchestrator fallback.
#     """
#     clf = _load_policy_model()
#     vec = _embed(lines)
#     return clf.predict(vec)[0]


"""
Embedding-based Document & Policy Classifier - ENHANCED (SESSION 3)
-------------------------------------------------------------------
Improvements:
1. Better feature engineering
2. Type-specific keyword extraction
3. Confidence scoring
4. Fallback handling
5. Better error messages

Uses sentence-transformers (MiniLM) - NOT an LLM
Deterministic and fast with lazy loading
"""

import os
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# PATH SETUP (ABSOLUTE, STABLE)
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

DOC_MODEL_PATH = os.path.join(MODEL_DIR, "doc_type_clf.joblib")
POLICY_MODEL_PATH = os.path.join(MODEL_DIR, "policy_type_clf.joblib")

# ============================================================
# EMBEDDING MODEL (LOAD ONCE)
# ============================================================

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_EMBEDDER = None
_doc_clf = None
_policy_clf = None

# ============================================================
# TYPE-SPECIFIC KEYWORDS (FEATURE ENGINEERING)
# ============================================================

DOC_TYPE_KEYWORDS = {
    "RNW": {
        "policy declarations", "declarations page", "mortgagee declarations",
        "coverage a", "coverage b", "coverage c", "annual premium",
        "policy period", "effective date", "expiration date",
    },
    "INV": {
        "invoice", "bill", "balance due", "amount due", "remit to",
        "payment due", "minimum due", "processed on", "billing",
    },
    "CAN": {
        "notice of cancellation", "cancellation", "cancelled effective",
        "non-payment", "non-renewal", "borrower request",
        "company cancelled", "terminate this policy",
    },
    "DOI": {
        "deletion of interest", "interest removed", "mortgage removed",
        "terminate the interest", "third party notice",
    },
    "RNS": {
        "reinstatement", "rescission", "policy reinstated",
        "reactivated", "lapse",
    },
    "COI": {
        "certificate of insurance", "acord", "certificate holder",
        "this certificate is issued",
    },
    "FPN": {
        "force placed", "lender-placed", "insurance will be purchased",
        "required coverage", "force-place",
    },
}

POLICY_TYPE_KEYWORDS = {
    "HO": {
        "homeowners", "coverage a", "coverage b", "coverage c",
        "dwelling", "other structures", "personal property",
        "loss of use", "residence premises",
    },
    "FLD": {
        "flood", "nfip", "fema", "flood insurance",
    },
    "FIR": {
        "dwelling fire", "dp-3", "dp-1", "fire policy",
    },
    "AUTO": {
        "automobile", "vehicle", "vin", "auto policy",
    },
    "HAZ": {
        "commercial property", "property protection",
        "buildings - replacement cost", "lessor risk",
    },
}


# ============================================================
# LAZY LOADING
# ============================================================

def _get_embedder():
    """Get or initialize embedder (lazy loading)"""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            _EMBEDDER = SentenceTransformer(MODEL_NAME)
            logger.info(f"[EMBEDDING] Loaded model: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"[EMBEDDING] Failed to load model: {e}")
            raise
    return _EMBEDDER


def _load_doc_model():
    """Load document classifier (lazy loading)"""
    global _doc_clf
    if _doc_clf is None:
        if not os.path.exists(DOC_MODEL_PATH):
            logger.warning(f"[EMBEDDING] Document model not found: {DOC_MODEL_PATH}")
            raise FileNotFoundError(f"Missing document model: {DOC_MODEL_PATH}")
        _doc_clf = joblib.load(DOC_MODEL_PATH)
        logger.info("[EMBEDDING] Loaded document classifier")
    return _doc_clf


def _load_policy_model():
    """Load policy classifier (lazy loading)"""
    global _policy_clf
    if _policy_clf is None:
        if not os.path.exists(POLICY_MODEL_PATH):
            logger.warning(f"[EMBEDDING] Policy model not found: {POLICY_MODEL_PATH}")
            raise FileNotFoundError(f"Missing policy model: {POLICY_MODEL_PATH}")
        _policy_clf = joblib.load(POLICY_MODEL_PATH)
        logger.info("[EMBEDDING] Loaded policy classifier")
    return _policy_clf


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def _extract_keyword_features(text: str, keyword_dict: dict) -> np.ndarray:
    """
    Extract keyword-based features for classification.
    
    Args:
        text: Document text
        keyword_dict: Dictionary of type -> keywords
        
    Returns:
        Feature vector with keyword counts
    """
    text_lower = text.lower()
    features = []
    
    for doc_type in sorted(keyword_dict.keys()):
        keywords = keyword_dict[doc_type]
        count = sum(1 for kw in keywords if kw in text_lower)
        features.append(count)
    
    return np.array(features)


def _combine_features(embedding: np.ndarray, keyword_features: np.ndarray) -> np.ndarray:
    """
    Combine embedding and keyword features.
    
    Args:
        embedding: Sentence embedding
        keyword_features: Keyword count features
        
    Returns:
        Combined feature vector
    """
    # Normalize keyword features (0-1 range)
    max_val = keyword_features.max() if keyword_features.max() > 0 else 1
    normalized_keywords = keyword_features / max_val
    
    # Concatenate
    return np.concatenate([embedding, normalized_keywords])


def _embed(lines: list[str], use_keywords: bool = True, keyword_dict: dict = None) -> np.ndarray:
    """
    Create embedding with optional keyword features.
    
    Args:
        lines: Text lines
        use_keywords: Whether to include keyword features
        keyword_dict: Keyword dictionary for features
        
    Returns:
        Feature vector
    """
    text = " ".join(lines).lower().strip()
    if not text:
        raise ValueError("Empty text for embedding")
    
    embedder = _get_embedder()
    embedding = embedder.encode([text])[0]
    
    if use_keywords and keyword_dict:
        keyword_features = _extract_keyword_features(text, keyword_dict)
        return _combine_features(embedding, keyword_features).reshape(1, -1)
    
    return embedding.reshape(1, -1)


# ============================================================
# CONFIDENCE ESTIMATION
# ============================================================

def _estimate_confidence(clf, features: np.ndarray) -> float:
    """
    Estimate classification confidence.
    
    Args:
        clf: Classifier model
        features: Feature vector
        
    Returns:
        Confidence score (0-1)
    """
    try:
        # Get probability estimates
        if hasattr(clf, 'predict_proba'):
            probas = clf.predict_proba(features)[0]
            confidence = float(probas.max())
            return confidence
        else:
            # Fallback: use decision function
            if hasattr(clf, 'decision_function'):
                scores = clf.decision_function(features)[0]
                # Convert to pseudo-probability
                if isinstance(scores, np.ndarray):
                    confidence = float(np.exp(scores.max()) / np.exp(scores).sum())
                else:
                    confidence = 0.85  # Default
                return confidence
    except Exception as e:
        logger.warning(f"[EMBEDDING] Confidence estimation failed: {e}")
    
    return 0.85  # Default confidence


# ============================================================
# PUBLIC API (ENHANCED)
# ============================================================

def classify_document_ml(lines: list[str]) -> Tuple[str, float]:
    """
    Classify document type with confidence.
    
    Args:
        lines: Document text lines
        
    Returns:
        Tuple of (document_type, confidence)
    """
    try:
        clf = _load_doc_model()
        vec = _embed(lines, use_keywords=True, keyword_dict=DOC_TYPE_KEYWORDS)
        
        prediction = clf.predict(vec)[0]
        confidence = _estimate_confidence(clf, vec)
        
        logger.info(f"[EMBEDDING] Document classified as {prediction} (confidence: {confidence:.2f})")
        return prediction, confidence
        
    except Exception as e:
        logger.error(f"[EMBEDDING] Document classification failed: {e}")
        raise


def classify_policy_ml(lines: list[str]) -> Tuple[str, float]:
    """
    Classify policy type with confidence.
    
    Args:
        lines: Document text lines
        
    Returns:
        Tuple of (policy_type, confidence)
    """
    try:
        clf = _load_policy_model()
        vec = _embed(lines, use_keywords=True, keyword_dict=POLICY_TYPE_KEYWORDS)
        
        prediction = clf.predict(vec)[0]
        confidence = _estimate_confidence(clf, vec)
        
        logger.info(f"[EMBEDDING] Policy classified as {prediction} (confidence: {confidence:.2f})")
        return prediction, confidence
        
    except Exception as e:
        logger.error(f"[EMBEDDING] Policy classification failed: {e}")
        raise


# ============================================================
# BACKWARD COMPATIBILITY (without confidence)
# ============================================================

def classify_document_ml_simple(lines: list[str]) -> str:
    """Classify document type (backward compatible - no confidence)"""
    doc_type, _ = classify_document_ml(lines)
    return doc_type


def classify_policy_ml_simple(lines: list[str]) -> str:
    """Classify policy type (backward compatible - no confidence)"""
    policy_type, _ = classify_policy_ml(lines)
    return policy_type


# ============================================================
# MODEL TRAINING UTILITIES (for future use)
# ============================================================

def prepare_training_features(texts: list[str], labels: list[str], keyword_dict: dict) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare features for model training.
    
    Args:
        texts: List of document texts
        labels: List of labels
        keyword_dict: Keyword dictionary for feature engineering
        
    Returns:
        Tuple of (features, labels)
    """
    embedder = _get_embedder()
    
    features_list = []
    for text in texts:
        # Get embedding
        embedding = embedder.encode([text])[0]
        
        # Get keyword features
        keyword_features = _extract_keyword_features(text, keyword_dict)
        
        # Combine
        combined = _combine_features(embedding, keyword_features)
        features_list.append(combined)
    
    features = np.vstack(features_list)
    labels_array = np.array(labels)
    
    return features, labels_array


def train_classifier(features: np.ndarray, labels: np.ndarray, model_type: str = "svm"):
    """
    Train a classifier on features.
    
    Args:
        features: Feature matrix
        labels: Label array
        model_type: Type of classifier ("svm", "rf", "lr")
        
    Returns:
        Trained classifier
    """
    from sklearn.svm import SVC
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    
    if model_type == "svm":
        clf = SVC(kernel='rbf', probability=True, random_state=42)
    elif model_type == "rf":
        clf = RandomForestClassifier(n_estimators=100, random_state=42)
    elif model_type == "lr":
        clf = LogisticRegression(max_iter=1000, random_state=42)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    clf.fit(features, labels)
    return clf


def save_classifier(clf, model_path: str):
    """Save trained classifier"""
    joblib.dump(clf, model_path)
    logger.info(f"[EMBEDDING] Saved classifier to {model_path}")


# ============================================================
# DIAGNOSTICS
# ============================================================

def get_classification_details(lines: list[str], doc_type: bool = True) -> dict:
    """
    Get detailed classification information for debugging.
    
    Args:
        lines: Document text lines
        doc_type: True for document type, False for policy type
        
    Returns:
        Dictionary with classification details
    """
    try:
        if doc_type:
            clf = _load_doc_model()
            keyword_dict = DOC_TYPE_KEYWORDS
        else:
            clf = _load_policy_model()
            keyword_dict = POLICY_TYPE_KEYWORDS
        
        vec = _embed(lines, use_keywords=True, keyword_dict=keyword_dict)
        
        prediction = clf.predict(vec)[0]
        confidence = _estimate_confidence(clf, vec)
        
        # Get keyword matches
        text = " ".join(lines).lower()
        keyword_matches = {}
        for type_name, keywords in keyword_dict.items():
            matches = [kw for kw in keywords if kw in text]
            if matches:
                keyword_matches[type_name] = matches
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "keyword_matches": keyword_matches,
            "feature_dimension": vec.shape[1],
        }
        
    except Exception as e:
        logger.error(f"[EMBEDDING] Failed to get classification details: {e}")
        return {
            "prediction": "UNK",
            "confidence": 0.0,
            "error": str(e),
        }