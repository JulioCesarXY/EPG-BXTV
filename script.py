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

# Inicializa a sessão principal para a API
session = requests.Session(impersonate="chrome")
session.headers.update(HEADERS)

def is_link_working(url):
    """Faz um teste rápido para checar se a stream está online (Status 200 ou 206)"""
    try:
        # Usamos o método HEAD ou um GET curto para não baixar o arquivo inteiro, apenas testar a resposta
        test_session = requests.Session(impersonate="chrome")
        res = test_session.get(url, timeout=5, stream=True)
        # 200 = OK, 206 = Partial Content (comum em streaming de vídeo)
        if res.status_code in [200, 206]:
            return True
        return False
    except:
        return False

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
    
    # Guarda as streams globais para evitar duplicados entre categorias diferentes
    streams_globais = set()
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        if not categories_map:
            print("[-] Não foi possível obter as categorias.")
            return

        total_canais = 0
        print(f"\n[+] Iniciando extração com checagem de links ativos...")
        
        for cat_name, cat_id in categories_map.items():
            for page in range(1, 4):
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
                        
                        # --- CAPTURA DE LOGO DO WORDPRESS ---
                        channel_logo = ""
                        embedded = post.get('_embedded', {})
                        featured_media_list = embedded.get('wp:featuredmedia', [])
                        
                        if featured_media_list and isinstance(featured_media_list, list):
                            media_details = featured_media_list[0].get('media_details', {})
                            sizes = media_details.get('sizes', {})
                            if sizes.get('medium'):
                                channel_logo = sizes['medium'].get('source_url', '')
                            elif sizes.get('full'):
                                channel_logo = sizes['full'].get('source_url', '')
                            else:
                                channel_logo = featured_media_list[0].get('source_url', '')

                        if not channel_logo:
                            channel_logo = post.get('jetpack_featured_media_url', '')
                        if not channel_logo:
                            img_match = re.search(r'src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp))["\']', html_content)
                            if img_match:
                                channel_logo = img_match.group(1)

                        # Extração bruta de links potenciais
                        streams = re.findall(r'(https?://[^\s"\'\`<>]+?\.(?:m3u8|mpd|ts)[^\s"\'\`<>]*)', html_content)
                        iframes = re.findall(r'src=["\'](https?://[^"\']+)["\']', html_content)
                        
                        all_links = list(set(streams + iframes))
                        
                        # Limpeza inicial de formatos de arquivos inválidos
                        valid_candidates = [l for l in all_links if not any(ext in l for ext in ['.jpg', '.png', '.js', '.css', 'wp-content/plugins', 'googleads'])]

                        # Filtro interno por post para não duplicar links idênticos dentro do mesmo canal
                        streams_do_post = []
                        for stream in valid_candidates:
                            if stream not in streams_globais and stream not in streams_do_post:
                                
                                # VALIDAÇÃO DE REDE: Só aceita se o link responder com sucesso (Status 200/206)
                                if is_link_working(stream):
                                    streams_do_post.append(stream)
                                    streams_globais.add(stream)
                                else:
                                    print(f"   [!] Link descartado (Off-line/Quebrado): {stream[:50]}...")

                        # Gravação dos links validados no arquivo M3U
                        for idx, stream in enumerate(streams_do_post):
                            name_suffix = f" ({idx + 1})" if len(streams_do_post) > 1 else ""
                            logo_attr = f' tvg-logo="{channel_logo}"' if channel_logo else ""
                            
                            f.write(f'#EXTINF:-1 group-title="{cat_name}"{logo_attr}, {channel_title}{name_suffix}\n')
                            f.write(f'{stream}\n\n')
                            total_canais += 1
                            
                except Exception as e:
                    print(f"[-] Erro na paginação: {e}")
                    break
                time.sleep(0.3)
            
        print(f"[V] Lista limpa e validada com sucesso! Total de canais ativos: {total_canais}")

if __name__ == "__main__":
    build_categorized_m3u()
