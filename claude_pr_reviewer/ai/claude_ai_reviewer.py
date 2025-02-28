"""
Claude AI reviewer implementation using the Claude API.
"""

import requests
from typing import List, Dict, Any
from claude_pr_reviewer.interfaces import AIReviewerInterface


class ClaudeAIReviewer(AIReviewerInterface):
    """Concrete implementation of AIReviewerInterface using Claude API"""
    
    def __init__(self, api_key: str):
        """Initialize with Claude API key"""
        self.api_key = api_key
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    
    def review_code(self, diff: str, commit_msg: str, branch: str) -> Dict[str, Any]:
        """Review the code using Claude AI and return the results"""
        # Check if there's anything to review
        if not diff.strip():
            return {
                "review_text": "No changes to review.",
                "suggestions": [],
                "issues": [],
                "raw_response": {},
                "diff": ""
            }
            
        prompt = self._create_prompt(diff, commit_msg, branch)
        
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Ensure we have valid content to work with
            review_text = ""
            if "content" in result and len(result["content"]) > 0 and "text" in result["content"][0]:
                review_text = result["content"][0]["text"]
            else:
                review_text = "Could not extract review text from API response."
                
            return {
                "review_text": review_text,
                "suggestions": self._extract_suggestions(review_text),
                "issues": self._extract_issues(review_text),
                "raw_response": result,
                "diff": diff  # Include the diff for side-by-side view
            }
        except requests.RequestException as e:
            return {
                "error": str(e),
                "review_text": f"Error calling Claude API: {e}",
                "suggestions": [],
                "issues": [],
                "diff": diff,  # Include the diff even on error
                "raw_response": {}
            }
    
    def _create_prompt(self, diff: str, commit_msg: str, branch: str) -> str:
        """Create the prompt for Claude"""
        return f"""Please review the following git diff for a commit on branch "{branch}" with commit message: "{commit_msg}".

Focus on:
1. Potential bugs or issues
2. Security concerns
3. Code quality and maintainability
4. Suggestions for improvement

Format your response with these sections:
- Summary: Brief overview of the changes
- Issues: List any problems that should be fixed (prioritized)
- Suggestions: Optional improvements that would be nice to have
- Questions: Anything that needs clarification

Here's the diff:
```
{diff}
```

Please be concise and focus on the most important points. If you find critical issues that should block the commit, start your response with "CRITICAL ISSUES FOUND".
"""
    
    def _extract_suggestions(self, review_text: str) -> List[str]:
        """Extract suggestions from the review text"""
        if not review_text:
            return []
            
        suggestions = []
        in_suggestions_section = False
        
        try:
            for line in review_text.split('\n'):
                # Check for section headers in various formats
                if 'suggestion' in line.lower() or 'improvement' in line.lower():
                    in_suggestions_section = True
                    continue
                elif in_suggestions_section and (line.startswith('- ') or line.startswith('* ')):
                    suggestions.append(line[2:].strip())
                elif in_suggestions_section and (line.startswith('#') or line == '' or 
                                               'issue' in line.lower() or 
                                               'question' in line.lower() or
                                               'summary' in line.lower()):
                    in_suggestions_section = False
            
            # If we didn't find any formatted suggestions, look for any lines with suggestion-like content
            if not suggestions:
                for line in review_text.split('\n'):
                    if ('suggest' in line.lower() or 'could' in line.lower() or 'would be better' in line.lower()) and len(line) > 10:
                        suggestions.append(line.strip())
                        
            return suggestions[:10]  # Limit to 10 suggestions
        except Exception:
            return []
    
    def _extract_issues(self, review_text: str) -> List[str]:
        """Extract issues from the review text"""
        if not review_text:
            return []
            
        issues = []
        in_issues_section = False
        
        try:
            for line in review_text.split('\n'):
                # Check for section headers in various formats
                if 'issue' in line.lower() or 'problem' in line.lower() or 'bug' in line.lower():
                    in_issues_section = True
                    continue
                elif in_issues_section and (line.startswith('- ') or line.startswith('* ')):
                    issues.append(line[2:].strip())
                elif in_issues_section and (line.startswith('#') or line == '' or
                                          'suggestion' in line.lower() or
                                          'question' in line.lower() or
                                          'summary' in line.lower()):
                    in_issues_section = False
            
            # If we didn't find any formatted issues, look for any lines with issue-like content
            if not issues:
                for line in review_text.split('\n'):
                    if ('issue' in line.lower() or 'bug' in line.lower() or 'error' in line.lower() or 'fix' in line.lower()) and len(line) > 10:
                        issues.append(line.strip())
            
            # Also check for critical issues at the beginning
            if review_text and "CRITICAL ISSUES FOUND" in review_text[:100]:
                issues.insert(0, "CRITICAL ISSUES FOUND - Please fix before committing")
                
            return issues[:10]  # Limit to 10 issues
        except Exception:
            return []