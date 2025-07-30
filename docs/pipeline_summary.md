# Pipeline Summary Command

## Overview
The `pipeline-summary` resource type allows you to display pipeline summaries from the ADOC orchestration API. This command fetches pipeline information including IDs, names, owners, source types, run counts, and latest run status.

## Usage
```
show pipeline-summary [options]
```

## Options
- `--filter <expr>`   Filter results (col=value,col>value,col~partial)
- `--sort <cols>`     Sort results (col1,-col2,col3)
- `--stats`          Show column statistics
- `--help`           Show this help message

## Available Columns

| Column | Display Name | Description | Filterable | Sortable |
|--------|--------------|-------------|------------|----------|
| `id` | Id | Pipeline ID | ✓ | ✓ |
| `name` | Name | Pipeline name | ✓ | ✓ |
| `owner` | Owner | Pipeline owner | ✓ | ✓ |
| `source_type` | Source | Pipeline source type | ✓ | ✓ |
| `total_runs_count` | # Runs | Total number of runs | ✓ | ✓ |
| `latest_run_result` | Last Run Status | Latest run result | ✓ | ✓ |
| `latest_run_finished_at` | Finished Time in UTC | Latest run finished time | ✓ | ✓ |

## Filter Examples
```
show pipeline-summary --filter source_type=SNOWFLAKE
show pipeline-summary --filter owner=testuser,total_runs_count>10
show pipeline-summary --filter source_type=ORACLE,latest_run_result=SUCCESS
show pipeline-summary --filter name~test
```

## Sort Examples
```
show pipeline-summary --sort name
show pipeline-summary --sort -latest_run_finished_at,owner
show pipeline-summary --sort total_runs_count,name
```

## Examples
```
# Show all pipeline summaries
show pipeline-summary

# Show only Snowflake pipelines
show pipeline-summary --filter source_type=SNOWFLAKE

# Show pipelines sorted by name
show pipeline-summary --sort name

# Show failed pipelines sorted by finish time (newest first)
show pipeline-summary --filter latest_run_result=FAILED --sort -latest_run_finished_at

# Show pipelines with statistics
show pipeline-summary --stats

# Show help
show pipeline-summary --help
```

## API Endpoint
The command makes a GET request to:
```
/torch-pipeline/api/pipelines/summary?page=0&size=20
```

## Response Format
The API returns a JSON response with:
- `meta`: Object containing `count` and `size`
- `pipelines`: Array of pipeline objects

Each pipeline object contains a nested `pipelineSummary` structure:
```json
{
  "pipelineSummary": {
    "id": "pipeline-id",
    "name": "Pipeline Name",
    "meta": {
      "owner": "pipeline-owner"
    },
    "sourceType": "SNOWFLAKE",
    "totalRunsCount": 42,
    "latestRunResult": "SUCCESS",
    "latestRunFinishedAt": "2024-01-01T12:00:00Z"
  }
}
```

### Field Mapping
The command maps the following fields from the API response:
- **Id**: `$.pipelines[].pipelineSummary.id`
- **Name**: `$.pipelines[].pipelineSummary.name`
- **Owner**: `$.pipelines[].pipelineSummary.meta.owner`
- **Source Type**: `$.pipelines[].pipelineSummary.sourceType`
- **Total Runs Count**: `$.pipelines[].pipelineSummary.totalRunsCount`
- **Latest Run Result**: `$.pipelines[].pipelineSummary.latestRunResult`
- **Latest Run Finished At**: `$.pipelines[].pipelineSummary.latestRunFinishedAt`

## Related Commands
- [`show data-sources`](data_sources.md): Show data sources
- [`show`](show.md): General show command documentation 