"""Resource registry for managing different resource types."""

from .base_models import ResourceColumnSet
from .data_source_models import DATA_SOURCE_COLUMNS
from .pipeline_models import PIPELINE_SUMMARY_COLUMNS

# Resource registry for managing different resource types
RESOURCE_REGISTRY = {
    "data-sources": DATA_SOURCE_COLUMNS,
    "pipeline-summary": PIPELINE_SUMMARY_COLUMNS,
    # Future resource types can be added here:
    # "assets": ASSET_COLUMNS,
    # "rules": RULE_COLUMNS,
    # "policies": POLICY_COLUMNS,
} 