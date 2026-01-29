import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings # 한국어 최적화용
from langchain.chains import RetrievalQA

# --- 1. 환경 설정 ---
GROQ_API_KEY = "여기에_Groq_API_키를_입력하세요"
ACCESS_PASSWORD = "우리끼리비번" # 담당자 3명만 공유할 비번

st.set_page_config(page_title="사내 매뉴얼 챗봇", layout="centered")

# --- 2. 로그인 체크 ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pwd = st.text_input("접속 비밀번호를 입력하세요:", type="password")
    if pwd == ACCESS_PASSWORD:
        st.session_state.auth = True
        st.rerun()
    else:
        if pwd: st.error("비밀번호가 틀렸습니다.")
        st.stop()

# --- 3. 데이터 로딩 (캐싱 처리로 속도 향상) ---
@st.cache_resource
def load_manual():
    # PDF 로드 (매뉴얼 파일명을 'manual.pdf'로 해서 같은 폴더에 두세요)
    loader = PyPDFLoader("manual.pdf")
    pages = loader.load_and_split()
    
    # 한국어 성능이 좋은 무료 임베딩 모델
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    
    # 벡터 DB 생성
    vectorstore = FAISS.from_documents(pages, embeddings)
    return vectorstore

vector_db = load_manual()

# --- 4. 챗봇 UI ---
st.title("📄 사내 매뉴얼 지식고")
st.caption("담당자 전용 매뉴얼 검색 서비스 (모바일 지원)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 내역 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 질문 입력
if prompt := st.chat_input("매뉴얼 내용을 물어보세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Groq의 Llama 3.3 70B 모델 호출
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )
        
        # RAG 체인 생성
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vector_db.as_retriever()
        )
        
        # 답변 생성 (한국어 강조 프롬프트 포함)
        response = qa_chain.invoke(f"반드시 한국어로 친절하게 답변해줘. 매뉴얼에 없는 내용은 모른다고 말해줘. 질문: {prompt}")
        answer = response["result"]
        
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
