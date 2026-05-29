import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/api/dart/query"

st.set_page_config(
    page_title="DART Insight Copilot",
    layout="wide",
)
st.title("DART Insight Copilot")
st.caption("OpenDART 공시 데이터 + K-IFRS 회계기준을 결합한 multi-agent 분석 시스템")


def render_citations(cits: list[dict]) -> None:
    if not cits:
        return
    with st.expander(f"인용 ({len(cits)}건)"):
        for c in cits:
            st.markdown(f"**[{c.get('source', '')}]** {c.get('label', '')}")
            bits = []
            if c.get('paragraph'):
                bits.append(f"문단 {c['paragraph']}")
            if c.get('rcept_no'):
                bits.append(f"rcept_no {c['rcept_no']}")
            if c.get('source_file'):
                bits.append(c['source_file'])
            if bits:
                st.caption(" · ".join(bits))
            st.divider()


with st.sidebar:
    st.header("예시 질문")
    EXAMPLES = [
        "삼성전자 2023년 매출액과 영업이익 알려줘",
        "삼성전자 매출이 2020년부터 2024년까지 어떻게 변했어?",
        "삼성전자와 같은 업종 회사들의 2023년 매출을 비교해줘",
        "삼성전자 2023년 사업보고서의 사업 내용을 요약해줘",
        "한화오션이 2017년에 낸 정정공시는 뭘 어떻게 바꿨어?",
        "수익 인식 시점 관련 K-IFRS 기준을 알려줘",
    ]
    for i, ex in enumerate(EXAMPLES):
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.queued_query = ex
            st.rerun()

    st.divider()
    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        render_citations(m.get("citations") or [])

queued = st.session_state.pop("queued_query", None)
prompt = st.chat_input("질문을 입력하세요") or queued

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("분석 중..."):
            content = ""
            citations = []
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]
                r = requests.post(
                    API_URL,
                    json={"question": prompt, "history": history},
                    timeout=180,
                )
                r.raise_for_status()
                data = r.json()
                error = data.get("error")
                citations = data.get("citations") or []

                if error:
                    content = f"오류: {error}"
                    st.error(content)
                else:
                    content = data.get("answer", "")
                    st.markdown(content)

                render_citations(citations)
                
            except requests.exceptions.HTTPError:
                detail = ""
                try:
                    detail = r.json().get("detail", "")
                except Exception:
                    pass
                content = f"백엔드 오류 (HTTP {r.status_code}): {detail}"
                st.error(content)
            except requests.exceptions.RequestException as e:
                content = f"백엔드 통신 실패 - uvicorn이 띄워져 있는지 확인하세요: {e}"
                st.error(content)

        st.session_state.messages.append({
            "role": "assistant",
            "content": content,
            "citations": citations,
        })