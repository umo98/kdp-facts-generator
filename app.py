import streamlit as st
import requests
import json

# --- Sabitler ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openrouter/owl-alpha"

# --- Sayfa Ayarları ---
st.set_page_config(page_title="KDP 8-12 Age Facts Generator", layout="wide")

# --- Yardımcı Fonksiyonlar ---
def get_api_key():
    return st.secrets.get("OPENROUTER_API_KEY")

def call_openrouter(prompt):
    """OpenRouter API'sine istek atar."""
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-kdp-app.com", # İsteğe bağlı
        "X-Title": "KDP Facts Generator"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def is_valid_fact(fact):
    """Factsin tam 3 cümle ve 21-24 kelime olup olmadığını kontrol eder."""
    fact = fact.strip()
    # Cümle sayısı kontrolü (noktadan bölüp boşlukları sileriz)
    sentences = [s for s in fact.split('.') if s.strip()]
    if len(sentences) != 3:
        return False, f"Not 3 sentences ({len(sentences)} sentences)"
    
    # Kelime sayısı kontrolü
    word_count = len(fact.split())
    if 21 <= word_count <= 24:
        return True, "Valid"
    else:
        return False, f"Word count is {word_count}"

def render_copy_button(text, index):
    """Streamlit içinde tek tıkla kopyalama butonu oluşturur."""
    # JSON dumps ile metin içindeki tırnak işaretlerinin Javascript'te bozulmasını engelleriz
    safe_text = json.dumps(text)
    html_code = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #eeeeee;">
        <span style="font-size: 15px; color: #333333; flex-grow: 1; padding-right: 15px;">
            {index+1}. {text}
        </span>
        <button onclick="
            navigator.clipboard.writeText({safe_text});
            this.innerText='Copied!';
            this.style.backgroundColor='#2E7D32';
            setTimeout(() => {{
                this.innerText='Copy';
                this.style.backgroundColor='#4CAF50';
            }}, 2000);
        " style="background-color: #4CAF50; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;">
            Copy
        </button>
    </div>
    """
    st.components.v1.html(html_code, height=45)

# --- Ana Arayüz ---
st.title("📚 Amazon KDP Facts Generator (8-12 Age)")
st.markdown("Bu uygulama belirlediğiniz konu için tam 8 alt başlık ve her başlıkta 50 adet (toplam 400) facts üretir. Her facts **tam 3 cümle** ve **21-24 kelime** kuralına göre filtrelenir.")

topic = st.text_input("Ana Konuyu Girin (Örn: Texas, Ocean Animals, Ancient Egypt):", placeholder="örn: Space Exploration")

if topic:
    st.write("---")
    
    # ADIM 1: 8 Alt Başlığı Üret
    if st.button("🚀 1. Adım: 8 Alt Başlığı Üret", use_container_width=True):
        with st.spinner(f"'{topic}' için alt başlıklar owl-alpha tarafından üretiliyor..."):
            prompt_categories = f"Give exactly 8 subcategories for the topic '{topic}' suitable for an 8-12 year old's fact book. Output ONLY a valid JSON array of 8 strings. Example: [\"Sub 1\", \"Sub 2\", \"Sub 3\", \"Sub 4\", \"Sub 5\", \"Sub 6\", \"Sub 7\", \"Sub 8\"]. No other text."
            try:
                res = call_openrouter(prompt_categories)
                # Model bazen ```json ``` ekleyebilir, onu temizliyoruz
                res_clean = res.replace("```json", "").replace("```", "").strip()
                st.session_state['categories'] = json.loads(res_clean)
                st.success("8 Alt başlık başarıyla oluşturuldu!")
            except Exception as e:
                st.error(f"Bir hata oluştu: {e}\n\nModelin ham çıktısı:\n{res}")

    # Eğer başlıklar oluşturulduysa göster
    if 'categories' in st.session_state:
        st.subheader("Oluşturulan 8 Alt Başlık:")
        cols = st.columns(4)
        for i, cat in enumerate(st.session_state['categories']):
            with cols[i % 4]:
                st.info(f"**{i+1}.** {cat}")

        # ADIM 2: 400 Factsi Üret
        if st.button("⚙️ 2. Adım: Tüm Factsleri Üret ve Filtrele (Biraz zaman alabilir)", use_container_width=True):
            st.session_state['facts_data'] = {}
            progress_text = st.empty()
            progress_bar = st.progress(0)
            
            total_cats = len(st.session_state['categories'])
            
            for i, cat in enumerate(st.session_state['categories']):
                progress_text.text(f"🎯 '{cat}' için 50 facts üretiliyor... ({i+1}/{total_cats})")
                
                prompt_facts = f"""You are a children's book author. Write exactly 50 facts about "{cat}" for 8-12 year olds.
STRICT RULES:
1. Output MUST be a valid JSON array of exactly 50 strings.
2. Each string MUST be exactly 3 sentences long.
3. Each string MUST be exactly 21 to 24 words long total.
Do not include any text outside the JSON array."""
                
                try:
                    res = call_openrouter(prompt_facts)
                    res_clean = res.replace("```json", "").replace("```", "").strip()
                    facts_list = json.loads(res_clean)
                    st.session_state['facts_data'][cat] = facts_list
                except Exception as e:
                    st.error(f"'{cat}' başlığında hata: {e}")
                    st.session_state['facts_data'][cat] = []
                
                progress_bar.progress((i + 1) / total_cats)
            
            progress_text.text("✅ Tüm üretim tamamlandı!")
            st.success("Factsler başarıyla oluşturuldu. Aşağıdan kontrol edip kopyalayabilirsiniz.")

    # ADIM 3: Factsleri Göster ve Kopyala
    if 'facts_data' in st.session_state and st.session_state['facts_data']:
        st.write("---")
        st.header("📋 Üretilen ve Filtrelenen Factsler")
        st.caption("🟢 Yeşil olanlar kurallara uygundur (3 cümle, 21-24 kelime) ve kopyalanabilir. 🔴 Kırmızı olanlar yapay zekanın kuralları dışına çıktığı için elenmiştir.")
        
        for cat, facts in st.session_state['facts_data'].items():
            valid_facts = []
            invalid_facts = []
            
            for fact in facts:
                is_valid, reason = is_valid_fact(fact)
                if is_valid:
                    valid_facts.append(fact)
                else:
                    invalid_facts.append((fact, reason))
            
            with st.expander(f"📂 {cat} (✅ {len(valid_facts)} Geçerli / ❌ {len(invalid_facts)} Geçersiz)"):
                if valid_facts:
                    for idx, fact in enumerate(valid_facts):
                        render_copy_button(fact, idx)
                else:
                    st.warning("Bu kategori için geçerli facts bulunamadı.")
                
                if invalid_facts:
                    with st.container():
                        st.markdown("<details><summary>❌ Geçersiz Factsleri Göster (Kopyalanamaz)</summary>", unsafe_allow_html=True)
                        for fact, reason in invalid_facts:
                            st.markdown(f"- *{reason}* ➔ {fact}")
                        st.markdown("</details>", unsafe_allow_html=True)
