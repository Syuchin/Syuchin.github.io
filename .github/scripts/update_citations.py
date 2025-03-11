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

        # 读取现有的数据文件
        try:
            with open('data/scholar_data.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if 'citation_trend' in existing_data:
                    citation_trend = existing_data['citation_trend']
                else:
                    citation_trend = HISTORICAL_CITATIONS
        except (FileNotFoundError, json.JSONDecodeError):
            print("No existing data file found or file is corrupted. Using historical data.")
            citation_trend = HISTORICAL_CITATIONS

        # 获取当前月份
        current_month = datetime.now().strftime('%Y-%m')
        
        # 检查是否需要添加本月记录
        if not citation_trend or citation_trend[-1]['date'] != current_month:
            citation_trend.append({
                "date": current_month,
                "citations": data['total_citations']
            })
            print(f"Added citation record for {current_month}")
        else:
            # 更新本月记录
            citation_trend[-1]['citations'] = data['total_citations']
            print(f"Updated citation record for {current_month}")
        
        # 更新趋势数据
        data["citation_trend"] = citation_trend
        
        # 获取 GitHub 星标数
        data["github_stars"] = {
            "leolee99/LD-Agent": get_github_stars("leolee99", "LD-Agent"),
            "multimodal-art-projection/CryptoX": get_github_stars("multimodal-art-projection", "CryptoX")
        }

        # 添加最后更新时间
        data["last_updated"] = datetime.now().isoformat()

        # 保存数据
        os.makedirs('data', exist_ok=True)
        with open('data/scholar_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\nSuccessfully saved data to scholar_data.json")

    except Exception as e:
        print(f"Error updating scholar stats: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    if os.getenv('TEST_MODE'):
        print("Running in test mode")
        os.environ['GOOGLE_SCHOLAR_ID'] = '8RnQ3EEAAAAJ'  # 测试用ID
    update_scholar_stats() 