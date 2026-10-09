# analysis/charts.py
# 功能：生成实习报告所需的全部图表（基础4张 + 进阶2张）
# 所有图表标题、坐标轴标签、图例均已中文化

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from wordcloud import WordCloud
import pymysql
from sqlalchemy import create_engine
from scipy import stats
from config import MYSQL_CONFIG

# 设置中文字体（防止乱码）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 自动获取项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ★ 图表保存目录（绝对路径，避免 subprocess 调用时路径错乱）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, 'docs')
os.makedirs(DOCS_DIR, exist_ok=True)


def fetch_data_from_mysql():
    """从 MySQL 读取数据（关联 video_stats 取最新快照）"""
    # ★ 使用 SQLAlchemy 连接（Pandas 2.0+ 要求）
    engine = create_engine(
        f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}"
        f"@{MYSQL_CONFIG['host']}/{MYSQL_CONFIG['database']}?charset=utf8mb4"
    )

    sql = """
          SELECT v.bvid, \
                 v.title, \
                 v.owner, \
                 v.tid, \
                 v.tags, \
                 v.pub_date,
                 vs.view, \
                 vs.danmaku, \
                 vs.like_count, \
                 vs.coin, \
                 vs.favorite, \
                 vs.share,
                 vs.interact_rate, \
                 vs.heat_score, \
                 v.url
          FROM videos v
                   INNER JOIN (SELECT bvid, MAX(crawl_time) AS max_time \
                               FROM video_stats \
                               GROUP BY bvid) latest ON v.bvid = latest.bvid
                   INNER JOIN video_stats vs
                              ON vs.bvid = latest.bvid AND vs.crawl_time = latest.max_time \
          """

    df = pd.read_sql(sql, engine)
    engine.dispose()  # 关闭连接
    return df


def generate_charts():
    print("正在读取数据...")
    df = fetch_data_from_mysql()
    print(f"共读取 {len(df)} 条数据，开始生成图表...")

    # docs 文件夹已在顶部创建，无需重复

    # ==========================================
    # 基础图 1：分区分布饼图（带中文注释）
    # ==========================================
    partition_counts = df['tid'].value_counts()
    plt.figure(figsize=(8, 8))
    plt.pie(partition_counts.values, labels=partition_counts.index, autopct='%1.1f%%')
    plt.title('B站热门视频分区分布', fontsize=16)
    # 添加中文字幕说明
    plt.text(0, -1.2, '注：各分区占比反映当前热门视频的内容分布情况',
             fontsize=10, ha='center', color='gray')
    plt.savefig(os.path.join(DOCS_DIR, '图1_分区分布饼图.png'), dpi=300, bbox_inches='tight')
    print("✅ 已生成：图1_分区分布饼图.png")

    # ==========================================
    # 基础图 2：播放量 TOP10 条形图（带中文注释）
    # ==========================================
    top10 = df.nlargest(10, 'view')[['title', 'view']]
    plt.figure(figsize=(10, 6))
    bars = plt.barh(top10['title'], top10['view'], color='skyblue')
    plt.xlabel('播放量（次）', fontsize=12)
    plt.title('B站热门视频播放量 TOP10', fontsize=16)
    plt.gca().invert_yaxis()
    # 在柱子上标注数值
    for bar, val in zip(bars, top10['view']):
        plt.text(bar.get_width() + 0.02 * max(top10['view']),
                 bar.get_y() + bar.get_height() / 2,
                 f'{val:,.0f}', va='center', fontsize=9)
    plt.savefig(os.path.join(DOCS_DIR, '图2_播放量TOP10条形图.png'), dpi=300, bbox_inches='tight')
    print("✅ 已生成：图2_播放量TOP10条形图.png")

    # ==========================================
    # 基础图 3：互动率分布直方图（带中文注释）
    # ==========================================
    plt.figure(figsize=(10, 6))
    plt.hist(df['interact_rate'], bins=20, color='lightgreen', edgecolor='black')
    plt.xlabel('互动率', fontsize=12)
    plt.ylabel('视频数量（个）', fontsize=12)
    plt.title('视频互动率分布情况', fontsize=16)
    # 添加统计说明
    mean_val = df['interact_rate'].mean()
    plt.axvline(mean_val, color='red', linestyle='--', label=f'平均互动率: {mean_val:.4f}')
    plt.legend()
    # 原
    plt.savefig('../docs/图3_互动率分布直方图.png', dpi=300, bbox_inches='tight')

    # 改为
    plt.savefig(os.path.join(DOCS_DIR, '图3_互动率分布直方图.png'), dpi=300, bbox_inches='tight')
    print("✅ 已生成：图3_互动率分布直方图.png")

    # ==========================================
    # 基础图 4：标题词云图（带中文注释）
    # ==========================================
    titles = ' '.join(df['title'].dropna().tolist())
    if titles.strip():
        wc = WordCloud(width=800, height=400,
                       background_color='white',
                       font_path='C:/Windows/Fonts/simhei.ttf',
                       colormap='viridis').generate(titles)
        plt.figure(figsize=(10, 5))
        plt.imshow(wc, interpolation='bilinear')
        plt.axis('off')
        plt.title('热门视频标题词云', fontsize=16)
        plt.savefig(os.path.join(DOCS_DIR, '图4_标题词云图.png'), dpi=300, bbox_inches='tight')
        print("✅ 已生成：图4_标题词云图.png")
    else:
        print("⚠️ 未找到标题数据，跳过词云图")

    # ==========================================
    # ★ 进阶图 1：播放量 vs 互动率 散点图（体现数据分析深度）
    # ==========================================
    plt.figure(figsize=(10, 6))
    plt.scatter(df['view'], df['interact_rate'], alpha=0.6, c='steelblue')
    plt.xlabel('播放量（次）', fontsize=12)
    plt.ylabel('互动率', fontsize=12)
    plt.title('播放量与互动率关系散点图', fontsize=16)

    # 添加趋势线（让图更专业）
    x = df['view']
    y = df['interact_rate']
    # 去除无效值
    mask = (x > 0) & (y > 0)
    if mask.sum() > 2:
        slope, intercept, r_value, p_value, std_err = stats.linregress(x[mask], y[mask])
        x_line = np.linspace(x[mask].min(), x[mask].max(), 100)
        y_line = slope * x_line + intercept
        plt.plot(x_line, y_line, 'r--', label=f'趋势线 (R²={r_value ** 2:.3f})')
        plt.legend()
        # 在图上添加注解
        plt.text(0.6 * x.max(), 0.8 * y.max(),
                 f'相关系数 r = {r_value:.3f}\n说明：播放量与互动率{"正相关" if r_value > 0 else "负相关"}',
                 fontsize=10, bbox=dict(boxstyle="round", facecolor='white', alpha=0.8))

    plt.savefig(os.path.join(DOCS_DIR, '图5_播放量与互动率散点图.png'), dpi=300, bbox_inches='tight')
    print("✅ 已生成：图5_播放量与互动率散点图.png")

    # ==========================================
    # ★ 进阶图 2：综合热度分 TOP10（体现你的特征工程）
    # ==========================================
    top10_heat = df.nlargest(10, 'heat_score')[['title', 'heat_score', 'view']]
    plt.figure(figsize=(10, 6))
    bars = plt.barh(top10_heat['title'], top10_heat['heat_score'], color='coral')
    plt.xlabel('综合热度分', fontsize=12)
    plt.title('B站热门视频综合热度分 TOP10', fontsize=16)
    plt.gca().invert_yaxis()
    # 标注数值和播放量对照
    for bar, val, view in zip(bars, top10_heat['heat_score'], top10_heat['view']):
        plt.text(bar.get_width() + 0.02 * max(top10_heat['heat_score']),
                 bar.get_y() + bar.get_height() / 2,
                 f'{val:.2f} (播放:{view:,.0f})', va='center', fontsize=8)
    # 底部注释说明权重
    plt.text(0, -0.5, '注：综合热度分 = 播放×0.3 + 点赞×0.3 + 收藏×0.2 + 投币×0.15 + 转发×0.05',
             fontsize=9, ha='left', color='gray')
    plt.savefig(os.path.join(DOCS_DIR, '图6_综合热度分TOP10.png'), dpi=300, bbox_inches='tight')
    print("✅ 已生成：图6_综合热度分TOP10.png")

    print("\n🎉 全部 6 张图表已生成完毕！保存在 docs/ 文件夹中。")
    print("📊 图表清单：")
    print("  图1_分区分布饼图.png - 各分区视频占比")
    print("  图2_播放量TOP10条形图.png - 播放量最高的10个视频")
    print("  图3_互动率分布直方图.png - 互动率整体分布情况")
    print("  图4_标题词云图.png - 热门标题关键词")
    print("  图5_播放量与互动率散点图.png - 相关关系分析（进阶）")
    print("  图6_综合热度分TOP10.png - 综合热度排名（进阶）")


if __name__ == '__main__':
    generate_charts()