"""Pseudonymous learner ids for research data (decision D11).

One keyed hash (HMAC-SHA256 with the study's secret salt) used by both the admin CSV export and
research/analysis/export.py, so the two always agree. Without the salt the ids cannot be linked
back to accounts; keep ANALYSIS_SALT secret and fixed for the whole study.
"""

import hashlib
import hmac


def pseudonym(user_id: object, salt: str) -> str:
    if not salt:
        raise ValueError("a pseudonym needs the study's secret salt")
    return hmac.new(salt.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()[:12]
