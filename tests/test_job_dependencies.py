"""Tests for job dependency and background worker functionality."""

from __future__ import annotations

import json
import time
from unittest.mock import Mock, patch

import pytest

from mindloom_core.models import EthemeralTaskType, Job, JobCreate, Status
from mindloom.template_parser import extract_job_ids, replace_templates, validate_template


class TestTemplateParser:
    """Tests for template parsing functions."""
    
    def test_extract_job_ids_simple(self):
        """Test extracting a single job ID."""
        content = "Summarize this: {{123456}}"
        result = extract_job_ids(content)
        assert result == [123456]
    
    def test_extract_job_ids_multiple(self):
        """Test extracting multiple job IDs."""
        content = "Compare {{100}} with {{200}} and {{300}}"
        result = extract_job_ids(content)
        assert result == [100, 200, 300]
    
    def test_extract_job_ids_duplicates(self):
        """Test that duplicates are removed."""
        content = "Use {{100}} and also {{100}} again"
        result = extract_job_ids(content)
        assert result == [100]
    
    def test_extract_job_ids_no_templates(self):
        """Test content without templates."""
        content = "This has no templates"
        result = extract_job_ids(content)
        assert result == []
    
    def test_extract_job_ids_empty(self):
        """Test empty content."""
        result = extract_job_ids("")
        assert result == []
    
    def test_replace_templates_simple(self):
        """Test replacing a single template."""
        content = "Summary: {{100}}"
        results = {100: "Hello world"}
        result = replace_templates(content, results)
        assert result == "Summary: Hello world"
    
    def test_replace_templates_multiple(self):
        """Test replacing multiple templates."""
        content = "First: {{1}}, Second: {{2}}"
        results = {1: "A", 2: "B"}
        result = replace_templates(content, results)
        assert result == "First: A, Second: B"
    
    def test_replace_templates_missing_key(self):
        """Test that missing keys are left unchanged."""
        content = "Available: {{100}}, Missing: {{200}}"
        results = {100: "Found"}
        result = replace_templates(content, results)
        assert result == "Available: Found, Missing: {{200}}"
    
    def test_validate_template_valid(self):
        """Test valid template."""
        assert validate_template("Valid {{123}}") is None
    
    def test_validate_template_invalid_placeholder(self):
        """Test invalid placeholder with non-numeric content."""
        error = validate_template("Invalid {{abc}}")
        assert error is not None
        assert "Invalid template placeholder" in error
    
    def test_validate_template_unmatched_braces(self):
        """Test unmatched braces."""
        error = validate_template("Unmatched {{123")
        assert error is not None
        assert "Unmatched template braces" in error


class TestJobDependencies:
    """Tests for job dependency detection and resolution."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()
    
    def test_create_job_no_dependencies(self, mock_db):
        """Test creating a job without dependencies."""
        from mindloom.db import create_job
        
        # Mock get_job_by_id to return None (no existing jobs)
        with patch('mindloom.db.get_job_by_id', return_value=None):
            job_data = JobCreate(
                task_type=EthemeralTaskType.SUMMARIZE,
                content="Simple content without templates"
            )
            
            job = create_job(mock_db, job_data)
            
            assert job.status == Status.PENDING.value
            assert job.dependencies is None
    
    def test_create_job_with_dependencies(self, mock_db):
        """Test creating a job with template dependencies."""
        from mindloom.db import create_job
        
        # Mock existing job
        existing_job = Job(
            id=100,
            task_type=str(EthemeralTaskType.SUMMARIZE.value),
            content="Test",
            result="Test result",
            status=Status.COMPLETED.value,
            created_at=None,
            updated_at=None,
        )
        
        with patch('mindloom.db.get_job_by_id', return_value=existing_job):
            job_data = JobCreate(
                task_type=EthemeralTaskType.SECTION,
                content="Expand on this: {{100}}"
            )
            
            job = create_job(mock_db, job_data)
            
            assert job.status == Status.WAITING_FOR.value
            assert job.dependencies == "[100]"
    
    def test_create_job_invalid_dependency(self, mock_db):
        """Test that referencing non-existent job raises error."""
        from mindloom.db import create_job
        
        with patch('mindloom.db.get_job_by_id', return_value=None):
            job_data = JobCreate(
                task_type=EthemeralTaskType.SECTION,
                content="Use {{999999}}"  # Non-existent job
            )
            
            with pytest.raises(ValueError, match="does not exist"):
                create_job(mock_db, job_data)


class TestBackgroundWorker:
    """Tests for background worker functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.execute = Mock(return_value=Mock())
        db.shutdown = Mock()
        return db
    
    def test_worker_initialization(self):
        """Test worker initializes correctly."""
        from mindloom.worker import BackgroundWorker
        
        worker = BackgroundWorker(poll_interval=10)
        assert worker.poll_interval == 10
        assert not worker._running
    
    def test_worker_start_stop(self):
        """Test worker start and stop."""
        from mindloom.worker import BackgroundWorker
        
        worker = BackgroundWorker(poll_interval=60)
        worker.start()
        assert worker._running
        
        worker.stop()
        assert not worker._running
    
    def test_check_dependencies_all_completed(self, mock_db):
        """Test dependency checking when all are completed."""
        from mindloom.worker import BackgroundWorker
        
        # Mock database responses
        completed_job = {
            "id": 100,
            "status": Status.COMPLETED.value,
            "result": "Job 100 result"
        }
        mock_db.execute.return_value.one.return_value = completed_job
        
        worker = BackgroundWorker(poll_interval=60)
        ready, results = worker._check_dependencies_ready(mock_db, [100], 200)
        
        assert ready is True
        assert results == {100: "Job 100 result"}
    
    def test_check_dependencies_one_failed(self, mock_db):
        """Test dependency checking when one has failed."""
        from mindloom.worker import BackgroundWorker
        
        failed_job = {
            "id": 100,
            "status": Status.FAILED.value,
            "result": None
        }
        mock_db.execute.return_value.one.return_value = failed_job
        
        worker = BackgroundWorker(poll_interval=60)
        ready, results = worker._check_dependencies_ready(mock_db, [100], 200)
        
        assert ready is False
        assert results == {}
    
    def test_check_dependencies_not_completed(self, mock_db):
        """Test dependency checking when still pending."""
        from mindloom.worker import BackgroundWorker
        
        pending_job = {
            "id": 100,
            "status": Status.PENDING.value,
            "result": None
        }
        mock_db.execute.return_value.one.return_value = pending_job
        
        worker = BackgroundWorker(poll_interval=60)
        ready, results = worker._check_dependencies_ready(mock_db, [100], 200)
        
        assert ready is False
        assert results == {}
    
    def test_check_dependencies_missing_job(self, mock_db):
        """Test dependency checking when job doesn't exist."""
        from mindloom.worker import BackgroundWorker
        
        mock_db.execute.return_value.one.return_value = None
        
        worker = BackgroundWorker(poll_interval=60)
        ready, results = worker._check_dependencies_ready(mock_db, [999], 200)
        
        assert ready is False
        assert results == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
