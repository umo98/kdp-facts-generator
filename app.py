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
        "temperature": 0.7,
    }
    # Timeout'u 60 saniyeye indirdik, model takılırsa uygulama çökmesin
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def is_valid_fact(fact):
    fact = fact.strip()
    sentences = [s for s in fact.split('.') if s.strip()]
    if len(sentences) != 3:
        return False
    word_count = len(fact.split())
    return 21 <= word_count <= 24

def generate_facts_for_category(category_name):
    """Modelin beyin yakan 60'lık sınırını aşmak için 10'arlı paketler halinde sessizce çeker."""
    valid_facts = []
    
    # Arka planda 5 kez istek atacak (5 x 10 = 50 hedefliyoruz)
    for _ in range(5):
        if len(valid_facts) >= 50:
            break
            
        # DİKKAT: Sadece 10 facts istiyoruz ki model timeout olmasın
        prompt = f"""You are a children's book author. Write exactly 10 facts about "{category_name}" for 8-12 year olds.
STRICT RULES:
1. Write exactly one fact per line. Do not use numbers or bullets. Just plain text.
2. Each fact MUST be exactly 3 sentences long.
3. Each fact MUST be exactly between 21 and 24 words long.
Here are the 10 facts:"""
        
        try:
            res = call_openrouter(prompt)
            lines = res.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                # Başta rakam veya tire varsa temizle (örn: "1. " veya "- ")
                if line[0].isdigit():
                    line = ' '.join(line.split()[1:])
                elif line[0] == '-':
                    line = line[1:].strip()
                    
                # Kurallara uyuyor mu ve daha önce listeye eklenmiş mi kontrol et
                if is_valid_fact(line) and line not in valid_facts:
                    valid_facts.append(line)
                    
        except requests.exceptions.Timeout:
            continue # Timeout olursa sessizce diğer pakete geç
        except Exception:
            continue
            
    # Ne bulduysak onu dön (50'yi geçmemeye dikkat ederek)
    return valid_facts[:50]

def render_copy_button(text, index):
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
st.title("📚 KDP 8-12 Yaş Facts Üretici")
st.markdown("Her kategori için arka planda parça parça facts toplanır ve anında listelenir.")

topic = st.text_input("Ana Konuyu Girin (Örn: Texas, Ocean Animals):")

if topic:
    num_cats = st.slider("Kaç tane otomatik alt kategori üretmek istiyorsun?", min_value=1, max_value=8, value=1)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🤖 Otomatik Alt Başlıkları Üret", use_container_width=True):
            with st.spinner("Çocukların ilgisini çekecek başlıklar üretiliyor..."):
                # Modeli yaratıcı olmaya zorlayan özel prompt
                prompt_cats = f"""You are writing a fun fact book for kids aged 8 to 12 about the topic: "{topic}".
Create exactly {num_cats} exciting and catchy subtopic titles. 
Do NOT use boring names like "History", "Geography", or "Introduction". 
Use titles that grab a kid's attention, like "Weird & Fun Facts", "Awesome Animals", "Cool Inventions".
Write them separated by newlines. Do not use numbers or bullets."""
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
            if st.button(f"⚙️ Seçilen Başlıklar İçin Factsleri Üret", use_container_width=True, type="primary"):
                if 'facts_data' not in st.session_state:
                    st.session_state.facts_data = {}
                    
                for cat in selected_cats:
                    with st.spinner(f"'{cat}' toplanıyor (lütfen bekleyin)..."):
                        st.session_state.facts_data[cat] = generate_facts_for_category(cat)
                        
                st.success("Üretim süreci tamamlandı!")

    # Factsleri Gösterme
    if 'facts_data' in st.session_state and st.session_state.facts_data:
        st.write("---")
        st.header("✅ Hazır Factsler")
        
        for cat, facts in st.session_state.facts_data.items():
            current_count = len(facts)
            
            # Kaç tane bulabildiyse onu yazdırıyoruz (Takılmıyor, direkt sonuç veriyoruz)
            title_text = f"📂 {cat} - [{current_count}/50 Geçerli Facts]"
            if current_count < 50:
                title_text = f"⚠️ {cat} - [{current_count}/50 Geçerli Facts (Model yeterli üretmedi)]"
                
            with st.expander(title_text, expanded=False):
                if current_count > 0:
                    for idx, fact in enumerate(facts):
                        render_copy_button(fact, idx)
                else:
                    st.warning("Bu kategori için model geçerli facts üretemedi.")
        
        if st.button("🗑️ Tüm Verileri Temizle ve Yeniden Başla"):
            st.session_state.clear()
            st.rerun()
