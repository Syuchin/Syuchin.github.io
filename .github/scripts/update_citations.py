import json
from datetime import datetime
from scholarly import scholarly
import os
import traceback
import requests

# 定义历史基准数据
HISTORICAL_CITATIONS = [
    {"date": "2024-07", "citations": 1},
    {"date": "2024-08", "citations": 2},
    {"date": "2024-09", "citations": 3},
    {"date": "2024-10", "citations": 7},
    {"date": "2024-11", "citations": 7},
    {"date": "2024-12", "citations": 7},
    {"date": "2025-01", "citations": 9},
]

def get_github_stars(owner, repo):
    """获取GitHub仓库的星标数"""
    try:
        response = requests.get(f"https://api.github.com/repos/{owner}/{repo}")
        if response.status_code == 200:
            stars = response.json()["stargazers_count"]
            print(f"Successfully retrieved stars for {owner}/{repo}: {stars}")
            return stars
        print(f"Failed to get stars for {owner}/{repo}: Status code {response.status_code}")
        return 0
    except Exception as e:
        print(f"Error fetching GitHub stars for {owner}/{repo}: {e}")
        return 0

def update_scholar_stats():
    # 获取 Google Scholar ID
    scholar_id = os.getenv('GOOGLE_SCHOLAR_ID')
    if not scholar_id:
        raise ValueError("Google Scholar ID not found in environment variables")

    try:
        # 获取作者信息
        author = scholarly.search_author_id(scholar_id)
        author_info = scholarly.fill(author)
        print(f"Successfully retrieved author info for: {author_info.get('name', 'Unknown')}")

        # 准备数据结构
        data = {
            "total_citations": author_info['citedby'],
            "h_index": author_info['hindex'],
            "papers": {},
            "citation_trend": []
        }
        print(f"Total citations: {data['total_citations']}")
        print(f"H-index: {data['h_index']}")

        # 获取论文信息和总引用数
        for pub in author_info['publications']:
            pub_filled = scholarly.fill(pub)
            print(f"\nProcessing paper: {pub_filled['bib']['title']}")
            print(f"Citations: {pub_filled['num_citations']}")
            print(f"Year: {pub_filled['bib']['pub_year']}")
            data["papers"][pub_filled['bib']['title']] = {
                "citations": pub_filled['num_citations'],
                "year": int(pub_filled['bib']['pub_year']),
                "url": pub_filled.get('pub_url', '')
            }

        # 读取现有的数据文件，以保留历史趋势数据
        try:
            with open('data/scholar_data.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                # 保留现有的趋势数据
                if 'citation_trend' in existing_data:
                    existing_trends = {item['date']: item['citations'] for item in existing_data['citation_trend']}
                else:
                    existing_trends = {}
        except (FileNotFoundError, json.JSONDecodeError):
            print("No existing data file found or file is corrupted. Creating new data.")
            existing_trends = {}

        # 获取当前月份
        current_month = datetime.now().strftime('%Y-%m')
        
        # 更新当前月份的引用数据
        existing_trends[current_month] = data['total_citations']
        
        # 检查是否是月末，如果是则创建一个历史记录
        today = datetime.now()
        is_month_end = today.day == get_last_day_of_month(today.year, today.month)
        
        if is_month_end:
            print(f"Today is the last day of {current_month}. Creating historical record.")
            # 创建历史记录目录（如果不存在）
            os.makedirs('data/history', exist_ok=True)
            
            # 保存当月数据的历史记录
            history_file = f'data/history/scholar_data_{current_month}.json'
            with open(history_file, 'w', encoding='utf-8') as f:
                # 复制当前数据并添加时间戳
                history_data = data.copy()
                history_data['snapshot_date'] = today.isoformat()
                history_data['citation_trend'] = [
                    {"date": month, "citations": count}
                    for month, count in sorted(existing_trends.items())
                ]
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            print(f"Historical data saved to {history_file}")

        # 转换为列表格式并按日期排序
        data["citation_trend"] = [
            {"date": month, "citations": count}
            for month, count in sorted(existing_trends.items())
        ]
        print("\nCitation trend:")
        for trend in data["citation_trend"]:
            print(f"{trend['date']}: {trend['citations']} citations")

        # 获取 GitHub 星标数并添加到数据中
        print("\nFetching GitHub stars...")
        data["github_stars"] = {
            "leolee99/LD-Agent": get_github_stars("leolee99", "LD-Agent"),
            "multimodal-art-projection/CryptoX": get_github_stars("multimodal-art-projection", "CryptoX")
        }

        # 添加最后更新时间
        data["last_updated"] = datetime.now().isoformat()

        # 保存数据
        with open('data/scholar_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\nSuccessfully saved data to scholar_data.json")

    except Exception as e:
        print(f"Error updating scholar stats: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        raise

def get_last_day_of_month(year, month):
    """获取指定年月的最后一天"""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - datetime.timedelta(days=1)).day

def test_scholar_stats():
    """测试函数，使用特定的 Scholar ID 进行验证"""
    try:
        # 设置测试用的 Scholar ID
        os.environ['GOOGLE_SCHOLAR_ID'] = '8RnQ3EEAAAAJ'  # 你的 Google Scholar ID
        print("\n=== Starting Google Scholar Stats Test ===\n")
        
        # 运行更新函数
        update_scholar_stats()
        
        # 验证生成的 JSON 文件
        print("\n=== Verifying Generated JSON ===\n")
        with open('data/scholar_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 检查必要的字段
        assert 'total_citations' in data, "Missing total_citations"
        assert 'h_index' in data, "Missing h_index"
        assert 'papers' in data, "Missing papers"
        assert 'citation_trend' in data, "Missing citation_trend"
        
        print("✓ All required fields present")
        print("✓ Test completed successfully")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    if os.getenv('TEST_MODE'):
        test_scholar_stats()
    else:
        update_scholar_stats() 