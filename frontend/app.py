# frontend/app.py - 后端（含定时爬虫 + 增量快照查询）

from flask import Flask, render_template, jsonify, request, send_from_directory
import pymysql
import sys
import os
import threading
import time
from datetime import datetime
import subprocess

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MYSQL_CONFIG

app = Flask(__name__)

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')

@app.route('/docs/<path:filename>')
def serve_docs(filename):
    """直接访问 docs/ 文件夹里的图片"""
    return send_from_directory(DOCS_DIR, filename)


# ==========================================
# ★ 后台定时爬虫（每 10 分钟自动跑一次）
# ==========================================
def scheduled_spider():
    """后台线程：定时执行爬虫"""
    # 等待 5 秒再开始，避免和 Flask 启动冲突
    time.sleep(5)

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🕷️ 定时爬虫启动...")

            # 动态导入爬虫模块（避免循环导入）
            spider_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'spider')
            if spider_path not in sys.path:
                sys.path.append(spider_path)
            from bilibili_spider import main as run_spider

            # 执行爬虫
            run_spider()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 定时爬虫完成")

            # ★ 爬完立刻调用 charts.py 重新生成图表
            try:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📊 开始生成图表...")
                charts_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'analysis', 'charts.py'
                )
                result = subprocess.run(
                    [sys.executable, charts_path],
                    capture_output=True, text=True, encoding='utf-8', errors='ignore'
                )
                if result.returncode == 0:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 图表生成完成")
                else:
                    print(f"❌ 图表生成失败: {result.stderr[:200]}")
            except Exception as e:
                print(f"❌ 图表生成出错: {e}")

        except Exception as e:
            print(f"❌ 定时爬虫出错: {e}")

        # 每 10 分钟执行一次（爬虫 + 图表一起）
        time.sleep(600)


def start_scheduler():
    """启动后台定时任务线程"""
    thread = threading.Thread(target=scheduled_spider, daemon=True)
    thread.start()
    print("⏰ 定时爬虫已启动（每 10 分钟运行一次）")


# ==========================================
# 数据库连接
# ==========================================
def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**MYSQL_CONFIG)


# ==========================================
# 页面路由
# ==========================================
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/last_update')
def get_last_update():
    """返回最后一次数据更新时间"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(crawl_time) FROM video_stats")
    last_time = cursor.fetchone()[0]
    conn.close()

    if last_time:
        return jsonify({'last_update': last_time.strftime('%Y/%m/%d %H:%M:%S')})
    return jsonify({'last_update': '暂无数据'})


# ==========================================
# API：统计数据
# ==========================================
@app.route('/api/stats')
def get_stats():
    """获取数据统计信息（从 video_stats 取最新快照）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 视频总数（从 videos 表）
    cursor.execute("SELECT COUNT(*) FROM videos")
    total_videos = cursor.fetchone()[0]

    # 总播放量（从 video_stats 取每个视频的最新快照）
    cursor.execute("""
                   SELECT SUM(vs.view)
                   FROM video_stats vs
                            INNER JOIN (SELECT bvid, MAX(crawl_time) AS max_time
                                        FROM video_stats
                                        GROUP BY bvid) latest
                                       ON vs.bvid = latest.bvid AND vs.crawl_time = latest.max_time
                   """)
    total_views = cursor.fetchone()[0] or 0

    # 平均互动率（取最新快照）
    cursor.execute("""
                   SELECT AVG(vs.interact_rate)
                   FROM video_stats vs
                            INNER JOIN (SELECT bvid, MAX(crawl_time) AS max_time
                                        FROM video_stats
                                        GROUP BY bvid) latest
                                       ON vs.bvid = latest.bvid AND vs.crawl_time = latest.max_time
                   """)
    avg_interact = cursor.fetchone()[0] or 0

    # UP主总数
    cursor.execute("SELECT COUNT(DISTINCT owner) FROM videos")
    total_owners = cursor.fetchone()[0]

    conn.close()
    return jsonify({
        'total_videos': total_videos,
        'total_views': f'{int(total_views):,}',
        'avg_interact': f'{avg_interact:.4f}',
        'total_owners': total_owners
    })


# ==========================================
# API：视频列表
# ==========================================
@app.route('/api/videos')
def get_videos():
    """获取视频列表（关联最新快照数据）"""
    keyword = request.args.get('keyword', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        base_sql = """
                   SELECT v.bvid, v.title, v.owner, vs.view, vs.like_count, vs.heat_score, v.url
                   FROM videos v
                            INNER JOIN (SELECT bvid, MAX(crawl_time) AS max_time
                                        FROM video_stats
                                        GROUP BY bvid) latest
                                       ON v.bvid = latest.bvid
                            INNER JOIN video_stats vs
                                       ON vs.bvid = latest.bvid AND vs.crawl_time = latest.max_time \
                   """

        if keyword:
            cursor.execute("SELECT COUNT(*) FROM videos WHERE title LIKE %s", (f'%{keyword}%',))
            total = cursor.fetchone()[0]
            cursor.execute(
                base_sql + " WHERE v.title LIKE %s ORDER BY vs.view DESC LIMIT %s OFFSET %s",
                (f'%{keyword}%', per_page, offset)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM videos")
            total = cursor.fetchone()[0]
            cursor.execute(
                base_sql + " ORDER BY vs.view DESC LIMIT %s OFFSET %s",
                (per_page, offset)
            )

        videos = cursor.fetchall()
        return jsonify({
            'videos': [{
                'bvid': v[0], 'title': v[1], 'owner': v[2],
                'view': v[3], 'like_count': v[4], 'heat_score': v[5], 'url': v[6]
            } for v in videos],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 1
        })
    finally:
        conn.close()


# ==========================================
# API：热度 TOP10
# ==========================================
@app.route('/api/top10')
def get_top10():
    """获取热度 TOP10"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, owner, heat_score, view FROM videos ORDER BY heat_score DESC LIMIT 10")
    results = cursor.fetchall()
    conn.close()

    return jsonify([{
        'title': r[0],
        'owner': r[1],
        'heat_score': r[2],
        'view': r[3]
    } for r in results])


# ==========================================
# 启动
# ==========================================
if __name__ == '__main__':
    start_scheduler()  # 只启动爬虫（爬完会自动画图）
    app.run(debug=True, port=5000, use_reloader=False)  # ★ use_reloader=False 避免定时器被启动两次