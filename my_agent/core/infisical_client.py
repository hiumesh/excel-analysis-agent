from infisical_sdk import InfisicalSDKClient
import asyncio
import os

from my_agent.core.execution_var import Environment, Secrets
from my_agent.core.logging_config import setup_logging

logger = setup_logging()


def get_infisical_client():
    try:
        client = InfisicalSDKClient(
            host="https://app.infisical.com"
        )  # host defaults to cloud
        client.auth.universal_auth.login(
            Secrets.INFISICAL_CLIENT_ID,
            Secrets.INFISICAL_CLIENT_TOKEN,
        )
        return client
    except Exception as e:
        logger.error("Error in Connecting to Infisical!", error=e)
        raise


def get_secret(secret_name):
    env_val = os.environ.get(secret_name)
    if env_val:
        return env_val

    try:
        client = get_infisical_client()
        secret = client.secrets.get_secret_by_name(
            secret_name=secret_name,
            project_id=Secrets.INFISICAL_PROJECT_ID,
            environment_slug=Environment.ENVIRONMENT,
            secret_path="/",
        ).secretValue
        return secret
    except Exception as e:
        logger.error("Retrieving Secret failed", secret_name=secret_name, error=e)

async def aget_secret(secret_name):
    return await asyncio.to_thread(get_secret, secret_name)
