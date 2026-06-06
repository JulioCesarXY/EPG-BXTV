import requests
import re
import time
import os

BASE_URL = "https://bx-tv.com/wp-json/wp/v2"

HEADERS = {
    "accept": "application/json",
    "referer": "https://bx-tv.com/",
    "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
}

CF_CLEARANCE = os.getenv("CF_CLEARANCE")
GA_COOKIE = os.getenv("GA_COOKIE", "GA1.2.858734980.1780751968")

if not CF_CLEARANCE:
    print("[-] ERRO: O Secret 'CF_CLEARANCE' não foi configurado no GitHub!")
    exit(1)

COOKIES = {
    "cf_clearance": CF_CLEARANCE,
    "_ga": GA_COOKIE
}

session = requests.Session()
session.headers.update(HEADERS)

def get_categories():
    print("[+] Tentando mapear categorias...")
    try:
        res = session.get(f"{BASE_URL}/categories?per_page=100", cookies=COOKIES, timeout=15)
        print(f"[i] Status da resposta da API de Categorias: {res.status_code}")
        if res.status_code == 200:
            return {cat['name']: cat['id'] for cat in res.json()}
        return {}
    except Exception as e:
        print(f"[-] Erro de conexão na API: {e}")
        return {}

def build_categorized_m3u():
    categories_map = get_categories()
    filename = "canais_bxtv_categorizado.m3u"
    
    # Sempre cria o arquivo para garantir que o Git não quebre as Actions
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        if not categories_map:
            print("[-] Não foi possível obter as categorias. Gerando arquivo M3U limpo por segurança.")
            return

        total_canais = 0
        print(f"\n[+] Iniciando extração...")
        
        for cat_name, cat_id in categories_map.items():
            for page in range(1, 4):
                url_posts = f"{BASE_URL}/posts?categories={cat_id}&per_page=100&page={page}"
                try:
                    res = session.get(url_posts, cookies=COOKIES, timeout=15)
                    if res.status_code != 200:
                        break
                    
                    posts = res.json()
                    if not posts:
                        break

                    for post in posts:
                        channel_title = post.get('title', {}).get('rendered', 'Sem Nome')
                        html_content = post.get('content', {}).get('rendered', '')

                        streams = re.findall(r'(https?://[^\s"\'\`<>]+?\.(?:m3u8|mpd|ts)[^\s"\'\`<>]*)', html_content)
                        iframes = re.findall(r'src=["\'](https?://[^"\']+)["\']', html_content)
                        
                        all_links = list(set(streams + iframes))
                        valid_streams = [l for l in all_links if not any(ext in l for ext in ['.jpg', '.png', '.js', '.css'])]

                        for idx, stream in enumerate(valid_streams):
                            name_suffix = f" ({idx + 1})" if len(valid_streams) > 1 else ""
                            f.write(f'#EXTINF:-1 group-title="{cat_name}", {channel_title}{name_suffix}\n')
                            f.write(f'{stream}\n\n')
                            total_canais += 1
                except:
                    break
                time.sleep(0.3)
            
        print(f"[V] Lista criada com sucesso. Total de canais: {total_canais}")

if __name__ == "__main__":
    build_categorized_m3u()
