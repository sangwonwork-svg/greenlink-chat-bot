import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA
# 또는 단순하게 아래처럼 유지하되 requirements가 정상 설치되면 해결됩니다.

# --- 1. 보안 설정 (Streamlit Secrets에서 불러오기) ---
# 로컬 테스트 시에는 .streamlit/secrets.toml 파일을 만들어 저장하세요.
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
ACCESS_PASSWORD = st.secrets["ACCESS_PASSWORD"]

st.set_page_config(page_title="사내 매뉴얼 챗봇", layout="centered")

# --- 2. 간단 로그인 기능 ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 접근 제한")
    pwd = st.text_input("접속 비밀번호를 입력하세요:", type="password")
    if st.button("로그인"):
        if pwd == ACCESS_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# --- 3. 매뉴얼 학습 (캐싱) ---
@st.cache_resource
def init_rag():
    # manual.pdf 파일이 루트 디렉토리에 있어야 합니다.
    loader = PyPDFLoader("manual.pdf")
    pages = loader.load_and_split()
    
    # 한국어 문장 유사도 측정에 특화된 모델
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    
    vectorstore = FAISS.from_documents(pages, embeddings)
    return vectorstore

try:
    vector_db = init_rag()
except Exception as e:
    st.error(f"매뉴얼 로딩 중 오류 발생: {e}")
    st.stop()

# --- 4. 채팅 인터페이스 ---
st.title("🤖 사내 매뉴얼 어시스턴트")
st.info("매뉴얼 내용을 바탕으로 답변합니다. 질문을 입력해주세요.")

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
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vector_db.as_retriever(search_kwargs={"k": 3})
        )
        
        # 한국어 답변 유도를 위한 프롬프트 구성
        sys_prompt = f"너는 회사의 매뉴얼 전문가야. 제공된 문서를 바탕으로 반드시 한국어로 답변해줘. 매뉴얼에 없는 내용이라면 '죄송하지만 해당 내용은 매뉴얼에서 찾을 수 없습니다'라고 답해줘. 질문: {prompt}"
        
        with st.spinner("답변을 생성 중입니다..."):
            response = qa_chain.invoke(sys_prompt)
            answer = response["result"]
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
