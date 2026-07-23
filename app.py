from __future__ import annotations

import gzip
import json
import os
import random
import re
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
HOME_CATALOG_PATH = STATIC_DIR / "data" / "home-products.json"
SCENARIO_CATALOG_PATH = STATIC_DIR / "data" / "scenario-products.json"
EXAMPLE_CATALOG_PATH = STATIC_DIR / "data" / "example-products.json"
CATEGORY_INTENT_SYSTEM_PROMPT_PATH = ROOT / "prompts" / "category_intent_system.txt"
CATEGORY_INTENT_SYSTEM_PROMPT = CATEGORY_INTENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
_WHALE_CONFIG_LOCK = threading.Lock()
_WHALE_CONFIG_SIGNATURE: tuple[str, str] | None = None
_HOME_CATALOG_GZIP: bytes | None = None


def load_local_env(path: Path) -> None:
    """Load simple KEY=VALUE entries without adding a runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_local_env(ROOT / ".env")
PORT = int(os.environ.get("PORT", "8000"))


def product(
    product_id: str,
    title: str,
    category: str,
    price: int,
    image: str,
    *,
    attributes: list[str],
    base_score: int,
    sales: str,
    novelty: int = 0,
    brand: str = "通用",
    origin: str = "国产",
    audiences: list[str] | None = None,
    styles: list[str] | None = None,
    goals: list[str] | None = None,
    trend: int = 0,
) -> dict[str, Any]:
    return {
        "id": product_id,
        "title": title,
        "category": category,
        "price": price,
        "image": image if image.startswith(("http://", "https://")) else f"/assets/{image}.svg",
        "attributes": attributes,
        "baseScore": base_score,
        "sales": sales,
        "novelty": novelty,
        "brand": brand,
        "origin": origin,
        "audiences": audiences or [],
        "styles": styles or [],
        "goals": goals or [],
        "trend": trend,
    }


PRODUCTS = [
    product("run-01", "Nike 轻云缓震男士跑鞋 透气回弹", "跑鞋", 399, "run-shoe", attributes=["男款", "白色", "运动鞋", "缓震", "轻量"], base_score=99, sales="2万+人付款", brand="耐克", origin="进口", audiences=["学生", "新手", "男朋友"], styles=["运动风"], trend=9),
    product("run-02", "城市疾风竞速跑鞋 碳板推进", "跑鞋", 699, "run-shoe", attributes=["男款", "黑色", "运动鞋", "碳板"], base_score=97, sales="8000+人付款"),
    product("run-03", "日常慢跑厚底运动鞋", "跑鞋", 269, "run-shoe", attributes=["男款", "白色", "运动鞋", "厚底"], base_score=96, sales="5万+人付款"),
    product("run-04", "专业支撑跑步鞋 稳定保护", "跑鞋", 459, "run-shoe", attributes=["男款", "灰色", "运动鞋", "支撑"], base_score=94, sales="1万+人付款"),
    product("shoe-01", "小白鞋男款 隐形增高 5cm", "休闲鞋", 329, "white-shoe", attributes=["男款", "白色", "运动鞋", "增高", "厚底"], base_score=92, sales="3万+人付款"),
    product("shoe-02", "复古德训鞋男 百搭白色", "休闲鞋", 289, "white-shoe", attributes=["男款", "白色", "运动鞋", "复古"], base_score=90, sales="1万+人付款"),
    product("shoe-03", "轻量厚底休闲运动鞋 增高", "休闲鞋", 459, "white-shoe", attributes=["男款", "白色", "运动鞋", "增高", "轻量"], base_score=88, sales="6000+人付款"),
    product("shoe-04", "板鞋男夏季透气简约小白鞋", "休闲鞋", 199, "white-shoe", attributes=["男款", "白色", "运动鞋", "透气"], base_score=87, sales="7万+人付款"),
    product("shoe-05", "潮流老爹鞋男 增高厚底", "休闲鞋", 499, "white-shoe", attributes=["男款", "白色", "运动鞋", "增高", "厚底"], base_score=86, sales="9000+人付款"),
    product("shoe-06", "真皮拼色休闲鞋 通勤男款", "休闲鞋", 559, "white-shoe", attributes=["男款", "白色", "运动鞋", "真皮"], base_score=84, sales="3000+人付款"),
    product("shoe-07", "软底基础款白色运动鞋", "休闲鞋", 159, "white-shoe", attributes=["男款", "白色", "运动鞋", "软底"], base_score=83, sales="10万+人付款"),
    product("shoe-08", "奶油白厚底增高运动鞋", "休闲鞋", 529, "white-shoe", attributes=["男款", "白色", "运动鞋", "增高", "厚底"], base_score=82, sales="4000+人付款"),
    product("home-01", "原木风移动边几 小户型置物", "家居", 189, "side-table", attributes=["原木风", "家具", "小户型", "浅色"], base_score=76, sales="2万+人付款", styles=["极简风", "ins风"], goals=["提升幸福感"]),
    product("home-02", "奶油复古空气炸烤箱 厨房多功能", "家居", 899, "armchair", attributes=["奶油风", "家电", "厨房"], base_score=73, sales="5000+人付款"),
    product("home-03", "暖光氛围台灯 卧室阅读灯", "家居", 129, "lamp", attributes=["原木风", "灯具", "卧室"], base_score=71, sales="6万+人付款"),
    product("home-04", "免打孔洞洞板 桌面收纳墙", "收纳", 79, "storage", attributes=["家居", "收纳", "桌面"], base_score=69, sales="8万+人付款"),
    product("home-05", "日式折叠脏衣篮 三层分类", "收纳", 99, "storage", attributes=["家居", "收纳", "日式"], base_score=68, sales="3万+人付款"),
    product("home-06", "原木床头柜 窄缝抽屉收纳", "家居", 239, "side-table", attributes=["原木风", "家具", "收纳"], base_score=67, sales="1万+人付款"),
    product("home-07", "模块化透明鞋盒 防尘可叠放", "收纳", 69, "storage", attributes=["家居", "收纳", "鞋盒"], base_score=65, sales="10万+人付款"),
    product("home-08", "羊羔绒休闲椅 原木脚踏", "家居", 599, "armchair", attributes=["原木风", "家具", "客厅"], base_score=64, sales="7000+人付款"),
    product("cup-01", "高颜值吸管保温杯 便携随行水杯", "水杯", 89, "water-cup", attributes=["水杯", "保温杯", "吸管杯", "便携", "耐脏"], base_score=63, sales="5万+人付款", audiences=["学生", "儿童"], styles=["可爱"], goals=["提升幸福感"], trend=8),
    product("cup-02", "简约大容量运动水杯 Tritan 材质", "水杯", 59, "water-cup-blue", attributes=["水杯", "运动水杯", "大容量", "便携"], base_score=62, sales="3万+人付款"),
    product("beauty-01", "丝绒哑光显白口红 持久不沾杯", "美妆", 129, "fresh", attributes=["口红", "彩妆", "红色", "送礼"], base_score=61, sales="4万+人付款"),
    product("beauty-02", "水光镜面唇釉礼盒 日常百搭色", "美妆", 159, "fresh", attributes=["口红", "唇釉", "彩妆", "送礼"], base_score=60, sales="2万+人付款"),
    product("earbuds-01", "主动降噪蓝牙耳机 入耳式长续航", "数码", 299, "fresh", attributes=["耳机", "蓝牙耳机", "无线", "降噪"], base_score=61, sales="8万+人付款"),
    product("earbuds-02", "开放式无线耳机 运动防水轻量", "数码", 239, "fresh", attributes=["耳机", "无线", "运动", "防水"], base_score=60, sales="5万+人付款"),
    product("phone-01", "Apple 轻薄旗舰智能手机 高清影像长续航", "数码", 3299, "fresh", attributes=["手机", "智能手机", "黑色", "数码"], base_score=61, sales="3万+人付款", brand="苹果", origin="进口", styles=["高级感"], trend=8),
    product("phone-02", "国产大屏高刷手机 影像防抖快充", "数码", 2499, "fresh", attributes=["手机", "智能手机", "蓝色", "数码"], base_score=60, sales="2万+人付款", brand="国产品牌", origin="国产", audiences=["学生"], trend=7),
    product("coffee-01", "奶油白意式咖啡机 家用小型", "家电", 699, "fresh", attributes=["咖啡机", "小家电", "厨房", "奶油风", "小巧"], base_score=61, sales="1万+人付款", audiences=["新手"], styles=["可爱"]),
    product("coffee-02", "研磨一体咖啡机 蒸汽奶泡系统", "家电", 1299, "fresh", attributes=["咖啡机", "小家电", "厨房", "家用"], base_score=60, sales="8000+人付款"),
    product("snack-01", "人气零食大礼包 休闲小吃组合", "食品", 79, "fresh", attributes=["零食", "小吃", "礼盒", "送礼"], base_score=61, sales="10万+人付款"),
    product("snack-02", "坚果饼干下午茶零食组合礼盒", "食品", 99, "fresh", attributes=["零食", "饼干", "坚果", "送礼"], base_score=60, sales="7万+人付款"),
    product("pet-01", "低敏全价猫粮 成猫营养主粮", "宠物", 139, "fresh", attributes=["猫粮", "宠物用品", "主粮", "大容量"], base_score=61, sales="6万+人付款"),
    product("pet-02", "鲜肉全价犬粮 中小型犬主粮", "宠物", 159, "fresh", attributes=["狗粮", "宠物用品", "主粮", "大容量"], base_score=60, sales="4万+人付款"),
    product("baby-01", "高景观轻便婴儿推车 可折叠双向", "母婴", 899, "fresh", attributes=["婴儿车", "宝宝用品", "轻便", "可折叠"], base_score=61, sales="2万+人付款"),
    product("baby-02", "一键收车轻量婴儿推车 可登机", "母婴", 699, "fresh", attributes=["婴儿车", "宝宝用品", "轻量", "便携"], base_score=60, sales="1万+人付款"),
    product("outdoor-01", "自动速开露营帐篷 防雨加厚", "户外", 399, "fresh", attributes=["帐篷", "露营", "防水", "户外"], base_score=61, sales="3万+人付款"),
    product("outdoor-02", "轻量双人徒步帐篷 便携防风", "户外", 529, "fresh", attributes=["帐篷", "露营", "轻量", "便携"], base_score=60, sales="2万+人付款"),
    product("bag-01", "真皮通勤单肩包 简约大容量", "箱包", 459, "fresh", attributes=["包包", "女包", "单肩包", "通勤", "大容量", "真皮"], base_score=61, sales="3万+人付款", audiences=["妈妈"], styles=["高级感"]),
    product("bag-02", "复古腋下包 轻便百搭女包", "箱包", 239, "fresh", attributes=["包包", "女包", "腋下包", "通勤"], base_score=60, sales="2万+人付款"),
    product("office-01", "客制化机械键盘 无线三模热插拔", "办公", 399, "fresh", attributes=["键盘", "机械键盘", "无线", "办公"], base_score=61, sales="5万+人付款"),
    product("office-02", "静音键鼠套装 蓝牙多设备切换", "办公", 189, "fresh", attributes=["键盘", "鼠标", "无线", "办公"], base_score=60, sales="4万+人付款"),
    product("car-01", "车载手机支架 强力吸盘稳固防抖", "汽车用品", 69, "fresh", attributes=["车载支架", "手机支架", "汽车用品", "车载"], base_score=61, sales="8万+人付款"),
    product("car-02", "磁吸车载支架 出风口迷你导航架", "汽车用品", 49, "fresh", attributes=["车载支架", "手机支架", "汽车用品", "磁吸", "小巧"], base_score=60, sales="6万+人付款"),
    product("skincare-01", "舒缓修护面霜 保湿屏障护理", "美妆", 199, "fresh", attributes=["护肤", "面霜", "保湿", "敏感肌"], base_score=61, sales="4万+人付款", audiences=["妈妈"], styles=["高级感"]),
    product("skincare-02", "补水精华液 清透保湿护肤套装", "美妆", 259, "fresh", attributes=["护肤", "精华", "保湿", "套装"], base_score=60, sales="3万+人付款"),
    product("dress-01", "法式碎花连衣裙 夏季收腰显瘦", "女装", 229, "fresh", attributes=["连衣裙", "裙子", "女款", "穿搭", "浅色"], base_score=61, sales="5万+人付款", audiences=["学生"], styles=["法式", "高级感"], trend=8),
    product("dress-02", "纯色吊带长裙 度假通勤两穿", "女装", 189, "fresh", attributes=["连衣裙", "裙子", "女款", "通勤"], base_score=60, sales="3万+人付款", styles=["极简风"]),
    product("fruit-01", "当季新鲜水果礼盒 多品种组合", "生鲜", 109, "fresh", attributes=["水果", "生鲜", "礼盒", "送礼"], base_score=61, sales="6万+人付款"),
    product("fruit-02", "阳光玫瑰葡萄与橙子组合装", "生鲜", 89, "fresh", attributes=["水果", "葡萄", "橙子", "生鲜"], base_score=60, sales="4万+人付款"),
    product("book-01", "年度高分文学小说精选套装", "图书", 128, "fresh", attributes=["图书", "书籍", "小说", "套装"], base_score=61, sales="2万+人付款"),
    product("book-02", "效率提升学习书籍与文具组合", "图书", 99, "fresh", attributes=["图书", "书籍", "文具", "学习"], base_score=60, sales="1万+人付款"),
    product("perfume-01", "清新木质调香水 持久淡香", "香水", 299, "fresh", attributes=["香水", "香氛", "清新", "送礼"], base_score=61, sales="3万+人付款", audiences=["妈妈"], styles=["高级感"]),
    product("perfume-02", "花果香氛香水礼盒 通勤淡香", "香水", 239, "fresh", attributes=["香水", "香氛", "通勤", "礼盒"], base_score=60, sales="2万+人付款"),
    product("fresh-01", "质感绝了！简约白色 Polo 短袖", "服饰", 137, "fresh", attributes=["男款", "白色", "穿搭", "新鲜感"], base_score=58, sales="400+人付款", novelty=10),
    product("fresh-02", "美式街头黑色卫衣 宽松复古穿搭", "服饰", 159, "fresh", attributes=["男款", "黑色", "穿搭", "新鲜感"], base_score=57, sales="3000+人付款", novelty=9),
    product("fresh-03", "新款圆珍珠白色棒球帽 设计感", "配饰", 148, "fresh", attributes=["白色", "配饰", "新鲜感"], base_score=56, sales="1000+人付款", novelty=8),
    product("fresh-04", "银白轻量复古运动鞋 潮流新品", "休闲鞋", 689, "fresh", attributes=["男款", "白色", "运动鞋", "新鲜感", "轻量"], base_score=55, sales="400+人付款", novelty=9, styles=["高级感"], trend=9),
    product("projector-01", "便携智能投影仪 露营卧室两用", "数码", 899, "fresh", attributes=["投影仪", "便携", "卧室", "露营"], base_score=66, sales="3万+人付款", audiences=["学生", "新手"], styles=["极简风"], goals=["宅家", "提升幸福感"], novelty=7, trend=9),
    product("camp-chair-01", "月亮折叠椅 户外露营轻量便携", "户外", 129, "armchair", attributes=["折叠椅", "露营椅", "露营", "轻量", "便携"], base_score=64, sales="6万+人付款", audiences=["新手"], goals=["露营"], novelty=6, trend=8),
    product("camp-light-01", "暖光露营灯 长续航防水氛围灯", "户外", 99, "lamp", attributes=["露营灯", "露营", "防水", "氛围"], base_score=63, sales="5万+人付款", audiences=["新手"], goals=["露营", "提升幸福感"], novelty=7, trend=8),
    product("camp-repel-01", "户外驱蚊灯 露营便携静音防护", "户外", 69, "fresh", attributes=["驱蚊", "露营", "便携", "户外"], base_score=62, sales="4万+人付款", audiences=["儿童"], goals=["露营"], novelty=5, trend=7),
    product("move-box-01", "加厚搬家纸箱 带扣可重复收纳", "收纳", 49, "storage", attributes=["搬家箱", "纸箱", "搬家", "收纳", "耐脏"], base_score=64, sales="8万+人付款", goals=["搬家"]),
    product("move-cart-01", "折叠平板搬运车 静音承重省力", "家居", 159, "fresh", attributes=["搬运车", "搬家", "折叠", "耐用"], base_score=61, sales="3万+人付款", goals=["搬家"]),
    product("cat-litter-01", "低尘豆腐猫砂 快速结团除味", "宠物", 69, "fresh", attributes=["猫砂", "猫用品", "除味", "耐脏"], base_score=66, sales="10万+人付款", audiences=["新手"], goals=["养猫"], trend=8),
    product("cat-scratch-01", "原木猫抓板窝一体 耐磨不掉屑", "宠物", 119, "armchair", attributes=["猫抓板", "猫窝", "猫用品", "耐用"], base_score=63, sales="5万+人付款", audiences=["新手"], goals=["养猫"], styles=["极简风"]),
    product("tool-01", "家用多功能电动工具箱 装修安装", "五金", 299, "fresh", attributes=["工具箱", "电钻", "装修", "耐用"], base_score=64, sales="4万+人付款", audiences=["新手"], goals=["装修", "搬家"]),
    product("decor-01", "现代极简装饰画 客厅沙发背景墙", "家居", 169, "fresh", attributes=["装饰画", "客厅", "装修", "浅色"], base_score=62, sales="3万+人付款", styles=["极简风", "高级感"], goals=["装修", "客厅氛围"], novelty=6),
    product("wedding-gift-01", "新婚双人餐具礼盒 高级感包装", "家居", 299, "fresh", attributes=["结婚礼物", "餐具", "礼盒", "送礼"], base_score=62, sales="2万+人付款", styles=["高级感"], goals=["结婚"]),
    product("wedding-decor-01", "婚礼氛围灯串 暖光布置套装", "家居", 89, "lamp", attributes=["婚礼布置", "灯串", "氛围", "结婚"], base_score=60, sales="1万+人付款", goals=["结婚", "提升幸福感"], novelty=6),
    product("travel-case-01", "轻量万向轮行李箱 可登机耐磨", "箱包", 329, "fresh", attributes=["行李箱", "旅行", "轻量", "耐脏", "耐用"], base_score=67, sales="8万+人付款", audiences=["学生"], goals=["旅行", "毕业"], trend=8),
    product("travel-power-01", "自带线快充充电宝 旅行便携", "数码", 129, "fresh", attributes=["充电宝", "旅行", "便携", "快充"], base_score=66, sales="10万+人付款", audiences=["学生"], goals=["旅行", "音乐节"], trend=9),
    product("travel-pillow-01", "记忆棉旅行颈枕 遮光眼罩套装", "家居", 99, "fresh", attributes=["颈枕", "眼罩", "旅行", "睡眠"], base_score=61, sales="4万+人付款", goals=["旅行", "睡得更好"]),
    product("fitness-mat-01", "高密度防滑瑜伽垫 新手健身", "运动", 89, "fresh", attributes=["瑜伽垫", "健身", "防滑", "耐脏"], base_score=66, sales="9万+人付款", audiences=["新手", "学生"], goals=["健身", "减肥"], trend=8),
    product("fitness-weight-01", "可调节哑铃套装 居家力量训练", "运动", 259, "fresh", attributes=["哑铃", "健身", "居家", "耐用"], base_score=64, sales="5万+人付款", audiences=["新手"], goals=["健身", "减肥"]),
    product("fitness-scale-01", "智能体脂秤 多维身体数据分析", "运动", 119, "fresh", attributes=["体脂秤", "健身", "智能"], base_score=63, sales="7万+人付款", goals=["减肥", "健身"], trend=8),
    product("cook-pan-01", "不粘锅具三件套 新手做饭组合", "厨具", 239, "fresh", attributes=["锅具", "做饭", "不粘", "厨房"], base_score=65, sales="6万+人付款", audiences=["新手", "学生"], goals=["做饭"]),
    product("cook-knife-01", "家用厨刀砧板组合 抗菌易清洁", "厨具", 159, "fresh", attributes=["厨刀", "砧板", "做饭", "厨房", "耐用"], base_score=62, sales="4万+人付款", audiences=["新手"], goals=["做饭"]),
    product("cozy-blanket-01", "柔软亲肤沙发毯 宅家午睡披毯", "家居", 99, "fresh", attributes=["毯子", "宅家", "客厅", "柔软"], base_score=62, sales="5万+人付款", styles=["可爱"], goals=["宅家", "提升幸福感"]),
    product("festival-fan-01", "挂脖小风扇 音乐节户外长续航", "数码", 79, "fresh", attributes=["小风扇", "音乐节", "便携", "户外"], base_score=64, sales="7万+人付款", audiences=["学生"], goals=["音乐节"], novelty=7, trend=9),
    product("festival-bag-01", "透明斜挎小包 音乐节轻便穿搭", "箱包", 69, "fresh", attributes=["斜挎包", "音乐节", "便携", "穿搭"], base_score=61, sales="3万+人付款", audiences=["学生"], styles=["ins风"], goals=["音乐节"], novelty=8, trend=8),
    product("bedroom-bedding-01", "A类柔软四件套 奶油色卧室搭配", "家居", 399, "armchair", attributes=["床品", "卧室", "柔软", "浅色"], base_score=65, sales="5万+人付款", styles=["极简风", "ins风"], goals=["卧室舒适", "睡得更好"], trend=7),
    product("aroma-01", "木质香薰机 暖光静音加湿", "家居", 159, "lamp", attributes=["香薰", "卧室", "静音", "氛围"], base_score=64, sales="6万+人付款", styles=["高级感"], goals=["睡得更好", "提升幸福感", "客厅氛围"], novelty=8, trend=9),
    product("living-rug-01", "奶油色短绒地毯 客厅氛围升级", "家居", 289, "armchair", attributes=["地毯", "客厅", "浅色", "氛围", "升级"], base_score=62, sales="3万+人付款", styles=["ins风", "高级感"], goals=["客厅氛围", "装修"], novelty=7),
    product("desk-organizer-01", "模块化桌面文件收纳架 极简办公", "收纳", 79, "storage", attributes=["桌面收纳", "文件架", "办公", "收纳"], base_score=65, sales="8万+人付款", styles=["极简风"], goals=["桌面整洁", "提高工作效率"], trend=8),
    product("balcony-table-01", "折叠小圆桌 阳台咖啡角桌椅", "家居", 259, "side-table", attributes=["阳台", "咖啡角", "折叠", "家具"], base_score=62, sales="2万+人付款", styles=["ins风"], goals=["阳台咖啡角", "提升幸福感"], novelty=7),
    product("study-headset-01", "英语听力头戴耳机 降噪轻量", "数码", 199, "fresh", attributes=["耳机", "英语学习", "降噪", "轻量"], base_score=63, sales="4万+人付款", audiences=["学生"], goals=["学英语", "提高工作效率"]),
    product("happiness-flower-01", "每周鲜花混合花束 居家幸福感", "家居", 79, "fresh", attributes=["鲜花", "花束", "居家", "新鲜感"], base_score=60, sales="2万+人付款", styles=["ins风"], goals=["提升幸福感"], novelty=10, trend=8),
]

CASE_PRODUCT_GROUPS: dict[str, list[tuple[str, str, int, list[str]]]] = {
    "rental": [
        ("奶油色亲肤床品四件套", "家居", 299, ["床品", "舒适睡眠", "出租屋"]),
        ("原木暖光床头台灯", "灯具", 119, ["台灯", "氛围灯光", "出租屋"]),
        ("模块化九宫格收纳柜", "收纳", 169, ["收纳柜", "小户型收纳", "出租屋"]),
        ("木纹静音香薰加湿器", "家居", 139, ["香薰", "幸福感软装", "出租屋"]),
        ("奶油色柔软短绒地毯", "家居", 189, ["地毯", "幸福感软装", "出租屋"]),
        ("小户型双层移动边几", "家居", 159, ["边几", "幸福感软装", "出租屋"]),
        ("免打孔遮光隔热窗帘", "家居", 129, ["窗帘", "舒适睡眠", "出租屋"]),
        ("慢回弹护颈记忆枕", "家居", 109, ["枕头", "舒适睡眠", "出租屋"]),
        ("便携高清卧室投影仪", "数码", 899, ["投影仪", "氛围灯光", "出租屋"]),
        ("日式折叠分类洗衣篮", "收纳", 79, ["洗衣篮", "小户型收纳", "出租屋"]),
        ("桌面静音大雾量加湿器", "家电", 99, ["加湿器", "幸福感软装", "出租屋"]),
        ("好养活桌面绿植盆栽", "家居", 59, ["绿植", "幸福感软装", "出租屋"]),
    ],
    "concert": [
        ("自带线快充充电宝", "数码", 129, ["充电宝", "续航补给", "演唱会"]),
        ("安检友好透明斜挎包", "箱包", 69, ["透明包", "轻装收纳", "演唱会"]),
        ("长续航挂脖小风扇", "数码", 89, ["小风扇", "户外防护", "演唱会"]),
        ("一次性轻便雨衣三件装", "户外", 39, ["雨衣", "户外防护", "演唱会"]),
        ("清爽高倍防晒喷雾", "美妆", 89, ["防晒霜", "户外防护", "演唱会"]),
        ("演出降噪音乐耳塞", "数码", 79, ["耳塞", "观演体验", "演唱会"]),
        ("高清便携观演望远镜", "数码", 159, ["望远镜", "观演体验", "演唱会"]),
        ("可调亮度应援灯棒", "数码", 59, ["应援棒", "观演体验", "演唱会"]),
        ("防晒百搭棒球帽", "配饰", 69, ["帽子", "户外防护", "演唱会"]),
        ("轻量折叠排队坐垫", "户外", 49, ["坐垫", "观演体验", "演唱会"]),
        ("便携防漏运动水杯", "水杯", 79, ["水杯", "续航补给", "演唱会"]),
        ("防丢可调节手机挂绳", "数码", 39, ["手机挂绳", "轻装收纳", "演唱会"]),
    ],
    "happy": [
        ("每周鲜花高颜值混合花束", "家居", 79, ["鲜花", "新鲜感"]),
        ("静音陶瓷香薰扩香机", "家居", 159, ["香薰", "新鲜感"]),
        ("笑脸陶瓷早餐马克杯", "水杯", 69, ["水杯", "可爱", "新鲜感"]),
        ("暖光蘑菇氛围小夜灯", "灯具", 99, ["台灯", "氛围", "新鲜感"]),
        ("掌上高清居家投影仪", "数码", 799, ["投影仪", "宅家", "新鲜感"]),
        ("织物迷你无线音箱", "数码", 199, ["音箱", "无线", "新鲜感"]),
        ("云朵感亲肤沙发毯", "家居", 119, ["毯子", "柔软", "新鲜感"]),
        ("奶油色滴滤咖啡机", "家电", 399, ["咖啡机", "厨房", "新鲜感"]),
        ("桌面自吸水绿植盆栽", "家居", 59, ["绿植", "桌面", "新鲜感"]),
        ("便携手机照片打印机", "数码", 399, ["照片打印机", "便携", "新鲜感"]),
        ("复古暖光融蜡灯", "灯具", 169, ["融蜡灯", "香薰", "新鲜感"]),
        ("温热揉捏腰颈按摩枕", "家居", 229, ["按摩枕", "舒适", "新鲜感"]),
    ],
    "sunscreen": [
        ("清透轻薄面部防晒乳", "防晒霜", 99, ["防晒霜", "面部", "轻薄"]),
        ("大容量身体防晒喷雾", "防晒霜", 89, ["防晒霜", "身体", "喷雾"]),
        ("便携补涂防晒棒", "防晒霜", 79, ["防晒霜", "防晒棒", "便携"]),
        ("儿童温和防晒乳", "防晒霜", 109, ["防晒霜", "儿童", "温和"]),
        ("敏感肌物理防晒霜", "防晒霜", 129, ["防晒霜", "敏感肌", "物理防晒"]),
        ("运动防水高倍防晒乳", "防晒霜", 119, ["防晒霜", "防水", "运动"]),
        ("自然提亮润色防晒霜", "防晒霜", 139, ["防晒霜", "润色", "面部"]),
        ("清爽透明防晒啫喱", "防晒霜", 89, ["防晒霜", "啫喱", "清爽"]),
        ("保湿型日常防晒乳", "防晒霜", 109, ["防晒霜", "保湿", "日常"]),
        ("随身补妆防晒气垫", "防晒霜", 159, ["防晒霜", "气垫", "便携"]),
        ("海边高倍防晒喷雾", "防晒霜", 129, ["防晒霜", "喷雾", "防水"]),
        ("哑光控油防晒精华", "防晒霜", 149, ["防晒霜", "控油", "面部"]),
    ],
    "dressbase": [
        ("美式复古深蓝牛仔短裙", "连衣裙", 239, ["连衣裙", "裙子", "美式", "深色", "短裙"]),
        ("黑色修身吊带短裙", "连衣裙", 199, ["连衣裙", "裙子", "辣妹风", "深色", "短裙"]),
        ("酒红复古收腰中长裙", "连衣裙", 289, ["连衣裙", "裙子", "复古", "深色", "中长裙"]),
        ("法式黑底碎花裹身裙", "连衣裙", 269, ["连衣裙", "裙子", "法式", "深色", "碎花"]),
        ("白色运动Polo连衣裙", "连衣裙", 219, ["连衣裙", "裙子", "运动风", "浅色", "短裙"]),
        ("祖母绿缎面吊带长裙", "连衣裙", 329, ["连衣裙", "裙子", "高级感", "深色", "长裙"]),
        ("棕色工装衬衫连衣裙", "连衣裙", 259, ["连衣裙", "裙子", "工装风", "深色", "中长裙"]),
        ("红色学院风A字短裙", "连衣裙", 229, ["连衣裙", "裙子", "学院风", "亮色", "短裙"]),
        ("炭灰极简修身长裙", "连衣裙", 299, ["连衣裙", "裙子", "极简风", "深色", "长裙"]),
        ("蓝白条纹衬衫连衣裙", "连衣裙", 249, ["连衣裙", "裙子", "通勤", "浅色", "中长裙"]),
        ("紫色Y2K修身短裙", "连衣裙", 189, ["连衣裙", "裙子", "Y2K", "亮色", "短裙"]),
        ("驼色波西米亚度假长裙", "连衣裙", 279, ["连衣裙", "裙子", "波西米亚", "大地色", "长裙"]),
    ],
    "dresskorean": [
        ("韩式黑色方领修身短裙", "连衣裙", 259, ["连衣裙", "裙子", "韩式", "深色", "短裙"]),
        ("韩式藏蓝海军领中长裙", "连衣裙", 289, ["连衣裙", "裙子", "韩式", "深色", "中长裙"]),
        ("韩式酒红针织鱼尾裙", "连衣裙", 299, ["连衣裙", "裙子", "韩式", "深色", "针织"]),
        ("韩式深棕百褶衬衫裙", "连衣裙", 279, ["连衣裙", "裙子", "韩式", "深色", "百褶"]),
        ("韩式炭灰双排扣西装裙", "连衣裙", 339, ["连衣裙", "裙子", "韩式", "深色", "西装"]),
        ("韩式墨绿方领修身裙", "连衣裙", 309, ["连衣裙", "裙子", "韩式", "深色", "修身"]),
        ("韩式宝蓝泡泡袖A字裙", "连衣裙", 249, ["连衣裙", "裙子", "韩式", "亮色", "泡泡袖"]),
        ("韩式深紫裹身荷叶边裙", "连衣裙", 289, ["连衣裙", "裙子", "韩式", "深色", "裹身"]),
        ("韩式砖红方领收腰裙", "连衣裙", 269, ["连衣裙", "裙子", "韩式", "深色", "收腰"]),
        ("韩式黑白粗花呢短裙", "连衣裙", 329, ["连衣裙", "裙子", "韩式", "深色", "粗花呢"]),
        ("韩式深蓝牛仔背带裙", "连衣裙", 229, ["连衣裙", "裙子", "韩式", "深色", "牛仔"]),
        ("韩式巧克力色针织长裙", "连衣裙", 299, ["连衣裙", "裙子", "韩式", "深色", "长裙"]),
    ],
    "dresscase": [
        ("象牙白收腰衬衫连衣裙", "连衣裙", 269, ["连衣裙", "裙子", "浅色"]),
        ("浅蓝碎花韩式中长裙", "连衣裙", 239, ["连衣裙", "裙子", "浅色"]),
        ("奶油色针织鱼尾连衣裙", "连衣裙", 299, ["连衣裙", "裙子", "浅色"]),
        ("樱花粉韩式A字连衣裙", "连衣裙", 229, ["连衣裙", "裙子", "浅色"]),
        ("鹅黄色吊带度假长裙", "连衣裙", 219, ["连衣裙", "裙子", "浅色"]),
        ("薄荷绿百褶收腰长裙", "连衣裙", 259, ["连衣裙", "裙子", "浅色"]),
        ("燕麦色极简通勤连衣裙", "连衣裙", 289, ["连衣裙", "裙子", "浅色"]),
        ("白色蕾丝温柔连衣裙", "连衣裙", 319, ["连衣裙", "裙子", "浅色"]),
        ("淡紫色裹身荷叶边长裙", "连衣裙", 249, ["连衣裙", "裙子", "浅色"]),
        ("浅蓝牛仔韩式背带裙", "连衣裙", 199, ["连衣裙", "裙子", "浅色"]),
        ("蜜桃色泡泡袖连衣裙", "连衣裙", 239, ["连衣裙", "裙子", "浅色"]),
        ("浅灰西装领收腰连衣裙", "连衣裙", 329, ["连衣裙", "裙子", "浅色"]),
    ],
    "fitcase": [
        ("加厚防滑瑜伽垫", "运动", 99, ["瑜伽垫", "训练装备", "健身"]),
        ("可调节重量哑铃套装", "运动", 399, ["哑铃", "训练装备", "健身"]),
        ("多维数据智能体脂秤", "运动", 129, ["体脂秤", "数据记录", "健身"]),
        ("大容量刻度运动水杯", "水杯", 79, ["运动水杯", "补水营养", "健身"]),
        ("五档阻力弹力带套装", "运动", 69, ["弹力带", "训练装备", "健身"]),
        ("高密度肌肉放松泡沫轴", "运动", 89, ["泡沫轴", "恢复放松", "健身"]),
        ("无绳负重智能跳绳", "运动", 119, ["跳绳", "训练装备", "健身"]),
        ("家用包胶壶铃", "运动", 159, ["壶铃", "训练装备", "健身"]),
        ("透气缓震综合训练鞋", "运动", 299, ["训练鞋", "训练装备", "健身"]),
        ("运动数据监测智能手表", "数码", 399, ["运动手表", "数据记录", "健身"]),
        ("防漏蛋白粉摇摇杯", "水杯", 59, ["摇摇杯", "补水营养", "健身"]),
        ("迷你深层肌肉筋膜枪", "运动", 229, ["筋膜枪", "恢复放松", "健身"]),
    ],
    "wow": [
        ("磁悬浮绿植桌面盆栽", "家居", 399, ["磁悬浮", "眼前一亮", "新鲜感"]),
        ("磁吸平衡创意氛围灯", "灯具", 259, ["平衡灯", "眼前一亮", "新鲜感"]),
        ("口袋便携照片打印机", "数码", 399, ["照片打印机", "眼前一亮", "新鲜感"]),
        ("透明机身无线蓝牙音箱", "数码", 299, ["音箱", "眼前一亮", "新鲜感"]),
        ("日出唤醒渐变闹钟灯", "灯具", 229, ["唤醒灯", "眼前一亮", "新鲜感"]),
        ("动态流沙艺术摆件", "家居", 169, ["流沙画", "眼前一亮", "新鲜感"]),
        ("迷你银河星空投影仪", "数码", 199, ["星空投影", "眼前一亮", "新鲜感"]),
        ("无线便携榨汁杯", "家电", 159, ["榨汁杯", "眼前一亮", "新鲜感"]),
        ("智能桌面香草种植机", "家居", 499, ["种植机", "眼前一亮", "新鲜感"]),
        ("恒温感应暖杯垫", "家电", 129, ["暖杯垫", "眼前一亮", "新鲜感"]),
        ("口袋高清数码显微镜", "数码", 269, ["显微镜", "眼前一亮", "新鲜感"]),
        ("几何暖光香薰扩香机", "家居", 189, ["香薰", "眼前一亮", "新鲜感"]),
    ],
}

CASE_PRODUCT_GOALS = {
    "rental": ["出租屋舒适", "提升幸福感"],
    "concert": ["看演唱会"],
    "happy": ["提升幸福感"],
    "sunscreen": ["户外防护"],
    "dressbase": ["多风格穿搭"],
    "dresskorean": ["韩式穿搭"],
    "dresscase": ["韩式穿搭"],
    "fitcase": ["健身"],
    "wow": ["探索新鲜事物"],
}

for group, rows in CASE_PRODUCT_GROUPS.items():
    for index, (title, category, price, attributes) in enumerate(rows, start=1):
        PRODUCTS.append(
            product(
                f"{group}-{index:02d}",
                title,
                category,
                price,
                "fresh",
                attributes=attributes + (
                    ["幸福感精选"] if group == "happy"
                    else ["眼前一亮精选"] if group == "wow"
                    else []
                ),
                base_score=(
                    112 - index if group == "dressbase"
                    else 98 - index if group == "dresskorean"
                    else 84 - index if group == "dresscase"
                    else 82 - index
                ),
                sales=f"{max(1, 13 - index)}万+人付款",
                novelty=10 if group == "wow" else 9 if group in ("happy", "concert", "fitcase") else 5,
                goals=CASE_PRODUCT_GOALS[group],
                styles=["韩式"] if group in ("dresskorean", "dresscase") else [],
                trend=10 if group == "wow" else 9 if group in ("happy", "concert", "sunscreen", "fitcase") else 7,
            )
        )

def infer_sample_category(title: str) -> tuple[str, list[str]]:
    lowered = title.lower()
    rules = (
        (("婴儿", "宝宝", "新生儿", "儿童", "童装"), "母婴", ["宝宝用品", "童装"]),
        (("劳保鞋", "鞋"), "鞋靴", ["鞋", "穿搭"]),
        (("手镯", "翡翠", "玉镯"), "珠宝", ["手镯", "珠宝", "女款"]),
        (("雨伞", "伞"), "日用", ["雨伞", "便携"]),
        (("团扇", "宫扇", "扇子"), "文创", ["非遗", "手工", "送礼"]),
        (("cos", "cosplay"), "服饰", ["动漫", "角色扮演", "穿搭"]),
        (("衬衫", "针织", "开衫", "毛衣", "t恤", "卫衣", "上衣", "cardigan", "sweater"), "服饰", ["上衣", "穿搭"]),
    )
    for keywords, category, attributes in rules:
        if any(keyword in lowered for keyword in keywords):
            extra = []
            if any(word in lowered for word in ("女", "women")):
                extra.append("女款")
            if any(word in lowered for word in ("男", "men")):
                extra.append("男款")
            return category, attributes + extra
    return "其他", ["精选商品"]


def load_sample_products() -> list[dict[str, Any]]:
    source = ROOT / "catalog" / "item_sample.json"
    if not source.exists():
        return []
    rows = json.loads(source.read_text(encoding="utf-8"))
    result = []
    for index, row in enumerate(rows, start=1):
        title = str(row["title"]).strip()
        pict_url = str(row["pict_url"]).strip().lstrip("/")
        category, attributes = infer_sample_category(title)
        result.append(product(
            f"odps-test-{index:02d}",
            title,
            category,
            float(row["price"]),
            f"https://img.alicdn.com/imgextra/{pict_url}",
            attributes=attributes + ["ODPS测试商品"],
            base_score=20 - index,
            sales="测试数据",
            novelty=7,
            styles=["韩系"] if "韩系" in title else [],
            trend=7,
        ))
    return result


ODPS_TEST_PRODUCTS = load_sample_products()
COMMON_CATALOG_GROUPS: dict[str, tuple[str, str, list[tuple[str, int, list[str]]]]] = {
    "laundry": ("日用", "洗衣液", [
        ("浓缩除菌洗衣液 家庭大容量装", 69, ["洗衣液", "清洁", "除菌", "大容量"]),
        ("持久留香洗衣凝珠 三合一盒装", 59, ["洗衣液", "洗衣凝珠", "留香", "便携"]),
    ]),
    "tissue": ("日用", "纸巾", [
        ("柔韧亲肤抽纸 整箱家庭装", 49, ["纸巾", "抽纸", "家庭装"]),
        ("加厚无芯卷纸 卫生间囤货装", 55, ["纸巾", "卷纸", "卫生纸", "大容量"]),
    ]),
    "toothbrush": ("个护", "电动牙刷", [
        ("声波电动牙刷 五档清洁长续航", 169, ["电动牙刷", "牙刷", "长续航"]),
        ("软毛护龈电动牙刷 学生便携款", 129, ["电动牙刷", "牙刷", "软毛", "便携"]),
    ]),
    "shampoo": ("个护", "洗发水", [
        ("控油蓬松洗发水 清爽留香", 89, ["洗发水", "洗发露", "控油", "留香"]),
        ("氨基酸修护洗发水 柔顺套装", 119, ["洗发水", "洗发露", "修护", "套装"]),
    ]),
    "dryer": ("个护", "吹风机", [
        ("高速负离子吹风机 快干护发", 299, ["吹风机", "电吹风", "负离子", "快干"]),
        ("折叠便携吹风机 宿舍旅行两用", 139, ["吹风机", "电吹风", "折叠", "便携"]),
    ]),
    "robotvac": ("家电", "扫地机器人", [
        ("扫拖一体机器人 自动集尘避障", 1999, ["扫地机器人", "扫地机", "扫拖一体", "智能"]),
        ("超薄智能扫地机 强力吸尘规划清扫", 1299, ["扫地机器人", "扫地机", "吸尘器", "智能"]),
    ]),
    "ricecooker": ("家电", "电饭煲", [
        ("智能预约电饭煲 多功能家用", 299, ["电饭煲", "电饭锅", "智能", "厨房"]),
        ("迷你电饭煲 宿舍一人食小容量", 189, ["电饭煲", "电饭锅", "小容量", "宿舍"]),
    ]),
    "airfryer": ("家电", "空气炸锅", [
        ("可视化空气炸锅 大容量低脂烹饪", 399, ["空气炸锅", "厨房", "大容量"]),
        ("多功能空气炸锅 烘烤一体易清洁", 329, ["空气炸锅", "烘烤", "易清洁"]),
    ]),
    "bedding": ("家居", "床品", [
        ("A类纯棉床品四件套 柔软亲肤", 299, ["床品", "四件套", "床上用品", "纯棉"]),
        ("奶油色被套床单三件套 宿舍适用", 199, ["床品", "被套", "床单", "浅色"]),
    ]),
    "pillow": ("家居", "枕头", [
        ("慢回弹记忆枕 护颈分区支撑", 159, ["枕头", "枕芯", "记忆枕", "护颈"]),
        ("五星酒店羽丝绒枕芯 柔软透气", 99, ["枕头", "枕芯", "柔软", "透气"]),
    ]),
    "umbrella": ("日用", "雨伞", [
        ("全自动晴雨伞 防晒防紫外线", 79, ["雨伞", "晴雨伞", "遮阳伞", "防晒"]),
        ("迷你五折口袋伞 超轻便携", 59, ["雨伞", "折叠伞", "便携", "轻量"]),
    ]),
    "tablet": ("数码", "平板电脑", [
        ("高清大屏平板电脑 学习娱乐轻办公", 1899, ["平板电脑", "平板", "学习", "轻办公"]),
        ("护眼学习平板 手写笔套装", 1599, ["平板电脑", "平板", "护眼", "套装"]),
    ]),
    "laptop": ("电脑", "笔记本电脑", [
        ("轻薄笔记本电脑 长续航办公本", 3999, ["笔记本电脑", "电脑", "轻薄", "办公"]),
        ("高性能笔记本电脑 学习设计两用", 4599, ["笔记本电脑", "电脑", "高性能", "学习"]),
    ]),
    "smartwatch": ("数码", "智能手表", [
        ("全天候健康监测智能手表", 699, ["智能手表", "手表", "健康监测", "运动"]),
        ("轻薄运动手表 GPS长续航", 499, ["智能手表", "运动手表", "GPS", "长续航"]),
    ]),
    "speaker": ("数码", "蓝牙音箱", [
        ("便携蓝牙音箱 户外防水重低音", 239, ["蓝牙音箱", "音箱", "音响", "防水"]),
        ("桌面无线音箱 氛围灯长续航", 199, ["蓝牙音箱", "音箱", "无线", "氛围"]),
    ]),
    "camera": ("数码", "相机", [
        ("轻量微单相机 旅行人像高清摄影", 4999, ["相机", "微单", "照相机", "旅行"]),
        ("复古数码相机 自拍美颜便携", 699, ["相机", "数码相机", "自拍", "便携"]),
    ]),
    "jeans": ("服饰", "牛仔裤", [
        ("高腰直筒牛仔裤 显瘦百搭", 169, ["牛仔裤", "裤子", "直筒", "显瘦"]),
        ("复古水洗宽松牛仔裤 男女同款", 199, ["牛仔裤", "裤子", "宽松", "复古"]),
    ]),
    "shirt": ("服饰", "衬衫", [
        ("纯棉白衬衫 通勤抗皱基础款", 159, ["衬衫", "衬衣", "白色", "通勤"]),
        ("宽松条纹衬衫 防晒叠穿外搭", 139, ["衬衫", "衬衣", "条纹", "宽松"]),
    ]),
    "jacket": ("服饰", "外套", [
        ("轻薄防风夹克 男女同款", 229, ["外套", "夹克", "轻薄", "防风"]),
        ("中长款通勤风衣 高级感垂顺", 399, ["外套", "风衣", "通勤", "高级感"]),
    ]),
    "slippers": ("鞋靴", "拖鞋", [
        ("云朵软底居家拖鞋 防滑静音", 39, ["拖鞋", "居家鞋", "软底", "防滑"]),
        ("轻量凉拖鞋 夏季浴室速干", 29, ["拖鞋", "凉拖", "速干", "轻量"]),
    ]),
    "underwear": ("内衣", "内衣", [
        ("精梳棉内裤 多色组合装", 79, ["内衣", "内裤", "纯棉", "组合装"]),
        ("无痕轻薄文胸 舒适聚拢", 129, ["内衣", "文胸", "无痕", "轻薄"]),
    ]),
    "mask": ("美妆", "面膜", [
        ("玻尿酸补水面膜 十片装", 89, ["面膜", "补水面膜", "保湿", "套装"]),
        ("舒缓修护贴片面膜 敏感肌适用", 109, ["面膜", "贴片面膜", "修护", "敏感肌"]),
    ]),
    "formula": ("母婴", "奶粉", [
        ("婴幼儿配方奶粉 科学营养罐装", 299, ["奶粉", "婴儿奶粉", "宝宝奶粉", "营养"]),
        ("儿童成长奶粉 高钙易吸收", 239, ["奶粉", "儿童奶粉", "高钙", "营养"]),
    ]),
    "toy": ("玩具", "玩具", [
        ("木质绕珠益智玩具 幼儿启蒙", 129, ["玩具", "益智玩具", "儿童玩具", "木质"]),
        ("大颗粒积木拼装套装 儿童礼物", 159, ["玩具", "积木", "儿童玩具", "礼物"]),
    ]),
    "fishing": ("户外", "鱼竿", [
        ("碳素便携鱼竿 钓鱼入门套装", 259, ["鱼竿", "钓鱼竿", "钓鱼装备", "套装"]),
        ("轻量路亚竿纺车轮组合", 399, ["鱼竿", "路亚竿", "钓鱼装备", "轻量"]),
    ]),
}

for group, (category, intent_value, rows) in COMMON_CATALOG_GROUPS.items():
    for index, (title, price, attributes) in enumerate(rows, start=1):
        PRODUCTS.append(
            product(
                f"common-{group}-{index:02d}",
                title,
                category,
                price,
                "fresh",
                attributes=[intent_value, *attributes],
                base_score=65 - index,
                sales=f"{7 - index}万+人付款",
                trend=7,
            )
        )

DATA_DIR = ROOT / "data"
TAXONOMY_DATA = json.loads((DATA_DIR / "category_taxonomy.json").read_text(encoding="utf-8"))
TAXONOMY_CATEGORIES: list[dict[str, str]] = TAXONOMY_DATA["categories"]
TAXONOMY_CATALOG = json.loads((DATA_DIR / "category_products.json").read_text(encoding="utf-8"))
TAXONOMY_PRODUCTS: list[dict[str, Any]] = TAXONOMY_CATALOG["products"]
# The homepage is loaded independently by static/app.js. Runtime intent results use
# only the real CSV-backed catalog so legacy demo/template products cannot leak in.
PRODUCTS: list[dict[str, Any]] = []
PRODUCT_BY_ID = {item["id"]: item for item in TAXONOMY_PRODUCTS}
INITIAL_RECOMMENDATIONS: list[str] = []
INITIAL_SEARCH_RESULTS: list[str] = []

SCENARIO_CATALOG = json.loads(SCENARIO_CATALOG_PATH.read_text(encoding="utf-8"))
SCENARIO_PRESETS: list[dict[str, Any]] = SCENARIO_CATALOG["presets"]
EXAMPLE_CATALOG = json.loads(EXAMPLE_CATALOG_PATH.read_text(encoding="utf-8"))
EXAMPLE_GUIDES: list[dict[str, Any]] = EXAMPLE_CATALOG["examples"]


def normalize_preset_prompt(value: str) -> str:
    return re.sub(r"[\s，。！？、,.!?“”\"'：:；;·\-—_]+", "", value).lower()


SCENARIO_PRESET_BY_KEY = {
    item["key"]: item
    for item in SCENARIO_PRESETS
}

# The demo scenarios are keyed by the user's core intent, not by a verbatim
# sentence. More specific intents are listed first so "通勤穿搭" routes to the
# commuting set instead of the broader outfit set.
SCENARIO_PRESET_MATCHERS = (
    {
        "key": "scenario-1-q2",
        "pattern": r"通勤",
    },
    {
        "key": "scenario-1-q3",
        "pattern": r"性价比|实惠|有些贵|太贵|便宜(?:点|些)|价格(?:低|友好)",
    },
    {
        "key": "scenario-1-q1",
        "pattern": r"穿搭|衣服搭配|服装搭配|看看衣服|想看衣服",
    },
    {
        "key": "scenario-2-q2",
        "pattern": r"兴趣爱好|新(?:的)?爱好|流行(?:的)?兴趣|值得尝试(?:的)?兴趣|尝试(?:点|些)?新爱好",
    },
    {
        "key": "scenario-2-q1",
        "pattern": r"看(?:得)?有点腻|看腻|换点新鲜|来点新鲜|新鲜(?:的|点)?|换一批|换点新的",
    },
    {
        "key": "scenario-3-q1",
        "pattern": r"搬(?:了)?新家|搬家|布置(?:一下|起来)?(?:我)?(?:的)?(?:新)?家|把家布置|新家(?:布置|装饰|收纳)",
    },
    {
        "key": "scenario-4-q1",
        "pattern": r"见喜欢的人|见心上人|见暗恋的人|去约会|要约会|约会(?:穿搭|准备|好物)?",
    },
)


def preset_scenario_for(transcript: str) -> dict[str, Any] | None:
    normalized = normalize_preset_prompt(transcript)
    for matcher in SCENARIO_PRESET_MATCHERS:
        if re.search(matcher["pattern"], normalized):
            return SCENARIO_PRESET_BY_KEY[matcher["key"]]
    return None


def example_guide_for(transcript: str) -> dict[str, Any] | None:
    normalized = normalize_preset_prompt(transcript)
    for guide in EXAMPLE_GUIDES:
        if re.search(guide["pattern"], normalized):
            return guide
    return None


def slot(name: str, operator: str, value: Any, strength: str, label: str) -> dict[str, Any]:
    return {"name": name, "operator": operator, "value": value, "strength": strength, "label": label}


def preset_bubble(
    source_key: str,
    label: str,
    *,
    group: str,
    operator: str = "eq",
) -> dict[str, Any]:
    return {
        "name": "presetBubble",
        "operator": operator,
        "value": source_key,
        "strength": "soft",
        "label": label,
        "sourceKey": source_key,
        "presetGroup": group,
        "presetBubble": True,
    }


PRESET_BUBBLE_PLANS: dict[str, dict[str, Any]] = {
    "scenario-1-q1": {
        "group": "scenario-1",
        "reset": True,
        "removeKeys": [],
        "add": [
            preset_bubble("preset-s1-outfit", "+ 穿搭", group="scenario-1"),
            preset_bubble("preset-s1-skincare", "− 护肤", group="scenario-1", operator="neq"),
        ],
    },
    "scenario-1-q2": {
        "group": "scenario-1",
        "reset": False,
        "removeKeys": ["preset-s1-outfit"],
        "add": [
            preset_bubble("preset-s1-commute", "+ 通勤穿搭", group="scenario-1"),
            preset_bubble("preset-s1-formal", "− 太正式", group="scenario-1", operator="neq"),
            preset_bubble("preset-s1-ordinary", "− 太普通", group="scenario-1", operator="neq"),
        ],
    },
    "scenario-1-q3": {
        "group": "scenario-1",
        "reset": False,
        "removeKeys": [],
        "add": [
            preset_bubble("preset-s1-value", "+ 高性价比", group="scenario-1"),
            preset_bubble("preset-s1-expensive", "− 高价", group="scenario-1", operator="neq"),
        ],
    },
    "scenario-2-q1": {
        "group": "scenario-2",
        "reset": True,
        "removeKeys": [],
        "add": [
            preset_bubble("preset-s2-fresh", "+ 新鲜感", group="scenario-2"),
            preset_bubble("preset-s2-repeat", "− 重复内容", group="scenario-2", operator="neq"),
        ],
    },
    "scenario-2-q2": {
        "group": "scenario-2",
        "reset": False,
        "removeKeys": ["preset-s2-repeat"],
        "add": [
            preset_bubble("preset-s2-trending", "+ 新流行", group="scenario-2"),
            preset_bubble("preset-s2-hobbies", "+ 兴趣爱好", group="scenario-2"),
        ],
    },
    "scenario-3-q1": {
        "group": "scenario-3",
        "reset": True,
        "removeKeys": [],
        "add": [
            preset_bubble("preset-s3-home", "+ 新家布置", group="scenario-3"),
            preset_bubble("preset-s3-storage", "+ 收纳", group="scenario-3"),
            preset_bubble("preset-s3-decor", "+ 软装氛围", group="scenario-3"),
        ],
    },
    "scenario-4-q1": {
        "group": "scenario-4",
        "reset": True,
        "removeKeys": [],
        "add": [
            preset_bubble("preset-s4-date", "+ 约会准备", group="scenario-4"),
            preset_bubble("preset-s4-outfit", "+ 见面穿搭", group="scenario-4"),
            preset_bubble("preset-s4-gift", "+ 心意礼物", group="scenario-4"),
        ],
    },
}


def apply_preset_bubble_plan(
    existing: list[dict[str, Any]],
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    group = plan["group"]
    current = [dict(item) for item in existing if isinstance(item, dict)]
    continues_group = any(item.get("presetGroup") == group for item in current)
    if plan["reset"] or not continues_group:
        removed_labels = [str(item.get("label", "")) for item in current if item.get("label")]
        current = []
    else:
        remove_keys = set(plan["removeKeys"])
        removed_labels = [
            str(item.get("label", ""))
            for item in current
            if item.get("sourceKey") in remove_keys and item.get("label")
        ]
        current = [item for item in current if item.get("sourceKey") not in remove_keys]
    for condition in plan["add"]:
        current = [item for item in current if item.get("sourceKey") != condition["sourceKey"]]
        current.append(dict(condition))
    return current, removed_labels


COMMODITY_INTENTS = [
    ("洗衣液", "洗衣液", ("洗衣凝珠", "洗衣服用的", "洗涤剂", "洗衣液")),
    ("纸巾", "纸巾", ("卫生纸", "厕纸", "卷纸", "抽纸", "纸巾")),
    ("电动牙刷", "电动牙刷", ("刷牙的", "电动牙刷", "牙刷")),
    ("洗发水", "洗发水", ("洗头膏", "洗发露", "洗发水")),
    ("吹风机", "吹风机", ("吹头发的", "电吹风", "吹风机")),
    ("扫地机器人", "扫地机器人", ("机器人吸尘器", "扫地机器人", "扫地机")),
    ("电饭煲", "电饭煲", ("煮饭锅", "电饭锅", "电饭煲")),
    ("空气炸锅", "空气炸锅", ("空气炸锅", "炸锅")),
    ("床品", "床上用品", ("床上四件套", "床上用品", "四件套", "被套", "床单", "床品")),
    ("枕头", "枕头", ("记忆枕", "枕芯", "枕头")),
    ("雨伞", "雨伞", ("晴雨伞", "遮阳伞", "折叠伞", "雨伞")),
    ("平板电脑", "平板电脑", ("平板电脑", "学习平板", "ipad", "iPad", "平板")),
    ("笔记本电脑", "笔记本电脑", ("笔记本电脑", "手提电脑", "笔记本", "电脑")),
    ("智能手表", "智能手表", ("运动手表", "智能手表", "手表")),
    ("蓝牙音箱", "蓝牙音箱", ("便携音响", "蓝牙音箱", "音响", "音箱")),
    ("相机", "相机", ("数码相机", "照相机", "摄像机", "微单", "相机")),
    ("牛仔裤", "牛仔裤", ("牛仔长裤", "牛仔裤", "裤子")),
    ("衬衫", "衬衫", ("白衬衫", "衬衣", "衬衫")),
    ("外套", "外套", ("防晒衣", "夹克", "风衣", "外套")),
    ("拖鞋", "拖鞋", ("居家鞋", "凉拖", "拖鞋")),
    ("内衣", "内衣", ("文胸", "内裤", "内衣")),
    ("面膜", "面膜", ("补水面膜", "贴片面膜", "面膜")),
    ("奶粉", "奶粉", ("婴儿奶粉", "宝宝奶粉", "儿童奶粉", "奶粉")),
    ("玩具", "玩具", ("儿童玩具", "益智玩具", "积木", "玩具")),
    ("鱼竿", "鱼竿", ("钓鱼装备", "钓鱼竿", "路亚竿", "鱼竿")),
    ("防晒霜", "防晒霜", ("防晒喷雾", "防晒乳", "防晒霜", "防晒")),
    ("投影仪", "投影仪", ("智能投影仪", "家用投影仪", "投影仪")),
    ("瑜伽垫", "瑜伽垫", ("健身垫", "瑜伽垫")),
    ("行李箱", "行李箱", ("旅行箱", "拉杆箱", "行李箱")),
    ("充电宝", "充电宝", ("移动电源", "充电宝")),
    ("锅具", "锅具", ("不粘锅", "炒锅", "锅具")),
    ("香薰", "香薰", ("香薰机", "香薰")),
    ("鲜花", "鲜花", ("花束", "鲜花")),
    ("汽车用品", "汽车用品", ("车载手机支架", "汽车用品", "车载支架", "手机支架", "车载")),
    ("耳机", "蓝牙耳机", ("主动降噪耳机", "蓝牙耳机", "无线耳机")),
    ("咖啡机", "咖啡机", ("意式咖啡机", "家用咖啡机", "咖啡机")),
    ("婴儿车", "婴儿车", ("婴儿推车", "宝宝推车", "婴儿车")),
    ("键盘", "机械键盘", ("机械键盘", "客制化键盘")),
    ("运动鞋", "运动鞋", ("运动鞋", "小白鞋", "休闲鞋", "鞋子")),
    ("宠物用品", "宠物用品", ("宠物用品", "宠物商品")),
    ("宝宝用品", "母婴用品", ("母婴用品", "宝宝用品", "婴儿用品")),
    ("护肤", "护肤品", ("护肤套装", "护肤品", "护肤", "面霜", "精华液", "精华")),
    ("口红", "口红", ("口红礼盒", "口红", "唇釉", "唇膏")),
    ("美妆", "美妆", ("化妆品", "彩妆", "美妆")),
    ("耳机", "耳机", ("耳机", "耳麦")),
    ("手机", "手机", ("智能手机", "手机")),
    ("数码", "数码产品", ("电子产品", "数码产品", "数码")),
    ("家电", "小家电", ("厨房家电", "小家电", "家电")),
    ("零食", "零食", ("零食大礼包", "零食礼包", "零食", "小吃", "饼干", "坚果")),
    ("食品", "食品", ("食品", "吃的")),
    ("猫粮", "猫粮", ("猫粮", "猫主粮")),
    ("狗粮", "狗粮", ("狗粮", "犬粮")),
    ("宠物", "宠物用品", ("宠物", "猫咪用品", "狗狗用品")),
    ("母婴", "母婴用品", ("母婴", "宝宝")),
    ("帐篷", "帐篷", ("露营帐篷", "户外帐篷", "帐篷")),
    ("户外", "户外用品", ("露营装备", "户外用品", "露营", "户外")),
    ("箱包", "包包", ("单肩包", "腋下包", "女包", "包包", "箱包")),
    ("办公", "办公用品", ("办公用品", "办公")),
    ("键盘", "键盘", ("键鼠套装", "键盘")),
    ("鼠标", "鼠标", ("无线鼠标", "鼠标")),
    ("连衣裙", "连衣裙", ("碎花裙", "连衣裙", "长裙", "裙子")),
    ("女装", "女装", ("女士衣服", "女装")),
    ("穿搭", "衣服", ("男装", "衣服", "服装", "短袖", "T恤", "t恤", "穿搭")),
    ("水果", "水果", ("水果礼盒", "新鲜水果", "水果", "葡萄", "橙子")),
    ("生鲜", "生鲜", ("生鲜食品", "生鲜")),
    ("图书", "图书", ("文学小说", "学习书", "书籍", "图书", "小说", "看书", "买书")),
    ("文具", "文具", ("学习文具", "文具")),
    ("香水", "香水", ("香水礼盒", "香水", "香氛")),
    ("水杯", "水杯", ("运动水杯", "保温杯", "随行杯", "吸管杯", "水杯", "杯子")),
    ("收纳", "收纳", ("收纳用品", "收纳")),
    ("家具", "家具", ("床头柜", "边几", "椅子", "桌子", "家具")),
    ("灯具", "灯具", ("台灯", "阅读灯", "灯具")),
    ("家居", "家居", ("家居用品", "收拾家", "家居", "家里")),
    ("跑鞋", "跑鞋", ("跑步鞋", "跑鞋")),
    ("配饰", "配饰", ("棒球帽", "帽子", "配饰")),
]

ATTRIBUTE_INTENTS = [
    ("浅色", "浅色", ("浅色系", "浅色", "颜色浅")),
    ("大容量", "大一点", ("大一点", "更大", "大号")),
    ("小巧", "小一点", ("小一点", "更小", "小巧")),
    ("耐脏", "更耐脏", ("耐脏一点", "更耐脏", "耐脏")),
    ("耐用", "更耐用", ("更耐用", "耐用一点", "耐用")),
    ("大容量", "大容量", ("大容量", "容量大")),
    ("便携", "便携", ("便携", "方便携带", "随身")),
    ("降噪", "降噪", ("主动降噪", "降噪")),
    ("保温杯", "保温", ("保温效果", "能保温", "保温")),
    ("通勤", "通勤", ("上班用", "通勤")),
    ("送礼", "适合送礼", ("适合送人", "送给朋友", "送礼", "礼物")),
    ("防水", "防水", ("防雨", "防水")),
    ("无线", "无线", ("无线", "蓝牙连接")),
    ("轻量", "更轻", ("更轻一点", "轻一点", "更轻", "轻便", "轻量")),
    ("真皮", "真皮", ("真皮材质", "真皮")),
    ("红色", "红色", ("红色", "红的")),
    ("黑色", "黑色", ("黑色", "黑的")),
    ("白色", "白色", ("白色", "白的")),
    ("蓝色", "蓝色", ("蓝色", "蓝的")),
    ("粉色", "粉色", ("粉色", "粉的")),
]

AUDIENCE_INTENTS = [
    ("学生", "适合学生", ("学生党", "适合学生", "学生用")),
    ("新手", "适合新手", ("入门用", "新手用", "适合新手", "新手")),
    ("妈妈", "给妈妈", ("妈妈用", "给妈妈买", "送妈妈")),
    ("男朋友", "男朋友用", ("男朋友用", "给男朋友", "男友用")),
    ("儿童", "儿童可用", ("小朋友用", "儿童可以用", "儿童用", "孩子用")),
]

STYLE_INTENTS = [
    ("韩式", "韩式风格", ("韩式风格", "韩系风格", "韩式", "韩系")),
    ("法式", "法式", ("法式一点", "法式风", "法式")),
    ("极简风", "极简风", ("极简一点", "极简风", "极简")),
    ("ins风", "ins风", ("ins风", "ins一点")),
    ("高级感", "高级感", ("高级一点", "有高级感", "高级感")),
    ("可爱", "可爱", ("可爱一点", "可爱风", "可爱")),
]

BRAND_INTENTS = [
    ("苹果", "苹果", ("Apple", "apple", "苹果")),
    ("耐克", "耐克", ("Nike", "nike", "耐克")),
    ("国产", "国产品牌", ("国产品牌", "国产")),
]

SCENARIO_INTENTS = [
    {
        "key": "rental_comfort",
        "label": "出租屋更舒服",
        "triggers": ("我的出租屋还能更舒服吗", "出租屋还能更舒服吗", "出租屋更舒服", "改善出租屋"),
        "targets": ("舒适睡眠", "氛围灯光", "小户型收纳", "幸福感软装"),
    },
    {
        "key": "concert",
        "label": "去看演唱会",
        "triggers": ("我要去看演唱会有什么推荐好物", "去看演唱会有什么推荐", "准备去看演唱会", "我要看演唱会"),
        "targets": ("续航补给", "轻装收纳", "户外防护", "观演体验"),
    },
    {
        "key": "camping",
        "label": "去露营",
        "triggers": ("准备去露营", "想去露营", "我要去露营", "周末去露营"),
        "targets": ("帐篷", "折叠椅", "露营灯", "驱蚊"),
    },
    {
        "key": "moving",
        "label": "搬家",
        "triggers": ("准备搬家", "我要搬家", "最近搬家"),
        "targets": ("搬家箱", "搬运车", "收纳", "工具箱"),
    },
    {
        "key": "cat",
        "label": "养猫",
        "triggers": ("准备养猫", "我要养猫", "刚养猫", "新手养猫"),
        "targets": ("猫粮", "猫砂", "猫抓板", "猫窝"),
    },
    {
        "key": "renovation",
        "label": "装修",
        "triggers": ("准备装修", "我要装修", "新家装修"),
        "targets": ("工具箱", "灯具", "装饰画", "收纳"),
    },
    {
        "key": "wedding",
        "label": "结婚",
        "triggers": ("准备结婚", "我要结婚", "婚礼要准备"),
        "targets": ("结婚礼物", "婚礼布置", "香水", "家居"),
    },
    {
        "key": "travel",
        "label": "旅行",
        "triggers": ("准备去旅行", "我要去旅行", "准备旅游", "我要旅游"),
        "targets": ("行李箱", "充电宝", "颈枕", "便携"),
    },
    {
        "key": "graduation",
        "label": "毕业",
        "triggers": ("我要毕业了", "准备毕业", "毕业季"),
        "targets": ("行李箱", "图书", "通勤", "充电宝"),
    },
    {
        "key": "hiking",
        "label": "徒步",
        "triggers": ("准备去徒步", "我想徒步", "我要徒步"),
        "targets": ("跑鞋", "水杯", "帐篷", "轻量"),
    },
    {
        "key": "fitness",
        "label": "健身",
        "triggers": ("给我推荐点健身好物", "推荐健身好物", "开始健身", "我想健身", "我要健身"),
        "targets": ("训练装备", "恢复放松", "补水营养", "数据记录"),
    },
    {
        "key": "cooking",
        "label": "做饭",
        "triggers": ("学着做饭", "我想做饭", "我要做饭"),
        "targets": ("锅具", "厨刀", "厨房", "咖啡机"),
    },
    {
        "key": "stay_home",
        "label": "宅家",
        "triggers": ("周末宅家", "我想宅家", "我要宅家"),
        "targets": ("投影仪", "毯子", "零食", "香薰"),
    },
    {
        "key": "music_festival",
        "label": "音乐节",
        "triggers": ("准备去音乐节", "我要去音乐节", "去看音乐节"),
        "targets": ("充电宝", "小风扇", "斜挎包", "防水"),
    },
    {
        "key": "bedroom",
        "label": "卧室更舒服",
        "triggers": ("卧室舒服一点", "卧室更舒服", "打造舒服卧室"),
        "targets": ("床品", "台灯", "香薰", "收纳"),
    },
    {
        "key": "living_room",
        "label": "客厅有氛围",
        "triggers": ("客厅更有氛围", "客厅有氛围", "提升客厅氛围"),
        "targets": ("地毯", "灯具", "装饰画", "香薰"),
    },
    {
        "key": "desk",
        "label": "桌面更整洁",
        "triggers": ("桌面更整洁", "整理一下桌面", "桌面太乱"),
        "targets": ("桌面收纳", "键盘", "文件架", "台灯"),
    },
    {
        "key": "balcony",
        "label": "阳台咖啡角",
        "triggers": ("阳台改造成咖啡角", "阳台咖啡角", "打造咖啡角"),
        "targets": ("咖啡机", "咖啡角", "水杯", "灯具"),
    },
    {
        "key": "work_efficiency",
        "label": "提高工作效率",
        "triggers": ("提高工作效率", "工作效率高一点", "办公更高效"),
        "targets": ("键盘", "桌面收纳", "耳机", "图书"),
    },
    {
        "key": "sleep",
        "label": "睡得更好",
        "triggers": ("想睡得更好", "睡得更好", "改善睡眠"),
        "targets": ("床品", "眼罩", "香薰", "台灯"),
    },
    {
        "key": "weight_loss",
        "label": "减肥",
        "triggers": ("我想减肥", "准备减肥", "开始减脂"),
        "targets": ("体脂秤", "瑜伽垫", "哑铃", "运动水杯"),
    },
    {
        "key": "english",
        "label": "学英语",
        "triggers": ("开始学英语", "我要学英语", "提升英语"),
        "targets": ("英语学习", "图书", "耳机", "文具"),
    },
    {
        "key": "happiness",
        "label": "提升幸福感",
        "triggers": ("提升幸福感", "生活更幸福", "提高幸福感"),
        "targets": ("鲜花", "香薰", "水杯", "家居"),
    },
]

EXPLORE_INTENTS = [
    {
        "key": "wow",
        "label": "发现眼前一亮的好物",
        "triggers": ("有没有让我眼前一亮的好物", "让我眼前一亮的好物", "眼前一亮的东西"),
    },
    {
        "key": "fresh",
        "label": "发现新鲜事物",
        "triggers": ("新鲜玩意", "新鲜东西", "没接触过", "不一样的", "随便逛", "探索一下"),
    },
    {
        "key": "trend",
        "label": "看看近期趋势",
        "triggers": ("最近流行什么", "最近有什么爆款", "大家最近都在买什么", "最近都在买"),
    },
    {
        "key": "style",
        "label": "探索适合的风格",
        "triggers": ("我适合什么风格", "是不是该换风格", "想换个风格"),
    },
    {
        "key": "inspiration",
        "label": "获得生活灵感",
        "triggers": (
            "有什么值得买",
            "可以买点什么",
            "买什么东西可以提升幸福感",
            "买了不会后悔",
            "提升幸福感的东西",
        ),
    },
    {
        "key": "upgrade",
        "label": "发现值得升级的物品",
        "triggers": ("有什么值得升级", "是不是该换点东西", "该升级什么"),
    },
    {
        "key": "future",
        "label": "预测可能缺少的物品",
        "triggers": ("最近可能还缺什么", "我还缺什么", "可能缺点什么"),
    },
]

DIRECT_PRODUCT_TERMS = tuple(
    term
    for _, _, aliases in COMMODITY_INTENTS
    for term in aliases
    if term not in {"露营", "户外", "办公", "穿搭", "家里", "收拾家", "宝宝"}
)

NEGATIVE_WORDS = (
    "不要", "不想", "不再", "先别", "别再", "别推", "别推荐",
    "别再推荐", "别给我推", "少点", "少看", "减少", "排除", "看腻", "烦",
)
GENERIC_TAXONOMY_ALIASES = {
    "其他", "其它", "配件", "耗材", "配件耗材", "其他类", "其它类",
    "周边", "服务", "用品", "套装", "护理", "治疗",
}
TAXONOMY_SPEECH_SYNONYMS = {
    "吹风机": "电吹风",
    "扫地机器人": "扫地机及配件耗材",
    "扫地机": "扫地机及配件耗材",
    "体脂秤": "体重秤/健康秤/体脂秤",
    "健康秤": "体重秤/健康秤/体脂秤",
    "水杯": "杯子/水杯/水壶",
    "杯子": "杯子/水杯/水壶",
    "奶粉": "婴童奶粉",
    "宝宝奶粉": "婴童奶粉",
    "口腔护理": "口腔治疗/护理",
    "蓝牙耳机": "无线耳机",
    "行李箱": "旅行箱",
    "拉杆箱": "旅行箱",
}


def normalize_taxonomy_text(value: str) -> str:
    return re.sub(r"[\s，。！？、,.!?“”\"'：:；;·\-—_]+", "", value).lower()


def taxonomy_aliases(name: str) -> set[str]:
    aliases = {normalize_taxonomy_text(name)}
    aliases.update(
        normalize_taxonomy_text(part)
        for part in re.split(r"[/／、|（）()]", name)
    )
    return {
        alias
        for alias in aliases
        if len(alias) >= 2 and alias not in GENERIC_TAXONOMY_ALIASES
    }


TAXONOMY_PARENT_NAMES = sorted(
    {item["xcat1"] for item in TAXONOMY_CATEGORIES},
    key=lambda value: (-len(value), value),
)
TAXONOMY_SECONDARY_BY_ALIAS: dict[str, list[dict[str, str]]] = {}
for category in TAXONOMY_CATEGORIES:
    for alias in taxonomy_aliases(category["xcat2"]):
        TAXONOMY_SECONDARY_BY_ALIAS.setdefault(alias, []).append(category)
for spoken_alias, xcat2 in TAXONOMY_SPEECH_SYNONYMS.items():
    for category in TAXONOMY_CATEGORIES:
        if category["xcat2"] == xcat2:
            TAXONOMY_SECONDARY_BY_ALIAS.setdefault(
                normalize_taxonomy_text(spoken_alias),
                [],
            ).append(category)
TAXONOMY_SECONDARY_ALIASES = sorted(
    TAXONOMY_SECONDARY_BY_ALIAS,
    key=lambda value: (-len(value), value),
)


def match_taxonomy_intent(text: str) -> dict[str, str] | None:
    normalized = normalize_taxonomy_text(text)
    matched_parent = next(
        (
            parent
            for parent in TAXONOMY_PARENT_NAMES
            if normalize_taxonomy_text(parent) in normalized
        ),
        None,
    )
    matched_alias = next(
        (alias for alias in TAXONOMY_SECONDARY_ALIASES if alias in normalized),
        None,
    )
    if matched_alias:
        candidates = TAXONOMY_SECONDARY_BY_ALIAS[matched_alias]
        if matched_parent:
            parent_candidate = next(
                (item for item in candidates if item["xcat1"] == matched_parent),
                None,
            )
            if parent_candidate:
                return {**parent_candidate, "evidence": matched_alias}
        return {**candidates[0], "evidence": matched_alias}
    if matched_parent:
        return {"xcat1": matched_parent, "xcat2": "", "evidence": matched_parent}
    return None


def extract_alias_slots(
    text: str,
    strength: str,
    definitions: list[tuple[str, str, tuple[str, ...]]],
    name: str,
) -> list[dict[str, Any]]:
    candidates: list[tuple[int, int, int, str, str, str]] = []
    for value, display, aliases in definitions:
        for alias in aliases:
            for match in re.finditer(re.escape(alias), text):
                candidates.append((len(alias), match.start(), match.end(), value, display, alias))

    selected: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    selected_values: set[str] = set()
    for _, start, end, value, display, _ in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if value in selected_values or any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        leading_clause = re.split(r"[，,。；;、]", text[:start])[-1]
        leading_context = leading_clause[-7:]
        trailing_context = text[end:min(len(text), end + 5)]
        negative = any(word in leading_context for word in NEGATIVE_WORDS) or any(
            word in trailing_context for word in ("看腻", "烦了", "太多")
        )
        operator = "neq" if negative else "eq"
        if name == "category":
            label = f"减少{display}" if negative else f"增加{display}"
        else:
            label = f"排除{display}" if negative else display
        selected.append(slot(name, operator, value, strength, label))
        occupied.append((start, end))
        selected_values.add(value)
    return selected


def match_intent_definition(text: str, definitions: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        (len(trigger), definition)
        for definition in definitions
        for trigger in definition["triggers"]
        if trigger.lower() in text.lower()
    ]
    return max(matches, key=lambda item: item[0])[1] if matches else None


def mode_payload(
    mode: str,
    *,
    confidence: float,
    evidence: list[str],
    route_name: str,
    route_label: str,
    route_summary: str,
) -> dict[str, Any]:
    labels = {
        "product": "商品意图",
        "scenario": "场景意图",
        "explore": "探索意图",
        "unknown": "待澄清意图",
    }
    return {
        "mode": mode,
        "modeLabel": labels[mode],
        "confidence": confidence,
        "evidence": evidence,
        "route": {
            "name": route_name,
            "label": route_label,
            "summary": route_summary,
        },
    }


def parse_intent_with_rules(transcript: str) -> dict[str, Any]:
    text = re.sub(r"\s+", "", transcript.strip())
    hard = any(word in text for word in ("必须", "只要", "只看", "不超过", "以内", "一定要"))
    strength = "hard" if hard else "soft"

    taxonomy_match = match_taxonomy_intent(text)
    taxonomy_slots: list[dict[str, Any]] = []
    catalog_slots = extract_alias_slots(text, strength, COMMODITY_INTENTS, "category")
    specific_catalog_values = {
        item["value"]
        for item in catalog_slots
        if item["value"] not in {"家居", "母婴"}
    }
    if specific_catalog_values:
        if "家里" in text and "家居" not in text:
            catalog_slots = [item for item in catalog_slots if item["value"] != "家居"]
        if "宝宝" in text and not any(term in text for term in ("宝宝用品", "母婴")):
            catalog_slots = [item for item in catalog_slots if item["value"] != "母婴"]
    attribute_slots = extract_alias_slots(text, strength, ATTRIBUTE_INTENTS, "attribute")
    audience_slots = extract_alias_slots(text, strength, AUDIENCE_INTENTS, "audience")
    style_slots = extract_alias_slots(text, strength, STYLE_INTENTS, "style")
    brand_slots = extract_alias_slots(text, strength, BRAND_INTENTS, "brand")
    positive_catalog_slots = [
        item for item in catalog_slots if item["operator"] == "eq"
    ]
    broad_catalog_values = {
        "家居", "户外", "办公", "穿搭", "食品", "宠物", "母婴",
        "数码", "家电", "女装",
    }
    taxonomy_active = bool(taxonomy_match)
    if taxonomy_match and taxonomy_match["xcat2"] and catalog_slots:
        normalized_xcat2 = normalize_taxonomy_text(taxonomy_match["xcat2"])
        compatible_values = [
            item["value"]
            for item in positive_catalog_slots
            if (
                normalize_taxonomy_text(str(item["value"])) in normalized_xcat2
                or normalized_xcat2 in normalize_taxonomy_text(str(item["value"]))
                or normalize_taxonomy_text(str(item["value"]))
                == normalize_taxonomy_text(taxonomy_match["evidence"])
            )
        ]
        taxonomy_active = (
            len(positive_catalog_slots) == 1
            and not any(item["operator"] == "neq" for item in catalog_slots)
            and bool(compatible_values)
            and compatible_values[0] not in broad_catalog_values
            and not brand_slots
        )
    if taxonomy_match and taxonomy_active:
        evidence = normalize_taxonomy_text(taxonomy_match["evidence"])
        normalized_text = normalize_taxonomy_text(text)
        taxonomy_negative = any(
            normalize_taxonomy_text(f"{word}{evidence}") in normalized_text
            for word in NEGATIVE_WORDS
        )
        taxonomy_operator = "neq" if taxonomy_negative else "eq"
        taxonomy_slots.append(
            slot(
                "xcat1",
                "eq" if taxonomy_match["xcat2"] else taxonomy_operator,
                taxonomy_match["xcat1"],
                strength,
                taxonomy_match["xcat1"],
            )
        )
        if taxonomy_match["xcat2"]:
            taxonomy_slots.append(
                slot(
                    "xcat2",
                    taxonomy_operator,
                    taxonomy_match["xcat2"],
                    strength,
                    (
                        f"减少{taxonomy_match['xcat2']}"
                        if taxonomy_negative
                        else taxonomy_match["xcat2"]
                    ),
                )
            )
    product_slots = (
        catalog_slots
        + attribute_slots
        + audience_slots
        + style_slots
        + brand_slots
        + taxonomy_slots
    )

    explicit_direct_product_terms = {
        term for term in DIRECT_PRODUCT_TERMS if term.lower() in text.lower()
    }
    direct_product_terms = sorted(
        {
            *explicit_direct_product_terms,
            *(
                {taxonomy_match["evidence"]}
                if taxonomy_match and taxonomy_active and taxonomy_match["xcat2"]
                else set()
            ),
        },
        key=len,
        reverse=True,
    )
    explore_definition = match_intent_definition(text, EXPLORE_INTENTS)
    scenario_definition = match_intent_definition(text, SCENARIO_INTENTS)

    if explore_definition and not explicit_direct_product_terms:
        explore_slot = slot("attribute", "eq", "新鲜感", "soft", explore_definition["label"])
        explore_slot.update({"sourceMode": "explore", "sourceKey": explore_definition["key"]})
        return {
            "type": "explore",
            "polarity": "neutral",
            "slots": [explore_slot],
            "scope": "session",
            "transcript": transcript,
            "exploreTheme": explore_definition["key"],
            **mode_payload(
                "explore",
                confidence=0.94,
                evidence=[trigger for trigger in explore_definition["triggers"] if trigger in text][:2],
                route_name="inspiration_discovery",
                route_label="灵感启发推荐",
                route_summary=f"围绕“{explore_definition['label']}”增加新鲜度、趋势性与跨品类多样性",
            ),
        }

    if scenario_definition and not explicit_direct_product_terms:
        scenario_slots = []
        for target in scenario_definition["targets"]:
            target_slot = slot("category", "eq", target, "soft", target)
            target_slot.update({"sourceMode": "scenario", "sourceKey": scenario_definition["key"]})
            scenario_slots.append(target_slot)
        return {
            "type": "pull",
            "polarity": "positive",
            "slots": scenario_slots,
            "scope": "session",
            "transcript": transcript,
            "scenario": {
                "key": scenario_definition["key"],
                "label": scenario_definition["label"],
                "targets": list(scenario_definition["targets"]),
            },
            **mode_payload(
                "scenario",
                confidence=0.96,
                evidence=[trigger for trigger in scenario_definition["triggers"] if trigger in text][:2],
                route_name="scenario_bundle",
                route_label="场景商品组合",
                route_summary=f"把“{scenario_definition['label']}”拆成 {'、'.join(scenario_definition['targets'])}",
            ),
        }

    slots = list(product_slots)
    intent_type = "pull"
    polarity = "positive"
    if any(item["operator"] == "neq" for item in product_slots):
        intent_type = "exclude"
        polarity = "negative"

    remove_height = any(phrase in text for phrase in ("不要增高", "不想增高", "取消增高"))
    if remove_height:
        intent_type = "correct"
        polarity = "negative"
        slots.append(slot("attribute", "neq", "增高", "hard", "排除增高"))
    elif "增高" in text:
        slots.append(slot("attribute", "eq", "增高", strength, "增高"))

    if "不是女" in text or "不要女" in text:
        intent_type = "correct"
        slots.append(slot("attribute", "neq", "女款", "hard", "排除女款"))
    if "男款" in text or "男生" in text or "是男" in text:
        if "不是女" in text:
            intent_type = "correct"
        slots.append(slot("attribute", "eq", "男款", strength, "男款"))

    price_match = re.search(r"(\d{2,5})元?(?:以内|以下|之内|以内的|以下的)", text)
    if price_match:
        value = int(price_match.group(1))
        slots.append(slot("price", "lte", value, "hard", f"≤¥{value}"))
    if any(phrase in text for phrase in ("便宜一点", "更便宜", "价格低一点")):
        slots.append(slot("priceOrder", "eq", "lower", "soft", "更便宜"))
    if any(phrase in text for phrase in ("贵一点", "更贵", "预算高一点")):
        slots.append(slot("priceOrder", "eq", "higher", "soft", "预算更高"))

    if slots:
        evidence = direct_product_terms[:2]
        evidence.extend(item["label"] for item in slots if item["label"] not in evidence)
        return {
            "type": intent_type,
            "polarity": polarity,
            "slots": slots,
            "scope": "session",
            "transcript": transcript,
            **(
                {
                    "taxonomy": {
                        "xcat1": taxonomy_match["xcat1"],
                        "xcat2": taxonomy_match["xcat2"] or None,
                    }
                }
                if taxonomy_match and taxonomy_active
                else {}
            ),
            **mode_payload(
                "product",
                confidence=0.96 if taxonomy_match else 0.92 if catalog_slots else 0.84,
                evidence=evidence[:4],
                route_name="constraint_ranking",
                route_label="商品约束排序",
                route_summary="按类目、属性、人群、风格、品牌和预算约束进行筛选与排序",
            ),
        }

    return {
        "type": "unknown",
        "polarity": "neutral",
        "slots": [],
        "scope": "session",
        "transcript": transcript,
        **mode_payload(
            "unknown",
            confidence=0.25,
            evidence=[],
            route_name="clarification",
            route_label="等待补充",
            route_summary="请补充商品、生活场景，或直接说想探索什么",
        ),
    }


class IntentAPIError(RuntimeError):
    pass


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def intent_api_enabled() -> bool:
    engine = os.environ.get("INTENT_ENGINE", "auto").strip().lower()
    if engine not in ("auto", "api", "rules"):
        raise IntentAPIError("INTENT_ENGINE 只能是 auto、api 或 rules")
    if engine == "rules":
        return False
    config_values = {
        "INTENT_API_KEY": first_env("INTENT_API_KEY", "WHALE_API_KEY"),
        "INTENT_API_MODEL": first_env("INTENT_API_MODEL", "WHALE_API_MODEL"),
    }
    missing = [name for name, value in config_values.items() if not value]
    if not missing:
        return True
    if engine == "api" or len(missing) != len(config_values):
        raise IntentAPIError(f"API 意图识别配置不完整，缺少：{', '.join(missing)}")
    return False


def category_selection_candidates(transcript: str) -> list[dict[str, str]]:
    """Build a compact, request-specific list containing only real catalog categories."""
    normalized = normalize_taxonomy_text(transcript)
    synonym_targets = {
        target
        for spoken, target in TAXONOMY_SPEECH_SYNONYMS.items()
        if normalize_taxonomy_text(spoken) in normalized
    }
    secondary_matches: list[tuple[int, dict[str, str]]] = []
    for category in TAXONOMY_CATEGORIES:
        contained = [
            alias for alias in taxonomy_aliases(category["xcat2"])
            if alias in normalized
        ]
        score = max((100 + len(alias) for alias in contained), default=0)
        if category["xcat2"] in synonym_targets:
            score = max(score, 130)
        if score:
            secondary_matches.append((score, category))

    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(level: str, name: str, parent: str = "") -> None:
        key = (level, parent, name)
        if key in seen:
            return
        candidates.append({
            "id": f"c{len(candidates) + 1:03d}",
            "level": level,
            "name": name,
            "parent": parent,
        })
        seen.add(key)

    for _, category in sorted(
        secondary_matches,
        key=lambda item: (-item[0], item[1]["xcat1"], item[1]["xcat2"]),
    )[:24]:
        add("xcat2", category["xcat2"], category["xcat1"])
    non_physical_parents = {
        "人工智能服务", "医疗及健康服务", "教育培训", "数字生活",
        "景点门票/演艺演出/周边游", "电影/演出/体育赛事",
        "本地化生活服务", "商务/设计服务", "个性定制/设计服务/DIY",
    }
    for parent in sorted(TAXONOMY_PARENT_NAMES):
        if parent in non_physical_parents:
            continue
        add("xcat1", parent)
    return candidates


def intent_system_prompt(_candidates: list[dict[str, str]] | None = None) -> str:
    """Return the exact, product-owned prompt used for Whale classification."""
    return CATEGORY_INTENT_SYSTEM_PROMPT


def prompt_allowed_categories() -> tuple[str, ...]:
    """Read the allowlist from the prompt so validation cannot drift from it."""
    marker = "# 允许品类列表\n"
    examples_marker = "\n# 示例1"
    if marker not in CATEGORY_INTENT_SYSTEM_PROMPT:
        raise RuntimeError("品类识别 system prompt 缺少允许品类列表")
    body = CATEGORY_INTENT_SYSTEM_PROMPT.split(marker, 1)[1]
    body = body.split(examples_marker, 1)[0]
    return tuple(line.strip() for line in body.splitlines() if line.strip())


ALLOWED_INTENT_CATEGORIES = prompt_allowed_categories()
ALLOWED_INTENT_CATEGORY_SET = frozenset(ALLOWED_INTENT_CATEGORIES)
MAX_INTENT_CATEGORIES = 8


def api_category_candidates() -> list[dict[str, str]]:
    """Build stable candidates from the prompt allowlist and the real taxonomy."""
    parents_by_name: dict[str, set[str]] = {}
    for item in TAXONOMY_CATEGORIES:
        parents_by_name.setdefault(item["xcat2"], set()).add(item["xcat1"])

    candidates: list[dict[str, str]] = []
    for name in ALLOWED_INTENT_CATEGORIES:
        parents = parents_by_name.get(name)
        if not parents:
            continue
        candidates.append({
            "id": f"c{len(candidates) + 1:03d}",
            "level": "xcat2",
            "name": name,
            "parent": sorted(parents)[0],
        })
    for parent in sorted(TAXONOMY_PARENT_NAMES):
        candidates.append({
            "id": f"c{len(candidates) + 1:03d}",
            "level": "xcat1",
            "name": parent,
            "parent": "",
        })
    return candidates


CATEGORY_GROUPS = [
    ("g1", "服装鞋履", "衣服、鞋、内衣、运动服"),
    ("g2", "数码影音", "手机、电脑、耳机、相机、数码配件"),
    ("g3", "家居生活", "床品、收纳、清洁、厨房、家电、日用品"),
    ("g4", "美妆健康", "护肤、彩妆、个护、保健用品"),
    ("g5", "食品饮料", "零食、生鲜、粮油、茶酒、冲饮"),
    ("g6", "母婴儿童", "婴童用品、童装童鞋、玩具"),
    ("g7", "户外运动", "旅行用品、露营、健身、骑行、户外装备"),
    ("g8", "学习办公", "书籍、文具、学习设备、办公用品"),
    ("g9", "宠物园艺礼品", "宠物、鲜花、园艺、节庆礼品"),
    ("g10", "汽车交通", "汽车、摩托车、电动车及配件"),
    ("g11", "箱包出行", "背包、旅行箱、行李箱、户外包"),
    ("g12", "首饰配件", "首饰、黄金、手表、眼镜、帽子围巾"),
]

CATEGORY_GROUP_KEYWORDS = {
    "g11": ("箱包", "运动包"),
    "g12": ("珠宝", "饰品", "黄金", "眼镜", "手表", "服饰配件"),
    "g1": ("女装", "男装", "内衣", "女鞋", "男鞋", "童装", "童鞋", "运动鞋", "运动服", "纺织面料"),
    "g2": ("3C", "DIY电脑", "二手数码", "台机", "数码相机", "智能设备", "影音", "电玩", "电脑硬件", "网络设备", "闪存卡"),
    "g3": ("家具", "全屋", "厨房", "大家电", "家居", "家装", "居家", "床上", "清洁", "生活电器", "收纳", "餐饮具", "建材", "搬运", "包装"),
    "g4": ("药", "保健", "个人护理", "彩妆", "美发", "护肤", "美容", "隐形眼镜", "滋补"),
    "g5": ("食品", "粮油", "咖啡", "水产", "零食", "茶", "酒"),
    "g6": ("婴童", "孕妇", "童装", "童鞋", "玩具", "积木", "玩偶"),
    "g7": ("户外", "运动", "自行车", "骑行"),
    "g8": ("书籍", "办公", "文具", "教育学习", "乐器"),
    "g9": ("宠物", "园艺", "鲜花", "节庆", "礼品"),
    "g10": ("汽车", "摩托车", "电动车", "交通工具", "零部件"),
}

CATEGORY_DELTA_TAXONOMY_HINTS = {
    # Broad spoken concepts need a small semantic guardrail because the
    # available recall model can otherwise confuse clothing with outdoor gear.
    # Every value is an existing first-level category from the live catalog.
    "穿搭": ("女装/女士精品", "男装"),
    "女装": ("女装/女士精品",),
    "护肤": ("美容护肤/美体/精油",),
    "美妆": ("彩妆/香水/美妆工具",),
    "家居": ("居家日用", "住宅家具"),
    "户外": ("户外/登山/野营/旅行用品",),
    "办公": ("文具用品/文化用品/商务用品", "办公设备/耗材/相关服务"),
    "食品": ("零食/坚果/特产",),
    "宠物": ("宠物/宠物食品及用品",),
    "母婴": ("婴童用品", "婴童奶粉"),
    "数码": ("3C数码配件", "手机"),
    "家电": ("生活电器", "厨房电器"),
}


def category_group_for(parent: str) -> str:
    for group_id, keywords in CATEGORY_GROUP_KEYWORDS.items():
        if any(keyword in parent for keyword in keywords):
            return group_id
    return "g3"


def category_group_scoring_prompt(transcript: str) -> str:
    lines = "\n".join(
        f"{group_id}|{label}（{description}）"
        for group_id, label, description in CATEGORY_GROUPS
    )
    return f"""用户购物需求：{transcript}
请分别判断每个现有商品范围能否直接帮助用户完成这个需求。
0 完全无关，1 仅泛泛相关或非必需，2 有帮助，3 最直接有帮助。
不要因为任何人都可能买某类商品就给高分。每项独立判断。
只输出 JSON 对象，键是范围编号，值只能是 0 到 3。
{lines}"""


def extract_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        value = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in value
        )
    if not isinstance(value, str):
        raise IntentAPIError("模型响应中没有可解析的 JSON")
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise IntentAPIError("模型没有返回 JSON 对象")
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise IntentAPIError("模型返回的 JSON 格式不合法") from exc
    if not isinstance(parsed, dict):
        raise IntentAPIError("模型返回值必须是 JSON 对象")
    return parsed


def extract_intent_api_payload(response: dict[str, Any]) -> dict[str, Any]:
    error_code = response.get("error_code")
    if error_code not in (None, 0, "0", 200, "200"):
        message = str(response.get("message") or "未知错误").strip()
        raise IntentAPIError(f"Whale 返回错误 {error_code}：{message}")
    if "mode" in response or "intent" in response:
        return extract_json_object(response.get("intent", response))
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message", {})
            if isinstance(message, dict) and "content" in message:
                return extract_json_object(message["content"])
            if "text" in choice:
                return extract_json_object(choice["text"])
    output = response.get("output")
    if isinstance(output, dict):
        return extract_intent_api_payload(output)
    raise IntentAPIError("无法从模型响应中找到意图结果")


def default_slot_label(name: str, operator: str, value: Any) -> str:
    if name == "price":
        symbol = "≤" if operator == "lte" else "≥"
        return f"{symbol}¥{value}"
    if name == "priceOrder":
        return "更便宜" if value == "lower" else "预算更高"
    if operator == "neq":
        return f"减少{value}" if name == "category" else f"排除{value}"
    return f"增加{value}" if name == "category" else str(value)


def normalize_api_slots(raw_slots: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_slots, list):
        raise IntentAPIError("模型返回的 slots 必须是数组")
    allowed_names = {
        "category", "xcat1", "xcat2", "attribute", "audience", "style",
        "brand", "price", "priceOrder",
    }
    allowed_xcat1 = set(TAXONOMY_PARENT_NAMES)
    allowed_xcat2 = {item["xcat2"] for item in TAXONOMY_CATEGORIES}
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in raw_slots[:24]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        operator = str(raw.get("operator", "eq")).strip().lower()
        value = raw.get("value")
        strength = str(raw.get("strength", "soft")).strip().lower()
        if name not in allowed_names or strength not in ("hard", "soft"):
            continue
        valid_operators = {"lte", "gte"} if name == "price" else {"eq"} if name == "priceOrder" else {"eq", "neq"}
        if operator not in valid_operators:
            continue
        if name == "price":
            if isinstance(value, str):
                match = re.search(r"\d+(?:\.\d+)?", value)
                value = float(match.group()) if match else None
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                continue
            value = int(value) if float(value).is_integer() else float(value)
        else:
            if not isinstance(value, str) or not value.strip():
                continue
            value = value.strip()
        if name == "priceOrder" and value not in ("lower", "higher"):
            continue
        if name == "xcat1" and value not in allowed_xcat1:
            continue
        if name == "xcat2" and value not in allowed_xcat2:
            continue
        dedupe_key = (name, operator, str(value))
        if dedupe_key in seen:
            continue
        item = slot(
            name,
            operator,
            value,
            strength,
            str(raw.get("label") or default_slot_label(name, operator, value))[:40],
        )
        source_mode = raw.get("sourceMode")
        source_key = raw.get("sourceKey")
        if source_mode in ("scenario", "explore"):
            item["sourceMode"] = source_mode
            if isinstance(source_key, str) and source_key.strip():
                item["sourceKey"] = source_key.strip()[:40]
        normalized.append(item)
        seen.add(dedupe_key)
    return normalized


def recover_explicit_product_category(transcript: str) -> dict[str, Any] | None:
    """Recover an explicit catalog noun only when the API omitted its category slot."""
    matches: list[tuple[int, str, str]] = []
    for value, display, aliases in COMMODITY_INTENTS:
        for alias in aliases:
            if alias in transcript:
                matches.append((len(alias), value, display))
    if not matches:
        return None
    _, value, display = max(matches)
    return slot("category", "eq", value, "hard", display)


def normalize_api_intent(
    raw: dict[str, Any],
    transcript: str,
    candidates: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    candidates = candidates or category_selection_candidates(transcript)
    candidate_by_id = {item["id"]: item for item in candidates}

    def selected(field: str, operator: str) -> list[dict[str, Any]]:
        values = raw.get(field, [])
        if not isinstance(values, list):
            values = []
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for candidate_id in values[:5]:
            candidate = candidate_by_id.get(str(candidate_id).strip())
            if not candidate:
                continue
            key = (candidate["level"], candidate["name"])
            if key in seen:
                continue
            label = candidate["name"] if operator == "eq" else f"少看{candidate['name']}"
            result.append(slot(candidate["level"], operator, candidate["name"], "soft", label))
            seen.add(key)
        return result

    include_slots = selected("include_ids", "eq")
    exclude_slots = selected("exclude_ids", "neq")
    selection_fallback = not include_slots and not exclude_slots
    if selection_fallback:
        fallback_pool = [item for item in candidates if item["level"] == "xcat1"]
        fallback_count = min(len(fallback_pool), random.SystemRandom().randint(2, 4))
        fallback = random.SystemRandom().sample(fallback_pool, fallback_count)
        include_slots = [
            {
                **slot(item["level"], "eq", item["name"], "soft", item["name"]),
                "hidden": True,
            }
            for item in fallback
        ]
    slots = include_slots + exclude_slots

    for field, operator in (("price_lte", "lte"), ("price_gte", "gte")):
        value = raw.get(field)
        if isinstance(value, str):
            match = re.search(r"\d+(?:\.\d+)?", value)
            value = float(match.group()) if match else None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            value = int(value) if float(value).is_integer() else float(value)
            slots.append(slot("price", operator, value, "hard", default_slot_label("price", operator, value)))

    names = [item["value"] for item in include_slots]
    excluded_names = [item["value"] for item in exclude_slots]
    result = {
        "type": "exclude" if exclude_slots and not include_slots else "pull",
        "polarity": "mixed" if include_slots and exclude_slots else "negative" if exclude_slots else "positive",
        "slots": slots,
        "scope": "session",
        "transcript": transcript,
        "selectedCategories": names,
        "excludedCategories": excluded_names,
        "selectionFallback": selection_fallback,
        **mode_payload(
            "product",
            confidence=0.35 if selection_fallback else 0.9,
            evidence=[transcript[:40]],
            route_name="category_selection",
            route_label="相关商品",
            route_summary=f"优先推荐：{'、'.join(names)}",
        ),
    }
    if len(include_slots) == 1 and not exclude_slots:
        only = include_slots[0]
        if only["name"] == "xcat1":
            result["taxonomy"] = {"xcat1": only["value"], "xcat2": None}
        elif only["name"] == "xcat2":
            candidate = next(
                item for item in candidates
                if item["level"] == "xcat2" and item["name"] == only["value"]
            )
            result["taxonomy"] = {"xcat1": candidate["parent"], "xcat2": only["value"]}
    return result


def call_whale_chat(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    timeout: float,
    base_url: str | None,
) -> Any:
    """Call the official Whale SDK using its OpenAI-compatible protocol."""
    try:
        from whale import TextGeneration
    except ImportError as exc:
        raise IntentAPIError(
            "缺少 whale-sdk，请先执行 .venv/bin/pip install -r requirements.txt"
        ) from exc

    if base_url:
        disable_unused_whale_discovery()

    signature = (api_key, base_url or "")
    global _WHALE_CONFIG_SIGNATURE
    if _WHALE_CONFIG_SIGNATURE != signature:
        with _WHALE_CONFIG_LOCK:
            if _WHALE_CONFIG_SIGNATURE != signature:
                if base_url:
                    TextGeneration.set_api_key(api_key, base_url=base_url)
                else:
                    TextGeneration.set_api_key(api_key)
                _WHALE_CONFIG_SIGNATURE = signature

    return TextGeneration.chat(
        model=model,
        messages=messages,
        stream=False,
        temperature=0,
        max_tokens=300,
        timeout=timeout,
    )


def disable_unused_whale_discovery() -> None:
    """Stop SDK discovery refreshes when a direct Whale base URL is configured."""
    try:
        from vipserver.vip_client import global_vip_client

        reactor = global_vip_client.host_reactor
        reactor.update_domain_thread.stop_flag = True
        reactor.proxy.update_srv_thread.stop_flag = True
    except Exception:
        # Discovery is an SDK implementation detail and must never break inference.
        pass


def warm_whale_sdk() -> None:
    """Load and configure Whale in the background so the first user call stays fast."""
    if not intent_api_enabled():
        return
    api_key = first_env("INTENT_API_KEY", "WHALE_API_KEY")
    model = first_env("INTENT_API_MODEL", "WHALE_API_MODEL")
    base_url = first_env("INTENT_API_URL", "WHALE_API_URL")
    if not api_key or not model:
        return
    try:
        from whale import TextGeneration

        if base_url:
            disable_unused_whale_discovery()
        global _WHALE_CONFIG_SIGNATURE
        signature = (api_key, base_url or "")
        with _WHALE_CONFIG_LOCK:
            if _WHALE_CONFIG_SIGNATURE != signature:
                if base_url:
                    TextGeneration.set_api_key(api_key, base_url=base_url)
                else:
                    TextGeneration.set_api_key(api_key)
                _WHALE_CONFIG_SIGNATURE = signature
    except Exception:
        # The real request still reports a useful error if warmup could not finish.
        return


def extract_whale_intent_payload(response: Any) -> dict[str, Any]:
    def field(name: str, default: Any = None) -> Any:
        if isinstance(response, dict):
            return response.get(name, default)
        return getattr(response, name, default)

    def safe_message(value: Any) -> str:
        message = str(value or "未知错误")
        # Whale's 403 message may echo the API key. Never pass that secret to the UI.
        return re.sub(r"(?i)(api[_ ]?key\s*=\s*)[^,\s]+", r"\1***", message)

    error_code = field("error_code")
    if error_code not in (None, 0, "0", 200, "200"):
        raise IntentAPIError(f"Whale 返回错误 {error_code}：{safe_message(field('message'))}")

    if isinstance(response, dict):
        return extract_intent_api_payload(response)
    status_code = field("status_code")
    if status_code not in (None, 0, 200, "200"):
        status_message = safe_message(field("status_message"))
        raise IntentAPIError(f"Whale 返回错误 {status_code}：{status_message}")
    choices = field("choices")
    if not isinstance(choices, (list, tuple)) or not choices:
        raise IntentAPIError("Whale 响应中没有 choices")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    return extract_json_object(content)


def call_category_selector(
    transcript: str,
    *,
    api_key: str,
    model: str,
    timeout: float,
    base_url: str,
) -> dict[str, Any]:
    response = call_whale_chat(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": CATEGORY_INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        timeout=timeout,
        base_url=base_url or None,
    )
    return extract_whale_intent_payload(response)


def select_category_ids_with_api(
    transcript: str,
    candidates: list[dict[str, str]],
    *,
    api_key: str,
    model: str,
    timeout: float,
    base_url: str,
) -> list[str]:
    raw = call_category_selector(
        transcript,
        api_key=api_key,
        model=model,
        timeout=timeout,
        base_url=base_url,
    )
    categories = raw.get("categories")
    if not isinstance(categories, list):
        return []
    candidate_id_by_name = {
        item["name"]: item["id"]
        for item in candidates
        if item["level"] == "xcat2"
    }
    selected_ids: list[str] = []
    for value in categories:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name not in ALLOWED_INTENT_CATEGORY_SET:
            continue
        candidate_id = candidate_id_by_name.get(name)
        if candidate_id and candidate_id not in selected_ids:
            selected_ids.append(candidate_id)
        if len(selected_ids) >= MAX_INTENT_CATEGORIES:
            break
    return selected_ids


def category_delta_slots(intent: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit category additions/removals found in this utterance."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in intent.get("slots", []):
        if item.get("name") not in ("category", "xcat1", "xcat2"):
            continue
        operator = item.get("operator")
        value = item.get("value")
        if operator not in ("eq", "neq") or not isinstance(value, str) or not value.strip():
            continue
        key = (operator, value.strip())
        if key in seen:
            continue
        result.append({"operator": operator, "query": value.strip()})
        seen.add(key)
    return result


def apply_category_delta_polarity(
    candidates: list[dict[str, str]],
    raw: dict[str, list[str]],
    delta_slots: list[dict[str, Any]],
) -> None:
    """Apply explicit add/remove wording without making another model call."""
    negative = [item for item in delta_slots if item["operator"] == "neq"]
    if not negative:
        return

    negative_parents = {
        parent
        for item in negative
        for parent in CATEGORY_DELTA_TAXONOMY_HINTS.get(item["query"], ())
    }
    candidate_by_id = {item["id"]: item for item in candidates}

    for candidate_id in list(raw["include_ids"]):
        candidate = candidate_by_id.get(candidate_id)
        if not candidate:
            continue
        belongs_to_negative = (
            candidate["level"] == "xcat2"
            and candidate["parent"] in negative_parents
        )
        if belongs_to_negative:
            raw["include_ids"].remove(candidate_id)
            if candidate_id not in raw["exclude_ids"]:
                raw["exclude_ids"].append(candidate_id)

    def add_candidate(level: str, name: str, parent: str = "") -> str:
        for candidate in candidates:
            if (
                candidate["level"] == level
                and candidate["name"] == name
                and candidate["parent"] == parent
            ):
                return candidate["id"]
        candidate_id = f"c{len(candidates) + 1:03d}"
        candidates.append({
            "id": candidate_id,
            "level": level,
            "name": name,
            "parent": parent,
        })
        return candidate_id

    for item in negative:
        query = item["query"]
        hinted_parents = CATEGORY_DELTA_TAXONOMY_HINTS.get(query, ())
        if hinted_parents:
            for parent in hinted_parents:
                if parent not in TAXONOMY_PARENT_NAMES:
                    continue
                candidate_id = add_candidate("xcat1", parent)
                if candidate_id not in raw["exclude_ids"]:
                    raw["exclude_ids"].append(candidate_id)
            continue
        matches = [
            candidate
            for candidate in category_selection_candidates(query)
            if candidate["level"] == "xcat2"
        ]
        for match in matches[:5]:
            candidate_id = add_candidate("xcat2", match["name"], match["parent"])
            if candidate_id in raw["include_ids"]:
                raw["include_ids"].remove(candidate_id)
            if candidate_id not in raw["exclude_ids"]:
                raw["exclude_ids"].append(candidate_id)


def parse_intent_with_api(transcript: str) -> dict[str, Any]:
    api_key = first_env("INTENT_API_KEY", "WHALE_API_KEY")
    model = first_env("INTENT_API_MODEL", "WHALE_API_MODEL")
    base_url = first_env("INTENT_API_URL", "WHALE_API_URL")
    if not api_key or not model:
        raise IntentAPIError("Whale OpenAI 协议需要配置 API Key 和 model")
    try:
        timeout = float(os.environ.get("INTENT_API_TIMEOUT", "20"))
    except ValueError as exc:
        raise IntentAPIError("INTENT_API_TIMEOUT 必须是数字") from exc
    rule_intent = parse_intent_with_rules(transcript)
    delta_slots = category_delta_slots(rule_intent)
    try:
        candidates = api_category_candidates()
        selected_ids = select_category_ids_with_api(
            transcript,
            candidates,
            api_key=api_key,
            model=model,
            timeout=timeout,
            base_url=base_url,
        )
        raw = {"include_ids": selected_ids, "exclude_ids": []}
        apply_category_delta_polarity(candidates, raw, delta_slots)
    except IntentAPIError:
        raise
    except Exception as exc:
        detail = str(exc).replace(api_key, "***")[:300]
        raise IntentAPIError(f"Whale 意图识别调用失败：{detail}") from exc
    rule_slots = rule_intent.get("slots", [])
    for condition in rule_slots:
        if condition["name"] != "price":
            continue
        raw["price_lte" if condition["operator"] == "lte" else "price_gte"] = condition["value"]
    return normalize_api_intent(raw, transcript, candidates)


def parse_intent(transcript: str) -> dict[str, Any]:
    if intent_api_enabled():
        return parse_intent_with_api(transcript)
    return parse_intent_with_rules(transcript)


def condition_key(condition: dict[str, Any]) -> tuple[str, Any]:
    return condition["name"], condition["value"]


def taxonomy_conditions_related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    taxonomy_names = {"category", "xcat1", "xcat2"}
    if left.get("name") not in taxonomy_names or right.get("name") not in taxonomy_names:
        return False
    left_value = str(left.get("value", ""))
    right_value = str(right.get("value", ""))
    if normalize_taxonomy_text(left_value) == normalize_taxonomy_text(right_value):
        return True
    xcat2_parents = {item["xcat2"]: item["xcat1"] for item in TAXONOMY_CATEGORIES}
    if left.get("name") == "xcat1" and right.get("name") == "xcat2":
        return xcat2_parents.get(right_value) == left_value
    if left.get("name") == "xcat2" and right.get("name") == "xcat1":
        return xcat2_parents.get(left_value) == right_value
    if "category" in (left.get("name"), right.get("name")):
        left_normalized = normalize_taxonomy_text(left_value)
        right_normalized = normalize_taxonomy_text(right_value)
        return (
            len(left_normalized) >= 2
            and len(right_normalized) >= 2
            and (left_normalized in right_normalized or right_normalized in left_normalized)
        )
    return False


def merge_conditions(existing: list[dict[str, Any]], intent: dict[str, Any]) -> list[dict[str, Any]]:
    # Random fallback slots only drive the current feed. They are not user
    # preferences, so replace them on every turn instead of accumulating them.
    merged = [dict(item) for item in existing if not item.get("hidden")]
    incoming_slots = intent.get("slots", [])
    for incoming in incoming_slots:
        opposite = "neq" if incoming["operator"] == "eq" else "eq" if incoming["operator"] == "neq" else None
        merged = [
            item
            for item in merged
            if condition_key(item) != condition_key(incoming)
            and not (
                opposite
                and item["operator"] == opposite
                and taxonomy_conditions_related(item, incoming)
            )
        ]
        merged.append(dict(incoming))
    return merged


def visible_session_conditions(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only user-backed conditions are allowed to reach visible client state."""
    return [dict(item) for item in conditions if not item.get("hidden")]


def product_contains_value(product_item: dict[str, Any], value: Any) -> bool:
    normalized_value = normalize_taxonomy_text(value) if isinstance(value, str) else ""
    attribute_match = value in product_item["attributes"]
    if (
        product_item["id"].startswith("tax-")
        and normalized_value
        and len(normalized_value) >= 2
    ):
        attribute_match = attribute_match or any(
            normalized_value in normalize_taxonomy_text(attribute)
            for attribute in product_item["attributes"]
            if isinstance(attribute, str)
        )
    return (
        product_item["category"] == value
        or attribute_match
        or value in product_item["audiences"]
        or value in product_item["styles"]
        or value in product_item["goals"]
        or product_item["brand"] == value
        or product_item["origin"] == value
    )


def product_matches(product_item: dict[str, Any], condition: dict[str, Any]) -> bool:
    name, operator, value = condition["name"], condition["operator"], condition["value"]
    if name == "price":
        return product_item["price"] <= value if operator == "lte" else product_item["price"] >= value
    if name == "priceOrder":
        return True
    if name == "xcat1":
        present = product_item.get("xcat1") == value
    elif name == "xcat2":
        present = product_item.get("xcat2") == value
    elif name == "category":
        present = product_contains_value(product_item, value)
        if value == "家居":
            present = present or product_item["category"] == "收纳"
    elif name == "audience":
        present = value in product_item["audiences"]
    elif name == "style":
        present = value in product_item["styles"]
    elif name == "brand":
        present = product_item["origin"] == "国产" if value == "国产" else product_item["brand"] == value
    else:
        present = value in product_item["attributes"] or value in product_item["goals"]
    return not present if operator == "neq" else present


def rank_product_results(scene: str, conditions: list[dict[str, Any]]) -> dict[str, list[str]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    hard = [item for item in conditions if item["strength"] == "hard"]
    taxonomy_conditions = [
        item for item in conditions if item["name"] in ("xcat1", "xcat2")
    ]
    raw_positive_taxonomy = [item for item in taxonomy_conditions if item["operator"] == "eq"]
    selected_xcat2 = {item["value"] for item in raw_positive_taxonomy if item["name"] == "xcat2"}
    selected_xcat2_parents = {
        category["xcat1"]
        for category in TAXONOMY_CATEGORIES
        if category["xcat2"] in selected_xcat2
    }
    positive_taxonomy = [
        item for item in raw_positive_taxonomy
        if item["name"] == "xcat2" or item["value"] not in selected_xcat2_parents
    ]
    negative_taxonomy = [item for item in taxonomy_conditions if item["operator"] == "neq"]
    candidates = TAXONOMY_PRODUCTS
    for item in candidates:
        if (
            scene == "search"
            and not taxonomy_conditions
            and not all(tag in item["attributes"] for tag in ("男款", "白色", "运动鞋"))
        ):
            continue
        score = float(item["baseScore"])
        for condition in conditions:
            if condition["name"] == "priceOrder":
                price_signal = min(item["price"], 4000) / 100
                score += -price_signal if condition["value"] == "lower" else price_signal
                continue
            matches = product_matches(item, condition)
            if condition["strength"] == "hard":
                score += 35 if matches else -120
            elif condition["operator"] == "neq":
                score += 8 if matches else -55
            elif condition["name"] in ("category", "xcat1", "xcat2"):
                score += 90 if matches else -10
            else:
                score += 48 if matches else -4
        if any(condition["value"] == "新鲜感" for condition in conditions):
            score += item["novelty"] * 8
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    positive_categories = [
        condition
        for condition in conditions
        if condition["name"] == "category" and condition["operator"] == "eq"
    ]
    exact_requirements = [
        *[item for item in hard if item not in positive_taxonomy],
        *negative_taxonomy,
        *positive_categories,
    ]
    exact = [
        item["id"]
        for _, item in scored
        if all(product_matches(item, condition) for condition in exact_requirements)
        and (
            not positive_taxonomy
            or any(product_matches(item, condition) for condition in positive_taxonomy)
        )
    ]
    if scene == "recommend" and len(positive_categories) > 1:
        remaining = list(exact)
        interleaved: list[str] = []
        while remaining:
            added = False
            for condition in positive_categories:
                next_id = next(
                    (item_id for item_id in remaining if product_matches(PRODUCT_BY_ID[item_id], condition)),
                    None,
                )
                if next_id is not None:
                    remaining.remove(next_id)
                    interleaved.append(next_id)
                    added = True
            if not added:
                break
        exact = interleaved + remaining
    near = [item["id"] for _, item in scored if item["id"] not in exact]
    if len(positive_taxonomy) > 1:
        remaining = list(exact)
        interleaved = []
        while remaining:
            added = False
            for condition in positive_taxonomy:
                next_id = next(
                    (item_id for item_id in remaining if product_matches(PRODUCT_BY_ID[item_id], condition)),
                    None,
                )
                if next_id is not None:
                    remaining.remove(next_id)
                    interleaved.append(next_id)
                    added = True
            if not added:
                break
        exact = interleaved + remaining
    positive_xcat1 = next((item for item in positive_taxonomy if item["name"] == "xcat1"), None)
    positive_xcat2 = any(item["name"] == "xcat2" for item in positive_taxonomy)
    if len(positive_taxonomy) == 1 and positive_xcat1 and not positive_xcat2:
        remaining = list(exact)
        child_names = list(dict.fromkeys(PRODUCT_BY_ID[item_id]["xcat2"] for item_id in remaining))
        interleaved = []
        while remaining:
            added = False
            for child_name in child_names:
                next_id = next(
                    (
                        item_id
                        for item_id in remaining
                        if PRODUCT_BY_ID[item_id]["xcat2"] == child_name
                    ),
                    None,
                )
                if next_id is not None:
                    remaining.remove(next_id)
                    interleaved.append(next_id)
                    added = True
            if not added:
                break
        exact = interleaved
    if taxonomy_conditions:
        exact = exact[:80]
        near = near[:30]
    return {"exact": exact, "near": near}


def scenario_definition_for(key: str | None) -> dict[str, Any] | None:
    return next((item for item in SCENARIO_INTENTS if item["key"] == key), None)


def rank_scenario_results(
    scene: str,
    conditions: list[dict[str, Any]],
    scenario_key: str | None,
) -> dict[str, list[str]]:
    definition = scenario_definition_for(scenario_key)
    scenario_conditions = [item for item in conditions if item.get("sourceMode") == "scenario"]
    targets = list(definition["targets"]) if definition else []
    targets.extend(item["value"] for item in scenario_conditions)
    targets.extend(
        item["value"]
        for item in conditions
        if item.get("sourceMode") is None
        and item["name"] == "category"
        and item["operator"] == "eq"
    )
    targets = list(dict.fromkeys(targets))
    refinements = [item for item in conditions if item not in scenario_conditions]
    hard_refinements = [item for item in refinements if item["strength"] == "hard"]
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in TAXONOMY_PRODUCTS:
        target_indexes = [index for index, target in enumerate(targets) if product_contains_value(item, target)]
        if not target_indexes:
            continue
        score = float(item["baseScore"]) + 110 - min(target_indexes) * 5
        for condition in refinements:
            matches = product_matches(item, condition)
            if condition["strength"] == "hard":
                score += 35 if matches else -120
            elif condition["operator"] == "neq":
                score += 8 if matches else -45
            else:
                score += 28 if matches else -3
        score += item["trend"] * 2 + item["novelty"]
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    exact_pool = [
        item["id"]
        for _, item in scored
        if all(product_matches(item, condition) for condition in hard_refinements)
    ]
    interleaved: list[str] = []
    remaining = list(exact_pool)
    while remaining:
        added = False
        for target in targets:
            next_id = next(
                (item_id for item_id in remaining if product_contains_value(PRODUCT_BY_ID[item_id], target)),
                None,
            )
            if next_id is not None:
                remaining.remove(next_id)
                interleaved.append(next_id)
                added = True
        if not added:
            break
    exact = interleaved + remaining
    near = [item["id"] for _, item in scored if item["id"] not in exact]
    return {"exact": exact, "near": near}


def diversify_products(scored: list[tuple[float, dict[str, Any]]]) -> list[str]:
    remaining = list(scored)
    diversified: list[str] = []
    used_categories: set[str] = set()
    while remaining:
        next_index = next(
            (index for index, (_, item) in enumerate(remaining) if item["category"] not in used_categories),
            0,
        )
        _, item = remaining.pop(next_index)
        diversified.append(item["id"])
        used_categories.add(item["category"])
    return diversified


def rank_explore_results(
    scene: str,
    conditions: list[dict[str, Any]],
    theme: str | None,
) -> dict[str, list[str]]:
    refinements = [item for item in conditions if item.get("sourceMode") != "explore"]
    hard = [item for item in refinements if item["strength"] == "hard"]
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in TAXONOMY_PRODUCTS:
        if scene == "search" and not all(tag in item["attributes"] for tag in ("男款", "白色", "运动鞋")):
            continue
        if not all(product_matches(item, condition) for condition in hard):
            continue
        score = float(item["baseScore"]) * 0.35 + item["novelty"] * 9 + item["trend"] * 5
        if theme == "fresh":
            score += item["novelty"] * 8
        elif theme == "trend":
            score += item["trend"] * 10
        elif theme == "style":
            score += len(item["styles"]) * 28 + (8 if item["styles"] else 0)
        elif theme == "inspiration":
            score += len(item["goals"]) * 16 + (18 if "提升幸福感" in item["goals"] else 0)
            score += 36 if "幸福感精选" in item["attributes"] else 0
        elif theme == "wow":
            score += 46 if "眼前一亮精选" in item["attributes"] else item["novelty"] * 4
        elif theme == "upgrade":
            score += 45 if "升级" in item["attributes"] else min(item["price"], 1200) / 35
        elif theme == "future":
            score += len(item["goals"]) * 12 + item["novelty"] * 5
        for condition in refinements:
            if condition["name"] == "priceOrder":
                price_signal = min(item["price"], 4000) / 100
                score += -price_signal if condition["value"] == "lower" else price_signal
                continue
            matches = product_matches(item, condition)
            if condition["strength"] == "hard":
                score += 30 if matches else -120
            elif condition["operator"] == "neq":
                score += 8 if matches else -40
            else:
                score += 32 if matches else -2
        scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    exact = [item["id"] for _, item in scored] if theme in ("inspiration", "wow") else diversify_products(scored)
    return {"exact": exact, "near": []}


def rank_results(
    scene: str,
    conditions: list[dict[str, Any]],
    intent: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    mode = intent.get("mode") if intent else None
    source_condition = next(
        (item for item in reversed(conditions) if item.get("sourceMode") in ("scenario", "explore")),
        None,
    )
    if mode in (None, "unknown") and source_condition:
        mode = source_condition["sourceMode"]
    if mode == "product" and source_condition:
        mode = source_condition["sourceMode"]
    if mode == "scenario":
        scenario_key = intent.get("scenario", {}).get("key") if intent else None
        if scenario_key is None and source_condition:
            scenario_key = source_condition.get("sourceKey")
        return rank_scenario_results(scene, conditions, scenario_key)
    if mode == "explore":
        theme = intent.get("exploreTheme") if intent else None
        if theme is None and source_condition:
            theme = source_condition.get("sourceKey")
        return rank_explore_results(scene, conditions, theme)
    return rank_product_results(scene, conditions)


def rank_results_for_display(
    scene: str,
    conditions: list[dict[str, Any]],
    intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ranked = rank_results(scene, conditions, intent)
    response: dict[str, Any] = {**ranked, "fallbackApplied": False}
    if scene != "recommend" or ranked["exact"]:
        return response

    softened_conditions = [
        {
            **condition,
            "strength": "soft" if condition["strength"] == "hard" else condition["strength"],
        }
        for condition in conditions
    ]
    relaxed = (
        rank_results(scene, softened_conditions, intent)
        if softened_conditions != conditions
        else ranked
    )
    fallback_ids = (
        relaxed["exact"]
        or relaxed["near"]
        or ranked["near"]
        or INITIAL_RECOMMENDATIONS
    )
    response["exact"] = list(dict.fromkeys(fallback_ids))[:80]
    response["fallbackApplied"] = True
    return response


def feedback_for(intent: dict[str, Any]) -> str:
    if intent["type"] == "unknown":
        return "先为你推荐一些热门好物，你也可以继续补充偏好"
    selected_categories = intent.get("selectedCategories", [])
    excluded_categories = intent.get("excludedCategories", [])
    if selected_categories and excluded_categories:
        return (
            f"已减少{'、'.join(excluded_categories)}，"
            f"增加{'、'.join(selected_categories)}"
        )
    if excluded_categories:
        return f"已减少{'、'.join(excluded_categories)}"
    if selected_categories:
        if intent.get("selectionFallback"):
            return "先为你推荐这些"
        return f"已按这些类目为你推荐：{'、'.join(selected_categories)}"
    labels = [item["label"] for item in intent.get("slots", [])]
    if "减少跑鞋" in labels and "增加家居" in labels:
        return "已为你减少跑鞋，增加收纳与家居好物"
    if intent["mode"] == "scenario":
        scenario = intent["scenario"]
        return f"已将“{scenario['label']}”拆成：{'、'.join(scenario['targets'])}"
    if intent["mode"] == "explore":
        return f"已进入{intent['route']['label']}，增加新鲜度、趋势性和跨品类灵感"
    if intent.get("taxonomy"):
        taxonomy = intent["taxonomy"]
        path = taxonomy["xcat1"]
        if taxonomy.get("xcat2"):
            path += f" › {taxonomy['xcat2']}"
        return f"已定位品类：{path}"
    if labels:
        return f"已应用：{' · '.join(labels)}"
    return "已理解你的即时意图"


def products_for_ranked_results(ranked: dict[str, list[str]]) -> list[dict[str, Any]]:
    result_ids = list(ranked["exact"][:20])
    if len(ranked["exact"]) < 3:
        result_ids.extend(ranked["near"][:6])
    return [
        PRODUCT_BY_ID[item_id]
        for item_id in dict.fromkeys(result_ids)
        if item_id in PRODUCT_BY_ID
    ]


def example_guide_response(transcript: str) -> dict[str, Any] | None:
    guide = example_guide_for(transcript)
    if guide is None:
        return None
    bubbles = [
        preset_bubble(
            f"example-{guide['key']}-{index}",
            label,
            group=f"example-{guide['key']}",
        )
        for index, label in enumerate(guide["bubbles"], start=1)
    ]
    products = guide["products"]
    intent = {
        "type": "showcase",
        "polarity": "neutral",
        "slots": bubbles,
        "scope": "turn",
        "transcript": transcript,
        "showcaseKey": guide["key"],
        "selectedCategories": [],
        "excludedCategories": [],
        "selectionFallback": False,
        **mode_payload(
            "scenario",
            confidence=1.0,
            evidence=[guide["prompt"]],
            route_name="example_showcase",
            route_label="示例场景",
            route_summary=f"直接展示 {guide['key']} 的精选商品集",
        ),
    }
    return {
        "intent": intent,
        "engine": {
            "mode": intent["mode"],
            "modeLabel": intent["modeLabel"],
            "confidence": intent["confidence"],
            "evidence": intent["evidence"],
            "route": intent["route"],
        },
        "sessionIntent": bubbles,
        "resultIds": [item["id"] for item in products],
        "nearMatchIds": [],
        "products": products,
        "fallbackApplied": False,
        "feedback": guide["feedback"],
    }


def preset_scenario_response(
    transcript: str,
    existing: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    preset = preset_scenario_for(transcript)
    if preset is None:
        return None
    bubble_plan = PRESET_BUBBLE_PLANS[preset["key"]]
    session_intent, removed_labels = apply_preset_bubble_plan(existing or [], bubble_plan)
    products = preset["products"]
    intent = {
        "type": "preset",
        "polarity": "neutral",
        "slots": [dict(item) for item in bubble_plan["add"]],
        "scope": "turn",
        "transcript": transcript,
        "presetKey": preset["key"],
        "presetGroup": bubble_plan["group"],
        "presetBubbleOps": {
            "group": bubble_plan["group"],
            "reset": bubble_plan["reset"],
            "removeKeys": list(bubble_plan["removeKeys"]),
            "add": [dict(item) for item in bubble_plan["add"]],
        },
        "presetBubbleDelta": {
            "added": [item["label"] for item in bubble_plan["add"]],
            "removed": removed_labels,
        },
        "scenario": preset["scenario"],
        "selectedCategories": [],
        "excludedCategories": [],
        "selectionFallback": False,
        **mode_payload(
            "product",
            confidence=1.0,
            evidence=[preset["prompt"]],
            route_name="preset_scenario",
            route_label="预制情景",
            route_summary=f"直接展示 {preset['scenario']} 的固定商品集",
        ),
    }
    return {
        "intent": intent,
        "engine": {
            "mode": intent["mode"],
            "modeLabel": intent["modeLabel"],
            "confidence": intent["confidence"],
            "evidence": intent["evidence"],
            "route": intent["route"],
        },
        "sessionIntent": session_intent,
        "resultIds": [item["id"] for item in products],
        "nearMatchIds": [],
        "products": products,
        "fallbackApplied": False,
        "feedback": preset["feedback"],
    }


def bootstrap_payload() -> dict[str, Any]:
    return {
        "products": PRODUCTS,
        "initialRecommendations": INITIAL_RECOMMENDATIONS,
        "initialSearchResults": INITIAL_SEARCH_RESULTS,
        "searchQuery": "男生白色运动鞋",
        "searchWatermarks": [
            "夏日上衣",
            "骑行防晒面罩",
            "夏季通勤穿搭",
            "搬家收纳好物",
            "500元以内蓝牙耳机",
            "敏感肌防晒",
            "周末露营装备",
        ],
        "examples": {
            "recommend": [
                "最近想换换穿衣风格。",
                "有没有适合夏天穿的？",
                "今天想看点不一样的。",
                "有没有适合周末的新玩法？",
                "最近想开始健身。",
                "下个月去意大利，有什么需要准备的吗？",
            ],
            "search": ["要能增高的，500元以内", "不是女款，是男款"],
        },
    }


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[demo] {self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "").lower()
        if accepts_gzip:
            body = gzip.compress(body, compresslevel=5)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if accepts_gzip:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_home_catalog(self) -> None:
        global _HOME_CATALOG_GZIP
        if "gzip" not in self.headers.get("Accept-Encoding", "").lower():
            self.path = "/data/home-products.json"
            super().do_GET()
            return
        if _HOME_CATALOG_GZIP is None:
            with _WHALE_CONFIG_LOCK:
                if _HOME_CATALOG_GZIP is None:
                    _HOME_CATALOG_GZIP = gzip.compress(
                        HOME_CATALOG_PATH.read_bytes(),
                        compresslevel=5,
                    )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(_HOME_CATALOG_GZIP)))
        self.end_headers()
        self.wfile.write(_HOME_CATALOG_GZIP)

    def do_GET(self) -> None:
        if self.path.partition("?")[0] == "/data/home-products.json":
            self.send_home_catalog()
            return
        if self.path == "/api/demo/bootstrap":
            self.send_json(bootstrap_payload())
            return
        if self.path.startswith("/api/"):
            self.send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        if self.path in ("/", "/recommend", "/search"):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        try:
            payload = self.read_json()
            if self.path == "/api/intent/apply":
                scene = payload.get("scene", "recommend")
                if scene not in ("recommend", "search"):
                    raise ValueError("scene 必须是 recommend 或 search")
                transcript = str(payload.get("transcript", "")).strip()
                if not transcript:
                    raise ValueError("请输入或说出你的想法")
                existing = payload.get("sessionIntent", [])
                if not isinstance(existing, list):
                    raise ValueError("sessionIntent 必须是数组")
                example_response = example_guide_response(transcript)
                if example_response is not None:
                    self.send_json(example_response)
                    return
                preset_response = preset_scenario_response(transcript, existing)
                if preset_response is not None:
                    self.send_json(preset_response)
                    return
                intent = parse_intent(transcript)
                conditions = merge_conditions(existing, intent)
                ranked = rank_results_for_display(scene, conditions, intent)
                engine = {
                    "mode": intent["mode"],
                    "modeLabel": intent["modeLabel"],
                    "confidence": intent["confidence"],
                    "evidence": intent["evidence"],
                    "route": intent["route"],
                }
                self.send_json({
                    "intent": intent,
                    "engine": engine,
                    "sessionIntent": visible_session_conditions(conditions),
                    "resultIds": ranked["exact"],
                    "nearMatchIds": ranked["near"],
                    "products": products_for_ranked_results(ranked),
                    "fallbackApplied": ranked["fallbackApplied"],
                    "feedback": feedback_for(intent),
                })
                return
            if self.path == "/api/intent/reset":
                self.send_json({
                    "sessionIntent": [],
                    "resultIds": INITIAL_RECOMMENDATIONS,
                    "searchResultIds": INITIAL_SEARCH_RESULTS,
                    "feedback": "已恢复初始推荐",
                })
                return
            self.send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)
        except IntentAPIError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def run() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DemoHandler)
    print(f"你说了算 Demo 已启动：http://127.0.0.1:{PORT}")
    print("手机体验：请使用电脑的局域网 IP 访问同一端口")
    threading.Thread(target=warm_whale_sdk, name="whale-sdk-warmup", daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
