from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    google_service_account_key_path: str = "./service-account-key.json"
    google_sheet_id: str = ""
    airtable_api_key: str = ""
    airtable_base_id: str = ""
    airtable_table_name: str = "Call Logs"
    vapi_private_key: str = ""
    vapi_public_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()