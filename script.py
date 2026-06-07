from curl_cffi import requests
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

if not CF_CLEARANCE:
    print("[-] ERRO: O Secret 'CF_CLEARANCE' não foi configurado no GitHub!")
    exit(1)

COOKIES = {
    "cf_clearance": CF_CLEARANCE
}

session = requests.Session(impersonate="chrome")
session.headers.update(HEADERS)

def get_categories():
    print("[+] Tentando mapear categorias...")
    try:
        res = session.get(f"{BASE_URL}/categories?per_page=100", cookies=COOKIES, timeout=15)
        if res.status_code == 200:
            return {cat['name']: cat['id'] for cat in res.json()}
        return {}
    except Exception as e:
        print(f"[-] Erro de conexão na API: {e}")
        return {}

def build_categorized_m3u():
    categories_map = get_categories()
    filename = "canais_bxtv_categorizado.m3u"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        if not categories_map:
            print("[-] Não foi possível obter as categorias.")
            return

        total_canais = 0
        print(f"\n[+] Iniciando extração com injeção de mídias (_embed)...")
        
        for cat_name, cat_id in categories_map.items():
            for page in range(1, 4):
                # O segredo está no &_embed adicionado aqui no final
                url_posts = f"{BASE_URL}/posts?categories={cat_id}&per_page=100&page={page}&_embed"
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
                        
                        # --- CAPTURA AVANÇADA DE LOGO DO WORDPRESS ---
                        channel_logo = ""
                        
                        # 1. Tenta pegar a imagem nativa embutida pelo WP devido ao uso do _embed
                        embedded = post.get('_embedded', {})
                        featured_media_list = embedded.get('wp:featuredmedia', [])
                        
                        if featured_media_list and isinstance(featured_media_list, list):
                            # Pega a URL do primeiro objeto de mídia de destaque disponível
                            media_details = featured_media_list[0].get('media_details', {})
                            # Tenta pegar um tamanho médio ou otimizado se houver
                            sizes = media_details.get('sizes', {})
                            if sizes.get('medium'):
                                channel_logo = sizes['medium'].get('source_url', '')
                            elif sizes.get('full'):
                                channel_logo = sizes['full'].get('source_url', '')
                            else:
                                channel_logo = featured_media_list[0].get('source_url', '')

                        # 2. Segunda alternativa: se não veio no embed, tenta chaves variantes comuns da raiz
                        if not channel_logo:
                            channel_logo = post.get('jetpack_featured_media_url', '')
                        if not channel_logo:
                            channel_logo = post.get('f_featured_image_url', '')

                        # 3. Terceira alternativa: varre o HTML por tags normais de imagem do post
                        if not channel_logo:
                            img_match = re.search(r'src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html_content)
                            if img_match:
                                channel_logo = img_match.group(1)

                        # Extração de streams normais (.m3u8 / iframes)
                        streams = re.findall(r'(https?://[^\s"\'\`<>]+?\.(?:m3u8|mpd|ts)[^\s"\'\`<>]*)', html_content)
                        iframes = re.findall(r'src=["\'](https?://[^"\']+)["\']', html_content)
                        
                        all_links = list(set(streams + iframes))
                        valid_streams = [l for l in all_links if not any(ext in l for ext in ['.jpg', '.png', '.js', '.css'])]

                        for idx, stream in enumerate(valid_streams):
                            name_suffix = f" ({idx + 1})" if len(valid_streams) > 1 else ""
                            
                            logo_attr = f' tvg-logo="{channel_logo}"' if channel_logo else ""
                            
                            f.write(f'#EXTINF:-1 group-title="{cat_name}"{logo_attr}, {channel_title}{name_suffix}\n')
                            f.write(f'{stream}\n\n')
                            total_canais += 1
                except Exception as e:
                    print(f"[-] Ocorreu uma falha na paginação: {e}")
                    break
                time.sleep(0.5)
            
        print(f"[V] Lista recriada com sucesso. Total de canais mapeados: {total_canais}")

if __name__ == "__main__":
    build_categorized_m3u()
