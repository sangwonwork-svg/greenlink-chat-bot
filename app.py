import streamlit as st
from groq import Groq
import fitz  # PDF용
from pptx import Presentation  # PPTX용
import pandas as pd  # Excel용
import os
import olefile # HWP용

# --- 1. 보안 설정 (API 키만 유지) ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# 앱 제목 및 레이아웃 설정
st.set_page_config(page_title="소규모지원사업IoT 챗봇", layout="wide")

# --- 2. 파일 통합 로직 ---
@st.cache_resource
def load_all_documents():
    combined_text = ""
    file_list = []
    
    # 학습용 문서 확장자
    target_extensions = (".pdf", ".pptx", ".txt", ".hwp", ".xlsx", ".xls")
    # 제외할 시스템 파일
    exclude_files = ("requirements.txt", "app.py", "packages.txt")
    
    for file in os.listdir("."):
        if file.lower().endswith(target_extensions) and file not in exclude_files and not file.startswith("."):
            try:
                # 1. PDF
                if file.lower().endswith(".pdf"):
                    doc = fitz.open(file)
                    for page in doc:
                        combined_text += page.get_text() + "\n"
                
                # 2. PPTX
                elif file.lower().endswith(".pptx"):
                    prs = Presentation(file)
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                combined_text += shape.text + "\n"
                
                # 3. Excel
                elif file.lower().endswith((".xlsx", ".xls")):
                    df_dict = pd.read_excel(file, sheet_name=None)
                    for sheet_name, df in df_dict.items():
                        combined_text += f"\n[시트: {sheet_name}]\n"
                        combined_text += df.to_string(index=False) + "\n"
                
                # 4. TXT
                elif file.lower().endswith(".txt"):
                    with open(file, "r", encoding="utf-8") as f:
                        combined_text += f.read() + "\n"
                
                # 5. HWP
                elif file.lower().endswith(".hwp"):
                    if olefile.isOleFile(file):
                        ole = olefile.OleFileIO(file)
                        if "PrvText" in ole.listdir():
                            combined_text += ole.openstream("PrvText").read().decode("utf-16") + "\n"
                
                file_list.append(file)
                
            except Exception as e:
                st.sidebar.error(f"{file} 읽기 실패: {e}")
                
    return combined_text, file_list

# 데이터 로딩
knowledge_base, learned_files = load_all_documents()

# --- 3. 사이드바 (학습 리스트) ---
with st.sidebar:
    st.title("📚 학습된 문서 목록")
    st.info(f"현재 총 {len(learned_files)}개의 파일을 학습했습니다.")
    
    if learned_files:
        for i, name in enumerate(sorted(learned_files), 1):
            st.write(f"{i}. {name}")
    else:
        st.warning("학습된 문서 파일이 없습니다.")
    
    st.divider()
    if st.button("🔄 지식 새로고침"):
        st.cache_resource.clear()
        st.rerun()

# --- 4. 챗봇 UI ---
st.title("🤖 소규모지원사업IoT 챗봇")
st.caption("사내 문서를 기반으로 IoT 지원 사업 관련 정보를 답변해 드립니다.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("문서 내용에 대해 질문하세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        client = Groq(api_key=GROQ_API_KEY)
        
        # 문서 내용 주입 (토큰 제한을 고려하여 상위 4만 자 전달)
        context_text = knowledge_base[:40000] 
        
        messages = [
            {
                "role": "system", 
                "content": f"너는 소규모지원사업 및 IoT 기술 전문가야. 아래 제공된 문서 내용을 바탕으로 답변해줘. 한국어로 친절하게 답변하고, 문서에 명시되지 않은 내용은 모른다고 답해줘.\n\n[문서 내용]\n{context_text}"
            }
        ]
        # 문맥 유지를 위해 최근 5개 대화 포함
        for m in st.session_state.messages[-5:]:
            messages.append({"role": m["role"], "content": m["content"]})

        with st.spinner("답변 생성 중..."):
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    temperature=0
                )
                answer = completion.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"오류 발생: {e}")
