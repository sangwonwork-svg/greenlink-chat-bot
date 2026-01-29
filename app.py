import streamlit as st
from groq import Groq
import fitz  # PDF용
from pptx import Presentation  # PPTX용
import pandas as pd  # Excel용
import os
import olefile # HWP용

# --- 1. 보안 설정 ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

st.set_page_config(page_title="소규모지원사업IoT 챗봇", layout="wide")

# --- 2. 파일 통합 로직 (캐싱) ---
@st.cache_resource
def load_all_documents():
    combined_text = ""
    file_list = []
    target_extensions = (".pdf", ".pptx", ".txt", ".hwp", ".xlsx", ".xls")
    exclude_files = ("requirements.txt", "app.py", "packages.txt")
    
    for file in os.listdir("."):
        if file.lower().endswith(target_extensions) and file not in exclude_files and not file.startswith("."):
            try:
                if file.lower().endswith(".pdf"):
                    doc = fitz.open(file)
                    for page in doc:
                        combined_text += page.get_text() + "\n"
                elif file.lower().endswith(".pptx"):
                    prs = Presentation(file)
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                combined_text += shape.text + "\n"
                elif file.lower().endswith((".xlsx", ".xls")):
                    df_dict = pd.read_excel(file, sheet_name=None)
                    for sheet_name, df in df_dict.items():
                        combined_text += f"\n[시트: {sheet_name}]\n{df.to_string(index=False)}\n"
                elif file.lower().endswith(".txt"):
                    with open(file, "r", encoding="utf-8") as f:
                        combined_text += f.read() + "\n"
                elif file.lower().endswith(".hwp"):
                    if olefile.isOleFile(file):
                        ole = olefile.OleFileIO(file)
                        if "PrvText" in ole.listdir():
                            combined_text += ole.openstream("PrvText").read().decode("utf-16") + "\n"
                file_list.append(file)
            except Exception as e:
                st.sidebar.error(f"{file} 읽기 실패: {e}")
    return combined_text, file_list

knowledge_base, learned_files = load_all_documents()

# --- 3. 사이드바 구성 ---
with st.sidebar:
    st.title("📚 학습된 문서 목록")
    st.info(f"총 {len(learned_files)}개 문서 학습 완료")
    if learned_files:
        for i, name in enumerate(sorted(learned_files), 1):
            st.write(f"{i}. {name}")
    st.divider()
    if st.button("🔄 지식 새로고침"):
        st.cache_resource.clear()
        st.rerun()

# --- 4. 챗봇 UI ---
st.title("🤖 소규모지원사업IoT 챗봇")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        client = Groq(api_key=GROQ_API_KEY)
        
        # 무료 토큰 한도(TPM)를 고려하여 안전하게 15,000자 내외로 조절
        # 8B 모델은 이 정도 분량도 충분히 빠르게 처리합니다.
        context_text = knowledge_base[:15000] 
        
        messages = [
            {
                "role": "system", 
                "content": f"너는 소규모지원사업IoT 전문가야. 아래 제공된 문서를 바탕으로 한국어로 답변해줘. 문서에 없으면 모른다고 해.\n\n[문서 내용]\n{context_text}"
            }
        ]
        # 문맥 유지를 위해 최근 대화 3개만 포함 (토큰 절약)
        for m in st.session_state.messages[-3:]:
            messages.append({"role": m["role"], "content": m["content"]})

        with st.spinner("답변 중..."):
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.1-8b-instant", # 가장 널널한 무료 모델
                    temperature=0.1,
                )
                answer = completion.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
