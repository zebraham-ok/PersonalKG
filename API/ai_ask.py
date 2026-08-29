"""存储了多种封装好的大语言模型
对多重括号的处理也放在了这里
"""

from http import HTTPStatus
from typing import Optional
import re
import json
from json_repair import repair_json
from .secret_manager import read_secrets_from_env
import requests
import os
import openai
import logging

# 禁用 httpx 的 INFO 级别日志，要在WARNING级别以上才会打印出来
logging.getLogger("httpx").setLevel(logging.WARNING)

secret_dict = read_secrets_from_env()
# print(secret_dict)
openai_key = secret_dict["openai"]
# gemini_key=secret_dict["gemini_cost1"]
# gemini_free_key=secret_dict["gemini_free2"]
general_key = secret_dict["general"]
moma_api_key = secret_dict.get("moma_api_key", "")
moma_base_url = secret_dict.get("moma_base_url", "http://zhenze-huhehaote.cmecloud.cn")
# metaso_key=secret_dict["metaso_key"]

qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" 
qwen_client=openai.OpenAI(base_url=qwen_base_url,api_key=secret_dict["qwen"],timeout=60)

# Qwen Vision 客户端（使用 QWEN_VISON API Key）
qwen_vision_api_key = secret_dict.get("qwen_vision", "")
qwen_vision_client = openai.OpenAI(
    base_url=qwen_base_url,
    api_key=qwen_vision_api_key,
    timeout=60
)  

from openai import OpenAI
import os

def get_qwen_embedding(
    text: str,
    model: str = "text-embedding-v3",
    dimensions: int = 512
) -> list:
    """
    获取通义千问的文本嵌入向量
    
    参数:
    text -- 需要编码的文本内容（必填）
    model -- 模型名称（默认text-embedding-v3）
    dimensions -- 向量维度（默认1024，可选512/1024/1536）
    encoding_format -- 编码格式（默认float）
    
    返回:
    list -- 文本嵌入向量
    """
    # 长度限制
    if len(text)<1 or len(text)>8191:
        return []
    
    try:
        response = qwen_client.embeddings.create(
            model=model,
            input=text,
            dimensions=dimensions,
            encoding_format="float"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None
    
def ask_qwen_with_gpt_backup(prompt_text,history=[],system_instruction="",model="qwen-turbo",mode="str",temperature=0, enable_search=False, enable_citaton=False, retry_model="gpt-4o"):
    "优先使用Qwen，如果没有返回结果就问OpenAI"
    qwen_result=ask_qwen(prompt_text, history, system_instruction, model, mode, temperature, enable_search, enable_citaton)
    if qwen_result:
        return qwen_result
    else:
        gpt_result=ask_gpt(prompt_text=prompt_text, history=history, system_instruction=system_instruction, model=retry_model, mode="json", temperature=temperature)
        if gpt_result:
            print(f"Retried successful with {retry_model}")
            return gpt_result

def ask_qwen(prompt_text,history=[],system_instruction="",model="qwen-turbo",mode="str",temperature=0, enable_search=False, enable_citaton=False):
    "直接返回字符串"
    if mode=="json":
        response_format={ "type": "json_object" }
    else:
        response_format=None
    message=[{"role": "system", "content": system_instruction}]    # 角色包含system、user和assistant三种
    for d in history:  # 把通义千问的历史格式转化为GPT的历史格式
        message.append({"role":"user","content":d["user"]})
        message.append({"role":"assistant","content":d["bot"]})
    message.append({"role":"user","content":prompt_text})
    try:
        completion = qwen_client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format=response_format,
            messages=message,
            extra_body={
                "enable_search": enable_search,
                "search_options": {
                    "enable_source": True,
                    "enable_citation": enable_citaton,
                    "citation_format": "[<number>]",
                    "forced_search": False
                    }
                }
            )
        # print(completion)
        if completion.choices:
            return completion.choices[0].message.content
        else:
            print("Qwen no reply")
    except Exception as e:
        print(f"Qwen error {e}")

def _build_chat_messages(prompt_text, history, system_instruction):
    """构造 OpenAI 兼容的 messages（system + 成对历史 + 当前问题）"""
    message = [{"role": "system", "content": system_instruction}]
    for d in history:  # 把通义千问的历史格式转化为GPT的历史格式
        message.append({"role": "user", "content": d["user"]})
        message.append({"role": "assistant", "content": d["bot"]})
    message.append({"role": "user", "content": prompt_text})
    return message


def ask_qwen_stream(prompt_text, history=[], system_instruction="", model="qwen-turbo",
                    temperature: float = 0, enable_search=False, enable_citaton=False):
    """Qwen 流式输出：生成器，逐块 yield 文本内容（SSE 由上层负责包装）"""
    message = _build_chat_messages(prompt_text, history, system_instruction)
    try:
        completion = qwen_client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=message,
            stream=True,
            extra_body={
                "enable_search": enable_search,
                "search_options": {
                    "enable_source": True,
                    "enable_citation": enable_citaton,
                    "citation_format": "[<number>]",
                    "forced_search": False,
                }
            }
        )
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        print(f"Qwen stream error {e}")
        raise


def ask_gpt_stream(prompt_text, history=[], system_instruction="", model="gpt-4o-mini", temperature: float = 0):
    """GPT 流式输出：生成器，逐块 yield 文本内容"""
    message = _build_chat_messages(prompt_text, history, system_instruction)
    try:
        completion = gpt_client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=message,
            stream=True,
        )
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        print(f"GPT stream error {e}")
        raise


def ask_qwen_with_gpt_backup_stream(prompt_text, history=[], system_instruction="", model="qwen-turbo",
                                    temperature: float = 0, enable_search=False, enable_citaton=False,
                                    retry_model="gpt-4o"):
    """优先 Qwen 流式；若在首个文本块之前失败（限流/超时等），回退 GPT 流式。"""
    qwen = None
    try:
        qwen = ask_qwen_stream(prompt_text, history, system_instruction, model,
                               temperature, enable_search, enable_citaton)
        first = next(qwen)  # 首个块之前抛异常才允许回退
        yield first
        yield from qwen
    except StopIteration:
        pass
    except Exception as e:
        print(f"Qwen stream failed before first chunk, fallback to {retry_model}: {e}")
        try:
            gpt = ask_gpt_stream(prompt_text, history, system_instruction, retry_model, temperature)
            yield from gpt
        except Exception as e2:
            print(f"GPT stream error too: {e2}")
            raise


# YunWu（云雾/OpenLux）客户端：OpenAI 兼容接口，交互方式与 Qwen（DashScope 兼容模式）一致
gpt_client = openai.OpenAI(base_url="https://api.openlux.ai/v1", api_key=general_key, timeout=60)
yunwu_client = gpt_client  # 同一服务，不同别名


def ask_yunwu_stream(prompt_text, history=[], system_instruction="", model="gpt-4o", temperature: float = 0):
    """YunWu（OpenLux）流式输出：OpenAI 兼容接口，生成器逐块 yield 文本内容（SSE 由上层包装）"""
    message = _build_chat_messages(prompt_text, history, system_instruction)
    try:
        completion = yunwu_client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=message,
            stream=True,
        )
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        print(f"YunWu stream error {e}")
        raise


def ask_gpt(prompt_text,history=[],system_instruction="",model="gpt-4o-mini",mode="json",temperature=0):
    if mode=="json":
        response_format={ "type": "json_object" }
    else:
        response_format=None
    message=[{"role": "system", "content": system_instruction}]    # 角色包含system、user和assistant三种
    for d in history:  # 把通义千问的历史格式转化为GPT的历史格式
        message.append({"role":"user","content":d["user"]})
        message.append({"role":"assistant","content":d["bot"]})
    message.append({"role":"user","content":prompt_text})
    try:
        completion = gpt_client.chat.completions.create(
            model=model,
            # model='gpt-4-1106-preview',
            temperature=temperature,
            response_format=response_format,
            messages=message)
        # print(completion)
        if completion.choices:
            return completion.choices[0].message.content
        else:
            print("GPT no reply")
    except Exception as e:
        print(f"gpt error {e}")
        
import base64
import mimetypes


def _encode_image_to_base64(image_path: str) -> str:
    """将本地图片编码为base64 data URL"""
    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type is None:
        mime_type = "image/jpeg"
    with open(image_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64_data}"


def ask_moma(
    prompt_text: str = "这张图里有什么内容?",
    image_url: Optional[str] = None,
    image_path: Optional[str] = None,
    model: str = "qwen2.5-vl-72b-instruct",
    system_instruction: str = "",
    temperature: float = 0,
    stream: bool = False,
    timeout: int = 60,
) -> Optional[str]:
    """
    MoMA 多模态模型调用，支持图片理解与对话。

    参数:
        prompt_text -- 图文对话的文本提示词
        image_url -- 图片的http/https链接（与image_path二选一）
        image_path -- 本地图片文件路径（与image_url二选一）
        model -- 模型名称，默认 Qwen2-VL-7B-Instruct
        system_instruction -- 系统提示词
        temperature -- 生成温度
        stream -- 是否流式输出
        timeout -- 请求超时秒数

    返回:
        str -- 模型返回的文本内容，失败返回None
    """
    if not image_url and not image_path:
        print("MoMA error: 必须提供 image_url 或 image_path")
        return None
    if image_url and image_path:
        print("MoMA error: image_url 和 image_path 不能同时提供")
        return None

    # 确定图片内容的格式
    if image_path:
        image_content = {
            "type": "image_url",
            "image_url": {"url": _encode_image_to_base64(image_path)}
        }
    else:
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_url}
        }

    api_url = f"{moma_base_url.rstrip('/')}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {moma_api_key}",
        "Content-Type": "application/json",
    }

    # 构建 messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    messages.append({
        "role": "user",
        "content": [
            image_content,
            {"type": "text", "text": prompt_text},
        ]
    })

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }

    try:
        response = requests.post(
            url=api_url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("choices"):
            return result["choices"][0].get("message", {}).get("content")
        else:
            print(f"MoMA no reply, raw response: {json.dumps(result, ensure_ascii=False)[:500]}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"MoMA HTTP error {e.response.status_code}: {e.response.text[:500]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"MoMA request error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"MoMA JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"MoMA unexpected error: {e}")
        return None


def ask_qwen_vision(
    prompt_text: str = "这张图里有什么内容?",
    image_url: Optional[str] = None,
    image_path: Optional[str] = None,
    model: str = "qwen3.6-plus",
    system_instruction: str = "",
    temperature: float = 0,
    stream: bool = False,
    timeout: int = 60,
) -> Optional[str]:
    """
    通义千问多模态模型调用（Qwen Vision），支持图片理解与对话。

    参数:
        prompt_text -- 图文对话的文本提示词
        image_url -- 图片的http/https链接（与image_path二选一）
        image_path -- 本地图片文件路径（与image_url二选一）
        model -- 模型名称，默认 qwen3.6-plus
        system_instruction -- 系统提示词
        temperature -- 生成温度
        stream -- 是否流式输出
        timeout -- 请求超时秒数

    返回:
        str -- 模型返回的文本内容，失败返回None
    """
    if not image_url and not image_path:
        print("Qwen Vision error: 必须提供 image_url 或 image_path")
        return None
    if image_url and image_path:
        print("Qwen Vision error: image_url 和 image_path 不能同时提供")
        return None

    # 确定图片内容的格式
    if image_path:
        image_content = {
            "type": "image_url",
            "image_url": {"url": _encode_image_to_base64(image_path)}
        }
    else:
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_url}
        }

    # 构建 messages
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    messages.append({
        "role": "user",
        "content": [
            image_content,
            {"type": "text", "text": prompt_text},
        ]
    })

    try:
        completion = qwen_vision_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            extra_body={"enable_thinking": True},
            stream=stream,
            timeout=timeout,
        )

        if stream:
            # 流式输出：收集所有 chunk
            full_content = ""
            is_answering = False
            for chunk in completion:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    if not is_answering:
                        pass  # 思考过程不存入返回值
                if hasattr(delta, "content") and delta.content:
                    if not is_answering:
                        is_answering = True
                    full_content += delta.content
            return full_content if full_content else None
        else:
            if completion.choices:
                return completion.choices[0].message.content
            else:
                print("Qwen Vision no reply")
                return None

    except Exception as e:
        print(f"Qwen Vision error: {e}")
        return None


def mitaso_upload_file(cfid, file_path, api_key):
    """
    上传文件到指定的目录ID下。

    参数:
    - dir_id (str): 目录ID是文件要被上传到的在线路径，可以通过打开专题知识库的链接查看，如https://metaso.cn/subject/8580814774167015424/manage?cfid=8580815096909144064中，一个是专题，一个是目录cfid
    - file_path (str)：是文件的本地路径
    - api_key (str): 用户的API密钥。
    
    返回:
    - str: 服务器响应文本。
    """
    # 构建请求URL
    url = f"https://metaso.cn/api/open/file/{cfid}"
    
    # 设置请求头
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    # 获取文件名和类型
    file_name = file_path.split('/')[-1]
    file_type, _ = mimetypes.guess_type(file_name)
    
    # 打开并读取文件
    with open(file_path, "rb") as file:
        # 发送PUT请求上传文件
        response = requests.put(url, files={"file": (file_name, file, file_type)}, headers=headers)
        
    return response.text


def find_outer_braces(s): 
    "获取一个字符串中所有的最外层大括号（避免因为没生成完导致缺少反括号]的错误），并直接将他们转化为字典，以(list[dict], list[str])形式返回"
    stack = []
    result = []
    start = None

    for i, char in enumerate(s):
        if char == '{':
            if not stack:
                start = i  # 记录最外层 '{' 的位置
            stack.append(i)
        elif char == '}':
            if stack:
                stack.pop()
                if not stack:
                    result.append(s[start:i+1])  # 记录最外层括号的内容
                    
    list_of_dict = []
    for i in result:
        if isinstance(i, str):
            try:
                list_of_dict.append(json.loads(i))
            except Exception as e:
                print(f"cannot conver {i} to json because {e}")
    return list_of_dict, result


def find_outer_brackets(s):
    """
    获取一个字符串中所有的最外层方括号（避免因为没生成完导致缺少反括号]的错误），
    并直接将他们转化为列表，以(tuple[list, list[str]])形式返回
    """
    stack = []
    result = []
    start = None

    for i, char in enumerate(s):
        if char == '[':
            if not stack:
                start = i  # 记录最外层 '[' 的位置
            stack.append(i)
        elif char == ']':
            if stack:
                stack.pop()
                if not stack:
                    result.append(s[start:i+1])  # 记录最外层括号的内容
                    
    list_of_lists = []
    for i in result:
        if isinstance(i, str):
            try:
                list_of_lists.append(json.loads(i))
            except Exception as e:
                print(f"cannot convert {i} to list because {e}")
    return list_of_lists, result

def extract_json_from_answer(answer: str, expected_keys: list = None) -> dict:
    """
    从回答中提取 JSON，兼容多种格式
    
    参数:
    - answer: 大语言模型返回的回答文本
    - expected_keys: 期望在 JSON 中找到的键列表，用于验证提取结果
    
    返回:
    - dict: 提取的 JSON 数据
    """
    if not answer or not isinstance(answer, str):
        return {}
    
    # 快速路径：如果整体就是 JSON，直接尝试解析
    if answer.strip().startswith('{') and answer.strip().endswith('}') or answer.strip().startswith('[') and answer.strip().endswith(']'):
        try:
            data = json.loads(answer.strip())
            if expected_keys:
                if all(k in data for k in expected_keys):
                    return data
            elif "source" in data or "analysis" in data or "final_answer" in data:
                return data
            elif data:
                return data
        except json.JSONDecodeError:
            pass
    
    # 方法1：尝试查找 ```json 代码块
    json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', answer)
    
    if json_blocks:
        for block in reversed(json_blocks):
            try:
                data = json.loads(block.strip())
                if expected_keys:
                    if all(k in data for k in expected_keys):
                        return data
                elif "source" in data or "analysis" in data or "final_answer" in data:
                    return data
                elif data:
                    return data
            except json.JSONDecodeError:
                try:
                    fixed = repair_json(block.strip())
                    data = json.loads(fixed)
                    if expected_keys:
                        if all(k in data for k in expected_keys):
                            return data
                    elif "source" in data or "analysis" in data or "final_answer" in data:
                        return data
                    elif data:
                        return data
                except:
                    continue
    
    # 方法2：直接在整个回答中查找 JSON 对象
    if expected_keys:
        # 如果有期望的键，优先查找包含这些键的 JSON
        for key in expected_keys:
            pattern = r'\{[\s\S]*"' + key + r'"[\s\S]*\}'
            json_matches = re.findall(pattern, answer)
            for match in json_matches:
                try:
                    data = json.loads(match)
                    if all(k in data for k in expected_keys):
                        return data
                except json.JSONDecodeError:
                    try:
                        fixed = repair_json(match)
                        data = json.loads(fixed)
                        if all(k in data for k in expected_keys):
                            return data
                    except:
                        continue
    
    # 方法3：让 find_outer_brackets 和 find_outer_braces 竞争，谁找到的字符串更长
    # 就用谁的解析结果
    _, braces_raw = find_outer_braces(answer)
    _, brackets_raw = find_outer_brackets(answer)
    
    # 比较所有找到的字符串，选择最长的
    all_raw = braces_raw + brackets_raw
    if all_raw:
        longest_raw = max(all_raw, key=len)
        
        # 尝试解析为 JSON
        try:
            data = json.loads(longest_raw)
            if expected_keys:
                if all(k in data for k in expected_keys):
                    return data
            elif data:
                return data
        except json.JSONDecodeError:
            pass
        
        # 如果是列表格式
        if longest_raw.strip().startswith('[') and longest_raw.strip().endswith(']'):
            try:
                parsed = json.loads(longest_raw)
                if isinstance(parsed, list):
                    return parsed
            except:
                pass
    
    return {}

def solve_nested_quotes(text):
    "这段代码可以解决嵌套双引号导致无法将gemini生成的字符串转化为字典的问题"
    # 匹配嵌套双引号的部分
    match = re.search(r'(?<=: ")([^"]*\"[^"]*\"[^"]*)(?=",\n|"\n|", \n)', text)
    # print(match)
    if match:
        sub_matched_str = re.sub(r'\"', "'", match.group())
        new_text = text.replace(match.group(), sub_matched_str)
        return new_text
    else:
        return text

if __name__=="__main__":  # 报告可用的gemini版本
    # for m in genai.list_models():
    #     if 'generateContent' in m.supported_generation_methods:
    #         print(m.name)
    response=ask_gpt("宇宙的尽头有什么",mode="str")
    print(response)
 