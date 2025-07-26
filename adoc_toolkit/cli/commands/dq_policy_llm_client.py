"""DQ Policy LLM Client for text-to-dq-policy command."""

import os
from typing import Optional, List, Callable, Dict, Any

from ...models import LLMRequest, LLMResponse, DQPolicyPromptConfig
from ...llm.client import BaseLLMClient


class DQPolicyLLMClient:
    """DQ Policy specific LLM client that handles prompt management and response processing."""
    
    def __init__(self, llm_client: BaseLLMClient, console, process_response_with_uids: Callable[[str, List[str]], None]):
        self.llm_client = llm_client
        self.console = console
        self.process_response_with_uids = process_response_with_uids
        self.prompt_config = DQPolicyPromptConfig()

    def get_system_prompt(self) -> str:
        """Get system prompt for DQ policy generation."""
        if self.prompt_config.system_prompt_text:
            return self.prompt_config.system_prompt_text
            
        prompt_path = os.path.join(os.path.dirname(__file__), '../../../config/prompts/text_to_dq_policy_system.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ("[ERROR: System prompt file not found at 'config/prompts/text_to_dq_policy_system.txt'. "
                    "Please ensure the prompt file exists.]")
        except Exception as e:
            return f"[ERROR: Could not read system prompt file: {e}]"

    def get_user_prompt(self, text: str) -> str:
        """Get user prompt for DQ policy generation."""
        return self.prompt_config.user_prompt_template.format(text=text)

    def _create_response_processor(self, uids: Optional[List[str]] = None):
        """Create response processor for DQ policy with UIDs."""
        def processor(response: LLMResponse, kwargs: Dict[str, Any]):
            if uids:
                self.process_response_with_uids(response.content, uids)
            else:
                self.console.print("\n✅ Generated Data Quality Policy:", style="green")
                self.console.print(response.content, style="white")
        return processor

    def generate_policy(self, text: str, api_key: str, model: str, uids: Optional[List[str]] = None) -> bool:
        """Generate DQ policy using the configured LLM client."""
        try:
            # Create response processor
            response_processor = self._create_response_processor(uids)
            
            # Create LLM request
            request = LLMRequest(
                system_prompt=self.get_system_prompt(),
                user_prompt=self.get_user_prompt(text),
                api_key=api_key,
                model=model
            )
            
            # Generate response using the LLM client
            return self.llm_client.generate_with_processing(request)
            
        except Exception as e:
            self.console.print(f"Error generating DQ policy: {e}", style="red")
            return True

    def set_prompt_config(self, prompt_config: DQPolicyPromptConfig):
        """Update prompt configuration."""
        self.prompt_config = prompt_config 