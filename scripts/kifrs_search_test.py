from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI

load_dotenv()

PERSIST_DIR = "cache/kifrs_chroma"
COLLECTION_NAME = "kifrs"
EMBEDDING_MODEL = "text-embedding-3-large"

TRIALS = 5

rewrite_llm = ChatOpenAI(
    model="gpt-5.4-2026-03-05",
    temperature=0,
)

def rewrite_query(query):
    response = rewrite_llm.invoke(
        [
            (
                "system",
                "사용자의 회계 질문을 K-IFRS 검색용 문구로 바꿔라. "
                "핵심 거래와 회계 쟁점을 전문용어로 표현하되 기준서 번호와 문단 번호는 쓰지 마라. "
                "관련된 단어를 다 나열하지 말고 질문에 대한 적절한 답을 얻을 수 있도록 핵심적인 내용만 남겨라. "
                "\n예시:"
                "\n질문: 재고 판맨가격이 원가보다 낮아졌는데 그대로 두나요?"
                "\n검색어: 재고자산 순실현가능가치 감액"
            ),
            ("user", query),
        ]
    )
    return response.content.strip()


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

REALISTIC_PARAGRAPH_QUERIES = [
    {
        "id": "R01",
        "query": (
            "고객이 주문한 전용 설비를 8개월 동안 제작하고 있습니다. "
            "중간에 계약이 취소돼도 지금까지 만든 부분에 대해서는 대금을 "
            "청구할 수 있고, 이 설비는 다른 고객에게 팔기 어렵습니다. "
            "매출을 완성할 때 한꺼번에 잡아야 하나요?"
        ),
        "expected_standard": "K-IFRS 1115",
        "expected_paragraphs": {"35"},
    },
    {
        "id": "R02",
        "query": (
            "제품은 고객 창고에 도착했지만 검수확인서는 다음 달에 받았습니다. "
            "배송일과 검수일 중 어느 시점에 매출을 잡아야 하나요?"
        ),
        "expected_standard": "K-IFRS 1115",
        "expected_paragraphs": {"38", "B84", "B85"},
    },
    {
        "id": "R03",
        "query": (
            "작년에 개당 8만원에 들여온 상품이 유행이 지나 지금은 "
            "5만원 정도에만 팔립니다. 장부에는 아직 8만원으로 남아 있는데 "
            "결산 때 그대로 두어도 되나요?"
        ),
        "expected_standard": "K-IFRS 1002",
        "expected_paragraphs": {"28"},
    },
    {
        "id": "R04",
        "query": (
            "작년에 잘 팔리지 않아서 재고 금액을 낮췄는데 올해 판매가격이 "
            "회복됐습니다. 작년에 줄였던 금액을 다시 올릴 수 있나요?"
        ),
        "expected_standard": "K-IFRS 1002",
        "expected_paragraphs": {"33"},
    },
    {
        "id": "R05",
        "query": (
            "상품을 고객에게 판매했는데 창고에서 빠져나간 상품 금액을 "
            "이번 달 비용으로 잡아야 하는지, 대금을 받은 달에 잡아야 하는지 "
            "헷갈립니다."
        ),
        "expected_standard": "K-IFRS 1002",
        "expected_paragraphs": {"34"},
    },
    {
        "id": "R06",
        "query": (
            "인수한 사업부의 실적이 예상보다 크게 나빠졌습니다. 해당 사업부에는 "
            "인수할 때 생긴 영업권과 여러 설비가 함께 들어 있습니다. 손실을 "
            "반영한다면 영업권과 설비 중 어디부터 줄여야 하나요?"
        ),
        "expected_standard": "K-IFRS 1036",
        "expected_paragraphs": {"104"},
    },
    {
        "id": "R07",
        "query": (
            "사무실을 5년간 빌렸고 보증금 외에는 매월 임차료를 지급합니다. "
            "예전처럼 매월 임차료만 비용으로 처리하면 되는지, 계약을 시작할 때 "
            "별도로 장부에 올려야 하는 항목이 있는지 궁금합니다."
        ),
        "expected_standard": "K-IFRS 1116",
        "expected_paragraphs": {"22"},
    },
    {
        "id": "R08",
        "query": (
            "장비 임대계약을 새로 체결했습니다. 앞으로 4년 동안 지급할 금액을 "
            "장부에 얼마로 올려야 하나요? 계약서에는 이자율이 따로 없습니다."
        ),
        "expected_standard": "K-IFRS 1116",
        "expected_paragraphs": {"26"},
    },
    {
        "id": "R09",
        "query": (
            "차량을 4년 동안 빌린 뒤 소유권을 넘겨받기로 했습니다. "
            "차량 사용기간은 7년으로 예상됩니다. 관련 자산을 4년과 7년 중 "
            "어느 기간에 걸쳐 비용 처리해야 하나요?"
        ),
        "expected_standard": "K-IFRS 1116",
        "expected_paragraphs": {"32"},
    },
    {
        "id": "R10",
        "query": (
            "임대차 계약을 시작한 후 매월 임차료를 지급하고 있습니다. "
            "처음 장부에 잡은 의무 금액에서 지급액만 빼면 되는 건가요? "
            "시간이 지나면서 발생하는 이자는 어떻게 반영하나요?"
        ),
        "expected_standard": "K-IFRS 1116",
        "expected_paragraphs": {"36"},
    },
    {
        "id": "R11",
        "query": (
            "매장 임대료가 매출에 따라 달라지는 조건으로 계약이 바뀌었습니다. "
            "계약 변경으로 앞으로 낼 금액이 달라지면 기존에 잡아둔 금액과 "
            "매장 사용권은 어떻게 조정해야 하나요?"
        ),
        "expected_standard": "K-IFRS 1116",
        "expected_paragraphs": {"38", "45", "46"},
    },
    {
        "id": "R12",
        "query": (
            "판매한 제품 중 일부에 결함이 발견되어 고객 보상 가능성이 큽니다. "
            "아직 고객이 소송을 제기하지 않았고 실제 보상액도 확정되지 않았는데 "
            "올해 결산에 부채를 잡아야 하나요?"
        ),
        "expected_standard": "K-IFRS 1037",
        "expected_paragraphs": {"14"},
    },
    {
        "id": "R13",
        "query": (
            "회사에 불리한 소송이 진행 중이지만 변호사는 패소 가능성을 "
            "40% 정도로 보고 있습니다. 예상 배상액을 장부에 부채로 잡아야 "
            "하나요, 주석에만 적으면 되나요?"
        ),
        "expected_standard": "K-IFRS 1037",
        "expected_paragraphs": {"23"},
    },
    {
        "id": "R14",
        "query": (
            "1년간 판매한 가전제품 1만 대에 무상수리 약정이 있습니다. "
            "제품 한 대마다 고장날 가능성은 낮습니다. 실제 고장 신고가 들어온 "
            "제품만 비용을 잡아도 되나요?"
        ),
        "expected_standard": "K-IFRS 1037",
        "expected_paragraphs": {"24"},
    },
    {
        "id": "R15",
        "query": (
            "작년에는 지급 가능성이 낮다고 보아 주석에만 적었던 소송이 "
            "올해 들어 패소할 가능성이 커졌습니다. 판결이 나올 때까지 계속 "
            "주석에만 두어도 되나요?"
        ),
        "expected_standard": "K-IFRS 1037",
        "expected_paragraphs": {"14", "30"},
    },
    {
        "id": "R16",
        "query": (
            "공장 철거 의무가 있어 결산에 반영해야 하는데 실제 철거는 "
            "몇 년 뒤이고 견적도 업체마다 다릅니다. 어느 금액을 장부에 "
            "올려야 하나요?"
        ),
        "expected_standard": "K-IFRS 1037",
        "expected_paragraphs": {"36", "40"},
    },
    {
        "id": "R17",
        "query": (
            "기계의 사용기간을 원래 10년으로 봤는데 최근 생산량 감소로 "
            "앞으로 6년밖에 사용하지 못할 것 같습니다. 과거 감가상각비까지 "
            "다시 계산해야 하나요?"
        ),
        "expected_standard": "K-IFRS 1016",
        "expected_paragraphs": {"51"},
    },
    {
        "id": "R18",
        "query": (
            "올해 결산 중 작년 재고수량이 잘못 입력되어 작년 이익이 "
            "과대계상된 사실을 발견했습니다. 올해 비용으로 한꺼번에 처리해도 "
            "되나요?"
        ),
        "expected_standard": "K-IFRS 1008",
        "expected_paragraphs": {"46"},
    },
    {
        "id": "R19",
        "query": (
            "작년에는 받을 수 있다고 판단한 거래처 채권이 올해 갑자기 "
            "부실해졌습니다. 작년 판단이 틀린 오류로 봐서 작년 재무제표를 "
            "고쳐야 하나요?"
        ),
        "expected_standard": "K-IFRS 1008",
        "expected_paragraphs": {"48"},
    },
    {
        "id": "R20",
        "query": (
            "오래전부터 적용한 회계처리를 바꾸려는데 당시 자료가 거의 "
            "남아 있지 않습니다. 지금 알고 있는 정보로 과거 수치를 추정해서 "
            "전부 다시 작성해야 하나요?"
        ),
        "expected_standard": "K-IFRS 1008",
        "expected_paragraphs": {"24", "25", "27", "52", "53"},
    },
    {
        "id": "R21",
        "query": (
            "대출 실행 당시에는 문제가 없던 차주의 신용등급이 크게 "
            "하락했고 연체 가능성도 높아졌습니다. 앞으로 1년치 부실만 "
            "예상하면 되나요, 대출 만기까지 봐야 하나요?"
        ),
        "expected_standard": "K-IFRS 1109",
        "expected_paragraphs": {"5.5.3", "B5.5.7", "B5.5.43"},
    },
    {
        "id": "R22",
        "query": (
            "매출채권 거래처의 신용상태가 작년과 거의 같습니다. "
            "아직 부실 징후가 없는데도 만기 전체 기간의 예상 손실을 "
            "반영해야 하나요?"
        ),
        "expected_standard": "K-IFRS 1109",
        "expected_paragraphs": {"5.5.5"},
    },
    {
        "id": "R23",
        "query": (
            "고객 신용이 처음보다 나빠졌는지 판단하려고 합니다. "
            "충당금 금액이 얼마나 증가했는지만 비교하면 되나요?"
        ),
        "expected_standard": "K-IFRS 1109",
        "expected_paragraphs": {"5.5.9", "B5.5.36"},
    },
    {
        "id": "R24",
        "query": (
            "대손 예상액을 계산하면서 과거 연체율만 사용했습니다. "
            "현재 경기와 향후 경기 전망, 돈을 받는 시점에 따른 가치 차이도 "
            "계산에 넣어야 하나요?"
        ),
        "expected_standard": "K-IFRS 1109",
        "expected_paragraphs": {"5.5.17"},
    },
    {
        "id": "R25",
        "query": (
            "회계팀에서 1년 예상손실을 계산하면서 앞으로 1년 동안 "
            "못 받을 것으로 예상되는 현금 전액을 잡았습니다. "
            "이 계산 방식이 맞나요?"
        ),
        "expected_standard": "K-IFRS 1109",
        "expected_paragraphs": {"B5.5.43"},
    },
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
        "Vector": vector,
    }


# def evaluate(name, retriever):
#     recall_at_1_count = 0
#     recall_at_3_count = 0

#     print(f"\n\n========== {name} 평가 ==========")

#     for index, (query, expected) in enumerate(QUERIES, start=1):
#         hits = retriever.invoke(query)[:3]

#         retrieved_standards = [
#             doc.metadata.get("standard")
#             for doc in hits
#         ]

#         success_at_1 = (
#             len(retrieved_standards) >= 1
#             and retrieved_standards[0] == expected
#         )
#         success_at_3 = expected in retrieved_standards

#         recall_at_1_count += int(success_at_1)
#         recall_at_3_count += int(success_at_3)

#         print(f"\n[{index}] {query}")
#         print(f"    정답: {expected}")
#         print(f"    결과: {retrieved_standards}")
#         print(f"    @1: {'PASS' if success_at_1 else 'FAIL'}")
#         print(f"    @3: {'PASS' if success_at_3 else 'FAIL'}")

#         if not success_at_3:
#             print("    실패 결과 내용:")

#             for rank, doc in enumerate(hits, start=1):
#                 standard = doc.metadata.get("standard")
#                 paragraph = doc.metadata.get("paragraph")
#                 content = doc.page_content[:200].replace("\n", " ")

#                 print(
#                     f"      {rank}. "
#                     f"{standard} / 문단 {paragraph} / {content}"
#                 )

#     total = len(QUERIES)

#     print(f"\n{name} 최종 결과")
#     print(
#         f"Recall@1: {recall_at_1_count}/{total} "
#         f"({recall_at_1_count / total:.1%})"
#     )
#     print(
#         f"Recall@3: {recall_at_3_count}/{total} "
#         f"({recall_at_3_count / total:.1%})"
#     )

#     return {
#         "name": name,
#         "recall_at_1": recall_at_1_count / total,
#         "recall_at_3": recall_at_3_count / total,
#     }


def evaluate(name, retriever):
    ks = (1, 3, 5, 8)
    hits_by_k = {k: 0 for k in ks}
    rr_sum = 0
    passed_ids = []

    print(f"\n========== {name} 평가 ==========")

    for item in REALISTIC_PARAGRAPH_QUERIES:
        rewritten = rewrite_query(item["query"])
        docs = retriever.invoke(rewritten)[:max(ks)]
        expected_paras = {
            str(p) for p in item["expected_paragraphs"]
        }

        rank = next(
            (
                i for i, doc in enumerate(docs, 1)
                if doc.metadata.get("standard") == item["expected_standard"]
                and str(doc.metadata.get("paragraph")) in expected_paras
            ),
            None,
        )
        if rank is not None:
            passed_ids.append(item["id"])

        for k in ks:
            hits_by_k[k] += int(
                rank is not None and rank <= k
            )

        rr_sum += 1 / rank if rank else 0

        print(
            f"{item['id']}: "
            f"{'PASS ' + str(rank) if rank else 'FAIL'}"
        )

    total = len(REALISTIC_PARAGRAPH_QUERIES)

    result = {
        f"recall_at_{k}": hits_by_k[k] / total
        for k in ks
    }
    result["mrr"] = rr_sum / total

    print(name, result)
    return {"name": name, "passed_ids": passed_ids, **result}


def main():
    retriever = build_retriever()["Vector"]

    trial_results = []
    item_success = {
        item["id"]: 0
        for item in REALISTIC_PARAGRAPH_QUERIES
    }

    for trial in range(1, TRIALS + 1):
        result = evaluate(
            f"Vector Trial {trial}",
            retriever,
        )
        trial_results.append(result)

        for item_id in result["passed_ids"]:
            item_success[item_id] += 1

    print("\n\n========== 반복 평가 결과 ==========")

    for k in (1, 3, 5, 8):
        key = f"recall_at_{k}"
        values = [
            result[key]
            for result in trial_results
        ]

        print(
            f"Recall@{k}: "
            f"평균={sum(values) / len(values):.1%}, "
            f"최저={min(values):.1%}, "
            f"최고={max(values):.1%}"
        )

    mrr_values = [
        result["mrr"]
        for result in trial_results
    ]

    print(
        f"MRR: "
        f"평균={sum(mrr_values) / len(mrr_values):.3f}, "
        f"최저={min(mrr_values):.3f}, "
        f"최고={max(mrr_values):.3f}"
    )

    print("\n========== 문항별 성공률 ==========")

    for item in REALISTIC_PARAGRAPH_QUERIES:
        item_id = item["id"]
        count = item_success[item_id]

        print(
            f"{item_id}: "
            f"{count}/{TRIALS} "
            f"({count / TRIALS:.0%})"
        )

if __name__ == "__main__":
    main()