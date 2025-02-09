import os
import json
from scholarly import scholarly

def update_citations():
    scholar_id = os.getenv('GOOGLE_SCHOLAR_ID')
    if not scholar_id:
        print("Error: GOOGLE_SCHOLAR_ID not set")
        return
    
    try:
        # 获取作者信息
        author = scholarly.search_author_id(scholar_id)
        author_data = scholarly.fill(author)
        
        # Debug: 打印作者数据结构
        print("Author data structure:")
        print(json.dumps(author_data, indent=2))
        
        # 获取论文信息
        papers = {}
        for pub in author_data.get('publications', []):
            try:
                paper_data = scholarly.fill(pub)
                # Debug: 打印论文数据结构
                print("\nPaper data structure:")
                print(json.dumps(paper_data, indent=2))
                
                title = paper_data.get('bib', {}).get('title')
                if title:
                    papers[title] = {
                        'citations': paper_data.get('num_citations', 0),
                        'year': paper_data.get('bib', {}).get('pub_year', 'N/A'),
                        'url': paper_data.get('pub_url', '')
                    }
            except Exception as e:
                print(f"Error processing paper: {str(e)}")
                continue
        
        # 保存数据
        data = {
            'total_citations': author_data.get('citedby', 0),
            'h_index': author_data.get('hindex', 0),
            'papers': papers,
            'last_updated': author_data.get('updated', '')
        }
        
        # 确保 data 目录存在
        os.makedirs('data', exist_ok=True)
        
        # 写入数据
        with open('data/scholar_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        print("Successfully updated citation data")
        
    except Exception as e:
        print(f"Error updating citations: {str(e)}")
        # Debug: 打印完整的错误信息
        import traceback
        traceback.print_exc()

def test_crawler():
    # 测试特定的 Google Scholar ID
    test_id = "8RnQ3EEAAAAJ"  # 你的 Google Scholar ID
    try:
        # 获取作者信息
        author = scholarly.search_author_id(test_id)
        author_data = scholarly.fill(author)
        
        # Debug: 打印完整的作者数据
        print("\nFull author data:")
        print(json.dumps(author_data, indent=2))
        
        print(f"\n作者名: {author_data.get('name', 'N/A')}")
        print(f"总引用数: {author_data.get('citedby', 0)}")
        print(f"h-index: {author_data.get('hindex', 0)}")
        print("\n论文列表:")
        
        # 获取并打印每篇论文的信息
        for pub in author_data.get('publications', []):
            try:
                paper_data = scholarly.fill(pub)
                print("\nPaper data:")
                print(json.dumps(paper_data, indent=2))
                
                title = paper_data.get('bib', {}).get('title', 'N/A')
                print(f"\n标题: {title}")
                print(f"引用数: {paper_data.get('num_citations', 0)}")
                print(f"年份: {paper_data.get('bib', {}).get('pub_year', 'N/A')}")
                print(f"URL: {paper_data.get('pub_url', 'N/A')}")
            except Exception as e:
                print(f"Error processing paper: {str(e)}")
                continue
            
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    if os.getenv('TEST_MODE'):
        test_crawler()
    else:
        update_citations() 