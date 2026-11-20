import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    docker_sandbox_image: str = os.getenv("DOCKER_SANDBOX_IMAGE", "autopatch-sandbox:latest")
    sandbox_timeout_seconds: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "30"))
    reports_dir: str = os.getenv("REPORTS_DIR", "./reports")
    demo_projects_dir: str = os.getenv("DEMO_PROJECTS_DIR", "../demo_projects")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
