# spider/bilibili_spider.py - 核心爬虫（含日志记录 + 增量爬取）

from curl_cffi import requests
import time
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append('..')
from config import PARTITIONS, HEADERS, REQUEST_DELAY
from storage.mysql_client import save_videos

# ==========================================
# 日志工具函数
# ==========================================
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'spider_log.txt')

def log_message(msg, level="INFO"):
    """写入日志文件"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {msg}\n"
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)

def log_error(msg):
    log_message(msg, "ERROR")

def log_start():
    log_message("=" * 50)
    log_message("🚀 爬虫任务启动")

def log_end(total_count, new_count, status="SUCCESS"):
    log_message(f"📊 爬取完成：总获取 {total_count} 条，新增入库 {new_count} 条")
    log_message(f"🏁 爬虫任务结束，状态：{status}")
    log_message("=" * 50 + "\n")


# ==========================================
# 爬虫核心函数
# ==========================================
def fetch_ranking(rid=0):
    """请求B站排行榜API"""
    url = f'https://api.bilibili.com/x/web-interface/ranking/v2?rid={rid}&type=all'

    try:
        # 使用 config.py 中统一管理的 HEADERS（已包含 Cookie）
        resp = requests.get(url, headers=HEADERS, timeout=15, impersonate="chrome120")
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('list', [])
            else:
                log_error(f"分区 {rid} API返回错误码: {data.get('code')}")
                return []
        else:
            log_error(f"分区 {rid} HTTP状态码异常: {resp.status_code}")
            return []
    except requests.exceptions.Timeout:
        log_error(f"分区 {rid} 请求超时")
        return []
    except Exception as e:
        log_error(f"分区 {rid} 请求失败: {e}")
        return []


def parse_video(v):
    """解析单条视频，提取所有字段"""
    stat = v.get('stat', {})
    play = stat.get('view', 0)
    likes = stat.get('like', 0)
    coins = stat.get('coin', 0)
    favs = stat.get('favorite', 0)
    shares = stat.get('share', 0)

    # 互动率
    interact = (likes + coins + favs + shares) / play if play > 0 else 0

    # ★ 综合热度分（毕设推荐系统用）★
    heat_score = (play * 0.3 + likes * 0.3 + favs * 0.2 + coins * 0.15 + shares * 0.05) / 10000

    # 标签处理
    tags_raw = v.get('tags', [])
    if isinstance(tags_raw, list):
        tags_str = ','.join([t.get('tag_name', '') for t in tags_raw if t.get('tag_name')])
    else:
        tags_str = ''

    pub_ts = v.get('pubdate', 0)
    pub_date = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d %H:%M:%S') if pub_ts else None

    return {
        'bvid': v.get('bvid'),
        'title': v.get('title', '').strip(),
        'owner': v.get('owner', {}).get('name', ''),
        'tid': v.get('tid', 0),
        'tags': tags_str[:500],
        'pub_date': pub_date,
        'pub_timestamp': pub_ts,
        'view': play,
        'danmaku': stat.get('danmaku', 0),
        'like_count': likes,
        'coin': coins,
        'favorite': favs,
        'share': shares,
        'interact_rate': round(interact, 4),
        'heat_score': round(heat_score, 4),
        'url': f"https://www.bilibili.com/video/{v.get('bvid')}"
    }


# ==========================================
# 主程序
# ==========================================
def main():
    # 记录开始
    log_start()
    start_time = datetime.now()
    log_message(f"📋 爬取分区: {PARTITIONS}")

    all_videos = []
    for rid in PARTITIONS:
        log_message(f"⏳ 正在爬取分区 {rid}...")
        raw_list = fetch_ranking(rid)
        if raw_list:
            for v in raw_list:
                all_videos.append(parse_video(v))
            log_message(f"   ✅ 分区 {rid} 获取 {len(raw_list)} 条原始数据")
        else:
            log_error(f"   ❌ 分区 {rid} 未获取到数据")
        time.sleep(REQUEST_DELAY)

    total_raw = len(all_videos)
    log_message(f"📊 共获取原始数据 {total_raw} 条，准备去重入库...")

    if all_videos:
        # 存数据库（增量模式：已存在的 bvid 会自动跳过）
        new_count = save_videos(all_videos)

        # 存CSV备份（追加模式）
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'bilibili_数据备份.csv')
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df = pd.DataFrame(all_videos)

        if os.path.exists(csv_path):
            df_existing = pd.read_csv(csv_path, encoding='utf-8-sig')
            df_all = pd.concat([df_existing, df], ignore_index=True)
            df_all = df_all.drop_duplicates(subset=['bvid'], keep='last')
            df_all.to_csv(csv_path, index=False, encoding='utf-8-sig')
        else:
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')

        log_message(f"💾 CSV备份保存至: {csv_path}")
        log_message(f"📊 本次新增入库: {new_count} 条")
    else:
        new_count = 0
        log_error("❌ 未获取到任何数据")

    # 记录结束
    elapsed = (datetime.now() - start_time).seconds
    status = "SUCCESS" if new_count > 0 else "PARTIAL"
    log_end(total_raw, new_count, status)
    log_message(f"⏱️ 总耗时: {elapsed} 秒")


if __name__ == '__main__':
    main()