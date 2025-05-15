
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
API_KEY = os.getenv('QWEN_API_KEY')  # Get API key from environment
MODEL_NAME = "qwen-vl-max"

# Move these constants and function before the route definitions
QWEN_PROMPT = """
Extract the exact content from this financial document image without summarizing. Return your response as a structured JSON object with the following format:

{
  "report_type": "annual" or "quarterly",
  "categories": [
    {
      "name": "category_name",
      "confidence": 0.95,
      "content": {
        "text": "exact extracted text",
        "key_figures": [
          {"label": "Revenue", "value": "1,234,567", "unit": "RM", "year": "2023"}
        ],
        "tables": [
          {
            "title": "exact table title",
            "headers": ["Header1", "Header2"],
            "rows": [["Data1", "Data2"]]
          }
        ]
      }
    }
    // Additional categories as needed
  ]
}

For Quarterly Reports (quarterly):
- financial_statements: Extract all financial statement data, tables, and figures exactly as they appear
- qr_announcement: Identify if this is part of a quarterly report announcement

For Annual Reports (annual):
- financial_statements: Extract all financial statement data, tables, and figures exactly as they appear
- financial_highlights: Key financial metrics, tables, charts, figures for bar charts with exact values
- financial_ratios: All financial ratios presented with exact values and labels
- corporate_directory: Company contact information, addresses, registration numbers exactly as shown
- corporate_structure: Organizational/group structure information exactly as presented
- shareholdings: Major shareholders, shareholding percentages, statistics exactly as listed
- board_of_directors: Board members listing with profiles and details exactly as presented
- key_senior_management: KSM profiles and information exactly as shown
- chairman_statement: Chairman's message/letter with exact text
- md_and_a: Management discussion & analysis section content with exact text

If you encounter content that doesn't fit any predefined categories:
1. Create a new category with a descriptive name that best represents the content
2. Include all extracted content following the same structure
3. Provide a confidence score

Do not summarize or paraphrase the content. Extract the exact text, numbers, and data as they appear in the image.
"""

FINANCIAL_HIGHLIGHTS_PROMPT = """
You are a financial data extraction assistant. Your task is to extract annual financial highlights from the provided content of an annual report and return them in a structured JSON format.

### Extract the following Annual Financial Highlights:
- Revenue (RM Million or equivalent currency)
- Profit/(Loss) Before Tax
- Earnings/(Loss) Attributable to Equity Holders
- Earnings/(Loss) Per Share (sen or local currency unit)
- Shareholders' Funds
- Total Assets
- Bank Borrowings
- Return on Average Shareholders' Funds (%)

### Rules:
1. Extract values only if explicitly mentioned.
2. Convert values into numeric types where possible (e.g., "RM1,645 million" → 1645).
3. Use the appropriate currency units as indicated (RM, USD, etc.).
4. If a field is missing for a given year, set its value to null.
5. Sort years in descending order.
6. Ensure the final output is valid JSON without markdown formatting.

Return your response in this exact JSON format:

{
  "financial_highlights": [
    {
      "year": 2024,
      "revenue_rm_million": 1645,
      "profit_loss_before_tax_rm_million": 75,
      "earnings_loss_attributable_to_equity_holders_rm_million": 64,
      "earnings_loss_per_share_sen": 1.43,
      "shareholders_funds_rm_million": 4620,
      "total_assets_rm_million": 9034,
      "bank_borrowings_rm_million": 848,
      "return_on_average_shareholders_funds_percentage": 1
    }
  ]
}
"""

QUARTERLY_PERFORMANCE_PROMPT = """
You are a financial data extraction assistant. Your task is to extract quarterly performance data from the provided content of an annual report and return them in a structured JSON format.

### Extract the following Quarterly Performance Data:
- Year
- Quarter (e.g., Q1, Q2, YTD)
- Revenue (RM Million)
- Profit Before Taxation
- Profit After Taxation
- Profit Attributable to Equity Holders
- Basic Earnings Per Share (sen)
- Dividend Per Share (sen)
- Net Assets Per Share Attributable to Equity Holders (RM)

### Rules:
1. Extract values only if explicitly mentioned.
2. Convert values into numeric types where possible (e.g., "RM1,645 million" → 1645).
3. Use the appropriate currency units as indicated (RM, USD, etc.).
4. If a field is missing for a given quarter, set its value to null.
5. Sort years in descending order and quarters in chronological order within each year (e.g., Q1, Q2, Q3, Q4, YTD).
6. Ensure the final output is valid JSON without markdown formatting.

Return your response in this exact JSON format:

{
  "quarterly_performance": [
    {
      "year": 2024,
      "quarter": "Q4",
      "revenue_rm_million": 371,
      "profit_before_taxation_rm_million": 5,
      "profit_after_taxation_rm_million": 1,
      "profit_attributable_to_equity_holders_rm_million": 1,
      "basic_earnings_per_share_sen": 0.01,
      "dividend_per_share_sen": 1.00,
      "net_assets_per_share_rm": 1.03
    }
  ]
}
"""