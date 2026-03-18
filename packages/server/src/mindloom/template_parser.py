"""Template parsing utilities for job dependencies.

This module provides functions to extract job ID references from template strings
and replace them with actual job results.
"""

import re
from typing import Optional


def extract_job_ids(content: str) -> list[int]:
    """Extract all job IDs from template placeholders in content.
    
    Finds all occurrences of {{job_id}} pattern where job_id is an integer.
    Returns a sorted list of unique job IDs.
    
    Args:
        content: String that may contain template placeholders like {{123456}}
        
    Returns:
        List of unique job IDs found in the content, sorted ascending
        
    Examples:
        >>> extract_job_ids("Summarize {{123}} and compare with {{456}}")
        [123, 456]
        >>> extract_job_ids("No templates here")
        []
        >>> extract_job_ids("Same job twice: {{100}} and {{100}}")
        [100]
    """
    if not content:
        return []
    
    # Pattern matches {{digits}}
    pattern = r'\{\{(\d+)\}\}'
    matches = re.findall(pattern, content)
    
    # Convert to integers, remove duplicates, and sort
    job_ids = sorted(set(int(match) for match in matches))
    return job_ids


def replace_templates(content: str, job_results: dict[int, str]) -> str:
    """Replace template placeholders with actual job results.
    
    Replaces all {{job_id}} placeholders in content with the corresponding
    result from job_results dictionary. If a job_id is not in the dictionary,
    it is left unchanged.
    
    Args:
        content: String containing template placeholders
        job_results: Dictionary mapping job IDs to their result strings
        
    Returns:
        String with all placeholders replaced by their corresponding results
        
    Examples:
        >>> replace_templates("Summary: {{100}}", {100: "Hello world"})
        'Summary: Hello world'
        >>> replace_templates("{{1}} and {{2}}", {1: "First", 2: "Second"})
        'First and Second'
    """
    if not content:
        return content
    
    def replacer(match: re.Match) -> str:
        job_id = int(match.group(1))
        # If job_id not in results, keep the placeholder
        return job_results.get(job_id, match.group(0))
    
    pattern = r'\{\{(\d+)\}\}'
    return re.sub(pattern, replacer, content)


def validate_template(content: str) -> Optional[str]:
    """Validate template syntax.
    
    Checks if the template has valid syntax. Returns None if valid,
    or an error message string if invalid.
    
    Args:
        content: String to validate
        
    Returns:
        None if valid, error message string if invalid
        
    Examples:
        >>> validate_template("Valid {{123}} template")
        None
        >>> validate_template("Invalid {{abc}} template")
        'Invalid template placeholder: {{abc}}'
    """
    if not content:
        return None
    
    # Check for invalid placeholders (non-digit content)
    invalid_pattern = r'\{\{([^}]*)\}\}'
    matches = re.finditer(invalid_pattern, content)
    
    for match in matches:
        inner = match.group(1)
        if not inner.isdigit():
            return f"Invalid template placeholder: {match.group(0)}"
    
    # Check for unmatched braces
    open_count = content.count('{{')
    close_count = content.count('}}')
    if open_count != close_count:
        return "Unmatched template braces"
    
    return None
