import os

from dotenv import load_dotenv

load_dotenv()


class Secrets:
    INFISICAL_CLIENT_ID = os.environ.get("INFISICAL_CLIENT_ID", "")
    INFISICAL_CLIENT_TOKEN = os.environ.get("INFISICAL_CLIENT_TOKEN", "")
    INFISICAL_PROJECT_ID = os.environ.get("INFISICAL_PROJECT_ID", "")


class Environment:
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
