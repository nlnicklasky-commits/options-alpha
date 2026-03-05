from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/options_alpha"
    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    thetadata_username: str = ""
    thetadata_password: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
