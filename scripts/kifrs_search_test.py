from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

PERSIST_DIR = "cache/kifrs_chroma"
COLLECTION_NAME = "kifrs"
EMBEDDING_MODEL = "text-embedding-3-large"


QUERIES = [
    # 1. 수익
    (
        "고객과의 계약에서 재화나 용역의 통제가 고객에게 이전되는 "
        "시점의 수익 인식 기준",
        "K-IFRS 1115",
    ),

    # 2. 리스
    (
        "리스이용자의 사용권자산과 리스부채 인식 및 측정 방법",
        "K-IFRS 1116",
    ),

    # 3. 금융상품 손상
    (
        "금융자산의 기대신용손실과 손실충당금 인식 및 측정 방법",
        "K-IFRS 1109",
    ),

    # 4. 재고자산
    (
        "재고자산을 취득원가와 순실현가능가치 중 낮은 금액으로 "
        "측정하는 회계처리 기준",
        "K-IFRS 1002",
    ),

    # 5. 유형자산
    (
        "유형자산의 감가상각 개시 시점과 내용연수 및 "
        "감가상각방법의 검토 기준",
        "K-IFRS 1016",
    ),

    # 6. 법인세
    (
        "당기법인세와 이연법인세 자산 및 부채의 인식과 측정 기준",
        "K-IFRS 1012",
    ),

    # 7. 보험계약
    (
        "보험계약의 일반측정모형과 보험계약마진 측정 방법",
        "K-IFRS 1117",
    ),

    # 8. 재무제표 표시
    (
        "전체 재무제표의 구성요소와 재무상태표 및 포괄손익계산서의 "
        "표시 원칙",
        "K-IFRS 1001",
    ),

    # 9. 현금흐름표
    (
        "현금흐름을 영업활동 투자활동 재무활동으로 구분하여 "
        "현금흐름표에 표시하는 기준",
        "K-IFRS 1007",
    ),

    # 10. 회계정책·추정·오류
    (
        "회계정책의 변경과 회계추정치의 변경 및 전기오류 수정을 "
        "구분하여 회계처리하는 기준",
        "K-IFRS 1008",
    ),

    # 11. 보고기간후사건
    (
        "보고기간 후 발생한 사건을 수정을 요하는 사건과 수정을 "
        "요하지 않는 사건으로 구분하는 기준",
        "K-IFRS 1010",
    ),

    # 12. 종업원급여
    (
        "확정급여제도의 순확정급여부채와 재측정요소를 인식하고 "
        "측정하는 방법",
        "K-IFRS 1019",
    ),

    # 13. 정부보조금
    (
        "자산 관련 정부보조금과 수익 관련 정부보조금의 인식 및 "
        "재무제표 표시 방법",
        "K-IFRS 1020",
    ),

    # 14. 환율변동효과
    (
        "기능통화의 결정과 외화거래 및 해외사업장의 재무제표를 "
        "환산하는 기준",
        "K-IFRS 1021",
    ),

    # 15. 차입원가
    (
        "적격자산의 취득이나 건설에 직접 관련된 차입원가를 "
        "자본화하는 기준",
        "K-IFRS 1023",
    ),

    # 16. 특수관계자
    (
        "지배기업 종속기업 주요 경영진 등 특수관계자와의 거래 및 "
        "채권채무를 공시하는 기준",
        "K-IFRS 1024",
    ),

    # 17. 금융상품 표시
    (
        "금융상품을 금융자산 금융부채 또는 지분상품으로 분류하고 "
        "상계하여 표시할 수 있는 요건",
        "K-IFRS 1032",
    ),

    # 18. 주당이익
    (
        "기본주당이익과 희석주당이익의 계산 및 표시 방법",
        "K-IFRS 1033",
    ),

    # 19. 중간재무보고
    (
        "분기나 반기 중간재무제표의 최소 구성요소와 인식 및 "
        "측정 원칙",
        "K-IFRS 1034",
    ),

    # 20. 자산손상
    (
        "현금창출단위의 회수가능액을 계산하고 영업권 손상차손을 "
        "인식하는 방법",
        "K-IFRS 1036",
    ),

    # 21. 충당부채
    (
        "현재의무의 이행에 자원이 유출될 가능성이 높을 때 "
        "충당부채를 인식하고 우발부채를 공시하는 기준",
        "K-IFRS 1037",
    ),

    # 22. 무형자산
    (
        "연구단계 지출과 개발단계 지출을 구분하고 개발비를 "
        "무형자산으로 인식할 수 있는 요건",
        "K-IFRS 1038",
    ),

    # 23. 투자부동산
    (
        "임대수익이나 시세차익을 목적으로 보유하는 부동산의 "
        "원가모형 및 공정가치모형 적용 기준",
        "K-IFRS 1040",
    ),

    # 24. 농림어업
    (
        "생물자산과 수확시점의 수확물을 공정가치에서 "
        "매각부대원가를 차감한 금액으로 측정하는 기준",
        "K-IFRS 1041",
    ),

    # 25. 주식기준보상
    (
        "종업원에게 부여한 주식선택권의 가득조건과 공정가치를 "
        "반영하여 보상원가를 인식하는 기준",
        "K-IFRS 1102",
    ),

    # 26. 사업결합
    (
        "취득법을 적용하여 식별가능한 자산과 부채 및 영업권을 "
        "인식하는 사업결합 회계처리 기준",
        "K-IFRS 1103",
    ),

    # 27. 매각예정비유동자산
    (
        "비유동자산을 매각예정으로 분류하고 장부금액과 "
        "순공정가치 중 낮은 금액으로 측정하는 기준",
        "K-IFRS 1105",
    ),

    # 28. 영업부문
    (
        "최고영업의사결정자가 검토하는 내부보고에 기초하여 "
        "보고부문을 식별하고 공시하는 기준",
        "K-IFRS 1108",
    ),

    # 29. 연결재무제표
    (
        "투자대상에 대한 힘과 변동이익에 대한 노출 및 그 힘을 "
        "사용할 능력에 기초하여 지배력을 판단하는 기준",
        "K-IFRS 1110",
    ),

    # 30. 공정가치
    (
        "시장참여자 사이의 정상거래에서 자산을 매도할 때 받거나 "
        "부채를 이전할 때 지급하게 될 가격의 측정 기준",
        "K-IFRS 1113",
    ),
]


def build_retriever():
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL),
        persist_directory=PERSIST_DIR,
    )

    raw = vectorstore.get()

    docs = [
        Document(
            page_content=raw["documents"][i],
            metadata=raw["metadatas"][i],
        )
        for i in range(len(raw["documents"]))
    ]

    print(f"K-IFRS 청크 수: {len(docs)}")

    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = 10

    vector = vectorstore.as_retriever(search_kwargs={"k": 10})

    hybrid = EnsembleRetriever(
        retrievers=[bm25, vector],
        weights=[0.5, 0.5],
    )

    return {
        "BM25": bm25,
        "Vector": vector,
        "Hybrid": hybrid,
    }


def evaluate(name, retriever):
    recall_at_1_count = 0
    recall_at_3_count = 0

    print(f"\n\n========== {name} 평가 ==========")

    for index, (query, expected) in enumerate(QUERIES, start=1):
        hits = retriever.invoke(query)[:3]

        retrieved_standards = [
            doc.metadata.get("standard")
            for doc in hits
        ]

        success_at_1 = (
            len(retrieved_standards) >= 1
            and retrieved_standards[0] == expected
        )
        success_at_3 = expected in retrieved_standards

        recall_at_1_count += int(success_at_1)
        recall_at_3_count += int(success_at_3)

        print(f"\n[{index}] {query}")
        print(f"    정답: {expected}")
        print(f"    결과: {retrieved_standards}")
        print(f"    @1: {'PASS' if success_at_1 else 'FAIL'}")
        print(f"    @3: {'PASS' if success_at_3 else 'FAIL'}")

        if not success_at_3:
            print("    실패 결과 내용:")

            for rank, doc in enumerate(hits, start=1):
                standard = doc.metadata.get("standard")
                paragraph = doc.metadata.get("paragraph")
                content = doc.page_content[:200].replace("\n", " ")

                print(
                    f"      {rank}. "
                    f"{standard} / 문단 {paragraph} / {content}"
                )

    total = len(QUERIES)

    print(f"\n{name} 최종 결과")
    print(
        f"Recall@1: {recall_at_1_count}/{total} "
        f"({recall_at_1_count / total:.1%})"
    )
    print(
        f"Recall@3: {recall_at_3_count}/{total} "
        f"({recall_at_3_count / total:.1%})"
    )

    return {
        "name": name,
        "recall_at_1": recall_at_1_count / total,
        "recall_at_3": recall_at_3_count / total,
    }


def main():
    retrievers = build_retriever()

    results = []

    for name, retriever in retrievers.items():
        result = evaluate(name, retriever)
        results.append(result)

    print("\n\n========== 검색 방식 비교 ==========")

    for result in results:
        print(
            f"{result['name']:8s} "
            f"Recall@1={result['recall_at_1']:.1%}, "
            f"Recall@3={result['recall_at_3']:.1%}"
        )


if __name__ == "__main__":
    main()