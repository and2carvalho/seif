"""
SEIF Fingerprint Module

Calculates and verifies cryptographic fingerprints for SEIF modules.
Fingerprint = sha256 of JSON content excluding the fingerprint field itself.
This ensures tamper detection: any modification to content breaks the hash.
"""

import hashlib
import json
from typing import Optional


def calculate_fingerprint(data: dict, algorithm: str = "sha256") -> str:
    """
    Calculate fingerprint hash of SEIF data.
    
    Args:
        data: SEIF module or RESONANCE.json as dict
        algorithm: Hash algorithm (default: sha256)
    
    Returns:
        Hex digest of the hash
    """
    clean_data = data.copy()
    clean_data.pop('fingerprint', None)
    clean_data.pop('integrity_hash', None)
    
    json_str = json.dumps(clean_data, separators=(',', ':'), ensure_ascii=False)
    
    if algorithm == "sha256":
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(json_str.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def verify_fingerprint(data: dict, expected_hash: Optional[str] = None) -> tuple[bool, str]:
    """
    Verify fingerprint of SEIF data.
    
    Args:
        data: SEIF module or RESONANCE.json as dict
        expected_hash: Expected hash (if None, reads from fingerprint.value)
    
    Returns:
        (is_valid, calculated_hash)
    """
    fingerprint = data.get('fingerprint', {})
    expected = expected_hash or fingerprint.get('value', '')
    
    if not expected or expected == '<calculate_on_save>':
        return False, calculate_fingerprint(data)
    
    calculated = calculate_fingerprint(data)
    return calculated == expected, calculated


def add_fingerprint(data: dict, save: bool = True, filepath: Optional[str] = None) -> dict:
    """
    Add or update fingerprint to SEIF data and optionally save to file.
    
    Args:
        data: SEIF module or RESONANCE.json as dict
        save: Whether to save to file
        filepath: Path to file (required if save=True)
    
    Returns:
        Data with fingerprint added
    """
    fp_hash = calculate_fingerprint(data)
    
    data['fingerprint'] = {
        'algorithm': 'sha256',
        'value': fp_hash,
        'scope': 'full_json_excluding_fingerprint',
        'calculated_at': 'auto'
    }
    
    if save and filepath:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data


def remove_fingerprint_field(data: dict) -> dict:
    """Remove fingerprint field from data for clean serialization."""
    clean = data.copy()
    clean.pop('fingerprint', None)
    return clean
