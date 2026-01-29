import streamlit as st
from groq import Groq
import fitz  # PyMuPDF

# --- 1. 보안 설정 ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
ACCESS_PASSWORD = st.secrets["ACCESS_PASSWORD"]

st.set_page_config(page_title="매뉴얼 챗봇", layout="centered")

# --- 2. 로그인 기능 ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 매뉴얼 챗봇 로그인")
    pwd = st.text_input("비밀번호를 입력하세요:", type="password")
    if st.button("로그인"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# --- 3. PDF 텍스트 추출 ---
@st.cache_resource
def load_manual_text():
    doc = fitz.open("manual.pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

try:
    manual_content = load_manual_text()
except Exception as e:
    st.error("manual.pdf 파일을 찾을 수 없습니다. GitHub에 파일을 올려주세요.")
    st.stop()

# --- 4. 챗봇 UI ---
st.title("🤖 사내 매뉴얼 가이드")

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

        # 모델에게 전달할 메시지 구성
        messages = [
            {
                "role": "system",
                "content": (
                    "너는 회사 매뉴얼 전문가야. 제공된 매뉴얼 내용을 바탕으로 답변해줘. "
                    "반드시 한국어로 친절하게 답변하고, 매뉴얼에 없는 내용은 모른다고 답해줘."
                    f"\n\n[매뉴얼 내용]\n{manual_content}"
                )
            }
        ]
        for m in st.session_state.messages[-5:]:
            messages.append({"role": m["role"], "content": m["content"]})

        with st.spinner("생각 중..."):
            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.2,
            )
            answer = chat_completion.choices[0].message.content
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
