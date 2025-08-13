"""Pipeline models for show command."""

from datetime import datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from .base_models import ColumnDefinition, ResourceColumnSet


class PipelineSummaryMeta(BaseModel):
    """Model for pipeline summary metadata."""

    owner: str | None = Field(default=None, description="Pipeline owner")
    # Add other meta fields as needed
    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }


class PipelineSummaryData(BaseModel):
    """Model for the actual pipeline summary data from the nested structure."""

    id: str | None = Field(default=None, description="Pipeline ID")
    name: str | None = Field(default=None, description="Pipeline name")
    meta: PipelineSummaryMeta | None = Field(
        default=None, description="Pipeline metadata"
    )
    source_type: str | None = Field(
        alias="sourceType", default=None, description="Pipeline source type"
    )
    total_runs_count: int | None = Field(
        alias="totalRunsCount", default=None, description="Total number of runs"
    )
    latest_run_result: str | None = Field(
        alias="latestRunResult", default=None, description="Latest run result"
    )
    latest_run_finished_at: datetime | None = Field(
        alias="latestRunFinishedAt",
        default=None,
        description="Latest run finished time"
    )

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    @field_validator('id', mode='before')
    @classmethod
    def coerce_id_to_str(cls, v):
        if v is None:
            return None
        return str(v)

    @field_validator('name', mode='before')
    @classmethod
    def coerce_name_to_str(cls, v):
        if v is None:
            return None
        return str(v)

    @property
    def owner(self) -> str | None:
        """Get owner from meta object."""
        return self.meta.owner if self.meta else None


class PipelineSummary(BaseModel):
    """Model for a pipeline summary from the orchestration API."""

    pipeline_summary: PipelineSummaryData | None = Field(
        alias="pipelineSummary", default=None, description="Pipeline summary data"
    )

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    @property
    def id(self) -> str | None:
        """Get pipeline ID from nested structure."""
        return self.pipeline_summary.id if self.pipeline_summary else None

    @property
    def name(self) -> str | None:
        """Get pipeline name from nested structure."""
        return self.pipeline_summary.name if self.pipeline_summary else None

    @property
    def owner(self) -> str | None:
        """Get pipeline owner from nested structure."""
        return self.pipeline_summary.owner if self.pipeline_summary else None

    @property
    def source_type(self) -> str | None:
        """Get pipeline source type from nested structure."""
        return self.pipeline_summary.source_type if self.pipeline_summary else None

    @property
    def total_runs_count(self) -> int | None:
        """Get total runs count from nested structure."""
        return self.pipeline_summary.total_runs_count if self.pipeline_summary else None

    @property
    def latest_run_result(self) -> str | None:
        """Get latest run result from nested structure."""
        return (
            self.pipeline_summary.latest_run_result if self.pipeline_summary else None
        )

    @property
    def latest_run_finished_at(self) -> datetime | None:
        """Get latest run finished time from nested structure."""
        if self.pipeline_summary:
            return self.pipeline_summary.latest_run_finished_at
        return None

    def model_dump(self, **kwargs):
        """Override model_dump to flatten the nested structure for 
           DataFrame compatibility."""
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "source_type": self.source_type,
            "total_runs_count": self.total_runs_count,
            "latest_run_result": self.latest_run_result,
            "latest_run_finished_at": self.latest_run_finished_at,
        }


class PipelineSummaryResponseMeta(BaseModel):
    """Model for pipeline summary response metadata."""

    count: int = Field(description="Total count of pipelines")
    size: int = Field(description="Page size")


class PipelineSummaryResponse(BaseModel):
    """Model for pipeline summary API response."""

    meta: PipelineSummaryResponseMeta = Field(description="Response metadata")
    pipelines: list[PipelineSummary] = Field(description="List of pipeline summaries")
    df: pd.DataFrame | None = Field(default=None, description="Pandas DataFrame")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

    @classmethod
    def from_api_response(
        cls, response_data: dict[str, Any]
    ) -> "PipelineSummaryResponse":
        """Create PipelineSummaryResponse from API response data.

        Args:
            response_data: Raw API response data

        Returns:
            PipelineSummaryResponse object
        """

        # Handle different possible response structures
        if isinstance(response_data, list):
            # If response is a list directly, treat it as pipelines
            pipelines = [PipelineSummary.model_validate(item) for item in response_data]
            meta = PipelineSummaryResponseMeta(
                count=len(pipelines), size=len(pipelines)
            )
        elif isinstance(response_data, dict):
            # Check if it has the expected structure
            if "meta" in response_data and "pipelines" in response_data:
                meta = PipelineSummaryResponseMeta.model_validate(
                    response_data.get("meta", {})
                )
                pipelines = [
                    PipelineSummary.model_validate(item)
                    for item in response_data.get("pipelines", [])
                ]
            elif "pipelines" in response_data:
                # Has pipelines but no meta
                pipelines = [
                    PipelineSummary.model_validate(item)
                    for item in response_data.get("pipelines", [])
                ]
                meta = PipelineSummaryResponseMeta(
                    count=len(pipelines), size=len(pipelines)
                )
            else:
                # Try to treat the entire response as a single pipeline or list of
                # pipelines
                try:
                    # Try as single pipeline
                    pipeline = PipelineSummary.model_validate(response_data)
                    pipelines = [pipeline]
                    meta = PipelineSummaryResponseMeta(count=1, size=1)
                except Exception:
                    # Try as list of pipelines
                    if isinstance(response_data, dict):
                        # Convert dict to list of pipelines
                        pipelines = [PipelineSummary.model_validate(response_data)]
                        meta = PipelineSummaryResponseMeta(count=1, size=1)
                    else:
                        # Try to handle case where pipelines don't have nested pipelineSummary
                        # This might be the actual API response structure
                        if "pipelines" in response_data:
                            pipelines_data = response_data.get("pipelines", [])
                            pipelines = []
                            for pipeline_data in pipelines_data:
                                # Check if pipeline data has nested structure
                                if "pipelineSummary" in pipeline_data:
                                    pipeline = PipelineSummary.model_validate(pipeline_data)
                                else:
                                    # Create a PipelineSummaryData directly from the pipeline data
                                    # This handles the case where the API returns direct pipeline data
                                    pipeline_summary_data = PipelineSummaryData.model_validate(pipeline_data)
                                    pipeline = PipelineSummary(pipeline_summary=pipeline_summary_data)
                                pipelines.append(pipeline)
                            meta = PipelineSummaryResponseMeta(
                                count=len(pipelines), size=len(pipelines)
                            )
                        else:
                            raise ValueError(
                                f"Unexpected response structure: {type(response_data)}"
                            ) from None
        else:
            raise ValueError(f"Unexpected response type: {type(response_data)}")

        # Create pandas DataFrame for efficient operations
        df = pd.DataFrame([p.model_dump() for p in pipelines])

        return cls(meta=meta, pipelines=pipelines, df=df)


# Column definitions for pipeline summaries
PIPELINE_SUMMARY_COLUMNS = ResourceColumnSet(
    resource_type="pipeline-summary",
    columns={
        "id": ColumnDefinition(
            name="id",
            display_name="Id",
            description="Pipeline ID",
            data_type="string"
        ),
        "name": ColumnDefinition(
            name="name",
            display_name="Name",
            description="Pipeline name",
            data_type="string"
        ),
        "owner": ColumnDefinition(
            name="owner",
            display_name="Owner",
            description="Pipeline owner",
            data_type="string"
        ),
        "source_type": ColumnDefinition(
            name="source_type",
            display_name="Source",
            description="Pipeline source type",
            data_type="string"
        ),
        "total_runs_count": ColumnDefinition(
            name="total_runs_count",
            display_name="# Runs",
            description="Total number of runs",
            data_type="int"
        ),
        "latest_run_result": ColumnDefinition(
            name="latest_run_result",
            display_name="Last Run Status",
            description="Latest run result",
            data_type="string"
        ),
        "latest_run_finished_at": ColumnDefinition(
            name="latest_run_finished_at",
            display_name="Finished Time in UTC",
            description="Latest run finished time",
            data_type="datetime"
        ),
    }
)
