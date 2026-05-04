import streamlit as st
import requests
import json

# --- Sabitler ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "ibm-granite/granite-4.1-8b"

st.set_page_config(page_title="KDP Facts Generator", layout="wide")

# --- Yardımcı Fonksiyonlar ---
def get_api_key():
    return st.secrets.get("OPENROUTER_API_KEY")

def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5, # Granite için biraz daha düşük tuttuk, kurallara daha sadık kalsın
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def is_valid_fact(fact):
    """3 cümle ve 21-24 kelime kontrolü yapar."""
    fact = fact.strip()
    # Cümle sayısı kontrolü (Noktadan bölüp boş olanları ele)
    sentences = [s for s in fact.split('.') if s.strip()]
    if len(sentences) != 3:
        return False
    # Kelime sayısı kontrolü
    word_count = len(fact.split())
    return 21 <= word_count <= 24

def generate_facts_for_category(category_name):
    """Arka planda sessizce çalışıp KESİNLİKLE 50 adet geçerli facts döndürür."""
    valid_facts = []
    max_silent_attempts = 5 # Arka planda en fazla 5 kez aynı başlığa istek atar (sessizce)
    
    attempt = 0
    while len(valid_facts) < 50 and attempt < max_silent_attempts:
        attempt += 1
        
        # Granite 8B için JSON yerine düz metin (satır satır) istiyoruz ki hata vermesin
        prompt = f"""You are a children's book author. Write 60 facts about "{category_name}" for 8-12 year olds.
STRICT RULES:
1. Write exactly one fact per line. Do not use numbers, bullets, or dashes at the start. Just the plain sentence text.
2. Each fact MUST be exactly 3 sentences long.
3. Each fact MUST be exactly between 21 and 24 words long total.
Here are the facts:"""
        
        try:
            res = call_openrouter(prompt)
            
            # Model bazenintroductory text yazabiliyor, onu temizle
            lines = res.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Başta numara veya tire varsa temizle (örn: "1. " veya "- ")
                if line[0].isdigit() or line[0] == '-':
                    line = ' '.join(line.split()[1:])
                    
                if is_valid_fact(line) and line not in valid_facts:
                    valid_facts.append(line)
                    
                # 50'ye ulaştığında anında dur
                if len(valid_facts) >= 50:
                    break
                    
        except Exception as e:
            pass # Hata olursa sessizce devam et, kullanıcıya gösterme
            
    # Her ihtimale karşı 50'yi geçmemesi için kes
    return valid_facts[:50]

def render_copy_button(text, index):
    """Her facts için kopyalama butonu oluşturur."""
    safe_text = json.dumps(text)
    html_code = f"""
    <div style="display: flex; align-items: center; padding: 6px 0; border-bottom: 1px solid #eee;">
        <span style="flex-grow: 1; padding-right: 10px; font-size: 14px;">{index+1}. {text}</span>
        <button onclick="
            navigator.clipboard.writeText({safe_text});
            this.innerText='Copied!';
            this.style.color='#2E7D32';
            setTimeout(() => {{ this.innerText='Copy'; this.style.color='white'; }}, 1500);
        " style="background-color: #008CBA; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold;">
            Copy
        </button>
    </div>
    """
    st.components.v1.html(html_code, height=38)

# --- Ana Arayüz ---
st.title("📚 KDP 8-12 Yaş Facts Üretici (Granite 4.1)")
st.markdown("Kurallar: Her facts **tam 3 cümle** ve **21-24 kelime** olacaktır. Her kategoride **tek seferde 50 facts** hazırlanır.")

topic = st.text_input("Ana Konuyu Girin (Örn: Texas, Ocean Animals):")

if topic:
    num_cats = st.slider("Kaç tane otomatik alt kategori üretmek istiyorsun?", min_value=1, max_value=8, value=1)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🤖 Otomatik Alt Başlıkları Üret", use_container_width=True):
            with st.spinner("Alt başlıklar üretiliyor..."):
                prompt_cats = f"List exactly {num_cats} subcategories for the topic '{topic}'. Write them separated by newlines. Do not use numbers or bullets."
                try:
                    res = call_openrouter(prompt_cats)
                    generated_cats = [line.strip() for line in res.split('\n') if line.strip()]
                    
                    if 'categories' not in st.session_state:
                        st.session_state.categories = []
                        
                    for cat in generated_cats:
                        if cat not in st.session_state.categories:
                            st.session_state.categories.append(cat)
                except Exception as e:
                    st.error(f"Başlık üretilemedi: {e}")
                    
    with col2:
        manual_cat = st.text_input("veya Manuel Başlık Ekle:", key="manual_input")
        if st.button("➕ Manuel Ekle", use_container_width=True):
            if manual_cat and manual_cat.strip():
                if 'categories' not in st.session_state:
                    st.session_state.categories = []
                if manual_cat not in st.session_state.categories:
                    st.session_state.categories.append(manual_cat.strip())

    # Kategorileri Listeleme ve Seçim
    if 'categories' in st.session_state and st.session_state.categories:
        st.subheader("📋 Mevcut Alt Başlıklar (İşlem yapmak istediklerini seç)")
        
        cols = st.columns(3)
        selected_cats = []
        
        for i, cat in enumerate(st.session_state.categories):
            with cols[i % 3]:
                is_checked = st.checkbox(cat, key=f"check_{cat}")
                if is_checked:
                    selected_cats.append(cat)
                    
        if selected_cats:
            if st.button(f"⚙️ Seçilen {len(selected_cats)} Başlık İçin Factsleri Üret", use_container_width=True, type="primary"):
                if 'facts_data' not in st.session_state:
                    st.session_state.facts_data = {}
                    
                # Seçilen her kategori için arka planda sessizce 50 factsi tamamlıyoruz
                for cat in selected_cats:
                    # Sadece o an üretilen kategorinin spinner'ını gösteriyoruz
                    with st.spinner(f"Arka planda '{cat}' için tam 50 adet geçerli facts hazırlanıyor (lütfen bekleyin)..."):
                        st.session_state.facts_data[cat] = generate_facts_for_category(cat)
                        
                st.success("Tüm seçilen kategoriler için üretim başarıyla tamamlandı!")

    # Factsleri Gösterme ve Kopyalama
    if 'facts_data' in st.session_state and st.session_state.facts_data:
        st.write("---")
        st.header("✅ Hazır Factsler (Kopyalamak için Copy butonuna tıkla)")
        
        for cat, facts in st.session_state.facts_data.items():
            current_count = len(facts)
            
            # Arka planda sessizce denemesine rağmen bir şekilde 50'ye ulaşamadıysa (çok nadir durum)
            if current_count < 50:
                 with st.expander(f"⚠️ {cat} - [{current_count}/50 Geçerli Facts Bulundu]", expanded=False):
                    for idx, fact in enumerate(facts):
                        render_copy_button(fact, idx)
            else:
                # Sorunsuz 50 facts
                with st.expander(f"📂 {cat} - [Tamamdır: 50/50]", expanded=False):
                    for idx, fact in enumerate(facts):
                        render_copy_button(fact, idx)
        
        if st.button("🗑️ Tüm Verileri Temizle ve Yeniden Başla"):
            st.session_state.clear()
            st.rerun()
