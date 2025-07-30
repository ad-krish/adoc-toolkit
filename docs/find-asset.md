# Find Asset Command

## Overview
The `find-asset` command allows you to find assets in the ADOC catalog by name. It performs a case-insensitive search that supports partial matches and displays results in a formatted table matching the data-sources command format.

## Usage
```
find-asset <asset-name>
```

## Options
- `<asset-name>`: The name of the asset to search for (required)

## Examples

### Basic Search
```bash
ADOC > find-asset database
```

### Search with Spaces
```bash
ADOC > find-asset "my table"
```

### Get Help
```bash
ADOC > find-asset --help
```

## Output Format

The command displays results in a Rich table format with the following columns:

| Column | Description |
|--------|-------------|
| Assembly | Assembly name (derived from asset name) |
| Source Type | Source type (derived from asset type) |
| Assembly ID | Asset identifier |
| Schedule | Schedule configuration (None for assets) |
| Virtual | Whether virtual (No for assets) |
| Protected | Whether protected (No for assets) |
| Integration ID | Asset UID |

### No Results
When no assets are found matching the search term:
```
No assets found matching 'nonexistent'
Try using a different search term or check the spelling.
```

## API Details

The command makes a GET request to:
- **Endpoint**: `/catalog-server/api/assets/search`
- **Query Parameter**: `name` (the search term)
- **Response**: JSON object containing an `assets` array

### Response Structure
```json
{
  "assets": [
    {
      "id": "123",
      "name": "asset_name",
      "assetType": {
        "name": "Database"
      },
      "uid": "asset_uid"
    }
  ]
}
```

## Aliases
- `search`
- `search-asset`
- `asset-search`

## Error Handling

The command handles various error scenarios:

- **Missing asset name**: Displays usage instructions
- **API errors**: Shows error message from the server
- **Network issues**: Displays connection error details
- **No results**: Shows user-friendly message with suggestions

## Related Commands
- [`get`](get.md): Execute general API calls
- [`use`](use.md): Switch between environments
- [`show-env`](show_env.md): Display current environment
- [`show data-sources`](show.md): Display data sources in similar format

## Debugging and Tracing

The `find-asset` command supports detailed tracing for debugging purposes. When TRACE level logging is enabled, the command will emit detailed trace information including:

- Command execution start/completion
- Asset search parameters and results
- API request/response details
- Response parsing and validation
- Individual asset display operations

To enable tracing:
```bash
ADOC > set-config log.level TRACE
ADOC > find-asset Snowflake
```

See [Tracing Guide](../tracing-guide.md) for more information about the tracing system.

## Next Steps
- Use `search-asset` to find assets you want to work with
- Use the asset ID or UID in other commands that require asset references
- Combine with other commands to perform asset-specific operations 