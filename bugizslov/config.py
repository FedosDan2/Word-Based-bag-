from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    llm_api_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    database_path: Path
    max_input_length: int
    max_question_rounds: int
    session_ttl_days: int
    user_requests_per_hour: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            llm_api_base_url=os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            database_path=Path(os.getenv("DATABASE_PATH", "data/bugizslov.sqlite3")),
            max_input_length=int(os.getenv("MAX_INPUT_LENGTH", "4000")),
            max_question_rounds=int(os.getenv("MAX_QUESTION_ROUNDS", "5")),
            session_ttl_days=int(os.getenv("SESSION_TTL_DAYS", "14")),
            user_requests_per_hour=int(os.getenv("USER_REQUESTS_PER_HOUR", "30")),
        )

    def validate(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.llm_api_key:
            missing.append("LLM_API_KEY")
        if missing:
            raise RuntimeError("Заполните обязательные настройки: " + ", ".join(missing))
        if self.llm_timeout_seconds <= 0 or self.max_question_rounds < 1:
            raise RuntimeError("Проверьте LLM_TIMEOUT_SECONDS и MAX_QUESTION_ROUNDS")
