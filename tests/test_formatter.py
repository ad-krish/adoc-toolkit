"""Tests for HTTP response formatter."""

from adoc_toolkit.http.formatter import ResponseFormatter
from adoc_toolkit.http.http_config import ResponseType


class TestResponseFormatter:
    """Test ResponseFormatter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ResponseFormatter()

    def test_flatten_dict_simple(self):
        """Test flattening of simple dictionary."""
        data = {"name": "test", "age": 30, "active": True}
        flattened = self.formatter._flatten_dict(data)

        expected = [("name", "test"), ("age", 30), ("active", True)]
        assert flattened == expected

    def test_flatten_dict_nested_small(self):
        """Test flattening of small nested dictionary."""
        data = {"user": {"name": "John", "age": 25}, "status": "active"}
        flattened = self.formatter._flatten_dict(data)

        expected = [("user.name", "John"), ("user.age", 25), ("status", "active")]
        assert flattened == expected

    def test_flatten_dict_nested_complex(self):
        """Test flattening of complex nested dictionary."""
        data = {
            "user": {
                "name": "John",
                "profile": {
                    "bio": "Developer",
                    "skills": ["Python", "JavaScript"],
                },
            },
            "metadata": {"created": "2023-01-01", "tags": ["important", "urgent"]},
        }
        flattened = self.formatter._flatten_dict(data)

        # All nested structures should now be flattened
        expected_keys = [
            "user.name",
            "user.profile.bio",
            "user.profile.skills",
            "metadata.created",
            "metadata.tags",
        ]

        actual_keys = [key for key, _ in flattened]
        assert len(flattened) == 5
        for expected_key in expected_keys:
            assert expected_key in actual_keys

    def test_format_dict_as_table(self):
        """Test dictionary table formatting."""
        data = {
            "name": "test",
            "details": {"age": 30, "city": "NYC"},
            "tags": ["tag1", "tag2"],
        }

        result = self.formatter.format_response(data, ResponseType.TABLE)

        assert "name" in result
        assert "test" in result
        assert "details.age" in result
        assert "30" in result
        assert "details.city" in result
        assert "NYC" in result

    def test_format_list_as_table_simple(self):
        """Test simple list table formatting."""
        data = ["item1", "item2", "item3"]

        result = self.formatter.format_response(data, ResponseType.TABLE)

        assert "Index" in result
        assert "Value" in result
        assert "item1" in result
        assert "item2" in result
        assert "item3" in result

    def test_format_list_as_table_dicts_few_keys(self):
        """Test list of dictionaries with few keys (horizontal format)."""
        data = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        result = self.formatter.format_response(data, ResponseType.TABLE)

        assert "name" in result
        assert "age" in result
        assert "John" in result
        assert "Jane" in result

    def test_format_list_as_table_dicts_many_keys(self):
        """Test list of dictionaries with many keys (vertical format)."""
        data = [
            {
                "id": 1,
                "name": "John",
                "email": "john@example.com",
                "department": "Engineering",
                "role": "Developer",
                "skills": ["Python", "JavaScript"],
                "projects": ["Project A", "Project B"],
                "location": "NYC",
                "start_date": "2023-01-01",
            },
            {
                "id": 2,
                "name": "Jane",
                "email": "jane@example.com",
                "department": "Design",
                "role": "Designer",
                "skills": ["Figma", "Sketch"],
                "projects": ["Project C"],
                "location": "SF",
                "start_date": "2023-02-01",
            },
        ]

        result = self.formatter.format_response(data, ResponseType.TABLE)

        # Should use vertical format with Item, Key, Value columns
        assert "Item" in result
        assert "Key" in result
        assert "Value" in result
        assert "Item 1" in result
        assert "Item 2" in result

    def test_format_csv_with_flattening(self):
        """Test CSV formatting with intelligent flattening."""
        data = {"name": "test", "details": {"age": 30, "city": "NYC"}}

        result = self.formatter.format_response(data, ResponseType.CSV)

        assert "name,test" in result
        assert "details.age,30" in result
        assert "details.city,NYC" in result

    def test_format_json_fallback(self):
        """Test JSON formatting fallback."""
        data = {"name": "test", "value": 123}

        result = self.formatter.format_response(data, ResponseType.JSON)

        assert '"name": "test"' in result
        assert '"value": 123' in result

    def test_empty_data_handling(self):
        """Test handling of empty data."""
        # Empty dict
        result = self.formatter.format_response({}, ResponseType.TABLE)
        assert "No data to display" in result

        # Empty list
        result = self.formatter.format_response([], ResponseType.TABLE)
        assert "No data to display" in result

        # None
        result = self.formatter.format_response(None, ResponseType.TABLE)
        assert "No data to display" in result

    def test_complex_nested_structure(self):
        """Test complex nested structure handling."""
        data = {
            "users": [
                {
                    "id": 1,
                    "name": "John",
                    "profile": {"bio": "Developer", "skills": ["Python", "JavaScript"]},
                }
            ],
            "metadata": {"total": 1, "page": 1},
        }

        result = self.formatter.format_response(data, ResponseType.TABLE)

        # Should flatten all nested structures now
        assert "metadata.total" in result
        assert "metadata.page" in result
        # Lists of dictionaries should be flattened with array indices
        assert "users[0].id" in result
        assert "users[0].name" in result
        assert "users[0].profile.bio" in result

    def test_truncation_of_long_values(self):
        """Test truncation of long JSON values in table cells."""
        data = {
            "long_json": {
                "very": {"deeply": {"nested": {"structure": "with many levels"}}}
            }
        }

        result = self.formatter.format_response(data, ResponseType.TABLE)

        # Should flatten the nested structure and truncate long keys
        assert "long_json.very.deeply.nes…" in result
        # The value should be truncated if too long
        assert len(result) < 1000  # Reasonable length

    def test_mixed_data_types(self):
        """Test handling of mixed data types."""
        data = {
            "string": "hello",
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }

        result = self.formatter.format_response(data, ResponseType.TABLE)

        assert "string" in result
        assert "hello" in result
        assert "number" in result
        assert "42" in result
        assert "boolean" in result
        assert "True" in result
        assert "dict.key" in result
        assert "value" in result
