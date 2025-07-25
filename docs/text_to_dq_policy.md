# Text to DQ Policy Command

## Overview

The `text-to-dq-policy` command uses Large Language Models (LLMs) to intelligently convert business text descriptions into structured data quality policies. The LLM analyzes the provided text and maps business requirements to the appropriate JSON fields, creating comprehensive data quality policy structures. The command can generate single or multiple policies based on the complexity of the business requirements.

## Usage

```bash
text-to-dq-policy <text> [--uids <comma-separated-uids>]
text-to-dq-policy --help
```

## Parameters

- `<text>`: The business text description to convert into a data quality policy
- `--uids <comma-separated-uids>`: Optional comma-separated list of UIDs to apply the policy to
- `--help`: Display detailed help information

## LLM Configuration

The command uses the LLM configuration set via the `set-config` command:

- **llm.vendor**: LLM vendor (claude, gemini, grok, chatgpt)
- **llm.model**: Model name for the selected vendor
- **llm.apikey**: API key for the selected LLM vendor

### Configuration Examples

```bash
# Set Grok as the LLM vendor
set-config llm.vendor grok

# Set the model (optional - uses default if not set)
set-config llm.model grok-beta

# Set your API key
set-config llm.apikey your-api-key-here
```

## Examples

### Basic Usage

```bash
ADOC > text-to-dq-policy "Sales data must have valid SALE_ID with no missing values"
```

### Complex Business Requirements

```bash
ADOC > text-to-dq-policy "Customer data quality rules: validate email format for customer_email, ensure customer_id is unique, check for missing phone_number, verify date_of_birth is between 1900-2024"
```

### Data Quality Policy with Partitioning and Thresholds

```bash
ADOC > text-to-dq-policy "Monthly sales data quality policy with 95% success threshold: validate transaction_amount > 0, check for duplicate sale_id, ensure customer_id exists, partition by sale_date"
```

### Policy Generation with UIDs

```bash
# Generate policy for a single UID
ADOC > text-to-dq-policy "Sales data validation with daily partitioning" --uids 9623947

# Generate policies for multiple UIDs
ADOC > text-to-dq-policy "Customer data quality rules: validate email format, check for missing values" --uids 12345,67890,11111

# Generate policies for mixed UID types
ADOC > text-to-dq-policy "Transaction data validation with 90% threshold" --uids 12345,ABC123,67890
```

### Advanced Examples

```bash
# Financial data with comprehensive validations
ADOC > text-to-dq-policy "Financial transaction data quality: validate account_number format, ensure transaction_amount > 0, check for duplicate transaction_id, verify account_id exists, with daily partitioning by transaction_date and 95% success threshold"

# Product catalog with multiple validation types
ADOC > text-to-dq-policy "Product catalog validation: ensure product_id is unique, validate price is numeric and > 0, check for missing category, verify brand exists, with monthly partitioning by created_date"

# Customer data with business rules
ADOC > text-to-dq-policy "Customer data quality: validate email format, ensure customer_id is unique, check for missing phone_number, verify age is between 0-120, validate postal_code format, with daily partitioning by registration_date"

# Multiple business domains (generates multiple policies)
ADOC > text-to-dq-policy "Sales data validation and Customer data validation and Product catalog validation"

# E-commerce with multiple contexts
ADOC > text-to-dq-policy "Order management validation and Inventory tracking validation and Customer profile validation"
```

## Output Format

The command generates structured JSON data quality policies that include:

- **Rule Configuration**: Policy name, description, thresholds, and execution settings
- **Backing Asset**: Table and partition configuration
- **Measurement Items**: Specific data quality checks (missing values, duplicates, etc.)
- **Notification Settings**: Alert and notification configuration
- **Transform UDFs**: Custom transformation functions

### Single vs Multiple Policies

The LLM intelligently determines whether to generate single or multiple policies:

**Single Policy**: When the text describes a coherent data quality requirement
- Example: "Customer data quality validation"
- Output: One JSON policy object

**Multiple Policies**: When the text describes different business domains or contexts
- Example: "Sales data validation and Customer data validation"
- Example: "Product catalog and Inventory management"
- Example: "Financial transactions and Customer accounts"
- Output: Array of JSON policy objects

### Sample Output

#### Single Policy (No UIDs specified)
```json
{
    "rule": {
        "enabled": true,
        "name": "customer_data_quality_policy",
        "description": "Customer data quality validation with email format, uniqueness checks, and missing value validation",
        "thresholdLevel": {
            "success": 95,
            "warning": 70
        },
        "executionTimeoutInMinutes": null,
        "analyticsPipelineId": null,
        "type": "DATA_QUALITY",
        "scheduled": false,
        "backingAsset": {
            "marker": {
                "type": "partition",
                "format": "",
                "frequency": "DAILY",
                "subType": "day-month-year",
                "dayFormat": "DD",
                "monthFormat": "MM",
                "yearFormat": "YYYY",
                "dayColumnName": "DAY",
                "monthColumnName": "MONTH",
                "yearColumnName": "YEAR",
                "offset": 0,
                "prefix": null,
                "suffix": null,
                "timeZoneId": "UTC",
                "baseAssetId": null
            },
            "tableAssetId": <uid>
        },
        "notificationChannels": {
            "configuredNotificationGroupIds": [],
            "notifyOn": [],
            "notifyOnSuccess": false,
            "reNotifyFactor": 0
        },
        "sparkResourceConfig": null,
        "labels": ["customer", "data-quality"],
        "policyGroups": [],
        "additionalPersistedColumns": [
            "CREATED_DATE"
        ],
        "segments": null,
        "filter": "",
        "sparkSQLFilterType": "STATIC",
        "sparkFilterSelectedColumns": null
    },
    "items": [
        {
            "measurementType": "FORMAT_VALIDATION",
            "columnName": "CUSTOMER_EMAIL",
            "executionOrder": 1,
            "weightage": 100,
            "businessExplanation": "Email format validation for customer communication",
            "labels": ["email", "format"],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        },
        {
            "measurementType": "UNIQUE_VALUES",
            "columnName": "CUSTOMER_ID",
            "executionOrder": 2,
            "weightage": 100,
            "businessExplanation": "Ensure customer ID uniqueness for data integrity",
            "labels": ["unique", "identifier"],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        },
        {
            "measurementType": "MISSING_VALUES",
            "columnName": "PHONE_NUMBER",
            "executionOrder": 3,
            "weightage": 80,
            "businessExplanation": "Check for missing phone numbers for customer contact",
            "labels": ["contact", "missing"],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        },
        {
            "measurementType": "RANGE_VALIDATION",
            "columnName": "DATE_OF_BIRTH",
            "executionOrder": 4,
            "weightage": 90,
            "businessExplanation": "Validate date of birth is within reasonable range (1900-2024)",
            "labels": ["date", "range"],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        }
    ],
    "transformUDFs": []
}
```

#### Multiple Policies (With UIDs specified)
When using the `--uids` option, a cross product is created: policies × UIDs.

**Example with Single Policy:**
```bash
ADOC > text-to-dq-policy "Sales data validation" --uids 12345,67890
```
Result: 1 policy × 2 UIDs = 2 total policies

**Example with Multiple Policies:**
```bash
ADOC > text-to-dq-policy "Sales data validation and Customer data validation" --uids 12345,67890
```
Result: 2 policies × 2 UIDs = 4 total policies

**Output for UID 12345:**
```json
{
    "rule": {
        "enabled": true,
        "name": "sales_dq_policy_date_incremental_partition_day_month_year",
        "description": "Sales DQ Policy date based incremental partiton day month year",
        "thresholdLevel": {
            "success": 100,
            "warning": 70
        },
        "executionTimeoutInMinutes": null,
        "analyticsPipelineId": null,
        "type": "DATA_QUALITY",
        "scheduled": false,
        "backingAsset": {
            "marker": {
                "type": "partition",
                "format": "",
                "frequency": "MONTHLY",
                "subType": "day-month-year",
                "dayFormat": "DD",
                "monthFormat": "MM",
                "yearFormat": "YYYY",
                "dayColumnName": "DAY",
                "monthColumnName": "MONTH",
                "yearColumnName": "YEAR",
                "offset": 0,
                "prefix": null,
                "suffix": null,
                "timeZoneId": "UTC",
                "baseAssetId": null
            },
            "tableAssetId": 12345
        },
        "notificationChannels": {
            "configuredNotificationGroupIds": [],
            "notifyOn": [],
            "notifyOnSuccess": false,
            "reNotifyFactor": 0
        },
        "sparkResourceConfig": null,
        "labels": [],
        "policyGroups": [],
        "additionalPersistedColumns": [
            "DATE"
        ],
        "segments": null,
        "filter": "",
        "sparkSQLFilterType": "STATIC",
        "sparkFilterSelectedColumns": null
    },
    "items": [
        {
            "measurementType": "MISSING_VALUES",
            "columnName": "SALE_ID",
            "executionOrder": 1,
            "weightage": 100,
            "businessExplanation": "",
            "labels": [],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        }
    ],
    "transformUDFs": []
}
```

**Output for UID 67890:**
```json
{
    "rule": {
        "enabled": true,
        "name": "sales_dq_policy_date_incremental_partition_day_month_year",
        "description": "Sales DQ Policy date based incremental partiton day month year",
        "thresholdLevel": {
            "success": 100,
            "warning": 70
        },
        "executionTimeoutInMinutes": null,
        "analyticsPipelineId": null,
        "type": "DATA_QUALITY",
        "scheduled": false,
        "backingAsset": {
            "marker": {
                "type": "partition",
                "format": "",
                "frequency": "MONTHLY",
                "subType": "day-month-year",
                "dayFormat": "DD",
                "monthFormat": "MM",
                "yearFormat": "YYYY",
                "dayColumnName": "DAY",
                "monthColumnName": "MONTH",
                "yearColumnName": "YEAR",
                "offset": 0,
                "prefix": null,
                "suffix": null,
                "timeZoneId": "UTC",
                "baseAssetId": null
            },
            "tableAssetId": 67890
        },
        "notificationChannels": {
            "configuredNotificationGroupIds": [],
            "notifyOn": [],
            "notifyOnSuccess": false,
            "reNotifyFactor": 0
        },
        "sparkResourceConfig": null,
        "labels": [],
        "policyGroups": [],
        "additionalPersistedColumns": [
            "DATE"
        ],
        "segments": null,
        "filter": "",
        "sparkSQLFilterType": "STATIC",
        "sparkFilterSelectedColumns": null
    },
    "items": [
        {
            "measurementType": "MISSING_VALUES",
            "columnName": "SALE_ID",
            "executionOrder": 1,
            "weightage": 100,
            "businessExplanation": "",
            "labels": [],
            "isWarning": false,
            "value": {
                "addEmptyCheck": false
            }
        }
    ],
    "transformUDFs": []
}
```

## Supported LLM Vendors

Currently, the command supports the following LLM vendors:

### Grok (Recommended)
- **Default Model**: `grok-beta`
- **Available Models**: `grok-beta`, `grok-2`
- **Features**: Optimized for reasoning and complex policy generation

### Claude
- **Default Model**: `claude-3-5-sonnet-20241022`
- **Available Models**: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, `claude-3-opus-20240229`, `claude-3-sonnet-20240229`
- **Features**: Excellent for structured output and policy generation

### Gemini
- **Default Model**: `gemini-1.5-pro`
- **Available Models**: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-1.0-pro`
- **Features**: Good for general policy generation tasks

### Other Vendors (Coming Soon)
- **ChatGPT**: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`

## Error Handling

The command provides clear error messages for common issues:

### Missing Configuration
```bash
Error: LLM API key not configured. Use 'set-config llm.apikey <your-api-key>'
Error: LLM vendor not configured. Use 'set-config llm.vendor <vendor>'
```

### Unsupported Vendor
```bash
Error: Unsupported LLM vendor: unknown
```

### Missing Dependencies
```bash
Error: xai-sdk not installed. Please install it with 'uv add xai-sdk'
Error: google-generativeai not installed. Please install it with 'uv add google-generativeai'
Error: anthropic not installed. Please install it with 'uv add anthropic'
```

## Aliases

The command supports the following aliases:
- `dq-policy`
- `text2dq`

## Integration with ADOC Toolkit

The `text-to-dq-policy` command integrates seamlessly with the ADOC toolkit:

- **Configuration Management**: Uses the same configuration system as other commands
- **Interactive Shell**: Works within the interactive ADOC shell
- **Help System**: Supports both `help text-to-dq-policy` and `text-to-dq-policy --help`
- **Auto-completion**: Provides intelligent completion suggestions
- **History**: Command usage is tracked in the command history

## Best Practices

### Writing Effective Prompts

The LLM intelligently extracts and maps information from your text. Here's what it can understand:

#### **Validation Types** (automatically mapped):
- **Missing Values**: "no missing values", "check for nulls", "ensure populated"
- **Duplicates**: "no duplicates", "unique values", "check for duplicates"
- **Format Validation**: "valid email", "proper format", "format validation"
- **Range Validation**: "between X and Y", "within range", "valid range"
- **Uniqueness**: "unique", "distinct", "no duplicates"
- **Data Type**: "numeric", "string", "date", "boolean"

#### **Partitioning Types** (automatically detected):
- **Daily**: "daily", "day", "daily partitioning"
- **Monthly**: "monthly", "month", "monthly partitioning"
- **Yearly**: "yearly", "year", "yearly partitioning"
- **Incremental**: "incremental", "id-based", "sequential"

#### **Thresholds** (automatically extracted):
- **Success Threshold**: "95% success", "100% threshold", "success rate"
- **Warning Threshold**: "70% warning", "warning level"

### Example Effective Prompts

```bash
# Comprehensive data quality rules
text-to-dq-policy "Customer data quality policy: validate email format for customer_email, ensure customer_id is unique, check for missing phone_number, verify date_of_birth is between 1900-2024, with 95% success threshold and daily partitioning by created_date"

# Sales data with specific validations
text-to-dq-policy "Sales data validation: ensure SALE_ID has no missing values, validate transaction_amount is positive, check for duplicate sale_id, verify customer_id exists, with monthly partitioning and 90% threshold"

# Simple validation
text-to-dq-policy "Product data: check for missing product_id, validate price is numeric, ensure category is not null"

# With business context
text-to-dq-policy "Financial transaction data quality: validate account_number format, ensure transaction_amount > 0, check for duplicate transaction_id, verify account_id exists, with daily partitioning by transaction_date"
```

### **What the LLM Extracts Automatically:**

1. **Policy Name**: Creates descriptive name from business context
2. **Description**: Summarizes data quality requirements
3. **Columns**: Identifies all columns needing validation
4. **Validation Types**: Maps to appropriate measurement types
5. **Thresholds**: Extracts success/warning levels
6. **Partitioning**: Detects and configures partitioning strategy
7. **Timeouts**: Extracts execution timeouts if mentioned
8. **Filters**: Identifies filtering conditions
9. **Labels**: Extracts business labels and tags
10. **Notifications**: Identifies notification requirements

### **Cross Product with UIDs:**

When UIDs are specified, the command creates a cross product:

- **Single Policy + Multiple UIDs**: 1 policy × N UIDs = N total policies
- **Multiple Policies + Multiple UIDs**: M policies × N UIDs = M×N total policies

**Examples:**
- 1 policy + 3 UIDs = 3 total policies
- 2 policies + 3 UIDs = 6 total policies
- 3 policies + 2 UIDs = 6 total policies

## Related Commands

- [`set-config`](set_config.md): Configure LLM settings
- [`show-config`](show_config.md): View current configuration
- [`help`](help.md): Get help on available commands

## Troubleshooting

### Common Issues

1. **API Key Issues**
   - Ensure your API key is valid and has sufficient credits
   - Check that the API key is correctly set via `set-config llm.apikey`

2. **Model Selection**
   - Verify the model name is correct for your vendor
   - Use `set-config llm.model` to specify a different model

3. **Timeout Issues**
   - Complex policies may take longer to generate
   - The command uses a 3600-second timeout for reasoning models

4. **JSON Output Issues**
   - The LLM is instructed to output only valid JSON
   - If malformed JSON is returned, try rephrasing your prompt

### Getting Help

```bash
# Get command help
text-to-dq-policy --help

# Get general help
help text-to-dq-policy

# Check LLM configuration
set-config --list | grep llm
``` 