# Command Development Guide

## Overview

This guide explains how to add new interactive commands to the ADOC Toolkit. The toolkit uses an object-oriented command system where each command is implemented as a class that inherits from the `Command` base class.

## Command System Architecture

### Core Components

- **[`Command Base Class`](../adoc_toolkit/cli/commands/base.py)**: Abstract base class that all commands must inherit from
- **[`InteractiveProcessor`](../adoc_toolkit/cli/interactive.py)**: Manages command registration, parsing, and execution
- **Command Registry**: Dictionary that maps command names and aliases to command instances
- **Auto-completion System**: Provides intelligent suggestions for commands and parameters

### File Structure

```
adoc_toolkit/
├── cli/
│   ├── commands/
│   │   ├── __init__.py           # Command exports and base class import
│   │   ├── base.py               # Command base class
│   │   ├── help_command.py       # Help system command
│   │   ├── use_command.py        # Environment switching command
│   │   ├── get_command.py        # API request command
│   │   └── your_command.py       # Your new command
│   └── interactive.py            # Interactive processor
└── tests/
    └── test_your_command.py      # Tests for your command
```

## Creating a New Command

### Step 1: Create Command Implementation

Create a new file in `adoc_toolkit/cli/commands/` named `<command_name>_command.py`:

```python
"""<Command description> command implementation."""

from typing import Optional, Union
from .base import Command  # [Command base class](../adoc_toolkit/cli/commands/base.py)
from ...models import CompletionItem  # [CompletionItem model](../adoc_toolkit/models/__init__.py) 


class YourCommandNameCommand(Command):
    """<Command description>."""
    
    def __init__(self, optional_dependencies=None):
        """Initialize the command.
        
        Args:
            optional_dependencies: Any dependencies the command needs
        """
        self.optional_dependencies = optional_dependencies
    
    @property
    def name(self) -> str:
        """Command name used for invocation."""
        return "your-command-name"
    
    @property
    def description(self) -> str:
        """Brief description for help listings."""
        return "Brief description of what the command does"
    
    @property
    def aliases(self) -> list[str]:
        """Command aliases (optional)."""
        return ["alias1", "alias2"]
    
    def get_help(self) -> str:
        """Get detailed help text for the command.
        
        Returns:
            Detailed help text with usage examples
        """
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: your-command-name [options] [arguments]\n\n"
        help_text += "Detailed description of what the command does.\n\n"
        help_text += "Options:\n"
        help_text += "  --help     Show this help message\n"
        help_text += "  --option1  Description of option1\n\n"
        help_text += "Examples:\n"
        help_text += "  your-command-name                    # Basic usage\n"
        help_text += "  your-command-name --option1 value    # With option\n"
        help_text += "  your-command-name arg1 arg2          # With arguments\n"
        return help_text
    
    def execute(self, args: list[str]) -> bool:
        """Execute the command.
        
        Args:
            args: Command arguments
            
        Returns:
            True to continue interactive mode, False to exit
        """
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
            return True
        
        # Parse arguments
        if not args:
            print("Error: Arguments required")
            print("Usage: your-command-name [options] [arguments]")
            print("Type 'your-command-name --help' for more information")
            return True
        
        # Implement command logic here
        try:
            # Your command implementation
            result = self._process_arguments(args)
            print(f"Command executed successfully: {result}")
            return True
        except Exception as e:
            print(f"Error executing command: {e}")
            return True
    
    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions.
        
        Args:
            current_input: The current input text
            cursor_position: Current cursor position
            
        Returns:
            List of completion suggestions
        """
        # Parse current input to determine context
        words = current_input[:cursor_position].split()
        
        if len(words) == 1 and words[0] == self.name:
            # Suggest options and arguments
            return [
                "--help",
                "--option1",
                "argument1",
                "argument2"
            ]
        elif len(words) > 1 and words[1] == "--option1":
            # Suggest values for option1
            return [
                "value1",
                "value2",
                "value3"
            ]
        
        return []
    
    def _process_arguments(self, args: list[str]) -> str:
        """Process command arguments.
        
        Args:
            args: Command arguments
            
        Returns:
            Processing result
        """
        # Implement argument processing logic
        return f"Processed {len(args)} arguments: {', '.join(args)}"
```

### Step 2: Add Command to Exports

Update [`adoc_toolkit/cli/commands/__init__.py`](../adoc_toolkit/cli/commands/__init__.py) to include your new command:

```python
"""Command system for ADOC toolkit interactive shell."""

# Import base Command class
from .base import Command

# Import all commands to make them available
from .exit_command import ExitCommand
from .export_execution_metrics_command import ExportExecutionMetricsCommand
from .export_metrics_command import ExportMetricsCommand
from .get_command import GetCommand
from .help_command import HelpCommand
from .history_command import HistoryCommand
from .set_config_command import SetConfigCommand
from .show_env_command import ShowEnvCommand
from .text_to_dq_policy_command import TextToDQPolicyCommand
from .use_command import UseCommand
from .your_command import YourCommandNameCommand  # Add this line

__all__ = [
    "Command",
    "ExitCommand",
    "ExportExecutionMetricsCommand",
    "ExportMetricsCommand",
    "GetCommand",
    "HelpCommand",
    "HistoryCommand",
    "SetConfigCommand",
    "ShowEnvCommand",
    "TextToDQPolicyCommand",
    "UseCommand",
    "YourCommandNameCommand",  # Add this line
]
```

### Step 3: Register Command

Update [`adoc_toolkit/cli/interactive.py`](../adoc_toolkit/cli/interactive.py) in the `_setup_default_commands()` method:

```python
def _setup_default_commands(self) -> None:
    """Set up default commands."""
    # ... existing commands ...
    
    # Add your new command
    your_command = YourCommandNameCommand(optional_dependencies=self.some_dependency)
    
    # Register commands
    self.register_command(help_cmd)
    self.register_command(exit_cmd)
    # ... other commands ...
    self.register_command(your_command)  # Add this line
```

## Command Requirements

### Required Methods

Every command must implement these abstract methods from the [`Command` base class](../adoc_toolkit/cli/commands/base.py):

#### `name` Property
```python
@property
def name(self) -> str:
    """Command name used for invocation."""
    return "command-name"
```

#### `description` Property
```python
@property
def description(self) -> str:
    """Brief description for help listings."""
    return "Brief description of what the command does"
```

#### `execute()` Method
```python
def execute(self, args: list[str]) -> bool:
    """Execute the command.
    
    Args:
        args: Command arguments
        
    Returns:
        True to continue interactive mode, False to exit
    """
    # Command implementation
    return True
```

### Optional Methods

These methods can be overridden to provide additional functionality:

#### `aliases` Property
```python
@property
def aliases(self) -> list[str]:
    """Command aliases."""
    return ["alias1", "alias2"]
```

#### `get_help()` Method
```python
def get_help(self) -> str:
    """Get detailed help text for the command."""
    help_text = f"{self.name}: {self.description}\n"
    help_text += "Usage: command-name [options]\n\n"
    help_text += "Detailed description and examples..."
    return help_text
```

#### `get_completions()` Method
```python
def get_completions(
    self, current_input: str, cursor_position: int
) -> list[Union[str, CompletionItem]]:
    """Get auto-completion suggestions."""
    return ["suggestion1", "suggestion2"]
```

## Help System Integration

### Required Help Support

All commands must support both help patterns:

1. **`help <command>`** - Shows detailed help via HelpCommand
2. **`<command> --help`** - Shows detailed help via command's `get_help()` method

### Help Implementation

```python
def execute(self, args: list[str]) -> bool:
    """Execute the command."""
    # Handle --help flag
    if args and args[0] == "--help":
        print(self.get_help())
        return True
    
    # Rest of command implementation...
```

## Auto-completion System

### Basic Completions

Return simple string suggestions:

```python
def get_completions(
    self, current_input: str, cursor_position: int
) -> list[Union[str, CompletionItem]]:
    """Get auto-completion suggestions."""
    return ["option1", "option2", "argument1", "argument2"]
```

### Structured Completions

Return [`CompletionItem`](../adoc_toolkit/models/__init__.py) objects with descriptions:

```python
from ...models import CompletionItem  # [CompletionItem model](../adoc_toolkit/models/__init__.py)

def get_completions(
    self, current_input: str, cursor_position: int
) -> list[Union[str, CompletionItem]]:
    """Get auto-completion suggestions."""
    return [
        CompletionItem(text="--help", description="Show help message"),
        CompletionItem(text="--verbose", description="Enable verbose output"),
        CompletionItem(text="argument1", description="First argument description")
    ]
```

### Context-Aware Completions

Parse current input to provide context-specific suggestions:

```python
def get_completions(
    self, current_input: str, cursor_position: int
) -> list[Union[str, CompletionItem]]:
    """Get context-aware completion suggestions."""
    words = current_input[:cursor_position].split()
    
    if len(words) == 1 and words[0] == self.name:
        # Suggest options when command is first word
        return ["--help", "--option1", "--option2"]
    elif len(words) > 1 and words[1] == "--option1":
        # Suggest values for specific option
        return ["value1", "value2", "value3"]
    elif len(words) > 1 and words[1] == "--file":
        # Suggest file completions
        return self._get_file_completions()
    
    return []
```

## Testing Your Command

### Step 1: Create Test File

Create [`tests/test_your_command.py`](../tests/) (follow the pattern of existing test files):

```python
"""Tests for your-command-name command."""

import pytest
from unittest.mock import Mock, patch
from adoc_toolkit.cli.commands.your_command import YourCommandNameCommand  # [Your command implementation](../adoc_toolkit/cli/commands/your_command.py)


class TestYourCommandNameCommand:
    """Test cases for YourCommandNameCommand."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.command = YourCommandNameCommand()
    
    def test_command_name(self):
        """Test command name property."""
        assert self.command.name == "your-command-name"
    
    def test_command_description(self):
        """Test command description."""
        assert self.command.description == "Brief description of what the command does"
    
    def test_command_aliases(self):
        """Test command aliases."""
        assert self.command.aliases == ["alias1", "alias2"]
    
    def test_help_flag(self):
        """Test --help flag handling."""
        result = self.command.execute(["--help"])
        assert result is True
    
    def test_no_arguments(self):
        """Test command with no arguments."""
        result = self.command.execute([])
        assert result is True
    
    def test_with_arguments(self):
        """Test command with arguments."""
        result = self.command.execute(["arg1", "arg2"])
        assert result is True
    
    def test_get_help(self):
        """Test help text generation."""
        help_text = self.command.get_help()
        assert "your-command-name" in help_text
        assert "Brief description" in help_text
        assert "Usage:" in help_text
    
    def test_get_completions(self):
        """Test auto-completion suggestions."""
        completions = self.command.get_completions("your-command-name ", 18)
        assert "--help" in completions
        assert "--option1" in completions
    
    def test_error_handling(self):
        """Test error handling."""
        with patch.object(self.command, '_process_arguments', side_effect=Exception("Test error")):
            result = self.command.execute(["arg1"])
            assert result is True
```

### Step 2: Run Tests

```bash
# Run your command tests
make test-your-command

# Run all tests
make test

# Run with coverage
make test-coverage
```

## Documentation Requirements

### Step 1: Create Command Documentation

Create [`docs/your_command.md`](./) (follow the pattern of existing documentation):

```markdown
# Your Command Name

## Overview

Brief description of what the command does and its purpose.

## Usage

```bash
your-command-name [options] [arguments]
```

## Arguments

- **argument1**: Description of first argument
- **argument2**: Description of second argument

## Options

- **--help**: Show help message
- **--option1 value**: Description of option1
- **--option2**: Description of option2

## Examples

### Basic Usage

```bash
ADOC > your-command-name
# Example output
```

### With Options

```bash
ADOC > your-command-name --option1 value
# Example with option
```

### With Arguments

```bash
ADOC > your-command-name arg1 arg2
# Example with arguments
```

## Features

- **Feature 1**: Description of feature 1
- **Feature 2**: Description of feature 2
- **Auto-completion**: Provides suggestions for options and arguments

## Error Handling

The command handles various error conditions:

- **Missing Arguments**: Shows usage information
- **Invalid Options**: Displays error messages
- **Processing Errors**: Graceful error handling with user-friendly messages

## Related Commands

- [`other-command`](other_command.md): Related functionality
- [`help`](help.md): Get help for commands


### Step 2: Update Main Documentation

Add your command to the main README.md in the appropriate section.

## Best Practices

### Command Design

1. **Single Responsibility**: Each command should have one clear purpose
2. **Consistent Interface**: Follow the same patterns as existing commands
3. **Error Handling**: Provide clear, helpful error messages
4. **Help Integration**: Always support both help patterns
5. **Auto-completion**: Provide intelligent suggestions

### Code Quality

1. **Type Hints**: Use proper type annotations
2. **Documentation**: Include docstrings for all methods
3. **Testing**: Write comprehensive tests
4. **Error Handling**: Handle exceptions gracefully
5. **Validation**: Validate inputs and provide helpful feedback

### Security

1. **Input Validation**: Validate all user inputs
2. **Error Messages**: Don't expose sensitive information in error messages
3. **File Operations**: Use safe file handling practices
4. **Network Operations**: Handle network errors gracefully

## Example: Complete Command Implementation

Here's a complete example of a simple command:

```python
"""Example command implementation."""

from typing import Union
from .base import Command  # [Command base class](adoc_toolkit/cli/commands/base.py)
from ...models import CompletionItem  # [CompletionItem model](adoc_toolkit/models/__init__.py)


class ExampleCommand(Command):
    """Example command that demonstrates command development."""
    
    @property
    def name(self) -> str:
        return "example"
    
    @property
    def description(self) -> str:
        return "Example command for demonstration"
    
    @property
    def aliases(self) -> list[str]:
        return ["ex", "demo"]
    
    def get_help(self) -> str:
        """Get detailed help for example command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: example [message]\n\n"
        help_text += "Displays a message or default greeting.\n\n"
        help_text += "Arguments:\n"
        help_text += "  message    Custom message to display (optional)\n\n"
        help_text += "Examples:\n"
        help_text += "  example                    # Show default greeting\n"
        help_text += "  example 'Hello, World!'    # Show custom message\n"
        return help_text
    
    def execute(self, args: list[str]) -> bool:
        """Execute the example command."""
        if args and args[0] == "--help":
            print(self.get_help())
            return True
        
        if args:
            message = " ".join(args)
            print(f"Message: {message}")
        else:
            print("Hello from the example command!")
        
        return True
    
    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions."""
        return [
            CompletionItem(text="--help", description="Show help message"),
            CompletionItem(text="Hello", description="Greeting message"),
            CompletionItem(text="World", description="World message")
        ]
```

## Troubleshooting

### Common Issues

1. **Command Not Found**: Ensure command is properly registered in [`_setup_default_commands()`](../adoc_toolkit/cli/interactive.py)
2. **Import Errors**: Check that command is exported in [`__init__.py`](../adoc_toolkit/cli/commands/__init__.py)
3. **Help Not Working**: Verify both help patterns are implemented
4. **Auto-completion Issues**: Check [`get_completions()`](../adoc_toolkit/cli/commands/base.py) method implementation
5. **Test Failures**: Ensure tests match the actual command implementation

### Debugging Tips

1. **Add Logging**: Use print statements or logging for debugging
2. **Test Incrementally**: Test each method individually
3. **Check Existing Commands**: Use existing commands as reference (see [`adoc_toolkit/cli/commands/`](../adoc_toolkit/cli/commands/) directory)
4. **Validate Input**: Test with various input combinations

## Next Steps

After implementing your command:

1. **Test thoroughly** with various inputs and edge cases
2. **Document completely** with examples and error handling
3. **Review code quality** using `make all-checks`
4. **Get feedback** from other developers
5. **Update related documentation** as needed

For more information about specific aspects of command development, see the individual command documentation in the `docs/` directory. 
