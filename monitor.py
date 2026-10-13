#!/usr/bin/env python3
"""
GitHub AI Trend Monitor
- Fetches top 5 hot AI repos and 3 cold-but-promising AI repos daily
- Pushes results to WeChat Work (企业微信) bot webhook
"""
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
WECHAT_WEBHOOK = os.environ.get('WECHAT_WEBHOOK', '')

HEADERS = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'AI-Trend-Monitor-Bot'
}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'token {GITHUB_TOKEN}'


def search_repos(q, sort='stars', order='desc', per_page=5):
    url = 'https://api.github.com/search/repositories'
    params = {'q': q, 'sort': sort, 'order': order, 'per_page': per_page}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get('items', [])
    except Exception as e:
        print(f'[ERROR] search failed: {e}', file=sys.stderr)
        return []


def get_hot_ai():
    """Top 5 trending AI repos by stars."""
    # topic:llm 是当前 AI 最热的标签，结果足够代表全球热点
    return search_repos(
        'topic:llm',
        sort='stars', order='desc', per_page=5
    )


def get_cold_ai():
    """3 promising new AI repos: created recently, low stars, actively updated."""
    # New repos (created in last 180 days), 5-80 stars, sorted by recent push
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).strftime('%Y-%m-%d')
    return search_repos(
        f'topic:ai created:>{cutoff} stars:5..80',
        sort='updated', order='desc', per_page=5
    )


def truncate(text, n=120):
    if not text:
        return ''
    text = text.replace('\n', ' ').strip()
    return text[:n] + '…' if len(text) > n else text


def translate_to_zh(text):
    """Translate English text to Chinese via MyMemory free API (no key needed)."""
    if not text:
        return ''
    try:
        r = requests.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text, 'langpair': 'en|zh-CN'},
            timeout=10
        )
        data = r.json()
        translated = data.get('responseData', {}).get('translatedText', '')
        if translated and 'MYMEMORY WARNING' not in translated.upper():
            return translated.strip()
        return text
    except Exception as e:
        print(f'  [translate fail: {e}]', file=sys.stderr)
        return text


def build_message(hot, cold):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'## GitHub AI 日报 ({now})',
        '',
        '### 🔥 全球热点 Top 5',
        ''
    ]
    for i, repo in enumerate(hot, 1):
        desc = truncate(repo.get('description'))
        zh = translate_to_zh(desc) if desc else '无描述'
        lines.append(
            f'{i}. **[{repo["full_name"]}]({repo["html_url"]})** '
            f'⭐{repo["stargazers_count"]} · {repo.get("language") or "-"}'
        )
        lines.append(f'   > {zh}')

    lines.extend(['', '### 🧊 冷门潜力股', ''])
    for i, repo in enumerate(cold[:3], 1):
        desc = truncate(repo.get('description'))
        zh = translate_to_zh(desc) if desc else '无描述'
        lines.append(
            f'{i}. **[{repo["full_name"]}]({repo["html_url"]})** '
            f'⭐{repo["stargazers_count"]} · {repo.get("language") or "-"}'
        )
        lines.append(f'   > {zh}')

    return '\n'.join(lines)


def send_wechat(content):
    if not WECHAT_WEBHOOK:
        print('[WARN] WECHAT_WEBHOOK not set, skipping push.')
        return
    payload = {'msgtype': 'markdown', 'markdown': {'content': content}}
    try:
        r = requests.post(WECHAT_WEBHOOK, json=payload, timeout=15)
        print(f'[WeChat] {r.status_code}: {r.text}')
    except Exception as e:
        print(f'[ERROR] wechat push failed: {e}', file=sys.stderr)


if __name__ == '__main__':
    print('=== Fetching hot AI repos ===')
    hot = get_hot_ai()
    print(f'Got {len(hot)} hot repos')

    print('=== Fetching cold AI repos ===')
    cold = get_cold_ai()
    print(f'Got {len(cold)} cold repos')

    msg = build_message(hot, cold)
    print('\n--- Message Preview ---')
    print(msg)
    print('--- End Preview ---\n')

    send_wechat(msg)
    print('Done.')
