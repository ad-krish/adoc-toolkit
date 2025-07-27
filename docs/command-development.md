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

## Enabling Tracing with Commands

The ADOC Toolkit provides a powerful tracing system that allows commands to emit detailed nested trace information when the log level is set to TRACE. This is extremely valuable for debugging complex operations and understanding execution flow.

### Quick Start: Adding Tracing to Your Command

#### Step 1: Import Tracing Components

```python
"""Your command implementation with tracing."""

from typing import Optional, Union
from .base import Command
from ...models import CompletionItem
from ...tracing import TraceableMixin, trace_method  # [TraceableMixin](../adoc_toolkit/tracing/mixins.py), [trace_method decorator](../adoc_toolkit/tracing/decorators.py)
```

#### Step 2: Inherit from TraceableMixin

```python
class YourCommandNameCommand(Command, TraceableMixin):  # Add TraceableMixin
    """Your command with tracing capabilities."""
    
    @property
    def trace_prefix(self) -> Optional[str]:
        """Get the trace prefix for this command."""
        return "your_command"  # This will prefix all trace messages
    
    # ... rest of your command implementation
```

#### Step 3: Add Tracing to Methods

```python
@trace_method("execute_command", "your_command")  # Add decorator
def execute(self, args: list[str]) -> bool:
    """Execute the command with tracing."""
    # Trace the start of execution
    self.trace("execution_started", args_count=len(args))
    
    try:
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
            self.trace("help_displayed")
            return True
        
        # Your command logic here
        result = self._process_arguments(args)
        
        # Trace successful completion
        self.trace("execution_completed", success=True, result=result)
        return True
        
    except Exception as e:
        # Trace errors
        self.trace_error("execution", e, args_count=len(args))
        print(f"Error executing command: {e}")
        return True

@trace_method("process_arguments", "your_command")  # Add decorator
def _process_arguments(self, args: list[str]) -> str:
    """Process command arguments with tracing."""
    self.trace("argument_processing_started", args=args)
    
    # Your argument processing logic
    result = f"Processed {len(args)} arguments: {', '.join(args)}"
    
    self.trace("argument_processing_completed", result=result)
    return result
```

### Enabling Tracing

#### Method 1: Set Log Level to TRACE

```bash
# In the ADOC toolkit interactive shell
ADOC > set-config log.level TRACE
ADOC > your-command-name arg1 arg2
```

#### Method 2: Environment Variable

```bash
# Set environment variable before running
export ADOC_LOG_LEVEL=TRACE
uv run adoc-toolkit
```

### Example Tracing Output

When tracing is enabled, you'll see detailed nested output:

```
→ your_command.execute_command
  → your_command.execution_started
    → your_command.process_arguments
      → your_command.argument_processing_started
      → your_command.argument_processing_completed
    → your_command.process_arguments_completed
  → your_command.execution_completed
→ your_command.execute_command_completed
```

### Tracing Methods Available

The [`TraceableMixin`](../adoc_toolkit/tracing/mixins.py) provides several convenient methods:

#### Basic Tracing

```python
# Simple operation tracing
self.trace("operation_name", detail1="value1", detail2="value2")

# Example usage
self.trace("data_loaded", records_count=100, file_size="1.2MB")
self.trace("validation_completed", errors_found=0, warnings=2)
```

#### Convenience Methods

```python
# Start tracing (adds "_started" suffix)
self.trace_start("processing", records_count=100)

# Complete tracing (adds "_completed" suffix)
self.trace_complete("processing", success=True, records_processed=100)

# Error tracing (adds "_failed" suffix with error details)
try:
    result = self._risky_operation()
except Exception as e:
    self.trace_error("risky_operation", e, context="data_processing")
```

#### Reset Trace Depth (Rarely Needed)

```python
# Reset trace depth if needed
self.reset_trace()
```

### [`@trace_method`](../adoc_toolkit/tracing/decorators.py) Decorator

The decorator automatically traces method entry, success, and failure:

#### Basic Usage

```python
@trace_method()  # Uses method name as operation name
def simple_method(self):
    pass

@trace_method("custom_operation")  # Custom operation name
def another_method(self):
    pass

@trace_method("fetch_data", "your_command")  # Custom operation and prefix
def fetch_data(self):
    pass
```

#### Decorator with Error Handling

```python
@trace_method("process_file", "your_command")
def process_file(self, filename: str) -> bool:
    """Process a file with automatic tracing."""
    # The decorator automatically traces:
    # - Method entry with arguments
    # - Successful completion
    # - Any exceptions that occur
    
    with open(filename, 'r') as f:
        data = f.read()
    
    # Process the data...
    return True
```

### Advanced Tracing Patterns

#### Conditional Tracing

```python
def execute(self, args: list[str]) -> bool:
    """Execute with conditional tracing."""
    self.trace("execution_started", args_count=len(args))
    
    # Only trace if verbose mode is enabled
    if self.verbose_mode:
        self.trace("verbose_mode_enabled")
    
    # Trace different paths
    if args:
        self.trace("processing_with_arguments", args=args)
        result = self._process_with_args(args)
    else:
        self.trace("processing_without_arguments")
        result = self._process_default()
    
    self.trace("execution_completed", result=result)
    return result
```

#### Performance Tracing

```python
import time

@trace_method("performance_test", "your_command")
def performance_test(self) -> None:
    """Test with performance tracing."""
    start_time = time.time()
    
    # Your operation here
    time.sleep(1)  # Simulate work
    
    duration = time.time() - start_time
    self.trace("performance_completed", duration_seconds=duration)
```

#### Batch Processing Tracing

```python
def process_batch(self, items: list[str]) -> None:
    """Process items with batch tracing."""
    self.trace("batch_processing_started", total_items=len(items))
    
    for i, item in enumerate(items):
        self.trace("processing_item", item_index=i, item=item)
        
        try:
            result = self._process_single_item(item)
            self.trace("item_processed", item_index=i, success=True)
        except Exception as e:
            self.trace_error("item_processing", e, item_index=i, item=item)
    
    self.trace("batch_processing_completed", items_processed=len(items))
```

### Testing with Tracing

Tracing is automatically disabled in test environments to avoid interfering with tests:

```python
def test_command_with_tracing(self):
    """Test that command works with tracing disabled."""
    command = YourCommandNameCommand()
    
    # Tracing is automatically disabled in tests
    result = command.execute(["arg1", "arg2"])
    
    # Command works normally, but no trace output
    assert result is True
```

### Best Practices for Tracing

1. **Use Descriptive Operation Names**: Choose clear, descriptive names for trace operations
2. **Include Relevant Context**: Add useful details like counts, sizes, or status information
3. **Trace at Logical Boundaries**: Trace at the start and end of major operations
4. **Handle Errors Gracefully**: Use `trace_error()` for exception handling
5. **Keep Performance in Mind**: Tracing has minimal overhead but should be used judiciously
6. **Use Consistent Prefixes**: Use the same prefix pattern across related commands

### Troubleshooting Tracing

#### Tracing Not Appearing

1. **Check Log Level**: Ensure log level is set to TRACE
2. **Verify Mixin**: Make sure your command inherits from [`TraceableMixin`](../adoc_toolkit/tracing/mixins.py)
3. **Check Prefix**: Ensure `trace_prefix` property returns a string
4. **Test Environment**: Tracing is disabled in pytest environments

#### Performance Issues

1. **Reduce Trace Frequency**: Don't trace in tight loops
2. **Limit Trace Details**: Avoid tracing large objects or data structures
3. **Use Conditional Tracing**: Only trace when needed

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
