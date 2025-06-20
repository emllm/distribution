import json
import os
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader
from llm_providers import LLMProvider


class CodeGenerator:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.template_env = Environment(loader=FileSystemLoader('/app/templates'))

    async def generate_application(
            self,
            app_type: str,
            description: str,
            requirements: List[str],
            tech_stack: List[str],
            features: List[str]
    ) -> Dict[str, Any]:
        """Generate complete application based on requirements"""

        # Create structured prompt
        prompt = self._create_generation_prompt(
            app_type, description, requirements, tech_stack, features
        )

        # Generate code using LLM
        llm_response = await self.llm_provider.generate_code(prompt)

        if not llm_response['success']:
            return llm_response

        # Parse LLM response and structure files
        try:
            generated_content = self._parse_llm_response(llm_response['content'])

            # Add standard files (Dockerfile, requirements, etc.)
            structured_files = await self._add_standard_files(
                generated_content, tech_stack, requirements
            )

            return {
                "success": True,
                "files": structured_files,
                "metadata": {
                    "app_type": app_type,
                    "tech_stack": tech_stack,
                    "features": features,
                    "llm_model": llm_response.get('model'),
                    "usage": llm_response.get('usage')
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse LLM response: {str(e)}"
            }

    def _create_generation_prompt(
            self,
            app_type: str,
            description: str,
            requirements: List[str],
            tech_stack: List[str],
            features: List[str]
    ) -> str:
        """Create structured prompt for LLM"""

        prompt_template = self.template_env.get_template('generation_prompt.jinja2')

        return prompt_template.render(
            app_type=app_type,
            description=description,
            requirements=requirements,
            tech_stack=tech_stack,
            features=features
        )

    def _parse_llm_response(self, content: str) -> Dict[str, str]:
        """Parse LLM response into structured files"""
        files = {}

        # Try to extract JSON if present
        try:
            if '```json' in content:
                json_start = content.find('```json') + 7
                json_end = content.find('```', json_start)
                json_content = content[json_start:json_end].strip()
                parsed_json = json.loads(json_content)

                if 'files' in parsed_json:
                    return parsed_json['files']
        except:
            pass

        # Fallback: parse code blocks
        import re

        # Find all code blocks with filenames
        pattern = r'```(\w+)?\s*#?\s*([^\n]+\.[\w]+)?\s*\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)

        for lang, filename, code in matches:
            if filename:
                files[filename.strip()] = code.strip()
            elif lang == 'python':
                files['main.py'] = code.strip()
            elif lang == 'dockerfile':
                files['Dockerfile'] = code.strip()
            elif lang == 'yaml' or lang == 'yml':
                files['docker-compose.yml'] = code.strip()

        # If no structured files found, create basic structure
        if not files:
            files['main.py'] = content.strip()

        return files

    async def _add_standard_files(
            self,
            generated_files: Dict[str, str],
            tech_stack: List[str],
            requirements: List[str]
    ) -> Dict[str, str]:
        """Add standard files like Dockerfile, requirements.txt"""

        files = generated_files.copy()

        # Add Dockerfile if not present
        if 'Dockerfile' not in files:
            if 'python' in tech_stack:
                files['Dockerfile'] = self._generate_python_dockerfile()
            elif 'node' in tech_stack or 'nodejs' in tech_stack:
                files['Dockerfile'] = self._generate_node_dockerfile()

        # Add requirements.txt for Python projects
        if 'python' in tech_stack and 'requirements.txt' not in files:
            files['requirements.txt'] = self._generate_requirements_txt(requirements)

        # Add package.json for Node projects
        if ('node' in tech_stack or 'nodejs' in tech_stack) and 'package.json' not in files:
            files['package.json'] = self._generate_package_json(requirements)

        # Add README.md
        if 'README.md' not in files:
            files['README.md'] = self._generate_readme(tech_stack)

        # Add .gitignore
        if '.gitignore' not in files:
            files['.gitignore'] = self._generate_gitignore(tech_stack)

        return files

    def _generate_python_dockerfile(self) -> str:
        return """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]"""

    def _generate_node_dockerfile(self) -> str:
        return """FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 8080

CMD ["npm", "start"]"""

    def _generate_requirements_txt(self, requirements: List[str]) -> str:
        base_requirements = [
            "fastapi==0.104.1",
            "uvicorn[standard]==0.24.0",
            "pydantic==2.5.0"
        ]

        all_requirements = base_requirements + requirements
        return '\n'.join(sorted(set(all_requirements)))

    def _generate_package_json(self, requirements: List[str]) -> str:
        dependencies = {
            "express": "^4.18.0",
            "cors": "^2.8.5"
        }

        # Add custom requirements
        for req in requirements:
            if ':' in req:
                name, version = req.split(':', 1)
                dependencies[name] = f"^{version}"
            else:
                dependencies[req] = "latest"

        package_json = {
            "name": "generated-app",
            "version": "1.0.0",
            "description": "Generated application",
            "main": "main.js",
            "scripts": {
                "start": "node main.js",
                "dev": "nodemon main.js"
            },
            "dependencies": dependencies
        }

        return json.dumps(package_json, indent=2)

    def _generate_readme(self, tech_stack: List[str]) -> str:
        return f"""# Generated Application

This application was automatically generated using LLM Email Distribution system.

## Technology Stack
{chr(10).join(f'- {tech}' for tech in tech_stack)}

## Quick Start

### Using Docker
```bash
docker build -t generated-app .
docker run -p 8080:8080 generated-app
```

### Local Development
1. Install dependencies
2. Run the application
3. Access at http://localhost:8080

## Generated Files
- Application source code
- Dockerfile for containerization
- Configuration files
- Documentation

## Support
This application was generated automatically. For customizations, 
modify the source code as needed for your specific requirements.
"""

    def _generate_gitignore(self, tech_stack: List[str]) -> str:
        gitignore_content = [
            "# General",
            "*.log",
            "*.tmp",
            ".env",
            ".DS_Store",
            ""
        ]

        if 'python' in tech_stack:
            gitignore_content.extend([
                "# Python",
                "__pycache__/",
                "*.pyc",
                "*.pyo",
                "*.pyd",
                ".Python",
                "venv/",
                "env/",
                ".venv/",
                ""
            ])

        if 'node' in tech_stack or 'nodejs' in tech_stack:
            gitignore_content.extend([
                "# Node.js",
                "node_modules/",
                "npm-debug.log*",
                "yarn-debug.log*",
                "yarn-error.log*",
                ""
            ])

        gitignore_content.extend([
            "# Docker",
            "*.tar",
            "*.tar.gz"
        ])

        return '\n'.join(gitignore_content)


