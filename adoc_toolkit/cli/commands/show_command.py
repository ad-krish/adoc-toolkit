from typing import Any, List

import pandas as pd
from rich.console import Console
from rich.table import Table

from ...http import ADOCHTTPClient
from ...models import (
    FilterCondition,
    ShowCommandArgs,
    SortSpec,
    RESOURCE_REGISTRY,
    ResourceColumnSet,
)
from ...tracing import TraceableMixin, trace_method
from .base import Command
from .show import DataSourceHandler, PipelineSummaryHandler

# Resource handlers mapping
RESOURCE_HANDLERS = {
    "data-sources": DataSourceHandler,
    "pipeline-summary": PipelineSummaryHandler,
}

# Pure functional utilities
def parse_show_args(args: list[str]) -> ShowCommandArgs:
    """Parse show command arguments using pure function.

    Args:
        args: Command line arguments

    Returns:
        ShowCommandArgs object
    """
    return ShowCommandArgs.from_args(args)


def parse_filter_conditions(filter_str: str) -> list[FilterCondition]:
    """Parse filter conditions from comma-separated string using pure function.

    Args:
        filter_str: Filter string like "col=value,col>value"

    Returns:
        List of FilterCondition objects

    Raises:
        ValueError: If filter format is invalid
    """
    if not filter_str:
        return []

    conditions = []
    for condition_str in filter_str.split(","):
        condition_str = condition_str.strip()
        if condition_str:
            conditions.append(FilterCondition.parse(condition_str))
    return conditions


def parse_sort_specs(sort_str: str) -> list[SortSpec]:
    """Parse sort specifications from comma-separated string using pure function.

    Args:
        sort_str: Sort string like "col1,-col2,col3"

    Returns:
        List of SortSpec objects

    Raises:
        ValueError: If sort format is invalid
    """
    if not sort_str:
        return []

    specs = []
    for spec_str in sort_str.split(","):
        spec_str = spec_str.strip()
        if spec_str:
            specs.append(SortSpec.parse(spec_str))
    return specs


def apply_pandas_filter(df: pd.DataFrame, filter_conditions: list[FilterCondition]) -> pd.DataFrame:
    """Apply filter conditions to pandas DataFrame efficiently.

    Args:
        df: Pandas DataFrame to filter
        filter_conditions: List of filter conditions

    Returns:
        Filtered DataFrame
    """
    if not filter_conditions:
        return df
    
    filtered_df = df.copy()
    
    for condition in filter_conditions:
        column = condition.column
        
        if column not in filtered_df.columns:
            continue
        
        # Convert value to appropriate type
        try:
            if condition.operator != "~":
                if filtered_df[column].dtype == 'bool':
                    # Handle boolean values
                    if condition.value.lower() in ("true", "1", "yes"):
                        compare_value = True
                    elif condition.value.lower() in ("false", "0", "no"):
                        compare_value = False
                    else:
                        continue
                elif filtered_df[column].dtype in ['int64', 'int32']:
                    compare_value = int(condition.value)
                elif filtered_df[column].dtype in ['float64', 'float32']:
                    compare_value = float(condition.value)
                else:
                    compare_value = condition.value
            else:
                compare_value = condition.value
        except (ValueError, TypeError):
            # If conversion fails, do string comparison
            compare_value = condition.value
            filtered_df[column] = filtered_df[column].astype(str)
        
        # Apply pandas filtering
        if condition.operator == "=":
            filtered_df = filtered_df[filtered_df[column] == compare_value]
        elif condition.operator == "!=":
            filtered_df = filtered_df[filtered_df[column] != compare_value]
        elif condition.operator == ">":
            filtered_df = filtered_df[filtered_df[column] > compare_value]
        elif condition.operator == "<":
            filtered_df = filtered_df[filtered_df[column] < compare_value]
        elif condition.operator == ">=":
            filtered_df = filtered_df[filtered_df[column] >= compare_value]
        elif condition.operator == "<=":
            filtered_df = filtered_df[filtered_df[column] <= compare_value]
        elif condition.operator == "~":
            filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(compare_value, case=False, na=False)]
    
    return filtered_df


def apply_pandas_sort(df: pd.DataFrame, sort_specs: list[SortSpec]) -> pd.DataFrame:
    """Apply sort specifications to pandas DataFrame efficiently.

    Args:
        df: Pandas DataFrame to sort
        sort_specs: List of sort specifications

    Returns:
        Sorted DataFrame
    """
    if not sort_specs:
        return df
    
    sort_columns = []
    ascending_list = []
    
    for spec in sort_specs:
        column = spec.column
        
        if column in df.columns:
            sort_columns.append(column)
            ascending_list.append(not spec.reverse)
    
    if sort_columns:
        return df.sort_values(by=sort_columns, ascending=ascending_list)
    
    return df


def display_resources(
    console: Console, 
    resources: list[Any],
    resource_type: str,
    filter_conditions: list[FilterCondition] | None = None,
    sort_specs: list[SortSpec] | None = None,
    show_stats: bool = False
) -> None:
    """Display resources in a table using pandas for efficiency.

    Args:
        console: Rich console for output
        resources: List of resource objects
        resource_type: Type of resource
        filter_conditions: Optional filter conditions
        sort_specs: Optional sort specifications
        show_stats: Whether to show column statistics
    """
    if not resources:
        console.print(f"No {resource_type} found.", style="yellow")
        return

    # Convert to DataFrame for efficient operations
    df = pd.DataFrame([r.model_dump() for r in resources])
    original_count = len(df)

    # Apply filtering using pandas
    if filter_conditions:
        df = apply_pandas_filter(df, filter_conditions)
        if df.empty:
            console.print(f"No {resource_type} match the filter criteria.", style="yellow")
            return

    # Apply sorting using pandas
    if sort_specs:
        df = apply_pandas_sort(df, sort_specs)

    # Use the appropriate handler to create and display the table
    if resource_type in RESOURCE_HANDLERS:
        handler_class = RESOURCE_HANDLERS[resource_type]
        # Create a temporary handler instance just for table creation
        temp_handler = handler_class(None)  # We don't need http_client for table creation
        table = temp_handler.create_table(df)
        console.print(table)
    else:
        # Fallback to generic table if no specific handler
        table = Table(title=f"{resource_type.title()}")
        for col in df.columns:
            table.add_column(col)
        for _, row in df.iterrows():
            table.add_row(*[str(v) for v in row.values])
        console.print(table)
    
    # Show summary
    total_count = len(df)
    filter_info = f" (filtered from {original_count} total)" if filter_conditions else ""
    sort_info = " (sorted)" if sort_specs else ""
    console.print(f"\nTotal {resource_type}: {total_count}{filter_info}{sort_info}", style="green")
    
    # Show column statistics if requested
    if show_stats and not df.empty:
        display_column_statistics(console, df)


def display_column_statistics(console: Console, df: pd.DataFrame) -> None:
    """Display column-level statistics for the DataFrame.

    Args:
        console: Rich console for output
        df: Pandas DataFrame to analyze
    """
    console.print("\n📊 Column Statistics:", style="bold cyan")
    
    # Create statistics table
    stats_table = Table(
        title="Column Statistics",
        show_header=True,
        header_style="bold magenta",
        show_lines=True
    )
    
    stats_table.add_column("Column", style="cyan", no_wrap=True)
    stats_table.add_column("Type", style="green")
    stats_table.add_column("Count", style="yellow", justify="right")
    stats_table.add_column("Unique", style="blue", justify="right")
    stats_table.add_column("Null", style="red", justify="right")
    stats_table.add_column("Min", style="white")
    stats_table.add_column("Max", style="white")
    
    for column in df.columns:
        col_data = df[column]
        col_type = str(col_data.dtype)
        count = len(col_data)
        
        # Handle unique count for different column types
        try:
            unique_count = col_data.nunique()
        except (TypeError, ValueError):
            # For columns with unhashable types (lists, dicts, etc.), estimate unique count
            try:
                # Try to convert to strings for counting unique values
                str_values = [str(val) if val is not None else None for val in col_data]
                unique_count = len(set(val for val in str_values if val is not None))
            except:
                unique_count = "N/A"
        
        null_count = col_data.isnull().sum()
        
        # Handle different column types for min/max
        if pd.api.types.is_numeric_dtype(col_data):
            # Numeric columns
            min_val = str(col_data.min()) if not col_data.isnull().all() else "N/A"
            max_val = str(col_data.max()) if not col_data.isnull().all() else "N/A"
        elif col_data.dtype == 'object':
            # Object columns (strings, mixed types, lists, etc.)
            try:
                # Check if column contains lists or other unhashable types
                sample_values = col_data.dropna().head(10)
                has_unhashable = any(isinstance(val, (list, dict, set)) for val in sample_values)
                
                if has_unhashable:
                    # For columns with lists/dicts, show count of non-empty items
                    non_empty_count = sum(1 for val in col_data if val and len(val) > 0)
                    min_val = f"{non_empty_count} non-empty"
                    max_val = "N/A"
                else:
                    # For regular object columns, try min/max
                    min_val = str(col_data.min()) if not col_data.isnull().all() else "N/A"
                    max_val = str(col_data.max()) if not col_data.isnull().all() else "N/A"
            except (TypeError, ValueError):
                min_val = "N/A"
                max_val = "N/A"
        else:
            # Other types (boolean, datetime, etc.)
            try:
                min_val = str(col_data.min()) if not col_data.isnull().all() else "N/A"
                max_val = str(col_data.max()) if not col_data.isnull().all() else "N/A"
            except (TypeError, ValueError):
                min_val = "N/A"
                max_val = "N/A"
        
        stats_table.add_row(
            column,
            col_type,
            str(count),
            str(unique_count),
            str(null_count),
            min_val,
            max_val
        )
    
    console.print(stats_table)


class ShowCommand(Command, TraceableMixin):
    """Show command for displaying various ADOC resources."""

    def __init__(self, http_client: ADOCHTTPClient | None = None):
        """Initialize the show command.

        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client or ADOCHTTPClient()
        self.console = Console()

    @property
    def trace_prefix(self) -> str:
        """Get the trace prefix for this command."""
        return "show"

    @property
    def name(self) -> str:
        return "show"

    @property
    def description(self) -> str:
        return "Show various ADOC resources and information"

    @property
    def aliases(self) -> list[str]:
        return ["s", "display"]

    def get_help(self) -> str:
        """Get detailed help for show command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: show <resource-type> [options]\n\n"
        help_text += "Resource Types:\n"
        for resource_type in RESOURCE_REGISTRY.keys():
            help_text += f"  {resource_type}\n"
        help_text += "\nOptions:\n"
        help_text += "  --filter <expr>   Filter results (col=value,col>value,col~partial)\n"
        help_text += "  --sort <cols>     Sort results (col1,-col2,col3)\n"
        help_text += "  --stats          Show column statistics\n"
        help_text += "  --help           Show this help message\n\n"
        
        # Add available columns for each resource type
        for resource_type, column_set in RESOURCE_REGISTRY.items():
            help_text += f"Available columns for {resource_type}:\n"
            filterable_columns = column_set.get_filterable_columns()
            sortable_columns = column_set.get_sortable_columns()
            
            for col_name in sorted(column_set.get_column_names()):
                col_def = column_set.columns[col_name]
                filterable = "✓" if col_name in filterable_columns else "✗"
                sortable = "✓" if col_name in sortable_columns else "✗"
                help_text += f"  {col_name:<20} ({col_def.display_name}) - Filter: {filterable} Sort: {sortable}\n"
            help_text += "\n"
        
        help_text += "Filter Examples:\n"
        help_text += "  --filter source=SNOWFLAKE\n"
        help_text += "  --filter assembly_id>1000,is_virtual=false\n"
        help_text += "  --filter source=ORACLE,assembly_id<=5000\n"
        help_text += "  --filter source~SNOW\n\n"
        help_text += "Sort Examples:\n"
        help_text += "  --sort assembly\n"
        help_text += "  --sort -assembly_id,source\n"
        help_text += "  --sort source,assembly_id\n\n"
        help_text += "Examples:\n"
        help_text += "  show data-sources\n"
        help_text += "  show data-sources --filter source=SNOWFLAKE\n"
        help_text += "  show data-sources --sort assembly\n"
        help_text += "  show data-sources --filter source=ORACLE --sort -assembly_id\n"
        help_text += "  show data-sources --filter source~SNOW --stats\n"
        help_text += "  show pipeline-summary\n"
        help_text += "  show pipeline-summary --filter source_type=SNOWFLAKE\n"
        help_text += "  show pipeline-summary --sort name\n"
        help_text += "  show --help\n"
        return help_text

    @trace_method("command_execute", "show")
    def execute(self, args: list[str]) -> bool:
        """Execute the show command.

        Args:
            args: Command arguments

        Returns:
            True to continue, False to exit
        """
        self.trace("execution_started", args_count=len(args))

        try:
            # Parse arguments using pure function
            parsed_args = parse_show_args(args)

            # Handle help flag
            if parsed_args.help_flag:
                print(self.get_help())
                self.trace("help_displayed")
                return True

            # Handle resource type
            if parsed_args.resource_type:
                resource_type = parsed_args.resource_type
                self.trace("resource_requested", resource_type=resource_type)

                # Check if resource type is supported
                if resource_type not in RESOURCE_REGISTRY:
                    self.console.print(
                        f"❌ Unknown resource type: {resource_type}",
                        style="red"
                    )
                    self.console.print(
                        f"Available resource types: {', '.join(RESOURCE_REGISTRY.keys())}",
                        style="yellow"
                    )
                    return True

                # Check if environment is set
                env_info = self.http_client._get_environment_info()
                if not env_info.get("base_url"):
                    self.console.print(
                        "❌ No environment set. Use 'use <environment>' first.",
                        style="red"
                    )
                    self.console.print(
                        "Available environments:",
                        style="yellow"
                    )
                    # TODO: Add environment listing logic here
                    return True

                # Parse filter and sort conditions
                filter_conditions = []
                sort_specs = []

                if parsed_args.filter_str:
                    try:
                        filter_conditions = parse_filter_conditions(parsed_args.filter_str)
                        self.trace("filter_conditions_parsed", count=len(filter_conditions))
                    except ValueError as e:
                        self.console.print(f"❌ Invalid filter format: {e}", style="red")
                        return True

                if parsed_args.sort_str:
                    try:
                        sort_specs = parse_sort_specs(parsed_args.sort_str)
                        self.trace("sort_specs_parsed", count=len(sort_specs))
                    except ValueError as e:
                        self.console.print(f"❌ Invalid sort format: {e}", style="red")
                        return True

                # Fetch and display resources using the appropriate handler
                if resource_type in RESOURCE_HANDLERS:
                    handler_class = RESOURCE_HANDLERS[resource_type]
                    handler = handler_class(self.http_client)
                    
                    # Fetch resources
                    resources = handler.fetch_resources()
                    
                    # Display resources with filtering and sorting
                    display_resources(
                        self.console, 
                        resources, 
                        resource_type,
                        filter_conditions, 
                        sort_specs,
                        parsed_args.stats
                    )

                    self.trace(
                        "resources_displayed", 
                        resource_type=resource_type,
                        count=len(resources),
                        filtered=bool(filter_conditions),
                        sorted=bool(sort_specs)
                    )
                else:
                    self.console.print(
                        f"❌ Resource type '{resource_type}' not yet implemented",
                        style="red"
                    )
                    return True

                return True

            # No valid options provided
            self.console.print(
                "Usage: show [options]",
                style="red"
            )
            self.console.print(
                "Use 'show --help' for available options",
                style="yellow"
            )
            return True

        except Exception as e:
            self.trace_error("execution", e, args_count=len(args))
            self.console.print(f"❌ Error: {e}", style="red")
            return True

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[str]:
        """Get auto-completion suggestions.

        Args:
            current_input: Current input string
            cursor_position: Current cursor position

        Returns:
            List of completion suggestions
        """
        input_before = current_input[:cursor_position]
        words = input_before.split()

        if not words:
            return []

        if input_before.endswith(" "):
            last_word = ""
        else:
            last_word = words.pop()

        # If we're completing the command name itself, return resource types
        if last_word == self.name:
            return list(RESOURCE_REGISTRY.keys()) + ["--help"]

        if len(words) == 0:
            return []

        if words[0] != self.name:
            return []

        # Parse the arguments so far
        resource_type = None
        has_filter = False
        has_sort = False
        has_stats = False
        has_help = False
        i = 1
        while i < len(words):
            word = words[i]
            if word == "--filter":
                has_filter = True
                i += 1
                if i < len(words):
                    i += 1
                continue
            elif word == "--sort":
                has_sort = True
                i += 1
                if i < len(words):
                    i += 1
                continue
            elif word == "--stats":
                has_stats = True
                i += 1
                continue
            elif word == "--help":
                has_help = True
                i += 1
                continue
            else:
                if resource_type is None:
                    resource_type = word
                i += 1

        if has_help:
            return []

        if last_word == "":
            if resource_type is None:
                return list(RESOURCE_REGISTRY.keys()) + ["--help"]
            else:
                remaining_opts = []
                if not has_filter:
                    remaining_opts.append("--filter")
                if not has_sort:
                    remaining_opts.append("--sort")
                if not has_stats:
                    remaining_opts.append("--stats")
                remaining_opts.append("--help")
                return remaining_opts

        # Completing last_word
        if resource_type is None and not last_word.startswith("--"):
            return [rt for rt in RESOURCE_REGISTRY.keys() if rt.startswith(last_word)]

        if last_word.startswith("--"):
            possible = []
            if not has_help and "--help".startswith(last_word):
                possible.append("--help")
            if resource_type:
                if not has_filter and "--filter".startswith(last_word):
                    possible.append("--filter")
                if not has_sort and "--sort".startswith(last_word):
                    possible.append("--sort")
                if not has_stats and "--stats".startswith(last_word):
                    possible.append("--stats")
            return possible

        # Completing arg to the last option needing arg
        last_opt_needing_arg = None
        for j in range(len(words) - 1, -1, -1):
            if words[j] in ["--filter", "--sort"]:
                last_opt_needing_arg = words[j]
                break

        if last_opt_needing_arg is None:
            return []

        if resource_type not in RESOURCE_REGISTRY:
            return []

        column_set = RESOURCE_REGISTRY[resource_type]

        if last_opt_needing_arg == "--filter":
            return self._get_filter_completions(last_word, column_set)
        elif last_opt_needing_arg == "--sort":
            return self._get_sort_completions(last_word, column_set)

        return []

    def _get_filter_completions(self, partial: str, column_set: ResourceColumnSet) -> list[str]:
        """Get completions for filter conditions."""
        parts = partial.split(",")
        prefix = ""
        if len(parts) > 1:
            prefix = ",".join(parts[:-1]) + ","
        current_part = parts[-1].strip()

        ops = ["=", "!=", ">=", "<=", ">", "<", "~"]
        has_op = any(current_part.endswith(op) or op in current_part for op in ops)

        if has_op:
            # Completing value
            for op in sorted(ops, key=len, reverse=True):
                if op in current_part:
                    col_val = current_part.rsplit(op, 1)
                    if len(col_val) == 2:
                        col, val = col_val
                        break
            else:
                return []

            col = col.strip()
            if col not in column_set.get_filterable_columns():
                return []

            possible_values = self._get_possible_values_for_column(column_set.columns[col])
            filtered = [v for v in possible_values if v.lower().startswith(val.lower())]
            return [prefix + col + op + f for f in filtered]
        else:
            # Completing column
            filterable = column_set.get_filterable_columns()
            matching_cols = [c for c in filterable if c.startswith(current_part)]
            suggestions = []
            for c in matching_cols:
                for op in ops:
                    suggestions.append(prefix + c + op)
            return suggestions

    def _get_sort_completions(self, partial: str, column_set: ResourceColumnSet) -> list[str]:
        """Get completions for sort specifications."""
        parts = partial.split(",")
        prefix = ""
        if len(parts) > 1:
            prefix = ",".join(parts[:-1]) + ","
        current_part = parts[-1].strip()

        is_desc = current_part.startswith("-")
        current_col = current_part[1:] if is_desc else current_part

        sortable = column_set.get_sortable_columns()
        matching = [c for c in sortable if c.startswith(current_col)]

        if is_desc:
            return [prefix + "-" + c for c in matching]
        else:
            return [prefix + c for c in matching] + [prefix + "-" + c for c in matching]

    def _get_possible_values_for_column(self, col_def) -> list[str]:
        """Get possible suggestion values for a column."""
        if col_def.data_type == "bool":
            return ["true", "false"]
        return []