import streamlit as st
from groq import Groq
import fitz  # PDF용
from pptx import Presentation  # PPTX용
import os
import olefile # HWP용

# --- 1. 보안 설정 ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
ACCESS_PASSWORD = st.secrets["ACCESS_PASSWORD"]

st.set_page_config(page_title="사내 통합 지식고", layout="centered")

# --- 2. 로그인 ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 지식고 로그인")
    pwd = st.text_input("비밀번호 입력:", type="password")
    if st.button("접속"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# --- 3. 다양한 파일에서 텍스트 추출하는 함수 ---
def extract_text():
    combined_text = ""
    # 현재 폴더의 모든 파일을 검사
    for file in os.listdir("."):
        try:
            # 1. PDF 처리
            if file.endswith(".pdf"):
                doc = fitz.open(file)
                for page in doc:
                    combined_text += page.get_text()
            # 2. PPTX 처리
            elif file.endswith(".pptx"):
                prs = Presentation(file)
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            combined_text += shape.text + "\n"
            # 3. TXT 처리
            elif file.endswith(".txt"):
                with open(file, "r", encoding="utf-8") as f:
                    combined_text += f.read()
            # 4. HWP 처리 (기본적인 텍스트 추출)
            elif file.endswith(".hwp"):
                if olefile.isOleFile(file):
                    ole = olefile.OleFileIO(file)
                    if "PrvText" in ole.listdir():
                        combined_text += ole.openstream("PrvText").read().decode("utf-16")
        except Exception as e:
            st.warning(f"{file} 읽기 실패: {e}")
            
    return combined_text

@st.cache_resource
def get_all_knowledge():
    return extract_text()

knowledge_base = get_all_knowledge()

if not knowledge_base.strip():
    st.error("학습할 수 있는 파일(*.pdf, *.pptx, *.txt, *.hwp)이 없습니다.")
    st.stop()

# --- 4. 챗봇 UI ---
st.title("🤖 통합 매뉴얼 어시스턴트")
st.caption("사내의 모든 문서를 학습하여 답변합니다.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("궁금한 점을 물어보세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        client = Groq(api_key=GROQ_API_KEY)
        
        messages = [
            {
                "role": "system",
                "content": (
                    "너는 사내 문서 전문가야. 아래 제공된 다양한 문서 내용을 바탕으로 답변해줘. "
                    "반드시 한국어로 답변하고, 문서에 없는 내용은 모른다고 답해줘."
                    f"\n\n[문서 통합 내용]\n{knowledge_base[:15000]}" # 토큰 제한을 고려해 일부 조절 가능
                )
            }
        ]
        # 최근 대화 문맥 유지
        for m in st.session_state.messages[-3:]:
            messages.append({"role": m["role"], "content": m["content"]})

        with st.spinner("답변 생성 중..."):
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    temperature=0.1,
                )
                answer = completion.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"오류 발생: {e}")
