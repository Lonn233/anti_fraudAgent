from __future__ import annotations

import re


_HIGH_RISK_PATTERNS: list[tuple[re.Pattern[str], str, int]] = [
    (re.compile(r"验证码|短信验证码|动态码", re.I), "索要验证码/动态码", 30),
    (re.compile(r"转账|汇款|刷流水|刷流水", re.I), "诱导转账/刷流水", 35),
    (re.compile(r"刷流水|刷流水返利|返利", re.I), "返利/刷流水话术", 20),
    (re.compile(r"客服|退款|理赔|取消订单", re.I), "假冒客服/退款理赔", 25),
    (re.compile(r"公检法|检察院|法院|通缉|涉案", re.I), "冒充公检法恐吓", 40),
    (re.compile(r"投资|理财|稳赚|高收益|内幕", re.I), "高收益投资/理财诱导", 30),
    (re.compile(r"裸聊|敲诈|偷拍视频", re.I), "裸聊敲诈风险", 45),
    (re.compile(r"点击链接|下载APP|远程协助|屏幕共享", re.I), "诱导点击链接/安装/远程控制", 25),
]


def score_text(text: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    t = text.strip()
    if not t:
        return 0, ["空文本"]

    for pat, reason, pts in _HIGH_RISK_PATTERNS:
        if pat.search(t):
            reasons.append(reason)
            score += pts

    if re.search(r"\b\d{16,19}\b", t):
        reasons.append("疑似银行卡号")
        score += 15

    if re.search(r"\b1[3-9]\d{9}\b", t):
        reasons.append("包含手机号（社工/诈骗常用信息）")
        score += 10

    score = min(100, score)
    if score == 0:
        reasons = ["未命中常见诈骗话术（仅为规则引擎结果）"]
    return score, reasons


def score_media(media_type: str, filename: str | None) -> tuple[int, list[str]]:
    # 占位：后续可接 ASR/OCR/视频抽帧/多模态模型
    # 目前按媒体类型给一个基础风险 + 文件名关键词命中
    base = {"image": 10, "audio": 15, "video": 15}.get(media_type, 10)
    reasons = [f"已接收{media_type}文件（当前为占位识别逻辑）"]
    score = base

    if filename:
        lowered = filename.lower()
        if "refund" in lowered or "退款" in lowered:
            reasons.append("文件名疑似包含退款/客服主题")
            score += 20
        if "police" in lowered or "公检法" in lowered:
            reasons.append("文件名疑似包含公检法主题")
            score += 25

    return min(100, score), reasons

