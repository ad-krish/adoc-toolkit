# Show Command

## Overview

The `show` command displays various ADOC resources and information in a tabular format. It provides a clean, organized view of different data types available in the ADOC platform.

## Usage

```
show [options]
```

## Options

- `--data-sources`: Show all data sources from the catalog
- `--filter <expr>`: Filter results using conditions (col=value,col>value)
- `--sort <cols>`: Sort results by columns (col1,-col2,col3)
- `--stats`: Show column-level statistics
- `--help`: Show detailed help information

## Examples

### Show Data Sources

Display all data sources in a formatted table:

```
ADOC > show --data-sources
```

This will display a table with the following columns:
- **Assembly**: Name of the data source assembly
- **Source Type**: Type of data source (e.g., SNOWFLAKE, ORACLE, AWS_S3)
- **Assembly ID**: Unique identifier for the assembly
- **Schedule**: Cron schedule configuration (if any)
- **Virtual**: Whether this is a virtual data source
- **Protected**: Whether this is a protected resource
- **Integration ID**: Unique integration identifier

### Filtering Data Sources

Filter data sources using various conditions:

```
# Filter by source type
ADOC > show --data-sources --filter source=SNOWFLAKE

# Filter by multiple conditions (AND logic)
ADOC > show --data-sources --filter assembly_id>1000,is_virtual=false

# Filter with different operators
ADOC > show --data-sources --filter source=ORACLE,assembly_id<=5000
```

**Supported Operators:**
- `=` : Equal to
- `!=` : Not equal to
- `>` : Greater than
- `<` : Less than
- `>=` : Greater than or equal to
- `<=` : Less than or equal to

**Supported Fields:**
- `assembly`: Assembly name
- `source`: Source type
- `assembly_id`: Assembly ID (numeric)
- `schedule`: Schedule configuration
- `is_virtual`: Virtual flag (boolean)
- `integration_id`: Integration ID
- `is_protected_resource`: Protected flag (boolean)
- `created_by`: Creator information

### Sorting Data Sources

Sort data sources by one or more columns:

```
# Sort by assembly name (ascending)
ADOC > show --data-sources --sort assembly

# Sort by assembly ID (descending)
ADOC > show --data-sources --sort -assembly_id

# Sort by multiple columns
ADOC > show --data-sources --sort source,assembly_id

# Sort with mixed directions
ADOC > show --data-sources --sort -assembly_id,source
```

**Sort Syntax:**
- `column` : Sort ascending
- `-column` : Sort descending
- Multiple columns separated by commas

### Combining Filter and Sort

You can combine filtering and sorting:

```
# Filter and sort
ADOC > show --data-sources --filter source=ORACLE --sort -assembly_id

# Complex filtering with sorting
ADOC > show --data-sources --filter assembly_id>1000,is_virtual=false --sort source,assembly
```

### Column Statistics

View detailed statistics for all columns:

```
# Show statistics for all data sources
ADOC > show --data-sources --stats

# Show statistics for filtered data
ADOC > show --data-sources --filter source=SNOWFLAKE --stats
```

The statistics include:
- **Column**: Column name
- **Type**: Data type (int64, object, bool, etc.)
- **Count**: Total number of rows
- **Unique**: Number of unique values
- **Null**: Number of null/missing values
- **Min**: Minimum value (for numeric columns)
- **Max**: Maximum value (for numeric columns)

### Show Help

Display detailed help information:

```
ADOC > show --help
```

## Environment Requirements

The `show` command requires an active environment to be set using the `use` command. If no environment is set, the command will display an error message and prompt you to set an environment first.

## Output Format

The command displays data in a rich, formatted table with:
- Color-coded columns for better readability
- Proper alignment for different data types
- Summary count of total items displayed
- Clear English column names
- Filter and sort information in summary
- Efficient pandas-based filtering and sorting algorithms
- Optional column-level statistics with data types and value ranges

## Error Handling

The command handles various error scenarios:
- Missing environment configuration
- API request failures
- Invalid command arguments
- Invalid filter or sort syntax
- Network connectivity issues
- Type conversion errors in filtering

## Related Commands

- [`use`](use.md): Set the active environment
- [`show-env`](show_env.md): Display current environment information
- [`get`](get.md): Make direct API requests

## Future Enhancements

The show command is designed to be extensible. Future versions may include additional options for showing:
- Assets
- Rules
- Policies
- Users
- And other ADOC resources 