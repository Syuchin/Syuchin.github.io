import json
from datetime import datetime
import os
import traceback
import requests
import time
import random
import re

# 简单 UA 轮换（保留占位，当前使用 SerpApi 无需本地抓取）
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
]

def _pick_ua():
    return USER_AGENTS[0]

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
        response = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
        if response.status_code == 200:
            stars = response.json()["stargazers_count"]
            print(f"成功获取 {owner}/{repo} 的星标数: {stars}")
            return stars
        print(f"获取 {owner}/{repo} 星标失败: HTTP {response.status_code}")
        return 0
    except Exception as e:
        print(f"获取 {owner}/{repo} 星标时出错: {e}")
        return 0

def calculate_h_index(papers):
    """计算H指数：有h篇论文的引用数都不少于h"""
    if not papers:
        return 0
    
    # 获取所有论文的引用数，并按降序排列
    citations = [paper.get('citations', 0) for paper in papers.values()]
    citations.sort(reverse=True)
    
    # 计算H指数
    h_index = 0
    for i, cite_count in enumerate(citations):
        if cite_count >= i + 1:
            h_index = i + 1
        else:
            break
    
    return h_index

def generate_citation_summary(papers):
    """生成引用摘要信息"""
    summary = {
        'total_papers': len(papers),
        'total_citations': sum(paper.get('citations', 0) for paper in papers.values()),
        'highly_cited_papers': [],
        'recent_papers': [],
        'citation_distribution': {}
    }
    
    current_year = datetime.now().year
    
    for title, paper in papers.items():
        citations = paper.get('citations', 0)
        year = paper.get('year', current_year)
        
        # 高引用论文 (>5引用)
        if citations >= 5:
            summary['highly_cited_papers'].append({
                'title': title,
                'citations': citations,
                'year': year
            })
        
        # 近期论文 (近3年)
        if current_year - year <= 3:
            summary['recent_papers'].append({
                'title': title,
                'citations': citations,
                'year': year
            })
        
        # 引用分布
        if citations > 0:
            if citations >= 20:
                category = '20+'
            elif citations >= 10:
                category = '10-19'
            elif citations >= 5:
                category = '5-9'
            else:
                category = '1-4'
            
            summary['citation_distribution'][category] = summary['citation_distribution'].get(category, 0) + 1
    
    # 按引用数排序
    summary['highly_cited_papers'].sort(key=lambda x: x['citations'], reverse=True)
    summary['recent_papers'].sort(key=lambda x: x['year'], reverse=True)
    
    return summary

def get_scholar_data_via_serpapi(scholar_id: str, api_key: str):
    """通过 SerpApi 获取 Scholar 作者数据（总引用、h-index、论文）。

    参考 SerpApi Google Scholar Author API 的返回结构：
    - cited_by.table 提供 citations/h_index/i10_index（不同语言键名可能变化）
    - cited_by.graph 提供年度引用数
    - articles 列表包含每篇论文的引用数、年份等
    """
    try:
        params = {
            'engine': 'google_scholar_author',
            'author_id': scholar_id,
            'hl': 'en',
            'api_key': api_key,
        }
        # 轻微随机延迟，防止瞬时并发触达
        time.sleep(random.uniform(0.3, 0.8))
        resp = requests.get('https://serpapi.com/search.json', params=params, timeout=30)
        if resp.status_code != 200:
            print(f"SerpApi 请求失败，HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        results = resp.json()

        status = results.get('search_metadata', {}).get('status')
        if status != 'Success':
            print(f"SerpApi 返回状态异常: {status}")
            return None

        cited_by = results.get('cited_by', {})
        table = cited_by.get('table', []) or []

        def _extract_total_citations(table_entries):
            for entry in table_entries:
                for key, val in entry.items():
                    if key in ('citations', 'indice_citations') and isinstance(val, dict):
                        # 常见键：all / since_2016 / depuis_2016 / recent
                        for k in ('all', 'since_2016', 'depuis_2016', 'recent'):
                            if k in val and str(val[k]).isdigit():
                                return int(val[k])
            return None

        def _extract_h_index(table_entries):
            for entry in table_entries:
                for key, val in entry.items():
                    if key in ('h_index', 'indice_h') and isinstance(val, dict):
                        for k in ('all', 'since_2016', 'depuis_2016', 'recent'):
                            if k in val and str(val[k]).isdigit():
                                return int(val[k])
            return None

        total_citations = _extract_total_citations(table)
        articles = results.get('articles', []) or []
        papers = {}
        current_year = datetime.now().year

        for art in articles[:30]:  # 取前30篇，避免过长
            try:
                title = art.get('title') or 'Untitled'
                year_raw = art.get('year')
                year = int(year_raw) if year_raw and str(year_raw).isdigit() else current_year
                cited_by_obj = art.get('cited_by') or {}
                citations = int(cited_by_obj.get('value') or 0)
                link = art.get('link') or ''
                citation_id = art.get('citation_id') or ''
                cited_by_link = cited_by_obj.get('link') or ''

                papers[title] = {
                    'citations': citations,
                    'year': year,
                    'url': link,
                    'citation_url': cited_by_link,
                    'citation_id': citation_id,
                }
            except Exception as e:
                print(f"解析论文条目时出错: {e}")

        h_index = _extract_h_index(table)
        if h_index is None:
            h_index = calculate_h_index(papers)

        if total_citations is None:
            # 若无法直接从表格获取，总计为论文引用数之和（保守）
            total_citations = max(sum(p.get('citations', 0) for p in papers.values()), 0)

        citation_summary = generate_citation_summary(papers)

        print("成功从 SerpApi 获取 Scholar 数据:")
        print(f"- 总引用数: {total_citations}")
        print(f"- H指数: {h_index}")
        print(f"- 论文数量: {len(papers)}")

        return {
            'total_citations': total_citations,
            'h_index': h_index,
            'papers': papers,
            'citation_summary': citation_summary,
        }
    except Exception as e:
        print(f"调用 SerpApi 失败: {e}")
        return None

def get_fallback_data():
    """获取备用数据，当API失败时使用"""
    print("使用备用数据...")
    
    # 尝试从现有文件读取最新数据
    try:
        with open('data/scholar_data.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            
        # 获取最新的引用数
        latest_citations = existing_data.get('total_citations', 9)
        
        # 智能增长：基于历史趋势估算增长
        citation_trend = existing_data.get('citation_trend', HISTORICAL_CITATIONS)
        if len(citation_trend) >= 2:
            # 计算最近的增长率
            recent_growth = citation_trend[-1]['citations'] - citation_trend[-2]['citations']
            # 保守估计：50%的增长率
            estimated_growth = max(0, int(recent_growth * 0.5))
        else:
            estimated_growth = random.randint(0, 2)  # 保守增长
            
        estimated_citations = latest_citations + estimated_growth
        
        print(f"基于历史数据估算：从 {latest_citations} 增长到 {estimated_citations}")
        
        # 获取现有论文数据并计算H-index
        papers = existing_data.get('papers', {})
        h_index = calculate_h_index(papers) if papers else existing_data.get('h_index', 0)
        
        return {
            "total_citations": estimated_citations,
            "h_index": h_index,
            "papers": papers,
            "citation_trend": citation_trend,
            "fallback_used": True,
            "fallback_reason": "ScrapingBee API failed"
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"读取现有数据失败: {e}，使用默认备用数据")
        return {
            "total_citations": 30,
            "h_index": 1,
            "papers": {
                "Hello again! llm-powered personalized agent for long-term dialogue": {
                    "citations": 29,
                    "year": 2024
                },
                "CryptoX: Compositional Reasoning Evaluation of Large Language Models": {
                    "citations": 1,
                    "year": 2025
                }
            },
            "citation_trend": HISTORICAL_CITATIONS,
            "fallback_used": True,
            "fallback_reason": "No existing data found"
        }

def update_scholar_stats():
    try:
        scholar_id = os.getenv('GOOGLE_SCHOLAR_ID')
        if not scholar_id:
            raise ValueError("环境变量中未找到 Google Scholar ID")
        api_key = os.getenv('SERPAPI_API_KEY')
        if not api_key:
            raise ValueError("环境变量中未找到 SERPAPI_API_KEY（请在仓库 Secrets 配置）")

        print(f"开始更新 Scholar 统计数据 (ID: {scholar_id})")
        
        # 使用 SerpApi 获取数据
        data = get_scholar_data_via_serpapi(scholar_id, api_key)
        
        # 回退：使用本地估算数据
        if data is None:
            data = get_fallback_data()
            data['fallback_reason'] = 'SerpApi API failed or quota exceeded'
        
        # 读取现有的数据文件
        try:
            with open('data/scholar_data.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if 'citation_trend' in existing_data:
                    citation_trend = existing_data['citation_trend']
                else:
                    citation_trend = HISTORICAL_CITATIONS
        except (FileNotFoundError, json.JSONDecodeError):
            print("没有找到现有数据文件或文件损坏，使用历史数据")
            citation_trend = HISTORICAL_CITATIONS

        # 获取当前月份
        current_month = datetime.now().strftime('%Y-%m')
        
        # 检查是否需要添加本月记录
        if not citation_trend or citation_trend[-1]['date'] != current_month:
            citation_trend.append({
                "date": current_month,
                "citations": data['total_citations']
            })
            print(f"添加了 {current_month} 的引用记录")
        else:
            # 更新本月记录
            citation_trend[-1]['citations'] = data['total_citations']
            print(f"更新了 {current_month} 的引用记录")
        
        # 更新趋势数据
        data["citation_trend"] = citation_trend
        
        # 获取 GitHub 星标数
        data["github_stars"] = {
            "leolee99/LD-Agent": get_github_stars("leolee99", "LD-Agent"),
            "multimodal-art-projection/CryptoX": get_github_stars("multimodal-art-projection", "CryptoX"),
            "Syuchin/MARS-Bench": get_github_stars("Syuchin", "MARS-Bench"),
            "randomtutu/FinSearchComp": get_github_stars("randomtutu", "FinSearchComp")
        }

        # 添加最后更新时间
        data["last_updated"] = datetime.now().isoformat()

        # 保存数据
        os.makedirs('data', exist_ok=True)
        with open('data/scholar_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n成功保存数据到 scholar_data.json")

    except Exception as e:
        print(f"更新 scholar 统计数据时出错: {e}")
        print("\n完整错误追踪:")
        traceback.print_exc()
        
        # 即使失败也尝试创建基本数据文件
        try:
            fallback_data = get_fallback_data()
            fallback_data["last_updated"] = datetime.now().isoformat()
            fallback_data["github_stars"] = {
                "leolee99/LD-Agent": get_github_stars("leolee99", "LD-Agent"),
                "multimodal-art-projection/CryptoX": get_github_stars("multimodal-art-projection", "CryptoX"),
                "Syuchin/MARS-Bench": get_github_stars("Syuchin", "MARS-Bench"),
                "randomtutu/FinSearchComp": get_github_stars("randomtutu", "FinSearchComp")
            }
            
            os.makedirs('data', exist_ok=True)
            with open('data/scholar_data.json', 'w', encoding='utf-8') as f:
                json.dump(fallback_data, f, ensure_ascii=False, indent=2)
            print("保存了备用数据到 scholar_data.json")
        except Exception as fallback_error:
            print(f"保存备用数据失败: {fallback_error}")
        
        # 不再抛出异常，让CI继续运行
        print("继续使用可用数据...")

if __name__ == "__main__":
    if os.getenv('TEST_MODE'):
        print("运行测试模式")
        os.environ['GOOGLE_SCHOLAR_ID'] = '8RnQ3EEAAAAJ'  # 测试用ID
    update_scholar_stats()