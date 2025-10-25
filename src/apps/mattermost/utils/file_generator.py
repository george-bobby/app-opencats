import contextlib
import random
import tempfile
from pathlib import Path
from typing import ClassVar


class FileGenerator:
    """Generate realistic files for Mattermost attachments."""

    # File types and their relative probabilities
    FILE_TYPES: ClassVar[dict] = {
        "text": {
            "extensions": [".txt", ".md", ".log"],
            "probability": 0.25,
            "mime_types": ["text/plain", "text/markdown", "text/plain"],
        },
        "documents": {
            "extensions": [".pdf", ".doc", ".docx"],
            "probability": 0.30,
            "mime_types": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        },
        "spreadsheets": {
            "extensions": [".xlsx", ".csv"],
            "probability": 0.15,
            "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"],
        },
        "images": {
            "extensions": [".png", ".jpg", ".jpeg"],
            "probability": 0.20,
            "mime_types": ["image/png", "image/jpeg", "image/jpeg"],
        },
        "archives": {
            "extensions": [".zip", ".tar.gz"],
            "probability": 0.10,
            "mime_types": ["application/zip", "application/gzip"],
        },
    }

    # Realistic filenames based on business context
    FILENAME_TEMPLATES: ClassVar[dict] = {
        "documents": [
            "Q{quarter}_Report_{year}",
            "Meeting_Notes_{month}_{day}",
            "Project_Proposal_{project}",
            "Requirements_{feature}",
            "Design_Spec_{component}",
            "User_Manual_v{version}",
            "API_Documentation",
            "Performance_Analysis",
            "Security_Audit_Report",
            "Budget_Planning_{year}",
        ],
        "spreadsheets": [
            "Sales_Data_{quarter}_{year}",
            "User_Analytics_{month}",
            "Team_Performance_Metrics",
            "Project_Timeline",
            "Resource_Allocation",
            "Expense_Report_{month}",
            "Customer_List_Export",
            "Feature_Comparison",
        ],
        "text": [
            "deployment_logs_{date}",
            "error_analysis",
            "configuration_notes",
            "troubleshooting_steps",
            "meeting_agenda_{date}",
            "code_review_comments",
            "release_notes_v{version}",
            "test_results_{feature}",
        ],
        "images": [
            "screenshot_{feature}",
            "ui_mockup_{page}",
            "diagram_{system}",
            "flowchart_{process}",
            "architecture_overview",
            "user_interface_design",
            "logo_variations",
            "presentation_slide_{number}",
        ],
        "archives": [
            "backup_{date}",
            "project_files_{version}",
            "assets_package",
            "deployment_bundle",
            "source_code_archive",
            "documentation_export",
        ],
    }

    @classmethod
    def generate_random_filename(cls, file_category: str) -> str:
        """Generate a realistic filename for the given category."""
        templates = cls.FILENAME_TEMPLATES.get(file_category, ["document_{random}"])
        template = random.choice(templates)

        # Fill in template variables
        replacements = {
            "quarter": f"Q{random.randint(1, 4)}",
            "year": random.choice(["2024", "2025"]),
            "month": random.choice(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]),
            "day": f"{random.randint(1, 28):02d}",
            "date": f"2025_{random.randint(1, 12):02d}_{random.randint(1, 28):02d}",
            "version": f"{random.randint(1, 3)}.{random.randint(0, 9)}",
            "project": random.choice(["Phoenix", "Atlas", "Nexus", "Orbit", "Zenith"]),
            "feature": random.choice(["login", "dashboard", "api", "search", "notifications", "reports"]),
            "component": random.choice(["auth", "database", "frontend", "backend", "mobile"]),
            "system": random.choice(["payment", "user_mgmt", "analytics", "messaging"]),
            "process": random.choice(["deployment", "onboarding", "approval", "review"]),
            "page": random.choice(["login", "dashboard", "settings", "profile", "admin"]),
            "number": f"{random.randint(1, 20)}",
            "random": f"{random.randint(1000, 9999)}",
        }

        for key, value in replacements.items():
            template = template.replace(f"{{{key}}}", value)

        return template

    @classmethod
    def select_file_type(cls) -> tuple[str, str, str]:
        """Select a random file type based on probabilities."""
        rand = random.random()
        cumulative = 0

        for category, info in cls.FILE_TYPES.items():
            cumulative += info["probability"]
            if rand <= cumulative:
                extension_idx = random.randint(0, len(info["extensions"]) - 1)
                extension = info["extensions"][extension_idx]
                mime_type = info["mime_types"][extension_idx]
                return category, extension, mime_type

        # Fallback to text files
        return "text", ".txt", "text/plain"

    @classmethod
    def create_sample_file(cls, file_category: str, extension: str, filename: str) -> str:
        """Create a sample file with realistic content."""
        temp_dir = Path(tempfile.gettempdir()) / "mattermost_files"
        temp_dir.mkdir(exist_ok=True)

        full_filename = f"{filename}{extension}"
        file_path = temp_dir / full_filename

        if file_category == "text":
            cls._create_text_file(file_path, filename)
        elif file_category == "documents":
            cls._create_document_file(file_path, filename)
        elif file_category == "spreadsheets":
            cls._create_spreadsheet_file(file_path, filename)
        elif file_category == "images":
            cls._create_image_file(file_path, filename)
        elif file_category == "archives":
            cls._create_archive_file(file_path, filename)

        return str(file_path)

    @classmethod
    def _create_text_file(cls, file_path: Path, filename: str):
        """Create a realistic text file."""
        content_templates = [
            (
                f"# {filename.replace('_', ' ').title()}\n\n"
                f"Date: 2025-09-10\nAuthor: System Generated\n\n## Summary\n\n"
                f"This document contains important information about {filename.replace('_', ' ')}.\n\n"
                f"## Details\n\n- Item 1: Configuration updated\n- Item 2: Performance metrics reviewed\n"
                f"- Item 3: Next steps identified\n\n## Conclusion\n\n"
                f"All items have been addressed successfully."
            ),
            (
                f"Log Entry - {filename}\n{'=' * 50}\n\n[INFO] Process started successfully\n"
                f"[DEBUG] Loading configuration\n[INFO] Configuration loaded\n[DEBUG] Connecting to database\n"
                f"[INFO] Database connection established\n[WARN] High memory usage detected\n"
                f"[INFO] Process completed\n\nEnd of log"
            ),
            (
                f"Meeting Notes: {filename.replace('_', ' ').title()}\n\nAttendees: John, Sarah, Mike, Lisa\n"
                f"Date: 2025-09-10\n\nAgenda:\n1. Project status review\n2. Budget discussion\n"
                f"3. Timeline updates\n\nAction Items:\n- Sarah: Update documentation by Friday\n"
                f"- Mike: Review performance metrics\n- Lisa: Schedule follow-up meeting"
            ),
        ]

        content = random.choice(content_templates)
        file_path.write_text(content, encoding="utf-8")

    @classmethod
    def _create_document_file(cls, file_path: Path, filename: str):
        """Create a simple document file (text-based for now)."""
        content = f"""Document: {filename.replace("_", " ").title()}
Generated: 2025-09-10

EXECUTIVE SUMMARY
This document provides a comprehensive overview of {filename.replace("_", " ")}.

INTRODUCTION
The purpose of this document is to outline the key findings and recommendations.

MAIN CONTENT
1. Background Information
   - Current state analysis
   - Key stakeholders identified
   - Timeline established

2. Findings
   - Performance metrics reviewed
   - Areas for improvement identified
   - Best practices documented

3. Recommendations
   - Implement new processes
   - Upgrade existing systems
   - Train team members

CONCLUSION
All objectives have been met and next steps have been identified.

Prepared by: System
Date: 2025-09-10
"""
        file_path.write_text(content, encoding="utf-8")

    @classmethod
    def _create_spreadsheet_file(cls, file_path: Path, filename: str):
        """Create a CSV file with sample data."""
        if file_path.suffix == ".csv":
            content = """Name,Department,Email,Phone,Status
John Smith,Engineering,john.smith@company.com,555-0101,Active
Sarah Johnson,Marketing,sarah.johnson@company.com,555-0102,Active
Mike Brown,Sales,mike.brown@company.com,555-0103,Active
Lisa Davis,HR,lisa.davis@company.com,555-0104,Active
Tom Wilson,Finance,tom.wilson@company.com,555-0105,Active"""
        else:
            # For .xlsx, create a simple text representation
            content = f"""Spreadsheet: {filename.replace("_", " ").title()}
Date: 2025-09-10

This is a simplified representation of an Excel file.
Actual Excel files would require additional libraries.

Sample Data:
- Q1 Revenue: $125,000
- Q2 Revenue: $145,000  
- Q3 Revenue: $168,000
- Q4 Revenue: $192,000
Total: $630,000"""

        file_path.write_text(content, encoding="utf-8")

    @classmethod
    def _create_image_file(cls, file_path: Path, filename: str):
        """Create a simple text-based image placeholder."""
        content = f"""Image Placeholder: {filename.replace("_", " ").title()}
Type: {file_path.suffix.upper()[1:]} Image
Generated: 2025-09-10

This is a placeholder for an actual image file.
In a real implementation, this would contain binary image data.

Image Properties:
- Width: 1024px
- Height: 768px
- Format: {file_path.suffix.upper()[1:]}
- Size: ~500KB"""

        file_path.write_text(content, encoding="utf-8")

    @classmethod
    def _create_archive_file(cls, file_path: Path, filename: str):
        """Create a simple archive placeholder."""
        content = f"""Archive: {filename.replace("_", " ").title()}
Created: 2025-09-10

This is a placeholder for an archive file.
Contents would typically include:

- Configuration files
- Documentation
- Source code
- Assets
- Build artifacts

Archive Type: {file_path.suffix}
Compression: Standard
Files: 15-25 items"""

        file_path.write_text(content, encoding="utf-8")

    @classmethod
    def generate_file_for_message(cls) -> tuple[str, str]:
        """Generate a single file for a message attachment."""
        category, extension, mime_type = cls.select_file_type()
        filename = cls.generate_random_filename(category)
        file_path = cls.create_sample_file(category, extension, filename)

        return file_path, f"{filename}{extension}"

    @classmethod
    def cleanup_temp_files(cls):
        """Clean up temporary files."""
        temp_dir = Path(tempfile.gettempdir()) / "mattermost_files"
        if temp_dir.exists():
            for file in temp_dir.iterdir():
                with contextlib.suppress(Exception):
                    file.unlink()
            with contextlib.suppress(Exception):
                temp_dir.rmdir()
