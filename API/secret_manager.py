import csv
import os
from typing import Optional
from dotenv import load_dotenv


def read_secrets_from_csv(filename: str) -> dict:
    secrets = {}
    
    try:
        with open(filename, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                id = row['id']
                secret_key = row['secret_key']
                secrets[id] = secret_key
                
    except FileNotFoundError:
        print(f"Error: The file {filename} does not exist.")
    except KeyError as e:
        print(f"Error: Missing column in CSV: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return secrets


def read_secrets_from_env(env_path: Optional[str] = None) -> dict:
    """
    从 .env 文件中加载密钥，返回字典，key 为小写形式。
    
    参数:
    env_path -- .env 文件路径，默认为项目根目录下的 .env
    """
    if env_path is None:
        # 默认为项目根目录下的 .env
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(current_dir, ".env")
    
    load_dotenv(env_path, override=True)
    
    # 读取 .env 文件，构建与原 CSV 格式兼容的 secret_dict
    # 将 KEY=VALUE 转为 {"key": "VALUE"} 格式（key 小写，与原 CSV id 列对应）
    secrets = {}
    
    env_mapping = {
        "QWEN_KEY": "qwen",
        "QWEN1_KEY": "qwen1",
        "BAIDU_KEY": "baidu",
        "OPENAI_KEY": "openai",
        "CLAUDE_KEY": "claude",
        "GENERAL_KEY": "general",
        "MOMA_API_KEY": "moma_api_key",
        "MOMA_BASE_URL": "moma_base_url",
        "SQL_HOST": "sql_host",
        "SQL_PORT": "sql_port",
        "SQL_SECRET": "sql_secret",
        "SQL_USER": "sql_user",
        "LIANG_GOOGLE_KEY": "liang_google",
        "LOCAL_NEO4J_URL": "local_neo4j_url",
        "LOCAL_NEO4J_USERNAME": "local_neo4j_username",
        "LOCAL_NEO4J_PASSWORD": "local_neo4j_password",
        "REMOTE_NEO4J_URL": "remote_neo4j_url",
        "REMOTE_NEO4J_USERNAME": "remote_neo4j_username",
        "REMOTE_NEO4J_PASSWORD": "remote_neo4j_password",
        "ALI_NEO4J_URL": "ali_neo4j_url",
        "ALI_NEO4J_USERNAME": "ali_neo4j_username",
        "ALI_NEO4J_PASSWORD": "ali_neo4j_password",
        "MONGO_DB": "mongo_db",
        "MONGO_URL": "mongo_url",
        "GAODE_API_KEY": "gaode_api_key",
        "QWEN_VISON": "qwen_vision",
    }
    
    for env_key, secret_key in env_mapping.items():
        value = os.getenv(env_key)
        if value:
            secrets[secret_key] = value
    
    return secrets

