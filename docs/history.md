# History Command

## Overview
The history command provides comprehensive command history management and recall functionality for the ADOC Toolkit interactive shell. It tracks up to 100 previously executed commands and allows easy recall and reuse.

## Usage
```
history [number]
```

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

### Auto-completion for History Numbers
```
ADOC > history 1<TAB>
# Shows completions: 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
```

## Command Options

### Display History
- `history`: Shows all commands in paginated format
- `hist`: Alias for history command

### Recall Commands
- `history <number>`: Recalls the command at the specified history number
- Numbers are 1-based (1 = most recent command)

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
The history file uses a structured JSON format:
```json
{
  "version": "1.0",
  "history": [
    "most recent command",
    "second most recent command",
    "..."
  ]
}
```

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