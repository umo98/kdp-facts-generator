import streamlit as st
import requests
import json
import re

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
    response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def clean_json_string(raw_str):
    """Modelin çıktılarını temizleyip düzgün JSON array'e çevirir."""
    raw_str = raw_str.strip()
    if raw_str.startswith("```json"):
        raw_str = raw_str[7:]
    if raw_str.startswith("```"):
        raw_str = raw_str[3:]
    if raw_str.endswith("```"):
        raw_str = raw_str[:-3]
    return raw_str.strip()

def is_valid_fact(fact):
    """3 cümle ve 21-24 kelime kontrolü yapar."""
    fact = fact.strip()
    sentences = [s for s in fact.split('.') if s.strip()]
    if len(sentences) != 3:
        return False
    word_count = len(fact.split())
    return 21 <= word_count <= 24

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

def generate_facts_for_category(category_name):
    """Bir kategori için kesinlikle 50 adet geçerli facts bulana kadar dener."""
    valid_facts = []
    max_attempts = 3
    
    for attempt in range(max_attempts):
        with st.spinner(f"🎯 '{category_name}' için deneme {attempt + 1}/{max_attempts} (Şu an {len(valid_facts)}/50 geçerli facts bulundu)..."):
            prompt = f"""You are a children's book author. Write 60 short facts about "{category_name}" for 8-12 year olds.
STRICT RULES:
1. Output ONLY a valid JSON array of strings. Example: ["Fact 1.", "Fact 2."]
2. Each string MUST be exactly 3 sentences long.
3. Each string MUST be exactly between 21 and 24 words long.
Do not include numbers at the start of the facts."""
            
            try:
                res = call_openrouter(prompt)
                res_clean = clean_json_string(res)
                
                # JSON array içindeki stringleri al
                matches = re.findall(r'"([^"]*)"', res_clean)
                
                for fact in matches:
                    # Fazladan gelen tırnak işaretlerini temizle
                    clean_fact = fact.replace('\\"', '"').replace("\\'", "'")
                    if is_valid_fact(clean_fact) and clean_fact not in valid_facts:
                        valid_facts.append(clean_fact)
                        
                    # 50'ye ulaştığında hemen döngüden çık
                    if len(valid_facts) >= 50:
                        break
                        
            except Exception as e:
                st.error(f"Hata oluştu: {e}")
                
        if len(valid_facts) >= 50:
            break
            
    return valid_facts[:50] # Kesinlikle 50 ile sınırla

# --- Ana Arayüz ---
st.title("📚 KDP 8-12 Yaş Facts Üretici")
st.markdown("Kurallar: Her facts **tam 3 cümle** ve **21-24 kelime** olacaktır. Her kategoride **kesinlikle 50 facts** bulunur.")

topic = st.text_input("Ana Konuyu Girin (Örn: Texas, Ocean Animals):")

if topic:
    # Kategori sayısını belirleme
    num_cats = st.slider("Kaç tane otomatik alt kategori üretmek istiyorsun?", min_value=1, max_value=8, value=1)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🤖 Otomatik Alt Başlıkları Üret", use_container_width=True):
            with st.spinner("Alt başlıklar üretiliyor..."):
                prompt_cats = f"Give exactly {num_cats} subcategories for the topic '{topic}'. Output ONLY a valid JSON array of strings. Example: [\"Sub 1\", \"Sub 2\"]"
                try:
                    res = call_openrouter(prompt_cats)
                    res_clean = clean_json_string(res)
                    generated_cats = json.loads(res_clean)
                    
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
                    st.success(f"'{manual_cat}' eklendi.")
                else:
                    st.warning("Bu başlık zaten listede.")

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
            if st.button(f"⚙️ Seçilen {len(selected_cats)} Başlık İçin Factsleri Üret (Her biri 50'şer adet)", use_container_width=True, type="primary"):
                if 'facts_data' not in st.session_state:
                    st.session_state.facts_data = {}
                    
                for cat in selected_cats:
                    st.session_state.facts_data[cat] = generate_facts_for_category(cat)
                st.success("Üretim süreci tamamlandı!")

    # Factsleri Gösterme ve Kopyalama
    if 'facts_data' in st.session_state and st.session_state.facts_data:
        st.write("---")
        st.header("✅ Hazır Factsler (Kopyalamak için Copy butonuna tıkla)")
        
        for cat, facts in st.session_state.facts_data.items():
            current_count = len(facts)
            
            # Eğer 50'den düşükse, yalnızca o kategori için yeniden deneme butonu koy
            if current_count < 50:
                st.error(f"⚠️ {cat}: Sadece {current_count}/50 geçerli facts üretilebildi.")
                if st.button(f"🔄 '{cat}' Başlığını Tekrar Dene", key=f"retry_{cat}"):
                    st.session_state.facts_data[cat] = generate_facts_for_category(cat)
                    st.rerun()
            else:
                with st.expander(f"📂 {cat} - [Tamamdır: 50/50]", expanded=False):
                    for idx, fact in enumerate(facts):
                        render_copy_button(fact, idx)
        
        # Tümünü Temizle Butonu
        if st.button("🗑️ Tüm Verileri Temizle ve Yeniden Başla"):
            st.session_state.clear()
            st.rerun()
