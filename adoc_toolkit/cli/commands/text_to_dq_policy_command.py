"""Text to DQ Policy command implementation."""

import json
import re
from functools import reduce
from itertools import product
from operator import methodcaller
from typing import Any

from rich.console import Console

from ...config import get_config_manager
from ...llm.client import get_llm_client
from ...models import CompletionItem
from .base import Command
from .dq_policy_llm_client import DQPolicyLLMClient


def parse_uids(uids_str: str) -> list[str]:
    """Parse comma-separated UIDs string into a list.

    Args:
        uids_str: Comma-separated string of UIDs

    Returns:
        List of stripped UIDs
    """
    return list(filter(None, map(methodcaller("strip"), uids_str.split(","))))


def parse_arguments(args: list[str]) -> tuple[str, list[str]]:
    """Parse command arguments using functional approach.

    Args:
        args: List of command arguments

    Returns:
        Tuple of (text, uids)
    """

    def reducer(
        acc: tuple[str, list[str]], item: tuple[int, str]
    ) -> tuple[str, list[str]]:
        idx, arg = item
        text, uids = acc

        if arg == "--uids":
            if idx + 1 < len(args):
                uids_str = args[idx + 1]
                return text, parse_uids(uids_str)
            else:
                raise ValueError("--uids requires a comma-separated list")
        elif idx > 0 and args[idx - 1] == "--uids":
            # Skip this argument as it was already processed
            return acc
        else:
            return text + " " + arg, uids

    try:
        text, uids = reduce(reducer, enumerate(args), ("", []))
        return text.strip(), uids
    except ValueError as e:
        raise ValueError(str(e)) from e


def validate_llm_config(llm_config) -> str | None:
    """Validate LLM configuration and return error message if invalid.

    Args:
        llm_config: LLM configuration object

    Returns:
        Error message if validation fails, None if valid
    """
    if not llm_config.apikey:
        return (
            "Error: LLM API key not configured. "
            "Use 'set-config llm.apikey <your-api-key>'"
        )

    if not llm_config.vendor:
        return "Error: LLM vendor not configured. Use 'set-config llm.vendor <vendor>'"

    return None


def parse_json_response(response_content: str) -> list[dict[str, Any]]:
    """Parse JSON response from LLM using functional approach.

    Args:
        response_content: Raw response content from LLM

    Returns:
        List of parsed policies
    """
    try:
        parsed_content = json.loads(response_content)
        return parsed_content if isinstance(parsed_content, list) else [parsed_content]
    except json.JSONDecodeError:
        # Try to extract JSON from the response using regex
        json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
        if json_match:
            return [json.loads(json_match.group())]
        else:
            raise ValueError("Could not parse JSON from LLM response") from None


def create_policy_with_uid(policy_template: dict[str, Any], uid: str) -> dict[str, Any]:
    """Create a policy copy with updated UID.

    Args:
        policy_template: Template policy to copy
        uid: UID to set in the policy

    Returns:
        New policy with updated UID
    """
    policy = json.loads(json.dumps(policy_template))

    # Update the tableAssetId with the current UID
    if "rule" in policy and "backingAsset" in policy["rule"]:
        table_asset_id = int(uid) if uid.isdigit() else uid
        policy["rule"]["backingAsset"]["tableAssetId"] = table_asset_id

    return policy


def format_policy_display_text(
    policy_idx: int,
    uid: str,
    policy_count: int,
    total_policies: int,
    multiple_policies: bool,
) -> str:
    """Format the display text for a policy.

    Args:
        policy_idx: Index of the policy
        uid: UID for the policy
        policy_count: Current policy count
        total_policies: Total number of policies
        multiple_policies: Whether there are multiple policies

    Returns:
        Formatted display text
    """
    if multiple_policies:
        return (
            f"\n✅ Generated Data Quality Policy {policy_idx + 1} "
            f"for UID {uid} ({policy_count}/{total_policies}):"
        )
    else:
        return (
            f"\n✅ Generated Data Quality Policy for UID {uid} "
            f"({policy_count}/{total_policies}):"
        )


def process_policies_with_uids(
    policies: list[dict[str, Any]], uids: list[str], console: Console
) -> None:
    """Process policies with UIDs using functional approach.

    Args:
        policies: List of policy templates
        uids: List of UIDs to apply policies to
        console: Console for output
    """
    # Create cross product: policies × UIDs
    total_policies = len(policies) * len(uids)
    console.print(
        f"🔄 Creating cross product: {len(policies)} policies × "
        f"{len(uids)} UIDs = {total_policies} total policies",
        style="blue",
    )

    # Generate all policy-UID combinations
    policy_uid_combinations = list(product(enumerate(policies), enumerate(uids)))

    # Process each combination
    for (policy_idx, policy_template), (uid_idx, uid) in policy_uid_combinations:
        policy_count = policy_idx * len(uids) + uid_idx + 1

        # Create policy with UID
        policy = create_policy_with_uid(policy_template, uid)

        # Display the policy
        display_text = format_policy_display_text(
            policy_idx, uid, policy_count, total_policies, len(policies) > 1
        )
        console.print(display_text, style="green")
        console.print(json.dumps(policy, indent=2), style="white")

        # Add separator between policies (but not after the last one)
        if policy_count < total_policies:
            console.print("\n" + "=" * 50, style="blue")


class TextToDQPolicyCommand(Command):
    """Command to convert text to data quality policy using LLM."""

    def __init__(self) -> None:
        """Initialize text-to-dq-policy command."""
        super().__init__()
        self.console = Console()

    @property
    def name(self) -> str:
        """Get command name."""
        return "text-to-dq-policy"

    @property
    def description(self) -> str:
        """Get command description."""
        return "Convert text to data quality policy using LLM"

    @property
    def aliases(self) -> list[str]:
        """Get command aliases."""
        return ["dq-policy", "text2dq"]

    def get_help(self) -> str:
        """Get detailed help for text-to-dq-policy command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: text-to-dq-policy <text> [--uids <comma-separated-uids>]\n"
        help_text += "       text-to-dq-policy --help\n\n"

        help_text += (
            "This command uses the configured LLM to convert business text into\n"
        )
        help_text += (
            "structured data quality policies. The LLM will analyze the provided\n"
        )
        help_text += "text and generate one or more JSON policy structures.\n\n"

        help_text += "Options:\n"
        help_text += (
            "  --uids <comma-separated-uids>  Comma-separated list of UIDs to "
            "apply the policy to\n"
        )
        help_text += (
            "                                  If provided, creates cross product: "
            "policies × UIDs\n\n"
        )

        help_text += "LLM Configuration:\n"
        help_text += "  The command uses the LLM configured via set-config:\n"
        help_text += "    llm.vendor - LLM vendor (claude, gemini, grok, chatgpt)\n"
        help_text += "    llm.model  - Model name for the selected vendor\n"
        help_text += "    llm.apikey - API key for the selected LLM vendor\n\n"

        help_text += "Examples:\n"
        help_text += (
            '  text-to-dq-policy "Sales data must have valid SALE_ID with '
            'no missing values"\n'
        )
        help_text += (
            '  text-to-dq-policy "Customer data quality rules for validation"\n'
        )
        help_text += (
            '  text-to-dq-policy "Sales data validation" --uids 12345,67890,11111\n'
        )
        help_text += '  text-to-dq-policy "Customer data quality" --uids 9623947\n'

        return help_text

    def execute(self, args: list[str]) -> bool:
        """Execute the text-to-dq-policy command.

        Args:
            args: Command arguments

        Returns:
            True to continue interactive mode
        """
        if not args:
            self.console.print(
                "Usage: text-to-dq-policy <text> [--uids <comma-separated-uids>]",
                style="yellow",
            )
            self.console.print(
                "Use 'text-to-dq-policy --help' for more information.", style="yellow"
            )
            return True

        # Handle help flag
        if args[0] == "--help":
            print(self.get_help())
            return True

        # Parse arguments using functional approach
        try:
            text, uids = parse_arguments(args)
        except ValueError as e:
            self.console.print(str(e), style="red")
            return True

        if not text:
            self.console.print("Error: Text content is required", style="red")
            return True

        return self._generate_dq_policy(text, uids)

    def _generate_dq_policy(self, text: str, uids: list[str] = None) -> bool:
        """Generate data quality policy from text using LLM.

        Args:
            text: Input text to convert to DQ policy
            uids: Optional list of UIDs to apply the policy to

        Returns:
            True to continue interactive mode
        """
        try:
            # Get LLM configuration
            config_manager = get_config_manager()
            llm_config = config_manager._config.llm

            # Validate LLM configuration
            error_message = validate_llm_config(llm_config)
            if error_message:
                self.console.print(error_message, style="red")
                return True

            try:
                # Get the base LLM client
                llm_client = get_llm_client(llm_config.vendor.value, self.console)
                # Create DQ Policy specific client
                dq_client = DQPolicyLLMClient(
                    llm_client, self.console, self._process_response_with_uids
                )
            except ValueError as e:
                self.console.print(str(e), style="red")
                return True

            # Generate policy using the DQ client
            response = dq_client.generate_policy(
                text=text,
                api_key=llm_config.apikey,
                model=llm_config.get_model(),
                uids=uids,
            )
            # If the response is a tuple (result, error_message), handle error
            if isinstance(response, tuple):
                result, error_message = response
                if result is None:
                    self.console.print(
                        f"Error generating response: {error_message}", style="red"
                    )
                    return True
                response = result
            # If the response has content, print it (for debugging or fallback)
            if hasattr(response, "content"):
                self.console.print(response.content, style="white")
            # Otherwise, assume the response is already processed by the callback
            return True

        except Exception as e:
            self.console.print(f"Error generating DQ policy: {e}", style="red")
            return True

    def _process_response_with_uids(
        self, response_content: str, uids: list[str]
    ) -> None:
        """Process LLM response and generate separate JSON for each UID.

        Args:
            response_content: Raw response content from LLM
            uids: List of UIDs to create policies for
        """
        try:
            # Parse policies using functional approach
            policies = parse_json_response(response_content)

            # Display policy count
            policy_count_text = (
                f"\n📋 LLM generated {len(policies)} "
                f"polic{'ies' if len(policies) > 1 else 'y'}"
            )
            self.console.print(policy_count_text, style="blue")

            # Process policies with UIDs using functional approach
            process_policies_with_uids(policies, uids, self.console)

        except Exception as e:
            self.console.print(f"Error processing response with UIDs: {e}", style="red")

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[str | CompletionItem]:
        """Get auto-completion suggestions for text-to-dq-policy command.

        Args:
            current_input: Current input text
            cursor_position: Current cursor position

        Returns:
            List of completion suggestions
        """
        words = current_input.split()

        # If we're typing the first argument (the text)
        if len(words) <= 1:
            return [
                CompletionItem(
                    text='"Sample business text here"',
                    description="Enter business text to convert to DQ policy",
                )
            ]

        # If we're typing after the text, suggest --uids option
        if len(words) >= 2 and not any(word.startswith("--uids") for word in words):
            return [
                CompletionItem(
                    text="--uids",
                    description="Specify comma-separated UIDs for policy generation",
                )
            ]

        # If we're typing after --uids, suggest UID format
        if len(words) >= 2 and words[-2] == "--uids":
            return [
                CompletionItem(
                    text="12345,67890,11111", description="Comma-separated list of UIDs"
                )
            ]

        # If we're typing after --uids (no space), suggest UID format
        if len(words) >= 1 and words[-1] == "--uids":
            return [
                CompletionItem(
                    text="12345,67890,11111", description="Comma-separated list of UIDs"
                )
            ]

        return []
