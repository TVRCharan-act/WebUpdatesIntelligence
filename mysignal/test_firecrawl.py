from mysignal.processors.article_processor import (
    summarize_url,
)

url = (
    "https://openai.com/index/introducing-gpt-5-5"
)

article = summarize_url(
    url
)

print()
print("=" * 80)

print(article.title)

print("=" * 80)

print(article.summary)