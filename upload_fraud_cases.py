#!/usr/bin/env python3
"""
批量上传反诈案例数据到知识库
"""
import json
import requests
from typing import Any

# 配置
API_BASE_URL = "http://127.0.0.1:8000"
USERNAME = "Lonn"  # 改成你的用户名
PASSWORD = "20041021"  # 改成你的密码

# 反诈案例数据
FRAUD_CASES = [
    {
        "text": "受害人收到冒充某市公安局的电话，称其名下银行卡涉嫌洗钱洗钱案，要求将资金转入'安全账户'进行审查。受害人因恐惧心理，分三次转账共计15万元。",
        "doc_id": "doc_2024_001",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 58,
        "job": "退休教师",
        "region": "上海市徐汇区",
        "fraud_type": "冒充公检法",
        "fraud_amount": 150000
    },
    {
        "text": "受害人在某社交软件结识一名自称境外投资专家的异性，对方通过虚假理财平台诱导其购买数字货币，初期小额返利后，受害人加大投入，最终平台无法登录。",
        "doc_id": "doc_2024_002",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 32,
        "job": "互联网公司程序员",
        "region": "浙江省杭州市",
        "fraud_type": "杀猪盘/虚假投资",
        "fraud_amount": 420000
    },
    {
        "text": "受害人在网上看到兼职刷单广告，称只需在电商平台购买指定商品并好评即可获得高额佣金。前两单顺利返佣，随后对方以'系统卡单'为由要求连续刷大单，受害人被骗。",
        "doc_id": "doc_2024_003",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 21,
        "job": "在校大学生",
        "region": "湖北省武汉市",
        "fraud_type": "刷单返利",
        "fraud_amount": 8500
    },
    {
        "text": "受害人接到自称某快递客服的电话，称其快递丢失需进行理赔。对方诱导受害人扫码进入虚假退款页面，并套取了银行卡验证码，导致卡内余额被盗刷。",
        "doc_id": "doc_2024_004",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 28,
        "job": "全职妈妈",
        "region": "广东省广州市",
        "fraud_type": "冒充电商客服",
        "fraud_amount": 12000
    },
    {
        "text": "诈骗分子盗取受害人好友的QQ号，向受害人发送'出急事借钱'的消息。受害人未通过电话核实便转账，事后发现好友账号被盗。",
        "doc_id": "doc_2024_005",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 45,
        "job": "企业中层管理",
        "region": "江苏省南京市",
        "fraud_type": "冒充熟人/QQ诈骗",
        "fraud_amount": 30000
    },
    {
        "text": "受害人收到短信称其信用卡额度可提升至10万，点击链接后下载了虚假贷款APP。客服称其流水不足需转入解冻金，受害人多次转账后仍无法提现。",
        "doc_id": "doc_2024_006",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 35,
        "job": "个体工商户",
        "region": "四川省成都市",
        "fraud_type": "虚假贷款",
        "fraud_amount": 55000
    },
    {
        "text": "诈骗分子在二手交易平台以极低价格发布二手手机信息，引诱受害人脱离平台在微信交易。受害人付款后被对方拉黑，未收到货物。",
        "doc_id": "doc_2024_007",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 19,
        "job": "自由职业者",
        "region": "河南省郑州市",
        "fraud_type": "网络购物诈骗",
        "fraud_amount": 2800
    },
    {
        "text": "受害人被拉入一个'炒股交流群'，群内'老师'宣称有内幕消息。受害人信以为真，下载了非法交易软件，投入全部积蓄后被踢出群聊，软件失效。",
        "doc_id": "doc_2024_008",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 65,
        "job": "退休职工",
        "region": "北京市朝阳区",
        "fraud_type": "虚假理财/荐股",
        "fraud_amount": 800000
    },
    {
        "text": "受害人收到自称是孩子学校老师的短信，称孩子突发急病正在抢救需立即缴纳住院费。受害人慌乱中按照要求向陌生账户转账，事后发现是骗局。",
        "doc_id": "doc_2024_009",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 42,
        "job": "医务工作者",
        "region": "陕西省西安市",
        "fraud_type": "冒充身份/紧急救助",
        "fraud_amount": 25000
    },
    {
        "text": "受害人在某直播平台抽中'大奖'，客服称需缴纳中奖税及公证费方可领奖。受害人多次转账后，对方继续索要'手续费'，受害人意识到被骗。",
        "doc_id": "doc_2024_010",
        "chunk_max_chars": 200,
        "chunk_overlap_chars": 20,
        "age": 25,
        "job": "餐饮服务员",
        "region": "福建省厦门市",
        "fraud_type": "中奖/幸运抽奖",
        "fraud_amount": 5000
    }
]


def login() -> str:
    """登录并获取 JWT token"""
    print("🔐 正在登录...")
    response = requests.post(
        f"{API_BASE_URL}/auth/login/json",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10
    )
    if response.status_code != 200:
        print(f"❌ 登录失败: {response.status_code}")
        print(response.text)
        exit(1)
    
    token = response.json()["access_token"]
    print(f"✅ 登录成功，token: {token[:20]}...")
    return token


def upload_case(token: str, case: dict[str, Any]) -> bool:
    """上传单个案例"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/kb/text/upload",
            json=case,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {case['doc_id']} 上传成功 - {result['chunk_count']} 个分段，{result['inserted']} 条记录")
            return True
        else:
            print(f"❌ {case['doc_id']} 上传失败 ({response.status_code}): {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ {case['doc_id']} 上传异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("反诈案例知识库批量上传工具")
    print("=" * 60)
    
    # 登录
    token = login()
    
    # 批量上传
    print(f"\n📤 开始上传 {len(FRAUD_CASES)} 个案例...\n")
    success_count = 0
    fail_count = 0
    
    for i, case in enumerate(FRAUD_CASES, 1):
        print(f"[{i}/{len(FRAUD_CASES)}] 上传 {case['doc_id']}...")
        if upload_case(token, case):
            success_count += 1
        else:
            fail_count += 1
    
    # 统计
    print("\n" + "=" * 60)
    print(f"📊 上传完成")
    print(f"   ✅ 成功: {success_count}")
    print(f"   ❌ 失败: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
