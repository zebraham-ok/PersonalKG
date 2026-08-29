"""
高德地图 Web 服务 API 封装
"""

import requests
import logging
from typing import Optional, List, Dict, Any

from .secret_manager import read_secrets_from_env

logger = logging.getLogger(__name__)

secret_dict = read_secrets_from_env()
GAODE_API_KEY = secret_dict.get("gaode_api_key", "")

BASE_URL = "https://restapi.amap.com/v5/place/around"


def around_search(
    location: str,
    keywords: Optional[str] = None,
    types: Optional[str] = None,
    radius: Optional[int] = None,
    sortrule: Optional[str] = None,
    region: Optional[str] = None,
    city_limit: Optional[str] = None,
    show_fields: Optional[str] = None,
    page_size: Optional[int] = None,
    page_num: Optional[int] = None,
    key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    高德地图周边搜索 API（v5）

    以指定坐标为中心，检索周边一定半径内的 POI 信息。

    参数:
        location (str):
            中心点坐标，格式 "经度,纬度"，小数点后不超过6位。必填。
            示例: "116.473168,39.993015"
        keywords (str):
            地点关键字，只支持一个关键字，总长度不超过80字符。可选。
        types (str):
            指定 POI 类型，多个类型用 "|" 分隔。
            当 keywords 和 types 均为空时，默认 types 为 "050000|070000|120000"。
            可选，参考 POI 分类码表。
        radius (int):
            搜索半径，单位米，范围 0-50000，默认 5000。可选。
        sortrule (str):
            排序规则："distance"（按距离）或 "weight"（综合排序）。
            默认 "distance"。注意：只传 keywords 时 distance 排序不生效。可选。
        region (str):
            搜索区划，可输入行政区划名、citycode 或 adcode。
            增加指定区域内数据召回权重，搭配 city_limit 使用。可选。
        city_limit (str):
            指定城市数据召回限制，"true" 或 "false"。默认 "false"。
            为 "true" 时仅召回 region 对应区域内数据。可选。
        show_fields (str):
            返回结果控制，多个字段用 "," 分隔。
            可选字段: children, business, indoor, navi, photos。
            未设置时只返回基础信息。可选。
        page_size (int):
            每页数据条数，取值 1-25，默认 10。可选。
        page_num (int):
            请求第几分页，默认 1。可选。
        key (str):
            高德 Web 服务 API Key。不传则自动从 .env 中读取。可选。

    返回:
        dict -- API 返回的完整 JSON 结果，包含 status, pois 等字段。失败返回 None。

    使用示例:
        >>> result = around_search(
        ...     location="116.473168,39.993015",
        ...     radius=10000,
        ...     types="011100",
        ... )
        >>> if result and result.get("status") == "1":
        ...     for poi in result.get("pois", []):
        ...         print(poi["name"], poi["distance"])
    """
    api_key = key or GAODE_API_KEY
    if not api_key:
        logger.error("高德 API Key 未配置，请在 .env 中设置 GAODE_API_KEY")
        return None

    if not location:
        logger.error("location 参数为必填项")
        return None

    # 构建请求参数
    params: Dict[str, Any] = {
        "key": api_key,
        "location": location,
    }

    if keywords is not None:
        params["keywords"] = keywords
    if types is not None:
        params["types"] = types
    if radius is not None:
        params["radius"] = radius
    if sortrule is not None:
        params["sortrule"] = sortrule
    if region is not None:
        params["region"] = region
    if city_limit is not None:
        params["city_limit"] = city_limit
    if show_fields is not None:
        params["show_fields"] = show_fields
    if page_size is not None:
        params["page_size"] = page_size
    if page_num is not None:
        params["page_num"] = page_num

    try:
        response = requests.get(url=BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get("status") == "1":
            logger.info(
                f"周边搜索成功: location={location}, "
                f"count={result.get('count', 0)}"
            )
        else:
            logger.warning(
                f"周边搜索失败: status={result.get('status')}, "
                f"info={result.get('info')}, infocode={result.get('infocode')}"
            )

        return result

    except requests.exceptions.HTTPError as e:
        logger.error(f"高德 API HTTP 错误 {e.response.status_code}: {e.response.text[:500]}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"高德 API 请求异常: {e}")
        return None
    except Exception as e:
        logger.error(f"高德 API 未知错误: {e}")
        return None


def around_search_all_pages(
    location: str,
    keywords: Optional[str] = None,
    types: Optional[str] = None,
    radius: Optional[int] = None,
    sortrule: Optional[str] = None,
    region: Optional[str] = None,
    city_limit: Optional[str] = None,
    show_fields: Optional[str] = None,
    page_size: int = 25,
    max_pages: int = 10,
    key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    周边搜索自动翻页，获取全部结果

    参数与 around_search 相同，额外参数:
        page_size (int): 每页条数，默认 25（最大值）
        max_pages (int): 最多翻页数，防止无限请求，默认 10

    返回:
        list[dict] -- 所有页面的 POI 列表（已合并）
    """
    all_pois: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        result = around_search(
            location=location,
            keywords=keywords,
            types=types,
            radius=radius,
            sortrule=sortrule,
            region=region,
            city_limit=city_limit,
            show_fields=show_fields,
            page_size=page_size,
            page_num=page,
            key=key,
        )

        if result is None or result.get("status") != "1":
            break

        pois = result.get("pois", [])
        if not pois:
            break

        all_pois.extend(pois)

        # 判断是否还有下一页
        count = int(result.get("count", 0))
        if page * page_size >= count:
            break

    logger.info(f"周边搜索完成: 共获取 {len(all_pois)} 条 POI")
    return all_pois


if __name__ == "__main__":
    # 测试示例：搜索北京朝阳大悦城周边 10km 内的火车站
    result = around_search(
        location="116.473168,39.993015",
        radius=10000,
        types="011100",
    )

    if result:
        print(f"状态: {result.get('status')}")
        print(f"信息: {result.get('info')}")
        print(f"结果数: {result.get('count')}")
        print("-" * 50)
        for poi in result.get("pois", []):
            print(
                f"名称: {poi.get('name')}, "
                f"距离: {poi.get('distance')}m, "
                f"地址: {poi.get('address')}"
            )
