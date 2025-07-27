# History Command

## Overview
The history command provides comprehensive command and execution tracking for the ADOC Toolkit interactive shell. It displays previously executed commands and detailed execution information including performance metrics, status, and timing data.

## Usage
```
history [number] | history --executions [count]
```

## Options

- `number`: Recall a specific command by its history number
- `--executions [count]`: Display execution history with detailed metrics (count: 10,25,50,100)
- `--help`: Show help message

## Features

### Command History Tracking
- **Automatic Tracking**: Automatically tracks all executed commands
- **Capacity**: Maintains up to 100 commands in history
- **Duplicate Handling**: Duplicate commands are moved to the top of the history instead of creating new entries
- **Smart Filtering**: Excludes history, help, and exit commands from being tracked
- **Number Exclusion**: History recall numbers are not added to history

### History Display
- **Paginated View**: Shows 25 commands at a time
- **Latest First**: Most recent commands appear first
- **Numbered List**: Each command has a number for easy reference
- **Interactive Browsing**: Press any key to show the next 25 commands
- **Progress Indicator**: Shows current page position (e.g., "showing 1-25 of 67")

### Command Recall
- **Easy Recall**: Use `history <number>` to recall a specific command
- **Pre-populated**: Recalled commands appear in the command line but don't execute automatically
- **Safe Operation**: Recalled commands must be manually executed with Enter

### Execution History (New)

The `--executions` option provides detailed execution tracking for all commands with comprehensive performance and status information.

#### Execution Tracking Features
- **Status Tracking**: Success/failure status for each command execution
- **Performance Metrics**: Precise timing data with start time, end time, and duration
- **Error Information**: Detailed error messages for failed commands
- **Persistent Storage**: Execution data is saved and persists across sessions (up to 500 executions)
- **Pagination Support**: Navigate through large execution histories efficiently

#### Display Information
Each execution entry shows:
- **Command**: The full command that was executed (truncated if too long)
- **Status**: "success" or "failure"
- **Duration**: Execution time in human-readable format (seconds, minutes)
- **Start Time**: When the command started executing
- **End Time**: When the command finished executing

#### Page Size Options
The `--executions` option supports different page sizes:
- `10`: Show 10 executions per page
- `25`: Show 25 executions per page (default)
- `50`: Show 50 executions per page  
- `100`: Show 100 executions per page

#### Navigation Controls
- **Next Page**: Press any key to show the next set of executions
- **Exit**: Press `<escape>` key to stop pagination and return to prompt
- **Automatic Exit**: Automatically returns to prompt when all executions are shown

## Examples

### Basic History Display
```
ADOC > history
History (showing 1-25 of 45):
--------------------------------------------------
  1: use staging
  2: show-env
  3: use dev
  4: show-env
  5: use cs-india
  ...
  25: some-other-command

Press any key to show next 20 commands...
```

### Command Recall
```
ADOC > history 3
Command recalled: use dev
ADOC > use dev
Environment set to dev
```

### Execution History Display

Display recent execution history with default page size (25):
```
ADOC > history --executions

Execution History (showing 1-3 of 3):
------------------------------------------------------------------------------------------------------------------------
#   Command                                  Status   Duration     Start Time          End Time           
------------------------------------------------------------------------------------------------------------------------
1   export-execution-metrics --output-ty... success  1m 5.0s      2024-01-15 10:30:00 2024-01-15 10:31:05
2   use prod                                 success  1.20s        2024-01-15 10:29:00 2024-01-15 10:29:01
3   invalid-command                          failure  0.100s       2024-01-15 10:28:00 2024-01-15 10:28:00
```

### Different Page Sizes for Executions

Show 10 executions per page:
```
ADOC > history --executions 10
```

Show 50 executions per page:
```
ADOC > history --executions 50
```

### Execution Pagination Example

When there are more executions than the page size:
```
ADOC > history --executions 10

Execution History (showing 1-10 of 25):
------------------------------------------------------------------------------------------------------------------------
#   Command                                  Status   Duration     Start Time          End Time           
------------------------------------------------------------------------------------------------------------------------
1   export-execution-metrics                success  45.30s       2024-01-15 10:30:00 2024-01-15 10:30:45
2   use prod                                 success  1.20s        2024-01-15 10:29:00 2024-01-15 10:29:01
...
10  show-env                                 success  0.50s        2024-01-15 10:20:00 2024-01-15 10:20:01

Press any key to show next 10 executions, <escape> to exit...
```

### Auto-completion for History Numbers
```
ADOC > history 1<TAB>
# Shows completions: 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
```

### Auto-completion for Execution Options
```
ADOC > history --<TAB>
# Shows: --executions

ADOC > history --executions <TAB>
# Shows: 10, 25, 50, 100
```

## Command Options

### Display History
- `history`: Shows all commands in paginated format
- `hist`: Alias for history command

### Display Execution History
- `history --executions`: Shows execution history with default page size (25)
- `history --executions <count>`: Shows execution history with specified page size (10, 25, 50, 100)

### Recall Commands
- `history <number>`: Recalls the command at the specified history number
- Numbers are 1-based (1 = most recent command)

## Duration Formatting

The execution history displays durations in human-readable formats:
- **Sub-second**: `0.500s` (3 decimal places for precision)
- **Seconds**: `30.00s` (2 decimal places)
- **Minutes**: `2m 45.0s` (minutes and seconds with 1 decimal place)

## History Rules

### Commands Excluded from History
- `history`, `hist` - History commands themselves
- `help`, `h`, `?` - Help commands  
- `exit`, `quit`, `q` - Exit commands
- Pure numbers (history recall numbers)

### Duplicate Handling
- If you execute a command that's already in history, it's moved to position 1 (most recent)
- No duplicate entries are created
- History maintains chronological accuracy

### Capacity Management  
- Maximum 100 commands stored
- When limit is reached, oldest commands are automatically removed
- Most recent 100 commands are always preserved

## Interactive Features

### Pagination Controls
- **First Page**: Automatically displayed when running `history`
- **Next Pages**: Press any key to continue to next set of 25 commands  
- **Navigation**: Continue pressing keys until all commands are shown
- **Exit Early**: Use Ctrl+C to stop browsing history

### Auto-completion
- History numbers support tab completion
- Type partial number and press Tab for suggestions
- Limits to first 10 suggestions for performance

## Use Cases

### Command Repetition
```
ADOC > use production
ADOC > show-env
ADOC > history
# Find the command number for "use production"
ADOC > history 5
# Command is recalled and ready to edit/execute
```

### Command Discovery
```
ADOC > history
# Browse through recent commands to remember what you did
# Useful for finding complex commands you used before
```

### Workflow Recreation
```
ADOC > history 10
ADOC > history 8  
ADOC > history 3
# Quickly replay a sequence of commands
```

## Aliases
- `hist`: Short alias for history command

## Related Commands
- [`help`](help.md): Get help on commands
- [`use`](use.md): Switch environments (commonly recalled command)
- [`show-env`](show_env.md): Display environment info (commonly recalled command)

## Technical Notes

### Storage
- History is stored persistently in `~/.adoc-toolkit-history` file
- History persists between sessions and is automatically loaded on startup
- History is independent of the shell's command history
- Uses JSON format with version information for future compatibility
- File is created automatically in the user's home directory
- Supports atomic writes to prevent data corruption

### History File Format
The history file uses a structured JSON format that includes both command history and execution tracking:
```json
{
  "version": "2.0",
  "history": [
    "most recent command",
    "second most recent command",
    "..."
  ],
  "execution_history": {
    "version": "1.0",
    "command_history": [...],
    "execution_history": [
      {
        "command": "export-execution-metrics --output-type csv",
        "status": "success",
        "start_time": "2024-01-15T10:30:00",
        "end_time": "2024-01-15T10:31:05", 
        "duration_seconds": 65.0,
        "error_message": null
      }
    ]
  }
}
```

### Storage Limits
- **Command History**: Up to 100 commands
- **Execution History**: Up to 500 executions
- **File Management**: Automatic rotation and cleanup when limits are exceeded

### File Location
- **Linux/macOS**: `~/.adoc-toolkit-history`
- **Windows**: `%USERPROFILE%\.adoc-toolkit-history`

### Performance
- History operations are optimized for real-time use
- Auto-completion is limited to first 10 matches for responsiveness
- Pagination prevents overwhelming display of large histories

### Compatibility
- Cross-platform keypress detection for pagination
- Graceful fallback to Enter key on systems without advanced terminal support
- Works in both interactive TTY and non-TTY environments

## Error Handling

### Missing History
When no history is available:
```
ADOC > history
No command history available

ADOC > history --executions
No execution history available
```

### Invalid Command Recall
When trying to recall a non-existent command:
```
ADOC > history 999
Error: History number 999 is out of range
Valid range: 1-10
```

### Invalid Page Sizes
When using invalid page sizes for executions:
```
ADOC > history --executions 15
Warning: Invalid page size 15. Valid sizes: 10, 25, 50, 100. Using default: 25
```

### Execution History Not Available
When execution tracking is not available:
```
ADOC > history --executions
Error: Execution history functionality not available
```

### File Corruption
If the history file becomes corrupted, the command gracefully handles the error and starts with empty history.