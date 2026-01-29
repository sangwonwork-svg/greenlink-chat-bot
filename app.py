import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# 경로를 더 명확하게 수정했습니다.
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# --- 1. 보안 설정 ---
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
ACCESS_PASSWORD = st.secrets["ACCESS_PASSWORD"]

st.set_page_config(page_title="사내 매뉴얼 챗봇", layout="centered")

# --- 2. 로그인 기능 ---
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
    loader = PyPDFLoader("manual.pdf")
    pages = loader.load_and_split()
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
        
        # 최신 방식의 프롬프트 구성
        system_prompt = (
            "너는 회사의 매뉴얼 전문가야. "
            "아래 제공된 문서를 바탕으로 반드시 한국어로 친절하게 답변해줘. "
            "매뉴얼에 없는 내용이라면 '죄송하지만 해당 내용은 매뉴얼에서 찾을 수 없습니다'라고 답해줘."
            "\n\n"
            "{context}"
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        # 최신 방식의 RAG 체인 생성
        question_answer_chain = create_stuff_documents_chain(llm, prompt_template)
        rag_chain = create_retrieval_chain(vector_db.as_retriever(), question_answer_chain)
        
        with st.spinner("답변을 생성 중입니다..."):
            response = rag_chain.invoke({"input": prompt})
            answer = response["answer"]
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
