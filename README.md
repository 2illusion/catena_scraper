# CATENA Journal Article Scraper

从 ScienceDirect 爬取 CATENA 期刊文章的投递时间（Received Date）和接收时间（Accepted Date），并计算审稿周期。

## 功能特性

- ✅ 爬取所有年份/卷的文章列表
- ✅ 提取每篇文章的关键日期信息：
  - Received Date (投递日期)
  - Revised Date (修改日期)
  - Accepted Date (接收日期)
  - Available Online Date (上线日期)
- ✅ 自动计算审稿周期（从投递到接收的天数）
- ✅ 多种导出格式：CSV、Excel、JSON
- ✅ Excel 报告包含统计图表
- ✅ 反爬虫措施（User-Agent 轮换、随机延迟、浏览器指纹保护）
- ✅ 支持按年份/卷号过滤
- ✅ 详细的日志记录
- ✅ **两种爬虫方案**：Playwright 版本和 Selenium 版本（更强反检测）

## 项目结构

```
catena_scraper/
├── main.py                 # 主程序入口 (Playwright 版本)
├── scraper_selenium.py     # 备用爬虫 (Selenium + undetected-chromedriver)
├── requirements.txt        # Python 依赖
├── README.md              # 说明文档
├── config/
│   ├── __init__.py
│   └── settings.py        # 配置文件
├── src/
│   ├── __init__.py
│   ├── scraper.py         # 核心爬虫逻辑 (Playwright)
│   ├── models.py          # 数据模型
│   └── exporter.py        # 数据导出
├── data/                  # 输出数据目录
│   ├── catena_articles.csv
│   ├── catena_articles.xlsx
│   └── catena_articles.json
└── logs/                  # 日志文件目录
```

## 安装

### 1. 克隆项目

```bash
cd catena_scraper
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate   # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装浏览器

**方案一：Playwright（需要安装浏览器）**
```bash
playwright install chromium
```

**方案二：Selenium + undetected-chromedriver（推荐，自动使用本地 Chrome）**
- 只需确保系统已安装 Chrome 浏览器即可

## 使用方法

### 方案一：Playwright 版本

```bash
# 测试模式（10 篇文章）
python main.py --test

# 完整爬取
python main.py

# 指定卷号范围
python main.py --volumes 260-263
```

### 方案二：Selenium 版本（推荐 - 更强的反检测能力）

如果遇到 403 错误，请使用此版本：

```bash
# 测试模式（10 篇文章）
python scraper_selenium.py --test

# 完整爬取
python scraper_selenium.py

# 指定卷号范围
python scraper_selenium.py --volumes 260-263

# 显示浏览器窗口（调试）
python scraper_selenium.py --test

# 无头模式（后台运行）
python scraper_selenium.py --headless --test
```

### 完整参数列表

```bash
# Playwright 版本
python main.py --help

# Selenium 版本
python scraper_selenium.py --help
```

```
optional arguments:
  -h, --help            show this help message and exit
  --test, -t            Test mode: scrape only 10 articles
  --max MAX, -m MAX     Maximum number of articles to scrape
  --volumes VOLUMES, -v VOLUMES
                        Volume range to scrape (e.g., "260-263" or "263")
  --years YEARS, -y YEARS
                        Year range to scrape (e.g., "2024-2025" or "2025")
  --headless            Run in headless mode (Selenium version)
```

## 解决 403 错误

如果遇到 403 Forbidden 错误，请尝试：

1. **使用 Selenium 版本**（推荐）：
   ```bash
   python scraper_selenium.py --test
   ```

2. **不使用无头模式**（让浏览器窗口可见）：
   ```bash
   python scraper_selenium.py --test  # 默认显示窗口
   ```

3. **增加延迟**：编辑代码中的 `random_delay()` 参数

4. **使用代理**：配置 `config/settings.py` 中的 `PROXY`

## 输出数据

### CSV 文件 (`catena_articles.csv`)

包含所有文章的扁平数据，适合在 Excel 或数据分析工具中打开。

| 列名 | 说明 |
|------|------|
| title | 文章标题 |
| url | 文章链接 |
| doi | DOI |
| volume | 卷号 |
| year | 年份 |
| authors | 作者列表 |
| received_date | 投递日期 |
| accepted_date | 接收日期 |
| review_days | 审稿天数 |
| ... | ... |

### Excel 文件 (`catena_articles.xlsx`)

包含多个工作表：

1. **Articles** - 所有文章列表
2. **Statistics** - 统计汇总
3. **By Year** - 按年份统计（含图表）
4. **Distribution** - 审稿周期分布

### JSON 文件 (`catena_articles.json`)

结构化数据，适合程序处理：

```json
{
  "metadata": {
    "exported_at": "2025-01-01T12:00:00",
    "total_articles": 1500,
    "source": "CATENA Journal (ScienceDirect)"
  },
  "articles": [
    {
      "title": "...",
      "received_date": "24 April 2025",
      "accepted_date": "20 November 2025",
      "review_days": 210,
      ...
    }
  ]
}
```

## 注意事项


3. **可能需要代理**：如果遇到访问限制，可配置代理
4. **完整爬取耗时**：CATENA 期刊文章数量较多，完整爬取可能需要数小时

## 技术栈

- Python 3.8+
- Playwright / Selenium + undetected-chromedriver（浏览器自动化）
- BeautifulSoup（HTML 解析）
- OpenPyXL（Excel 导出）


