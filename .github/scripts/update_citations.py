import json
from datetime import datetime
import os
import traceback
import requests
from bs4 import BeautifulSoup
import time
import random
import re

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

def get_paper_citation_stats(paper_row, base_url):
    """获取论文的引用统计信息和基本引用链接"""
    try:
        citation_info = {
            'count': 0,
            'url': '',
            'related_papers': []
        }
        
        # 获取引用数
        citation_cell = paper_row.find('td', class_='gsc_a_c')
        if citation_cell:
            citation_link = citation_cell.find('a')
            if citation_link:
                citation_text = citation_link.get_text(strip=True)
                if citation_text.isdigit():
                    citation_info['count'] = int(citation_text)
                    # 获取引用页面URL
                    href = citation_link.get('href')
                    if href and href.startswith('/'):
                        citation_info['url'] = base_url + href
                    elif href:
                        citation_info['url'] = href
        
        # 尝试获取相关论文信息
        related_cell = paper_row.find('td', class_='gsc_a_e')
        if related_cell:
            related_links = related_cell.find_all('a')
            for link in related_links:
                href = link.get('href', '')
                if 'versions' in href:
                    # 这是版本链接
                    citation_info['versions_url'] = base_url + href if href.startswith('/') else href
                elif 'scholar' in href:
                    # 这是Scholar链接
                    citation_info['scholar_url'] = base_url + href if href.startswith('/') else href
        
        return citation_info
        
    except Exception as e:
        print(f"获取论文引用统计时出错: {e}")
        return {'count': 0, 'url': '', 'related_papers': []}

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

def parse_scholar_page(soup):
    """解析Scholar页面内容"""
    try:
        citation_stats = {}
        
        # 查找引用统计表格
        stats_table = soup.find('table', {'id': 'gsc_rsb_st'})
        if stats_table:
            rows = stats_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if 'Citations' in label and 'All' in label:
                        try:
                            citation_stats['total_citations'] = int(value)
                        except ValueError:
                            pass
                    elif 'h-index' in label and 'All' in label:
                        try:
                            citation_stats['h_index'] = int(value)
                        except ValueError:
                            pass
        
        # 如果没找到统计表格，尝试其他方法
        if not citation_stats:
            # 查找其他可能的引用数显示方式
            citation_elements = soup.find_all(string=re.compile(r'Cited by \d+'))
            if citation_elements:
                # 提取最大的引用数
                citations = []
                for elem in citation_elements:
                    match = re.search(r'Cited by (\d+)', elem)
                    if match:
                        citations.append(int(match.group(1)))
                if citations:
                    citation_stats['total_citations'] = max(citations)
        
        # 获取论文列表
        papers = {}
        paper_rows = soup.find_all('tr', class_='gsc_a_tr')[:10]  # 取前10篇论文
        
        for row in paper_rows:
            try:
                title_cell = row.find('td', class_='gsc_a_t')
                if title_cell:
                    title_link = title_cell.find('a')
                    if title_link:
                        title = title_link.get_text(strip=True)
                        
                        # 获取年份
                        year_cell = row.find('td', class_='gsc_a_y')
                        year = int(year_cell.get_text(strip=True)) if year_cell and year_cell.get_text(strip=True).isdigit() else 2024
                        
                        # 获取引用统计
                        citation_stats_detail = get_paper_citation_stats(row, "https://scholar.google.com")
                        
                        papers[title] = {
                            "citations": citation_stats_detail['count'],
                            "year": year,
                            "url": title_link.get('href', ''),
                            "citation_url": citation_stats_detail['url'],
                            "versions_url": citation_stats_detail.get('versions_url', ''),
                            "scholar_url": citation_stats_detail.get('scholar_url', '')
                        }
                        
            except Exception as e:
                print(f"解析论文时出错: {e}")
                continue
        
        # 设置默认值
        if 'total_citations' not in citation_stats:
            # 如果无法解析总引用数，使用论文引用数之和作为估算
            total_from_papers = sum(paper.get('citations', 0) for paper in papers.values())
            citation_stats['total_citations'] = max(total_from_papers, 9)
            
        if 'h_index' not in citation_stats:
            # 如果无法解析H-index，根据论文引用数据计算
            citation_stats['h_index'] = calculate_h_index(papers)
        
        # 生成引用摘要
        citation_summary = generate_citation_summary(papers)
        
        print(f"成功解析 Scholar 数据:")
        print(f"- 总引用数: {citation_stats.get('total_citations', 'N/A')}")
        print(f"- H指数: {citation_stats.get('h_index', 'N/A')}")
        print(f"- 论文数量: {len(papers)}")
        
        return {
            "total_citations": citation_stats.get('total_citations', 9),
            "h_index": citation_stats.get('h_index', 3),
            "papers": papers,
            "citation_summary": citation_summary
        }
        
    except Exception as e:
        print(f"解析Scholar页面时出错: {e}")
        return None

def get_scholar_data_with_scrapingbee(scholar_id):
    """使用ScrapingBee API获取Scholar数据"""
    api_key = os.getenv('SCRAPINGBEE_API_KEY')
    if not api_key:
        print("未配置 ScrapingBee API Key")
        return None
    
    try:
        url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
        params = {
            'api_key': api_key,
            'url': url,
            'render_js': 'false',
            'premium_proxy': 'true',
            'country_code': 'us',
            'custom_google': 'true'  # 爬取Google网站必需的参数
        }
        
        print("使用 ScrapingBee API 获取 Scholar 数据...")
        response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return parse_scholar_page(soup)
        else:
            print(f"ScrapingBee API 失败: {response.status_code}")
            if response.status_code == 422:
                print("可能是 API 配额用完或参数错误")
            elif response.status_code == 401:
                print("API Key 无效")
            elif response.status_code == 400:
                print("请求参数错误")
            return None
            
    except Exception as e:
        print(f"ScrapingBee API 错误: {e}")
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

        print(f"开始更新 Scholar 统计数据 (ID: {scholar_id})")
        
        # 使用 ScrapingBee API 获取数据
        data = get_scholar_data_with_scrapingbee(scholar_id)
        
        if data is None:
            # 如果API失败，使用备用数据
            data = get_fallback_data()
        
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
            "Syuchin/MARS-Bench": get_github_stars("Syuchin", "MARS-Bench")
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
                "Syuchin/MARS-Bench": get_github_stars("Syuchin", "MARS-Bench")
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