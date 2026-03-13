from researchclaw.agents.resource_lookup import (
    build_resource_query_context,
    format_resource_lookup_response,
    rank_resource_results,
)


def test_build_resource_query_context_detects_exam_request() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    assert context.year == "2025"
    assert "exam_paper" in context.resource_types
    assert "数学" in context.search_query
    assert "pdf" in context.search_query


def test_build_resource_query_context_detects_video_request() -> None:
    context = build_resource_query_context("推荐一下导数教学视频")
    assert context is not None
    assert "video" in context.resource_types
    assert "导数" in context.topic_terms
    assert "数学" in context.search_query


def test_rank_resource_results_prefers_exact_exam_page() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "2025全国各地高考试题及答案出炉！高清PDF版可下载 - 搜狐",
                "url": "https://www.sohu.com/a/902869733_121123754",
                "content": "2025年高考新课标I卷、新课标Ⅱ卷试题及答案，数学试题及答案。",
            },
            {
                "title": "2025年高考数学新课标I卷试题 - 网易",
                "url": "https://www.163.com/dy/article/K1FN4C3K054535JN.html",
                "content": "2025年高考数学新课标I卷试题|广东|山东|数学试卷。",
            },
            {
                "title": "[PDF] 數學 - 香港考試及評核局",
                "url": "https://www.hkeaa.edu.hk/DocLibrary/HKDSE/Subject_Information/math/2025hkdse-c-math.pdf",
                "content": "香港数学 PDF",
            },
        ],
    )
    assert ranked[0].url == "https://www.163.com/dy/article/K1FN4C3K054535JN.html"
    assert ranked[-1].source_host == "www.hkeaa.edu.hk"


def test_format_resource_lookup_response_contains_links() -> None:
    context = build_resource_query_context("帮我找2025年新高考一卷的数学卷子")
    assert context is not None
    ranked = rank_resource_results(
        context,
        [
            {
                "title": "2025年高考数学新课标I卷试题 - 网易",
                "url": "https://www.163.com/dy/article/K1FN4C3K054535JN.html",
                "content": "2025年高考数学新课标I卷试题|广东|山东|数学试卷。",
            },
        ],
    )
    response = format_resource_lookup_response(
        context,
        ranked,
        excerpt="提取内容明确包含新课标I卷数学试题。",
        verified_title="2025年高考数学新课标I卷试题|广东|山东|数学试卷_网易订阅",
    )
    assert "链接：https://www.163.com/dy/article/K1FN4C3K054535JN.html" in response
    assert "已验证页面标题" in response
