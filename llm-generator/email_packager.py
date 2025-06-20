import json
import base64
import zipfile
import io
from typing import Dict, Any, List  # Added List to imports
from datetime import datetime
import uuid


class EmailPackager:
    def __init__(self):
        self.package_version = "1.0"

    async def create_package(
            self,
            request_id: str,
            generation_result: Dict[str, Any],
            metadata: Dict[str, Any],
            recipient: str
    ) -> Dict[str, Any]:
        """Create email package with generated code"""

        # Create ZIP archive with all files
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all generated files
            for filename, content in generation_result['files'].items():
                zip_file.writestr(filename, content)

            # Add metadata file
            package_metadata = {
                "package_version": self.package_version,
                "request_id": request_id,
                "generated_at": datetime.now().isoformat(),
                "recipient": recipient,
                "metadata": metadata,
                "generation_metadata": generation_result.get('metadata', {}),
                "files": list(generation_result['files'].keys()),
                "execution_instructions": self._generate_execution_instructions(
                    generation_result['metadata']
                )
            }

            zip_file.writestr('metadata.json', json.dumps(package_metadata, indent=2))

        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Encode ZIP as base64 for email attachment
        zip_base64 = base64.b64encode(zip_data).decode('utf-8')

        # Create email package
        email_package = {
            "recipient": recipient,
            "subject": f"Generated Application - {metadata.get('app_type', 'Application')} ({request_id[:8]})",
            "body": {
                "text": self._generate_text_body(package_metadata),
                "html": self._generate_html_body(package_metadata)
            },
            "attachments": [
                {
                    "filename": f"generated-app-{request_id[:8]}.zip",
                    "content": zip_base64,
                    "content_type": "application/zip",
                    "encoding": "base64"
                }
            ],
            "headers": {
                "X-Generated-By": "LLM-Email-Distribution",
                "X-Request-ID": request_id,
                "X-Package-Version": self.package_version
            }
        }

        return email_package

    def _generate_execution_instructions(self, metadata: Dict[str, Any]) -> List[str]:
        """Generate step-by-step execution instructions"""
        tech_stack = metadata.get('tech_stack', [])

        instructions = [
            "# Execution Instructions",
            "",
            "1. Extract the ZIP archive to your desired directory",
            "2. Navigate to the extracted directory",
            ""
        ]

        if 'python' in tech_stack:
            instructions.extend([
                "3. Install Python dependencies:",
                "   pip install -r requirements.txt",
                "",
                "4. Run the application:",
                "   python main.py",
                "",
                "5. Or use Docker:",
                "   docker build -t generated-app .",
                "   docker run -p 8080:8080 generated-app",
                ""
            ])
        elif 'node' in tech_stack or 'nodejs' in tech_stack:
            instructions.extend([
                "3. Install Node.js dependencies:",
                "   npm install",
                "",
                "4. Run the application:",
                "   npm start",
                "",
                "5. Or use Docker:",
                "   docker build -t generated-app .",
                "   docker run -p 8080:8080 generated-app",
                ""
            ])
        else:
            instructions.extend([
                "3. Follow the instructions in README.md",
                "4. Use Docker for easy deployment:",
                "   docker build -t generated-app .",
                "   docker run -p 8080:8080 generated-app",
                ""
            ])

        instructions.extend([
            "6. Access the application at http://localhost:8080",
            "",
            "For support and customizations, refer to the README.md file."
        ])

        return instructions

    def _generate_text_body(self, metadata: Dict[str, Any]) -> str:
        """Generate plain text email body"""
        return f"""
Generated Application Delivery

Hello,

Your requested application has been successfully generated and is attached to this email.

Application Details:
- Request ID: {metadata['request_id']}
- Generated: {metadata['generated_at']}
- Type: {metadata['metadata'].get('app_type', 'Application')}
- Files: {len(metadata['files'])} files included

Quick Start:
1. Download and extract the attached ZIP file
2. Follow the instructions in README.md
3. Use Docker for easy deployment: docker build -t app . && docker run -p 8080:8080 app

The application is ready to run and includes all necessary dependencies and configuration files.

---
Generated by LLM Email Distribution System
Request ID: {metadata['request_id']}
"""

    def _generate_html_body(self, metadata: Dict[str, Any]) -> str:
        """Generate HTML email body"""
        files_list = '</li><li>'.join(metadata['files'])
        instructions_html = '<br>'.join(metadata['execution_instructions'])

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Generated Application Delivery</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #007bff; color: white; padding: 15px; border-radius: 5px; }}
        .content {{ background: #f8f9fa; padding: 20px; margin: 15px 0; border-radius: 5px; }}
        .details {{ background: white; padding: 15px; border-left: 4px solid #007bff; }}
        .files {{ background: #e9ecef; padding: 10px; border-radius: 3px; }}
        .instructions {{ background: #d4edda; padding: 15px; border-radius: 5px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        code {{ background: #f1f3f4; padding: 2px 4px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Generated Application Delivery</h1>
            <p>Your custom application is ready!</p>
        </div>

        <div class="content">
            <div class="details">
                <h3>📋 Application Details</h3>
                <ul>
                    <li><strong>Request ID:</strong> {metadata['request_id']}</li>
                    <li><strong>Generated:</strong> {metadata['generated_at']}</li>
                    <li><strong>Type:</strong> {metadata['metadata'].get('app_type', 'Application')}</li>
                    <li><strong>Files Included:</strong> {len(metadata['files'])} files</li>
                </ul>
            </div>

            <div class="files">
                <h4>📁 Included Files:</h4>
                <ul><li>{files_list}</li></ul>
            </div>

            <div class="instructions">
                <h4>🏃‍♂️ Quick Start Instructions:</h4>
                <ol>
                    <li>Download and extract the attached ZIP file</li>
                    <li>Open terminal/command prompt in the extracted directory</li>
                    <li>Run: <code>docker build -t generated-app .</code></li>
                    <li>Run: <code>docker run -p 8080:8080 generated-app</code></li>
                    <li>Open <a href="http://localhost:8080">http://localhost:8080</a> in your browser</li>
                </ol>

                <p><strong>💡 Alternative:</strong> See README.md for local development setup.</p>
            </div>
        </div>

        <div class="footer">
            <p>Generated by LLM Email Distribution System</p>
            <p>Request ID: {metadata['request_id']}</p>
        </div>
    </div>
</body>
</html>
"""

